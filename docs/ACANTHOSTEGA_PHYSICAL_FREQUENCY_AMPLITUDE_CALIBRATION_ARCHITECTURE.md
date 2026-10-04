# PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION — Architecture Audit

**Status:** Architecture audit complete; C0 metadata contract implemented — see `docs/ACANTHOSTEGA_PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION_CONTRACT_V1.md`.  
**C0 IMPLEMENTATION = YES** · **PLAYBACK = NO** · **TOTAL_SIMULATED_TICKS (C0) = 0**

## Central finding

Current acoustic quantities are **anonymous simulation magnitudes** on a discrete **tick × cell** medium. They are **not** SI frequency (Hz), sound pressure (Pa), intensity, or SPL (dB).

Therefore:

| Mode name | Verdict |
|-----------|---------|
| `ORIGINAL / HUMAN-AUDIBLE` | **NOT READY** — cannot honestly claim literal human-audible sound |
| `CANONICAL PHYSICAL-FIELD SONIFICATION` | **POSSIBLE** after Calibration C0–C1 (explicitly non-SI) |
| `SELECTED ORGANISM AUDITORY VIEW` | Can precede SI calibration if labelled **transformed monitor of organism-accessible channels** |
| `EXTENDED / TRANSLATED AUDIBILITY` | Needs at least abstract band ordering + explicit transform provenance; SI optional |

## Recommended staged calibration (Strategy 2 → optional 1)

| Stage | Name | Content |
|-------|------|---------|
| **C0** | Abstract band/time/amplitude authority freeze | Versioned metadata: 6 anonymous bands; optional **declared** monotonic abstract-frequency axis ∈[0,1] for OSC centres only; tick≠seconds; cells≠metres; field quantity = anonymous energy; no Hz/SPL |
| **C1** | Canonical monitoring transform | Deterministic sonification profile mapping abstract bands → audible display; label **CANONICAL PHYSICAL-FIELD SONIFICATION**; never writes sim/cognition |
| **C2** | Optional SI mapping | Only if length/time/medium references are later frozen with dimensional consistency → then reconsider `ORIGINAL / HUMAN-AUDIBLE` gate |

**Rejected as ORIGINAL:** Strategy 3 (arbitrary playback-only remapping without labels).

## Why Hz/SPL cannot be derived today

1. Oscillator “frequency” is normalized \(f\in[0,1]\), not Hz.  
2. Impact spectra are equal energy split (`UNIFORM_BROADBAND_V1`), not physical frequency content.  
3. Time unit is scientific tick (`dt=1` tick), not seconds.  
4. Length unit is world cell, not metre.  
5. Acoustic energy is model coupling from impulse/KE with `mechanical_energy_withdrawn=False`.  
6. Attenuation \(1/(1+kd^2)\) is dimensionless in cells; not acoustic intensity law with SI ρc.  
7. No pressure reference \(p_0\), no characteristic impedance, no human threshold model.

## Evidence pack

See `results/acanthostega_physical_frequency_amplitude_calibration_architecture/`.

## Next slice

`PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION_CONTRACT_V1` — **metadata-only** versioned calibration profile attached to stream/probe/Analyzer; **no** playback, **no** numeric change to `osc_l/r`.
