from django.contrib.contenttypes.models import ContentType

from nautobot.core.testing import TestCase
from nautobot.tenancy.models import Tenant
from nautobot.users.forms import (
    PolicyParameterForm,
)
from nautobot.users.tests.test_policies import create_tenant_policy


class PolicyParameterFormTest(TestCase):
    def test_object_parameter_requires_target(self):
        policy = create_tenant_policy()
        form = PolicyParameterForm(data={"policy": policy.pk, "name": "region", "kind": "object", "multiple": True})
        self.assertFalse(form.is_valid())
        self.assertIn("target object type", str(form.errors["target_content_type"]))
        # The message comes from the model's clean(), once, not once from the form and once from the model.
        self.assertEqual(len(form.errors["target_content_type"]), 1)

    def test_string_parameter_drops_target(self):
        policy = create_tenant_policy()
        tenant_ct = ContentType.objects.get_for_model(Tenant)
        form = PolicyParameterForm(
            data={"policy": policy.pk, "name": "prefix", "kind": "string", "target_content_type": tenant_ct.pk}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["target_content_type"])

    def test_inputs_carry_accessible_names(self):
        form = PolicyParameterForm()
        for name, field in form.fields.items():
            self.assertEqual(field.widget.attrs.get("aria-label"), field.label, name)
