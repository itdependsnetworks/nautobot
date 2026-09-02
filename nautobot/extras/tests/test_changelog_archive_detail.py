"""
A retained record's own page: the change record and the job result.

Both open at the URL they had before rotation, read-only, with the panels that depend on relations the
mirror no longer holds resolved within the record's period.
"""

from datetime import datetime, timezone as dt_timezone
import uuid

from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse

from nautobot.core.testing import TestCase
from nautobot.extras.choices import (
    JobConsoleEntryOutputTypeChoices,
    JobResultStatusChoices,
    LogLevelChoices,
    ObjectChangeActionChoices,
)
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    ArchiveSegment,
    ObjectChange,
)
from nautobot.extras.tests.test_changelog_archive_base import ArchiveReadFixtureMixin, PERIOD


class ArchiveAwareRetrieveGuardsTestCase(ArchiveReadFixtureMixin, TestCase):
    """
    The retention fallback on the existing detail views is deliberately narrow.

    Both guards here were real hazards, not hypotheticals: without them the fallback fired on every 404
    and offered an archived record to a delete view.
    """

    def setUp(self):
        super().setUp()
        ArchivedJobResult.objects.all().delete()
        ArchiveSegment.objects.all().delete()
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        ArchiveSegment.objects.create(
            model_label="extras.jobresult",
            period_key=PERIOD,
            label=PERIOD,
            time_start=datetime(int(PERIOD), 1, 1, tzinfo=dt_timezone.utc),
            time_end=datetime(int(PERIOD) + 1, 1, 1, tzinfo=dt_timezone.utc),
            row_count=1,
            is_period_closed=True,
        )
        self.archived = ArchivedJobResult.objects.create(
            id=uuid.uuid4(),
            period_key=PERIOD,
            name="Archived Run",
            date_created=datetime(int(PERIOD), 6, 1, tzinfo=dt_timezone.utc),
            status=JobResultStatusChoices.STATUS_SUCCESS,
        )

    @override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
    def test_detail_view_serves_a_retained_record(self):
        """The point of the fallback: one URL space, and a link made before rotation still works."""
        response = self.client.get(self.archived.get_absolute_url())
        self.assertHttpStatus(response, 200)
        self.assertIn("Archived Run", response.content.decode(response.charset))

    @override_settings(CHANGELOG_ARCHIVE_ENABLED=False)
    def test_no_fallback_while_retention_is_disabled(self):
        """
        §8: with the capability off, reads behave exactly as they did before it existed.

        Also why unrelated test classes do not need the archive database declared: a 404 costs no query.
        """
        self.assertHttpStatus(self.client.get(self.archived.get_absolute_url()), 404)

    @override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
    def test_delete_view_does_not_fall_back_to_retention(self):
        """A retained record has no write surface, so a destroy action must not resolve one."""
        response = self.client.get(f"{self.archived.get_absolute_url()}delete/")
        self.assertHttpStatus(response, 404)

    @override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
    def test_fallback_requires_the_cold_storage_permission(self):
        self.user.is_superuser = False
        self.user.save()
        self.add_permissions("extras.view_jobresult")
        self.client.force_login(self.user)

        self.assertHttpStatus(self.client.get(self.archived.get_absolute_url()), 403)


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchivedRelatedChangesTestCase(ArchiveReadFixtureMixin, TestCase):
    """
    Related changes survive rotation; links to them must keep the period.

    A link that drops `archive_period` lands the reader back in warm storage, which reads as the records
    having changed rather than the view. Two templates render such links and both had it hardcoded.
    """

    def setUp(self):
        super().setUp()
        ArchivedObjectChange.objects.all().delete()
        ArchiveSegment.objects.all().delete()
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        self.content_type = ContentType.objects.get_for_model(ObjectChange)
        ArchiveSegment.objects.create(
            model_label="extras.objectchange",
            period_key=PERIOD,
            label=PERIOD,
            time_start=datetime(int(PERIOD), 1, 1, tzinfo=dt_timezone.utc),
            time_end=datetime(int(PERIOD) + 1, 1, 1, tzinfo=dt_timezone.utc),
            row_count=3,
            is_period_closed=True,
        )
        # One request touching one object three times, as a bulk edit does, plus an unrelated record.
        self.request_id = uuid.uuid4()
        self.object_id = uuid.uuid4()
        self.siblings = [self._change(self.request_id, self.object_id, second) for second in range(3)]
        self._change(uuid.uuid4(), uuid.uuid4(), 0)

    def _change(self, request_id, object_id, second, action=None, object_data=None):
        return ArchivedObjectChange.objects.create(
            id=uuid.uuid4(),
            period_key=PERIOD,
            time=datetime(int(PERIOD), 6, 1, 12, 0, second, tzinfo=dt_timezone.utc),
            user_name="alice",
            request_id=request_id,
            action=action or ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type_id=self.content_type.pk,
            changed_object_id=object_id,
            change_context="orm",
            object_repr="Archived Widget",
            object_data=object_data if object_data is not None else {},
            object_data_v2=object_data,
        )

    def test_related_changes_match_warm_semantics(self):
        """Same object, same request, excluding this record -- what `get_related_changes` means warm."""
        response = self.client.get(self.siblings[0].get_absolute_url())

        self.assertHttpStatus(response, 200)
        self.assertEqual(response.context["related_changes_count"], 2)
        listed = {change.pk for change in response.context["related_changes_table"].data.data}
        self.assertEqual(listed, {self.siblings[1].pk, self.siblings[2].pk})

    def test_request_id_links_keep_the_period(self):
        """Both the detail badge and the table column render one of these."""
        for url in (
            self.siblings[0].get_absolute_url(),
            f"{reverse('extras:objectchange_list')}?archive_period={PERIOD}",
        ):
            with self.subTest(url=url):
                headers = {"hx-request": "true"} if "archive_period" in url else {}
                content = self.client.get(url, headers=headers).content.decode()
                links = [
                    part.split('"')[0].replace("&amp;", "&")
                    for part in content.split('href="')[1:]
                    if "request_id=" in part.split('"')[0]
                ]
                self.assertTrue(links, f"expected a request_id link on {url}")
                for link in links:
                    self.assertIn(f"archive_period={PERIOD}", link)

    def test_warm_request_id_links_do_not_gain_a_period(self):
        """The templates serve both, so the warm path must be untouched."""
        warm = ObjectChange.objects.create(
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type=self.content_type,
            changed_object_id=uuid.uuid4(),
            object_repr="Warm Widget",
            object_data={},
            request_id=uuid.uuid4(),
            user_name="alice",
            change_context="orm",
        )
        content = self.client.get(
            f"{reverse('extras:objectchange_list')}", headers={"hx-request": "true"}
        ).content.decode()

        links = [part.split('"')[0] for part in content.split('href="')[1:] if "request_id=" in part.split('"')[0]]
        self.assertTrue(links, "expected warm rows to render request_id links")
        for link in links:
            self.assertNotIn("archive_period", link)
        self.assertIsNotNone(warm.pk)


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchivedRecordDiffTestCase(ArchivedRelatedChangesTestCase):
    """
    A retained record is diffed and navigated the same way a warm one is.

    The diff is not stored; it is derived by comparing a record against the previous change to the same
    object. That works on a mirror once the mirror can find its own neighbours, so the detail view runs one
    code path for both and the panel is populated rather than blank.
    """

    def setUp(self):
        super().setUp()
        # A create followed by two updates to one object, each changing one field, as real history looks.
        self.object_id = uuid.uuid4()
        self.request_id = uuid.uuid4()
        self.created = self._change(
            self.request_id,
            self.object_id,
            10,
            action=ObjectChangeActionChoices.ACTION_CREATE,
            object_data={"name": "widget", "status": "Active", "asset_tag": None},
        )
        self.renamed = self._change(
            self.request_id,
            self.object_id,
            11,
            object_data={"name": "widget", "status": "Planned", "asset_tag": None},
        )
        self.tagged = self._change(
            self.request_id,
            self.object_id,
            12,
            object_data={"name": "widget", "status": "Planned", "asset_tag": "ASSET-1"},
        )

    def test_update_diffs_against_the_previous_change(self):
        response = self.client.get(self.tagged.get_absolute_url())

        self.assertHttpStatus(response, 200)
        self.assertEqual(response.context["diff_added"], {"asset_tag": "ASSET-1"})
        self.assertEqual(response.context["diff_removed"], {"asset_tag": None})
        self.assertNotContains(response, "No changes")

    def test_create_has_everything_added_and_nothing_removed(self):
        snapshots = self.created.get_snapshots()

        self.assertEqual(snapshots["differences"]["added"], self.created.object_data)
        self.assertIsNone(snapshots["differences"]["removed"])
        self.assertIsNone(snapshots["prechange"])

    def test_delete_has_everything_removed_and_nothing_added(self):
        deleted = self._change(
            self.request_id,
            self.object_id,
            13,
            action=ObjectChangeActionChoices.ACTION_DELETE,
            object_data=self.tagged.object_data,
        )
        snapshots = deleted.get_snapshots()

        self.assertIsNone(snapshots["differences"]["added"])
        self.assertEqual(snapshots["differences"]["removed"], self.tagged.object_data)

    def test_neighbours_are_this_object_within_this_period(self):
        self.assertEqual(self.renamed.get_prev_change().pk, self.created.pk)
        self.assertEqual(self.renamed.get_next_change().pk, self.tagged.pk)
        # A record in an adjacent period is not a neighbour: one period per query.
        other_period = ArchivedObjectChange.objects.create(
            id=uuid.uuid4(),
            period_key=str(int(PERIOD) - 1),
            time=datetime(int(PERIOD) - 1, 12, 31, tzinfo=dt_timezone.utc),
            user_name="alice",
            request_id=self.request_id,
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type_id=self.content_type.pk,
            changed_object_id=self.object_id,
            change_context="orm",
            object_repr="Archived Widget",
            object_data={},
        )
        self.assertNotIn(other_period.pk, {change.pk for change in self.created.get_related_changes()})
        # The earliest record in a period has no predecessor, which yields no diff rather than an error.
        self.assertIsNone(self.created.get_prev_change())

    def test_content_types_resolve_from_their_identifier_columns(self):
        self.assertEqual(self.tagged.changed_object_type, self.content_type)
        self.assertIsNone(self.tagged.related_object_type)
        response = self.client.get(self.tagged.get_absolute_url())
        self.assertContains(response, str(self.content_type))

    def test_sorting_by_a_demoted_relation_does_not_error(self):
        """
        `?sort=changed_object_type` names a relation the mirror holds as an id, and raised `FieldError`.

        Ordering by a foreign key orders by its column warm too, so retargeting to the id column gives the
        reader the same grouping the warm sort gives.
        """
        for sort in ("changed_object_type", "-changed_object_type"):
            with self.subTest(sort=sort):
                response = self.client.get(
                    f"{reverse('extras:objectchange_list')}?archive_period={PERIOD}&sort={sort}",
                    headers={"hx-request": "true"},
                )
                self.assertHttpStatus(response, 200)


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchivedJobResultPanelsTestCase(ArchiveAwareRetrieveGuardsTestCase):
    """
    A retained job result's log and console panels load through their own detail actions.

    Those actions look their instance up directly rather than through `get_object`, so the retention
    fallback did not reach them: the detail page rendered and every panel on it came back 404 and empty.
    The panels are most of what a job result detail page is for, so an empty one reads as the history
    having been lost.
    """

    def setUp(self):
        super().setUp()
        self.log_entries = [
            ArchivedJobLogEntry.objects.create(
                id=uuid.uuid4(),
                period_key=PERIOD,
                job_result_id=self.archived.pk,
                log_level=LogLevelChoices.LOG_INFO,
                grouping="run",
                message=f"archived log line {index}",
                created=datetime(int(PERIOD), 6, 1, 12, 0, index, tzinfo=dt_timezone.utc),
            )
            for index in range(3)
        ]
        self.console_entries = [
            ArchivedJobConsoleEntry.objects.create(
                id=uuid.uuid4(),
                period_key=PERIOD,
                job_result_id=self.archived.pk,
                output_type=JobConsoleEntryOutputTypeChoices.TYPE_STDOUT,
                text=f"archived console line {index}",
                timestamp=datetime(int(PERIOD), 6, 1, 12, 0, index, tzinfo=dt_timezone.utc),
            )
            for index in range(2)
        ]
        # A second retained result, so a panel cannot pass by showing everything in the period.
        self.other = ArchivedJobResult.objects.create(
            id=uuid.uuid4(),
            period_key=PERIOD,
            name="Other Archived Run",
            date_created=datetime(int(PERIOD), 6, 2, tzinfo=dt_timezone.utc),
            status=JobResultStatusChoices.STATUS_SUCCESS,
        )
        ArchivedJobLogEntry.objects.create(
            id=uuid.uuid4(),
            period_key=PERIOD,
            job_result_id=self.other.pk,
            log_level=LogLevelChoices.LOG_INFO,
            grouping="run",
            message="log line belonging to the other run",
            created=datetime(int(PERIOD), 6, 2, tzinfo=dt_timezone.utc),
        )

    def _get(self, suffix, **kwargs):
        return self.client.get(f"{self.archived.get_absolute_url()}{suffix}", **kwargs)

    def test_log_table_serves_a_retained_result(self):
        response = self._get("log-table/", headers={"hx-request": "true"})

        self.assertHttpStatus(response, 200)
        self.assertTrue(response.context["has_logs"])
        body = response.content.decode(response.charset)
        for entry in self.log_entries:
            self.assertIn(entry.message, body)
        self.assertNotIn("log line belonging to the other run", body)

    def test_log_table_filter_applies_within_retained_history(self):
        response = self._get("log-table/?q=log line 1", headers={"hx-request": "true"})

        body = response.content.decode(response.charset)
        self.assertIn("archived log line 1", body)
        self.assertNotIn("archived log line 2", body)

    def test_log_table_sorts_without_error(self):
        """The log table's columns name fields, but `job_result` on a mirror is an identifier column."""
        for sort in ("log_level", "-created", "message", "job_result"):
            with self.subTest(sort=sort):
                self.assertHttpStatus(self._get(f"log-table/?sort={sort}", headers={"hx-request": "true"}), 200)

    def test_console_output_serves_a_retained_result(self):
        response = self._get("job-console-entries/")

        self.assertHttpStatus(response, 200)
        body = response.content.decode(response.charset)
        for entry in self.console_entries:
            self.assertIn(entry.text, body)

    def test_console_export_serves_a_retained_result(self):
        response = self._get("export-job-console-entries/")

        self.assertHttpStatus(response, 200)
        body = response.content.decode(response.charset)
        for entry in self.console_entries:
            self.assertIn(entry.text, body)

    def test_export_logs_link_carries_the_period(self):
        """The link targets the warm API endpoint, which serves retained entries only for a named period."""
        response = self.client.get(self.archived.get_absolute_url())

        self.assertIn(f"archive_period={PERIOD}", response.content.decode(response.charset))

    def test_panels_still_require_the_cold_storage_permission(self):
        self.user.is_superuser = False
        self.user.save()
        self.add_permissions("extras.view_jobresult", "extras.view_joblogentry", "extras.view_jobconsoleentry")
        self.client.force_login(self.user)

        for suffix in ("log-table/", "job-console-entries/", "export-job-console-entries/"):
            with self.subTest(suffix=suffix):
                self.assertHttpStatus(self._get(suffix, headers={"hx-request": "true"}), 403)
