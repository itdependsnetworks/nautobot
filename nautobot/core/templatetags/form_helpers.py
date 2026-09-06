from urllib.parse import urlencode

from django import template
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist

from nautobot.core.api.constants import NON_FILTER_QUERY_PARAMS

register = template.Library()


def get_render_field_context(request, field, bulk_nullable=False, container_class=None, full_width=False):
    """
    Build the template context used by `utilities/render_field.html` to render a single bound form field.

    Shared by the `{% render_field %}` template tag and by `nautobot.core.ui.object_form.FormField`, so that both
    rendering paths emit identical markup (embedded create/search buttons, nullable toggles, errors, aria wiring).

    Args:
        request (HttpRequest or None): The current request, if any. Embedded create/search affordances are only
            offered when a request with a user is available.
        field (BoundField): The bound form field to render.
        bulk_nullable (bool): Render the bulk-edit "Set null" checkbox alongside the field.
        container_class (str or None): Extra CSS class for the field's container element.
        full_width (bool): Render the control across the full row instead of the 3/9 label/control split.
    """
    field_instance = getattr(field, "field", None)
    embedded_create = getattr(field_instance, "embedded_create", False)
    embedded_search = getattr(field_instance, "embedded_search", False)
    # We're rendering inside an embedded-action modal flow only when the originating HTMX request
    # came from one of the embedded-action buttons (which set HX-Embedded-Action explicitly).
    # Plain HTMX swaps (e.g. dynamic field updates within a normal form) don't suppress the
    # embedded-action affordances on their fields.
    if request is not None:
        is_embedded = request.headers.get("HX-Embedded-Action", "") in ("create", "search")
        has_embedded_create_permissions = request.user.has_perms(
            getattr(field_instance, "embedded_create_permissions", [])
        )
    else:
        is_embedded = False
        has_embedded_create_permissions = False

    embedded_create_query_params = []
    embedded_search_query_params = []
    field_query_params = getattr(field_instance, "query_params", {})
    for query_param_name, query_param_value in field_query_params.items():
        # If field defines a specific content type(s), use it as initial value in embedded create and search forms.
        if query_param_name in ("content_type", "content_types"):
            # Some `content_types` query params are defined as lists of strings, e.g. `["dcim.location"]`, while others
            # may just be plain strings, e.g. `"dcim.location"`.
            content_types = query_param_value if isinstance(query_param_value, list) else [query_param_value]
            for content_type in content_types:
                try:
                    app_label, model = content_type.split(".")
                    # Need to map content type string to content type ID before passing it as initial form value.
                    content_type_id = ContentType.objects.get(app_label=app_label, model=model).id
                    embedded_create_query_params.append((query_param_name, content_type_id))
                    # For search form, additionally prefix content type param with `initial_` to avoid confusion with
                    # `content_type` param indicating the model of filterset form to render, not related to form values.
                    embedded_search_query_params.append((query_param_name, content_type))
                except (AttributeError, ObjectDoesNotExist, ValueError):
                    pass
        # Directly forward all query params other than `content_type` and `content_types` with a few exceptions - omit
        # non-filter query params because they are irrelevant in the context of create or filter form, and make sure
        # that query param value is not a list or a tuple, and that it is not parametrized (`$`).
        elif (
            query_param_name not in NON_FILTER_QUERY_PARAMS
            and not isinstance(query_param_value, (list, tuple))
            and (not isinstance(query_param_value, str) or not query_param_value.startswith("$"))
        ):
            embedded_create_query_params.append((query_param_name, query_param_value))
            embedded_search_query_params.append((query_param_name, query_param_value))

    embedded_search_content_type = ""
    try:
        embedded_search_content_type = field_instance.queryset.model._meta.label_lower
    except AttributeError:
        pass

    return {
        "field": field,
        "bulk_nullable": bulk_nullable,
        "should_render_embedded_create": embedded_create and not is_embedded and has_embedded_create_permissions,
        "should_render_embedded_search": embedded_search and not is_embedded,
        "embedded_create_query_string": urlencode(embedded_create_query_params),
        "embedded_search_query_string": urlencode(embedded_search_query_params),
        "embedded_search_content_type": embedded_search_content_type,
        "container_class": container_class,
        "full_width": full_width,
    }


@register.inclusion_tag("utilities/render_field.html", takes_context=True)
def render_field(context, field, bulk_nullable=False, container_class=None, full_width=False):
    """
    Render a single form field from template
    """
    return get_render_field_context(
        getattr(context, "request", None),
        field,
        bulk_nullable=bulk_nullable,
        container_class=container_class,
        full_width=full_width,
    )


@register.simple_tag(takes_context=True)
def render_form_layout(context, form, default_label=None, bare=False):
    """
    Render a form according to its resolved layout (`Meta.fieldsets` plus mixin-contributed panels).

    Hidden fields are emitted first, followed by each panel in weight order. Fields not claimed by any panel are
    collected into a trailing panel, so nothing is silently dropped.

    Args:
        form (FormLayoutMixin): A form exposing `layout`.
        default_label (str, optional): Header for the trailing panel when the form declares no panels of its own
            (defaults to the `obj_type` in the render context, then the model's verbose name).
        bare (bool, optional): Render the panels' items only, without cards, for a template that draws its own card
            around the form.
    """
    layout = form.layout
    layout.default_label = default_label
    if bare:
        return layout.render_bare(context)
    return layout.render(context)


@register.simple_tag(takes_context=True)
def render_contributed_panels(context, form, names):
    """
    Render only the named mixin-contributed panels of a form's layout.

    Exists so that templates which still hand-render their fields can include the shared panels (custom fields,
    relationships, notes, dynamic groups, tags) from the same single source of truth as `render_form_layout`.

    Args:
        form (Form): The form; forms without a `layout` render nothing.
        names (str): Comma-separated contributed panel names, e.g. `"custom_fields,relationships,tags"`.
    """
    layout = getattr(form, "layout", None)
    if layout is None:
        return ""
    return layout.render_panels(context, [name.strip() for name in names.split(",") if name.strip()])


@register.inclusion_tag("utilities/render_custom_fields.html")
def render_custom_fields(form):
    """
    Render all custom fields in a form
    """
    return {
        "form": form,
    }


@register.inclusion_tag("utilities/render_relationships.html")
def render_relationships(form):
    """
    Render all relationships in a form
    """
    return {
        "form": form,
    }


@register.inclusion_tag("utilities/render_form.html")
def render_form(form, excluded_fields=None):
    """
    Render an entire form from template and default to skipping over `tags` and `object_note` fields.
    Setting `excluded_fields` to [] prevents skipping over `tags` and `object_note` fields
    in case they are used as Job variables or DynamicGroup filters.
    See:
    https://github.com/nautobot/nautobot/issues/4473
    https://github.com/nautobot/nautobot/issues/4503
    """
    if excluded_fields is None:
        excluded_fields = ["tags", "dynamic_groups", "object_note"]

    return {
        "form": form,
        "excluded_fields": excluded_fields,
    }


@register.filter(name="widget_type")
def widget_type(field):
    """
    Return the widget type
    """
    if hasattr(field, "widget"):
        return field.widget.__class__.__name__.lower()
    elif hasattr(field, "field"):
        return field.field.widget.__class__.__name__.lower()
    else:
        return None
