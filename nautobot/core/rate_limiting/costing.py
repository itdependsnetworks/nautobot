"""Pure costing pipeline: classify -> estimate -> cost, from the request shape alone.

Never touches the database or Redis, never imports the middleware, never reads MODE. The features
object returned alongside the cost is exactly what the calibration log records, so the shipped
weights (deliberately provisional v0 values) can be regressed offline against measured time
before enforcement is ever enabled.

Every calculator is a symmetric `(classify, estimate)` pair registered in :data:`CALCULATORS`:
classification is feature extraction, estimation is pure `(features, weights)` math, and
:func:`cost` dispatches and finalizes (ceil, floor of 1). Replacing a calculator (most likely the
GraphQL one) means swapping one dict entry.

Callers should invoke this module qualified (`costing.cost(request)`) — a bare `cost` import
begs to be shadowed by the local variable holding its result.
"""

import math

from nautobot.core.rate_limiting import graphql_cost, rest_cost
from nautobot.core.rate_limiting.config import get_config, KIND_GRAPHQL, KIND_REST

# Cardinality combining weights (layer 9). Only consumed by `combine()` below, which is not yet
# wired into the request path — see that function's docstring.
CARDINALITY_DEFAULT_WEIGHTS = {
    "cardinality_divisor": 100_000,  # rows per multiplier step
    "cardinality_cap_multiplier": 10,  # multiplier never exceeds this, bounding the blast radius
}

DEFAULT_WEIGHTS = {
    **rest_cost.REST_DEFAULT_WEIGHTS,
    **graphql_cost.GRAPHQL_DEFAULT_WEIGHTS,
    **CARDINALITY_DEFAULT_WEIGHTS,
}

# Weight preset under which every request costs exactly 1, turning the budget into a plain
# requests-per-window rate limit — no dedicated code path, just configuration:
#
#     from nautobot.core.rate_limiting.costing import FLAT_WEIGHTS
#     RATE_LIMITING = {"MODE": "enforce", "LIMIT": 300, "HEURISTIC_WEIGHTS": FLAT_WEIGHTS}
#
# Infinite divisors zero out the page/node terms (ceil(x/inf) == 0, clamped back to a multiplier
# of 1; the GraphQL floor of 1 then wins), so flatness holds for arbitrarily large page arguments.
FLAT_WEIGHTS = {
    "rest_read_base": 1.0,
    "rest_write_base": 1.0,
    "rest_page_size_divisor": float("inf"),
    "rest_per_join_surcharge": 0.0,
    "rest_unindexable_surcharge": 0.0,
    "rest_depth_multiplier_per_level": 0.0,
    "rest_computed_fields_multiplier": 1.0,
    "rest_csv_multiplier": 1.0,
    "graphql_default_page": 1,
    "graphql_node_divisor": float("inf"),
    "graphql_floor": 1.0,
}

# The REST/GraphQL seam: each calculator is a (classify, estimate) pair with identical signatures.
CALCULATORS = {
    KIND_REST: (rest_cost.classify, rest_cost.estimate),
    KIND_GRAPHQL: (graphql_cost.classify, graphql_cost.estimate),
}


def request_kind(request):
    """Return "graphql" or "rest" for a request already known to be API-bound."""
    from nautobot.core.middleware import _GRAPHQL_PATHS

    return KIND_GRAPHQL if request.path.rstrip("/") in _GRAPHQL_PATHS else KIND_REST


def features_class(kind):
    """Return the feature schema (dataclass) for a request kind."""
    return graphql_cost.GraphQLFeatures if kind == KIND_GRAPHQL else rest_cost.RestFeatures


def get_weights():
    """Return the effective heuristic weights (shipped defaults merged under operator overrides)."""
    return {**DEFAULT_WEIGHTS, **get_config()["HEURISTIC_WEIGHTS"]}


def cost(request):
    """Return `(cost, features)` for a request; cost is always an integer >= 1.

    `features` is the kind's feature dataclass and doubles as the calibration-log input record.
    """
    classify, estimate = CALCULATORS[request_kind(request)]
    weights = get_weights()
    features = classify(request, weights)
    return max(1, math.ceil(estimate(features, weights))), features


def combine(heuristic_cost, cardinality, weights):
    """The single place a heuristic cost and a model cardinality meet (layer 9) — a capped multiplier.

    `multiplier = min(max(1, cardinality // cardinality_divisor), cardinality_cap_multiplier)`,
    so queries against large tables cost proportionally more, small tables change nothing, and the
    cap bounds the blast radius of any one table's growth. `cardinality=None` (unknown, or the
    feature unused) passes the heuristic through unchanged.

    Deliberately NOT wired into :func:`cost` yet, and deliberately pure (no Redis, no model
    resolution): cardinality pricing may not make the final solution, and keeping this as an
    isolated bolt-on means adopting it later changes one call site — or dropping it deletes this
    function and its tests, nothing else.
    """
    if cardinality is None:
        return int(heuristic_cost)
    multiplier = min(
        max(1, int(cardinality) // int(weights["cardinality_divisor"])),
        int(weights["cardinality_cap_multiplier"]),
    )
    return int(heuristic_cost) * multiplier
