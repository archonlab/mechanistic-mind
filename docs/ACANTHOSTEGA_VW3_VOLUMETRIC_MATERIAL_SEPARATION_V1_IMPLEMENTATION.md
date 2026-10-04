# VW3_VOLUMETRIC_MATERIAL_SEPARATION_V1 — Implementation result

**Date:** 2026-09-30  
**Schema:** `VW3_VOLUMETRIC_MATERIAL_SEPARATION_V1`  
**Capability:** `volumetric_world_material_separation`  
**Authority:** `AUTHORITATIVE_VOLUMETRIC_MATERIAL_SEPARATION_VIA_WMT`

## Mutation authority

WMT remains the single material transaction authority.  
Operation kind: `SEPARATE_VOLUMETRIC_OCCUPANCY_INTERVAL`.  
Successful commit mutates VW1 `world.volumetric_occupancy` via `set_volumetric_column` **first** (authoritative), then appends a conserved `ResourceObject`.

Empty columns are stored as sparse overrides so PSC heightfield cannot reappear as occupancy truth after full removal.

## Interval subtraction

VW1 `(z_min, z_max]` preserved. Supports top / bottom / middle / full removal. Middle removal splits one interval into two with an internal free gap. Incompatible multi-material mixes in one removal batch are rejected.

## Conservation / provenance

Removed quantity/mass/composition (per-area × `CELL_AREA`) == ResourceObject payload.  
Provenance links `transaction_id`, source cell, absolute-Z removal range, before/after intervals, `object_id`.

## Compatibility projection

`derived_surface_elevation` / `compatibility_surface_elevation` remain derived from occupancy.  
PSC is **not** the separation source of truth for this path. Existing top-slice `SEPARATE_SURFACE_COLUMN_SLICE` path unchanged (legacy); VW3 researcher/test API is the volumetric path.

## Remaining heightfield consumers

Effector clearance, RASP ring heights, CSG bilinear on non-override cells — **not required** for VW3 researcher volumetric separation path; left for later seams.

## Observer

Cell geometry includes `volumetric_material_separation` receipt (before/removed/after, transaction, object_id). PassiveVW1 strip + VW2 support inspector continue to reflect post-mutation occupancy.

## Next seam

`VW4_CONSERVATIVE_VOLUMETRIC_DEPOSITION_REINTEGRATION_V1`
