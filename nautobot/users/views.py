from http import HTTPStatus
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash,
)
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.encoding import iri_to_uri
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import get_default_timezone_name
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import View
from rest_framework.decorators import action

from nautobot.core.choices import NautobotEditionChoices
from nautobot.core.constants import NAUTOBOT_EDITION_URLS
from nautobot.core.events import publish_event
from nautobot.core.forms import ConfirmationForm
from nautobot.core.models.querysets import count_related
from nautobot.core.ui import object_detail
from nautobot.core.ui.choices import SectionChoices
from nautobot.core.ui.titles import Titles
from nautobot.core.utils.config import get_nautobot_edition
from nautobot.core.views.generic import GenericView
from nautobot.core.views.mixins import (
    ObjectBulkCreateViewMixin,
    ObjectBulkDestroyViewMixin,
    ObjectBulkRenameViewMixin,
    ObjectBulkUpdateViewMixin,
    ObjectChangeLogViewMixin,
    ObjectDestroyViewMixin,
    ObjectDetailViewMixin,
    ObjectEditViewMixin,
    ObjectListViewMixin,
    ObjectOverviewViewMixin,
)
from nautobot.users import filters as users_filters, tables as users_tables
from nautobot.users.api import serializers as users_serializers
from nautobot.users.utils import serialize_user_without_config_and_views

from ..core.views.mixins import GetReturnURLMixin
from .forms import (
    AdvancedProfileSettingsForm,
    LoginForm,
    NavbarFavoritesAddForm,
    NavbarFavoritesRemoveForm,
    NavbarFavoritesReorderForm,
    parameter_formset_class,
    parameter_specs_from_formset,
    parameter_specs_from_policy,
    PasswordChangeForm,
    PermissionPolicyBulkEditForm,
    PermissionPolicyFilterForm,
    PermissionPolicyForm,
    policy_parameter_rows,
    policy_rule_rows,
    PolicyParameterFilterForm,
    PolicyParameterForm,
    PolicyParameterFormSet,
    PolicyRuleFilterForm,
    PolicyRuleForm,
    PolicyRuleFormSet,
    PreferenceProfileSettingsForm,
    rule_formset_class,
    suggested_parameter_paths,
    TokenForm,
)
from .models import PermissionPolicy, PolicyParameter, PolicyRule, Token

#
# Login/logout
#


class LoginView(View):
    """
    Perform user authentication via the web UI.
    """

    template_name = "login.html"

    @method_decorator(sensitive_post_parameters("password"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def show_edition_badge(self, edition):
        """Show the edition badge only for a commercial edition with no custom branding logo overriding the stock logo."""
        has_custom_logo = bool(settings.BRANDING_FILEPATHS.get("logo"))
        is_commercial_edition = edition in NautobotEditionChoices.COMMERCIAL_EDITIONS
        return is_commercial_edition and not has_custom_logo

    def get(self, request):
        form = LoginForm(request)

        if request.user.is_authenticated:
            logger = logging.getLogger("nautobot.auth.login")
            return self.redirect_to_next(request, logger)

        edition = get_nautobot_edition()
        edition_display = NautobotEditionChoices.as_dict().get(edition, edition)
        is_commercial_edition = edition in NautobotEditionChoices.COMMERCIAL_EDITIONS

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "title": "Login",
                "nautobot_edition": edition_display,
                "is_commercial_edition": is_commercial_edition,
                "edition_url": NAUTOBOT_EDITION_URLS.get(edition, "https://nautobot.com"),
                "show_edition_badge": self.show_edition_badge(edition),
            },
        )

    def post(self, request):
        logger = logging.getLogger("nautobot.auth.login")
        form = LoginForm(request, data=request.POST)

        if form.is_valid():
            logger.debug("Login form validation was successful")

            # Authenticate user
            user = form.get_user()
            auth_login(request, form.get_user())
            messages.info(request, f"Logged in as {request.user}.")
            payload = serialize_user_without_config_and_views(user)
            publish_event(topic="nautobot.users.user.login", payload=payload)

            return self.redirect_to_next(request, logger)

        else:
            logger.debug("Login form validation failed")

        edition = get_nautobot_edition()
        edition_display = NautobotEditionChoices.as_dict().get(edition, edition)
        is_commercial_edition = edition in NautobotEditionChoices.COMMERCIAL_EDITIONS

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "title": "Login",
                "nautobot_edition": edition_display,
                "is_commercial_edition": is_commercial_edition,
                "edition_url": NAUTOBOT_EDITION_URLS.get(edition, "https://nautobot.com"),
                "show_edition_badge": self.show_edition_badge(edition),
            },
        )

    def redirect_to_next(self, request, logger):
        if request.method == "POST":
            redirect_to = request.POST.get("next", reverse("home"))
        else:
            redirect_to = request.GET.get("next", reverse("home"))

        if redirect_to and not url_has_allowed_host_and_scheme(url=redirect_to, allowed_hosts=request.get_host()):
            logger.warning(f"Ignoring unsafe 'next' URL passed to login form: {redirect_to}")
            redirect_to = reverse("home")

        logger.debug(f"Redirecting user to {redirect_to}")
        return HttpResponseRedirect(iri_to_uri(redirect_to))


# TODO: The LogoutView should inherit from `LoginRequiredMixin` or `GenericView`
#   to prevent unauthenticated users from accessing the logout page.
#   However, using `LoginRequiredMixin` or `GenericView` as-is currently redirects
#   users to the login page with `?next=/logout/`, which is not desired.
class LogoutView(View):
    """
    Deauthenticate a web user.
    """

    def get(self, request):
        # Log out the user
        if request.user.is_authenticated:
            payload = serialize_user_without_config_and_views(request.user)
            publish_event(topic="nautobot.users.user.logout", payload=payload)
        auth_logout(request)
        messages.info(request, "You have logged out.")

        # Delete session key cookie (if set) upon logout
        response = HttpResponseRedirect(reverse("home"))
        response.delete_cookie("session_key")

        return response


#
# User profiles
#


def is_django_auth_user(request):
    return request.session.get(BACKEND_SESSION_KEY, None) == "nautobot.core.authentication.ObjectPermissionBackend"


class ProfileView(GenericView):
    template_name = "users/profile.html"
    view_titles = Titles(titles={"*": "User Profile"})

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "is_django_auth_user": is_django_auth_user(request),
                "active_tab": "profile",
                "view_titles": self.get_view_titles(),
                "breadcrumbs": self.get_breadcrumbs(),
            },
        )


class UserConfigView(GenericView):
    template_name = "users/preferences.html"
    view_titles = Titles(titles={"*": "User Preferences"})

    def get(self, request):
        initial = {}
        initial["timezone"] = request.user.get_config("timezone", get_default_timezone_name())
        form = PreferenceProfileSettingsForm(initial=initial)
        preferences = request.user.all_config()

        return render(
            request,
            self.template_name,
            {
                "preferences": preferences,
                "form": form,
                "active_tab": "preferences",
                "is_django_auth_user": is_django_auth_user(request),
                "view_titles": self.get_view_titles(),
                "breadcrumbs": self.get_breadcrumbs(),
            },
        )

    def post(self, request):
        is_preference_update_post = "_update_preference_form" in request.POST
        if is_preference_update_post:
            form = PreferenceProfileSettingsForm(request.POST)
            if form.is_valid():
                response = redirect("user:preferences")
                if timezone := form.cleaned_data["timezone"]:
                    request.user.set_config("timezone", str(timezone), commit=True)
                return response

            return render(
                request,
                self.template_name,
                {
                    "preferences": request.user.all_config(),
                    "form": form,
                    "active_tab": "preferences",
                    "is_django_auth_user": is_django_auth_user(request),
                },
            )

        else:
            user = request.user
            data = user.all_config()

            # Delete selected preferences
            for key in request.POST.getlist("pk"):
                if key in data:
                    user.clear_config(key)
            user.save()
            messages.success(request, "Your preferences have been updated.")

            return redirect("user:preferences")


class UserNavbarFavoritesAddView(GetReturnURLMixin, GenericView):
    def post(self, request):
        if request.headers.get("HX-Request", False):
            form = NavbarFavoritesAddForm(request.POST)
            if form.is_valid():
                navbar_favorites = request.user.get_config("navbar_favorites", [])
                navbar_favorites.append(form.cleaned_data)
                request.user.set_config("navbar_favorites", navbar_favorites, commit=True)

                return render(
                    request,
                    "inc/nav_menu.html",
                    status=HTTPStatus.CREATED,
                )

        return redirect(self.get_return_url(request))


class UserNavbarFavoritesDeleteView(GetReturnURLMixin, GenericView):
    def post(self, request):
        if request.headers.get("HX-Request", False):
            form = NavbarFavoritesRemoveForm(request.POST)
            if form.is_valid():
                navbar_favorites = request.user.get_config("navbar_favorites", [])
                navbar_favorites = [item for item in navbar_favorites if item.get("link") != form.cleaned_data["link"]]
                request.user.set_config("navbar_favorites", navbar_favorites, commit=True)

                return render(
                    request,
                    "inc/nav_menu.html",
                    status=HTTPStatus.OK,
                )

        return redirect(self.get_return_url(request))


class UserNavbarFavoritesReorderView(GetReturnURLMixin, GenericView):
    def post(self, request):
        if request.headers.get("HX-Request", False):
            form = NavbarFavoritesReorderForm(request.POST)
            if form.is_valid():
                favorites_by_link = {favorite.get("link"): favorite for favorite in request.user.navbar_favorites}
                # `link` as key, while iterating over a concatenated list of posted and stored links, prioritizes the
                # posted order, collapses duplicates, and appends any potential omissions to the end.
                reordered = {
                    link: favorites_by_link[link]
                    for link in [*form.cleaned_data["ordered_links"], *favorites_by_link]
                    if link in favorites_by_link
                }

                request.user.set_config("navbar_favorites", list(reordered.values()), commit=True)

                return HttpResponse(status=HTTPStatus.NO_CONTENT)

        return redirect(self.get_return_url(request))


class ChangePasswordView(GenericView):
    template_name = "users/change_password.html"
    view_titles = Titles(titles={"*": "Change Password"})

    RESTRICTED_NOTICE = "Remotely authenticated user credentials cannot be changed within Nautobot."

    def get(self, request):
        # Non-Django authentication users cannot change their password here
        if not is_django_auth_user(request):
            messages.warning(
                request,
                self.RESTRICTED_NOTICE,
            )
            return redirect("user:profile")

        form = PasswordChangeForm(user=request.user)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "active_tab": "change_password",
                "is_django_auth_user": is_django_auth_user(request),
                "view_titles": self.get_view_titles(),
                "breadcrumbs": self.get_breadcrumbs(),
            },
        )

    def post(self, request):
        # Non-Django authentication users cannot change their password here
        if not is_django_auth_user(request):
            messages.warning(
                request,
                self.RESTRICTED_NOTICE,
            )
            return redirect("user:profile")

        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            messages.success(request, "Your password has been changed successfully.")
            payload = serialize_user_without_config_and_views(request.user)
            publish_event(topic="nautobot.users.user.change_password", payload=payload)
            return redirect("user:profile")

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "active_tab": "change_password",
                "is_django_auth_user": is_django_auth_user(request),
            },
        )


#
# API tokens
#


class TokenListView(GenericView):
    view_titles = Titles(titles={"*": "API Tokens"})

    def get(self, request):
        tokens = Token.objects.filter(user=request.user)

        return render(
            request,
            "users/api_tokens.html",
            {
                "tokens": tokens,
                "active_tab": "api_tokens",
                "is_django_auth_user": is_django_auth_user(request),
                "view_titles": self.get_view_titles(),
                "breadcrumbs": self.get_breadcrumbs(),
            },
        )


class TokenEditView(GenericView):
    def get(self, request, pk=None):
        if pk is not None:
            if not request.user.has_perm("users.change_token"):
                return HttpResponseForbidden()
            token = get_object_or_404(Token.objects.filter(user=request.user), pk=pk)
        else:
            if not request.user.has_perm("users.add_token"):
                return HttpResponseForbidden()
            token = Token(user=request.user)

        form = TokenForm(instance=token)

        return render(
            request,
            "generic/object_create.html",
            {
                "obj": token,
                "obj_type": token._meta.verbose_name,
                "form": form,
                "return_url": reverse("user:token_list"),
                "editing": token.present_in_database,
            },
        )

    def post(self, request, pk=None):
        if pk is not None:
            token = get_object_or_404(Token.objects.filter(user=request.user), pk=pk)
            form = TokenForm(request.POST, instance=token)
        else:
            token = Token()
            form = TokenForm(request.POST)

        if form.is_valid():
            token = form.save(commit=False)
            token.user = request.user
            token.save()

            msg = f"Modified token {token}" if pk else f"Created token {token}"
            messages.success(request, msg)

            if "_addanother" in request.POST:
                return redirect(request.path)
            else:
                return redirect("user:token_list")

        return render(
            request,
            "generic/object_create.html",
            {
                "obj": token,
                "obj_type": token._meta.verbose_name,
                "form": form,
                "return_url": reverse("user:token_list"),
                "editing": token.present_in_database,
            },
        )


class TokenDeleteView(GenericView):
    def get(self, request, pk):
        token = get_object_or_404(Token.objects.filter(user=request.user), pk=pk)
        initial_data = {
            "return_url": reverse("user:token_list"),
        }
        form = ConfirmationForm(initial=initial_data)

        return render(
            request,
            "generic/object_destroy.html",
            {
                "obj": token,
                "obj_type": token._meta.verbose_name,
                "form": form,
                "return_url": reverse("user:token_list"),
            },
        )

    def post(self, request, pk):
        token = get_object_or_404(Token.objects.filter(user=request.user), pk=pk)
        form = ConfirmationForm(request.POST)
        if form.is_valid():
            token.delete()
            messages.success(request, "Token deleted")
            return redirect("user:token_list")

        return render(
            request,
            "generic/object_destroy.html",
            {
                "obj": token,
                "obj_type": token._meta.verbose_name,
                "form": form,
                "return_url": reverse("user:token_list"),
            },
        )


#
# Advanced Profile Settings
#


class AdvancedProfileSettingsEditView(GenericView):
    template_name = "users/advanced_settings_edit.html"
    view_titles = Titles(titles={"*": "Advanced Settings"})

    def get(self, request):
        silk_record_requests = request.session.get("silk_record_requests", False)
        form = AdvancedProfileSettingsForm(initial={"request_profiling": silk_record_requests})

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "active_tab": "advanced_settings",
                "return_url": reverse("user:advanced_settings_edit"),
                "is_django_auth_user": is_django_auth_user(request),
                "view_titles": self.get_view_titles(),
                "breadcrumbs": self.get_breadcrumbs(),
            },
        )

    def post(self, request):
        form = AdvancedProfileSettingsForm(request.POST)

        if form.is_valid():
            silk_record_requests = form.cleaned_data["request_profiling"]

            # Set the value for `silk_record_requests` in the session
            request.session["silk_record_requests"] = silk_record_requests

            if silk_record_requests:
                msg = "Enabled request profiling for the duration of the login session."
            else:
                msg = "Disabled request profiling."
            messages.success(request, msg)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "active_tab": "advanced_settings",
                "return_url": reverse("user:advanced_settings_edit"),
                "is_django_auth_user": is_django_auth_user(request),
            },
        )


#
# Permission policies
#


# PLACEHOLDER: will be replaced in C13 (Policy assignment validation and warnings): warn about assignments
# that lack a value for a parameter added after them.


class PolicyUIViewSetBase(
    ObjectDetailViewMixin,
    ObjectListViewMixin,
    ObjectEditViewMixin,
    ObjectDestroyViewMixin,
    ObjectBulkDestroyViewMixin,
    ObjectBulkCreateViewMixin,
    ObjectBulkUpdateViewMixin,
    ObjectBulkRenameViewMixin,
    ObjectChangeLogViewMixin,
    ObjectOverviewViewMixin,
):
    """`NautobotUIViewSet` minus the Notes and Data Compliance views, which these models do not support."""


class PolicyChildUIViewSetBase(
    ObjectDetailViewMixin,
    ObjectListViewMixin,
    ObjectEditViewMixin,
    ObjectDestroyViewMixin,
    ObjectBulkDestroyViewMixin,
    ObjectBulkCreateViewMixin,
    ObjectChangeLogViewMixin,
    ObjectOverviewViewMixin,
):
    """
    Views of a policy's parameters and rules: as `PolicyUIViewSetBase` without bulk edit and bulk rename, since
    neither model has a field that is sensibly changed across many records at once.
    """


class PermissionPolicyUIViewSet(PolicyUIViewSetBase):
    bulk_update_form_class = PermissionPolicyBulkEditForm
    filterset_class = users_filters.PermissionPolicyFilterSet
    filterset_form_class = PermissionPolicyFilterForm
    form_class = PermissionPolicyForm
    queryset = PermissionPolicy.objects.all()
    serializer_class = users_serializers.PermissionPolicySerializer
    table_class = users_tables.PermissionPolicyTable

    object_detail_content = object_detail.ObjectDetailContent(
        panels=(
            object_detail.ObjectFieldsPanel(
                section=SectionChoices.LEFT_HALF,
                weight=100,
                fields=("name", "description"),
            ),
            object_detail.ObjectsTablePanel(
                section=SectionChoices.RIGHT_HALF,
                weight=100,
                table_class=users_tables.PolicyParameterTable,
                table_filter="policy",
                table_title="Parameters",
                exclude_columns=("policy",),
                select_related_fields=("target_content_type",),
            ),
            object_detail.ObjectsTablePanel(
                section=SectionChoices.FULL_WIDTH,
                weight=200,
                table_class=users_tables.PolicyRuleTable,
                table_filter="policy",
                table_title="Rules",
                exclude_columns=("policy",),
                select_related_fields=("content_type",),
                # The parameter-paths column lists, per rule, the parameters it does not use.
                prefetch_related_fields=("policy__parameters",),
            ),
        ),
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in ("list", "bulk_update", "bulk_destroy"):
            # The same table renders the list and the bulk confirmation pages; subquery counts avoid the join
            # cross-product that three `Count(distinct=True)` annotations would produce.
            queryset = queryset.prefetch_related("rules__content_type").annotate(
                parameter_count=count_related(PolicyParameter, "policy"),
                rule_count=count_related(PolicyRule, "policy"),
            )
        return queryset

    def _clone_source(self, request, instance):
        """The policy named by `?clone_from=` on the create form (the standard Clone flow), if any."""
        if request.method != "GET" or instance.present_in_database:
            return None
        pk = request.GET.get("clone_from")
        if not pk:
            return None
        return PermissionPolicy.objects.restrict(request.user, "view").filter(pk=pk).first()

    def _parameter_formset(self, request, instance):
        if request.method == "POST":
            return PolicyParameterFormSet(data=request.POST, instance=instance, prefix="parameters")
        source = self._clone_source(request, instance)
        if source is not None:
            initial = policy_parameter_rows(source)
            return parameter_formset_class(extra=len(initial))(instance=instance, prefix="parameters", initial=initial)
        return PolicyParameterFormSet(instance=instance, prefix="parameters")

    def _rule_formset(self, request, instance, specs):
        kwargs = {"instance": instance, "prefix": "rules", "form_kwargs": {"parameter_specs": specs}}
        if request.method == "POST":
            return PolicyRuleFormSet(data=request.POST, **kwargs)
        source = self._clone_source(request, instance)
        if source is not None:
            initial = policy_rule_rows(source)
            return rule_formset_class(extra=len(initial))(initial=initial, **kwargs)
        return PolicyRuleFormSet(**kwargs)

    def get_extra_context(self, request, instance):
        context = super().get_extra_context(request, instance)
        if self.action in ("create", "update"):
            parameters = self._parameter_formset(request, instance)
            if request.method == "POST":
                specs = parameter_specs_from_formset(parameters)
            elif instance.present_in_database:
                specs = parameter_specs_from_policy(instance)
            else:
                source = self._clone_source(request, instance)
                specs = parameter_specs_from_policy(source) if source is not None else []
            context["parameters"] = parameters
            context["rules"] = self._rule_formset(request, instance, specs)
            context["rule_paths_url"] = reverse("users:permissionpolicy_rule_paths")
        return context

    def form_save(self, form, **kwargs):
        with transaction.atomic():
            obj = super().form_save(form, **kwargs)
            parameters = self._parameter_formset(self.request, obj)
            if not parameters.is_valid():
                # Row-level errors are rendered beside their fields; the message only points at the table.
                raise ValidationError(
                    list(parameters.non_form_errors()) or ["Correct the errors in the parameters table."]
                )
            parameters.save()
            obj.refresh_from_db()
            rules = self._rule_formset(self.request, obj, parameter_specs_from_policy(obj))
            if not rules.is_valid():
                raise ValidationError(list(rules.non_form_errors()) or ["Correct the errors in the rules below."])
            rules.save()
            obj.refresh_from_db()
        return obj

    @action(detail=False, methods=["get"], url_path="rule-paths", url_name="rule_paths", custom_view_base_action="view")
    def rule_paths(self, request, *args, **kwargs):
        """
        HTMX fragment: candidate lookup paths from a rule's object type to each declared parameter.

        The rule's own form names its saved policy (`?policy=<pk>`); the policy form's rule rows instead pass the
        (possibly unsaved) parameter formset in the query string, so the fragment works before anything is saved.
        """
        content_type_pks = [pk for pk in request.GET.getlist("content_type") if pk]
        content_types = list(ContentType.objects.filter(pk__in=content_type_pks).order_by("app_label", "model"))
        policy_pk = request.GET.get("policy")
        if policy_pk:
            policy = PermissionPolicy.objects.restrict(request.user, "view").filter(pk=policy_pk).first()
            specs = parameter_specs_from_policy(policy) if policy is not None else []
        else:
            specs = parameter_specs_from_formset(PolicyParameterFormSet(data=request.GET, prefix="parameters"))
        suggestions = [(content_type, suggested_parameter_paths(content_type, specs)) for content_type in content_types]
        return render(
            request,
            "users/inc/policy_rule_paths.html",
            {
                "content_types": content_types,
                "specs": specs,
                "suggestions": suggestions,
                "prefix": request.GET.get("prefix", ""),
            },
        )


class PolicyParameterUIViewSet(PolicyChildUIViewSetBase):
    filterset_class = users_filters.PolicyParameterFilterSet
    filterset_form_class = PolicyParameterFilterForm
    form_class = PolicyParameterForm
    queryset = PolicyParameter.objects.select_related("policy", "target_content_type")
    serializer_class = users_serializers.PolicyParameterSerializer
    table_class = users_tables.PolicyParameterTable

    object_detail_content = object_detail.ObjectDetailContent(
        panels=(
            object_detail.ObjectFieldsPanel(
                section=SectionChoices.LEFT_HALF,
                weight=100,
                fields=("policy", "name", "kind", "target_content_type", "multiple"),
            ),
        ),
    )


class PolicyRuleUIViewSet(PolicyChildUIViewSetBase):
    filterset_class = users_filters.PolicyRuleFilterSet
    filterset_form_class = PolicyRuleFilterForm
    form_class = PolicyRuleForm
    queryset = PolicyRule.objects.select_related("policy", "content_type")
    serializer_class = users_serializers.PolicyRuleSerializer
    table_class = users_tables.PolicyRuleTable

    object_detail_content = object_detail.ObjectDetailContent(
        panels=(
            object_detail.ObjectFieldsPanel(
                section=SectionChoices.LEFT_HALF,
                weight=100,
                fields=("policy", "content_type", "actions"),
            ),
            object_detail.ObjectFieldsPanel(
                section=SectionChoices.RIGHT_HALF,
                weight=100,
                label="Constraint",
                fields=("constraint_template", "path_map"),
            ),
        ),
    )

    def get_extra_context(self, request, instance):
        context = super().get_extra_context(request, instance)
        if self.action in ("create", "update"):
            context["rule_paths_url"] = reverse("users:permissionpolicy_rule_paths")
        return context
