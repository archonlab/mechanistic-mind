# SIGNAL-CONDITIONED SENSORIMOTOR SELECTION

Observation + Analyzer + Observer UI for whether **agent-accessible physical
signal structure** participates in sensorimotor prediction and PSC selection.

This task does **not** redesign cognition, add communication semantics, or
wire L/R bands into SMC.

## 1. Path audit (authoritative)

| Stage | `local.FIELD_A/B` | `osc_l_*` / `osc_r_*` |
|-------|-------------------|------------------------|
| PHYSICAL WORLD | AVAILABLE | AVAILABLE |
| RECEIVER | AVAILABLE (site mean) | AVAILABLE (L/R receptors) |
| AGENT-ACCESSIBLE OBSERVATION | AVAILABLE | AVAILABLE |
| ObservationReceipt | AVAILABLE | AVAILABLE |
| SMC `SENSORY_CHANNELS` | AVAILABLE | **NOT_AVAILABLE** |
| Predicted ΔO / O′ | AVAILABLE | **NOT_AVAILABLE** |
| O′ history / PSC via HSS | via FIELD in O′ | **NOT via osc bands** |

Source of truth for SMC channels:

`mechanistic_mind/physical_system/sensorimotor_consequence.py` → `SENSORY_CHANNELS`

Osc fragments enter cognition via `cognition_osc_fragments` in
`observation.py`, but are **not** listed in `SENSORY_CHANNELS`. This task
**does not** silently add them.

## 2. Evidence join (no second timeline)

Analyzer aggregates:

- `scientific_observations.jsonl` → agent-accessible signal state
- `scientific_decisions.jsonl` → `sensorimotor_consequence` + `historical_sensorimotor_selection`

Module: `mechanistic_mind/scientific_v3/analyzer_next/signal_conditioned_selection.py`

Signal components of predicted Δ taken only from:

`local.FIELD_A`, `local.FIELD_B`

Bilateral `total_L` / `total_R` / asymmetry from `osc_*` are tagged:

`DERIVED_DISPLAY_ONLY` / `not_an_agent_variable`

Geometry remains OBSERVER_ONLY and is never fed into the cognition evidence chain.

## 3. Funnel

```
SIGNAL_PRESENT
→ MULTI_CANDIDATE
→ SIGNAL_SMC_PREDICTIONS_AVAILABLE
→ SIGNAL_FUTURES_DIFFERENTIATED
→ O_PRIME_HISTORY_QUERIED
→ HISTORICAL_SUPPORT_DIFFERENTIATED
→ HISTORICAL_EVIDENCE_AVAILABLE_TO_PSC
→ SELECTED_CANDIDATE
→ FINAL_SELECTION_DIFFERS_FROM_WITHHELD_COUNTERFACTUAL  (if authoritative)
```

WITHHELD stratification by signal state is labeled **SIGNAL-CONDITIONED ASSOCIATION**,
not “signal caused selection.”

## 4. Reference re-analysis (read-only)

Run: `psyweb-20260921T100237.603374Z-cb44bb52` (seed 111)

Status: **RECORDED**

Gates:

| Gate | Result |
|------|--------|
| A signal→SMC join | PASS |
| B differentiated FIELD futures | PASS |
| C O′ history join | PASS |
| D historical available to PSC | PASS |
| E selected motor joinable | PASS |
| F no-vision subset | PASS |
| L/R bands reach SMC | **NOT_AVAILABLE** |

Artifacts: `results/observer_performance/signal_conditioned_seed111/`

## 5. Observer Web UI

- Product: `signal_sensorimotor` (demand-driven)
- API: `GET /api/diagnostics/signal-sensorimotor`
- Panel: **SIGNAL → PREDICTION → PSC** (`SignalSensorimotorPanel.tsx`)
- MINIMAL: DEFERRED (Tier-0 scientific evidence unchanged)
- NORMAL/FULL: live FIELD + L/R display (derived label) + PSC candidate signal Δ

## 6. Future causal control (documentation only)

Do **not** implement in this task:

| Condition | Intent |
|-----------|--------|
| A NORMAL | baseline bilateral receptors |
| B L/R SWAPPED | isolate spatial structure |
| C L/R SYMMETRIZED | destroy asymmetry, preserve energy |
| D SIGNAL OFF | abolish signal |

Preserve overall signal-energy distribution between A/B/C so the manipulation
isolates spatial structure rather than mere presence.

Potential future claim if supported:

`BILATERAL SIGNAL STRUCTURE CAUSALLY PARTICIPATES IN MOTOR SELECTION`

Requires wiring osc bands into SMC first (separate task) **or** a physical
receiver swap that still lands in FIELD-accessible SMC channels.

## 7. Claim boundary

Allowed if supported: physical signal exposure; FIELD action-conditioned
prediction; differentiated predicted FIELD futures; historical support;
signal-conditioned PSC association; no-vision signal subset.

**Not established:** understands other agent; left/right semantics; voice
following; communication; language; osc L/R participation in SMC/O′.

## 8. Tests

`tests/test_signal_conditioned_selection.py`
