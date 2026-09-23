# COMPOSITE MOTOR CONTROL

**Marker:** `COMPOSITE_MOTOR_CONTROL_ACCEPTED` (see `results/composite_motor_control/`)

## Principle

Separate:

1. **Passive physical perception** — continuous transducers (vision, osc L/R, vest, prop, fields)
2. **One cognitive decision cycle** — existing MM machinery
3. **Composite motor output** — structured `{locomotion, neck, oscillator, push}`
4. **Physical effector state** — persists and evolves under ordinary dynamics

Perception is **not** an action. No LISTEN / SEE / FEEL slots.

## Schema `COMPOSITE_MOTOR_V1`

```text
CompositeMotorOutput {
  locomotion: WAIT | MOVE:N|S|E|W
  neck:       NONE | NECK_LEFT | NECK_RIGHT | NECK_HOLD
  oscillator: { frequency_delta, amplitude_delta, emit_trigger }
  push:       bool
}
```

No Cartesian compound tokens (`MOVE_E_NECK_LEFT_OSC_EMIT`, …).

## Selection (one cycle)

- PSC / competition runs on the **locomotion** set only.
- Neck / oscillator / push are **factorized** in the same cycle from retained predictions (or rare endogenous exploration).
- Cost is O(sum of domain sizes), not O(product).

## Persistence

| Control | Persistence |
|---------|-------------|
| MOVE | one-tick impulse (momentum may continue) |
| NECK_* | torque this tick; head angle/omega continue under neck physics when NONE |
| OSC_FREQ/AMP | change `osc_*_u` once; value remains |
| OSC_EMIT | starts episode of duration N; remaining ticks without re-select |
| WAIT | no new intervention; world/body/sensors continue |

## Full duplex

Agents may emit and receive in the same tick. Two agents may emit simultaneously. Self + cross contributions superpose physically. Cognition sees anonymous `osc_l_*` / `osc_r_*` only.

## Legacy

Old runs with single-slot `action_counts` keep schema `LEGACY_SINGLE_SLOT`. Analyzer does not reinterpret them as composite control counts.

## Module

`mechanistic_mind/physical_system/composite_motor.py`
