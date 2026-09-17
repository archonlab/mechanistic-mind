# Physical Object Map and Psychology Observer

The Psychology Observer renders the objective world as spatial cells, terrain,
environmental exposure, objects, obstacles, and agents. The camera transform is
display-only: zoom, pan, fit, follow, and selection never modify simulation
state.

## Objective object foundation

The existing `ObjectiveObject` model remains backward compatible and now has a
small extensible set of physical and sensory fields:

```text
position, mass_kg, size, shape, color, opacity, brightness, signal,
friction, hardness, quantity, durability, mobility, blocks_movement
```

`hidden_role` remains legacy compatibility metadata. The new renderer does not
use it, and object inspection filters it out. The psyche sees only local
observable fields and experienced consequences.

Carry feasibility is derived from object mobility, mass, size, and configured
agent capacity. Push feasibility is derived from mass, friction, mobility, and
configured push capacity. Blocking geometry uses the object's live position.
There is no item taxonomy or psychological value label.

## Interaction states

```text
FREE → CARRIED → DROPPED
FREE/DROPPED → PUSHED
```

`TAKE`, `MOVE`, `RELEASE`, and `PUSH` are ordinary deterministic world actions.
The UI only displays their telemetry. Invalid capacity, boundary, adjacency,
and collision requests leave state unchanged and produce an objective rejection
receipt.

## Focused manipulation protocol

The `object-manipulation` Observer mode is a focused regression protocol through
the real Engine and world transition layer. It approaches and carries `OBJ-41`,
drops it, pushes `OBJ-42`, and attempts a rejected push of high-resistance
`OBJ-73`.

Headless reproduction:

```bash
python3 observer_launcher.py \
  --world object-manipulation \
  --mechanism physical-demo \
  --ticks 9 \
  --seed 17 \
  --no-signals
```

Visual reproduction:

```bash
python3 psychology_observer.py
```

The visual launcher defaults to the unscripted `contextual-objects` ecology.
The focused protocol remains available to verify carry/push rendering.
`--tick-delay-ms` changes wall-clock presentation only; it is excluded from all
world transition calculations.
