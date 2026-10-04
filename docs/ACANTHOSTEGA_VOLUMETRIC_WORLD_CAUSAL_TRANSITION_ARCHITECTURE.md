# VOLUMETRIC_WORLD_CAUSAL_TRANSITION_ARCHITECTURE

**MODE:** Repo-first architecture / scientific transition audit  
**IMPLEMENTATION:** NO · **TOTAL_SIMULATED_TICKS:** 0  
**Recorded:** 2026-09-30T20:23:57Z · branch `main` · HEAD `5d0f14cd7968b4d5b190796a2494d348a0e10f48`  
**Dirty tree:** preserved intentionally (~373 entries).

---

## 1. EXECUTIVE CONCLUSION

**YES — the repository is ready for a staged transition to one volumetric world**, under constraints.

What already exists (verified in code, not only docs):

| Capability | Status |
|------------|--------|
| Body/object physics-Z free-space motion (FGG) | **Present** |
| Free-space support state + PE mutex (V1A) | **Present** |
| Vertical landing contact (V1B) | **Present** |
| Per-XY procedural surface columns + layered subsurface | **Present** (not volumetric) |
| Conservative column→ResourceObject separation (WMT) | **Present** |
| Detached material placement on support | **Present** |
| Explicit deposition mutating column elevation | **NOT yet** (`terrain_effects_applied=False`) |
| Cavities / overhangs / multi-Z occupancy | **Explicitly not modelled** |
| Vision / LPS acoustics in XYZ | **XY-only** |

The transition is **not** “add decorative Z”. Free-space body Z already exists. The blocking ontology is **single-valued terrain surface per XY** plus **2.5D contact/support**. One final physics authority must remain; no parallel 3D runtime.

**FIRST_HABITABLE_VOLUMETRIC_RUN** is defined below. Ecology/living matter is an **extension seam**, included as **final optional slices after** physical habitability (excavation + cavities + locomotion + manipulation), not as foundational physics classes.

---

## 2. CURRENT WORLD AUTHORITY MAP

| Domain | Current authority | Dimensional assumption |
|--------|-------------------|------------------------|
| A. Spatial position | `PhysicalBodyState` / `ResourceObject` `x,y` + Phase-C `z,vz` | XY torus + independent physics-Z |
| B. Orientation | `theta` / `body_orientation` | **Planar yaw only** |
| C. Terrain geometry | `procedural_surface_columns` (`SurfaceColumnState`, sparse deltas) | **One `surface_elevation` per XY** + layers **down from surface** |
| D. Free space | FGG + V1A vs `support_z=h(x,y)` | Above heightfield ≠ volumetric free volume |
| E. Material occupancy | Column layers under surface; `material_at_depth` | Contiguous subsurface; `ABOVE_SURFACE` / `NOT_MODELLED` |
| F. Support | SES / CSG bilinear → `support_z` | Single upward-facing support sample |
| G. Gravity | FGG semi-implicit `a_z=−g` | Vertical integrator over heightfield contact |
| H. PE | V1A mutex: supported SES/CSG vs unsupported FGG | Two tokens, one active; not dual Z authorities fused incorrectly |
| I. Vertical motion | FGG integrate + V1B landing | Physics-Z free until contact with `support_z` |
| J. Horizontal motion | Existing dynamics + BNLT when grounded | XY; traction gated by `grounded` |
| K. Collision/contact | XY circles + optional Z-slab filter; landing 1D Z | No walls/ceilings/cavities |
| L. Resting contact | V1A rest gate + V1B rest PERSIST | Heightfield rest |
| M. Body extent | `vertical_half_extent` + horizontal radius | Slab + circle, not mesh |
| N. ResourceObject geometry | `collision_radius` horizontal; Z fields present | Probe/circle, not solid volume |
| O. Detached material | Separation → FREE RO + placement | Conserved object, not column |
| P. Held objects | Held kinematics + held-terrain clearance probe | Heightfield clearance |
| Q. Terrain failure/separation | `SEPARATE_SURFACE_COLUMN_SLICE` via WMT | Top-slice from column |
| R. Deposition | Explicit deposits overlay | **Does not** raise column elevation yet |
| S. Vision | `near_field_exteroception` Phase 4 | **2D angular/occlusion; not depth/3D** |
| T. Acoustics | LPS toroidal XY distance | Z on stream often NE; not in delay/attenuation |
| U. Env fields | Ecology/climate mostly separate | Not volumetric occupancy |
| V. Snapshot/restore | Body Z + column serialize | No voxel grid |
| W. Seeding | Column baseline seed + deltas | Deterministic columns |
| X. Analyzer/Observer | Elevation/free-space viz consumers | Must not become geometry authority |
| Y. Boundaries | `wrap_coord` XY torus | Z unbounded / no wrap |

**Critical split already present:** terrain **heightfield** `support_z` vs entity **physics-Z**. Do not invent a third shadow Z for rendering.

---

## 3. CRITICAL 2D / HEIGHTFIELD ASSUMPTIONS (only those that block)

1. **One surface elevation per XY** — forbids cavities, tunnels, overhangs, stacked free/occupied intervals.
2. **Layers measured down from local surface** with fixed lower datum — not arbitrary Z intervals of matter.
3. **Support = sample of upward heightfield** — no ceilings; walls only as horizontal XY collision if at all.
4. **Landing/contact normal ≈ (0,0,+1)** at heightfield — not arbitrary local surface orientation.
5. **Effector/held clearance = z − r − h(x,y)** — probe vs single surface.
6. **Pair contact = XY circle (+ optional vertical slab overlap gate)** — not volumetric solids.
7. **Spatial index / LPS / vision = XY** — coherent enough for first habitable run if deferred carefully; vision needs a **minimal** 3D interface before habitability claim.
8. **Deposition does not return mass to world column elevation** — conservation path incomplete for reintegration.
9. **Planar orientation only** — acceptable initially; full SO(3) not required for FIRST_HABITABLE.

Decorative Z / renderer-owned mesh / parallel 3D runtime: **rejected**.

---

## 4. TARGET AUTHORITY MODEL (minimum final ontology)

**One world simulation state** owns:

1. **Occupancy field** `O` — for each XY cell (or sparse chunk), a sorted list of **occupied Z intervals** with material composition/quantity (and future process/living flags). Free space = complement intervals. Cavities and overhangs are ordinary free intervals between occupied ones.
2. **Entity pose** — `(x,y,z)` + planar `theta` initially; extents for contact queries.
3. **Support/contact** — derived by querying `O` (and entity geometry), not a separate heightmap authority.
4. **Gravity / PE** — same FGG/V1A mutex pattern, but `support_z` / contact surfaces come from occupancy queries.
5. **Material transactions** — single WMT ledger: world occupancy ↔ detached ResourceObjects (and later living matter), conservative.
6. **Consumers** — Observer camera, Analyzer, vision, acoustics read `O` / poses; never write physics.

**Occupancy representation (chosen from repo-compatible candidates):**

**Primary proposal: sparse vertical interval columns** (generalize today’s `SurfaceMaterialLayer` stacks into **absolute Z intervals**, not depth-from-surface).

| Criterion | Why intervals win over dense voxels (now) |
|-----------|-------------------------------------------|
| Fits existing column + WMT slice ops | Direct evolution of PSC/separation |
| Cavities/overhangs | Multiple occupied intervals per XY |
| Conservation | Interval quantity/mass like current layers |
| 64×64+ performance | Sparse deltas (already the pattern) |
| Snapshot | Serialize sparse interval maps |
| Living matter seam | Composition + process tags on intervals |
| Collision/support queries | Interval vs point/AABB/sphere probes |

Dense voxels deferred. Hybrid chunking optional later as optimization, not new authority.

**Camera/render:** derive display meshes/markers from `O`; never authoritative.

---

## 5. MIGRATION ORDER

**Choice: C — repository-derived** (not pure A or B).

### Why not pure A
A assumes free-space XYZ is still ahead. **It already exists** (FGG + V1A + V1B). Building “3D contact” against a still-single-valued heightfield only deepens 2.5D.

### Why not pure B
B’s final step “then XYZ free-space bodies” is backwards here — bodies already leave the surface. Occupancy-first is right; free-space-last is wrong.

### Chosen order (C)

```
EXISTING: free-space body/object Z + heightfield support + column materials + WMT separation
    →
VW1  VOLUMETRIC_OCCUPANCY_AUTHORITY
    →
VW2  OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES
    →
VW3  CONSERVATIVE_VOLUMETRIC_SEPARATION
    →
VW4  CONSERVATIVE_VOLUMETRIC_DEPOSITION_REINTEGRATION
    →
VW5  EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE
    →
VW6  MINIMAL_VISION_3D_GEOMETRIC_INTERFACE
    →
VW7  OBSERVER_CAMERA_OCCUPANCY_CONSUMER
    →
VW8  FIRST_HABITABLE_VOLUMETRIC_RUN (integration gate)
    →
VW9  LIVING_MATTER_OCCUPANCY_EXTENSION_SEAM (post-habitability / optional final)
```

Acoustics: **preserve C1/SAV2/SAV3/SAV4A/SAV4B**; only ensure source/listener Z fields do not invent authority. Full 3D propagation **deferred** (not required for FIRST_HABITABLE).

---

## 6. FINITE IMPLEMENTATION ROADMAP

### VW1 — `VOLUMETRIC_OCCUPANCY_AUTHORITY_V1`
- **Purpose:** Replace single-valued surface+depth-from-surface as material truth with sparse absolute-Z occupied intervals per XY.
- **Replaces/generalizes:** `procedural_surface_columns` elevation+layers as *geometry authority* (migrate, don’t fork).
- **New authority:** `WorldOccupancyState` (name flexible) — interval map + composition; heightfield view becomes a **derived** “upper free-surface” query for migration.
- **Deps:** none beyond current PSC/WMT.
- **State:** sparse intervals; snapshot serialize/restore.
- **Physics:** none yet (queries may stub to old support).
- **Observer/Analyzer:** inventory + provenance of occupancy schema.
- **Preservation:** bit-stable derived surface height for legacy SES until VW2; cognition untouched.
- **Gates:** round-trip snapshot; same seed → same intervals; cavity = free interval between occupied; multi-Z per XY proven in fixtures.
- **Tests:** unit interval merge/split; conservation identity; wrap XY; 0 long runs.
- **Max ticks:** 0–5 for smoke only if needed.
- **Does not:** contact, excavation UX, vision, acoustics, voxels-as-graphics.

### VW2 — `OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES_V1`
- **Purpose:** Support and clearance from occupancy (floors; optional ceiling/wall probes).
- **Replaces:** SES/CSG as *sole* `support_z` authority; FGG/V1A/V1B consume new queries.
- **Deps:** VW1.
- **Physics:** free-space fall into cavities; stand on remaining matter; no free snap through ceilings if ceiling probe ON (minimal).
- **Preservation:** V1A PE mutex; no energy injection; rest gate semantics.
- **Gates:** remove support below → unsupported; cavity fall; stand on interval top; snapshot.
- **Does not:** full rigid-body; arbitrary mesh contact; vision.

### VW3 — `CONSERVATIVE_VOLUMETRIC_SEPARATION_V1`
- **Purpose:** Local failure/separation removes occupied quantity → ResourceObject via **existing WMT**.
- **Replaces:** top-slice-only column separation assumptions with interval-local separation.
- **Deps:** VW1–VW2.
- **Causal chain:** contact/work → resistance → separation → conserved detached matter → changed `O` → changed support.
- **Gates:** Δworld + Δobject = 0 mass/qty; geometry changes next-tick support; no DIG verb.
- **Does not:** fracture aesthetics; continuum soil.

### VW4 — `CONSERVATIVE_VOLUMETRIC_DEPOSITION_REINTEGRATION_V1`
- **Purpose:** Close the known gap: deposition returns matter into occupancy (not overlay-only).
- **Replaces:** `terrain_consequence=NOT_IMPLEMENTED` for reintegration path.
- **Deps:** VW1, VW3; reuse explicit deposition + WMT.
- **Gates:** object qty↓ occupancy qty↑; can create new support; conservation.
- **Does not:** fluid deposition; living growth.

### VW5 — `EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE_V1`
- **Purpose:** Wire existing effector/held contact + bounded effort + surface resistance into VW3/VW4 without semantic DIG.
- **Deps:** VW2–VW4; existing manipulator / exertion / resistance modules.
- **Gates:** motor→effector motion→contact→work→separation in one short probe; Acanthostega path.
- **Does not:** new motor vocabulary; Tiktaalik cognition rewrite.

### VW6 — `MINIMAL_VISION_3D_GEOMETRIC_INTERFACE_V1`
- **Purpose:** Enough geometric adaptation that spatial vision remains coherent with XYZ poses (elevation in sensor frame or occlusion by occupancy samples)—**no** TARGET_ABOVE semantics.
- **Deps:** VW1–VW2; `near_field_exteroception`.
- **Gates:** elevated targets not silently treated as coplanar when blocking; cognition still only gets existing channel classes.
- **Does not:** full depth buffer; cave semantics.

### VW7 — `OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1`
- **Purpose:** Camera/render consume occupancy; free/inspect camera; never write physics.
- **Deps:** VW1.
- **Gates:** visual cavity matches occupancy; Observer passivity tests.
- **Does not:** beautiful lighting; radiative ecology light (seam only).

### VW8 — `FIRST_HABITABLE_VOLUMETRIC_RUN_V1`
- **Purpose:** Integration milestone: one world where Acanthostega can locomote, excavate locally, transport, redeposit, leave persistent cavities that change support; cognition/hearing preserved; vision minimally coherent; snapshot deterministic.
- **Deps:** VW1–VW7.
- **Gates:** checklist in §14; short deterministic probes only.
- **Does not:** ecology; water; SAV4C; acoustic reverb/occlusion.

### VW9 — `LIVING_MATTER_OCCUPANCY_EXTENSION_SEAM_V1` (after habitability)
- **Purpose:** Composition/process tags + neighbor growth into free intervals; mass conservation; death→transportable matter. Not PlantEntity images.
- **Deps:** VW8.
- **Decision:** ecology **after** FIRST_HABITABLE, as explicit next seam—not blocking physical habitability.

**ROADMAP_SLICE_COUNT = 9** (VW1–VW9). Finite. No “12 more audits” required to start VW1.

---

## 7. PRESERVATION RISKS

| Risk | Mitigation |
|------|------------|
| Dual terrain authorities during migrate | Derived heightfield from occupancy only; kill date in VW2 |
| PE double-count | Keep V1A mutex; retarget support query only |
| Material loss on separation/deposition | Single WMT; VW3/VW4 conservation tests |
| Cognition leak | Occupancy researcher metadata in FORBIDDEN_TOKENS; no new sensory categories |
| Acoustics churn | No LPS rewrite; XY propagation stays until post-habitability |
| SAV4A/B / C1/SAV2/SAV3 | Semantically frozen; Z on stream remains non-authority |
| Tiktaalik/Acanthostega | Same world authority; presets differ, physics does not |
| Snapshot drift | Occupancy in planet/world serialize from VW1 |
| Vision regression | VW6 minimal; LEGACY mode until gate |

---

## 8. VALIDATION STRATEGY

- Unit + invariant + conservation + snapshot round-trip.
- Short probes (≤30 ticks absolute budget per slice if smoke needed; prefer 0).
- No 5k/10k/40k campaigns inside implementation slices.
- Geometry fixtures: cavity fall, overhang interval, support removal, redeposit support regain.

---

## 9. DEFERRED FEATURES

Sophisticated rendering · rich ecology (until VW9) · water · chemistry · fracture · granular continuum · acoustic reflection/reverb/occlusion · SAV4C/WAV · semantic DIG/CLIMB/FALL/CAVE gameplay · full SO(3) · parallel 3D runtime · decorative Z · dense voxel graphics authority.

**Light field:** document environmental light as future **field consumer of occupancy**, not renderer-only; do not implement radiative transport in VW1–VW8.

---

## 10. NEXT SAFE IMPLEMENTATION SEAM

**VW1 status:** implemented — see `docs/ACANTHOSTEGA_VW1_VOLUMETRIC_OCCUPANCY_AUTHORITY_V1_IMPLEMENTATION.md`.  
**VW2 status:** implemented — see `docs/ACANTHOSTEGA_VW2_OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES_V1_IMPLEMENTATION.md`.

**VW3 status:** implemented — see `docs/ACANTHOSTEGA_VW3_VOLUMETRIC_MATERIAL_SEPARATION_V1_IMPLEMENTATION.md`.  
**VW4 status:** implemented — see `docs/ACANTHOSTEGA_VW4_CONSERVATIVE_VOLUMETRIC_DEPOSITION_REINTEGRATION_V1_IMPLEMENTATION.md`.  
**VW5 status:** implemented — see `docs/ACANTHOSTEGA_VW5_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE_V1_IMPLEMENTATION.md` (VW4 physical reintegration trigger blocked; separation bridge complete).  
**VW6 status:** implemented — see `docs/ACANTHOSTEGA_VW6_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE_V1_IMPLEMENTATION.md`.  
**VW7 status:** implemented — see `docs/ACANTHOSTEGA_VW7_OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1_IMPLEMENTATION.md`.

**Exactly one next:**

`FIRST_HABITABLE_VOLUMETRIC_RUN_V1`

Integration milestone: locomote / excavate / transport / redeposit with persistent cavities; short deterministic probes (architecture VW8).
