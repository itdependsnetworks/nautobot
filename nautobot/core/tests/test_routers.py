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
    JobConsoleEntry,
    JobLogEntry,
    JobResult,
    ObjectChange,
    Status,
    Tag,
)

ARCHIVE_MODELS = (ArchivedObjectChange, ArchivedJobResult, ArchivedJobLogEntry, ArchivedJobConsoleEntry)
WARM_MODELS = (ObjectChange, JobResult, JobLogEntry, JobConsoleEntry)


# The router asks whether the two connections point at the same place, so these set up each case. A
# fabricated `DATABASES` is the condition itself, where the old flag was a stand-in for it.
SAME_DATABASE = {
    "default": {"ENGINE": "django.db.backends.postgresql", "NAME": "nautobot", "HOST": "db", "PORT": "5432"},
    CHANGELOG_ARCHIVE: {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "nautobot",
        "HOST": "db",
        "PORT": "5432",
    },
}
SEPARATE_DATABASES = {
    "default": {"ENGINE": "django.db.backends.postgresql", "NAME": "nautobot", "HOST": "db", "PORT": "5432"},
    CHANGELOG_ARCHIVE: {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "nautobot_archive",
        "HOST": "archive-db",
        "PORT": "5432",
    },
}


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
        """A model that merely lives in `extras` is not retained history and stays on `default`."""
        for model in (Status, Tag):
            with self.subTest(model=model.__name__):
                self.assertIsNone(self.router.db_for_read(model))
                self.assertIsNone(self.router.db_for_write(model))

    @override_settings(DATABASES=SAME_DATABASE)
    def test_allow_migrate_defers_entirely_when_one_database(self):
        """
        With both aliases on one database there is nothing to route, so the router abstains.

        Not just a simplification: `allow_migrate` also decides which tables `TransactionTestCase` flushes
        between tests, so narrowing that set here broke unrelated job-logging fixtures.
        """
        for model in (*ARCHIVE_MODELS, *WARM_MODELS, Status, Tag):
            with self.subTest(model=model.__name__):
                self.assertIsNone(self.router.allow_migrate("default", "extras", model._meta.model_name))
                self.assertIsNone(self.router.allow_migrate(CHANGELOG_ARCHIVE, "extras", model._meta.model_name))

    @override_settings(DATABASES=SEPARATE_DATABASES)
    def test_warm_tables_are_not_built_on_a_separate_archive_database(self):
        """A separate archive database holds retained history only; `default` keeps building the rest."""
        for model in (*WARM_MODELS, ObjectChange):
            with self.subTest(model=model.__name__):
                self.assertIs(self.router.allow_migrate(CHANGELOG_ARCHIVE, "extras", model._meta.model_name), False)
                self.assertIsNone(self.router.allow_migrate("default", "extras", model._meta.model_name))

    @override_settings(DATABASES=SEPARATE_DATABASES)
    def test_retained_tables_are_built_on_a_separate_archive_database(self):
        """
        The branch that makes a separate archive database usable at all.

        `allow_migrate` returning False here instead would leave `nautobot-server migrate --database
        changelog_archive` with nothing to create, and the retention tables would never exist on the
        database the router sends every retained read and write to.
        """
        for model in ARCHIVE_MODELS:
            with self.subTest(model=model.__name__):
                self.assertIs(self.router.allow_migrate(CHANGELOG_ARCHIVE, "extras", model._meta.model_name), True)
                self.assertIs(self.router.allow_migrate("default", "extras", model._meta.model_name), False)

    @override_settings(DATABASES=SEPARATE_DATABASES)
    def test_allow_migrate_ignores_unknown_models(self):
        """An app_label/model_name Django cannot resolve is not ours to route."""
        self.assertIsNone(self.router.allow_migrate("default", "extras", "nosuchmodel"))
        self.assertIsNone(self.router.allow_migrate("default", "extras", None))

    @override_settings(DATABASES=SAME_DATABASE)
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
        warm = ObjectChange()
        mirror = ArchivedObjectChange()
        warm._state.db = "default"
        mirror._state.db = CHANGELOG_ARCHIVE
        self.assertIs(self.router.allow_relation(warm, mirror), True)
        self.assertIs(self.router.allow_relation(mirror, warm), True)

    def test_allow_relation_defers_for_unrelated_aliases(self):
        warm = ObjectChange()
        mirror = ArchivedObjectChange()
        warm._state.db = "some_other_alias"
        mirror._state.db = CHANGELOG_ARCHIVE
        self.assertIsNone(self.router.allow_relation(warm, mirror))
