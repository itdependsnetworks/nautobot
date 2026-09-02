"""Tests for the `ChangelogRotation` system job."""

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock
import uuid

from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.utils import timezone

from nautobot.core.constants import CHANGELOG_ARCHIVE
from nautobot.core.jobs.retention import ChangelogRotation, ROTATION_ORDER
from nautobot.core.testing import TestCase
from nautobot.extras.choices import JobResultStatusChoices, LogLevelChoices, ObjectChangeActionChoices
from nautobot.extras.models import (
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    ArchiveSegment,
    JobLogEntry,
    JobResult,
    ObjectChange,
)
from nautobot.extras.tests.test_changelog_truncation import RecordingLogger, StubJobResult


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True, CHANGELOG_WARM_WINDOW_DAYS=90, CHANGELOG_ARCHIVE_PERIOD="year")
class ChangelogRotationTestCase(TestCase):
    """
    Rotation files each record under the calendar period its own timestamp falls in.

    Driven directly with a recording logger, the same shape as the truncation unit tests: rule-free
    behavior, deterministic messages, no dependency on `JobLogEntry` rows surviving the `job_logs`
    connection.
    """

    databases = ["default", CHANGELOG_ARCHIVE]

    def setUp(self):
        super().setUp()
        self.content_type = ContentType.objects.get_for_model(ObjectChange)
        # Rotation is unfiltered by design, so it would sweep up the test database's own change records
        # and make every count assertion meaningless. Start from an empty population.
        ObjectChange.objects.all().delete()
        ArchivedObjectChange.objects.all().delete()
        ArchiveSegment.objects.all().delete()
        self.job = ChangelogRotation()
        self.logger = RecordingLogger()
        self.job.logger = self.logger
        self.job.job_result = StubJobResult(self.user)

    def run_job(self, **kwargs):
        kwargs.setdefault("record_types", ["extras.objectchange"])
        kwargs.setdefault("dry_run", False)
        return self.job.run(**kwargs)

    def make_object_change(self, *, time, user_name="alice"):
        change = ObjectChange.objects.create(
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type=self.content_type,
            changed_object_id=uuid.uuid4(),
            object_repr="Widget",
            object_data={"a": 1},
            request_id=uuid.uuid4(),
            user_name=user_name,
            change_context="orm",
        )
        ObjectChange.objects.filter(pk=change.pk).update(time=time)
        change.refresh_from_db()
        return change

    def test_disabled_capability_is_a_no_op(self):
        """With retention off, rotation moves nothing and says why."""
        change = self.make_object_change(time=datetime(2020, 5, 1, tzinfo=dt_timezone.utc))
        with override_settings(CHANGELOG_ARCHIVE_ENABLED=False):
            result = self.run_job()
        self.assertEqual(result, {})
        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())
        self.assertTrue(self.logger.said("disabled"))

    def test_moves_record_into_the_period_its_timestamp_falls_in(self):
        change = self.make_object_change(time=datetime(2021, 7, 15, tzinfo=dt_timezone.utc))

        result = self.run_job()

        self.assertEqual(result, {"extras.ObjectChange": 1})
        self.assertFalse(ObjectChange.objects.filter(pk=change.pk).exists())
        mirror = ArchivedObjectChange.objects.get(pk=change.pk)
        self.assertEqual(mirror.period_key, "2021")
        segment = ArchiveSegment.objects.get(model_label="extras.objectchange", period_key="2021")
        self.assertEqual(segment.label, "2021")
        self.assertEqual(segment.row_count, 1)
        self.assertEqual(segment.last_rotated_time, change.time)

    def test_no_field_is_lost(self):
        """§8: rotation moves records without loss of the retained fields."""
        change = self.make_object_change(time=datetime(2021, 3, 3, tzinfo=dt_timezone.utc), user_name="carol")

        self.run_job()

        mirror = ArchivedObjectChange.objects.get(pk=change.pk)
        self.assertEqual(mirror.id, change.id)
        self.assertEqual(mirror.time, change.time)
        self.assertEqual(mirror.action, change.action)
        self.assertEqual(mirror.user_name, "carol")
        self.assertEqual(mirror.request_id, change.request_id)
        self.assertEqual(mirror.changed_object_id, change.changed_object_id)
        self.assertEqual(mirror.changed_object_type_id, change.changed_object_type_id)
        self.assertEqual(mirror.object_repr, change.object_repr)
        self.assertEqual(mirror.object_data, change.object_data)
        self.assertEqual(mirror.change_context, change.change_context)

    def test_rotation_is_idempotent(self):
        """§8: re-running moves no additional records and changes no counts."""
        self.make_object_change(time=datetime(2021, 7, 15, tzinfo=dt_timezone.utc))
        self.run_job()
        segment = ArchiveSegment.objects.get(model_label="extras.objectchange", period_key="2021")
        first_count, first_rotated = segment.row_count, segment.last_rotated_time

        second = self.run_job()

        self.assertEqual(second, {"extras.ObjectChange": 0})
        self.assertEqual(ArchivedObjectChange.objects.count(), 1)
        segment.refresh_from_db()
        self.assertEqual(segment.row_count, first_count)
        self.assertEqual(segment.last_rotated_time, first_rotated)

    def test_records_inside_the_warm_window_stay(self):
        recent = self.make_object_change(time=timezone.now() - timedelta(days=5))

        result = self.run_job()

        self.assertEqual(result, {"extras.ObjectChange": 0})
        self.assertTrue(ObjectChange.objects.filter(pk=recent.pk).exists())
        self.assertFalse(ArchivedObjectChange.objects.filter(pk=recent.pk).exists())

    def test_separate_periods_get_separate_segments(self):
        self.make_object_change(time=datetime(2020, 6, 1, tzinfo=dt_timezone.utc))
        self.make_object_change(time=datetime(2021, 6, 1, tzinfo=dt_timezone.utc))
        self.make_object_change(time=datetime(2021, 9, 1, tzinfo=dt_timezone.utc))

        self.run_job()

        segments = {
            segment.period_key: segment.row_count
            for segment in ArchiveSegment.objects.filter(model_label="extras.objectchange")
        }
        self.assertEqual(segments, {"2020": 1, "2021": 2})

    @override_settings(CHANGELOG_ARCHIVE_PERIOD="quarter")
    def test_period_granularity_is_configurable(self):
        self.make_object_change(time=datetime(2021, 2, 1, tzinfo=dt_timezone.utc))
        self.make_object_change(time=datetime(2021, 8, 1, tzinfo=dt_timezone.utc))

        self.run_job()

        segments = ArchiveSegment.objects.filter(model_label="extras.objectchange").order_by("period_key")
        self.assertEqual([segment.period_key for segment in segments], ["2021-Q1", "2021-Q3"])
        self.assertEqual([segment.label for segment in segments], ["2021 Q1", "2021 Q3"])

    def test_moves_in_bounded_increments(self):
        for day in range(1, 6):
            self.make_object_change(time=datetime(2021, 4, day, tzinfo=dt_timezone.utc))

        result = self.run_job(batch_size=2)

        self.assertEqual(result, {"extras.ObjectChange": 5})
        increments = [message for message in self.logger.messages if message.startswith("Increment ")]
        self.assertEqual(len(increments), 3, f"5 records at batch_size=2 is 3 increments, got {increments}")

    def test_dry_run_moves_nothing(self):
        change = self.make_object_change(time=datetime(2021, 7, 15, tzinfo=dt_timezone.utc))

        result = self.run_job(dry_run=True)

        # The count it would move, flagged as a dry run, so the summary says what it would do.
        self.assertEqual(result, {"extras.ObjectChange": 1, "dry_run": True})
        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())
        self.assertFalse(ArchiveSegment.objects.exists())
        self.assertTrue(self.logger.said("Dry run: would move 1"))

    def test_finished_period_is_closed(self):
        """A period that has ended with no warm records left carries no staleness claim."""
        self.make_object_change(time=datetime(2021, 7, 15, tzinfo=dt_timezone.utc))

        self.run_job()

        segment = ArchiveSegment.objects.get(model_label="extras.objectchange", period_key="2021")
        self.assertTrue(segment.is_period_closed)
        self.assertTrue(self.logger.said("Closed retention period 2021"))

    def test_current_period_stays_open(self):
        """A period still in progress cannot be closed, however much of it has rotated."""
        now = timezone.now()
        if now.month <= 4:
            self.skipTest("no date is both inside the current calendar year and past the warm window")
        # Past the 90-day warm window, but still inside the current calendar year.
        self.make_object_change(time=now.replace(month=1, day=2))

        self.run_job()

        segment = ArchiveSegment.objects.get(model_label="extras.objectchange", period_key=str(now.year))
        self.assertFalse(segment.is_period_closed, "the current calendar period has not ended yet")

    def test_period_with_warm_records_remaining_stays_open(self):
        """
        A period is only complete once nothing of it is left in warm storage.

        The second run uses a warm window wide enough to rotate nothing, which is the state a
        partially-failed rotation leaves behind: an ended period that still holds warm records.
        """
        self.make_object_change(time=datetime(2021, 2, 1, tzinfo=dt_timezone.utc))
        self.run_job()
        segment = ArchiveSegment.objects.get(model_label="extras.objectchange", period_key="2021")
        self.assertTrue(segment.is_period_closed)

        segment.is_period_closed = False
        segment.save(update_fields=["is_period_closed"])
        straggler = self.make_object_change(time=datetime(2021, 3, 1, tzinfo=dt_timezone.utc))
        self.run_job(warm_window_days=99999)

        segment.refresh_from_db()
        self.assertTrue(ObjectChange.objects.filter(pk=straggler.pk).exists())
        self.assertFalse(
            segment.is_period_closed, "a period still holding warm records must not be reported as complete"
        )


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True, CHANGELOG_WARM_WINDOW_DAYS=90)
class ChangelogRotationJobResultTestCase(TestCase):
    """
    `JobResult` has CASCADE children, so rotating it is where collateral loss would happen.

    Log and console entries are archived first; output files are never archived at all.
    """

    databases = ["default", CHANGELOG_ARCHIVE]

    def setUp(self):
        super().setUp()
        JobLogEntry.objects.all().delete()
        JobResult.objects.all().delete()
        ArchivedJobLogEntry.objects.all().delete()
        ArchivedJobResult.objects.all().delete()
        ArchiveSegment.objects.all().delete()
        self.job = ChangelogRotation()
        self.logger = RecordingLogger()
        self.job.logger = self.logger
        self.job.job_result = StubJobResult(self.user)
        self.old = datetime(2021, 5, 5, tzinfo=dt_timezone.utc)

    def make_job_result(self):
        result = JobResult.objects.create(name="Test Job", status=JobResultStatusChoices.STATUS_SUCCESS)
        JobResult.objects.filter(pk=result.pk).update(date_created=self.old, date_done=self.old)
        result.refresh_from_db()
        return result

    def test_children_rotate_before_their_parent(self):
        """ROTATION_ORDER puts CASCADE children first, or deleting the parent would take them along."""
        self.assertLess(
            ROTATION_ORDER.index("extras.joblogentry"),
            ROTATION_ORDER.index("extras.jobresult"),
            "job log entries must rotate before job results",
        )
        self.assertLess(
            ROTATION_ORDER.index("extras.jobconsoleentry"),
            ROTATION_ORDER.index("extras.jobresult"),
            "job console entries must rotate before job results",
        )

    def test_log_entries_survive_a_full_rotation(self):
        """
        The regression this ordering exists for.

        Rotating everything in order must archive the log entry and the job result, with neither lost to a
        cascade.
        """
        result = self.make_job_result()
        entry = JobLogEntry.objects.create(
            job_result=result, log_level=LogLevelChoices.LOG_INFO, message="hello", created=self.old
        )

        self.job.run(record_types=None, dry_run=False)

        self.assertTrue(ArchivedJobLogEntry.objects.filter(pk=entry.pk).exists())
        self.assertEqual(ArchivedJobLogEntry.objects.get(pk=entry.pk).message, "hello")
        self.assertTrue(ArchivedJobResult.objects.filter(pk=result.pk).exists())
        self.assertFalse(JobLogEntry.objects.filter(pk=entry.pk).exists())
        self.assertFalse(JobResult.objects.filter(pk=result.pk).exists())

    def test_job_result_held_back_while_its_log_entries_are_still_warm(self):
        """Rotating only the parent must not delete children that have not been archived yet."""
        result = self.make_job_result()
        entry = JobLogEntry.objects.create(
            job_result=result, log_level=LogLevelChoices.LOG_INFO, message="keep me", created=self.old
        )

        self.job.run(record_types=["extras.jobresult"], dry_run=False)

        self.assertTrue(JobResult.objects.filter(pk=result.pk).exists())
        self.assertTrue(JobLogEntry.objects.filter(pk=entry.pk).exists())
        self.assertFalse(ArchivedJobResult.objects.filter(pk=result.pk).exists())
        self.assertTrue(self.logger.said("still in warm storage"))

    def test_held_back_count_is_job_results_not_log_entries(self):
        """
        The reported count must be job results, not the rows a reverse-foreign-key join produces.

        Without `.distinct()` a result with three log entries is reported three times, which reads as if
        far more work is pending than there is.
        """
        result = self.make_job_result()
        for index in range(3):
            JobLogEntry.objects.create(
                job_result=result, log_level=LogLevelChoices.LOG_INFO, message=f"line {index}", created=self.old
            )

        self.job.run(record_types=["extras.jobresult"], dry_run=True)

        held = [message for message in self.logger.messages if "still in warm storage" in message]
        self.assertEqual(len(held), 1, f"expected one held-back message, got {held}")
        self.assertIn("Holding back 1 job results", held[0])

    def test_job_result_user_name_is_denormalized(self):
        """The username is unrecoverable once the foreign key is demoted, so rotation copies it."""
        result = self.make_job_result()
        JobResult.objects.filter(pk=result.pk).update(user=self.user)

        self.job.run(record_types=["extras.jobresult"], dry_run=False)

        self.assertEqual(ArchivedJobResult.objects.get(pk=result.pk).user_name, self.user.username)


class ChangelogRotationInterruptionTestCase(ChangelogRotationTestCase):
    """
    What a run killed part-way leaves behind, and whether the next run resolves it.

    A rotation job is a long bulk copy over the tables this feature exists because they are enormous, so it
    is a plausible target for an out-of-memory kill. A SIGKILL runs no `finally` and no transaction commit,
    so what matters is that whatever it leaves is recoverable by running the job again.
    """

    def test_a_record_copied_but_not_deleted_is_resolved_by_the_next_run(self):
        """
        The state a kill between the copy and the warm delete leaves.

        Copy-then-delete is chosen so this is the failure mode: the record exists twice, rather than not at
        all. The next run has to converge -- not duplicate the retained copy, and not double-count it.
        """
        change = self.make_object_change(time=datetime(2020, 5, 1, tzinfo=dt_timezone.utc))
        # Exactly what the interrupted run had done: mirror written, warm row still present, no count.
        ArchivedObjectChange.objects.create(
            id=change.pk,
            period_key="2020",
            time=change.time,
            user_name=change.user_name,
            request_id=change.request_id,
            action=change.action,
            changed_object_type_id=self.content_type.pk,
            changed_object_id=change.changed_object_id,
            change_context=change.change_context,
            object_repr=change.object_repr,
            object_data=change.object_data,
        )

        result = self.run_job()

        self.assertEqual(result, {"extras.ObjectChange": 1})
        self.assertEqual(ArchivedObjectChange.objects.filter(pk=change.pk).count(), 1)
        self.assertFalse(ObjectChange.objects.filter(pk=change.pk).exists())
        segment = ArchiveSegment.objects.get(model_label="extras.objectchange", period_key="2020")
        self.assertEqual(segment.row_count, 1)
        self.assertEqual(segment.row_count, ArchivedObjectChange.objects.filter(period_key="2020").count())

    def test_the_warm_delete_and_the_row_count_commit_together(self):
        """
        A count lower than what was actually removed from warm storage cannot be fixed by re-running.

        Re-running cannot fix it, because the warm records it would have counted are already gone. So the
        count and the delete have to land in one transaction. Forcing the count to fail is how that is
        checked: the warm record must still be there afterwards.
        """
        change = self.make_object_change(time=datetime(2020, 5, 1, tzinfo=dt_timezone.utc))

        with mock.patch.object(ChangelogRotation, "_record_progress", side_effect=RuntimeError("killed")):
            with self.assertRaises(RuntimeError):
                self.run_job()

        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())
        segment = ArchiveSegment.objects.filter(model_label="extras.objectchange", period_key="2020").first()
        self.assertEqual(getattr(segment, "row_count", 0), 0)
        # The retained copy is *not* rolled back with it: the mirror is written through the archive
        # connection while this transaction is on `default`, so they are two transactions. That is why
        # rotation copies before deleting -- the record is in both places, not neither -- and why the run
        # above converges rather than losing it.
        self.assertTrue(ArchivedObjectChange.objects.filter(pk=change.pk).exists())

        # And the next run does converge.
        result = self.run_job()
        self.assertEqual(result, {"extras.ObjectChange": 1})
        self.assertFalse(ObjectChange.objects.filter(pk=change.pk).exists())
        self.assertEqual(ArchivedObjectChange.objects.filter(pk=change.pk).count(), 1)
        segment = ArchiveSegment.objects.get(model_label="extras.objectchange", period_key="2020")
        self.assertEqual(segment.row_count, 1)

    def test_interrupted_batches_leave_earlier_ones_committed(self):
        """Each increment stands on its own, so a kill costs the current batch and nothing before it."""
        for day in range(1, 6):
            self.make_object_change(time=datetime(2020, 5, day, tzinfo=dt_timezone.utc))

        self.run_job(batch_size=2)

        self.assertEqual(ArchivedObjectChange.objects.count(), 5)
        self.assertEqual(ObjectChange.objects.count(), 0)
        segment = ArchiveSegment.objects.get(model_label="extras.objectchange", period_key="2020")
        self.assertEqual(segment.row_count, 5)
        self.assertTrue(self.logger.said("Increment 1"))
        self.assertTrue(self.logger.said("Increment 3"))

    def test_rotation_has_its_own_batch_size_setting(self):
        """
        Rotation holds records in memory to copy them; truncation only needs their keys.

        Sharing truncation's default made an out-of-memory kill likelier than intended, by an order of
        magnitude, on the large-record tables this feature is for.
        """
        from nautobot.core.utils.config import get_settings_or_config

        self.assertEqual(get_settings_or_config("CHANGELOG_ROTATION_BATCH_SIZE", fallback=None), 1000)
        self.assertLess(
            get_settings_or_config("CHANGELOG_ROTATION_BATCH_SIZE", fallback=1000),
            get_settings_or_config("CHANGELOG_TRUNCATION_BATCH_SIZE", fallback=10000),
        )


class ChangelogRotationDryRunReportingTestCase(ChangelogRotationTestCase):
    """
    A dry run exists to answer "how much would this do", so the answer has to be in the summary.

    It used to return 0 for every model and put the number only in the log, which made the job result page
    say nothing happened -- true, but not the question being asked.
    """

    def test_the_summary_carries_the_counts_and_says_it_was_a_dry_run(self):
        for day in range(1, 5):
            self.make_object_change(time=datetime(2020, 5, day, tzinfo=dt_timezone.utc))

        result = self.run_job(dry_run=True)

        self.assertEqual(result, {"extras.ObjectChange": 4, "dry_run": True})
        self.assertEqual(ArchivedObjectChange.objects.count(), 0)
        self.assertEqual(ObjectChange.objects.count(), 4)

    def test_a_real_run_carries_no_dry_run_flag(self):
        """So a reader cannot mistake pending work for work done, or the reverse."""
        self.make_object_change(time=datetime(2020, 5, 1, tzinfo=dt_timezone.utc))

        result = self.run_job()

        self.assertNotIn("dry_run", result)
        self.assertEqual(result, {"extras.ObjectChange": 1})

    def test_a_dry_run_says_why_its_job_result_count_is_a_lower_bound(self):
        """
        Nothing moves in a dry run, so every job result looks held back behind its own log entries.

        The count is genuinely a lower bound rather than a prediction, and the log has to say so -- a bare
        0 beside "would move 66 log entries" reads as a bug in the job.
        """
        job_result = JobResult.objects.create(name="Dry Run Reporting")
        JobResult.objects.filter(pk=job_result.pk).update(
            date_created=datetime(2020, 5, 1, tzinfo=dt_timezone.utc),
            date_done=datetime(2020, 5, 1, tzinfo=dt_timezone.utc),
        )
        JobLogEntry.objects.create(job_result=job_result, log_level=LogLevelChoices.LOG_INFO, message="held back")

        result = self.job.run(
            record_types=["extras.jobresult", "extras.joblogentry"], warm_window_days=90, dry_run=True
        )

        self.assertEqual(result["extras.JobResult"], 0)
        # Not pinning the number: the test database carries its own job results with log entries, and this
        # is about what the message explains rather than how many it counts.
        self.assertTrue(self.logger.said("Holding back"))
        self.assertTrue(self.logger.said("lower bound rather than a prediction"))
