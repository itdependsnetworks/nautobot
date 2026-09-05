"""Tables for the users app (permission policies)."""

import json

from django.contrib.auth.models import AnonymousUser
from django.utils.html import format_html, format_html_join
from django.utils.text import Truncator
import django_tables2 as tables

from nautobot.core.tables import BaseTable, BooleanColumn, ButtonsColumn, LinkedCountColumn, ToggleColumn
from nautobot.core.templatetags.helpers import HTML_NONE, render_json
from nautobot.users.models import PermissionPolicy, PolicyAssignment, PolicyParameter, PolicyRule

__all__ = (
    "PermissionPolicyTable",
    "PolicyAssignmentTable",
    "PolicyParameterTable",
    "PolicyRuleTable",
    "PreviewResultsTable",
    "RuleConstraintsTable",
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


OBJECT_TYPES_TEMPLATE = """{{ value|join:", " }}"""

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

MISSING_VALUE_BADGE = (
    '<div><span class="badge bg-warning text-dark" title="This assignment grants nothing until a value is supplied.">'
    "missing value: {}</span></div>"
)


def render_parameter_values(values, missing=()):
    """
    Render an assignment's `parameter_values` compactly: one line per parameter, short lists inline and long lists as
    a count, followed by a warning badge for each parameter that has no value.
    """
    lines = []
    for name, value in (values or {}).items():
        if isinstance(value, list):
            shown = ", ".join(str(item) for item in value) if len(value) <= 3 else f"{len(value)} values"
        else:
            shown = str(value)
        lines.append(format_html("<div><code>{}</code>: {}</div>", name, shown))
    if not lines:
        lines.append(HTML_NONE)
    lines.extend(format_html(MISSING_VALUE_BADGE, name) for name in missing)
    return format_html_join("", "{}", ((line,) for line in lines))


class PermissionPolicyTable(BaseTable):
    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    content_types = PolicyContentTypesColumn()
    parameter_count = tables.Column(verbose_name="Parameters")
    rule_count = tables.Column(verbose_name="Rules")
    assignment_count = LinkedCountColumn(
        viewname="users:policyassignment_list",
        url_params={"policy": "name"},
        verbose_name="Assignments",
    )
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
            "assignment_count",
            "actions",
        )
        default_columns = ("pk", "name", "description", "content_types", "assignment_count", "actions")


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


class PolicyAssignmentTable(BaseTable):
    pk = ToggleColumn()
    name = tables.Column(linkify=True)
    policy = tables.Column(linkify=True)
    enabled = BooleanColumn()
    parameter_values = tables.Column(orderable=False)
    users = tables.ManyToManyColumn(linkify_item=False)
    groups = tables.ManyToManyColumn(linkify_item=False)
    actions = ButtonsColumn(PolicyAssignment)

    class Meta(BaseTable.Meta):
        model = PolicyAssignment
        fields = ("pk", "name", "policy", "enabled", "description", "parameter_values", "users", "groups", "actions")
        default_columns = ("pk", "name", "policy", "enabled", "parameter_values", "users", "groups", "actions")

    def render_parameter_values(self, value, record):
        return render_parameter_values(value, record.missing_parameter_names())


COMPACT_CONSTRAINT_MAX_LENGTH = 90


def render_constraints(value):
    """
    Render a rendered constraint list: a warning badge for "no constraint", a single highlighted line when the
    constraint is short, and pretty-printed JSON only when it is not.
    """
    if not value or not value[0]:
        return format_html('<span class="badge bg-warning text-dark">no constraint (all objects)</span>')
    compact = json.dumps(value[0] if len(value) == 1 else value, default=str)
    if len(compact) <= COMPACT_CONSTRAINT_MAX_LENGTH:
        return format_html('<code class="language-json">{}</code>', compact)
    return format_html('<pre class="mb-0 small">{}</pre>', render_json(value))


class ConstraintsColumn(tables.Column):
    """A column over a rendered constraint list, using `render_constraints`."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("orderable", False)
        super().__init__(*args, **kwargs)

    def render(self, value):
        return render_constraints(value)


class NonModelTable(tables.Table):
    """
    django-tables2 base for tables over plain dicts (no QuerySet), styled like `BaseTable`.

    Supports the same per-user column configuration as `BaseTable`: `Meta.default_columns` hides the other columns
    until the user picks them, the choice is stored under `tables.<ClassName>.columns` in the user's config, and
    `configurable=True` shows the table's Configure button.
    """

    class Meta:
        attrs = {"class": "table table-hover nb-table-headings"}
        orderable = False
        default = HTML_NONE

    def __init__(self, data, *args, user=None, configurable=False, **kwargs):
        # Mirrors the default-column and per-user column handling of `BaseTable.__init__`; keep the two in step.
        super().__init__(data, *args, **kwargs)
        self.configurable = configurable
        default_columns = list(getattr(self.Meta, "default_columns", []))
        if default_columns:
            for column in self.columns:
                if column.name not in default_columns:
                    self.columns.hide(column.name)
        columns = None
        if user is not None and not isinstance(user, AnonymousUser):
            columns = user.get_config(f"tables.{self.__class__.__name__}.columns")
        if columns:
            for name in self.base_columns:
                if name in columns and name not in self.exclude:
                    self.columns.show(name)
                else:
                    self.columns.hide(name)
            self.sequence = [name for name in columns if name in self.base_columns]

    @property
    def configurable_columns(self):
        """Columns the user may toggle, selected ones first in their current order (same contract as `BaseTable`)."""
        selected = [(name, column.verbose_name) for name, column in self.columns.items() if name in self.sequence]
        available = [(name, column.verbose_name) for name, column in self.columns.items() if name not in self.sequence]
        return [item for item in selected + available if item[0] not in self.exclude]

    @property
    def visible_columns(self):
        return [name for name, column in self.columns.items() if column.visible and name not in self.exclude]


MATCHES_TEMPLATE = """
{% if record.has_result %}
    {% if record.timed_out %}
        <span class="badge bg-danger">timed out</span>
    {% else %}
        {% if record.list_url %}<a href="{{ record.list_url }}" title="Open the full {{ record.object_type }} list filtered like this constraint">{% endif %}
        {% if value == 0 %}
            <span class="badge bg-danger" title="No objects match. Check the lookup path.">0</span>
        {% else %}
            <span class="badge bg-success">{{ value }}</span>
        {% endif %}
        {% if record.list_url %}</a>{% endif %}
    {% endif %}
{% else %}
    <span class="text-secondary" title="Supply parameter values to count matching objects">&mdash;</span>
{% endif %}
"""

SAMPLE_TEMPLATE = """{% load helpers %}
{% if record.has_result and value %}
    {% hyperlinked_object_list value total=record.count list_url=record.list_url separator=", " %}
{% else %}
    <span class="text-secondary">&mdash;</span>
{% endif %}
"""

DEFINITION_TEMPLATE = """{% load helpers %}<details><summary class="small text-secondary">{{ value.name }}</summary><pre class="mb-0 small">{{ value|render_json }}</pre></details>"""


class PreviewResultsTable(NonModelTable):
    """
    Policy preview: one row per rule (object type) with the rendered constraint, the match count and a sample.

    Before parameter values are supplied the constraints keep their `{{ name }}` placeholders and the count and
    sample columns show a dash.
    """

    object_type = tables.Column(verbose_name="Object type")
    actions = tables.TemplateColumn(template_code=ACTIONS_TEMPLATE)
    constraints = ConstraintsColumn()
    count = tables.TemplateColumn(template_code=MATCHES_TEMPLATE, verbose_name="Matches")
    sample = tables.TemplateColumn(template_code=SAMPLE_TEMPLATE, verbose_name="Sample")

    class Meta(NonModelTable.Meta):
        pass

    def __init__(self, data, *args, sample_size=None, **kwargs):
        super().__init__(data, *args, **kwargs)
        if sample_size:
            self.columns["sample"].column.verbose_name = f"Sample (first {sample_size})"

    @staticmethod
    def rows_from_preview(preview_rows):
        """Rows from `PreviewRow` results: the preview ran, so every row has a count and a sample."""
        return [
            {
                "object_type": row.object_type,
                "actions": row.actions,
                "constraints": row.constraints,
                "count": row.count,
                "timed_out": row.timed_out,
                "sample": row.sample,
                "list_url": row.list_url,
                "has_result": True,
            }
            for row in preview_rows
        ]

    @staticmethod
    def rows_from_rules(rules):
        """Rows from unrendered rules (no parameter values yet): templates as written, no counts."""
        from nautobot.core.utils.permissions import normalize_constraints
        from nautobot.users.policies import rule_content_type

        return [
            {
                "object_type": rule_content_type(rule),
                "actions": rule.actions,
                "constraints": normalize_constraints(rule.constraint_template),
                "count": None,
                "timed_out": False,
                "sample": [],
                "list_url": None,
                "has_result": False,
            }
            for rule in rules
        ]


class RuleConstraintsTable(NonModelTable):
    """
    The constraints an assignment renders to: exactly what permission resolution produces.

    Rules with the same actions and the same rendered constraints share one row listing all of their object types,
    the way an object permission lists its content types. The hidden "Definition (JSON)" column, available from the
    table's Configure button, shows each record in the shape the object permissions REST API accepts.
    """

    object_types = tables.TemplateColumn(template_code=OBJECT_TYPES_TEMPLATE, verbose_name="Object types")
    actions = tables.TemplateColumn(template_code=ACTIONS_TEMPLATE)
    constraints = ConstraintsColumn()
    definition = tables.TemplateColumn(template_code=DEFINITION_TEMPLATE, verbose_name="Definition (JSON)")

    class Meta(NonModelTable.Meta):
        default_columns = ("object_types", "actions", "constraints")

    @staticmethod
    def rows_from_records(records):
        return [
            {
                "object_types": record.object_types,
                "actions": record.actions,
                "constraints": record.constraints,
                "definition": record.as_dict(),
            }
            for record in records
        ]
