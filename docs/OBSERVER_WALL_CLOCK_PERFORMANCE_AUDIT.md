# Observer wall-clock performance autopsy

**Date:** 2026-09-21  
**Scope:** Measurement and attribution only. **No optimizations.**  
**Prior compression audit:** `docs/PERFORMANCE_MEMORY_COMPRESSION_AUDIT.md` (`COMPUTATIONAL_COMPRESSION_PARTIAL`).

**Symptom under investigation:** interactive Observer ~**1.5–2.0 s/tick** near tick ~9000.

**Artifacts:**

- `results/performance_observer_autopsy/tick_profile.jsonl` (550 rows)
- `results/performance_observer_autopsy/summary.json`
- `results/performance_observer_autopsy/overhead_unpatched.json`

---

## 1. Executive diagnosis

### Primary classification

**`BOTTLENECK_NOT_REPRODUCED`**

Controlled production-path measurements through **tick 6000** (filled stores, SMC/HSS/PSC ON, 2 agents) never approach 1.5–2.0 s/tick.

| Mode (mature, SEARCH_COMPACT, tick ~3000–6000) | Wall p50 |
|------------------------------------------------|----------|
| A HEADLESS (science + evidence append, no capture) | **~34–37 ms** |
| B OBSERVER compact capture + JSON | **~49 ms** |
| C OBSERVER **full** capture + JSON | **~121–124 ms** |

Unpatched (no monkeypatch timers) at tick ~840: HEADLESS ~33 ms; full capture+JSON ~**87 ms**.

### Secondary classification (among measured costs)

When comparing FULL vs HEADLESS on the same science:

**`OBSERVER_CAPTURE_DOMINATED`** for the *extra* wall time (~80–90 ms), not for a multi-second tick.

Within FULL capture, the largest pieces are:

1. **`cognitive_view` / public cognition construction** (~40 ms timer; **8 calls/capture**)
2. **`memory_cost` JSON sizing** nested under snapshot (~32 ms timer; 2 calls)
3. **`json.dumps` of ~2.3 MB full frame** (~36 ms)
4. Runtime-required cognition (~30–34 ms: compose ~11 ms + predict_one_step ~9 ms)

Scientific evidence append is **small**: SEARCH_COMPACT ~0.1–0.2 ms; FULL_SCIENTIFIC ~4–5.5 ms at tick 1000.

### Implication for the missing ~1.45–1.97 s

Under this autopsy’s production tick path, **≥90% of measured wall time is attributed**, and the ceiling is ~0.12 s — leaving **~1.4–1.9 s unexplained by science+capture+JSON on this machine**.

Likely places the multi-second cost still lives (not proven here as “the murderer”):

- **Frontend main-thread** work on large WS/HTTP payloads (not coupled into `_loop` SIM time).
- **Synchronous STEP / PAUSED full captures** stacked with other API work while the user perceives “tick lag.”
- **Diagnostic / Analyze / packs** paths outside the SIM loop (historically expensive; partially mitigated).
- **Machine-specific I/O stalls** not seen in this run’s local SSD appends.
- **Mis-attribution of UI cadence** (1× throttle sleep, dropped captures, STALE) as “ms/tick.”

This report documents what the **real SIM+capture path** costs, and what it does **not**.

---

## 2. Production tick call path

```text
ObserverSession.play() → daemon _loop()
  │
  ├─ _yield_step_lock_to_capture()          # coop yield to capture worker
  ├─ with _step_lock:
  │     _scientific_step_once_unlocked()
  │         experimenter pre → runtime.step(1) → experimenter post
  │         (_last_tick_wall_ms = science-only wall under this call)
  │     with _lock:
  │         _accumulate_events_locked()
  │         _record_motion_locked()
  │         _append_scientific_locked()     # SEARCH_COMPACT or V2+V3
  │     maybe schedule capture if ui_hz period elapsed
  │
  ├─ _request_observer_capture(detail=_frame_detail_for_speed())
  │     # RUNNING → "compact"; never waits for live_frame
  │     capture worker later:
  │       acquire _step_lock
  │       _capture_locked(detail, serialize=False)
  │       geo overlay outside lock
  │       _serialize_published / _maybe_push
  │
  └─ sleep(remain) for wall-clock throttle (1× → 25 ms period target)

API step() (PAUSED path):
  with _step_lock:
    N × (scientific step + append)
    _capture_locked(detail="full" if Observer preset FULL else "compact")
  push frame  # SYNCHRONOUS capture — can include full JSON path
```

**Evidence:** `session.py` `_loop` (~3531), `step` (~1835), `_capture_locked` (~863), `_append_scientific_locked` (~1426), `_frame_detail_for_speed` (RUNNING → compact).

---

## 3. Wall-clock budget (representative FULL tick)

Example: SEARCH_COMPACT, checkpoint 3000, mode C (sync full capture+JSON under lock — **worst-case Observer capture**, stricter than async RUNNING).

| Category | p50 ms | Notes |
|----------|--------|-------|
| RUNTIME / cognition (`runtime.step`) | ~33 | Includes compose/PSC; see §6 |
| SCIENTIFIC_EVIDENCE_APPEND | ~0.13 | SEARCH_COMPACT |
| OBSERVER_CAPTURE (build frame) | ~52 | Includes ~40 ms `cognitive_view` aggregate |
| SERIALIZATION (`json.dumps`) | ~36 | ~2.27 MB payload |
| LOCK_WAIT (uncontended probe) | ~0 | Contended RUNNING+capture not fully stressed here |
| **TOTAL** | **~124** | |
| Sum of parts | ≈ total | Unattributed typically **&lt;5%** |

Attribution gate: **PASS** for measured slow-ish FULL ticks (~120 ms).  
Attribution gate for user’s **1500–2000 ms**: **FAIL to reproduce** — cannot attribute seconds that do not appear.

---

## 4. Runtime-age scaling

SEARCH_COMPACT, mechanisms ON (PSC/SMC/HSS/vision):

| Tick | HEADLESS p50 | COMPACT+JSON p50 | FULL+JSON p50 | transitions | SMC | sel_json≈ |
|------|--------------|------------------|---------------|-------------|-----|-----------|
| 100 | 29.1 | 44.9 | 118.9 | ~108 | 39 | ~95 KB |
| 1000 | 33.3 | 48.2 | 118.7 | 128 | 256 | ~97 KB |
| 3000 | 33.9 | 48.9 | 123.5 | 128 | 256 | ~90 KB |
| 6000 | 36.6 | — | 121.0 | 128 | 256 | (filled) |

**Finding:** after store fill (~1k), wall times **plateau**. No growth toward seconds by tick 6k.

FULL_SCIENTIFIC (heavier append) at 100 / 1000: HEADLESS 33→38 ms (append 4.2→5.4 ms); FULL+JSON still ~121–122 ms.

---

## 5. HEADLESS vs MINIMAL vs FULL

| | HEADLESS | MINIMAL≈compact | FULL |
|--|----------|-----------------|------|
| `cognitive_view` calls/tick | 0 | 0 | **8** |
| `memory_cost` calls/tick | 0 | 0 | **2** |
| Payload | 0 | ~0.47 MB | ~2.3 MB |
| Capture build | 0 | ~7–9 ms | ~47–52 ms |
| JSON | 0 | ~8 ms | ~36 ms |
| Science | ~30–37 ms | same | same |

**D — FULL backend without browser:** mode C in this autopsy is in-process full capture+JSON with no frontend. Cost remains ~120 ms → **frontend not required to explain measured backend FULL cost**, and backend FULL alone still does not explain 1.5–2 s.

RUNNING production uses **async compact** capture, so interactive LIVE should track closer to **B (~49 ms)** plus throttle sleep — not C — unless something forces full frames (STEP + FULL preset, PAUSED inspect, or a regression).

---

## 6. PSC / composite contribution

| Metric | Mean per science tick (2 agents) |
|--------|----------------------------------|
| `compose_trajectories` calls | **2** (1/agent) |
| `predict_one_step` calls | **~151** |
| `soft_match` calls | **~130–137** |
| Compose timer | **~11 ms** |
| predict_one_step timer | **~9 ms** |
| soft_match timer | **~2 ms** |

**Runtime-required** vs **Observer-induced:**

- Compose / predict_one_step / soft_match occur in **HEADLESS** at the same call counts → **runtime-required**.
- FULL capture does **not** increase compose calls (still 2).
- FULL capture **does** add `cognitive_view` ×8 and `memory_cost` ×2 — **Observer-induced**, and these do **not** call compose (no second cognition pass into PSC).

**Answer to §13 options:** **D** — compose is not responsible for multi-second wall time; it remains ~11 ms inside ~30 ms science.

---

## 7. Observer public-view contribution

| Question | Result |
|----------|--------|
| Calls to `cognitive_view` per FULL capture | **8** (`POSSIBLE_DUPLICATE_WORK`) |
| Per compact capture | **0** |
| Under `_step_lock`? | Yes when capture runs sync (STEP / worker with lock) |
| Same-tick cache | Present on `PhysicalSystemRuntime.cognitive_view`; TwoAgent delegates per-slot |
| Invokes predict/compose? | **No** (counters unchanged) |
| Invokes `memory_cost`? | **Yes** via `pc.snapshot` inside `cognition_public_view` |
| Construction time | ~40 ms aggregated across 8 calls (dominated by first uncached build + memory_cost) |
| Serialize time | separate ~36 ms for whole frame |

`cognition_public_view` monkeypatch counter stayed 0 because `runtime.py` binds the function at import; `cognitive_view` / `memory_cost` wrappers still captured cost.

---

## 8. Duplicate-work analysis

| Function | Calls/tick (FULL) | Unique necessity | Flag |
|----------|-------------------|------------------|------|
| `compose_trajectories` | 2 | 2 agents | OK |
| `predict_one_step` | ~151 | compose×actions | OK (known filled cost) |
| `soft_match` | ~133 | misses | OK |
| `cognitive_view` | **8** | should be ≤#slots after cache | **POSSIBLE_DUPLICATE_WORK** |
| `memory_cost` | 2 | 2 agents via snapshot | OK-ish; expensive JSON size |

Do **not** cache yet (task rule). Flag only.

---

## 9. Scientific evidence I/O

| Mode | Append p50 | Notes |
|------|------------|-------|
| SEARCH_COMPACT | ~0.1–0.2 ms | Tiny vs science |
| FULL_SCIENTIFIC | ~4–5.5 ms at ≤1k | Buffered JSONL; meta rewrite on flush; **no fsync/record** |

V3 `append_runtime_tick` included in FULL_SCIENTIFIC path; still single-digit ms here.

**Not** the multi-second murderer on this machine/workload.

Bytes/tick evidence: not the dominant FULL payload; full **live frame** JSON is ~2.3 MB when captured.

---

## 10. Lock / synchronization

| Metric | Probe result |
|--------|--------------|
| Lock wait (uncontended measure windows) | ~0 |
| Lock held HEADLESS | ≈ science+append (~34 ms) |
| Lock held FULL sync capture | ≈ science+append+capture+JSON (~120 ms) |

**Pattern of concern (architecture, not timed to seconds here):**

If capture worker or STEP holds `_step_lock` during **full** frame build + serialize (~80+ ms), SIM `_loop` waits. Coop yield exists; RUNNING normally requests **compact**.  

A scenario that repeatedly does **full** captures under the step lock (FULL preset + STEP, or a forced full detail regression) would amplify lock-held time — still ~0.1 s/capture in our data, not 2 s, unless many stack or disk blocks inside the lock.

Frontend `refreshAux` interval exists; packs/gearbox skipped while RUNNING (prior long-run fix). Contended lock from frontend not measured as multi-second here.

---

## 11. Serialization

| Path | Calls | Bytes p50 | Wall p50 |
|------|-------|-----------|----------|
| Compact frame JSON | 1/capture | ~0.47 MB | ~8 ms |
| Full frame JSON | 1/capture | ~2.3 MB | ~36 ms |
| `memory_cost` internal `json.dumps` | 2/FULL | store-sized | ~32 ms (build path) |

Age growth of full payload: **flat** (~2.3 MB) from 100→6000 once cognition panels stabilize.

---

## 12. Frontend contribution

Not instrumented with `performance.now()` in this pass (backend autopsy first).

Backend evidence already shows:

- SIM `_loop` does **not** await frontend.
- Full 2.3 MB frames are **not** the RUNNING default (compact is).

Therefore frontend slowness can make the **UI feel** like 1–2 s/tick without making `_scientific_step_once_unlocked` take 1–2 s. That is a **coupling-of-perception** hypothesis, not a measured SIM budget line.

---

## 13. Profiler overhead

| | Headless p50 | Full cap+JSON p50 |
|--|--------------|-------------------|
| Patched autopsy windows | ~34 ms | ~121 ms |
| Unpatched spot check | ~33 ms | ~87 ms (cap 50 + json 37) |

Monkeypatches add noticeable cost on the FULL path (~30 ms), mostly timer wrappers around hot `predict_one_step` / view paths. **Order-of-magnitude conclusions unchanged** (tens–low hundreds of ms, not seconds).

---

## 14. Unattributed time

For FULL sync windows: parts sum ≈ total; unattributed typically **&lt;5–10 ms**.

For the user’s **1500–2000 ms** claim: **~1400–1900 ms remain outside this autopsy’s measured SIM+capture path** → reported as **not reproduced**, not as a silent unattributed bucket inside a 120 ms tick.

---

## 15. Ranked bottlenecks (measured wall-clock)

1. **FULL Observer capture + public cognition (`cognitive_view` ×8, `memory_cost`)** — ~40–50 ms  
2. **FULL frame `json.dumps` (~2.3 MB)** — ~36 ms  
3. **Runtime cognition (`compose` + `predict_one_step`)** — ~20 ms inside ~33 ms science  
4. **Compact capture + JSON** — ~15–16 ms total add-on  
5. **FULL_SCIENTIFIC append** — ~5 ms  
6. **SEARCH_COMPACT append** — ≪1 ms  

**Not ranked as multi-second causes:** raw memory re-scan, unbounded transition growth (capped), compose alone.

---

## 16. Architectural remedies (NOT IMPLEMENTED)

1. Deduplicate `cognitive_view` producers in `live_frame` / mind / pipeline (8→≤slots) — measure E2E after.  
2. Keep RUNNING on compact; never force FULL detail on the hot path (verify presets).  
3. Move `memory_cost` off LIVE capture entirely (Analyzer-only).  
4. Stream/delta WS payloads instead of 2.3 MB full frames.  
5. Frontend: measure parse/render of frame sizes; avoid retaining full inspect frames while RUNNING.  
6. Reproduce the user’s exact run: seed, evidence_mode, Observer preset, STEP vs PLAY, panel set, and capture `header.last_tick_wall_ms` + capture timings + browser Performance panel simultaneously.

---

## Final line

**`BOTTLENECK_NOT_REPRODUCED`**

Secondary (measured delta FULL−HEADLESS): **`OBSERVER_CAPTURE_DOMINATED`**.

Filled science remains ~30–37 ms; worst measured Observer-full sync path ~120 ms through tick 6000. The reported **1.5–2.0 s/tick** interactive cost is **not explained** by the production SIM → append → (compact|full) capture path measured here; next autopsy should target **frontend/main-thread**, **forced full/STEP paths**, and **out-of-loop APIs** with the user’s exact configuration.
