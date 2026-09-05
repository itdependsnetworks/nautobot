"""Users-app Playwright fixtures: policy cleanup and browser error capture."""

import pytest


@pytest.fixture
def policy_cleanup(api):
    """Collect names of permission policies a test creates through the UI; delete them on teardown."""
    names = []
    yield names
    for name in names:
        response = api.get("/api/users/permission-policies/", params={"name": name})
        for record in response.json().get("results", []):
            api.delete(f"/api/users/permission-policies/{record['id']}/")


@pytest.fixture
def browser_errors(auth_page):
    """Uncaught page errors and console errors raised during the test; assert it is empty at the end."""
    errors = []
    auth_page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    auth_page.on("console", lambda msg: errors.append(f"console.error: {msg.text}") if msg.type == "error" else None)
    return errors
