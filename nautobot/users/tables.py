"""Tables for the users app (permission policies)."""

import django_tables2 as tables

from nautobot.core.tables import BaseTable, BooleanColumn, ButtonsColumn, ToggleColumn
from nautobot.users.models import PermissionPolicy, PolicyParameter

__all__ = (
    "PermissionPolicyTable",
    "PolicyParameterTable",
)


class PermissionPolicyTable(BaseTable):
    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    parameter_count = tables.Column(verbose_name="Parameters")
    # PLACEHOLDER: will be replaced in C12 (Policy assignment model and stack): a linked count of assignments.
    actions = ButtonsColumn(PermissionPolicy)

    class Meta(BaseTable.Meta):
        model = PermissionPolicy
        fields = (
            "pk",
            "name",
            "description",
            "parameter_count",
            "actions",
        )
        default_columns = ("pk", "name", "description", "actions")


class PolicyParameterTable(BaseTable):
    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    policy = tables.Column(linkify=True)
    kind = tables.Column()
    target_content_type = tables.Column(verbose_name="Target object type")
    multiple = BooleanColumn()
    actions = ButtonsColumn(PolicyParameter)

    class Meta(BaseTable.Meta):
        model = PolicyParameter
        fields = ("pk", "name", "policy", "kind", "target_content_type", "multiple", "actions")
