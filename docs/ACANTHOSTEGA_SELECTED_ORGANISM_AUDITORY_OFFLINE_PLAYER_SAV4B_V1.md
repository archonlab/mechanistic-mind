# SELECTED_ORGANISM_AUDITORY_OFFLINE_PLAYER_SAV4B_V1

**Capability:** `selected_organism_auditory_offline_playback`  
**Profile:** `SAV4A_SCHEDULE_TRANSLATED_STEREO_OFFLINE_PLAYER_SAV4B_V1`  
**Authority:** `RESEARCHER_DERIVED_PLAYBACK_OVER_SAV4A_SCHEDULE`

## Purpose

Finite offline player over **SAV4A deterministic schedule only**. Translated stereo monitor via existing SAV2 carriers/gain/envelope/timing. Not physical audio, not organism phenomenology, not simulation/LPS replay.

## Ownership

`OFF | LIVE_C1 | LIVE_SAV2 | OFFLINE_SAV4B` — mutually exclusive audible owners.

## Input

SAV4A schedule items (amplitudes already mapped). Does not parse OATT/SAV1/legacy/stream/probe.

## Gaps

Missing evidence is not silence. Playback stays within contiguous segments; end may report `GAP_BOUNDARY`. True recorded zeros may silence normally.

## Timing

`canonical_seconds_per_tick = 0.05` — playback mapping, non-physical. Bounded lookahead (`SCHEDULED_HORIZON_SECONDS`).

## Not in SAV4B

PCM render, WAV export, OfflineAudioContext dump, live SAV2 queue enqueue.

## Next seam

`AUDIO_TOOLING_PAUSE_AND_RETURN_TO_CORE_WORLD_ROADMAP`
