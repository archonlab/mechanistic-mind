# Acanthostega Sensory Modality Temporal Alignment Contract V1 (O5)

## Identity
- **Schema:** `SENSORY_MODALITY_TEMPORAL_ALIGNMENT_CONTRACT_V1`
- **Capability:** `sensory_modality_temporal_alignment`
- **Profile:** `PHYSICAL_EVENT_RECEPTOR_OBSERVATION_TICK_ENVELOPE_O5_V1`
- **Authority:** `RESEARCHER_AND_CAUSAL_METADATA_OVER_EXISTING_MODALITY_TIMING`

O5 is cumulative researcher-only metadata on public Acanthostega Beta 4. It does **not** change organism-accessible sensory numerics, cognition schema, LPS transport, O4 visual values, A3/A4/A5/`osc_l/r`, motor selection, or physics.

## Purpose
Allow vision, hearing, body/support, and motor consequences to be compared without pretending they are instantaneous or sampled at the same physical time.

## Vocabulary
| Field | Meaning |
|---|---|
| `physical_event_tick` | Authoritative physical cause tick (emission, contact, landing, …). Static light: `NOT_APPLICABLE` (no fabricated emission). |
| `field_state_tick` | Field / medium evaluation stamp (LPS reception, optical generations/version). |
| `receptor_sample_tick` | Receptor buffer sample (O4 receptor; A3 auditory). |
| `organism_observation_tick` | Cognition-bound observation dictionary tick. |
| `motor_decision_tick` | Selected action / decision tick. |
| `actuation_tick` | EBAE / manipulator actuation tick. |
| `physical_consequence_tick` | ETC / contact / material consequence tick. |
| `researcher_presentation_tick` | Observer/Analyzer display tick — **never** organism experience authority. |
| `causal_delay_ticks` | Seam-specific delay; never copied across seams. |
| `availability` / `true_zero` / `missing_reason` | Distinguish true zero from missing. |

Missing authority stays `NOT_AVAILABLE` / `MISSING_*` — never copied from another seam.

## Alignment envelope
Read-only per-agent envelope finalized at the authoritative organism observation seam
(`_capture_selected_organism_auditory_boundary` → `_finalize_sensory_modality_temporal_alignment`),
after SAV1/OATT capture when applicable.

Structure: `observation_identity` + `vision` + `hearing` + `body_support` + `motor_context` + `alignment_status`.
References existing modality receipts; does not copy numeric sensory payloads into cognition.

## Vision (O4)
- `visual_causal_delay_ticks=0` when field and receptor share the scientific observation tick.
- Static source version ≠ sample tick; no fabricated emission events.
- Missing O4 trace ≠ darkness.

## Hearing
Two delays kept distinct:
1. `source_to_receptor_propagation_delay_ticks` — LPS transport (`>=1` when established)
2. `receptor_to_observation_delay_ticks` — OATT A3→observation (may be 0)

OATT zero delay **never** overwrites LPS transport delay.
Silence = available all-zero receptor sample; absent evidence = `MISSING_*`.

## Motor causal links
Only when explicit receipt refs exist:
`observation_tick → motor_decision_tick → actuation_tick → consequence_tick`
Adjacent ticks alone are not causal proof.

## Snapshot / restore
Restore loads researcher history only; does not create live envelopes or replay reception.
Next genuine observation produces exactly one new envelope. Runtime generations never merge.

## Observer / Analyzer
Researcher-only temporal alignment panel with labels:
- `SCIENTIFIC TICKS · NOT WALL TIME`
- `MODALITIES MAY REPRESENT DIFFERENT PHYSICAL EVENT TIMES`
- `OATT DELAY IS RECEPTOR→OBSERVATION, NOT LPS TRANSPORT`

Analyzer reconstructs chains without claiming same observation ⇒ same physical time.

## Privacy
Timing/provenance metadata is researcher-only unless already part of organism perception.
