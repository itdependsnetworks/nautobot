"""
How retained history is divided into calendar periods.

Retained history is one table per period. The four mirrors are concrete models whose tables a migration
created, and they are the unbounded period; every other period is a class `period_model_for` generates
from the mirror's abstract base, differing only in `db_table`.

Two properties make that work, and each fails silently if it stops holding:

1. `period_table_name(mirror, "unbounded")` equals the mirror's declared `db_table`. If the two spellings
   drift, reads of the unbounded period address an empty table standing beside the populated one.
2. A period model carries exactly the fields of the mirror, which is what lets the table, filterset,
   views and serializer declare `Meta.model = ArchivedObjectChange` and still be handed any period's rows.

The registry test is here for the same reason: a concrete model is registered by being defined, and a
period model left in `apps.get_models()` turns up in global search, in the searchable-fields artifact,
and in `makemigrations`, which would then propose a migration per period.
"""

from datetime import datetime, timezone as dt_timezone

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import override_settings

from nautobot.core.constants import CHANGELOG_ARCHIVE
from nautobot.core.testing import TestCase
from nautobot.extras.choices import ChangelogArchivePeriodChoices
from nautobot.extras.constants import CHANGELOG_ARCHIVE_MAX_PERIOD_KEY, CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    ArchiveSegment,
)
from nautobot.extras.models.archive import (
    archive_base_of,
    ensure_period_table,
    period_bounds_for,
    period_key_for,
    period_label_for,
    period_model_for,
    period_table_name,
)
from nautobot.extras.registry import registry

MIRRORS = [ArchivedObjectChange, ArchivedJobResult, ArchivedJobLogEntry, ArchivedJobConsoleEntry]


class PeriodModelTestCase(TestCase):
    def test_unbounded_period_is_the_mirror_itself(self):
        """The declared mirror is the unbounded period, so that period needs no generated class."""
        for mirror in MIRRORS:
            with self.subTest(mirror=mirror.__name__):
                self.assertIs(period_model_for(mirror, CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD), mirror)

    def test_unbounded_table_name_matches_the_declared_table(self):
        """
        The name `period_table_name` computes is the name the migration created.

        Asserted for all four mirrors because the two spellings are written in different places: the
        migration states `db_table` per model, and `period_table_name` derives it from the app label and
        model name.
        """
        for mirror in MIRRORS:
            with self.subTest(mirror=mirror.__name__):
                self.assertEqual(
                    period_table_name(mirror, CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD),
                    mirror._meta.db_table,
                )

    def test_period_key_becomes_an_sql_identifier(self):
        """A period key is punctuated for a person to read; a table name is an identifier."""
        self.assertEqual(period_table_name(ArchivedObjectChange, "2024"), "extras_archivedobjectchange_2024")
        self.assertEqual(period_table_name(ArchivedObjectChange, "2024-Q3"), "extras_archivedobjectchange_2024_q3")
        self.assertEqual(period_table_name(ArchivedObjectChange, "2024-07"), "extras_archivedobjectchange_2024_07")

    def test_period_model_has_the_fields_of_its_mirror(self):
        """Identical field lists are what let one filterset and one table serve every period."""
        for mirror in MIRRORS:
            with self.subTest(mirror=mirror.__name__):
                period_model = period_model_for(mirror, "2024-Q3")
                self.assertEqual(
                    [field.name for field in period_model._meta.fields],
                    [field.name for field in mirror._meta.fields],
                )
                self.assertEqual(period_model._meta.ordering, mirror._meta.ordering)
                self.assertNotEqual(period_model._meta.db_table, mirror._meta.db_table)

    def test_period_model_is_cached(self):
        """Two asks for the same period return one class, so instances of it compare as the same model."""
        self.assertIs(
            period_model_for(ArchivedObjectChange, "2024"),
            period_model_for(ArchivedObjectChange, "2024"),
        )

    def test_period_models_do_not_share_index_names(self):
        """
        Each period's indexes are named after its own table.

        Django deep-copies `Meta.indexes` per concrete child for exactly this reason. Were they shared,
        creating the second period's table would fail on a duplicate index name.
        """
        mirror_indexes = {index.name for index in ArchivedObjectChange._meta.indexes}
        period_indexes = {index.name for index in period_model_for(ArchivedObjectChange, "2024")._meta.indexes}
        self.assertTrue(mirror_indexes)
        self.assertEqual(set(), mirror_indexes & period_indexes)

    def test_archive_base_of_resolves_a_period_model(self):
        """Every lookup keyed on a model class goes through this, because a period model equals nothing."""
        self.assertIs(archive_base_of(period_model_for(ArchivedObjectChange, "2024")), ArchivedObjectChange)
        self.assertIs(archive_base_of(ArchivedObjectChange), ArchivedObjectChange)

    def test_period_model_is_recognized_as_retained_history(self):
        """
        The registry holds the four mirrors, so a period model is in it under no key.

        The database router asks this question to decide which connection a read uses. Answering "no" for
        a period model would send it to `default`, where its table does not exist.
        """
        period_model = period_model_for(ArchivedObjectChange, "2024")
        self.assertNotIn(period_model, registry["changelog_archive_models"].values())
        self.assertIn(archive_base_of(period_model), registry["changelog_archive_models"].values())


class PeriodModelRegistryTestCase(TestCase):
    def test_period_models_are_not_in_the_app_registry(self):
        """
        Defining a concrete model registers it, and `period_model_for` takes it back out.

        Left registered, one table of one period of retained history is returned by `apps.get_models()`,
        which is the sweep deciding what is searchable and what `makemigrations` writes migrations for.
        """
        period_model = period_model_for(ArchivedObjectChange, "2024")
        self.assertNotIn(period_model, apps.get_models())
        self.assertIsNone(apps.all_models[period_model._meta.app_label].get(period_model._meta.model_name))

    def test_mirrors_stay_in_the_app_registry(self):
        """The mirrors are ordinary models: their content types and permissions depend on it."""
        for mirror in MIRRORS:
            with self.subTest(mirror=mirror.__name__):
                self.assertIn(mirror, apps.get_models())


class EnsurePeriodTableTestCase(TestCase):
    databases = ["default", CHANGELOG_ARCHIVE]

    def test_unbounded_table_is_not_created_again(self):
        """The migration created it, so this finds it and creates nothing."""
        model = ensure_period_table(ArchivedObjectChange, CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD)
        self.assertIs(model, ArchivedObjectChange)

    def test_calendar_period_table_is_created_once(self):
        """The first write to a period creates its table; later ones find it."""
        connection = connections[CHANGELOG_ARCHIVE]
        model = ensure_period_table(ArchivedObjectChange, "2024")
        self.addCleanup(self._drop_table, model._meta.db_table)
        with connection.cursor() as cursor:
            self.assertIn(model._meta.db_table, connection.introspection.table_names(cursor))
        # Idempotent: a second call over an existing table returns the same model and does not raise.
        self.assertIs(ensure_period_table(ArchivedObjectChange, "2024"), model)

    def test_a_created_period_table_holds_records(self):
        """A period model reads and writes its own table through the archive connection."""
        model = ensure_period_table(ArchivedJobLogEntry, "2024")
        self.addCleanup(self._drop_table, model._meta.db_table)
        model.objects.create(
            period_key="2024",
            job_result_id="00000000-0000-0000-0000-000000000001",
            message="retained",
            created="2024-06-01T00:00:00Z",
        )
        self.assertEqual(1, model.objects.count())
        # The mirror's own table is a different table and is unaffected.
        self.assertEqual(0, ArchivedJobLogEntry.objects.count())

    @staticmethod
    def _drop_table(table_name):
        with connections[CHANGELOG_ARCHIVE].cursor() as cursor:
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')


class PeriodKeyTestCase(TestCase):
    """`period_key_for` is the single definition of which period a record belongs to."""

    def test_unbounded_granularity_ignores_the_timestamp(self):
        for timestamp in (datetime(2020, 1, 1), datetime(2027, 12, 31)):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(
                    CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD,
                    period_key_for(timestamp, ChangelogArchivePeriodChoices.PERIOD_UNBOUNDED),
                )

    def test_year_quarter_and_month_keys(self):
        timestamp = datetime(2024, 8, 9)
        self.assertEqual("2024", period_key_for(timestamp, ChangelogArchivePeriodChoices.PERIOD_YEAR))
        self.assertEqual("2024-Q3", period_key_for(timestamp, ChangelogArchivePeriodChoices.PERIOD_QUARTER))
        self.assertEqual("2024-08", period_key_for(timestamp, ChangelogArchivePeriodChoices.PERIOD_MONTH))

    def test_quarter_boundaries(self):
        """The month a quarter starts and the month it ends give the same key."""
        for month, expected in ((1, "2024-Q1"), (3, "2024-Q1"), (4, "2024-Q2"), (12, "2024-Q4")):
            with self.subTest(month=month):
                self.assertEqual(
                    expected, period_key_for(datetime(2024, month, 1), ChangelogArchivePeriodChoices.PERIOD_QUARTER)
                )

    def test_month_key_is_zero_padded(self):
        """So that keys sort the same as the dates they stand for, and table names are uniform."""
        self.assertEqual("2024-03", period_key_for(datetime(2024, 3, 1), ChangelogArchivePeriodChoices.PERIOD_MONTH))

    def test_granularity_defaults_to_the_setting(self):
        with override_settings(CHANGELOG_ARCHIVE_PERIOD="month"):
            self.assertEqual("2024-08", period_key_for(datetime(2024, 8, 9)))
        with override_settings(CHANGELOG_ARCHIVE_PERIOD="unbounded"):
            self.assertEqual(CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD, period_key_for(datetime(2024, 8, 9)))

    def test_every_offered_granularity_produces_a_key_that_fits(self):
        """
        The key is stored in a column `CHANGELOG_ARCHIVE_MAX_PERIOD_KEY` characters wide.

        A key that overflowed would be truncated on write, and the truncated value would name a different
        period from the table the record was written to.
        """
        for value, _ in ChangelogArchivePeriodChoices.CHOICES:
            with self.subTest(granularity=value):
                key = period_key_for(datetime(2024, 12, 31), value)
                self.assertLessEqual(len(key), CHANGELOG_ARCHIVE_MAX_PERIOD_KEY)


class PeriodBoundsTestCase(TestCase):
    def test_unbounded_has_no_bounds(self):
        """Not a sentinel date: every caller computing with these has to handle the absence."""
        self.assertEqual((None, None), period_bounds_for(CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD))

    def test_year_bounds(self):
        start, end = period_bounds_for("2024")
        self.assertEqual((2024, 1, 1), (start.year, start.month, start.day))
        self.assertEqual((2025, 1, 1), (end.year, end.month, end.day))

    def test_quarter_bounds(self):
        start, end = period_bounds_for("2024-Q3")
        self.assertEqual((2024, 7), (start.year, start.month))
        self.assertEqual((2024, 10), (end.year, end.month))

    def test_fourth_quarter_ends_in_the_next_year(self):
        start, end = period_bounds_for("2024-Q4")
        self.assertEqual((2024, 10), (start.year, start.month))
        self.assertEqual((2025, 1), (end.year, end.month))

    def test_month_bounds(self):
        start, end = period_bounds_for("2024-07")
        self.assertEqual((2024, 7), (start.year, start.month))
        self.assertEqual((2024, 8), (end.year, end.month))

    def test_december_ends_in_the_next_year(self):
        start, end = period_bounds_for("2024-12")
        self.assertEqual((2024, 12), (start.year, start.month))
        self.assertEqual((2025, 1), (end.year, end.month))

    def test_bounds_round_trip_with_the_key(self):
        """
        A period's start falls inside that period, and its end does not.

        `time_start` is inclusive and `time_end` exclusive, so a record written at exactly the end belongs
        to the next period. Getting that wrong files a record in a period a reader selecting it never sees.
        """
        for granularity in ("year", "quarter", "month"):
            key = period_key_for(datetime(2024, 8, 9), granularity)
            start, end = period_bounds_for(key)
            with self.subTest(granularity=granularity):
                self.assertEqual(key, period_key_for(start, granularity))
                self.assertNotEqual(key, period_key_for(end, granularity))


class PeriodLabelTestCase(TestCase):
    def test_labels(self):
        self.assertEqual("All time", period_label_for(CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD))
        self.assertEqual("2024", period_label_for("2024"))
        self.assertEqual("2024 Q3", period_label_for("2024-Q3"))
        self.assertEqual("July 2024", period_label_for("2024-07"))


class ArchiveSegmentTestCase(TestCase):
    def test_a_calendar_period_needs_both_bounds(self):
        segment = ArchiveSegment(model_label="extras.objectchange", period_key="2024", label="2024")
        with self.assertRaises(ValidationError) as raised:
            segment.full_clean()
        self.assertIn("time_start", raised.exception.message_dict)

    def test_the_unbounded_period_may_leave_both_unset(self):
        segment = ArchiveSegment(
            model_label="extras.objectchange", period_key=CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD, label="All time"
        )
        segment.full_clean()

    def test_a_period_must_end_after_it_starts(self):
        """A period ending at or before its start is one no record can belong to."""
        segment = ArchiveSegment(
            model_label="extras.objectchange",
            period_key="2024",
            label="2024",
            time_start=datetime(2025, 1, 1, tzinfo=dt_timezone.utc),
            time_end=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
        )
        with self.assertRaises(ValidationError) as raised:
            segment.full_clean()
        self.assertIn("time_end", raised.exception.message_dict)
