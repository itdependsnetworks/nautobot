"""Tests for `nautobot.core.ui.object_form`: declarative form layout via `Meta.fieldsets`."""

import re
from types import SimpleNamespace

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.template import Context, engines
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from nautobot.circuits.forms import ProviderNetworkForm
from nautobot.core.testing import TestCase
from nautobot.core.ui.object_form import (
    Contributed,
    ContributedFieldsPanel,
    evaluate_render_if,
    FormField,
    FormLayout,
    FormPanel,
    InlineFields,
    resolve_dotted_path,
)
from nautobot.dcim.forms import ManufacturerForm, SoftwareVersionForm
from nautobot.dcim.models import Manufacturer, Platform
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
