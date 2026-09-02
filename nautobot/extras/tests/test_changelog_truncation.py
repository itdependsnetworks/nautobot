"""
Tests for the `ChangelogTruncation` system job.

Split deliberately into two layers:

- `ChangelogTruncationUnitTestCase` drives the job object directly with a recording logger. Rule
  resolution, increment sizing, and the messages the operator reads are asserted here, where they are
  deterministic.
- `ChangelogTruncation*IntegrationTestCase` runs the job through the real Celery path and asserts on
  database state only. It deliberately makes no claim about `JobLogEntry` rows: those are written through
  the separate `job_logs` connection, which cannot see a `JobResult` still inside the enqueueing
  transaction, so their presence is not something a test can rely on.
"""

from datetime import datetime, timedelta, timezone as dt_timezone
import uuid

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings

from nautobot.core.constants import CHANGELOG_ARCHIVE
from nautobot.core.jobs.retention import ChangelogTruncation
from nautobot.core.testing import create_job_result_and_run_job, TestCase, TransactionTestCase
from nautobot.dcim.models import Location
from nautobot.extras.choices import (
    JobResultStatusChoices,
    ObjectChangeActionChoices,
    RetentionRuleModeChoices,
)
from nautobot.extras.models import ArchiveSegment, JobResult, ObjectChange, RetentionRule
from nautobot.users.models import ObjectPermission

MODULE = "nautobot.core.jobs.retention"
JOB_CLASS = "ChangelogTruncation"
OLD_TIME = datetime(2020, 3, 1, tzinfo=dt_timezone.utc)


class StubJobResult:
    """Stands in for the `JobResult` a running job reads its user from."""

    def __init__(self, user):
        self.user = user


class RecordingLogger:
    """Captures what the job would tell the operator, so messages can be asserted directly."""

    def __init__(self):
        self.records = []

    def _record(self, level, message, *args):
        self.records.append((level, message % args if args else message))

    def debug(self, message, *args, **kwargs):
        self._record("debug", message, *args)

    def info(self, message, *args, **kwargs):
        self._record("info", message, *args)

    def warning(self, message, *args, **kwargs):
        self._record("warning", message, *args)

    def error(self, message, *args, **kwargs):
        self._record("error", message, *args)

    def success(self, message, *args, **kwargs):
        self._record("success", message, *args)

    @property
    def messages(self):
        return [message for _level, message in self.records]

    def said(self, fragment):
        return any(fragment in message for message in self.messages)


class ChangelogTruncationTestMixin:
    """Shared fixture building for both layers."""

    def make_object_change(self, *, action=ObjectChangeActionChoices.ACTION_DELETE, time=OLD_TIME, user_name=None):
        """
        Create an `ObjectChange` at a chosen time.

        Each record gets a fresh `request_id` and `changed_object_id`: `ObjectChange` is unique on
        (time, request_id, changed_object_type, changed_object_id) and these tests deliberately pin several
        records to one timestamp.
        """
        change = ObjectChange.objects.create(
            action=action,
            changed_object_type=self.content_type,
            changed_object_id=uuid.uuid4(),
            object_repr="Widget",
            object_data={},
            request_id=uuid.uuid4(),
            user_name=user_name or self.marker,
            change_context="orm",
        )
        # `time` is auto_now_add, so it can only be set after the insert.
        ObjectChange.objects.filter(pk=change.pk).update(time=time)
        change.refresh_from_db()
        return change

    def make_rule(self, *, scoped=True, **kwargs):
        """
        Create a rule, scoped by default to this test's own records.

        The test database carries pre-existing `ObjectChange` rows, so an unscoped filter such as
        "every delete older than 30 days" selects far more than the test created. Passing
        `scoped=False` opts out, for cases that are specifically about an unscoped filter.
        """
        kwargs.setdefault("name", f"rule-{uuid.uuid4().hex[:8]}")
        kwargs.setdefault("content_type", self.content_type)
        if scoped:
            scope_filter = dict(kwargs.get("scope_filter") or {})
            scope_filter.setdefault("user_name", [self.marker])
            kwargs["scope_filter"] = scope_filter
        return RetentionRule.objects.create(**kwargs)

    def grant_delete(self):
        permission = ObjectPermission.objects.create(name="Delete object changes", actions=["delete", "view"])
        permission.users.add(self.user)
        permission.object_types.add(self.content_type)


class ChangelogTruncationUnitTestCase(ChangelogTruncationTestMixin, TestCase):
    """Rule resolution, increment sizing, and operator messaging, driven directly."""

    def setUp(self):
        super().setUp()
        self.content_type = ContentType.objects.get_for_model(ObjectChange)
        self.marker = f"user-{uuid.uuid4().hex[:8]}"
        self.job = ChangelogTruncation()
        self.logger = RecordingLogger()
        self.job.logger = self.logger
        # `Job.user` reads through `job_result`, which is a cached_property, so a stub assigns cleanly.
        self.job.job_result = StubJobResult(self.user)
        self.grant_delete()
        self.clear_permission_cache()

    def clear_permission_cache(self):
        """`has_perm` caches resolved permissions on the user, so changes need the cache dropped."""
        if hasattr(self.user, "_object_perm_cache"):
            del self.user._object_perm_cache

    def run_job(self, **kwargs):
        kwargs.setdefault("batch_size", 10000)
        kwargs.setdefault("dry_run", False)
        return self.job.run(**kwargs)

    def test_deletes_only_what_the_filter_selects(self):
        """The core guarantee: exactly the selected rows, and no others."""
        doomed = self.make_object_change(action=ObjectChangeActionChoices.ACTION_DELETE)
        spared = self.make_object_change(action=ObjectChangeActionChoices.ACTION_UPDATE)
        self.make_rule(scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]}, max_age_days=30)

        result = self.run_job()

        self.assertEqual(result, {"extras.ObjectChange": 1})
        self.assertFalse(ObjectChange.objects.filter(pk=doomed.pk).exists())
        self.assertTrue(ObjectChange.objects.filter(pk=spared.pk).exists())

    def test_no_rules_at_all_is_a_no_op_not_a_failure(self):
        """A scheduled job with nothing configured should say so, not fail."""
        change = self.make_object_change()

        result = self.run_job()

        self.assertEqual(result, {})
        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())
        self.assertTrue(self.logger.said("No retention rules exist"))

    def test_rules_exist_but_none_enabled_says_which_case_it_is(self):
        """
        Every enabled rule applies, so with none enabled the job has nothing to apply.

        An operator seeing an empty picker and a job that does nothing needs to be told which of the two
        situations they are in, since the fix differs: create a rule, or enable one.
        """
        change = self.make_object_change(action=ObjectChangeActionChoices.ACTION_DELETE, time=OLD_TIME)
        self.make_rule(
            scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]},
            max_age_days=30,
            enabled=False,
        )

        result = self.run_job()

        self.assertEqual(result, {})
        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())
        self.assertTrue(self.logger.said("are enabled"))
        self.assertFalse(self.logger.said("No retention rules exist"))

    def test_age_bound_alone_is_a_valid_rule(self):
        old = self.make_object_change(action=ObjectChangeActionChoices.ACTION_UPDATE, time=OLD_TIME)
        recent = self.make_object_change(
            action=ObjectChangeActionChoices.ACTION_UPDATE, time=datetime.now(dt_timezone.utc) - timedelta(days=1)
        )
        self.make_rule(scope_filter={}, max_age_days=30, scoped=False)

        self.run_job()

        self.assertFalse(ObjectChange.objects.filter(pk=old.pk).exists())
        self.assertTrue(ObjectChange.objects.filter(pk=recent.pk).exists())

    def test_exclude_rule_protects_records_an_include_rule_selects(self):
        """An exclude rule wins, which is what makes rules composable without ordering surprises."""
        protected = self.make_object_change(user_name=f"keep-{self.marker}")
        doomed = self.make_object_change(user_name=f"delete-{self.marker}")
        self.make_rule(
            name="include-deletes",
            scope_filter={"user_name": [f"keep-{self.marker}", f"delete-{self.marker}"]},
            max_age_days=30,
            weight=100,
            scoped=False,
        )
        self.make_rule(
            name="protect-keepme",
            scope_filter={"user_name": [f"keep-{self.marker}"]},
            max_age_days=30,
            mode=RetentionRuleModeChoices.MODE_EXCLUDE,
            weight=200,
            scoped=False,
        )

        self.run_job()

        self.assertTrue(ObjectChange.objects.filter(pk=protected.pk).exists())
        self.assertFalse(ObjectChange.objects.filter(pk=doomed.pk).exists())
        self.assertTrue(self.logger.said("protected by an exclude rule"))

    def test_object_type_scoped_filter(self):
        """A rule scoped by changed object type, per the acceptance criteria."""
        other_type = ContentType.objects.exclude(pk=self.content_type.pk).first()
        mine = self.make_object_change(action=ObjectChangeActionChoices.ACTION_UPDATE)
        theirs = self.make_object_change(action=ObjectChangeActionChoices.ACTION_UPDATE)
        ObjectChange.objects.filter(pk=theirs.pk).update(changed_object_type=other_type)
        self.make_rule(scope_filter={"changed_object_type_id": [str(self.content_type.pk)]}, max_age_days=30)

        self.run_job()

        self.assertFalse(ObjectChange.objects.filter(pk=mine.pk).exists())
        self.assertTrue(ObjectChange.objects.filter(pk=theirs.pk).exists())

    def test_dry_run_reports_without_deleting(self):
        change = self.make_object_change()
        self.make_rule(scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]}, max_age_days=30)

        result = self.run_job(dry_run=True)

        # The count it would delete, flagged as a dry run -- a summary reading 0 answers the wrong question.
        self.assertEqual(result, {"extras.ObjectChange": 1, "dry_run": True})
        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())
        self.assertTrue(self.logger.said("Dry run: would delete 1"))

    def test_only_exclude_rules_says_why_nothing_was_selected(self):
        """
        Exclude rules sit in the same picker as include rules, so choosing only those is easy to do.

        The arithmetic answer is a bare zero, which reads as a broken job rather than as "you picked the
        rules that protect records, and none that select them".
        """
        self.make_object_change(action=ObjectChangeActionChoices.ACTION_DELETE, time=OLD_TIME)
        self.make_rule(
            mode=RetentionRuleModeChoices.MODE_EXCLUDE,
            scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]},
        )

        result = self.run_job()

        self.assertEqual(result, {"extras.ObjectChange": 0})
        self.assertTrue(self.logger.said("No include rule was applied"))
        self.assertTrue(self.logger.said("at least one include rule has to select them first"))

    def test_every_enabled_rule_applies_including_protections(self):
        """
        There is no per-run rule selection, so a protection cannot be left out of one.

        The job used to offer a picker, and narrowing it withdrew the protection of any exclude rule not
        chosen -- deleting records something else was protecting, with the records' absence as the only
        evidence. `RetentionRule.enabled` is the only control now.

        Protected and doomed differ by action rather than by user, because the fixture helpers scope both
        the records and the rules by `user_name`; distinguishing on it would leave the include rule not
        matching the protected record at all, and the test would pass without the protection doing anything.
        """
        protected = self.make_object_change(action=ObjectChangeActionChoices.ACTION_UPDATE, time=OLD_TIME)
        doomed = self.make_object_change(action=ObjectChangeActionChoices.ACTION_DELETE, time=OLD_TIME)
        self.make_rule(
            scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE, ObjectChangeActionChoices.ACTION_UPDATE]},
            max_age_days=30,
        )
        self.make_rule(
            mode=RetentionRuleModeChoices.MODE_EXCLUDE,
            scope_filter={"action": [ObjectChangeActionChoices.ACTION_UPDATE]},
        )

        result = self.run_job()

        self.assertEqual(result, {"extras.ObjectChange": 1})
        self.assertTrue(ObjectChange.objects.filter(pk=protected.pk).exists())
        self.assertFalse(ObjectChange.objects.filter(pk=doomed.pk).exists())

    def test_a_disabled_rule_does_not_apply(self):
        """
        The rule's own switch decides, so disabling a protection really does remove it.

        The counterpart to the test above: same fixture, exclude rule disabled, and the record it would
        have protected is deleted. Without this, that test could pass because the include rule never
        selected the record rather than because the protection held.
        """
        exposed = self.make_object_change(action=ObjectChangeActionChoices.ACTION_UPDATE, time=OLD_TIME)
        doomed = self.make_object_change(action=ObjectChangeActionChoices.ACTION_DELETE, time=OLD_TIME)
        self.make_rule(
            scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE, ObjectChangeActionChoices.ACTION_UPDATE]},
            max_age_days=30,
        )
        self.make_rule(
            mode=RetentionRuleModeChoices.MODE_EXCLUDE,
            scope_filter={"action": [ObjectChangeActionChoices.ACTION_UPDATE]},
            enabled=False,
        )

        result = self.run_job()

        self.assertEqual(result, {"extras.ObjectChange": 2})
        self.assertFalse(ObjectChange.objects.filter(pk=exposed.pk).exists())
        self.assertFalse(ObjectChange.objects.filter(pk=doomed.pk).exists())

    def test_deletes_in_bounded_increments(self):
        """Deletion is always incremental, never one statement, however small the batch size."""
        for _ in range(5):
            self.make_object_change()
        self.make_rule(scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]}, max_age_days=30)

        result = self.run_job(batch_size=2)

        self.assertEqual(result, {"extras.ObjectChange": 5})
        increments = [message for message in self.logger.messages if message.startswith("Increment ")]
        self.assertEqual(len(increments), 3, f"5 records at batch_size=2 is 3 increments, got {increments}")
        self.assertEqual(ObjectChange.objects.filter(time=OLD_TIME).count(), 0)

    def test_requires_delete_permission(self):
        ObjectPermission.objects.all().delete()
        self.clear_permission_cache()
        change = self.make_object_change()
        self.make_rule(scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]}, max_age_days=30)

        with self.assertRaises(PermissionDenied):
            self.run_job()

        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())
        self.assertTrue(self.logger.said("does not have permission to delete extras.ObjectChange"))

    def test_invalid_filter_is_refused_not_widened(self):
        """
        A rule whose filter does not validate must delete nothing.

        Widening an unparseable filter to "everything" would delete records the operator never selected,
        which is the one failure mode this job cannot have.
        """
        change = self.make_object_change(action=ObjectChangeActionChoices.ACTION_UPDATE)
        self.make_rule(scope_filter={"action": ["not-a-real-action"]}, max_age_days=30)

        result = self.run_job()

        self.assertEqual(result, {"extras.ObjectChange": 0})
        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())
        self.assertTrue(self.logger.said("invalid filter parameters"))

    def test_rule_with_neither_filter_nor_age_is_skipped(self):
        """An empty rule would select every record, so it is skipped rather than obeyed."""
        change = self.make_object_change()
        self.make_rule(scope_filter={}, max_age_days=None, scoped=False)

        self.run_job()

        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())
        self.assertTrue(self.logger.said("neither a filter nor an age bound"))

    def test_disabled_rules_are_not_applied(self):
        change = self.make_object_change()
        self.make_rule(
            scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]}, max_age_days=30, enabled=False
        )

        result = self.run_job()

        self.assertEqual(result, {})
        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())

    def test_uncovered_content_type_is_skipped(self):
        self.make_rule(content_type=ContentType.objects.get_for_model(RetentionRule), scope_filter={"name": ["x"]})

        self.run_job()

        self.assertTrue(self.logger.said("not covered by changelog retention"))

    @override_settings(CHANGELOG_ARCHIVE_ENABLED=False)
    def test_works_with_rotation_unconfigured(self):
        """With retention off, truncation deletes what it selects and consults no period at all."""
        change = self.make_object_change()
        self.make_rule(scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]}, max_age_days=30)

        self.run_job()

        self.assertFalse(ObjectChange.objects.filter(pk=change.pk).exists())

    @override_settings(CHANGELOG_ARCHIVE_ENABLED=True, CHANGELOG_WARM_WINDOW_DAYS=90)
    def test_withholds_records_rotation_has_not_moved_yet(self):
        """
        A record old enough to rotate, in a period that is not closed, is rotation's to move.

        Deleting it first would lose it permanently, so truncation withholds it and says why. This is what
        makes the two jobs safe to run in either order.
        """
        change = self.make_object_change()
        self.make_rule(scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]}, max_age_days=30)

        self.run_job()

        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())
        self.assertTrue(self.logger.said("rotation job's to move"))

    @override_settings(CHANGELOG_ARCHIVE_ENABLED=True, CHANGELOG_WARM_WINDOW_DAYS=90)
    def test_deletes_leftovers_once_the_period_is_closed(self):
        """A closed period has been fully rotated, so its warm leftovers are safe to delete."""
        change = self.make_object_change()
        self.make_rule(scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]}, max_age_days=30)
        ArchiveSegment.objects.create(
            model_label="extras.objectchange",
            period_key="2020",
            label="2020",
            time_start=datetime(2020, 1, 1, tzinfo=dt_timezone.utc),
            time_end=datetime(2021, 1, 1, tzinfo=dt_timezone.utc),
            is_period_closed=True,
        )

        self.run_job()

        self.assertFalse(ObjectChange.objects.filter(pk=change.pk).exists())

    @override_settings(CHANGELOG_ARCHIVE_ENABLED=True, CHANGELOG_WARM_WINDOW_DAYS=90)
    def test_records_inside_the_warm_window_are_never_withheld(self):
        """Rotation only moves records past the warm window, so newer ones are truncation's alone."""
        change = self.make_object_change(time=datetime.now(dt_timezone.utc) - timedelta(days=2))
        # No age bound, or the rule would not select a two-day-old record and this would pass for the
        # wrong reason.
        self.make_rule(scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]})

        self.run_job()

        self.assertFalse(ObjectChange.objects.filter(pk=change.pk).exists())
        self.assertFalse(self.logger.said("rotation job's to move"))


class ChangelogTruncationIntegrationTestCase(ChangelogTruncationTestMixin, TransactionTestCase):
    """
    The job runs end to end through the real Celery path.

    Asserts database state only. `JobLogEntry` rows are written through the separate `job_logs`
    connection, which cannot see a `JobResult` still inside the enqueueing transaction, so log presence is
    not assertable here. Messaging is covered by the unit layer above.
    """

    databases = ("default", "job_logs")

    def setUp(self):
        super().setUp()
        self.content_type = ContentType.objects.get_for_model(ObjectChange)
        self.marker = f"user-{uuid.uuid4().hex[:8]}"

    def test_end_to_end_deletes_selected_records(self):
        self.grant_delete()
        doomed = self.make_object_change(action=ObjectChangeActionChoices.ACTION_DELETE)
        spared = self.make_object_change(action=ObjectChangeActionChoices.ACTION_UPDATE)
        self.make_rule(scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]}, max_age_days=30)

        job_result = create_job_result_and_run_job(MODULE, JOB_CLASS, username=self.user.username, dry_run=False)

        self.assertJobResultStatus(job_result)
        self.assertFalse(ObjectChange.objects.filter(pk=doomed.pk).exists())
        self.assertTrue(ObjectChange.objects.filter(pk=spared.pk).exists())

    def test_end_to_end_dry_run_changes_nothing(self):
        self.grant_delete()
        change = self.make_object_change()
        self.make_rule(scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]}, max_age_days=30)

        job_result = create_job_result_and_run_job(MODULE, JOB_CLASS, username=self.user.username, dry_run=True)

        self.assertJobResultStatus(job_result)
        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())

    def test_end_to_end_without_permission_fails_and_deletes_nothing(self):
        change = self.make_object_change()
        self.make_rule(scope_filter={"action": [ObjectChangeActionChoices.ACTION_DELETE]}, max_age_days=30)

        job_result = create_job_result_and_run_job(MODULE, JOB_CLASS, username=self.user.username, dry_run=False)

        self.assertJobResultStatus(job_result, JobResultStatusChoices.STATUS_FAILURE)
        self.assertTrue(ObjectChange.objects.filter(pk=change.pk).exists())


class RetentionRuleModelTestCase(TestCase):
    """`RetentionRule` is change-logged, because it decides what gets deleted."""

    def test_edits_are_change_logged(self):
        rule = RetentionRule.objects.create(
            name="audited", content_type=ContentType.objects.get_for_model(JobResult), max_age_days=10
        )
        self.assertIsNotNone(rule.created)
        self.assertIsNotNone(rule.last_updated)

    def test_natural_key_is_the_name(self):
        rule = RetentionRule.objects.create(
            name="by-name", content_type=ContentType.objects.get_for_model(JobResult), max_age_days=10
        )
        self.assertEqual(rule.natural_key(), ["by-name"])

    def test_a_covered_content_type_is_accepted(self):
        for model in (ObjectChange, JobResult):
            with self.subTest(model=model.__name__):
                rule = RetentionRule(
                    name=f"covered-{model.__name__}",
                    content_type=ContentType.objects.get_for_model(model),
                    max_age_days=10,
                )
                rule.validated_save()

    def test_a_scope_filter_the_filterset_rejects_is_refused(self):
        """
        Truncation refuses such a rule at run time, which is safe but late.

        Before this the REST API would store a filter the edit form would not let you save, leaving a rule
        that looked enabled and quietly did nothing until someone read a job log.
        """
        rule = RetentionRule(
            name="bad-filter",
            content_type=ContentType.objects.get_for_model(ObjectChange),
            scope_filter={"action": ["not-a-real-action"]},
            max_age_days=10,
        )

        with self.assertRaises(ValidationError) as context:
            rule.validated_save()

        self.assertIn("scope_filter", context.exception.message_dict)

    def test_a_valid_scope_filter_is_accepted(self):
        """The demo fixture's own filters have to survive this, or the command stops working."""
        for scope_filter in (
            {"action": [ObjectChangeActionChoices.ACTION_DELETE]},
            {"action": [ObjectChangeActionChoices.ACTION_DELETE], "change_context_detail": ["retention-demo"]},
            {"user_name": ["carol"]},
            {},
        ):
            with self.subTest(scope_filter=scope_filter):
                RetentionRule(
                    name=f"valid-{hash(str(scope_filter))}",
                    content_type=ContentType.objects.get_for_model(ObjectChange),
                    scope_filter=scope_filter,
                    max_age_days=10,
                ).validated_save()

    def test_an_uncovered_content_type_is_refused(self):
        """
        A rule for a model retention does not cover would save fine and never apply.

        Truncation only walks the covered models, so the rule would sit in the list looking enabled while
        deleting nothing. The failure is silent, which is what makes it worth refusing at the form.
        """
        rule = RetentionRule(
            name="uncovered",
            content_type=ContentType.objects.get_for_model(Location),
            max_age_days=10,
        )

        with self.assertRaises(ValidationError) as context:
            rule.validated_save()

        self.assertIn("content_type", context.exception.message_dict)
        self.assertIn("does not cover dcim.location", str(context.exception))


class ArchiveSegmentModelTestCase(TestCase):
    """A segment names a span of time, so the span has to be one."""

    databases = ["default", CHANGELOG_ARCHIVE]

    def make_segment(self, *, time_start, time_end):
        return ArchiveSegment(
            model_label="extras.objectchange",
            period_key="2024",
            label="2024",
            time_start=time_start,
            time_end=time_end,
        )

    def test_a_period_that_spans_time_is_accepted(self):
        self.make_segment(
            time_start=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            time_end=datetime(2025, 1, 1, tzinfo=dt_timezone.utc),
        ).validated_save()

    def test_an_end_before_the_start_is_refused(self):
        segment = self.make_segment(
            time_start=datetime(2025, 1, 1, tzinfo=dt_timezone.utc),
            time_end=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
        )

        with self.assertRaises(ValidationError) as context:
            segment.validated_save()

        self.assertIn("time_end", context.exception.message_dict)

    def test_an_empty_period_is_refused(self):
        """
        `time_start` is inclusive and `time_end` exclusive, so an equal pair holds nothing.

        Rotation would still file records against it, and reconciliation would then report every one of
        them as sitting outside its own period, which reads as corruption instead of a bad segment.
        """
        moment = datetime(2024, 1, 1, tzinfo=dt_timezone.utc)
        segment = self.make_segment(time_start=moment, time_end=moment)

        with self.assertRaises(ValidationError) as context:
            segment.validated_save()

        self.assertIn("time_end", context.exception.message_dict)
