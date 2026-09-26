# Beta 3.1 — Optical → PSC competition counterexample search

**BETA31_OPTICAL_PSC_COUNTEREXAMPLE_SEARCH = PASS**

Audit/search. Production semantics unchanged. Finding a counterexample is **not**
a claim that Tiktaalik understands colour.

```
BETA3_REFERENCE_MODIFIED = NO
SCIENTIFIC_SEMANTICS_CHANGED = NO
RUNTIME_SEMANTICS_CHANGED = NO
PSC_SEMANTICS_CHANGED = NO
SMC_SEMANTICS_CHANGED = NO
PE_SEMANTICS_CHANGED = NO
OPTICAL_WEIGHTS_ADDED = NO
SEMANTIC_COLOR_MEANING_ADDED = NO
GIT_PUSH = NO
```

Harness: `experiments/run_beta31_optical_psc_counterexample.py`  
Tests: `tests/test_optical_psc_counterexample_search.py`  
Artifacts: `results/beta31_optical_psc_counterexample/`

Primary proof: **A. PURE ACCESSIBLE OPTICAL** (`NON_OPTICAL_DIFF_COUNT = 0`).
Selection is always `select_observed_composite_motor`.

---

## A. Search design

Controlled current state: identical cognition-relevant non-optical observation,
body/local fillers, motors, RNG (`0.2`), PSC mode `OBSERVED_COMPOSITE`. Only
`surface_c*` differs.

Stores are deep-cloned per branch. X-then-Y vs Y-then-X order invariance is
checked. RNG ties are not counted as optical sensitivity.

Optical families: single-channel bin crossings, same-bin raw pair, C0/C1 swap,
LEFT vs RIGHT sectors, 8- and 9-channel high separation.

History families: empty, symmetric, optically conditioned separated
consequences, unequal support, competing motors, PE-merge, PE-separation.
Depths 1–16; support ratios 1:1 through 8:1 (and mirrors).

---

## B. SMC optical-only bound

Default SMC vector: **48 equal-weight channels**. `FAMILY_VISUAL` includes 3
`exo_*` plus **9** `surface_c*`. `channels_for_store(empty_store)` is 48.
`_l1` is `sum|Δ| / len(keys)` on **quantized** signatures (`_q_scalar` midpoints
0.1 … 0.9, max per-channel travel **0.8**). Missing keys fill as 0 then
quantize to 0.1.

| Bound | Value |
|---|---|
| Naïve raw `[0,1]` | 9/48 = **0.1875** |
| Quantized max | 9×0.8/48 = **0.15** |
| Empirical 0 vs 1 | **0.15** |
| `SIM_THRESHOLD` | **0.22** |

**0.15 < 0.22** and **0.1875 < 0.22**.

**SMC_ALWAYS_GENERALIZES_ACROSS_OPTICAL_ONLY_DIFFERENCES = YES**  
**SMC_OPTICAL_ONLY_SEPARATION_IMPOSSIBLE = YES** for current optical-only
perturbations on the default 48-channel store.

This does **not** make PSC competition structurally insensitive: downstream
exact keys and `MATCH_TOL = 0.12` can still separate (0.15 > 0.12).

Eight optical channels at full quantized travel: 8×0.8/48 ≈ **0.133 > 0.12**.
Seven channels: 7×0.8/48 ≈ **0.117 < 0.12**.

---

## C. Optical profile families

Quantizer (verified): 0.19→0.1, 0.21→0.3, 0.21 and 0.29 alias at 0.3.

| Pair | SMC mean L1 | vs 0.22 | vs MATCH_TOL 0.12 |
|---|---|---|---|
| bin crossings (1 ch) | ≈ 0.0042 | always match | always match |
| same-bin 0.21 vs 0.29 | 0 | alias | alias |
| C0/C1 swap / sector | 0.10 | match | match |
| high-sep 8 ch | 0.133 | match | **separable** |
| high-sep 9 ch / C0C1C2 swap | 0.15 | match | **separable** |

---

## D. Conditioned history families

Empty history: both X and Y → `FALLBACK_LOCO` (negative control).

Symmetric support on both motors: **LEVEL 0** even at 9-channel optical
separation (HSS equalizes).

**conditioned_separated**: X+MOVE:E → high non-optical basin; Y+MOVE:W → low
basin. Production `smc.update` + `pr.learn_transition`. This is the positive
family.

Unequal support / competing motors / PE-separation also produce flips when
optical L1 > MATCH_TOL. PE-merge (similar consequences) is weaker.

---

## E. HSS behavior

`query_history_on_o_prime` is **f(O′), not f(candidate identity)**: argmax
support over **all** loco candidates from that O′.

SMC still returns both motors (optical L1 0.15 < 0.22). Predicted Δ overwrites
non-optical channels; **surface_c\* is carried** into O′.

When motor-conditioned Δ is large enough that the “wrong” O′ is > MATCH_TOL
from every lived antecedent:

- X, MOVE:E → O′ ≈ high+X optics → MATCH MOVE:E  
- X, MOVE:W → O′ ≈ low+X optics → **NO_MATCH** (0.15 from Y basin; far from X high basin)  
- Y is the mirror  

`build_psc_scenario` returns `None` on NO_MATCH → **candidate set shrinks**.
Winner is `SINGLE_SUPPORTED`. HSS here **does** condition on carried O′ optics
once basins are MATCH_TOL-separated. If basins are too close, HSS **pools**
across optical contexts (previous causal-trace fixture).

Nine exo/vest/prop channels are **not** enough once production also learns
the **pre-consequence** state (quantized travel 0.6×9/48 ≈ 0.1125 < 0.12).
The surviving OFF→ON protocol uses **all 39 non-optical SMC channels** as
consequence travel so ox vs wrong-O′ exceeds MATCH_TOL. That is still
anonymous ΔS, not colour meaning.

---

## F–J. Sensitivity ladder

| Level | Demonstrated |
|---|---|
| 0 optics reach candidates, competition unchanged | YES (symmetric / empty) |
| 1 evidence/scores | YES |
| 2 ordering | YES |
| 3 winner | YES |
| 4 motor proposal | YES (MOVE:E vs MOVE:W; necks differ) |
| 5 final action | YES (`legacy_token` MOVE:E vs MOVE:W) |

**PSC_OPTICAL_SENSITIVITY_MAX_LEVEL = 5**

Not motor aliasing: winner change and motor change coincide.

---

## K. Strongest positive counterexample

Mode A. `NON_OPTICAL_DIFF_COUNT = 0`. RNG 0.2. Order-invariant.

**CURRENT** non-optical: all SMC channels 0.25.

**OPTICAL X:** all nine `surface_c* = 0.90`  
**OPTICAL Y:** all nine `surface_c* = 0.10`

**HISTORY (family conditioned_separated, depth 8):**  
X + MOVE:E/NECK_LEFT → high non-optical consequence (8×)  
Y + MOVE:W/NECK_RIGHT → low non-optical consequence (8×)  
Prospection: continuations from those O′ basins, support 8, `MIN_SUPPORT` met.

**X:** SMC matches both motors; HSS MATCH only on MOVE:E (support 8).  
Candidate set `{MOVE:E|NECK_LEFT}`. Winner MOVE:E.

**Y:** HSS MATCH only on MOVE:W. Winner MOVE:W.

**CAUSAL DIFFERENCE:** SMC 5-bin signatures differ but remain **similar**
(0.15 < 0.22). Earliest competition-relevant split: **O′ carry of surface_c\*
into prospective `predict_one_step`**, where 0.15 > MATCH_TOL 0.12, so the
wrong motor’s O′ is NO_MATCH and is dropped before `compete_scenarios`.

Receipt: `results/beta31_optical_psc_counterexample/strongest_positive.json`

---

## L. Minimal reduction

- **8** differing `surface_c*` channels (9th held at 0.50)  
- History depth **1** SMC update per motor; prospection support **3** (`MIN_SUPPORT`)  
- Two empirical composites only  

Still LEVEL 5: X → MOVE:E, Y → MOVE:W.

`results/beta31_optical_psc_counterexample/minimized_counterexample.json`

---

## M. Strongest negative

1. Empty history → both `FALLBACK_LOCO`. Current optics do not magically select.  
2. **Symmetric** high-sep 9ch history: both motors supported in both basins →
   same candidate set, same scores, same winner (RNG unused; dominance/tie
   identical). Optics reach O′ but competition equalizes.

---

## N. PSC OFF → ON control

Learned with `psc_motor_resolution = LOCO_FACTORIZED` via
`run_cognition_before_action` (canonical `smc.update` + `pr.learn_transition`,
including composite/neck dual-writes). Stores not reset. Then
`select_observed_composite_motor`.

Requires a lived step **at the consequence basin** (ox→x1 then x1→x2) because
HSS queries O′, not O.

**COUNTEREXAMPLE_SURVIVES_PSC_OFF_ON_PROTOCOL = YES**  
X → MOVE:E, Y → MOVE:W, `NON_OPTICAL_DIFF_COUNT = 0`.

---

## O. Naturalistic counterfactual

After the controlled proof: R=3 RICH, PSC competition off for 20 ticks, then
ON. Clone observation; invert `surface_c*` only; do not step the world.

| Mapping | n_obs keys | pr L1 | Result |
|---|---|---|---|
| CORRELATED | 30 | 0.16 | actual WAIT **SELECTED** vs invert **FALLBACK_LOCO** |
| SHUFFLED | 30 | 0.17 | both FALLBACK |

**NATURALISTIC_COUNTERFACTUAL_FOUND = YES** (CORRELATED clone). Ecological
sample, not a semantic terrain claim. SHUFFLED did not flip in this 20-tick
window.

---

## P. V3 observability

| | |
|---|---|
| optical current state | FULL (compact obs keeps `surface_c*`) |
| candidate / HSS / winner / motor divergence | PARTIAL |
| prove optical **causation** after a normal run | ABSENT |

**V3_CAN_PROVE_OPTICAL_PSC_CAUSALITY = PARTIAL**

The X/Y clone is diagnostic. V3 can show optics were present and a composite
was selected; it cannot reconstruct that the optical-only perturbation caused
the winner.

---

## Q. Search coverage / performance

| | |
|---|---|
| optical pairs | 10 |
| history fixtures | 80 |
| PSC selections | 160 |
| runtime | ~3.6 s |
| peak RSS | ~49 MB |

---

## R. Scientific interpretation

Under current production semantics, **an optical-only change can, given an
appropriate predictive history, causally alter OBSERVED_COMPOSITE PSC
competition**, including the winner and the resolved composite motor.

That is **not** colour understanding, reward, or terrain labels. It is
anonymous `surface_c*` floats participating in existing SMC → O′ → HSS →
`compete_scenarios` machinery.

SMC **always** generalizes across optical-only current differences (9/48 bound).
Specificity is rescued by **prospective MATCH_TOL** and O′ carry, **not** by
SMC retrieval. If history does not build MATCH_TOL-separated O′ basins, HSS
pools evidence and competition does not flip (symmetric family; prior causal
trace fixture).

---

## Classifications

```
SMC_OPTICAL_ONLY_MAX_MEAN_L1 = 0.15
SMC_MATCH_THRESHOLD = 0.22
SMC_ALWAYS_GENERALIZES_ACROSS_OPTICAL_ONLY_DIFFERENCES = YES
OPTICAL_CAN_CHANGE_PSC_CANDIDATE_SET = YES
OPTICAL_CAN_CHANGE_PSC_CANDIDATE_SCORE = YES
OPTICAL_CAN_CHANGE_PSC_ORDERING = YES
OPTICAL_CAN_CHANGE_PSC_WINNER = YES
OPTICAL_CAN_CHANGE_MOTOR_PROPOSAL = YES
OPTICAL_CAN_CHANGE_FINAL_ACTION = YES
PSC_OPTICAL_SENSITIVITY_MAX_LEVEL = 5
OPTICAL_PSC_COUNTEREXAMPLE = FOUND
COUNTEREXAMPLE_SURVIVES_PSC_OFF_ON_PROTOCOL = YES
NATURALISTIC_COUNTERFACTUAL_FOUND = YES
V3_CAN_PROVE_OPTICAL_PSC_CAUSALITY = PARTIAL
```

```
BETA3_REFERENCE_MODIFIED = NO
SCIENTIFIC_SEMANTICS_CHANGED = NO
RUNTIME_SEMANTICS_CHANGED = NO
PSC_SEMANTICS_CHANGED = NO
SMC_SEMANTICS_CHANGED = NO
PE_SEMANTICS_CHANGED = NO
OPTICAL_WEIGHTS_ADDED = NO
SEMANTIC_COLOR_MEANING_ADDED = NO
GIT_PUSH = NO
```
