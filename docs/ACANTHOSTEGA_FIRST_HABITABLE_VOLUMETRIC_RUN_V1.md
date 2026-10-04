# Acanthostega First Habitable Volumetric Run V1

Integration habitability gate for public `ACANTHOSTEGA_BETA4`.

## Verdict

**A. FIRST_HABITABLE_PASS**

- PHYSICAL_HABITABILITY = `ESTABLISHED`
- AUTONOMOUS_TERRAIN_MANIPULATION = `NOT_OBSERVED`
- SCIENTIFIC_BEHAVIORAL_VALIDATION = `NOT_YET_COMPLETE`

## Budget

Total simulated ticks: 538 / 800

## O4 wiring repair (documented integration defect)

Observing body sphere was included in eye→terrain entity occlusion (`exclude_entity_id=None` for terrain),
forcing `OCCLUDED_ENTITY` and zero receptors. Repair excludes the observing body entity id from
`_eye_surface_visibility` occluders. No optical constants changed.

## Note

This is **not** Beta4 scientific closure or release validation.
Next safe seam: `BETA4_FEATURE_FREEZE_AND_PERFORMANCE_OPTIMIZATION_ARCHITECTURE`.
