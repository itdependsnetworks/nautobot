"""Decides whether an action that has a scope or conditions should fire for a given change.

Two questions, answered in two different places, for one reason each:

Scope runs in the change-logging signal receivers, while the change is still in flight. Deletes force
that: the dispatch stage runs after the request body has completed, by which point the row is gone and
no query can reach it. The receivers record their verdict on the change context and the dispatch stage
reads it back.

Conditions run here, in the dispatch stage, against the frozen payload. They need no database access,
and a compiled condition costs about ten microseconds, the same order as the Jinja that custom links
already render in the request path.

An action with neither a scope nor conditions never reaches this module: `has_conditional_trigger` is
False and the caller dispatches it exactly as it did before this feature existed.
"""

import contextlib
from copy import deepcopy
import logging

from django.core.cache import cache
import redis.exceptions

from nautobot.core.utils.cache import construct_cache_key
from nautobot.extras.conditions.engine import evaluate

logger = logging.getLogger(__name__)


def scoped_actions_for_model(model, action):
    """
    Return the enabled Webhooks and Job Hooks that watch `model` on `action` **and** have a scope filter.

    Only scoped actions are returned, because only they need a query while the change is in flight. The
    result is cached per model: a change-logging receiver calls this on every save and delete, and the
    common answer (nothing, because no action for this model is scoped) must cost one cache read and no
    queries at all.

    The action filter is applied in Python so that one cache entry serves all three actions.
    """
    from nautobot.extras.models import JobHook, Webhook

    concrete = model._meta.concrete_model
    cache_key = construct_cache_key(
        Webhook.objects,
        method_name="scoped_actions_for_model",
        branch_aware=True,
        model=concrete._meta.label_lower,
    )
    # The cache is an optimisation, never a dependency. This runs inside the change-logging receivers, so
    # letting a cache outage raise here would turn "Redis is down, so webhooks do not fire" into "Redis is
    # down, so no object can be saved at all". On failure fall through to the query and skip the write;
    # correctness is unaffected and the cost is one extra query per save until the cache is back.
    found = None
    with contextlib.suppress(redis.exceptions.ConnectionError):
        found = cache.get(cache_key)

    if found is None:
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(concrete)
        found = [
            item
            for model_class in (Webhook, JobHook)
            for item in model_class.objects.filter(content_types=content_type, enabled=True)
            if item.scope_filter
        ]
        # Invalidated by nautobot.extras.signals.invalidate_scoped_action_cache
        with contextlib.suppress(redis.exceptions.ConnectionError):
            cache.set(cache_key, found, timeout=None)
    return [item for item in found if item.watches_action(action)]


def invalidate_scoped_action_cache():
    """Drop the per-model scoped-action lookup. Called from the Webhook and Job Hook signal receivers."""
    from nautobot.extras.models import Webhook

    with contextlib.suppress(redis.exceptions.ConnectionError):
        cache_key = construct_cache_key(Webhook.objects, method_name="scoped_actions_for_model", branch_aware=True)
        cache.delete_pattern(f"{cache_key}(*)")


def record_scope_matches(change_context, action, instance):
    """
    Record which scoped actions have `instance` in scope, for the dispatch stage to read back.

    Keyed by action as well as by object. One request can produce more than one action for the same
    object, since creating it and then setting its tags is a create followed by an update, and keying on
    the object alone lets the later action's verdict overwrite the earlier one's.
    """
    if change_context is None or instance.pk is None:
        return

    scoped = scoped_actions_for_model(instance._meta.concrete_model, action)
    if not scoped:
        return

    matched = set()
    for item in scoped:
        try:
            if item.matches_scope(instance):
                matched.add(str(item.pk))
        except Exception:  # pylint: disable=broad-except
            # An action whose scope cannot be evaluated must not break the save that triggered it.
            logger.exception(
                "Error evaluating scope for %s `%s`; treating as out of scope.", item._meta.verbose_name, item
            )

    change_context.scope_matches[(str(instance.pk), action)] = matched


def passed_scope(action_object, object_change, change_context):
    """
    Whether `action_object`'s scope matched, according to what the receivers recorded.

    An unscoped action is always in scope. A scoped one is in scope only if the receiver said so, which
    fails closed: if the verdict is missing (no change context, or a path that never recorded one) the
    action stays quiet instead of firing for everything.
    """
    if not action_object.scope_filter:
        return True
    if change_context is None:
        return False
    matched = change_context.scope_matches.get((str(object_change.changed_object_id), object_change.action))
    return bool(matched) and str(action_object.pk) in matched


def should_fire(action_object, object_change, change_context, payload=None):
    """
    Whether `action_object` should fire for `object_change`.

    Args:
        action_object (Webhook | JobHook): The action being considered.
        object_change (ObjectChange): The change that selected it by object type and event.
        change_context (ChangeContext): Carries the scope verdicts recorded by the receivers.
        payload (dict): The frozen event payload. May be None when no action being dispatched has
            conditions, since only conditions read it; one is built here if it turns out to be needed.

    Returns:
        (bool): True if every part passed.
    """
    if not action_object.has_conditional_trigger:
        return True

    if not passed_scope(action_object, object_change, change_context):
        return False

    if not action_object.conditions:
        return True

    if payload is None:
        from nautobot.extras.conditions.payload import build_payload_from_object_change

        payload = build_payload_from_object_change(object_change)

    try:
        # A copy per action. Conditions are expressions, and an expression can call a method on the
        # payload it is given (`data.clear()` is a valid one), so sharing the built payload would let one
        # action's condition change what every later action in this dispatch sees.
        result = evaluate(action_object.conditions, deepcopy(payload))
    except Exception:  # pylint: disable=broad-except
        # A condition that blows up must not take the change, or any other action, down with it.
        logger.exception(
            "%s `%s` could not be evaluated; it will not fire.", action_object._meta.verbose_name, action_object
        )
        return False

    for condition in result.conditions:
        if condition.error:
            logger.error(
                "%s `%s` condition %d errored: %s",
                action_object._meta.verbose_name,
                action_object,
                condition.index + 1,
                condition.error,
            )

    if not result.would_fire:
        logger.debug("%s `%s` did not fire for %s.", action_object._meta.verbose_name, action_object, object_change.pk)
    return result.would_fire
