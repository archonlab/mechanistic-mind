# Observer Performance Optimization — Decouple Simulation from Observation

**Date:** 2026-09-21  
**Verdict:** `OBSERVER_OPTIMIZATION_ACCEPTED`  
**Artifacts:** `results/observer_performance_optimization/`

## 1. Previous measured baseline

From `docs/OBSERVER_WALL_CLOCK_PERFORMANCE_AUDIT.md` (PSC/SMC/HSS-style cognition, mature bounded stores):

| Mode | ms/tick (audit) | Notes |
|---|---:|---|
| HEADLESS science + evidence | ~34–37 | cognition plateaus |
| Compact Observer + JSON | ~49 | RUNNING path |
| FULL Observer + JSON | ~121 | ~8× `cognitive_view`, ~2.3 MB frames |
| Primary audit class | `BOTTLENECK_NOT_REPRODUCED` | multi-second ticks not seen in controlled backend |
| FULL overhead class | `OBSERVER_CAPTURE_DOMINATED` | |

## 2. Root architectural problem

Scientific cognition (~30–37 ms/tick) was fine. The expensive path was **Observer representation**:

- One FULL capture reconstructed `cognition_public_view` about **8 times per tick** (mind + causal + pipeline + prospection × 2 agents).
- Nested `memory_cost` JSON sizing amplified that cost.
- LIVE risked looking like FULL (~2.3 MB) every simulation tick if detail was not forced compact.

Rule: **simulation frequency and Observer display frequency are independent.** Cognition still runs every tick. Only expensive public/UI representation may be decimated or cached.

## 3. Files changed

| File | Change |
|---|---|
| `mechanistic_mind/ui/psy_observer_web/serialize.py` | Optional `cog=` on panel builders; `agents_views_frame` builds **one** public view per agent on FULL and passes it; `observer_perf` on `live_frame` |
| `mechanistic_mind/physical_system/runtime.py` | Same-tick `_cognitive_view_cache` + build/hit stats |
| `mechanistic_mind/physical_system/two_agent.py` | Aggregate cache stats across slots |
| `mechanistic_mind/ui/psy_observer_web/session.py` | Stamp capture/serialization/bytes/queue into `observer_perf`; record `_last_serialized_bytes` |
| `web/psy-observer/src/App.tsx` | Lightweight HUD line from `observer_perf` |
| `mechanistic_mind/ui/psy_observer_web/web_dist/` | Rebuilt |
| `tests/test_observer_public_view_dedupe.py` | Regression: FULL builds == agents; compact builds == 0 |
| `results/observer_performance_optimization/` | Bench + science equivalence |

**Unchanged (intentionally):** cognition, PSC, SMC/HSS, compression, evidence writers, motor selection.

## 4. Same-tick public-view caching

`PhysicalSystemRuntime.cognitive_view()`:

- Keyed by `tick`.
- First call builds `cognition_public_view` once.
- Later same-tick callers reuse the immutable dict.
- Invalidates automatically when `tick` advances.
- Observer/public only — does **not** cache scientific decisions.

Additionally, `agents_views_frame` (FULL) calls `cognitive_view()` **once per agent** and threads `cog=` into mind / causal_chain / cognition_pipeline / prospection so panels never re-enter the builder.

### Call graph (two-agent FULL, after)

```
live_frame
  └─ agents_views_frame(detail=full)
       ├─ agent_0: cognitive_view()  → build #1
       │    ├─ mind_frame(cog=…)
       │    ├─ causal_chain_frame(cog=…)
       │    ├─ cognition_pipeline_frame(cog=…)
       │    └─ prospection_frame(cog=…)
       └─ agent_1: cognitive_view()  → build #2
            └─ (same four panels with cog=)
```

Target met: **one construction per agent per tick per FULL representation.** Compact: **zero** constructions.

## 5. `memory_cost` deduplication

`predictive_compression.memory_cost` already caches on structural occupancy keys (`ticks_lived`, raw counters, structure counts, …). With one public-view build per agent, `memory_cost` runs once per agent mem per FULL capture (not 4× nested rebuilds). Numerical definition unchanged; tests assert identical repeated results.

## 6. Canonical Observer snapshot

Boundary:

`runtime @ tick T` → `live_frame(..., detail=compact|full)` → `Observer` panels/routes consume the frame.

- FULL: shared `cog` snapshot per agent inside `agents_views`.
- Compact: `mind_compact_frame` / compact causal/pipeline — no `cognition_public_view`.
- Frame carries `observer.frame_detail`, `observer_perf.captured_tick`.
- UI consumers must not mutate runtime (unchanged contract).

## 7. LIVE compact path

Pre-existing + retained:

- `ObserverSession._frame_detail_for_speed()` → **always `compact` while `RUNNING`**.
- Compact frames ~**170 KB** in this bench (not ~1–2 MB FULL).
- Compact cognition summary uses metrics/selection only — not full structures.

## 8. FULL on-demand path

- PAUSE / STEP / explicit inspect still request `detail=full`.
- `observer_perf.captured_tick` identifies the tick represented.
- FULL remains scientifically faithful for that tick; LIVE does not stream FULL every step.

## 9. Simulation / Observer decoupling

Already in session (validated by `tests/test_observer_speed_decoupling.py`):

- `tick_sleep_seconds` / `observer_capture_period` / `ui_hz` vs simulation speed.
- Async capture worker, **latest-wins** pending queue (bounded depth 0–1).
- Cooperative yield so capture is not starved; SIM does not wait on React paint.
- Evidence append remains on scientific ticks independent of visual cadence.

## 10. Frontend changes

- HUD shows `Observer detail: COMPACT|FULL · tick · bytes · ms` from `observer_perf` when present.
- Existing `liveBounds.ts` caps timeline/events/trajectory — no unbounded FULL history in React state.
- `ObserverDetailControl` (MINIMAL/NORMAL/FULL interest) remains orthogonal to EVID mode.
- `web_dist` rebuilt after HUD change.

## 11. Before / after benchmarks

Method: `TwoAgentRuntime` seed 111, SMC + HSS bridge ON, 16×16, warm to checkpoint, then 30-tick windows measuring HEADLESS / compact `live_frame` / FULL `live_frame` (+ JSON size).  
**Note:** This probe times runtime + `live_frame` (no `ObserverSession` evidence I/O). Absolute HEADLESS ms differ from the audit's session+evidence path; use call counts and LIVE vs FULL ratios for the optimization claim.

### Mature table (checkpoint 6000)

| Mode | Before ms/tick | After ms/tick | ticks/sec | frame bytes | cognitive_view builds |
|---|---:|---:|---:|---:|---:|
| HEADLESS | 35.5 | 15.308 | 65.32 | 0 | 0 |
| COMPACT (LIVE) | 49.0 | 21.417 | 46.69 | 172437 | 0 |
| FULL | 121.0 | 64.708 | 15.45 | 1025553 | 2 |

FULL public-view builds: **8 → 2** (exactly agent count). LIVE compact builds: **0**.

### Flat through age (after ms/tick)

| Checkpoint | HEADLESS | COMPACT | FULL | FULL builds |
|---:|---:|---:|---:|---:|
| 1000 | 16.7 | 20.5 | 59.2 | 2 |
| 3000 | 15.4 | 23.6 | 60.8 | 2 |
| 6000 | 15.3 | 21.4 | 64.7 | 2 |
| 9000 | 14.6 | 20.4 | 60.2 | 2 |

No multi-second ticks; no age-scaling blow-up through 9000.

## 12. Long-run results

- Checkpoints 1000 / 3000 / 6000 / 9000 completed.
- Compact ~20–24 ms/tick; FULL ~59–65 ms/tick; HEADLESS ~15 ms/tick in this probe.
- Queue depth remains latest-wins (session architecture); drops counted in `observer_perf.queue_drops` when capture is busy.
- Frame sizes stable (compact ~172 KB; FULL ~1.0 MB in this config).

## 13. Scientific equivalence validation

Seed 111, 400 ticks, SMC+HSS ON:

| Pair | Match |
|---|---|
| HEADLESS vs compact-every-tick Observer | **True** |
| HEADLESS vs FULL every 10th tick | **True** |

Digest: `98b63ad538319e844ababafeff662f9f51d2019849a7de017aefba7e466c4197`

Observer timing/frame count may differ; **scientific tick-boundary state does not.**

Regression tests: `tests/test_observer_public_view_dedupe.py`, `tests/test_observer_speed_decoupling.py` — all passed.

## 14. Remaining bottlenecks

- FULL still ~60 ms/tick dominated by one `cognition_public_view` per agent + ~1 MB JSON — expected for diagnostic detail; not on LIVE RUNNING path.
- Original interactive **~1.5–2.0 s/tick** around 9000 was **not reproduced** on this backend path (consistent with audit `BOTTLENECK_NOT_REPRODUCED`). If it reappears interactively, capture a browser performance trace and correlate with `observer_perf` / capture timings — likely FE main thread, a specific FULL/STEP path, or host load, not cognition.
- Session evidence append and geo overlay costs were out of scope for this probe’s absolute ms (audit already attributed them separately).

## 15. Known limitations

- Optimization does not rewrite cognition or shrink scientific evidence.
- `observer_perf` is diagnostic metadata only.
- FULL frame byte size depends on store contents and detail; ~1 MB here vs ~2.3 MB in the audit config — both remain “FULL diagnostic,” not LIVE.
- No git push performed.

---

## Final verdict

**`OBSERVER_OPTIMIZATION_ACCEPTED`**

Acceptance checklist:

- [x] Scientific equivalence preserved (HEADLESS digests match Observer-amplified runs)
- [x] No Observer-induced scientific divergence
- [x] Duplicate public-view work materially reduced (8 → 2 builds / FULL tick)
- [x] LIVE no longer requires FULL multi-MB state every simulation tick (~172 KB compact)
- [x] Simulation decoupled from frontend rendering cadence (ui_hz + async latest-wins)
- [x] No unbounded frame backlog (bounded pending + FE retain caps)
- [x] Mature-run performance measured through ~9000
- [x] Original multi-second failure mode retested on backend path through 9000 — still not reproduced

A Tiktaalik may think on every tick. The Observer no longer writes a full biography about it on every tick.
