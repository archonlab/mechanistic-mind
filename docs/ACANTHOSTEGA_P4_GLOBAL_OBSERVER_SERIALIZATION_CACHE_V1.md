# ACANTHOSTEGA · P4 GLOBAL OBSERVER SERIALIZATION CACHE V1

## Identity
- Schema: `OBSERVER_SERIALIZATION_FRAGMENT_CACHE_V1`
- Capability: `global_observer_serialization_cache`
- Profile: `GENERATION_AND_TICK_SCOPED_CANONICAL_FRAME_FRAGMENT_CACHE_P4_V1`
- Authority: `DERIVED_RESEARCHER_SERIALIZATION_NO_PHYSICAL_EFFECT`
- Representation: `PICKLED_STRUCTURED_FRAGMENT_INDEPENDENT_CLONE_V1`

## Verdict
**A. P4_PASS_BOUNDED_SERIALIZATION_CACHE**

Paused MAP warm frame construction improved (~5.1 → ~2.8 ms p50) via bounded pickle fragment reuse. Hit≡miss except nested researcher telemetry counters. Snapshots/evidence uncached. P1/P2/P3 preserved. Apply/restore clears cache.

## Design
1. Canonical serializer → derived fragments
2. Cache: mechanisms, experiment, honesty, tick-scoped world (authority-keyed)
3. Independent pickle clones (deepcopy was slower than rebuild for large fragments)
4. Whole-frame JSON encode unchanged (no fragile concat)

## Measured
| Metric | Value |
|--------|-------|
| MAP paused OFF p50/p95 | 5.10 / 5.93 ms |
| MAP paused ON warm p50/p95 | 2.79 / 2.89 ms |
| JSON encode p95 | ~5.7 ms (unchanged) |
| Hit rate (paused warm) | ~0.93 |
| Cache memory | ~223 KB |

## Next safe seam
**P5 · browser upload/render** (server warm construction now ≤ JSON encode; cold VOLUME still VW1-bound).
