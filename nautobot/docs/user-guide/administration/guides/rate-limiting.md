# Rate Limiting

+++ 3.3.0

Nautobot can account for — and optionally limit — the work that token-authenticated REST and GraphQL API requests consume. Every such request is assigned a **cost** computed from the request shape alone (URL parameters, body, GraphQL document — never a database query), drawn down from a per-token budget stored in Redis. Clients see their consumption on every response and can regulate themselves; when enforcement is enabled, a token that has exhausted its budget receives an immediate `429` before any database work is performed.

Session-authenticated (UI) traffic carries no `Authorization` header and is exempt. Accounting is strictly per token: a user with several tokens holds several budgets.

Rollback at any point is setting `MODE` to `"off"`.

## Configuration

All configuration lives in the single [`RATE_LIMITING`](../configuration/settings.md#rate_limiting) dict in `nautobot_config.py`. Keys you omit fall back to the shipped defaults, so you only ever state what you're changing:

```python
# The complete dict with its default values:
RATE_LIMITING = {
    "MODE": "off",                  # "off" | "report" | "enforce", or per-kind (see below)
    "WINDOW_SECONDS": 60,           # budget window length
    "LIMIT": 1000,                  # cost points per token per window
    "HEURISTIC_WEIGHTS": {},        # overrides merged over the shipped weights (see table below)
    "CALIBRATION_LOG": False,       # structured cost-vs-reality records (see below)
    "CALIBRATION_SAMPLE_RATE": 1.0, # fraction of requests to log when calibration is on
}
```

Typical progressions, each a complete valid config:

```python
# Step 1 — observe. Costs and headers on every response, nothing ever denied,
# and a calibration record per request so you can pick a LIMIT from real data:
RATE_LIMITING = {"MODE": "report", "CALIBRATION_LOG": True}

# Step 2 — enforce REST once its costs are trusted; GraphQL keeps calibrating:
RATE_LIMITING = {
    "MODE": {"rest": "enforce", "graphql": "report"},
    "LIMIT": 3000,
    "CALIBRATION_LOG": True,
}

# Alternative — plain request-rate limiting, no cost heuristic:
# the FLAT_WEIGHTS preset makes every request cost 1, so LIMIT is simply "requests per window".
from nautobot.core.rate_limiting.costing import FLAT_WEIGHTS

RATE_LIMITING = {"MODE": "enforce", "LIMIT": 300, "WINDOW_SECONDS": 60, "HEURISTIC_WEIGHTS": FLAT_WEIGHTS}

# Tuning individual heuristic weights after reviewing calibration data:
RATE_LIMITING = {
    "MODE": "report",
    "HEURISTIC_WEIGHTS": {"rest_unindexable_surcharge": 8.0, "graphql_default_page": 20},
}
```

## The rate-limiting contract

Every token-authenticated API response — in **all** modes, including `off` — carries a capability semaphore:

```no-highlight
X-Nautobot-Rate-Limit-Mode: off   # or "report" / "enforce"
```

Its presence tells a client this Nautobot version supports rate limiting; its value tells them whether (and how) it applies to this request's kind — during a per-kind rollout, a REST response may say `enforce` while a GraphQL response says `report`. Clients and tooling should use this header, not version sniffing, for discovery.

!!! note "Disclosing the mode is deliberate, not a security risk"
    The whole design premise is that clients regulate themselves, which requires telling them the truth about whether limiting is active. The header reveals nothing sensitive — no limits, no consumption, no identity and an attacker would already have access and see the headers returned, this simply saves a redundant version lookup on each request.

In `report` and `enforce` modes, responses additionally carry the four accounting headers:

```no-highlight
X-Nautobot-Cost: 14      # cost of this request
RateLimit-Limit: 1000    # budget per window
RateLimit-Remaining: 862
RateLimit-Reset: 37      # seconds until this token's window expires
```

!!! info "Why the mixed header names?"
    The split is deliberate: **standard names for standard semantics, vendor prefix for vendor semantics.** `RateLimit-Limit`/`-Remaining`/`-Reset` follow the IETF rate-limit headers draft, so off-the-shelf client libraries can act on them without reading Nautobot's documentation. Cost points and the mode semaphore are Nautobot inventions with no standard meaning, so they carry the `X-Nautobot-` prefix — naming them `RateLimit-Cost` or `RateLimit-Mode` would squat on a namespace the IETF is still standardizing (risking a future collision that breaks this contract) and would be swept up by client libraries that prefix-match `RateLimit-*` headers they don't actually understand.

The budget window is anchored to the token's *first* request in it (the countdown runs from there), and resets when it expires — so on every request after the first, `RateLimit-Reset` is less than the full window length.

If accounting is temporarily unavailable (see the fail-open note below), `RateLimit-Remaining` and `RateLimit-Reset` are reported as `-1` — a documented "unknown" sentinel — while `X-Nautobot-Cost` and `RateLimit-Limit`, which don't depend on Redis, remain accurate. Clients should treat `-1` as "do not self-regulate on this value right now."

One rule governs the limit check: **it only counts consumption already recorded — the current request's cost is never part of the deny decision.** A request admitted under the limit always completes, and its cost is added afterward, even if that pushes the budget past the limit.

!!! important "Budgets bound work per window, not simultaneous requests"
    N parallel requests that all start under the limit all run; the budget catches up afterward. Size limits to the work your deployment can absorb within one window, keep the window short, and treat the web worker pool as the concurrency cap.

## How cost is computed

Cost approximates the database work a request will cause, judged from its shape alone. Every weight below is overridable via `HEURISTIC_WEIGHTS`; the shipped values are deliberately provisional starting points, meant to be replaced with values calibrated from your own traffic (see [Calibration logging](#calibration-logging)).

### REST requests

| Weight key | Default | What it prices |
|---|---|---|
| `rest_read_base` | 1.0 | Base cost of a `GET`/`HEAD`/`OPTIONS` request |
| `rest_write_base` | 3.0 | Base cost of any write method |
| `rest_page_size_divisor` | 50 | Requested page size: cost is multiplied by `ceil(limit / 50)` — asking for 200 records costs 4× asking for 50 |
| `rest_depth_multiplier_per_level` | 1.0 | `?depth=N` nested serialization: cost is multiplied by `(1 + N)` |
| `rest_per_join_surcharge` | 1.0 | Added once per **relation traversal** in a filter (see below) |
| `rest_unindexable_surcharge` | 5.0 | Added once per **non-indexable lookup** in a filter (see below) |
| `rest_computed_fields_multiplier` | 3.0 | `include=computed_fields` — computed fields execute per returned object |
| `rest_csv_multiplier` | 3.0 | `format=csv` — a full, unpaginated render |

**Relation traversals** are filter keys that cross a relationship using `__`, such as `?location__name=dc1` — each hop is a SQL JOIN the database must perform, so each one adds `rest_per_join_surcharge`.

**Non-indexable lookups** are filter suffixes the database cannot satisfy with a B-tree index, forcing it to scan and test every candidate row — on a large table these are among the most expensive requests Nautobot serves. Each one adds `rest_unindexable_surcharge`. The recognized suffixes are the Django forms `icontains`, `contains`, `iregex`, `regex`, `iendswith`, `endswith` and Nautobot's short filter forms `ic`, `nic` (contains), `ie`, `nie` (case-insensitive exact), `iew`, `niew` (ends-with), and `re`, `nre`, `ire`, `nire` (regex). Index-friendly suffixes (`exact`, `in`, `gt`, `isnull`, `startswith`, ...) carry no surcharge — anchored prefix matches *can* use an index, which is why `startswith` is cheap while `endswith` is not.

A worked example:

```no-highlight
GET /api/dcim/devices/?location__name__ic=dc1&limit=200&depth=2

base (read)                          1.0
+ 1 relation traversal (location__)  + 1.0
+ 1 non-indexable lookup (__ic)      + 5.0
                                     = 7.0
× page size  ceil(200 / 50) = 4      = 28.0
× depth      (1 + 2)                 = 84.0

X-Nautobot-Cost: 84
```

The same query filtered with `location__name=dc1` (exact match, indexable) and `limit=50&depth=0` would cost 2 — the heuristic's entire purpose is that spread.

### GraphQL requests

GraphQL costing statically analyzes the query document (it is parsed, never executed) and estimates the number of objects the query will touch, GitHub/Shopify-style: each list field multiplies its parent's count by its `first`/`last`/`limit` argument, or by an assumed page size when none is given.

| Weight key | Default | What it prices |
|---|---|---|
| `graphql_default_page` | 50 | Assumed fan-out for a list field with no `first`/`last`/`limit` argument |
| `graphql_node_divisor` | 100 | Cost is `estimated_nodes / 100` |
| `graphql_floor` | 5.0 | Minimum GraphQL cost; also charged when the query doesn't parse |

```no-highlight
query {
  locations(first: 10) {            # 10 nodes
    devices(first: 100) {           # 10 × 100 = 1,000 nodes
      id name
    }
  }
}

estimated_nodes = 1 + 10 + 1000 = 1011
cost = max(5.0, 1011 / 100) = 10.11  →  X-Nautobot-Cost: 11
```

Note what the unbounded version of that query costs: with no `first` arguments, both levels assume the default page of 50, estimating 1 + 50 + 2,500 nodes → cost 26. Clients are thereby nudged toward explicit, small page arguments.

!!! note
    The AST alone cannot distinguish a to-one relation (`device { location { name } }`) from a list, so v1 conservatively assumes list fan-out for any nested selection without a page argument. This overprices relation-heavy queries; calibration data is how the weights get corrected.

### Flat costing

Setting `HEURISTIC_WEIGHTS` to the importable `FLAT_WEIGHTS` preset makes every request cost exactly 1 regardless of shape, making `LIMIT` a plain "requests per window" ceiling. Same machinery, same headers, same metrics, no dedicated code path — use it for conventional request-rate limiting without reasoning about cost, or as a stepping stone before adopting the heuristic.

## Reporting

`MODE: "report"` computes costs, records them, and emits the headers on every response (including errors) — it never denies. This is the mandated first rollout step: run it long enough to see real consumption before choosing a `LIMIT`. A reasonable starting point is your busiest legitimate token's observed per-window consumption plus comfortable headroom.

## Enforcement

`MODE: "enforce"` activates the deny path: once a token's recorded consumption reaches `LIMIT` within the current window, further requests receive `429` with a `Retry-After` header equal to the window's remaining seconds, a standard error body, and all four rate-limit headers — with zero SQL executed. The denied request is not added to the budget, so an over-limit consumer hammering the API costs one Redis read per request.

`MODE` may also be set per request kind:

```python
RATE_LIMITING = {
    "MODE": {"rest": "enforce", "graphql": "report"},
    "LIMIT": 3000,
}
```

This is the expected rollout shape: the REST heuristic is more direct and will be trustworthy sooner, while GraphQL costing keeps calibrating in report mode against the same shared budget. Do not enable `enforce` for a kind until its calibration data shows its costs track measured database time comparably to the already-enforced kind (cost parity) — otherwise one kind's mispriced requests distort the shared budget.

!!! note "Failure posture: fail-open"
    If Redis is unreachable, accounting and enforcement are skipped, the error is logged, and the `nautobot_budget_errors` metric increments. Responses still carry `X-Nautobot-Cost` and `RateLimit-Limit`, with `RateLimit-Remaining` and `RateLimit-Reset` set to the `-1` sentinel. Enforcement resumes without intervention when Redis returns. Losing fairness temporarily is preferable to a Redis blip becoming an API outage.

Fixed windows permit up to 2× the limit straddling a window boundary; set limits with this in mind.

## Calibration logging

`CALIBRATION_LOG: True` makes the middleware emit one structured JSON record per request (sampled by `CALIBRATION_SAMPLE_RATE`) to the logger `nautobot.core.consumption.calibration`, pairing the assigned cost with measured reality. Measured values are never fed back into cost at runtime — they are the offline dataset for calibrating `HEURISTIC_WEIGHTS`.

Each record looks like this (one JSON object per line):

```json
{
    "token_hash": "3f5a9c0e8b...",
    "method": "GET",
    "path": "/api/dcim/devices/",
    "view": "dcim-api:device-list",
    "status": 200,
    "features": {
        "kind": "rest",
        "method": "GET",
        "limit": 200,
        "depth": 0,
        "computed_fields": false,
        "csv": false,
        "filter_count": 1,
        "join_traversals": 0,
        "unindexable_lookups": 1,
        "lookups": ["name__ic"]
    },
    "assigned_cost": 24,
    "wall_ms": 181.4,
    "cpu_ms": 92.3,
    "actual_db_ms": 63.7,
    "actual_db_queries": 9,
    "mode": "report"
}
```

| Field | Meaning |
|---|---|
| `token_hash` | Same SHA-256 hash used in the Redis budget key — joinable against metrics, never the raw token |
| `view` | The resolved view name, so residuals can be grouped per endpoint |
| `features` | The exact heuristic inputs the cost was computed from (GraphQL records `parse_ok`, `max_depth`, `field_count`, `estimated_nodes` instead) |
| `assigned_cost` | What the request was charged |
| `wall_ms` / `cpu_ms` | Total request wall-clock and process CPU time |
| `actual_db_ms` / `actual_db_queries` | Measured database time and query count for this request (measured via Django's query instrumentation — no `DEBUG` required, negligible overhead, only active while calibration logging is on) |

!!! warning "Filter flagged records before regressing"
    Records with `features.classification_error` set had cost computation fail (they were charged a fallback) — their counting fields are placeholder zeros, not measurements; exclude them from weight calibration.

Route the logger to your log pipeline as JSON lines:

```python
LOGGING = {
    ...
    "handlers": {
        "consumption_jsonl": {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": "/var/log/nautobot/consumption.jsonl",
        },
    },
    "loggers": {
        "nautobot.core.consumption.calibration": {"handlers": ["consumption_jsonl"], "level": "INFO"},
    },
}
```

What to do with the data:

- **Set `LIMIT`**: sum `assigned_cost` per `token_hash` per window; pick a limit above your busiest legitimate consumer.
- **Calibrate weights**: regress `actual_db_ms` against the recorded features — the coefficients are your calibrated `HEURISTIC_WEIGHTS`. A quick sketch with pandas: `pd.read_json("consumption.jsonl", lines=True)`, flatten `features`, fit `actual_db_ms` against the priced features.
- **Find mispriced shapes**: sort by `actual_db_ms / assigned_cost`. A request costed at 5 that took 2.5 seconds of database time is exactly what this log exists to surface — its `features` and `view` tell you which weight (or missing feature) to fix.
- **Check cost parity before per-kind enforcement**: compare the `actual_db_ms / assigned_cost` distribution for `features.kind == "rest"` vs `"graphql"`. Enabling `enforce` for a kind whose ratio runs far from the other's means the shared budget treats the two currencies unequally.

## External systems

Two properties make this feature composable with infrastructure outside Nautobot:

- **The consumer identity is derivable statelessly.** The budget key is `budget:` followed by the lowercase hex SHA-256 of the raw `Authorization` header value. Any device that sees the same header can compute the same key — no lookup against Nautobot, no shared secret — and because the hash is one-way, the raw token appears nowhere in Redis, logs, metrics, or the external device's own tables.
- **Consumption is published, pull-only.** The `/metrics` endpoint exposes per-token budget levels (`nautobot_budget_consumed{token_hash=...}`) and a global cost counter (`nautobot_cost_total`) read straight from Redis, so external systems observe demand by scraping — no push integration, no delivery guarantees to manage.

### Enforcing at the edge (example: F5)

Nautobot's own 429s are already nearly free (one Redis read, zero SQL), but a load balancer can do two things Nautobot deliberately won't:

- **Stop over-limit traffic before it consumes a connection at all.** An aggressive client retrying into a 429 still occupies an accept queue slot and a worker for the Redis read; the edge can absorb that instead.
- **Smooth instead of reject.** Holding a request while a budget window resets is the rejected server-side-delay pattern *inside* Nautobot (a sleeping request holds a uWSGI worker — the scarcest resource), but at the load balancer waiting is cheap. Operators who prefer queueing to 429s implement it at the edge.

The simplest integration doesn't even require key derivation: honor Nautobot's answers. When a response comes back `429`, remember that client's `Authorization` hash for `Retry-After` seconds and answer subsequent requests from the edge directly. An illustrative iRule sketch:

```tcl
when HTTP_REQUEST {
    set auth [HTTP::header "Authorization"]
    if { $auth ne "" } {
        # Same identity Nautobot budgets by: SHA-256 of the raw header value.
        set consumer [b64encode [sha256 $auth]]
        set holdoff [table lookup -notouch "nautobot_throttle_$consumer"]
        if { $holdoff ne "" } {
            HTTP::respond 429 content {{"detail": "Over consumption budget."}} \
                "Retry-After" $holdoff "Content-Type" "application/json"
            return
        }
    }
}
when HTTP_RESPONSE {
    if { [HTTP::status] == 429 } {
        set holdoff [HTTP::header "Retry-After"]
        table set "nautobot_throttle_$consumer" $holdoff indef $holdoff
    }
}
```

Because the edge keys its table on the same hash Nautobot uses, its decisions correlate one-to-one with Nautobot's `nautobot_budget_consumed{token_hash=...}` series and with the `token_hash` field in the calibration log — you can always answer "which consumer is the edge holding, and what does Nautobot's accounting say about them?" with a join on the hash. A more ambitious edge policy (its own token-keyed rate class, queue-and-release smoothing via a `Retry-After`-informed delay) builds on the same two ingredients: the derivable hash for identity, the response headers for state.

!!! warning
    Keep Nautobot's enforcement on even when the edge enforces. The edge sees only traffic that flows through it; direct access, a second ingress path, or a misconfigured pool bypasses it silently. Nautobot's 429 is the backstop that makes the published contract true regardless of path.

### Autoscaling on demand (example: Kubernetes)

CPU is a lagging, noisy proxy for API pressure — a burst of expensive requests queues work long before pod CPU averages catch up. The global cost rate is a direct demand signal, in the same currency as the budgets: `rate(nautobot_cost_total[5m])` is the cost-points-per-second the deployment is actually serving, aggregated correctly across all workers because the counter lives in Redis, not per-process.

Calibration data gives the capacity side of the equation: if reports show one Nautobot pod comfortably serves ~500 cost points per minute, scale before pods approach it. With [KEDA](https://keda.sh)'s Prometheus scaler:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: nautobot-cost-rate
spec:
  scaleTargetRef:
    name: nautobot
  minReplicaCount: 3
  maxReplicaCount: 12
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus.monitoring:9090
        # Cost points served per minute, fleet-wide.
        query: sum(rate(nautobot_cost_total[5m])) * 60
        # Target per-replica load; KEDA divides query by threshold to size the fleet.
        threshold: "400"
```

The same shape works with prometheus-adapter feeding a native HPA external metric.

One operational distinction worth internalizing: **scale on broad demand, throttle the outlier.** Before raising `maxReplicaCount` because cost rate is pegged, check `nautobot_budget_consumed` — if the demand is one token burning its budget, that's what enforcement (or a conversation with that automation's owner) is for; autoscaling in response would spend infrastructure absorbing traffic the contract says to reject. If consumption is spread across many tokens all comfortably under their limits, that's genuine organic growth — scale.
