# EXP-4.7 — update47 multi agent v047

- Status: COMPLETED
- Source completeness: COMPLETE (final_report=True; preserved_result_files=11; source_files=3; tests=7)
- Predecessor: EXP-4.6
- Successor: EXP-4.7.1

## Why this experiment existed

Previous result: **Mixed.** Qty/durability-scaled objects already finite. **Six** replenishing objects (modes 3–4) had no reservoir → infinite identical USE. `quantity` / `durability` via `interaction_state_deltas`. **YES** (initial qty ÷ transfer chunk ± regen). Not a use_count knob. **YES** — full while qty ≥ chunk; last partial; then none. Per-object: {"OBJ-100": {"quantity_changed": true, "effective_uses": 11, "zeroed": true}, "OBJ-103": {"quantity_changed": true, "effective_uses": 8, "zeroed": true}, "OBJ-1

Unresolved question: NOT_RECORDED

This experiment: NOT_RECORDED

## Architecture

1. **Share** geometry, objects, object state, dynamics, fields via one `OrganismWorld` / world dict. 2. **Do not share** memory/experience/retrieval/predictions/body/MPs/decisions — private `mechanisms_by_agent` + per-agent `agent.state` / `bodies`. 3. **Sequential** action apply in `sorted(agent_id)` order; shared dynamics advance once (`advance_dynamics` flag). 4. **No social plumbing** — occupancy blocking + optional anonymous OCCUPANT fragments only. 5. **Observer** — minimal: agent selector + project_tick(agent_id); no large UI rewrite.

## Result

**Status:** SUCCESS — code + reports synced to lab `~/Desktop/psy` (2026-09-11). Lab smoke: 2-agent Engine step OK. Telemetry `.jsonl` left on box extract only (large); metrics/reports present on lab. 1. **Share** geometry, objects, object state, dynamics, fields via one `OrganismWorld` / world dict. 2. **Do not share** memory/experience/retrieval/predictions/body/MPs/decisions — private `mechanisms_by_agent` + per-agent `agent.state` / `bodies`. 3. **Sequential** action apply in `sorted(agent_id)` order; shared dynamics advance once (`advance_dynamics` flag). 4. **No social plumbing** — occupancy blocking + optional anonymous OCCUPANT fragments only. 5. **Observer** — minimal: agent selector + project_tick(agent_id); no large UI rewrite. | Criterion | Result | |---|---| | Two agents co-exist, separate bodies & psyches | PASS (TWO_NEAR / TWO_FAR) | | MEMORY_ISOLATION | PASS (0 shared fingerprints) | | SHARED_OBJECT_TRACE | PASS (OBJ-12 quantity depleted by A's USE) | | SINGLE still runs | PASS | | Artifacts under `results/update47_multi_agent_v047/` | PASS | | No social reward plumbing | PASS | ```json { "MEMORY_ISOLATION": { "ticks": 40, "action_counts": { "A001": { "WAIT": 32 }, "B001": { "WAIT": 32 } }, "memory_isolation": { "episodes_A": 39, "episodes_B": 39, "pass": true, "shared_episode_fingerprints": 0 }, "memory_episode_counts": { "A001": 39, "B001": 39 }, "final_positi

## Limits

See FRONTIER.md (social channels; 4.6 USE/WAIT; full dual inspector; lab sync).

## Next question

UNKNOWN

## Provenance

- `results/update47_multi_agent_v047/FINAL_REPORT.md`
- `results/update47_multi_agent_v047/CAUSAL_CHAIN.md`
- `results/update47_multi_agent_v047/FINAL_REPORT.md`
- `results/update47_multi_agent_v047/FRONTIER.md`
- `results/update47_multi_agent_v047/MATRIX_SUMMARY.json`
- `results/update47_multi_agent_v047/UPDATE47_MULTI_AGENT_AUDIT.md`
- `results/update47_multi_agent_v047/memory_isolation_metrics.json`
- `results/update47_multi_agent_v047/passive_body_metrics.json`
- `results/update47_multi_agent_v047/shared_object_trace_metrics.json`
- `results/update47_multi_agent_v047/single_metrics.json`
- `results/update47_multi_agent_v047/two_far_metrics.json`
- `results/update47_multi_agent_v047/two_near_metrics.json`
- `experiments/run_update471_cross_agent_trace.py`
- `experiments/run_update47_matrix_lab_v047.py`
- `experiments/run_update47_multi_agent_v047.py`
- `tests/test_update470_generic_action_body_internal_return.py`
- `tests/test_update471_post_consequence_relaxation_latent_return.py`
- `tests/test_update472_state_dependent_physical_consequence.py`
- `tests/test_update473_physical_intervention_vs_nonintervention.py`
- `tests/test_update474_body_response_consequence_acquisition_archaeology.py`
- `tests/test_update475_response_contingent_internal_transition_acquisition.py`
- `tests/test_update476_acquired_transition_reinstatement.py`
