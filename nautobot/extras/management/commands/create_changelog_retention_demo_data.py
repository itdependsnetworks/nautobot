"""
Generate everything needed to exercise changelog long-term retention by hand.

Retention only acts on records older than the warm window, so a fresh install has nothing to show until
history has had months to accumulate. This fabricates that history with backdated timestamps, adds rules
for the truncation job with records it can actually delete, and creates a user who may read retained
history and one who may not.

# PLACEHOLDER: later stories extend this command. CONCRETE-5 puts records into the archive, ROTATE-1
# replaces that with the real job, and ABSTRACT-5 adds --period.

Everything it creates is tagged with MARKER, in `change_context_detail` for change records and in the name or text
for everything else, so `--flush` can find and remove all of it. It never touches a record it did not
create.

The fabricated history is deliberately lumpy. Uniform data makes the UI unreadable: when a period's total,
an object's own history, and the page size are all the same number, a disagreement between them is
invisible. The seed makes a re-run reproduce the same data.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone
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

#: Years to fabricate history for.
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
            help="Remove what a previous run created and generate nothing.",
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
            self._object_changes(random.Random(options["seed"]))  # noqa: S311  # not cryptographic
            self._job_history(random.Random(options["seed"] + 1))  # noqa: S311  # not cryptographic
            self._truncation_candidates(random.Random(options["seed"] + 2))  # noqa: S311  # not cryptographic
            self._retention_rules()
            self._users()

        self._report()
        self.stdout.write(
            self.style.WARNING(
                f"Users '{DEMO_USERS[0]}' (no cold storage) and '{DEMO_USERS[1]}' (cold storage) share the "
                f"password '{DEMO_PASSWORD}'. Development instances only."
            )
        )

    # Setup

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
        """Backdated job results with log and console output, so job history is old enough to retain too."""
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
        Two users to read the fabricated history as.

        They differ in nothing yet. CONCRETE-2 gives one of them the cold-storage permission, which is
        the only difference between them and the reason there are two.
        """
        for username in DEMO_USERS:
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
                # Both users get to see the rules: the point of these accounts is that the *only*
                # difference between them is whether they may read retained history.
                # PLACEHOLDER: CONCRETE-2 adds `extras.view_archivesegment` for one of the two.
                "extras.view_retentionrule",
                "dcim.view_device",
                "dcim.view_location",
            ]
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

    def _report(self):
        """What exists now, so a run can be checked without opening the UI."""
        rows = [
            ("Warm change records", ObjectChange.objects.count()),
            (f"  of which {MARKER}", ObjectChange.objects.filter(change_context_detail__startswith=MARKER).count()),
            ("Warm job results", JobResult.objects.count()),
            (f"  of which {MARKER}", JobResult.objects.filter(name__startswith=MARKER).count()),
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

    def _flush(self):
        """
        Remove what a previous run created.

        Keyed on MARKER throughout, so a record this command did not create is never touched.
        """
        # Per model from `delete()[1]`, since `[0]` counts cascades too and would report 120 for 17 job
        # results.
        deleted = defaultdict(int)
        for queryset in (
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
                deleted[model._meta.label if model else label] += count

        for label, count in sorted(deleted.items()):
            self.stdout.write(f"Removed {count:6} {label}")
        if not deleted:
            self.stdout.write("Nothing to remove")
