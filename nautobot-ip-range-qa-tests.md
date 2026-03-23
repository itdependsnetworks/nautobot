# IPRange Feature — Manual QA Test Plan

## 1. IPRange CRUD (UI)

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 1.1 | Create basic range | IPAM > IP Ranges > Add. Fill in start_address, end_address, parent prefix, status. Save. | Range created, appears in list view. |
| 1.2 | Create range with all fields | Add range with start/end, parent, status, role, tenant, description, count_as_utilized=True, is_exclusive=False, tags. | All fields saved and displayed on detail page. |
| 1.3 | Standards| Edit, Save, Bulk, Bulk Delete. | Operational. |

## 2. IPRange Validation

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 2.1 | End before start | Create range where end_address < start_address. | ValidationError: end must be >= start. |
| 2.2 | Range outside parent | Create range where start or end falls outside the parent prefix. | ValidationError: range must be within parent. |
| 2.3 | Overlapping ranges | Create two ranges in the same prefix with overlapping address spans. | ValidationError on the second range: overlap detected. |
| 2.4 | Duplicate range | Create exact same start/end/parent range twice. | UniqueConstraint error (parent, start_address, end_address). |
| 2.5 | Exclusive with existing IPs | Set is_exclusive=True on a range that already contains IPAddress objects. | ValidationError: "Cannot mark this range as exclusive: N IP addresses already exist..." |
| 2.6 | IP in exclusive range | Create an IPAddress within an existing exclusive IPRange. | ValidationError: "IP falls within exclusive IP Range..." |
| 2.7 | Parent prefix required | Try to create range with no parent prefix. | Form validation error on parent field. |
| 2.8 | Single-IP range | Create range where start_address == end_address. | Range created, size=1. |
| 2.9 | Full-prefix range | Create range covering entire parent prefix address space. | Range created (if no overlaps), size equals prefix size. |
| 2.10 | IPv6 range | Create range with IPv6 start/end within an IPv6 prefix. | Range created, ip_version=6. |


## 3. Prefix Detail View Integration

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 3.1 | IP Ranges tab visible | View a Prefix detail page that has IP ranges. | "IP Ranges" tab appears (tab_id: ip-ranges). |
| 3.2 | IP Addresses tab interleaving | View Prefix > IP Addresses tab with both IPs and ranges. | IP ranges appear inline at their start_address position, available-IP gap tuples shown between objects. |
| 3.3 | Add IP Range button | On Prefix detail, look for the "Add IP Range" button. | Button appears, links to IPRange add form pre-populated with parent=prefix.pk. |
| 3.4 | Add IP Range pre-populates start | Click Add IP Range when prefix has available IPs. | start_address pre-populated with first available IP (without mask). |
| 3.5 | Add IP Range pre-populates tenant | Click Add IP Range on a prefix that has a tenant. | tenant and tenant_group pre-populated from parent prefix. |
| 3.6 | Range absorbs available IPs | Prefix has a range 10.0.0.5–10.0.0.10. View IP Addresses tab with show_available=true. | No "available" entries shown within 10.0.0.5–10.0.0.10 span; gaps before/after the range shown correctly. |

## 4. count_as_utilized Behavior

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 4.1 | Utilization without flag | Create range with count_as_utilized=False inside a prefix. Check prefix utilization. | Range does NOT inflate prefix utilization percentage. |
| 4.2 | Utilization with flag | Create range with count_as_utilized=True inside a prefix. Check prefix utilization. | Range's full span counts as utilized; prefix utilization increases accordingly. |
| 4.3 | Toggle flag | Edit range, flip count_as_utilized from False to True. | Prefix utilization recalculates to include range span. |

## 5. is_exclusive Behavior

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 5.1 | Exclusive blocks IP creation | Create exclusive range 10.0.0.5–10.0.0.10. Try to create IPAddress 10.0.0.7. | IPAddress creation blocked with ValidationError referencing the exclusive range. |
| 5.2 | Non-exclusive allows IP creation | Create non-exclusive range. Create IPAddress within it. | IPAddress created successfully. |
| 5.3 | Exclusive reduces available IPs | Create exclusive range. Check prefix get_available_ips. | Exclusive range addresses subtracted from available IP set. |
| 5.4 | Exclusive after IPs exist | Create IPs first, then try to create exclusive range covering them. | Range creation blocked: "Cannot mark as exclusive: N IP addresses already exist..." |

## 6. Prefix Deletion Cascade

| # | Test | Steps | Expected |
|---|------|-------|----------|
| 6.1 | Delete prefix with ranges (has grandparent) | Delete a child prefix that has IPRanges and whose parent prefix exists. | TDB |
| 6.2 | Delete prefix with ranges (no grandparent) | Delete a top-level prefix that has IPRanges. | TDB|
