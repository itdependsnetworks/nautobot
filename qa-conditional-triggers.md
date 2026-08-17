# Conditional Triggers: Manual QA Test Plan

Covers the scope filter and conditions that Webhooks and Job Hooks carry.

!!! note
    There is no separate rule object. **Scope Filter** and **Conditions** are two fields on the Webhook or Job Hook itself, so "the trigger" below means the webhook or job hook you are configuring, and everything is done on that object's own form, detail page and API endpoint.

Everything in sections 1 through 15 applies identically to Webhooks and Job Hooks, because both carry the same mixin. Run each section against Webhooks, then use section 8 to confirm Job Hooks behave the same rather than repeating every case twice.

## 0. Prerequisites and setup

Do these before starting. Two of them will otherwise block you immediately.

| # | Item | Detail |
|---|------|--------|
| 0.1 | Running stack with demo data | `invoke start` then `invoke load-data` (or an existing dev DB). You need at least 2 Locations of type Campus, several Devices, and the Active / Staged / Planned Statuses. |
| 0.2 | **A webhook receiver that is not on loopback** | `127.0.0.1` and `localhost` are loopback, which the SSRF check blocks unconditionally. `WEBHOOK_ALLOWED_HOSTS` does **not** override the built-in block list. Use a receiver reachable at a private (`10.x`, `172.16-31.x`, `192.168.x`) or public address: another compose service, your host's LAN IP, or webhook.site. Verify the URL saves on a plain Webhook before building anything on it. |
| 0.3 | Celery worker running | Conditions are evaluated in the worker. Keep `docker compose logs -f celery_worker` open in a second terminal for the whole session; several tests below read it. |
| 0.4 | A job hook receiver job | Needed for section 8. Enable any `JobHookReceiver` under Jobs. |
| 0.5 | Two user accounts | One superuser; one non-superuser you can grant individual permissions to (section 11). |
| 0.6 | Sample data (optional) | `nautobot-server create_conditional_trigger_demo_data` creates `DEMO-` webhooks covering every preset, plus change log entries to test against. Useful for section 9. |

---

## 1. List view, detail view, and form entry points

There is no new menu item and no new list view. These confirm the existing Webhook and Job Hook pages gained the feature without changing anything else.

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 1.1 | No new menu entry | Log in as superuser. Open the **Extensibility** menu. | **Webhooks** appears as before. There is **no** "Event Rules" or "Conditional Triggers" item; the feature adds no navigation. |
| 1.2 | Webhook list unchanged | Open **Extensibility > Webhooks**. | The list renders with its usual default columns: Name, Object types, Payload URL, HTTP content type, Enabled. No scope or conditions column was added, and no column was removed. Check the column selector too: the available columns are unchanged. |
| 1.3 | Detail panels present | Open any Webhook's detail page. | Alongside the existing panels, a **Scope Filter** panel and a **Conditions** panel appear on the right, each rendered as formatted JSON. A webhook that has neither shows `{}` and `[]`. |
| 1.4 | Panels have copy buttons | On that detail page, hover the Scope Filter and Conditions panel values. | Each has a copy button, and clicking it copies the JSON. |
| 1.5 | Test tab present | Inspect the tab bar on the detail page. | Tabs include **Test**, alongside the standard Advanced / Notes / Change Log tabs. Its URL is `/extras/webhooks/<pk>/test/`. |
| 1.6 | Edit form has both cards | Click Edit on a Webhook. | Below the Webhook's own fields, a **Conditions** card and a **Scope Filter** card appear, above the tags / custom fields block. |
| 1.7 | Job Hook parity | Repeat 1.3 through 1.6 on a Job Hook. | Identical panels, tab and cards, with the same labels and wording. |
| 1.8 | Standards still work | Edit, Delete, Bulk Edit, Bulk Delete, Notes, Change Log tab, and filtering from the list sidebar, on both models. | All operational. |

---

## 2. Create / edit form: scope section

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 2.1 | Minimal valid trigger | Add a Webhook. Name `qa-minimal`, Object Types = `dcim \| device`, Type Update checked, a valid payload URL. Save. | Saved, redirected to detail. Scope Filter shows `{}`, Conditions shows `[]`. |
| 2.2 | Scope filter fields load on type selection | Add a Webhook. Before selecting an Object Type, look at the **Scope Filter** card. Then select `dcim \| device`. | Before: the card reads "Select one or more object types to load the available scope filter fields." After: the card re-renders (HTMX) with Device filter fields (Location, Status, Role, Tenant and so on) under **Basic** and **Advanced** tabs. |
| 2.3 | Scope filter saved | On the webhook from 2.2, set Location = a specific Campus in the Basic tab. Save. | Detail **Scope Filter** panel shows `{"location": ["<uuid-or-name>"]}`. |
| 2.4 | Scope filter round-trips into the form | Edit the webhook from 2.3. Give the page a moment to settle. | The Location field shows the saved value. It fetches the value from the API after load, so it is briefly blank first, the same behavior as the filter sidebar on any list view. Re-saving without touching it keeps the scope; it may be rewritten from a UUID to the object's name, which is equivalent. |
| 2.5 | Changing object type reloads filters | Edit the webhook from 2.3 and change Object Types to `dcim \| location`. | The Scope Filter card re-renders with the Location model's filters. |
| 2.6 | Advanced tab filter | Add a webhook, select `dcim \| device`, go to the Scope Filter **Advanced** tab, add `status` = `Active` and click **Add Filter**. Save. | The filter is applied and appears in the saved scope. |
| 2.7 | Advanced tab auto-apply on submit | Repeat 2.6 but click **Save** *without* clicking **Add Filter** first. | The pending filter is applied anyway and appears in the saved scope. |
| 2.8 | Empty scope means all objects | Save a webhook with Object Types set and no scope filter. | Scope is `{}`, and it matches every object of that type (verified in section 5). |
| 2.9 | Scope card is shared with custom fields | Open a Custom Field's edit form and compare its Scope Filter card to the Webhook's. | Same markup, same wording, same Basic / Advanced behavior. Both use the shared component; neither has drifted. |

---

## 3. Create / edit form: conditions section

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 3.1 | One dropdown for the whole choice | Edit a Webhook and open the Conditions row's dropdown. | A single **Condition** dropdown listing **Raw expression** first, then the presets: Field changed, Field compare, Field transition, User is, User is not. There is no separate "type" dropdown to answer first. |
| 3.2 | Preset reveals only its own fields | Choose **Field transition**. | Only **Field**, **From** and **To** are visible in that row. Value, Username and Expression are hidden. |
| 3.3 | Switching preset changes fields | In the same row, change the dropdown to **User is**. | Field / From / To hide; only **Username** is visible. Values previously typed into now-hidden inputs are cleared. |
| 3.4 | Raw expression reveals the expression box | Change the dropdown to **Raw expression**. | All parameter inputs hide and a single wide **Expression** input appears. |
| 3.5 | Row height does not change | Switch the dropdown between all six options in turn, watching the row. | The row stays one line at the same height throughout, so the controls below it do not shift under the cursor. Repeat at a narrow window width: the row wraps to a taller stack but stays consistent while switching. |
| 3.6 | Controls do not overlap | With **Field compare** chosen, pick the longest operator (`starts with`) and resize the window from narrow to maximised. | The condition dropdown, Field, Operator, Value, **not** and the delete button never overlap, and the operator label is never cut off. |
| 3.7 | Add and remove rows | Click **Add another Condition** twice, then delete the middle row. | Rows add and remove cleanly, the management form stays consistent, and Save succeeds. The word "and" appears from the second row onwards but not on the first. |
| 3.8 | Multiple conditions saved in order | Save with row 1 = Field changed on `status` and row 2 = expression `username != 'admin'`. | Detail **Conditions** panel shows both rows as JSON, row 1 first. |
| 3.9 | Blank row is dropped, not rejected | Save with one filled condition and one completely untouched row. | Saves. Only the filled condition is stored; the blank row does not appear. |
| 3.10 | Conditions round-trip into the form | Edit the webhook from 3.8. | Row 1 shows Field changed with Field = `status`; row 2 shows Raw expression with its text. Nothing is lost. |
| 3.11 | `not` round-trips | Save with **not** checked on a condition, then re-open for editing. | Stored conditions show `"negate": true` and the checkbox is still checked. |
| 3.12 | **An old-style POST does not clear the new fields** | On a webhook that has a scope and conditions, POST the webhook form the way a pre-feature script would, omitting the conditions and scope inputs entirely (for example with `curl` against the edit URL, sending only the webhook's own fields). | The saved scope and conditions are **unchanged**. A request that predates these fields must not silently wipe them. |

---

## 4. Save-time validation (failure cases)

Each of these must be rejected at save with the stated message, not accepted and discovered later.

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 4.1 | No event type | Save a Webhook with Type Create, Type Update and Type Delete all unchecked. | Rejected: **"You must select at least one type: create, update, and/or delete."** This is existing Webhook behavior, confirmed unchanged. |
| 4.2 | Unknown scope filter parameter | Via API: `PATCH /api/extras/webhooks/<pk>/` with `"scope_filter": {"no_such_param": "x"}` on a webhook watching `dcim.device`. | HTTP 400 on `scope_filter`: **"dcim.Device has no filter parameter(s): no_such_param."** This is the case a FilterSet form silently accepts, so it must not be silently accepted here. |
| 4.3 | Scope param valid for one type but not another | Set Object Types to `dcim.device` **and** `dcim.location` with a Device-only scope parameter such as `device_type`. | Rejected, naming the model that lacks the parameter. Must **not** save with Location left silently unscoped. |
| 4.4 | Same check on bulk edit | Bulk-edit two webhooks to add an object type that makes an existing stored scope invalid. | Rejected the same way. Bulk edit must not be a way around 4.3. |
| 4.5 | Unknown preset key | Via API, PATCH `"conditions": [{"type": "preset", "preset": "nope", "params": {}}]`. | HTTP 400 containing **"Condition 1: unknown preset `nope`."** |
| 4.6 | Missing required preset parameter | UI: choose Field transition, fill Field and From, leave To empty. Save. | Rejected: **"Preset `field_transition` requires parameter `to`."** |
| 4.7 | Non-compiling expression | UI: Raw expression = `data.name ==`. Save. | Rejected, naming the syntax problem, prefixed **"Condition 1:"**. |
| 4.8 | Statement instead of expression | Expression = `{% set x = 1 %}`. Save. | Rejected. Statements are not expressions. |
| 4.9 | Error names the offending row | Save with row 1 = `true` and row 2 = `data.name ==`. | The message contains **"Condition 2"**, not "Condition 1". |
| 4.10 | Two identical webhooks are still refused | Create two Webhooks with the same object type, payload URL and event flags, both with empty scope and conditions. | The second is rejected as a duplicate. The existing uniqueness check still applies when nothing distinguishes them. |
| 4.11 | **Two webhooks to one endpoint are allowed when they differ** | Create two Webhooks with the same object type, payload URL and event flags, but different scope filters (or different conditions). | **Both save.** This is the relaxation that lets one endpoint serve several reasons. Confirm the detail pages show the two different scopes. |

---

## 5. Dispatch: scope and event type matching

For each test, keep the worker log open and the receiver visible.

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 5.1 | In-scope update fires | Webhook W: `dcim.device`, Type Update, scope `location = Campus-A`, no conditions. Edit a device **in** Campus-A (change a field it has, such as comments). Save. | Receiver gets exactly **one** request. |
| 5.2 | Out-of-scope update does not fire | Same webhook. Edit a device in **Campus-B**. | Receiver gets **nothing**, and the worker log records no delivery. |
| 5.3 | Wrong event type does not fire | Webhook with only Type Delete checked. Update an in-scope device. | Nothing fires. |
| 5.4 | Create fires a create trigger | Webhook: `dcim.device`, Type Create, no scope. Create a device. | One request; payload `event` is **`created`**. |
| 5.5 | Disabled webhook never fires | Set the webhook from 5.1 to Enabled = No. Edit an in-scope device. | Nothing fires. |
| 5.6 | Unscoped webhook fires for every object | Scope `{}`. Edit devices in Campus-A and Campus-B. | Both fire. |
| 5.7 | Fires exactly once | Webhook from 5.1. Make a single edit to one in-scope device. | Exactly **one** request, not two. |
| 5.8 | Two triggers on one change | Two enabled webhooks both matching the same device update, each with its own receiver. Edit the device. | **Both** fire, one request each. |
| 5.9 | Wrong model does not fire | Webhook watching `dcim.location`. Edit a Device. | Nothing fires. |
| 5.10 | Scope change takes effect immediately | With a webhook whose scope excludes a device, widen the scope so it matches, then immediately make a qualifying change. | Fires on the very next change, with no stale-cache delay. This guards the per-model scoped-action cache invalidation. |
| 5.11 | New scope on a previously unscoped model | Confirm no scoped action exists for `dcim.location`. Edit a Location (nothing should fire). Now add a scope filter to a Location webhook and edit a Location again. | The second edit is evaluated against the new scope. This guards against a cached "nothing is scoped here" answer never being invalidated. |
| 5.12 | Scope is matched against the post-change state | Webhook scoped to `location = Campus-A`, Type Update. Move a device **out** of Campus-A, then move another device **in**. | Moving out does **not** fire; moving in **does**. Scope is judged on the object after the change. |

---

## 6. Dispatch: delete semantics

Deletes are the case the design is built around, so test them explicitly.

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 6.1 | In-scope delete fires | Webhook: `dcim.location`, Type Delete, scope `name = qa-doomed`. Create a Location named `qa-doomed`, then delete it. | One request; payload `event` is **`deleted`**. Scope was evaluated correctly even though the row is now gone. |
| 6.2 | Out-of-scope delete does not fire | Same webhook. Create and delete a Location named `qa-survivor`. | Nothing fires. |
| 6.3 | Condition on postchange is false, not an error | Type Delete, condition = expression `snapshots.postchange.name`. Delete an in-scope object. | Does **not** fire. Worker log shows a "did not fire" debug line and **no** traceback and no "condition errored" line. |
| 6.4 | Condition on prechange works on delete | Type Delete, condition = expression `snapshots.prechange.name`. Delete an in-scope object. | **Fires.** Prechange data is present on a delete. |
| 6.5 | Field changed on a delete | Type Delete, preset Field changed on `status`. Delete an in-scope object. | Does not fire, and nothing is logged as an error. |

---

## 7. Condition semantics

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 7.1 | Field transition: exact match fires | `dcim.device`, Type Update, preset Field transition (field `status`, from `Staged`, to `Active`). Set a device to Staged and save, then to Active and save. | Fires only on the Staged to Active save. |
| 7.2 | Field transition: wrong destination | Same. Move a device Staged to Planned. | Does not fire. |
| 7.3 | Field transition: wrong origin | Same. Move a device Planned to Active. | Does not fire. |
| 7.4 | No-op re-save does not fire | Same. Open an Active device and save without changing anything. | Does not fire. |
| 7.5 | **Status matched by value, not label** | Confirm the preset in 7.1 uses the status **value**. Then try the display **label** if it differs. | The value matches; the label does not. Behaviour matches the documentation. |
| 7.6 | Field changed fires on any change | Preset Field changed on `comments`. Change a device's comments and save, then change only its serial and save. | Fires on the comments change; not on the serial-only change. Pick a field the model actually has: `dcim.device` has no `description`. |
| 7.7 | Field compare: equality | Preset Field compare (field `status`, operator `=`, value `Active`). Update a device that ends Active, then one that ends Staged. | Fires for the first, not the second. |
| 7.7a | Field compare: every operator | One at a time, use `>`, `>=`, `<`, `<=` against `mtu` on an interface, then `in` (value `Active,Staged`), `contains`, `starts with` and `ends with` against `name`. Trigger a change each time. | Each fires only for a value the operator genuinely matches. Ordering compares numerically when both sides are numbers, so `mtu > 999` is true for 1500. |
| 7.7b | Field compare: dotted field | Field compare (field `status.name`, operator `=`, value `Active`) on an Active device. Then set the field to `nope.deep`. | The dotted path fires. The path leading nowhere does not fire, and the worker log shows **no** error. |
| 7.7c | **`not` inverts a row** | Take the passing case from 7.7 and check **not**. Trigger the same change. | Does not fire. Uncheck it and it fires again. Repeat on a raw-expression row: the same inversion applies. |
| 7.7d | **`not` does not rescue a broken row** | Expression `data.name / 0` with **not** checked. Trigger a change. | Does **not** fire. Inverting a row that errored must not turn the error into a pass. |
| 7.8 | User is | Preset User is with your username. Make a change as that user, then as another. | Fires for the first, not the second. |
| 7.9 | User is not | Preset User is not with some other username. Make a change as yourself. | Fires. |
| 7.10 | All conditions must pass | Row 1 = `true`, row 2 = `false`. Trigger a matching change. | Does not fire. |
| 7.11 | Empty condition list fires for every in-scope change | No conditions. Trigger any in-scope change. | Fires. |
| 7.12 | Truthiness contract | One at a time, set a single expression to `''`, `none`, `0`, `[]`, `{}`. Trigger a change for each. | **None** fire. Only a truthy result passes. |
| 7.13 | Missing key is falsy, not fatal | Expression `data.no_such_field`. Trigger a change. | Does not fire; worker log shows **no** error. |
| 7.14 | Genuine error is contained and recorded | Expression `data.name / 0`. Trigger a change. | Does not fire. Worker log records that condition 1 errored, with the exception text. The change itself completes normally. |
| 7.15 | **One broken trigger does not affect others** | Two webhooks on the same change: A with `data.name / 0`, B with `true`, each with its own receiver. Trigger the change. | B **fires**, A does not, A's error is logged, and neither the change nor B is affected. |
| 7.16 | Filters are available in expressions | Expression `data.name \| upper == '<DEVICE NAME IN CAPS>'`. Trigger a change. | Fires. The shared Jinja filter set is available. |
| 7.17 | Nested value comparison | Expression `data.status.name == 'Active'`, and separately `data.status \| event_value == 'Active'`. | Both fire for an Active device. |
| 7.18 | **Payload is not shared between triggers** | Two webhooks on the same change: A with expression `data.clear()`, B with `data.name`. Trigger the change. | B still fires and still sees its data. One trigger's condition must not be able to mutate what a later one evaluates against. |

---

## 8. Job Hook parity

The mixin is shared, so these confirm the second action type behaves identically rather than re-running every case.

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 8.1 | Job hook runs when its trigger passes | Job Hook with a scope and one passing condition. Trigger a qualifying change. | The receiver job runs; a JobResult appears under Jobs > Job Results. |
| 8.2 | Job hook does not run when scope excludes | Same job hook. Change an out-of-scope object. | The job does **not** run. |
| 8.3 | Job hook does not run when a condition fails | Same job hook with a failing condition. Trigger an in-scope change. | The job does **not** run. |
| 8.4 | Disabled job hook never runs | Set Enabled = No. Trigger a qualifying change. | Nothing runs. |
| 8.5 | Job hook permission is still enforced | Trigger a job hook by a change made by a user **without** run permission on that job. | The job does not run and the worker log records the permission skip. This existing behavior is unchanged. |
| 8.6 | A webhook and a job hook on the same change | One webhook and one job hook, both matching the same change, each with its own scope and conditions. Trigger it. | Both are evaluated independently and both fire. |
| 8.7 | Payload shape unchanged | Compare a body received from a webhook with a scope and conditions against one from a webhook with neither, for the same change. | Identical structure: `event`, `timestamp`, `model`, `username`, `request_id`, `data`, `snapshots`. Narrowing changes *whether* it is sent, never *what* is sent. |
| 8.8 | Job modules reloaded once per task | Three job hooks all matching one change. Watch the worker log. | Job source reload happens **at most once** for that task, not once per job hook. |

---

## 9. Dry-run: Test tab and API

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 9.1 | Test tab renders | Open a Webhook > **Test** tab. | Heading reads **"Test This Webhook"**. A change-log picker and Object type / Object ID inputs are shown. |
| 9.2 | Test against a live object | On a webhook whose only condition is Field compare (`status` `=` `Active`), pick Object type = Device and an Active device. Run Test. | **Would fire: Yes**, scope matched true, and a Conditions table showing the row passed. |
| 9.3 | Live object with a transition condition | Same, but the condition is Field transition. Run against a live object. | **Would fire: No.** A live object is an update in which nothing changed, so a transition cannot pass. |
| 9.4 | Test against a change log entry | Perform a real Staged to Active transition. On a webhook with a matching Field transition condition, pick that change log entry. Run Test. | **Would fire: Yes**, matching what actually happened. |
| 9.5 | **Dry-run fidelity** | For the change in 9.4, compare the verdict against whether the webhook actually fired at the time. | They agree. Repeat with one that did not fire; dry-run also says No. |
| 9.6 | Dry-run dispatches nothing | Run any Test reporting Would fire: Yes, watching the receiver. | The receiver gets **no** request. |
| 9.7 | Per-row results | Two conditions, one passing and one failing. Run Test. | The Conditions table identifies which row failed. |
| 9.8 | Scope reported separately | Scope the webhook to exclude the chosen object. Run Test. | Scope matched shows false and Would fire is No, so the scope is identifiable as the reason. |
| 9.9 | Neither target supplied | Click Run Test with all fields blank. | The form re-renders with **"Choose a change log entry, or an object."** Not a blank form and not a 500. |
| 9.10 | Both targets supplied | Pick both a change log entry and an object type + ID. Run Test. | **"Choose either a change log entry or an object, not both."** |
| 9.11 | Delete change replay | Replay a delete change log entry against a delete-watching webhook. | Returns a verdict without error even though the object no longer exists. |
| 9.12 | Disabled trigger can still be tested | Set Enabled = No and run a Test that would otherwise pass. | Still reports the verdict, and says the trigger is disabled, so it can be built and verified before being turned on. |
| 9.13 | Change-log picker is filtered | Open the picker on a webhook watching only `dcim.device`. | It offers changes for the watched object types, not every change ever recorded. |
| 9.14 | API dry-run: object | `POST /api/extras/webhooks/<pk>/dry-run/` with `{"object_type": "dcim.device", "object_id": "<uuid>"}`. | HTTP 200; body has `scope_matched`, `conditions` (a list of `{index, row, passed, error}`) and `would_fire`. |
| 9.15 | API dry-run: change | Same endpoint with `{"object_change": "<uuid>"}`. | HTTP 200, same shape. |
| 9.16 | API dry-run: bad input | POST `{}`, then POST with both target kinds. | HTTP 400 both times, the second saying **"Provide either `object_type` and `object_id`, or `object_change`, not both and not neither."** |
| 9.17 | Job Hook dry-run | Repeat 9.1 and 9.14 against a Job Hook, at `/extras/job-hooks/<pk>/test/` and `/api/extras/job-hooks/<pk>/dry-run/`. | Same behavior and same response shape. |

---

## 10. REST API

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 10.1 | Fields present on read | `GET /api/extras/webhooks/<pk>/`. | The body includes `scope_filter` and `conditions`. |
| 10.2 | **Fields are writable** | `PATCH` a webhook with a populated `scope_filter` and `conditions`. Re-read it. | Both persist. A scope accepted and silently dropped is the worst outcome here, because it produces a trigger the client believes is narrow that in fact fires for everything. |
| 10.3 | Create with both fields | `POST /api/extras/webhooks/` with `scope_filter` and `conditions` set. | Created with both stored, and validated as in section 4. |
| 10.4 | Presets catalog | `GET /api/extras/webhooks/presets/`. | HTTP 200 with exactly five entries, keyed `field_transition`, `field_changed`, `field_compare`, `user_is`, `user_is_not`. `field_transition` lists parameters `field`, `from`, `to`, and `field_compare` publishes its operator choices. Each key matches its UI label. |
| 10.5 | Presets requires auth | Call `/presets/` unauthenticated. | 401 or 403, not 200. |
| 10.6 | Presets on job hooks | `GET /api/extras/job-hooks/presets/`. | Identical catalog. |
| 10.7 | Existing filters unaffected | `?content_types=dcim.device`, `?enabled=false`, `?q=<partial name>`. | All behave as before the feature. |
| 10.8 | OpenAPI schema | `GET /api/docs/` and find the Webhook schema. | `scope_filter` and `conditions` appear and are not marked read-only. The dry-run and presets endpoints are documented. |
| 10.9 | **CSV round-trip** | Export webhooks to CSV (`?format=csv`), including one with a populated scope and conditions. Delete it, then re-import the CSV. | Record what happens. An empty cell must come back as an empty scope or empty condition list rather than an error, because the serializer normalises that case. If a populated scope or condition list does **not** survive, the failure must be a clear validation error rather than a 500 or a silently emptied field. Note the outcome here; this is the item most likely to need a documentation change. |

---

## 11. Permissions

There is no separate permission for scope and conditions. They are fields on the Webhook and Job Hook, so the existing permissions govern them.

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 11.1 | View-only user can see the fields | Grant only `extras.view_webhook`. Open a webhook's detail page. | The Scope Filter and Conditions panels are visible. Add / Edit / Delete are disabled or absent. |
| 11.2 | **View-only user can run dry-run** | As that user, open the Test tab and test against an object they can view. | Works. Dry-run must **not** require change permission, because it writes nothing. |
| 11.3 | Dry-run needs view on the trigger | As a user with **no** `extras.view_webhook`, POST to `/dry-run/`. | 403 or 404, not a result. |
| 11.4 | Dry-run needs view on the target | As a user with `extras.view_webhook` but no `dcim.view_device`, dry-run against a Device. | 403 or 404, not a result. |
| 11.5 | Changing a scope needs change permission | Grant only `extras.view_webhook`, then PATCH `scope_filter` via the API. | Rejected. Editing the trigger requires `extras.change_webhook`. |
| 11.6 | Job hook equivalent | Repeat 11.2 and 11.5 with `extras.view_jobhook` and `extras.change_jobhook`. | Same behavior. |
| 11.7 | Constrained permission | Create an ObjectPermission on Webhook constrained to one webhook by name. | Only that webhook is visible and editable, and only its Test tab is reachable. |

---

## 12. Backward compatibility (must not regress)

The whole feature is additive. These prove it.

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 12.1 | Untouched webhook is unchanged | Configure a Webhook with Type Update and object type Device, leaving scope and conditions empty. Edit a device. | Fires exactly as it did before the feature existed, once. |
| 12.2 | **Upgrade leaves every existing webhook firing** | On a database predating the feature, apply migrations, then trigger each pre-existing webhook. | All still fire. The new fields default to empty, and empty means "no change in behavior". |
| 12.3 | Narrowing takes effect on save | Add a scope filter to the webhook from 12.1 that excludes the device you just edited. Edit it again. | Now does not fire. There is no intermediate state in which it fires on both the old and the new terms. |
| 12.4 | Clearing the fields restores the old behavior | Clear the scope filter and conditions. Edit the device again. | Fires again, exactly as in 12.1. |
| 12.5 | A webhook cannot have all three types clear | Try to save a Webhook with Type Create, Type Update and Type Delete all unchecked. | Rejected. Scope and conditions narrow an action; they are not a replacement for its event flags. |
| 12.6 | Job hooks unaffected | With no scope or conditions set, verify an existing Job Hook still triggers on its own configuration. | Unchanged. |
| 12.7 | Change logging unaffected | Make several changes with no scope or conditions anywhere. Check the Change Log. | ObjectChange records are created exactly as before. |
| 12.8 | Migration applies and reverses | `nautobot-server migrate`, then `nautobot-server migrate extras 0145`. | `extras.0146_conditional_trigger` applies cleanly, and reverses cleanly with Nautobot still starting and webhooks still firing. |

---

## 13. Performance and caching

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 13.1 | Zero-scope cost | With **no** webhook or job hook carrying a scope filter, bulk-edit 100 Devices. Compare against the same operation on a model nothing watches. | No perceptible slowdown. The per-model lookup is cached and adds no queries. |
| 13.2 | Bulk edit with scopes | With 5 enabled scoped webhooks on Device, bulk-edit 100 Devices. | Completes without timeout. Note the wall time. |
| 13.3 | Bulk edit fires per object | Bulk-edit 5 in-scope devices with a matching webhook. | The receiver gets 5 requests. |
| 13.4 | Bulk edit respects scope | Bulk-edit 5 devices where only 2 are in scope. | The receiver gets **2** requests, not 5. |
| 13.5 | **M2M multi-fire: accepted behavior** | On a webhook watching `dcim.device`, change an object and its tags in one save. | It may fire **more than once**. This is documented accepted behavior; confirm the docs say so and that nothing errors. |

---

## 14. Regression checks on shared surfaces

The feature touched app-wide code paths. These are the specific places it broke during development.

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 14.1 | **Advanced filter form on any model** | Devices list > Filter > **Advanced** tab. Open the field dropdown. Repeat on Locations and IP Addresses. | The form renders, with no 500 and no `KeyError`. |
| 14.2 | Global search unaffected | Search for a device name. | Normal results. |
| 14.3 | Custom field scope filter still works | Create a Custom Field with a scope filter, then confirm it appears only on in-scope objects. | Unchanged. The scope filter component is shared, so this proves the sharing did not break the original user. |
| 14.4 | Custom field required-plus-scope behavior | On a Custom Field's form, tick **Required**. | The scope filter card is replaced by its explanation rather than offering filter fields. This is existing behavior and must survive the shared endpoint. |
| 14.5 | HTMX endpoints respond | Watch the browser network tab while changing object types on a Custom Field form, a Webhook form and a Job Hook form. | Each issues a request to its own `scope-filter-fields` URL and swaps in the right markup. Three separate URLs, one shared implementation. |
| 14.6 | Documentation builds and links | Open the Conditional Triggers and Condition Expressions docs, and follow the cross-links from the Webhooks and Job Hooks pages. | All pages render and all links resolve. |
| 14.7 | Webhook and Job Hook create/edit forms share a template | Compare the two create forms side by side. | Same card order and same wording. Both render from one shared template. |

---

## 15. Security

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 15.1 | Sandbox blocks introspection | Set an expression to each of `''.__class__`, `data.__class__.__mro__`, and `''.__class__.__mro__[1].__subclasses__()`. Save and trigger. | Each either fails validation at save or evaluates falsy. **None** cause a fire, and none expose Python internals. |
| 15.2 | No ORM reach from an expression | Expression referencing a manager or queryset attribute, such as `data.objects` or `data.query`. | Falsy, with no database access and no error reaching the user. |
| 15.3 | Preset parameters are data, not code | Field compare with value `{{ 7 * 7 }}`, against an object named `49`. | Does **not** fire. The parameter is compared literally, never rendered as a template. |
| 15.4 | Expression is validated before storage | Save an expression referencing an undefined filter, such as `data.name \| no_such_filter`. | Rejected at save time, not at event time. |
| 15.5 | SSRF check still applies | Try to save a Webhook with a loopback payload URL. | Rejected, whether or not it carries a scope or conditions. |
| 15.6 | Docs state the permission warning | Read the Conditional Triggers docs Permissions section. | It states that permission to edit webhooks and job hooks should be treated with the same sensitivity as permission to edit webhook body templates. |

---

## 16. Sign-off checklist

| # | Item | Expected |
|---|------|----------|
| 16.1 | All sections 1 to 15 executed | No unexplained failures. |
| 16.2 | Worker log reviewed end to end | Only expected delivery, "did not fire" and deliberate condition-error lines. No unhandled tracebacks. |
| 16.3 | Nautobot log reviewed | No unhandled exceptions from signal receivers during any test. |
| 16.4 | Known limitations confirmed as documented | CSV round-trip (10.9) and M2M multi-fire (13.5) behave as documented rather than as surprises. If 10.9 revealed something the docs do not cover, the docs are updated before sign-off. |
| 16.5 | Zero-scope baseline confirmed | 13.1 shows no regression for installations that never set a scope or a condition. |
| 16.6 | Upgrade path confirmed | 12.2 shows every pre-existing webhook and job hook still fires after migrating. |
