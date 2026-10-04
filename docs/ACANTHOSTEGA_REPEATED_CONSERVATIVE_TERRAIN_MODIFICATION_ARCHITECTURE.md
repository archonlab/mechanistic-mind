# ACANTHOSTEGA — REPEATED CONSERVATIVE TERRAIN MODIFICATION ARCHITECTURE

Architecture audit only. No physics, preset, or runtime implementation in this document’s companion task.

## Central question

Can the existing Acanthostega Beta 4 chain safely modify the **same** terrain region repeatedly, and **adjacent** regions, while preserving conservation, deterministic geometry, atomic WMT, meaningful work accumulation, placement integrity, snapshot/restore, and isolation from Tiktaalik / Phase C / earlier Beta 4 presets?

## Verdict summary

| Claim | Result |
|-------|--------|
| Same-column repeat currently possible | **YES** |
| Same-column repeat currently fully safe | **NO** (missing cell/tick gate; surplus carry across material change; placement crowding soft-stops deep peels) |
| Adjacent modification possible | **YES** (independent columns; bilinear ramps authoritative) |
| N-transaction conservation | **HOLDS** under current WMT (qty/mass/components) |
| Implementation of new excavation semantics | **FORBIDDEN** — no DIG/MINE/… |
| Recommended next slice | `REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION_V1` (policy/contract + gates; reuse existing WMT/DTIP) |
| Overall | **READY_TO_IMPLEMENT** |

## Philosophical constraint

Repeated terrain change must emerge from contact + bounded work + resistance + conservative transfer + persistent sparse geometry — never from a named excavation mechanic.

## Current capability (established in code + 0-tick probes)

1. `SEPARATE_SURFACE_COLUMN_SLICE` may be committed repeatedly on one cell; each commit replaces the single sparse delta and increments `revision`.
2. Second and later slices read the post-mutation top via `resolved_column_at`.
3. SETMR recomputes `separation_work_per_quantity` from the current top layer each consume.
4. One SETMR consume performs at most one separation; residual policy is `REMAIN_ACCUMULATED_AT_CELL`.
5. Multiple same-tick WMT commits on one cell are currently allowed.
6. Failed placement rejects the whole WMT (no terrain mutation, no id consume) and keeps SETMR accumulation.
7. Occupants: `apply_ground_lowered_to_occupants` → airborne, z unchanged, no free lift.
8. Deposits are **not** coupled to column separation (**NOT ESTABLISHED** coupling).
9. Snapshot/restore via `PhysicalSystemRuntime.restore` preserves deltas and permits further seps.
10. Tiktaalik / Phase C / prior presets unchanged by this audit (docs only).

## Defects / ambiguities for V1 to close

1. **No** `MAX_SUCCESSFUL_SEPARATIONS_PER_CELL_PER_TICK` enforcement.
2. Surplus residual after commit can fund later slices and **crosses material identity** without explicit policy.
3. Local newborn crowding can reject further seps before depth floor.
4. Deposit ↔ excavation interaction undefined (leave uncoupled).
5. Multi-agent same-cell ordering not formally specified (dictionary/call order today).

## Authoritative column model

Procedural baseline + **one sparse delta per cell** (cumulative top lowering / replaced layers). Not multi-interval scar lists. Depth floor `minimum_resolved_depth`; cross-layer `STOP_AT_TOP_LAYER_BOUNDARY_CLAMP_V1`.

## Recommended V1 policies

| Topic | Policy |
|-------|--------|
| Accumulator | `CLEAR_ACCUMULATOR_ON_COMMITTED_SEPARATION_V1`; keep on WMT reject |
| Resistance refresh | `FROM_CURRENT_TOP_LAYER` every attempt |
| Surplus | Cleared on commit; not transferred to newly exposed face |
| Cell/tick | Exactly one successful sep per source cell per scientific tick |
| Commit order | Sequential against updated authoritative state; stable sort `(cell, body_id, effector_id)` |
| Support | Immediate re-eval; airborne; no free lift; no sound from refresh |
| Placement | Reuse DTIP K=16; reject ⇒ no mutation / no id |
| Deposits | No coupling |
| Isolation | Child preset only; legacy snapshots retain prior semantics |

## Isolation

Do not globally change WMT/SETMR defaults for earlier presets. New gates live behind:

`ACANTHOSTEGA_BETA4_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION`

Parent: `ACANTHOSTEGA_BETA4_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT`.

## Following roadmap seam (after V1)

`LOCAL_DETACHED_OBJECT_CROWDING_AND_PLACEMENT_RETRY_ARCHITECTURE`

Not gravity, volumetric voxels, hydrology, ecology, or lifecycle.

## Evidence pack

`results/acanthostega_repeated_conservative_terrain_modification_architecture/`
