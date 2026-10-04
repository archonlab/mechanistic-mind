# ACANTHOSTEGA — REPEATED CONSERVATIVE SURFACE-COLUMN SEPARATION V1

## Status
**IMPLEMENTED** (implementation validation only; scientific validation deferred).

## Preset
- `ACANTHOSTEGA_BETA4_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION`
- Parent: `ACANTHOSTEGA_BETA4_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR`
- Mechanism: `repeated_conservative_surface_column_separation`
- Profile: `REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION_V1`

## Policies
| Topic | Value |
|-------|-------|
| Cell/tick cap | 1 successful commit / cell / tick |
| First-wins | `STABLE_SORT_FIRST_WINS_CELL_TICK_CAP` |
| Commit | `SEQUENTIAL_AGAINST_UPDATED_AUTHORITATIVE_STATE` |
| Accumulator | clear on commit; keep on WMT reject |
| Surplus | clear on commit |
| Resistance | current top layer |
| Support | immediate re-eval; no free lift |
| Deposits | NOT_ESTABLISHED |

## Non-goals
No DIG/MINE; no second removal path; no volumetric free-space V1–V5; no deposit excavation.

## Evidence
`results/acanthostega_repeated_conservative_surface_column_separation_v1/`

## Next seam
`LOCAL_DETACHED_OBJECT_CROWDING_AND_PLACEMENT_RETRY_ARCHITECTURE`
