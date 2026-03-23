# Cable Termination Endpoints

+++ 3.1

A cable termination endpoint is a record linking a [cable](cable.md) to a terminating object (such as an interface, front port, or circuit termination) at a specific cable end and optional connector/position.

Every cable has at least two cable termination endpoint rows — one for the A side and one for the B side. Breakout cables have additional rows, one per connected connector per side.

## Fields

* **Cable** — the cable this termination belongs to.
* **Cable End** — which end of the cable: "A" or "B".
* **Termination** — the terminating object (Interface, FrontPort, RearPort, ConsolePort, ConsoleServerPort, PowerPort, PowerOutlet, PowerFeed, or CircuitTermination).
* **Connector** — the connector number on this cable end. Null for standard (non-breakout) cables.
* **Position** — the position (lane) within the connector. Null for standard cables.

## Constraints

Each terminating object can only be connected to one cable at a time. This is enforced by a unique constraint on `(termination_type, termination_id)`.

## Standard vs Breakout Cables

| Cable Type | Rows | Connector/Position |
|------------|------|--------------------|
| Standard (no template) | 2 (one A, one B) | Null |
| Breakout (template assigned) | 1 per connected connector per side | Populated from template mapping |

## Related Models

* [Cable](cable.md) — the parent cable.
* [Breakout Template](breakouttemplate.md) — defines the connector/position structure for breakout cables.
