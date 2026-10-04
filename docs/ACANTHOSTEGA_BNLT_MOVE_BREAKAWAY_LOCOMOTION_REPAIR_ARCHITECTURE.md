# ACANTHOSTEGA — BNLT MOVE BREAKAWAY LOCOMOTION REPAIR ARCHITECTURE

## Architecture decision

**READY_TO_IMPLEMENT** → **IMPLEMENTED** — minimal Option C: use capacity-limited realized MOVE impulse as `drive_accel` for force-aware kinetic residual under a new Beta 4 child preset. Do not weaken `μ_k`. Do not change Phase C / parent DTIP / Tiktaalik.

## Root cause (verified)

1. Static traction correctly **limits** transmitted MOVE impulse (`|J|≤μ_s N dt`).
2. BNLT kinetic correctly **may** oppose trial velocity during MOVE.
3. Existing force-aware residual rule requires `drive_accel > μ_k g` to keep leftover after friction exhausts trial speed.
4. Implementation sets `drive_accel = |v_trial|/dt` and never fills `move_impulse_xy` → when Gentle env absorb leaves `speed_trial ≤ μ_k g dt`, residual rule fails and MOVE is erased despite `|Δv_lim|=μ_s g > μ_k g`.

## Equations (repair ON)

```text
J_act = m_eff · Δv_lim          # after static capacity + affinity + work realize
drive_accel = |J_act| / (m_eff · dt) = |Δv_lim| / dt
a_k = μ_k · g                   # or projected N/m when slope ON
# coulomb_kinetic_step(v_trial, drive_accel=drive_accel):
#   if |v_trial| ≤ a_k·dt and drive_accel > a_k:
#        v_out = ((drive_accel - a_k)·dt) · v_trial/|v_trial|
#   elif |v_trial| ≤ a_k·dt:
#        v_out = 0
#   else: standard Coulomb scale
```

## Labels

| Item | Status |
|------|--------|
| Architecture decision | **DECIDED** |
| Implementation | **IMPLEMENTED** |
| Validation | **IMPLEMENTATION VALIDATED** (focused) |
| Scientific validation | **DEFERRED** |
| Repeated terrain slice | **DEFERRED** (next seam) |

## Isolation

| Preset | Behavior |
|--------|----------|
| Tiktaalik | unchanged |
| Phase C / G2A | unchanged (repair OFF) |
| Parent DTIP | unchanged (repair OFF) |
| New child | repair ON |

## Preset names

- `ACANTHOSTEGA_BETA4_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR`
- Parent: `ACANTHOSTEGA_BETA4_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT`
- Mechanism: `bnlt_move_breakaway_locomotion_repair`
- Profile: `BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR_V1`
