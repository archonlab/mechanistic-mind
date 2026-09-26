# PSC COMPOSITION PERFORMANCE

**Marker:** `PSC_COMPOSITION_PERFORMANCE_ACCEPTED`

**Outcome:** **E** (with measured call-level redundancy that is not end-to-end profitable) — remaining filled-store PSC work is largely scientifically necessary under current semantics.

## Starting point

`LIVE_OPTICAL_PERFORMANCE_ACCEPTED`: late science ~38 t/s; LIVE compact ~43–45 t/s; packed PSC default; `_sig` cache present.

## Configuration

All normal mechanisms ON, Climate Ecology OFF, Vision R3, 2 agents. See `results/psc_composition_performance/effective_configuration.json`.

## Action repertoire (runtime)

**14 actions:** WAIT, MOVE:N/S/E/W, NECK_LEFT/RIGHT/HOLD, PUSH, OSC_FREQ_UP/DOWN, OSC_AMP_UP/DOWN, OSC_EMIT.

Composite motor **selects** on locomotion only (5), but `compose_trajectories` / `pc.predict` still iterate the **full** repertoire.

## Semantic keys (proven from code)

| Stage | Equivalence key |
|-------|-----------------|
| `predict_one_step` / soft_match | `_sig(_q(antecedent)) \|\| action` |
| `compose_trajectories` | `_sig(_q(start)) \|\| ordered branch_actions \|\| depth` (once per agent) |
| `pc.predict` | quantized fragment + action + domain |

**Action string is part of soft_match/prediction keys.** Distinct actions are never interchangeable at those stages.

## Loco-only hypothesis

**REJECTED.** Non-locomotion candidates are genuinely distinct for soft_match and prediction. “Fingerprint-aware loco-only compose” would change science, not merely remove duplicates.

## “14-action compose” diagnosis

**PARTIALLY CORRECT:** `compose_trajectories` is called **once per agent** (2/tick), not 14 times. Cost is multiplied **inside** compose by seeding/expanding `predict_one_step` across the full `branch_actions` list (≤ MAX_EXPANSIONS=64).

## Filled-store hotpath (instrumented Phase A)

| Stage | Share / notes |
|-------|----------------|
| `compose_trajectories` | ~44% of staged (includes nested predict) |
| `predict_one_step` soft path | ~29% |
| `_sig` | high call volume; **hit rate ~99.8%** → further hash opt not justified |
| bare `soft_match` | ~3.5%; **~1.2 rows/call** with packed index |

Calls/tick (2 agents, filled): ~119 `predict_one_step`, ~107 soft_match, 2 compose, ~33 `pc.predict`.

## Equivalence classes (filled)

| Stage | Raw/tick | Unique/tick | Dup fraction |
|-------|----------|-------------|--------------|
| soft_match | ~107 | ~70 | ~34% |
| predict_one_step | ~119 | ~77 | ~35% |
| compose | 2 | 2 | 0% |
| pc.predict | ~33 | ~29 | ~7% |

Duplicate fraction is **BFS revisits of the same `(antecedent_q, action)`**, not cross-action equivalence classes.

Estimated duplicate wall ~7 ms/tick (instrumented). Soft_match itself is already cheap per call.

## Optimization attempted then reverted

**Cognition-cycle cache for `predict_one_step`** (same semantic key → reuse).

Same-process A/B (`results/psc_composition_performance/ab_cycle_cache.json`):

| | t/s |
|--|-----|
| cache OFF | 27.75 |
| cache ON | 27.23 |
| Δ | **−0.52** (−1.9%) |

Per brief rule: **REVERTED** (no end-to-end benefit; cache keying/`_sig` overhead ≥ soft-match savings at ~1.2 rows/action).

## Rejected

- Loco-only compose (semantic change)
- Soft-match prefilter (already ~1.2 rows/action)
- Further `_sig` work (99.8% hits)
- NumPy / Numba / GPU / single-world multicore (unchanged: NOT_WORTH_IT / UNSAFE)

## Uninstrumented (current code, cache reverted)

| Regime | t/s | ms/tick |
|--------|-----|---------|
| Early | ~43 | ~23 |
| Filled | ~29.5 | ~34 |
| Plateau | ~28 | ~35 |
| LIVE + compact | ~32 | ~31 (capture ~7 ms) |

Machine-dependent; LOP reported late science ~38 under quieter load. No retained semantic code change from this task.

## Equivalence

Self-replay / multi-seed / filled / exposure-heavy fingerprints: **EXACT_MATCH** (no semantic code change retained).

## What now limits one-world speed?

Genuinely required work under current semantics:

1. Per-action prospective retrieval across the full 14-action branch list inside compose (scientifically distinct keys).
2. Broader cognition around compose (selection, other predictive modules, scientific append).

Not: cross-action predictive equivalence classes; not Vision; not Observer compact capture.

## Recommended NEXT

Only if science owners explicitly accept a **new fingerprint baseline**: change `branch_actions` for compose/predict loops to match composite’s locomotion competition set **as a documented model change**, not a silent perf hack. Otherwise treat filled-store ~plateau as the required cognition cost ceiling for interactive single-world use.
