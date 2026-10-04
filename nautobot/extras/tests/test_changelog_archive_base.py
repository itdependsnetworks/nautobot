"""Shared fixture for the retained-history read tests.

One period of every retained model, built the way rotation would build it, so each read test can say
what it is about rather than restating the fixture.
"""

from datetime import datetime, timezone as dt_timezone
import uuid

from django.contrib.contenttypes.models import ContentType

from nautobot.core.constants import CHANGELOG_ARCHIVE, COLD_STORAGE_PERMISSION
from nautobot.extras.choices import (
    ObjectChangeActionChoices,
)
from nautobot.extras.models import (
    ArchivedObjectChange,
    ArchiveSegment,
    ObjectChange,
)
from nautobot.extras.models.archive import warm_model_for

PERIOD = "unbounded"


def archived(mirror, period_key=PERIOD):
    """
    The model holding one period of `mirror`, with its period registered.

    Rotation never writes retained records without registering the period, and the verification jobs read
    that registry to know which periods exist. A fixture that skipped it would leave records no sweep can
    find.
    """
    start, end = (None, None)
    ArchiveSegment.objects.get_or_create(
        model_label=warm_model_for(mirror)._meta.label_lower,
        period_key=period_key,
        defaults={
            "label": period_key,
            "time_start": start,
            "time_end": end,
            "row_count": 0,
            "is_period_closed": True,
        },
    )
    return mirror


def clear_archive(*mirrors):
    """Empty these mirrors and forget their periods, so a test starts from nothing."""
    for mirror in mirrors:
        mirror.objects.all().delete()
        ArchiveSegment.objects.filter(model_label=warm_model_for(mirror)._meta.label_lower).delete()


class ArchiveReadFixtureMixin:
    databases = ["default", CHANGELOG_ARCHIVE]

    def build_period(self, *, period_key=PERIOD, closed=True, rows=1):
        segment, _ = ArchiveSegment.objects.get_or_create(
            model_label="extras.objectchange",
            period_key=period_key,
            defaults={
                "label": period_key,
                "row_count": rows,
                "last_rotated_time": datetime(2021, 6, 1, tzinfo=dt_timezone.utc),
                "is_period_closed": closed,
            },
        )
        for _ in range(rows):
            ArchivedObjectChange.objects.create(
                id=uuid.uuid4(),
                period_key=period_key,
                time=datetime(2021, 6, 1, tzinfo=dt_timezone.utc),
                user_name="alice",
                request_id=uuid.uuid4(),
                action=ObjectChangeActionChoices.ACTION_UPDATE,
                changed_object_type_id=ContentType.objects.get_for_model(ObjectChange).pk,
                changed_object_id=uuid.uuid4(),
                change_context="orm",
                object_repr="Archived Widget",
                object_data={},
            )
        return segment

    def grant_cold_storage(self):
        """Grant the single cold-storage permission through Nautobot's own helper."""
        self.add_permissions(COLD_STORAGE_PERMISSION)
        if hasattr(self.user, "_object_perm_cache"):
            del self.user._object_perm_cache
