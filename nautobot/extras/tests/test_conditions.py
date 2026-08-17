"""Tests for the condition evaluation engine, preset catalog, and payload builder."""

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase

from nautobot.dcim.models import Device, Location
from nautobot.extras.choices import ConditionTypeChoices, ObjectChangeActionChoices
from nautobot.extras.conditions import engine
from nautobot.extras.conditions.engine import (
    compile_condition,
    ConditionError,
    evaluate_condition,
    evaluate_conditions,
    resolve_condition,
)
from nautobot.extras.conditions.payload import event_value
from nautobot.extras.conditions.presets import (
    ConditionPreset,
    get_condition_preset,
    get_condition_presets,
    PresetParameter,
    register_condition_preset,
)
from nautobot.extras.models import Webhook
from nautobot.extras.models.mixins import ConditionalTriggerMixin


def expression_row(source):
    return {"type": ConditionTypeChoices.TYPE_EXPRESSION, "source": source}


def preset_row(key, **params):
    return {"type": ConditionTypeChoices.TYPE_PRESET, "preset": key, "params": params}


UPDATE_PAYLOAD = {
    "event": "updated",
    "timestamp": "2026-07-27 00:00:00",
    "model": "device",
    "username": "alice",
    "request_id": "6f1c1d3e-0000-0000-0000-000000000000",
    "data": {"name": "device-1", "status": {"name": "Active", "id": 1}},
    "snapshots": {
        "prechange": {"name": "device-1", "status": {"name": "Staged", "id": 2}},
        "postchange": {"name": "device-1", "status": {"name": "Active", "id": 1}},
        "differences": {
            "added": {"status": {"name": "Active", "id": 1}},
            "removed": {"status": {"name": "Staged", "id": 2}},
        },
    },
}

DELETE_PAYLOAD = {
    "event": "deleted",
    "timestamp": "2026-07-27 00:00:00",
    "model": "device",
    "username": "alice",
    "request_id": "6f1c1d3e-0000-0000-0000-000000000000",
    "data": {"name": "device-1", "status": {"name": "Active", "id": 1}},
    "snapshots": {
        "prechange": {"name": "device-1", "status": {"name": "Active", "id": 1}},
        "postchange": None,
        "differences": {"added": None, "removed": {"name": "device-1", "status": {"name": "Active", "id": 1}}},
    },
}


class ConditionEngineTestCase(TestCase):
    """A condition passes only on a truthy result, and missing data is falsy rather than fatal."""

    def test_truthy_result_passes(self):
        result = evaluate_condition(expression_row("data.name == 'device-1'"), UPDATE_PAYLOAD)
        self.assertTrue(result.passed)
        self.assertIsNone(result.error)

    def test_falsy_results_fail(self):
        for source in ("''", "none", "0", "[]", "{}", "false"):
            with self.subTest(source=source):
                result = evaluate_condition(expression_row(source), UPDATE_PAYLOAD)
                self.assertFalse(result.passed)
                self.assertIsNone(result.error, "a falsy result is a failure, not an error")

    def test_missing_key_is_falsy_not_fatal(self):
        """A condition naming something absent from the payload fails its row without raising."""
        for source in (
            "data.no_such_field",
            "nonexistent_variable",
            "snapshots.postchange.status",
            "a.deeply.nested.path.that.does.not.exist",
        ):
            with self.subTest(source=source):
                result = evaluate_condition(expression_row(source), DELETE_PAYLOAD)
                self.assertFalse(result.passed)
                self.assertIsNone(result.error, f"{source} should evaluate falsy, not error")

    def test_delete_payload_referencing_postchange_does_not_error(self):
        """The acceptance criterion for deletes: false, not an exception."""
        result = evaluate_condition(expression_row("snapshots.postchange.status.name == 'Active'"), DELETE_PAYLOAD)
        self.assertFalse(result.passed)
        self.assertIsNone(result.error)

    def test_error_is_contained_and_recorded(self):
        """An expression that genuinely raises fails its row and records why."""
        result = evaluate_condition(expression_row("data.name / 0"), UPDATE_PAYLOAD)
        self.assertFalse(result.passed)
        self.assertIsNotNone(result.error)

    def test_non_compiling_expression_is_reported(self):
        with self.assertRaises(ConditionError):
            compile_condition("data.name ==")

    def test_delimiters_are_rejected_with_a_useful_message(self):
        """Jinja reports a stray delimiter as a token error, which says nothing about the actual mistake."""
        for source in ("{{ data.name }}", "{% if data.name %}x{% endif %}"):
            with self.subTest(source=source):
                with self.assertRaises(ConditionError) as ctx:
                    compile_condition(source)
                self.assertIn("bare expression", str(ctx.exception))

    def test_a_single_expression_may_span_lines(self):
        """One expression is the constraint, not one line."""
        result = evaluate_condition(
            expression_row("data.name == 'device-1'\n    and username == 'alice'"), UPDATE_PAYLOAD
        )
        self.assertTrue(result.passed)
        self.assertIsNone(result.error)

    def test_multiple_expressions_are_rejected(self):
        with self.assertRaises(ConditionError):
            compile_condition("data.name; username")

    def test_statements_are_not_expressions(self):
        """`compile_expression` accepts expressions only, so statements cannot be smuggled in."""
        for source in ("{% for x in data %}{% endfor %}", "{% set x = 1 %}"):
            with self.subTest(source=source):
                with self.assertRaises(ConditionError):
                    compile_condition(source)

    def test_sandbox_blocks_introspection(self):
        """Classic SSTI probes must not produce a truthy result."""
        for source in (
            "''.__class__",
            "data.__class__.__mro__",
            "''.__class__.__mro__[1].__subclasses__()",
            "self.__init__.__globals__",
        ):
            with self.subTest(source=source):
                result = evaluate_condition(expression_row(source), UPDATE_PAYLOAD)
                self.assertFalse(result.passed, f"{source} must not pass a condition row")

    def test_filters_from_the_shared_environment_are_available(self):
        """Conditions get the same filter set webhook body templates get."""
        result = evaluate_condition(expression_row("data.name | upper == 'DEVICE-1'"), UPDATE_PAYLOAD)
        self.assertTrue(result.passed)

    def test_all_rows_are_evaluated_even_after_a_failure(self):
        """Dry-run needs a verdict per row, not just the first one that stopped the rule."""
        results = evaluate_conditions(
            [expression_row("false"), expression_row("true"), expression_row("data.name")],
            UPDATE_PAYLOAD,
        )
        self.assertEqual([r.passed for r in results], [False, True, True])

    def test_negate_inverts_a_row(self):
        """`negate` is one flag on the row, so it covers presets and raw expressions alike."""
        for row in (
            expression_row("data.name == 'device-1'"),
            preset_row("field_compare", field="status", operator="=", value="Active"),
        ):
            with self.subTest(row=row["type"]):
                self.assertTrue(evaluate_condition(row, UPDATE_PAYLOAD).passed)
                self.assertFalse(evaluate_condition({**row, "negate": True}, UPDATE_PAYLOAD).passed)

    def test_negate_does_not_rescue_an_errored_row(self):
        """Inverting a broken condition into a pass would fire a rule on a mistake."""
        result = evaluate_condition({**preset_row("no_such_preset"), "negate": True}, UPDATE_PAYLOAD)
        self.assertFalse(result.passed)
        self.assertIsNotNone(result.error)

    def test_unknown_row_type_is_an_error_not_a_crash(self):
        result = evaluate_condition({"type": "nonsense"}, UPDATE_PAYLOAD)
        self.assertFalse(result.passed)
        self.assertIn("Unknown condition row type", result.error)

    def test_unknown_preset_is_an_error_not_a_crash(self):
        result = evaluate_condition(preset_row("no_such_preset"), UPDATE_PAYLOAD)
        self.assertFalse(result.passed)
        self.assertIn("Unknown condition preset", result.error)


class CompilationCacheTestCase(TestCase):
    """Expression sources are compiled once, not once per event, and the cache is bounded."""

    def setUp(self):
        super().setUp()
        compile_condition.cache_clear()

    def test_identical_source_compiles_once(self):
        first = compile_condition("data.name == 'a'")
        second = compile_condition("data.name == 'a'")
        self.assertIs(first, second)
        self.assertEqual(compile_condition.cache_info().currsize, 1)

    def test_a_preset_shared_by_many_actions_compiles_once(self):
        """The reason the cache keys on source rather than on the owning action."""
        for _ in range(5):
            evaluate_condition(preset_row("field_changed", field="status"), UPDATE_PAYLOAD)
        self.assertEqual(compile_condition.cache_info().currsize, 1)

    def test_changed_source_is_a_different_entry(self):
        compile_condition("data.name == 'a'")
        compile_condition("data.name == 'b'")
        self.assertEqual(compile_condition.cache_info().currsize, 2)

    def test_non_compiling_source_is_not_cached(self):
        with self.assertRaises(ConditionError):
            compile_condition("data.name ==")
        self.assertEqual(compile_condition.cache_info().currsize, 0)

    def test_a_source_with_delimiters_is_not_cached(self):
        with self.assertRaises(ConditionError):
            compile_condition("{{ data.name }}")
        self.assertEqual(compile_condition.cache_info().currsize, 0)

    def test_the_cache_is_bounded(self):
        """Form validation compiles every expression a user types, so it must not grow without limit."""
        for index in range(engine._MAX_COMPILED_EXPRESSIONS + 20):
            compile_condition(f"data.name == 'device-{index}'")
        self.assertEqual(compile_condition.cache_info().currsize, engine._MAX_COMPILED_EXPRESSIONS)

    def test_eviction_drops_the_least_recently_used_entry(self):
        """A preset in constant use should outlive a one-off expression typed into a form after it."""
        in_use = "data.name == 'kept'"
        compile_condition(in_use)
        for index in range(engine._MAX_COMPILED_EXPRESSIONS - 1):
            compile_condition(f"data.name == 'filler-{index}'")
        compile_condition(in_use)  # using it again is what saves it
        misses_before = compile_condition.cache_info().misses
        compile_condition("data.name == 'the-one-that-evicts'")
        compile_condition(in_use)
        self.assertEqual(
            compile_condition.cache_info().misses,
            misses_before + 1,
            "the entry in use was evicted, so looking it up again had to recompile",
        )


class ConditionPresetTestCase(TestCase):
    """Each built-in preset does what its name says, on both update and delete payloads."""

    def assertPreset(self, key, payload, expected, **params):
        result = evaluate_condition(preset_row(key, **params), payload)
        self.assertIsNone(result.error)
        self.assertEqual(result.passed, expected, f"{key}({params}) on {payload['event']}")

    def test_field_transition(self):
        self.assertPreset(
            "field_transition", UPDATE_PAYLOAD, True, field="status", **{"from": "Staged", "to": "Active"}
        )
        self.assertPreset(
            "field_transition", UPDATE_PAYLOAD, False, field="status", **{"from": "Staged", "to": "Failed"}
        )
        self.assertPreset(
            "field_transition", UPDATE_PAYLOAD, False, field="status", **{"from": "Planned", "to": "Active"}
        )

    def test_field_transition_on_delete_is_false_not_error(self):
        self.assertPreset("field_transition", DELETE_PAYLOAD, False, field="status", **{"from": "Active", "to": "Gone"})

    def test_field_changed(self):
        self.assertPreset("field_changed", UPDATE_PAYLOAD, True, field="status")
        self.assertPreset("field_changed", UPDATE_PAYLOAD, False, field="name")

    def test_field_changed_on_delete_is_false_not_error(self):
        """`differences.added` is None on a delete, which must not blow up the `in` test."""
        self.assertPreset("field_changed", DELETE_PAYLOAD, False, field="status")

    def test_field_compare_equals(self):
        self.assertPreset("field_compare", UPDATE_PAYLOAD, True, field="status", operator="=", value="Active")
        self.assertPreset("field_compare", UPDATE_PAYLOAD, False, field="status", operator="=", value="Staged")
        self.assertPreset("field_compare", UPDATE_PAYLOAD, False, field="no_such_field", operator="=", value="Active")

    def test_field_compare_every_operator(self):
        """Each operator, on the payload's own values, so the wiring is exercised end to end."""
        cases = [
            ("name", "=", "device-1", True),
            ("name", "startswith", "device", True),
            ("name", "startswith", "switch", False),
            ("name", "endswith", "-1", True),
            ("name", "contains", "vic", True),
            ("name", "contains", "zzz", False),
            ("status", "in", "Active,Staged", True),
            ("status", "in", "Failed,Offline", False),
            ("name", "gt", "a", True),
            ("name", "lt", "a", False),
        ]
        for field, operator, value, expected in cases:
            with self.subTest(operator=operator, value=value):
                self.assertPreset(
                    "field_compare", UPDATE_PAYLOAD, expected, field=field, operator=operator, value=value
                )

    def test_field_compare_on_a_list_field(self):
        """
        `tags in critical,urgent` reads as "tagged with either", so `in` looks for an overlap.

        Comparing the list as a whole against each name could never match, which made `in` silently useless
        on the one kind of field people most want to use it on.
        """
        payload = {
            **UPDATE_PAYLOAD,
            "data": {**UPDATE_PAYLOAD["data"], "tags": [{"name": "critical"}, {"name": "edge"}]},
        }
        cases = [
            ("in", "critical,urgent", True),
            ("in", "edge", True),
            ("in", "urgent,retired", False),
            # `contains` asks whether one named entry is present, and already worked this way.
            ("contains", "critical", True),
            ("contains", "urgent", False),
        ]
        for operator, value, expected in cases:
            with self.subTest(operator=operator, value=value):
                self.assertPreset("field_compare", payload, expected, field="tags", operator=operator, value=value)

    def test_field_compare_numeric_comparison(self):
        """Ordering operators compare as numbers when both sides are numbers, not as text."""
        payload = {**UPDATE_PAYLOAD, "data": {**UPDATE_PAYLOAD["data"], "mtu": 9000}}
        for operator, value, expected in [
            ("gt", "1500", True),
            ("gt", "9000", False),
            ("gte", "9000", True),
            ("lt", "9500", True),
            ("lte", "9000", True),
            # Lexicographically "9000" < "9500" too, so use a case where text and numbers disagree.
            ("gt", "10000", False),
        ]:
            with self.subTest(operator=operator, value=value):
                self.assertPreset("field_compare", payload, expected, field="mtu", operator=operator, value=value)

    def test_field_compare_reads_a_dotted_field(self):
        """`status` and `status.name` should both work, the second by reaching inside the related object."""
        for field in ("status", "status.name"):
            with self.subTest(field=field):
                self.assertPreset("field_compare", UPDATE_PAYLOAD, True, field=field, operator="=", value="Active")
        # A path that goes nowhere is falsy rather than an error.
        self.assertPreset("field_compare", UPDATE_PAYLOAD, False, field="nope.deep", operator="=", value="Active")

    def test_field_compare_rejects_an_unknown_operator(self):
        from django.core.exceptions import ValidationError

        preset = get_condition_preset("field_compare")
        with self.assertRaises(ValidationError) as ctx:
            preset.clean_params({"field": "status", "operator": "sideways", "value": "x"})
        self.assertIn("must be one of", str(ctx.exception))

    def test_user_is(self):
        self.assertPreset("user_is", UPDATE_PAYLOAD, True, username="alice")
        self.assertPreset("user_is", UPDATE_PAYLOAD, False, username="bob")

    def test_user_is_not(self):
        self.assertPreset("user_is_not", UPDATE_PAYLOAD, True, username="bob")
        self.assertPreset("user_is_not", UPDATE_PAYLOAD, False, username="alice")

    def test_params_never_reach_the_expression_source(self):
        """A parameter that looks like template syntax is data, not code."""
        result = evaluate_condition(
            preset_row("field_compare", field="name", operator="=", value="{{ 7 * 7 }}"), UPDATE_PAYLOAD
        )
        self.assertFalse(result.passed)
        self.assertIsNone(result.error)
        # The source is a constant regardless of what the user typed.
        source, params = resolve_condition(preset_row("field_compare", field="name", operator="=", value="{{ 7 * 7 }}"))
        self.assertEqual(source, get_condition_preset("field_compare").source)
        self.assertEqual(params["param_value"], "{{ 7 * 7 }}")

    def test_every_builtin_preset_compiles(self):
        for preset in get_condition_presets():
            with self.subTest(preset=preset.key):
                self.assertIsNotNone(compile_condition(preset.source))

    def test_builtin_presets_are_registered(self):
        keys = {preset.key for preset in get_condition_presets()}
        self.assertEqual(
            keys,
            {"field_transition", "field_changed", "field_compare", "user_is", "user_is_not"},
        )


class PresetRegistrationTestCase(TestCase):
    """Registration is idempotent for the same preset and a conflict for a different one."""

    def make_preset(self, source="true"):
        return ConditionPreset(
            key="test_only_preset",
            label="Test only",
            description="",
            source=source,
            parameters=(PresetParameter(name="thing", label="Thing"),),
        )

    def tearDown(self):
        super().tearDown()
        from nautobot.extras.registry import registry

        registry["condition_presets"].pop("test_only_preset", None)

    def test_registering_the_same_preset_twice_is_a_noop(self):
        preset = self.make_preset()
        register_condition_preset(preset)
        register_condition_preset(self.make_preset())  # equal by value
        self.assertEqual(get_condition_preset("test_only_preset"), preset)

    def test_registering_a_different_preset_under_one_key_conflicts(self):
        register_condition_preset(self.make_preset())
        with self.assertRaises(KeyError):
            register_condition_preset(self.make_preset(source="false"))

    def test_non_preset_is_rejected(self):
        with self.assertRaises(TypeError):
            register_condition_preset("not a preset")


class PresetParamValidationTestCase(TestCase):
    """`clean_params` is what stops a malformed rule reaching the database."""

    def setUp(self):
        super().setUp()
        self.preset = get_condition_preset("field_transition")

    def test_valid_params_pass(self):
        self.preset.clean_params({"field": "status", "from": "a", "to": "b"})

    def test_missing_required_param_is_rejected(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.preset.clean_params({"field": "status", "from": "a"})

    def test_empty_required_param_is_rejected(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.preset.clean_params({"field": "status", "from": "a", "to": ""})

    def test_unknown_param_is_rejected(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError) as ctx:
            self.preset.clean_params({"field": "status", "from": "a", "to": "b", "extra": "x"})
        self.assertIn("extra", str(ctx.exception))

    def test_non_string_param_is_rejected(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.preset.clean_params({"field": "status", "from": "a", "to": 7})

    def test_params_schema_is_json_serializable(self):
        import json

        json.dumps(self.preset.as_dict())


class EventValueTestCase(TestCase):
    """The same comparison works whether a field serialized as a nested object or a bare key."""

    def test_nested_object_reduces_to_a_comparable_value(self):
        self.assertEqual(event_value({"id": 1, "name": "Active", "url": "..."}), "Active")

    def test_value_key_wins_over_name(self):
        self.assertEqual(event_value({"value": "active", "name": "Active"}), "active")

    def test_bare_value_is_unchanged(self):
        self.assertEqual(event_value("Active"), "Active")
        self.assertEqual(event_value(7), 7)
        self.assertIsNone(event_value(None))

    def test_object_without_a_recognized_key_is_returned_whole(self):
        self.assertEqual(event_value({"foo": "bar"}), {"foo": "bar"})

    def test_lists_normalize_element_by_element(self):
        self.assertEqual(event_value([{"name": "a"}, {"name": "b"}]), ["a", "b"])


class ResolveConditionTestCase(TestCase):
    """Malformed rows are reported clearly rather than crashing the worker."""

    def test_expression_row_returns_its_source(self):
        source, params = resolve_condition(expression_row("true"))
        self.assertEqual(source, "true")
        self.assertEqual(params, {})

    def test_preset_row_returns_prefixed_params(self):
        _source, params = resolve_condition(preset_row("user_is", username="alice"))
        self.assertEqual(params, {"param_username": "alice"})

    def test_row_must_be_a_mapping(self):
        with self.assertRaises(ConditionError):
            resolve_condition("not a row")

    def test_expression_row_needs_a_source(self):
        for row in ({"type": "expression"}, {"type": "expression", "source": "   "}):
            with self.subTest(row=row):
                with self.assertRaises(ConditionError):
                    resolve_condition(row)

    def test_preset_params_must_be_a_mapping(self):
        with self.assertRaises(ConditionError):
            resolve_condition({"type": "preset", "preset": "user_is", "params": "nope"})


class PayloadShapeTestCase(TestCase):
    """The payload uses the same names the webhook body-template context uses."""

    def test_expected_keys(self):
        self.assertEqual(
            set(UPDATE_PAYLOAD),
            {"event", "timestamp", "model", "username", "request_id", "data", "snapshots"},
        )

    def test_event_names_match_the_display_form(self):
        """`event` is "created"/"updated"/"deleted", not the raw action value."""
        self.assertEqual(
            {dict(ObjectChangeActionChoices)[a].lower() for a, _ in ObjectChangeActionChoices.CHOICES},
            {"created", "updated", "deleted"},
        )


class ConditionalTriggerValidationTestCase(TestCase):
    """A scope or condition that could not run must not be saveable."""

    @classmethod
    def setUpTestData(cls):
        cls.device_ct = ContentType.objects.get_for_model(Device)

    def make_webhook(self, **kwargs):
        kwargs.setdefault("name", "conditional webhook")
        kwargs.setdefault("payload_url", "http://example.com/test")
        kwargs.setdefault("type_update", True)
        webhook = Webhook(**kwargs)
        webhook.save()
        webhook.content_types.set([self.device_ct])
        return webhook

    def test_a_valid_condition_saves(self):
        webhook = self.make_webhook(conditions=[expression_row("data.name")])
        webhook.validated_save()
        self.assertEqual(str(webhook), "conditional webhook")

    def test_unknown_preset_key_is_rejected(self):
        webhook = self.make_webhook(conditions=[preset_row("no_such_preset")])
        with self.assertRaises(ValidationError) as ctx:
            webhook.validated_save()
        self.assertIn("unknown preset", str(ctx.exception))

    def test_bad_preset_params_are_rejected(self):
        webhook = self.make_webhook(conditions=[preset_row("field_transition", field="status")])
        with self.assertRaises(ValidationError) as ctx:
            webhook.validated_save()
        self.assertIn("requires parameter", str(ctx.exception))

    def test_non_compiling_expression_is_rejected(self):
        webhook = self.make_webhook(conditions=[expression_row("data.name ==")])
        with self.assertRaises(ValidationError) as ctx:
            webhook.validated_save()
        self.assertIn("Condition 1", str(ctx.exception))

    def test_unknown_condition_type_is_rejected(self):
        webhook = self.make_webhook(conditions=[{"type": "nonsense"}])
        with self.assertRaises(ValidationError) as ctx:
            webhook.validated_save()
        self.assertIn("unknown condition type", str(ctx.exception))

    def test_conditions_must_be_a_list(self):
        webhook = self.make_webhook(conditions={"type": "expression", "source": "true"})
        with self.assertRaises(ValidationError) as ctx:
            webhook.validated_save()
        self.assertIn("must be a list", str(ctx.exception))

    def test_error_message_names_the_offending_row(self):
        webhook = self.make_webhook(conditions=[expression_row("true"), expression_row("data.name ==")])
        with self.assertRaises(ValidationError) as ctx:
            webhook.validated_save()
        self.assertIn("Condition 2", str(ctx.exception))

    def test_negate_must_be_a_boolean(self):
        webhook = self.make_webhook(conditions=[{**expression_row("true"), "negate": "yes"}])
        with self.assertRaises(ValidationError) as ctx:
            webhook.validated_save()
        self.assertIn("must be true or false", str(ctx.exception))

    def test_blank_rows_are_dropped_rather_than_rejected(self):
        webhook = self.make_webhook(conditions=[expression_row("true"), {}, None])
        webhook.validated_save()
        self.assertEqual(len(webhook.conditions), 1)

    def test_unknown_scope_filter_parameter_is_rejected(self):
        webhook = self.make_webhook(scope_filter={"no_such_param": "x"})
        with self.assertRaises(ValidationError) as ctx:
            webhook.validated_save()
        self.assertIn("no filter parameter", str(ctx.exception))

    def test_valid_scope_filter_is_accepted(self):
        webhook = self.make_webhook(scope_filter={"name": ["device-1"]})
        webhook.validated_save()

    def test_empty_scope_and_conditions_are_allowed(self):
        """The default state, and the one that must behave exactly as it did before this existed."""
        webhook = self.make_webhook()
        webhook.validated_save()
        self.assertFalse(webhook.has_conditional_trigger)

    def test_has_conditional_trigger(self):
        self.assertTrue(self.make_webhook(conditions=[expression_row("true")]).has_conditional_trigger)
        self.assertTrue(self.make_webhook(name="scoped", scope_filter={"name": ["x"]}).has_conditional_trigger)

    def test_scope_filter_prefixed(self):
        webhook = self.make_webhook(scope_filter={"name": ["device-1"]})
        self.assertEqual(webhook.scope_filter_prefixed, {"scope-name": ["device-1"]})

    def test_watches_action(self):
        webhook = self.make_webhook(type_create=True, type_update=False, type_delete=True)
        self.assertTrue(webhook.watches_action(ObjectChangeActionChoices.ACTION_CREATE))
        self.assertFalse(webhook.watches_action(ObjectChangeActionChoices.ACTION_UPDATE))
        self.assertTrue(webhook.watches_action(ObjectChangeActionChoices.ACTION_DELETE))

    def test_job_hooks_validate_the_same_way(self):
        """The mixin is shared, so a job hook rejects exactly what a webhook rejects."""
        from nautobot.extras.models import Job, JobHook

        job = Job.objects.filter(is_job_hook_receiver=True, installed=True, enabled=True).first()
        if job is None:
            self.skipTest("no installed and enabled job hook receiver")
        job_hook = JobHook(
            name="conditional job hook", job=job, type_update=True, conditions=[expression_row("data.name ==")]
        )
        job_hook.save()
        job_hook.content_types.set([self.device_ct])
        with self.assertRaises(ValidationError) as ctx:
            job_hook.validated_save()
        self.assertIn("Condition 1", str(ctx.exception))


class ConditionalTriggerScopeTestCase(TestCase):
    """`matches_scope` is what the signal receiver calls, once per scoped action per changed object."""

    @classmethod
    def setUpTestData(cls):
        cls.device_ct = ContentType.objects.get_for_model(Device)
        cls.device = Device.objects.first()
        cls.location = cls.device.location

    def make_webhook(self, scope_filter):
        webhook = Webhook(
            name=f"scope-{len(scope_filter)}-{id(scope_filter)}",
            payload_url="http://example.com/test",
            type_update=True,
            scope_filter=scope_filter,
        )
        webhook.save()
        webhook.content_types.set([self.device_ct])
        return webhook

    def test_empty_scope_matches_everything_without_a_query(self):
        webhook = self.make_webhook({})
        with self.assertNumQueries(0):
            self.assertTrue(webhook.matches_scope(self.device))

    def test_matching_scope_returns_true(self):
        self.assertTrue(self.make_webhook({"name": [self.device.name]}).matches_scope(self.device))

    def test_non_matching_scope_returns_false(self):
        self.assertFalse(self.make_webhook({"name": ["definitely-not-this-device"]}).matches_scope(self.device))

    def test_scope_check_is_a_single_query(self):
        webhook = self.make_webhook({"name": [self.device.name]})
        with self.assertNumQueries(1):
            webhook.matches_scope(self.device)

    def test_unreadable_scope_matches_nothing(self):
        """
        A filter that cannot be applied makes the action inert, rather than firing for everything.

        A scope filter exists to narrow, so widening it to every object would deliver webhooks and run job
        hooks against objects the author excluded, and a delivery cannot be recalled.
        """
        webhook = self.make_webhook({"name": [self.device.name]})
        Webhook.objects.filter(pk=webhook.pk).update(scope_filter={"no_such_param": "x"})
        webhook.refresh_from_db()
        with self.assertLogs("nautobot.extras.models.mixins", level="ERROR"):
            self.assertFalse(webhook.matches_scope(self.device))

    def test_invalid_scope_value_matches_nothing(self):
        webhook = self.make_webhook({"name": [self.device.name]})
        Webhook.objects.filter(pk=webhook.pk).update(scope_filter={"device_type": ["no-such-device-type"]})
        webhook.refresh_from_db()
        with self.assertLogs("nautobot.extras.models.mixins", level="ERROR"):
            self.assertFalse(webhook.matches_scope(self.device))

    def test_check_scope_filter_validates_every_content_type(self):
        """One filter is stored for every watched type, so a parameter only one supports is rejected."""
        location_ct = ContentType.objects.get_for_model(Location)
        error = ConditionalTriggerMixin.check_scope_filter({"serial": ["ABC"]}, [self.device_ct, location_ct])
        self.assertIsNotNone(error)
        self.assertIn("Location", error)
