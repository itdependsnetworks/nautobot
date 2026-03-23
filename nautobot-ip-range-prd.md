
1. Use Cases

The following are common scenarios where users need to manage contiguous blocks of IP addresses without creating individual IP Address records for each address:

- A DHCP scope of 10.10.1.50–10.10.1.200 to be represented without creating individual IP objects
- An exclusion zone (e.g., reserving 192.168.1.1–192.168.1.9 for network appliances)
- A NAT pool spanning 203.0.113.64–203.0.113.95

2. What

Introduce a new first-class IPAM object: the IP Range. An IP Range represents an contiguous span of IP addresses defined by a start address and an end address, both within the same IP version. IP Ranges are nested within prefixes and coexist with individual IP Address objects.

2.1 Requirements

- Allow users to define a named, contiguous span of IP addresses with a start and end address.
- Associate IP Ranges with a parent prefix automatically (when possible).
- Allow IP Ranges to be prefix utilization calculations (this is a configuration option from mark_utilized).
- Prevent individual IP Address objects from being created within a Range when the Range when configured to.
- Display IP Ranges inline within the prefix detail view, alongside IP addresses.
- All standard PrimaryModel implementations (status, tenant, api, graphql, etc.)
- TODO: Figure out how this should interact with bulk IP and IP Range import

2.2 Non-Requirements

- IP Ranges do not automatically create or manage individual IP Address records within their span.
- IP Ranges do not support non-contiguous address sets (e.g., every even address in a /24). Use multiple ranges.
- No automatic splitting or merging of overlapping ranges is performed — overlaps are a validation error.

3. Model

| Field           | Type                | Required | Description                                                                                   |
|-----------------|---------------------|----------|-----------------------------------------------------------------------------------------------|
| start_address   | `VarbinaryIPField` | Yes      | First address in the range, inclusive. Must include prefix length.                            |
| end_address     | `VarbinaryIPField` | Yes      | Last address in the range, inclusive. Must include prefix length.                             |
| count_as_utilized   | Boolean     | Yes      | Forces this range to count as fully utilized in prefix calculations. (Default: No)            |
| is_exclusive    | Boolean             | Yes      | Do not allow IP addresses to be created within this space. (Default: No)                      |

> Note: include standard fields that are on IP such as role, status, custom field, etc.. 
> TODO: Do we need a special role like or status like field for dhcp? Similar for reserved?

3.1 Properties

| Property         | Description                                                                                           |
|------------------|-------------------------------------------------------------------------------------------------------|
| size             | Total number of IP addresses in the range: (end − start) + 1.                                         |
| percent_utilized | Percentage of addresses within the range that have an IP Address object.                              |

3.2 Constraints & Validation Rules

- start_address and end_address IPs must be within the Prefix it is assigned to
- start_address must be numerically less than to end_address.
- Must not overlap with other IP Range
- Must not overlap with other IP Addresses when is_exclusive=True

4. View Considerations

- Standard CRUD views for IP Range objects
- There should be a an IP Range Tab in Prefix Detail

4.1 IP Address Tab in Prefix Detail

- IP Range objects are rendered as a single row in the address table, IP Address contain an icon (TODO: Need to consider if this is always are only when is_exclusive)
- Next Available IP skips all addresses covered by is_exclusive ranges. For active ranges with no exclusive flag, addresses within the range are included in the available pool. 
- IP Range are positioned at the start address of the range in the sort order.
- IP Range Objects do not consume pagination slots. 
- The Add IP Address button, when clicked with an address that falls within a blocking range, produces validation
- There is an "Add IP Range" button on both ip range and ip address tabs starting at the first available address in the subnet.

5. Acceptance Criteria

- A user can create an IP Range with valid start/end addresses and it appears in the IPAM > IP Ranges list view.
- Creating an IP Range with start > end raises a validation error.
- Creating two overlapping IP Ranges in the same namespace raises a validation error on the second range.
- An IP Range appears in the IP Ranges panel of its parent prefix's detail view.
- Prefix utilization increases correctly when an IP Range with mark_utilized = True is created within it.
- The available-ips endpoint for a prefix excludes addresses within is_exclusive ranges.
- Creating an IP Address within an is_exclusive IP Range is blocked with a descriptive error.
- The IP Address tab in Prefix Detail correctly renders IP Ranges inline with IP Addresses, sorted by address, and does not consume pagination slots.
- All standard views, API endpoints, and GraphQL queries for the IP Range model work as expected.

6. Stories

- Create IP Range model with validations and properties for IP Range (not IP yet)
- Create Standard CRUD views for IP Range (including Prefix detail tab)
- Update Available IP logic in API, IP Address, and Prefix Detail (IP Adrress Tab) to account for IP Ranges with `mark_utilized=True` and `is_exclusive=True`
- Finish IP Address tab on Prefix Detail (update rows to render and add "Add IP Range" button)
- Update Prefix utlization logic
- Create Standard API, GraphQL for IP Range