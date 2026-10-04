# Acanthostega Beta 4 — Held COMBINE Radius Resize Transaction V1

## Identity

| Field | Value |
|-------|-------|
| Public preset | `ACANTHOSTEGA_BETA4_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION` |
| Parent | `ACANTHOSTEGA_BETA4_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS` |
| Mechanism | `held_combine_radius_resize_transaction` |
| Profile | `HELD_COMBINE_RADIUS_RESIZE_TRANSACTION_V1` |
| Receipt family | `HELD_COMBINE_GEOMETRY_RESIZE` |
| Model line | `ACANTHOSTEGA` |

## Scope

Extends explicit held-object COMBINE with atomic geometry admission and creation-profile radius growth for **profile-stamped survivors only**.

Does **not**:
- resize on deposition
- resize free grounded / legacy / preset-spawned objects
- change radius formula or raise `r_max`
- change optical radius or grasp reach
- auto-release, teleport, impact sound, free-space V1/V2
- modify Tiktaalik / Phase C / prior Beta 4 presets

## Eligibility

Survivor resizes only when `provenance.size_geometry_profile == DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1`.
Left survivor policy wins; right source profile never overrides.

## Geometry

```text
r_proposed = clamp(0.25 * quantity_after^(1/3), 0.08, 0.25)
z_after = z_before                    # held base/feet retained
vertical_half_extent_after = r_proposed
centre_z_after = z_before + r_proposed
```

Growth-only. Unexpected shrink → `REJECTED_UNEXPECTED_SHRINK` (entire COMBINE).
No-change (`|Δr| ≤ 1e-12`) → existing COMBINE, no PE debit.

## Work

```text
required_resize_work = max(0, m_after * g * Δr)
```

`g` from active flat-ground gravity authority. Debit from `body.mechanical_work_reservoir` exactly once on successful commit. Insufficient work → atomic reject, no merge.

## Conflict

Baseline-vs-proposed penetration (`OVERLAP_MARGIN=0.95`, `PENETRATION_EPS=1e-9`) against holder, foreign bodies, experimenter, terrain, other objects (right source excluded). Any worsened overlap → reject entire COMBINE.

## Commit order

```text
plan (side-effect-free admit)
→ validate stale preconditions
→ merge mass/quantity/components/optical
→ set radius/vhe + debit work
→ remove right + free right hand
→ spatial reconcile once
→ publish receipts
```

## Next seam

`HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION_ARCHITECTURE` (not implemented here).
