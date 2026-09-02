"""
Reading retained history: the helpers that resolve a period, and the REST endpoints that expose it.

The read model is one period at a time behind a single permission, so the permission check and the
read-only guarantee are tested here rather than per view.
"""

import uuid

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings
from django.urls import reverse

from nautobot.core.testing import APITestCase, TestCase
from nautobot.extras.archive_reads import (
    get_archive_freshness,
    get_archive_periods,
    get_archive_queryset,
    requested_archive_period,
    user_can_read_archive,
)
from nautobot.extras.choices import (
    ObjectChangeActionChoices,
)
from nautobot.extras.models import (
    ArchivedObjectChange,
    ArchiveSegment,
    ObjectChange,
)
from nautobot.extras.models.archive import archive_model_for
from nautobot.extras.tests.test_changelog_archive_base import ArchiveReadFixtureMixin, PERIOD


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchiveReadHelperTestCase(ArchiveReadFixtureMixin, TestCase):
    """The helpers every read surface goes through, so the permission check lives in one place."""

    def setUp(self):
        super().setUp()
        ArchivedObjectChange.objects.all().delete()
        ArchiveSegment.objects.all().delete()

    def test_registry_resolves_a_warm_model_to_its_mirror(self):
        self.assertIs(archive_model_for(ObjectChange), ArchivedObjectChange)

    def test_uncovered_model_has_no_mirror(self):
        self.assertIsNone(archive_model_for(ArchiveSegment))

    def test_permission_is_required_to_read(self):
        self.assertFalse(user_can_read_archive(self.user))
        self.grant_cold_storage()
        self.assertTrue(user_can_read_archive(self.user))

    def test_periods_are_hidden_without_the_permission(self):
        """The selector offers nothing, so a caller renders it from this alone."""
        self.build_period()
        self.assertEqual(list(get_archive_periods(ObjectChange, self.user)), [])

    def test_periods_are_listed_with_the_permission(self):
        self.build_period(period_key="2020")
        self.build_period(period_key="2021")
        self.grant_cold_storage()

        periods = get_archive_periods(ObjectChange, self.user)

        self.assertEqual([segment.period_key for segment in periods], ["2021", "2020"], "newest first")

    @override_settings(CHANGELOG_ARCHIVE_ENABLED=False)
    def test_periods_are_hidden_when_the_capability_is_off(self):
        self.build_period()
        self.grant_cold_storage()
        self.assertEqual(list(get_archive_periods(ObjectChange, self.user)), [])

    def test_reading_without_the_permission_is_denied(self):
        self.build_period()
        with self.assertRaises(PermissionDenied):
            get_archive_queryset(ObjectChange, PERIOD, self.user)

    def test_reading_an_unknown_period_is_a_validation_error(self):
        self.grant_cold_storage()
        with self.assertRaises(ValidationError):
            get_archive_queryset(ObjectChange, "1999", self.user)

    def test_reading_a_period_returns_only_that_period(self):
        self.build_period(period_key="2020", rows=2)
        self.build_period(period_key="2021", rows=3)
        self.grant_cold_storage()

        self.assertEqual(get_archive_queryset(ObjectChange, "2020", self.user).count(), 2)
        self.assertEqual(get_archive_queryset(ObjectChange, "2021", self.user).count(), 3)

    def test_freshness_reports_a_closed_period_as_complete(self):
        segment = self.build_period(closed=True)
        freshness = get_archive_freshness(segment)
        self.assertTrue(freshness["is_period_closed"])
        self.assertEqual(freshness["period_label"], PERIOD)

    def test_freshness_reports_an_open_period_with_its_progress(self):
        segment = self.build_period(closed=False)
        freshness = get_archive_freshness(segment)
        self.assertFalse(freshness["is_period_closed"])
        self.assertIsNotNone(freshness["last_rotated_time"])

    def test_requested_period_reads_the_query_parameter(self):
        class _Request:
            GET = {"archive_period": "2021"}

        self.assertEqual(requested_archive_period(_Request()), "2021")
        self.assertIsNone(requested_archive_period(None))

        class _Empty:
            GET = {}

        self.assertIsNone(requested_archive_period(_Empty()))


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchiveReadAPITestCase(ArchiveReadFixtureMixin, APITestCase):
    """
    `?archive_period=` on the endpoints a client already calls.

    Absent, the endpoint behaves exactly as before; that parity is asserted rather than assumed.
    """

    def setUp(self):
        super().setUp()
        ArchivedObjectChange.objects.all().delete()
        ArchiveSegment.objects.all().delete()
        self.url = reverse("extras-api:objectchange-list")

    def test_default_read_is_unchanged_and_needs_no_permission(self):
        """§8: with no period requested, reads behave as they do today."""
        self.add_permissions("extras.view_objectchange")
        self.build_period(rows=2)

        response = self.client.get(self.url, **self.header)

        self.assertHttpStatus(response, 200)
        archived_reprs = {"Archived Widget"}
        returned = {entry.get("object_repr") for entry in response.data["results"]}
        self.assertFalse(returned & archived_reprs, "a default read must not return archived records")

    def test_period_read_is_rejected_without_the_permission(self):
        """§8: without the permission the API parameter is rejected, not quietly downgraded."""
        self.add_permissions("extras.view_objectchange")
        self.build_period()

        response = self.client.get(f"{self.url}?archive_period={PERIOD}", **self.header)

        self.assertHttpStatus(response, 403)

    def test_unknown_period_is_a_bad_request(self):
        self.add_permissions("extras.view_objectchange")
        self.grant_cold_storage()

        response = self.client.get(f"{self.url}?archive_period=1999", **self.header)

        self.assertHttpStatus(response, 400)

    def test_period_read_returns_that_period(self):
        self.add_permissions("extras.view_objectchange")
        self.grant_cold_storage()
        self.build_period(rows=2)

        response = self.client.get(f"{self.url}?archive_period={PERIOD}", **self.header)

        self.assertHttpStatus(response, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual({entry["object_repr"] for entry in response.data["results"]}, {"Archived Widget"})

    def test_archived_response_matches_the_warm_schema(self):
        """§8: an archived response validates against the same schema as the warm equivalent."""
        self.add_permissions("extras.view_objectchange")
        self.grant_cold_storage()
        self.build_period(rows=1)
        ObjectChange.objects.create(
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type=ContentType.objects.get_for_model(ObjectChange),
            changed_object_id=uuid.uuid4(),
            object_repr="Warm Widget",
            object_data={},
            request_id=uuid.uuid4(),
            user_name="alice",
            change_context="orm",
        )

        warm = self.client.get(self.url, **self.header)
        cold = self.client.get(f"{self.url}?archive_period={PERIOD}", **self.header)

        self.assertHttpStatus(warm, 200)
        self.assertHttpStatus(cold, 200)
        self.assertEqual(
            set(warm.data["results"][0].keys()),
            set(cold.data["results"][0].keys()),
            "archived and warm responses must carry the same fields",
        )

    def test_changed_object_falls_back_to_object_repr_for_archived_records(self):
        """A retained record has no generic foreign key to follow, so the denormalized repr is used."""
        self.add_permissions("extras.view_objectchange")
        self.grant_cold_storage()
        self.build_period(rows=1)

        response = self.client.get(f"{self.url}?archive_period={PERIOD}", **self.header)

        self.assertHttpStatus(response, 200)
        self.assertEqual(response.data["results"][0]["changed_object"], "Archived Widget")

    def test_archive_segments_endpoint_lists_the_available_periods(self):
        """How a client discovers valid `archive_period` values."""
        self.add_permissions("extras.view_archivesegment")
        self.build_period(period_key="2020")
        self.build_period(period_key="2021")

        response = self.client.get(reverse("extras-api:archivesegment-list"), **self.header)

        self.assertHttpStatus(response, 200)
        self.assertEqual(
            {entry["period_key"] for entry in response.data["results"]},
            {"2020", "2021"},
        )
