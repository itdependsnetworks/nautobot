"""
The contract between each retention mirror and the warm model it mirrors.

A mirror has to stay field-compatible with its warm model, and the two permitted deviations are a foreign
key demoted to an identifier column and a name denormalized because the key it was read through is gone.
Nothing else catches a field added to a warm model and not to its mirror: it produces no migration error
and no failure anywhere else, and every record rotated afterwards is missing it.
"""

from nautobot.core.testing import TestCase
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    JobConsoleEntry,
    JobLogEntry,
    JobResult,
    ObjectChange,
)

# Each mirror beside the warm model it holds history for.
MIRRORED = {
    ObjectChange: ArchivedObjectChange,
    JobResult: ArchivedJobResult,
    JobLogEntry: ArchivedJobLogEntry,
    JobConsoleEntry: ArchivedJobConsoleEntry,
}
ARCHIVE_MODELS = tuple(MIRRORED.values())


class ChangelogArchiveSchemaTestCase(TestCase):
    """The mirrors have to stay field-compatible with the warm models they hold history for."""

    def test_mirror_fields_match_warm_fields_with_foreign_keys_demoted(self):
        """
        Every warm field is present on the mirror, with foreign keys held as `<name>_id` columns.

        This is the check that catches the failure mode nothing else does: a field added to a warm model
        and not to its mirror produces no migration error and no test failure anywhere else.
        """
        # Denormalized on the mirror to survive the loss of the foreign key it was read through.
        expected_extra = {JobResult: {"user_name"}}

        for warm, mirror in MIRRORED.items():
            with self.subTest(model=warm.__name__):
                mirror_fields = {f.name for f in mirror._meta.fields}
                missing = set()
                for field in warm._meta.fields:
                    if field.name in mirror_fields:
                        continue
                    if field.is_relation and f"{field.name}_id" in mirror_fields:
                        continue
                    missing.add(field.name)
                self.assertEqual(missing, set(), f"{mirror.__name__} is missing warm fields")

                warm_names = {f.name for f in warm._meta.fields}
                extra = {name for name in mirror_fields - warm_names if name.removesuffix("_id") not in warm_names}
                self.assertEqual(extra, expected_extra.get(warm, set()))

    def test_mirrors_offer_only_the_view_permission(self):
        """Rotation writes retained records and nothing else does, so there is no add, change or delete."""
        for mirror in ARCHIVE_MODELS:
            with self.subTest(model=mirror.__name__):
                self.assertEqual(mirror._meta.default_permissions, ("view",))

    def test_mirrors_hold_no_foreign_keys(self):
        """
        A real relation would be a cross-database constraint the moment the alias is repointed.

        Each reference is a plain identifier column instead. Only concrete forward relations matter here;
        the reverse `GenericRelation` descriptors inherited from `BaseModel` add no column and no
        constraint.
        """
        for mirror in ARCHIVE_MODELS:
            with self.subTest(model=mirror.__name__):
                relations = [f.name for f in mirror._meta.fields if f.is_relation]
                self.assertEqual(relations, [])

    def test_mirrors_are_excluded_from_global_search(self):
        """A warm record and the retained copy of one, returned by the same search, reads as a duplicate."""
        from nautobot.core.constants import GLOBAL_SEARCH_EXCLUDE_LIST

        for mirror in ARCHIVE_MODELS:
            with self.subTest(model=mirror.__name__):
                self.assertIn(mirror._meta.model_name, GLOBAL_SEARCH_EXCLUDE_LIST)
