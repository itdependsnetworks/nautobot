"""API rate limiting: per-token cost accounting and budget enforcement for REST and GraphQL.

This package is deliberately import-light at the top level: `nautobot.core.settings` imports
`nautobot.core.rate_limiting.config` at settings-load time, so nothing here may import Django
apps, models, or third-party clients. Import the individual modules directly instead:

- `config` — the `RATE_LIMITING` defaults and merged-settings access
- `costing` — the classify -> estimate -> cost pipeline (dispatch, weights, FLAT_WEIGHTS)
- `rest_cost` / `graphql_cost` — the per-kind cost calculators
- `budgets` — all Redis budget operations
- `middleware` — the `RateLimitingMiddleware` orchestrator
- `metrics` — Prometheus error counter (full collector arrives with the metrics layer)
"""
