"""
Long-term retention of change and job history.

Warm storage is the live `ObjectChange`, `JobResult`, `JobLogEntry`, and `JobConsoleEntry` tables,
holding a recent window. Retained history lives in the mirrored `Archived*` models here, filed by
the calendar period a record's own timestamp falls in, with one `ArchiveSegment` row per
(model, period).

A read resolves against warm storage or against exactly one retained period, never both and never
several, so ordering and pagination behave the same as they do for a warm read.

The mirrors deliberately hold foreign keys as bare identifier columns: relationships are not enforced
once a record is separated from warm storage, and real foreign keys would couple retained rows to live
records and block truncation. `ChangelogArchiveIntegrityCheck` and `ChangelogArchiveReconciliation`
stand in for what CASCADE and PROTECT provided, and `check_changelog_archive_schema` stands in for
what migrations provided.
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
    ChangelogArchivePeriodChoices,
    JobCancelTypeChoices,
    JobConsoleEntryOutputTypeChoices,
    JobResultStatusChoices,
    LogLevelChoices,
    ObjectChangeActionChoices,
    ObjectChangeEventContextChoices,
)
from nautobot.extras.constants import (
    CHANGELOG_ARCHIVE_MAX_PERIOD_KEY,
    CHANGELOG_MAX_CHANGE_CONTEXT_DETAIL,
    CHANGELOG_MAX_OBJECT_REPR,
    JOB_LOG_MAX_ABSOLUTE_URL_LENGTH,
    JOB_LOG_MAX_GROUPING_LENGTH,
    JOB_LOG_MAX_LOG_OBJECT_LENGTH,
)
from nautobot.extras.models.change_logging import ObjectChangeSnapshotsMixin
from nautobot.extras.models.customfields import CustomFieldModel

# The timestamp field that means "when this record happened", per covered model. Stated explicitly rather
# than probed for, because getting it wrong silently files records under the wrong period.
CHANGELOG_ARCHIVE_AGE_FIELDS = {
    "extras.objectchange": "time",
    "extras.jobresult": "date_created",
    "extras.joblogentry": "created",
    "extras.jobconsoleentry": "timestamp",
}


def age_field_for(model):
    """The timestamp field deciding which period a record of `model` is filed under."""
    try:
        return CHANGELOG_ARCHIVE_AGE_FIELDS[model._meta.label_lower]
    except KeyError:
        raise ValueError(f"{model._meta.label} is not covered by changelog retention") from None


def period_key_for(timestamp, granularity=None):
    """
    The calendar period key a timestamp falls in.

    The single definition of how records are filed. Rotation uses it to decide where a record goes and
    truncation uses it to decide whether a record has been rotated yet, so the two cannot drift apart.
    """
    if granularity is None:
        from nautobot.core.utils.config import get_settings_or_config

        granularity = get_settings_or_config(
            "CHANGELOG_ARCHIVE_PERIOD", fallback=ChangelogArchivePeriodChoices.PERIOD_YEAR
        )
    if granularity == ChangelogArchivePeriodChoices.PERIOD_MONTH:
        return f"{timestamp.year}-{timestamp.month:02d}"
    if granularity == ChangelogArchivePeriodChoices.PERIOD_QUARTER:
        return f"{timestamp.year}-Q{(timestamp.month - 1) // 3 + 1}"
    return str(timestamp.year)


def period_bounds_for(period_key):
    """
    The inclusive start and exclusive end of a period key, as timezone-aware datetimes.

    Inverse of `period_key_for`, used when creating an `ArchiveSegment` and when deciding whether a period
    has ended.
    """
    from django.utils import timezone

    tz = timezone.get_current_timezone()

    def _at(year, month):
        return datetime(year, month, 1, tzinfo=tz)

    if "-Q" in period_key:
        year, quarter = period_key.split("-Q")
        year, quarter = int(year), int(quarter)
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
    """Human-readable name for a period, used as its entry in the period selector."""
    if "-Q" in period_key:
        year, quarter = period_key.split("-Q")
        return f"{year} Q{quarter}"
    if "-" in period_key:
        year, month = period_key.split("-")
        return f"{calendar.month_name[int(month)]} {year}"
    return period_key


# Mirror columns with no warm counterpart, and how to derive them. `JobResult` reads the username through
# its `user` foreign key; with the key demoted that would be unrecoverable once the User row is deleted, so
# rotation denormalizes it -- the same trade `ObjectChange.user_name` already makes.
MIRROR_DERIVED_FIELDS = {
    "extras.archivedjobresult": {
        "user_name": lambda warm: getattr(warm.user, "username", "") or "",
    },
}


def build_mirror_instance(warm_object, mirror_model, period_key):
    """
    Build an unsaved mirror instance carrying every retained field of `warm_object`.

    The primary key carries over unchanged. That is what makes rotation idempotent: a re-run inserts the
    same key, the conflict is ignored, and nothing is duplicated.

    Field correspondence is derived from the models rather than hand-written, so a field added to both
    sides needs no change here. A field present only on the mirror raises, rather than silently writing a
    default -- `MIRROR_DERIVED_FIELDS` is where a deliberate exception is declared.
    """
    # Keyed on the abstract mirror: the exceptions are a property of the shape of retained history, and
    # every period shares it.
    derived = MIRROR_DERIVED_FIELDS.get(archive_base_of(mirror_model)._meta.label_lower, {})
    values = {"id": warm_object.pk, "period_key": period_key}
    for field in mirror_model._meta.fields:
        name = field.name
        if name in ("id", "period_key"):
            continue
        if name in derived:
            values[name] = derived[name](warm_object)
        elif hasattr(warm_object, name):
            # Covers plain columns, and demoted foreign keys whose `<name>_id` attribute exists on the
            # warm model too, read as a raw id rather than a related-object fetch.
            values[name] = getattr(warm_object, name)
        else:
            raise ValueError(
                f"{mirror_model.__name__}.{name} has no counterpart on {warm_object._meta.label} and no "
                f"entry in MIRROR_DERIVED_FIELDS. Run `nautobot-server check_changelog_archive_schema`."
            )
    return mirror_model(**values)


def archive_model_for(model, period_key=None):
    """
    The retention mirror holding `model`'s history, or None if it has none.

    Without a period this is the abstract mirror, which is the right answer for anything asking about the
    shape of retained history: its fields, its filterset, its serializer. It cannot be queried.

    With a period it is the concrete class for that period's table, which is what a read wants. Retained
    history is one table per period, so the period is not a column to filter on, it is which table to read.
    """
    from nautobot.extras.registry import registry

    mirror = registry["changelog_archive_models"].get(model._meta.label_lower)
    if mirror is None or period_key is None:
        return mirror
    return period_model_for(mirror, period_key)


def archive_base_of(model):
    """
    The abstract mirror a model is, or was generated from.

    Every registry keyed on the mirror -- the database router, the archive filtersets, the table's
    read-only detection -- is asked about concrete per-period classes too, and each of them has to arrive
    at the same answer for both.
    """
    return getattr(model, "archive_base", model)


def period_schema_name(period_key):
    """
    The PostgreSQL schema holding one period, or None when periods are separated by table name instead.

    Controlled by `CHANGELOG_ARCHIVE_SCHEMA_PREFIX`, which is empty by default. Setting it puts each
    period in its own schema, so a period is removed with one `DROP SCHEMA ... CASCADE` instead of four
    `DROP TABLE`s, can be granted or revoked as a unit, and can be excluded from a backup by name.
    """
    from django.conf import settings

    prefix = getattr(settings, "CHANGELOG_ARCHIVE_SCHEMA_PREFIX", "") or ""
    if not prefix:
        return None
    return f"{prefix}_{period_key.lower().replace('-', '_')}"


def period_table_name(mirror, period_key):
    """
    Where one period of one mirror is stored.

    With no schema prefix set, the period is in the table name and everything sits in the connection's
    default schema: `extras_archivedobjectchange_2024_q3`. With a prefix, the schema carries the period
    and the table keeps its plain name: `"changelog_archive_2024_q3"."extras_archivedobjectchange"`.

    Django understands a schema-qualified `db_table` and splits it when generating index names, so the
    rest of the ORM needs to know nothing about which arrangement is in use.
    """
    schema = period_schema_name(period_key)
    if schema is None:
        return f"{mirror._meta.db_table}_{period_key.lower().replace('-', '_')}"
    return '"{}"."{}"'.format(schema, mirror._meta.db_table)


def period_model_for(mirror, period_key):
    """
    The concrete model for one period's table, generated once and cached.

    Generated rather than declared because the set of periods is data, not code: a period comes into
    existence the first time rotation has a record to file in it. Subclassing the abstract mirror carries
    its fields *and* its methods, which is what lets the detail page diff a retained record and walk its
    neighbours without knowing which period it came from.

    `managed = False` keeps these out of `makemigrations`. The tables are created by rotation when a period
    opens and dropped whole when a period is purged, which is the point of the arrangement.
    """
    cached = _PERIOD_MODELS.get((mirror, period_key))
    if cached is not None:
        return cached

    name = f"{mirror.__name__}{period_key.replace('-', '')}"
    meta = type(
        "Meta",
        (mirror.Meta,),
        {"abstract": False, "managed": False, "db_table": period_table_name(mirror, period_key)},
    )
    model = type(
        name,
        (mirror,),
        {"__module__": mirror.__module__, "Meta": meta, "archive_base": mirror, "period_key_value": period_key},
    )
    _PERIOD_MODELS[(mirror, period_key)] = model
    return model


def ensure_period_table(mirror, period_key, using=CHANGELOG_ARCHIVE):
    """
    Create this period's table if it does not exist yet, and return its model.

    Called by rotation when it first has a record to file in a period, beside the `ArchiveSegment` it
    writes there. Creating the table is the act that opens a period; the segment row records that it is
    open. Idempotent, so a re-run or a concurrent worker costs an existence check.
    """
    from django.db import connections

    model = period_model_for(mirror, period_key)
    connection = connections[using]
    schema = period_schema_name(period_key)
    if schema is not None:
        with connection.cursor() as cursor:
            # Quoted through the schema editor so a prefix from configuration cannot become SQL.
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {connection.ops.quote_name(schema)}")
    if not period_table_exists(mirror, period_key, using=using):
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(model)
            # `create_model` skips `Meta.indexes` entirely for an unmanaged model, and these are
            # unmanaged so they stay out of `makemigrations`. Without this a period read is a sequential
            # scan, which is the opposite of the point.
            for index in model._meta.indexes:
                schema_editor.add_index(model, index)
            # A field carrying `db_index` that a declared index already covers would be created twice,
            # and the two would generate the same name.
            declared = {tuple(index.fields) for index in model._meta.indexes}
            for field in model._meta.local_fields:
                if not field.db_index or field.unique or field.primary_key:
                    continue
                if (field.name,) in declared:
                    continue
                index = models.Index(fields=[field.name])
                # Named the way Django names an implicit index, which also keeps it unique per table.
                index.set_name_with_model(model)
                schema_editor.add_index(model, index)
    return model


def ensure_period(period_key, using=CHANGELOG_ARCHIVE):
    """
    Open a period by creating every covered model's table for it, and return them.

    A period is one unit, so its tables come into existence together even where a model has nothing to
    file there yet. Creating them lazily instead would mean a read of a period that happens to hold no
    records of some type hits a table that does not exist: a retained job result with no console output
    would raise rather than show an empty tab. Empty tables are cheap; a conditional on every read is not.
    """
    from nautobot.extras.registry import registry

    return {
        label: ensure_period_table(mirror, period_key, using=using)
        for label, mirror in registry["changelog_archive_models"].items()
    }


def period_table_exists(mirror, period_key, using=CHANGELOG_ARCHIVE):
    """
    Whether this period's table has been created.

    `introspection.table_names()` only sees the connection's search path, so a schema-qualified table has
    to be looked for by schema and name instead.
    """
    from django.db import connections

    connection = connections[using]
    schema = period_schema_name(period_key)
    if schema is None:
        with connection.cursor() as cursor:
            return period_table_name(mirror, period_key) in connection.introspection.table_names(cursor)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
            [schema, mirror._meta.db_table],
        )
        return cursor.fetchone() is not None


def drop_period_table(mirror, period_key, using=CHANGELOG_ARCHIVE):
    """
    Drop a whole period's table.

    This is what the arrangement buys. Removing a period is a `DROP TABLE`, which returns the space
    immediately and leaves no index entries behind, where deleting the same records row by row would
    leave the table exactly as large as it was.
    """
    from django.db import connections

    model = period_model_for(mirror, period_key)
    connection = connections[using]
    if not period_table_exists(mirror, period_key, using=using):
        return False
    with connection.schema_editor() as schema_editor:
        schema_editor.delete_model(model)
    return True


# Keyed by (abstract mirror, period key). Model classes are expensive to build and Django registers each
# one in the app registry, so building the same period twice would be both wasteful and a name collision.
_PERIOD_MODELS = {}


class ArchiveSegment(BaseModel):
    """
    One calendar period of retained history, for one record type.

    This is the registry the read surfaces enumerate to offer a period selector, and the record of how
    far rotation has gotten. Its `view` permission is the single cold-storage gate for every covered
    model, so it is deliberately a real model with a real content type rather than a settings flag.
    """

    model_label = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        db_index=True,
        help_text="Label of the warm model this period holds retained history for, e.g. `extras.objectchange`.",
    )
    period_key = models.CharField(
        max_length=CHANGELOG_ARCHIVE_MAX_PERIOD_KEY,
        db_index=True,
        help_text="Calendar period this segment covers, e.g. `2024`, `2024-Q3`, or `2024-07`.",
    )
    label = models.CharField(
        max_length=CHARFIELD_MAX_LENGTH,
        help_text="Human-readable name for this period, used as the period selector entry.",
    )
    period_granularity = models.CharField(
        max_length=16,
        choices=ChangelogArchivePeriodChoices,
        default=ChangelogArchivePeriodChoices.PERIOD_YEAR,
        help_text="Granularity in effect when this period was created. Existing periods keep their "
        "granularity when the setting changes.",
    )
    time_start = models.DateTimeField(help_text="Inclusive start of the period.")
    time_end = models.DateTimeField(help_text="Exclusive end of the period.")
    row_count = models.PositiveBigIntegerField(
        default=0,
        help_text="Records rotated into this period. Verified by the reconciliation job.",
    )
    last_rotated_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the most recent record rotated into this period. Surfaced beside the "
        "period selector so a reader can see how far behind live activity it is.",
    )
    is_period_closed = models.BooleanField(
        default=False,
        help_text="The period has ended and rotation has caught up, so no further records will be filed "
        "here and the period carries no staleness claim.",
    )

    documentation_static_path = "docs/user-guide/platform-functionality/change-logging.html"
    natural_key_field_names = ["model_label", "period_key"]
    is_metadata_associable_model = False
    is_data_compliance_model = False
    is_version_controlled = False
    hide_in_diff_view = True

    class Meta:
        ordering = ["model_label", "-period_key"]
        unique_together = [["model_label", "period_key"]]
        verbose_name = "archive segment"
        verbose_name_plural = "archive segments"

    def clean(self):
        """
        A period must cover a span of time.

        `time_start` is inclusive and `time_end` exclusive, so an end at or before the start describes a
        period no record can fall into. Rotation would file records against it and every reconciliation
        check would then report them as outside their own period, which reads as data corruption instead
        of as the bad segment it is.
        """
        super().clean()
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

    Subclasses mirror their warm counterpart field for field. `id` carries over from the warm record
    unchanged, so a retained record keeps its original primary key and rotation can be re-run without
    creating duplicates.
    """

    # Deliberately not a ForeignKey to `ArchiveSegment`. The registry lives on `default` while the mirrors
    # live on the archive alias, so a real FK would be a cross-database constraint the moment an operator
    # repoints that alias at its own host -- and it would contradict the rule the rest of this module
    # follows, that a retained record holds its references as bare columns. `ArchiveSegment` is found by
    # (`model_label`, `period_key`); every read, count, and period purge keys off `period_key` alone.
    period_key = models.CharField(
        max_length=CHANGELOG_ARCHIVE_MAX_PERIOD_KEY,
        db_index=True,
        help_text="Calendar period this record is filed under, matching `ArchiveSegment.period_key`.",
    )

    is_metadata_associable_model = False
    is_data_compliance_model = False
    is_version_controlled = False
    # `ArchivedJobResult` mirrors a model that carries `_custom_field_data`, which is how the feature
    # registry recognizes a custom field model. Left registered, the custom field content type picker
    # offers retained job results, and the orphaned key sweep streams every retained row over the archive
    # database and then writes to the ones it finds keys on. Retained history is immutable.
    is_custom_field_model = False
    hide_in_diff_view = True
    natural_key_field_names = ["id"]

    def __getattr__(self, name):
        """
        Resolve a demoted relation to None rather than raising.

        A mirror keeps `job_result_id` but has no `job_result`, and plenty of code -- serializers, tables,
        templates -- reaches for the relation by name. Returning None for exactly those names keeps that
        code working and reads honestly: the relation is not available here, only the identifier is.

        Deliberately narrow. Only names whose `<name>_id` is a real field on this model resolve; anything
        else raises as usual, so a genuine typo is still an error.
        """
        if not name.startswith("_") and not name.endswith("_id"):
            try:
                self._meta.get_field(f"{name}_id")
            except Exception:  # noqa: S110  # FieldDoesNotExist, plus anything during model setup
                pass
            else:
                return None
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    # Warm models whose detail view also serves their retained records. The URL is the warm one on
    # purpose: a retained record keeps its primary key, so a link made before rotation still works after.
    # Absent means the record has no page, and `get_absolute_url` returns None so a linkified column
    # renders plain text instead of failing.
    DETAIL_ROUTES = {
        "extras.archivedobjectchange": "extras:objectchange",
        "extras.archivedjobresult": "extras:jobresult",
    }

    def get_absolute_url(self, api=False):
        """
        The record's read-only detail page, or None where it has none.

        Returning None rather than raising is what lets a table linkify a column and render plain text for
        the mirrors that have no page, instead of failing the whole row.
        """
        from django.urls import NoReverseMatch, reverse

        # Keyed on the abstract mirror: the route belongs to the kind of record, not to the period it was
        # filed in, and a retained record opens at the URL it had before rotation.
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


class ArchivedObjectChange(ObjectChangeSnapshotsMixin, ArchivedRecord):
    """Retained mirror of `extras.ObjectChange`."""

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

        `user` and `permission` are accepted to match `ObjectChange.get_related_changes` -- the detail view
        and `ObjectChangeSnapshotsMixin` both pass them -- and ignored, because a mirror carries no
        per-object permissions to restrict against. Reaching retained history at all requires
        `extras.view_archivesegment`, checked before any of this runs.

        Scoped to `period_key`, like every other read of retained history: a query resolves against one
        period or none. The neighbour a diff needs is normally in the same period, since a record's
        timestamp picks its period and consecutive changes are usually close together. Where an object's
        history straddles a period boundary the neighbour is in the adjacent period and is not found, which
        `get_snapshots` already handles -- it is the same case as a warm record whose predecessor has been
        deleted, and it yields the change's own data with no diff rather than an error.
        """
        # `type(self)` is this period's own table, which is the scoping the docstring describes: one
        # period or none, with no period filter needed because the table is the period.
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

        Demoting a foreign key to an identifier column is about not depending on the *record* referenced;
        a content type is schema metadata rather than a changelog record, it is what the table's "Type"
        column and the API's content-type field read by name, and `ContentType.objects.get_for_id` is
        cached per process. None where the content type has been removed -- an app uninstalled since the
        record was written -- which is the case `ChangelogArchiveIntegrityCheck` reports.
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


class ArchivedJobResult(ArchivedRecord, CustomFieldModel):
    """Retained mirror of `extras.JobResult`."""

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
    # page calls. The raw JSON carries over on rotation, so no custom field value is lost.

    @property
    def job_description(self):
        """
        Empty: the warm property reads it through the `job_model` relation, which is demoted here.

        Defined rather than left to `__getattr__` because there is no `job_description_id` field to key
        off, and the warm detail view reads it directly.
        """
        return None

    @property
    def duration(self):
        """Same as the warm property: derived from the stored timestamps, which the mirror keeps."""
        if not self.date_done or not self.date_started:
            return None
        minutes, seconds = divmod((self.date_done - self.date_started).total_seconds(), 60)
        return f"{int(minutes)} minutes, {seconds:.2f} seconds"

    @property
    def files(self):
        """
        Empty: job output files are not archived.

        Rotation holds back any result carrying files unless the operator opts in, precisely because those
        files are deleted with the warm record rather than moved.
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

        The warm model reaches these through a reverse foreign key, which the mirrors do not have. Matching
        on the stored identifier gives the same answer for records that were rotated together, which is the
        normal case: rotation moves children before parents.
        """

        # This result's own period: a run's log and console entries are filed under the same
        # period the result is, because they share its timestamp.
        return period_model_for(ArchivedJobLogEntry, self.period_key).objects.filter(job_result_id=self.pk)

    @property
    def job_console_entries(self):
        """This result's retained console output. See `job_log_entries`."""

        # This result's own period: a run's log and console entries are filed under the same
        # period the result is, because they share its timestamp.
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

        That fallback resolves a live `JobQueue`, which is exactly the kind of reference retention does not
        keep; the stored value is used when present and nothing is inferred otherwise.
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


class ArchivedJobLogEntry(ArchivedRecord):
    """Retained mirror of `extras.JobLogEntry`."""

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


class ArchivedJobConsoleEntry(ArchivedRecord):
    """Retained mirror of `extras.JobConsoleEntry`."""

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
