# Update 4.39 — Intrinsic Sensorimotor Dynamics

Update 4.39 introduces the smallest generic bounded physical layer between
actual body inputs and motor output. It is not a decision, reward, planning, or
biological-neuron model.

## Architecture inspection

The 0.08 interaction probability measured in Update 4.38 is
`BASELINE_NON_WAIT` in its research action probe and is sampled at action
selection. It is independent of body state and learning. Existing body physics
contains action costs, persistent loads, and WAIT evolution, while the legacy
prediction-to-action route passes through inherited target-error evaluation.
No generic dynamical state accepted actual and predicted body states through a
shared physical interface.

Update 4.39 therefore adds a three-channel state with bounded accumulation,
decay, persistence, mixed actual-body coupling, sensory perturbation, and the
unaltered 0.08 stochastic motor baseline. It has no predicted-body input port.

## Experimental result

Across seeds 17, 23, 41, 59, and 83:

- C1–C12 were asserted.
- C13–C17 were not asserted.
- C18 prediction revision was asserted.
- C19 anticipatory sensorimotor revision was not asserted.
- C20 passive-development compatibility and C21 boundedness were asserted.

Body-state sweeps changed the bounded sensorimotor state and motor-channel
distribution. Selective B→N ablation removed the difference. Hiding the
accessible signal did not remove physical coupling; showing the signal while
ablating physical coupling did not reproduce it. These effects retained zero
`ordinary_state_value` and legacy-logit contributions.

Ordinary learning acquired precursor→future-body and future-body→future-N
relations, including passive acquisition. The composed prediction remained
available after learning, but matched current body/world probes produced the
same current N and motor distribution with learned history, no history, and
prediction ablation.

The result is therefore:

`ACTUAL BODY -> SENSORIMOTOR DYNAMICS -> MOTOR OUTPUT`

while:

`PREDICTED FUTURE SENSORIMOTOR STATE -X-> PRESENT SENSORIMOTOR DYNAMICS`

Actual physical body state causally modulated intrinsic sensorimotor dynamics,
but acquired prediction of that future body state did not independently
re-enter present sensorimotor dynamics in the tested architecture.

Run:

```bash
PYTHONPATH=. python3 experiments/run_update439_sensorimotor_dynamics.py
```
