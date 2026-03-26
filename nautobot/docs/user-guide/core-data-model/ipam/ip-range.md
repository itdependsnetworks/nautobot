# IP Range

## Overview

An IP Range represents a contiguous span of IP addresses defined by a start address and an end address, both within the same parent Prefix. IP Ranges are useful for representing blocks of addresses that have a specific purpose without creating individual IP Address records for each address.

Common use cases include:

- A DHCP scope (e.g., `10.10.1.50-10.10.1.200`) managed by an external server
- An exclusion zone reserving addresses for network appliances
- A NAT pool spanning a contiguous block of public addresses

The IP Range model provides the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start_address` | IP address | Yes | First IP address in the range, inclusive. |
| `end_address` | IP address | Yes | Last IP address in the range, inclusive. Must be the same IP version as `start_address` and greater than or equal to it. |
| `parent` | ForeignKey to Prefix | Yes | The parent Prefix that contains this range. The start and end addresses must both fall within the parent prefix. |
| `status` | ForeignKey to Status | Yes | Operational status of the range (e.g., Active, Reserved). |
| `role` | ForeignKey to Role | No | Functional role of the range. |
| `tenant` | ForeignKey to Tenant | No | Optional tenant ownership. |
| `description` | string | No | Free-form description. |
| `count_as_utilized` | boolean | No | If enabled, this range is counted as fully utilized in parent prefix utilization calculations, regardless of how many individual IP Address objects exist within it. |
| `is_exclusive` | boolean | No | If enabled, individual IP Address objects cannot be created within this range. Attempting to do so will raise a validation error. |

## Details

IP Ranges coexist with individual IP Address objects within a prefix. They appear as rows in the IP Addresses tab of the parent prefix detail view, sorted at their start address position.

### Derived Properties

| Property | Description |
|---|---|
| `ip_version` | Derived from `start_address`; set automatically on save. |
| `size` | Total number of addresses in the range: `(end_address − start_address) + 1`. |
| `percent_utilized` | Percentage of addresses within the range that have a corresponding IP Address object. |

### Validation Rules

- `start_address` and `end_address` must be the same IP version (both IPv4 or both IPv6).
- `end_address` must be greater than or equal to `start_address`.
- Both addresses must fall within the bounds of the `parent` prefix.
- IP Ranges within the same namespace may not overlap with one another.
- If `is_exclusive` is enabled, no existing IP Address objects may exist within the range at the time it is saved.

### Prefix Utilization

- If `count_as_utilized` is enabled on a range, the entire span of addresses is added to the parent prefix's utilization numerator, whether or not individual IP Address objects exist within it.
- If `is_exclusive` is enabled, addresses within the range are excluded from the "available" pool when calculating available IPs for the parent prefix.

### Exclusive Ranges

When a range has `is_exclusive` enabled:

- Individual IP Address objects cannot be created at any address within the range. The model's `clean()` method enforces this at the database level.
- The range cannot be saved with `is_exclusive=True` if IP Address objects already exist within it.
- The addresses within the range are excluded from the parent prefix's available-IP pool.

### Deletion Behavior

When a parent Prefix is deleted:

- If the prefix has a grandparent (the parent's own parent), any IP Ranges are reparented to the grandparent prefix.
- If the prefix has **no** grandparent (it is a top-level prefix), any IP Ranges within it are **cascade-deleted** along with the prefix. This differs from IP Address objects, which raise a `ProtectedError` in the same situation. A warning is logged when this occurs.
