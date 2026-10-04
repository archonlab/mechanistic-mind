# ACANTHOSTEGA_FREE_RESOURCE_OBJECT_AMOUNT_RADIUS_CONTINUITY_ARCHITECTURE

## Status

**Architecture audit only.** `IMPLEMENTATION_STARTED = NO`. No runtime, preset, test, frontend, or `web_dist` edits.

## Freshness

| Field | Value |
|-------|-------|
| cwd | `<repository-root>` |
| Branch | `main` |
| HEAD | `5d0f14cd7968b4d5b190796a2494d348a0e10f48` |
| Dirty paths | ~285 (preserved) |
| Destructive git | **NONE** |
| Live Observer | **NOT MUTATED** |

## Verified cumulative tip

```text
BNLT → RCSS → ALTVSF → EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
  → DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
  → HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
  → HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION   ← current tip
```

Size profile: `DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1`  
Law: `r(q) = clamp(0.25 × q^(1/3), 0.08, 0.25)` via shared `derive_detached_material_collision_radius`  
Serialized `collision_radius` is restore authority (no recompute from quantity).

## Central finding

**While a ResourceObject remains FREE, no production path mutates its quantity, mass, or composition.**

Material mutations that change amount (COMBINE, APPLY_TO_SURFACE) require **HELD** objects and already have transaction-local geometry contracts on the tip for stamped objects.

Therefore:

| Question | Answer |
|----------|--------|
| Free stamped amount–radius mismatch currently reachable? | **NO** (without snapshot/test corruption) |
| Free unstamped “qty ≠ ∛(r)” after COMBINE→RELEASE? | **YES**, but **by design** (fixed-geometry policy) |
| Free-Space V1 required now for amount–radius continuity? | **NO** |
| Implement free grounded resize now? | **NO — DEFER** |

## Verdict

```text
VERDICT = DEFER
RECOMMENDED_NEXT_SLICE = NONE_FOR_FREE_OBJECT_RESIZE
  (or domain work elsewhere; free resize waits for a real free material-mutation)
RECOMMENDED_INVARIANT_MODEL = OPTION_A_TRANSACTION_LOCAL_GEOMETRY
SHARED_MATERIAL_GEOMETRY_TRANSACTION_SEAM_REQUIRED = NO_NOW
  (optional later when a second free mutation appears)
FREE_SPACE_V1_REQUIRED_NOW = NO
BLOCKER = NONE_FOR_CONTINUITY_CLAIM
  (blocker for free resize = NO_CURRENT_FREE_QUANTITY_MUTATION)
```

## Stamp interpretation

`size_geometry_profile` is **creation provenance + eligibility for transaction-local resize**, not a continuous global enforcer. Continuity is maintained by each authorized material transaction that changes quantity (creation, held COMBINE, held deposition). Periodical repair (Option C) is rejected.

## Following roadmap seam

```text
FOLLOWING_ROADMAP_SEAM =
  WAIT_FOR_FREE_MATERIAL_MUTATION_OR_OTHER_BETA4_DOMAIN
  | FREE_SPACE_V1_WHEN_UNSUPPORTED_VERTICAL_CONSEQUENCES_REQUIRED
```

Do **not** promote Free-Space V1 solely for amount–radius continuity.

## Evidence pack

`results/acanthostega_free_resource_object_amount_radius_continuity_architecture/`
