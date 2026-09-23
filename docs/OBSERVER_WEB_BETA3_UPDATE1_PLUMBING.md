# Observer WEB Beta 3 — Update 1 (plumbing × performance × lifecycle)

Not a visual redesign. Isolated validation only. Live port **8771** (`temporal_opt_web_val_18795`) was not attached, played, paused, stopped, or restarted.

Required: `SCIENTIFIC_EQUIVALENCE = EXACT_MATCH`. Observer speed from **less presentation work**, not weaker science.

Artifacts: `results/observer_beta3_update1/`.

## 1. Root causes found

| Finding | Cause | Relationship |
| --- | --- | --- |
| Generic `STOP: REJECTED` | Control receipt had `accepted`/`reason` but UI did not surface structured `error.code`; `saveBanner` was computed then discarded (`void saveBanner`) | **SAVE_FAILED and STOP_REJECTED are independent.** Failed finalize sets status `SAVE_FAILED` and rejects that STOP with `error.code=SAVE_FAILED`. Other illegal STOPs use `STOP_REJECTED` / `INVALID_TRANSITION`. |
| PSC ~65 ms @ ~1 Hz | `signal_sensorimotor_panel` always called `full_composite_psc_shadow.replay_tick` while the Signal panel polled | Analysis-only; does not mutate agent/runtime. |
| ~43 KB catalog while RUNNING | Aux poll `GET /api/mechanisms` included COLD `catalog` + descriptions | Enabled flags are WARM; catalog is COLD. |
| Compact ~341 KB | Dominated by HOT world grids (~123 KB) + `agents_views` (~86 KB) + `physical` (~53 KB) + `body` (~23 KB). COLD `experiment` was ~15 KB every frame. | Grids required for world render. Agent duplication not proven equivalent — not unified. |
| Control receipt deepcopy | `_clone_published` deepcopied the full published frame for every control response | Presentation/lifecycle wrap only; scientific Decision/Motor receipts unchanged. |
| Session ~13 ms vs bare ~4.8 ms | **Not Observer JSON.** Session-bound `runtime.step` ≈ 12 ms after `apply_experiment`; events/evidence/motion/experimenter-idle ≈ 0–0.02 ms; capture is off the scientific path. Default `PhysicalSystemRuntime(seed=17)` is a different (cheaper) constructor. | Not optimized this pass. |
| HEADLESS stale picture | Capture skipped (correct) but HUD `tick` was overwritten with `sim_tick`, so the last image looked current | Display tick vs runtime tick now explicit. |

## 2. Lifecycle changes

Structured Observer control receipts (not scientific DecisionReceipts):

- `ok`, `accepted`, `operation`, `lifecycle_state`, `reason`
- on failure: `error: { code, message, recoverable }`

Codes actually produced: `SAVE_FAILED`, `STOP_REJECTED`, `INVALID_TRANSITION` (plus frontend `DISCONNECTED` / server unavailable).

`STOP save=true`: `FINALIZING` → persist → `STOPPED`, or `SAVE_FAILED` with live runtime preserved (retryable).  
`STOP save=false`: `STOPPED` without persist. Independent of SAVE.

Frontend: SAVE_FAILED banner restored; receipt shows `error.code` + message; Play/Pause/Step/Stop/Reset disabled when `DISCONNECTED`.

## 3. PSC shadow demand gating

Default `GET /api/diagnostics/signal-sensorimotor` and `signal_sensorimotor_panel()` use `include_shadow=false` → `motor_resolution_shadow.status=DEFERRED` (no `replay_tick`).

Checkbox in Signal → PSC panel requests `?include_shadow=true`. MINIMAL still defers. Runtime PSC unchanged.

Measured isolated: hidden **0.708 ms**, requested **37.8 ms** (audit mounted poll was **65.48 ms** — same path, different tick/store size). Two requested replays at the same tick: exact JSON match.

## 4–5. HOT / WARM / COLD and mechanism polling

See `hot_warm_cold_inventory.json`.

RUNNING aux uses `GET /api/mechanisms/state` (WARM enabled flags, ~6.3 KB) unless `runtime_generation` changed. Full catalog at load / generation change. Hidden document: aux poll skipped.

`FULL_MECHANISM_CATALOG_REPEATED_WHILE_RUNNING = NO`.

Before: 43 488 B × 30/min ≈ 1.30 MB/min catalog. After: 6 290 B × 30/min ≈ 0.19 MB/min flags.

## 6–7. Compact payload

Decomposed in `compact_payload_breakdown.json`.

Safe HOT change this pass: compact `experiment_config_frame` omits static planet/body/internal/cognition dicts (full remains on PAUSE/INSPECT).

| | bytes |
| --- | --- |
| Audit compact | 341 408 |
| After compact p50 | 329 447 |
| Experiment full → compact | 14 431 → 2 561 (−11 870) |

Not removed: world scalars, `agents_views`, `physical`, `body`, preflight `rows` (Preflight panel still reads them while RUNNING).

## 8. Control receipts

`_clone_published` / `_with_receipt` shallow-wrap header + top-level dict. Nested world object identity preserved. Receipt wrap **0.008–0.055 ms** vs multi-MB deepcopy.

## 9. Scientific wrapper attribution

`SCIENTIFIC_WRAPPER_OVERHEAD_ATTRIBUTED = YES`.

| Part | p50 ms |
| --- | --- |
| Default-constructor `PhysicalSystemRuntime.step` | 4.87 |
| Session-bound `runtime.step` | 11.98 |
| Experimenter pre/post (inactive) | 0.001 |
| `_scientific_step_once` | 13.25 |
| events / motion / SEARCH_COMPACT evidence | 0.014 / 0.002 / 0.001 |

Presentation JSON is not this delta. No T0 evidence weakening.

## 10. HEADLESS stale frame

`current_frame` sets `display_frozen`, `display_tick` (last captured), `sim_tick` / `live_runtime_tick`. Banner: `DISPLAY FROZEN @ tN · RUNTIME @ tM`. No extra HEADLESS capture.

## 11–12. Network / performance

Compact HOT −12 KB; catalog polling removed; shadow off the default poll. Compact build/JSON still ~3.7 + 5.3 ms, **flat through t5000**. FULL still inspect-grade (~22 + 19 ms, ~1.29 MB this probe).

`LONG_RUN_OBSERVER_SCALING_REGRESSION = NO`.

## 13. Scientific equivalence

LIVE / HEADLESS / MINIMAL / FULL observer presets, 40 ticks, seed 17: **identical** body/world fingerprint.

`SCIENTIFIC_EQUIVALENCE = EXACT_MATCH`.

## 14. Tests

`tests/test_observer_beta3_update1_plumbing.py` plus demand-driven + PSC motor-resolution Observer UI. Frontend `lifecycleReceipt.test.ts`. `web_dist` rebuilt.

`TESTS = PASS` for this update. Full `npm test` still has a **pre-existing** `measurementIntegrity` failure (`STRUCTURED COGNITIVE EVENTS` log label) unrelated to plumbing.

## Production files changed

- `mechanistic_mind/ui/psy_observer_web/session.py`
- `mechanistic_mind/ui/psy_observer_web/serialize.py`
- `mechanistic_mind/ui/psy_observer_web/server.py`
- `web/psy-observer/src/App.tsx`
- `web/psy-observer/src/components/SignalSensorimotorPanel.tsx`
- `web/psy-observer/src/lifecycleReceipt.ts` (new)
- `web/psy-observer/src/lifecycleReceipt.test.ts` (new)
- `web/psy-observer/package.json` (test include)
- `tests/test_observer_beta3_update1_plumbing.py` (new)
- `mechanistic_mind/ui/psy_observer_web/web_dist/` (rebuild)

## Remaining — Update 2 (deliberate)

- App.tsx monolith / `setNow` 500 ms rerenders / React.memo / RUN·INSPECT·ANALYZE layout
- Unify `agents_views` / `physical` / `body` only after semantic proof
- Move preflight `rows` off compact HOT (panel still needs a WARM channel)
- World renderer / map aesthetics
- Full `npm test` measurementIntegrity log-label drift
- Scientific session `runtime.step` vs default-constructor cost (science/config, not Observer)

`GIT_PUSH = NO`

## Verdicts

| Key | Value |
| --- | --- |
| LIFECYCLE_STATE_TRUTHFUL | YES |
| SAVE_FAILED_VISIBLE | YES |
| STOP_REJECTION_REASON_VISIBLE | YES |
| PSC_SHADOW_DEMAND_GATED | YES |
| PSC_SHADOW_HIDDEN_COST_ZERO_OR_NEGLIGIBLE | YES |
| PSC_SHADOW_RESULT_EXACT | YES |
| HOT_WARM_COLD_CLASSIFIED | YES |
| REPEATED_COLD_MECHANISM_POLLING_REMOVED | YES |
| COMPACT_PAYLOAD_DECOMPOSED | YES |
| HOT_FRAME_COLD_DATA_REDUCED | YES |
| CONTROL_RECEIPT_FULL_COPY_AUDITED | YES |
| SCIENTIFIC_WRAPPER_OVERHEAD_ATTRIBUTED | YES |
| HEADLESS_CAPTURE_SEMANTICS_UNCHANGED | YES |
| HEADLESS_STALE_DISPLAY_TRUTHFUL | YES |
| LONG_RUN_OBSERVER_SCALING_REGRESSION | NO |
| SCIENTIFIC_EQUIVALENCE | EXACT_MATCH |
| TESTS | PASS |
| GIT_PUSH | NO |
