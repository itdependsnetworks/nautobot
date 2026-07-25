"""Helper code for loading values that may be defined in settings.py/nautobot_config.py *or* in django-constance."""

import contextlib
from functools import lru_cache
import logging

from constance import config
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import OperationalError, ProgrammingError

from nautobot.core.choices import NautobotEditionChoices
from nautobot.core.utils.otel import traced_span

logger = logging.getLogger(__name__)


# In-process memo for get_settings_or_config_memoized(), keyed by variable name. Cleared per-key by the
# config_updated / setting_changed signal receivers in nautobot.core.signals.
_settings_or_config_memo = {}


def get_settings_or_config_memoized(variable_name, fallback=None):
    """
    In-process memoized variant of `get_settings_or_config`, for values read per-object in hot code paths.

    A Constance-backed value normally costs a cache-backend (Redis) round-trip per read, which is
    prohibitive when read once per serialized object. The memo is cleared when the variable changes via
    Constance or `override_settings` *in this process* (see `nautobot.core.signals`); other worker
    processes retain their memoized value until they observe a change themselves or restart.

    Only use this for variables that already accept that staleness model — e.g. the natural-key-shaping
    flags such as `LOCATION_NAME_AS_NATURAL_KEY`, whose derived values are cached with the same
    invalidation semantics. Do not use it for values that must propagate promptly to all workers.
    """
    try:
        return _settings_or_config_memo[variable_name]
    except KeyError:
        value = get_settings_or_config(variable_name, fallback=fallback)
        _settings_or_config_memo[variable_name] = value
        return value


def get_settings_or_config(variable_name, fallback=None):
    """
    Get a value from Django settings (if specified there) or Constance configuration (otherwise).

    The fallback value is returned *only* if the requested variable cannot be found at all - this is an error case,
    and will generate warning logs.
    """
    # Explicitly set in settings.py or nautobot_config.py takes precedence, for now
    if hasattr(settings, variable_name):
        return getattr(settings, variable_name)
    # django-constance 4.x removed some built-in error handling here, so we have to do it ourselves now
    with traced_span(
        "nautobot.core.config",
        "constance_config.get",
        **{"constance_config.key": variable_name},
    ):
        with contextlib.suppress(ObjectDoesNotExist, OperationalError, ProgrammingError):
            return getattr(config, variable_name)
    logger.warning(
        'Configuration "%s" is not in settings, and could not read from the Constance database table '
        "(perhaps not initialized yet?)",
        variable_name,
    )
    if variable_name in settings.CONSTANCE_CONFIG:
        default = settings.CONSTANCE_CONFIG[variable_name][0]
        logger.warning('Using default value of "%s" from Constance configuration for "%s"', default, variable_name)
        return default
    logger.warning(
        'Constance configuration does not include an entry for "%s" - must return %s', variable_name, fallback
    )
    return fallback


@lru_cache(maxsize=None)
def get_nautobot_edition():
    """Return the active Nautobot edition: the highest-weighted `nautobot_edition` declared by any installed app."""
    current_edition = NautobotEditionChoices.COMMUNITY
    editions_by_weight = NautobotEditionChoices.WEIGHTS
    for app_config in apps.get_app_configs():
        app_edition = getattr(app_config, "nautobot_edition", None)
        if app_edition in editions_by_weight and editions_by_weight[app_edition] > editions_by_weight[current_edition]:
            current_edition = app_edition
    return current_edition
