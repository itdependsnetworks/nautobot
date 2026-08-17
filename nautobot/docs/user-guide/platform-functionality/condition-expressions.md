# Condition Expressions

When no [condition preset](conditional-triggers.md#presets) expresses what you need, a condition can be a Jinja2 expression you write yourself. This page is the contract: what data you get, what counts as passing, and what happens when something goes wrong.

Presets are built on the same engine, so everything here describes their behavior too.

## The shape of an expression

A condition is **one bare Jinja2 expression**, the kind of thing you would put inside `{{ }}` in a template, but written without the delimiters:

```jinja2
data.status.name == 'Active'
```

Not `{{ data.status.name == 'Active' }}`, and not `{% if ... %}`. Both are rejected when you save the rule.

Three consequences:

- **One expression, not a program.** There is nowhere to assign an intermediate variable, because `{% set %}` is a statement. Neither are loops.
- **One expression, but not necessarily one line.** You can break a long expression across lines for readability; that is still one expression.
- **You rarely need a long one.** Conditions on a rule are AND-ed, so instead of joining checks with `and`, add another condition row. Two short rows are easier to read, and dry-run tells you which one failed.

Plenty fits inside a single expression:

**Combine checks**

```jinja2
A and B
A or B
not A
```

**Choose between values, or test membership**

```jinja2
'a' if condition else 'b'
data.status.name in ['Active', 'Staged']
'status' in snapshots.differences.added
```

**Ask whether something was provided**

```jinja2
data.tenant is defined
snapshots.postchange is none
```

**Transform a value before comparing it**

```jinja2
data.name | upper == 'DEV-1'
```

**Ask a question about a list**

```jinja2
data.tags | map(attribute='name') | join(',')
data.tags | selectattr('name', 'equalto', 'prod') | list | length > 0
```

## What you get

A condition looks at a snapshot of the change, taken at the moment it happened and never re-read afterwards. It is not a live view of the database. That is what makes two awkward cases behave normally: a deleted object, which could not be looked up any more, and an object that changed again before the rule was evaluated.

These names are available, and only these:

| Name | Contains |
|---|---|
| `data` | The serialized object as it is after the change. |
| `snapshots.prechange` | The serialized object before the change. `None` for a create. |
| `snapshots.postchange` | The serialized object after the change. `None` for a delete. |
| `snapshots.differences.added` | The fields that changed, with their new values. |
| `snapshots.differences.removed` | The same fields, with their previous values. |
| `event` | `created`, `updated`, or `deleted`. |
| `model` | The model name, e.g. `device`. |
| `username` | Who made the change. |
| `request_id` | The request that made it, for correlating with the change log. |
| `timestamp` | When it happened. |

These are the same names the webhook body-template context uses, so an expression that works in one works in the other.

## What counts as passing

In general, you should be using comparisons, such as `==`, `!=`, `>`, etc. which will return a `true` or `false`. However, that is not compuslory in Jinja Expressions, so it is important to know what constitutes as passing or not.

A condition passes when its result is **anything other than empty, zero, or false**. It does not have to be `true`; any value with content in it counts.

| Result | Passes? | Why |
|---|---|---|
| `'Active'` | yes | a string with something in it |
| `'hello-world'` | yes | likewise, the content is irrelevant, only that it is not empty |
| `'0'`, `'false'`, `'no'` | **yes** | still non-empty strings. Quoting matters |
| `1`, `-1`, `99` | yes | any non-zero number, including negatives |
| `['a']`, `{'a': 1}` | yes | a list or a set of values with at least one entry |
| `true` | yes | |
| `''` | no | the empty string |
| `none` | no | no value at all |
| `0`, `0.0` | no | zero |
| `[]`, `{}` | no | an empty list, or no values |
| `false` | no | |
| anything not in the payload | no | see the next section |

### A bare field name is an "is it set?" test

This catches people out. Writing a field on its own does not compare it to anything. It asks whether the field has a value:

```jinja2
data.status.name
```

That passes for a device whose status is `Active`, and equally for `Failed`, `Staged`, or any other status, because every one of them is a non-empty string. It only fails when the field is empty or absent. If you meant "the status is Active", say so:

```jinja2
data.status.name == 'Active'
```

Used deliberately, the bare form is useful: `data.primary_ip4` is a good way to ask "does this device have a primary IP at all?"

### Watch the quotes

`'false'` and `'0'` **pass**, because they are strings with characters in them. Only `false` and `0` without quotes are false. If you are comparing against a field that holds the text `"false"`, compare it explicitly rather than relying on the value being falsy:

```jinja2
data.some_field == 'false'
```

## Missing data is false, not an error

Naming something that is not in the payload evaluates to false. It does not raise, and it does not stop the rule from being evaluated.

```jinja2
data.no_such_field                 {# false #}
snapshots.postchange.status        {# false on a delete, where postchange is None #}
a.deeply.nested.path.that.is.absent  {# false #}
```

This is what lets one rule cover creates, updates, and deletes without special-casing each. On a delete there is no `postchange`, so a condition referring to it simply does not pass.

An expression that *genuinely* errors, dividing by zero for instance, also fails its condition instead of propagating. The error is recorded so you can find it, the rule does not fire, and every other rule for the same change carries on unaffected.

## Comparing related fields

A related field such as `status` or `role` is recorded as a nested object, not a bare value:

```jinja2
data.status.name == 'Active'
```

Depending on how the object was serialized, the same field can instead have been recorded as a bare identifier. To compare without having to know which, use the `event_value` filter, which reduces either form to the same comparable value:

```jinja2
data.status | event_value == 'Active'
```

Presets use this internally, which is why a preset comparison works regardless of how the field was recorded.

### Reading a field by name

`field_value` takes a container and a dotted path, and returns the value at that path already reduced by
`event_value`. It is what the presets use to turn a **field** parameter into a value, and it is available to
expressions too:

```jinja2
{# Equivalent to data.status | event_value #}
field_value(data, 'status')

{# Reaching further in #}
field_value(data, 'primary_ip4.address')
```

Written out, `data.status | event_value` is clearer, so reach for `field_value` when the path itself is the
variable part, comparing the same path across prechange and postchange for example:

```jinja2
field_value(snapshots.prechange, 'tenant.name') != field_value(snapshots.postchange, 'tenant.name')
```

A path that leads nowhere returns nothing, which is falsy, so a misspelled field fails its row rather than
raising.

## Examples

```jinja2
{# A device came into service #}
snapshots.prechange.status | event_value == 'Staged' and snapshots.postchange.status | event_value == 'Active'

{# Anything about the name changed #}
'name' in (snapshots.differences.added or {})

{# Not an automation account #}
username != 'svc-automation'

{# A create, in a particular tenant #}
event == 'created' and data.tenant.name == 'Customer A'

{# Several conditions at once. You can also express these as separate rows, which is easier to read #}
event == 'updated' and data.status.name == 'Active' and username != 'svc-automation'
```

## Available filters

Expressions have the same filters as every other user-authored template in Nautobot: Jinja2's built-ins, the [netutils](https://netutils.readthedocs.io/) convenience filters, Nautobot's own template helpers, and `event_value` described above.

## The sandbox

Expressions run in Nautobot's sandboxed Jinja2 environment, the same one that renders webhook body templates and computed fields.

- **Expressions only.** Statements and macros (`{% for %}`, `{% set %}`, and so on) are a syntax error, not something the sandbox has to defend against.
- **No ORM access.** The evaluation context holds only the frozen snapshot. There are no model instances to traverse, so an expression cannot reach the database, amplify queries, or walk to something unbounded.
- **Attribute access is restricted.** Introspection routes into Python internals are blocked, and a blocked access is falsy, so such a condition fails.

Expressions are validated when you save the rule, so one that does not parse is rejected then rather than discovered by a worker later.

!!! warning
    Sandboxed is not the same as harmless. A trusted user can still write an expression that is slow, iterating a large list with `selectattr` for example. Per-condition evaluation time is recorded so a slow rule can be identified. Treat permission to edit webhooks and job hooks with the same sensitivity as permission to edit webhook body templates.

## Duplicate events

A single logical change that touches many-to-many relationships can emit more than one change event, and so fire the same rule more than once. Nautobot does not deduplicate these.

**Write receivers to tolerate the same event arriving twice.** In practice this means making the action idempotent: keyed on `request_id` if you need to recognize a repeat, or simply written so that applying it twice has the same effect as applying it once.

This matters most for transition rules. "Status went from Staged to Active" reads as a one-time occurrence, which makes it the kind of event most likely to be acted on twice if it arrives twice, opening two tickets or sending two pages. A condition on `data` or on `differences` is usually less sensitive, because re-applying it is more often harmless.

## Compilation

Expressions are compiled once per process and reused, keyed on the text of the expression. A preset shared by fifty rules is compiled once, and editing an expression compiles the new text on first use. You do not need to do anything to benefit from this, but it is why a rule with a complex condition costs no more per event than a simple one.
