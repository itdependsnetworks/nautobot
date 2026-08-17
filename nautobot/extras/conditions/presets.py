"""Catalog of built-in condition presets.

A preset is a parameter schema paired with a Jinja2 expression written by a Nautobot developer. It
exists so the common conditions ("this field changed", "this field went from X to Y") need no
expression written by the user at all.

What a user fills in never becomes part of the expression text. Parameters are handed to the
expression as context variables (`param_field`, `param_from`, and so on) at the moment it runs, so a
preset's expression is a constant that compiles exactly once and there is no string assembly
anywhere for a user to inject into.
"""

from dataclasses import dataclass, field as dataclass_field

from django.core.exceptions import ValidationError

from nautobot.extras.conditions.operators import FIELD_OPERATORS
from nautobot.extras.registry import registry

# Parameter kinds. `FIELD` names a field on the watched model, which lets the UI offer a picker
# rather than a free-text box; `STRING` is an arbitrary value to compare against.
PARAM_KIND_FIELD = "field"
PARAM_KIND_STRING = "string"
PARAM_KIND_CHOICE = "choice"


@dataclass(frozen=True)
class PresetParameter:
    """One parameter a preset accepts from the user."""

    name: str
    label: str
    kind: str = PARAM_KIND_STRING
    required: bool = True
    help_text: str = ""
    #: For a `choice` parameter, the accepted `(value, label)` pairs. Empty for any other kind.
    choices: tuple = ()

    def as_dict(self):
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "required": self.required,
            "help_text": self.help_text,
            "choices": [{"value": value, "label": label} for value, label in self.choices],
        }


@dataclass(frozen=True)
class ConditionPreset:
    """A built-in condition type offered by the rule form."""

    key: str
    label: str
    description: str
    source: str
    parameters: tuple = dataclass_field(default_factory=tuple)

    @property
    def params_schema(self):
        """JSON-serializable description of this preset's parameters, for the API and the form."""
        return [parameter.as_dict() for parameter in self.parameters]

    def as_dict(self):
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "params_schema": self.params_schema,
        }

    def clean_params(self, params):
        """
        Validate user-supplied `params` against this preset's schema.

        Raises:
            ValidationError: If a required parameter is missing or empty, or an unknown one is given.
        """
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ValidationError(f"Preset `{self.key}` params must be a mapping.")

        known = {parameter.name for parameter in self.parameters}
        unknown = sorted(set(params) - known)
        if unknown:
            raise ValidationError(
                f"Preset `{self.key}` does not accept parameter(s): {', '.join(unknown)}. "
                f"Accepted: {', '.join(sorted(known)) or 'none'}."
            )

        for parameter in self.parameters:
            value = params.get(parameter.name)
            if parameter.required and (value is None or value == ""):
                raise ValidationError(f"Preset `{self.key}` requires parameter `{parameter.name}`.")
            if value is not None and not isinstance(value, str):
                raise ValidationError(
                    f"Preset `{self.key}` parameter `{parameter.name}` must be a string, not {type(value).__name__}."
                )
            if parameter.choices and value:
                allowed = [choice_value for choice_value, _ in parameter.choices]
                if value not in allowed:
                    raise ValidationError(
                        f"Preset `{self.key}` parameter `{parameter.name}` must be one of: {', '.join(allowed)}."
                    )


def register_condition_preset(preset):
    """
    Register a `ConditionPreset` so the rule form and the API catalog will offer it.

    Registering the same preset object twice is a no-op, so an App whose `ready()` runs more than
    once does not error. Registering a *different* preset under an existing key is a conflict.
    """
    if not isinstance(preset, ConditionPreset):
        raise TypeError(f"{preset} must be an instance of ConditionPreset")
    existing = registry["condition_presets"].get(preset.key)
    if existing is not None:
        if existing == preset:
            return
        raise KeyError(f"A different condition preset is already registered under key `{preset.key}`")
    registry["condition_presets"][preset.key] = preset


def get_condition_preset(key):
    """Return the registered `ConditionPreset` for `key`, or None if there is no such preset."""
    return registry["condition_presets"].get(key)


def get_condition_presets():
    """Return all registered presets, ordered by key."""
    return [registry["condition_presets"][key] for key in sorted(registry["condition_presets"])]


#
# Built-in presets
#

FIELD_TRANSITION = ConditionPreset(
    key="field_transition",
    label="Field transition",
    description="Fires when a field moves from one specific value to another specific value.",
    source=(
        "field_value(snapshots.prechange, param_field) == param_from"
        " and field_value(snapshots.postchange, param_field) == param_to"
    ),
    parameters=(
        PresetParameter(name="field", label="Field", kind=PARAM_KIND_FIELD, help_text="Field to watch."),
        PresetParameter(name="from", label="From", help_text="Value the field must have had before the change."),
        PresetParameter(name="to", label="To", help_text="Value the field must have after the change."),
    ),
)

FIELD_CHANGED = ConditionPreset(
    key="field_changed",
    label="Field changed",
    description="Fires when a field's value changed at all, regardless of what it changed to.",
    source="param_field in (snapshots.differences.added or {})",
    parameters=(PresetParameter(name="field", label="Field", kind=PARAM_KIND_FIELD, help_text="Field to watch."),),
)

FIELD_OPERATOR = ConditionPreset(
    key="field_compare",
    label="Field compare",
    description="Fires when a field compares as chosen against a value after the change.",
    source="field_matches(field_value(data, param_field), param_operator, param_value)",
    parameters=(
        PresetParameter(name="field", label="Field", kind=PARAM_KIND_FIELD, help_text="Field to compare."),
        PresetParameter(
            name="operator",
            label="Operator",
            kind=PARAM_KIND_CHOICE,
            choices=FIELD_OPERATORS,
            help_text="How to compare. Ordering operators compare numerically when both sides are numbers.",
        ),
        PresetParameter(name="value", label="Value", help_text="Value to compare against."),
    ),
)

USER_IS = ConditionPreset(
    key="user_is",
    label="User is",
    description="Fires only when a specific user made the change.",
    source="username == param_username",
    parameters=(
        PresetParameter(name="username", label="Username", help_text="Username that must have made the change."),
    ),
)

USER_IS_NOT = ConditionPreset(
    key="user_is_not",
    label="User is not",
    description="Fires for every user except a specific one. Useful for ignoring an automation account.",
    source="username != param_username",
    parameters=(
        PresetParameter(name="username", label="Username", help_text="Username whose changes should be ignored."),
    ),
)

BUILTIN_CONDITION_PRESETS = (
    FIELD_TRANSITION,
    FIELD_CHANGED,
    FIELD_OPERATOR,
    USER_IS,
    USER_IS_NOT,
)


def register_builtin_condition_presets():
    """Register the presets Nautobot ships with. Called from `ExtrasConfig.ready()`."""
    for preset in BUILTIN_CONDITION_PRESETS:
        register_condition_preset(preset)
