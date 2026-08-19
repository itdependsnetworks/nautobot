"""
Object-centric loading of RelationshipAssociations.

Relationship retrieval was historically *definition-centric*: for each relationship definition applicable to a
model, ask the database whether this object has any associations. Query count therefore grew with the number of
definitions, independent of how much data actually existed. This module inverts that: it retrieves every
association involving an object (or a batch of objects) in two queries, one per endpoint side, then groups the
rows in memory. Resolving the objects on the far end of those associations in bulk lands in a later story
(core-4 Bulk peer resolution); this story stops at the association rows.

The loader is the single owner of applicable-definition resolution, association retrieval, grouping, and symmetric
normalization. `RelationshipModel` helpers delegate to it and reshape its output into their existing return
shapes, so callers and Apps see no interface change.

Note on returned querysets: several existing consumers require real `QuerySet` instances rather than lists.
`nautobot.core.ui.object_detail.KeyValueTablePanel.render_value()` branches on `isinstance(value, models.QuerySet)`,
and the relationship UI templates call `value.queryset.count`. `evaluated_queryset()` therefore returns a genuine
queryset whose results are already loaded, which satisfies those consumers without issuing a query.
"""

from collections import defaultdict
from dataclasses import dataclass
import logging

from django.contrib.contenttypes.models import ContentType

from nautobot.core.utils.lookup import get_filterset_for_model
from nautobot.core.utils.otel import traced_span
from nautobot.extras.choices import RelationshipSideChoices

logger = logging.getLogger(__name__)

#: The two concrete endpoint sides an association row can match an object on.
ENDPOINT_SIDES = (RelationshipSideChoices.SIDE_SOURCE, RelationshipSideChoices.SIDE_DESTINATION)


@dataclass(frozen=True)
class AssociationRecord:
    """
    One association, as seen from one of the objects being loaded.

    Attributes:
        association (RelationshipAssociation): The association row.
        matched_side (str): Which endpoint of the association the object sits on, `"source"` or `"destination"`.
            Retained even for symmetric relationships, where the caller-facing side is `"peer"`, because it is what
            identifies which endpoint is the peer.
        peer (Model): The resolved object on the other endpoint, or None if it could not be resolved (unresolvable
            content type, missing model class, stale association, or excluded by permissions).
    """

    association: object
    matched_side: str
    peer: object = None

    @property
    def peer_side(self):
        """The endpoint holding the peer."""
        return RelationshipSideChoices.OPPOSITE[self.matched_side]

    @property
    def peer_type_id(self):
        """ContentType id of the peer endpoint."""
        return getattr(self.association, f"{self.peer_side}_type_id")

    @property
    def peer_id(self):
        """Object id of the peer endpoint."""
        return getattr(self.association, f"{self.peer_side}_id")

    def with_peer(self, peer):
        """Return a copy of this record carrying the resolved `peer`."""
        return AssociationRecord(association=self.association, matched_side=self.matched_side, peer=peer)


def evaluated_queryset(model, instances, *, order_by=None):
    """
    Return a real `QuerySet` for `model` whose results are already loaded, issuing no database query.

    Used where a caller's contract requires a queryset but the objects have already been fetched in bulk. The
    queryset's filter is a faithful description of its contents, so anything that re-evaluates it (by cloning it,
    for instance) still gets correct results, just at the cost of a query.

    Callers must iterate the returned queryset directly. Anything that *clones* it - `.all()`, `.filter()`,
    `.order_by()` - drops the loaded results and the peer caches attached to them, silently restoring the
    per-association queries this module exists to remove.

    Args:
        model (type): The Django model the queryset is over.
        instances (Iterable): Already-fetched instances of `model`, in the order they should appear.
        order_by (str): Optional explicit ordering to declare on the queryset. Pass this when `model` has no
            `Meta.ordering`, so that `QuerySet.first()` can use the loaded results instead of cloning and
            re-querying; the value must match the order `instances` is already in.

    Returns:
        (QuerySet): Queryset of exactly `instances`.
    """
    instances = list(instances)
    queryset = model.objects.filter(pk__in=[instance.pk for instance in instances])
    if order_by is not None:
        queryset = queryset.order_by(order_by)
    queryset._result_cache = instances
    return queryset


class RelationshipAssociationLoader:
    """
    Load all RelationshipAssociations involving one or more objects of a single model.

    Construct through `for_object()` or `for_objects()` rather than directly. `load()` is idempotent; its result is
    memoized on the instance.
    """

    def __init__(self, objects, *, include_hidden=False, advanced_ui=None, user=None):
        """
        Args:
            objects (list): Instances of one concrete model. Must be non-empty and homogeneous.
            include_hidden (bool): Whether to include definitions hidden on the object's side.
            advanced_ui (bool): If not None, restrict to definitions with this `advanced_ui` value.
            user (User): If provided, peer objects are restricted to those this user may view. `None` means no
                restriction, matching the behavior of the UI and REST callers today.
        """
        if not objects:
            raise ValueError("RelationshipAssociationLoader requires at least one object")
        self.objects = list(objects)
        self.model = self.objects[0]._meta.model
        self.concrete_model = self.objects[0]._meta.concrete_model
        self.include_hidden = include_hidden
        self.advanced_ui = advanced_ui
        self.user = user
        self._result = None
        self._content_type = None
        # Cache of filter dict -> set of object pks matching it, so that definitions sharing a filter, and repeated
        # loads within one loader, evaluate that filter only once.
        self._filter_matches = {}

    @classmethod
    def for_object(cls, obj, **kwargs):
        """Construct a loader for a single object."""
        return cls([obj], **kwargs)

    @classmethod
    def for_objects(cls, objects, **kwargs):
        """
        Construct a loader for a batch of objects, which must all be of the same concrete model.

        No production code calls this yet, though it is tested. Batching ten objects costs 12 queries against 120
        for ten separate loads, so the REST list response is the obvious consumer; see the performance-opportunity
        comment on `nautobot.core.api.serializers.RelationshipModelSerializerMixin` for what wiring it up requires.
        """
        return cls(objects, **kwargs)

    def get_content_type(self):
        """
        Return the ContentType of the objects being loaded, resolving it once per loader.

        A method rather than a property because it can reach the database. Django's ContentType manager keeps its
        own process-wide cache, so in practice it usually does not.
        """
        if self._content_type is None:
            self._content_type = ContentType.objects.get_for_model(self.concrete_model)
        return self._content_type

    def load(self):
        """
        Retrieve and group all applicable associations.

        Returns:
            (RelationshipLoadResult): Grouped associations, merged against the applicable definitions so that
                definitions with no associations are still represented.
        """
        if self._result is not None:
            return self._result

        with traced_span(
            "nautobot.extras.relationships",
            "load_for_objects",
            **{
                "nautobot.extras.relationships.model": self.concrete_model._meta.label_lower,
                "nautobot.extras.relationships.objects": len(self.objects),
            },
        ) as span:
            applicable = self._applicable_definitions()
            definition_count = len({relationship.pk for relationship, _side, _pks in applicable})
            associations = self._fetch_associations(applicable)
            grouped = self._group_associations(applicable, associations)

            span.set_attribute("nautobot.extras.relationships.definitions", definition_count)
            span.set_attribute("nautobot.extras.relationships.associations", len(associations))
            span.set_attribute("nautobot.extras.relationships.filter_evaluations", len(self._filter_matches))

            self._result = RelationshipLoadResult(
                objects=self.objects,
                applicable=applicable,
                grouped=grouped,
                loader=self,
            )
        return self._result

    def _definitions_by_side(self):
        """
        Return `[(side, [relationship, ...]), ...]` for the object's model, from the existing definition cache.

        The list form of `get_for_model()` is used deliberately: it is cached, so applying `advanced_ui` in Python
        avoids the database query that filtering the cached *queryset* form would incur.
        """
        # Imported here to avoid a circular import at module load: models.relationships imports this module.
        from nautobot.extras.models.relationships import Relationship

        source_definitions, destination_definitions = Relationship.objects.get_for_model(
            self.concrete_model, get_queryset=False
        )
        by_side = [
            (RelationshipSideChoices.SIDE_SOURCE, source_definitions),
            (RelationshipSideChoices.SIDE_DESTINATION, destination_definitions),
        ]
        if self.advanced_ui is None:
            return by_side
        return [
            (side, [definition for definition in definitions if definition.advanced_ui == self.advanced_ui])
            for side, definitions in by_side
        ]

    def _applicable_definitions(self):
        """
        Resolve which definitions apply to which objects.

        Returns:
            (list): `[(relationship, side, applicable_pks), ...]` where `side` is the side the objects sit on and
                `applicable_pks` is the set of object pks the definition applies to. A definition appears once per
                side it is relevant on, so a same-model definition appears twice, matching the legacy behavior.
        """
        applicable = []
        for side, definitions in self._definitions_by_side():
            for relationship in definitions:
                if getattr(relationship, f"{side}_hidden") and not self.include_hidden:
                    continue

                filter_params = getattr(relationship, f"{side}_filter")
                if filter_params:
                    matching = self._objects_matching_filter(filter_params)
                    if matching is not None:
                        if not matching:
                            continue
                        applicable.append((relationship, side, matching))
                        continue

                applicable.append((relationship, side, {obj.pk for obj in self.objects}))
        return applicable

    def _objects_matching_filter(self, filter_params):
        """
        Return the set of object pks matching `filter_params`, or None if the model has no FilterSet.

        Mirrors the legacy applicability check, which treats a model without a FilterSet as "filter cannot be
        evaluated, so the definition applies". Results are memoized per filter dict, so definitions that share a
        filter cost one query between them.
        """
        cache_key = _filter_cache_key(filter_params)
        if cache_key in self._filter_matches:
            return self._filter_matches[cache_key]

        filterset = get_filterset_for_model(self.model)
        if filterset is None:
            self._filter_matches[cache_key] = None
            return None

        base_queryset = self.model.objects.filter(pk__in=[obj.pk for obj in self.objects])
        matching = set(filterset(filter_params, base_queryset).qs.values_list("pk", flat=True))
        self._filter_matches[cache_key] = matching
        return matching

    def _fetch_associations(self, applicable):
        """
        Retrieve association rows for the objects, one query per endpoint side.

        No `select_related()` is used, deliberately. The `Relationship` objects are already in hand from the
        definition cache, so they are attached to each row directly; joining to fetch them again costs real time
        once an object has thousands of associations. The `source_type` and `destination_type` foreign keys are
        left alone because only their ids are needed here, and Django's ContentType manager serves the objects
        themselves from its own process-wide cache when a generic foreign key is dereferenced.

        Returns:
            (list): `[(side, association), ...]` where `side` is the side the object matched on.
        """
        from nautobot.extras.models.relationships import RelationshipAssociation

        definitions_by_pk = {relationship.pk: relationship for relationship, _side, _pks in applicable}
        if not definitions_by_pk:
            return []

        object_pks = [obj.pk for obj in self.objects]
        rows = []
        for side in ENDPOINT_SIDES:
            queryset = RelationshipAssociation.objects.filter(
                relationship__in=set(definitions_by_pk),
                **{f"{side}_type": self.get_content_type(), f"{side}_id__in": object_pks},
                # Deterministic order, which the legacy querysets lacked: RelationshipAssociation has no
                # Meta.ordering, so previously the display order of associations was whatever the database chose.
            ).order_by("pk")
            for association in queryset:
                # Populate the foreign key cache so that reading `association.relationship` does not lazy-load
                # once per row.
                association.relationship = definitions_by_pk[association.relationship_id]
                rows.append((side, association))
        return rows

    def _group_associations(self, applicable, associations):
        """
        Group association rows by object, relationship, and result side.

        Returns:
            (dict): `{(object_pk, relationship_pk, result_side): [AssociationRecord, ...]}` where `result_side` is
                `"peer"` for symmetric relationships and the matched endpoint side otherwise.

        Symmetric relationships are matched by both endpoint queries, and a same-model relationship can return the
        same row through either, so rows are de-duplicated by association pk within each group.
        """
        applicable_pks = defaultdict(set)
        for relationship, side, pks in applicable:
            applicable_pks[(relationship.pk, side)] |= pks

        grouped = defaultdict(list)
        seen = defaultdict(set)
        for side, association in associations:
            relationship = association.relationship
            object_pk = getattr(association, f"{side}_id")
            if object_pk not in applicable_pks.get((relationship.pk, side), ()):
                # The object has this relationship's association, but the definition does not apply to it on this
                # side (hidden, wrong advanced_ui, or excluded by the side filter).
                continue

            result_side = RelationshipSideChoices.SIDE_PEER if relationship.symmetric else side
            key = (object_pk, relationship.pk, result_side)
            if association.pk in seen[key]:
                continue
            seen[key].add(association.pk)
            grouped[key].append(AssociationRecord(association=association, matched_side=side))

        # Sort by association pk within each group. The endpoint queries are each ordered by pk, but they run one
        # after the other, so a symmetric relationship (matched by both) would otherwise hold all its source-side
        # rows ahead of all its destination-side rows. `association_sets()` declares `order_by("pk")` on the
        # queryset it builds, and that declaration has to describe the contents, or a caller that re-evaluates the
        # queryset gets a different order than one that reads the loaded results.
        for records in grouped.values():
            records.sort(key=lambda record: record.association.pk)

        return grouped


def _filter_cache_key(filter_params):
    """Build a hashable, order-independent key for a relationship side filter dict."""
    return tuple(sorted((key, _hashable(value)) for key, value in filter_params.items()))


def _hashable(value):
    """Coerce a JSON-derived filter value into something hashable."""
    if isinstance(value, list):
        return tuple(_hashable(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((key, _hashable(item)) for key, item in value.items()))
    return value


class RelationshipLoadResult:
    """
    Grouped result of one `RelationshipAssociationLoader.load()` call.

    Indexed by object, then by side (`source`, `destination`, `peer`), then by `Relationship`.
    """

    def __init__(self, *, objects, applicable, grouped, loader):
        self.objects = objects
        self.loader = loader
        self._grouped = grouped
        # Relationship instances keyed by pk, so callers get the same objects the definition cache provided.
        self._definitions = {}
        # {(object_pk, side): [relationship_pk, ...]} preserving definition order per side.
        self._definition_order = defaultdict(list)
        for relationship, side, pks in applicable:
            self._definitions[relationship.pk] = relationship
            result_side = RelationshipSideChoices.SIDE_PEER if relationship.symmetric else side
            for object_pk in pks:
                order = self._definition_order[(object_pk, result_side)]
                if relationship.pk not in order:
                    order.append(relationship.pk)

    def records_for(self, obj, relationship, side):
        """Return the `AssociationRecord` list for one object, relationship, and result side."""
        return self._grouped.get((obj.pk, relationship.pk, side), [])

    def associations_for(self, obj, relationship, side):
        """Return the list of associations for one object, relationship, and result side."""
        return [record.association for record in self.records_for(obj, relationship, side)]

    def association_sets(self, obj):
        """
        Return `{side: {relationship: <association QuerySet>}}` for one object.

        Every applicable definition is present, including those with no associations, matching the legacy shape.
        The querysets are already evaluated, so reading them issues no query.
        """
        from nautobot.extras.models.relationships import RelationshipAssociation

        result = {
            RelationshipSideChoices.SIDE_SOURCE: {},
            RelationshipSideChoices.SIDE_DESTINATION: {},
            RelationshipSideChoices.SIDE_PEER: {},
        }
        for side in result:
            for relationship_pk in self._definition_order.get((obj.pk, side), []):
                relationship = self._definitions[relationship_pk]
                associations = self.associations_for(obj, relationship, side)
                result[side][relationship] = evaluated_queryset(RelationshipAssociation, associations, order_by="pk")
        return result
