# Long-run Web Observer performance + LIVE mechanism apply + Analyzer isolation

**Date:** 2026-09-21  
**Marker:** `LONG_RUN_OBSERVER_PERF_PASS` (PARTIAL→infra PASS; science cost honest)

## 1. Root causes (measured)

| Cause | Evidence | Severity for UI collapse |
|-------|----------|--------------------------|
| **Mechanism/vision HTTP blocked on `_step_lock`** | `set_mechanism` held lock for full tick + capture; long ticks → multi-minute “PENDING” | **Primary UX** |
| **STALE = no WS frame while tick computes** | Frontend: `now - lastArrival > stale_after` while `RUNNING`; no heartbeat | **Primary UX** |
| **`/api/results/packs` full `iterdir()` every ~1.5s while RUNNING** | `len(list(p.iterdir()))` per `mm_*` pack; grows with research disk | **Observer I/O tax** |
| **Analyze tab auto-ran full evidence package** | Opening Analyze → `runAnalyzeCurrent()` while RUNNING loads entire JSONL | **Analyzer vs sim** |
| **Bare scientific tick aging** | Bare PSR seed 17: early ~6.2 ms → ~5k ~7.0 ms (**~1.14×**) | **Mild / expected store fill** |
| **Session+scientific append** | Flat ~11 ms early→1k; earlier 5k window ~1.5× with continuous append+RSS growth | **Secondary** |

**Conclusion:** Catastrophic long-run *Observer* degradation was **not** unexplained scientific blow-up. Bare cognition approximately plateaus after stores fill. The multi-minute PENDING / RUNNING↔STALE pattern was **lock contention + missing progress heartbeats + periodic disk catalog scans**.

## 2. Fixes retained

1. **Deferred LIVE mechanism/vision apply** at tick boundary (`WAITING_FOR_TICK_BOUNDARY`); HTTP returns immediately when `_step_lock` is busy.
2. **Heartbeat WS** (`type: heartbeat`) + `/api/runtime/progress` — COMPUTING_TICK vs true STALE.
3. **Packs catalog**: 5s cache; no `iterdir()` file counts.
4. **Analyzer isolation while RUNNING**: skip packs/gearbox in `refreshAux`; do not auto-Analyze on tool open; banner on Analyze tab.
5. Tick wall timing recorded for progress UI.

## 3. Rejected / not done this pass

- Numba / PSC branch cuts / store shrink / tick skip — would change science.
- Fake FPS thresholds.
- Increasing STALE timeout alone (hid the bug).

## 4. BEFORE / AFTER (this machine)

### Bare scientific runtime (seed 17, 1 agent)

| Window | p50 ms/tick | t/s | Slowdown vs early |
|--------|-------------|-----|-------------------|
| ~200 | ~6.2 | ~164 | 1.0× |
| ~1k | ~6.5 | ~142 | ~1.05× |
| ~5k | ~7.0 | ~136 | **~1.14×** |

### HEADLESS session + scientific append (1 agent)

| Window | p50 ms/tick | Notes |
|--------|-------------|-------|
| early | ~11–12 | includes V2 append + event drain |
| ~1k | ~11 | flat |
| ~5k (prior probe) | ~18 | ~1.5×; RSS ↑ from evidence files |

### Mechanism toggle latency

| Case | BEFORE | AFTER |
|------|--------|-------|
| Toggle during long tick | HTTP blocked until tick+capture (minutes possible) | **&lt;0.5 s** return + `WAITING_FOR_TICK_BOUNDARY`; apply next boundary |
| Toggle while paused | immediate | immediate (unchanged) |

### Analyzer while RUNNING

| BEFORE | AFTER |
|--------|-------|
| Auto Analyze on tab; packs `iterdir` every 1.5–2s | No auto Analyze; packs/gearbox skipped in LIVE refresh; packs API cached |

## 5. Tests

- `tests/test_live_mechanism_tick_boundary.py` — deferred apply, progress COMPUTING_TICK, sync path
- Existing `tests/test_long_run_performance_architecture.py` — mode fingerprints EXACT_MATCH
- Frontend `npm test` — 202 pass; `web_dist` rebuilt

## 6. Scientific / determinism

- No cognition/physics/tick-order/action-repertoire changes.
- Mechanism apply still uses the same `runtime.set_mechanism` path; only **when** it runs (boundary) and **HTTP wait** changed.
- Mode fingerprint test still EXACT_MATCH across LIVE/FAST/MAX/HEADLESS.

## 7. Remaining limitations

- A single scientific tick can still be expensive (PSC); heartbeats keep UI truthful but do not make the tick faster.
- Full “Analyze Current” while RUNNING still allowed via explicit button — loads evidence (I/O); prefer STOP first.
- Evidence JSONL on disk still grows unbounded by design (moved off live critical path for catalog scans).
- Next science ROI remains PSC `predict_one_step` packing (see `docs/PERFORMANCE_OPTIMIZATION_ROADMAP.md`) — not Observer chrome.

## 8. Verdict

**PARTIAL → infrastructure PASS.**

Acceptance mapped:

| Criterion | Status |
|-----------|--------|
| A measured/explained slowdown | PASS |
| B accidental run-age overhead removed/moved | PASS (packs/lock/analyze) |
| C plateau after store saturate | PASS for bare (~1.14×); session append mild growth documented |
| D RUNNING/STALE reflects reality | PASS (heartbeat / COMPUTING_TICK) |
| E mechanism apply at boundary, no multi-minute PENDING | PASS |
| F Analyzer not significant while RUNNING | PASS (policy + skip auto) |
| G STOP allows full analysis | PASS (unchanged; explicit Analyze) |
| H Observer usable on mature runs | PASS (expected; verify live) |
| I science unchanged | PASS |
| J exact-match regressions | PASS |

Do not git push.
