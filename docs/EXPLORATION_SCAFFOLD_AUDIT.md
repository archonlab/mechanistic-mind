
# Phase-A Exploration Scaffold Audit

**File:** `experiments/historical_sensorimotor_selection/harness.py` → `phase_a_explore_motor`

## What it produces
Cycles locomotion over `{WAIT, MOVE:N/E/S/W}` and neck over `{NONE, NECK_LEFT, NECK_RIGHT, NECK_HOLD}` as a function of `(tick, seed)`.

## When active
Only while `(not psc_from_start) and tick <= T0` (Phase A). After PSC activation it is **off**.

## Does it bypass normal selection?
Yes, **during Phase A only**: after `run_cognition_before_action`, the harness replaces the executed motor and aligns `last_action` / `last_motor_output` so learning stores the scheduled experience.

## Does it modify cognition internals?
It does not change config, stores, or PSC scoring. It only sets what motor was executed for physics + next-tick learning.

## Semantic preferences?
None. Fixed cycle; not approach/visual/reward biased.

## Active after PSC activation?
**No.** Phase B uses real PSC / composite factorization only.

## Role
Experimental scaffolding so Phase A accumulates diverse `(O,M)→ΔO` and history before PSC ON — required after endogenous collapse starved multi-candidate PSC in the prior battery.
