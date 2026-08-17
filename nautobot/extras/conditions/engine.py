"""Evaluation engine for the conditions on a Webhook or Job Hook.

A condition row is either a preset chosen from the catalog or a raw Jinja2 expression typed by a
user. Both resolve to a Jinja2 boolean expression evaluated here, which is what guarantees the two
behave identically: one definition of "passed", one behavior when an expression errors.

Nothing here knows what owns the conditions. The engine is handed a list of rows and a payload, so a
Webhook and a Job Hook cannot drift apart in how their conditions behave.

Conditions are evaluated against a frozen payload (see `nautobot.extras.conditions.payload`) and
never touch the ORM, so a delete evaluates exactly like any other event.
"""

from dataclasses import dataclass, field as dataclass_field
from functools import lru_cache
import logging

from django.template import engines
from jinja2 import ChainableUndefined
from jinja2.exceptions import TemplateError

from nautobot.extras.choices import ConditionTypeChoices

logger = logging.getLogger(__name__)

# An upper bound on the compiled-expression cache below. It is written by form and serializer validation
# as well as by dispatch: every distinct expression someone types into a form is compiled, whether or not
# the action is ever saved. Without a bound a process would grow for as long as somebody kept editing.
# Well above the number of expressions any real installation has, so a working set is never evicted.
_MAX_COMPILED_EXPRESSIONS = 1000


class ConditionError(Exception):
    """A condition could not be compiled or evaluated."""


@lru_cache(maxsize=None)
def get_expression_environment():
    """
    Return the sandboxed Jinja2 environment used to compile and evaluate conditions.

    Built once per process, on first use rather than at import: it overlays the shared Jinja environment,
    which is not available until Django has finished configuring its template engines.

    This is an overlay of the environment Nautobot uses for every other user-authored template, so
    conditions get the same filter set (netutils convenience functions, Nautobot's own helpers) that
    webhook body templates get. The overlay changes exactly one thing: undefined values are
    chainable, so `snapshots.postchange.status` on a delete evaluates falsy instead of raising.
    """
    from nautobot.extras.conditions.operators import field_matches
    from nautobot.extras.conditions.payload import event_value, field_value

    environment = engines["jinja"].env.overlay(undefined=ChainableUndefined)
    environment.globals["event_value"] = event_value
    environment.filters["event_value"] = event_value
    # Operator dispatch lives in Python: Jinja cannot pick an operator at runtime, and nesting inline
    # conditionals for nine of them would be unreadable and untestable.
    environment.globals["field_matches"] = field_matches
    # Dotted field lookup, so a preset parameter can name a nested value such as `status.name`.
    environment.globals["field_value"] = field_value
    return environment


@lru_cache(maxsize=_MAX_COMPILED_EXPRESSIONS)
def compile_condition(source):
    """
    Compile `source` to a callable, reusing an earlier compilation of identical source.

    Cached on the source text, so a preset shared by fifty actions compiles once per process and an edited
    expression is simply a different key, so there is no cache to invalidate. Least-recently-used entries
    are evicted past `_MAX_COMPILED_EXPRESSIONS`, and a source that fails to compile is not cached at all,
    because `lru_cache` does not memoize a call that raised.

    A condition is a bare Jinja2 expression with no surrounding delimiters: `data.name == 'x'`, not
    `{{ data.name == 'x' }}`. Jinja2's `compile_expression` parses exactly one expression, so statements
    and macros are a syntax error rather than something the sandbox has to defend against. Newlines are
    allowed; it must be one expression, not one line.

    Raises:
        ConditionError: If `source` is not a valid Jinja2 expression.
    """
    # Caught before compiling: Jinja reports a delimiter as a stray-token syntax error ("expected
    # token ':', got '}'"), which tells the author nothing about what they did wrong.
    for delimiter in ("{{", "{%"):
        if delimiter in source:
            raise ConditionError(
                f"A condition is a bare expression, so remove the `{delimiter}`. "
                f"Write `data.status.name == 'Active'`, not `{{{{ data.status.name == 'Active' }}}}`."
            )
    try:
        return get_expression_environment().compile_expression(source, undefined_to_none=False)
    except TemplateError as exc:
        raise ConditionError(f"Unable to compile expression: {exc}") from exc


def resolve_condition(row):
    """
    Return `(source, parameters)` for a condition row.

    For an expression row the source is the user's own text and there are no parameters. For a
    preset row the source is the catalog's fixed expression and the parameters are the user's form
    values, prefixed with `param_` so they cannot shadow a payload variable.

    Raises:
        ConditionError: If the row is malformed or names a preset that is not registered.
    """
    from nautobot.extras.conditions.presets import get_condition_preset

    if not isinstance(row, dict):
        raise ConditionError(f"Condition row must be a mapping, not {type(row).__name__}.")

    row_type = row.get("type")
    if row_type == ConditionTypeChoices.TYPE_EXPRESSION:
        source = row.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ConditionError("Expression row is missing a `source`.")
        return source, {}

    if row_type == ConditionTypeChoices.TYPE_PRESET:
        preset = get_condition_preset(row.get("preset"))
        if preset is None:
            raise ConditionError(f"Unknown condition preset `{row.get('preset')}`.")
        params = row.get("params") or {}
        if not isinstance(params, dict):
            raise ConditionError(f"Preset `{preset.key}` params must be a mapping.")
        return preset.source, {f"param_{name}": value for name, value in params.items()}

    raise ConditionError(f"Unknown condition row type `{row_type}`.")


@dataclass
class ConditionResult:
    """The outcome of a single condition row."""

    index: int
    row: dict
    passed: bool
    error: str = None

    def as_dict(self):
        return {"index": self.index, "row": self.row, "passed": self.passed, "error": self.error}


@dataclass
class EvaluationResult:
    """The outcome of evaluating one rule against one captured change."""

    scope_matched: bool
    conditions: list = dataclass_field(default_factory=list)
    would_fire: bool = False
    error: str = None

    def as_dict(self):
        return {
            "scope_matched": self.scope_matched,
            "conditions": [condition.as_dict() for condition in self.conditions],
            "would_fire": self.would_fire,
            "error": self.error,
        }


def evaluate_condition(row, payload, index=0):
    """
    Evaluate one condition row against `payload` and return a `ConditionResult`.

    A row passes only when the expression returns something truthy, so `None`, `""`, `0`, and empty
    collections all fail, unless the row is negated. A row that raises fails and records why. It never
    propagates, because one malformed condition must not stop the other rules for the same change.

    A row that errors stays failed even when negated: "this did not evaluate" is not the same claim as
    "this evaluated false", and inverting a broken condition into a pass would fire a rule on a mistake.
    """
    try:
        source, parameters = resolve_condition(row)
        compiled = compile_condition(source)
        result = compiled(**payload, **parameters)
    except ConditionError as exc:
        return ConditionResult(index=index, row=row, passed=False, error=str(exc))
    except Exception as exc:  # pylint: disable=broad-except
        return ConditionResult(index=index, row=row, passed=False, error=f"{type(exc).__name__}: {exc}")

    passed = bool(result)
    # `negate` lives on the row, not on the preset, so one flag covers every preset and raw expressions
    # alike. A negated twin of each preset would multiply the catalog, and would still leave no way to
    # invert an expression without editing its text.
    if isinstance(row, dict) and row.get("negate"):
        passed = not passed
    return ConditionResult(index=index, row=row, passed=passed)


def evaluate_conditions(conditions, payload):
    """
    Evaluate every condition row against `payload` and return a list of `ConditionResult`.

    Every row is evaluated even once one has failed, because the dry-run view needs to show a user
    which rows passed and which did not, not merely the first that stopped the rule.
    """
    return [evaluate_condition(row, payload, index=index) for index, row in enumerate(conditions or [])]


def evaluate(conditions, payload, scope_matched=True):
    """
    Evaluate a webhook's or job hook's conditions against a captured change.

    The action fires only when scope matched and every condition row passed. An action with no
    conditions fires for every in-scope event, which is what makes a scope-only trigger useful, and
    what makes an action with neither scope nor conditions behave exactly as it did before this feature.

    Conditions are evaluated even when scope did not match. Nothing is dispatched either way, and the
    result is what the Test tab reports: returning an empty condition list for an out-of-scope object made
    an action with conditions indistinguishable from one without any. Live dispatch is unaffected, since
    it only calls this once scope has already matched.

    Args:
        conditions (list): The stored condition rows.
        payload (dict): The frozen event payload to evaluate against.
        scope_matched (bool): Whether the object was in scope.

    Returns:
        (EvaluationResult): Per-part verdict.
    """
    results = evaluate_conditions(conditions, payload)
    would_fire = scope_matched and all(result.passed for result in results)
    return EvaluationResult(scope_matched=scope_matched, conditions=results, would_fire=would_fire)
