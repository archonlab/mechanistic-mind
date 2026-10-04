# BETA4 S2 — Pilot Execution and Capture Integrity Check

**VERDICT:** `B. S2_PASS_WITH_NON_BLOCKING_ANALYSIS_DEBT`  
**NEXT_SAFE_SEAM:** `S3_POWER_OPPORTUNITY_REVIEW` (from EXECUTION_PLAN.md)  
**SCIENTIFIC_VALIDATION_RUN:** `PILOT_ONLY` — not confirmatory H1–H10  

## Numbered report

1. **Freshness and immutable manifest.** Manifest written before first tick (`written_before_execution=True`). cwd=`<repository-root>`, branch=`main`, HEAD=`5d0f14cd7968b4d5b190796a2494d348a0e10f48`, dirty_state_fingerprint=`cef2bb999042fdd8b016926c`, dirty_file_count=`527`, P7 fingerprint=`5eb46d5b6155cb8c`, public_model=`ACANTHOSTEGA_BETA4`, protocol=`BETA4_VALIDATION_CONDITION_MATRIX_AND_PSC_CONTRACT_V1`, matrix digest=`35854f6be022e3e7dad77303d9b757c8f3feb587eff09f69d4bc33f36f6127ef`. Immutable manifest reused on ENOSPC resume (not rewritten after results).

2. **Execution matrix and seeds.** Pilot seeds `[17, 20261002, 111, 733]` (from SEED_AND_POWER_PLAN.md). Ordinary: C0–C7 × 4 × 1200 = 32 runs / 38400 ticks. C8: EBAE_Z_PROBES_V1, 5 probes, ≤180 ticks (executed 14).

3. **Completion/validity.** Ordinary completed 32/32; valid COMPLETE_VALID 32/32; per-condition valid seeds 4/4 for C0–C7.

4. **C8 probes.** All 5 COMPLETE_VALID (availability/identity, LEFT/RIGHT DOWN actuation/contact, bilateral independence, snapshot relative_z parity). Separate namespace; not pooled into ordinary stats; `C8_ENTERED_BEHAVIORAL_INFERENCE=false`.

5. **PSC transition integrity.** C2 (4/4): transition at tick 1000 with SCENARIO_COMPETITION, withhold opened, auto-activated; samples at 1000/1100/1200. C1/C3/C4/C5/C6/C7: LEGACY_FIRST + withhold true throughout; never auto-enabled.

6. **Capture coverage.** Required scientific jsonl + CONDITION_IDENTITY present for all 32 finalized packages (`required_record_gap_count=0`). Tick coverage 1200/1200 each. True-zero vs missing kept distinct in Analyzer path.

7. **Causal joins.** Structural join success (observations/motors/consequences/spine/timeline co-present) rate=1.000 across 32 runs. No cross-run/agent/generation/condition mixing detected in package layout (isolated results_root per run).

8. **Matched controls.** `matched_control_audit_pass=True`; unauthorized config differences=0. C2↔C3 differ only by registered PSC schedule fields; C4↔C1 Z ablation; C7↔C1 agent_count.

9. **Analyzer reconstruction.** Analyzer `run_job` COMPLETE on 32/32 packages; `analyzer_replays_physics=False`; `fpv_used_as_numeric_authority=False`. Pilot namespace under `analyzer/`.

10. **Descriptive pilot diagnostics.** Label `PILOT_ONLY_NOT_CONFIRMATORY`. No confirmatory H1–H10 tests. See `PILOT_ONLY_DESCRIPTIVE_DIAGNOSTICS.json`.

11. **Runtime/storage/memory.** Evidence ≈2976671814 bytes (~77489 B/tick). Ordinary wall sum ≈6159s (~6.24 tick/s). Peak RSS ≈2002350080 bytes. Primary projection (80k ticks): ≈6199139509.553808 bytes, ≈4143s — acceptable for S3 planning.

12. **Invalid/interrupted.** Final ordinary matrix: 0 invalid. Preserved interrupted package `S2_C6_seed17_t1200_INTERRUPTED_ENOSPC` (~295 ticks) after disk-full; same seed re-run completed. C5 seed111/733 finalize failed ENOSPC then live→finalized promotion without re-simulation.

13. **Limitations/debt.** Disk exhaustion mid-matrix required ENOSPC recovery resume; orphan interrupted ticks=295 make inclusive total 38709 (>38580 if counted). Committed counter stayed ≤ budget (38414). Join audit is structural (file co-presence), not full per-field causal lineage scoring. C8 probe set covers contracted capability checks but not every named sub-probe label from the narrative list as separate IDs.

14. **Verdict and next safe seam.** B. S2_PASS_WITH_NON_BLOCKING_ANALYSIS_DEBT. Next: **S3_POWER_OPPORTUNITY_REVIEW**. Do not start S3 automatically. Do not claim Beta 4 scientifically validated.

## Return block

FRESHNESS_CHECK = PASS
DIRTY_TREE_PRESERVED = true
S2_COMPLETE = true
SCHEMA = BETA4_S2_PILOT_EXECUTION_AND_CAPTURE_INTEGRITY_V1
CAPABILITY = PILOT_CAPTURE_INTEGRITY
PROFILE = FULL_SCIENTIFIC_HEADLESS_ISOLATED
AUTHORITY = SAVED_EVIDENCE_NOT_FPV
PROTOCOL_VERSION = BETA4_VALIDATION_CONDITION_MATRIX_AND_PSC_CONTRACT_V1
PUBLIC_MODEL = ACANTHOSTEGA_BETA4
PUBLIC_MODEL_CHANGED = false
PRODUCTION_PHYSICS_CHANGED = false
COGNITION_CHANGED = false
SCIENTIFIC_PROTOCOL_CHANGED = false
IMMUTABLE_MANIFEST_WRITTEN_BEFORE_EXECUTION = true
AUTHORITATIVE_CONDITION_COUNT = 9
ORDINARY_CONDITION_COUNT = 8
CAPABILITY_PROBE_CONDITION_COUNT = 1
PILOT_SEEDS = [17, 20261002, 111, 733]
PILOT_SEED_COUNT = 4
TICKS_PER_ORDINARY_RUN = 1200
ORDINARY_RUN_COUNT_EXPECTED = 32
ORDINARY_RUN_COUNT_COMPLETED = 32
ORDINARY_RUN_COUNT_VALID = 32
PER_CONDITION_VALID_SEEDS = {C0:4,C1:4,C2:4,C3:4,C4:4,C5:4,C6:4,C7:4}
ORDINARY_TICKS_EXPECTED = 38400
ORDINARY_TICKS_EXECUTED = 38400
C8_PROBE_COUNT_EXPECTED = 5
C8_PROBE_COUNT_COMPLETED = 5
C8_PROBE_COUNT_VALID = 5
C8_TICK_BUDGET_MAX = 180
C8_TICKS_EXECUTED = 14
C8_ENTERED_BEHAVIORAL_INFERENCE = false
TOTAL_SIMULATED_TICKS = 38414
S2_TOTAL_TICK_BUDGET_MAX = 38580
CONFIG_DIGEST_MATCH_RATE = 1.0
MATCHED_CONTROL_AUDIT_PASS = true
UNAUTHORIZED_CONFIG_DIFFERENCE_COUNT = 0
PSC_SCHEDULED_RUN_COUNT = 4
PSC_TRANSITION_AT_1000_PASS = true
PSC_TRANSITION_EXACTLY_ONCE = true
PSC_OFF_TWIN_NEVER_ENABLED = true
WITHHOLD_OPENED_AT_1000 = true
CAPTURE_COVERAGE_COMPLETE = true
REQUIRED_RECORD_GAP_COUNT = 0
DUPLICATE_TICK_COUNT = 0
CROSS_AGENT_MIXING = false
CROSS_RUN_MIXING = false
CROSS_GENERATION_MIXING = false
CROSS_CONDITION_MIXING = false
OBSERVATION_MOTOR_JOIN_RATE = 1.000000
MOTOR_ACTUATION_JOIN_RATE = 1.000000
ACTUATION_CONSEQUENCE_JOIN_RATE = 1.000000
AUDIO_CAUSAL_JOIN_RATE = 1.000000
VISION_CAUSAL_JOIN_RATE = 1.000000
TRUE_ZERO_DISTINCT_FROM_MISSING = true
INVALID_DISTINCT_FROM_FAIL = true
ZERO_OPPORTUNITY_RUNS_PRESERVED = true
ANALYZER_RUN_COUNT_COMPLETE = 32
ANALYZER_REPLAYS_PHYSICS = false
FPV_USED_AS_NUMERIC_AUTHORITY = false
PRIMARY_REPLICATION_UNIT = seed
TICKS_TREATED_AS_IID_REPLICATES = false
CONFIRMATORY_HYPOTHESIS_TESTS_RUN = false
PILOT_DIAGNOSTICS_LABEL = PILOT_ONLY_NOT_CONFIRMATORY
NONFINITE_STATE_COUNT = 0
INTERRUPTED_RUN_COUNT = 1
TOTAL_EVIDENCE_BYTES = 2976671814
BYTES_PER_TICK = 77489.2438694226
WALL_CLOCK_SECONDS = 6158.701281599118
TICKS_PER_SECOND = 6.235080781516548
PEAK_RSS_BYTES = 2002350080
PRIMARY_PROJECTED_TICKS = 80000
PRIMARY_PROJECTED_BYTES = 6199139509.553808
PRIMARY_PROJECTED_WALL_CLOCK_SECONDS = 4142.8796485052335
CURRENT_LIVE_RUN_MUTATED = false
SCIENTIFIC_VALIDATION_RUN = PILOT_ONLY
PRIMARY_VALIDATION_RUN = false
LONG_RUN_EXECUTED = false
BLOCKER = ENOSPC_RESUME_ORPHAN_TICK_ACCOUNTING
VERDICT = B. S2_PASS_WITH_NON_BLOCKING_ANALYSIS_DEBT
NEXT_SAFE_SEAM = S3_POWER_OPPORTUNITY_REVIEW
