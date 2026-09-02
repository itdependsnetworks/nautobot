"""
The demo-data command has to actually produce data that exercises the feature.

It exists so retention can be tried by hand, and every property asserted here is one that was missing at
some point and made the feature look broken when it was not: a diff panel with nothing to diff, a related
changes panel with no siblings, a console tab with no output, a truncation run with no enabled rules. A
generator that produces flat, uniform, or incoherent data is worse than no generator, because what it shows
gets mistaken for a bug in the thing being tested.
"""

from io import StringIO
from itertools import pairwise

from constance.test import override_config
from django.core.management import call_command
from django.test import override_settings

from nautobot.core.constants import CHANGELOG_ARCHIVE
from nautobot.core.testing import TestCase
from nautobot.extras.choices import JobResultStatusChoices, ObjectChangeActionChoices
from nautobot.extras.management.commands.create_changelog_retention_demo_data import (
    CHANGES_PER_YEAR,
    DEMO_USERS,
    MARKER,
    TRUNCATION_DELETABLE,
    TRUNCATION_FAILED_RESULTS,
    TRUNCATION_MARKER,
    TRUNCATION_PROTECTED,
    TRUNCATION_UNTOUCHED,
    YEARS,
)
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    ArchiveSegment,
    JobResult,
    ObjectChange,
    RetentionRule,
)
from nautobot.users.models import ObjectPermission, User


# `override_config`, not just `override_settings`: the command turns retention on by writing Constance
# config, which is cached in memory and so survives the per-test database rollback. Left to leak, it
# switches retention on for every suite that runs afterwards -- which changes what truncation withholds,
# and was quietly failing eleven of its tests.
@override_config(CHANGELOG_ARCHIVE_ENABLED=True, CHANGELOG_WARM_WINDOW_DAYS=90, CHANGELOG_ARCHIVE_PERIOD="year")
@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class CreateChangelogRetentionDemoDataTestCase(TestCase):
    databases = ["default", CHANGELOG_ARCHIVE]

    def setUp(self):
        super().setUp()
        self._clear_retained_history()

    def tearDown(self):
        # Cleared on the way out as well as in. Retained history is written through a second connection, so
        # `TestCase`'s per-test transaction on `default` does not roll it back, and what this suite leaves
        # behind is not inert: truncation reads `ArchiveSegment` to decide which warm records rotation has
        # not moved yet, so a leftover period changes what a later suite's truncation withholds.
        self._clear_retained_history()
        super().tearDown()

    @staticmethod
    def _clear_retained_history():
        for model in (ArchivedObjectChange, ArchivedJobLogEntry, ArchivedJobConsoleEntry, ArchivedJobResult):
            model.objects.all().delete()
        ArchiveSegment.objects.all().delete()

    def run_command(self, *args):
        output = StringIO()
        call_command("create_changelog_retention_demo_data", *args, stdout=output, stderr=output)
        return output.getvalue()

    def demo_changes(self):
        return ObjectChange.objects.filter(change_context_detail=MARKER)

    def retained_demo_changes(self):
        """
        Scoped to the marker, because rotation is unfiltered by design.

        It moves every record past the warm window, including the test database's own change history, so an
        unscoped count here measures the fixture rather than the command.
        """
        return ArchivedObjectChange.objects.filter(change_context_detail=MARKER)

    def retained_demo_results(self):
        return ArchivedJobResult.objects.filter(name__startswith=MARKER)

    def test_generates_warm_history_without_rotating_it(self):
        self.run_command("--no-rotate")

        self.assertEqual(self.demo_changes().count(), sum(CHANGES_PER_YEAR))
        self.assertEqual(ArchivedObjectChange.objects.count(), 0)
        self.assertEqual(ArchiveSegment.objects.count(), 0)

    def test_history_is_backdated_into_every_period(self):
        """Records dated inside the warm window would never rotate, so the whole thing would show nothing."""
        self.run_command("--no-rotate")

        years = {change.time.year for change in self.demo_changes()}
        self.assertEqual(years, set(YEARS))

    def test_counts_differ_per_period(self):
        """
        Equal counts make the UI unreadable rather than wrong.

        When a period's total, an object's own history, and the page size are the same number, a
        disagreement between them is invisible -- which is how a real off-by-three went unnoticed.
        """
        self.run_command("--no-rotate")

        per_year = {}
        for change in self.demo_changes():
            per_year[change.time.year] = per_year.get(change.time.year, 0) + 1

        self.assertEqual(len(set(per_year.values())), len(YEARS))

    def test_rotation_fills_the_periods(self):
        self.run_command()

        self.assertEqual(self.retained_demo_changes().count(), sum(CHANGES_PER_YEAR))
        self.assertEqual(self.demo_changes().count(), 0)
        periods = set(self.retained_demo_changes().values_list("period_key", flat=True))
        self.assertEqual(periods, {str(year) for year in YEARS})
        for segment in ArchiveSegment.objects.filter(model_label="extras.objectchange"):
            with self.subTest(period=segment.period_key):
                actual = ArchivedObjectChange.objects.filter(period_key=segment.period_key).count()
                self.assertEqual(segment.row_count, actual)

    def test_history_is_coherent_per_object(self):
        """
        The difference panel diffs a record against the previous change to the same object.

        So an object cannot be created twice, and consecutive payloads have to actually differ, or every
        diff on the instance reads "No changes" and the panel looks broken.
        """
        self.run_command("--no-rotate")

        by_object = {}
        for change in self.demo_changes().order_by("time"):
            by_object.setdefault((change.changed_object_type_id, change.changed_object_id), []).append(change)

        diffs_found = 0
        for history in by_object.values():
            actions = [change.action for change in history]
            with self.subTest(object_id=history[0].changed_object_id):
                self.assertEqual(actions.count(ObjectChangeActionChoices.ACTION_CREATE), 1)
                self.assertEqual(actions[0], ObjectChangeActionChoices.ACTION_CREATE)
                # A delete can only be last, since nothing happens to an object after it is deleted.
                for index, action in enumerate(actions[:-1]):
                    self.assertNotEqual(action, ObjectChangeActionChoices.ACTION_DELETE, f"delete at {index}")
            for earlier, later in pairwise(history):
                if later.action == ObjectChangeActionChoices.ACTION_UPDATE:
                    self.assertNotEqual(earlier.object_data_v2, later.object_data_v2)
                    diffs_found += 1
        self.assertGreater(diffs_found, 0, "no update has a differing predecessor, so no diff can be shown")

    def test_some_requests_touch_an_object_more_than_once(self):
        """Related changes means siblings in the same request; without any, that panel is always empty."""
        self.run_command("--no-rotate")

        grouped = {}
        for change in self.demo_changes():
            key = (change.request_id, change.changed_object_type_id, change.changed_object_id)
            grouped[key] = grouped.get(key, 0) + 1

        self.assertTrue(any(count > 1 for count in grouped.values()))

    def test_job_history_has_logs_and_some_console_output(self):
        """
        Console output on some results and not others.

        With none, the console tab is blank and reads as broken; with it everywhere, the genuinely-empty
        case is never seen.
        """
        self.run_command()

        self.assertGreater(self.retained_demo_results().count(), 0)
        self.assertGreater(ArchivedJobLogEntry.objects.filter(message__startswith=MARKER).count(), 0)
        with_console = set(
            ArchivedJobConsoleEntry.objects.filter(text__startswith=MARKER).values_list("job_result_id", flat=True)
        )
        all_results = set(self.retained_demo_results().values_list("pk", flat=True))
        self.assertTrue(with_console)
        self.assertTrue(all_results - with_console, "every result has console output, so the empty case is unseen")

    def test_rules_cover_both_modes_and_both_enabled_states(self):
        """The truncation job's picker lists enabled rules only, so with none enabled it looks broken."""
        self.run_command()

        rules = RetentionRule.objects.filter(name__startswith=MARKER)
        self.assertTrue(rules.filter(enabled=True).exists())
        self.assertTrue(rules.filter(enabled=False).exists())
        self.assertEqual({rule.mode for rule in rules}, {"include", "exclude"})
        for rule in rules:
            with self.subTest(rule=rule.name):
                self.assertTrue(rule.scope_filter, "a rule with no filter is skipped rather than applied")

    def test_the_two_users_differ_only_in_cold_storage(self):
        """That difference is the whole point of having two of them."""
        self.run_command()

        granted = {}
        for username in DEMO_USERS:
            user = User.objects.get(username=username)
            granted[username] = {
                f"{content_type.app_label}.{action}_{content_type.model}"
                for permission in ObjectPermission.objects.filter(users=user)
                for action in permission.actions
                for content_type in permission.object_types.all()
            }

        viewer, archivist = granted["retention-viewer"], granted["retention-archivist"]
        self.assertEqual(archivist - viewer, {"extras.view_archivesegment"})
        self.assertEqual(viewer - archivist, set())

    def test_rerunning_with_flush_does_not_accumulate(self):
        self.run_command()
        first = self.retained_demo_changes().count()

        self.run_command("--flush")

        self.assertEqual(self.retained_demo_changes().count(), first)
        self.assertEqual(RetentionRule.objects.filter(name__startswith=MARKER).count(), 3)
        self.assertEqual(User.objects.filter(username__in=DEMO_USERS).count(), len(DEMO_USERS))

    def test_teardown_removes_only_what_it_created(self):
        """Keyed on the marker throughout, so a record the command did not create is never touched."""
        keeper = ObjectChange.objects.create(
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type=self.changed_object_type(),
            changed_object_id=self.some_object_id(),
            object_repr="Not demo data",
            object_data={},
            request_id="11111111-1111-1111-1111-111111111111",
            user_name="someone-else",
            change_context="orm",
        )
        keeper_result = JobResult.objects.create(name="A real job result")
        self.run_command()

        self.run_command("--teardown")

        self.assertTrue(ObjectChange.objects.filter(pk=keeper.pk).exists())
        self.assertTrue(JobResult.objects.filter(pk=keeper_result.pk).exists())
        self.assertEqual(self.retained_demo_changes().count(), 0)
        self.assertEqual(self.retained_demo_results().count(), 0)
        self.assertEqual(RetentionRule.objects.filter(name__startswith=MARKER).count(), 0)
        self.assertEqual(User.objects.filter(username__in=DEMO_USERS).count(), 0)

    def test_teardown_reports_counts_that_are_not_inflated_by_cascades(self):
        """
        `delete()[0]` counts cascaded rows too, so deleting 17 job results reported 120.

        The whole feature is about counts a reader can trust, so its own tooling should not overstate them.
        """
        self.run_command()
        results = self.retained_demo_results().count()

        output = self.run_command("--teardown")

        self.assertIn(f"{results:6} extras.ArchivedJobResult", output)
        # Many-to-many through tables are an artifact of how permissions are stored, not created records.
        self.assertNotIn("ObjectPermission_users", output)

    def test_status_changes_nothing(self):
        self.run_command()
        before = (self.retained_demo_changes().count(), RetentionRule.objects.count())

        output = self.run_command("--status")

        self.assertEqual((self.retained_demo_changes().count(), RetentionRule.objects.count()), before)
        self.assertIn("Retained change records", output)

    def test_the_seed_makes_a_run_reproducible(self):
        self.run_command("--no-rotate")
        first = sorted(
            (change.time, change.user_name, change.action, change.object_repr) for change in self.demo_changes()
        )

        self.run_command("--flush", "--no-rotate")
        second = sorted(
            (change.time, change.user_name, change.action, change.object_repr) for change in self.demo_changes()
        )

        self.assertEqual(first, second)

    def test_a_different_seed_makes_different_history(self):
        self.run_command("--no-rotate")
        first = sorted((change.time, change.user_name) for change in self.demo_changes())

        self.run_command("--flush", "--no-rotate", "--seed", "1234")
        second = sorted((change.time, change.user_name) for change in self.demo_changes())

        self.assertNotEqual(first, second)

    # Helpers

    def changed_object_type(self):
        from django.contrib.contenttypes.models import ContentType

        from nautobot.dcim.models import Location

        return ContentType.objects.get_for_model(Location)

    def some_object_id(self):
        from nautobot.dcim.models import Location

        return Location.objects.first().pk


@override_config(CHANGELOG_ARCHIVE_ENABLED=True, CHANGELOG_WARM_WINDOW_DAYS=90, CHANGELOG_ARCHIVE_PERIOD="year")
@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class DemoDataTruncationTestCase(CreateChangelogRetentionDemoDataTestCase):
    """
    The enabled rules have to have something to delete after a default run.

    They did not. Everything the command created was backdated past the warm window and then rotated, and
    the include rule's age bound was above the window -- so every record it could match had already been
    moved out of warm storage. Running truncation to see the feature work deleted nothing, or worse, only
    matched the change history `generate_test_data` created, because the rules were unscoped.
    """

    def truncate(self, dry_run=False):
        from nautobot.core.jobs.retention import ChangelogTruncation
        from nautobot.extras.tests.test_changelog_truncation import RecordingLogger, StubJobResult

        self.user.is_superuser = True
        self.user.save()
        job = ChangelogTruncation()
        job.logger = RecordingLogger()
        job.job_result = StubJobResult(self.user)
        return job.run(batch_size=10000, dry_run=dry_run), job.logger

    def candidates(self, **kwargs):
        return ObjectChange.objects.filter(change_context_detail=TRUNCATION_MARKER, **kwargs)

    def test_candidates_survive_rotation(self):
        """They are inside the warm window, which is the whole point -- rotation must leave them."""
        self.run_command()

        remaining = self.candidates()
        self.assertEqual(remaining.count(), TRUNCATION_DELETABLE + TRUNCATION_PROTECTED + TRUNCATION_UNTOUCHED)
        self.assertEqual(self.retained_demo_changes().count(), sum(CHANGES_PER_YEAR))

    def test_the_enabled_rules_delete_exactly_the_deletable_group(self):
        self.run_command()
        before = self.candidates().count()

        result, _logger = self.truncate()

        self.assertEqual(result.get("extras.ObjectChange"), TRUNCATION_DELETABLE)
        self.assertEqual(self.candidates().count(), before - TRUNCATION_DELETABLE)

    def test_the_exclude_rule_saves_carols_records(self):
        """Both groups are delete-action and both match the include rule; only one survives."""
        self.run_command()

        self.truncate()

        self.assertEqual(self.candidates(user_name="carol").count(), TRUNCATION_PROTECTED)
        self.assertEqual(self.candidates(action=ObjectChangeActionChoices.ACTION_DELETE).count(), TRUNCATION_PROTECTED)

    def test_records_the_filter_does_not_select_are_untouched(self):
        self.run_command()

        self.truncate()

        self.assertEqual(self.candidates(action=ObjectChangeActionChoices.ACTION_UPDATE).count(), TRUNCATION_UNTOUCHED)

    def test_a_dry_run_reports_the_number_it_would_delete(self):
        """A dry run exists to answer "how much would this do", so the summary has to carry the number."""
        self.run_command()
        before = self.candidates().count()

        result, logger = self.truncate(dry_run=True)

        self.assertEqual(result.get("extras.ObjectChange"), TRUNCATION_DELETABLE)
        self.assertTrue(result.get("dry_run"))
        self.assertTrue(logger.said(f"would delete {TRUNCATION_DELETABLE} extras.ObjectChange records"))
        self.assertEqual(self.candidates().count(), before)

    def test_the_rules_cannot_reach_records_this_command_did_not_create(self):
        """
        Unscoped, the include rule selected every old delete-action record in the database.

        A tester running truncation on a dev instance would have silently deleted the change history
        `generate_test_data` produced.
        """
        self.run_command()
        others = ObjectChange.objects.exclude(change_context_detail__startswith=MARKER)
        before = others.count()

        self.truncate()

        self.assertEqual(others.count(), before)

    def test_the_disabled_rule_leaves_its_job_results_alone_until_enabled(self):
        self.run_command()
        failed = JobResult.objects.filter(name__istartswith=MARKER, status=JobResultStatusChoices.STATUS_FAILURE)
        self.assertGreaterEqual(failed.count(), TRUNCATION_FAILED_RESULTS)

        self.truncate()
        self.assertGreaterEqual(failed.count(), TRUNCATION_FAILED_RESULTS)

        RetentionRule.objects.filter(name__startswith=MARKER, content_type__model="jobresult").update(enabled=True)
        self.truncate()

        self.assertEqual(failed.count(), 0)
