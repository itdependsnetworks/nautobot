"""
What the archived lists show, where a warm list would follow a relation.

A retained record stores the object it describes as a content type id and an object id, so nothing can
follow it the way a template follows a warm record's generic foreign key. These pin the two consequences:
the Object cell links where the object survives and falls back to its recorded name where it does not, and
the links cost one query per object type on the page instead of one per row.
"""

from datetime import datetime, timezone as dt_timezone
import uuid

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext

from nautobot.core.testing import TestCase
from nautobot.dcim.models import Location
from nautobot.extras.choices import ObjectChangeActionChoices
from nautobot.extras.filters import ArchivedObjectChangeFilterSet
from nautobot.extras.models import ArchivedObjectChange, ObjectChange
from nautobot.extras.tables import ArchivedObjectChangeTable
from nautobot.extras.tests.test_changelog_archive_base import clear_archive

WHEN = datetime(2021, 6, 1, tzinfo=dt_timezone.utc)


class ArchivedObjectChangeTableTestCase(TestCase):
    def setUp(self):
        super().setUp()
        clear_archive(ArchivedObjectChange)
        self.addCleanup(clear_archive, ArchivedObjectChange)
        self.location = Location.objects.first()
        self.location_type = ContentType.objects.get_for_model(Location)

    def make_record(self, *, content_type_id, object_id, object_repr):
        return ArchivedObjectChange.objects.create(
            id=uuid.uuid4(),
            time=WHEN,
            user_name="alice",
            request_id=uuid.uuid4(),
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type_id=content_type_id,
            changed_object_id=object_id,
            change_context="orm",
            object_repr=object_repr,
            object_data={},
        )

    def rendered(self, table):
        table.paginate(per_page=50)
        return "".join(str(cell) for row in table.paginated_rows for _bound, cell in row.items())

    def test_the_object_cell_links_where_the_object_still_exists(self):
        self.make_record(
            content_type_id=self.location_type.pk, object_id=self.location.pk, object_repr=str(self.location)
        )

        rendered = self.rendered(ArchivedObjectChangeTable(ArchivedObjectChange.objects.all()))

        self.assertIn(self.location.get_absolute_url(), rendered)

    def test_the_object_cell_falls_back_to_the_recorded_name(self):
        """The ordinary case for an archive: the object was deleted long after the record was written."""
        self.make_record(content_type_id=self.location_type.pk, object_id=uuid.uuid4(), object_repr="Gone Location")

        rendered = self.rendered(ArchivedObjectChangeTable(ArchivedObjectChange.objects.all()))

        self.assertIn("Gone Location", rendered)
        self.assertNotIn(f'href="/dcim/locations/{uuid.uuid4()}', rendered)

    def test_the_links_cost_one_query_per_object_type_not_one_per_row(self):
        """Resolved per row, a page of retained history would issue a query for every record on it."""
        for index in range(20):
            self.make_record(
                content_type_id=self.location_type.pk, object_id=self.location.pk, object_repr=f"Location {index}"
            )

        with CaptureQueriesContext(connection) as captured:
            self.rendered(ArchivedObjectChangeTable(ArchivedObjectChange.objects.all()))

        self.assertLess(len(captured), 10, "the object links are being resolved one row at a time")

    def test_the_type_column_renders_the_content_type(self):
        self.make_record(
            content_type_id=self.location_type.pk, object_id=self.location.pk, object_repr=str(self.location)
        )

        rendered = self.rendered(ArchivedObjectChangeTable(ArchivedObjectChange.objects.all()))

        self.assertIn("DCIM", rendered)


class ArchivedContentTypeFilterTestCase(TestCase):
    """`?changed_object_type=dcim.location` has to keep working against an identifier column."""

    def setUp(self):
        super().setUp()
        clear_archive(ArchivedObjectChange)
        self.addCleanup(clear_archive, ArchivedObjectChange)
        for model in (Location, ObjectChange):
            ArchivedObjectChange.objects.create(
                id=uuid.uuid4(),
                time=WHEN,
                user_name="alice",
                request_id=uuid.uuid4(),
                action=ObjectChangeActionChoices.ACTION_UPDATE,
                changed_object_type_id=ContentType.objects.get_for_model(model).pk,
                changed_object_id=uuid.uuid4(),
                change_context="orm",
                object_repr=model.__name__,
                object_data={},
            )

    def filtered(self, value):
        return ArchivedObjectChangeFilterSet(
            {"changed_object_type": value}, queryset=ArchivedObjectChange.objects.all()
        ).qs

    def test_an_app_label_and_model_selects_that_type(self):
        self.assertEqual([record.object_repr for record in self.filtered("dcim.location")], ["Location"])

    def test_an_unknown_type_selects_nothing(self):
        self.assertEqual(self.filtered("dcim.nosuchmodel").count(), 0)

    def test_a_malformed_value_selects_nothing_instead_of_raising(self):
        self.assertEqual(self.filtered("not-a-dotted-pair").count(), 0)
