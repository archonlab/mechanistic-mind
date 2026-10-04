# CURRENT LIVE RUN — Effector-Z Control And Analyzer Consistency Forensic

## Verdict (primary)

**H. ANALYZER_MISCLASSIFIES_CURRENT_Z_CONTROL_EVIDENCE**

The live Acanthostega Beta 4.0 run already has agent-accessible effector relative_z control
(MRWA+EBAE → `EFFECTOR_Z_*` in repertoire; COMPOSITE_MOTOR_V1 serializes `effector_z_*`;
policy selects nonzero Z; tip `relative_z` displaces by ±0.1075). The Analyzer report’s
`agent_selectable = NO` / `REQUIRED_CONTROL_NOT_IN_REPERTOIRE` banner is **not** reflecting
live authority — it is produced by hardcoded Analyzer summary fields plus an incorrect
“actuated” predicate that treats pose `relative_z ≠ 0` as actuation.

## Identity

| Field | Value |
|---|---|
| Analyzed run | `psyweb-20261001T124649.320946Z-1a7d3be6` |
| Live evidence dir | `results/psychology_observer/psy_observer_web/.live-psyweb-20261001T124649.320946Z-1a7d3be6` |
| Match | **YES** (same run_id, seed 3716, generation 5, ACANTHOSTEGA_BETA4) |
| Analysis cutoff | 2172 |
| Live tick (during audit) | ~2950→3267+ (RUNNING, not mutated by audit) |
| Observer | `127.0.0.1:8769` (launcher pid 670651 → uvicorn 670706) |
| Served asset | `index-C7CoAFuV.js` |

Do **not** label this run stale: `agent_selectable=NO` is an Analyzer lie, not proof of an
old binary without V1.

## Configuration matrix (live)

| Authority | Live |
|---|---|
| public_preset | ACANTHOSTEGA_BETA4 |
| model_line | ACANTHOSTEGA |
| MRWA | True |
| EBAE | True |
| `effector_z_on = MRWA∧EBAE` | True (code path in `runtime._sync_embodiment_dofs`) |
| PSC motor resolution | OBSERVED_COMPOSITE |
| cognition_enabled | True |
| agent_count | 2 |

Isolated Beta4 builder probe (1 tick, not the live run): available_actions includes
`LEFT_EFFECTOR_Z_UP/DOWN`, `RIGHT_EFFECTOR_Z_UP/DOWN`.

## Action / motor evidence (cutoff ≤ 2172)

| Metric | Count |
|---|---|
| Motor rows | 4346 (2173×2) |
| Motors with `effector_z_*` schema | **4346** |
| Motors with nonzero Z | **520** (260/agent) |
| LEFT up/down | 179 / 167 |
| RIGHT up/down | 182 / 178 |
| Decision primary token = `*_EFFECTOR_Z_*` | 0 (expected: Z is factorized side-channel, not loco token) |
| Reachability traces (event_refs) | 8692 |
| Trace `physical_relative_z_dof=AVAILABLE` | all sampled / counted PRESENT path |
| Trace `agent_selectable_motor_factor=PRESENT` | **all 8692** |
| Trace `agent_cognition_token=PRESENT` | PRESENT |
| `relative_z` pose ≠ 0 on traces | 11170 (pose state, not proof of this-tick command) |
| Geometric reach | 0 |
| ETC `contact_fact` | 0 |
| EBAE receipts in consequence `event_refs` | **0** (capture/index gap) |
| Observed tip Δrelative_z = ±0.1075 after Z select | **yes** (706 effector-tick changes when Z selected) |

## First disappearance / contradiction

1. **Live/control path intact through selection + displacement.**
2. **First false statement in the export** is Analyzer aggregate construction:

```text
relative_z.agent_selectable := "NO"   # HARDCODED whenever volumetric story applicable
format footer always prints REQUIRED_CONTROL_NOT_IN_REPERTOIRE
```

File: `mechanistic_mind/scientific_v3/analyzer_next/volumetric_physical_causal_reconstruction.py`
(`build_volumetric_physical_causal_reconstruction` / `format_volumetric_physical_causal_section`).

3. **Why 4232 × ACTUATED_NO_GEOMETRIC_REACH while agent_selectable=NO:**

Per-story classifier:

```text
actuated_rz := any(|trace.relative_z| > 0)   # POSE, not Z request
…
elif actuated_rz and not geometric_reach and not contacts:
    neg = ACTUATED_NO_GEOMETRIC_REACH
```

After any prior Z motion leaves `relative_z ≠ 0`, nearly every later story is labeled
ACTUATED_… even when this tick’s `effector_z_* == 0`. That class does **not** require a
positive Z actuator request. Recomputed under the same predicates ≈ 2116/agent ≈ 4232 total.

Passive EORT itself often records `control_repertoire_class=NOT_SELECTED` with
`agent_selectable_motor_factor=PRESENT` — the Analyzer summary ignores that.

## Downstream (not primary)

- EBAE receipts are produced in mechanism code but **not** present in SCIENTIFIC_V3
  consequence `event_refs` for this run (0). Tip displacement still proves application.
  Treat as a separate capture/index seam, **not** the cause of `agent_selectable=NO`.

## Proposed repair slice (do not implement in this audit unless approved)

**Analyzer-only, local, low-risk:**

1. Set `relative_z.agent_selectable` from evidence (`PRESENT`→`YES` when motor schema or
   traces say PRESENT; else `NO`).
2. Redefine actuation evidence as: nonzero `effector_z_*` selection **and/or** explicit
   EBAE request receipt — **never** `|relative_z|` alone.
3. Make markdown footer use the computed `outcome_class`, not a fixed
   `REQUIRED_CONTROL_NOT_IN_REPERTOIRE` string.
4. (Optional separate seam) Route EBAE receipts into scientific consequence refs so
   `SELECTED_NOT_ACTUATED` vs applied displacement can be proven from receipts.

**No new run required** to validate availability — current evidence already shows selection
and displacement. Re-analyze current/saved after Analyzer repair.

## Preservation

- Dirty tree preserved; no commit/reset.
- Live run not stepped/paused/re-Applied by this audit.
- Isolated probe ticks: 1 (≤20 budget).
