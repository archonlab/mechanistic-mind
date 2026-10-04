# SELECTED_ORGANISM_AUDITORY_OFFLINE_RECONSTRUCTION_SAV4A_V1

**Slice:** `SAV4A_SAVED_EVIDENCE_NORMALIZATION_AND_DETERMINISTIC_SCHEDULE_V1`  
**Capability:** `selected_organism_auditory_offline_reconstruction`  
**Profile:** `SAVED_EVIDENCE_NORMALIZATION_AND_DETERMINISTIC_SCHEDULE_SAV4A_V1`  
**Authority:** `RESEARCHER_DERIVED_READ_ONLY_OVER_SAVED_AUTHORITATIVE_EVIDENCE`

## Purpose

Read-only reconstruction over **saved** scientific evidence:

1. discover accepted evidence files
2. normalize auditory records into one canonical offline timeline
3. classify authority and completeness honestly
4. detect gaps, duplicates, generation boundaries, legacy evidence
5. derive a deterministic SAV2-compatible sonification **schedule** (data only)
6. expose in Analyzer + HEARING workspace

**Not in this slice:** audio player, Web Audio, PCM/WAV, export, physics restore, LPS re-execution.

## Authority hierarchy

OATT exact trace → SAV1 exact A5 → classified legacy osc_l/r (12 finite channels) → Unavailable.

## Integration

- Backend: `mechanistic_mind/physical_system/selected_organism_auditory_offline_reconstruction_sav4a.py`
- Analyzer: `.../selected_organism_auditory_offline_reconstruction_sav4a_summary.py` + pipeline hook
- Observer HEARING: `SelectedOrganismAuditoryOfflineReconstructionPanel` after SAV3
- Privacy: SAV4A tokens in `FORBIDDEN_TOKENS`

## Evidence

`results/acanthostega_selected_organism_auditory_offline_reconstruction_sav4a_v1/`

## Next seam

`SAV4B_SELECTED_ORGANISM_AUDITORY_OFFLINE_PLAYER_V1` (do not start here)
