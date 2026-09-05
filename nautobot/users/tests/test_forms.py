from nautobot.core.testing import TestCase
from nautobot.users.forms import (
    PolicyParameterForm,
)


class PolicyParameterFormTest(TestCase):
    def test_inputs_carry_accessible_names(self):
        form = PolicyParameterForm()
        for name, field in form.fields.items():
            self.assertEqual(field.widget.attrs.get("aria-label"), field.label, name)
