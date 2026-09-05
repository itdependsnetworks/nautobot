from django import forms
from django.contrib.auth.forms import (
    AdminPasswordChangeForm as _AdminPasswordChangeForm,
    AuthenticationForm,
    PasswordChangeForm as DjangoPasswordChangeForm,
)
from timezone_field import TimeZoneFormField

from nautobot.core.events import publish_event
from nautobot.core.forms import (
    BootstrapMixin,
    BulkEditForm,
    DateTimePicker,
    MultiValueCharField,
)
from nautobot.core.forms.widgets import StaticSelect2
from nautobot.core.utils.config import get_settings_or_config
from nautobot.extras.forms import NautobotFilterForm
from nautobot.users.utils import serialize_user_without_config_and_views

from .models import (
    PermissionPolicy,
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
#: Inputs whose values are parameter names the constraint editor should offer, besides the saved ones: the name cells
#: of the policy form's parameter rows, and the hidden names the suggested-paths fragment emits on the rule form.
class PermissionPolicyForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PermissionPolicy
        fields = ("name", "description")


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
