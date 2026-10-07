"""
Tests for the pages that show retained history.

Each of these asserts something that returns HTTP 200 when it is broken, which is why they exist. A
permission that quietly grants more than intended, a constraint that quietly grants everything, a write
route that quietly exists: none of them shows up in a status code the way a 500 does.
"""

from datetime import datetime, timezone as dt_timezone
import uuid

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError
from django.test import override_settings
from django.urls import NoReverseMatch, reverse

from nautobot.core.testing import TestCase
from nautobot.extras.choices import ObjectChangeActionChoices
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    ObjectChange,
)
from nautobot.extras.tests.test_changelog_archive_base import clear_archive
from nautobot.users.models import ObjectPermission

WHEN = datetime(2021, 6, 1, tzinfo=dt_timezone.utc)


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
