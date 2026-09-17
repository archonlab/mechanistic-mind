# TODO #4 pre-implementation audit

The machine-readable audit is in `experiments/todo4_preimplementation_audit.json`.

The current contextual world combines the default daily body drains with directional ambient exposure. At unit exposure, WAIT therefore starts from approximately −0.090 energy, −0.057 hydration and +0.060 fatigue per tick; MOVE adds its distance-dependent cost. This is short relative to a 32×32 environment and explains the early physiological collapse visible in long Observer runs.

Perception is lawful but vision-centric. Local observations expose visible physical fragments and geometry, current position/actions, body-derived interoceptive signals, and the last experienced action/effects. Hidden roles, configured body effects, world effects and Observer history are excluded. Physical exposure and action contacts exist in the runtime but are not yet composed as explicit perceptual modalities.

Bounded retrieval is genuinely indexed and capped at 12 inspected memory records. However, `exploration_gain=2.0` is active in the final bounded action score as an intrinsic uncertainty bonus. TODO #4 must explicitly disable that term in its arm while retaining the old configuration as the baseline control.

`BROKEN` is not a body or psychological state. It configures only the hidden transition schedule of `TARGET-ANVIL` in `PersistentTargetsWorld`: it works before tick 45 and then stalls while its visible cue remains unchanged.

Finally, the canonical Psychology Observer currently repeats full before/after state and mechanism payloads each tick. A compact event/telemetry/checkpoint observer already exists, but the live Observer and Analyzer do not yet use a compatible compact reconstruction contract.
