# Integrated Psyche v1

Integrated Psyche v1 is an additional continuous-run configuration. It is not
a replacement for, or reinterpretation of, historical acceptance experiments.

## Reused implementation inventory

- Dynamic compositional ecology: `worlds/contextual_object_ecology_v034.py`,
  `mechanistic_mind/world_engine/*`.
- Continuous physical fields: `world_engine/background_fields.py`.
- Objective body and persistent generic processes: `body/engine.py` and
  `body/persistent_processes.py`.
- Agent-visible multi-channel fragments: `world_engine/perception.py`.
- Predictive compression: `research/predictive_compression.py`.
- Multi-scale organization: `research/multiscale_prediction.py`.
- Prospective trajectory composition: `research/prospective_composition.py`.
- Instrumental observation store: `research/instrumental_observation.py`.
- Runtime, observer and serialization contracts: `core/engine.py`, `observer/*`.

`integrated/mechanism.py` is an adapter. It projects only numeric values from
the ordinary `Observation`, updates the tested stores, retrieves predictions,
composes bounded continuations, and returns a normal physical action proposal.
No world-state object is passed into cognition.

## Causal flow

World/body dynamics → ordinary observation → bounded experience/compression →
local and broader predictive stores → bounded transition composition → action
proposal → ordinary world/body transition → next observation. Provenance edges
are emitted only where code consumes the source as an input. Mere succession is
marked `TEMPORAL`, not causal.

## Bounds and telemetry

All reused store capacities remain active. The causal trace is a ring (512
events by default, at most three times that many edges). Observer JSONL uses
compact world deltas. Run metadata records every pre-run mechanism switch.
Observer model properties expose integrated layers, configuration, and trace;
ground truth remains in the pre-existing objective namespace.

## Snapshots

Snapshots preserve the exact `SimulationState`, mechanism stores, bounded
provenance, world/body state, clock, run configuration and Python RNG state.
Observer telemetry is excluded. The pickle payload is base85-wrapped inside a
versioned JSON envelope; snapshots must therefore be treated as trusted local
research artifacts.

## Commands

```bash
python3 experiments/run_integrated_psyche_v1.py --ticks 1000 --seed 17
python3 psychology_observer.py
python3 -m pytest tests/test_integrated_psyche_v1.py
python3 experiments/run_update421_predictive_compression.py --seed 17
python3 experiments/run_update422_multiscale_prediction.py --seeds 17 --ticks 400
python3 experiments/run_update423_prospective_composition.py --seeds 17 --ticks 40
python3 experiments/run_update425_instrumental_observation.py --seeds 17 --ticks 80
python3 -m pytest tests/test_contextual_object_ecology_v034.py tests/test_autonomous_world_dynamics.py tests/test_experience_compression.py tests/test_bounded_cognition.py tests/test_multi_channel_perception.py tests/test_persistent_prospective_trace.py tests/test_observer.py tests/test_observer_serialization.py
```

The Observer's historical preset selector includes **Integrated Psyche v1**.
Pause/single-step and decoupled rendering are available in the current-world
live surface; preset execution supports slow pacing through the existing launch
spec and unbounded execution with zero delay.

## Claim boundary

Passing integration tests supports a coupled recurrent software system: learned
store outputs can change selected actions; actions change physical trajectories;
new accessible observations then update the same bounded learned stores. It does
not establish consciousness, sentience, emotion, curiosity, beliefs, goals,
planning, subjective time, human-like cognition, or general intelligence.
