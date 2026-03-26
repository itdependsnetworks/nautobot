from django.db import migrations

from nautobot.extras.management import clear_status_choices, populate_status_choices


def populate_iprange_status_choices(apps, schema_editor):
    """Create/link default Status records for the IPRange content-type."""
    populate_status_choices(apps, schema_editor, models=["ipam.IPRange"])


def clear_iprange_status_choices(apps, schema_editor):
    """De-link/delete Status records from the IPRange content-type."""
    clear_status_choices(apps, schema_editor, models=["ipam.IPRange"])


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0001_initial"),
        ("extras", "0138_job_console_log_default_and_more"),
        ("ipam", "0056_iprange"),
    ]

    operations = [
        migrations.RunPython(
            code=populate_iprange_status_choices,
            reverse_code=clear_iprange_status_choices,
        ),
    ]
