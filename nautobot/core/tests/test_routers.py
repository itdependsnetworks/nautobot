"""Tests for `nautobot.core.models.routers`."""

from django.test import override_settings

from nautobot.core.constants import CHANGELOG_ARCHIVE
from nautobot.core.models.routers import ChangelogArchiveRouter
from nautobot.core.testing import TestCase
from nautobot.extras.models import (
    ArchivedJobConsoleEntry,
    ArchivedJobLogEntry,
    ArchivedJobResult,
    ArchivedObjectChange,
    ArchiveSegment,
    JobConsoleEntry,
    JobLogEntry,
    JobResult,
    ObjectChange,
    RetentionRule,
)

ARCHIVE_MODELS = (ArchivedObjectChange, ArchivedJobResult, ArchivedJobLogEntry, ArchivedJobConsoleEntry)
WARM_MODELS = (ObjectChange, JobResult, JobLogEntry, JobConsoleEntry)


class ChangelogArchiveRouterTestCase(TestCase):
    """The router pins the retention mirrors to their alias and leaves every other model alone."""

    def setUp(self):
        super().setUp()
        self.router = ChangelogArchiveRouter()

    def test_mirrors_read_and_write_on_archive_alias(self):
        for model in ARCHIVE_MODELS:
            with self.subTest(model=model.__name__):
                self.assertEqual(self.router.db_for_read(model), CHANGELOG_ARCHIVE)
                self.assertEqual(self.router.db_for_write(model), CHANGELOG_ARCHIVE)

    def test_warm_models_are_not_intercepted(self):
        """Returning None hands the choice back to Django, which is what keeps `job_logs` working."""
        for model in WARM_MODELS:
            with self.subTest(model=model.__name__):
                self.assertIsNone(self.router.db_for_read(model))
                self.assertIsNone(self.router.db_for_write(model))

    def test_job_log_entry_is_not_intercepted(self):
        """
        `JobResult.log` writes `JobLogEntry` through the `job_logs` alias explicitly.

        Covered separately from the loop above because intercepting it is the specific regression that
        would break job logging.
        """
        self.assertIsNone(self.router.db_for_write(JobLogEntry))
        self.assertIsNone(self.router.db_for_write(JobConsoleEntry))

    def test_registry_models_are_not_mirrors(self):
        """`ArchiveSegment` and `RetentionRule` are ordinary models on `default`, not retained history."""
        for model in (ArchiveSegment, RetentionRule):
            with self.subTest(model=model.__name__):
                self.assertIsNone(self.router.db_for_read(model))
                self.assertIsNone(self.router.db_for_write(model))

    @override_settings(CHANGELOG_ARCHIVE_SEPARATE_DATABASE=False)
    def test_allow_migrate_defers_entirely_when_one_database(self):
        """
        With both aliases on one database there is nothing to route, so the router abstains.

        Not just a simplification: `allow_migrate` also decides which tables `TransactionTestCase` flushes
        between tests, so narrowing that set here broke unrelated job-logging fixtures.
        """
        for model in (*ARCHIVE_MODELS, *WARM_MODELS, ArchiveSegment, RetentionRule):
            with self.subTest(model=model.__name__):
                self.assertIsNone(self.router.allow_migrate("default", "extras", model._meta.model_name))
                self.assertIsNone(self.router.allow_migrate(CHANGELOG_ARCHIVE, "extras", model._meta.model_name))

    @override_settings(CHANGELOG_ARCHIVE_SEPARATE_DATABASE=True)
    def test_allow_migrate_separate_database(self):
        """A separate archive database has its own migration history and takes only the mirrors."""
        for model in ARCHIVE_MODELS:
            with self.subTest(model=model.__name__):
                self.assertIs(self.router.allow_migrate("default", "extras", model._meta.model_name), False)
                self.assertIs(self.router.allow_migrate(CHANGELOG_ARCHIVE, "extras", model._meta.model_name), True)

    @override_settings(CHANGELOG_ARCHIVE_SEPARATE_DATABASE=True)
    def test_allow_migrate_excludes_everything_else_from_archive_alias(self):
        """The archive database holds the retention tables and nothing else."""
        for model in (*WARM_MODELS, ArchiveSegment, RetentionRule):
            with self.subTest(model=model.__name__):
                self.assertIs(self.router.allow_migrate(CHANGELOG_ARCHIVE, "extras", model._meta.model_name), False)
                self.assertIsNone(self.router.allow_migrate("default", "extras", model._meta.model_name))

    @override_settings(CHANGELOG_ARCHIVE_SEPARATE_DATABASE=True)
    def test_allow_migrate_ignores_unknown_models(self):
        """An app_label/model_name Django cannot resolve is not ours to route."""
        self.assertIsNone(self.router.allow_migrate("default", "extras", "nosuchmodel"))
        self.assertIsNone(self.router.allow_migrate("default", "extras", None))

    @override_settings(CHANGELOG_ARCHIVE_SEPARATE_DATABASE=False)
    def test_transaction_test_case_flush_set_is_not_narrowed(self):
        """
        The regression guard for the above: every installed model must stay flushable on `default`.

        `TransactionTestCase` truncates the tables `django_table_names` reports, and that list is filtered
        by `allow_migrate_model`. A router that excludes anything here leaves rows behind between tests,
        which surfaces far away as foreign key violations in unrelated fixtures.
        """
        from django.apps import apps
        from django.db import router as global_router

        excluded = [
            model._meta.label for model in apps.get_models() if not global_router.allow_migrate_model("default", model)
        ]
        self.assertEqual(excluded, [])

    def test_allow_relation_across_default_and_archive(self):
        """
        Both aliases address one physical database by default, so Django's cross-database guard would
        otherwise be a false positive for any code comparing instances across them.
        """
        segment = ArchiveSegment(model_label="extras.objectchange", period_key="2024")
        mirror = ArchivedObjectChange(period_key="2024")
        segment._state.db = "default"
        mirror._state.db = CHANGELOG_ARCHIVE
        self.assertIs(self.router.allow_relation(segment, mirror), True)
        self.assertIs(self.router.allow_relation(mirror, segment), True)

    def test_allow_relation_defers_for_unrelated_aliases(self):
        segment = ArchiveSegment(model_label="extras.objectchange", period_key="2024")
        mirror = ArchivedObjectChange(period_key="2024")
        segment._state.db = "some_other_alias"
        mirror._state.db = CHANGELOG_ARCHIVE
        self.assertIsNone(self.router.allow_relation(segment, mirror))


class ChangelogArchiveSchemaTestCase(TestCase):
    """The mirrors have to stay field-compatible with the warm models they hold history for."""

    databases = ["default", CHANGELOG_ARCHIVE]

    def test_mirrors_are_registered_for_every_covered_model(self):
        from nautobot.extras.constants import CHANGELOG_ARCHIVE_COVERED_MODELS
        from nautobot.extras.registry import registry

        self.assertEqual(
            sorted(registry["changelog_archive_models"]),
            sorted(CHANGELOG_ARCHIVE_COVERED_MODELS),
        )

    def test_mirror_fields_match_warm_fields_with_foreign_keys_demoted(self):
        """
        Every warm field is present on the mirror, with foreign keys held as `<name>_id` columns.

        This is the check that catches the failure mode nothing else does: a field added to a warm model
        and not to its mirror produces no migration error and no test failure anywhere else.
        """
        from nautobot.extras.registry import registry

        # Denormalized on the mirror to survive the loss of the foreign key it was read through.
        expected_extra = {"extras.jobresult": {"user_name"}}

        for warm_label, mirror in registry["changelog_archive_models"].items():
            with self.subTest(model=warm_label):
                from django.apps import apps

                warm = apps.get_model(warm_label)
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
                extra = {
                    name
                    for name in mirror_fields - warm_names
                    if name != "period_key" and name.removesuffix("_id") not in warm_names
                }
                self.assertEqual(extra, expected_extra.get(warm_label, set()))

    def test_mirrors_declare_no_permissions_of_their_own(self):
        """Access is gated on `extras.view_archivesegment`, a single grant rather than four."""
        for mirror in ARCHIVE_MODELS:
            with self.subTest(model=mirror.__name__):
                self.assertEqual(mirror._meta.default_permissions, ())

    def test_mirrors_hold_no_foreign_keys(self):
        """
        A real relation would be a cross-database constraint the moment the alias is repointed.

        `period_key` is the join key to `ArchiveSegment` instead. Only concrete forward relations matter
        here; the reverse `GenericRelation` descriptors inherited from `BaseModel` add no column and no
        constraint.
        """
        for mirror in ARCHIVE_MODELS:
            with self.subTest(model=mirror.__name__):
                relations = [f.name for f in mirror._meta.fields if f.is_relation]
                self.assertEqual(relations, [])
