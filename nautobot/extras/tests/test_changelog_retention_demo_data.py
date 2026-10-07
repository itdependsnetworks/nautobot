"""
The demo-data command has to actually produce data that exercises the feature.

It exists so retention can be tried by hand, and every property asserted here is one that was missing at
some point and made the feature look broken when it was not: a diff panel with nothing to diff, a
related changes panel with no siblings, a console tab with no output. A generator that produces flat,
uniform, or incoherent data is worse than no generator, because what it shows gets mistaken for a bug in
the thing being tested.
"""

from io import StringIO
from itertools import pairwise

from django.core.management import call_command

from nautobot.core.testing import TestCase
from nautobot.extras.choices import ObjectChangeActionChoices
from nautobot.extras.management.commands.create_changelog_retention_demo_data import (
    CHANGES_PER_YEAR,
    DEMO_USERS,
    MARKER,
    YEARS,
)
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    JobResult,
    ObjectChange,
)
from nautobot.users.models import ObjectPermission, User

# `override_config` for the two runtime knobs the command still writes. Constance config is cached in
# memory and survives the per-test database rollback, so left to leak it changes what a later suite sees.
# The capability itself is `override_settings`, because it is a deployment setting now rather than
# something the command can turn on.


class CreateChangelogRetentionDemoDataTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self._clear_retained_history()

    def tearDown(self):
        # Cleared on the way out as well as in. Retained history is written through a second connection,
        # so `TestCase`'s per-test transaction on `default` does not roll it back and whatever this suite
        # leaves behind is still there for the next one.
        self._clear_retained_history()
        super().tearDown()

    @staticmethod
    def _clear_retained_history():
        for mirror in (ArchivedObjectChange, ArchivedJobLogEntry, ArchivedJobConsoleEntry, ArchivedJobResult):
            mirror.objects.all().delete()

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
        # Nothing was rotated, so the retained table is empty.
        self.assertEqual(self.retained_demo_changes().count(), 0)

    def test_history_is_backdated_across_every_year(self):
        """Records dated inside the warm window would never rotate, so the whole thing would show nothing."""
        self.run_command("--no-rotate")

        years = {change.time.year for change in self.demo_changes()}
        self.assertEqual(years, set(YEARS))

    def test_counts_differ_per_year(self):
        """
        Equal counts make the UI unreadable, not wrong.

        When a year's total, an object's own history, and the page size are the same number, a
        disagreement between them is invisible, which is how a real off-by-three went unnoticed.
        """
        self.run_command("--no-rotate")

        per_year = {}
        for change in self.demo_changes():
            per_year[change.time.year] = per_year.get(change.time.year, 0) + 1

        self.assertEqual(len(set(per_year.values())), len(YEARS))

    def test_rotation_moves_every_year_into_retained_storage(self):
        """
        Every fabricated year is moved into the retained table, and the count matches what is there.
        """
        self.run_command()

        self.assertEqual(self.retained_demo_changes().count(), sum(CHANGES_PER_YEAR))
        self.assertEqual(self.demo_changes().count(), 0)
        self.assertEqual({record.time.year for record in self.retained_demo_changes()}, set(YEARS))

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
        self.assertEqual(
            archivist - viewer,
            {
                "extras.view_archivedobjectchange",
                "extras.view_archivedjobresult",
                "extras.view_archivedjoblogentry",
                "extras.view_archivedjobconsoleentry",
            },
        )
        self.assertEqual(viewer - archivist, set())

    def test_rerunning_with_flush_does_not_accumulate(self):
        self.run_command()
        first = self.retained_demo_changes().count()

        self.run_command("--flush")

        self.assertEqual(self.retained_demo_changes().count(), first)
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
        before = self.retained_demo_changes().count()

        output = self.run_command("--status")

        self.assertEqual(self.retained_demo_changes().count(), before)
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
