# Observer UI — 4.26–4.28 Context / Prospection / Persistent Prospective Control

**Date:** 2026-09-21  
**Verdict:** `OBSERVER_426_428_UI_ACCEPTED`

## Files changed

| Area | Path |
|---|---|
| Registry | `mechanistic_mind/physical_system/mechanism_registry.py` |
| Hot-toggle sync | `mechanistic_mind/physical_system/runtime.py` |
| Compact LIVE + FULL mind | `mechanistic_mind/ui/psy_observer_web/serialize.py` |
| Promotion | `mechanistic_mind/model/identity.py`, `tiktaalik.py` |
| Panel | `web/psy-observer/src/components/ContextualProspectiveControlPanel.tsx` |
| Controls + mount | `web/psy-observer/src/App.tsx` |
| Tests | `tests/test_observer_426_428_ui.py` |
| Build | `mechanistic_mind/ui/psy_observer_web/web_dist/` |

## Backend / public-summary fields

### LIVE compact (`mind.contextual_stack`)

Built in `mind_compact_frame` **without** `cognitive_view` / `cognition_public_view`:

- `context` ← `cpo.observer_compact`
- `prospection` ← `cgp.observer_compact`
- `persistent_control` ← `ppc.observer_compact`
- `flags`, `psc_mode`, `last_event`, `last_reactivation`, `last_active_context`, `selection_source`

### FULL

`mind_frame` exposes public-view sections:

- `contextual_predictive_organization`
- `context_grounded_prospection`
- `persistent_prospective_control`
- plus `contextual_stack` derived from their `observer_compact` snapshots

## Control wiring

MM Control → **Predictive / PSC** (`set_predictive`):

- Contextual Predictive Organization (4.26)
- Context-Grounded Prospection (4.27)
- Persistent Prospective Control (4.28)

Toggles call existing `POST /api/mechanisms/{id}` → registry `set_mechanism` → cognition flags.

Dependency hints (Observer-only, no silent auto-enable):

- 4.27 requires `contextual_predictive_organization`, `prospective_composition`
- 4.28 requires `context_grounded_prospection`, `prospective_scenario_competition`

## Panel layout

**CONTEXT → PROSPECTION → CONTROL**

Pipeline stages: CONTEXT → PROSPECTION → PSC → PERSIST → MOTOR

- Persistence age: `ACTIVE FOR N TICKS` when same structure remains active
- Interruption: `INTERRUPTED · predictive mismatch`
- Bounded event strip (cap 24)
- `Observer interpretation` (explanatory only; may say intention-like)
- FULL block: path_ids, actions, novel composition, motor chunk count

World overlay skipped (would need major architecture; documented as optional future).

## LIVE vs FULL

| Mode | Behavior |
|---|---|
| RUNNING / compact | `contextual_stack` only; 0 `cognitive_view` builds |
| PAUSE / STEP / FULL | Full sections + stack; may build public view once/agent |

## Performance validation

`tests/test_observer_426_428_ui.py::test_compact_live_includes_stack_without_cognitive_view_builds` — **PASS** (builds == 0).

Aligned with `docs/OBSERVER_PERFORMANCE_OPTIMIZATION.md`.

## Scientific terminology boundary

| UI label | Cognition |
|---|---|
| Contextual Predictive Organization | flag + higher-order structures |
| Context-Grounded Prospection | flag + context transitions |
| Persistent Prospective Control | flag + support-gated active continuation |
| Intention-like control | **Observer interpretation only** |

No PLACE / MAP / GOAL / DESTINATION / PLAN / INTENTION variables.

## Acceptance checklist

- [x] All three mechanisms controllable via backend flags
- [x] Active context / prospection / persist / motor visible
- [x] Persistence across ticks shown as age, not reselection spam
- [x] Interruption visible
- [x] No semantic leakage into cognition
- [x] LIVE compact architecture preserved
- [x] Bounded frontend history (24)
- [x] Production web_dist rebuilt
- [x] Registry/UI tests pass; science modules unchanged in semantics

## Verdict

`OBSERVER_426_428_UI_ACCEPTED`
