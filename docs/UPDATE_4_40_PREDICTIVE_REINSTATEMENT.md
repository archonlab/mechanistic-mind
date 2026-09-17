# Update 4.40 — Endogenous Predictive Signaling

## Architecture boundary

Update 4.39 N accepted actual body input, sensory perturbation, persistence,
and stochastic variation. Predictive stores were queried data: retrieval did
not create a bounded causal activation state, and no associative mechanism
could partially reinstate an internal pattern. Update 4.40 did not manufacture
that missing arrow.

The update adds only neutral infrastructure: a fixed three-dimensional bounded
internal signal with decay, persistence, and superposition, plus a
source-agnostic numeric I→N input port. The port cannot identify predictions,
body states, actions, or consequences.

## Result

Across seeds 17, 23, 41, 59, and 83:

- C1–C5 were asserted.
- C6–C18 were not asserted.
- C19 prediction revision was asserted.
- C20–C24 were not asserted.
- C25 boundedness was asserted.

Researcher-injected I changed N, and I→N ablation removed that change. Two
distinct precursor/future-N relations were acquired using ordinary bounded
learning. However, presenting either precursor generated the same zero I in
learned, no-history, shuffled-history, prediction-ablation, raw-history-purged,
and valuation-neutralized probes. Current body, world, initial N, stochastic
sequence, and omission of the future event were matched.

The first unsupported arrow is:

`ACQUIRED PREDICTION -X-> ENDOGENOUS SIGNAL GENERATION`

A bounded generic endogenous signal can physically participate in the
intrinsic sensorimotor dynamics established in 4.39. This says nothing about
learning or anticipation: acquired prediction did not generate such a signal
in the tested architecture.

Run:

```bash
PYTHONPATH=. python3 experiments/run_update440_predictive_reinstatement.py
```
