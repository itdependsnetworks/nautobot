"""
Generate everything needed to exercise changelog long-term retention by hand.

Retention is hard to try out on a fresh install: it only does anything to records older than the warm
window, so there is nothing to rotate until history has had months to accumulate. This fabricates that
history with backdated timestamps, then optionally rotates it, leaving an instance where every part of the
feature has something real to show -- retained periods to select, filters to apply within one, a rule to
run truncation with, and a user who may read retained history and one who may not.

Everything it creates carries MARKER, in `change_context_detail` for change records and in the name or text
for everything else, so `--flush` can find and remove all of it. It never touches a record it did not
create.

The fabricated history is deliberately lumpy. Uniform data makes the UI unreadable: when a period's total,
an object's own history, and the page size are all the same number, a disagreement between them is
invisible. The seed makes a re-run reproduce the same data.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone
import logging
import random
import uuid

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from nautobot.dcim.models import Device, Location
from nautobot.extras.choices import (
    JobConsoleEntryOutputTypeChoices,
    JobResultStatusChoices,
    LogLevelChoices,
    ObjectChangeActionChoices,
    RetentionRuleModeChoices,
)
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    ArchiveSegment,
    JobConsoleEntry,
    JobLogEntry,
    JobResult,
    ObjectChange,
    RetentionRule,
)
from nautobot.users.models import ObjectPermission

MARKER = "retention-demo"
#: The truncation candidates get their own marker. They are the one group that must be dated relative to
#: *now* rather than to a fixed year, so they are neither reproducible from the seed nor part of the
#: backdated history -- and every count and invariant over that history has to be able to exclude them.
TRUNCATION_MARKER = f"{MARKER}-truncation"

#: Years to fabricate history for. Each becomes its own retention period at `year` granularity.
YEARS = (2022, 2023, 2024, 2025)
#: One entry per year in YEARS. Uneven so a count in the UI can be traced to what it is counting.
CHANGES_PER_YEAR = (17, 63, 41, 28)
JOB_RESULTS_PER_YEAR = (3, 7, 5, 2)

#: Warm records the truncation rules can actually act on, and what each group is for. They sit *inside*
#: the warm window, so rotation leaves them where truncation can reach them -- anything older than the
#: window is rotated first, which is why an age bound above it can never match.
TRUNCATION_DELETABLE = 7  # delete-action, not carol: what an include rule selects
TRUNCATION_PROTECTED = 3  # delete-action by carol: selected by include, saved by the exclude rule
TRUNCATION_UNTOUCHED = 5  # update-action: proves the filter is selective
TRUNCATION_FAILED_RESULTS = 4  # failed job results the third rule selects, once enabled
TRUNCATION_PASSED_RESULTS = 2  # succeeded: left alone, so the status filter is visibly doing something
TRUNCATION_AGE_DAYS = 14  # the age bound the rules use; the records are older than this and still warm

DEFAULT_SEED = 20260820
#: Dev instances only. The command says so on every run.
DEMO_PASSWORD = "retention-demo-1234"  # noqa: S105

DEMO_USERS = ("retention-viewer", "retention-archivist")

User = get_user_model()


class _StubJobResult:
    """Stands in for the `JobResult` a running job reads its user from.

    Rotation is run in-process here rather than through a worker, so there is no real `JobResult` to read.
    """

    def __init__(self, user):
        self.user = user


class Command(BaseCommand):
    help = "Generate backdated history, retention rules, and users for exercising changelog retention by hand."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help=f"Remove what a previous run created (anything carrying '{MARKER}') before generating again.",
        )
        parser.add_argument(
            "--teardown",
            action="store_true",
            help="Remove what a previous run created, turn retention off, and generate nothing.",
        )
        parser.add_argument(
            "--no-rotate",
            action="store_false",
            dest="rotate",
            help=(
                "Stop after creating the warm history, without rotating it. Use this to see the state before "
                "rotation, or to run the Changelog Rotation job yourself from the UI."
            ),
        )
        parser.add_argument(
            "--status",
            action="store_true",
            help="Report what exists and change nothing.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=DEFAULT_SEED,
            help="Random seed, so a re-run reproduces the same history. Change it for a different shape.",
        )
        parser.add_argument(
            "--period",
            choices=["year", "quarter", "month"],
            default="year",
            help="Retention period granularity to configure. Defaults to year, which matches YEARS above.",
        )

    def handle(self, *args, **options):
        if options["status"]:
            self._report()
            return

        if options["teardown"]:
            self._flush()
            return

        if options["flush"]:
            self._flush()

        with transaction.atomic():
            self._configure(options["period"])
            self._object_changes(random.Random(options["seed"]))  # noqa: S311  # not cryptographic
            self._job_history(random.Random(options["seed"] + 1))  # noqa: S311  # not cryptographic
            self._truncation_candidates(random.Random(options["seed"] + 2))  # noqa: S311  # not cryptographic
            self._retention_rules()
            self._users()

        # Outside the transaction above on purpose: rotation manages its own per-increment transactions,
        # and wrapping it would undo the bounded-increment behaviour this command exists to demonstrate.
        if options["rotate"]:
            self._rotate()

        self._report()
        self.stdout.write(
            self.style.WARNING(
                f"Users '{DEMO_USERS[0]}' (no cold storage) and '{DEMO_USERS[1]}' (cold storage) share the "
                f"password '{DEMO_PASSWORD}'. Development instances only."
            )
        )

    # Setup

    def _configure(self, period):
        """Turn retention on, at the granularity the fabricated history is shaped for."""
        from constance import config

        config.CHANGELOG_ARCHIVE_ENABLED = True
        config.CHANGELOG_ARCHIVE_PERIOD = period
        config.CHANGELOG_WARM_WINDOW_DAYS = 90
        self.stdout.write(self.style.NOTICE(f"Retention enabled, period granularity {period}, warm window 90 days"))

    def _targets(self, rng):
        """
        Real devices and locations to attach the fabricated history to.

        Attached to real objects on purpose: it makes the period selector testable from an object's own
        Change Log tab, not only from the global list.
        """
        devices = list(Device.objects.all()[:12])
        locations = list(Location.objects.all()[:5])
        targets = [(ContentType.objects.get_for_model(Device), obj) for obj in devices]
        targets += [(ContentType.objects.get_for_model(Location), obj) for obj in locations]
        if not targets:
            raise CommandError(
                "No devices or locations to attach history to. Run `nautobot-server generate_test_data` first."
            )
        # Weighted so a couple of objects dominate and some barely appear, as real history does.
        weights = [rng.choice((1, 1, 2, 3, 8, 13)) for _ in targets]
        return targets, weights

    # Change records

    def _object_changes(self, rng):
        """Backdated change records, coherent per object so the difference panel has something to show."""
        targets, weights = self._targets(rng)
        # Uneven, so filtering by user gives a different number for each.
        user_names = ["alice"] * 5 + ["bob"] * 3 + ["carol"] * 2 + ["dave"]

        slots = []
        for year, total in zip(YEARS, CHANGES_PER_YEAR):
            remaining = total
            while remaining > 0:
                # Grouped into requests, the way a bulk edit is. Without this every record has a request of
                # its own, the related-changes panel is always empty, and that reads as broken rather than
                # as "there were no siblings".
                batch = min(remaining, rng.choice((1, 1, 2, 3, 5)))
                remaining -= batch
                request_id = uuid.uuid4()
                user_name = rng.choice(user_names)
                content_type, obj = rng.choices(targets, weights=weights, k=1)[0]
                when = datetime(year, 1, 1, tzinfo=dt_timezone.utc) + timedelta(
                    days=rng.randrange(365), hours=rng.randrange(24), minutes=rng.randrange(60)
                )
                for offset in range(batch):
                    # Distinct times: ObjectChange is unique on (time, request_id, type, object id).
                    slots.append((when + timedelta(seconds=offset), request_id, user_name, content_type, obj))

        by_object = defaultdict(list)
        for slot in slots:
            by_object[(slot[3].pk, slot[4].pk)].append(slot)

        made = defaultdict(int)
        for group in by_object.values():
            group.sort(key=lambda slot: slot[0])
            for when, change in self._object_history(rng, group):
                ObjectChange.objects.filter(pk=change.pk).update(time=when)
                made[when.year] += 1

        self.stdout.write(self.style.NOTICE(f"Created change records per year: {dict(sorted(made.items()))}"))

    def _object_history(self, rng, group):
        """
        One object's history as an evolving state, yielding `(timestamp, ObjectChange)`.

        The difference panel derives its diff by comparing a record against the previous change to the same
        object, so the history has to be coherent: an object cannot be created twice, and consecutive
        payloads have to actually differ or every diff reads "No changes".
        """
        statuses = ["Active", "Planned", "Staged", "Offline"]
        notes = [
            "migrated to new rack",
            "firmware upgraded",
            "reassigned to core role",
            "cabling audit",
            "decommission scheduled",
            "tenant changed",
        ]
        state = {
            "name": str(group[0][4]),
            "status": statuses[0],
            "description": "",
            "comments": "",
            "asset_tag": None,
        }
        # A minority of histories end in a deletion, so the delete action is not vanishingly rare.
        ends_deleted = len(group) > 2 and rng.random() < 0.25

        for index, (when, request_id, user_name, content_type, obj) in enumerate(group):
            if index == 0:
                action = ObjectChangeActionChoices.ACTION_CREATE
                state["status"] = rng.choice(statuses)
                state["description"] = rng.choice(notes)
            elif ends_deleted and index == len(group) - 1:
                action = ObjectChangeActionChoices.ACTION_DELETE
            else:
                action = ObjectChangeActionChoices.ACTION_UPDATE
                fields = rng.sample(("status", "description", "comments", "asset_tag"), rng.choice((1, 1, 2)))
                for field in fields:
                    if field == "status":
                        state["status"] = rng.choice([s for s in statuses if s != state["status"]])
                    elif field == "asset_tag":
                        state["asset_tag"] = f"ASSET-{rng.randrange(1000, 9999)}"
                    else:
                        state[field] = rng.choice([n for n in notes if n != state[field]])

            yield (
                when,
                ObjectChange.objects.create(
                    action=action,
                    changed_object_type=content_type,
                    changed_object_id=obj.pk,
                    object_repr=str(obj),
                    object_data=dict(state),
                    object_data_v2=dict(state),
                    request_id=request_id,
                    user_name=user_name,
                    change_context="orm",
                    change_context_detail=MARKER,
                ),
            )

    # Job history

    def _job_history(self, rng):
        """Backdated job results with log and console output, so job history has something to rotate too."""
        made = defaultdict(int)
        for year, total in zip(YEARS, JOB_RESULTS_PER_YEAR):
            for index in range(total):
                when = datetime(
                    year, rng.randrange(1, 13), rng.randrange(1, 28), rng.randrange(24), 30, tzinfo=dt_timezone.utc
                )
                job_name = rng.choice(("Nightly Sync", "Config Backup", "Compliance Scan"))
                result = JobResult.objects.create(
                    name=f"{MARKER}: {job_name} {year}-{index}",
                    status=rng.choice(
                        [JobResultStatusChoices.STATUS_SUCCESS] * 3 + [JobResultStatusChoices.STATUS_FAILURE]
                    ),
                )
                JobResult.objects.filter(pk=result.pk).update(date_created=when, date_started=when, date_done=when)
                self._job_log_entries(rng, result, when, year)
                self._job_console_entries(rng, result, when, year)
                made[year] += 1
        self.stdout.write(self.style.NOTICE(f"Created job results per year: {dict(sorted(made.items()))}"))

    def _job_log_entries(self, rng, result, when, year):
        """Entry counts vary per result, so "12 results" and "36 entries" cannot be mistaken for each other."""
        for line in range(rng.randrange(1, 10)):
            entry = JobLogEntry.objects.create(
                job_result=result,
                log_level=rng.choice(
                    [LogLevelChoices.LOG_INFO] * 4 + [LogLevelChoices.LOG_WARNING, LogLevelChoices.LOG_ERROR]
                ),
                grouping="run",
                message=f"{MARKER} log line {line} for {year}",
            )
            JobLogEntry.objects.filter(pk=entry.pk).update(created=when)

    def _job_console_entries(self, rng, result, when, year):
        """
        Console output on some results and not others.

        Without any of it the console tab renders blank, which reads as broken rather than as "this run
        produced no console output" -- and with it on every result, the genuinely-empty case is never seen.
        """
        if rng.random() >= 0.6:
            return
        for line in range(rng.randrange(2, 8)):
            console = JobConsoleEntry.objects.create(
                job_result=result,
                output_type=rng.choice(
                    [JobConsoleEntryOutputTypeChoices.TYPE_STDOUT] * 4 + [JobConsoleEntryOutputTypeChoices.TYPE_STDERR]
                ),
                text=f"{MARKER} console line {line} for {year}",
            )
            JobConsoleEntry.objects.filter(pk=console.pk).update(timestamp=when + timedelta(seconds=line))

    # Truncation candidates

    def _truncation_candidates(self, rng):
        """
        Warm change records the enabled truncation rules can actually delete.

        Everything else this command creates is backdated past the warm window and then rotated, which
        leaves truncation nothing to do: a record old enough for an age bound above the window has already
        been moved out of warm storage. These sit between `TRUNCATION_AGE_DAYS` and the warm window, so
        rotation leaves them and the rules still match.

        Three groups, so a dry run reports a number a tester can reason about: records the include rule
        selects, records it selects and the exclude rule then saves, and records neither touches.
        """
        targets, weights = self._targets(rng)
        made = {}
        groups = (
            ("deletable", TRUNCATION_DELETABLE, ObjectChangeActionChoices.ACTION_DELETE, ("alice", "bob", "dave")),
            ("protected", TRUNCATION_PROTECTED, ObjectChangeActionChoices.ACTION_DELETE, ("carol",)),
            ("untouched", TRUNCATION_UNTOUCHED, ObjectChangeActionChoices.ACTION_UPDATE, ("alice", "bob")),
        )
        for label, count, action, user_names in groups:
            for index in range(count):
                content_type, obj = rng.choices(targets, weights=weights, k=1)[0]
                # Comfortably older than the age bound and comfortably inside the warm window, so neither
                # boundary is being tested by accident.
                when = timezone.now() - timedelta(days=rng.randrange(TRUNCATION_AGE_DAYS + 6, 80), minutes=index)
                change = ObjectChange.objects.create(
                    action=action,
                    changed_object_type=content_type,
                    changed_object_id=obj.pk,
                    object_repr=str(obj),
                    object_data={"name": str(obj), "note": f"{MARKER} truncation candidate"},
                    object_data_v2={"name": str(obj), "note": f"{MARKER} truncation candidate"},
                    request_id=uuid.uuid4(),
                    user_name=rng.choice(user_names),
                    change_context="orm",
                    change_context_detail=TRUNCATION_MARKER,
                )
                ObjectChange.objects.filter(pk=change.pk).update(time=when)
            made[label] = count

        for index in range(TRUNCATION_FAILED_RESULTS + TRUNCATION_PASSED_RESULTS):
            failed = index < TRUNCATION_FAILED_RESULTS
            when = timezone.now() - timedelta(days=rng.randrange(TRUNCATION_AGE_DAYS + 6, 80), minutes=index)
            result = JobResult.objects.create(
                name=f"{MARKER}: Recent Run {index}",
                status=JobResultStatusChoices.STATUS_FAILURE if failed else JobResultStatusChoices.STATUS_SUCCESS,
            )
            JobResult.objects.filter(pk=result.pk).update(date_created=when, date_started=when, date_done=when)
        made["failed job results"] = TRUNCATION_FAILED_RESULTS

        self.stdout.write(
            self.style.NOTICE(
                f"Created warm truncation candidates: {made['deletable']} deletable, "
                f"{made['protected']} protected by the exclude rule, {made['untouched']} untouched, "
                f"{made['failed job results']} failed job results"
            )
        )

    # Rules and users

    def _retention_rules(self):
        """
        Rules for the truncation job, including one of each mode.

        The include/exclude pair is left enabled because the truncation job applies every enabled rule
        and nothing else, so with none enabled a run has nothing to do -- which reads as broken. Truncation
        still defaults to a dry run, so nothing is deleted without being asked. The third rule stays
        disabled so that state is visible too, and so the enabled checkbox can be seen to matter.
        """
        change_ct = ContentType.objects.get_for_model(ObjectChange)
        result_ct = ContentType.objects.get_for_model(JobResult)
        rules = [
            {
                "name": f"{MARKER}: delete old deletions",
                "content_type": change_ct,
                "mode": RetentionRuleModeChoices.MODE_INCLUDE,
                # Scoped to this command's own records. Unscoped, the rule would also select the change
                # history `generate_test_data` created, and running truncation to see it work would delete
                # data the tester did not mean to lose.
                "scope_filter": {
                    "action": [ObjectChangeActionChoices.ACTION_DELETE],
                    "change_context_detail": [TRUNCATION_MARKER],
                },
                "max_age_days": TRUNCATION_AGE_DAYS,
                "weight": 100,
                "description": (f"Selects this command's delete-action changes older than {TRUNCATION_AGE_DAYS} days."),
                "enabled": True,
            },
            {
                "name": f"{MARKER}: protect carol's changes",
                "content_type": change_ct,
                "mode": RetentionRuleModeChoices.MODE_EXCLUDE,
                "scope_filter": {"user_name": ["carol"], "change_context_detail": [TRUNCATION_MARKER]},
                "weight": 200,
                "description": "Protects one user's changes from any include rule.",
                "enabled": True,
            },
            {
                "name": f"{MARKER}: delete failed job results",
                "content_type": result_ct,
                "mode": RetentionRuleModeChoices.MODE_INCLUDE,
                "scope_filter": {"status": [JobResultStatusChoices.STATUS_FAILURE], "name__isw": [MARKER]},
                "max_age_days": TRUNCATION_AGE_DAYS,
                "weight": 100,
                "description": (f"Selects this command's failed job results older than {TRUNCATION_AGE_DAYS} days."),
                "enabled": False,
            },
        ]
        for spec in rules:
            RetentionRule.objects.update_or_create(name=spec.pop("name"), defaults=spec)
        enabled = RetentionRule.objects.filter(name__startswith=MARKER, enabled=True).count()
        self.stdout.write(
            self.style.NOTICE(f"Created {len(rules)} retention rules ({enabled} enabled, {len(rules) - enabled} not)")
        )

    def _users(self):
        """
        Two users, so the cold-storage permission can be tried from both sides.

        Reading retained history takes `extras.view_archivesegment` on top of the warm view permission, and
        the difference is only visible by comparing a user who has it against one who does not.
        """
        for username in DEMO_USERS:
            cold_storage = username == "retention-archivist"
            user, _ = User.objects.get_or_create(username=username, defaults={"is_active": True})
            user.set_password(DEMO_PASSWORD)
            user.is_active = True
            user.is_staff = False
            user.is_superuser = False
            user.save()

            permissions = [
                "extras.view_objectchange",
                "extras.view_jobresult",
                "extras.view_joblogentry",
                "extras.view_jobconsoleentry",
                # Both users get to see the rules: without this the retention rule UI is a 403, and the
                # point of these accounts is that the *only* difference between them is whether they may
                # read retained history.
                "extras.view_retentionrule",
                "dcim.view_device",
                "dcim.view_location",
            ]
            if cold_storage:
                permissions.append("extras.view_archivesegment")
            for name in permissions:
                app_label, codename = name.split(".")
                action, model = codename.split("_", 1)
                content_type = ContentType.objects.get(app_label=app_label, model=model)
                permission, _ = ObjectPermission.objects.update_or_create(
                    name=f"{MARKER}: {username} {name}", defaults={"actions": [action]}
                )
                permission.users.add(user)
                permission.object_types.add(content_type)
        self.stdout.write(self.style.NOTICE(f"Created users {', '.join(DEMO_USERS)}"))

    # Rotation

    def _rotate(self):
        """
        Run the rotation job in-process, so no worker is needed to get retained history to look at.

        Its log goes to stdout rather than to `JobLogEntry`, since there is no real `JobResult` behind it.
        """
        from nautobot.core.jobs.retention import ChangelogRotation

        logger = logging.getLogger(f"nautobot.{MARKER}")
        logger.setLevel(logging.INFO)
        # Not propagated: Nautobot's root handler would print every line a second time, with its own
        # timestamped prefix, which makes the rotation log twice as long and half as readable.
        logger.propagate = False
        if not logger.handlers:
            handler = logging.StreamHandler(self.stdout)
            handler.setFormatter(logging.Formatter("  %(message)s"))
            logger.addHandler(handler)

        job = ChangelogRotation()
        job.logger = logger
        job.job_result = _StubJobResult(User.objects.filter(is_superuser=True).first())

        self.stdout.write(self.style.NOTICE("Running Changelog Rotation in-process"))
        result = job.run(record_types=None, warm_window_days=90, batch_size=500, dry_run=False)
        self.stdout.write(self.style.SUCCESS(f"Rotated: {result}"))

    # Reporting and teardown

    def _report(self):
        """What exists now, warm and retained, so a run can be checked without opening the UI."""
        rows = [
            ("Warm change records", ObjectChange.objects.count()),
            (f"  of which {MARKER}", ObjectChange.objects.filter(change_context_detail__startswith=MARKER).count()),
            ("Retained change records", ArchivedObjectChange.objects.count()),
            ("Warm job results", JobResult.objects.count()),
            ("Retained job results", ArchivedJobResult.objects.count()),
            ("Retained job log entries", ArchivedJobLogEntry.objects.count()),
            ("Retained console entries", ArchivedJobConsoleEntry.objects.count()),
            ("Retention rules", RetentionRule.objects.count()),
            # Truncation deletes these, so they are used up by the first real run. Reported so a tester can
            # see when there is nothing left for the rules to act on and re-run with --flush.
            (
                "Warm truncation candidates",
                ObjectChange.objects.filter(change_context_detail=TRUNCATION_MARKER).count(),
            ),
            (
                "  of which deletable",
                ObjectChange.objects.filter(
                    change_context_detail=TRUNCATION_MARKER, action=ObjectChangeActionChoices.ACTION_DELETE
                )
                .exclude(user_name="carol")
                .count(),
            ),
        ]
        self.stdout.write("")
        for label, count in rows:
            self.stdout.write(f"{label:28} {count}")

        segments = ArchiveSegment.objects.order_by("model_label", "-period_key")
        self.stdout.write(f"{'Retention periods':28} {segments.count()}")
        for segment in segments:
            state = "complete" if segment.is_period_closed else "still receiving"
            self.stdout.write(f"  {segment.model_label:32} {segment.label:10} {segment.row_count:6} rows  ({state})")

    def _flush(self):
        """
        Remove what a previous run created, and turn retention back off.

        Keyed on MARKER throughout, so a record this command did not create is never touched. A retention
        period is removed only once nothing is filed under it, since the period registry is otherwise the
        rotation job's to maintain.
        """
        from constance import config

        from nautobot.extras.registry import registry

        # Reported per model from `delete()[1]`, not from `delete()[0]`: the total counts cascades too, so
        # deleting 17 job results reports 120 once their log and console entries are included, which reads
        # as this command having created records it did not.
        deleted = defaultdict(int)
        for queryset in (
            ArchivedObjectChange.objects.filter(change_context_detail__startswith=MARKER),
            ArchivedJobLogEntry.objects.filter(message__startswith=MARKER),
            ArchivedJobConsoleEntry.objects.filter(text__startswith=MARKER),
            ArchivedJobResult.objects.filter(name__startswith=MARKER),
            ObjectChange.objects.filter(change_context_detail__startswith=MARKER),
            JobResult.objects.filter(name__startswith=MARKER),
            RetentionRule.objects.filter(name__startswith=MARKER),
            ObjectPermission.objects.filter(name__startswith=MARKER),
            User.objects.filter(username__in=DEMO_USERS),
        ):
            for label, count in queryset.delete()[1].items():
                # Skip many-to-many through tables: they are an artifact of how a permission's users and
                # object types are stored, not something this command created.
                if apps.get_model(label)._meta.auto_created:
                    continue
                deleted[label] += count

        emptied = 0
        for segment in ArchiveSegment.objects.all():
            mirror = registry["changelog_archive_models"].get(segment.model_label)
            if mirror and not mirror.objects.filter(period_key=segment.period_key).exists():
                segment.delete()
                emptied += 1
        if emptied:
            deleted["extras.ArchiveSegment (emptied)"] = emptied

        config.CHANGELOG_ARCHIVE_ENABLED = False
        for label, count in sorted(deleted.items()):
            self.stdout.write(f"Removed {count:6} {label}")
        if not deleted:
            self.stdout.write("Nothing to remove")
        self.stdout.write(self.style.NOTICE("Retention disabled"))
