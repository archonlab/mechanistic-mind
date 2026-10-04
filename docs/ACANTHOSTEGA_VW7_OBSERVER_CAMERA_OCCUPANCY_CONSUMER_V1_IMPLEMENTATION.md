# OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1 — Implementation result

**Date:** 2026-09-30  
**Schema:** `OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1`  
**Capability:** `researcher_3d_camera_over_authoritative_volumetric_world`  
**Authority:** `RESEARCHER_CAMERA_OVER_AUTHORITATIVE_VOLUMETRIC_OCCUPANCY`

## Render authority boundary

Simulation physical state → passive render description → Canvas 2D researcher camera → pixels.

Renderer never writes physics, occupancy, body pose, ResourceObject pose, support, vision, or WMT.

## Occupancy → render description

Sparse VW1 columns only (`world.volumetric_occupancy`).  
One `OCCUPIED_INTERVAL_PRISM` per `(z_min, z_max]` interval.  
Free gaps = absence of geometry (no CaveEntity).  
Authoritative empty sparse column → no volume (beats PSC).  
Compatibility heightfield is **not** volume authority.

## Bodies / ResourceObjects

Authoritative `centre_z` (FGG) + extent. No surface snap. Held objects use authoritative held pose fields.

## Coordinate transform

| Renderer | Simulation |
|----------|------------|
| X | X |
| Y (up) | Z |
| Z (depth) | Y |

Canonical XY tile; physical topology remains WRAP_PERIODIC. Z absolute, shared.

## Camera / lighting

Orbit / pan / zoom on VOLUME / 3D workspace. Researcher-only.  
`OBSERVER_RENDER_LIGHTING_ONLY` (Canvas fill/stroke) — zero effect on VW6 / physics.

## Live VW3 / VW4

Render description re-derived from occupancy after mutation. No DIG/BUILD visual hooks.

## Passivity / old sessions

Camera movement is UI-only. Missing VW1 → `available: false` (no fabricated volume). 2D MAP view preserved.

## Next seam

`FIRST_HABITABLE_VOLUMETRIC_RUN_V1`
