"""
Baseline and regression measurements for Relationship retrieval performance.

These tests do two things:

1. **Characterize** today's retrieval cost. Some assertions here deliberately encode the *current*, undesirable
   behavior, notably that query count grows with the number of relationship definitions. They are marked
   PLACEHOLDER with the story that inverts them, so the improvement shows up in a diff rather than only in a
   benchmark log.
2. **Record** per-surface measurements (query count, database time, median and p95 wall time) so that each step of
   the effort can publish a before/after table. Set `NAUTOBOT_RELATIONSHIP_BENCH_OUT` to a file path to collect
   them; `nautobot.extras.tests.relationship_fixtures.format_bench_table()` renders the result as Markdown.

The large-scale scenarios (S2-S5) are skipped unless `NAUTOBOT_RELATIONSHIP_BENCH_FULL` is truthy, because
generating 10,000 associations is far too slow to belong in every CI run.
"""

import os
import unittest

from django.test import tag
from django.urls import reverse

from nautobot.core.settings_funcs import is_truthy
from nautobot.core.testing import APITestCase, AssertNoRepeatedQueries, create_test_user, TestCase
from nautobot.core.tests.test_graphql import execute_query_on_rebuilt_schema
from nautobot.dcim.forms import LocationForm
from nautobot.dcim.models import Location
from nautobot.dcim.tables import LocationTable
from nautobot.extras.choices import RelationshipTypeChoices
from nautobot.extras.models import Relationship
from nautobot.extras.tests.relationship_fixtures import (
    build_relationship_benchmark_fixture,
    RELATIONSHIP_BENCH_SCENARIOS,
    RelationshipBenchmarkMixin,
)

FULL_BENCH_ENV_VAR = "NAUTOBOT_RELATIONSHIP_BENCH_FULL"

#: One association query per endpoint side is the loader's floor; see `RelationshipAssociationLoader`.
LOADER_MAX_ASSOCIATION_QUERIES = 2

requires_full_bench = unittest.skipUnless(
    is_truthy(os.environ.get(FULL_BENCH_ENV_VAR, False)),
    f"Large-scale relationship benchmarks only run when {FULL_BENCH_ENV_VAR} is set",
)


def applicable_definition_count(model):
    """
    Count the *distinct* relationship definitions applicable to `model`.

    `get_for_model()` returns a (source, destination) pair, and a same-model definition legitimately appears in
    both halves, so the two lists cannot simply be added up.
    """
    source_relationships, destination_relationships = Relationship.objects.get_for_model(model, get_queryset=False)
    return len({definition.pk for definition in [*source_relationships, *destination_relationships]})


def evaluate_relationships(relationships_by_side):
    """
    Force full evaluation of the lazy querysets returned by `get_relationships()`.

    `get_relationships()` returns querysets, so simply calling it issues no association queries at all. Every
    caller pays for the queries at evaluation time, which is what needs measuring.
    """
    evaluated = 0
    for relationships in relationships_by_side.values():
        for queryset in relationships.values():
            evaluated += len(list(queryset))
    return evaluated


def evaluate_relationships_data(relationships_data):
    """Force evaluation of the `get_relationships_data()` output the UI templates would render."""
    evaluated = 0
    for relationships in relationships_data.values():
        for data in relationships.values():
            if data.get("has_many"):
                evaluated += data["queryset"].count()
            elif data.get("value") is not None:
                evaluated += 1
    return evaluated


def evaluate_related_objects(related_objects_by_side):
    """Force evaluation of the `get_relationships_with_related_objects()` output the detail panels render."""
    evaluated = 0
    for relationships in related_objects_by_side.values():
        for value in relationships.values():
            if isinstance(value, str):
                # Uninstalled-App placeholder string, e.g. "3 nonexistent.nosuchmodel object(s)"
                evaluated += 1
            elif hasattr(value, "count"):
                evaluated += value.count()
            elif value is not None:
                evaluated += 1
    return evaluated


class RelationshipFixtureTestMixin:
    """Shared fixture construction so each test class builds its data exactly once."""

    scenario_name = "S1"
    seed = "relbench"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.fixture = build_relationship_benchmark_fixture(scenario=cls.scenario_name, seed=cls.seed)
        cls.location = cls.fixture.primary_object


@tag("performance")
class RelationshipBenchmarkFixtureTest(RelationshipFixtureTestMixin, RelationshipBenchmarkMixin, TestCase):
    """
    Validate that the benchmark fixture actually contains every shape this effort has to measure.

    Without these checks a later "we made it fast" claim could rest on data that never exercised symmetric
    relationships, filters, or empty definitions.
    """

    def test_every_cardinality_is_represented(self):
        types_present = {definition.type for definition in self.fixture.definitions}
        for expected in (
            RelationshipTypeChoices.TYPE_ONE_TO_ONE,
            RelationshipTypeChoices.TYPE_ONE_TO_MANY,
            RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            RelationshipTypeChoices.TYPE_ONE_TO_ONE_SYMMETRIC,
            RelationshipTypeChoices.TYPE_MANY_TO_MANY_SYMMETRIC,
        ):
            self.assertIn(expected, types_present)

    def test_primary_object_is_on_both_sides(self):
        source_relationships, destination_relationships = Relationship.objects.get_for_model(Location)
        self.assertTrue(source_relationships.exists(), "No definitions have the primary model as source")
        self.assertTrue(destination_relationships.exists(), "No definitions have the primary model as destination")

    def test_no_definitions_beyond_the_fixture(self):
        """
        Every applicable definition must come from the fixture.

        Relationship definitions apply model-wide, so pre-existing definitions on `Location` would inflate every
        measurement in this module without any obvious symptom.
        """
        self.assertEqual(
            applicable_definition_count(Location),
            len(self.fixture.definitions),
            "Location has relationship definitions that the fixture did not create; measurements would not be "
            "attributable to the fixture alone",
        )

    def test_same_model_definitions_exist(self):
        same_model = [
            definition
            for definition in self.fixture.definitions
            if definition.source_type_id == definition.destination_type_id
        ]
        self.assertTrue(any(definition.symmetric for definition in same_model), "No same-model symmetric definition")
        self.assertTrue(
            any(not definition.symmetric for definition in same_model), "No same-model asymmetric definition"
        )

    def test_advanced_ui_definitions_exist(self):
        """
        The Advanced tab is a real surface, so the fixture must contain a definition that renders there.

        The fixture originally had none, which meant every detail-render measurement only ever exercised the main
        tab and the Advanced tab looked free.
        """
        self.assertTrue(
            any(definition.advanced_ui for definition in self.fixture.definitions),
            "No definition renders on the Advanced tab",
        )
        self.assertTrue(
            any(not definition.advanced_ui for definition in self.fixture.definitions),
            "No definition renders on the main tab",
        )

    def test_hidden_filtered_and_empty_definitions_exist(self):
        self.assertTrue(any(definition.source_hidden for definition in self.fixture.definitions))
        self.assertGreaterEqual(
            len(self.fixture.filtered_definitions), 3, "Expected filtered definitions on both sides plus a shared dict"
        )
        # Two definitions must share an identical filter dict, so that per-distinct-filter batching has something
        # to collapse later on.
        filters = [
            definition.source_filter or definition.destination_filter
            for definition in self.fixture.filtered_definitions
        ]
        self.assertLess(len({str(f) for f in filters}), len(filters), "No two definitions share a filter dict")
        self.assertIsNotNone(self.fixture.empty_definition)
        self.assertEqual(
            self.fixture.empty_definition.relationship_associations.count(),
            0,
            "The 'empty' definition unexpectedly has associations",
        )

    def test_symmetric_associations_exist_in_both_directions(self):
        symmetric = [definition for definition in self.fixture.definitions if definition.symmetric]
        directions = set()
        for definition in symmetric:
            for association in definition.relationship_associations.all():
                if association.source_id == self.location.pk:
                    directions.add("source")
                if association.destination_id == self.location.pk:
                    directions.add("destination")
        self.assertEqual(
            directions,
            {"source", "destination"},
            "Symmetric associations must place the primary object on both sides to exercise de-duplication",
        )

    def test_requested_association_count_is_met(self):
        scenario = RELATIONSHIP_BENCH_SCENARIOS[self.scenario_name]
        self.assertEqual(self.fixture.association_count, scenario.association_count)

    def test_requested_peer_content_type_count_is_met(self):
        scenario = RELATIONSHIP_BENCH_SCENARIOS[self.scenario_name]
        self.assertEqual(self.fixture.peer_content_type_count, scenario.peer_content_type_count)


@tag("performance")
class RelationshipBaselineTest(RelationshipFixtureTestMixin, RelationshipBenchmarkMixin, TestCase):
    """Per-surface baseline measurements at the S1 shape (20 definitions, 100 associations, 3 peer types)."""

    scenario_name = "S1"

    def test_baseline_get_relationships(self):
        measurement = self.measure(
            lambda: evaluate_relationships(self.location.get_relationships()),
            scenario=self.scenario_name,
            surface="get_relationships",
        )
        self.assertGreater(measurement["queries"], 1)

    def test_baseline_get_relationships_data(self):
        measurement = self.measure(
            lambda: evaluate_relationships_data(self.location.get_relationships_data()),
            scenario=self.scenario_name,
            surface="get_relationships_data",
        )
        self.assertGreater(measurement["queries"], 1)

    def _render_both_tabs(self):
        evaluate_related_objects(self.location.get_relationships_with_related_objects(advanced_ui=False))
        evaluate_related_objects(self.location.get_relationships_with_related_objects(advanced_ui=True))

    def test_baseline_detail_render_both_tabs(self):
        """
        Both detail tabs, with no request scope.

        Kept without a request scope so the number stays comparable to the rest of this series, which was measured
        that way. `test_detail_render_both_tabs_in_request_scope` is the figure that reflects a real request.
        """
        measurement = self.measure(
            self._render_both_tabs,
            scenario=self.scenario_name,
            surface="detail_render_both_tabs",
        )
        self.assertGreater(measurement["queries"], 1)

    def test_baseline_form_render(self):
        measurement = self.measure(
            lambda: LocationForm(instance=self.location),
            scenario=self.scenario_name,
            surface="form_render",
        )
        self.assertGreater(measurement["queries"], 1)

    def test_baseline_list_table(self):
        """
        Measure a list-view render with relationship columns visible.

        Column visibility must come from user table config, the way the UI supplies it, because that is what
        `BaseTable.__init__()` reads when deciding whether to prefetch relationship data. Making the columns
        visible after construction would measure an unprefetched table that no real request produces.
        """
        user = create_test_user("relbench_table")
        # Relationship columns are registered during table instantiation, not at class definition time, so an
        # instance is needed just to learn their names.
        relationship_columns = [
            name for name in LocationTable(Location.objects.none()).base_columns if name.startswith("cr_")
        ]
        self.assertTrue(relationship_columns, "LocationTable has no relationship columns")
        user.set_config("tables.LocationTable.columns", ["name", *relationship_columns], commit=True)

        def render_table():
            table = LocationTable(Location.objects.filter(pk=self.location.pk), user=user)
            visible = [name for name in relationship_columns if table.columns[name].visible]
            self.assertTrue(visible, "Relationship columns are not visible; the measurement would be meaningless")
            return [list(row) for row in table.rows]

        measurement = self.measure(
            render_table,
            scenario=self.scenario_name,
            surface="list_table",
            relationship_columns=len(relationship_columns),
        )
        self.assertGreater(measurement["queries"], 0)

    def test_baseline_repeated_association_queries(self):
        """
        Demonstrate the N+1 pattern itself, not just its total, using the existing repeated-query detector.

        PLACEHOLDER: characterizes current behavior; core-4 Bulk peer resolution inverts this to assert that the
        detector does *not* fire.
        """
        with self.assertRaises(AssertionError):
            with AssertNoRepeatedQueries(self, threshold=5):
                evaluate_relationships_data(self.location.get_relationships_data())


@tag("performance")
class RelationshipDefinitionSweepTest(RelationshipBenchmarkMixin, TestCase):
    """
    The bounded-growth sweep for TRD acceptance criterion 1.

    Deliberately *not* built on `RelationshipFixtureTestMixin`: definitions apply to a whole model, so a
    class-level fixture would silently add its own definitions to every measurement in this class and inflate
    the low end of the sweep. `test_sweep_is_uncontaminated` pins that down rather than trusting it.
    """

    def _measure_definition_count(self, definition_count):
        """Build a homogeneous fixture with `definition_count` definitions, measure it, then remove it again."""
        fixture = build_relationship_benchmark_fixture(
            scenario="S0",
            definition_count=definition_count,
            seed=f"sweep{definition_count}",
        )
        applicable = applicable_definition_count(Location)
        measurement = self.measure(
            lambda obj=fixture.primary_object: evaluate_relationships(obj.get_relationships()),
            scenario="S0",
            surface="get_relationships",
            definition_count=definition_count,
            applicable_definitions=applicable,
        )
        # Definitions are model-wide, so leaving them in place would contaminate the next point in the sweep.
        Relationship.objects.filter(pk__in=[definition.pk for definition in fixture.definitions]).delete()
        return measurement

    def test_sweep_is_uncontaminated(self):
        """A measurement is only meaningful if the object really has the number of definitions we think it has."""
        measurement = self._measure_definition_count(5)
        self.assertEqual(
            measurement["applicable_definitions"],
            5,
            "Extra relationship definitions exist for Location, so sweep measurements are not attributable to the "
            "fixture alone",
        )

    def test_baseline_query_count_grows_with_definition_count(self):
        """
        Characterize TRD acceptance criterion 1 in its *current*, failing state.

        Retrieval today issues one association query per relationship definition, so raising the definition count
        raises the query count one-for-one.

        PLACEHOLDER: characterizes current behavior; core-3 Object-centric loader inverts this to assert that query
        count stays flat as definition count rises.
        """
        low = self._measure_definition_count(5)
        high = self._measure_definition_count(25)

        self.assertEqual(low["queries"], 5, "Expected exactly one association query per definition at D=5")
        self.assertEqual(high["queries"], 25, "Expected exactly one association query per definition at D=25")
        self.assertGreater(
            high["queries"],
            low["queries"],
            "Query count did not grow with definition count; retrieval is no longer definition-centric",
        )


@tag("performance")
class RelationshipAPIBaselineTest(RelationshipFixtureTestMixin, RelationshipBenchmarkMixin, APITestCase):
    """
    Baseline measurements for the REST surfaces, which use `get_relationships()` via `RelationshipsDataField`.

    `relationships` is an opt-in serializer field (see `BaseModelSerializer.get_field_names()`), so every request
    here must pass `include=relationships` - without it the API does no relationship work at all and the
    measurement would be meaningless.

    Measurements use `depth=0`. That is not a shortcut: `RelationshipsDataField.to_representation()` resolves every
    peer via `association.get_peer()` regardless of depth, so `depth=0` measures the full per-association cost
    while avoiding the unrelated nested-serializer construction bug characterized in
    `test_symmetric_relationship_with_depth_raises_attribute_error`.
    """

    scenario_name = "S1"

    def _get_with_relationships(self, url):
        """Fetch `url` with relationships opted in, asserting the payload really contains them."""
        separator = "&" if "?" in url else "?"
        response = self.client.get(f"{url}{separator}include=relationships", **self.header)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        payload = body["results"][0] if "results" in body else body
        self.assertIn(
            "relationships",
            payload,
            "Response contains no relationships data, so this measurement would not reflect relationship cost",
        )
        self.assertTrue(payload["relationships"], "Relationships data is empty")
        return response

    def test_baseline_rest_retrieve(self):
        self.add_permissions("dcim.view_location")
        url = reverse("dcim-api:location-detail", kwargs={"pk": self.location.pk})
        measurement = self.measure(
            lambda: self._get_with_relationships(url),
            scenario=self.scenario_name,
            surface="rest_retrieve",
        )
        self.assertGreater(measurement["queries"], 1)

    def test_baseline_rest_list(self):
        self.add_permissions("dcim.view_location")
        url = reverse("dcim-api:location-list")
        measurement = self.measure(
            lambda: self._get_with_relationships(f"{url}?limit=10"),
            scenario=self.scenario_name,
            surface="rest_list",
        )
        self.assertGreater(measurement["queries"], 1)

    def test_symmetric_relationship_with_depth_raises_attribute_error(self):
        """
        Characterize a pre-existing bug found while building this fixture.

        `RelationshipsDataField.to_representation()` derives the peer side as
        `RelationshipSideChoices.OPPOSITE[this_side]`, which for a symmetric relationship is `"peer"`. It then
        passes that to `get_relation_info_for_nested_serializers()`, which does
        `getattr(RelationshipAssociation, "peer")` - and `RelationshipAssociation` defines `source` and
        `destination` GenericForeignKeys but no `peer`. The result is an HTTP 500 on any `depth > 0` request that
        opts in to relationships for an object having associations on a symmetric relationship.

        This is unrelated to the retrieval-performance work and is tracked separately; the assertion below exists
        so that fixing it produces a visible failure here rather than going unnoticed.
        """
        self.add_permissions("dcim.view_location")
        url = reverse("dcim-api:location-detail", kwargs={"pk": self.location.pk})
        response = self.client.get(f"{url}?depth=1&include=relationships", **self.header)
        self.assertEqual(
            response.status_code,
            500,
            "The symmetric-relationship nested serializer bug appears to be fixed - remove this characterization "
            "test and restore depth=1 in the REST baseline measurements",
        )
        self.assertIn("has no attribute 'peer'", response.content.decode())


@tag("performance")
class RelationshipGraphQLBaselineTest(RelationshipFixtureTestMixin, RelationshipBenchmarkMixin, TestCase):
    """Baseline measurement for the GraphQL surface, where cost is multiplied by the number of nodes."""

    scenario_name = "S4"

    def setUp(self):
        super().setUp()
        # A superuser keeps `restrict()` out of the measurement, so the number reflects relationship retrieval
        # rather than permission filtering.
        self.user = create_test_user("relbench_graphql")
        self.user.is_superuser = True
        self.user.save()

    def _relationship_query(self, *, limit):
        """Build a GraphQL query selecting a few relationship-derived fields across many location nodes."""
        # Only many-to-many cross-model definitions with the primary model on the source side are used, so that
        # the generated field name is simply `rel_<key>` with no side suffix.
        fields = []
        for definition in self.fixture.definitions:
            if definition.type != RelationshipTypeChoices.TYPE_MANY_TO_MANY:
                continue
            if definition.source_type_id == definition.destination_type_id:
                continue
            if definition.source_type.model_class() is not Location:
                continue
            fields.append(f"rel_{definition.key} {{ id }}")
            if len(fields) == 3:
                break
        self.assertTrue(fields, "Fixture produced no usable many-to-many definitions for the GraphQL query")
        selections = "\n".join(fields)
        return f"{{ locations(limit: {limit}) {{ id\n{selections} }} }}"

    def test_baseline_graphql_batch(self):
        query = self._relationship_query(limit=RELATIONSHIP_BENCH_SCENARIOS["S4"].object_count)

        def run():
            result = execute_query_on_rebuilt_schema(query, user=self.user)
            self.assertIsNone(result.errors)
            return result

        measurement = self.measure(
            run,
            scenario=self.scenario_name,
            surface="graphql_batch",
            # Rebuilding the schema per call dominates wall time here, so the query count is the meaningful metric.
            iterations=1,
        )
        self.assertGreater(measurement["queries"], 1)


@tag("performance")
@requires_full_bench
class RelationshipLargeScaleBaselineTest(RelationshipBenchmarkMixin, TestCase):
    """
    Baseline measurements at the remaining TRD sizes.

    Skipped unless `NAUTOBOT_RELATIONSHIP_BENCH_FULL` is set - S3 alone creates 10,000 associations.
    """

    def _measure_scenario(self, scenario_name):
        fixture = build_relationship_benchmark_fixture(scenario=scenario_name, seed=f"large{scenario_name}")
        location = fixture.primary_object
        self.measure(
            lambda: evaluate_relationships(location.get_relationships()),
            scenario=scenario_name,
            surface="get_relationships",
            iterations=1,
        )
        self.measure(
            lambda: evaluate_relationships_data(location.get_relationships_data()),
            scenario=scenario_name,
            surface="get_relationships_data",
            iterations=1,
        )
        self.measure(
            lambda: evaluate_related_objects(location.get_relationships_with_related_objects()),
            scenario=scenario_name,
            surface="detail_render_both_tabs",
            iterations=1,
        )
        return fixture

    def test_baseline_s2_many_definitions(self):
        fixture = self._measure_scenario("S2")
        self.assertEqual(len(fixture.definitions), 100)

    def test_baseline_s3_many_associations(self):
        fixture = self._measure_scenario("S3")
        self.assertEqual(fixture.association_count, 10000)


@tag("performance")
class CoverageOnlyScenarioTest(TestCase):
    """
    `COVERAGE_ONLY` keeps a scenario pinned to the coverage set as that set grows.

    S5 previously carried a literal definition count that had to be raised by hand every time a coverage definition
    was added. Forgetting dropped the scenario below the coverage floor and failed every test using it, and it made
    the commits unsafe to reorder, since the commit adding a definition and the commit raising the count had to stay
    in that order.
    """

    def test_coverage_only_yields_exactly_the_coverage_set(self):
        fixture = build_relationship_benchmark_fixture(scenario="S5", seed="covonly")
        padding = [d for d in fixture.definitions if "Bench bulk" in d.label]
        self.assertEqual(padding, [], "COVERAGE_ONLY must not generate padding definitions")
        self.assertEqual(len(fixture.definitions), len(set(d.pk for d in fixture.definitions)))

    def test_coverage_only_still_covers_every_shape(self):
        fixture = build_relationship_benchmark_fixture(scenario="S5", seed="covshapes")
        types_present = {definition.type for definition in fixture.definitions}
        for expected in (
            RelationshipTypeChoices.TYPE_ONE_TO_ONE,
            RelationshipTypeChoices.TYPE_ONE_TO_MANY,
            RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            RelationshipTypeChoices.TYPE_ONE_TO_ONE_SYMMETRIC,
            RelationshipTypeChoices.TYPE_MANY_TO_MANY_SYMMETRIC,
        ):
            self.assertIn(expected, types_present)
        self.assertTrue(any(d.advanced_ui for d in fixture.definitions))
        self.assertTrue(any(d.source_hidden for d in fixture.definitions))
        self.assertIsNotNone(fixture.empty_definition)

    def test_explicit_count_below_the_coverage_floor_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "definition_count must be at least"):
            build_relationship_benchmark_fixture(scenario="S5", definition_count=2, seed="covlow")

    def test_explicit_count_above_the_floor_adds_padding(self):
        coverage = build_relationship_benchmark_fixture(scenario="S5", seed="covbase")
        padded = build_relationship_benchmark_fixture(
            scenario="S5", definition_count=len(coverage.definitions) + 3, seed="covpad"
        )
        self.assertEqual(len(padded.definitions), len(coverage.definitions) + 3)
        self.assertEqual(len([d for d in padded.definitions if "Bench bulk" in d.label]), 3)
