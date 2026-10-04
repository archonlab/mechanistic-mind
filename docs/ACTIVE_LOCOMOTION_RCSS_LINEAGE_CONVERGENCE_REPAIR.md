# ACTIVE_LOCOMOTION_RCSS_LINEAGE_CONVERGENCE_REPAIR

## Status
**IMPLEMENTED** via **direct reparenting** (no convergence preset).

## Problem
ALTVSF was built as a sibling of RCSS under BNLT, so crowding could not inherit both.

## Repair
```text
BNLT → RCSS → ALTVSF → (future EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT_V1)
```

- Builder: `acanthostega_active_locomotion_traction_vs_sliding_friction_config()` now calls `acanthostega_repeated_conservative_surface_column_separation_config()`.
- Mechanism map: extends RCSS map, then sets `active_locomotion_traction_vs_sliding_friction=True`.
- Public preset name unchanged: `ACANTHOSTEGA_BETA4_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION`.
- RCSS parent unchanged (ALTVSF still OFF there).
- Force laws unchanged (ALTVSF / BNLT / RCSS physics).

## Future crowding parent
```text
PARENT_PRESET = ACANTHOSTEGA_BETA4_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
```

## Evidence
`results/active_locomotion_rcss_lineage_convergence_repair/`
