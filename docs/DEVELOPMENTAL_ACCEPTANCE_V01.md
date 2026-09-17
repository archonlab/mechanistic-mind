# Developmental Experience Acquisition — Acceptance Report

Date: 2026-09-10
Suite: full `pytest -q` — all collected tests passed after implementation.

## Architecture

Minimal insertion: `mechanistic_mind/psyche/developmental.py` + `DevelopmentalGateModule` in MEMORY stage of sensorimotor (and optional organism) stacks; gate consumed by sensorimotor proposal generation and organism prediction history scope; optional `CompressionConfig.developmental` for ExperienceCompressionMechanism.

## Acceptance criteria

1. PASS — Memory/contingency formation from tick 1 under DEVELOPMENTAL (`test_memory_forms_under_developmental_from_tick_1`).
2. PASS — Early cognition uses bounded retrieval/learned slots (`test_sensorimotor_gate_bounds_learned_proposals`).
3. PASS — No semantic knowledge modules added.
4. PASS — No curiosity/novelty reward added.
5. PASS — No scripted exploration behavior added.
6. PASS — No privileged world-state path into cognition; gate from agent stores only.
7. PASS — Fragments from ordinary sensorimotor/episode/action_model experience.
8. PASS — Early sparse history cannot immediately dominate mature access (`gate_factor < 0.95` early; proposal caps).
9. PASS — Gate/stage expands gradually (stage progression in short experiment).
10. PASS — Maturity uses structural metrics (`test_maturity_not_tick_only`).
11. PASS — Not tick-only (`test_maturity_not_tick_only`, `test_cannot_fully_mature_before_min_ticks`).
12. PASS — `min_ticks` configurable.
13. PASS — `max_ticks` configurable.
14. PASS — Same `PSYCHE-SENSORIMOTOR-V05` psyche across stages.
15. PASS — Memory not reset (`test_same_psyche_persists_and_no_memory_reset`).
16. PASS — Mature cognition retains developmental contingencies.
17. PASS — `ADULT_FROM_TICK_0` available.
18. PASS — Identical seeds/worlds in experiment runner.
19. PASS — Observer/telemetry via `memory.developmental` and mechanism telemetry (not agent observation channel).
20. PASS — Existing bounded-cognition tests still pass.
21. PASS — Existing object ecology tests still pass (full suite green).
22. PASS — Physical field constraints untouched.
23. PASS — Compression mechanisms remain valid (disabled developmental reproduces actions).
24. PASS — No new unbounded stores; uses existing sensorimotor/episode capacities.
25. PASS — `DISABLED` default completely disables gating effects on proposals.
26. PASS — `test_compression_developmental_disabled_reproduces_budget`.

## Short deterministic comparison

`experiments/run_developmental_experience_v01.py --ticks-dev 40 --ticks-life 60` (seed 17):
- ADULT_FROM_TICK_0: mean early gate 1.0, matured_at 1
- DEVELOPMENTAL: mean early gate ~0.42, matured_at 81 (at max window)
- Late action diversity matched in this short ecology smoke (both locked to two MOVE actions); longer runs needed for behavioral persistence claims.

## Limitations

- Short CI windows use reduced tick bounds; production defaults remain 3000/5000/10000.
- RICH/POOR developmental environment control is architecturally permitted but not implemented as a separate experiment yet.
- Human developmental language is analogy only.
