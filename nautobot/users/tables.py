"""Tables for the users app (permission policies)."""

from django.utils.html import format_html
from django.utils.text import Truncator
import django_tables2 as tables

from nautobot.core.tables import BaseTable, BooleanColumn, ButtonsColumn, ToggleColumn
from nautobot.users.models import PermissionPolicy, PolicyParameter, PolicyRule

__all__ = (
    "PermissionPolicyTable",
    "PolicyParameterTable",
    "PolicyRuleTable",
)


class PolicyContentTypesColumn(tables.Column):
    """
    The content types of a policy's rules, rendered like `ContentTypesColumn` does for a Status or Tag:
    a comma-separated list such as "DCIM | device, DCIM | interface", truncated after `truncate_words` words.
    """

    def __init__(self, *args, truncate_words=15, **kwargs):
        kwargs.setdefault("orderable", False)
        kwargs.setdefault("verbose_name", "Object types")
        kwargs.setdefault("accessor", "rules")
        super().__init__(*args, **kwargs)
        self.truncate_words = truncate_words

    def render(self, value):
        content_types = sorted({str(rule.content_type) for rule in value.all()})
        if not content_types:
            return format_html('<span class="text-secondary">&mdash;</span>')
        text = ", ".join(content_types)
        if self.truncate_words is not None:
            text = Truncator(text).words(self.truncate_words)
        return text


ACTIONS_TEMPLATE = """{% for action in value %}<span class="badge bg-secondary">{{ action }}</span> {% endfor %}"""

PATH_MAP_TEMPLATE = """
{% with parameters=record.policy.parameters.all %}
{% for name, entry in value.items %}
    <div><code>{{ name }}</code> &rarr; <code>{{ entry.path }}</code> <span class="text-secondary">({{ entry.lookup }})</span></div>
{% endfor %}
{% for parameter in parameters %}
    {% if parameter.name not in value %}
        <div><code>{{ parameter.name }}</code> &rarr; <span class="badge bg-warning text-dark" title="This rule's template does not use this parameter, so this object type is not limited by it">not scoped by this parameter</span></div>
    {% endif %}
{% endfor %}
{% if not value and not parameters %}<span class="text-secondary">&mdash;</span>{% endif %}
{% endwith %}
"""

JSON_TEMPLATE = """{% load helpers %}{% if value %}<pre class="mb-0 small">{{ value|render_json }}</pre>{% else %}<span class="badge bg-warning text-dark">no constraint (all objects)</span>{% endif %}"""


class PermissionPolicyTable(BaseTable):
    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    content_types = PolicyContentTypesColumn()
    parameter_count = tables.Column(verbose_name="Parameters")
    rule_count = tables.Column(verbose_name="Rules")
    # PLACEHOLDER: will be replaced in C12 (Policy assignment model and stack): a linked count of assignments.
    actions = ButtonsColumn(PermissionPolicy)

    class Meta(BaseTable.Meta):
        model = PermissionPolicy
        fields = (
            "pk",
            "name",
            "description",
            "content_types",
            "parameter_count",
            "rule_count",
            "actions",
        )
        default_columns = ("pk", "name", "description", "content_types", "actions")


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


class PolicyRuleTable(BaseTable):
    pk = ToggleColumn()
    content_type = tables.Column(verbose_name="Object type", linkify=lambda record: record.get_absolute_url())
    policy = tables.Column(linkify=True)
    rule_actions = tables.TemplateColumn(
        template_code=ACTIONS_TEMPLATE, accessor="actions", verbose_name="Actions", orderable=False
    )
    path_map = tables.TemplateColumn(template_code=PATH_MAP_TEMPLATE, verbose_name="Parameter paths", orderable=False)
    constraint_template = tables.TemplateColumn(template_code=JSON_TEMPLATE, orderable=False)
    actions = ButtonsColumn(PolicyRule)

    class Meta(BaseTable.Meta):
        model = PolicyRule
        fields = ("pk", "content_type", "policy", "rule_actions", "path_map", "constraint_template", "actions")
