# Beta 3.1 — Optical → predictive → PSC causal trace

**BETA31_OPTICAL_TO_PSC_CAUSAL_TRACE = PASS**

Forensic audit. Production semantics unchanged. Not a claim that Tiktaalik
“sees colour” or “plans with colour”.

```
BETA3_REFERENCE_MODIFIED = NO
SCIENTIFIC_SEMANTICS_CHANGED = NO
RUNTIME_SEMANTICS_CHANGED = NO
PSC_SEMANTICS_CHANGED = NO
OPTICAL_WEIGHTS_ADDED = NO
SEMANTIC_COLOR_MEANING_ADDED = NO
GIT_PUSH = NO
```

Primary mode: **OBSERVED_COMPOSITE**. SMC / compression / PE apply to both
motor-resolution modes. LOCO_FACTORIZED competition was not fully re-run.

Harness: `experiments/run_beta31_optical_to_psc.py`  
Tests: `tests/test_optical_to_psc_causal_trace.py`  
Artifacts: `results/beta31_optical_to_psc/`

---

## A. Canonical causal path

```
sample_near_field
  → surface_c* floats in accessible_observation
  → run_cognition_before_action(observation)
       pc.observe / pc._sig (round 4)
       pe.learn / pe.retrieve (member = same _sig; classes = continuation Linf)
       smc.update / smc.query (5-bin midpoints; FAMILY_VISUAL includes surface_c*)
       pr.learn_transition / compose_trajectories (5-bin _q transition keys)
       oc.collect_observed_candidates → O′ + HSS → compete_scenarios
       motor resolution
```

No second vision or test PSC.

---

## B. Raw surface_c representation

RICH keys `surface_c{0,1,2}_{0,1,2}` are anonymous floats in
`accessible_observation`. They are on the SMC visual allowlist
(`FAMILY_VISUAL` in `sensorimotor_consequence.py`).

Example (controlled profile X): `surface_c0_* = 0.90`, `surface_c1_* = 0.10`,
`surface_c2_* = 0.90`.

---

## C. Quantization (empirical)

`background_context._quantize` / Eye PE: `int(clip01(v)*5)`  
bins: `[0,0.2)→0 … [0.8,1)→4`.

SMC: midpoint `(bin+0.5)/5` → `0.1, 0.3, 0.5, 0.7, 0.9`.

| Pair | raw | q5 | SMC key |
|---|---|---|---|
| A | 0.10 vs 0.50 | 0 vs 2 | **distinct** |
| B | 0.21 vs 0.29 | both 1 | **aliased** |

Compression `pc._sig` uses **round(v, 4)**, so pair B remains distinct there.
Researchers reading Tiktaalik Eye PE bins are **not** seeing the compression
identity. Pair B is the Eye-alias case: raw C0 0.21 vs 0.29 → same PE bin,
same SMC context, different compression signatures.

---

## D. SMC

**TRANSPORT YES.** `extract_sensory` copies every present `surface_c*` key.

**STORAGE DISTINCT** when 5-bin signatures differ (pair A; multichannel X/Y
→ two records).

**QUERY PARTIAL.** Exact `_sig_key` first, then mean L1 ≤ `SIM_THRESHOLD=0.22`
over **all 48** sensory channels. Multichannel X vs Y quantized L1 = **0.15**
`< 0.22`, so a motor learned only under Y still MATCH-es query(X, that motor).
That is expected generalization, not a vision bug.

---

## E. Predictive compression

**YES.** Full fragment including `surface_c*` is stored; identity is round-4
SHA. X vs Y: `03816caf85dc` vs `5603ed8dad09`. Pair B (0.21 vs 0.29) also
distinct.

---

## F. Predictive equivalence

Member identity = compression `_sig` (not 5-bin). Observation is **not**
globally binned. Classes group by **continuation L∞**. Visually different
states with similar Δ can share a class (expected MM PE). Retrieval is AABB
over member antecedents.

**RAW_OPTICAL_DISTINCTIONS_SURVIVE_PE = PARTIAL.**

---

## G. Prediction

Exact SMC query(X, mE) vs query(Y, mW) returns different `record_id` (SMC1 vs
SMC2) after conditioned training. Similarity also returns the cross-motor
record. So prediction **can** differ, and **can** alias.

---

## H. Prospective composition

`transition_key = sha(_q(antecedent, 5-bin)) || action`. Surface channels
participate. `MATCH_TOL=0.12` mean L1: X vs Y L1 **0.15 > 0.12**, so
soft-match does **not** merge the two optical profiles (unlike SMC 0.22).

Empty history: `compose_trajectories` yields no MATCH continuations
(naive run: `n_continuations=0`).

---

## I–L. PSC candidates, competition, motor, action

Conditioned fixture (production `smc.update` + `pr.learn_transition` +
`select_observed_composite_motor`):

| | X | Y |
|---|---|---|
| n_candidates | 2 | 2 |
| motors | MOVE:E+NECK_LEFT, MOVE:W+NECK_RIGHT | same |
| historical_support | 5 / 5 | 5 / 5 |
| selected | `L:MOVE:E\|N:NECK_LEFT\|…` | **same** |
| O′ surface carry | C0/C2 high, C1 low | C0/C2 low, C1 high |

**Boundary (not a PSC redesign request):**

1. SMC similarity attaches **both** empirical composites to **both** optical
   contexts.
2. O′ **carries current** `surface_c*` (`construct_o_prime`); candidate Δ is
   typically `exo_*`, so all motors at a tick share the same optical carry.
3. HSS queries **all locos from O′** and takes **argmax support**, so
   historical_support ties.
4. `compete_scenarios` therefore receives **identical evidence vectors**.

O′ optics still differ (carry). Competition **scores** do not. This fixture
does **not** produce a different selected composite or motor.

Naive / empty history: `OBSERVED_COMPOSITE` → `FALLBACK_LOCO` then factorized
endogenous action (`MOVE:S` at rng=0.41 for both). Optical signatures already
differ; PSC does not consult them yet.

---

## M. PSC-OFF accumulated history

`psc_off_ticks` turns competition ON at a tick **without resetting**
cognition stores. The fixture fills SMC/prospection first, then calls
production select: **SELECTED**, stores consumed. Optical SMC records
accumulated while competition is unused remain available.

---

## N. Controlled X/Y receipt

See `results/beta31_optical_to_psc/psc_candidate_diff.json`.

Strongest demonstration achieved:

- identical non-optical channels  
- only C0/C1/C2 profile X vs Y  
- conditioned SMC + prospection history  
- **O′ optical carry distinct**  
- **competition winner identical**

Not demonstrated: different selected prospective candidate / motor from
optics alone under OBSERVED_COMPOSITE + default SIM_THRESHOLD / HSS
aggregation.

---

## O. V3 observability

| Stage | |
|---|---|
| accessible optical | FULLY (compact observation receipts keep `surface_c*`) |
| SMC | PARTIAL (status/support/record_id on decisions) |
| PE | NOT OBSERVABLE |
| prediction / composition | PARTIAL |
| PSC candidates / winner | PARTIAL (`observed_composite_selection`) |
| **overall** | **PARTIAL** |

**PSC OPTICAL OBSERVABILITY GAP:** V3 can show `surface_c*` was present and a
composite was selected. It cannot prove after the run that `surface_c*`
caused the selection.

CORRELATED / SHUFFLED / UNIFORM still emit 9 `surface_c*` keys into
accessible observation (mapping sanity). No behavioural interpretation.

---

## P. Causal ladder

| STAGE | PRESENT | DISTINCT | CONSULTED | CAUSAL |
|---|---|---|---|---|
| accessible_observation | YES | YES | YES | YES |
| observation signature (5-bin Eye) | YES | YES | PARTIAL | PARTIAL |
| SMC | YES | YES | YES | PARTIAL |
| predictive compression | YES | YES | YES | YES |
| PE | YES | PARTIAL | YES | PARTIAL |
| prediction | YES | YES | YES | YES |
| prospective composition | YES | YES | YES | YES |
| PSC candidate construction | YES | PARTIAL | YES | PARTIAL |
| PSC competition | YES | NO | YES | NO |
| motor resolution | YES | NO | YES | NO |
| final action | YES | NO | YES | NO |

---

## Q. Information-loss boundaries

1. **5-bin SMC / Eye PE** aliases raw magnitudes in one bin (0.21 vs 0.29).
2. **SMC mean-L1 0.22 / 48 channels** generalizes across even extreme C0/C1/C2
   swaps (L1 0.15).
3. **HSS argmax over all locos from O′** equalizes historical_support when
   every O′ still MATCH-es some trained continuation.
4. **O′ carry** preserves optics in the hypothetical observation but does not
   by itself change lexicographic competition inputs.
5. Empty history: optics never consulted by OBSERVED_COMPOSITE (`FALLBACK_LOCO`).

---

## R. Scientific interpretation

`surface_c*` **does reach** accessible observation, SMC storage, compression,
PE member identity, and prospective transition keys. It is **consulted** in
those stores.

Under OBSERVED_COMPOSITE as currently implemented, a pure optical-profile
difference with conditioned history **need not change candidate scores or
selected motor**, because similarity + HSS aggregation wash out the
distinction at competition time while still carrying it in O′.

That is **not** “PSC ignores vision” and **not** “PSC plans with colour”.
It is: optical distinctions are **transported and stored**, **partially
used** in retrieval, and **not sufficient in this fixture to change
competition**.

Eye UI: treat **raw floats** and **5-bin PE** as different layers. Downstream
cognition is not “the PE bin only” (compression round-4) and not “raw floats
only” (SMC 5-bin + similarity).

---

## Classifications

```
SURFACE_C_REACHES_ACCESSIBLE_OBSERVATION = YES
SURFACE_C_REACHES_SMC = YES
SURFACE_C_REACHES_PREDICTIVE_COMPRESSION = YES
SURFACE_C_REACHES_PE = YES
SURFACE_C_REACHES_PREDICTION = YES
SURFACE_C_REACHES_PROSPECTIVE_COMPOSITION = YES
SURFACE_C_REACHES_PSC_CANDIDATES = YES
RAW_OPTICAL_DISTINCTIONS_SURVIVE_PE = PARTIAL
MULTICHANNEL_OPTICAL_PROFILE_SURVIVES = YES
PSC_CANDIDATES_ARE_OPTICALLY_SENSITIVE = PARTIAL
PSC_COMPETITION_IS_OPTICALLY_SENSITIVE = NO
MOTOR_RESOLUTION_CAN_BE_OPTICALLY_SENSITIVE = NO
FINAL_ACTION_CAN_BE_OPTICALLY_SENSITIVE = NO
PSC_CAN_USE_OPTICAL_HISTORY_ACCUMULATED_WHILE_OFF = YES
V3_PSC_OPTICAL_OBSERVABILITY = PARTIAL
```
