"""
Seed the built-in permission policies.

Each policy is created only if no policy with that name exists, so a later run of this migration never overwrites
a policy that an administrator edited, and never recreates one that an administrator deleted. The reverse
migration is a no-op: deleting a built-in policy could be blocked by assignments and would abort a rollback.
"""

from django.db import migrations

TENANT_PATHS = {
    ("dcim", "device"): "tenant",
    ("dcim", "interface"): "device__tenant",
    ("dcim", "rack"): "tenant",
    ("ipam", "prefix"): "tenant",
    ("ipam", "ipaddress"): "tenant",
    ("virtualization", "virtualmachine"): "tenant",
}

REFERENCE_DATA_TYPES = [
    ("dcim", "location"),
    ("dcim", "locationtype"),
    ("dcim", "manufacturer"),
    ("dcim", "devicetype"),
    ("dcim", "platform"),
    ("extras", "role"),
    ("extras", "status"),
    ("extras", "tag"),
    ("tenancy", "tenant"),
    ("tenancy", "tenantgroup"),
]


def _content_type(ContentType, app_label, model):
    return ContentType.objects.get_or_create(app_label=app_label, model=model)[0]


def _create_tenant_policy(apps, name, description, actions):
    PermissionPolicy = apps.get_model("users", "PermissionPolicy")

    _, created = PermissionPolicy.objects.get_or_create(name=name, defaults={"description": description})
    if not created:
        return
    # PLACEHOLDER: will be replaced in C04 (Policy parameter model and stack): the tenant parameter.
    # PLACEHOLDER: will be replaced in C08 (Policy rule model and stack): one rule per tenant-scoped object type.


def _create_unparameterized_policy(apps, name, description, rules):
    PermissionPolicy = apps.get_model("users", "PermissionPolicy")
    _, created = PermissionPolicy.objects.get_or_create(name=name, defaults={"description": description})
    if not created:
        return
    # PLACEHOLDER: will be replaced in C08 (Policy rule model and stack): the policy's rules.


def create_builtin_policies(apps, schema_editor):
    _create_tenant_policy(
        apps,
        name="nautobot-default-tenant-device-viewer",
        description="Read access to devices, interfaces, racks, prefixes, IP addresses and virtual machines "
        "belonging to the selected tenant(s).",
        actions=["view"],
    )
    _create_tenant_policy(
        apps,
        name="nautobot-default-tenant-device-operator",
        description="Full access to devices, interfaces, racks, prefixes, IP addresses and virtual machines "
        "belonging to the selected tenant(s).",
        actions=["view", "add", "change", "delete"],
    )
    _create_unparameterized_policy(
        apps,
        name="nautobot-default-reference-data-viewer",
        description="Read access to organizational and reference data: locations, device types, platforms, "
        "roles, statuses, tags and tenants.",
        rules=[((app_label, model), ["view"], {}) for app_label, model in REFERENCE_DATA_TYPES],
    )
    _create_unparameterized_policy(
        apps,
        name="nautobot-default-export-job-runner",
        description="Permission to run the built-in export job and to view one's own job results.",
        rules=[
            (
                ("extras", "job"),
                ["view", "run"],
                {"module_name": "nautobot.core.jobs", "job_class_name": "ExportObjectList"},
            ),
            (("extras", "jobresult"), ["view"], {"user": "$user"}),
        ],
    )


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0012_permission_policy"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("dcim", "0097_virtualdevicecontext_controller_managed_device_group"),
        ("ipam", "0058_iprange_role_data"),
        ("tenancy", "0009_update_all_charfields_max_length_to_255"),
        ("virtualization", "0030_alter_virtualmachine_local_config_context_data_owner_content_type_and_more"),
        ("extras", "0145_objectmetadata_assigned_object_type_cascade"),
    ]

    operations = [
        migrations.RunPython(create_builtin_policies, migrations.RunPython.noop),
    ]
