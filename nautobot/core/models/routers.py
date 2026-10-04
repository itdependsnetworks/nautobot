"""Database routers."""

from nautobot.core.constants import CHANGELOG_ARCHIVE
from nautobot.core.utils.config import changelog_archive_is_separate


class ChangelogArchiveRouter:
    """
    Pins the long-term retention models to the `changelog_archive` connection alias.

    A router picks a database, not a table, so it does not decide whether a read is warm or retained;
    the read surfaces do that by resolving a warm model to its mirror. Every other model is left alone,
    `JobLogEntry` included, because `JobResult.log` writes through the `job_logs` alias explicitly.
    """

    def _is_archive_model(self, model):
        """Whether `model` is a registered retention mirror."""
        # Imported lazily: the registry is populated during app loading, and this module is imported from
        # settings before that finishes.
        from nautobot.extras.registry import registry

        return model in registry["changelog_archive_models"].values()

    def db_for_read(self, model, **hints):
        return CHANGELOG_ARCHIVE if self._is_archive_model(model) else None

    def db_for_write(self, model, **hints):
        return CHANGELOG_ARCHIVE if self._is_archive_model(model) else None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Permit relations spanning the default and archive aliases.

        Nothing declares such a relation. This stays permissive because both aliases address one database
        by default, where Django's cross-database guard would be a false positive.
        """
        databases = {"default", CHANGELOG_ARCHIVE}
        if obj1._state.db in databases and obj2._state.db in databases:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        The retention tables are built on the archive connection, and nothing else is.

        Decided by name, because `model_name` is all a migration gives and the model class may not exist
        yet. Abstains when `changelog_archive` addresses the same database as `default`: `allow_migrate`
        also decides what `TransactionTestCase` flushes between tests, and narrowing that breaks
        unrelated fixtures.
        """
        if not changelog_archive_is_separate():
            return None
        is_archive_model = app_label == "extras" and (model_name or "").startswith("archived")
        if db == CHANGELOG_ARCHIVE:
            return is_archive_model
        return False if is_archive_model else None
