"""
System jobs maintaining changelog long-term retention.

`ChangelogTruncation` deletes warm records the operator has decided not to keep. It is deliberately
independent of rotation: deletion is the intended outcome, not a side effect of archiving, and it works
whether or not any retention period exists.

`LogsCleanup` remains the age-only, delete-everything-older-than-N-days tool. This is the filter-driven
one, and the two share `CascadeDeleteMixin` rather than each carrying its own cascade walk.
"""

from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from nautobot.core.jobs.cleanup import CascadeDeleteMixin
from nautobot.core.utils.config import get_settings_or_config
from nautobot.core.utils.lookup import get_filterset_for_model
from nautobot.extras.choices import RetentionRuleModeChoices
from nautobot.extras.constants import CHANGELOG_ARCHIVE_COVERED_MODELS
from nautobot.extras.context_managers import without_delete_change_logging
from nautobot.extras.jobs import BooleanVar, IntegerVar, Job
from nautobot.extras.models import (
    ArchiveSegment,
    RetentionRule,
)
from nautobot.extras.models.archive import (
    age_field_for,
)

name = "System Jobs"


# Rotation order matters. JobLogEntry and JobConsoleEntry are CASCADE children of JobResult, so deleting a
# warm JobResult first would take its warm log entries with it. Children are archived before parents.
ROTATION_ORDER = (
    "extras.objectchange",
    "extras.joblogentry",
    "extras.jobconsoleentry",
    "extras.jobresult",
)


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
