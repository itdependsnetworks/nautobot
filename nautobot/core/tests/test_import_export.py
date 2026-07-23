"""Consolidated test suite for the Configurable Import / Export with Upsert feature.

Organized to match `test-matrix-import-export.md`. The pattern (mirroring
`extras.tests.test_customfields.CustomFieldBackgroundTasks`) is:

    setup a scenario  →  run the job via a helper  →  assert the outcome via helpers

`ImportExportJobTestCase` provides the cadence:

    run_export(**opts) / run_import(csv_data, **opts)   — run the system job, assert its status, return it
    export_text / export_lines / export_rows / export_document / export_filename(jr)  — read the produced file
    assertImport(jr, created=, updated=, unchanged=, match_fields=, source=)  — assert the upsert summary
    assertLog(jr, substr, level=) / assertNoLog(...) / assertNoIssues(jr)     — assert the job log

so each test reads as a few declarative lines.

Naming convention (see the doc):
    test_<layer>_<direction>__<field_type|format>[__<operation>]   # core / adapter / e2e layers
    test_<area>__<case>                                            # match / scope / select / error / perm / rest

Lower-level serializer/parser unit tests for CSV live in `test_csv.py` / `test_api.py`; the
management-command round-trip lives in `test_commands.py`.
"""

from django.test import SimpleTestCase

from nautobot.core.api.utils import nest_flat_dict
from nautobot.core.constants import CSV_NO_OBJECT, CSV_NULL_TYPE

# ===========================================================================
# Layer 1c — shared pure functions (format-agnostic core, no DB)
# ===========================================================================


class NestFlatDictTests(SimpleTestCase):
    """`nest_flat_dict` converts flat `a__b` keys to nested dicts (used by both export and import)."""

    def test_core_nest__flat_to_nested(self):
        result = nest_flat_dict({"name": "iface", "device__name": "dev", "device__tenant__name": "ten"})
        self.assertEqual(result, {"name": "iface", "device": {"name": "dev", "tenant": {"name": "ten"}}})

    def test_core_nest__nested_passthrough(self):
        self.assertEqual(nest_flat_dict({"name": "x", "color": "111111"}), {"name": "x", "color": "111111"})

    def test_core_nest__sentinels(self):
        result = nest_flat_dict(
            {"tenant__name": CSV_NO_OBJECT, "asset_tag": CSV_NULL_TYPE},
            null_sentinels=(CSV_NO_OBJECT, CSV_NULL_TYPE),
        )
        self.assertIsNone(result["tenant"]["name"])
        self.assertIsNone(result["asset_tag"])

    def test_core_nest__list_value_preserved(self):
        self.assertEqual(nest_flat_dict({"tags": ["a", "b"]}), {"tags": ["a", "b"]})
