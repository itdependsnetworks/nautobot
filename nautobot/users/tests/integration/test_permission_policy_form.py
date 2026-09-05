"""Permission policy authoring form: parameters, rules, suggested paths, constraint editor.

Browser tests for a new feature, written as Playwright one-offs per the interim guidance in
`docs/development/core/playwright-testing.md`.
"""

import json

import pytest

from nautobot.playwright.helpers import unique_name
from nautobot.users.tests.integration.pages.permission_policy_page import PermissionPolicyFormPage, PolicyRuleFormPage


class PermissionPolicyFormTestCase:
    def test_form_starts_without_blank_rows(self, auth_page, base_url, browser_errors):
        """Neither formset renders an empty row until the user asks for one."""
        form = PermissionPolicyFormPage(auth_page, base_url)
        form.navigate_add()
        assert form.visible_parameter_rows() == 0
        assert form.visible_rule_rows() == 0
        form.add_parameter("tenant", "Object", "Tenancy | tenant")
        form.add_rule("DCIM | device")
        assert form.visible_parameter_rows() == 1
        assert form.visible_rule_rows() == 1
        assert browser_errors == []

    def test_target_object_type_follows_kind(self, auth_page, base_url, browser_errors):
        """Target object type is shown for an object parameter and hidden for a string parameter."""
        form = PermissionPolicyFormPage(auth_page, base_url)
        form.navigate_add()
        index = form.add_parameter("tenant", "Object", "Tenancy | tenant")
        assert not form.target_object_type_cell_hidden(index)
        form.set_parameter_kind(index, "String")
        assert form.target_object_type_cell_hidden(index)
        assert browser_errors == []

    @pytest.mark.behavioral
    def test_builder_reflects_unsaved_parameter_and_picker_is_visible(self, auth_page, base_url, browser_errors):
        """Using a suggested path writes a parameter placeholder the builder recognizes; the field picker opens
        on screen (not clipped by the panels below) and expands relations."""
        form = PermissionPolicyFormPage(auth_page, base_url)
        form.navigate_add()
        form.add_parameter("tenant", "Object", "Tenancy | tenant", multiple=True)
        index = form.add_rule("DCIM | device")

        paths = form.suggested_paths(index)
        assert paths[0] == "tenant", f"Shortest path should be first: {paths}"
        form.use_suggested_path(index, "tenant")
        assert json.loads(form.constraint_json(index)) == {"tenant__in": "{{ tenant }}"}
        form.expect_builder_row_parameter(index, "tenant")

        form.add_condition(index)
        picker = form.open_field_picker(index)
        box = picker.bounding_box()
        viewport = auth_page.viewport_size
        assert box is not None and box["x"] >= 0 and box["y"] >= 0
        assert box["x"] + box["width"] <= viewport["width"] and box["y"] + box["height"] <= viewport["height"]
        form.expand_picker_node("tenant")
        form.choose_picker_node("tenant__name")
        assert "tenant__name" in json.loads(form.constraint_json(index))
        assert browser_errors == []

    @pytest.mark.behavioral
    def test_create_policy_with_two_rules(self, auth_page, base_url, api, policy_cleanup, browser_errors):
        """Two rules, each taking its own suggested path to the shared parameter, are stored with derived path maps."""
        name = unique_name("ZZZ-policy")
        policy_cleanup.append(name)
        form = PermissionPolicyFormPage(auth_page, base_url)
        form.navigate_add()
        form.fill_name(name)
        form.add_parameter("tenant", "Object", "Tenancy | tenant", multiple=True)
        device_row = form.add_rule("DCIM | device")
        form.use_suggested_path(device_row, "tenant")
        interface_row = form.add_rule("DCIM | interface")
        form.use_suggested_path(interface_row, "device__tenant")

        form.submit()
        form.expect_on_detail_page()

        response = api.get("/api/users/permission-policies/", params={"name": name})
        assert response.ok, response.text()
        results = response.json()["results"]
        assert len(results) == 1
        policy = results[0]
        assert [parameter["name"] for parameter in policy["parameters"]] == ["tenant"]
        rules = {rule["content_type"]: rule for rule in policy["rules"]}
        assert set(rules) == {"dcim.device", "dcim.interface"}
        assert rules["dcim.device"]["constraint_template"] == {"tenant__in": "{{ tenant }}"}
        assert rules["dcim.device"]["path_map"] == {"tenant": {"path": "tenant", "lookup": "in"}}
        assert rules["dcim.interface"]["constraint_template"] == {"device__tenant__in": "{{ tenant }}"}
        assert rules["dcim.interface"]["path_map"] == {"tenant": {"path": "device__tenant", "lookup": "in"}}
        assert browser_errors == []


class PolicyRuleFormTestCase:
    @pytest.mark.behavioral
    def test_rule_form_suggests_paths_for_the_selected_policy(
        self, auth_page, base_url, api, policy_cleanup, browser_errors
    ):
        """The rule's own form resolves paths from the policy's saved parameters and stores the derived path map."""
        name = unique_name("ZZZ-policy")
        policy_cleanup.append(name)
        response = api.post(
            "/api/users/permission-policies/",
            data={
                "name": name,
                "parameters": [
                    {"name": "tenant", "kind": "object", "target_content_type": "tenancy.tenant", "multiple": True}
                ],
                "rules": [
                    {
                        "content_type": "dcim.device",
                        "actions": ["view"],
                        "path_map": {"tenant": {"path": "tenant", "lookup": "in"}},
                    }
                ],
            },
        )
        assert response.ok, response.text()
        policy_pk = response.json()["id"]

        form = PolicyRuleFormPage(auth_page, base_url)
        form.navigate_add(policy_pk)
        form.select_object_type("DCIM | interface")
        form.select_action("View")
        assert form.suggested_paths()[0] == "device__tenant"
        form.use_suggested_path("device__tenant")
        assert json.loads(form.constraint_json()) == {"device__tenant__in": "{{ tenant }}"}
        form.expect_builder_row_parameter("tenant")
        form.submit()
        form.expect_on_detail_page()

        response = api.get(f"/api/users/permission-policies/{policy_pk}/")
        assert response.ok, response.text()
        rules = {rule["content_type"]: rule for rule in response.json()["rules"]}
        assert set(rules) == {"dcim.device", "dcim.interface"}
        assert rules["dcim.interface"]["path_map"] == {"tenant": {"path": "device__tenant", "lookup": "in"}}
        assert browser_errors == []
