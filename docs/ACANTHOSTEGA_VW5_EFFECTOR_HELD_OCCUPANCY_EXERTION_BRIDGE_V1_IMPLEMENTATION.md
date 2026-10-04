# VW5_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE_V1 — Implementation result

**Date:** 2026-09-30  
**Schema:** `VW5_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE_V1`  
**Capability:** `organism_physical_interaction_with_volumetric_world`  
**Authority:** `AUTHORITATIVE_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE`

## Previous heightfield assumptions

Effector clearance / tip nonpenetration used `sample_terrain_at` → CSG/SES **max** surface `h(x,y)`:
`clearance = z − r − h`. Surface exertion selected **PSC top layer** and failed into `SEPARATE_SURFACE_COLUMN_SLICE`.

## Migrated occupancy-aware geometry

When VW5 is ON:
- Probe clearance/contact uses VW1 occupancy **floor-below** at tip elevation (not max surface).
- Deterministic selection: inside-interval → that interval; else greatest `z_max ≤ z_eff` (tie-break: lowest `z_min`, density desc, composition id).
- Legacy compatibility surface is recorded for contradiction display only.

## Work / failure / VW3

Existing `surface_exertion_terrain_material_resistance` preserved.  
Material/resistance comes from the **contacted occupancy interval**.  
On failure, VW5 routes to **VW3** `apply_volumetric_material_separation` (top of contacted interval by requested thickness).  
VW5 never subtracts occupancy itself.

## Held object / VW4 reintegration

Held ResourceObject pose can be related to occupancy (`held_object_occupancy_contact`).  
**VW4 physical trigger: BLOCKED.**  
`APPLY_TO_SURFACE` writes surface-deposit overlay; mere contact/RELEASE do not scientifically distinguish rest from world-material incorporation.  
No semantic PLACE invented.

## Observer

Cell geometry includes VW5 inspector: clearance, boundary, contacted interval, legacy contradiction, VW3 link, reintegration blocker. PassivePassive.

## Next seam

If closing held→world is highest priority: a narrowly scoped physical deposition-into-occupancy event (distinct from overlay APPLY_TO_SURFACE).  
Otherwise architecture major seam: `VW6_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE_V1`.
