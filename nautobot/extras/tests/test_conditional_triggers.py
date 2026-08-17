"""End-to-end tests for the scope and conditions on Webhooks and Job Hooks.

Dispatch only happens when a `web_request_context` exits, so these tests enter one explicitly rather
than relying on a test client request. `process_webhook` is patched at the enqueue boundary, so what is
asserted is *which actions were handed to the delivery queue*. Everything above that line is what the
feature owns.
"""

from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType

from nautobot.core.testing import TestCase
from nautobot.dcim.models import Location, LocationType
from nautobot.extras.choices import ConditionTypeChoices, ObjectChangeActionChoices
from nautobot.extras.conditions.gate import scoped_actions_for_model
from nautobot.extras.context_managers import web_request_context
from nautobot.extras.models import Status, Tag, Webhook

MOCK_URL = "https://8.8.8.8/"


def expression_row(source, negate=False):
    return {"type": ConditionTypeChoices.TYPE_EXPRESSION, "source": source, "negate": negate}


def preset_row(key, **params):
    return {"type": ConditionTypeChoices.TYPE_PRESET, "preset": key, "params": params}


class ConditionalTriggerTestCase(TestCase):
    """Shared fixtures: a Location model to change, and webhooks to fire."""

    def setUp(self):
        super().setUp()
        self.location_ct = ContentType.objects.get_for_model(Location)
        self.location_type = LocationType.objects.get(name="Campus")
        self.statuses = Status.objects.get_for_model(Location)

    def make_webhook(
        self,
        name="hook",
        *,
        events=None,
        scope_filter=None,
        conditions=None,
        enabled=True,
        url=MOCK_URL,
        content_type=None,
    ):
        events = events or [ObjectChangeActionChoices.ACTION_UPDATE]
        webhook = Webhook(
            name=name,
            payload_url=url,
            enabled=enabled,
            type_create=ObjectChangeActionChoices.ACTION_CREATE in events,
            type_update=ObjectChangeActionChoices.ACTION_UPDATE in events,
            type_delete=ObjectChangeActionChoices.ACTION_DELETE in events,
            scope_filter=scope_filter or {},
            conditions=conditions or [],
        )
        webhook.save()
        webhook.content_types.set([content_type or self.location_ct])
        webhook.validated_save()
        return webhook

    def make_location(self, name="Location 1"):
        with web_request_context(self.user):
            location = Location(name=name, status=self.statuses[0], location_type=self.location_type)
            location.save()
        return location

    @staticmethod
    def enqueued_webhook_pks(mock_enqueue):
        return [
            str(call.kwargs.get("args", call.args[0] if call.args else [None])[0])
            for call in mock_enqueue.call_args_list
        ]

    def fire(self, callable_or_obj, **changes):
        """Run a change inside a request context and return the webhook PKs handed to the delivery queue."""
        with patch("nautobot.extras.webhooks.process_webhook.apply_async") as mock_enqueue:
            with web_request_context(self.user):
                if callable(callable_or_obj):
                    callable_or_obj()
                else:
                    for attribute, value in changes.items():
                        setattr(callable_or_obj, attribute, value)
                    callable_or_obj.save()
        return self.enqueued_webhook_pks(mock_enqueue)


class ScopeAndEventTestCase(ConditionalTriggerTestCase):
    """Which actions reach the delivery queue for a given change."""

    def test_in_scope_update_fires_exactly_once(self):
        webhook = self.make_webhook("scoped", scope_filter={"name": ["in-scope"]})
        location = self.make_location("in-scope")
        self.assertEqual(self.fire(location, description="changed"), [str(webhook.pk)])

    def test_out_of_scope_update_does_not_fire(self):
        self.make_webhook("scoped", scope_filter={"name": ["somewhere-else"]})
        location = self.make_location("in-scope")
        self.assertEqual(self.fire(location, description="changed"), [])

    def test_unscoped_action_fires_for_every_object(self):
        webhook = self.make_webhook("unscoped")
        for name in ("one", "two"):
            location = self.make_location(name)
            self.assertEqual(self.fire(location, description="changed"), [str(webhook.pk)])

    def test_an_action_with_no_scope_or_conditions_behaves_as_before(self):
        """The backward-compatibility guarantee: an untouched webhook is unaffected by this feature."""
        webhook = self.make_webhook("legacy")
        self.assertFalse(webhook.has_conditional_trigger)
        location = self.make_location()
        self.assertEqual(self.fire(location, description="changed"), [str(webhook.pk)])

    def test_disabled_action_never_fires(self):
        self.make_webhook("disabled", enabled=False, scope_filter={"name": ["in-scope"]})
        location = self.make_location("in-scope")
        self.assertEqual(self.fire(location, description="changed"), [])

    def test_wrong_event_type_does_not_fire(self):
        self.make_webhook("delete-only", events=[ObjectChangeActionChoices.ACTION_DELETE])
        location = self.make_location()
        self.assertEqual(self.fire(location, description="changed"), [])

    def test_wrong_model_does_not_fire(self):
        from nautobot.dcim.models import Device

        self.make_webhook("devices", content_type=ContentType.objects.get_for_model(Device))
        location = self.make_location()
        self.assertEqual(self.fire(location, description="changed"), [])

    def test_create_fires_a_create_watching_action(self):
        webhook = self.make_webhook(
            "creates", events=[ObjectChangeActionChoices.ACTION_CREATE], scope_filter={"name": ["fresh"]}
        )
        fired = self.fire(
            lambda: Location(name="fresh", status=self.statuses[0], location_type=self.location_type).save()
        )
        self.assertEqual(fired, [str(webhook.pk)])

    def test_in_scope_delete_fires(self):
        """Scope is decided while the row still exists, which is the whole reason it runs in the receiver."""
        webhook = self.make_webhook(
            "deletes", events=[ObjectChangeActionChoices.ACTION_DELETE], scope_filter={"name": ["doomed"]}
        )
        location = self.make_location("doomed")
        self.assertEqual(self.fire(location.delete), [str(webhook.pk)])

    def test_out_of_scope_delete_does_not_fire(self):
        self.make_webhook(
            "deletes", events=[ObjectChangeActionChoices.ACTION_DELETE], scope_filter={"name": ["doomed"]}
        )
        location = self.make_location("survivor")
        self.assertEqual(self.fire(location.delete), [])

    def test_create_that_also_sets_an_m2m_uses_the_create_action(self):
        """
        Creating an object and tagging it is a create followed by an update, but yields one ObjectChange
        whose action is `create`. The scope verdict read back must be the one recorded for that action.
        """
        create_hook = self.make_webhook(
            "creates", events=[ObjectChangeActionChoices.ACTION_CREATE], scope_filter={"name": ["tagged"]}
        )
        self.make_webhook(
            "updates", events=[ObjectChangeActionChoices.ACTION_UPDATE], scope_filter={"name": ["tagged"]}
        )
        tag = Tag.objects.create(name="trigger-tag")
        tag.content_types.add(self.location_ct)

        def create_and_tag():
            location = Location(name="tagged", status=self.statuses[0], location_type=self.location_type)
            location.save()
            location.tags.add(tag)

        self.assertEqual(self.fire(create_and_tag), [str(create_hook.pk)])


class ConditionsTestCase(ConditionalTriggerTestCase):
    """What the conditions decide, once scope has let a change through."""

    def test_passing_condition_fires(self):
        webhook = self.make_webhook("passes", conditions=[expression_row("true")])
        self.assertEqual(self.fire(self.make_location(), description="x"), [str(webhook.pk)])

    def test_failing_condition_does_not_fire(self):
        self.make_webhook("fails", conditions=[expression_row("false")])
        self.assertEqual(self.fire(self.make_location(), description="x"), [])

    def test_every_condition_must_pass(self):
        self.make_webhook("both", conditions=[expression_row("true"), expression_row("false")])
        self.assertEqual(self.fire(self.make_location(), description="x"), [])

    def test_no_conditions_fires(self):
        webhook = self.make_webhook("none", conditions=[])
        self.assertEqual(self.fire(self.make_location(), description="x"), [str(webhook.pk)])

    def test_negate_inverts_a_row(self):
        self.make_webhook("negated", conditions=[expression_row("true", negate=True)])
        self.assertEqual(self.fire(self.make_location(), description="x"), [])

    def test_one_broken_action_does_not_affect_the_others(self):
        """The error-isolation guarantee, now across actions rather than across rules."""
        self.make_webhook("broken", conditions=[expression_row("data.name / 0")])
        working = self.make_webhook("working", conditions=[expression_row("true")])
        with self.assertLogs("nautobot.extras.conditions.gate", level="ERROR"):
            fired = self.fire(self.make_location(), description="x")
        self.assertEqual(fired, [str(working.pk)])

    def test_one_action_cannot_change_what_another_sees(self):
        """
        Each action is evaluated against its own copy of the payload.

        A condition is an expression, and `data.clear()` is one a user can write, so a shared payload would
        let one action silently stop every later one from matching.
        """
        self.make_webhook("a-vandal", conditions=[expression_row("data.clear()")])
        bystander = self.make_webhook("b-bystander", conditions=[expression_row("data.name == 'target'")])
        location = self.make_location("target")
        self.assertEqual(self.fire(location, description="x"), [str(bystander.pk)])

    def test_missing_key_is_falsy_not_fatal(self):
        self.make_webhook("missing", conditions=[expression_row("data.no_such_field")])
        with patch("nautobot.extras.webhooks.process_webhook.apply_async") as mock_enqueue:
            with web_request_context(self.user):
                location = Location(name="probe", status=self.statuses[0], location_type=self.location_type)
                location.save()
                location.description = "x"
                location.save()
        self.assertEqual(self.enqueued_webhook_pks(mock_enqueue), [])

    def test_transition_preset_end_to_end(self):
        webhook = self.make_webhook(
            "transition",
            conditions=[
                preset_row(
                    "field_transition", field="status", **{"from": self.statuses[0].name, "to": self.statuses[1].name}
                )
            ],
        )
        location = self.make_location()
        self.assertEqual(self.fire(location, status=self.statuses[1]), [str(webhook.pk)])

    def test_transition_preset_does_not_fire_for_a_different_transition(self):
        self.make_webhook(
            "transition",
            conditions=[
                preset_row(
                    "field_transition", field="status", **{"from": self.statuses[0].name, "to": self.statuses[1].name}
                )
            ],
        )
        location = self.make_location()
        self.assertEqual(self.fire(location, status=self.statuses[2]), [])


class TriggerFreeCostTestCase(ConditionalTriggerTestCase):
    """An installation that never uses this must not pay for it."""

    def test_a_save_with_nothing_scoped_costs_no_extra_queries(self):
        location = self.make_location()
        scoped_actions_for_model(Location, ObjectChangeActionChoices.ACTION_UPDATE)  # warm the cache
        with self.assertNumQueries(0):
            scoped_actions_for_model(Location, ObjectChangeActionChoices.ACTION_UPDATE)
        # And the save still works, with no action to fire.
        self.assertEqual(self.fire(location, description="x"), [])


class TriggerPreservationTestCase(ConditionalTriggerTestCase):
    """The scope and conditions must survive edits that never mention them.

    Each of these covers a way the two fields were silently lost. They are write-path tests rather than
    dispatch tests, so they assert on what is stored, not on what fires.
    """

    def test_partial_api_update_preserves_the_scope_filter(self):
        """A PATCH that omits `scope_filter` must leave it alone, not read absence as "clear it"."""
        from nautobot.extras.api.serializers import WebhookSerializer

        webhook = self.make_webhook(scope_filter={"name": ["Location 1"]})

        serializer = WebhookSerializer(webhook, data={"name": "renamed"}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        webhook.refresh_from_db()
        self.assertEqual(webhook.scope_filter, {"name": ["Location 1"]})

    def test_partial_api_update_preserves_the_conditions(self):
        conditions = [{"type": ConditionTypeChoices.TYPE_EXPRESSION, "source": "true", "negate": False}]
        webhook = self.make_webhook(conditions=conditions)

        from nautobot.extras.api.serializers import WebhookSerializer

        serializer = WebhookSerializer(webhook, data={"name": "renamed"}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        webhook.refresh_from_db()
        self.assertEqual(webhook.conditions, conditions)

    def test_api_update_can_still_clear_the_scope_filter_explicitly(self):
        """Sending an explicitly empty value must still clear it; only absence is ignored."""
        from nautobot.extras.api.serializers import WebhookSerializer

        webhook = self.make_webhook(scope_filter={"name": ["Location 1"]})

        serializer = WebhookSerializer(webhook, data={"scope_filter": {}}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        webhook.refresh_from_db()
        self.assertEqual(webhook.scope_filter, {})

    def test_bulk_edit_rejects_an_object_type_the_scope_cannot_apply(self):
        """Bulk edit adds object types after `full_clean()`, so it re-checks the filter itself.

        Mirrors `nautobot.core.jobs.bulk_actions.BulkEditObjects._update_objects`, which runs
        `full_clean()`, then `save()`, then `form.post_save(obj)` where the M2M changes are applied.
        """
        from django.core.exceptions import ValidationError

        from nautobot.extras.forms import WebhookBulkEditForm

        # `location_type` is a Location filter parameter. Status's filterset has no such parameter.
        webhook = self.make_webhook(scope_filter={"location_type": ["Campus"]})
        status_ct = ContentType.objects.get_for_model(Status)

        form = WebhookBulkEditForm(
            Webhook,
            {"pk": [str(webhook.pk)], "add_content_types": [status_ct.pk], "remove_content_types": []},
        )
        self.assertTrue(form.is_valid(), form.errors.as_text())

        webhook.full_clean()
        webhook.save()
        with self.assertRaises(ValidationError) as raised:
            form.post_save(webhook)

        self.assertIn("has no filter parameter(s)", str(raised.exception))

    def test_the_scoped_action_lookup_survives_a_cache_outage(self):
        """The cache is an optimisation here, not a dependency.

        Nautobot has other unguarded cache reads on the change-logging path, so this does not claim a
        save can always survive losing Redis. It pins the narrower promise that this lookup falls back to
        querying rather than raising, matching `invalidate_scoped_action_cache`, which already suppresses
        the same exception on the write side.
        """
        import redis.exceptions

        webhook = self.make_webhook(scope_filter={"name": ["Location 1"]})

        with patch("nautobot.extras.conditions.gate.cache") as mock_cache:
            mock_cache.get.side_effect = redis.exceptions.ConnectionError("redis is down")
            mock_cache.set.side_effect = redis.exceptions.ConnectionError("redis is down")
            found = scoped_actions_for_model(Location, ObjectChangeActionChoices.ACTION_UPDATE)

        self.assertEqual([str(item.pk) for item in found], [str(webhook.pk)])
