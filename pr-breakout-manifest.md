# Performance series — PR breakout manifest

One-stop index of the performance series as it stands on the `vibed-api-ui-improvements` branch: 38 commits in
8 PRs, each PR reviewable on its own.

Merge order is the PR number order. PR 1 merges first because PR 2's optimizer reads
`natural_key_field_lookups` per nested model while building prefetches — without PR 1's caches that
is a per-request config read — and pure memoization is the cheapest first review.

| PR | Branch | Theme |
|---|---|---|
| 1 | `pr1-api-caching` | Behavior-preserving memoization of per-object recomputation |
| 2 | `pr2-api-generic` | The automatic REST queryset optimizer: prefetch strategy, all depths, GFKs |
| 3 | `pr3-api-targeted` | Per-model N+1 fixes the optimizer can't see |
| 4 | `pr4-api-behavioral` | URL route-shape memoization + the `NATURAL_SLUG_ENABLED` setting |
| 5 | `pr5-ui-views` | View-scoped prefetches for two hot UI pages |
| 6 | `pr6-ui-basetable` | Generic table mechanisms (BaseTable + column classes) |
| 7 | `pr7-ui-tables` | Per-table fixes built on the PR 6 mechanisms |
| 8 | `pr8-cabling` | Cable-peer/termination prefetching, API depth≥1 and UI tables |

## PR 1 — API | Caching (`pr1-api-caching`)

| Hash | Commit | What it does | Bench |
|---|---|---|---|
| `6d2582b93` | API \| Caching \| 1 | Cache `natural_key_field_lookups` per concrete model class; invalidated on tree-shape change, `LOCATION_NAME_AS_NATURAL_KEY`, `DEVICE_UNIQUENESS` | `pr1c1` |
| `08af89a00` | API \| Caching \| 2 | Compute `natural_slug` once per object (eager `getattr` default ran it twice) | `pr1c2` |
| `089ee666a` | API \| Caching \| 3 | `Location.natural_key_field_lookups` override uses the same cache — kills a per-nested-object config read at `?depth≥1` | `pr1c3` |
| `e81c233b8` | API \| Caching \| 4 | Memoize `custom_field_keys` per serializer field instance — one cache GET per request, not per object | `pr1c4` |
| `56f4e299f` | API \| Caching \| 5 | Opt-in `get_settings_or_config_memoized()`, signal-invalidated; applied to `Location.display` and `NETWORK_DRIVERS` reads | `pr1c5` |
| `fd584db6a` | API \| Caching \| 6 | `ProcessTTLCache` in-process memo at the three remaining per-object cache-GET sites (`keys_for_model`, `get_celery_queues`, `TreeModel.display`); cleared per test | `pr1c6` |

## PR 2 — API | Generic (`pr2-api-generic`)

| Hash | Commit | What it does | Bench |
|---|---|---|---|
| `2faf6adad` | API \| Generic \| 1 | Optimizer prefetches FK serializer fields at depth 0 instead of JOINing (Device 266→57 ms) and covers all requested nesting depths with prefixed prefetches (circuits `?depth=1`: 2,063→23 queries) | `pr2c1` |
| `d14c9fe57` | API \| Generic \| 2 | Optimizer prefetches every `GenericForeignKey` on the model — association endpoints drop 2 q/row → 0; covers app-defined models | `pr2c2` |

## PR 3 — API | Targeted (`pr3-api-targeted`)

| Hash | Commit | What it does | Bench |
|---|---|---|---|
| `036404a90` | API \| Targeted \| 1 | Device `parent_bay` reverse one-to-one `select_related` | `pr3c1` |
| `26222c5fd` | API \| Targeted \| 2 | FrontPort/RearPort get the cable-peer prefetch Interfaces already had | `pr3c2` |
| `c4dfe22a8` | API \| Targeted \| 3 | `Job.task_queues` honors prefetch; UserSavedViewAssociation `saved_view__owner` chain | `pr3c3` |

## PR 4 — API | Behavioral (`pr4-api-behavioral`)

| Hash | Commit | What it does | Bench |
|---|---|---|---|
| `68920cacc` | API \| Behavioral \| 1 | Sentinel-pk memo of hyperlinked-field and `notes_url` route shapes — `reverse()` once per view per request (105→6 on a 100-row page) | `pr4c1` |
| `26e6dd995` | API \| Behavioral \| 2 | Same pattern for `BaseModel.get_absolute_url()` and dynamic form field data-urls | `pr4c2` |
| `a714d9267` | API \| Behavioral \| 3 | `NATURAL_SLUG_ENABLED` settings-only opt-out (default on); pins it on in the test-runner config | `pr4c3` |

## PR 5 — UI | Views (`pr5-ui-views`)

| Hash | Commit | What it does | Bench |
|---|---|---|---|
| `5082f4a10` | UI \| Views \| 1 | Device LLDP neighbors tab prefetches connected endpoints (224→54 queries) | `ui-pr5c1` |
| `bb09ebf60` | UI \| Views \| 2 | Changelog views prefetch the `changed_object` GFK (98→52) | `ui-pr5c2` |

## PR 6 — UI | BaseTable (`pr6-ui-basetable`)

| Hash | Commit | What it does | Bench |
|---|---|---|---|
| `c3fb5aee0` | UI \| BaseTable \| 1 | Accessor walk no longer drops to-many segments behind FK segments (silent optimization loss) | `ui-pr6c1` |
| `34e8d3c61` | UI \| BaseTable \| 2 | Explicit `columns=` kwarg — programmatic column selection, enables per-column tooling/tests | `ui-pr6c2` |
| `bb3255f01` | UI \| BaseTable \| 3 | ContentTypesColumn sorts in Python so `.order_by()` doesn't discard the prefetch cache | `ui-pr6c3` |
| `054c7009b` | UI \| BaseTable \| 4 | Prefetch both relationship-association generic relations when any relationship column is visible | `ui-pr6c4` |
| `41e69ca83` | UI \| BaseTable \| 5 | RelationshipColumn compares by ID and batch-prefetches association peers (stale-ContentType fallback included) | `ui-pr6c5` |
| `5c40c77d5` | UI \| BaseTable \| 6 | `display_prefetch_related` model convention — models declare what their `display` reads; BaseTable prefetches it for own and related models | `ui-pr6c6` |
| `06276a82e` | UI \| BaseTable \| 7 | LinkedCountColumn hover-sample honors `display_prefetch_related` | `ui-pr6c7` |
| `867cb152e` | UI \| BaseTable \| 8 | Public `replace_queryset()` helper for post-init queryset swaps (consumed by PRs 7/8) | `ui-pr6c8` |

## PR 7 — UI | Tables (`pr7-ui-tables`)

| Hash | Commit | What it does | Bench |
|---|---|---|---|
| `f047b8d47` | UI \| Tables \| 1 | Prefix hierarchy lookups batched per page; injected "available" rows carry real-row prefetches (Prefixes tab 264→60) | `ui-pr7c1` |
| `9c6431d23` | UI \| Tables \| 2 | Device tables prefetch `primary_ip` (property over two FKs) when visible | `ui-pr7c2` |
| `ecdfdf4ea` | UI \| Tables \| 3 | Location tree-link uses annotated `tree_depth` + one batched children lookup (LocationType detail 155→59) | `ui-pr7c3` |
| `4eab9c8d0` | UI \| Tables \| 4 | `display_prefetch_related` declarations for circuits/ipam/load-balancers/software models | `ui-pr7c4` |
| `c5d3cd136` | UI \| Tables \| 5 | Interface IP columns prefetch the parent namespace chain | `ui-pr7c5` |
| `ba5cbadaa` | UI \| Tables \| 6 | Extras tables join per-row FK/GFK reads (job results, object changes, webhooks) | `ui-pr7c6` |
| `fd0aa7b4e` | UI \| Tables \| 7 | Parent objects read by name links/properties are joined in | `ui-pr7c7` |
| `b28f73e43` | UI \| Tables \| 8 | Action buttons stop issuing per-row queries | `ui-pr7c8` |
| `cafdbbe7f` | UI \| Tables \| 9 | JobTable batch-prefetches each job's latest result | `ui-pr7c9` |
| `f2d45ff6b` | UI \| Tables \| 10 | PowerFeed/Rack utilization columns prefetch their inputs | `ui-pr7c10` |

## PR 8 — Cabling (`pr8-cabling`)

| Hash | Commit | What it does | Bench |
|---|---|---|---|
| `61e2fffef` | Cabling \| 1 | `for_nested_serialization` flavor of the cable-peer/connected-endpoint prefetches — API `?depth≥1` (interfaces 0.84→0.34 q/row) | `pr8c1` / `ui-pr8c1` |
| `7c3a785ee` | Cabling \| 2 | CableTerminationTable self-applies cable-column optimizations — the whole port-table family (table audit 247→19 offenders) | `pr8c2` / `ui-pr8c2` |
| `375835e6b` | Cabling \| 3 | Connection columns prefetch far-end parent devices (audit →14) | `pr8c3` / `ui-pr8c3` |
| `bbe6061ee` | Cabling \| 4 | CableTable self-applies the same optimizations (audit →8, the documented design-discussion leftovers) | `pr8c4` / `ui-pr8c4` |

## Validation (2026-07-26, dev DB: 1,210 devices / 24,462 interfaces)

- Per-PR test suites: green.
- `-k test_list_objects` sweep (every model's list view): 2,827 tests OK.
- `-k test_get_object_with_permission` sweep (every detail view): 115/116 — the one failure is a
  pre-existing shared-Redis `TreeModel.display` TTL timing flake that fails identically on the
  pre-breakout branch and passes in isolation.
- Full `nautobot.core` + `nautobot.extras.tests.test_api`: 2,289 tests OK.
- Table-column audit (183 tables × 1,757 columns): 8 remaining offenders, all documented
  design-discussion items (DynamicGroup member counts ×4, `JobTable.source_version`,
  PowerFeed/Rack power utilization, PrefixDetail utilization).
