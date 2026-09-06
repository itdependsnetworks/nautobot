# Form Layout Framework

+++ 3.3.0

## Introduction

Model forms in Nautobot historically controlled their layout through a hand-written template that overrode the `form` block of `generic/object_create_base.html` purely to group fields into cards. The Form Layout Framework replaces that with a declaration on the form itself: a `fieldsets` attribute on the form's `Meta` class, built from the components in `nautobot.core.ui.object_form` (exported via `nautobot.apps.ui`).

It is the form-side counterpart of the [UI Component Framework](ui-component-framework.md) and shares its base class: every layout component is a `Component` with a `weight`, optional `required_permissions`, and a `should_render()` method.

```python
from nautobot.apps.forms import NautobotModelForm
from nautobot.apps.ui import Contributed, FormField, FormPanel, IncludedTemplate, StaticField


class DeviceForm(NautobotModelForm):
    class Meta:
        model = Device
        fields = [...]
        fieldsets = (
            ("Device", ("name", "role", "status", "secrets_group")),
            FormPanel(
                "Location",
                (
                    "location",
                    "rack_group",
                    "rack",
                    StaticField("Parent bay", attribute="parent_bay.name", render_if="obj.parent_bay"),
                    FormField("face", render_if="not obj.parent_bay"),
                    FormField("position", render_if="not obj.parent_bay"),
                ),
            ),
            ("Hardware", ("manufacturer", "device_type", "serial", "asset_tag")),
            FormPanel(
                "Management",
                (
                    FormField("primary_ip4", render_if="editing"),
                    FormField("primary_ip6", render_if="editing"),
                    IncludedTemplate("dcim/inc/device_primary_ip_hint.html", render_if="not editing"),
                ),
            ),
            Contributed("tenancy"),
            ("Comments", ("comments",)),
        )
```

A form that declares `Meta.fieldsets` is rendered by `{% render_form_layout form %}`; the generic create/edit templates do this automatically, so no template is needed. A form that declares nothing renders exactly as before.

## Declaring a Layout

`Meta.fieldsets` is a tuple of top-level entries. Each entry is one of:

| Entry | Meaning |
|---|---|
| `("Label", ("field_a", "field_b", ...))` | Shorthand for `FormPanel("Label", items)` |
| `("Label", {"tabs": (("Tab A", (...)), ("Tab B", (...)))})` | Shorthand for a panel containing a single `TabbedGroups` (the `nautobot-app-floor-plan` format) |
| `FormPanel(label, items, ...)` | A titled card of items |
| `FormSetPanel(label, context_key=..., add_label=..., keep_field_values=...)` | A card containing a formset that the view constructed, with "Add another" and per-row delete buttons wired up |
| `Contributed(name)` | Pins a mixin-contributed panel (see below) to this position |

Inside a `FormPanel`, `items` may contain:

| Item | Meaning |
|---|---|
| `"field_name"` | Shorthand for `FormField("field_name")` |
| `FormField(name, label=..., help_text=..., full_width=...)` | A single field with the standard label/control row |
| `FormField(name, template_path=...)` | A field rendered from your own row template (receives `field`, `form`, `component`) — for rows whose markup genuinely differs, such as an input group with a dropdown |
| `FormField(name, as_hidden=True)` | A field rendered as a hidden input in place, whatever its widget |
| `FormField(name, optional=True)` | Skipped silently when the form has no such field — for fields a form adds or removes in `__init__` |
| `InlineFields(*names, label=..., widths=...)` | Several fields side by side under one label |
| `StaticField(label, attribute=... or value=...)` | A read-only label/value row that is not a form field |
| `TabbedGroups(FieldGroup(label, items), ..., clear_inactive=False)` | Alternative groups of fields under tabs (see below) |
| `IncludedTemplate(template_path)` | A block of markup that is not a field, rendered from a template (see below) |
| `RemoteFragment(url, watch=(...), include=(...), template_path=...)` | A region the server re-renders over HTMX whenever the watched fields change (see below) |
| `Contributed(name)` | Splices a contributed panel's fields into this panel |
| `Omitted(*names)` | Keeps fields off the page deliberately — for fields the form derives in `clean()` from other inputs |

Panels cannot be nested.

### Tabs

`TabbedGroups` renders its groups under Bootstrap tabs and records the active tab in a hidden input. In the browser the controls of the inactive tabs are disabled, so they neither submit nor feed cross-field query narrowing; on the server (see below) the inactive tabs' fields are treated as hidden. By default their submitted values are *ignored* and an existing object's values kept — right for alternative ways of narrowing down the same selection (the NAT selectors on the IP address form). Pass `clear_inactive=True` when the tabs are mutually exclusive ways of setting *different* fields (a controller runs on a device *or* a redundancy group): switching tabs then clears what was entered on the tab being left, and the server clears the inactive tabs' fields rather than ignoring them.

### Markup that is not a field

Three items render from a template you write. Pick by what the markup *is*:

| The markup is… | Use | The template receives |
|---|---|---|
| a form field whose row looks unusual (an input group with a dropdown, a field inside its own tabs) | `FormField(name, template_path=...)` | `field` (the bound field), `form` |
| a read-only value | `StaticField(label, attribute=..., template_path=...)` | `label`, `value`, `required` |
| anything else — a hint, an alert, a container a script fills in, a hidden copy of a value | `IncludedTemplate(template_path)` | the page context (`obj`, `editing`, `request`, `perms`, …) plus `form` |

`IncludedTemplate` is the `{% include %}` of a layout and claims no fields. That is the one thing to keep in mind: if its template renders a form field itself (`{{ form.x }}`), the layout does not know, so `x` will also appear in the trailing panel. Name the field with a `FormField` (a custom `template_path` if the row needs one), or declare it `Omitted` when the template's copy is the only rendering wanted. A panel whose entire body is bespoke markup is simply a panel with a single `IncludedTemplate` item.

### Markup the server re-renders

When part of a form depends on another field's value in a way the browser cannot compute (the filter fields available for the content types a Custom Field is assigned to, the parameter form of a Secret's provider), declare a `RemoteFragment`. It renders a container carrying the HTMX attributes, and the view supplies an endpoint that returns the container's inner HTML for the current values:

```python
FormPanel(
    "Scope filter",
    (
        RemoteFragment(
            reverse_lazy("extras:customfield_scope_filter_fields"),
            watch=("content_types", "required"),
            template_path="extras/inc/customfield_scope_filter.html",
            attrs={"id": "nb-scope-filter-form-container"},
        ),
    ),
)
```

`watch` names the fields whose `change` triggers a refresh; `include` (defaulting to `watch`) names the fields whose values are sent as query parameters. `template_path` renders the initial content server-side; without it the fragment fetches itself once the page has loaded. After every swap `jsify_form` runs on the container, so Select2 and the other widget behaviours attach to the new content. Select2 widgets take part in `watch` like any other input: the core bundle re-dispatches their jQuery-only change notifications as native `change` events.

### Your own item types

Anything with repeated bespoke markup deserves a small component rather than a row template per use. Subclass `FormPanel` when the panel needs its own script and markup (`SoftwareImagePanel` in `nautobot.dcim.forms` inserts the software image list under `software_version` and ships the script that fills it via `Media`), or `FormComponent` for a row spanning several fields (`OverridableFormField` in `nautobot.extras.forms` renders a Job property beside its `*_override` checkbox, claims both fields in `bind()`, and ships the lock/unlock script via `Media`). Prefer a widget over a layout item when the behaviour belongs to a single control: the circuit speed inputs use the `NumberWithSelect` widget rather than a custom row.

### Resolution Rules

The declaration is resolved into a `FormLayout` on first access of `form.layout`, which happens when the form is rendered. Resolution is deliberately lazy so that every mixin and every subclass `__init__` has finished adding or removing fields; custom fields (`cf_*`), relationships (`cr_*`), `object_note`, `dynamic_groups` and Job variables all exist by then and may be named directly.

1. **Every visible field is claimed exactly once.** Naming a field twice, or naming a field the form does not have, raises `ValueError`.
2. **Unclaimed fields are never dropped.** They are collected into a trailing panel. When the form declares no panels of its own, that panel is the form's main card: it renders first and is labelled with the object type, exactly as the generic template always has. When the form does declare panels, it renders last and is labelled `"Other"`. If you do not want a field rendered, remove it from the form.
3. **Hidden fields** (those with a `HiddenInput` widget) are emitted once, ahead of all panels, regardless of whether a panel names them.
4. **Ordering is by weight.** Entries in `Meta.fieldsets` receive implicit weights 100, 200, 300... unless they set their own. Mixin-contributed panels have fixed default weights (see below) that place them after the form's own panels; `Contributed(name)` at the top level moves one into that slot instead.
5. **Empty panels are not rendered**, whether because they have no fields, because every item's `render_if` was false, or because the user lacks the panel's `required_permissions`.

### Contributed Panels

Form mixins that add fields dynamically declare a `form_panels` class attribute containing `ContributedFieldsPanel` instances. The layout gathers these across the form's MRO and renders whichever of their fields the form actually has and that no explicit entry has claimed.

| Name | Declared by | Fields | Weight |
|---|---|---|---|
| `tenancy` | `TenancyForm` | `tenant_group`, `tenant` | 5100 |
| `custom_fields` | `CustomFieldModelFormMixin` | every `cf_*` field | 5200 |
| `relationships` | `RelationshipModelFormMixin` | every `cr_*` field | 5300 |
| `notes` | `NoteModelFormMixin` | `object_note` (requires `extras.add_note`) | 5400 |
| `dynamic_groups` | `DynamicGroupModelFormMixin` | `dynamic_groups` (requires `extras.add_staticgroupassociation`) | 5500 |
| `tags` | `FormLayoutMixin` | `tags` | 5600 |

Because these arrive from the mixins, a form never needs to list them. Use `Contributed("tenancy")` to reposition the whole panel, or place `Contributed("custom_fields")` inside one of your own panels to splice the fields in. Naming one of the fields explicitly (for example `"tags"` inside your main panel) removes it from the contributed panel.

Your own mixins may contribute panels the same way:

```python
class LocatableModelFormMixin(forms.Form):
    form_panels = (
        ContributedFieldsPanel(
            name="location",
            label="Location",
            fields=("location", "rack_group", "rack"),
            weight=4000,
        ),
    )
```

`fields` may also be a callable taking the form and returning field names, for mixins whose fields are only known at runtime.

## Visibility

Two mechanisms exist, named to carry the difference between them.

### `render_if` (server side)

Evaluated once when the page renders. When false, **no HTML is emitted** for the component. It accepts a dotted path resolved against the render context and tested for truthiness (`"editing"`, `"obj.parent_bay"`), optionally negated by prefixing the word `not` (`"not obj.parent_bay"`), or a callable taking the context. `render_if` is the declarative shorthand for `should_render()`, which components may still override.

Use it for conditions that cannot change without a page load: create versus edit, object state, permissions (prefer `required_permissions` for the latter).

Prefer dotted paths to callables. Component identity (`component_id`) is hashed from JSON-serializable attributes, so two components that differ only by a callable `render_if` would collide; give one an explicit `component_id` if you must use callables.

### `visible_if` (client side, enforced on the server)

A `Condition` describing when the component should be shown based on the *current values* of other fields. The condition is serialized into a `data-nb-visible-if` attribute and re-evaluated by the browser as the user edits. When false, the component's wrapper is hidden and every control inside it is disabled, so hidden fields neither submit nor take part in cross-field query narrowing. Set `clear_on_hide=True` to also clear their values.

```python
from nautobot.apps.ui import AllOf, AnyOf, Not, When

FormField("untagged_vlan", visible_if=When("mode", is_set=True), clear_on_hide=True)
FormField("tagged_vlans", visible_if=When("mode", eq=InterfaceModeChoices.MODE_TAGGED), clear_on_hide=True)
FormPanel("Validation Rules", (...), visible_if=AnyOf(When("type", in_=MIN_MAX_TYPES), When("type", in_=REGEX_TYPES)))
```

The grammar is deliberately small — `When(field, eq=...)`, `When(field, in_=[...])`, `When(field, is_set=True|False)`, combined with `AnyOf`, `AllOf` and `Not` — because it must round-trip to JSON and be evaluable in Python. Anything richer belongs in an HTMX round trip: declare a `RemoteFragment` and let the server re-render that region.

!!! warning "Markup is never the sole enforcer of a data rule"
    Hiding a field in the browser does not constrain what a client may submit. `visible_if` conditions are also evaluated on the server during validation, and any rule you express in an `IncludedTemplate` or custom JavaScript must be enforced in the form's `clean()` as well.

## Media

Any component may declare an inner `class Media` with `css` and `js` lists, using the same semantics as Django widgets. The layout aggregates component media into `form.media`, which the generic templates already emit — so a panel can ship the JavaScript it needs without a template override:

```python
class SoftwareImagePanel(FormPanel):
    class Media:
        js = ["js/software_image_picker.js"]
```

A script shipped this way runs on every page that renders the component, including forms swapped in over HTMX, so it should find its elements by a `data-*` attribute the component renders rather than by a page-specific id, and bind each element once. Scripts that need Select2 to be initialized first (to read a Select2 value, for example) should wait for the `nb-form:load:<obj_type>` event the form dispatches once its widgets are ready; `software_image_picker.js` is the model to copy.

Two framework components ship scripts of their own: `FormSetPanel` initializes `jquery.formset.js` on its rows, and `RemoteFragment` relies on HTMX. Neither needs anything from the page template.

## Migrating a Template

1. Move the card structure from the template's `{% block form %}` into `Meta.fieldsets`.
2. Delete `{% include 'inc/tenancy_form_panel.html' %}` and `{% include 'inc/extras_features_edit_form_fields.html' %}`; the mixins contribute those panels. Use `Contributed("tenancy")` if the Tenancy card sat somewhere other than after your own cards.
3. Replace `{% if editing %}` / `{% if perms... %}` wrappers with `render_if` and `required_permissions`.
4. Replace read-only rows with `StaticField`, hand-written tabs with `TabbedGroups`, formsets with `FormSetPanel`, HTMX-refreshed regions with `RemoteFragment`, and remaining markup with `IncludedTemplate`.
5. Move any `{% block javascript %}` that remains into a `FormPanel` subclass with a `Media` declaration. Show/hide logic becomes `visible_if`; formset initialization and Select2 change bridging are no longer needed at all.
6. If nothing else remains in the template, delete it — unless Apps may `{% extends %}` it, in which case reduce it to a one-line `{% extends 'generic/object_create.html' %}` shim so they keep working (`dcim/device_create.html` is an example).

Templates that still hand-render their fields keep working: `inc/extras_features_edit_form_fields.html` now renders the contributed panels from the same source, so the two paths cannot drift apart.

## Server-Side Enforcement

`FormLayoutMixin` re-evaluates the layout's conditions during validation (`_clean_fields`), against the raw submitted values, so that what the browser hid is not trusted to stay hidden:

- A field hidden by a `visible_if` condition is not required, whatever its field definition says.
- Its submitted value is **ignored** (dropped from `cleaned_data`, leaving an existing object's value untouched), or **cleared** to the field's empty value when `clear_on_hide` is set on the field or on the hidden component enclosing it.
- Any validation error it produced is discarded.

`TabbedGroups` follows the same rule for the fields in its inactive tabs. The client records the active tab in a hidden input (`data-nb-active-tab`) that the component renders; when that input is present in the submission, the other tabs' fields are ignored (or cleared, with `clear_inactive=True`) exactly as hidden fields are. When it is absent (no JavaScript ran), every tab's fields are validated normally.

A `FormSetPanel` hidden by `visible_if` keeps its formset's management inputs enabled but reports zero forms while hidden, so the view can still construct the formset from the submission; the original counts are restored when the panel is shown again.

Conditions are evaluated against the values the browser shows: the submitted value, or the initial value for a disabled field, which the browser displays but never submits.

A consequence worth knowing when writing a form's `clean()`: a rule such as "an access-mode interface may not have tagged VLANs" is no longer reachable through a layout that hides `tagged_vlans` for access mode, because the offending value never arrives in `cleaned_data`. Keep the rule in `clean()` regardless: it still protects other callers of the form (bulk edit forms, scripts) that do not use the layout.

## Jobs

A Job declares `fieldsets` on its `Meta` class over its variable names; `as_form_class()` copies the declaration onto the generated form, where it is resolved exactly like a model form's. Variables not named are still rendered, in a trailing "Other" panel. A job without `fieldsets` renders exactly as before, with `field_order` still ordering the single "Job Data" card.

```python
class ProvisionCircuit(Job):
    provider = ObjectVar(model=Provider)
    circuit_type = ObjectVar(model=CircuitType)
    device = ObjectVar(model=Device)
    dry_run = BooleanVar(default=True)
    commit_message = StringVar(required=False)

    class Meta:
        name = "Provision Circuit"
        fieldsets = (
            ("Circuit", ("provider", "circuit_type")),
            ("Termination", ("device",)),
            FormPanel(
                "Options",
                (
                    "dry_run",
                    FormField("commit_message", visible_if=When("dry_run", eq=False)),
                ),
            ),
        )
```

The layout governs the Job Data region only; the Job Execution and Job Schedule cards are Nautobot's and are not reorderable by a job. The compact job modal (opened from a Job Button) renders variables flat and does not apply `fieldsets`.

The Job Schedule card is itself a small layout: `JobScheduleForm` declares `visible_if` on the schedule name, start time and crontab rows, and `job.html` renders it with `{% render_form_layout schedule_form bare=True %}`. The `bare` option emits the panels' items without card chrome, for a template that draws its own card.

## Limitations

- **One form per layout.** Pages that compose several form objects (component creation's `form` and `model_form`; the job run page's three forms) are laid out per form. A page-level container does not exist yet.
- **Formsets are placed, not managed.** `FormSetPanel` renders a formset the view built and wires up its add/delete buttons; construction, validation and saving stay in the view.
- **Filter forms and bulk-edit forms** do not yet use layouts.
- **Value mirroring** (one field copying another) is not expressible; keep that in JavaScript.
- **Identical `TabbedGroups` declarations on one page** (the same form class rendered twice, on the page and in an embedded-create modal) share element ids, since ids derive from the declaration; the second copy's tabs would drive the first. Give one of them an explicit `component_id`.
- **A stored value that no longer satisfies its `visible_if`** is rendered hidden (the server emits `hidden` on the wrapper) and left alone until the user changes something; `clear_on_hide` acts on transitions the user causes, not on page load.
