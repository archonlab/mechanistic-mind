# Scientific Telemetry V2

Tiered long-run evidence architecture for Mechanistic Mind 2.0 / Tiktaalik: Undercover.

**Status:** Post-Beta Engineering Update 02  
**Depends on:** LONG_RUN_PHASE_1_ACCEPTED (bounded LIVE Observer)

## Goal

Reduce scientific storage substantially while preserving Analyzer / Visual Forensics /
Signal Forensics measurements. Telemetry is observation/storage — never a causal input
to cognition or physics.

## V1 architecture (reference)

Per tick, `ScientificHistoryWriter` appended:

1. **scientific_timeline.jsonl** — one rich row per `(tick, agent)` including:
   - pose / action / resources / thin cognition counters
   - full `vision_optical` (with prose + alias duplication)
   - GEO nests: `action_realization`, `work_ecology`, `locomotor_economy`
2. **scientific_events.jsonl** — nearly all runtime structured events, including:
   - full `SCENARIO_SELECTED` graphs (~5 KB each)
   - every-tick bookkeeping (`SITE_GEOMETRY_CHANGED`, `BODY_MOVED`, …)

Measured (Phase 1 / this audit): **~33–41 KB/tick** (~73% events, ~27% timeline).

## V1 storage breakdown (ranked)

| Contributor | Approx share | Disposition in V2 |
|-------------|-------------:|-------------------|
| `SCENARIO_SELECTED` rich graphs | ~35% of events | compact summary (action/score/id) |
| Other near-tick events (DEFORM/CONVERSION/…) | large | keep lean (Analyzer counts) |
| `SITE_GEOMETRY` / `BODY_MOVED` | large | omit → checkpoint / NOT_RECORDED_IN_V2 |
| Timeline GEO triple | ~50% of row | checkpoint only |
| `vision_optical` | ~34% of row | VF fields only; drop prose/aliases |
| Meta | negligible | versioned once |

See `results/performance/scientific_telemetry_v2/v1_storage_breakdown.json`.

## Evidence requirements matrix

Machine-readable: `results/performance/scientific_telemetry_v2/evidence_requirements_matrix.json`.

Summary:

| Class | Examples |
|-------|----------|
| EVERY_TICK_REQUIRED | pose, action, resources, contact, thin cognition counters, VF exo/exposure |
| EVENT_ONLY_SUFFICIENT | SCENARIO/DISCRETE counts, signals, interventions, DEFORM/CONVERSION |
| CHECKPOINT_SUFFICIENT | GEO receipts, rich scenario graphs, force dumps |
| STATIC_METADATA | seed, map, schema, constant vision notes |
| DERIVABLE | exo aliases, duplicated work fields |

## V2 architecture

| Level | File | Content |
|------:|------|---------|
| 0 | `scientific_meta.json` | mode, schema major/minor, exhaustiveness policy, durability |
| 1 | `scientific_timeline.jsonl` | `scientific_tick.v2` compact rows |
| 2 | `scientific_events.jsonl` | Analyzer-exhaustive families, compact payloads |
| 3 | `scientific_checkpoints.jsonl` | periodic full V1-shaped rows (default every 10 000 ticks) |

Modes (env `SCIENTIFIC_TELEMETRY_MODE`):

- `SCIENTIFIC_V1_REFERENCE` — legacy full writer (equivalence harness)
- `SCIENTIFIC_V2_TIERED` — default

### Exhaustiveness (no information-laundering)

- Analyzer-relevant families (SCENARIO, DISCRETE_ACTION, PREDICTION, DEFORM,
  WORK_LIMIT, CONVERSION, PHYSICAL_SIGNAL, WORLD_INTERVENTION, EXPERIMENTER, …)
  are **exhaustive when emitted** (payloads compacted, not dropped).
- Omitted types (`BODY_MOVED`, `SITE_GEOMETRY_CHANGED`, …) mean
  **`NOT_RECORDED_IN_V2`**, not “did not occur”.
- Analyzer must not treat absence of omitted types as a scientific observation.

### Schema detection

`load_evidence_package` sets `telemetry_schema`:

- `V1_FULL` — old Public Beta / reference
- `V2_TIERED` — new writer

Old histories remain readable on the V1 path. Missing reconstructible metrics stay
**NOT_AVAILABLE** (never silent zero).

## Analyzer reconstruction rules

| Need | Source in V2 |
|------|----------------|
| Trajectory / actions / resources / contacts | LEVEL 1 timeline |
| Scenario / discrete / deform / conversion counts | LEVEL 2 events (compact) |
| Visual Forensics exposure | LEVEL 1 `vision_optical` |
| Signal emit/receive / attribution | LEVEL 2 signal events |
| Interventions / regimes | LEVEL 2 `WORLD_INTERVENTION` |
| Deep GEO / rich scenario graphs | LEVEL 3 checkpoints (optional) |

## Measured results

From `results/performance/scientific_telemetry_v2/benchmark.md`:

| ticks | V1 B/tick | V2 B/tick | ratio |
|------:|----------:|----------:|------:|
| 1 000 | 32 842 | 5 487 | 6.0× |
| 10 000 | 32 764 | 5 289 | 6.2× |

Equivalence (120 + 1k + 10k): simulation / Analyzer core / VF exposure **EXACT_MATCH**.

### Why not ≤4 KB/tick?

Remaining ~5.3 KB/tick is dominated by **Analyzer-counted near-every-tick events**
(SCENARIO_SELECTED summaries, DISCRETE_ACTION_SELECTED, DEFORM, CONVERSION) plus
compact multi-agent vision rows. Further cuts would change Analyzer counters or
drop VF fields — rejected under ST6/ST7. **~5.3 KB/tick with full evidence
preservation is accepted over a smaller scientifically weaker log.**

### Long-run estimates (V2 steady-state ≈ 5.3 KB/tick)

| Horizon | Estimate |
|---------|----------|
| 100k | ~0.50 GB |
| 1M | ~4.9 GB |
| 10M | ~49 GB |

(vs V1 ~32–41 KB/tick → hundreds of GB at 10M)

## Writer memory

V2 bounds event-dedupe keys to a recent tick window (`SEEN_KEY_TICK_WINDOW`) instead
of retaining every historical key. Prefer stream→disk; no full-experiment retain.

## Crash / durability

Buffered append (`flush_every` default 32). After `flush()`, completed lines are
readable. Unexpected kill may lose ≤ buffered lines. No per-record `fsync`
(documented in meta.durability).

## LIVE Observer

Phase 1 bounded LIVE path unchanged. Scientific writer mode does not feed LIVE
frame construction. Re-run `tests/test_live_observer_bounds.py`.

## Snapshot / resume readiness (Phase 3)

V2 coexists with future deterministic resume:

- Checkpoints store rich Observer/GEO rows, **not** full RNG/runtime authority.
- Remaining blockers for `snapshot N + future inputs + RNG → identical continuation`:
  1. Explicit RNG stream capture/restore verification
  2. Full runtime snapshot continuity (already partially present)
  3. Scientific writer append continuity across resume (new run_id vs continue)
  4. Intervention/regime rebinding

## Code

- `mechanistic_mind/ui/psy_observer_web/scientific_telemetry_v2.py`
- `mechanistic_mind/ui/psy_observer_web/scientific_history.py` (mode-aware writer)
- `experiments/run_scientific_telemetry_v2.py`
- `tests/test_scientific_telemetry_v2.py`
