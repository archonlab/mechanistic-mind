# ANALYZER NEXT — TARGET RUN CAPABILITY AUDIT

**Run:** `psyweb-20260921T064313.398170Z-f82f5a38` (live)  
**Seed:** 733 · **Runtime:** TwoAgentRuntime · **Map:** 32×32 WRAP_PERIODIC  
**Audit date:** 2026-09-21  
**Evidence window audited:** ticks 0–3520 spine / timeline through 3521 · V3 receipts 7042/7042 complete

## Verdict

**Missing analysis ≠ missing evidence.** SCIENTIFIC_V3 CORE already provides a complete O→D→M→C spine. Relative geometry, optical magnitude, and head/sensor orientation are reconstructable from timeline + vision_optical Observer GT + ObservationReceipt accessible exo/FIELD without new telemetry.

No SCIENTIFIC_V3 Phase 2 fields are required for the sensorimotor questions in this task.

## Capability matrix

| ID | Quantity | Classification | Source |
|----|----------|----------------|--------|
| A | body position | AVAILABLE_DIRECT | `scientific_timeline.jsonl` x,y |
| B | body orientation | AVAILABLE_DIRECT | timeline `theta` / `omega` |
| C | head / sensor orientation | AVAILABLE_DIRECT | timeline `head_world_heading`, `head_relative_angle` |
| D | authoritative sensor orientation (articulated) | AVAILABLE_DIRECT | nonzero `head_relative_angle` on majority of ticks; use `head_world_heading` when present |
| E | other-body physical position | AVAILABLE_DIRECT | peer timeline row same tick |
| F | toroidal distance | AVAILABLE_DERIVED | wrap-aware distance on 32×32 |
| G | bearing to other body | AVAILABLE_DERIVED | atan2 wrap deltas |
| H | relative bearing (body) | AVAILABLE_DERIVED | bearing − theta |
| I | angular sensor/head error | AVAILABLE_DERIVED | bearing − head_world_heading; also Observer `neighbors_optical.relative_angle_deg` |
| J | body-derived optical contribution | AVAILABLE_DIRECT | `vision_optical.foreign_body_contribution` / `foreign_body_total` / `source_bodies_gt` (Observer GT — not agent-accessible identity) |
| K | exo_L/F/R accessible | AVAILABLE_DIRECT | ObservationReceipt `accessible.exo_*` |
| L | FIELD_A/B accessible | AVAILABLE_DIRECT | ObservationReceipt `accessible.local.FIELD_*` |
| M | DecisionReceipt | AVAILABLE_DIRECT | `scientific_decisions.jsonl` |
| N | selected continuation / path | AVAILABLE_DIRECT | DecisionReceipt selection_* fields |
| O | authoritative composite motor | AVAILABLE_DIRECT | MotorReceipt COMPOSITE_MOTOR_V1 |
| P | physical displacement T→T+1 | AVAILABLE_DIRECT | ConsequenceReceipt.pose_delta (+ timeline) |
| Q | orientation/head change T→T+1 | AVAILABLE_DIRECT | ConsequenceReceipt.orientation_delta |
| R | distance change T→T+1 | AVAILABLE_DERIVED | F at T and T+1 |
| S | optical change T→T+1 | AVAILABLE_DERIVED | Δ foreign_body_total / Δ accessible exo |
| T | resource/work changes | AVAILABLE_DIRECT | ConsequenceReceipt.resource_delta + timeline |
| U | contact | AVAILABLE_DIRECT | timeline `contact` + CONTACT events |
| V | physical signal provenance | AVAILABLE_DIRECT | PHYSICAL_SIGNAL_* events (UNIQUE/MIXED/…) |

## Provenance rules (must not leak)

- `vision_optical.source_bodies_gt` / `identity_layer=OBSERVER_GT_ONLY` → Observer ground truth. May explain optical contribution; **must not** be treated as agent recognition.
- Agent-accessible state is only ObservationReceipt.`accessible` (and Decision/Motor as internal decision/motor evidence).

## Gaps (honest)

| Desired | Status | Note |
|---------|--------|------|
| Specific exo component → decision causation | NOT_RECORDED | No ablation / component-mask receipt |
| “Recognized other body” | NOT_RECORDED | No identity in accessible observation |
| Intent / seeking / following labels | NOT_APPLICABLE | Not implemented constructs |
| Learning claim | NOT_RECORDED | Longitudinal change ≠ proven learning |

## Conclusion for Analyzer

Proceed with Analyzer-only joins + sensorimotor consequence engine. **Do not** add runtime telemetry for this investigation.
