# Breakout Cables

+++ 3.1

Breakout cables are multi-lane cable assemblies where a single physical cable splits into multiple individual connections. Common examples include:

- A **400G QSFP-DD** port broken out into **4×100G SFP** lanes, each connecting to a different leaf switch
- A **40GE** interface broken out into **4×10GE** lanes terminating on four separate server NICs
- An **MPO-12** trunk fanning out to **twelve individual LC duplex** connections at a fiber distribution frame
- Two **MPO-8** trunks (4 lanes each) fanning out to **8 individual legs** across multiple devices

In Nautobot, a breakout cable is simply a [cable](../core-data-model/dcim/cable.md) with a [breakout template](../core-data-model/dcim/breakouttemplate.md) assigned. Standard cables and breakout cables appear in the same cable list — the breakout behavior is unlocked by the template.

## Terminology

These terms describe the physical parts of a breakout cable and how they relate to each other in Nautobot.

### Naming Convention

Throughout Nautobot, a specific point on a cable is referenced as **`{Side}{Connector}`** — for example, `A1` or `B3`. The side is a single letter (`A` or `B`), and the connector is a 1-based number. Position (the lane within a connector) is internal detail and not shown in the primary label — it appears in tooltips or expanded views when relevant.

### Connector

A **connector** is a physical plug or receptacle at one end of a cable. A standard point-to-point cable has one connector on each end. A breakout cable may have a different number of connectors on each end — for example, one MPO connector on the trunk side and four LC connectors on the leg side.

In Nautobot, each end of a cable (A-side and B-side) has a configurable number of connectors. The breakout template defines how many connectors exist on each side.

All connectors on the same side of a cable are assumed to be the same type with the same number of positions. For example, if Side B has 4 connectors with 1 position each, all 4 are the same connector type (e.g., all LC). Mixed connector types on the same side are not supported.

**Examples:**

- A 1×4 DAC breakout: 1 QSFP-DD connector on Side A (4 positions), 4 SFP28 connectors on Side B (1 position each)
- A 2×4 MPO trunk: 2 MPO-8 connectors on each side (4 positions each)

### Position

A **position** is a single path within a connector. A connector may carry one or more positions. Each position represents one logical channel through that connector.

- A simple SFP connector has **1 position** — one path in, one path out.
- A QSFP connector has **4 positions** — four parallel paths.
- An MPO-12 connector used for duplex fiber has **6 positions** (12 strands ÷ 2 strands per position).

In the breakout template, `a_positions` and `b_positions` define how many positions each connector has on their respective sides. The total number of lanes in the cable is `connectors × positions`.

### Lane

A **lane** is one discrete end-to-end path through the entire cable, from an A-side connector+position to a B-side connector+position. The breakout template's `mapping` field defines each lane as a pair: which A-side connector and position maps to which B-side connector and position.

For a 1×4 breakout cable, there are 4 lanes:

| Lane | A-Side | B-Side |
|------|--------|--------|
| 1 | Connector 1, Position 1 | Connector 1, Position 1 |
| 2 | Connector 1, Position 2 | Connector 2, Position 1 |
| 3 | Connector 1, Position 3 | Connector 3, Position 1 |
| 4 | Connector 1, Position 4 | Connector 4, Position 1 |

The total lane count equals the length of the mapping array: `a_connectors × a_positions` (which must equal `b_connectors × b_positions`).

### Strand

A **strand** is a single physical fiber or conductor within a cable. A lane may require one or more strands depending on the transmission technology:

| Technology | Strands Per Lane | Example |
|------------|-----------------|---------|
| Copper / DAC | 1 | One copper pair per lane |
| Duplex fiber (standard) | 2 | One strand transmits, one receives (Tx/Rx) |
| Parallel optics (PSM4, SR4) | 8 | Multiple strands per lane for higher bandwidth |

The `strands_per_lane` field on the breakout template captures this. The total physical strand count is `total_lanes × strands_per_lane`. This is useful for fiber plant documentation and capacity planning — for example, an MPO-12 cable with 6 duplex lanes has 12 total strands.

### Polarity

**Polarity** describes how the transmit (Tx) and receive (Rx) strands are arranged between the two ends of a fiber cable. Correct polarity ensures that the Tx output at one end connects to the Rx input at the other end. There are several standard polarity methods:

#### Straight-through (Method A / TIA-568)

Strand 1 at end A connects to strand 1 at end B. Strand 2 at A connects to strand 2 at B, and so on. The Tx/Rx swap happens at the connector — one end uses a "key up" orientation and the other uses "key down," which provides the crossover.

This is the most common method for MPO trunk cables. It requires that one end of the cable has the connector installed in the opposite orientation (key up to key down).

#### Reversed (Method B)

Strand 1 at end A connects to strand N at end B (where N is the total strand count). Strand 2 at A connects to strand N-1 at B, and so on. Both connectors are "key up to key up." The cable itself provides the Tx/Rx swap by reversing the entire fiber order.

This is simple to understand and widely used. For a 12-strand MPO, strand 1 maps to strand 12, strand 2 to strand 11, etc.

#### Pair-reversed (Method C)

Strands are swapped in adjacent pairs rather than fully reversed. Strand 1 connects to strand 2, strand 2 to strand 1, strand 3 to strand 4, strand 4 to strand 3, and so on. Each Tx/Rx pair is locally swapped.

This is less common but used in specific high-density applications where pair-level polarity management is needed.

#### Custom

Any non-standard polarity arrangement that doesn't fit the above methods. The actual strand mapping is defined by the lane mapping in the breakout template; the polarity method field is informational only and does not affect tracing or validation.

!!! note
    The `polarity_method` field is informational — Nautobot does not validate or enforce strand-level polarity. It is intended for documentation and compliance purposes. The lane-level mapping (connector+position to connector+position) is what Nautobot uses for path tracing.

## Creating a Breakout Template

Navigate to **DCIM > Breakout Templates** and click **Add**.

### Connector and Position Counts

Define the physical structure of each cable end:

- **A Connectors** — number of physical connectors on the A side (e.g., 1 for a single trunk port)
- **A Positions** — number of positions (lanes) per A-side connector (e.g., 4 for a 4-lane trunk)
- **B Connectors** — number of physical connectors on the B side (e.g., 4 for four individual legs)
- **B Positions** — number of positions per B-side connector (e.g., 1 for single-lane legs)

### Lane Mapping

The mapping defines how each A-side position connects to a B-side position. On the create/edit form, the mapping is presented in three modes:

- **Auto-generate** (default) — the mapping is automatically generated from the connector and position counts in a sequential fan-out pattern. This covers the vast majority of real-world breakout cables.
- **Table editor** — a table with one row per lane, allowing you to customize individual position assignments. Use this for polarity shuffles or non-standard mappings.
- **JSON editor** — click the "JSON" button to switch to a raw JSON textarea for advanced editing or pasting from external tools.

#### Mapping JSON Format

Each entry in the mapping array maps one A-side connector+position pair to one B-side connector+position pair:

```json
[
  { "a_connector": 1, "a_position": 1, "b_connector": 1, "b_position": 1 },
  { "a_connector": 1, "a_position": 2, "b_connector": 2, "b_position": 1 },
  { "a_connector": 1, "a_position": 3, "b_connector": 3, "b_position": 1 },
  { "a_connector": 1, "a_position": 4, "b_connector": 4, "b_position": 1 }
]
```

This example represents a 1×4 breakout: one 4-position A-side connector fans out to four single-position B-side connectors.

### Fiber-Specific Fields

For fiber optic cables:

- **Strands Per Lane** — number of physical strands per logical lane (1 for copper/DAC, 2 for duplex fiber, 8 for parallel optics)
- **Polarity Method** — the fiber polarity method (Straight-through, Reversed, Pair-reversed, Custom). Informational only.

### Lane Mapping Diagram

The template detail view shows an SVG diagram of the connector mapping. A-side connectors appear on the left, B-side on the right, with lines showing the mapping. Connectors with multiple positions show the lane count in parentheses.

## Assigning a Template to a Cable

Edit any cable and select a breakout template from the **Breakout Template** dropdown. The template dropdown is only enabled for cables with compatible termination types:

- Interfaces
- Front ports
- Rear ports
- Circuit terminations

Power and console cables do not support breakout templates.

When a template is assigned, the cable edit form dynamically updates to show the correct number of connector rows for each side. If the cable already had terminations (a standard A↔B connection), those terminations are preserved as the first connector on each side.

## Managing Connections

### Connections Table

The cable detail view shows a **Connections** table with Side A on the left and Side B on the right. For breakout cables, connectors with fewer counterparts use row spanning to visually group related connections.

Each connection shows:

- A **type icon** indicating the termination type (interface, front port, circuit termination, etc.)
- The **parent object** (device, circuit, or power panel) as a clickable link
- The **termination object** as a clickable link
- An **"Unconnected"** badge for lanes without a termination

### Editing Connections

On the cable edit form, each connector row has three fields:

1. **Type** — select the termination type (Interface, Front Port, Rear Port, etc.)
2. **Parent** — select the parent object (Device, Circuit, etc.), filtered by type
3. **Termination** — select the specific termination object, filtered by parent

Changing the type dynamically swaps the parent and termination picker fields. Mixed termination types are supported — for example, some lanes can connect to device interfaces while others connect to circuit terminations.

### Lane Mapping Diagram

Below the connections table, the cable detail view shows an SVG lane mapping diagram:

- **Green nodes** — connectors with a termination assigned
- **Gray nodes** — unconnected connectors
- **Lines** — show the mapping between A-side and B-side connectors
- **Tooltips** — hover over a node to see the connected device and interface

## Cable Trace

When tracing a cable path that passes through a breakout cable, Nautobot follows the correct lane via the template mapping:

1. The trace identifies which connector and position the entry point is on
2. It looks up the mapped connector and position on the far side
3. If the far side is connected, the trace continues from that termination
4. If the far side is unconnected, the trace halts

The cable trace view shows breakout lane info on each breakout cable hop: a split icon with the connector and position (e.g., "Connector 1, Position 2").

## REST API

### Creating a Breakout Cable

```json
POST /api/dcim/cables/
{
    "breakout_template": "<template-uuid>",
    "label": "SRV1-SPINE1-BKO",
    "status": "<status-uuid>",
    "lanes": [
        {
            "lane": 1,
            "a_termination": { "object_type": "dcim.interface", "object_id": "<uuid>" },
            "b_termination": { "object_type": "dcim.interface", "object_id": "<uuid>" }
        },
        {
            "lane": 2,
            "a_termination": { "object_type": "dcim.interface", "object_id": "<uuid>" },
            "b_termination": null
        }
    ]
}
```

Lane 2 has a null `b_termination`, representing an unconnected leg.

### Filtering

- `?breakout_template=<uuid>` — cables using a specific template
- `?breakout_template__isnull=true` — standard cables only
- `?breakout_template__isnull=false` — breakout cables only
- `?termination_a_type=dcim.interface` — cables with A-side interfaces
- `?termination_b_type=dcim.interface` — cables with B-side interfaces
- `?termination_type=dcim.interface` — cables with interfaces on either side

## Demo Data

A management command generates comprehensive demo data for testing:

```bash
nautobot-server create_breakout_demo_data
```

Use `--flush` to delete and recreate:

```bash
nautobot-server create_breakout_demo_data --flush
```

This creates:

- 9 breakout templates (1×4, 40G→4×10G, MPO-12, 2×4 shuffle, 1×2, mixed-type, 2×4→8×1 fanout, 4×1→1×4 aggregation, 8×1→2×4 reverse)
- 15+ cables covering all termination types (interface, front port, rear port, circuit termination, power, console)
- Spare interfaces on all devices for testing
- All contained in a single "DEMO-DC1" location
