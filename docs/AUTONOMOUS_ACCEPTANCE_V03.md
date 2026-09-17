# Autonomous World Dynamics — Acceptance Report (Update 3)

Date: 2026-09-10
Full pytest: PASS.

## Architecture

Minimal insertion: `world_engine/autonomous.py` advanced inside `transition_action` (runs on WAIT). Master switch `WorldEngineConfig.autonomous_dynamics_enabled` (default False). Per-object `autonomous` config. Ground truth on world state only.

## Experiments (seed 17; A=80 free ticks, B=60 forced WAIT)

Experience stream:
- PASSIVE STATIC: unique_obs=1, passive_transitions=0, auto_events=0
- PASSIVE DYNAMIC: unique_obs=2, passive_transitions=14, auto_events=96

Behavior (free policy, EXPERIENCE_GATED unchanged):
- STATIC and DYNAMIC both repeated_action_concentration=0.5, wait_frequency=0.0
- Claim 2 (behavior change): **null on this short horizon**

## Acceptance 1–34

1–8 PASS (independent evolution, WAIT not freeze, body continues, autonomous move/state, generic, structured routes, reappear via existing existence still available)
9–10 PASS (no future trajectory / usefulness in observation)
11–13 PASS (no curiosity/novelty/forced exploration)
14 PASS (WAIT sensory change in DYNAMIC)
15 PASS (STATIC remains stable)
16–17 PASS (seeded determinism test)
18–19 PASS (passive/active metrics + provenance on world/receipts)
20 PASS (no provenance in observation; forbidden keys)
21 PASS (EXPERIENCE_GATED consumes ordinary experience unchanged)
22 PASS (developmental gating not retuned)
23–24 PASS (static/dynamic configurable)
25–29 PASS (full regression green)
30 PASS (event log capped; no per-tick world snapshots)
31 PARTIAL — machine-readable telemetry emitted; Psychology Observer UI panels not fully wired (documented)
32–33 PASS (experiments runnable)
34 PASS (no post-hoc behavioral tuning)

## Changed files

- mechanistic_mind/world_engine/autonomous.py (new)
- mechanistic_mind/world_engine/engine.py, models.py, existence.py, __init__.py
- worlds/contextual_object_ecology_v034.py (static/dynamic helpers)
- experiments/run_autonomous_world_dynamics_v03.py, configs/, tests/, docs/
