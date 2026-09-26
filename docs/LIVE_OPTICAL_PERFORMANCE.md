# LIVE OPTICAL PERFORMANCE

**Marker:** `LIVE_OPTICAL_PERFORMANCE_ACCEPTED`

## Question

Why does a normal 2-agent Observer world feel expensive after other-body optical exposure?

## Verdict

Other-body optical exposure is **correlated**, not the primary computational cause.

| Factor | Role |
|--------|------|
| Physical Vision (`sample_near_field`) | **Exonerated** (~0.7 ms/sample, flat with exposure) |
| Cognition store fill (prospection transitions → 128) | **Primary science cost growth** |
| Observer **full** `cognitive_view` / `memory_cost` | **Primary interactive collapse** when frames are `detail=full` every tick |
| LIVE RUNNING compact capture | Cheap (~5 ms) and stable |

Novel exo input (including other-body optical contribution) accelerates unique antecedents, so transition stores fill earlier. That raises soft-match / compose work. Separately, PAUSE/STEP/full frames were re-serializing growing cognition stores many times per frame.

## Benchmark configuration

All current mechanisms ON except **Climate Ecology OFF**. Artifact: `results/live_optical_performance/effective_configuration.json`.

## PERFORMANCE PROFILE CONFIGURATION MISMATCH DISCOVERED

Use `effective_configuration.json` as the authority for *this* profile. Do not
promote these TPS numbers to the canonical Beta 3.1 baseline unless that file
matches `TIKTAALIK_BETA31`. Artifacts not deleted.

## Reproduction

- Seed **17** (natural + adjacent fixture for sustained proximity).
- Science-only path (no per-tick full capture) used for causal isolation.
- `session.step(1)` always builds a **full** Observer frame — that path previously looked like a “Vision collapse” but was capture+cognition-view cost.

## Transition (science-only, after opts)

| Window | Before | After |
|--------|--------|-------|
| Early (~1–50) | ~40 t/s | ~58 t/s |
| Mid | ~32 t/s | ~40–43 t/s |
| Late (~200+) | ~29 t/s | ~37–39 t/s |

Adjacent optical fixture is not slower than far agents once stores fill.

## Vision ON/OFF (performance only)

~52 vs ~50 t/s (noise-level). Physical Vision does not cause the collapse.

## R1 / R2 / R3

Vision radius changes candidate cells; end-to-end cost difference is small vs cognition store fill. See `vision_range_scaling.json`.

## HEADLESS vs LIVE

HEADLESS science ~50 t/s. LIVE with compact capture amortized ~43–45 t/s. Observer Hz mainly changes how often ~5 ms compact frames run under `step_lock`.

## Optimizations implemented

1. **Default PSC backend `packed`** (EXACT_MATCH vs legacy; multi-seed verified).
2. **`_sig` payload cache** (prospective + compression).
3. **`memory_cost` structural cache** (stops repeated full-store `json.dumps` on Observer views).
4. **Same-tick `cognitive_view` cache**.
5. **Same-tick `sample_near_field` cache**.
6. **Defer counterfactual soft-match probe** to sampled decision-trace ticks (Observer diagnostic).

## Rejected / deferred

- Restrict compose/predict to locomotion-only under composite motor (would change fingerprints).
- Numba / GPU (not justified for this single-world hot path).
- Parallel multi-agent cognition inside one world (**UNSAFE** without architecture change: shared world, RNG, event order).

## Equivalence

- packed vs legacy multi-seed (17,23,41,59,83): **EXACT_MATCH**
- Exposure-heavy adjacent seed 17: **EXACT_MATCH**
- Self-replay fingerprint: **EXACT_MATCH**

## Served Observer

Verified at `http://127.0.0.1:8770` — LIVE RUNNING, Vision R3, Climate OFF, agents updating, UI responsive.

## NEXT performance step

Bound compose/predict action loops to the locomotion set under `COMPOSITE_MOTOR_V1` **with a new fingerprint baseline**, or index/limit prospective expansion once MATCH rate is high. Do not disable Vision/cognition/signals.
