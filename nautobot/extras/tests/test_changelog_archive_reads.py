"""
Reading retained history: the helpers that resolve a period, and the REST endpoints that expose it.

The read model is one period at a time behind a single permission, so the permission check and the
read-only guarantee are tested here rather than per view.
"""

from datetime import datetime, timezone as dt_timezone
import uuid

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings
from django.urls import reverse

from nautobot.core.testing import APITestCase, TestCase
from nautobot.extras.archive_reads import (
    get_archive_queryset,
    requested_archive_period,
    user_can_read_archive,
)
from nautobot.extras.choices import (
    JobResultStatusChoices,
    ObjectChangeActionChoices,
)
from nautobot.extras.models import (
    ArchivedJobResult,
    ArchivedObjectChange,
    ArchiveSegment,
    JobResult,
    ObjectChange,
)
from nautobot.extras.models.archive import archive_model_for
from nautobot.extras.tests.test_changelog_archive_base import archived, ArchiveReadFixtureMixin, clear_archive, PERIOD


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchiveReadHelperTestCase(ArchiveReadFixtureMixin, TestCase):
    """The helpers every read surface goes through, so the permission check lives in one place."""

    def setUp(self):
        super().setUp()
        clear_archive(ArchivedObjectChange)
        ArchiveSegment.objects.all().delete()

    def test_registry_resolves_a_warm_model_to_its_mirror(self):
        self.assertIs(archive_model_for(ObjectChange), ArchivedObjectChange)

    def test_uncovered_model_has_no_mirror(self):
        self.assertIsNone(archive_model_for(ArchiveSegment))

    def test_permission_is_required_to_read(self):
        self.assertFalse(user_can_read_archive(self.user))
        self.grant_cold_storage()
        self.assertTrue(user_can_read_archive(self.user))

    def test_reading_without_the_permission_is_denied(self):
        self.build_period()
        with self.assertRaises(PermissionDenied):
            get_archive_queryset(ObjectChange, PERIOD, self.user)

    def test_reading_an_unknown_period_is_a_validation_error(self):
        self.grant_cold_storage()
        with self.assertRaises(ValidationError):
            get_archive_queryset(ObjectChange, "1999", self.user)

    def test_requested_period_reads_the_query_parameter(self):
        class _Request:
            GET = {"archive_period": PERIOD}

        self.assertEqual(requested_archive_period(_Request()), PERIOD)
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
        clear_archive(ArchivedObjectChange)
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


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchivedRecordsAreReadOnlyTestCase(ArchiveReadFixtureMixin, TestCase):
    """
    Retained history has no write surface, so the table must not offer one.

    Row actions and the bulk-select checkbox reverse warm URLs from the record's key, so on a retained
    record they point at a view that cannot find it. That surfaced as a delete link returning 404.
    """

    def setUp(self):
        super().setUp()
        clear_archive(ArchivedJobResult)
        ArchiveSegment.objects.all().delete()
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        ArchiveSegment.objects.create(
            model_label="extras.jobresult",
            period_key=PERIOD,
            label=PERIOD,
            row_count=1,
            is_period_closed=True,
        )
        archived(ArchivedJobResult).objects.create(
            id=uuid.uuid4(),
            period_key=PERIOD,
            name="Archived Run",
            date_created=datetime(2021, 6, 1, tzinfo=dt_timezone.utc),
            status=JobResultStatusChoices.STATUS_SUCCESS,
        )

    def rendered(self, query=""):
        response = self.client.get(f"{reverse('extras:jobresult_list')}{query}", headers={"hx-request": "true"})
        self.assertHttpStatus(response, 200)
        return response.content.decode(response.charset)

    def test_archived_rows_offer_no_row_actions(self):
        content = self.rendered(f"?archive_period={PERIOD}")
        self.assertIn("Archived Run", content)
        self.assertNotIn("/delete/", content)

    def test_archived_rows_offer_no_bulk_select(self):
        self.assertNotIn('name="pk"', self.rendered(f"?archive_period={PERIOD}"))

    def test_sorting_by_a_demoted_relation_executes(self):
        """
        A mirror declares its foreign keys as bare `<name>_id` columns.

        A column whose sort names the relation -- `job_model`, `user` -- raises `FieldError` against the
        mirror, so the header link 500s. `_retarget_retained_history_ordering` points each one at the
        identifier instead, which is what the warm sort resolves to anyway.
        """
        for column in ("job_model", "user", "name"):
            with self.subTest(column=column):
                self.assertIn("Archived Run", self.rendered(f"?archive_period={PERIOD}&sort={column}"))

    def test_warm_rows_still_offer_row_actions(self):
        """The guard must be specific to retained history, not a blanket removal."""
        JobResult.objects.create(name="Warm Run", status=JobResultStatusChoices.STATUS_SUCCESS)

        content = self.rendered()

        self.assertIn("Warm Run", content)
        self.assertIn("/delete/", content)
        self.assertIn('name="pk"', content)
