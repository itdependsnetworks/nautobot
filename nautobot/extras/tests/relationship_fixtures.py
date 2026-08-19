"""
Reusable data generation and measurement helpers for Relationship performance work.

The fixtures here exist so that every step of the "performant custom relationships" effort measures the *same*
data shapes, making per-step query counts and timings directly comparable. `build_relationship_benchmark_fixture()`
is shared by the automated benchmarks (`nautobot.extras.tests.test_relationship_performance`) and by the
`generate_relationship_test_data` management command, so hand-timed page loads and `EXPLAIN` runs against a real
database exercise exactly the same shapes as the test suite.
"""

import contextlib
from dataclasses import dataclass, field
import json
import logging
import math
import os
from statistics import median
import time

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
import redis.exceptions

from nautobot.core.utils.cache import construct_cache_key
from nautobot.extras.choices import RelationshipTypeChoices
from nautobot.extras.models import Relationship, RelationshipAssociation, Status

logger = logging.getLogger(__name__)

#: Environment variable naming the JSONL file that benchmark measurements are appended to.
BENCH_OUT_ENV_VAR = "NAUTOBOT_RELATIONSHIP_BENCH_OUT"

#: Peer models used for cross-model relationships, in a fixed order so that `peer_content_type_count` is meaningful.
#: All of these are `OrganizationalModel` subclasses whose only required field is `name`, which keeps generation of
#: tens of thousands of peer objects cheap - the point of the fixture is relationship volume, not peer complexity.
#:
#: Held as labels rather than imported classes because `nautobot.extras` must not import a domain app such as `dcim`
#: or `ipam` at module level; see the app load order in the circular-imports reference. `peer_models()` resolves them.
PEER_MODEL_LABELS = ("dcim.Manufacturer", "dcim.Platform", "circuits.CircuitType", "ipam.VLANGroup", "tenancy.Tenant")


def peer_models():
    """Resolve `PEER_MODEL_LABELS` to model classes, in the same order."""
    return tuple(apps.get_model(label) for label in PEER_MODEL_LABELS)


#: Sentinel for a scenario's `definition_count`: use exactly the behavior-coverage set, with no padding definitions.
#: Scenarios that need every relationship *shape* represented but do not care how many definitions that takes should
#: use this rather than a literal count. A literal has to be raised by hand every time a coverage definition is added,
#: and forgetting drops the scenario below the coverage floor, which fails every test using it.
COVERAGE_ONLY = -1


@dataclass(frozen=True)
class RelationshipBenchScenario:
    """One named benchmark data shape.

    Attributes:
        name (str): Short scenario id, e.g. `"S1"`.
        definition_count (int): Number of Relationship definitions applicable to the primary object's model.
        association_count (int): Number of RelationshipAssociations per primary object.
        peer_content_type_count (int): Number of distinct peer content types to spread associations across.
        object_count (int): Number of primary objects to create (>1 for batch surfaces such as GraphQL and tables).
        description (str): Why this shape exists / what failure mode it represents.
        coverage (bool): Whether to include the fixed behavior-coverage definitions (every cardinality, filters,
            hidden, empty, same-model). `False` produces homogeneous many-to-many definitions only, which is what
            a scaling sweep wants: varying definition count without also varying definition *kind*.
    """

    name: str
    definition_count: int
    association_count: int
    peer_content_type_count: int
    object_count: int
    description: str
    coverage: bool = True


RELATIONSHIP_BENCH_SCENARIOS = {
    scenario.name: scenario
    for scenario in (
        RelationshipBenchScenario(
            name="S0",
            definition_count=5,
            association_count=10,
            peer_content_type_count=2,
            object_count=1,
            description="Bounded-growth sweep; definition_count is varied 5->25 by the caller",
            # Homogeneous definitions, so the sweep isolates definition count as the only variable.
            coverage=False,
        ),
        RelationshipBenchScenario(
            name="S1",
            definition_count=20,
            association_count=100,
            peer_content_type_count=3,
            object_count=1,
            description="Baseline size: many definitions, moderate associations",
        ),
        RelationshipBenchScenario(
            name="S2",
            definition_count=100,
            association_count=1000,
            peer_content_type_count=3,
            object_count=1,
            description="Definition-count failure mode",
        ),
        RelationshipBenchScenario(
            name="S3",
            definition_count=20,
            association_count=10000,
            peer_content_type_count=5,
            object_count=1,
            description="Association-count failure mode; also exercises large IN predicates",
        ),
        RelationshipBenchScenario(
            name="S4",
            definition_count=20,
            association_count=20,
            peer_content_type_count=3,
            object_count=100,
            description="Many objects in one GraphQL query",
        ),
        RelationshipBenchScenario(
            name="S5",
            # Exactly the coverage set, so that the table render exercises symmetric and same-model columns
            # (`RelationshipColumn` treats those differently) rather than only plain many-to-many ones.
            definition_count=COVERAGE_ONLY,
            association_count=5,
            peer_content_type_count=3,
            object_count=50,
            description="List-view table render with relationship columns",
        ),
    )
}


@dataclass
class RelationshipBenchmarkFixture:
    """Everything `build_relationship_benchmark_fixture()` created, for tests and commands to assert against."""

    scenario: RelationshipBenchScenario
    location_type: object
    objects: list = field(default_factory=list)
    definitions: list = field(default_factory=list)
    peer_objects: dict = field(default_factory=dict)
    association_count: int = 0
    #: The subset of `definitions` that carry a filter on the side the primary objects are on.
    filtered_definitions: list = field(default_factory=list)
    #: The definition deliberately left with zero associations.
    empty_definition: Relationship = None

    @property
    def primary_object(self):
        """The single object that single-object surfaces (detail render, REST retrieve, form) are measured against."""
        return self.objects[0]

    @property
    def peer_content_type_count(self):
        """Number of distinct peer content types actually reachable from the primary object."""
        return len(self.peer_objects)

    def summary(self):
        """Return a dict describing the generated data, suitable for logging or command output."""
        return {
            "scenario": self.scenario.name,
            "objects": len(self.objects),
            "definitions": len(self.definitions),
            "filtered_definitions": len(self.filtered_definitions),
            "associations": self.association_count,
            "peer_content_types": self.peer_content_type_count,
            "peer_objects": sum(len(peers) for peers in self.peer_objects.values()),
        }


def clear_relationship_caches():
    """
    Drop the `Relationship.objects.get_for_model_*` caches.

    Definitions created via `validated_save()` invalidate these through
    `nautobot.extras.signals.invalidate_relationship_models_cache`, but bulk-created or externally-modified
    definitions do not, so callers that generate data outside the normal save path must clear explicitly.
    """
    for method_name in ("get_for_model_source", "get_for_model_destination"):
        with contextlib.suppress(redis.exceptions.ConnectionError):
            cache_key = construct_cache_key(Relationship.objects, method_name=method_name, branch_aware=True)
            cache.delete_pattern(f"{cache_key}(*)")


def build_relationship_benchmark_fixture(
    *,
    scenario=None,
    definition_count=None,
    association_count=None,
    peer_content_type_count=None,
    object_count=None,
    coverage=None,
    seed="relbench",
):
    """
    Create a reproducible relationship data set for benchmarking.

    Either pass `scenario` (a `RelationshipBenchScenario` or its name, e.g. `"S1"`), or pass the individual
    dimensions. Individual dimensions override the scenario's values when both are given, which is what the
    bounded-growth sweep uses to vary `definition_count` while holding everything else fixed.

    The generated data always includes, regardless of size: every supported cardinality; definitions with the
    primary model on the source side *and* on the destination side; a same-model asymmetric definition; a
    same-model symmetric definition with associations in both directions; a hidden definition; a definition
    filtered on the primary object's side; two definitions sharing an identical filter dict; and a definition
    with no associations at all.

    Args:
        scenario (Union[RelationshipBenchScenario, str]): Named shape to build.
        definition_count (int): Override the scenario's definition count.
        association_count (int): Override the scenario's per-object association count.
        peer_content_type_count (int): Override the scenario's peer content type count.
        object_count (int): Override the scenario's primary object count.
        coverage (bool): Override the scenario's `coverage` flag; see `RelationshipBenchScenario`.
        seed (str): Name prefix making generated records unique and reproducible.

    Returns:
        (RelationshipBenchmarkFixture): The created objects, definitions, and counts.
    """
    if isinstance(scenario, str):
        scenario = RELATIONSHIP_BENCH_SCENARIOS[scenario]
    if scenario is None:
        if None in (definition_count, association_count, peer_content_type_count, object_count):
            raise ValueError("Either scenario or all four individual dimensions must be specified")
        scenario = RelationshipBenchScenario(
            name="custom",
            definition_count=definition_count,
            association_count=association_count,
            peer_content_type_count=peer_content_type_count,
            object_count=object_count,
            description="Caller-specified shape",
            coverage=True if coverage is None else coverage,
        )
    else:
        scenario = RelationshipBenchScenario(
            name=scenario.name,
            definition_count=definition_count if definition_count is not None else scenario.definition_count,
            association_count=association_count if association_count is not None else scenario.association_count,
            peer_content_type_count=(
                peer_content_type_count if peer_content_type_count is not None else scenario.peer_content_type_count
            ),
            object_count=object_count if object_count is not None else scenario.object_count,
            description=scenario.description,
            coverage=scenario.coverage if coverage is None else coverage,
        )

    if not 2 <= scenario.peer_content_type_count <= len(PEER_MODEL_LABELS):
        raise ValueError(f"peer_content_type_count must be between 2 and {len(PEER_MODEL_LABELS)}")
    if scenario.object_count < 1:
        raise ValueError("object_count must be at least 1")

    available_peer_models = peer_models()

    selected_peer_models = available_peer_models[: scenario.peer_content_type_count]

    location_type, objects = _create_primary_objects(scenario, seed)
    fixture = RelationshipBenchmarkFixture(scenario=scenario, location_type=location_type, objects=objects)

    specs = _definition_specs(scenario, selected_peer_models, location_type, objects)
    fixture.definitions = _create_definitions(specs, seed)
    fixture.filtered_definitions = [
        definition for definition, spec in zip(fixture.definitions, specs) if spec.filter_params
    ]
    fixture.empty_definition = next(
        (definition for definition, spec in zip(fixture.definitions, specs) if spec.association_share == 0), None
    )

    budget = _association_budget(specs, scenario.association_count)
    fixture.peer_objects = _create_peer_objects(specs, budget, objects, seed)
    fixture.association_count = _create_associations(specs, fixture.definitions, budget, objects, fixture.peer_objects)

    clear_relationship_caches()
    logger.info("Built relationship benchmark fixture: %s", fixture.summary())
    return fixture


@dataclass
class _DefinitionSpec:
    """Internal description of one relationship definition to create, plus how many associations it should carry."""

    label: str
    type: str
    #: Model on the source side. `Location` means the primary objects are (also) sources.
    source_model: type
    #: Model on the destination side.
    destination_model: type
    #: Which side the primary objects sit on: `"source"` or `"destination"`.
    primary_side: str
    #: Relative share of the association budget; 0 means "create no associations for this definition".
    association_share: int = 0
    #: Hard cap on associations, used for cardinalities that cannot support many.
    max_associations: int = None
    #: Floor on associations, used where fewer would fail to exercise the behavior the definition exists to cover.
    min_associations: int = 1
    hidden: bool = False
    #: Whether the definition renders on the object detail page's Advanced tab instead of the main tab.
    advanced_ui: bool = False
    #: Filter dict applied to `primary_side`, so that applicability evaluation is actually exercised.
    filter_params: dict = None

    @property
    def peer_model(self):
        """The model on the opposite side from the primary objects."""
        return self.destination_model if self.primary_side == "source" else self.source_model

    @property
    def is_same_model(self):
        return self.source_model is self.destination_model

    @property
    def symmetric(self):
        return self.type in (
            RelationshipTypeChoices.TYPE_ONE_TO_ONE_SYMMETRIC,
            RelationshipTypeChoices.TYPE_MANY_TO_MANY_SYMMETRIC,
        )

    @property
    def exclusive_peers(self):
        """
        Whether each peer object may be used by only one association of this relationship.

        True for the cardinalities whose `clean()` forbids multiple sources per destination, which means peer
        objects cannot be shared between primary objects for this definition.
        """
        return self.type != RelationshipTypeChoices.TYPE_MANY_TO_MANY


def _create_primary_objects(scenario, seed):
    """Create the `LocationType` and `Location` objects that relationships are measured against."""
    from nautobot.dcim.models import Location, LocationType

    location_status = Status.objects.get_for_model(Location).first()
    location_type = LocationType.objects.create(name=f"{seed} Bench Location Type")
    objects = Location.objects.bulk_create(
        [
            Location(name=f"{seed} Bench Location {index:05d}", location_type=location_type, status=location_status)
            for index in range(scenario.object_count + _SAME_MODEL_PEER_HEADROOM)
        ]
    )
    # The trailing objects exist purely to be peers for the same-model definitions, so they are not returned
    # as primary objects - but they are real Locations and so are themselves valid relationship endpoints.
    return location_type, objects[: scenario.object_count]


#: Extra same-model objects created so that same-model definitions have peers that are not primary objects.
_SAME_MODEL_PEER_HEADROOM = 8


def _definition_specs(scenario, selected_peer_models, location_type, objects):
    """
    Build the list of definitions to create for this scenario.

    When `scenario.coverage` is set, the first entries are the fixed coverage set (one per behavior that must
    always be represented) and any remaining definitions are many-to-many "bulk" definitions carrying the
    association volume. When it is not set, *all* definitions are homogeneous bulk definitions.
    """
    from nautobot.dcim.models import Location

    shared_filter = {"location_type": [location_type.name]}
    # A second, *distinct* filter dict, so that per-distinct-filter memoization can be told apart from
    # "all filters collapse to one query".
    distinct_filter = {"location_type": [location_type.name], "name": sorted(obj.name for obj in objects)}

    def peer(index):
        return selected_peer_models[index % len(selected_peer_models)]

    coverage_specs = [
        _DefinitionSpec(
            label="Bench one-to-one",
            type=RelationshipTypeChoices.TYPE_ONE_TO_ONE,
            source_model=Location,
            destination_model=peer(0),
            primary_side="source",
            association_share=1,
            max_associations=1,
        ),
        _DefinitionSpec(
            label="Bench one-to-many",
            type=RelationshipTypeChoices.TYPE_ONE_TO_MANY,
            source_model=Location,
            destination_model=peer(1),
            primary_side="source",
            association_share=1,
            max_associations=5,
        ),
        _DefinitionSpec(
            label="Bench many-to-many",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            source_model=Location,
            destination_model=peer(2),
            primary_side="source",
            association_share=4,
        ),
        _DefinitionSpec(
            label="Bench many-to-many reverse",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            source_model=peer(0),
            destination_model=Location,
            primary_side="destination",
            association_share=4,
        ),
        _DefinitionSpec(
            label="Bench one-to-many reverse",
            type=RelationshipTypeChoices.TYPE_ONE_TO_MANY,
            source_model=peer(1),
            destination_model=Location,
            primary_side="destination",
            association_share=1,
            max_associations=1,
        ),
        _DefinitionSpec(
            label="Bench same-model one-to-one",
            type=RelationshipTypeChoices.TYPE_ONE_TO_ONE,
            source_model=Location,
            destination_model=Location,
            primary_side="source",
            association_share=1,
            max_associations=1,
        ),
        _DefinitionSpec(
            label="Bench same-model many-to-many symmetric",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY_SYMMETRIC,
            source_model=Location,
            destination_model=Location,
            primary_side="source",
            association_share=1,
            max_associations=4,
            # At least two, so that the primary object appears as both source and destination and the loader's
            # de-duplication across the two side-specific queries is genuinely exercised.
            min_associations=2,
        ),
        _DefinitionSpec(
            label="Bench same-model one-to-one symmetric",
            type=RelationshipTypeChoices.TYPE_ONE_TO_ONE_SYMMETRIC,
            source_model=Location,
            destination_model=Location,
            primary_side="source",
            association_share=1,
            max_associations=1,
        ),
        _DefinitionSpec(
            label="Bench hidden",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            source_model=Location,
            destination_model=peer(0),
            primary_side="source",
            association_share=1,
            hidden=True,
        ),
        _DefinitionSpec(
            label="Bench source filtered",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            source_model=Location,
            destination_model=peer(1),
            primary_side="source",
            association_share=1,
            filter_params=shared_filter,
        ),
        _DefinitionSpec(
            label="Bench source filtered shared dict",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            source_model=Location,
            destination_model=peer(2),
            primary_side="source",
            association_share=1,
            # Deliberately the same filter as the previous definition, so that PR 5's per-distinct-filter
            # batching has something to collapse.
            filter_params=shared_filter,
        ),
        _DefinitionSpec(
            label="Bench destination filtered",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            source_model=peer(0),
            destination_model=Location,
            primary_side="destination",
            association_share=1,
            filter_params=shared_filter,
        ),
        _DefinitionSpec(
            label="Bench distinct filter",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            source_model=Location,
            destination_model=peer(0),
            primary_side="source",
            association_share=1,
            filter_params=distinct_filter,
        ),
        _DefinitionSpec(
            label="Bench advanced UI",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            source_model=Location,
            destination_model=peer(2),
            primary_side="source",
            association_share=1,
            advanced_ui=True,
        ),
        _DefinitionSpec(
            label="Bench empty",
            type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
            source_model=Location,
            destination_model=peer(1),
            primary_side="source",
            association_share=0,
        ),
    ]

    specs = coverage_specs if scenario.coverage else []
    target_count = len(specs) if scenario.definition_count == COVERAGE_ONLY else scenario.definition_count
    if target_count < len(specs):
        raise ValueError(
            f"definition_count must be at least {len(specs)} so that every relationship behavior is represented; "
            f"pass COVERAGE_ONLY for exactly the coverage set, or coverage=False for a homogeneous scaling sweep"
        )

    # Pad with bulk many-to-many definitions, alternating which side the primary objects are on so that both
    # the source-side and destination-side association queries carry real volume.
    for index in range(target_count - len(specs)):
        primary_is_source = index % 2 == 0
        peer_model = peer(index)
        specs.append(
            _DefinitionSpec(
                label=f"Bench bulk {index:04d}",
                type=RelationshipTypeChoices.TYPE_MANY_TO_MANY,
                source_model=Location if primary_is_source else peer_model,
                destination_model=peer_model if primary_is_source else Location,
                primary_side="source" if primary_is_source else "destination",
                association_share=8,
            )
        )

    return specs


def _create_definitions(specs, seed):
    """Create one `Relationship` per spec, in spec order."""
    content_types = {}

    def content_type_for(model):
        if model not in content_types:
            content_types[model] = ContentType.objects.get_for_model(model)
        return content_types[model]

    definitions = []
    for index, spec in enumerate(specs):
        relationship = Relationship(
            label=f"{seed} {spec.label} {index:04d}",
            source_type=content_type_for(spec.source_model),
            destination_type=content_type_for(spec.destination_model),
            type=spec.type,
        )
        relationship.advanced_ui = spec.advanced_ui
        if spec.hidden:
            # Symmetric definitions require both sides to agree; setting both is correct for asymmetric ones too,
            # since the benchmark only cares that *some* definition is hidden from the primary object's side.
            relationship.source_hidden = True
            relationship.destination_hidden = True
        if spec.filter_params:
            setattr(relationship, f"{spec.primary_side}_filter", spec.filter_params)
            if spec.symmetric:
                relationship.destination_filter = spec.filter_params
                relationship.source_filter = spec.filter_params
        relationship.validated_save()
        definitions.append(relationship)

    return definitions


def _association_budget(specs, association_count):
    """
    Split `association_count` across the specs in proportion to their `association_share`.

    Returns a list of per-spec association counts, in spec order, respecting each spec's `max_associations`.
    Any budget freed by a capped spec is redistributed to the uncapped ones, so the requested total is met
    whenever the uncapped specs can absorb it.
    """
    total_share = sum(spec.association_share for spec in specs) or 1
    counts = []
    for spec in specs:
        if spec.association_share == 0:
            counts.append(0)
            continue
        allocated = max(spec.min_associations, round(association_count * spec.association_share / total_share))
        if spec.max_associations is not None:
            allocated = min(allocated, spec.max_associations)
        counts.append(allocated)

    # Redistribute the shortfall (or overage) across specs that have no cap.
    uncapped = [index for index, spec in enumerate(specs) if spec.association_share and spec.max_associations is None]
    if uncapped:
        shortfall = association_count - sum(counts)
        while shortfall != 0:
            step = 1 if shortfall > 0 else -1
            progressed = False
            for index in uncapped:
                if shortfall == 0:
                    break
                if step < 0 and counts[index] <= 1:
                    continue
                counts[index] += step
                shortfall -= step
                progressed = True
            if not progressed:
                break

    return counts


def _create_peer_objects(specs, budget, objects, seed):
    """
    Bulk-create the peer objects that associations will point at.

    Peer objects are shared between definitions wherever cardinality allows, so the number created is driven by
    the largest single definition rather than by the total association count.
    """
    needed = {}
    for spec, count in zip(specs, budget):
        if count == 0 or spec.is_same_model:
            continue
        # A definition whose peers cannot be shared between primary objects needs `count` peers *per* object.
        multiplier = len(objects) if spec.exclusive_peers else 1
        needed[spec.peer_model] = max(needed.get(spec.peer_model, 0), count * multiplier)

    peer_objects = {}
    for model, count in needed.items():
        peer_objects[model] = model.objects.bulk_create(
            [model(name=f"{seed} Bench {model._meta.model_name} {index:06d}") for index in range(count)],
            batch_size=1000,
        )
    return peer_objects


def _create_associations(specs, definitions, budget, objects, peer_objects):
    """
    Bulk-create all `RelationshipAssociation` rows.

    `bulk_create()` is used deliberately: it skips `clean()`, which is far too slow at 10,000 associations, so
    this function is responsible for generating only cardinality-valid data. See `_DefinitionSpec.exclusive_peers`.
    """
    from nautobot.dcim.models import Location

    same_model_peers = _same_model_peers(objects)
    location_ct = ContentType.objects.get_for_model(Location)
    peer_content_types = {model: ContentType.objects.get_for_model(model) for model in peer_objects}

    associations = []
    for spec, definition, count in zip(specs, definitions, budget):
        if count == 0:
            continue
        for object_index, obj in enumerate(objects):
            peers = _peers_for(spec, count, object_index, objects, peer_objects, same_model_peers)
            peer_ct = location_ct if spec.is_same_model else peer_content_types[spec.peer_model]
            for peer_index, peer in enumerate(peers):
                if spec.symmetric and peer_index % 2 == 1:
                    # Put the primary object on the destination side for half of the symmetric associations, so
                    # that de-duplication across the two side-specific queries is genuinely exercised.
                    source, source_ct, destination, destination_ct = peer, peer_ct, obj, location_ct
                elif spec.primary_side == "source":
                    source, source_ct, destination, destination_ct = obj, location_ct, peer, peer_ct
                else:
                    source, source_ct, destination, destination_ct = peer, peer_ct, obj, location_ct
                associations.append(
                    RelationshipAssociation(
                        relationship=definition,
                        source_type=source_ct,
                        source_id=source.pk,
                        destination_type=destination_ct,
                        destination_id=destination.pk,
                    )
                )

    RelationshipAssociation.objects.bulk_create(associations, batch_size=1000)
    return len(associations)


def _same_model_peers(objects):
    """Return Locations usable as same-model peers: the headroom objects created alongside the primary ones."""
    from nautobot.dcim.models import Location

    primary_pks = {obj.pk for obj in objects}
    return [
        location
        for location in Location.objects.filter(location_type=objects[0].location_type).exclude(pk__in=primary_pks)
    ]


def _peers_for(spec, count, object_index, objects, peer_objects, same_model_peers):
    """Select `count` peer objects for one (spec, primary object) pair, honoring exclusivity."""
    if spec.is_same_model:
        # Same-model peers are scarce (headroom is small), so wrap around and clamp.
        available = same_model_peers or [obj for obj in objects if obj is not objects[object_index]]
        return [available[(object_index + index) % len(available)] for index in range(min(count, len(available)))]

    available = peer_objects[spec.peer_model]
    if spec.exclusive_peers:
        start = object_index * count
        return available[start : start + count]
    return available[:count]


@contextlib.contextmanager
def capture_db_time():
    """
    Accumulate real time spent inside the database driver for the duration of the block.

    Django's debug cursor records per-query time truncated to milliseconds, which rounds nearly every query in a
    relationship N+1 to zero and makes the total useless. `connection.execute_wrapper()` lets us time each call
    ourselves at `perf_counter` resolution.

    Yields:
        (dict): A dict whose `"ms"` key holds the accumulated milliseconds; only final after the block exits.
    """
    elapsed = {"ms": 0.0}

    def wrapper(execute, sql, params, many, context):
        started = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            elapsed["ms"] += (time.perf_counter() - started) * 1000

    with connection.execute_wrapper(wrapper):
        yield elapsed


class RelationshipBenchmarkMixin:
    """
    Test-case mixin providing query-count assertions and measurement recording.

    Measurements are appended as JSON Lines to the file named by the `NAUTOBOT_RELATIONSHIP_BENCH_OUT`
    environment variable, if set, so that per-PR before/after tables can be generated rather than hand-typed.
    See `format_bench_table()`.
    """

    #: Number of timed passes used to derive median and p95 wall time.
    bench_iterations = 5

    def assertQueryCountBounded(self, func, *, max_queries, label=""):  # matches unittest naming
        """
        Assert that calling `func` issues no more than `max_queries` database queries.

        Args:
            func (Callable): Zero-argument callable to execute.
            max_queries (int): Inclusive upper bound on query count.
            label (str): Description included in the failure message.

        Returns:
            The value returned by `func`.
        """
        with CaptureQueriesContext(connection) as ctx:
            result = func()
        query_count = len(ctx.captured_queries)
        self.assertLessEqual(
            query_count,
            max_queries,
            f"{label or func!r} issued {query_count} queries, expected at most {max_queries}",
        )
        return result

    def measure(self, func, *, scenario, surface, iterations=None, **extra):
        """
        Time `func` and count its queries, then record the result.

        Wall time is measured without a debug cursor (which would inflate it substantially); query count and
        database time are measured in a separate final pass, so each number is taken under the conditions that
        make it meaningful.

        Args:
            func (Callable): Zero-argument callable to measure.
            scenario (Union[RelationshipBenchScenario, str]): Scenario the data was built from.
            surface (str): Which surface is being measured, e.g. `"detail_render"`.
            iterations (int): Number of timed passes; defaults to `bench_iterations`.
            **extra (Any): Additional fields to record alongside the measurement.

        Returns:
            (dict): The recorded measurement.
        """
        iterations = iterations or self.bench_iterations
        durations = []
        for _ in range(iterations):
            started = time.perf_counter()
            func()
            durations.append((time.perf_counter() - started) * 1000)

        with capture_db_time() as db_time, CaptureQueriesContext(connection) as ctx:
            func()

        return self.record(
            scenario=scenario,
            surface=surface,
            queries=len(ctx.captured_queries),
            db_time_ms=round(db_time["ms"], 2),
            wall_median_ms=round(median(durations), 2),
            wall_p95_ms=round(_percentile(durations, 95), 2),
            **extra,
        )

    def record(self, *, scenario, surface, queries, db_time_ms=None, wall_median_ms=None, wall_p95_ms=None, **extra):
        """Append one measurement row to the benchmark report, and return it."""
        scenario_name = scenario if isinstance(scenario, str) else scenario.name
        row = {
            "scenario": scenario_name,
            "surface": surface,
            "queries": queries,
            "db_time_ms": db_time_ms,
            "wall_median_ms": wall_median_ms,
            "wall_p95_ms": wall_p95_ms,
            "test": self.id(),
            **extra,
        }
        out_path = os.environ.get(BENCH_OUT_ENV_VAR)
        if out_path:
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            with open(out_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
        logger.info("relationship benchmark: %s", row)
        return row


def _percentile(values, percentile):
    """Return the given percentile of `values` using nearest-rank, which is well-defined for small samples."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(percentile / 100 * len(ordered)) - 1))
    return ordered[index]


def load_bench_report(path):
    """Read a JSONL benchmark report written by `RelationshipBenchmarkMixin.record()`."""
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def format_bench_table(rows, *, scenarios=None, metric="queries"):
    """
    Render benchmark rows as a Markdown table of surface x scenario, for pasting into a pull request.

    Args:
        rows (list): Measurement dicts, e.g. from `load_bench_report()`.
        scenarios (list): Scenario names to include as columns, in order; defaults to all seen, sorted.
        metric (str): Which recorded key to tabulate.

    Returns:
        (str): A Markdown table.
    """
    scenarios = scenarios or sorted({row["scenario"] for row in rows})
    surfaces = sorted({row["surface"] for row in rows})
    by_key = {(row["surface"], row["scenario"]): row for row in rows}

    lines = [
        "| Surface | " + " | ".join(scenarios) + " |",
        "|---" * (len(scenarios) + 1) + "|",
    ]
    for surface in surfaces:
        cells = []
        for scenario in scenarios:
            row = by_key.get((surface, scenario))
            value = row.get(metric) if row else None
            cells.append("n/a" if value is None else str(value))
        lines.append(f"| {surface} | " + " | ".join(cells) + " |")
    return "\n".join(lines)
