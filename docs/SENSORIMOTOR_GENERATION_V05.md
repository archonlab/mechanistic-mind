# Experience-Structured Sensorimotor Generation — TODO #5

Sensorimotor generation is one continuous mechanism. It does not begin as
an exploration phase and does not get replaced by a learned policy.

```text
body
+ accessible perception
+ physically available actions
+ bounded retrieved experience
    -> sensorimotor proposals
    -> ordinary selection
```

## Audit of the prior path

`PSYCHE-SINGLE-ORGANISM-V03` enumerates every available action and then
selects with `CONTEXT_NOVEL_AFFORDANCE_PROBE`, `SPATIAL_EXPLORATION`, and
`exploration_gain * uncertainty`. That is a phase-like novelty probe, not
continuous experience-structured generation.

This revision adds `PSYCHE-SENSORIMOTOR-V05` instead of silently rewriting
V03. V03 remains the compatibility organism psyche.

No age, tick, or memory-size switch was found or added.

## What changes

Endogenous motor variation always remains available over **currently
legal** actions. Bounded retrieved contingencies may occupy more of the
proposal set when evidence is strong. Unfamiliar context returns weak
evidence, so variation broadens again. That dependence is on retrieval
quality, not lifetime.

Unknown objects do not receive extra value. Controllability is stored as
a predictive rate, not a reward. Selection still uses ordinary action
value; WAIT can win; severe physiology can suppress interaction.

Retrieval stays inside the existing budget:

```text
max_pattern_candidates: 4
max_exception_candidates: 4
max_episode_candidates: 8
max_total_memory_candidates: 12
```

## Claim boundary

Allowed: endogenous motor variation, learned sensorimotor contingency,
context-dependent proposal structure.

Not claimed: curiosity, interest, exploration drive, play, intention,
or human development.
