"""
System jobs maintaining changelog long-term retention.

`ChangelogTruncation` deletes warm records the operator has decided not to keep. It is deliberately
independent of rotation: deletion is the intended outcome, not a side effect of archiving, and it works
whether or not any retention period exists.

`LogsCleanup` remains the age-only, delete-everything-older-than-N-days tool. This is the filter-driven
one, and the two share `CascadeDeleteMixin` rather than each carrying its own cascade walk.
"""

from datetime import timedelta

from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from nautobot.core.jobs.cleanup import CascadeDeleteMixin
from nautobot.core.utils.config import get_settings_or_config
from nautobot.core.utils.lookup import get_filterset_for_model
from nautobot.extras.choices import RetentionRuleModeChoices
from nautobot.extras.constants import CHANGELOG_ARCHIVE_COVERED_MODELS
from nautobot.extras.context_managers import without_delete_change_logging
from nautobot.extras.jobs import BooleanVar, IntegerVar, Job, MultiChoiceVar
from nautobot.extras.models import (
    ArchiveSegment,
    RetentionRule,
)
from nautobot.extras.models.archive import (
    age_field_for,
    build_mirror_instance,
    period_bounds_for,
    period_key_for,
    period_label_for,
)
from nautobot.extras.registry import registry

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
    Move change and job history out of warm storage into its calendar period.

    A record's own timestamp decides which period holds it, so rotation is idempotent: re-running files the
    same records in the same period and the repeated primary keys conflict harmlessly. There is no
    fill-and-rotate step and no size bound to trip; period granularity is the size control.
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
        if not get_settings_or_config("CHANGELOG_ARCHIVE_ENABLED", fallback=False):
            self.logger.warning("Changelog long-term retention is disabled (CHANGELOG_ARCHIVE_ENABLED); nothing to do.")
            return {}

        if warm_window_days in (None, ""):
            warm_window_days = get_settings_or_config("CHANGELOG_WARM_WINDOW_DAYS", fallback=90)
        if batch_size in (None, ""):
            # Rotation's own setting, not truncation's. The two measure different costs: truncation's batch
            # is how many rows one delete statement covers, which needs only their keys, while rotation's
            # is how many records are held in memory at once to copy -- each one twice, the warm record and
            # the retained copy built from it. Reusing truncation's default made an out-of-memory kill an
            # order of magnitude more likely than intended, on exactly the large-record tables this
            # feature exists to relieve.
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
            # Sits beside the per-model counts so the summary reads "dry run; 149 object changes" rather
            # than leaving a reader to guess whether the numbers describe work done or work pending.
            result["dry_run"] = True
        else:
            self._close_finished_periods(labels)

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
            # The count it *would* move, not zero. A dry run exists to answer "how much would this do",
            # and a result summary reading 0 answers the wrong question -- the caller knows it was a dry
            # run from the `dry_run` key alongside these counts.
            return total

        moved = 0
        increments = 0
        while True:
            batch = list(eligible[:batch_size])
            if not batch:
                break
            moved_now = self._move_batch(model, mirror, batch, age_field)
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

        A warm `JobResult` is deleted once archived, and its CASCADE children go with it. Log and console
        entries are archived first by `ROTATION_ORDER`, so any still present mean their own rotation has not
        caught up and this result must wait. Output files are never archived at all, so a result carrying
        them is held back unless the operator opts in.
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
                    "Holding back %d job results whose log or console entries are still in warm storage. "
                    "In a dry run those never move, so the job result count is a lower bound rather than a "
                    "prediction; a real run moves them first.",
                    straggler_count,
                )
            else:
                self.logger.info(
                    "Holding back %d job results whose log or console entries are still in warm storage; "
                    "they will rotate once those do.",
                    straggler_count,
                )
            queryset = queryset.exclude(pk__in=stragglers.values("pk"))

        if not include_job_files:
            with_files = queryset.filter(files__isnull=False).distinct()
            file_count = with_files.count()
            if file_count:
                self.logger.warning(
                    "Holding back %d job results with output files attached. Those files are not archived "
                    "and would be deleted with the warm record; re-run with `include_job_files` to accept that.",
                    file_count,
                )
                queryset = queryset.exclude(pk__in=with_files.values("pk"))

        return queryset

    def _move_batch(self, model, mirror, batch, age_field):
        """
        Copy a batch into its periods, then delete the warm rows.

        Copy-then-delete rather than delete-then-copy: a failure between the two leaves the record in both
        places, which the next run resolves, whereas the reverse would lose it.

        Deliberately *not* one transaction across both, and it cannot be: the mirror is written through the
        `changelog_archive` connection while the warm delete goes through `default`, so they are two
        connections and two transactions even when the alias points at the same database. The ordering above
        is what makes that safe. What the transaction here does cover is the warm delete and the period's
        row count together, so a process killed between them cannot leave a count that says fewer records
        were archived than were actually removed from warm storage.
        """
        by_period = {}
        for warm_object in batch:
            period_key = period_key_for(getattr(warm_object, age_field))
            by_period.setdefault(period_key, []).append(warm_object)

        moved = 0
        for period_key, objects in by_period.items():
            segment = self._get_or_create_segment(model, period_key)
            mirrors = [build_mirror_instance(warm_object, mirror, period_key) for warm_object in objects]
            pks = [warm_object.pk for warm_object in objects]
            latest = max(getattr(warm_object, age_field) for warm_object in objects)
            with transaction.atomic():
                mirror.objects.bulk_create(mirrors, ignore_conflicts=True)
                archived = set(mirror.objects.filter(pk__in=pks).values_list("pk", flat=True))
                if len(archived) != len(pks):
                    missing = len(pks) - len(archived)
                    self.logger.error(
                        "%d of %d %s records did not land in period %s; leaving them in warm storage",
                        missing,
                        len(pks),
                        model._meta.label,
                        period_key,
                    )
                deleted = model.objects.filter(pk__in=list(archived)).delete()[0]
                moved += len(archived)
                self._record_progress(segment, len(archived), latest)
            self.logger.debug("Period %s: archived %d and removed %d warm rows", period_key, len(archived), deleted)
        return moved

    def _get_or_create_segment(self, model, period_key):
        """Find or create the registry row for one (model, period)."""
        time_start, time_end = period_bounds_for(period_key)
        segment, created = ArchiveSegment.objects.get_or_create(
            model_label=model._meta.label_lower,
            period_key=period_key,
            defaults={
                "label": period_label_for(period_key),
                "period_granularity": get_settings_or_config("CHANGELOG_ARCHIVE_PERIOD", fallback="year"),
                "time_start": time_start,
                "time_end": time_end,
            },
        )
        if created:
            self.logger.info("Opened retention period %s for %s", segment.label, model._meta.label)
        return segment

    def _record_progress(self, segment, archived_count, latest_time):
        """Update the period's row count and how far rotation has gotten into it."""
        segment.row_count = F("row_count") + archived_count
        if segment.last_rotated_time is None or latest_time > segment.last_rotated_time:
            segment.last_rotated_time = latest_time
        segment.save(update_fields=["row_count", "last_rotated_time"])
        segment.refresh_from_db(fields=["row_count"])

    def _close_finished_periods(self, labels):
        """
        Mark a period closed once it has ended and no warm records remain inside it.

        A closed period carries no staleness claim, and it is the signal truncation uses to decide that a
        period's warm leftovers are safe to delete.
        """
        now = timezone.now()
        for label in labels:
            model = apps.get_model(label)
            age_field = age_field_for(model)
            for segment in ArchiveSegment.objects.filter(model_label=label, is_period_closed=False, time_end__lte=now):
                remaining = model.objects.filter(
                    **{f"{age_field}__gte": segment.time_start, f"{age_field}__lt": segment.time_end}
                ).exists()
                if not remaining:
                    segment.is_period_closed = True
                    segment.save(update_fields=["is_period_closed"])
                    self.logger.info("Closed retention period %s for %s", segment.label, model._meta.label)


class ChangelogTruncation(CascadeDeleteMixin, Job):
    """
    Delete warm change and job history selected by `RetentionRule` filters.

    Rules are resolved through each covered model's own FilterSet, so anything expressible as a filter in
    the UI or REST API is expressible as a retention rule. `exclude` rules protect what they match and win
    over any `include` rule that would otherwise select the same records.

    Every enabled rule applies. There is deliberately no per-run rule picker: `RetentionRule.enabled` is
    already the switch for whether a rule runs, and a second per-run control meant the same rule set was
    described in two places. Worse, narrowing that selection withdrew the protection of any exclude rule
    left out of it, which cost records and showed nothing. Enable and disable rules on the rules
    themselves; use `dry_run` to see what they would do.

    Deletion always proceeds in bounded increments. A single statement against a table of the size this
    feature exists to relieve is the thing being avoided.
    """

    batch_size = IntegerVar(
        description=(
            "Records to delete per increment. Leave empty to use the CHANGELOG_TRUNCATION_BATCH_SIZE setting."
        ),
        label="Batch Size",
        min_value=1,
        required=False,
    )
    dry_run = BooleanVar(
        description="Report what would be deleted without deleting anything.",
        default=True,
    )

    class Meta:
        name = "Changelog Truncation"
        description = "Delete warm change and job history selected by retention rule filters."
        has_sensitive_variables = False

    def run(self, *, batch_size=None, dry_run=True):  # pylint: disable=arguments-differ
        if batch_size in (None, ""):
            batch_size = get_settings_or_config("CHANGELOG_TRUNCATION_BATCH_SIZE", fallback=10000)

        rules = RetentionRule.objects.filter(enabled=True).select_related("content_type").order_by("weight", "name")

        if not rules.exists():
            total = RetentionRule.objects.count()
            if total:
                self.logger.warning(
                    "None of the %d retention rules are enabled, so there is nothing to apply. "
                    "Enable a rule under Extensibility > Logging > Retention Rules.",
                    total,
                )
            else:
                self.logger.warning(
                    "No retention rules exist, so there is nothing to apply. "
                    "Create one under Extensibility > Logging > Retention Rules."
                )
            return {}

        result = {}
        with without_delete_change_logging(self.logger):
            for model, model_rules in self._rules_by_model(rules).items():
                result[model._meta.label] = self._truncate_model(model, model_rules, batch_size, dry_run)

        if dry_run:
            # See the note in `ChangelogRotation.run`.
            result["dry_run"] = True

        return result

    def _rules_by_model(self, rules):
        """Group rules by the model they apply to, skipping any content type we do not cover."""
        grouped = {}
        for rule in rules:
            model = rule.content_type.model_class()
            if model is None:
                self.logger.warning(
                    "Rule `%s` refers to content type `%s`, whose model no longer exists. Skipping.",
                    rule.name,
                    rule.content_type,
                )
                continue
            if model._meta.label_lower not in CHANGELOG_ARCHIVE_COVERED_MODELS:
                self.logger.warning(
                    "Rule `%s` applies to `%s`, which is not covered by changelog retention. Skipping.",
                    rule.name,
                    model._meta.label,
                )
                continue
            grouped.setdefault(model, []).append(rule)
        return grouped

    def _truncate_model(self, model, rules, batch_size, dry_run):
        """Resolve every rule for one model into a single queryset, then delete it in increments."""
        permission = f"{model._meta.app_label}.delete_{model._meta.model_name}"
        if not self.user.has_perm(permission):
            self.logger.error('User "%s" does not have permission to delete %s records', self.user, model._meta.label)
            raise PermissionDenied(f"User does not have delete permissions for {model._meta.label} records")

        # Kept as Q objects over subqueries rather than sets of primary keys. The tables this job exists
        # for run to tens of millions of rows, and materializing every matching key would exhaust memory
        # long before the first delete.
        include_q = Q(pk__in=[])
        exclude_q = Q(pk__in=[])
        include_rules = 0
        for rule in rules:
            queryset = self._resolve_rule(rule, model)
            if queryset is None:
                continue
            count = queryset.count()
            if rule.mode == RetentionRuleModeChoices.MODE_EXCLUDE:
                exclude_q |= Q(pk__in=queryset.values("pk"))
                self.logger.info("Rule `%s` protects %d %s records", rule.name, count, model._meta.label)
            else:
                include_rules += 1
                include_q |= Q(pk__in=queryset.values("pk"))
                self.logger.info("Rule `%s` selects %d %s records", rule.name, count, model._meta.label)

        if not include_rules:
            # Picking only exclude rules is an easy thing to do -- they are listed alongside the others --
            # and the arithmetic answer is a bare zero with nothing to explain it.
            self.logger.warning(
                "No include rule was applied to %s, so nothing was selected. An exclude rule only protects "
                "records from deletion; at least one include rule has to select them first.",
                model._meta.label,
            )
            return 0

        selected = model.objects.filter(include_q)
        protected_count = selected.filter(exclude_q).count()
        if protected_count:
            self.logger.info(
                "%d %s records are selected by an include rule but protected by an exclude rule; keeping them",
                protected_count,
                model._meta.label,
            )
        selected = selected.exclude(exclude_q)

        selected = self._withhold_unrotated(model, selected)

        total = selected.count()
        if not total:
            self.logger.info("No %s records selected for deletion", model._meta.label)
            return 0

        if dry_run:
            self.logger.warning(
                "Dry run: would delete %d %s records in increments of %d", total, model._meta.label, batch_size
            )
            # The count it *would* delete, not zero. See the note in `_rotate_model`.
            return total

        return self._delete_in_batches(model, selected, batch_size)

    def _resolve_rule(self, rule, model):
        """
        Turn a rule's filter parameters and age bound into a queryset.

        The filter goes through the model's own FilterSet, so a rule expresses exactly what the same filter
        would select in the UI or REST API. An invalid filter is refused rather than silently widened to
        everything, since widening here means deleting records the operator did not select.
        """
        queryset = model.objects.all()

        if rule.max_age_days:
            cutoff = timezone.now() - timedelta(days=rule.max_age_days)
            queryset = queryset.filter(**{f"{age_field_for(model)}__lt": cutoff})

        if not rule.scope_filter:
            if rule.max_age_days:
                return queryset
            self.logger.warning(
                "Rule `%s` has neither a filter nor an age bound, so it would select every %s record. Skipping.",
                rule.name,
                model._meta.label,
            )
            return None

        filterset_class = get_filterset_for_model(model)
        if filterset_class is None:
            self.logger.error(
                "No FilterSet found for %s, so rule `%s` cannot be resolved. Skipping.",
                model._meta.label,
                rule.name,
            )
            return None

        filterset = filterset_class(rule.scope_filter, queryset)
        if not filterset.is_valid():
            self.logger.error(
                "Rule `%s` has invalid filter parameters and was not applied: %s",
                rule.name,
                filterset.errors,
            )
            return None

        return filterset.qs

    def _withhold_unrotated(self, model, selected):
        """
        Keep truncation from deleting records that rotation has not moved yet.

        This is what makes the two jobs safe to run in either order. When retention is enabled, a warm
        record old enough to be rotated is rotation's to move, and deleting it first would lose it for
        good. A period whose `ArchiveSegment` is closed has been fully rotated, so its warm leftovers are
        safe to delete; anything older than the warm window in a period that is not closed is withheld.

        Expressed as time ranges rather than period keys, because a warm record has no period column --
        its period is implied by its timestamp, and a closed period is exactly the half-open interval the
        segment records.
        """
        if not get_settings_or_config("CHANGELOG_ARCHIVE_ENABLED", fallback=False):
            return selected

        warm_window_days = get_settings_or_config("CHANGELOG_WARM_WINDOW_DAYS", fallback=90)
        cutoff = timezone.now() - timedelta(days=warm_window_days)
        age_field = age_field_for(model)

        already_rotated = Q(pk__in=[])
        for time_start, time_end in ArchiveSegment.objects.filter(
            model_label=model._meta.label_lower, is_period_closed=True
        ).values_list("time_start", "time_end"):
            already_rotated |= Q(**{f"{age_field}__gte": time_start, f"{age_field}__lt": time_end})

        withheld_q = Q(**{f"{age_field}__lt": cutoff}) & ~already_rotated
        withheld_count = selected.filter(withheld_q).count()
        if withheld_count:
            self.logger.warning(
                "Withholding %d %s records older than the %d-day warm window: their retention period is "
                "not closed yet, so they are the rotation job's to move. Run rotation first.",
                withheld_count,
                model._meta.label,
                warm_window_days,
            )
        return selected.exclude(withheld_q)

    def _delete_in_batches(self, model, selected, batch_size):
        """
        Delete the selected records in bounded increments.

        Each increment is a separate statement with its own cascade walk, so a table large enough to
        motivate this feature never becomes one long-running delete.

        Keys are pulled one page at a time and materialized per batch: the page is bounded by
        `batch_size`, and a concrete list of keys is what the delete needs anyway, since MySQL will not
        accept a LIMIT inside a subquery or a DELETE whose subquery names the table being deleted from.
        """
        total = 0
        increments = 0
        while True:
            batch = list(selected.values_list("pk", flat=True)[:batch_size])
            if not batch:
                break
            queryset = model.objects.filter(pk__in=batch)
            summary = {}
            # CascadeDeleteMixin, shared with LogsCleanup: signals are detached for speed, so the CASCADE
            # walk and the PROTECT refusal are ours to do rather than Django's collector's.
            self.recursive_delete_with_cascade(queryset, summary)
            deleted = summary.get(model._meta.label, 0)
            total += deleted
            increments += 1
            self.logger.info(
                "Increment %d: deleted %d %s records%s",
                increments,
                deleted,
                model._meta.label,
                self._describe_cascade(summary, model),
            )
            if not deleted:
                # Nothing was removed although keys came back, so the next page would be the same one.
                # Stop rather than spin: a PROTECT relationship the cascade walk refuses to break puts us
                # here, and it has already been logged.
                self.logger.warning(
                    "Stopping: %d %s records remain selected but could not be deleted", len(batch), model._meta.label
                )
                break
        self.logger.success("Deleted %d %s records across %d increments", total, model._meta.label, increments)
        return total

    @staticmethod
    def _describe_cascade(summary, model):
        cascaded = {label: count for label, count in summary.items() if label != model._meta.label and count}
        if not cascaded:
            return ""
        detail = ", ".join(f"{count} {label}" for label, count in sorted(cascaded.items()))
        return f" (and {detail})"
