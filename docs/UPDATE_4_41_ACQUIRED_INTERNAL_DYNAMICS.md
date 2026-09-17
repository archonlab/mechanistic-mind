# Update 4.41 — Acquired Internal Dynamics

## Architecture inspection

Before this update, endogenous I had fixed decay and persistence but no
plastic cross-channel coupling. Learned weights existed only in descriptive
prediction stores; retrieval did not alter active state. No generic local
mechanism converted temporal physical activity into changed future internal
dynamics.

Update 4.41 adds a fixed three-channel adaptive substrate with a bounded 3×3
matrix and three-element eligibility trace. The update rule uses only the
previous local trace and the current numeric physical input. It receives no
reward, value, prediction error, action result, experiment condition, symbolic
identity, or desired response. State and traces are bounded to ±1, weights to
±0.65, and all terms decay.

## Result

All C1–C30 were asserted across seeds 17, 23, 41, 59, and 83.

Repeated numeric X→Y and A→B sequences modified W. Under matched current body,
world, input, initial q, I, N, and stochastic sequence, the same X subsequently
produced a different q trajectory than in the naive system. X→Y and X→Z
histories produced distinct trajectories.

The effect was larger than preregistered L1 trajectory differences from
matched shuffled and iid streams and from X-only/Y-only controls. It vanished
with plasticity disabled or acquired W ablated. Explicit prediction remained
available under W ablation, while history-dependent activation persisted with
runtime prediction disabled.

Acquired q activity entered the already established generic I substrate. I
then modulated the unchanged 4.40 I→N port and the unchanged 4.39 N→motor
mapping. I→N ablation preserved upstream q/I and removed downstream N effects.
The effect occurred before and survived omission of the later physical event.

Silent X→Y to X→Z reversal revised W, precursor activity, I, and N through
local activity alone. Relation removal changed the response and restoration
formed it again. Raw-history purge did not alter the acquired response.

The supported chain is:

`PAST PHYSICAL SEQUENCE → BOUNDED LOCAL W → SAME INPUT / DIFFERENT q → I → N → MOTOR`

Runtime explicit prediction and `ordinary_state_value` contributions were
zero. Historical NULLs remain valid because this is a newly isolated pathway.

Run:

```bash
PYTHONPATH=. python3 experiments/run_update441_acquired_internal_dynamics.py
```
