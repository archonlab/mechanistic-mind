# Update 4.44 FINAL REPORT — Body × Acquired Dynamics

## Outcome A

Current body and acquired distal history each change endogenous dynamics.
They do **not** interact in q, I, or N. Softmax produces a small motor residual
below the preregistered interaction criterion.

20 / 31 claims ASSERTED. Seeds 17, 23, 41, 59, 83. `leak = []`

Motor readout was not changed. 4.43 0.01 bar was not reused as the
interaction definition. SPAN_MIN=0.008, RESIDUAL_MIN=0.004, written before
factorial outcomes.

## Why 4.43 Δq≈1.35 yields ΔP(A)≈0.005

Distal B writes **channel 2**. P(A)=P(M1) is sensitive to **N1**.
Jacobian at H1: dP(A)/dN ≈ [0.035, 0.104, −0.019].
dN ≈ [−0.018, −0.037, +0.294]. Motor-orthogonal L2 ≈ 0.283 vs linearized
|dP(A)| ≈ 0.010. ~95% of the internal difference is motor-orthogonal.

## Five questions

1. Same acquired history, different body, different motor?
   Body changes P(A) (main effect). History ΔP(A) stays ≈ −0.005 at MID
   and −0.004/−0.010 at HIGH/LOW. Not a body-gated distal-A effect.

2. Non-additive or sum of mains?
   Additive. Residual max |r| ≈ 0.0019 < 0.004. Span of Δ_history ≈ 0.0061
   < 0.008. Tiny softmax curvature only.

3. At the same instantaneous body, does recent trajectory matter?
   No. T_DOWN vs T_UP end at B_MID; q L1=0; ΔP(A)≈0.001.

4. What would carry trajectory dependence?
   Only N persistence. After complete-state match (reset q/I/N), ΔP(A)=0.
   No extra historical variable.

5. Does distal history become motor-relevant anywhere in the tested body space
   without changing readout?
   **No.**

## Factorial P(A) (seed 17; others match)

| | B_LOW | B_MID | B_HIGH |
|---|---|---|---|
| H1 | 0.1224 | 0.0845 | 0.0732 |
| H2 | 0.1121 | 0.0792 | 0.0689 |
| Δ | −0.0104 | −0.0053 | −0.0043 |

q/I/N history L1 is **identical** at all three bodies (q last-tick 0.161;
traj L1 as in 4.43). Body never enters q or I. N = body_term + 0.16 I.

## First unsupported arrows

| chain | first unsupported |
|---|---|
| BODY | null |
| HISTORY | null |
| INTERACTION_INTERNAL | C8_q_interaction |
| INTERACTION_MOTOR | C11_motor_interaction |
| TRAJECTORY | C23_same_body_diff_traj_internal |
| TRAJECTORY_MOTOR | C24_same_body_diff_traj_motor |
| FULL_CONTEXTUAL_CHAIN | C12_pA_interaction |
| FUTURE | C30_future_body_secondary |

## Strongest allowed claim (Level 1)

Current physical body state and acquired developmental history each
altered endogenous dynamics, but no reproducible interaction between
them was detected.

## Historical NULLs

4.37–4.40 untouched. 4.42 Outcome C preserved. 4.43 Outcome D preserved
(C18/C29/C30 still not a 4.43-condition motor effect). This does not
retroactively make 4.43 C18 positive.

## Regressions

4.39–4.44 unit tests passed. 4.42 summary still C. 4.43 summary still D.

## Recommended next

Stay at internal integration/readout. Body and W add in N; the distal
difference remains motor-orthogonal. Do not raise motor gain, do not
install a reason/value variable, do not start recursive development.

## Not claimed

motivation, reason, context, urgency, preferred state, intention, hunger,
consciousness.
