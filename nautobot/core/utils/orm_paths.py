"""
Introspection and validation of ORM lookup paths (`device__tenant__name`) against Django model metadata.

These helpers back the permission-policy path resolver and the visual constraint editor. They read
`model._meta` only, never serializer or FilterSet fields, because a permission constraint is evaluated as
a queryset filter and must therefore be expressed in terms the ORM understands.

Version 1 deliberately excludes multi-valued relations (many-to-many and reverse relations): a constraint
across one of those returns duplicate rows from `RestrictedQuerySet.restrict()` unless `distinct()` is
applied, and that decision has not been made for all callers.
"""

from collections import deque
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django_filters.utils import get_field_parts

from nautobot.core.constants import FILTER_CHAR_BASED_LOOKUP_MAP, FILTER_NUMERIC_BASED_LOOKUP_MAP
from nautobot.core.models.tree_queries import TreeModel
from nautobot.core.utils.permissions import CONSTRAINT_PLACEHOLDER_PATTERN, permission_is_exempt, USER_TOKEN

#: Maximum number of relations a lookup path may cross (`a__b__c__d` crosses three).
RELATION_PATH_MAX_DEPTH = 3

_TEXT_FIELD_TYPES = (models.CharField, models.TextField, models.SlugField, models.EmailField, models.URLField)
_NUMERIC_FIELD_TYPES = (
    models.IntegerField,
    models.DecimalField,
    models.FloatField,
    models.DateField,
    models.DateTimeField,
    models.TimeField,
    models.DurationField,
)

_TEXT_LOOKUPS = ("exact", "in", *sorted(set(FILTER_CHAR_BASED_LOOKUP_MAP.values()) - {"exact"}))
_NUMERIC_LOOKUPS = ("exact", "in", *sorted(set(FILTER_NUMERIC_BASED_LOOKUP_MAP.values()) - {"exact"}))
_RELATION_LOOKUPS = ("exact", "in")
_BOOLEAN_LOOKUPS = ("exact",)
_JSON_LOOKUPS = ("exact", "contains", "has_key")

#: Every lookup name any of the vocabularies above can produce, plus `isnull`; used to split a constraint
#: key such as `device__tenant__name__icontains` into its path and its lookup.
KNOWN_LOOKUPS = frozenset(
    {*_TEXT_LOOKUPS, *_NUMERIC_LOOKUPS, *_RELATION_LOOKUPS, *_BOOLEAN_LOOKUPS, *_JSON_LOOKUPS, "isnull", "in_tree"}
)

#: Human-readable labels for the lookups offered by the constraint editor.
LOOKUP_LABELS = {
    "exact": "is",
    "iexact": "is (case-insensitive)",
    "in": "is one of",
    "icontains": "contains",
    "istartswith": "starts with",
    "iendswith": "ends with",
    "regex": "matches regex",
    "iregex": "matches regex (case-insensitive)",
    "lt": "less than",
    "lte": "less than or equal to",
    "gt": "greater than",
    "gte": "greater than or equal to",
    "isnull": "is null",
    "in_tree": "is or is within",
    "contains": "contains",
    "has_key": "has key",
}


def lookup_label(lookup):
    """Return the display label for a lookup name, falling back to the name itself."""
    return f"{LOOKUP_LABELS.get(lookup, lookup)} ({lookup})"


@dataclass(frozen=True)
class FieldNode:
    """One node in the field tree of a model, as shown by the constraint editor."""

    name: str
    path: str
    verbose_name: str
    field_type: str
    is_relation: bool
    related_model: str | None
    expandable: bool
    lookups: tuple
    has_choices: bool
    nullable: bool

    def as_dict(self):
        return {
            "name": self.name,
            "path": self.path,
            "verbose_name": self.verbose_name,
            "field_type": self.field_type,
            "is_relation": self.is_relation,
            "related_model": self.related_model,
            "expandable": self.expandable,
            "lookups": list(self.lookups),
            "has_choices": self.has_choices,
            "nullable": self.nullable,
        }


@dataclass(frozen=True)
class RelationHop:
    """One relation crossed by a `PathCandidate`."""

    field: str
    verbose_name: str
    model: str

    def as_dict(self):
        return {"field": self.field, "verbose_name": self.verbose_name, "model": self.model}


@dataclass(frozen=True)
class PathCandidate:
    """A lookup path from a source model to a target model, proposed by `find_relation_paths()`."""

    path: str
    depth: int
    relations: tuple
    lookups: tuple

    def as_dict(self):
        return {
            "path": self.path,
            "depth": self.depth,
            "relations": [hop.as_dict() for hop in self.relations],
            "lookups": list(self.lookups),
        }


@dataclass
class ConstraintRow:
    """One `path lookup value` condition of a constraint, as edited by the constraint editor."""

    path: str
    lookup: str
    value: object
    source: str  # "literal", "parameter" or "user"

    def as_dict(self):
        return {"path": self.path, "lookup": self.lookup, "value": self.value, "source": self.source}


def is_forward_single_valued(field):
    """Return True if `field` is a concrete forward relation that yields at most one related object."""
    return bool(field.is_relation and field.concrete and (field.many_to_one or field.one_to_one))


def is_multi_valued(field):
    """Return True if crossing `field` can multiply rows (many-to-many or reverse relation)."""
    return bool(field.is_relation and (field.many_to_many or field.one_to_many))


def lookups_for_field(field):
    """
    Return the lookup names the constraint editor offers for `field`, restricted to lookups the field supports.

    The vocabulary mirrors the FilterSet lookup maps so the words match what users see in filter forms.
    """
    if field.is_relation or isinstance(field, (models.UUIDField, models.AutoField)) or field.primary_key:
        candidates = _RELATION_LOOKUPS
    elif isinstance(field, models.BooleanField):
        candidates = _BOOLEAN_LOOKUPS
    elif isinstance(field, models.JSONField):
        candidates = _JSON_LOOKUPS
    elif isinstance(field, _NUMERIC_FIELD_TYPES):
        candidates = _NUMERIC_LOOKUPS
    elif isinstance(field, _TEXT_FIELD_TYPES):
        candidates = _TEXT_LOOKUPS
    else:
        candidates = ("exact", "in")

    supported = set(field.get_lookups())
    lookups = [lookup for lookup in candidates if lookup in supported]
    # `in_tree` is provisional (see `InTreeLookup` in core/models/tree_queries.py); drop this branch if it is withdrawn.
    if tree_model_for_field(field) is not None and "in_tree" in supported:
        lookups.insert(2, "in_tree")  # right after exact / in
    if getattr(field, "null", False) and "isnull" in supported:
        lookups.append("isnull")
    return tuple(lookups)


def tree_model_for_field(field):
    """Return the `TreeModel` subclass that `field` references (a FK to one, or its primary key), else None."""
    model = (
        field.related_model if field.is_relation else (field.model if getattr(field, "primary_key", False) else None)
    )
    if model is not None and issubclass(model, TreeModel):
        return model
    return None


def _user_may_traverse(user, related_model):
    """Return True if `user` may expand into `related_model` (None means no permission gate)."""
    if user is None or getattr(user, "is_superuser", False):
        return True
    permission = f"{related_model._meta.app_label}.view_{related_model._meta.model_name}"
    return permission_is_exempt(permission) or user.has_perm(permission)


def enumerate_model_fields(model, *, prefix="", depth=0, user=None, max_depth=RELATION_PATH_MAX_DEPTH):
    """
    Return one level of the field tree for `model`: its concrete fields and forward single-valued relations.

    Many-to-many relations, reverse relations and generic foreign keys are omitted (see module docstring).

    Args:
        model (type): The model whose fields to list.
        prefix (str): Lookup path prefix that reaches `model` from the root model (`""` for the root).
        depth (int): Number of relations already crossed by `prefix`.
        user (User, optional): If given, relations to models the user may not view are not expandable.
        max_depth (int): Relations may be expanded only while `depth < max_depth`.

    Returns:
        (list[FieldNode]): Relations first, then by verbose name.
    """
    nodes = []
    for field in model._meta.get_fields():
        if not getattr(field, "concrete", False) or is_multi_valued(field):
            continue
        if field.name.startswith("_"):  # internal storage such as `_custom_field_data`
            continue
        if field.is_relation and not is_forward_single_valued(field):
            continue
        path = f"{prefix}__{field.name}" if prefix else field.name
        related_model = field.related_model if field.is_relation else None
        expandable = bool(related_model is not None and depth < max_depth and _user_may_traverse(user, related_model))
        nodes.append(
            FieldNode(
                name=field.name,
                path=path,
                verbose_name=str(getattr(field, "verbose_name", field.name)),
                field_type=field.get_internal_type(),
                is_relation=bool(field.is_relation),
                related_model=related_model._meta.label_lower if related_model is not None else None,
                expandable=expandable,
                lookups=lookups_for_field(field),
                has_choices=bool(getattr(field, "choices", None)),
                nullable=bool(getattr(field, "null", False)),
            )
        )
    nodes.sort(key=lambda node: (not node.is_relation, node.verbose_name.lower(), node.name))
    return nodes


def find_relation_paths(source_model, target_model, max_depth=RELATION_PATH_MAX_DEPTH):
    """
    Search forward single-valued relations for every lookup path from `source_model` to `target_model`.

    Args:
        source_model (type): The model the constraint applies to (e.g. `Interface`).
        target_model (type): The model a policy parameter references (e.g. `Tenant`).
        max_depth (int): Maximum number of relations a path may cross.

    Returns:
        (list[PathCandidate]): Shortest paths first, then alphabetical. Empty if no path exists.
            If the two models are the same, a `pk` candidate of depth 0 is included first.
    """
    candidates = []
    if source_model is target_model:
        candidates.append(
            PathCandidate(path="pk", depth=0, relations=(), lookups=lookups_for_field(source_model._meta.pk))
        )

    seen_paths = set()
    queue = deque([(source_model, "", (), frozenset({source_model}))])
    while queue:
        model, prefix, hops, visited = queue.popleft()
        depth = len(hops)
        if depth >= max_depth:
            continue
        for field in model._meta.get_fields():
            if not is_forward_single_valued(field):
                continue
            related_model = field.related_model
            path = f"{prefix}__{field.name}" if prefix else field.name
            hop = RelationHop(
                field=field.name,
                verbose_name=str(getattr(field, "verbose_name", field.name)),
                model=related_model._meta.label_lower,
            )
            if related_model is target_model and path not in seen_paths:
                seen_paths.add(path)
                candidates.append(
                    PathCandidate(path=path, depth=depth + 1, relations=(*hops, hop), lookups=lookups_for_field(field))
                )
                continue
            if related_model in visited:
                continue
            queue.append((related_model, path, (*hops, hop), visited | {related_model}))

    candidates.sort(key=lambda candidate: (candidate.depth, candidate.path))
    return candidates


def validate_lookup_path(model, path):
    """
    Validate that `path` is a lookup path on `model` that crosses only forward single-valued relations.

    Args:
        model (type): The model the path starts from.
        path (str): A `__`-separated lookup path such as `device__tenant__name`. A trailing `pk` is accepted.

    Returns:
        (Field): The terminal model field.

    Raises:
        ValidationError: If any segment is unknown, or the path crosses a multi-valued or generic relation.
    """
    if not isinstance(path, str) or not path:
        raise ValidationError("A lookup path must be a non-empty string.")

    parts = path.split("__")
    trailing_pk = parts[-1] == "pk"
    if trailing_pk:
        parts = parts[:-1]
        if not parts:
            return model._meta.pk

    fields = get_field_parts(model, "__".join(parts))
    if fields is None:
        raise ValidationError(f"'{path}' is not a valid lookup path for {model._meta.label}.")

    for field in fields:
        if is_multi_valued(field):
            raise ValidationError(
                f"'{path}' crosses a multi-valued relation at '{field.name}', which is not supported."
            )
        if field.is_relation and not getattr(field, "concrete", False):
            raise ValidationError(f"'{path}' crosses a generic relation at '{field.name}', which is not supported.")

    terminal = fields[-1]
    if trailing_pk:
        if not terminal.is_relation:
            raise ValidationError(f"'{path}' uses 'pk' after '{terminal.name}', which is not a relation.")
        return terminal.related_model._meta.pk
    return terminal


def split_path_and_lookup(model, key):
    """
    Split a constraint key such as `device__tenant__name__icontains` into `("device__tenant__name", "icontains")`.

    A trailing segment is treated as a lookup only when it is a known lookup name and the remaining path is a
    valid lookup path; otherwise the whole key is the path and the lookup is `exact`.

    Returns:
        (tuple[str, str]): `(path, lookup)`.
    """
    parts = key.split("__")
    if len(parts) > 1 and parts[-1] in KNOWN_LOOKUPS:
        candidate_path = "__".join(parts[:-1])
        try:
            validate_lookup_path(model, key)
        except ValidationError:
            # The whole key is not a field path, so the trailing segment must be the lookup (whether or not the
            # remaining path is valid; the caller reports an invalid path with the lookup already stripped).
            return candidate_path, parts[-1]
        try:
            validate_lookup_path(model, candidate_path)
        except ValidationError:
            return key, "exact"  # e.g. a field that happens to be named like a lookup
        return candidate_path, parts[-1]
    return key, "exact"


def _value_source(value):
    if value == USER_TOKEN:
        return "user"
    if isinstance(value, str) and CONSTRAINT_PLACEHOLDER_PATTERN.match(value):
        return "parameter"
    return "literal"


def constraint_to_rows(model, constraint):
    """
    Convert a stored constraint into editor rows, or return `None` if the editor cannot represent it.

    Args:
        model (type): The model the constraint applies to.
        constraint (dict, list, None): A constraint dict (all conditions must match) or a list of dicts
            (any dict may match).

    Returns:
        (list[list[ConstraintRow]] | None): One inner list per "any of" group. `None` when any key is not a
            valid single-valued lookup path, or any value is a nested structure the editor cannot show.
    """
    if constraint is None or constraint == {} or constraint == []:
        return [[]]
    groups = constraint if isinstance(constraint, list) else [constraint]
    rows_by_group = []
    for group in groups:
        if not isinstance(group, dict):
            return None
        rows = []
        for key, value in group.items():
            if not isinstance(key, str) or isinstance(value, dict):
                return None
            path, lookup = split_path_and_lookup(model, key)
            try:
                terminal = validate_lookup_path(model, path)
            except ValidationError:
                return None
            if lookup not in terminal.get_lookups():
                return None
            rows.append(ConstraintRow(path=path, lookup=lookup, value=value, source=_value_source(value)))
        rows_by_group.append(rows)
    return rows_by_group


def rows_to_constraint(groups):
    """
    Convert editor rows back into a stored constraint.

    Args:
        groups (list[list[ConstraintRow]]): One inner list per "any of" group.

    Returns:
        (dict | list[dict]): A single dict when there is one group, otherwise a list of dicts.
    """
    constraints = []
    for rows in groups:
        constraint = {}
        for row in rows:
            key = row.path if row.lookup == "exact" else f"{row.path}__{row.lookup}"
            constraint[key] = row.value
        constraints.append(constraint)
    if len(constraints) == 1:
        return constraints[0]
    return constraints


def form_field_for_lookup(field, lookup):
    """
    Build a Django form field whose widget suits `field` and `lookup`, for entering a constraint value.

    Foreign keys render as API-backed selects for the related model; the API URL is derived automatically by
    `DynamicModelChoiceMixin.get_bound_field()`.

    Args:
        field (Field): The terminal model field of a lookup path.
        lookup (str): The lookup that will be applied to the value.

    Returns:
        (forms.Field): An optional form field with no initial value.
    """
    # Imported here because `nautobot.core.forms` imports model utilities and would otherwise form a cycle.
    from django import forms

    from nautobot.core.forms.constants import BOOLEAN_CHOICES
    from nautobot.core.forms.fields import DynamicModelChoiceField, DynamicModelMultipleChoiceField, MultiValueCharField
    from nautobot.core.forms.widgets import DatePicker, DateTimePicker, StaticSelect2, StaticSelect2Multiple

    multiple = lookup == "in"
    if lookup == "isnull" or isinstance(field, models.BooleanField):
        form_field = forms.ChoiceField(choices=BOOLEAN_CHOICES, widget=StaticSelect2())
    elif field.is_relation:
        field_class = DynamicModelMultipleChoiceField if multiple else DynamicModelChoiceField
        form_field = field_class(queryset=field.related_model._default_manager.all())
    elif field.primary_key:
        field_class = DynamicModelMultipleChoiceField if multiple else DynamicModelChoiceField
        form_field = field_class(queryset=field.model._default_manager.all())
    elif getattr(field, "choices", None):
        if multiple:
            form_field = forms.MultipleChoiceField(choices=field.choices, widget=StaticSelect2Multiple())
        else:
            form_field = forms.ChoiceField(choices=[("", "---------"), *field.choices], widget=StaticSelect2())
    elif multiple:
        form_field = MultiValueCharField()
    elif isinstance(field, models.DateTimeField):
        form_field = forms.DateTimeField(widget=DateTimePicker())
    elif isinstance(field, models.DateField):
        form_field = forms.DateField(widget=DatePicker())
    elif isinstance(field, models.DecimalField):
        form_field = forms.DecimalField()
    elif isinstance(field, models.FloatField):
        form_field = forms.FloatField()
    elif isinstance(field, models.IntegerField):
        form_field = forms.IntegerField()
    else:
        form_field = forms.CharField()

    form_field.required = False
    form_field.initial = None
    form_field.widget.attrs.pop("required", None)
    return form_field


def path_targets_user_model(model, path):
    """Return True if `path` on `model` ends at a relation to (or the pk of) the User model, so `$user` applies."""
    try:
        terminal = validate_lookup_path(model, path)
    except ValidationError:
        return False
    user_model = get_user_model()
    if terminal.is_relation:
        return terminal.related_model is user_model
    return bool(terminal.primary_key and terminal.model is user_model)
