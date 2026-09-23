# SCIENTIFIC_V2_TO_V3_GAP_MAP

**Date:** 2026-09-21T05:32:50.068120+00:00  
**Example run referenced:** psyweb-20260921T041444.727355Z-ec8b45bc

| Relationship / need | V2 status | V3 requirement | Runtime instrumentation? | Storage impact | Scientific value |
|---------------------|-----------|----------------|--------------------------|----------------|------------------|
| Identity agent↔body↔controller | FRAGILE (undercover/agent_1) | IdentityMap + controller_type | Writer-side mapping (no science change) | Tiny | Critical |
| observation→decision linkage | TEMPORALLY_ASSOCIATED | observation_id on DecisionReceipt | Capture observation used by cognition each tick | Low | Critical |
| decision→composite motor | Partial (legacy action; composite posthoc) | MotorReceipt every tick | Serialize last_motor_output | Low | Critical |
| motor→consequence | Weak / omitted BODY_MOVED | ConsequenceReceipt deltas | Snapshot before/after finish_tick | Low | Critical |
| PSC candidates/selection | Aggregates; structured often UNAVAILABLE | Compact DecisionReceipt every tick; top-k RESEARCH | Compact last_selection subset (already computed) | Low–med | Critical |
| Full PSC graphs | Expensive / checkpoint | FORENSIC sampled | Existing receipt builder, rate-limit | Med if abused | High forensic |
| prediction error/revision | NOT_ESTABLISHED often | RevisionReceipt when enabled | Emit existing per/tpe diagnostics | Low | High when ON |
| Endogenous motor channel | Not on timeline | Optional force norms RESEARCH | last_force_contributions compact | Low | Medium |
| Morphology B_site/torque | Omitted events | Checkpoint / RESEARCH ledger | Optional | Low–med | Medium |
| Vision GT vs accessible | MIXED in vision_optical | Split ObservationReceipt vs exposure events | Packaging only | Low | High |
| Signal volume | Dominates events | Lean IDs; no full state per event | Event schema slim | **Savings** | High perf |
| Coverage banner | Single PARTIAL/COMPLETE | CoverageMatrix | Meta only | Tiny | High honesty |
| Legacy one-label action | Still prominent | LEGACY_COMPATIBILITY only | Keep field but demote | None | Integrity |
| Wrapped spatial path | Misleading zeros | DERIVED from pose series | Analyzer-only OK | None | High |
| Experimenter vs autonomous | Label confusion | controller_type | Mapping | Tiny | Critical |
| Cognition aggregates alone | Misleading next to SCENARIO=0 | Deltas + decision receipts | Prefer deltas | Low | High |

### What V2 can still reconstruct without V3
Composite motor forensics (derived), resource bounds, signal counts, vision exposure associations (temporal), contact/push presence.

### What only V3 CORE unlocks
Stable per-tick causal spine for observation→decision→motor→consequence without guessing.

### Still NOT_ESTABLISHED even with V3
Semantic seeking/communication/intention; “looked at”; goal-directed resource foraging — hypothesis layer only.
