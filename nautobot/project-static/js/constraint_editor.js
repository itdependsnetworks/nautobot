/**
 * Visual constraint editor for permission constraints (ObjectPermission constraints, PolicyRule templates).
 *
 * Progressive enhancement over a JSON textarea rendered by `ConstraintEditorWidget`. The textarea remains the
 * real form value; this script keeps it in sync with a row-based builder:
 *
 *   - "Any of" groups (a list of constraint objects) containing "All of" rows (the keys of one object).
 *   - Each row is: ORM lookup path (picked from a lazily loaded field tree), lookup, value and value source
 *     (literal, policy parameter placeholder, or the current user token).
 *   - Anything the builder cannot represent (an unknown path, a nested value) locks the builder and leaves
 *     the JSON untouched, so the editor never damages a hand-written constraint.
 *
 * Endpoints (from the widget's data attributes):
 *   field tree:      GET <field-tree-url>?content_type=app.model&prefix=device
 *   lookup choices:  GET <lookup-choices-url>?content_type=app.model&path=device__tenant
 *   value widget:    GET <value-widget-url>?content_type=app.model&path=...&lookup=...&name=...
 */
(function () {
    "use strict";

    const USER_TOKEN = "$user";
    const PLACEHOLDER_RE = /^\{\{\s*([a-z][a-z0-9_]*)\s*\}\}$/;
    const LOOKUP_LABELS = {
        exact: "is",
        iexact: "is (case-insensitive)",
        in: "is one of",
        icontains: "contains",
        istartswith: "starts with",
        iendswith: "ends with",
        regex: "matches regex",
        iregex: "matches regex (case-insensitive)",
        lt: "less than",
        lte: "less than or equal to",
        gt: "greater than",
        gte: "greater than or equal to",
        isnull: "is null",
        in_tree: "is or is within",
        contains: "contains",
        has_key: "has key",
    };

    function el(tag, attrs, children) {
        const node = document.createElement(tag);
        Object.entries(attrs || {}).forEach(([key, value]) => {
            if (key === "class") node.className = value;
            else if (key === "text") node.textContent = value;
            else if (key === "html") node.innerHTML = value;
            else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
            else node.setAttribute(key, value);
        });
        (children || []).forEach((child) => child && node.appendChild(child));
        return node;
    }

    async function fetchJSON(url, params) {
        const response = await fetch(`${url}?${new URLSearchParams(params)}`, { headers: { Accept: "application/json" } });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
        return data;
    }

    class ConstraintEditor {
        constructor(root) {
            this.root = root;
            this.textarea = root.querySelector("textarea");
            this.tabs = root.querySelector(".nb-constraint-editor-tabs");
            this.builder = root.querySelector(".nb-constraint-editor-builder");
            this.jsonPane = root.querySelector(".nb-constraint-editor-json-pane");
            this.urls = {
                tree: root.dataset.fieldTreeUrl,
                lookups: root.dataset.lookupChoicesUrl,
                validate: root.dataset.validatePathUrl,
                widget: root.dataset.valueWidgetUrl,
            };
            this.allowUserToken = root.dataset.allowUserToken !== "false";
            this.treeCache = new Map();
            this.groups = [];
            this.locked = false;
            this.uid = `nbce-${Math.random().toString(36).slice(2, 8)}`;

            this.tabs.hidden = false;
            // Point each tab at its pane by the textarea's (unique) id. Formset rows are cloned from a template whose
            // ids are rewritten on insertion, but `data-bs-target` and `aria-controls` are not, so set them here.
            const base = this.textarea.id || this.uid;
            this.builder.id = `${base}-builder`;
            this.jsonPane.id = `${base}-json`;
            // Bootstrap owns the tab switching (and its ARIA state); re-render the builder whenever it is shown.
            this.tabs.querySelectorAll("[data-nb-editor-tab]").forEach((button) => {
                const pane = button.dataset.nbEditorTab === "builder" ? this.builder : this.jsonPane;
                button.setAttribute("data-bs-target", `#${pane.id}`);
                button.setAttribute("aria-controls", pane.id);
                button.addEventListener("shown.bs.tab", () => {
                    if (button.dataset.nbEditorTab === "builder" && !this.locked) this.render();
                });
            });
            this.textarea.addEventListener("change", () => this.loadFromJSON());
            this.textarea.addEventListener("input", () => this.loadFromJSON());

            this.contentTypeField = this.resolveContentTypeField();
            if (this.contentTypeField) {
                this.contentTypeField.addEventListener("change", () => {
                    this.treeCache.clear();
                    this.loadFromJSON();
                });
                if (window.jQuery) {
                    window.jQuery(this.contentTypeField).on("select2:select select2:clear", () => {
                        this.treeCache.clear();
                        this.loadFromJSON();
                    });
                }
            }
            if (this.root.dataset.parameterInputs) {
                const form = this.root.closest("form") || document;
                const onParameterChange = (event) => {
                    if (event.target.matches && event.target.matches(this.root.dataset.parameterInputs)) this.render();
                    if (event.target.name && event.target.name.endsWith("-DELETE")) this.render();
                };
                form.addEventListener("input", onParameterChange);
                form.addEventListener("change", onParameterChange);
            }
            this.loadFromJSON();
            this.showTab(this.locked ? "json" : "builder");
        }

        // ----- configuration -------------------------------------------------------------------------------

        get parameterNames() {
            const names = (this.root.dataset.parameters || "").split(",").map((name) => name.trim()).filter(Boolean);
            // Parameters declared on the same form (not yet saved): read their name inputs, skipping deleted rows
            // and hidden formset templates.
            const selector = this.root.dataset.parameterInputs;
            if (selector) {
                const form = this.root.closest("form") || document;
                form.querySelectorAll(selector).forEach((input) => {
                    if (input.name.includes("__prefix__") || !input.value.trim()) return;
                    const row = input.closest("tr, .formset-row, .card");
                    const deleted = row && row.querySelector('input[type="checkbox"][name$="-DELETE"]');
                    if (deleted && deleted.checked) return;
                    if (!names.includes(input.value.trim())) names.push(input.value.trim());
                });
            }
            return names;
        }

        resolveContentTypeField() {
            const source = this.root.dataset.contentType || "";
            if (!source.startsWith("$")) return null;
            // "$content_types" refers to a sibling form field; formset rows carry a prefix (rules-0-content_types).
            const fieldName = source.slice(1);
            const prefix = this.textarea.name.replace(/[^-]*$/, "");
            return document.getElementById(`id_${prefix}${fieldName}`) || document.getElementById(`id_${fieldName}`);
        }

        /**
         * The "app_label.model" label of the model the constraint applies to, or "" when unknown.
         *
         * A fixed source is used as-is. A `$field` source is a ContentType select (possibly multiple) whose options
         * carry the label as `data-content-type` (or use it as their value); the first selected one is used, because
         * every selected object type shares the template.
         */
        resolveContentType() {
            const source = this.root.dataset.contentType || "";
            if (!source.startsWith("$")) return source;
            if (!this.contentTypeField) return "";
            const selected = this.contentTypeField.selectedOptions ? [...this.contentTypeField.selectedOptions] : [];
            const option = selected.find((item) => item.value !== "");
            if (!option) return "";
            if (option.dataset.contentType) return option.dataset.contentType;
            return /^[a-z_]+\.[a-z_]+$/.test(option.value) ? option.value : "";
        }

        // ----- JSON <-> rows -------------------------------------------------------------------------------

        loadFromJSON() {
            let parsed = {};
            const text = this.textarea.value.trim();
            if (text) {
                try {
                    parsed = JSON.parse(text);
                } catch (error) {
                    return this.lock("The JSON is not valid; fix it in the JSON tab.");
                }
            }
            const groups = Array.isArray(parsed) ? parsed : [parsed];
            const rows = [];
            for (const group of groups) {
                if (group === null || typeof group !== "object" || Array.isArray(group)) {
                    return this.lock("This constraint is not a JSON object or a list of objects.");
                }
                const groupRows = [];
                for (const [key, value] of Object.entries(group)) {
                    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
                        return this.lock("This constraint contains a nested object the builder cannot show.");
                    }
                    groupRows.push(this.rowFromEntry(key, value));
                }
                rows.push(groupRows);
            }
            this.locked = false;
            this.groups = rows.length ? rows : [[]];
            this.render();
        }

        rowFromEntry(key, value) {
            const parts = key.split("__");
            let path = key;
            let lookup = "exact";
            if (parts.length > 1 && Object.prototype.hasOwnProperty.call(LOOKUP_LABELS, parts[parts.length - 1])) {
                lookup = parts.pop();
                path = parts.join("__");
            }
            let source = "literal";
            if (value === USER_TOKEN) source = "user";
            else if (typeof value === "string" && PLACEHOLDER_RE.test(value)) source = "parameter";
            return { path, lookup, value, source };
        }

        syncToJSON() {
            const constraints = this.groups.map((rows) => {
                const constraint = {};
                rows.forEach((row) => {
                    if (!row.path) return;
                    const key = row.lookup === "exact" ? row.path : `${row.path}__${row.lookup}`;
                    constraint[key] = row.value;
                });
                return constraint;
            });
            const value = constraints.length === 1 ? constraints[0] : constraints;
            const text = Object.keys(value).length || Array.isArray(value) ? JSON.stringify(value, null, 4) : "";
            if (this.textarea.value !== text) {
                this.textarea.value = text;
                // Do not re-parse our own write; notify other listeners only.
                this.textarea.dispatchEvent(new CustomEvent("nb-constraint-editor:sync", { bubbles: true }));
            }
        }

        /**
         * Add the condition `<path>__<lookup>: {{ name }}` to the first group, replacing any condition that already
         * uses that parameter. Used by the suggested-path buttons of the policy form.
         */
        setParameterCondition(path, lookup, name) {
            if (this.locked || this.groups.length !== 1) {
                return false; // several "any of" groups: the author must choose where the condition belongs
            }
            const placeholder = `{{ ${name} }}`;
            this.groups[0] = this.groups[0].filter((row) => row.value !== placeholder);
            this.groups[0].push({ path, lookup, value: placeholder, source: "parameter" });
            this.syncToJSON();
            this.render();
            return true;
        }

        lock(message) {
            this.locked = true;
            this.builder.innerHTML = "";
            this.builder.appendChild(
                el("div", { class: "alert alert-warning mb-8" }, [
                    el("span", { text: `${message} ` }),
                    el("span", { class: "text-secondary", text: "The builder is disabled and the JSON is left unchanged." }),
                ])
            );
            this.showTab("json");
        }

        // ----- rendering -----------------------------------------------------------------------------------

        showTab(name) {
            const button = this.tabs.querySelector(`[data-nb-editor-tab="${name}"]`);
            if (button && window.bootstrap) window.bootstrap.Tab.getOrCreateInstance(button).show();
        }

        render() {
            if (this.locked) return;
            const contentType = this.resolveContentType();
            this.builder.innerHTML = "";
            if (!contentType) {
                this.builder.appendChild(
                    el("div", { class: "text-secondary small mb-8", text: "Select an object type to build a constraint." })
                );
                return;
            }
            this.groups.forEach((rows, groupIndex) => {
                if (groupIndex > 0) {
                    this.builder.appendChild(el("div", { class: "text-center text-secondary small my-4", text: "— or —" }));
                }
                this.builder.appendChild(this.renderGroup(rows, groupIndex, contentType));
            });
            const footer = el("div", { class: "d-flex gap-8 mb-8" }, [
                el("button", {
                    type: "button",
                    class: "btn btn-sm btn-outline-secondary",
                    html: '<span class="mdi mdi-plus" aria-hidden="true"></span> Add "any of" group',
                    onclick: () => {
                        this.groups.push([]);
                        this.syncToJSON();
                        this.render();
                    },
                }),
            ]);
            this.builder.appendChild(footer);
            if (this.groups.length === 1 && this.groups[0].length === 0) {
                this.builder.appendChild(
                    el("div", {
                        class: "badge bg-warning text-dark",
                        text: "No constraint: every object of this type matches.",
                    })
                );
            }
        }

        renderGroup(rows, groupIndex, contentType) {
            const card = el("div", { class: "card mb-8" });
            const header = el("div", { class: "card-header d-flex justify-content-between align-items-center py-4" }, [
                el("strong", { class: "small", text: this.groups.length > 1 ? `Group ${groupIndex + 1}: all of` : "All of" }),
                this.groups.length > 1
                    ? el("button", {
                          type: "button",
                          class: "btn btn-sm btn-link text-danger p-0",
                          html: '<span class="mdi mdi-trash-can-outline" aria-hidden="true"></span> Remove group',
                          onclick: () => {
                              this.groups.splice(groupIndex, 1);
                              this.syncToJSON();
                              this.render();
                          },
                      })
                    : null,
            ]);
            const body = el("div", { class: "card-body p-8" });
            const table = el("table", { class: "table table-sm mb-8 align-middle nb-ce-table", style: "table-layout: fixed" }, [
                el("thead", {}, [
                    el("tr", {}, [
                        el("th", { text: "Field path", style: "width: 28%" }),
                        el("th", { text: "Lookup", style: "width: 19%" }),
                        el("th", { text: "Value", style: "width: 30%" }),
                        el("th", { text: "Source", style: "width: 18%" }),
                        el("th", { style: "width: 5%" }),
                    ]),
                ]),
            ]);
            const tbody = el("tbody");
            rows.forEach((row, rowIndex) => tbody.appendChild(this.renderRow(row, groupIndex, rowIndex, contentType)));
            if (!rows.length) {
                tbody.appendChild(
                    el("tr", {}, [el("td", { colspan: "5", class: "text-secondary small", text: "No conditions." })])
                );
            }
            table.appendChild(tbody);
            body.appendChild(table);
            body.appendChild(
                el("button", {
                    type: "button",
                    class: "btn btn-sm btn-primary",
                    html: '<span class="mdi mdi-plus" aria-hidden="true"></span> Add condition',
                    onclick: () => {
                        rows.push({ path: "", lookup: "exact", value: "", source: "literal" });
                        this.render();
                    },
                })
            );
            card.appendChild(header);
            card.appendChild(body);
            return card;
        }

        renderRow(row, groupIndex, rowIndex, contentType) {
            const tr = el("tr");
            const rowId = `${this.uid}-${groupIndex}-${rowIndex}`;

            // Field path picker: a Bootstrap dropdown whose menu holds the lazily loaded field tree.
            const pathCell = el("td", { class: "dropdown" });
            const pathButton = el(
                "button",
                {
                    type: "button",
                    class: "btn btn-sm btn-outline-secondary w-100 text-start nb-ce-path",
                    "data-bs-toggle": "dropdown",
                    "data-bs-auto-close": "outside",
                    "aria-expanded": "false",
                },
                [row.path ? el("code", { text: row.path }) : el("span", { class: "text-secondary", text: "Choose a field…" })]
            );
            pathCell.appendChild(pathButton);
            this.attachPicker(pathCell, pathButton, contentType, (path, node) => {
                row.path = path;
                row.lookup = node && node.lookups && node.lookups.length ? node.lookups[0] : "exact";
                row.value = "";
                row.source = "literal";
                this.syncToJSON();
                this.render();
                // The rows were rebuilt; put the focus back on this row's path button.
                const fresh = this.builder.querySelector(`tr[data-row-id="${rowId}"] .nb-ce-path`);
                if (fresh) fresh.focus();
            });
            tr.dataset.rowId = rowId;
            tr.appendChild(pathCell);

            // Lookup select and value cell, populated once the path is validated against the current object type.
            const lookupCell = el("td");
            const lookupSelect = el("select", { class: "form-select form-select-sm w-100", id: `${rowId}-lookup`, "aria-label": "Lookup" });
            lookupSelect.appendChild(el("option", { value: row.lookup, text: labelFor(row.lookup) }));
            lookupSelect.disabled = true;
            lookupSelect.addEventListener("change", () => {
                row.lookup = lookupSelect.value;
                if (row.source === "literal") row.value = row.lookup === "in" ? [] : "";
                this.syncToJSON();
                this.render();
            });
            lookupCell.appendChild(lookupSelect);
            tr.appendChild(lookupCell);

            const valueCell = el("td", { class: "nb-ce-value", style: "min-width: 0" });
            tr.appendChild(valueCell);

            if (!row.path) {
                valueCell.appendChild(el("span", { class: "text-secondary small", text: "Choose a field first." }));
            } else {
                fetchJSON(this.urls.validate, { content_type: contentType, path: row.path })
                    .then((data) => {
                        if (!data.valid) {
                            this.markRowInvalid(tr, pathButton, valueCell, row, data.detail);
                            return;
                        }
                        lookupSelect.disabled = false;
                        lookupSelect.innerHTML = "";
                        data.lookups.forEach((result) => {
                            const option = el("option", { value: result.id, text: result.name });
                            if (result.id === row.lookup) option.selected = true;
                            lookupSelect.appendChild(option);
                        });
                        if (!data.lookups.some((result) => result.id === row.lookup)) {
                            lookupSelect.appendChild(el("option", { value: row.lookup, text: labelFor(row.lookup), selected: "selected" }));
                        }
                        row.targetsUser = Boolean(data.targets_user);
                        if (row.targetsUser && this.allowUserToken && ![...sourceSelect.options].some((o) => o.value === "user")) {
                            sourceSelect.appendChild(el("option", { value: "user", text: "$user" }));
                        }
                        this.renderValueCell(valueCell, row, contentType, rowId);
                    })
                    .catch((error) => this.markRowInvalid(tr, pathButton, valueCell, row, error.message));
            }

            // Source toggle.
            const sourceCell = el("td");
            const sourceSelect = el("select", { class: "form-select form-select-sm w-100", "aria-label": "Value source" });
            const sources = [["literal", "Literal"]];
            if (this.parameterNames.length || row.source === "parameter") sources.push(["parameter", "Param"]);
            if (this.allowUserToken && (row.targetsUser || row.source === "user")) sources.push(["user", "$user"]);
            sources.forEach(([value, text]) => {
                const option = el("option", { value, text });
                if (value === row.source) option.selected = true;
                sourceSelect.appendChild(option);
            });
            sourceSelect.addEventListener("change", () => {
                row.source = sourceSelect.value;
                if (row.source === "user") row.value = USER_TOKEN;
                else if (row.source === "parameter") row.value = this.parameterNames.length ? `{{ ${this.parameterNames[0]} }}` : "";
                else row.value = row.lookup === "in" ? [] : "";
                this.syncToJSON();
                this.render();
            });
            sourceCell.appendChild(sourceSelect);
            tr.appendChild(sourceCell);

            // Remove.
            tr.appendChild(
                el("td", {}, [
                    el("button", {
                        type: "button",
                        class: "btn btn-sm btn-link text-danger p-0",
                        title: "Remove condition",
                        html: '<span class="mdi mdi-trash-can-outline" aria-hidden="true"></span>',
                        onclick: () => {
                            this.groups[groupIndex].splice(rowIndex, 1);
                            this.syncToJSON();
                            this.render();
                        },
                    }),
                ])
            );
            return tr;
        }

        markRowInvalid(tr, pathButton, valueCell, row, detail) {
            tr.classList.add("table-danger");
            pathButton.classList.add("border-danger");
            pathButton.title = detail;
            valueCell.innerHTML = "";
            valueCell.appendChild(
                el("div", { class: "small text-danger" }, [
                    el("span", { class: "mdi mdi-alert-circle-outline", "aria-hidden": "true" }),
                    el("span", { text: ` ${detail} Choose another field or remove this condition.` }),
                ])
            );
            if (row.value !== "" && row.value !== null && row.value !== undefined) {
                valueCell.appendChild(el("code", { class: "small", text: JSON.stringify(row.value) }));
            }
        }

        renderValueCell(cell, row, contentType, rowId) {
            cell.innerHTML = "";
            if (row.source === "user") {
                cell.appendChild(el("code", { text: USER_TOKEN }));
                cell.appendChild(el("span", { class: "text-secondary small ms-6", text: "the requesting user" }));
                return;
            }
            if (row.source === "parameter") {
                const select = el("select", { class: "form-select form-select-sm", "aria-label": "Parameter" });
                const current = typeof row.value === "string" ? (row.value.match(PLACEHOLDER_RE) || [])[1] : null;
                this.parameterNames.forEach((name) => {
                    const option = el("option", { value: name, text: `{{ ${name} }}` });
                    if (name === current) option.selected = true;
                    select.appendChild(option);
                });
                select.addEventListener("change", () => {
                    row.value = `{{ ${select.value} }}`;
                    this.syncToJSON();
                });
                cell.appendChild(select);
                return;
            }
            if (!row.path) {
                cell.appendChild(el("span", { class: "text-secondary small", text: "Choose a field first." }));
                return;
            }
            // Literal: load a type-appropriate widget, fall back to a text input.
            const inputName = `${rowId}-value`;
            const params = new URLSearchParams({ content_type: contentType, path: row.path, lookup: row.lookup, name: inputName });
            (Array.isArray(row.value) ? row.value : [row.value]).forEach((item) => {
                if (item !== "" && item !== null && item !== undefined) params.append("value", String(item));
            });
            const fallback = () => {
                const input = el("input", {
                    type: "text",
                    class: "form-control form-control-sm",
                    value: Array.isArray(row.value) ? row.value.join(",") : row.value ?? "",
                });
                input.addEventListener("input", () => {
                    row.value = row.lookup === "in" ? input.value.split(",").map((part) => part.trim()).filter(Boolean) : input.value;
                    this.syncToJSON();
                });
                cell.appendChild(input);
            };
            fetch(`${this.urls.widget}?${params}`)
                .then((response) => (response.ok ? response.text() : Promise.reject(new Error("widget"))))
                .then((html) => {
                    const wrapper = el("div", { class: "nb-ce-widget w-100", html });
                    cell.appendChild(wrapper);
                    const input = wrapper.querySelector(`[name="${inputName}"]`);
                    if (!input) return fallback();
                    if (window.jsify_form) window.jsify_form(wrapper);
                    const handler = () => {
                        row.value = this.readValueFromInput(input, row.lookup);
                        this.syncToJSON();
                    };
                    input.addEventListener("change", handler);
                    input.addEventListener("input", handler);
                    if (window.jQuery) window.jQuery(input).on("select2:select select2:unselect select2:clear", handler);
                })
                .catch(fallback);
        }

        readValueFromInput(input, lookup) {
            if (input.tagName === "SELECT") {
                const selected = [...input.selectedOptions].map((option) => option.value).filter((v) => v !== "");
                if (input.multiple || lookup === "in") return selected;
                const value = selected[0] ?? "";
                if (value === "True") return true;
                if (value === "False") return false;
                return value;
            }
            if (input.type === "checkbox") return input.checked;
            if (input.type === "number") return input.value === "" ? "" : Number(input.value);
            if (lookup === "in") return input.value.split(",").map((part) => part.trim()).filter(Boolean);
            return input.value;
        }

        // ----- field tree picker ---------------------------------------------------------------------------

        async loadTreeLevel(contentType, prefix) {
            const key = `${contentType}::${prefix}`;
            if (!this.treeCache.has(key)) {
                this.treeCache.set(key, fetchJSON(this.urls.tree, { content_type: contentType, prefix }));
            }
            return this.treeCache.get(key);
        }

        attachPicker(cell, toggle, contentType, onSelect) {
            const picker = el("div", {
                class: "dropdown-menu nb-ce-picker p-8 shadow",
                role: "dialog",
                "aria-label": "Choose a field path",
                style: "min-width: 22rem; max-width: 34rem; max-height: 22rem; overflow: auto;",
            });
            const search = el("input", { type: "search", class: "form-control form-control-sm mb-6", placeholder: "Filter fields…", "aria-label": "Filter fields" });
            const tree = el("ul", { class: "list-unstyled mb-0 small" });
            picker.appendChild(search);
            picker.appendChild(tree);
            cell.appendChild(picker);
            if (!window.bootstrap) return;
            // A fixed strategy keeps the menu out of any scrolling or clipping ancestor (the rule card, a panel).
            const dropdown = new window.bootstrap.Dropdown(toggle, { autoClose: "outside", popperConfig: { strategy: "fixed" } });

            const renderLevel = (container, nodes, depth) => {
                nodes.forEach((node) => {
                    const item = el("li", { class: "nb-ce-node", "data-path": node.path, style: `margin-left: ${depth * 1.25}rem` });
                    const line = el("div", { class: "d-flex align-items-center gap-6 py-2" });
                    if (node.expandable) {
                        const caret = el("button", { type: "button", class: "btn btn-link btn-sm p-0", title: `Expand ${node.related_model}`, "aria-label": `Expand ${node.related_model}`, "aria-expanded": "false" }, [
                            el("span", { class: "mdi mdi-chevron-right", "aria-hidden": "true" }),
                        ]);
                        const children = el("ul", { class: "list-unstyled mb-0", hidden: "hidden" });
                        caret.addEventListener("click", async (event) => {
                            event.stopPropagation();
                            if (!children.dataset.loaded) {
                                caret.replaceChildren(el("span", { class: "mdi mdi-loading mdi-spin", "aria-hidden": "true" }));
                                try {
                                    const data = await this.loadTreeLevel(contentType, node.path);
                                    renderLevel(children, data.fields, depth + 1);
                                    children.dataset.loaded = "true";
                                } catch (error) {
                                    children.appendChild(el("li", { class: "text-danger", text: error.message }));
                                }
                            }
                            children.hidden = !children.hidden;
                            caret.replaceChildren(el("span", { class: children.hidden ? "mdi mdi-chevron-right" : "mdi mdi-chevron-down", "aria-hidden": "true" }));
                            caret.setAttribute("aria-expanded", children.hidden ? "false" : "true");
                            dropdown.update();
                        });
                        line.appendChild(caret);
                        item.appendChild(line);
                        item.appendChild(children);
                    } else {
                        line.appendChild(el("span", { class: "d-inline-block", style: "width: 1.25rem" }));
                        item.appendChild(line);
                    }
                    const choose = el("button", { type: "button", class: "btn btn-link btn-sm p-0 text-start" }, [
                        document.createTextNode(`${node.verbose_name} `),
                        el("code", { class: "text-secondary", text: node.path }),
                        node.is_relation ? el("span", { class: "mdi mdi-key-link text-warning ms-2", title: "relation", "aria-hidden": "true" }) : null,
                    ]);
                    choose.addEventListener("click", () => {
                        dropdown.hide();
                        onSelect(node.path, node);
                    });
                    line.appendChild(choose);
                    container.appendChild(item);
                });
            };

            search.addEventListener("input", () => {
                const query = search.value.trim().toLowerCase();
                tree.querySelectorAll(".nb-ce-node").forEach((node) => {
                    node.hidden = query !== "" && !node.dataset.path.toLowerCase().includes(query) && !node.textContent.toLowerCase().includes(query);
                });
            });

            toggle.addEventListener("show.bs.dropdown", () => {
                if (picker.dataset.loaded) return;
                picker.dataset.loaded = "true";
                tree.appendChild(el("li", { class: "text-secondary" }, [el("span", { class: "mdi mdi-loading mdi-spin", "aria-hidden": "true" }), document.createTextNode(" Loading…")]));
                this.loadTreeLevel(contentType, "")
                    .then((data) => {
                        tree.innerHTML = "";
                        renderLevel(tree, data.fields, 0);
                        dropdown.update();
                    })
                    .catch((error) => {
                        tree.innerHTML = "";
                        tree.appendChild(el("li", { class: "text-danger", text: error.message }));
                    });
            });
            toggle.addEventListener("shown.bs.dropdown", () => search.focus());
        }
    }

    function labelFor(lookup) {
        return `${LOOKUP_LABELS[lookup] || lookup} (${lookup})`;
    }

    function initializeConstraintEditors(context) {
        const root = context && context.jquery ? context[0] : context || document;
        if (!root || !root.querySelectorAll) return;
        root.querySelectorAll(".nb-constraint-editor").forEach((node) => {
            if (node.dataset.nbInitialized) return;
            node.dataset.nbInitialized = "true";
            node.nbConstraintEditor = new ConstraintEditor(node);
        });
    }

    /**
     * Suggested-path buttons (`.nb-use-path` inside a `[data-prefix]` container) add a parameter condition to the
     * constraint editor of their form row. Delegated once, so buttons swapped in by HTMX need no script of their own.
     */
    document.addEventListener("click", (event) => {
        const button = event.target.closest(".nb-use-path");
        if (!button) return;
        const container = button.closest("[data-prefix]");
        // Rows of the policy form carry a formset prefix (rules-0); the rule's own form has none.
        const prefix = container ? container.dataset.prefix : "";
        const textareaId = prefix ? `id_${prefix}-constraint_template` : "id_constraint_template";
        const textarea = container && document.getElementById(textareaId);
        const root = textarea && textarea.closest(".nb-constraint-editor");
        const editor = root && root.nbConstraintEditor;
        if (!editor) return;
        const added = editor.setParameterCondition(button.dataset.path, button.dataset.lookup, button.dataset.param);
        let notice = container.querySelector(".nb-rule-paths-notice");
        if (added) {
            if (notice) notice.remove();
            return;
        }
        if (!notice) {
            notice = el("div", { class: "nb-rule-paths-notice text-danger small mt-4", role: "alert" });
            container.appendChild(notice);
        }
        notice.textContent = "The constraint template is not a single JSON object; add the path in the JSON tab.";
    });

    window.initializeConstraintEditors = initializeConstraintEditors;
    document.addEventListener("DOMContentLoaded", () => initializeConstraintEditors(document));
})();
