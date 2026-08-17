"""Scope and conditions: deciding, per change event, whether a Webhook or Job Hook fires.

The pieces here know nothing about which model owns them. A Webhook and a Job Hook both carry a
`scope_filter` and a list of `conditions` (see `ConditionalTriggerMixin`), and both are evaluated by
this one engine, which is what keeps their behaviour identical instead of merely similar.
"""

# PLACEHOLDER: `dry_run` is re-exported here in story 7 (Dry-run: the Test tab and the API endpoints).
from nautobot.extras.conditions.engine import (
    compile_condition,
    ConditionError,
    ConditionResult,
    evaluate,
    evaluate_condition,
    evaluate_conditions,
    EvaluationResult,
)
from nautobot.extras.conditions.payload import (
    build_event_payload,
    build_payload_for_instance,
    build_payload_from_object_change,
    event_value,
    field_value,
)
from nautobot.extras.conditions.presets import (
    ConditionPreset,
    get_condition_preset,
    get_condition_presets,
    PresetParameter,
    register_condition_preset,
)

__all__ = (
    "ConditionError",
    "ConditionPreset",
    "ConditionResult",
    "EvaluationResult",
    "PresetParameter",
    "build_event_payload",
    "build_payload_for_instance",
    "build_payload_from_object_change",
    "compile_condition",
    "evaluate",
    "evaluate_condition",
    "evaluate_conditions",
    "event_value",
    "field_value",
    "get_condition_preset",
    "get_condition_presets",
    "register_condition_preset",
)
