# Experience Compression Experiment v0.3.6

## Separation and data flow

The experiment uses three one-way layers:

```text
World state -> agent Observation -> finite agent memory -> action
World state + action + agent state -> CompactEvidenceObserver -> evidence
```

`ExperienceCompressionMechanism` receives only `MechanismContext`: current
Observation, its private mechanism namespace, tick, agent ID, and a stateless
seeded random value. No Observer object, history, checkpoint, or objective world
state is reachable from the decision API.

The legacy full causal observer remains available for compatibility. New long
experiments use `CompactEvidenceObserver`: lightweight telemetry each tick,
event records on meaningful transitions, SHA-256 world-state digests, and full
checkpoints at tick 1, every configured interval (250 by default), and pattern
creation/invalidation or environmental perturbation.

## Agent memory

An episode contains the prior decision's context signature, action/action
signature, perceived cue identifiers, coarse body-state signature, position,
agent-observed outcome, novelty, prediction error, and retention deadline. It
contains no world yields, hidden object effects, Observer receipts, or past raw
state snapshot.

COMPRESSED mode groups compatible context/action episodes using deterministic
running means and second moments. After three compatible observations the
candidate becomes a pattern. Pattern confidence combines effective observation
count and outcome variance. Low-error redundant episodes are removed after
their information updates the pattern. High-error episodes receive a protected
retention window. Repeated high error invalidates and reinitializes the pattern.

RAW retains up to 5,000 individual episodes and never creates patterns.
FORGETFUL has the same 64-episode pressure as COMPRESSED but only FIFO eviction;
it receives neither candidates nor patterns. Pattern and episode predictions
are used by the same generic outcome-plus-uncertainty action policy.

## Matched perturbation protocol

All three conditions use seed 17, the same initial agent/world digests, the same
mechanism ID and stateless random stream, and the existing `ReversalYieldWorld`.
At tick 150 the objective action/outcome contingency changes without exposing
the phase or yields to the agent. This isolates the memory architecture while
testing persistence, surprise, invalidation, exploration, and adaptation.

The canonical 360-tick run produced:

| Mode | final episodes | patterns | final decision source | adaptation latency |
|---|---:|---:|---|---:|
| RAW | 359 | 0 | EPISODE | 184 ticks |
| COMPRESSED | 9 | 2 | PATTERN | 3 ticks |
| FORGETFUL | 64 | 0 | EPISODE | 37 ticks |

These values characterize this mechanism/seed; they are not evidence about
human memory and must not be generalized without multi-seed runs.

## Storage evidence

The benchmark measures the compact evidence bytes and serializes the equivalent
legacy full trace without retaining it. Results on the canonical run:

| Ticks | compact | legacy-equivalent | reduction | compact bytes/tick |
|---:|---:|---:|---:|---:|
| 1,000 | 1.26 MB | 16.49 MB | 13.1x | 1,261 |
| 5,000 | 6.30 MB | 83.11 MB | 13.2x | 1,259 |

Run 10,000 and 50,000 points manually with
`--benchmark-ticks 1000 5000 10000 50000`; they are excluded from normal CI.

## Metrics and limitations

The API reports action/path entropy, repeated-route frequency, object
preference/avoidance, context-action consistency, persistence, exploration,
revisits, diversity, episode/pattern counts and bytes, compression ratio,
prediction error, confidence distributions, checkpoints, output bytes, and
peak RSS. Spatial/object metrics remain zero or empty in the canonical
non-spatial reversal world; the same collector becomes active in spatial worlds.

Important confounds: one seed is insufficient for a scientific conclusion;
the UCB exploration coefficient depends on outcome scale; running means assume
numeric stationary segments; checkpoint replay still requires the deterministic
runtime and matching code/config; legacy Studio consumes full tick records and
has not yet migrated to the compact stream. The clean memory summary/events API
is exposed for that later UI migration.

## Acceptance status

- A PASS — the mechanism API has no Observer/history input.
- B PASS — compact telemetry has no raw snapshot; checkpoints are sparse.
- C PASS — compact agent-accessible episodes are formed.
- D PASS — compatible episodes create and update generic patterns.
- E PASS — high-error episodes receive protected retention.
- F PASS — COMPRESSED finishes with `PATTERN` as its decision source.
- G PASS — FORGETFUL contains zero patterns and predicts from episodes only.
- H PASS — all conditions have identical initial world/agent digests.
- I PASS — compact rows distinguish the outcome accessible before a decision
  from the objective outcome produced after that action; the next row permits
  direct objective-to-encoded comparison without a one-tick attribution error.
- J PASS — behavioral and memory metrics are emitted.
- K PASS — the unannounced reversal emits a perturbation event and adaptation
  latency.
- L PASS — RAM, agent memory, evidence, checkpoint, per-record, and output bytes
  are measured.
- M PASS — 5,000 ticks use 6.30 MB versus 83.11 MB legacy-equivalent (13.2x).
- N PASS — all 153 Mechanistic Mind/ARCHON regressions pass.
