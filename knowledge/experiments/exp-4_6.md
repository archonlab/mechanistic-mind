# EXP-4.6 — update46 object resources v046

- Status: COMPLETED
- Source completeness: COMPLETE (final_report=True; preserved_result_files=9; source_files=1; tests=10)
- Predecessor: EXP-4.5
- Successor: EXP-4.7

## Why this experiment existed

Previous result: | Arm | MP candidates | Prospective ≠0 | Selected | |---|---|---|---| | A no-prospective | 21/21 | 0 | 0 | | B/C prospective | 21/21 | 63 | 0 | | D experience ablated | 0 | 0 | 0 | | E prediction ablated | 21/21 | 0 | 0 | Policy still WAIT×60 in phase2 for all bootstrap arms.

Unresolved question: NOT_RECORDED

This experiment: NOT_RECORDED

## Architecture

NOT_RECORDED

## Result

**Mixed.** Qty/durability-scaled objects already finite. **Six** replenishing objects (modes 3–4) had no reservoir → infinite identical USE. `quantity` / `durability` via `interaction_state_deltas`. **YES** (initial qty ÷ transfer chunk ± regen). Not a use_count knob. **YES** — full while qty ≥ chunk; last partial; then none. Per-object: {"OBJ-100": {"quantity_changed": true, "effective_uses": 11, "zeroed": true}, "OBJ-103": {"quantity_changed": true, "effective_uses": 8, "zeroed": true}, "OBJ-105": {"quantity_changed": true, "effective_uses": 5, "zeroed": true}, "OBJ-107": {"quantity_changed": true, "effective_uses": 25, "zeroed": false}} **YES** — low_energy 0.0800 vs high_energy -0.0400. **YES** — OBJ-107 regen 0→0.782; effects return. Not newly added; existing autonomous dynamics optional/unchanged. Quantity may be observable; semantic EMPTY/FOOD not exposed. Observer: last USE object + quantity fields. Familiarity does **not** change value (support 1..80 identical). Confidence not used as value. Organism: yes. Depletion→policy: not shown in free run. {'EMIT': 1, 'MOVE': 204, 'USE': 1, 'WAIT': 794}; USE=1 (OBJ-12×1). No depletion cycle, leave, or return. **NO.** Free-policy: USE consequence → learned significance → further USE / leave depleted object. Audit; ecology reservoir gap closed; controlled A/B/knowledge/recovery tests; compact Observer; autonomous artifact. Familia

## Limits

Free-policy: USE consequence → learned significance → further USE / leave depleted object.

## Next question

Free-policy: USE consequence → learned significance → further USE / leave depleted object.

## Provenance

- `results/update46_object_resources_v046/FINAL_REPORT.md`
- `results/update46_object_resources_v046/FINAL_REPORT.md`
- `results/update46_object_resources_v046/UPDATE46_AUTONOMOUS_RUN.json`
- `results/update46_object_resources_v046/UPDATE46_CAUSAL_CHAIN.json`
- `results/update46_object_resources_v046/UPDATE46_CAUSAL_CHAIN.md`
- `results/update46_object_resources_v046/UPDATE46_DEPLETION_TEST.json`
- `results/update46_object_resources_v046/UPDATE46_KNOWLEDGE_CONTROL.json`
- `results/update46_object_resources_v046/UPDATE46_OBJECT_USE_AUDIT.md`
- `results/update46_object_resources_v046/UPDATE46_ORGANISM_STATE_CONTROL.json`
- `results/update46_object_resources_v046/UPDATE46_RECOVERY_TEST.json`
- `experiments/run_update46_object_resources_v046.py`
- `tests/test_update460_arbitrary_physical_coupling.py`
- `tests/test_update461_live_operating_range.py`
- `tests/test_update462_amplitude_budget.py`
- `tests/test_update463_existing_physical_ecology.py`
- `tests/test_update464_world_body_path_audit.py`
- `tests/test_update465_minimal_passive_physical_exchange.py`
- `tests/test_update466_frozen_physical_composition.py`
- `tests/test_update467_physical_dof_access_audit.py`
- `tests/test_update468_persistent_process_provenance.py`
- `tests/test_update469_frozen_physical_composition.py`
