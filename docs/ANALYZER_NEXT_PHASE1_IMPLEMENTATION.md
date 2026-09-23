# ANALYZER NEXT — PHASE 1 IMPLEMENTATION

**Status:** Implemented (analysis-only)  
**Date:** 2026-09-21  
**Acceptance fixture:** `psyweb-20260921T064313.398170Z-f82f5a38` (live dir; seed 733; cutoff 2334)

## Goal

Make Analyzer use SCIENTIFIC_V3 CORE receipts to reconstruct evidence-backed behavioral stories:

Observation → Decision → COMPOSITE_MOTOR_V1 → Consequence

joined to vision / signals / contact / resources / geometry — without inventing cognition, rewards, motivation, recognition, or communication.

## Architecture

Package: `mechanistic_mind/scientific_v3/analyzer_next/`

| Module | Role |
|--------|------|
| `relationships.py` | Typed `RelationshipGraph` / `NodeRef` / edge strengths |
| `tick_stories.py` | Canonical per-agent/per-tick `TickStory` from `RunEvidence` spine |
| `joins.py` | Vision / signal / contact / wrap geometry joins |
| `geometry.py` | Toroidal distance, approach decomposition, orienting error |
| `episodes.py` | Deterministic episode extraction |
| `contrasts.py` | Within-run DERIVED_ASSOCIATION contrasts |
| `interestingness.py` | Deterministic story/episode selection (no LLM) |
| `report.py` | `BEHAVIORAL RECONSTRUCTION` text |
| `pipeline.py` | Orchestration + artifacts |

Uses existing `RunEvidence` API — **no parallel evidence loader**.

## Web wiring

1. `load_evidence_package` attaches `behavioral_reconstruction` (+ writes `analyzer_next/` artifacts under the run dir).
2. Frontend `analyzeEvidencePackage` copies it onto the analysis object.
3. `formatAnalysisLog` emits **BEHAVIORAL RECONSTRUCTION** before SIGNAL FORENSICS.
4. Legacy `SCENARIO_SELECTED` is labeled as compatibility-only; V3 DecisionReceipts are authoritative when present.

Download Analysis Log path unchanged: Analyze Results → Analyze → Download Analysis Log.

## Relationship types (Phase 1)

AVAILABLE_TO_AGENT, PART_OF_OBSERVATION, PART_OF_DECISION_CONTEXT, SELECTED, PRODUCED_MOTOR, PHYSICALLY_RESULTED_IN, RECEIVED_FROM, PHYSICALLY_CONTRIBUTED_TO, OBSERVED_AS, TEMPORALLY_FOLLOWED, DERIVED_ASSOCIATION, NOT_ESTABLISHED, NOT_RECORDED

Specific sensory-component → decision causation is always **NOT_ESTABLISHED** unless a future receipt proves it.

## Artifacts

- `analysis_relationship_graph.json` (bounded)
- `analysis_tick_stories.jsonl`
- `analysis_episodes.json`
- `analysis_behavioral_summary.json`
- `BEHAVIORAL_RECONSTRUCTION.txt`

## V2 compatibility

If SCIENTIFIC_V3 is absent: status `NOT_RECORDED`, no fabricated O→D→M→C.

## Runtime science

**Untouched.** Analyzer / Observer evidence packaging / frontend log only.

## Tests

`tests/test_analyzer_next_phase1.py` — gates 1–10 style coverage + geometry + determinism + language boundary.

## Performance (seed-733, cutoff 2334)

~3.3 s for 4670 TickStories on local machine (~0.7 ms/story). Linear extrapolation: ~7 s @ 10k, ~68 s @ 100k, ~11 min @ 1M (then stream stories / retain indexes only).

## NO GIT PUSH

Local Desktop work only; do not push.

## Phase 1b — Sensorimotor consequence (2026-09-21)

Added `sensorimotor.py`: T→T+1 consequence chaining, MOTOR_REVERSAL, SENSORIMOTOR_TREND_REVERSAL, RECEDING_WHILE_WATCHING search, longitudinal windows, visual asymmetry geometry, target-interval reconstruction (incl. t3250–3315).

Artifacts include `analysis_sensorimotor_consequence.json`. Download log embeds both BEHAVIORAL RECONSTRUCTION and SENSORIMOTOR CONSEQUENCE ANALYSIS.

Capability audit: `docs/ANALYZER_NEXT_TARGET_RUN_CAPABILITY_AUDIT.md`.

Full acceptance pack: `results/mm_analyzer_next_phase1/full_f82f5a38/`.
