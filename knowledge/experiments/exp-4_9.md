# EXP-4.9 — update49 world exchange

- Status: COMPLETED
- Source completeness: COMPLETE (final_report=True; preserved_result_files=17; source_files=2; tests=0)
- Predecessor: EXP-4.8
- Successor: EXP-4.9.1

## Why this experiment existed

Previous result: 1. USE still immediate full replenish? **No** when intake enabled (intake_mode). 2. Transfer amount: per-interaction cap 0.03 (partial/capacity bounded). 3. Bounded per interaction? **Yes** 4. Bounded by internal capacity? **Yes** (CAPACITY_LIMIT) 5. External qty conserved w.r.t. accepted? **True** 6. Material persists? **Yes** 7. Processing after other actions? **Yes** (ACTION_INDEPENDENCE) 8. Consequence unfolds over ticks: see DELAYED_PROCESSING series 9. Partial transfer: **True** 10. Empty 

Unresolved question: NOT_RECORDED

This experiment: NOT_RECORDED

## Architecture

NOT_RECORDED

## Result

Continuous World–Organism Exchange × Physical Dependency - Maintained `env_material_field` (boundary condition) → per-tick `env_exchange_transfer` - Same `BodyState.internal_materials` and `process_materials` as Update 4.8 - USE discrete transfer still defers processing; continuous env does **not** permanently defer - MOVE affects exchange only via position → local availability - Defaults: `env_exchange_enabled=False` (opt-in) - **ENV_AVAILABLE**: PASS `{'pass_energy_responded': True, 'pass_exchange_nonzero': True, 'pass_internal_rose': True}` - **ENV_DEPRIVED**: PASS `{'pass_exchange_stops': True, 'pass_internal_declines': True}` - **ENV_RESTORED**: PASS `{'pass_exchange_returns': True, 'pass_internal_rises_after': True}` - **EXCHANGE_ABLATED**: PASS `{'pass_internal_flat': True, 'pass_zero_exchange': True}` - **PROCESSING_ABLATED**: PASS `{'pass_exchange_ok': True, 'pass_internal_accumulates': True, 'pass_no_processing_credit': True}` - **SPATIAL_MOVE**: PASS `{'pass_high_gt_low': True, 'pass_moved': True}` - **USE_REGRESSION_4_8**: PASS `{'pass_processing_later': True, 'pass_qty_down': True, 'pass_use_transfer': True}` - **AUTONOMOUS_200**: OK (physics ran; policy null allowed) `{'action_counts': {'WAIT': 200}, 'total_env_exchange': 1.6000000000000012}` - PASS abs_error=0.000e+00 - PASS (0 hits) 1. local availability (maintained field) 2. env_exchange_transfer (bounded per t

## Limits

- Not repaired. Physical dependency only; no survival rewards / temporal credit / policy fix.

## Next question

- Not repaired. Physical dependency only; no survival rewards / temporal credit / policy fix.

## Provenance

- `results/update49_world_exchange/UPDATE49_FINAL_REPORT.md`
- `results/update49_world_exchange/AUTONOMOUS_200_SUMMARY.json`
- `results/update49_world_exchange/ENV_AVAILABLE_SUMMARY.json`
- `results/update49_world_exchange/ENV_DEPRIVED_SUMMARY.json`
- `results/update49_world_exchange/ENV_RESTORED_SUMMARY.json`
- `results/update49_world_exchange/EXCHANGE_ABLATED_SUMMARY.json`
- `results/update49_world_exchange/OBSERVER_UPDATE49_AUDIT.md`
- `results/update49_world_exchange/PHYSICAL_CONSERVATION_AUDIT.json`
- `results/update49_world_exchange/PHYSICAL_CONSERVATION_AUDIT.md`
- `results/update49_world_exchange/PROCESSING_ABLATED_SUMMARY.json`
- `results/update49_world_exchange/SEMANTIC_LEAKAGE_AUDIT.json`
- `results/update49_world_exchange/SEMANTIC_LEAKAGE_AUDIT.md`
- `results/update49_world_exchange/SPATIAL_MOVE_SUMMARY.json`
- `experiments/run_update491_env_regulation_probe.py`
- `experiments/run_update49_world_exchange.py`
