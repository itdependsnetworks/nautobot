"""Named region definitions for automated screenshot capture.

Every screenshot is taken at the same viewport (1920x960), matching the
docs-media-standards.md "Full Screen" width.  Regions define:
  - A CSS selector whose bounding box is used to *crop* the 1920px capture.
  - A target output width the cropped image should match.

Standard output widths (from docs-media-standards.md):
    - 1920 px  Full Screen or List View
    - 1024 px  Center Panel (e.g., Edit or Job Form)
    -  760 px  Side Panels (Right or Left)
    -  360 px  Navbar
"""

REGIONS = {
    # Full page -- no cropping, output is 1920px wide
    "full": {
        "selector": None,
        "target_width": 1920,
    },
    # List views (e.g., /dcim/locations/) -- same as full
    "list-view": {
        "selector": None,
        "target_width": 1920,
    },
    # Object detail views -- crop to main content area
    "center-panel": {
        "selector": "#main-content",
        "target_width": 1024,
    },
    # Create/edit forms
    "form": {
        "selector": "#main-content",
        "target_width": 1024,
    },
    # Right-side drawer (filters, saved views, table config)
    "side-panel-right": {
        "selector": "#drawer .nb-drawer.nb-drawer-open",
        "target_width": 760,
    },
    # Left sidenav
    "side-panel-left": {
        "selector": "#sidenav",
        "target_width": 760,
    },
    # Navbar (collapsed sidenav)
    "navbar": {
        "selector": "#sidenav",
        "target_width": 360,
    },
    # Header bar (breadcrumbs, search, tabs)
    "header": {
        "selector": "#header",
        "target_width": 1920,
    },
}

# Viewport matches the docs-media-standards.md custom device:
# 1280x960 CSS pixels at DPR 1.5 → 1920x1440 device pixel screenshots.
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 960
