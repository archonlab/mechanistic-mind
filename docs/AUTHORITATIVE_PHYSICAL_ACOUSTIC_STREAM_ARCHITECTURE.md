# AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM — Architecture

## Status

**Architecture audit complete.** Implementation slice delivered as
`AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_CONTRACT_V1` — see
`docs/ACANTHOSTEGA_AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_CONTRACT_V1.md`.

**No playback / Hz / probe in that slice.** Stream is read-only L1+L2 capture only.

## Verified tip / display parent

| Field | Value |
|-------|-------|
| Physical tip | `ACANTHOSTEGA_BETA4_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION` |
| Free-Space | V1A–V1D complete (V1C supplies vertical impact → LPS) |
| Display | `OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1_1` (+ fall trails) |
| Acoustic UI today | World Map **visual** physical-sound-source markers only |

## Central finding

The simulation already has **one physical signal reality** for all impact/contact/oscillator emissions:

```
physical cause → measured response energy → UNIFORM_BROADBAND_V1 bands
  → emit_local_physical_signal (x,y)
  → LPS UNIFORM_SIGNAL_MEDIUM_V1 wavefront (XY torus)
  → pose-at-arrival body receivers
  → summed anonymous osc_l_k / osc_r_k
  → cognition (anonymous only)
```

There is **no** human-audible playback, **no** Hz mapping, **no** semantic `PLAY_*` path, and **no** Observer-only physical source.

## Authority layers (adopted)

| Layer | Exists now? | Authority |
|-------|-------------|-----------|
| L1 Physical source event | YES (per-mechanism receipts) | RESEARCHER-AUTHORITATIVE RECEIPT |
| L2 Propagation state | YES (`PhysicalSignalEmission` / LPS active set) | AUTHORITATIVE SIMULATION STATE |
| L3 Listener-local physical field | PARTIAL (body auditory slots only) | AUTHORITATIVE at registered bodies |
| L4 Organism transduction | YES (`auditory_fragments` → `osc_l_*`/`osc_r_*`) | AGENT-ACCESSIBLE SENSOR |
| L5 Observer playback transduction | **NO** | future TRANSDUCTION_ONLY |

## One-reality contract (normative)

1. One physical source event may feed many receivers via LPS.
2. Agent hearing and future Observer playback derive from the **same** source/propagation reality.
3. Observer playback never injects a source into LPS.
4. Playback settings never modify LPS, receipts, or cognition.
5. Selected-organism playback never modifies organism receipts.
6. Transformed playback never changes authoritative bands/energy.
7. UI mute/volume = local output only.
8. No semantic ambient track is treated as physical world sound.

## Recommended stream schema

`AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_V1`

Read-only export / bounded capture of L1 (+ pointers into L2), versioned, researcher-only.  
**Not** a waveform. **Not** playback.

## Smallest next implementation slice

`AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_CONTRACT_V1`

- Serialize/capture bounded source-event stream from existing receipts + LPS emission IDs.
- No AudioContext, no Hz, no probe, no playback UI.
- Optional hardening in same or adjacent slice: add explicit `FORBIDDEN_TOKENS` for B/O and O/O impact acoustic mechanism ids (parity with vertical/LPS/contact lists). Treat legacy OSC_BANDS as non-authoritative when LPS is active.

Then: passive Observer acoustic probe → ORIGINAL (after frequency mapping) → SELECTED ORGANISM VIEW → TRANSLATED.

## Blocker for ORIGINAL / HUMAN-AUDIBLE

`PHYSICAL_FREQUENCY_MAPPING = NOT_ESTABLISHED`  
Anonymous bands ≠ Hz. Oscillator `frequency` is normalized \(f \in [0,1]\), not SI frequency.

## Docs in this pack

See `results/authoritative_physical_acoustic_stream_architecture/`.
