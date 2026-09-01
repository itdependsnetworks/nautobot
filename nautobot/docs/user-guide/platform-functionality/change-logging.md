# Change Logging

Nautobot utilizes two fundamental types of change categories to log change events: Administrative and Object-level.

## Administrative Changes

Administrative changes are those made under the "Admin" section of the user interface. This is the primary view for Users, Groups, Object Permissions, and other objects core to the administration of Nautobot. Any changes made to objects using this interface will be displayed as "Log entries" under the "Administration" section of the Admin list view. This is a read-only view that disallows manual creation, updating, or deletion of these objects.

These records are commonly referred to as "admin logs" for short and are provided by default by the Django web framework.  

You may access these records if logged in either as a superuser, or a staff user with `view_logentry` permission, by navigating to `/admin/` or by clicking your username in the navigation bar, then "Admin".

## Object Changes

Every time an object in Nautobot is created, deleted, or updated in a way that changes one of its values, a serialized copy of that object is saved to the database, along with meta data including the current time and the user associated with the change. These records form a persistent record of changes both for each individual object as well as Nautobot as a whole. The global change log can be viewed by navigating to Extensibility > Logging > Change Log.

A serialized representation of the instance being modified is included in JSON format. This is similar to how objects are conveyed within the REST API.

Each record has carried two such representations since Nautobot 1.3: `object_data_v2`, which is the REST API representation, and `object_data`, the older format it superseded. Everything in Nautobot reads `object_data_v2` and falls back to `object_data` only for records written before 1.3.

+++ 3.3.0
    Storing the older representation is now optional. Set [`CHANGELOG_LEGACY_OBJECT_DATA`](../administration/configuration/settings.md) to `False` and new records store only `object_data_v2`, halving what each one writes. It defaults to `True`, so upgrading changes nothing.

    Records written while it is off leave `object_data` empty. That is visible to a REST API client reading `object_data` directly; such a client should read `object_data_v2` instead. Records written before the switch are unaffected and keep rendering as they always did.

### Saves that change nothing

+++ 3.3.0

A save that leaves every value as it was records nothing. Submitting an edit form without editing anything, or a `PATCH` carrying the values an object already holds, produces no change record — and therefore fires no [webhook](webhook.md), [job hook](jobs/jobhook.md), or [event](events.md). Before 3.3 each of these wrote a record whose difference display read "No changes".

Some details worth knowing:

- The comparison is against the object's stored values at the moment of the save, not the values it was loaded with. A save that writes an old value back over someone else's concurrent change *is* a change, and is recorded.
- `last_updated` is not a value a reader sees, and moves on every save, so it alone is never a change. An object's `last_updated` can therefore be newer than its most recent change record.
- Association changes still record on both sides, even though the associated objects' own values did not change. See [Many-to-Many Association Changes](#many-to-many-association-changes).
- Changes made outside a change-logging context — `queryset.update()`, `bulk_update()`, migrations — are not recorded when they happen and are not "caught up" by a later save that changes nothing.
- A change to a *related* object no longer surfaces as a change record on this one. Renaming a Location previously produced a change record on every Device saved afterwards, attributing the Location's change to that Device and that user.
- An App whose model builds its change record from something other than its own fields can opt out with the class attribute `changelog_skip_unchanged_saves = False`, in the same way as `is_m2m_change_logged`.

When a request is made, a UUID is generated and attached to any change records resulting from that request. For example, editing three objects in bulk will create a separate change record for each  (three in total), and each of those objects will be associated with the same UUID. This makes it easy to identify all the change records resulting from a particular request.

Change records are exposed in the API via the read-only endpoint `/api/extras/object-changes/`. They may also be exported via the web UI in CSV format.

Change records can also be accessed via the read-only GraphQL endpoint `/api/graphql/`. An example query to fetch change logs by action:

```graphql
{ 
  query: object_changes(action: "created") {
    action
    user_name
    object_repr
  }
}
```

## Many-to-Many Association Changes

+++ 3.2.2

Some many-to-many relationships in Nautobot are implemented with an explicit "through" model that is exposed through its own REST API endpoint, for example `IPAddressToInterface` (`/api/ipam/ip-address-to-interface/`, associating IP addresses with interfaces) or `VRFPrefixAssignment` (`/api/ipam/vrf-prefix-assignments/`, associating VRFs with prefixes).

Creating or deleting such an association record - whether through its REST API endpoint, the UI, or ORM many-to-many operations such as `interface.ip_addresses.add(...)`, `.remove(...)`, `.set(...)`, or `.clear()` - records an "update" change against *both* of the objects it associates. These change records appear in both objects' change logs and drive any [webhooks](webhook.md), [job hooks](jobs/jobhook.md), and [events](events.md) configured for those objects.

!!! note
    As with all change logging, ORM operations are only recorded when performed within a change-logging context: this is automatic for web requests and Jobs, while shell or script usage must be wrapped in `web_request_context`. See [Change Logging and Webhooks](../administration/tools/nautobot-shell.md#change-logging-and-webhooks) for details.

Please note the following behavioral details:

- Deleting an object that *cascades* to its association records (for example, deleting a Device that has VRF assignments) records a "delete" change for the deleted object only; the surviving objects on the other side of its associations (the VRFs) do not receive a change record, and their webhooks and job hooks do not fire. This is a deliberate trade-off: a single delete may cascade to association records for many thousands of surviving objects (consider deleting a Location to which thousands of Prefixes are assigned), and recording a change for each would require serializing every one of those objects and dispatching a webhook, job hook, and event for each within that one request. Note that the deleted object's own "delete" change record includes its final serialized data, so removed associations remain discoverable from that record where the object's REST API representation includes them (for example, a deleted Prefix's record includes its location assignments).
- Updating additional fields on an association record itself (for example, `VRFDeviceAssignment.rd`) does not record a change against the associated objects, as their own data is unaffected.
- Because the serialized data of the associated objects may not include the association itself, the "difference" display of such a change record may be empty even though the change record is meaningful and still drives webhooks, job hooks, and events.
- App-defined models automatically receive the same behavior for any many-to-many relationship declared with an explicit `through` model. An App can opt an association model out of this behavior by setting the class attribute `is_m2m_change_logged = False` on the through model, as Nautobot itself does for user-specific preference data such as `UserSavedViewAssociation`.

## Long-Term Retention

+++ 3.3.0

By default, change and job history accumulates in a single table per record type, and the only way to bound its size is to delete the oldest records. Long-term retention offers a second option: move older records out of the tables that serve everyday reads, and keep them.

Retention is disabled by default. While it is disabled, every read and write behaves exactly as it does without it.

### How records are stored

Recent history stays where it always was, in the `ObjectChange`, `JobResult`, `JobLogEntry`, and `JobConsoleEntry` tables. This is *warm storage*, and it is what every read reaches by default, at the speed it always has.

Older records are moved into a separate table per record type, filed under the calendar period their own timestamp falls in. A record from June 2024 belongs to the 2024 period regardless of when it was moved, which means moving records is repeatable: running the job again files the same records in the same period without duplicating them.

Period granularity is set by [`CHANGELOG_ARCHIVE_PERIOD`](../administration/configuration/settings.md) and defaults to `year`. If yearly periods grow unwieldy, narrowing it to `quarter` or `month` affects periods created from then on; existing periods keep the granularity they were created with.

Each period is registered as an *archive segment*, listed under Extensibility > Logging > Archive Segments, recording the period's bounds, how many records it holds, and how far rotation has gotten into it.

### Reading retained history

Retained history is read **one period at a time**. The change log list view and each object's change log tab offer a period dropdown; choosing a period replaces the recent records with that period's rather than adding to them. There is no combined view spanning warm storage and a retained period, and no view spanning several periods.

This is deliberate. A read scoped to one period sorts and paginates exactly as a warm read does, so reaching older history costs nothing in the common case and behaves predictably in the uncommon one.

Within a selected period, the same filters apply as on a warm read, with a few exceptions. Filters that follow a relationship cannot be used, because a retained record holds its references as plain identifier values rather than as database relationships:

| Record type | Unavailable within a period | Use instead |
|---|---|---|
| Object changes | `user` | `user_name`, or `user_id` |
| Job results | `job_model`, `scheduled_job`, `canceled_by`, `user`, `has_job_console_entries` | the corresponding `_id` filter |
| Job log entries | none | |

Searching within a period works, as do time ranges and `changed_object_type`.

Switching period keeps your filters and sorting: the selector means "show me the same thing, for that
period". Two things do not carry over. The page number resets, since a different period holds a different
number of records. And a filter the target period cannot support is dropped rather than applied, with a
note naming it, because carrying one in would produce an empty table for a reason that has nothing to do
with what you asked for.

Retained history is read-only. While a period is selected, the row actions and bulk-select checkboxes are
not offered, because there is no way to edit or delete a record that has been moved out of warm storage.
Rows do open, though. A retained record keeps the primary key it had in warm storage, so its detail page is
the same URL it always was -- a link saved before rotation still works afterwards. The page is read-only,
and the parts that depend on relationships no longer enforced, such as the diff against the previous
change, are left empty rather than guessed at. Related changes from the same request still work, scoped to
the period.

The Object column links to the object a record describes, on both the list and the detail page, whenever
that object still exists. A retained record stores the object as an identifier rather than as a
relationship, so the link is rebuilt from that identifier when the page is rendered -- one lookup per
object type on the page, not one per row. Where the object has since been deleted, which is common in
older history, the column shows the object's name as it was recorded at the time and does not link
anywhere. There is nothing left to link to, and the recorded name is the whole point of storing it.

Beside the selector, a note says how current the period is. "All 2024 records have been archived" means
the period has ended and everything from it has been moved, so you are seeing all of it. A period still
being archived says so, and gives the timestamp reached so far.

### Permissions

Reading retained history requires the `extras.view_archivesegment` permission, in addition to permission to view the record type itself. One grant covers retained history for every record type.

Without it, the period dropdown is not offered and the REST API parameter is rejected. This permission is deliberately exempt from `EXEMPT_VIEW_PERMISSIONS`, so setting that to `["*"]` does not open retained history.

!!! warning
    Object-level and row-scoped permissions are **not** enforced against retained history in this release. A user who can read retained history can read all of it for the record types they can view. Parity with warm storage is planned as a follow-on.

### REST API

Add `?archive_period=` to the list endpoint you already call:

```no-highlight
GET /api/extras/object-changes/?archive_period=2024
GET /api/extras/object-changes/?archive_period=2024&user_name=alice
GET /api/extras/job-results/?archive_period=2024-Q3
GET /api/extras/job-logs/?archive_period=2024
```

The response schema is identical to a warm response. Valid period values are discoverable from `/api/extras/archive-segments/`. Requesting a period without the permission returns `403`; requesting one that does not exist returns `400`.

`JobConsoleEntry` has no REST endpoint, and gains none here. Retained console output is reached through the job result view's console export.

### Maintaining retention

Four system jobs, all disabled from running on a schedule until you schedule them:

| Job | What it does |
|---|---|
| Changelog Rotation | Moves records older than [`CHANGELOG_WARM_WINDOW_DAYS`](../administration/configuration/settings.md) into their calendar period |
| Changelog Truncation | Deletes warm records selected by retention rules (below) |
| Changelog Archive Integrity Check | Reports retained records whose referent no longer exists |
| Changelog Archive Reconciliation | Verifies each period's record count, that no record falls outside the period holding it, and that nothing exists in both places |

Rotation and truncation are independent. Truncation works whether or not rotation is configured, and rotation does not depend on any retention rule.

Both default to a dry run. Both work in bounded increments rather than one large statement.

The two increment sizes are set separately, because they cost different things. `CHANGELOG_ROTATION_BATCH_SIZE` (default 1000) is how many records rotation holds in memory at once to copy them, each one twice over -- the warm record and the retained copy built from it -- so it is the setting to lower if rotation runs out of memory on records carrying large data. `CHANGELOG_TRUNCATION_BATCH_SIZE` (default 10000) is how many rows one delete statement covers, which needs only their keys.

Either job can be interrupted safely. Rotation copies a record before deleting the warm one, so a run killed part-way leaves records in both places rather than losing them, and re-running files the same records in the same period without duplicating them. Truncation commits each increment, so a killed run has simply deleted less than it would have. Run `Changelog Archive Reconciliation` afterwards to confirm each period's recorded row count still matches what it holds.

#### Job output files

Job results with output files attached are **not** rotated by default. Those files are not archived, and are deleted along with the warm record, so rotation holds such results back rather than removing files silently. Set `include_job_files` to accept that trade.

#### Order of operations

Rotation and truncation are safe to run in either order. When retention is enabled, truncation withholds any record old enough to rotate whose period is not yet complete, on the grounds that rotation has not moved it yet, and says so in its log. Running rotation first avoids the delay.

### Retention rules

A retention rule tells the truncation job what to delete. Each rule names a record type, a filter, and optionally a maximum age, and is either an *include* rule (select these for deletion) or an *exclude* rule (protect these). Exclude wins: a record matched by both is kept.

A rule's filter is built the same way a custom field's scope filter is, with the Basic and Advanced tabs of the filter form for whichever record type the rule names. That means a rule selects exactly what the same filter selects in the change log, so you can check what a rule will delete by running its filter there first.

A rule with neither a filter nor an age bound is skipped rather than applied, since it would select every record. A rule whose filter does not validate is refused, both when you save it and when truncation runs -- never widened to match more than you asked for.

Every enabled rule applies. The truncation job has no per-run rule picker: a rule's *Enabled* checkbox is the switch for whether it runs, so there is one place to look to know what a run will do. It also means a protection cannot be left out of a run by accident, which is what a per-run selection allowed. If every enabled rule is an exclude rule, the run deletes nothing and says so rather than reporting a bare zero.

Manage rules under Extensibility > Logging > Retention Rules. The REST API accepts the filter directly as `scope_filter`, for creating rules from a script.

### Trying it out

Retention only acts on records past the warm window, so a fresh install has nothing to rotate and every
part of the feature comes up empty. `nautobot-server create_changelog_retention_demo_data` fabricates
backdated history to fill it in, rotates it, and creates two users differing only in whether they hold the
cold-storage permission:

```no-highlight
nautobot-server create_changelog_retention_demo_data
```

| Option | Effect |
| --- | --- |
| `--no-rotate` | Create the warm history but leave it unrotated, to run the rotation job yourself |
| `--flush` | Remove what a previous run created, then generate again |
| `--teardown` | Remove what a previous run created, turn retention off, and generate nothing |
| `--status` | Report what exists and change nothing |
| `--seed` | Change the random seed for a differently shaped history |
| `--period` | Configure a different period granularity |

Everything it creates is marked, so `--flush` and `--teardown` never touch a record it did not create.
It is for development and demonstration instances: the two users it creates share a published password.

### Where the retained tables live

Retained history lives in the same database as everything else, reached through a separate connection named `changelog_archive`. Nothing needs provisioning to enable retention.

To put retained history on its own database server, point that connection elsewhere with `NAUTOBOT_CHANGELOG_ARCHIVE_DB_HOST` and the other `NAUTOBOT_CHANGELOG_ARCHIVE_DB_*` variables, then run `nautobot-server migrate --database changelog_archive`.

### Operational notes

!!! warning "Integrations reading the database directly"
    Once truncation is enabled, anything querying the covered tables directly rather than through the REST API will see fewer rows, with no error. Records moved into retention are in different tables entirely.

!!! important "After upgrading"
    Run `nautobot-server check_changelog_archive_schema` after every upgrade. The retained tables mirror the warm models, and nothing in the migration tooling detects when a field is added to one and not the other; records rotated while a field is missing will not carry it. Nautobot also reports this at startup as check `nautobot.core.W011`.

Relationships between records are not enforced once a record is moved into retention. A retained job log entry can outlive its job result, for example. The integrity and reconciliation jobs above are how you find that, rather than the database preventing it.
