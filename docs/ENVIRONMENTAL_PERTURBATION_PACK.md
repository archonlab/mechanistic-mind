# Environmental Perturbation Pack v0.2.2

Mechanistic Mind v0.2.2 keeps the same single psyche and turns the Life World
into an intervention surface.

The core scientific rule is:

> Perturb the environment, not the agent's private state, unless the experiment
> explicitly studies an internal intervention.

The agent never receives the perturbation manifest or receipt. It receives only
what the changed environment makes observable and the consequences it actually
experiences. Observer/world truth stores the exact intervention provenance.

## Timing contract

Each `ScheduledPerturbation` has an `effective_tick`.

An intervention with `effective_tick = 80` is applied after the action from
world tick 79. The first observation that can reflect the altered world is tick
80.

This creates a clean common-prefix design:

```text
ticks 0..79   matched control trajectory
after tick 79 intervention applied
tick 80       first post-intervention observation
```

## Canonical conditions

### CONTROL

No intervention. Same perturbed-world runtime, same psyche, same seed.

### RELOCATION

Move `OBJ-23` from its learned location `(7,5)` to `(1,5)`.

Primary measurements:
- visits to the stale remembered location,
- first visit to the new location,
- first post-relocation use,
- reacquisition latency.

This tests adaptation to spatial model invalidation. Failure is compatible with
multiple explanations, including stale memory, insufficient exploration,
weak change detection, or limitations in route generation.

### DEPLETION

Set `OBJ-04` inactive. It disappears as a visible/current affordance, but the
agent's memory is not edited.

Primary measurements:
- visits to the depleted remembered site,
- impossible uses after depletion (must remain zero),
- latency to another object interaction,
- internal-state cost.

This tests whether the agent can recover from a formerly reliable affordance
becoming unavailable.

### OUTCOME_NOISE

Add deterministic seeded noise to the experienced outcome of `OBJ-31`.

Primary measurements:
- prediction error on noisy uses,
- action allocation,
- progress variance,
- whether the agent overreacts to outcome fluctuations.

This separates stochastic consequence variation from a deterministic regime
change.

### AMBIENT_PRESSURE

Add an observer-defined environmental load to every experienced consequence:

```text
hydration_delta -= 0.018
fatigue_delta   += 0.004
```

Primary measurements:
- hydration-resource use,
- minimum hydration,
- homeostatic tension,
- changes in route allocation.

The intervention is environmental. No goal weight or internal state is directly
edited.

### UTILITY_CONFLICT

Increase the hydration/fatigue cost of the progress site without changing its
identity or its progress output.

Primary measurements:
- post-shift use of the progress site,
- progress accumulation,
- homeostatic state,
- valuation/action-selection response.

This creates a changing multi-objective tradeoff instead of a single reward
change.

## Intervention API

The pack currently supports five world-level operations:

- `RELOCATE_OBJECT`
- `SET_OBJECT_ACTIVE`
- `SET_OUTCOME_NOISE`
- `SET_AMBIENT_LOAD`
- `SHIFT_OBJECT_OUTCOME`

Each intervention produces an observer-only receipt with:

- perturbation id,
- kind,
- applied-after tick,
- effective tick,
- parameters,
- before snapshot,
- after snapshot.

## Matched-control integrity

Canonical conditions use:

- one agent,
- identical initial psyche state,
- identical world layout before intervention,
- identical seed,
- identical mechanism implementations,
- identical action availability before intervention.

Regression tests verify that the behavioral prefix is identical before the
intervention tick for deterministic conditions.

## Interpretation rule

A behavioral difference after intervention is an observation, not a mechanism
identification.

For example, failure to reacquire a relocated resource does not prove a
"memory failure". Competing explanations include exploration policy, stale
prediction, route-generation limits, valuation, uncertainty dynamics, or an
interaction among them.

Those alternatives become follow-up ablation/model-comparison experiments.

## ARCHON direction

This pack is deliberately structured for later ARCHON use:

```text
condition manifest
→ matched run
→ intervention receipt
→ Psychology telemetry
→ dependent metrics
→ competing mechanism hypotheses
→ next experiment
```

The first ARCHON-worthy experiment family is relocation/depletion because it
can distinguish persistence of stale spatial models from successful
re-exploration without adding any new psychological labels to the engine.
