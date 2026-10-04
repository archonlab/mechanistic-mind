# ACANTHOSTEGA · P5 BROWSER UPLOAD RENDER PROFILING AND OPTIMIZATION V1

## Identity
- Schema: `OBSERVER_BROWSER_RENDER_PERFORMANCE_V1`
- Capability: `browser_upload_render_profiling_and_optimization`
- Profile: `MAP_VOLUME_SURFACE_BROWSER_PIPELINE_P5_V1`
- Authority: `RESEARCHER_DISPLAY_PERFORMANCE_TELEMETRY_NO_PHYSICAL_EFFECT`

## Verdict
**A. P5_PASS_BROWSER_HOTSPOT_OPTIMIZED**

Phase A (isolated Chromium + Observer `:8788`) ranked **VOLUME_DRAW_FIRST**: Canvas2D project/sort/fill of ~18k occupancy faces (~25–42 ms project/sort, ~56–78 ms fill when uncached). Not GPU upload (no WebGL path).

Phase B: persistent flat face list + projected-poly cache + static-layer blit keyed by `(staticPayloadId, camera, viewport)`. Warm entity/paused redraws with unchanged camera hit ~0 ms project/sort and ~0 ms fill (blit only). Camera orbit invalidates and rebuilds exactly.

## Contracts preserved
P1 suspension, P2/P3 static IDs, picking labels, no DPR reduction, no primitive omission, no physics/cognition/snapshot change.

## Artifacts
`results/p5_browser_upload_render_profiling_and_optimization_v1/`

## Next safe seam
Camera-orbit VOLUME rebuild remains expensive by necessity; MAP warm server path still dominated by JSON encode (~5.7 ms) → optional `P4B_CANONICAL_RESPONSE_ENCODING_OPTIMIZATION_V1` if end-to-end MAP latency matters more than VOLUME orbit.
