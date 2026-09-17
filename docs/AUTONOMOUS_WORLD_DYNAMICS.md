# Autonomous World Dynamics (Update 3)

## Audit

- Every `transition_action` (including WAIT) already advances regeneration, existence clocks, body, and exogenous events.
- Default contextual ecology objects are mostly STATIC existence with no continuous motion.
- Gap: agent inactivity ⇒ little new sensory change when nearby objects lack autonomous motion.

## Insertion

- `mechanistic_mind/world_engine/autonomous.py` — generic temporal/motion properties.
- Called from `ObjectiveWorldEngine.transition_action` after existence advance.
- `WorldEngineConfig.autonomous_dynamics_enabled` master switch (default False = STATIC_WORLD).
- Per-object `autonomous` config on records; never copied into agent observation.
- Ground-truth events: `state["autonomous_events"]`, tick provenance `state["causal_provenance_tick"]`.

## Patterns

- `PERIODIC_ROUTE` — A→B→C→A positions
- `BOUNDED_WANDER` — seeded step within bound
- `OSCILLATE` — two-point oscillation
- Optional `state_cycle` on mutable quantity/durability fields
- Optional deplete→absent→reappear via existing existence modes remains available

Developmental gating is unchanged.
