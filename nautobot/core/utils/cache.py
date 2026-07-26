"""Utilities for conveniently working with the Django/Redis cache."""

import logging
import time

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


class ProcessTTLCache:
    """
    A small in-process TTL cache for values that are read once per serialized object in hot code paths.

    A Django-cache-backed value costs a cache-backend (Redis) round-trip per read; when a REST API list
    response reads the same value for every row, those round-trips dominate. This wraps such reads with a
    short-lived process-local memo: staleness is bounded by `ttl` seconds (choose it to match — or be
    stricter than — the staleness the underlying value already tolerates), and correctness across worker
    processes is unchanged because each process re-reads at most `ttl` seconds later.

    Entries beyond `maxsize` trigger a purge of expired entries (and a full clear as a last resort), so
    per-instance keys can't grow the memo without bound.
    """

    # All instances, so the test harness can clear them between tests (a memo surviving into the next
    # test would make query-count assertions timing-dependent).
    instances = []

    def __init__(self, ttl, maxsize=4096):
        self.ttl = ttl
        self.maxsize = maxsize
        self._data = {}
        ProcessTTLCache.instances.append(self)

    @classmethod
    def clear_all(cls):
        for instance in cls.instances:
            instance.clear()

    def get_or_set(self, key, compute):
        """Return the memoized value for `key`, calling `compute()` (and storing its result) on miss/expiry."""
        now = time.monotonic()
        entry = self._data.get(key)
        if entry is not None and entry[1] > now:
            return entry[0]
        value = compute()
        if len(self._data) >= self.maxsize:
            self._data = {k: v for k, v in self._data.items() if v[1] > now}
            if len(self._data) >= self.maxsize:
                self._data.clear()
        self._data[key] = (value, now + self.ttl)
        return value

    def pop(self, key):
        self._data.pop(key, None)

    def clear(self):
        self._data.clear()


def construct_cache_key(obj, *, method_name=None, branch_aware=True, **params):
    """
    Construct a consistently-structured Django/Redis cache key for the given obj and/or method name.

    Args:
        obj (Any): A model class, model instance, model manager, class, or function that will make use of the cache.
        method_name (str): Name of a specific method on `obj`. May be omitted only if `obj` is itself a function.
        branch_aware (bool): Whether this cache key needs to vary by branch when Version Control is enabled.
        **params (dict): Parameters that should further narrow the scope of the cache key.

    Examples:
        >>> construct_cache_key(Location.objects, method_name="max_depth")
        'nautobot.dcim.location.max_depth'
        >>> construct_cache_key(MinMaxValidationRule, method_name="get_for_model")
        'nautobot.data_validation.minmaxvalidationrule.get_for_model'
        >>> construct_cache_key(MinMaxValidationRule, method_name="get_for_model", content_type="dcim.location")
        'nautobot.data_validation.minmaxvalidationrule.get_for_model(content_type=dcim.location)'
        >>> construct_cache_key(CustomField.objects, method_name="get_for_model", model="dcim.location", exclude_filter_disabled=True, listing=True)
        'nautobot.extras.customfield.get_for_model(model=dcim.location,exclude_filter_disabled=True,listing=True)'
        >>> from nautobot.extras.utils import change_logged_models_queryset
        >>> construct_cache_key(change_logged_models_queryset)
        'nautobot.extras.utils.change_logged_models_queryset'
    """
    method_name_must_be_set = True
    if isinstance(obj, models.Model):
        tokens = ["nautobot", obj._meta.concrete_model._meta.label_lower, str(obj.pk), method_name]
    elif isinstance(obj, models.Manager):
        tokens = ["nautobot", obj.model._meta.concrete_model._meta.label_lower, method_name]
    elif isinstance(obj, type):
        # A class object
        if issubclass(obj, models.Model):
            tokens = ["nautobot", obj._meta.concrete_model._meta.label_lower, method_name]
        elif issubclass(obj, models.Manager):
            tokens = ["nautobot", obj.model._meta.concrete_model._meta.label_lower, method_name]
        else:
            tokens = [obj.__module__, obj.__name__, method_name]
    elif method_name is not None:
        # An instance of any class not specifically handled above
        tokens = [obj.__module__, obj.__class__.__name__, method_name]
    else:
        # A standalone function
        tokens = [obj.__module__, obj.__name__]
        method_name_must_be_set = False

    if method_name_must_be_set and method_name is None:
        raise ValueError("method_name must be specified for the given obj")

    if branch_aware and "nautobot_version_control" in settings.PLUGINS:
        from nautobot_version_control.utils import active_branch  # pylint: disable=import-error

        tokens += ["branch", active_branch()]

    cache_key = ".".join(tokens)

    params_tokens = [f"{key}={value}" for key, value in params.items()]
    if params_tokens:
        cache_key += f"({','.join(params_tokens)})"

    # Disabled as it's very noisy in some cases
    # logger.debug("Constructed cache key is %s", cache_key)
    return cache_key
