# ANALYZER_RELATIVE_Z_TAXONOMY_AND_PROGRESS_REPORTING_REPAIR_V1

## Summary

Repaired Analyzer volumetric relative_z taxonomy so it no longer hardcodes
`agent_selectable=NO` or treats pose `|relative_z|>0` as current-tick actuation.
Added genuine phase-aware analysis progress contract + UI progress bar.
Added EBAE observability capture into scientific `event_refs` for **future** ticks
(historical run still honestly reports EBAE refs absent).

## Taxonomy authority

| Concern | Authority |
|---|---|
| Control availability | Motor schema Z fields (incl. zero) → AVAILABLE; trace PRESENT; Tiktaalik/explicit ABSENT → UNAVAILABLE; else NOT_ESTABLISHED |
| Z request | Normalized `effector_z_left/right` ∈ {-1,0,+1,NOT_AVAILABLE}; nonzero ⇒ request |
| Actuation | EBAE receipt **or** (nonzero request ∧ generation-safe aligned pose delta). Never pose alone |
| Aggregate selectable | Evidence-derived YES/NO/NOT_ESTABLISHED |
| Footer | Dynamic from `relative_z` summary |

## Classes (mutually exclusive)

CONTROL_NOT_AVAILABLE · CONTROL_AVAILABILITY_NOT_ESTABLISHED · NOT_SELECTED ·
SELECTED_NOT_ACTUATED · ACTUATED_NO_DISPLACEMENT · ACTUATED_NO_GEOMETRIC_REACH ·
CONTACT_INSUFFICIENT_WORK · MATERIAL_FAILURE · DETACHED_MATERIAL_CREATED

## Old vs new (psyweb-…1a7d3be6 @ 2172)

| Metric | Old | New |
|---|---|---|
| agent_selectable | NO | YES |
| control_availability | (hardcoded) | AVAILABLE |
| ACTUATED_NO_GEOMETRIC_REACH | 4232 | **520** |
| NOT_SELECTED | 110 | **3826** |
| SELECTED_NOT_ACTUATED | 4 | 0 |
| z_request_nonzero | (hidden) | 520 |
| pose used as actuation | YES (bug) | NO |

## Progress contract

Phases: DISCOVER_EVIDENCE → LOAD_AND_VALIDATE → NORMALIZE_RECORDS → BUILD_TICK_STORIES →
RECONSTRUCT_PHYSICAL_CAUSALITY → BUILD_SUMMARIES → RENDER_EXPORT_PAYLOADS → COMPLETE|FAILED

Payload fields: job_id, state, phase, phase_index, phase_count, completed_units,
total_units, percent (or null), status_text, terminal, error_code, error_message.

UI: `analyzer-progress` / progressbar with aria-*; export disabled until COMPLETE.

## EBAE linkage

`capture.py` appends compact researcher-only refs from `last_agent_effector_z_actuation`.
Does not re-execute EBAE. Historical evidence of this run retains
`EBAE_EVENT_REFS_ABSENT_IN_HISTORICAL_EVIDENCE` + partial motor+pose-delta inference.

## Files

- `volumetric_physical_causal_reconstruction.py` — taxonomy + dynamic footer
- `capture.py` — EBAE event_refs
- `analyzer_next/job.py` — progress contract
- `AnalyzeResultsPanel.tsx` / `App.tsx` / `AnalyzeWorkspace.tsx` — progress UI
- tests + `web_dist` (`index-BtCFnM1b.js`)
