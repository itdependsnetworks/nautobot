"""
Tests for the REST endpoints over retained history.

These cover what the endpoints do here: list, retrieve, filter, and refuse a write. Each serializer
subclasses its warm counterpart with `Meta.model` pointed at the mirror, which is what makes `url` name
the archived route and keeps `BaseModelSerializer`'s natural-key lookups off relations the mirror does
not have.

A demoted reference still serializes to null, because the mirror stores `user_id` and has no `user` to
follow. Key-for-key agreement with the warm response is what CONCRETE-8 adds, and the test asserting it
arrives with it.
"""

from datetime import datetime, timezone as dt_timezone
import uuid

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from nautobot.core.constants import CHANGELOG_ARCHIVE
from nautobot.core.testing import APITestCase, APIViewTestCases
from nautobot.extras.choices import JobResultStatusChoices, LogLevelChoices, ObjectChangeActionChoices
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    JobLogEntry,
    JobResult,
    ObjectChange,
)
from nautobot.extras.tests.test_changelog_archive_base import clear_archive

WHEN = datetime(2021, 6, 1, tzinfo=dt_timezone.utc)
MIRRORS = (ArchivedObjectChange, ArchivedJobResult, ArchivedJobLogEntry, ArchivedJobConsoleEntry)


def make_archived_changes(count=3):
    for index in range(count):
        ArchivedObjectChange.objects.create(
            id=uuid.uuid4(),
            time=WHEN,
            user_name="alice",
            request_id=uuid.uuid4(),
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type_id=ContentType.objects.get_for_model(ObjectChange).pk,
            changed_object_id=uuid.uuid4(),
            change_context="orm",
            object_repr=f"Archived Widget {index}",
            object_data={},
        )


def make_archived_results(count=3):
    results = []
    for index in range(count):
        results.append(
            ArchivedJobResult.objects.create(
                id=uuid.uuid4(),
                name=f"retained-job-{index}",
                user_name="alice",
                status=JobResultStatusChoices.STATUS_SUCCESS,
                date_created=WHEN,
                date_started=WHEN,
                date_done=WHEN,
                celery_kwargs={"queue": "default"},
            )
        )
    return results


class ArchivedObjectChangeTest(APIViewTestCases.GetObjectViewTestCase, APIViewTestCases.ListObjectsViewTestCase):
    databases = ["default", CHANGELOG_ARCHIVE]

    model = ArchivedObjectChange

    @classmethod
    def setUpTestData(cls):
        clear_archive(*MIRRORS)
        make_archived_changes()


class ArchivedJobResultTest(APIViewTestCases.GetObjectViewTestCase, APIViewTestCases.ListObjectsViewTestCase):
    databases = ["default", CHANGELOG_ARCHIVE]

    model = ArchivedJobResult
    choices_fields = ["status"]

    @classmethod
    def setUpTestData(cls):
        clear_archive(*MIRRORS)
        make_archived_results()


class ArchivedJobLogEntryTest(APIViewTestCases.GetObjectViewTestCase, APIViewTestCases.ListObjectsViewTestCase):
    databases = ["default", CHANGELOG_ARCHIVE]

    model = ArchivedJobLogEntry
    choices_fields = []

    @classmethod
    def setUpTestData(cls):
        clear_archive(*MIRRORS)
        result = make_archived_results(1)[0]
        for level in (LogLevelChoices.LOG_DEBUG, LogLevelChoices.LOG_INFO, LogLevelChoices.LOG_WARNING):
            ArchivedJobLogEntry.objects.create(
                id=uuid.uuid4(),
                job_result_id=result.pk,
                created=WHEN,
                grouping="run",
                log_level=level,
                message=f"a retained {level} line",
            )


class ArchivedApiShapeTest(APITestCase):
    """The archived response against the warm one, field name by field name."""

    databases = ["default", CHANGELOG_ARCHIVE]

    def setUp(self):
        super().setUp()
        clear_archive(*MIRRORS)
        self.addCleanup(clear_archive, *MIRRORS)
        self.add_permissions(
            "extras.view_archivedobjectchange",
            "extras.view_archivedjobresult",
            "extras.view_archivedjoblogentry",
            "extras.view_objectchange",
            "extras.view_jobresult",
            "extras.view_joblogentry",
        )
        make_archived_changes(1)
        self.archived_result = make_archived_results(1)[0]
        ArchivedJobLogEntry.objects.create(
            id=uuid.uuid4(),
            job_result_id=self.archived_result.pk,
            created=WHEN,
            grouping="run",
            log_level=LogLevelChoices.LOG_INFO,
            message="a retained log line",
        )
        # Warm counterparts to compare against.
        change = ObjectChange.objects.create(
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type=ContentType.objects.get_for_model(ObjectChange),
            changed_object_id=uuid.uuid4(),
            object_repr="Warm Widget",
            object_data={},
            request_id=uuid.uuid4(),
            user_name="alice",
            change_context="orm",
        )
        self.warm_change = change
        self.warm_result = JobResult.objects.create(name="warm-job", celery_kwargs={})
        JobLogEntry.objects.create(
            job_result=self.warm_result, grouping="run", log_level=LogLevelChoices.LOG_INFO, message="warm log line"
        )

    def keys_at(self, route):
        response = self.client.get(f"{reverse(route)}?limit=1", **self.header)
        self.assertHttpStatus(response, 200)
        self.assertTrue(response.data["results"], f"{route} returned no records to compare")
        return set(response.data["results"][0])

    def test_retained_changes_carry_the_same_fields_as_warm_changes(self):
        self.assertEqual(
            self.keys_at("extras-api:archivedobjectchange-list"), self.keys_at("extras-api:objectchange-list")
        )

    def test_retained_job_log_entries_carry_the_same_fields_as_warm_ones(self):
        self.assertEqual(
            self.keys_at("extras-api:archivedjoblogentry-list"), self.keys_at("extras-api:joblogentry-list")
        )

    def test_retained_job_results_add_only_the_denormalized_user_name(self):
        """`user_name` is the one addition: the user foreign key is demoted, so the name is stored."""
        archived = self.keys_at("extras-api:archivedjobresult-list")
        warm = self.keys_at("extras-api:jobresult-list")

        self.assertEqual(warm - archived, set())
        self.assertEqual(archived - warm, {"user_name"})

    def test_a_demoted_relation_is_rendered_as_an_object_not_a_bare_id(self):
        """`fields = "__all__"` over a mirror names these `job_result_id`, which no warm client reads."""
        response = self.client.get(f"{reverse('extras-api:archivedjoblogentry-list')}?limit=1", **self.header)

        entry = response.data["results"][0]
        self.assertNotIn("job_result_id", entry)
        self.assertEqual(entry["job_result"]["id"], str(self.archived_result.pk))
        self.assertEqual(entry["job_result"]["object_type"], "extras.jobresult")

    def test_a_demoted_content_type_is_rendered_as_app_label_and_model(self):
        response = self.client.get(f"{reverse('extras-api:archivedobjectchange-list')}?limit=1", **self.header)

        record = response.data["results"][0]
        self.assertNotIn("changed_object_type_id", record)
        self.assertEqual(record["changed_object_type"], "extras.objectchange")

    def test_url_names_the_retained_endpoint_not_the_warm_one(self):
        """The two share a primary key, so a warm url here would point at a record that is gone."""
        record = ArchivedObjectChange.objects.first()

        response = self.client.get(f"{reverse('extras-api:archivedobjectchange-list')}?limit=1", **self.header)

        self.assertIn(f"/api/extras/archived-object-changes/{record.pk}/", response.data["results"][0]["url"])

    def test_csv_export_of_retained_log_entries(self):
        """
        Built from the warm model, the natural-key lookups name relations rotation demoted.

        That raised `FieldError` on every export, which is why the serializer declares the mirror.
        """
        url = f"{reverse('extras-api:archivedjoblogentry-list')}?job_result_id={self.archived_result.pk}&format=csv"

        response = self.client.get(url, **self.header)

        self.assertHttpStatus(response, 200)
        self.assertEqual(len(response.content.decode().splitlines()), 2)  # header plus the one entry


class ArchivedApiPermissionTest(APITestCase):
    """Retained history is gated by its own ordinary `view` permission, granted to nobody by default."""

    databases = ["default", CHANGELOG_ARCHIVE]

    def setUp(self):
        super().setUp()
        clear_archive(*MIRRORS)
        self.addCleanup(clear_archive, *MIRRORS)
        make_archived_changes(1)

    def test_the_warm_permission_does_not_grant_the_retained_endpoint(self):
        self.add_permissions("extras.view_objectchange")

        response = self.client.get(reverse("extras-api:archivedobjectchange-list"), **self.header)

        self.assertHttpStatus(response, 403)

    def test_the_retained_endpoint_offers_no_write(self):
        """Rotation writes these records and nothing else does, so only `view` exists."""
        self.add_permissions("extras.view_archivedobjectchange")

        response = self.client.post(reverse("extras-api:archivedobjectchange-list"), {}, format="json", **self.header)

        self.assertIn(response.status_code, (403, 405))
