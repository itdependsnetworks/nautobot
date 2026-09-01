"""Database routers."""

from nautobot.core.constants import CHANGELOG_ARCHIVE


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
        from nautobot.extras.registry import registry

        return model in registry["changelog_archive_models"].values()

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
        Build each table exactly once, on the connection that owns it.

        When `changelog_archive` addresses the same physical database as `default` -- the default, and the
        only arrangement that needs no provisioning -- there is nothing to route. Both aliases share one
        set of tables and one `django_migrations`, so the `default` run builds everything and a run against
        the archive alias finds every migration already recorded and does nothing. Returning `None` here
        keeps this router out of a decision it has no business making, which matters: `allow_migrate` also
        decides which tables `TransactionTestCase` flushes between tests, and narrowing that set breaks
        unrelated fixtures.

        When the alias is genuinely a separate database it has its own `django_migrations`, replays from
        scratch, and takes only the retention tables -- and `default` must then skip them.
        """
        from django.conf import settings

        if not getattr(settings, "CHANGELOG_ARCHIVE_SEPARATE_DATABASE", False):
            return None

        if model_name is None:
            return None

        from django.apps import apps

        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            return None

        if self._is_archive_model(model):
            return db == CHANGELOG_ARCHIVE
        if db == CHANGELOG_ARCHIVE:
            # A separate archive database holds the retention tables and nothing else.
            return False
        return None
