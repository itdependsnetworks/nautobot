"""Database routers."""

from nautobot.core.constants import CHANGELOG_ARCHIVE
from nautobot.core.utils.config import changelog_archive_is_separate


class ChangelogArchiveRouter:
    """
    Pins the long-term retention models to the `changelog_archive` connection alias.

    A Django router picks a *database*, not a table, and cannot dispatch by row, so this router does not
    decide whether a given read is warm or retained. That is decided a layer up, by the read surfaces
    resolving a warm model to its `Archived*` mirror. What this router does is narrower and worth keeping
    narrow:

    - Pin the mirrors to their own alias, so the alias stays repointable at a separate host by
      configuration rather than by code change.
    - Keep `allow_migrate` honest, so `nautobot-server migrate` builds each table exactly once, on the
      connection that owns it.

    Every other model, `JobLogEntry` included, is left alone. Returning `None` hands the decision back to
    Django, which matters because `JobResult.log` writes through the `job_logs` alias explicitly and this
    router must not intercept that.
    """

    def _is_archive_model(self, model):
        """Whether `model` is one of the registered long-term retention mirrors."""
        # Imported lazily: the registry is populated during app loading, and this module is imported from
        # settings before that finishes.
        # Resolved through the base: reads use the concrete per-period class, which is generated rather
        # than registered, so asking about it by identity would send retained reads to `default`.
        from nautobot.extras.models.archive import archive_base_of
        from nautobot.extras.registry import registry

        return archive_base_of(model) in registry["changelog_archive_models"].values()

    def db_for_read(self, model, **hints):
        return CHANGELOG_ARCHIVE if self._is_archive_model(model) else None

    def db_for_write(self, model, **hints):
        return CHANGELOG_ARCHIVE if self._is_archive_model(model) else None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Permit relations spanning the default and archive aliases.

        Nothing in the retention models declares such a relation: the mirrors hold their references as
        bare columns precisely so that no constraint spans the two connections. This stays permissive
        anyway, because by default both aliases address one physical database and Django's cross-database
        guard would otherwise be a false positive for any code that compares instances across them.
        """
        databases = {"default", CHANGELOG_ARCHIVE}
        if obj1._state.db in databases and obj2._state.db in databases:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Nothing migrates onto the archive connection.

        Retained history is one table per period, and rotation creates each of those when the period
        opens. No migration builds them, so a separate archive database has no migrated tables at all and
        needs none.

        When `changelog_archive` addresses the same physical database as `default` -- the default, and the
        only arrangement that needs no provisioning -- this router abstains entirely. That matters beyond
        tidiness: `allow_migrate` also decides which tables `TransactionTestCase` flushes between tests,
        and narrowing that set breaks unrelated fixtures.
        """
        if not changelog_archive_is_separate():
            return None
        if db == CHANGELOG_ARCHIVE:
            return False
        return None
