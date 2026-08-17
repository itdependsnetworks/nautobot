"""Generate realistic conditional triggers for manual testing and demonstration.

Each rule is one a network team plausibly wants, and together they cover every built-in condition preset
plus the cases presets cannot express. Everything is prefixed `DEMO-` so it is easy to flush and
re-create; pass `--flush` to wipe the demo objects first.

The webhooks created here point at example.com hostnames. Nothing is delivered; they exist so the rules
have an action to fire, which the model requires. Note that a receiver on `localhost` would be rejected:
loopback is blocked unconditionally by the webhook URL check and `WEBHOOK_ALLOWED_HOSTS` does not override
it, so a real receiver needs a private or public address.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from nautobot.dcim.models import Device, DeviceType, Interface, Location, LocationType, Manufacturer, Platform
from nautobot.extras.choices import ConditionTypeChoices, ObjectChangeActionChoices
from nautobot.extras.context_managers import change_logging, ORMChangeContext
from nautobot.extras.models import ObjectChange, Role, Status, Tag, Webhook
from nautobot.ipam.models import IPAddress, Namespace, Prefix

CREATE = ObjectChangeActionChoices.ACTION_CREATE
UPDATE = ObjectChangeActionChoices.ACTION_UPDATE
DELETE = ObjectChangeActionChoices.ACTION_DELETE


def preset(key, negate=False, **params):
    """A condition row using a built-in preset, optionally inverted."""
    return {
        "type": ConditionTypeChoices.TYPE_PRESET,
        "preset": key,
        "params": params,
        "negate": negate,
    }


def expression(source, negate=False):
    """A condition row using a raw Jinja2 expression, optionally inverted."""
    return {"type": ConditionTypeChoices.TYPE_EXPRESSION, "source": source, "negate": negate}


class Command(BaseCommand):
    help = "Generate realistic conditional triggers demonstrating condition presets and raw expressions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing demo conditional triggers and webhooks (DEMO- prefix) before creating fresh ones.",
        )
        parser.add_argument(
            "--no-changes",
            action="store_true",
            help="Create the rules only, skipping the change log entries used to exercise them.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self._flush()

        self.stdout.write(self.style.NOTICE("Creating conditional trigger demo data..."))

        # Endpoints, not objects: each demo trigger below is its own Webhook, and several of them deliver
        # to the same URL, which is what a chat or ticketing integration looks like in practice.
        self.urls = {
            "cmdb": "https://cmdb.example.com/hooks/nautobot",
            "monitoring": "https://monitoring.example.com/hooks/nautobot",
            "chatops": "https://chat.example.com/hooks/nautobot",
            "security": "https://siem.example.com/hooks/nautobot",
            "ipam-audit": "https://ipam-audit.example.com/hooks/nautobot",
        }

        self._ensure_objects()

        created = []
        created += self._preset_rules()
        created += self._expression_rules()
        created += self._combined_rules()

        if not options["no_changes"]:
            self._generate_changes()

        self.stdout.write(self.style.SUCCESS(f"Created {len(created)} demo webhooks with conditional triggers."))
        for webhook in created:
            kinds = {row.get("type") for row in webhook.conditions} or {"none"}
            events = [
                name
                for name, flag in (
                    ("create", webhook.type_create),
                    ("update", webhook.type_update),
                    ("delete", webhook.type_delete),
                )
                if flag
            ]
            self.stdout.write(f"  {webhook.name}")
            self.stdout.write(
                f"      watches {', '.join(events)} on "
                f"{', '.join(str(ct) for ct in webhook.content_types.all())}"
                f" | {len(webhook.conditions)} condition(s) [{', '.join(sorted(kinds))}]"
                f" | scope {webhook.scope_filter or '{} (all)'}"
            )
        self.stdout.write("")
        if options["no_changes"]:
            self.stdout.write("No change log entries created (--no-changes).")
        else:
            count = ObjectChange.objects.filter(change_context_detail__startswith="DEMO").count()
            self.stdout.write(self.style.SUCCESS(f"Created {count} change log entries to test against."))
            self.stdout.write("")
            self.stdout.write("On a rule's Test tab, pick a change log entry whose detail starts `DEMO+` to")
            self.stdout.write("see it fire, or `DEMO-` to see it not fire. The detail names the rule.")

    #
    # Rules built from presets
    #

    def _preset_rules(self):
        """One rule per built-in preset, each a plausible reason to want it."""
        return [
            # field_transition: the canonical case, a device entering service.
            self._rule(
                "DEMO-Device brought into service",
                Device,
                [UPDATE],
                conditions=[preset("field_transition", field="status", **{"from": "Staged", "to": "Active"})],
                webhooks=["cmdb", "monitoring"],
                scope_filter={},
            ),
            # field_transition, narrowed by scope: only one site's kit is onboarded this way.
            self._rule(
                "DEMO-Campus-01 device decommissioned",
                Device,
                [UPDATE],
                conditions=[preset("field_transition", field="status", **{"from": "Active", "to": "Decommissioning"})],
                webhooks=["cmdb"],
                scope_filter=self._first_location_filter(),
            ),
            # field_changed: any change to the field, whatever it became.
            self._rule(
                "DEMO-Interface description changed",
                Interface,
                [UPDATE],
                conditions=[preset("field_changed", field="description")],
                webhooks=["cmdb"],
            ),
            # field_compare with "=": the state after the change, regardless of what it was before.
            self._rule(
                "DEMO-Device is failed",
                Device,
                [CREATE, UPDATE],
                conditions=[preset("field_compare", field="status", operator="=", value="Failed")],
                webhooks=["monitoring", "chatops"],
            ),
            # field_compare with a non-equality operator, which needed a raw expression before.
            self._rule(
                "DEMO-Device name starts with ams01",
                Device,
                [CREATE, UPDATE],
                conditions=[preset("field_compare", field="name", operator="startswith", value="ams01")],
                webhooks=["cmdb"],
            ),
            # The same comparison inverted by the row's `not`, rather than by a second preset.
            self._rule(
                "DEMO-Device not in the active states",
                Device,
                [UPDATE],
                conditions=[preset("field_compare", field="status", operator="in", value="Active,Staged", negate=True)],
                webhooks=["monitoring"],
            ),
            # A dotted field, reaching inside the related object instead of relying on its display value.
            self._rule(
                "DEMO-Device platform is Arista EOS",
                Device,
                [CREATE, UPDATE],
                conditions=[preset("field_compare", field="platform.name", operator="contains", value="EOS")],
                webhooks=["cmdb"],
            ),
            # An ordering comparison, which only makes sense on a numeric field.
            self._rule(
                "DEMO-Interface MTU above jumbo",
                Interface,
                [CREATE, UPDATE],
                conditions=[preset("field_compare", field="mtu", operator="gt", value="9000")],
                webhooks=["monitoring"],
            ),
            # `endswith`, on a name that encodes its role in a suffix.
            self._rule(
                "DEMO-Interface name ends with -mgmt",
                Interface,
                [CREATE, UPDATE],
                conditions=[preset("field_compare", field="name", operator="endswith", value="-mgmt")],
                webhooks=["cmdb"],
            ),
            # user_is: watch one privileged account specifically.
            self._rule(
                "DEMO-Prefix changed by admin",
                Prefix,
                [UPDATE, DELETE],
                conditions=[preset("user_is", username="admin")],
                webhooks=["security"],
            ),
            # user_is_not: the usual reason, ignoring your own automation's churn.
            self._rule(
                "DEMO-IP address changed by a human",
                IPAddress,
                [CREATE, UPDATE, DELETE],
                conditions=[preset("user_is_not", username="svc-automation")],
                webhooks=["ipam-audit"],
            ),
        ]

    #
    # Rules that need a raw expression
    #

    def _expression_rules(self):
        """Cases no preset covers, which is the reason the expression tier exists."""
        return [
            # OR across values. A preset compares against one value; this accepts several.
            self._rule(
                "DEMO-Device entered any bad state",
                Device,
                [UPDATE],
                conditions=[expression("data.status.name in ['Failed', 'Offline', 'Inventory']")],
                webhooks=["monitoring", "chatops"],
            ),
            # Reads the previous value, which only prechange holds.
            self._rule(
                "DEMO-Active device was deleted",
                Device,
                [DELETE],
                conditions=[expression("snapshots.prechange.status | event_value == 'Active'")],
                webhooks=["chatops", "security"],
            ),
            # Asks a question about a list; presets compare scalars.
            self._rule(
                "DEMO-Critical-tagged device changed",
                Device,
                [UPDATE, DELETE],
                conditions=[
                    expression("'critical' in (data.tags | map(attribute='name') | list)"),
                ],
                webhooks=["chatops"],
            ),
            # Combines "this field changed" with "and its new value is set", which no single preset does.
            self._rule(
                "DEMO-Device got a primary IP",
                Device,
                [UPDATE],
                conditions=[
                    expression(
                        "'primary_ip4' in (snapshots.differences.added or {})\n    and data.primary_ip4 is not none"
                    )
                ],
                webhooks=["cmdb", "ipam-audit"],
            ),
            # Branches on the event kind, so one rule covers create and delete differently.
            self._rule(
                "DEMO-Container prefix added or removed",
                Prefix,
                [CREATE, DELETE],
                conditions=[
                    expression(
                        "(data.type | event_value == 'container') if event == 'created'\n"
                        "    else (snapshots.prechange.type | event_value == 'container')"
                    )
                ],
                webhooks=["ipam-audit"],
            ),
            # A substring match rather than an equality check.
            self._rule(
                "DEMO-Uplink interface changed",
                Interface,
                [UPDATE],
                conditions=[expression("'uplink' in (data.name | lower)")],
                webhooks=["monitoring"],
            ),
        ]

    #
    # Rules mixing both, and the scope-only case
    #

    def _combined_rules(self):
        return [
            # Several rows are AND-ed, so each stays short and dry-run reports them separately.
            # This is the preferred shape over one long expression.
            self._rule(
                "DEMO-Human brought a critical device into service",
                Device,
                [UPDATE],
                conditions=[
                    preset("field_transition", field="status", **{"from": "Staged", "to": "Active"}),
                    preset("user_is_not", username="svc-automation"),
                    expression("'critical' in (data.tags | map(attribute='name') | list)"),
                ],
                webhooks=["cmdb", "chatops"],
            ),
            # No conditions at all: scope alone decides. Legitimate, and the simplest rule to reason about.
            self._rule(
                "DEMO-Any change at the first location",
                Device,
                [CREATE, UPDATE, DELETE],
                conditions=[],
                webhooks=["cmdb"],
                scope_filter=self._first_location_filter(),
            ),
            # Disabled on purpose, so the list view shows the state and it never fires.
            self._rule(
                "DEMO-Disabled example",
                Device,
                [UPDATE],
                conditions=[expression("true")],
                webhooks=["chatops"],
                enabled=False,
            ),
        ]

    #
    # Demo objects the changes act on
    #

    def _ensure_objects(self):
        """
        Create the objects the demo changes are made against.

        Dedicated DEMO- objects rather than existing ones, so running this never rewrites real data. Two
        locations exist because one rule is scoped to the first, which is what makes an out-of-scope
        negative case possible.
        """
        User = get_user_model()
        self.admin, _ = User.objects.get_or_create(username="admin", defaults={"is_superuser": True})
        self.robot, _ = User.objects.get_or_create(username="svc-automation")

        self.critical_tag, _ = Tag.objects.get_or_create(name="critical", defaults={"color": "f44336"})
        self.critical_tag.content_types.add(ContentType.objects.get_for_model(Device))

        campus = LocationType.objects.filter(name="Campus").first() or LocationType.objects.first()
        location_status = Status.objects.get_for_model(Location).first()
        self.location_in_scope, _ = Location.objects.get_or_create(
            name="DEMO-Campus-01", defaults={"location_type": campus, "status": location_status}
        )
        self.location_out_of_scope, _ = Location.objects.get_or_create(
            name="DEMO-Campus-02", defaults={"location_type": campus, "status": location_status}
        )

        manufacturer, _ = Manufacturer.objects.get_or_create(name="DEMO-Manufacturer")
        self.device_type, _ = DeviceType.objects.get_or_create(
            model="DEMO-Switch", defaults={"manufacturer": manufacturer}
        )
        self.device_role = Role.objects.get_for_model(Device).first()
        self.device_statuses = {
            name: status for name, status in Status.objects.get_for_model(Device).values_list("name", "pk")
        }
        self.status = {s.name: s for s in Status.objects.get_for_model(Device)}
        self.interface_status = Status.objects.get_for_model(Interface).first()
        self.prefix_status = Status.objects.get_for_model(Prefix).first()
        self.ip_status = Status.objects.get_for_model(IPAddress).first()
        self.namespace = Namespace.objects.filter(name="Global").first() or Namespace.objects.first()

    def _device(self, name, location, status="Active", tags=()):
        """
        Create or reset a demo device, logging the creation as a change.

        The creation is logged deliberately. A replayed change only has a pre-change snapshot if an earlier
        ObjectChange exists for that object, because `get_snapshots` derives it from the previous change
        and not from the database. Create a device outside the change log and its first update replays with no
        pre-change data, so a transition condition cannot see where the field came from and every field
        looks newly added.
        """
        device = Device.objects.filter(name=name).first()
        if device is None:
            with self._changes(f"DEMO setup: create {name}"):
                device = Device.objects.create(
                    name=name,
                    location=location,
                    device_type=self.device_type,
                    role=self.device_role,
                    status=self.status[status],
                )
        else:
            with self._changes(f"DEMO setup: reset {name}"):
                device.location = location
                device.status = self.status[status]
                device.save()
        device.tags.set(tags)
        return device

    #
    # Change log entries
    #

    def _changes(self, label, user=None):
        """
        Record changes to the change log without dispatching anything.

        `change_logging` rather than `web_request_context`: the demo webhooks point at example.com, so
        firing rules for real would only queue deliveries that fail. The ObjectChange rows are what the
        Test tab replays, and those are all this needs.

        The label lands in the change log's Change Context Detail column, so a tester can see which
        scenario a row belongs to and whether it is meant to fire.
        """
        return change_logging(ORMChangeContext(user=user or self.admin, context_detail=label))

    def _generate_changes(self):
        """
        Produce a firing and a non-firing change for each rule.

        Each scenario runs in its own savepoint and its own error boundary. A database can carry validation
        rules or required fields this command knows nothing about, and one model it cannot write is not a
        reason to abandon the rest.
        """
        self.stdout.write(self.style.NOTICE("Creating change log entries..."))
        skipped = []
        for name in (
            "transition",
            "scoped_transition",
            "field_changed",
            "field_comparison",
            "operator_comparisons",
            "actor",
            "delete_prechange",
            "tagged",
            "primary_ip",
            "prefix_type",
            "name_substring",
            "scope_only",
        ):
            method = getattr(self, f"_scenario_{name}")
            try:
                with transaction.atomic():
                    method()
            except Exception as exc:  # pylint: disable=broad-except
                skipped.append(name)
                self.stdout.write(self.style.WARNING(f"  skipped {name}: {type(exc).__name__}: {exc}"))
                if isinstance(exc, AttributeError):
                    self.stdout.write(
                        "      An AttributeError naming a field that does not exist usually means a stale "
                        "data validation rule targets that model. Check Extensibility > data validation."
                    )
        if skipped:
            self.stdout.write(self.style.WARNING(f"  {len(skipped)} scenario(s) skipped; the rest were created."))

    def _scenario_transition(self):
        """field_transition: Staged -> Active fires, Staged -> Failed does not."""
        device = self._device("DEMO-dev-transition", self.location_in_scope, status="Staged")
        with self._changes("DEMO+ Device brought into service"):
            device.status = self.status["Active"]
            device.save()

        other = self._device("DEMO-dev-wrong-transition", self.location_in_scope, status="Staged")
        with self._changes("DEMO- Device brought into service (Staged to Failed)"):
            other.status = self.status["Failed"]
            other.save()

    def _scenario_scoped_transition(self):
        """The same transition in and out of the rule's scope."""
        inside = self._device("DEMO-dev-decomm-in-scope", self.location_in_scope, status="Active")
        with self._changes("DEMO+ Campus-01 device decommissioned"):
            inside.status = self.status["Decommissioning"]
            inside.save()

        outside = self._device("DEMO-dev-decomm-out-of-scope", self.location_out_of_scope, status="Active")
        with self._changes("DEMO- Campus-01 device decommissioned (wrong location)"):
            outside.status = self.status["Decommissioning"]
            outside.save()

    def _scenario_field_changed(self):
        """field_changed on `description`: changing something else must not match."""
        device = self._device("DEMO-dev-interfaces", self.location_in_scope)
        uplink = self._interface(device, "Uplink-1")
        access = self._interface(device, "Access-1")
        with self._changes("DEMO+ Interface description changed"):
            uplink.description = "Uplink to spine"
            uplink.save()
        with self._changes("DEMO- Interface description changed (label only)"):
            access.label = "port-1"
            access.save()

    def _scenario_field_comparison(self):
        """A `field_compare` equality comparison, which also exercises the "any bad state" rule."""
        failing = self._device("DEMO-dev-failed", self.location_in_scope, status="Active")
        with self._changes("DEMO+ Device is failed / entered a bad state"):
            failing.status = self.status["Failed"]
            failing.save()

        healthy = self._device("DEMO-dev-healthy", self.location_in_scope, status="Staged")
        with self._changes("DEMO- Device is failed / entered a bad state (now Active)"):
            healthy.status = self.status["Active"]
            healthy.save()

    def _scenario_operator_comparisons(self):
        """One firing and one non-firing change for each comparison operator that has its own rule."""
        # `in`, inverted: a device leaving the active states fires; one entering them does not.
        leaving = self._device("DEMO-dev-not-active", self.location_in_scope, status="Active")
        with self._changes("DEMO+ Device not in the active states"):
            leaving.status = self.status["Failed"]
            leaving.save()
        entering = self._device("DEMO-dev-still-active", self.location_in_scope, status="Staged")
        with self._changes("DEMO- Device not in the active states (became Active)"):
            entering.status = self.status["Active"]
            entering.save()

        # `contains` on a dotted field. Assigning the platform is the change, so the rule sees it set.
        arista = self._platform("DEMO-Arista EOS")
        junos = self._platform("DEMO-Juniper Junos")
        matched = self._device("DEMO-dev-platform-eos", self.location_in_scope)
        with self._changes("DEMO+ Device platform is Arista EOS"):
            matched.platform = arista
            matched.save()
        unmatched = self._device("DEMO-dev-platform-junos", self.location_in_scope)
        with self._changes("DEMO- Device platform is Arista EOS (Junos)"):
            unmatched.platform = junos
            unmatched.save()

        # `gt` and `endswith`, both on interfaces of one device.
        device = self._device("DEMO-dev-operators", self.location_in_scope)
        jumbo = self._interface(device, "Ethernet1")
        with self._changes("DEMO+ Interface MTU above jumbo"):
            jumbo.mtu = 9216
            jumbo.save()
        standard = self._interface(device, "Ethernet2")
        with self._changes("DEMO- Interface MTU above jumbo (1500)"):
            standard.mtu = 1500
            standard.save()

        mgmt = self._interface(device, "vlan99-mgmt")
        data = self._interface(device, "vlan99-data")
        with self._changes("DEMO+ Interface name ends with -mgmt"):
            mgmt.description = "Out-of-band management"
            mgmt.save()
        with self._changes("DEMO- Interface name ends with -mgmt (no suffix)"):
            data.description = "User data"
            data.save()

    def _scenario_actor(self):
        """user_is / user_is_not: the same edit made by two different users."""
        device = self._device("DEMO-dev-actor", self.location_in_scope)
        with self._changes("DEMO+ Changed by admin", user=self.admin):
            device.description = "Edited by admin"
            device.save()
        with self._changes("DEMO- Changed by admin (automation did it)", user=self.robot):
            device.description = "Edited by automation"
            device.save()

    def _scenario_delete_prechange(self):
        """Reading prechange on a delete, where postchange is null."""
        active = self._device("DEMO-dev-delete-active", self.location_in_scope, status="Active")
        with self._changes("DEMO+ Active device was deleted"):
            active.delete()

        staged = self._device("DEMO-dev-delete-staged", self.location_in_scope, status="Staged")
        with self._changes("DEMO- Active device was deleted (was Staged)"):
            staged.delete()

    def _scenario_tagged(self):
        """Tag membership, and the three-row rule that also checks the actor and the transition."""
        tagged = self._device("DEMO-dev-critical", self.location_in_scope, status="Staged", tags=[self.critical_tag])
        with self._changes("DEMO+ Critical-tagged device changed"):
            tagged.description = "Touched"
            tagged.save()
        with self._changes("DEMO+ Human brought a critical device into service", user=self.admin):
            tagged.status = self.status["Active"]
            tagged.save()

        robot_owned = self._device(
            "DEMO-dev-critical-robot", self.location_in_scope, status="Staged", tags=[self.critical_tag]
        )
        with self._changes("DEMO- Human brought a critical device into service (automation)", user=self.robot):
            robot_owned.status = self.status["Active"]
            robot_owned.save()

        plain = self._device("DEMO-dev-untagged", self.location_in_scope)
        with self._changes("DEMO- Critical-tagged device changed (no tag)"):
            plain.description = "Touched"
            plain.save()

    def _scenario_primary_ip(self):
        """A field that both changed and ended up set, which no single preset expresses."""
        device = self._device("DEMO-dev-primary-ip", self.location_in_scope)
        interface = self._interface(device, "mgmt0")
        self._prefix("10.222.0.0/16")  # an IPAddress needs a containing prefix
        address = self._ip_address("10.222.0.20/32")
        interface.ip_addresses.add(address)
        with self._changes("DEMO+ Device got a primary IP"):
            device.primary_ip4 = address
            device.save()
        with self._changes("DEMO- Device got a primary IP (description only)"):
            device.description = "Touched"
            device.save()

    def _scenario_prefix_type(self):
        """Branching on the event kind: a container prefix created, versus a network one."""
        with self._changes("DEMO+ Container prefix added"):
            self._prefix("10.223.0.0/16", prefix_type="container")
        with self._changes("DEMO- Container prefix added (network prefix)"):
            self._prefix("10.224.0.0/16", prefix_type="network")

    def _scenario_name_substring(self):
        """A substring match on a name rather than an equality check."""
        device = self._device("DEMO-dev-interfaces", self.location_in_scope)
        uplink = self._interface(device, "Uplink-1")
        access = self._interface(device, "Access-1")
        with self._changes("DEMO+ Uplink interface changed"):
            uplink.label = "uplink-label"
            uplink.save()
        with self._changes("DEMO- Uplink interface changed (access port)"):
            access.description = "Access port"
            access.save()

    def _scenario_scope_only(self):
        """A rule with no conditions, where scope alone decides."""
        inside = self._device("DEMO-dev-scope-in", self.location_in_scope)
        with self._changes("DEMO+ Any change at the first location"):
            inside.description = "Touched in scope"
            inside.save()

        outside = self._device("DEMO-dev-scope-out", self.location_out_of_scope)
        with self._changes("DEMO- Any change at the first location (other site)"):
            outside.description = "Touched out of scope"
            outside.save()

    #
    # Helpers
    #

    def _rule(self, name, model, event_types, *, conditions, webhooks, scope_filter=None, enabled=True):
        """
        Create one demo Webhook carrying its own scope and conditions.

        `webhooks` names the endpoint(s) this trigger delivers to. Several triggers can share an endpoint
        URL, which is the shape a chat or ticketing integration has, but each is now its own Webhook row,
        because the scope and conditions live on the row.
        """
        webhook = Webhook(
            name=name,
            enabled=enabled,
            payload_url=self.urls[webhooks[0]],
            type_create=ObjectChangeActionChoices.ACTION_CREATE in event_types,
            type_update=ObjectChangeActionChoices.ACTION_UPDATE in event_types,
            type_delete=ObjectChangeActionChoices.ACTION_DELETE in event_types,
            conditions=conditions,
            scope_filter=scope_filter or {},
        )
        webhook.save()
        webhook.content_types.set([ContentType.objects.get_for_model(model)])
        # Validate only now: content types are many-to-many, so `clean()` cannot see them before the
        # first save, and the scope filter is checked against them.
        webhook.validated_save()
        return webhook

    def _interface(self, device, name):
        """Create or return a demo interface, logging the creation for the same reason as `_device`."""
        interface = Interface.objects.filter(device=device, name=name).first()
        if interface is None:
            with self._changes(f"DEMO setup: create {device.name} {name}"):
                interface = Interface.objects.create(
                    device=device, name=name, type="1000base-t", status=self.interface_status
                )
        else:
            # Reset, and log it. An object left over from an earlier run has no create change of its own
            # once the demo change log is flushed, and a change with no predecessor replays with a null
            # pre-change snapshot, which makes every field look newly added.
            with self._changes(f"DEMO setup: reset {device.name} {name}"):
                interface.description = ""
                interface.label = ""
                interface.mtu = None
                interface.save()
        return interface

    def _platform(self, name):
        platform, _ = Platform.objects.get_or_create(name=name)
        return platform

    def _prefix(self, prefix, prefix_type="network"):
        obj, _ = Prefix.objects.get_or_create(
            prefix=prefix,
            namespace=self.namespace,
            defaults={"status": self.prefix_status, "type": prefix_type},
        )
        return obj

    def _ip_address(self, address):
        obj, _ = IPAddress.objects.get_or_create(
            address=address, namespace=self.namespace, defaults={"status": self.ip_status}
        )
        return obj

    def _first_location_filter(self):
        """Scope filter naming the demo in-scope location, so the out-of-scope negative case is meaningful."""
        return {"location": [str(self.location_in_scope.pk)]}

    def _flush(self):
        self.stdout.write(self.style.WARNING("Flushing existing conditional trigger demo data..."))
        webhooks = Webhook.objects.filter(name__startswith="DEMO-")
        # Change log entries too. Without this, repeated runs leave several entries sharing a label, and a
        # tester picking one by name in the Test tab gets whichever happens to come first, possibly one
        # generated before a fix, which then reports the wrong verdict.
        changes = ObjectChange.objects.filter(change_context_detail__startswith="DEMO")
        self.stdout.write(f"  {webhooks.count()} webhook(s), {changes.count()} change log entry(ies)")
        webhooks.delete()
        changes.delete()

        # The objects too. Leaving them behind means their creation is never re-logged, so the first
        # change of the next run has no predecessor to diff against.
        Device.objects.filter(name__startswith="DEMO-").delete()
        Platform.objects.filter(name__startswith="DEMO-").delete()
        Prefix.objects.filter(description__startswith="DEMO").delete()
        DeviceType.objects.filter(model__startswith="DEMO-").delete()
        Manufacturer.objects.filter(name__startswith="DEMO-").delete()
        Location.objects.filter(name__startswith="DEMO-").delete()
