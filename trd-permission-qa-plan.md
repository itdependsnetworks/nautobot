# Permission Policies — Manual QA Test Plan

Scope: the Permission Policies feature described in `trd-permission.md` on branch `vibe-original-permissions` (base `next`, Nautobot 3.3.0a0).

Setup assumed by every section unless a step says otherwise:

- A development stack with PostgreSQL, the branch migrated (`nautobot-server migrate`), and a superuser (`admin`).
- Demo data loaded once with `nautobot-server create_permission_policy_demo_data`. It creates users `ntc-operator`, `it-amer`, `it-emea`, `it-apac`, `telco-owner`, `job-runner`, all with password `nautobot`, three `demo-*` policies and seven `demo-*` assignments. `--flush` removes them again. Never run it against production data.
- An API token for `admin`. In examples, `$TOKEN`, and `$HOST` is the base URL.
- "Policies list" means Extensibility > Users > Permission Policies (`/users/permission-policies/`); "Assignments list" means Extensibility > Users > Policy Assignments (`/users/permission-policy-assignments/`).

## 1. Policy CRUD (UI)

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 1.1 | Navigation entries | As admin open the Extensibility menu. | Under the Users group, below Saved Views, two items: "Permission Policies" and "Policy Assignments". |
| 1.2 | Create a policy with no parameters | Policies list > Add. Name `qa-reference`, description `QA`. Add rule: object type `DCIM \| location`, action `view`, empty constraint template. Add rule: `DCIM \| location type`, action `view`, empty template. Create. | Redirect to the detail page. Rules panel lists two rows (location, location type), each with actions `view` and constraints badge `no constraint (all objects)`. Parameters panel is empty. Assignments panel is empty. |
| 1.3 | Empty form load | Policies list > Add. Do not add anything. | No parameter row and no rule card are shown; only the "Add parameter" and "Add rule" buttons. The Kind help text under the parameters table explains object vs string parameters. |
| 1.4 | Create with a parameter and two rules | Add policy `qa-tenant`. Add parameter `tenant`, kind Object reference, target `Tenancy \| tenant`, Multiple checked. Add rule: `DCIM \| device`, action `view`; in the suggested paths click `tenant`. Add rule: `DCIM \| interface`, action `view`; click `device__tenant`. Create. | Detail page: Parameters table shows `tenant`, `object`, `Tenancy \| tenant`, Multiple = green check. Rules table shows device with path map `tenant → tenant (in)` and interface with `tenant → device__tenant (in)`. Constraint templates show `{"tenant__in": "{{ tenant }}"}` and `{"device__tenant__in": "{{ tenant }}"}`. |
| 1.5 | Edit a policy | Open `qa-tenant` > Edit. Change description to `edited`, add action `change` to the device rule. Update. | Detail shows description `edited`, device rule actions `view`, `change`. Interface rule unchanged. The edit form loaded with exactly one parameter row and two rule cards, no blank extras. |
| 1.6 | Policy with no rules | Policies list > Add, name `qa-empty`, add no rule, Create. Then create `qa-empty` through the API without rules, and open Assignments list > Add. | The UI refuses with "Policy 'qa-empty' has no rules and grants nothing; it cannot be assigned." The API-created empty policy is not offered in the Policy dropdown (only policies with rules), and `POST /api/users/permission-policy-assignments/` naming it returns 400 with the same message. |
| 1.7 | Delete a policy with assignments is refused | Open `demo-regional-it-operator` > Delete > confirm. | Deletion refused with the standard protected-object message naming the dependent assignments (`demo-it-amer`, `demo-it-emea`, `demo-it-apac`). Policy still exists. |
| 1.8 | Delete a policy without assignments | Delete `qa-reference` (no assignments). | Policy removed; list no longer shows it. Change log records the deletion. |
| 1.9 | Standards | List filter by name, search `q`, bulk edit description, bulk delete, change log tab, table column configuration. | All operational. Object types column shows comma-separated types like "DCIM \| device, DCIM \| interface" truncated with an ellipsis after 15 words. Bulk edit and bulk delete confirmation tables show the Parameters/Rules/Assignments counts (no dashes). |
| 1.10 | Object type allowlist | On the rule form open the object type dropdown and search `permission policy`, `policy rule`, `session`. | `Users \| permission policy`, `Users \| policy parameter`, `Users \| policy rule`, `Users \| policy assignment` are offered; `Sessions \| session` and `Contenttypes \| content type` are not. |

## 2. Parameters

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 2.1 | Kind toggles target object type | Add parameter row. Set Kind to `String`. | The Target object type cell becomes invisible and is cleared. Switching back to `Object reference` shows it again. |
| 2.2 | Object parameter requires a target | Parameter `tenant`, kind Object reference, no target. Add a rule using `{{ tenant }}`. Create. | Form does not save. Under the target cell: "An 'object' parameter must reference a target object type." shown exactly once. |
| 2.3 | Invalid parameter name | Parameter named `Tenant Name`. | Save refused with the name validation message (lowercase letters, digits and underscores, starting with a letter). |
| 2.4 | Duplicate parameter names | Two parameter rows both named `tenant`. | Save refused; the parameters table shows the duplicate error alert ("Please correct the duplicate data for name."). |
| 2.5 | Unused parameter is refused | Policy with parameter `prefix` (string) and one rule whose template is `{}`. Create. | Save refused with alert "Parameter 'prefix' is not used by any rule; reference '{{ prefix }}' in a rule's constraint template or remove the parameter." |
| 2.6 | Rule need not use every parameter | Policy with parameters `region` (object, Location, single) and `tenant_name` (string). Rule A: `DCIM \| device`, `{"location__in_tree": "{{ region }}"}`. Rule B: `Circuits \| circuit`, `{"tenant__name": "{{ tenant_name }}"}`. Create. | Saves. Rules table marks rule A with `tenant_name → not scoped by this parameter` and rule B with `region → not scoped by this parameter` (yellow badges). |
| 2.7 | Add a parameter to an existing policy in one edit | Edit `demo-regional-it-operator`. Add parameter `tenant_name` (string). Add rule `IPAM \| VRF`, `view`, template `{"tenant__name": "{{ tenant_name }}"}`. Update. | Saves in one step. A warning message lists the three `demo-it-*` assignments: "3 assignment(s) of this policy now lack a value for a parameter and grant nothing until they are updated: demo-it-amer (missing tenant_name); ...". |
| 2.8 | Placeholder inside a string is rejected | Rule template `{"name__istartswith": "core-{{ prefix }}"}`. | Save refused: "a placeholder must be a complete value such as "{{ name }}"; found: 'core-{{ prefix }}'". |
| 2.9 | Undeclared placeholder | Rule template `{"tenant__in": "{{ nope }}"}` with no parameter `nope`. | Save refused: "the template references undeclared parameter 'nope'". |

## 3. Rules

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 3.1 | Standalone rule page | Policy Rules list > Add. Policy `qa-reference`, object type `Extras \| status`, action `view`, empty template. Create. | Redirect to the rule's detail page showing policy, object type, actions and the empty template. The policy's detail page now lists three rules. |
| 3.2 | Same object type in two rows | Two rule cards both containing `DCIM \| device`. Create. | Save refused; rules section alert says the object type appears in more than one rule. |
| 3.3 | No action | Rule with object type but no action and no additional action. | Save refused: "At least one action must be selected." |
| 3.4 | Custom action | Rule `Extras \| job`, actions `view`, additional action `run`. | Saves; Rules table shows action badges `view`, `run`. |
| 3.5 | Path validated at save | JSON tab template `{"nonexistent__in": "{{ tenant }}"}` on a device rule. | Save refused; error names `dcim.device` and the invalid path. |
| 3.6 | Wrong lookup for a multi-valued object parameter | Device rule template `{"tenant": "{{ tenant }}"}` where `tenant` is Multiple. | Save refused: "parameter 'tenant' accepts multiple values and requires the 'in' lookup, not 'exact'." |
| 3.7 | String parameter path must end at a field | Rule `{"tenant__in": "{{ tenant_name }}"}` with `tenant_name` a string parameter. | Save refused: "parameter 'tenant_name' is a string parameter but path 'tenant' ends at a relation." |
| 3.8 | Multi-valued relation path | JSON template `{"tags__name": "core"}` on a device rule (no parameter). Create, then Edit and open the Builder. | Saves: a literal path follows the same rules as a hand-written object permission. The builder flags the row red ("is not a valid lookup path ... Choose another field or remove this condition.") because the resolver and editor only handle single-valued relations, and the JSON is left untouched. A *parameter* path across `tags` is refused at save. |
| 3.9 | Remove a rule on edit | Edit `qa-tenant`, click Remove rule on the interface card, Update. | Detail shows only the device rule; the interface `PolicyRule` is deleted (API `GET /api/users/policy-rules/?policy=qa-tenant` returns one result). |

## 4. Suggested parameter paths

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 4.1 | Suggestions per object type | New policy, parameter `tenant` (object, Tenant, multiple). Add rule, select `DCIM \| interface`. | Without saving, the card shows "Suggested parameter paths" with `device__tenant` first (breadcrumb "Device › Tenant"), and longer paths under a "N longer paths" disclosure. |
| 4.2 | Use a suggestion | Click the `device__tenant` button. | Constraint template becomes `{"device__tenant__in": "{{ tenant }}"}`; the Builder shows one row with source `Param` and parameter `tenant`. Clicking a different suggestion replaces that row instead of adding a second. |
| 4.3 | No path | Rule object type `Extras \| status`, parameter `tenant`. | Badge "No path from Extras \| status to Tenancy \| tenant" with the hint to leave the parameter out of this rule's template or move the object type to its own row. Policy can still be saved if the template does not use `tenant`. |
| 4.4 | Suggestions follow parameter edits | With a rule card open, rename the parameter from `tenant` to `owner` in the parameters table. | The rule card's suggestions update to `{{ owner }}` without a save. Adding or removing a parameter row also refreshes every rule card. |
| 4.5 | Tree target suggests `in_tree` | Parameter `region` (object, `DCIM \| location`, single). Rule `DCIM \| device`. | Suggested path is `location` with lookup `in_tree`; using it writes `{"location__in_tree": "{{ region }}"}`. |
| 4.6 | Suggestions after JSON edit conflict | Switch to JSON tab, enter `[{"name": "a"}, {"name": "b"}]`, then click a suggestion. | Inline red notice under the suggestions: "The constraint template is not a single JSON object; add the path in the JSON tab." No browser alert; template unchanged. |

## 5. Visual constraint editor

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 5.1 | Default state | Add rule, select `DCIM \| device`. | Editor shows Builder tab active, JSON tab available, "All of" group with "No conditions.", buttons Add condition and Add "any of" group, badge "No constraint: every object of this type matches." |
| 5.2 | Builder without object type | Add rule, select no object type. | Builder shows "Select an object type to build a constraint." |
| 5.3 | Field picker | Add condition, click "Choose a field…". | A dropdown opens under the button (not clipped by the card or the panel below), with a filter box focused and the device fields listed; relations show a caret. Expand `tenant`, choose `tenant__name`. Picker closes, focus returns to the button, row path shows `tenant__name`, lookup list populates (`is`, `is (case-insensitive)`, `contains`, ...). |
| 5.4 | Picker keyboard and dismissal | Open the picker; press Escape. Open again; click outside. | Picker closes both times; clicking inside the filter box does not close it. |
| 5.5 | Literal value | Path `tenant__name`, lookup `contains`, type `core` in the value box. | JSON tab shows `{"tenant__name__icontains": "core"}`. Switch to JSON and back to Builder: the row still shows `core`. |
| 5.6 | Relation value widget | Path `tenant`, lookup `is one of`. | Value cell renders an object selector (select2 with API search) and selected tenants appear as pks in the JSON. Reloading the Builder tab keeps the selected tenants shown by name. |
| 5.7 | Parameter source | Row path `tenant`, lookup `is one of`, source `Param`, parameter `tenant`. | JSON `{"tenant__in": "{{ tenant }}"}`. The `Param` option appears only while the policy has at least one named parameter (delete the parameter row: the option disappears on new rows). |
| 5.8 | `$user` source | Policy rule for `Extras \| job result`; row path `user`. | Source list offers `$user`; choosing it writes `{"user": "$user"}` and the value cell reads `$user the requesting user`. For path `tenant` the `$user` option is not offered. |
| 5.9 | "Any of" groups | Add "any of" group; add a condition in each. | JSON becomes a list of two objects separated by "— or —" in the builder; removing a group removes its object. |
| 5.10 | Invalid JSON locks the builder | JSON tab: type `{not json`. | Builder tab shows warning "The JSON is not valid; fix it in the JSON tab. The builder is disabled and the JSON is left unchanged."; JSON is not rewritten. Fixing the JSON re-enables the builder. |
| 5.11 | Unrepresentable constraint is preserved | JSON tab: `{"tags__name": "core", "nested": {"a": 1}}`. Save the policy (as an ObjectPermission-style hand-written constraint on a valid object type it may be refused by validation; use an object type where `tags__name` is valid but expect refusal). | Builder locks with "contains a nested object the builder cannot show". The textarea value is byte-for-byte what was typed. |
| 5.12 | Invalid path after object type change | Row with path `device__tenant`; then change the row's object type from Interface to Device. | Row turns red with "'device__tenant' is not a valid lookup path for dcim.Device ... Choose another field or remove this condition."; no 400 errors in the browser console. |
| 5.13 | Row tools accessible names | Inspect the lookup, source and parameter selects and the picker filter box. | Each has an `aria-label` (Lookup, Value source, Parameter, Filter fields); tab buttons carry `role="tab"` and `aria-selected`; the picker has `role="dialog"`. |
| 5.14 | Editor on formset-added rows | Add two rules with "Add rule". | Each card has its own working editor and picker; tabs on card 2 do not toggle card 1. No "Cannot read properties of null (reading 'current')" errors in the console. |

## 6. Assignments

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 6.1 | Parameter fields follow the policy | Assignments list > Add. Before choosing a policy the Parameter values card reads "Select a policy to enter its parameter values." Choose `demo-regional-it-operator`. | Card swaps to fields `region` (location selector) and, if 2.7 was done, `tenant_name` (text). Choosing a policy without parameters shows "This policy declares no parameters." Clearing the policy shows the initial hint again. |
| 6.2 | Create an assignment | Name `qa-amer-2`, policy `demo-regional-it-operator`, region `AMER`, user `it-amer`. Create. | Detail page: Parameter values panel shows `Region: AMER (Region)` as links; Assigned to shows Users `it-amer`; Generated constraints panel lists the rendered records. `ObjectPermission` count unchanged (`GET /api/users/permissions/?limit=1` count before and after). |
| 6.3 | Missing required value | Create assignment for `demo-regional-it-operator` leaving region empty. | The browser submits (no silent client-side block); the form comes back with "This field is required." under the region field. |
| 6.4 | Single vs multiple values | API: `POST` assignment for `demo-job-runner` (parameter `jobs` multiple) with `"parameter_values": {"jobs": "<one pk>"}`. | 400: "Parameter 'jobs' accepts multiple values and requires a non-empty list." |
| 6.5 | Wrong target type | API: assignment for `qa-tenant` with `"tenant": ["<a Location pk>"]`. | 400 stating the value does not reference an existing object of the target type. |
| 6.6 | Stored values are canonical | API: `PATCH` an assignment with `{"parameter_values": {"tenant": ["<UPPERCASE UUID>"]}}`. | 200; `GET` shows the pk lowercase in a list. |
| 6.7 | Disable an assignment | Edit `qa-amer-2`, uncheck Enabled. | Detail Enabled shows a red X. Log in as `it-amer` in another browser: device list is empty (or only what other assignments grant) on the next request; no delay, no cleanup step. |
| 6.8 | Assignment list badges | After 2.7, open the Assignments list. | Each `demo-it-*` row's Parameter values column shows `region: <pk>` and a yellow badge `missing value: tenant_name`. Rows for complete assignments show none. |
| 6.9 | Incomplete assignment detail | Open `demo-it-amer` after 2.7. | Yellow alert at the top: "This assignment supplies no value for parameter(s) tenant_name and therefore grants nothing. Edit it to supply the missing value(s)." Generated constraints panel is replaced by a red alert "This assignment cannot be rendered: No value supplied for parameter 'tenant_name'." Reloading the page does not stack toasts. |
| 6.10 | Supplying the value restores access | Edit `demo-it-amer`, enter `tenant_name` = `Network to Code`, Update. | Alert gone; Generated constraints shows a `IPAM \| VRF` row with `{"tenant__name": "Network to Code"}`; `it-amer` sees devices again on the next request. |
| 6.11 | Standards | Bulk edit (enabled, description), bulk delete, filters (policy, users, groups, enabled), change log. | Operational. Bulk edit offers only Enabled and Description. |

## 7. Preview tab

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 7.1 | Policy preview before values | Open `demo-regional-it-operator` > Preview tab. | Form with `region` selector. Table has one row per object type (device, rack, interface, location, power panel, rack group, ...) with the templates showing `"{{ region }}"` as written, Matches and Sample showing a dash. Footer text starts "One row per object type." |
| 7.2 | Policy preview with values | Select region `APAC`, Run preview. | Each row shows a green count badge and up to ten sample links followed by "… and N more <plural>" linking to the filtered list. Device count badge links to `/dcim/devices/?location=<APAC pk>`. A rule with no matches (e.g. rack group) shows a red `0` badge whose tooltip reads "No objects match. Check the lookup path." and a dash for Sample. |
| 7.3 | Parameterless policy previews immediately | Open `nautobot-default-reference-data-viewer` > Preview. | No form; the table already shows counts for every reference model and constraints badge `no constraint (all objects)`; count links go to the unfiltered lists. |
| 7.4 | Invalid values | Submit the preview form with the region cleared. | The form submits and comes back with "This field is required." under the region field; the table still shows the placeholder rows. |
| 7.5 | Sample is permission-limited | As a user with `users.view_permissionpolicy` but `dcim.view_device` limited to one location, run the preview for `demo-regional-it-operator` with region `APAC`. | Device count covers all APAC devices; the Sample lists only devices the user may view (fewer than the count) and the "more" link opens the list which the user's own permission then filters. |
| 7.6 | Assignment preview | Open `demo-it-apac` > Preview. | Same table using the stored values, no form. Count links for tree-scoped constraints go to `?location=<pk>`; an `exact` location constraint (e.g. `{"location": "<pk>"}` on a hand-written test policy) shows a count with no link. |
| 7.7 | Column configuration | Click the cog on the Preview table. | Drawer "Table Configuration" lists Object type, Actions, Constraints, Matches, Sample (first 10). Uncheck Sample, Save. Page shows the table without Sample; Reset restores. No "Definition (JSON)" column here. |
| 7.8 | Compact constraints | Any preview row with a short constraint; one with a long one (e.g. five keys). | Short constraints render on one highlighted line; long ones render as pretty-printed JSON. |

## 8. Generated constraints panel

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 8.1 | Grouped records | Open `demo-it-apac`. | Generated constraints has one row per distinct (actions, constraints) pair: `DCIM \| device, DCIM \| power panel, DCIM \| rack, DCIM \| rack group` share one row with `view add change delete` and `{"location__in_tree": "<APAC pk>"}`; interface and location are separate rows. Footer explains the grouping and the Configure button. |
| 8.2 | Definition (JSON) column | Cog > check "Definition (JSON)" > Save. | Column appears; each cell shows the record name collapsed (`demo-it-apac (1)`); clicking expands JSON with keys `actions`, `constraints`, `enabled`, `name`, `object_types` (values like `dcim.device`). Uncheck to hide again. Default state (no saved preference) hides it. |
| 8.3 | API constraints endpoint matches | `GET /api/users/permission-policy-assignments/<demo-it-apac pk>/constraints/`. | 200 with `rules[]` each holding `content_type` like `dcim.device`, `actions`, `permissions` like `dcim.view_device`, and `constraints` equal to the panel's values. For an incomplete assignment (6.9) the endpoint returns 400 with the render error. |

## 9. Effective access

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 9.1 | Own access page | Log in as `it-apac`. Profile menu > Profile > Access tab (`/user/access/`). | Summary "You have explicit access to N object types through 0 stored permission grants and M policy assignment grants." Table rows list `dcim.view_device` etc. with badge `Policy assignment`, source `demo-it-apac` (plain text, not a link, because the user cannot view assignments), policy `demo-regional-it-operator`, compact constraints, and a List column with "view list" links where a filter exists. |
| 9.2 | Both sources | As admin create an ObjectPermission `qa-locations` (view on `dcim.location`, no constraint) for `it-apac`. Reload the Access tab as `it-apac`. | A row `dcim.view_location` with badge `Permission` and source `qa-locations` appears beside the policy rows. |
| 9.3 | Superuser banner | Log in as admin, open Access tab. | Blue banner "You are a superuser: all permissions are implicitly granted. The table lists only explicit grants." |
| 9.4 | Incomplete assignment on access page | After 2.7 and before 6.10, open `it-amer`'s Access tab. | Yellow alert "You are in policy assignment(s) that grant nothing because a parameter value is missing: demo-it-amer (missing tenant_name)" and no `dcim.view_device` row from that assignment. |
| 9.5 | Admin view of another user | As admin, Admin > Users > `it-apac` > "Effective access" link (`/users/<pk>/access/`). | Page titled "Effective Access: it-apac" with the same table. As a user with only `users.view_user`, the page returns 403; with `users.view_user`, `users.view_objectpermission` and `users.view_policyassignment`, 200. Unknown pk returns 404. |
| 9.6 | API | `GET /api/users/users/effective-access/` as `it-apac`'s token; `GET /api/users/users/<other pk>/effective-access/` as a user without the three permissions. | First: 200 with `grants[]` each carrying `permission`, `object_type`, `action`, `constraints`, `source.type` (`policy_assignment` or `objectpermission`). Second: 403. Unknown pk with permissions: 404. |

## 10. Enforcement

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 10.1 | Region scope in the UI | Log in as `it-apac`. Open Devices. | Only devices whose location is APAC or a descendant (SYD01, TYO01, ...). Open a device in AMER by URL: 404. Racks, power panels, interfaces are limited the same way. The Locations list shows every location, because the demo also assigns the reference-data policy, which grants locations without constraint: the union of permissions widens the region scope, as documented. |
| 10.2 | Region scope in the API and GraphQL | With `it-apac`'s token: `GET /api/dcim/devices/`; GraphQL `{ devices { name location { name } } }`. | Same device set as 10.1 in both. |
| 10.3 | Equivalence with a hand-written permission | Create ObjectPermission `qa-equiv` for a new user `qa-user` with `dcim.device` `view` and constraints `{"location__in_tree": "<APAC pk>"}`; compare the device list with `it-apac`'s. | Identical device sets. |
| 10.4 | Multi-valued parameter | Log in as `job-runner`. Jobs list. | Only "Export Object List" and "Import Objects" jobs are visible with a Run button; Job Results show only the user's own results; Job Queues are all visible. |
| 10.5 | Unparameterized policy | Log in as `telco-owner`. | Full access to circuits, providers, circuit types, circuit terminations; read access to locations; no access to devices. |
| 10.6 | `$user` passthrough | As `job-runner`, run an export job, then open Job Results. | The new result is visible; results run by `admin` are not. |
| 10.7 | Change takes effect at once | While logged in as `it-apac`, have admin disable `demo-it-apac`. Reload the device list as `it-apac`. | Empty list immediately; re-enable, reload: devices return. No `ObjectPermission` rows created or deleted at any point. |
| 10.8 | Broken assignment fails closed | Repeat 2.7 without 6.10; log in as `it-amer`. | Device list empty (nothing from that assignment); server log contains "Skipping policy assignment demo-it-amer". Nothing is granted unconstrained. |
| 10.9 | Derivation cost | In `nautobot-server nbshell`, call `derive_policy_permissions(user)` once to warm the ContentType cache, then wrap a second call in `CaptureQueriesContext`. Do it for `it-apac` and for a user with no assignments. | With assignments: 2 queries (assignments, then rules). Without: 1 (the assignments select). The first call in a fresh process pays one extra query per distinct content type while the cache fills. |

## 11. Built-in policies and demo data

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 11.1 | Seeded policies exist | Policies list after migrate. | `nautobot-default-tenant-device-viewer`, `nautobot-default-tenant-device-operator`, `nautobot-default-reference-data-viewer`, `nautobot-default-export-job-runner` exist. No assignments and no groups are seeded. |
| 11.2 | Seeded definitions validate | Assignments list > Add: each built-in policy is offered; the export job runner policy previews immediately with `{"user": "$user"}` on job results. | All four are assignable; previews show counts, none show validation errors. |
| 11.3 | Migration is idempotent and respects edits | Rename `nautobot-default-reference-data-viewer` to `qa-renamed`. Run `nautobot-server migrate users 0012` then `migrate`. | No error. `qa-renamed` still exists with its edit; `nautobot-default-reference-data-viewer` is re-created by the seed migration; assignments (if any) are untouched. |
| 11.4 | Demo data command | Run `nautobot-server create_permission_policy_demo_data` twice. Create an assignment `qa-amer-2` of `demo-regional-it-operator` by hand, run `--flush`, delete `qa-amer-2`, run `--flush` again. | Second run reports no duplicates (upserts). The first `--flush` refuses: "Cannot flush: assignment(s) not created by this command still use a demo policy: qa-amer-2. Delete them first." The second removes the six demo users, their groups, three `demo-*` policies and seven `demo-*` assignments, and leaves built-in policies alone. |

## 12. Model field introspection API (constraint editor backend)

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 12.1 | Root model gate | As a user with no dcim permissions: `GET /api/core/model-fields/?content_type=dcim.interface`. | 403 "You do not have permission to browse dcim.interface." After granting `dcim.view_interface`: 200 with `fields[]`; the `device` entry has `expandable: false` until `dcim.view_device` is granted too. |
| 12.2 | Hop gate | With `dcim.view_interface` only: `?content_type=dcim.interface&prefix=device`. | 403 naming `dcim.device`. With `dcim.view_device` as well: 200, `model` = `dcim.device`, paths like `device__tenant`. |
| 12.3 | Bad inputs | `prefix=tags` (many-to-many); `content_type=nope.nope`; missing `content_type`. | 400 "crosses a multi-valued relation"; 404 "not a known content type"; 400 "required". |
| 12.4 | Lookups and validation | `GET /api/core/model-fields/lookup-choices/?content_type=dcim.device&path=tenant`; `GET /api/core/model-fields/validate-path/?content_type=dcim.device&path=nope`. | First: select2 envelope with `results` starting `exact`, `in`, then `in_tree` is absent (tenant is not a tree); for `path=location` `in_tree` is present. Second: 200 with `valid: false` and a `detail`. |
| 12.5 | Value widget with value | `GET /api/core/model-fields/value-widget/?content_type=dcim.device&path=tenant&lookup=in&name=v&value=<pk1>&value=<pk2>`. | HTML select with class `nautobot-select2-api`, both pks present and `selected`. For `path=name&lookup=icontains&value=core-`: input with `value="core-"`. |

## 13. Tree lookup (provisional)

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 13.1 | Descendants included | `it-apac` opens Devices (constraint `location__in_tree` = APAC). | Devices at APAC itself and at every descendant location (countries, sites, rooms) are listed; devices in AMER are not. |
| 13.2 | On the tree model itself | Create user `qa-tree` with a single object permission `dcim.location` `view` and constraint `{"pk__in_tree": "<APAC pk>"}`. List locations as that user. | APAC and all descendants visible; AMER and other siblings not. (`it-apac` cannot be used here because the reference-data policy also grants every location.) |
| 13.3 | Non-tree field refused | Admin > Object permissions > add: object type `dcim > device`, actions `view`, constraints `{"tenant__in_tree": "<tenant pk>"}`. Save. | Validation error "The 'in_tree' lookup applies only to tree models; 'tenant' does not reference one." |
| 13.4 | Unknown node | ObjectPermission with `{"location__in_tree": "<random UUID>"}`. | Saves; the restricted queryset is empty (matches nothing), no server error. |
| 13.5 | Provisional markers | Read the docs pages for object permissions and permission policies. | Both carry a "Provisional" warning stating `in_tree` may change or be withdrawn; the changelog line says "provisional". |

## 14. Regressions in shared core code

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 14.1 | Jinja2 `hyperlinked_object` filter | Create a computed field on Device with template `{{ obj.location \| hyperlinked_object }}`. Open a device. | Renders a link to the location. (This filter's registration was lost and restored during development.) |
| 14.2 | `hyperlinked_object_list` tag | On an assignment Preview, a row with more than ten matches. | Ten comma-separated links then "… and N more devices" linking to the filtered list; a row with fewer shows all links and no tail. |
| 14.3 | Excluded columns not configurable | Policy detail > Assignments panel > cog. | The drawer does not offer "Policy" (excluded because the panel is on the policy). Checking anything else and saving works and survives reload. |
| 14.4 | Existing table configuration unaffected | Devices list > cog: add and remove a column, save, reset. | Behavior unchanged from `next`. |
| 14.5 | Object permission admin form validation | Admin > Object permissions > add. Name `qa-badconstraint`, object type `dcim > device` (the admin labels content types as `app > model`), actions `view`, constraints `{"nonexistent": 1}`. Save. | Form error "Invalid filter for dcim.Device: ..." (shared validator). The object types dropdown offers `users > permission policy`, `users > policy parameter`, `users > policy rule` and `users > policy assignment`. |
| 14.6 | Clone hook is opt-in | Clone a Location. | Clone URL contains only the model's clone fields; no `clone_from` parameter. |
| 14.7 | Extras features stay clear of the new models | Custom Fields > Add > Object types; Relationships > Add source/destination types; Dynamic Groups > Add > Content type. | Permission policy, parameter, rule and assignment are not offered anywhere. |
| 14.8 | Change logging | Create, edit and delete a policy and an assignment. | Change log entries exist for `PermissionPolicy`, `PolicyParameter`, `PolicyRule` and `PolicyAssignment`; nested children changed through the policy form or API are logged individually. |
| 14.9 | No notes or data compliance tabs | Policy and assignment detail pages. | Tabs are: object, Advanced, Preview, Change Log. No Notes tab, and `/users/permission-policies/<pk>/notes/` returns 404. |
