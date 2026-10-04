"""
Resolving a read against one period of retained history.

The storage side is defined in `nautobot.extras.models.archive`; this is everything a request goes through to
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
    Whether `user` has been granted the single cold-storage permission.

    One grant covering retained history across every covered model, rather than one per model: the default
    view permission on the period registry.
    """
    return bool(user and user.is_authenticated and user.has_perm(COLD_STORAGE_PERMISSION))


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
    from django.core.exceptions import ValidationError

    segment = get_archive_segment(model, period_key, user)
    mirror = archive_model_for(model, segment.period_key)
    if mirror is None:
        raise ValidationError(f"{model._meta.verbose_name} does not support archived history.")
    # No period filter: the table is the period. `period_key` stays on the row so reconciliation can
    # still find a record written to the wrong one.
    return mirror.objects.all()


def filter_archive_queryset(queryset, params):
    """
    Apply the mirror's own filterset to a retained-period queryset.

    A separate filterset from the warm one because a handful of warm filters traverse relations the mirror
    holds as identifier columns. Everything else carries over, so filtering within a period behaves as it
    does warm; see `nautobot.extras.filters.ARCHIVE_FILTERSETS` for what each one offers.

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
        # The mirror declares content types as identifier columns, so this cannot reuse the warm lookup.
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
