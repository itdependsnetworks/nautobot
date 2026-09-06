"""Tests for `nautobot.core.ui.object_form`: declarative form layout via `Meta.fieldsets`."""

import json
import re
from types import SimpleNamespace

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.template import Context, engines
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from nautobot.circuits.forms import ProviderNetworkForm
from nautobot.core.testing import TestCase
from nautobot.core.ui.object_form import (
    AllOf,
    AnyOf,
    Condition,
    Contributed,
    ContributedFieldsPanel,
    evaluate_render_if,
    FieldGroup,
    FormField,
    FormLayout,
    FormPanel,
    IncludedTemplate,
    InlineFields,
    Not,
    Omitted,
    resolve_dotted_path,
    StaticField,
    TabbedGroups,
    When,
)
from nautobot.dcim.forms import ManufacturerForm, SoftwareImagePanel, SoftwareVersionForm
from nautobot.dcim.models import Device, Manufacturer, Platform
from nautobot.extras.choices import CustomFieldTypeChoices, RelationshipTypeChoices
from nautobot.extras.forms import NautobotModelForm
from nautobot.extras.models import CustomField, Relationship


def normalize_html(html):
    """Collapse whitespace so that structurally identical markup compares equal."""
    html = re.sub(r"\s+", " ", str(html))
    html = re.sub(r">\s+<", "><", html)
    return html.strip()


def render_string(template_string, context, request):
    """Render a template string with the full set of context processors (so `perms` etc. are available)."""
    return engines["django"].from_string(template_string).render(context, request=request)


class ManufacturerLayoutForm(NautobotModelForm):
    """Baseline form for layout tests: two model fields, one extra visible field, one hidden field."""

    extra = forms.CharField(required=False)
    secret = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Manufacturer
        fields = ["name", "description"]


def form_class_with_fieldsets(fieldsets, base=ManufacturerLayoutForm, **attrs):
    """Build a subclass of `base` whose `Meta.fieldsets` is `fieldsets`."""
    meta = type("Meta", (base.Meta,), {"fieldsets": fieldsets})
    return type("LayoutTestForm", (base,), {"Meta": meta, **attrs})


class ConditionTestCase(SimpleTestCase):
    """`visible_if` condition objects: evaluation, validation, and JSON round trip. Pure Python; no database."""

    def test_edge_values(self):
        # `eq=None` means "empty", however the browser spells it
        self.assertTrue(When("x", eq=None).matches({"x": ""}))
        self.assertTrue(When("x", eq=None).matches({"x": "null"}))
        self.assertFalse(When("x", eq=None).matches({"x": "a"}))
        # Submitted values are strings; compare as strings
        self.assertTrue(When("n", eq=0).matches({"n": "0"}))
        self.assertFalse(When("n", eq=0).matches({"n": ""}))
        # A multi-valued field matches `in_` if any value matches, and counts as set only with a real value
        self.assertTrue(When("t", in_=["a"]).matches({"t": ["b", "a"]}))
        self.assertFalse(When("m", is_set=True).matches({"m": ["", "null"]}))
        with self.assertRaises(TypeError):
            AnyOf("x")
        with self.assertRaises(TypeError):
            Not("x")

    def test_when_eq(self):
        condition = When("mode", eq="tagged")
        self.assertTrue(condition.matches({"mode": "tagged"}))
        self.assertFalse(condition.matches({"mode": "access"}))
        self.assertFalse(condition.matches({"mode": ""}))
        self.assertFalse(condition.matches({}))
        # Multi-valued fields match if any value matches
        self.assertTrue(condition.matches({"mode": ["access", "tagged"]}))

    def test_when_eq_boolean(self):
        condition = When("enabled", eq=True)
        self.assertTrue(condition.matches({"enabled": True}))
        self.assertTrue(condition.matches({"enabled": "on"}))
        self.assertFalse(condition.matches({"enabled": False}))
        self.assertFalse(condition.matches({"enabled": "false"}))
        self.assertFalse(condition.matches({}))
        self.assertTrue(When("enabled", eq=False).matches({}))

    def test_when_in(self):
        condition = When("type", in_=["select", "multi-select"])
        self.assertTrue(condition.matches({"type": "select"}))
        self.assertTrue(condition.matches({"type": "multi-select"}))
        self.assertFalse(condition.matches({"type": "text"}))
        self.assertFalse(condition.matches({"type": None}))

    def test_when_is_set(self):
        self.assertTrue(When("mode", is_set=True).matches({"mode": "access"}))
        self.assertFalse(When("mode", is_set=True).matches({"mode": ""}))
        self.assertFalse(When("mode", is_set=True).matches({"mode": None}))
        self.assertFalse(When("mode", is_set=True).matches({"mode": "null"}))  # Select2's "nothing selected"
        self.assertFalse(When("mode", is_set=True).matches({"mode": []}))
        self.assertTrue(When("mode", is_set=False).matches({"mode": ""}))
        self.assertTrue(When("mode", is_set=False).matches({}))

    def test_when_validation(self):
        with self.assertRaises(TypeError):
            When("mode")
        with self.assertRaises(TypeError):
            When("mode", eq="a", is_set=True)
        with self.assertRaises(TypeError):
            When("mode", in_="not-a-list")

    def test_combinators(self):
        a = When("a", eq="1")
        b = When("b", eq="2")
        self.assertTrue(AnyOf(a, b).matches({"a": "1"}))
        self.assertFalse(AnyOf(a, b).matches({"a": "x"}))
        self.assertTrue(AllOf(a, b).matches({"a": "1", "b": "2"}))
        self.assertFalse(AllOf(a, b).matches({"a": "1"}))
        self.assertTrue(Not(a).matches({"a": "x"}))
        self.assertFalse(Not(a).matches({"a": "1"}))
        self.assertEqual(AllOf(a, Not(b)).field_names(), {"a", "b"})
        with self.assertRaises(TypeError):
            AnyOf()
        with self.assertRaises(TypeError):
            Not("a")

    def test_json_round_trip(self):
        conditions = [
            When("mode", eq="tagged"),
            When("enabled", eq=True),
            When("type", in_=["select", "multi-select"]),
            When("mode", is_set=True),
            When("mode", is_set=False),
            AnyOf(When("a", eq="1"), AllOf(When("b", is_set=True), Not(When("c", in_=["x"])))),
        ]
        for condition in conditions:
            with self.subTest(condition=condition):
                restored = Condition.from_dict(json.loads(condition.to_json()))
                self.assertEqual(restored, condition)
                # Both evaluate identically against a few data sets
                for data in ({}, {"mode": "tagged", "enabled": "on", "type": "select", "a": "1", "b": "x"}):
                    self.assertEqual(restored.matches(data), condition.matches(data))


class RenderIfTestCase(SimpleTestCase):
    """`render_if`: server-side gating by dotted path or callable. Pure Python; no database."""

    def test_resolve_dotted_path_guards(self):
        class Target:
            attr = "value"
            items = ["zero", "one"]
            mapping = {"key": "mapped"}

            def method(self):
                return "called"

            def dangerous(self):
                return "never"

            dangerous.alters_data = True

            def untouchable(self):
                return "never"

            untouchable.do_not_call_in_templates = True

        context = Context({"obj": Target()})
        self.assertEqual(resolve_dotted_path("obj.attr", context), "value")
        self.assertEqual(resolve_dotted_path("obj.items.1", context), "one")
        self.assertEqual(resolve_dotted_path("obj.mapping.key", context), "mapped")
        self.assertEqual(resolve_dotted_path("obj.method", context), "called")
        self.assertIsNone(resolve_dotted_path("obj.dangerous", context))
        self.assertTrue(callable(resolve_dotted_path("obj.untouchable", context)))
        self.assertIsNone(resolve_dotted_path("obj.items.9", context))
        self.assertIsNone(resolve_dotted_path("obj.missing.deeper", context))

    def test_evaluate(self):
        context = Context({"editing": True, "obj": SimpleNamespace(parent_bay=None, name="x")})
        self.assertTrue(evaluate_render_if(None, context))
        self.assertTrue(evaluate_render_if("editing", context))
        self.assertFalse(evaluate_render_if("not editing", context))
        self.assertFalse(evaluate_render_if("obj.parent_bay", context))
        self.assertTrue(evaluate_render_if("not obj.parent_bay", context))
        self.assertTrue(evaluate_render_if("obj.name", context))
        # Missing variables are simply falsy
        self.assertFalse(evaluate_render_if("does.not.exist", context))
        self.assertTrue(evaluate_render_if("not does.not.exist", context))
        self.assertTrue(evaluate_render_if(lambda ctx: ctx["editing"], context))
        with self.assertRaises(TypeError):
            evaluate_render_if(42, context)

    def test_component_validation(self):
        with self.assertRaises(TypeError):
            FormPanel("x", render_if=42)


class FormLayoutResolutionTestCase(TestCase):
    """Resolution of `Meta.fieldsets` into a `FormLayout`."""

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get("/")
        self.request.user = self.user

    def context(self, **extra):
        return Context({"request": self.request, "obj_type": "manufacturer", **extra})

    def panel_labels(self, layout, context=None):
        """Labels of the panels that would actually render, in order."""
        context = context or self.context()
        return [panel.get_label(context) for panel in layout.panels if panel.has_content]

    def test_no_fieldsets_uses_single_trailing_panel(self):
        form = ManufacturerLayoutForm()
        self.assertFalse(form.has_declared_layout)
        layout = form.layout
        self.assertFalse(layout.has_declared_panels)
        # With nothing declared, the trailing panel is the main card and leads
        trailing = layout.panels[0]
        self.assertEqual(trailing.weight, 0)
        self.assertEqual(trailing.field_names, ("name", "description", "extra"))
        # Label falls back to the object type in context, as the generic create/edit template does
        self.assertEqual(trailing.get_label(self.context()), "Manufacturer")
        self.assertEqual(trailing.get_label(Context({})), "Manufacturer")  # then the model verbose_name
        layout.default_label = "job data"
        self.assertEqual(trailing.get_label(self.context()), "Job data")

    def test_tuple_sugar_and_trailing_other(self):
        form = form_class_with_fieldsets((("Main", ("name", "description")),))()
        self.assertTrue(form.has_declared_layout)
        layout = form.layout
        self.assertTrue(layout.has_declared_panels)
        self.assertIsInstance(layout.panels[0], FormPanel)
        self.assertEqual(layout.panels[0].label, "Main")
        self.assertEqual(layout.panels[0].weight, 100)
        self.assertEqual(layout.panels[0].field_names, ("name", "description"))
        self.assertIsInstance(layout.panels[0]._bound_items[0], FormField)
        trailing = layout.panels[-1]
        self.assertEqual(trailing.weight, FormPanel.WEIGHT_TRAILING_PANEL)
        self.assertEqual(trailing.field_names, ("extra",))
        self.assertEqual(trailing.get_label(self.context()), "Other")

    def test_floor_plan_tabs_sugar(self):
        fieldsets = (("Axes", {"tabs": (("X", ("name",)), ("Y", ("description",)))}),)
        layout = form_class_with_fieldsets(fieldsets)().layout
        panel = layout.panels[0]
        self.assertEqual(panel.label, "Axes")
        self.assertIsInstance(panel._bound_items[0], TabbedGroups)
        self.assertEqual(panel.field_names, ("name", "description"))
        with self.assertRaises(TypeError):
            form_class_with_fieldsets((("Axes", {"columns": ()}),))().layout  # pylint: disable=expression-not-assigned

    def test_implicit_and_explicit_weights(self):
        fieldsets = (
            ("First", ("name",)),
            FormPanel("Heavy", ("description",), weight=50),
            ("Third", ("extra",)),
        )
        layout = form_class_with_fieldsets(fieldsets)().layout
        weights = {panel.label: panel.weight for panel in layout.panels if panel.label in ("First", "Heavy", "Third")}
        self.assertEqual(weights, {"First": 100, "Heavy": 50, "Third": 300})
        labels = self.panel_labels(layout)
        self.assertLess(labels.index("Heavy"), labels.index("First"))
        self.assertLess(labels.index("First"), labels.index("Third"))

    def test_contributed_pin(self):
        """`Contributed(name)` at the top level moves a mixin panel into that slot."""
        fieldsets = (("Main", ("name",)), Contributed("notes"), ("More", ("description",)))
        layout = form_class_with_fieldsets(fieldsets)().layout
        notes = layout.contributed_panels["notes"]
        self.assertEqual(notes.weight, 200)
        self.assertEqual(notes.field_names, ("object_note",))
        labels = self.panel_labels(layout)
        self.assertEqual(labels[:3], ["Main", "Notes", "More"])

    def test_contributed_splice(self):
        """`Contributed(name)` inside a panel splices the fields in; the contributed panel then has nothing left."""
        fieldsets = (("Main", ("name", Contributed("notes"), "description")),)
        layout = form_class_with_fieldsets(fieldsets)().layout
        self.assertEqual(layout.panels[0].field_names, ("name", "object_note", "description"))
        self.assertFalse(layout.contributed_panels["notes"].has_content)

    def test_explicit_claim_beats_contributed_panel(self):
        fieldsets = (("Main", ("name", "object_note")),)
        layout = form_class_with_fieldsets(fieldsets)().layout
        self.assertFalse(layout.contributed_panels["notes"].has_content)

    def test_duplicate_and_unknown_names_raise(self):
        with self.assertRaisesRegex(ValueError, "more than once"):
            form_class_with_fieldsets((("A", ("name",)), ("B", ("name",))))().layout  # pylint: disable=expression-not-assigned
        with self.assertRaisesRegex(ValueError, "unknown field 'nope'"):
            form_class_with_fieldsets((("A", ("nope",)),))().layout  # pylint: disable=expression-not-assigned
        with self.assertRaisesRegex(ValueError, "unknown contributed panel 'nope'"):
            form_class_with_fieldsets((("A", ("name",)), Contributed("nope")))().layout  # pylint: disable=expression-not-assigned
        with self.assertRaisesRegex(ValueError, "unknown contributed panel 'nope'"):
            form_class_with_fieldsets((("A", ("name", Contributed("nope"))),))().layout  # pylint: disable=expression-not-assigned

    def test_component_declaration_validation(self):
        with self.assertRaises(TypeError):
            FormPanel("x", deferred_render=True)
        with self.assertRaises(TypeError):
            FormPanel("x", attrs="id=x")
        with self.assertRaises(TypeError):
            FormPanel("x", items="name")

    def test_omitted(self):
        """`Omitted` claims a field so that it neither renders nor lands in the trailing panel."""
        form = form_class_with_fieldsets((("Main", ("name", Omitted("description"))),))()
        layout = form.layout
        self.assertTrue(layout.is_claimed("description"))
        self.assertIsNone(layout.claimed_component("description"))
        for panel in layout.panels:
            self.assertNotIn("description", panel.field_names)
        self.assertEqual(layout.panels[-1].field_names, ("extra",))
        self.assertNotIn('name="description"', layout.render(self.context()))
        # The form still receives the field, empty, exactly as when a template left it out
        bound = form_class_with_fieldsets((("Main", ("name", Omitted("description"))),))(data={"name": "Vendor"})
        self.assertTrue(bound.is_valid(), bound.errors)
        self.assertEqual(bound.cleaned_data["description"], "")
        with self.assertRaisesRegex(ValueError, "more than once"):
            form_class_with_fieldsets((("Main", ("description", Omitted("description"))),))().layout  # pylint: disable=expression-not-assigned
        with self.assertRaisesRegex(ValueError, "unknown field 'nope'"):
            form_class_with_fieldsets((("Main", (Omitted("nope"),)),))().layout  # pylint: disable=expression-not-assigned
        with self.assertRaises(TypeError):
            Omitted()

    def test_invalid_shapes_raise(self):
        with self.assertRaises(TypeError):
            form_class_with_fieldsets(
                ("name",)
            )().layout  # bare string at top level  # pylint: disable=expression-not-assigned
        with self.assertRaises(TypeError):
            form_class_with_fieldsets((("A", (("Nested", ("name",)),)),))().layout  # pylint: disable=expression-not-assigned
        with self.assertRaises(TypeError):
            form_class_with_fieldsets((("A", (FormPanel("Inner", ("name",)),)),))().layout  # pylint: disable=expression-not-assigned
        with self.assertRaises(TypeError):
            form_class_with_fieldsets("name,description")().layout  # pylint: disable=expression-not-assigned

    def test_resolution_is_lazy_and_sees_post_init_field_removal(self):
        """A subclass that pops a field after `super().__init__()` must not be broken by a stale claim."""

        class PopsExtra(form_class_with_fieldsets((("Main", ("name", "description")),))):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields.pop("extra")

        layout = PopsExtra().layout
        self.assertNotIn("extra", layout.panels[-1].field_names)
        self.assertFalse(layout.panels[-1].has_content)

    def test_hidden_fields_are_not_claimed_by_panels(self):
        layout = form_class_with_fieldsets((("Main", ("name", "description", "extra")),))().layout
        for panel in layout.panels:
            self.assertNotIn("secret", panel.field_names)
        html = layout.render(self.context())
        self.assertEqual(html.count('name="secret"'), 1)
        self.assertLess(html.index('name="secret"'), html.index('class="card"'))

    def test_runtime_injected_custom_fields_and_relationships(self):
        manufacturer_ct = ContentType.objects.get_for_model(Manufacturer)
        custom_field = CustomField.objects.create(
            label="Layout Test", key="layout_test", type=CustomFieldTypeChoices.TYPE_TEXT
        )
        custom_field.content_types.set([manufacturer_ct])
        Relationship.objects.create(
            label="Manufacturer Platforms",
            key="mfr_platforms",
            type=RelationshipTypeChoices.TYPE_ONE_TO_MANY,
            source_type=manufacturer_ct,
            destination_type=ContentType.objects.get_for_model(Platform),
        )

        # Not named anywhere: the mixin-contributed panels pick them up
        layout = form_class_with_fieldsets((("Main", ("name",)),))().layout
        self.assertEqual(layout.contributed_panels["custom_fields"].field_names, ("cf_layout_test",))
        self.assertEqual(layout.contributed_panels["relationships"].field_names, ("cr_mfr_platforms__destination",))
        self.assertNotIn("cf_layout_test", layout.panels[-1].field_names)

        # Spliced into an explicit panel
        layout = form_class_with_fieldsets((("Main", ("name", Contributed("custom_fields"))),))().layout
        self.assertEqual(layout.panels[0].field_names, ("name", "cf_layout_test"))
        self.assertFalse(layout.contributed_panels["custom_fields"].has_content)

        # Named explicitly by its runtime name
        layout = form_class_with_fieldsets((("Main", ("name", "cf_layout_test")),))().layout
        self.assertEqual(layout.panels[0].field_names, ("name", "cf_layout_test"))

    def test_media_aggregation(self):
        class ScriptedPanel(FormPanel):
            class Media:
                js = ["test/form_layout_panel.js"]

        form = form_class_with_fieldsets((ScriptedPanel("Main", ("name",)),))()
        self.assertIn("test/form_layout_panel.js", str(form.media))
        # Widget media is still present alongside component media
        self.assertIn("test/form_layout_panel.js", str(form.layout.media))
        self.assertNotIn("test/form_layout_panel.js", str(ManufacturerLayoutForm().media))


class FormLayoutRenderTestCase(TestCase):
    """Rendering of resolved layouts."""

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get("/")
        self.request.user = self.user

    def context(self, **extra):
        return Context({"request": self.request, "obj_type": "manufacturer", **extra})

    def test_render_panels_and_fields(self):
        form = form_class_with_fieldsets((("Main", ("name", "description")),))()
        html = form.layout.render(self.context())
        self.assertIn("<strong>Main</strong>", html)
        self.assertIn("<strong>Other</strong>", html)
        self.assertIn('id="id_name"', html)
        self.assertIn('id="id_extra"', html)
        self.assertLess(html.index("<strong>Main</strong>"), html.index("<strong>Other</strong>"))

    def test_empty_panels_are_not_rendered(self):
        form = form_class_with_fieldsets((("Main", ("name", "description", "extra")),))()
        html = form.layout.render(self.context())
        self.assertNotIn("<strong>Other</strong>", html)
        self.assertNotIn("<strong>Custom Fields</strong>", html)

    def test_render_if_on_field_and_panel(self):
        fieldsets = (
            ("Main", (FormField("name", render_if="editing"), FormField("description", render_if="not editing"))),
            FormPanel("Gated", ("extra",), render_if="obj.parent_bay"),
        )
        form = form_class_with_fieldsets(fieldsets)()
        html = form.layout.render(self.context(editing=True, obj=SimpleNamespace(parent_bay=None)))
        self.assertIn('id="id_name"', html)
        self.assertNotIn('id="id_description"', html)
        self.assertNotIn("<strong>Gated</strong>", html)
        html = form.layout.render(self.context(editing=False, obj=SimpleNamespace(parent_bay="bay")))
        self.assertNotIn('id="id_name"', html)
        self.assertIn('id="id_description"', html)
        self.assertIn("<strong>Gated</strong>", html)

    def test_required_permissions_gate_contributed_panels(self):
        form = form_class_with_fieldsets((("Main", ("name", "description", "extra")),))()
        html = form.layout.render(self.context())
        self.assertNotIn("<strong>Notes</strong>", html)
        self.add_permissions("extras.add_note")
        # Permissions are cached on the user instance; use a fresh one
        self.request.user = type(self.user).objects.get(pk=self.user.pk)
        html = form.layout.render(self.context())
        self.assertIn("<strong>Notes</strong>", html)
        self.assertIn('id="id_object_note"', html)

    def test_visible_if_serializes_to_wrapper(self):
        fieldsets = (
            (
                "Main",
                (
                    "name",
                    FormField("description", visible_if=When("name", is_set=True), clear_on_hide=True),
                ),
            ),
            FormPanel("Extras", ("extra",), visible_if=AnyOf(When("name", eq="a"), When("name", eq="b"))),
        )
        form = form_class_with_fieldsets(fieldsets)()
        html = form.layout.render(self.context())
        self.assertIn('data-nb-visible-if="{&quot;field&quot;:&quot;name&quot;,&quot;is_set&quot;:true}"', html)
        self.assertIn('data-nb-clear-on-hide="true"', html)
        self.assertIn("&quot;any&quot;", html)
        # Conditions that are false for the form's current values render hidden from the start
        self.assertEqual(html.count(" hidden>"), 2)
        html = form_class_with_fieldsets(fieldsets)(initial={"name": "a"}).layout.render(self.context())
        self.assertNotIn(" hidden>", html)
        html = form_class_with_fieldsets(fieldsets)(data={"name": "c"}).layout.render(self.context())
        self.assertEqual(html.count(" hidden>"), 1)  # `description` shows for any name; "Extras" only for a or b

    def test_field_label_help_text_and_full_width(self):
        fieldsets = (
            (
                "Main",
                (
                    FormField("name", label="Vendor", help_text="Who makes it"),
                    FormField("description", full_width=True),
                ),
            ),
        )
        form = form_class_with_fieldsets(fieldsets)()
        html = form.layout.render(self.context())
        self.assertIn(">Vendor<", html.replace("\n", "").replace("  ", ""))
        self.assertIn("Who makes it", html)
        # full_width puts the label above the control (`form-label`) instead of beside it (`col-form-label`)
        self.assertIn('class="form-label" for="id_description"', html)
        self.assertIn('class="col-md-3 col-form-label nb-required" for="id_name"', html)
        self.assertEqual(form["name"].label, "Vendor")

    def test_field_row_template_container_class_and_attrs(self):
        fieldsets = (
            (
                "Main",
                (
                    FormField("name", template_path="components/form/static_field.html", attrs={"id": "row-name"}),
                    FormField("description", container_class="nb-wide"),
                ),
            ),
        )
        html = form_class_with_fieldsets(fieldsets)().layout.render(self.context())
        # The row template replaces the standard row and the component attrs wrap it
        self.assertIn('<div id="row-name">', html)
        self.assertIn("form-control-plaintext", html)
        self.assertNotIn('for="id_name"', html)
        self.assertIn("justify-content-center nb-wide", html)

    def test_field_as_hidden(self):
        fieldsets = (("Main", ("name", FormField("description", as_hidden=True))),)
        html = form_class_with_fieldsets(fieldsets)().layout.render(self.context())
        self.assertIn('type="hidden" name="description"', html)
        self.assertEqual(html.count('name="description"'), 1)
        self.assertNotIn('for="id_description"', html)

    def test_static_field(self):
        fieldsets = (
            (
                "Main",
                (
                    "name",
                    StaticField("Parent bay", attribute="parent_bay.name"),
                    StaticField("Literal", value="a-literal-value-42"),
                    StaticField("Linked", attribute="platform"),
                    StaticField("Absent", attribute="parent_bay.device", render_if="obj.parent_bay.device"),
                    # Not on the object: falls back to the form field of the same name (a create page's `initial`)
                    StaticField("From form", attribute="description"),
                ),
            ),
        )
        form = form_class_with_fieldsets(fieldsets)(initial={"description": "from-initial"})
        platform = Platform.objects.first()
        obj = SimpleNamespace(parent_bay=SimpleNamespace(name="Bay 1", device=None), platform=platform, description="")
        html = form.layout.render(self.context(obj=obj))
        for label in ("Parent bay", "Literal", "Linked", "From form"):
            self.assertIn(f'col-form-label">{label}</span>', html)
        self.assertIn("Bay 1", html)
        self.assertIn("a-literal-value-42", html)
        self.assertIn(platform.get_absolute_url(), html)
        self.assertIn("from-initial", html)
        self.assertNotIn("Absent", html)

    def test_inline_fields(self):
        with self.assertRaises(ValueError):
            InlineFields("name", "description", widths=(5,))
        with self.assertRaises(ValueError):
            InlineFields("name", "description", widths=(6, 6))
        fieldsets = (("Main", (InlineFields("name", "description", label="Identity", widths=(6, 3)),)),)
        form = form_class_with_fieldsets(fieldsets)()
        self.assertEqual(form.layout.panels[0].field_names, ("name", "description"))
        html = form.layout.render(self.context())
        self.assertIn("Identity", html)
        self.assertIn('class="col-md-6"', html)
        self.assertIn('class="col-md-3"', html)
        self.assertIn('id="id_name"', html)
        self.assertIn('id="id_description"', html)
        # Defaults: the first field's label, an even split of the nine columns, help text beneath
        fieldsets = (("Main", (InlineFields("name", "description", help_text="Two <em>inline</em>"),)),)
        form = form_class_with_fieldsets(fieldsets)(data={"description": "x" * 300})
        html = form.layout.render(self.context())
        self.assertIn(">Name</label>", html)
        self.assertEqual(html.count('class="col-md-4"'), 2)
        self.assertIn("Two <em>inline</em>", html)
        self.assertIn("has-error", html)  # errors of every inline field are aggregated on the row

    def test_tabbed_groups(self):
        with self.assertRaises(TypeError):
            TabbedGroups(FieldGroup("Only", ("name",)))
        fieldsets = (
            ("Main", (TabbedGroups(("By name", ("name",)), FieldGroup("By description", ("description",))), "extra")),
        )
        form_class = form_class_with_fieldsets(fieldsets)
        html = form_class().layout.render(self.context())
        self.assertIn('class="nav nav-tabs"', html)
        self.assertIn(">By name<", html)
        self.assertIn(">By description<", html)
        self.assertIn('id="id_extra"', html)
        # First tab is active by default...
        self.assertRegex(html, r'nav-link active"\s+id="[^"]*-0-tab"')
        self.assertIn('aria-selected="true"', html)
        # ...but a tab whose field carries a value wins
        html = form_class(initial={"description": "something"}).layout.render(self.context())
        self.assertRegex(html, r'nav-link active"\s+id="[^"]*-1-tab"')

    def test_panel_markup_options(self):
        fieldsets = (
            FormPanel("Styled", ("name",), css_class="warning", attrs={"class": "extra-x", "id": "p1"}),
            FormPanel(None, ("description",)),
            FormPanel("Gone", (FormField("extra", render_if="editing"),)),
        )
        html = form_class_with_fieldsets(fieldsets)().layout.render(self.context(editing=False))
        # A caller-supplied class is folded into the card's classes rather than repeating the attribute
        self.assertIn('class="card border-warning extra-x" id="p1"', html)
        self.assertIn('class="card-header bg-warning-subtle border-warning"', html)
        self.assertEqual(html.count("<strong>Styled</strong>"), 1)
        self.assertNotIn("<strong>None</strong>", html)  # the unlabelled panel has no header
        # A panel whose every item is gated off renders no card at all
        self.assertNotIn("Gone", html)
        self.assertNotIn('id="id_extra"', html)

    def test_included_template(self):
        fieldsets = (("Main", ("name", IncludedTemplate("components/form/static_field.html", render_if="editing"))),)
        form = form_class_with_fieldsets(fieldsets)()
        self.assertIn("form-control-plaintext", form.layout.render(self.context(editing=True)))
        self.assertNotIn("form-control-plaintext", form.layout.render(self.context(editing=False)))
        # It claims nothing: the other fields are untouched and still land in the trailing panel
        included = form.layout.panels[0]._bound_items[1]
        self.assertIsInstance(included, IncludedTemplate)
        self.assertEqual(included.field_names, ())
        self.assertEqual(form.layout.panels[-1].field_names, ("description", "extra"))

    def test_software_image_panel_inserts_image_list(self):
        panel = SoftwareImagePanel("Software", ("platform", "software_version", "software_image_files"))
        kinds = [item if isinstance(item, str) else type(item).__name__ for item in panel.items]
        self.assertEqual(kinds, ["platform", "software_version", "IncludedTemplate", "software_image_files"])
        self.assertEqual(panel.items[2].template_path, SoftwareImagePanel.image_list_template_path)
        # Declaring it explicitly does not duplicate it
        explicit = SoftwareImagePanel(
            "Software",
            ("software_version", IncludedTemplate(SoftwareImagePanel.image_list_template_path)),
        )
        self.assertEqual(len(explicit.items), 2)
        # Without a software_version item there is nothing to attach to
        self.assertEqual(SoftwareImagePanel("Software", ("platform",)).items, ("platform",))
        self.assertIn("js/software_image_picker.js", str(panel.media))

    def test_render_form_layout_tag_matches_legacy_generic_template(self):
        """
        For a form with no `Meta.fieldsets` (and no tenancy mixin), `{% render_form_layout %}` must produce the
        same markup as the generic create/edit template and its `extras_features_edit_form_fields` include did.
        """
        self.user.is_superuser = True
        self.user.save()
        legacy = """{% load form_helpers %}
<div class="card">
    <div class="card-header"><strong>{{ obj_type|capfirst }}</strong></div>
    <div class="card-body">
        {% render_form form %}
    </div>
</div>
{% if form.custom_fields %}
    <div class="card"><div class="card-header"><strong>Custom Fields</strong></div><div class="card-body">{% render_custom_fields form %}</div></div>
{% endif %}
{% if form.relationships %}
    <div class="card"><div class="card-header"><strong>Relationships</strong></div><div class="card-body">{% render_relationships form %}</div></div>
{% endif %}
{% if form.object_note and perms.extras.add_note %}
    <div class="card"><div class="card-header"><strong>Notes</strong></div><div class="card-body">{% render_field form.object_note %}</div></div>
{% endif %}
{% if form.dynamic_groups and perms.extras.add_staticgroupassociation %}
    <div class="card"><div class="card-header"><strong>Static Assignment to Dynamic Groups</strong></div><div class="card-body">{% render_field form.dynamic_groups %}</div></div>
{% endif %}
{% if form.tags %}
    <div class="card"><div class="card-header"><strong>Tags</strong></div><div class="card-body">{% render_field form.tags %}</div></div>
{% endif %}
"""
        new = "{% load form_helpers %}{% render_form_layout form %}"
        # Both forms declare no fieldsets and are free of hidden fields; the legacy path emitted hidden fields inside
        # the card, the layout emits them ahead of all panels (resolution rule 5), which is the one intentional
        # difference. SoftwareVersionForm brings a `tags` field, exercising the contributed Tags panel.
        for form in (SoftwareVersionForm(), ManufacturerForm()):
            self.assertFalse(form.has_declared_layout)
            with self.subTest(form=type(form).__name__):
                context = {"form": form, "obj_type": form._meta.model._meta.verbose_name}
                expected = normalize_html(render_string(legacy, context, self.request))
                actual = normalize_html(render_string(new, context, self.request))
                self.assertEqual(actual, expected)

    def test_render_form_layout_tag_default_label(self):
        html = render_string(
            '{% load form_helpers %}{% render_form_layout form "job data" %}',
            {"form": ManufacturerLayoutForm()},
            self.request,
        )
        self.assertIn("<strong>Job data</strong>", html)

    def test_deprecated_include_renders_contributed_panels(self):
        self.user.is_superuser = True
        self.user.save()
        template = "{% include 'inc/extras_features_edit_form_fields.html' %}"
        html = render_string(template, {"form": ManufacturerLayoutForm()}, self.request)
        self.assertIn("<strong>Notes</strong>", html)
        self.assertNotIn("<strong>Manufacturer</strong>", html)

        class PlainForm(forms.Form):
            name = forms.CharField()

        html = render_string(template, {"form": PlainForm()}, self.request)
        self.assertEqual(normalize_html(html), "")


class ProviderNetworkFieldsetsTestCase(TestCase):
    """`ProviderNetworkForm` has declared `Meta.fieldsets` since 1.x; it now takes effect."""

    def test_layout(self):
        form = ProviderNetworkForm()
        self.assertTrue(form.has_declared_layout)
        panel = form.layout.panels[0]
        self.assertEqual(panel.label, "Provider Network")
        self.assertEqual(panel.field_names, ("provider", "name", "description", "comments", "tags"))
        # `tags` is claimed explicitly, so the contributed Tags panel has nothing to render
        self.assertFalse(form.layout.contributed_panels["tags"].has_content)

    def test_add_view_renders_layout(self):
        self.user.is_superuser = True
        self.user.save()
        response = self.client.get(reverse("circuits:providernetwork_add"))
        self.assertHttpStatus(response, 200)
        content = response.content.decode(response.charset)
        self.assertIn("<strong>Provider Network</strong>", content)
        self.assertIn('id="id_tags"', content)
        self.assertNotIn("<strong>Tags</strong>", content)
        self.assertIn("<strong>Notes</strong>", content)


class ContributedFieldsPanelTestCase(TestCase):
    def test_declaration_validation(self):
        with self.assertRaises(TypeError):
            ContributedFieldsPanel(name="", label="x", fields=("a",), weight=1)
        with self.assertRaises(TypeError):
            ContributedFieldsPanel(name="x", label="x", fields="a", weight=1)

    def test_form_panels_must_be_contributed_panels(self):
        class BadMixin:
            form_panels = (FormPanel("Nope", ("name",)),)

        class BadForm(BadMixin, ManufacturerLayoutForm):
            pass

        with self.assertRaises(TypeError):
            FormLayout(BadForm())


class VisibleIfEnforcementTestCase(TestCase):
    """`visible_if` and inactive tab groups are enforced on the server during validation, not only in the browser."""

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get("/")
        self.request.user = self.user

    @staticmethod
    def mode_form_class(panel_level=False):
        detail = FormField("detail", visible_if=When("mode", eq="on"))
        scratch = FormField("scratch", visible_if=When("mode", eq="on"), clear_on_hide=True)
        if panel_level:
            fieldsets = (
                ("Main", ("name", "mode")),
                FormPanel(
                    "Details",
                    (FormField("detail"), FormField("scratch", clear_on_hide=True)),
                    visible_if=When("mode", eq="on"),
                ),
            )
        else:
            fieldsets = (("Main", ("name", "mode", detail, scratch)),)

        class ModeForm(ManufacturerLayoutForm):
            mode = forms.ChoiceField(choices=[("", "---------"), ("on", "On"), ("off", "Off")], required=False)
            detail = forms.CharField(required=True)
            scratch = forms.CharField(required=False)

            class Meta(ManufacturerLayoutForm.Meta):
                pass

        ModeForm.Meta.fieldsets = fieldsets
        return ModeForm

    def test_hidden_required_field_does_not_block_submission(self):
        form = self.mode_form_class()(data={"name": "Vendor", "mode": "off", "detail": "stale", "scratch": "stale"})
        self.assertTrue(form.is_valid(), form.errors)
        # `detail` was hidden: its submitted value is ignored
        self.assertNotIn("detail", form.cleaned_data)
        # `scratch` was hidden with clear_on_hide: it is cleared
        self.assertEqual(form.cleaned_data["scratch"], "")
        # `required` was lifted only for the cleaning run; the field is as declared afterwards
        self.assertTrue(form.fields["detail"].required)

    def test_hidden_field_errors_are_discarded(self):
        class StrictField(forms.CharField):
            """Rejects being cleared, to exercise the fallback when `clear(None)` fails."""

            def clean(self, value):
                if value is None:
                    raise ValidationError("cannot be cleared")
                return super().clean(value)

        class CountForm(self.mode_form_class()):
            count = forms.IntegerField(required=False)
            strict = StrictField(required=False)

            class Meta(self.mode_form_class().Meta):
                fieldsets = (
                    (
                        "Main",
                        (
                            "name",
                            "mode",
                            FormField("detail", visible_if=When("mode", eq="on")),
                            FormField("scratch", visible_if=When("mode", eq="on"), clear_on_hide=True),
                            FormField("count", visible_if=When("mode", eq="on")),
                            FormField("strict", visible_if=When("mode", eq="on"), clear_on_hide=True),
                        ),
                    ),
                )

        form = CountForm(data={"name": "Vendor", "mode": "off", "count": "not-a-number", "strict": "stale"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("count", form.errors)
        self.assertNotIn("count", form.cleaned_data)
        # Clearing failed, so the value is dropped rather than left stale
        self.assertNotIn("strict", form.cleaned_data)
        # Visible, the same input is an error as usual
        form = CountForm(data={"name": "Vendor", "mode": "on", "detail": "d", "count": "not-a-number"})
        self.assertFalse(form.is_valid())
        self.assertIn("count", form.errors)

    def test_panel_level_clear_on_hide(self):
        form_class = self.mode_form_class(panel_level=True)
        form_class.Meta.fieldsets[1].clear_on_hide = True
        form = form_class(data={"name": "Vendor", "mode": "", "detail": "stale", "scratch": "stale"})
        self.assertTrue(form.is_valid(), form.errors)
        # Set on the panel, `clear_on_hide` applies to every field in it: `detail` is cleared, not merely dropped
        self.assertEqual(form.cleaned_data["detail"], "")
        self.assertEqual(form.cleaned_data["scratch"], "")

    def test_disabled_field_initial_value_drives_conditions(self):
        """A disabled field never submits; its initial value is what the browser showed, so that is what counts."""

        class LockedModeForm(self.mode_form_class()):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields["mode"].disabled = True

        form = LockedModeForm(data={"name": "Vendor"}, initial={"mode": "on"})
        self.assertFalse(form.is_valid())
        self.assertIn("detail", form.errors)  # visible because the locked mode is "on", so still required
        form = LockedModeForm(data={"name": "Vendor", "detail": "stale"}, initial={"mode": "off"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("detail", form.cleaned_data)

    def test_declaration_validation(self):
        with self.assertRaises(TypeError):
            FormPanel("x", visible_if="mode")
        with self.assertRaises(TypeError):
            FormField("name", visible_if=When("mode", eq="on"), clear_on_hide="yes")

    def test_visible_field_is_validated_normally(self):
        form = self.mode_form_class()(data={"name": "Vendor", "mode": "on"})
        self.assertFalse(form.is_valid())
        self.assertIn("detail", form.errors)
        form = self.mode_form_class()(data={"name": "Vendor", "mode": "on", "detail": "x", "scratch": "y"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["detail"], "x")
        self.assertEqual(form.cleaned_data["scratch"], "y")

    def test_panel_level_condition_hides_every_field_in_the_panel(self):
        form = self.mode_form_class(panel_level=True)(
            data={"name": "Vendor", "mode": "", "detail": "stale", "scratch": "stale"}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("detail", form.cleaned_data)
        self.assertEqual(form.cleaned_data["scratch"], "")

    def test_inactive_tab_fields_are_ignored(self):
        class TabForm(ManufacturerLayoutForm):
            class Meta(ManufacturerLayoutForm.Meta):
                fieldsets = (("Main", ("name", TabbedGroups(("A", ("description",)), ("B", ("extra",))))),)

        context = Context({"request": self.request})
        unbound = TabForm()
        tabs = unbound.layout.panels[0]._bound_items[1]
        input_name = tabs.active_tab_input_name
        self.assertTrue(input_name.startswith("_nb_active_tab_"))
        html = unbound.layout.render(context)
        self.assertIn(f'name="{input_name}" value="0" data-nb-active-tab', html)

        # Tab B active: tab A's field is ignored, tab B's is kept, and tab B stays active on re-render
        form = TabForm(data={"name": "Vendor", "description": "d", "extra": "e", input_name: "1"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("description", form.cleaned_data)
        self.assertEqual(form.cleaned_data["extra"], "e")
        html = form.layout.render(context)
        self.assertIn(f'name="{input_name}" value="1" data-nb-active-tab', html)
        self.assertRegex(html, r'nav-link active"\s+id="[^"]*-1-tab"')

        # Without the marker (no JavaScript), nothing is treated as inactive
        form = TabForm(data={"name": "Vendor", "description": "d", "extra": "e"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["description"], "d")
        self.assertEqual(form.cleaned_data["extra"], "e")

        # An out-of-range marker is ignored too
        form = TabForm(data={"name": "Vendor", "description": "d", "extra": "e", input_name: "7"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["description"], "d")

    def test_clear_inactive_tab_fields_are_cleared_on_a_prefixed_form(self):
        """With `clear_inactive`, the inactive tab's fields are cleared rather than ignored; prefixes are honoured."""

        class ExclusiveTabForm(ManufacturerLayoutForm):
            class Meta(ManufacturerLayoutForm.Meta):
                fieldsets = (
                    (
                        "Main",
                        ("name", TabbedGroups(("A", ("description",)), ("B", ("extra",)), clear_inactive=True)),
                    ),
                )

        unbound = ExclusiveTabForm(prefix="p")
        tabs = unbound.layout.panels[0]._bound_items[1]
        input_name = tabs.active_tab_input_name
        self.assertTrue(input_name.startswith("p-_nb_active_tab_"))
        html = unbound.layout.render(Context({"request": self.request}))
        self.assertIn('data-nb-clear-inactive="true"', html)
        self.assertIn('id="id_p-description"', html)

        form = ExclusiveTabForm(
            prefix="p", data={"p-name": "Vendor", "p-description": "d", "p-extra": "e", input_name: "1"}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["description"], "")  # cleared, not dropped
        self.assertEqual(form.cleaned_data["extra"], "e")


class DeviceFormLayoutTestCase(TestCase):
    """`DeviceForm.Meta.fieldsets` reproduces the former hand-written template, including its conditional parts."""

    PANEL_LABELS = (
        "Device",
        "Location",
        "Hardware",
        "Software",
        "VRF Assignment",
        "Management",
        "Topology",
        "Virtualization",
        "Tenancy",
        "Local Config Context Data",
        "Comments",
    )

    def setUp(self):
        super().setUp()
        self.user.is_superuser = True
        self.user.save()

    def test_add_page(self):
        response = self.client.get(reverse("dcim:device_add"))
        self.assertHttpStatus(response, 200)
        content = response.content.decode(response.charset)
        positions = [content.index(f"<strong>{label}</strong>") for label in self.PANEL_LABELS]
        self.assertEqual(positions, sorted(positions), "panels are not rendered in the declared order")
        # The software image list and the script that drives it (shipped via the panel's Media)
        self.assertIn("data-nb-software-image-picker", content)
        self.assertIn("js/software_image_picker.js", content)
        # On create: no primary IP fields, a hint instead; rack face/position shown (not a child device)
        self.assertNotIn('id="id_primary_ip4"', content)
        self.assertIn("A management IP address can be selected after creating this device", content)
        self.assertIn('id="id_face"', content)
        self.assertIn('id="id_position"', content)
        self.assertNotIn("Parent bay", content)

    def test_edit_page(self):
        device = Device.objects.first()
        response = self.client.get(reverse("dcim:device_edit", kwargs={"pk": device.pk}))
        self.assertHttpStatus(response, 200)
        content = response.content.decode(response.charset)
        self.assertIn('id="id_primary_ip4"', content)
        self.assertIn('id="id_primary_ip6"', content)
        self.assertNotIn("A management IP address can be selected after creating this device", content)
        self.assertIn("<strong>Notes</strong>", content)


class IPAddressFormLayoutTestCase(TestCase):
    """`IPAddressForm.Meta.fieldsets` renders the NAT selectors as tabbed groups feeding `nat_inside`."""

    def test_add_page(self):
        self.user.is_superuser = True
        self.user.save()
        response = self.client.get(reverse("ipam:ipaddress_add"))
        self.assertHttpStatus(response, 200)
        content = response.content.decode(response.charset)
        for label in ("IP Address", "Tenancy", "NAT IP (Inside)"):
            self.assertIn(f"<strong>{label}</strong>", content)
        self.assertLess(content.index("<strong>Tenancy</strong>"), content.index("<strong>NAT IP (Inside)</strong>"))
        self.assertIn('class="nb-form-tabbed-groups"', content)
        self.assertIn("data-nb-active-tab", content)
        for tab in ("By Device", "By VM", "By IP"):
            self.assertIn(f">{tab}<", content)
        # `nat_inside` sits after the tabs, outside any pane
        self.assertIn('id="id_nat_inside"', content)
        self.assertLess(content.index('id="id_nat_vrf"'), content.index('id="id_nat_inside"'))
