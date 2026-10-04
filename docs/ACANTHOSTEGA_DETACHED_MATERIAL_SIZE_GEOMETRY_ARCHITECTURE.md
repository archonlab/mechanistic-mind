# ACANTHOSTEGA_DETACHED_MATERIAL_SIZE_GEOMETRY_ARCHITECTURE

## Status

**Architecture audit only.** No runtime/frontend implementation in this task.

## Central question

What should determine the physical collision geometry of a detached material ResourceObject?

## Verdict

```text
VERDICT = READY_TO_IMPLEMENT
```

Fixed r=0.25 is a coherent **V1 abstraction** but is **not** scientifically acceptable forever: detached slice quantity ∈ ~[0.05, 0.25] while spawn qty=1 share the same collision disk, producing artificial crumb crowding. Contact/support/DTIP kernels already accept per-object radius; WMT creation hardcodes 0.25.

## Recommended next implementation slice

```text
RECOMMENDED_NEXT_SLICE = DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1
```

| Item | Recommendation |
|------|----------------|
| Preset | `ACANTHOSTEGA_BETA4_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS` |
| Parent | `ACANTHOSTEGA_BETA4_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT` |
| Mechanism | `detached_material_amount_scaled_collision_radius` |
| Profile | `DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1` |
| Radius authority | Serialized `collision_radius` after creation |
| Model | Bounded ref scaling: `r = clamp(r_ref * (quantity/quantity_ref)^(1/3), r_min, r_max)` |
| Amount | `quantity` (WMT volume proxy) |
| quantity_ref | 1.0 |
| r_ref | 0.25 |
| r_min | 0.08 |
| r_max | 0.25 |
| Scope | WMT detached terrain objects at creation only |
| Mutation | **NO** post-creation resize |
| Optical / interaction | Unchanged |
| Placement | K=16 unchanged (r_max≤0.25) |
| Snapshot | Serialize r; missing → 0.25 legacy |
| Cognition | No size labels |

## Why this order

```text
creation-time amount-scaled r (this slice)
→ later radius-aware placement if r_max must rise
→ later transactional COMBINE/deposition resize
→ optional free-space only if stacking/vertical free placement demanded
```

Free-space V1/V2 **not** required before variable size under r_max≤0.25.

Additional kernel notes (post-audit confirmation):
- Grasp XY uses **optical_radius**, not collision_radius.
- Body/held broad-phase reach uses **config default** collision radius — safe while r_max≤0.25; must widen if uncapped.
- Free-object friction ignores collision_radius (point support).
- `vertical_half_extent` does not auto-follow later radius mutation.

## Following roadmap seam

```text
FOLLOWING_ROADMAP_SEAM = COMBINE_DEPOSITION_TRANSACTIONAL_RADIUS_UPDATE_OR_RADIUS_AWARE_PLACEMENT_V2
```

Prefer transactional resize audit/implement only after creation-time scaling is validated; elevate placement V2 if uncapped growth is required.

## Evidence pack

`results/acanthostega_detached_material_size_geometry_architecture/`
