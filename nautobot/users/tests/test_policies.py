"""Tests for permission policies: placeholder substitution, rendering, the derivation hook, and the path resolver."""

import importlib
from io import StringIO

from django.apps import apps
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
from nautobot.core.utils.permissions import qs_filter_from_constraints, validate_constraints_for_model
from nautobot.dcim.models import Device, Interface, Location, Rack
from nautobot.extras.models import Status
from nautobot.tenancy.models import Tenant
from nautobot.users.models import PermissionPolicy, PolicyParameter, PolicyRule
from nautobot.users.policies import (
    extract_placeholders,
    find_malformed_placeholders,
    PolicyRenderError,
    render_as_object_permissions,
    substitute_placeholders,
)

User = get_user_model()


class SubstitutePlaceholdersTest(SimpleTestCase):
    def test_whole_value_replacement(self):
        rendered = substitute_placeholders({"tenant__in": "{{ tenant }}"}, {"tenant": ["a", "b"]})
        self.assertEqual(rendered, [{"tenant__in": ["a", "b"]}])

    def test_scalar_replacement_and_whitespace_variants(self):
        rendered = substitute_placeholders({"tenant": "{{tenant}}", "site": "{{  site  }}"}, {"tenant": "x", "site": 1})
        self.assertEqual(rendered, [{"tenant": "x", "site": 1}])

    def test_list_value_is_spliced_into_list(self):
        rendered = substitute_placeholders({"tenant__in": ["{{ tenants }}", "z"]}, {"tenants": ["a", "b"]})
        self.assertEqual(rendered, [{"tenant__in": ["a", "b", "z"]}])

    def test_user_token_passes_through_unchanged(self):
        rendered = substitute_placeholders({"user": "$user", "tenant": "{{ tenant }}"}, {"tenant": "x"})
        self.assertEqual(rendered, [{"user": "$user", "tenant": "x"}])

    def test_partial_string_is_not_a_placeholder(self):
        template = {"name__startswith": "prefix-{{ tenant }}"}
        self.assertEqual(substitute_placeholders(template, {"tenant": "x"}), [template])
        self.assertEqual(find_malformed_placeholders(template), ["prefix-{{ tenant }}"])
        self.assertEqual(find_malformed_placeholders({"{{ tenant }}": "x"}), ["{{ tenant }}"])

    def test_missing_value_raises(self):
        with self.assertRaises(PolicyRenderError):
            substitute_placeholders({"tenant": "{{ tenant }}"}, {})

    def test_string_value_cannot_change_structure(self):
        hostile = '{"name": "x"}, "tenant__name__in": ["y"], "a__b'
        rendered = substitute_placeholders({"name": "{{ name }}"}, {"name": hostile})
        self.assertEqual(rendered, [{"name": hostile}])

    def test_empty_template_grants_everything(self):
        self.assertEqual(substitute_placeholders({}, {}), [{}])
        self.assertEqual(substitute_placeholders(None, {}), [{}])
        self.assertEqual(qs_filter_from_constraints(substitute_placeholders({}, {})).children, [])

    def test_list_template_keeps_groups(self):
        rendered = substitute_placeholders([{"a": "{{ x }}"}, {"b": 1}], {"x": 2})
        self.assertEqual(rendered, [{"a": 2}, {"b": 1}])

    def test_extract_placeholders(self):
        template = [{"tenant__in": "{{ tenant }}", "nested": ["{{ other }}", "literal"]}, {"user": "$user"}]
        self.assertEqual(extract_placeholders(template), {"tenant", "other"})


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
    PolicyRule(
        policy=policy,
        content_type=ContentType.objects.get_for_model(Device),
        actions=list(actions),
        constraint_template={"tenant__in": "{{ tenant }}"},
        path_map={"tenant": {"path": "tenant", "lookup": "in"}},
    ).validated_save()
    PolicyRule(
        policy=policy,
        content_type=ContentType.objects.get_for_model(Interface),
        actions=list(actions),
        constraint_template={"device__tenant__in": "{{ tenant }}"},
        path_map={"tenant": {"path": "device__tenant", "lookup": "in"}},
    ).validated_save()
    return policy


class PolicyModelValidationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.device_ct = ContentType.objects.get_for_model(Device)
        cls.interface_ct = ContentType.objects.get_for_model(Interface)
        cls.tenant_ct = ContentType.objects.get_for_model(Tenant)
        cls.policy = create_tenant_policy()
        cls.tenants = list(Tenant.objects.all()[:2])

    def _rule(self, **overrides):
        kwargs = {
            "policy": self.policy,
            "content_type": ContentType.objects.get_for_model(Location),
            "actions": ["view"],
            "constraint_template": {"tenant__in": "{{ tenant }}"},
            "path_map": {"tenant": {"path": "tenant", "lookup": "in"}},
        }
        kwargs.update(overrides)
        return PolicyRule(**kwargs)

    def test_valid_rule_passes(self):
        self._rule().full_clean()

    def test_rule_placeholder_without_path_map_entry_names_content_type(self):
        with self.assertRaises(ValidationError) as cm:
            self._rule(path_map={}).full_clean()
        message = str(cm.exception.message_dict["constraint_template"])
        self.assertIn("dcim.location", message)
        self.assertIn("no entry for 'tenant'", message)

    def test_rule_need_not_use_every_parameter(self):
        """A rule whose template does not mention a parameter is valid; it is simply not scoped by it."""
        self._rule(constraint_template={}, path_map={}).full_clean()
        self._rule(constraint_template={"name__istartswith": "core-"}, path_map={}).full_clean()

    def test_rule_rejects_legacy_unconstrained_entry(self):
        with self.assertRaises(ValidationError) as cm:
            self._rule(constraint_template={}, path_map={"tenant": {"unconstrained": True}}).full_clean()
        self.assertIn('exactly the keys "path" and "lookup"', str(cm.exception.message_dict["path_map"]))

    def test_rule_malformed_definitions_are_reported(self):
        cases = {
            "actions": {"actions": ["view", ""]},
            "constraint_template": {"constraint_template": "nope"},
            "path_map": {"path_map": []},
        }
        for field, overrides in cases.items():
            with self.subTest(field=field):
                with self.assertRaises(ValidationError) as cm:
                    self._rule(**overrides).full_clean()
                self.assertIn(field, cm.exception.message_dict)

    def test_rule_path_map_entries_are_checked(self):
        cases = [
            (
                {"tenant": {"path": "tenant", "lookup": "in"}, "nope": {"path": "name", "lookup": "exact"}},
                "not a parameter",
            ),
            ({"tenant": "tenant"}, "must be a JSON object"),
            ({"tenant": {"path": "tenant", "lookup": "bogus"}}, "lookup 'bogus' is not valid"),
        ]
        for path_map, message in cases:
            with self.subTest(message=message):
                with self.assertRaises(ValidationError) as cm:
                    self._rule(path_map=path_map).full_clean()
                self.assertIn(message, str(cm.exception.message_dict["path_map"]))

    def test_rule_path_without_placeholder(self):
        with self.assertRaises(ValidationError) as cm:
            self._rule(constraint_template={}).full_clean()
        self.assertIn("does not use", str(cm.exception.message_dict["constraint_template"]))

    def test_rule_path_to_wrong_model(self):
        with self.assertRaises(ValidationError) as cm:
            self._rule(
                constraint_template={"location_type__in": "{{ tenant }}"},
                path_map={"tenant": {"path": "location_type", "lookup": "in"}},
            ).full_clean()
        self.assertIn("does not reach tenancy.Tenant", str(cm.exception.message_dict["path_map"]))

    def test_rule_wrong_lookup_for_multiple_parameter(self):
        with self.assertRaises(ValidationError) as cm:
            self._rule(
                constraint_template={"tenant": "{{ tenant }}"},
                path_map={"tenant": {"path": "tenant", "lookup": "exact"}},
            ).full_clean()
        self.assertIn("requires the 'in' lookup", str(cm.exception.message_dict["path_map"]))

    def test_rule_multi_valued_path_rejected(self):
        with self.assertRaises(ValidationError) as cm:
            self._rule(
                content_type=self.device_ct,
                constraint_template={"tags__tenant__in": "{{ tenant }}"},
                path_map={"tenant": {"path": "tags__tenant", "lookup": "in"}},
            ).full_clean()
        self.assertIn("multi-valued relation", str(cm.exception.message_dict["path_map"]))

    def test_rule_undeclared_placeholder(self):
        with self.assertRaises(ValidationError) as cm:
            self._rule(constraint_template={"tenant__in": "{{ tenant }}", "name": "{{ nope }}"}).full_clean()
        self.assertIn("undeclared parameter 'nope'", str(cm.exception.message_dict["constraint_template"]))

    def test_rule_malformed_placeholder(self):
        with self.assertRaises(ValidationError) as cm:
            self._rule(constraint_template={"tenant__in": "{{ tenant }}", "name": "x-{{ tenant }}"}).full_clean()
        self.assertIn("complete value", str(cm.exception.message_dict["constraint_template"]))

    def test_rule_template_invalid_for_model(self):
        with self.assertRaises(ValidationError) as cm:
            self._rule(constraint_template={"tenant__in": "{{ tenant }}", "bogus_field": 1}).full_clean()
        self.assertIn("Invalid filter for dcim.Location", str(cm.exception.message_dict["constraint_template"]))

    def test_rule_requires_actions(self):
        with self.assertRaises(ValidationError) as cm:
            self._rule(actions=[]).full_clean()
        self.assertIn("actions", cm.exception.message_dict)

    def test_default_constraint_template(self):
        self.assertEqual(
            PolicyRule.default_constraint_template(
                {
                    "tenant": {"path": "device__tenant", "lookup": "in"},
                    "x": {"path": "name", "lookup": "exact"},
                }
            ),
            {"device__tenant__in": "{{ tenant }}", "name": "{{ x }}"},
        )

    def test_in_tree_lookup_accepted_for_tree_targets_only(self):
        policy = PermissionPolicy.objects.create(name="Region policy")
        PolicyParameter(
            policy=policy,
            name="region",
            kind="object",
            target_content_type=ContentType.objects.get_for_model(Location),
            multiple=False,
        ).validated_save()
        PolicyRule(
            policy=policy,
            content_type=self.device_ct,
            actions=["view"],
            constraint_template={"location__in_tree": "{{ region }}"},
            path_map={"region": {"path": "location", "lookup": "in_tree"}},
        ).full_clean()
        PolicyRule(
            policy=policy,
            content_type=ContentType.objects.get_for_model(Location),
            actions=["view"],
            constraint_template={"pk__in_tree": "{{ region }}"},
            path_map={"region": {"path": "pk", "lookup": "in_tree"}},
        ).full_clean()
        # Tenant is not a tree model, so `in_tree` is rejected for the tenant parameter.
        with self.assertRaises(ValidationError) as cm:
            self._rule(
                content_type=self.device_ct,
                constraint_template={"tenant__in_tree": "{{ tenant }}"},
                path_map={"tenant": {"path": "tenant", "lookup": "in_tree"}},
            ).full_clean()
        self.assertIn("requires the 'in' lookup", str(cm.exception.message_dict["path_map"]))

    def test_string_parameter_path_must_not_end_at_relation(self):
        policy = PermissionPolicy.objects.create(name="String policy")
        PolicyParameter(policy=policy, name="prefix", kind="string").validated_save()
        with self.assertRaises(ValidationError) as cm:
            PolicyRule(
                policy=policy,
                content_type=self.device_ct,
                actions=["view"],
                constraint_template={"tenant": "{{ prefix }}"},
                path_map={"prefix": {"path": "tenant", "lookup": "exact"}},
            ).full_clean()
        self.assertIn("ends at a relation", str(cm.exception.message_dict["path_map"]))
        PolicyRule(
            policy=policy,
            content_type=self.device_ct,
            actions=["view"],
            constraint_template={"name__istartswith": "{{ prefix }}"},
            path_map={"prefix": {"path": "name", "lookup": "istartswith"}},
        ).full_clean()

    def test_parameter_kind_validation(self):
        with self.assertRaises(ValidationError):
            PolicyParameter(policy=self.policy, name="other", kind="object").full_clean()
        with self.assertRaises(ValidationError):
            PolicyParameter(
                policy=self.policy, name="other", kind="string", target_content_type=self.tenant_ct
            ).full_clean()
        with self.assertRaises(ValidationError):
            PolicyParameter(policy=self.policy, name="Bad Name", kind="string").full_clean()

    def test_render_as_object_permissions(self):
        rules = list(self.policy.rules.select_related("content_type"))
        # Without values the placeholders stay as written, one record per distinct constraint.
        records = render_as_object_permissions(rules, None, name="Tenant device viewer")
        self.assertEqual(
            [(r.name, [ct.model for ct in r.object_types], r.constraints) for r in records],
            [
                ("Tenant device viewer (1)", ["device"], [{"tenant__in": "{{ tenant }}"}]),
                ("Tenant device viewer (2)", ["interface"], [{"device__tenant__in": "{{ tenant }}"}]),
            ],
        )
        # Rules with identical actions and rendered constraints collapse into one record with several object types.
        pks = [str(tenant.pk) for tenant in self.tenants]
        rack_rule = PolicyRule(
            policy=self.policy,
            content_type=ContentType.objects.get_for_model(Rack),
            actions=["view"],
            constraint_template={"tenant__in": "{{ tenant }}"},
            path_map={"tenant": {"path": "tenant", "lookup": "in"}},
        )
        records = render_as_object_permissions([*rules, rack_rule], {"tenant": pks}, name="Assignment", enabled=False)
        self.assertEqual(len(records), 2)
        self.assertEqual([ct.model for ct in records[0].object_types], ["device", "rack"])
        self.assertEqual(records[0].constraints, [{"tenant__in": pks}])
        self.assertFalse(records[0].enabled)
        self.assertEqual(records[0].as_dict()["object_types"], ["dcim.device", "dcim.rack"])
        with self.assertRaises(PolicyRenderError):
            render_as_object_permissions(rules, {}, name="Assignment")

    def test_clone_params_reference_source_policy(self):
        self.assertEqual(self.policy.clone_fields, ["description"])
        self.assertEqual(self.policy.get_clone_extra_params(), {"clone_from": str(self.policy.pk)})

    def test_validate_constraints_for_model(self):
        validate_constraints_for_model(Device, {"tenant__name": "x"})
        validate_constraints_for_model(Device, [{"tenant__name": "x"}, {}])
        with self.assertRaisesRegex(ValidationError, "Invalid filter for dcim.Device"):
            validate_constraints_for_model(Device, {"bogus": "x"})
        with self.assertRaises(ValidationError):
            validate_constraints_for_model(Device, ["not a dict"])


seed_migration = importlib.import_module("nautobot.users.migrations.0015_permission_policy_seed_data")


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


class BuiltinPoliciesTest(TestCase):
    """The test database is flushed after migrations, so the seed function is run explicitly here."""

    @classmethod
    def setUpTestData(cls):
        seed_migration.create_builtin_policies(apps, None)

    def test_seed_does_not_overwrite_edited_policy(self):
        policy = PermissionPolicy.objects.get(name="nautobot-default-reference-data-viewer")
        policy.description = "Edited by an administrator"
        policy.validated_save()
        policy.rules.first().delete()
        rule_count = policy.rules.count()
        PermissionPolicy.objects.get(name="nautobot-default-export-job-runner").delete()

        seed_migration.create_builtin_policies(apps, None)

        policy.refresh_from_db()
        self.assertEqual(policy.description, "Edited by an administrator")
        self.assertEqual(policy.rules.count(), rule_count)
        # A deleted built-in policy is recreated (the deployment never had a customized copy), so a fresh
        # install and an upgraded install converge.
        self.assertTrue(PermissionPolicy.objects.filter(name="nautobot-default-export-job-runner").exists())


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
