"""
The contract between each retention mirror and the warm model it holds history for.

Nothing in Django's migration tooling knows the mirrors are meant to track the warm models, so a field
added to `ObjectChange` and not to `ArchivedObjectChange` produces a clean `makemigrations --check` and a
silently incomplete archive from that point on. `check_changelog_archive_schema` catches that at runtime by
comparing field *names*.

These tests are stricter, and they are what caught the drift that check could not see: nine fields whose
`help_text` had been dropped in hand-copying, a lost `verbose_name`, and three `blank=True` the warm columns
do not carry. `help_text` feeds the REST API schema, so a retained record described differently from its
warm equivalent is a schema-parity failure.

The contract is declared rather than inferred: every field must be present on both sides, every shared field
must be *identical* unless this module says otherwise, and each exception says which kind it is and is
checked against what that kind means. A new mirror, or a new reason for two fields to differ, has to be
written down here before the suite will pass.
"""

from django.apps import apps
from django.db import models
from django.db.models.fields import NOT_PROVIDED

from nautobot.core.management.commands import EXEMPT_ATTRS
from nautobot.core.testing import TestCase
from nautobot.extras.models.archive import MIRROR_DERIVED_FIELDS
from nautobot.extras.registry import registry

# Present on every mirror and on no warm model: which calendar period files the record.
MIRROR_ONLY_FIELDS = {"period_key"}

# Kinds of permitted difference, and what each one licenses:
#
# "demoted"   -- a foreign key the mirror holds as a bare `<name>_id` column. Retained records do not
#                depend on live records, so there is no relation to follow and nothing for a delete of the
#                referent to cascade into.
# "unstamped" -- a timestamp the warm model fills in for itself, with `auto_now_add` or a `default`. The
#                mirror must NOT, because rotation copies the original value: a self-stamping mirror column
#                would overwrite a 2022 record's time with today's and destroy the history the table
#                exists to keep. Only `auto_now_add`, `default`, and `editable` may differ.
MIRROR_FIELD_CONTRACT = {
    "extras.archivedobjectchange": {
        "demoted": {"changed_object_type", "related_object_type", "user"},
        "unstamped": {"time"},
    },
    "extras.archivedjobresult": {
        "demoted": {"canceled_by", "job_model", "scheduled_job", "user"},
        "unstamped": {"date_created"},
    },
    "extras.archivedjoblogentry": {
        "demoted": {"job_result"},
        "unstamped": {"created"},
    },
    "extras.archivedjobconsoleentry": {
        "demoted": {"job_result"},
        "unstamped": {"timestamp"},
    },
}

UNSTAMPED_ALLOWED_KWARGS = {"auto_now_add", "default", "editable"}


def _field_definition(field):
    """
    Everything that defines a field, in both halves Nautobot splits it into.

    `Field.deconstruct` is monkeypatched during migration commands to drop `EXEMPT_ATTRS` -- `help_text`,
    `verbose_name`, and `choices` -- so that editing them generates no migration. That patch is in effect
    under the test runner, which is why comparing deconstructions alone silently passed a mirror whose
    `help_text` had been dropped. Those attributes are non-structural to the database and still reach the
    REST API schema, so they are compared explicitly rather than left to whichever `deconstruct` is bound.
    """
    return (field.deconstruct()[1:], {attr: getattr(field, attr, None) for attr in EXEMPT_ATTRS})


def _mirror_pairs():
    """Every registered mirror with the warm model it holds history for."""
    from nautobot.extras.registry import registry

    return [(apps.get_model(warm_label), mirror) for warm_label, mirror in registry["changelog_archive_models"].items()]


class MirrorFieldContractTestCase(TestCase):
    def test_contract_covers_exactly_the_registered_mirrors(self):
        """A new mirror has to declare its contract before anything else here will check it."""
        self.assertEqual(
            {mirror._meta.label_lower for _warm, mirror in _mirror_pairs()},
            set(MIRROR_FIELD_CONTRACT),
        )

    def test_every_warm_field_is_present_on_the_mirror(self):
        """The gap `check_changelog_archive_schema` exists to catch, asserted at development time."""
        for warm, mirror in _mirror_pairs():
            with self.subTest(mirror=mirror._meta.label):
                contract = MIRROR_FIELD_CONTRACT[mirror._meta.label_lower]
                mirror_names = {field.name for field in mirror._meta.concrete_fields}
                derived = set(MIRROR_DERIVED_FIELDS.get(mirror._meta.label_lower, {}))
                for field in warm._meta.concrete_fields:
                    if field.name in mirror_names or field.name in derived:
                        continue
                    self.assertIn(
                        field.name,
                        contract["demoted"],
                        f"{warm._meta.label}.{field.name} is on neither the mirror nor the contract",
                    )
                    self.assertIn(f"{field.name}_id", mirror_names)

    def test_every_mirror_field_is_accounted_for(self):
        """The reverse gap: a mirror column no warm model has, and nothing explaining it."""
        for warm, mirror in _mirror_pairs():
            with self.subTest(mirror=mirror._meta.label):
                contract = MIRROR_FIELD_CONTRACT[mirror._meta.label_lower]
                warm_names = {field.name for field in warm._meta.concrete_fields}
                allowed = (
                    warm_names
                    | MIRROR_ONLY_FIELDS
                    | {f"{name}_id" for name in contract["demoted"]}
                    | set(MIRROR_DERIVED_FIELDS.get(mirror._meta.label_lower, {}))
                )
                unexplained = {field.name for field in mirror._meta.concrete_fields} - allowed
                self.assertEqual(unexplained, set(), f"{mirror._meta.label} has unexplained fields")

    def test_shared_fields_are_identical(self):
        """
        Anything the contract does not except is a verbatim copy, kwargs included.

        Comparing the full deconstruction rather than the column is the point: `help_text`, `verbose_name`,
        `choices`, and `default` are all invisible to a column comparison and all reach the API schema.
        """
        for warm, mirror in _mirror_pairs():
            contract = MIRROR_FIELD_CONTRACT[mirror._meta.label_lower]
            excepted = contract["demoted"] | contract["unstamped"]
            warm_fields = {field.name: field for field in warm._meta.concrete_fields}
            for field in mirror._meta.concrete_fields:
                if field.name in excepted or field.name not in warm_fields:
                    continue
                with self.subTest(field=f"{mirror._meta.label}.{field.name}"):
                    self.assertEqual(_field_definition(field), _field_definition(warm_fields[field.name]))

    def test_demoted_relations_are_plain_identifier_columns(self):
        """A demoted key must genuinely not be a relation, or it reintroduces the coupling it removed."""
        for warm, mirror in _mirror_pairs():
            contract = MIRROR_FIELD_CONTRACT[mirror._meta.label_lower]
            for name in contract["demoted"]:
                with self.subTest(field=f"{mirror._meta.label}.{name}"):
                    warm_field = warm._meta.get_field(name)
                    self.assertTrue(warm_field.is_relation, f"{name} is not a relation on {warm._meta.label}")
                    mirror_field = mirror._meta.get_field(f"{name}_id")
                    self.assertFalse(mirror_field.is_relation)
                    # The identifier has to be able to hold the referent's key, whatever type that is.
                    target_pk = warm_field.related_model._meta.pk
                    expected = models.UUIDField if isinstance(target_pk, models.UUIDField) else models.IntegerField
                    self.assertIsInstance(mirror_field, expected)
                    self.assertEqual(mirror_field.null, warm_field.null)

    def test_unstamped_timestamps_do_not_fill_themselves_in(self):
        """
        The one exception where getting it wrong destroys data rather than just looking wrong.

        If a mirror timestamp kept `auto_now_add=True`, every record rotation filed would be stamped with
        the time it was filed instead of the time it happened -- and it is filed into the period its
        timestamp names, so the record would land in the wrong period as well.
        """
        for warm, mirror in _mirror_pairs():
            contract = MIRROR_FIELD_CONTRACT[mirror._meta.label_lower]
            for name in contract["unstamped"]:
                with self.subTest(field=f"{mirror._meta.label}.{name}"):
                    warm_field = warm._meta.get_field(name)
                    mirror_field = mirror._meta.get_field(name)
                    # The exception is only warranted where the warm column really does stamp itself.
                    self.assertTrue(
                        getattr(warm_field, "auto_now_add", False) or warm_field.default is not NOT_PROVIDED,
                        f"{warm._meta.label}.{name} does not fill itself in, so it needs no exception",
                    )
                    self.assertFalse(getattr(mirror_field, "auto_now_add", False))
                    self.assertIs(mirror_field.default, NOT_PROVIDED)
                    # Nothing else about the field may drift under cover of this exception.
                    warm_kwargs = warm_field.deconstruct()[3] | {a: getattr(warm_field, a, None) for a in EXEMPT_ATTRS}
                    mirror_kwargs = mirror_field.deconstruct()[3] | {
                        a: getattr(mirror_field, a, None) for a in EXEMPT_ATTRS
                    }
                    differing = {
                        key
                        for key in set(warm_kwargs) | set(mirror_kwargs)
                        if warm_kwargs.get(key, NOT_PROVIDED) is not mirror_kwargs.get(key, NOT_PROVIDED)
                        and warm_kwargs.get(key) != mirror_kwargs.get(key)
                    }
                    self.assertEqual(differing - UNSTAMPED_ALLOWED_KWARGS, set())


class MirrorFeatureRegistryTestCase(TestCase):
    """
    A mirror must not register itself for any extras feature.

    Mirrors copy their warm counterpart field for field, and several feature registries are populated by
    looking for a field name. That makes a mirror look like a participant in features it has no business
    in: `ArchivedJobResult` carries `_custom_field_data` because `JobResult` does, and so registered as a
    custom field model. The consequences were an admin being offered retained job results in the custom
    field content type picker, and `cleanup_custom_field_data()` streaming every retained row over the
    archive database and then writing to the ones that held an orphaned key. Retained history is immutable,
    and it is the table this feature exists to let grow.

    Each mirror opts out with the flag the corresponding registry lookup constrains on, which is why this
    test names no feature: a new feature detected by field name would otherwise capture the mirrors
    silently, exactly as this one did.
    """

    def test_no_mirror_registers_for_any_feature(self):
        mirrors = {model._meta.label_lower for model in registry["changelog_archive_models"].values()}
        self.assertNotEqual(mirrors, set(), "no mirrors registered, so this test would pass vacuously")

        for feature, entries in registry["model_features"].items():
            with self.subTest(feature=feature):
                registered = {f"{app_label}.{name}" for app_label, names in entries.items() for name in names}
                self.assertEqual(mirrors & registered, set())
