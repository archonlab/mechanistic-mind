# Release 0.3.0

## Organism × World Foundation

Mechanistic Mind v0.3 separates the simulation into:

- World Engine,
- Body Engine,
- Psyche Engine.

The main invariant is:

> Objective simulator truth may be known to the simulator and Observer.
> Agent knowledge must be innate-accessible signal or learned from experience.

## Added

### World Engine

- configurable objective world state
- hidden object roles and effect tables
- local observation
- objective causal reliability
- delayed outcomes
- scheduled exogenous events
- stochastic exogenous resource relocation
- terrain-dependent movement cost inputs

### Body Engine

- objective mass / height / age
- energy reserve
- hydration
- fatigue
- damage
- movement cost depends on mass, fatigue, damage, terrain
- bounded toy mass adaptation
- interoceptive projection separate from body truth

### Psyche v0.3

- `PSYCHE-SINGLE-ORGANISM-V03`
- same 15 candidate foundation roles
- no preset personality
- empty learned models and habits at t=0
- learning in experienced-signal space
- spatial memory
- prediction / prediction error
- uncertainty
- state-dependent multi-objective valuation
- organism-specific self-model

### Experimental primitives

- same architecture / different world
- same world / different stochastic history
- delayed consequence without causal label
- exogenous event receipt visible only to Observer
- developmental history tail in state + full history in Observer telemetry

## Acceptance

- legacy v0.2.x regression remains green
- body truth is absent from agent observation
- hidden object roles/effect tables are absent from agent observation
- heavier objective body produces higher movement effort
- exogenous events occur independently of agent action
- random histories diverge by seed
- delayed effects arrive later without a causal source label
- identical psyche/body can diverge across objective world layouts

## First scientific observation

The initial static-world runs can still enter an undesirable physiological
attractor where energy and hydration approach zero while fatigue approaches
one.

This is not considered solved by v0.3.

It is evidence that the current interaction of valuation, navigation,
regulatory pressure, and learned action models remains insufficient in some
conditions.

No special-case survival behavior was added to hide this failure.

## Scope limits

v0.3 is still single-agent.

It does not yet implement:

- social interaction,
- communication,
- competition/cooperation between agents,
- realistic human physiology,
- developmental growth laws,
- reproduction,
- language,
- predefined personality constructs.

Those are intentionally outside this foundation.
