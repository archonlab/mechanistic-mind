# EXP-4.8 — update48 bounded intake

- Status: COMPLETED
- Source completeness: COMPLETE (final_report=True; preserved_result_files=18; source_files=1; tests=0)
- Predecessor: EXP-4.7.1-POST-CONSEQUENCE-RELAXATION-LATENT-RETURN
- Successor: EXP-4.9

## Why this experiment existed

Previous result: MIXED_TEMPORAL_FATE Claims 104 / 104. Canonical: 4.70 G, 4.69 F. Zero new capability. 4.72 not implemented.

Unresolved question: Bounded external→internal transfer with temporal processing **without knowing the object is food**? **YES (physical).** Secondary: existing psyche discovers delayed relation without temporal credit? **NOT DEMONSTRATED.** Elapsed 75.4s

This experiment: Bounded external→internal transfer with temporal processing **without knowing the object is food**? **YES (physical).** Secondary: existing psyche discovers delayed relation without temporal credit? **NOT DEMONSTRATED.** Elapsed 75.4s

## Architecture

NOT_RECORDED

## Result

1. USE still immediate full replenish? **No** when intake enabled (intake_mode). 2. Transfer amount: per-interaction cap 0.03 (partial/capacity bounded). 3. Bounded per interaction? **Yes** 4. Bounded by internal capacity? **Yes** (CAPACITY_LIMIT) 5. External qty conserved w.r.t. accepted? **True** 6. Material persists? **Yes** 7. Processing after other actions? **Yes** (ACTION_INDEPENDENCE) 8. Consequence unfolds over ticks: see DELAYED_PROCESSING series 9. Partial transfer: **True** 10. Empty object zero transfer: accepted=0.0 11. Processing ablation isolates consequence: **True** 12. Transfer ablation isolates acquisition: accepted=0.0 13. State-dependent significance: existing valuation retained; physical deltas recorded for low/high energy 14. Material intrinsic +VALUE? **No** 15. FOOD/EAT/HUNGER in cognition? leak PASS=True 16–20. Delayed association / prediction / valuation / selection: **NULL / not demonstrated** 21. First unsupported cognitive arrow: `{'arrow': 'body_consequence→ordinary_experience', 'status': 'PARTIAL'}` 22. Strongest conclusion: Bounded physical intake with delayed internal processing is demonstrated without food semantics; existing psyche does not yet associate delayed consequences with earlier USE. 23. Smallest next experiment: instrument whether ordinary episodes bind USE-time transfer to later processing-time body deltas — still no credit-assignm

## Limits

See report and causal/claim registries; do not infer beyond recorded assertions.

## Next question

UNKNOWN

## Provenance

- `results/update48_bounded_intake/UPDATE48_FINAL_REPORT.md`
- `results/update48_bounded_intake/ACTION_INDEPENDENCE_SUMMARY.json`
- `results/update48_bounded_intake/AUTONOMOUS_SUMMARY.json`
- `results/update48_bounded_intake/CAPACITY_LIMIT_SUMMARY.json`
- `results/update48_bounded_intake/DELAYED_PROCESSING_SUMMARY.json`
- `results/update48_bounded_intake/DIRECT_TRANSFER_SUMMARY.json`
- `results/update48_bounded_intake/EMPTY_OBJECT_SUMMARY.json`
- `results/update48_bounded_intake/OBSERVER_UPDATE48_AUDIT.md`
- `results/update48_bounded_intake/PARTIAL_FINAL_TRANSFER_SUMMARY.json`
- `results/update48_bounded_intake/PHYSICAL_CONSERVATION_AUDIT.json`
- `results/update48_bounded_intake/PHYSICAL_CONSERVATION_AUDIT.md`
- `results/update48_bounded_intake/PROCESSING_ABLATED_SUMMARY.json`
- `results/update48_bounded_intake/SEMANTIC_LEAKAGE_AUDIT.md`
- `experiments/run_update48_bounded_intake.py`
