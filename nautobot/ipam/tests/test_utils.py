import netaddr

from nautobot.core.forms.utils import parse_numeric_range
from nautobot.core.testing import TestCase
from nautobot.extras.models import Status
from nautobot.ipam.choices import PrefixTypeChoices
from nautobot.ipam.models import IPAddress, IPRange, Namespace, Prefix, VLAN, VLANGroup
from nautobot.ipam.utils import add_available_ipaddresses, add_available_vlans, get_add_available_ipaddresses_callback


class AddAvailableVlansTest(TestCase):
    """Tests for add_available_vlans()."""

    def test_add_available_vlans(self):
        vlan_group = VLANGroup.objects.create(name="VLAN Group 1", range="100-105,110-112,115")
        status = Status.objects.get_for_model(VLAN).first()
        vlan_100 = {"vid": 100, "available": 2, "range": "100-101"}
        vlan_102 = VLAN.objects.create(name="VLAN 102", vid=102, vlan_group=vlan_group, status=status)
        vlan_103 = VLAN.objects.create(name="VLAN 103", vid=103, vlan_group=vlan_group, status=status)
        vlan_104 = {"vid": 104, "available": 2, "range": "104-105"}
        vlan_110 = VLAN.objects.create(name="VLAN 110", vid=110, vlan_group=vlan_group, status=status)
        vlan_111 = VLAN.objects.create(name="VLAN 111", vid=111, vlan_group=vlan_group, status=status)
        vlan_112 = {"vid": 112, "available": 1, "range": "112"}
        vlan_115 = VLAN.objects.create(name="VLAN 115", vid=115, vlan_group=vlan_group, status=status)

        self.assertEqual(
            list(add_available_vlans(vlan_group=vlan_group, vlans=vlan_group.vlans.all())),
            [vlan_100, vlan_102, vlan_103, vlan_104, vlan_110, vlan_111, vlan_112, vlan_115],
        )


class AddAvailableIPsTest(TestCase):
    """Tests for add_available_ipaddresses()."""

    def test_add_available_ipaddresses_ipv4(self):
        prefix = Prefix.objects.create(prefix="22.22.22.0/24", status=Status.objects.get_for_model(Prefix).first())
        ip_status = Status.objects.get_for_model(IPAddress).first()
        # .0 isn't available since this isn't a Pool prefix
        available_1 = (9, "22.22.22.1/24")
        ip_1 = IPAddress.objects.create(address="22.22.22.10/24", status=ip_status)
        available_2 = (10, "22.22.22.11/24")
        ip_2 = IPAddress.objects.create(address="22.22.22.21/24", status=ip_status)
        available_3 = (233, "22.22.22.22/24")
        # .255 isn't available since this isn't a Pool prefix
        self.assertEqual(
            add_available_ipaddresses(prefix=netaddr.IPNetwork(prefix.prefix), ipaddress_list=(ip_1, ip_2)),
            [available_1, ip_1, available_2, ip_2, available_3],
        )

    def test_add_available_ipaddresses_ipv6(self):
        namespace = Namespace.objects.create(name="add_available_ipv6")
        prefix = Prefix.objects.create(
            prefix="::/0", status=Status.objects.get_for_model(Prefix).first(), namespace=namespace
        )
        ip_status = Status.objects.get_for_model(IPAddress).first()
        # .0 is available in IPv6
        available_1 = (10, "::/0")
        ip_1 = IPAddress.objects.create(address="::a/0", status=ip_status, namespace=namespace)
        available_2 = (2**128 - 10 - 10 - 2, "::b/0")
        ip_2 = IPAddress.objects.create(
            address="ffff:ffff:ffff:ffff:ffff:ffff:ffff:fff5/0", status=ip_status, namespace=namespace
        )
        available_3 = (10, "ffff:ffff:ffff:ffff:ffff:ffff:ffff:fff6/0")
        self.assertEqual(
            add_available_ipaddresses(prefix=netaddr.IPNetwork(prefix.prefix), ipaddress_list=(ip_1, ip_2)),
            [available_1, ip_1, available_2, ip_2, available_3],
        )

    def test_ip_range_appears_at_start_address_and_absorbs_span(self):
        """An IPRange row appears at its start address and its span is excluded from available tuples."""
        namespace = Namespace.objects.create(name="utils_iprange_absorb")
        pfx_status = Status.objects.get_for_model(Prefix).first()
        ip_status = Status.objects.get_for_model(IPRange).first()
        prefix = Prefix.objects.create(prefix="10.50.0.0/24", status=pfx_status, namespace=namespace)
        # .0 and .255 are excluded (non-pool IPv4 /24)
        ip_range = IPRange.objects.create(
            start_address="10.50.0.10",
            end_address="10.50.0.19",  # 10 addresses
            parent=prefix,
            status=ip_status,
        )
        result = add_available_ipaddresses(
            prefix=netaddr.IPNetwork(prefix.prefix),
            ipaddress_list=[],
            ip_ranges=[ip_range],
        )
        # 9 available before range (.1-.9), then the range row, then 235 available after (.20-.254)
        self.assertEqual(result[0], (9, "10.50.0.1/24"))
        self.assertIs(result[1], ip_range)
        self.assertEqual(result[2], (235, "10.50.0.20/24"))
        self.assertEqual(len(result), 3)

    def test_ip_range_and_ip_address_in_same_prefix(self):
        """IPRange and IPAddress objects are interleaved correctly by address."""
        namespace = Namespace.objects.create(name="utils_iprange_interleave")
        pfx_status = Status.objects.get_for_model(Prefix).first()
        ip_range_status = Status.objects.get_for_model(IPRange).first()
        ip_status = Status.objects.get_for_model(IPAddress).first()
        prefix = Prefix.objects.create(prefix="10.51.0.0/24", status=pfx_status, namespace=namespace)
        ip_range = IPRange.objects.create(
            start_address="10.51.0.1",
            end_address="10.51.0.5",  # absorbs .1-.5
            parent=prefix,
            status=ip_range_status,
        )
        ip = IPAddress.objects.create(address="10.51.0.10/24", status=ip_status, namespace=namespace)
        result = add_available_ipaddresses(
            prefix=netaddr.IPNetwork(prefix.prefix),
            ipaddress_list=[ip],
            ip_ranges=[ip_range],
        )
        # range at .1, gap .6-.9 (4 available), ip at .10, gap .11-.254 (244 available)
        self.assertIs(result[0], ip_range)
        self.assertEqual(result[1], (4, "10.51.0.6/24"))
        self.assertIs(result[2], ip)
        self.assertEqual(result[3], (244, "10.51.0.11/24"))

    def test_show_available_false_omits_available_tuples(self):
        """show_available=False returns only IPAddress and IPRange rows, no gap tuples."""
        namespace = Namespace.objects.create(name="utils_show_available_false")
        pfx_status = Status.objects.get_for_model(Prefix).first()
        ip_range_status = Status.objects.get_for_model(IPRange).first()
        ip_status = Status.objects.get_for_model(IPAddress).first()
        prefix = Prefix.objects.create(prefix="10.52.0.0/24", status=pfx_status, namespace=namespace)
        ip_range = IPRange.objects.create(
            start_address="10.52.0.1",
            end_address="10.52.0.5",
            parent=prefix,
            status=ip_range_status,
        )
        ip = IPAddress.objects.create(address="10.52.0.20/24", status=ip_status, namespace=namespace)
        result = add_available_ipaddresses(
            prefix=netaddr.IPNetwork(prefix.prefix),
            ipaddress_list=[ip],
            ip_ranges=[ip_range],
            show_available=False,
        )
        self.assertEqual(len(result), 2)
        self.assertIs(result[0], ip_range)
        self.assertIs(result[1], ip)

    def test_empty_prefix_with_no_ranges_and_show_available_false(self):
        """With no IPs, no ranges, and show_available=False, returns empty list."""
        result = add_available_ipaddresses(
            prefix=netaddr.IPNetwork("10.53.0.0/24"),
            ipaddress_list=[],
            ip_ranges=[],
            show_available=False,
        )
        self.assertEqual(result, [])


class GetAddAvailableIPAddressesCallbackTest(TestCase):
    """Tests for get_add_available_ipaddresses_callback()."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = Namespace.objects.create(name="utils_callback_test")
        pfx_status = Status.objects.get_for_model(Prefix).first()
        ip_range_status = Status.objects.get_for_model(IPRange).first()
        ip_status = Status.objects.get_for_model(IPAddress).first()
        cls.prefix = Prefix.objects.create(prefix="10.60.0.0/24", status=pfx_status, namespace=cls.namespace)
        cls.ip_range = IPRange.objects.create(
            start_address="10.60.0.10",
            end_address="10.60.0.19",
            parent=cls.prefix,
            status=ip_range_status,
        )
        cls.ip = IPAddress.objects.create(address="10.60.0.30/24", status=ip_status, namespace=cls.namespace)

    def test_callback_injects_ip_ranges(self):
        """The callback from get_add_available_ipaddresses_callback injects ip_ranges into output."""
        callback = get_add_available_ipaddresses_callback(show_available=True, parent=self.prefix)
        result = callback(IPAddress.objects.filter(pk=self.ip.pk))
        # ip_range row should be present in the output
        self.assertIn(self.ip_range, result)
        self.assertIn(self.ip, result)

    def test_callback_show_available_false(self):
        """show_available=False propagates through the callback."""
        callback = get_add_available_ipaddresses_callback(show_available=False, parent=self.prefix)
        result = callback(IPAddress.objects.filter(pk=self.ip.pk))
        # No tuples in output
        self.assertFalse(any(isinstance(row, tuple) for row in result))
        self.assertIn(self.ip_range, result)
        self.assertIn(self.ip, result)

    def test_callback_pool_prefix_includes_network_broadcast(self):
        """A POOL prefix includes network and broadcast in the available range."""
        pfx_status = Status.objects.get_for_model(Prefix).first()
        pool_prefix = Prefix.objects.create(
            prefix="10.61.0.0/30",
            status=pfx_status,
            namespace=self.namespace,
            type=PrefixTypeChoices.TYPE_POOL,
        )
        callback = get_add_available_ipaddresses_callback(show_available=True, parent=pool_prefix)
        result = callback([])
        # /30 pool: 4 addresses all available → single tuple (4, "10.61.0.0/30")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 4)


class ParseNumericRangeTest(TestCase):
    """Tests for add_available_vlans()."""

    def test_parse(self):
        self.assertEqual(parse_numeric_range(input_string="5"), [5])
        self.assertEqual(parse_numeric_range(input_string="5-5"), [5])
        self.assertEqual(parse_numeric_range(input_string="5-5,5,5"), [5])
        self.assertEqual(parse_numeric_range(input_string="1-5"), [1, 2, 3, 4, 5])
        self.assertEqual(parse_numeric_range(input_string="1,2,3,4,5"), [1, 2, 3, 4, 5])
        self.assertEqual(parse_numeric_range(input_string="5,4,3,1,2"), [1, 2, 3, 4, 5])
        self.assertEqual(parse_numeric_range(input_string="1-5,10"), [1, 2, 3, 4, 5, 10])
        self.assertEqual(parse_numeric_range(input_string="1,5,10-11"), [1, 5, 10, 11])
        self.assertEqual(parse_numeric_range(input_string="10-11,1,5"), [1, 5, 10, 11])
        self.assertEqual(parse_numeric_range(input_string="a", base=16), [10])
        self.assertEqual(parse_numeric_range(input_string="a,b", base=16), [10, 11])
        self.assertEqual(parse_numeric_range(input_string="9-c,f", base=16), [9, 10, 11, 12, 15])
        self.assertEqual(parse_numeric_range(input_string="15-19", base=16), [21, 22, 23, 24, 25])
        self.assertEqual(parse_numeric_range(input_string="fa-ff", base=16), [250, 251, 252, 253, 254, 255])

    def test_invalid_input(self):
        invalid_inputs = [
            [1, 2, 3],
            None,
            1,
            "",
            "3-",
        ]

        for x in invalid_inputs:
            with self.assertRaises(TypeError) as exc:
                parse_numeric_range(input_string=x)
            self.assertEqual(str(exc.exception), "Input value must be a string using a range format.")
