/**
 * Behaviour of `OverridableFormField` rows on the Job edit form (nautobot.extras.forms).
 *
 * Each row (`[data-nb-overridable]`, see extras/inc/overridable_field.html) pairs a property control with an
 * "Override default value" checkbox. While the checkbox is clear the control is locked and shows the job class's
 * own value, which the row carries as a JSON script (`<field id>_default`) when the class is installed; without
 * it, the value the form was rendered with is restored. Ticking the checkbox unlocks the control.
 *
 * Checkboxes cannot be read-only and selects may not offer the default as an option, so those two are *disabled*
 * rather than read-only, and re-enabled at submit time so that the browser sends them. `JobEditForm.clean()`
 * reverts non-overridden properties on the server regardless.
 */
(function () {
    "use strict";

    const DISABLED_MARKER = "nbOverridableDisabled";

    function setDisabled(control, disabled) {
        if (disabled) {
            if (!control.disabled) {
                control.disabled = true;
                control.dataset[DISABLED_MARKER] = "true";
            }
        } else if (control.dataset[DISABLED_MARKER] === "true") {
            control.disabled = false;
            delete control.dataset[DISABLED_MARKER];
        }
    }

    function bindRow(row) {
        if (row.dataset.nbOverridableBound === "true") {
            return;
        }
        const field = document.getElementById(row.dataset.nbOverridableField);
        const override = document.getElementById(row.dataset.nbOverridableOverride);
        if (!field || !override) {
            return; // Not marked bound: a later initialize() call may find the controls.
        }
        row.dataset.nbOverridableBound = "true";
        const defaultScript = document.getElementById(`${row.dataset.nbOverridableField}_default`);
        const hasDefault = defaultScript !== null;
        const defaultValue = hasDefault ? JSON.parse(defaultScript.textContent) : undefined;

        const apply = () => {
            const overridden = override.checked;
            if (field.tagName === "SELECT") {
                // The options may not include the job class value; keep the current selection and only lock it.
                setDisabled(field, !overridden);
                return;
            }
            if (field.type === "checkbox") {
                if (!overridden) {
                    field.checked = hasDefault ? Boolean(defaultValue) : field.defaultChecked;
                }
                setDisabled(field, !overridden);
                return;
            }
            if (!overridden) {
                field.value = hasDefault && defaultValue !== null ? String(defaultValue) : field.defaultValue;
            }
            field.readOnly = !overridden;
        };

        override.addEventListener("change", apply);
        apply();
    }

    function bindForm(form) {
        if (!form || form.dataset.nbOverridableSubmitBound === "true") {
            return;
        }
        form.dataset.nbOverridableSubmitBound = "true";
        form.addEventListener("submit", () => {
            form.querySelectorAll("[data-nb-overridable] :disabled").forEach((control) => setDisabled(control, false));
        });
    }

    function initialize(scope) {
        const root = scope && scope.querySelectorAll ? scope : document;
        root.querySelectorAll("[data-nb-overridable]").forEach((row) => {
            bindRow(row);
            bindForm(row.closest("form"));
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => initialize(document));
    } else {
        initialize(document);
    }
    if (window.htmx) {
        window.htmx.onLoad((content) => initialize(content));
    }

    window.nb = window.nb || {};
    window.nb.overridableField = { initialize: initialize };
})();
