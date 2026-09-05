# Policy Assignments

+++ 3.3.0

A policy assignment binds a [permission policy](permissionpolicy.md) to the values of its parameters and to the users and groups that receive the resulting access. One policy with two assignments for two different tenants produces two independent sets of access.

An assignment has:

* **Policy** - the policy that defines the access. A policy with no rules cannot be assigned, and a policy that has assignments cannot be deleted until its assignments are removed.
* **Name** - unique.
* **Enabled** - if unchecked, the assignment grants nothing but remains on record.
* **Parameter values** - one value (or, for a multi-valued parameter, a list of values) for every parameter the policy declares. Object parameters store primary keys; the user interface presents them as object selectors.
* **Users** and **groups** - who receives the access, in the same way as an object permission.

## Generated constraints

Nautobot does not write object permission records for an assignment. It renders the constraints when it resolves a user's permissions, once per user per request, and merges them with the constraints from stored permissions. The assignment detail view and the REST API endpoint `GET /api/users/permission-policy-assignments/{id}/constraints/` show the exact JSON that permission resolution produces for each object type, so an administrator can always read what an assignment grants.

The **Generated constraints** panel lists the equivalent [object permission](objectpermission.md) records: rules with the same actions and constraints share a row listing all of their object types, which is how object permissions are normally written. The table's Configure button offers a **Definition (JSON)** column, off by default, showing each record in the shape accepted by `POST /api/users/permissions/`; adding `users` or `groups` to it creates the equivalent stored permission by hand.

Because nothing is stored, no record can drift from its policy, and there is no cleanup step. Disabling or deleting an assignment ends the access at the user's next request.

!!! note
    The object permission list view, the `/api/users/permissions/` endpoint and other tools that read stored permissions do not include policy-generated access. Use the effective access view to see everything a user is granted.

## Missing parameter values

When a parameter is added to a policy that already has assignments, those assignments supply no value for it. Such an assignment grants nothing (permission resolution skips it and logs an error) rather than granting unconstrained access. Nautobot flags this in several places: saving the policy warns which assignments now lack a value, the assignment list shows a "missing value" badge, the assignment detail page shows a warning, and the effective access page names the affected assignments. Edit each assignment to supply the value and the access resumes at the user's next request.

## Effective access

Every user can see their own effective access from the **Access** tab of their profile. The page lists each object type and action the user is granted, and for each grant names its source: either a stored object permission or a policy assignment together with its policy. Superusers hold every permission implicitly and see only explicit grants in the list. View exemptions configured with `EXEMPT_VIEW_PERMISSIONS` are not represented.

The same information is available from the REST API at `GET /api/users/users/effective-access/` for the requesting user. An administrator with permission to view users, object permissions and policy assignments can read another user's access at `GET /api/users/users/{id}/effective-access/`.

## Preview

The **Preview** tab of an assignment runs the assignment's stored values through the policy and reports, per object type, how many objects match and lists the first few as a sample. The count covers every match, the sample is restricted to objects the requesting user can already view, and where the constraint has an equivalent list filter the count links to that filtered list.
