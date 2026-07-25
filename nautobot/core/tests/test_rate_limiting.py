"""Tests for API rate limiting (nautobot.core.rate_limiting)."""


from django.test import override_settings, RequestFactory, SimpleTestCase

from nautobot.core.rate_limiting import costing, rest_cost


class CostEngineTestCase(SimpleTestCase):
    """REST cost calculator: classification and estimation, no Django stack involved."""

    factory = RequestFactory()

    def _cost(self, path):
        cost, _ = costing.cost(self.factory.get(path))
        return cost

    def _features(self, path):
        return rest_cost.classify(self.factory.get(path), costing.DEFAULT_WEIGHTS)

    @override_settings(RATE_LIMITING={"HEURISTIC_WEIGHTS": costing.FLAT_WEIGHTS})
    def test_flat_weights_charge_exactly_one(self):
        # The FLAT_WEIGHTS preset turns the budget into a plain requests-per-window limit —
        # no dedicated code path, just configuration.
        self.assertEqual(self._cost("/api/dcim/devices/?limit=1000&depth=3&name__ic=foo"), 1)
        cost, _ = costing.cost(self.factory.post("/api/dcim/devices/"))
        self.assertEqual(cost, 1)
        # Infinite divisors keep flatness even for absurd page arguments.
        self.assertEqual(self._cost("/api/dcim/devices/?limit=999999999"), 1)

    def test_rest_cost_scales_with_limit_and_filters(self):
        base = self._cost("/api/dcim/devices/")
        paged = self._cost("/api/dcim/devices/?limit=200")  # ceil(200/50) = 4 pages
        self.assertEqual(paged, base * 4)
        filtered = self._features("/api/dcim/devices/?location__name=foo")
        self.assertEqual(filtered.filter_count, 1)
        self.assertEqual(filtered.join_traversals, 1)

    def test_unindexable_lookup_surcharge(self):
        for lookup in ("name__ic", "name__icontains", "name__nre"):
            with self.subTest(lookup=lookup):
                features = self._features(f"/api/dcim/devices/?{lookup}=foo")
                self.assertEqual(features.unindexable_lookups, 1)
                self.assertEqual(features.join_traversals, 0)
        # Surcharge lands in the estimate: 1.0 base + 5.0 unindexable = 6
        self.assertEqual(self._cost("/api/dcim/devices/?name__ic=foo"), 6)

    def test_join_traversal_counting_peels_lookup_suffixes(self):
        features = self._features("/api/dcim/devices/?location__name__ic=foo")
        self.assertEqual(features.unindexable_lookups, 1)
        self.assertEqual(features.join_traversals, 1)
        # Index-friendly suffix is peeled without a surcharge
        features = self._features("/api/dcim/devices/?location__name__in=a,b")
        self.assertEqual(features.unindexable_lookups, 0)
        self.assertEqual(features.join_traversals, 1)

    def test_non_filter_params_not_counted(self):
        features = self._features("/api/dcim/devices/?limit=50&offset=100&format=json&sort=name&q=foo")
        self.assertEqual(features.filter_count, 0)

    def test_write_method_costs_more_than_read(self):
        read, _ = costing.cost(self.factory.get("/api/dcim/devices/"))
        write, _ = costing.cost(self.factory.post("/api/dcim/devices/"))
        self.assertGreater(write, read)

    def test_cost_floor_is_one(self):
        self.assertGreaterEqual(self._cost("/api/"), 1)

    @override_settings(RATE_LIMITING={"HEURISTIC_WEIGHTS": {"rest_read_base": 10.0}})
    def test_weights_overridable_from_settings(self):
        self.assertEqual(self._cost("/api/dcim/devices/"), 10)

class CardinalityCombineTestCase(SimpleTestCase):
    """The layer-9 cardinality multiplier (`costing.combine`), with and without cardinality.

    `combine` is a pure bolt-on that nothing in the request path calls yet — cardinality pricing
    may not make the final solution, and these tests prove both halves of that bet: with
    cardinality the same heuristic cost scales stepwise (capped) with table size, and without it
    (`cardinality=None`) every cost passes through unchanged. Dropping the feature deletes
    `combine` and this class; nothing else references either.

    Defaults: cardinality_divisor=100,000 (rows per multiplier step), cardinality_cap_multiplier=10.
    """

    factory = RequestFactory()

    def test_without_cardinality_heuristic_passes_through_unchanged(self):
        for heuristic in (1, 5, 491, 1276):
            with self.subTest(heuristic=heuristic):
                self.assertEqual(costing.combine(heuristic, None, costing.DEFAULT_WEIGHTS), heuristic)

    def test_small_tables_do_not_change_cost(self):
        # Under one divisor step (100,000 rows), the multiplier clamps to 1.
        for cardinality in (0, 100, 5_000, 99_999):
            with self.subTest(cardinality=cardinality):
                self.assertEqual(costing.combine(11, cardinality, costing.DEFAULT_WEIGHTS), 11)

    def test_cost_scales_stepwise_with_table_size(self):
        # Same query, same heuristic cost of 11 — only the table size differs.
        for cardinality, expected in (
            (100_000, 11),  # exactly one step: multiplier 1
            (250_000, 22),  # 2 steps
            (500_000, 55),  # 5 steps
            (900_000, 99),  # 9 steps
        ):
            with self.subTest(cardinality=cardinality):
                self.assertEqual(costing.combine(11, cardinality, costing.DEFAULT_WEIGHTS), expected)

    def test_multiplier_is_capped(self):
        # 3M rows would be a 30x multiplier; the cap bounds it to 10x so one huge table's growth
        # can't silently make every query against it unaffordable.
        self.assertEqual(costing.combine(11, 3_000_000, costing.DEFAULT_WEIGHTS), 110)

    def test_cap_and_divisor_are_operator_tunable(self):
        weights = {**costing.DEFAULT_WEIGHTS, "cardinality_cap_multiplier": 50}
        self.assertEqual(costing.combine(11, 3_000_000, weights), 330)  # 30x now allowed
        weights = {**costing.DEFAULT_WEIGHTS, "cardinality_divisor": 10_000}
        self.assertEqual(costing.combine(11, 250_000, weights), 110)  # 25 steps, capped at 10
