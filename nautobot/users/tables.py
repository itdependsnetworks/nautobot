"""Tables for the users app (permission policies)."""

import django_tables2 as tables

from nautobot.core.tables import BaseTable, ButtonsColumn, ToggleColumn
from nautobot.users.models import PermissionPolicy

__all__ = ("PermissionPolicyTable",)


class PermissionPolicyTable(BaseTable):
    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    # PLACEHOLDER: will be replaced in C12 (Policy assignment model and stack): a linked count of assignments.
    actions = ButtonsColumn(PermissionPolicy)

    class Meta(BaseTable.Meta):
        model = PermissionPolicy
        fields = (
            "pk",
            "name",
            "description",
            "actions",
        )
        default_columns = ("pk", "name", "description", "actions")
