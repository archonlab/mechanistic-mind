# HISTORICAL SENSORIMOTOR SELECTION — Scientific Investigation Report

**Date:** 2026-09-21  
**Repo:** local project tree  
**Baseline biography untouched:** `psyweb-20260921T064313.398170Z-f82f5a38`  
**Audit:** `docs/HISTORICAL_SENSORIMOTOR_SELECTION_AUDIT.md`  
**Data:** `results/mm_historical_sensorimotor_selection/`

---

## PART A — Architecture audit

### Graph before inventing anything

```
accessible O_t
  -> compression / prospection / TPS retrieve & compose
  -> scenario groups with evidence (historical_support, reliability, depth)
  -> compete_scenarios -> selected locomotion

accessible O_(t-1) + M_(t-1) + O_t
  -> SMC update: (S,M) -> mean deltaS

at selection (SMC on, not withheld):
  M_i -> SMC query -> delta_hat_i -> O'_i = clip(O+delta_hat)
       -> scenario.historical_support := SMC_record.support   # NOT history(O')
       -> O'_i stored as predicted_state_fragments only
```

### Hypothesized bridge

`M -> deltaO -> O' -> query existing history with O' -> historical_support -> PSC -> selection`

### Audit conclusion

| Edge | Status |
|------|--------|
| Action-conditioned deltaS prediction | Present |
| O' construction | Present |
| O' -> history query -> PSC evidence | **Absent** |
| SMC record support -> PSC evidence | Present |
| Reward/value/goal scalar | Not present (not added) |

STOP condition honored: missing O'-history selection edge was **not** invented.

---

## PART B — Experiment design

### Ecology

Cognition-loop synthetic accessible sensorimotor ecology (deterministic exo/vest/prop consequences of composite motor). No GT agent identity/distance/bearing. Internal funnel primary. Macroscopic Tiktaalik approach metrics not optimized.

### Phases

| Phase | PSC | SMC | Motor source |
|-------|-----|-----|--------------|
| A EXPERIENCE | OFF (LEGACY_FIRST) | ON | Documented exploration schedule (loco+neck cycle) |
| B PROSPECTION | ON (SCENARIO_COMPETITION) | ON | Real PSC / composite factorization |

Activation tick **T0 = 1000**. No reset (Gate 2 verified).  
Calibration chose Phase A=1000, Phase B=1500 after occupancy/learning probes at 500/1000/2500/5000.

### Conditions (paired by seed)

A FULL_BRIDGE · B PREDICTION_WITHHELD · C MOTOR_SHUFFLE · D HISTORY_CONTROL (O' probe permute only) · E PSC_FROM_START · F SMC_OFF

### Seeds

`[101, 202, 303, 404, 505, 606, 707, 733, 808, 909]` (n=10; 733 case study only)

---

## PART C — Internal results (funnel)

Median over 10 seeds (Phase B = 1500 ticks when multi-candidate exists):

| Funnel stage | A | B | C | E | F |
|--------------|--:|--:|--:|--:|--:|
| Multi-candidate | 1500 | 1500 | 1500 | **0** | 1500 |
| Predicted futures differentiated | 1500 | 1500 | **0** | 0 | 0 |
| SMC support differentiated | 1500 | 1500 | **0** | 0 | 0 |
| O'-history differentiated (logging-only) | ~1416 | ~same | 0 | n/a | 0 |
| Selected = max SMC support | ~441 | ~410 | 0 | n/a | 0 |

Rates (A): future-diff|preds = 1.00; SMC-diff|multi = 1.00; O'-hist-diff|preds median = 0.94; select-max-SMC|diff median = **0.29**.

### Four-stage chain

1. Different motors -> different predicted futures? **YES** (destroyed by shuffle).
2. Different futures -> different historical support? SMC-record **YES**; O'-keyed probe **YES** (latent).
3. Support reaches PSC? SMC-record **YES**; O'-keyed **NO** (edge missing).
4. Removing bridge changes selection? WITHHELD vs FULL: median delta select-max rate = **0.007**; median selection-hist L1 = **0.011** → **negligible**.

---

## PART D — Behavioral results

Cognition ecology only. No CONTINUE/REVERSE optimization. Baseline seed-733 biography untouched. Head-domain (A): NECK_LEFT positive delta exo_0 sign rate median ≈ **0.21**.

---

## PART E — Developmental history

Experience-first (A): multi-candidate median **1500**, Phase A occupancy ~208–256.  
PSC-from-start (E): multi-candidate median **0**, final SMC occupancy **13** (collapse).

**DEVELOPMENTAL_HISTORY_EFFECT_DEMONSTRATED** — prior diverse non-PSC experience enables later multi-candidate competition in this ecology. Not the same as O'-history selection.

---

## PART F — Representative biographies

### Differentiated SMC support and selected = max support

TICK 1100 — synthetic cognition agent
SELECTION SOURCE: COMPOSITE_FACTORIZED
COMPETITION OUTCOME: DOMINANT_SCENARIO
WITHHELD: False

PSC CANDIDATES
  WAIT
    predicted deltaS: (near-0 on compact channels)
    SMC support/reliability: 10 / 0.9997998644599817
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=12 differentiated=True
    selected: True
  MOVE:N
    predicted deltaS: exo_1:0.0132
    SMC support/reliability: 6 / 0.998948823768085
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=12 differentiated=True
    selected: False
  MOVE:S
    predicted deltaS: exo_0:0.02, exo_1:-0.12
    SMC support/reliability: 5 / 0.9994518368267155
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=12 differentiated=True
    selected: False
  MOVE:E
    predicted deltaS: exo_0:0.12, exo_2:-0.03
    SMC support/reliability: 5 / 0.9992025180541665
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=12 differentiated=True
    selected: False
  MOVE:W
    predicted deltaS: (near-0 on compact channels)
    SMC support/reliability: 8 / 0.9998287368516942
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=12 differentiated=True
    selected: False

SELECTION: WAIT

INTERPRETATION
- action-conditioned prediction: RECORDED
- SMC support differentiation: RECORDED
- O'-history probe: RECORDED (logging-only)
- SMC enrichment reached PSC: RECORDED
- selection depended on that evidence: ASSOCIATED at best — NOT_ESTABLISHED (WITHHELD)

---

TICK 1200 — synthetic cognition agent
SELECTION SOURCE: COMPOSITE_FACTORIZED
COMPETITION OUTCOME: INCOMPARABLE
WITHHELD: False

PSC CANDIDATES
  WAIT
    predicted deltaS: (near-0 on compact channels)
    SMC support/reliability: 2 / 0.9999694124338232
    status: LOW_SUPPORT
    O-prime history probe (logging-only): matched_actions=5 support_spread=4 differentiated=True
    selected: False
  MOVE:N
    predicted deltaS: exo_1:0.0236
    SMC support/reliability: 5 / 0.9952777447253917
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=4 differentiated=True
    selected: False
  MOVE:S
    predicted deltaS: exo_0:0.02, exo_1:-0.12
    SMC support/reliability: 3 / 0.9989305054587314
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=4 differentiated=True
    selected: False
  MOVE:E
    predicted deltaS: exo_0:0.12, exo_2:-0.03
    SMC support/reliability: 2 / 0.9999277341098434
    status: LOW_SUPPORT
    O-prime history probe (logging-only): matched_actions=5 support_spread=4 differentiated=True
    selected: False
  MOVE:W
    predicted deltaS: exo_0:-0.12, exo_2:0.03
    SMC support/reliability: 5 / 0.9998166913381703
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=4 differentiated=True
    selected: True

SELECTION: MOVE:W

INTERPRETATION
- action-conditioned prediction: RECORDED
- SMC support differentiation: RECORDED
- O'-history probe: RECORDED (logging-only)
- SMC enrichment reached PSC: RECORDED
- selection depended on that evidence: ASSOCIATED at best — NOT_ESTABLISHED (WITHHELD)

---

TICK 1300 — synthetic cognition agent
SELECTION SOURCE: COMPOSITE_FACTORIZED
COMPETITION OUTCOME: INCOMPARABLE
WITHHELD: False

PSC CANDIDATES
  WAIT
    predicted deltaS: (near-0 on compact channels)
    SMC support/reliability: 18 / 0.9997864518507807
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: True
  MOVE:N
    predicted deltaS: exo_1:0.12
    SMC support/reliability: 2 / 0.9999475521547897
    status: LOW_SUPPORT
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: False
  MOVE:S
    predicted deltaS: exo_0:0.02, exo_1:-0.12
    SMC support/reliability: 3 / 0.999686842383192
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: False
  MOVE:E
    predicted deltaS: exo_0:0.12, exo_2:-0.03
    SMC support/reliability: 9 / 0.999719541470501
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: False
  MOVE:W
    predicted deltaS: (near-0 on compact channels)
    SMC support/reliability: 1 / 0.5
    status: LOW_SUPPORT
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: False

SELECTION: WAIT

INTERPRETATION
- action-conditioned prediction: RECORDED
- SMC support differentiation: RECORDED
- O'-history probe: RECORDED (logging-only)
- SMC enrichment reached PSC: RECORDED
- selection depended on that evidence: ASSOCIATED at best — NOT_ESTABLISHED (WITHHELD)

---


### Differentiated support but selected ≠ max SMC support

TICK 1050 — synthetic cognition agent
SELECTION SOURCE: COMPOSITE_FACTORIZED
COMPETITION OUTCOME: INCOMPARABLE
WITHHELD: False

PSC CANDIDATES
  WAIT
    predicted deltaS: (near-0 on compact channels)
    SMC support/reliability: 1 / 0.5
    status: LOW_SUPPORT
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: False
  MOVE:N
    predicted deltaS: exo_1:0.12
    SMC support/reliability: 1 / 0.5
    status: LOW_SUPPORT
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: True
  MOVE:S
    predicted deltaS: exo_0:0.02, exo_1:-0.12
    SMC support/reliability: 3 / 0.9986370960869144
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: False
  MOVE:E
    predicted deltaS: exo_0:0.12, exo_2:-0.03
    SMC support/reliability: 2 / 0.9983227978783822
    status: LOW_SUPPORT
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: False
  MOVE:W
    predicted deltaS: (near-0 on compact channels)
    SMC support/reliability: 7 / 0.9999250111873601
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: False

SELECTION: MOVE:N

INTERPRETATION
- prediction/support: RECORDED
- selection depended on SMC support: NOT_ESTABLISHED

---

TICK 1150 — synthetic cognition agent
SELECTION SOURCE: COMPOSITE_FACTORIZED
COMPETITION OUTCOME: INCOMPARABLE
WITHHELD: False

PSC CANDIDATES
  WAIT
    predicted deltaS: (near-0 on compact channels)
    SMC support/reliability: 6 / 0.9998921325664808
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: True
  MOVE:N
    predicted deltaS: exo_1:0.0297
    SMC support/reliability: 8 / 0.9952826694270895
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: False
  MOVE:S
    predicted deltaS: exo_0:0.02, exo_1:-0.12
    SMC support/reliability: 1 / 0.5
    status: LOW_SUPPORT
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: False
  MOVE:E
    predicted deltaS: exo_0:0.12, exo_2:-0.03
    SMC support/reliability: 3 / 0.9998253843453937
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: False
  MOVE:W
    predicted deltaS: (near-0 on compact channels)
    SMC support/reliability: 5 / 0.9999139996804512
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=11 differentiated=True
    selected: False

SELECTION: WAIT

INTERPRETATION
- prediction/support: RECORDED
- selection depended on SMC support: NOT_ESTABLISHED

---

TICK 1250 — synthetic cognition agent
SELECTION SOURCE: COMPOSITE_FACTORIZED
COMPETITION OUTCOME: INCOMPARABLE
WITHHELD: False

PSC CANDIDATES
  WAIT
    predicted deltaS: (near-0 on compact channels)
    SMC support/reliability: 6 / 0.9998920468700578
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=16 differentiated=True
    selected: True
  MOVE:N
    predicted deltaS: exo_1:0.12
    SMC support/reliability: 2 / 0.9999475521547897
    status: LOW_SUPPORT
    O-prime history probe (logging-only): matched_actions=5 support_spread=16 differentiated=True
    selected: False
  MOVE:S
    predicted deltaS: exo_0:0.02, exo_1:-0.12
    SMC support/reliability: 3 / 0.999654586167816
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=16 differentiated=True
    selected: False
  MOVE:E
    predicted deltaS: exo_0:0.12, exo_2:-0.03
    SMC support/reliability: 9 / 0.999719541470501
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=16 differentiated=True
    selected: False
  MOVE:W
    predicted deltaS: (near-0 on compact channels)
    SMC support/reliability: 6 / 0.9999122050331907
    status: MATCH
    O-prime history probe (logging-only): matched_actions=5 support_spread=16 differentiated=True
    selected: False

SELECTION: WAIT

INTERPRETATION
- prediction/support: RECORDED
- selection depended on SMC support: NOT_ESTABLISHED

---


## PART G — Scientific verdict

1. `ACTION_CONDITIONED_PREDICTIONS_AVAILABLE`
2. `HISTORICAL_SUPPORT_DIFFERENTIATION_DEMONSTRATED` (SMC-record + logging-only O' probe)
3. `SELECTION_USE_NOT_DEMONSTRATED` (WITHHELD ≈ FULL)
4. `PSC_SELECTION_EDGE_MISSING` for hypothesized `O' -> history query -> PSC`
5. `DEVELOPMENTAL_HISTORY_EFFECT_DEMONSTRATED` (experience-first vs PSC-from-start)

Charter outcome **B** (+ **D** for the O'-keyed edge).  
Do **not** claim `HISTORICAL_SENSORIMOTOR_SELECTION_DEMONSTRATED`.

---

## PART H — Next mechanistic edge (not implemented)

```
O'_i = apply(O_t, delta_hat(M_i))
   --missing--> predict_one_step(prospection, O'_i, ...) / compression.predict(O'_i, ...)
   --missing--> write that support into scenario evidence
   ----------> compete_scenarios
```

Any future wiring must keep WITHHELD/shuffle/history-control and prove selection change before claiming a selection bridge. No reward/value scalar.

---

## PART I — Performance / determinism / gates

Perf: 100 ticks ≈ 0.264s; 1000 ticks ≈ 5.518s. Capacity-bounded.  
Determinism: seed 202 EXACT_MATCH.

| Gate | Status | Note |
|-----:|--------|------|

| 1 | PASS | SMC learning during PSC-OFF Phase A — updates≈phase_a-2; occupancy grows |
| 2 | PASS | PSC activation does not reset stores — snap before/after equal occupancy/updates |
| 3 | PASS | Exact activation tick recorded — T0=1000 |
| 4 | PASS | Candidate motors produce action-conditioned futures — future_diff rate median 1.0 |
| 5 | PASS | No GT distance/bearing/identity in cognition — synth accessible obs only; audit_cognition_payload |
| 6 | PASS_LOGGING_ONLY | Historical support query uses existing organization — predict_one_step(O') — not selection-wired |
| 7 | PASS | No reward/value/goal scalar added — evidence vector unchanged |
| 8 | PASS | Predicted futures tested for support differentiation — SMC support + O' probe |
| 9 | PASS | Support reaching PSC separately observable — enrichment vs WITHHELD |
| 10 | PASS | WITHHELD cleanly removes bridge — condition B; selection L1 median ~0.01 |
| 11 | PASS | Motor-shuffle control — C: smc_diff median 0 |
| 12 | PASS | Experience-first vs PSC-from-start — E: multi_candidate median 0 |
| 13 | PASS | Multi-seed paired — 10 seeds |
| 14 | PASS_PARTIAL | Head and locomotion domains — loco primary; head query rates recorded |
| 15 | PASS_PARTIAL | Analyzer reconstructs bridge — section + dedicated report; not full TwoAgent Analyzer Next |
| 16 | PASS | Macroscopic behavior not optimized — cognition ecology; no CONTINUE/REVERSE objective |
| 17 | PASS | Baseline f82f5a38 untouched — dir present |
| 18 | PASS | Runtime bounded after saturation — SMC capacity 256; Phase A occ at capacity |
| 19 | PASS | Determinism EXACT_MATCH — seed 202 replay |

---

## Methods honesty

1. Phase A used an explicit exploration schedule after LEGACY/endogenous collapse starved multi-candidate PSC. Documented experience generation — not claimed curiosity.
2. O'-history metrics are diagnostic, not selection inputs.
3. Not a full TwoAgent Analyzer Next macroscopic suite.
4. No new cognition mechanism invented to force selection success.
