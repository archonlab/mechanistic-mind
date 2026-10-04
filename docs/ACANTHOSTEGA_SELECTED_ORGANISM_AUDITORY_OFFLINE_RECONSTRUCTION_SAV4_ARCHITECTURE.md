# SELECTED_ORGANISM_AUDITORY_OFFLINE_RECONSTRUCTION_SAV4 — Architecture Audit

**Status:** Architecture / saved-evidence / deterministic-replay only.  
**IMPLEMENTATION_STARTED = NO** · **TOTAL_SIMULATED_TICKS = 0**  
**Authority:** `RESEARCHER_OFFLINE_RECONSTRUCTION_ONLY` — not physics, not live playback, not cognition.

## Purpose

Design offline reconstruction of a selected organism’s recorded auditory history from **saved scientific evidence**, without live runtime, LPS replay, or inferred hearing.

```
saved A3/A5 evidence
  → organism/tick interval
  → deterministic SAV2 schedule
  → offline visual timeline
  → optional later PCM/export
```

## Verdict (short)

**IMPLEMENTATION_GATE = READY_WITH_CONSTRAINTS**  
**VERDICT = READY_WITH_CONSTRAINTS**  
**RECOMMENDED_NEXT_SLICE = SAV4A_SAVED_EVIDENCE_NORMALIZATION_AND_DETERMINISTIC_SCHEDULE**

Preferred input hierarchy:

1. `ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1` (full A3+A5)
2. `SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1` / exact A5 (schedule only)
3. else unavailable — never stream/probe/pixels/cognition as organism hearing

First scope: **visual reconstruction + canonical SAV2 schedule** (`CANONICAL_COMPLETE_FROM_SAVED_A5`).  
Defer browser/PCM export to later slices.  
**Do not** restore/step physics to manufacture sound.

## Critical repository findings

| Finding | Implication |
|---------|-------------|
| Live SAV1/OATT histories are FIFO **128** | Live frame may evict; tick-synchronous capture into append-only consequences can retain fuller history **when those schemas were active** |
| Inspected saved runs use `scientific_consequences.jsonl` | Several Analyzer loaders (incl. OATT/SAV1 helpers) currently look for `consequences.jsonl` — SAV4 must normalize both paths |
| Sample autopsy/e2e runs: `event_refs` **empty** | Pre-OATT/SAV1 capture era; no saved A3 traces on disk in inspected packages |
| `scientific_observations.jsonl` contains continuous `osc_l/r` | Legacy **partial A5** path exists; classify carefully; not OATT |
| SAV2 provenance is frontend-only (queue/mute/drops) | `HISTORICAL_MONITORING_REPLAY` **not supported** today |
| `canonical_seconds_per_tick = 0.05` | Playback parameter, **not** physical time |

## Evidence

`results/acanthostega_selected_organism_auditory_offline_reconstruction_sav4_architecture/`

## Preservation

Docs/results only. No capture, playback, physics, cognition, or live-run changes. No commit/push.
