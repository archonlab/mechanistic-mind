# ACANTHOSTEGA · P3 SURFACE PERSISTENT GEOMETRY AND INCREMENTAL UPDATES V1

## Identity
- Schema: `OBSERVER_SURFACE_INCREMENTAL_PAYLOAD_V1`
- Capability: `surface_persistent_geometry_and_incremental_updates`
- Profile: `O2_O3_O3A_GENERATION_KEYED_SURFACE_DELTA_P3_V1`
- Authority: `RESEARCHER_DERIVED_DELIVERY_OPTIMIZATION_NO_PHYSICAL_EFFECT`

## Verdict
**A. P3_PASS_PERSISTENT_SURFACE_INCREMENTAL_UPDATES**

Ordinary entity motion no longer rebuilds/resends static terrain geometry. DYNAMIC wire omits static columns when the client holds a matching `static_payload_id`. Materialized static+dynamic matches full SURFACE authority. Entity transforms refresh every frame (fixes pre-P3 warm-cache staleness). P1 MAP/VOLUME/SURFACE gating and tab-hidden suspension preserved.

## Decomposition
1. **Static** — O2 facet topology/geometry/material refs (`surface_static`)
2. **Optical** — O3 band/causal columns (`surface_dynamic.facets_columnar_optical`)
3. **Entities** — O3A samples always refreshed + tombstones
4. **UI-only** — camera/band/palette local; no physics request

## Measured
See `results/p3_surface_persistent_geometry_and_incremental_updates_v1/BENCHMARK_RESULTS.json`.
Cold remains O2+O3 authority cost (~1.2 s). Warm/dynamic ≪ 1 ms. Body-move static hit rate = 1.0.

Browser ms: **NOT_MEASURED** (honest); persistent buffer + merge path implemented.

## Next safe seam
**P2 · VOLUME persistent geometry / incremental updates** (VOLUME still ~2 MB / ~280 ms when requested). P4 serialize cache remains secondary.

## Artifacts
`results/p3_surface_persistent_geometry_and_incremental_updates_v1/`
