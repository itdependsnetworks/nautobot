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

import copy

from django.forms.utils import flatatt
from django.template import Context
from django.utils.html import format_html, format_html_join

from nautobot.core.templatetags.form_helpers import get_render_field_context
from nautobot.core.ui.object_detail import Component
from nautobot.core.ui.utils import render_component_template

__all__ = (
    "FormComponent",
    "FormField",
    "FormPanel",
)


def _as_context(context):
    """Ensure we are working with a template `Context` (tests may hand us a plain dict)."""
    if isinstance(context, Context):
        return context
    return Context(context or {})


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
    template_path = None

    def __init__(self, **kwargs):
        if kwargs.pop("deferred_render", False):
            raise TypeError(
                "deferred_render is not supported by form components; "
                "a deferred panel's fields would be missing from the DOM when the form is submitted."
            )
        kwargs.setdefault("weight", 0)
        super().__init__(**kwargs)
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
