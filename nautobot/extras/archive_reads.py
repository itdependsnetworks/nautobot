"""
Resolving a read against one period of retained history.

The storage side lives in `nautobot.extras.models.archive`; this is everything a request goes through to
land on it. A read resolves against warm storage or against exactly one retained period, never both and
never several, which is what keeps ordering and pagination behaving as they do for a warm read.

Kept apart from the models so the read path can be followed without reading six model definitions first,
and so a caller that only needs to resolve a period does not import the mirrors to get it.
"""

from django.db import models

from nautobot.core.constants import COLD_STORAGE_PERMISSION
from nautobot.extras.models.archive import (
    archive_model_for,
    ArchiveSegment,
)


def requested_archive_period(request):
    """
    The retention period a request asked for, or None.

    A non-filter query parameter on purpose. As a filterset filter it would be captured into SavedViews
    and the filter form, so a saved view would keep reaching retained history after the operator revoked
    the permission. This way the check happens in exactly one place per request.
    """
    if request is None:
        return None
    params = getattr(request, "query_params", None)
    if params is None:
        params = getattr(request, "GET", {})
    value = params.get("archive_period")
    return value or None


def user_can_read_archive(user):
    """
    Whether `user` holds the single cold-storage permission.

    One grant covering retained history across every covered model, rather than one per model: the default
    view permission on the period registry.
    """
    return bool(user and user.is_authenticated and user.has_perm(COLD_STORAGE_PERMISSION))


def get_archive_periods(model, user):
    """
    The periods offered in the period selector for `model`, newest first.

    Empty when retention is off, the model has no mirror, or the user lacks the cold-storage permission --
    so a caller can render the selector from this alone without repeating the checks.
    """
    from nautobot.core.utils.config import get_settings_or_config

    if not get_settings_or_config("CHANGELOG_ARCHIVE_ENABLED", fallback=False):
        return ArchiveSegment.objects.none()
    if archive_model_for(model) is None:
        return ArchiveSegment.objects.none()
    if not user_can_read_archive(user):
        return ArchiveSegment.objects.none()
    return ArchiveSegment.objects.filter(model_label=model._meta.label_lower).order_by("-period_key")


def get_archive_segment(model, period_key, user):
    """
    Resolve one requested period, or raise.

    `PermissionDenied` when the user cannot reach retained history at all, `ValidationError` when the
    period does not exist -- the API turns those into 403 and 400 respectively.
    """
    from django.core.exceptions import PermissionDenied, ValidationError

    if not user_can_read_archive(user):
        raise PermissionDenied("You do not have permission to read archived change history.")
    try:
        return ArchiveSegment.objects.get(model_label=model._meta.label_lower, period_key=period_key)
    except ArchiveSegment.DoesNotExist:
        raise ValidationError(f"No archived period '{period_key}' exists for {model._meta.verbose_name}.") from None


def get_archive_queryset(model, period_key, user):
    """
    The queryset for one retained period of `model`.

    One period per query, never a union across periods and never merged with warm storage. That is what
    keeps ordering and pagination identical to a warm read, and it is why `ObjectChange` having no
    time-sortable primary key never becomes a problem.
    """
    segment = get_archive_segment(model, period_key, user)
    mirror = archive_model_for(model)
    if mirror is None:
        from django.core.exceptions import ValidationError

        raise ValidationError(f"{model._meta.verbose_name} does not support archived history.")
    return mirror.objects.filter(period_key=segment.period_key)


# Query parameters that are not filters, and so are carried across a period switch untouched. Sorting and
# page size are preferences about presentation, not about which records are shown.
_NON_FILTER_CARRYOVER = (
    "sort",
    "per_page",
    "saved_view",
    "table_changes_pending",
    "all_filters_removed",
    "clear_view",
)


def period_switch_url(request, period_key, model):
    """
    Where a period selector entry should link, preserving the reader's current view.

    Switching period means "show me the same thing, for that period", so filters and sorting carry over.
    Two things do not:

    - `page`, because a different period has a different number of records and page 40 may not exist.
    - Any filter the target does not support. A few warm filters follow relationships a mirror holds as
      identifier columns, and carrying one into a period yields "invalid filters" and an empty table --
      confusing when the reader only meant to change period. Those are dropped, and returned so the caller
      can say which.

    Returns `(url, dropped_param_names)`.
    """
    from nautobot.extras.filters import archive_filterset_for

    params = request.GET.copy()
    params.pop("page", None)
    params.pop("archive_period", None)

    dropped = []
    if period_key:
        mirror = archive_model_for(model)
        filterset_class = archive_filterset_for(mirror) if mirror else None
        if filterset_class is not None:
            allowed = set(filterset_class.base_filters)
            for name in list(params.keys()):
                if name in _NON_FILTER_CARRYOVER or name in allowed:
                    continue
                params.pop(name)
                dropped.append(name)
        params["archive_period"] = period_key

    query = params.urlencode()
    return (f"{request.path}?{query}" if query else request.path), sorted(dropped)


def archive_context(model, request, show_counts=True):
    """
    The context the period selector renders from.

    Returns empty-but-present keys when retention is off or the viewer lacks the permission, so a template
    can include the selector unconditionally and a view needs no conditional of its own.

    `show_counts=False` for a view scoped to one object. A period's record count is for the whole period,
    so showing it beside an object's own history invites reading it as that object's count.
    """
    period_key = requested_archive_period(request)
    periods = get_archive_periods(model, getattr(request, "user", None))
    segment = None
    if period_key and periods:
        segment = periods.filter(period_key=period_key).first()
    # URLs are built here rather than in the template because deciding what carries over needs both
    # filtersets, which a template cannot see.
    periods = list(periods)
    dropped_any = set()
    # Deliberately not named `segment`: that holds the selected period, which `get_archive_freshness` below
    # still needs. Reusing the name reported the last period in the list as the selected one.
    for entry in periods:
        entry.switch_url, dropped = period_switch_url(request, entry.period_key, model)
        dropped_any.update(dropped)
    warm_url, _ = period_switch_url(request, None, model)

    return {
        "archive_periods": periods,
        "archive_period": period_key if segment is not None else None,
        "archive_freshness": get_archive_freshness(segment),
        "archive_show_counts": show_counts,
        "archive_warm_url": warm_url,
        "archive_dropped_filters": sorted(dropped_any),
    }


def filter_archive_queryset(queryset, params):
    """
    Apply the mirror's own filterset to a retained-period queryset.

    A separate filterset from the warm one because a handful of warm filters traverse relations the mirror
    holds as identifier columns. Everything else carries over, so filtering within a period behaves as it
    does warm; see `nautobot.extras.filters.build_archive_filterset` for what is dropped and why.

    Returns `(queryset, filterset)` so a caller can surface validation errors the way it already does for
    warm reads.
    """
    from nautobot.core.api.constants import NON_FILTER_QUERY_PARAMS
    from nautobot.extras.filters import archive_filterset_for

    filterset_class = archive_filterset_for(queryset.model)
    if filterset_class is None:
        return queryset, None

    data = params.copy() if hasattr(params, "copy") else dict(params)
    for name in NON_FILTER_QUERY_PARAMS:
        data.pop(name, None)
    for name in (
        "page",
        "per_page",
        "sort",
        "saved_view",
        "table_changes_pending",
        "all_filters_removed",
        "clear_view",
        "export",
    ):
        data.pop(name, None)

    filterset = filterset_class(data, queryset)
    return filterset.qs, filterset


def object_change_history(obj, content_type, request, user=None):
    """
    The change history to show on one object's change log tab, warm or from a selected period.

    Shared by the object change log view and the renderer that builds the tab's table, because two copies
    of this drifted once already: the dropdown rendered while the table kept showing warm records.

    Returns `(queryset, period_key)`. `period_key` is None when no period is selected.
    """
    from nautobot.extras.models import ObjectChange

    user = user or getattr(request, "user", None)
    period_key = requested_archive_period(request)
    if period_key:
        archived = get_archive_queryset(ObjectChange, period_key, user)
        # The mirror holds content types as identifier columns, so this cannot reuse the warm lookup.
        return (
            archived.filter(
                models.Q(changed_object_type_id=content_type.pk, changed_object_id=obj.pk)
                | models.Q(related_object_type_id=content_type.pk, related_object_id=obj.pk)
            ),
            period_key,
        )
    return (
        ObjectChange.objects.restrict(user, "view")
        .prefetch_related("user", "changed_object_type")
        .filter(
            models.Q(changed_object_type=content_type, changed_object_id=obj.pk)
            | models.Q(related_object_type=content_type, related_object_id=obj.pk)
        ),
        None,
    )


def get_archive_freshness(segment):
    """
    How current a period is, for display beside the selector.

    A closed period is complete and carries no staleness claim; an open one reports how far rotation has
    gotten into it.
    """
    if segment is None:
        return {}
    return {
        "period_label": segment.label,
        "last_rotated_time": segment.last_rotated_time,
        "is_period_closed": segment.is_period_closed,
    }
