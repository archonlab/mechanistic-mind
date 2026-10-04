# ACANTHOSTEGA · ABSTRACT SPECTRAL LIGHT SOURCE AND DIRECT TRANSPORT V1 (O3)

## Identity
- Schema: `ABSTRACT_SPECTRAL_LIGHT_SOURCE_AND_DIRECT_TRANSPORT_V1`
- Capability: `abstract_spectral_light_source_and_direct_transport`
- Profile: `DIRECT_OCCUPANCY_OCCLUDED_ANONYMOUS_SPECTRAL_LIGHT_O3_V1`
- Authority: `PHYSICAL_ABSTRACT_NON_SI_DIRECT_LIGHT_FIELD`
- Module: `mechanistic_mind/physical_system/abstract_spectral_light_source_and_direct_transport.py`

## Purpose
First authoritative physical-light state for Acanthostega Beta 4:
directional abstract non-SI six-band source → free-space direct transport with VW1 occupancy occlusion → incident spectrum on O2 facets → O1 reflectance → `reflected_spectral_exitance_proxy`.

Does **not** feed organism receptors, `exo_*`, cognition, SAV/audio, or display RGB authority.

## Source V1
- ID: `abstract_directional_source_0`
- Type: global directional
- Direction convention: `DIRECTION_TOWARD_SOURCE_UNIT` (unit vector from surface toward source)
- Spectrum: six anonymous nonnegative abstract bands (`optical_band_0`…`optical_band_5`)
- No distance attenuation; no hidden ambient; no explicit diffuse environment in V1
- Static configuration in V1 (mutable only via config/snapshot)

## Facet law
```
cosine = max(0, dot(outward_normal, direction_toward_source))
incident[b] = source_spectrum[b] * cosine   # if visible
reflected_spectral_exitance_proxy[b] = incident[b] * O1_R[b]
```
Unknown material → `UNKNOWN_MATERIAL_RESPONSE` with geometry/visibility still reported; no fabricated reflectance.

## Occlusion
Shared primitives: `traverse_xy_columns` + `occupied_intervals_at`.
Kernel: `directional_occupancy_occlusion` (not VW6 eye→target LOS; endpoint-skip semantics unsuitable for same-column blockers).
VW6 vision numerics unchanged.
Ray origin = facet centre + ε·normal; owning interval does not self-occlude; XY periodic; Z absolute.

## State classes
`DIRECT_ILLUMINATED` · `BACK_FACING_ZERO` · `OCCLUDED_ZERO` · `SOURCE_DISABLED_ZERO` · `UNKNOWN_MATERIAL_RESPONSE` · `NOT_EVALUATED` · `INVALID_GEOMETRY`

## Scope
Terrain O2 facets fully supported. Object/body/held optical surfaces: **deferred** — `OBJECT_BODY_OPTICAL_SURFACES_REQUIRED_BEFORE_O4`.

## Public model
Cumulative in `ACANTHOSTEGA_BETA4`. Behaviorally dormant for organisms until O4. Tiktaalik unchanged. Selector remains two public models.

## Observer / Analyzer
Researcher O3 audit panel; Analyzer causal reconstruction (no “organism saw” language).

## Next seam
O4 organism optical reception (after object/body optical surfaces prerequisite).
