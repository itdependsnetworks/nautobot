"""
Tests for the pages that show retained history.

Each of these asserts something that returns HTTP 200 when it is broken, which is why they exist. A
permission that quietly grants more than intended, a constraint that quietly grants everything, a write
route that quietly exists: none of them shows up in a status code the way a 500 does. Neither does a
record served at two URLs, which renders its panels at only one of them, because
`Tab.should_render_content` compares `request.path` against `object.get_absolute_url()` and the other URL
returns a complete page with every panel missing.
"""

from datetime import datetime, timezone as dt_timezone
import uuid

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError
from django.test import override_settings
from django.urls import NoReverseMatch, reverse

from nautobot.core.testing import TestCase
from nautobot.extras.choices import JobResultStatusChoices, ObjectChangeActionChoices
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    JobResult,
    ObjectChange,
)
from nautobot.extras.tests.test_changelog_archive_base import clear_archive
from nautobot.users.models import ObjectPermission

WHEN = datetime(2021, 6, 1, tzinfo=dt_timezone.utc)


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class WarmUrlRedirectTestCase(TestCase):
    """A primary key the warm table no longer has belongs to a record that was rotated, not to nothing."""

    user_permissions = (
        "extras.view_objectchange",
        "extras.view_jobresult",
        "extras.view_archivedobjectchange",
        "extras.view_archivedjobresult",
    )

    def setUp(self):
        super().setUp()
        clear_archive(ArchivedObjectChange, ArchivedJobResult)
        self.addCleanup(clear_archive, ArchivedObjectChange, ArchivedJobResult)
        self.change = ArchivedObjectChange.objects.create(
            id=uuid.uuid4(),
            time=WHEN,
            user_name="alice",
            request_id=uuid.uuid4(),
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type_id=ContentType.objects.get_for_model(ObjectChange).pk,
            changed_object_id=uuid.uuid4(),
            change_context="orm",
            object_repr="Archived Widget",
            object_data={},
        )
        self.result = ArchivedJobResult.objects.create(
            id=uuid.uuid4(),
            name="retained-job",
            user_name="alice",
            status=JobResultStatusChoices.STATUS_SUCCESS,
            date_created=WHEN,
            date_started=WHEN,
            date_done=WHEN,
            celery_kwargs={},
        )

    # Redirects from the warm URL

    def test_warm_change_url_redirects_to_the_retained_page(self):
        """A link saved before rotation names a primary key the warm table no longer has."""
        response = self.client.get(reverse("extras:objectchange", kwargs={"pk": self.change.pk}))

        self.assertRedirects(response, self.change.get_absolute_url())

    def test_warm_job_result_url_redirects_to_the_retained_page(self):
        response = self.client.get(reverse("extras:jobresult", kwargs={"pk": self.result.pk}))

        self.assertRedirects(response, self.result.get_absolute_url())

    def test_a_warm_record_is_still_served_at_its_own_url(self):
        """The redirect applies only to a primary key the warm table has lost, never to a live record."""
        warm = JobResult.objects.create(name="warm-job", celery_kwargs={})

        response = self.client.get(warm.get_absolute_url())

        self.assertEqual(response.status_code, 200)

    def test_an_unknown_primary_key_is_still_a_404(self):
        response = self.client.get(reverse("extras:objectchange", kwargs={"pk": uuid.uuid4()}))

        self.assertEqual(response.status_code, 404)

    @override_settings(CHANGELOG_ARCHIVE_ENABLED=False)
    def test_no_redirect_while_retention_is_off(self):
        """With the capability off the view behaves exactly as it did before retention existed."""
        response = self.client.get(reverse("extras:objectchange", kwargs={"pk": self.change.pk}))

        self.assertEqual(response.status_code, 404)


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class RetainedChangeDetailTestCase(TestCase):
    """The panels a retained change record shares with the warm one."""

    user_permissions = ("extras.view_archivedobjectchange",)

    def setUp(self):
        super().setUp()
        clear_archive(ArchivedObjectChange)
        self.addCleanup(clear_archive, ArchivedObjectChange)
        self.content_type = ContentType.objects.get_for_model(ObjectChange)
        self.request_id = uuid.uuid4()
        self.object_id = uuid.uuid4()
        self.earlier = self.make_change({"name": "Widget", "description": "before"}, WHEN)
        self.change = self.make_change({"name": "Widget", "description": "after"}, WHEN.replace(hour=12))

    def make_change(self, data, when):
        return ArchivedObjectChange.objects.create(
            id=uuid.uuid4(),
            time=when,
            user_name="alice",
            request_id=self.request_id,
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type_id=self.content_type.pk,
            changed_object_id=self.object_id,
            change_context="orm",
            object_repr="Archived Widget",
            object_data={},
            object_data_v2=data,
        )

    def test_the_difference_panel_loads_the_diff_viewer(self):
        """
        The panel renders a container that `js/editor.js` fills.

        Without a retrieve template extending the warm one that script never loads, and the panel is an
        empty box on a page that returns 200.
        """
        body = self.client.get(self.change.get_absolute_url()).content.decode()

        self.assertIn("nb-editor-container", body)
        self.assertIn("js/editor.js", body)

    def test_the_diff_compares_against_the_previous_change_to_the_same_object(self):
        snapshots = self.change.get_snapshots()

        self.assertEqual(snapshots["prechange"]["description"], "before")
        self.assertEqual(snapshots["postchange"]["description"], "after")
        self.assertEqual(snapshots["differences"]["added"], {"description": "after"})

    def test_previous_and_next_navigate_between_retained_records(self):
        self.assertEqual(self.change.get_prev_change(), self.earlier)
        self.assertEqual(self.earlier.get_next_change(), self.change)

    def test_a_record_with_no_predecessor_does_not_raise(self):
        self.assertIsNone(self.earlier.get_prev_change())
        self.assertIsNotNone(self.earlier.get_snapshots())


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class RetainedJobResultSummaryTestCase(TestCase):
    """The summary panel a retained job result shares with the warm one."""

    user_permissions = ("extras.view_archivedjobresult",)

    def setUp(self):
        super().setUp()
        clear_archive(ArchivedJobResult)
        self.addCleanup(clear_archive, ArchivedJobResult)
        self.result = ArchivedJobResult.objects.create(
            id=uuid.uuid4(),
            name="retained-job",
            user_name="alice",
            status=JobResultStatusChoices.STATUS_SUCCESS,
            date_created=WHEN,
            date_started=WHEN,
            date_done=WHEN.replace(minute=2),
            worker="celery@worker-01",
            celery_kwargs={"queue": "priority"},
        )

    def test_the_summary_panel_is_the_warm_one(self):
        body = self.client.get(self.result.get_absolute_url()).content.decode()

        self.assertIn("SUMMARY OF RESULTS", body.upper())

    def test_the_summary_panel_is_the_class_the_warm_page_uses(self):
        """
        Not cosmetic: `JobResultSummaryPanel` decides how `result` and `duration` render.

        A plain `ObjectFieldsPanel` renders a stored `result` as raw JSON wherever the row is shown.
        """
        from nautobot.extras.views import ArchivedJobResultUIViewSet, JobResultSummaryPanel

        panel = next(
            p
            for p in ArchivedJobResultUIViewSet.object_detail_content.tabs[0].panels
            if p.label == "Summary of Results"
        )

        self.assertIsInstance(panel, JobResultSummaryPanel)

    def test_a_stored_result_renders_in_the_summary(self):
        self.result.result = {"devices_checked": 12}
        self.result.save()

        body = self.client.get(self.result.get_absolute_url()).content.decode()

        self.assertIn("devices_checked", body)

    def test_cancel_details_is_hidden_on_a_job_that_was_not_canceled(self):
        """The warm panel hides itself the same way, so an uncanceled job shows no empty rows."""
        body = self.client.get(self.result.get_absolute_url()).content.decode()

        self.assertNotIn("CANCEL DETAILS", body.upper())

    def test_the_derived_fields_read_from_what_was_stored(self):
        self.assertEqual(self.result.queue, "priority")
        self.assertEqual(self.result.duration, "2 minutes, 0.00 seconds")

    def test_the_fields_that_cannot_be_recovered_are_empty_not_wrong(self):
        """
        The job's description belongs to the `Job`, which is not archived, and output files are deleted
        with the warm record. Both render empty instead of showing something from today.
        """
        self.assertIsNone(self.result.job_description)
        self.assertEqual(self.result.files, [])


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class RetainedHistoryPermissionTestCase(TestCase):
    """Retained history is gated by its own ordinary `view` permission, granted to nobody by default."""

    user_permissions = ("extras.view_objectchange",)

    def setUp(self):
        super().setUp()
        clear_archive(ArchivedObjectChange)
        self.addCleanup(clear_archive, ArchivedObjectChange)
        self.change = ArchivedObjectChange.objects.create(
            id=uuid.uuid4(),
            time=WHEN,
            user_name="alice",
            request_id=uuid.uuid4(),
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type_id=ContentType.objects.get_for_model(ObjectChange).pk,
            changed_object_id=uuid.uuid4(),
            change_context="orm",
            object_repr="Archived Widget",
            object_data={},
        )

    def test_the_change_log_permission_does_not_grant_retained_history(self):
        response = self.client.get(reverse("extras:archivedobjectchange_list"))

        self.assertEqual(response.status_code, 403)

    def test_a_warm_url_is_not_redirected_to_a_page_the_user_may_not_see(self):
        """Without the retained permission the record is not found, so the link 404s as any other would."""
        response = self.client.get(reverse("extras:objectchange", kwargs={"pk": self.change.pk}))

        self.assertEqual(response.status_code, 404)


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class RetainedHistoryObjectConstraintTestCase(TestCase):
    """
    What an object permission's constraints do against a retained record.

    Documented behaviour, pinned here because both halves are easy to get wrong in opposite directions:
    assuming constraints are ignored would overstate what a reader can see, and assuming they all work
    would send operators to copy a constraint written for the warm model, which cannot resolve.
    """

    def setUp(self):
        super().setUp()
        clear_archive(ArchivedObjectChange)
        self.addCleanup(clear_archive, ArchivedObjectChange)
        self.content_type = ContentType.objects.get_for_model(ObjectChange)
        for name in ("alice", "bob"):
            ArchivedObjectChange.objects.create(
                id=uuid.uuid4(),
                time=WHEN,
                user_name=name,
                request_id=uuid.uuid4(),
                action=ObjectChangeActionChoices.ACTION_UPDATE,
                changed_object_type_id=self.content_type.pk,
                changed_object_id=uuid.uuid4(),
                change_context="orm",
                object_repr=f"Widget touched by {name}",
                object_data={},
            )

    def constrain(self, constraints):
        """Grant the user `view` on retained change records under these constraints."""
        permission = ObjectPermission.objects.create(
            name=f"retained {constraints}", actions=["view"], constraints=constraints
        )
        permission.object_types.set([ContentType.objects.get_for_model(ArchivedObjectChange)])
        permission.users.set([self.user])
        if hasattr(self.user, "_object_perm_cache"):
            del self.user._object_perm_cache

    def test_a_constraint_on_a_stored_column_is_applied(self):
        self.constrain({"user_name": "alice"})

        visible = ArchivedObjectChange.objects.restrict(self.user, "view")

        self.assertEqual([record.user_name for record in visible], ["alice"])

    def test_a_constraint_on_the_stored_content_type_id_is_applied(self):
        """The workaround the documentation gives for constraining by object type."""
        self.constrain({"changed_object_type_id": self.content_type.pk})

        visible = ArchivedObjectChange.objects.restrict(self.user, "view")

        self.assertEqual(visible.count(), 2)

    def test_a_constraint_that_traverses_a_relation_cannot_be_resolved(self):
        """
        `restrict()` raises while building the queryset, instead of returning everything.

        That is the safe direction, and the reason the documentation says to write a separate object
        permission for retained records in place of reusing the warm model's.
        """
        self.constrain({"user__username": "alice"})

        with self.assertRaises(FieldError):
            ArchivedObjectChange.objects.restrict(self.user, "view")


class RetainedHistoryReadOnlyTestCase(TestCase):
    """Retained history offers no write surface at all."""

    def test_no_write_url_resolves_for_a_retained_record(self):
        """Rotation writes these records and nothing else does, so there is nothing to edit or delete."""
        for action in ("edit", "delete", "add"):
            with self.subTest(action=action):
                with self.assertRaises(NoReverseMatch):
                    reverse(f"extras:archivedobjectchange_{action}", kwargs={"pk": uuid.uuid4()})

    def test_the_models_declare_only_a_view_permission(self):
        for model in (ArchivedObjectChange, ArchivedJobResult, ArchivedJobLogEntry, ArchivedJobConsoleEntry):
            with self.subTest(model=model.__name__):
                self.assertEqual(model._meta.default_permissions, ("view",))
