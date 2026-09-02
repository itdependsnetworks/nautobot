"""Report retained-history tables that have fallen behind the warm models they mirror."""

from django.apps import apps
from django.core.management.base import BaseCommand

from nautobot.extras.models.archive import MIRROR_DERIVED_FIELDS


def find_schema_drift():
    """
    Compare each retention mirror against the warm model it holds history for.

    Returns a list of `(mirror_label, warm_label, missing_field_names)` for every mirror missing a field
    its warm counterpart has.

    This exists because nothing in Django's migration tooling knows the mirrors are meant to track the warm
    models. A field added to `ObjectChange` and not to `ArchivedObjectChange` produces a clean
    `makemigrations --check`, a clean migration, and a silently incomplete archive from that point on.
    """
    from nautobot.extras.registry import registry

    drift = []
    for warm_label, mirror in registry["changelog_archive_models"].items():
        warm = apps.get_model(warm_label)
        mirror_fields = {field.name for field in mirror._meta.fields}
        derived = set(MIRROR_DERIVED_FIELDS.get(mirror._meta.label_lower, {}))
        missing = []
        for field in warm._meta.fields:
            if field.name in mirror_fields or field.name in derived:
                continue
            # A demoted foreign key is held as `<name>_id`, which is a match, not a gap.
            if field.is_relation and f"{field.name}_id" in mirror_fields:
                continue
            missing.append(field.name)
        if missing:
            drift.append((mirror._meta.label, warm._meta.label, sorted(missing)))
    return drift


class Command(BaseCommand):
    help = "Report retained-history tables that have fallen behind the warm models they mirror."

    def add_arguments(self, parser):
        parser.add_argument(
            "--repair",
            action="store_true",
            help=(
                "Print the model changes needed to close the gap. The fields are not added automatically, "
                "because each one needs a migration and a deliberate choice about how it is stored."
            ),
        )

    def handle(self, *args, **options):
        drift = find_schema_drift()
        if not drift:
            self.stdout.write(self.style.SUCCESS("Every retention mirror matches the model it mirrors."))
            return

        for mirror_label, warm_label, missing in drift:
            self.stdout.write(
                self.style.ERROR(f"{mirror_label} is missing {len(missing)} field(s) present on {warm_label}:")
            )
            for name in missing:
                self.stdout.write(f"    {name}")

        if options["repair"]:
            self.stdout.write("")
            self.stdout.write(
                "To close the gap, add each field to its mirror in nautobot/extras/models/archive.py, "
                "holding any foreign key as a bare `<name>_id` column, then run `nautobot-server "
                "makemigrations extras`. Retained records already written will carry the field's default."
            )
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "Records rotated while a field is missing will not carry it. Close the gap before enabling rotation."
            )
        )
