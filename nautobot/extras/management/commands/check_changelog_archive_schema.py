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


class Command(BaseCommand):
    help = "Report retained-history tables that have fallen behind the warm models they mirror."

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

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "Records rotated while a field is missing will not carry it. Close the gap before enabling rotation."
            )
        )
