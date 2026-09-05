from collections import namedtuple
import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AdminPasswordChangeForm as _AdminPasswordChangeForm,
    AuthenticationForm,
    PasswordChangeForm as DjangoPasswordChangeForm,
)
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.forms import inlineformset_factory
from timezone_field import TimeZoneFormField

from nautobot.core.events import publish_event
from nautobot.core.forms import (
    add_blank_choice,
    BOOLEAN_WITH_BLANK_CHOICES,
    BootstrapMixin,
    BulkEditForm,
    BulkEditNullBooleanSelect,
    ConstraintEditorField,
    DateTimePicker,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    MultipleContentTypeField,
    MultiValueCharField,
)
from nautobot.core.forms.widgets import APISelect, APISelectMultiple, StaticSelect2, StaticSelect2Multiple
from nautobot.core.models.tree_queries import TreeModel
from nautobot.core.utils.config import get_settings_or_config
from nautobot.core.utils.orm_paths import find_relation_paths, split_path_and_lookup
from nautobot.core.utils.permissions import CONSTRAINT_PLACEHOLDER_PATTERN
from nautobot.extras.forms import NautobotFilterForm
from nautobot.users.choices import PolicyParameterKindChoices
from nautobot.users.utils import serialize_user_without_config_and_views

from .models import (
    PERMISSION_OBJECT_TYPE_LIMIT_CHOICES,
    PermissionPolicy,
    PolicyAssignment,
    PolicyParameter,
    PolicyRule,
    Token,
)


class LoginForm(BootstrapMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].widget.attrs["placeholder"] = ""
        self.fields["password"].widget.attrs["placeholder"] = ""


class PasswordChangeForm(BootstrapMixin, DjangoPasswordChangeForm):
    pass


class TokenForm(BootstrapMixin, forms.ModelForm):
    key = forms.CharField(
        required=False,
        help_text="If no key is provided, one will be generated automatically.",
    )

    class Meta:
        model = Token
        fields = [
            "key",
            "write_enabled",
            "expires",
            "description",
        ]
        widgets = {
            "expires": DateTimePicker(),
        }


class AdvancedProfileSettingsForm(BootstrapMixin, forms.Form):
    request_profiling = forms.BooleanField(
        required=False,
        help_text="Enable request profiling for the duration of the login session. "
        "This is for debugging purposes and should only be enabled when "
        "instructed by an administrator.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ALLOW_REQUEST_PROFILING is a constance config option that controls whether users can enable request profiling
        ALLOW_REQUEST_PROFILING = get_settings_or_config("ALLOW_REQUEST_PROFILING")
        if not ALLOW_REQUEST_PROFILING:
            self.fields["request_profiling"].disabled = True

    def clean(self):
        # ALLOW_REQUEST_PROFILING is a constance config option that controls whether users can enable request profiling
        ALLOW_REQUEST_PROFILING = get_settings_or_config("ALLOW_REQUEST_PROFILING")
        if not ALLOW_REQUEST_PROFILING and self.cleaned_data["request_profiling"]:
            raise forms.ValidationError(
                {"request_profiling": "Request profiling has been globally disabled by an administrator."}
            )


class PreferenceProfileSettingsForm(BootstrapMixin, forms.Form):
    timezone = TimeZoneFormField(required=False, help_text="Set your preferred timezone.", widget=StaticSelect2)


class NavbarFavoritesAddForm(forms.Form):
    link = forms.CharField()
    name = forms.CharField()
    tab_name = forms.CharField()


class NavbarFavoritesRemoveForm(forms.Form):
    link = forms.CharField()


class NavbarFavoritesReorderForm(forms.Form):
    """
    Parse and validate the reordered navbar favorite links, as submitted from the sidenav.
    """

    ordered_links = MultiValueCharField()


class AdminPasswordChangeForm(_AdminPasswordChangeForm):
    def save(self, commit=True):
        # Override `_AdminPasswordChangeForm.save()` to publish admin change user password event
        instance = super().save(commit)
        if commit:
            payload = serialize_user_without_config_and_views(instance)
            publish_event(topic="nautobot.admin.user.change_password", payload=payload)
        return instance


#
# Permission policies
#

#: The declared parameters of a policy, as needed by the rule form. Built from saved parameters or from the
#: (possibly unsaved) parameter formset so that the create and edit flows behave identically.
ParameterSpec = namedtuple("ParameterSpec", ["name", "kind", "target_content_type", "multiple"])

#: Formset prefixes shared by the policy form, its templates and the views that bind the formsets.
PARAMETER_FORMSET_PREFIX = "parameters"
RULE_FORMSET_PREFIX = "rules"

#: Inputs whose values are parameter names the constraint editor should offer, besides the saved ones: the name cells
#: of the policy form's parameter rows, and the hidden names the suggested-paths fragment emits on the rule form.
PARAMETER_NAME_INPUTS_SELECTOR = (
    f"input[name^='{PARAMETER_FORMSET_PREFIX}-'][name$='-name'], input.nb-rule-parameter-name"
)

CRUD_ACTION_CHOICES = (
    ("view", "View"),
    ("add", "Add"),
    ("change", "Change"),
    ("delete", "Delete"),
)


def parameter_specs_from_policy(policy):
    """Return the `ParameterSpec`s of a saved policy."""
    return [
        ParameterSpec(parameter.name, parameter.kind, parameter.target_content_type, parameter.multiple)
        for parameter in policy.parameters.all()
    ]


def parameter_specs_from_formset(formset):
    """Return the `ParameterSpec`s described by a bound parameter formset, skipping deleted and invalid rows."""
    specs = []
    for form in formset.forms:
        if not form.is_valid() or form.cleaned_data.get("DELETE") or not form.cleaned_data.get("name"):
            continue
        data = form.cleaned_data
        specs.append(ParameterSpec(data["name"], data["kind"], data.get("target_content_type"), data.get("multiple")))
    return specs


def suggested_parameter_paths(content_type, parameter_specs):
    """
    For each object-kind parameter, the candidate lookup paths from `content_type` to the parameter's target model.

    Returns:
        (list[tuple[ParameterSpec, str, list[PathCandidate]]]): `(spec, lookup, candidates)`; `candidates` is empty
            when no path exists, and `lookup` is `in` for a multi-valued parameter, else `exact`.
    """
    model = content_type.model_class() if content_type is not None else None
    suggestions = []
    for spec in parameter_specs:
        lookup = "in" if spec.multiple else "exact"
        target_model = spec.target_content_type.model_class() if spec.target_content_type is not None else None
        if target_model is not None and issubclass(target_model, TreeModel):
            # `in_tree` is provisional (see `InTreeLookup`); fall back to `in`/`exact` here if it is withdrawn.
            lookup = "in_tree"  # the selected node(s) and everything beneath them
        if model is None or spec.kind != PolicyParameterKindChoices.KIND_OBJECT or target_model is None:
            suggestions.append((spec, lookup, []))
            continue
        suggestions.append((spec, lookup, find_relation_paths(model, target_model)))
    return suggestions


def add_parameter_fields(form, policy, prefix="param__", initial=None):
    """
    Add one form field per parameter of `policy` to `form`, for entering parameter values.

    Object parameters render as API-backed object selectors on the target model; string parameters as text inputs.
    Multi-valued parameters accept several values.
    """
    initial = initial or {}
    if policy is None:
        return
    for parameter in policy.parameters.all():
        field_name = f"{prefix}{parameter.name}"
        value = initial.get(parameter.name)
        if parameter.kind == PolicyParameterKindChoices.KIND_OBJECT:
            model = parameter.target_content_type.model_class() if parameter.target_content_type_id else None
            if model is None:
                continue
            field_class = DynamicModelMultipleChoiceField if parameter.multiple else DynamicModelChoiceField
            field = field_class(queryset=model._default_manager.all(), required=True)
            help_text = f"{model._meta.verbose_name_plural if parameter.multiple else model._meta.verbose_name}"
        else:
            field = MultiValueCharField(required=True) if parameter.multiple else forms.CharField(required=True)
            help_text = "text values" if parameter.multiple else "text value"
        field.label = parameter.name
        field.help_text = f"Parameter '{parameter.name}': {help_text}"
        if value is not None:
            field.initial = value
        # These fields are added after `BootstrapMixin.__init__` has styled the form, so style them the same way.
        attrs = field.widget.attrs
        if not isinstance(field.widget, (APISelect, APISelectMultiple)):
            attrs["class"] = " ".join(filter(None, [attrs.get("class", ""), "form-control"]))
        attrs.setdefault("placeholder", parameter.name)
        attrs.setdefault("aria-label", parameter.name)
        # Validate on the server: the HTML `required` attribute on a select2 control makes the browser block the
        # submission without any visible message.
        field.widget.use_required_attribute = lambda initial: False
        form.fields[field_name] = field


def parameter_values_from_cleaned_data(cleaned_data, policy, prefix="param__"):
    """Collect the `parameter_values` dict for `policy` from a form's cleaned data."""
    values = {}
    if policy is None:
        return values
    for parameter in policy.parameters.all():
        value = cleaned_data.get(f"{prefix}{parameter.name}")
        if value is None or value == "" or value == []:
            continue
        if parameter.kind == PolicyParameterKindChoices.KIND_OBJECT:
            if parameter.multiple:
                values[parameter.name] = [str(obj.pk) for obj in value]
            else:
                values[parameter.name] = str(value.pk)
        else:
            values[parameter.name] = list(value) if parameter.multiple else value
    return values


def _drop_required_attribute(form):
    """
    Remove the HTML `required` attribute from a formset row's widgets.

    Blank extra rows are ignored server-side, but a `required` attribute on a select2-hidden control makes the browser
    refuse to submit the form with "An invalid form control is not focusable". Server-side validation is unchanged.
    """
    for field in form.fields.values():
        field.widget.attrs.pop("required", None)
        if hasattr(field.widget, "widgets"):
            for sub_widget in field.widget.widgets:
                sub_widget.attrs.pop("required", None)


class PermissionPolicyForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PermissionPolicy
        fields = ("name", "description")


class PolicyParameterForm(BootstrapMixin, forms.ModelForm):
    """
    A parameter of a policy. Serves the parameter's own create and edit pages and, through `PolicyParameterFormSet`
    (which replaces `policy` with the parent link), the rows of the policy form's parameter table.
    """

    policy = DynamicModelChoiceField(queryset=PermissionPolicy.objects.all())
    kind = forms.ChoiceField(
        choices=add_blank_choice(PolicyParameterKindChoices),
        widget=StaticSelect2(),
        help_text="Object: the assignment picks instances of the target object type; the placeholder becomes their "
        "primary keys, so a rule's path must end at that model (e.g. tenant) and renames do not matter. "
        "String: the assignment types free text; the placeholder can sit under any text field "
        "(e.g. tenant__name) and silently stops matching if the text changes.",
    )
    target_content_type = DynamicModelChoiceField(
        queryset=ContentType.objects.all(),
        required=False,
        label="Target object type",
        help_text="Only for an 'object' parameter: the model whose instances the assignment selects.",
    )

    class Meta:
        model = PolicyParameter
        fields = ("policy", "name", "kind", "target_content_type", "multiple")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _drop_required_attribute(self)
        # The parameter rows render as bare table cells, so the accessible name comes from the widget itself.
        for field in self.fields.values():
            field.widget.attrs.setdefault("aria-label", field.label)

    def clean(self):
        super().clean()
        # The object-kind/target consistency check is the model's (`PolicyParameter.clean()`); a string parameter
        # simply drops whatever target the (hidden) select still carried.
        if self.cleaned_data.get("kind") == PolicyParameterKindChoices.KIND_STRING:
            self.cleaned_data["target_content_type"] = None
        return self.cleaned_data


PolicyParameterFormSet = inlineformset_factory(
    parent_model=PermissionPolicy,
    model=PolicyParameter,
    form=PolicyParameterForm,
    extra=0,  # the form renders `empty_form` as a hidden template row and adds rows client-side
    can_delete=True,
)


class PolicyContentTypeSelect(StaticSelect2):
    """A content type select whose options carry `data-content-type="app_label.model"` for client-side scripts."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-content-type"] = f"{instance.app_label}.{instance.model}"
        return option


def _policy_from_form(form):
    """The policy a bound or initial-populated form refers to, or None (shared by the rule and assignment forms)."""
    policy_pk = None
    if form.is_bound:
        policy_pk = form.data.get(form.add_prefix("policy"))
    if not policy_pk and getattr(form.instance, "policy_id", None):
        return form.instance.policy
    if not policy_pk:
        policy_pk = form.initial.get("policy")
    if not policy_pk:
        return None
    if isinstance(policy_pk, PermissionPolicy):
        return policy_pk
    return PermissionPolicy.objects.filter(pk=policy_pk).first()


class PolicyRuleForm(BootstrapMixin, forms.ModelForm):
    """
    One rule: an object type, the actions granted on it and the constraint template.

    The `path_map` is derived from the template (every `{{ parameter }}` placeholder yields the path and lookup of
    the key it sits under), so the author edits one thing. The form serves the rule's own create and edit pages and,
    through `PolicyRuleFormSet` (which replaces `policy` with the parent link), the rows of the policy form's rule
    editor, where the parameters may not be saved yet and are passed in as `parameter_specs`.
    """

    policy = DynamicModelChoiceField(queryset=PermissionPolicy.objects.all())
    content_type = forms.ModelChoiceField(
        queryset=ContentType.objects.filter(PERMISSION_OBJECT_TYPE_LIMIT_CHOICES).order_by("app_label", "model"),
        widget=PolicyContentTypeSelect(),
        label="Object type",
    )
    actions = forms.MultipleChoiceField(
        choices=CRUD_ACTION_CHOICES,
        required=False,
        widget=StaticSelect2Multiple(),
    )
    additional_actions = MultiValueCharField(
        required=False,
        help_text="Custom actions such as 'run'",
    )
    constraint_template = ConstraintEditorField(
        required=False,
        content_type_source="$content_type",
        parameter_inputs_selector=PARAMETER_NAME_INPUTS_SELECTOR,
        label="Constraint template",
    )

    class Meta:
        model = PolicyRule
        fields = ("policy", "content_type", "actions", "constraint_template")

    def __init__(self, *args, parameter_specs=None, **kwargs):
        super().__init__(*args, **kwargs)
        _drop_required_attribute(self)
        if self.instance.present_in_database:
            crud_actions = [action for action, _ in CRUD_ACTION_CHOICES]
            self.initial["actions"] = [action for action in self.instance.actions if action in crud_actions]
            self.initial["additional_actions"] = [
                action for action in self.instance.actions if action not in crud_actions
            ]
        if parameter_specs is None:
            policy = _policy_from_form(self)
            parameter_specs = parameter_specs_from_policy(policy) if policy is not None else []
        self.parameter_specs = list(parameter_specs)
        names = [spec.name for spec in self.parameter_specs]
        self.fields["constraint_template"].parameter_names = names
        self.fields["constraint_template"].widget.attrs["data-parameters"] = ",".join(names)

    def add_error(self, field, error):
        # The model validates `path_map`, which this form derives rather than exposes; show those messages at the
        # form level instead of failing on an unknown field.
        if field is None and isinstance(error, ValidationError) and hasattr(error, "error_dict"):
            remapped = {}
            for key, messages in error.error_dict.items():
                target = key if key in self.fields or key == NON_FIELD_ERRORS else NON_FIELD_ERRORS
                remapped.setdefault(target, []).extend(messages)
            error = ValidationError(remapped)
        elif field is not None and field != NON_FIELD_ERRORS and field not in self.fields:
            field = None
        super().add_error(field, error)

    def clean(self):
        super().clean()
        actions = list(self.cleaned_data.get("actions") or [])
        for action in self.cleaned_data.get("additional_actions") or []:
            if action and action not in actions:
                actions.append(action)
        if not actions:
            self.add_error("actions", "At least one action must be selected.")
        self.cleaned_data["actions"] = actions

        template = self.cleaned_data.get("constraint_template")
        if template in (None, ""):
            template = {}
        self.cleaned_data["constraint_template"] = template
        content_type = self.cleaned_data.get("content_type")
        model = content_type.model_class() if content_type is not None else None
        self.instance.path_map = self._derive_path_map(model, template)
        # The model's clean() validates the template against these parameters, saved or not.
        self.instance._pending_parameters = {spec.name: spec for spec in self.parameter_specs}
        return self.cleaned_data

    def _derive_path_map(self, model, template):
        """Every `{{ name }}` placeholder in the template gives the path map one entry: its key split into path and lookup."""
        path_map = {}
        groups = template if isinstance(template, list) else [template]
        for group in groups:
            if not isinstance(group, dict):
                continue
            for key, value in group.items():
                match = CONSTRAINT_PLACEHOLDER_PATTERN.match(value) if isinstance(value, str) else None
                if match is None or model is None:
                    continue
                path, lookup = split_path_and_lookup(model, key)
                path_map[match.group(1)] = {"path": path, "lookup": lookup}
        return path_map


class BasePolicyRuleFormSet(forms.BaseInlineFormSet):
    """Rules formset: an object type may appear in only one row."""

    def clean(self):
        # Checked before Django's own unique_together pass so the message names the object type.
        seen = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            content_type = form.cleaned_data.get("content_type")
            if content_type is None:
                continue
            if content_type.pk in seen:
                raise ValidationError(
                    f"Object type '{content_type}' appears in more than one rule; each object type may have "
                    "only one rule per policy."
                )
            seen.add(content_type.pk)
        super().clean()


def rule_formset_class(extra=0):
    """`PolicyRuleFormSet` with `extra` blank forms, so prefilled (cloned) rows have forms to occupy."""
    return inlineformset_factory(
        parent_model=PermissionPolicy,
        model=PolicyRule,
        form=PolicyRuleForm,
        formset=BasePolicyRuleFormSet,
        extra=extra,
        can_delete=True,
    )


PolicyRuleFormSet = rule_formset_class()


def policy_parameter_rows(policy):
    """Initial data for `PolicyParameterFormSet` copied from an existing policy (used when cloning)."""
    return [
        {
            "name": parameter.name,
            "kind": parameter.kind,
            "target_content_type": parameter.target_content_type_id,
            "multiple": parameter.multiple,
        }
        for parameter in policy.parameters.select_related("target_content_type")
    ]


def parameter_formset_class(extra=0):
    """`PolicyParameterFormSet` with `extra` blank forms, so prefilled (cloned) rows have forms to occupy."""
    if extra == 0:
        return PolicyParameterFormSet
    return inlineformset_factory(
        parent_model=PermissionPolicy,
        model=PolicyParameter,
        form=PolicyParameterForm,
        extra=extra,
        can_delete=True,
    )


def policy_rule_rows(policy):
    """Initial data for `PolicyRuleFormSet` copied from an existing policy's rules (used when cloning)."""
    crud_actions = [action for action, _ in CRUD_ACTION_CHOICES]
    return [
        {
            "content_type": rule.content_type_id,
            "actions": [action for action in rule.actions if action in crud_actions],
            "additional_actions": [action for action in rule.actions if action not in crud_actions],
            "constraint_template": rule.constraint_template,
        }
        for rule in policy.rules.select_related("content_type").order_by(
            "content_type__app_label", "content_type__model"
        )
    ]


class PermissionPolicyBulkEditForm(BootstrapMixin, BulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=PermissionPolicy.objects.all(), widget=forms.MultipleHiddenInput())
    description = forms.CharField(max_length=255, required=False)

    class Meta:
        nullable_fields = ["description"]


class PermissionPolicyFilterForm(NautobotFilterForm):
    model = PermissionPolicy
    field_order = ["q", "name", "content_types", "has_assignments"]

    q = forms.CharField(required=False, label="Search")
    name = MultiValueCharField(required=False)
    content_types = MultipleContentTypeField(
        required=False,
        label="Object types",
        queryset=ContentType.objects.filter(PERMISSION_OBJECT_TYPE_LIMIT_CHOICES),
    )
    has_assignments = forms.NullBooleanField(
        required=False,
        widget=StaticSelect2(choices=BOOLEAN_WITH_BLANK_CHOICES),
    )


class PolicyParameterFilterForm(NautobotFilterForm):
    model = PolicyParameter
    field_order = ["q", "policy", "kind", "target_content_type", "multiple"]

    q = forms.CharField(required=False, label="Search")
    policy = DynamicModelMultipleChoiceField(
        queryset=PermissionPolicy.objects.all(), to_field_name="name", required=False
    )
    kind = forms.ChoiceField(
        choices=add_blank_choice(PolicyParameterKindChoices), required=False, widget=StaticSelect2()
    )
    target_content_type = forms.ModelChoiceField(
        queryset=ContentType.objects.all().order_by("app_label", "model"),
        required=False,
        label="Target object type",
        widget=StaticSelect2(),
    )
    multiple = forms.NullBooleanField(required=False, widget=StaticSelect2(choices=BOOLEAN_WITH_BLANK_CHOICES))


class PolicyRuleFilterForm(NautobotFilterForm):
    model = PolicyRule
    field_order = ["q", "policy", "content_type"]

    q = forms.CharField(required=False, label="Search")
    policy = DynamicModelMultipleChoiceField(
        queryset=PermissionPolicy.objects.all(), to_field_name="name", required=False
    )
    content_type = forms.ModelChoiceField(
        queryset=ContentType.objects.filter(PERMISSION_OBJECT_TYPE_LIMIT_CHOICES).order_by("app_label", "model"),
        required=False,
        label="Object type",
        widget=StaticSelect2(),
    )


class PolicyAssignmentForm(BootstrapMixin, forms.ModelForm):
    """
    Bind a policy to parameter values and to users and groups.

    Parameter value fields are generated from the selected policy. On the create form they are swapped in over
    HTMX when the policy changes; on the edit form the policy cannot change.
    """

    policy = DynamicModelChoiceField(
        queryset=PermissionPolicy.objects.all(),
        query_params={"has_rules": True},
    )
    users = DynamicModelMultipleChoiceField(queryset=get_user_model().objects.all(), required=False)
    groups = DynamicModelMultipleChoiceField(queryset=Group.objects.all(), required=False)
    # Derived in clean() from the per-parameter fields; present so model validation errors attach to the form.
    parameter_values = forms.JSONField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = PolicyAssignment
        fields = ("policy", "name", "description", "enabled", "users", "groups", "parameter_values")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.selected_policy = self._resolve_policy()
        if self.instance.present_in_database:
            self.fields["policy"].disabled = True
        add_parameter_fields(self, self.selected_policy, initial=self.instance.parameter_values or {})

    def _resolve_policy(self):
        return _policy_from_form(self)

    @property
    def parameter_fields(self):
        """The bound parameter-value fields, for rendering as a group."""
        return [self[name] for name in self.fields if name.startswith("param__")]

    def clean(self):
        super().clean()
        policy = self.cleaned_data.get("policy") or self.selected_policy
        self.cleaned_data["parameter_values"] = (
            parameter_values_from_cleaned_data(self.cleaned_data, policy) if policy is not None else {}
        )
        return self.cleaned_data

    def _post_clean(self):
        super()._post_clean()
        # Model validation reports value problems against the hidden `parameter_values` field; show each message
        # beside the parameter it names (the messages quote the parameter name) so the author can see it.
        for message in self._errors.pop("parameter_values", []):
            match = re.search(r"'([a-z][a-z0-9_]*)'", str(message))
            target = f"param__{match.group(1)}" if match else None
            if target in self.fields and message not in self.errors.get(target, []):
                self.add_error(target, message)
            elif target not in self.fields:
                self.add_error(None, message)


class PolicyAssignmentBulkEditForm(BootstrapMixin, BulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=PolicyAssignment.objects.all(), widget=forms.MultipleHiddenInput())
    enabled = forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect())
    description = forms.CharField(max_length=255, required=False)

    class Meta:
        nullable_fields = ["description"]


class PolicyAssignmentFilterForm(NautobotFilterForm):
    model = PolicyAssignment
    field_order = ["q", "name", "policy", "enabled", "users", "groups"]

    q = forms.CharField(required=False, label="Search")
    name = MultiValueCharField(required=False)
    policy = DynamicModelMultipleChoiceField(
        queryset=PermissionPolicy.objects.all(), to_field_name="name", required=False
    )
    enabled = forms.NullBooleanField(required=False, widget=StaticSelect2(choices=BOOLEAN_WITH_BLANK_CHOICES))
    users = DynamicModelMultipleChoiceField(
        queryset=get_user_model().objects.all(), to_field_name="username", required=False
    )
    groups = DynamicModelMultipleChoiceField(queryset=Group.objects.all(), to_field_name="name", required=False)


class PolicyPreviewForm(BootstrapMixin, forms.Form):
    """Parameter values for previewing a policy before it is assigned."""

    def __init__(self, policy, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.policy = policy
        add_parameter_fields(self, policy)

    def cleaned_parameter_values(self):
        return parameter_values_from_cleaned_data(self.cleaned_data, self.policy)
