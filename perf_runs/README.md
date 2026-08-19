# Performance measurement records

Committed evidence for performance work, so that a claimed improvement can be checked against the numbers it was
measured from rather than taken on trust.

| File | What it records |
|---|---|
| `relationships_pr1_baseline.md` | Relationship retrieval baseline (PR 1 of the performant-custom-relationships effort), plus the index query plans |
| `relationships_pr1_baseline.jsonl` | Raw measurements behind that report, one JSON object per surface/scenario |

## Regenerating

```bash
NAUTOBOT_RELATIONSHIP_BENCH_OUT=perf_runs/relationships_pr<N>.jsonl \
  invoke tests --skip-docs-build --label nautobot.extras.tests.test_relationship_performance

# Add the large-scale scenarios (S2, S3), which are skipped by default:
NAUTOBOT_RELATIONSHIP_BENCH_FULL=True \
NAUTOBOT_RELATIONSHIP_BENCH_OUT=perf_runs/relationships_pr<N>.jsonl \
  invoke tests --skip-docs-build --label nautobot.extras.tests.test_relationship_performance
```

Render a Markdown table from any `.jsonl` in this directory with
`nautobot.extras.tests.relationship_fixtures.format_bench_table()`.

## Reading these numbers

Query counts are reproducible: they are a property of the code and the data shape, so they can be compared across
machines and across commits. Wall and database timings are not - they come from whatever machine happened to run
them, under a development configuration with `DEBUG` and query capture active. **Compare timings only against other
timings in the same file**, and treat query count as the metric that travels.
