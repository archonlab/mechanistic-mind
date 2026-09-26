# Action-Conditioned Sensorimotor Consequence Model

**Date:** 2026-09-21  
**Status:** Phase-1 implemented (default **OFF**)  
**Baseline biography (untouched):** `psyweb-20260921T064313.398170Z-f82f5a38`  
**Results:** `results/mm_sensorimotor_consequence/`

---

## PART A — Architecture audit

### Accessible observation channels used
Compact consequence vector (agent-accessible only; no Observer GT):

| Channel | Role |
|---------|------|
| `exo_0/1/2` | Near-field optical / exteroceptive |
| `local.FIELD_A/B` | Local field samples |
| `vest_0/1` | Vestibular |
| `prop_neck_0/1` | Neck proprioception |

Body/internal channels remain in full PSC fragments but are omitted from the compact ΔS vector to keep capacity on exteroceptive calibration.

### Existing prediction / selection
- **Prospective composition** already learns `(antecedent, action_token) → consequent`.
- **PSC** selects by historical **support / reliability / depth** — no utility over ΔS direction.
- Legitimate bridge: richer motor-conditioned MATCH → higher support/reliability.  
  **Not** inventing preference for optical increase / approach / SEEK.

### Stop-condition stance
- If predictions are available as MATCH evidence → **PREDICTION BRIDGE ESTABLISHED**.
- Directional value over ΔS → **SELECTION BRIDGE MISSING** (and stays missing unless a separate justified mechanism is designed).

---

## PART B — Implementation

| Piece | Path |
|-------|------|
| Core store | `mechanistic_mind/physical_system/sensorimotor_consequence.py` |
| Cognition wire | `mechanistic_mind/physical_system/cognition.py` (default OFF) |
| Mechanism registry | `sensorimotor_consequence_model` |
| Observer API | `GET /api/diagnostics/sensorimotor-consequence` |
| React panel | `SensorimotorConsequencePanel.tsx` (sensor inspector / near-field card) |
| V3 decision block | `SENSORIMOTOR_CONSEQUENCE_QUERIED` / `PREDICTED` / `UPDATED` on decision receipt |
| Analyzer section | `ACTION-CONDITIONED SENSORIMOTOR MODEL` (+ existing SENSORIMOTOR CONSEQUENCE ANALYSIS) |
| Tests | `tests/test_sensorimotor_consequence_model.py` |

### Config flags (all default safe)
- `cognition.sensorimotor_consequence_model` — enable learn/query
- `cognition.sensorimotor_consequence_withhold_from_psc` — learn but do not feed PSC
- `cognition.sensorimotor_consequence_shuffle_motors` — control: scramble motor labels at learn/query

### Explicit non-goals
No SEEK / FOLLOW / APPROACH_REWARD / TURN_TOWARD_TARGET / ERROR_MINIMIZATION_GOAL.  
No GT bearing/distance. No treating CONTINUE/REVERSE rate change as success.

---

## PART C — Experiments

### Exp1 — Head → exo calibration
Synthetic accessible consequences: `NECK_LEFT → Δexo_0↑`, `NECK_RIGHT → Δexo_2↑`.

| Condition | Result |
|-----------|--------|
| Enabled | MATCH/LOW_SUPPORT with correct-signed Δ |
| Disabled ablation | UNKNOWN, zero updates |

**Verdict:** `ACTION_CONDITIONED_SENSORY_PREDICTION_DEMONSTRATED`

### Exp2 — Locomotion + motor-shuffle control
Distinct ΔS per `MOVE:N/S/E/W`. Shuffle control breaks label→consequence binding.

**Verdict:** `ACTION_CONDITIONING_SUPPORTED_BY_SHUFFLE_CONTROL`

### Exp3 — Cognition ablations (short, not full TwoAgent world)
Variants: disabled / enabled / shuffle / withhold-from-PSC (80 ticks, synthetic obs).

| Check | Result |
|-------|--------|
| Learning when enabled | YES |
| No learning when disabled | YES |
| Withhold blocks PSC source flag | YES |
| Prospection availability | `PROSPECTION_AVAILABILITY_DEMONSTRATED` |
| Behavioral use vs baseline CONTINUE≈68% / REVERSE≈4% | **not claimed** — `BEHAVIORAL_USE_NOT_DEMONSTRATED` |

Full two-agent Observer runs with Analyzer Next on new seeds remain optional follow-up; baseline `f82f5a38` must not be rewritten.

Artifacts: `results/mm_sensorimotor_consequence/exp{1,2,3}_*.json`, `SUMMARY.json`.

---

## PART D — Scientific verdict

1. **ACTION_CONDITIONED_SENSORY_PREDICTION_DEMONSTRATED** — synthetic Exp1/Exp2 with shuffle control.
2. **PROSPECTION_AVAILABILITY_DEMONSTRATED** — queries/candidates when enabled; withhold flag works.
3. **PREDICTION BRIDGE ESTABLISHED** — dual-write into prospective transitions + optional PSC MATCH enrichment (support/reliability only).
4. **SELECTION BRIDGE MISSING** — no directional preference over ΔS; PSC still does not value “optical increase.”
5. **BEHAVIORAL_USE_NOT_DEMONSTRATED** — no justified claim that organisms *use* (O,M)→ΔO for corrective selection in the biography run.

Organisms can **receive** sensory consequences of motion (prior Analyzer Next). Strong **use** of predicted ΔS for corrective selection remains **NOT_ESTABLISHED**.

---

## PART E — Perf / determinism

| Ticks | Enabled ms | Disabled ms | Overhead |
|------:|-----------:|------------:|---------:|
| 100 | ~246 | ~170 | ~44% |
| 1000 | ~2362 | ~1783 | ~32% |

~2.4 ms/tick cognition-only overhead on this machine (synthetic obs).  
**Determinism:** EXACT_MATCH on action sequence replay with fixed rng (`determinism.json`).

---

## PART F — Gates checklist

| Gate | Status |
|------|--------|
| No semantic reward / seek tokens in core module | PASS (test) |
| No GT channels in SENSORY_CHANNELS | PASS (test) |
| Temporal alignment Motor(T)→ΔObs(T→T+1) | PASS (test) |
| Bounded capacity + eviction | PASS (test) |
| Head and loco learnable | PASS (test) |
| Motor shuffle harms conditioning | PASS (test + Exp2) |
| PSC availability + withhold ablation | PASS (test + Exp3) |
| Does not hardcode approach behavior | PASS (test) |
| Determinism EXACT_MATCH when enabled | PASS |
| Baseline biography untouched | PASS (path still `.live-…f82f5a38`) |
| No git push | PASS (local only) |

---

## How to enable in Observer
Mechanism list → `sensorimotor_consequence_model` ON (or config `cognition.sensorimotor_consequence_model: true`).  
Panel: **CURRENT MM — SENSORIMOTOR CONSEQUENCES** under near-field / sensor inspector.
