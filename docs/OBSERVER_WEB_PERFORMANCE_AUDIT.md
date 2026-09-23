# Observer Web performance audit (demand-driven UI)

**Date:** 2026-09-21  
**Workload:** seed 733, warmup 20, N=60, `evidence_mode=SEARCH_COMPACT`  
**Artifact:** `results/observer_performance/before_benchmark.json`

## 1. Method

Measured on the local Desktop tree (same Observer the experimenter runs).

| Label | What |
|-------|------|
| A | Bare `PhysicalSystemRuntime.step` |
| B | `ObserverSession` HEADLESS + SEARCH_COMPACT via public `step()` |
| D | Session step + sync `_capture_locked(compact)` + sampled JSON |
| E | Session step + sync `_capture_locked(full)` + sampled JSON |
| F | E + SMC/HSS diagnostic panels each tick |

Note: public `ObserverSession.step()` always captured **full** detail before this work (inspect-grade), so B≈E cost.

## 2. BEFORE measurements

| Mode | p50 ms/tick (or stage) | ticks/sec | payload p50 |
|------|------------------------|-----------|-------------|
| A headless runtime | **4.22** | ~235 | 0 |
| B session HEADLESS (public step=full capture) | **67.8** | ~15 | (full) |
| D frame_build compact | **3.46** | — | **512 KB** |
| D JSON serialize compact (sampled) | **8.1** | — | 512 KB |
| E frame_build full | **4.45** | — | **1.84 MB** |
| E JSON serialize full (sampled) | **28.9** | — | 1.84 MB |
| F full + diag panels | **75.0** | ~12 | — |

Stage microbench (after warmup):

| Stage | ms |
|-------|-----|
| live_frame compact | 3.03 |
| capture_locked compact | 3.53 |
| live_frame full | 4.34 |
| capture_locked full | 4.72 |

Isolated path breakdown (N=40, seed 733):

| Path | p50 ms |
|------|--------|
| scientific tick only (session wrapper) | ~10.0 |
| sci + evidence append | ~10.9 |
| sci + append + compact capture (no JSON) | ~15.8 |
| sci + append + **full capture + JSON** | **~63.2** |
| public `step()` | ~65.7 |

## 3. Root causes (ranked)

1. **Full-detail live frame + `json.dumps`** — ~50 ms of the ~66 ms public-step cost. Compact frame build is only ~3.5 ms; full JSON is ~29 ms vs compact ~8 ms; payload 1.8 MB vs 0.5 MB.
2. **Public `step()` always used `detail="full"`** — every API step paid inspect-grade serialization even when experimenter did not need it.
3. **Session scientific wrapper** — ~6 ms over bare runtime (hooks / bookkeeping); evidence append is small (~1 ms) in SEARCH_COMPACT.
4. **Optional diagnostic HTTP panels** — small vs (1); still wasteful when panels are mounted but unused interest-wise.
5. **Frontend** — secondary for this backlog; 1 Hz panel polls and hidden-tab work are easy wins.

**Not the dominant issue:** world rendering itself, or compact RUNNING capture (already decoupled via `ui_hz` + latest-wins capture worker).

## 4. Tier classification (producers)

| Tier | Products | Repo producers |
|------|----------|----------------|
| T0 Scientific core | evidence/receipts, runtime.step | `scientific_history`, `_append_scientific_locked`, V3 — **never gated by UI** |
| T1 World view | `world` | `live_frame` physical/body, geometry overlay |
| T2 Light telemetry | `telemetry`, `mechanisms` | header TPS/tick, mechanism snapshot/summary |
| T3 Cognition panels | `cognition`, `psc`, `smc`, `historical_sensorimotor_selection`, `prediction`, … | `agents_views_frame` mind/pipeline, diagnostic panel APIs |
| T4 Graphs / diagnostics | `graphs`, `diagnostics`, `signals`, `experimenter` | trajectory/telemetry series, signal/experimenter compact blocks |

## 5. Existing machinery retained

- Capture worker, latest-wins pending, visual drop counters
- RUNNING → compact frames; PAUSED/INSPECT → full available
- `execution_mode` LIVE/FAST/MAX/HEADLESS (wall-clock / ui_hz) — **orthogonal** to Observer detail presets
- Cooperative step_lock yield for capture

## 6. Implications for optimization

Demand-driven Observer detail must:

- keep T0 always on
- avoid building/serializing T3/T4 without subscription
- default NORMAL (compact + useful panels)
- never change action selection / RNG / receipts when switching MINIMAL↔FULL

## 7. AFTER measurements (same seed/N)

Artifact: `results/observer_performance/after_benchmark.json`

| Mode | p50 ms/tick | ticks/sec | payload p50 |
|------|-------------|-----------|-------------|
| A headless runtime | 4.38 | ~225 | 0 |
| Observer MINIMAL | **28.1** | ~35 | **474 KB** |
| Observer NORMAL | **28.3** | ~34 | **491 KB** |
| Observer FULL | 68.2 | ~14 | 1.87 MB |

Comparison vs BEFORE public-step/full path (~67.8 ms / ~15 t/s):

- MINIMAL/NORMAL public `step()` ≈ **2.4× faster** than prior always-full STEP capture (measured 28 vs 68 ms).
- FULL remains inspect-grade (by design).
- EXACT_MATCH actions across MINIMAL/NORMAL/FULL: **True**.

Long-run (800 ticks, toggling MINIMAL↔NORMAL): `visual_dropped_delta=0`; `ru_maxrss` high-water rose (Python allocator + evidence). Not attributed to unbounded display queues (latest-wins still in force). Distinguish from intentional on-disk evidence growth.

## 8. Remaining bottlenecks

- Scientific session wrapper still ~10 ms vs bare ~4 ms.
- Compact live payload still ~0.5 MB (world/geometry-heavy).
- FULL JSON ~29 ms serialize — expected for inspect.
- True independent per-product cadence emission inside one WS frame is only partially realized (interest gates build/serialize; `ui_hz` still sets push rate).
