"""Tests for permission policies: placeholder substitution, rendering, the derivation hook, and the path resolver."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import SimpleTestCase

from nautobot.core.testing import TestCase
from nautobot.core.utils.orm_paths import (
    constraint_to_rows,
    enumerate_model_fields,
    find_relation_paths,
    lookups_for_field,
    rows_to_constraint,
    split_path_and_lookup,
    validate_lookup_path,
)
from nautobot.dcim.models import Device, Interface, Location
from nautobot.extras.models import Status
from nautobot.tenancy.models import Tenant
from nautobot.users.models import PermissionPolicy, PolicyParameter

User = get_user_model()


class PathResolverTest(SimpleTestCase):
    def test_interface_reaches_tenant_through_device_first(self):
        candidates = find_relation_paths(Interface, Tenant)
        self.assertEqual(candidates[0].path, "device__tenant")
        self.assertEqual(candidates[0].depth, 2)
        self.assertEqual([hop.model for hop in candidates[0].relations], ["dcim.device", "tenancy.tenant"])
        self.assertEqual(
            [candidate.depth for candidate in candidates], sorted(candidate.depth for candidate in candidates)
        )

    def test_device_reaches_tenant_directly(self):
        self.assertEqual(find_relation_paths(Device, Tenant)[0].path, "tenant")

    def test_no_path_is_empty_list(self):
        self.assertEqual(find_relation_paths(Status, Tenant), [])

    def test_same_model_offers_pk(self):
        self.assertEqual(find_relation_paths(Tenant, Tenant)[0].path, "pk")

    def test_multi_valued_relations_are_excluded(self):
        # Device.tags is M2M; Device.interfaces is a reverse relation. Neither may appear in a path.
        for candidate in find_relation_paths(Device, Tenant):
            self.assertNotIn("tags", candidate.path)
            self.assertNotIn("interfaces", candidate.path)

    def test_validate_lookup_path(self):
        self.assertEqual(validate_lookup_path(Interface, "device__tenant__name").name, "name")
        self.assertTrue(validate_lookup_path(Device, "pk").primary_key)
        self.assertEqual(validate_lookup_path(Interface, "device__pk").model, Device)
        with self.assertRaisesRegex(ValidationError, "multi-valued relation at 'tags'"):
            validate_lookup_path(Device, "tags__name")
        with self.assertRaisesRegex(ValidationError, "multi-valued relation at 'interfaces'"):
            validate_lookup_path(Device, "interfaces__name")
        with self.assertRaisesRegex(ValidationError, "not a valid lookup path"):
            validate_lookup_path(Device, "nonexistent__field")
        with self.assertRaises(ValidationError):
            validate_lookup_path(Device, "")

    def test_lookups_for_field(self):
        self.assertIn("icontains", lookups_for_field(Device._meta.get_field("name")))
        self.assertEqual(lookups_for_field(Device._meta.get_field("tenant"))[:2], ("exact", "in"))
        self.assertIn("isnull", lookups_for_field(Device._meta.get_field("tenant")))
        self.assertNotIn("icontains", lookups_for_field(Device._meta.get_field("tenant")))
        # Tree-model targets (Location) additionally offer `in_tree`; plain relations (Tenant) do not.
        self.assertIn("in_tree", lookups_for_field(Device._meta.get_field("location")))
        self.assertIn("in_tree", lookups_for_field(Location._meta.pk))
        self.assertNotIn("in_tree", lookups_for_field(Device._meta.get_field("tenant")))
        self.assertIn("in_tree", find_relation_paths(Device, Location)[0].lookups)

    def test_enumerate_model_fields_one_level(self):
        nodes = enumerate_model_fields(Interface)
        by_name = {node.name: node for node in nodes}
        self.assertNotIn("tagged_vlans", by_name)  # M2M
        self.assertNotIn("ip_addresses", by_name)  # M2M
        self.assertTrue(by_name["device"].expandable)
        self.assertEqual(by_name["device"].related_model, "dcim.device")
        self.assertFalse(by_name["name"].is_relation)
        # Depth cap: nothing is expandable at the maximum depth.
        self.assertFalse(any(node.expandable for node in enumerate_model_fields(Interface, depth=3)))

    def test_split_path_and_lookup(self):
        self.assertEqual(split_path_and_lookup(Device, "tenant__name__icontains"), ("tenant__name", "icontains"))
        self.assertEqual(split_path_and_lookup(Device, "tenant__name"), ("tenant__name", "exact"))
        self.assertEqual(split_path_and_lookup(Device, "tenant__in"), ("tenant", "in"))

    def test_constraint_round_trip(self):
        constraint = {"tenant__name__icontains": "x", "status": "$user", "location__in": ["a"], "name": "{{ n }}"}
        rows = constraint_to_rows(Device, constraint)
        self.assertEqual(len(rows), 1)
        self.assertEqual([row.source for row in rows[0]], ["literal", "user", "literal", "parameter"])
        self.assertEqual(rows_to_constraint(rows), constraint)
        grouped = [{"name": "a"}, {"name": "b"}]
        self.assertEqual(rows_to_constraint(constraint_to_rows(Device, grouped)), grouped)
        self.assertEqual(constraint_to_rows(Device, {}), [[]])

    def test_constraint_round_trip_refuses_unrepresentable(self):
        self.assertIsNone(constraint_to_rows(Device, {"tags__name": "x"}))
        self.assertIsNone(constraint_to_rows(Device, {"nonexistent": "x"}))
        self.assertIsNone(constraint_to_rows(Device, {"name": {"nested": True}}))
        self.assertIsNone(constraint_to_rows(Device, ["not-a-dict"]))


def create_tenant_policy(name="Tenant device viewer", actions=("view",)):
    """Create a policy with a multi-valued `tenant` parameter over Device and Interface."""
    policy = PermissionPolicy.objects.create(name=name)
    PolicyParameter(
        policy=policy,
        name="tenant",
        kind="object",
        target_content_type=ContentType.objects.get_for_model(Tenant),
        multiple=True,
    ).validated_save()
    # PLACEHOLDER: will be replaced in C08 (Policy rule model and stack): the Device and Interface rules.
    return policy


class PolicyModelValidationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.device_ct = ContentType.objects.get_for_model(Device)
        cls.interface_ct = ContentType.objects.get_for_model(Interface)
        cls.tenant_ct = ContentType.objects.get_for_model(Tenant)
        cls.policy = create_tenant_policy()
        cls.tenants = list(Tenant.objects.all()[:2])

    def test_parameter_kind_validation(self):
        with self.assertRaises(ValidationError):
            PolicyParameter(policy=self.policy, name="other", kind="object").full_clean()
        with self.assertRaises(ValidationError):
            PolicyParameter(
                policy=self.policy, name="other", kind="string", target_content_type=self.tenant_ct
            ).full_clean()
        with self.assertRaises(ValidationError):
            PolicyParameter(policy=self.policy, name="Bad Name", kind="string").full_clean()

    def test_clone_params_reference_source_policy(self):
        self.assertEqual(self.policy.clone_fields, ["description"])
        self.assertEqual(self.policy.get_clone_extra_params(), {"clone_from": str(self.policy.pk)})


class ConstraintToFilterParamsTest(TestCase):
    """Only constraints with an equivalent FilterSet query translate; everything else yields None."""

    def test_translations(self):
        from nautobot.core.utils.filtering import constraint_to_filter_params

        tenant = str(Tenant.objects.first().pk)
        location = str(Location.objects.first().pk)
        self.assertEqual(constraint_to_filter_params(Device, {"tenant__in": [tenant]}), [("tenant", tenant)])
        self.assertEqual(constraint_to_filter_params(Device, {"tenant": tenant}), [("tenant", tenant)])
        self.assertEqual(constraint_to_filter_params(Device, {"location__in_tree": location}), [("location", location)])
        self.assertEqual(constraint_to_filter_params(Device, {"name__icontains": "x"}), [("name__ic", "x")])
        self.assertEqual(constraint_to_filter_params(Device, {}), [])
        self.assertEqual(
            constraint_to_filter_params(Device, {"tenant": "$user"}, tokens={"$user": tenant}), [("tenant", tenant)]
        )
        # Exact match on a tree field is narrower than the tree-aware `location` filter: no link.
        self.assertIsNone(constraint_to_filter_params(Device, {"location": location}))
        self.assertIsNone(constraint_to_filter_params(Device, [{"name": "a"}, {"name": "b"}]))
        self.assertIsNone(constraint_to_filter_params(Device, {"nonexistent": "x"}))
        self.assertIsNone(constraint_to_filter_params(Device, {"tenant__name": "x"}))
        # Booleans render as the strings the filters expect; an `isnull` lookup maps to the `__isnull` filter.
        self.assertEqual(
            constraint_to_filter_params(Device, {"asset_tag__isnull": True}), [("asset_tag__isnull", "True")]
        )
        # A null value has no query-string representation.
        self.assertIsNone(constraint_to_filter_params(Device, {"asset_tag": None}))


class DemoDataCommandTest(TestCase):
    """`create_permission_policy_demo_data` builds the documented demo personas and is idempotent."""

    def _run(self, *args):
        out = StringIO()
        call_command("create_permission_policy_demo_data", *args, stdout=out)
        return out.getvalue()

    def test_creates_personas_idempotently(self):
        output = self._run()
        self.assertIn("password: nautobot", output)
        for username in ("ntc-operator", "it-amer", "it-emea", "it-apac", "telco-owner", "job-runner"):
            user = User.objects.get(username=username)
            self.assertTrue(user.check_password("nautobot"))
            self.assertTrue(user.groups.exists())
        policies = PermissionPolicy.objects.filter(name__startswith="demo-").count()
        self.assertEqual(policies, 3)
        # PLACEHOLDER: will be replaced in C11 (Policy assignment model and stack): assignment assertions.

        self._run()  # second run updates in place
        self.assertEqual(PermissionPolicy.objects.filter(name__startswith="demo-").count(), policies)

    def test_flush_removes_demo_objects_only(self):
        self._run()
        builtin_count = PermissionPolicy.objects.filter(name__startswith="nautobot-default-").count()
        output = self._run("--flush")
        self.assertIn("Removed", output)
        self.assertFalse(PermissionPolicy.objects.filter(name__startswith="demo-").exists())
        self.assertFalse(User.objects.filter(username="job-runner").exists())
        self.assertEqual(PermissionPolicy.objects.filter(name__startswith="nautobot-default-").count(), builtin_count)
