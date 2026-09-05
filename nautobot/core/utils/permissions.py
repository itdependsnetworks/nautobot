import re

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError, ValidationError
from django.db.models import Q

#: Token that the permission evaluator replaces with the requesting user at query time.
USER_TOKEN = "$user"  # noqa: S105  # not a secret, a substitution token

#: A permission-policy placeholder occupies a complete JSON value, e.g. `"{{ tenant }}"`.
#: Deliberately distinct from `$user`, which is substituted by the evaluator at a different time.
CONSTRAINT_PLACEHOLDER_PATTERN = re.compile(r"^\{\{\s*([a-z][a-z0-9_]*)\s*\}\}$")


def get_permission_for_model(model, action):
    """
    Resolve the named permission for a given model (or instance) and action (e.g. view or add).

    Args:
        model (Any): A model or instance
        action (str): View, add, change, or delete
    """
    if action not in ("view", "add", "change", "delete"):
        raise ValueError(f"Unsupported action: {action}")

    return f"{model._meta.app_label}.{action}_{model._meta.model_name}"


def resolve_permission(name):
    """
    Given a permission name, return the app_label, action, and model_name components. For example, "dcim.view_location"
    returns ("dcim", "view", "location").

    Args:
        name (str): Permission name in the format `<app_label>.<action>_<model>`
    """
    try:
        app_label, codename = name.split(".")
        action, model_name = codename.rsplit("_", 1)
    except ValueError:
        raise ValueError(f"Invalid permission name: {name}. Must be in the format <app_label>.<action>_<model>")

    return app_label, action, model_name


def resolve_permission_ct(name):
    """
    Given a permission name, return the relevant ContentType and action. For example, "dcim.view_location" returns
    (Location, "view").

    Args:
        name (str): Permission name in the format `<app_label>.<action>_<model>`
    """
    app_label, action, model_name = resolve_permission(name)
    try:
        content_type = ContentType.objects.get(app_label=app_label, model=model_name)
    except ContentType.DoesNotExist:
        raise ValueError(f"Unknown app_label/model_name for {name}")

    return content_type, action


def permission_is_exempt(name):
    """
    Determine whether a specified permission is exempt from evaluation.

    Args:
        name (str): Permission name in the format `<app_label>.<action>_<model>`
    """
    app_label, action, model_name = resolve_permission(name)

    if action == "view":
        if (
            # All models (excluding those in EXEMPT_EXCLUDE_MODELS) are exempt from view permission enforcement
            "*" in settings.EXEMPT_VIEW_PERMISSIONS and (app_label, model_name) not in settings.EXEMPT_EXCLUDE_MODELS
        ) or (
            # This specific model is exempt from view permission enforcement
            f"{app_label}.{model_name}" in settings.EXEMPT_VIEW_PERMISSIONS
        ):
            return True

    return False


def qs_filter_from_constraints(constraints, tokens=None):
    """
    Construct filtered QuerySet from user constraints (tokens).

    Args:
        constraints (dict): User's permissions cached items.
        tokens (dict, optional): user tokens. Defaults to a None.

    Returns:
        (Q): QuerySet filter constructed from the given constraints, possibly empty.
    """
    if tokens is None:
        tokens = {}

    def _replace_tokens(value, tokens):
        if isinstance(value, list):
            return list(map(lambda v: tokens.get(v, v), value))
        return tokens.get(value, value)

    params = Q()
    for constraint in constraints:
        if constraint:
            params |= Q(**{k: _replace_tokens(v, tokens) for k, v in constraint.items()})
        else:
            # permit model level access, constrains are null
            return Q()

    return params


def normalize_constraints(constraints):
    """
    Normalize a stored constraint value to a list of constraint dicts.

    `None`, `{}` and `[]` all mean "no constraint" and normalize to `[{}]` so that
    `qs_filter_from_constraints()` grants model-level access, exactly as it does for a null
    `ObjectPermission.constraints` value.

    Args:
        constraints (dict, list, None): A constraint dict, a list of constraint dicts, or null.

    Returns:
        (list): A non-empty list of dicts.
    """
    if constraints is None or constraints == {} or constraints == []:
        return [{}]
    if isinstance(constraints, dict):
        return [constraints]
    return list(constraints)


def validate_constraints_for_model(model, constraints, *, tokens=None):
    """
    Raise a `ValidationError` if `constraints` is not a filter that `model` can evaluate.

    The filter is constructed (which resolves every lookup path and coerces every value) but not
    executed, so this is cheap enough to call from a model's `clean()`.

    Args:
        model (type): The Django model class the constraints apply to.
        constraints (dict, list, None): A constraint dict or list of constraint dicts.
        tokens (dict, optional): Token substitutions; defaults to `{"$user": None}`.
    """
    if tokens is None:
        tokens = {USER_TOKEN: None}
    if not isinstance(constraints, (dict, list)) and constraints is not None:
        raise ValidationError("Constraints must be a JSON object or a list of JSON objects.")
    constraint_list = normalize_constraints(constraints)
    if not all(isinstance(constraint, dict) for constraint in constraint_list):
        raise ValidationError("Each constraint must be a JSON object.")
    try:
        model.objects.filter(qs_filter_from_constraints(constraint_list, tokens))
    except (FieldError, ValueError, TypeError, ValidationError) as exc:
        message = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        raise ValidationError(f"Invalid filter for {model._meta.label}: {message}") from exc
