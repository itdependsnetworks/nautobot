"""Report retained-history tables that have fallen behind the warm models they mirror."""

from django.apps import apps
from django.core.management.base import BaseCommand


def find_schema_drift():
    """
    Compare each retention mirror against the warm model whose history it retains.

    Returns `(mirror_label, warm_label, missing_field_names)` per mirror missing a field its warm
    counterpart has. Nothing in Django's tooling treats the mirrors as tracking the warm models, so a
    field added to one side only produces a clean `makemigrations --check` and a silently partial archive.
    """
    from nautobot.extras.registry import registry

    drift = []
    for warm_label, mirror in registry["changelog_archive_models"].items():
        warm = apps.get_model(warm_label)
        mirror_fields = {field.name for field in mirror._meta.fields}
        missing = []
        for field in warm._meta.fields:
            if field.name in mirror_fields:
                continue
            # A demoted foreign key is held as `<name>_id`, which is a match, not a gap.
            if field.is_relation and f"{field.name}_id" in mirror_fields:
                continue
            missing.append(field.name)
        if missing:
            drift.append((mirror._meta.label, warm._meta.label, sorted(missing)))
    return drift


def find_table_drift():
    """
    Compare each period's table against the mirror whose columns it was created with.

    Returns `(table_name, missing_column_names)`. Periods are created at different times, so a field added
    in a later release reaches only the periods created after it. `find_schema_drift` cannot see that,
    comparing models with models. The unbounded period's table comes from a migration.
    """
    from django.db import connections

    from nautobot.core.constants import CHANGELOG_ARCHIVE
    from nautobot.extras.models.archive import period_models_for
    from nautobot.extras.registry import registry

    connection = connections[CHANGELOG_ARCHIVE]
    drift = []
    with connection.cursor() as cursor:
        existing_tables = set(connection.introspection.table_names(cursor))
        for mirror in registry["changelog_archive_models"].values():
            for period_model in period_models_for(mirror):
                table = period_model._meta.db_table
                if table not in existing_tables:
                    # A segment naming a table nobody created, or one an operator dropped. Reported by
                    # the integrity check, which knows what the records in it were; not drift.
                    continue
                columns = {column.name for column in connection.introspection.get_table_description(cursor, table)}
                missing = sorted(field.column for field in period_model._meta.fields if field.column not in columns)
                if missing:
                    drift.append((table, missing))
    return drift


class Command(BaseCommand):
    help = "Report retained-history tables that have fallen behind the warm models they mirror."

    def handle(self, *args, **options):
        drift = find_schema_drift()
        table_drift = find_table_drift()
        if not drift and not table_drift:
            self.stdout.write(
                self.style.SUCCESS(
                    "Every retention mirror matches the model it mirrors, and every period table matches its mirror."
                )
            )
            return

        for table, missing in table_drift:
            self.stdout.write(
                self.style.ERROR(f"Table {table} is missing {len(missing)} column(s) its mirror declares:")
            )
            for name in missing:
                self.stdout.write(f"    {name}")
            self.stdout.write(
                "    This period's table was created before those fields existed. Add the columns with "
                "`ALTER TABLE`, matching the mirror's definition."
            )

        for mirror_label, warm_label, missing in drift:
            self.stdout.write(
                self.style.ERROR(f"{mirror_label} is missing {len(missing)} field(s) present on {warm_label}:")
            )
            for name in missing:
                self.stdout.write(f"    {name}")

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "Records rotated while a field is missing will not carry it. Close the gap before enabling rotation."
            )
        )
