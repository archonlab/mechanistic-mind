# ANALYZER NEXT — ARCHITECTURE RECOMMENDATIONS

**Status:** Recommendations only. Do not implement in the audit pass.  
**Depends on:** `docs/SCIENTIFIC_OBSERVABILITY_AUDIT.md`, `docs/scientific_observability_matrix.json`, `docs/SCIENTIFIC_TELEMETRY_V2.md`

---

## Design principle

Fewer disconnected numbers; more reconstructable chains:

WHAT WAS THE PHYSICAL STATE?
→ WHAT COULD THE AGENT OBSERVE?
→ WHAT DID HISTORY/PREDICTION/PROSPECTION DO?
→ WHAT MOTOR COMPONENTS WERE PRODUCED?
→ WHAT PHYSICALLY HAPPENED?
→ WHAT CHANGED AFTERWARD?

Where an edge cannot be connected, say **NOT_ESTABLISHED** / **NOT_RECORDED_IN_V2** / **AGGREGATE_ONLY** explicitly. Never launder omission into “did not occur”.

---

## Analyzer Next structure

### A. Evidence package loader
- Detect V1_FULL vs V2_TIERED  
- Load timeline, events, meta, checkpoints, snapshot, cumulative summaries  
- Build **CoverageMatrix** (per channel × completeness)  
- Build **IdentityMap** (runtime agent_id ↔ body_id ↔ undercover/experimenter)

### B. Layer engines (pure functions over evidence)
1. Integrity  
2. Mechanism/config  
3. Physical organism  
4. Perception  
5. Cognition (split AggregateCognition vs StructuredCognition)  
6. Action (Composite authoritative; Legacy projection subsection)  
7. Consequence (tick-aligned deltas)  
8. Adaptation (only if error/revision evidence)  
9. Ecology  
10. Interaction  
11. Longitudinal  

### C. Relationship graph API
Nodes: ticks, agents, events, states.  
Edges typed: OBSERVED, DERIVED, TEMPORALLY_ASSOCIATED, NOT_ESTABLISHED.

### D. Report + Web contract
Same JSON drives text report and Observer “ANALYZE” views. Provenance badge required on every metric.

---

## Top dependency-ordered recommendations

1. **Fix identity & coverage model** for multi-agent + undercover before new metrics.  
2. **Global multidimensional coverage** replacing single PARTIAL/COMPLETE banner.  
3. **Composite-first action analytics**; quarantine one-label occupancy.  
4. **Structured cognition path**: either persist compact decision records every selection tick or teach Analyzer to use checkpoints — stop showing SCENARIO_SELECTED=0 beside huge aggregates without explanation.  
5. **Consequence engine**: Δ(resource, work, pose, theta) aligned to composite action ticks.  
6. **Spatial engine**: wrapped distances/bearings using timeline pose; fix path_euclid/wrap reporting.  
7. **Perception×Action panels**: extend vision/signal/contact associations with explicit NOT_ESTABLISHED cognition links.  
8. **Optional evidence tier** (config): record motor_u / force_contributions / B_site summaries at checkpoint or low-rate — only if endogenous/morphology claims are required.  
9. **Observer Web information architecture**: linked views with tick sync; provenance labels separating GT / agent-accessible / cognition / derived.  
10. **Deprecation pass**: mark misleading zeros and legacy projections in UI; do not delete historical metrics until replacements are accepted.

---

## What can be built without new runtime data

- CoverageMatrix + IdentityMap  
- Composite-first reports  
- Resource/work consequence tables  
- Wrapped spatial metrics from x,y,theta  
- Stronger vision/signal/contact → next-action associations  
- Honest cognition section (aggregates vs structured unavailable)

## What requires new / denser evidence

- Per-decision PSC graphs (if not in checkpoints)  
- Prediction-error / revision tick chains  
- Endogenous motor_u and morphology site force ledgers for channel claims  
- Full every-tick BODY_MOVED/ROTATED if rotation dynamics must be event-audited (prefer using timeline theta/omega instead)

---

## Run-time capture policy (unchanged philosophy)

Keep V2 tiered design. Do not reintroduce full Analyzer during RUNNING. Prefer:
- cheap every-tick scalars  
- exhaustive compact events for claim-critical families  
- checkpoints for heavy nests  
- STOP-time Analyzer Next

---

## Non-goals for Analyzer Next v1

- New physics or cognition mechanisms  
- Semantic motivation/reward variables  
- Calling signals “communication”  
- Steering / heading preference language  
- UI redesign big-bang (architecture first)
