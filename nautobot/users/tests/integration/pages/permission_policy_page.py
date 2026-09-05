"""Page object for the permission policy create/edit form (/users/permission-policies/add/)."""

import re

from playwright.sync_api import expect

from nautobot.playwright.base_page import BasePage, select2_filter_pick


class PermissionPolicyFormPage(BasePage):
    """The policy authoring form: name, a parameters formset, and a rules formset with the constraint editor."""

    ADD_PATH = "/users/permission-policies/add/"
    PARAMETER_ROWS = "tr.formset_row-parameters:not(.nb-formset-anchor):visible"
    RULE_ROWS = ".rule-card:not(.nb-formset-anchor):visible"

    def navigate_add(self):
        self._goto(self.ADD_PATH)

    def navigate_edit(self, pk):
        self._goto(f"/users/permission-policies/{pk}/edit/")

    def fill_name(self, name):
        self.page.fill("input[name='name']", name)

    # ----- parameters -------------------------------------------------------------------------------------

    def visible_parameter_rows(self):
        return self.page.locator(self.PARAMETER_ROWS).count()

    def add_parameter(self, name, kind, target_text=None, multiple=False):
        """Click "Add parameter" and fill the new row. Returns the row's formset index."""
        index = self.visible_parameter_rows()
        self.page.get_by_text("Add parameter").click()
        self.page.wait_for_selector(f"input[name='parameters-{index}-name']")
        self.page.fill(f"input[name='parameters-{index}-name']", name)
        select2_filter_pick(self.page, f"parameters-{index}-kind", kind, kind, exact=False)
        if target_text is not None:
            select2_filter_pick(
                self.page,
                f"parameters-{index}-target_content_type",
                target_text.split("|")[-1].strip(),
                target_text,
                exact=False,
            )
        if multiple:
            self.page.check(f"input[name='parameters-{index}-multiple']")
        return index

    def set_parameter_kind(self, index, kind):
        select2_filter_pick(self.page, f"parameters-{index}-kind", kind, kind, exact=False)

    def target_object_type_cell_hidden(self, index):
        cell = self.page.locator(f"select[name='parameters-{index}-target_content_type']").locator("xpath=ancestor::td")
        return "invisible" in (cell.get_attribute("class") or "")

    # ----- rules ------------------------------------------------------------------------------------------

    def visible_rule_rows(self):
        return self.page.locator(self.RULE_ROWS).count()

    def add_rule(self, object_type, actions=("View",)):
        """Click "Add rule", select the object type (by its "App | model" text) and actions. Returns the row index."""
        index = self.visible_rule_rows()
        self.page.get_by_text("Add rule").click()
        self.page.wait_for_selector(f"select[name='rules-{index}-content_type']")
        select2_filter_pick(self.page, f"rules-{index}-content_type", object_type.split("|")[-1].strip(), object_type)
        for action in actions:
            select2_filter_pick(self.page, f"rules-{index}-actions", action, action, exact=False)
        return index

    def rule_card(self, index):
        return self.page.locator(f".rule-card:has(select[name='rules-{index}-content_type'])")

    def suggested_paths(self, index):
        """The `path` values of the suggested-parameter-path buttons currently shown in the rule row."""
        card = self.rule_card(index)
        card.locator(".nb-use-path").first.wait_for(state="attached", timeout=10_000)
        return card.locator(".nb-use-path").evaluate_all("nodes => nodes.map(n => n.dataset.path)")

    def use_suggested_path(self, index, path):
        self.rule_card(index).locator(f".nb-use-path[data-path='{path}']").first.click()

    def constraint_json(self, index):
        return self.page.locator(f"textarea[name='rules-{index}-constraint_template']").input_value()

    # ----- constraint editor ------------------------------------------------------------------------------

    def builder_rows(self, index):
        return self.rule_card(index).locator(".nb-constraint-editor-builder tbody tr")

    def expect_builder_row_parameter(self, index, parameter_name, row=0):
        """Assert (auto-retrying, since the builder renders after resolving the object type) that a builder row
        uses the Parameter source with the given parameter selected."""
        cells = self.builder_rows(index).nth(row).locator("td")
        expect(cells.nth(3).locator("select")).to_have_value("parameter")
        expect(cells.nth(2).locator("select")).to_have_value(parameter_name)

    def add_condition(self, index):
        self.rule_card(index).locator(".nb-constraint-editor-builder").get_by_text("Add condition").click()

    def open_field_picker(self, index, row=-1):
        buttons = self.rule_card(index).locator(".nb-ce-path")
        (buttons.last if row == -1 else buttons.nth(row)).click()
        # Each row owns a (Bootstrap dropdown) picker; the open one carries the `show` class.
        picker = self.page.locator(".nb-ce-picker.show")
        picker.wait_for(state="visible", timeout=10_000)
        self.page.wait_for_selector(".nb-ce-picker.show .nb-ce-node", timeout=10_000)
        return picker

    def expand_picker_node(self, path):
        self.page.locator(f".nb-ce-picker.show .nb-ce-node[data-path='{path}'] button").first.click()

    def choose_picker_node(self, path):
        node = self.page.locator(f".nb-ce-picker.show .nb-ce-node[data-path='{path}']")
        node.wait_for(state="visible", timeout=10_000)
        node.locator("button").last.click()

    # ----- submit -----------------------------------------------------------------------------------------

    def submit(self):
        self._click_and_wait_for_navigation("button[name='_create'], button[name='_update']")

    def form_errors(self):
        return [text.strip() for text in self.page.locator(".alert-danger").all_inner_texts() if text.strip()]

    def expect_on_detail_page(self):
        expect(self.page).to_have_url(re.compile(r"/users/permission-policies/[0-9a-f-]{36}/$"))


class PolicyRuleFormPage(BasePage):
    """The rule's own create form (/users/policy-rules/add/), with the same editor as a policy form row."""

    ADD_PATH = "/users/policy-rules/add/"

    def navigate_add(self, policy_pk=None):
        self._goto(f"{self.ADD_PATH}?policy={policy_pk}" if policy_pk else self.ADD_PATH)

    def select_object_type(self, object_type):
        select2_filter_pick(self.page, "content_type", object_type.split("|")[-1].strip(), object_type)

    def select_action(self, action):
        select2_filter_pick(self.page, "actions", action, action, exact=False)

    def suggested_paths(self):
        self.page.locator(".nb-use-path").first.wait_for(state="attached", timeout=10_000)
        return self.page.locator(".nb-use-path").evaluate_all("nodes => nodes.map(n => n.dataset.path)")

    def use_suggested_path(self, path):
        self.page.locator(f".nb-use-path[data-path='{path}']").first.click()

    def constraint_json(self):
        return self.page.locator("textarea[name='constraint_template']").input_value()

    def expect_builder_row_parameter(self, parameter_name, row=0):
        cells = self.page.locator(".nb-constraint-editor-builder tbody tr").nth(row).locator("td")
        expect(cells.nth(3).locator("select")).to_have_value("parameter")
        expect(cells.nth(2).locator("select")).to_have_value(parameter_name)

    def submit(self):
        self._click_and_wait_for_navigation("button[name='_create'], button[name='_update']")

    def expect_on_detail_page(self):
        expect(self.page).to_have_url(re.compile(r"/users/policy-rules/[0-9a-f-]{36}/$"))
