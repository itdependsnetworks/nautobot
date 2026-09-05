# Nautobot v3.3

This document describes all new features and chagnes in Nautobot 3.3.

## Upgrade Actions

### Administrators

TODO

## Release Overview

### Added

#### Permission Policies

Permission policies add a reusable layer above object permissions. A [permission policy](../user-guide/platform-functionality/users/permissionpolicy.md) names object types, actions and a constraint template with named parameters such as `{{ tenant }}`; a [policy assignment](../user-guide/platform-functionality/users/policyassignment.md) binds the policy to parameter values and to users or groups. Nautobot renders the constraints when it resolves a user's permissions and never writes object permission records, so a change to a policy or assignment takes effect on the next request with nothing to clean up.

When authoring a policy, Nautobot proposes the lookup path from each object type to each parameter (for example `device__tenant` on an interface), and a visual constraint editor lets an administrator build a constraint by browsing a model's fields and relations, choosing a lookup, and entering a value, with the JSON always available. A preview reports how many objects a policy would match before it is assigned. Every user can review their own effective access, from both stored permissions and policy assignments, from the **Access** tab of their profile or from the REST API. A set of built-in policies covering common patterns is created on upgrade.

### Changed

TODO

#### Enhanced Export/Import

The object export/import functionality has been enhanced in several ways:

- JSON and YAML formats are now supported in addition to the existing CSV format support.
- Imports can now update existing records as well as create existing records, when requested ("upsert" functionality).
- CSV export/import now includes a metadata header row, and includes support for a wider range of many-to-many fields.

For more details, refer to the [import and export documentation](../user-guide/feature-guides/import-and-export.md).

<!-- pyml disable-num-lines 2 blanks-around-headers -->

<!-- towncrier release notes start -->
