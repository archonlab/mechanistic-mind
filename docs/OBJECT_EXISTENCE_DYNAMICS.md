# Object Existence Dynamics — Update #4

Object effects and spatial-temporal existence are independent world
properties. This update does not add food, water, migration knowledge, or
route reasoning to the psyche.

## Separation

```text
A. WHAT AN OBJECT DOES     body/world effects
B. HOW IT EXISTS           STATIC | RELOCATING_RANDOM | RELOCATING_ROUTE
```

`OBJ-A` may change `energy_delta` and separately follow a hidden route
`A -> B -> C -> A`. The two configurations do not imply each other.

## Modes

`STATIC` preserves prior behavior. A finite `max_uses` still deactivates
the current appearance and does not invent renewal.

`RELOCATING_RANDOM` removes the current appearance after its trigger,
keeps the logical object, waits a configured delay, and restores a new
valid appearance.

`RELOCATING_ROUTE` uses an ordered list of regions. Regions are allowed
cells, not semantic places. `cycle: true` wraps the route. `cycle: false`
ends after the last disappearance.

The architecture accepts later modes (`PERIODIC`, `CONDITIONAL`,
`TEMPORARY`) without psyche changes. They are not implemented here.

## Configuration example

```json
{
  "object_id": "OBJ-A",
  "position": [1, 1],
  "body_effects": {"energy_delta": 0.20},
  "max_uses": 2,
  "existence": {
    "mode": "RELOCATING_ROUTE",
    "trigger": {"type": "DEPLETED"},
    "route": [
      {"region": "A", "cells": [[1, 1]]},
      {"region": "B", "cells": [[3, 1]]},
      {"region": "C", "cells": [[5, 1]]}
    ],
    "cycle": true,
    "transition_delay_ticks": [2, 2],
    "randomize_position_within_region": false
  }
}
```

An explanatory analogy is a renewable environmental source that is not
always in the same place. That analogy is not an agent-facing category.

## Cognitive firewall

Agent observation may contain position, cue, affordance, and already
lawful visible fields. It must not contain mode, route, route index,
next region, next position, delay remaining, trigger identity, or future
appearance time.

Ground-truth events live on the world state:

```text
OBJECT_DEPLETED
OBJECT_DISAPPEARED
OBJECT_RELOCATED
OBJECT_REAPPEARED
```

Observer/Analyzer may reconstruct existence history from those events.
Psyche code does not read them.

## Determinism

Relocation, within-region sampling, residence, and delay draws use the
run `DeterministicRandom`. Same config plus same seed replay the
objective existence history.

## Claim boundary

This update implements an experimental capability. It does not require
the agent to learn a route and does not claim planning, belief, or
semantic resource knowledge.
