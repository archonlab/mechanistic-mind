# Mechanistic Mind v0.2.2 Release Note

## Environmental Perturbation Pack

v0.2.2 does not add a new psyche role. It keeps the same single continuous
psyche and introduces controlled environmental interventions around it.

Regression status: **78/78 tests pass**.

Standalone Observer + ARCHON bridge smoke:

- 6 Psychology ticks recorded,
- 6 ARCHON observations,
- 18 ARCHON events,
- 1 observer-only perturbation receipt,
- 0 perturbation service flags leaked into agent observation.

## First matched-control run

Design:

- one agent,
- seed 17,
- 160 ticks,
- intervention effective at tick 80,
- identical psyche and initial world,
- deterministic behavioral prefix before intervention.

All five treatment conditions reproduced the control action sequence exactly
through the pre-intervention window.

### CONTROL

Observed final progress: **9.0**.

Post-intervention-window object use in the equivalent control interval:

- OBJ-04: 15,
- OBJ-23: 2,
- OBJ-31: 8.

Mean prediction error: ~0.0086.
Mean tension: ~0.2623.

### RELOCATION

OBJ-23 was moved from `(7,5)` to `(1,5)` at tick 80.

Observed:

- the agent visited the stale old location twice,
- it did not visit the new location by tick 160,
- it did not reacquire/use OBJ-23,
- final progress was 1.0 versus 9.0 control,
- mean tension increased by ~0.0267,
- minimum hydration was ~0.135 lower than control.

Interpretation status: **adaptation failure observed; mechanism unresolved**.

Compatible explanations include insufficient renewed exploration, stale spatial
memory, route-generation limitations, valuation dynamics, or interactions
among them.

### DEPLETION

OBJ-04 became inactive at tick 80 while the agent's memory was left intact.

Observed:

- impossible post-depletion uses remained correctly at zero,
- the agent revisited the depleted site 50 times,
- no alternative object interaction occurred in the post window,
- final progress was 1.0 versus 9.0 control,
- mean tension increased by ~0.1512,
- minimum hydration was ~0.169 lower than control.

Interpretation status: **strong stale-affordance persistence observed**.

This does not by itself prove a memory mechanism failure. The agent may retain
an obsolete location because no existing process generates sufficient evidence
or incentive to reopen exploration.

### OUTCOME NOISE

Seeded outcome noise was added to OBJ-31 at tick 80.

Observed:

- 5 noisy post-intervention uses,
- all 5 produced explicit environment-effect receipts,
- mean prediction error on noisy uses was ~0.1703,
- overall post-window mean prediction error increased by ~0.0146 over control,
- final progress was ~5.95 versus 9.0 control.

Interpretation status: **noise sensitivity observed**.

The current running-mean learning/prediction stack detects mismatch but does not
yet establish whether it appropriately distinguishes stochastic variation from
regime change.

### AMBIENT PRESSURE

At tick 80 every action gained an environmental load:

- hydration delta -0.018,
- fatigue delta +0.004.

Observed:

- the load was applied on all 80 post-intervention ticks,
- OBJ-17 was used 16 times,
- OBJ-23 was used only once,
- final progress was 1.0,
- mean tension increased by ~0.0719,
- minimum hydration was ~0.169 lower than control.

Interpretation status: **cross-resource allocation anomaly observed**.

The system reacts strongly, but not obviously in the dimension an external
observer might expect. This is a useful target for valuation/regulation
analysis rather than something to patch by hand.

### UTILITY CONFLICT

At tick 80 the progress site retained its progress output while its hydration
and fatigue costs increased.

Observed:

- the agent used the progress site twice after the shift,
- first post-shift progress-site use occurred at tick 134,
- final progress was 3.0 versus 9.0 control,
- mean tension was slightly lower than control (~-0.0195 delta).

Interpretation status: **behavior changed under altered multi-objective cost**.

This is compatible with state-dependent valuation responding to the changed
tradeoff, but component ablations are required before attributing the effect to
a specific mechanism.

## Scientific consequence

The rich Life World is now doing its job: it exposes failures that the earlier
REST/WORK world could not reveal.

The most informative next experiment family is not another feature. It is a
mechanism-discrimination study around relocation and depletion:

```text
observed failure to recover
        ↓
competing explanations
        ↓
exploration ablation/substitution
memory staleness / forgetting manipulation
prediction-error-driven reopening
uncertainty policy manipulation
        ↓
which intervention restores adaptation?
```

This family is a strong candidate for later ARCHON-driven model comparison.
