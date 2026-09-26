# Beta 3 long-run Analyzer failure — forensic inventory

**Do not mutate these artifacts.** This file is evidence, not a repair log.

Incident time (kernel): **2026-09-23 06:52:13** local  
`Out of memory: Killed process 269596 (python) total-vm:16684052kB, anon-rss:15410428kB`  
OOM killer invoked by `ChatGPT` (desktop app allocating while the machine was already exhausted). Classic swap-thrash freeze (mouse stuck) then SIGKILL of the Observer Python process.

## Identified run (Analyze target)

| Field | Value |
|---|---|
| Live directory | `results/psychology_observer/psy_observer_web/.live-psyweb-20260923T015520.874726Z-f390c468/` |
| run_id | `psyweb-20260923T015520.874726Z-f390c468` |
| Runtime | TwoAgentRuntime, seed 177, generation 3 |
| Ecology | STRUCTURED_WORLD_EXPERIMENTAL |
| last_tick_written (V2 meta) | **29157** |
| V3 ticks_captured | 27434 (meta lag vs timeline; spine last tick **29156**) |
| opened_at | 2026-09-23T02:00:36Z |
| updated_at | 2026-09-23T04:42:27Z (files mtime **06:42** local — still appending until pause) |
| Analyzer output in live dir | **none** (`analyzer_next/` absent — process died before artifacts) |
| Finalized `psyweb-*` for this id | **none** (paused live staging, not Save & Stop) |

### Files (live dir, sizes at inventory)

| File | Size | Lines (where counted) | Last tick | Status |
|---|---|---|---|---|
| scientific_decisions.jsonl | **1900.31 MB** | 58292 | 29156 | live/complete-enough for analysis; huge per-line cognition receipts |
| scientific_events.jsonl | 106.98 MB | 260081 (meta events_written) | — | live |
| scientific_timeline.jsonl | 93.08 MB | 58292 | 29157 | live; last line valid JSON |
| scientific_observations.jsonl | 64.45 MB | 54868 (v3 counts; file may have more) | — | live |
| scientific_consequences.jsonl | 41.69 MB | 54868 (v3) | — | live |
| scientific_motors.jsonl | 34.37 MB | 54868 (v3) | — | live |
| scientific_spine.jsonl | 30.20 MB | **58292** | 29156 | live; valid last JSON |
| scientific_checkpoints.jsonl | 0.02 MB | — | — | live |
| scientific_meta.json | 14 KB | — | 29157 | live |
| scientific_v3_meta.json | 1.6 KB | — | ticks_captured 27434 | live; counts slightly behind spine |
| identity_map.json | 1 KB | — | — | present |
| search_compact/ | dir | — | — | observer search cache; not mutated by this task |

First decision line ~2.7 KB; **mean decision line ~32.6 KB**. Python `json.loads` of the whole file is typically several× the file size.

## Related large artifacts (not the Analyze incident; do not touch)

| Path | last_tick | Size | Note |
|---|---|---|---|
| `.live-psyweb-20260921T210500.373847Z-6080792b` | **4_314_272** | **75.8 GB** | Pathological tick/log growth. Not the ~20k paused run. Do not Analyze. |
| `.live-psyweb-20260921T211344.366902Z-aece9f34` | 23854 | 1.74 GB | Older 20k-class live |
| `.live-psyweb-20260922T192322.056455Z-f9b24837` | 10231 | 709 MB | Prior Save/Stop OOM forensic; keep |
| `.live-psyweb-20260919T080956.183903Z-c59942d7` | 20381 | 669 MB | V2-only style (events+timeline) |

## Kernel OOM history (this host)

| Time | PID | RSS | Note |
|---|---|---|---|
| 2026-09-22 05:58 | 20829 python | ~19.9 GB | earlier python OOM |
| 2026-09-22 23:03 | 179327 python | ~14.6 GB | Save & Stop snapshot OOM (documented separately) |
| **2026-09-23 06:52** | **269596 python** | **~15.4 GB** | **Analyze / evidence load on aged live run** |

## Pipeline that ran at Analyze

`GET /api/analysis/evidence` (same uvicorn process, same event loop)

1. `ObserverSession.scientific_evidence` → `load_evidence_package`
2. `iter_jsonl` **materializes** `scientific_timeline.jsonl` and `scientific_events.jsonl` as `list[dict]`
3. `scientific_v3_core_reconstruction` → `RunEvidence.__init__` **materializes** observations, **decisions**, motors, consequences, spine into dicts/lists
4. `build_behavioral_reconstruction` → **second** `RunEvidence` + `list[TickStory]` holding **references to those full receipts** + full timeline index + full events-by-tick
5. HTTP handler blocked until complete or SIGKILL

No `analyzer_next` artifacts were written → death during load/reconstruct, before `write_behavioral_artifacts`.

## Root-cause statement (Phase 1)

**Working-memory cost is proportional to the entire scientific JSONL corpus parsed into Python objects, in the Observer process.**

Dominant term: `scientific_decisions.jsonl` (1.90 GB on disk) loaded twice conceptually (core reconstruction + behavioral reconstruction) via `RunEvidence._dec`. Expected RAM: **order 10–20 GB**, matching the 15.4 GB RSS kill.

Contributing terms: timeline index (`joins.load_timeline_index`), events (`load_events_by_tick`), TickStory list retaining full observation/decision/motor/consequence dicts.

Not: frontend rendering of 29k ticks (payload is summaries). Not CPU-only. **OOM + swap thrash.** Desktop unresponsive because the kernel was reclaiming/killing under global OOM.

This is **not** scientific-history truncation. Fix must stream/index JSONL and drop receipt objects after extracting analyzer fields. Canonical JSONL stays on disk unchanged.

## Post-fix verification (do not mutate evidence)

Re-analysis of the same live directory (read-only) completed 2026-09-23T05:08Z:

- output: `results/beta3_long_run_analysis/` (not inside the live dir)
- forensic directory extra names after job: **none**
- TickStories 58292, complete O→D→M→C **58292 / 58292**, last tick **29156**
- analyzer subprocess peak RSS **1.82 GB** vs incident **15.4 GB**
- wall **160 s**
- swap free unchanged (~15 MB of 2 GB already used; no additional swap pressure)

