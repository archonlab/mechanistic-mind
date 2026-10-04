# VW1_VOLUMETRIC_OCCUPANCY_AUTHORITY_V1 — Implementation result

**Date:** 2026-09-30  
**Schema:** `VW1_VOLUMETRIC_OCCUPANCY_AUTHORITY_V1`  
**Capability:** `volumetric_world_material_occupancy`  
**Authority:** `AUTHORITATIVE_WORLD_MATERIAL_OCCUPANCY_ABSOLUTE_Z`  
**Profile:** `SPARSE_ABSOLUTE_Z_OCCUPIED_INTERVALS_V1`

## What became authoritative

Sparse absolute-Z **occupied** intervals per wrapped XY cell, owned by
`world.volumetric_occupancy` (`VolumetricOccupancyState`).

- Free space = **complement** of occupied intervals (not a second stored authority).
- Explicit sparse overrides (cavities / multi-stack columns) live in `state.columns`.
- Ordinary heightfield cells without a sparse override: occupancy queries **derive**
  intervals from procedural surface columns (PSC) on read — compatibility path only.

## Interval semantics

`INTERVAL_ENDPOINT_SEMANTICS = HALF_OPEN_LOWER_EXCLUSIVE_UPPER_INCLUSIVE`

Occupied iff `z_min < z ≤ z_max` (tolerance `1e-12`).

Matches PSC depth `[top, bottom)` via `z = H - depth`.

Canonicalization: sort by `(z_min, z_max)`; reject overlaps and zero thickness;
merge abutting intervals only when density+composition+derivation match
(`merge_compatible_abutting=True`).

## Compatibility surface projection

`compatibility_surface_elevation(world, x, y)` / `derived_surface_elevation` =
`max(z_max)` of occupied intervals at XY.

**Pre-VW2 physics (SES/FGG/support/contact) still consume PSC `surface_elevation`.**
VW1 does **not** migrate support/contact. Sparse cavity columns may therefore
diverge from PSC heightfield until VW2/VW3; that is intentional for this slice.

**Authority direction**

1. Sparse occupancy column present → volumetric is sole occupancy authority for that XY.
2. Else → intervals derived from PSC (legacy geology still mutated by WMT/PSC until VW3).
3. Derived surface projection is never competing occupancy truth for Observer/VW1 queries.

**Removal seam:** VW2 consumes occupancy queries for support/contact; VW3 writes sparse
intervals on separation instead of heightfield-only layers.

## Snapshot

`VOLUMETRIC_OCCUPANCY_SNAPSHOT_V1` inside planet/world snapshot under
`volumetric_occupancy`. Hex float exact encode; columns sorted by `(cell_x, cell_y)`;
digest verified on restore. No Observer state.

## Observer

- World frame: `volumetric_occupancy` researcher payload.
- Selected-cell geometry: `volumetric_occupancy` column inspector (intervals + free gaps).
- UI: vertical strip in cell inspector; labels distinguish
  **AUTHORITATIVE VOLUMETRIC OCCUPANCY** vs **LEGACY / DERIVED SURFACE PROJECTION**.
- Passiveive: inspection does not mutate digest/history; tokens in `FORBIDDEN_TOKENS`.

## Known limitations

- Support/contact/landing/excavation **not** volumetric (VW2+).
- Dense global XYZ grid **not** used.
- PSC remains the mutation path for ordinary terrain until VW3.
- No living matter, caves-as-entities, 3D vision, audio change.

## Exact next seam

`VW2_OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES_V1`
