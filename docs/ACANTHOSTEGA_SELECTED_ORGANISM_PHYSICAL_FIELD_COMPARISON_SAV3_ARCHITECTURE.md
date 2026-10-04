# SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3 — Architecture Audit

**Status:** Architecture / authority / scientific-comparison only.  
**IMPLEMENTATION_STARTED = NO** · **TOTAL_SIMULATED_TICKS = 0**  
**Workspace (future UI):** HEARING section `PHYSICAL FIELD → ORGANISM RECEPTORS`  
**Capability (future):** `selected_organism_physical_field_comparison`  
**Authority:** `RESEARCHER_UI_ONLY` / observational receipts — **not** a physical mechanism or preset.

## Purpose

Design a scientifically honest researcher comparison of the **real** sensory path:

```
A0 physical emission
 → A1 LPS wavefront transport
 → A2 physical field / acceptance at selected body
 → A3 raw left/right receptor reception
 → A4 phenotype scale + clip
 → A5 exact osc_l_0…5 / osc_r_0…5 (organism-accessible, pre-cognition)
```

SAV3 must **record and display** that transformation. It must not replace LPS, recompute a second acoustic reality, add playback, or claim subjective experience.

## Central authority verdict (short)

| Stage | Current status |
|-------|----------------|
| A0 | Authoritative emissions + stream refs |
| A1 | Authoritative active LPS wavefronts |
| A2 body-centre mono | Authoritative **per-contributor** in reception receipts (gate/threshold); **no** retained summed mono sensory channel |
| A3 raw L/R | Authoritative **runtime** in `LocalSignalState.auditory`; **transient** live; serialized in LPS snapshot; **not** frozen into SAV1 history |
| A4 | Deterministic transform in `auditory_fragments`; params stamped in SAV1 Section B |
| A5 | Authoritative organism-accessible; frozen by SAV1 receipt |

**Frozen historically today:** A5 (SAV1, capacity 128).  
**Not frozen as same-tick comparison history:** A3 vectors (except current LPS `auditory` buffer + snapshot).

## A2 definition verdict

**Do not invent body-centre mono as the sole sensory A2.**

The real receiver path:

1. Tests wavefront crossing and threshold at **body centre** (`body.x`, `body.y`).
2. On accept, accumulates **separate** left/right receptor energies using source→receptor distances.

**Recommended SAV3 A2 split:**

- `A2_ACCEPTANCE_FIELD` — body-centre mono per accepted contributor (from `LOCAL_PHYSICAL_SIGNAL_RECEPTION`); explains gate/threshold; **not** what cognition hears.
- `A3_RAW_LEFT` / `A3_RAW_RIGHT` — summed pre-phenotype receptor vectors from `st.auditory` (exact sensory preimage of A5).

If UI needs one “physical at body” column, label it **ACCEPTANCE / GATE FIELD** with authority badge, never as organism input.

## Passive probe

**PASSIVE_PROBE_AT_BODY_EQUIVALENCE = PARTIAL_EQUIVALENT** (static body-centre gate field only) / **DIFFERENT_GEOMETRY** vs A3.  
**PASSIVE_PROBE_MAY_SERVE_AS_SAV3_AUTHORITY = NO.**

## Capture recommendation

**Option B — new researcher-only trace** (preferred):

1. `ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1` — capture A3 (and optional A2 acceptance aggregate / contributor caps) at the real receiver seam.
2. `SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3_V1` — same-tick link to SAV1 A5 + loss metrics.

Do **not** extend SAV1 Section A with A3. Do **not** use probe-as-body. Do **not** invert A5→A3.

## Implementation gate

**READY_WITH_CONSTRAINTS**

Constraints: A3 must be observationally captured (or proven parity reconstruction with heading); tick alignment documented (`reception_tick` = `observation_tick`, `causal_delay_ticks` = 0 for A3→A5); privacy split; bounded history; no playback; no LPS/phenotype change.

## Evidence

`results/acanthostega_selected_organism_physical_field_comparison_sav3_architecture/`

## Preservation

No change to LPS, receptors, phenotype, A5, SAV1/SAV2, C1, HEARING engines, cognition, presets, or live run. This audit edits **docs/results only**.
