# HISTORICAL SENSORIMOTOR SELECTION — Architecture Audit

**Date:** 2026-09-21  
**Scope:** Read-only trace of existing Mechanistic Mind cognition.  
**Rule:** Do not invent a new reward/value/goal scalar. Stop before inventing a missing historical-support edge.

---

## 1. Historical / predictive stores (cognition-internal)

| Store | Module | What it holds | Agent-accessible? | Feeds PSC? |
|-------|--------|---------------|-------------------|------------|
| Prospective transitions | `research/prospective_composition.py` (`state["prospection"]`) | `(quantized antecedent, action) → consequent stats` with **support**, **reliability** | Yes (learned from accessible obs) | **Yes** — `predict_one_step` / `compose_trajectories` → scenarios |
| Predictive compression | `research/predictive_compression.py` (`state["compression"]`) | Compressed structures over fragments×action | Yes | **Yes** — `pc.predict` → retained predictions / fallback |
| Temporal predictive structure | TPS module | Temporal chains | Yes when enabled | Via entry steps / PCP into continuations |
| Predictive equivalence / relevance | PE / PRL | Equivalence classes | Yes when enabled | Into predictions list |
| Instrumental observation | IO | Emit→consequence | Separate | Predict only |
| **Sensorimotor consequence** | `physical_system/sensorimotor_consequence.py` | `(S_t, M_t) → mean ΔS` with support/reliability | Yes (accessible channels only) | **Partial** — see §4 |

No Observer GT (bearing, distance, agent id) enters these stores by design.

---

## 2. PSC candidate path (actual code)

```
accessible Observation O_t
  → compression / TPS / PE retrieve(O_t, action)     → predictions[]
  → prospection.compose_trajectories(O_t, actions)   → continuations[]
  → collect_scenario_groups / FSA                    → groups[action] = scenarios
       each scenario has evidence vector:
         (historical_support, reliability, depth)
         from transition MATCH edges — NOT utility
  → compete_scenarios: lexicographic dominance
  → selected first_action (locomotion under COMPOSITE_MOTOR_V1)
  → side channels (neck/osc) factorized after
```

Evidence dimensions are fixed in `scenario_competition._evidence_vector`:
`(historical_support, reliability, depth)`. No reward/value.

**PSC OFF (Phase A operationalization):**  
`cognition.prospective_selection = "LEGACY_FIRST"` (mechanism registry maps PSC toggle this way),  
while keeping learning paths active (`prospective_composition` learn_transition, compression learn, SMC update).  
LEGACY_FIRST uses list-position privilege among continuations — **not** dominance on historical support.  
Endogenous fallback remains when nothing matches.

---

## 3. Sensorimotor consequence path (actual code)

```
previous O_{t-1} + last_motor M_{t-1} + current O_t
  → smc.update → record (S, M) → mean ΔS   [Phase A learning]

at selection time:
  smc.query_candidates(O_t, loco_candidates)
  → for each M_i: predicted_delta, support, reliability, status
  → o_hat = apply_predicted_to_observation(O_t, predicted_delta)   # = O'_i
```

Dual-write (when SMC enabled): also `pr.learn_transition(prospection, O_{t-1}, motor_signature, O_t)`  
so ordinary prospection MATCH can condition on composite motor keys.

---

## 4. Hypothesized bridge vs what exists

### Hypothesized (this investigation)

```
M_i → predicted ΔO_i → O'_i
    → query EXISTING predictive history with O'_i
    → historical_support_i (familiarity / continuation evidence for that future)
    → PSC candidate evidence
    → selection
```

### What the code actually does today (`_enrich_groups_with_smc`)

```
M_i → SMC predicted ΔO_i → O'_i (stored as predicted_state_fragments)
    → scenario.historical_support := SMC record.support   # count of (S,M)→ΔS updates
    → scenario.reliability := SMC reliability
    → append scenario into groups[loco]
```

**Critical distinction:**  
The field named `historical_support` on SMC-injected scenarios is **SMC-local pathway support** (how often this action-conditioned ΔS was observed), **not** a query of prospective/compression history keyed by the hypothetical future observation `O'_i`.

`O'_i` is **constructed** and attached as `predicted_state_fragments`, but **no subsequent call** of the form:

- `pr.predict_one_step(prospection, O'_i, ·)`  
- `pc.predict(compression, O'_i, ·)`  
- soft-match of transitions by consequent ≈ `O'_i`

feeds that result back into the scenario evidence vector.

### Parallel existing path (not the hypothesis)

Ordinary `one_step_scenario(prospection, O_t, action)` already returns transition support for `(O_t, action)` when dual-write / normal learning filled that key. That is **present-state action-conditioned historical support**, not **future-state historical support**.

---

## 5. Answers to audit questions

1. **What historical stores exist?**  
   Prospection transitions, compression structures, TPS/PE/PRL (when on), SMC ΔS records, instrumental.

2. **Agent-accessible / cognition-internal?**  
   All of the above are cognition-internal and trained on accessible observations (plus SMC compact channel subset).

3. **Which can evaluate a hypothetical future sensory state?**  
   **APIs exist** that *could* be called with antecedent=`O'_i` (`predict_one_step`, `pc.predict`).  
   **Selection path does not call them with `O'_i` today.**

4. **Which already contribute to PSC?**  
   Prospection MATCH scenarios, compression retained predictions (fallback), SMC enrichment (as SMC-support scenarios), optional FSA/PCP/MAP branches.

5. **Can predicted ΔS become candidate future observation?**  
   **Yes** — `apply_predicted_to_observation` builds `O'_i`.

6. **Can that hypothetical observation query existing history?**  
   **Mechanically possible** via existing retrieve APIs.  
   **Not wired** into candidate evidence.

7. **Does resulting support reach candidate selection?**  
   SMC **record** support reaches selection (when not withheld).  
   History-query-on-`O'_i` support **does not** (edge absent).

8. **Missing graph edge**  
   ```
   O'_i  ──✗──▶  historical_support_query(prospection|compression)
                      │
                      ▼
                 PSC evidence vector
   ```
   Present instead:
   ```
   SMC_record.support  ──▶  scenario.historical_support  ──▶  compete_scenarios
   O'_i                ──▶  predicted_state_fragments only (display / receipt)
   ```

---

## 6. STOP-CONDITION STANCE

Per investigation charter §27:

- **Do not invent** a new historical-support scoring mechanism or value scalar in this task.
- **Do** measure, with logging-only probes, whether existing stores *would* differentiate `O'_i` if queried (diagnostic, not selection).
- **Do** run Phase A→B experiments on the **existing** bridge (SMC-support → PSC) vs WITHHELD / shuffle / PSC-from-start.
- Verdict language must separate:
  - `ACTION_CONDITIONED_PREDICTIONS_AVAILABLE`
  - `SMC_SUPPORT_REACHES_PSC` (existing enrichment)
  - `HISTORICAL_SUPPORT_ON_O_PRIME` (diagnostic probe only unless already wired — it is not)
  - `SELECTION_BRIDGE` claims only when WITHHELD control shows selection change

**Pre-experiment architectural verdict:**  
The hypothesized selection bridge (**predicted future → history query → PSC**) is **ABSENT**.  
A weaker bridge (**action-conditioned ΔS record support → PSC**) is **PRESENT** when SMC enrichment is not withheld.

---

## 7. Implications for experiment design

| Question | How to test without inventing |
|----------|-------------------------------|
| Does Phase A learn SMC while PSC OFF? | SMC ON + `prospective_selection=LEGACY_FIRST`; measure occupancy before T0 |
| Does activation reset? | Snapshot store IDs/occupancy across T0 |
| Do candidates get different SMC supports / ΔS? | Counterfactual receipts at competition ticks |
| Does O' differentiate under existing history APIs? | **Logging-only** probe: soft-match / predict with antecedent=O' |
| Does that reach selection today? | Compare FULL vs WITHHELD; expect effect only from SMC-support path, not O'-history |
| Developmental history? | EXPERIENCE_FIRST vs PSC_FROM_START paired by seed |

If logging-only probes show differentiation on O' but selection is unchanged under WITHHELD that only strips SMC enrichment:  
report `HISTORICAL_SUPPORT_DIFFERENTIATION_LATENT` + `PSC_SELECTION_EDGE_MISSING` for the O'-history edge.
