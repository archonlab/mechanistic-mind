# Physical Vestibular Sensing × Rotational Proprioception

Minimal body-local rotational transducers for Mechanistic Mind / Tiktaalik.

## What the agent can physically sense

When enabled:

| Channel | Physical source | Notes |
|---------|-----------------|-------|
| `vest_0` | body angular velocity ω | tanh-bounded |
| `vest_1` | body angular acceleration α | from orientation meta or Δω |
| `prop_neck_0` | head_relative_angle | requires articulated head |
| `prop_neck_1` | head_omega | requires articulated head |

These channels are **continuous passive transducers** — they do not consume a
motor/action slot. Under COMPOSITE_MOTOR_V1 they remain active during
MOVE + NECK + OSC in the same tick (see `docs/COMPOSITE_MOTOR_CONTROL.md`).

## What cognition does **not** receive

- absolute heading / compass / N-S-E-W
- head_world_heading
- target / agent / object direction
- SELF_MOTION / WORLD_MOTION labels
- LOOK_AT / gaze error / attention

## WORLD GT (Observer only)

Body θ, ω, α · head relative / world heading · head ω · neck motor  
Separated from AGENT-ACCESSIBLE in Sensors UI.

## Ablation

| Toggle OFF | Physics | Vision | Sensor access |
|------------|---------|--------|---------------|
| vestibular | unchanged | unchanged | vest_* absent |
| neck proprioception | neck still moves | FOV still follows head | prop_neck_* absent |

## Transduction decision

**Direct bounded tanh** — no transducer time-constant memory in this update  
(documented alternative deferred to avoid hidden semantic processing).

Linear body-local acceleration channels: **DEFERRED**.

## Mechanisms

- `physical_vestibular_sensing`
- `neck_proprioception`

## Integration

- Observation: `accessible_observation`  
- Telemetry V2: compact `omega`, `body_alpha`, `head_omega`, `vest_*`, `prop_neck_*`  
- Analyzer: `summarize_vestibular_proprioception`  
- UI: `VestibularProprioceptionPanel`

## Claims supported

physical vestibular sensing · rotational proprioception · body-local angular sensing · neck-state sensing · sensorimotor coupling availability

## Claims NOT supported

balance · self-awareness · gaze stabilization · VOR · attention · navigation · intentional looking

## Artifacts

`results/embodiment/vestibular_proprioception/`  
`tests/test_vestibular_proprioception.py`
