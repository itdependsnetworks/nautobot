# Breakout Cable Feature — Manual QA Test Plan

## 1. BreakoutTemplate CRUD

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 1.1 | Create template | DCIM > Breakout Templates > Add. Fill in name, connectors, positions. | Template created, mapping auto-generated, appears in list. |
| 1.2 | Mapping auto-generation | Change connector/position counts on create form. | Lane mapping table refreshes via HTMX with correct lane count. |
| 1.3 | Table editor | Edit individual lane selects in the table editor. | Values persist on save. |
| 1.4 | JSON toggle | Switch to JSON mode, edit, switch back to table mode. | Data round-trips correctly. |
| 1.5 | Validation error on bad mapping | Submit with duplicate (connector, position) pairs. | Error message displayed on the mapping field. |
| 1.6 | Delete protection | Try to delete a template assigned to a cable. | Blocked with error listing assigned cables. |
| 1.7 | SVG diagram on detail | View a template's detail page. | Lane mapping SVG diagram shows on right panel with A-to-B connector lines. |
| 1.8 | Default templates exist | Check Breakout Template list after fresh migration. | 9 default templates (4 AOC + 5 fiber MPO) present. |

## 2. Cable Edit Form — Standard Cables

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 2.1 | Edit standard cable | Edit existing interface-to-interface cable. | A-side and B-side show device + interface, saves correctly. |
| 2.2 | Change type to RearPort | On cable edit, change B-side type from Interface to RearPort. | Parent and termination pickers swap via HTMX. Device and port selectable. |
| 2.3 | Change type to FrontPort | Change B-side type to FrontPort. | FrontPort dropdown loads correctly (no 400 error). |
| 2.4 | Change type to CircuitTermination | Change B-side type to CircuitTermination. | Circuit and termination side pickers appear. |
| 2.5 | Power/console types work | Edit a power cable. | PowerPort and PowerOutlet types selectable, saves correctly. |
| 2.6 | Already-connected excluded | On termination picker, check if already-cabled interfaces are disabled. | Cabled interfaces show as disabled in dropdown. |

## 3. Cable Edit Form — Breakout Cables

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 3.1 | Assign breakout template | Edit existing cable, select a 1x4 template. | Lane form reloads via HTMX showing 1 A-side + 4 B-side connector rows. |
| 3.2 | Multiple A-side connectors | Assign a 2x4 template. | 2 A-side rows + 8 B-side rows appear. |
| 3.3 | Save breakout cable | Fill in all terminations and save. | CableTerminationEndpoint rows created, cable detail shows connections table. |
| 3.4 | Breakout eligibility | Try to assign breakout template to a power cable. | Template field disabled with help text explaining incompatibility. |
| 3.5 | Mixed termination types | Assign 1x4 template, set B-side lanes to Interface, FrontPort, RearPort, CircuitTermination. | All types save correctly, detail view shows mixed icons. |
| 3.6 | Partially connected breakout | Assign 1x4 template, only connect 2 of 4 B-side lanes. | Saves with 2 connected + 2 unconnected lanes. |
| 3.7 | Rowspan grouping on detail | Breakout cable: A has 1 connector (4 positions), B has 4 connectors (1 position each). | A-side shows rowspan=4, B-side shows 4 separate rows. |

## 4. Cable Detail View

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 4.1 | Standard cable connections | View a standard cable. | Single row: A-side left, B-side right. |
| 4.2 | Breakout cable connections | View a 1x4 breakout cable. | Multiple rows with A-side rowspan, type icons, parent/termination links. |
| 4.3 | Lane mapping SVG | View a breakout cable detail. | SVG diagram below connections table. Connected=green, unconnected=gray. |
| 4.4 | Utilization fraction | View a partially connected breakout cable. | Shows "2 / 4 lanes connected" or similar. |

## 5. Cable Create (Connect Flow)

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 5.1 | Connect from interface detail | On interface detail, click "New Cable > Interface". | Redirected to cable add form with A-side pre-populated. |
| 5.2 | A-side pre-populated | On the add form from connect flow. | A-side type=Interface, device and interface filled in. |
| 5.3 | B-side editable | Select B-side device and interface, save. | Cable created with both terminations. |
| 5.4 | Breakout on create | On the add form, select a breakout template. | Lane rows appear, can fill in multiple B-side terminations. |
| 5.5 | Cancel returns cleanly | Start cable create, click Cancel. | No orphan cable created. Returns to interface page. |
| 5.6 | Connect to existing cable | On interface detail, click "Existing Cable". | Redirected to cable list filtered by location. |
| 5.7 | RearPort B-side on create | Create cable, set B-side type to RearPort, select device + port. | Saves correctly with RearPort termination. |

## 6. Cable Disconnect

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 6.1 | Single disconnect from table dropdown | On interface table, dropdown > Disconnect. | CableTerminationEndpoint row removed. Cable survives. Success message with clickable cable link. |
| 6.2 | Single disconnect from interface detail | On interface detail, dropdown > Disconnect. | Same as 6.1. |
| 6.3 | Bulk disconnect | Select multiple interfaces, click Disconnect. | All selected disconnected. Cable(s) survive. Info messages with clickable cable links. |
| 6.4 | Peer cache cleared on disconnect | After disconnect, check the peer interface. | Peer's Cable Peer and Connection columns are empty. Row is no longer green. |
| 6.5 | Delete cable still works | On interface table, dropdown > Delete cable. | Cable deleted entirely. Both sides cleared. |
| 6.6 | Disconnect message renders HTML | After disconnect, check the Django message banner. | Cable link renders as clickable hyperlink, not raw HTML tags. |
| 6.7 | No IntegrityError on disconnect | Disconnect an interface that has a CablePath. | No FK constraint violation. Clean disconnect. |

## 7. Cable Trace SVG

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 7.1 | Linear trace — simple | Trace a standard interface-to-interface cable. | SVG: origin (interface at bottom) -> cable -> destination (interface at top). |
| 7.2 | Linear trace — through patch panel | Trace through a patch panel (FrontPort/RearPort). | Pass-through node shows FrontPort at top + RearPort at bottom, device name in between. |
| 7.3 | Linear trace — through 2 patch panels | Trace LEAF-02 Ethernet7/1 (complex path demo data). | Full path: LEAF-02 -> cable -> PATCH-02 (pass-through) -> MPO cable -> PATCH-01 (pass-through) -> breakout cable -> SPINE-01. |
| 7.4 | Fan-out trace — 1x4 | Trace trunk port of a 1x4 breakout. | Fork with 4 legs (B1-B4), each column showing destination device. |
| 7.5 | Fan-out trace — 2x4 | Trace connector 1 of a 2x4 breakout (Ethernet8/1). | Fork with 4 legs (B1-B4). |
| 7.6 | Fan-out with unconnected legs | Trace a partially connected breakout. | Connected legs show device boxes. Unconnected legs show "Unconnected" label. |
| 7.7 | Fan-out multi-hop | Trace Ethernet11/1 (complex path). | Fan-out: B1+B2 to LEAF-01, B3+B4 through PATCH-01 (pass-through) -> MPO -> PATCH-02 (pass-through) -> cables -> LEAF-02 + LEAF-03. |
| 7.8 | Same-device grouping | Fan-out where 2 legs go to the same device. | Grouped into one device box with side-by-side termination sub-boxes. |
| 7.9 | Status badge — Connected | Trace a cable with "Connected" status. | Green badge on cable segment. |
| 7.10 | Status badge — other status | Trace a cable with "Decommissioning" or "Planned" status. | Colored badge matching status color. Dashed cable bar if not Connected. |
| 7.11 | Z-order correct | Check that cable bars are behind device boxes. | No lines painting over termination or device boxes. |
| 7.12 | Row heights consistent | In fan-out, check that cells at the same depth align horizontally. | No misaligned rows between columns. |
| 7.13 | Clickable links | Click device name and interface name in SVG. | Navigate to correct object detail pages. |
| 7.14 | Connector labels on fork | Check the fork bar in a fan-out trace. | B1, B2, B3, B4 labels above each leg drop line. |
| 7.15 | Breakout template name on cable | Check the trunk cable segment in a fan-out. | Shows "Breakout: <template name>" below the cable name. |

## 8. Device Interface Table Columns

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 8.1 | Cable Peer — standard cable | Interface connected via standard cable. | Shows single peer: "Device > Interface". |
| 8.2 | Cable Peer — breakout trunk | Trunk port of a 1x4 breakout. | Shows 4 peers, one per line. |
| 8.3 | Cable Peer — breakout leg | Leaf interface connected to a breakout cable leg. | Shows single peer: the trunk port. |
| 8.4 | Connection matches Cable Peer | For all connected interfaces. | Connection column shows same peers as Cable Peer column. |
| 8.5 | Module interface shows parent | Interface on a module (not directly on device). | Parent column shows the device (resolved through module). |
| 8.6 | Green row = has cable | Check all green rows. | Every green row has a Cable value and at least one Cable Peer. |
| 8.7 | No sub-interfaces for breakout | Check SPINE-01 interfaces after demo data. | No Ethernet1/1.2, 1/1.3, 1/1.4. Only Ethernet1/1. |
| 8.8 | Icons for termination types | Check cable list columns for power, front port, rear port, circuit cables. | Correct MDI icons displayed for each termination type. |

## 9. Cable List View

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 9.1 | Breakout template column | Enable breakout_template column via Configure Table. | Shows template name (linked) or "---". |
| 9.2 | Multi-termination columns | View a breakout cable row. | A-Side and B-Side show multiple terminations with connector annotations. |
| 9.3 | Filter by breakout template | Filter cables by a specific template. | Only cables with that template shown. |
| 9.4 | Parent via .parent | Cable connecting a module interface. | Shows correct parent device name in termination column. |

## 10. API Backward Compatibility

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 10.1 | termination fields on read | GET a cable via REST API. | `termination_a_type`, `termination_a_id`, `termination_b_type`, `termination_b_id` present. |
| 10.2 | Create cable via API | POST with `termination_a_type`, `termination_a_id`, `termination_b_type`, `termination_b_id`. | Cable created with correct CableTerminationEndpoint rows. |
| 10.3 | Filter termination_a_type | GET `/api/dcim/cables/?termination_a_type=dcim.interface`. | Returns cables with A-side interfaces. |
| 10.4 | Cable(termination_a=obj) pattern | In shell: `Cable(termination_a=intf_a, termination_b=intf_b).validated_save()`. | Cable created with endpoint rows via signal handler. |
| 10.5 | Lanes in API response | GET a breakout cable via REST API. | `lanes` array present with lane, connector, position, termination data per lane. |
| 10.6 | BreakoutTemplate CRUD via API | Full CRUD at `/api/dcim/breakout-templates/`. | Create, read, update, delete all work. |
| 10.7 | GraphQL breakout fields | Query Cable with breakoutTemplate in GraphQL. | Returns template data and terminations. |

## 11. Breakout Diagram SVG

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 11.1 | Template detail diagram | View a 1x4 template detail page. | SVG: A-side node left, 4 B-side nodes right, connecting lines. All gray (no status context). |
| 11.2 | Cable detail diagram | View a 1x4 breakout cable detail page. | SVG: connected nodes green, unconnected gray. |
| 11.3 | Lane numbers on lines | Check connecting lines in the diagram. | Lane numbers displayed on lines. |
| 11.4 | Hover tooltips on cable diagram | Hover over a connected node on cable diagram SVG. | Shows device and interface name. |

## 12. Demo Data

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 12.1 | Generate demo data | Run `nautobot-server create_breakout_demo_data`. | Creates all demo objects without errors. |
| 12.2 | Flush and regenerate | Run with `--flush` flag. | Old demo data deleted, new data created cleanly. |
| 12.3 | Idempotent without flush | Run without `--flush` on existing data. | Fails gracefully (IntegrityError) — requires `--flush`. |
| 12.4 | Complex path trace works | Trace Ethernet11/1 on SPINE-01. | Full fan-out: 2 legs to LEAF-01, 2 legs through 2 patch panels to LEAF-02 + LEAF-03. |
| 12.5 | Cable peer caches populated | Check SRV-01 eth1-eth4 interfaces table. | All 4 show Cable Peer = SPINE-01 Ethernet2/1. All 4 show Connection = SPINE-01 Ethernet2/1. |
| 12.6 | All termination types covered | Verify demo data includes cables for: Interface, FrontPort, RearPort, CircuitTermination, PowerPort, PowerOutlet, PowerFeed, ConsolePort, ConsoleServerPort. | All types present in cable list. |
| 12.7 | Mixed-type breakout | View DEMO-BKO-MIXED-TYPES cable detail. | B-side lanes show Interface + FrontPort + RearPort + CircuitTermination with correct icons. |
| 12.8 | MPO trunk between patch panels | View DEMO-MPO-PATCH1-PATCH2 cable. | Single cable connecting 2 multi-position rear ports. |

## 13. Migration & Data Integrity

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 13.1 | Fresh migration | Run `nautobot-server migrate` on fresh DB. | All migrations (0084-0087) apply without errors. |
| 13.2 | Data migration from GFK | Migrate a DB with existing cables (pre-breakout). | CableTerminationEndpoint rows populated from old GFK fields. |
| 13.3 | Old GFK fields removed | After migration, check Cable model. | `termination_a_type`, `termination_a_id`, etc. are gone from DB schema. |
| 13.4 | Default templates loaded | After migration, check BreakoutTemplate table. | 9 default templates present. |
| 13.5 | Existing cables unchanged | After migration, existing cables trace correctly. | All pre-existing cable paths work identically to before. |
