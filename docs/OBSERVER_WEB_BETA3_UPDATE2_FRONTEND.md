# Observer WEB Beta 3 — Update 2 (frontend architecture)

Presentation/workflow only. Science unchanged. Port **8771** was not attached.

`SCIENTIFIC_EQUIVALENCE = EXACT_MATCH` (seed 19, 30 ticks, LIVE vs HEADLESS).

## 1–2. Architecture before / after

**Before:** `App.tsx` held HOT `liveFrame` + WARM heartbeat + a 500 ms `setNow` clock. Every compact frame committed the whole desktop tree (header, world, inspectors, device).

**After:** HOT frames go to `frameStore` (`useSyncExternalStore`). Slim lifecycle/tick goes to `statusStore`. Wall-clock goes to `clockStore`. Workspace is `workspaceStore`. `App` remains the session/controller for COLD config, mechanism list, and analysis *buttons* — it does **not** `useState` the world frame.

## 3–4. Decomposition and domains

New modules:

- `observer/stores.ts`, `useExternalStore.ts`, `interest.ts`, `drivers.tsx`
- `chrome/ObserverHeader.tsx`, `LifecycleBanners.tsx`, `RuntimeClock.tsx`, `WorldPane.tsx`
- `workspaces/RunWorkspace.tsx`, `InspectWorkspace.tsx`, `AnalyzeWorkspace.tsx`
- `inspectors/InspectorDock.tsx`

`APP_MONOLITH_DECOMPOSED = PARTIAL` — leftover COLD JSX and device screens still live in `App.tsx` (~70 `useState` values), but they no longer subscribe to HOT frames.

## 5. HOT-frame isolation

`frameStore` listeners ≠ `statusStore` listeners ≠ `clockStore` listeners (unit-tested). Analyze workspace is not a `useFrameStore` consumer. Closed inspector categories are not mounted.

`HOT_FRAME_INVALIDATES_UNRELATED_UI = NO`

## 6. Clock

`setNow(Date.now())` removed from `App`. `ClockDriver` writes `clockStore` at 500 ms while RUNNING. Only `RuntimeClock` displays age/STALE.

`GLOBAL_APP_RERENDER_FROM_500MS_CLOCK = NO`

## 7–9. Workspaces

- **RUN** — world + agent HUD + experimenter IN/OUT flag. Control dock collapsed. Observer interest MINIMAL. No Signal/PSC/SMC panels mounted.
- **INSPECT** — world + category dock: BODY, SENSORS, SIGNALS, COGNITION, PREDICTIVE, MECHANISMS, EXPERIMENTER. One category at a time.
- **ANALYZE** — Analyzer + overview. No live world dashboard. No HOT diagnostic polls.

Workspace selection does not change execution mode, evidence mode, or science.

## 10–12. Header, world, inspector

Header clusters: SIMULATION, ACTIONS, EXECUTION (REALTIME/FAST/MAX/HEADLESS), OBSERVER detail, EVIDENCE, WORKSPACE. Ambiguous dual-LIVE transport button removed from the primary header (LIVE view-mode remains a session concern via `modeRef`).

World is the spatial anchor of RUN and INSPECT (`sim-map-host`). Inspector is a side dock, not a stack of all panels.

## 13–15. Predictive / mechanisms / experimenter

PREDICTIVE inspector: PSC motor resolution (mode, not toggle) + Context→Prospection→Control + optional Signal→PSC (shadow still checkbox). MECHANISMS inspector is the authoritative editor (`MechanismsPanel` + preflight). Compact RUN does not duplicate the editor. EXPERIMENTER inspector: IN WORLD / NOT IN WORLD; InteractPanel; not cognition; signals are not communication.

## 16–18. Responsive, lifecycle, interest

CSS: wrap header; 1366 inspector ~320px; &lt;900 inspector below map. Stop still uses confirmation dialog; Reset confirms. SAVE_FAILED / DISPLAY FROZEN / SERVER_UNAVAILABLE / receipt codes remain in `LifecycleBanners`. InterestDriver POSTs Observer MINIMAL/NORMAL products from visible workspace/inspector only.

## 19–21. Performance, equivalence, tests

Store isolation tests pass. Python Update 1+2 + demand-driven + PSC Observer UI pass. `web_dist` rebuilt.

**PRE_EXISTING_TEST_FAILURE:** full `npm test` `measurementIntegrity` log-label (`STRUCTURED COGNITIVE EVENTS`) — not treated as Update 2 regression.

## 22. Deferred (Beta 3 polish)

- Finish extracting remaining `App.tsx` COLD screens out of the file
- Chromium commit/sec on an isolated server (not 8771)
- Preflight `rows` off compact HOT (Update 1 follow-up)
- Agent-view unification
- Visual redesign beyond restrained lab chrome

## Production files

`web/psy-observer/src/App.tsx`, `styles/app.css`, `package.json`, new `observer/*`, `chrome/*`, `workspaces/*`, `inspectors/InspectorDock.tsx`, `tests/test_observer_beta3_update2_frontend.py`, demand-driven/plumbing test path updates, `web_dist`.

`GIT_PUSH = NO`
