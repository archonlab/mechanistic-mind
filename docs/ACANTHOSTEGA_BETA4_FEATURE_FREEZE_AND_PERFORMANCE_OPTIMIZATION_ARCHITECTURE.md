# ACANTHOSTEGA · BETA4 FEATURE FREEZE AND PERFORMANCE OPTIMIZATION ARCHITECTURE

## Verdict
**B. BENCHMARK_NUMBERS_NOT_COMPARABLE_REBASE_REQUIRED**

FIRST_HABITABLE habitability PASS stands. Phase7 “tps” labels are **not** a valid optimization baseline. First implementation slice is **P0 benchmark/instrumentation contract**, not production physics/renderer rewrites.

## Freeze
Beta 4.0 is **feature-complete enough to freeze** for performance engineering:
- selector (Tiktaalik 3.1 + Acanthostega Beta 4.0);
- cumulative VW1–VW7, Free-Space, material/WMT, locomotion, effector Z, O1–O6, LPS/O5, Observer modes, Analyzer, snapshot/restore, privacy.

Permitted: `BUG_FIX_ALLOWED`, `PERFORMANCE_EQUIVALENT_ALLOWED`, `TEST_OBSERVABILITY_ALLOWED`.  
Deferred: scientific calibration, new features.  
Forbidden before release: semantic authority changes / evidence dropping / false TPS claims.

Scientific behavioral validation remains **NOT_YET_COMPLETE** and is not blocked by freeze — it resumes after P0 using honest metrics.

## Why VISION≈2493 is not simulation TPS
It timed repeated `agent_observation()` **without** `step`, on a warm path. It excludes motor, contacts, Free-Space, WMT, LPS end-of-tick, capture, and browser work.

## Why MAP/VOLUME/SURFACE numbers are not comparable
- MAP proxy = step+observation, not canvas MAP.
- VOLUME proxy = backend prism description only (~18432 faces), not E2E.
- SURFACE proxy = O6 summary with **undefined cold/warm**; cold≃470ms vs warm≃0.1ms.

## Evidence-backed next costs (post-rebase suspects)
1. VOLUME payload build ~220–240ms + ~2.1MB  
2. SURFACE cold rebuild ~470ms + ~2.6MB (warm cached)  
3. serialize.py always attaching VOLUME/O6 when VW1 on  
4. Headless step ~10–25ms (secondary for Observer VOLUME UX)

## Roadmap
P0 instrumentation → P1 inactive payload/render suspension → P2 VOLUME persist → P3 SURFACE persist → P4 serialize cache → P5 O4 (proof-gated) → P6 Analyzer stream → P7 release performance gate.

## Artifacts
See `results/beta4_feature_freeze_and_performance_optimization_architecture/`.

## Next safe seam
`BETA4_PERFORMANCE_BENCHMARK_REBASE_AND_INSTRUMENTATION_V1` (P0 implementation).
