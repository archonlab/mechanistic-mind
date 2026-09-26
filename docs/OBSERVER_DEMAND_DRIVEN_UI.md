# Demand-driven Observer UI

## Purpose

Make live Observer instrumentation **opt-in by interest**. Closing a panel or choosing MINIMAL must stop optional backend construction for that product. Scientific evidence is independent and always recorded per `evidence_mode`.

## Presets (Observer-only)

| Preset | Products | Frame detail on STEP |
|--------|----------|----------------------|
| **MINIMAL** | world, telemetry, mechanisms | compact |
| **NORMAL** (default) | + cognition, smc, historical_sensorimotor_selection, geometry, experimenter | compact |
| **FULL** | all products | full (inspect-grade) |

Changing preset does **not** change cognition, mechanism ON/OFF, world state, RNG, or scientific receipts.

## Subscription API

- `GET /api/observer/detail` — current interest snapshot
- `POST /api/observer/detail` `{ "preset": "MINIMAL"|"NORMAL"|"FULL" }`
- `POST /api/observer/detail` `{ "product": "smc", "enabled": true }`
- `POST /api/observer/detail` `{ "products": ["world", ...] }`

Module: `mechanistic_mind/ui/psy_observer_web/subscriptions.py`  
Session: `_observer_interest: ObserverInterest`

## Cadences

Suggested Hz in `DEFAULT_CADENCE_HZ` (world ~20, telemetry ~4, cognition panels ~2–3, graphs ~1.5). Simulation continues independently; existing `ui_hz` + latest-wins capture already coalesce display frames (`visual_frames_dropped`).

## Panel lifecycle

- SMC / Historical Sensorimotor Selection APIs return `status: DEFERRED` when unsubscribed (no store work).
- Frontend `ObserverDetailControl` switches presets while RUNNING without reset.
- Panel polls pause while the document is `hidden`.

## Backpressure

Unchanged: at most one pending capture; obsolete visual frames drop; scientific append path separate.

## Tests

`tests/test_observer_demand_driven_ui.py` — presets, deferred panels, no runtime reset, producer skip, EXACT_MATCH across presets.
