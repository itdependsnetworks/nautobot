/**
 * Behaviour for the shared scope filter card (inc/scope_filter_card.html).
 *
 * Used by every form whose model's scope is a stored filter over another model -- custom fields and
 * retention rules today. Lifted out of the custom field template so the two cannot drift apart; the only
 * per-form difference is which select changes the target model, named by `data-nb-scope-filter-trigger`
 * on the card container.
 */

/**
 * Re-initialize select2 fields after HTMX replaces the card.
 *
 * Called from `hx-on::after-settle` on the container. Does nothing when the swapped-in content is one of
 * the placeholder messages rather than a filter form.
 *
 * @param event
 */
const initializeScopeFilter = event => {
    const container = document.getElementById('nb-scope-filter-form-container');
    if (container && container.querySelector('#filter-tabs')) {
        window.nb.select2.initializeSelect2Fields(event.target)
    }
}

/**
 * Get HTML elements for default and dynamic filter forms.
 * @returns {object} Object with `defaultFilterForm` and `dynamicFilterForm` HTML elements or `null`,
 *   depending on their actual existence in the DOM.
 */
const getFilterForms = () => ({
    defaultFilterForm: document.querySelector('#default-filter'),
    dynamicFilterForm: document.querySelector('#advanced-filter'),
});

/**
 * Check if submit event is from default filter form or other form on page.
 * @param defaultFilterForm
 * @param event
 * @returns {boolean}
 */
const isEventFromDefaultFilterFormField = (defaultFilterForm, event) => (
    event.target.closest(`#${defaultFilterForm?.id}`) !== null
)

/**
 * Function to reinitialize select2 fields after changes on filter form.
 * filter_form.js will call this function when re-initialization is needed.
 * @param element
 */
const reInitialize = element => {
    window.nb.select2.initializeSelect2Fields(element)
}

/**
 * Function to set name for newly created input after adding filter on advanced tab.
 * filter_form.js will call this function to set correct filter input name
 * @param name
 */
const getInputName = (name) => (`scope-${name}`)

document.addEventListener('DOMContentLoaded', () => {
    /*
     * Select2 does not emit a plain `change` event, which is what HTMX listens for, so the select that
     * chooses the target model has its select2 events re-mapped. Which select that is differs per form.
     */
    const container = document.getElementById('nb-scope-filter-form-container');
    const triggerSelector = container?.dataset.nbScopeFilterTrigger;
    if (triggerSelector) {
        $(triggerSelector).on('select2:select select2:unselect select2:clear', function () {
            htmx.trigger(triggerSelector, 'change')
        });
    }

    document.addEventListener('submit', (event) => {
        const { defaultFilterForm, dynamicFilterForm } = getFilterForms();
        // No card on the page, or a placeholder message in place of the filter form.
        if (!defaultFilterForm || !dynamicFilterForm) {
            return;
        }

        /*
         * Just before the form submission automatically add filter selected in "Advanced" tab (if any)
         * which hasn't been manually applied for whatever reason (usually forgetfulness, speed, etc.).
         * This is a requested UX flavor.
         */
        const add = dynamicFilterForm.querySelector('button.nb-dynamic-filter-add');
        if (add) {
            add.click();
        }

        /*
         * Data on default and advanced tabs are synchronized and we can't send both forms
         * to avoid data duplication. To do that we need to remove name attributes from inputs
         * that are belongs to the default tab just before form submission.
         */
        defaultFilterForm
            .querySelectorAll('input[name], select[name], textarea[name]')
            .forEach(el => {
                el.dataset.originalName = el.name
                el.removeAttribute('name')
            })
    }, {capture: true});
});
