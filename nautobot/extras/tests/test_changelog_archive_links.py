"""
Linking a retained record to the object it describes, and the table that renders it.

A mirror holds its object as an identifier rather than a relation, so the link is rebuilt per page and the
warm table has to tolerate being handed a mirror.
"""

from datetime import datetime, timezone as dt_timezone
import uuid
import warnings

from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse

from nautobot.core.testing import TestCase
from nautobot.dcim.models import Location, LocationType
from nautobot.extras.choices import (
    ObjectChangeActionChoices,
)
from nautobot.extras.models import (
    ArchivedObjectChange,
    ArchiveSegment,
    ObjectChange,
)
from nautobot.extras.tables import ObjectChangeTable
from nautobot.extras.tests.test_changelog_archive_base import ArchiveReadFixtureMixin, PERIOD


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class ArchiveChangedObjectLinkTestCase(ArchiveReadFixtureMixin, TestCase):
    """
    The Object column links to the object a retained record describes, when that object still exists.

    A retained record has no relation to follow -- rotation demotes the generic foreign key to a content
    type id and an object id -- so the link is rebuilt from those. Plenty of retained records outlive their
    objects, which is what an archive is for, so falling back to plain text matters as much as the link.
    """

    def setUp(self):
        super().setUp()
        ArchivedObjectChange.objects.all().delete()
        ArchiveSegment.objects.all().delete()
        self.segment = self.build_period(rows=0)
        self.location = Location.objects.first()
        self.location_ct = ContentType.objects.get_for_model(Location)
        self.present = self.make_record(self.location_ct.pk, self.location.pk, "A location that still exists")
        self.absent = self.make_record(self.location_ct.pk, uuid.uuid4(), "A location that is long gone")

    def make_record(self, content_type_id, object_id, object_repr):
        return ArchivedObjectChange.objects.create(
            id=uuid.uuid4(),
            period_key=PERIOD,
            time=datetime(int(PERIOD), 6, 1, tzinfo=dt_timezone.utc),
            user_name="alice",
            request_id=uuid.uuid4(),
            action=ObjectChangeActionChoices.ACTION_UPDATE,
            changed_object_type_id=content_type_id,
            changed_object_id=object_id,
            change_context="orm",
            object_repr=object_repr,
            object_data={},
        )

    def render_cell(self, record):
        """Render just the Object column for one record, through the real table."""
        table = ObjectChangeTable(ArchivedObjectChange.objects.filter(pk=record.pk))
        return table.rows[0].get_cell("object_repr")

    def test_a_resolvable_object_is_linked(self):
        self.assertIn(self.location.get_absolute_url(), self.render_cell(self.present))

    def test_a_missing_object_falls_back_to_the_stored_repr(self):
        cell = self.render_cell(self.absent)

        self.assertIn("A location that is long gone", cell)
        self.assertNotIn("<a ", cell)

    def test_the_page_is_resolved_in_one_query_per_content_type(self):
        """
        The link is worth having only if it costs about what the warm page costs.

        Warm rows get a generic foreign key prefetch, which issues one query per distinct content type on
        the page. This does the same by hand, so the query count is the assertion: two content types across
        twelve rows is two queries, not twelve. `assertNumQueries` watches the default database, which is
        where the objects live; the page of retained records itself is read over the archive alias.
        """
        location_type = LocationType.objects.first()
        location_type_ct = ContentType.objects.get_for_model(LocationType)
        for _ in range(5):
            self.make_record(self.location_ct.pk, Location.objects.last().pk, "Another location")
            self.make_record(location_type_ct.pk, location_type.pk, "A location type")
        table = ObjectChangeTable(ArchivedObjectChange.objects.filter(period_key=PERIOD))
        for content_type_id in (self.location_ct.pk, location_type_ct.pk):
            ContentType.objects.get_for_id(content_type_id)  # warm the content type cache

        with self.assertNumQueries(2):
            urls = table.changed_object_urls()

        self.assertEqual(urls[(self.location_ct.pk, self.location.pk)], self.location.get_absolute_url())
        self.assertEqual(urls[(location_type_ct.pk, location_type.pk)], location_type.get_absolute_url())
        self.assertNotIn((self.location_ct.pk, self.absent.changed_object_id), urls)

    def test_the_link_appears_on_the_list_view(self):
        """
        The list page loads its rows over HTMX, so the header is what makes this exercise the real table.

        Without it the renderer hands the table an empty queryset and the assertions below pass or fail on
        the page shell rather than on any row.
        """
        self.add_permissions("extras.view_objectchange")
        self.grant_cold_storage()
        url = f"{reverse('extras:objectchange_list')}?archive_period={PERIOD}"

        response = self.client.get(url, headers={"hx-request": "true"})

        self.assertHttpStatus(response, 200)
        content = response.content.decode(response.charset)
        self.assertIn(self.location.get_absolute_url(), content)
        self.assertIn("A location that is long gone", content)

    def test_the_link_appears_on_the_detail_view(self):
        self.add_permissions("extras.view_objectchange")
        self.grant_cold_storage()
        url = reverse("extras:objectchange", kwargs={"pk": self.present.pk})

        response = self.client.get(f"{url}?archive_period={PERIOD}")

        self.assertHttpStatus(response, 200)
        self.assertIn(self.location.get_absolute_url(), response.content.decode(response.charset))

    def test_a_warm_table_does_not_scan_the_page(self):
        """A warm record's relation is prefetched, so the batch resolver must stay out of the way."""
        table = ObjectChangeTable(ObjectChange.objects.all())

        with self.assertNumQueries(0):
            self.assertEqual(table.changed_object_urls(), {})


@override_settings(CHANGELOG_ARCHIVE_ENABLED=True)
class MirrorTableWarningTestCase(ArchiveReadFixtureMixin, TestCase):
    """
    Rendering a warm table over a mirror is deliberate, so it must not warn that it is misconfigured.

    django-tables2 compares the data's model against `Table.Meta.model` and warns when the data is not a
    subclass. A mirror never is. The warning went to the log on every retained page render, telling whoever
    read it that a table was set up wrong when the whole feature depends on this working.
    """

    def setUp(self):
        super().setUp()
        ArchivedObjectChange.objects.all().delete()
        ArchiveSegment.objects.all().delete()
        self.build_period(rows=2)

    def build_table(self, queryset):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ObjectChangeTable(queryset)
        return [str(warning.message) for warning in caught]

    def test_a_mirror_does_not_warn(self):
        caught = self.build_table(ArchivedObjectChange.objects.filter(period_key=PERIOD))

        self.assertEqual([message for message in caught if "Table data is of type" in message], [])

    def test_a_warm_queryset_is_untouched(self):
        """The suppression is narrow, so a genuinely mismatched table still says so."""
        caught = self.build_table(ObjectChange.objects.all())

        self.assertEqual([message for message in caught if "Table data is of type" in message], [])

    def test_a_real_mismatch_still_warns(self):
        """Pinning that the warning is suppressed for mirrors only, not switched off wholesale."""
        caught = self.build_table(ArchiveSegment.objects.all())

        self.assertNotEqual([message for message in caught if "Table data is of type" in message], [])
