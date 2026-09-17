# Mechanistic Mind v0.3: Organism × World Foundation

v0.3 introduces explicit separation between objective environment, objective
body physiology, accessible organism signals, and learned psyche state.

## Runtime composition

```text
ObjectiveWorldEngine
        │
        ├─ geometry
        ├─ resources
        ├─ affordances
        ├─ causal reliability
        ├─ delayed outcomes
        ├─ exogenous events
        └─ stochastic events
        │
        ↓
OrganismWorld
        ↕
BodyEngine
        │
        ├─ mass
        ├─ height
        ├─ age
        ├─ energy reserve
        ├─ hydration
        ├─ fatigue
        ├─ damage
        └─ movement cost
        │
        ↓ accessible interoception only
SingleOrganismPsycheV03
```

The legacy v0.2.x Life World remains available as a diagnostic branch.

## World Engine

`mechanistic_mind/world_engine/`

The World Engine owns objective external truth.

It currently supports:

- configurable 2D geometry,
- blocked cells,
- local visibility radius,
- resource/object placement,
- hidden object roles,
- body effects and world effects,
- terrain movement factors,
- causal reliability,
- delayed action outcomes,
- scheduled exogenous events,
- stochastic exogenous relocation events.

Current exogenous event kinds:

- `RELOCATE_OBJECT`
- `SET_OBJECT_ACTIVE`
- `SPAWN_OBJECT`
- `DAMAGE_ORGANISM`
- `SET_TERRAIN_FACTOR`

The event receipt is never placed in the agent observation.

## Body Engine

`mechanistic_mind/body/`

The Body Engine owns objective toy physiology.

Current state:

- `mass_kg`
- `height_m`
- `age_years`
- `energy_reserve`
- `hydration`
- `fatigue`
- `damage`
- `last_effort_cost`

Movement cost depends on objective body state and terrain.

The implementation is intentionally a toy physiology, not a claim of
biological realism.

### Agent-accessible interoception

The psyche receives:

- `energy_signal`
- `hydration_signal`
- `fatigue_signal`
- `discomfort_signal`
- `effort_signal`

It does not automatically receive:

- body mass,
- age,
- physiological equations,
- objective body-effect tables.

## Psyche v0.3

`PSYCHE-SINGLE-ORGANISM-V03`

The psyche still uses the same 15 candidate process roles.

Concrete v0.3 implementations operate on accessible signal space instead of
owning objective physiology.

At t=0:

- learned action models are empty,
- episodic memory is empty,
- spatial memory is empty,
- habits are empty,
- no personality is assigned,
- no trust/avoidance/anxiety values exist.

Basic regulatory target signals are allowed as the minimal innate need layer.

## Experienced consequence versus objective consequence

When the body changes, the psyche learns from changes in accessible signals.

For example:

```text
Body truth:
mass=...
energy_reserve=...

Agent experience:
energy_signal_delta=-0.04
effort_signal_delta=+0.08
```

With delayed or exogenous effects, the agent is not given a causal label.

This intentionally permits incorrect causal learning.

## History

Full scientific history belongs to the canonical Observer JSONL.

Only a bounded recent tail is kept inside simulation state so long runs do not
carry an ever-growing deep-copied archive.

## Initial foundation experiment

`experiments/run_organism_world_foundation.py`

It compares:

1. same psyche + same initial body + different resource layouts,
2. same psyche + same objective world + different random-event histories.

This experiment establishes divergence, not a unique causal explanation.

Later ARCHON experiments should identify which mechanisms produce a specific
trajectory difference.
