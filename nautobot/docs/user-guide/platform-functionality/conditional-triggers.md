# Conditional Triggers

A Webhook or Job Hook can say *which object types* and *which kinds of change* it watches. On its own it
cannot say which *particular* objects, or which *particular* changes, so receivers get sent everything
and have to do the filtering themselves.

A **scope** and a list of **conditions** answer those two questions. Both are fields on the Webhook or Job
Hook itself, so a trigger is configured in one place, on one page.

| Part | Question it answers | How you express it |
|---|---|---|
| Object Types | "What kind of object?" | The action's own Object Type(s) |
| Event Types | "What kind of change?" | The action's own Type Create / Update / Delete flags |
| Scope Filter | "Which objects?" | Filter parameters for the selected object type(s) |
| Conditions | "Which changes?" | An ordered list, all of which must pass |

Both new fields are empty by default, and **an action with both empty behaves exactly as it did before
they existed**. This is additive: filling them in narrows when an action fires; it never adds a new way to
fire one.

Everything below applies identically to Webhooks and Job Hooks. They share one implementation, so they
cannot drift apart in behaviour.

## Fields

| Field | Required | Description |
|---|---|---|
| Scope Filter | No | Filter parameters limiting which objects the action applies to. Empty means every object of the selected type(s). |
| Conditions | No | An ordered list of conditions, all of which must pass. Empty means every in-scope change passes. |

## Scope

A scope filter narrows an action to particular objects. Selecting one or more object types loads that model's real filter fields, the same ones the model's list view offers, so an action can be scoped to `location=Campus-1` or `status=Active` or anything else you can filter that model by.

Scope is evaluated while the change is happening, not later, because a deleted object cannot be queried after the fact and a delete-subscribed action would otherwise be unable to tell whether the deleted object was in scope.

### Which state scope is matched against

| Event | Scope is matched against |
|---|---|
| Created | the object as it now is |
| Updated | the object **after** the change |
| Deleted | the object **before** the change, which is the only state that still exists |

So moving a device *out* of a scoped location does **not** fire an update-watching action scoped to that location: by the time the scope is checked, the device is somewhere else. Moving one *in* does fire. Deleting a device that was in scope fires, because Nautobot checks the scope just before the object is removed, while it can still be matched.

!!! note
    An action watching more than one object type stores one filter for all of them, so every parameter must be valid for every selected type. Nautobot rejects a filter parameter that one of the selected models does not support, on the form, through the REST API, and when object types are added in bulk, instead of silently leaving that model unscoped.

If a stored filter somehow cannot be applied anyway, because it was written straight to the database or predates that checking, the action **does not fire** for the object type it cannot be applied to, and an error naming the action and the parameter is written to the log. A filter exists to narrow, so the alternative of falling back to "every object" would deliver webhooks and run job hooks against exactly the objects you excluded, and a delivery cannot be recalled. An action that has gone quiet is the recoverable failure; fixing the filter brings it back.

### Several triggers, one endpoint

A chat or ticketing endpoint usually has more than one reason to be called: a device failing, a circuit
being deprovisioned, a prefix disappearing from production. Each reason is its own Webhook, carrying its
own scope and conditions, and they may share a payload URL.

Nautobot normally refuses two webhooks with the same object type, event and URL, because that means the
receiver gets the same thing twice. That check now allows them when their scope filters or conditions
differ. At that point they are deliberately different triggers, not an accidental duplicate.

## Conditions

A condition is one row in the Conditions list. Each row picks either a **preset**, a ready-made check from a short catalog, or **Raw expression**, where you write the check yourself. Both are listed in the same dropdown, and both are evaluated by the same engine, so they behave identically: the same definition of passing, and the same behavior when something goes wrong.

Each row also has a **not** checkbox, which inverts that row's verdict. A row that would have passed fails instead, and vice versa. It works on presets and raw expressions alike, so there is no need for a negated copy of a preset or a `not` written into an expression. A row that could not be evaluated at all, a typo in an expression for instance, stays failed even when **not** is checked, because inverting a broken check into a pass would fire the action on a mistake.

Conditions are AND-ed: **every** condition must pass for the action to fire. There is no OR between rows and no grouping.

| Row 1 | Row 2 | Row 3 | Rule fires? |
|---|---|---|---|
| pass | pass | pass | **yes** |
| fail | pass | pass | no |
| pass | fail | pass | no |
| fail | fail | fail | no |

Any single failing row is enough to stop it firing, so an action fires only when the whole list passes. The Test tab shows each row's verdict separately, which is how you tell *which* row stopped it.

#### Getting OR behavior

There is no OR *between* rows, but a single expression row can contain whatever logic you like, including OR. Put the alternatives in one row instead of splitting them across two:

```jinja2
{# Any of several statuses #}
data.status.name in ['Failed', 'Offline', 'Inventory']

{# Either of two conditions #}
data.status.name == 'Failed' or 'primary_ip4' in (snapshots.differences.added or {})

{# One thing must hold, and either of two others #}
event == 'updated' and (data.status.name == 'Failed' or data.tenant.name == 'Customer A')
```

The trade-off is legibility. Rows are individually reported by dry-run, so `A` and `B` as two rows tells you which one failed, while `A or B` in one row only tells you the row failed. Prefer separate rows for independent requirements, and a single row when the logic genuinely is "either of these".

An action with no conditions fires for every in-scope change, which is a reasonable configuration when scope alone is the filter you want.

### Presets

| Preset | Parameters | Fires when |
|---|---|---|
| Field transition | field, from, to | The field moved from one specific value to another specific value. |
| Field changed | field | The field's value changed at all, whatever it changed to. |
| Field compare | field, operator, value | The comparison holds after the change. Check **not** on the row for the opposite. |
| User is | username | A specific user made the change. |
| User is not | username | Anyone *except* a specific user made the change. Useful for ignoring an automation account. |

#### Comparison operators

**Field compare** takes an operator, so one preset covers what would otherwise be a row of near-identical
presets:

| Operator | Meaning |
|---|---|
| `=` | equals |
| `>` `>=` `<` `<=` | ordering |
| `in` | the value is one of a comma-separated list, e.g. `Active,Staged`, or, for a list field such as tags, has at least one entry in that list |
| `contains` | the value contains the text, or, for a list field such as tags, contains that entry |
| `starts with` / `ends with` | text prefix or suffix |

The ordering operators compare **numerically when both sides are numbers**, and alphabetically otherwise.
So `mtu > 1500` behaves arithmetically, while `name > 'm'` sorts by text. That means `mtu > 999` is true for
an MTU of 1500, where a purely alphabetical comparison would say otherwise.

The available presets and the parameters each accepts can also be read from the API, at `/api/extras/webhooks/presets/`, so external tooling does not need a hardcoded copy.

#### Naming a field

The **field** parameter is the field's name, and it may use dots to reach inside a related object. `status` and `status.name` both work: the first because Nautobot reduces a related object to its single most obvious value (usually its name), the second because you asked for that value explicitly. Use dots when the value you want is not the obvious one, such as `primary_ip4.address` instead of `primary_ip4`.

A path that leads nowhere, whether a misspelled field or a related object that is not set, is treated as empty and not as an error. The row fails; nothing raises.

#### Values, not labels

For a field like `status`, a preset parameter matches the **stored value**, not the display label. The form offers a dropdown so this distinction stays invisible in normal use, but it matters if you are configuring this through the API.

The reason to be strict here is that "accept either" sounds friendlier but becomes ambiguous the moment one status's label collides with another status's value, and that ambiguity would be discovered in production instead of at save time.

### Raw expressions

If no preset expresses what you need, write a Jinja2 expression instead. See [Condition Expressions](condition-expressions.md) for the available data, the rules about what passes, and the sandbox boundary.

## Testing a trigger

A Webhook's or Job Hook's detail page has a **Test** tab, and the same thing is available at `POST /api/extras/webhooks/{id}/dry-run/` (or `/api/extras/job-hooks/{id}/dry-run/`). Both report whether it would fire, broken out per part (did scope match, did each condition pass) and neither dispatches anything.

You can test against either:

- **A change log entry.** Nautobot rebuilds the before-and-after picture from what that change recorded, so the answer is the one given at the time. This works for deletions too, even though the object is gone.
- **A live object.** There is no real change to describe, so this is treated as an update in which nothing changed. A condition that requires a transition will correctly report that it would not fire.

Dry-run needs view permission on the action and on the target object. It does not need change permission, because it changes nothing.

### How faithful is it?

**Conditions are exact.** Testing and live firing run the same code, and when you replay a change log entry the conditions see exactly the same data they saw at the time. A condition that passes in one passes in the other.

**Scope is evaluated at a different moment.** Live evaluation decides scope while the change is happening; dry-run decides it now, against the object as it currently is. If the object has moved out of scope since that change, dry-run reports scope as not matched even though it matched at the time. Replaying the change of a deleted object cannot query anything at all, so scope is reported as matched and the conditions carry the verdict.

## Example: notify on a specific status transition

An engineer wants a webhook when a device at one campus goes from Staged to Active, and only then.

1. Create the Webhook as normal, pointing at the receiver:
    - Object Types: `dcim | device`
    - Type Update: checked
2. On the same form, narrow it:
    - Scope Filter: `location` = the campus in question
    - Condition: **Field transition**, field `status`, from `Staged`, to `Active`
3. Open its **Test** tab and replay a recent change log entry for that transition to confirm the verdict.

It now fires for exactly that transition on an in-scope device. It does not fire for the same transition on a device somewhere else, for a different transition on an in-scope device, or for a re-save that changed nothing.

## Sample data

A management command creates a set of realistic webhooks covering every preset and the cases that need a raw
expression, so you can see working examples without building them by hand:

```no-highlight
nautobot-server create_conditional_trigger_demo_data
```

Everything it creates is prefixed `DEMO-`, and every one points at an `example.com`
hostname that delivers nothing. Re-run with `--flush` to
delete and recreate them.

The set includes one webhook per preset, among them one comparison per operator style: an equality
check, a prefix match, a suffix match, a numeric `greater than`, a `contains` on a dotted field, and an
`in` list inverted by the row's **not**. It also includes six that need an expression (matching several values at once,
reading the previous value on a delete, asking about a tag list, combining "this field changed" with "and
the new value is set", branching on the event kind, and a substring match), one that mixes presets and an
expression across three AND-ed rows, one with no conditions at all, and one left disabled.

It also creates change log entries to test against, two per webhook: one labelled `DEMO+ ...` that makes the
it fire and one labelled `DEMO- ...` that does not. The label names the scenario, so on a webhook's Test tab
you can pick the entry you want and see both outcomes. `--no-changes` creates the webhooks alone.

!!! note
    A disabled rule can still be tested. The Test tab says so, and reports what would happen once the rule
    is enabled, so you can build and verify a rule before turning it on.

## Narrowing an existing webhook

There is no migration to perform. Scope and conditions are two more fields on the Webhook or Job Hook you already have, and both start empty, so every existing action keeps firing exactly as it does now until you fill one in.

To narrow one:

1. Edit the action and add the scope filter, the conditions, or both.
2. Verify with the **Test** tab before saving, or after.

The action's own Object Type(s) and Type Create / Update / Delete settings stay as they are. Those still decide *what kind* of change is a candidate; scope and conditions decide which of those candidates actually fire.

!!! note
    Narrowing takes effect as soon as you save. There is no intermediate state in which the action fires on both the old and the new terms, so make the change on a maintenance window if the receiver depends on the current volume.

## Duplicate events

A single logical change that touches many-to-many relationships can produce more than one change event, and therefore fire the same rule more than once. Nautobot does not suppress this.

**Receivers must tolerate the same event arriving twice.** This matters most for transition rules, which are exactly the ones where a duplicate is most likely to be acted on twice. See [Condition Expressions](condition-expressions.md#duplicate-events) for more.

## Performance

An installation with no rules is unaffected: the per-model rule lookup is cached, and a change to a model no rule watches costs one cache read and no database queries.

When rules do exist, each in-scope rule costs one primary-key-constrained existence query per changed object at capture time, the cheapest query the ORM can issue. Condition evaluation itself happens in a background worker against a frozen snapshot, touches no database, and takes microseconds.

## Permissions

There is no separate permission for scope and conditions. They are fields on the Webhook and Job Hook models, so the permission that governs them is the one that already governs the action: `extras.change_webhook` or `extras.change_jobhook`. Dry-run needs only the matching `view` permission, plus view permission on the object being tested.

!!! warning
    An expression is evaluated code. It is sandboxed, but it is still code, so **permission to edit webhooks and job hooks should be treated with the same sensitivity as permission to edit webhook body templates**.
