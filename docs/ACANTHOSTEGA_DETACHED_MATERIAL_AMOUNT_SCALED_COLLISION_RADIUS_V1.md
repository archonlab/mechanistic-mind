# ACANTHOSTEGA_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1

## Status

**Implemented.** Creation-time quantity∛ collision radius for SEPARATE_SURFACE_COLUMN_SLICE ResourceObjects under the new Beta 4 child preset only.

## Identity

| Field | Value |
|-------|-------|
| Preset | `ACANTHOSTEGA_BETA4_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS` |
| Parent | `ACANTHOSTEGA_BETA4_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT` |
| Mechanism | `detached_material_amount_scaled_collision_radius` |
| Profile | `DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1` |
| Receipt family | `DETACHED_MATERIAL_SIZE_GEOMETRY` |
| Geometry model | `BOUNDED_QUANTITY_CBRT_REF_SCALING_DETACHED_CREATION_ONLY` |
| Radius authority | Serialized `collision_radius` after creation |

## Formula

```text
r_raw = 0.25 * (quantity / 1.0)^(1/3)
collision_radius = clamp(r_raw, 0.08, 0.25)
```

Amount authority = `quantity` (not mass). Optical / grasp / interaction radii unchanged.

## Creation order

```text
plan slice → final quantity → derive radius → DTIP with derived radius
→ commit column + object (r + vertical_half_extent stamped) OR reject atomically
```

## Non-goals (this slice)

- No post-creation resize (COMBINE / deposition / ticks)
- No K=16 redesign; no far-SW candidate
- No density material property
- No optical radius change; no glyph-as-physics
- No free-space V1/V2; no stacking

## Following seam

```text
POST_CREATION_RESOURCE_OBJECT_RESIZE_TRANSACTION_ARCHITECTURE
```

## Evidence

`results/acanthostega_detached_material_amount_scaled_collision_radius_v1/`
