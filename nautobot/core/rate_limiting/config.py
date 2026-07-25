"""Configuration access for API rate limiting.

All operator-facing knobs live in a single `RATE_LIMITING` dict in `nautobot_config.py`.
Operators may override any subset of its keys; :func:`get_config` merges the shipped defaults
underneath the operator's value so a partial override never removes a knob.

This module must stay import-light (stdlib and `django.conf` only): it is imported by
`nautobot.core.settings` at settings-load time.
"""

from django.conf import settings

MODE_OFF = "off"
MODE_REPORT = "report"
MODE_ENFORCE = "enforce"
VALID_MODES = frozenset({MODE_OFF, MODE_REPORT, MODE_ENFORCE})

KIND_REST = "rest"
KIND_GRAPHQL = "graphql"

RATE_LIMITING_DEFAULTS = {
    # "off" | "report" | "enforce", applying to all request kinds; or a per-kind mapping such as
    # {"rest": "enforce", "graphql": "report"}, with unmapped kinds treated as "off".
    "MODE": MODE_OFF,
    # Length of each token's budget window. The window is anchored to the token's first request
    # (the Redis key's TTL); expiry is the reset.
    "WINDOW_SECONDS": 60,
    # Budget per token per window, in cost points. Enforcement denies once *already-recorded*
    # recorded consumption reaches this value.
    "LIMIT": 1000,
    # Overrides merged over the shipped heuristic weight defaults; see the *_DEFAULT_WEIGHTS
    # dicts in nautobot.core.rate_limiting (rest_cost, graphql_cost, costing) for the available
    # keys, and costing.FLAT_WEIGHTS for the flat requests-per-window preset.
    "HEURISTIC_WEIGHTS": {},
    # When True, emit one structured JSON record per request to the
    # "nautobot.core.rate_limiting.calibration" logger, pairing the assigned cost with measured
    # wall-clock/CPU/database time so the heuristic weights can be regressed offline.
    "CALIBRATION_LOG": False,
    # Per-request sampling probability (0.0-1.0) for the calibration log.
    "CALIBRATION_SAMPLE_RATE": 1.0,
}


def get_config():
    """Return the effective RATE_LIMITING configuration (shipped defaults merged under operator overrides)."""
    return {**RATE_LIMITING_DEFAULTS, **getattr(settings, "RATE_LIMITING", {})}
