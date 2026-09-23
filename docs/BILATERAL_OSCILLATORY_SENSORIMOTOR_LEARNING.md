# BILATERAL OSCILLATORY SENSORIMOTOR LEARNING

Sensory-channel extension of the existing action-conditioned Sensorimotor
Consequence Model (SMC) so agent-accessible bilateral oscillatory receptors
participate in prediction → O′ → history → PSC.

No spatial concepts, source direction, communication semantics, goals, reward,
or target-following were added. Physical receiver and signal propagation are
unchanged. PSC / historical-retrieval semantics are unchanged.

## 1. Channel audit

Authoritative keys from `cognition_osc_fragments`:

| Key | Count | Range | Notes |
|-----|-------|-------|-------|
| `osc_l_0` … `osc_l_5` | 6 | [0,1] | left receptor bands / `field_cap` |
| `osc_r_0` … `osc_r_5` | 6 | [0,1] | right receptor bands / `field_cap` |

- Present when oscillatory signaling enabled + perception ON + `OSC_BANDS` exist
- Empty dict otherwise (conditionally present)
- Identical band counts for all agents (`n_bands=6` default)
- Already in agent-accessible observation and `ObservationReceipt`

## 2. SMC change

Before (`BASE_SENSORY_CHANNELS`):

```
exo_0, exo_1, exo_2, local.FIELD_A, local.FIELD_B,
vest_0, vest_1, prop_neck_0, prop_neck_1
```

After (default `SENSORY_CHANNELS`):

```
BASE + osc_l_0..5 + osc_r_0..5   (21 channels)
```

Implementation:

- `mechanistic_mind/physical_system/sensorimotor_consequence.py`
- Store-scoped `channel_list` via `channels_for_store`
- `empty_store(bilateral=True|False)` / `set_bilateral`
- CognitionConfig: `sensorimotor_consequence_bilateral: bool = True`
  - `False` = **WITHHELD**: osc remain in observation/receipts; excluded from SMC/O′ only

No special bilateral predictor. No `if R>L: TURN…` logic.

## 3. O′ / history / PSC

Existing path:

`construct_o_prime` → `apply_predicted_to_observation` uses `SENSORY_CHANNELS`

When bilateral ON, predicted Δosc enters O′ `predicted_fields` and the existing
O′ historical-selection bridge / PSC evidence attachment without a signal score.

## 4. Analyzer

`signal_conditioned_selection.py` now reports bilateral funnel:

- BILATERAL_SMC_PREDICTIONS_AVAILABLE
- BILATERAL_FUTURES_DIFFERENTIATED
- BILATERAL_O_PRIME_AVAILABLE
- BILATERAL_HISTORY_QUERIED
- BILATERAL_HISTORY_SUPPORT_DIFFERENTIATED
- BILATERAL_EVIDENCE_AVAILABLE_TO_PSC
- NO_VISION_BILATERAL_FUTURES_DIFFERENTIATED

Historical seed-111 (`…cb44bb52`) remains valid as **pre-extension**
(osc NOT_AVAILABLE to SMC). New runs measure bilateral.

Derived Analyzer diagnostics (`total_L`, asymmetry, Δasym) remain
DERIVED — not agent variables.

## 5. Observer UI

Panel **SIGNAL → PREDICTION → PSC**:

- BILATERAL SMC status: LEARNING / ACTIVE / WITHHELD / NOT AVAILABLE
- L′ / R′ mini-bars + ΔASYM [DERIVED] per candidate
- NOW → PREDICTED AFTER SELECTED MOTOR ear view
- Demand-driven product `signal_sensorimotor` (MINIMAL = DEFERRED)

## 6. Acceptance

### Synthetic

`ACTION_CONDITIONED_BILATERAL_PREDICTION_DEMONSTRATED`

Same S, motors MOVE:N vs MOVE:E → different predicted osc_l/r futures;
O′ lists osc predicted_fields; WITHHELD excludes osc from Δ.

### Fresh wet-world (seed 111, NEW run)

`psyweb-20260921T111535.617867Z-5ada1ee0`

- Phase A 300 ticks PSC OFF → Phase B 200 PSC ON (no reset)
- decisions 1000; with osc Δ 998
- GATE_LR_bands_reach_SMC: **PASS**
- GATE_BILATERAL_FUTURES_DIFFERENTIATED: **PASS**
- BILATERAL_SMC_PREDICTIONS_AVAILABLE: 400
- BILATERAL_FUTURES_DIFFERENTIATED: 214
- BILATERAL_EVIDENCE_AVAILABLE_TO_PSC: 400
- NO_VISION_BILATERAL_FUTURES_DIFFERENTIATED: 24

Artifacts: `results/observer_performance/bilateral_osc_smc_seed111/`

## 7. Performance (microbench)

| Mode | channels | update µs | query µs |
|------|----------|-----------|----------|
| WITHHELD | 9 | ~45 | ~40 |
| bilateral ON | 21 | ~88 | ~77 |

≈2× SMC update/query cost; no science change for optimization.

## 8. Claim boundary

**Supported:** bilateral sensing; action-conditioned bilateral prediction;
differentiated predicted bilateral futures; bilateral in O′; historical
support; evidence available to PSC; no-vision bilateral differentiation
(association).

**NOT established:** spatial / left-right concepts; source localization;
follows voice; communication; language; intentional signaling.

## 9. Next experiment (NOT implemented)

NORMAL / L/R SWAPPED / L/R SYMMETRIZED / SIGNAL OFF — energy-matched A–C —
to test causal participation of bilateral structure.
