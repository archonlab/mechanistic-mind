# Obstacle Learning & Value Ecology v0.3.2

## Purpose

The world must do more than provide resources.

It must be able to create histories in which:

- a valuable goal has more than one route,
- routes have different physical costs,
- an initially unknown obstacle produces surprising bodily consequences,
- a learned safe detour becomes preferable,
- perceptual cues acquire value through experience,
- a similar cue can later cause a wrong expectation,
- direct experience can correct that wrong expectation.

## Objective obstacle model

`ObjectiveObstacle` is World Truth.

Current fields:

```text
obstacle_id
position
cue_signature
cue_salience
traversable
active
terrain_factor
contact_probability
body_effects
```

Only a perceptual projection is available to the agent.

The hidden body-effect table remains Observer truth.

## Route learning

Movement consequences are learned under the existing Learning role.

The psyche can retain:

```text
MOVE:x,y → experienced signal changes
```

and:

```text
obstacle cue → experienced signal changes
```

Prediction then evaluates known paths.

No psychological variable named avoidance is required.

### Minimal diagnostic

At the same decision point:

```text
direct route:
  shorter

detour:
  longer
```

With a safe learned direct cell:

```text
direct value > detour value
→ direct selected
```

With the same cell carrying learned adverse consequences:

```text
direct value < detour value
→ detour selected
```

The difference is history, not a different personality parameter.

## Cue-value learning

Objects expose a cue signature but not their outcome tables.

The learning model maintains:

```text
object_cue_models
```

A novel object can therefore inherit an expectation from another object that
looked similar.

Direct object experience has higher specificity than cue generalization:

```text
direct action model
    overrides
cue model
```

This gives a minimal mechanism for:

```text
looks valuable
→ approach
→ disappointing outcome
→ prediction error
→ revised object-specific expectation
```

without a `deceptive_object` concept inside the psyche.

## Free-life observation, seed 17

In the canonical HAZARD world:

- a real valuable cue is learned before the decoy exists;
- the decoy appears exogenously on day 30;
- the first selected move explicitly targeting the decoy occurs on day 39;
- the decoy is used on day 40;
- predicted progress was `0.55`;
- actual progress was `0.0`;
- prediction source was `OBJECT_CUE:CUE-AMBER-VALUABLE`;
- a direct `USE:GOAL-DECOY` action model later stores progress `0.0`.

This is a clean example of an internal model being wrong because of
generalization from previous experience.

## Obstacle free-life observation

In the short 70-day free-life comparison:

```text
HAZARD:
  one obstacle contact
  damage > 0

SHAM_CUE:
  one obstacle contact
  damage = 0
```

The overall trajectory did not diverge strongly within that horizon.

Therefore v0.3.2 does **not** claim that one small injury automatically creates
a persistent avoidance phenotype.

The controlled route diagnostic establishes only that, once both routes are
known and the direct path has learned adverse value, the same architecture can
select the detour.

## Temporal value

Objects now support cooldowns and optional finite use capacity.

This makes objective value depend not only on consequence magnitude but also
on availability through time.

## Scientific status

Established in the model implementation:

- obstacle consequences can be hidden from the agent;
- obstacle cues can be remembered and learned;
- learned physical route cost can alter route selection;
- value can generalize by perceptual cue;
- cue generalization can be wrong;
- direct experience can override the generalized object expectation.

Not established:

- human fear,
- clinical avoidance,
- boredom,
- perseverance,
- real-world value learning equations,
- biological realism of the obstacle injury model.

These remain future hypotheses or calibration targets.
