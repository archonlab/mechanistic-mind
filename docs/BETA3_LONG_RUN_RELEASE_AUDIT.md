# Beta 3 long-run Analyzer release audit

Incident run (preserved):  
`results/psychology_observer/psy_observer_web/.live-psyweb-20260923T015520.874726Z-f390c468`  
run_id `psyweb-20260923T015520.874726Z-f390c468`, last tick **29157** (spine **29156**).

## Gates

| Gate | Result |
|---|---|
| Original long-run artifacts preserved | PASS (job `forensic_mutated_names: []`) |
| Root cause identified | PASS (OOM from full JSONL materialization in Observer) |
| No scientific-history truncation | PASS |
| Streaming JSONL | PASS (sequential compact scan + stream SMC) |
| Bounded TickStory reconstruction | PASS (compact fields; no full 32 KB receipts) |
| Bounded episode reconstruction | PASS (state machines; episodes on disk) |
| No giant global DataFrame/list of full receipts | PASS |
| OLD vs NEW semantic oracle | PASS (`tests/test_beta3_bounded_analyzer.py`) |
| O→D→M→C reconstruction unchanged | PASS **58292 / 58292** on real run |
| Existing Analyzer tests | PASS where fixtures present; phase1 live fixture absent (skipped) |
| P0 cognition tests | PASS |
| save/restore tests | PASS (`test_psy_observer_save_stop`, `test_observer_aged_save_stop`) |
| Analyzer failure cannot kill/mutate paused runtime | PASS (subprocess; live dir not written) |
| progress/cancellation | PASS (progress.json + CANCEL file + terminate) |
| 20k real-run analysis completes | PASS (29156 ticks, 160 s) |
| machine remains responsive | PASS (peak 1.82 GB; MemAvailable ~15.7 GB; no extra swap) |
| memory growth bounded/acceptable | PASS (synthetic STRESS 50k ticks peak ~169 MB RSS) |
| no NaN/invalid analysis artifacts | PASS (summary NaN scan 0) |
| real-run behavioral report | PASS (`results/beta3_long_run_analysis/BEHAVIORAL_SANITY_REPORT.md`) |

**BETA3_ANALYZER_RELEASE_GATE = PASS**

## Memory benchmark (synthetic compact receipts)

See `results/beta3_analyzer_memory/memory_benchmark.csv`.

| label | ticks | ΔRSS KB | peak RSS KB | wall s | tick stories |
|---|---|---|---|---|---|
| SHORT | 1k | 26648 | 64164 | 0.59 | 2000 |
| MEDIUM | 5k | 57728 | 113704 | 2.74 | 10000 |
| LONG | 20k | 89072 | 163872 | 10.82 | 40000 |
| STRESS | 50k | 58164 | 168796 | 27.14 | 100000 |

STRESS peak ≈ LONG peak (same process). Not ~linear in historical full receipts.

## Real aged run

| | |
|---|---|
| source ticks | 1–29156 (meta last_tick_written 29157) |
| input | ~2.27 GB scientific files (`bytes_total`) |
| wall | 160.0 s |
| peak RSS | 1821100 KB (~1.78 GiB) |
| TickStories | 58292 |
| O→D→M→C | 58292 / 58292 |
| Observer during re-run | not started; analyzer was a separate process |

## Remaining limitations

- Compact TickStory list and sensorimotor steps are still O(ticks) RAM (small per row).
- SMC/HSS/embodied aggregators re-read full `scientific_decisions.jsonl` (time, not RSS).
- Per-tick terrain meshes are not in the archive (PARTIAL historical geometry).
- `GET /api/analysis/evidence` no longer returns bulk rows; heavy work is `/api/analysis/jobs`.
- Current-run Signal Forensics still uses a separate path and can be expensive if bulk rows are requested.
