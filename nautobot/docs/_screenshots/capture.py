"""Automated screenshot capture engine for Nautobot documentation.

Parses markdown files for `[//]: # (screenshot: ...)` comments, resolves
output paths from paired image references, and captures screenshots using
Selenium/Splinter against a running Nautobot instance.

Usage (via invoke):
    invoke capture-screenshots
    invoke capture-screenshots --base-url http://localhost:8080 --path nautobot/docs/_screenshots/sample.md
    invoke capture-screenshots --dry-run
"""

import importlib.util
import os
import re
import shlex
import sys
import time

from PIL import Image, ImageDraw

from nautobot.docs._screenshots.regions import (
    REGIONS,
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
)

# Default URLs matching the docker-compose service names.
# Override via env vars (same as nautobot.core.testing.integration) or CLI args.
DEFAULT_SELENIUM_URL = os.getenv("NAUTOBOT_SELENIUM_URL", "http://selenium:4444/wd/hub")
DEFAULT_BASE_URL = os.getenv("NAUTOBOT_SCREENSHOT_BASE_URL", "http://nautobot:8080")

# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

# Matches: [//]: # (screenshot: url=/foo region=bar ...)
SCREENSHOT_COMMENT_RE = re.compile(r'^\[//\]: # \(screenshot:\s+(.+)\)\s*$')

# Matches: [//]: # (media: type=diagram note="..." ...)
MEDIA_COMMENT_RE = re.compile(r'^\[//\]: # \(media:\s+(.+)\)\s*$')

# Matches: ![alt text](path/to/image.png#only-light){ .on-glb }
# or:      ![alt text](path/to/image.png#only-dark){ .on-glb }
IMAGE_REF_RE = re.compile(r'^!\[([^\]]*)\]\(([^)]+)\)(?:\{[^}]*\})?\s*$')


def parse_screenshot_params(param_string):
    """Parse 'url=/foo region=bar highlight=.a,.b script=x.py' into a dict.

    Uses shlex to handle quoted values like url='/path with spaces/'.
    """
    params = {}
    tokens = shlex.split(param_string)
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            params[key] = value
        else:
            # Bare token -- treat as url for convenience
            if "url" not in params:
                params["url"] = token
    return params


def _resolve_image_paths(lines, comment_line_idx, file_dir):
    """Look upward from a comment line to find paired light/dark image references."""
    light_path = None
    dark_path = None
    j = comment_line_idx - 1
    while j >= 0:
        img_match = IMAGE_REF_RE.match(lines[j].strip())
        if img_match:
            img_path = img_match.group(2)
            if "#only-light" in img_path:
                raw_path = img_path.split("#only-light")[0]
                light_path = os.path.normpath(os.path.join(file_dir, raw_path))
            elif "#only-dark" in img_path:
                raw_path = img_path.split("#only-dark")[0]
                dark_path = os.path.normpath(os.path.join(file_dir, raw_path))
            j -= 1
        else:
            break
    return light_path, dark_path


# Matches the old-style URL comment: [//]: # "`https://...`"
OLD_URL_COMMENT_RE = re.compile(r'^\[//\]: # "`(https?://.+)`"\s*$')


def parse_markdown_file(filepath):
    """Parse a single markdown file for screenshot and media specs.

    Looks for `[//]: # (screenshot: ...)` and `[//]: # (media: ...)` lines
    and resolves output image paths from paired image references above.

    Also detects image pairs with old-style URL comments or no comment at all,
    tagging them as type=unknown media specs.

    Returns:
        Tuple of (screenshot_specs, media_specs).
    """
    filepath = os.path.abspath(filepath)
    file_dir = os.path.dirname(filepath)
    screenshot_specs = []
    media_specs = []

    with open(filepath, "r") as f:
        lines = f.readlines()

    # Track which image-reference lines are "claimed" by a screenshot/media comment
    claimed_image_lines = set()

    for i, line in enumerate(lines):
        stripped = line.strip()

        # --- Media comments ---
        media_match = MEDIA_COMMENT_RE.match(stripped)
        if media_match:
            params = parse_screenshot_params(media_match.group(1))
            light_path, dark_path = _resolve_image_paths(lines, i, file_dir)
            media_specs.append({
                "type": params.get("type", "unknown"),
                "note": params.get("note", ""),
                "source": params.get("source", ""),
                "light_path": light_path,
                "dark_path": dark_path,
                "source_file": filepath,
                "source_line": i + 1,
            })
            # Mark the image lines above as claimed
            j = i - 1
            while j >= 0 and IMAGE_REF_RE.match(lines[j].strip()):
                claimed_image_lines.add(j)
                j -= 1
            continue

        # --- Screenshot comments ---
        match = SCREENSHOT_COMMENT_RE.match(stripped)
        if match:
            params = parse_screenshot_params(match.group(1))
            if "url" not in params:
                print(f"WARNING: {filepath}:{i + 1} -- screenshot comment missing 'url' param, skipping", file=sys.stderr)
                continue

            light_path, dark_path = _resolve_image_paths(lines, i, file_dir)

            highlight_str = params.get("highlight", "")
            highlights = [s.strip() for s in highlight_str.split(",") if s.strip()] if highlight_str else []

            screenshot_specs.append({
                "url": params["url"],
                "region": params.get("region", "full"),
                "selector": params.get("selector"),
                "highlight": highlights,
                "script": params.get("script"),
                "height": params.get("height"),
                "crop_top": params.get("crop_top"),
                "crop_bottom": params.get("crop_bottom"),
                "light_path": light_path,
                "dark_path": dark_path,
                "source_file": filepath,
                "source_line": i + 1,
            })
            # Mark the image lines above as claimed
            j = i - 1
            while j >= 0 and IMAGE_REF_RE.match(lines[j].strip()):
                claimed_image_lines.add(j)
                j -= 1
            continue

        # --- Old-style URL comments: claim the images above ---
        if OLD_URL_COMMENT_RE.match(stripped):
            j = i - 1
            while j >= 0 and IMAGE_REF_RE.match(lines[j].strip()):
                claimed_image_lines.add(j)
                j -= 1

    # --- Second pass: find unclaimed image pairs (unknown) ---
    i = 0
    while i < len(lines):
        if i in claimed_image_lines:
            i += 1
            continue
        img_match = IMAGE_REF_RE.match(lines[i].strip())
        if img_match:
            # Collect consecutive image lines starting here
            light_path = None
            dark_path = None
            start_line = i
            while i < len(lines):
                m = IMAGE_REF_RE.match(lines[i].strip())
                if not m or i in claimed_image_lines:
                    break
                img_path = m.group(2)
                if "#only-light" in img_path:
                    raw_path = img_path.split("#only-light")[0]
                    light_path = os.path.normpath(os.path.join(file_dir, raw_path))
                elif "#only-dark" in img_path:
                    raw_path = img_path.split("#only-dark")[0]
                    dark_path = os.path.normpath(os.path.join(file_dir, raw_path))
                i += 1

            if light_path or dark_path:
                media_specs.append({
                    "type": "unknown",
                    "note": "",
                    "source": "",
                    "light_path": light_path,
                    "dark_path": dark_path,
                    "source_file": filepath,
                    "source_line": start_line + 1,
                })
        else:
            i += 1

    return screenshot_specs, media_specs


def filter_specs_by_name(specs, names):
    """Filter screenshot specs to only those whose output filenames match any of the given names.

    Matches against the base filename (without extension) of either the light or dark output path.
    Supports partial matching -- "ss_circuit" matches "ss_circuit_light.png" and "ss_circuit_dark.png".

    Args:
        specs: List of screenshot spec dicts.
        names: List of name strings to match against.

    Returns:
        Filtered list of specs.
    """
    filtered = []
    for spec in specs:
        for path in [spec["light_path"], spec["dark_path"]]:
            if not path:
                continue
            basename = os.path.basename(path)
            if any(n in basename for n in names):
                filtered.append(spec)
                break
    return filtered


def find_all_specs(paths):
    """Walk one or more directories/files and collect screenshot + media specs.

    Args:
        paths: List of file or directory paths to scan.

    Returns:
        Tuple of (screenshot_specs, media_specs).
    """
    all_screenshots = []
    all_media = []
    for path in paths:
        path = os.path.abspath(path)
        if os.path.isfile(path) and path.endswith(".md"):
            screenshots, media = parse_markdown_file(path)
            all_screenshots.extend(screenshots)
            all_media.extend(media)
        elif os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for filename in sorted(files):
                    if filename.endswith(".md"):
                        screenshots, media = parse_markdown_file(os.path.join(root, filename))
                        all_screenshots.extend(screenshots)
                        all_media.extend(media)
    return all_screenshots, all_media


# ---------------------------------------------------------------------------
# Screenshot helpers (wraps Splinter/Selenium for setup scripts)
# ---------------------------------------------------------------------------

class ScreenshotHelpers:
    """Exposes common Selenium/Splinter helpers for use in setup scripts.

    Mirrors the API from nautobot.core.testing.integration.SeleniumTestCase
    so that script authors use familiar methods.
    """

    def __init__(self, browser):
        self.browser = browser

    def fill_select2_field(self, field_name, value):
        """Fill a Select2 single-selection field."""
        from selenium.webdriver.common.keys import Keys  # noqa: E402

        self.browser.find_by_xpath(f"//select[@id='id_{field_name}']//following-sibling::span").click()
        self.scroll_element_into_view(css=f"#id_{field_name}")
        search_box = self.browser.find_by_xpath(
            "//*[@class='select2-search select2-search--dropdown']//input",
            wait_time=5,
        )
        for _ in search_box.first.type(value, slowly=True):
            pass
        self.browser.is_element_not_present_by_css(".loading-results", wait_time=5)
        # Select first result
        results = self.browser.find_by_css(".select2-results li.select2-results__option")
        if results.first.text != "None":
            results.first.click()
        else:
            results[1].click()

    def fill_select2_multiselect_field(self, field_name, value):
        """Fill a Select2 multi-selection field."""
        from selenium.webdriver.common.keys import Keys  # noqa: E402

        search_box = self.browser.find_by_xpath(
            f"//select[@id='id_{field_name}']//following-sibling::span//input"
        )
        for _ in search_box.first.type(value, slowly=True):
            pass
        self.browser.is_element_not_present_by_css(".loading-results", wait_time=5)
        search_box.first.type(Keys.ENTER)

    def click_button(self, query_selector):
        """Click a button, scrolling it into view first."""
        from selenium.webdriver.common.by import By  # noqa: E402
        from selenium.webdriver.support.expected_conditions import element_to_be_clickable  # noqa: E402
        from selenium.webdriver.support.wait import WebDriverWait  # noqa: E402

        self.browser.is_element_present_by_css(query_selector, wait_time=5)
        self.scroll_element_into_view(css=query_selector)
        WebDriverWait(self.browser.driver, 30).until(
            element_to_be_clickable((By.CSS_SELECTOR, query_selector))
        )
        self.browser.find_by_css(query_selector).click()

    def scroll_element_into_view(self, element=None, css=None, xpath=None, block="start"):
        """Scroll an element into view."""
        if css:
            element = self.browser.find_by_css(css)
        elif xpath:
            element = self.browser.find_by_xpath(xpath)
        el = element.first._element if hasattr(element, "__iter__") else element._element
        self.browser.execute_script(
            f"arguments[0].scrollIntoView({{ behavior: 'instant', block: '{block}' }});", el
        )

    def switch_tab(self, tab_name):
        """Switch to a tab by name on a detail view."""
        tabs_container_xpath = '//div[@data-nb-tests-id="object-details-header-tabs"]'
        tab_xpath = f'{tabs_container_xpath}//a[contains(normalize-space(), "{tab_name}")]'
        tab = self.browser.find_by_xpath(tab_xpath, wait_time=5)
        if tab:
            tab.click()
            time.sleep(0.5)  # Allow tab content to render


# ---------------------------------------------------------------------------
# Setup script loader
# ---------------------------------------------------------------------------

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")


def load_setup_script(script_name):
    """Import a setup script from the scripts directory and return its setup() function.

    Args:
        script_name: Filename (e.g., 'fill-contact-form.py') relative to the scripts dir.

    Returns:
        The setup(browser, helpers) callable, or None if not found.
    """
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.isfile(script_path):
        print(f"WARNING: Setup script not found: {script_path}", file=sys.stderr)
        return None

    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "setup"):
        print(f"WARNING: Script {script_path} has no setup() function", file=sys.stderr)
        return None

    return module.setup


# ---------------------------------------------------------------------------
# Theme switching
# ---------------------------------------------------------------------------

def set_theme(browser, theme):
    """Switch Nautobot's theme without a page reload.

    Sets both data-bs-theme and data-theme attributes on <html>, plus the
    theme cookies so server-side rendering stays consistent.
    """
    browser.execute_script(f"""
        document.documentElement.setAttribute('data-bs-theme', '{theme}');
        document.documentElement.setAttribute('data-theme', '{theme}');
        document.cookie = 'theme={theme}; path=/; max-age=31536000';
        document.cookie = 'theme_choice={theme}; path=/; max-age=31536000';
        // Trigger handlers that listen for theme changes (ECharts, syntax highlighter)
        if (typeof setTheme === 'function') {{
            setTheme();
        }} else if (typeof handleEchartsThemeChange === 'function') {{
            handleEchartsThemeChange();
        }}
    """)
    time.sleep(0.5)  # Allow CSS transitions and re-renders


# ---------------------------------------------------------------------------
# Page cleanup
# ---------------------------------------------------------------------------

def hide_debug_toolbar(browser):
    """Hide the Django Debug Toolbar so it doesn't appear in screenshots."""
    browser.execute_script("""
        var djdt = document.getElementById('djDebug');
        if (djdt) { djdt.style.display = 'none'; }
    """)


# ---------------------------------------------------------------------------
# Capture engine
# ---------------------------------------------------------------------------

def collapse_sidenav(browser):
    """Collapse the sidenav so full-page screenshots show the minimized navbar."""
    browser.execute_script("""
        var sidenav = document.getElementById('sidenav');
        if (sidenav && !sidenav.classList.contains('nb-sidenav-collapsed')) {
            sidenav.classList.add('nb-sidenav-collapsed');
            // Update the toggler state to match
            var toggler = sidenav.querySelector('[aria-label="Collapse sidenav"]');
            if (toggler) { toggler.setAttribute('aria-expanded', 'false'); }
        }
        document.cookie = 'sidenav_collapsed=true; path=/; max-age=31536000';
    """)
    time.sleep(0.3)


def expand_sidenav(browser):
    """Expand the sidenav (for navbar screenshots that need the full menu)."""
    browser.execute_script("""
        var sidenav = document.getElementById('sidenav');
        if (sidenav && sidenav.classList.contains('nb-sidenav-collapsed')) {
            sidenav.classList.remove('nb-sidenav-collapsed');
            var toggler = sidenav.querySelector('[aria-label="Collapse sidenav"]');
            if (toggler) { toggler.setAttribute('aria-expanded', 'true'); }
        }
        document.cookie = 'sidenav_collapsed=false; path=/; max-age=31536000';
    """)
    time.sleep(0.3)


def take_full_page_screenshot(browser):
    """Take a screenshot of the full page and return it as a PIL Image.

    Temporarily expands the viewport height to fit all page content so nothing
    is clipped, while keeping the width locked at VIEWPORT_WIDTH for correct
    CSS layout.  Restores the original viewport height afterward.
    """
    import io

    # Get the full page scroll height
    scroll_height = browser.execute_script(
        "return Math.max(document.body.scrollHeight, document.body.offsetHeight, "
        "document.documentElement.scrollHeight);"
    )

    # Expand viewport height to fit, keep width fixed
    browser.driver.set_window_size(VIEWPORT_WIDTH, scroll_height)
    time.sleep(0.3)  # Allow reflow

    png_bytes = browser.driver.get_screenshot_as_png()

    # Restore original viewport height
    browser.driver.set_window_size(VIEWPORT_WIDTH, VIEWPORT_HEIGHT)

    return Image.open(io.BytesIO(png_bytes))


def take_viewport_screenshot(browser, height_css):
    """Take a screenshot at a fixed viewport height and return it as a PIL Image.

    Sets the viewport to the given height (CSS pixels) and captures exactly
    what's visible -- no expansion to fit page content.  Useful for showing
    sticky footers (Create/Cancel buttons) without scrolling through all fields.
    """
    import io

    browser.driver.set_window_size(VIEWPORT_WIDTH, int(height_css))
    time.sleep(0.3)  # Allow reflow

    png_bytes = browser.driver.get_screenshot_as_png()

    # Restore original viewport height
    browser.driver.set_window_size(VIEWPORT_WIDTH, VIEWPORT_HEIGHT)

    return Image.open(io.BytesIO(png_bytes))


def get_device_pixel_ratio(browser):
    """Get the actual device pixel ratio from the browser."""
    return browser.execute_script("return window.devicePixelRatio;") or 1


def resolve_y_boundary(browser, value, dpr, edge="bottom"):
    """Resolve a crop boundary to a device-pixel y-coordinate.

    For "bottom" edge boundaries, adds a small buffer below the element.
    The buffer is half the gap to the next visible element below, capped
    at 20 CSS px. This gives breathing room without awkwardly clipping
    into the next element.

    Args:
        browser: Splinter Browser instance.
        value: Either a CSS selector string or a pixel offset (as string, e.g. "100").
        dpr: Device pixel ratio.
        edge: "top" to use the element's top edge, "bottom" for its bottom edge.

    Returns:
        y-coordinate in device pixels.
    """
    MAX_PADDING_CSS = 20  # max padding in CSS pixels

    # If it's a number, treat as CSS pixels (no auto-padding for explicit values)
    try:
        return int(int(value) * dpr)
    except ValueError:
        pass

    # Otherwise treat as a CSS selector
    elements = browser.find_by_css(value)
    if not elements:
        print(f"  WARNING: Crop boundary selector '{value}' not found", file=sys.stderr)
        return 0

    if edge == "top":
        rect = browser.execute_script(
            "var r = arguments[0].getBoundingClientRect(); return {top: r.top};",
            elements.first._element,
        )
        return int(rect["top"] * dpr)

    # For bottom edge: get the element's bottom and find the gap to the next element
    gap_and_bottom = browser.execute_script("""
        var el = arguments[0];
        var rect = el.getBoundingClientRect();
        var bottom = rect.bottom;

        // Walk siblings and their children to find the next visible element below
        var gap = arguments[1];  // default to max padding if nothing found below
        var candidate = el.nextElementSibling;
        while (candidate) {
            var cRect = candidate.getBoundingClientRect();
            if (cRect.height > 0 && cRect.top > bottom) {
                gap = cRect.top - bottom;
                break;
            }
            candidate = candidate.nextElementSibling;
        }

        // Also check parent's next siblings if no sibling found
        if (gap === arguments[1] && el.parentElement) {
            candidate = el.parentElement.nextElementSibling;
            while (candidate) {
                var cRect = candidate.getBoundingClientRect();
                if (cRect.height > 0 && cRect.top > bottom) {
                    gap = cRect.top - bottom;
                    break;
                }
                candidate = candidate.nextElementSibling;
            }
        }

        return {bottom: bottom, gap: gap};
    """, elements.first._element, MAX_PADDING_CSS)

    bottom = gap_and_bottom["bottom"]
    gap = gap_and_bottom["gap"]

    # Use half the gap as padding, capped at MAX_PADDING_CSS
    padding = min(gap / 2, MAX_PADDING_CSS)

    return int((bottom + padding) * dpr)


def get_element_rect(browser, selector, dpr):
    """Get an element's bounding box in device pixels.

    Returns:
        Dict with x, y, width, height in device pixels, or None if not found.
    """
    elements = browser.find_by_css(selector)
    if not elements:
        return None

    rect = browser.execute_script(
        "var r = arguments[0].getBoundingClientRect(); "
        "return {x: r.x, y: r.y, width: r.width, height: r.height};",
        elements.first._element,
    )

    return {
        "x": int(rect["x"] * dpr),
        "y": int(rect["y"] * dpr),
        "width": int(rect["width"] * dpr),
        "height": int(rect["height"] * dpr),
    }


def crop_region(full_image, element_rect, target_width):
    """Crop a fixed-width region from a screenshot, centered on an element.

    The output is exactly `target_width` pixels wide at the same pixel density
    as the full screenshot (no resize). The full element height is used.

    Args:
        full_image: PIL Image of the full page screenshot.
        element_rect: Dict with x, y, width, height in device pixels.
        target_width: Desired output width in device pixels.

    Returns:
        Cropped PIL Image.
    """
    img_w, img_h = full_image.size
    el_x = element_rect["x"]
    el_y = element_rect["y"]
    el_w = element_rect["width"]
    el_h = element_rect["height"]

    # Center the target_width crop on the element horizontally
    el_center_x = el_x + el_w // 2
    crop_x1 = el_center_x - target_width // 2
    crop_x2 = crop_x1 + target_width

    # Shift if the crop falls outside image bounds
    if crop_x1 < 0:
        crop_x1 = 0
        crop_x2 = target_width
    if crop_x2 > img_w:
        crop_x2 = img_w
        crop_x1 = max(0, img_w - target_width)

    # Use the element's full vertical extent
    crop_y1 = max(0, el_y)
    crop_y2 = min(el_y + el_h, img_h)

    return full_image.crop((crop_x1, crop_y1, crop_x2, crop_y2))


def capture_one(browser, spec, base_url, helpers):
    """Capture a single screenshot spec (both light and dark).

    Every screenshot is taken at the standard viewport (1920x960) with the
    sidenav collapsed.  For regions other than "full", the image is then
    cropped to the element defined by the region's CSS selector.

    Args:
        browser: Splinter Browser instance, already logged in.
        spec: A screenshot spec dict from parse_markdown_file().
        base_url: Base URL of the Nautobot instance.
        helpers: ScreenshotHelpers instance.

    Returns:
        List of output file paths that were written.
    """
    region_name = spec["region"]
    region = REGIONS.get(region_name)
    if region is None:
        print(f"WARNING: Unknown region '{region_name}' at {spec['source_file']}:{spec['source_line']}", file=sys.stderr)
        return []

    # Navigate to the URL
    url = base_url.rstrip("/") + "/" + spec["url"].lstrip("/")
    browser.visit(url)
    browser.is_element_present_by_tag("body", wait_time=10)
    time.sleep(1)  # Allow dynamic content to render

    # Hide Django Debug Toolbar if present
    hide_debug_toolbar(browser)

    # Full-screen screenshots collapse the sidenav so more content is visible.
    # All other regions keep the sidenav expanded -- it gets cropped out anyway,
    # and the expanded sidenav gives #main-content a narrower, more natural width.
    if region_name in ("full", "list-view"):
        collapse_sidenav(browser)
    else:
        expand_sidenav(browser)

    # Run setup script if specified
    if spec["script"]:
        setup_fn = load_setup_script(spec["script"])
        if setup_fn:
            setup_fn(browser, helpers)
            time.sleep(0.5)  # Allow script actions to render

    # Remove focus ring from any active element so it doesn't appear in screenshots
    browser.execute_script("if (document.activeElement) { document.activeElement.blur(); }")

    # Determine the crop selector and target width
    selector = spec["selector"] or region["selector"]
    target_width = region["target_width"]

    # Detect DPR for coordinate scaling (CSS pixels → device pixels)
    dpr = get_device_pixel_ratio(browser)

    # Get the element rect once (shared across light/dark captures)
    el_rect = None
    if selector:
        el_rect = get_element_rect(browser, selector, dpr)
        if el_rect is None:
            print(
                f"  WARNING: Selector '{selector}' not found on {url} "
                f"(spec at {spec['source_file']}:{spec['source_line']})",
                file=sys.stderr,
            )
            return []

    output_files = []

    for theme, output_path in [("light", spec["light_path"]), ("dark", spec["dark_path"])]:
        if output_path is None:
            continue

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Set theme
        set_theme(browser, theme)

        # --- Capture the raw screenshot ---
        # Mode 1 (height=): fixed viewport height, capture what's visible
        # Mode 2/3 (crop_top=/crop_bottom=): full page, then crop vertically
        # Default: full page
        if spec["height"]:
            raw_image = take_viewport_screenshot(browser, int(spec["height"]))
        else:
            raw_image = take_full_page_screenshot(browser)

        # --- Horizontal crop: fixed target_width centered on element ---
        if el_rect:
            final_image = crop_region(raw_image, el_rect, target_width)
            # Track the horizontal crop origin for highlight offset
            el_center_x = el_rect["x"] + el_rect["width"] // 2
            crop_x1 = el_center_x - target_width // 2
            if crop_x1 < 0:
                crop_x1 = 0
            if crop_x1 + target_width > raw_image.width:
                crop_x1 = max(0, raw_image.width - target_width)
            crop_y1 = max(0, el_rect["y"])
        else:
            final_image = raw_image
            crop_x1 = 0
            crop_y1 = 0

        # --- Vertical crop (modes 2 and 3) ---
        # Applied after horizontal crop. crop_top/crop_bottom are resolved
        # relative to the full page, then offset by the horizontal crop origin.
        if not spec["height"] and (spec["crop_top"] or spec["crop_bottom"]):
            img_w, img_h = final_image.size

            if spec["crop_top"]:
                y_top = resolve_y_boundary(browser, spec["crop_top"], dpr, edge="top") - crop_y1
                y_top = max(0, y_top)
            else:
                y_top = 0

            if spec["crop_bottom"]:
                y_bottom = resolve_y_boundary(browser, spec["crop_bottom"], dpr, edge="bottom") - crop_y1
                y_bottom = min(img_h, y_bottom)
            else:
                y_bottom = img_h

            if y_top < y_bottom:
                final_image = final_image.crop((0, y_top, img_w, y_bottom))

        # --- Apply highlights ---
        if spec["highlight"]:
            draw = ImageDraw.Draw(final_image)
            # Compute full vertical offset for highlight coordinate translation
            hl_y_offset = crop_y1
            if not spec["height"] and spec["crop_top"]:
                hl_y_offset += resolve_y_boundary(browser, spec["crop_top"], dpr, edge="top") - crop_y1

            highlight_elements = browser.find_by_css(",".join(spec["highlight"]))
            for hl_el in highlight_elements:
                rect = browser.execute_script(
                    "var r = arguments[0].getBoundingClientRect(); "
                    "return {x: r.x, y: r.y, width: r.width, height: r.height};",
                    hl_el._element,
                )
                # 5px padding around the element so the box doesn't sit flush
                pad = int(5 * dpr)
                x = int(rect["x"] * dpr) - crop_x1 - pad
                y = int(rect["y"] * dpr) - hl_y_offset - pad
                w = int(rect["width"] * dpr) + 2 * pad
                h = int(rect["height"] * dpr) + 2 * pad
                draw.rectangle([x, y, x + w, y + h], outline="red", width=3)

        final_image.save(output_path, format="PNG")

        output_files.append(output_path)
        print(f"  Captured: {os.path.relpath(output_path)} ({theme}, {final_image.width}x{final_image.height})")

    return output_files


def login(browser, base_url, username, password):
    """Log into the Nautobot instance."""
    browser.visit(f"{base_url}/login/")
    browser.fill("username", username)
    browser.fill("password", password)
    button = browser.find_by_xpath("//button[text()='Log In']")
    if button:
        button.first.click()
    # Wait for redirect after login
    time.sleep(2)


def run_capture(specs, base_url, username, password, selenium_url=None):
    """Run the full capture pipeline.

    Args:
        specs: List of screenshot spec dicts.
        base_url: Nautobot instance URL.
        username: Login username.
        password: Login password.
        selenium_url: Selenium WebDriver hub URL.

    Returns:
        Tuple of (captured_files, error_count).
    """
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from splinter.browser import Browser

    if selenium_url is None:
        selenium_url = DEFAULT_SELENIUM_URL

    # Set DPR to 1.5 to match the docs-media-standards.md custom device.
    # At 1280x960 viewport with DPR 1.5, screenshots are 1920px wide --
    # same visual density as the manual Chrome DevTools workflow.
    options = FirefoxOptions()
    options.set_preference("layout.css.devPixelsPerPx", "1.5")

    print(f"Connecting to Selenium at {selenium_url}...")
    browser = Browser("remote", command_executor=selenium_url, options=options)

    try:
        # Set viewport to 1280x960 CSS pixels. With DPR 1.5, screenshots
        # will be 1920x1440 device pixels (matching the 1920px standard).
        browser.driver.set_window_size(VIEWPORT_WIDTH, VIEWPORT_HEIGHT)

        print(f"Logging into {base_url}...")
        login(browser, base_url, username, password)

        helpers = ScreenshotHelpers(browser)
        captured = []
        errors = 0

        for i, spec in enumerate(specs, 1):
            print(f"[{i}/{len(specs)}] {spec['url']} (region={spec['region']})")
            try:
                files = capture_one(browser, spec, base_url, helpers)
                captured.extend(files)
            except Exception as e:
                print(f"  ERROR: {e}", file=sys.stderr)
                errors += 1

        return captured, errors
    finally:
        browser.quit()


# ---------------------------------------------------------------------------
# Media (non-automated) handling
# ---------------------------------------------------------------------------

STAMP_SIZE = 40  # size of the triangle marker in pixels


def stamp_media_image(image_path):
    """Add a red triangle to the top-right corner of an image.

    This marks the image as needing manual attention, making it easy to
    spot in diff views (red is visible in both light and dark modes).
    """
    try:
        img = Image.open(image_path)
        # Convert palette-mode images to RGB so we can draw in color
        if img.mode == "P":
            img = img.convert("RGB")
    except Exception as e:
        print(f"  WARNING: Could not open {image_path}: {e}", file=sys.stderr)
        return False

    draw = ImageDraw.Draw(img)
    w = img.width
    s = STAMP_SIZE
    # Red triangle in top-right corner
    draw.polygon([(w - s, 0), (w, 0), (w, s)], fill="red")
    img.save(image_path)
    return True


def stamp_media_specs(media_specs):
    """Stamp all media images with a black triangle marker.

    Returns:
        Tuple of (stamped_count, error_count).
    """
    stamped = 0
    errors = 0
    for spec in media_specs:
        for path in [spec["light_path"], spec["dark_path"]]:
            if path and os.path.isfile(path):
                if stamp_media_image(path):
                    print(f"  Stamped: {os.path.relpath(path)}")
                    stamped += 1
                else:
                    errors += 1
    return stamped, errors


def print_media_summary(media_specs):
    """Print a summary of non-automated media items."""
    if not media_specs:
        return
    print(f"\nFound {len(media_specs)} non-automated media item(s):\n")
    for i, spec in enumerate(media_specs, 1):
        print(f"  {i}. {spec['source_file']}:{spec['source_line']}")
        print(f"     Type: {spec['type']}")
        if spec["note"]:
            print(f"     Note: {spec['note']}")
        if spec["source"]:
            print(f"     Source: {spec['source']}")
        if spec["light_path"]:
            exists = "exists" if os.path.isfile(spec["light_path"]) else "MISSING"
            print(f"     Light: {os.path.relpath(spec['light_path'])} ({exists})")
        if spec["dark_path"]:
            exists = "exists" if os.path.isfile(spec["dark_path"]) else "MISSING"
            print(f"     Dark:  {os.path.relpath(spec['dark_path'])} ({exists})")
        print()


# ---------------------------------------------------------------------------
# Dry run / reporting
# ---------------------------------------------------------------------------

def print_dry_run(specs, media_specs=None):
    """Print a summary of what would be captured without actually doing it."""
    print(f"\nFound {len(specs)} screenshot spec(s):\n")
    for i, spec in enumerate(specs, 1):
        print(f"  {i}. {spec['source_file']}:{spec['source_line']}")
        print(f"     URL:       {spec['url']}")
        region = REGIONS.get(spec["region"], {})
        target_w = region.get("target_width", "?")
        crop_sel = spec["selector"] or region.get("selector") or "(full viewport)"
        print(f"     Region:    {spec['region']} → {target_w}px crop via {crop_sel}")
        if spec["height"]:
            print(f"     Height:    {spec['height']}px viewport (mode 1)")
        if spec["crop_top"]:
            print(f"     Crop top:  {spec['crop_top']}")
        if spec["crop_bottom"]:
            print(f"     Crop bot:  {spec['crop_bottom']}")
        if spec["script"]:
            print(f"     Script:    {spec['script']}")
        if spec["highlight"]:
            print(f"     Highlight: {', '.join(spec['highlight'])}")
        if spec["light_path"]:
            print(f"     Light:     {os.path.relpath(spec['light_path'])}")
        else:
            print(f"     Light:     (no paired image reference found)")
        if spec["dark_path"]:
            print(f"     Dark:      {os.path.relpath(spec['dark_path'])}")
        else:
            print(f"     Dark:      (no paired image reference found)")
        print()

    if media_specs:
        print_media_summary(media_specs)


# ---------------------------------------------------------------------------
# Migration: old URL comments → new (screenshot:) syntax
# ---------------------------------------------------------------------------

def _infer_region(url_path):
    """Infer a region from a URL path pattern.

    Returns a region name string.
    """
    # Form pages
    if "/add/" in url_path or "/edit/" in url_path or "/bulk-add/" in url_path:
        return "center-panel"
    if "add-new-contact" in url_path or "assign-contact-team" in url_path:
        return "center-panel"
    # GraphQL / API docs / special pages
    if url_path.startswith("/graphql") or url_path.startswith("/api/docs"):
        return "full"
    if url_path.startswith("/admin/"):
        return "full"
    if url_path.startswith("/silk/"):
        return "full"
    # Detail view (UUID in path, no trailing action)
    uuid_re = re.compile(r'/[0-9a-f]{8}-[0-9a-f]{4}-')
    if uuid_re.search(url_path) and not url_path.rstrip("/").endswith(("/add", "/edit")):
        return "full"
    # List view (no UUID, no /add/ or /edit/)
    return "full"


def migrate_old_comments(paths, dry_run=True, base_url_prefix="https://next.demo.nautobot.com"):
    """Convert old-style URL comments to new (screenshot:) syntax.

    Transforms:
        [//]: # "`https://next.demo.nautobot.com/dcim/locations/`"
    To:
        [//]: # (screenshot: url=/dcim/locations/ region=full)

    Args:
        paths: List of file or directory paths to scan.
        dry_run: If True, print what would change without modifying files.
        base_url_prefix: The base URL to strip from old comments.

    Returns:
        Number of comments migrated.
    """
    old_re = re.compile(r'^(\s*)\[//\]: # "`(https?://[^`]+)`"\s*$')
    # Also handle demo.nautobot.com (without "next." prefix)
    base_prefixes = [
        base_url_prefix,
        base_url_prefix.replace("next.", ""),
    ]

    migrated = 0
    files_to_scan = []

    for path in paths:
        path = os.path.abspath(path)
        if os.path.isfile(path) and path.endswith(".md"):
            files_to_scan.append(path)
        elif os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for filename in sorted(files):
                    if filename.endswith(".md"):
                        files_to_scan.append(os.path.join(root, filename))

    for filepath in files_to_scan:
        with open(filepath, "r") as f:
            lines = f.readlines()

        changed = False
        new_lines = []

        for line in lines:
            match = old_re.match(line)
            if match:
                indent = match.group(1)
                full_url = match.group(2)

                # Strip the base URL to get the path
                url_path = full_url
                for prefix in base_prefixes:
                    if full_url.startswith(prefix):
                        url_path = full_url[len(prefix):]
                        break

                region = _infer_region(url_path)
                new_comment = f"{indent}[//]: # (screenshot: url={url_path} region={region})\n"

                if dry_run:
                    relpath = os.path.relpath(filepath)
                    print(f"  {relpath}:")
                    print(f"    - {line.rstrip()}")
                    print(f"    + {new_comment.rstrip()}")
                    print()

                new_lines.append(new_comment)
                changed = True
                migrated += 1
            else:
                new_lines.append(line)

        if changed and not dry_run:
            with open(filepath, "w") as f:
                f.writelines(new_lines)
            print(f"  Migrated {os.path.relpath(filepath)}")

    return migrated


# ---------------------------------------------------------------------------
# Report: compare current vs last-committed image dimensions
# ---------------------------------------------------------------------------

def _get_committed_image_size(filepath):
    """Get the dimensions of an image from the last git commit.

    Returns:
        (width, height) tuple, or None if the file isn't tracked or has no prior commit.
    """
    import io
    import subprocess

    relpath = os.path.relpath(filepath)
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{relpath}"],
            capture_output=True,
            check=True,
        )
        img = Image.open(io.BytesIO(result.stdout))
        return img.width, img.height
    except (subprocess.CalledProcessError, Exception):
        return None


def print_report(specs, threshold=10):
    """Compare current vs last-committed image dimensions.

    Shows images sorted by largest dimensional change. Only includes images
    that differ by more than `threshold` percent in width or height.

    Args:
        specs: List of screenshot spec dicts.
        threshold: Minimum percent change to include in the report (default 10).
    """
    entries = []

    for spec in specs:
        for label, path in [("light", spec["light_path"]), ("dark", spec["dark_path"])]:
            if not path or not os.path.isfile(path):
                continue

            current = Image.open(path)
            committed = _get_committed_image_size(path)

            if committed is None:
                # New file, no prior commit to compare
                entries.append({
                    "path": path,
                    "spec": spec,
                    "label": label,
                    "current": (current.width, current.height),
                    "committed": None,
                    "pct_change": 100,  # treat new files as 100% change
                })
                continue

            old_w, old_h = committed
            new_w, new_h = current.width, current.height

            # Percent change: max of width or height change
            w_pct = abs(new_w - old_w) / max(old_w, 1) * 100
            h_pct = abs(new_h - old_h) / max(old_h, 1) * 100
            pct = max(w_pct, h_pct)

            entries.append({
                "path": path,
                "spec": spec,
                "label": label,
                "current": (new_w, new_h),
                "committed": (old_w, old_h),
                "pct_change": pct,
            })

    # Filter by threshold and sort by largest change
    entries = [e for e in entries if e["pct_change"] >= threshold]
    entries.sort(key=lambda e: e["pct_change"], reverse=True)

    if not entries:
        print(f"\nNo images differ by more than {threshold}% from last commit.")
        return

    print(f"\n{len(entries)} image(s) differ by >{threshold}% from last commit (sorted by change):\n")

    for e in entries:
        relpath = os.path.relpath(e["path"])
        spec = e["spec"]
        new_w, new_h = e["current"]
        pct = e["pct_change"]

        if e["committed"] is None:
            print(f"  {relpath}  ({e['label']})")
            print(f"    NEW FILE  {new_w}x{new_h}")
        else:
            old_w, old_h = e["committed"]
            w_delta = new_w - old_w
            h_delta = new_h - old_h
            w_sign = "+" if w_delta >= 0 else ""
            h_sign = "+" if h_delta >= 0 else ""
            print(f"  {relpath}  ({e['label']}, {pct:.0f}% change)")
            print(f"    {old_w}x{old_h} → {new_w}x{new_h}  (w:{w_sign}{w_delta}, h:{h_sign}{h_delta})")

        print(f"    spec: {os.path.relpath(spec['source_file'])}:{spec['source_line']}")
        print()


def print_review_list(specs):
    """Print a numbered checklist of changed images in git-status order.

    Groups dark/light pairs together. Ordered by how they appear in
    `git diff --name-only` so the list matches the diff viewer.
    """
    import subprocess

    # Get changed files from git in diff order
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        diff_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except subprocess.CalledProcessError:
        diff_files = []

    # Also get untracked (new) files
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, check=True,
        )
        diff_files.extend(line.strip() for line in result.stdout.splitlines() if line.strip())
    except subprocess.CalledProcessError:
        pass

    # Build a lookup from all spec image paths
    image_info = {}
    for spec in specs:
        for label, path in [("light", spec["light_path"]), ("dark", spec["dark_path"])]:
            if not path:
                continue
            relpath = os.path.relpath(path)
            if not os.path.isfile(path):
                continue

            current = Image.open(path)
            committed = _get_committed_image_size(path)
            image_info[relpath] = {
                "label": label,
                "current": (current.width, current.height),
                "committed": committed,
                "spec": spec,
            }

    # Only include files that are in git diff (changed/new) -- unchanged files aren't relevant
    diff_set = set(diff_files)
    ordered = [f for f in diff_files if f in image_info]

    # Group dark/light pairs: keep them adjacent with dark first
    seen = set()
    grouped = []
    for f in ordered:
        if f in seen:
            continue
        seen.add(f)
        grouped.append(f)
        # Pull in the paired variant if it's also changed
        if "_dark." in f:
            pair = f.replace("_dark.", "_light.")
        elif "_light." in f:
            pair = f.replace("_light.", "_dark.")
        else:
            continue
        if pair in diff_set and pair in image_info and pair not in seen:
            seen.add(pair)
            grouped.append(pair)

    if not grouped:
        print("\nNo changed screenshot images in git diff.")
        return

    print(f"\nReview checklist ({len(grouped)} changed images):\n")

    for idx, relpath in enumerate(grouped, 1):
        info = image_info.get(relpath)
        if not info:
            continue

        filename = os.path.basename(relpath)
        new_w, new_h = info["current"]
        committed = info["committed"]
        is_light = info["label"] == "light"

        if committed is None:
            pct_str = "NEW"
            note = "new file"
        else:
            old_w, old_h = committed
            w_pct = abs(new_w - old_w) / max(old_w, 1) * 100
            h_pct = abs(new_h - old_h) / max(old_h, 1) * 100
            pct = max(w_pct, h_pct)
            if pct < 1:
                pct_str = "0%"
                note = "no change"
            else:
                pct_str = f"{pct:.0f}%"
                h_delta = new_h - old_h
                note = f"h:{'+' if h_delta >= 0 else ''}{h_delta}"

        # Light variants shown as secondary to their dark pair
        if is_light and idx > 1:
            prev = grouped[idx - 2] if idx >= 2 else ""
            if prev.replace("_dark.", "_light.") == relpath:
                print(f"  {idx:>3}. {filename} | {pct_str} | {note}  (light of above)")
                continue

        print(f"  {idx:>3}. {filename} | {pct_str} | {note}")
    print()
