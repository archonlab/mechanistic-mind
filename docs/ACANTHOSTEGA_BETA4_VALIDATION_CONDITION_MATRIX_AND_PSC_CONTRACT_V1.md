# ACANTHOSTEGA_BETA4_VALIDATION_CONDITION_MATRIX_AND_PSC_CONTRACT_V1

**Date:** 2026-10-02  
**Status:** Author decision applied; matrix unique; PSC schedule/restore repaired; S1 re-pass with non-blocking debt.  
**Public model:** `ACANTHOSTEGA_BETA4` (unchanged).  
**Verdict:** `B. MATRIX_REPAIRED_S1_PASS_WITH_NON_BLOCKING_DEBT`

## Author decision (frozen)

- `C4_BASE=C1`, `C4_AGENT_COUNT=2` (Z unavailable only)
- `C7_BASE=C1`, `agent_count=1`
- `C8_PROBE_IDS=[EBAE_Z_PROBES_V1]`, budget 180 hard max; ordinary snippet excluded; diagnostic only

Ambiguous predecessor archived:  
`results/.../EXPERIMENTAL_CONDITIONS_AMBIGUOUS_SUPERSEDED_ARCHIVED.md`  
Live preregistration updated:  
`results/beta4_scientific_behavioral_validation_architecture/EXPERIMENTAL_CONDITIONS.md`

## Exact C0–C8

| ID | Base | Causal delta | Agents |
|----|------|--------------|--------|
| C0 | shipped | — | 2 |
| C1 | shipped | LEGACY_FIRST | 2 |
| C2 | C1-pre | schedule@1000 → competition ON + withhold open once | 2 |
| C3 | C1 | pairing metadata only | 2 |
| C4 | C1 | Z/MRWA off | 2 |
| C5 | C1 | light/source off | 2 |
| C6 | C1 | emission off | 2 |
| C7 | C1 | agent_count=1 | 1 |
| C8 | PSC-OFF | bounded EBAE Z controlled probes | 1 |

## PSC contract (implemented)

- 0–999: LEGACY_FIRST, withhold true, `psc_off_ticks=1000`
- ≥1000 once: SCENARIO_COMPETITION + withhold false; receipts `PSC_ACTIVATION` + `SMC_WITHHOLD_OPEN`
- Off twin: LEGACY_FIRST + withhold true forever
- `psc_off_ticks` on `CognitionConfig`; snapshot `psc_schedule` block; restore 999/1000/1001 verified
- Legacy missing schedule → explicit status (not silent reschedule)

## C8 manifest

Controlled probes only: availability, LEFT DOWN, RIGHT DOWN, bilateral independence, snapshot relative_z parity. Ordinary `H_ORDINARY` excluded. Max 180 ticks (not run in S1).

## Production changes (schedule persistence only)

- `CognitionConfig.psc_off_ticks`
- `_maybe_auto_enable_psc` opens withhold + emits withhold receipt
- snapshot/restore of schedule activation flags

No physics, morphology, sensor/motor numerics, public-model composition, hypotheses, or pass criteria changes.

## Next

`S2_PILOT_EXECUTION_AND_CAPTURE_INTEGRITY_CHECK`
