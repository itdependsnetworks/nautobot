"""GraphQL cost calculator: static AST analysis only — parse, never execute.

All GraphQL costing knowledge lives in this module so it can be replaced or removed without
touching REST costing (e.g. by a future schema-aware calculator that can distinguish to-one
relations from lists). The costing module knows it only as one entry in CALCULATORS.

Known v0 coarseness, accepted and corrected by calibration rather than by code: a field with a
selection set but no page argument cannot be distinguished from a to-one relation using the AST
alone, so both are assumed to fan out by `graphql_default_page`; fragments are handled coarsely.
"""

import dataclasses

# graphql-core ships with graphene / Nautobot. Guarded so a packaging surprise degrades GraphQL
# costing to the flat floor instead of breaking every request.
try:
    from graphql import parse as gql_parse
    from graphql.language import ast as gql_ast

    GRAPHQL_AVAILABLE = True
except ImportError:  # pragma: no cover
    GRAPHQL_AVAILABLE = False

from nautobot.core.rate_limiting.config import KIND_GRAPHQL

GRAPHQL_DEFAULT_WEIGHTS = {
    "graphql_default_page": 50,  # assumed fan-out when no first/last/limit argument is present
    "graphql_node_divisor": 100,  # cost = max(floor, estimated_nodes / this)
    "graphql_floor": 5.0,
}

_PAGE_ARGUMENT_NAMES = ("first", "last", "limit")


@dataclasses.dataclass
class GraphQLFeatures:
    """The GraphQL cost-feature schema — the authoritative contract for what a GraphQL request is priced on.

    Serialized verbatim into the calibration log's `features` field, so these names are what
    operators regress against offline; treat renames as breaking changes to that dataset.
    """

    method: str
    parse_ok: bool = False
    max_depth: int = 0
    field_count: int = 0
    estimated_nodes: int = 0
    # When set, cost computation failed and the fields above were never populated.
    classification_error: bool = False
    kind: str = KIND_GRAPHQL


def classify(request, weights):
    """Extract cost features from a GraphQL request without executing anything.

    `parse_ok` is False when there is no parseable query document, in which case
    :func:`estimate` charges the flat floor (the view will reject it anyway).
    """
    features = GraphQLFeatures(method=request.method)
    if not GRAPHQL_AVAILABLE:
        return features
    query_text = _extract_query(request)
    if not query_text:
        return features
    try:
        document = gql_parse(query_text)
    except Exception:  # malformed query; graphene will reject it anyway
        return features

    state = {"fields": 0, "max_depth": 0, "nodes": 0}
    default_page = int(weights["graphql_default_page"])
    try:
        for definition in document.definitions:
            if isinstance(definition, gql_ast.OperationDefinitionNode):
                state["nodes"] += 1
                _walk(definition.selection_set, 1, 1, state, default_page)
    except Exception:
        # E.g. RecursionError from a pathologically nested document. Degrade exactly like an
        # unparseable query — charge the floor — rather than raising into the middleware's generic
        # cost-1 fallback, which would underprice the most suspicious request shape there is.
        return features

    features.parse_ok = True
    features.max_depth = state["max_depth"]
    features.field_count = state["fields"]
    features.estimated_nodes = state["nodes"]
    return features


def estimate(features, weights):
    """Pure (features, weights) -> cost; GitHub/Shopify-style node-count pricing."""
    if not features.parse_ok:
        return float(weights["graphql_floor"])
    nodes = max(features.estimated_nodes, 1)
    return round(max(float(weights["graphql_floor"]), nodes / float(weights["graphql_node_divisor"])), 2)


def _extract_query(request):
    """Return the GraphQL query text from a GET query parameter or a POST body."""
    if request.method == "GET":
        return request.GET.get("query", "")
    # Reuse the existing body parser (handles application/json and application/graphql).
    # Imported lazily on purpose: nautobot.core.middleware pulls in the full view layer, which
    # this module must not load at import time (nautobot.core.settings imports our sibling
    # config module during settings load).
    from nautobot.core.middleware import GraphQLOpenTelemetryMiddleware

    query_text, _ = GraphQLOpenTelemetryMiddleware._parse_graphql_body(request)
    return query_text or ""


def _walk(selection_set, depth, fan_in, state, default_page):
    """Accumulate field/node counts; `fan_in` is the number of parent nodes this level resolves under."""
    if selection_set is None:
        return
    state["max_depth"] = max(state["max_depth"], depth)
    for selection in selection_set.selections:
        if not isinstance(selection, gql_ast.FieldNode):
            continue  # fragments handled coarsely in v0
        state["fields"] += 1
        if selection.selection_set is not None:
            # A field with a selection set and a page argument is list-like: each parent fans out
            # to `page` children. Without a page argument the AST alone can't distinguish a list
            # from a to-one relation, so the conservative default fan-out is recorded and
            # calibration corrects the weights.
            page = _page_arg(selection)
            fan_out = page if page is not None else default_page
            child_nodes = fan_in * fan_out
            state["nodes"] += child_nodes
            _walk(selection.selection_set, depth + 1, child_nodes, state, default_page)


def _page_arg(field):
    """Return the first/last/limit integer argument of a field, if present."""
    for argument in getattr(field, "arguments", None) or ():
        if argument.name.value in _PAGE_ARGUMENT_NAMES and isinstance(argument.value, gql_ast.IntValueNode):
            return int(argument.value.value)
    return None
