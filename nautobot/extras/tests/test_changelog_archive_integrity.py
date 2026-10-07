"""
Tests for the jobs and checks that stand in for what the retention mirrors gave up.

The mirrors hold their references as bare identifier columns, so the database enforces nothing about them.
These are the mechanisms that replace CASCADE, PROTECT, and the migration tooling: each one detects a
specific way retained history can diverge, and none of them prevents it.
"""

from datetime import datetime, timezone as dt_timezone
from io import StringIO
import uuid

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from nautobot.core.constants import CHANGELOG_ARCHIVE
from nautobot.core.jobs.retention import ChangelogArchiveIntegrityCheck
from nautobot.core.testing import TestCase
from nautobot.extras.choices import JobResultStatusChoices, LogLevelChoices, ObjectChangeActionChoices
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    JobResult,
    ObjectChange,
)
from nautobot.extras.tests.test_changelog_archive_base import clear_archive, RecordingLogger, StubJobResult

WHEN = datetime(2021, 6, 1, tzinfo=dt_timezone.utc)


class ArchiveIntegrityTestMixin:
    databases = ["default", CHANGELOG_ARCHIVE]

    def setUp(self):
        super().setUp()
        self.content_type = ContentType.objects.get_for_model(ObjectChange)
        clear_archive(ArchivedObjectChange, ArchivedJobResult, ArchivedJobLogEntry, ArchivedJobConsoleEntry)
        self.logger = RecordingLogger()

    def drive(self, job_class, **kwargs):
        job = job_class()
        job.logger = self.logger
        job.job_result = StubJobResult(self.user)
        return job.run(**kwargs)

    def make_archived_change(self, *, time=WHEN, content_type_id=None, pk=None):
        return ArchivedObjectChange.objects.create(
            id=pk or uuid.uuid4(),
            time=time,
            user_name="alice",
            request_id=uuid.uuid4(),
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type_id=self.content_type.pk if content_type_id is None else content_type_id,
            changed_object_id=uuid.uuid4(),
            change_context="orm",
            object_repr="Widget",
            object_data={},
        )

    def make_archived_job_result(self, *, pk=None):
        return ArchivedJobResult.objects.create(
            id=pk or uuid.uuid4(),
            name="Test Job",
            date_created=WHEN,
            status=JobResultStatusChoices.STATUS_SUCCESS,
        )

    def make_archived_log_entry(self, *, job_result_id):
        return ArchivedJobLogEntry.objects.create(
            id=uuid.uuid4(),
            job_result_id=job_result_id,
            log_level=LogLevelChoices.LOG_INFO,
            message="hello",
            created=WHEN,
        )


class ChangelogArchiveIntegrityCheckTestCase(ArchiveIntegrityTestMixin, TestCase):
    """Replaces CASCADE: a retained record can outlive what it points at, and nothing stops it."""

    def test_clean_archive_reports_nothing(self):
        job_result = self.make_archived_job_result()
        self.make_archived_log_entry(job_result_id=job_result.pk)
        self.make_archived_change()

        result = self.drive(ChangelogArchiveIntegrityCheck)

        self.assertEqual(
            result,
            {
                "orphaned_log_entries": 0,
                "orphaned_console_entries": 0,
                "stale_content_types": 0,
                "duplicated_records": 0,
            },
        )

    def test_log_entry_whose_job_result_is_archived_is_not_an_orphan(self):
        """The referent may live in retention rather than warm storage; both count."""
        job_result = self.make_archived_job_result()
        self.make_archived_log_entry(job_result_id=job_result.pk)

        result = self.drive(ChangelogArchiveIntegrityCheck)

        self.assertEqual(result["orphaned_log_entries"], 0)

    def test_log_entry_whose_job_result_is_warm_is_not_an_orphan(self):
        warm = JobResult.objects.create(name="Warm Job", status=JobResultStatusChoices.STATUS_SUCCESS)
        self.make_archived_log_entry(job_result_id=warm.pk)

        result = self.drive(ChangelogArchiveIntegrityCheck)

        self.assertEqual(result["orphaned_log_entries"], 0)

    def test_orphaned_log_entry_is_reported_not_deleted(self):
        """A dangling reference is a reason to look, so reporting is the default."""
        entry = self.make_archived_log_entry(job_result_id=uuid.uuid4())

        result = self.drive(ChangelogArchiveIntegrityCheck)

        self.assertEqual(result["orphaned_log_entries"], 1)
        self.assertTrue(ArchivedJobLogEntry.objects.filter(pk=entry.pk).exists())
        self.assertTrue(self.logger.said("Re-run with `repair`"))

    def test_orphaned_log_entry_is_deleted_when_repairing(self):
        entry = self.make_archived_log_entry(job_result_id=uuid.uuid4())

        result = self.drive(ChangelogArchiveIntegrityCheck, repair=True)

        self.assertEqual(result["orphaned_log_entries"], 1)
        self.assertFalse(ArchivedJobLogEntry.objects.filter(pk=entry.pk).exists())

    def test_orphaned_console_entry_is_reported(self):
        ArchivedJobConsoleEntry.objects.create(id=uuid.uuid4(), job_result_id=uuid.uuid4(), timestamp=WHEN, text="line")

        result = self.drive(ChangelogArchiveIntegrityCheck)

        self.assertEqual(result["orphaned_console_entries"], 1)

    def test_stale_content_type_is_reported(self):
        """A retained change pointing at a removed content type cannot render its object."""
        self.make_archived_change(content_type_id=99999999)

        result = self.drive(ChangelogArchiveIntegrityCheck)

        self.assertEqual(result["stale_content_types"], 1)

    def test_null_content_type_is_not_stale(self):
        """`changed_object_type` is nullable on the warm model too; absent is not dangling."""
        self.make_archived_change(content_type_id=None)
        ArchivedObjectChange.objects.update(changed_object_type_id=None)

        result = self.drive(ChangelogArchiveIntegrityCheck)

        self.assertEqual(result["stale_content_types"], 0)


class ArchiveDuplicateRecordTestCase(ArchiveIntegrityTestMixin, TestCase):
    """Replaces PROTECT and the migration tooling: the registry's claims are checked against reality."""

    def test_record_in_both_warm_and_retention_is_reported(self):
        """The state an interrupted rotation leaves: copied but never removed."""
        warm = ObjectChange.objects.create(
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type=self.content_type,
            changed_object_id=uuid.uuid4(),
            object_repr="Widget",
            object_data={},
            request_id=uuid.uuid4(),
            user_name="alice",
            change_context="orm",
        )
        self.make_archived_change(pk=warm.pk)

        result = self.drive(ChangelogArchiveIntegrityCheck)

        self.assertEqual(result["duplicated_records"], 1)
        self.assertTrue(self.logger.said("both warm storage and retention"))

    def test_clean_archive_reports_nothing(self):
        self.make_archived_change()

        result = self.drive(ChangelogArchiveIntegrityCheck)

        self.assertEqual(result["duplicated_records"], 0)


class CheckChangelogArchiveSchemaTestCase(TestCase):
    """
    Replaces the migration tooling.

    Nothing in Django knows the mirrors track the warm models, so a field added to one side only is
    otherwise invisible. This is the mechanism that makes it visible.
    """

    databases = ["default", CHANGELOG_ARCHIVE]

    def test_reports_clean_when_mirrors_match(self):
        output = StringIO()
        call_command("check_changelog_archive_schema", stdout=output)
        self.assertIn("Every retention mirror matches", output.getvalue())

    def test_detects_a_field_present_only_on_the_warm_model(self):
        """Simulated by pointing a mirror at a warm model with fields it does not have."""
        from nautobot.extras.management.commands.check_changelog_archive_schema import find_schema_drift
        from nautobot.extras.registry import registry

        original = dict(registry["changelog_archive_models"])
        try:
            # ArchivedJobLogEntry does not mirror JobResult, so every JobResult field reads as missing.
            registry["changelog_archive_models"]["extras.jobresult"] = ArchivedJobLogEntry
            drift = find_schema_drift()
        finally:
            registry["changelog_archive_models"].clear()
            registry["changelog_archive_models"].update(original)

        offenders = {mirror_label for mirror_label, _warm, _missing in drift}
        self.assertIn("extras.ArchivedJobLogEntry", offenders)

    def test_system_check_reports_no_warning_when_clean(self):
        from nautobot.core.checks import check_changelog_archive_schema

        self.assertEqual(check_changelog_archive_schema(None), [])
