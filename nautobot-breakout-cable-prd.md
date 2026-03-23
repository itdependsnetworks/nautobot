# Nautobot — Breakout Cable Feature PRD

> **Scope:** This PRD covers the `BreakoutTemplate` model and the extensions to the existing `Cable` and `CableTermination` models required to support multi-lane breakout cables. Splice support is a separate feature (see **nautobot-breakout-cable-splice-prd.md**). Lane-aware pass-through device support is also a separate feature (see **nautobot-lane-aware-passthrough-prd.md**), but this feature must not foreclose that option — see §7.

## 1. Use Cases

The following are common scenarios where Nautobot's current single-termination cable model is insufficient:

- A 400G QSFP-DD spine port broken out into 4×100G SFP lanes, each connecting to a different leaf switch interface, via a single physical cable assembly
- A 40GE interface broken out into 4×10GE lanes terminating on four separate server NICs — the four legs are one cable, not four
- An MPO-12 trunk fanning out to twelve individual LC duplex connections at a fiber distribution frame
- A partially-utilized breakout cable where only 2 of 4 legs are connected — the unconnected legs must be explicitly documented, not simply absent

## 2. What

Extend Nautobot's existing `Cable` and `CableTermination` models to support multi-lane breakout cables, and introduce a new `BreakoutTemplate` model to hold reusable lane structure definitions.

**The core design principle:** a breakout cable is a `Cable`. It is not a parallel object or a subtype. A user browsing the cable list sees breakout cables and standard cables in the same place. The breakout behavior is unlocked by assigning a `BreakoutTemplate` to a cable — a nullable FK on the `Cable` model. Cables without a template assigned behave identically to today.

The changes required are:
- A new **`BreakoutTemplate`** model defining connectors, positions, and the A→B lane mapping.
- A new **`CableTerminationEndpoint`** concrete join table replacing Cable's existing GFK-based termination fields (`termination_a_type`, `termination_a_id`, `termination_b_type`, `termination_b_id`). Each row stores: cable, cable_end (A/B), termination GFK, connector, and position.
- A nullable **`breakout_template`** FK field on `Cable`.
- **`connector`** and **`position`** integer fields on `CableTerminationEndpoint`, identifying which lane of the cable a given termination occupies. These are null for cables without a template.
- Relaxing the existing one-termination-per-side constraint on `Cable` to allow multiple terminations per side when a template is assigned.
- Updated `CablePath` tracing to follow the correct lane through a breakout cable rather than treating it as a single hop.
- A server-side SVG cable trace renderer that supports breakout fan-out visualization with a two-phase matrix-based layout, handling multi-hop paths through patch panels at arbitrary depth.
- A server-side SVG breakout diagram renderer for lane mapping visualization on template and cable detail views.
- Pre-populated default breakout templates via data migration for common AOC and fiber MPO configurations.

### 2.1 Requirements

- Allow users to define reusable **`BreakoutTemplates`** that describe a cable's internal lane structure: connectors, positions per connector, and an explicit A→B lane mapping.
- Allow users to assign a `BreakoutTemplate` to any `Cable`, unlocking multi-termination behavior for that cable.
- When a template is assigned, `connector` and `position` values are automatically populated on each `CableTerminationEndpoint` according to the template mapping. These values are managed by Nautobot — users do not set them manually.
- Allow lanes to have a null B-side termination, explicitly representing an unconnected leg. This is distinct from the leg simply not existing.
- Enable per-lane `CablePath` tracing: following a path into a specific termination on a breakout cable resolves, via the template mapping, to the correct termination on the other side.
- Provide a fan-out diagram on the cable detail view when a template is assigned, annotated with actual termination names and visually distinguishing connected vs. unconnected lanes.
- Provide a server-side SVG cable trace renderer that handles linear traces, breakout fan-outs, and multi-hop paths through patch panels (FrontPort/RearPort pass-throughs, including multi-position rear ports for MPO trunk cables) at arbitrary depth.
- Preserve identical behavior for all existing cables with no template assigned — backward-compatible read-only properties (`termination_a`, `termination_b`) and the `Cable(termination_a=obj, termination_b=obj)` creation pattern must continue to work. No migration of existing data required beyond populating the new join table from existing GFK fields.
- Ship default breakout templates via data migration for common configurations (AOC fanouts: 1×2, 1×4, 1×8, 2×4; fiber MPO fanouts: MPO-8→4×LC, MPO-12→6×LC, MPO-24→12×LC, MPO-24→2×MPO-12, 2×MPO-12→12×LC).
- Expose all new fields and models via REST API and GraphQL.
- Support all standard Nautobot features on `BreakoutTemplate`: tags, custom fields, change logging.

### 2.2 Non-Requirements

- Cables do not automatically create interface or port objects for broken-out lanes.
- `BreakoutTemplate` does not validate physical connector compatibility — it is a documentation construct.
- Assigning a template to an existing cable that already has terminations is not permitted without first clearing the existing terminations.
- No automatic lane allocation or utilization tracking beyond what is surfaced by the `connected_lanes` / `total_lanes` properties.

## 3. Model: BreakoutTemplate

A `BreakoutTemplate` is a reusable, named definition of a cable's internal lane structure. It is defined once and assigned to many `Cable` instances.

### 3.1 Fields

| Field             | Type        | Required | Default | Description                                                                                                                                                          |
|-------------------|-------------|----------|---------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `name`            | CharField   | Yes      | —       | Human-readable name (e.g. "1×4 AOC Fanout", "MPO-12 → 6×LC Duplex"). Must be unique.                                                                               |
| `description`     | CharField   | No       | —       | Optional free-text description.                                                                                                                                      |
| `a_connectors`    | PositiveInt | Yes      | —       | Number of physical connectors on the A side.                                                                                                                         |
| `a_positions`     | PositiveInt | Yes      | —       | Number of positions (lanes) per A-side connector.                                                                                                                    |
| `b_connectors`    | PositiveInt | Yes      | —       | Number of physical connectors on the B side.                                                                                                                         |
| `b_positions`     | PositiveInt | Yes      | —       | Number of positions (lanes) per B-side connector.                                                                                                                    |
| `mapping`         | JSONField   | Yes      | —       | Explicit A→B lane mapping. See §3.2.                                                                                                                                 |
| `is_shuffle`      | Boolean     | Yes      | False   | Indicates non-linear (polarity-shuffled) position mapping. Informational only — tracing always follows `mapping` explicitly regardless of this flag.                 |
| `strands_per_lane`| PositiveInt | Yes      | 1       | Number of physical strands that constitute one logical lane. Use 1 for copper/AOC, 2 for standard duplex fiber, 8 for parallel optics (e.g. PSM4/SR4 QSFP), etc.   |
| `polarity_method` | ChoiceField | No       | null    | The fiber polarity method used by cables of this template. Choices: Straight-through, Reversed, Pair-reversed. Informational only — for compliance documentation purposes.|

> **Polarity methods:**
> - **Straight-through:** Strand 1 at end A connects to strand 1 at end B. Works if one end has a crossed connector (MPO "key up to key down"), providing the Tx/Rx swap at the connector itself.
> - **Reversed:** Strand 1 at end A connects to strand 12 at end B (for a 12-strand MPO). Both connectors are "key up to key up." The cable itself provides the swap.
> - **Pair-reversed:** Strands are swapped in pairs rather than fully reversed. Less common, used in specific high-density applications.

### 3.2 Mapping Format

The `mapping` field is a JSON array. Each entry defines one discrete lane through the cable, expressed as an A-side connector+position pair mapping to a B-side connector+position pair:

```json
[
  { "a_connector": 1, "a_position": 1, "b_connector": 1, "b_position": 1 },
  { "a_connector": 1, "a_position": 2, "b_connector": 2, "b_position": 1 },
  { "a_connector": 1, "a_position": 3, "b_connector": 3, "b_position": 1 },
  { "a_connector": 1, "a_position": 4, "b_connector": 4, "b_position": 1 }
]
```

This example represents a 1×4 breakout: one 4-position A-side connector fans out to four single-position B-side connectors.

A shuffle example (2×4 trunk with polarity swap):

```json
[
  { "a_connector": 1, "a_position": 1, "b_connector": 1, "b_position": 1 },
  { "a_connector": 1, "a_position": 2, "b_connector": 1, "b_position": 2 },
  { "a_connector": 1, "a_position": 3, "b_connector": 2, "b_position": 1 },
  { "a_connector": 1, "a_position": 4, "b_connector": 2, "b_position": 2 },
  { "a_connector": 2, "a_position": 1, "b_connector": 1, "b_position": 3 },
  { "a_connector": 2, "a_position": 2, "b_connector": 1, "b_position": 4 },
  { "a_connector": 2, "a_position": 3, "b_connector": 2, "b_position": 3 },
  { "a_connector": 2, "a_position": 4, "b_connector": 2, "b_position": 4 }
]
```

### 3.3 Properties

| Property             | Description                                                                                                       |
|----------------------|-------------------------------------------------------------------------------------------------------------------|
| `total_lanes`        | Total number of discrete lanes: length of the `mapping` array.                                                    |
| `total_strands`      | Total physical strand count: `total_lanes × strands_per_lane`. Informational — useful for fiber plant documentation and capacity planning. |
| `is_breakout`        | True if `a_connectors != b_connectors` or `a_positions != b_positions`.                                           |
| `cable_count`        | Number of Cable instances currently assigned this template.                                                       |

### 3.4 Constraints & Validation

- Every `(a_connector, a_position)` pair in `mapping` must be unique.
- Every `(b_connector, b_position)` pair in `mapping` must be unique.
- `a_connectors × a_positions` must equal the number of distinct A-side entries in `mapping`.
- `b_connectors × b_positions` must equal the number of distinct B-side entries in `mapping`.
- `strands_per_lane` must be a positive integer. Common values are 1 (copper/AOC), 2 (duplex fiber), 4, 8, 12 — but no enumeration is enforced, as physical standards vary.
- `polarity_method` is only meaningful when `strands_per_lane >= 2`. No validation error is raised if it is set on a non-fiber template, but the UI should suppress it when `strands_per_lane = 1`.
- `name` must be unique.
- A `BreakoutTemplate` that has one or more `Cable` instances assigned cannot be deleted. It must be unassigned from all cables first.

### 3.5 Default Templates (Pre-populated)

The following templates are shipped as default data via data migration, using generic connector names (no speed ratings):

**AOC Ethernet Breakouts** (strands_per_lane=1):
- 1×2 AOC Fanout (1 conn × 2 pos → 2 conn × 1 pos)
- 1×4 AOC Fanout (1 conn × 4 pos → 4 conn × 1 pos)
- 1×8 AOC Fanout (1 conn × 8 pos → 8 conn × 1 pos)
- 2×4 AOC Fanout (2 conn × 4 pos → 8 conn × 1 pos)

**Fiber MPO Fanouts** (strands_per_lane=2, polarity=straight-through):
- MPO-8 → 4×LC Duplex (1 conn × 4 pos → 4 conn × 1 pos)
- MPO-12 → 6×LC Duplex (1 conn × 6 pos → 6 conn × 1 pos)
- MPO-24 → 12×LC Duplex (1 conn × 12 pos → 12 conn × 1 pos)
- MPO-24 → 2×MPO-12 (1 conn × 12 pos → 2 conn × 6 pos)
- 2×MPO-12 → 12×LC Duplex (2 conn × 6 pos → 12 conn × 1 pos)

---

## 4. Changes to `Cable`

### 4.1 New Field

| Field                | Type                      | Required | Default | Description                                                                                               |
|----------------------|---------------------------|----------|---------|---------------------------------------------------------------------------------------------------------------------------|
| `breakout_template`  | FK → BreakoutTemplate     | No       | null    | The template defining this cable's lane structure. Null for standard point-to-point cables. When set, multi-termination behavior is enabled and `CableTerminationEndpoint.connector` / `position` values are managed automatically. |

### 4.2 Termination Join Table

The existing GFK fields (`termination_a_type`, `termination_a_id`, `termination_b_type`, `termination_b_id`) on `Cable` are replaced by a concrete **`CableTerminationEndpoint`** join table. Each row represents one side of one lane:

| Field              | Type                      | Required | Default | Description                                                                                               |
|--------------------|---------------------------|----------|---------|-----------------------------------------------------------------------------------------------------------|
| `cable`            | FK → Cable                | Yes      | —       | The parent cable. Cascade-deletes with the cable.                                                         |
| `cable_end`        | CharField(1)              | Yes      | —       | "A" or "B".                                                                                               |
| `termination_type` | FK → ContentType          | Yes      | —       | ContentType of the termination object.                                                                     |
| `termination_id`   | UUIDField                 | Yes      | —       | PK of the termination object.                                                                             |
| `termination`      | GenericForeignKey          | —        | —       | Resolved termination object (Interface, FrontPort, etc.).                                                 |
| `connector`        | PositiveSmallIntegerField  | No       | null    | Connector number on this cable end. Null for cables without a template.                                   |
| `position`         | PositiveSmallIntegerField  | No       | null    | Position (lane) within the connector. Null for cables without a template.                                 |

A termination object can only be connected to one cable (unique constraint on termination_type + termination_id).

### 4.3 Termination Count Behavior

| `breakout_template` | Allowed terminations per side                                                                         |
|---------------------|-------------------------------------------------------------------------------------------------------|
| `null`              | Exactly 1 (existing behavior, unchanged).                                                             |
| Set                 | 1 to `total_lanes` on the A side; 0 to `total_lanes` on the B side. Each termination is associated with one lane in the template mapping. B-side terminations may be null per-lane to represent unconnected legs. |

### 4.4 Backward-Compatible Properties

The following read-only properties query the `CableTerminationEndpoint` join table to maintain backward compatibility:

| Property            | Description                                                                                     |
|---------------------|-------------------------------------------------------------------------------------------------|
| `termination_a`     | First A-side termination object.                                                                |
| `termination_b`     | First B-side termination object.                                                                |
| `termination_a_type`| ContentType of first A-side termination.                                                        |
| `termination_b_type`| ContentType of first B-side termination.                                                        |
| `terminations_a`    | QuerySet of all A-side termination endpoint rows.                                               |
| `terminations_b`    | QuerySet of all B-side termination endpoint rows.                                               |

The `Cable(termination_a=obj, termination_b=obj)` creation pattern must continue to work. The constructor captures these kwargs and the post-save hook creates the corresponding join table rows.

### 4.5 Breakout-Specific Properties

| Property            | Description                                                                                     |
|---------------------|-------------------------------------------------------------------------------------------------|
| `breakout_eligible` | True if all terminations are breakout-compatible types (interface, front port, rear port, circuit termination). Power and console termination types are excluded. |
| `total_lanes`       | Template's total lane count, or None.                                                           |
| `connected_lanes`   | Count of lanes where both A and B sides have terminations.                                      |

### 4.6 Template Assignment Rules

- A template may only be assigned to a cable with breakout-compatible termination types: interface, front port, rear port, or circuit termination. Assigning to power or console cables raises a validation error.
- Changing the template on a cable that already has lane terminations is not permitted. The template must be cleared and terminations deleted first.
- Removing a template from a cable deletes all multi-termination endpoint rows beyond the first on each side, and clears `connector` and `position` on any remaining rows.

---

## 5. Changes to `CableTermination`

### 5.1 Abstract Mixin

The existing abstract `CableTermination` mixin (on Interface, FrontPort, RearPort, ConsolePort, ConsoleServerPort, PowerPort, PowerOutlet, PowerFeed, CircuitTermination) retains its original name for backward compatibility. The concrete join table is named `CableTerminationEndpoint` to avoid collision.

### 5.2 Peer Resolution

When resolving a cable peer via the mixin's `get_cable_peer()` method:
- For standard cables: return the termination on the opposite side.
- For breakout cables: look up the mapping entry for this termination's connector/position, then return the termination on the opposite side at the mapped connector/position.

### 5.3 Disconnect on Delete

When a termination object (Interface, FrontPort, etc.) is deleted, the corresponding `CableTerminationEndpoint` row is removed **without** deleting the Cable itself. This ensures disconnecting a single leg of a breakout cable does not destroy the entire cable. The user is informed that the cable was not deleted and provided a link to the cable.

---

## 6. Path Tracing

### 6.1 Cables Without a Template (Existing Behavior)

Unchanged. A cable with `breakout_template=null` is treated as a single hop between its one A-side and one B-side termination.

### 6.2 Cables With a Template (Per-Lane Tracing)

When `CablePath` tracing encounters a cable with a `breakout_template` assigned, it switches from single-hop tracing to per-lane tracing:

1. Identify the `connector` and `position` on the `CableTerminationEndpoint` at the entry point.
2. Look up the corresponding mapping entry in `breakout_template.mapping` to find the paired `connector` and `position` on the far side.
3. Find the `CableTerminationEndpoint` on the far side matching that `connector` and `position`.
4. If that termination has a null `termination_object` (unconnected lane), the trace halts and displays an "unconnected lane" warning with the lane identifier.
5. Otherwise, continue tracing from that termination's object.

### 6.3 SVG Trace Renderer

The cable trace visualization is rendered as a server-side SVG, using a two-phase architecture:

**Phase 1 — Build matrix:** Collect trace data into a row/column matrix with spatial metadata:
- Each fan-out leg becomes a column.
- Trace segments (device nodes, cable segments, pass-through hops) become rows.
- Consecutive same-parent terminations at the same depth get column-span (grouped into a shared device box with side-by-side termination sub-boxes).
- Empty cells below active content get continuation markers (faint vertical lines).
- Pass-through hops (FrontPort → RearPort) are explicitly followed, including through multi-position rear ports (MPO trunk cables between patch panels), at arbitrary depth.

**Phase 2 — Render matrix:** Walk the matrix and draw each cell at its computed pixel position:
- Row heights are pre-computed so all cells at the same depth align horizontally.
- Stretchy cells (pass-throughs, continuations) fill the full row height.
- Grouped nodes render as a single device box with side-by-side termination sub-boxes.
- Linear traces (no fan-out) render as a simple top-to-bottom flow of device → cable → device segments.

### 6.4 Display

The path trace visualization displays:
- Connector labels (e.g. "B3") on each fan-out leg drop line.
- Breakout template name on the trunk cable segment.
- Lane info ("Breakout: A1 → B3") on per-lane cable segments.
- "pass-thru" label on FrontPort → RearPort pass-through hops.
- Faint continuation lines for columns with no content at a given row depth.
- The trace SVG is rendered in a left-panel card ("Cable Trace"), with "Related Paths" in a right-panel card.

---

## 7. Related Feature: Lane-Aware Pass-Through Devices

> **Scope:** Out of scope for this delivery. See companion PRD: **nautobot-lane-aware-passthrough-prd.md**.

A customer has identified a need for pass-through devices (passive shuffle boxes, MPO polarity modules) whose internal FrontPort → RearPort mapping is lane-aware in the same sense as a `BreakoutTemplate`. The cables on both sides of such a device would be breakout cables covered by this feature; the gap is the device model itself.

### 7.1 Design Constraint

The `CablePath` tracing implementation **must not** hardcode the assumption that all pass-through hops are lane-unaware. It should propagate the `(connector, position)` identifier entering a pass-through port and be structured to allow a future lookup against a `PortLaneMapping` table at that hop, even though that table does not exist yet. This is a code-review concern, not a user-facing acceptance criterion.

---

## 8. View Considerations

### 8.1 BreakoutTemplate Views
- Standard list, create, edit, delete views under DCIM > Breakout Templates.
- Detail view shows the full mapping table with one row per lane, plus `cable_count`, `total_lanes`, `total_strands`, and a fan-out diagram.
- `polarity_method` is displayed on the detail view only when `strands_per_lane >= 2`; it is suppressed from the create/edit form when `strands_per_lane = 1` to avoid presenting irrelevant fields for copper/AOC templates.
- The **fan-out diagram** renders A-side connector(s) and their positions fanning out to B-side connectors. Straight-through mappings render as parallel lines; shuffle mappings render with crossing lines. Lane numbers are shown on connecting lines.
- The breakout template create/edit form auto-generates the lane mapping from connector and position counts. A table editor allows per-lane customization, and a "JSON" toggle allows raw JSON editing for advanced users.
- Attempting to delete a template with assigned cables shows a warning; deletion is blocked until all are unassigned.

### 8.2 Cable Edit Form (when `breakout_template` is assigned)

- Selecting a `BreakoutTemplate` from the dropdown dynamically renders connector-level termination pickers via HTMX.
- The lane form shows a two-column table: A-side on the left, B-side on the right, with `rowspan` grouping connectors.
- Each connector row has a type selector, parent picker (device/circuit/power panel), and termination picker. Changing the type selector dynamically swaps the parent and termination picker fields via HTMX.
- All termination types are supported: Interface, FrontPort, RearPort, CircuitTermination, ConsolePort, ConsoleServerPort, PowerPort, PowerOutlet, PowerFeed.
- Breakout templates can only be assigned to cables with compatible termination types (interface, front port, rear port, circuit termination). The template field is disabled if the cable has incompatible termination types.

### 8.3 Cable Detail View (when `breakout_template` is assigned)

- A two-column **connections table**: Side A on the left, Side B on the right. Connectors with fewer counterparts use `rowspan` to visually group related connections. Type icons and parent/termination links are shown for each connector.
- A **lane mapping SVG diagram** below the connections table. Connected nodes are green, unconnected nodes are gray.
- `connected_lanes / total_lanes` is shown as a utilization fraction (e.g. "3 / 4 lanes connected") alongside the template name.

### 8.4 Cable Create Form (Connect View)

The cable create form (triggered from the "Connect" button on interface/port detail views) pre-populates the A-side termination from the URL context. The B-side is chosen via the form. For new cables that have not yet been saved, the A-side context is resolved from the URL parameters rather than from the database.

### 8.5 Cable List View
- A `breakout_template` column is available via Configure Table, showing the template name (linked) or "—".
- The list view supports filtering by `breakout_template` (assigned / not assigned / specific template).
- Multi-termination columns show type icons, parent/termination links, and connector.position annotations for breakout cables.

### 8.6 Cable Trace View
- The cable trace SVG is rendered in a left-panel card ("Cable Trace"), with "Related Paths" in a right-panel card.
- The SVG shows breakout fan-outs as a fork from the trunk, with each leg rendered in its own column.
- Multi-hop paths through patch panels (including multi-position rear ports for MPO trunks) are fully rendered at arbitrary depth.
- Same-device terminations at the same trace depth are grouped into shared device boxes with side-by-side termination sub-boxes.

### 8.7 Disconnect Behavior

Disconnecting a cable termination removes the endpoint join table row **without** deleting the Cable. The user is informed that the cable was not deleted and provided a link to the cable.

### 8.8 Diagram Shared Requirements
- All fan-out diagrams (BreakoutTemplate detail and Cable detail) are rendered as server-side SVGs.
- Termination object labels on diagrams are clickable links to the relevant object.
- Lane numbers are shown on the diagram connecting lines.

---

## 9. API Considerations

- Full REST API CRUD for `BreakoutTemplate` at `/api/dcim/breakout-templates/`.
- `breakout_template` field exposed as a nested object on `Cable` create, update, and filter operations.
- `CableTerminationEndpoint` objects expose `connector` and `position` as **read-only** fields. These cannot be set directly via the API — they are derived from the cable's template.
- `Cable.termination_a` and `Cable.termination_b` backward-compatible properties are available in the API response.
- The cable trace REST endpoint returns `lane`, `connector`, and `position` at each breakout cable hop.
- `Cable` list endpoint supports `?breakout_template=<id>` and `?breakout_template__isnull=true/false` filters.
- Backward-compatible `?termination_a_type=` and `?termination_b_type=` filters query the join table by `cable_end`.
- GraphQL schema extended with `BreakoutTemplate` type on Cable and terminations relation on `CableTerminationEndpoint`.
- `BreakoutTemplate` supports CSV import for bulk creation.

---

## 10. Migration & Backward Compatibility

- `Cable.breakout_template` is nullable; all existing cable records default to `null`. No data migration required for this field.
- The existing GFK fields on Cable are replaced by `CableTerminationEndpoint` rows via a data migration that copies existing termination references into the join table, then removes the old fields.
- `Cable.termination_a` and `Cable.termination_b` become read-only properties querying the join table. All existing API consumers, path traces, and UI views are unaffected.
- The `Cable(termination_a=obj, termination_b=obj)` creation pattern continues to work — the constructor captures these kwargs and the post-save hook creates the corresponding join table rows.
- `CableTerminationEndpoint.connector` and `CableTerminationEndpoint.position` are nullable; all existing records default to `null`.
- The abstract `CableTermination` mixin retains its original name. The concrete join table is named `CableTerminationEndpoint` to avoid collision.
- Filter names `termination_a_type` and `termination_b_type` continue to work, querying via the join table.
- All existing cables with no template assigned trace identically to before this feature.
- Any code that assumes `Cable` has exactly one A-side and one B-side termination must be audited and updated to handle the multi-termination case. Known locations: cable forms, cable trace renderer, cable path signal handlers, cable serializers.
- Default breakout templates (9 total) are shipped via a data migration using idempotent `get_or_create` to avoid duplicates on re-run.

---

## 11. Acceptance Criteria

- A user can create a `BreakoutTemplate` with a valid mapping and it appears in DCIM > Breakout Templates.
- Creating a `BreakoutTemplate` with duplicate A-side or B-side `(connector, position)` pairs raises a validation error.
- `total_strands` on a template detail view correctly reflects `total_lanes × strands_per_lane`.
- The `polarity_method` field is visible on the create/edit form only when `strands_per_lane >= 2`; it is hidden when `strands_per_lane = 1`.
- A template with `strands_per_lane = 2` and `polarity_method = straight-through` saves correctly and displays both values on the detail view.
- The breakout template create/edit form auto-generates the lane mapping from connector and position counts. A table editor allows per-lane customization, and a "JSON" toggle allows raw JSON editing for advanced users.
- The breakout template detail view shows a lane mapping SVG diagram with A-side connectors on the left, B-side connectors on the right, and lines connecting mapped lanes.
- A breakout template that has one or more cables assigned cannot be deleted.
- 9 default breakout templates are available out of the box after migration.
- When a user selects a `BreakoutTemplate` on the cable edit form, the form dynamically renders connector rows for each side via HTMX. Each connector row has a type selector, parent picker, and termination picker.
- The cable edit form supports all termination types (Interface, FrontPort, RearPort, CircuitTermination, ConsolePort, ConsoleServerPort, PowerPort, PowerOutlet, PowerFeed) via a centralized termination field factory. Each side's type selector dynamically swaps the parent and termination picker fields via HTMX.
- Breakout templates can only be assigned to cables with compatible termination types: interface, front port, rear port, or circuit termination. Assigning to power or console cables raises a validation error.
- The cable detail view shows a two-column connections table: Side A on the left, Side B on the right. Connectors with fewer counterparts use `rowspan` to visually group related connections. Type icons and parent/termination links are shown for each connector.
- The cable detail view shows a lane mapping SVG diagram below the connections table for breakout cables. Connected nodes are green, unconnected nodes are gray.
- The cable list view shows multi-termination columns with type icons, parent/termination links, and connector.position annotations for breakout cables.
- The cable trace view renders an SVG showing breakout fan-outs as a fork from the trunk, with each leg in its own column. Multi-hop paths through patch panels (including multi-position rear ports for MPO trunk cables) are rendered at arbitrary depth.
- Same-device terminations at the same trace depth are grouped into shared device boxes with side-by-side termination sub-boxes. Row heights are consistent — all cells at the same depth align horizontally.
- Tracing a path from a B-side termination resolves to the correct A-side termination via the template mapping using the join table.
- Tracing into an unconnected lane halts the path (destination is null, `is_active` is false).
- All existing cables with no template assigned trace identically to before this feature (regression test).
- A cable with `breakout_template=null` uses exactly one join table row per side (A and B).
- A cable with a `breakout_template` assigned uses one join table row per connector per side, with `connector` and `position` fields populated from the template mapping.
- `Cable.termination_a` and `Cable.termination_b` backward-compatible read-only properties work for both standard and breakout cables.
- `Cable(termination_a=obj, termination_b=obj)` creation pattern continues to work — the post-save hook creates the corresponding join table rows.
- Disconnecting a cable termination (deleting the termination object or using bulk disconnect) removes the join table row without deleting the Cable. The user is informed and provided a link to the cable.
- The API filter `?termination_a_type=` and `?termination_b_type=` are backward compatible, filtering via the join table by `cable_end`.
- `?breakout_template=` filter works on the cable list endpoint.
- `BreakoutTemplate` and `CableTerminationEndpoint` fields are accessible via REST API and GraphQL with correct filtering.
- `BreakoutTemplate` supports standard Nautobot features: tags, custom fields, change logging.
- A management command generates demo data covering: breakout cables (1×4, 40G→4×10G, partial, planned, mixed-type with Interface + FrontPort + RearPort + CircuitTermination), multi-trunk fanouts (2×4→8×1, 4×1→1×4, 8×1→2×4), complex multi-hop paths (breakout → patch panel → MPO trunk → patch panel → devices), standard cables, patch panel pass-through, circuit termination, power, and console cables.
