# Dynamic Object Ecology v0.3.5

The canonical contextual-object world is a deterministic 32×32 ecology with 30
objects. Seeded placement creates near, medium, distant, isolated, clustered,
and sparse regions without depending on Observer pixels.

## Mutable object state

Each object retains ordinary objective fields plus a small compositional state
contract:

```text
mutable_state: quantity, durability
state_capacities
interaction_state_deltas
minimum_effect_state
effect_scale_state
regeneration_rates
observable_state_fields
remove_when_exhausted
```

An interaction applies only the deltas configured by that object. Reusable
objects have no state delta. Finite effects stop when their configured minimum
state is unavailable. A partial final quantity scales the final effect rather
than creating material from nothing. Exhausted objects remain present unless
`remove_when_exhausted` is explicitly configured.

Regeneration is deterministic and bounded by state capacity. It is applied by
the objective world transition before the current action and is recorded in the
action receipt. The psyche is not told regeneration rates or hidden state. Only
fields named in `observable_state_fields` enter local perception.

## Scientific record

Every `USE` receipt records:

- object ID;
- mutable object state before and after;
- applied object-state deltas;
- effect availability and scale;
- relevant objective body context before interaction.

The enclosing developmental-history row already records body truth before and
after, experienced signal changes, action, and tick. Canonical mechanism
telemetry provides predictions and prediction errors where the active psyche
supports them.

## Seed-17 baseline

Before finite state and world expansion, the previous compact world produced a
39-action consecutive `USE:OBJ-29` run and 59 total uses in the measured
120-tick baseline. That
object had no depleting state and was colocated with the initial agent.

The expanded seed-17 run must be interpreted as a new ecology rather than an
anti-loop patch. No repetition penalty was added. Reusable objects can still
become learned behavioral attractors; this is preserved as a scientific result.

In the 120-tick expanded seed-17 comparison, `OBJ-29` was used once and retained
quantity `0.88`; its longest run was one action. The agent visited 97 positions
and remembered seven objects. The strongest observed repetition moved to the
objectively reusable `OBJ-109`: 13 total uses, with a maximum run of four. This
does not prove depletion alone caused exploration because map scale, placement,
and ecology changed together. It does show that the original `OBJ-29` attractor
did not survive, while shorter attraction to a reusable object remained.
