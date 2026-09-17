# Update 4.42 FINAL REPORT — Body-Coupled Development

## Outcome C

Autonomous intervention probability changes under matched present conditions.
The expected future body trajectory does **not** diverge enough to assert regulation.

30 / 34 claims ASSERTED across seeds 17, 23, 41, 59, 83.
`leak = []`

This replaces an earlier untrustworthy pass that asserted Outcome F with C3 forced `or True` and identical X/A patterns.

## Strongest allowed claim (Level 3, with C7 boundary)

Different developmental histories produced different autonomous physical intervention
distributions under matched present conditions through acquired internal dynamics,
independently of runtime explicit prediction and the legacy ordinary_state_value pathway.

Not claimed: the distal body relation is what produced that intervention shift
(C7 NOT ASSERTED). Not claimed: the shift alters later body trajectory (C22/C24
NOT ASSERTED). Not claimed: hunger, desire, goal, homeostasis, intention, planning.

## First unsupported arrows

| chain | first unsupported |
|---|---|
| PHYSICAL | null |
| DEVELOPMENT | null |
| PRE_EVENT | null |
| BEHAVIOR | null |
| FUTURE | C22_future_body_divergence |
| FULL_LOOP | C24_closed_body_coupled_loop |
| REVISION | null |

C29 (reversal of future body) is ASSERTED only because the reversal probe applies
B3 distal physics. That is a world-side flip, not independent evidence that
revised behavior closed a body loop. Treat C26–C28 as the supported revision chain.

## Why C22 / C24 fail

Successful A changes later body (C2): physics L1 = 0.155.
H1 vs H2 P(M1) ≈ 0.076 vs 0.055 (Δ ≈ 0.021).
Mixed expected future L1 ≈ 0.0032–0.0033, below the preregistered 0.004 cutoff.
The motor shift is real and too small to move expected B.

## Why C7 fails

H_A_REP (X→A without distal B) produces a similar P(A) to H1.
The intervention shift is accounted for by X→A temporal coupling (4.41-style),
not by the X→A→B body relation.

## Immediate vs distal (C3)

immediate L1 = 0; distal L1 = 0.155. Matched immediate, different distal.

## Per-seed metrics

| seed | P(A)\|H1 | P(A)\|H2 | P(A) naive | fut_diff | A vs no-A physics | d_q | d_q_rep | W L1 |
|---|---|---|---|---|---|---|---|---|
| 17 | 0.07568 | 0.05466 | 0.05338 | 0.00326 | 0.155 | 2.409 | 1.371 | 0.755 |
| 23 | 0.07534 | 0.05460 | 0.05329 | 0.00321 | 0.155 | 2.409 | 1.371 | 0.755 |
| 41 | 0.07520 | 0.05458 | 0.05326 | 0.00320 | 0.155 | 2.409 | 1.371 | 0.755 |
| 59 | 0.07635 | 0.05478 | 0.05357 | 0.00334 | 0.155 | 2.409 | 1.371 | 0.755 |
| 83 | 0.07587 | 0.05469 | 0.05343 | 0.00328 | 0.155 | 2.409 | 1.371 | 0.755 |

## Claims

- C1 autonomous body evolution: **ASSERTED**
- C2 physical interaction consequence: **ASSERTED**
- C3 immediate consequence match: **ASSERTED**
- C4 body-coupled developmental experience: **ASSERTED**
- C5 local coupling acquisition: **ASSERTED**
- C6 temporal structure dependence: **ASSERTED**
- C7 action repetition independence: **NOT ASSERTED**
- C8 body exposure independence: **ASSERTED**
- C9 precursor dependence: **ASSERTED**
- C10 pre-event internal activation: **ASSERTED**
- C11 W necessity: **ASSERTED**
- C12 event omission survival: **ASSERTED**
- C13 explicit prediction independence: **ASSERTED**
- C14 valuation independence: **ASSERTED**
- C15 pre-event N modulation: **ASSERTED**
- C16 I→N necessity: **ASSERTED**
- C17 autonomous motor modulation: **ASSERTED**
- C18 motor path necessity: **ASSERTED**
- C19 autonomous physical intervention: **ASSERTED**
- C20 stochastic baseline separation: **ASSERTED**
- C21 same present / different history action: **ASSERTED**
- C22 future body divergence: **NOT ASSERTED**
- C23 intervention necessity for future: **NOT ASSERTED**
- C24 closed body-coupled loop: **NOT ASSERTED**
- C25 passive development compatibility: **ASSERTED**
- C26 reversal of acquired coupling: **ASSERTED**
- C27 reversal of pre-event internal: **ASSERTED**
- C28 reversal of autonomous intervention: **ASSERTED**
- C29 reversal of future body: **ASSERTED** (world-side B3 confound; see above)
- C30 relation removal adaptation: **ASSERTED**
- C31 reacquisition: **ASSERTED**
- C32 raw-history independence: **ASSERTED**
- C33 long-run boundedness: **ASSERTED**
- C34 second-order development: **ASSERTED**

## Historical NULL preservation

- 4.37 contingent futures → present action: untouched
- 4.38 acquired consequence prediction → endogenous action: untouched
- 4.39 predicted future body/N → present N: untouched
- 4.40 acquired explicit prediction → endogenous I: untouched
- 4.41 HISTORY → W → q → I → N → MOTOR: preserved (pytest 4.39/4.40/4.41 passed)

## Architecture notes

No `.git` in `<local-lab-tree>`. Existing persist `EMIT` / `action_relief` unused.
4.42 adds only distinct X vs A_PAT channels, delayed distal body on `internal_a`/`load_c`,
and the probe/control suite. 4.41 learning rule unchanged. M1 is physical A
because A_PAT is channel 1.

## Recommended next

Do **not** implement self-generated development.

Follow the first unsupported FUTURE arrow (C22): the acquired ΔP(A) ≈ 0.021
does not move expected B past 0.004. Separately, C7 shows the motor shift is
X→A coupling, not X→A→B. A later probe should ask whether a larger or
more body-specific motor displacement can appear without installing a
preference or policy.

## Not claimed

consciousness, self-awareness, subjective memory, expectation, intention,
desire, hunger, fear, preference, goal, understanding, planning, survival.
