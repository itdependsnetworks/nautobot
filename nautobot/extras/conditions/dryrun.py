"""Answers "would this webhook or job hook have fired?" without firing anything.

Dry-run is only useful if it predicts what live evaluation does, so it deliberately reuses both the
payload builder and the engine rather than reimplementing either. The one thing it does differently is
evaluate scope itself: live evaluation decided scope back in the change-logging receiver, whereas
dry-run is asked about an object or a past change after the fact.
"""

import logging

from django.core.exceptions import ValidationError

from nautobot.extras.conditions.engine import evaluate
from nautobot.extras.conditions.payload import build_payload_for_instance, build_payload_from_object_change

logger = logging.getLogger(__name__)


def dry_run(action, *, object_change=None, instance=None):
    """
    Evaluate a Webhook's or Job Hook's scope and conditions against an object or a past change.

    Exactly one of `object_change` or `instance` must be given.

    Against an ObjectChange, the payload is rebuilt from the stored snapshots, so a rule can be tested
    against something that already happened, including a delete, whose object no longer exists. Against
    a live object, the payload describes an update in which nothing changed, so a rule whose condition
    requires a real transition correctly reports that it would not fire.

    Scope is evaluated against the object where one is available. For a delete there is no object left to
    query, so scope is reported as matched and the conditions carry the verdict. That is the same
    position live evaluation is in by the time conditions run.

    Args:
        action (Webhook | JobHook): The action whose scope and conditions are being tested.
        object_change (ObjectChange): A past change to replay.
        instance (Model): A live object to test against.

    Returns:
        (EvaluationResult): Per-part verdict; nothing is dispatched.

    Raises:
        ValidationError: If neither or both of `object_change` and `instance` are given.
    """
    if (object_change is None) == (instance is None):
        raise ValidationError("Provide exactly one of `object_change` or `instance`.")

    if object_change is not None:
        payload = build_payload_from_object_change(object_change)
        target = object_change.changed_object
    else:
        payload = build_payload_for_instance(instance)
        target = instance

    if target is not None:
        scope_matched = action.matches_scope(target)
    else:
        # The object is gone (a delete), so scope cannot be re-queried. Live evaluation had already
        # decided scope before this point, so reporting it as matched keeps dry-run and live in step.
        scope_matched = True

    return evaluate(action.conditions, payload, scope_matched=scope_matched)
