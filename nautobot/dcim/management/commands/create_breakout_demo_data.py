"""Generate demo data showcasing breakout cables and all cable termination types."""

from django.core.management.base import BaseCommand
from django.db import transaction

from nautobot.circuits.models import Circuit, CircuitTermination, CircuitType, Provider
from nautobot.dcim.choices import (
    CableTypeChoices,
    InterfaceTypeChoices,
    PortTypeChoices,
    PowerOutletFeedLegChoices,
)
from nautobot.dcim.models import (
    BreakoutTemplate,
    Cable,
    CableTerminationEndpoint,
    ConsolePort,
    ConsoleServerPort,
    Device,
    DeviceType,
    FrontPort,
    Interface,
    Location,
    LocationType,
    Manufacturer,
    PowerFeed,
    PowerOutlet,
    PowerPanel,
    PowerPort,
    RearPort,
)
from nautobot.extras.models import Role, Status


class Command(BaseCommand):
    help = "Generate demo data showcasing breakout cables and all cable termination types."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing demo data (objects with 'DEMO-' prefix) before creating.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self._flush()

        self.stdout.write(self.style.NOTICE("Creating breakout cable demo data..."))

        # Statuses and Roles
        self.status_active = Status.objects.get_for_model(Device).get(name="Active")
        self.status_connected = Status.objects.get_for_model(Cable).get(name="Connected")
        self.status_planned = Status.objects.get_for_model(Cable).get(name="Planned")
        self.intf_status = Status.objects.get_for_model(Interface).first()
        self.device_role = Role.objects.get_for_model(Device).first()

        # Location
        loc_type, _ = LocationType.objects.get_or_create(name="DEMO Data Center")
        self.location, _ = Location.objects.get_or_create(
            name="DEMO-DC1", location_type=loc_type, defaults={"status": self.status_active}
        )

        # Manufacturer + DeviceType
        mfg, _ = Manufacturer.objects.get_or_create(name="DEMO-Vendor")
        self.dt_spine, _ = DeviceType.objects.get_or_create(model="DEMO-Spine-Switch", manufacturer=mfg)
        self.dt_leaf, _ = DeviceType.objects.get_or_create(model="DEMO-Leaf-Switch", manufacturer=mfg)
        self.dt_server, _ = DeviceType.objects.get_or_create(model="DEMO-Server", manufacturer=mfg)
        self.dt_patch, _ = DeviceType.objects.get_or_create(model="DEMO-Patch-Panel", manufacturer=mfg)
        self.dt_console, _ = DeviceType.objects.get_or_create(model="DEMO-Console-Server", manufacturer=mfg)
        self.dt_pdu, _ = DeviceType.objects.get_or_create(model="DEMO-PDU", manufacturer=mfg)

        # Devices
        self.spine1 = self._device("DEMO-SPINE-01", self.dt_spine)
        self.leaf1 = self._device("DEMO-LEAF-01", self.dt_leaf)
        self.leaf2 = self._device("DEMO-LEAF-02", self.dt_leaf)
        self.leaf3 = self._device("DEMO-LEAF-03", self.dt_leaf)
        self.leaf4 = self._device("DEMO-LEAF-04", self.dt_leaf)
        self.server1 = self._device("DEMO-SRV-01", self.dt_server)
        self.server2 = self._device("DEMO-SRV-02", self.dt_server)
        self.patch1 = self._device("DEMO-PATCH-01", self.dt_patch)
        self.patch2 = self._device("DEMO-PATCH-02", self.dt_patch)
        self.console_srv = self._device("DEMO-CONSOLE-01", self.dt_console)
        self.pdu = self._device("DEMO-PDU-01", self.dt_pdu)

        # Pre-create plenty of spare interfaces on each device for testing
        self._create_spare_interfaces()

        # Breakout Templates
        self._create_breakout_templates()

        # Create all cable types
        self._create_breakout_cables()
        self._create_standard_cables()
        self._create_patch_panel_cables()
        self._create_circuit_cable()
        self._create_power_cables()
        self._create_console_cables()
        self._create_complex_path()

        # Sync cable peer caches and rebuild cable paths for all demo cables
        self._sync_all_caches()

        self.stdout.write(self.style.SUCCESS("Demo data created successfully!"))
        self.stdout.write(f"  Location: {self.location}")
        self.stdout.write(f"  Devices: {Device.objects.filter(name__startswith='DEMO-').count()}")
        self.stdout.write(f"  Breakout Templates: {BreakoutTemplate.objects.filter(name__startswith='DEMO').count()}")
        self.stdout.write(f"  Cables: {Cable.objects.filter(label__startswith='DEMO').count()}")

    def _sync_all_caches(self):
        """Sync cable peer caches and rebuild CablePaths for all demo cables."""
        from nautobot.dcim.models import CablePath, CableTerminationEndpoint
        from nautobot.dcim.models.device_components import PathEndpoint
        from nautobot.dcim.utils import get_opposite_lane_termination

        for cable in Cable.objects.filter(label__startswith="DEMO"):
            endpoints = list(CableTerminationEndpoint.objects.filter(cable=cable))
            a_endpoints = [ep for ep in endpoints if ep.cable_end == "A"]
            b_endpoints = [ep for ep in endpoints if ep.cable_end == "B"]

            for endpoint in endpoints:
                termination = endpoint.termination
                if termination is None:
                    continue

                # Find peer
                if endpoint.connector is not None and endpoint.position is not None:
                    peer = get_opposite_lane_termination(cable, endpoint.cable_end, endpoint.connector, endpoint.position)
                else:
                    if endpoint.cable_end == "A":
                        peer = b_endpoints[0].termination if b_endpoints else None
                    else:
                        peer = a_endpoints[0].termination if a_endpoints else None

                # Update caches
                termination.cable = cable
                termination._cable_peer = peer
                termination.save()

            # Rebuild CablePaths (uses create_cablepath which handles per-lane paths)
            from django.contrib.contenttypes.models import ContentType
            from nautobot.dcim.signals import create_cablepath

            seen_origins = set()
            for endpoint in endpoints:
                termination = endpoint.termination
                if termination and isinstance(termination, PathEndpoint) and termination.pk not in seen_origins:
                    seen_origins.add(termination.pk)
                    origin_ct = ContentType.objects.get_for_model(termination)
                    CablePath.objects.filter(origin_type=origin_ct, origin_id=termination.pk).delete()
                    create_cablepath(termination, rebuild=False)

        self.stdout.write("  Synced cable peer caches and rebuilt CablePaths")

    def _flush(self):
        self.stdout.write(self.style.WARNING("Flushing existing demo data..."))
        Cable.objects.filter(label__startswith="DEMO").delete()
        BreakoutTemplate.objects.filter(name__startswith="DEMO").delete()
        CircuitTermination.objects.filter(circuit__cid__startswith="DEMO-").delete()
        Circuit.objects.filter(cid__startswith="DEMO-").delete()
        CircuitType.objects.filter(name__startswith="DEMO-").delete()
        Provider.objects.filter(name__startswith="DEMO-").delete()
        PowerFeed.objects.filter(name__startswith="DEMO-").delete()
        PowerPanel.objects.filter(name__startswith="DEMO-").delete()
        Device.objects.filter(name__startswith="DEMO-").delete()
        DeviceType.objects.filter(model__startswith="DEMO-").delete()
        Manufacturer.objects.filter(name="DEMO-Vendor").delete()
        Location.objects.filter(name="DEMO-DC1").delete()
        LocationType.objects.filter(name="DEMO Data Center").delete()

    def _device(self, name, device_type):
        dev, _ = Device.objects.get_or_create(
            name=name,
            defaults={
                "device_type": device_type,
                "role": self.device_role,
                "status": self.status_active,
                "location": self.location,
            },
        )
        return dev

    def _interface(self, device, name, intf_type=InterfaceTypeChoices.TYPE_100GE_QSFP28):
        intf, _ = Interface.objects.get_or_create(
            device=device,
            name=name,
            defaults={"type": intf_type, "status": self.intf_status},
        )
        return intf

    def _create_spare_interfaces(self):
        """Create plenty of unconnected interfaces on each device for testing."""
        network_devices = [self.spine1, self.leaf1, self.leaf2, self.leaf3, self.leaf4]
        server_devices = [self.server1, self.server2]

        for dev in network_devices:
            for slot in range(20, 24):
                for port in range(1, 9):
                    self._interface(dev, f"Ethernet{slot}/{port}", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS)

        for dev in server_devices:
            for i in range(20, 36):
                self._interface(dev, f"eth{i}", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS)

        # Also create spare front/rear ports on the patch panel
        for i in range(10, 18):
            rp = self._rear_port(self.patch1, f"Rear-Spare-{i}")
            self._front_port(self.patch1, f"Front-Spare-{i}", rp)

        self.stdout.write("  Created spare interfaces and ports for testing")

    def _rear_port(self, device, name, positions=1, port_type=PortTypeChoices.TYPE_LC):
        rp, _ = RearPort.objects.get_or_create(
            device=device,
            name=name,
            defaults={"positions": positions, "type": port_type},
        )
        return rp

    def _front_port(self, device, name, rear_port, rear_port_position=1, port_type=PortTypeChoices.TYPE_LC):
        fp, _ = FrontPort.objects.get_or_create(
            device=device,
            name=name,
            defaults={"rear_port": rear_port, "rear_port_position": rear_port_position, "type": port_type},
        )
        return fp

    def _cable(self, term_a, term_b, label, status=None, cable_type="", breakout_template=None):
        if status is None:
            status = self.status_connected
        cable = Cable(
            termination_a=term_a,
            termination_b=term_b,
            label=label,
            status=status,
            type=cable_type,
        )
        if breakout_template:
            cable.breakout_template = breakout_template
        cable.validated_save()

        # For breakout cables, set connector/position on the lane-1 CableTermination rows
        # created by the signal handler (they default to NULL)
        if breakout_template and breakout_template.mapping:
            entry = breakout_template.mapping[0]
            for ct_row in CableTerminationEndpoint.objects.filter(cable=cable, connector__isnull=True):
                if ct_row.cable_end == "A":
                    ct_row.connector = entry["a_connector"]
                    ct_row.position = entry["a_position"]
                else:
                    ct_row.connector = entry["b_connector"]
                    ct_row.position = entry["b_position"]
                ct_row.save()

        return cable

    def _create_breakout_templates(self):
        """Create various breakout template configurations."""

        # 1x400G → 4x100G (QSFP-DD to SFP28) — most common data center breakout
        self.tmpl_1x4, _ = BreakoutTemplate.objects.get_or_create(
            name="DEMO-QSFP-DD 1x400G → 4x100G",
            defaults={
                "a_connectors": 1,
                "a_positions": 4,
                "b_connectors": 4,
                "b_positions": 1,
                "mapping": [
                    {"a_connector": 1, "a_position": i, "b_connector": i, "b_position": 1} for i in range(1, 5)
                ],
                "strands_per_lane": 1,
                "description": "400G QSFP-DD broken out to 4x 100G SFP28 lanes (DAC/AOC)",
            },
        )

        # 1x40G → 4x10G (QSFP+ to SFP+)
        self.tmpl_40g_4x10, _ = BreakoutTemplate.objects.get_or_create(
            name="DEMO-QSFP+ 1x40G → 4x10G",
            defaults={
                "a_connectors": 1,
                "a_positions": 4,
                "b_connectors": 4,
                "b_positions": 1,
                "mapping": [
                    {"a_connector": 1, "a_position": i, "b_connector": i, "b_position": 1} for i in range(1, 5)
                ],
                "strands_per_lane": 1,
                "description": "40G QSFP+ broken out to 4x 10G SFP+ (server NICs)",
            },
        )

        # MPO-12 Duplex Fanout (1 MPO trunk → 6 LC duplex)
        self.tmpl_mpo12, _ = BreakoutTemplate.objects.get_or_create(
            name="DEMO-MPO-12 Duplex Fanout",
            defaults={
                "a_connectors": 1,
                "a_positions": 6,
                "b_connectors": 6,
                "b_positions": 1,
                "mapping": [
                    {"a_connector": 1, "a_position": i, "b_connector": i, "b_position": 1} for i in range(1, 7)
                ],
                "strands_per_lane": 2,
                "polarity_method": "straight-through",
                "description": "MPO-12 trunk fanning out to 6 LC duplex connections",
            },
        )

        # 2x4 Polarity Shuffle (2 MPO-8 connectors shuffled to 2 MPO-8)
        self.tmpl_shuffle, _ = BreakoutTemplate.objects.get_or_create(
            name="DEMO-2x4 Polarity Shuffle",
            defaults={
                "a_connectors": 2,
                "a_positions": 4,
                "b_connectors": 2,
                "b_positions": 4,
                "is_shuffle": True,
                "mapping": [
                    {"a_connector": 1, "a_position": 1, "b_connector": 1, "b_position": 1},
                    {"a_connector": 1, "a_position": 2, "b_connector": 1, "b_position": 2},
                    {"a_connector": 1, "a_position": 3, "b_connector": 2, "b_position": 1},
                    {"a_connector": 1, "a_position": 4, "b_connector": 2, "b_position": 2},
                    {"a_connector": 2, "a_position": 1, "b_connector": 1, "b_position": 3},
                    {"a_connector": 2, "a_position": 2, "b_connector": 1, "b_position": 4},
                    {"a_connector": 2, "a_position": 3, "b_connector": 2, "b_position": 3},
                    {"a_connector": 2, "a_position": 4, "b_connector": 2, "b_position": 4},
                ],
                "strands_per_lane": 2,
                "polarity_method": "pair-reversed",
                "description": "2x4 trunk with polarity-shuffled lanes between connectors",
            },
        )

        # 1x2 simple breakout (100G → 2x50G)
        self.tmpl_1x2, _ = BreakoutTemplate.objects.get_or_create(
            name="DEMO-1x100G → 2x50G",
            defaults={
                "a_connectors": 1,
                "a_positions": 2,
                "b_connectors": 2,
                "b_positions": 1,
                "mapping": [
                    {"a_connector": 1, "a_position": 1, "b_connector": 1, "b_position": 1},
                    {"a_connector": 1, "a_position": 2, "b_connector": 2, "b_position": 1},
                ],
                "strands_per_lane": 1,
                "description": "100G broken out to 2x 50G lanes",
            },
        )

        # 1x4 Mixed-Type Showcase
        self.tmpl_mixed, _ = BreakoutTemplate.objects.get_or_create(
            name="DEMO-1x4 Mixed-Type Showcase",
            defaults={
                "a_connectors": 1,
                "a_positions": 4,
                "b_connectors": 4,
                "b_positions": 1,
                "mapping": [
                    {"a_connector": 1, "a_position": i, "b_connector": i, "b_position": 1} for i in range(1, 5)
                ],
                "strands_per_lane": 2,
                "description": "Showcase: each B-side lane connects to a different termination type "
                "(interface, front port, rear port, circuit termination)",
            },
        )

        # 2x4 → 8x1 (two trunk connectors fanning out to 8 individual legs)
        self.tmpl_2x4_to_8x1, _ = BreakoutTemplate.objects.get_or_create(
            name="DEMO-2x4 Trunk → 8x1 Fanout",
            defaults={
                "a_connectors": 2,
                "a_positions": 4,
                "b_connectors": 8,
                "b_positions": 1,
                "mapping": [
                    # Connector 1 lanes 1-4 → B connectors 1-4
                    {"a_connector": 1, "a_position": 1, "b_connector": 1, "b_position": 1},
                    {"a_connector": 1, "a_position": 2, "b_connector": 2, "b_position": 1},
                    {"a_connector": 1, "a_position": 3, "b_connector": 3, "b_position": 1},
                    {"a_connector": 1, "a_position": 4, "b_connector": 4, "b_position": 1},
                    # Connector 2 lanes 1-4 → B connectors 5-8
                    {"a_connector": 2, "a_position": 1, "b_connector": 5, "b_position": 1},
                    {"a_connector": 2, "a_position": 2, "b_connector": 6, "b_position": 1},
                    {"a_connector": 2, "a_position": 3, "b_connector": 7, "b_position": 1},
                    {"a_connector": 2, "a_position": 4, "b_connector": 8, "b_position": 1},
                ],
                "strands_per_lane": 2,
                "polarity_method": "straight-through",
                "description": "Two MPO-8 trunks (4 lanes each) fanning out to 8 individual LC duplex legs",
            },
        )

        # 4x1 → 1x4 (4 individual A-side connectors aggregating into 1 B-side trunk with 4 lanes)
        self.tmpl_4x1_to_1x4, _ = BreakoutTemplate.objects.get_or_create(
            name="DEMO-4x1 → 1x4 Aggregation",
            defaults={
                "a_connectors": 4,
                "a_positions": 1,
                "b_connectors": 1,
                "b_positions": 4,
                "mapping": [
                    {"a_connector": 1, "a_position": 1, "b_connector": 1, "b_position": 1},
                    {"a_connector": 2, "a_position": 1, "b_connector": 1, "b_position": 2},
                    {"a_connector": 3, "a_position": 1, "b_connector": 1, "b_position": 3},
                    {"a_connector": 4, "a_position": 1, "b_connector": 1, "b_position": 4},
                ],
                "strands_per_lane": 2,
                "description": "4 individual LC duplex connections aggregating into 1 MPO-8 trunk (4 lanes)",
            },
        )

        # 8x1 → 2x4 (reverse of 2x4 → 8x1: 8 individual legs aggregating into 2 trunks)
        self.tmpl_8x1_to_2x4, _ = BreakoutTemplate.objects.get_or_create(
            name="DEMO-8x1 → 2x4 Reverse Fanout",
            defaults={
                "a_connectors": 8,
                "a_positions": 1,
                "b_connectors": 2,
                "b_positions": 4,
                "mapping": [
                    # A connectors 1-4 → B connector 1 positions 1-4
                    {"a_connector": 1, "a_position": 1, "b_connector": 1, "b_position": 1},
                    {"a_connector": 2, "a_position": 1, "b_connector": 1, "b_position": 2},
                    {"a_connector": 3, "a_position": 1, "b_connector": 1, "b_position": 3},
                    {"a_connector": 4, "a_position": 1, "b_connector": 1, "b_position": 4},
                    # A connectors 5-8 → B connector 2 positions 1-4
                    {"a_connector": 5, "a_position": 1, "b_connector": 2, "b_position": 1},
                    {"a_connector": 6, "a_position": 1, "b_connector": 2, "b_position": 2},
                    {"a_connector": 7, "a_position": 1, "b_connector": 2, "b_position": 3},
                    {"a_connector": 8, "a_position": 1, "b_connector": 2, "b_position": 4},
                ],
                "strands_per_lane": 2,
                "description": "8 individual LC duplex legs aggregating into 2 MPO-8 trunks (4 lanes each)",
            },
        )

        self.stdout.write(
            f"  Created {BreakoutTemplate.objects.filter(name__startswith='DEMO').count()} breakout templates"
        )

    def _create_breakout_cables(self):
        """Create breakout cables showing different configurations."""

        # === 1. Spine 400G → 4x Leaf 100G (most common DC use case) ===
        spine_400g = self._interface(self.spine1, "Ethernet1/1", InterfaceTypeChoices.TYPE_400GE_QSFP_DD)
        leaf_100g = [
            self._interface(dev, "Ethernet1/1", InterfaceTypeChoices.TYPE_100GE_QSFP28)
            for dev in [self.leaf1, self.leaf2, self.leaf3, self.leaf4]
        ]
        cable = self._cable(
            spine_400g,
            leaf_100g[0],
            label="DEMO-BKO-SPINE-LEAF-400G",
            cable_type=CableTypeChoices.TYPE_DAC_PASSIVE,
            breakout_template=self.tmpl_1x4,
        )
        # Add remaining B-side lanes (A-side trunk port is shared across all lanes)
        from django.contrib.contenttypes.models import ContentType

        for i, leaf_intf in enumerate(leaf_100g[1:], start=2):
            entry = self.tmpl_1x4.mapping[i - 1]
            ct = ContentType.objects.get_for_model(leaf_intf)
            CableTerminationEndpoint.objects.get_or_create(
                termination_type=ct,
                termination_id=leaf_intf.pk,
                defaults={
                    "cable": cable,
                    "cable_end": "B",
                    "connector": entry["b_connector"],
                    "position": entry["b_position"],
                },
            )
            leaf_intf.cable = cable
            leaf_intf.save()

        self.stdout.write("  Created SPINE→4xLEAF 400G breakout cable")

        # === 2. 40G → 4x10G server NICs ===
        spine_40g = self._interface(self.spine1, "Ethernet2/1", InterfaceTypeChoices.TYPE_40GE_QSFP_PLUS)
        srv_10g = [
            self._interface(self.server1, f"eth{i}", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS) for i in range(1, 5)
        ]
        cable2 = self._cable(
            spine_40g,
            srv_10g[0],
            label="DEMO-BKO-40G-4x10G-SRV",
            cable_type=CableTypeChoices.TYPE_DAC_PASSIVE,
            breakout_template=self.tmpl_40g_4x10,
        )
        for i, srv_intf in enumerate(srv_10g[1:], start=2):
            entry = self.tmpl_40g_4x10.mapping[i - 1]
            ct = ContentType.objects.get_for_model(srv_intf)
            CableTerminationEndpoint.objects.get_or_create(
                termination_type=ct,
                termination_id=srv_intf.pk,
                defaults={
                    "cable": cable2,
                    "cable_end": "B",
                    "connector": entry["b_connector"],
                    "position": entry["b_position"],
                },
            )
            srv_intf.cable = cable2
            srv_intf.save()

        self.stdout.write("  Created 40G→4x10G server breakout cable")

        # === 3. 100G → 2x50G (partially connected — lane 2 unconnected) ===
        spine_100g = self._interface(self.spine1, "Ethernet3/1", InterfaceTypeChoices.TYPE_100GE_QSFP28)
        leaf_50g = self._interface(self.leaf1, "Ethernet2/1", InterfaceTypeChoices.TYPE_25GE_SFP28)
        self._cable(
            spine_100g,
            leaf_50g,
            label="DEMO-BKO-100G-2x50G-PARTIAL",
            cable_type=CableTypeChoices.TYPE_SMF,
            breakout_template=self.tmpl_1x2,
        )
        self.stdout.write("  Created 100G→2x50G partial breakout (1 of 2 lanes connected)")

        # === 4. Planned breakout cable (not yet connected) ===
        spine_future = self._interface(self.spine1, "Ethernet4/1", InterfaceTypeChoices.TYPE_400GE_QSFP_DD)
        leaf_future = self._interface(self.leaf2, "Ethernet2/1", InterfaceTypeChoices.TYPE_100GE_QSFP28)
        self._cable(
            spine_future,
            leaf_future,
            label="DEMO-BKO-PLANNED-400G",
            status=self.status_planned,
            cable_type=CableTypeChoices.TYPE_DAC_ACTIVE,
            breakout_template=self.tmpl_1x4,
        )
        self.stdout.write("  Created planned 400G breakout cable")

        # === 5. Mixed-Type Showcase: every B-side lane is a different termination type ===
        from django.contrib.contenttypes.models import ContentType

        # A-side: 4 interfaces on spine
        a_intfs = [
            self._interface(self.spine1, f"Ethernet7/{i}", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS) for i in range(1, 5)
        ]

        # B-side lane 1: Interface on a leaf
        b_lane1_intf = self._interface(self.leaf3, "Ethernet4/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS)

        # B-side lane 2: FrontPort on patch panel
        rp_mixed = self._rear_port(self.patch1, "Rear-Mixed-1")
        b_lane2_fp = self._front_port(self.patch1, "Front-Mixed-1", rp_mixed)

        # B-side lane 3: RearPort on patch panel
        b_lane3_rp = self._rear_port(self.patch1, "Rear-Mixed-2")

        # B-side lane 4: CircuitTermination
        ct_type, _ = CircuitType.objects.get_or_create(name="DEMO-Transit")
        provider, _ = Provider.objects.get_or_create(name="DEMO-ISP")
        circuit2, _ = Circuit.objects.get_or_create(
            cid="DEMO-CID-MIXED",
            defaults={
                "circuit_type": ct_type,
                "provider": provider,
                "status": Status.objects.get_for_model(Circuit).get(name="Active"),
            },
        )
        b_lane4_ct, _ = CircuitTermination.objects.get_or_create(
            circuit=circuit2,
            term_side="A",
            defaults={"location": self.location},
        )

        # Create cable with lane 1 (A-side interface → B-side interface)
        mixed_cable = self._cable(
            a_intfs[0],
            b_lane1_intf,
            label="DEMO-BKO-MIXED-TYPES",
            cable_type=CableTypeChoices.TYPE_SMF,
            breakout_template=self.tmpl_mixed,
        )

        # Add lanes 2-4 with different B-side types
        b_side_terms = [
            (2, b_lane2_fp),  # FrontPort
            (3, b_lane3_rp),  # RearPort
            (4, b_lane4_ct),  # CircuitTermination
        ]
        for lane_num, b_term in b_side_terms:
            entry = self.tmpl_mixed.mapping[lane_num - 1]

            # A-side CableTermination
            a_intf = a_intfs[lane_num - 1]
            ct_a = ContentType.objects.get_for_model(a_intf)
            CableTerminationEndpoint.objects.get_or_create(
                termination_type=ct_a,
                termination_id=a_intf.pk,
                defaults={
                    "cable": mixed_cable,
                    "cable_end": "A",
                    "connector": entry["a_connector"],
                    "position": entry["a_position"],
                },
            )
            a_intf.cable = mixed_cable
            a_intf.save()

            # B-side CableTermination
            ct_b = ContentType.objects.get_for_model(b_term)
            CableTerminationEndpoint.objects.get_or_create(
                termination_type=ct_b,
                termination_id=b_term.pk,
                defaults={
                    "cable": mixed_cable,
                    "cable_end": "B",
                    "connector": entry["b_connector"],
                    "position": entry["b_position"],
                },
            )
            if hasattr(b_term, "cable"):
                b_term.cable = mixed_cable
                b_term.save()

        self.stdout.write("  Created MIXED-TYPE breakout: Interface + FrontPort + RearPort + CircuitTermination")

        # === 6. 2x4 Trunk → 8x1 Fanout (two trunk ports, eight leg ports) ===
        from django.contrib.contenttypes.models import ContentType

        # A-side: 2 trunk ports on spine (one per connector)
        trunk_a1 = self._interface(self.spine1, "Ethernet8/1", InterfaceTypeChoices.TYPE_100GE_QSFP28)
        trunk_a2 = self._interface(self.spine1, "Ethernet8/2", InterfaceTypeChoices.TYPE_100GE_QSFP28)

        # B-side: 8 leg ports across leaf switches
        legs = [
            self._interface(self.leaf1, "Ethernet5/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS),
            self._interface(self.leaf1, "Ethernet5/2", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS),
            self._interface(self.leaf2, "Ethernet5/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS),
            self._interface(self.leaf2, "Ethernet5/2", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS),
            self._interface(self.leaf3, "Ethernet5/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS),
            self._interface(self.leaf3, "Ethernet5/2", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS),
            self._interface(self.leaf4, "Ethernet5/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS),
            self._interface(self.leaf4, "Ethernet5/2", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS),
        ]

        # Create cable with trunk_a1 as A-side lane 1, legs[0] as B-side lane 1
        fanout_cable = self._cable(
            trunk_a1,
            legs[0],
            label="DEMO-BKO-2x4-FANOUT",
            cable_type=CableTypeChoices.TYPE_SMF,
            breakout_template=self.tmpl_2x4_to_8x1,
        )

        # Add A-side connector 2 (trunk_a2)
        ct_a = ContentType.objects.get_for_model(trunk_a2)
        CableTerminationEndpoint.objects.get_or_create(
            termination_type=ct_a,
            termination_id=trunk_a2.pk,
            defaults={"cable": fanout_cable, "cable_end": "A", "connector": 2, "position": 1},
        )
        trunk_a2.cable = fanout_cable
        trunk_a2.save()

        # Add B-side connectors 2-8 (legs[1] through legs[7])
        for i, leg in enumerate(legs[1:], start=2):
            entry = self.tmpl_2x4_to_8x1.mapping[i - 1]
            ct_b = ContentType.objects.get_for_model(leg)
            CableTerminationEndpoint.objects.get_or_create(
                termination_type=ct_b,
                termination_id=leg.pk,
                defaults={
                    "cable": fanout_cable,
                    "cable_end": "B",
                    "connector": entry["b_connector"],
                    "position": entry["b_position"],
                },
            )
            leg.cable = fanout_cable
            leg.save()

        self.stdout.write("  Created 2x4 TRUNK → 8x1 FANOUT breakout (2 A-side connectors, 8 B-side connectors)")

        # === 7. 4x1 → 1x4 Aggregation (4 A-side connectors into 1 B-side trunk) ===
        # A-side: 4 individual interfaces on different leaf switches
        agg_a = [
            self._interface(self.leaf1, "Ethernet6/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS),
            self._interface(self.leaf2, "Ethernet6/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS),
            self._interface(self.leaf3, "Ethernet6/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS),
            self._interface(self.leaf4, "Ethernet6/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS),
        ]
        # B-side: 1 trunk port on spine (1 connector, 4 lanes)
        agg_b = self._interface(self.spine1, "Ethernet9/1", InterfaceTypeChoices.TYPE_40GE_QSFP_PLUS)

        # Create cable with A1→B (lane 1)
        agg_cable = self._cable(
            agg_a[0],
            agg_b,
            label="DEMO-BKO-4x1-AGGREGATION",
            cable_type=CableTypeChoices.TYPE_SMF,
            breakout_template=self.tmpl_4x1_to_1x4,
        )

        # Add A-side connectors 2-4
        for i, a_intf in enumerate(agg_a[1:], start=2):
            entry = self.tmpl_4x1_to_1x4.mapping[i - 1]
            ct_a = ContentType.objects.get_for_model(a_intf)
            CableTerminationEndpoint.objects.get_or_create(
                termination_type=ct_a,
                termination_id=a_intf.pk,
                defaults={
                    "cable": agg_cable,
                    "cable_end": "A",
                    "connector": entry["a_connector"],
                    "position": entry["a_position"],
                },
            )
            a_intf.cable = agg_cable
            a_intf.save()

        self.stdout.write("  Created 4x1 → 1x4 AGGREGATION breakout (4 A-side connectors, 1 B-side trunk)")

        # === 8. 8x1 → 2x4 Reverse Fanout (8 A-side legs into 2 B-side trunks) ===
        # A-side: 8 interfaces spread across servers
        rev_a = [
            self._interface(self.server1, f"eth{i + 10}", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS) for i in range(1, 9)
        ]
        # B-side: 2 trunk ports on spine
        rev_b1 = self._interface(self.spine1, "Ethernet10/1", InterfaceTypeChoices.TYPE_40GE_QSFP_PLUS)
        rev_b2 = self._interface(self.spine1, "Ethernet10/2", InterfaceTypeChoices.TYPE_40GE_QSFP_PLUS)

        # Create cable with A1→B1 (lane 1)
        rev_cable = self._cable(
            rev_a[0],
            rev_b1,
            label="DEMO-BKO-8x1-REVERSE-FANOUT",
            cable_type=CableTypeChoices.TYPE_SMF,
            breakout_template=self.tmpl_8x1_to_2x4,
        )

        # Add A-side connectors 2-8
        for i, a_intf in enumerate(rev_a[1:], start=2):
            entry = self.tmpl_8x1_to_2x4.mapping[i - 1]
            ct_a = ContentType.objects.get_for_model(a_intf)
            CableTerminationEndpoint.objects.get_or_create(
                termination_type=ct_a,
                termination_id=a_intf.pk,
                defaults={
                    "cable": rev_cable,
                    "cable_end": "A",
                    "connector": entry["a_connector"],
                    "position": entry["a_position"],
                },
            )
            a_intf.cable = rev_cable
            a_intf.save()

        # Add B-side connector 2 (rev_b2)
        ct_b2 = ContentType.objects.get_for_model(rev_b2)
        CableTerminationEndpoint.objects.get_or_create(
            termination_type=ct_b2,
            termination_id=rev_b2.pk,
            defaults={"cable": rev_cable, "cable_end": "B", "connector": 2, "position": 1},
        )
        rev_b2.cable = rev_cable
        rev_b2.save()

        self.stdout.write("  Created 8x1 → 2x4 REVERSE FANOUT breakout (8 A-side, 2 B-side trunks)")

    def _create_standard_cables(self):
        """Create standard point-to-point cables (no breakout)."""

        # Interface ↔ Interface (most common)
        a = self._interface(self.leaf1, "Ethernet3/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS)
        b = self._interface(self.server1, "eth5", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS)
        self._cable(a, b, label="DEMO-STD-LEAF-SRV", cable_type=CableTypeChoices.TYPE_DAC_PASSIVE)
        self.stdout.write("  Created standard Interface↔Interface cable")

    def _create_patch_panel_cables(self):
        """Create cables through a patch panel (FrontPort/RearPort)."""

        # Rear ports on patch panel
        rp1 = self._rear_port(self.patch1, "Rear-1")
        rp2 = self._rear_port(self.patch1, "Rear-2")

        # Front ports on patch panel
        fp1 = self._front_port(self.patch1, "Front-1", rp1)
        fp2 = self._front_port(self.patch1, "Front-2", rp2)

        # Server → FrontPort (front of patch panel)
        srv_intf = self._interface(self.server2, "eth1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS)
        self._cable(srv_intf, fp1, label="DEMO-SRV-PATCH-FRONT", cable_type=CableTypeChoices.TYPE_SMF)

        # RearPort → Leaf switch (back of patch panel)
        leaf_intf = self._interface(self.leaf3, "Ethernet3/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS)
        self._cable(rp1, leaf_intf, label="DEMO-PATCH-REAR-LEAF", cable_type=CableTypeChoices.TYPE_SMF)

        # Another path: Leaf4 → FrontPort2 (front) and RearPort2 → Spine (rear)
        leaf4_intf = self._interface(self.leaf4, "Ethernet3/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS)
        self._cable(leaf4_intf, fp2, label="DEMO-LEAF-PATCH-FRONT", cable_type=CableTypeChoices.TYPE_SMF)

        spine_intf = self._interface(self.spine1, "Ethernet5/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS)
        self._cable(rp2, spine_intf, label="DEMO-PATCH-REAR-SPINE", cable_type=CableTypeChoices.TYPE_SMF)

        self.stdout.write("  Created patch panel cables (FrontPort↔RearPort pass-through)")

    def _create_circuit_cable(self):
        """Create a cable connecting a device interface to a circuit termination."""

        ct_type, _ = CircuitType.objects.get_or_create(name="DEMO-Transit")
        provider, _ = Provider.objects.get_or_create(name="DEMO-ISP")
        circuit, _ = Circuit.objects.get_or_create(
            cid="DEMO-CID-001",
            defaults={
                "circuit_type": ct_type,
                "provider": provider,
                "status": Status.objects.get_for_model(Circuit).get(name="Active"),
            },
        )
        circ_term, _ = CircuitTermination.objects.get_or_create(
            circuit=circuit,
            term_side="A",
            defaults={"location": self.location},
        )

        spine_intf = self._interface(self.spine1, "Ethernet6/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS)
        self._cable(spine_intf, circ_term, label="DEMO-SPINE-CIRCUIT", cable_type=CableTypeChoices.TYPE_SMF)
        self.stdout.write("  Created Interface↔CircuitTermination cable")

    def _create_power_cables(self):
        """Create power cables (PowerPort↔PowerOutlet, PowerPort↔PowerFeed)."""

        # Power panel + feed
        panel, _ = PowerPanel.objects.get_or_create(
            name="DEMO-PP-01",
            location=self.location,
        )
        feed, _ = PowerFeed.objects.get_or_create(
            name="DEMO-Feed-A",
            power_panel=panel,
            defaults={"status": Status.objects.get_for_model(PowerFeed).first()},
        )

        # PDU power port → power feed
        pp, _ = PowerPort.objects.get_or_create(device=self.pdu, name="Input-1")
        self._cable(pp, feed, label="DEMO-PDU-FEED")

        # PDU power outlet → server power port
        po, _ = PowerOutlet.objects.get_or_create(
            device=self.pdu,
            name="Outlet-1",
            defaults={"feed_leg": PowerOutletFeedLegChoices.FEED_LEG_A},
        )
        srv_pp, _ = PowerPort.objects.get_or_create(device=self.server1, name="PSU-1")
        self._cable(po, srv_pp, label="DEMO-PDU-SRV-POWER")

        self.stdout.write("  Created power cables (PowerPort↔PowerFeed, PowerOutlet↔PowerPort)")

    def _create_console_cables(self):
        """Create console cables (ConsolePort↔ConsoleServerPort)."""

        csp, _ = ConsoleServerPort.objects.get_or_create(device=self.console_srv, name="Port-1")
        cp, _ = ConsolePort.objects.get_or_create(device=self.spine1, name="Console")
        self._cable(cp, csp, label="DEMO-CONSOLE")
        self.stdout.write("  Created ConsolePort↔ConsoleServerPort cable")

    def _create_complex_path(self):
        """Create a complex multi-hop path: breakout → patch panel → patch panel → devices.

        Topology:
            SPINE-01 Ethernet11/1 (400G QSFP-DD)
                │
                │  1x4 breakout cable
                │
            ┌───┼───┬───┐
            B1  B2  B3  B4
            │   │   │   │
          [LEAF-01       ]   [PATCH-01             ]
          Eth7/1  Eth7/2     Front-LC-1  Front-LC-2
                                  │ pos=1     │ pos=2
                              Rear-MPO-1 (positions=2)
                                      │
                                 MPO cable (single)
                                      │
                              Rear-MPO-1 (positions=2)
                                  │ pos=1     │ pos=2
                             Front-LC-1  Front-LC-2
                            [PATCH-02              ]
                                  │           │
                             std cable    std cable
                                  │           │
                            [LEAF-02]    [LEAF-03]
                             Eth7/1       Eth7/1
        """
        from django.contrib.contenttypes.models import ContentType

        # === Origin: Spine 400G port ===
        spine_port = self._interface(self.spine1, "Ethernet11/1", InterfaceTypeChoices.TYPE_400GE_QSFP_DD)

        # === B-side leg 1 & 2: direct to LEAF-01 ===
        leaf1_eth1 = self._interface(self.leaf1, "Ethernet7/1", InterfaceTypeChoices.TYPE_100GE_QSFP28)
        leaf1_eth2 = self._interface(self.leaf1, "Ethernet7/2", InterfaceTypeChoices.TYPE_100GE_QSFP28)

        # === B-side leg 3 & 4: to PATCH-01 front ports ===
        # Single MPO rear port with 2 positions
        rp1_mpo = self._rear_port(self.patch1, "Rear-MPO-1", positions=2, port_type=PortTypeChoices.TYPE_MPO)
        fp1_lc1 = self._front_port(
            self.patch1, "Front-LC-1", rp1_mpo, rear_port_position=1, port_type=PortTypeChoices.TYPE_LC
        )
        fp1_lc2 = self._front_port(
            self.patch1, "Front-LC-2", rp1_mpo, rear_port_position=2, port_type=PortTypeChoices.TYPE_LC
        )

        # === Create the breakout cable (1x4) ===
        complex_cable = self._cable(
            spine_port,
            leaf1_eth1,
            label="DEMO-BKO-COMPLEX-PATH",
            cable_type=CableTypeChoices.TYPE_DAC_PASSIVE,
            breakout_template=self.tmpl_1x4,
        )

        # Add remaining 3 B-side lanes (A-side trunk port is shared across all lanes)
        b_side_terms = [
            (2, leaf1_eth2),  # B2 → LEAF-01 Eth7/2
            (3, fp1_lc1),  # B3 → PATCH-01 Front-LC-1
            (4, fp1_lc2),  # B4 → PATCH-01 Front-LC-2
        ]
        for lane_num, b_term in b_side_terms:
            entry = self.tmpl_1x4.mapping[lane_num - 1]
            ct_b = ContentType.objects.get_for_model(b_term)
            CableTerminationEndpoint.objects.get_or_create(
                termination_type=ct_b,
                termination_id=b_term.pk,
                defaults={
                    "cable": complex_cable,
                    "cable_end": "B",
                    "connector": entry["b_connector"],
                    "position": entry["b_position"],
                },
            )
            if hasattr(b_term, "cable"):
                b_term.cable = complex_cable
                b_term.save()

        self.stdout.write("  Created complex path: breakout cable (SPINE → 2xLEAF-01 + 2xPATCH-01)")

        # === PATCH-02: single MPO rear port with 2 positions ===
        rp2_mpo = self._rear_port(self.patch2, "Rear-MPO-1", positions=2, port_type=PortTypeChoices.TYPE_MPO)
        fp2_lc1 = self._front_port(
            self.patch2, "Front-LC-1", rp2_mpo, rear_port_position=1, port_type=PortTypeChoices.TYPE_LC
        )
        fp2_lc2 = self._front_port(
            self.patch2, "Front-LC-2", rp2_mpo, rear_port_position=2, port_type=PortTypeChoices.TYPE_LC
        )

        # === Single MPO cable: PATCH-01 Rear-MPO-1 → PATCH-02 Rear-MPO-1 ===
        self._cable(rp1_mpo, rp2_mpo, label="DEMO-MPO-PATCH1-PATCH2", cable_type=CableTypeChoices.TYPE_MMF)
        self.stdout.write("  Created single MPO trunk cable (PATCH-01 → PATCH-02)")

        # === LC cables: PATCH-02 front ports → destination devices ===
        leaf2_eth1 = self._interface(self.leaf2, "Ethernet7/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS)
        self._cable(fp2_lc1, leaf2_eth1, label="DEMO-PATCH2-LC1-LEAF2", cable_type=CableTypeChoices.TYPE_SMF)

        leaf3_eth1 = self._interface(self.leaf3, "Ethernet7/1", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS)
        self._cable(fp2_lc2, leaf3_eth1, label="DEMO-PATCH2-LC2-LEAF3", cable_type=CableTypeChoices.TYPE_SMF)

        self.stdout.write("  Created LC cables (PATCH-02 → LEAF-02, LEAF-03)")
        self.stdout.write(
            self.style.SUCCESS(
                "  COMPLEX PATH: SPINE →(breakout)→ 2xLEAF-01 + 2xPATCH-01 →(MPO trunk)→ PATCH-02 →(LC)→ LEAF-02 + LEAF-03"
            )
        )
