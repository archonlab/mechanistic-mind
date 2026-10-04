# ACANTHOSTEGA_BETA4_RELEASE_EQUIVALENCE_AND_PERFORMANCE_GATE_V1

## Schema / profile / authority

- Schema: `BETA4_RELEASE_EQUIVALENCE_AND_PERFORMANCE_GATE_V1`
- Profile: `FROZEN_PUBLIC_MODEL_ENGINEERING_RELEASE_GATE_P7_V1`
- Authority: `ENGINEERING_VALIDATION_NO_NEW_SCIENTIFIC_CLAIM`

## Status

**Engineering release gate complete** with non-blocking performance debt.

Public model `ACANTHOSTEGA_BETA4` is **not** scientifically validated by this gate.

## Completed prerequisite chain

FIRST_HABITABLE → feature freeze → P0–P6/P4B → receptor-grounded FPV →
`P7_RECEPTOR_FPV_LIVE_REFRESH_REPAIR_V1` (operator-confirmed live) → this gate.

## FPV acceptance (updated)

```
RECEPTOR_FPV_ACCEPTANCE = PASS
COGNITION_FPV_ACCEPTANCE = PASS
LIVE_FPV_REFRESH = PASS
LATEST_EXACT_TRACE_ADVANCES = YES
MISSING_TRACE_IS_UNAVAILABLE = YES
TRUE_ZERO_DISTINCT_FROM_MISSING = YES
FPV_REFRESH_REPAIR = P7_RECEPTOR_FPV_LIVE_REFRESH_REPAIR_V1
LIVE_OPERATOR_ACCEPTANCE = CONFIRMED
```

Live evidence (port **8769**, RUNNING): `obs_tick`/`receptor_tick` 2458 → 2461 → 2464 with advancing trace IDs and capture counts. Same-tick caching preserved in isolated harness.

## Verdict

**B. P7_PASS_WITH_NON_BLOCKING_DEBT**

Hard scientific authority held (cache OFF/ON equivalence, freeze, snapshot/restore, FPV, Analyzer terminal).
Numeric performance targets for headless tick ≤25 ms, VOLUME warm ≤50 ms (software renderer), MAP full compact payload ≤0.5 MB, and mode-switch ≤100 ms remain missed and are registered as non-blocking engineering debt — not new regressions from this gate.

## Next seam

`BETA4_SCIENTIFIC_BEHAVIORAL_VALIDATION_ARCHITECTURE`

## Artifacts

Under `results/beta4_release_equivalence_and_performance_gate_v1/`:

- `RELEASE_CANDIDATE_MANIFEST.json`
- `FREEZE_MATRIX.md`
- `EQUIVALENCE_REPORT.md`
- `SNAPSHOT_RESTORE_REPORT.md`
- `OBSERVER_FPV_ACCEPTANCE.md`
- `ANALYZER_ACCEPTANCE.md`
- `PERFORMANCE_RESULTS.json`
- `TEST_MATRIX.md`
- `DEBT_REGISTER.md`
- `FINAL_REPORT.md`
- `LIVE_FPV_OPERATOR_CONFIRMATION.json`
- `gate_raw.json`
