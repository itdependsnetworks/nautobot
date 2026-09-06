# Form Layout Framework: migration tracker

> **This file is not intended to reach the final pull request.**
>
> It exists so that a reviewer taking one commit at a time can see which forms that commit migrates and what each
> one exercises. It lands as its own commit at the head of the series and is **deleted in a final commit before the
> PR is opened**, on the same footing as the `NB-FIELDSETS-REVIEW` markers in the code. If you are reading this in
> a pull request, it should not be there: say so on the PR.

Every form the Form Layout Framework migrates, in the order the commit series migrates it. The commit ids are those
in the commit plan, where each set is a capability of the framework (`Sn.F*`, the foundation commits) followed by the
implementation commit that migrates the forms needing it (`Sn.I`). Any prefix of the series is shippable: no migrated
form depends on a capability that lands later.

## How to read this

**Commit** is the commit that migrates the form. **Status**:

- **shim** — the form declares `fieldsets` and the template is down to a single `{% extends %}` line. It only still
  exists because an App might extend it.
- **kept** — the form declares `fieldsets` and the template lost its form block but still carries something else: a
  page title, a tab header, extra buttons, or a page script.
- **default** — no `fieldsets` were needed; what the template drew by hand is what the default layout draws anyway.
- **done** — no template was involved.
- **skip** — left alone; the reason is in Notes.

Feature columns record what each form's `Meta.fieldsets` **actually uses** after the migration, so a column total is
the number of forms exercising that feature. **Tenancy pin** — `Contributed("tenancy")` placed explicitly (the
Custom Fields / Relationships / Notes / Tags panels arrive automatically on every model form, so they are not
tracked). **Included** — an `IncludedTemplate` named in the form's own `fieldsets`; one a component inserts for
itself, as `SoftwareImagePanel` does, is not counted. **Custom** — a field or panel rendered from its own template
or component. **Media** — an app-level component ships its own script; the scripts built into `FormSetPanel` and
`RemoteFragment` are framework plumbing and are not counted. **Cond.** — `render_if` (r) or `visible_if` (v).
**FormSet**, **Tabs**, **Static**, **Inline**, **Remote** — the corresponding items. **Other blocks** — template
blocks that keep the template alive.

## Migrated, by commit

| Commit | Template | Form class | Tenancy pin | Included | Custom | Media | Cond. | FormSet | Tabs | Static | Inline | Remote | Other blocks | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1.F6 | circuits (no template) | ProviderNetworkForm | | | | | | | | | | | | done | dormant `Meta.fieldsets` from 1.x; takes effect the moment the generic templates honour a declared layout |
| S1.I | circuits/provider_create.html | ProviderForm | | | | | | | | | | | | shim | |
| S1.I | cloud/cloudnetwork_update.html | CloudNetworkForm | | | | | | | | | | | | shim | |
| S1.I | cloud/cloudservice_update.html | CloudServiceForm | | | | | | | | | | | | shim | |
| S1.I | dcim/deviceredundancygroup_create.html | DeviceRedundancyGroupForm | | | | | | | | | | | | shim | |
| S1.I | dcim/devicetype_update.html | DeviceTypeForm | | | | | | | | | | | | shim | |
| S1.I | dcim/powerfeed_create.html | PowerFeedForm | | | | | | | | | | | | shim | **surfaces `power_path`**, which the template had omitted |
| S1.I | dcim/rackreservation_create.html | RackReservationForm | | | | | | | | | | | | shim | tenancy kept under its own "Tenant Assignment" panel, so no pin is needed |
| S1.I | dcim/virtualchassis_create.html | VirtualChassisCreateForm | | | | | | | | | | | | shim | |
| S1.I | extras/configcontextschema_update.html | ConfigContextSchemaForm | | | | | | | | | | | | shim | |
| S1.I | extras/externalintegration_update.html | ExternalIntegrationForm | | | | | | | | | | | | shim | |
| S1.I | extras/tag_update.html | TagForm | | | | | | | | | | | | shim | |
| S1.I | tenancy/tenant_create.html | TenantForm | | | | | | | | | | | | shim | |
| S1.I | dcim/device_component_edit.html | component edit forms | | | | | | | | | | | | default | was `render_form form` only |
| S1.I | dcim/interfaceredundancygroupassociation_create.html | InterfaceRedundancyGroupAssociationForm | | | | | | | | | | | | default | was a card around `render_form` |
| S2.I | circuits/circuit_create.html | CircuitForm | x | | | | | | | | | | | shim | commit rate uses the `NumberWithSelect` widget with `CircuitSpeedChoices` (was a `SpeedField` layout item with its own template and script) |
| S2.I | dcim/location_update.html | LocationForm | x | | | | | | | | | | | shim | |
| S2.I | ipam/namespace_update.html | NamespaceForm | x | | | | | | | | | | | shim | |
| S2.I | ipam/prefix_create.html | PrefixForm | x | | | | | | | | | | | shim | |
| S2.I | ipam/vlan_update.html | VLANForm | x | | | | | | | | | | | shim | |
| S2.I | ipam/vrf_create.html | VRFForm | x | | | | | | | | | | | shim | **surfaces `virtual_device_contexts`**, which the template had omitted |
| S2.I | virtualization/cluster_create.html | ClusterForm | x | | | | | | | | | | | shim | **surfaces `devices`**, which the template had omitted |
| S3.I | dcim/virtualdevicecontext_update.html | VirtualDeviceContextForm | | | | | r | | | | | | | shim | `render_if` on the primary IPs; explicit Tenancy panel of plain tenant fields, no mixin |
| S4.I | dcim/rack_update.html | RackForm | x | | | | | | | | x | | | shim | `InlineFields` for the outer dimensions (3/3/2) |
| S5.I | dcim/platform_create.html | PlatformForm | | | x | | | | | | | | | shim | `network_driver` row from its own template (help link plus choices modal) |
| S5.I | extras/secret_create.html | SecretForm | | | x | | | | | | | | javascript | kept | `parameters` row from its own template (Form / JSON tabs); provider script stays; a `RemoteFragment` candidate |
| S6.I | dcim/interface_update.html | InterfaceForm | | | | | v | | | | | | buttons | kept | `visible_if` on the VLAN fields; now also shows `module_family`/`module` |
| S6.I | extras/objectmetadata_create.html | ObjectMetadataCreateForm | | | | | | | | | | | javascript | default | the block rendered every visible field in one card, which is the default layout; the page script lost its select2 bridge; the value widget is a `RemoteFragment` candidate |
| S7.I | dcim/module_update.html | ModuleForm | | | | | | | x | | | | | shim | tabs (`clear_inactive`) device / module / location; `Omitted("parent_module_bay")`; script removed, and so was the view's dead active-tab helper |
| S7.I | dcim/controller_create.html | ControllerForm | x | | | | | | x | | | | | shim | tabs (`clear_inactive`) device vs redundancy group; script removed. Default tab is now "Controller Device" |
| S7.I | ipam/ipaddress_edit.html | IPAddressForm | x | | | | | | x | | | | tabs | kept | tabs for the NAT selectors |
| S8.I | circuits/circuittermination_create.html | CircuitTerminationForm | | | | | | | x | x | | | title | kept | three `StaticField`s; tabs (`clear_inactive`) for location / provider network / cloud network; speeds use the `NumberWithSelect` widget (was `SpeedField` ×2) |
| S9.I | dcim/device_create.html | DeviceForm | x | x | x | x | r | | | x | | | | shim | `SoftwareImagePanel`, which inserts the image list itself; `IncludedTemplate` for the primary-IP hint; `StaticField` ×2 for parent device and bay; `render_if` on face/position and the primary IPs |
| S9.I | dcim/inventoryitem_update.html | InventoryItemForm | | | x | x | | | | | | | | shim | `SoftwareImagePanel`, version-only mode |
| S9.I | virtualization/virtualmachine_update.html | VirtualMachineForm | x | | x | x | | | | | | | | shim | `SoftwareImagePanel`, version-only mode |
| S10.I | extras/object_new_contact.html | ObjectNewContactForm | | | | | | | | | | | tabs | kept | `FormField(..., as_hidden=True)` ×2 |
| S10.I | extras/object_new_team.html | ObjectNewTeamForm | | | | | | | | | | | tabs | kept | `FormField(..., as_hidden=True)` ×2 |
| S11.I | extras/configcontext_update.html | ConfigContextForm | | | | | | | | | | | | shim | gained `FormLayoutMixin`; assignment `tags` claimed explicitly; `FormField("dynamic_groups", optional=True)`; the Notes panel is now permission-gated |
| S12.I | extras/secretsgroup_update.html | SecretsGroupForm | | | | | | x | | | | | | shim | secrets formset (`add_label`); script block gone |
| S12.I | extras/metadatatype_create.html | MetadataTypeForm | | | | | | x | | | | | | shim | choices formset (`add_label`, `keep_field_values`); script block gone |
| S12.I | extras/approvalworkflowdefinition_update.html | ApprovalWorkflowDefinitionForm | | | | | | x | | | | | | shim | gained `FormLayoutMixin`; stages formset (`add_label`, `keep_field_values`); script block gone |
| S12.I | vpn/vpnprofile_create.html | VPNProfileForm | x | | | | | x | | | | | | shim | two policy formsets (`add_label`); **surfaces the Tenancy panel**, which the template had omitted; script block gone |
| S12.I | wireless/wirelessnetwork_create.html | WirelessNetworkForm | | | | | | x | | | | | | shim | device groups formset (`add_label`); **surfaces `tenant`**, which the template had omitted; script block gone |
| S12.I | dcim/controllermanageddevicegroup_create.html | ControllerManagedDeviceGroupForm | x | x | | | | x | | | | | javascript | kept | `IncludedTemplate` for the hidden `controller` copy; wireless networks formset, self-initializing; the parent/controller mirroring script stays, on native `change` events |
| S13.I | extras/customfield_update.html | CustomFieldForm | | | | | v | x | | | | x | javascript | kept | gained `FormLayoutMixin`; the scope filter is a `RemoteFragment` whose endpoint renders its inner HTML; `visible_if` on the validation fields and the choices formset; the template keeps only the dynamic-filter page script; `customfield_form.js` deleted |
| S14.I | extras/job_update.html | JobEditForm | | x | x | x | | | | | | | | shim | `OverridableFormField` ×12, which ships the lock/unlock script and each row's default; `IncludedTemplate` for the Job Source rows |
| S15.I | extras/job.html (schedule card) | JobScheduleForm | | | | | v | | | | | | javascript | kept | not a model form: gained `FormLayoutMixin` and `visible_if` with `clear_on_hide` on the three schedule rows; rendered with `{% render_form_layout schedule_form bare=True %}` inside the page's own card; the script keeps only the required-marking and the run button swap |

Totals for the migrated forms: 43 with `fieldsets` (34 shim, 8 kept, 1 done) plus 3 default-layout templates.
Feature totals: Tenancy pin 15 · Included 3 · Custom 6 · Media 4 · Cond. 4 · FormSet 7 · Tabs 4 · Static 2 ·
Inline 1 · Remote 1.

## Not migrated

Nine templates are deliberately left alone. None of them blocks the series.

| Template | Form class | Other blocks | Notes |
|---|---|---|---|
| dcim/cable_update.html | CableForm | javascript | bespoke termination form (`dcim/inc/cable_form.html`) plus script; its select2-to-HTMX bridge was removed, since that is global now |
| dcim/cabletype_create.html | CableTypeForm | javascript | bespoke Lane Mapping editor with header controls and an HTMX table editor; a `RemoteFragment` candidate |
| dcim/device_component_add.html | ComponentCreateForm + model_form | buttons, title | two form objects on one page |
| dcim/inventoryitem_add.html | InventoryItemCreateForm | javascript | component create form (pattern expansion), not a model form |
| dcim/location_migrate_data_to_contact.html | LocationMigrateDataToContactForm | buttons, title | bespoke action form |
| extras/dynamicgroup_update.html | DynamicGroupForm | form_errors, javascript | filter form plus children formset on one page |
| extras/job_bulk_update.html | JobBulkEditForm | extra_styles, javascript | bulk edit is out of scope |
| extras/object_assign_contact_or_team.html | ContactAssociationForm | buttons, tabs, javascript | the form class is shared with the generic ContactAssociation edit view, where the object fields must stay visible |
| ipam/ipaddress_bulk_add.html | IPAddressBulkCreateForm + model_form | tabs, title | two form objects on one page |

## Behaviour changes worth a second look

Each is marked `NB-FIELDSETS-REVIEW[behaviour]` at the line in question, and named in its commit's message.

| Commit | Change |
|---|---|
| S1.F3 | Where a template placed the Custom Fields / Relationships / Notes / Tags cards *before* its own trailing "Comments" card, Comments now comes first. Eleven migrated forms are affected. Pinning with `Contributed(...)` would restore the old order per form. |
| S1.I | `PowerFeed.power_path` is on the page; the old template omitted it although the form had the field. |
| S2.I | `VRF.virtual_device_contexts` and `Cluster.devices` likewise. |
| S6.F3 | Select2 widgets now emit a native `change` event, so a jQuery `change` listener on a Select2 field fires twice per selection. The listeners in core are idempotent; an App's may not be. |
| S6.I | Access and tagged-all mode now *discard* submitted tagged VLANs (server-side `clear_on_hide`) instead of rejecting them; two tests changed accordingly. `Interface` also shows `module_family` and `module`. |
| S7.I | Controller opens on the "Controller Device" tab rather than the redundancy group. |
| S11.I | The Config Context Notes card is gated on `extras.add_note` like every other form; it used to be unconditional. |
| S12.I | VPN Profile shows the Tenancy card and Wireless Network shows `tenant`; both templates had omitted them. |
| S13.I | The Custom Field min/max help text no longer switches wording between numeric and text types. |
