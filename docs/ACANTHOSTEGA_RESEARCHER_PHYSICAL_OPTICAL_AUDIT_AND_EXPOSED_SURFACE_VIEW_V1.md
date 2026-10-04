# Acanthostega Researcher Physical Optical Audit & Exposed Surface View V1 (O6)

## Identity
- **Schema:** `RESEARCHER_PHYSICAL_OPTICAL_AUDIT_VIEW_V1`
- **Capability:** `researcher_physical_optical_audit_view`
- **Profile:** `EXPOSED_SURFACE_AND_DIRECT_LIGHT_DISPLAY_O6_V1`
- **Authority:** `RESEARCHER_TRANSFORM_OVER_O2_O3_O3A_O4_O5_READ_ONLY`

O6 is a **passive scientific visualization** over O2/O3/O3A/O4/O5. It is **not** a physical mechanism or public preset.

## Viewport modes
1. `MAP / 2D` — existing WorldMap (unchanged)
2. `VOLUME / X-RAY` — existing VW7 occupancy prism view (unchanged authority; label clarified)
3. `SURFACE / LIGHT` — new O6 view over O2 exposed facets + O3A analytic entity geometry + O3 light state

## Surface geometry
- World material: O2 exposed facets only (no internal VW1 coincident faces)
- Bodies / ResourceObjects / held: O3A analytic samples (labelled analytic physical geometry)
- Display triangles are render artifacts only — never become authority

## Physical-light display transforms
- `CAUSAL_STATE` — O3 state classes
- `BAND_AUDIT` — `optical_band_0..5` scalar false-color
- `COMPOSITE_FALSE_COLOR` — fixed documented 6→display-RGB (`O6_FIXED_6_TO_DISPLAY_RGB_V1`)
- `MATERIAL_REFLECTANCE` — O1 reflectance audit independent of illumination

Labels always shown: RESEARCHER TRANSFORM · ABSTRACT NON-SI OPTICAL BANDS · NOT HUMAN RGB · NOT ORGANISM VISION

## Organism comparison
Exact O4 trace only; O5 timing envelope visible; camera ≠ organism eye; never recomputed from display.

## Privacy
Renderer/camera/pick/transform metadata stay outside cognition.
