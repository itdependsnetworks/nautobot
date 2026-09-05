# Permission Policies

+++ 3.3.0

A permission policy is a reusable definition of access. Where an [object permission](objectpermission.md) is one hand-written record that binds a JSON constraint to specific users and groups, a policy separates the *shape* of the access from the *values* it applies to. An administrator writes a policy once, for example "read access to the devices, interfaces and IP addresses of a tenant", and then creates one [policy assignment](policyassignment.md) per tenant and per team.

A policy grants nothing on its own. Nautobot never writes object permission records for a policy. Instead, when it resolves a user's permissions during a request, it reads the user's enabled assignments, substitutes each assignment's parameter values into the policy's constraint templates, and adds the result to the same set of constraints that stored object permissions produce. The rest of permission enforcement is unchanged and cannot tell the two sources apart. Because nothing is stored, a change to a policy or an assignment takes effect at the next request, and deleting an assignment needs no cleanup.

## Editing a policy

A policy's parameters and rules are edited in two places that behave identically: in place on the policy's own form, where parameters and rules are rows that are validated and saved together with the policy, and on their own pages under **Extensibility > Users**, [Policy Parameters](policyparameter.md) and [Policy Rules](policyrule.md), which the **Add** buttons on the policy's detail page open with the policy pre-selected. A policy may be saved before it is complete; until it has at least one rule and every parameter is used by a rule, its detail page reports that it cannot be assigned.

## Parameters

A policy may declare named parameters. Each assignment must supply a value for every parameter. A parameter has:

* **Name** - the placeholder token used in rule templates, written as `{{ name }}`. Names are lowercase identifiers.
* **Kind** - `object` or `string`.
    * An `object` parameter references instances of one model (its **target object type**), for example Tenant. Assignments store the primary keys of the selected objects, so a rename of the referenced object does not affect the access.
    * A `string` parameter stores plain text, for example a name prefix. If the text no longer matches anything, the access silently shrinks to nothing; that is the documented consequence of choosing this kind.
* **Multiple** - whether an assignment may supply more than one value. A multi-valued parameter is rendered as a single `__in` lookup.

A policy with no parameters is valid and grants the same access to everyone it is assigned to.

## Rules

A rule states what the policy grants on one object type:

* **Object type** and **actions** - the same values an object permission uses, including custom actions such as `run`.
* **Constraint template** - a JSON constraint in exactly the [shape a stored permission uses](objectpermission.md#constraints), except that a value may be a placeholder such as `"{{ tenant }}"`. A placeholder must occupy a complete value; Nautobot never inserts a parameter into the middle of a string, so a value can never change the structure of a constraint or of a lookup path. `{}` means no constraint on this object type.
* **Path map** - for every parameter the template uses, the lookup path and lookup that reach the parameter from this object type (`{"path": "device__tenant", "lookup": "in"}`). The user interface derives it from the template. A parameter the template does not use has no entry, and the rule is simply not scoped by it; the policy detail page marks such object types as "not scoped by this parameter" so the omission is never hidden.

A rule does not have to use every parameter, so one policy can scope devices by region and circuits by tenant. Every declared parameter must, however, be used by at least one rule of the policy, because a parameter nobody uses would still have to be supplied on every assignment. A policy that declares an unused parameter, or that has no rules, can be saved but not assigned; its detail page and the save message say why, naming the parameter.

The `$user` token continues to work as it does in a stored permission. It is not a policy placeholder; the permission evaluator substitutes it at query time.

### Resolving lookup paths

One parameter needs a different lookup path on every object type: a device reaches its tenant as `tenant`, an interface as `device__tenant`. When editing a rule, Nautobot reads the model metadata and proposes candidate paths, shortest first, together with the relations each one crosses. The author confirms a path and Nautobot stores it. If no path exists, the author either moves the object type to a rule that does not use that parameter or removes it from the policy; Nautobot never widens a grant by default.

Only forward, single-valued relations are proposed. A path across a many-to-many relation or a reverse relation (for example `tags__name`) is not supported in a policy, because such a path returns duplicate rows from a restricted queryset. Those cases remain the domain of hand-written object permissions.

When a parameter references a tree model such as Location, the proposed lookup is `in_tree`: the constraint `{"location__in_tree": "{{ region }}"}` matches objects at the selected location *or anywhere beneath it*, so one region value covers every site, building and room under it without listing them. The same lookup is available in hand-written object permission constraints.

!!! warning "Provisional"
    `in_tree` is not yet ratified and needs further investigation; see the note on the [object permission](objectpermission.md#constraints) page. It may change or be withdrawn before this release is final, in which case tree-scoped policies would fall back to `in` with an explicit list of nodes.

### The constraint editor

The rule form includes a visual editor for the constraint template. It presents the object type's fields as a tree that can be expanded along relations, offers the lookups valid for the chosen field, and renders a value widget matched to the field's type. A value may be a literal, a policy parameter, or the current user. Conditions within a group must all match; multiple groups match if any group matches, which corresponds to a list of constraint objects.

JSON remains the stored form. A constraint that the editor cannot represent, such as one that crosses a many-to-many relation, opens in the JSON view and is saved unchanged.

## Preview

Before assigning a policy, an administrator can open the policy's **Preview** tab. The table has one row per object type the policy covers, with the rule's actions and rendered constraint. Until parameter values are supplied in the form above the table, the constraints show the `{{ name }}` placeholders as written; a policy with no parameters previews immediately. Once values are supplied, Nautobot reports for each object type how many objects match and lists the first few as a sample. The count covers every match; the sample is limited to objects the requesting user can already see, and the linked count opens the full list. A count of zero is shown as zero rather than as an empty list, because zero is the usual symptom of a wrong lookup path. When the rendered constraint has an equivalent list-view filter, the count links to that filtered list; constraints that list filters cannot express identically (for example an exact match on a location, where the list filter would also include child locations) are shown without a link rather than linking to a list with a different count.

Nothing is stored by the preview itself: Nautobot renders the same constraints when it resolves a user's permissions. The equivalent object permission records, including a JSON form, are shown on each [assignment](policyassignment.md#generated-constraints).

## Clone

A policy is the same for every assignment; there are no per-assignment overrides. To vary a policy for one audience, clone it: the **Clone** button on a policy opens the create form pre-filled with the policy's description, parameters and rules. Nothing is stored until the form is saved, and the copy has no link to the original.

## Built-in policies

Nautobot ships with a small set of policies that cover common patterns. They are ordinary policies: an administrator may edit or delete them, and a later upgrade never overwrites a policy that has been changed or removed.

| Name | Parameters | Grants |
| --- | --- | --- |
| `nautobot-default-tenant-device-viewer` | `tenant` (one or more tenants) | View devices, interfaces, racks, prefixes, IP addresses and virtual machines of the selected tenants |
| `nautobot-default-tenant-device-operator` | `tenant` (one or more tenants) | View, add, change and delete the same object types |
| `nautobot-default-reference-data-viewer` | none | View locations, location types, manufacturers, device types, platforms, roles, statuses, tags, tenants and tenant groups |
| `nautobot-default-export-job-runner` | none | View and run the built-in export job; view one's own job results |

!!! tip "Trying it out in a development environment"
    `nautobot-server create_permission_policy_demo_data` creates six demo users (password `nautobot`), each in its own group with a policy assignment that illustrates a pattern: a tenant operator on the built-in tenant policy, three regional IT operators sharing one location-parameterized policy, a circuits owner on an unparameterized policy, and a job runner whose multi-valued parameter selects the jobs they may run. `--flush` removes them again. Never run it on a production instance.

!!! warning
    Nautobot combines all of a user's permissions with a logical OR and has no deny rule. A policy that grants an object type without constraint therefore widens any other permission that limits the same object type. The built-in policies restrict unconstrained grants to organizational and reference data for this reason.

## REST API

Policies are managed at `/api/users/permission-policies/`, with their `parameters` and `rules` as nested lists that are created and updated in the same request. Read-only listings of parameters and rules are available at `/api/users/policy-parameters/` and `/api/users/policy-rules/`. Additional endpoints:

* `GET /api/users/permission-policies/resolve-path/?content_type=dcim.interface&target_content_type=tenancy.tenant` returns candidate lookup paths, shortest first. An empty list means no path exists.
* `POST /api/users/permission-policies/{id}/preview/` with `{"parameter_values": {...}}` returns a count and sample per object type.
