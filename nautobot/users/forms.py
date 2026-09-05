from django import forms
from django.contrib.auth.forms import (
    AdminPasswordChangeForm as _AdminPasswordChangeForm,
    AuthenticationForm,
    PasswordChangeForm as DjangoPasswordChangeForm,
)
from django.contrib.contenttypes.models import ContentType
from django.forms import inlineformset_factory
from timezone_field import TimeZoneFormField

from nautobot.core.events import publish_event
from nautobot.core.forms import (
    add_blank_choice,
    BOOLEAN_WITH_BLANK_CHOICES,
    BootstrapMixin,
    BulkEditForm,
    DateTimePicker,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    MultiValueCharField,
)
from nautobot.core.forms.widgets import StaticSelect2
from nautobot.core.utils.config import get_settings_or_config
from nautobot.extras.forms import NautobotFilterForm
from nautobot.users.choices import PolicyParameterKindChoices
from nautobot.users.utils import serialize_user_without_config_and_views

from .models import (
    PermissionPolicy,
    PolicyParameter,
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
#: Formset prefixes shared by the policy form, its templates and the views that bind the formsets.
PARAMETER_FORMSET_PREFIX = "parameters"


#: Inputs whose values are parameter names the constraint editor should offer, besides the saved ones: the name cells
#: of the policy form's parameter rows, and the hidden names the suggested-paths fragment emits on the rule form.
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


class PermissionPolicyBulkEditForm(BootstrapMixin, BulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=PermissionPolicy.objects.all(), widget=forms.MultipleHiddenInput())
    description = forms.CharField(max_length=255, required=False)

    class Meta:
        nullable_fields = ["description"]


class PermissionPolicyFilterForm(NautobotFilterForm):
    model = PermissionPolicy
    field_order = ["q", "name"]

    q = forms.CharField(required=False, label="Search")
    name = MultiValueCharField(required=False)


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
