"""Playwright tests for the users app. Run with `invoke playwright --app users`."""

from nautobot.playwright import load_tests  # noqa: F401  keeps unittest discovery out; see nautobot.playwright
