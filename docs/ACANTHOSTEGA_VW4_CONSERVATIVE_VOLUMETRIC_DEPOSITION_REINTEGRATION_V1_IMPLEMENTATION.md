# VW4_CONSERVATIVE_VOLUMETRIC_DEPOSITION_REINTEGRATION_V1 — Implementation result

**Date:** 2026-09-30  
**Schema:** `VW4_CONSERVATIVE_VOLUMETRIC_DEPOSITION_REINTEGRATION_V1`  
**Capability:** `conservative_volumetric_material_reintegration`  
**Authority:** `AUTHORITATIVE_VOLUMETRIC_MATERIAL_REINTEGRATION_VIA_WMT`

## Mutation authority

WMT remains the single material transaction authority.  
Operation kind: `REINTEGRATE_VOLUMETRIC_OCCUPANCY_INTERVAL`.  
Successful commit mutates VW1 `world.volumetric_occupancy` via `set_volumetric_column` **first** (authoritative destination), then fully consumes the source `ResourceObject`.

## Insertion semantics

Destination is a bounded absolute-Z free region `(z_lo, z_hi]` at one XY cell (WORLD_XY wrap).  
Overlap with any occupied interval → atomic reject (no overwrite, no clip, no compaction).  
After insert, intervals are canonicalized with VW1 `merge_compatible_abutting` (exact density + composition equality).

Supported topologies: empty column, top/bottom adjacency, partial/complete internal gap fill, isolated free-space insertion (not heightfield growth).

## ResourceObject consumption

**Full reintegration only** in this slice: source `quantity` must equal destination thickness × `CELL_AREA`.  
On commit the object is removed from `world.resource_objects`.  
Partial consumption: `NOT_IMPLEMENTED` (rejected with explicit reason).

## Conservation / provenance

`source_before = world_added + source_after` with `source_after = 0` for full reintegration.  
Composition (absolute → per-area) and density (`mass/quantity`) preserved into the inserted interval.  
Provenance records VW4 transaction plus prior object provenance (VW3 separation ids when present).

## Compatibility projection

`derived_surface_elevation` / PSC projection remain derived from occupancy.  
PSC is **not** the deposition destination. Internal free space survives partial fills.

## Legacy deposition

`APPLY_TO_SURFACE` / `explicit_surface_deposition` remains a separate held-object overlay path (surface deposits). It is **not** competing VW4 destination truth. Migration of that effector path onto VW4 is **VW5**.

## VW2 support

Deposited matter is immediately queryable via occupancy floor-below / VW2 support. No semantic `set_supported`.

## Observer

Cell geometry includes `volumetric_material_reintegration` receipt (before / deposited / after, source object, consumption, WMT id, provenance, legacy projection label). PassiveVW1 strip + VW2 inspector update from occupancy. Passive inspection only.

## Known limitations

- Partial source consumption not implemented.
- Multi-column deposition not implemented (single-column primitive).
- VW1 exact-composition merge may leave abutting thickness-scaled remnants as multiple intervals after gap fill; physical occupancy coverage is still continuous.
- Organism effector/held trigger not wired (VW5).

## Remaining heightfield consumers

Effector clearance, RASP ring heights, CSG bilinear on non-override cells — unchanged; deferred to later seams unless narrowly required.

## Next seam

`VW5_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE_V1`
