from unittest import mock
import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase

from nautobot.core.celery import app
from nautobot.core.testing import get_job_class_and_model, TransactionTestCase
from nautobot.core.utils.lookup import get_changes_for_model
from nautobot.dcim.models import (
    DeviceType,
    DeviceTypeToSoftwareImageFile,
    Location,
    LocationType,
    Manufacturer,
    Platform,
    SoftwareImageFile,
    SoftwareVersion,
)
from nautobot.extras.choices import ObjectChangeActionChoices, ObjectChangeEventContextChoices
from nautobot.extras.context_managers import (
    deferred_change_logging_for_bulk_operation,
    web_request_context,
    without_delete_change_logging,
)
from nautobot.extras.models import Contact, ContactAssociation, JobHook, Note, Role, Status, Webhook
from nautobot.extras.utils import bulk_delete_with_bulk_change_logging

# Use the proper swappable User model
User = get_user_model()


class WebRequestContextTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="jacob",
            email="jacob@example.com",
            password="top_secret",  # noqa: S106  # hardcoded-password-func-arg -- ok as this is test code only
        )

        location_ct = ContentType.objects.get_for_model(Location)
        MOCK_URL = "http://localhost/"
        MOCK_SECRET = "LOOKATMEIMASECRETSTRING"  # noqa: S105  # hardcoded-password-string -- ok as this is test code

        webhooks = Webhook.objects.bulk_create(
            (
                Webhook(
                    name="Location Create Webhook",
                    type_create=True,
                    payload_url=MOCK_URL,
                    secret=MOCK_SECRET,
                ),
            )
        )
        for webhook in webhooks:
            webhook.content_types.set([location_ct])

        app.control.purge()  # Begin each test with an empty queue

    def test_user_object_type_error(self):
        with self.assertRaises(TypeError):
            with web_request_context("a string is not a user object"):
                pass

    def test_change_log_created(self):
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        with web_request_context(self.user):
            location = Location(name="Test Location 1", location_type=location_type, status=location_status)
            location.save()

        location = Location.objects.get(name="Test Location 1")
        oc_list = get_changes_for_model(location).order_by("pk").filter(changed_object_id=location.id)
        self.assertEqual(len(oc_list), 1)
        self.assertEqual(oc_list[0].changed_object, location)
        self.assertEqual(oc_list[0].action, ObjectChangeActionChoices.ACTION_CREATE)

    @mock.patch("nautobot.extras.jobs.enqueue_job_hooks", return_value=(True, None))
    @mock.patch("nautobot.extras.context_managers.enqueue_webhooks", return_value=None)
    def test_create_then_delete(self, mock_enqueue_webhooks, mock_enqueue_job_hooks):
        """Test that a create followed by a delete is logged as two changes"""
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        with web_request_context(self.user):
            location = Location(name="Test Location 1", location_type=location_type, status=location_status)
            location.save()
            location_pk = location.pk
            location.delete()

        location = Location.objects.filter(pk=location_pk)
        self.assertFalse(location.exists())
        oc_list = get_changes_for_model(Location).filter(changed_object_id=location_pk).order_by("time")
        self.assertEqual(len(oc_list), 2)
        self.assertEqual(oc_list[0].action, ObjectChangeActionChoices.ACTION_CREATE)
        self.assertEqual(oc_list[1].action, ObjectChangeActionChoices.ACTION_DELETE)
        mock_enqueue_job_hooks.assert_has_calls(
            [
                mock.call(oc_list[0], may_reload_jobs=True, jobhook_queryset=None),
                mock.call(oc_list[1], may_reload_jobs=False, jobhook_queryset=None),
            ],
        )
        mock_enqueue_webhooks.assert_has_calls(
            [
                mock.call(oc_list[0], snapshots=oc_list[0].get_snapshots(), webhook_queryset=None),
                mock.call(oc_list[1], snapshots=oc_list[1].get_snapshots(), webhook_queryset=None),
            ]
        )

    def test_update_then_delete(self):
        """Test that an update followed by a delete is logged as a single delete"""
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        with web_request_context(self.user):
            location = Location(name="Test Location 1", location_type=location_type, status=location_status)
            location.save()
            location_pk = location.pk
        with web_request_context(self.user):
            location.description = "changed"
            location.save()
            location.delete()

        location = Location.objects.filter(pk=location_pk)
        self.assertFalse(location.exists())
        oc_list = get_changes_for_model(Location).filter(changed_object_id=location_pk)
        self.assertEqual(len(oc_list), 2)
        self.assertEqual(oc_list[0].action, ObjectChangeActionChoices.ACTION_DELETE)
        snapshots = oc_list[0].get_snapshots()
        self.assertIsNotNone(snapshots["prechange"])
        self.assertIsNone(snapshots["postchange"])
        self.assertIsNone(snapshots["differences"]["added"])
        self.assertEqual(snapshots["differences"]["removed"]["description"], "")

    def test_create_then_update(self):
        """Test that a create followed by an update is logged as a single create"""
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        with web_request_context(self.user):
            location = Location(name="Test Location 1", location_type=location_type, status=location_status)
            location.save()
            location.description = "changed"
            location.save()

        oc_list = get_changes_for_model(location).filter(changed_object_id=location.id)
        self.assertEqual(len(oc_list), 1)
        self.assertEqual(oc_list[0].action, ObjectChangeActionChoices.ACTION_CREATE)
        snapshots = oc_list[0].get_snapshots()
        self.assertIsNone(snapshots["prechange"])
        self.assertIsNotNone(snapshots["postchange"])
        self.assertIsNone(snapshots["differences"]["removed"])
        self.assertEqual(snapshots["differences"]["added"]["description"], "changed")

    def test_delete_then_create(self):
        """Test that a delete followed by a create is logged as a single update"""
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        pk_list = []
        with web_request_context(self.user):
            location = Location(name="Test Location 1", location_type=location_type, status=location_status)
            location.save()
            location_pk = location.pk
            pk_list.append(location.pk)
        with web_request_context(self.user):
            location.delete()
            location = Location.objects.create(
                pk=location_pk,
                name="Test Location 1",
                location_type=location_type,
                status=location_status,
                description="changed",
            )
            pk_list.append(location.pk)

        oc_list = get_changes_for_model(location).filter(changed_object_id__in=pk_list)
        self.assertEqual(len(oc_list), 2)
        self.assertEqual(oc_list[0].action, ObjectChangeActionChoices.ACTION_UPDATE)
        snapshots = oc_list[0].get_snapshots()
        self.assertIsNotNone(snapshots["prechange"])
        self.assertIsNotNone(snapshots["postchange"])
        self.assertSequenceEqual(
            list(snapshots["differences"]["added"].keys()),
            ("created", "description"),
        )
        self.assertEqual(snapshots["differences"]["added"]["description"], "changed")

    def test_change_log_context(self):
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        with web_request_context(self.user, context_detail="test_change_log_context"):
            location = Location(name="Test Location 1", location_type=location_type, status=location_status)
            location.save()

        location = Location.objects.get(name="Test Location 1")
        oc_list = get_changes_for_model(location)
        with self.subTest():
            self.assertEqual(oc_list[0].change_context, ObjectChangeEventContextChoices.CONTEXT_ORM)
        with self.subTest():
            self.assertEqual(oc_list[0].change_context_detail, "test_change_log_context")

    @mock.patch("nautobot.extras.webhooks.process_webhook.apply_async")
    def test_change_webhook_enqueued(self, mock_apply_async):
        """Test that the webhook resides on the queue"""
        with web_request_context(self.user):
            location = Location(
                name="Test Location 2",
                location_type=LocationType.objects.get(name="Campus"),
                status=Status.objects.get_for_model(Location).first(),
            )
            location.save()

        # Verify that a job was queued for the object creation webhook
        oc_list = get_changes_for_model(location)
        mock_apply_async.assert_called_once()
        call_args = mock_apply_async.call_args.kwargs["args"]
        self.assertEqual(8, len(call_args), call_args)
        self.assertEqual(call_args[0], Webhook.objects.get(type_create=True).pk)
        self.assertEqual(call_args[1], oc_list[0].object_data_v2)
        self.assertEqual(call_args[2], "location")
        self.assertEqual(call_args[3], "create")
        self.assertIsInstance(call_args[4], str)  # str(timezone.now())
        self.assertEqual(call_args[5], self.user.username)
        self.assertEqual(call_args[6], oc_list[0].request_id)
        self.assertEqual(call_args[7], oc_list[0].get_snapshots())

    def test_web_request_context_raises_exception_correctly(self):
        """
        Test implemented to ensure the fix for https://github.com/nautobot/nautobot/issues/7358 is working as intended.
        The operation should raise and allow an exception to be passed through instead of raising an
        AttributeError: 'NoneType' object has no attribute 'get'"
        """
        valid_location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        invalid_location_type = LocationType(name="rackgroup")
        with self.assertRaises(ValidationError):
            with web_request_context(self.user, context_detail="test_web_request_context_raises_exception_correctly"):
                # These operations should generate some ObjectChange records to test the code path that was causing the reported issue.
                location = Location(name="Test Location 1", location_type=valid_location_type, status=location_status)
                location.save()
                location.description = "changed"
                location.save()
                # Location type name is not allowed to be "rackgroup" (reserved name), so this should raise an exception.
                invalid_location_type.validated_save()


class WebRequestContextTransactionTestCase(TransactionTestCase):
    def test_change_log_thread_safe(self):
        """
        Emulate a race condition where the change log signal handler
        is disconnected while there is a pending object change.
        """
        user = User.objects.create(username="test-user123")
        with web_request_context(user, context_detail="test_change_log_context"):
            with web_request_context(user, context_detail="test_change_log_context"):
                status1 = Status.objects.create(name="Test Status 1")
            status2 = Status.objects.create(name="Test Status 2")

        self.assertEqual(get_changes_for_model(status1).count(), 1)
        self.assertEqual(get_changes_for_model(status2).count(), 1)


class BulkEditDeleteChangeLogging(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="jacob",
            email="jacob@example.com",
            password="top_secret",  # noqa: S106  # hardcoded-password-func-arg -- ok as this is test code only
        )

    def test_change_log_created(self):
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        with web_request_context(self.user):
            with deferred_change_logging_for_bulk_operation():
                location = Location(name="Test Location 1", location_type=location_type, status=location_status)
                location.save()

        location = Location.objects.get(name="Test Location 1")
        oc_list = get_changes_for_model(location).order_by("pk").filter(changed_object_id=location.id)
        self.assertEqual(len(oc_list), 1)
        self.assertEqual(oc_list[0].changed_object, location)
        self.assertEqual(oc_list[0].action, ObjectChangeActionChoices.ACTION_CREATE)

    def test_delete(self):
        """Test that deletes raise an exception"""
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        with self.assertRaises(ValueError):
            with web_request_context(self.user):
                with deferred_change_logging_for_bulk_operation():
                    location = Location(name="Test Location 1", location_type=location_type, status=location_status)
                    location.save()
                    location.delete()

    def test_bulk_delete_has_user_in_change_log(self):
        """Test that the bulk delete operation adds the user to the change log"""
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        with web_request_context(self.user):
            location = Location(name="Test Location 1", location_type=location_type, status=location_status)
            location.save()
            location_pk = location.pk
            location_qs = Location.objects.filter(pk=location_pk)
            bulk_delete_with_bulk_change_logging(location_qs)

        oc_list = get_changes_for_model(location)
        self.assertEqual(len(oc_list), 2)
        self.assertEqual(oc_list[0].action, ObjectChangeActionChoices.ACTION_DELETE)
        self.assertEqual(oc_list[0].user, self.user)
        self.assertEqual(oc_list[0].user_name, self.user.username)

    def test_bulk_delete_logs_cascade_children(self):
        """Bulk delete should log ObjectChanges for CASCADE-deleted child rows, not just queryset members."""
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        parent = Location.objects.create(name="Parent BulkDelete", location_type=location_type, status=location_status)
        child_a = Location.objects.create(
            name="Child A", location_type=location_type, status=location_status, parent=parent
        )
        child_b = Location.objects.create(
            name="Child B", location_type=location_type, status=location_status, parent=parent
        )
        expected_pks = {parent.pk, child_a.pk, child_b.pk}

        change_id = uuid.uuid4()
        with web_request_context(self.user, change_id=change_id):
            bulk_delete_with_bulk_change_logging(Location.objects.filter(pk=parent.pk))

        delete_changes = get_changes_for_model(Location).filter(
            action=ObjectChangeActionChoices.ACTION_DELETE,
            request_id=change_id,
        )
        self.assertEqual({oc.changed_object_id for oc in delete_changes}, expected_pks)
        for oc in delete_changes:
            self.assertEqual(oc.user, self.user)
            self.assertEqual(oc.user_name, self.user.username)

    def test_bulk_delete_logs_contact_associations(self):
        """Bulk delete should log an ObjectChange for ContactAssociations the receiver cleans up."""
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        location = Location.objects.create(
            name="Location With Contact", location_type=location_type, status=location_status
        )
        contact = Contact.objects.create(name="Test Contact")
        assoc_role = Role.objects.get_for_model(ContactAssociation).first()
        assoc_status = Status.objects.get_for_model(ContactAssociation).first()
        association = ContactAssociation.objects.create(
            contact=contact,
            associated_object=location,
            role=assoc_role,
            status=assoc_status,
        )
        association_pk = association.pk

        change_id = uuid.uuid4()
        with web_request_context(self.user, change_id=change_id):
            bulk_delete_with_bulk_change_logging(Location.objects.filter(pk=location.pk))

        assoc_changes = get_changes_for_model(ContactAssociation).filter(
            action=ObjectChangeActionChoices.ACTION_DELETE, request_id=change_id
        )
        self.assertEqual({oc.changed_object_id for oc in assoc_changes}, {association_pk})
        self.assertEqual(assoc_changes.first().user, self.user)

    def test_bulk_delete_logs_notes(self):
        """Bulk delete should log an ObjectChange for Notes the receiver cleans up."""
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        location = Location.objects.create(
            name="Location With Note", location_type=location_type, status=location_status
        )
        note = Note.objects.create(assigned_object=location, user=self.user, note="A note on this location")
        note_pk = note.pk

        change_id = uuid.uuid4()
        with web_request_context(self.user, change_id=change_id):
            bulk_delete_with_bulk_change_logging(Location.objects.filter(pk=location.pk))

        note_changes = get_changes_for_model(Note).filter(
            action=ObjectChangeActionChoices.ACTION_DELETE, request_id=change_id
        )
        self.assertEqual({oc.changed_object_id for oc in note_changes}, {note_pk})
        self.assertEqual(note_changes.first().user, self.user)

    def test_create_then_update(self):
        """Test that a create followed by an update is logged as a single create"""
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        with web_request_context(self.user):
            with deferred_change_logging_for_bulk_operation():
                location = Location(name="Test Location 1", location_type=location_type, status=location_status)
                location.save()
                location.description = "changed"
                location.save()

        oc_list = get_changes_for_model(location).filter(changed_object_id=location.id)
        self.assertEqual(len(oc_list), 1)
        self.assertEqual(oc_list[0].action, ObjectChangeActionChoices.ACTION_CREATE)
        snapshots = oc_list[0].get_snapshots()
        self.assertIsNone(snapshots["prechange"])
        self.assertIsNotNone(snapshots["postchange"])
        self.assertIsNone(snapshots["differences"]["removed"])
        self.assertEqual(snapshots["differences"]["added"]["description"], "changed")

    @mock.patch("nautobot.extras.jobs.import_jobs")
    def test_bulk_edit(self, mock_import_jobs):
        """Test that edits to multiple objects are correctly logged"""
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        locations = [
            Location(name=f"Test Location {i}", location_type=location_type, status=location_status)
            for i in range(1, 4)
        ]
        Location.objects.bulk_create(locations)
        # Create a JobHook that applies to Locations
        _, job_model = get_job_class_and_model("job_hook_receiver", "TestJobHookReceiverLog")
        mock_import_jobs.assert_called_once()
        mock_import_jobs.reset_mock()
        job_hook = JobHook.objects.create(name="JobHookTest", type_update=True, job=job_model)
        job_hook.content_types.set([ContentType.objects.get_for_model(Location)])

        pk_list = []
        with web_request_context(self.user):
            with deferred_change_logging_for_bulk_operation():
                for location in locations:
                    location.description = "changed"
                    location.save()
                    pk_list.append(location.id)

        oc_list = get_changes_for_model(Location).filter(changed_object_id__in=pk_list)
        self.assertEqual(len(oc_list), 3)
        for oc in oc_list:
            self.assertEqual(oc.action, ObjectChangeActionChoices.ACTION_UPDATE)
            snapshots = oc.get_snapshots()
            self.assertIsNone(snapshots["prechange"])
            self.assertIsNotNone(snapshots["postchange"])
            self.assertIsNone(snapshots["differences"]["removed"])
            self.assertEqual(snapshots["differences"]["added"]["description"], "changed")

        # Check for regression of https://github.com/nautobot/nautobot/issues/6203
        mock_import_jobs.assert_called_once()

    def test_bulk_edit_device_type_software_image_file(self):
        """Test that bulk edits to null does not cause integrity error"""
        manufacturer = Manufacturer.objects.create(name="Test")
        platform = Platform.objects.create(name="Test")
        software_status = Status.objects.get_for_model(SoftwareVersion).first()
        software_version = SoftwareVersion.objects.create(version="1.0.0", platform=platform, status=software_status)
        software_image_file = SoftwareImageFile.objects.create(
            image_file_name="test.iso", software_version=software_version, status=software_status
        )
        device_type = DeviceType.objects.create(manufacturer=manufacturer, model="test123")
        device_type.software_image_files.set([software_image_file])
        oc_list_1 = list(get_changes_for_model(DeviceTypeToSoftwareImageFile))
        with web_request_context(self.user):
            with deferred_change_logging_for_bulk_operation():
                device_type.software_image_files.set([])
                device_type.save()

        oc_list_2 = list(get_changes_for_model(DeviceTypeToSoftwareImageFile))
        self.assertEqual(len(oc_list_2) - len(oc_list_1), 1)
        self.assertEqual(oc_list_2[0].action, ObjectChangeActionChoices.ACTION_DELETE)
        self.assertIsNotNone(oc_list_2[0].changed_object_id)
        self.assertEqual(oc_list_2[0].user, self.user)
        self.assertEqual(oc_list_2[0].user_name, self.user.username)

    def test_change_log_context(self):
        location_type = LocationType.objects.get(name="Campus")
        location_status = Status.objects.get_for_model(Location).first()
        with web_request_context(self.user, context_detail="test_change_log_context"):
            with deferred_change_logging_for_bulk_operation():
                location = Location(name="Test Location 1", location_type=location_type, status=location_status)
                location.save()

        location = Location.objects.get(name="Test Location 1")
        oc_list = get_changes_for_model(location)
        with self.subTest():
            self.assertEqual(oc_list[0].change_context, ObjectChangeEventContextChoices.CONTEXT_ORM)
        with self.subTest():
            self.assertEqual(oc_list[0].change_context_detail, "test_change_log_context")


class WithoutDeleteChangeLoggingTestCase(TestCase):
    """
    The reconnect has to happen, including when the block raises.

    This was a `try`/`finally` repeated at four call sites. Getting it wrong leaves delete change logging
    off for the rest of the worker process -- silently, and for every model, not just the one being
    deleted -- so the guarantee is worth asserting rather than reviewing.
    """

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="signal-suppression-user")

    @staticmethod
    def _is_connected():
        """
        Whether the change log's `pre_delete` receiver is currently attached.

        Read off `Signal.receivers`, whose entries are `(lookup_key, receiver, is_async)` and whose
        receiver is normally a weak reference, since `@receiver` connects weakly by default.
        """
        import weakref

        from django.db.models.signals import pre_delete

        from nautobot.extras.signals import _handle_deleted_object

        for entry in pre_delete.receivers:
            receiver = entry[1]
            if isinstance(receiver, weakref.ReferenceType):
                receiver = receiver()
            if receiver is _handle_deleted_object:
                return True
        return False

    def test_disconnected_inside_and_reconnected_after(self):
        self.assertTrue(self._is_connected())

        with without_delete_change_logging():
            self.assertFalse(self._is_connected())

        self.assertTrue(self._is_connected())

    def test_reconnected_when_the_block_raises(self):
        with self.assertRaises(ValueError):
            with without_delete_change_logging():
                self.assertFalse(self._is_connected())
                raise ValueError("boom")

        self.assertTrue(self._is_connected())

    def test_deletes_inside_the_block_are_not_change_logged(self):
        """What the callers are actually buying: no change records for the records they are deleting."""
        location_type = LocationType.objects.create(name="Signal Suppression LT")

        with without_delete_change_logging():
            location_type.delete()

        self.assertFalse(
            get_changes_for_model(LocationType)
            .filter(object_repr="Signal Suppression LT", action=ObjectChangeActionChoices.ACTION_DELETE)
            .exists()
        )

    def test_deletes_outside_the_block_are_still_change_logged(self):
        """The comparison that makes the previous test mean something."""
        location_type = LocationType.objects.create(name="Signal Passthrough LT")

        with web_request_context(self.user):
            location_type.delete()

        self.assertTrue(
            get_changes_for_model(LocationType)
            .filter(object_repr="Signal Passthrough LT", action=ObjectChangeActionChoices.ACTION_DELETE)
            .exists()
        )


class NoOpSaveCoalescingTestCase(TestCase):
    """
    How a suppressed save interacts with the coalescing that folds repeat saves of one object into one row.

    A suppressed save registers nothing, so a later real save in the same request takes the insert branch
    rather than the overwrite branch. These pin that the record count and its final data come out the same
    either way.
    """

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="coalescing-user")
        self.manufacturer = Manufacturer.objects.create(name="Coalescing Manufacturer")
        get_changes_for_model(self.manufacturer).delete()

    def changes(self):
        return get_changes_for_model(self.manufacturer)

    def test_no_op_then_real_records_once(self):
        with web_request_context(self.user, context_detail="no-op then real"):
            self.manufacturer.save()
            self.manufacturer.description = "changed"
            self.manufacturer.save()

        self.assertEqual(self.changes().count(), 1)
        self.assertEqual(self.changes().first().action, ObjectChangeActionChoices.ACTION_UPDATE)
        self.assertEqual(self.changes().first().object_data["description"], "changed")

    def test_real_then_no_op_records_once(self):
        with web_request_context(self.user, context_detail="real then no-op"):
            self.manufacturer.description = "changed"
            self.manufacturer.save()
            self.manufacturer.save()

        self.assertEqual(self.changes().count(), 1)
        self.assertEqual(self.changes().first().object_data["description"], "changed")

    def test_create_then_no_op_stays_a_create(self):
        with web_request_context(self.user, context_detail="create then no-op"):
            created = Manufacturer.objects.create(name="Created Then Resaved")
            created.save()

        changes = get_changes_for_model(created)
        self.assertEqual(changes.count(), 1)
        self.assertEqual(changes.first().action, ObjectChangeActionChoices.ACTION_CREATE)

    def test_no_op_then_delete_keeps_its_prechange(self):
        """
        The suppressed save must not have consumed the prior-state cache the delete's diff needs.

        That cache is populated in `pre_save` for objects with no change history, and the delete's rendered
        diff falls back to it. Decoupling the two would leave webhook consumers a null prechange here.
        """
        with web_request_context(self.user, context_detail="no-op then delete"):
            self.manufacturer.save()
            self.manufacturer.delete()

        change = get_changes_for_model(Manufacturer).filter(object_repr="Coalescing Manufacturer").first()
        self.assertEqual(change.action, ObjectChangeActionChoices.ACTION_DELETE)
        self.assertIsNotNone(change.get_snapshots()["prechange"])

    def test_a_round_trip_within_one_request_still_records(self):
        """
        Documented, not desired: A -> B -> A in one request leaves one record whose diff is empty.

        The second save really does change the stored row, so it is recorded, and the coalescing then
        rewrites the row's data back to A. Suppression is per-save; it does not reconcile a request's net
        effect. Here so the behaviour is not mistaken for a bug in no-op suppression.
        """
        with web_request_context(self.user, context_detail="round trip"):
            self.manufacturer.description = "B"
            self.manufacturer.save()
            self.manufacturer.description = ""
            self.manufacturer.save()

        self.assertEqual(self.changes().count(), 1)
        self.assertEqual(self.changes().first().object_data["description"], "")

    def test_bulk_operation_of_no_ops_records_nothing(self):
        """The case worth the most: a bulk edit setting fields to the values they already hold."""
        manufacturers = [Manufacturer.objects.create(name=f"Bulk No-Op {index}") for index in range(5)]
        for manufacturer in manufacturers:
            get_changes_for_model(manufacturer).delete()

        with web_request_context(self.user, context_detail="bulk no-op"):
            with deferred_change_logging_for_bulk_operation():
                for manufacturer in manufacturers:
                    manufacturer.save()

        for manufacturer in manufacturers:
            with self.subTest(manufacturer=manufacturer.name):
                self.assertFalse(get_changes_for_model(manufacturer).exists())

    def test_bulk_operation_records_only_what_changed(self):
        manufacturers = [Manufacturer.objects.create(name=f"Bulk Mixed {index}") for index in range(4)]
        for manufacturer in manufacturers:
            get_changes_for_model(manufacturer).delete()

        with web_request_context(self.user, context_detail="bulk mixed"):
            with deferred_change_logging_for_bulk_operation():
                for index, manufacturer in enumerate(manufacturers):
                    if index % 2:
                        manufacturer.description = "changed"
                    manufacturer.save()

        for index, manufacturer in enumerate(manufacturers):
            with self.subTest(manufacturer=manufacturer.name):
                self.assertEqual(get_changes_for_model(manufacturer).count(), 1 if index % 2 else 0)

    @mock.patch("nautobot.extras.context_managers.enqueue_webhooks")
    @mock.patch("nautobot.extras.context_managers.publish_event")
    def test_a_no_op_dispatches_nothing(self, mock_publish_event, mock_enqueue_webhooks):
        """No record means no webhook and no event -- the consequence that needs documenting."""
        with web_request_context(self.user, context_detail="silent"):
            self.manufacturer.save()

        mock_enqueue_webhooks.assert_not_called()
        mock_publish_event.assert_not_called()

    @mock.patch("nautobot.extras.context_managers.enqueue_webhooks")
    @mock.patch("nautobot.extras.context_managers.publish_event")
    def test_a_real_change_still_dispatches(self, mock_publish_event, mock_enqueue_webhooks):
        """The comparison that makes the previous test mean something."""
        with web_request_context(self.user, context_detail="dispatched"):
            self.manufacturer.description = "changed"
            self.manufacturer.save()

        mock_enqueue_webhooks.assert_called_once()
        mock_publish_event.assert_called_once()
