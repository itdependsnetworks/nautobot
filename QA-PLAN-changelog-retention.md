# Changelog Long-Term Retention — Manual QA Test Plan

Covers [trd-changelog.md](trd-changelog.md). Acceptance criteria are TRD §8; section 16 lists behaviour that
looks like a defect and is not, so it does not get filed as one.

One row is one pass at one screen — a task a tester performs, with everything that must hold afterwards
bundled into Expected. A row fails if any part of Expected fails; note which part.

**Fixture.** Every test assumes `nautobot-server create_changelog_retention_demo_data` has been run with the
default seed unless the test says otherwise. That produces exactly:

| | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| Retained change records | 17 | 63 | 41 | 28 |
| Retained job results | 3 | 7 | 5 | 2 |

149 retained change records and 17 retained job results across 15 retention periods, 3 retention rules
(2 enabled), and two users — `retention-viewer` and `retention-archivist` — sharing the password
`retention-demo-1234` and differing only in whether they hold `extras.view_archivesegment`.

The fixture also leaves **15 warm change records** the truncation rules can act on — 7 the include rule
deletes, 3 of carol's the exclude rule saves, 5 update-action ones neither touches — plus 4 failed job
results for the third, disabled rule. These sit inside the warm window so rotation leaves them; anything
older is rotated first, which is why an age bound above the window can never match.

**The counts are deliberately unequal.** If a period total, an object's own history and the page size are all
the same number, a disagreement between them is invisible. Distrust any check where two of them coincide, and
re-run with a different `--seed`.

---

## 1. Setup and fixture data

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 1.1 | Provision on a fresh database | On a database at `extras.0145` with no `NAUTOBOT_CHANGELOG_ARCHIVE_DB_*` variables set, run `nautobot-server migrate`. Then `makemigrations --check --dry-run`. Then print `settings.DATABASES` keys. | Migration `0146_changelog_archive` applies; check says `No changes detected`; `changelog_archive` is present alongside `default` and `job_logs`. Nothing had to be provisioned separately. |
| 1.2 | Generate the fixture | Run `nautobot-server create_changelog_retention_demo_data`. | Reports per-year change records `{2022: 17, 2023: 63, 2024: 41, 2025: 28}`, `Rotated:` with 149 object changes and 17 job results, 3 rules (2 enabled, 1 not), 2 users, 15 retention periods, and the dev-only password warning. |
| 1.3 | Re-run and tear down | Run again with `--flush`, comparing counts. Create one unrelated change record and job result. Run `--teardown` and read the removed counts. | Second run reports the same counts (149, not 298). Teardown leaves the two unrelated records intact, removes rules and demo users, disables retention, and reports `17 extras.ArchivedJobResult` — not 120 — with no `ObjectPermission_users` line. |
| 1.4 | Repoint the alias to another host | Set `NAUTOBOT_CHANGELOG_ARCHIVE_DB_HOST` (and credentials) to a second Postgres host. Restart. Run `nautobot-server migrate --database changelog_archive`. Rotate and read a period. | Retention tables created on the second host; rotation and per-period reads work unchanged; warm reads unaffected. No code change needed. |
| 1.5 | Command guardrails | On a database with no Devices or Locations, run the command. Then on a populated one, run `--status` and compare counts before and after. Then `--no-rotate`. | First raises `CommandError` naming `nautobot-server generate_test_data`, not a traceback. `--status` prints counts and changes nothing. `--no-rotate` leaves 149 records warm and creates no retention periods. |

## 2. Capability disabled — behaviour parity (TRD §8)

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 2.1 | Warm reads are untouched with retention off | Set `CHANGELOG_ARCHIVE_ENABLED = False`. Open the change log list with django-debug-toolbar. Request `?archive_period=2024` in the UI and on `/api/extras/object-changes/`. Open a known retained record's URL. | No period selector anywhere; no query against `extras_archived*` or `ArchiveSegment`; both `archive_period` requests return warm data with no error and an unchanged response shape; the retained URL 404s. Query list matches `develop`. |
| 2.2 | Jobs are present but inert | With retention still off, run **Changelog Rotation** and **Changelog Truncation**. | Rotation completes saying retention is disabled and moves nothing. Truncation still works normally — it does not depend on rotation. |

## 3. Rotation job

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 3.1 | Dry run reports without moving | Run **Changelog Rotation** with `dry_run` checked. Read the result summary and the log. Note warm and retained counts before and after. | Summary carries the per-model counts it *would* move plus `dry_run: true`; the log names each count and the increment size. All record counts unchanged. The job result count is reported as a lower bound, and the log says why: nothing moves in a dry run, so every result still looks held back behind its own log entries. |
| 3.2 | Each record is filed in its own period | Create one change record dated today. Run rotation with `warm_window_days=90`. Then compare every retained record's `time` against its `period_key`. | Today's record stays warm. Every retained record's `period_key` equals its own timestamp's period — no 2023 record filed under 2024. Periods created for 2022–2025 only. |
| 3.3 | Idempotent, with honest counts (TRD §8) | Note every `ArchiveSegment.row_count`. Run rotation again. Compare counts, and compare each `row_count` against `SELECT count(*)` on that mirror for that `period_key`. Check `is_period_closed`. | Second run moves 0 records; no `row_count` changes; every `row_count` equals the actual count; fully-rotated past periods are `is_period_closed = True` and the current period is not. |
| 3.4 | Nothing is lost in the move | Pick a warm change record and a warm job result with log and console entries; record every field. Rotate. Compare against the retained copies. Read the held-back count for results with output files when `include_job_files` is unchecked. | Every field matches, including `object_data`, `object_data_v2`, `change_context_detail`, `user_name` and custom field values. Log and console entries moved with their result; no orphaned warm children. The held-back number equals the number actually held back — a missing `.distinct()` once reported 36 for 12. |
| 3.5 | Increments are bounded, sized by rotation's own setting | Run with `batch_size=25` over 149 eligible records. Then run with `batch_size` empty and check which setting is read. | Log shows `Increment 1`…`Increment 6`, not one statement. Empty falls back to `CHANGELOG_ROTATION_BATCH_SIZE` (default **1000**), not `CHANGELOG_TRUNCATION_BATCH_SIZE` (10000). |

## 4. Truncation job

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 4.1 | Deletes exactly what the filter selects (TRD §8) | With both enabled demo rules, run **Changelog Truncation** with `dry_run` on, then off. Count the fixture's warm truncation candidates before and after each. | The fixture leaves 15 warm candidates: 7 deletable, 3 carol's, 5 update-action. Dry run summary reads `extras.ObjectChange: 7` with `dry_run: true`, logs `would delete 7`, and deletes nothing. Real run summary reads `extras.ObjectChange: 7` with no `dry_run` key, logs `Deleted 7`, leaving 8. The 5 update-action records survive, so the filter is selective. |
| 4.2 | Exclude beats include, and a protection cannot be left out | Run **Changelog Truncation** as a dry run. Then disable the exclude rule and run again. Then re-enable it and disable the include rule instead, and run again. | First reports 7 with `selects 10` / `protects 3` / `keeping them`. Second reports 10: disabling the protection really does remove it. Third reports 0 and says `No include rule was applied`, rather than a bare zero. There is no per-run rule picker, so the *Enabled* checkbox is the only thing that changes any of this. |
| 4.3 | Bounded increments, and no dependence on rotation (TRD §8) | Run with `batch_size=10` against 50+ selected rows. Then `--teardown`, create warm-only history and a rule with `CHANGELOG_ARCHIVE_ENABLED = False`, and run again. | First shows more than one delete increment, never a single statement. Second deletes the selected rows normally with retention off. |
| 4.4 | Unsafe and invalid rules are refused, not widened | Create a rule with no scope filter and no `max_age_days`. Via the API set another rule's `scope_filter` to `{"action": ["not-a-real-action"]}`. Run truncation. | Log warns the first would select every record and skips it; reports the second as invalid and does not apply it. Neither deletes anything. Nothing is widened to match more than was asked. |
| 4.5 | Both empty cases are named, not silent | Open the **Changelog Truncation** run form. Disable all three rules and run. Then `--teardown` and run again. | Run form offers only a batch size and a dry-run toggle -- no rule picker, since every enabled rule applies. With rules present but none enabled, the run names the count and says none are enabled. With no rules at all: `No retention rules exist, so there is nothing to apply. Create one under Extensibility > Logging > Retention Rules.` Two distinct messages, each naming the fix. |
| 4.6 | Rotation is not raced | With retention enabled and a period not yet closed, run truncation against records in that period. | Those records are withheld and the log says why. Records in closed periods are deleted normally. |

## 5. Retention rules and the scope filter

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 5.1 | Standards | Extensibility > Logging > Retention Rules: Add, Edit, Save, Bulk Edit, Bulk Delete, list filtering, detail page. | Operational. Detail page shows a **Scope Filter** panel rendering the stored filter as JSON. |
| 5.2 | The builder is the standard one and follows the object type | Add a rule. Select object type **Object Change** and look at the Scope Filter card. Change the object type to **Job Result**. Then clear it. | Card shows Basic and Advanced tabs with the selected model's own filters — the same builder a custom field's scope uses, not a JSON textarea. Changing type re-renders over HTMX: `action`/`user_name` give way to `status`/`name`. With none selected: `Please select an object type first to load the available filter fields.` |
| 5.3 | A scope round-trips through the form | Add a rule with Basic tab Action = Deleted, save. Reopen for edit. Change only the description and save again. Then add another with Action = Deleted **and** Updated. | First stores `{"action": ["delete"]}`. Reopening shows the stored filter with **no** `Select a valid choice. ['delete'] is not one of the available choices.` Resaving preserves `scope_filter` rather than emptying it. The second stores both values — collapsing submitted data once reduced this to one and the form rejected the field. |
| 5.4 | The applied filter is always visible, and Advanced works | Open a rule with a stored filter and look at the card before touching the tabs. Switch to Advanced. Hard-reload, then add a filter on the Advanced tab with the browser console open. | The applied-filter badge is visible from both tabs, sitting above them rather than only under Advanced. Adding a filter creates a badge with no `Cannot read properties of null` in the console. |
| 5.5 | Invalid at save time, not at run time, on both paths | On the Advanced tab, add a filter with a value the filterset rejects, and save. Then `POST` the same `scope_filter` to `/api/extras/retention-rules/`. Then save a rule with no filter but `max_age_days=365`. | The form redisplays with a field error and creates nothing. The API returns **400** naming the filterset's own complaint -- it returned 201 and stored it while the form rejected the same value, so a scripted rule could be one the UI would not let you save. The third saves with `scope_filter = {}`, valid because the age bound bounds it. |
| 5.6 | Auditability and scripted creation | Edit a rule, then open its Change Log tab. `POST /api/extras/retention-rules/` with `scope_filter` in the body. | The edit appears in the change log — a rule decides what gets deleted, so who changed it is auditable. The API returns 201 with the filter stored, so rules are scriptable without the UI builder. |
| 5.7 | Custom fields still work (shared construct) | Extensibility > Custom Fields > Add. Select content type Location, set a scope filter, save, reopen. Then tick **Required**. | Scope round-trips unchanged. With Required ticked, the card reads `Scope filter can be set only for non-required custom fields.` |

## 6. Reading a retained period in the UI

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 6.1 | Pick a period and come back | As `retention-archivist`, open Extensibility > Logging > Change Log. Open the dropdown, choose 2023, then each other year, then **Recent**. | Dropdown labelled **Archive** with an `mdi-history` icon, listing `Recent`, a divider, then 2025→2022 with record counts. Choosing 2023 puts `?archive_period=2023` in the URL, shows 63 records all dated 2023, and turns the button primary reading `2023`. Each year shows 17/63/41/28. No warm record and no divider appears alongside — exactly one period at a time (TRD §8). **Recent** drops the parameter and returns warm records. |
| 6.2 | Filter and sort inside a period | With 2023 selected, filter `user_name = alice`. Then filter by object type = Device. Then sort by every column in both directions, starting with **Type**. | Filters narrow within 2023 only, count below 63, period stays selected. Object type filters correctly against the identifier column. Every column sorts, both directions, all 200 — sorting **Type** once raised `FieldError` and returned a 500. |
| 6.3 | Page through a period | Select 2023, set page size 25, page to the end and back. | 3 pages, stable ordering, no duplicated or omitted rows across pages, page size preserved. |
| 6.4 | Freshness, and a period that does not exist | Hover the dropdown button with 2023 selected. Rotate part of the current period and hover with that selected. Then request `?archive_period=1999`. | Closed period tooltip: `All 2023 records have been archived.` Open period says it is still being archived and names the last-rotated time, with a clock icon in the dropdown. `1999` is reported as invalid — no 500 and no silent fall back to warm data. |
| 6.5 | An object's own change log tab | Open a Device with retained history > Change Log tab. Select 2023. Check every row. Repeat on a Location. Then open the dropdown. | Selector present; the table shows only **this object's** 2023 records, not the period's 63 — the selector once rendered while the table kept showing warm records. Same on a Location. Period entries carry **no** count badge here, since a whole-period count beside one object's history reads as that object's count. |
| 6.6 | An object with nothing retained | Open the Change Log tab of an object with only warm records and select a period. | Empty table, no error. |
| 6.7 | The Object column links where the object survives | With a period selected, find a row whose object still exists (a Device or Location the demo data still has) and click its Object cell. Then find a row for an object since deleted -- a `delete` action row is the easy case -- and try the same. Open the surviving one's detail page too. | The first opens that object's page. The second is plain text with no link, showing the name as recorded at the time. The detail page's Changed Object field behaves the same way as the list. Watch the page load with a period of 50+ rows: it should not slow noticeably, since the links cost one lookup per object type rather than one per row. |

## 7. A retained change record's detail page

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 7.1 | The page survives rotation | Note a warm record's URL. Rotate it. Revisit that URL. Also reach one from a period listing. | Same URL still resolves, read-only, at `/extras/object-changes/<pk>/`. Links made before rotation do not rot. **Changed Object Type** shows the content type, e.g. `DCIM \| device`, not `—`. |
| 7.2 | The difference panel across all three actions | Open a retained *update* that has an earlier change to the same object in the same period. Then a retained *create*. Then a retained *delete*. | Update shows added and removed values — the panel once always read `No changes`. Create shows the whole payload as added, nothing removed. Delete shows the payload as removed, nothing added. |
| 7.3 | Neighbours and siblings | On a retained record with neighbours in its period, use PREVIOUS and NEXT. Then open one whose request touched the same object more than once and read RELATED CHANGES. | Previous/next navigate to the adjacent change to the same object and are not greyed out. Related changes lists other changes to **this object** in the same request, excluding this one — it once listed unrelated objects' records and included itself. |
| 7.4 | Links out keep the period | Click the Request ID link in the related-changes table and in the badge. Then do the same on a warm record. | Both retained links go to `?archive_period=<period>&request_id=…`; dropping the period once landed the reader back in warm storage. The warm record's link carries no `archive_period`. |
| 7.5 | Sweep a whole period | Walk every record in one period, opening each detail page. | All render. No 500 on any. |

## 8. A retained job result

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 8.1 | The page and its log panel | Open a retained job result's URL. Read the log panel. Compare it against the retained log entries for that `job_result_id`. Filter the log table, then sort it by every column. | Page renders read-only with name, status, dates, duration and custom field values. Log panel shows exactly that result's entries and no neighbouring result's — the page once rendered while every panel 404'd and came up empty. Filter narrows within them; every column sorts, all 200. |
| 8.2 | Console output and export | Open the console log tab of a retained result that has console output. Use **Export Console Logs**. Inspect the **Export Logs** button's URL. Then open a retained result with no console output. | Console lines shown; export downloads them as plain text. Export Logs URL carries `&archive_period=<period>` — without it the download was an empty file. The result with none renders an empty tab without error, so the genuinely-empty case is distinguishable from broken. |
| 8.3 | The job results list with a period | Request `/extras/job-results/?archive_period=2023`. | 200 with that period's results. This once raised `FieldError` from `select_related` on demoted relations. |
| 8.5 | The period selector on the job result list | Open Jobs > Job Results as `retention-archivist`. Open the **Archive** dropdown and choose 2023. Then repeat as `retention-viewer`. | Selector offers 2022-2025 and 2023 shows that period's 7 results. This was a known gap while the helpers existed but nothing was wired to them. The viewer sees no selector, the same gate as the change log list. |
| 8.4 | Sweep every retained result | Walk all 17, opening detail, log table, console tab and export for each. | All render. No 500 on any. |

## 9. Read-only enforcement and the cold-storage permission (TRD §8)

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 9.1 | No write affordances on retained history | Select a period on the change log list. Look for row actions, the bulk-select column, bulk edit and bulk delete. | None offered. Retained history is read-only by design. |
| 9.2 | Write URLs and API writes refuse | Construct `/extras/job-results/<retained pk>/delete/` and the edit URL and open both. `PATCH` and `DELETE` a retained record through the API. | All refuse — 404 for the UI URLs. The delete view once resolved the retained record and offered a delete against something with no write surface. No mutation from the API. |
| 9.3 | The UI gate | Log in as `retention-viewer` and open the change log list. Try `?archive_period=2023` by hand. Open a retained record's URL directly. Then repeat all three as `retention-archivist`. | Viewer sees no dropdown, gets no retained records from the hand-typed parameter, and is refused the retained detail page. Archivist can do all three. |
| 9.4 | The API gate | As `retention-viewer`, `GET /api/extras/object-changes/?archive_period=2023` and a retained result's log table URL. Repeat as `retention-archivist`. | Viewer gets **403** — not 200-with-warm-data. Archivist gets 200 with that period's records. |
| 9.5 | The gate holds under a global exemption | Compare the two users' object permissions. Set `EXEMPT_VIEW_PERMISSIONS = ["*"]`, restart, and retry 9.3 as the viewer. Then grant `extras.view_archivesegment` to a third user through the ObjectPermission UI. | The two users differ only by `extras.view_archivesegment`. The global exemption does not open retained history — the viewer still sees no dropdown. The grant works through the standard framework and the third user gains access. |

## 10. View state across period changes

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 10.1 | The period survives a filter submit | Select 2023, open the filter drawer, apply a filter, submit. | Still in 2023 with the filter applied. The period was once dropped here, silently returning the reader to warm storage. |
| 10.2 | Switching period keeps the view | Filter `user_name = alice` in 2023, sort by user name, go to page 3, set page size 25. Switch to 2024. | Filter, sorting and page size all preserved; page resets to 1 rather than a page that may not exist. |
| 10.3 | Unsupportable filters and search | Filter by a relation-traversing field such as `user`, then switch into a period. Then use the `in: Change Log` search box with a period selected. | The filter is dropped and named: `Not available for archived records, so this filter was dropped: …`, and the table still renders. Search results stay within the selected period, and "see all results" keeps it. |

## 11. REST API

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 11.1 | Discover the periods | `GET /api/extras/archive-segments/` as the archivist. Try to `POST` to it. | Read-only list with `period_key`, `label`, `row_count`, `last_rotated_time`, `is_period_closed` per period. Writes refused. This is how a client learns which `archive_period` values are valid. |
| 11.2 | Read a period on every covered endpoint | `?archive_period=2023` on `/api/extras/object-changes/`, `/api/extras/job-results/` and `/api/extras/job-logs/`. | All 200 with that period's records; object changes report `count = 63`. `JobConsoleEntry` has no endpoint by design — its retained output comes from the job result console export. |
| 11.3 | Schema parity (TRD §8) | Diff the field names of a retained object-change response against an unparameterized one. Inspect `changed_object_type` and `related_object_type` on a retained record. | Field names identical; nothing omitted. Both type fields are populated with `app_label.model` — they once came back `null`, losing the referent. |
| 11.4 | Bad and irrelevant parameters | `?archive_period=1999`, `?archive_period=not-a-period`, `?archive_period=`, and `?archive_period=2023` on `/api/dcim/devices/`. | Unknown period is a **400** naming the problem. Malformed values are rejected or ignored consistently. On an uncovered model the parameter is ignored and the normal list returns. No 500 from any of them. |
| 11.5 | Paging, filtering and the schema | `?archive_period=2023&limit=10&offset=60`, then `&user_name=alice`. Full CRUD on `/api/extras/retention-rules/`. Open `/api/docs/`. | Paging is consistent to `count = 63` with `next`/`previous` keeping the parameter; filtering narrows within the period. Rules CRUD works with `scope_filter` writable. Docs and schema render, with `RetentionRuleModeChoices` not collision-suffixed. |

## 12. Verification jobs

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 12.1 | Integrity check finds and fixes orphans | Run **Changelog Archive Integrity Check** on clean data. Delete a warm `JobResult` that retained log entries reference, leaving the entries. Re-run. Re-run again with `repair` checked. | Clean run reports no orphans. Second run reports those entries as having no referent and **does not** delete them. The repair run removes them and reports the count. |
| 12.2 | Integrity check finds a stale content type | Point a retained record's `changed_object_type_id` at a removed content type. Run the check. | Reported. The record still renders in the UI with `—` for its type rather than erroring. |
| 12.3 | Reconciliation finds and fixes count drift | Run **Changelog Archive Reconciliation** on clean data. Set an `ArchiveSegment.row_count` to a wrong value. Re-run. Re-run with `repair` checked. | Clean run reports every period as matching. Second names the drift with expected and actual. Repair corrects `row_count` to the actual count. |
| 12.4 | Reconciliation finds misfiled and duplicated records | Move a retained record's `time` outside its period's bounds. Copy another retained record back into warm storage. Run reconciliation. | Both reported — one as outside its period, one as existing in both warm and retained storage. |
| 12.5 | Schema drift is reported (TRD §8) | Run `nautobot-server check_changelog_archive_schema`. Add a field to `ObjectChange` without adding it to `ArchivedObjectChange`. Re-run, then run `nautobot-server check`. | Clean run: `Every retention mirror matches the model it mirrors.` With drift, the command names the missing field and `check` emits a warning rather than passing silently. |
| 12.6 | All four jobs are schedulable | Create a `ScheduledJob` for rotation, truncation, integrity check and reconciliation. | All four schedulable through the standard interface, disabled by default until retention is turned on. |

## 13. Interruption and resource bounds

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 13.1 | A killed rotation loses nothing | Start rotation over a large set. `kill -9` the worker mid-run. Compare warm and retained counts, then check records from completed increments. Re-run rotation. | No record is missing from both places; some may be in both, which is the safe direction. Completed increments are committed and retained. The re-run resolves the duplicates, duplicates nothing, and leaves every `row_count` equal to the actual count. |
| 13.2 | The count never overstates, and change logging comes back | After 13.1, compare each `row_count` against the actual retained count and against what left warm storage. Then edit any object and open its change log. | No `row_count` is higher than what is retained or lower than what was removed from warm storage — the latter cannot be repaired by re-running. The edit is change-logged, so rotation's signal suppression did not leak past the crash. |
| 13.3 | A killed truncation is safe to re-run | Kill truncation mid-run. Compare counts. Re-run. | It deleted less than it would have, with no error and nothing half-deleted. The re-run completes the job. |
| 13.4 | Memory is bounded, and reads survive a run | Rotate a large volume at the default batch size while watching worker RSS. Truncate a very large selection. Load the change log list while rotation is running. | Rotation memory is bounded by batch size, not total volume — lower `CHANGELOG_ROTATION_BATCH_SIZE` if records are large. Truncation does not materialize every matching key. The page renders during a run, with no error and no partial row. |

## 14. Saves that change nothing (nautobot#3321)

Not retention, but on this branch and against the same tables. A save that moves no value now records
nothing — and so fires no webhook, job hook, or event. The comparison is against the object's stored values
at save time, not the values it was loaded with.

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 14.1 | An edit with no edits | Open a Device, press Save without changing anything. Then change one field and save. Check the Change Log tab after each. | The first records nothing. The second records exactly one entry, whose difference panel shows that one field. Before this change the first wrote an entry reading "No changes". |
| 14.2 | Same through the API | `PATCH` a device with `{}`. Then `PATCH` it with a field set to the value it already holds. Then with a genuinely new value. | 200 each time. No change record for the first two; exactly one for the third. |
| 14.3 | Reverting someone else's change is recorded | Open a Device's edit form. In a second session (or via `nautobot-server shell`, `Device.objects.filter(pk=...).update(description="other")`), change that field. Return to the first form and save it unchanged. | A change record **is** written. This is the case the design exists for: the save reverted a value, which is a change to the stored row even though the form looked untouched. |
| 14.4 | Associations still record | Add a tag to a Device. Then, in one request, save it unchanged and add a tag. | Each records one entry. No concrete field moved, but the change is real, so it is not suppressed. |
| 14.5 | Bulk edit of no-ops | Bulk-edit 20 devices, setting a field to the value they already hold. Then bulk-edit them setting a genuinely new value. | The first records nothing at all. The second records one entry per device. |
| 14.6 | Nothing dispatches for a no-op | Configure a webhook on Device change. Save a Device unchanged, then save it changed. | No webhook for the unchanged save; one for the changed save. **This is the migration risk** — an integration using a same-value `PATCH` as a heartbeat silently stops firing. |
| 14.7 | Custom fields and status count | Change only a custom field value on an object; then only its status; then clear a custom field. | Each records exactly one entry. Custom field data lives in a JSON column and is the likeliest thing for a comparison to miss. |
| 14.8 | `last_updated` moves anyway | Note an object's Last Updated, save it unchanged, reload. | Last Updated advances; no change record. An object's Last Updated can be newer than its newest change record, by design. |
| 14.9 | A related object's change is no longer attributed here | Rename a Location, then save an unrelated Device in that Location without changing it. | No change record on the Device. Previously this wrote one whose diff showed the Location's rename, attributed to this Device and this user. |

## 15. The legacy object snapshot

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 15.1 | Default is unchanged behaviour | On a fresh upgrade, make a change and inspect the record via `/api/extras/object-changes/`. | `CHANGELOG_LEGACY_OBJECT_DATA` defaults to `True`; both `object_data` and `object_data_v2` are populated, exactly as before. |
| 15.2 | Turning it off | Set `CHANGELOG_LEGACY_OBJECT_DATA` to `False` under Admin > Configuration. Make a change. Inspect the record. | `object_data` is null; `object_data_v2` is populated. |
| 15.3 | Everything still reads | With it off, open the new record's detail page. | Page renders; the Object Data panel shows the snapshot; the difference panel shows the change. Nothing is empty. |
| 15.4 | Older records are unaffected | With it off, open a record written before the switch, and one written before Nautobot 1.3 if the deployment has any. | Both render, with their diffs intact. The fallbacks exist for exactly these. |
| 15.5 | Webhooks still carry data | With it off, trigger a webhook and inspect the payload. | The `data` key is populated from `object_data_v2`, and `snapshots` still has prechange, postchange and differences. |
| 15.6 | Retained records match | With it off, rotate, then open a retained record. | Its snapshot and difference panels behave the same as a warm record's — the mirror carries whichever snapshot exists. |

## 16. Accepted limitations — confirm as designed, do not file

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 16.1 | No cross-period read and no GraphQL | Look for any way to query two periods at once in the UI or API. Query retained history through GraphQL. | Neither is offered. **Expected** — TRD §2. |
| 16.2 | No diff at a period boundary | Open the earliest retained record for an object within a period, where the previous change to it sits in the adjacent period. | Shows its data with no diff. **Expected** — the same presentation warm gives a record whose predecessor was deleted. |
| 16.3 | Relation filters unavailable within a period | With a period selected, try each of: `user` on object changes; `canceled_by`, `has_job_console_entries`, `job_model`, `scheduled_job`, `user` on job results. Then try their `_id` variants and `changed_object_type`. | The first set is dropped with a named warning; the `_id` variants and `changed_object_type` work. **Expected** — those relations are identifier columns on a retained record. |
| 16.4 | A constrained permission does not narrow a retained period | Grant a user an object permission constrained to one tenant's or one location's records, plus `extras.view_archivesegment`. Read the warm change log as that user, then select a period. | Warm records are narrowed by the constraint. The retained period is not: they see all of it. **Expected** -- TRD §2 accepts this, and TRD §9 carries it. Reading retained history is all-or-nothing on the archive permission today. |
| 16.6 | Direct database readers see fewer rows | After truncation, query the warm table directly in SQL. | Fewer rows, no error. **Expected and documented** — TRD §6. |
| 16.7 | SSoT `Sync` coupling | With `nautobot_ssot` installed, rotate a `JobResult` that has a `Sync` record. Check whether the `Sync` still resolves. | **Verify and report.** Rotation does not consider `Sync`, so such a result is rotated like any other. TRD §9 carries this as an open item — record what actually happens rather than filing it. |

---

## Sign-off — TRD §8 acceptance criteria

| Criterion | Tests |
|---|---|
| Capability disabled behaves as today | 2.1, 2.2 |
| Default reads resolve against warm tables only | 2.1, 6.1 |
| Retained read needs the permission; parameter rejected without it; unknown period is a bad request | 9.3, 9.4, 9.5, 6.4, 11.4 |
| A retained read resolves against exactly one period | 6.1, 16.1 |
| Truncation removes exactly what its filters select | 4.1, 4.2 |
| Truncation runs in bounded increments | 4.3 |
| Truncation works with rotation unconfigured | 4.3 |
| Rotation moves records with no field loss | 3.4 |
| A record is rotated into its own timestamp's period | 3.2 |
| Rotation is idempotent | 3.3 |
| Schema-drift check reports a gained field | 12.5 |
| Retained response validates against the warm schema | 11.3 |
| Include and exclude filters resolve, job- and object-type-scoped | 4.1, 4.2, 5.3 |

Not covered, because the TRD leaves the numbers unset: warm read latency budget, rotation throughput,
freshness bound and truncation increment size (TRD §8, §9). Performance testing needs those agreed first.
