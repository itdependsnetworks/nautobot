# Breakout Templates

+++ 3.1

A breakout template is a reusable definition of a cable's internal lane structure. It describes how the connectors and positions on one side of a cable map to the connectors and positions on the other side. Templates are defined once and can be assigned to many [cables](cable.md).

## Fields

Each breakout template defines the physical structure of both cable ends:

* **A Connectors / A Positions** — the number of physical connectors on the A side, and how many positions (lanes) each connector has.
* **B Connectors / B Positions** — the same for the B side.
* **Mapping** — a JSON array defining the explicit A→B lane mapping. Each entry maps an A-side connector+position pair to a B-side connector+position pair. See [Breakout Cables feature guide](../../feature-guides/breakout-cables.md) for mapping examples.
* **Is Shuffle** — indicates non-linear (polarity-shuffled) position mapping. Informational only.
* **Strands Per Lane** — number of physical strands per logical lane (1 for copper/DAC, 2 for duplex fiber, etc.).
* **Polarity Method** — the fiber polarity method (Straight-through, Reversed, Pair-reversed, Custom). Informational only.

## Properties

* **Total Lanes** — the number of discrete lanes, equal to the length of the mapping array.
* **Total Strands** — `total_lanes × strands_per_lane`.
* **Is Breakout** — true if the A-side and B-side connector/position counts differ.
* **Cable Count** — number of cables currently using this template.

## Validation

* Every `(a_connector, a_position)` and `(b_connector, b_position)` pair must be unique within the mapping.
* `a_connectors × a_positions` must equal `b_connectors × b_positions` and the mapping length.
* A template with assigned cables cannot be deleted.

## Related Models

* [Cable](cable.md) — a cable references a breakout template via the `breakout_template` field.
* [Cable Termination Endpoint](cableterminationendpoint.md) — the join table rows carry `connector` and `position` derived from the template mapping.
