"""Builds the frozen picture of a change that conditions are evaluated against.

Live dispatch and dry-run both build their payload here. That is deliberate: dry-run is only useful
if it predicts what live evaluation does, and the surest way to keep that true is for there to be
one builder rather than two that can drift.

The payload deliberately uses the same variable names as the webhook body-template context, so an
expression that works in one works in the other.
"""

from django.utils import timezone

from nautobot.core.models.utils import serialize_object, serialize_object_v2
from nautobot.extras.choices import ObjectChangeActionChoices

# Keys checked, in order, when reducing a nested object to a single comparable value.
_VALUE_KEYS = ("value", "name", "display", "id")

#: Maps a payload's `event` string back to the `ObjectChangeActionChoices` value it was built from.
#: The payload says "created" because that reads better in a condition; a rule stores "create".
EVENT_TO_ACTION = {label.lower(): value for value, label in ObjectChangeActionChoices.CHOICES}


def event_value(value):
    """
    Reduce a serialized field value to the scalar a condition should compare against.

    An object's serialization records a related object as a nested mapping (`{"id": ..., "name":
    "Active", ...}`) when the newer serializer is in play, and as a bare primary key when falling
    back to the older one. A user writing `status` equals `Active` should not have to know which
    they got, so both are reduced here to the same comparable value.

    Lists are normalized element by element; anything else is returned unchanged.
    """
    if isinstance(value, dict):
        for key in _VALUE_KEYS:
            if key in value:
                return value[key]
        return value
    if isinstance(value, (list, tuple)):
        return [event_value(item) for item in value]
    return value


def field_value(container, path):
    """
    Look up a field by name, following dots into nested values.

    `status` and `status.name` should both work: the first because a related object is reduced to a single
    comparable value by `event_value`, the second because people reasonably expect to reach inside it. A
    plain subscript cannot do the second (`data["status.name"]` looks for a key with a dot in its name),
    so the path is walked a segment at a time.

    Args:
        container (dict): Usually the serialized object, but any mapping will do.
        path (str): A field name, optionally dotted, e.g. `status` or `primary_ip4.address`.

    Returns:
        The value at that path reduced by `event_value`, or None if any segment is missing.
    """
    if not path:
        return None
    current = container
    for segment in str(path).split("."):
        if isinstance(current, dict):
            if segment not in current:
                return None
            current = current[segment]
        else:
            return None
    return event_value(current)


def _serialized_data(object_change):
    """Return the post-change serialization recorded on an ObjectChange, preferring the newer form."""
    data = object_change.object_data_v2
    if data is None:
        data = object_change.object_data
    return data


def build_event_payload(object_change, snapshots):
    """
    Assemble the payload for `object_change`, given snapshots already computed for it.

    Callers that have snapshots in hand should use this; `build_payload_from_object_change` is the
    entry point for callers that do not, since computing snapshots costs a query.
    """
    return {
        "event": dict(ObjectChangeActionChoices)[object_change.action].lower(),
        "timestamp": str(object_change.time),
        "model": object_change.changed_object_type.model,
        "username": object_change.user_name,
        "request_id": str(object_change.request_id),
        "data": _serialized_data(object_change),
        "snapshots": snapshots,
    }


def build_payload_from_object_change(object_change):
    """
    Assemble the payload for `object_change`, computing its snapshots.

    This is how dry-run reconstructs a past event: the snapshots come from the change log rather
    than from a change happening now, so a rule can be tested against something that already
    happened, including a delete, whose object no longer exists.
    """
    return build_event_payload(object_change, object_change.get_snapshots())


def build_payload_for_instance(instance, event=ObjectChangeActionChoices.ACTION_UPDATE, user=None):
    """
    Assemble a payload for a live object, synthesizing an update in which nothing changed.

    Used by dry-run when a user picks an object rather than a change-log entry. Because there is no
    real change to describe, prechange and postchange are both the object as it stands and the
    difference sets are empty, so a rule whose condition requires an actual transition correctly
    reports that it would not fire.
    """
    data = serialize_object_v2(instance)
    if data is None:
        data = serialize_object(instance)
    return {
        "event": dict(ObjectChangeActionChoices)[event].lower(),
        "timestamp": str(timezone.now()),
        "model": instance._meta.model_name,
        "username": getattr(user, "username", "") or "",
        "request_id": "",
        "data": data,
        "snapshots": {
            "prechange": data,
            "postchange": data,
            "differences": {"added": {}, "removed": {}},
        },
    }
