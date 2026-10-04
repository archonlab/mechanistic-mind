# ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION_ARCHITECTURE

## Status

**Architecture audit only.** `IMPLEMENTATION_STARTED = NO`. No runtime, test, preset, frontend, or `web_dist` edits in this task.

## Freshness

| Field | Value |
|-------|-------|
| Absolute cwd | `<repository-root>` |
| Branch | `main` |
| HEAD | `5d0f14cd7968b4d5b190796a2494d348a0e10f48` |
| Dirty paths (approx) | ~280 |
| Destructive git ops | **NONE** |
| Live Observer mutated | **NO** |

## Verified cumulative tip

```text
BNLT → RCSS → ALTVSF → EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
  → DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
  → HELD_COMBINE_RADIUS_RESIZE_TRANSACTION   ← current tip (implemented)
  → (this audit) HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
```

Confirmed from `preset_canonical(...)`: parent of COMBINE-resize tip is creation-size; mechanism `held_combine_radius_resize_transaction` active; `DEPOSITION_RESIZES_OBJECT = NO` today.

Size law (shared helper, unchanged by this audit):

```text
r(q) = clamp(0.25 × (q / 1.0)^(1/3), 0.08, 0.25)
```

## Central question

When `APPLY_TO_SURFACE` removes quantity from an eligible held ResourceObject, how should collision radius / vertical geometry shrink **transactionally** without free energy, invalid placement, hidden impulses, broken grasp, or partial state?

## Verdict

```text
VERDICT = READY_TO_IMPLEMENT
RECOMMENDED_NEXT_SLICE = HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION_V1
PLAN_COMMIT_REFACTOR_REQUIRED = NO
FREE_SPACE_V1_REQUIRED_NOW = NO
FREE_SPACE_V2_REQUIRED_NOW = NO
BLOCKER = NONE
```

Held deposition shrink fits inside the existing WMT `plan_deposition` → `_commit_deposition` path with a **minimal COMBINE-resize-style extension** (pure geometry admit on plan; radius/vhe mutate on successful partial commit only). Full exhaustion already removes the source — do **not** fabricate `r_min` for zero quantity.

Prior post-creation audit deferred shrink because released PE lacked a work-debit sink. This audit resolves that by classifying shrink PE as **dissipated / non-recoverable / no agent credit**, and by **not claiming global PE conservation** across deposit destinations (deposits are not elevated collision bodies).

## Recommended implementation identity

| Item | Value |
|------|-------|
| Public preset | `ACANTHOSTEGA_BETA4_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION` |
| Parent | `ACANTHOSTEGA_BETA4_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION` |
| Mechanism | `held_deposition_radius_shrink_transaction` |
| Profile | `HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION_V1` |
| Receipt family | `HELD_DEPOSITION_GEOMETRY_SHRINK` |

## Selected policies (summary)

| Decision | Selection |
|----------|-----------|
| Eligibility | Source stamp `DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1` only |
| Partial radius | `r_after = derive(q_after)` from planned conservation-checked transfer |
| Full exhaustion | Remove object; free LEFT; **no** survivor geometry |
| Anchor | `HELD_BASE_FEET_SNAP_RETAINED` (`z` unchanged; centre falls by Δr) |
| Shrink PE | `m_after·g·(r_before−r_after)` recorded as `DISSIPATED_NON_RECOVERABLE`; **not** credited to agent |
| Conflict admit | **Not required** for shrink (radius decrease); not a penetration solver |
| Impulse / sound | **NO** |
| Optical / grasp | **Unchanged** |
| Spatial reconcile | Exactly **one** on successful WMT commit (existing `_sync_spatial_index`) |
| Free-space | Not required |

## Following roadmap seam

```text
FOLLOWING_ROADMAP_SEAM = FREE_GROUNDED_RESOURCE_OBJECT_RESIZE_OR_AMOUNT_RADIUS_CONTINUITY_AUDIT
```

(or held-only polish / deposition work accounting if energy semantics expand later — **not** free-space V1/V2)

## Explicit non-goals

No free-grounded resize; no legacy migration; no deposit collision disks; no deposit elevation; no resize impulse/sound; no agent PE credit; no heat/kinetic channel; no stacking; no free-space; no cognition changes; no Tiktaalik/Phase C/prior Beta4 preset mutation.

## Evidence pack

`results/acanthostega_held_deposition_radius_shrink_transaction_architecture/`
