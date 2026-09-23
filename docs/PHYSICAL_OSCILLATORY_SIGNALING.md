# Physical Oscillatory Signaling

Banded spatial transduction alongside legacy `FIELD_A` / `FIELD_B`.

## Architecture decision: OPTION B

Legacy FIELD_A/B are **non-negative amplitude continua** (motion→A, contact→B).
They cannot carry frequency / overlapping spectral discrimination without
fake physics. This feature adds **`OSC_BANDS`** `(n_bands, H, W)` plus motor
controls and L/R head-linked receptors.

When `oscillatory_signaling` is OFF: legacy fingerprint **EXACT_MATCH**.

`FINITE_PROPAGATION = NOT_IMPLEMENTED` — deposits are local; reach emerges from
decay + 4-neighbor spread (same family as FIELD_A/B). No delayed wavefront.

## Emission motor (no combinatorial action table)

| Action | Effect |
|--------|--------|
| `OSC_FREQ_UP` / `OSC_FREQ_DOWN` | nudge `osc_freq_u` ∈ [0,1] |
| `OSC_AMP_UP` / `OSC_AMP_DOWN` | nudge `osc_amp_u` ∈ [0,1] |
| `OSC_EMIT` | start/refresh persistent emission for bounded duration |

Under **COMPOSITE_MOTOR_V1**, these are oscillator-domain components of one
structured motor vector (may coexist with MOVE/NECK/PUSH in the same tick).
`frequency_delta`, `amplitude_delta`, and `emit_trigger` may all be set together.
Full duplex: emit and receive in the same tick; no half-duplex / turn-taking.

Physical frequency = `f_min + (f_max−f_min)·osc_freq_u` (normalized).
Duration persists across WAIT/MOVE/NECK/PUSH.

Optional work cost: `work_cost_per_amp_tick × amplitude` per emit tick.

## Reception

6 overlapping Gaussian bands → anonymous cognition channels:

`osc_l_0`…`osc_l_5`, `osc_r_0`…`osc_r_5`

Receptor sites rotate with `head_world_heading` (or body θ if head OFF).

Cognition does **not** receive: exact frequency, source id, source direction,
emitter motor parameters, left−right bearing.

## Mechanism

- id: `oscillatory_signaling`
- fresh default: **ON**
- Climate Ecology remains default **OFF**
- Preflight verifies emitter actions + `OSC_BANDS` + channel availability
  (zeros are valid)

## Claims supported

physical oscillatory signaling · banded reception · spatial transduction ·
sensorimotor coupling availability

## Claims NOT supported

language · messages · meaning · communication · attention · orienting-to-source ·
dialogue · vocabulary

## Artifacts

`results/oscillatory_signaling/` · `tests/test_oscillatory_signaling.py`
