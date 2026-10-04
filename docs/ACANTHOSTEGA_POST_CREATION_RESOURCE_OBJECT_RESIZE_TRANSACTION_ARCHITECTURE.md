# ACANTHOSTEGA_POST_CREATION_RESOURCE_OBJECT_RESIZE_TRANSACTION_ARCHITECTURE

## Status

**Architecture audit only.** No runtime/frontend implementation in this task.

## Central question

How can a ResourceObject change collision geometry after creation without violating conservation, identity, atomicity, exclusion, support, held constraints, energy, replay, snapshot, and preset isolation?

## Verdict

```text
VERDICT = READY_TO_IMPLEMENT
```

Post-creation resize is scientifically coherent as an **explicit held COMBINE geometry admission** inside the existing WMT plan/commit path. Creation-time size child remains creation-only. Deposition shrink and free-grounded resize are deferred (PE dump / support harder). Free-space V1/V2 **not** required while `r_max≤0.25` and resize is held-only.

## Current debt (proven)

COMBINE and APPLY_TO_SURFACE mutate quantity/mass/components but **never** `collision_radius` / `vertical_half_extent`. WMT-scaled crumbs therefore accumulate **amount–radius inconsistency**.

Zero-tick formula probes (same profile):

| Event | qty path | Δr |
|-------|----------|-----|
| COMBINE crumbs | 0.05+0.05 → 0.10 | ~0.092 → ~0.116 (**real growth**) |
| COMBINE near-ref | 1.0+1.0 → 2.0 | 0.25 → 0.25 (**clamp no-op**) |
| Deposit | 0.25 → 0.15 | ~0.157 → ~0.133 (**real shrink**) |

## Recommended next implementation slice

```text
RECOMMENDED_NEXT_SLICE = HELD_COMBINE_RADIUS_RESIZE_TRANSACTION_V1
```

| Item | Recommendation |
|------|----------------|
| Preset | `ACANTHOSTEGA_BETA4_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION` |
| Parent | `ACANTHOSTEGA_BETA4_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS` |
| Mechanism | `held_combine_radius_resize_transaction` |
| Profile | `HELD_COMBINE_RADIUS_RESIZE_TRANSACTION_V1` |
| Scope | Explicit COMBINE only; both objects held; left survives |
| Eligibility | Survivor must carry creation size-geometry profile stamp; legacy/preset-spawned stay fixed |
| Formula | Same: `clamp(0.25×qty^(1/3), 0.08, 0.25)` on **combined** quantity |
| Anchor | Held base/feet: `object.z` remains holder snap; `vertical_half_extent ← new_r`; `centre_z = z + new_r` |
| Growth PE | Debit `ΔPE = m·g·Δr` (g from Phase C uniform gravity) from actor work / reject if insufficient |
| Conflict | Atomic reject entire COMBINE (no partial merge) on holder/body/object/terrain XY overlap |
| Shrink | Out of scope (deposition deferred) |
| Optical/grasp | Unchanged |
| Sound/impulse | No resize-created impact sound; no automatic impulse from geometry alone |
| Snapshot | Serialize committed r + vhe + resize provenance; restore does not replan |
| Free-space | Not required now |

## Why COMBINE before deposition shrink

1. Existing `plan_combine` → `commit_material_transaction` atomicity with staged copies + rollback-by-reject.
2. Crumb COMBINE produces **non-zero** Δr under current caps (not a no-op).
3. Growth PE has a clear **work-debit** sink; shrink PE dump lacks an established dissipation ledger.
4. Deposition exhaustion/removal is a separate identity hazard.

## Following roadmap seam

```text
FOLLOWING_ROADMAP_SEAM = HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION_V1
```

(or PE-dissipation foundation if shrink energy blocks first)

## Explicit exclusions

No free-grounded resize; no stacking; no free-space; no optical/grasp change; no automatic pose search; no silent clamp-to-fit; no legacy migration.

## Evidence

`results/acanthostega_post_creation_resource_object_resize_transaction_architecture/`
