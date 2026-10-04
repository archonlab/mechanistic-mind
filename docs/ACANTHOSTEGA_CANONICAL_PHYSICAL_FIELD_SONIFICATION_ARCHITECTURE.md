# CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1 — Architecture Audit

**Status:** Architecture / scientific-semantics only.  
**IMPLEMENTATION_STARTED = NO** · **TOTAL_SIMULATED_TICKS = 0**  
**No AudioContext in repository today** (grep clean).

## Purpose

First honest listening mode: **CANONICAL PHYSICAL-FIELD SONIFICATION** — a deterministic, Observer-only playback transform of the authoritative **passive probe** field under **C0** abstract authority.

Not ORIGINAL / HUMAN-AUDIBLE · not Hz-calibrated physics · not organism hearing · not semantic SFX · not a second acoustic reality.

## Chain

```
physical sources → LPS → OBSERVER_ACOUSTIC_PROBE_V1 samples
  → ABSTRACT_ACOUSTIC_AUTHORITY_C0_V1
  → C1 playback transform (non-authoritative)
  → browser audio renderer
  → human device
```

## Recommended identities

| Field | Value |
|-------|-------|
| Schema | `CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1` |
| Profile | `CANONICAL_ABSTRACT_BAND_SONIFICATION_C1_V1` |
| Mode label | `CANONICAL PHYSICAL-FIELD SONIFICATION` |
| Warning | `TRANSFORMED PLAYBACK OF ABSTRACT PHYSICAL FIELD · NOT PHYSICAL Hz · NOT SPL · NOT ORIGINAL HUMAN-AUDIBLE` |

## Authoritative input

**`OBSERVER_ACOUSTIC_PROBE_V1` sample history + C0 reference.**  
Default mode does **not** use `osc_l/r`, pixels, semantic source labels, or frontend frame cadence.

## Recommended transform (summary)

- **Six fixed playback carriers** (`canonical_playback_carrier_hz`) — device Hz coordinates, **not** physical band centres  
- Amplitude ∝ **√energy** with **fixed playback reference** (no AGC, no per-event loudness equalization)  
- Zero field → exact silence  
- **Mono** (`POINT_MONO_V1`)  
- Tick→playback via versioned `canonical_seconds_per_tick` (playback parameter ≠ physical seconds)  
- Impacts/OSC emerge from **probe sample sequence** after LPS delay, not HIT/FOOTSTEP labels  

## Implementation gate

**READY_WITH_CONSTRAINTS** — C0 + probe exist; no Web Audio yet; autoplay gesture + queue policies required at implementation.

## Next slice

`CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1` implementation (Observer-only renderer).

## Evidence pack

`results/acanthostega_canonical_physical_field_sonification_architecture/`
