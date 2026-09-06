"""Tests for `nautobot.core.ui.object_form`: declarative form layout via `Meta.fieldsets`."""

from nautobot.core.testing import TestCase
from nautobot.core.ui.object_form import (
    FormPanel,
)


class FormLayoutResolutionTestCase(TestCase):
    """Resolution of `Meta.fieldsets` into a `FormLayout`."""

    def test_component_declaration_validation(self):
        with self.assertRaises(TypeError):
            FormPanel("x", deferred_render=True)
        with self.assertRaises(TypeError):
            FormPanel("x", attrs="id=x")
        with self.assertRaises(TypeError):
            FormPanel("x", items="name")
