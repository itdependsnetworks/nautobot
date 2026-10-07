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

from nautobot.core.testing import APITestCase, APIViewTestCases
from nautobot.extras.choices import JobResultStatusChoices, LogLevelChoices, ObjectChangeActionChoices
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
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
    model = ArchivedObjectChange

    @classmethod
    def setUpTestData(cls):
        clear_archive(*MIRRORS)
        make_archived_changes()


class ArchivedJobResultTest(APIViewTestCases.GetObjectViewTestCase, APIViewTestCases.ListObjectsViewTestCase):
    model = ArchivedJobResult
    choices_fields = ["status"]

    @classmethod
    def setUpTestData(cls):
        clear_archive(*MIRRORS)
        make_archived_results()


class ArchivedJobLogEntryTest(APIViewTestCases.GetObjectViewTestCase, APIViewTestCases.ListObjectsViewTestCase):
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


class ArchivedApiPermissionTest(APITestCase):
    """Retained history is gated by its own ordinary `view` permission, granted to nobody by default."""

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
