# AGENT_ACCESSIBLE_EFFECTOR_RELATIVE_Z_CONTROL_V1

**Implementation complete.** Independent ternary per-hand vertical motor factors
(`LEFT_Z` / `RIGHT_Z` ∈ {UP, NONE, DOWN}) travel through ordinary cognition →
`COMPOSITE_MOTOR_V1` → existing EBAE `request_actuated_relative_displacement`.

This is general manipulator motor control — **not** a semantic excavation action.

## Sign convention (code authority)

| Factor | Integer | Requested Δrelative_z | Physical tip |
|--------|---------|----------------------|--------------|
| UP | `+1` | `+max_delta_z_per_tick` (+0.1075) | tip rises (`ez = centre_z + relative_z`) |
| NONE | `0` | no request | holds current relative_z |
| DOWN | `−1` | `−max_delta_z_per_tick` | tip descends |

Bounds unchanged: `±DEFAULT_MAX_RELATIVE_Z = ±1.075`.

## Tokens

`LEFT_EFFECTOR_Z_UP`, `LEFT_EFFECTOR_Z_DOWN`, `RIGHT_EFFECTOR_Z_UP`, `RIGHT_EFFECTOR_Z_DOWN`

Gated when `mrwa_is_active ∧ ebae_is_active` (capability, not preset-name string).

## Pipeline

```
observation → factorized side-channel pick (OSC-style)
→ CompositeMotorOutput.effector_z_{left,right}
→ finish_tick after resolve_shared_world_manipulators
→ request_actuated_relative_displacement (EBAE)
→ tip pose → ETC / VW5 / SETMR consequences
```

## Motor identity

SMC signature extended: `…|P:{push}|ZL:{d}|ZR:{d}`

## Model boundary

- Acanthostega Beta 4.0: ON  
- Tiktaalik Beta 3.1: OFF (frozen)  
- Public selector unchanged (exactly two models)  
- No new public preset

## Proprioception

**Not added in V1.** Open-loop factors only; numeric relative_z is researcher/Observer only.

## Evidence

`results/agent_accessible_effector_relative_z_control_v1/`

## Next safe seam

`FIRST_HABITABLE_VOLUMETRIC_RUN_V1` (do not begin in this task).
