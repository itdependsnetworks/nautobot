"""Prometheus instrumentation for API rate limiting.

This module currently owns only the fail-open error counter. The full collector (bucket gauges and
the global cost counter, read from Redis at scrape time) arrives with the metrics layer.

The error counter is deliberately a per-process `prometheus_client` counter rather than a Redis
key: it is incremented precisely when Redis is unavailable. Per-process counters aggregate
correctly at scrape time under multi-worker deployments via the standard Prometheus multiprocess
directory environment variable.
"""

# prometheus_client ships with Nautobot via django-prometheus. Guarded so a packaging surprise
# degrades instrumentation instead of breaking every request.
try:
    from prometheus_client import Counter

    METRICS_AVAILABLE = True
except ImportError:  # pragma: no cover
    METRICS_AVAILABLE = False

if METRICS_AVAILABLE:
    budget_errors = Counter(
        "nautobot_budget_errors",
        "Errors (typically Redis unavailability) that caused rate-limiting accounting or "
        "enforcement to be skipped (fail-open).",
    )


def record_budget_error():
    """Increment the fail-open error counter, if instrumentation is available."""
    if METRICS_AVAILABLE:
        budget_errors.inc()
