"""
Tests for `nautobot.extras.relationships.RelationshipAssociationLoader`.

`LegacyEquivalenceTest` is the primary guard against behavioral drift: it reimplements the definition-centric
algorithm that `get_relationships()` used before the loader existed, and asserts the loader agrees with it across
every relationship shape. When the two disagree, the loader is wrong unless a deliberate decision says otherwise.
"""

import json

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.models import Q, QuerySet
from django.test.utils import CaptureQueriesContext

from nautobot.core.testing import TestCase
from nautobot.core.utils.lookup import get_filterset_for_model
from nautobot.dcim.models import Location, LocationType, Manufacturer
from nautobot.extras.choices import (
    RelationshipSideChoices,
    RelationshipTypeChoices,
)
from nautobot.extras.models import Relationship, RelationshipAssociation, Status
from nautobot.extras.relationships import evaluated_queryset, RelationshipAssociationLoader
from nautobot.extras.tests.relationship_fixtures import build_relationship_benchmark_fixture


def legacy_get_relationships(obj, include_hidden=False, advanced_ui=None):
    """
    The pre-loader implementation of `RelationshipModel.get_relationships()`, verbatim.

    Kept here as the reference behavior for `LegacyEquivalenceTest`. Do not "improve" it; its value is being an
    unchanged copy of what shipped before.
    """
    src_relationships, dst_relationships = Relationship.objects.get_for_model(obj)
    if advanced_ui is not None:
        src_relationships = src_relationships.filter(advanced_ui=advanced_ui)
        dst_relationships = dst_relationships.filter(advanced_ui=advanced_ui)
    content_type = ContentType.objects.get_for_model(obj)

    sides = {
        RelationshipSideChoices.SIDE_SOURCE: src_relationships,
        RelationshipSideChoices.SIDE_DESTINATION: dst_relationships,
    }

    resp = {
        RelationshipSideChoices.SIDE_SOURCE: {},
        RelationshipSideChoices.SIDE_DESTINATION: {},
        RelationshipSideChoices.SIDE_PEER: {},
    }
    for side, relationships in sides.items():
        for relationship in relationships:
            if getattr(relationship, f"{side}_hidden") and not include_hidden:
                continue

            if getattr(relationship, f"{side}_filter"):
                filterset = get_filterset_for_model(obj._meta.model)
                if filterset:
                    filter_params = getattr(relationship, f"{side}_filter")
                    if not filterset(filter_params, obj._meta.model.objects.filter(id=obj.id)).qs.exists():
                        continue

            query_params = {"relationship": relationship}
            if not relationship.symmetric:
                query_params[f"{side}_id"] = obj.pk
                query_params[f"{side}_type"] = content_type
                resp[side][relationship] = RelationshipAssociation.objects.filter(**query_params)
            else:
                resp[RelationshipSideChoices.SIDE_PEER][relationship] = RelationshipAssociation.objects.filter(
                    (
                        Q(source_id=obj.pk, source_type=content_type)
                        | Q(destination_id=obj.pk, destination_type=content_type)
                    ),
                    **query_params,
                )

    return resp


def as_comparable(relationships_by_side):
    """Reduce a `get_relationships()`-shaped dict to `{side: {relationship_key: sorted association pks}}`."""
    return {
        side: {
            relationship.key: sorted(str(association.pk) for association in queryset)
            for relationship, queryset in relationships.items()
        }
        for side, relationships in relationships_by_side.items()
    }


class RelationshipLoaderTestMixin:
    """Builds the full-coverage benchmark fixture once per class."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.fixture = build_relationship_benchmark_fixture(scenario="S1", seed="loader")
        cls.location = cls.fixture.primary_object


class LegacyEquivalenceTest(RelationshipLoaderTestMixin, TestCase):
    """The loader must return exactly what the definition-centric implementation returned."""

    def test_matches_legacy_default(self):
        self.assertEqual(
            as_comparable(self.location.get_relationships()),
            as_comparable(legacy_get_relationships(self.location)),
        )

    def test_matches_legacy_include_hidden(self):
        self.assertEqual(
            as_comparable(self.location.get_relationships(include_hidden=True)),
            as_comparable(legacy_get_relationships(self.location, include_hidden=True)),
        )

    def test_matches_legacy_advanced_ui_true(self):
        self.assertEqual(
            as_comparable(self.location.get_relationships(advanced_ui=True)),
            as_comparable(legacy_get_relationships(self.location, advanced_ui=True)),
        )

    def test_matches_legacy_advanced_ui_false(self):
        self.assertEqual(
            as_comparable(self.location.get_relationships(advanced_ui=False)),
            as_comparable(legacy_get_relationships(self.location, advanced_ui=False)),
        )

    def test_matches_legacy_for_peer_objects(self):
        """Every non-primary object in the fixture must also agree, including ones with no associations."""
        for location in Location.objects.filter(location_type=self.fixture.location_type):
            with self.subTest(location=location.name):
                self.assertEqual(
                    as_comparable(location.get_relationships(include_hidden=True)),
                    as_comparable(legacy_get_relationships(location, include_hidden=True)),
                )


class LoaderQueryCountTest(RelationshipLoaderTestMixin, TestCase):
    """Query-count guarantees the loader exists to provide."""

    def test_association_retrieval_costs_two_queries(self):
        loader = RelationshipAssociationLoader.for_object(self.location)
        with CaptureQueriesContext(connection) as ctx:
            loader.load()
        association_queries = [q for q in ctx.captured_queries if "extras_relationshipassociation" in q["sql"]]
        self.assertEqual(
            len(association_queries),
            2,
            "Expected exactly one association query per endpoint side",
        )

    def test_returned_querysets_are_already_evaluated(self):
        relationships = self.location.get_relationships(include_hidden=True)
        with CaptureQueriesContext(connection) as ctx:
            for side_relationships in relationships.values():
                for queryset in side_relationships.values():
                    self.assertIsInstance(queryset, QuerySet)
                    queryset.count()
                    queryset.exists()
                    list(queryset)
                    queryset.first()
        self.assertEqual(len(ctx.captured_queries), 0, [q["sql"] for q in ctx.captured_queries])

    def test_filter_evaluation_costs_one_query_per_distinct_filter(self):
        """
        Side filters cost one query per *distinct* filter dict, not one per filtered definition.

        This is what the effort's planned "applicability-filter optimization" step was going to build; it fell out
        of the loader owning applicability, so that step closed with no further work. The fixture deliberately
        contains four filtered definitions sharing two distinct dicts, so this can tell the two apart.
        """
        distinct_dicts = {
            json.dumps(definition.source_filter or definition.destination_filter, sort_keys=True)
            for definition in self.fixture.filtered_definitions
        }
        self.assertGreater(len(self.fixture.filtered_definitions), len(distinct_dicts), "No filter dict is shared")
        self.assertGreater(len(distinct_dicts), 1, "Fixture has only one distinct filter dict")

        loader = RelationshipAssociationLoader.for_object(self.location)
        with CaptureQueriesContext(connection) as ctx:
            loader.load()

        # Filter evaluation runs the model's own FilterSet, so its queries hit the object's table.
        filter_queries = [
            q
            for q in ctx.captured_queries
            if '"dcim_location"' in q["sql"] and "extras_relationshipassociation" not in q["sql"]
        ]
        self.assertLessEqual(
            len(filter_queries),
            # One per distinct filter, plus the same-model peer fetch, which also queries this table.
            len(distinct_dicts) + 1,
            f"Expected at most one query per distinct filter dict, got {len(filter_queries)}",
        )

    def test_batch_load_costs_two_queries_for_many_objects(self):
        locations = list(Location.objects.filter(location_type=self.fixture.location_type))
        self.assertGreater(len(locations), 1)
        loader = RelationshipAssociationLoader.for_objects(locations)
        with CaptureQueriesContext(connection) as ctx:
            loader.load()
        association_queries = [q for q in ctx.captured_queries if "extras_relationshipassociation" in q["sql"]]
        self.assertEqual(len(association_queries), 2)


class LoaderContractTest(RelationshipLoaderTestMixin, TestCase):
    """Contracts that existing callers depend on."""

    def test_returned_queryset_supports_delete(self):
        """`RelationshipModelBulkEditFormMixin.save_relationships()` calls delete() on the returned value."""
        relationships = self.location.get_relationships(include_hidden=True)
        target = None
        for side_relationships in relationships.values():
            for relationship, queryset in side_relationships.items():
                if queryset.count() > 0:
                    target = (relationship, queryset)
                    break
            if target:
                break
        self.assertIsNotNone(target, "Fixture produced no non-empty association queryset")

        relationship, queryset = target
        pks = [association.pk for association in queryset]
        queryset.delete()
        self.assertFalse(RelationshipAssociation.objects.filter(pk__in=pks).exists())

    def test_every_applicable_definition_is_present_even_with_no_associations(self):
        relationships = self.location.get_relationships(include_hidden=True)
        keys = {
            relationship.key for side_relationships in relationships.values() for relationship in side_relationships
        }
        self.assertIn(self.fixture.empty_definition.key, keys)
        empty = next(
            queryset
            for side_relationships in relationships.values()
            for relationship, queryset in side_relationships.items()
            if relationship.key == self.fixture.empty_definition.key
        )
        self.assertEqual(empty.count(), 0)

    def test_hidden_definitions_are_excluded_by_default(self):
        hidden_keys = {
            definition.key
            for definition in self.fixture.definitions
            if definition.source_hidden or definition.destination_hidden
        }
        self.assertTrue(hidden_keys, "Fixture has no hidden definition")

        visible = {
            relationship.key
            for side_relationships in self.location.get_relationships().values()
            for relationship in side_relationships
        }
        with_hidden = {
            relationship.key
            for side_relationships in self.location.get_relationships(include_hidden=True).values()
            for relationship in side_relationships
        }
        self.assertFalse(hidden_keys & visible)
        self.assertTrue(hidden_keys <= with_hidden)


class LoaderShapeTest(TestCase):
    """
    Side and de-duplication behavior, on explicit minimal fixtures.

    These use hand-built relationships rather than the benchmark fixture so that each assertion has exactly one
    relationship in play and a failure points at one behavior.
    """

    @classmethod
    def setUpTestData(cls):
        cls.location_ct = ContentType.objects.get_for_model(Location)
        cls.manufacturer_ct = ContentType.objects.get_for_model(Manufacturer)
        status = Status.objects.get_for_model(Location).first()
        cls.location_type = LocationType.objects.create(name="Loader Shape LT")
        cls.locations = Location.objects.bulk_create(
            [
                Location(name=f"Loader Shape Location {index}", location_type=cls.location_type, status=status)
                for index in range(4)
            ]
        )
        cls.manufacturers = Manufacturer.objects.bulk_create(
            [Manufacturer(name=f"Loader Shape Manufacturer {index}") for index in range(2)]
        )

    def _relationship(self, *, key, type, source_ct=None, destination_ct=None, **kwargs):
        relationship = Relationship(
            label=key.replace("_", " ").title(),
            key=key,
            source_type=source_ct or self.location_ct,
            destination_type=destination_ct or self.manufacturer_ct,
            type=type,
            **kwargs,
        )
        relationship.validated_save()
        return relationship

    def test_symmetric_relationship_lands_under_peer(self):
        relationship = self._relationship(
            key="shape_symmetric",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY_SYMMETRIC,
            destination_ct=self.location_ct,
        )
        RelationshipAssociation.objects.create(
            relationship=relationship,
            source_type=self.location_ct,
            source_id=self.locations[0].pk,
            destination_type=self.location_ct,
            destination_id=self.locations[1].pk,
        )
        relationships = self.locations[0].get_relationships()
        self.assertIn(relationship, relationships[RelationshipSideChoices.SIDE_PEER])
        self.assertNotIn(relationship, relationships[RelationshipSideChoices.SIDE_SOURCE])
        self.assertNotIn(relationship, relationships[RelationshipSideChoices.SIDE_DESTINATION])

    def test_symmetric_associations_are_deduplicated_across_sides(self):
        """
        An object that is the source of one symmetric association and the destination of another must see both
        exactly once. This is the case where the two side-specific queries can overlap.
        """
        relationship = self._relationship(
            key="shape_symmetric_both",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY_SYMMETRIC,
            destination_ct=self.location_ct,
        )
        first = RelationshipAssociation.objects.create(
            relationship=relationship,
            source_type=self.location_ct,
            source_id=self.locations[0].pk,
            destination_type=self.location_ct,
            destination_id=self.locations[1].pk,
        )
        second = RelationshipAssociation.objects.create(
            relationship=relationship,
            source_type=self.location_ct,
            source_id=self.locations[2].pk,
            destination_type=self.location_ct,
            destination_id=self.locations[0].pk,
        )
        queryset = self.locations[0].get_relationships()[RelationshipSideChoices.SIDE_PEER][relationship]
        self.assertEqual(sorted(a.pk for a in queryset), sorted([first.pk, second.pk]))

    def test_same_model_asymmetric_appears_on_both_sides(self):
        relationship = self._relationship(
            key="shape_same_model",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            destination_ct=self.location_ct,
        )
        as_source = RelationshipAssociation.objects.create(
            relationship=relationship,
            source_type=self.location_ct,
            source_id=self.locations[0].pk,
            destination_type=self.location_ct,
            destination_id=self.locations[1].pk,
        )
        as_destination = RelationshipAssociation.objects.create(
            relationship=relationship,
            source_type=self.location_ct,
            source_id=self.locations[2].pk,
            destination_type=self.location_ct,
            destination_id=self.locations[0].pk,
        )
        relationships = self.locations[0].get_relationships()
        self.assertEqual(
            [a.pk for a in relationships[RelationshipSideChoices.SIDE_SOURCE][relationship]], [as_source.pk]
        )
        self.assertEqual(
            [a.pk for a in relationships[RelationshipSideChoices.SIDE_DESTINATION][relationship]],
            [as_destination.pk],
        )

    def test_side_filter_excludes_non_matching_object(self):
        relationship = self._relationship(
            key="shape_filtered",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            source_filter={"name": [self.locations[0].name]},
        )
        RelationshipAssociation.objects.create(
            relationship=relationship,
            source_type=self.location_ct,
            source_id=self.locations[1].pk,
            destination_type=self.manufacturer_ct,
            destination_id=self.manufacturers[0].pk,
        )
        self.assertIn(relationship, self.locations[0].get_relationships()[RelationshipSideChoices.SIDE_SOURCE])
        # locations[1] does not match the filter, so the definition does not apply to it - even though it has an
        # association on that relationship.
        self.assertNotIn(relationship, self.locations[1].get_relationships()[RelationshipSideChoices.SIDE_SOURCE])

    def test_advanced_ui_filtering(self):
        basic = self._relationship(key="shape_basic_ui", type=RelationshipTypeChoices.TYPE_MANY_TO_MANY)
        advanced = self._relationship(
            key="shape_advanced_ui", type=RelationshipTypeChoices.TYPE_MANY_TO_MANY, advanced_ui=True
        )
        basic_only = self.locations[0].get_relationships(advanced_ui=False)[RelationshipSideChoices.SIDE_SOURCE]
        advanced_only = self.locations[0].get_relationships(advanced_ui=True)[RelationshipSideChoices.SIDE_SOURCE]
        self.assertIn(basic, basic_only)
        self.assertNotIn(advanced, basic_only)
        self.assertIn(advanced, advanced_only)
        self.assertNotIn(basic, advanced_only)

    def test_batch_load_keeps_objects_separate(self):
        relationship = self._relationship(key="shape_batch", type=RelationshipTypeChoices.TYPE_MANY_TO_MANY)
        first = RelationshipAssociation.objects.create(
            relationship=relationship,
            source_type=self.location_ct,
            source_id=self.locations[0].pk,
            destination_type=self.manufacturer_ct,
            destination_id=self.manufacturers[0].pk,
        )
        second = RelationshipAssociation.objects.create(
            relationship=relationship,
            source_type=self.location_ct,
            source_id=self.locations[1].pk,
            destination_type=self.manufacturer_ct,
            destination_id=self.manufacturers[1].pk,
        )
        result = RelationshipAssociationLoader.for_objects(self.locations).load()
        self.assertEqual(
            [
                a.pk
                for a in result.association_sets(self.locations[0])[RelationshipSideChoices.SIDE_SOURCE][relationship]
            ],
            [first.pk],
        )
        self.assertEqual(
            [
                a.pk
                for a in result.association_sets(self.locations[1])[RelationshipSideChoices.SIDE_SOURCE][relationship]
            ],
            [second.pk],
        )
        self.assertEqual(
            list(result.association_sets(self.locations[2])[RelationshipSideChoices.SIDE_SOURCE][relationship]),
            [],
        )

    def test_loader_requires_at_least_one_object(self):
        with self.assertRaises(ValueError):
            RelationshipAssociationLoader.for_objects([])


class EvaluatedQuerysetTest(TestCase):
    """`evaluated_queryset()` must behave as a real queryset without querying."""

    @classmethod
    def setUpTestData(cls):
        cls.manufacturers = Manufacturer.objects.bulk_create(
            [Manufacturer(name=f"Evaluated QS Manufacturer {index}") for index in range(3)]
        )

    def test_reads_issue_no_queries(self):
        queryset = evaluated_queryset(Manufacturer, self.manufacturers)
        with CaptureQueriesContext(connection) as ctx:
            self.assertTrue(queryset.exists())
            self.assertEqual(queryset.count(), 3)
            self.assertEqual(len(list(queryset)), 3)
            self.assertEqual(list(queryset[:2]), self.manufacturers[:2])
            self.assertEqual(queryset.first(), self.manufacturers[0])
        self.assertEqual(len(ctx.captured_queries), 0, [q["sql"] for q in ctx.captured_queries])

    def test_empty(self):
        queryset = evaluated_queryset(Manufacturer, [])
        with CaptureQueriesContext(connection) as ctx:
            self.assertFalse(queryset.exists())
            self.assertEqual(queryset.count(), 0)
            self.assertIsNone(queryset.first())
        self.assertEqual(len(ctx.captured_queries), 0)

    def test_order_by_makes_first_free_for_unordered_model(self):
        """RelationshipAssociation has no Meta.ordering, so first() would otherwise clone and re-query."""
        queryset = evaluated_queryset(RelationshipAssociation, [], order_by="pk")
        self.assertTrue(queryset.ordered)
        with CaptureQueriesContext(connection) as ctx:
            queryset.first()
        self.assertEqual(len(ctx.captured_queries), 0)

    def test_is_a_real_queryset(self):
        queryset = evaluated_queryset(Manufacturer, self.manufacturers)
        self.assertIsInstance(queryset, QuerySet)
        self.assertIs(queryset.model, Manufacturer)
