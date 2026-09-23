# SCIENTIFIC OBSERVABILITY AUDIT

**Date:** 2026-09-21T05:27:10.964831+00:00  
**Scope:** Read-only repository + saved-run audit. No runtime/physics/cognition changes.  
**Runtime label at audit:** `MM_1_0_TIKTAALIK`  
**Example run:** `psyweb-20260921T041444.727355Z-ec8b45bc` (6268 ticks, TwoAgentRuntime + undercover, SCIENTIFIC_V2_TIERED)  
**Machine-readable companion:** `docs/scientific_observability_matrix.json`

---

## AUDIT VERDICT

Mechanistic Mind currently has a **broad mechanism surface** (46 registered mechanisms across physical, sensory, signal, cognitive, and motor families) and a **deliberately compressed evidence pipeline** (Scientific Telemetry V2) that preserves many Analyzer counters while dropping high-volume bookkeeping events.

The dominant scientific observability problem is **not absence of mechanisms**. It is **incomplete reconstructability of causal chains**:

PHYSICAL STATE → AGENT-ACCESSIBLE OBSERVATION → COGNITION STEPS → COMPOSITE MOTOR → PHYSICAL CONSEQUENCE → REVISION

Several edges are only **aggregates**, **legacy projections**, or **NOT_RECORDED_IN_V2**. The Analyzer often presents impressive numbers that cannot reconnect those edges.

---

## 1. Mechanisms found

**Count:** 46 registered in `mechanism_registry.py`  
**Families:** ACTION_MOTOR, COGNITIVE, PHYSICAL_WORLD, SENSORY, SIGNAL_INTERACTION

### Physical / world (representative)
distributed morphology, body orientation, body deformation, deformation work, environmental site mechanics, resource A/B ecology & transfer, complementary conversion, resource→work, work accounting, climate/illumination (when enabled)

### Sensory
near-field vision, body optical response, articulated head, vestibular sensing, neck proprioception, OSC L/R energy channels

### Signal / interaction
experimental physical signal, oscillatory signaling, contact, physical push

### Cognitive
bounded memory, retrieval, predictive compression, multiscale prediction, prospective composition, PSC, instrumental observation, predictive equivalence/relevance/conflict, temporal predictive structure & bridges, prediction-error / revision variants, future-sensitive / multistep prospection, cognition master switch

### Action / motor
discrete action bridge, COMPOSITE_MOTOR_V1 factorization (MOVE/WAIT/PUSH/NECK/OSC_*), endogenous motor coupling, unknown-action probe, shared work allocation

Full per-mechanism rows: matrix JSON.

---

## 2. Mechanism → state → evidence map (summary)

| Layer | What exists | What persists (V2 default) | Analyzer use |
|-------|-------------|----------------------------|--------------|
| Pose / orientation / speed | runtime body | timeline every tick | distance, speed, cells |
| Resources A/B, work | runtime reservoirs | timeline every tick | start/end/min/max |
| Head / vestibular / neck | runtime + agent channels | timeline fields | weak / mostly raw |
| Vision | exo + optical GT | compact `vision_optical` | exposure episodes |
| Signals / push / contact | runtime events | exhaustive event families | signal forensics |
| Composite motor | factorized components | reconstructed from action stream + events | COMPOSITE MOTOR FORENSICS |
| Cognition internals | stores, PSC, predictions | **aggregates** on timeline; rich graphs checkpoint/compact | aggregates; structured events often NOT AVAILABLE |
| Morphology B_site / site forces | runtime | mostly omitted / not on V2 timeline | weak |
| Endogenous motor_u / force ledger | runtime | not on V2 timeline | weak |
| Deformation alpha | runtime | `body_alpha` on timeline; DEFORM events when emitted | often NOT AVAILABLE counts |

---

## 3. Provenance taxonomy (recommended canonical)

| Code | Meaning |
|------|---------|
| PHYSICAL_GROUND_TRUTH | Simulator body/world truth (may exceed agent sensors) |
| AGENT_ACCESSIBLE | Entered agent observation channels |
| COGNITIVE_INTERNAL | Cognition stores / metrics |
| ACTION_SELECTION | Selected motor / discrete / composite output |
| DERIVED_ANALYSIS | Post-hoc Analyzer/UI derivation |
| EXPERIMENTER_CONTROL | Human intervention / undercover body |
| CONFIGURATION | Mechanism toggles, seed, preset |
| LEGACY_PROJECTION | Compatibility view (e.g. one-label action) |
| DEBUG_DIAGNOSTIC | Non-scientific diagnostics |
| MIXED_* | Must be split before scientific claim |

**Ambiguous today:** `vision_optical` (MIXED), one-label `action` under COMPOSITE (LEGACY_PROJECTION), cognition aggregates vs structured events, omitted V2 events misreadable as absence.

---

## 4. Temporal semantics

### Documented / intended tick order
1. WORLD(T)  
2. OBSERVATION  
3. COGNITION (if enabled)  
4. ACTION SELECTION / COMPOSITE MOTOR  
5. PHYSICAL COMMIT  
6. WORLD(T+1)  
7. EVIDENCE APPEND  

### Confirmed issues
- Timeline row is a **post-tick snapshot** with a **canonical action label**, not a full pre/post pair.
- `prediction_count` / `prospective_compositions` are **cumulative counters**, not “this tick’s graph”.
- Multiple Level-2 events can share one tick (signals especially).
- GEO receipts / rich scenario graphs are **checkpoint-only** in V2 (`geo_receipts_on_timeline: CHECKPOINT_ONLY`).
- Omitted types (`BODY_MOVED`, `BODY_ROTATED`, …) are **NOT_RECORDED_IN_V2**, not evidence of non-occurrence (`event_exhaustiveness` in scientific_meta).

---

## 5. Action semantics audit

**Authoritative:** COMPOSITE_MOTOR_V1 / `action_source=COMPOSITE_FACTORIZED` (combinations of MOVE, NECK, OSC_*, PUSH, WAIT).  
**Legacy projection:** single string `action` per timeline row (WAIT, MOVE:N, …).  

| Metric class | Examples | Status |
|--------------|----------|--------|
| AUTHORITATIVE | composite combinations, emission active ticks | KEEP |
| VALID_DERIVED | MOVE distribution from composite | KEEP BUT REFRAME |
| LEGACY_COMPATIBILITY | one-label occupancy, WAIT% | LEGACY — label clearly |
| MISLEADING | treating one label as exclusive motor content | DEPRECATED for claims |

Analyzer already labels legacy occupancy; UI must never promote it over composite forensics.

---

## 6. Cognition observability audit

### What exists as aggregates (example run agent_0)
- Prediction count: 3587  
- Prospective compositions: 2704  

### What Analyzer reports as structured
- SCENARIO_SELECTED: **0**  
- `structured_cognition_events: NOT AVAILABLE`  
- `cognition_enabled: NOT AVAILABLE` (identity)

### Break classification (chain)

| Step | Status |
|------|--------|
| INPUT observation | PARTIAL (timeline/sensors) |
| RETRIEVAL | B/C — mechanism exists; reconstructable episode graph not persisted every tick |
| PREDICTION | F — aggregate only |
| COMPRESSION / MULTISCALE | F / D — config ON; little tick evidence |
| PROSPECTIVE COMPOSITION | F — aggregate |
| SCENARIO COMPETITION / SELECTION | B/C/E — runtime emits/compacts; Analyzer structured path unavailable |
| MOTOR IMPULSE | LEGACY label + composite derivation |
| PHYSICAL CONSEQUENCE | PARTIAL (pose/resources) |
| PREDICTION ERROR / REVISION | G/A sparse — NOT AVAILABLE in report |

**Critical:** large aggregates + zero structured selection is an **observability gap**, not proof PSC was idle.

---

## 7. Physical consequence / body-state

Persisted well: `resource_A`, `resource_B`, `work`, pose, contact, `body_alpha`.  
Weak: deform event counts, work-limited events, morphology site state, endogenous motor contribution ledger, explicit ACTION→Δresource mediation tables.

Possible now without new runtime data: resource trajectories × action occupancy (with composite caveats); work reservoir bounds.  
Needs Analyzer work: ACTION → ΔA/ΔB/Δwork with correct tick alignment.  
Needs new evidence: per-tick force contributions / motor_u if claims about endogenous channel required.

---

## 8. Space / trajectory / ecology

Available: x,y,speed,theta, cells, WRAP_PERIODIC topology (runtime).  
Example Analyzer: manhattan_legacy distance present; path_euclid / wrap nets often 0 or NOT AVAILABLE; map size NOT AVAILABLE in report.  

Missing but evidence-possible: wrapped bearing to other body/resources, resource-relative approach/depart, orientation-conditioned displacement.  
Weak: rotation accumulation NOT AVAILABLE despite theta on timeline.

---

## 9. Interaction / multi-agent

Recorded heavily: PHYSICAL_SIGNAL_EMITTED/RECEIVED, CONTACT, PUSH_*, vision foreign-body exposure.  
Attribution often `mixed` / `not_unique`.  
Cognition linkage for vision: **NOT_ESTABLISHED**.  
Do **not** call signaling “communication” from current evidence.

---

## 10. Experimenter intervention

Undercover body (`observer_undercover`) is first-class in timeline.  
WORLD_INTERVENTION / EXPERIMENTER_ families are Analyzer-exhaustive **when emitted**; example run: Interventions 0.  
Gap: experimenter vs autonomous identity sometimes splits across agent_0 / agent_1 / UNDERCOVER with uneven timeline coverage.

---

## 11. Current Analyzer inventory (classification)

From `PsychologyAnalyzer` 1.1.0 + `analyze_run` / vision & signal forensics / composite forensics:

| Area | Classification |
|------|----------------|
| Run identity / coverage banner | KEEP |
| COMPOSITE MOTOR FORENSICS | KEEP (authoritative) |
| Legacy one-label occupancy | KEEP BUT REFRAME as LEGACY |
| Resource/work min-max | KEEP |
| Signal emit/recv counts & attribution | KEEP; note mixed attribution |
| Vision exposure episodes | KEEP; cognition linkage honest NOT_ESTABLISHED |
| Cognition aggregates | KEEP BUT REFRAME — not tick graphs |
| Structured SCENARIO_SELECTED counts | RECOMPUTE / fix coverage path |
| Manhattan distance | KEEP BUT REFRAME (legacy formula) |
| path_euclid / wrap nets when zeroed | MISLEADING if shown as “no motion geometry” |
| agent_1 empty vs undercover | MERGE identity model |
| Biography / epochs / meaningful events | KEEP as exploratory; verify against V2 |

Duplicate concepts: WAIT% (legacy) vs WAIT/NONE composite; prediction_count vs SCENARIO_SELECTED; contact emissions vs CONTACT events.

---

## 12. Observer Web UX map (current)

**Tabs:** WORLD, INTERACT, AGENT, MIND, TIMELINE, EXPERIMENT, DATA, ANALYZE RESULTS, OVERVIEW  

**Panels (components):** WorldMap, Mechanisms, ModelBanner, Mind, CausalChain/Gearbox, Why Move/Rotate/Shape, NearField, Oscillatory, Vestibular, SignalContext, AnalyzeResults, Overview, Interact, Geometry, Vision experimenter, Timeline, ActionDecision, ObserveV2, Preflight.

**Problems:** scientifically related facts split (Mind vs Analyze vs Signal vs Vision); GT vs agent-accessible not always labeled; Analyze Results is a report dump rather than a linked causal explorer.

---

## 13. Cross-mechanism opportunities

| Relationship | Status |
|--------------|--------|
| resource A/B × composite action | READY NOW (Analyzer work) |
| vision exposure × next action | READY NOW (partially done; extend) |
| signal exposure × next action | READY NOW |
| contact × post-contact action | READY NOW |
| theta × displacement / bearing | NEEDS ANALYZER WORK (theta present) |
| composite motor × OSC emission episodes | READY NOW (forensics exist) |
| prediction aggregate Δ × action regime | NEEDS ANALYZER WORK (weak causal) |
| PSC candidate → selected motor → outcome | NEEDS ADDITIONAL PERSISTED EVIDENCE (compact selection graph every decision or denser checkpoints) |
| endogenous motor_u × translation | NEEDS ADDITIONAL PERSISTED EVIDENCE |
| B_site × force × torque | NEEDS ADDITIONAL PERSISTED EVIDENCE (V2 omits) |
| history-conditioned prediction difference | NOT CURRENTLY POSSIBLE at tick-graph fidelity |

---

## 14. Scientific analysis graph — edge status

| Edge | Status |
|------|--------|
| WORLD → PHYSICAL STATE | DIRECTLY RECORDED |
| PHYSICAL → SENSORY EXPOSURE | DIRECTLY RECORDED (compact) |
| SENSORY → AGENT-ACCESSIBLE | PARTIAL / MIXED packaging |
| OBSERVATION → MEMORY/RETRIEVAL | RECONSTRUCTABLE only coarsely |
| → PREDICTION / PROSPECTION | TEMPORALLY ASSOCIATED (aggregates) |
| → COMPETITION/SELECTION | NOT ESTABLISHED in V2 Analyzer path |
| → COMPOSITE MOTOR | DIRECTLY RECORDED / DERIVED |
| → PHYSICAL CONSEQUENCE | PARTIAL |
| → PREDICTION ERROR | NOT ESTABLISHED |
| OTHER AGENT / EXPERIMENTER → interaction | DIRECTLY RECORDED (signals/contact/vision) |
| interaction → cognition | NOT ESTABLISHED |

---

## 15. Proposed analysis layers (derived)

1. Run integrity & coverage (multidimensional)  
2. Configuration / mechanism map  
3. Physical organism (pose, resources, work, deformation)  
4. Perception (vision, vestibular, proprioception, OSC sense)  
5. Cognition (aggregates vs structured — separate)  
6. Action (composite authoritative; legacy clearly marked)  
7. Consequence (Δ body/world aligned to action tick)  
8. Learning/adaptation (only if error/revision evidence exists)  
9. Ecology (resources, illumination, sites)  
10. Interaction (agents, experimenter, signals, contact)  
11. Longitudinal regimes / phases  

---

## 16. Evidence quality model (proposed)

Per channel: `COMPLETE | PARTIAL | AGGREGATE_ONLY | SPARSE | UNAVAILABLE | NOT_APPLICABLE`  
Per claim link: `OBSERVED | DERIVED | DIRECT_CAUSAL_LINK | TEMPORALLY_ASSOCIATED | NOT_ESTABLISHED`

Example run already partially does this (`coverage.*`, vision cognition linkage). Extend globally; retire single COMPLETE/PARTIAL as the only banner.

---

## 17. What should be recorded during RUN

### Cheap every-tick (keep)
pose, theta/omega, resources/work, composite-resolvable action fields, contact, compact vision VF, thin cognition counters, undercover flag, head/vest/neck/osc scalars

### Event-driven exhaustive (keep)
signals, push/contact/neck, interventions, deform/conversion/work-limit families, compact decision summaries

### Checkpoint / on-STOP (keep)
GEO nests, rich scenario graphs, optical dumps, force ledgers, B_site

### Do not run full Analyzer while RUNNING
Confirmed by docs/performance history.

### Storage (from SCIENTIFIC_TELEMETRY_V2 measured ~5.3 KB/tick V2)
| Horizon | ~V2 size |
|--------:|---------:|
| 10k | ~53 MB |
| 100k | ~530 MB |
| 1M | ~5.3 GB |

Plus events (example run: 69k events / 6.3k ticks ≈ heavy signal regimes dominate).

---

## 18. Observer Web future analysis architecture (proposal only)

Connected views: RUN OVERVIEW · MECHANISM MAP · BODY & VIABILITY · PERCEPTION · COGNITION · ACTION & CONSEQUENCE · ECOLOGY · INTERACTION · LONGITUDINAL · CAUSAL EXPLORER · RAW EVIDENCE  

Synced selection by tick / agent / event. Provenance badges on every value. No large UI rewrite in this pass.

---

## 19. Example run `psyweb-20260921T041444.727355Z-ec8b45bc` — what we can / cannot answer

### CAN answer (with caveats)
- Composite motor organization for agent_0 and undercover  
- Resource A/B and work reservoir trajectories (bounds)  
- Signal flood statistics and mixed attribution  
- Vision exposure episodes and next-action observations (association only)  
- Contact/push event presence  

### LOOK answerable but cannot (honestly)
- “PSC selected WAIT/MOVE N times” from structured events (0 / NOT AVAILABLE)  
- Full scenario competition graphs per decision  
- Cognition enabled? (identity NOT AVAILABLE)  
- Euclidean path / wrap net geometry as reported  
- agent_1 as a full peer timeline agent  

### EXISTS but Analyzer fails to combine
- theta series × movement/bearing  
- resource Δ aligned to composite combinations  
- undercover vs autonomous comparative cognition (undercover aggregates 0)  
- omitted V2 motion/rotation events vs orientation timeline fields  

---

## 20. Files created

- `docs/SCIENTIFIC_OBSERVABILITY_AUDIT.md` (this file)  
- `docs/scientific_observability_matrix.json`  
- `docs/ANALYZER_NEXT_ARCHITECTURE.md`  

No git push. No runtime changes.
