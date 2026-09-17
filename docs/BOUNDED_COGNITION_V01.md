# Hierarchical Bounded Retrieval v0.3.7

## Decision pipeline

The existing experience-compression mechanism now follows one deterministic
agent-facing path:

```text
current local observation and body signals
  -> bounded-retrieval-cue-v1
  -> indexed mature pattern candidates
  -> linked exceptions / representatives when insufficient
  -> indexed episodes when still insufficient
  -> explicit low confidence or unknown
  -> existing numerical outcome-plus-uncertainty selector
  -> observed outcome, prediction error, and retention update
```

The mechanism receives only `MechanismContext.observation`, its isolated memory
namespace, and a seeded stateless random value. Observer history, objective
world state, hidden object effects, future outcomes, and perturbation timing do
not enter the cue or memory update.

## Cue and cognitive budget

`bounded-retrieval-cue-v1` contains context, coarse body bands, lawful local
visual fragments, recent action, and the previously observed response fragment.
Its lookup signature uses the pre-outcome context; the response remains retained
as evidence so contradictory outcomes can update or invalidate the same pattern.

Default hard limits are:

```yaml
max_pattern_candidates: 4
max_exception_candidates: 4
max_episode_candidates: 8
max_total_memory_candidates: 12
```

A candidate counts when its stored contents are inspected. Hash-index probes are
reported separately. Bounded mode never iterates the full episode biography or
the complete pattern store. Index misses legitimately produce unknown evidence.
`LEGACY_UNBOUNDED` remains an explicitly named experimental ablation.

## Memory lifecycle

A mature pattern is sufficient at confidence 0.45 and effective sample count
3.0 by default. Low-error compatible experience updates its running outcome
statistics, removes redundant episodic detail, and may replace one of two
representative fragments. Moderate/high error is retained as compact evidence;
up to three high-information exceptions remain linked to a pattern. Repeated
contradiction weakens and can invalidate its running aggregate.
Pre-pattern aggregates are independently capped at 256 by default, preventing
unique spatial contexts from creating an unbounded candidate store.

Novelty controls retention and uncertainty only. It is not added to action
value, reward, valence, or a forced exploration policy. Partial evidence stores
only cue/action, prediction, observed response, error, selected sensory
identifiers, timestamp, and provenance—not a full world snapshot.

For spatial organism runs, numerical outcome projection follows declared
agent-facing body-signal directions: increasing energy/hydration/progress counts
positively, while increasing fatigue/discomfort/effort/damage counts negatively.
This is a configurable interpretation of the physiological interface and does
not assign intrinsic value or meaning to any object.

## Short-range vision

Contextual object ecology defaults to a two-cell Manhattan horizon. The new
`visual_fragments` stream is agent-relative and exposes geometry and observable
physical features: relative position, distance, cue signal, size, shape, color,
opacity, brightness, and traversability where applicable. It omits hidden role,
body effects, contact consequences, and semantic conclusions. These fragments
enter only the ordinary retrieval cue; there is no special approach/avoid rule.

## Evidence and experiments

`CompactEvidenceObserver` records counts, stage/provenance, confidence, fallback
reason, retention reason, index statistics, and bounded streaming summaries
(mean/max/approximate p50/p95). Wall-clock lookup/fallback/retrieval/selection
timings are aggregated and may be retained through an explicit runtime-only
channel; they are excluded from deterministic scientific telemetry.

Run all four compact experiments:

```bash
python3 experiments/run_bounded_cognition_v01.py
```

The JSON result is written to
`experiments/bounded_cognition_v01_result.json`. Experiment A probes 100, 1,000,
and 10,000 stored patterns; B compares matched legacy and bounded retrieval for
1,200 ticks; C measures compression, bounded exceptions, and invalidation; D
compares matched vision horizons 0 and 2. Behavioral differences and null
results are both valid.

## Psychology Observer integration

The `contextual-objects` Run Setup exposes four real-runtime conditions:
`BOUNDED_COMPRESSED`, `BOUNDED_RAW`, `BOUNDED_FORGETFUL`, and
`LEGACY_PSYCHE_V03`. The first is the default for new contextual-object runs.
The Observer projects the selected memory mode, episode/pattern/novel-fragment
counts, retrieval stage and inspected candidates, confidence, prediction source,
and retention reason. The legacy condition remains available for direct visual
comparison and backwards compatibility.

## Claim boundary

This implementation demonstrates bounded contextual retrieval in this tested
mechanism. It does not establish human cognition, understanding, curiosity,
semantic object recognition, rationality, consciousness, or optimal behavior.
