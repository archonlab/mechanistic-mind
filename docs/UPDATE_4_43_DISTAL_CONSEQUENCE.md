# Update 4.43 FINAL REPORT — Distal Consequence

## Outcome D

A distal physical consequence contributes additional bounded W and later q/I/N
under a matched present X. It does **not** produce a reproducible distal-specific
P(A) shift. 4.42 C7 is resolved at acquisition/dynamics, not at motor.

27 / 32 claims ASSERTED. Seeds 17, 23, 41, 59, 83. `leak = []`

Learning rule unchanged (`TRACE_DECAY=0.62`, `LEARNING_RATE=0.075`).
Invalid 4.42 Outcome F was not restored. 4.42 remains Outcome C.
C22 threshold 0.004 was not moved.

## What did B add that X→A did not?

Additional W structure and later endogenous q/I/N under the same present X.
Nothing detectable in autonomous P(A).

H2 vs H1 W L1 = 0.488. H2 vs H1B (matched B, out of window) W L1 = 0.464.
Same-present q L1 H2 vs H1 = 1.35.

P(A)|H1 ≈ 0.084, P(A)|H1B ≈ 0.073, P(A)|H2 ≈ 0.079.
|H2−H1| ≈ 0.005 < 0.01. H2 sits between H1 and H1B.

## Where does distal information disappear?

1. B physically occurs and changes body if applied (C5).
2. At D1=2, A-eligibility on ch1 is 0.269; B writes ΔW ≈ 0.014 (C6, C7).
3. That ΔW is retained and is temporally specific (C8–C13). Delay series
   W-vs-H1: D0=0.91, D1=0.49, D2=0.22, D3=0.17.
4. Matched-present X then produces different q/I/N (C14, C16).
5. Softmax motor *probs* are not identical (C17) but P(A)=P(M1) does not
   move past the preregistered 0.01 bar (C18, C30).

Limiting factor: **downstream readout**, not temporal locality or capacity.
X probe reactivates the proximal X→A coupling (channel 1 / M1). Distal
A→B structure lives mainly in other couplings and does not change P(A).

Not: eligibility missing (in-window). Not: 3×3 too small (C26/C27).
Do not extend the trace or boost B to force C18.

## First unsupported arrows

| chain | first unsupported |
|---|---|
| PHYSICAL_ACCESS | null |
| ELIGIBILITY | null |
| ACQUISITION | null |
| TEMPORAL_SPECIFICITY | null |
| CURRENT_DYNAMICS | null |
| BEHAVIOR | C18_autonomous_pA_difference |
| FUTURE | C31_future_body_secondary |
| FULL_DISTAL_CHAIN | C30_distal_consequence_to_motor |

## Strongest allowed claim (Level 3)

A distal physical consequence contributed to acquired internal dynamics such
that matched present conditions later produced different endogenous activity
from otherwise matched proximal histories.

Not Level 4/5. Not credit assignment, reward, intention, preference, regulation.

## 4.42 C7

W and q now distinguish X→A from X→A→B (C8, C11, C14).
The *motor* effect in 4.42 still does not: C29/C30 NOT ASSERTED.

## Secondary future body

fut_diff ≈ 0.0008 << 0.004. C31 NOT ASSERTED. Not retuned.

## Per-seed P(A)

| seed | H1 | H1B | H2 |
|---|---|---|---|
| 17 | 0.08446 | 0.07252 | 0.07918 |
| 23 | 0.08420 | 0.07229 | 0.07883 |
| 41 | 0.08409 | 0.07219 | 0.07869 |
| 59 | 0.08500 | 0.07300 | 0.07988 |
| 83 | 0.08462 | 0.07266 | 0.07938 |

## Claims

- C1 distinct X and A: **ASSERTED**
- C2 proximal history match: **ASSERTED**
- C3 distal exposure match: **ASSERTED**
- C4 distal temporal difference: **ASSERTED**
- C5 B reaches ordinary physics: **ASSERTED**
- C6 eligibility present at B: **ASSERTED**
- C7 B participates in local update: **ASSERTED**
- C8 distal W difference: **ASSERTED**
- C9 temporal specificity: **ASSERTED**
- C10 B exposure independence: **ASSERTED**
- C11 proximal repetition independence: **ASSERTED**
- C12 delay dependence: **ASSERTED**
- C13 out-of-window loss: **ASSERTED**
- C14 same-present internal difference: **ASSERTED**
- C15 W necessity: **ASSERTED**
- C16 pre-event N difference: **ASSERTED**
- C17 motor distribution difference: **ASSERTED** (any inequality; see C18)
- C18 autonomous P(A) difference: **NOT ASSERTED**
- C19 stochastic separation: **NOT ASSERTED**
- C20 explicit prediction independence: **ASSERTED**
- C21 valuation independence: **ASSERTED**
- C22 raw-history independence: **ASSERTED**
- C23 B removal causality: **ASSERTED**
- C24 temporal shift causality: **ASSERTED**
- C25 physical consequence specificity: **ASSERTED**
- C26 representational coexistence: **ASSERTED**
- C27 boundedness: **ASSERTED**
- C28 acquisition horizon: **ASSERTED**
- C29 4.42 C7 resolution (motor): **NOT ASSERTED**
- C30 distal consequence → motor: **NOT ASSERTED**
- C31 future body secondary: **NOT ASSERTED**
- C32 historical NULL preservation: **ASSERTED**

## 4.42 adversarial audit

No `or True`. X ≠ A. C22 threshold untouched. Outcome C still valid.
Serious defect invalidating C: none.

## Delay preregistration

D0=0, D1=2 (primary, 4.42 gap), D2=5, D3=12. From eligibility, before behavior.

## Regressions

4.39, 4.40, 4.41, 4.42, 4.43 unit tests passed. 4.42 summary still Outcome C.

## Recommended next

C29/C30 NOT ASSERTED. Stay at the readout boundary:

    distal-specific q/I/N  -X->  autonomous P(A)

Do **not** implement self-generated / recursive development.
Do not extend eligibility or raise motor gain to cross 0.01 or 0.004.

## Not claimed

credit assignment, reward learning, reason, motivation, desire, preference,
goal, intention, planning, hunger, fear, consciousness.
