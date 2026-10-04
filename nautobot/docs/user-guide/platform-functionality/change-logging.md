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

    Records written while it is off leave `object_data` empty. That is visible to a REST API client reading `object_data` directly; such a client should read `object_data_v2` instead. Records written before the switch are unaffected and still render as they always did.

### Saves that change nothing

+++ 3.3.0

A save that leaves every value as it was records nothing. Submitting an edit form without editing anything, or a `PATCH` whose values match the object's current values, produces no change record, and therefore fires no [webhook](webhook.md), [job hook](jobs/jobhook.md), or [event](events.md). Before 3.3 each of these wrote a record whose difference display read "No changes".

Some details worth knowing:

- The comparison is against the object's stored values at the moment of the save, not the values it was loaded with. A save that writes an old value back over someone else's concurrent change *is* a change, and is recorded.
- `last_updated` is not a value a reader sees, and moves on every save, so it alone is never a change. An object's `last_updated` can therefore be newer than its most recent change record.
- Association changes still record on both sides, even though the associated objects' own values did not change. See [Many-to-Many Association Changes](#many-to-many-association-changes).
- Changes made outside a change-logging context (`queryset.update()`, `bulk_update()`, migrations) are not recorded when they happen and are not "caught up" by a later save that changes nothing.
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

## What Is Recorded

### Saves That Change Nothing

+/- 3.3.0

When you save an object without changing any of its fields, for example by clicking **Save** on an edit form you did not touch, or by sending an empty `PATCH` request, no change record is created. No [webhooks](webhook.md), [job hooks](jobs/jobhook.md), or [events](events.md) are triggered either. The object's `last_updated` timestamp still moves, because the row is still written to the database.

Nautobot decides whether anything changed by comparing the values being saved with the values currently stored in the database. It does not compare them with the values the object had when it was loaded. This means that if someone else changed the object in the meantime and your save puts the old values back, that save is recorded as a change.

Only the object's own fields take part in this comparison. Adding or removing related objects through a many-to-many relationship is always recorded, even when the end result is the same set of related objects. See [Many-to-Many Association Changes](#many-to-many-association-changes) below.

If your deployment relies on the previous behavior, set [`CHANGELOG_SKIP_UNCHANGED_SAVES`](../administration/configuration/settings.md#changelog_skip_unchanged_saves) to `False` to record these saves again. This setting is provided to ease the transition and is expected to be removed in a future major release.

### The `prechange` in Webhook and Event Payloads

+/- 3.3.0

When an object is updated, the `prechange` snapshot in [webhook](webhook.md) and [event](events.md) payloads shows the object exactly as it was stored right before the change was written. This includes any modifications made outside of change logging, such as data migrations or bulk `update()` calls. In earlier versions the snapshot was rebuilt from the object's previous change record, which could be very old or absent entirely.

This snapshot is only captured when a webhook, job hook, or event broker is configured for the object type, because nothing else uses it.

Two places still rebuild `prechange` from the previous change record: the change log view in the UI, and `ObjectChange.get_snapshots()` when called from a [job hook](jobs/jobhook.md). After a change made outside of change logging, these may show a different `prechange` than the webhook payload did. This is a known inconsistency. The behavior may change in a future release.

Changes to many-to-many associations are not made by saving a field, so their `prechange` is always rebuilt from the previous change record.

## Many-to-Many Association Changes

+++ 3.2.2

Some many-to-many relationships in Nautobot are implemented with an explicit "through" model that is exposed through its own REST API endpoint, for example `IPAddressToInterface` (`/api/ipam/ip-address-to-interface/`, associating IP addresses with interfaces) or `VRFPrefixAssignment` (`/api/ipam/vrf-prefix-assignments/`, associating VRFs with prefixes).

Creating or deleting such an association record - whether through its REST API endpoint, the UI, or ORM many-to-many operations such as `interface.ip_addresses.add(...)`, `.remove(...)`, `.set(...)`, or `.clear()` - records an "update" change against _both_ of the objects it associates. These change records appear in both objects' change logs and drive any [webhooks](webhook.md), [job hooks](jobs/jobhook.md), and [events](events.md) configured for those objects.

!!! note
    As with all change logging, ORM operations are only recorded when performed within a change-logging context: this is automatic for web requests and Jobs, while shell or script usage must be wrapped in `web_request_context`. See [Change Logging and Webhooks](../administration/tools/nautobot-shell.md#change-logging-and-webhooks) for details.

Please note the following behavioral details:

- Deleting an object that _cascades_ to its association records (for example, deleting a Device that has VRF assignments) records a "delete" change for the deleted object only; the surviving objects on the other side of its associations (the VRFs) do not receive a change record, and their webhooks and job hooks do not fire. This is a deliberate trade-off: a single delete may cascade to association records for many thousands of surviving objects (consider deleting a Location to which thousands of Prefixes are assigned), and recording a change for each would require serializing every one of those objects and dispatching a webhook, job hook, and event for each within that one request. Note that the deleted object's own "delete" change record includes its final serialized data, so removed associations remain discoverable from that record where the object's REST API representation includes them (for example, a deleted Prefix's record includes its location assignments).
- Updating additional fields on an association record itself (for example, `VRFDeviceAssignment.rd`) does not record a change against the associated objects, as their own data is unaffected.
- Because the serialized data of the associated objects may not include the association itself, the "difference" display of such a change record may be empty even though the change record is meaningful and still drives webhooks, job hooks, and events.
- App-defined models automatically receive the same behavior for any many-to-many relationship declared with an explicit `through` model. An App can opt an association model out of this behavior by setting the class attribute `is_m2m_change_logged = False` on the through model, as Nautobot itself does for user-specific preference data such as `UserSavedViewAssociation`.

## Long-Term Retention

+++ 3.3.0

By default, change and job history accumulates in a single table per record type, and the only way to bound its size is to delete the oldest records. Long-term retention offers a second option: move older records out of the tables that serve everyday reads, and keep them.

Retention is disabled by default. While it is disabled, every read and write behaves exactly as it does without it.

### How records are stored

Recent history stays where it always was, in the `ObjectChange`, `JobResult`, `JobLogEntry`, and `JobConsoleEntry` tables. This is *warm storage*, and it is what every read reaches by default, at the speed it always has.

The **Changelog Rotation** job moves older records into a separate table per record type, reached through a separate database connection. Moving records is repeatable: a second run writes the same records to the same table without duplicating them, because each record has the same primary key it had in warm storage.

Retained history is divided into *periods*, one table per period per record type, and a record's own timestamp decides which period it is written to. `CHANGELOG_ARCHIVE_PERIOD` sets how long a period is: `year`, `quarter`, `month`, or `unbounded`. It defaults to `year`. `unbounded` is one period holding everything, which is the setting under which the archive only ever grows.

Every installation has the unbounded period, whatever that setting says. Its four tables are created by a migration like any other: `extras_archivedobjectchange_unbounded`, `extras_archivedjobresult_unbounded`, `extras_archivedjoblogentry_unbounded` and `extras_archivedjobconsoleentry_unbounded`. Under a calendar granularity, rotation stops writing to them and creates a table per period beside them, named for the period it holds: `extras_archivedobjectchange_2024`, `extras_archivedobjectchange_2024_q3`, `extras_archivedobjectchange_2024_07`. Each period's table is created the first time rotation writes to that period.

Periods are what make retained history reducible. Deleting rows returns no disk until the table is rewritten, while `DROP TABLE` on a period you have decided not to keep returns all of it at once. That is the reason to choose a calendar granularity. Without one, the archive only ever grows.

### Choosing a period granularity

Choose it from how much history you expect to discard at a time, since a period is the smallest unit you can drop. Yearly periods on an installation keeping seven years give you seven tables and one decision a year. Monthly periods on the same installation give you 84 tables.

Set it before enabling retention, and read the next section before changing it afterwards.

```python
# nautobot_config.py
CHANGELOG_ARCHIVE_PERIOD = "year"
```

#### Changing the period granularity

One granularity applies at a time, and it describes the whole archive, not the period written next. Changing it does not reshape the periods that already exist. An installation switching from `year` to `month` keeps its year-long tables holding a year each, and writes month-long tables from then on.

Nautobot allows that and does nothing about it. Resplitting a period is a manual operation, and the SQL is short because PostgreSQL copies a table's shape:

```sql
-- Split a yearly period into months. Run against the changelog_archive database.
CREATE TABLE extras_archivedobjectchange_2024_01 (LIKE extras_archivedobjectchange_2024 INCLUDING ALL);
INSERT INTO extras_archivedobjectchange_2024_01
    SELECT * FROM extras_archivedobjectchange_2024
    WHERE "time" >= '2024-01-01' AND "time" < '2024-02-01';
UPDATE extras_archivedobjectchange_2024_01 SET period_key = '2024-01';
-- repeat for each month, confirm the counts add up, then
DROP TABLE extras_archivedobjectchange_2024;
```

`INCLUDING ALL` copies the indexes, constraints and defaults, so the new table matches what Nautobot would have created.

Three things to get right, because missing any one of them loses records:

1. **The timestamp column differs per record type.** It is `time` on object changes, `date_created` on job results, `created` on job log entries, and `timestamp` on job console entries. Naming the wrong one selects no rows, and the `INSERT` reports that it inserted none.
2. **All four record types need splitting together.** Stopping after object changes leaves a period that exists for change records and not for job results.
3. **The period registry is a separate edit, on a different connection.** Nautobot records which periods exist in `extras_archivesegment`, which is on the `default` database while the period tables are on `changelog_archive`. Those are two connections and possibly two hosts. Add a row per new period and delete the row for the period you dropped, or Nautobot goes on offering a period whose table is gone.

A management command for this may come later. Today the SQL above is the whole of it.

### Reading retained history

Retained history is read through the change log itself, not through a separate page. The **Archive** button sits with the other buttons at the top right of the Change Log list and of an object's Change Log tab. It lists **Recent**, which is warm storage, then each period newest first, with how many records each holds and whether rotation has finished filling it.

Choosing a period replaces what the list shows. One period per read, never merged with warm storage and never two at once: a record belongs to exactly one period's table, so a list showing two would have its ordering, its paginator and its row count describing something other than a table. **Recent** goes back to warm.

The button appears on any list view whose model has retained history, and on an object's Change Log tab, where it offers periods of change records rather than of the object's own model.

Filters and sorting carry across the switch, and so does the reverse. Choosing a period and then filtering by user gives that user's records in that period, not across all of them.

The period is in the URL as `?archive_period=`, so a filtered view of one period is a link you can keep.

**Extensibility > Logging > Archive Periods** lists which periods exist, what each covers, how many records are in it, and the newest record it holds. It is read-only, and it is the list to read before discarding a period.

A few warm filters have no counterpart in a period, because a retained record holds its references as plain identifier values instead of database relationships, so there is no relation to follow. Those are dropped when you switch, and the page says which:

| Record type | Available on the warm list, not on the archived one | Use instead |
|---|---|---|
| Object changes | `user`, `user_id` | `user_name` |
| Job results | `job_model`, `job_model_id`, `scheduled_job`, `canceled_by`, `user`, `cancel_type`, `has_job_console_entries` | `name` for the job, `user_name` for the user |

Every other filter is available on both, including search, time ranges, `changed_object_type`, and the advanced filter with its lookup expressions.

Retained history is read-only. There are no row actions and no bulk-select checkboxes, because a record moved out of warm storage cannot be edited or deleted through the UI. Rows do open: a retained record has the same primary key it had in warm storage.

The Object column links to the object a record describes, whenever that object still exists. A retained record stores the object as an identifier instead of a relationship, so Nautobot rebuilds the link from that identifier when the page renders, with one lookup per object type on the page, not one per row. Where the object has since been deleted, which is common in older history, the column shows the name recorded at the time and links nowhere. There is nothing left to link to, and the recorded name is the whole point of storing it.

### Permissions

Reading retained history requires the `extras.view_archivesegment` permission. One grant covers retained history for every record type.

Without it the **Archive** button is not rendered, so there is no way into a period, and **Archive Periods** is hidden. This permission is deliberately exempt from `EXEMPT_VIEW_PERMISSIONS`, so setting that to `["*"]` does not open retained history.

There is no per-model permission for retained records. The models behind them are abstract and declare none, which is why one permission gates all of them.

!!! warning
    Object-level and row-scoped permissions are **not** enforced against retained history in this release. A user who can read retained history can read all of it. Parity with warm storage is planned as a follow-on.

### REST API

`archive_period` on the existing endpoints reads one period instead of warm storage, the same parameter the UI puts in its links. There are no separate archived endpoints: the response schema is the warm one, because a retained record carries the same fields.

```no-highlight
GET /api/extras/object-changes/?archive_period=2024
GET /api/extras/object-changes/?archive_period=2024&user_name=alice
GET /api/extras/job-log-entries/?archive_period=2024
```

Without the parameter nothing changes and the endpoint returns warm storage exactly as before. With it, and without the `extras.view_archivesegment` permission, the request is rejected rather than quietly answered from warm storage, so a client cannot mistake one for the other.

The periods available are listed by **Archive Periods** in the UI.

### Turning retention on

`CHANGELOG_ARCHIVE_ENABLED` is a deployment setting, not a runtime toggle. Set it in `nautobot_config.py` (or as `NAUTOBOT_CHANGELOG_ARCHIVE_ENABLED`) and restart:

```python
# nautobot_config.py
CHANGELOG_ARCHIVE_ENABLED = True
```

It is deliberately not configurable from Admin > Configuration. Turning it on commits the installation to a second database connection, a growing set of retention tables, and two scheduled jobs that move and delete history, so it is an administrator's decision made once with the rest of the deployment, not something switched on from a web form.

```python
# nautobot_config.py
CHANGELOG_ARCHIVE_ENABLED = True
```

The remaining settings are runtime tuning and can be changed from Admin > Configuration at any time: the warm window, and the two batch sizes.

### Maintaining retention

Four system jobs, all disabled from running on a schedule until you schedule them:

| Job | What it does |
|---|---|
| Changelog Rotation | Moves records older than [`CHANGELOG_WARM_WINDOW_DAYS`](../administration/configuration/settings.md) into retained storage |
| Changelog Truncation | Deletes warm records selected by retention rules (below) |
| Changelog Archive Integrity Check | Reports retained records whose referent no longer exists |

Rotation and truncation are independent. Truncation works whether or not rotation is configured, and rotation does not depend on any retention rule.

Both default to a dry run. Both work in bounded increments rather than one large statement.

The two increment sizes are set separately, because they cost different things. `CHANGELOG_ROTATION_BATCH_SIZE` (default 1000) is how many records rotation loads into memory at once to copy them, each one twice over -- the warm record and the retained copy built from it -- so it is the setting to lower if rotation runs out of memory on records with large data. `CHANGELOG_TRUNCATION_BATCH_SIZE` (default 10000) is how many rows one delete statement covers, which needs only their keys.

Either job can be interrupted safely. Rotation copies a record before deleting the warm one, so a run killed part-way leaves records in both places instead of losing them, and a second run writes the same records again without duplicating them. Truncation commits each increment, so a killed run has simply deleted less than it would have. Run `Changelog Archive Integrity Check` afterwards: it reports any record left in both places.

#### Job output files

Job results with output files attached are **not** rotated by default. Those files are not archived, and are deleted along with the warm record, so rotation excludes such results instead of removing files silently. Set `include_job_files` to accept that trade.

#### Order of operations

Rotation and truncation are safe to run in either order. When retention is enabled, truncation withholds any record old enough to rotate that rotation has not moved into retained storage yet, and says so in its log. Running rotation first avoids the delay.

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
| `--period` | Rotate under this granularity for this command only, without restarting the instance |

The history it fabricates spans four years, so `--period year` gives four periods and a period selector with something to select:

```no-highlight
nautobot-server create_changelog_retention_demo_data --flush --period year
```

`CHANGELOG_ARCHIVE_PERIOD` needs a restart to change, which is right for a deployment setting and awkward for seeing what the setting does. `--period` applies only to the rotation this command runs; the scheduled job goes on reading the setting.

Everything it creates is marked, so `--flush` and `--teardown` never touch a record it did not create. `--flush` sweeps every period, and removes the registry row for any period it leaves empty, keeping the table.
It is for development and demonstration instances: the two users it creates share a published password.

### Where the retained tables are stored

Retained history is in the same database as everything else, reached through a separate connection named `changelog_archive`. Nothing needs provisioning to enable retention.

To put retained history on its own database server, point that connection elsewhere with `NAUTOBOT_CHANGELOG_ARCHIVE_DB_HOST` and the other `NAUTOBOT_CHANGELOG_ARCHIVE_DB_*` variables. You can also define `DATABASES["changelog_archive"]` yourself in `nautobot_config.py`, in which case Nautobot leaves it exactly as you wrote it.

Either way the four retained tables are created by migration, on whichever connection owns them. A separate archive database is migrated like any other: run `nautobot-server migrate --database changelog_archive` against it.

### Example configurations

Two arrangements. In both, `DATABASE_ROUTERS` already includes `ChangelogArchiveRouter` by default; you only need to name it yourself if you set `DATABASE_ROUTERS` to add routers of your own, and it must stay in the list.

#### 1. One database

The default. No configuration at all.

```python
# nautobot_config.py -- nothing to add
DATABASES = {
    "default": {
        "NAME": "nautobot",
        "USER": os.getenv("NAUTOBOT_DB_USER", ""),
        "PASSWORD": os.getenv("NAUTOBOT_DB_PASSWORD", ""),
        "HOST": os.getenv("NAUTOBOT_DB_HOST", "localhost"),
        "PORT": os.getenv("NAUTOBOT_DB_PORT", ""),
        "ENGINE": "django.db.backends.postgresql",
    },
}
```

Nautobot copies `default` into a second connection named `changelog_archive`, and the migration creates the four retained tables in it:

```no-highlight
extras_archivedobjectchange_unbounded
extras_archivedjobresult_unbounded
extras_archivedjoblogentry_unbounded
extras_archivedjobconsoleentry_unbounded
```

#### 2. A separate archive database

Point the archive connection at another server. Either set the environment variables:

```no-highlight
NAUTOBOT_CHANGELOG_ARCHIVE_DB_HOST=archive.example.com
NAUTOBOT_CHANGELOG_ARCHIVE_DB_NAME=nautobot_archive
NAUTOBOT_CHANGELOG_ARCHIVE_DB_USER=nautobot
NAUTOBOT_CHANGELOG_ARCHIVE_DB_PASSWORD=...
```

or write the connection out yourself, in which case Nautobot leaves it exactly as you wrote it:

```python
# nautobot_config.py
DATABASES = {
    "default": {...},
    "changelog_archive": {
        "NAME": "nautobot_archive",
        "USER": "nautobot",
        "PASSWORD": os.getenv("NAUTOBOT_ARCHIVE_DB_PASSWORD", ""),
        "HOST": "archive.example.com",
        "PORT": "5432",
        "ENGINE": "django.db.backends.postgresql",
        "CONN_MAX_AGE": 300,
    },
}
```

The four retained tables are created by migration, so a separate archive database is migrated like any other: `nautobot-server migrate --database changelog_archive`. Nothing else is built there.

### Reclaiming disk space

Deleting rows does not give disk space back, on either PostgreSQL or MySQL. This surprises people, and it decides how you should operate this feature.

When PostgreSQL deletes a row it marks the row dead and leaves it in place. `VACUUM`, which autovacuum runs for you, then marks that space reusable **by the same table**. The file on disk does not shrink. Delete 100 GB of old change records and you have given that table 100 GB to grow back into, and given the operating system nothing.

To actually shrink a table you need `VACUUM FULL`, which rewrites it. That takes an exclusive lock, so nothing can read or write the table while it runs, and it needs enough free disk space for a second copy. On a table large enough to be worth shrinking, that is exactly when you can least afford either. MySQL behaves the same way: `DELETE` leaves the space inside the InnoDB file and `OPTIMIZE TABLE` is the equivalent rebuild.

What this means in practice:

- **Dropping a retained table is how you reclaim disk.** Each record type has its own, so removing one is a `DROP TABLE`. Space comes back at once, nothing else is locked, and the indexes go with it. This gets more useful once retained history is divided by calendar period and the oldest can be dropped on its own; with one period it discards the whole archive.
- **Truncation bounds row count, not disk.** The truncation job deletes rows from the warm tables. Those tables stop growing and stay at whatever size they reached. That is usually what you want, because the space is reused by new records instead of being returned and re-allocated.
- **Run truncation on a schedule from the start.** A warm table that is kept at a steady size never needs shrinking. A table allowed to grow for two years and then truncated will be mostly empty space until someone rebuilds it.
- **If you do need the space back from a warm table**, schedule it during a maintenance window and expect the table to be unavailable:

```no-highlight
VACUUM FULL extras_objectchange;
```

- **`pg_repack` is the online alternative.** It rebuilds a table without holding an exclusive lock for the duration, at the cost of an extension and roughly double the disk while it runs. Worth having if you cannot take the outage.
- **Check what you would actually recover** before planning any of this. `pg_stat_user_tables.n_dead_tup` reports how many dead rows a table has:

```no-highlight
SELECT relname, n_live_tup, n_dead_tup, last_autovacuum
  FROM pg_stat_user_tables
 WHERE relname LIKE 'extras_objectchange%'
    OR relname LIKE 'extras_job%';
```

If `n_dead_tup` is small, there is nothing to reclaim and a rebuild would only cost you an outage.

### Operational notes

!!! warning "Integrations reading the database directly"
    Once truncation is enabled, anything querying the covered tables directly rather than through the REST API will see fewer rows, with no error. Records moved into retention are in different tables entirely.

!!! important "After upgrading"
    Run `nautobot-server check_changelog_archive_schema` after every upgrade. The retained tables mirror the warm models, and nothing in the migration tooling detects when a field is added to one and not the other; records rotated while a field is missing will not carry it. Nautobot also reports this at startup as check `nautobot.core.W011`.

Relationships between records are not enforced once a record is moved into retention. A retained job log entry can outlive its job result, for example. The integrity and reconciliation jobs above are how you find that, rather than the database preventing it.
