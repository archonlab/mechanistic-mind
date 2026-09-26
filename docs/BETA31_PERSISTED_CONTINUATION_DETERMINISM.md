# Beta 3.1 persisted JSON continuation determinism

Independent of PE member packing. The same live-vs-JSON mismatch existed with compaction off.

## Verdict

**BETA31_PERSISTED_CONTINUATION_DETERMINISM = PASS** (after restore-path fixes)

Reference is uninterrupted live, not JSON-vs-JSON.

## Before fix

First divergence **t10** (seed 575 Beta 3.1 TwoAgent):

- LIVE vs in-memory restore: **FAIL**
- in-memory restore vs JSON restore: **EXACT**
- First pipeline stage: **OBSERVATION** (`exo_0`)
- Pose, `surface_optical`, `T`, illumination matched; `osc_*` energy was 0

Cause: `PhysicalSystemRuntime.restore` replaced `body` without `_sync_embodiment_dofs()`. TwoAgent calls `observations()` **before** `begin_tick`, so `_articulated_head_enabled` stayed False and FOV used body θ instead of head heading.

Also missing from planet serialize/restore: **`OSC_BANDS`** (would bite once emitters deposited energy). Snapshot now includes it. `prev_body_omega` and `last_orientation_meta` are persisted for vestibular/orientation continuation.

JSON tuple→list and stripped derived indexes were not the t10 exo break. RNG is `_rng_unit(seed,tick)` (EXACT).

## After fix

Search ticks 1,5,10,20,50,80,100,120,200: A=B=C.  
JSON restore from t100, next **100** ticks: EXACT.  
Crash-checkpoint tests: PASS.

Old snapshots without `OSC_BANDS` still load (bands None → `ensure_osc_fields` zeros), same as pre-fix.

No PE/PSC/vision sampling semantics were changed. Restore now reconstructs embodiment flags the live runtime already had.
