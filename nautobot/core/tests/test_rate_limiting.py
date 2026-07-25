"""Tests for API rate limiting (nautobot.core.rate_limiting)."""

from unittest import mock

from django.test import override_settings, RequestFactory, SimpleTestCase

from nautobot.core.rate_limiting import costing, graphql_cost, rest_cost


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

class GraphQLCostTestCase(SimpleTestCase):
    """GraphQL cost calculator: static AST analysis only."""

    factory = RequestFactory()

    def _classify(self, query):
        request = self.factory.post("/api/graphql/", data={"query": query}, content_type="application/json")
        return graphql_cost.classify(request, costing.DEFAULT_WEIGHTS)

    def test_nodes_multiply_by_page_arg_per_level(self):
        features = self._classify("query { devices(first: 10) { interfaces(first: 5) { id } } }")
        self.assertTrue(features.parse_ok)
        # 1 operation + 10 devices + 10*5 interfaces
        self.assertEqual(features.estimated_nodes, 61)
        self.assertEqual(features.max_depth, 3)
        self.assertEqual(features.field_count, 3)

    def test_default_page_assumed_without_first_arg(self):
        features = self._classify("query { devices { id } }")
        # 1 operation + graphql_default_page (50) devices
        self.assertEqual(features.estimated_nodes, 51)

    def test_estimate_scales_with_nodes_above_floor(self):
        small = graphql_cost.estimate(self._classify("query { devices(first: 1) { id } }"), costing.DEFAULT_WEIGHTS)
        large = graphql_cost.estimate(
            self._classify("query { devices(first: 5000) { interfaces(first: 100) { id } } }"),
            costing.DEFAULT_WEIGHTS,
        )
        self.assertEqual(small, costing.DEFAULT_WEIGHTS["graphql_floor"])
        self.assertGreater(large, costing.DEFAULT_WEIGHTS["graphql_floor"])

    def test_unparseable_query_costs_floor(self):
        features = self._classify("query { devices(")
        self.assertFalse(features.parse_ok)
        self.assertEqual(
            graphql_cost.estimate(features, costing.DEFAULT_WEIGHTS),
            costing.DEFAULT_WEIGHTS["graphql_floor"],
        )

    def test_graphql_unavailable_degrades_to_floor(self):
        with mock.patch.object(graphql_cost, "GRAPHQL_AVAILABLE", False):
            features = self._classify("query { devices { id } }")
        self.assertFalse(features.parse_ok)

    def test_pathologically_nested_query_degrades_to_floor(self):
        # Deep enough to exhaust Python's recursion limit in the parser or the walker. Either way
        # the request must be charged the floor — never the generic cost-1 fallback, and never a 500.
        depth = 2000
        query = "query " + "{ f " * depth + "{ id }" + " }" * depth
        features = self._classify(query)
        self.assertFalse(features.parse_ok)
        self.assertEqual(
            graphql_cost.estimate(features, costing.DEFAULT_WEIGHTS),
            costing.DEFAULT_WEIGHTS["graphql_floor"],
        )
        request = self.factory.post("/api/graphql/", data={"query": query}, content_type="application/json")
        cost, features = costing.cost(request)
        self.assertEqual(cost, costing.DEFAULT_WEIGHTS["graphql_floor"])
        self.assertFalse(features.classification_error)

    def test_get_request_query_parameter(self):
        request = self.factory.get("/api/graphql/", {"query": "query { devices(first: 2) { id } }"})
        features = graphql_cost.classify(request, costing.DEFAULT_WEIGHTS)
        self.assertTrue(features.parse_ok)
        self.assertEqual(features.estimated_nodes, 3)

    def test_engine_dispatches_graphql_path_to_graphql_calculator(self):
        request = self.factory.post(
            "/api/graphql/", data={"query": "query { devices { id } }"}, content_type="application/json"
        )
        _, features = costing.cost(request)
        self.assertEqual(features.kind, "graphql")

class GraphQLCostExplosionTestCase(SimpleTestCase):
    """Demonstrates, with exact numbers, how GraphQL cost scales as query features toggle.

    Every input is stated literally in WEIGHTS below (and pinned against the shipped defaults by
    test_weights_are_the_shipped_defaults), so each scenario's numbers can be recomputed by eye:

        nodes = 1 for the operation, then each level with a selection set multiplies its parent's
                count by its first/last/limit argument, or by graphql_default_page when absent
        cost  = ceil(max(graphql_floor, nodes / graphql_node_divisor))

    Cardinality is NEVER part of `cost` — that is what the request path charges today, and
    test_scenarios proves compute_cost() matches it exactly. The two cardinality columns show what
    layer 9 *would* charge if it were wired in, by feeding the same cost through costing.combine():
    a multiplier of one step per `cardinality_divisor` rows in the target table, capped at
    `cardinality_cap_multiplier`. So 250k rows → x2, and 3M rows → x30 capped to x10.
    """

    factory = RequestFactory()

    # The shipped v0 defaults, restated literally so the scenario arithmetic is visible here.
    WEIGHTS = {
        "graphql_default_page": 50,  # assumed fan-out when no first/last/limit argument
        "graphql_node_divisor": 100,  # cost = nodes / this
        "graphql_floor": 5.0,  # minimum charge
        "cardinality_divisor": 100_000,  # rows per multiplier step (layer 9 only)
        "cardinality_cap_multiplier": 10,  # multiplier ceiling (layer 9 only)
    }

    SCENARIOS = [
        {
            "label": "single object lookup — the AST can't prove it's to-one, so it's assumed list-like",
            "query": 'query { device(id: "abc") { name } }',
            "nodes": 51,  # 1 op + 50 (default page; `id` is not a page argument)
            "cost": 5,  # 51/100 = 0.51 → floor 5.0 wins
            "cost_at_250k_rows": 10,  # x2
            "cost_at_3m_rows": 50,  # x10 (capped)
        },
        {
            "label": "small bounded list — cheapest realistic query, floor applies",
            "query": "query { devices(first: 10) { id } }",
            "nodes": 11,  # 1 + 10
            "cost": 5,  # 0.11 → floor
            "cost_at_250k_rows": 10,
            "cost_at_3m_rows": 50,
        },
        {
            "label": "unbounded flat list — default page assumed, still under the floor",
            "query": "query { devices { id } }",
            "nodes": 51,  # 1 + 50
            "cost": 5,
            "cost_at_250k_rows": 10,
            "cost_at_3m_rows": 50,
        },
        {
            "label": "large page on a flat list — page argument drives cost linearly",
            "query": "query { devices(first: 2000) { id } }",
            "nodes": 2001,  # 1 + 2000
            "cost": 21,  # 2001/100 = 20.01
            "cost_at_250k_rows": 42,
            "cost_at_3m_rows": 210,
        },
        {
            "label": "two-level nesting — pages MULTIPLY per level",
            "query": "query { locations(first: 10) { devices(first: 100) { id } } }",
            "nodes": 1011,  # 1 + 10 + 10*100
            "cost": 11,  # 10.11
            "cost_at_250k_rows": 22,
            "cost_at_3m_rows": 110,
        },
        {
            "label": "three-level nesting — the explosion the estimator exists to price",
            "query": "query { locations(first: 10) { devices(first: 100) { interfaces(first: 48) { id } } } }",
            "nodes": 49011,  # 1 + 10 + 1,000 + 48,000
            "cost": 491,  # 490.11
            "cost_at_250k_rows": 982,
            "cost_at_3m_rows": 4910,
        },
        {
            "label": "three-level UNBOUNDED — every level assumes the default page; the priciest shape",
            "query": "query { locations { devices { interfaces { id } } } }",
            "nodes": 127551,  # 1 + 50 + 2,500 + 125,000
            "cost": 1276,  # 1,275.51
            "cost_at_250k_rows": 2552,
            "cost_at_3m_rows": 12760,
        },
        {
            "label": "sibling lists ADD, they don't multiply — breadth is far cheaper than depth",
            "query": "query { devices(first: 100) { id } locations(first: 100) { id } }",
            "nodes": 201,  # 1 + 100 + 100
            "cost": 5,  # 2.01 → floor
            "cost_at_250k_rows": 10,
            "cost_at_3m_rows": 50,
        },
        {
            "label": "nested to-one chain without page args — compounds the default page (v0 coarseness)",
            "query": "query { devices { location { name } } }",
            "nodes": 2551,  # 1 + 50 + 50*50
            "cost": 26,  # 25.51
            "cost_at_250k_rows": 52,
            "cost_at_3m_rows": 260,
        },
        {
            "label": "'last' is recognized as a page argument, same as 'first'",
            "query": "query { devices(last: 3000) { id } }",
            "nodes": 3001,  # 1 + 3000
            "cost": 31,  # 30.01
            "cost_at_250k_rows": 62,
            "cost_at_3m_rows": 310,
        },
        {
            "label": "'limit' is recognized as a page argument too",
            "query": "query { devices(limit: 3000) { id } }",
            "nodes": 3001,
            "cost": 31,
            "cost_at_250k_rows": 62,
            "cost_at_3m_rows": 310,
        },
        {
            "label": "mutations walk the same — the returned selection set is what's priced",
            "query": 'mutation { updateDevice(input: {id: "x"}) { device { name } } }',
            "nodes": 2551,  # 1 + 50 + 2,500: no page args anywhere, defaults compound
            "cost": 26,
            "cost_at_250k_rows": 52,
            "cost_at_3m_rows": 260,
        },
    ]

    def _request(self, query):
        return self.factory.post("/api/graphql/", data={"query": query}, content_type="application/json")

    def test_weights_are_the_shipped_defaults(self):
        """Pin the literal WEIGHTS above to the real shipped defaults so the table can't drift."""
        for key, value in self.WEIGHTS.items():
            self.assertEqual(costing.DEFAULT_WEIGHTS[key], value, f"shipped default for {key} changed")

    def test_scenarios(self):
        for scenario in self.SCENARIOS:
            with self.subTest(scenario=scenario["label"]):
                features = graphql_cost.classify(self._request(scenario["query"]), self.WEIGHTS)
                self.assertEqual(features.estimated_nodes, scenario["nodes"])

                # What the request path charges today — cardinality is never consulted.
                cost, _ = costing.cost(self._request(scenario["query"]))
                self.assertEqual(cost, scenario["cost"])
                self.assertEqual(costing.combine(cost, None, self.WEIGHTS), scenario["cost"])

                # What layer 9 WOULD charge if wired in, per target-table size.
                self.assertEqual(costing.combine(cost, 250_000, self.WEIGHTS), scenario["cost_at_250k_rows"])
                self.assertEqual(costing.combine(cost, 3_000_000, self.WEIGHTS), scenario["cost_at_3m_rows"])

    @override_settings(RATE_LIMITING={"HEURISTIC_WEIGHTS": {"graphql_default_page": 1}})
    def test_default_page_weight_tames_unbounded_queries(self):
        # With unpaged selections assumed to-one (page 1), the priciest shape above collapses
        # from 1,276 to the floor: 1 + 1 + 1 + 1 = 4 nodes.
        cost, features = costing.cost(self._request("query { locations { devices { interfaces { id } } } }"))
        self.assertEqual(features.estimated_nodes, 4)
        self.assertEqual(cost, 5)

    @override_settings(RATE_LIMITING={"HEURISTIC_WEIGHTS": {"graphql_node_divisor": 10}})
    def test_node_divisor_scales_all_costs(self):
        # Same 1,011-node query as the two-level scenario, priced 10x harsher: 1011/10 = 101.1.
        cost, _ = costing.cost(self._request("query { locations(first: 10) { devices(first: 100) { id } } }"))
        self.assertEqual(cost, 102)

    @override_settings(RATE_LIMITING={"HEURISTIC_WEIGHTS": {"graphql_floor": 1.0}})
    def test_floor_is_the_minimum_charge(self):
        # Lowering the floor lets genuinely tiny queries cost their true estimate: max(1, 0.11) = 1.
        cost, _ = costing.cost(self._request("query { devices(first: 10) { id } }"))
        self.assertEqual(cost, 1)

    @override_settings(RATE_LIMITING={"HEURISTIC_WEIGHTS": costing.FLAT_WEIGHTS})
    def test_flat_weights_flatten_everything_to_one(self):
        cost, _ = costing.cost(self._request("query { locations { devices { interfaces { id } } } }"))
        self.assertEqual(cost, 1)
        cost, _ = costing.cost(self._request("query { devices(limit: 999999999) { interfaces { id } } }"))
        self.assertEqual(cost, 1)

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

    def test_compute_cost_does_not_apply_cardinality_today(self):
        # Guards the bolt-on property: until layer 9 is wired in, the request path never combines.
        request = self.factory.post(
            "/api/graphql/", data={"query": "query { devices(first: 2000) { id } }"}, content_type="application/json"
        )
        cost, _ = costing.cost(request)
        self.assertEqual(cost, 21)  # pure heuristic, no multiplier applied
