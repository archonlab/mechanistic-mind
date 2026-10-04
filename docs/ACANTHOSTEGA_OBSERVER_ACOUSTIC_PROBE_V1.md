# ACANTHOSTEGA — OBSERVER_ACOUSTIC_PROBE_V1

## Status

**Implemented** as a researcher-only scientific/display contract. Not a physical preset.

| Field | Value |
|-------|-------|
| Schema | `OBSERVER_ACOUSTIC_PROBE_V1` |
| Contract | `observer_acoustic_probe` |
| Receipt | `OBSERVER_ACOUSTIC_PROBE_SAMPLE` |
| Probe ID | `observer-acoustic-probe-0` |
| Mode | `POINT_MONO_V1` |
| Module | `mechanistic_mind/physical_system/observer_acoustic_probe.py` |
| Shared law | `local_physical_signal_transport.evaluate_wavefront_crossing_at_point` / `sample_point_field_passive` |

## Passivity

Probe is **not** a body, mass, collision, spatial-index occupant, LPS receiver, or source.
Enabling/moving/disabling/observing does not change LPS step count, stream records, body auditory, or `osc_l/r`.

## Shared point-field law

Body-centre reception and probe mono sampling share `evaluate_wavefront_crossing_at_point` (wavefront crossing + inverse-quadratic attenuation). L/R organism transduction remains a separate phenotype step.

## Tick seam

```
emitters → step_end_of_tick (ONE) → sync_acoustic_stream → sample_observer_acoustic_probe
```

## Sample semantics

- At most one aggregate sample per scientific tick (pose-stable key)
- Zero field is a valid observation (not a physical source / stream record)
- Contributors bounded (16); truncation counters exposed
- History capacity 64; FIFO eviction

## Limitations (explicit)

XY_ONLY · NO_Z_DISTANCE · NO_OCCLUSION · NO_REFLECTION · NO_REVERB · NO_HUMAN_FREQUENCY_MAPPING

## Observer

Panel + diamond map glyph (not entity/source). Controls: Enable, X/Y, Apply/Move, Use selected cell, Clear history.
Banner: `PASSIVE ACOUSTIC PROBE · PHYSICAL FIELD · XY POINT SAMPLE · NO AUDIO PLAYBACK`

## Next seam

`PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION_CONTRACT`
