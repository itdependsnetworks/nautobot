"""Fill the 'Add New Contact' form partially for screenshot capture.

This script navigates to the contact creation form and fills in some fields
without submitting, to show what a partially-completed form looks like.
"""


def setup(browser, helpers):
    """Fill contact form fields without submitting.

    Args:
        browser: Splinter Browser instance, already on the target page.
        helpers: ScreenshotHelpers instance with fill_select2_field, scroll_element_into_view, etc.
    """
    browser.fill("name", "Jane Smith")
    browser.fill("phone", "555-0142")
    browser.fill("email", "jane.smith@example.com")
