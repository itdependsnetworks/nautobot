from django.contrib.contenttypes.models import ContentType

from nautobot.core.testing import TestCase
from nautobot.dcim.models import Device, Interface, Location
from nautobot.tenancy.models import Tenant
from nautobot.users.forms import (
    parameter_specs_from_policy,
    PolicyParameterForm,
    PolicyRuleForm,
    PolicyRuleFormSet,
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


class PolicyRuleFormTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.policy = create_tenant_policy()
        cls.specs = parameter_specs_from_policy(cls.policy)
        cls.device_ct = ContentType.objects.get_for_model(Device)
        cls.interface_ct = ContentType.objects.get_for_model(Interface)
        cls.location_ct = ContentType.objects.get_for_model(Location)

    def test_additional_actions_are_merged_once_and_path_map_is_derived(self):
        form = PolicyRuleForm(
            data={
                "policy": self.policy.pk,
                "content_type": self.location_ct.pk,
                "actions": ["view"],
                "additional_actions": ["run", "view"],
                "constraint_template": '{"tenant__in": "{{ tenant }}"}',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["actions"], ["view", "run"])
        self.assertEqual(form.instance.actions, ["view", "run"])
        self.assertEqual(form.instance.path_map, {"tenant": {"path": "tenant", "lookup": "in"}})
        # The parameters the editor offers come from the selected policy when none are passed in.
        self.assertEqual(form.fields["constraint_template"].parameter_names, ["tenant"])

    def test_actions_required(self):
        form = PolicyRuleForm(
            data={
                "policy": self.policy.pk,
                "content_type": self.location_ct.pk,
                "actions": [],
                "constraint_template": "{}",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("actions", form.errors)

    def test_model_errors_name_the_object_type(self):
        """A template that does not fit the object type is rejected with the model's message, on the form."""
        form = PolicyRuleForm(
            data={
                "policy": self.policy.pk,
                "content_type": self.interface_ct.pk,
                "actions": ["view"],
                "constraint_template": '{"tenant__in": "{{ tenant }}"}',  # Interface reaches Tenant via device
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("dcim.interface", str(form.errors))

    def test_editing_a_rule_splits_custom_actions(self):
        rule = self.policy.rules.get(content_type=self.device_ct)
        rule.actions = ["view", "run"]
        rule.save()
        form = PolicyRuleForm(instance=rule)
        self.assertEqual(form.initial["actions"], ["view"])
        self.assertEqual(form.initial["additional_actions"], ["run"])

    def test_formset_save_removes_rules_no_longer_listed(self):
        self.assertEqual(self.policy.rules.count(), 2)
        device_rule = self.policy.rules.get(content_type=self.device_ct)
        interface_rule = self.policy.rules.get(content_type=self.interface_ct)
        data = {
            "rules-TOTAL_FORMS": "2",
            "rules-INITIAL_FORMS": "2",
            "rules-MIN_NUM_FORMS": "0",
            "rules-MAX_NUM_FORMS": "1000",
            "rules-0-id": device_rule.pk,
            "rules-0-policy": self.policy.pk,
            "rules-0-content_type": self.device_ct.pk,
            "rules-0-actions": ["view", "change"],
            "rules-0-constraint_template": '{"tenant__in": "{{ tenant }}"}',
            "rules-1-id": interface_rule.pk,
            "rules-1-policy": self.policy.pk,
            "rules-1-content_type": self.interface_ct.pk,
            "rules-1-actions": ["view"],
            "rules-1-constraint_template": '{"device__tenant__in": "{{ tenant }}"}',
            "rules-1-DELETE": "on",
        }
        formset = PolicyRuleFormSet(
            data=data, instance=self.policy, prefix="rules", form_kwargs={"parameter_specs": self.specs}
        )
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertEqual(list(self.policy.rules.values_list("content_type", flat=True)), [self.device_ct.pk])
        self.assertEqual(self.policy.rules.get().actions, ["view", "change"])

    def test_formset_rejects_duplicate_object_types(self):
        data = {
            "rules-TOTAL_FORMS": "2",
            "rules-INITIAL_FORMS": "0",
            "rules-MIN_NUM_FORMS": "0",
            "rules-MAX_NUM_FORMS": "1000",
            "rules-0-content_type": self.location_ct.pk,
            "rules-0-actions": ["view"],
            "rules-0-constraint_template": "{}",
            "rules-1-content_type": self.location_ct.pk,
            "rules-1-actions": ["view"],
            "rules-1-constraint_template": "{}",
        }
        formset = PolicyRuleFormSet(
            data=data, instance=self.policy, prefix="rules", form_kwargs={"parameter_specs": self.specs}
        )
        self.assertFalse(formset.is_valid())
        self.assertIn("more than one rule", str(formset.non_form_errors()))
