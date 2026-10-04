# CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1

**Status:** Implemented (Observer-only playback).  
**Schema:** `CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1`  
**Profile:** `CANONICAL_ABSTRACT_BAND_SONIFICATION_C1_V1`

## What it is

Deterministic labelled transform of `OBSERVER_ACOUSTIC_PROBE_V1` band energies into mono Web Audio monitoring under C0 abstract authority.

Not ORIGINAL · not physical Hz/SPL · not organism hearing · not a second acoustic reality.

## Chain

probe samples + C0 → C1 schedule (√E × G_ref) → six playback carriers → Web Audio → device

## Profile constants (playback only)

| Parameter | Value |
|-----------|-------|
| Carriers `canonical_playback_carrier_hz` | 120, 200, 320, 480, 720, 1000 |
| `fixed_reference_gain` | 0.25 |
| `canonical_seconds_per_tick` | 0.05 (not physical) |
| Queue | 64 drop-oldest |
| Horizon | 0.5 s |
| Envelope | linear ramp, 0.2 × tick duration |
| MAX | `MAX_PLAYBACK_MUTED_BY_POLICY` |

## Files

- Backend profile: `mechanistic_mind/physical_system/canonical_physical_field_sonification.py`
- Frontend: `web/psy-observer/src/acoustic/*`
- Analyzer: `mechanistic_mind/scientific_v3/canonical_physical_field_sonification_summary.py`
- Evidence: `results/acanthostega_canonical_physical_field_sonification_v1/`

## Preservation

Does not mutate LPS, stream, probe numerics, C0 semantics, osc_l/r, cognition, or physics.
