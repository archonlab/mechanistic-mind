# Release 0.3.4

## Contextual Object Ecology × Compositional World

This release adds a lower-level physical substrate in which consequences can
depend on body state and short history, objects can be relocated, and local
directional exposure changes with persistent object geometry.

## Architecture

`ObjectiveObject` now supports mobility, mass, numeric directional attenuation,
and numeric body-state-gated effects. `ObjectiveWorldEngine` owns action
legality, carried-object position updates, persistence, and directional ray
attenuation. `BodyEngine` owns decaying generic internal loads and carried-mass
cost while retaining the existing metabolic mass equation. The organism psyche
learns length-2 and length-3 action n-grams inside its ordinary learning and
prediction stages.

The canonical `ContextualObjectEcologyWorld` contains anonymous objects and
numeric channels. Hidden rules are observer truth. Agent observations expose
only ordinary cues, positions, available actions, and interoceptive consequences.

## Acceptance answers

- A. Can object effects depend on body state? **YES.** Numeric min/max gates
  are evaluated against objective body state.
- B. Can repeated exposure accumulate? **YES.** Generic internal loads decay
  and accumulate across ticks.
- C. Can A+B physically produce a result unavailable from A or B alone?
  **YES.** In the canonical diagnostic, two `OBJ-12` exposures raise a hidden
  load above a numeric gate; later `OBJ-29` then produces positive energy and
  recovery that neither isolated condition produces.
- D. Does the agent start knowing that combinations exist? **NO.** Its generic
  history-model store begins empty and hidden physical rules are not observed.
- E. Can the agent represent predictive information from short action histories
  without a recipe-specific subsystem? **YES.** Ordinary action n-grams of
  lengths two and three index learned consequence means.
- F. Can false/overcomplete sequences remain plausible in the learned model?
  **YES.** Different n-gram lengths and correlations are retained independently;
  no truth oracle or minimality rule deletes them.
- G. Can objects be physically moved and persist at new positions? **YES.**
  Legal take, movement, and release update objective object position.
- H. Does carrying have body cost? **YES.** Daily energy, hydration, and fatigue
  costs scale with carried kilograms.
- I. Does object geometry alter local wind exposure? **YES.** The canonical
  directional exposure is attenuated by objects on the source ray.
- J. Does moving an object move the protected region? **YES.** Attenuation is
  recomputed from current positions, so relocation changes affected cells.
- K. Can multiple-object geometry produce a different effect than isolated
  objects? **YES.** Independent attenuation factors multiply.
- L. Is there ANY primitive concept of shelter/building/settlement/recipe/crafting?
  **NO.** See `ONTOLOGY_AUDIT.md`.

## Controlled diagnostic results (seed 17)

- Same object action, low versus high hidden load: energy-signal effect changed
  from `-0.09` to `+0.15` (difference `+0.24`).
- Repeated `OBJ-12`: load `0.34` then `0.6664` after decay and re-exposure.
- A-only final energy effect: `-0.09`; B-only: `-0.09`; A-then-B: `+0.15`.
- Geometry exposure multipliers: first object `0.35`, second object `0.50`,
  both `0.175`. Moving the first object changed the sampled cell from `0.175`
  to `0.50`.
- Carrying 11 kg changed one-day energy from `0.725` to `0.714` and fatigue
  from `0.165` to `0.1738`; mass was unchanged relative to the matched control.
- A length-3 model predicted `+0.19` while a conflicting length-2 model remained
  stored, demonstrating representational capacity rather than truth.

## Reproduce

```bash
python3 -m pytest -q tests/test_contextual_object_ecology_v034.py
python3 experiments/run_contextual_object_ecology_v034.py
python3 observer_launcher.py --world contextual-objects --mechanism psyche-v03 --ticks 30 --seed 17
python3 -m pytest -q
```

## Scientific limitations and negative results

These are controlled mechanism diagnostics, not a demonstration of autonomous
discovery. No run here shows a stable object configuration emerging, being
preferentially maintained, or being repeatedly reconstructed. The attenuation
physics is a two-dimensional cardinal-ray toy model; objects have no rotation,
shape extent, collision volume, torque, breakage, or multi-agent ownership.
Internal loads are abstract scalars, not pharmacology. N-gram means do not
perform causal identification and can preserve spurious or overcomplete
histories. The agent's existing action selection was not tuned to manufacture
the target phenomenon.
