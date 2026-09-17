# Release 0.3.2.1

## State-Conditional Learning & Navigation Fix

This patch responds to a failure observed in the canonical v0.3.2 HAZARD
free-life run.

The old trajectory could learn a resource only in a high-energy/high-hydration
state, later underestimate its value during depletion, and become trapped in a
progress-goal orbit while physiology deteriorated.

No survival override, fear variable, or hand-coded return-home rule was added.

## Fix 1: state-conditioned consequence learning

Action, object-cue, and obstacle-cue models now retain:

```text
global mean
+
coarse physiology-context means
```

The context is derived from accessible interoception only:

```text
energy
hydration
fatigue
discomfort
```

Each signal is discretized into LOW / MID / HIGH.

At action selection time the psyche stores the pre-action accessible state.
When the consequence arrives on the next tick, learning associates that
consequence with the state in which the action was chosen.

Example:

```text
USE:HOME at high energy
→ observed energy +0.08

USE:HOME at depleted state
→ observed energy +0.352
```

These are now separate learned contexts instead of being collapsed into one
context-free mean.

When an action is known globally but has never been sampled in the current body
state:

- the global mean remains a fallback prediction;
- context sample count is zero;
- uncertainty returns to 1.0 for that action/state pairing;
- a locally available affordance may be probed again as
  `CONTEXT_NOVEL_AFFORDANCE_PROBE`.

This does not give the agent hidden physiology equations. It only allows it to
notice that the same action can behave differently when the body is different.

## Fix 2: relative navigation advantage

v0.3.2 rewarded a movement by the absolute value of the route available after
the movement.

That allowed this loop:

```text
stand on valuable goal
→ step away
→ route back to valuable goal still exists
→ movement receives positive navigation value
→ step back
```

v0.3.2.1 instead computes navigation as an opportunity difference:

```text
navigation advantage
=
future opportunity from destination
-
future opportunity from current position
```

Therefore moving away from a goal already reached does not receive a bonus just
because the agent can return afterward.

## Fix 3: urgency semantics inside navigation

v0.3.2 multiplied all navigation by physiological urgency.

That accidentally made progress-only goals more attractive during depletion.

Navigation is now split into:

```text
navigation_regulatory
navigation_progress
```

Physiological urgency:

```text
amplifies regulatory navigation
suppresses progress navigation
```

matching the already existing suppression of direct progress value under high
tension.

This is not a survival rule. It is a correction to the multi-objective
valuation semantics.

## Seed-17 regression

Same canonical command:

```bash
python observer_launcher.py \
  --world obstacle-value \
  --mechanism psyche-v03 \
  --obstacle-condition HAZARD \
  --ticks 70 \
  --seed 17
```

v0.3.2.1 result:

```text
HOME uses: days 1, 51, 54, 57
GOAL-FAR uses: days 36, 69
DECOY use: day 40
obstacle contact: day 17

day 70:
energy    0.616
hydration 0.803
fatigue   0.692
damage    0.035
progress  3.77
```

The persistent 5,2 ↔ 6,2 goal orbit is gone.

The agent learned multiple state-specific HOME outcomes, including a depleted
context in which HOME produced much larger experienced recovery than on day 1.

This is one deterministic seed, not evidence that all self-destructive
attractors are solved.

## Scientific status

The patch establishes inside this toy model that:

- action consequences can be state-conditional;
- previously learned actions can become uncertain again in a new internal
  state;
- direct experience can refine the same action differently across body states;
- navigation can be represented as improvement relative to the current state;
- physiological urgency need not amplify progress-only navigation.

It does not establish the human mechanisms of motivation, homeostasis,
avoidance, boredom, or goal pursuit.
