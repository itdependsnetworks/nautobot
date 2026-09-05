"""Tests for permission policies: placeholder substitution, rendering, the derivation hook, and the path resolver."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.management import call_command

from nautobot.core.testing import TestCase
from nautobot.dcim.models import Device, Interface
from nautobot.tenancy.models import Tenant
from nautobot.users.models import PermissionPolicy, PolicyParameter

User = get_user_model()


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
