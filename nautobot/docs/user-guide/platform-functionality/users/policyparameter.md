# Policy Parameters

+++ 3.3.0

A policy parameter is a named value that a [permission policy](permissionpolicy.md) declares and that every [policy assignment](policyassignment.md) of that policy must supply. The name is the placeholder used in the policy's rule templates, written as `{{ name }}`.

A parameter has:

* **Policy** - the policy that declares it. A name is unique within its policy.
* **Name** - a lowercase identifier: letters, digits and underscores, starting with a letter.
* **Kind** - `object` or `string`.
    * An `object` parameter references instances of one model, its **target object type** (for example Tenant). Assignments store the primary keys of the selected objects, so renaming a referenced object does not change the access. A rule that uses the parameter must end its lookup path at that model.
    * A `string` parameter stores plain text, for example a name prefix. A rule places it under a text field (for example `name__istartswith`). If the text no longer matches anything, the access silently shrinks to nothing.
* **Multiple** - whether an assignment may supply more than one value. A multi-valued parameter is rendered as a single `__in` lookup (or `in_tree` for tree models).

Parameters are listed under **Extensibility > Users > Policy Parameters**, and on the detail page of their policy, where the **Add** button pre-selects the policy. They can also be edited in place on the policy's own form.

## Adding a parameter to a policy that is in use

Every declared parameter must be used by at least one rule of its policy, and every assignment must supply a value for it. Adding a parameter therefore leaves the policy unassignable until a rule uses it, and leaves existing assignments granting nothing until they supply the new value. Nautobot reports both states when the parameter is saved, on the policy's detail page, and on each affected assignment; it never widens a grant to fill the gap.

Deleting a parameter that a rule template still references leaves that rule with an undeclared placeholder, which the policy detail page reports in the same way.
