# Mechanistic Mind TODO #4 implementation report

## Implemented architecture

- Contextual-object physiology now uses an explicit calibrated profile; the former profile remains callable through `ContextualObjectEcologyWorld.legacy_physiology()` for matched controls.
- `OrganismWorld` constructs one bounded lawful multimodal context from visual fragments, contact/action receipts, carried-state proprioception and interoceptive signals. The contextual ecology adds the existing directional physical field.
- Bounded memory stores atomic perceptual feature tokens with episodes and patterns. It does not enumerate modality combinations or scan beyond the existing 12-record retrieval budget.
- A supported retrieved prediction may supply expected next-percept features. Jaccard discrepancy is emitted only when confidence is supported; insufficient evidence is `unknown` with `mismatch=null`.
- `perceptual_activation` is deterministic, clamped to `[0,1]`, decays each tick, and receives mismatch magnitude. It is not included as reward and has no direct action edge.
- Psychology Observer bounded modes use TODO #4 with `exploration_gain=0`; TODO #1 defaults remain available to the A/B controls.

## Calibration

Exact calibrated coefficients are in `todo4_calibrated_body_config()` and the contextual world fields. The deterministic resource-free control produced:

- legacy WAIT: severe constraint at tick 8;
- calibrated WAIT: energy LOW 267, hydration LOW 280, fatigue HIGH 439, severe constraint 444;
- calibrated ordinary locomotion: energy LOW 165, hydration LOW 226, fatigue HIGH 265, severe constraint 268.

These results were identical for seeds 17, 23 and 41 because the resource-free action protocol intentionally applies no restorative interaction. Physiology is substantially slower but remains finite. PUSH and carried mass retain their pre-existing additional objective costs.

## Observer and Analyzer

The selected-agent panel now shows active modalities, expectation status, mismatch and activation while retaining bounded-memory diagnostics. Large violations and material activation transitions are event records. Candidate diagnostics contain availability, expected consequence, confidence, unknown/uncertainty, physiological and effort contribution, learned contribution, total and selection; they are sampled rather than dumped unconditionally.

Bounded contextual telemetry removes repeated full memory/state-update copies, trims accumulated histories, writes the object/obstacle configuration once and then position/state deltas. The UI projector reconstructs current object truth from those deltas. Psychology Analyzer consumes TODO #4 values and reports unknown/action fractions, retrieval stages, candidate/mismatch/activation ranges and spatial coverage. Epoch labels are now descriptive mobility/interaction regimes.

## Preliminary A/B/C matrix

`experiments/todo4_result.json` contains 100-tick runs for seeds 17, 23 and 41. This is a smoke/calibration matrix, not evidence that C is superior. C produced both high- and low-mobility outcomes across seeds; mismatch was mostly unavailable at this short horizon and the near-zero activation in two seeds is a valid null result.

## Verification and limitations

- Full suite: 185 passed.
- Observer CLI: 120 deterministic ticks completed before compaction; 20 compact-delta ticks completed after compaction.
- Canonical bounded JSONL fell from roughly 1.67 MB/tick in the pathological pre-fix sample to roughly 23 KB/tick in the post-fix sample. The remaining stream is linear but a formal 1k/5k/10k disk benchmark is still required before claiming 50k readiness.
- Acoustic sensing was intentionally not added.
- No temporal credit assignment, semantic perception, novelty reward, forced movement, communication, caregiver mechanics or emotion variables were added.
- The workspace is not a Git repository, so no commit hash can be produced.

## Reproduction

```bash
python3 -m pytest -q
python3 experiments/run_todo4_experiments.py --ticks 500
python3 psychology_observer.py
```

For the Observer select `contextual-objects` and any bounded mode; `BOUNDED_COMPRESSED` remains the default.

## TODO #4 acceptance status

PASS: lawful multimodal context; no hidden/Observer leak; interoceptive context; supported-only mismatch; UNKNOWN is not maximum mismatch; mismatch/activation are not reward; bounded/decaying activation; no forced MOVE/approach/exploration; compact compositional cues; bounded retrieval and stores; all four existing cognition modes remain launchable; deterministic tests, contextual ecology, fields, movable objects, compression, Analyzer consumption, and compact-history regression.

PARTIAL: acquired-predictive-significance, expectation-violation, physiology×perception and different-history capabilities are implemented, but only the short naturalistic matrix has been executed; dedicated controlled result artifacts remain to be generated. Formal 1k/5k/10k telemetry measurements are also pending. Consequently 10k/50k readiness is not yet claimed.
