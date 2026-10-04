# SELECTED_ORGANISM_AUDITORY_SONIFICATION_V1 (SAV2)

## Freshness

- Repository: `<repository-root>`
- Work only on dirty tree; no reset/stash/commit/push; live Observer run not mutated.

## Authority

| Field | Value |
|-------|-------|
| Schema | `SELECTED_ORGANISM_AUDITORY_SONIFICATION_V1` |
| Profile | `CANONICAL_ORGANISM_RECEPTOR_SONIFICATION_SAV2_V1` |
| Capability | `selected_organism_auditory_sonification` |
| Mode | `SELECTED_ORGANISM_AUDITORY_SONIFICATION` |
| Input | `A5_OSC_LR_ACCESSIBLE_OBSERVATION_PRE_COGNITION` via SAV1 Section A only |
| Authority class | `PLAYBACK_DERIVED_TRANSLATED_RECEPTOR_MONITOR` |

## What it is

Translated stereo monitor of selected-organism left/right receptor activations (post-phenotype, pre-cognition). Researcher playback only.

## What it is not

Literal organism sound · human binaural/HRTF · physical mic · C1 probe sonification · ORIGINAL/HUMAN-AUDIBLE · Hz/SPL/dB · cognition/memory/prediction · organism sensory input.

## Pipeline

```
SAV1/A5 receipt (Section A L/R)
  → validate SAV1/A5
  → LINEAR_RECEPTOR_ACTIVATION_FIXED_REFERENCE_V1 (gain=0.35)
  → bounded queue (64, drop-oldest)
  → stereo Web Audio (6 shared carriers × L/R gains → ChannelMerger)
  → monitor volume + playback limiter
  → human output device
```

Never feeds back into organism, simulation, LPS, stream, probe, SAV1, or `osc_l/r`.

## C1 reuse / non-reuse

| Reuse | Item |
|-------|------|
| YES | `canonical_playback_carrier_hz` (shared C1 table) |
| YES | `canonical_seconds_per_tick=0.05`, time-scale, `LINEAR_RAMP_0.2_OF_TICK` |
| YES | queue 64 / FAST/MAX / gesture / teardown / fake-audio seam |
| NO | probe adapter, mono routing, `sqrt(energy)`, probe sample IDs, C1 provenance |

## Amplitude

`amp = 0.35 × clamp(activation, 0, 1)` per band per side. Zero → silence. No AGC / per-event / per-side norm. Distinct from ORGANISM RECEPTOR CLIPPING vs PLAYBACK SAFETY LIMITING.

## Stereo

`TRANSLATED_STEREO_LR_RECEPTOR_MONITOR_V1`: organism L→monitor L, R→R. No HRTF/ITD/crossfeed/source pan.

## Mode ownership

`MUTUALLY_EXCLUSIVE_LISTENING_MODES`: OFF | PHYSICAL_FIELD_C1 | SELECTED_ORGANISM_SAV2. Switching ramps silence, clears queue, tears down prior graph.

## Policies

- REALTIME: bounded schedule
- FAST: lossy drop-oldest (`FAST_PLAYBACK_LOSSY_MONITORING`)
- MAX: `MAX_PLAYBACK_MUTED_BY_POLICY`
- Pause: silence, clear queue, resume from next receipt
- Step: one new receipt at most once
- Enable mid-run: future receipts only
- Selection change / restore / runtime switch: silence, clear, no history replay

## Privacy

SAV2 identifiers in `FORBIDDEN_TOKENS`. Playback never enters observation/cognition. `osc_l/r` remain legitimate and unchanged.

## Files

- `mechanistic_mind/physical_system/selected_organism_auditory_sonification.py`
- `mechanistic_mind/scientific_v3/selected_organism_auditory_sonification_summary.py`
- `web/psy-observer/src/acoustic/sav2*.ts`, `stereoAudioBackend.ts`, `listeningModeOwner.ts`
- Observer UI: SAV2 section in `SelectedOrganismAuditoryViewPanel.tsx`
- Analyzer: `AnalyzeResultsPanel` SAV2 section + pipeline hook

## Next seam

`SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3_ARCHITECTURE`
