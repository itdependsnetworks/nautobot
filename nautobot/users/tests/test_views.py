import json
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import override_settings, RequestFactory
from django.urls import reverse
from django.utils import timezone
from social_django.utils import load_backend, load_strategy

from nautobot.core.testing import TestCase, utils, ViewTestCases
from nautobot.core.testing.context import load_event_broker_override_settings
from nautobot.core.testing.utils import post_data
from nautobot.dcim.models import Device, Interface, Location
from nautobot.extras.models import Status
from nautobot.tenancy.models import Tenant
from nautobot.users.models import PermissionPolicy, PolicyParameter, PolicyRule
from nautobot.users.tests.test_policies import create_tenant_policy
from nautobot.users.utils import serialize_user_without_config_and_views

User = get_user_model()

SAMPLE_FAVORITES = [
    {"link": "/dcim/devices/", "name": "Devices", "tab_name": "Devices"},
    {"link": "/dcim/locations/", "name": "Locations", "tab_name": "Organization"},
    {"link": "/ipam/prefixes/", "name": "Prefixes", "tab_name": "IPAM"},
]


class PasswordUITest(TestCase):
    def test_change_password_enabled(self):
        """
        Check that a Django-authentication-based user is allowed to change their password
        """
        profile_response = self.client.get(reverse("user:profile"))
        preferences_response = self.client.get(reverse("user:preferences"))
        api_tokens_response = self.client.get(reverse("user:token_list"))
        for response in [profile_response, preferences_response, api_tokens_response]:
            self.assertBodyContains(response, "Change Password")

        # Check GET change_password functionality
        get_response = self.client.get(reverse("user:change_password"))
        self.assertBodyContains(get_response, "New password confirmation")

        # Check POST change_password functionality
        post_response = self.client.post(
            reverse("user:change_password"),
            data={
                "old_password": "foo",
                "new_password1": "bar",
                "new_password2": "baz",
            },
        )
        self.assertBodyContains(post_response, "The two password fields")

    @load_event_broker_override_settings(
        EVENT_BROKERS={
            "SyslogEventBroker": {
                "CLASS": "nautobot.core.events.SyslogEventBroker",
                "TOPICS": {
                    "INCLUDE": ["*"],
                },
            }
        }
    )
    def test_change_password(self):
        self.user.set_password("foo")
        self.user.save()
        self.client.force_login(self.user)
        with self.assertLogs("nautobot.events") as cm:
            self.client.post(
                reverse("user:change_password"),
                data={
                    "old_password": "foo",
                    "new_password1": "bar",
                    "new_password2": "bar",
                },
            )
        payload = serialize_user_without_config_and_views(self.user)
        self.assertEqual(
            cm.output,
            [f"INFO:nautobot.events.nautobot.users.user.change_password:{json.dumps(payload, indent=4)}"],
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("bar"))

    @override_settings(
        AUTHENTICATION_BACKENDS=[
            "social_core.backends.google.GoogleOAuth2",
            "nautobot.core.authentication.ObjectPermissionBackend",
        ]
    )
    def test_change_password_disabled(self):
        """
        Mock an SSO-authenticated user, log them in by force and check that the change
        password functionality isn't visible in the UI or available server-side
        """
        # Logout the non-SSO user
        self.client.logout()

        sso_user = User.objects.create_user(username="sso_user", is_superuser=True)

        self.request_factory = RequestFactory(SERVER_NAME="nautobot.example.com")
        self.request = self.request_factory.get("/")
        SessionMiddleware(lambda: None).process_request(self.request)

        # load 'social_django.strategy.DjangoStrategy' from social_core into the fake request
        django_strategy = load_strategy(request=self.request)

        # Load GoogleOAuth2 authentication backend to test against in the mock
        google_auth_backend = load_backend(strategy=django_strategy, name="google-oauth2", redirect_uri="/")

        # Mock an authenticated SSO pipeline
        with mock.patch("social_core.backends.base.BaseAuth.pipeline", return_value=sso_user):
            result = django_strategy.authenticate(backend=google_auth_backend, response=mock.Mock())
            self.assertEqual(result, sso_user)
            self.assertEqual(result.backend, "social_core.backends.google.GoogleOAuth2")
            self.assertTrue(sso_user.is_authenticated)
            self.client.force_login(sso_user, backend=settings.AUTHENTICATION_BACKENDS[0])

            # Check UI
            profile_response = self.client.get(reverse("user:profile"))
            preferences_response = self.client.get(reverse("user:preferences"))
            api_tokens_response = self.client.get(reverse("user:token_list"))
            for response in [profile_response, preferences_response, api_tokens_response]:
                self.assertNotIn("Change Password", utils.extract_page_body(response.content.decode(response.charset)))

            # Check GET and POST change_password functionality
            get_response = self.client.get(reverse("user:change_password"), follow=True)
            post_response = self.client.post(reverse("user:change_password"), follow=True)
            for response in [get_response, post_response]:
                content = utils.extract_page_body(response.content.decode(response.charset))
                self.assertNotIn("New password confirmation", content)
                # Check redirect
                self.assertIn("User Profile", content)
                # Check warning message
                self.assertIn("Remotely authenticated user credentials cannot be changed within Nautobot.", content)


class AdvancedProfileSettingsViewTest(TestCase):
    """
    Tests for the user's advanced settings profile edit view
    """

    @override_settings(ALLOW_REQUEST_PROFILING=True)
    def test_enable_request_profiling(self):
        """
        Check that a user can enable request profling on their session
        """
        # Simulate form submission with checkbox checked
        response = self.client.post(reverse("user:advanced_settings_edit"), {"request_profiling": True})
        self.assertEqual(response.status_code, 200)
        # Check if the session has the correct value
        self.assertTrue(self.client.session["silk_record_requests"])

    @override_settings(ALLOW_REQUEST_PROFILING=True)
    def test_disable_request_profiling(self):
        """
        Check that a user can disable request profling on their session
        """
        # Simulate form submission with checkbox unchecked
        response = self.client.post(reverse("user:advanced_settings_edit"), {"request_profiling": False})
        self.assertEqual(response.status_code, 200)
        # Check if the session has the correct value
        self.assertFalse(self.client.session["silk_record_requests"])

    @override_settings(ALLOW_REQUEST_PROFILING=False)
    def test_disable_allow_request_profiling_rejects_user_enable(self):
        """
        Check that a user cannot enable request profiling if ALLOW_REQUEST_PROFILING=False
        """
        # Simulate form submission with checkbox unchecked
        response = self.client.post(reverse("user:advanced_settings_edit"), {"request_profiling": True})

        # Check if the form is in the response context and has errors
        self.assertTrue("form" in response.context)
        form = response.context["form"]
        self.assertFalse(form.cleaned_data["request_profiling"])

        # Check if the session has the correct value
        self.assertFalse(self.client.session.get("silk_record_requests"))


class PreferenceTestCase(TestCase):
    def test_timezone_change(self):
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)

        timezone_name = timezone.get_current_timezone_name()
        new_timezone_name = "US/Eastern"
        form_data = {"timezone": new_timezone_name, "_update_preference_form": [""]}
        url = reverse("user:preferences")
        request = {
            "path": url,
            "data": post_data(form_data),
        }
        response = self.client.post(**request, follow=True)
        self.assertHttpStatus(response, 200)
        response = self.client.get(url)
        self.assertEqual(timezone.get_current_timezone_name(), new_timezone_name)
        self.assertNotEqual(timezone_name, new_timezone_name)
        self.assertHttpStatus(response, 200)


class NavbarFavoritesReorderViewTest(TestCase):
    """Tests for the UserNavbarFavoritesReorderView."""

    def setUp(self):
        super().setUp()
        self.url = reverse("user:navbar_favorites_reorder")
        self.user.set_config("navbar_favorites", list(SAMPLE_FAVORITES), commit=True)

    def _post_reorder(self, ordered_links):
        return self.client.post(self.url, data={"ordered_links": ordered_links}, headers={"HX-Request": "true"})

    def test_reorder_favorites(self):
        """Reordering should persist the new order and preserve each favorite's full metadata."""
        reversed_links = [favorite["link"] for favorite in reversed(SAMPLE_FAVORITES)]
        response = self._post_reorder(reversed_links)
        self.assertHttpStatus(response, 204)

        self.user.refresh_from_db()
        result = self.user.get_config("navbar_favorites", [])
        self.assertEqual(result, list(reversed(SAMPLE_FAVORITES)))

    def test_partial_list_appends_missing(self):
        """Favorites not included in ordered_links should be appended at the end, in their existing order."""
        response = self._post_reorder(["/ipam/prefixes/"])
        self.assertHttpStatus(response, 204)

        self.user.refresh_from_db()
        links = [favorite["link"] for favorite in self.user.get_config("navbar_favorites", [])]
        self.assertEqual(links, ["/ipam/prefixes/", "/dcim/devices/", "/dcim/locations/"])

    def test_duplicate_and_unknown_links(self):
        """Duplicate links should appear once; unknown links should be ignored."""
        response = self._post_reorder(["/nonexistent/", "/dcim/devices/", "/dcim/devices/", "/ipam/prefixes/"])
        self.assertHttpStatus(response, 204)

        self.user.refresh_from_db()
        links = [favorite["link"] for favorite in self.user.get_config("navbar_favorites", [])]
        self.assertEqual(links, ["/dcim/devices/", "/ipam/prefixes/", "/dcim/locations/"])

    def test_non_htmx_request_redirects(self):
        """Requests that do not come from htmx should be redirected without touching the saved order."""
        response = self.client.post(self.url, data={"ordered_links": ["/ipam/prefixes/"]})
        self.assertHttpStatus(response, 302)

        self.user.refresh_from_db()
        self.assertEqual(self.user.get_config("navbar_favorites", []), list(SAMPLE_FAVORITES))

    def test_unauthenticated_returns_redirect(self):
        """Unauthenticated requests should be redirected to the login page."""
        self.client.logout()
        response = self._post_reorder(["/dcim/devices/"])
        self.assertHttpStatus(response, 302)
        self.assertIn("login", response.url)


#
# Permission policies
#


def _formset_management(prefix, total, initial=0):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }


# The generic view tests assume the model honors `EXEMPT_VIEW_PERMISSIONS = ["*"]`. These models are deliberately
# listed in EXEMPT_EXCLUDE_MODELS (like ObjectPermission), so the exclusion is narrowed for the generic tests only.
POLICY_TEST_EXEMPT_EXCLUDE_MODELS = (("auth", "group"), ("users", "user"), ("users", "objectpermission"))


@override_settings(EXEMPT_EXCLUDE_MODELS=POLICY_TEST_EXEMPT_EXCLUDE_MODELS)
class PermissionPolicyTestCase(ViewTestCases.PrimaryObjectViewTestCase):
    model = PermissionPolicy

    @classmethod
    def setUpTestData(cls):
        for i in range(3):
            create_tenant_policy(name=f"Policy {i + 1}")
        tenant_ct = ContentType.objects.get_for_model(Tenant)
        device_ct = ContentType.objects.get_for_model(Device)
        interface_ct = ContentType.objects.get_for_model(Interface)

        cls.form_data = {
            "name": "Policy X",
            "description": "Created through the UI",
            **_formset_management("parameters", 1),
            "parameters-0-name": "tenant",
            "parameters-0-kind": "object",
            "parameters-0-target_content_type": tenant_ct.pk,
            "parameters-0-multiple": True,
            **_formset_management("rules", 2),
            "rules-0-content_type": device_ct.pk,
            "rules-0-actions": ["view"],
            "rules-0-constraint_template": '{"tenant__in": "{{ tenant }}"}',
            "rules-1-content_type": interface_ct.pk,
            "rules-1-actions": ["view", "change"],
            "rules-1-constraint_template": '{"device__tenant__in": "{{ tenant }}"}',
        }
        # Editing posts no parameter rows (leaving them untouched) and adds one rule; existing rules, when re-posted
        # by the browser, carry their ids.
        cls.update_data = {
            "name": "Policy Y",
            "description": "Edited through the UI",
            **_formset_management("parameters", 0),
            **_formset_management("rules", 1),
            "rules-0-content_type": ContentType.objects.get_for_model(Location).pk,
            "rules-0-actions": ["view"],
            "rules-0-constraint_template": '{"tenant__in": "{{ tenant }}"}',
        }
        cls.bulk_edit_data = {"description": "Bulk edited"}

    def test_create_object_with_constrained_permission(self):
        super().test_create_object_with_constrained_permission()
        policy = PermissionPolicy.objects.get(name="Policy X")
        self.assertEqual(policy.parameters.count(), 1)
        rules = {rule.content_type.model: rule for rule in policy.rules.all()}
        self.assertEqual(rules["interface"].path_map, {"tenant": {"path": "device__tenant", "lookup": "in"}})
        self.assertEqual(rules["interface"].actions, ["view", "change"])

    def test_duplicate_object_type_across_rows_is_rejected(self):
        self.add_permissions("users.add_permissionpolicy")
        device_ct = ContentType.objects.get_for_model(Device)
        data = {**self.form_data, "rules-1-content_type": device_ct.pk}
        response = self.client.post(self._get_url("add"), data=post_data(data))
        self.assertHttpStatus(response, 200)
        self.assertIn("more than one rule", response.content.decode(response.charset))
        self.assertFalse(PermissionPolicy.objects.filter(name="Policy X").exists())

    def test_create_with_rule_not_using_parameter_succeeds(self):
        """A rule need not use every parameter; the interface rule here is not scoped by tenant."""
        self.add_permissions("users.add_permissionpolicy", "users.view_policyrule")
        data = {**self.form_data, "rules-1-constraint_template": "{}"}
        response = self.client.post(self._get_url("add"), data=post_data(data))
        self.assertHttpStatus(response, 302)
        policy = PermissionPolicy.objects.get(name="Policy X")
        interface_rule = policy.rules.get(content_type=ContentType.objects.get_for_model(Interface))
        self.assertEqual(interface_rule.path_map, {})
        self.add_permissions("users.view_permissionpolicy")
        self.assertIn("not scoped by this parameter", self.client.get(policy.get_absolute_url()).content.decode())

    def test_clone_prefills_parameters_and_rules(self):
        self.add_permissions("users.add_permissionpolicy", "users.view_permissionpolicy")
        policy = PermissionPolicy.objects.get(name="Policy 1")
        response = self.client.get(policy.get_absolute_url())
        body = response.content.decode(response.charset)
        self.assertIn(f"clone_from={policy.pk}", body)

        response = self.client.get(f"{self._get_url('add')}?description=Copy&clone_from={policy.pk}")
        self.assertHttpStatus(response, 200)
        body = response.content.decode(response.charset)
        self.assertIn('name="parameters-0-name" value="tenant"', body)
        self.assertIn('name="rules-TOTAL_FORMS" value="2"', body)
        self.assertIn("device__tenant__in", body)
        # Nothing is created until the form is submitted.
        self.assertEqual(PermissionPolicy.objects.filter(description="Copy").count(), 0)

    def test_rule_paths_fragment(self):
        self.add_permissions("users.view_permissionpolicy")
        tenant_ct = ContentType.objects.get_for_model(Tenant)
        interface_ct = ContentType.objects.get_for_model(Interface)
        status_ct = ContentType.objects.get_for_model(Status)
        params = {
            "content_type": interface_ct.pk,
            "prefix": "rules-0",
            **_formset_management("parameters", 1),
            "parameters-0-name": "tenant",
            "parameters-0-kind": "object",
            "parameters-0-target_content_type": tenant_ct.pk,
            "parameters-0-multiple": "on",
        }
        response = self.client.get(reverse("users:permissionpolicy_rule_paths"), data=params)
        self.assertHttpStatus(response, 200)
        body = response.content.decode(response.charset)
        self.assertIn('data-path="device__tenant"', body)
        self.assertIn('data-lookup="in"', body)
        # Shortest candidate comes first.
        self.assertLess(body.index('data-path="device__tenant"'), body.index('data-path="device__location__tenant"'))

        params["content_type"] = status_ct.pk
        response = self.client.get(reverse("users:permissionpolicy_rule_paths"), data=params)
        self.assertIn("No path from", response.content.decode(response.charset))

        # The rule's own form names a saved policy instead of posting parameter rows.
        policy = PermissionPolicy.objects.get(name="Policy 1")
        response = self.client.get(
            reverse("users:permissionpolicy_rule_paths"),
            data={"content_type": interface_ct.pk, "policy": policy.pk, "prefix": ""},
        )
        self.assertHttpStatus(response, 200)
        body = response.content.decode(response.charset)
        self.assertIn('data-path="device__tenant"', body)
        # The editor learns the policy's parameter names from hidden inputs in the fragment.
        self.assertIn('class="nb-rule-parameter-name" value="tenant"', body)

    def test_detail_view_lists_rules_and_parameters(self):
        # The parameter and rule panels are permission-restricted tables of their own models.
        self.add_permissions("users.view_permissionpolicy", "users.view_policyparameter", "users.view_policyrule")
        policy = PermissionPolicy.objects.get(name="Policy 1")
        response = self.client.get(policy.get_absolute_url())
        self.assertHttpStatus(response, 200)
        body = response.content.decode(response.charset)
        self.assertIn("device__tenant", body)
        self.assertIn("parameters", body.lower())
        # The assignments panel excludes the redundant "policy" column, so the table configuration must not offer it.
        self.assertNotIn('value="policy"', body)


class PolicyChildViewTestCases:
    """Namespace, so the shared base is not collected as a test case of its own."""

    class ViewTestCase(
        ViewTestCases.GetObjectViewTestCase,
        ViewTestCases.GetObjectChangelogViewTestCase,
        ViewTestCases.GetObjectOverviewViewTestCase,
        ViewTestCases.CreateObjectViewTestCase,
        ViewTestCases.EditObjectViewTestCase,
        ViewTestCases.DeleteObjectViewTestCase,
        ViewTestCases.ListObjectsViewTestCase,
        ViewTestCases.BulkDeleteObjectsViewTestCase,
    ):
        """The views a policy's parameters and rules have: everything but bulk edit and bulk import."""


@override_settings(EXEMPT_EXCLUDE_MODELS=POLICY_TEST_EXEMPT_EXCLUDE_MODELS)
class PolicyParameterTestCase(PolicyChildViewTestCases.ViewTestCase):
    model = PolicyParameter

    @classmethod
    def setUpTestData(cls):
        policies = [create_tenant_policy(name=f"Policy {i + 1}") for i in range(3)]
        cls.form_data = {
            "policy": policies[0].pk,
            "name": "region",
            "kind": "object",
            "target_content_type": ContentType.objects.get_for_model(Location).pk,
            "multiple": True,
        }
        cls.update_data = {
            "policy": policies[0].pk,
            "name": "tenant",
            "kind": "object",
            "target_content_type": ContentType.objects.get_for_model(Tenant).pk,
            "multiple": False,
        }

    def test_create_form_prefills_policy_from_the_detail_page_link(self):
        self.add_permissions("users.add_policyparameter", "users.view_permissionpolicy")
        policy = PermissionPolicy.objects.get(name="Policy 1")
        response = self.client.get(f"{self._get_url('add')}?policy={policy.pk}")
        self.assertHttpStatus(response, 200)
        self.assertIn(f'value="{policy.pk}"', response.content.decode(response.charset))


@override_settings(EXEMPT_EXCLUDE_MODELS=POLICY_TEST_EXEMPT_EXCLUDE_MODELS)
class PolicyRuleTestCase(PolicyChildViewTestCases.ViewTestCase):
    model = PolicyRule

    @classmethod
    def setUpTestData(cls):
        policies = [create_tenant_policy(name=f"Policy {i + 1}") for i in range(3)]
        cls.form_data = {
            "policy": policies[0].pk,
            "content_type": ContentType.objects.get_for_model(Location).pk,
            "actions": ["view"],
            "constraint_template": '{"tenant__in": "{{ tenant }}"}',
        }
        # The edited rule keeps its policy; Location has no rule yet, so the object type can change to it.
        cls.update_data = {
            "policy": policies[0].pk,
            "content_type": ContentType.objects.get_for_model(Location).pk,
            "actions": ["view", "change"],
            "constraint_template": '{"tenant__in": "{{ tenant }}"}',
        }

    def assertInstanceEqual(self, instance, data, exclude=None, api=False):
        # `model_to_dict` renders the JSON array of actions as comma-separated text.
        data = {**data}
        if isinstance(data.get("actions"), list):
            data["actions"] = ",".join(data["actions"])
        super().assertInstanceEqual(instance, data, exclude=exclude, api=api)

    def test_create_derives_path_map_and_merges_actions(self):
        self.add_permissions("users.add_policyrule", "users.view_permissionpolicy")
        data = {**self.form_data, "additional_actions": ["run"]}
        response = self.client.post(self._get_url("add"), data=post_data(data))
        self.assertHttpStatus(response, 302)
        rule = PolicyRule.objects.get(content_type=ContentType.objects.get_for_model(Location))
        self.assertEqual(rule.actions, ["view", "run"])
        self.assertEqual(rule.path_map, {"tenant": {"path": "tenant", "lookup": "in"}})

    def test_template_that_does_not_fit_the_object_type_is_rejected(self):
        self.add_permissions("users.add_policyrule", "users.view_permissionpolicy")
        data = {**self.form_data, "constraint_template": '{"device__tenant__in": "{{ tenant }}"}'}
        response = self.client.post(self._get_url("add"), data=post_data(data))
        self.assertHttpStatus(response, 200)
        self.assertIn("dcim.location", response.content.decode(response.charset))
        self.assertFalse(PolicyRule.objects.filter(content_type=ContentType.objects.get_for_model(Location)).exists())

    def test_detail_view_shows_the_template_and_path_map(self):
        self.add_permissions("users.view_policyrule")
        rule = PolicyRule.objects.filter(content_type=ContentType.objects.get_for_model(Interface)).first()
        response = self.client.get(rule.get_absolute_url())
        self.assertHttpStatus(response, 200)
        body = response.content.decode(response.charset)
        self.assertIn("device__tenant", body)
        self.assertIn(str(rule.policy), body)
