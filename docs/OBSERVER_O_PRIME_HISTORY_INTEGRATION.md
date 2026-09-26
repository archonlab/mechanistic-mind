# Observer integration: O′ → history → PSC (Historical Sensorimotor Selection)

## Purpose

Expose the demonstrated O′→history→PSC bridge in Psychology Observer Web without redesigning cognition science. Experience-first defaults: accumulate sensorimotor and predictive history before enabling prospective scenario competition (PSC).

## Mechanism path (UI → runtime)

1. UI `toggleMechanism` → `POST /api/mechanisms/{id}`
2. `ObserverSession.set_mechanism` → `_apply_mechanism_now_unlocked`
3. `runtime.set_mechanism` → `mechanism_registry.set_mechanism`
4. Cognition config written via `cognition["config"] = to_dict()`; SMC store `enabled` synced live

Hot-toggle does **not** rebuild the runtime or clear prospection / SMC stores.

## Flags

| UI / registry id | Config field | Fresh default |
|---|---|---|
| `sensorimotor_consequence_model` | `cognition.sensorimotor_consequence_model` | **ON** |
| `historical_sensorimotor_selection_bridge` | `cognition.historical_sensorimotor_selection_bridge` | **ON** |
| `prospective_scenario_competition` | `prospective_selection=SCENARIO_COMPETITION` | **OFF** |
| Climate | `spatiotemporal_climate_ecology` | **OFF** |

Ablation / control flags (unchanged semantics):

- `historical_sensorimotor_selection_withhold`
- `historical_sensorimotor_selection_shuffle`

Authority for new runs: `fresh_experiment_default_map()` in `mechanism_configuration.py` (PSC forced OFF for experience-first policy). `CognitionConfig` dataclass field defaults may still be False until Observer resolve/stamp.

## UI status

Panel: `HistoricalSensorimotorSelectionPanel` → `GET /api/diagnostics/historical-sensorimotor-selection`

| State | Meaning |
|---|---|
| **OFF** | Bridge mechanism disabled |
| **READY** | Bridge ON, PSC OFF — history/SMC accumulate; selection path unchanged by bridge |
| **ACTIVE** | Bridge ON and PSC ON — O′ historical evidence may participate in PSC |

PSC control shows guidance: explore first (~1000 ticks is a reasonable experimental starting point); PSC can be enabled mid-run without reset.

## What is not Observer cognition

Phase-A exploration schedules used in battery harnesses are **experiment scaffolding only**. They are not wired into Observer UI cognition.

## Verification

- `tests/test_observer_o_prime_history_integration.py`
- Existing `tests/test_o_prime_history_bridge.py`, `tests/test_sensorimotor_consequence_model.py`
- Frontend build: `web/psy-observer` → `mechanistic_mind/ui/psy_observer_web/web_dist`

## Limitations

- Bridge does not change action selection while PSC is OFF (READY is intentional).
- Effect size remains seed-heterogeneous (see `docs/O_PRIME_HISTORY_BRIDGE_REPORT.md`); Observer does not re-run that battery.
- Do not alter `results/mm_o_prime_history_bridge/` or the baseline biography run.
