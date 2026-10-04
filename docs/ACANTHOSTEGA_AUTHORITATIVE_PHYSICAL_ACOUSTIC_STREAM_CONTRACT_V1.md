# ACANTHOSTEGA — AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_CONTRACT_V1

## Status

**Implemented** as a scientific/display contract (not a physical preset, not playback).

| Field | Value |
|-------|-------|
| Schema | `AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_V1` |
| Contract | `authoritative_physical_acoustic_stream` |
| Receipt family | `PHYSICAL_ACOUSTIC_STREAM_RECORD` |
| Module | `mechanistic_mind/physical_system/authoritative_physical_acoustic_stream_contract.py` |
| Physical tip | unchanged (`ACANTHOSTEGA_BETA4_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION`) |
| Display parent | `OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1_1` |

## One reality

```
physical cause → mechanism L1 emission receipt → LPS L2 emission_id
  → sync_acoustic_stream (read-only ingest)
  → PHYSICAL_ACOUSTIC_STREAM_RECORD (bounded)
  → Observer / Analyzer
```

Never emits, never advances LPS, never invents Hz/SPL/waveform, never enters cognition.

## Seam / tick map

```
B/B contact acoustics
→ B/O impact acoustics
→ O/O impact acoustics
→ vertical impact acoustics
→ LPS step_end_of_tick (OSC_EMIT + receptions)   [exactly one]
→ sync_acoustic_stream(world)                    [NEW, observational]
```

## Source coverage

| Family | L1 source | Stream mechanism id |
|--------|-----------|---------------------|
| Body/body contact | `contact_acoustic_state.emission_history` | `physical_contact_acoustic_emission` |
| Body/object impact | `body_object_impact_acoustic_state.emission_history` | `body_resource_object_impact_acoustic_emission` |
| Object/object impact | `resource_object_pair_impact_acoustic_state.emission_history` | `resource_object_pair_impact_acoustic_emission` |
| Vertical impact | `vertical_impact_acoustic_emission_state.emission_history` | `vertical_impact_acoustic_emission` |
| OSC_EMIT | LPS `emission_history` with `ENDOGENOUS_MOTOR` / `INTERVENTION_EXPERIMENTER_BODY` | `OSC_EMIT` |
| LPS intervention | LPS `INTERVENTION_SETUP` | `local_physical_signal_transport_intervention` |

Physical-contact LPS rows are **not** double-counted (mechanism history owns L1).
Legacy `OSC_BANDS` is **non-authoritative** when LPS is active and never ingested.

## Ordering

`(scientific_tick, mechanism_rank, source_identity, emission_id)`

Mechanism ranks follow within-tick physical emission order (contact → B/O → O/O → vertical → OSC → intervention).

`stream_record_id = apas:{emission_id}` (deterministic; no UUID/wall-clock).

## Bounded history

- Default capacity **96** (clamped `[8, 512]`)
- Oldest-drop eviction; `evicted_count` exposed
- `seen_emission_ids` retained so restore/re-sync cannot resurrect duplicates

## Layers

| Layer | V1 |
|-------|----|
| L1 source receipts | Captured |
| L2 LPS references | Captured (`lps_emission_id`, enqueue status, transport profile/medium) |
| L3 receiver field | Not globally reconstructable |
| L4 organism transduction | Unchanged (`osc_l/r`) |
| L5 human playback | Absent |

## Snapshot / restore

- Stream state serialized in planet + physical snapshots
- Restore restores bounded records + seen ids + eviction counters
- **Never** re-emits or re-enqueues LPS
- Older snapshots without stream blob: rebuild from mechanism/LPS histories (still no emit)

## Cognition privacy

Extended `FORBIDDEN_TOKENS` for B/O, O/O mechanism ids and stream schema/receipt identifiers.
Anonymous `osc_l_k` / `osc_r_k` remain organism-accessible.

## Observer

Researcher panel: schema, capacity, retained/evicted, recent records (mech, tick, energy, bands, LPS id).
Banner: `PHYSICAL ACOUSTIC EVENTS · RESEARCHER-ONLY · NO AUDIO PLAYBACK · NO HZ CALIBRATION`
No Play/volume/Hz/probe controls.
Vertical display ACOUSTIC_EMISSION markers link `stream_record_id` when available; read `emission_history` (fixed empty `.history` alias).

## Analyzer

`authoritative_physical_acoustic_stream_summary.py` reconstructs cause → emission → LPS ref.
Progress = scanned record count (honest; not fabricated wall-clock %).

## Explicit non-goals (deferred)

Audio playback, Hz mapping, amplitude/SPL calibration, Observer acoustic probe, 3D/occlusion/reverb, semantic ambient tracks, new sources.
