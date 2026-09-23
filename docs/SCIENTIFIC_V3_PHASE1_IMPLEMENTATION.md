# SCIENTIFIC_V3 Phase-1 CORE — Implementation

**Status:** IMPLEMENTED  
**Date:** 2026-09-21T05:48:31.638348+00:00  
**Tier:** CORE only (not RESEARCH/FORENSIC)  
**Design refs:** `SCIENTIFIC_V3_EVIDENCE_CONTRACT.md`, gap map, schema drafts

---

## Verdict

Phase-1 CORE lands the every-tick causal spine:

`ObservationReceipt(T) → DecisionReceipt(T) → MotorReceipt(T) → ConsequenceReceipt(T→T+1)`

for every **AUTONOMOUS** cognitive agent, with deterministic IDs, IdentityMap,
CoverageMatrix, append-only JSONL writer, and a minimal Analyzer reconstruction
section. Runtime science is unchanged (V3 ON vs OFF fingerprint EXACT_MATCH).

---

## Implemented receipts

| Receipt | File stream | Provenance |
|---------|-------------|------------|
| Observation | `scientific_observations.jsonl` | AGENT_ACCESSIBLE |
| Decision | `scientific_decisions.jsonl` | DECISION_INTERNAL |
| Motor (COMPOSITE_MOTOR_V1) | `scientific_motors.jsonl` | MOTOR_OUTPUT |
| Consequence | `scientific_consequences.jsonl` | PHYSICAL_GROUND_TRUTH |
| Spine | `scientific_spine.jsonl` | links the four |

IDs: `o:|d:|m:|c:{run}:{tick}:{agent|body}` (deterministic).

---

## Tick semantics

- Capture runs **after** `finish_tick` / `_step_once` (session `_append_scientific_locked` or direct `ScientificV3Writer.append_runtime_tick`).
- `last_v3_decision_tick` / `last_v3_body_before` set in `begin_tick`.
- `last_v3_body_after` set after `tick += 1` in `finish_tick`.
- Obs/Dec/Motor labeled with **decision tick T** (pre-commit).
- Consequence is **T→T+1** with wrap-aware pose deltas.

---

## Identity semantics

`IdentityMap` (`identity_map.json`):

- `physical_body_id` = `body-{slot}`
- `cognitive_agent_id` = `agent_{slot}` (AUTONOMOUS) or `controller_experimenter_{slot}` (EXPERIMENTER); `None` for PASSIVE
- `controller_type` ∈ AUTONOMOUS | EXPERIMENTER | PASSIVE | SYSTEM
- `role_label` = `UNDERCOVER` for experimenter **role only** (never the fundamental id)
- lifecycle changes recorded when controller/cognition role flips

---

## Provenance & coverage

Schema-level provenance enums in `mechanistic_mind/scientific_v3/provenance.py`.  
Coverage dimensions use COMPLETE / PARTIAL / NOT_RECORDED / NOT_AVAILABLE / NOT_APPLICABLE  
(**MISSING ≠ ZERO**). No fake `SCENARIO_SELECTED: 0` for absence.

---

## Persistence layout

Under the same live scientific directory as V2 (additive):

```
scientific_v3_meta.json
identity_map.json
scientific_spine.jsonl
scientific_observations.jsonl
scientific_decisions.jsonl
scientific_motors.jsonl
scientific_consequences.jsonl
```

Writer: bounded in-memory buffers, flush_every default 32, fail-closed on
`EVIDENCE_BACKPRESSURE` / `EVIDENCE_WRITE_FAILED` (no silent drops). Flush on close/STOP.

V2 `SCIENTIFIC_V2_TIERED` continues unchanged alongside V3.

---

## Failure semantics

| State | Meaning |
|-------|---------|
| OK | Normal |
| EVIDENCE_BACKPRESSURE | Queue exceeded max; flush attempted; if still over → incomplete |
| EVIDENCE_INCOMPLETE | Capture aborted after backpressure |
| EVIDENCE_WRITE_FAILED | Disk/write error; further appends raise |

Runtime physics continues; evidence reports incomplete coverage.

---

## Normalized API

`mechanistic_mind.scientific_v3.api.RunEvidence`:

- `get_observation / get_decision / get_motor / get_consequence`
- `trace_chain(agent_id, tick)` → O→D→M→C completeness
- `detect_evidence_version(dir)` → SCIENTIFIC_V3 | SCIENTIFIC_V2_TIERED | …

Analyzer adapter: `build_v3_core_reconstruction` / `write_v3_core_reconstruction`
→ section **SCIENTIFIC_V3 CORE RECONSTRUCTION**.

---

## Deviations from design draft

1. **Observation size:** full accessible float map each tick (required for decision context) → storage higher than the ~1.2 KB/tick/agent scalar sketch. Slimmed notes/rules/oscillator defaults; floats rounded to 8 decimals for JSON compactness only (runtime untouched).
2. **Signal event slim:** **DEFERRED** (non-trivial; V2 events unchanged).
3. **Controller enum:** design said AUTONOMOUS_COGNITIVE; implementation uses `AUTONOMOUS` (shorter; same meaning).
4. **Attribution:** only SELF_MOTOR / SHARED_WORLD / CONTACT / MIXED / UNKNOWN / EXPERIMENTER_CONTROL when derivable — never guessed.

---

## How to run gates

```bash
cd <project-root>
PYTHONPATH=. .venv_psy_web/bin/python -m pytest tests/test_scientific_v3_phase1_core.py -q
```

Benchmark artifacts: `results/mm_scientific_v3_phase1_core/benchmark_slim/`.

---

## Known gaps (Phase-1)

- No top-k PSC candidate graphs (Phase-2)
- No revision receipts beyond absence (Phase-2)
- No lean signal event rewrite (Phase-2/3)
- No Observer Web redesign (Phase-3)
- Vision/signals coverage PARTIAL only when channels appear in accessible obs
- Non-autonomous slots get consequence (+ identity) but not O→D→M

---

## Files

New package: `mechanistic_mind/scientific_v3/`  
Wired: `runtime.py` (v3 snapshots), `session.py` (additive writer),  
`scientific_history.py` / `psychology_analyzer/analyzer.py` (adapter hooks)  
Tests: `tests/test_scientific_v3_phase1_core.py`


## Measured performance / storage

From `results/mm_scientific_v3_phase1_core/benchmark_slim/BENCHMARK.json`
(TwoAgent, seed 17, `signal_enabled=False`, slim CORE receipts):

| Mode | ticks/s (n=500) | bytes/tick (2 agents) |
|------|----------------:|----------------------:|
| none | 107.3 | 0 |
| V2 timeline | 102.6 | 2140.8 |
| V3 CORE | 101.7 | 5489.2 |
| V2+V3 | 95.6 | ~7699 (500-tick sample) |

- V3 CPU overhead vs none: **5.5%**
- V3 storage ≈ **2744.6 B/tick/agent** (2.56× V2 timeline-only)
- Projections (V3 only): 10k ≈ 54.89 MB; 100k ≈ 548.92 MB; 1M ≈ 5.489 GB
- One-agent V3: 2762.2 B/tick @ 180.8 t/s
- Peak queue depth observed: 40 lines (flush_every 32)
- Flush time: sub-millisecond on close for 500-tick runs

Higher than ~1.2KB/tick/agent sketch due to full accessible observation maps every tick; defensible vs reconstructability goal; below signal-heavy ~10KB/tick V2 all-in.

### V3 1k component breakdown (bytes)

```json
{
  "scientific_consequences.jsonl": 1162818,
  "scientific_observations.jsonl": 1284566,
  "scientific_v3_meta.json": 1423,
  "scientific_spine.jsonl": 648900,
  "scientific_decisions.jsonl": 1499224,
  "scientific_motors.jsonl": 891340,
  "identity_map.json": 937,
  "TOTAL": 5489208
}
```
