# P7_RECEPTOR_FPV_LIVE_REFRESH_REPAIR_V1

## Placement

Release-blocking repair inside `P7_BETA4_RELEASE_EQUIVALENCE_AND_PERFORMANCE_GATE_V1` → `OBSERVER_FPV_ACCEPTANCE`.
Not a new FPV system. Not a roadmap successor.

## Symptom

Live Acanthostega Beta 4 Observer: simulation ticks advance, organisms move/rotate heads, RECEPTOR FPV is visible, but the frame is static with `obs_tick=0` / `receptor_tick=0`.

## Expected chain

```
scientific observation
  → O4 exact receptor trace
  → latest_exact_trace[agent/body/generation]
  → frame serialization / P1 subscription
  → P4 / P4B cache identity
  → frontend store
  → selected-agent FPV frame
  → render
```

## First stale seam

**SNF cache hit returns early without FPV publication**, while ObserverSession pre-samples can fill `_SNF_CACHE` for the upcoming tick **without** scientific capture context.

During `ObserverSession.step()`:

1. Apply / prior work may leave an SNF entry for tick `T`.
2. Non-scientific (NOCTX) near-field samples also miss-fill the cache for tick `T` and update `_o4_last_reception_trace`, but `capture_from_o4_trace` correctly no-ops without context.
3. The cognition-bound `agent_observation` then hits the SNF cache with context armed.
4. Cache-hit path previously returned immediately — **no** `capture_from_o4_trace`.
5. Unlike SOVV, FPV had **no** post-observation finalize, so `latest_exact_trace` stayed at the apply-time tick-0 frame forever while `header.tick` advanced.

Direct `TwoAgentRuntime.step()` without Observer pre-sampling often advanced FPV (miss path), which masked the ObserverSession defect.

## Repair (minimal)

1. **near_field_exteroception.py** — on non-diagnostic SNF cache hit: refresh SOVV stash and invoke SOVV/FPV capture (still gated by scientific context inside capture helpers).
2. **organism_physical_optical_reception.py** — stash full O4 traces per body (`_o4_last_reception_by_body`) so multi-agent cache hits publish the correct agent's evidence.
3. **runtime.py `agent_observation`** — finalize FPV from per-body O4 while capture context is still armed (mirrors existing SOVV finalize).

## Non-changes

- O1–O5 physical/sensory numerics unchanged
- Receptor count / FOV / range / phenotype / clipping / pair-fold unchanged
- FPV projection semantics unchanged
- P1–P5 / P4B contracts preserved (WORLD_FRAME remains dynamic; same-tick P4B hits preserved)
- No polling-driven trace generation
- Trace history remains bounded; latest survives FIFO

## Verdict

`A. FIXED_BACKEND_TRACE_PUBLICATION`

## Live process note

Operator restarted the Observer. Live FPV refresh is **CONFIRMED** (port 8769 RUNNING: advancing `obs_tick`/`receptor_tick` with fresh O4 traces). Frontend asset `index-jH_Elu33.js` remains current for FPV UI. Legacy paused interpreters on 8772/8788 may still omit FPV and were not mutated.
