# ACANTHOSTEGA — Radius-Aware Support Points G2B Architecture
**(architecture audit ONLY — no implementation)**

**Date:** 2026-09-28 (Europe/Oslo, UTC+2)  
**Repo:** `<repository-root>` (lab)  
**HEAD:** `5d0f14cd7968b4d5b190796a2494d348a0e10f48` (`main`)  
**Parent chain (landed):** G1 CSG → G2A body static traction → FOGF static twin  
**Immediate parent preset:** `ACANTHOSTEGA_PHASE_C_FREE_OBJECT_STATIC_TRACTION`  
**Roadmap slot:** `G2B_RADIUS_AWARE_SUPPORT_POINTS` (named in G2 arch + FOGF-static `NEXT_SAFE_SEAM`)  
**SCIENTIFIC_VALIDATION_RUN:** NO  
**Method:** static code inspection + freshness gate; Part-B sim ticks: **0** (budget reserved ≤150; not consumed).  
**Prior binding docs:** `docs/ACANTHOSTEGA_CONTINUOUS_SURFACE_PHYSICS_G2_ARCHITECTURE.md`, `docs/ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY_NORMALS_ARCHITECTURE.md`, SES / BNLT / FOGF / FGG docs.

---

## 0. Freshness gate

```text
pwd              = <repository-root>
branch           = main
HEAD             = 5d0f14cd7968b4d5b190796a2494d348a0e10f48
git status       = dirty working tree (pre-existing Phase-C / UI / mechanism files; no G2B physics edits this audit)
G1_CLOSURE       = PASS  (results/acanthostega_continuous_surface_geometry/G1_CLOSURE_EVIDENCE.md)
```

| Parent / flag | Evidence | Status |
|---|---|---|
| `G1_CLOSURE=PASS` | `results/.../G1_CLOSURE_EVIDENCE.md` + `.json` | **PASS** |
| `ACANTHOSTEGA_PHASE_C_CONTINUOUS_SURFACE_GEOMETRY` | `model/acanthostega.py` `PUBLIC_PRESET_CONTINUOUS_SURFACE_GEOMETRY`; `continuous_surface_geometry.py` | **PRESENT** |
| `BODY_STATIC_TRACTION_THRESHOLD_V1` | `body_static_traction_threshold.py` `PROFILE_VERSION`; preset `ACANTHOSTEGA_PHASE_C_STATIC_TRACTION` | **PRESENT** |
| `FREE_RESOURCE_OBJECT_STATIC_TRACTION_THRESHOLD_V1` | `free_resource_object_static_traction_threshold.py`; preset `ACANTHOSTEGA_PHASE_C_FREE_OBJECT_STATIC_TRACTION` | **PRESENT** |
| `ONE_PE_AUTHORITY = SES_DDA` | both static-traction modules + G2 arch + FOGF-static report | **CONFIRMED** |
| `NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO` | CSG / body static / FOGF static modules | **CONFIRMED** |
| `SUBGRID_MICRORELIEF_RAMP_V1` | `surface_elevation_support.py` `PROFILE_VERSION` | **PRESENT** |
| Current support still centre-query | `surface_support_height` / `support_z_for_entity(x,y)`; SES `ENTITY_RADIUS_FACE_SWEEP=NOT_IMPLEMENTED`; FOGF `FOOTPRINT_MULTI_CELL=NOT_IMPLEMENTED` | **CONFIRMED** |

```text
FRESHNESS_CHECK = PASS
```

### 0.1 Symbol / file inventory (real loci)

| Concern | Real file / symbol |
|---|---|
| Body footprint (material sites) | `physical_body/config.py` `PhysicalBodyConfig.footprint` default `((0,0))` BODY-1; BODY-2 plus in `default_physical_body2_config` |
| Body collision / contact radius | `physical_body_resource_object_contact.py` `BODY_CONTACT_RADIUS = 0.575`; `body_contact_geometry` |
| Body vertical half-extent | FGG: `body_vertical_half_extent = BODY_CONTACT_RADIUS` |
| ResourceObject collision radius | same module `CANONICAL_COLLISION_RADIUS = 0.25`; `ensure_object_collision_radius` |
| Optical radius | `resource_objects.py` `CANONICAL_OPTICAL_RADIUS = 0.45` (**not** support geometry) |
| Effector offsets / held pose | `physical_manipulator.py` `effector_world_xy`, `update_held_kinematics` |
| Continuous geometry oracle | `continuous_surface_geometry.py` `sample_surface_geometry`, `continuous_support_height`, `_bilinear_patch` |
| SES DDA | `surface_elevation_support.py` `centre_path_boundary_crossings`, `evaluate_path_transitions`, `commit_body_elevation_gate`, `commit_free_object_elevation_gate` |
| Body / object vertical support | `flat_ground_gravity.py` `integrate_vertical_entity`; SES `support_z_for_entity` → `surface_support_height` |
| Landing / grounded | FGG `grounded`, `landing_event`; `landing_sound=False` |
| Vertical contact filter | FGG vertical interval overlap in contact paths |
| Spatial contents | `spatial_contents.py` `multi_content_spatial_index` (2D broadphase) |
| Dynamic surface-column mutation | procedural columns + `conservative_surface_column_transfer`; SES `preflight_occupied_support_rise` |
| BNLT / FOGF N | `N = m_eff·g` / `m·g`; affinity at **single** support cell |
| Static traction | `body_static_traction_threshold.py`, `free_resource_object_static_traction_threshold.py` |

---

## 1. Geometry inventory + Q1–Q10

### 1.1 Inventory table

| Geometry channel | Authority today | Used for support height? | Radius-aware? | Notes |
|---|---|---|---|---|
| Cell `surface_elevation` | Procedural columns ± sparse delta | Via cell-centre / bilinear | No | Material authority |
| Continuous `h(x,y)` | Derived CSG bilinear (G1) | **YES** when CSG ON | No — single `(x,y)` | `HEIGHT_PHYSICAL_EFFECTS_ACTIVE=YES` |
| Analytic `n̂` | Derived same patch | No | N/A | `NORMAL_PHYSICAL_EFFECTS_ACTIVE=NO` |
| Body COM `(x,y)` | Dynamics | Query locus | Point | Default support sample |
| Body footprint cells | `PhysicalBodyConfig.footprint` | Material exchange / sites | Multi-cell optional BODY-2 | **Not** support disk |
| Body contact radius 0.575 | Contact / FGG half-extent | No for h-query | Circle in xy contacts | Best physical support radius candidate |
| Object `collision_radius` 0.25 | Contacts / FGG half-extent | No for h-query | Circle | Support radius candidate |
| Object `optical_radius` 0.45 | Vision / grasp reach | **Forbidden** for support | — | Distinct from collision |
| Effector xy | Manipulator forward±lateral | Held object follows effector | Offset from body | HELD support = holder policy, not free FOGF |
| SES centre-path DDA | Transition PE/block | Cell centres only | Explicitly NOT | `ENTITY_RADIUS_FACE_SWEEP=NOT_IMPLEMENTED` |
| FOGF affinity cell | Deposit mix at floor(cell) | Friction μ only | Single cell | `FOOTPRINT_MULTI_CELL=NOT_IMPLEMENTED` |

### 1.2 Answers Q1–Q10

| # | Question | Answer (repo-grounded) |
|---|---|---|
| Q1 | What is “the” body support point today? | Single COM query: `support_z_for_entity(world,cfg,body.x,body.y)` → `surface_support_height` → CSG bilinear `h` or discrete cell elevation. |
| Q2 | What is object support point? | Same centre query at `(obj.x,obj.y)`. FOGF affinity also single `resolve_support_cell`. |
| Q3 | Does body footprint define support? | **No.** Footprint is material/site geometry; support uses COM. BODY-1 is `((0,0))`. |
| Q4 | Collision vs optical for objects? | Collision 0.25 is contact/vertical half-extent; optical 0.45 is vision/grasp. Support must **not** use optical. |
| Q5 | Is SES radius-aware? | **No.** Centre-path DDA; face-sweep flagged NOT_IMPLEMENTED. |
| Q6 | Can single-point balance on a peak? | **Yes** — G2 B8 defect class; COM on a local max can look stable with no pitch/roll. |
| Q7 | Can a narrow pit be stepped over? | **Yes** — samples only at COM; pit between ring loci invisible today. |
| Q8 | WRAP? | CSG `_wrap_pose` + SES unwrap short path; any multi-sample must wrap each sample. |
| Q9 | Is aggregate normal active? | **No.** Inactive; G2B may compute diagnostic aggregate n̂ but must not activate forces. |
| Q10 | Does radius-aware **transition** need SES split first? | **Yes for replacing centre Δh / face-sweep PE.** **No** for a constrained G2B that keeps centre `support_z` + SES DDA and only adds multi-sample **classification** (+ optional PE-safe loss-of-support). See §10 / §22. |

---

## 2. Current support pipeline (real order)

Shared tick skeleton (G2 B1 / `runtime.py`): cognition → discrete MOVE → horizontal CoM (+ BNLT/static) → **SES elevation gate** → gentle rest → **FGG vertical** → manipulators → spatial reconcile → contacts/acoustics → LPS.

### 2.1 Body — grounded

1. Horizontal integrate (`integrate_com_translation`) with BNLT kinetic + optional static cone; uses **prior-tick** `body.grounded` (`body_normal_load_traction._is_body_grounded`).  
2. `commit_body_elevation_gate`: centre-path DDA; `support_height_at_cell` at crossing cell centres; MICRO_UPHILL debit `m·g·Δh` / LARGE block / micro-downhill dissipate / large-downhill → support lost.  
3. `integrate_body_vertical` → `integrate_vertical_entity(..., support_z=support_z_for_entity(x,y))`: gravity, inelastic clamp to **centre** `h`, set `grounded`.  
4. Contacts use xy radii + vertical intervals; no support acoustics on quiet grounded ticks (`landing_sound=False`).

### 2.2 Body — airborne

- `grounded=False` → BNLT/static **not eligible**; SES may still gate horizontal proposals; FGG integrates vz with no clamp until `z` meets support (SES lock: no free upward snap if `z0 < support`).

### 2.3 FREE_STATIC / FREE_MOVING grounded object

1. `plan_free_object_horizontal_step` + FOGF (+ static twin): affinity at **single** support cell; requires grounded.  
2. `commit_free_object_elevation_gate` (same SES PE authority).  
3. FGG vertical with centre `support_z`.  
4. Pair contacts after vertical.

### 2.4 Airborne FREE object

- No FOGF; vertical free-fall until support; landing sets `grounded` next-tick friction eligibility (FOGF comment: horizontal before vertical).

### 2.5 HELD

- `update_held_kinematics` snaps xy to effector; vertical via FGG held policy; **no** independent FOGF; foreign-body contact mediation separate. Support of holder body still centre-COM.

### 2.6 Experimenter / TwoAgent

- Experimenter column transfer/deltas: atomic + SES occupied support-rise preflight.  
- `TwoAgentRuntime`: one shared world; deferred manipulator/contact once per world tick; **same** PE/support authorities per slot — no special “human stability”.

**Seam fact:** Geometry for support is **not** a free-standing mid-pipeline stage; it is consumed inside SES gate + `support_z_for_entity` / FGG.

---

## 3. Representation alternatives A–E (+ hybrid)

| ID | Representation | Pros | Cons | Fit for G2B |
|---|---|---|---|---|
| A | Keep centre-only | Zero risk to SES PE | Does not close peak/pit defects; blocks honest G2D | Reject as terminal; OK as PE authority fallback |
| B | Morphologic footprint cells only | Reuses BODY-2 sites | BODY-1 trivial; cells ≠ collision disk; material≠support | Reject as sole support geometry |
| C | Collision-disk ring samples (centre + N on circle R) | Matches contact radii; WRAP-easy; bounded cost | Still discrete; no pitch/roll | **Select for body & object** |
| D | Dense disk / raster footprint | High fidelity | Perf + dense raster forbidden by G1 | Reject |
| E | Full radius face-sweep DDA replacing centre SES | True multi-cell transitions | **Rewrites SES energy law** | Defer to G2C+ coupled work |
| **Hybrid C⋆** | Ring samples for **classification / loss-of-support**; **authoritative support_z stays centre `h(x,y)`**; SES DDA unchanged | PE-safe; unblocks Observer/Analyzer + future N framing; no SES rewrite | Does not yet change resting height on edges | **SELECTED for first G2B slice** |

Body vs object may differ only by **R** (0.575 vs `collision_radius`), not by law family.

---

## 4. Support height definitions (analysis — no auto max/mean)

Evaluate candidate aggregates of sample heights `{h_i}` on flat / slope / peak / pit / ledge / edge / embankment / WRAP:

| Definition | Flat | Smooth slope | Peak | Pit | Ledge/edge | Embankment | WRAP | PE risk vs SES centre |
|---|---|---|---|---|---|---|---|---|
| **Centre only** (today) | OK | OK locally | False stable | Ignores pit | May miss drop | Misses shoulder | OK | Baseline (authority) |
| **max(h_i)** | OK | Sits high side | Worse false stable | Bridges pit | Climbs lip **for free** | Free lift | OK if wrapped | **HIGH — free ΔU** |
| **min(h_i)** | OK | Sits low side | Falls into void early | Sinks | Early LOS | Conservative | OK | Medium (penetration vs high samples unless SES blocks) |
| **mean(h_i)** | OK | Mid | Softens peak | Softens pit | Ambiguous | Ambiguous | OK | Medium — still ≠ SES centre debit |
| **Plane fit / least-squares** | OK | Good with n̂ | Needs ≥3 non-colinear | Unstable | Needs class split | Useful later | Careful | Needs G2D coupling |
| **Subset (lowest k / majority)** | Tunable | Tunable | Better LOS | Better | Edge class | Tunable | OK | Still PE if raises z |
| **Constraint:** `support_z ≤ h_centre` + LOS from class | Keeps PE | Keeps PE | Can force LOS on peak | Can force LOS | Edge→LOS | Safe | OK | **PE-safe** |

**G2B selection:** do **not** adopt max or mean as authoritative `support_z`.  
**Authoritative support height for FGG clamp / SES PE coupling remains centre `h(entity.x, entity.y)`.**  
Multi-sample heights feed **classification** and optional **loss-of-support** only. Replacing centre authority with an aggregate is **out of scope for first G2B** and requires SES decomposition (§10, §22).

---

## 5. Support-contact classification (non-semantic)

Names are mechanism tokens — **not** agent-facing terrain labels (no SLOPE/CLIFF/LEDGE in cognition).

| Class (selected set `SUPPORT_CONTACT_CLASS_V1`) | Predicate (sketch) | `grounded` implication | Friction / static eligibility | SES | Receipts |
|---|---|---|---|---|---|
| `FULL_SUPPORT` | ≥ τ_full of samples within ε of centre support plane/height band | May stay grounded if FGG says so | Eligible if grounded | Unchanged | classify receipt |
| `PARTIAL_SUPPORT` | τ_partial ≤ fraction < τ_full | Grounded allowed | Eligible (same N until G2D) | Unchanged | classify |
| `EDGE_OR_SPARSE_SUPPORT` | Few samples supported / large height spread | Grounded allowed **or** optional LOS policy | Eligible or reduced later | Unchanged | classify |
| `LOSS_OF_SUPPORT` | Supported fraction < τ_los **or** centre free while ring unsupported (policy) | Force airborne (PE-safe) | **Not** eligible | May align with large-downhill LOS | `RADIUS_SUPPORT_LOST` |
| `AIRBORNE_NO_SUPPORT` | Already airborne / gap | Airborne | None | — | — |

**Transitions:** hysteresis on fraction (enter LOS harder than exit) to avoid chatter at WRAP / cell edges.  
**Forbidden:** mapping classes to human semantic cognition tokens.

---

## 6. Stability levels 1–4

| Level | Meaning | Pitch/roll? | G2B |
|---|---|---|---|
| 1 | Planar multi-sample classification + optional LOS | **No** | **SELECTED (minimal)** |
| 2 | Support polygon / tipping margin in xy | No body lean | Later |
| 3 | Pitch/roll orientation degrees of freedom | Yes | Explicitly **absent** today — honest defer |
| 4 | Full 3D contact / gait | Yes | Out of roadmap window |

**STABILITY_MODEL_SELECTED = LEVEL_1_PLANAR_CLASSIFICATION_ONLY.**  
Pitch/roll / tipping dynamics are **not** claimed by G2B.

---

## 7. Body support geometry (concrete)

| Item | Selection |
|---|---|
| Law | Collision-disk ring samples |
| Radius R | `BODY_CONTACT_RADIUS = 0.575` (same as contact + FGG half-extent) |
| Samples | Centre + 8 ring at R (N=9 total); WRAP each sample via CSG/`wrap_coord` |
| Oracle | Each sample → `sample_surface_geometry` / `continuous_support_height` when CSG ON; else discrete elevation path |
| Authoritative z | **Centre sample only** for FGG `support_z` |
| Footprint cells | **Not** used for support |
| Aggregate n̂ | Optional researcher mean of sample normals — **inactive** physically |

---

## 8. ResourceObject support geometry (concrete)

| Item | Selection |
|---|---|
| Law | Same family as body |
| Radius R | `ensure_object_collision_radius(obj)` (canonical 0.25) |
| **Not** | `optical_radius` (0.45) |
| Samples | Centre + 8 ring (same N unless perf tweak to 4+centre for tiny R) |
| Authoritative z | Centre |
| HELD | No independent radius-aware FOGF; holder body classification may note held mass via existing EHL — object ring unused while held |
| FREE_STATIC / FREE_MOVING | Classification + FOGF eligibility use grounded ∧ class ≠ LOSS |

---

## 9. Continuous bilinear interaction

- Queries: O(1) per sample via existing `_bilinear_patch` (four corners, WRAP).  
- Patches: samples may span multiple patches; **no** dense raster.  
- WRAP: per-sample `_wrap_pose`.  
- Inactive aggregate normal: **allowed** as researcher diagnostic; must keep `NORMAL_PHYSICAL_EFFECTS_ACTIVE=NO`.  
- Cache: per-entity per-tick sample set keyed by pose + column generation (`note_authoritative_surface_mutation`).

---

## 10. SES interaction (**critical**)

**Prefer:** G2B does **not** rewrite SES energy law (`climb_work`, centre-path DDA, MICRO/LARGE classes).

| Change | SES impact | Allowed in first G2B? |
|---|---|---|
| Multi-sample classification receipts | None | YES |
| Force airborne on `LOSS_OF_SUPPORT` | Aligns with existing LOS spirit; no free PE | YES (careful tests) |
| Replace `support_z` with max/mean/plane | **Breaks ONE_PE** (free lift / mismatch vs centre Δh) | **NO** |
| Radius face-sweep replacing centre DDA | **Is** SES rewrite / decomposition | **NO** → G2C |

```text
SES_DECOMPOSITION_REQUIRED_BEFORE_G2B_IMPLEMENTATION = NO
  (for constrained Hybrid C⋆ slice)

SES_DECOMPOSITION_REQUIRED_BEFORE_SUPPORT_HEIGHT_REPLACEMENT = YES
  (aggregate support_z or face-sweep PE → G2C first / coupled)
```

**ONE_PE_AUTHORITY after G2B:** remains **`SES_DDA`**.

Order recommendation if full radius transition desired later:

```text
G2B constrained (samples + class + optional LOS)
  → G2C SES decomposition contract
  → optional radius-aware transition / support_z policy under new PE split
  → G2D N(n_z) → G2E g_tangent
```

---

## 11. Static / kinetic traction eligibility

- Keep **`N = m·g` / `m_eff·g` until G2D** (G2 B4 / static modules).  
- Eligibility: grounded ∧ class ∈ {FULL, PARTIAL, EDGE_OR_SPARSE} (policy); **not** if LOS/airborne.  
- Affinity sample: remain **centre cell** in G2B (FOGF `FOOTPRINT_MULTI_CELL` still NOT); multi-cell affinity = later.  
- Hysteresis: class + static rest flags; avoid flicker at patch edges.  
- No terrain-type μ tables.

---

## 12. Airborne / landing (radius-aware)

- **No unconditional snap** to support (FGG SES lock already forbids free upward snap).  
- Landing: when centre support met **and** class ≠ immediate LOS (or LOS evaluated next tick).  
- Multi-sample must not invent bounce / landing sound spam (`landing_sound` stays false unless explicit acoustic event).

---

## 13. Dynamic terrain mutation policies

Keep existing atomic column transfer + SES occupied support-rise reject.  
G2B adds: after mutation, invalidate per-entity sample cache; reclassify; may emit LOS if support withdrawn under footprint — **no forced free lift**.

---

## 14. Contacts / spatial index / acoustics

- Spatial index remains **2D** broadphase (`spatial_contents.py`).  
- Support classification ≠ impact; **no** acoustic emission every grounded tick.  
- Do not invent a second penetration solver from ring samples in G2B.

---

## 15. Energy / work

- SES DDA remains sole height-transition PE authority.  
- Classification / LOS dissipate or remove support only — **no reservoir credit**.  
- Friction still never creates energy.  
- Ideal support reaction does no work (unchanged FGG inelastic story).

```text
ONE_PE_AUTHORITY = SES_DDA
```

---

## 16. Snapshot / restore

- Serialize: mechanism enabled flag, profile version, class hysteresis state, counters; **omit** dense sample caches.  
- Missing key = OFF (parent presets bit-identity).  
- Do not double `ensure_body_vertical` on non-FGG restores (G1 closure repair).  
- Tiktaalik / pre-G2B fingerprints frozen.

---

## 17. Two-agent / experimenter

- Same classification law per entity; **no** special human stability.  
- Experimenter mutations already SES-gated; G2B reclassify after commit.  
- TwoAgent: one world authority; deferred contacts unchanged.

---

## 18. Cognition boundary

Agent may feel: slip, failed climb, fall (airborne), harder work — via existing physical channels.  
**Must not** receive `FULL_SUPPORT` / `LOSS_OF_SUPPORT` / slope tokens as symbols. Researcher overlays only.

---

## 19. Observer / Analyzer contract + anomalies

**Observer (gated):** sample count, class, height spread, optional inactive aggregate n̂, centre h, LOS flag, mechanism banner `radius samples available · support_z centre authority · normal physics inactive`.

**Analyzer anomalies:** free PE if support_z raised without SES; grounded friction while LOS; class chatter; sample query storm; optical radius used as support R; double PE; landing sound spam; Tiktaalik pollution.

---

## 20. Performance budget

| Item | Bound |
|---|---|
| Samples / entity / tick | ≤9 (body), ≤9 (object); start 5 if needed |
| Geometry | O(1) bilinear each; cache by pose+generation |
| Prospective deep copy | Forbidden / NOT_ESTABLISHED |
| Observer | No dense raster overlay |

---

## 21. Architectural invariants

1. One PE authority per height transition (SES DDA until G2C says otherwise).  
2. Authoritative G2B `support_z` = centre `h` (first slice).  
3. Support R from **collision** radii, never optical.  
4. Friction never creates energy; airborne ⇒ no support friction.  
5. `NORMAL_PHYSICAL_EFFECTS_ACTIVE=NO`; no g_tangent; no N(n_z).  
6. No renderer physics; no human terrain labels in cognition.  
7. Held mass counted once (EHL).  
8. Old presets frozen; snapshot omit inactive defaults.  
9. Mutation atomic + no free lift.  
10. Acoustics only from dissipative impacts/landings.  
11. Tick order preserved: horizontal (+SES) → vertical → contacts.  
12. Pitch/roll absent — Level-1 honesty.  
13. G2B_IMPLEMENTATION_STARTED remains NO until an explicit implementation slice.

---

## 22. Dependency verdict

| Verdict | Meaning |
|---|---|
| A | G2B fully independent of SES decomposition for all support-height policies |
| B | SES decomposition must precede **any** G2B work |
| **C** | **Constrained G2B (samples + classification + optional LOS) may proceed now with SES energy unchanged; replacing centre support_z / face-sweep PE requires G2C first** |
| D | Single coupled G2B+G2C mega-slice |

**Selected: C.**

**Code justification:**  
- `surface_elevation_support.py` hard-codes centre-path DDA and `ENTITY_RADIUS_FACE_SWEEP=NOT_IMPLEMENTED`.  
- `surface_support_height` / `support_z_for_entity` are single-point; raising support via max(samples) would change `integrate_vertical_entity` ground without SES `climb_work` — free PE.  
- G2 architecture already set `RADIUS_AWARE_SUPPORT_REQUIRED_BEFORE_NORMAL_PHYSICS=YES` and `SES_DECOMPOSITION_REQUIRED=YES` before g_tangent — consistent with C, not B (static traction already landed without SES split).

```text
RADIUS_AWARE_SUPPORT_REQUIRED_BEFORE_NORMAL_PHYSICS = YES
SES_DECOMPOSITION_REQUIRED_BEFORE_G2B = NO   # constrained slice
```

---

## 23. Recommended first implementation slice (**do not implement here**)

| Field | Value |
|---|---|
| Preset | `ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_SUPPORT` (name frozen at implement time) |
| Parent | `ACANTHOSTEGA_PHASE_C_FREE_OBJECT_STATIC_TRACTION` |
| Mechanism | `radius_aware_support_points` |
| Profile | `RADIUS_AWARE_SUPPORT_POINTS_V1` |
| Geometry | Body R=0.575 centre+8; object R=`collision_radius` centre+8; WRAP |
| Samples | CSG oracle per sample when ON |
| Classification | `SUPPORT_CONTACT_CLASS_V1` + hysteresis |
| Effects | Classification receipts; optional LOS→airborne; **support_z centre unchanged**; N unchanged; SES unchanged |
| Seam | After pose known for SES/FGG consumers: compute samples once per entity/tick; FGG still centre `support_z`; class gates traction eligibility |
| SES | **No rewrite** |
| Friction | Eligibility only; μ still centre affinity |
| Mutation | Cache invalidate + reclassify |
| Receipts | `RADIUS_SUPPORT_SAMPLE_SET`, `RADIUS_SUPPORT_CLASS`, `RADIUS_SUPPORT_LOST` |
| Observer / Analyzer | Banner + anomaly set §19 |
| Exclusions | No SES face-sweep; no aggregate support_z; no N(n_z); no g_tangent; no pitch/roll; no gait/jump/excavation/erosion/hydrology/3D renderer/lifecycle; no optical-R support |
| Tests | Flat FULL; peak → EDGE/LOS; pit visible to ring; WRAP continuity; free PE absent; parent OFF identity; snapshot omit; HELD skips object FOGF path; TwoAgent parity |
| Budget | Focused pytest + probes ≤30 ticks each; total sim ≤150; `SCIENTIFIC_VALIDATION_RUN=NO` |

**RECOMMENDED_NEXT_SLICE = G2B_RADIUS_AWARE_SUPPORT_POINTS (constrained Hybrid C⋆)**  
After G2B: `G2C_SES_DECOMPOSITION_CONTRACT` before any support-height replacement / face-sweep / g_tangent.

---

## Final status block

```text
FRESHNESS_CHECK = PASS
G2B_ARCHITECTURE_COMPLETE = YES
G2B_IMPLEMENTATION_STARTED = NO

BODY_SUPPORT_GEOMETRY_SELECTED = COLLISION_DISK_RING_SAMPLES_V1_R_BODY_CONTACT_0_575
OBJECT_SUPPORT_GEOMETRY_SELECTED = COLLISION_DISK_RING_SAMPLES_V1_R_COLLISION_RADIUS
SUPPORT_CLASSIFICATION_SELECTED = SUPPORT_CONTACT_CLASS_V1
STABILITY_MODEL_SELECTED = LEVEL_1_PLANAR_CLASSIFICATION_ONLY
ONE_PE_AUTHORITY = SES_DDA
SES_DECOMPOSITION_REQUIRED_BEFORE_G2B = NO
RADIUS_AWARE_SUPPORT_REQUIRED_BEFORE_NORMAL_PHYSICS = YES
NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO
TANGENT_GRAVITY_IMPLEMENTED = NO
SLOPE_SLIDING_IMPLEMENTED = NO

RECOMMENDED_NEXT_SLICE = G2B_RADIUS_AWARE_SUPPORT_POINTS_CONSTRAINED_HYBRID_CSTAR
SCIENTIFIC_VALIDATION_RUN = NO
```
