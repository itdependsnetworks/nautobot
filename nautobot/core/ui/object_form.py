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
import json
import logging

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.forms.utils import flatatt
from django.forms.widgets import Media
from django.template import Context
from django.utils.html import format_html, format_html_join
from django.utils.text import capfirst

from nautobot.core.templatetags.form_helpers import get_render_field_context
from nautobot.core.templatetags.helpers import hyperlinked_object
from nautobot.core.ui.object_detail import Component
from nautobot.core.ui.utils import render_component_template

logger = logging.getLogger(__name__)

__all__ = (
    "AllOf",
    "AnyOf",
    "Condition",
    "Contributed",
    "ContributedFieldsPanel",
    "FieldGroup",
    "FormComponent",
    "FormField",
    "FormLayout",
    "FormLayoutMixin",
    "FormPanel",
    "FormSetPanel",
    "IncludedTemplate",
    "InlineFields",
    "Not",
    "Omitted",
    "StaticField",
    "TabbedGroups",
    "When",
)

_UNSET = object()

# Values that the browser (and Select2 in particular) uses to mean "nothing selected".
_EMPTY_VALUES = (None, "", "null")


#
# Conditions (`visible_if`)
#


def _normalize_value(value):
    """Collapse the various ways an "empty" value can reach us into `None` (scalar) or `[]` (list)."""
    if isinstance(value, (list, tuple)):
        return [item for item in value if item not in _EMPTY_VALUES]
    if value in _EMPTY_VALUES:
        return None
    return value


def _as_bool(value):
    """Coerce a raw form value to a boolean the way a checkbox would be interpreted."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() not in ("", "0", "false", "off", "no", "null", "none")


def _equals(actual, expected):
    """Compare a raw form value to an expected value, tolerating the str-typing of submitted data."""
    if isinstance(expected, bool):
        return _as_bool(actual) is expected
    if actual is None or expected is None:
        return actual is None and expected is None
    return str(actual) == str(expected)


class Condition:
    """
    Base class for `visible_if` conditions.

    A condition must round-trip to JSON (for the client-side runtime) and be evaluable in Python against raw form
    data (for server-side enforcement). Keep the grammar small: anything richer than what `When`, `AnyOf`, `AllOf`
    and `Not` can express belongs in an HTMX round trip instead.
    """

    def to_dict(self):
        """Return a JSON-serializable dict describing this condition."""
        raise NotImplementedError

    def to_json(self):
        """Serialize this condition for the `data-nb-visible-if` attribute."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def matches(self, data):
        """
        Evaluate this condition against a mapping of raw form values.

        Args:
            data (Mapping): Field name to raw value, as produced by `Widget.value_from_datadict()`; strings, lists
                of strings, or booleans (for checkboxes).
        """
        raise NotImplementedError

    def field_names(self):
        """Return the set of field names this condition depends on."""
        raise NotImplementedError

    @staticmethod
    def from_dict(data):
        """Reconstruct a condition from the output of `to_dict()`."""
        if "any" in data:
            return AnyOf(*(Condition.from_dict(item) for item in data["any"]))
        if "all" in data:
            return AllOf(*(Condition.from_dict(item) for item in data["all"]))
        if "not" in data:
            return Not(Condition.from_dict(data["not"]))
        kwargs = {}
        if "eq" in data:
            kwargs["eq"] = data["eq"]
        elif "in" in data:
            kwargs["in_"] = data["in"]
        elif "is_set" in data:
            kwargs["is_set"] = data["is_set"]
        return When(data["field"], **kwargs)

    def __eq__(self, other):
        return isinstance(other, Condition) and self.to_dict() == other.to_dict()

    def __hash__(self):
        return hash(self.to_json())

    def __repr__(self):
        return f"{self.__class__.__name__}({self.to_json()})"


class When(Condition):
    """
    A condition on a single field's value.

    Exactly one of the keyword arguments must be given:

    Args:
        field (str): Name of the form field to inspect.
        eq (Any): The field's value must equal this value (compared as strings; booleans compare as a checkbox would).
        in_ (list): The field's value must be one of these values.
        is_set (bool): `True` requires a non-empty value; `False` requires an empty one.

    For multi-valued fields, `eq` and `in_` match if *any* selected value matches.
    """

    def __init__(self, field, *, eq=_UNSET, in_=None, is_set=None):
        given = sum([eq is not _UNSET, in_ is not None, is_set is not None])
        if given != 1:
            raise TypeError("When() requires exactly one of `eq=`, `in_=`, or `is_set=`")
        if in_ is not None and isinstance(in_, (str, bytes)):
            raise TypeError("When(in_=...) expects a list or tuple of values, not a single string")
        self.field = field
        self.eq = eq
        self.in_ = list(in_) if in_ is not None else None
        self.is_set = is_set

    def to_dict(self):
        data = {"field": self.field}
        if self.eq is not _UNSET:
            data["eq"] = self.eq
        elif self.in_ is not None:
            data["in"] = self.in_
        else:
            data["is_set"] = self.is_set
        return data

    def matches(self, data):
        value = _normalize_value(data.get(self.field))
        if self.is_set is not None:
            present = value not in (None, [])
            return present is self.is_set
        values = value if isinstance(value, list) else [value]
        if self.eq is not _UNSET:
            return any(_equals(item, self.eq) for item in values)
        return any(_equals(item, option) for item in values for option in self.in_)

    def field_names(self):
        return {self.field}


class _Combinator(Condition):
    key = None

    def __init__(self, *conditions):
        if not conditions:
            raise TypeError(f"{self.__class__.__name__}() requires at least one condition")
        for condition in conditions:
            if not isinstance(condition, Condition):
                raise TypeError(f"{self.__class__.__name__}() arguments must be Condition instances")
        self.conditions = conditions

    def to_dict(self):
        return {self.key: [condition.to_dict() for condition in self.conditions]}

    def field_names(self):
        names = set()
        for condition in self.conditions:
            names |= condition.field_names()
        return names


class AnyOf(_Combinator):
    """True if any of the given conditions is true."""

    key = "any"

    def matches(self, data):
        return any(condition.matches(data) for condition in self.conditions)


class AllOf(_Combinator):
    """True only if all of the given conditions are true."""

    key = "all"

    def matches(self, data):
        return all(condition.matches(data) for condition in self.conditions)


class Not(Condition):
    """Inverts a condition."""

    def __init__(self, condition):
        if not isinstance(condition, Condition):
            raise TypeError("Not() argument must be a Condition instance")
        self.condition = condition

    def to_dict(self):
        return {"not": self.condition.to_dict()}

    def matches(self, data):
        return not self.condition.matches(data)

    def field_names(self):
        return self.condition.field_names()


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


class Omitted:
    """
    Explicitly keeps the named form fields off the page.

    Unlisted fields are never dropped (they fall into the trailing panel), so a field that must exist on the form
    but must not be rendered — typically one the form derives in `clean()` from other inputs — is declared here.
    The fields are claimed, so they neither render nor land in the trailing panel; they are not submitted, so the
    form receives them as empty, exactly as when a template simply left them out.
    """

    def __init__(self, *names):
        if not names or any(not isinstance(name, str) for name in names):
            raise TypeError("Omitted() requires one or more field names")
        self.names = tuple(names)

    def __repr__(self):
        return f"Omitted({', '.join(map(repr, self.names))})"


class FieldGroup:
    """One tab within a `TabbedGroups` item. A declaration only; not itself a component."""

    def __init__(self, label, items=()):
        self.label = label
        self.items = tuple(items)

    def __repr__(self):
        return f"FieldGroup({self.label!r}, {self.items!r})"


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
        visible_if (Condition, optional): Client-side gate, also enforced on the server during validation. When
            false, the component's wrapper is hidden and its controls are disabled.
        clear_on_hide (bool, optional): When hidden by `visible_if`, also clear the controls' values.
        attrs (dict, optional): Extra HTML attributes for the component's wrapper element.
        weight (int, optional): Relative ordering among top-level panels. Items inside a panel are ordered
            positionally and ignore weight. Top-level panels without an explicit weight receive one from their
            position in `Meta.fieldsets`.
        required_permissions (list, optional): Permissions the user must hold for the component to render.

    `deferred_render` is not supported: a deferred panel's fields would be absent from the DOM at submit time.
    """

    attrs = None
    clear_on_hide = False
    deferred_render = False
    label = None
    render_if = None
    template_path = None
    visible_if = None

    def __init__(self, **kwargs):
        if kwargs.pop("deferred_render", False):
            raise TypeError(
                "deferred_render is not supported by form components; "
                "a deferred panel's fields would be missing from the DOM when the form is submitted."
            )
        kwargs.setdefault("weight", 0)
        super().__init__(**kwargs)
        if self.visible_if is not None and not isinstance(self.visible_if, Condition):
            raise TypeError("visible_if must be a Condition instance (When, AnyOf, AllOf, Not)")
        if self.render_if is not None and not (isinstance(self.render_if, str) or callable(self.render_if)):
            raise TypeError("render_if must be a dotted-path string or a callable")
        if self.attrs is not None and not isinstance(self.attrs, dict):
            raise TypeError("attrs must be a dict")
        if not isinstance(self.clear_on_hide, bool):
            raise TypeError("clear_on_hide must be a boolean")
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

    @property
    def media(self):
        """Media declared on this component via an inner `class Media`."""
        definition = getattr(self, "Media", None)
        return Media(definition) if definition is not None else Media()

    # --- rendering --------------------------------------------------------------------------------------------

    def should_render(self, context):
        if not super().should_render(context):
            return False
        return evaluate_render_if(self.render_if, context)

    def wrapper_attrs(self):
        """HTML attributes for this component's wrapper element, including the `visible_if` serialization."""
        attrs = dict(self.attrs or {})
        if self.visible_if is not None:
            attrs["data-nb-visible-if"] = self.visible_if.to_json()
            if self._initially_hidden():
                # Rendered hidden from the start, so nothing flashes before the client runtime runs and a stored
                # value that no longer satisfies its condition is hidden rather than wiped on load.
                attrs["hidden"] = True
        if self.clear_on_hide:
            # Emitted independently of `visible_if`: a field may ask to be cleared when an enclosing panel hides it.
            attrs["data-nb-clear-on-hide"] = "true"
        return attrs

    def _initially_hidden(self):
        """Whether `visible_if` is false for the values the form currently shows (submitted data, else initial)."""
        if self.visible_if is None or self.form is None:
            return False
        names = [name for name in self.visible_if.field_names() if name in self.form.fields]
        values = {name: self.form[name].value() for name in names}
        return not self.visible_if.matches(values)

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
        template_path (str, optional): Render the row from this template instead of the standard one. The template
            receives `field` (the bound field), `form` and `component`. For rows whose markup genuinely differs
            (an input group with a dropdown, a tabbed editor around one field).
        as_hidden (bool, optional): Render the field as a hidden input, in place, regardless of its widget.
        optional (bool, optional): Silently skip this item if the form has no such field, for fields a form adds
            or removes conditionally in `__init__`.
    """

    as_hidden = False
    container_class = None
    full_width = False
    help_text = None
    name = None
    optional = False

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
        if self.as_hidden:
            return bound_field.as_hidden()
        if bound_field.is_hidden:
            # Hidden fields are emitted once by the layout itself, outside of any panel.
            return ""
        if self.template_path:
            return self._wrap(
                render_component_template(
                    self.template_path, context, field=bound_field, form=self.form, component=self
                )
            )
        extra = get_render_field_context(
            context.get("request"),
            bound_field,
            container_class=self.container_class,
            full_width=self.full_width,
        )
        return self._wrap(render_component_template("utilities/render_field.html", context, **extra))


class StaticField(FormComponent):
    """
    A read-only label/value row that is not a form field at all.

    Args:
        label (str): The row label.

    Keyword Args:
        attribute (str, optional): Dotted attribute path resolved against the object being edited (the `obj` in
            the render context, falling back to the form's `instance`). When that yields nothing and the form has a
            field of the same name, the field's current value is shown instead, so a value the view passes as
            `initial` (a hidden `term_side`, say) reads correctly on a create page. Model instances are hyperlinked.
        value (optional): A literal value to display instead of resolving `attribute`.
        template_path (str, optional): Custom template; receives `label`, `value` and `required`.
        required (bool, optional): Style the label as required.
    """

    attribute = None
    required = False
    template_path = "components/form/static_field.html"
    value = None

    def __init__(self, label, **kwargs):
        kwargs["label"] = label
        super().__init__(**kwargs)

    def get_value(self, context):
        """Resolve the value to display."""
        if self.attribute is None:
            return self.value
        target = context.get("obj")
        if target is None and self.form is not None:
            target = getattr(self.form, "instance", None)
        value = resolve_dotted_path(self.attribute, target) if target is not None else None
        if value in (None, "") and self.form is not None and self.attribute in self.form.fields:
            # Not on the object (yet): a create page whose view passed the value as form `initial`.
            value = self.form[self.attribute].value()
        return value

    def render(self, context):
        context = _as_context(context)
        if not self.should_render(context):
            return ""
        value = self.get_value(context)
        if isinstance(value, models.Model):
            value = hyperlinked_object(value)
        return self._wrap(
            render_component_template(
                self.template_path, context, label=self.label, value=value, required=self.required
            )
        )


class InlineFields(FormComponent):
    """
    Several fields rendered side by side under one shared label.

    Args:
        *names (str): Names of the form fields, in display order.

    Keyword Args:
        label (str, optional): The shared label. Defaults to the first field's label.
        help_text (str, optional): Help text shown beneath the row. Rendered as HTML, like a field's own help text,
            so pass literal markup only, never a value derived from data.
        widths (tuple, optional): Bootstrap column widths (out of the 9 columns beside the label) for each field.
            Defaults to an even split.
    """

    help_text = None
    names = ()
    template_path = "components/form/inline_fields.html"
    widths = None

    def __init__(self, *names, **kwargs):
        if not names:
            raise TypeError("InlineFields() requires at least one field name")
        if any(not isinstance(name, str) for name in names):
            raise TypeError("InlineFields() field names must be strings")
        kwargs["names"] = tuple(names)
        super().__init__(**kwargs)
        if self.widths is not None:
            if len(self.widths) != len(self.names):
                raise ValueError("InlineFields() widths must have one entry per field")
            if sum(self.widths) > 9:
                raise ValueError("InlineFields() widths must sum to at most 9 columns")

    @property
    def field_names(self):
        return self.names

    def bind(self, layout, weight=None):
        bound = super().bind(layout, weight)
        for name in self.names:
            layout.claim(name, bound)
        return bound

    def render(self, context):
        context = _as_context(context)
        if not self.should_render(context):
            return ""
        bound_fields = [self.form[name] for name in self.names]
        widths = self.widths or [9 // len(self.names)] * len(self.names)
        label = self.label if self.label is not None else bound_fields[0].label
        return self._wrap(
            render_component_template(
                self.template_path,
                context,
                label=label,
                help_text=self.help_text,
                fields=list(zip(bound_fields, widths)),
                required=any(bound_field.field.required for bound_field in bound_fields),
                errors=[error for bound_field in bound_fields for error in bound_field.errors],
            )
        )


class IncludedTemplate(FormComponent):
    """
    A block of markup that is not a form field, rendered from a template at this position in the panel.

    It is the `{% include %}` of a layout: use it for a hint, an alert, a container some script fills in, or a
    hidden copy of a value. Anything that *is* a field has a better home — `FormField(name, template_path=...)`
    for a field with unusual row markup, `StaticField` for a read-only value.

    The template receives the page's render context (`obj`, `editing`, `request`, `perms`, ...) plus `form`.

    It claims no fields. If the template renders a form field itself (`{{ form.x }}`), that field is still unclaimed
    and will also be rendered in the trailing panel; name the field in a `FormField` instead, or `Omitted` if the
    template's copy is the only one wanted.

    Markup or JavaScript rendered here may never be the sole enforcer of a data rule; if a value must be
    constrained, do it in the form's `clean()` as well.

    Args:
        template_path (str): Path to the template to render.
    """

    def __init__(self, template_path, **kwargs):
        if not isinstance(template_path, str) or not template_path:
            raise TypeError("IncludedTemplate() requires a template path")
        kwargs["template_path"] = template_path
        super().__init__(**kwargs)

    def render(self, context):
        context = _as_context(context)
        if not self.should_render(context):
            return ""
        return self._wrap(render_component_template(self.template_path, context, form=self.form, component=self))


class TabbedGroups(FormComponent):
    """
    Two or more groups of fields under tabs, for mutually exclusive ways of filling in the same thing.

    The initially active tab is the first one whose fields carry a value, falling back to the first tab.

    Args:
        *groups (FieldGroup): The tabs. A `("Label", (items...))` tuple is accepted as shorthand for a `FieldGroup`.

    Keyword Args:
        clear_inactive (bool, optional): Treat the tabs as mutually exclusive: switching tabs clears what was
            entered on the tab being left, and on the server the inactive tabs' fields are cleared rather than merely
            ignored. Default `False` (the inactive tabs' submitted values are ignored, existing values kept).
    """

    clear_inactive = False
    groups = ()
    template_path = "components/form/tabbed_groups.html"

    def __init__(self, *groups, **kwargs):
        if len(groups) < 2:
            raise TypeError("TabbedGroups() requires at least two groups")
        coerced = []
        for group in groups:
            if isinstance(group, FieldGroup):
                coerced.append(group)
            elif isinstance(group, (tuple, list)) and len(group) == 2 and isinstance(group[0], str):
                coerced.append(FieldGroup(group[0], group[1]))
            else:
                raise TypeError(
                    f"TabbedGroups() groups must be FieldGroup instances or (label, items) tuples; got {group!r}"
                )
        kwargs["groups"] = tuple(coerced)
        super().__init__(**kwargs)
        self._bound_groups = ()

    @property
    def field_names(self):
        return tuple(name for _, items in self._bound_groups for item in items for name in item.field_names)

    def _bind_children(self, layout):
        self._bound_groups = tuple(
            (group.label, tuple(bound for item in group.items for bound in layout.bind_item(item)))
            for group in self.groups
        )

    def iter_components(self):
        yield self
        for _, items in self._bound_groups:
            for item in items:
                yield from item.iter_components()

    @property
    def active_tab_input_name(self):
        """
        Name of the hidden input that records which tab is active.

        The browser keeps it current as the user switches tabs; on submit the server uses it to treat the fields of
        the inactive tabs as hidden (not required, submitted values ignored). Absent from the submitted data, no
        tab is treated as inactive.
        """
        return self.form.add_prefix(f"_nb_active_tab_{self.component_id[:10]}")

    def _submitted_active_index(self, data):
        if not data:
            return None
        try:
            index = int(data.get(self.active_tab_input_name))
        except (TypeError, ValueError):
            return None
        return index if 0 <= index < len(self._bound_groups) else None

    def _active_index(self):
        """The initially active tab: the submitted one, else the first whose fields carry a value, else the first."""
        submitted = self._submitted_active_index(self.form.data if self.form.is_bound else None)
        if submitted is not None:
            return submitted
        for index, (_, items) in enumerate(self._bound_groups):
            for item in items:
                for name in item.field_names:
                    if _normalize_value(self.form[name].value()) not in (None, []):
                        return index
        return 0

    def inactive_field_names(self, data):
        """Names of the fields in every tab other than the one `data` marks as active; empty when that is unknown."""
        active = self._submitted_active_index(data)
        if active is None:
            return ()
        return tuple(
            name
            for index, (_, items) in enumerate(self._bound_groups)
            if index != active
            for item in items
            for name in item.field_names
        )

    def render(self, context):
        context = _as_context(context)
        if not self.should_render(context):
            return ""
        prefix = (self.form.auto_id or "id_%s").replace("%s", "").strip("_") or "id"
        id_base = f"{prefix}-nbtab-{self.component_id[:10]}"
        active = self._active_index()
        tabs = []
        for index, (label, items) in enumerate(self._bound_groups):
            body = format_html_join("", "{}", ((item.render(context),) for item in items))
            tabs.append(
                {
                    "id": f"{id_base}-{index}",
                    "label": label,
                    "body": body,
                    "active": index == active,
                }
            )
        return self._wrap(
            render_component_template(
                self.template_path,
                context,
                tabs=tabs,
                active_index=active,
                active_tab_input_name=self.active_tab_input_name,
                clear_inactive=self.clear_inactive,
            )
        )


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


class FormSetPanel(FormPanel):
    """
    A card containing a formset that the *view* constructed, rendered as a table of rows with an "Add another"
    button and a delete button per row.

    Constructing, validating and saving the formset remain the view's responsibility. The panel renders the rows
    and initializes `jquery.formset.js` on them (through `js/formset_panel.js`, shipped via its `Media`), so the
    page template needs no `javascript` block for it. Rows carry the `formset_row-<prefix>` class.

    When the panel is hidden by `visible_if`, the browser reports zero forms in the formset's management inputs, so
    the view constructs an empty formset and existing rows are left untouched (neither saved nor deleted). A formset
    with `validate_min` would fail validation while hidden; do not combine the two.

    Args:
        label (str, optional): The card header.
        context_key (str): Key under which the formset is found in the render context.

    Keyword Args:
        add_label (str, optional): Noun for the "Add another ..." button. Defaults to the formset model's
            `verbose_name`, else the panel label.
        keep_field_values (str, optional): CSS selector of inputs that keep their initial value in a newly added row
            instead of being blanked (e.g. `'input[type="number"]'` so a new choice starts with the default weight).
        row_template_path (str, optional): Custom template for the table; receives `formset`, `add_label`,
            `keep_field_values` and `component`.
    """

    # NB-FIELDSETS-REVIEW[js-media] (temporary marker, delete before merge): `add_label`, `keep_field_values`, the
    # `Media` declaration and `get_add_label()` are new; the seven templates that used to carry the
    # `$('.formset_row-...').formset({...})` block were reduced to shims.
    add_label = None
    context_key = None
    keep_field_values = None
    row_template_path = None
    body_template_path = "components/form/formset_body.html"

    class Media:
        js = ["js/formset_panel.js"]

    def __init__(self, label=None, context_key=None, **kwargs):
        if not isinstance(context_key, str) or not context_key:
            raise TypeError("FormSetPanel() requires a context_key naming the formset in the render context")
        kwargs["context_key"] = context_key
        super().__init__(label, (), **kwargs)

    @property
    def has_content(self):
        """Whether the panel would render anything; only known at render time, when the formset is in context."""
        return True

    def get_add_label(self, formset):
        """Noun for the "Add another ..." button."""
        if self.add_label:
            return self.add_label
        model = getattr(formset, "model", None)
        if model is not None:
            return capfirst(model._meta.verbose_name)
        return self.label or "row"

    def render(self, context):
        context = _as_context(context)
        if not self.should_render(context):
            return ""
        formset = context.get(self.context_key)
        if formset is None:
            logger.warning("FormSetPanel: no formset found in the render context under %r", self.context_key)
            return ""
        body = render_component_template(
            self.row_template_path or self.body_template_path,
            context,
            formset=formset,
            add_label=self.get_add_label(formset),
            keep_field_values=self.keep_field_values,
            component=self,
        )
        return self.render_card(context, body)


#
# Resolution
#


def _coerce_tabs_shorthand(label, spec):
    """The nautobot-app-floor-plan `("Label", {"tabs": ((label, items), ...)})` form: a panel holding one TabbedGroups."""
    unknown = set(spec) - {"tabs"}
    if unknown:
        raise TypeError(
            f"Unsupported fieldset options {sorted(unknown)} for panel {label!r}; only 'tabs' is recognized"
        )
    return FormPanel(label, items=(TabbedGroups(*spec["tabs"]),))


def _coerce_toplevel(entry):
    """Apply top-level shorthand: `("Label", (...))` and the floor-plan `("Label", {"tabs": ...})` form."""
    if isinstance(entry, (FormPanel, Contributed)):
        return entry
    if isinstance(entry, (tuple, list)) and len(entry) == 2 and isinstance(entry[0], (str, type(None))):
        label, spec = entry
        if isinstance(spec, dict):
            return _coerce_tabs_shorthand(label, spec)
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
    if isinstance(item, (FormComponent, Contributed, Omitted)):
        return item
    if isinstance(item, FieldGroup):
        raise TypeError("FieldGroup is only valid inside TabbedGroups")
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
        if isinstance(item, Omitted):
            return self._claim_omitted(item)
        if isinstance(item, FormField) and item.optional and item.name not in self.form.fields:
            return []
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

    def _claim_omitted(self, item):
        """An `Omitted(...)` item: claim the fields so nothing else renders them, and render nothing."""
        for name in item.names:
            self.claim(name, item)
        return []

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

    @property
    def media(self):
        """Aggregate `Media` declared on every component in the layout."""
        media = Media()
        for component in self.iter_components():
            media += component.media
        return media

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

    Exposes `layout` (the resolved `FormLayout`, computed on first access), `has_declared_layout` (whether this form
    class declares any fieldsets), and extends `media` with the media declared by layout components.

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

    @property
    def media(self):
        return super().media + self.layout.media

    # --- server-side enforcement of `visible_if` and inactive tab groups -------------------------------------------

    def _layout_raw_values(self):
        """
        Raw value of every field as the browser sees it: the submitted value (strings, lists, booleans for
        checkboxes), or the initial value for a disabled field, which the browser shows but never submits.
        """
        return {name: self[name].value() for name in self.fields}

    def _layout_hidden_fields(self):
        """
        Determine which fields the layout hides for the submitted data.

        Returns:
            (dict): Field name to a boolean: `True` if the value should be cleared (`clear_on_hide`), `False` if the
                submitted value should merely be ignored.
        """
        if not self.is_bound:
            return {}
        hidden = {}
        self._collect_fields_hidden_by_conditions(hidden)
        self._collect_fields_in_inactive_tabs(hidden)
        return {name: clear for name, clear in hidden.items() if name in self.fields}

    def _collect_fields_hidden_by_conditions(self, hidden):
        """Add to `hidden` every field inside a component whose `visible_if` is false for the submitted values."""
        raw_values = None
        for component in self.layout.iter_components():
            if component.visible_if is None:
                continue
            if raw_values is None:
                raw_values = self._layout_raw_values()
            if component.visible_if.matches(raw_values):
                continue
            # `clear_on_hide` may be set on the hidden component itself or on any field it contains.
            for leaf in component.iter_components():
                if isinstance(leaf, (FormPanel, TabbedGroups)):
                    continue
                for name in leaf.field_names:
                    hidden[name] = hidden.get(name, False) or component.clear_on_hide or leaf.clear_on_hide

    def _collect_fields_in_inactive_tabs(self, hidden):
        """Add to `hidden` every field of a `TabbedGroups` tab other than the one the submission marks active."""
        for component in self.layout.iter_components():
            if isinstance(component, TabbedGroups):
                for name in component.inactive_field_names(self.data):
                    hidden[name] = hidden.get(name, False) or component.clear_inactive

    def _clean_fields(self):
        """
        Enforce the layout's `visible_if` conditions and inactive tab groups while cleaning fields.

        A hidden field is never required, its submitted value is discarded (or replaced by the field's empty value
        when `clear_on_hide` is set), and any validation error it produced is dropped. This mirrors what the browser
        does when it disables the hidden controls, so that the client is never the sole enforcer of the rule.
        """
        hidden = self._layout_hidden_fields()
        # Lift `required` only for this cleaning run (including the clearing below); the field definitions are left
        # as declared afterwards.
        required = {name: self.fields[name].required for name in hidden}
        for name in hidden:
            self.fields[name].required = False
        try:
            super()._clean_fields()
            for name, clear in hidden.items():
                self._errors.pop(name, None)
                if clear:
                    try:
                        self.cleaned_data[name] = self.fields[name].clean(None)
                    except ValidationError:
                        self.cleaned_data.pop(name, None)
                else:
                    self.cleaned_data.pop(name, None)
        finally:
            for name, value in required.items():
                self.fields[name].required = value
