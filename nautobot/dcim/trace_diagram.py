"""Server-side SVG generation for cable path trace diagrams."""

from django.contrib.contenttypes.models import ContentType
import svgwrite


class CableTraceSVG:
    """
    Generate an SVG diagram of a cable trace path.

    Renders a top-to-bottom flow showing devices, terminations, cables,
    pass-throughs, and breakout fan-outs as connected SVG elements.

    The rendering is split into two phases:
      Phase 1 (build_matrix): Collect trace data into a row/column matrix with
          spatial metadata (colspan for grouped devices, continuation markers
          for empty cells above active content, etc.)
      Phase 2 (render_matrix): Walk the matrix and draw each cell at its
          computed pixel position.

    Usage:
        diagram = CableTraceSVG(origin_instance, base_url="")
        svg_string = diagram.render()
    """

    # Layout: overall dimensions
    MAX_WIDTH = 400
    COL_WIDTH = 140
    INITIAL_HEIGHT = 800
    INITIAL_FANOUT_HEIGHT = 2000
    EMPTY_HEIGHT = 60

    # Layout: node (device/circuit/panel box)
    NODE_W = 180
    NODE_H = 50
    NODE_BORDER_RADIUS = 6

    # Layout: termination sub-box
    TERM_W = 120
    TERM_H = 26
    TERM_BORDER_RADIUS = 4

    # Layout: cable segment
    CABLE_H = 120
    CABLE_BAR_W = 4

    # Layout: pass-through
    PASSTHROUGH_H = 24

    # Layout: spacing and offsets
    GAP_Y = 4
    LABEL_OFFSET_X = 8  # Horizontal offset for labels beside cable bars / pass-throughs
    FORK_DROP_LENGTH = 12  # GAP_Y * 3 — vertical drop from fork bar to first row
    TEXT_LINE_SPACING = 10  # Vertical spacing between text lines in nodes
    TEXT_VERTICAL_OFFSET = 4  # Vertical centering offset for text within boxes
    TRACE_END_PADDING = 6  # Padding above trace-end label
    TRACE_END_HEIGHT = 20  # Height of trace-end section

    # Typography
    FONT_FAMILY = "system-ui, -apple-system, sans-serif"
    FONT_SIZE = 12
    FONT_SIZE_SM = 10

    # Line widths
    FORK_LINE_WIDTH = 2

    # Colors
    COLOR_NODE_BG = "#f8f9fa"
    COLOR_NODE_BORDER = "#dee2e6"
    COLOR_TERM_BG = "#e9ecef"
    COLOR_TERM_BORDER = "#adb5bd"
    COLOR_ACTIVE_BORDER = "#198754"
    COLOR_TEXT = "#212529"
    COLOR_TEXT_MUTED = "#6c757d"
    COLOR_LINK = "#0d6efd"
    COLOR_CABLE_DEFAULT = "#606060"
    COLOR_SUCCESS = "#198754"
    COLOR_DANGER = "#dc3545"
    COLOR_WARNING = "#ffc107"

    def __init__(self, origin, base_url=""):
        self.origin = origin
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.traced_path = origin.trace() if hasattr(origin, "trace") else []
        self.fanout_paths = self._detect_fanout()

    # ──────────────────────────────────────────────
    # Data collection helpers
    # ──────────────────────────────────────────────

    def _detect_fanout(self):
        """Detect if this trace fans out through a breakout cable.

        Uses CablePath records — each lane has its own CablePath with connector/position fields.
        Falls back to template mapping for unconnected lanes (no CablePath).
        """
        if not self.traced_path:
            return []

        _, cable, far_end = self.traced_path[0]
        if not cable or not cable.breakout_template_id:
            return []

        from nautobot.dcim.models import CablePath, CableTerminationEndpoint

        # Get all CablePaths from this origin (one per breakout lane)
        content_type = ContentType.objects.get_for_model(self.origin)
        all_paths = CablePath.objects.filter(
            origin_type=content_type, origin_id=self.origin.pk
        ).order_by("connector", "position")

        if all_paths.count() <= 1 and not cable.breakout_template_id:
            return []

        # Find the origin's endpoint to determine which side we're on
        origin_endpoint = CableTerminationEndpoint.objects.filter(
            cable=cable, termination_id=self.origin.pk
        ).first()
        if not origin_endpoint:
            return []

        opposite_side = "B" if origin_endpoint.cable_end == "A" else "A"
        origin_side_key = "a_connector" if origin_endpoint.cable_end == "A" else "b_connector"
        far_side_key = "b_connector" if origin_endpoint.cable_end == "A" else "a_connector"
        far_position_key = "b_position" if origin_endpoint.cable_end == "A" else "a_position"

        # Build a lookup of CablePaths by (connector, position)
        path_lookup = {}
        for cable_path in all_paths:
            if cable_path.connector is not None:
                path_lookup[(cable_path.connector, cable_path.position or 1)] = cable_path

        # Build fan-out legs from the template mapping (includes unconnected lanes)
        mapped_lanes = sorted(
            [e for e in cable.breakout_template.mapping if e[origin_side_key] == origin_endpoint.connector],
            key=lambda e: (e[far_side_key], e.get(far_position_key, 1)),
        )

        if len(mapped_lanes) <= 1:
            return []

        # Build a lookup of far-side endpoints for termination names
        far_endpoint_lookup = {}
        for endpoint in CableTerminationEndpoint.objects.filter(cable=cable, cable_end=opposite_side):
            far_endpoint_lookup[(endpoint.connector, endpoint.position or 1)] = endpoint

        fanout_legs = []
        for lane in mapped_lanes:
            far_connector = lane[far_side_key]
            far_position = lane.get(far_position_key, 1)
            far_ep = far_endpoint_lookup.get((far_connector, far_position))
            termination = far_ep.termination if far_ep else None

            # Get trace from the CablePath for this lane
            leg_trace = []
            cable_path = path_lookup.get((far_connector, far_position))
            if cable_path:
                # Reconstruct the trace from the CablePath, stripping the first hop (breakout cable)
                full_path_objects = [self.origin, *cable_path.get_path()]
                while (len(full_path_objects) + 1) % 3:
                    full_path_objects.append(None)
                full_path_objects.append(cable_path.destination)
                full_trace = list(zip(*[iter(full_path_objects)] * 3))
                if len(full_trace) > 1:
                    leg_trace = self._expand_trace_segments(full_trace[1:])

            fanout_legs.append({
                "termination": termination,
                "connector_label": f"{opposite_side}{far_connector}",
                "trace": leg_trace,
            })

        return fanout_legs

    def _url(self, obj):
        """Get the absolute URL for an object."""
        try:
            return self.base_url + obj.get_absolute_url()
        except (AttributeError, TypeError):
            return "#"

    def _get_parent_info(self, termination):
        """Extract parent info for a termination: grouping key, display name, detail, and URL.

        Returns (key, name, detail, url). Key is used for grouping same-device nodes.
        Uses the termination's .parent property which handles device, module, circuit, and power_panel.
        """
        if termination is None:
            return None, None, None, None

        parent = getattr(termination, "parent", None)
        if parent is None:
            return (None, str(termination), "", "#")

        parent_key = str(parent.pk)
        parent_name = str(parent)
        parent_url = self._url(parent)

        # Build detail string and key prefix based on parent type
        if hasattr(parent, "device_type"):
            # Device — show manufacturer / device type
            detail = f"{parent.device_type.manufacturer} / {parent.device_type}"
        elif hasattr(parent, "provider"):
            # Circuit — prefix key to avoid PK collisions with devices
            parent_key = f"c:{parent.pk}"
            parent_name = f"{parent.provider} / {parent.cid}"
            detail = "Circuit"
        else:
            # PowerPanel or other — use verbose name as detail
            parent_key = f"{parent._meta.model_name}:{parent.pk}"
            detail = parent._meta.verbose_name.title()

        return (parent_key, parent_name, detail, parent_url)

    # ──────────────────────────────────────────────
    # Phase 1: Build the matrix
    # ──────────────────────────────────────────────

    def build_matrix(self):
        """Build a row/column matrix from fan-out legs with spatial metadata.

        Returns:
            {
                "header": {
                    "origin": termination,
                    "cable": cable_obj,
                    "cable_color": str,
                    "connector_labels": [str, ...],
                },
                "columns": int,
                "col_centers": [float, ...],    # X center for each column
                "total_width": float,
                "rows": [
                    [cell, cell, ...],  # one cell per column
                    ...
                ],
            }

        Cell types:
            {"type": "node", "col": int, "colspan": 1, "termination": obj}
            {"type": "grouped_node", "col": int, "colspan": int,
             "terminations": [obj, ...], "parent_key": str}
            {"type": "spanned"}  — covered by a grouped_node in a prior column
            {"type": "cable", "col": int, "cable": obj, "near": obj, "far": obj}
            {"type": "passthrough", "col": int, "near": obj, "far": obj}
            {"type": "empty", "col": int, "continuation": bool}
        """
        column_count = len(self.fanout_paths)

        # Column X centers
        col_width = self.COL_WIDTH
        total_width = max(column_count * col_width, self.MAX_WIDTH)
        x_offset = max((total_width - column_count * col_width) / 2, 0)
        col_centers = [x_offset + (col_idx + 0.5) * col_width for col_idx in range(column_count)]

        # Header
        near_end, cable, _ = self.traced_path[0] if self.traced_path else (None, None, None)
        cable_color = f"#{cable.color}" if cable and cable.color else self.COLOR_CABLE_DEFAULT

        header = {
            "origin": near_end,
            "cable": cable,
            "cable_color": cable_color,
            "connector_labels": [leg["connector_label"] for leg in self.fanout_paths],
        }

        # Step 1: Build raw per-column entry lists, merging node+passthrough into passthrough_node
        column_entries = []
        for leg in self.fanout_paths:
            raw_entries = []
            leg_termination = leg["termination"]
            trace_segments = leg.get("trace", [])

            # First entry: the leg's far-end termination
            raw_entries.append({"type": "node", "termination": leg_termination})

            # Check for implicit pass-through between leg termination and first trace near_end
            # (e.g., FrontPort → RearPort within the same device)
            if trace_segments and leg_termination:
                first_near = trace_segments[0][0]
                if first_near and first_near.pk != leg_termination.pk:
                    raw_entries.append({"type": "passthrough", "near": leg_termination, "far": first_near})

            for segment_near, segment_cable, segment_far in trace_segments:
                if segment_cable is None and segment_far is not None:
                    raw_entries.append({"type": "passthrough", "near": segment_near, "far": segment_far})
                else:
                    if segment_cable:
                        raw_entries.append(
                            {"type": "cable", "cable": segment_cable, "near": segment_near, "far": segment_far}
                        )
                    if segment_far:
                        raw_entries.append({"type": "node", "termination": segment_far})

            # Merge: when a node is immediately followed by a passthrough, combine into passthrough_node
            entries = []
            entry_index = 0
            while entry_index < len(raw_entries):
                entry = raw_entries[entry_index]
                if (
                    entry["type"] == "node"
                    and entry_index + 1 < len(raw_entries)
                    and raw_entries[entry_index + 1]["type"] == "passthrough"
                ):
                    passthrough = raw_entries[entry_index + 1]
                    entries.append(
                        {
                            "type": "passthrough_node",
                            "arriving": entry["termination"],
                            "departing": passthrough["far"],
                        }
                    )
                    entry_index += 2  # Skip both the node and the passthrough
                else:
                    entries.append(entry)
                    entry_index += 1

            column_entries.append(entries)

        # Step 2: Normalize into rows (pad with empty)
        max_depth = max((len(entries) for entries in column_entries), default=0)
        raw_rows = []
        for depth in range(max_depth):
            row = []
            for col_idx in range(column_count):
                if depth < len(column_entries[col_idx]):
                    cell = dict(column_entries[col_idx][depth])  # shallow copy
                    cell["col"] = col_idx
                else:
                    cell = {"type": "empty", "col": col_idx}
                row.append(cell)
            raw_rows.append(row)

        # Step 3: Mark continuation on empty cells (if any cell below in same col has content)
        for col_idx in range(column_count):
            last_content_row_idx = -1
            for row_idx in range(len(raw_rows) - 1, -1, -1):
                if raw_rows[row_idx][col_idx]["type"] != "empty":
                    last_content_row_idx = row_idx
                    break
            for row_idx in range(last_content_row_idx):
                cell = raw_rows[row_idx][col_idx]
                if cell["type"] == "empty":
                    cell["continuation"] = True
                else:
                    cell.setdefault("continuation", False)
            for row_idx in range(last_content_row_idx, len(raw_rows)):
                cell = raw_rows[row_idx][col_idx]
                cell.setdefault("continuation", False)

        # Step 4: Group consecutive same-parent node cells into colspan
        rows = []
        for raw_row in raw_rows:
            row = list(raw_row)  # copy

            col_idx = 0
            while col_idx < column_count:
                cell = row[col_idx]
                if cell["type"] == "node" and cell.get("termination") is not None:
                    parent_key = self._get_parent_info(cell["termination"])[0]
                    span_end = col_idx + 1
                    while span_end < column_count:
                        next_cell = row[span_end]
                        if next_cell["type"] == "node" and next_cell.get("termination") is not None:
                            if (
                                self._get_parent_info(next_cell["termination"])[0] == parent_key
                                and parent_key is not None
                            ):
                                span_end += 1
                                continue
                        break

                    colspan = span_end - col_idx
                    if colspan > 1:
                        terminations = [row[spanned_col]["termination"] for spanned_col in range(col_idx, span_end)]
                        row[col_idx] = {
                            "type": "grouped_node",
                            "col": col_idx,
                            "colspan": colspan,
                            "terminations": terminations,
                            "parent_key": parent_key,
                            "continuation": False,
                        }
                        for spanned_col in range(col_idx + 1, span_end):
                            row[spanned_col] = {"type": "spanned", "col": spanned_col, "continuation": False}
                        col_idx = span_end
                    else:
                        cell["colspan"] = 1
                        col_idx += 1
                else:
                    col_idx += 1

            rows.append(row)

        return {
            "header": header,
            "columns": column_count,
            "col_centers": col_centers,
            "total_width": total_width,
            "rows": rows,
        }

    # ──────────────────────────────────────────────
    # Phase 2: Render the matrix to SVG
    # ──────────────────────────────────────────────

    def render(self):
        """Render the complete trace as an SVG string."""
        if not self.traced_path:
            return self._render_empty()

        # Normalize: a linear trace is a single-leg fanout without the fork.
        # This ensures all paths go through the same build_matrix → render pipeline.
        if not self.fanout_paths:
            _, _, far_end = self.traced_path[0]
            self.fanout_paths = [
                {
                    "termination": far_end,
                    "connector_label": "",
                    "trace": self._expand_trace_segments(self.traced_path[1:]),
                }
            ]

        return self._render_fanout()

    def _expand_trace_segments(self, segments):
        """Expand trace() three-tuples into entries with explicit pass-through hops.

        When trace() returns consecutive segments where the far-end of segment N
        differs from the near-end of segment N+1, that's an implicit pass-through
        (e.g., FrontPort → RearPort within the same device). This method inserts
        explicit (from, None, to) passthrough entries for those gaps.

        Used by both linear traces and fan-out leg traces.
        """
        entries = []
        for segment_index, (near_end, cable, far_end) in enumerate(segments):
            # Detect implicit pass-through from previous segment's far_end
            if segment_index > 0:
                prev_far = segments[segment_index - 1][2]
                if prev_far and near_end and near_end.pk != prev_far.pk:
                    entries.append((prev_far, None, near_end))

            if cable:
                entries.append((near_end, cable, far_end))

        return entries

    def _render_fanout(self):
        """Render a breakout fan-out trace from the matrix."""
        matrix = self.build_matrix()
        header = matrix["header"]
        col_centers = matrix["col_centers"]
        total_width = matrix["total_width"]

        dwg = svgwrite.Drawing(size=(f"{total_width}px", f"{self.INITIAL_FANOUT_HEIGHT}px"), debug=False)
        dwg.viewbox(0, 0, total_width, self.INITIAL_FANOUT_HEIGHT)

        trunk_cx = (col_centers[0] + col_centers[-1]) / 2 if col_centers else total_width / 2
        y = self.GAP_Y

        # ── Header: Origin node ──
        if header["origin"]:
            y = self._draw_node(dwg, trunk_cx, y, header["origin"], term_position="bottom")
            y += self.GAP_Y

        # ── Header: Breakout cable trunk + fork ──
        cable = header["cable"]
        if not cable:
            y = self._draw_trace_end(dwg, trunk_cx, y, incomplete=True)
            dwg["height"] = f"{y + self.GAP_Y}px"
            dwg.viewbox(0, 0, total_width, y + self.GAP_Y)
            return dwg.tostring()

        cable_color = header["cable_color"]
        is_breakout_fanout = cable.breakout_template_id and len(col_centers) > 1

        if is_breakout_fanout:
            # Breakout cable: half-height bar, then fork lines to each column
            y = self._draw_cable(dwg, trunk_cx, y, cable)
            y += self.GAP_Y

            fork_y = y
            # Horizontal bar across all columns
            dwg.add(
                dwg.line(
                    start=(col_centers[0], fork_y),
                    end=(col_centers[-1], fork_y),
                    stroke=cable_color,
                    stroke_width=self.FORK_LINE_WIDTH,
                )
            )
            # Vertical drop + connector label per column
            drop_end = fork_y + self.FORK_DROP_LENGTH
            for col_idx, cx in enumerate(col_centers):
                dwg.add(
                    dwg.line(
                        start=(cx, fork_y),
                        end=(cx, drop_end),
                        stroke=cable_color,
                        stroke_width=self.FORK_LINE_WIDTH,
                    )
                )
                label = header["connector_labels"][col_idx]
                if label:
                    dwg.add(
                        dwg.text(
                            label,
                            insert=(cx, fork_y - self.TEXT_VERTICAL_OFFSET),
                            text_anchor="middle",
                            fill=self.COLOR_TEXT_MUTED,
                            font_size=f"{self.FONT_SIZE_SM}px",
                            font_family=self.FONT_FAMILY,
                            font_weight="bold",
                        )
                    )
            y = drop_end + self.GAP_Y
        else:
            # Linear or single-leg: full-height cable bar, no fork
            y = self._draw_cable(dwg, trunk_cx, y, cable)
            y += self.GAP_Y

        # ── Render matrix rows (two full passes for z-order) ──
        # First compute all row positions
        row_positions = []  # list of (y, row, row_h)
        for row in matrix["rows"]:
            row_h = self._compute_row_height(row)
            row_positions.append((y, row, row_h))
            y += row_h + self.GAP_Y

        # Pass 1: Background — cables, lines, continuations (drawn first, behind nodes)
        for row_y, row, row_h in row_positions:
            self._render_row_background(dwg, row_y, row, row_h, col_centers)

        # Pass 2: Foreground — device boxes, termination boxes (painted over lines)
        for row_y, row, row_h in row_positions:
            self._render_row_foreground(dwg, row_y, row, col_centers)

        # Resize to actual content
        dwg["height"] = f"{y + self.GAP_Y}px"
        dwg["width"] = f"{total_width}px"
        dwg.viewbox(0, 0, total_width, y + self.GAP_Y)
        return dwg.tostring()

    def _compute_row_height(self, row):
        """Compute the height of a row without drawing anything."""
        row_h = 0
        for cell in row:
            if cell["type"] == "node":
                row_h = max(row_h, self.TERM_H / 2 + self.NODE_H)
            elif cell["type"] == "grouped_node":
                row_h = max(row_h, self.TERM_H / 2 + self.NODE_H)
            elif cell["type"] == "passthrough_node":
                # Two termination overlaps + text area between them
                text_area_h = self.TEXT_LINE_SPACING * 3
                row_h = max(row_h, self.TERM_H + text_area_h)
            elif cell["type"] == "cable":
                row_h = max(row_h, self.CABLE_H)
            elif cell["type"] == "passthrough":
                row_h = max(row_h, self.PASSTHROUGH_H)
        return row_h

    def _render_row_background(self, dwg, y, row, row_h, col_centers):
        """Draw background elements for a row: cables, pass-through lines, continuation lines."""
        if row_h == 0:
            return
        for cell in row:
            cx = col_centers[cell["col"]]

            if cell["type"] == "cable":
                self._draw_cable(dwg, cx, y, cell["cable"], cell.get("near"), cell.get("far"))

            elif cell["type"] == "passthrough":
                dwg.add(
                    dwg.line(
                        start=(cx, y),
                        end=(cx, y + row_h),
                        stroke=self.COLOR_NODE_BORDER,
                        stroke_width=1,
                        stroke_dasharray="4,3",
                    )
                )
                dwg.add(
                    dwg.text(
                        "pass-thru",
                        insert=(cx + self.LABEL_OFFSET_X, y + row_h / 2 + self.TEXT_VERTICAL_OFFSET),
                        fill=self.COLOR_TEXT_MUTED,
                        font_size=f"{self.FONT_SIZE_SM}px",
                        font_family=self.FONT_FAMILY,
                    )
                )

            elif cell["type"] == "empty" and cell.get("continuation"):
                dwg.add(
                    dwg.line(
                        start=(cx, y),
                        end=(cx, y + row_h),
                        stroke=self.COLOR_NODE_BORDER,
                        stroke_width=1,
                        stroke_dasharray="2,4",
                        opacity=0.3,
                    )
                )

    def _render_row_foreground(self, dwg, y, row, col_centers):
        """Draw foreground elements for a row: device boxes, termination boxes."""
        for cell in row:
            cx = col_centers[cell["col"]]

            if cell["type"] == "node":
                if cell["termination"] is None:
                    # Unconnected lane — draw a dashed circle with label
                    dwg.add(dwg.text(
                        "Unconnected",
                        insert=(cx, y + self.NODE_H / 2),
                        text_anchor="middle", fill=self.COLOR_WARNING,
                        font_size=f"{self.FONT_SIZE_SM}px", font_family=self.FONT_FAMILY,
                        font_weight="bold",
                    ))
                else:
                    self._draw_node(dwg, cx, y, cell["termination"], term_position="top")

            elif cell["type"] == "grouped_node":
                self._draw_grouped_node_cell(dwg, y, cell, col_centers)

            elif cell["type"] == "passthrough_node":
                self._draw_passthrough_node(dwg, cx, y, cell["arriving"], cell["departing"])

    # ──────────────────────────────────────────────
    # Cell drawing primitives
    # ──────────────────────────────────────────────

    def _draw_device_box(self, dwg, box_x, box_y, box_w, box_h, text_cx, text_area_top, text_area_h, termination):
        """Draw a device/circuit/panel box with centered name and detail text.

        This is the shared primitive for all node types. Callers handle termination
        box placement; this method draws only the device background and text.
        """
        _parent_key, parent_name, parent_detail, parent_url = self._get_parent_info(termination)

        dwg.add(
            dwg.rect(
                insert=(box_x, box_y),
                size=(box_w, box_h),
                rx=self.NODE_BORDER_RADIUS,
                ry=self.NODE_BORDER_RADIUS,
                fill=self.COLOR_NODE_BG,
                stroke=self.COLOR_NODE_BORDER,
                stroke_width=1,
            )
        )

        text_center_y = text_area_top + text_area_h / 2
        if parent_name:
            link = dwg.a(href=parent_url, target="_top")
            link.add(
                dwg.text(
                    parent_name,
                    insert=(text_cx, text_center_y - self.TEXT_LINE_SPACING / 2 + self.TEXT_VERTICAL_OFFSET),
                    text_anchor="middle",
                    fill=self.COLOR_LINK,
                    font_size=f"{self.FONT_SIZE}px",
                    font_family=self.FONT_FAMILY,
                    font_weight="bold",
                )
            )
            dwg.add(link)
        if parent_detail:
            dwg.add(
                dwg.text(
                    parent_detail,
                    insert=(text_cx, text_center_y + self.TEXT_LINE_SPACING / 2 + self.TEXT_VERTICAL_OFFSET),
                    text_anchor="middle",
                    fill=self.COLOR_TEXT_MUTED,
                    font_size=f"{self.FONT_SIZE_SM}px",
                    font_family=self.FONT_FAMILY,
                )
            )

    def _draw_node(self, dwg, cx, y, termination, term_position="top", is_last=False):
        """Draw a device node with one termination box (top or bottom)."""
        half_term_h = self.TERM_H / 2

        if term_position == "top":
            term_y = y
            box_y = y + half_term_h
            text_area_top = box_y + half_term_h
            text_area_h = self.NODE_H - self.TERM_H
            total_bottom = box_y + self.NODE_H
        else:
            box_y = y
            term_y = y + self.NODE_H - half_term_h
            text_area_top = box_y
            text_area_h = self.NODE_H - self.TERM_H
            total_bottom = term_y + self.TERM_H

        self._draw_device_box(
            dwg,
            cx - self.NODE_W / 2,
            box_y,
            self.NODE_W,
            self.NODE_H,
            cx,
            text_area_top,
            text_area_h,
            termination,
        )
        self._draw_termination_box(dwg, cx, term_y, termination)

        return total_bottom

    def _draw_grouped_node_cell(self, dwg, y, cell, col_centers):
        """Draw a device box spanning multiple columns with side-by-side termination boxes at top."""
        terminations = cell["terminations"]
        start_col = cell["col"]
        colspan = cell["colspan"]
        half_term_h = self.TERM_H / 2

        first_cx = col_centers[start_col]
        last_cx = col_centers[start_col + colspan - 1]
        group_cx = (first_cx + last_cx) / 2

        box_w = (last_cx - first_cx) + self.TERM_W + self.GAP_Y * 2
        box_x = first_cx - self.TERM_W / 2 - self.GAP_Y
        box_y = y + half_term_h
        text_area_top = box_y + half_term_h
        text_area_h = self.NODE_H - self.TERM_H

        self._draw_device_box(
            dwg,
            box_x,
            box_y,
            box_w,
            self.NODE_H,
            group_cx,
            text_area_top,
            text_area_h,
            terminations[0],
        )
        for term_index, termination in enumerate(terminations):
            self._draw_termination_box(dwg, col_centers[start_col + term_index], y, termination)

        return box_y + self.NODE_H

    def _draw_cable(self, dwg, cx, y, cable, near_end=None, far_end=None):
        """Draw a cable segment with color bar, label, and status."""
        cable_color = f"#{cable.color}" if cable.color else self.COLOR_CABLE_DEFAULT
        cable_url = self._url(cable)
        is_connected = hasattr(cable, "status") and cable.status and cable.status.name == "Connected"

        bar_x = cx - self.CABLE_BAR_W / 2
        bar_h = self.CABLE_H

        if is_connected:
            dwg.add(dwg.rect(insert=(bar_x, y), size=(self.CABLE_BAR_W, bar_h), fill=cable_color))
        else:
            dwg.add(
                dwg.line(
                    start=(cx, y),
                    end=(cx, y + bar_h),
                    stroke=cable_color,
                    stroke_width=self.CABLE_BAR_W,
                    stroke_dasharray="8,4",
                )
            )

        label_x = cx + self.CABLE_BAR_W / 2 + self.LABEL_OFFSET_X
        label_y = y + bar_h / 2

        link = dwg.a(href=cable_url, target="_top")
        link.add(
            dwg.text(
                str(cable),
                insert=(label_x, label_y - self.TEXT_VERTICAL_OFFSET),
                fill=self.COLOR_LINK,
                font_size=f"{self.FONT_SIZE}px",
                font_family=self.FONT_FAMILY,
                font_weight="bold",
            )
        )
        dwg.add(link)

        # Breakout lane info (if applicable)
        next_line_y = label_y + self.LABEL_OFFSET_X
        if cable.breakout_template_id and near_end and far_end:
            from nautobot.core.templatetags.helpers import get_cable_lane_info

            near_endpoint = get_cable_lane_info(cable, near_end)
            far_endpoint = get_cable_lane_info(cable, far_end)
            if near_endpoint and near_endpoint.connector is not None:
                breakout_text = f"Breakout: {near_endpoint.cable_end}{near_endpoint.connector}"
                if far_endpoint and far_endpoint.connector is not None:
                    breakout_text += f" \u2192 {far_endpoint.cable_end}{far_endpoint.connector}"
                dwg.add(
                    dwg.text(
                        breakout_text,
                        insert=(label_x, next_line_y),
                        fill=self.COLOR_TEXT_MUTED,
                        font_size=f"{self.FONT_SIZE_SM}px",
                        font_family=self.FONT_FAMILY,
                    )
                )
                next_line_y += self.TEXT_LINE_SPACING + 2

        # Status badge (Bootstrap-style pill)
        status = cable.status if hasattr(cable, "status") else None
        status_name = status.name if status else "Unknown"
        status_color = f"#{status.color}" if status and status.color else self.COLOR_TEXT_MUTED
        self._draw_status_badge(dwg, label_x, next_line_y, status_name, status_color)

        return y + bar_h

    def _draw_passthrough_node(self, dwg, cx, y, arriving_termination, departing_termination):
        """Draw a device node with arriving port at top and departing port at bottom."""
        half_term_h = self.TERM_H / 2
        text_area_h = self.TEXT_LINE_SPACING * 3
        box_h = half_term_h + text_area_h + half_term_h

        box_y = y + half_term_h
        departing_y = box_y + box_h - half_term_h
        text_area_top = box_y + half_term_h

        self._draw_device_box(
            dwg,
            cx - self.NODE_W / 2,
            box_y,
            self.NODE_W,
            box_h,
            cx,
            text_area_top,
            text_area_h,
            arriving_termination,
        )
        self._draw_termination_box(dwg, cx, y, arriving_termination)
        self._draw_termination_box(dwg, cx, departing_y, departing_termination)

        return departing_y + self.TERM_H

    def _draw_status_badge(self, dwg, x, y, status_name, bg_color):
        """Draw a Bootstrap-style badge pill with colored background and white text."""
        from nautobot.core.templatetags.helpers import fgcolor

        # Estimate text width (approximate: ~6.5px per character at FONT_SIZE_SM)
        text_width = len(status_name) * 6.5
        badge_w = text_width + 12  # padding left + right
        badge_h = self.FONT_SIZE_SM + 6
        badge_r = 4  # slightly rounded corners

        # Badge background
        dwg.add(
            dwg.rect(
                insert=(x, y - badge_h / 2),
                size=(badge_w, badge_h),
                rx=badge_r,
                ry=badge_r,
                fill=bg_color,
            )
        )

        # Badge text (contrasting foreground)
        text_color = fgcolor(bg_color.lstrip("#")) if bg_color.startswith("#") else "#ffffff"
        dwg.add(
            dwg.text(
                status_name,
                insert=(x + badge_w / 2, y + self.TEXT_VERTICAL_OFFSET),
                text_anchor="middle",
                fill=f"#{text_color}" if not text_color.startswith("#") else text_color,
                font_size=f"{self.FONT_SIZE_SM}px",
                font_family=self.FONT_FAMILY,
                font_weight="bold",
            )
        )

    def _draw_termination_box(self, dwg, cx, y, termination):
        """Draw a single termination sub-box at the given position."""
        termination_x = cx - self.TERM_W / 2
        is_active = termination == self.origin
        termination_url = self._url(termination) if termination else "#"
        termination_name = str(termination)

        border_color = self.COLOR_ACTIVE_BORDER if is_active else self.COLOR_TERM_BORDER
        border_width = 3 if is_active else 1

        dwg.add(
            dwg.rect(
                insert=(termination_x, y),
                size=(self.TERM_W, self.TERM_H),
                rx=self.TERM_BORDER_RADIUS,
                ry=self.TERM_BORDER_RADIUS,
                fill=self.COLOR_TERM_BG,
                stroke=border_color,
                stroke_width=border_width,
            )
        )
        link = dwg.a(href=termination_url, target="_top")
        link.add(
            dwg.text(
                termination_name,
                insert=(cx, y + self.TERM_H / 2 + self.TEXT_VERTICAL_OFFSET),
                text_anchor="middle",
                fill=self.COLOR_LINK,
                font_size=f"{self.FONT_SIZE}px",
                font_family=self.FONT_FAMILY,
                font_weight="bold",
            )
        )
        dwg.add(link)

    def _draw_trace_end(self, dwg, cx, y, incomplete=False):
        """Draw the trace completion indicator."""
        text = "Trace completed" if not incomplete else "Trace incomplete"
        color = self.COLOR_SUCCESS if not incomplete else self.COLOR_DANGER

        y += self.TRACE_END_PADDING
        segment_count = len(self.traced_path)
        label = f"{text} \u2022 {segment_count} segment{'s' if segment_count != 1 else ''}"
        dwg.add(
            dwg.text(
                label,
                insert=(cx, y + self.FONT_SIZE),
                text_anchor="middle",
                fill=color,
                font_size=f"{self.FONT_SIZE}px",
                font_family=self.FONT_FAMILY,
                font_weight="bold",
            )
        )
        return y + self.TRACE_END_HEIGHT

    def _render_empty(self):
        """Render an empty/no-path SVG."""
        dwg = svgwrite.Drawing(size=(f"{self.COL_WIDTH}px", f"{self.EMPTY_HEIGHT}px"), debug=False)
        dwg.viewbox(0, 0, self.COL_WIDTH, self.EMPTY_HEIGHT)
        dwg.add(
            dwg.text(
                "No cable path found",
                insert=(self.COL_WIDTH / 2, self.EMPTY_HEIGHT / 2),
                text_anchor="middle",
                fill=self.COLOR_TEXT_MUTED,
                font_size=f"{self.FONT_SIZE}px",
                font_family=self.FONT_FAMILY,
            )
        )
        return dwg.tostring()
