# Acanthostega Beta 4 — Held Deposition Radius Shrink Transaction V1

## Identity

| Field | Value |
|-------|-------|
| Public preset | `ACANTHOSTEGA_BETA4_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION` |
| Parent | `ACANTHOSTEGA_BETA4_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION` |
| Mechanism | `held_deposition_radius_shrink_transaction` |
| Profile | `HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION_V1` |
| Receipt | `HELD_DEPOSITION_GEOMETRY_SHRINK` |

## Behavior

Extends existing WMT `plan_deposition` / `_commit_deposition` / `apply_explicit_surface_deposition`:

- **Eligible** stamped sources (`DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1`) on **partial** deposit: `r_after = derive(q_after)` via shared helper; base `z` retained; `vhe = r`; optical/grasp unchanged.
- **Full exhaustion**: remove object, free LEFT; no `r_min` survivor.
- **Ineligible**: deposit proceeds; radius fixed (`SOURCE_FIXED_GEOMETRY_NO_SHRINK`).
- **Energy**: `E_shrink = m_after·g·Δr` classified `SURVIVOR_GEOMETRY_DISSIPATED_NON_RECOVERABLE`; no agent credit; no global PE claim; no impulse/sound.
- **Conflict**: none required for shrink.
- **Spatial**: one reconcile on successful WMT commit (existing).

## Next seam

`FREE_GROUNDED_RESOURCE_OBJECT_RESIZE_OR_AMOUNT_RADIUS_CONTINUITY_AUDIT`
