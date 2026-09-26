# SCIENTIFIC_V3 EVIDENCE CONTRACT

**Status:** DESIGN ONLY — not implemented  
**Date:** 2026-09-21T05:32:50.068120+00:00  
**Depends on:** `SCIENTIFIC_OBSERVABILITY_AUDIT.md`, `ANALYZER_NEXT_ARCHITECTURE.md`, `SCIENTIFIC_TELEMETRY_V2.md`  
**Companion schemas:** `scientific_v3_schema_draft.json`, `scientific_relationship_types.json`

---

## Design verdict (short)

**YES — SCIENTIFIC_V3 is worth implementing**, if Phase-1 CORE only lands:

1. stable identity map  
2. per-(tick, agent) causal spine IDs  
3. every-tick compact DecisionReceipt + MotorReceipt (COMPOSITE_MOTOR_V1) + ConsequenceReceipt  
4. multidimensional coverage + provenance  

This closes the highest-value break (decision linkage) without full-state dumps or UI redesign.

---

## 1. Non-negotiable constraints

V3 is **observation infrastructure only**. It must not change physics, cognition, PSC, sensors, action selection, RNG, tick order, or mechanism semantics. No semantic motivation/intention/communication/reward variables enter runtime.

---

## 2. ACTUAL_TICK_PIPELINE (TwoAgentRuntime authority)

Verified from `two_agent.py::_step_once` and `PhysicalSystemRuntime::begin_tick` / `finish_tick`.

| # | Stage | Where | Tick semantics | Currently persisted (V2) | V3 requirement |
|--:|-------|-------|----------------|--------------------------|----------------|
| 0 | Pre-tick body/internal sync | `begin_tick` | WORLD(T) still current | partial | Spine start |
| 1 | Multi-agent observations | `TwoAgentRuntime.observations()` | AGENT-ACCESSIBLE at T | via later timeline | ObservationReceipt |
| 2 | Slot begin: cognition | `run_cognition_before_action` | uses observation; may revise prior prediction vs current obs | aggregates; decision receipts **sampled** | DecisionReceipt **every tick** (compact) |
| 3 | Motor intent + impulse realize | composite / discrete action work | MOTOR_OUTPUT intent→partial physical Δv | legacy action string + composite forensics posthoc | MotorReceipt (intent) |
| 4 | Shared planet step | `step_planet` once | WORLD advances | not full fields | world_epoch / checkpoint |
| 5 | Slot finish: physical commit | morph/orient/deform/endo/resources/head… | BODY/WORLD(T+1) | pose/resources/θ on timeline | ConsequenceReceipt deltas |
| 6 | Pairwise contact + push | two_agent after finishes | PHYSICAL_EVENT | CONTACT/PUSH events | event_refs on consequence |
| 7 | Simultaneous resources | complementary resources | BODY reservoirs | resources on timeline | resource_delta |
| 8 | Physical signals | `step_physical_signals` | field + reception | EMIT/RECV events (volume!) | lean event refs + emission/reception IDs |
| 9 | Oscillatory signaling | `step_oscillatory_signaling` | shared fields | osc scalars on timeline | keep scalars; events lean |
| 10 | Tick++ / receipts / stats | finish_tick end | evidence belongs to decision_tick T committing to T+1 | ScientificHistoryWriter after session step | ordered spine append |

**Temporal rule for Analyzer:**  
`observation_id(T)`, `decision_id(T)`, `motor_id(T)` are computed **before** planet/body finish; `consequence_id(T→T+1)` summarizes commit after finish (+ shared contact/signal stages). Do not treat timeline row as pre-action observation.

---

## 3. Minimum causal spine

Per `(run_id, tick, cognitive_agent_id)`:

```text
AgentTickSpine {
  observation_id,
  decision_id,
  motor_id,
  consequence_id,
  revision_id?,          # only if mechanism produced one this tick
  physical_body_id,
  controller_type
}
```

Stable linkage answers:
- What observation preceded this action?
- What decision produced this motor?
- What consequence followed?
- What revision (if any) referenced which prior prediction?

---

## 4. Identity contract

| Concept | ID | Notes |
|---------|----|------|
| Run | `run_id` | immutable for package |
| Generation | `generation` | increments on reset |
| Cognitive agent | `cognitive_agent_id` | may be absent for PASSIVE bodies |
| Physical body | `physical_body_id` | always present while body exists |
| Controller | `controller_type` | AUTONOMOUS_COGNITIVE / EXPERIMENTER / PASSIVE / SYSTEM |

**Labels are not IDs.** `UNDERCOVER` is a label/controller role, not an agent identity.

Lifecycle:
- spawn body → new `physical_body_id`
- attach experimenter controller → same body_id, controller_type=EXPERIMENTER
- detach → PASSIVE or remove from process_order
- despawn → body_id retired (never reused in-run)
- generation reset → new generation; document whether body IDs reset

This makes `agent_1` empty vs UNDERCOVER populated an **IdentityMap** presentation issue, not a mystery.

---

## 5. Provenance contract

| Provenance | Influences cognition? | Observer | Analyzer causal claims |
|------------|----------------------|----------|------------------------|
| PHYSICAL_GROUND_TRUTH | No (unless also accessible) | Yes | Yes as world truth |
| AGENT_ACCESSIBLE | Yes | Yes | Yes as input |
| COGNITIVE_INTERNAL | Internal only | Optional | Yes if recorded |
| DECISION_INTERNAL | Selection internals | Optional | Yes if recorded |
| MOTOR_OUTPUT | No (is output) | Yes | Yes |
| EXPERIMENTER_CONTROL | No | Yes | Separate from autonomous |
| CONFIGURATION | Indirect | Yes | Integrity |
| DERIVED_POSTHOC | No | Yes | Mark DERIVED |
| LEGACY_COMPATIBILITY | No | Yes | Never authoritative |
| DEBUG_DIAGNOSTIC | No | Optional | Not for claims |

Mixing GT into “what agent saw” is a contract violation.

---

## 6. Coverage contract

Dimensions (minimum): tick_history, identity, world, body, resources, trajectory, orientation, sensory, vision, signals, interoception, cognition, retrieval, prediction, compression, prospection, competition, decision, composite_motor, physical_consequence, prediction_error, revision, interaction, experimenter, configuration.

States: COMPLETE | PARTIAL | AGGREGATE_ONLY | EVENT_ONLY | CHECKPOINT_ONLY | SPARSE | NOT_RECORDED | NOT_AVAILABLE | NOT_APPLICABLE.

Causal strength (separate): DIRECT_CAUSAL_LINK | RECONSTRUCTED_CAUSAL_LINK | TEMPORALLY_ASSOCIATED | DERIVED | NOT_ESTABLISHED.

**Rule:** absence of NOT_RECORDED channels must never display as numeric zero for “did not happen”.

---

## 7. ObservationReceipt

CORE: hashable `accessible` map only (what cognition actually received) + `observation_id`.  
RESEARCH/FORENSIC: contributor decomposition for vision/signal **event-driven or checkpointed**, not every-tick full optical dumps.

---

## 8. Cognitive DecisionReceipt (highest priority)

Runtime already builds rich `ActionDecisionReceipt` but samples it (`every_10` default).  
`CognitionTickResult` already exposes: observation, selected_action, selection_source, composition, predictions, actions, motor_output, selection_rule.

**V3 CORE (every tick, compact):**
- decision_id, observation_id, motor_id
- selection_mode / source / rule
- selected_candidate_id or selected legacy token
- candidate_count
- fallback_reason if any
- peer_evaluation if present
- optional counter deltas (not absolute aggregates alone)

**Forbidden:** invented utility/motivation scores.

**RESEARCH:** top-k candidate summaries using real PSC fields (reliability/support/depth/edges statuses).  
**FORENSIC:** full scenario_groups/competition sampled or checkpointed (replace V2’s expensive every-decision full graphs).

---

## 9. Composite MotorReceipt

Authoritative schema: `COMPOSITE_MOTOR_V1` components (locomotion, neck, oscillator, push).  
Legacy one-label token is LEGACY_COMPATIBILITY only.

Preserve **intent vs realized** when ledgers exist (`action_work`, `motor_apply`, push receipts).

---

## 10. ConsequenceReceipt

Compact T→T+1 deltas: pose (wrap-aware), orientation, resources A/B/work, deform α; plus `event_refs` for contact/push/signal/transfer/deform.  
Optional RESEARCH: force contribution norms (env_site / endo / action) — not full site arrays every tick.

---

## 11. Prediction error / revision

When `prediction_error_revision` / `temporal_prediction_error` enabled, emit RevisionReceipt linking prior prediction → realized observation_id → real error metric → revision flag.  
When disabled: coverage NOT_APPLICABLE (not zero errors).

---

## 12. Event stream

Keep event-driven families; **lean payloads** (IDs + scalars). Signal-heavy regimes dominate V2 (~10 KB/tick measured on example run including events). V3 must:
- avoid duplicating full state in each signal event
- use emission_id / reception_id / field contribution refs
- optionally rate-limit forensic contributor detail

Omitted bookkeeping (BODY_MOVED etc.) remains omitable if ConsequenceReceipt + spine exist.

---

## 13. Checkpoints

For: cognition stores, compression, rich PSC graphs, optical dumps, B_site ledgers, world fields.  
Not a substitute for spine. Reconstruction = checkpoint + spine + events.

Default proposal: every 10k ticks (retain V2 cadence) + on STOP.

---

## 14. Evidence tiers

| Tier | Must reconstruct |
|------|------------------|
| CORE | identity, spine, observation accessible, decision compact, composite motor, consequence, major events |
| RESEARCH | top-k candidates, revision receipts, optional force norms, richer attribution |
| FORENSIC | sampled full PSC graphs, contributor decompositions, mechanism ledgers |

Tier recorded in meta. Missing tier data → NOT_RECORDED / NOT_AVAILABLE, never silent zero.

---

## 15. Storage estimates

### Measured V2 (example run psyweb-20260921T041444.727355Z-ec8b45bc, signal-heavy)
- Timeline ~1.6 KB/row; ~1.9 rows/tick → ~3.1 KB/tick timeline  
- Events ~0.63 KB/event; ~11 events/tick → ~7 KB/tick events  
- **≈10 KB/tick total** in this regime (higher than the ~5.3 KB/tick benign benchmark)

### Proposed V3 CORE (1 agent, scalars only)
| Receipt | ≈ bytes/tick |
|---------|-------------:|
| spine | 160 |
| observation | 260 |
| decision | 320 |
| motor | 220 |
| consequence | 200 |
| **subtotal** | **~1.2 KB** |

Plus lean events (hopefully ≤ current if signal payloads shrink) + rare checkpoints.

| Horizon | V2 benign ~5.3KB | V2 signal-heavy ~10KB | V3 CORE scalars-only | V3 CORE + lean events (target ≤V2) |
|--------:|-----------------:|----------------------:|---------------------:|-----------------------------------:|
| 10k | 53 MB | 100 MB | 12 MB | ≤100 MB |
| 100k | 530 MB | 1.0 GB | 120 MB | ≤1.0 GB |
| 1M | 5.3 GB | 10 GB | 1.2 GB | ≤10 GB |

2 agents ≈ ×2 spines; 10 agents ≈ ×10 spines + shared world events.

**Replace, don’t duplicate:** V3 receipts should supersede redundant V2 timeline fields where equivalent (action string → motor receipt; absolute cognition counters → deltas + decision).

---

## 16. Performance architecture

```text
simulation (unchanged science)
  → compact receipts (in-process, deterministic)
  → bounded queue
  → append-only chunked writer
  → flush on STOP
```

- No Analyzer while RUNNING  
- No silent drops: backpressure must block or fail closed  
- Prefer stay on **JSONL** for Phase-1 (inspectability, existing tooling); revisit msgpack/SQLite only after CORE metrics prove write-bound  

---

## 17. Versioning / migration

- `SCIENTIFIC_V2_TIERED` remains readable  
- Analyzer Next detects schema; V2 builds all reconstructable edges; missing V3 edges marked NOT_RECORDED  
- Meta: schema_version, evidence_tier, mechanism_registry_version, runtime fingerprint  

---

## 18. Validation strategy (pre-implementation tests)

A Tick alignment · B Composite survival · C Identity · D Accessible vs GT · E Signal chain · F Vision chain · G Consequence · H Revision when enabled · I Missing≠zero · J 100k synthetic · K Fingerprint unchanged · L Backpressure fail-closed  

---

## 19. Analyzer Next / Web boundary

```text
RAW EVIDENCE → NORMALIZED EVIDENCE → RELATIONSHIP GRAPH → ENGINES → SHARED ANALYSIS MODEL
                                                                      ↙ TEXT / HTML / WEB
```

Web must not reinterpret raw files independently.

---

## 20. Minimum implementation phase (recommended)

**Phase-1 CORE only** (no UI redesign):
1. IdentityMap writer  
2. AgentTickSpine every tick  
3. ObservationReceipt (accessible)  
4. DecisionReceipt compact every tick (replace sampled-only authority)  
5. MotorReceipt COMPOSITE_MOTOR_V1  
6. ConsequenceReceipt deltas  
7. CoverageMatrix + provenance on meta  
8. Adapter so Analyzer can consume V3 when present, V2 otherwise  

Defer RESEARCH/FORENSIC candidate graphs and Web redesign until Phase-1 proves storage/perf.
