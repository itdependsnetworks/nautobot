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

PERIOD = "2021"


def archived(mirror, period_key=PERIOD):
    """
    The concrete model for one period of `mirror`, with its table created.

    Retained history is one table per period, so a test that wants to read or write retained records has
    to say which period it means. `ensure_period_table` is what rotation calls, so a fixture built this
    way is built the same way real data is.
    """
    from nautobot.extras.models.archive import ensure_period_table

    return ensure_period_table(mirror, period_key)


def clear_archive(*mirrors):
    """
    Drop every period table these mirrors have, so a test starts from nothing.

    Dropping the tables rather than deleting rows, because that is what purging a period does and it
    leaves no partially-populated period behind for the next test to trip over.
    """
    from nautobot.extras.models import ArchiveSegment
    from nautobot.extras.models.archive import drop_period_table

    for mirror in mirrors:
        for period_key in set(ArchiveSegment.objects.values_list("period_key", flat=True)) | {PERIOD}:
            drop_period_table(mirror, period_key)


class ArchiveReadFixtureMixin:
    databases = ["default", CHANGELOG_ARCHIVE]

    def build_period(self, *, period_key=PERIOD, closed=True, rows=1):
        year = int(period_key)
        segment = ArchiveSegment.objects.create(
            model_label="extras.objectchange",
            period_key=period_key,
            label=period_key,
            time_start=datetime(year, 1, 1, tzinfo=dt_timezone.utc),
            time_end=datetime(year + 1, 1, 1, tzinfo=dt_timezone.utc),
            row_count=rows,
            last_rotated_time=datetime(year, 6, 1, tzinfo=dt_timezone.utc),
            is_period_closed=closed,
        )
        archived(ArchivedObjectChange, period_key)  # the table is what opens the period
        for _ in range(rows):
            archived(ArchivedObjectChange, period_key).objects.create(
                id=uuid.uuid4(),
                period_key=period_key,
                time=datetime(year, 6, 1, tzinfo=dt_timezone.utc),
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
