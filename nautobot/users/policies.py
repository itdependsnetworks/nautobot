"""
Renderer for permission policies.

This module is the only place that turns a `PermissionPolicy` and a `PolicyAssignment` into permission
constraints. Permission resolution, the generated-constraints API, preview and the effective-access view
all call it, so they cannot disagree about what a policy grants.

Model imports are deferred inside functions because `nautobot.users.models` imports the placeholder helpers
defined here.
"""

from collections import defaultdict
import copy
from dataclasses import dataclass
import json
import logging

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Q

from nautobot.core.utils.permissions import (
    CONSTRAINT_PLACEHOLDER_PATTERN,
    normalize_constraints,
)
from nautobot.users.choices import PolicyParameterKindChoices

logger = logging.getLogger(__name__)


class PolicyRenderError(Exception):
    """A policy could not be rendered into constraints, for example because a parameter value is missing."""


#
# Placeholders
#


def _walk_strings(value, dict_keys=False):
    """Yield every string found in a JSON structure; include dict keys when `dict_keys` is True."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if dict_keys and isinstance(key, str):
                yield key
            yield from _walk_strings(item, dict_keys=dict_keys)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item, dict_keys=dict_keys)


def extract_placeholders(template):
    """
    Return the set of parameter names referenced as whole-value placeholders in a constraint template.

    Args:
        template (dict, list): A constraint template (dict or list of dicts) containing `{{ name }}` values.
    """
    names = set()
    for text in _walk_strings(template):
        match = CONSTRAINT_PLACEHOLDER_PATTERN.match(text)
        if match:
            names.add(match.group(1))
    return names


def find_malformed_placeholders(template):
    """
    Return strings that look like placeholders but are not whole-value placeholders, plus placeholders used as keys.

    A parameter value must never be embedded in text that is later parsed as a lookup path or JSON, so
    `"prefix-{{ name }}"` and `{"{{ name }}": ...}` are both rejected.
    """
    malformed = []
    if isinstance(template, dict):
        groups = [template]
    elif isinstance(template, list):
        groups = template
    else:
        return malformed
    for group in groups:
        if not isinstance(group, dict):
            continue
        for key in group:
            if isinstance(key, str) and "{{" in key:
                malformed.append(key)
        for text in _walk_strings(list(group.values())):
            if "{{" in text and not CONSTRAINT_PLACEHOLDER_PATTERN.match(text):
                malformed.append(text)
    return malformed


def _substitute(value, values):
    if isinstance(value, str):
        match = CONSTRAINT_PLACEHOLDER_PATTERN.match(value)
        if match is None:
            return value
        name = match.group(1)
        if name not in values:
            raise PolicyRenderError(f"No value supplied for parameter '{name}'.")
        # Values are pk strings or flat lists of them; a shallow copy keeps the rendered lists independent.
        substituted = values[name]
        return list(substituted) if isinstance(substituted, list) else substituted
    if isinstance(value, dict):
        return {key: _substitute(item, values) for key, item in value.items()}
    if isinstance(value, list):
        result = []
        for item in value:
            substituted = _substitute(item, values)
            if isinstance(item, str) and CONSTRAINT_PLACEHOLDER_PATTERN.match(item) and isinstance(substituted, list):
                result.extend(substituted)
            else:
                result.append(substituted)
        return result
    return value


def substitute_placeholders(template, values):
    """
    Replace every whole-value `{{ name }}` placeholder in `template` with `values[name]`.

    Substitution operates on the parsed structure and never on text. A placeholder that is a list element and
    whose value is a list is spliced into the list. Dict keys are never touched. `$user` and any other string
    pass through unchanged.

    Args:
        template (dict, list, None): A constraint template.
        values (dict): Parameter values keyed by parameter name.

    Returns:
        (list[dict]): The rendered constraints, always a non-empty list of dicts.

    Raises:
        PolicyRenderError: If a placeholder names a parameter that has no value.
    """
    return [_substitute(constraint, values) for constraint in normalize_constraints(template)]


#
# Rendering
#


@dataclass
class RenderedObjectPermission:
    """
    One `ObjectPermission`-shaped record: what an administrator would have to create by hand to grant the same access.

    Rules with the same actions and the same rendered constraints share one record with several object types, which
    is how object permissions are normally written.
    """

    name: str
    object_types: list
    actions: list
    constraints: list
    enabled: bool = True

    def as_dict(self):
        return {
            "name": self.name,
            "enabled": self.enabled,
            "object_types": [f"{ct.app_label}.{ct.model}" for ct in self.object_types],
            "actions": list(self.actions),
            "constraints": self.constraints,
        }


def render_as_object_permissions(rules, parameter_values=None, *, name, enabled=True):
    """
    Render `rules` into the smallest set of `ObjectPermission`-shaped records that grants the same access.

    Args:
        rules (iterable[PolicyRule]): The rules, with `content_type` loaded.
        parameter_values (dict, None): Values to substitute. `None` leaves `{{ name }}` placeholders in place so a
            policy can be shown before any assignment exists.
        name (str): Base name for the records; a numeric suffix is added when more than one is needed.
        enabled (bool): Recorded on every record.

    Returns:
        (list[RenderedObjectPermission]): One record per distinct (actions, constraints) pair, object types sorted.

    Raises:
        PolicyRenderError: If `parameter_values` is given and misses a placeholder's value.
    """
    groups = {}
    for rule in rules:
        if parameter_values is None:
            constraints = copy.deepcopy(normalize_constraints(rule.constraint_template))
        else:
            constraints = render_rule_constraints(rule, parameter_values)
        key = (tuple(sorted(rule.actions)), json.dumps(constraints, sort_keys=True, default=str))
        group = groups.setdefault(key, {"actions": list(rule.actions), "constraints": constraints, "object_types": []})
        group["object_types"].append(rule.content_type)
    for group in groups.values():
        group["object_types"].sort(key=lambda ct: (ct.app_label, ct.model))
    ordered = sorted(groups.values(), key=lambda g: [(ct.app_label, ct.model) for ct in g["object_types"]])
    return [
        RenderedObjectPermission(
            name=f"{name} ({index})" if len(ordered) > 1 else name,
            object_types=group["object_types"],
            actions=group["actions"],
            constraints=group["constraints"],
            enabled=enabled,
        )
        for index, group in enumerate(ordered, start=1)
    ]


def rule_content_type(rule):
    """
    The `ContentType` of a `PolicyRule`, from Django's process-wide ContentType cache.

    Rules fetched for permission resolution deliberately do not join or prefetch `content_type`: the cache answers
    without a query, which saves one query per request.
    """
    return ContentType.objects.get_for_id(rule.content_type_id)


def permission_names_for_rule(rule):
    """Return the `app_label.action_model` permission names granted by a `PolicyRule`."""
    object_type = rule_content_type(rule)
    return [f"{object_type.app_label}.{action}_{object_type.model}" for action in rule.actions]


def render_rule_constraints(rule, parameter_values):
    """Render one `PolicyRule` into a list of constraint dicts using `parameter_values`."""
    return substitute_placeholders(rule.constraint_template, parameter_values)


def render_assignment_constraints(assignment):
    """
    Render a `PolicyAssignment` into the same shape that `ObjectPermissionBackend.get_object_permissions()` builds.

    Args:
        assignment (PolicyAssignment): An assignment whose `policy.rules` are (ideally) prefetched.

    Returns:
        (dict[str, list[dict]]): Constraint lists keyed by `app_label.action_model`.

    Raises:
        PolicyRenderError: If the assignment does not supply a value for a placeholder.
    """
    perms = defaultdict(list)
    for rule in assignment.policy.rules.all():
        constraints = render_rule_constraints(rule, assignment.parameter_values or {})
        for permission_name in permission_names_for_rule(rule):
            perms[permission_name].extend(constraints)
    return perms


def get_user_assignments(user, *, prefetch=()):
    """
    Return the enabled `PolicyAssignment` records that apply to `user`, with policies and rules prefetched.

    A user reached through several groups (or directly and through a group) matches an assignment several times;
    duplicates are removed here by primary key instead of with `DISTINCT`, which would make the database compare
    every column including the JSON `parameter_values`. Rule content types are resolved from the ContentType cache
    (see `rule_content_type()`), not prefetched.

    Args:
        user (User): The user.
        prefetch (tuple[str]): Additional `prefetch_related` lookups.

    Returns:
        (list[PolicyAssignment]): Each applicable assignment once, in name order.
    """
    from nautobot.users.models import PolicyAssignment  # avoid circular import

    queryset = (
        PolicyAssignment.objects.filter(Q(users=user) | Q(groups__user=user), enabled=True)
        .select_related("policy")
        .prefetch_related("policy__rules", *prefetch)
    )
    seen = set()
    assignments = []
    for assignment in queryset:
        if assignment.pk not in seen:
            seen.add(assignment.pk)
            assignments.append(assignment)
    return assignments


def derive_policy_permissions(user):
    """
    Build the permissions granted to `user` by enabled policy assignments.

    This is the derivation hook called from `ObjectPermissionBackend`. It costs one query for a user with
    no assignments and two for a user with any (assignments, then their policies' rules). An assignment that
    cannot be rendered is logged and skipped, so a broken assignment never widens access.

    Returns:
        (dict[str, list[dict]]): Same shape as `ObjectPermissionBackend.get_object_permissions()`.
    """
    perms = defaultdict(list)
    for assignment in get_user_assignments(user):
        try:
            rendered = render_assignment_constraints(assignment)
        except PolicyRenderError as exc:
            logger.error("Skipping policy assignment %s (%s): %s", assignment.name, assignment.pk, exc)
            continue
        for permission_name, constraints in rendered.items():
            perms[permission_name].extend(constraints)
    return perms


#
# Parameter values
#


def validate_parameter_values(policy, values):
    """
    Validate and normalize the `parameter_values` of an assignment (or a preview request) against `policy`.

    Args:
        policy (PermissionPolicy): The policy that declares the parameters.
        values (dict): Supplied values keyed by parameter name.

    Returns:
        (dict): Normalized values: lists for `multiple` parameters, scalars otherwise; object primary keys
            as strings (integers for integer primary keys).

    Raises:
        ValidationError: With one message per problem, each naming the parameter.
    """
    if values is None:
        values = {}
    if not isinstance(values, dict):
        raise ValidationError("Parameter values must be a JSON object keyed by parameter name.")

    parameters = {parameter.name: parameter for parameter in policy.parameters.all()}
    errors = []
    normalized = {}

    for name in sorted(set(values) - set(parameters)):
        errors.append(f"'{name}' is not a parameter of policy '{policy.name}'.")

    for name, parameter in parameters.items():
        if name not in values:
            errors.append(f"A value for parameter '{name}' is required.")
            continue
        value = values[name]
        if parameter.multiple:
            if not isinstance(value, list) or not value:
                errors.append(f"Parameter '{name}' accepts multiple values and requires a non-empty list.")
                continue
            items = value
        else:
            if isinstance(value, list):
                errors.append(f"Parameter '{name}' accepts a single value, not a list.")
                continue
            items = [value]

        if parameter.kind == PolicyParameterKindChoices.KIND_STRING:
            if not all(isinstance(item, str) and item != "" for item in items):
                errors.append(f"Parameter '{name}' requires a non-empty string value.")
                continue
            normalized[name] = items if parameter.multiple else items[0]
            continue

        target_model = parameter.target_content_type.model_class() if parameter.target_content_type_id else None
        if target_model is None:
            errors.append(f"Parameter '{name}' references an object type that is not installed.")
            continue
        pk_field = target_model._meta.pk
        coerced = []
        try:
            for item in items:
                pk_value = pk_field.to_python(item)
                coerced.append(pk_value if isinstance(pk_value, int) else str(pk_value))
        except (ValidationError, ValueError, TypeError):
            errors.append(f"Parameter '{name}' requires {target_model._meta.verbose_name} identifiers.")
            continue
        found = set(str(pk) for pk in target_model._default_manager.filter(pk__in=coerced).values_list("pk", flat=True))
        missing = [str(pk) for pk in coerced if str(pk) not in found]
        if missing:
            errors.append(
                f"Parameter '{name}': no {target_model._meta.verbose_name} exists with identifier {', '.join(missing)}."
            )
            continue
        normalized[name] = coerced if parameter.multiple else coerced[0]

    if errors:
        raise ValidationError(errors)
    return normalized
