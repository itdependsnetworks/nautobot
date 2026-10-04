"""Create the retained-history tables and the registry of which periods exist.

`ChangelogArchiveRouter.allow_migrate` decides which connection these are built on: the
`changelog_archive` alias when it addresses its own database, and the `default` run when it is a second
alias onto the same one, where both share a single `django_migrations` table.
"""

import uuid

import django.core.serializers.json
from django.db import migrations, models

import nautobot.core.celery.encoders
import nautobot.extras.models.change_logging


class Migration(migrations.Migration):
    dependencies = [
        ("extras", "0148_retention_rule"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArchivedJobConsoleEntry",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("period_key", models.CharField(db_index=True, max_length=16)),
                ("job_result_id", models.UUIDField(db_index=True)),
                ("timestamp", models.DateTimeField()),
                ("output_type", models.CharField(default="output", max_length=10)),
                ("text", models.TextField()),
            ],
            options={
                "verbose_name": "archived job console entry",
                "verbose_name_plural": "archived job console entries",
                "db_table": "extras_archivedjobconsoleentry_unbounded",
                "ordering": ["timestamp"],
                "get_latest_by": "timestamp",
                "abstract": False,
                "default_permissions": (),
                "indexes": [
                    models.Index(fields=["job_result_id", "timestamp"], name="extras_arch_job_res_4136fd_idx"),
                    models.Index(fields=["period_key", "timestamp"], name="extras_arch_period__6f0a34_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ArchivedJobLogEntry",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("period_key", models.CharField(db_index=True, max_length=16)),
                ("job_result_id", models.UUIDField(db_index=True)),
                ("log_level", models.CharField(db_index=True, default="info", max_length=32)),
                ("grouping", models.CharField(default="main", max_length=100)),
                ("message", models.TextField(blank=True)),
                ("created", models.DateTimeField(db_index=True)),
                ("log_object", models.CharField(blank=True, default="", max_length=200)),
                ("absolute_url", models.CharField(blank=True, default="", max_length=255)),
            ],
            options={
                "verbose_name": "archived job log entry",
                "verbose_name_plural": "archived job log entries",
                "db_table": "extras_archivedjoblogentry_unbounded",
                "ordering": ["created"],
                "get_latest_by": "created",
                "abstract": False,
                "default_permissions": (),
                "indexes": [
                    models.Index(fields=["job_result_id", "created"], name="extras_arch_job_res_d057fd_idx"),
                    models.Index(fields=["period_key", "created"], name="extras_arch_period__0ee81d_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ArchivedJobResult",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                (
                    "_custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder),
                ),
                ("period_key", models.CharField(db_index=True, max_length=16)),
                ("job_model_id", models.UUIDField(blank=True, null=True)),
                ("name", models.CharField(db_index=True, max_length=255)),
                ("task_name", models.CharField(db_index=True, max_length=255, null=True)),
                ("date_created", models.DateTimeField(db_index=True)),
                ("date_started", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("date_done", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("user_id", models.UUIDField(blank=True, null=True)),
                ("user_name", models.CharField(blank=True, default="", max_length=150)),
                ("status", models.CharField(db_index=True, default="PENDING", max_length=30)),
                (
                    "result",
                    models.JSONField(
                        blank=True,
                        editable=False,
                        encoder=nautobot.core.celery.encoders.NautobotKombuJSONEncoder,
                        null=True,
                    ),
                ),
                ("worker", models.CharField(default=None, max_length=100, null=True)),
                (
                    "task_args",
                    models.JSONField(
                        blank=True, default=list, encoder=nautobot.core.celery.encoders.NautobotKombuJSONEncoder
                    ),
                ),
                (
                    "task_kwargs",
                    models.JSONField(
                        blank=True, default=dict, encoder=nautobot.core.celery.encoders.NautobotKombuJSONEncoder
                    ),
                ),
                (
                    "celery_kwargs",
                    models.JSONField(
                        blank=True, default=dict, encoder=nautobot.core.celery.encoders.NautobotKombuJSONEncoder
                    ),
                ),
                ("traceback", models.TextField(blank=True, null=True)),
                ("meta", models.JSONField(default=None, editable=False, null=True)),
                ("scheduled_job_id", models.UUIDField(blank=True, null=True)),
                ("debug_log_count", models.PositiveIntegerField(blank=True, editable=False, null=True)),
                ("success_log_count", models.PositiveIntegerField(blank=True, editable=False, null=True)),
                ("info_log_count", models.PositiveIntegerField(blank=True, editable=False, null=True)),
                ("warning_log_count", models.PositiveIntegerField(blank=True, editable=False, null=True)),
                ("error_log_count", models.PositiveIntegerField(blank=True, editable=False, null=True)),
                ("canceled_by_id", models.UUIDField(blank=True, null=True)),
                ("canceled_by_user_name", models.CharField(blank=True, editable=False, max_length=150)),
                ("cancel_type", models.CharField(blank=True, max_length=30)),
                ("date_canceled", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "archived job result",
                "verbose_name_plural": "archived job results",
                "db_table": "extras_archivedjobresult_unbounded",
                "ordering": ["-date_created"],
                "get_latest_by": "date_created",
                "abstract": False,
                "default_permissions": (),
                "indexes": [
                    models.Index(fields=["period_key", "-date_created"], name="extras_arch_period__97be20_idx"),
                    models.Index(fields=["status", "-date_created"], name="extras_arch_status_449d92_idx"),
                    models.Index(fields=["name"], name="extras_arch_name_5ad61a_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ArchivedObjectChange",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("period_key", models.CharField(db_index=True, max_length=16)),
                ("time", models.DateTimeField(db_index=True, editable=False)),
                ("user_id", models.UUIDField(blank=True, null=True)),
                ("user_name", models.CharField(db_index=True, editable=False, max_length=150)),
                ("request_id", models.UUIDField(db_index=True, editable=False)),
                ("action", models.CharField(max_length=50)),
                ("changed_object_type_id", models.PositiveIntegerField(blank=True, null=True)),
                ("changed_object_id", models.UUIDField(db_index=True)),
                ("change_context", models.CharField(db_index=True, editable=False, max_length=50)),
                ("change_context_detail", models.CharField(blank=True, editable=False, max_length=400)),
                ("related_object_type_id", models.PositiveIntegerField(blank=True, null=True)),
                ("related_object_id", models.UUIDField(blank=True, null=True)),
                ("object_repr", models.CharField(editable=False, max_length=200)),
                (
                    "object_data",
                    models.JSONField(
                        blank=True, editable=False, encoder=django.core.serializers.json.DjangoJSONEncoder, null=True
                    ),
                ),
                (
                    "object_data_v2",
                    models.JSONField(
                        blank=True,
                        editable=False,
                        encoder=nautobot.core.celery.encoders.NautobotKombuJSONEncoder,
                        null=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "archived object change",
                "verbose_name_plural": "archived object changes",
                "db_table": "extras_archivedobjectchange_unbounded",
                "ordering": ["-time"],
                "get_latest_by": "time",
                "abstract": False,
                "default_permissions": (),
                "indexes": [
                    models.Index(fields=["period_key", "-time"], name="extras_arch_period__76d5e7_idx"),
                    models.Index(
                        fields=["changed_object_type_id", "changed_object_id"], name="extras_arch_changed_0b1d8c_idx"
                    ),
                    models.Index(
                        fields=["related_object_type_id", "related_object_id"], name="extras_arch_related_e488a0_idx"
                    ),
                    models.Index(fields=["request_id"], name="extras_arch_request_8759f1_idx"),
                    models.Index(fields=["user_name"], name="extras_arch_user_na_15cc93_idx"),
                ],
            },
            bases=(nautobot.extras.models.change_logging.ObjectChangeSnapshotsMixin, models.Model),
        ),
        migrations.CreateModel(
            name="ArchiveSegment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("model_label", models.CharField(db_index=True, max_length=255)),
                ("period_key", models.CharField(db_index=True, max_length=16)),
                ("label", models.CharField(max_length=255)),
                ("time_start", models.DateTimeField(blank=True, null=True)),
                ("time_end", models.DateTimeField(blank=True, null=True)),
                ("row_count", models.PositiveBigIntegerField(default=0)),
                ("is_period_closed", models.BooleanField(default=False)),
                ("last_rotated_time", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "archive period",
                "verbose_name_plural": "archive periods",
                "ordering": ["model_label", models.OrderBy(models.F("time_start"), descending=True, nulls_last=True)],
                "unique_together": {("model_label", "period_key")},
            },
        ),
    ]
