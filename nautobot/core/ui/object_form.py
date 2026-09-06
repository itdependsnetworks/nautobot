"""Classes and utilities for declaratively laying out a form via its `Meta.fieldsets`.

This module is the form-side counterpart of `nautobot.core.ui.object_detail`: a form declares its layout as a tuple
of components on `Meta.fieldsets`, and `FormLayoutMixin` resolves that declaration (together with any panels
contributed by form mixins) into an ordered, renderable `FormLayout`.

Two visibility mechanisms exist and are deliberately named to carry their difference:

- `render_if` is evaluated **once, on the server**. When false, no HTML is emitted for the component at all.
- `visible_if` is a `Condition` that is serialized into the page for the client to re-evaluate as the user changes
  values, **and** is enforced again on the server during form validation. When hidden, the HTML is still emitted,
  but the wrapper is hidden and the controls inside it are disabled so that they neither submit nor participate in
  cross-field query narrowing.
"""

from collections.abc import Mapping
import copy
from functools import cached_property

from django.core.exceptions import ObjectDoesNotExist
from django.forms.utils import flatatt
from django.template import Context
from django.utils.html import format_html, format_html_join
from django.utils.text import capfirst

from nautobot.core.templatetags.form_helpers import get_render_field_context
from nautobot.core.ui.object_detail import Component
from nautobot.core.ui.utils import render_component_template

__all__ = (
    "Contributed",
    "ContributedFieldsPanel",
    "FormComponent",
    "FormField",
    "FormLayout",
    "FormLayoutMixin",
    "FormPanel",
)


#
# `render_if` evaluation
#


def evaluate_render_if(render_if, context):
    """
    Evaluate a component's `render_if` against the render context.

    Args:
        render_if: `None` (always render), a dotted-path string resolved against the context and tested for
            truthiness (optionally prefixed with `not `, e.g. `"not obj.parent_bay"`), or a callable taking the
            context and returning a boolean.
        context (Context or dict): The render context.
    """
    if render_if is None:
        return True
    if callable(render_if):
        return bool(render_if(context))
    if isinstance(render_if, str):
        expression = render_if.strip()
        negate = False
        if expression.startswith("not "):
            negate = True
            expression = expression[4:].strip()
        result = bool(resolve_dotted_path(expression, context))
        return not result if negate else result
    raise TypeError(f"render_if must be None, a string, or a callable; got {type(render_if)}")


def resolve_dotted_path(expression, root):
    """
    Resolve a dotted path such as `"obj.parent_bay.device"` against `root`, the way a template variable would.

    Each segment is tried as a mapping key, then an attribute, then a sequence index; a resulting callable is called
    (unless it is marked `do_not_call_in_templates` or `alters_data`). Any lookup failure, including a missing related
    object, yields `None` rather than an exception, so the result is safe to test for truthiness.
    """
    current = root
    for bit in expression.split("."):
        try:
            if isinstance(current, (Context, Mapping)):
                current = current[bit]
            elif bit.isdigit() and isinstance(current, (list, tuple)):
                current = current[int(bit)]
            else:
                current = getattr(current, bit)
        except (KeyError, AttributeError, IndexError, TypeError, ObjectDoesNotExist):
            return None
        if callable(current) and not getattr(current, "do_not_call_in_templates", False):
            if getattr(current, "alters_data", False):
                return None
            try:
                current = current()
            except (TypeError, ObjectDoesNotExist):
                return None
    return current


def _as_context(context):
    """Ensure we are working with a template `Context` (tests may hand us a plain dict)."""
    if isinstance(context, Context):
        return context
    return Context(context or {})


#
# Declaration-only helpers (not components)
#


class Contributed:
    """
    Reference to a panel contributed by a form mixin via its `form_panels` attribute.

    At the top level of `Meta.fieldsets`, pins that contributed panel to this slot (overriding its default weight).
    Inside `FormPanel.items`, splices that panel's not-yet-claimed fields into the enclosing panel instead.

    Well-known names: `"tenancy"`, `"custom_fields"`, `"relationships"`, `"notes"`, `"dynamic_groups"`, `"tags"`.
    """

    def __init__(self, name):
        if not isinstance(name, str) or not name:
            raise TypeError("Contributed() requires a non-empty name")
        self.name = name

    def __repr__(self):
        return f"Contributed({self.name!r})"


#
# Components
#


class FormComponent(Component):
    """
    Base class for components that can appear in a form's `Meta.fieldsets`.

    Components declared on `Meta.fieldsets` are shared by every instance of the form, so they must never be mutated
    at render time. Resolution (`bind()`) produces a shallow copy per form instance carrying the bound form and any
    per-instance state.

    Keyword Args:
        render_if (str or callable, optional): Server-side gate. A dotted path resolved against the render context
            (optionally prefixed with `not `), or a callable taking the context. When false, nothing is emitted.
        attrs (dict, optional): Extra HTML attributes for the component's wrapper element.
        weight (int, optional): Relative ordering among top-level panels. Items inside a panel are ordered
            positionally and ignore weight. Top-level panels without an explicit weight receive one from their
            position in `Meta.fieldsets`.
        required_permissions (list, optional): Permissions the user must hold for the component to render.

    `deferred_render` is not supported: a deferred panel's fields would be absent from the DOM at submit time.
    """

    attrs = None
    deferred_render = False
    label = None
    render_if = None
    template_path = None

    def __init__(self, **kwargs):
        if kwargs.pop("deferred_render", False):
            raise TypeError(
                "deferred_render is not supported by form components; "
                "a deferred panel's fields would be missing from the DOM when the form is submitted."
            )
        kwargs.setdefault("weight", 0)
        super().__init__(**kwargs)
        if self.render_if is not None and not (isinstance(self.render_if, str) or callable(self.render_if)):
            raise TypeError("render_if must be a dotted-path string or a callable")
        if self.attrs is not None and not isinstance(self.attrs, dict):
            raise TypeError("attrs must be a dict")
        # Populated on bound copies only:
        self.form = None
        self.layout = None

    # --- resolution -------------------------------------------------------------------------------------------

    def bind(self, layout, weight=None):
        """Return a shallow copy of this component bound to `layout.form`, with children resolved."""
        bound = copy.copy(self)
        bound.form = layout.form
        bound.layout = layout
        if weight is not None:
            bound.weight = weight
        bound._bind_children(layout)
        return bound

    def _bind_children(self, layout):
        """Hook for container components to resolve their children. Called on the bound copy."""

    @property
    def field_names(self):
        """Names of the form fields rendered by this component (and its children), once bound."""
        return ()

    def iter_components(self):
        """Yield this component and, recursively, any bound children."""
        yield self

    # --- rendering --------------------------------------------------------------------------------------------

    def should_render(self, context):
        if not super().should_render(context):
            return False
        return evaluate_render_if(self.render_if, context)

    def wrapper_attrs(self):
        """HTML attributes for this component's wrapper element."""
        attrs = dict(self.attrs or {})
        return attrs

    def _wrap(self, html):
        """Wrap rendered HTML in a `div` carrying `wrapper_attrs()`, or return it untouched when there are none."""
        attrs = self.wrapper_attrs()
        if not attrs or not html:
            return html
        return format_html("<div{}>{}</div>", flatatt(attrs), html)

    def render(self, context):
        return ""


class FormField(FormComponent):
    """
    A single form field, rendered with the standard label/control row.

    A bare string in `Meta.fieldsets` is shorthand for `FormField(name)`.

    Args:
        name (str): Name of the form field.

    Keyword Args:
        label (str, optional): Override the field's label.
        help_text (str, optional): Override the field's help text.
        full_width (bool, optional): Render the control across the full width of the panel instead of the standard
            3/9 label/control split. Useful for large editor-style widgets.
        container_class (str, optional): Extra CSS class for the field's container element.
    """

    container_class = None
    full_width = False
    help_text = None
    name = None

    def __init__(self, name, **kwargs):
        if not isinstance(name, str) or not name:
            raise TypeError("FormField() requires a field name")
        kwargs["name"] = name
        super().__init__(**kwargs)

    def __repr__(self):
        return f"FormField({self.name!r})"

    @property
    def field_names(self):
        return (self.name,)

    def bind(self, layout, weight=None):
        bound = super().bind(layout, weight)
        layout.claim(self.name, bound)
        form = layout.form
        # Apply overrides to the field first, then to the BoundField: the latter snapshots `label` and `help_text`
        # when first constructed, and it may already have been constructed (and cached) before we got here.
        field = form.fields[self.name]
        if self.label is not None:
            field.label = self.label
        if self.help_text is not None:
            field.help_text = self.help_text
        bound_field = form[self.name]
        if self.label is not None:
            bound_field.label = self.label
        if self.help_text is not None:
            bound_field.help_text = self.help_text
        return bound

    def render(self, context):
        context = _as_context(context)
        if not self.should_render(context):
            return ""
        bound_field = self.form[self.name]
        if bound_field.is_hidden:
            # Hidden fields are emitted once by the layout itself, outside of any panel.
            return ""
        extra = get_render_field_context(
            context.get("request"),
            bound_field,
            container_class=self.container_class,
            full_width=self.full_width,
        )
        return self._wrap(render_component_template("utilities/render_field.html", context, **extra))


class FormPanel(FormComponent):
    """
    A titled group of fields, rendered as a card.

    A `("Label", (items...))` tuple in `Meta.fieldsets` is shorthand for `FormPanel(label, items)`, and the
    nautobot-app-floor-plan style `("Label", {"tabs": ((label, items), ...)})` is shorthand for a panel containing
    a single `TabbedGroups`.

    Args:
        label (str, optional): The card header. `None` renders a card with no header.
        items (tuple, optional): Field names, item components, or `Contributed(name)` splices, in display order.

    Keyword Args:
        css_class (str, optional): Bootstrap contextual class for the card border and header (e.g. `"warning"`).
        attrs (dict, optional): Extra HTML attributes for the card element; a `class` entry is merged into the
            card's classes.
    """

    # NB-FIELDSETS-REVIEW[behaviour] (temporary marker, delete before merge): declared panels take slot weights
    # 100, 200, ...; contributed panels sit at 5100+. On the eleven migrated forms whose old template placed the
    # Custom Fields / Relationships / Notes / Tags cards *before* a trailing "Comments" card, Comments now comes
    # first. Pinning with `Contributed(...)` would restore the old order per form.
    WEIGHT_TENANCY_PANEL = 5100
    WEIGHT_CUSTOM_FIELDS_PANEL = 5200
    WEIGHT_RELATIONSHIPS_PANEL = 5300
    WEIGHT_NOTES_PANEL = 5400
    WEIGHT_DYNAMIC_GROUPS_PANEL = 5500
    WEIGHT_TAGS_PANEL = 5600
    WEIGHT_TRAILING_PANEL = 9000

    css_class = None
    items = ()
    template_path = "components/form/panel.html"

    def __init__(self, label=None, items=(), **kwargs):
        if isinstance(items, str):
            raise TypeError("FormPanel() items must be a tuple or list of items, not a single string")
        kwargs["label"] = label
        kwargs["items"] = tuple(items)
        super().__init__(**kwargs)
        self._bound_items = ()

    def __repr__(self):
        return f"{self.__class__.__name__}({self.label!r})"

    @property
    def field_names(self):
        return tuple(name for item in self._bound_items for name in item.field_names)

    def _bind_children(self, layout):
        self._bound_items = tuple(bound for item in self.items for bound in layout.bind_item(item))

    def iter_components(self):
        yield self
        for item in self._bound_items:
            yield from item.iter_components()

    @property
    def has_content(self):
        """Whether this panel has any items to render."""
        return bool(self._bound_items)

    def get_label(self, context):
        """The card header text, if any."""
        return self.label

    def render_body_content(self, context):
        """Render the card body: each bound item in order."""
        return format_html_join("", "{}", ((item.render(context),) for item in self._bound_items))

    def render(self, context):
        context = _as_context(context)
        if not self.should_render(context):
            return ""
        body = self.render_body_content(context)
        if not str(body).strip():
            # Never render an empty card.
            return ""
        return self.render_card(context, body, css_class=self.css_class)

    def render_card(self, context, body, css_class=None):
        """Wrap already-rendered `body` in the card markup, carrying this component's wrapper attributes."""
        attrs = self.wrapper_attrs()
        # `class` cannot be repeated on an element; fold a caller-supplied class into the card's own.
        extra_class = attrs.pop("class", "")
        return render_component_template(
            self.template_path,
            context,
            label=self.get_label(context),
            body=body,
            css_class=css_class,
            extra_class=extra_class,
            wrapper_attrs=flatatt(attrs) if attrs else "",
        )


class ContributedFieldsPanel(FormPanel):
    """
    A panel whose fields are discovered from the form instance at resolution time.

    Form mixins that add fields dynamically (custom fields, relationships, notes, tags, tenancy, ...) declare one of
    these in a `form_panels` class attribute. The panel renders whichever of its fields the form actually has and
    that have not already been claimed by an explicit entry in `Meta.fieldsets`; if none remain, it renders nothing.

    Args:
        name (str): The key by which `Contributed(name)` refers to this panel.
        label (str): The card header.
        fields (tuple or callable): Field names to look for on the form, or a callable taking the form and
            returning them.
        weight (int): Default position relative to other panels; `Contributed(name)` in `Meta.fieldsets`
            overrides it.
    """

    fields = ()
    name = None

    def __init__(self, name, label, fields, weight, **kwargs):
        if not isinstance(name, str) or not name:
            raise TypeError("ContributedFieldsPanel() requires a name")
        if not callable(fields) and isinstance(fields, str):
            raise TypeError("ContributedFieldsPanel() fields must be a tuple of names or a callable")
        kwargs.update({"name": name, "label": label, "fields": fields, "weight": weight})
        super().__init__(**kwargs)

    def __repr__(self):
        return f"ContributedFieldsPanel({self.name!r})"

    def discover_field_names(self, form):
        """Return the names of this panel's fields that exist on `form`, in order."""
        names = self.fields(form) if callable(self.fields) else self.fields
        return [name for name in names if name in form.fields]

    def _bind_children(self, layout):
        names = [name for name in self.discover_field_names(layout.form) if not layout.is_claimed(name)]
        self._bound_items = tuple(FormField(name).bind(layout) for name in names)


class _TrailingPanel(ContributedFieldsPanel):
    """Internal: collects every visible field not claimed by any other panel, so that nothing is silently dropped."""

    def __init__(self):
        super().__init__(
            name="__trailing__",
            label=None,
            fields=lambda form: [name for name, field in form.fields.items() if not field.widget.is_hidden],
            weight=FormPanel.WEIGHT_TRAILING_PANEL,
        )

    def get_label(self, context):
        layout = self.layout
        if layout.has_declared_panels:
            return "Other"
        if layout.default_label:
            return capfirst(layout.default_label)
        obj_type = context.get("obj_type")
        if obj_type:
            return capfirst(str(obj_type))
        meta = getattr(self.form, "_meta", None)
        model = getattr(meta, "model", None)
        if model is not None:
            return capfirst(model._meta.verbose_name)
        return None


#
# Resolution
#


def _coerce_toplevel(entry):
    """Apply top-level shorthand: `("Label", (...))` and the floor-plan `("Label", {"tabs": ...})` form."""
    if isinstance(entry, (FormPanel, Contributed)):
        return entry
    if isinstance(entry, (tuple, list)) and len(entry) == 2 and isinstance(entry[0], (str, type(None))):
        label, spec = entry
        if isinstance(spec, (tuple, list)):
            return FormPanel(label, items=spec)
    if isinstance(entry, FormComponent):
        raise TypeError(
            f"{entry!r} cannot appear at the top level of Meta.fieldsets; wrap it in a FormPanel or FormSetPanel"
        )
    raise TypeError(f"Unrecognized Meta.fieldsets entry {entry!r}")


def _coerce_item(item):
    """Apply item shorthand: a bare string is a `FormField`."""
    if isinstance(item, str):
        return FormField(item)
    if isinstance(item, FormPanel):
        raise TypeError(f"{item!r} cannot be nested inside another panel")
    if isinstance(item, (FormComponent, Contributed)):
        return item
    if isinstance(item, (tuple, list)):
        raise TypeError(
            f"Nested tuple {item!r} is not a valid item; use TabbedGroups for grouped fields within a panel"
        )
    raise TypeError(f"Unrecognized fieldset item {item!r}")


class FormLayout:
    """
    The resolved layout of one form instance: an ordered list of bound top-level panels.

    Resolution rules:

    1. Shorthand is expanded (`_coerce_toplevel`, `_coerce_item`), including the floor-plan `{"tabs": ...}` form.
    2. Panels in `Meta.fieldsets` receive implicit weights 100, 200, 300... unless they declare their own.
       Mixin-contributed panels use their declared weights; `Contributed(name)` pins one to a slot.
    3. Resolution runs lazily, on first access of `form.layout`, so that every mixin and every subclass `__init__`
       has finished adding or removing fields.
    4. Every visible field is claimed exactly once: a duplicate or unknown name raises `ValueError`.
    5. Hidden fields are emitted once, outside all panels, ahead of them.
    6. Unclaimed fields are collected into a trailing panel. When no panels were declared it is the form's main
       card: it renders first and is labelled with the object type, matching the generic create/edit page. When
       panels were declared it renders last and is labelled `"Other"`.
    """

    def __init__(self, form):
        self.form = form
        self.default_label = None
        self._claims = {}
        self._contributed = {}
        self.panels = ()
        self.has_declared_panels = False
        self._resolve()

    @staticmethod
    def declared_fieldsets(form_class):
        """Return the `Meta.fieldsets` declaration for a form class, or an empty tuple."""
        meta = getattr(form_class, "Meta", None)
        fieldsets = getattr(meta, "fieldsets", None) or ()
        if isinstance(fieldsets, (str, dict)):
            raise TypeError(f"{form_class.__name__}.Meta.fieldsets must be a tuple or list")
        return tuple(fieldsets)

    def _collect_contributed(self):
        """Gather `form_panels` from every class in the form's MRO, base classes first so subclasses can override."""
        panels = {}
        for klass in reversed(type(self.form).__mro__):
            for panel in klass.__dict__.get("form_panels", ()):
                if not isinstance(panel, ContributedFieldsPanel):
                    raise TypeError(f"{klass.__name__}.form_panels entries must be ContributedFieldsPanel instances")
                panels[panel.name] = panel
        return panels

    def claim(self, name, component):
        """Record that `component` renders field `name`; raise if the name is unknown or already claimed."""
        form_name = type(self.form).__name__
        if name not in self.form.fields:
            raise ValueError(f"{form_name}.Meta.fieldsets references unknown field {name!r}")
        if name in self._claims:
            raise ValueError(f"{form_name}.Meta.fieldsets lists field {name!r} more than once")
        self._claims[name] = component

    def is_claimed(self, name):
        return name in self._claims

    def claimed_component(self, name):
        """The bound component rendering field `name`, or `None` if it is unclaimed or declared `Omitted`."""
        component = self._claims.get(name)
        return component if isinstance(component, FormComponent) else None

    def bind_item(self, item):
        """Resolve one item inside a panel into a list of bound components (a `Contributed` splice may expand)."""
        item = _coerce_item(item)
        if isinstance(item, Contributed):
            return self._splice_contributed(item)
        return [item.bind(self)]

    def _contributed_declaration(self, name):
        """The `ContributedFieldsPanel` registered under `name`, or raise naming the ones available."""
        declaration = self._contributed.get(name)
        if declaration is None:
            raise ValueError(
                f"{type(self.form).__name__}.Meta.fieldsets references unknown contributed panel {name!r}; "
                f"available: {sorted(self._contributed)}"
            )
        return declaration

    def _splice_contributed(self, item):
        """A `Contributed(name)` inside a panel: bind that panel's not-yet-claimed fields as plain rows here."""
        declaration = self._contributed_declaration(item.name)
        names = [name for name in declaration.discover_field_names(self.form) if not self.is_claimed(name)]
        return [FormField(name).bind(self) for name in names]

    def _resolve(self):
        self._contributed = self._collect_contributed()
        bound, pinned = self._bind_declared_panels()
        bound.extend(self._bind_contributed_panels(pinned))
        bound.append(self._bind_trailing_panel())
        self.panels = tuple(sorted(bound, key=lambda component: component.weight))

    def _bind_declared_panels(self):
        """
        Bind the top-level entries of `Meta.fieldsets`.

        Returns:
            (tuple): The bound panels, and a mapping of contributed panel name to the slot weight a `Contributed`
            pin claims for it.
        """
        bound = []
        pinned = {}
        for index, entry in enumerate(self.declared_fieldsets(type(self.form))):
            slot_weight = (index + 1) * 100
            entry = _coerce_toplevel(entry)
            if isinstance(entry, Contributed):
                self._contributed_declaration(entry.name)  # validates the name
                pinned[entry.name] = slot_weight
                continue
            bound.append(entry.bind(self, weight=entry.weight or slot_weight))
            self.has_declared_panels = True
        return bound, pinned

    def _bind_contributed_panels(self, pinned):
        """Bind every mixin-contributed panel at its pinned slot weight, else its own default weight."""
        return [
            declaration.bind(self, weight=pinned.get(name, declaration.weight))
            for name, declaration in self._contributed.items()
        ]

    def _bind_trailing_panel(self):
        # With no declared panels the trailing panel *is* the form's main card and leads, exactly as the generic
        # create/edit template has always rendered it; otherwise it collects the leftovers at the very end.
        weight = FormPanel.WEIGHT_TRAILING_PANEL if self.has_declared_panels else 0
        return _TrailingPanel().bind(self, weight=weight)

    # --- queries ----------------------------------------------------------------------------------------------

    @property
    def contributed_panels(self):
        """The bound mixin-contributed panels, by name."""
        return {panel.name: panel for panel in self.panels if isinstance(panel, ContributedFieldsPanel)}

    def iter_components(self):
        for panel in self.panels:
            yield from panel.iter_components()

    # --- rendering --------------------------------------------------------------------------------------------

    def render_hidden_fields(self):
        return format_html_join("", "{}", ((str(bound_field),) for bound_field in self.form.hidden_fields()))

    def render(self, context):
        """Render hidden fields followed by every panel, in weight order."""
        context = _as_context(context)
        with context.update({"form": self.form}):
            panels = format_html_join("", "{}", ((panel.render(context),) for panel in self.panels))
        return format_html("{}{}", self.render_hidden_fields(), panels)

    def render_panels(self, context, names):
        """Render only the named contributed panels. Used by the deprecated `extras_features_edit_form_fields.html`."""
        context = _as_context(context)
        panels = self.contributed_panels
        with context.update({"form": self.form}):
            return format_html_join("", "{}", ((panels[name].render(context),) for name in names if name in panels))


class FormLayoutMixin:
    """
    Form mixin providing `Meta.fieldsets` support.

    Exposes `layout` (the resolved `FormLayout`, computed on first access) and `has_declared_layout`
    (whether this form class declares any fieldsets).

    Mixins that add fields dynamically declare `form_panels`, a tuple of `ContributedFieldsPanel`; the tags panel is
    declared here because the `tags` field comes from the model rather than from a mixin.
    """

    form_panels = (
        ContributedFieldsPanel(
            name="tags",
            label="Tags",
            fields=("tags",),
            weight=FormPanel.WEIGHT_TAGS_PANEL,
        ),
    )

    @property
    def has_declared_layout(self):
        return bool(FormLayout.declared_fieldsets(type(self)))

    @cached_property
    def layout(self):
        return FormLayout(self)
