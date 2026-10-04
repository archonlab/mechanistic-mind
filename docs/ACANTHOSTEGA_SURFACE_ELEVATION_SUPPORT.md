# Acanthostega Phase C — Surface Elevation Support V1

**Preset:** `ACANTHOSTEGA_PHASE_C_SURFACE_ELEVATION_SUPPORT`  
**Mechanism:** `surface_elevation_support`  
**Profile:** `SUBGRID_MICRORELIEF_RAMP_V1`  
**Parent:** `ACANTHOSTEGA_PHASE_C_FREE_OBJECT_GROUND_FRICTION`

## Contract

`surface_elevation` is physical support height. Every upward ΔU is paid from mechanical work (body) or normal kinetic energy (FREE), or the move is rejected. **No free snap. No free PE gain.**

- `physical_height_scale = 1.0`
- `physical_support_height = scale * raw_elevation`
- `microrelief_threshold = 0.12` (not `BODY_CONTACT_RADIUS`)
- Shared helper: `surface_support_height(world, x, y)` — raises if elevation active and value missing (no silent 0)

## Transitions (centre-path DDA)

| Kind | Condition | Effect |
|------|-----------|--------|
| LEVEL | \|Δh\| ≈ 0 | pass |
| MICRO_UPHILL | 0 < Δh ≤ threshold | pay W_climb; accept or block |
| LARGE_UPHILL | Δh > threshold | block (not climbable in V1) |
| MICRO_DOWNHILL | −threshold ≤ Δh < 0 | inelastic dissipate; land on new support |
| LARGE_DOWNHILL | Δh < −threshold | support lost; z remains; airborne; no snap |

## Energy

- Body: `W_climb = m_eff * g * Δh` from `mechanical_work_reservoir` debit-on-accept; `m_eff` includes held load.
- FREE: require `K_normal >= W_climb`; reduce `|v_n|`; else block. Rest never climbs.

## Friction order

source cell friction → proposal → elev transitions → commit → vertical

## Transfer

- Occupied support rise: `OCCUPIED_SUPPORT_RISE_REJECTED` (atomic)
- Ground lowered under entity: airborne; no snap down

## Receipts / UI

- Receipt: `SURFACE_ELEVATION_TRANSITION` (`agent_accessible=false`)
- Observer banner + Analyzer section
- One APPLY EXPERIMENT button; co-gated internal flags

## Not in V1

Continuous slopes, radius-face sweep, CLIMB action, stacking, excavation, 3D, lifecycle, Undercover.
