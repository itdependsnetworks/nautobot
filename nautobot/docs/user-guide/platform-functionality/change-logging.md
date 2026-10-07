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

The **Changelog Rotation** job moves older records into a separate table per record type, reached through a separate database connection: `extras_archivedobjectchange`, `extras_archivedjobresult`, `extras_archivedjoblogentry`, and `extras_archivedjobconsoleentry`. All four are created by migration, like any other table.

Moving records is repeatable. A second run writes the same records to the same table without duplicating them, because each record keeps the primary key it had in warm storage.

A retained record stores each of its references as a plain identifier value instead of a database relationship, so no constraint has to cross the two connections. That is where the filter and field differences described below come from: there is no relation to follow.

### Reading retained history

Retained history has its own pages, under Extensibility > Logging:

| Page | What it lists |
|---|---|
| **Archived Change Log** | Retained change records |
| **Archived Job Results** | Retained job results, with their log entries and console output |

Each row opens a detail page laid out like the warm one, with the same panels over the same fields.

A link saved before rotation still works. Opening `/extras/object-changes/<id>/` or `/extras/job-results/<id>/` for a record that has since been rotated redirects to that record's retained page, so an old link reaches the record instead of a 404.

A few warm filters have no counterpart on the archived lists, because a retained record holds its references as plain identifier values:

| Record type | Available on the warm list, not on the archived one | Use instead |
|---|---|---|
| Object changes | `user`, `user_id` | `user_name` |
| Job results | `job_model`, `job_model_id`, `scheduled_job`, `canceled_by`, `user`, `has_job_console_entries` | `name` for the job, `user_name` for the user |

Every other filter is available on both, including search, time ranges, `changed_object_type`, and the advanced filter with its lookup expressions.

#### Fields a retained record cannot show

For the same reason, a few fields on the detail page are always empty on a retained record. The page shows the row, so what is missing is visible rather than silently dropped:

| Field | Why it is empty |
|---|---|
| A job result's **Job description** | The description belongs to the `Job`, which is not archived, and the job reference is stored as an identifier. The job's **name** is copied onto the record at rotation, so the job is still identified. |
| A job result's **Files** | Job output files are deleted with the warm record rather than archived. Rotation excludes results that have files unless `include_job_files` is set. |

A job's description can change after a result is produced, so a description shown beside an old result would be the description the job has now, not the one it had at the time. Copying it at rotation, the way the name and username are copied, would be the way to fill this in, and is not done today.

Retained history is read-only. There are no row actions and no bulk-select checkboxes, because a record moved out of warm storage cannot be edited or deleted through the UI.

The Object column links to the object a record describes, whenever that object still exists. A retained record stores the object as an identifier instead of a relationship, so Nautobot rebuilds the link from that identifier when the page renders, with one lookup per object type on the page, not one per row. Where the object has since been deleted, which is common in older history, the column shows the name recorded at the time and links nowhere. There is nothing left to link to, and the recorded name is the whole point of storing it.

### Permissions

Each retained record type has its own ordinary `view` permission, granted the same way as any other:

- `extras.view_archivedobjectchange`
- `extras.view_archivedjobresult`
- `extras.view_archivedjoblogentry`
- `extras.view_archivedjobconsoleentry`

Holding the warm permission does not grant the retained one. A user who may read the change log can be given retained change records or not, as a separate decision.

There is no `add`, `change` or `delete` permission for any of them. Rotation writes these records and nothing else does, so those actions do not exist to grant.

#### Object-level constraints

An object permission's constraints are applied to retained records, but only constraints that name a column the retained record stores for itself. A constraint on `user_name`, `action`, `time` or `object_repr` filters retained change records exactly as it filters warm ones.

A constraint that traverses a relation cannot be applied. A retained record stores each reference as a plain identifier value, so there is no relation to follow and nothing to join to:

| Constraint | Against warm records | Against retained records |
|---|---|---|
| `{"user_name": "alice"}` | Works | Works |
| `{"user__username": "alice"}` | Works | Cannot be resolved |
| `{"changed_object_type__app_label": "dcim"}` | Works | Cannot be resolved |

!!! warning
    A constraint that traverses a relation raises an error while the archived list builds its query, rather than being ignored. It does not quietly widen access, but it does break the page for anyone the permission applies to. Write constraints for retained record types against the stored columns, and grant the retained permission through an object permission of its own rather than reusing one written for the warm model.

Constraining by object type is the case worth planning for. Use `changed_object_type_id` with the numeric id of the content type, which the retained record does store, in place of `changed_object_type__app_label`.

### REST API

Three read-only endpoints, one per record type that has a warm endpoint:

```no-highlight
GET /api/extras/archived-object-changes/
GET /api/extras/archived-job-results/
GET /api/extras/archived-job-logs/
```

Each response carries the same field names as its warm counterpart, with the demoted references rendered as the nested object a warm response carries, so a client that reads change or job history needs no second code path for the retained version. A retained job result adds one field, `user_name`, the username denormalized at rotation because the user reference is stored as an identifier.

They accept the same filters as the archived lists, and the same `format=csv` export. Each requires its record type's view permission and returns `403` without it. None of them accepts a write.

`JobConsoleEntry` has no REST endpoint, so neither does its mirror. Retained console output is exported from the Console Log tab of a retained job result.

### Turning retention on

`CHANGELOG_ARCHIVE_ENABLED` is a deployment setting, not a runtime toggle. Set it in `nautobot_config.py` (or as `NAUTOBOT_CHANGELOG_ARCHIVE_ENABLED`) and restart:

```python
# nautobot_config.py
CHANGELOG_ARCHIVE_ENABLED = True
```

It is deliberately not configurable from Admin > Configuration. Turning it on commits the installation to a second database connection, four retained tables, and scheduled jobs that move history, so it is an administrator's decision made once with the rest of the deployment, not something switched on from a web form.

The remaining settings are runtime tuning and can be changed from Admin > Configuration at any time: the warm window and the rotation batch size.

### Maintaining retention

Two system jobs, neither scheduled until you schedule it:

| Job | What it does |
|---|---|
| Changelog Rotation | Moves records older than [`CHANGELOG_WARM_WINDOW_DAYS`](../administration/configuration/settings.md) into retained storage |
| Changelog Archive Integrity Check | Reports retained records whose referent no longer exists, and records left in both places |

Rotation defaults to a dry run, and works in bounded increments rather than one large statement. `CHANGELOG_ROTATION_BATCH_SIZE` (default 1000) is how many records it loads into memory at once to copy them, each one twice over, the warm record and the retained copy built from it, so it is the setting to lower if rotation runs out of memory on records with large data.

Rotation can be interrupted safely. It copies a record before deleting the warm one, so a run killed part-way leaves records in both places instead of losing them, and a second run writes the same records again without duplicating them. Run `Changelog Archive Integrity Check` afterwards: it reports any record left in both places.

#### Job output files

Job results with output files attached are **not** rotated by default. Those files are not archived, and are deleted along with the warm record, so rotation excludes such results instead of removing files silently. Set `include_job_files` to accept that trade.

### Trying it out

Retention only acts on records past the warm window, so a fresh install has nothing to rotate and every part of the feature comes up empty. `nautobot-server create_changelog_retention_demo_data` fabricates backdated history to fill it in, rotates it, and creates two users differing only in whether they hold the retained-history permissions:

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

Everything it creates is marked, so `--flush` and `--teardown` never touch a record it did not create. It is for development and demonstration instances: the two users it creates share a published password.

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

- **Dropping a retained table is how you reclaim disk.** Each record type has its own, so removing one is a `DROP TABLE`. Space comes back at once, nothing else is locked, and the indexes go with it. There is one table per record type, so dropping one discards that record type's whole retained history.
- **Rotation bounds the warm tables' row count, not their disk.** Rotation deletes the warm row once it has been copied. The warm tables stop growing and stay at whatever size they reached. That is usually what you want, because the space is reused by new records instead of being returned and re-allocated.
- **Schedule rotation from the start.** A warm table kept at a steady size never needs shrinking. A table allowed to grow for two years and then rotated will be mostly empty space until someone rebuilds it.
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
    Once rotation is scheduled, anything querying the covered tables directly instead of through the REST API will see fewer rows, with no error. Records moved into retention are in different tables entirely, and are read through the archived endpoints.

!!! important "After upgrading"
    Run `nautobot-server check_changelog_archive_schema` after every upgrade. The retained tables mirror the warm models, and nothing in the migration tooling detects when a field is added to one and not the other; records rotated while a field is missing will not carry it. Nautobot also reports this at startup as check `nautobot.core.W011`.

Relationships between records are not enforced once a record is moved into retention. A retained job log entry can outlive its job result, for example. The integrity and reconciliation jobs above are how you find that, rather than the database preventing it.
