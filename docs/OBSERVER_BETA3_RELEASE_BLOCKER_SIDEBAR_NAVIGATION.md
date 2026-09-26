# Observer Beta 3 — Release blocker: left rail navigation

**GIT_PUSH = NO**  
Isolated Chromium against **8799** only. Port **8771** was not attached.

## Root cause

**ROOT_CAUSE_IDENTIFIED = YES**

Class: **H** (rail still targeted leftover `deviceTool`) **+ C** (workspace stayed RUN) **+ E** (RUN forced the dock collapsed so the COLD panel never appeared).

Not pointer-events, overlay intercept, or a stale closure as the primary bug.

### Differential (Analyze vs everything else)

**Analyze (worked):**

1. `ControlDevice` `onClick` → `onTool('analyze')` + `onToggleCollapse()`
2. `App` `onTool`: `setDeviceTool('analyze')` **and** `workspaceStore.set({ workspace: 'ANALYZE' })`
3. `AnalyzeWorkspace` mounts
4. Control rail unmounted (`lab.workspace !== 'ANALYZE'`)

**Every other icon (dead on RUN):**

1. Same click path reaches the button (`pointer-events: auto`; Experiment even got `active`)
2. `onTool` only `setDeviceTool(t)`
3. `workspaceStore` unchanged (**RUN**)
4. `collapsed={lab.workspace === 'RUN' || deviceCollapsed}` stays **true**
5. COLD `deviceBody` never shown; InspectorDock never mounts

First line that differs: `if (t === 'analyze') workspaceStore.set(...)`.

Actual rail (authority): Experiment, Intervention, Observe, Sensors, Signals, Analyze Results, Runs, World Status.

## Fix (navigation only)

Single helper `applyRailDestination` / `railDestination`:

| Rail | Result |
|---|---|
| Sensors | `INSPECT` + inspector `SENSORS`, dock collapsed |
| Signals | `INSPECT` + `SIGNALS`, dock collapsed |
| Analyze Results | `ANALYZE`, dock collapsed, **rail stays visible** |
| Experiment / Intervention / Observe / Runs / World Status | leftover COLD screen, **dock expands** (RUN no longer forces collapsed) |

Header WORKSPACE buttons and rail share `workspaceStore`. Inspector tabs still use `useSetInspector`.

Production files:

- `web/psy-observer/src/observer/railNav.ts` (new)
- `web/psy-observer/src/observer/railNav.test.ts` (new)
- `web/psy-observer/src/App.tsx`
- `web/psy-observer/src/desktop/ControlDevice.tsx`
- `web/psy-observer/package.json` (test list)
- `tests/test_observer_beta3_update2_frontend.py`

No science/runtime/capture changes.

## Verification

Chromium 8799: every rail icon opens its destination. ANALYZE → Signals enters INSPECT/SIGNALS. SIGNALS polls `signal-sensorimotor`; returning to RUN stops it. 44×44 hitboxes, `pointer-events: auto`, no page overflow at 1920 and 1366.

BODY / COGNITION / PREDICTIVE / MECHANISMS / EXPERIMENTER are **InspectorDock tabs**, not left-rail icons; they work after rail (or header) enters INSPECT.

LIVE vs HEADLESS fingerprint still **EXACT_MATCH**.

---

RELEASE_BLOCKER_RESOLVED = YES
