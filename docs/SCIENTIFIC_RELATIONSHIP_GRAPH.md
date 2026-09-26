# SCIENTIFIC RELATIONSHIP GRAPH

**Status:** DESIGN ONLY  
**Date:** 2026-09-21T05:32:50.068120+00:00  
**Companion:** `scientific_relationship_types.json`

---

## Layers

1. **EVIDENCE_GRAPH** — recorded/reconstructable facts from V3 receipts/events  
2. **DERIVED_RELATIONSHIP_GRAPH** — deterministic calculations (wrapped distance, Δresource)  
3. **HYPOTHESIS_FORENSIC_LAYER** — scientific tests (“moved toward source”) — never written as runtime evidence  

---

## Node types

WORLD_STATE, BODY_STATE, OBSERVATION, SENSORY_EXPOSURE, MEMORY_CONTEXT, RETRIEVAL, PREDICTION, PROSPECTIVE_CANDIDATE, DECISION, MOTOR_OUTPUT, PHYSICAL_EVENT, CONSEQUENCE, REVISION, EXPERIMENTER_INTERVENTION  

Keys and tiers: see JSON.

---

## Edge types (summary)

| Edge | Typical strength | Requires |
|------|------------------|----------|
| AVAILABLE_TO_AGENT | DIRECT | observation_id → decision_id same tick |
| SELECTED / PRODUCED_MOTOR | DIRECT | decision_id → motor_id |
| PHYSICALLY_RESULTED_IN | DIRECT | motor_id → consequence_id |
| RECEIVED_FROM | DIRECT | emission/reception IDs |
| OBSERVED_AS | RECONSTRUCTED | exposure → accessible observation |
| COMPETED_WITH | DIRECT | RESEARCH candidate pair |
| UPDATED_BY | DIRECT | revision receipt when mechanism on |
| TEMPORALLY_FOLLOWED | TEMPORALLY_ASSOCIATED | never alone supports “caused” |

---

## Example reconstructions (case study: `psyweb-20260921T041444.727355Z-ec8b45bc` mindset)

### A. Action consequence
observation → decision → MOVE(+…) → displacement/orientation → next observation  
- V2: TEMPORALLY_ASSOCIATED (pose + legacy action)  
- V3 CORE: DIRECT via spine IDs  

### B. Resource-directed behavior
resource state → observation → decision → movement → resource_delta  
- V2: TEMPORALLY_ASSOCIATED (resources on timeline)  
- V3 CORE: stronger if observation includes resource-accessible channels; still **NOT_ESTABLISHED** as “seeking” (hypothesis layer)

### C. Signal interaction
experimenter emit → field → reception → later decision → motor → distance-to-source  
- V2: RECEIVED_FROM partially via events; later action only TEMPORALLY_ASSOCIATED; attribution often mixed  
- V3: better with emission/reception IDs + decision spine; approach remains DERIVED/HYPOTHESIS  

### D. Visual orientation
other body → optical → exo → decision → neck → bearing change  
- V2: exposure episodes + next-action assoc; cognition linkage NOT_ESTABLISHED  
- V3: ObservationReceipt + MotorReceipt neck component enable RECONSTRUCTED chain; “looked at” stays hypothesis  

### E. Prediction revision
prediction → future observation → error → revision → later prediction  
- V2: usually NOT_ESTABLISHED / aggregates  
- V3 RESEARCH: RevisionReceipt when mechanisms enabled  

---

## Query model (Analyzer API sketch)

```text
get_agent_timeline(agent_id)
get_observation(tick, agent_id)
get_decision(tick, agent_id)
get_motor(tick, agent_id)
get_consequence(tick, body_id)
trace_forward(node_id) / trace_backward(node_id)
get_relationships(type, range)
get_coverage(domain)
get_identity_map()
```

---

## Fact vs hypothesis

“Signal physically contributed to sensor” → EVIDENCE_GRAPH  
“Reception preceded MOVE toward emitter” → DERIVED distance + TEMPORALLY_ASSOCIATED / tested hypothesis  
“Agent searched for source” → HYPOTHESIS only  
