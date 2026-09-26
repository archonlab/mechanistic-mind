# Observer WEB — Beta 3 full UI / performance / architecture audit

**Date:** 2026-09-22  
**Mode:** AUDIT ONLY — no UI redesign, no refactor, no optimization, no git push, no change to science.  
**Artifacts:** `results/observer_beta3_audit/`

---

## 1. Executive summary

Psy Observer WEB is a **desktop-in-the-browser**: a left **Control Device** (experiment / observe / sensors / analyze), a **world canvas workspace**, floating inspector windows, and a **single top bar** that currently mixes simulation transport, execution policy, evidence policy, and Observer detail.

The runtime→Observer split is already real:

- Scientific ticks always run (T0).
- RUNNING presentation captures are **compact**, **async**, **latest-wins**.
- HEADLESS skips presentation capture entirely (`observer_fps = 0`).
- FULL `cognition_public_view` is gated to inspect/FULL paths and is **one build per agent per tick** (prior optimization retained).

Isolated autopsy (this machine, seed 17, 24×24, 1 agent, `SEARCH_COMPACT`, did **not** attach to the live user instance):

| Cost center | p50 | Scaling t500→t5000 |
|---|---:|---|
| Bare `PhysicalSystemRuntime.step` | **4.7 ms** | not aged here |
| Session scientific tick + evidence append | **13–16 ms** | **flat** (15.3 → 16.0 ms) |
| Compact frame build | **3.7 ms** | flat 3.6–3.9 ms |
| Compact JSON | **5.4 ms** | flat |
| Compact payload | **341 KB** | stable |
| FULL frame build | **23 ms** | flat ~24 ms |
| FULL JSON | **22 ms** | flat |
| FULL payload | **1.42 MB** | stable |
| `/api/diagnostics/signal-sensorimotor` (NORMAL/FULL, panel mounted) | **65 ms / call** | per 1 Hz poll |

**Observer capture is bounded with biography** through 5 000 ticks. RSS high-water rose 146→212 MB (allocator + evidence files), not unbounded frame queues.

A **live user experiment was running** on port **8771** (`temporal_opt_web_val_18795`, seed 676, tick **~1 050 680**, RUNNING **HEADLESS**, `FULL_SCIENTIFIC`, ~39 t/s, `observer_fps=0`). This audit used read-only health/progress/header only. No play/pause/stop. No SPA attach (that would add WS + aux polls).

**Largest remaining Observer-owned costs (not science):**

1. Compact WS frames still **~340 KB** (world grids + duplicated `agents_views` / `physical`).
2. **Signal→PSC panel** reconstructs analysis-only composite PSC **shadow** (~65 ms) every second if the inspector float is open.
3. **Giant `App.tsx`** (77 `useState`, **zero** `React.memo`) rerenders the map and dock on every frame **and** every 500 ms `setNow`.
4. `refreshAux` re-fetches **mechanisms catalog (~43 KB, COLD)** and **events (~108 KB)** at 0.5–0.67 Hz while RUNNING.
5. COLD blobs (`experiment` ~15 KB) ride the HOT compact frame.

UI/architecture: the world is already a workspace, but **controls that belong to RUN vs INSPECT vs ANALYZE share one wrapping top bar and one always-visible dock**. SAVE_FAILED is computed then **`void saveBanner`** — failure UX is a generic REJECTED receipt.

---

## 2. Current architecture

```
SIMULATION (PhysicalSystemRuntime.step)
    ↓ T0 evidence append (scientific_history / SEARCH_COMPACT / V3)
ObserverSession._loop  [step_lock]
    ↓ optional latest-wins capture request (not HEADLESS)
capture worker  [step_lock for live_frame; GEO overlay outside lock]
    ↓ json.dumps  →  _published + hub.offer_text (latest-wins)
WebSocket /ws/live  {type: frame|heartbeat|ping}
    ↓ App.tsx connectLive → projectLive / applyProjectionToFrame
React App state (liveFrame)
    ↓ WorldMap canvas + current ControlDevice tool + open floats
visible panels
```

**Entry points**

| Layer | Path |
|---|---|
| SPA | `web/psy-observer/src/main.tsx` → `App.tsx` |
| Built assets | `mechanistic_mind/ui/psy_observer_web/web_dist/` |
| HTTP/WS | `mechanistic_mind/ui/psy_observer_web/server.py` |
| Session | `session.py` (`_loop`, `_capture_worker_loop`, `_capture_locked`) |
| Frames | `serialize.live_frame` / `world_frame` / `agents_views_frame` |
| Interest | `subscriptions.py` MINIMAL / NORMAL / FULL |
| Analyzer | `GET /api/analysis/evidence` + `web/psy-observer/src/analysis/*` |

**Global vs local state:** almost all live state is **global in `App`**. Child panels hold only poll results (diagnostics) or local form state (PSC motor mode, observer detail menu).

---

## 3. Runtime → Observer → WEB data flow

### A. What WEB Observer does every **simulation tick**

On the SIM thread (`ObserverSession._loop`):

1. Cooperative yield if capture wants `_step_lock`.
2. `_scientific_step_once_unlocked()` — experimenter pre/post + `runtime.step(1)` + deferred LIVE mechanism apply.
3. Under `_lock`: event accumulate, motion record, **scientific append** (T0 — not gated by Observer interest).
4. If execution_mode ≠ HEADLESS and capture period elapsed (`observer_capture_period(speed, ui_hz)`): `_request_observer_capture(detail="compact")` while RUNNING.
5. Optional `tick_sleep_seconds(speed)`.

**Not every tick:** compact `live_frame`, JSON, WS push, React render, Analyzer, mechanism HTTP.

HEADLESS (live 8771): steps 1–3+5 only. Capture **off**.

### B. What it does every **browser poll / frame**

| Loop | Period | Work |
|---|---|---|
| WS frame | ≤ `ui_hz` (10/5/2/0) | parse JSON → `setLiveFrame` → full App render → WorldMap paint |
| WS heartbeat | during long ticks | `setSimHeartbeat`, STALE vs COMPUTING_TICK |
| `setNow` | **500 ms** | full App render for stale clock |
| `refreshAux` RUNNING | **1500–2000 ms** | timeline, events, mechanisms, snapshot/meta; **skips packs + gearbox** |
| `refreshAux` PAUSED | 350 ms debounce on tick | same + packs/gearbox |
| Diagnostic panels | **1000 ms if mounted** | SMC / HSS cheap; **Signal→PSC expensive** |
| ObserverDetailControl | mount | GET `/api/observer/detail` |

### C. Science vs presentation

| Tier | Examples | Gated by UI? |
|---|---|---|
| T0 science | `runtime.step`, receipts, JSONL evidence | **Never** |
| T1 world view | `world_frame` scalars | capture / HEADLESS |
| T2 telemetry | header TPS, mechanism summary | capture |
| T3 cognition panels | FULL mind / causal_chain / prospection | RUNNING compact avoids public view; interest can stub cognition |
| T4 diagnostics | signal panel shadow, gearbox, packs | HTTP; Analyzer on button |

### D–G. UI → backend, expense, rerenders, repeat payloads

See `endpoint_inventory.json`, `network_summary.json`. Highlights:

- **One tick does not fan out to N equivalent `live_frame`s** on RUNNING (single capture worker, latest-wins).
- **One WS frame does fan out to the entire React tree** (no memo).
- **Unchanged COLD data** (`/api/mechanisms` catalog, `experiment` in every frame) is still transmitted.
- **Diagnostic HTTP is independent** of the capture worker: opening Sensor Inspector can add **~65 ms/s** backend without changing ticks.

---

## 4. Performance measurements

Isolated process, `nice -n 19`. Full tables: `performance_summary.json`, `profiles/checkpoint_*.json`.

**Young (~t270):**

- SIM session: 12.9 ms (77 t/s) vs bare 4.7 ms (211 t/s) — **~8 ms session wrapper + evidence**, not Observer JSON.
- Compact Observer extra (build+JSON): **~9.0 ms** when a capture actually runs.
- FULL extra: **~44 ms** build+JSON (inspect-grade).

**Observer detail presets (live_frame only):**

| Preset | include_cognition | p50 ms | bytes |
|---|---|---:|---:|
| MINIMAL | false | 3.39 | 320 KB |
| NORMAL | true (compact mind) | 3.67 | 337 KB |
| FULL | true + full panels | 24.0 | 1.42 MB |

MINIMAL vs NORMAL is **almost free** on compact path. FULL is inspect-grade.

**Interest does not change scientific tick** (15.4–16.0 ms either MINIMAL or FULL preset).

---

## 5. Long-run scaling findings

Checkpoints:

| t | sci p50 ms | compact build | compact bytes | full build | full bytes | RSS MB |
|---:|---:|---:|---:|---:|---:|---:|
| 500 | 15.3 | 3.7 | 344 KB | 23.2 | 1.42 MB | 146 |
| 1000 | 15.8 | 4.0 | 334 KB | 24.1 | 1.42 MB | 159 |
| 2500 | 15.4 | 3.6 | 341 KB | 23.6 | 1.39 MB | 194 |
| 5000 | 16.0 | 3.9 | 341 KB | 23.9 | 1.42 MB | 212 |

- Frame buffer / timeline lengths stay small (bounded deques).
- Compact/FULL byte sizes **do not grow with tick**.
- **No Observer aging** in capture cost through 5 000.
- t10 000 **not run** here to avoid stealing CPU from the live 1.05M-tick 8771 job.
- Live 8771 itself is HEADLESS at **~39 t/s at t>1e6** — consistent with “Observer is not the long-run wall” for that mode; remaining cost is **science + FULL_SCIENTIFIC I/O**, not WS.

Frontend LIVE arrays are capped (`liveBounds.ts`: trajectory 2000, events 500, timeline 400). Scientific JSONL is **intentionally unbounded** (Analyzer, not LIVE state).

---

## 6. Browser / render findings

**BROWSER_COST_MEASURED = PARTIAL** (code + architecture; no Chromium session against 8771).

- **No `React.memo` / `useMemo` barriers** around WorldMap or ControlDevice.
- `App.tsx` holds **77 `useState` hooks**. Any `setLiveFrame` or `setNow` rebuilds:
  - map
  - entire current device body
  - HUD
  - **open** floating window bodies (they close-unmount — good)
- WorldMap (`WorldMap.tsx`): 2D canvas. PHYSICAL/CELL paths **fill every cell every paint**. TRAVERSABILITY/DEFLECTION use an offscreen **heat cache** and blit when only bodies move (OBS-05). Trajectory is a sliced array (`slice(-trajectoryLength)`).
- Cost scales with **world side** (grids, max_side 64) and **overlay count**, not biography length.
- Inactive device tools are **not mounted** (`deviceBody()` switch) — good.
- Hidden diagnostic panels: **unmounted floats stop 1 Hz polls** — verified by effect cleanup. Collapsed dock **still rerenders** with App.
- `setNow` every 500 ms means **map repaints twice per second even if WS is silent** (HEADLESS live attach would still tax the browser).

---

## 7. Network findings

Compact HOT payload (~341 KB) is dominated by:

| Field | compact | full | class |
|---|---:|---:|---|
| `world` | 133 KB | 367 KB | HOT (grids every capture) |
| `agents_views` | 86 KB | 472 KB | HOT; duplicates mind/body/physical |
| `physical` (top-level) | 53 KB | 53 KB | HOT duplicate of selected view |
| `body` | 23 KB | 23 KB | WARM/HOT |
| `experiment` | 15 KB | 15 KB | **COLD on HOT path** |
| `causal_chain` | 3.6 KB | **275 KB** | FULL-only explosion |
| `mind` | 2.1 KB | **116 KB** | FULL |
| `model_banner` | 0.8 KB | 45 KB | COLD; FULL dumps mechanisms |

Theoretical compact WS:

- LIVE 10 Hz → **~3.3 MB/s**
- FAST 5 Hz → **~1.7 MB/s**
- MAX 2 Hz → **~0.67 MB/s**
- HEADLESS → **0**

Aux while RUNNING (plus WS): mechanisms 43 KB + events 108 KB + timeline 21 KB every 1.5–2 s.

---

## 8. State-management findings

See `state_dependency_map.json`.

- **Fan-out:** one snapshot → many UI surfaces, but **one React state object**, so one update invalidates everything.
- Latest-wins exists **below** React (capture queue, WS hub, `shouldAcceptLiveFrame` for agent selection).
- Races: overlapping `refreshAux`; control HTTP returns a **deepcopy** of the full frame (`_with_receipt`) on play/pause/step.
- `analysisStateRef` is **not** fed on every aux tick (good; Analyzer is button-triggered).
- `void saveBanner` drops dedicated SAVE_FAILED chrome; `saveBanner` state still updates but is never shown.
- Stale last-known **map frame** in HEADLESS: last published compact/full frame can sit on the client while sim is at t+10⁵ with `observer_fps=0` — header `sim_tick` vs `frame_tick` / `observer_lag_ticks` exist on `current_frame()` but HUD emphasis is weak.

---

## 9. Panel inventory

Full list: `panel_inventory.json`. Classification:

**PRIMARY:** world canvas, transport (Play/Pause/Step/Stop), EXEC mode, agent HUD, Observe V2, experimenter when in-world.

**SECONDARY:** Sensors, Signals, overlays/inspector floats, Observer detail, vision bars.

**EXPERIMENT CONFIGURATION:** Set World / Ecology / Model / Experimental / EVID mode / seed/map.

**SCIENTIFIC INSPECTION:** Analyze, evidence package, Signal Forensics, Visual Forensics, gearbox/packs (paused).

**DIAGNOSTIC / DEVELOPER:** Raw float, legacy Mind/Data, mechanism integrity preflight, observer_perf HUD line, PSC shadow.

**Duplication:** mechanisms toggled in Experimental, Predictive/PSC, Mechanisms float, Sensors (vision), Observe overlays. Vision appears in HUD + Sensors + NearField float. Action/motor numbers appear in inspector cards, Observe, and causal chain.

---

## 10. Screen-layout findings

From `styles/app.css` (screenshots skipped — see `screenshots/README.md`).

| Viewport | Expected behavior |
|---|---|
| 1920×1080 | Dock `clamp(300px, 28vw, 380px)` ≈ 380px; map ~1500px. Top bar likely **one wrap**. |
| 1600×900 | Dock ~380px; map tighter; header wrap likely. |
| 1366×768 | Dock 300–380px is **22–28% width**; top bar **wraps to 2–3 rows**; nested scroll in device-screen. |
| MacBook-class 1440×900 | Same class as 1600; map is large if dock collapsed (64px). |

Issues (structural, not aesthetic):

- **Fixed chrome:** `desktop-top` (wrap) + `sim-hud` (~28px) + optional receipt banners steal vertical space before the map.
- Map is correctly `position:absolute; inset:0` in `.sim-map-host` — world **is** the workspace when the dock is collapsed.
- Expanded dock **fights the map** at 1366.
- Nested scroll: device-screen, float windows, Observe V2, Analyze.
- Fullscreen world (`world-layout.map-only.fullscreen`) covers the map host, **not** the top bar — transport stays, which is correct for RUN, but the wrapping header still shrinks the map.
- Tiny hit targets: header buttons use 5×8 padding at 11px font.

---

## 11. Control hierarchy findings

**Top bar currently mixes:**

| Concept | Controls |
|---|---|
| Simulation state | status badge, tN, Play/Pause/Step/Stop/Reset |
| View mode | LIVE button (inspect vs live — **same word as EXEC LIVE**) |
| Execution performance | EXEC LIVE/FAST/MAX/HEADLESS, speed `<select>`, SIM t/s, OBS Hz |
| Evidence detail | EVID FULL / COMPACT |
| Observer detail | MINIMAL / NORMAL / FULL |
| Capture diagnostics | observer_perf bytes/ms |
| Config pending | PENDING CONFIG, OV count |

**Visible user state machine**

```
CONNECTING → CONNECTED
                ├ RUNNING (+ optional COMPUTING_TICK / PENDING TICK BOUNDARY)
                ├ PAUSED
                ├ STALE (RUNNING + no frame/heartbeat)
                ├ DISCONNECTED
                └ STOPPED
FINALIZING shown as banner text ("Finalizing run…") while stop in flight
SAVE_FAILED: session status exists; UI mainly "STOP: REJECTED"
STOP_REJECTED: not named; control_receipt.accepted=false
```

Play/Pause/Step/Reset stay **enabled** while DISCONNECTED until `finalizing` — clicks will throw and may set a REJECTED receipt. Stop is not extra-protected.

LIVE (view) vs LIVE (execution) is the worst naming collision.

---

## 12. Visualization findings

- **Tech:** HTML canvas 2D, DPR capped at 2.
- **Redraw:** entire backing store cleared (`fillRect`) each effect; scalar grids iterated unless geo heat cache hits.
- **Overlays:** body, sites, trajectory, velocity, orientation, deformation, occupancy, force, terrain_*, ambient_*, vision FOV (Sensors tool only), experimenter target, empirical traversability.
- **Independently togglable without science:** all `layers` checkboxes, renderMode, trajectory length, worldView, Observer interest products, HEADLESS capture.
- **Must not be confused with science:** empirical GEO, FOV overlay, PSC shadow, derived L/R asymmetry in Signal panel.
- Scaling: **O(W×H)** paint + JSON; agent count adds HUD chips and `agents_views` size; trajectory cap 2000 points.

---

## 13. Error / lifecycle UX findings

**Do not fix in this task** — documentation only.

| Failure | Origin | Frontend | Persistence | Distinguishability |
|---|---|---|---|---|
| SAVE_FAILED | `session.stop` / `run_finalize` integrity | `setSaveBanner({failed})` then **`void saveBanner`** — user sees generic `STOP: REJECTED` | until next receipt | Weak vs other rejections |
| STOP_REJECTED | `accepted=false` (finalizing, integrity, etc.) | control_receipt.bad | until next control | Not named |
| Analyzer unavailable | evidence GET error | `analysisCopyMsg` + live-frame fallback | until cleared | Medium |
| Evidence empty | no scientific_rows | Visual Forensics NOT_AVAILABLE | — | Honest |
| DISCONNECTED | WS onclose | displayStatus DISCONNECTED; auto-reconnect 1.2s | while down | Good |
| Request timeout | fetch throw | some paths swallow to `{}` | silent | Weak |
| Mechanism deferred | step_lock busy | PENDING — WAITING FOR TICK BOUNDARY | until apply | Good (recent) |
| COMPUTING_TICK vs STALE | heartbeat | distinguished | — | Good |
| Invalid mechanism | POST rejected | receipt | — | OK |
| Runtime exception | WS/HTTP | often ignored in poll `.catch` | last frame looks live | **Risky in HEADLESS** |

STOP / RESET have no extra confirm except Stop’s two-step discard. Reset is one click.

---

## 14. Proposed Beta 3 information architecture

Suggested primary modes (fits existing tools better than a greenfield):

```
RUN      — world workspace + transport + EXEC + experimenter
INSPECT  — pause-friendly cognition / signals / mechanisms / body
ANALYZE  — evidence, Analyzer, forensics, runs
```

Experiment configuration is a **fourth rail** (infrequent, destructive) — keep as a dock app, not in the RUN header.

| Item | CURRENT | PROPOSED | WHY |
|---|---|---|---|
| Top bar | SIM+EXEC+EVID+OBS mixed | RUN: transport + status + EXEC only | Stop mixing evidence/observer with play |
| LIVE button | next to Play | Rename view mode to **FOLLOW** / **INSPECT TICK** | Disambiguate EXEC LIVE |
| EVID | header | Experiment → Evidence policy | Changes notebook, not watching |
| Observer MINIMAL/NORMAL/FULL | header | INSPECT chrome or Observe tool | Display interest, not sim speed |
| World | already workspace | Keep; default dock collapsed while RUNNING | Map is the instrument |
| Predictive / PSC toggles | Experiment submenu | INSPECT → Mechanisms / Predictive | Used while watching, buried in setup |
| Mechanism ON/OFF | 4 places | One Mechanisms inspector + compact RUN chips for active experimental flags | Duplication |
| Sensors | own tool + HUD bars | HUD bars stay; full vision in INSPECT | HUD is enough while RUNNING |
| Signal→PSC / SMC / HSS | float over map | INSPECT tab; **do not mount while RUN** | 65 ms shadow |
| Analyzer | tool + float | ANALYZE mode only; keep RUNNING banner | Isolation already started |
| Experimenter | Intervention tool | RUN overlay when spawned; hide when OUT | Contextual |
| Diagnostics / Raw / observer_perf | header/HUD | ANALYZE or overflow “Diagnostics” | Developer |
| Errors | generic receipt | Persistent **lifecycle chip**: RUNNING / PAUSED / FINALIZING / SAVE_FAILED / DISCONNECTED | Failure UX |
| SAVE_FAILED banner | voided | Restore dedicated banner (UI plan, not this audit’s fix) | Users cannot see integrity mismatch |

This is **not** a mandate to delete panels. Re-home and **unmount** what RUN does not need.

---

## 15. Performance priority backlog

### P0 — pathological / scaling / correctness (Observer-owned)

1. **Signal→PSC HTTP shadow replay (~65 ms/call)**  
   - Evidence: `endpoint_microbench` p50 **65.48 ms**; three panels together **67.4 ms**.  
   - Root: `session.signal_sensorimotor_panel` → `full_composite_psc_shadow.replay_tick` whenever interest ≠ MINIMAL.  
   - Files: `session.py` (~3314+), `SignalSensorimotorPanel.tsx` (1 Hz).  
   - Benefit: UNKNOWN as % of a LIVE session (0 if panel closed; **~65 ms/s** if open).  
   - Scientific risk: **none** if shadow stays analysis-only; do not feed shadow into action selection.  
   - UI risk: shadow banners appear less often unless on-demand.  
   - Fix (later): compute on PAUSED / ANALYZE / FULL only; never 1 Hz RUNNING.  
   - Validate: same microbench < 2 ms RUNNING; EXACT_MATCH actions.

2. **COLD catalog on HOT aux path**  
   - Evidence: `/api/mechanisms` **43 KB / 0.09 ms** every 1.5–2 s RUNNING.  
   - Root: `refreshAux` always GET mechanisms.  
   - Files: `App.tsx` `refreshAux`; `server.py` `get_mechanisms` includes **catalog**.  
   - Benefit: UNKNOWN bytes; small CPU; less parse/rerender.  
   - Risk: stale toggle UI if events missed — need invalidation on mechanism POST.  
   - Validate: toggle still updates via frame `mechanism_result`.

### P1 — major recurring cost

3. **Compact frame ~340 KB / ~9 ms serialize+build**  
   - Dominant: `world` 133 KB + duplicated `agents_views`/`physical`/`body`.  
   - Files: `serialize.py` `live_frame`, `world_frame`.  
   - Benefit: UNKNOWN until protocol split (hot/warm/cold).  
   - Risk: if grids dropped, map lies — keep T/flow/FIELD; stop duplicating selected agent three times.  
   - Validate: pixel-compare map; compact still no `cognition_public_view`.

4. **App monolith rerender (500 ms timer + every WS frame)**  
   - Evidence: 77 useState, 0 memo; `setNow` interval.  
   - Files: `App.tsx`, `WorldMap.tsx`.  
   - Benefit: UNKNOWN ms (not measured in Chromium).  
   - Risk: split components without changing projection identity rules.  
   - Validate: projection tests; render counts via profiler.

5. **FULL inspect JSON ~22 ms + 1.42 MB**  
   - Acceptable for PAUSE; must **never** stream on RUNNING (already policy).  
   - Risk: STEP with FULL preset still captures full (`session.step` uses FULL if preset FULL).  
   - Validate: `test_observer_public_view_dedupe.py` still 0 compact builds.

### P2

6. `experiment` 15 KB COLD in every compact frame.  
7. `refreshAux` events 108 KB vs frame `structured_events` overlap.  
8. `_with_receipt` deepcopy of full frame on every control.  
9. `setNow` 2 Hz without isolating status chip.  
10. Physical mode per-cell canvas vs cached tiles.

### P3

11. observer_perf HUD clutter.  
12. Ping WS every 30s.  
13. Duplicate VisionBars markup.

**Not Observer P0:** age-dependent predictive scans (already optimized elsewhere); live 8771 HEADLESS 39 t/s at t=1e6.

---

## 16. UI priority backlog

### P0

1. **Disambiguate LIVE** (view) vs **LIVE** (execution).  
2. **Surface SAVE_FAILED / STOP_REJECTED** as named, sticky lifecycle — `saveBanner` is computed and discarded (`void saveBanner`).  
3. **Do not leave Play/Reset armed** when `DISCONNECTED` / `FINALIZING` without explanation.

### P1

4. Split top bar: transport+status | EXEC | overflow for EVID/OBS.  
5. Collapse dock by default while RUNNING; world is the workspace.  
6. Move Predictive/PSC + mechanism toggles to a single INSPECT inspector.  
7. Keep Analyzer out of RUN (already partly done).  
8. Unmount Sensor Inspector diagnostic polls while RUN.

### P2

9. Contextual experimenter chrome only when IN WORLD.  
10. Reduce duplicate vision/mechanism controls.  
11. Larger Stop/Reset hit targets; Reset confirm.  
12. Status not color-only (already text badges — keep).

### P3

13. Legacy Mind/Data behind an explicit Debug flag.  
14. Typography/contrast pass.  
15. Keyboard: Stop/Reset not adjacent to Step without confirm.

Keep UI plan **separate** from payload/render engineering.

---

## 17. Risks

- Optimizing compact JSON by dropping grids **falsifies** the world view.
- Gating T0 evidence on Observer interest **breaks** Analyzer later.
- Shadow PSC must remain **analysis-only**.
- Changing `refreshAux` mechanisms fetch can desync ON/OFF buttons.
- Attaching a browser to a HEADLESS million-tick run **is** a disturbance (aux + WS).
- CPU autopsy on the same machine as 8771 was run `nice -n 19`; t10k skipped.

Scientific constraint observed: this audit did not weaken cognition, receipts, PSC semantics, or mechanisms.

---

## 18. Recommended implementation sequence

1. **Lifecycle UX** (SAVE_FAILED visible; named STOP_REJECTED; disconnect disables destructive controls) — no science.  
2. **Unmount / defer Signal→PSC shadow** while RUNNING — largest measured Observer-owned spike.  
3. **Header IA split** (transport vs EXEC vs EVID/OBS) — unlocks Beta 3 modes without touching ticks.  
4. **Hot/warm/cold frame protocol** (stop duplicating physical/agents_views; cache experiment).  
5. **React split** (WorldMap memo; status clock isolated) — after protocol, so profilers see paint not parse.  
6. **Mechanisms/PSC single inspector** — after header split.  
7. **Analyzer as ANALYZE mode** — already isolated; finish navigation.

---

## Answers to primary questions

**A.** Every sim tick: scientific step + evidence append; optionally one latest-wins compact capture request.  
**B.** Browser: WS parse+setState at ui_hz; 2 Hz now-timer; 0.5 Hz aux REST; 1 Hz diagnostic HTTP **only if those panels are mounted**.  
**C.** T0 science required; compact world useful for RUN; FULL mind/causal/prospection/shadow are presentation.  
**D.** Aux polls, diagnostic panels, control POSTs, Analyzer buttons, mechanism toggles, experimenter keys.  
**E.** FULL `live_frame` (~23+22 ms, 1.42 MB); Signal→PSC shadow (~65 ms); compact world JSON (~5 ms, 341 KB). `cognition_public_view` compact = 0 by design.  
**F.** Entire `App` including WorldMap on every frame and every 500 ms.  
**G.** World grids, duplicated physical, experiment blob, mechanisms catalog, events list.  
**H.** Mechanisms, vision, motor/action, signals.  
**I.** Predictive/PSC under Experiment; EVID vs OBSERVER both “FULL/COMPACT”; two LIVEs.  
**J.** Expanded dock vs map; floats vs canvas; Analyze vs live world.  
**K.** SAVE_FAILED hidden; HEADLESS last frame vs live tick; FINALIZING vs RUNNING; DISCONNECTED still clickable.  
**L.** RUN / INSPECT / ANALYZE (+ Experiment as setup), world as workspace, inspectors unmounted in RUN.

---

## FINAL VERDICT

```
OBSERVER_ARCHITECTURE_MAPPED = YES
LIVE_COST_MEASURED = YES          # isolated session; live 8771 read-only only
BROWSER_COST_MEASURED = PARTIAL   # no Chromium against 8771 (protect live experiment)
NETWORK_COST_MEASURED = YES       # payload bytes + theoretical Hz; not pcaps on 8771
LONG_RUN_SCALING_MEASURED = YES   # t500–t5000 isolated; t10000 skipped (CPU vs 8771)
HIDDEN_PANEL_COST_AUDITED = YES   # unmount=0 polls; Signal panel 65ms if mounted
STATE_DEPENDENCIES_MAPPED = YES
ERROR_UX_AUDITED = YES
BETA3_INFORMATION_ARCHITECTURE_PROPOSED = YES
IMPLEMENTATION_PERFORMED = NO
```

### TOP 5 PERFORMANCE PROBLEMS

1. Compact live payload still ~340 KB (world + duplicated agent blobs) every capture.  
2. Signal→PSC inspector **shadow replay ~65 ms** at 1 Hz if mounted (NORMAL/FULL).  
3. Session scientific wrapper ~8 ms over bare step (not Observer JSON; still wall time).  
4. Giant App rerender + 2 Hz `setNow` + unmemoized canvas.  
5. COLD mechanisms/events re-fetched on RUNNING aux.

### TOP 5 UI/UX PROBLEMS

1. Header mixes SIM, EXEC, EVID, OBSERVER; two different “LIVE”s.  
2. SAVE_FAILED / STOP_REJECTED not first-class in the UI (`void saveBanner`).  
3. Predictive/PSC and mechanisms scattered vs how they are used live.  
4. Expanded control dock competes with the world at laptop widths.  
5. HEADLESS/lag: last painted world can be mistaken for the live tick.

### TOP 5 ARCHITECTURAL PROBLEMS

1. `App.tsx` monolith is the state bus.  
2. HOT WS message still carries COLD config and duplicated views.  
3. Demand-driven **interest** is only partially bound to **mounted** panels (preset FULL enables shadow even for a single float).  
4. Control receipts deepcopy full frames.  
5. Analyzer / forensics / RUN share one SPA without a hard mode boundary (policy exists, navigation does not).

### RECOMMENDED UPDATE ORDER

Lifecycle UX visibility → defer shadow diagnostics on RUN → split header/modes → hot/cold protocol → React render isolation → consolidate mechanism/PSC inspector → ANALYZE mode finish.

**IMPLEMENTATION_PERFORMED = NO**
