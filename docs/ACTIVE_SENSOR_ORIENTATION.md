# Active Sensor Orientation (Articulated Head)

Physical neck DOF for Mechanistic Mind / Tiktaalik. Not gaze control.

## What the agent can physically do

When `articulated_head.mode = EXPERIMENTAL`:

- Motor actions: `NECK_LEFT`, `NECK_RIGHT`, `NECK_HOLD`
- Under **COMPOSITE_MOTOR_V1**, neck is one domain of a structured motor output
  and may be commanded in the **same tick** as locomotion / oscillator / PUSH
  (see `docs/COMPOSITE_MOTOR_CONTROL.md`). Absence of neck command = torque 0;
  head angle/ω continue under ordinary neck physics (no repeated NECK required).
- Motors produce torque on `head_relative_angle` (bounded, damped)
- Vision FOV uses `head_world_heading = body_theta + head_relative_angle`

When `OFF` (default): legacy behavior — vision uses `body.theta`; relative angle forced to 0.

## What the Observer knows (GT)

- `ACTIVE_SENSOR_ORIENTATION = AVAILABLE` when enabled
- body heading, head relative angle, head world heading, neck ω, neck motor
- Map: amber body axis, cyan head axis, FOV wedge from sensor heading

## What cognition receives

Only anonymous `exo_0/1/2` (and existing physical fragments).  
**Not** head angles, other-agent direction, LOOK_AT targets, or attention signals.

## What is NOT implemented

- LOOK_AT_AGENT / TRACK / FOLLOW / ATTENTION / CURIOSITY
- Desired-angle assignment
- Gaze stabilization toward salient objects
- Teaching the agent when to turn its head

## Scientific claims supported

- Active / articulated sensor orientation (physical)
- Sensorimotor coupling: neck motor → head → FOV → exo change (learnable chain)

## Claims NOT supported by this alone

attention, recognition, intentional tracking, curiosity, social interest, imitation

## Snapshot fields (future resume)

`head_relative_angle`, `head_omega`, `neck_motor` (+ config `articulated_head`)

## Parameters

| Field | Default | Role |
|-------|---------|------|
| `neck_angle_limit` | ±π/2 | Relative bound |
| `neck_motor_torque` | 0.08 | Torque scale |
| `neck_angular_velocity_limit` | 0.25 | ω max |
| `neck_damping` | 0.35 | Viscous damping |
| `neck_restoring_strength` | 0.04 | Soft return to 0 |
| `neck_work_cost_per_motor` | 0.02 | Optional work debit |

## Tests / artifacts

`tests/test_articulated_head_push.py`  
`results/embodiment/active_sensor_orientation_push/`

## Related

Neck proprioception (`prop_neck_*`) is documented in `docs/PHYSICAL_VESTIBULAR_SENSING.md`.
It senses neck configuration without exposing `head_world_heading` to cognition.

Oscillatory L/R receptors attach to the same head geometry; see
`docs/PHYSICAL_OSCILLATORY_SIGNALING.md`.
