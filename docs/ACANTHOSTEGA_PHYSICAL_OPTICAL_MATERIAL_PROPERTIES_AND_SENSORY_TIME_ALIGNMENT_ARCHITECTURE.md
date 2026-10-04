# ACANTHOSTEGA — PHYSICAL OPTICAL MATERIAL PROPERTIES AND SENSORY TIME ALIGNMENT ARCHITECTURE

**Status:** architecture / evidence only — no optical model implementation  
**Roadmap position:** Physical Optical Substrate (before FIRST_HABITABLE_VOLUMETRIC_RUN_V1)  
**Date:** 2026-10-01  
**Repo freshness:** `main` @ `5d0f14c`, dirty tree preserved (~442)

---

## 0. Core principle (authoritative causal direction)

```
physical light sources
  → propagation through physical space
  → interaction with material optical properties
  → light field at organism receptors
  → organism phenotype / transduction
  → cognition-accessible visual values
```

**Forbidden reverse:** material semantic label → authored display color → organism “sees” that color.

Researcher rendering and organism vision may share physical optical **authorities**, but researcher pixels must never become sensory input. Existing Observer RGB / elevation false-color / SOVV status colors remain **diagnostic**.

---

## PART A — CURRENT OPTICAL AUTHORITY AUDIT

### 1. Freshness and scope

| Item | Value |
|---|---|
| cwd | `<repository-root>` |
| branch / HEAD | `main` / `5d0f14c` |
| dirty-tree | preserved (~442) |
| public Beta 4 builder | `ACANTHOSTEGA_BETA4` cumulative (VW1–VW7, Free-Space, agent relative_z, Analyzer) |
| VW1–VW7 | Occupancy authority → support/contact → separation → deposition → exertion bridge → VW6 geometric vision → VW7 observer camera |
| VW6 vision | 3D distance + occupancy LOS; preserves near-field illumination assumptions |
| Observer optical paths | WorldMap false-color, SOVV false-color status, occupancy views; labelled researcher |
| Cognition visual schemas | `exo_*` / spatial near-field floats via `accessible_observation` |
| Live run | not mutated; 0 simulated ticks for this audit |

See also: `results/.../PRE_IMPLEMENTATION_AUTHORITY_MAP.md`.

### 2. Complete current visual chain

Documented in `CURRENT_VISUAL_CHAIN.md`. Summary:

| Stage | Input authority | Output | Tick/seam | Class | Agent access | Observer poll alters? |
|---|---|---|---|---|---|---|
| Terrain / body / RO optical coeffs | world/body/object state | surface_response, optical_response | world tick | ABSTRACT_SENSOR_CHANNEL | via exo_* only | No |
| Illumination cycle | tick | illumination_intensity | begin_tick sample | ABSTRACT ambient | multiplies exposure | No |
| Candidate / LOS | poses + VW1 | candidates + los flag | begin_tick | PHYSICAL_GEOMETRY | los not exposed | No |
| Receptor / phenotype | candidates × illum × gain | exo_* | begin_tick | ABSTRACT_SENSOR | Yes | No |
| Cognition | obs dict | decision | begin_tick OO=T | — | Yes | No |
| Researcher / Observer | traces + RGB maps | pixels | poll/frame | DISPLAY_ONLY | No | No (read-only) |

### 3. Inventory classification (names ≠ physics)

| Property / alias | Classification |
|---|---|
| `optical_radius` | PHYSICAL_GEOMETRY (also dual-used for grasp reach) |
| `optical_response` / surface_optical (c0,c1,c2) | ABSTRACT_SENSOR_CHANNEL (anonymous; independent of composition) |
| `surface_response` | ABSTRACT_SENSOR_CHANNEL |
| body optical response | ABSTRACT_SENSOR_CHANNEL |
| surface optical coating / soft-OR compose | ABSTRACT_SENSOR_CHANNEL + researcher receipt; named `optical_mix` NOT_ESTABLISHED |
| `illumination_intensity` | ABSTRACT_SENSOR_CHANNEL (global cycle; not a light-source field) |
| RO `composition` | MATERIAL_COMPOSITION_PROXY |
| emissive/source terms | NOT_ESTABLISHED |
| opacity / transmission / absorption / reflectance | NOT_ESTABLISHED as physical authorities |
| VW6 visibility / LOS / eye–target | PHYSICAL_GEOMETRY (receipts RESEARCHER_DIAGNOSTIC) |
| Observer RGB / false-color / FPV | DISPLAY_ONLY_FALSE_COLOR |
| SOVV glyph color | RESEARCHER_DIAGNOSTIC / DISPLAY_ONLY_FALSE_COLOR |
| VW7 pixels | RESEARCHER_DIAGNOSTIC (`drives_organism_vision: False`) |
| Tiktaalik LEGACY spatial | LEGACY_COMPATIBILITY (Beta4 still RICH discrimination) |
| Semantic COLOR/SEE | NOT_ESTABLISHED (intentionally absent) |

**Taxonomy note:** Do not promote anonymous optical coefficients to PHYSICAL_OPTICAL_AUTHORITY merely because they gate receptor exposure; physical optical authority begins with sources × material response under transport (O1–O3).

### 4. Current lighting reality

| Mechanism | Status |
|---|---|
| Physical light sources | NOT_ESTABLISHED |
| Directional / point emission | NOT_ESTABLISHED |
| Ambient illumination | Abstract global cosine cycle only |
| Shadows | NOT_ESTABLISHED (LOS occlusion ≠ shadowing of a light) |
| Wavelength / spectral bands | Anonymous channels only; not SI λ |
| Reflection / absorption / transmission / scattering | NOT_ESTABLISHED |
| Occlusion | Geometry LOS (VW6) — not optical transport |
| Distance falloff | Phenotype `distance_k` on coefficients |
| Surface orientation / BRDF | NOT_ESTABLISHED |
| Exposure / adaptation | Phenotype gain/sat only |
| Temporal integration | NOT_ESTABLISHED (sample at observation) |

---

## PART B — PROPOSED PHYSICAL OPTICAL SUBSTRATE

### 5. Selected initial model

| Option | Verdict |
|---|---|
| A. Existing anonymous channels, no transport | Insufficient — darkness/occlusion of *light* undefended |
| B. Scalar illumination + reflectance | Minimal but loses anonymous spectral distinction already latent in c0..c2 |
| **C. Small anonymous spectral-band light field** | **SELECTED** |
| D. Full SI radiometry | Premature; false precision |
| E. Renderer-derived RGB | Forbidden causal direction |

**SELECTED_OPTICAL_SUBSTRATE = C** — anonymous spectral-band irradiance field (non-SI) × material reflectance per band, with direct transport and occupancy occlusion.

Why C: reuses band arity already present in optical_response; makes light/dark and material alteration meaningful; extensible to calibration without rewriting cognition key shapes; never uses VW7 pixels.

### 6. Material optical profile V1

**Include in V1 (consumers exist in O3/O4):**
- anonymous spectral reflectance `R[b]` per band (same B as light field)
- optional scalar opacity / absorption for transmission path length through occupied material (only if O3 implements transmission stubs; else defer absorption until a consumer exists)

**Defer (no V1 consumer):** transmission spectrum, emissivity, scattering/albedo beyond reflectance, roughness/specularity, IOR/refraction, fluorescence, polarization.

**Attachment:** versioned profile on **material components**; resolve to **mixture profile** at occupied cells / deposit / ResourceObject surface; exposed-surface interaction uses **resolved surface material**.

**Mix:** amount-weighted or volume-weighted mix of `R[b]` (document rule in O1); quantity affects path length / opacity only when transmission is enabled.

**Detach / COMBINE / deposition:** inherit source profile; COMBINE mixes profiles; deposition writes resolved profile onto deposited material; legacy objects without profile → explicit `UNKNOWN_PROFILE` fallback (neutral R or zero contribution — pick one rule and stamp).

**Serialize/restore:** profile id + version + bands in world/material snapshots; generation counter for cache invalidation.

### 7. Exposed-surface authority

```
VW1 occupied interval
  → exposed boundary / surface facets (top, pit wall, cavity, vertical face)
  → material at boundary (resolved profile)
  → surface normal
  → optical response to incident light
```

Do **not** shade internal prism volume as exposed.

Participation:
- Detached ResourceObjects / bodies / held objects: object surface samples (existing optical_radius geometry) + profile
- Deposits not yet collision bodies: still contribute if they have material authority and exposed facets; else deferred with stamp
- Absent profile: UNKNOWN_PROFILE rule

**Researcher SURFACE 3D:** may share O2 geometry as **passive consumer**; need **not** precede O4 if O2 provides the simulation authority; SURFACE 3D UI can precede organism integration for researcher tooling (**yes, can precede**).

### 8. Light-source authority (smallest V1)

**Include:**
1. One global directional source (spectral output `S[b]`, direction, optional on/off)
2. Optional global diffuse environment term `E[b]` **explicitly labelled** (not a hidden fill for caves)

**Defer:** arbitrary point/area lights, emissive materials, organism emitters, thermal IR — unless a single debug source is needed for probes (fixture-only, not public science claim).

**State / update:** source state on world; update when configured (constant or slow schedule); spatial: directional has no origin; diffuse is uniform.

**Energy ledger:** V1 is **abstract physical-light authority (non-SI)** — does **not** participate in conserved mechanical energy ledger.

### 9. Propagation and interaction (minimal causal law)

For each band b at sample point / surface:
- visibility(source → point) via occupancy occlusion (reuse VW1/VW6 LOS primitives where applicable)
- irradiance ∝ S[b] × visibility × distance_falloff × max(0, n·L) for directional
- + E[b] if environment enabled
- reflected toward receptor ≈ irradiance × R[b] (Lambertian-class abstract; no multibounce)
- multiple sources: linear sum
- darkness: zero when no visible source and E=0
- periodic XY + absolute Z consistent with VW1
- clip to finite non-negative bounds

**Intentionally absent in V1:** multi-bounce GI, volumetric scattering, refraction, caustics, cave indirect lighting, participating media.

### 10. Organism receptor boundary

Preserve:
```
physical optical field ≠ receptor response ≠ cognition exo_* ≠ Observer display
```

VW6 receptor **geometry** (eye pose, FOV, LOS) can consume the new field **without changing public cognitive key names** if exo_* remain anonymous band aggregates; **numerics will change**.

Specify in O4:
- pre-phenotype physical sample at eye (band irradiance / incoming)
- phenotype transfer (gain, sat, existing distance terms may be retargeted)
- clip/adapt as phenotype only
- receptor integration window: V1 = single observation tick (delay 0 unless later revised)
- tick authority: RS = OO = decision_tick for vision unless delay introduced
- anonymous band compatibility with profile bands
- legacy fallback: if optics off → current near-field path
- researcher transformation traces only
- privacy: no material IDs, source IDs, RGB, XYZ, blockers, VW7

### 11. Researcher rendering relationship

**A. Physical optical audit view (O6):** authoritative bands, irradiance, reflectance, visibility.  
**B. Aesthetic world rendering:** tone-map / palette for humans — labelled false-color.

Required labels: authoritative physical bands; transformed false color; exposure/tone mapping; unavailable physical optics; legacy display fallback.

Researcher exposure/camera/gamma/palette **never** enter simulation or cognition.

---

## PART C — CROSS-MODAL TEMPORAL ALIGNMENT

### 12–14. Inventory, semantics, hazards

See `MODALITY_TIMING_MATRIX.md`.

Proposed contract stamps:
`PHYSICAL_EVENT_TICK`, `FIELD_STATE_TICK`, `RECEPTOR_SAMPLE_TICK`, `ORGANISM_OBSERVATION_TICK`, `MOTOR_DECISION_TICK`, `ACTUATION_TICK`, `CONSEQUENCE_TICK`, `RESEARCHER_PRESENTATION_TICK`.

Answers:
- Vision delay today: **0** (sample of committed world at begin_tick T)
- Hearing **LPS transport** delay: **≥1** (emit te=T → arrive A=T+1 → observe T+1; default max delay 4)
- Hearing **A3→A5 / OATT** phenotype delay: **0** (`causal_delay_ticks` expects 0) — **not** the same as LPS delay
- Cognition: single observation boundary at OO=T — stamp-synchronous, not causally contemporaneous across modalities
- Cross-modal combine without PE metadata: **yes, currently possible → risk**
- OATT compatible with LPS reception→observation: **yes**; not a vision↔audio PE envelope
- Analyzer/V3: consequence T→T+1; LPS arrivals under consequence of T feed **next** observation
- Motor: EBAE → ETC → VIA → LPS; attribution via decision_tick / event_refs; still separate from sensory PE stamps
- Extra hazards: `world.tick ∈ {self.tick, self.tick+1}` desync can zero hearing; `_lps_body_id` re-bind on restore; illumination cache may lag one finish cycle

### 15. Required alignment contract (before FIRST_HABITABLE)

Minimal implementation (O5):
- shared observation envelope OR linked modality receipts
- per-modality PE / RS / OO ticks + causal_delay
- runtime generation + agent/body identity
- missing vs true-zero
- deterministic ordering of modalities in envelope
- snapshot/restore of envelope + LPS + vision sample policy
- Analyzer reconstruction by PE and RS when interpreting “what was sensed when”
- cognition privacy (no researcher clocks)
- bounded history

Do **not** merge modalities into a semantic world-perception vector.

---

## PART D — ROADMAP DECISION

### 16. Implementation slices

See `ROADMAP_DEPENDENCY_GRAPH.md`.

**Recommended order:** O1 → O2 → O3 → O5 ∥ O4 → O6 → O7  
(O5 must complete before O7; preferred before or with O4.)

### 17. FIRST_HABITABLE gate (objective)

Minimum:
- coherent public Beta 4 model
- reachable agent-selectable manipulators
- truthful Analyzer
- exposed physical world geometry (O2)
- material optical profiles (O1)
- ≥1 physical illumination authority (O3)
- organism receptor integration (O4)
- explicit vision/audio temporal alignment (O5)
- snapshot/restore parity; two-agent parity
- Observer visibility of audit optics (O6 recommended)
- bounded performance; no researcher-state leakage

**Not required:** photorealism, GI, SI radiometry, caves, volumetric atmosphere.

### 18. Performance implications

| Cost center | Estimate / rule |
|---|---|
| Exposed-surface extraction | Cache on VW1 occupancy generation/checksum |
| Light visibility | Candidate subsets / receptor rays — **not** all 3072 prisms per agent/tick by default |
| Receptor sampling | Per-eye × bands × visible candidates |
| Per-band interaction | O(B) with small B (e.g. 3) |
| Observer rendering | Decoupled; poll-rate limited |
| Analyzer traces | Bounded receipts; generation-scoped |

Invalidation authorities: VW1 occupancy generation; material-profile generation; light-source state; receptor pose/tick.

---

## Verdict

**F. OPTICAL_AND_TEMPORAL_SLICES_REQUIRED_IN_STAGED_SEQUENCE**

- FIRST_HABITABLE must **not** begin before physical optics **and** temporal alignment contract.
- Researcher SURFACE 3D **can** precede organism optical integration.
- Physical optics requires Free-Space/VW **occupancy** for occlusion honesty where volumes exist; does **not** require volumetric-world V3 caves/ceilings.
- Does **not** require SI wavelength/metres/seconds/watts/lux.
- First scientifically defensible “organism saw it”: **O4**.
- First vision↔hearing temporally comparable: **O5**.
- Next slice: **O1 PHYSICAL_OPTICAL_MATERIAL_PROFILE_V1**.
- Following roadmap seam: O2 → O3 → O5/O4 → O6 → O7.
