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

from nautobot.core.testing import create_test_user, TestCase
from nautobot.core.utils.cache import request_cache
from nautobot.core.utils.lookup import get_filterset_for_model
from nautobot.dcim.models import Location, LocationType, Manufacturer
from nautobot.extras.choices import (
    RelationshipRequiredSideChoices,
    RelationshipSideChoices,
    RelationshipTypeChoices,
)
from nautobot.extras.models import Relationship, RelationshipAssociation, Status
from nautobot.extras.relationships import evaluated_queryset, RelationshipAssociationLoader
from nautobot.extras.tests.relationship_fixtures import build_relationship_benchmark_fixture, peer_models


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


def legacy_get_relationships_with_related_objects(obj, include_hidden=False, advanced_ui=None):
    """
    The pre-loader implementation of `RelationshipModel.get_relationships_with_related_objects()`, verbatim.

    Reference behavior for `LegacyRelatedObjectEquivalenceTest`. Do not "improve" it.
    """
    src_relationships, dst_relationships = Relationship.objects.get_for_model(obj)

    if advanced_ui is not None:
        src_relationships = src_relationships.filter(advanced_ui=advanced_ui)
        dst_relationships = dst_relationships.filter(advanced_ui=advanced_ui)

    resp = {
        RelationshipSideChoices.SIDE_SOURCE: {},
        RelationshipSideChoices.SIDE_DESTINATION: {},
        RelationshipSideChoices.SIDE_PEER: {},
    }

    for side, relationships in (
        (RelationshipSideChoices.SIDE_SOURCE, src_relationships),
        (RelationshipSideChoices.SIDE_DESTINATION, dst_relationships),
    ):
        peer_side = RelationshipSideChoices.OPPOSITE[side]
        for relationship in relationships:
            if getattr(relationship, f"{side}_hidden") and not include_hidden:
                continue

            if getattr(relationship, f"{side}_filter"):
                filterset = get_filterset_for_model(obj._meta.model)
                if filterset:
                    filter_params = getattr(relationship, f"{side}_filter")
                    if not filterset(filter_params, obj._meta.model.objects.filter(id=obj.id)).qs.exists():
                        continue

            remote_ct = getattr(relationship, f"{peer_side}_type")
            remote_model = remote_ct.model_class()
            if remote_model is not None:
                if not relationship.symmetric:
                    query_params = {
                        f"{peer_side}_for_associations__relationship": relationship,
                        f"{peer_side}_for_associations__{side}_id": obj.pk,
                    }
                    resp[side][relationship] = remote_model.objects.filter(**query_params).distinct()
                    if not relationship.has_many(peer_side):
                        resp[side][relationship] = resp[side][relationship].first()
                else:
                    side_query_params = {
                        f"{peer_side}_for_associations__relationship": relationship,
                        f"{peer_side}_for_associations__{side}_id": obj.pk,
                    }
                    peer_side_query_params = {
                        f"{side}_for_associations__relationship": relationship,
                        f"{side}_for_associations__{peer_side}_id": obj.pk,
                    }
                    resp[RelationshipSideChoices.SIDE_PEER][relationship] = remote_model.objects.filter(
                        Q(**side_query_params) | Q(**peer_side_query_params)
                    ).distinct()
                    if not relationship.has_many(peer_side):
                        resp[RelationshipSideChoices.SIDE_PEER][relationship] = resp[RelationshipSideChoices.SIDE_PEER][
                            relationship
                        ].first()
            else:
                if not relationship.symmetric:
                    count = RelationshipAssociation.objects.filter(
                        relationship=relationship, **{f"{side}_id": obj.pk}
                    ).count()
                    resp[side][relationship] = f"{count} {remote_ct} object(s)"
                else:
                    count = (
                        RelationshipAssociation.objects.filter(relationship=relationship)
                        .filter(Q(source_id=obj.pk) | Q(destination_id=obj.pk))
                        .count()
                    )
                    resp[RelationshipSideChoices.SIDE_PEER][relationship] = f"{count} {remote_ct} object(s)"

    return resp


def related_objects_as_comparable(related_by_side):
    """Reduce a `get_relationships_with_related_objects()`-shaped dict to comparable primitives.

    Peer order is preserved rather than sorted, because it is user-visible: the detail panel displays the first
    three peers of a many-valued relationship.
    """
    comparable = {}
    for side, relationships in related_by_side.items():
        comparable[side] = {}
        for relationship, value in relationships.items():
            if isinstance(value, str):
                comparable[side][relationship.key] = value
            elif value is None:
                comparable[side][relationship.key] = None
            elif isinstance(value, QuerySet):
                comparable[side][relationship.key] = [str(instance.pk) for instance in value]
            else:
                comparable[side][relationship.key] = str(value.pk)
    return comparable


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


class LegacyRelatedObjectEquivalenceTest(RelationshipLoaderTestMixin, TestCase):
    """
    `get_relationships_with_related_objects()` must return exactly what the join-based implementation returned.

    This is the riskiest migration in the effort: the old code reached peers through a reverse generic join per
    definition, the new code resolves them in bulk per content type, and the two must agree on membership, on
    single-versus-many collapsing, on the uninstalled-App placeholder string, and on peer ordering.
    """

    def test_matches_legacy_default(self):
        self.assertEqual(
            related_objects_as_comparable(self.location.get_relationships_with_related_objects()),
            related_objects_as_comparable(legacy_get_relationships_with_related_objects(self.location)),
        )

    def test_matches_legacy_include_hidden(self):
        self.assertEqual(
            related_objects_as_comparable(self.location.get_relationships_with_related_objects(include_hidden=True)),
            related_objects_as_comparable(
                legacy_get_relationships_with_related_objects(self.location, include_hidden=True)
            ),
        )

    def test_matches_legacy_advanced_ui_true(self):
        self.assertEqual(
            related_objects_as_comparable(self.location.get_relationships_with_related_objects(advanced_ui=True)),
            related_objects_as_comparable(
                legacy_get_relationships_with_related_objects(self.location, advanced_ui=True)
            ),
        )

    def test_matches_legacy_advanced_ui_false(self):
        self.assertEqual(
            related_objects_as_comparable(self.location.get_relationships_with_related_objects(advanced_ui=False)),
            related_objects_as_comparable(
                legacy_get_relationships_with_related_objects(self.location, advanced_ui=False)
            ),
        )

    def test_matches_legacy_for_every_object(self):
        for location in Location.objects.filter(location_type=self.fixture.location_type):
            with self.subTest(location=location.name):
                self.assertEqual(
                    related_objects_as_comparable(location.get_relationships_with_related_objects(include_hidden=True)),
                    related_objects_as_comparable(
                        legacy_get_relationships_with_related_objects(location, include_hidden=True)
                    ),
                )

    def test_queryset_is_returned_exactly_for_many_valued_relationships(self):
        """
        A queryset comes back if and only if the far side can hold many objects.

        `KeyValueTablePanel.render_value()` branches on `isinstance(value, models.QuerySet)`, so getting this mapping
        wrong renders a single object through the queryset branch or vice versa.
        """
        related = self.location.get_relationships_with_related_objects(include_hidden=True)
        many_valued = 0
        single_valued = 0
        for side, relationships in related.items():
            for relationship, value in relationships.items():
                if isinstance(value, str):
                    # Uninstalled-App placeholder; neither shape applies.
                    continue
                # Mirrors how `related_object_sets()` picks the side it asks `has_many()` about.
                peer_side = (
                    RelationshipSideChoices.SIDE_SOURCE
                    if side == RelationshipSideChoices.SIDE_PEER
                    else RelationshipSideChoices.OPPOSITE[side]
                )
                expected_many = relationship.has_many(peer_side)
                self.assertEqual(
                    isinstance(value, QuerySet),
                    expected_many,
                    f"{relationship.key} on side {side}: has_many({peer_side}) is {expected_many} but value is "
                    f"{type(value).__name__}",
                )
                if expected_many:
                    many_valued += 1
                else:
                    single_valued += 1
        self.assertGreater(many_valued, 0, "Fixture produced no many-valued relationships")
        self.assertGreater(single_valued, 0, "Fixture produced no single-valued relationships")

    def test_peer_reads_issue_no_queries(self):
        related = self.location.get_relationships_with_related_objects(include_hidden=True)
        with CaptureQueriesContext(connection) as ctx:
            for relationships in related.values():
                for value in relationships.values():
                    if isinstance(value, QuerySet):
                        value.exists()
                        value.count()
                        list(value[:3])
        self.assertEqual(len(ctx.captured_queries), 0, [q["sql"] for q in ctx.captured_queries])


class PeerResolutionTest(RelationshipLoaderTestMixin, TestCase):
    """Bulk peer resolution: one query per distinct peer content type."""

    def _peer_table_queries(self, captured_queries):
        """Return `{db_table: query count}` for queries touching any of the benchmark fixture's peer tables."""
        counts = {}
        for model in peer_models():
            table = model._meta.db_table
            hits = [q for q in captured_queries if f'"{table}"' in q["sql"]]
            if hits:
                counts[table] = len(hits)
        return counts

    def test_one_query_per_peer_content_type(self):
        loader = RelationshipAssociationLoader.for_object(self.location)
        with CaptureQueriesContext(connection) as ctx:
            loader.load()
        per_table = self._peer_table_queries(ctx.captured_queries)
        self.assertTrue(per_table, "No peer queries were issued at all")
        for table, count in per_table.items():
            self.assertEqual(count, 1, f"Expected exactly one bulk query for {table}, got {count}")

    def test_peer_query_count_does_not_grow_with_association_count(self):
        """The whole point of bulk resolution: cost follows content types, not associations."""
        loader = RelationshipAssociationLoader.for_object(self.location)
        with CaptureQueriesContext(connection) as ctx:
            result = loader.load()
        peer_queries = sum(self._peer_table_queries(ctx.captured_queries).values())

        resolved_peers = sum(
            len(result.peers_for(self.location, relationship, side))
            for side, relationships in result.association_sets(self.location).items()
            for relationship in relationships
        )
        self.assertGreater(resolved_peers, peer_queries * 2, "Fixture is too small to demonstrate bulk resolution")

    def test_get_peer_is_free_after_loading(self):
        """Both endpoints are cached, so `RelationshipAssociation.get_peer()` must not query."""
        relationships = self.location.get_relationships(include_hidden=True)
        with CaptureQueriesContext(connection) as ctx:
            for side_relationships in relationships.values():
                for queryset in side_relationships.values():
                    for association in queryset:
                        association.get_peer(self.location)
        self.assertEqual(len(ctx.captured_queries), 0, [q["sql"] for q in ctx.captured_queries])

    def test_resolve_peers_false_skips_peer_queries(self):
        loader = RelationshipAssociationLoader.for_object(self.location, resolve_peers=False)
        with CaptureQueriesContext(connection) as ctx:
            loader.load()
        self.assertEqual(
            self._peer_table_queries(ctx.captured_queries),
            {},
            "resolve_peers=False must not query any peer table",
        )
        association_queries = [q for q in ctx.captured_queries if "extras_relationshipassociation" in q["sql"]]
        self.assertEqual(len(association_queries), 2)


class RequestScopedReuseTest(RelationshipLoaderTestMixin, TestCase):
    """
    Reuse of a load within one request scope, and the invalidation that makes it safe.

    Association data is mutable, so a cache that outlived a write would serve stale answers. These tests cover both
    halves: that reuse happens, and that a write ends it.
    """

    def test_second_load_in_request_scope_issues_no_queries(self):
        with request_cache():
            self.location.get_relationships(include_hidden=True)
            with CaptureQueriesContext(connection) as ctx:
                self.location.get_relationships(include_hidden=True)
            self.assertEqual(len(ctx.captured_queries), 0, [q["sql"] for q in ctx.captured_queries])

    def test_differing_filters_do_not_share_a_cache_entry(self):
        """
        Loads are cached per definition-filter combination, so the two detail tabs do not share one.

        A superset load that both tabs could share was tried and rejected: it made every caller outside an HTTP
        request pay for definitions it did not want, and only HTTP requests have a request scope (jobs and
        management commands do not). See perf_runs/relationships_progress.md.
        """
        with request_cache():
            self.location.get_relationships(advanced_ui=False)
            # A load asking for a different definition subset must not be served the previous one.
            with CaptureQueriesContext(connection) as ctx:
                self.location.get_relationships(advanced_ui=True)
            self.assertGreater(len(ctx.captured_queries), 0)

    def test_repeated_identical_call_is_free(self):
        """
        The pattern that reuse actually helps: one caller reading the same relationships twice in a request.

        `RelationshipModelFormMixin` does exactly this, calling `get_relationships()` in `_append_relationships()`
        and again in `clean()` with identical arguments.
        """
        with request_cache():
            self.location.get_relationships()
            with CaptureQueriesContext(connection) as ctx:
                self.location.get_relationships()
            self.assertEqual(len(ctx.captured_queries), 0, [q["sql"] for q in ctx.captured_queries])

    def test_no_reuse_outside_a_request_scope(self):
        """Outside a request scope there is no cache, so every load must go to the database."""
        self.location.get_relationships(include_hidden=True)
        with CaptureQueriesContext(connection) as ctx:
            self.location.get_relationships(include_hidden=True)
        self.assertGreater(len(ctx.captured_queries), 0)

    def test_creating_an_association_invalidates_the_cache(self):
        relationship = next(
            definition
            for definition in self.fixture.definitions
            if definition.type == RelationshipTypeChoices.TYPE_MANY_TO_MANY
            and definition.source_type_id == ContentType.objects.get_for_model(Location).pk
            and definition.destination_type.model_class() is not Location
        )
        peer_model = relationship.destination_type.model_class()
        unused_peer = (
            peer_model.objects.exclude(
                pk__in=RelationshipAssociation.objects.filter(relationship=relationship).values_list(
                    "destination_id", flat=True
                )
            )
            .order_by("pk")
            .first()
        )
        self.assertIsNotNone(unused_peer, "No unused peer available to create a new association with")

        with request_cache():
            before = self.location.get_relationships(include_hidden=True)[RelationshipSideChoices.SIDE_SOURCE][
                relationship
            ].count()

            RelationshipAssociation.objects.create(
                relationship=relationship,
                source_type=relationship.source_type,
                source_id=self.location.pk,
                destination_type=relationship.destination_type,
                destination_id=unused_peer.pk,
            )

            after = self.location.get_relationships(include_hidden=True)[RelationshipSideChoices.SIDE_SOURCE][
                relationship
            ].count()

        self.assertEqual(after, before + 1, "A newly created association was not visible; the cache went stale")

    def test_deleting_an_association_invalidates_the_cache(self):
        with request_cache():
            relationships = self.location.get_relationships(include_hidden=True)
            target = next(
                (relationship, queryset)
                for side_relationships in relationships.values()
                for relationship, queryset in side_relationships.items()
                if queryset.count() > 0
            )
            relationship, queryset = target
            side = next(
                side for side, side_relationships in relationships.items() if relationship in side_relationships
            )
            before = queryset.count()
            RelationshipAssociation.objects.filter(pk=queryset.first().pk).delete()

            after = self.location.get_relationships(include_hidden=True)[side][relationship].count()

        self.assertEqual(after, before - 1, "A deleted association was still visible; the cache went stale")

    def test_restricted_and_unrestricted_loads_do_not_share_a_cache_entry(self):
        """
        A load performed with no user must never be served to one that asked for permission filtering.

        Sharing them would expose peers that `restrict()` should have hidden, which is the failure mode the TRD
        calls out as a permission bug rather than a performance bug.
        """
        user = create_test_user("relbench_restricted")
        with request_cache():
            RelationshipAssociationLoader.for_object(self.location).load()
            # The restricted load must still hit the database rather than reusing the unrestricted result.
            with CaptureQueriesContext(connection) as ctx:
                RelationshipAssociationLoader.for_object(self.location, user=user).load()
            self.assertGreater(
                len(ctx.captured_queries),
                0,
                "A restricted load reused an unrestricted one, which would expose peers permissions should hide",
            )

    def test_resolve_peers_variants_do_not_share_a_cache_entry(self):
        with request_cache():
            RelationshipAssociationLoader.for_object(self.location, resolve_peers=False).load()
            # A peer-resolving load must not be served a result that never resolved peers.
            result = RelationshipAssociationLoader.for_object(self.location).load()
        peers = [
            peer
            for side, relationships in result.association_sets(self.location).items()
            for relationship in relationships
            for peer in result.peers_for(self.location, relationship, side)
        ]
        self.assertGreater(len(peers), 0, "Peers were not resolved; a resolve_peers=False result was reused")


class EvaluatedQuerysetCloneHazardTest(RelationshipLoaderTestMixin, TestCase):
    """
    Cloning a loaded queryset silently undoes the loader's work.

    `get_relationships()` returns querysets whose results are loaded and whose associations carry populated peer
    caches. Any clone - `.all()`, `.filter()`, `.order_by()` - discards both. A `.all()` call in
    `RelationshipModelFormMixin._append_relationships()` cost 216 queries per form render for exactly this reason;
    removing it took the same render to 14.
    """

    def test_iterating_directly_costs_nothing(self):
        queryset = self._first_non_empty_queryset()
        with CaptureQueriesContext(connection) as ctx:
            [association.get_peer(self.location) for association in queryset]
        self.assertEqual(len(ctx.captured_queries), 0, [q["sql"] for q in ctx.captured_queries])

    def test_cloning_discards_the_loaded_results(self):
        """Characterizes the hazard, so the cost of cloning is visible rather than surprising."""
        queryset = self._first_non_empty_queryset()
        with CaptureQueriesContext(connection) as ctx:
            [association.get_peer(self.location) for association in queryset.all()]
        self.assertGreater(
            len(ctx.captured_queries),
            0,
            "Cloning no longer discards the loaded results; if QuerySet.all() became cache-preserving, the warning "
            "in evaluated_queryset() and _append_relationships() can be relaxed",
        )

    def _first_non_empty_queryset(self):
        for side_relationships in self.location.get_relationships(include_hidden=True).values():
            for relationship, queryset in side_relationships.items():
                if queryset.count() > 0 and relationship.has_many(RelationshipSideChoices.SIDE_DESTINATION):
                    return queryset
        self.fail("Fixture produced no non-empty many-valued association queryset")


class FormMixinQueryCountTest(RelationshipLoaderTestMixin, TestCase):
    """The form path that the `.all()` clone used to make expensive."""

    def test_form_render_does_not_requery_per_relationship(self):
        from nautobot.dcim.forms import LocationForm

        LocationForm(instance=self.location)  # warm the definition cache
        with CaptureQueriesContext(connection) as ctx:
            LocationForm(instance=self.location)
        association_queries = [q for q in ctx.captured_queries if "extras_relationshipassociation" in q["sql"]]
        self.assertLessEqual(
            len(association_queries),
            2,
            "Form rendering issued more than one association query per endpoint side, so it is re-querying per "
            f"relationship ({len(association_queries)} association queries)",
        )


class RequiredRelationshipCacheTest(TestCase):
    """
    `get_required_for_model()` is cached like its `get_for_model_*` siblings.

    It runs on every form validation and every API create or update, so an uncached query here is paid on every
    write. It was the one definition lookup that was not cached.
    """

    @classmethod
    def setUpTestData(cls):
        cls.location_ct = ContentType.objects.get_for_model(Location)
        cls.manufacturer_ct = ContentType.objects.get_for_model(Manufacturer)
        cls.required = Relationship(
            label="Required Cache Test",
            key="required_cache_test",
            source_type=cls.location_ct,
            destination_type=cls.manufacturer_ct,
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            required_on=RelationshipRequiredSideChoices.SOURCE_SIDE_REQUIRED,
        )
        cls.required.validated_save()

    def test_repeated_lookups_hit_the_cache(self):
        Relationship.objects.get_required_for_model(Location, get_queryset=False)  # warm
        with CaptureQueriesContext(connection) as ctx:
            for _ in range(5):
                Relationship.objects.get_required_for_model(Location, get_queryset=False)
        self.assertEqual(len(ctx.captured_queries), 0, [q["sql"] for q in ctx.captured_queries])

    def test_returns_the_required_relationship(self):
        required = Relationship.objects.get_required_for_model(Location, get_queryset=False)
        self.assertIn(self.required.pk, [relationship.pk for relationship in required])

    def test_queryset_form_still_supported(self):
        queryset = Relationship.objects.get_required_for_model(Location)
        self.assertIn(self.required.pk, [relationship.pk for relationship in queryset])

    def test_saving_a_relationship_invalidates_the_cache(self):
        self.assertIn(
            self.required.pk,
            [r.pk for r in Relationship.objects.get_required_for_model(Location, get_queryset=False)],
        )
        self.required.required_on = RelationshipRequiredSideChoices.NEITHER_SIDE_REQUIRED
        self.required.validated_save()
        self.assertNotIn(
            self.required.pk,
            [r.pk for r in Relationship.objects.get_required_for_model(Location, get_queryset=False)],
            "The cache was not invalidated when required_on changed",
        )
