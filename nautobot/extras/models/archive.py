"""
Long-term retention of change and job history.

Warm storage is the live `ObjectChange`, `JobResult`, `JobLogEntry` and `JobConsoleEntry` tables. The
`Archived*` models here mirror them, one table per calendar period, with an `ArchiveSegment` row per
(model, period). A record's own timestamp picks its period, and a read resolves against warm storage or
exactly one period, so ordering and pagination behave as they do warm.

The mirrors declare foreign keys as bare identifier columns, because real ones would couple retained
rows to live records and block truncation. `ChangelogArchiveIntegrityCheck` stands in for CASCADE and
PROTECT, and `check_changelog_archive_schema` for what migrations provided.
"""

import calendar
from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from nautobot.core.celery import NautobotKombuJSONEncoder
from nautobot.core.constants import (  # noqa: F401  # CHANGELOG_ARCHIVE re-exported
    CHANGELOG_ARCHIVE,
    CHARFIELD_MAX_LENGTH,
    COLD_STORAGE_PERMISSION,
)
from nautobot.core.models import BaseModel
from nautobot.extras.choices import (
    JobCancelTypeChoices,
    JobConsoleEntryOutputTypeChoices,
    JobResultStatusChoices,
    LogLevelChoices,
    ObjectChangeActionChoices,
    ObjectChangeEventContextChoices,
)
from nautobot.extras.constants import (
    CHANGELOG_ARCHIVE_MAX_PERIOD_KEY,
    CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD,
    CHANGELOG_MAX_CHANGE_CONTEXT_DETAIL,
    CHANGELOG_MAX_OBJECT_REPR,
    JOB_LOG_MAX_ABSOLUTE_URL_LENGTH,
    JOB_LOG_MAX_GROUPING_LENGTH,
    JOB_LOG_MAX_LOG_OBJECT_LENGTH,
)
from nautobot.extras.models.change_logging import ObjectChangeSnapshotsMixin
from nautobot.extras.models.customfields import CustomFieldModel


def build_mirror_instance(warm_object, mirror_model, period_key):
    """
    Build an unsaved mirror instance with every retained field of `warm_object`.

    The primary key is copied unchanged, which is what makes rotation idempotent. A field present only on
    the mirror raises instead of taking a default, `user_name` below being the one exception.
    """
    values = {"id": warm_object.pk, "period_key": period_key}
    for field in mirror_model._meta.fields:
        name = field.name
        if name in ("id", "period_key"):
            continue
        if name == "user_name" and not hasattr(warm_object, name):
            # `JobResult` reads the username through its `user` foreign key. With the key demoted that
            # would be unrecoverable once the User row is deleted, so rotation denormalizes it, the same
            # trade `ObjectChange.user_name` already makes.
            values[name] = getattr(warm_object.user, "username", "") or ""
        elif hasattr(warm_object, name):
            # Covers plain columns, and demoted foreign keys whose `<name>_id` attribute exists on the
            # warm model too, read as a raw id rather than a related-object fetch.
            values[name] = getattr(warm_object, name)
        else:
            raise ValueError(
                f"{mirror_model.__name__}.{name} has no counterpart on {warm_object._meta.label}. "
                f"Run `nautobot-server check_changelog_archive_schema`."
            )
    return mirror_model(**values)


def archive_model_for(model, period_key=None):
    """
    The retention mirror for `model`'s history, or None if `model` has none.

    Takes the warm model: `archive_model_for(ObjectChange, "2024")` is the class for that year's table.
    Without a period it is the declared mirror, which is the unbounded period.
    """
    from nautobot.extras.registry import registry

    mirror = registry["changelog_archive_models"].get(model._meta.label_lower)
    if mirror is None or period_key is None:
        return mirror
    return period_model_for(mirror, period_key)


def archive_base_of(model):
    """
    The declared mirror `model` stands for: itself, or the mirror a period model was generated from.

    Every lookup keyed on a model class goes through this, because a period model is a different class and
    compares equal to nothing. Getting it wrong is silent wherever the answer picks a database.
    """
    return getattr(model, "archive_base", model)


def warm_model_for(model):
    """
    The warm model a retention mirror stands for, or None when `model` is not a mirror.

    For anything outside retention asking what is being rendered: a mirror has no content type of its own.
    """
    from django.apps import apps

    from nautobot.extras.registry import registry

    declared = archive_base_of(model)
    label = next((warm for warm, mirror in registry["changelog_archive_models"].items() if mirror is declared), None)
    return apps.get_model(label) if label else None


class ArchiveSegment(BaseModel):
    """
    One period of retained history, for one record type.

    `extras.view_archivesegment` hangs off this model, the single gate on reading retained history, so
    renaming it revokes every existing grant. It is also the list of which periods exist, written by
    rotation on first write to a period.
    """

    model_label = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        db_index=True,
        help_text="Label of the warm model whose retained history this period covers, e.g. `extras.objectchange`.",
    )
    period_key = models.CharField(
        max_length=CHANGELOG_ARCHIVE_MAX_PERIOD_KEY,
        db_index=True,
        help_text="Period this segment covers: `unbounded`, or a calendar key such as `2024`, `2024-Q3`, or `2024-07`.",
    )
    label = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        help_text="Name this period is listed under, for a reader choosing one.",
    )
    # Null on both for the unbounded period, which by definition has no bounds. Every caller computing
    # with these has to handle that, which is the honest reading: a sentinel date would let a comparison
    # succeed while standing for a date no record was written under.
    time_start = models.DateTimeField(
        null=True, blank=True, help_text="Inclusive start of the period. Null for the unbounded period."
    )
    time_end = models.DateTimeField(
        null=True, blank=True, help_text="Exclusive end of the period. Null for the unbounded period."
    )
    row_count = models.PositiveBigIntegerField(
        default=0,
        help_text="Records rotated into this period. Verified by the integrity check job.",
    )
    is_period_closed = models.BooleanField(
        default=False,
        help_text="The period has ended and rotation has caught up, so no further records will be filed "
        "under it, and no staleness claim applies to it.",
    )
    last_rotated_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the most recent record rotated into this period, which is how far behind "
        "live activity this period is.",
    )

    documentation_static_path = "docs/user-guide/platform-functionality/change-logging.html"
    natural_key_field_names = ["model_label", "period_key"]
    is_metadata_associable_model = False
    is_data_compliance_model = False
    is_version_controlled = False
    hide_in_diff_view = True

    class Meta:
        # Newest first, unbounded last. Ordering on `period_key` is lexical, and ASCII puts letters
        # above digits, so `unbounded` would sort above `2027`. `nulls_last` avoids inventing a start.
        ordering = ["model_label", models.F("time_start").desc(nulls_last=True)]
        unique_together = [["model_label", "period_key"]]
        # "Period" is the word the docs, the selector and the table use. The class name cannot follow:
        # `extras.view_archivesegment` derives from it, and renaming would revoke every grant.
        verbose_name = "archive period"
        verbose_name_plural = "archive periods"

    def clean(self):
        """
        A calendar period must cover a span of time.

        `time_start` is inclusive and `time_end` exclusive, so an end at or before the start is a period no
        record can belong to. The unbounded period leaves both null and is exempt.
        """
        super().clean()
        if self.period_key != CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD and (self.time_start is None or self.time_end is None):
            raise ValidationError(
                {
                    "time_start": (
                        f"Period `{self.period_key}` is a calendar period, so it needs both a start and an "
                        f"end. Only the `{CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD}` period may leave them unset."
                    )
                }
            )
        if self.time_start and self.time_end and self.time_start >= self.time_end:
            raise ValidationError(
                {
                    "time_end": (
                        f"A period must end after it starts, and this one ends at {self.time_end} having "
                        f"started at {self.time_start}. No record can fall inside it."
                    )
                }
            )

    def __str__(self):
        return f"{self.model_label} {self.label}"


class ArchivedRecord(BaseModel):
    """
    Shared shape for every retained-history mirror.

    `id` is copied from the warm record, so a retained record keeps its primary key and rotation can
    re-run without duplicating.
    """

    # Which period this record is in, read by the templates that carry it into a link. Not a ForeignKey
    # to `ArchiveSegment`: the registry is on `default` and the mirrors on the archive alias, so a real
    # FK would be a cross-database constraint the moment that alias is repointed.
    period_key = models.CharField(
        max_length=CHANGELOG_ARCHIVE_MAX_PERIOD_KEY,
        db_index=True,
        help_text="The period this record belongs to.",
    )

    is_metadata_associable_model = False
    is_data_compliance_model = False
    is_version_controlled = False
    # `ArchivedJobResult` mirrors a model that defines `_custom_field_data`, which is how the feature
    # registry recognizes a custom field model. Left registered, the custom field content type picker
    # offers retained job results, and the orphaned key sweep streams every retained row over the archive
    # database and then writes to the ones it finds keys on. Retained history is immutable.
    is_custom_field_model = False
    hide_in_diff_view = True
    natural_key_field_names = ["id"]

    # The period this model's table holds, overridden by `period_model_for` on each generated class, so
    # a model handed around can say where it came from. The mirrors are the unbounded period.
    period_key_value = CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD

    def __getattr__(self, name):
        """
        Resolve a demoted relation to None rather than raising.

        A mirror declares `job_result_id` and has no `job_result`, and serializers, tables and templates reach
        for the relation by name. Narrow: only names whose `<name>_id` is a real field, so a typo still raises.
        """
        if not name.startswith("_") and not name.endswith("_id"):
            try:
                self._meta.get_field(f"{name}_id")
            except Exception:  # noqa: S110  # FieldDoesNotExist, plus anything during model setup
                pass
            else:
                return None
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    # Retained records have their own pages, so these are the archived routes, not the warm ones. A
    # mirror with no page is absent, and `get_absolute_url` returns None so a linkified column renders
    # plain text instead of failing the row.
    # Keyed on the declared mirror: the route belongs to the kind of record, not to the period, and a
    # retained record opens at the URL it had before rotation.
    DETAIL_ROUTES = {
        "extras.archivedobjectchange": "extras:objectchange",
        "extras.archivedjobresult": "extras:jobresult",
    }

    def get_absolute_url(self, api=False):
        """
        The record's read-only detail page, or None where it has none.

        None rather than raising, so a linkified column renders plain text instead of failing the row.
        """
        from django.urls import NoReverseMatch, reverse

        route = self.DETAIL_ROUTES.get(archive_base_of(type(self))._meta.label_lower)
        if route is None or api:
            return None
        try:
            return reverse(route, kwargs={"pk": self.pk})
        except NoReverseMatch:
            return None

    class Meta:
        abstract = True
        # Retained history is read-only through the ORM. Access is gated on `extras.view_archivesegment`
        # instead, so per-model permissions here would be four grants where the design calls for one.
        default_permissions = ()


class ArchivedObjectChangeBase(ObjectChangeSnapshotsMixin, ArchivedRecord):
    """
    Every field and method of a retained `extras.ObjectChange`, shared by each period's table.

    Abstract so `period_model_for` can generate a class per calendar period from it. `ArchivedObjectChange`
    below is the unbounded period, and the model the table, filterset, views and serializer declare.
    """

    time = models.DateTimeField(editable=False, db_index=True)
    user_id = models.UUIDField(blank=True, null=True)
    user_name = models.CharField(max_length=150, editable=False, db_index=True)
    request_id = models.UUIDField(editable=False, db_index=True)
    action = models.CharField(max_length=50, choices=ObjectChangeActionChoices)
    changed_object_type_id = models.PositiveIntegerField(blank=True, null=True)
    changed_object_id = models.UUIDField(db_index=True)
    change_context = models.CharField(
        max_length=50,
        choices=ObjectChangeEventContextChoices,
        editable=False,
        db_index=True,
    )
    change_context_detail = models.CharField(max_length=CHANGELOG_MAX_CHANGE_CONTEXT_DETAIL, blank=True, editable=False)
    related_object_type_id = models.PositiveIntegerField(blank=True, null=True)
    related_object_id = models.UUIDField(blank=True, null=True)
    object_repr = models.CharField(max_length=CHANGELOG_MAX_OBJECT_REPR, editable=False)
    object_data = models.JSONField(encoder=DjangoJSONEncoder, editable=False, null=True, blank=True)
    object_data_v2 = models.JSONField(encoder=NautobotKombuJSONEncoder, editable=False, null=True, blank=True)

    class Meta(ArchivedRecord.Meta):
        abstract = True
        default_permissions = ()
        ordering = ["-time"]
        get_latest_by = "time"
        verbose_name = "archived object change"
        verbose_name_plural = "archived object changes"
        indexes = [
            models.Index(fields=["period_key", "-time"]),
            models.Index(fields=["changed_object_type_id", "changed_object_id"]),
            models.Index(fields=["related_object_type_id", "related_object_id"]),
            models.Index(fields=["request_id"]),
            models.Index(fields=["user_name"]),
        ]

    def get_related_changes(self, user=None, permission="view"):
        """
        The other retained changes to this object, within this record's period.

        `user` and `permission` match the warm signature and are ignored: a mirror has no per-object
        permissions. One period, because `type(self)` is that period's table; a neighbour across a boundary is
        not found, which `get_snapshots` handles as it handles a deleted predecessor.
        """
        return (
            type(self)
            .objects.filter(
                changed_object_type_id=self.changed_object_type_id,
                changed_object_id=self.changed_object_id,
            )
            .exclude(pk=self.pk)
        )

    @property
    def changed_object_type(self):
        """
        The content type this record's `changed_object_type_id` names, or None.

        A content type is schema metadata rather than a changelog record, and `get_for_id` is cached per
        process. None where the app has been uninstalled since, which the integrity check reports.
        """
        return self._content_type_for(self.changed_object_type_id)

    @property
    def related_object_type(self):
        """The content type this record's `related_object_type_id` names, or None."""
        return self._content_type_for(self.related_object_type_id)

    @staticmethod
    def _content_type_for(type_id):
        from django.contrib.contenttypes.models import ContentType

        if not type_id:
            return None
        try:
            return ContentType.objects.get_for_id(type_id)
        except ContentType.DoesNotExist:
            return None

    def get_action_class(self):
        """CSS class for the action badge, as `ObjectChange` provides it.

        The change log table renders retained rows with the same columns as warm ones, so a mirror has to
        answer the presentation helpers those columns call.
        """
        return ObjectChangeActionChoices.CSS_CLASSES.get(self.action)

    def __str__(self):
        return f"{self.object_repr} {self.action} by {self.user_name}"


class ArchivedObjectChange(ArchivedObjectChangeBase):
    """Retained mirror of `extras.ObjectChange`: the unbounded period's table."""

    period_base = ArchivedObjectChangeBase

    class Meta(ArchivedObjectChangeBase.Meta):
        db_table = "extras_archivedobjectchange_unbounded"


class ArchivedJobResultBase(ArchivedRecord, CustomFieldModel):
    """
    Every field and method of a retained `extras.JobResult`, shared by each period's table.

    Abstract for the reason `ArchivedObjectChangeBase` is.
    """

    job_model_id = models.UUIDField(blank=True, null=True)
    name = models.CharField(max_length=CHARFIELD_MAX_LENGTH, db_index=True)
    task_name = models.CharField(  # noqa: DJ001  # mirrors the warm column, which is nullable
        max_length=CHARFIELD_MAX_LENGTH,
        null=True,
        db_index=True,
        help_text="Registered name of the Celery task for this job. Internal use only.",
    )
    date_created = models.DateTimeField(db_index=True)
    date_started = models.DateTimeField(null=True, blank=True, db_index=True)
    date_done = models.DateTimeField(null=True, blank=True, db_index=True)
    user_id = models.UUIDField(blank=True, null=True)
    # Not a mirror: `JobResult` has no `user_name`, it reads through the `user` FK. With the FK demoted
    # to an id column, the username would be unrecoverable once the User row is deleted, so rotation
    # denormalizes it here. This is the same trade `ObjectChange.user_name` already makes.
    user_name = models.CharField(max_length=150, blank=True, default="")
    status = models.CharField(
        max_length=30,
        choices=JobResultStatusChoices,
        db_index=True,
        default=JobResultStatusChoices.STATUS_PENDING,
        help_text="Current state of the Job being run",
    )
    result = models.JSONField(
        verbose_name="Result Data",
        encoder=NautobotKombuJSONEncoder,
        null=True,
        blank=True,
        editable=False,
        help_text="The data returned by the task",
    )
    worker = models.CharField(max_length=100, null=True, default=None)  # noqa: DJ001  # mirrors the warm column
    task_args = models.JSONField(blank=True, default=list, encoder=NautobotKombuJSONEncoder)
    task_kwargs = models.JSONField(blank=True, default=dict, encoder=NautobotKombuJSONEncoder)
    celery_kwargs = models.JSONField(blank=True, default=dict, encoder=NautobotKombuJSONEncoder)
    traceback = models.TextField(blank=True, null=True)  # noqa: DJ001  # mirrors the warm column
    meta = models.JSONField(null=True, default=None, editable=False)
    scheduled_job_id = models.UUIDField(blank=True, null=True)
    debug_log_count = models.PositiveIntegerField(blank=True, null=True, editable=False)
    success_log_count = models.PositiveIntegerField(blank=True, null=True, editable=False)
    info_log_count = models.PositiveIntegerField(blank=True, null=True, editable=False)
    warning_log_count = models.PositiveIntegerField(blank=True, null=True, editable=False)
    error_log_count = models.PositiveIntegerField(blank=True, null=True, editable=False)
    canceled_by_id = models.UUIDField(blank=True, null=True)
    canceled_by_user_name = models.CharField(max_length=150, blank=True, editable=False)
    cancel_type = models.CharField(
        max_length=30,
        choices=JobCancelTypeChoices,
        blank=True,
        help_text="Cancel type of the Job being canceled",
    )
    date_canceled = models.DateTimeField(null=True, blank=True, help_text="Timestamp at which the job was canceled")
    # `_custom_field_data` comes from CustomFieldModel, which also supplies the accessors the warm detail
    # page calls. Rotation copies the raw JSON, so no custom field value is lost.

    @property
    def job_description(self):
        """
        Empty: the warm property reads it through the `job_model` relation, which is demoted here.

        Defined rather than left to `__getattr__` because there is no `job_description_id` field to key off.
        """
        return None

    @property
    def duration(self):
        """Same as the warm property: derived from the stored timestamps, which the mirror also has."""
        if not self.date_done or not self.date_started:
            return None
        minutes, seconds = divmod((self.date_done - self.date_started).total_seconds(), 60)
        return f"{int(minutes)} minutes, {seconds:.2f} seconds"

    @property
    def files(self):
        """
        Empty: job output files are not archived.

        Rotation excludes any result with files unless the operator opts in, because those files are deleted
        with the warm record rather than moved.
        """
        return []

    @property
    def is_unready_state(self):
        """Always False: a retained result finished long ago, by definition."""
        return False

    @property
    def job_log_entries(self):
        """
        This result's retained log entries.

        The warm model uses a reverse foreign key, which the mirrors do not have. Matching on the stored
        identifier gives the same answer, rotation moving children before parents.
        """

        # This result's own period: a run's log and console entries belong to the same period the
        # result is, because they share its timestamp.
        return period_model_for(ArchivedJobLogEntry, self.period_key).objects.filter(job_result_id=self.pk)

    @property
    def job_console_entries(self):
        """This result's retained console output. See `job_log_entries`."""

        return period_model_for(ArchivedJobConsoleEntry, self.period_key).objects.filter(job_result_id=self.pk)

    @property
    def queue(self):
        """Same as warm: read from the stored celery kwargs."""
        if self.celery_kwargs and isinstance(self.celery_kwargs, dict):
            return self.celery_kwargs.get("queue")
        return None

    @property
    def queue_type(self):
        """
        Same as warm, minus the fallback that looks the queue up by name.

        That fallback resolves a live `JobQueue`, which is the kind of reference retention does not keep.
        """
        if self.celery_kwargs and isinstance(self.celery_kwargs, dict):
            return self.celery_kwargs.get("nautobot_job_queue_type")
        return None

    @property
    def console_log(self):
        """Same as warm: read from the stored celery kwargs."""
        if self.celery_kwargs and isinstance(self.celery_kwargs, dict):
            return self.celery_kwargs.get("nautobot_job_console_log", False)
        return False

    class Meta(ArchivedRecord.Meta):
        abstract = True
        default_permissions = ()
        ordering = ["-date_created"]
        get_latest_by = "date_created"
        verbose_name = "archived job result"
        verbose_name_plural = "archived job results"
        indexes = [
            models.Index(fields=["period_key", "-date_created"]),
            models.Index(fields=["status", "-date_created"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.name} created at {self.date_created} ({self.status})"


class ArchivedJobResult(ArchivedJobResultBase):
    """Retained mirror of `extras.JobResult`: the unbounded period's table."""

    period_base = ArchivedJobResultBase

    class Meta(ArchivedJobResultBase.Meta):
        db_table = "extras_archivedjobresult_unbounded"


class ArchivedJobLogEntryBase(ArchivedRecord):
    """
    Every field of a retained `extras.JobLogEntry`, shared by each period's table.

    Abstract for the reason `ArchivedObjectChangeBase` is.
    """

    job_result_id = models.UUIDField(db_index=True)
    log_level = models.CharField(
        max_length=32, choices=LogLevelChoices, db_index=True, default=LogLevelChoices.LOG_INFO
    )
    grouping = models.CharField(max_length=JOB_LOG_MAX_GROUPING_LENGTH, default="main")
    message = models.TextField(blank=True)
    created = models.DateTimeField(db_index=True)
    log_object = models.CharField(max_length=JOB_LOG_MAX_LOG_OBJECT_LENGTH, blank=True, default="")
    absolute_url = models.CharField(max_length=JOB_LOG_MAX_ABSOLUTE_URL_LENGTH, blank=True, default="")

    class Meta(ArchivedRecord.Meta):
        abstract = True
        default_permissions = ()
        ordering = ["created"]
        get_latest_by = "created"
        verbose_name = "archived job log entry"
        verbose_name_plural = "archived job log entries"
        indexes = [
            # Mirrors `extras_joblog_jr_created_idx`; this is the access path for a job result's log table.
            models.Index(fields=["job_result_id", "created"]),
            models.Index(fields=["period_key", "created"]),
        ]

    def __str__(self):
        return self.message


class ArchivedJobLogEntry(ArchivedJobLogEntryBase):
    """Retained mirror of `extras.JobLogEntry`: the unbounded period's table."""

    period_base = ArchivedJobLogEntryBase

    class Meta(ArchivedJobLogEntryBase.Meta):
        db_table = "extras_archivedjoblogentry_unbounded"


class ArchivedJobConsoleEntryBase(ArchivedRecord):
    """
    Every field of a retained `extras.JobConsoleEntry`, shared by each period's table.

    Abstract for the reason `ArchivedObjectChangeBase` is.
    """

    job_result_id = models.UUIDField(db_index=True)
    timestamp = models.DateTimeField(help_text="Timestamp when this output has been produced / received")
    output_type = models.CharField(
        max_length=10,
        choices=JobConsoleEntryOutputTypeChoices,
        default=JobConsoleEntryOutputTypeChoices.TYPE_OUTPUT,
        help_text="Type of the output (e.g. stdout, stderr, output)",
    )
    text = models.TextField(help_text="Actual line of output data")

    class Meta(ArchivedRecord.Meta):
        abstract = True
        default_permissions = ()
        ordering = ["timestamp"]
        get_latest_by = "timestamp"
        verbose_name = "archived job console entry"
        verbose_name_plural = "archived job console entries"
        indexes = [
            models.Index(fields=["job_result_id", "timestamp"]),
            models.Index(fields=["period_key", "timestamp"]),
        ]

    def __str__(self):
        return self.text


class ArchivedJobConsoleEntry(ArchivedJobConsoleEntryBase):
    """Retained mirror of `extras.JobConsoleEntry`: the unbounded period's table."""

    period_base = ArchivedJobConsoleEntryBase

    class Meta(ArchivedJobConsoleEntryBase.Meta):
        db_table = "extras_archivedjobconsoleentry_unbounded"


# One concrete class per (mirror, period key), built on first use and reused after. Keyed on the mirror
# class itself, so two record types never share an entry.
_PERIOD_MODELS = {}


#
# Calendar periods. Everything below divides retained history by time: which period a record
# belongs to, what that period covers, and the per-period class and table that hold it.
#


def period_key_for(timestamp, granularity=None):
    """
    The period key a record with this timestamp is written under.

    The single definition of how records are assigned to periods, so rotation and truncation cannot
    disagree about where a record went. `granularity` defaults to `CHANGELOG_ARCHIVE_PERIOD`.
    """
    from django.conf import settings

    from nautobot.extras.choices import ChangelogArchivePeriodChoices

    if granularity is None:
        granularity = getattr(settings, "CHANGELOG_ARCHIVE_PERIOD", ChangelogArchivePeriodChoices.PERIOD_UNBOUNDED)
    if granularity == ChangelogArchivePeriodChoices.PERIOD_UNBOUNDED:
        return CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD
    if granularity == ChangelogArchivePeriodChoices.PERIOD_MONTH:
        return f"{timestamp.year}-{timestamp.month:02d}"
    if granularity == ChangelogArchivePeriodChoices.PERIOD_QUARTER:
        return f"{timestamp.year}-Q{(timestamp.month - 1) // 3 + 1}"
    return str(timestamp.year)


def period_bounds_for(period_key):
    """
    The inclusive start and exclusive end of a period, as timezone-aware datetimes.

    Inverse of `period_key_for`. The unbounded period returns `(None, None)`, so every caller has to
    handle it; a sentinel date would compare against a date no record was written under.
    """
    from django.utils import timezone

    if period_key == CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD:
        return None, None

    tz = timezone.get_current_timezone()

    def _at(year, month):
        return datetime(year, month, 1, tzinfo=tz)

    if "-Q" in period_key:
        year, quarter = (int(part) for part in period_key.split("-Q"))
        start_month = (quarter - 1) * 3 + 1
        end_year, end_month = (year + 1, 1) if quarter == 4 else (year, start_month + 3)
        return _at(year, start_month), _at(end_year, end_month)
    if "-" in period_key:
        year, month = (int(part) for part in period_key.split("-"))
        end_year, end_month = (year + 1, 1) if month == 12 else (year, month + 1)
        return _at(year, month), _at(end_year, end_month)
    year = int(period_key)
    return _at(year, 1), _at(year + 1, 1)


def period_label_for(period_key):
    """The name a period is listed under, for a reader choosing one."""
    if period_key == CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD:
        return "All time"
    if "-Q" in period_key:
        year, quarter = period_key.split("-Q")
        return f"{year} Q{quarter}"
    if "-" in period_key:
        year, month = period_key.split("-")
        return f"{calendar.month_name[int(month)]} {year}"
    return period_key


def period_table_name(mirror, period_key):
    """
    The table one period of `mirror` is stored in.

    Built from the app label and model name, so the unbounded period resolves to the table migration 0149
    created; `test_changelog_archive_periods` pins that. `2024-Q3` becomes `2024_q3`.
    """
    suffix = period_key.lower().replace("-", "_")
    return f"{mirror._meta.app_label}_{mirror._meta.model_name}_{suffix}"


def period_model_for(mirror, period_key):
    """
    The concrete model that reads and writes one period of `mirror`.

    The unbounded period is `mirror` itself. Every other period is generated from `mirror.period_base`,
    differing only in `db_table`, and taken out of the app registry by `_unregister`. All of them inherit
    the same fields, which is what lets one table and one filterset serve every period.
    """
    if period_key == CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD:
        return mirror
    cached = _PERIOD_MODELS.get((mirror, period_key))
    if cached is not None:
        return cached
    base = mirror.period_base
    meta = type("Meta", (base.Meta,), {"db_table": period_table_name(mirror, period_key)})
    model = type(
        f"{mirror.__name__}{''.join(c for c in period_key.title() if c.isalnum())}",
        (base,),
        {
            "__module__": mirror.__module__,
            "Meta": meta,
            "archive_base": mirror,
            "period_key_value": period_key,
        },
    )
    _unregister(model)
    _PERIOD_MODELS[(mirror, period_key)] = model
    return model


def _unregister(model):
    """
    Take a period model back out of Django's app registry.

    Defining a concrete model registers it, and `apps.get_models()` decides global search, the
    searchable-fields artifact, and what `makemigrations` writes migrations for. Safe because
    `period_model_for` is the only way to reach a period model.
    """
    from django.apps import apps

    apps.all_models[model._meta.app_label].pop(model._meta.model_name, None)
    apps.clear_cache()


def period_table_exists(mirror, period_key, using=CHANGELOG_ARCHIVE):
    """Whether this period's table has been created on `using`."""
    from django.db import connections

    connection = connections[using]
    with connection.cursor() as cursor:
        return period_table_name(mirror, period_key) in connection.introspection.table_names(cursor)


def ensure_period_table(mirror, period_key, using=CHANGELOG_ARCHIVE):
    """
    Create this period's table if it does not exist yet, and return its model.

    The unbounded period's table comes from migration 0149, so for that period this creates nothing.
    """
    from django.db import connections

    model = period_model_for(mirror, period_key)
    if period_table_exists(mirror, period_key, using=using):
        return model
    with connections[using].schema_editor() as schema_editor:
        schema_editor.create_model(model)
    return model


def ensure_period(period_key, using=CHANGELOG_ARCHIVE):
    """
    Open a period by creating every covered model's table for it, and return them.

    A period is one unit. Creating them lazily leaves a period whose console table does not exist, and
    reading a retained result's console tab then raises instead of showing an empty one.
    """
    from nautobot.extras.registry import registry

    return {
        label: ensure_period_table(mirror, period_key, using=using)
        for label, mirror in registry["changelog_archive_models"].items()
    }


def drop_period_table(mirror, period_key, using=CHANGELOG_ARCHIVE):
    """
    Drop a whole period's table.

    This is what the arrangement buys: `DROP TABLE` returns the space at once, where deleting the rows
    leaves the table as large as it was.
    """
    from django.db import connections

    if not period_table_exists(mirror, period_key, using=using):
        return False
    with connections[using].schema_editor() as schema_editor:
        schema_editor.delete_model(period_model_for(mirror, period_key))
    return True


def period_models_for(mirror):
    """
    Every period of `mirror` holding retained history, newest first and the unbounded period last.

    Anything sweeping retained history iterates this; `mirror.objects` alone reads the unbounded table.
    That period is always included, which spares an upgrade from the single-period release a data
    migration.

    A period whose table is gone is left out, because querying it raises `UndefinedTable` and aborts the
    sweep. Introspection is skipped when the unbounded period is the only one.
    """
    from django.db import connections

    warm = warm_model_for(mirror)
    keys = (
        ArchiveSegment.objects.filter(model_label=warm._meta.label_lower)
        .exclude(period_key=CHANGELOG_ARCHIVE_UNBOUNDED_PERIOD)
        .values_list("period_key", flat=True)
    )
    models_for_periods = [period_model_for(mirror, key) for key in keys]
    if not models_for_periods:
        return [mirror]
    connection = connections[CHANGELOG_ARCHIVE]
    with connection.cursor() as cursor:
        existing = set(connection.introspection.table_names(cursor))
    return [model for model in models_for_periods if model._meta.db_table in existing] + [mirror]
