"""Rotation under a calendar granularity, where a record's own timestamp picks its table.

Inherits the single-period case's fixtures and overrides `CHANGELOG_ARCHIVE_PERIOD` per test, so the two
are exercised against identical records and the only difference is the granularity.
"""

from datetime import datetime, timezone as dt_timezone

from django.db import connections
from django.test import override_settings

from nautobot.core.constants import CHANGELOG_ARCHIVE
from nautobot.extras.models import ArchivedObjectChange, ArchiveSegment
from nautobot.extras.models.archive import period_models_for
from nautobot.extras.tests.test_changelog_archive_base import archived, PERIOD
from nautobot.extras.tests.test_changelog_rotation import ChangelogRotationTestCase


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True, CHANGELOG_WARM_WINDOW_DAYS=90)
class ChangelogRotationCalendarPeriodTestCase(ChangelogRotationTestCase):
    """
    Rotation under a calendar granularity, where a record's own timestamp picks its table.

    Inherits the unbounded case's fixtures and overrides the setting per test, so the two are exercised
    against identical records and the only difference is `CHANGELOG_ARCHIVE_PERIOD`.
    """

    def tearDown(self):
        """Drop the period tables this test created, so the next test starts with none."""
        super().tearDown()
        for model in period_models_for(ArchivedObjectChange):
            if model is not ArchivedObjectChange:
                with connections[CHANGELOG_ARCHIVE].cursor() as cursor:
                    cursor.execute(f'DROP TABLE IF EXISTS "{model._meta.db_table}"')

    @override_settings(CHANGELOG_ARCHIVE_PERIOD="year")
    def test_a_record_is_written_to_its_own_year(self):
        change = self.make_object_change(time=datetime(2021, 7, 15, tzinfo=dt_timezone.utc))

        self.run_job()

        self.assertTrue(archived(ArchivedObjectChange, "2021").objects.filter(pk=change.pk).exists())
        # Not in the unbounded table: a calendar granularity stops writing there entirely.
        self.assertFalse(ArchivedObjectChange.objects.filter(pk=change.pk).exists())

    @override_settings(CHANGELOG_ARCHIVE_PERIOD="year")
    def test_one_batch_spanning_two_years_splits(self):
        """
        A batch is ordered by age, so a period boundary can fall inside it.

        Writing the whole batch to one period would file December's records under the following year,
        where a reader selecting either year would find the wrong set.
        """
        older = self.make_object_change(time=datetime(2020, 12, 31, tzinfo=dt_timezone.utc))
        newer = self.make_object_change(time=datetime(2021, 1, 1, tzinfo=dt_timezone.utc))

        result = self.run_job(batch_size=100)

        self.assertEqual(result, {"extras.ObjectChange": 2})
        self.assertTrue(archived(ArchivedObjectChange, "2020").objects.filter(pk=older.pk).exists())
        self.assertTrue(archived(ArchivedObjectChange, "2021").objects.filter(pk=newer.pk).exists())

    @override_settings(CHANGELOG_ARCHIVE_PERIOD="quarter")
    def test_quarter_granularity_keys_by_quarter(self):
        change = self.make_object_change(time=datetime(2021, 8, 9, tzinfo=dt_timezone.utc))

        self.run_job()

        self.assertTrue(archived(ArchivedObjectChange, "2021-Q3").objects.filter(pk=change.pk).exists())

    @override_settings(CHANGELOG_ARCHIVE_PERIOD="month")
    def test_month_granularity_keys_by_month(self):
        change = self.make_object_change(time=datetime(2021, 8, 9, tzinfo=dt_timezone.utc))

        self.run_job()

        self.assertTrue(archived(ArchivedObjectChange, "2021-08").objects.filter(pk=change.pk).exists())

    @override_settings(CHANGELOG_ARCHIVE_PERIOD="year")
    def test_a_segment_records_the_period(self):
        """The segment row is the only record of which periods exist."""
        change = self.make_object_change(time=datetime(2021, 7, 15, tzinfo=dt_timezone.utc))

        self.run_job()

        segment = ArchiveSegment.objects.get(model_label="extras.objectchange", period_key="2021")
        self.assertEqual(segment.label, "2021")
        self.assertEqual(segment.row_count, 1)
        self.assertEqual(segment.last_rotated_time, change.time)
        self.assertEqual(segment.time_start, datetime(2021, 1, 1, tzinfo=dt_timezone.utc))
        self.assertEqual(segment.time_end, datetime(2022, 1, 1, tzinfo=dt_timezone.utc))

    @override_settings(CHANGELOG_ARCHIVE_PERIOD="year")
    def test_rerunning_leaves_the_count_where_it_was(self):
        """
        `row_count` is read back from the period's table, not added to.

        Counting up per run would double a period's reported size every time rotation re-ran over records
        already written, which is the idempotent case rotation is built around.
        """
        self.make_object_change(time=datetime(2021, 7, 15, tzinfo=dt_timezone.utc))
        self.run_job()
        self.make_object_change(time=datetime(2021, 9, 1, tzinfo=dt_timezone.utc))
        self.run_job()

        segment = ArchiveSegment.objects.get(model_label="extras.objectchange", period_key="2021")
        self.assertEqual(segment.row_count, 2)

    @override_settings(CHANGELOG_ARCHIVE_PERIOD="year")
    def test_periods_are_listed_newest_first_with_unbounded_last(self):
        """
        Ordering is on `time_start`, not on the period key.

        The key is text, and ASCII puts letters above digits, so ordering on it would put `unbounded`
        above `2027` in a list labelled newest first.
        """
        self.make_object_change(time=datetime(2020, 5, 1, tzinfo=dt_timezone.utc))
        self.make_object_change(time=datetime(2022, 5, 1, tzinfo=dt_timezone.utc))
        self.run_job()
        ArchiveSegment.objects.create(model_label="extras.objectchange", period_key=PERIOD, row_count=0)

        keys = list(
            ArchiveSegment.objects.filter(model_label="extras.objectchange").values_list("period_key", flat=True)
        )

        self.assertEqual(["2022", "2020", PERIOD], keys)

    @override_settings(CHANGELOG_ARCHIVE_PERIOD="year")
    def test_the_unbounded_period_is_swept_without_a_segment(self):
        """
        An installation upgraded from the single-period release has rows under `unbounded` and no segment
        row naming it, because that release recorded none. The period is included anyway, which is what
        spares the upgrade a data migration.
        """
        self.assertEqual(0, ArchiveSegment.objects.count())

        models = period_models_for(ArchivedObjectChange)

        self.assertEqual([ArchivedObjectChange], models)
