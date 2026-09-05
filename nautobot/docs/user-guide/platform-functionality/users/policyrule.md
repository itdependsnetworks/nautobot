# Policy Rules

+++ 3.3.0

A policy rule states what a [permission policy](permissionpolicy.md) grants on one object type, and how that object type reaches each of the policy's [parameters](policyparameter.md). A policy has at most one rule per object type.

A rule has:

* **Policy** - the policy the rule belongs to.
* **Object type** - the model the rule applies to, chosen from the same set an object permission may name.
* **Actions** - `view`, `add`, `change`, `delete`, and any custom action such as `run`.
* **Constraint template** - a JSON constraint in exactly the [shape a stored permission uses](objectpermission.md#constraints), except that a value may be a placeholder such as `"{{ tenant }}"`. A placeholder must occupy a complete value; Nautobot never inserts a parameter into the middle of a string, so a value can never change the structure of a constraint or of a lookup path. `{}` means no constraint on this object type.
* **Path map** - for every parameter the template uses, the lookup path and lookup that reach the parameter from this object type (`{"path": "device__tenant", "lookup": "in"}`). Nautobot derives it from the template when the rule is saved through the user interface; the REST API accepts it directly and, when the template is omitted, generates the template from it.

Rules are listed under **Extensibility > Users > Policy Rules**, and on the detail page of their policy, where the **Add** button pre-selects the policy. They can also be edited in place on the policy's own form.

## Validation

A rule is validated against its object type when it is saved: every lookup path in the template must exist on the model, an `object` parameter's path must end at the parameter's target model with the lookup the parameter requires (`in` when it accepts several values, `exact` otherwise), a `string` parameter's path must end at a text field, and every placeholder must name a parameter of the policy. Error messages name the object type.

A rule does not have to use every parameter of its policy, so one policy can scope devices by region and circuits by tenant. An object type not scoped by a parameter is marked as such on the policy's detail page, so the omission is never hidden.

## Suggested paths and the constraint editor

The rule form proposes, for each object parameter of the selected policy, the lookup paths from the object type to the parameter's model, shortest first; selecting one adds the condition to the template. The visual constraint editor presents the object type's fields as a tree that can be expanded along relations, offers the lookups valid for the chosen field, and renders a value widget matched to the field's type. See the [permission policy](permissionpolicy.md#resolving-lookup-paths) page for the details of path resolution, the `in_tree` lookup for tree models, and the editor.
