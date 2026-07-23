# Design Note — General Many-to-Many Support in Import / Export

Status: **proposal, for review** — no code changes are made pending approval of this approach.
Companion to `trd-csv-import-export.md` and `qa-test-plan-import-export.md`.

## 1. Problem

Two gaps surfaced while exporting VLANs (a VLAN with 2 `locations` produced a file with **no `locations` column**):

1. **The field picker is symmetric, but export and import needs are not.** A single helper
   (`get_csv_form_fields_from_serializer_class`) feeds *both* the export field-selection tree and the
   import field-reference table. It skips `read_only` fields and (until reverted) only surfaced the
   default M2M subset (`tags`/`content_types`/`object_types`). So a read-only M2M like `locations` is
   never offered as an export column — you can only get it via "leave everything unchecked = all
   fields," never as a curated selection.

2. **Read-only M2M don't round-trip.** Even when an export *does* include such a field, its serializer
   is `read_only`, so a re-import silently drops it. Making import write these fields is not a flag —
   they are managed through **association / through models**, each with its own semantics.

The goal of this note is a coherent, general model for M2M in import/export, rather than per-field
patches.

## 2. Taxonomy of M2M fields

Every M2M relation falls into one of the classes below. The classification signal is **not** Django's
`through._meta.auto_created` — Nautobot mixes `associated_object_metadata` and
`associated_data_compliance` (GenericRelations) plus `created`/`last_updated` into most through models,
so nearly all report `auto_created=False`. The real question is: **does the through row carry
user-meaningful fields beyond the two foreign keys?** (ignoring `id`, `created`, `last_updated`,
`associated_object_metadata`, `associated_data_compliance`).

| Class | Example | Serializer | Through carries data? | Export today | Import today |
|-------|---------|-----------|----------------------|--------------|--------------|
| **A. Scalar-keyed, writable** | `tags` | writable (taggit) | n/a (special) | ✅ comma list | ✅ |
| **B. Composite-keyed, writable** | `software_image_files` | writable, auto-through | no | ✅ JSON cell | ✅ |
| **C. ContentType** | `content_types`, `object_types` | writable, auto-through | no | ✅ `app.model` | ✅ |
| **D. Read-only, join-only through** | `VLAN.locations` (`VLANLocationAssignment`) | `read_only` | **no** (only the 2 FKs + auto metadata) | ⚠️ only via "all fields" | ❌ dropped |
| **E. Read-only, data-carrying through** | `SecretsGroup.secrets` (`access_type`,`secret_type`), `DynamicGroup.children` (`operator`,`weight`), `InterfaceRedundancyGroup.interfaces` (`priority`) | `read_only` | **yes** | ⚠️ only via "all fields", and member NK alone loses the through data | ❌ dropped |
| **F. Reverse FK / one-to-many** | `Cable.terminations` | (nested only) | n/a | ❌ excluded (can't flatten) | ❌ |

Classes **A/B/C already work** both directions. The work is in **D**, **E**, and the picker.

## 3. Classification signal (proposed helper)

Add a single source of truth for "how importable/round-trippable is this M2M":

```python
IGNORED_THROUGH_FIELDS = {"id", "created", "last_updated",
                          "associated_object_metadata", "associated_data_compliance"}

def m2m_through_profile(model, field_name):
    """Return one of: 'auto' (no through / auto-through), 'join' (custom through, FKs only),
    'data' (custom through with user fields), or 'reverse' (not a forward M2M)."""
    f = model._meta.get_field(field_name)
    if not f.many_to_many:
        return "reverse"
    through = f.remote_field.through
    if through._meta.auto_created:
        return "auto"
    fk_names = {x.name for x in through._meta.get_fields() if x.many_to_one}
    extra = [x for x in through._meta.get_fields()
             if x.concrete and x.name not in fk_names and x.name not in IGNORED_THROUGH_FIELDS]
    return "data" if extra else "join"
```

- `auto` / `join` → **round-trippable by member natural key** (import can set the relation).
- `data` → **not** round-trippable by member NK alone (the through row carries `access_type`,
  `priority`, etc.).

## 4. Proposed design

### 4a. Decouple the export and import field lists

Split the shared helper by intent:

- **Export tree** — offer every *readable* field, including `read_only` ones and all M2M
  (classes A–E). This matches what an "all fields" export already produces, so a curated selection can
  include `locations`.
- **Import reference** — offer every *writable* field (classes A–C today), **plus** the read-only M2M
  we choose to make importable in 4c (class D, and optionally E).

Mechanically: add `include_read_only` (and keep `exclude_m2m=False`) to
`get_csv_form_fields_from_serializer_class`, or split into `exportable_fields()` /
`importable_fields()`. The export path passes `include_read_only=True`; the import path does not.
Also guard the `child_relation.queryset.model` lookup, which is `None` for read-only M2M.

### 4b. Export (read side) — all classes

No serializer changes needed; the export job already sets `exclude_m2m=False` and can read everything.
Once the picker offers the fields (4a), classes A–E all export:

- D/E scalar members → comma list; composite members → JSON cell (existing machinery).
- For **class E**, a member-NK-only cell **loses the through data**. Two options:
  - **E-lossy**: export members by NK only, and emit a one-time warning that the field is export-only
    and its association attributes (e.g. `priority`) are not represented.
  - **E-rich** (later): export each member as a JSON object that *includes* the through fields
    (`{"member": <nk>, "priority": 10}`), enabling a future rich re-import.

Recommendation: **E-lossy now**, E-rich as a follow-up if needed.

### 4c. Import (write side)

The `ImportObjects` job resolves each row through the serializer, then — for M2M the serializer won't
accept — applies them **after** `save()` via the ORM, keyed on the `m2m_through_profile`:

- **auto / join (class B, C, D)** → resolve each member by natural key (reusing the existing
  related-object resolution + error messaging), then `getattr(obj, field).set(members)`. This makes
  `VLAN.locations` round-trip.
- **data (class E)** → **not** written from a member-NK cell. Log a clear WARNING naming the field and
  why ("managed via an association that carries additional attributes; not importable from this
  column"), and skip it — never silently drop. (A future E-rich path could recreate the through rows
  from the JSON form in 4b.)
- Permissions: setting a read-only-but-join M2M still requires the appropriate permission on the
  relation / through model; the job must enforce it, consistent with §15 of the QA plan.

### 4d. Round-trip semantics matrix

| Class | Export | Import | Round-trips? |
|-------|--------|--------|--------------|
| A tags | ✅ | ✅ | ✅ |
| B composite (auto-through) | ✅ | ✅ | ✅ |
| C content_types | ✅ | ✅ | ✅ |
| D join-only read-only (`locations`) | ✅ (after 4a) | ✅ (via post-save `.set()`, 4c) | ✅ (new) |
| E data-carrying read-only | ✅ export-only + warning | ⚠️ warned & skipped (E-lossy) | ❌ by design (until E-rich) |
| F reverse/one-to-many | ❌ | ❌ | n/a |

## 5. Phasing

1. **Phase 1 — Export parity + picker decouple (4a, 4b E-lossy).** Low risk, no serializer changes.
   Delivers the user's immediate need (`locations` selectable and exported). Classes D/E export.
2. **Phase 2 — Import round-trip for join-only M2M (4c auto/join).** Medium. Adds post-save M2M
   application in `ImportObjects` + the `m2m_through_profile` helper + permission checks. Makes class D
   round-trip.
3. **Phase 3 (optional) — E-rich.** Export/import the through attributes for class E. Larger; only if
   there's demand.

## 6. Risks & edge cases

- **`associated_*` GenericRelations** must be excluded from the through-field scan, or every through
  looks like class E. (Signal in §3 handles this.)
- **`tags`** is taggit-special (through `TaggedItem` with a GFK); keep the existing special-casing
  rather than routing it through the generic path.
- **Ordering / uniqueness**: `.set()` replaces the full membership; confirm that's the desired import
  semantic (declarative — the file is the source of truth) vs additive.
- **Reverse accessors** (class F) remain excluded — they multiply rows and can't be flattened.
- **Performance**: post-save `.set()` adds queries per row; batch where possible.

## 7. Open questions for review

1. Phase 1 only for now, or Phase 1+2 together (so `locations` fully round-trips)?
2. For class E, is **export-only + warning** acceptable, or is E-rich (through attributes in a JSON
   cell) required?
3. Import M2M semantics: **declarative `.set()`** (file replaces membership) — agreed?
4. Should read-only *non-M2M* fields (e.g. `created`, computed counts) also be offered in the export
   tree, or only read-only **M2M**? (Offering all readable fields is simplest and matches "all
   fields", but adds `url`/`display`/`object_type` noise.)
