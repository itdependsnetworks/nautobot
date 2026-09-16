# `untested_filters` probed as `generic_filter_tests` entries

Each `untested_filters` entry in core was run through the `test_filters_generic` logic inside its own test class fixtures. Attempts per filter: the plain filter name, then the filter's `field_name` if different, then `<field_name>__id` / `<field_name>__name` for `ModelMultipleChoiceFilter`-based filters. Attempts stop at the first PASS. Note `get_filterset_test_values()` picks values with a random early break, so PASS/FAIL on `TreeNodeMultipleChoiceFilter` entries can vary between runs.

## Summary

| Outcome (best attempt) | Filters |
|---|---|
| PASS | 94 |
| FAIL | 12 |
| ERROR | 184 |

### Why the plain entry doesn't work (non-passing filters)

| Diagnosis | Filters |
|---|---|
| test data has < 2 distinct values with a non-matching remainder | 99 |
| filter has `method=`; generic `__in` comparison can't express it | 51 |
| field_name isn't a real model field path (or filter name != field) | 38 |
| filterset result differs from `queryset.filter(field__in=...)` | 5 |
| ValueError | 2 |
| filterset rejects the raw values (form validation) | 1 |

### Non-passing filters by filter class

| Filter class | Filters |
|---|---|
| `BooleanFilter` | 54 |
| `NaturalKeyOrPKMultipleChoiceFilter` | 41 |
| `MultiValueCharFilter` | 18 |
| `MultiValueDateTimeFilter` | 18 |
| `ModelMultipleChoiceFilter` | 15 |
| `TreeNodeMultipleChoiceFilter` | 9 |
| `MultiValueUUIDFilter` | 8 |
| `MultipleChoiceFilter` | 8 |
| `CharFilter` | 6 |
| `ContentTypeMultipleChoiceFilter` | 4 |
| `ContentTypeFilter` | 4 |
| `MultiValueNumberFilter` | 3 |
| `ModelChoiceFilter` | 3 |
| `MultiValueFloatFilter` | 2 |
| `DateFilter` | 1 |
| `Filter` | 1 |
| `StatusFilter` | 1 |

## Filters that pass with a generic entry (ready to move into `generic_filter_tests`)

| Test class | Filter | Working entry |
|---|---|---|
| circuits.CircuitTerminationTestCase | `cable` | `("cable", "cable_termination__cable")` |
| dcim.ConsoleConnectionFilterSetTestCase | `device` | `("device", "device__name")` |
| dcim.ConsoleConnectionFilterSetTestCase | `device_id` | `("device_id",)` |
| dcim.ConsoleConnectionFilterSetTestCase | `name` | `("name",)` |
| dcim.ConsolePortTemplateTestCase | `type` | `("type",)` |
| dcim.ConsolePortTestCase | `type` | `("type",)` |
| dcim.ConsoleServerPortTemplateTestCase | `type` | `("type",)` |
| dcim.ConsoleServerPortTestCase | `type` | `("type",)` |
| dcim.ControllerFilterSetTestCase | `location` | `("location",)` |
| dcim.ControllerFilterSetTestCase | `role` | `("role",)` |
| dcim.ControllerFilterSetTestCase | `status` | `("status",)` |
| dcim.ControllerManagedDeviceGroupFilterSetTestCase | `radio_profiles` | `("radio_profiles",)` |
| dcim.ControllerManagedDeviceGroupFilterSetTestCase | `wireless_networks` | `("wireless_networks",)` |
| dcim.DeviceRedundancyGroupTestCase | `status` | `("status",)` |
| dcim.DeviceTestCase | `face` | `("face",)` |
| dcim.DeviceTestCase | `serial` | `("serial",)` |
| dcim.DeviceTypeTestCase | `subdevice_role` | `("subdevice_role",)` |
| dcim.InterfaceRedundancyGroupTestCase | `status` | `("status",)` |
| dcim.InterfaceTestCase | `device_id` | `("device_id",)` |
| dcim.ModuleBayTestCase | `module_family` | `("module_family",)` |
| dcim.ModuleTestCase | `location` | `("location",)` |
| dcim.ModuleTestCase | `module_family` | `("module_family", "module_type__module_family")` |
| dcim.PowerConnectionFilterSetTestCase | `device` | `("device", "device__name")` |
| dcim.PowerConnectionFilterSetTestCase | `device_id` | `("device_id",)` |
| dcim.PowerConnectionFilterSetTestCase | `name` | `("name",)` |
| dcim.PowerOutletTemplateTestCase | `type` | `("type",)` |
| dcim.PowerOutletTestCase | `type` | `("type",)` |
| dcim.PowerPortTemplateTestCase | `type` | `("type",)` |
| dcim.PowerPortTestCase | `type` | `("type",)` |
| dcim.RackGroupTestCase | `location` | `("location",)` |
| dcim.SoftwareImageFileFilterSetTestCase | `download_url` | `("download_url",)` |
| dcim.SoftwareVersionFilterSetTestCase | `device_types` | `("device_types", "software_image_files__device_types")` |
| dcim.SoftwareVersionFilterSetTestCase | `inventory_items` | `("inventory_items",)` |
| dcim.SoftwareVersionFilterSetTestCase | `virtual_machines` | `("virtual_machines",)` |
| dcim.VirtualDeviceContextTestCase | `identifier` | `("identifier",)` |
| extras.DynamicGroupFilterTest | `member_id` | `("member_id", "static_group_associations__associated_object_id")` |
| extras.ApprovalWorkflowDefinitionFilterTestCase | `weight` | `("weight",)` |
| extras.ContactAssociationFilterSetTestCase | `associated_object_id` | `("associated_object_id",)` |
| extras.DynamicGroupFilterSetTestCase | `member_id` | `("member_id", "static_group_associations__associated_object_id")` |
| extras.ExternalIntegrationTestCase | `ca_file_path` | `("ca_file_path",)` |
| extras.ImageAttachmentTestCase | `object_id` | `("object_id",)` |
| extras.JobFilterSetTestCase | `soft_time_limit` | `("soft_time_limit",)` |
| extras.JobFilterSetTestCase | `time_limit` | `("time_limit",)` |
| extras.JobLogEntryTestCase | `absolute_url` | `("absolute_url",)` |
| extras.JobLogEntryTestCase | `job_result` | `("job_result",)` |
| extras.JobLogEntryTestCase | `log_object` | `("log_object",)` |
| extras.JobQueueFilterSetTestCase | `description` | `("description",)` |
| extras.JobQueueFilterSetTestCase | `jobs` | `("jobs",)` |
| extras.JobResultFilterSetTestCase | `user` | `("user",)` |
| extras.ObjectChangeTestCase | `action` | `("action",)` |
| extras.ObjectChangeTestCase | `change_context` | `("change_context",)` |
| extras.ObjectChangeTestCase | `change_context_detail` | `("change_context_detail",)` |
| extras.ObjectChangeTestCase | `changed_object_id` | `("changed_object_id",)` |
| extras.ObjectChangeTestCase | `object_repr` | `("object_repr",)` |
| extras.ObjectChangeTestCase | `request_id` | `("request_id",)` |
| extras.ObjectChangeTestCase | `time` | `("time",)` |
| extras.ObjectMetadataTestCase | `assigned_object_id` | `("assigned_object_id",)` |
| ipam.IPAddressTestCase | `description` | `("description",)` |
| ipam.IPAddressTestCase | `namespace` | `("namespace", "parent__namespace")` |
| ipam.NamespaceTestCase | `description` | `("description",)` |
| ipam.PrefixLocationAssignmentTestCase | `location` | `("location", "location__id")` |
| ipam.PrefixTestCase | `location` | `("location", "locations__id")` |
| ipam.PrefixTestCase | `locations` | `("locations",)` |
| ipam.PrefixTestCase | `namespace` | `("namespace",)` |
| ipam.PrefixTestCase | `parent` | `("parent",)` |
| ipam.PrefixTestCase | `vlan_id` | `("vlan_id",)` |
| ipam.PrefixTestCase | `vlan_vid` | `("vlan_vid", "vlan__vid")` |
| ipam.PrefixTestCase | `vrfs` | `("vrfs",)` |
| ipam.VLANLocationAssignmentTestCase | `location` | `("location",)` |
| ipam.VRFTestCase | `description` | `("description",)` |
| ipam.VRFTestCase | `status` | `("status",)` |
| ipam.VRFTestCase | `virtual_device_contexts` | `("virtual_device_contexts",)` |
| virtualization.VMInterfaceTestCase | `status` | `("status",)` |
| vpn.VPNFilterTestCase | `role` | `("role",)` |
| vpn.VPNFilterTestCase | `status` | `("status",)` |
| vpn.VPNPhase1PolicyFilterTestCase | `vpn_profiles` | `("vpn_profiles",)` |
| vpn.VPNPhase2PolicyFilterTestCase | `vpn_profiles` | `("vpn_profiles",)` |
| vpn.VPNProfileFilterTestCase | `role` | `("role",)` |
| vpn.VPNTunnelEndpointFilterTestCase | `name` | `("name",)` |
| vpn.VPNTunnelEndpointFilterTestCase | `protected_prefixes` | `("protected_prefixes",)` |
| vpn.VPNTunnelEndpointFilterTestCase | `role` | `("role",)` |
| vpn.VPNTunnelEndpointFilterTestCase | `vpn_profile` | `("vpn_profile",)` |
| vpn.VPNTunnelFilterTestCase | `endpoint_a` | `("endpoint_a",)` |
| vpn.VPNTunnelFilterTestCase | `endpoint_z` | `("endpoint_z",)` |
| vpn.VPNTunnelFilterTestCase | `role` | `("role",)` |
| vpn.VPNTunnelFilterTestCase | `status` | `("status",)` |
| wireless.ControllerManagedDeviceGroupWirelessNetworkAssignmentTestCase | `vlan` | `("vlan",)` |
| wireless.RadioProfileTestCase | `controller_managed_device_groups__devices` | `("controller_managed_device_groups__devices",)` |
| wireless.RadioProfileTestCase | `rx_power_min` | `("rx_power_min",)` |
| wireless.RadioProfileTestCase | `supported_data_rates` | `("supported_data_rates",)` |
| wireless.RadioProfileTestCase | `tx_power_max` | `("tx_power_max",)` |
| wireless.RadioProfileTestCase | `tx_power_min` | `("tx_power_min",)` |
| wireless.WirelessNetworkTestCase | `controller_managed_device_groups__controller` | `("controller_managed_device_groups__controller",)` |
| wireless.WirelessNetworkTestCase | `controller_managed_device_groups__devices` | `("controller_managed_device_groups__devices",)` |

## All filters

| Test class | Filter | Filter class | field_name | method | Diagnosis | Attempts |
|---|---|---|---|---|---|---|
| circuits.CircuitTerminationTestCase | `available_for_cable` | `NaturalKeyOrPKMultipleChoiceFilter` | `available_for_cable` | `_filter_available_for_cable` | filter has `method=`; generic `__in` comparison can't express it | `available_for_cable`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, associated_contacts,<br>`available_for_cable__id`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, associated_contacts,<br>`available_for_cable__name`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, associated_contacts, |
| circuits.CircuitTerminationTestCase | `cable` | `ModelMultipleChoiceFilter` | `cable_termination__cable` |  | field_name isn't a real model field path (or filter name != field) | `cable`: ERROR FieldError: Cannot resolve keyword 'cable' into field. Choices are: _custom_field_data, associated_contacts, associated_da<br>`cable_termination__cable`: PASS |
| circuits.CircuitTerminationTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `location` |  | test data has < 2 distinct values with a non-matching remainder | `location`: ERROR ValueError: Cannot find enough valid test data for CircuitTermination field location. At least 3 unique values are require<br>`location__id`: ERROR ValueError: Cannot find enough valid test data for CircuitTermination field location__id. At least 3 unique values are req<br>`location__name`: ERROR ValueError: Cannot find enough valid test data for CircuitTermination field location__name. At least 3 unique values are r |
| data_validation.MinMaxValidationRuleFilterTestCase | `enabled` | `BooleanFilter` | `enabled` |  | test data has < 2 distinct values with a non-matching remainder | `enabled`: ERROR ValueError: Cannot find enough valid test data for MinMaxValidationRule field enabled. At least 3 unique values are requir |
| data_validation.MinMaxValidationRuleFilterTestCase | `max` | `MultiValueFloatFilter` | `max` |  | test data has < 2 distinct values with a non-matching remainder | `max`: ERROR ValueError: Cannot find enough valid test data for MinMaxValidationRule field max. At least 3 unique values are required t |
| data_validation.MinMaxValidationRuleFilterTestCase | `min` | `MultiValueFloatFilter` | `min` |  | test data has < 2 distinct values with a non-matching remainder | `min`: ERROR ValueError: Cannot find enough valid test data for MinMaxValidationRule field min. At least 3 unique values are required t |
| data_validation.RegularExpressionValidationRuleFilterTestCase | `context_processing` | `BooleanFilter` | `context_processing` |  | test data has < 2 distinct values with a non-matching remainder | `context_processing`: ERROR ValueError: Cannot find enough valid test data for RegularExpressionValidationRule field context_processing. At least 3 un |
| data_validation.RegularExpressionValidationRuleFilterTestCase | `enabled` | `BooleanFilter` | `enabled` |  | test data has < 2 distinct values with a non-matching remainder | `enabled`: ERROR ValueError: Cannot find enough valid test data for RegularExpressionValidationRule field enabled. At least 3 unique values |
| data_validation.RequiredValidationRuleFilterTestCase | `enabled` | `BooleanFilter` | `enabled` |  | test data has < 2 distinct values with a non-matching remainder | `enabled`: ERROR ValueError: Cannot find enough valid test data for RequiredValidationRule field enabled. At least 3 unique values are requ |
| data_validation.UniqueValidationRuleFilterTestCase | `enabled` | `BooleanFilter` | `enabled` |  | test data has < 2 distinct values with a non-matching remainder | `enabled`: ERROR ValueError: Cannot find enough valid test data for UniqueValidationRule field enabled. At least 3 unique values are requir |
| dcim.CableTestCase | `cable_type` | `NaturalKeyOrPKMultipleChoiceFilter` | `cable_type` |  | test data has < 2 distinct values with a non-matching remainder | `cable_type`: ERROR ValueError: Cannot find enough valid test data for Cable field cable_type. At least 3 unique values are required to test m<br>`cable_type__id`: ERROR ValueError: Cannot find enough valid test data for Cable field cable_type__id. At least 3 unique values are required to te<br>`cable_type__name`: ERROR ValueError: Cannot find enough valid test data for Cable field cable_type__name. At least 3 unique values are required to  |
| dcim.CableTestCase | `device_id` | `ModelMultipleChoiceFilter` | `terminations` | `filter_device_id` | filter has `method=`; generic `__in` comparison can't express it | `device_id`: ERROR FieldError: Cannot resolve keyword 'device_id' into field. Choices are: _abs_length, _custom_field_data, associated_contac<br>`terminations`: FAIL AssertionError: False is not true : * device_id<br>`terminations__id`: FAIL AssertionError: False is not true : * device_id<br>`terminations__name`: ERROR FieldError: Unsupported lookup 'name' for UUIDField or join on the field not permitted. |
| dcim.CableTestCase | `location_id` | `ModelMultipleChoiceFilter` | `device__location` | `filter_device` | filter has `method=`; generic `__in` comparison can't express it | `location_id`: ERROR FieldError: Cannot resolve keyword 'location_id' into field. Choices are: _abs_length, _custom_field_data, associated_cont<br>`device__location`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts,<br>`device__location__id`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts,<br>`device__location__name`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, |
| dcim.CableTestCase | `rack_id` | `ModelMultipleChoiceFilter` | `device__rack` | `filter_device` | filter has `method=`; generic `__in` comparison can't express it | `rack_id`: ERROR FieldError: Cannot resolve keyword 'rack_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts<br>`device__rack`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts,<br>`device__rack__id`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts,<br>`device__rack__name`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, |
| dcim.CableTestCase | `tenant_id` | `ModelMultipleChoiceFilter` | `device__tenant` | `filter_device` | filter has `method=`; generic `__in` comparison can't express it | `tenant_id`: ERROR FieldError: Cannot resolve keyword 'tenant_id' into field. Choices are: _abs_length, _custom_field_data, associated_contac<br>`device__tenant`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts,<br>`device__tenant__id`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts,<br>`device__tenant__name`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, |
| dcim.CableTestCase | `termination_a_id` | `MultiValueUUIDFilter` | `termination_a_id` | `_termination_a_id` | filter has `method=`; generic `__in` comparison can't express it | `termination_a_id`: ERROR FieldError: Cannot resolve keyword 'termination_a_id' into field. Choices are: _abs_length, _custom_field_data, associated |
| dcim.CableTestCase | `termination_a_type` | `ContentTypeMultipleChoiceFilter` | `termination_a_type` | `_termination_a_type` | filter has `method=`; generic `__in` comparison can't express it | `termination_a_type`: ERROR FieldError: Cannot resolve keyword 'termination_a_type' into field. Choices are: _abs_length, _custom_field_data, associat |
| dcim.CableTestCase | `termination_b_id` | `MultiValueUUIDFilter` | `termination_b_id` | `_termination_b_id` | filter has `method=`; generic `__in` comparison can't express it | `termination_b_id`: ERROR FieldError: Cannot resolve keyword 'termination_b_id' into field. Choices are: _abs_length, _custom_field_data, associated |
| dcim.CableTestCase | `termination_b_type` | `ContentTypeMultipleChoiceFilter` | `termination_b_type` | `_termination_b_type` | filter has `method=`; generic `__in` comparison can't express it | `termination_b_type`: ERROR FieldError: Cannot resolve keyword 'termination_b_type' into field. Choices are: _abs_length, _custom_field_data, associat |
| dcim.CableTestCase | `termination_id` | `MultiValueUUIDFilter` | `termination_id` | `_termination_id` | filter has `method=`; generic `__in` comparison can't express it | `termination_id`: ERROR FieldError: Cannot resolve keyword 'termination_id' into field. Choices are: _abs_length, _custom_field_data, associated_c |
| dcim.ConsoleConnectionFilterSetTestCase | `device` | `MultiValueCharFilter` | `device__name` | `filter_device` | filter has `method=`; generic `__in` comparison can't express it | `device`: FAIL AssertionError: 0 == 0 : QuerySet cannot be empty<br>`device__name`: PASS |
| dcim.ConsoleConnectionFilterSetTestCase | `device_id` | `MultiValueUUIDFilter` | `device_id` | `filter_device` | passes as plain generic entry | `device_id`: PASS |
| dcim.ConsoleConnectionFilterSetTestCase | `location` | `CharFilter` | `location` | `filter_location` | filter has `method=`; generic `__in` comparison can't express it | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, ass |
| dcim.ConsoleConnectionFilterSetTestCase | `name` | `MultiValueCharFilter` | `name` |  | passes as plain generic entry | `name`: PASS |
| dcim.ConsolePortTemplateTestCase | `type` | `MultipleChoiceFilter` | `type` |  | passes as plain generic entry | `type`: PASS |
| dcim.ConsolePortTestCase | `available_for_cable` | `NaturalKeyOrPKMultipleChoiceFilter` | `available_for_cable` | `_filter_available_for_cable` | filter has `method=`; generic `__in` comparison can't express it | `available_for_cable`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co<br>`available_for_cable__id`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co<br>`available_for_cable__name`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co |
| dcim.ConsolePortTestCase | `location` | `NaturalKeyOrPKMultipleChoiceFilter` | `device__location` |  | field_name isn't a real model field path (or filter name != field) | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, ass<br>`device__location`: ERROR ValueError: Cannot find enough valid test data for ConsolePort field device__location. At least 3 unique values are requir<br>`device__location__id`: ERROR ValueError: Cannot find enough valid test data for ConsolePort field device__location__id. At least 3 unique values are re<br>`device__location__name`: ERROR ValueError: Cannot find enough valid test data for ConsolePort field device__location__name. At least 3 unique values are  |
| dcim.ConsolePortTestCase | `type` | `MultipleChoiceFilter` | `type` |  | passes as plain generic entry | `type`: PASS |
| dcim.ConsoleServerPortTemplateTestCase | `type` | `MultipleChoiceFilter` | `type` |  | passes as plain generic entry | `type`: PASS |
| dcim.ConsoleServerPortTestCase | `available_for_cable` | `NaturalKeyOrPKMultipleChoiceFilter` | `available_for_cable` | `_filter_available_for_cable` | filter has `method=`; generic `__in` comparison can't express it | `available_for_cable`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co<br>`available_for_cable__id`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co<br>`available_for_cable__name`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co |
| dcim.ConsoleServerPortTestCase | `location` | `NaturalKeyOrPKMultipleChoiceFilter` | `device__location` |  | field_name isn't a real model field path (or filter name != field) | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, ass<br>`device__location`: ERROR ValueError: Cannot find enough valid test data for ConsoleServerPort field device__location. At least 3 unique values are <br>`device__location__id`: ERROR ValueError: Cannot find enough valid test data for ConsoleServerPort field device__location__id. At least 3 unique values <br>`device__location__name`: ERROR ValueError: Cannot find enough valid test data for ConsoleServerPort field device__location__name. At least 3 unique value |
| dcim.ConsoleServerPortTestCase | `type` | `MultipleChoiceFilter` | `type` |  | passes as plain generic entry | `type`: PASS |
| dcim.ControllerFilterSetTestCase | `capabilities` | `MultipleChoiceFilter` | `capabilities` |  | test data has < 2 distinct values with a non-matching remainder | `capabilities`: ERROR ValueError: Cannot find enough valid test data for Controller field capabilities. At least 3 unique values are required to |
| dcim.ControllerFilterSetTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `location` |  | passes as plain generic entry | `location`: PASS |
| dcim.ControllerFilterSetTestCase | `role` | `RoleFilter` | `role` |  | passes as plain generic entry | `role`: PASS |
| dcim.ControllerFilterSetTestCase | `status` | `StatusFilter` | `status` |  | passes as plain generic entry | `status`: PASS |
| dcim.ControllerManagedDeviceGroupFilterSetTestCase | `capabilities` | `MultipleChoiceFilter` | `capabilities` |  | test data has < 2 distinct values with a non-matching remainder | `capabilities`: ERROR ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field capabilities. At least 3 unique valu |
| dcim.ControllerManagedDeviceGroupFilterSetTestCase | `description` | `MultiValueCharFilter` | `description` |  | test data has < 2 distinct values with a non-matching remainder | `description`: ERROR ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field description. At least 3 unique value |
| dcim.ControllerManagedDeviceGroupFilterSetTestCase | `radio_profiles` | `NaturalKeyOrPKMultipleChoiceFilter` | `radio_profiles` |  | passes as plain generic entry | `radio_profiles`: PASS |
| dcim.ControllerManagedDeviceGroupFilterSetTestCase | `subtree` | `NaturalKeyOrPKMultipleChoiceFilter` | `subtree` | `_subtree` | filter has `method=`; generic `__in` comparison can't express it | `subtree`: ERROR FieldError: Cannot resolve keyword 'subtree' into field. Choices are: _custom_field_data, associated_contacts, associated_<br>`subtree__id`: ERROR FieldError: Cannot resolve keyword 'subtree' into field. Choices are: _custom_field_data, associated_contacts, associated_<br>`subtree__name`: ERROR FieldError: Cannot resolve keyword 'subtree' into field. Choices are: _custom_field_data, associated_contacts, associated_ |
| dcim.ControllerManagedDeviceGroupFilterSetTestCase | `tenant` | `NaturalKeyOrPKMultipleChoiceFilter` | `tenant` |  | test data has < 2 distinct values with a non-matching remainder | `tenant`: ERROR ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant. At least 3 unique values are<br>`tenant__id`: ERROR ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant__id. At least 3 unique values<br>`tenant__name`: ERROR ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant__name. At least 3 unique valu |
| dcim.ControllerManagedDeviceGroupFilterSetTestCase | `tenant_group` | `TreeNodeMultipleChoiceFilter` | `tenant__tenant_group` |  | field_name isn't a real model field path (or filter name != field) | `tenant_group`: ERROR FieldError: Cannot resolve keyword 'tenant_group' into field. Choices are: _custom_field_data, associated_contacts, associ<br>`tenant__tenant_group`: ERROR ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant__tenant_group. At least 3 uni<br>`tenant__tenant_group__id`: ERROR ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant__tenant_group__id. At least 3<br>`tenant__tenant_group__name`: ERROR ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant__tenant_group__name. At least |
| dcim.ControllerManagedDeviceGroupFilterSetTestCase | `tenant_id` | `ModelMultipleChoiceFilter` | `tenant_id` |  | test data has < 2 distinct values with a non-matching remainder | `tenant_id`: ERROR ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant_id. At least 3 unique values <br>`tenant_id__id`: ERROR ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant_id__id. At least 3 unique val<br>`tenant_id__name`: ERROR ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant_id__name. At least 3 unique v |
| dcim.ControllerManagedDeviceGroupFilterSetTestCase | `wireless_networks` | `NaturalKeyOrPKMultipleChoiceFilter` | `wireless_networks` |  | passes as plain generic entry | `wireless_networks`: PASS |
| dcim.DeviceBayTestCase | `location` | `NaturalKeyOrPKMultipleChoiceFilter` | `device__location` |  | field_name isn't a real model field path (or filter name != field) | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, ass<br>`device__location`: ERROR ValueError: Cannot find enough valid test data for DeviceBay field device__location. At least 3 unique values are required<br>`device__location__id`: ERROR ValueError: Cannot find enough valid test data for DeviceBay field device__location__id. At least 3 unique values are requ<br>`device__location__name`: ERROR ValueError: Cannot find enough valid test data for DeviceBay field device__location__name. At least 3 unique values are re |
| dcim.DeviceClusterAssignmentTestCase | `created` | `MultiValueDateTimeFilter` | `created` |  | field_name isn't a real model field path (or filter name != field) | `created`: ERROR FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metada |
| dcim.DeviceClusterAssignmentTestCase | `last_updated` | `MultiValueDateTimeFilter` | `last_updated` |  | field_name isn't a real model field path (or filter name != field) | `last_updated`: ERROR FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_m |
| dcim.DeviceRedundancyGroupTestCase | `status` | `StatusFilter` | `status` |  | passes as plain generic entry | `status`: PASS |
| dcim.DeviceTestCase | `controller` | `NaturalKeyOrPKMultipleChoiceFilter` | `controller_managed_device_group__controller` |  | field_name isn't a real model field path (or filter name != field) | `controller`: ERROR FieldError: Cannot resolve keyword 'controller' into field. Choices are: _custom_field_data, _name, asset_tag, associated_<br>`controller_managed_device_group__controller`: ERROR ValueError: Cannot find enough valid test data for Device field controller_managed_device_group__controller. At least 3 un<br>`controller_managed_device_group__controller__id`: ERROR ValueError: Cannot find enough valid test data for Device field controller_managed_device_group__controller__id. At least <br>`controller_managed_device_group__controller__name`: ERROR ValueError: Cannot find enough valid test data for Device field controller_managed_device_group__controller__name. At leas |
| dcim.DeviceTestCase | `face` | `MultipleChoiceFilter` | `face` |  | passes as plain generic entry | `face`: PASS |
| dcim.DeviceTestCase | `has_primary_ip` | `BooleanFilter` | `has_primary_ip` | `_has_primary_ip` | filter has `method=`; generic `__in` comparison can't express it | `has_primary_ip`: ERROR FieldError: Cannot resolve keyword 'has_primary_ip' into field. Choices are: _custom_field_data, _name, asset_tag, associa |
| dcim.DeviceTestCase | `is_full_depth` | `BooleanFilter` | `device_type__is_full_depth` |  | field_name isn't a real model field path (or filter name != field) | `is_full_depth`: ERROR FieldError: Cannot resolve keyword 'is_full_depth' into field. Choices are: _custom_field_data, _name, asset_tag, associat<br>`device_type__is_full_depth`: ERROR ValueError: Cannot find enough valid test data for Device field device_type__is_full_depth. At least 3 unique values are r |
| dcim.DeviceTestCase | `local_config_context_data` | `BooleanFilter` | `local_config_context_data` | `_local_config_context_data` | filter has `method=`; generic `__in` comparison can't express it | `local_config_context_data`: ERROR ValueError: Cannot find enough valid test data for Device field local_config_context_data. At least 3 unique values are re |
| dcim.DeviceTestCase | `local_config_context_schema` | `NaturalKeyOrPKMultipleChoiceFilter` | `local_config_context_schema` |  | test data has < 2 distinct values with a non-matching remainder | `local_config_context_schema`: ERROR ValueError: Cannot find enough valid test data for Device field local_config_context_schema. At least 3 unique values are <br>`local_config_context_schema__id`: ERROR ValueError: Cannot find enough valid test data for Device field local_config_context_schema__id. At least 3 unique values <br>`local_config_context_schema__name`: ERROR ValueError: Cannot find enough valid test data for Device field local_config_context_schema__name. At least 3 unique value |
| dcim.DeviceTestCase | `local_config_context_schema_id` | `ModelMultipleChoiceFilter` | `local_config_context_schema_id` |  | test data has < 2 distinct values with a non-matching remainder | `local_config_context_schema_id`: ERROR ValueError: Cannot find enough valid test data for Device field local_config_context_schema_id. At least 3 unique values a<br>`local_config_context_schema_id__id`: ERROR ValueError: Cannot find enough valid test data for Device field local_config_context_schema_id__id. At least 3 unique valu<br>`local_config_context_schema_id__name`: ERROR ValueError: Cannot find enough valid test data for Device field local_config_context_schema_id__name. At least 3 unique va |
| dcim.DeviceTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `location` |  | test data has < 2 distinct values with a non-matching remainder | `location`: ERROR ValueError: Cannot find enough valid test data for Device field location. At least 3 unique values are required to test mu<br>`location__id`: ERROR ValueError: Cannot find enough valid test data for Device field location__id. At least 3 unique values are required to tes<br>`location__name`: ERROR ValueError: Cannot find enough valid test data for Device field location__name. At least 3 unique values are required to t |
| dcim.DeviceTestCase | `serial` | `MultiValueCharFilter` | `serial` |  | passes as plain generic entry | `serial`: PASS |
| dcim.DeviceTypeTestCase | `console_ports` | `BooleanFilter` | `console_ports` | `_console_ports` | filter has `method=`; generic `__in` comparison can't express it | `console_ports`: ERROR FieldError: Cannot resolve keyword 'console_ports' into field. Choices are: _custom_field_data, associated_contacts, assoc |
| dcim.DeviceTypeTestCase | `console_server_ports` | `BooleanFilter` | `console_server_ports` | `_console_server_ports` | filter has `method=`; generic `__in` comparison can't express it | `console_server_ports`: ERROR FieldError: Cannot resolve keyword 'console_server_ports' into field. Choices are: _custom_field_data, associated_contacts |
| dcim.DeviceTypeTestCase | `device_bays` | `BooleanFilter` | `device_bays` | `_device_bays` | filter has `method=`; generic `__in` comparison can't express it | `device_bays`: ERROR FieldError: Cannot resolve keyword 'device_bays' into field. Choices are: _custom_field_data, associated_contacts, associa |
| dcim.DeviceTypeTestCase | `interfaces` | `BooleanFilter` | `interfaces` | `_interfaces` | filter has `method=`; generic `__in` comparison can't express it | `interfaces`: ERROR FieldError: Cannot resolve keyword 'interfaces' into field. Choices are: _custom_field_data, associated_contacts, associat |
| dcim.DeviceTypeTestCase | `is_full_depth` | `BooleanFilter` | `is_full_depth` |  | test data has < 2 distinct values with a non-matching remainder | `is_full_depth`: ERROR ValueError: Cannot find enough valid test data for DeviceType field is_full_depth. At least 3 unique values are required t |
| dcim.DeviceTypeTestCase | `power_outlets` | `BooleanFilter` | `power_outlets` | `_power_outlets` | filter has `method=`; generic `__in` comparison can't express it | `power_outlets`: ERROR FieldError: Cannot resolve keyword 'power_outlets' into field. Choices are: _custom_field_data, associated_contacts, assoc |
| dcim.DeviceTypeTestCase | `power_ports` | `BooleanFilter` | `power_ports` | `_power_ports` | filter has `method=`; generic `__in` comparison can't express it | `power_ports`: ERROR FieldError: Cannot resolve keyword 'power_ports' into field. Choices are: _custom_field_data, associated_contacts, associa |
| dcim.DeviceTypeTestCase | `subdevice_role` | `MultipleChoiceFilter` | `subdevice_role` |  | passes as plain generic entry | `subdevice_role`: PASS |
| dcim.FrontPortTestCase | `available_for_cable` | `NaturalKeyOrPKMultipleChoiceFilter` | `available_for_cable` | `_filter_available_for_cable` | filter has `method=`; generic `__in` comparison can't express it | `available_for_cable`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co<br>`available_for_cable__id`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co<br>`available_for_cable__name`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co |
| dcim.FrontPortTestCase | `location` | `NaturalKeyOrPKMultipleChoiceFilter` | `device__location` |  | field_name isn't a real model field path (or filter name != field) | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, ass<br>`device__location`: ERROR ValueError: Cannot find enough valid test data for FrontPort field device__location. At least 3 unique values are required<br>`device__location__id`: ERROR ValueError: Cannot find enough valid test data for FrontPort field device__location__id. At least 3 unique values are requ<br>`device__location__name`: ERROR ValueError: Cannot find enough valid test data for FrontPort field device__location__name. At least 3 unique values are re |
| dcim.InterfaceConnectionFilterSetTestCase | `device` | `MultiValueCharFilter` | `device` | `filter_device_name` | filter has `method=`; generic `__in` comparison can't express it | `device`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: associated_data_compliance, associated_object_metadat |
| dcim.InterfaceConnectionFilterSetTestCase | `device_id` | `MultiValueUUIDFilter` | `device_id` | `filter_device_id` | filter has `method=`; generic `__in` comparison can't express it | `device_id`: ERROR FieldError: Cannot resolve keyword 'device_id' into field. Choices are: associated_data_compliance, associated_object_meta |
| dcim.InterfaceConnectionFilterSetTestCase | `location` | `CharFilter` | `location` | `filter_location` | filter has `method=`; generic `__in` comparison can't express it | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: associated_data_compliance, associated_object_metad |
| dcim.InterfaceRedundancyGroupTestCase | `description` | `MultiValueCharFilter` | `description` |  | test data has < 2 distinct values with a non-matching remainder | `description`: ERROR ValueError: Cannot find enough valid test data for InterfaceRedundancyGroup field description. At least 3 unique values ar |
| dcim.InterfaceRedundancyGroupTestCase | `interfaces` | `NaturalKeyOrPKMultipleChoiceFilter` | `interfaces` |  | test data has < 2 distinct values with a non-matching remainder | `interfaces`: ERROR ValueError: Cannot find enough valid test data for InterfaceRedundancyGroup field interfaces. At least 3 unique values are<br>`interfaces__id`: ERROR ValueError: Cannot find enough valid test data for InterfaceRedundancyGroup field interfaces__id. At least 3 unique values<br>`interfaces__name`: ERROR ValueError: Cannot find enough valid test data for InterfaceRedundancyGroup field interfaces__name. At least 3 unique valu |
| dcim.InterfaceRedundancyGroupTestCase | `status` | `StatusFilter` | `status` |  | passes as plain generic entry | `status`: PASS |
| dcim.InterfaceTestCase | `device_id` | `ModelMultipleChoiceFilter` | `device` | `filter_device_id` | passes as plain generic entry | `device_id`: PASS |
| dcim.InterfaceTestCase | `interface_redundancy_groups` | `NaturalKeyOrPKMultipleChoiceFilter` | `interface_redundancy_groups` |  | test data has < 2 distinct values with a non-matching remainder | `interface_redundancy_groups`: ERROR ValueError: Cannot find enough valid test data for Interface field interface_redundancy_groups. At least 3 unique values a<br>`interface_redundancy_groups__id`: ERROR ValueError: Cannot find enough valid test data for Interface field interface_redundancy_groups__id. At least 3 unique valu<br>`interface_redundancy_groups__name`: ERROR ValueError: Cannot find enough valid test data for Interface field interface_redundancy_groups__name. At least 3 unique va |
| dcim.InterfaceTestCase | `location` | `NaturalKeyOrPKMultipleChoiceFilter` | `device__location` |  | field_name isn't a real model field path (or filter name != field) | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, ass<br>`device__location`: ERROR ValueError: Cannot find enough valid test data for Interface field device__location. At least 3 unique values are required<br>`device__location__id`: ERROR ValueError: Cannot find enough valid test data for Interface field device__location__id. At least 3 unique values are requ<br>`device__location__name`: ERROR ValueError: Cannot find enough valid test data for Interface field device__location__name. At least 3 unique values are re |
| dcim.InterfaceVDCAssignmentTestCase | `created` | `MultiValueDateTimeFilter` | `created` |  | field_name isn't a real model field path (or filter name != field) | `created`: ERROR FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metada |
| dcim.InterfaceVDCAssignmentTestCase | `last_updated` | `MultiValueDateTimeFilter` | `last_updated` |  | field_name isn't a real model field path (or filter name != field) | `last_updated`: ERROR FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_m |
| dcim.InventoryItemTestCase | `location` | `NaturalKeyOrPKMultipleChoiceFilter` | `device__location` |  | field_name isn't a real model field path (or filter name != field) | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, asset_tag, associated_co<br>`device__location`: ERROR ValueError: Cannot find enough valid test data for InventoryItem field device__location. At least 3 unique values are requ<br>`device__location__id`: ERROR ValueError: Cannot find enough valid test data for InventoryItem field device__location__id. At least 3 unique values are <br>`device__location__name`: ERROR ValueError: Cannot find enough valid test data for InventoryItem field device__location__name. At least 3 unique values ar |
| dcim.LocationTypeFilterSetTestCase | `nestable` | `BooleanFilter` | `nestable` |  | test data has < 2 distinct values with a non-matching remainder | `nestable`: ERROR ValueError: Cannot find enough valid test data for LocationType field nestable. At least 3 unique values are required to t |
| dcim.ModuleBayTestCase | `module_family` | `NaturalKeyOrPKMultipleChoiceFilter` | `module_family` |  | passes as plain generic entry | `module_family`: PASS |
| dcim.ModuleBayTestCase | `requires_first_party_modules` | `BooleanFilter` | `requires_first_party_modules` |  | test data has < 2 distinct values with a non-matching remainder | `requires_first_party_modules`: ERROR ValueError: Cannot find enough valid test data for ModuleBay field requires_first_party_modules. At least 3 unique values  |
| dcim.ModuleFamilyTestCase | `module_bay_id` | `ModelMultipleChoiceFilter` | `module_bay_id` |  | field_name isn't a real model field path (or filter name != field) | `module_bay_id`: ERROR FieldError: Cannot resolve keyword 'module_bay_id' into field. Choices are: _custom_field_data, associated_contacts, assoc<br>`module_bay_id__id`: ERROR FieldError: Cannot resolve keyword 'module_bay_id' into field. Choices are: _custom_field_data, associated_contacts, assoc<br>`module_bay_id__name`: ERROR FieldError: Cannot resolve keyword 'module_bay_id' into field. Choices are: _custom_field_data, associated_contacts, assoc |
| dcim.ModuleTestCase | `device` | `NaturalKeyOrPKMultipleChoiceFilter` | `device` | `filter_device` | filter has `method=`; generic `__in` comparison can't express it | `device`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _custom_field_data, asset_tag, associated_contacts, a<br>`device__id`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _custom_field_data, asset_tag, associated_contacts, a<br>`device__name`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _custom_field_data, asset_tag, associated_contacts, a |
| dcim.ModuleTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `location` |  | passes as plain generic entry | `location`: PASS |
| dcim.ModuleTestCase | `module_family` | `NaturalKeyOrPKMultipleChoiceFilter` | `module_type__module_family` |  | field_name isn't a real model field path (or filter name != field) | `module_family`: ERROR FieldError: Cannot resolve keyword 'module_family' into field. Choices are: _custom_field_data, asset_tag, associated_cont<br>`module_type__module_family`: PASS |
| dcim.PowerConnectionFilterSetTestCase | `device` | `MultiValueCharFilter` | `device__name` | `filter_device` | filter has `method=`; generic `__in` comparison can't express it | `device`: FAIL AssertionError: 0 == 0 : QuerySet cannot be empty<br>`device__name`: PASS |
| dcim.PowerConnectionFilterSetTestCase | `device_id` | `MultiValueUUIDFilter` | `device_id` | `filter_device` | passes as plain generic entry | `device_id`: PASS |
| dcim.PowerConnectionFilterSetTestCase | `location` | `CharFilter` | `location` | `filter_location` | filter has `method=`; generic `__in` comparison can't express it | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, allocated_draw, associat |
| dcim.PowerConnectionFilterSetTestCase | `name` | `MultiValueCharFilter` | `name` |  | passes as plain generic entry | `name`: PASS |
| dcim.PowerFeedTestCase | `available_for_cable` | `NaturalKeyOrPKMultipleChoiceFilter` | `available_for_cable` | `_filter_available_for_cable` | filter has `method=`; generic `__in` comparison can't express it | `available_for_cable`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, amperage, associated<br>`available_for_cable__id`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, amperage, associated<br>`available_for_cable__name`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, amperage, associated |
| dcim.PowerFeedTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `power_panel__location` |  | field_name isn't a real model field path (or filter name != field) | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, amperage, associated_contacts, <br>`power_panel__location`: ERROR ValueError: Cannot find enough valid test data for PowerFeed field power_panel__location. At least 3 unique values are req<br>`power_panel__location__id`: ERROR ValueError: Cannot find enough valid test data for PowerFeed field power_panel__location__id. At least 3 unique values are<br>`power_panel__location__name`: ERROR ValueError: Cannot find enough valid test data for PowerFeed field power_panel__location__name. At least 3 unique values a |
| dcim.PowerOutletTemplateTestCase | `type` | `MultipleChoiceFilter` | `type` |  | passes as plain generic entry | `type`: PASS |
| dcim.PowerOutletTestCase | `available_for_cable` | `NaturalKeyOrPKMultipleChoiceFilter` | `available_for_cable` | `_filter_available_for_cable` | filter has `method=`; generic `__in` comparison can't express it | `available_for_cable`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co<br>`available_for_cable__id`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co<br>`available_for_cable__name`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co |
| dcim.PowerOutletTestCase | `location` | `NaturalKeyOrPKMultipleChoiceFilter` | `device__location` |  | field_name isn't a real model field path (or filter name != field) | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, ass<br>`device__location`: ERROR ValueError: Cannot find enough valid test data for PowerOutlet field device__location. At least 3 unique values are requir<br>`device__location__id`: ERROR ValueError: Cannot find enough valid test data for PowerOutlet field device__location__id. At least 3 unique values are re<br>`device__location__name`: ERROR ValueError: Cannot find enough valid test data for PowerOutlet field device__location__name. At least 3 unique values are  |
| dcim.PowerOutletTestCase | `type` | `MultipleChoiceFilter` | `type` |  | passes as plain generic entry | `type`: PASS |
| dcim.PowerPanelTestCase | `breaker_position_count` | `MultiValueNumberFilter` | `breaker_position_count` |  | test data has < 2 distinct values with a non-matching remainder | `breaker_position_count`: ERROR ValueError: Cannot find enough valid test data for PowerPanel field breaker_position_count. At least 3 unique values are r |
| dcim.PowerPanelTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `location` |  | test data has < 2 distinct values with a non-matching remainder | `location`: ERROR ValueError: Cannot find enough valid test data for PowerPanel field location. At least 3 unique values are required to tes<br>`location__id`: ERROR ValueError: Cannot find enough valid test data for PowerPanel field location__id. At least 3 unique values are required to<br>`location__name`: ERROR ValueError: Cannot find enough valid test data for PowerPanel field location__name. At least 3 unique values are required  |
| dcim.PowerPanelTestCase | `panel_type` | `MultipleChoiceFilter` | `panel_type` |  | test data has < 2 distinct values with a non-matching remainder | `panel_type`: ERROR ValueError: Cannot find enough valid test data for PowerPanel field panel_type. At least 3 unique values are required to t |
| dcim.PowerPanelTestCase | `power_path` | `MultipleChoiceFilter` | `power_path` |  | test data has < 2 distinct values with a non-matching remainder | `power_path`: ERROR ValueError: Cannot find enough valid test data for PowerPanel field power_path. At least 3 unique values are required to t |
| dcim.PowerPortTemplateTestCase | `type` | `MultipleChoiceFilter` | `type` |  | passes as plain generic entry | `type`: PASS |
| dcim.PowerPortTestCase | `available_for_cable` | `NaturalKeyOrPKMultipleChoiceFilter` | `available_for_cable` | `_filter_available_for_cable` | filter has `method=`; generic `__in` comparison can't express it | `available_for_cable`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, allocated_dra<br>`available_for_cable__id`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, allocated_dra<br>`available_for_cable__name`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, allocated_dra |
| dcim.PowerPortTestCase | `location` | `NaturalKeyOrPKMultipleChoiceFilter` | `device__location` |  | field_name isn't a real model field path (or filter name != field) | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, allocated_draw, associat<br>`device__location`: ERROR ValueError: Cannot find enough valid test data for PowerPort field device__location. At least 3 unique values are required<br>`device__location__id`: ERROR ValueError: Cannot find enough valid test data for PowerPort field device__location__id. At least 3 unique values are requ<br>`device__location__name`: ERROR ValueError: Cannot find enough valid test data for PowerPort field device__location__name. At least 3 unique values are re |
| dcim.PowerPortTestCase | `type` | `MultipleChoiceFilter` | `type` |  | passes as plain generic entry | `type`: PASS |
| dcim.RackGroupTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `location` |  | passes as plain generic entry | `location`: PASS |
| dcim.RackReservationTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `rack__location` |  | field_name isn't a real model field path (or filter name != field) | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, associated_contacts, associated<br>`rack__location`: ERROR ValueError: Cannot find enough valid test data for RackReservation field rack__location. At least 3 unique values are requ<br>`rack__location__id`: ERROR ValueError: Cannot find enough valid test data for RackReservation field rack__location__id. At least 3 unique values are <br>`rack__location__name`: ERROR ValueError: Cannot find enough valid test data for RackReservation field rack__location__name. At least 3 unique values ar |
| dcim.RackTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `location` |  | test data has < 2 distinct values with a non-matching remainder | `location`: ERROR ValueError: Cannot find enough valid test data for Rack field location. At least 3 unique values are required to test mult<br>`location__id`: ERROR ValueError: Cannot find enough valid test data for Rack field location__id. At least 3 unique values are required to test <br>`location__name`: ERROR ValueError: Cannot find enough valid test data for Rack field location__name. At least 3 unique values are required to tes |
| dcim.RearPortTestCase | `available_for_cable` | `NaturalKeyOrPKMultipleChoiceFilter` | `available_for_cable` | `_filter_available_for_cable` | filter has `method=`; generic `__in` comparison can't express it | `available_for_cable`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co<br>`available_for_cable__id`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co<br>`available_for_cable__name`: ERROR FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_co |
| dcim.RearPortTestCase | `location` | `NaturalKeyOrPKMultipleChoiceFilter` | `device__location` |  | field_name isn't a real model field path (or filter name != field) | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, ass<br>`device__location`: ERROR ValueError: Cannot find enough valid test data for RearPort field device__location. At least 3 unique values are required <br>`device__location__id`: ERROR ValueError: Cannot find enough valid test data for RearPort field device__location__id. At least 3 unique values are requi<br>`device__location__name`: ERROR ValueError: Cannot find enough valid test data for RearPort field device__location__name. At least 3 unique values are req |
| dcim.SoftwareImageFileFilterSetTestCase | `download_url` | `MultiValueCharFilter` | `download_url` |  | passes as plain generic entry | `download_url`: PASS |
| dcim.SoftwareVersionFilterSetTestCase | `device_types` | `NaturalKeyOrPKMultipleChoiceFilter` | `software_image_files__device_types` |  | field_name isn't a real model field path (or filter name != field) | `device_types`: ERROR FieldError: Cannot resolve keyword 'device_types' into field. Choices are: _custom_field_data, alias, associated_contacts,<br>`software_image_files__device_types`: PASS |
| dcim.SoftwareVersionFilterSetTestCase | `inventory_items` | `NaturalKeyOrPKMultipleChoiceFilter` | `inventory_items` |  | passes as plain generic entry | `inventory_items`: PASS |
| dcim.SoftwareVersionFilterSetTestCase | `virtual_machines` | `NaturalKeyOrPKMultipleChoiceFilter` | `virtual_machines` |  | passes as plain generic entry | `virtual_machines`: PASS |
| dcim.VirtualChassisTestCase | `tenant` | `NaturalKeyOrPKMultipleChoiceFilter` | `master__tenant` |  | field_name isn't a real model field path (or filter name != field) | `tenant`: ERROR FieldError: Cannot resolve keyword 'tenant' into field. Choices are: _custom_field_data, associated_contacts, associated_d<br>`master__tenant`: ERROR ValueError: Cannot find enough valid test data for VirtualChassis field master__tenant. At least 3 unique values are requi<br>`master__tenant__id`: ERROR ValueError: Cannot find enough valid test data for VirtualChassis field master__tenant__id. At least 3 unique values are r<br>`master__tenant__name`: ERROR ValueError: Cannot find enough valid test data for VirtualChassis field master__tenant__name. At least 3 unique values are |
| dcim.VirtualChassisTestCase | `tenant_group` | `TreeNodeMultipleChoiceFilter` | `master__tenant__tenant_group` |  | field_name isn't a real model field path (or filter name != field) | `tenant_group`: ERROR FieldError: Cannot resolve keyword 'tenant_group' into field. Choices are: _custom_field_data, associated_contacts, associ<br>`master__tenant__tenant_group`: ERROR ValueError: Cannot find enough valid test data for VirtualChassis field master__tenant__tenant_group. At least 3 unique va<br>`master__tenant__tenant_group__id`: ERROR ValueError: Cannot find enough valid test data for VirtualChassis field master__tenant__tenant_group__id. At least 3 uniqu<br>`master__tenant__tenant_group__name`: ERROR ValueError: Cannot find enough valid test data for VirtualChassis field master__tenant__tenant_group__name. At least 3 uni |
| dcim.VirtualDeviceContextTestCase | `identifier` | `MultiValueNumberFilter` | `identifier` |  | passes as plain generic entry | `identifier`: PASS |
| extras.DynamicGroupFilterTest | `ancestors` | `NaturalKeyOrPKMultipleChoiceFilter` | `ancestors` | `filter_ancestors` | filter has `method=`; generic `__in` comparison can't express it | `ancestors`: ERROR FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associate<br>`ancestors__id`: ERROR FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associate<br>`ancestors__name`: ERROR FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associate |
| extras.DynamicGroupFilterTest | `descendants` | `NaturalKeyOrPKMultipleChoiceFilter` | `descendants` | `filter_descendants` | filter has `method=`; generic `__in` comparison can't express it | `descendants`: ERROR FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associa<br>`descendants__id`: ERROR FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associa<br>`descendants__name`: ERROR FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associa |
| extras.DynamicGroupFilterTest | `member_id` | `MultiValueUUIDFilter` | `static_group_associations__associated_object_id` |  | field_name isn't a real model field path (or filter name != field) | `member_id`: ERROR FieldError: Cannot resolve keyword 'member_id' into field. Choices are: _custom_field_data, associated_contacts, associate<br>`static_group_associations__associated_object_id`: PASS |
| extras.DynamicGroupMembershipFilterTest | `created` | `MultiValueDateTimeFilter` | `created` |  | field_name isn't a real model field path (or filter name != field) | `created`: ERROR FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metada |
| extras.DynamicGroupMembershipFilterTest | `last_updated` | `MultiValueDateTimeFilter` | `last_updated` |  | field_name isn't a real model field path (or filter name != field) | `last_updated`: ERROR FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_m |
| extras.ApprovalWorkflowDefinitionFilterTestCase | `model_constraints` | `MultiValueCharFilter` | `model_constraints` |  | test data has < 2 distinct values with a non-matching remainder | `model_constraints`: ERROR ValueError: Cannot find enough valid test data for ApprovalWorkflowDefinition field model_constraints. At least 3 unique v |
| extras.ApprovalWorkflowDefinitionFilterTestCase | `weight` | `MultiValueNumberFilter` | `weight` |  | passes as plain generic entry | `weight`: PASS |
| extras.ApprovalWorkflowFilterTestCase | `decision_date` | `MultiValueDateTimeFilter` | `decision_date` |  | test data has < 2 distinct values with a non-matching remainder | `decision_date`: ERROR ValueError: Cannot find enough valid test data for ApprovalWorkflow field decision_date. At least 3 unique values are requ |
| extras.ApprovalWorkflowFilterTestCase | `user` | `ModelMultipleChoiceFilter` | `user` |  | test data has < 2 distinct values with a non-matching remainder | `user`: ERROR ValueError: Cannot find enough valid test data for ApprovalWorkflow field user. At least 3 unique values are required to t<br>`user__id`: ERROR ValueError: Cannot find enough valid test data for ApprovalWorkflow field user__id. At least 3 unique values are required <br>`user__name`: ERROR FieldError: Cannot resolve keyword 'name' into field. Choices are: approval_workflow_stage_responses, approval_workflows,  |
| extras.ApprovalWorkflowFilterTestCase | `user_name` | `MultiValueCharFilter` | `user_name` |  | test data has < 2 distinct values with a non-matching remainder | `user_name`: ERROR ValueError: Cannot find enough valid test data for ApprovalWorkflow field user_name. At least 3 unique values are required |
| extras.ApprovalWorkflowStageDefinitionFilterTestCase | `approval_workflow` | `NaturalKeyOrPKMultipleChoiceFilter` | `approval_workflow` | `_approval_workflow` | filter has `method=`; generic `__in` comparison can't express it | `approval_workflow`: ERROR FieldError: Cannot resolve keyword 'approval_workflow' into field. Choices are: _custom_field_data, approval_workflow_defi<br>`approval_workflow__id`: ERROR FieldError: Cannot resolve keyword 'approval_workflow' into field. Choices are: _custom_field_data, approval_workflow_defi<br>`approval_workflow__name`: ERROR FieldError: Cannot resolve keyword 'approval_workflow' into field. Choices are: _custom_field_data, approval_workflow_defi |
| extras.ApprovalWorkflowStageFilterTestCase | `decision_date_day` | `DateFilter` | `decision_date` |  | field_name isn't a real model field path (or filter name != field) | `decision_date_day`: ERROR FieldError: Cannot resolve keyword 'decision_date_day' into field. Choices are: _custom_field_data, approval_workflow, app<br>`decision_date`: ERROR AttributeError: 'list' object has no attribute 'strip' |
| extras.ComputedFieldTestCase | `grouping` | `MultiValueCharFilter` | `grouping` |  | test data has < 2 distinct values with a non-matching remainder | `grouping`: ERROR ValueError: Cannot find enough valid test data for ComputedField field grouping. At least 3 unique values are required to  |
| extras.ConfigContextTestCase | `device_redundancy_group` | `NaturalKeyOrPKMultipleChoiceFilter` | `device_redundancy_groups` |  | field_name isn't a real model field path (or filter name != field) | `device_redundancy_group`: ERROR FieldError: Cannot resolve keyword 'device_redundancy_group' into field. Choices are: associated_contacts, associated_data<br>`device_redundancy_groups`: ERROR ValueError: Cannot find enough valid test data for ConfigContext field device_redundancy_groups. At least 3 unique values <br>`device_redundancy_groups__id`: ERROR ValueError: Cannot find enough valid test data for ConfigContext field device_redundancy_groups__id. At least 3 unique val<br>`device_redundancy_groups__name`: ERROR ValueError: Cannot find enough valid test data for ConfigContext field device_redundancy_groups__name. At least 3 unique v |
| extras.ConfigContextTestCase | `owner_content_type` | `ContentTypeFilter` | `owner_content_type` |  | test data has < 2 distinct values with a non-matching remainder | `owner_content_type`: ERROR ValueError: Cannot find enough valid test data for ConfigContext field owner_content_type. At least 3 unique values are re |
| extras.ConfigContextTestCase | `owner_object_id` | `MultiValueUUIDFilter` | `owner_object_id` |  | test data has < 2 distinct values with a non-matching remainder | `owner_object_id`: ERROR ValueError: Cannot find enough valid test data for ConfigContext field owner_object_id. At least 3 unique values are requi |
| extras.ConfigContextTestCase | `schema` | `NaturalKeyOrPKMultipleChoiceFilter` | `config_context_schema` |  | field_name isn't a real model field path (or filter name != field) | `schema`: ERROR FieldError: Cannot resolve keyword 'schema' into field. Choices are: associated_contacts, associated_data_compliance, asso<br>`config_context_schema`: ERROR ValueError: Cannot find enough valid test data for ConfigContext field config_context_schema. At least 3 unique values are<br>`config_context_schema__id`: ERROR ValueError: Cannot find enough valid test data for ConfigContext field config_context_schema__id. At least 3 unique values<br>`config_context_schema__name`: ERROR ValueError: Cannot find enough valid test data for ConfigContext field config_context_schema__name. At least 3 unique valu |
| extras.ConfigContextTestCase | `tag` | `NaturalKeyOrPKMultipleChoiceFilter` | `tags` |  | field_name isn't a real model field path (or filter name != field) | `tag`: ERROR FieldError: Cannot resolve keyword 'tag' into field. Choices are: associated_contacts, associated_data_compliance, associa<br>`tags`: ERROR ValueError: Cannot find enough valid test data for ConfigContext field tags. At least 3 unique values are required to test<br>`tags__id`: ERROR ValueError: Cannot find enough valid test data for ConfigContext field tags__id. At least 3 unique values are required to <br>`tags__name`: ERROR ValueError: Cannot find enough valid test data for ConfigContext field tags__name. At least 3 unique values are required t |
| extras.ContactAssociationFilterSetTestCase | `associated_object_id` | `MultiValueUUIDFilter` | `associated_object_id` |  | passes as plain generic entry | `associated_object_id`: PASS |
| extras.ContentTypeFilterSetTestCase | `feature` | `CharFilter` | `feature` | `_feature` | filter has `method=`; generic `__in` comparison can't express it | `feature`: ERROR FieldError: Cannot resolve keyword 'feature' into field. Choices are: app_label, cloud_resource_types, computed_fields, co |
| extras.ContentTypeFilterSetTestCase | `has_serializer` | `BooleanFilter` | `has_serializer` | `_has_serializer` | filter has `method=`; generic `__in` comparison can't express it | `has_serializer`: ERROR FieldError: Cannot resolve keyword 'has_serializer' into field. Choices are: app_label, cloud_resource_types, computed_fie |
| extras.CustomLinkTestCase | `button_class` | `MultipleChoiceFilter` | `button_class` |  | test data has < 2 distinct values with a non-matching remainder | `button_class`: ERROR ValueError: Cannot find enough valid test data for CustomLink field button_class. At least 3 unique values are required to |
| extras.CustomLinkTestCase | `content_type` | `ContentTypeFilter` | `content_type` |  | test data has < 2 distinct values with a non-matching remainder | `content_type`: ERROR ValueError: Cannot find enough valid test data for CustomLink field content_type. At least 3 unique values are required to |
| extras.CustomLinkTestCase | `group_name` | `MultiValueCharFilter` | `group_name` |  | test data has < 2 distinct values with a non-matching remainder | `group_name`: ERROR ValueError: Cannot find enough valid test data for CustomLink field group_name. At least 3 unique values are required to t |
| extras.CustomLinkTestCase | `new_window` | `BooleanFilter` | `new_window` |  | test data has < 2 distinct values with a non-matching remainder | `new_window`: ERROR ValueError: Cannot find enough valid test data for CustomLink field new_window. At least 3 unique values are required to t |
| extras.DynamicGroupFilterSetTestCase | `ancestors` | `NaturalKeyOrPKMultipleChoiceFilter` | `ancestors` | `filter_ancestors` | filter has `method=`; generic `__in` comparison can't express it | `ancestors`: ERROR FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associate<br>`ancestors__id`: ERROR FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associate<br>`ancestors__name`: ERROR FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associate |
| extras.DynamicGroupFilterSetTestCase | `content_type` | `ContentTypeMultipleChoiceFilter` | `content_type` |  | filterset rejects the raw values (form validation) | `content_type`: FAIL AssertionError: False is not true : * content_type |
| extras.DynamicGroupFilterSetTestCase | `descendants` | `NaturalKeyOrPKMultipleChoiceFilter` | `descendants` | `filter_descendants` | filter has `method=`; generic `__in` comparison can't express it | `descendants`: ERROR FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associa<br>`descendants__id`: ERROR FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associa<br>`descendants__name`: ERROR FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associa |
| extras.DynamicGroupFilterSetTestCase | `member_id` | `MultiValueUUIDFilter` | `static_group_associations__associated_object_id` |  | field_name isn't a real model field path (or filter name != field) | `member_id`: ERROR FieldError: Cannot resolve keyword 'member_id' into field. Choices are: _custom_field_data, associated_contacts, associate<br>`static_group_associations__associated_object_id`: PASS |
| extras.ExportTemplateTestCase | `owner_content_type` | `ContentTypeFilter` | `owner_content_type` |  | test data has < 2 distinct values with a non-matching remainder | `owner_content_type`: ERROR ValueError: Cannot find enough valid test data for ExportTemplate field owner_content_type. At least 3 unique values are r |
| extras.ExportTemplateTestCase | `owner_object_id` | `MultiValueUUIDFilter` | `owner_object_id` |  | test data has < 2 distinct values with a non-matching remainder | `owner_object_id`: ERROR ValueError: Cannot find enough valid test data for ExportTemplate field owner_object_id. At least 3 unique values are requ |
| extras.ExternalIntegrationTestCase | `ca_file_path` | `MultiValueCharFilter` | `ca_file_path` |  | passes as plain generic entry | `ca_file_path`: PASS |
| extras.ExternalIntegrationTestCase | `extra_config` | `MultiValueCharFilter` | `extra_config` |  | filterset result differs from `queryset.filter(field__in=...)` | `extra_config`: FAIL AssertionError: 0 == 0 : QuerySet cannot be empty |
| extras.ExternalIntegrationTestCase | `headers` | `MultiValueCharFilter` | `headers` |  | filterset result differs from `queryset.filter(field__in=...)` | `headers`: FAIL AssertionError: 0 == 0 : QuerySet cannot be empty |
| extras.ImageAttachmentTestCase | `content_type_id` | `ModelMultipleChoiceFilter` | `content_type_id` |  | test data has < 2 distinct values with a non-matching remainder | `content_type_id`: ERROR ValueError: Cannot find enough valid test data for ImageAttachment field content_type_id. At least 3 unique values are req<br>`content_type_id__id`: ERROR ValueError: Cannot find enough valid test data for ImageAttachment field content_type_id__id. At least 3 unique values are<br>`content_type_id__name`: ERROR FieldError: Cannot resolve keyword 'name' into field. Choices are: app_label, cloud_resource_types, computed_fields, confi |
| extras.ImageAttachmentTestCase | `object_id` | `MultiValueUUIDFilter` | `object_id` |  | passes as plain generic entry | `object_id`: PASS |
| extras.JobButtonFilterTestCase | `button_class` | `MultipleChoiceFilter` | `button_class` |  | test data has < 2 distinct values with a non-matching remainder | `button_class`: ERROR ValueError: Cannot find enough valid test data for JobButton field button_class. At least 3 unique values are required to  |
| extras.JobButtonFilterTestCase | `confirmation` | `BooleanFilter` | `confirmation` |  | test data has < 2 distinct values with a non-matching remainder | `confirmation`: ERROR ValueError: Cannot find enough valid test data for JobButton field confirmation. At least 3 unique values are required to  |
| extras.JobButtonFilterTestCase | `content_types` | `ContentTypeFilter` | `content_types` |  | test data has < 2 distinct values with a non-matching remainder | `content_types`: ERROR ValueError: Cannot find enough valid test data for JobButton field content_types. At least 3 unique values are required to |
| extras.JobButtonFilterTestCase | `enabled` | `BooleanFilter` | `enabled` |  | test data has < 2 distinct values with a non-matching remainder | `enabled`: ERROR ValueError: Cannot find enough valid test data for JobButton field enabled. At least 3 unique values are required to test  |
| extras.JobButtonFilterTestCase | `group_name` | `MultiValueCharFilter` | `group_name` |  | test data has < 2 distinct values with a non-matching remainder | `group_name`: ERROR ValueError: Cannot find enough valid test data for JobButton field group_name. At least 3 unique values are required to te |
| extras.JobFilterSetTestCase | `console_log_default` | `BooleanFilter` | `console_log_default` |  | test data has < 2 distinct values with a non-matching remainder | `console_log_default`: ERROR ValueError: Cannot find enough valid test data for Job field console_log_default. At least 3 unique values are required to |
| extras.JobFilterSetTestCase | `console_log_default_override` | `BooleanFilter` | `console_log_default_override` |  | test data has < 2 distinct values with a non-matching remainder | `console_log_default_override`: ERROR ValueError: Cannot find enough valid test data for Job field console_log_default_override. At least 3 unique values are re |
| extras.JobFilterSetTestCase | `description_override` | `BooleanFilter` | `description_override` |  | test data has < 2 distinct values with a non-matching remainder | `description_override`: ERROR ValueError: Cannot find enough valid test data for Job field description_override. At least 3 unique values are required t |
| extras.JobFilterSetTestCase | `dryrun_default_override` | `BooleanFilter` | `dryrun_default_override` |  | test data has < 2 distinct values with a non-matching remainder | `dryrun_default_override`: ERROR ValueError: Cannot find enough valid test data for Job field dryrun_default_override. At least 3 unique values are require |
| extras.JobFilterSetTestCase | `grouping_override` | `BooleanFilter` | `grouping_override` |  | test data has < 2 distinct values with a non-matching remainder | `grouping_override`: ERROR ValueError: Cannot find enough valid test data for Job field grouping_override. At least 3 unique values are required to t |
| extras.JobFilterSetTestCase | `has_sensitive_variables` | `BooleanFilter` | `has_sensitive_variables` |  | test data has < 2 distinct values with a non-matching remainder | `has_sensitive_variables`: ERROR ValueError: Cannot find enough valid test data for Job field has_sensitive_variables. At least 3 unique values are require |
| extras.JobFilterSetTestCase | `has_sensitive_variables_override` | `BooleanFilter` | `has_sensitive_variables_override` |  | test data has < 2 distinct values with a non-matching remainder | `has_sensitive_variables_override`: ERROR ValueError: Cannot find enough valid test data for Job field has_sensitive_variables_override. At least 3 unique values ar |
| extras.JobFilterSetTestCase | `hidden_override` | `BooleanFilter` | `hidden_override` |  | test data has < 2 distinct values with a non-matching remainder | `hidden_override`: ERROR ValueError: Cannot find enough valid test data for Job field hidden_override. At least 3 unique values are required to tes |
| extras.JobFilterSetTestCase | `is_job_button_receiver` | `BooleanFilter` | `is_job_button_receiver` |  | test data has < 2 distinct values with a non-matching remainder | `is_job_button_receiver`: ERROR ValueError: Cannot find enough valid test data for Job field is_job_button_receiver. At least 3 unique values are required |
| extras.JobFilterSetTestCase | `is_singleton` | `BooleanFilter` | `is_singleton` |  | test data has < 2 distinct values with a non-matching remainder | `is_singleton`: ERROR ValueError: Cannot find enough valid test data for Job field is_singleton. At least 3 unique values are required to test m |
| extras.JobFilterSetTestCase | `is_singleton_override` | `BooleanFilter` | `is_singleton_override` |  | test data has < 2 distinct values with a non-matching remainder | `is_singleton_override`: ERROR ValueError: Cannot find enough valid test data for Job field is_singleton_override. At least 3 unique values are required  |
| extras.JobFilterSetTestCase | `name_override` | `BooleanFilter` | `name_override` |  | test data has < 2 distinct values with a non-matching remainder | `name_override`: ERROR ValueError: Cannot find enough valid test data for Job field name_override. At least 3 unique values are required to test  |
| extras.JobFilterSetTestCase | `soft_time_limit` | `MultiValueFloatFilter` | `soft_time_limit` |  | passes as plain generic entry | `soft_time_limit`: PASS |
| extras.JobFilterSetTestCase | `soft_time_limit_override` | `BooleanFilter` | `soft_time_limit_override` |  | test data has < 2 distinct values with a non-matching remainder | `soft_time_limit_override`: ERROR ValueError: Cannot find enough valid test data for Job field soft_time_limit_override. At least 3 unique values are requir |
| extras.JobFilterSetTestCase | `time_limit` | `MultiValueFloatFilter` | `time_limit` |  | passes as plain generic entry | `time_limit`: PASS |
| extras.JobFilterSetTestCase | `time_limit_override` | `BooleanFilter` | `time_limit_override` |  | test data has < 2 distinct values with a non-matching remainder | `time_limit_override`: ERROR ValueError: Cannot find enough valid test data for Job field time_limit_override. At least 3 unique values are required to |
| extras.JobLogEntryTestCase | `absolute_url` | `MultiValueCharFilter` | `absolute_url` |  | passes as plain generic entry | `absolute_url`: PASS |
| extras.JobLogEntryTestCase | `job_result` | `ModelMultipleChoiceFilter` | `job_result` |  | passes as plain generic entry | `job_result`: PASS |
| extras.JobLogEntryTestCase | `log_object` | `MultiValueCharFilter` | `log_object` |  | passes as plain generic entry | `log_object`: PASS |
| extras.JobQueueFilterSetTestCase | `description` | `MultiValueCharFilter` | `description` |  | passes as plain generic entry | `description`: PASS |
| extras.JobQueueFilterSetTestCase | `jobs` | `NaturalKeyOrPKMultipleChoiceFilter` | `jobs` |  | passes as plain generic entry | `jobs`: PASS |
| extras.JobResultFilterSetTestCase | `canceled_by` | `ModelMultipleChoiceFilter` | `canceled_by` |  | test data has < 2 distinct values with a non-matching remainder | `canceled_by`: ERROR ValueError: Cannot find enough valid test data for JobResult field canceled_by. At least 3 unique values are required to t<br>`canceled_by__id`: ERROR ValueError: Cannot find enough valid test data for JobResult field canceled_by__id. At least 3 unique values are required <br>`canceled_by__name`: ERROR FieldError: Cannot resolve keyword 'name' into field. Choices are: approval_workflow_stage_responses, approval_workflows,  |
| extras.JobResultFilterSetTestCase | `date_canceled` | `MultiValueDateTimeFilter` | `date_canceled` |  | test data has < 2 distinct values with a non-matching remainder | `date_canceled`: ERROR ValueError: Cannot find enough valid test data for JobResult field date_canceled. At least 3 unique values are required to |
| extras.JobResultFilterSetTestCase | `user` | `ModelMultipleChoiceFilter` | `user` |  | passes as plain generic entry | `user`: PASS |
| extras.ObjectChangeTestCase | `action` | `MultipleChoiceFilter` | `action` |  | passes as plain generic entry | `action`: PASS |
| extras.ObjectChangeTestCase | `change_context` | `MultipleChoiceFilter` | `change_context` |  | passes as plain generic entry | `change_context`: PASS |
| extras.ObjectChangeTestCase | `change_context_detail` | `MultiValueCharFilter` | `change_context_detail` |  | passes as plain generic entry | `change_context_detail`: PASS |
| extras.ObjectChangeTestCase | `changed_object_id` | `MultiValueUUIDFilter` | `changed_object_id` |  | passes as plain generic entry | `changed_object_id`: PASS |
| extras.ObjectChangeTestCase | `object_repr` | `MultiValueCharFilter` | `object_repr` |  | passes as plain generic entry | `object_repr`: PASS |
| extras.ObjectChangeTestCase | `request_id` | `MultiValueUUIDFilter` | `request_id` |  | passes as plain generic entry | `request_id`: PASS |
| extras.ObjectChangeTestCase | `time` | `MultiValueDateTimeFilter` | `time` |  | passes as plain generic entry | `time`: PASS |
| extras.ObjectMetadataTestCase | `assigned_object_id` | `MultiValueUUIDFilter` | `assigned_object_id` |  | passes as plain generic entry | `assigned_object_id`: PASS |
| extras.ObjectMetadataTestCase | `scoped_fields` | `MultiValueCharFilter` | `scoped_fields` |  | ValueError | `scoped_fields`: ERROR ValueError: value ['speed', 'module', 'associated_object_metadata', 'breakout_position', 'bridge', 'type', 'cable_paths',  |
| extras.ObjectMetadataTestCase | `value` | `Filter` | `_value` | `filter_value` | filter has `method=`; generic `__in` comparison can't express it | `value`: ERROR FieldError: Cannot resolve keyword 'value' into field. Choices are: _value, assigned_object, assigned_object_id, assigned_<br>`_value`: ERROR AttributeError: 'list' object has no attribute 'strip' |
| extras.SecretsGroupTestCase | `secrets` | `NaturalKeyOrPKMultipleChoiceFilter` | `secrets` |  | test data has < 2 distinct values with a non-matching remainder | `secrets`: ERROR ValueError: Cannot find enough valid test data for SecretsGroup field secrets. At least 3 unique values are required to te<br>`secrets__id`: ERROR ValueError: Cannot find enough valid test data for SecretsGroup field secrets__id. At least 3 unique values are required t<br>`secrets__name`: ERROR ValueError: Cannot find enough valid test data for SecretsGroup field secrets__name. At least 3 unique values are required |
| extras.WebhookTestCase | `content_types` | `ContentTypeMultipleChoiceFilter` | `content_types` |  | test data has < 2 distinct values with a non-matching remainder | `content_types`: ERROR ValueError: Cannot find enough valid test data for Webhook field content_types. At least 3 unique values are required to t |
| extras.WebhookTestCase | `type_create` | `BooleanFilter` | `type_create` |  | test data has < 2 distinct values with a non-matching remainder | `type_create`: ERROR ValueError: Cannot find enough valid test data for Webhook field type_create. At least 3 unique values are required to tes |
| extras.WebhookTestCase | `type_delete` | `BooleanFilter` | `type_delete` |  | test data has < 2 distinct values with a non-matching remainder | `type_delete`: ERROR ValueError: Cannot find enough valid test data for Webhook field type_delete. At least 3 unique values are required to tes |
| extras.WebhookTestCase | `type_update` | `BooleanFilter` | `type_update` |  | test data has < 2 distinct values with a non-matching remainder | `type_update`: ERROR ValueError: Cannot find enough valid test data for Webhook field type_update. At least 3 unique values are required to tes |
| ipam.IPAddressTestCase | `address` | `MultiValueCharFilter` | `address` | `filter_address` | filter has `method=`; generic `__in` comparison can't express it | `address`: ERROR FieldError: Cannot resolve keyword 'address' into field. Choices are: _custom_field_data, associated_contacts, associated_ |
| ipam.IPAddressTestCase | `description` | `MultiValueCharFilter` | `description` |  | passes as plain generic entry | `description`: PASS |
| ipam.IPAddressTestCase | `device_id` | `MultiValueUUIDFilter` | `pk` | `filter_device` | filter has `method=`; generic `__in` comparison can't express it | `device_id`: ERROR FieldError: Cannot resolve keyword 'device_id' into field. Choices are: _custom_field_data, associated_contacts, associate<br>`pk`: FAIL AssertionError: 0 == 0 : QuerySet cannot be empty |
| ipam.IPAddressTestCase | `namespace` | `NaturalKeyOrPKMultipleChoiceFilter` | `parent__namespace` |  | field_name isn't a real model field path (or filter name != field) | `namespace`: ERROR FieldError: Cannot resolve keyword 'namespace' into field. Choices are: _custom_field_data, associated_contacts, associate<br>`parent__namespace`: PASS |
| ipam.IPAddressTestCase | `present_in_vrf_id` | `ModelChoiceFilter` | `parent__vrfs` | `filter_present_in_vrf` | filter has `method=`; generic `__in` comparison can't express it | `present_in_vrf_id`: ERROR FieldError: Cannot resolve keyword 'present_in_vrf_id' into field. Choices are: _custom_field_data, associated_contacts, a<br>`parent__vrfs`: FAIL AssertionError: False is not true : * present_in_vrf_id<br>`parent__vrfs__id`: FAIL AssertionError: False is not true : * present_in_vrf_id<br>`parent__vrfs__name`: FAIL AssertionError: False is not true : * present_in_vrf_id |
| ipam.IPAddressTestCase | `type` | `MultipleChoiceFilter` | `type` |  | test data has < 2 distinct values with a non-matching remainder | `type`: ERROR ValueError: Cannot find enough valid test data for IPAddress field type. At least 3 unique values are required to test mul |
| ipam.IPAddressTestCase | `virtual_machine_id` | `MultiValueUUIDFilter` | `pk` | `filter_virtual_machine` | filter has `method=`; generic `__in` comparison can't express it | `virtual_machine_id`: ERROR FieldError: Cannot resolve keyword 'virtual_machine_id' into field. Choices are: _custom_field_data, associated_contacts, <br>`pk`: FAIL AssertionError: 0 == 0 : QuerySet cannot be empty |
| ipam.IPAddressToInterfaceTestCase | `created` | `MultiValueDateTimeFilter` | `created` |  | field_name isn't a real model field path (or filter name != field) | `created`: ERROR FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metada |
| ipam.IPAddressToInterfaceTestCase | `is_default` | `BooleanFilter` | `is_default` |  | test data has < 2 distinct values with a non-matching remainder | `is_default`: ERROR ValueError: Cannot find enough valid test data for IPAddressToInterface field is_default. At least 3 unique values are req |
| ipam.IPAddressToInterfaceTestCase | `is_destination` | `BooleanFilter` | `is_destination` |  | test data has < 2 distinct values with a non-matching remainder | `is_destination`: ERROR ValueError: Cannot find enough valid test data for IPAddressToInterface field is_destination. At least 3 unique values are |
| ipam.IPAddressToInterfaceTestCase | `is_preferred` | `BooleanFilter` | `is_preferred` |  | test data has < 2 distinct values with a non-matching remainder | `is_preferred`: ERROR ValueError: Cannot find enough valid test data for IPAddressToInterface field is_preferred. At least 3 unique values are r |
| ipam.IPAddressToInterfaceTestCase | `is_primary` | `BooleanFilter` | `is_primary` |  | test data has < 2 distinct values with a non-matching remainder | `is_primary`: ERROR ValueError: Cannot find enough valid test data for IPAddressToInterface field is_primary. At least 3 unique values are req |
| ipam.IPAddressToInterfaceTestCase | `is_secondary` | `BooleanFilter` | `is_secondary` |  | test data has < 2 distinct values with a non-matching remainder | `is_secondary`: ERROR ValueError: Cannot find enough valid test data for IPAddressToInterface field is_secondary. At least 3 unique values are r |
| ipam.IPAddressToInterfaceTestCase | `is_source` | `BooleanFilter` | `is_source` |  | test data has < 2 distinct values with a non-matching remainder | `is_source`: ERROR ValueError: Cannot find enough valid test data for IPAddressToInterface field is_source. At least 3 unique values are requ |
| ipam.IPAddressToInterfaceTestCase | `is_standby` | `BooleanFilter` | `is_standby` |  | test data has < 2 distinct values with a non-matching remainder | `is_standby`: ERROR ValueError: Cannot find enough valid test data for IPAddressToInterface field is_standby. At least 3 unique values are req |
| ipam.IPAddressToInterfaceTestCase | `last_updated` | `MultiValueDateTimeFilter` | `last_updated` |  | field_name isn't a real model field path (or filter name != field) | `last_updated`: ERROR FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_m |
| ipam.NamespaceTestCase | `description` | `MultiValueCharFilter` | `description` |  | passes as plain generic entry | `description`: PASS |
| ipam.NamespaceTestCase | `location` | `ModelMultipleChoiceFilter` | `location` |  | test data has < 2 distinct values with a non-matching remainder | `location`: ERROR ValueError: Cannot find enough valid test data for Namespace field location. At least 3 unique values are required to test<br>`location__id`: ERROR ValueError: Cannot find enough valid test data for Namespace field location__id. At least 3 unique values are required to <br>`location__name`: ERROR ValueError: Cannot find enough valid test data for Namespace field location__name. At least 3 unique values are required t |
| ipam.PrefixLocationAssignmentTestCase | `created` | `MultiValueDateTimeFilter` | `created` |  | field_name isn't a real model field path (or filter name != field) | `created`: ERROR FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metada |
| ipam.PrefixLocationAssignmentTestCase | `last_updated` | `MultiValueDateTimeFilter` | `last_updated` |  | field_name isn't a real model field path (or filter name != field) | `last_updated`: ERROR FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_m |
| ipam.PrefixLocationAssignmentTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `location` |  | filterset result differs from `queryset.filter(field__in=...)` | `location`: FAIL AssertionError: Count[39 chars]/16: Building-16>: 1, <PrefixLocationAssignmen[21955 chars]: 1}) != Count[39 chars]/16: Campus-<br>`location__id`: PASS |
| ipam.PrefixTestCase | `contains` | `MultiValueCharFilter` | `contains` | `search_contains` | filter has `method=`; generic `__in` comparison can't express it | `contains`: ERROR FieldError: Cannot resolve keyword 'contains' into field. Choices are: _custom_field_data, associated_contacts, associated |
| ipam.PrefixTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `locations` |  | field_name isn't a real model field path (or filter name != field) | `location`: ERROR FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, associated_contacts, associated<br>`locations`: FAIL AssertionError: Count[251 chars]fix: 10.44.0.0/16>: 1, <Prefix: 2001:db8:0:9::[2631 chars]: 1}) != Count[251 chars]fix: 2001:d<br>`locations__id`: PASS |
| ipam.PrefixTestCase | `locations` | `TreeNodeMultipleChoiceFilter` | `locations` |  | passes as plain generic entry | `locations`: PASS |
| ipam.PrefixTestCase | `namespace` | `NaturalKeyOrPKMultipleChoiceFilter` | `namespace` |  | passes as plain generic entry | `namespace`: PASS |
| ipam.PrefixTestCase | `parent` | `PrefixFilter` | `parent` |  | passes as plain generic entry | `parent`: PASS |
| ipam.PrefixTestCase | `present_in_vrf` | `ModelChoiceFilter` | `vrfs__rd` | `filter_present_in_vrf` | filter has `method=`; generic `__in` comparison can't express it | `present_in_vrf`: ERROR FieldError: Cannot resolve keyword 'present_in_vrf' into field. Choices are: _custom_field_data, associated_contacts, asso<br>`vrfs__rd`: FAIL AssertionError: False is not true : * present_in_vrf<br>`vrfs__rd__id`: ERROR FieldError: Cannot resolve keyword 'id' into field. Join on 'rd' not permitted.<br>`vrfs__rd__name`: ERROR FieldError: Cannot resolve keyword 'name' into field. Join on 'rd' not permitted. |
| ipam.PrefixTestCase | `present_in_vrf_id` | `ModelChoiceFilter` | `vrfs` | `filter_present_in_vrf` | filter has `method=`; generic `__in` comparison can't express it | `present_in_vrf_id`: ERROR FieldError: Cannot resolve keyword 'present_in_vrf_id' into field. Choices are: _custom_field_data, associated_contacts, a<br>`vrfs`: FAIL AssertionError: False is not true : * present_in_vrf_id<br>`vrfs__id`: FAIL AssertionError: False is not true : * present_in_vrf_id<br>`vrfs__name`: FAIL AssertionError: False is not true : * present_in_vrf_id |
| ipam.PrefixTestCase | `vlan_id` | `ModelMultipleChoiceFilter` | `vlan_id` |  | passes as plain generic entry | `vlan_id`: PASS |
| ipam.PrefixTestCase | `vlan_vid` | `MultiValueNumberFilter` | `vlan__vid` |  | field_name isn't a real model field path (or filter name != field) | `vlan_vid`: ERROR FieldError: Cannot resolve keyword 'vlan_vid' into field. Choices are: _custom_field_data, associated_contacts, associated<br>`vlan__vid`: PASS |
| ipam.PrefixTestCase | `vpn_tunnel_endpoints_name_contains` | `CharFilter` | `vpn_tunnel_endpoints_name_contains` | `filter_vpntunnelendpoint_name_contains` | filter has `method=`; generic `__in` comparison can't express it | `vpn_tunnel_endpoints_name_contains`: ERROR FieldError: Cannot resolve keyword 'vpn_tunnel_endpoints_name_contains' into field. Choices are: _custom_field_data, assoc |
| ipam.PrefixTestCase | `vrfs` | `NaturalKeyOrPKMultipleChoiceFilter` | `vrfs` |  | passes as plain generic entry | `vrfs`: PASS |
| ipam.PrefixTestCase | `within` | `MultiValueCharFilter` | `within` | `search_within` | filter has `method=`; generic `__in` comparison can't express it | `within`: ERROR FieldError: Cannot resolve keyword 'within' into field. Choices are: _custom_field_data, associated_contacts, associated_d |
| ipam.PrefixTestCase | `within_include` | `MultiValueCharFilter` | `within_include` | `search_within_include` | filter has `method=`; generic `__in` comparison can't express it | `within_include`: ERROR FieldError: Cannot resolve keyword 'within_include' into field. Choices are: _custom_field_data, associated_contacts, asso |
| ipam.VLANGroupTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `location` |  | filterset result differs from `queryset.filter(field__in=...)` | `location`: FAIL AssertionError: Counter({<VLANGroup: BUDGET>: 1, <VLANGroup: DISTANCE>: 1, <VL[115 chars]: 1}) != Counter({<VLANGroup: PROTECT<br>`location__id`: FAIL AssertionError: Count[39 chars]oup: BUDGET>: 1, <VLANGroup: DISTANCE>: 1, <VL[145 chars]: 1}) != Count[39 chars]oup: PROTECTIO<br>`location__name`: FAIL AssertionError: Count[39 chars]oup: BUDGET>: 1, <VLANGroup: DISTANCE>: 1, <VL[93 chars]: 1}) != Count[39 chars]oup: PROTECTION |
| ipam.VLANLocationAssignmentTestCase | `created` | `MultiValueDateTimeFilter` | `created` |  | field_name isn't a real model field path (or filter name != field) | `created`: ERROR FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metada |
| ipam.VLANLocationAssignmentTestCase | `last_updated` | `MultiValueDateTimeFilter` | `last_updated` |  | field_name isn't a real model field path (or filter name != field) | `last_updated`: ERROR FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_m |
| ipam.VLANLocationAssignmentTestCase | `location` | `TreeNodeMultipleChoiceFilter` | `location` |  | passes as plain generic entry | `location`: PASS |
| ipam.VRFDeviceAssignmentTestCase | `created` | `MultiValueDateTimeFilter` | `created` |  | field_name isn't a real model field path (or filter name != field) | `created`: ERROR FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metada |
| ipam.VRFDeviceAssignmentTestCase | `last_updated` | `MultiValueDateTimeFilter` | `last_updated` |  | field_name isn't a real model field path (or filter name != field) | `last_updated`: ERROR FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_m |
| ipam.VRFPrefixAssignmentTestCase | `created` | `MultiValueDateTimeFilter` | `created` |  | field_name isn't a real model field path (or filter name != field) | `created`: ERROR FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metada |
| ipam.VRFPrefixAssignmentTestCase | `last_updated` | `MultiValueDateTimeFilter` | `last_updated` |  | field_name isn't a real model field path (or filter name != field) | `last_updated`: ERROR FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_m |
| ipam.VRFTestCase | `description` | `MultiValueCharFilter` | `description` |  | passes as plain generic entry | `description`: PASS |
| ipam.VRFTestCase | `device` | `NaturalKeyOrPKMultipleChoiceFilter` | `devices` |  | field_name isn't a real model field path (or filter name != field) | `device`: ERROR FieldError: Cannot resolve keyword 'device' into field. Choices are: _custom_field_data, associated_contacts, associated_d<br>`devices`: ERROR ValueError: Cannot find enough valid test data for VRF field devices. At least 3 unique values are required to test multiv<br>`devices__id`: ERROR ValueError: Cannot find enough valid test data for VRF field devices__id. At least 3 unique values are required to test mu<br>`devices__name`: ERROR ValueError: Cannot find enough valid test data for VRF field devices__name. At least 3 unique values are required to test  |
| ipam.VRFTestCase | `status` | `StatusFilter` | `status` |  | passes as plain generic entry | `status`: PASS |
| ipam.VRFTestCase | `virtual_device_contexts` | `NaturalKeyOrPKMultipleChoiceFilter` | `virtual_device_contexts` |  | passes as plain generic entry | `virtual_device_contexts`: PASS |
| ipam.VRFTestCase | `virtual_machines` | `NaturalKeyOrPKMultipleChoiceFilter` | `virtual_machines` |  | test data has < 2 distinct values with a non-matching remainder | `virtual_machines`: ERROR ValueError: Cannot find enough valid test data for VRF field virtual_machines. At least 3 unique values are required to te<br>`virtual_machines__id`: ERROR ValueError: Cannot find enough valid test data for VRF field virtual_machines__id. At least 3 unique values are required t<br>`virtual_machines__name`: ERROR ValueError: Cannot find enough valid test data for VRF field virtual_machines__name. At least 3 unique values are required |
| load_balancers.LoadBalancerPoolMemberFilterTestCase | `ssl_offload` | `BooleanFilter` | `ssl_offload` |  | test data has < 2 distinct values with a non-matching remainder | `ssl_offload`: ERROR ValueError: Cannot find enough valid test data for LoadBalancerPoolMember field ssl_offload. At least 3 unique values are  |
| load_balancers.LoadBalancerPoolMemberFilterTestCase | `status` | `StatusFilter` | `status` |  | test data has < 2 distinct values with a non-matching remainder | `status`: ERROR ValueError: Cannot find enough valid test data for LoadBalancerPoolMember field status. At least 3 unique values are requi<br>`status__id`: ERROR ValueError: Cannot find enough valid test data for LoadBalancerPoolMember field status__id. At least 3 unique values are r<br>`status__name`: ERROR ValueError: Cannot find enough valid test data for LoadBalancerPoolMember field status__name. At least 3 unique values are |
| load_balancers.VirtualServerFilterTestCase | `enabled` | `BooleanFilter` | `enabled` |  | test data has < 2 distinct values with a non-matching remainder | `enabled`: ERROR ValueError: Cannot find enough valid test data for VirtualServer field enabled. At least 3 unique values are required to t |
| load_balancers.VirtualServerFilterTestCase | `ssl_offload` | `BooleanFilter` | `ssl_offload` |  | test data has < 2 distinct values with a non-matching remainder | `ssl_offload`: ERROR ValueError: Cannot find enough valid test data for VirtualServer field ssl_offload. At least 3 unique values are required  |
| virtualization.ClusterTestCase | `devices` | `NaturalKeyOrPKMultipleChoiceFilter` | `devices` |  | test data has < 2 distinct values with a non-matching remainder | `devices`: ERROR ValueError: Cannot find enough valid test data for Cluster field devices. At least 3 unique values are required to test mu<br>`devices__id`: ERROR ValueError: Cannot find enough valid test data for Cluster field devices__id. At least 3 unique values are required to tes<br>`devices__name`: ERROR ValueError: Cannot find enough valid test data for Cluster field devices__name. At least 3 unique values are required to t |
| virtualization.VMInterfaceTestCase | `enabled` | `BooleanFilter` | `enabled` |  | test data has < 2 distinct values with a non-matching remainder | `enabled`: ERROR ValueError: Cannot find enough valid test data for VMInterface field enabled. At least 3 unique values are required to tes |
| virtualization.VMInterfaceTestCase | `status` | `StatusFilter` | `status` |  | passes as plain generic entry | `status`: PASS |
| virtualization.VMInterfaceTestCase | `vlan_id` | `CharFilter` | `vlan_id` | `filter_vlan_id` | filter has `method=`; generic `__in` comparison can't express it | `vlan_id`: ERROR FieldError: Cannot resolve keyword 'vlan_id' into field. Choices are: _custom_field_data, _name, associated_contacts, asso |
| virtualization.VirtualMachineTestCase | `local_config_context_schema` | `NaturalKeyOrPKMultipleChoiceFilter` | `local_config_context_schema` |  | test data has < 2 distinct values with a non-matching remainder | `local_config_context_schema`: ERROR ValueError: Cannot find enough valid test data for VirtualMachine field local_config_context_schema. At least 3 unique val<br>`local_config_context_schema__id`: ERROR ValueError: Cannot find enough valid test data for VirtualMachine field local_config_context_schema__id. At least 3 unique<br>`local_config_context_schema__name`: ERROR ValueError: Cannot find enough valid test data for VirtualMachine field local_config_context_schema__name. At least 3 uniq |
| virtualization.VirtualMachineTestCase | `local_config_context_schema_id` | `ModelMultipleChoiceFilter` | `local_config_context_schema_id` |  | test data has < 2 distinct values with a non-matching remainder | `local_config_context_schema_id`: ERROR ValueError: Cannot find enough valid test data for VirtualMachine field local_config_context_schema_id. At least 3 unique <br>`local_config_context_schema_id__id`: ERROR ValueError: Cannot find enough valid test data for VirtualMachine field local_config_context_schema_id__id. At least 3 uni<br>`local_config_context_schema_id__name`: ERROR ValueError: Cannot find enough valid test data for VirtualMachine field local_config_context_schema_id__name. At least 3 u |
| vpn.VPNFilterTestCase | `extra_attributes` | `MultiValueCharFilter` | `extra_attributes` |  | filterset result differs from `queryset.filter(field__in=...)` | `extra_attributes`: FAIL AssertionError: 0 == 0 : QuerySet cannot be empty |
| vpn.VPNFilterTestCase | `role` | `RoleFilter` | `role` |  | passes as plain generic entry | `role`: PASS |
| vpn.VPNFilterTestCase | `status` | `StatusFilter` | `status` |  | passes as plain generic entry | `status`: PASS |
| vpn.VPNPhase1PolicyFilterTestCase | `aggressive_mode` | `BooleanFilter` | `aggressive_mode` |  | test data has < 2 distinct values with a non-matching remainder | `aggressive_mode`: ERROR ValueError: Cannot find enough valid test data for VPNPhase1Policy field aggressive_mode. At least 3 unique values are req |
| vpn.VPNPhase1PolicyFilterTestCase | `ike_version` | `MultipleChoiceFilter` | `ike_version` |  | test data has < 2 distinct values with a non-matching remainder | `ike_version`: ERROR ValueError: Cannot find enough valid test data for VPNPhase1Policy field ike_version. At least 3 unique values are require |
| vpn.VPNPhase1PolicyFilterTestCase | `vpn_profiles` | `NaturalKeyOrPKMultipleChoiceFilter` | `vpn_profiles` |  | passes as plain generic entry | `vpn_profiles`: PASS |
| vpn.VPNPhase2PolicyFilterTestCase | `vpn_profiles` | `NaturalKeyOrPKMultipleChoiceFilter` | `vpn_profiles` |  | passes as plain generic entry | `vpn_profiles`: PASS |
| vpn.VPNProfileFilterTestCase | `extra_options` | `MultiValueCharFilter` | `extra_options` |  | filterset result differs from `queryset.filter(field__in=...)` | `extra_options`: FAIL AssertionError: 0 == 0 : QuerySet cannot be empty |
| vpn.VPNProfileFilterTestCase | `keepalive_enabled` | `BooleanFilter` | `keepalive_enabled` |  | test data has < 2 distinct values with a non-matching remainder | `keepalive_enabled`: ERROR ValueError: Cannot find enough valid test data for VPNProfile field keepalive_enabled. At least 3 unique values are requir |
| vpn.VPNProfileFilterTestCase | `nat_traversal` | `BooleanFilter` | `nat_traversal` |  | test data has < 2 distinct values with a non-matching remainder | `nat_traversal`: ERROR ValueError: Cannot find enough valid test data for VPNProfile field nat_traversal. At least 3 unique values are required t |
| vpn.VPNProfileFilterTestCase | `role` | `RoleFilter` | `role` |  | passes as plain generic entry | `role`: PASS |
| vpn.VPNProfileFilterTestCase | `secrets_group` | `ModelMultipleChoiceFilter` | `secrets_group` |  | test data has < 2 distinct values with a non-matching remainder | `secrets_group`: ERROR ValueError: Cannot find enough valid test data for VPNProfile field secrets_group. At least 3 unique values are required t<br>`secrets_group__id`: ERROR ValueError: Cannot find enough valid test data for VPNProfile field secrets_group__id. At least 3 unique values are requir<br>`secrets_group__name`: ERROR ValueError: Cannot find enough valid test data for VPNProfile field secrets_group__name. At least 3 unique values are requ |
| vpn.VPNProfilePhase1PolicyAssignmentFilterTestCase | `weight` | `MultiValueNumberFilter` | `weight` |  | test data has < 2 distinct values with a non-matching remainder | `weight`: ERROR ValueError: Cannot find enough valid test data for VPNProfilePhase1PolicyAssignment field weight. At least 3 unique values |
| vpn.VPNProfilePhase2PolicyAssignmentFilterTestCase | `weight` | `MultiValueNumberFilter` | `weight` |  | test data has < 2 distinct values with a non-matching remainder | `weight`: ERROR ValueError: Cannot find enough valid test data for VPNProfilePhase2PolicyAssignment field weight. At least 3 unique values |
| vpn.VPNTunnelEndpointFilterTestCase | `name` | `MultiValueCharFilter` | `name` |  | passes as plain generic entry | `name`: PASS |
| vpn.VPNTunnelEndpointFilterTestCase | `protected_prefixes` | `ModelMultipleChoiceFilter` | `protected_prefixes` |  | passes as plain generic entry | `protected_prefixes`: PASS |
| vpn.VPNTunnelEndpointFilterTestCase | `protected_prefixes_dg` | `ModelMultipleChoiceFilter` | `protected_prefixes_dg` |  | test data has < 2 distinct values with a non-matching remainder | `protected_prefixes_dg`: ERROR ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field protected_prefixes_dg. At least 3 unique values<br>`protected_prefixes_dg__id`: ERROR ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field protected_prefixes_dg__id. At least 3 unique va<br>`protected_prefixes_dg__name`: ERROR ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field protected_prefixes_dg__name. At least 3 unique  |
| vpn.VPNTunnelEndpointFilterTestCase | `role` | `RoleFilter` | `role` |  | passes as plain generic entry | `role`: PASS |
| vpn.VPNTunnelEndpointFilterTestCase | `source_ipaddress` | `NaturalKeyOrPKMultipleChoiceFilter` | `source_ipaddress` |  | test data has < 2 distinct values with a non-matching remainder | `source_ipaddress`: ERROR ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field source_ipaddress. At least 3 unique values are <br>`source_ipaddress__id`: ERROR ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field source_ipaddress__id. At least 3 unique values <br>`source_ipaddress__name`: ERROR FieldError: Cannot resolve keyword 'name' into field. Choices are: _custom_field_data, associated_contacts, associated_dat |
| vpn.VPNTunnelEndpointFilterTestCase | `tunnel_interface` | `NaturalKeyOrPKMultipleChoiceFilter` | `tunnel_interface` |  | test data has < 2 distinct values with a non-matching remainder | `tunnel_interface`: ERROR ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field tunnel_interface. At least 3 unique values are <br>`tunnel_interface__id`: ERROR ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field tunnel_interface__id. At least 3 unique values <br>`tunnel_interface__name`: ERROR ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field tunnel_interface__name. At least 3 unique value |
| vpn.VPNTunnelEndpointFilterTestCase | `vpn_profile` | `ModelMultipleChoiceFilter` | `vpn_profile` |  | passes as plain generic entry | `vpn_profile`: PASS |
| vpn.VPNTunnelFilterTestCase | `endpoint_a` | `ModelMultipleChoiceFilter` | `endpoint_a` |  | passes as plain generic entry | `endpoint_a`: PASS |
| vpn.VPNTunnelFilterTestCase | `endpoint_z` | `ModelMultipleChoiceFilter` | `endpoint_z` |  | passes as plain generic entry | `endpoint_z`: PASS |
| vpn.VPNTunnelFilterTestCase | `role` | `RoleFilter` | `role` |  | passes as plain generic entry | `role`: PASS |
| vpn.VPNTunnelFilterTestCase | `secrets_group` | `ModelMultipleChoiceFilter` | `secrets_group` |  | test data has < 2 distinct values with a non-matching remainder | `secrets_group`: ERROR ValueError: Cannot find enough valid test data for VPNTunnel field secrets_group. At least 3 unique values are required to<br>`secrets_group__id`: ERROR ValueError: Cannot find enough valid test data for VPNTunnel field secrets_group__id. At least 3 unique values are require<br>`secrets_group__name`: ERROR ValueError: Cannot find enough valid test data for VPNTunnel field secrets_group__name. At least 3 unique values are requi |
| vpn.VPNTunnelFilterTestCase | `status` | `StatusFilter` | `status` |  | passes as plain generic entry | `status`: PASS |
| wireless.ControllerManagedDeviceGroupWirelessNetworkAssignmentTestCase | `vlan` | `ModelMultipleChoiceFilter` | `vlan` |  | passes as plain generic entry | `vlan`: PASS |
| wireless.RadioProfileTestCase | `allowed_channel_list` | `MultiValueCharFilter` | `allowed_channel_list` |  | ValueError | `allowed_channel_list`: ERROR ValueError: value [36] is not list or tuple |
| wireless.RadioProfileTestCase | `controller_managed_device_groups__devices` | `NaturalKeyOrPKMultipleChoiceFilter` | `controller_managed_device_groups__devices` |  | passes as plain generic entry | `controller_managed_device_groups__devices`: PASS |
| wireless.RadioProfileTestCase | `rx_power_min` | `MultiValueNumberFilter` | `rx_power_min` |  | passes as plain generic entry | `rx_power_min`: PASS |
| wireless.RadioProfileTestCase | `supported_data_rates` | `ModelMultipleChoiceFilter` | `supported_data_rates` |  | passes as plain generic entry | `supported_data_rates`: PASS |
| wireless.RadioProfileTestCase | `tx_power_max` | `MultiValueNumberFilter` | `tx_power_max` |  | passes as plain generic entry | `tx_power_max`: PASS |
| wireless.RadioProfileTestCase | `tx_power_min` | `MultiValueNumberFilter` | `tx_power_min` |  | passes as plain generic entry | `tx_power_min`: PASS |
| wireless.WirelessNetworkTestCase | `controller_managed_device_groups__controller` | `NaturalKeyOrPKMultipleChoiceFilter` | `controller_managed_device_groups__controller` |  | passes as plain generic entry | `controller_managed_device_groups__controller`: PASS |
| wireless.WirelessNetworkTestCase | `controller_managed_device_groups__devices` | `NaturalKeyOrPKMultipleChoiceFilter` | `controller_managed_device_groups__devices` |  | passes as plain generic entry | `controller_managed_device_groups__devices`: PASS |
| wireless.WirelessNetworkTestCase | `enabled` | `BooleanFilter` | `enabled` |  | test data has < 2 distinct values with a non-matching remainder | `enabled`: ERROR ValueError: Cannot find enough valid test data for WirelessNetwork field enabled. At least 3 unique values are required to |
| wireless.WirelessNetworkTestCase | `hidden` | `BooleanFilter` | `hidden` |  | test data has < 2 distinct values with a non-matching remainder | `hidden`: ERROR ValueError: Cannot find enough valid test data for WirelessNetwork field hidden. At least 3 unique values are required to  |

## Tracebacks

Traceback of each non-passing attempt, grouped by test class.

### nautobot.circuits.tests.test_filters.CircuitTerminationTestCase

<details><summary><code>available_for_cable</code> via <code>available_for_cable</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, circuit, circuit_id, cloud_network, cloud_network_id, created, description, destination_for_associations, id, last_updated, location, location_id, port_speed, pp_info, provider_network, provider_network_id, source_for_associations, static_group_association_set, tagged_items, tags, term_side, upstream_speed, xconnect_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, circuit, circuit_id, cloud_network, cloud_network_id, created, description, destination_for_associations, id, last_updated, location, location_id, port_speed, pp_info, provider_network, provider_network_id, source_for_associations, static_group_association_set, tagged_items, tags, term_side, upstream_speed, xconnect_id
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, circuit, circuit_id, cloud_network, cloud_network_id, created, description, destination_for_associations, id, last_updated, location, location_id, port_speed, pp_info, provider_network, provider_network_id, source_for_associations, static_group_association_set, tagged_items, tags, term_side, upstream_speed, xconnect_id
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, circuit, circuit_id, cloud_network, cloud_network_id, created, description, destination_for_associations, id, last_updated, location, location_id, port_speed, pp_info, provider_network, provider_network_id, source_for_associations, static_group_association_set, tagged_items, tags, term_side, upstream_speed, xconnect_id
```
</details>

<details><summary><code>location</code> via <code>location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for CircuitTermination field location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for CircuitTermination field location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for CircuitTermination field location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.data_validation.tests.test_filters.MinMaxValidationRuleFilterTestCase

<details><summary><code>enabled</code> via <code>enabled</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for MinMaxValidationRule field enabled. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>max</code> via <code>max</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for MinMaxValidationRule field max. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>min</code> via <code>min</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for MinMaxValidationRule field min. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.data_validation.tests.test_filters.RegularExpressionValidationRuleFilterTestCase

<details><summary><code>context_processing</code> via <code>context_processing</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for RegularExpressionValidationRule field context_processing. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>enabled</code> via <code>enabled</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for RegularExpressionValidationRule field enabled. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.data_validation.tests.test_filters.RequiredValidationRuleFilterTestCase

<details><summary><code>enabled</code> via <code>enabled</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for RequiredValidationRule field enabled. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.data_validation.tests.test_filters.UniqueValidationRuleFilterTestCase

<details><summary><code>enabled</code> via <code>enabled</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for UniqueValidationRule field enabled. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.CableTestCase

<details><summary><code>cable_type</code> via <code>cable_type</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Cable field cable_type. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>cable_type</code> via <code>cable_type__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Cable field cable_type__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>cable_type</code> via <code>cable_type__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Cable field cable_type__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>device_id</code> via <code>device_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>device_id</code> via <code>terminations</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 81, in test_probe_untested_filters
    self.assertTrue(fs.is_valid(), fs.errors.as_text())
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 744, in assertTrue
    raise self.failureException(msg)
AssertionError: False is not true : * device_id
  * Select a valid choice. d2b5823a-e1ab-4f0d-935e-5ba2739cea48 is not one of the available choices.
```
</details>

<details><summary><code>device_id</code> via <code>terminations__id</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 81, in test_probe_untested_filters
    self.assertTrue(fs.is_valid(), fs.errors.as_text())
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 744, in assertTrue
    raise self.failureException(msg)
AssertionError: False is not true : * device_id
  * Select a valid choice. d2b5823a-e1ab-4f0d-935e-5ba2739cea48 is not one of the available choices.
```
</details>

<details><summary><code>device_id</code> via <code>terminations__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2267, in add_fields
    cols.append(join_info.transform_function(targets[0], final_alias))
                ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1931, in transform
    return self.try_transform(wrapped, name)
           ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1460, in try_transform
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Unsupported lookup 'name' for UUIDField or join on the field not permitted.
```
</details>

<details><summary><code>location_id</code> via <code>location_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>location_id</code> via <code>device__location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>location_id</code> via <code>device__location__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>location_id</code> via <code>device__location__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>rack_id</code> via <code>rack_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'rack_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'rack_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>rack_id</code> via <code>device__rack</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>rack_id</code> via <code>device__rack__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>rack_id</code> via <code>device__rack__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>tenant_id</code> via <code>tenant_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'tenant_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'tenant_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>tenant_id</code> via <code>device__tenant</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>tenant_id</code> via <code>device__tenant__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>tenant_id</code> via <code>device__tenant__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>termination_a_id</code> via <code>termination_a_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'termination_a_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'termination_a_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>termination_a_type</code> via <code>termination_a_type</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'termination_a_type' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'termination_a_type' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>termination_b_id</code> via <code>termination_b_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'termination_b_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'termination_b_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>termination_b_type</code> via <code>termination_b_type</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'termination_b_type' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'termination_b_type' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

<details><summary><code>termination_id</code> via <code>termination_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'termination_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'termination_id' into field. Choices are: _abs_length, _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, cable_type, cable_type_id, circuit_terminations, color, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, label, last_updated, length, length_unit, power_feeds, power_outlets, power_ports, rear_ports, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, terminations, type
```
</details>

### nautobot.dcim.tests.test_filters.ConsoleConnectionFilterSetTestCase

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

### nautobot.dcim.tests.test_filters.ConsolePortTestCase

<details><summary><code>available_for_cable</code> via <code>available_for_cable</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>location</code> via <code>device__location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConsolePort field device__location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConsolePort field device__location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConsolePort field device__location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.ConsoleServerPortTestCase

<details><summary><code>available_for_cable</code> via <code>available_for_cable</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>location</code> via <code>device__location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConsoleServerPort field device__location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConsoleServerPort field device__location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConsoleServerPort field device__location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.ControllerFilterSetTestCase

<details><summary><code>capabilities</code> via <code>capabilities</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Controller field capabilities. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.ControllerManagedDeviceGroupFilterSetTestCase

<details><summary><code>capabilities</code> via <code>capabilities</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field capabilities. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>description</code> via <code>description</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field description. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>subtree</code> via <code>subtree</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'subtree' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, capabilities, children, controller, controller_id, created, description, destination_for_associations, devices, id, last_updated, name, parent, parent_id, radio_profile_assignments, radio_profiles, source_for_associations, static_group_association_set, tagged_items, tags, tenant, tenant_id, virtual_device_contexts, weight, wireless_network_assignments, wireless_networks

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'subtree' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, capabilities, children, controller, controller_id, created, description, destination_for_associations, devices, id, last_updated, name, parent, parent_id, radio_profile_assignments, radio_profiles, source_for_associations, static_group_association_set, tagged_items, tags, tenant, tenant_id, virtual_device_contexts, weight, wireless_network_assignments, wireless_networks
```
</details>

<details><summary><code>subtree</code> via <code>subtree__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'subtree' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, capabilities, children, controller, controller_id, created, description, destination_for_associations, devices, id, last_updated, name, parent, parent_id, radio_profile_assignments, radio_profiles, source_for_associations, static_group_association_set, tagged_items, tags, tenant, tenant_id, virtual_device_contexts, weight, wireless_network_assignments, wireless_networks
```
</details>

<details><summary><code>subtree</code> via <code>subtree__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'subtree' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, capabilities, children, controller, controller_id, created, description, destination_for_associations, devices, id, last_updated, name, parent, parent_id, radio_profile_assignments, radio_profiles, source_for_associations, static_group_association_set, tagged_items, tags, tenant, tenant_id, virtual_device_contexts, weight, wireless_network_assignments, wireless_networks
```
</details>

<details><summary><code>tenant</code> via <code>tenant</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant</code> via <code>tenant__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant</code> via <code>tenant__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant_group</code> via <code>tenant_group</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'tenant_group' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, capabilities, children, controller, controller_id, created, description, destination_for_associations, devices, id, last_updated, name, parent, parent_id, radio_profile_assignments, radio_profiles, source_for_associations, static_group_association_set, tagged_items, tags, tenant, tenant_id, virtual_device_contexts, weight, wireless_network_assignments, wireless_networks

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'tenant_group' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, capabilities, children, controller, controller_id, created, description, destination_for_associations, devices, id, last_updated, name, parent, parent_id, radio_profile_assignments, radio_profiles, source_for_associations, static_group_association_set, tagged_items, tags, tenant, tenant_id, virtual_device_contexts, weight, wireless_network_assignments, wireless_networks
```
</details>

<details><summary><code>tenant_group</code> via <code>tenant__tenant_group</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant__tenant_group. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant_group</code> via <code>tenant__tenant_group__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant__tenant_group__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant_group</code> via <code>tenant__tenant_group__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant__tenant_group__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant_id</code> via <code>tenant_id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant_id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant_id</code> via <code>tenant_id__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant_id__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant_id</code> via <code>tenant_id__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ControllerManagedDeviceGroup field tenant_id__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.DeviceBayTestCase

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, device, device_id, id, installed_device, installed_device_id, label, last_updated, name, source_for_associations, static_group_association_set, tagged_items, tags

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, device, device_id, id, installed_device, installed_device_id, label, last_updated, name, source_for_associations, static_group_association_set, tagged_items, tags
```
</details>

<details><summary><code>location</code> via <code>device__location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for DeviceBay field device__location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for DeviceBay field device__location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for DeviceBay field device__location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.DeviceClusterAssignmentTestCase

<details><summary><code>created</code> via <code>created</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, cluster, cluster_id, device, device_id, id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, cluster, cluster_id, device, device_id, id
```
</details>

<details><summary><code>last_updated</code> via <code>last_updated</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, cluster, cluster_id, device, device_id, id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, cluster, cluster_id, device, device_id, id
```
</details>

### nautobot.dcim.tests.test_filters.DeviceTestCase

<details><summary><code>controller</code> via <code>controller</code>: ERROR FieldError</summary>

```
_name, asset_tag, associated_contacts, associated_data_compliance, associated_object_metadata, cluster_assignments, clusters, comments, console_ports, console_server_ports, controller_managed_device_group, controller_managed_device_group_id, controllers, created, destination_for_associations, device_bays, device_redundancy_group, device_redundancy_group_id, device_redundancy_group_priority, device_type, device_type_id, face, front_ports, id, images, interfaces, inventory_items, last_updated, local_config_context_data, local_config_context_data_owner, local_config_context_data_owner_content_type, local_config_context_data_owner_content_type_id, local_config_context_data_owner_object_id, local_config_context_schema, local_config_context_schema_id, location, location_id, module_bays, name, parent_bay, platform, platform_id, position, power_outlets, power_ports, primary_ip4, primary_ip4_id, primary_ip6, primary_ip6_id, rack, rack_id, rear_ports, role, role_id, secrets_group, secrets_group_id, serial, services, software_image_files, software_version, software_version_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, vc_master_for, vc_position, vc_priority, virtual_chassis, virtual_chassis_id, virtual_device_contexts, virtual_servers, vpn_tunnel_endpoints, vrf_assignments, vrfs

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'controller' into field. Choices are: _custom_field_data, _name, asset_tag, associated_contacts, associated_data_compliance, associated_object_metadata, cluster_assignments, clusters, comments, console_ports, console_server_ports, controller_managed_device_group, controller_managed_device_group_id, controllers, created, destination_for_associations, device_bays, device_redundancy_group, device_redundancy_group_id, device_redundancy_group_priority, device_type, device_type_id, face, front_ports, id, images, interfaces, inventory_items, last_updated, local_config_context_data, local_config_context_data_owner, local_config_context_data_owner_content_type, local_config_context_data_owner_content_type_id, local_config_context_data_owner_object_id, local_config_context_schema, local_config_context_schema_id, location, location_id, module_bays, name, parent_bay, platform, platform_id, position, power_outlets, power_ports, primary_ip4, primary_ip4_id, primary_ip6, primary_ip6_id, rack, rack_id, rear_ports, role, role_id, secrets_group, secrets_group_id, serial, services, software_image_files, software_version, software_version_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, vc_master_for, vc_position, vc_priority, virtual_chassis, virtual_chassis_id, virtual_device_contexts, virtual_servers, vpn_tunnel_endpoints, vrf_assignments, vrfs
```
</details>

<details><summary><code>controller</code> via <code>controller_managed_device_group__controller</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field controller_managed_device_group__controller. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>controller</code> via <code>controller_managed_device_group__controller__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field controller_managed_device_group__controller__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>controller</code> via <code>controller_managed_device_group__controller__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field controller_managed_device_group__controller__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>has_primary_ip</code> via <code>has_primary_ip</code>: ERROR FieldError</summary>

```
e, asset_tag, associated_contacts, associated_data_compliance, associated_object_metadata, cluster_assignments, clusters, comments, console_ports, console_server_ports, controller_managed_device_group, controller_managed_device_group_id, controllers, created, destination_for_associations, device_bays, device_redundancy_group, device_redundancy_group_id, device_redundancy_group_priority, device_type, device_type_id, face, front_ports, id, images, interfaces, inventory_items, last_updated, local_config_context_data, local_config_context_data_owner, local_config_context_data_owner_content_type, local_config_context_data_owner_content_type_id, local_config_context_data_owner_object_id, local_config_context_schema, local_config_context_schema_id, location, location_id, module_bays, name, parent_bay, platform, platform_id, position, power_outlets, power_ports, primary_ip4, primary_ip4_id, primary_ip6, primary_ip6_id, rack, rack_id, rear_ports, role, role_id, secrets_group, secrets_group_id, serial, services, software_image_files, software_version, software_version_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, vc_master_for, vc_position, vc_priority, virtual_chassis, virtual_chassis_id, virtual_device_contexts, virtual_servers, vpn_tunnel_endpoints, vrf_assignments, vrfs

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'has_primary_ip' into field. Choices are: _custom_field_data, _name, asset_tag, associated_contacts, associated_data_compliance, associated_object_metadata, cluster_assignments, clusters, comments, console_ports, console_server_ports, controller_managed_device_group, controller_managed_device_group_id, controllers, created, destination_for_associations, device_bays, device_redundancy_group, device_redundancy_group_id, device_redundancy_group_priority, device_type, device_type_id, face, front_ports, id, images, interfaces, inventory_items, last_updated, local_config_context_data, local_config_context_data_owner, local_config_context_data_owner_content_type, local_config_context_data_owner_content_type_id, local_config_context_data_owner_object_id, local_config_context_schema, local_config_context_schema_id, location, location_id, module_bays, name, parent_bay, platform, platform_id, position, power_outlets, power_ports, primary_ip4, primary_ip4_id, primary_ip6, primary_ip6_id, rack, rack_id, rear_ports, role, role_id, secrets_group, secrets_group_id, serial, services, software_image_files, software_version, software_version_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, vc_master_for, vc_position, vc_priority, virtual_chassis, virtual_chassis_id, virtual_device_contexts, virtual_servers, vpn_tunnel_endpoints, vrf_assignments, vrfs
```
</details>

<details><summary><code>is_full_depth</code> via <code>is_full_depth</code>: ERROR FieldError</summary>

```
me, asset_tag, associated_contacts, associated_data_compliance, associated_object_metadata, cluster_assignments, clusters, comments, console_ports, console_server_ports, controller_managed_device_group, controller_managed_device_group_id, controllers, created, destination_for_associations, device_bays, device_redundancy_group, device_redundancy_group_id, device_redundancy_group_priority, device_type, device_type_id, face, front_ports, id, images, interfaces, inventory_items, last_updated, local_config_context_data, local_config_context_data_owner, local_config_context_data_owner_content_type, local_config_context_data_owner_content_type_id, local_config_context_data_owner_object_id, local_config_context_schema, local_config_context_schema_id, location, location_id, module_bays, name, parent_bay, platform, platform_id, position, power_outlets, power_ports, primary_ip4, primary_ip4_id, primary_ip6, primary_ip6_id, rack, rack_id, rear_ports, role, role_id, secrets_group, secrets_group_id, serial, services, software_image_files, software_version, software_version_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, vc_master_for, vc_position, vc_priority, virtual_chassis, virtual_chassis_id, virtual_device_contexts, virtual_servers, vpn_tunnel_endpoints, vrf_assignments, vrfs

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'is_full_depth' into field. Choices are: _custom_field_data, _name, asset_tag, associated_contacts, associated_data_compliance, associated_object_metadata, cluster_assignments, clusters, comments, console_ports, console_server_ports, controller_managed_device_group, controller_managed_device_group_id, controllers, created, destination_for_associations, device_bays, device_redundancy_group, device_redundancy_group_id, device_redundancy_group_priority, device_type, device_type_id, face, front_ports, id, images, interfaces, inventory_items, last_updated, local_config_context_data, local_config_context_data_owner, local_config_context_data_owner_content_type, local_config_context_data_owner_content_type_id, local_config_context_data_owner_object_id, local_config_context_schema, local_config_context_schema_id, location, location_id, module_bays, name, parent_bay, platform, platform_id, position, power_outlets, power_ports, primary_ip4, primary_ip4_id, primary_ip6, primary_ip6_id, rack, rack_id, rear_ports, role, role_id, secrets_group, secrets_group_id, serial, services, software_image_files, software_version, software_version_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, vc_master_for, vc_position, vc_priority, virtual_chassis, virtual_chassis_id, virtual_device_contexts, virtual_servers, vpn_tunnel_endpoints, vrf_assignments, vrfs
```
</details>

<details><summary><code>is_full_depth</code> via <code>device_type__is_full_depth</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field device_type__is_full_depth. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>local_config_context_data</code> via <code>local_config_context_data</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field local_config_context_data. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>local_config_context_schema</code> via <code>local_config_context_schema</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field local_config_context_schema. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>local_config_context_schema</code> via <code>local_config_context_schema__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field local_config_context_schema__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>local_config_context_schema</code> via <code>local_config_context_schema__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field local_config_context_schema__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>local_config_context_schema_id</code> via <code>local_config_context_schema_id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field local_config_context_schema_id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>local_config_context_schema_id</code> via <code>local_config_context_schema_id__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field local_config_context_schema_id__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>local_config_context_schema_id</code> via <code>local_config_context_schema_id__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field local_config_context_schema_id__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Device field location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.DeviceTypeTestCase

<details><summary><code>console_ports</code> via <code>console_ports</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'console_ports' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, comments, console_port_templates, console_server_port_templates, created, destination_for_associations, device_bay_templates, device_family, device_family_id, devices, front_image, front_port_templates, id, interface_templates, is_full_depth, last_updated, manufacturer, manufacturer_id, model, module_bay_templates, part_number, power_outlet_templates, power_port_templates, rear_image, rear_port_templates, software_image_file_mappings, software_image_files, source_for_associations, static_group_association_set, subdevice_role, tagged_items, tags, u_height

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'console_ports' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, comments, console_port_templates, console_server_port_templates, created, destination_for_associations, device_bay_templates, device_family, device_family_id, devices, front_image, front_port_templates, id, interface_templates, is_full_depth, last_updated, manufacturer, manufacturer_id, model, module_bay_templates, part_number, power_outlet_templates, power_port_templates, rear_image, rear_port_templates, software_image_file_mappings, software_image_files, source_for_associations, static_group_association_set, subdevice_role, tagged_items, tags, u_height
```
</details>

<details><summary><code>console_server_ports</code> via <code>console_server_ports</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'console_server_ports' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, comments, console_port_templates, console_server_port_templates, created, destination_for_associations, device_bay_templates, device_family, device_family_id, devices, front_image, front_port_templates, id, interface_templates, is_full_depth, last_updated, manufacturer, manufacturer_id, model, module_bay_templates, part_number, power_outlet_templates, power_port_templates, rear_image, rear_port_templates, software_image_file_mappings, software_image_files, source_for_associations, static_group_association_set, subdevice_role, tagged_items, tags, u_height

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'console_server_ports' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, comments, console_port_templates, console_server_port_templates, created, destination_for_associations, device_bay_templates, device_family, device_family_id, devices, front_image, front_port_templates, id, interface_templates, is_full_depth, last_updated, manufacturer, manufacturer_id, model, module_bay_templates, part_number, power_outlet_templates, power_port_templates, rear_image, rear_port_templates, software_image_file_mappings, software_image_files, source_for_associations, static_group_association_set, subdevice_role, tagged_items, tags, u_height
```
</details>

<details><summary><code>device_bays</code> via <code>device_bays</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device_bays' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, comments, console_port_templates, console_server_port_templates, created, destination_for_associations, device_bay_templates, device_family, device_family_id, devices, front_image, front_port_templates, id, interface_templates, is_full_depth, last_updated, manufacturer, manufacturer_id, model, module_bay_templates, part_number, power_outlet_templates, power_port_templates, rear_image, rear_port_templates, software_image_file_mappings, software_image_files, source_for_associations, static_group_association_set, subdevice_role, tagged_items, tags, u_height

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device_bays' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, comments, console_port_templates, console_server_port_templates, created, destination_for_associations, device_bay_templates, device_family, device_family_id, devices, front_image, front_port_templates, id, interface_templates, is_full_depth, last_updated, manufacturer, manufacturer_id, model, module_bay_templates, part_number, power_outlet_templates, power_port_templates, rear_image, rear_port_templates, software_image_file_mappings, software_image_files, source_for_associations, static_group_association_set, subdevice_role, tagged_items, tags, u_height
```
</details>

<details><summary><code>interfaces</code> via <code>interfaces</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'interfaces' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, comments, console_port_templates, console_server_port_templates, created, destination_for_associations, device_bay_templates, device_family, device_family_id, devices, front_image, front_port_templates, id, interface_templates, is_full_depth, last_updated, manufacturer, manufacturer_id, model, module_bay_templates, part_number, power_outlet_templates, power_port_templates, rear_image, rear_port_templates, software_image_file_mappings, software_image_files, source_for_associations, static_group_association_set, subdevice_role, tagged_items, tags, u_height

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'interfaces' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, comments, console_port_templates, console_server_port_templates, created, destination_for_associations, device_bay_templates, device_family, device_family_id, devices, front_image, front_port_templates, id, interface_templates, is_full_depth, last_updated, manufacturer, manufacturer_id, model, module_bay_templates, part_number, power_outlet_templates, power_port_templates, rear_image, rear_port_templates, software_image_file_mappings, software_image_files, source_for_associations, static_group_association_set, subdevice_role, tagged_items, tags, u_height
```
</details>

<details><summary><code>is_full_depth</code> via <code>is_full_depth</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for DeviceType field is_full_depth. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>power_outlets</code> via <code>power_outlets</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'power_outlets' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, comments, console_port_templates, console_server_port_templates, created, destination_for_associations, device_bay_templates, device_family, device_family_id, devices, front_image, front_port_templates, id, interface_templates, is_full_depth, last_updated, manufacturer, manufacturer_id, model, module_bay_templates, part_number, power_outlet_templates, power_port_templates, rear_image, rear_port_templates, software_image_file_mappings, software_image_files, source_for_associations, static_group_association_set, subdevice_role, tagged_items, tags, u_height

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'power_outlets' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, comments, console_port_templates, console_server_port_templates, created, destination_for_associations, device_bay_templates, device_family, device_family_id, devices, front_image, front_port_templates, id, interface_templates, is_full_depth, last_updated, manufacturer, manufacturer_id, model, module_bay_templates, part_number, power_outlet_templates, power_port_templates, rear_image, rear_port_templates, software_image_file_mappings, software_image_files, source_for_associations, static_group_association_set, subdevice_role, tagged_items, tags, u_height
```
</details>

<details><summary><code>power_ports</code> via <code>power_ports</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'power_ports' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, comments, console_port_templates, console_server_port_templates, created, destination_for_associations, device_bay_templates, device_family, device_family_id, devices, front_image, front_port_templates, id, interface_templates, is_full_depth, last_updated, manufacturer, manufacturer_id, model, module_bay_templates, part_number, power_outlet_templates, power_port_templates, rear_image, rear_port_templates, software_image_file_mappings, software_image_files, source_for_associations, static_group_association_set, subdevice_role, tagged_items, tags, u_height

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'power_ports' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, comments, console_port_templates, console_server_port_templates, created, destination_for_associations, device_bay_templates, device_family, device_family_id, devices, front_image, front_port_templates, id, interface_templates, is_full_depth, last_updated, manufacturer, manufacturer_id, model, module_bay_templates, part_number, power_outlet_templates, power_port_templates, rear_image, rear_port_templates, software_image_file_mappings, software_image_files, source_for_associations, static_group_association_set, subdevice_role, tagged_items, tags, u_height
```
</details>

### nautobot.dcim.tests.test_filters.FrontPortTestCase

<details><summary><code>available_for_cable</code> via <code>available_for_cable</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, rear_port, rear_port_id, rear_port_position, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, rear_port, rear_port_id, rear_port_position, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, rear_port, rear_port_id, rear_port_position, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, rear_port, rear_port_id, rear_port_position, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, rear_port, rear_port_id, rear_port_position, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, module, module_id, name, rear_port, rear_port_id, rear_port_position, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>location</code> via <code>device__location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for FrontPort field device__location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for FrontPort field device__location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for FrontPort field device__location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.InterfaceConnectionFilterSetTestCase

<details><summary><code>device</code> via <code>device</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: associated_data_compliance, associated_object_metadata, destination, destination_fans_out, destination_id, destination_type, destination_type_id, id, is_active, is_split, origin, origin_endpoint, origin_fans_out, origin_id, origin_type, origin_type_id, path, peer_connector

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: associated_data_compliance, associated_object_metadata, destination, destination_fans_out, destination_id, destination_type, destination_type_id, id, is_active, is_split, origin, origin_endpoint, origin_fans_out, origin_id, origin_type, origin_type_id, path, peer_connector
```
</details>

<details><summary><code>device_id</code> via <code>device_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device_id' into field. Choices are: associated_data_compliance, associated_object_metadata, destination, destination_fans_out, destination_id, destination_type, destination_type_id, id, is_active, is_split, origin, origin_endpoint, origin_fans_out, origin_id, origin_type, origin_type_id, path, peer_connector

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device_id' into field. Choices are: associated_data_compliance, associated_object_metadata, destination, destination_fans_out, destination_id, destination_type, destination_type_id, id, is_active, is_split, origin, origin_endpoint, origin_fans_out, origin_id, origin_type, origin_type_id, path, peer_connector
```
</details>

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: associated_data_compliance, associated_object_metadata, destination, destination_fans_out, destination_id, destination_type, destination_type_id, id, is_active, is_split, origin, origin_endpoint, origin_fans_out, origin_id, origin_type, origin_type_id, path, peer_connector

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: associated_data_compliance, associated_object_metadata, destination, destination_fans_out, destination_id, destination_type, destination_type_id, id, is_active, is_split, origin, origin_endpoint, origin_fans_out, origin_id, origin_type, origin_type_id, path, peer_connector
```
</details>

### nautobot.dcim.tests.test_filters.InterfaceRedundancyGroupTestCase

<details><summary><code>description</code> via <code>description</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for InterfaceRedundancyGroup field description. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>interfaces</code> via <code>interfaces</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for InterfaceRedundancyGroup field interfaces. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>interfaces</code> via <code>interfaces__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for InterfaceRedundancyGroup field interfaces__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>interfaces</code> via <code>interfaces__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for InterfaceRedundancyGroup field interfaces__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.InterfaceTestCase

<details><summary><code>interface_redundancy_groups</code> via <code>interface_redundancy_groups</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Interface field interface_redundancy_groups. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>interface_redundancy_groups</code> via <code>interface_redundancy_groups__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Interface field interface_redundancy_groups__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>interface_redundancy_groups</code> via <code>interface_redundancy_groups__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Interface field interface_redundancy_groups__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, breakout_position, bridge, bridge_id, bridged_interfaces, cable_paths, cable_termination, child_interfaces, created, description, destination_for_associations, device, device_id, duplex, enabled, id, interface_redundancy_group_associations, interface_redundancy_groups, ip_address_assignments, ip_addresses, label, lag, lag_id, last_updated, mac_address, member_interfaces, mgmt_only, mode, module, module_id, mtu, name, parent_interface, parent_interface_id, port_type, role, role_id, source_for_associations, speed, static_group_association_set, status, status_id, tagged_items, tagged_vlans, tags, type, untagged_vlan, untagged_vlan_id, virtual_device_context_assignments, virtual_device_contexts, vpn_terminations, vpn_tunnel_endpoints_src_int, vpn_tunnel_endpoints_tunnel, vrf, vrf_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, breakout_position, bridge, bridge_id, bridged_interfaces, cable_paths, cable_termination, child_interfaces, created, description, destination_for_associations, device, device_id, duplex, enabled, id, interface_redundancy_group_associations, interface_redundancy_groups, ip_address_assignments, ip_addresses, label, lag, lag_id, last_updated, mac_address, member_interfaces, mgmt_only, mode, module, module_id, mtu, name, parent_interface, parent_interface_id, port_type, role, role_id, source_for_associations, speed, static_group_association_set, status, status_id, tagged_items, tagged_vlans, tags, type, untagged_vlan, untagged_vlan_id, virtual_device_context_assignments, virtual_device_contexts, vpn_terminations, vpn_tunnel_endpoints_src_int, vpn_tunnel_endpoints_tunnel, vrf, vrf_id
```
</details>

<details><summary><code>location</code> via <code>device__location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Interface field device__location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Interface field device__location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Interface field device__location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.InterfaceVDCAssignmentTestCase

<details><summary><code>created</code> via <code>created</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, id, interface, interface_id, virtual_device_context, virtual_device_context_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, id, interface, interface_id, virtual_device_context, virtual_device_context_id
```
</details>

<details><summary><code>last_updated</code> via <code>last_updated</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, id, interface, interface_id, virtual_device_context, virtual_device_context_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, id, interface, interface_id, virtual_device_context, virtual_device_context_id
```
</details>

### nautobot.dcim.tests.test_filters.InventoryItemTestCase

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, asset_tag, associated_contacts, associated_data_compliance, associated_object_metadata, children, created, description, destination_for_associations, device, device_id, discovered, id, label, last_updated, manufacturer, manufacturer_id, name, parent, parent_id, part_id, serial, software_image_files, software_version, software_version_id, source_for_associations, static_group_association_set, tagged_items, tags

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, asset_tag, associated_contacts, associated_data_compliance, associated_object_metadata, children, created, description, destination_for_associations, device, device_id, discovered, id, label, last_updated, manufacturer, manufacturer_id, name, parent, parent_id, part_id, serial, software_image_files, software_version, software_version_id, source_for_associations, static_group_association_set, tagged_items, tags
```
</details>

<details><summary><code>location</code> via <code>device__location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for InventoryItem field device__location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for InventoryItem field device__location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for InventoryItem field device__location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.LocationTypeFilterSetTestCase

<details><summary><code>nestable</code> via <code>nestable</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for LocationType field nestable. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.ModuleBayTestCase

<details><summary><code>requires_first_party_modules</code> via <code>requires_first_party_modules</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ModuleBay field requires_first_party_modules. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.ModuleFamilyTestCase

<details><summary><code>module_bay_id</code> via <code>module_bay_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'module_bay_id' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, id, last_updated, module_bay_templates, module_bays, module_types, name, source_for_associations, static_group_association_set, tagged_items, tags

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'module_bay_id' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, id, last_updated, module_bay_templates, module_bays, module_types, name, source_for_associations, static_group_association_set, tagged_items, tags
```
</details>

<details><summary><code>module_bay_id</code> via <code>module_bay_id__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'module_bay_id' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, id, last_updated, module_bay_templates, module_bays, module_types, name, source_for_associations, static_group_association_set, tagged_items, tags
```
</details>

<details><summary><code>module_bay_id</code> via <code>module_bay_id__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'module_bay_id' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, id, last_updated, module_bay_templates, module_bays, module_types, name, source_for_associations, static_group_association_set, tagged_items, tags
```
</details>

### nautobot.dcim.tests.test_filters.ModuleTestCase

<details><summary><code>device</code> via <code>device</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _custom_field_data, asset_tag, associated_contacts, associated_data_compliance, associated_object_metadata, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, last_updated, location, location_id, module_bays, module_type, module_type_id, parent_module_bay, parent_module_bay_id, power_outlets, power_ports, rear_ports, role, role_id, serial, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _custom_field_data, asset_tag, associated_contacts, associated_data_compliance, associated_object_metadata, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, last_updated, location, location_id, module_bays, module_type, module_type_id, parent_module_bay, parent_module_bay_id, power_outlets, power_ports, rear_ports, role, role_id, serial, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id
```
</details>

<details><summary><code>device</code> via <code>device__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _custom_field_data, asset_tag, associated_contacts, associated_data_compliance, associated_object_metadata, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, last_updated, location, location_id, module_bays, module_type, module_type_id, parent_module_bay, parent_module_bay_id, power_outlets, power_ports, rear_ports, role, role_id, serial, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id
```
</details>

<details><summary><code>device</code> via <code>device__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _custom_field_data, asset_tag, associated_contacts, associated_data_compliance, associated_object_metadata, console_ports, console_server_ports, created, destination_for_associations, front_ports, id, interfaces, last_updated, location, location_id, module_bays, module_type, module_type_id, parent_module_bay, parent_module_bay_id, power_outlets, power_ports, rear_ports, role, role_id, serial, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id
```
</details>

### nautobot.dcim.tests.test_filters.PowerConnectionFilterSetTestCase

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, allocated_draw, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, maximum_draw, module, module_id, name, power_factor, power_outlets, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, allocated_draw, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, maximum_draw, module, module_id, name, power_factor, power_outlets, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

### nautobot.dcim.tests.test_filters.PowerFeedTestCase

<details><summary><code>available_for_cable</code> via <code>available_for_cable</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, amperage, associated_contacts, associated_data_compliance, associated_object_metadata, available_power, breaker_pole_count, breaker_position, cable_paths, cable_termination, comments, created, destination_for_associations, destination_panel, destination_panel_id, id, last_updated, max_utilization, name, phase, power_panel, power_panel_id, power_path, rack, rack_id, source_for_associations, static_group_association_set, status, status_id, supply, tagged_items, tags, type, voltage

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, amperage, associated_contacts, associated_data_compliance, associated_object_metadata, available_power, breaker_pole_count, breaker_position, cable_paths, cable_termination, comments, created, destination_for_associations, destination_panel, destination_panel_id, id, last_updated, max_utilization, name, phase, power_panel, power_panel_id, power_path, rack, rack_id, source_for_associations, static_group_association_set, status, status_id, supply, tagged_items, tags, type, voltage
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, amperage, associated_contacts, associated_data_compliance, associated_object_metadata, available_power, breaker_pole_count, breaker_position, cable_paths, cable_termination, comments, created, destination_for_associations, destination_panel, destination_panel_id, id, last_updated, max_utilization, name, phase, power_panel, power_panel_id, power_path, rack, rack_id, source_for_associations, static_group_association_set, status, status_id, supply, tagged_items, tags, type, voltage
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, amperage, associated_contacts, associated_data_compliance, associated_object_metadata, available_power, breaker_pole_count, breaker_position, cable_paths, cable_termination, comments, created, destination_for_associations, destination_panel, destination_panel_id, id, last_updated, max_utilization, name, phase, power_panel, power_panel_id, power_path, rack, rack_id, source_for_associations, static_group_association_set, status, status_id, supply, tagged_items, tags, type, voltage
```
</details>

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, amperage, associated_contacts, associated_data_compliance, associated_object_metadata, available_power, breaker_pole_count, breaker_position, cable_paths, cable_termination, comments, created, destination_for_associations, destination_panel, destination_panel_id, id, last_updated, max_utilization, name, phase, power_panel, power_panel_id, power_path, rack, rack_id, source_for_associations, static_group_association_set, status, status_id, supply, tagged_items, tags, type, voltage

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, amperage, associated_contacts, associated_data_compliance, associated_object_metadata, available_power, breaker_pole_count, breaker_position, cable_paths, cable_termination, comments, created, destination_for_associations, destination_panel, destination_panel_id, id, last_updated, max_utilization, name, phase, power_panel, power_panel_id, power_path, rack, rack_id, source_for_associations, static_group_association_set, status, status_id, supply, tagged_items, tags, type, voltage
```
</details>

<details><summary><code>location</code> via <code>power_panel__location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerFeed field power_panel__location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>power_panel__location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerFeed field power_panel__location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>power_panel__location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerFeed field power_panel__location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.PowerOutletTestCase

<details><summary><code>available_for_cable</code> via <code>available_for_cable</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, feed_leg, id, label, last_updated, module, module_id, name, power_port, power_port_id, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, feed_leg, id, label, last_updated, module, module_id, name, power_port, power_port_id, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, feed_leg, id, label, last_updated, module, module_id, name, power_port, power_port_id, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, feed_leg, id, label, last_updated, module, module_id, name, power_port, power_port_id, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, feed_leg, id, label, last_updated, module, module_id, name, power_port, power_port_id, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, feed_leg, id, label, last_updated, module, module_id, name, power_port, power_port_id, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>location</code> via <code>device__location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerOutlet field device__location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerOutlet field device__location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerOutlet field device__location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.PowerPanelTestCase

<details><summary><code>breaker_position_count</code> via <code>breaker_position_count</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerPanel field breaker_position_count. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerPanel field location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerPanel field location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerPanel field location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>panel_type</code> via <code>panel_type</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerPanel field panel_type. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>power_path</code> via <code>power_path</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerPanel field power_path. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.PowerPortTestCase

<details><summary><code>available_for_cable</code> via <code>available_for_cable</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, allocated_draw, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, maximum_draw, module, module_id, name, power_factor, power_outlets, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, allocated_draw, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, maximum_draw, module, module_id, name, power_factor, power_outlets, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, allocated_draw, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, maximum_draw, module, module_id, name, power_factor, power_outlets, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, allocated_draw, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, maximum_draw, module, module_id, name, power_factor, power_outlets, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, allocated_draw, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, maximum_draw, module, module_id, name, power_factor, power_outlets, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, allocated_draw, associated_contacts, associated_data_compliance, associated_object_metadata, cable_paths, cable_termination, created, description, destination_for_associations, device, device_id, id, label, last_updated, maximum_draw, module, module_id, name, power_factor, power_outlets, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>location</code> via <code>device__location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerPort field device__location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerPort field device__location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for PowerPort field device__location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.RackReservationTestCase

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, id, last_updated, rack, rack_id, source_for_associations, static_group_association_set, tagged_items, tags, tenant, tenant_id, units, user, user_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, id, last_updated, rack, rack_id, source_for_associations, static_group_association_set, tagged_items, tags, tenant, tenant_id, units, user, user_id
```
</details>

<details><summary><code>location</code> via <code>rack__location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for RackReservation field rack__location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>rack__location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for RackReservation field rack__location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>rack__location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for RackReservation field rack__location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.RackTestCase

<details><summary><code>location</code> via <code>location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Rack field location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Rack field location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Rack field location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.RearPortTestCase

<details><summary><code>available_for_cable</code> via <code>available_for_cable</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_termination, created, description, destination_for_associations, device, device_id, front_ports, id, label, last_updated, module, module_id, name, positions, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_termination, created, description, destination_for_associations, device, device_id, front_ports, id, label, last_updated, module, module_id, name, positions, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_termination, created, description, destination_for_associations, device, device_id, front_ports, id, label, last_updated, module, module_id, name, positions, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>available_for_cable</code> via <code>available_for_cable__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'available_for_cable' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_termination, created, description, destination_for_associations, device, device_id, front_ports, id, label, last_updated, module, module_id, name, positions, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>location</code> via <code>location</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_termination, created, description, destination_for_associations, device, device_id, front_ports, id, label, last_updated, module, module_id, name, positions, source_for_associations, static_group_association_set, tagged_items, tags, type

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'location' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, cable_termination, created, description, destination_for_associations, device, device_id, front_ports, id, label, last_updated, module, module_id, name, positions, source_for_associations, static_group_association_set, tagged_items, tags, type
```
</details>

<details><summary><code>location</code> via <code>device__location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for RearPort field device__location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for RearPort field device__location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>device__location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for RearPort field device__location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.dcim.tests.test_filters.VirtualChassisTestCase

<details><summary><code>tenant</code> via <code>tenant</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'tenant' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, destination_for_associations, domain, id, last_updated, master, master_id, members, name, source_for_associations, static_group_association_set, tagged_items, tags, virtual_servers

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'tenant' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, destination_for_associations, domain, id, last_updated, master, master_id, members, name, source_for_associations, static_group_association_set, tagged_items, tags, virtual_servers
```
</details>

<details><summary><code>tenant</code> via <code>master__tenant</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualChassis field master__tenant. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant</code> via <code>master__tenant__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualChassis field master__tenant__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant</code> via <code>master__tenant__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualChassis field master__tenant__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant_group</code> via <code>tenant_group</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'tenant_group' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, destination_for_associations, domain, id, last_updated, master, master_id, members, name, source_for_associations, static_group_association_set, tagged_items, tags, virtual_servers

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'tenant_group' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, destination_for_associations, domain, id, last_updated, master, master_id, members, name, source_for_associations, static_group_association_set, tagged_items, tags, virtual_servers
```
</details>

<details><summary><code>tenant_group</code> via <code>master__tenant__tenant_group</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualChassis field master__tenant__tenant_group. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant_group</code> via <code>master__tenant__tenant_group__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualChassis field master__tenant__tenant_group__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tenant_group</code> via <code>master__tenant__tenant_group__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualChassis field master__tenant__tenant_group__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.extras.tests.test_dynamicgroups.DynamicGroupFilterTest

<details><summary><code>ancestors</code> via <code>ancestors</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints
```
</details>

<details><summary><code>ancestors</code> via <code>ancestors__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints
```
</details>

<details><summary><code>ancestors</code> via <code>ancestors__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints
```
</details>

<details><summary><code>descendants</code> via <code>descendants</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints
```
</details>

<details><summary><code>descendants</code> via <code>descendants__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints
```
</details>

<details><summary><code>descendants</code> via <code>descendants__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints
```
</details>

### nautobot.extras.tests.test_dynamicgroups.DynamicGroupMembershipFilterTest

<details><summary><code>created</code> via <code>created</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, group, group_id, id, operator, parent_group, parent_group_id, weight

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, group, group_id, id, operator, parent_group, parent_group_id, weight
```
</details>

<details><summary><code>last_updated</code> via <code>last_updated</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, group, group_id, id, operator, parent_group, parent_group_id, weight

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, group, group_id, id, operator, parent_group, parent_group_id, weight
```
</details>

### nautobot.extras.tests.test_filters.ApprovalWorkflowDefinitionFilterTestCase

<details><summary><code>model_constraints</code> via <code>model_constraints</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ApprovalWorkflowDefinition field model_constraints. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.extras.tests.test_filters.ApprovalWorkflowFilterTestCase

<details><summary><code>decision_date</code> via <code>decision_date</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ApprovalWorkflow field decision_date. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>user</code> via <code>user</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ApprovalWorkflow field user. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>user</code> via <code>user__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ApprovalWorkflow field user__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>user</code> via <code>user__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1931, in transform
    return self.try_transform(wrapped, name)
           ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1460, in try_transform
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Unsupported lookup 'name' for UUIDField or join on the field not permitted.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2267, in add_fields
    cols.append(join_info.transform_function(targets[0], final_alias))
                ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1935, in transform
    raise last_field_exception
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'name' into field. Choices are: approval_workflow_stage_responses, approval_workflows, associated_data_compliance, associated_object_metadata, config_data, date_joined, default_saved_views, email, first_name, groups, id, is_active, is_staff, is_superuser, last_login, last_name, logentry, notes, object_changes, object_permissions, password, rack_reservations, saved_view_assignments, savedview, social_auth, terminated_job_results, tokens, user_permissions, username
```
</details>

<details><summary><code>user_name</code> via <code>user_name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ApprovalWorkflow field user_name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.extras.tests.test_filters.ApprovalWorkflowStageDefinitionFilterTestCase

<details><summary><code>approval_workflow</code> via <code>approval_workflow</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'approval_workflow' into field. Choices are: _custom_field_data, approval_workflow_definition, approval_workflow_definition_id, approval_workflow_stages, approver_group, approver_group_id, associated_contacts, associated_data_compliance, associated_object_metadata, created, denial_message, destination_for_associations, id, last_updated, min_approvers, name, sequence, source_for_associations, static_group_association_set

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'approval_workflow' into field. Choices are: _custom_field_data, approval_workflow_definition, approval_workflow_definition_id, approval_workflow_stages, approver_group, approver_group_id, associated_contacts, associated_data_compliance, associated_object_metadata, created, denial_message, destination_for_associations, id, last_updated, min_approvers, name, sequence, source_for_associations, static_group_association_set
```
</details>

<details><summary><code>approval_workflow</code> via <code>approval_workflow__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'approval_workflow' into field. Choices are: _custom_field_data, approval_workflow_definition, approval_workflow_definition_id, approval_workflow_stages, approver_group, approver_group_id, associated_contacts, associated_data_compliance, associated_object_metadata, created, denial_message, destination_for_associations, id, last_updated, min_approvers, name, sequence, source_for_associations, static_group_association_set
```
</details>

<details><summary><code>approval_workflow</code> via <code>approval_workflow__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'approval_workflow' into field. Choices are: _custom_field_data, approval_workflow_definition, approval_workflow_definition_id, approval_workflow_stages, approver_group, approver_group_id, associated_contacts, associated_data_compliance, associated_object_metadata, created, denial_message, destination_for_associations, id, last_updated, min_approvers, name, sequence, source_for_associations, static_group_association_set
```
</details>

### nautobot.extras.tests.test_filters.ApprovalWorkflowStageFilterTestCase

<details><summary><code>decision_date_day</code> via <code>decision_date_day</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'decision_date_day' into field. Choices are: _custom_field_data, approval_workflow, approval_workflow_id, approval_workflow_stage_definition, approval_workflow_stage_definition_id, approval_workflow_stage_responses, associated_contacts, associated_data_compliance, associated_object_metadata, created, decision_date, destination_for_associations, id, last_updated, source_for_associations, state, static_group_association_set

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'decision_date_day' into field. Choices are: _custom_field_data, approval_workflow, approval_workflow_id, approval_workflow_stage_definition, approval_workflow_stage_definition_id, approval_workflow_stage_responses, associated_contacts, associated_data_compliance, associated_object_metadata, created, decision_date, destination_for_associations, id, last_updated, source_for_associations, state, static_group_association_set
```
</details>

<details><summary><code>decision_date_day</code> via <code>decision_date</code>: ERROR AttributeError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 81, in test_probe_untested_filters
    self.assertTrue(fs.is_valid(), fs.errors.as_text())
                    ~~~~~~~~~~~^^
  File "/source/nautobot/core/filters.py", line 1152, in is_valid
    self._is_valid = super().is_valid()
                     ~~~~~~~~~~~~~~~~^^
  File "/usr/local/lib/python3.13/site-packages/django_filters/filterset.py", line 215, in is_valid
    return self.is_bound and self.form.is_valid()
                             ~~~~~~~~~~~~~~~~~~^^
  File "/usr/local/lib/python3.13/site-packages/django/forms/forms.py", line 206, in is_valid
    return self.is_bound and not self.errors
                                 ^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/forms/forms.py", line 201, in errors
    self.full_clean()
    ~~~~~~~~~~~~~~~^^
  File "/usr/local/lib/python3.13/site-packages/django/forms/forms.py", line 337, in full_clean
    self._clean_fields()
    ~~~~~~~~~~~~~~~~~~^^
  File "/usr/local/lib/python3.13/site-packages/django/forms/forms.py", line 345, in _clean_fields
    self.cleaned_data[name] = field._clean_bound_field(bf)
                              ~~~~~~~~~~~~~~~~~~~~~~~~^^^^
  File "/usr/local/lib/python3.13/site-packages/django/forms/fields.py", line 272, in _clean_bound_field
    return self.clean(value)
           ~~~~~~~~~~^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/forms/fields.py", line 207, in clean
    value = self.to_python(value)
  File "/usr/local/lib/python3.13/site-packages/django/forms/fields.py", line 499, in to_python
    return super().to_python(value)
           ~~~~~~~~~~~~~~~~~^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/forms/fields.py", line 468, in to_python
    value = value.strip()
            ^^^^^^^^^^^
AttributeError: 'list' object has no attribute 'strip'
```
</details>

### nautobot.extras.tests.test_filters.ComputedFieldTestCase

<details><summary><code>grouping</code> via <code>grouping</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ComputedField field grouping. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.extras.tests.test_filters.ConfigContextTestCase

<details><summary><code>device_redundancy_group</code> via <code>device_redundancy_group</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device_redundancy_group' into field. Choices are: associated_contacts, associated_data_compliance, associated_object_metadata, cluster_groups, clusters, config_context_schema, config_context_schema_id, created, data, description, device_families, device_redundancy_groups, device_types, dynamic_groups, id, is_active, last_updated, locations, name, owner, owner_content_type, owner_content_type_id, owner_object_id, platforms, roles, tags, tenant_groups, tenants, weight

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device_redundancy_group' into field. Choices are: associated_contacts, associated_data_compliance, associated_object_metadata, cluster_groups, clusters, config_context_schema, config_context_schema_id, created, data, description, device_families, device_redundancy_groups, device_types, dynamic_groups, id, is_active, last_updated, locations, name, owner, owner_content_type, owner_content_type_id, owner_object_id, platforms, roles, tags, tenant_groups, tenants, weight
```
</details>

<details><summary><code>device_redundancy_group</code> via <code>device_redundancy_groups</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConfigContext field device_redundancy_groups. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>device_redundancy_group</code> via <code>device_redundancy_groups__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConfigContext field device_redundancy_groups__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>device_redundancy_group</code> via <code>device_redundancy_groups__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConfigContext field device_redundancy_groups__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>owner_content_type</code> via <code>owner_content_type</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConfigContext field owner_content_type. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>owner_object_id</code> via <code>owner_object_id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConfigContext field owner_object_id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>schema</code> via <code>schema</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'schema' into field. Choices are: associated_contacts, associated_data_compliance, associated_object_metadata, cluster_groups, clusters, config_context_schema, config_context_schema_id, created, data, description, device_families, device_redundancy_groups, device_types, dynamic_groups, id, is_active, last_updated, locations, name, owner, owner_content_type, owner_content_type_id, owner_object_id, platforms, roles, tags, tenant_groups, tenants, weight

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'schema' into field. Choices are: associated_contacts, associated_data_compliance, associated_object_metadata, cluster_groups, clusters, config_context_schema, config_context_schema_id, created, data, description, device_families, device_redundancy_groups, device_types, dynamic_groups, id, is_active, last_updated, locations, name, owner, owner_content_type, owner_content_type_id, owner_object_id, platforms, roles, tags, tenant_groups, tenants, weight
```
</details>

<details><summary><code>schema</code> via <code>config_context_schema</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConfigContext field config_context_schema. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>schema</code> via <code>config_context_schema__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConfigContext field config_context_schema__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>schema</code> via <code>config_context_schema__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConfigContext field config_context_schema__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tag</code> via <code>tag</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'tag' into field. Choices are: associated_contacts, associated_data_compliance, associated_object_metadata, cluster_groups, clusters, config_context_schema, config_context_schema_id, created, data, description, device_families, device_redundancy_groups, device_types, dynamic_groups, id, is_active, last_updated, locations, name, owner, owner_content_type, owner_content_type_id, owner_object_id, platforms, roles, tags, tenant_groups, tenants, weight

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'tag' into field. Choices are: associated_contacts, associated_data_compliance, associated_object_metadata, cluster_groups, clusters, config_context_schema, config_context_schema_id, created, data, description, device_families, device_redundancy_groups, device_types, dynamic_groups, id, is_active, last_updated, locations, name, owner, owner_content_type, owner_content_type_id, owner_object_id, platforms, roles, tags, tenant_groups, tenants, weight
```
</details>

<details><summary><code>tag</code> via <code>tags</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConfigContext field tags. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tag</code> via <code>tags__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConfigContext field tags__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tag</code> via <code>tags__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ConfigContext field tags__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.extras.tests.test_filters.ContentTypeFilterSetTestCase

<details><summary><code>feature</code> via <code>feature</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'feature' into field. Choices are: app_label, cloud_resource_types, computed_fields, config_context_schemas, config_contexts, custom_fields, custom_links, datacompliance, destination_relationships, devices, dynamic_groups, export_template_owners, export_templates, extras_taggeditem_tagged_items, graphql_queries, id, image_attachments, job_buttons, job_hooks, location_types, logentry, metadata_types, minmaxvalidationrule, model, notes, object_permissions, permission, regularexpressionvalidationrule, requiredvalidationrule, roles, source_relationships, static_group_associations, statuses, taggit_taggeditem_tagged_items, tags, uniquevalidationrule, virtual_machines, webhooks

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'feature' into field. Choices are: app_label, cloud_resource_types, computed_fields, config_context_schemas, config_contexts, custom_fields, custom_links, datacompliance, destination_relationships, devices, dynamic_groups, export_template_owners, export_templates, extras_taggeditem_tagged_items, graphql_queries, id, image_attachments, job_buttons, job_hooks, location_types, logentry, metadata_types, minmaxvalidationrule, model, notes, object_permissions, permission, regularexpressionvalidationrule, requiredvalidationrule, roles, source_relationships, static_group_associations, statuses, taggit_taggeditem_tagged_items, tags, uniquevalidationrule, virtual_machines, webhooks
```
</details>

<details><summary><code>has_serializer</code> via <code>has_serializer</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'has_serializer' into field. Choices are: app_label, cloud_resource_types, computed_fields, config_context_schemas, config_contexts, custom_fields, custom_links, datacompliance, destination_relationships, devices, dynamic_groups, export_template_owners, export_templates, extras_taggeditem_tagged_items, graphql_queries, id, image_attachments, job_buttons, job_hooks, location_types, logentry, metadata_types, minmaxvalidationrule, model, notes, object_permissions, permission, regularexpressionvalidationrule, requiredvalidationrule, roles, source_relationships, static_group_associations, statuses, taggit_taggeditem_tagged_items, tags, uniquevalidationrule, virtual_machines, webhooks

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'has_serializer' into field. Choices are: app_label, cloud_resource_types, computed_fields, config_context_schemas, config_contexts, custom_fields, custom_links, datacompliance, destination_relationships, devices, dynamic_groups, export_template_owners, export_templates, extras_taggeditem_tagged_items, graphql_queries, id, image_attachments, job_buttons, job_hooks, location_types, logentry, metadata_types, minmaxvalidationrule, model, notes, object_permissions, permission, regularexpressionvalidationrule, requiredvalidationrule, roles, source_relationships, static_group_associations, statuses, taggit_taggeditem_tagged_items, tags, uniquevalidationrule, virtual_machines, webhooks
```
</details>

### nautobot.extras.tests.test_filters.CustomLinkTestCase

<details><summary><code>button_class</code> via <code>button_class</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for CustomLink field button_class. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>content_type</code> via <code>content_type</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for CustomLink field content_type. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>group_name</code> via <code>group_name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for CustomLink field group_name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>new_window</code> via <code>new_window</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for CustomLink field new_window. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.extras.tests.test_filters.DynamicGroupFilterSetTestCase

<details><summary><code>ancestors</code> via <code>ancestors</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints
```
</details>

<details><summary><code>ancestors</code> via <code>ancestors__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints
```
</details>

<details><summary><code>ancestors</code> via <code>ancestors__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'ancestors' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints
```
</details>

<details><summary><code>content_type</code> via <code>content_type</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 81, in test_probe_untested_filters
    self.assertTrue(fs.is_valid(), fs.errors.as_text())
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 744, in assertTrue
    raise self.failureException(msg)
AssertionError: False is not true : * content_type
  * Select a valid choice. 148 is not one of the available choices.
```
</details>

<details><summary><code>descendants</code> via <code>descendants</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints
```
</details>

<details><summary><code>descendants</code> via <code>descendants__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints
```
</details>

<details><summary><code>descendants</code> via <code>descendants__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'descendants' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, children, content_type, content_type_id, created, description, destination_for_associations, dynamic_group_memberships, filter, group_type, id, last_updated, name, parents, source_for_associations, static_group_association_set, static_group_associations, tagged_items, tags, tenant, tenant_id, vpn_tunnel_endpoints
```
</details>

### nautobot.extras.tests.test_filters.ExportTemplateTestCase

<details><summary><code>owner_content_type</code> via <code>owner_content_type</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ExportTemplate field owner_content_type. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>owner_object_id</code> via <code>owner_object_id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ExportTemplate field owner_object_id. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.extras.tests.test_filters.ExternalIntegrationTestCase

<details><summary><code>extra_config</code> via <code>extra_config</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 84, in test_probe_untested_filters
    self.assertQuerySetEqualAndNotEmpty(filterset_result, qs_result, ordered=False)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/source/nautobot/core/testing/mixins.py", line 302, in assertQuerySetEqualAndNotEmpty
    self.assertNotEqual(len(qs), 0, "QuerySet cannot be empty")
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 916, in assertNotEqual
    raise self.failureException(msg)
AssertionError: 0 == 0 : QuerySet cannot be empty
```
</details>

<details><summary><code>headers</code> via <code>headers</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 84, in test_probe_untested_filters
    self.assertQuerySetEqualAndNotEmpty(filterset_result, qs_result, ordered=False)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/source/nautobot/core/testing/mixins.py", line 302, in assertQuerySetEqualAndNotEmpty
    self.assertNotEqual(len(qs), 0, "QuerySet cannot be empty")
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 916, in assertNotEqual
    raise self.failureException(msg)
AssertionError: 0 == 0 : QuerySet cannot be empty
```
</details>

### nautobot.extras.tests.test_filters.ImageAttachmentTestCase

<details><summary><code>content_type_id</code> via <code>content_type_id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ImageAttachment field content_type_id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>content_type_id</code> via <code>content_type_id__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for ImageAttachment field content_type_id__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>content_type_id</code> via <code>content_type_id__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1931, in transform
    return self.try_transform(wrapped, name)
           ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1460, in try_transform
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Unsupported lookup 'name' for AutoField or join on the field not permitted.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2267, in add_fields
    cols.append(join_info.transform_function(targets[0], final_alias))
                ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1935, in transform
    raise last_field_exception
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'name' into field. Choices are: app_label, cloud_resource_types, computed_fields, config_context_schemas, config_contexts, custom_fields, custom_links, datacompliance, destination_relationships, devices, dynamic_groups, export_template_owners, export_templates, extras_taggeditem_tagged_items, graphql_queries, id, image_attachments, job_buttons, job_hooks, location_types, logentry, metadata_types, minmaxvalidationrule, model, notes, object_permissions, permission, regularexpressionvalidationrule, requiredvalidationrule, roles, source_relationships, static_group_associations, statuses, taggit_taggeditem_tagged_items, tags, uniquevalidationrule, virtual_machines, webhooks
```
</details>

### nautobot.extras.tests.test_filters.JobButtonFilterTestCase

<details><summary><code>button_class</code> via <code>button_class</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for JobButton field button_class. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>confirmation</code> via <code>confirmation</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for JobButton field confirmation. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>content_types</code> via <code>content_types</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for JobButton field content_types. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>enabled</code> via <code>enabled</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for JobButton field enabled. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>group_name</code> via <code>group_name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for JobButton field group_name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.extras.tests.test_filters.JobFilterSetTestCase

<details><summary><code>console_log_default</code> via <code>console_log_default</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field console_log_default. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>console_log_default_override</code> via <code>console_log_default_override</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field console_log_default_override. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>description_override</code> via <code>description_override</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field description_override. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>dryrun_default_override</code> via <code>dryrun_default_override</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field dryrun_default_override. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>grouping_override</code> via <code>grouping_override</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field grouping_override. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>has_sensitive_variables</code> via <code>has_sensitive_variables</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field has_sensitive_variables. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>has_sensitive_variables_override</code> via <code>has_sensitive_variables_override</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field has_sensitive_variables_override. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>hidden_override</code> via <code>hidden_override</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field hidden_override. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>is_job_button_receiver</code> via <code>is_job_button_receiver</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field is_job_button_receiver. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>is_singleton</code> via <code>is_singleton</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field is_singleton. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>is_singleton_override</code> via <code>is_singleton_override</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field is_singleton_override. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>name_override</code> via <code>name_override</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field name_override. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>soft_time_limit_override</code> via <code>soft_time_limit_override</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field soft_time_limit_override. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>time_limit_override</code> via <code>time_limit_override</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Job field time_limit_override. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.extras.tests.test_filters.JobResultFilterSetTestCase

<details><summary><code>canceled_by</code> via <code>canceled_by</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for JobResult field canceled_by. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>canceled_by</code> via <code>canceled_by__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for JobResult field canceled_by__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>canceled_by</code> via <code>canceled_by__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1931, in transform
    return self.try_transform(wrapped, name)
           ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1460, in try_transform
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Unsupported lookup 'name' for UUIDField or join on the field not permitted.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2267, in add_fields
    cols.append(join_info.transform_function(targets[0], final_alias))
                ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1935, in transform
    raise last_field_exception
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'name' into field. Choices are: approval_workflow_stage_responses, approval_workflows, associated_data_compliance, associated_object_metadata, config_data, date_joined, default_saved_views, email, first_name, groups, id, is_active, is_staff, is_superuser, last_login, last_name, logentry, notes, object_changes, object_permissions, password, rack_reservations, saved_view_assignments, savedview, social_auth, terminated_job_results, tokens, user_permissions, username
```
</details>

<details><summary><code>date_canceled</code> via <code>date_canceled</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for JobResult field date_canceled. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.extras.tests.test_filters.ObjectMetadataTestCase

<details><summary><code>scoped_fields</code> via <code>scoped_fields</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 83, in test_probe_untested_filters
    qs_result = self.queryset.filter(**{f"{field_name}__in": test_data}).distinct()
                ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/source/nautobot/core/models/querysets.py", line 100, in filter
    return super().filter(*args, **self.split_composite_key_into_kwargs(composite_key, **kwargs))
           ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1495, in filter
    return self._filter_or_exclude(False, args, kwargs)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1513, in _filter_or_exclude
    clone._filter_or_exclude_inplace(negate, args, kwargs)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1523, in _filter_or_exclude_inplace
    self._query.add_q(Q(*args, **kwargs))
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1648, in add_q
    clause, _ = self._add_q(q_object, can_reuse)
                ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1680, in _add_q
    child_clause, needed_inner = self.build_filter(
                                 ~~~~~~~~~~~~~~~~~^
        child,
        ^^^^^^
    ...<7 lines>...
        update_join_types=update_join_types,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1590, in build_filter
    condition = self.build_lookup(lookups, col, value)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1417, in build_lookup
    lookup = lookup_class(lhs, rhs)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/lookups.py", line 38, in __init__
    self.rhs = self.get_prep_lookup()
               ~~~~~~~~~~~~~~~~~~~~^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/lookups.py", line 536, in get_prep_lookup
    return super().get_prep_lookup()
           ~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/lookups.py", line 321, in get_prep_lookup
    rhs_value = self.lhs.output_field.get_prep_value(rhs_value)
  File "/source/nautobot/core/models/fields.py", line 310, in get_prep_value
    raise ValueError(f"value {value} is not list or tuple")
ValueError: value ['speed', 'module', 'associated_object_metadata', 'breakout_position', 'bridge', 'type', 'cable_paths', 'bridged_interfaces', 'member_interfaces', 'parent_interface', 'port_type', 'destination_for_associations', 'interface_redundancy_groups', 'mtu'] is not list or tuple
```
</details>

<details><summary><code>value</code> via <code>value</code>: ERROR FieldError</summary>

```
hqlquery, associated_object_metadata_extras_healthchecktestmodel, associated_object_metadata_extras_imageattachment, associated_object_metadata_extras_job, associated_object_metadata_extras_jobbutton, associated_object_metadata_extras_jobconsoleentry, associated_object_metadata_extras_jobhook, associated_object_metadata_extras_joblogentry, associated_object_metadata_extras_jobqueue, associated_object_metadata_extras_jobqueueassignment, associated_object_metadata_extras_jobresult, associated_object_metadata_extras_metadatachoice, associated_object_metadata_extras_metadatatype, associated_object_metadata_extras_note, associated_object_metadata_extras_objectchange, associated_object_metadata_extras_objectmetadata, associated_object_metadata_extras_relationship, associated_object_metadata_extras_relationshipassociation, associated_object_metadata_extras_role, associated_object_metadata_extras_savedview, associated_object_metadata_extras_scheduledjob, associated_object_metadata_extras_secret, associated_object_metadata_extras_secretsgroup, associated_object_metadata_extras_secretsgroupassociation, associated_object_metadata_extras_staticgroupassociation, associated_object_metadata_extras_status, associated_object_metadata_extras_tag, associated_object_metadata_extras_taggeditem, associated_object_metadata_extras_team, associated_object_metadata_extras_usersavedviewassociation, associated_object_metadata_extras_webhook, associated_object_metadata_ipam_ipaddress, associated_object_metadata_ipam_ipaddressrange, associated_object_metadata_ipam_ipaddresstointerface, associated_object_metadata_ipam_namespace, associated_object_metadata_ipam_prefix, associated_object_metadata_ipam_prefixlocationassignment, associated_object_metadata_ipam_rir, associated_object_metadata_ipam_routetarget, associated_object_metadata_ipam_service, associated_object_metadata_ipam_vlan, associated_object_metadata_ipam_vlangroup, associated_object_metadata_ipam_vlanlocationassignment, associated_object_metadata_ipam_vrf, associated_object_metadata_ipam_vrfdeviceassignment, associated_object_metadata_ipam_vrfprefixassignment, associated_object_metadata_load_balancers_certificateprofile, associated_object_metadata_load_balancers_healthcheckmonitor, associated_object_metadata_load_balancers_loadbalancerpool, associated_object_metadata_load_balancers_loadbalancerpoolmember, associated_object_metadata_load_balancers_loadbalancerpoolmembercertificateprofileassignment, associated_object_metadata_load_balancers_virtualserver, associated_object_metadata_load_balancers_virtualservercertificateprofileassignment, associated_object_metadata_tenancy_tenant, associated_object_metadata_tenancy_tenantgroup, associated_object_metadata_users_objectpermission, associated_object_metadata_users_token, associated_object_metadata_users_user, associated_object_metadata_virtualization_cluster, associated_object_metadata_virtualization_clustergroup, associated_object_metadata_virtualization_clustertype, associated_object_metadata_virtualization_virtualmachine, associated_object_metadata_virtualization_vminterface, associated_object_metadata_vpn_vpn, associated_object_metadata_vpn_vpnphase1policy, associated_object_metadata_vpn_vpnphase2policy, associated_object_metadata_vpn_vpnprofile, associated_object_metadata_vpn_vpnprofilephase1policyassignment, associated_object_metadata_vpn_vpnprofilephase2policyassignment, associated_object_metadata_vpn_vpntermination, associated_object_metadata_vpn_vpntunnel, associated_object_metadata_vpn_vpntunnelendpoint, associated_object_metadata_wireless_controllermanageddevicegroupradioprofileassignment, associated_object_metadata_wireless_controllermanageddevicegroupwirelessnetworkassignment, associated_object_metadata_wireless_radioprofile, associated_object_metadata_wireless_supporteddatarate, associated_object_metadata_wireless_wirelessnetwork, contact, contact_id, created, id, last_updated, metadata_type, metadata_type_id, scoped_fields, team, team_id
```
</details>

<details><summary><code>value</code> via <code>_value</code>: ERROR AttributeError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 82, in test_probe_untested_filters
    filterset_result = fs.qs
                       ^^^^^
  File "/usr/local/lib/python3.13/site-packages/django_filters/filterset.py", line 250, in qs
    qs = self.filter_queryset(qs)
  File "/usr/local/lib/python3.13/site-packages/django_filters/filterset.py", line 233, in filter_queryset
    queryset = self.filters[name].filter(queryset, value)
  File "/usr/local/lib/python3.13/site-packages/django_filters/filters.py", line 834, in __call__
    return self.method(qs, self.f.field_name, value)
           ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/source/nautobot/extras/filters.py", line 1413, in filter_value
    value = value.strip()
            ^^^^^^^^^^^
AttributeError: 'list' object has no attribute 'strip'
```
</details>

### nautobot.extras.tests.test_filters.SecretsGroupTestCase

<details><summary><code>secrets</code> via <code>secrets</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for SecretsGroup field secrets. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>secrets</code> via <code>secrets__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for SecretsGroup field secrets__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>secrets</code> via <code>secrets__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for SecretsGroup field secrets__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.extras.tests.test_filters.WebhookTestCase

<details><summary><code>content_types</code> via <code>content_types</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Webhook field content_types. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>type_create</code> via <code>type_create</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Webhook field type_create. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>type_delete</code> via <code>type_delete</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Webhook field type_delete. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>type_update</code> via <code>type_update</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Webhook field type_update. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.ipam.tests.test_filters.IPAddressTestCase

<details><summary><code>address</code> via <code>address</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'address' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, dns_name, host, id, interface_assignments, interface_redundancy_groups, interfaces, ip4_vdcs, ip6_vdcs, ip_version, last_updated, load_balancer_pool_members, mask_length, nat_inside, nat_inside_id, nat_outside_list, parent, parent_id, primary_ip4_for, primary_ip6_for, role, role_id, services, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vm_interfaces, vpn_tunnel_endpoints_src_ip

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'address' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, dns_name, host, id, interface_assignments, interface_redundancy_groups, interfaces, ip4_vdcs, ip6_vdcs, ip_version, last_updated, load_balancer_pool_members, mask_length, nat_inside, nat_inside_id, nat_outside_list, parent, parent_id, primary_ip4_for, primary_ip6_for, role, role_id, services, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vm_interfaces, vpn_tunnel_endpoints_src_ip
```
</details>

<details><summary><code>device_id</code> via <code>device_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device_id' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, dns_name, host, id, interface_assignments, interface_redundancy_groups, interfaces, ip4_vdcs, ip6_vdcs, ip_version, last_updated, load_balancer_pool_members, mask_length, nat_inside, nat_inside_id, nat_outside_list, parent, parent_id, primary_ip4_for, primary_ip6_for, role, role_id, services, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vm_interfaces, vpn_tunnel_endpoints_src_ip

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device_id' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, dns_name, host, id, interface_assignments, interface_redundancy_groups, interfaces, ip4_vdcs, ip6_vdcs, ip_version, last_updated, load_balancer_pool_members, mask_length, nat_inside, nat_inside_id, nat_outside_list, parent, parent_id, primary_ip4_for, primary_ip6_for, role, role_id, services, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vm_interfaces, vpn_tunnel_endpoints_src_ip
```
</details>

<details><summary><code>device_id</code> via <code>pk</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 84, in test_probe_untested_filters
    self.assertQuerySetEqualAndNotEmpty(filterset_result, qs_result, ordered=False)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/source/nautobot/core/testing/mixins.py", line 302, in assertQuerySetEqualAndNotEmpty
    self.assertNotEqual(len(qs), 0, "QuerySet cannot be empty")
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 916, in assertNotEqual
    raise self.failureException(msg)
AssertionError: 0 == 0 : QuerySet cannot be empty
```
</details>

<details><summary><code>present_in_vrf_id</code> via <code>present_in_vrf_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'present_in_vrf_id' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, dns_name, host, id, interface_assignments, interface_redundancy_groups, interfaces, ip4_vdcs, ip6_vdcs, ip_version, last_updated, load_balancer_pool_members, mask_length, nat_inside, nat_inside_id, nat_outside_list, parent, parent_id, primary_ip4_for, primary_ip6_for, role, role_id, services, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vm_interfaces, vpn_tunnel_endpoints_src_ip

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'present_in_vrf_id' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, dns_name, host, id, interface_assignments, interface_redundancy_groups, interfaces, ip4_vdcs, ip6_vdcs, ip_version, last_updated, load_balancer_pool_members, mask_length, nat_inside, nat_inside_id, nat_outside_list, parent, parent_id, primary_ip4_for, primary_ip6_for, role, role_id, services, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vm_interfaces, vpn_tunnel_endpoints_src_ip
```
</details>

<details><summary><code>present_in_vrf_id</code> via <code>parent__vrfs</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 81, in test_probe_untested_filters
    self.assertTrue(fs.is_valid(), fs.errors.as_text())
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 744, in assertTrue
    raise self.failureException(msg)
AssertionError: False is not true : * present_in_vrf_id
  * “[&#x27;2e868722-577a-4dc2-894a-f1cc402449c8&#x27;, &#x27;a1211f17-baed-4447-88b7-96b67239cd5d&#x27;, &#x27;aa11a17f-f9fe-457d-9431-a3ce2e43a117&#x27;, &#x27;79539e1e-5fa2-4dde-adc3-6936e24faa18&#x27;]” is not a valid UUID.
```
</details>

<details><summary><code>present_in_vrf_id</code> via <code>parent__vrfs__id</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 81, in test_probe_untested_filters
    self.assertTrue(fs.is_valid(), fs.errors.as_text())
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 744, in assertTrue
    raise self.failureException(msg)
AssertionError: False is not true : * present_in_vrf_id
  * “[&#x27;2e868722-577a-4dc2-894a-f1cc402449c8&#x27;, &#x27;a1211f17-baed-4447-88b7-96b67239cd5d&#x27;, &#x27;aa11a17f-f9fe-457d-9431-a3ce2e43a117&#x27;]” is not a valid UUID.
```
</details>

<details><summary><code>present_in_vrf_id</code> via <code>parent__vrfs__name</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 81, in test_probe_untested_filters
    self.assertTrue(fs.is_valid(), fs.errors.as_text())
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 744, in assertTrue
    raise self.failureException(msg)
AssertionError: False is not true : * present_in_vrf_id
  * “[&#x27;SlateBlue4026&#x27;, &#x27;SlateGray7384&#x27;, &#x27;PaleTurquoise9499&#x27;, &#x27;MediumBlue6215&#x27;, &#x27;SlateBlue1031&#x27;]” is not a valid UUID.
```
</details>

<details><summary><code>type</code> via <code>type</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for IPAddress field type. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>virtual_machine_id</code> via <code>virtual_machine_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'virtual_machine_id' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, dns_name, host, id, interface_assignments, interface_redundancy_groups, interfaces, ip4_vdcs, ip6_vdcs, ip_version, last_updated, load_balancer_pool_members, mask_length, nat_inside, nat_inside_id, nat_outside_list, parent, parent_id, primary_ip4_for, primary_ip6_for, role, role_id, services, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vm_interfaces, vpn_tunnel_endpoints_src_ip

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'virtual_machine_id' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, dns_name, host, id, interface_assignments, interface_redundancy_groups, interfaces, ip4_vdcs, ip6_vdcs, ip_version, last_updated, load_balancer_pool_members, mask_length, nat_inside, nat_inside_id, nat_outside_list, parent, parent_id, primary_ip4_for, primary_ip6_for, role, role_id, services, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vm_interfaces, vpn_tunnel_endpoints_src_ip
```
</details>

<details><summary><code>virtual_machine_id</code> via <code>pk</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 84, in test_probe_untested_filters
    self.assertQuerySetEqualAndNotEmpty(filterset_result, qs_result, ordered=False)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/source/nautobot/core/testing/mixins.py", line 302, in assertQuerySetEqualAndNotEmpty
    self.assertNotEqual(len(qs), 0, "QuerySet cannot be empty")
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 916, in assertNotEqual
    raise self.failureException(msg)
AssertionError: 0 == 0 : QuerySet cannot be empty
```
</details>

### nautobot.ipam.tests.test_filters.IPAddressToInterfaceTestCase

<details><summary><code>created</code> via <code>created</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, id, interface, interface_id, ip_address, ip_address_id, is_default, is_destination, is_preferred, is_primary, is_secondary, is_source, is_standby, vm_interface, vm_interface_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, id, interface, interface_id, ip_address, ip_address_id, is_default, is_destination, is_preferred, is_primary, is_secondary, is_source, is_standby, vm_interface, vm_interface_id
```
</details>

<details><summary><code>is_default</code> via <code>is_default</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for IPAddressToInterface field is_default. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>is_destination</code> via <code>is_destination</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for IPAddressToInterface field is_destination. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>is_preferred</code> via <code>is_preferred</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for IPAddressToInterface field is_preferred. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>is_primary</code> via <code>is_primary</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for IPAddressToInterface field is_primary. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>is_secondary</code> via <code>is_secondary</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for IPAddressToInterface field is_secondary. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>is_source</code> via <code>is_source</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for IPAddressToInterface field is_source. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>is_standby</code> via <code>is_standby</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for IPAddressToInterface field is_standby. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>last_updated</code> via <code>last_updated</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, id, interface, interface_id, ip_address, ip_address_id, is_default, is_destination, is_preferred, is_primary, is_secondary, is_source, is_standby, vm_interface, vm_interface_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, id, interface, interface_id, ip_address, ip_address_id, is_default, is_destination, is_preferred, is_primary, is_secondary, is_source, is_standby, vm_interface, vm_interface_id
```
</details>

### nautobot.ipam.tests.test_filters.NamespaceTestCase

<details><summary><code>location</code> via <code>location</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Namespace field location. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Namespace field location__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>location</code> via <code>location__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Namespace field location__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.ipam.tests.test_filters.PrefixLocationAssignmentTestCase

<details><summary><code>created</code> via <code>created</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, id, location, location_id, prefix, prefix_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, id, location, location_id, prefix, prefix_id
```
</details>

<details><summary><code>last_updated</code> via <code>last_updated</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, id, location, location_id, prefix, prefix_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, id, location, location_id, prefix, prefix_id
```
</details>

### nautobot.ipam.tests.test_filters.PrefixTestCase

<details><summary><code>contains</code> via <code>contains</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'contains' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, broadcast, children, cloud_network_assignments, cloud_networks, created, date_allocated, description, destination_for_associations, id, ip_address_ranges, ip_addresses, ip_version, last_updated, location_assignments, locations, namespace, namespace_id, network, parent, parent_id, prefix_length, rir, rir_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vlan, vlan_id, vpn_tunnel_endpoints, vrf_assignments, vrfs

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'contains' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, broadcast, children, cloud_network_assignments, cloud_networks, created, date_allocated, description, destination_for_associations, id, ip_address_ranges, ip_addresses, ip_version, last_updated, location_assignments, locations, namespace, namespace_id, network, parent, parent_id, prefix_length, rir, rir_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vlan, vlan_id, vpn_tunnel_endpoints, vrf_assignments, vrfs
```
</details>

<details><summary><code>present_in_vrf</code> via <code>present_in_vrf</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'present_in_vrf' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, broadcast, children, cloud_network_assignments, cloud_networks, created, date_allocated, description, destination_for_associations, id, ip_address_ranges, ip_addresses, ip_version, last_updated, location_assignments, locations, namespace, namespace_id, network, parent, parent_id, prefix_length, rir, rir_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vlan, vlan_id, vpn_tunnel_endpoints, vrf_assignments, vrfs

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'present_in_vrf' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, broadcast, children, cloud_network_assignments, cloud_networks, created, date_allocated, description, destination_for_associations, id, ip_address_ranges, ip_addresses, ip_version, last_updated, location_assignments, locations, namespace, namespace_id, network, parent, parent_id, prefix_length, rir, rir_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vlan, vlan_id, vpn_tunnel_endpoints, vrf_assignments, vrfs
```
</details>

<details><summary><code>present_in_vrf</code> via <code>vrfs__rd</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 81, in test_probe_untested_filters
    self.assertTrue(fs.is_valid(), fs.errors.as_text())
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 744, in assertTrue
    raise self.failureException(msg)
AssertionError: False is not true : * present_in_vrf
  * Select a valid choice. That choice is not one of the available choices.
```
</details>

<details><summary><code>present_in_vrf</code> via <code>vrfs__rd__id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1931, in transform
    return self.try_transform(wrapped, name)
           ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1460, in try_transform
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Unsupported lookup 'id' for CharField or join on the field not permitted.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2267, in add_fields
    cols.append(join_info.transform_function(targets[0], final_alias))
                ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1935, in transform
    raise last_field_exception
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1850, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'id' into field. Join on 'rd' not permitted.
```
</details>

<details><summary><code>present_in_vrf</code> via <code>vrfs__rd__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1931, in transform
    return self.try_transform(wrapped, name)
           ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1460, in try_transform
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Unsupported lookup 'name' for CharField or join on the field not permitted.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2267, in add_fields
    cols.append(join_info.transform_function(targets[0], final_alias))
                ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1935, in transform
    raise last_field_exception
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1850, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'name' into field. Join on 'rd' not permitted.
```
</details>

<details><summary><code>present_in_vrf_id</code> via <code>present_in_vrf_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'present_in_vrf_id' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, broadcast, children, cloud_network_assignments, cloud_networks, created, date_allocated, description, destination_for_associations, id, ip_address_ranges, ip_addresses, ip_version, last_updated, location_assignments, locations, namespace, namespace_id, network, parent, parent_id, prefix_length, rir, rir_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vlan, vlan_id, vpn_tunnel_endpoints, vrf_assignments, vrfs

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'present_in_vrf_id' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, broadcast, children, cloud_network_assignments, cloud_networks, created, date_allocated, description, destination_for_associations, id, ip_address_ranges, ip_addresses, ip_version, last_updated, location_assignments, locations, namespace, namespace_id, network, parent, parent_id, prefix_length, rir, rir_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vlan, vlan_id, vpn_tunnel_endpoints, vrf_assignments, vrfs
```
</details>

<details><summary><code>present_in_vrf_id</code> via <code>vrfs</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 81, in test_probe_untested_filters
    self.assertTrue(fs.is_valid(), fs.errors.as_text())
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 744, in assertTrue
    raise self.failureException(msg)
AssertionError: False is not true : * present_in_vrf_id
  * “[&#x27;71946ba6-e75c-42ce-9427-7e738a5c1c3c&#x27;, &#x27;4ac1c0ac-9641-43c4-90f2-d09a19684cab&#x27;]” is not a valid UUID.
```
</details>

<details><summary><code>present_in_vrf_id</code> via <code>vrfs__id</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 81, in test_probe_untested_filters
    self.assertTrue(fs.is_valid(), fs.errors.as_text())
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 744, in assertTrue
    raise self.failureException(msg)
AssertionError: False is not true : * present_in_vrf_id
  * “[&#x27;71946ba6-e75c-42ce-9427-7e738a5c1c3c&#x27;, &#x27;4ac1c0ac-9641-43c4-90f2-d09a19684cab&#x27;, &#x27;2e868722-577a-4dc2-894a-f1cc402449c8&#x27;]” is not a valid UUID.
```
</details>

<details><summary><code>present_in_vrf_id</code> via <code>vrfs__name</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 81, in test_probe_untested_filters
    self.assertTrue(fs.is_valid(), fs.errors.as_text())
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 744, in assertTrue
    raise self.failureException(msg)
AssertionError: False is not true : * present_in_vrf_id
  * “[&#x27;PaleTurquoise9499&#x27;, &#x27;Aquamarine6873&#x27;]” is not a valid UUID.
```
</details>

<details><summary><code>vpn_tunnel_endpoints_name_contains</code> via <code>vpn_tunnel_endpoints_name_contains</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'vpn_tunnel_endpoints_name_contains' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, broadcast, children, cloud_network_assignments, cloud_networks, created, date_allocated, description, destination_for_associations, id, ip_address_ranges, ip_addresses, ip_version, last_updated, location_assignments, locations, namespace, namespace_id, network, parent, parent_id, prefix_length, rir, rir_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vlan, vlan_id, vpn_tunnel_endpoints, vrf_assignments, vrfs

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'vpn_tunnel_endpoints_name_contains' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, broadcast, children, cloud_network_assignments, cloud_networks, created, date_allocated, description, destination_for_associations, id, ip_address_ranges, ip_addresses, ip_version, last_updated, location_assignments, locations, namespace, namespace_id, network, parent, parent_id, prefix_length, rir, rir_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vlan, vlan_id, vpn_tunnel_endpoints, vrf_assignments, vrfs
```
</details>

<details><summary><code>within</code> via <code>within</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'within' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, broadcast, children, cloud_network_assignments, cloud_networks, created, date_allocated, description, destination_for_associations, id, ip_address_ranges, ip_addresses, ip_version, last_updated, location_assignments, locations, namespace, namespace_id, network, parent, parent_id, prefix_length, rir, rir_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vlan, vlan_id, vpn_tunnel_endpoints, vrf_assignments, vrfs

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'within' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, broadcast, children, cloud_network_assignments, cloud_networks, created, date_allocated, description, destination_for_associations, id, ip_address_ranges, ip_addresses, ip_version, last_updated, location_assignments, locations, namespace, namespace_id, network, parent, parent_id, prefix_length, rir, rir_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vlan, vlan_id, vpn_tunnel_endpoints, vrf_assignments, vrfs
```
</details>

<details><summary><code>within_include</code> via <code>within_include</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'within_include' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, broadcast, children, cloud_network_assignments, cloud_networks, created, date_allocated, description, destination_for_associations, id, ip_address_ranges, ip_addresses, ip_version, last_updated, location_assignments, locations, namespace, namespace_id, network, parent, parent_id, prefix_length, rir, rir_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vlan, vlan_id, vpn_tunnel_endpoints, vrf_assignments, vrfs

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'within_include' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, broadcast, children, cloud_network_assignments, cloud_networks, created, date_allocated, description, destination_for_associations, id, ip_address_ranges, ip_addresses, ip_version, last_updated, location_assignments, locations, namespace, namespace_id, network, parent, parent_id, prefix_length, rir, rir_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vlan, vlan_id, vpn_tunnel_endpoints, vrf_assignments, vrfs
```
</details>

### nautobot.ipam.tests.test_filters.VLANGroupTestCase

<details><summary><code>location</code> via <code>location</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 84, in test_probe_untested_filters
    self.assertQuerySetEqualAndNotEmpty(filterset_result, qs_result, ordered=False)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/source/nautobot/core/testing/mixins.py", line 305, in assertQuerySetEqualAndNotEmpty
    return self.assertQuerySetEqual(qs, values, *args, **kwargs)
           ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/test/testcases.py", line 1282, in assertQuerySetEqual
    return self.assertDictEqual(Counter(items), Counter(values), msg=msg)
           ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 1206, in assertDictEqual
    self.fail(self._formatMessage(msg, standardMsg))
    ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 732, in fail
    raise self.failureException(msg)
AssertionError: Counter({<VLANGroup: BUDGET>: 1, <VLANGroup: DISTANCE>: 1, <VL[115 chars]: 1}) != Counter({<VLANGroup: PROTECTION>: 1, <VLANGroup: WEEK>: 1})
+ Counter({<VLANGroup: PROTECTION>: 1, <VLANGroup: WEEK>: 1})
- Counter({<VLANGroup: BUDGET>: 1,
-          <VLANGroup: DISTANCE>: 1,
-          <VLANGroup: PROTECTION>: 1,
-          <VLANGroup: REVIEW>: 1,
-          <VLANGroup: STRUCTURE>: 1,
-          <VLANGroup: TIME>: 1,
-          <VLANGroup: WEEK>: 1})
```
</details>

<details><summary><code>location</code> via <code>location__id</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 84, in test_probe_untested_filters
    self.assertQuerySetEqualAndNotEmpty(filterset_result, qs_result, ordered=False)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/source/nautobot/core/testing/mixins.py", line 305, in assertQuerySetEqualAndNotEmpty
    return self.assertQuerySetEqual(qs, values, *args, **kwargs)
           ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/test/testcases.py", line 1282, in assertQuerySetEqual
    return self.assertDictEqual(Counter(items), Counter(values), msg=msg)
           ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 1206, in assertDictEqual
    self.fail(self._formatMessage(msg, standardMsg))
    ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 732, in fail
    raise self.failureException(msg)
AssertionError: Count[39 chars]oup: BUDGET>: 1, <VLANGroup: DISTANCE>: 1, <VL[145 chars]: 1}) != Count[39 chars]oup: PROTECTION>: 1, <VLANGroup: STRUCTURE>: 1[49 chars]: 1})
  Counter({<VLANGroup: ATMOSPHERE>: 1,
-          <VLANGroup: BUDGET>: 1,
-          <VLANGroup: DISTANCE>: 1,
           <VLANGroup: PROTECTION>: 1,
-          <VLANGroup: REVIEW>: 1,
           <VLANGroup: STRUCTURE>: 1,
-          <VLANGroup: TIME>: 1,
           <VLANGroup: VLAN Group 3>: 1,
           <VLANGroup: WEEK>: 1})
```
</details>

<details><summary><code>location</code> via <code>location__name</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 84, in test_probe_untested_filters
    self.assertQuerySetEqualAndNotEmpty(filterset_result, qs_result, ordered=False)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/source/nautobot/core/testing/mixins.py", line 305, in assertQuerySetEqualAndNotEmpty
    return self.assertQuerySetEqual(qs, values, *args, **kwargs)
           ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/test/testcases.py", line 1282, in assertQuerySetEqual
    return self.assertDictEqual(Counter(items), Counter(values), msg=msg)
           ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 1206, in assertDictEqual
    self.fail(self._formatMessage(msg, standardMsg))
    ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 732, in fail
    raise self.failureException(msg)
AssertionError: Count[39 chars]oup: BUDGET>: 1, <VLANGroup: DISTANCE>: 1, <VL[93 chars]: 1}) != Count[39 chars]oup: PROTECTION>: 1})
+ Counter({<VLANGroup: ATMOSPHERE>: 1, <VLANGroup: PROTECTION>: 1})
- Counter({<VLANGroup: ATMOSPHERE>: 1,
-          <VLANGroup: BUDGET>: 1,
-          <VLANGroup: DISTANCE>: 1,
-          <VLANGroup: PROTECTION>: 1,
-          <VLANGroup: REVIEW>: 1,
-          <VLANGroup: STRUCTURE>: 1,
-          <VLANGroup: TIME>: 1})
```
</details>

### nautobot.ipam.tests.test_filters.VLANLocationAssignmentTestCase

<details><summary><code>created</code> via <code>created</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, id, location, location_id, vlan, vlan_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, id, location, location_id, vlan, vlan_id
```
</details>

<details><summary><code>last_updated</code> via <code>last_updated</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, id, location, location_id, vlan, vlan_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, id, location, location_id, vlan, vlan_id
```
</details>

### nautobot.ipam.tests.test_filters.VRFDeviceAssignmentTestCase

<details><summary><code>created</code> via <code>created</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, device, device_id, id, name, rd, virtual_device_context, virtual_device_context_id, virtual_machine, virtual_machine_id, vrf, vrf_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, device, device_id, id, name, rd, virtual_device_context, virtual_device_context_id, virtual_machine, virtual_machine_id, vrf, vrf_id
```
</details>

<details><summary><code>last_updated</code> via <code>last_updated</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, device, device_id, id, name, rd, virtual_device_context, virtual_device_context_id, virtual_machine, virtual_machine_id, vrf, vrf_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, device, device_id, id, name, rd, virtual_device_context, virtual_device_context_id, virtual_machine, virtual_machine_id, vrf, vrf_id
```
</details>

### nautobot.ipam.tests.test_filters.VRFPrefixAssignmentTestCase

<details><summary><code>created</code> via <code>created</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, id, prefix, prefix_id, vrf, vrf_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'created' into field. Choices are: associated_data_compliance, associated_object_metadata, id, prefix, prefix_id, vrf, vrf_id
```
</details>

<details><summary><code>last_updated</code> via <code>last_updated</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, id, prefix, prefix_id, vrf, vrf_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'last_updated' into field. Choices are: associated_data_compliance, associated_object_metadata, id, prefix, prefix_id, vrf, vrf_id
```
</details>

### nautobot.ipam.tests.test_filters.VRFTestCase

<details><summary><code>device</code> via <code>device</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, device_assignments, devices, export_targets, id, import_targets, interfaces, last_updated, name, namespace, namespace_id, prefixes, rd, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, virtual_device_contexts, virtual_machines, vm_interfaces

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'device' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, device_assignments, devices, export_targets, id, import_targets, interfaces, last_updated, name, namespace, namespace_id, prefixes, rd, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, virtual_device_contexts, virtual_machines, vm_interfaces
```
</details>

<details><summary><code>device</code> via <code>devices</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VRF field devices. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>device</code> via <code>devices__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VRF field devices__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>device</code> via <code>devices__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VRF field devices__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>virtual_machines</code> via <code>virtual_machines</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VRF field virtual_machines. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>virtual_machines</code> via <code>virtual_machines__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VRF field virtual_machines__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>virtual_machines</code> via <code>virtual_machines__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VRF field virtual_machines__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.load_balancers.tests.test_filters.LoadBalancerPoolMemberFilterTestCase

<details><summary><code>ssl_offload</code> via <code>ssl_offload</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for LoadBalancerPoolMember field ssl_offload. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>status</code> via <code>status</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for LoadBalancerPoolMember field status. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>status</code> via <code>status__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for LoadBalancerPoolMember field status__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>status</code> via <code>status__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for LoadBalancerPoolMember field status__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.load_balancers.tests.test_filters.VirtualServerFilterTestCase

<details><summary><code>enabled</code> via <code>enabled</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualServer field enabled. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>ssl_offload</code> via <code>ssl_offload</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualServer field ssl_offload. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.virtualization.tests.test_filters.ClusterTestCase

<details><summary><code>devices</code> via <code>devices</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Cluster field devices. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>devices</code> via <code>devices__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Cluster field devices__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>devices</code> via <code>devices__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for Cluster field devices__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.virtualization.tests.test_filters.VMInterfaceTestCase

<details><summary><code>enabled</code> via <code>enabled</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VMInterface field enabled. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>vlan_id</code> via <code>vlan_id</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2245, in add_fields
    join_info = self.setup_joins(
        name.split(LOOKUP_SEP), opts, alias, allow_many=allow_m2m
    )
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'vlan_id' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, bridge, bridge_id, bridged_interfaces, child_interfaces, created, description, destination_for_associations, enabled, id, ip_address_assignments, ip_addresses, last_updated, mac_address, mode, mtu, name, parent_interface, parent_interface_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tagged_vlans, tags, untagged_vlan, untagged_vlan_id, virtual_machine, virtual_machine_id, vpn_terminations, vrf, vrf_id

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2286, in add_fields
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'vlan_id' into field. Choices are: _custom_field_data, _name, associated_contacts, associated_data_compliance, associated_object_metadata, bridge, bridge_id, bridged_interfaces, child_interfaces, created, description, destination_for_associations, enabled, id, ip_address_assignments, ip_addresses, last_updated, mac_address, mode, mtu, name, parent_interface, parent_interface_id, role, role_id, source_for_associations, static_group_association_set, status, status_id, tagged_items, tagged_vlans, tags, untagged_vlan, untagged_vlan_id, virtual_machine, virtual_machine_id, vpn_terminations, vrf, vrf_id
```
</details>

### nautobot.virtualization.tests.test_filters.VirtualMachineTestCase

<details><summary><code>local_config_context_schema</code> via <code>local_config_context_schema</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualMachine field local_config_context_schema. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>local_config_context_schema</code> via <code>local_config_context_schema__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualMachine field local_config_context_schema__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>local_config_context_schema</code> via <code>local_config_context_schema__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualMachine field local_config_context_schema__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>local_config_context_schema_id</code> via <code>local_config_context_schema_id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualMachine field local_config_context_schema_id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>local_config_context_schema_id</code> via <code>local_config_context_schema_id__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualMachine field local_config_context_schema_id__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>local_config_context_schema_id</code> via <code>local_config_context_schema_id__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VirtualMachine field local_config_context_schema_id__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.vpn.tests.test_filters.VPNFilterTestCase

<details><summary><code>extra_attributes</code> via <code>extra_attributes</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 84, in test_probe_untested_filters
    self.assertQuerySetEqualAndNotEmpty(filterset_result, qs_result, ordered=False)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/source/nautobot/core/testing/mixins.py", line 302, in assertQuerySetEqualAndNotEmpty
    self.assertNotEqual(len(qs), 0, "QuerySet cannot be empty")
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 916, in assertNotEqual
    raise self.failureException(msg)
AssertionError: 0 == 0 : QuerySet cannot be empty
```
</details>

### nautobot.vpn.tests.test_filters.VPNPhase1PolicyFilterTestCase

<details><summary><code>aggressive_mode</code> via <code>aggressive_mode</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNPhase1Policy field aggressive_mode. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>ike_version</code> via <code>ike_version</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNPhase1Policy field ike_version. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.vpn.tests.test_filters.VPNProfileFilterTestCase

<details><summary><code>extra_options</code> via <code>extra_options</code>: FAIL AssertionError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 84, in test_probe_untested_filters
    self.assertQuerySetEqualAndNotEmpty(filterset_result, qs_result, ordered=False)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/source/nautobot/core/testing/mixins.py", line 302, in assertQuerySetEqualAndNotEmpty
    self.assertNotEqual(len(qs), 0, "QuerySet cannot be empty")
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/unittest/case.py", line 916, in assertNotEqual
    raise self.failureException(msg)
AssertionError: 0 == 0 : QuerySet cannot be empty
```
</details>

<details><summary><code>keepalive_enabled</code> via <code>keepalive_enabled</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNProfile field keepalive_enabled. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>nat_traversal</code> via <code>nat_traversal</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNProfile field nat_traversal. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>secrets_group</code> via <code>secrets_group</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNProfile field secrets_group. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>secrets_group</code> via <code>secrets_group__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNProfile field secrets_group__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>secrets_group</code> via <code>secrets_group__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNProfile field secrets_group__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.vpn.tests.test_filters.VPNProfilePhase1PolicyAssignmentFilterTestCase

<details><summary><code>weight</code> via <code>weight</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNProfilePhase1PolicyAssignment field weight. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.vpn.tests.test_filters.VPNProfilePhase2PolicyAssignmentFilterTestCase

<details><summary><code>weight</code> via <code>weight</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNProfilePhase2PolicyAssignment field weight. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.vpn.tests.test_filters.VPNTunnelEndpointFilterTestCase

<details><summary><code>protected_prefixes_dg</code> via <code>protected_prefixes_dg</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field protected_prefixes_dg. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>protected_prefixes_dg</code> via <code>protected_prefixes_dg__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field protected_prefixes_dg__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>protected_prefixes_dg</code> via <code>protected_prefixes_dg__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field protected_prefixes_dg__name. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>source_ipaddress</code> via <code>source_ipaddress</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field source_ipaddress. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>source_ipaddress</code> via <code>source_ipaddress__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field source_ipaddress__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>source_ipaddress</code> via <code>source_ipaddress__name</code>: ERROR FieldError</summary>

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1931, in transform
    return self.try_transform(wrapped, name)
           ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1460, in try_transform
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Unsupported lookup 'name' for UUIDField or join on the field not permitted.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 128, in get_filterset_test_values
    values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
                        ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1370, in values
    clone = self._values(*fields, **expressions)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1365, in _values
    clone.query.set_values(fields)
    ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2584, in set_values
    self.add_fields(field_names, True)
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 2267, in add_fields
    cols.append(join_info.transform_function(targets[0], final_alias))
                ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1935, in transform
    raise last_field_exception
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1908, in setup_joins
    path, final_field, targets, rest = self.names_to_path(
                                       ~~~~~~~~~~~~~~~~~~^
        names[:pivot],
        ^^^^^^^^^^^^^^
    ...<2 lines>...
        fail_on_missing=True,
        ^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1813, in names_to_path
    raise FieldError(
    ...<2 lines>...
    )
django.core.exceptions.FieldError: Cannot resolve keyword 'name' into field. Choices are: _custom_field_data, associated_contacts, associated_data_compliance, associated_object_metadata, created, description, destination_for_associations, dns_name, host, id, interface_assignments, interface_redundancy_groups, interfaces, ip4_vdcs, ip6_vdcs, ip_version, last_updated, load_balancer_pool_members, mask_length, nat_inside, nat_inside_id, nat_outside_list, parent, parent_id, primary_ip4_for, primary_ip6_for, role, role_id, services, source_for_associations, static_group_association_set, status, status_id, tagged_items, tags, tenant, tenant_id, type, virtual_servers, vm_interfaces, vpn_tunnel_endpoints_src_ip
```
</details>

<details><summary><code>tunnel_interface</code> via <code>tunnel_interface</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field tunnel_interface. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tunnel_interface</code> via <code>tunnel_interface__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field tunnel_interface__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>tunnel_interface</code> via <code>tunnel_interface__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNTunnelEndpoint field tunnel_interface__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.vpn.tests.test_filters.VPNTunnelFilterTestCase

<details><summary><code>secrets_group</code> via <code>secrets_group</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNTunnel field secrets_group. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>secrets_group</code> via <code>secrets_group__id</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNTunnel field secrets_group__id. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>secrets_group</code> via <code>secrets_group__name</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for VPNTunnel field secrets_group__name. At least 3 unique values are required to test multivalue filters.
```
</details>

### nautobot.wireless.tests.test_filters.RadioProfileTestCase

<details><summary><code>allowed_channel_list</code> via <code>allowed_channel_list</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 83, in test_probe_untested_filters
    qs_result = self.queryset.filter(**{f"{field_name}__in": test_data}).distinct()
                ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/source/nautobot/core/models/querysets.py", line 100, in filter
    return super().filter(*args, **self.split_composite_key_into_kwargs(composite_key, **kwargs))
           ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1495, in filter
    return self._filter_or_exclude(False, args, kwargs)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1513, in _filter_or_exclude
    clone._filter_or_exclude_inplace(negate, args, kwargs)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/query.py", line 1523, in _filter_or_exclude_inplace
    self._query.add_q(Q(*args, **kwargs))
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1648, in add_q
    clause, _ = self._add_q(q_object, can_reuse)
                ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1680, in _add_q
    child_clause, needed_inner = self.build_filter(
                                 ~~~~~~~~~~~~~~~~~^
        child,
        ^^^^^^
    ...<7 lines>...
        update_join_types=update_join_types,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1590, in build_filter
    condition = self.build_lookup(lookups, col, value)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/sql/query.py", line 1417, in build_lookup
    lookup = lookup_class(lhs, rhs)
  File "/usr/local/lib/python3.13/site-packages/django/db/models/lookups.py", line 38, in __init__
    self.rhs = self.get_prep_lookup()
               ~~~~~~~~~~~~~~~~~~~~^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/lookups.py", line 536, in get_prep_lookup
    return super().get_prep_lookup()
           ~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/usr/local/lib/python3.13/site-packages/django/db/models/lookups.py", line 321, in get_prep_lookup
    rhs_value = self.lhs.output_field.get_prep_value(rhs_value)
  File "/source/nautobot/core/models/fields.py", line 310, in get_prep_value
    raise ValueError(f"value {value} is not list or tuple")
ValueError: value [36] is not list or tuple
```
</details>

### nautobot.wireless.tests.test_filters.WirelessNetworkTestCase

<details><summary><code>enabled</code> via <code>enabled</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for WirelessNetwork field enabled. At least 3 unique values are required to test multivalue filters.
```
</details>

<details><summary><code>hidden</code> via <code>hidden</code>: ERROR ValueError</summary>

```
Traceback (most recent call last):
  File "/source/nautobot/core/tests/test_zz_probe_untested.py", line 77, in test_probe_untested_filters
    test_data = self.get_filterset_test_values(field_name)
  File "/source/nautobot/core/testing/filters.py", line 138, in get_filterset_test_values
    raise ValueError(
    ...<2 lines>...
    )
ValueError: Cannot find enough valid test data for WirelessNetwork field hidden. At least 3 unique values are required to test multivalue filters.
```
</details>

