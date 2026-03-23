from nautobot.core.models.querysets import count_related
from nautobot.core.testing import TestCase
from nautobot.dcim.models.locations import Location
from nautobot.extras.models import Status
from nautobot.ipam.models import IPAddress, IPRange, Namespace, Prefix
from nautobot.ipam.tables import IPAddressTable, PrefixTable


class PrefixTableTestCase(TestCase):
    def _validate_sorted_queryset_same_with_table_queryset(self, queryset, table_class, field_name):
        with self.subTest(f"Assert sorting {table_class.__name__} on '{field_name}'"):
            table = table_class(queryset, order_by=field_name)
            table_queryset_data = table.data.data.values_list("pk", flat=True)
            sorted_queryset = queryset.order_by(field_name).values_list("pk", flat=True)
            self.assertEqual(list(table_queryset_data), list(sorted_queryset))

    def test_prefix_table_sort(self):
        """Assert TreeNode model table are orderable."""
        # Due to MySQL's lack of support for combining 'LIMIT' and 'ORDER BY' in a single query,
        # hence this approach.
        pk_list = Prefix.objects.all().values_list("pk", flat=True)[:20]
        pk_list = [str(pk) for pk in pk_list]
        queryset = Prefix.objects.filter(pk__in=pk_list)

        # Assets model names
        table_avail_fields = ["tenant", "vlan", "namespace"]
        for table_field_name in table_avail_fields:
            self._validate_sorted_queryset_same_with_table_queryset(queryset, PrefixTable, table_field_name)
            self._validate_sorted_queryset_same_with_table_queryset(queryset, PrefixTable, f"-{table_field_name}")

        # Assert `prefix`
        table_queryset_data = PrefixTable(queryset, order_by="prefix").data.data.values_list("pk", flat=True)
        prefix_queryset = queryset.order_by("network", "prefix_length").values_list("pk", flat=True)
        self.assertEqual(list(table_queryset_data), list(prefix_queryset))
        table_queryset_data = PrefixTable(queryset, order_by="-prefix").data.data.values_list("pk", flat=True)
        prefix_queryset = queryset.order_by("-network", "-prefix_length").values_list("pk", flat=True)
        self.assertEqual(list(table_queryset_data), list(prefix_queryset))

        # Assets `location_count`
        location_count_queryset = queryset.annotate(location_count=count_related(Location, "prefixes")).all()
        self._validate_sorted_queryset_same_with_table_queryset(location_count_queryset, PrefixTable, "location_count")
        self._validate_sorted_queryset_same_with_table_queryset(location_count_queryset, PrefixTable, "-location_count")


class IPAddressTableRenderPkTest(TestCase):
    """Tests for IPAddressTable.render_pk()."""

    @classmethod
    def setUpTestData(cls):
        cls.namespace = Namespace.objects.create(name="table_render_pk_test")
        pfx_status = Status.objects.get_for_model(Prefix).first()
        ip_range_status = Status.objects.get_for_model(IPRange).first()
        ip_status = Status.objects.get_for_model(IPAddress).first()
        cls.prefix = Prefix.objects.create(prefix="10.70.0.0/24", status=pfx_status, namespace=cls.namespace)
        cls.ip = IPAddress.objects.create(address="10.70.0.1/24", status=ip_status, namespace=cls.namespace)
        cls.ip_range = IPRange.objects.create(
            start_address="10.70.0.10",
            end_address="10.70.0.20",
            parent=cls.prefix,
            status=ip_range_status,
        )

    def _make_table(self):
        """Build an IPAddressTable with a single IPAddress row (enough to bind columns)."""
        return IPAddressTable(IPAddress.objects.filter(pk=self.ip.pk))

    def test_render_pk_for_ipaddress_is_not_empty(self):
        """render_pk for an IPAddress returns the rendered checkbox markup, not empty string."""
        table = self._make_table()
        result = table.render_pk(value=self.ip.pk, record=self.ip)
        # The real ToggleColumn renders a checkbox input; it should not be blank
        self.assertNotEqual(str(result), "")

    def test_render_pk_for_iprange_returns_empty(self):
        """render_pk for an IPRange returns an empty SafeString (no checkbox)."""
        table = self._make_table()
        result = table.render_pk(value=self.ip_range.pk, record=self.ip_range)
        self.assertEqual(str(result), "")

    def test_render_pk_for_available_tuple_returns_empty(self):
        """render_pk for an available-IP tuple returns an empty SafeString (no checkbox)."""
        table = self._make_table()
        # Available-IP rows are plain tuples (count, first_available_address_str)
        available_tuple = (5, "10.70.0.21/24")
        result = table.render_pk(value=None, record=available_tuple)
        self.assertEqual(str(result), "")
