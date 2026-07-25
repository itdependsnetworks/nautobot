"""Rate-limiting middleware: per-token cost accounting and budget enforcement for API requests.

Placement: immediately after `CorsMiddleware` and before `SessionMiddleware` in
`MIDDLEWARE` — ahead of anything that can touch the database, so a denied request costs zero
SQL. It therefore never sees `request.user`: activation and accounting key on the raw
`Authorization` header (session-authenticated UI traffic, which carries no such header, passes
through untouched).

`__call__` is a thin orchestrator over methods each owned by exactly one delivery layer, so a
layer can be extracted or reverted by deleting its call line and methods:

- layer 3 (report):   :meth:`_charge_and_annotate` (+ the costing and budgets modules)
- layer 4 (enforce):  :meth:`_maybe_deny` / :meth:`_deny`
- layer 7 (calibrate): :meth:`_measure` / :meth:`_emit_calibration`

Failure posture is fail-open: if Redis is unreachable, accounting and enforcement are skipped,
the error is logged loudly, and the `nautobot_budget_errors` counter increments. Losing
fairness temporarily is preferable to a Redis blip becoming an API outage.
"""

import contextlib
import dataclasses
import functools
import hashlib
import json
import logging
import random
import time

from django.db import connections
from django.http import JsonResponse
from django.urls import reverse
from redis.exceptions import RedisError

from nautobot.core.rate_limiting import budgets, costing, metrics
from nautobot.core.rate_limiting.config import get_config, MODE_ENFORCE, MODE_OFF, VALID_MODES

logger = logging.getLogger(__name__)
calibration_logger = logging.getLogger("nautobot.core.rate_limiting.calibration")

HEADER_MODE = "X-Nautobot-Rate-Limit-Mode"
HEADER_COST = "X-Nautobot-Cost"
HEADER_LIMIT = "RateLimit-Limit"
HEADER_REMAINING = "RateLimit-Remaining"
HEADER_RESET = "RateLimit-Reset"


@functools.cache
def _get_api_path():
    """Return the REST API root path ("/api/"), resolved once per process (needs the URLconf loaded)."""
    return reverse("api-root")


class _QueryStats:
    """Database query counter/timer installed via `connection.execute_wrapper` (calibration only)."""

    __slots__ = ("count", "total_ms")

    def __init__(self):
        self.count = 0
        self.total_ms = 0.0

    def __call__(self, execute, sql, params, many, context):
        started = time.monotonic()
        try:
            return execute(sql, params, many, context)
        finally:
            self.count += 1
            self.total_ms += (time.monotonic() - started) * 1000.0


class RateLimitingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self._applies_to(request):
            return self.get_response(request)
        mode = self._effective_mode(request)
        if mode == MODE_OFF:
            # Capability semaphore: the header's presence says this Nautobot version supports rate
            # limiting; its value says it is not enabled for this request's kind. This disclosure
            # is deliberate (clients regulate themselves, so tell them the truth), not a leak.
            response = self.get_response(request)
            response[HEADER_MODE] = mode
            return response

        config = get_config()
        budget_hash = self._budget_hash(request)
        scope = self._budget_scope(request)
        start_wall = time.monotonic()
        start_cpu = time.process_time()

        denial = self._maybe_deny(request, budget_hash, scope, mode, config)  # layer 4
        if denial is not None:
            denial[HEADER_MODE] = mode
            return denial

        try:  # layer 3: cost is computed pre-execution, from the request shape alone
            cost, features = costing.cost(request)
        except Exception:
            logger.exception("Rate-limiting cost computation failed; falling back to a cost of 1")
            cost = 1
            features = costing.features_class(costing.request_kind(request))(
                method=request.method, classification_error=True
            )

        calibrate = self._should_calibrate(config)  # layer 7
        with self._measure(calibrate) as stats:  # layer 7
            response = self.get_response(request)

        self._charge_and_annotate(response, budget_hash, scope, cost, config)  # layer 3
        response[HEADER_MODE] = mode
        if calibrate:  # layer 7
            self._emit_calibration(request, response, features, cost, start_wall, start_cpu, stats, mode)
        return response

    @staticmethod
    def _applies_to(request):
        """Activate only for requests carrying an Authorization header bound for the API or GraphQL."""
        if not request.META.get("HTTP_AUTHORIZATION"):
            return False
        from nautobot.core.middleware import _GRAPHQL_PATHS

        return request.path_info.startswith(_get_api_path()) or request.path.rstrip("/") in _GRAPHQL_PATHS

    @staticmethod
    def _effective_mode(request):
        """Resolve MODE for this request's kind — the only place MODE is interpreted.

        A scalar applies to all kinds; a dict (e.g. `{"rest": "enforce", "graphql": "report"}`)
        resolves by kind with unmapped kinds treated as off. Unrecognized values are off.
        """
        mode = get_config()["MODE"]
        if isinstance(mode, dict):
            mode = mode.get(costing.request_kind(request), MODE_OFF)
        return mode if mode in VALID_MODES else MODE_OFF

    @staticmethod
    def _budget_hash(request):
        """Lowercase hex SHA-256 of the raw Authorization header value — deterministic and one-way."""
        return hashlib.sha256(request.META["HTTP_AUTHORIZATION"].encode("utf-8")).hexdigest()

    @staticmethod
    def _budget_scope(request):  # pylint: disable=unused-argument  # the request drives scope selection when a split is enabled
        """Return the budget scope for this request.

        v1 uses a single shared budget for all request kinds (a database second is a database
        second regardless of which API consumed it), so this is a constant. It exists as the seam
        for a future per-kind budget split, which would return the request kind here and read a
        per-scope limit — and change nothing else.
        """
        return budgets.DEFAULT_SCOPE

    def _maybe_deny(self, request, budget_hash, scope, mode, config):
        """Layer 4 in one method: return a 429 response, or None to admit the request.

        The check is against consumption that has already been recorded — a request is never
        rejected because it *would* exceed the remaining budget. The denied request is not added
        to the budget, so an over-limit consumer costs one Redis GET per request.
        """
        if mode != MODE_ENFORCE:
            return None
        try:
            state = budgets.read(budget_hash, scope=scope)
        except RedisError:
            self._record_fail_open("budget read")
            return None
        limit = int(config["LIMIT"])
        if state.consumed is not None and state.consumed >= limit and state.reset_seconds:
            return self._deny(state, limit)
        return None

    @classmethod
    def _deny(cls, state, limit):
        """Build the 429: DRF-style body, Retry-After from the budget's remaining TTL, all four headers."""
        response = JsonResponse(
            {"detail": "Request was throttled. Consumption budget exhausted for this token."},
            status=429,
        )
        response["Retry-After"] = str(state.reset_seconds)
        # The denied request is never priced or charged, so its cost is honestly zero.
        cls._inject_headers(response, cost=0, consumed=state.consumed, limit=limit, reset_seconds=state.reset_seconds)
        return response

    def _charge_and_annotate(self, response, budget_hash, scope, cost, config):
        """Layer 3 response phase in one method: record the cost and annotate the response."""
        try:
            state = budgets.charge(budget_hash, cost, int(config["WINDOW_SECONDS"]), scope=scope)
        except RedisError:
            self._record_fail_open("budget charge")
            # Degrade the contract rather than dropping it: cost and limit don't need Redis;
            # the two accounting-derived headers report the documented -1 sentinel.
            self._inject_headers(response, cost, None, int(config["LIMIT"]), None)
            return None
        self._inject_headers(response, cost, state.consumed, int(config["LIMIT"]), state.reset_seconds)
        return state

    @staticmethod
    def _should_calibrate(config):
        """Layer 7: decide whether this request emits a calibration record (sampling)."""
        if not config["CALIBRATION_LOG"]:
            return False
        return random.random() < float(config["CALIBRATION_SAMPLE_RATE"])  # noqa: S311  # sampling, not cryptography

    @staticmethod
    def _inject_headers(response, cost, consumed, limit, reset_seconds):
        """Set the four contract headers; None for consumed/reset means accounting is unavailable
        (Redis fail-open) and is reported as the documented -1 sentinel."""
        response[HEADER_COST] = str(cost)
        response[HEADER_LIMIT] = str(limit)
        response[HEADER_REMAINING] = str(max(0, limit - consumed)) if consumed is not None else "-1"
        response[HEADER_RESET] = str(reset_seconds) if reset_seconds is not None else "-1"

    @staticmethod
    @contextlib.contextmanager
    def _measure(enabled):
        """Layer 7: count and time database queries during the view, without needing DEBUG.

        Yields zeroed stats without installing anything when calibration is disabled, so no other
        code path pays for or depends on measurement.
        """
        stats = _QueryStats()
        if not enabled:
            yield stats
            return
        with contextlib.ExitStack() as stack:
            for alias in connections:
                stack.enter_context(connections[alias].execute_wrapper(stats))
            yield stats

    @classmethod
    def _emit_calibration(cls, request, response, features, cost, start_wall, start_cpu, stats, mode):
        """Layer 7: one structured JSON record pairing the assigned cost with measured reality.

        Measured values are never fed back into cost at runtime; they are the offline regression
        dataset that sets the heuristic weights and gates per-kind enforcement (cost parity).
        """
        try:
            record = {
                "token_hash": cls._budget_hash(request),
                "method": request.method,
                "path": request.path,
                "view": getattr(getattr(request, "resolver_match", None), "view_name", None),
                "status": response.status_code,
                "features": dataclasses.asdict(features),
                "assigned_cost": cost,
                "wall_ms": round((time.monotonic() - start_wall) * 1000.0, 2),
                "cpu_ms": round((time.process_time() - start_cpu) * 1000.0, 2),
                "actual_db_ms": round(stats.total_ms, 2),
                "actual_db_queries": stats.count,
                "mode": mode,
            }
            calibration_logger.info(json.dumps(record, default=str))
        except Exception:
            logger.exception("Rate-limiting calibration record emission failed")

    @staticmethod
    def _record_fail_open(operation):
        logger.exception(
            "Redis unavailable during rate-limiting %s; failing open (no accounting or enforcement for this request)",
            operation,
        )
        metrics.record_budget_error()
