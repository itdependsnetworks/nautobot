"""
The period selector, and the view state a reader carries across a period switch.

Selecting a period has to keep filters, sorting and paging, and must not leave warm affordances behind on
records that cannot be written to.
"""

from datetime import datetime, timezone as dt_timezone
import uuid

from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse

from nautobot.core.constants import COLD_STORAGE_PERMISSION
from nautobot.core.testing import TestCase
from nautobot.extras.choices import (
    JobResultStatusChoices,
    ObjectChangeActionChoices,
)
from nautobot.extras.models import (
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    ArchiveSegment,
    ObjectChange,
)
from nautobot.extras.tests.test_changelog_archive_base import ArchiveReadFixtureMixin, PERIOD


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchivePeriodSelectorTestCase(ArchiveReadFixtureMixin, TestCase):
    """
    The period selector on the change log list view.

    It renders nothing without the cold-storage permission, which is what lets templates include it
    unconditionally.
    """

    def setUp(self):
        super().setUp()
        ArchivedObjectChange.objects.all().delete()
        ArchiveSegment.objects.all().delete()
        self.url = reverse("extras:objectchange_list")

    def test_selector_is_absent_without_the_permission(self):
        self.add_permissions("extras.view_objectchange")
        self.build_period()

        response = self.client.get(self.url)

        self.assertHttpStatus(response, 200)
        self.assertNotIn("archive-period-dropdown", response.content.decode(response.charset))

    def test_selector_lists_periods_with_the_permission(self):
        self.add_permissions("extras.view_objectchange")
        self.grant_cold_storage()
        self.build_period(period_key="2020")
        self.build_period(period_key="2021")

        response = self.client.get(self.url)

        self.assertHttpStatus(response, 200)
        content = response.content.decode(response.charset)
        self.assertIn("archive-period-dropdown", content)
        self.assertIn("archive_period=2021", content)
        self.assertIn("archive_period=2020", content)

    def test_selecting_a_period_shows_that_period(self):
        """
        The rows arrive on the HTMX request, not the initial page.

        A list view renders its table empty and then fetches it, so asserting against the first response
        would pass whether or not the archive was reached.
        """
        self.add_permissions("extras.view_objectchange")
        self.grant_cold_storage()
        self.build_period(rows=2)

        response = self.client.get(f"{self.url}?archive_period={PERIOD}", headers={"hx-request": "true"})

        self.assertHttpStatus(response, 200)
        self.assertIn("Archived Widget", response.content.decode(response.charset))

    def test_warm_records_are_absent_when_a_period_is_selected(self):
        """One period at a time: selecting a period replaces warm storage rather than adding to it."""
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

        response = self.client.get(f"{self.url}?archive_period={PERIOD}", headers={"hx-request": "true"})

        content = response.content.decode(response.charset)
        self.assertIn("Archived Widget", content)
        self.assertNotIn("Warm Widget", content)

    def test_selecting_a_period_without_the_permission_is_refused(self):
        self.add_permissions("extras.view_objectchange")
        self.build_period()

        response = self.client.get(f"{self.url}?archive_period={PERIOD}")

        self.assertNotEqual(response.status_code, 200)

    def test_period_is_not_persisted_into_a_saved_view(self):
        """
        `archive_period` is a non-filter parameter on purpose.

        As a filterset filter it would be captured into a SavedView, and that view would keep reaching
        retained history after the permission was revoked.
        """
        from nautobot.core.views.mixins import ObjectListViewMixin

        self.assertIn("archive_period", ObjectListViewMixin.non_filter_params)

    def test_archive_context_is_empty_but_present_when_nothing_to_offer(self):
        """So a template can include the selector with no conditional of its own."""
        from django.test import RequestFactory

        from nautobot.extras.archive_reads import archive_context

        request = RequestFactory().get("/extras/object-changes/")
        request.user = self.user
        context = archive_context(ObjectChange, request)

        self.assertEqual(
            set(context),
            {
                "archive_periods",
                "archive_period",
                "archive_freshness",
                "archive_show_counts",
                "archive_warm_url",
                "archive_dropped_filters",
            },
        )
        self.assertEqual(list(context["archive_periods"]), [])
        self.assertIsNone(context["archive_period"])


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchiveObjectChangeLogTabTestCase(ArchiveReadFixtureMixin, TestCase):
    """
    An object's change log tab has to honor the selected period, not merely offer the selector.

    Both assertions here failed in manual testing: the dropdown rendered while the table kept showing warm
    records, and the period's whole-period count sat beside one object's history as if it were that
    object's count.
    """

    def setUp(self):
        super().setUp()
        ArchivedObjectChange.objects.all().delete()
        ArchiveSegment.objects.all().delete()
        self.content_type = ContentType.objects.get_for_model(ObjectChange)
        # Any object with a change log tab will do; ObjectChange itself has one.
        self.target = ObjectChange.objects.create(
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type=self.content_type,
            changed_object_id=uuid.uuid4(),
            object_repr="Warm Target",
            object_data={},
            request_id=uuid.uuid4(),
            user_name="alice",
            change_context="orm",
        )

    def archived_change_for(self, target, *, period_key=PERIOD, repr_text="Archived For Target"):
        segment_start = datetime(int(period_key), 1, 1, tzinfo=dt_timezone.utc)
        ArchiveSegment.objects.get_or_create(
            model_label="extras.objectchange",
            period_key=period_key,
            defaults={
                "label": period_key,
                "time_start": segment_start,
                "time_end": datetime(int(period_key) + 1, 1, 1, tzinfo=dt_timezone.utc),
                "row_count": 1,
                "is_period_closed": True,
            },
        )
        return ArchivedObjectChange.objects.create(
            id=uuid.uuid4(),
            period_key=period_key,
            time=datetime(int(period_key), 6, 1, tzinfo=dt_timezone.utc),
            user_name="alice",
            request_id=uuid.uuid4(),
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type_id=self.content_type.pk,
            changed_object_id=target.pk,
            change_context="orm",
            object_repr=repr_text,
            object_data={},
        )

    def test_helper_returns_warm_history_by_default(self):
        from nautobot.extras.archive_reads import object_change_history

        self.archived_change_for(self.target)

        class _Request:
            GET = {}

        request = _Request()
        request.user = self.user
        queryset, period_key = object_change_history(self.target, self.content_type, request)

        self.assertIsNone(period_key)
        self.assertEqual(queryset.model, ObjectChange)

    def test_helper_returns_the_selected_period_scoped_to_the_object(self):
        from nautobot.extras.archive_reads import object_change_history

        self.grant_cold_storage()
        mine = self.archived_change_for(self.target)
        # Same period, a different object: must not appear.
        other = ObjectChange.objects.create(
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type=self.content_type,
            changed_object_id=uuid.uuid4(),
            object_repr="Other",
            object_data={},
            request_id=uuid.uuid4(),
            user_name="bob",
            change_context="orm",
        )
        self.archived_change_for(other, repr_text="Archived For Other")

        class _Request:
            GET = {"archive_period": PERIOD}

        request = _Request()
        request.user = self.user
        queryset, period_key = object_change_history(self.target, self.content_type, request)

        self.assertEqual(period_key, PERIOD)
        self.assertEqual(queryset.model, ArchivedObjectChange)
        self.assertEqual([change.pk for change in queryset], [mine.pk])

    def test_period_counts_are_hidden_on_object_scoped_views(self):
        """A whole-period count beside one object's history reads as that object's count."""
        from django.test import RequestFactory

        from nautobot.extras.archive_reads import archive_context

        self.grant_cold_storage()
        self.archived_change_for(self.target)
        request = RequestFactory().get("/extras/object-changes/")
        request.user = self.user

        self.assertFalse(archive_context(ObjectChange, request, show_counts=False)["archive_show_counts"])
        self.assertTrue(archive_context(ObjectChange, request)["archive_show_counts"])


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchivePeriodSurvivesNavigationTestCase(ArchiveReadFixtureMixin, TestCase):
    """
    The selected period has to survive every way of navigating within the list view.

    Losing it silently returns the reader to warm storage, which reads as the records having changed rather
    than the view. Sort links and the paginator preserve the whole query string already; a GET form submits
    only its own fields, so the filter forms have to carry it deliberately.
    """

    def setUp(self):
        super().setUp()
        ArchivedObjectChange.objects.all().delete()
        ArchiveSegment.objects.all().delete()
        self.url = reverse("extras:objectchange_list")
        self.add_permissions("extras.view_objectchange")
        self.grant_cold_storage()
        self.build_period(rows=2)

    def test_filter_forms_carry_the_period(self):
        """The reported bug: filtering while viewing a period dropped it from the URL."""
        response = self.client.get(f"{self.url}?archive_period={PERIOD}")
        content = response.content.decode(response.charset)

        self.assertHttpStatus(response, 200)
        self.assertIn(
            f'<input type="hidden" name="archive_period" value="{PERIOD}">',
            content,
            "the filter forms must repeat the period, or submitting them loses it",
        )

    def test_sort_links_carry_the_period(self):
        response = self.client.get(f"{self.url}?archive_period={PERIOD}", headers={"hx-request": "true"})
        content = response.content.decode(response.charset)

        sort_links = [href for href in content.split('href="')[1:] if "sort=" in href.split('"')[0]]
        self.assertTrue(sort_links, "expected sortable column headers")
        for href in sort_links:
            self.assertIn(f"archive_period={PERIOD}", href.split('"')[0])

    def test_paginator_carries_the_period(self):
        response = self.client.get(f"{self.url}?archive_period={PERIOD}")
        self.assertIn(
            f'<input type="hidden" name="archive_period" value="{PERIOD}"',
            response.content.decode(response.charset),
        )

    def test_preserved_params_do_not_include_page(self):
        """Changing a filter should return to the first page, not one that may no longer exist."""
        from nautobot.core.templatetags.form_helpers import PRESERVED_VIEW_STATE_PARAMS

        self.assertNotIn("page", PRESERVED_VIEW_STATE_PARAMS)
        self.assertIn("archive_period", PRESERVED_VIEW_STATE_PARAMS)

    def test_nothing_is_emitted_when_no_period_is_selected(self):
        response = self.client.get(self.url)
        self.assertNotIn(
            'name="archive_period"', response.content.decode(response.charset), "no period, nothing to carry"
        )


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchivePeriodSwitchPreservesViewTestCase(ArchiveReadFixtureMixin, TestCase):
    """
    Switching period means "show me the same thing, for that period".

    So filters and sorting carry over. Two things do not: `page`, because a different period has a
    different number of records, and any filter the target cannot support.
    """

    def setUp(self):
        super().setUp()
        ArchivedObjectChange.objects.all().delete()
        ArchiveSegment.objects.all().delete()
        self.build_period(period_key="2023")
        self.build_period(period_key="2024")

    def build_request(self, query):
        from django.test import RequestFactory

        request = RequestFactory().get(f"/extras/object-changes/{query}")
        request.user = self.user
        return request

    def test_sort_and_supported_filters_carry_over(self):
        from nautobot.extras.archive_reads import period_switch_url

        request = self.build_request("?sort=user_name&user_name=carol")
        url, dropped = period_switch_url(request, "2024", ObjectChange)

        self.assertIn("sort=user_name", url)
        self.assertIn("user_name=carol", url)
        self.assertIn("archive_period=2024", url)
        self.assertEqual(dropped, [])

    def test_page_is_not_carried_over(self):
        """A different period has a different number of records, so the page number is meaningless."""
        from nautobot.extras.archive_reads import period_switch_url

        request = self.build_request("?page=3&sort=action")
        url, _dropped = period_switch_url(request, "2024", ObjectChange)

        self.assertNotIn("page=", url)
        self.assertIn("sort=action", url)

    def test_unsupported_filter_is_dropped_and_reported(self):
        """
        Carrying `user` into a period would yield "invalid filters" and an empty table.

        Confusing when the reader only meant to change period, so it is dropped and named instead.
        """
        from nautobot.extras.archive_reads import period_switch_url

        request = self.build_request("?user=abc123&sort=action")
        url, dropped = period_switch_url(request, "2024", ObjectChange)

        self.assertNotIn("user=abc123", url)
        self.assertIn("sort=action", url)
        self.assertEqual(dropped, ["user"])

    def test_returning_to_warm_keeps_every_filter(self):
        """Warm storage supports every filter, so nothing needs dropping on the way back."""
        from nautobot.extras.archive_reads import period_switch_url

        request = self.build_request("?user=abc123&sort=action&archive_period=2024")
        url, dropped = period_switch_url(request, None, ObjectChange)

        self.assertIn("user=abc123", url)
        self.assertIn("sort=action", url)
        self.assertNotIn("archive_period", url)
        self.assertEqual(dropped, [])

    def test_selected_period_freshness_is_the_selected_one(self):
        """
        Regression: building each period's URL in a loop clobbered the selected segment, so the note
        described the last period in the list instead of the one being viewed.
        """
        from nautobot.extras.archive_reads import archive_context

        self.grant_cold_storage()
        request = self.build_request("?archive_period=2024")
        context = archive_context(ObjectChange, request)

        self.assertEqual(context["archive_period"], "2024")
        self.assertEqual(context["archive_freshness"]["period_label"], "2024")

    def test_every_period_gets_a_switch_url(self):
        from nautobot.extras.archive_reads import archive_context

        self.grant_cold_storage()
        context = archive_context(ObjectChange, self.build_request("?sort=action"))

        self.assertTrue(context["archive_periods"])
        for entry in context["archive_periods"]:
            self.assertIn(f"archive_period={entry.period_key}", entry.switch_url)
            self.assertIn("sort=action", entry.switch_url)
        self.assertIn("sort=action", context["archive_warm_url"])


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchivedRelationRenderingTestCase(ArchiveReadFixtureMixin, TestCase):
    """
    A mirror holds its references as identifier columns, and a lot of code reaches for the relation.

    Each of these was a 500 or a silent loss of information found by exercising the real pages.
    """

    def test_unknown_relation_resolves_to_none_rather_than_raising(self):
        """Serializers, tables, and templates all reach for `job_result` by name."""
        entry = ArchivedJobLogEntry(period_key=PERIOD, job_result_id=uuid.uuid4())
        self.assertIsNone(entry.job_result)

    def test_a_genuine_typo_still_raises(self):
        """The fallback is narrow on purpose: only names backed by a real `<name>_id` field resolve."""
        entry = ArchivedJobLogEntry(period_key=PERIOD, job_result_id=uuid.uuid4())
        with self.assertRaises(AttributeError):
            entry.job_reslut  # deliberate typo

    def test_api_keeps_the_referent_identifier(self):
        """
        Rendering the relation as null would lose the ability to correlate a log entry to its run.

        The identifying half of what a warm response carries is kept; `url` is not, because the referent
        may no longer exist.
        """
        from nautobot.extras.api.serializers import JobLogEntrySerializer

        job_result_id = uuid.uuid4()
        entry = ArchivedJobLogEntry(
            id=uuid.uuid4(),
            period_key=PERIOD,
            job_result_id=job_result_id,
            log_level="info",
            message="hello",
            created=datetime(2021, 6, 1, tzinfo=dt_timezone.utc),
        )
        data = JobLogEntrySerializer(entry, context={"request": None}).data

        self.assertEqual(data["job_result"]["id"], str(job_result_id))
        self.assertEqual(data["job_result"]["object_type"], "extras.jobresult")

    def test_uncovered_model_ignores_the_parameter(self):
        """
        A stray `archive_period` carried over from another page must not error.

        ArchiveSegment has no retained history of its own, and this 500'd before.
        """
        self.add_permissions("extras.view_archivesegment")
        response = self.client.get(f"{reverse('extras:archivesegment_list')}?archive_period={PERIOD}")
        self.assertHttpStatus(response, 200)

    def test_unknown_period_on_a_covered_model_is_reported_not_a_server_error(self):
        self.add_permissions("extras.view_objectchange", COLD_STORAGE_PERMISSION)
        response = self.client.get(f"{reverse('extras:objectchange_list')}?archive_period=1999")
        self.assertHttpStatus(response, 200)


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchivedRowsLinkNowhereWarmTestCase(ArchiveReadFixtureMixin, TestCase):
    """
    Category test: no link in a rendered archived row may address something that cannot serve it.

    Five separate bugs shared one shape -- something downstream of the period swap reversed a URL, followed
    a relation, or resolved a permission from the warm model. A sweep for non-200 responses catches the
    ones that raise; it cannot catch a rendered link that 404s only when clicked, which is how the
    delete-link bug reached manual testing.

    This walks every covered model with a list view, as a superuser so nothing is hidden by permissions,
    and asserts that every link addressing a retained record resolves to a view that can serve it.

    HISTORY, and a caution: this began as the blunter assertion that no link may carry a retained record's
    key at all, with a note that it was more aggressive than the requirement and would fail if a read-only
    detail view for retained records was ever added. That happened one commit later, and it failed exactly
    as predicted. It is now narrowed to what actually matters -- a link must resolve and serve -- rather
    than deleted. Keep that distinction if it fires again: the question is never "does this link mention an
    archived record", it is "can whatever it points at serve it".

    Note that a retained record's URL is its *warm* model's detail route. It keeps the primary key it had
    before rotation, so the same URL serves it either way and a link made earlier does not rot.
    """

    def setUp(self):
        super().setUp()
        for model in (ArchivedObjectChange, ArchivedJobResult, ArchiveSegment):
            model.objects.all().delete()
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        self.archived_pks = {}
        self._build("extras.objectchange", self._archived_object_change)
        self._build("extras.jobresult", self._archived_job_result)

    def _segment(self, model_label):
        ArchiveSegment.objects.get_or_create(
            model_label=model_label,
            period_key=PERIOD,
            defaults={
                "label": PERIOD,
                "time_start": datetime(int(PERIOD), 1, 1, tzinfo=dt_timezone.utc),
                "time_end": datetime(int(PERIOD) + 1, 1, 1, tzinfo=dt_timezone.utc),
                "row_count": 1,
                "is_period_closed": True,
            },
        )

    def _build(self, model_label, factory):
        self._segment(model_label)
        self.archived_pks[model_label] = str(factory().pk)

    def _archived_object_change(self):
        return ArchivedObjectChange.objects.create(
            id=uuid.uuid4(),
            period_key=PERIOD,
            time=datetime(int(PERIOD), 6, 1, tzinfo=dt_timezone.utc),
            user_name="alice",
            request_id=uuid.uuid4(),
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type_id=ContentType.objects.get_for_model(ObjectChange).pk,
            changed_object_id=uuid.uuid4(),
            change_context="orm",
            object_repr="Archived Widget",
            object_data={},
        )

    def _archived_job_result(self):
        return ArchivedJobResult.objects.create(
            id=uuid.uuid4(),
            period_key=PERIOD,
            name="Archived Run",
            date_created=datetime(int(PERIOD), 6, 1, tzinfo=dt_timezone.utc),
            status=JobResultStatusChoices.STATUS_SUCCESS,
        )

    def covered_list_views(self):
        """Every covered model that has a list view, paired with the key of its retained record."""
        from django.urls import NoReverseMatch

        from nautobot.core.utils.lookup import get_route_for_model
        from nautobot.extras.registry import registry

        for model_label in registry["changelog_archive_models"]:
            if model_label not in self.archived_pks:
                continue  # no list view, or no fixture built for it
            try:
                url = reverse(get_route_for_model(model_label, "list"))
            except NoReverseMatch:
                # No list view for this model, so there is nothing rendered to check.
                continue
            yield model_label, url, self.archived_pks[model_label]

    def test_every_link_to_a_retained_record_resolves(self):
        """
        A link carrying a retained record's key must point at a view that can serve it.

        The detail route can: it falls back to retention when the key is not in warm storage. An edit or
        delete route cannot, because it has no such fallback and nothing to write to.
        """
        from django.urls import resolve, Resolver404

        checked = 0
        for model_label, url, archived_pk in self.covered_list_views():
            with self.subTest(model=model_label):
                response = self.client.get(f"{url}?archive_period={PERIOD}", headers={"hx-request": "true"})
                self.assertHttpStatus(response, 200)
                content = response.content.decode(response.charset)
                hrefs = [part.split('"')[0] for part in content.split('href="')[1:]]
                for href in hrefs:
                    if archived_pk not in href:
                        continue
                    path = href.split("?")[0]
                    try:
                        resolve(path)
                    except Resolver404:
                        self.fail(f"{href} addresses retained {model_label} but resolves to no view")
                    # It resolves; confirm it actually serves the record rather than 404ing on lookup.
                    self.assertHttpStatus(self.client.get(href), 200)
                    checked += 1
        self.assertGreater(
            checked, 0, "expected retained rows to link to their detail view; has get_absolute_url regressed?"
        )

    def test_no_write_routes_are_offered_for_retained_records(self):
        """The narrow form of the above, and the part that is unambiguously required."""
        checked = 0
        for model_label, url, _pk in self.covered_list_views():
            with self.subTest(model=model_label):
                response = self.client.get(f"{url}?archive_period={PERIOD}", headers={"hx-request": "true"})
                content = response.content.decode(response.charset)
                for route in ("/edit/", "/delete/"):
                    self.assertNotIn(route, content, f"{route} offered for retained {model_label}")
                self.assertNotIn('name="pk"', content, f"bulk select offered for retained {model_label}")
                checked += 1
        self.assertGreater(checked, 0)
