"""
Generate everything needed to exercise changelog long-term retention by hand.

Retention is hard to try out on a fresh install: it only does anything to records older than the warm
window, so there is nothing to rotate until history has had months to accumulate. This fabricates that
history with backdated timestamps, then optionally rotates it, leaving an instance where every part of the
feature has something real to show -- retained records to browse and filter, a rule to run truncation
with, and a user who may read retained history and one who may not.

Everything it creates is tagged with MARKER, in `change_context_detail` for change records and in the name or text
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
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from nautobot.dcim.models import Device, Location
from nautobot.extras.choices import (
    ChangelogArchivePeriodChoices,
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
from nautobot.extras.models.archive import period_models_for, warm_model_for
from nautobot.extras.registry import registry
from nautobot.users.models import ObjectPermission

MARKER = "retention-demo"
#: The truncation candidates get their own marker. They are the one group that must be dated relative to
#: *now* rather than to a fixed year, so they are neither reproducible from the seed nor part of the
#: backdated history -- and every count and invariant over that history has to be able to exclude them.
TRUNCATION_MARKER = f"{MARKER}-truncation"

#: Years to fabricate history for. Under the default `unbounded` granularity all four are written to the
#: one period; under a calendar granularity each year becomes one or more periods of its own.
YEARS = (2022, 2023, 2024, 2025)
#: One entry per year in YEARS. Uneven so a count in the UI can be traced to what it is counting.
CHANGES_PER_YEAR = (17, 63, 41, 28)
JOB_RESULTS_PER_YEAR = (3, 7, 5, 2)

#: Warm records the truncation rules can actually act on, and what each group is for. These are *inside*
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


def _reported_label(model, label):
    """The label a deletion is counted under: the mirror's, for a period model, and otherwise its own."""
    from nautobot.extras.models.archive import archive_base_of
    from nautobot.extras.registry import registry

    if model is None:
        for mirror in registry["changelog_archive_models"].values():
            if label.lower().startswith(mirror._meta.label_lower):
                return mirror._meta.label
        return label
    return archive_base_of(model)._meta.label


def _model_for_label(label):
    """The model a `delete()` result is keyed by, or None where it is not a registered model."""
    try:
        return apps.get_model(label)
    except LookupError:
        return None


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
            choices=[value for value, _ in ChangelogArchivePeriodChoices.CHOICES],
            help=(
                "Granularity to rotate this history under, for the duration of this command only. Without "
                "it, CHANGELOG_ARCHIVE_PERIOD decides, as it does for the scheduled job. Pass `year` to "
                f"get a period per year in {YEARS}, so the period selector has something to select, "
                "without restarting the instance on a different setting."
            ),
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
            self._configure()
            self._object_changes(random.Random(options["seed"]))  # noqa: S311  # not cryptographic
            self._job_history(random.Random(options["seed"] + 1))  # noqa: S311  # not cryptographic
            self._truncation_candidates(random.Random(options["seed"] + 2))  # noqa: S311  # not cryptographic
            self._retention_rules()
            self._users()

        # Outside the transaction above on purpose: rotation manages its own per-increment transactions,
        # and wrapping it would undo the bounded-increment behaviour this command exists to demonstrate.
        if options["rotate"]:
            self._rotate(options["period"])

        self._report()
        self.stdout.write(
            self.style.WARNING(
                f"Users '{DEMO_USERS[0]}' (no cold storage) and '{DEMO_USERS[1]}' (cold storage) share the "
                f"password '{DEMO_PASSWORD}'. Development instances only."
            )
        )

    # Setup

    def _configure(self):
        """Set the runtime tuning this fabricated history is shaped for, and check the capability is on."""
        from constance import config
        from django.conf import settings

        if not settings.CHANGELOG_ARCHIVE_ENABLED:
            raise CommandError(
                "Changelog long-term retention is off. It is a deployment setting rather than a runtime "
                "toggle, so this command cannot turn it on. Set CHANGELOG_ARCHIVE_ENABLED = True in "
                "nautobot_config.py (or NAUTOBOT_CHANGELOG_ARCHIVE_ENABLED=True), restart, and run again."
            )
        config.CHANGELOG_WARM_WINDOW_DAYS = 90
        self.stdout.write(self.style.NOTICE("Warm window 90 days"))

    def _targets(self, rng):
        """
        Real devices and locations to attach the fabricated history to.

        Real objects on purpose: the lists link each record to the object it describes, and an object's Change
        Log tab links back. Neither is testable against objects that never existed.
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

        The difference panel diffs a record against the previous change to the same object, so an object
        cannot be created twice and consecutive payloads have to differ, or every diff reads "No changes".
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

        With none, the console tab reads as broken rather than empty; with it on every result, the
        genuinely-empty case is never seen.
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

        Everything else here is backdated past the warm window and rotated, which leaves truncation nothing to
        do. These sit between `TRUNCATION_AGE_DAYS` and the window, so rotation leaves them and the rules
        still match.

        Three groups, so a dry run reports a number a tester can reason about: selected by the include rule,
        selected and then saved by the exclude rule, and untouched.
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

        The include/exclude pair is enabled because truncation applies every enabled rule and nothing else, so
        with none enabled a run reads as broken. It still defaults to a dry run. The third stays disabled so
        that state is visible too.
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

        The difference is only visible by comparing a user holding `extras.view_archivesegment` against one
        who does not.
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

    def _rotate(self, period=None):
        """
        Run the rotation job in-process, so no worker is needed to get retained history to look at.

        Its log goes to stdout, there being no real `JobResult` behind it.

        `period` overrides `CHANGELOG_ARCHIVE_PERIOD` for this run only. That setting needs a restart, so
        without this a demo instance could only show the granularity it was started on.
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

        granularity = period or settings.CHANGELOG_ARCHIVE_PERIOD
        self.stdout.write(self.style.NOTICE(f"Running Changelog Rotation in-process, period `{granularity}`"))
        previous = settings.CHANGELOG_ARCHIVE_PERIOD
        settings.CHANGELOG_ARCHIVE_PERIOD = granularity
        try:
            result = job.run(record_types=None, warm_window_days=90, batch_size=500, dry_run=False)
        finally:
            settings.CHANGELOG_ARCHIVE_PERIOD = previous
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

        self._report_storage()

        from nautobot.extras.registry import registry

        for warm_label, mirror in sorted(registry["changelog_archive_models"].items()):
            self.stdout.write(f"  {warm_label:32} {mirror.objects.count():6} rows  {mirror._meta.db_table}")

    def _report_storage(self):
        """
        Where retained history is being written, which is what a tester most often needs to check.

        The archive sharing the primary database and the archive on its own host look identical from the UI.
        """
        from django.conf import settings

        from nautobot.core.constants import CHANGELOG_ARCHIVE
        from nautobot.core.utils.config import changelog_archive_is_separate

        archive = settings.DATABASES.get(CHANGELOG_ARCHIVE, {})
        if changelog_archive_is_separate():
            host = archive.get("HOST") or "localhost"
            target = f"{archive.get('NAME', '?')} on {host}:{archive.get('PORT') or 'default'}"
        else:
            target = f"{archive.get('NAME', '?')} (same database as default)"
        self.stdout.write("")
        self.stdout.write(f"{'Retained history connection':28} {CHANGELOG_ARCHIVE} -> {target}")

        periods = ArchiveSegment.objects.all()
        if not periods.exists():
            return
        self.stdout.write("")
        self.stdout.write(f"{'Period':16} {'Record type':28} {'Records':>8}  Covers")
        for segment in periods:
            covers = (
                "all time"
                if segment.time_start is None
                else f"{segment.time_start:%Y-%m-%d} to {segment.time_end:%Y-%m-%d}"
            )
            self.stdout.write(f"{segment.period_key:16} {segment.model_label:28} {segment.row_count:>8}  {covers}")

    def _flush(self):
        """
        Remove what a previous run created, and turn retention back off.

        Keyed on MARKER throughout, so a record this command did not create is never touched.
        """

        # Per model from `delete()[1]`, since `[0]` counts cascades too and would report 120 for 17 job
        # results. Every period of each mirror: under a calendar granularity the mirror's own table is
        # empty, so sweeping it alone would remove nothing and leave the demo history in place.
        retained = [
            period_model.objects.filter(**{f"{field}__startswith": MARKER})
            for mirror, field in (
                (ArchivedObjectChange, "change_context_detail"),
                (ArchivedJobLogEntry, "message"),
                (ArchivedJobConsoleEntry, "text"),
                (ArchivedJobResult, "name"),
            )
            for period_model in period_models_for(mirror)
        ]

        deleted = defaultdict(int)
        for queryset in (
            *retained,
            ObjectChange.objects.filter(change_context_detail__startswith=MARKER),
            JobResult.objects.filter(name__startswith=MARKER),
            RetentionRule.objects.filter(name__startswith=MARKER),
            ObjectPermission.objects.filter(name__startswith=MARKER),
            User.objects.filter(username__in=DEMO_USERS),
        ):
            for label, count in queryset.delete()[1].items():
                model = _model_for_label(label)
                # Skip many-to-many through tables: they are an artifact of how a permission's users and
                # object types are stored, not something this command created.
                if model is not None and model._meta.auto_created:
                    continue
                # Reported against the mirror, not the period. `delete()` names the class it deleted
                # through, which for a calendar period is `extras.ArchivedObjectChange2024`: a label for
                # one table of one period, where what a reader wants is how many change records went.
                deleted[_reported_label(model, label)] += count

        emptied = self._remove_empty_periods()

        for label, count in sorted(deleted.items()):
            self.stdout.write(f"Removed {count:6} {label}")
        if emptied:
            self.stdout.write(f"Removed {emptied:6} empty retention period(s)")
        if not deleted and not emptied:
            self.stdout.write("Nothing to remove")
        # The capability itself is a deployment setting, so this leaves it alone and says so.
        self.stdout.write(self.style.NOTICE("Demo data removed. CHANGELOG_ARCHIVE_ENABLED is unchanged."))

    @staticmethod
    def _remove_empty_periods():
        """
        Drop the segment row for any period left holding nothing, and return how many went.

        Only empty ones: the registry is the rotation job's to maintain. The table stays, a row being cheaper
        to recreate. A segment naming a table that does not exist is left alone, reading it to decide would
        raise `UndefinedTable`.
        """
        removed = 0
        for mirror in registry["changelog_archive_models"].values():
            warm_label = warm_model_for(mirror)._meta.label_lower
            empty = [model.period_key_value for model in period_models_for(mirror) if not model.objects.exists()]
            removed += ArchiveSegment.objects.filter(model_label=warm_label, period_key__in=empty).delete()[0]
        return removed
