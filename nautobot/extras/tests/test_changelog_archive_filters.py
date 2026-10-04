"""
Filtering within a retained period.

The mirror filtersets are derived from the warm ones, so what survives derivation and what is dropped is
the thing worth pinning.
"""

from datetime import datetime, timezone as dt_timezone
import uuid

from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse

from nautobot.core.constants import CHANGELOG_ARCHIVE
from nautobot.core.testing import APITestCase, TestCase
from nautobot.extras.choices import (
    ObjectChangeActionChoices,
)
from nautobot.extras.models import (
    ArchivedObjectChange,
    ArchiveSegment,
    ObjectChange,
)
from nautobot.extras.tests.test_changelog_archive_base import archived, ArchiveReadFixtureMixin, clear_archive, PERIOD


class ArchiveFilterSetTestCase(TestCase):
    """
    The mirror filtersets, and what they cost against the warm ones.

    The archive filtersets are declared against the mirrors instead of derived from the warm filtersets, so
    nothing stops the two drifting apart silently. The difference is pinned here, which makes a capability
    loss something a reviewer agrees to instead of something a reader discovers.
    """

    databases = ["default", CHANGELOG_ARCHIVE]

    # Each of these traverses a relation the mirror does not have. The `_id` columns survive, and for
    # `user` the mirror also records the denormalized `user_name`. `period_key` is absent by design: one
    # table per period means the period is which table a read opens, not a column to filter on.
    EXPECTED_MISSING = {
        "extras.archivedobjectchange": {"user", "user_id"},
        "extras.archivedjobresult": {
            "cancel_type",
            "canceled_by",
            "has_job_console_entries",
            "job_model",
            "job_model_id",
            "scheduled_job",
            "user",
        },
        "extras.archivedjoblogentry": set(),
    }

    WARM_COUNTERPARTS = {
        "extras.archivedobjectchange": "extras.objectchange",
        "extras.archivedjobresult": "extras.jobresult",
        "extras.archivedjoblogentry": "extras.joblogentry",
    }

    def test_filters_absent_from_the_archive_are_exactly_what_is_expected(self):
        from django.apps import apps

        from nautobot.core.utils.lookup import get_filterset_for_model
        from nautobot.extras.filters import ARCHIVE_FILTERSETS

        actual = {}
        for label, archive_filterset in ARCHIVE_FILTERSETS.items():
            warm_filterset = get_filterset_for_model(apps.get_model(self.WARM_COUNTERPARTS[label]))
            # Compared on declared names only. The lookup expansions (`__ic`, `__n`, and the rest) follow
            # from the declarations, so comparing those too would report one divergence many times over.
            candidates = set(warm_filterset.declared_filters)
            candidates |= set(getattr(warm_filterset.Meta, "fields", None) or [])
            actual[label] = candidates - set(archive_filterset.base_filters)
        self.assertEqual(actual, self.EXPECTED_MISSING)

    def test_every_kept_filter_actually_executes(self):
        """A filter that resolves at class-definition time but raises on use would be worse than a dropped one."""
        from nautobot.extras.filters import ARCHIVE_FILTERSETS
        from nautobot.extras.registry import registry

        # The filtersets are keyed on the abstract mirrors, which are not in the app registry. A filter
        # has to execute against a period's table, so each is exercised against one.
        mirrors = {m._meta.label_lower: m for m in registry["changelog_archive_models"].values()}
        for label, filterset_class in ARCHIVE_FILTERSETS.items():
            model = archived(mirrors[label])
            for name in filterset_class.base_filters:
                with self.subTest(model=label, filter=name):
                    # Values are deliberately junk; the point is that the lookup resolves against the mirror.
                    list(filterset_class({name: "1"}, queryset=model.objects.all()).qs[:1])

    def test_search_filter_keeps_only_resolvable_predicates(self):
        from nautobot.extras.filters import ArchivedJobResultFilterSet

        predicates = ArchivedJobResultFilterSet.declared_filters["q"].filter_predicates
        self.assertNotIn("scheduled_job__name", predicates, "a predicate traversing a relation cannot resolve")
        self.assertTrue(predicates, "searching within a period is the filter most worth keeping")


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchiveFilteredReadAPITestCase(ArchiveReadFixtureMixin, APITestCase):
    """Filtering within a period, over the same query parameters a warm read accepts."""

    def setUp(self):
        super().setUp()
        clear_archive(ArchivedObjectChange)
        ArchiveSegment.objects.all().delete()
        self.url = reverse("extras-api:objectchange-list")
        self.add_permissions("extras.view_objectchange")
        self.grant_cold_storage()
        self.build_period(rows=2)
        # A third record, distinguishable by user_name and action.
        archived(ArchivedObjectChange).objects.create(
            id=uuid.uuid4(),
            period_key=PERIOD,
            time=datetime(2021, 7, 1, tzinfo=dt_timezone.utc),
            user_name="bob",
            request_id=uuid.uuid4(),
            action=ObjectChangeActionChoices.ACTION_DELETE,
            changed_object_type_id=ContentType.objects.get_for_model(ObjectChange).pk,
            changed_object_id=uuid.uuid4(),
            change_context="orm",
            object_repr="Bob Widget",
            object_data={},
        )

    def get(self, query):
        response = self.client.get(f"{self.url}?archive_period={PERIOD}&{query}", **self.header)
        self.assertHttpStatus(response, 200)
        return response.data

    def test_unfiltered_period_returns_everything_in_it(self):
        self.assertEqual(self.get("")["count"], 3)

    def test_filter_by_action(self):
        data = self.get(f"action={ObjectChangeActionChoices.ACTION_DELETE}")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["object_repr"], "Bob Widget")

    def test_filter_by_user_name(self):
        self.assertEqual(self.get("user_name=bob")["count"], 1)
        self.assertEqual(self.get("user_name=alice")["count"], 2)

    def test_search_within_a_period(self):
        self.assertEqual(self.get("q=Bob")["count"], 1)

    def test_filter_by_time_range(self):
        self.assertEqual(self.get("time__gte=2021-06-15")["count"], 1)

    def test_filter_by_content_type_uses_the_identifier_column(self):
        """`?changed_object_type=extras.objectchange` keeps working against a mirror."""
        self.assertEqual(self.get("changed_object_type=extras.objectchange")["count"], 3)
        self.assertEqual(self.get("changed_object_type=dcim.device")["count"], 0)

    def test_invalid_filter_value_is_a_bad_request(self):
        response = self.client.get(f"{self.url}?archive_period={PERIOD}&action=not-a-real-action", **self.header)
        self.assertHttpStatus(response, 400)
