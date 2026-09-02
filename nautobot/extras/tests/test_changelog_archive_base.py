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
        for _ in range(rows):
            ArchivedObjectChange.objects.create(
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
