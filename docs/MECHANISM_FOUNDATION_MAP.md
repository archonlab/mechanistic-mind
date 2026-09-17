# Mechanism Foundation Map v0.1

This map is a **research scaffold**, not a declaration that psychology has a
settled list of fundamental mechanisms.

The Single Agent Psyche Foundation gives each candidate role:
- explicit inputs,
- explicit state ownership,
- an explicit temporal location,
- alternatives,
- a discriminating experiment,
- ablation/substitution capability.

Current candidate roles:

1. Internal regulation
2. Perception
3. Attention
4. Learning
5. Memory
6. Prediction
7. Prediction error
8. Uncertainty
9. Goals
10. Global modulation
11. Self-model
12. Habit
13. Valuation
14. Action generation
15. Action selection

The v0.2 rule is:

> Do not program a psychological behavior. Program candidate processes whose
> interaction may generate behavior.

## Single-agent boundary

Foundation v0.2 deliberately excludes:
- social agents,
- language,
- communication,
- reputation,
- norms,
- predefined personality labels.

Those become meaningful only after one continuous agent is sufficiently
coherent on its own.

## Same-tick causal order

```text
Internal regulation
→ Perception
→ Attention
→ Learning from previous consequence
→ Memory
→ Prediction
→ Prediction error
→ Uncertainty
→ Goals
→ Global modulation
→ Self-model
→ Habit
→ Valuation
→ Action generation
→ Action selection
→ Environment consequence
→ next tick
```

Modules inside the same stage receive the same stage-start state. Conflicting
same-stage writes fail closed.

## Important limitation

The current concrete modules are **minimal candidate implementations**. For
example, memory is a short episodic trace plus learned action statistics;
attention is a small deterministic filter; valuation is a simple
multi-objective calculation. These implementations are intended to be replaced
and experimentally compared.
