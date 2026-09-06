# Form Layout

+++ 3.3.0

Apps lay out their model forms declaratively, without writing a template, by setting `fieldsets` on the form's `Meta` class. Any form based on `NautobotModelForm` supports this; other forms can opt in by adding `FormLayoutMixin` (from `nautobot.apps.ui`) to their bases.

```python
from nautobot.apps.forms import NautobotModelForm
from nautobot.apps.ui import Contributed, FormField, FormPanel, TabbedGroups, When

from .models import FloorPlan


class FloorPlanForm(NautobotModelForm):
    class Meta:
        model = FloorPlan
        fields = "__all__"
        fieldsets = (
            ("Floor Plan", ("location", "x_size", "y_size", "tile_width", "tile_depth", "is_tile_movable")),
            FormPanel(
                "X Axis",
                (
                    TabbedGroups(
                        ("Default Labels", ("x_axis_labels", "x_origin_seed", "x_axis_step")),
                        ("Custom Labels", ("x_custom_labels",)),
                    ),
                ),
            ),
            Contributed("tenancy"),
        )
```

Anything you do not name is still rendered, in a trailing panel, and the Custom Fields, Relationships, Notes, Dynamic Groups and Tags panels are contributed automatically by the form mixins. The existing `("Label", {"tabs": (...)})` shorthand used by some apps continues to parse.

Refer to the [Form Layout Framework](../../../core/form-layout.md) documentation for the full set of components (including `FormSetPanel` for formsets and `RemoteFragment` for regions the server re-renders over HTMX), the `render_if` / `visible_if` visibility mechanisms, the resolution rules, and how to ship JavaScript with a panel via `Media`.
