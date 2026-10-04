# VW6_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE_V1 — Implementation result

**Date:** 2026-09-30  
**Schema:** `VW6_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE_V1`  
**Capability:** `minimal_volumetric_3d_visual_geometry`  
**Authority:** `AUTHORITATIVE_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE`

## Previous visual geometry

Near-field exteroception used **XY-only** Moore-neighborhood geometry:
- distance = `hypot(dx, dy)` (planar)
- FOV / sector occlusion in the horizontal plane
- no authoritative occupancy line-of-sight
- target Z was not part of visibility geometry

## VW6 geometry authority

When VW6 is ON (Acanthostega + VW1 occupancy):
1. **Eye / sensor origin** = body XY + `centre_z` (existing FGG anatomy; no new eyeballs).
2. **Target approximation** = cell centre XY + authoritative surface / entity Z (`CELL_CENTRE_XY_PLUS_AUTHORITATIVE_SURFACE_OR_ENTITY_Z`).
3. **Relative XYZ** = wrapped XY (`toroidal_delta`) + absolute Z (Z does not wrap).
4. **3D distance** = `norm(dx,dy,dz)` feeds existing attenuation laws / phenotype parameters.
5. **Vertical acceptance** = configurable half-angle (default ±90°). No organism pitch DOF invented; horizontal FOV / head orientation preserved.
6. **Occupancy LOS** = deterministic Amanatyan-style XY column traversal of the sight segment; per-column ray Z span vs VW1 `(z_min, z_max]` intervals.
7. **Endpoints** = open segment `(ε, 1−ε)` so observer origin and target endpoint do not false-occlude.
8. **Nearest blocker** = minimal `t`, then `(cell_x, cell_y, z_min)`.

## What VW6 does / does not

**Does:** geometry constrains physical visual exposure before phenotype/receptor → cognition (`exo_*` / surface / spatial floats only).

**Does not:** cave/tunnel/above/below semantics; omniscient Z to cognition; renderer/framebuffer vision; body or ResourceObject ray occlusion (world occupancy only); VW7 camera; VW4 physical reintegration trigger; light-field / shadows.

## Phenotype / cognition boundary

Physical visibility / occupancy occlusion gates exposure. Existing receptor limits (FOV, threshold, gain, saturation, distance_k) remain authoritative for organism access. Researcher receipts (`occupancy_los`, `eye_xyz`, blocker interval) are FORBIDDEN for cognition.

## VW3 / VW4 feedback

Visibility is re-queried from occupancy. VW3 removal can turn occluded→visible; VW4 insertion can turn visible→occluded. No stale visibility cache.

## Observer

Cell geometry inspector shows eye/target/relative XYZ, 3D distance, elevation, occupancy LOS CLEAR/OCCLUDED, blocker interval, legacy max-surface contradiction, phenotype boundary. PassivePassive.

## Snapshot

Vision geometry is derived from snapshot-authoritative occupancy + body pose. VW6 config serializes when ON. No separate occlusion cache.

## Performance

Local sparse column traversal only. No dense XYZ grid. No full scene renderer.

## Limitations

- Target geometry is a point/centre approximation (not meshes).
- No vertical eye musculature / pitch motor DOF.
- Bodies and ResourceObjects do not occlude rays in VW6 (world material only).
- Illumination assumptions of existing near-field contract preserved (not a light field).

## Next seam

`OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1` (architecture VW7) — **implemented**; see `docs/ACANTHOSTEGA_VW7_OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1_IMPLEMENTATION.md`.  
Further next: `FIRST_HABITABLE_VOLUMETRIC_RUN_V1`.
