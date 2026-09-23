# Observer WEB Beta 3 — Field Validation × Release Freeze Gate

**Date:** 2026-09-22  
**Ports:** isolated **8799** (aged TwoAgent 12k), **8801** / **8802** (lifecycle). **8771 never attached.**  
**GIT_PUSH = NO**

## Freeze

**OBSERVER BETA 3 FEATURE / ARCHITECTURE FREEZE**

`OBSERVER_BETA3_FREEZE_READY = YES`

After this point only release blockers should modify Observer before MM 1.0 Tiktaalik Public Beta 3.

---

## 1. Validation environment

| Item | Value |
|---|---|
| Node | v24.18.0 |
| npm | 11.16.0 |
| Python | 3.12.3 `.venv_psy_web` |
| OS | Linux 7.0.0-31-generic (Ubuntu) |
| Browser | Chromium via cursor-ide-browser / Chrome 153.0.8010.47 |
| Build | `cd web/psy-observer && npm run build` (~6.5s, then ~0.25s vite) |
| Final dist | `web_dist/assets/index-DFnC0cHC.js` (634 kB) |
| Warnings | npm `devdir`; vite chunk >500 kB |
| Errors | none |

Phase 0 rebuilt dist from current source (hash matched Update 2, then two field-blocker rebuilds).

## 2. Isolated experiment configuration

**8799** `PSY_OBSERVER_INSTANCE_ID=beta3_field_val_8799`

- Seed **20260922**, **TwoAgentRuntime**, 32×32 WRAP_PERIODIC  
- `BASELINE_CLIMATE_DEFAULT`, cognition ON  
- Evidence **SEARCH_COMPACT**, aging **MAX**, target 12000  
- Tiktaalik + experimental overrides already in identity: CPO, CGP, PPC, experimental physical signal  
- Did **not** extra-enable experimental systems solely for load  

Reached **t12000** (~23–25 sim ticks/s). Auto-paused at target. 8771 remained `temporal_opt_web_val_18795`.

## 3. Browser validation

Real Chromium against **http://127.0.0.1:8799/** and **8801** only. Console/fetch hooks: no uncaught exceptions, no React warnings during walkthroughs.

`REAL_BROWSER_VALIDATION = PASS`

## 4. RUN

World canvas filled the map host; HUD agents + experimenter NOT IN WORLD; header tick/RUNNING/MAX truthful; dock default collapsed; Signal/PSC/Analyzer not mounted; no `include_shadow` traffic.

`RUN_FIELD_VALIDATION = PASS`

## 5. INSPECT

Three full cycles RUN → BODY → SENSORS → SIGNALS → COGNITION → PREDICTIVE → MECHANISMS → EXPERIMENTER → RUN. Dock unmounts on RUN; last inspector restored; body x,y/action update; sensors vision copy non-semantic; no INTENTION/GOAL/PLAN/BELIEF ontology labels.

`INSPECT_FIELD_VALIDATION = PASS`

## 6. SIGNAL / PSC shadow

Default checkbox **off**. Idle SIGNALS polls `signal-sensorimotor` without shadow. Enable → `?include_shadow=true` 200. Disable → requests lose the query. Leave SIGNALS → **no** signal-sensorimotor.

`PSC_SHADOW_INTEREST_LIFECYCLE = PASS`

## 7. PREDICTIVE

CONTEXT → PROSPECTION → CONTROL, current CX, persist/motor, bounded events, “Intention-like remains Observer interpretation — not a cognition variable.” PSC shadow opt-in, not implied runtime ontology.

`PREDICTIVE_INSPECTOR = PASS`

## 8. MECHANISMS

Authoritative inspector only. **illumination_cycle** OFF then ON (recorded). First pass: stale `!m.enabled` + WAITING receipt (HIGH). Fixed (F1/F2). Retest at PAUSED t12000: UI ON→OFF→ON matched `/api/mechanisms/state`.

`MECHANISM_EDITOR = PASS`

## 9. EXPERIMENTER

Spawn CONTROLLED TIKTAALIK → `CONTROL_ACTIVE` / UNDERCOVER / IN WORLD. Copy: external intervention, not cognition; signals physical coupling. body-2 visually distinct. MOVE:E enabled after spawn. Re-enter inspector: no stuck handlers. Remove not required for freeze.

`EXPERIMENTER_UI = PASS`

## 10. ANALYZE

No HOT canvas. Copy: historical, does not follow every tick. 2s idle: no diagnostic flood. Context survived RUN→ANALYZE. SEARCH_COMPACT overview waits until Analyze; Visual Forensics empty until package — MEDIUM usability, not blocker.

`ANALYZE_FIELD_VALIDATION = PASS`

## 11. Workspace stress

56 transitions in 2.4s, no console errors, ANALYZE stays canvas-free.

`WORKSPACE_STRESS = PASS`

## 12. Execution-mode transitions

REALTIME / FAST / MAX / HEADLESS buttons; 8801 MAX→HEADLESS→LIVE. Header uses REALTIME not ambiguous LIVE. Bogus mode → `INVALID_TRANSITION`.

`EXECUTION_MODE_TRANSITIONS = PASS`

## 13. HEADLESS

First field observation: backend `display_frozen` + `observer_fps=0` but UI lacked DISPLAY FROZEN (no capture frames). **F3:** heartbeat carries frozen fields. Retest: `DISPLAY FROZEN @ t560 · RUNTIME @ t944 · HEADLESS (no live capture)`. LIVE return: frozen false, display catches current tick, no backlog replay.

`HEADLESS_FIELD_BEHAVIOR = PASS`

## 14. Pause / step / resume

8801: pause @4813, step→4814, step→4815. PLAY after LIVE unfreeze advanced. 8799 pause/step not used (already at target).

`PAUSE_STEP_RESUME = PASS`

## 15. Save / stop

8801 `STOP save=true` → STOPPED, verified t4847, artifact `psyweb-20260922T060705.889796Z-39070ca5`. Second STOP idempotent SAVED.

`STOP_SAVE_LIFECYCLE = PASS`

## 16. Failure UX

- `INVALID_TRANSITION` reproduced (bogus execution mode).  
- `SERVER_UNAVAILABLE` reproduced by killing **8801 only**: DISCONNECTED + banner that last image is not a live tick.  
- `SAVE_FAILED`: unit test + SPA banner present; chmod field attempt on 8802 still wrote (same-uid). Not treated as freeze block.

`SAVE_FAILED_UX = PASS`  
`SERVER_UNAVAILABLE_UX = PASS`

## 17. Responsive

1920 / 1600 / 1366 / 1440: no page-level horizontal overflow; Play/Pause/Step/Stop/workspaces visible; header wraps ~75px; HEADLESS in bounding box. Screenshots under `results/observer_beta3_field_validation/screenshots/`.

`RESPONSIVE_1920x1080 = PASS`  
`RESPONSIVE_1600x900 = PASS`  
`RESPONSIVE_1366x768 = PASS`  
`RESPONSIVE_MACBOOK = PASS`

## 18–20. Memory, performance, aging

JS heap 13–43 MB across 12k ticks + stress. ANALYZE isolated. Shadow demand-gated. Aged t5k/t10k/t12k workflow unchanged.

`FRONTEND_MEMORY_LEAK = NONE_DETECTED`  
`OBSERVER_FRONTEND_AGING = NONE_DETECTED`  
`HOT_FRAME_RENDER_ISOLATION = PASS`  
`DIAGNOSTIC_INTEREST_GATING = PASS`

## 21. Usability (not redesigned)

MEDIUM: leftover COLD dock expand hides map; ANALYZE needs explicit Analyze on compact evidence. LOW: header crowding; sticky control receipt. COSMETIC: chunk size.

## 22. Release-blocker fixes

| ID | Root cause | Fix |
|---|---|---|
| F1 | Toggle used stale `!m.enabled` | Requested `enabled` + optimistic list |
| F2 | WAITING receipt never cleared | Heartbeat `pending_live_apply=null` |
| F3 | HEADLESS no frames → no frozen UI | Progress/heartbeat display fields |

No science/mechanism/feature work.

## 23. Scientific equivalence

`test_scientific_fingerprint_exact_match_live_headless` **passed**. Workspaces presentation-only.

`SCIENTIFIC_EQUIVALENCE = EXACT_MATCH`

## 24. Tests

- pytest update1+update2: **26 passed**  
- node stores+lifecycle: **13 passed**  
- `measurementIntegrity` STRUCTURED COGNITIVE EVENTS: **PRE_EXISTING** (log still says `structured cognition events: AVAILABLE`, assert wants `STRUCTURED COGNITIVE EVENTS`). Unchanged by this pass.

`NEW_TEST_FAILURES = NONE`

## 25. Freeze decision

Researcher-usable for long runs: RUN / INSPECT / ANALYZE / HEADLESS truth / pause-step / save-stop / disconnect / laptop viewports / demand-driven diagnostics / exact LIVE↔HEADLESS science.

`RELEASE_BLOCKERS = NONE`  
`OBSERVER_BETA3_FREEZE_READY = YES`  
`GIT_PUSH = NO`

---

OBSERVER BETA 3 FEATURE / ARCHITECTURE FREEZE
