"""REST cost calculator: classify a request into features, then estimate a cost from weights.

The symmetric sibling of `graphql_cost`: each calculator module exposes a
`classify(request, weights) -> features` / `estimate(features, weights) -> float` pair,
registered in `costing.CALCULATORS`. Classification is feature extraction with no arithmetic;
estimation is pure (features, weights) math.
"""

import dataclasses
import math

from nautobot.core.rate_limiting.config import KIND_REST

# --- Shipped v0 heuristic weights. DELIBERATELY provisional: report mode plus the calibration ---
# --- log exist to replace them with regressed values. Overridable via HEURISTIC_WEIGHTS.       ---
REST_DEFAULT_WEIGHTS = {
    "rest_read_base": 1.0,
    "rest_write_base": 3.0,
    "rest_page_size_divisor": 50,  # cost *= ceil(limit / this)
    "rest_per_join_surcharge": 1.0,  # per relation traversal in filter keys
    "rest_unindexable_surcharge": 5.0,  # icontains / regex style lookups
    "rest_depth_multiplier_per_level": 1.0,  # cost *= (1 + N * this) for ?depth=N
    "rest_computed_fields_multiplier": 3.0,  # include=computed_fields
    "rest_csv_multiplier": 3.0,  # format=csv full renders
}

# Query params that are pagination/rendering controls, not filters.
NON_FILTER_PARAMS = frozenset(
    {
        "limit",
        "offset",
        "depth",
        "format",
        "include",
        "exclude",
        "sort",
        "api_version",
        "brief",
        "q",
    }
)

# Lookup suffixes that cannot use a btree index (sequential scan risk).
# Covers Django-style lookups and Nautobot's short filter suffixes.
UNINDEXABLE_LOOKUPS = frozenset(
    {
        # Django-style
        "icontains",
        "contains",
        "iregex",
        "regex",
        "iendswith",
        "endswith",
        # Nautobot short forms
        "ic",
        "nic",  # (not) case-insensitive contains
        "ie",
        "nie",  # (not) case-insensitive exact
        "iew",
        "niew",  # (not) case-insensitive ends-with
        "re",
        "nre",
        "ire",
        "nire",  # regex family
    }
)

# Lookup suffixes that ARE lookups but index-friendly; recognized so they are not miscounted as
# relation traversals.
INDEXABLE_LOOKUPS = frozenset(
    {
        "n",
        "exact",
        "iexact",
        "in",
        "gt",
        "gte",
        "lt",
        "lte",
        "isnull",
        "startswith",
        "istartswith",
        "isw",
        "nisw",
    }
)

READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclasses.dataclass
class RestFeatures:
    """The REST cost-feature schema — the authoritative contract for what a REST request is priced on.

    Serialized verbatim into the calibration log's `features` field, so these names are what
    operators regress against offline; treat renames as breaking changes to that dataset.
    """

    method: str
    limit: int | None = None
    depth: int = 0
    computed_fields: bool = False
    csv: bool = False
    filter_count: int = 0
    join_traversals: int = 0
    unindexable_lookups: int = 0
    lookups: list[str] = dataclasses.field(default_factory=list)  # e.g. ["name__ic", "location__name"]
    # When set, cost computation failed and the counting fields above were never populated.
    classification_error: bool = False
    kind: str = KIND_REST


def classify(request, weights):  # pylint: disable=unused-argument  # symmetric calculator signature
    """Extract cost features from a REST request — feature extraction only, no arithmetic."""
    params = request.GET
    features = RestFeatures(
        method=request.method,
        limit=_int_or_none(params.get("limit")),
        depth=_int_or_none(params.get("depth")) or 0,
        computed_fields="computed_fields" in params.get("include", ""),
        csv=params.get("format") == "csv",
    )

    for raw_key in params.keys():
        key = raw_key.strip()
        if key in NON_FILTER_PARAMS or not key:
            continue
        features.filter_count += 1
        segments = key.split("__")
        # If the last segment is a known lookup, peel it; what remains beyond the field name is
        # relation traversal (best-effort: real confirmation against the FilterSet happens
        # offline, from the recorded lookups).
        last = segments[-1]
        if last in UNINDEXABLE_LOOKUPS:
            features.unindexable_lookups += 1
            segments = segments[:-1]
        elif last in INDEXABLE_LOOKUPS:
            segments = segments[:-1]
        features.join_traversals += max(len(segments) - 1, 0)
        features.lookups.append(key)

    return features


def estimate(features, weights):
    """Pure (features, weights) -> cost for a REST request."""
    base = weights["rest_read_base"] if features.method in READ_METHODS else weights["rest_write_base"]
    cost = float(base)
    cost += features.join_traversals * weights["rest_per_join_surcharge"]
    cost += features.unindexable_lookups * weights["rest_unindexable_surcharge"]
    if features.limit:
        pages = math.ceil(features.limit / weights["rest_page_size_divisor"])
        cost *= max(pages, 1)
    if features.depth:
        cost *= 1 + features.depth * weights["rest_depth_multiplier_per_level"]
    if features.computed_fields:
        cost *= weights["rest_computed_fields_multiplier"]
    if features.csv:
        cost *= weights["rest_csv_multiplier"]
    return round(cost, 2)


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
