"""All Redis operations for rate-limiting budgets — a token's per-window allowance and its state.

This module is deliberately layer-agnostic: nothing here knows about limits or modes. The
enforcement layer only calls :func:`read`; the reporting layer only calls :func:`charge`. The
limit comparison happens in the middleware, keeping this store reusable by both.

Note this is a fixed-window counter, not the token-bucket algorithm — budgets don't refill
gradually; the key expires at the window boundary and the next request starts a fresh one.

Redis access uses the raw redis-py client from the django-redis pool already configured as
`CACHES["default"]` — the budget increment needs an atomic INCRBY-with-conditional-EXPIRE and
(later) the metrics collector needs SCAN, neither of which the Django cache API can express.
"""

from collections import namedtuple
import functools

from django_redis import get_redis_connection

BUDGET_KEY_PREFIX = "budget:"
# Global counter, exported as the nautobot_cost_total metric. Lives inside the budget: namespace
# for collision safety; anything SCANning budget:* for per-token keys must exclude this exact key.
COST_TOTAL_KEY = "budget:total"
DEFAULT_SCOPE = "default"

BudgetState = namedtuple("BudgetState", ["consumed", "reset_seconds"])

# INCRBY the budget, guarantee the (possibly just-recreated) key always carries a TTL so a budget
# can never stop resetting, and INCRBY the global cost counter — all in one atomic operation.
# A Lua script rather than INCR + EXPIRE NX because the NX flag requires Redis >= 7.0, which
# Nautobot does not pin, and a non-scripted pipeline is racy between the INCR and the TTL check.
# Returns {budget value, remaining TTL in seconds}.
_CHARGE_LUA = """
local consumed = redis.call('INCRBY', KEYS[1], ARGV[1])
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    ttl = tonumber(ARGV[2])
end
redis.call('INCRBY', KEYS[2], ARGV[1])
return {consumed, ttl}
"""


def get_client():
    """Return the raw redis-py client from the existing django-redis "default" connection pool."""
    return get_redis_connection("default")


@functools.cache
def _charge_script():
    """Register the charge Lua script once per process; the executing client is passed per call."""
    return get_client().register_script(_CHARGE_LUA)


def budget_key(token_hash, scope=DEFAULT_SCOPE):
    """Return the Redis key for a token's budget.

    The default scope maps to the unprefixed `budget:{hash}` key so external systems can derive
    it statelessly from the Authorization header alone. A future per-scope budget split (e.g.
    separate REST/GraphQL budgets) changes only the scope passed in, yielding
    `budget:{scope}:{hash}` keys, without touching the operations below.
    """
    if scope == DEFAULT_SCOPE:
        return f"{BUDGET_KEY_PREFIX}{token_hash}"
    return f"{BUDGET_KEY_PREFIX}{scope}:{token_hash}"


def read(token_hash, scope=DEFAULT_SCOPE):
    """Return the current BudgetState for a token — one pipelined round trip, no writes.

    `consumed` is None when the token has no live budget; `reset_seconds` is None when the
    key has no expiry (which the charge script guarantees cannot persist).
    """
    key = budget_key(token_hash, scope=scope)
    pipe = get_client().pipeline()
    pipe.get(key)
    pipe.ttl(key)
    consumed, ttl = pipe.execute()
    if consumed is None:
        return BudgetState(consumed=None, reset_seconds=None)
    return BudgetState(consumed=int(consumed), reset_seconds=ttl if ttl >= 0 else None)


def charge(token_hash, cost, window_seconds, scope=DEFAULT_SCOPE):
    """Atomically add `cost` to the token's budget and the global counter; return the new BudgetState."""
    consumed, ttl = _charge_script()(
        keys=[budget_key(token_hash, scope=scope), COST_TOTAL_KEY],
        args=[int(cost), int(window_seconds)],
        client=get_client(),
    )
    return BudgetState(consumed=int(consumed), reset_seconds=int(ttl))
