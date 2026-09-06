/**
 * Initialization of `jquery.formset.js` for every `FormSetPanel` on the page (nautobot.core.ui.object_form).
 *
 * The panel's table carries `data-nb-formset-prefix`, `data-nb-formset-add-label` and, optionally,
 * `data-nb-formset-keep-field-values` (see components/form/formset_body.html). Shipped through the panel's `Media`
 * declaration, so a page template no longer needs its own `$('.formset_row-...').formset({...})` block.
 *
 * NB-FIELDSETS-REVIEW[js-media] (temporary marker, delete before merge): new file; replaces seven identical
 * per-template script blocks.
 */
(function () {
    "use strict";

    function escapeHtml(text) {
        const span = document.createElement("span");
        span.textContent = text;
        return span.innerHTML;
    }

    function initializeTable(table) {
        if (table.dataset.nbFormsetBound === "true") {
            return;
        }
        if (!window.jQuery || !window.jQuery.fn.formset) {
            return; // jquery.formset.js is not on this page; nothing to do.
        }
        table.dataset.nbFormsetBound = "true";

        const prefix = table.dataset.nbFormsetPrefix;
        const addLabel = table.dataset.nbFormsetAddLabel || "row";
        const label = escapeHtml(addLabel);
        const options = {
            // No whitespace between the icon and the text: the gap is the icon's `me-4` (see the UI best practices
            // guide). The delete button is icon-only, so it carries a visually hidden name.
            addText: `<span class="mdi mdi-plus-thick me-4" aria-hidden="true"></span>Add another ${label}`,
            addCssClass: "btn btn-primary add-row",
            deleteText:
                '<span class="mdi mdi-trash-can-outline" aria-hidden="true"></span>' +
                `<span class="visually-hidden">Remove this ${label}</span>`,
            deleteCssClass: "btn btn-danger delete-row",
            prefix: prefix,
            formCssClass: `dynamic-formset-${prefix}`,
            added: window.jsify_form,
        };
        if (table.dataset.nbFormsetKeepFieldValues) {
            options.keepFieldValues = table.dataset.nbFormsetKeepFieldValues;
        }
        // Scoped to this table: the same prefix may exist twice on a page (page form plus embedded modal).
        window.jQuery(table.querySelectorAll(`tr.formset_row-${prefix}`)).formset(options);
    }

    function initialize(scope) {
        const root = scope && scope.querySelectorAll ? scope : scope && scope[0] ? scope[0] : document;
        root.querySelectorAll("table[data-nb-formset-prefix]").forEach(initializeTable);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => initialize(document));
    } else {
        initialize(document);
    }
    // A panel can also arrive with HTMX-swapped content (an embedded-create modal, a re-rendered fragment).
    if (window.htmx) {
        window.htmx.onLoad((content) => initialize(content));
    }

    window.nb = window.nb || {};
    window.nb.formsetPanel = { initialize: initialize };
})();
