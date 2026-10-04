"""
The demo-data command has to actually produce data that exercises the feature.

It exists so retention can be tried by hand, and every property asserted here is one that was missing at
some point and made the feature look broken when it was not: a diff panel with nothing to diff, a related
changes panel with no siblings, a console tab with no output. A generator that produces flat, uniform or
incoherent data is worse than no generator, because what it shows gets mistaken for a bug in the thing
being tested.
"""

from io import StringIO
from itertools import pairwise

from django.contrib.auth import get_user_model
from django.core.management import call_command

from nautobot.core.testing import TestCase
from nautobot.extras.choices import ObjectChangeActionChoices
from nautobot.extras.management.commands.create_changelog_retention_demo_data import (
    DEMO_USERS,
    MARKER,
)
from nautobot.extras.models import JobConsoleEntry, JobLogEntry, JobResult, ObjectChange


class CreateChangelogRetentionDemoDataTestCase(TestCase):
    def run_command(self, *args):
        output = StringIO()
        call_command("create_changelog_retention_demo_data", *args, stdout=output, stderr=output)
        return output.getvalue()

    def demo_changes(self):
        return ObjectChange.objects.filter(change_context_detail=MARKER)

    def test_history_is_coherent_per_object(self):
        """
        The difference panel diffs a record against the previous change to the same object.

        So an object cannot be created twice, and consecutive payloads have to actually differ, or every
        diff on the instance reads "No changes" and the panel looks broken.
        """
        self.run_command()

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
        self.run_command()

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

        results = JobResult.objects.filter(name__startswith=MARKER)
        self.assertGreater(results.count(), 0)
        self.assertGreater(JobLogEntry.objects.filter(message__startswith=MARKER).count(), 0)
        with_console = set(
            JobConsoleEntry.objects.filter(text__startswith=MARKER).values_list("job_result_id", flat=True)
        )
        all_results = set(results.values_list("pk", flat=True))
        self.assertTrue(with_console)
        self.assertTrue(all_results - with_console, "every result has console output, so the empty case is unseen")

    def test_rerunning_with_flush_does_not_accumulate(self):
        self.run_command()
        first = self.demo_changes().count()

        self.run_command("--flush")

        self.assertEqual(self.demo_changes().count(), first)
        self.assertEqual(get_user_model().objects.filter(username__in=DEMO_USERS).count(), len(DEMO_USERS))

    def test_status_changes_nothing(self):
        self.run_command()
        before = self.demo_changes().count()

        output = self.run_command("--status")

        self.assertEqual(self.demo_changes().count(), before)
        self.assertIn("Warm change records", output)

    def test_the_seed_makes_a_run_reproducible(self):
        self.run_command()
        first = sorted(
            (change.time, change.user_name, change.action, change.object_repr) for change in self.demo_changes()
        )

        self.run_command("--flush")
        second = sorted(
            (change.time, change.user_name, change.action, change.object_repr) for change in self.demo_changes()
        )

        self.assertEqual(first, second)

    def test_a_different_seed_makes_different_history(self):
        self.run_command()
        first = sorted((change.time, change.user_name) for change in self.demo_changes())

        self.run_command("--flush", "--seed", "1234")
        second = sorted((change.time, change.user_name) for change in self.demo_changes())

        self.assertNotEqual(first, second)
