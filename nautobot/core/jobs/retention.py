"""
System jobs maintaining changelog long-term retention.

`ChangelogRotation` moves change and job history past the warm window into retained storage, which is
what keeps the warm tables a working set instead of the whole history.

`LogsCleanup` stays the age-only tool that deletes warm history outright. Rotation moves that history
instead of deleting it, so the two are alternatives and not a sequence.
"""

from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from nautobot.core.utils.config import get_settings_or_config
from nautobot.extras.context_managers import without_delete_change_logging
from nautobot.extras.jobs import BooleanVar, IntegerVar, Job, MultiChoiceVar
from nautobot.extras.models.archive import (
    build_mirror_instance,
)
from nautobot.extras.registry import registry
from nautobot.extras.utils import age_field_for

name = "System Jobs"


# Rotation order matters. JobLogEntry and JobConsoleEntry are CASCADE children of JobResult, so deleting a
# warm JobResult first would take its warm log entries with it. Children are archived before parents.
ROTATION_ORDER = (
    "extras.objectchange",
    "extras.joblogentry",
    "extras.jobconsoleentry",
    "extras.jobresult",
)


class ChangelogRotation(Job):
    """
    Move change and job history out of warm storage into long-term retention.

    A retained record keeps the primary key it had warm, so a second run writes the same records again and
    the repeated keys conflict harmlessly.
    """

    record_types = MultiChoiceVar(
        choices=[(label, label) for label in ROTATION_ORDER],
        description="Record types to rotate. Leave empty to rotate all of them.",
        required=False,
    )
    warm_window_days = IntegerVar(
        description=(
            "Days of history to keep in warm storage. Records older than this are moved. "
            "Leave empty to use the CHANGELOG_WARM_WINDOW_DAYS setting."
        ),
        label="Warm Window",
        min_value=1,
        required=False,
    )
    batch_size = IntegerVar(
        description=(
            "Records to move per increment. Leave empty to use the CHANGELOG_ROTATION_BATCH_SIZE setting. "
            "Lower it if rotation runs out of memory: each record in a batch is held twice while it is copied."
        ),
        label="Batch Size",
        min_value=1,
        required=False,
    )
    include_job_files = BooleanVar(
        description=(
            "Rotate job results that have output files attached. Those files are deleted with the warm "
            "record and are not archived, so this is off by default."
        ),
        default=False,
    )
    dry_run = BooleanVar(description="Report what would be moved without moving anything.", default=True)

    class Meta:
        name = "Changelog Rotation"
        description = "Move change and job history older than the warm window into long-term retention."
        has_sensitive_variables = False

    def run(  # pylint: disable=arguments-differ
        self, *, record_types=None, warm_window_days=None, batch_size=None, include_job_files=False, dry_run=True
    ):
        if not settings.CHANGELOG_ARCHIVE_ENABLED:
            self.logger.warning("Changelog long-term retention is disabled (CHANGELOG_ARCHIVE_ENABLED); nothing to do.")
            return {}

        if warm_window_days in (None, ""):
            warm_window_days = get_settings_or_config("CHANGELOG_WARM_WINDOW_DAYS", fallback=90)
        if batch_size in (None, ""):
            # Sized for what rotation actually costs: every record in a batch is held in memory twice
            # while it is copied, once as the warm record and once as the retained copy built from it.
            batch_size = get_settings_or_config("CHANGELOG_ROTATION_BATCH_SIZE", fallback=1000)

        labels = [label for label in ROTATION_ORDER if not record_types or label in record_types]
        cutoff = timezone.now() - timedelta(days=warm_window_days)
        self.logger.info("Rotating records older than %s (%d-day warm window)", cutoff, warm_window_days)

        result = {}
        with without_delete_change_logging(self.logger):
            for label in labels:
                model = apps.get_model(label)
                mirror = registry["changelog_archive_models"].get(label)
                if mirror is None:
                    self.logger.warning("No retention mirror registered for %s; skipping.", label)
                    continue
                result[model._meta.label] = self._rotate_model(
                    model, mirror, cutoff, batch_size, include_job_files, dry_run
                )

        if dry_run:
            # Printed beside the per-model counts so the summary reads "dry run; 149 object changes"
            # instead of leaving a reader to guess whether the numbers describe work done or work pending.
            result["dry_run"] = True

        return result

    def _rotate_model(self, model, mirror, cutoff, batch_size, include_job_files, dry_run):
        """Move one model's eligible records, a bounded batch at a time."""
        age_field = age_field_for(model)
        eligible = model.objects.filter(**{f"{age_field}__lt": cutoff}).order_by(age_field)
        eligible = self._exclude_unsafe(model, eligible, include_job_files, dry_run=dry_run)

        total = eligible.count()
        if not total:
            self.logger.info("No %s records older than the warm window", model._meta.label)
            return 0

        if dry_run:
            self.logger.warning(
                "Dry run: would move %d %s records in increments of %d", total, model._meta.label, batch_size
            )
            # The count it *would* move, not zero. A dry run exists to report how much a real run would do,
            # and a result summary reading 0 reports the wrong thing -- the caller can see it was a dry
            # run from the `dry_run` key alongside these counts.
            return total

        moved = 0
        increments = 0
        while True:
            batch = list(eligible[:batch_size])
            if not batch:
                break
            moved_now = self._move_batch(model, mirror, batch)
            moved += moved_now
            increments += 1
            self.logger.info("Increment %d: moved %d %s records", increments, moved_now, model._meta.label)
            if not moved_now:
                self.logger.warning(
                    "Stopping: %d %s records remain eligible but could not be moved", len(batch), model._meta.label
                )
                break

        self.logger.success("Moved %d %s records across %d increments", moved, model._meta.label, increments)
        return moved

    def _exclude_unsafe(self, model, queryset, include_job_files, dry_run=False):
        """
        Drop records that cannot be rotated without collateral loss.

        A warm `JobResult` is deleted once archived and its CASCADE children go with it. Log and console
        entries are archived first, so any still present mean this result must wait. Output files are never
        archived, so a result carrying them is held back unless the operator opts in.
        """
        if model._meta.label_lower != "extras.jobresult":
            return queryset

        # `.distinct()` because filtering across these reverse foreign keys yields one row per child, so
        # the count would otherwise report log entries rather than job results.
        stragglers = queryset.filter(Q(job_log_entries__isnull=False) | Q(job_console_entries__isnull=False)).distinct()
        straggler_count = stragglers.count()
        if straggler_count:
            # One message, with the reason phrased for the mode. A dry run moves nothing, so every child
            # is still warm and every parent looks held back -- reporting that count without saying why
            # reads as a bug, since the real run will exceed it.
            if dry_run:
                self.logger.info(
                    "Withholding %d job results whose log or console entries are still in warm storage. "
                    "In a dry run those never move, so the job result count is a lower bound rather than a "
                    "prediction; a real run moves them first.",
                    straggler_count,
                )
            else:
                self.logger.info(
                    "Withholding %d job results whose log or console entries are still in warm storage; "
                    "they will rotate once those do.",
                    straggler_count,
                )
            queryset = queryset.exclude(pk__in=stragglers.values("pk"))

        if not include_job_files:
            with_files = queryset.filter(files__isnull=False).distinct()
            file_count = with_files.count()
            if file_count:
                self.logger.warning(
                    "Withholding %d job results with output files attached. Those files are not archived "
                    "and would be deleted with the warm record; re-run with `include_job_files` to accept that.",
                    file_count,
                )
                queryset = queryset.exclude(pk__in=with_files.values("pk"))

        return queryset

    def _move_batch(self, model, mirror, batch):
        """
        Copy a batch into retained storage, then delete the warm rows.

        Copy then delete, because a failure between the two leaves the record in both places, which the
        next run resolves. It cannot be one transaction: the two sides are different connections, and the
        reverse order would lose the record outright.
        """
        pks = [warm_object.pk for warm_object in batch]
        mirror.objects.bulk_create(
            [build_mirror_instance(warm_object, mirror) for warm_object in batch], ignore_conflicts=True
        )
        archived = set(mirror.objects.filter(pk__in=pks).values_list("pk", flat=True))
        if len(archived) != len(pks):
            self.logger.error(
                "%d of %d %s records were not written to retained storage; leaving them in warm storage",
                len(pks) - len(archived),
                len(pks),
                model._meta.label,
            )

        with transaction.atomic():
            deleted = model.objects.filter(pk__in=list(archived)).delete()[0]
        self.logger.debug("Archived %d and removed %d warm rows", len(archived), deleted)
        return len(archived)
