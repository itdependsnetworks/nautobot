"""Test vpn Filters."""

from django.contrib.contenttypes.models import ContentType

from nautobot.apps.testing import FilterTestCases
from nautobot.extras.models import Status
from nautobot.vpn import choices, factory as vpn_factory, filters, models


class VPNProfileFilterTestCase(FilterTestCases.FilterTestCase, FilterTestCases.TenancyFilterTestCaseMixin):
    """VPNProfileFilterSet Test Case."""

    tenancy_related_name = "vpn_profiles"

    queryset = models.VPNProfile.objects.all()
    filterset = filters.VPNProfileFilterSet
    generic_filter_tests = (
        ("name",),
        ("description",),
        ("vpn_phase1_policies", "vpn_phase1_policies__id"),
        ("vpn_phase1_policies", "vpn_phase1_policies__name"),
        ("vpn_phase2_policies", "vpn_phase2_policies__id"),
        ("vpn_phase2_policies", "vpn_phase2_policies__name"),
        ("keepalive_interval",),
        ("keepalive_retries",),
        ("role",),
        ("extra_options",),
    )
    untested_filters = [
        "secrets_group",
    ]


class VPNPhase1PolicyFilterTestCase(FilterTestCases.FilterTestCase, FilterTestCases.TenancyFilterTestCaseMixin):
    """VPNPhase1PolicyFilterSet Test Case."""

    tenancy_related_name = "vpn_phase_1_policies"

    queryset = models.VPNPhase1Policy.objects.all()
    filterset = filters.VPNPhase1PolicyFilterSet
    generic_filter_tests = (
        ("name",),
        ("description",),
        ("lifetime_seconds",),
        ("lifetime_kb",),
        ("authentication_method",),
        ("vpn_profiles",),
    )
    untested_filters = [
        "ike_version",
    ]

    def test_encryption_algorithm(self):
        self.assertQuerySetEqualAndNotEmpty(
            self.filterset({"encryption_algorithm": "AES-128-CBC"}, self.queryset).qs,
            self.queryset.filter(encryption_algorithm__contains=["AES-128-CBC"]),
            ordered=False,
        )

    def test_integrity_algorithm(self):
        self.assertQuerySetEqualAndNotEmpty(
            self.filterset({"integrity_algorithm": "SHA256"}, self.queryset).qs,
            self.queryset.filter(integrity_algorithm__contains=["SHA256"]),
            ordered=False,
        )

    def test_dh_group(self):
        self.assertQuerySetEqualAndNotEmpty(
            self.filterset({"dh_group": "14"}, self.queryset).qs,
            self.queryset.filter(dh_group__contains=["14"]),
            ordered=False,
        )


class VPNPhase2PolicyFilterTestCase(FilterTestCases.FilterTestCase, FilterTestCases.TenancyFilterTestCaseMixin):
    """VPNPhase2PolicyFilterSet Test Case."""

    tenancy_related_name = "vpn_phase_2_policies"

    queryset = models.VPNPhase2Policy.objects.all()
    filterset = filters.VPNPhase2PolicyFilterSet
    generic_filter_tests = (
        ("name",),
        ("description",),
        ("lifetime",),
        ("vpn_profiles",),
    )

    def test_encryption_algorithm(self):
        self.assertQuerySetEqualAndNotEmpty(
            self.filterset({"encryption_algorithm": "AES-128-CBC"}, self.queryset).qs,
            self.queryset.filter(encryption_algorithm__contains=["AES-128-CBC"]),
            ordered=False,
        )

    def test_integrity_algorithm(self):
        self.assertQuerySetEqualAndNotEmpty(
            self.filterset({"integrity_algorithm": "SHA256"}, self.queryset).qs,
            self.queryset.filter(integrity_algorithm__contains=["SHA256"]),
            ordered=False,
        )

    def test_pfs_group(self):
        self.assertQuerySetEqualAndNotEmpty(
            self.filterset({"pfs_group": "14"}, self.queryset).qs,
            self.queryset.filter(pfs_group__contains=["14"]),
            ordered=False,
        )


class VPNFilterTestCase(FilterTestCases.FilterTestCase, FilterTestCases.TenancyFilterTestCaseMixin):
    """VPNFilterSet Test Case."""

    tenancy_related_name = "vpns"

    queryset = models.VPN.objects.all()
    filterset = filters.VPNFilterSet
    generic_filter_tests = (
        ("vpn_profile", "vpn_profile__id"),
        ("vpn_profile", "vpn_profile__name"),
        ("name",),
        ("description",),
        ("vpn_id",),
        ("service_type",),
        ("role",),
        ("status",),
        ("extra_attributes",),
    )

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        vpn_ct = ContentType.objects.get_for_model(models.VPN)
        active = Status.objects.get(name="Active")
        active.content_types.add(vpn_ct)
        if not models.VPN.objects.filter(name="VPN Filter VXLAN").exists():
            models.VPN.objects.create(
                name="VPN Filter VXLAN",
                service_type=choices.VPNServiceTypeChoices.TYPE_VXLAN,
                status=active,
                vpn_id="18001",
            )
            models.VPN.objects.create(
                name="VPN Filter VPLS",
                service_type=choices.VPNServiceTypeChoices.TYPE_VPLS,
                status=active,
                vpn_id="18002",
            )


class VPNTunnelFilterTestCase(FilterTestCases.FilterTestCase, FilterTestCases.TenancyFilterTestCaseMixin):
    """VPNTunnelFilterSet Test Case."""

    tenancy_related_name = "vpn_tunnels"

    queryset = models.VPNTunnel.objects.all()
    filterset = filters.VPNTunnelFilterSet
    generic_filter_tests = (
        ("id",),
        ("vpn_profile", "vpn_profile__id"),
        ("vpn_profile", "vpn_profile__name"),
        ("vpn", "vpn__id"),
        ("vpn", "vpn__name"),
        ("name",),
        ("description",),
        ("tunnel_id",),
        ("encapsulation",),
        ("endpoint_a",),
        ("endpoint_z",),
        ("role",),
        ("status",),
    )
    untested_filters = [
        "secrets_group",
    ]


class VPNTunnelEndpointFilterTestCase(FilterTestCases.FilterTestCase, FilterTestCases.TenancyFilterTestCaseMixin):
    """VPNTunnelEndpointFilterSet Test Case."""

    tenancy_related_name = "vpn_tunnel_endpoints"

    queryset = models.VPNTunnelEndpoint.objects.all()
    filterset = filters.VPNTunnelEndpointFilterSet
    generic_filter_tests = (
        ("device", "device__id"),
        ("device", "device__name"),
        ("source_interface", "source_interface__id"),
        ("source_interface", "source_interface__name"),
        ("source_fqdn",),
        ("endpoint_a_vpn_tunnels", "endpoint_a_vpn_tunnels__id"),
        ("endpoint_a_vpn_tunnels", "endpoint_a_vpn_tunnels__name"),
        ("endpoint_z_vpn_tunnels", "endpoint_z_vpn_tunnels__id"),
        ("endpoint_z_vpn_tunnels", "endpoint_z_vpn_tunnels__name"),
        ("name",),
        ("protected_prefixes",),
        ("role",),
        ("vpn_profile",),
    )
    untested_filters = [
        "protected_prefixes_dg",
        "source_ipaddress",
        "tunnel_interface",
    ]


class VPNTerminationFilterTestCase(FilterTestCases.FilterTestCase):
    """VPNTermination filter tests."""

    queryset = models.VPNTermination.objects.all()
    filterset = filters.VPNTerminationFilterSet
    generic_filter_tests = (
        ("vpn", "vpn__id"),
        ("vpn", "vpn__name"),
        ("vlan", "vlan__id"),
        ("interface", "interface__id"),
        ("vm_interface", "vm_interface__id"),
    )

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        active = Status.objects.get(name="Active")
        active.content_types.add(ContentType.objects.get_for_model(models.VPN))
        cls.vpns = [
            models.VPN.objects.create(
                name=f"VPN Termination Filter Test {index}",
                service_type=choices.VPNServiceTypeChoices.TYPE_VXLAN,
                status=active,
                vpn_id=f"1500{index}",
            )
            for index in range(3)
        ]
        cls.terminations = []
        for target_type in ("vlan", "interface", "vm_interface"):
            for vpn in cls.vpns:
                cls.terminations.append(vpn_factory.VPNTerminationFactory.create(vpn=vpn, target_type=target_type))

    def test_search_filter(self):
        queryset = models.VPNTermination.objects.all()
        filtered_qs = filters.VPNTerminationFilterSet({"q": self.vpns[0].name}, queryset).qs
        self.assertTrue(filtered_qs.filter(vpn=self.vpns[0]).exists())


class VPNProfilePhase1PolicyAssignmentFilterTestCase(FilterTestCases.FilterTestCase):
    """VPNProfilePhase1PolicyAssignmentFilterSet Test Case."""

    queryset = models.VPNProfilePhase1PolicyAssignment.objects.all()
    filterset = filters.VPNProfilePhase1PolicyAssignmentFilterSet
    generic_filter_tests = (
        ("vpn_profile", "vpn_profile__id"),
        ("vpn_profile", "vpn_profile__name"),
        ("vpn_phase1_policy", "vpn_phase1_policy__id"),
        ("vpn_phase1_policy", "vpn_phase1_policy__name"),
    )
    untested_filters = [
        "weight",
    ]


class VPNProfilePhase2PolicyAssignmentFilterTestCase(FilterTestCases.FilterTestCase):
    """VPNProfilePhase2PolicyAssignmentFilterSet Test Case."""

    queryset = models.VPNProfilePhase2PolicyAssignment.objects.all()
    filterset = filters.VPNProfilePhase2PolicyAssignmentFilterSet
    generic_filter_tests = (
        ("vpn_profile", "vpn_profile__id"),
        ("vpn_profile", "vpn_profile__name"),
        ("vpn_phase2_policy", "vpn_phase2_policy__id"),
        ("vpn_phase2_policy", "vpn_phase2_policy__name"),
    )
    untested_filters = [
        "weight",
    ]
