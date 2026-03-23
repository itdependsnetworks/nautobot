"""Shared test data for IPRange tests."""

from django.contrib.contenttypes.models import ContentType
from django.db import DEFAULT_DB_ALIAS

from nautobot.extras.models import Role, Status
from nautobot.ipam.models import IPRange, Namespace, Prefix
from nautobot.tenancy.models import Tenant, TenantGroup


def generate_iprange_test_data(db=DEFAULT_DB_ALIAS):
    """Generate test data for IPRange tests."""
    objects = {}

    objects["namespace"], _ = Namespace.objects.using(db).get_or_create(name="IPRange Test Namespace")

    pfx_status, _ = Status.objects.using(db).get_or_create(name="Active")
    pfx_status.content_types.add(ContentType.objects.db_manager(db).get_for_model(Prefix))

    objects["parent"], _ = Prefix.objects.using(db).get_or_create(
        prefix="10.100.0.0/16",
        namespace=objects["namespace"],
        defaults={"status": pfx_status},
    )

    objects["ip_status"] = Status.objects.using(db).get_for_model(IPRange).first()
    objects["ip_role"] = Role.objects.using(db).get_for_model(IPRange).first()

    objects["tenant_group1"], _ = TenantGroup.objects.using(db).get_or_create(name="IPRange Test Tenant Group 1")
    objects["tenant_group2"], _ = TenantGroup.objects.using(db).get_or_create(name="IPRange Test Tenant Group 2")
    objects["tenant1"], _ = Tenant.objects.using(db).get_or_create(
        name="IPRange Test Tenant 1",
        defaults={"tenant_group": objects["tenant_group1"]},
    )
    objects["tenant2"], _ = Tenant.objects.using(db).get_or_create(
        name="IPRange Test Tenant 2",
        defaults={"tenant_group": objects["tenant_group2"]},
    )

    # Create 3 IPRange instances for the generic delete/list/filter tests.
    # Non-overlapping ranges, using different tenant/flag combinations to
    # ensure filter tests have distinguishable rows to select from.
    objects["ip_ranges"] = (
        IPRange.objects.using(db).create(
            start_address="10.100.0.1",
            end_address="10.100.0.10",
            parent=objects["parent"],
            status=objects["ip_status"],
            tenant=objects["tenant1"],
            description="First test range",
            count_as_utilized=False,
            is_exclusive=False,
        ),
        IPRange.objects.using(db).create(
            start_address="10.100.0.20",
            end_address="10.100.0.30",
            parent=objects["parent"],
            status=objects["ip_status"],
            tenant=objects["tenant2"],
            description="Second test range",
            count_as_utilized=True,
            is_exclusive=False,
        ),
        IPRange.objects.using(db).create(
            start_address="10.100.0.40",
            end_address="10.100.0.50",
            parent=objects["parent"],
            status=objects["ip_status"],
            tenant=None,
            description="Third test range",
            count_as_utilized=False,
            is_exclusive=False,
        ),
    )

    return objects


class IPRangeTestDataMixin:
    """Shared test data mixin for IPRange tests."""

    # Declared for static analysis (pylint/mypy); populated at runtime by setUpTestData.
    namespace: Namespace
    parent: Prefix
    ip_status: Status
    ip_role: Role
    tenant_group1: TenantGroup
    tenant_group2: TenantGroup
    tenant1: Tenant
    tenant2: Tenant
    ip_ranges: tuple

    @classmethod
    def setUpTestData(cls):
        """Set up shared IPRange test data."""
        for key, value in generate_iprange_test_data().items():
            setattr(cls, key, value)
