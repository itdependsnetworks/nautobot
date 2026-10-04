"""
System jobs maintaining changelog long-term retention.

`ChangelogRotation` moves change and job history past the warm window into retained storage, which is
what keeps the warm tables a working set rather than the whole history.

`ChangelogArchiveIntegrityCheck` stands in for the CASCADE the mirrors gave up when their foreign keys
became identifier columns.

`ChangelogTruncation` deletes warm records the operator has decided not to keep. It is deliberately
independent of rotation: deletion is the intended outcome, not a side effect of archiving, and it works
whether or not any retention period exists.

`LogsCleanup` remains the age-only, delete-everything-older-than-N-days tool. This is the filter-driven
one, and the two share `CascadeDeleteMixin` rather than each carrying its own cascade walk.
"""

from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from nautobot.core.jobs.cleanup import CascadeDeleteMixin
from nautobot.core.utils.config import get_settings_or_config
from nautobot.core.utils.lookup import get_filterset_for_model
from nautobot.extras.choices import RetentionRuleModeChoices
from nautobot.extras.constants import CHANGELOG_ARCHIVE_COVERED_MODELS, CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD
from nautobot.extras.context_managers import without_delete_change_logging
from nautobot.extras.jobs import BooleanVar, IntegerVar, Job, MultiChoiceVar
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    ArchiveSegment,
    JobResult,
    RetentionRule,
)
from nautobot.extras.models.archive import build_mirror_instance
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
            moved_now = self._move_batch(model, mirror, batch, age_field, cutoff)
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

    def _move_batch(self, model, mirror, batch, age_field, cutoff):
        """
        Copy a batch into retained storage, then delete the warm rows.

        Copy then delete, because a failure between the two leaves the record in both places, which the next
        run resolves. It cannot be one transaction: the two sides are different connections.
        """
        pks = [warm_object.pk for warm_object in batch]
        # PLACEHOLDER: everything still goes to the unbounded period. ABSTRACT-2 files each record under
        # the period its own timestamp falls in.
        instances = [
            build_mirror_instance(warm_object, mirror, CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD) for warm_object in batch
        ]
        mirror.objects.bulk_create(instances, ignore_conflicts=True)
        archived = set(mirror.objects.filter(pk__in=pks).values_list("pk", flat=True))
        if len(archived) != len(pks):
            self.logger.error(
                "%d of %d %s records were not written to retained storage; leaving them in warm storage",
                len(pks) - len(archived),
                len(pks),
                model._meta.label,
            )
        self._record_segment(model, mirror, batch, age_field, cutoff)

        with transaction.atomic():
            deleted = model.objects.filter(pk__in=list(archived)).delete()[0]
        self.logger.debug("Archived %d and removed %d warm rows", len(archived), deleted)
        return len(archived)

    @staticmethod
    def _record_segment(model, mirror, batch, age_field, cutoff):  # `cutoff` closes a period
        """
        Record that this period exists, and how much is in it.

        Written after the rows, so a segment never claims a period that failed to write. `row_count` is read
        back from the table instead of added to, so a re-run leaves it where it was.
        """
        newest = max(getattr(warm_object, age_field) for warm_object in batch)
        segment, _ = ArchiveSegment.objects.get_or_create(
            model_label=model._meta.label_lower,
            period_key=CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD,
            defaults={"label": "All time"},
        )
        segment.row_count = mirror.objects.count()
        if segment.last_rotated_time is None or newest > segment.last_rotated_time:
            segment.last_rotated_time = newest
        # The unbounded period never ends, so it is never closed: rotation can always file more into it.
        segment.save()


class ChangelogArchiveIntegrityCheck(Job):
    """
    Stand in for what CASCADE used to do for retained history.

    The mirrors declare their references as bare identifier columns, so a retained record can outlive what
    it points at. Deletes only when asked: a dangling reference is a reason to look, not to discard.
    """

    repair = BooleanVar(
        description="Delete the records reported instead of only reporting them.",
        default=False,
    )

    class Meta:
        name = "Changelog Archive Integrity Check"
        description = "Report retained records whose referent no longer exists."
        has_sensitive_variables = False

    def run(self, *, repair=False):  # pylint: disable=arguments-differ
        result = {}
        for name, finder in (
            ("orphaned_log_entries", self._find_orphaned_log_entries),
            ("orphaned_console_entries", self._find_orphaned_console_entries),
            ("stale_content_types", self._find_stale_content_types),
        ):
            queryset = finder()
            count = queryset.count()
            result[name] = count
            if not count:
                self.logger.info("%s: none found", name)
                continue
            if repair:
                deleted = queryset.delete()[0]
                self.logger.warning("%s: deleted %d records", name, deleted)
                result[name] = deleted
            else:
                self.logger.warning("%s: %d records found. Re-run with `repair` to delete them.", name, count)

        # Not a finder like the others: a duplicate is reported, never deleted. Which copy to keep is the
        # operator's call, and re-running rotation resolves it without this job touching anything.
        result["duplicated_records"] = self._find_duplicate_records()
        return result

    def _find_orphaned_log_entries(self):
        """Retained log entries whose job result is in neither warm storage nor retained storage."""
        return self._orphans_for(ArchivedJobLogEntry)

    def _find_orphaned_console_entries(self):
        return self._orphans_for(ArchivedJobConsoleEntry)

    def _orphans_for(self, mirror):
        """Entries whose job result is in neither warm storage nor retained storage."""
        # Every table a job result could still be in: the warm one, and the retained one.
        missing = self._missing_referents(mirror, "job_result_id", [JobResult, ArchivedJobResult])
        return mirror.objects.filter(job_result_id__in=missing)

    def _find_stale_content_types(self):
        """
        Retained changes pointing at a content type that no longer exists.

        `ContentType` is small, so its keys are compared as a literal list, for the same cross-connection
        reason as `_missing_referents`.
        """
        known = list(ContentType.objects.values_list("pk", flat=True))
        return ArchivedObjectChange.objects.filter(changed_object_type_id__isnull=False).exclude(
            changed_object_type_id__in=known
        )

    def _find_duplicate_records(self):
        """
        A record in both warm storage and retention was copied but never removed.

        What an interrupted rotation leaves behind. Harmless to read past, but the warm table is not as small
        as the operator thinks.
        """
        total = 0
        for label, mirror in registry["changelog_archive_models"].items():
            warm = apps.get_model(label)
            # Chunked in Python for the same reason as `_missing_referents`: the two are stored on different
            # connections, so a subquery across them cannot be relied on.
            count = 0
            offset = 0
            retained_pks = mirror.objects.values_list("pk", flat=True)
            while True:
                chunk = list(retained_pks[offset : offset + 10000])
                if not chunk:
                    break
                count += warm.objects.filter(pk__in=chunk).count()
                offset += 10000
            if count:
                total += count
                self.logger.warning(
                    "%d %s records exist in both warm storage and retention; re-run rotation to clear them",
                    count,
                    warm._meta.label,
                )
        if not total:
            self.logger.info("No record exists in both warm storage and retention")
        return total

    @staticmethod
    def _missing_referents(mirror, field_name, referent_models):
        """
        Which values of `mirror.field_name` name nothing that still exists.

        Compared in chunks in Python instead of as a subquery, because the two sides are on different
        connections and may be on different hosts.

        The caller passes every table a referent could be in, so a log entry is orphaned only once its job
        result is in none of them.
        """
        CHUNK = 10000
        missing = []
        distinct_ids = (
            mirror.objects.exclude(**{f"{field_name}__isnull": True}).values_list(field_name, flat=True).distinct()
        )
        offset = 0
        while True:
            chunk = list(distinct_ids[offset : offset + CHUNK])
            if not chunk:
                break
            found = set()
            for table in referent_models:
                found |= set(table.objects.filter(pk__in=chunk).values_list("pk", flat=True))
            missing.extend(value for value in chunk if value not in found)
            offset += CHUNK
        return missing


class ChangelogTruncation(CascadeDeleteMixin, Job):
    """
    Delete warm change and job history selected by `RetentionRule` filters.

    Rules resolve through each covered model's own FilterSet, and `exclude` rules win over any `include`
    rule matching the same records. Every enabled rule applies, with no per-run picker: narrowing the
    selection per run withdrew the protection of any exclude rule left out, silently. Deletion proceeds in
    bounded increments.
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

        Through the model's own FilterSet, so a rule selects what the same filter would. An invalid filter is
        refused rather than widened to everything, since widening here deletes records nobody selected.
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
        Prevent truncation from deleting records that rotation has not moved yet.

        This is what makes the two jobs safe to run in either order: a warm record old enough to rotate is
        rotation's to move, and deleting it first would lose it.
        """
        if not settings.CHANGELOG_ARCHIVE_ENABLED:
            return selected

        warm_window_days = get_settings_or_config("CHANGELOG_WARM_WINDOW_DAYS", fallback=90)
        cutoff = timezone.now() - timedelta(days=warm_window_days)
        age_field = age_field_for(model)
        mirror = registry["changelog_archive_models"].get(model._meta.label_lower)

        # A list of keys, not a subquery: the two models are on different connections.
        rotated_pks = []
        if mirror is not None:
            candidates = list(selected.filter(**{f"{age_field}__lt": cutoff}).values_list("pk", flat=True))
            rotated_pks = list(mirror.objects.filter(pk__in=candidates).values_list("pk", flat=True))

        withheld_q = Q(**{f"{age_field}__lt": cutoff}) & ~Q(pk__in=rotated_pks)
        withheld_count = selected.filter(withheld_q).count()
        if withheld_count:
            self.logger.warning(
                "Withholding %d %s records older than the %d-day warm window: rotation has not moved them "
                "into retained storage yet, so they are its to move. Run rotation first.",
                withheld_count,
                model._meta.label,
                warm_window_days,
            )
        return selected.exclude(withheld_q)

    def _delete_in_batches(self, model, selected, batch_size):
        """
        Delete the selected records in bounded increments.

        Each increment is a separate statement with its own cascade walk. Keys are materialized per batch
        because MySQL accepts neither a LIMIT inside a subquery nor a DELETE whose subquery names its own
        table.
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
