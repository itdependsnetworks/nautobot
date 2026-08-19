# Relationship retrieval — cumulative progress

One row per surface, one column pair per step, so each step's contribution is visible on its own. Baseline detail
and query plans are in [`relationships_pr1_baseline.md`](./relationships_pr1_baseline.md).

`q` = query count (comparable across machines). `db` = milliseconds inside the database driver (comparable only
against other numbers in this file).

## PR 2 — object-centric association loader

`RelationshipAssociationLoader` retrieves all associations in two queries, one per endpoint side, and groups them
in memory. `get_relationships()` delegates to it and returns already-evaluated querysets.

| Surface | Scenario | q before | q after | db before | db after |
|---|---|---|---|---|---|
| `get_relationships` | S0, D=5 | 5 | **2** | 0.51 | 0.43 |
| `get_relationships` | S0, D=25 | 25 | **2** | 2.01 | 0.71 |
| `get_relationships` | S1 | 29 | **5** | 3.62 | 0.84 |
| `get_relationships` | S2 | 109 | **5** | 12.11 | 2.93 |
| `get_relationships` | S3 | 29 | **5** | 14.47 | 9.30 |
| `get_relationships_data` | S1 | 37 | **13** | 4.80 | 2.11 |
| `get_relationships_data` | S2 | 117 | **13** | 27.78 | 4.42 |
| `get_relationships_data` | S3 | 37 | **13** | 6.25 | 9.93 |
| `rest_retrieve` | S1 | 237 | **212** | 39.61 | 22.39 |
| `rest_list` (10 objects) | S1 | 280 | **60** | 43.56 | 14.77 |
| `form_render` | S1 | 229 | **219** | 27.24 | 21.65 |
| `detail_render_both_tabs` | S1 | 34 | 34 | 9.24 | 6.26 |
| `detail_render_both_tabs` | S3 | 30 | 30 | 1934 | 1955 |
| `list_table` | S1 | 2183 | 2183 | 215 | 249 |
| `graphql_batch` | S4 | 309 | 309 | 32.6 | 50.4 |

### What moved, and what did not

**Definition-count scaling is gone.** The S0 sweep is flat at 2 queries from 5 definitions to 25, where it was
previously 5 and 25. This satisfies TRD acceptance criterion 1, and the sweep test now asserts flatness rather than
characterizing growth.

**`detail_render_both_tabs`, `list_table`, and `graphql_batch` are deliberately unchanged.** They are not migrated
in this step:

- `get_relationships_with_related_objects()`, which the detail panels use, does not go through the loader yet. It
  currently issues one reverse-generic-join per definition and returns peer objects directly, so migrating it
  before bulk peer resolution exists would replace `D` join queries with `2 + 2A` generic-foreign-key lookups and
  make it worse. This is a deviation from the original plan, which had PR 2 migrating both reader helpers;
  measurement says the peer work has to land first. It moves to PR 3.
- List tables and GraphQL are PR 4.

**One accepted regression.** `get_relationships_data` at S3 costs 9.93 ms of database time against a 6.25 ms
baseline, in exchange for 37 queries becoming 13. The legacy path only ever counted association rows for
many-valued relationships, using cheap `COUNT` aggregates; the loader fetches the rows because callers that need
peers need the rows themselves. At 10,000 associations that is 3.7 ms. Recorded rather than hidden.

**An optimization found by measuring.** The loader initially used
`select_related("relationship", "source_type", "destination_type")`, which cost real time once an object had
thousands of associations: `get_relationships` at S3 measured 24.78 ms, worse than the 14.47 ms baseline. The
`Relationship` objects are already in hand from the definition cache, so they are now attached to each row
directly and no join is issued. That single change took S3 from 24.78 ms to 9.30 ms, and S2's detail render from
56.3 ms to 37.9 ms.

## PR 3 — bulk peer resolution

Peers are resolved with one query per distinct peer content type and attached to both endpoints' foreign key
caches, so `RelationshipAssociation.get_peer()` no longer queries. `get_relationships_with_related_objects()` now
goes through the loader, replacing one reverse-generic-join-with-`DISTINCT` per definition.

| Surface | Scenario | q before | q PR2 | q PR3 | db before | db PR2 | db PR3 |
|---|---|---|---|---|---|---|---|
| `detail_render_both_tabs` | S1 | 34 | 34 | **9** | 9.24 | 6.26 | **2.12** |
| `detail_render_both_tabs` | S2 | 110 | 110 | **9** | 40.54 | 37.94 | **2.65** |
| `detail_render_both_tabs` | S3 | 30 | 30 | **16** | 1934 | 1955 | **23.4** |
| `rest_retrieve` | S1 | 237 | 212 | **16** | 39.61 | 22.39 | **3.40** |
| `rest_list` (10 objects) | S1 | 280 | 60 | **60** | 43.56 | 14.77 | 12.41 |
| `get_relationships_data` | S1 | 37 | 13 | **9** | 4.80 | 2.11 | 2.23 |
| `get_relationships_data` | S2 | 117 | 13 | **9** | 27.78 | 4.42 | 2.78 |
| `get_relationships_data` | S3 | 37 | 13 | 16 | 6.25 | 9.93 | 22.2 |
| `get_relationships` | S1 | 29 | 5 | 9 | 3.62 | 0.84 | 1.79 |
| `get_relationships` | S3 | 29 | 5 | 16 | 14.47 | 9.30 | 22.4 |
| `form_render` | S1 | 229 | 219 | 215 | 27.24 | 21.65 | 25.24 |
| `list_table` | S1 | 2183 | 2183 | 2183 | 215 | 249 | 189 |
| `graphql_batch` | S4 | 309 | 309 | 309 | 32.6 | 50.4 | 35.4 |

### The headline

**The detail render at 10,000 associations went from 1,934 ms to 23.4 ms of database time, an 83-fold reduction.**
This is the case that TRD acceptance criterion 11 was added for: query count barely moved (30 to 16), so a
query-count-only criterion would have scored the original as nearly optimal. The join-with-`DISTINCT` per
definition was the entire cost, and bulk peer resolution removes it.

REST retrieve is the second headline: 237 queries to 16, and 39.6 ms to 3.4 ms, because
`RelationshipsDataField.to_representation()` called `get_peer()` twice per association and both endpoints are now
cached.

### Why some counts went up, and why that is correct

`get_relationships` at S1 shows 5 queries at PR 2 and 9 at PR 3. Query count now grows with the number of distinct
peer content types, which TRD §6 accepts explicitly as the floor for generic relations. Going below it means the
storage redesign that §5 defers.

**`get_relationships` is no longer comparable to its own baseline**, and neither is `get_relationships_data` at S3.
Both now resolve peers, which the baseline versions did not do at all: the old code left every caller to
dereference generic foreign keys itself, at two queries per association. Measured in isolation, the method looks
more expensive; measured end to end, the caller that actually used it went from 237 queries to 16. The honest
comparison for this step is `detail_render_both_tabs` and `rest_retrieve`, which are complete operations.

### Tests inverted by this step

Two assertions in `test_relationship_performance.py` failed when PR 3 landed, which is what they were written to do:

- `test_baseline_repeated_association_queries` asserted that the repeated-query detector *fired*. It is now
  `test_no_repeated_association_queries` and asserts the opposite.
- The definition sweep's upper bound had to grow from "one query per endpoint side" to "one per endpoint side plus
  one per peer content type", for the reason above.

## PR 4a — list-view relationship columns

`BaseTable` now prefetches what `RelationshipColumn` reads, when any relationship column is visible.

| Surface | Scenario | before | after |
|---|---|---|---|
| `list_table` (1 row, 21 relationship columns) | S1 | 2,182 queries / 182 ms | **14 queries / 1.98 ms** |
| `list_table` relationship queries (50 rows) | S5 | grew with row count | **flat vs 1 row** |

### The dominant cost was not what the plan predicted

The plan attributed the 2,183 queries to the `associations` property (2 per row) plus a generic-foreign-key lookup
per association. Measurement disagreed: **2,100 of the 2,183 were `SELECT extras_relationship`**.
`RelationshipColumn.render()` compares `association.relationship` against its own definition for every association
in every column, and that foreign key was dereferenced one row at a time. Prefetching the associations with
`select_related("relationship")` is what removes the bulk of it; the peer generic foreign keys are a much smaller
term.

Both endpoints' generic foreign keys are prefetched, not just the far one, because `get_peer()` dereferences source
and destination to work out which end the caller passed.

### Verified against the same test method

The baseline measurement made its columns visible *after* constructing the table, which no real request does:
column visibility comes from user table config, which `BaseTable.__init__()` reads. The benchmark was corrected to
configure columns the way the UI does, and then re-measured with the prefetch disabled, giving 2,182 queries. So
the 2,182-to-14 improvement is attributable to the change rather than to the test being rewritten.

### What is deliberately not claimed

Total list-view query count is **not** flat with row count, and the test does not assert that it is. `LocationTable`
renders a tree hierarchy link that issues one child-existence check per row
(`SELECT 1 FROM dcim_location WHERE parent_id = ...`), so 50 rows cost 49 more queries than 1 row. That is an
unrelated N+1 in the location tree column, outside this effort's scope.
`test_relationship_query_count_is_independent_of_row_count` therefore counts only queries against relationship and
peer tables, and `test_unrelated_tree_hierarchy_queries_scale_with_rows` characterizes the excluded one so the
exclusion is documented by a test rather than only by a comment.

### Unrelated finding: form rendering

`form_render` sits at 215 queries and barely moved across PRs 2 and 3. Diagnosis: only 16 of those are association
queries. The rest are `DynamicModelChoiceField` querysets being evaluated once per relationship form field (98
against `dcim_location`, 41 `dcim_manufacturer`, 30 `circuits_circuittype`, 25 `dcim_platform`). That is form-field
construction, not relationship retrieval, and needs a separate look at `Relationship.to_form_field()`.

## PR 4b — request-scoped reuse

A load is reused within one request scope when an identical load has already happened, keyed on the model, the
objects, the definition filters, whether peers were resolved, and the permission context they were resolved under.
Writing a `RelationshipAssociation` invalidates every cached load, because association data is mutable and a cache
that outlived a write would serve stale answers.

### Honest accounting: this earns very little

| Path | Without reuse | With reuse |
|---|---|---|
| Bound form submission (reads relationships twice) | 232 queries | **223 queries** |
| Detail page, both tabs | 12 queries | 12 queries |
| REST retrieve / list, list table, GraphQL | unchanged | unchanged |

**Nine queries on one path is the entire measured benefit.** Everything else is unchanged, because nothing else
reads the same relationships twice with the same arguments in one request. The mechanism is proven by
`RequestScopedReuseTest.test_repeated_identical_call_is_free` (second read costs zero queries) rather than by any
headline surface.

It ships because it is cheap, correct, invalidated, and the effort committed to it; not because measurement
demanded it. If the staleness surface ever looks like a liability, this is the piece to remove first.

### A design that measurement rejected

The first implementation loaded a *superset* per object (every definition, ignoring `include_hidden` and
`advanced_ui`) and applied those filters when reading the result, so that the detail page's two tabs could share one
load. It was reverted:

- Only HTTP requests have a request scope. `nautobot.core.middleware` establishes it; jobs and management commands
  do not. So every non-request caller would pay to load definitions it had no interest in.
- Measured without a scope, the detail render went from 9 queries to 18, because each tab loaded the full superset.
- The upside was small even inside a scope: it replaces two cheap filtered loads with one larger load.

Load-time filtering with the filters in the cache key gives up cross-tab sharing and keeps every other path
unregressed.

### A fixture gap this exposed

While measuring the two tabs, the benchmark fixture turned out to contain **no `advanced_ui=True` definitions at
all**, so every detail-render measurement in PRs 1 through 4a exercised only the main tab, and the Advanced tab
looked free. The fixture now includes one, which is why `detail_render_both_tabs` at S1 reads 12 queries here
against 9 at PR 3: the Advanced tab is finally doing work. `RelationshipBenchmarkFixtureTest.test_advanced_ui_definitions_exist`
prevents the gap from reopening.

## Cumulative: baseline to now

| Surface | Scenario | Baseline q | Now q | Baseline db | Now db |
|---|---|---|---|---|---|
| `get_relationships` | S1 | 29 | **9** | 3.62 | 1.04 |
| `get_relationships` | S2 | 109 | **9** | 12.11 | 2.01 |
| `get_relationships_data` | S1 | 37 | **9** | 4.80 | 1.93 |
| `get_relationships_data` | S2 | 117 | **9** | 27.78 | 2.00 |
| `detail_render_both_tabs` | S1 | 34 | **12** | 9.24 | 1.34 |
| `detail_render_both_tabs` | S2 | 110 | **9** | 40.54 | 2.13 |
| `detail_render_both_tabs` | S3 | 30 | **16** | **1934** | **24.6** |
| `rest_retrieve` | S1 | 237 | **16** | 39.61 | 2.90 |
| `rest_list` (10 objects) | S1 | 280 | **60** | 43.56 | 10.43 |
| `list_table` (1 row) | S1 | 2183 | **14** | 215 | 2.03 |
| `form_render` | S1 | 229 | 213 | 27.24 | 20.16 |
| `graphql_batch` (100 nodes) | S4 | 309 | 309 | 32.6 | 36.1 |

Two surfaces remain unimproved, both for documented reasons: `graphql_batch` (see below) and `form_render`, whose
cost is `DynamicModelChoiceField` construction rather than relationship retrieval.

## GraphQL: why no DataLoader

GraphQL is a demonstrated hotspot at 309 queries for 100 nodes, and the effort's design called for a request-scoped
DataLoader keyed by `(content_type_id, object_id)`. It is **not** built, for a structural reason rather than an
oversight:

Batching requires a resolver to return a pending value that the executor resolves later. Nautobot runs graphene 3 on
graphql-core 3, executed synchronously (`nautobot.core.graphql.execute_query` calls `graphql.execute` and uses the
result directly). graphql-core 3 dropped `promise`-style deferred values in favour of awaitables, so a DataLoader
would require the whole GraphQL execution path, and the view that calls it, to become async. That is a change to
Nautobot's request handling, not to relationship retrieval.

The obvious smaller step does not help either: using the loader per node costs `2 + C` queries for that node
regardless of how many relationship fields are selected, which is *worse* than the current 3 per relationship field
whenever a query selects only a few. It would only pay off for queries selecting many relationship fields per node.

Recommendation: treat GraphQL relationship batching as its own effort, gated on whether Nautobot's GraphQL execution
moves to async.

## PR 5 — applicability-filter optimization: closed with no further work

The effort's last step was conditional on profiling showing material value. It does not, because the work already
happened: the loader owns applicability, and memoizes each side filter by its dict, so four filtered definitions
sharing two distinct dicts cost two queries rather than four. Batching across objects is also already there, since
the filter query is evaluated against `pk__in=<all objects>`.

Measured at 20 definitions: **two of twelve queries** are filter evaluation, and both are irreducible short of
persisting filter results, which is out of scope. `LoaderQueryCountTest.test_filter_evaluation_costs_one_query_per_distinct_filter`
asserts the behavior, and the fixture carries four filtered definitions across two distinct dicts specifically so
that "one per distinct filter" can be told apart from "one in total".

## Controlled before/after

The per-PR tables above compare each step against the measurement before it, but the fixture grew as gaps in it were
found (an `advanced_ui` definition in PR 4b, a second distinct filter dict in PR 5), so the original PR 1 baseline is
no longer a controlled comparison against the final state. This table fixes that: the pre-loader production code was
checked out with **today's** fixture and re-measured, so both columns describe identical data.

| Surface | Scenario | Before q | After q | Factor | Before db | After db |
|---|---|---|---|---|---|---|
| `get_relationships` | S1 | 32 | 12 | 2.7x | 2.94 | 1.44 |
| `get_relationships` | S2 | 112 | 12 | **9.3x** | 11.37 | 3.09 |
| `get_relationships` | S3 | 32 | 19 | 1.7x | 14.56 | 24.53 |
| `get_relationships_data` | S1 | 40 | 12 | 3.3x | 3.65 | 1.61 |
| `get_relationships_data` | S2 | 120 | 12 | **10.0x** | 9.82 | 2.85 |
| `get_relationships_data` | S3 | 40 | 19 | 2.1x | 7.70 | 24.29 |
| `detail_render_both_tabs` | S1 | 37 | 15 | 2.5x | 8.30 | 2.21 |
| `detail_render_both_tabs` | S2 | 113 | 12 | **9.4x** | 32.69 | 2.77 |
| `detail_render_both_tabs` | S3 | 33 | 19 | 1.7x | **2546** | **24.0** |
| `rest_retrieve` | S1 | 240 | 19 | **12.6x** | 23.79 | 4.91 |
| `rest_list` (10 objects) | S1 | 300 | 90 | 3.3x | 31.36 | 17.65 |
| `list_table` (1 row) | S1 | 2182 | 13 | **168x** | 182.38 | 1.74 |
| `form_render` | S1 | 230 | 216 | 1.1x | 28.03 | 21.04 |
| `graphql_batch` (100 nodes) | S4 | 309 | 309 | 1.0x | 31.77 | 35.20 |

Reproduce by checking out the production files from commit `b7617ce8d` (PR 1) while keeping the current test files,
then running the benchmark; five assertions fail against the old code, which is expected, and measurements are still
recorded because `measure()` records before it asserts.

### The two honest negatives

**`get_relationships` and `get_relationships_data` cost more database time at S3** (10,000 associations): 24.5 ms
against 14.6 ms, and 24.3 ms against 7.7 ms. Both now resolve peers, which the old versions did not do at all; the
old code left each caller to dereference generic foreign keys itself at two queries per association. The end-to-end
callers are what improved: `rest_retrieve` went 240 queries to 19, and `detail_render_both_tabs` at the same size
went from 2,546 ms to 24 ms.

**`form_render` barely moved and `graphql_batch` did not move.** Form rendering is dominated by
`DynamicModelChoiceField` construction, not relationship retrieval (only 16 of its queries are association queries).
GraphQL needs async execution before batching is possible; see the section above.

## Follow-up: the form path was never actually unimproved

`form_render` was reported through PRs 2 to 5 as barely moved (230 to 216 queries), attributed to
`DynamicModelChoiceField` construction rather than relationship retrieval. **That attribution was wrong.**
`Relationship.to_form_field()` measured on its own issues **zero** queries. The cost was relationship retrieval the
whole time, caused by one call:

```python
initial = [association.get_peer(self.instance) for association in queryset.all()]
```

`get_relationships()` returns querysets whose results are already loaded and whose associations carry populated peer
caches. `.all()` clones, and a clone drops both, so every association fell back to the two-query `get_peer()` path
this effort exists to remove. Iterating the queryset directly instead:

| Surface | Before | After | Factor |
|---|---|---|---|
| `form_render` | 230 q / 28.0 ms | **14 q / 1.93 ms** | **16x** |
| Bound form submission | 252 q | **24 q** | 10x |

This was unfinished PR 4 work: the plan listed migrating `_append_relationships()` and it had been skipped because
the surface looked unrelated.

The general hazard is now documented on `evaluated_queryset()` and covered by
`EvaluatedQuerysetCloneHazardTest`, which asserts that direct iteration costs nothing and characterizes what
cloning costs, so a future `.all()` shows up as a test failure rather than as a silent regression.

## Measured: are the standalone endpoint-id indexes now redundant?

The new composite indexes cover `(source_type, source_id, relationship)` and its destination equivalent, so the
question was whether the pre-existing single-column indexes on `source_id` and `destination_id` still earn their
write cost. **They do. Keep them.**

A composite index cannot serve a predicate on `source_id` alone, because `source_id` is not its leading column.
Several real queries filter on the bare endpoint id without its content type: `RelationshipAssociation.clean()`'s
cardinality checks, the form mixin's `exclude(**{f"{side}_id": ...})`, and the uninstalled-App count path. Measured
on 41,508 association rows:

| Query | With standalone indexes | Without |
|---|---|---|
| `WHERE source_id = ?` | Bitmap Index Scan, **0.036 ms** | Seq Scan, **1.297 ms** (36x slower) |
| `WHERE destination_id = ?` | Bitmap Index Scan, **0.025 ms** | Seq Scan, **0.924 ms** (37x slower) |
| `WHERE source_type_id = ? AND source_id = ?` | Index Scan on the composite, 0.018 ms | unchanged, 0.012 ms |
| Table + indexes total | 24 MB | 22 MB |

Usage counts settle it. Over the benchmark run, `extras_relationshipassociation_source_id_cb8931c1` took **1,529
index scans** against 64 for the new `relassoc_src_obj_rel_idx`: the single-column index is the busiest on the
table, not a legacy leftover. Dropping both would save about 1.9 MB per 41,500 rows and convert the hottest access
path into a sequential scan.

Reproduce by generating S3 plus three `--scenario S4 --objects 500` runs, then dropping and recreating
`extras_relationshipassociation_source_id_cb8931c1` and `extras_relationshipassociation_destination_id_83f811cb`
around an `EXPLAIN (ANALYZE, BUFFERS)` pass.

## Implemented: caching the required-relationship lookup

`Relationship.objects.get_required_for_model()` was the one definition lookup with no cache, while its
`get_for_model_source()` / `get_for_model_destination()` siblings have had one for some time. It runs from
`required_related_objects_errors()`, which means every form validation and every API create or update paid a query
for it. It is now cached the same way, invalidated by the same signal, and offers the same `get_queryset=False`
list form.

Both call sites use the list form, because the form mixin filtered the result with `.exclude(key__in=...)` and
filtering a cached queryset clones it, re-queries, and defeats the cache. That filter is now applied in Python.

## Reproducing

```bash
NAUTOBOT_RELATIONSHIP_BENCH_FULL=True \
NAUTOBOT_RELATIONSHIP_BENCH_OUT=perf_runs/relationships_pr<N>.jsonl \
  invoke tests --skip-docs-build --label nautobot.extras.tests.test_relationship_performance
```
