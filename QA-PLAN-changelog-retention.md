# Changelog Long-Term Retention: Manual QA Test Plan

One row is one pass at one screen: a task a tester performs, with everything that must hold afterwards bundled into Expected. A row fails if any part of Expected fails; note which part.

Section 11 lists behaviour that looks like a defect and is not, so it does not get filed as one.

**What this release covers.** Rotation moves change and job history older than the warm window into four retained tables on a second connection, and those tables are read through their own pages and their own REST endpoints. There is no truncation job, no retention rules, and no calendar periods: retained history is one table per record type holding everything rotated so far.

**Fixture.** Every test assumes `nautobot-server create_changelog_retention_demo_data` has been run with the default seed unless the test says otherwise. That produces exactly:

| | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| Retained change records | 17 | 63 | 41 | 28 |
| Retained job results | 3 | 7 | 5 | 2 |

149 retained change records, 17 retained job results with their log and console entries, and two users, `retention-viewer` and `retention-archivist`, sharing the password `retention-demo-1234` and differing only in the four retained-history view permissions.

**The counts are deliberately unequal.** If a year's total, an object's own history and the page size are all the same number, a disagreement between them is invisible. Distrust any check where two of them coincide, and re-run with a different `--seed`.

---

## 1. Setup and fixture data

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 1.1 | Provision on a fresh database | On a database at `extras.0147` with no `NAUTOBOT_CHANGELOG_ARCHIVE_DB_*` variables set, run `nautobot-server migrate`. Then `makemigrations --check --dry-run`. Then print `settings.DATABASES` keys. | Migration `0148_changelog_archive_storage` applies and creates the four retained tables; check says `No changes detected`; `changelog_archive` is present alongside `default` and `job_logs`. Nothing had to be provisioned separately. |
| 1.2 | Generate the fixture | Run `nautobot-server create_changelog_retention_demo_data`. | Reports per-year change records `{2022: 17, 2023: 63, 2024: 41, 2025: 28}`, a rotation summary covering 149 object changes and 17 job results, 2 users, and the dev-only password warning. |
| 1.3 | Re-run and tear down | Run again with `--flush`, comparing counts. Create one unrelated change record and job result. Run `--teardown` and read the removed counts. | Second run reports the same counts (149, not 298). Teardown leaves the two unrelated records intact, removes the demo users, turns retention off, and reports `17 extras.ArchivedJobResult`, not 120, with no `ObjectPermission_users` line. |
| 1.4 | Repoint the alias to another host | Set `NAUTOBOT_CHANGELOG_ARCHIVE_DB_HOST` (and credentials) to a second Postgres host. Restart. Run `nautobot-server migrate --database changelog_archive`. Rotate, then read the archived lists. | The four retained tables are created on the second host; rotation and archived reads work unchanged; warm reads unaffected. No code change needed. A `migrate` that creates nothing here is the failure to watch for. |
| 1.5 | Command guardrails | On a database with no Devices or Locations, run the command. Then on a populated one, run `--status` and compare counts before and after. Then `--no-rotate`. | First raises `CommandError` naming `nautobot-server generate_test_data`, not a traceback. `--status` prints counts and changes nothing. `--no-rotate` leaves 149 records warm and the retained tables empty. |

## 2. Capability disabled: behaviour parity

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 2.1 | Warm reads are untouched with retention off | Set `CHANGELOG_ARCHIVE_ENABLED = False` and restart. Open the change log list with django-debug-toolbar. Open a known retained record's warm URL. | No query against any `extras_archived*` table. The retained URL 404s instead of redirecting. Query list matches `next`. |
| 2.2 | The archived pages still serve with retention off | With retention still off, open the archived lists and `GET /api/extras/archived-object-changes/`. | All return 200 and show whatever was rotated before the setting was turned off. The views are registered unconditionally and only the warm-URL redirect is gated on the setting, so turning retention off stops new rotation without hiding history already moved. Confirm that is the intent. |
| 2.3 | The rotation job is present but inert | With retention still off, run **Changelog Rotation**. | Completes, logs that retention is disabled, and moves nothing. |

## 3. Rotation job

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 3.1 | Dry run reports without moving | Run **Changelog Rotation** with `dry_run` checked. Read the result summary and the log. Note warm and retained counts before and after. | Summary carries the per-model counts it *would* move plus `dry_run: true`; the log names each count and the increment size. All record counts unchanged. The job result count is reported as a lower bound and the log says why: nothing moves in a dry run, so every result still looks held back behind its own log entries. |
| 3.2 | Only records past the warm window move | Create one change record dated today. Run rotation with `warm_window_days=90`. | Today's record stays warm. Every record moved is older than the cutoff, and the log names the cutoff date. |
| 3.3 | Idempotent | Note the retained counts. Run rotation again. | Second run moves 0 records, reports no error, and the retained counts are unchanged. A retained record keeps the primary key it had warm, so a repeat write conflicts harmlessly. |
| 3.4 | Nothing is lost in the move | Pick a warm change record and a warm job result with log and console entries; record every field. Rotate. Compare against the retained copies. Read the held-back count for results with output files when `include_job_files` is unchecked. | Every field matches, including `object_data`, `object_data_v2`, `change_context_detail` and custom field values. A job result's `user` is demoted, and its username appears in `user_name`. Log and console entries moved with their result; no orphaned warm children. The held-back number equals the number actually held back, not the child-row count. |
| 3.5 | Increments are bounded | Run with `batch_size=25` over 149 eligible records. Then run with `batch_size` empty and check which setting is read. | Log shows `Increment 1`…`Increment 6`, not one statement. Empty falls back to `CHANGELOG_ROTATION_BATCH_SIZE`, default 1000. |
| 3.6 | Record types can be rotated selectively | Run with `record_types` set to object changes only. | Only change records move. Job results, log entries and console entries stay warm. |

## 4. Reading retained history in the UI

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 4.1 | The two archived lists | As `retention-archivist`, open Extensibility > Logging > **Archived Change Log** and Jobs > **Archived Job Results**. | Both render. 149 and 17 records. Read-only: no Add button, no row actions, no bulk-select column. Export is offered. |
| 4.2 | Filter and sort | On the archived change log, filter `user_name = alice`. Then filter by object type. Then sort by every column in both directions, starting with **Type**. | Filters narrow correctly; object type filters against the identifier column. Every column sorts, both directions, all 200. Sorting **Type** once raised `FieldError` and returned a 500. |
| 4.3 | Page through | Set page size 25 and page to the end and back. | 6 pages, stable ordering, no duplicated or omitted rows, page size preserved. |
| 4.4 | The Object column links where the object survives | Find a row whose object still exists and click its Object cell. Then find a row for an object since deleted, a `delete` action row being the easy case. Watch a 50-row page load. | The first opens that object's page. The second is plain text, showing the name as recorded at the time. The page should not slow noticeably: links cost one lookup per object type, not one per row. |
| 4.5 | Search | Use the global search box scoped to Archived Change Log. Then search globally without a scope. | Scoped search returns retained records. Unscoped global search does **not** return them, by design, so a warm record and its retained copy never appear side by side. |

## 5. A retained change record's detail page

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 5.1 | A link made before rotation still works | Note a warm record's URL. Rotate it. Revisit `/extras/object-changes/<pk>/`. | Redirects to `/extras/archived-object-changes/<pk>/` and that page renders. Links made before rotation do not rot. |
| 5.2 | The page matches the warm one | Open a retained record and the warm equivalent side by side. Count the panels on each. | Same panels in the same order: Change, Object Data, Object Data v2, Difference, Related Changes, plus the Advanced tab. **Changed Object Type** shows the content type, for example `DCIM | location`, not a placeholder. |
| 5.3 | The difference panel across all three actions | Open a retained *update* that has an earlier change to the same object. Then a retained *create*. Then a retained *delete*. | Update shows added and removed values in the diff viewer. Create shows the whole payload as added. Delete shows it as removed. An empty diff box means `js/editor.js` did not load; that is a defect, not an empty diff. |
| 5.4 | Neighbours and siblings | On a retained record with neighbours, use PREVIOUS and NEXT. Then open one whose request touched the same object more than once and read RELATED CHANGES. | Previous and next navigate to the adjacent change to the same object. Related changes lists other changes to this object in the same request, excluding this one, and every row links to an archived detail page. |
| 5.5 | Sweep | Walk a full page of retained records, opening each detail page. | All render. No 500 on any. |

## 6. A retained job result

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 6.1 | The page matches the warm one | Open a retained job result and a warm one side by side. Compare the Summary of Results panel and the Advanced tab. | Same panels. The summary shows job description, status, dates, duration, result and files; `user_name` appears where the warm page shows `user`. Advanced shows job kwargs, positional args, celery kwargs, Worker and Traceback. Cancel Details appears only on a canceled result. No Run and no Cancel Job button. |
| 6.2 | The Logs panel | Read the log panel and compare it against the retained log entries for that `job_result_id`. Type in the filter box. Sort by every column. | Logs card with a filter box, same as the warm page. Shows exactly that result's entries and no neighbouring result's. The filter narrows them; every column sorts, all 200. |
| 6.3 | Console output | Open the **Console Log** tab of a retained result that has console output. Then open one with none. | Output renders as a console block, monospace lines with timestamps, the same presentation as the warm page. A table of Time/Stream/Text columns is a defect. The result with no output does not show the tab at all. |
| 6.4 | Both exports | Use **Export Logs** and **Export Console Logs**. | Logs download as CSV from `/api/extras/archived-job-logs/?job_result_id=…&format=csv`, containing that result's entries only. Console logs download as plain text, one `[HH:MM:SS.mmm] line` per entry. |
| 6.5 | Sweep every retained result | Walk all 17, opening detail, log panel, console tab and both exports. | All render. No 500 on any. |

## 7. Read-only enforcement and permissions

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 7.1 | No write affordances | On both archived lists, look for row actions, the bulk-select column, bulk edit and bulk delete. On a detail page, look for Edit and Delete. | None offered. |
| 7.2 | Write URLs and API writes refuse | Construct `/extras/archived-job-results/<pk>/delete/` and the edit URL and open both. `POST`, `PATCH` and `DELETE` against the archived endpoints. | All refuse. The models declare only a `view` permission, so there is no add, change or delete to grant. |
| 7.3 | The UI gate | As `retention-viewer`, open both archived lists and a retained record's URL directly. Then repeat as `retention-archivist`. | Viewer is refused all three and sees no Archived entries in the navigation menu. Archivist can do all three. |
| 7.4 | The API gate | As `retention-viewer`, `GET` each of the three archived endpoints. Repeat as `retention-archivist`. | Viewer gets **403** on each. Archivist gets 200. |
| 7.5 | The permissions are separate from the warm ones | Compare the two users' object permissions. Grant a third user only `extras.view_objectchange`. | The two demo users differ by `extras.view_archivedobjectchange`, `extras.view_archivedjobresult`, `extras.view_archivedjoblogentry` and `extras.view_archivedjobconsoleentry`. The third user can read the warm change log and is refused retained history. |
| 7.6 | A retained job result needs the log and console permissions too | Grant a user `extras.view_archivedjobresult` only. Open a retained job result. | The page renders, the Logs panel is empty and the Console Log tab is absent. Granting the other two fills both in. Worth knowing before an operator reports an empty page. |

## 8. REST API

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 8.1 | The three endpoints | `GET /api/extras/archived-object-changes/`, `/api/extras/archived-job-results/` and `/api/extras/archived-job-logs/`. | All 200. Object changes report `count = 149`, job results `17`. |
| 8.2 | Schema parity | Diff the field names of a retained object-change response against a warm one from `/api/extras/object-changes/`. Do the same for job results and job log entries. | Field names identical, with one exception: a retained job result adds `user_name`. Nothing is named `user_id`, `job_result_id` or `changed_object_type_id`, because each demoted reference is rendered the way the warm response renders it. |
| 8.3 | Demoted references carry their referent | On a retained record inspect `changed_object_type`, `related_object_type`, `user` and, on a log entry, `job_result`. | Content types read `app_label.model`. Other references read `{"id": …, "object_type": …}` with no `url` key. None of them is `null` where the warm response has a value. |
| 8.4 | `url` names the archived endpoint | Read `url` on a retained record from each endpoint. | Each points at its own archived detail endpoint, not the warm one. A warm `url` here names a record that is gone. |
| 8.5 | Filtering, paging and CSV | `?limit=10&offset=60`, then `&user_name=alice`. Then `?job_result_id=<pk>&format=csv` on the job logs endpoint. | Paging is consistent to `count = 149` with `next` and `previous`. Filtering narrows. The CSV downloads with a header row and that result's entries. |
| 8.6 | The schema renders | Open `/api/docs/`. Find the three archived paths. | All six paths (list and detail) are present with their own components, each offering `GET` only. No duplicate-component warning at startup. |

## 9. Verification tooling

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 9.1 | Integrity check finds and removes orphans | Run **Changelog Archive Integrity Check** on clean data. Delete a warm `JobResult` that retained log entries reference, leaving the entries. Re-run. Re-run with `repair` checked. | Clean run reports no orphans. Second run reports those entries as having no referent and leaves them in place. The repair run removes them and reports the count. |
| 9.2 | Integrity check finds a stale content type | Point a retained record's `changed_object_type_id` at a removed content type. Run the check. | Reported. The record still renders in the UI with a placeholder for its type instead of erroring. |
| 9.3 | Integrity check finds records in both places | Copy a retained record back into warm storage. Run the check. | Reported as present in both warm and retained storage, which is what an interrupted rotation leaves behind. |
| 9.4 | Schema drift is reported | Run `nautobot-server check_changelog_archive_schema`. Add a field to `ObjectChange` without adding it to `ArchivedObjectChange`. Re-run, then run `nautobot-server check`. | Clean run reports every mirror as matching. With drift, the command names the missing field and `check` emits a warning instead of passing silently. |
| 9.5 | Both jobs are schedulable | Create a `ScheduledJob` for rotation and for the integrity check. | Both schedulable through the standard interface. |

## 10. Interruption and resource bounds

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 10.1 | A killed rotation loses nothing | Start rotation over a large set. `kill -9` the worker mid-run. Compare warm and retained counts, then check records from completed increments. Re-run rotation. | No record is missing from both places; some may be in both, which is the safe direction. Completed increments are committed. The re-run resolves the duplicates and duplicates nothing. Run the integrity check afterwards: it should name anything left in both places. |
| 10.2 | Change logging comes back after a crash | After 10.1, edit any object and open its change log. | The edit is change-logged, so rotation's signal suppression did not leak past the crash. |
| 10.3 | Memory is bounded, and reads survive a run | Rotate a large volume at the default batch size while watching worker RSS. Load the change log list and an archived list while rotation is running. | Memory is bounded by batch size, not total volume. Both pages render during a run, with no error and no partial row. |

## 11. Accepted limitations: confirm as designed, do not file

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 11.1 | No GraphQL and no merged read | Query retained history through GraphQL. Look for any view showing warm and retained records together. | Neither is offered. **Expected.** |
| 11.2 | A job result's description and files are empty | Open a retained job result and read **Job description** and **Files**. | Both empty. **Expected and documented.** The description belongs to the `Job`, which is not archived, and output files are deleted with the warm record instead of being moved. The job's name is copied at rotation, so the job is still identified. |
| 11.3 | No diff where the predecessor has not rotated | Open the earliest retained record for an object whose previous change is still warm. | Shows its data with no diff. **Expected**, and the same presentation warm gives a record whose predecessor was deleted. |
| 11.4 | Relation filters are unavailable | On the archived change log try `user`; on archived job results try `job_model`, `scheduled_job`, `canceled_by`, `user` and `has_job_console_entries`. Then try `user_name`, `name` and `changed_object_type`. | The first set is absent. The second set works. **Expected**: those relations are identifier columns on a retained record. |
| 11.5 | An object permission constraint that traverses a relation breaks the page | Grant a user `extras.view_archivedobjectchange` constrained by `{"user__username": "alice"}`. Open the archived change log. Then change the constraint to `{"user_name": "alice"}`, and then to `{"changed_object_type_id": <id>}`. | The first raises an error instead of returning everything, which is the safe direction but does break the page. The second and third apply normally and narrow the list. **Expected and documented**: write constraints for retained records against the columns they store. |
| 11.6 | Direct database readers see fewer rows | After rotation, query `extras_objectchange` directly in SQL. | Fewer rows, no error. **Expected and documented.** |
| 11.7 | SSoT `Sync` coupling | With `nautobot_ssot` installed, rotate a `JobResult` that has a `Sync` record. Check whether the `Sync` still resolves. | **Verify and report.** Rotation does not consider `Sync`, so such a result is rotated like any other. Record what actually happens instead of filing it. |

## 12. The legacy object snapshot

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 12.1 | Default is unchanged behaviour | On a fresh upgrade, make a change and inspect the record via `/api/extras/object-changes/`. | `CHANGELOG_LEGACY_OBJECT_DATA` defaults to `True`; both `object_data` and `object_data_v2` are populated, exactly as before. |
| 12.2 | Turning it off | Set `CHANGELOG_LEGACY_OBJECT_DATA` to `False` under Admin > Configuration. Make a change. Inspect the record. | `object_data` is null; `object_data_v2` is populated. |
| 12.3 | Everything still reads | With it off, open the new record's detail page. | Page renders; the Object Data panel shows the snapshot; the difference panel shows the change. Nothing is empty. |
| 12.4 | Older records are unaffected | With it off, open a record written before the switch, and one written before Nautobot 1.3 if the deployment has any. | Both render, with their diffs intact. The fallbacks exist for exactly these. |
| 12.5 | Webhooks still carry data | With it off, trigger a webhook and inspect the payload. | The `data` key is populated from `object_data_v2`, and `snapshots` still has prechange, postchange and differences. |
| 12.6 | Retained records match | With it off, rotate, then open a retained record. | Its snapshot and difference panels behave the same as a warm record's; the mirror carries whichever snapshot exists. |

---

## Sign-off

| Criterion | Tests |
|---|---|
| Capability disabled behaves as today | 2.1, 2.3 |
| Default reads resolve against warm tables only | 2.1 |
| Retained reads need their own permission, in the UI and the API | 7.3, 7.4, 7.5 |
| Rotation moves records with no field loss | 3.4 |
| Rotation moves only records past the warm window | 3.2 |
| Rotation is idempotent | 3.3 |
| Rotation runs in bounded increments | 3.5 |
| An interrupted rotation loses no record | 10.1 |
| Retained history is read-only everywhere | 7.1, 7.2 |
| A link made before rotation still reaches the record | 5.1 |
| A retained page shows what the warm page shows | 5.2, 6.1, 6.2, 6.3 |
| A retained API response matches the warm schema | 8.2, 8.3, 8.4 |
| Schema-drift check reports a gained field | 9.4 |
| Orphans and double-stored records are detected | 9.1, 9.3 |

Not covered, because the numbers are not set: warm read latency budget, rotation throughput, and freshness bound. Performance testing needs those agreed first.
