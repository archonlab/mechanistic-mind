# BETA4 Primary Budget / Lineage / Storage Readiness V1

**VERDICT:** `A. S3_REPASS_READY_FOR_S4`  
**BLOCKER:** `none`  
**NEXT_SAFE_SEAM:** `S4_PRIMARY_MATCHED_SEED_VALIDATION`  

## Numbered report

1. **Author budget decision.** `BUDGET_LIMIT_SCOPE=PRIMARY_ONLY`. Core C1/C2/C3 = 60 000; ablations C4:3 / C5:3 / C6:2 / C7:2 = 20 000; total primary 80 000. Pilot 38 400 + C8 14 outside primary cap → program total projected 118 414. C0 primary allocation = 0.

2. **Exact 40-run / 80 000-tick manifest.** Written as `IMMUTABLE_PRIMARY_MANIFEST_DRAFT.json` with `EXECUTION_AUTHORIZED=false`.

3. **Seed allocations.** Core: all ten primary-family seeds. C4/C5: [5,23,42]; C6/C7: [5,23]. All ablation seeds paired to C1.

4. **Pilot supersession.** Pilot seeds remain preregistered; primary 2000-tick package `SUPERSEDES_PILOT_PACKAGE` for confirmatory analysis; no double-counting; pilot retained as provenance.

5. **Actuation→ETC lineage.** Added `actuation_etc_causal_lineage` researcher receipt (exact IDs; no second solver). Probe captured=True.

6. **O3/O4 lineage.** Added `o3_o4_exact_receptor_lineage` from existing O4 traces (no raycast/FPV). Probe captured=True.

7. **Finalization repair.** Same-filesystem hardlink promotion into `.tmp-*` then atomic rename; avoids full live→tmp byte duplication. Orphan not deleted.

8. **Storage inventory.** Free≈147520827392 bytes; inodes free≈28033614. Capacity pass=True.

9. **Exact user action still required.** None for capacity — free space gate passes (≥15 GB). Inventory still lists optional regeneratable/archive candidates; do not delete immutable S2 evidence or live Observer packages. Orphan retained. `EXECUTION_AUTHORIZED=false` until explicit S4 start.

10. **Equivalence tests.** Short HEADLESS probes; ticks=20 ≤30. Numerics unchanged flags false for physics/cognition/O1–O5. Hardlink finalize exercised.

11. **Ticks used.** TOTAL_SIMULATED_TICKS=20 (validation probes only; not primary).

12. **S3 readiness verdict.** A. S3_REPASS_READY_FOR_S4

13. **Next safe seam.** S4_PRIMARY_MATCHED_SEED_VALIDATION — do not start S4 automatically.

## Return block

FRESHNESS_CHECK = PASS
DIRTY_TREE_PRESERVED = true
IMPLEMENTATION_COMPLETE = true
AUTHOR_BUDGET_DECISION_APPLIED = true
PROTOCOL_AMENDMENT_VERSION = BETA4_PRIMARY_BUDGET_AMENDMENT_V1
BUDGET_LIMIT_SCOPE = PRIMARY_ONLY
PILOT_TICKS = 38400
C8_TICKS = 14
PRIMARY_TICK_BUDGET = 80000
TOTAL_PROGRAM_TICKS_PROJECTED = 118414
PRIMARY_RUN_COUNT = 40
PRIMARY_CORE_ALLOCATION = C1:10x2000;C2:10x2000;C3:10x2000
PRIMARY_ABLATION_ALLOCATION = C4:3x2000;C5:3x2000;C6:2x2000;C7:2x2000
C0_PRIMARY_ALLOCATION = 0
PRIMARY_MANIFEST_COMPLETE = true
PRIMARY_MANIFEST_EXECUTION_AUTHORIZED = false
PILOT_SEED_REUSE_POLICY = PILOT_SEEDS_INCLUDED_AS_PREREGISTERED_DATA_WITH_PRIMARY_SUPERSESSION
PILOT_PACKAGES_COUNTED_AS_INDEPENDENT_REPLICATES = false
PILOT_PRIMARY_OVERLAP_DOUBLE_COUNTED = false
ACTUATION_ETC_EXACT_LINEAGE = True
O3_O4_EXACT_LINEAGE = True
STRUCTURAL_COPRESENCE_ONLY_REQUIRED_METRIC_COUNT = 0
PHYSICS_NUMERICS_CHANGED = false
COGNITION_NUMERICS_CHANGED = false
O1_O5_NUMERICS_CHANGED = false
FINALIZATION_FULL_COPY_REQUIRED = false
FINALIZATION_ATOMIC_PROMOTION = true
INCOMPLETE_STAGING_EXPLICIT = true
ORPHAN_DELETED = false
DESTRUCTIVE_CLEANUP_PERFORMED = false
FILESYSTEM_FREE_BYTES = 147520827392
FILESYSTEM_FREE_INODES = 28033614
MINIMUM_SAFE_FREE_BYTES = 15000000000
STORAGE_CAPACITY_PASS = True
USER_STORAGE_ACTION_REQUIRED = false
PRIMARY_PROJECTED_RAW_BYTES = 6200000000
PRIMARY_PROJECTED_TRANSIENT_PEAK_BYTES = 2930000000.0
PRIMARY_PROJECTED_WALL_CLOCK_SECONDS = 12820.51282051282
PRIMARY_PROJECTED_PEAK_RSS_BYTES = 2002350080
CURRENT_LIVE_RUN_MUTATED = false
SCIENTIFIC_VALIDATION_RUN = false
PRIMARY_VALIDATION_RUN = false
LONG_RUN_EXECUTED = false
TOTAL_SIMULATED_TICKS = 20
VALIDATION_BUDGET_MAX = 30
BLOCKER = none
VERDICT = A. S3_REPASS_READY_FOR_S4
NEXT_SAFE_SEAM = S4_PRIMARY_MATCHED_SEED_VALIDATION
