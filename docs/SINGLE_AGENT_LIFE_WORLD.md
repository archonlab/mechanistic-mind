# Single Agent Life World v0.1

Mechanistic Mind v0.2.1 gives the existing single-agent psyche a richer reality
without adding a social layer or scripting a life story.

## World

A bounded 9x7 spatial world contains obstacles and four persistent objects.
The agent starts in the center and sees only a radius-1 neighborhood.

The engine's world truth knows that the objects are:

- a recovery site,
- an energy resource,
- a hydration resource,
- a progress site.

The agent does **not** receive those labels or outcome tables. It sees generic
object IDs such as `OBJ-17`, an affordance (`USE`), position, and relative
offset. Consequences are learned only after interaction.

## Action vocabulary

The world exposes affordances dynamically:

- `MOVE:x,y`
- `USE:OBJ-id`
- `WAIT`

Movement targets encode local spatial possibilities, not semantic goals.
There is no `GO_EAT`, `GO_WORK`, or `FIND_WATER` action.

## Internal state

The Life profile uses:

- energy,
- hydration,
- fatigue,
- progress.

Energy and hydration drift downward, fatigue drifts upward. Consequences can
move these variables independently.

## Same 15 foundation roles, alternative implementations

The Life profile does not add a special navigation mechanism. It substitutes
implementations inside the existing Foundation Map:

- attention includes position and local objects,
- learning accepts arbitrary action tokens,
- memory stores visited positions and observed object locations,
- prediction adds a minimal prospective navigation estimate toward remembered
  objects whose experienced outcomes currently matter,
- valuation becomes multidimensional and state-dependent,
- action selection distinguishes novel local affordances from spatial
  exploration and exploitation.

This is a test of architectural substitutability, not a claim that these
implementations are biologically correct.

## First 220-tick run

With seed 17, the first baseline run:

- visited all 59 reachable positions,
- discovered all four objects,
- learned 64 action models,
- performed 148 movement actions,
- used objects 53 times,
- returned repeatedly to the progress, hydration, and recovery sites,
- accumulated 12 progress units,
- ended with energy ~0.58, hydration ~0.45, fatigue ~0.02.

The asymmetry of object use is scientifically useful rather than something to
hide: the current policy overuses the recovery site relative to the energy
source. Richer environments are already exposing biases that REST/WORK could
not reveal.

## What this version does not yet solve

- dynamic or depleting resources,
- stochastic outcomes,
- source relocation,
- explicit multi-step route search,
- active forgetting of stale spatial memories,
- delayed goals,
- mortality/damage dynamics,
- social agents.

These should become diagnostic interventions against the same single psyche,
not one-off scripted behaviors.
