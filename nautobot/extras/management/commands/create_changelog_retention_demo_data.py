"""
Generate everything needed to exercise changelog long-term retention by hand.

Retention is hard to try out on a fresh install: it only does anything to records older than the warm
window, so there is nothing to rotate until history has had months to accumulate. This fabricates that
history with backdated timestamps, then optionally rotates it, leaving an instance where every part of
the feature has something real to show: retained records to browse and filter, job results with logs and
console output, and a user who may read retained history beside one who may not.

Everything it creates is tagged with MARKER, in `change_context_detail` for change records and in the name or text
for everything else, so `--flush` can find and remove all of it. It never touches a record it did not
create.

The fabricated history is deliberately lumpy. Uniform data makes the UI unreadable: when a total, an
object's own history, and the page size are all the same number, a disagreement between them is
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

from nautobot.dcim.models import Device, Location
from nautobot.extras.choices import (
    JobConsoleEntryOutputTypeChoices,
    JobResultStatusChoices,
    LogLevelChoices,
    ObjectChangeActionChoices,
)
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    JobConsoleEntry,
    JobLogEntry,
    JobResult,
    ObjectChange,
)
from nautobot.users.models import ObjectPermission

MARKER = "retention-demo"
#: Years to fabricate history for.
YEARS = (2022, 2023, 2024, 2025)
#: One entry per year in YEARS. Uneven so a count in the UI can be traced to what it is counting.
CHANGES_PER_YEAR = (17, 63, 41, 28)
JOB_RESULTS_PER_YEAR = (3, 7, 5, 2)

DEFAULT_SEED = 20260820
#: Dev instances only. The command says so on every run.
DEMO_PASSWORD = "retention-demo-1234"  # noqa: S105

DEMO_USERS = ("retention-viewer", "retention-archivist")

User = get_user_model()

# Each warm model beside the mirror its history is moved into. Listed here rather than looked up,
# because nothing in Nautobot maps the two yet.
MIRRORED = {
    "extras.jobconsoleentry": "extras.ArchivedJobConsoleEntry",
    "extras.joblogentry": "extras.ArchivedJobLogEntry",
    "extras.jobresult": "extras.ArchivedJobResult",
    "extras.objectchange": "extras.ArchivedObjectChange",
}


def _model_for_label(label):
    """The model a `delete()` result is keyed by, or None where it is not a registered model."""
    try:
        return apps.get_model(label)
    except LookupError:
        return None


class Command(BaseCommand):
    help = "Generate backdated change and job history, and users, for exercising changelog retention by hand."

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
            # Users first: `_job_history` assigns each job result one of them, and a job result with no
            # user renders a summary panel missing the rows a real one has.
            self._users()
            self._object_changes(random.Random(options["seed"]))  # noqa: S311  # not cryptographic
            self._job_history(random.Random(options["seed"] + 1))  # noqa: S311  # not cryptographic

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
        # `user`, `worker`, `task_name` and `result` are set because the detail page shows a row for each
        # and omits the row when the value is empty. Left unset, a retained job result rendered four rows
        # where a real one renders seven, which reads as the retained page being broken.
        users = list(User.objects.filter(username__in=DEMO_USERS)) or [User.objects.filter(is_superuser=True).first()]
        for year, total in zip(YEARS, JOB_RESULTS_PER_YEAR):
            for index in range(total):
                when = datetime(
                    year, rng.randrange(1, 13), rng.randrange(1, 28), rng.randrange(24), 30, tzinfo=dt_timezone.utc
                )
                job_name = rng.choice(("Nightly Sync", "Config Backup", "Compliance Scan"))
                status = rng.choice(
                    [JobResultStatusChoices.STATUS_SUCCESS] * 3 + [JobResultStatusChoices.STATUS_FAILURE]
                )
                result = JobResult.objects.create(
                    name=f"{MARKER}: {job_name} {year}-{index}",
                    status=status,
                    user=rng.choice(users),
                    worker=f"celery@{rng.choice(('worker-01', 'worker-02', 'worker-03'))}",
                    task_name="nautobot.extras.jobs.scheduled_job_handler",
                    result={"status": status, "devices_checked": rng.randrange(5, 400)},
                    # The Worker panel's Queue row reads `celery_kwargs["queue"]`, on the retained page
                    # as on the warm one, so an empty `celery_kwargs` leaves that row off both.
                    celery_kwargs={"queue": rng.choice(("default", "priority"))},
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

    # Users

    def _users(self):
        """
        Two users, so retained history can be read from both sides.

        The only difference between them is the ordinary view permission on the retained models.
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
                "dcim.view_device",
                "dcim.view_location",
            ]
            if cold_storage:
                # All four, not just the two with list views: without the log and console permissions a
                # retained job result opens with an empty Logs panel and no Console Log tab.
                permissions += [
                    "extras.view_archivedobjectchange",
                    "extras.view_archivedjobresult",
                    "extras.view_archivedjoblogentry",
                    "extras.view_archivedjobconsoleentry",
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

    # Rotation

    def _rotate(self):
        """
        Move the fabricated history into retained storage, so there is something to browse.

        TODO(retention-placeholder): a direct move, because the rotation job does not exist yet. ROTATE-1
        replaces this body with an in-process run of `ChangelogRotation`, which is what a real deployment
        uses. The records this writes are the same records rotation would write: same primary keys, same
        field values, children before parents.
        """
        from django.apps import apps
        from django.utils import timezone

        cutoff = timezone.now() - timedelta(days=90)
        age_fields = {
            "extras.objectchange": "time",
            "extras.jobresult": "date_created",
            "extras.joblogentry": "created",
            "extras.jobconsoleentry": "timestamp",
        }
        moved = {}
        # Children first: a warm job result is deleted once copied, and its log and console entries go
        # with it.
        # Children before parents: deleting a warm job result takes its log and console entries with it.
        for label, mirror_label in MIRRORED.items():
            model = apps.get_model(label)
            mirror = apps.get_model(mirror_label)
            eligible = list(model.objects.filter(**{f"{age_fields[label]}__lt": cutoff}))
            if not eligible:
                continue
            mirror.objects.bulk_create(
                [self._mirror_of(warm_object, mirror) for warm_object in eligible], ignore_conflicts=True
            )
            model.objects.filter(pk__in=[o.pk for o in eligible]).delete()
            moved[label] = len(eligible)
        self.stdout.write(self.style.SUCCESS(f"Moved into retained storage: {moved}"))

    @staticmethod
    def _mirror_of(warm_object, mirror_model):
        """TODO(retention-placeholder): ROTATE-1 replaces this with `build_mirror_instance`."""
        values = {"id": warm_object.pk}
        for field in mirror_model._meta.fields:
            if field.name == "id":
                continue
            if field.name == "user_name" and not hasattr(warm_object, field.name):
                values[field.name] = getattr(warm_object.user, "username", "") or ""
            else:
                values[field.name] = getattr(warm_object, field.name)
        return mirror_model(**values)

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
        ]
        self.stdout.write("")
        for label, count in rows:
            self.stdout.write(f"{label:28} {count}")

        for warm_label, mirror_label in sorted(MIRRORED.items()):
            mirror = apps.get_model(mirror_label)
            self.stdout.write(f"  {warm_label:32} {mirror.objects.count():6} rows  {mirror._meta.db_table}")

    def _flush(self):
        """
        Remove what a previous run created, and turn retention back off.

        Keyed on MARKER throughout, so a record this command did not create is never touched.
        """

        # Per model from `delete()[1]`, since `[0]` counts cascades too and would report 120 for 17 job
        retained = [
            mirror.objects.filter(**{f"{field}__startswith": MARKER})
            for mirror, field in (
                (ArchivedObjectChange, "change_context_detail"),
                (ArchivedJobLogEntry, "message"),
                (ArchivedJobConsoleEntry, "text"),
                (ArchivedJobResult, "name"),
            )
        ]

        deleted = defaultdict(int)
        for queryset in (
            *retained,
            ObjectChange.objects.filter(change_context_detail__startswith=MARKER),
            JobResult.objects.filter(name__startswith=MARKER),
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
        # The capability itself is a deployment setting, so this leaves it alone and says so.
        self.stdout.write(self.style.NOTICE("Demo data removed. CHANGELOG_ARCHIVE_ENABLED is unchanged."))
