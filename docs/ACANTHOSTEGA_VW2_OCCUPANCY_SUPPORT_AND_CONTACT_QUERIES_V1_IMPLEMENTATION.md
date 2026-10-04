# VW2_OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES_V1 — Implementation result

**Date:** 2026-09-30  
**Schema:** `VW2_OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES_V1`  
**Capability:** `volumetric_world_support_contact_queries`  
**Authority:** `AUTHORITATIVE_SUPPORT_CONTACT_FROM_VOLUMETRIC_OCCUPANCY`

## Support/contact authority

VW2 is a **query/consumer layer** over VW1 `world.volumetric_occupancy`. It does not store intervals.

Vertical support for entity lower extent `z` (FGG: feet) selects the highest occupied interval top `z_max` with `z_max ≤ query_z + eps`. Upper material is never mistaken for support below. Free gaps yield lower-interval candidates, not legacy `max(z_max)`.

## Physical integrator migration

`support_z_for_entity(..., z=)` → when VW2 active **and** XY has a **sparse VW1 override column**, returns occupancy boundary (or `NO_SUPPORT_SENTINEL`).  
Ordinary PSC/CSG columns without sparse override keep `surface_support_height` (CSG bilinear / SES) for flat-terrain equivalence until VW3 mutates occupancy.

FGG `integrate_vertical_entity` passes `z=z0` into `support_z_for_entity`. Gravity / V1A PE mutex / V1B landing ownership unchanged.

## Contact vs support

`VerticalSupportContactResult`: `contact_exists`, `support_capable`, `boundary_z`, `clearance`, `penetration`, `relation`, `source_interval`, `legacy_projected_surface`, `contradicts_legacy_projected_surface`. Ceiling probe is provenance-only (no dynamic response).

## Observer

Selected-cell `occupancy_support_contact` inspector shows body `query_z`, VW2 boundary, legacy projected surface, contradiction flag, source interval. Passiveends VW1 column strip. Passive; tokens in `FORBIDDEN_TOKENS`.

## Remaining heightfield consumers (post-VW2)

- `surface_support_height` / CSG for non-override cells (SES climb DDA, PE path, effector clearance until later)
- Radius-aware ring classification still samples CSG heights (footprint helper `sample_footprint_vertical_support` available for occupancy)
- Horizontal SES transitions still use cell elevation samples

## Known limitations

- Ceiling/wall dynamic response not implemented
- Sparse-override gate for physical support (derived PSC columns unchanged for CSG parity)
- No VW3 separation / VW4 deposition

## Exact next seam

`VW3_CONSERVATIVE_VOLUMETRIC_SEPARATION_V1`
