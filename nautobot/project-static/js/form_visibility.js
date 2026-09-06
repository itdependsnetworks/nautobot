/**
 * Client-side runtime for the Form Layout Framework (`nautobot.core.ui.object_form`).
 *
 * Components rendered with `visible_if=...` carry a `data-nb-visible-if` attribute holding a JSON condition over the
 * values of other fields in the same form. This module evaluates those conditions in the browser, re-evaluates them
 * whenever a field changes, and applies one standard hide mechanic:
 *
 *   - the wrapper receives the `hidden` attribute, and
 *   - every control inside it is disabled, so it neither submits nor takes part in Select2 query narrowing
 *     (`select2.js` skips disabled reference fields).
 *
 * The same mechanic applies to the inactive panes of a `TabbedGroups` item (`data-nb-form-tab-pane`), and the index
 * of the active pane is recorded in a hidden input (`data-nb-active-tab`) so the server can treat inactive panes the
 * same way. The identical condition grammar is re-evaluated on the server during form validation
 * (`FormLayoutMixin._clean_fields`), so the browser is never the sole enforcer of a data rule.
 *
 * Conditions are re-evaluated on the form's native `change` event. Select2 widgets take part because
 * `ui/src/js/select2.js` re-dispatches their jQuery-only change notifications as native events.
 *
 * Condition grammar (mirrors `nautobot.core.ui.object_form.Condition`):
 *   {"field": name, "eq": value} | {"field": name, "in": [values]} | {"field": name, "is_set": bool}
 *   {"any": [...]} | {"all": [...]} | {"not": {...}}
 */
(function () {
    "use strict";

    const CONTROL_SELECTOR = "input, select, textarea";
    // A control inside any of these is hidden from the user and must neither submit nor take part in narrowing.
    const HIDDEN_ANCESTOR_SELECTOR = "[data-nb-visible-if][hidden]";
    // Values the browser (and Select2 in particular) uses to mean "nothing selected".
    const EMPTY_VALUES = new Set(["", "null"]);
    const FALSE_STRINGS = new Set(["", "0", "false", "off", "no", "null", "none"]);
    const DISABLED_MARKER = "nbVisibilityDisabled";
    const MAX_PASSES = 4;

    function formRoot(element) {
        return element.closest("form") || document;
    }

    function findField(root, name) {
        // Prefer the field within the same form (handles formset prefixes and embedded forms), then fall back to the
        // Django id convention.
        return root.querySelector(`[name="${CSS.escape(name)}"]`) || document.getElementById(`id_${name}`);
    }

    function fieldValue(field) {
        if (!field) {
            return null;
        }
        if (field.type === "checkbox") {
            return field.checked;
        }
        if (field.type === "radio") {
            const checked = formRoot(field).querySelector(
                `input[type="radio"][name="${CSS.escape(field.name)}"]:checked`,
            );
            return checked ? checked.value : null;
        }
        if (field.tagName === "SELECT" && field.multiple) {
            return [...field.selectedOptions].map((option) => option.value).filter((value) => !EMPTY_VALUES.has(value));
        }
        const value = field.value;
        return value === undefined || EMPTY_VALUES.has(value) ? null : value;
    }

    function asBool(value) {
        if (typeof value === "boolean") {
            return value;
        }
        if (value === null) {
            return false;
        }
        return !FALSE_STRINGS.has(String(value).toLowerCase());
    }

    function equals(actual, expected) {
        if (typeof expected === "boolean") {
            return asBool(actual) === expected;
        }
        if (actual === null || expected === null) {
            return actual === null && expected === null;
        }
        return String(actual) === String(expected);
    }

    function evaluate(condition, root) {
        if (Array.isArray(condition.any)) {
            return condition.any.some((child) => evaluate(child, root));
        }
        if (Array.isArray(condition.all)) {
            return condition.all.every((child) => evaluate(child, root));
        }
        if (condition.not !== undefined) {
            return !evaluate(condition.not, root);
        }
        const value = fieldValue(findField(root, condition.field));
        if (Object.hasOwn(condition, "is_set")) {
            const present = Array.isArray(value) ? value.length > 0 : value !== null;
            return present === Boolean(condition.is_set);
        }
        const values = Array.isArray(value) ? value : [value];
        if (Object.hasOwn(condition, "eq")) {
            return values.some((item) => equals(item, condition.eq));
        }
        if (Array.isArray(condition.in)) {
            return values.some((item) => condition.in.some((option) => equals(item, option)));
        }
        return true;
    }

    function clearControls(container) {
        container.querySelectorAll(CONTROL_SELECTOR).forEach((control) => {
            if (control.type === "hidden") {
                return;
            }
            const isCheckable = control.type === "checkbox" || control.type === "radio";
            const isEmpty = isCheckable ? !control.checked : control.value === "";
            if (isEmpty) {
                return; // Nothing to clear; avoid needless change events.
            }
            if (control.type === "checkbox" || control.type === "radio") {
                control.checked = false;
            } else if (control.tagName === "SELECT") {
                if (window.jQuery) {
                    // Select2 listens through jQuery; `val(null)` works for single and multiple selects alike. The
                    // jQuery `change` is re-dispatched natively by select2.js, so no native event is needed here.
                    window.jQuery(control).val(null).trigger("change");
                    return;
                }
                control.selectedIndex = -1;
            } else {
                control.value = "";
            }
            control.dispatchEvent(new Event("change", { bubbles: true }));
        });
    }

    function syncControls(root) {
        root.querySelectorAll(CONTROL_SELECTOR).forEach((control) => {
            const shouldDisable = control.closest(HIDDEN_ANCESTOR_SELECTOR) !== null;
            if (shouldDisable) {
                if (!control.disabled) {
                    control.disabled = true;
                    control.dataset[DISABLED_MARKER] = "true";
                }
            } else if (control.dataset[DISABLED_MARKER] === "true") {
                // Only re-enable what we disabled; leave controls the server disabled alone.
                control.disabled = false;
                delete control.dataset[DISABLED_MARKER];
            }
        });
    }

    function applyAll(root) {
        if (root.nbVisibilityApplying) {
            return;
        }
        root.nbVisibilityApplying = true;
        // The first evaluation only establishes the initial state: a stored value that no longer satisfies its
        // condition is hidden, not wiped, until the user changes something (the server hides it too, so nothing
        // flashes). `clear_on_hide` acts on transitions the user causes.
        const initial = !root.nbVisibilityInitialized;
        root.nbVisibilityInitialized = true;
        try {
            // Clearing a hidden field fires change events that other conditions may depend on, so iterate to a
            // fixed point (bounded).
            for (let pass = 0; pass < MAX_PASSES; pass++) {
                let cleared = false;
                root.querySelectorAll("[data-nb-visible-if]").forEach((wrapper) => {
                    let condition;
                    try {
                        condition = JSON.parse(wrapper.dataset.nbVisibleIf);
                    } catch (exception) {
                        return;
                    }
                    const visible = evaluate(condition, root);
                    const becameHidden = !initial && visible === false && wrapper.hidden === false;
                    wrapper.hidden = !visible;
                    if (becameHidden) {
                        // `clear_on_hide` may be declared on the hidden component itself or on fields inside it.
                        const targets =
                            wrapper.dataset.nbClearOnHide === "true"
                                ? [wrapper]
                                : [...wrapper.querySelectorAll("[data-nb-clear-on-hide]")];
                        targets.forEach((target) => {
                            clearControls(target);
                            cleared = true;
                        });
                    }
                });
                syncControls(root);
                if (!cleared) {
                    break;
                }
            }
        } finally {
            root.nbVisibilityApplying = false;
        }
    }

    function resolveScope(context) {
        if (!context) {
            return document;
        }
        if (context.nodeType) {
            return context;
        }
        if (context[0] && context[0].nodeType) {
            return context[0]; // jQuery object, as passed by `jsify_form`
        }
        return document;
    }

    /**
     * Initialize declarative visibility for every form within `context` (an element, a jQuery object, or omitted for
     * the whole document). Safe to call repeatedly: forms are bound once and re-evaluated on each call.
     */
    function initializeFormVisibility(context) {
        const scope = resolveScope(context);
        const roots = new Set();
        const candidates = scope.querySelectorAll
            ? scope.querySelectorAll("[data-nb-visible-if], .nb-form-tabbed-groups")
            : [];
        candidates.forEach((element) => roots.add(formRoot(element)));
        if (scope.matches && scope.matches("[data-nb-visible-if], .nb-form-tabbed-groups")) {
            roots.add(formRoot(scope));
        }
        roots.forEach((root) => {
            if (!root.nbVisibilityBound) {
                root.nbVisibilityBound = true;
                // NB-FIELDSETS-REVIEW[js-media] (temporary marker, delete before merge): was a jQuery `change`
                // listener because Select2 only fired jQuery events; select2.js now re-dispatches those as native
                // `change` events, so one native listener covers plain inputs and Select2 alike.
                root.addEventListener("change", () => applyAll(root));
            }
            applyAll(root);
        });
    }

    window.nb = window.nb || {};
    window.nb.formVisibility = { initialize: initializeFormVisibility, evaluate: evaluate };
    window.initializeFormVisibility = initializeFormVisibility;
})();
