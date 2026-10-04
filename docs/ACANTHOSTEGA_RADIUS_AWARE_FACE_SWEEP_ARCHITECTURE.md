# ACANTHOSTEGA — Radius-Aware Face Sweep Architecture

**Date:** 2026-09-29 (Europe/Oslo, UTC+2)  
**Status:** ARCHITECTURE ONLY — no face-sweep implementation  
**Repo:** `<repository-root>` · **branch** `main` · **HEAD** `5d0f14cd7968b4d5b190796a2494d348a0e10f48`  
**Parent chain:** G1 CSG → G2A static → FOGF static twin → G2B Hybrid C⋆ → G2C1 contract → G2C2 runtime classifier → **this audit**

```text
FACE_SWEEP_ARCHITECTURE_COMPLETE = YES
FACE_SWEEP_IMPLEMENTATION_STARTED = NO
CURRENT_SES_SWEEPS_ENTITY_RADIUS = NO
ONE_PE_AUTHORITY = PE_AUTHORITY_SES_DDA
NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO
TANGENT_GRAVITY_IMPLEMENTED = NO
SLOPE_SLIDING_IMPLEMENTED = NO
RADIUS_FACE_SWEEP_IMPLEMENTED = NO
SCIENTIFIC_VALIDATION_RUN = NO
TOTAL_SIMULATED_TICKS = 0
```

**Method:** source inspection of SES / CSG / G2B / G2C1 / G2C2 / FGG / FOK / body-object contact radius. No new mechanism, preset, receipt, or physics. Prefer documentation-only.

Evidence pack: `results/acanthostega_radius_aware_face_sweep_architecture/`.

---

## 0. Repository confirmation (code is authoritative)

| Claim | Code status |
|---|---|
| CSG bilinear height + analytic n̂ | Present; `NORMAL_PHYSICAL_EFFECTS_ACTIVE=False` |
| G2A / FOGF static traction | Present |
| G2B centre+8 ring, centre z authority | Present (`RING_CLASSIFICATION_ONLY`, `CENTRE_Z_AUTHORITY`) |
| G2C1 taxonomy + `PE_AUTHORITY_SES_DDA` | Present |
| G2C2 post-resolution classifier | Present; no physical feedback |
| SES DDA sole height-transition PE | Present (`climb_work`, MICRO/LARGE) |
| `ENTITY_RADIUS_FACE_SWEEP` | **`"NOT_IMPLEMENTED"`** in `surface_elevation_support.py` |
| Continuous PE / N(n_z) / g_tangent / slope slide | OFF |

**Discrepancy vs older prose:** none material. G2C2 exists as S2_CLASSIFIER (still SES pays). Face sweep remains the next geometry seam before any radius PE.

---

## 1. Current geometry and authority map

### 1.1 Shared tick (preserved)

```text
horizontal CoM proposal
  → SES centre-path DDA plan + commit  (PE / topology block)   [+ G2C1/G2C2 receipts]
  → vertical FGG (centre support_z)
  → G2B ring classify (class / LOS→airborne; no PE)
  → contacts / impulses / acoustics
```

### 1.2 Per-entity pipelines

| Entity | Radius source | Horizontal → SES | Vertical | G2B | PE / work | Optical R |
|---|---|---|---|---|---|---|
| Organism body | `BODY_CONTACT_RADIUS = 0.575` | CoM integrate → `commit_body_elevation_gate` | FGG | `step_after_body_vertical` | Reservoir `m·g·Δh` on MICRO_UPHILL accept | **Forbidden** for support |
| Experimenter body | Same as body | Same SES body path | Same | Same | Same | Forbidden |
| FREE ResourceObject | `collision_radius` (canon 0.25) | FOK/FOGF proposal → `commit_free_object_elevation_gate` | FGG | `step_after_free_objects_vertical` | Block / K_normal / LOS (no body reservoir) | **Forbidden** (`optical_radius` ~0.45 unused) |
| HELD ResourceObject | Holder-coupled; no independent SES gate | Skipped while held | Held vertical policy | Skip classify | EHL elsewhere | N/A |

### 1.3 What SES sweeps today

**Confirmed from `centre_path_boundary_crossings` + `evaluate_path_transitions`:**

- **Only the centre trajectory** (unwrap short WRAP path).
- **Only cell faces crossed by the centre** (integer x/y boundaries; corner ties: x then y).
- **No part of the entity radius.**
- Destination G2B ring samples are **post-vertical classification**, not SES path evidence.
- Flag stamped on every crossing/receipt: `ENTITY_RADIUS_FACE_SWEEP = NOT_IMPLEMENTED`.
- Policy string: `TRAVERSAL_POLICY = CENTRE_PATH_DDA_GRID_BOUNDARY_V1`.

### 1.4 Authority classes

| Kind | Examples |
|---|---|
| Authoritative simulation state | body/object `x,y,z,vx,vy,vz,grounded`; reservoir; terrain columns |
| Derived physical query | CSG `sample_surface_geometry`; G2B ring heights; SES plan (pre-commit) |
| Researcher-only diagnostic | G2C1/G2C2 receipts; G2B class receipts; analytic n̂; banners |
| Agent-visible consequence | Pose, velocity, grounded, work depletion — **not** taxonomy labels |
| Renderer-only | Glyph / optical size |

---

## 2. Definition of “face sweep”

### Physical question (binding)

> Given a circular horizontal footprint of physical radius `R` moving from `p0 → p1` (WRAP minimum-image), determine whether any physically relevant portion of the **swept disk** encounters terrain elevation discontinuities or support gaps that should (a) **block** the transition as topology, (b) **cause support loss**, (c) **require elevation work** (future, under ONE_PE), (d) **feed support classification**, or (e) remain **diagnostic only**.

### What face sweep is **not**

- Not destination-only ring classification (already G2B).
- Not replacing centre `support_z` with max/mean ring height.
- Not continuous PE path integral.
- Not optical / glyph / reach radius.
- Not a general 3D mesh collider.

### Phase split (must stay separate)

| Phase | Role |
|---|---|
| **Broad phase** | Enumerate candidate cells / faces the swept disk might touch |
| **Narrow phase** | Exact (or ε-exact) disk/capsule vs face / height-step tests |
| **Support classification** | Remains G2B post-vertical (destination ring) unless a later coupled slice |
| **Collision / blocking** | Topology reject before pose/work commit |
| **Energy accounting** | Remains SES centre Δh until an explicit PE-owner migration |

### Candidate meanings A–F

| ID | Meaning | Verdict for V1 |
|---|---|---|
| A | Swept centre + radius-expanded cell boundaries | Useful **broad phase** only; alone misses interior features |
| B | Full continuous h(x,y) disk sweep | Too costly; tempts continuous PE; reject as V1 authority |
| C | Centre + 8 ring trajectories swept | Reuses G2B stencil; **false negatives** between samples |
| D | Capsule/footprint vs discontinuity faces | Correct **narrow phase** for ledges/steps |
| E | Conservative cell enum + exact queries | Correct **broad + narrow** skeleton |
| F | Hybrid E+D under SES plan | **SELECTED** |

**Selected definition:**  
`RADIUS_EXPANDED_CELL_ENUM_PLUS_SWEPT_DISK_VS_CELL_FACE_DISCONTINUITY_V1`  
= conservative Minkowski-expanded path cells (broad) + swept circular disk tested against cell-face elevation discontinuities (narrow), feeding SES plan evidence.

---

## 3. Failure modes of centre-only SES

Assume body `R = 0.575`, microrelief thr `τ = 0.12`. Coordinate examples are schematic.

| # | Case | SES sees | G2B dest sees | Unmodelled | Face sweep should | Action class |
|---|---|---|---|---|---|---|
| 1 | Centre path clear beside ledge; disk clips high cell | LEVEL / accept | May be PARTIAL if dest ring hits | Path-time radius collision | Earliest face hit along sweep | **Block** (topology) |
| 2 | Centre lands on ground; ring hangs over pit | Accept climb/level | PARTIAL / LOSS after vertical | Mid-path ring gap | Optional support-gap annotation; LOS still G2B | **Classify** / LOS post-vert |
| 3 | Narrow raised spike inside swept disk, not on centre | Miss | Miss if dest clear | Interior obstacle | Broad enum catches cell; narrow hits face | **Block** if Δh > τ |
| 4 | Gap width < diameter | Centre may thread | Dest may FULL wrongly | Diameter constraint | Overlap of blocked cells across path | **Block** if no continuous corridor of width ≥ 2R |
| 5 | Diagonal past corner | Centre DDA may skip adjacent high cell | Corner samples only at dest | Off-path corner clip | Expanded cell set includes corner neighbors | **Block** or evidence |
| 6 | WRAP boundary | Centre unwraps | Per-sample wrap | Radius must unwrap consistently | Same min-image unwrap for disk | Same laws |
| 7 | Starting overlap (restore/mutation/spawn) | No transition | Class may be odd | Penetration at t=0 | Starting-penetration policy (Part 9) | Anomaly; no free PE |
| 8 | Large multi-cell move | All centre faces | Dest only | Missed side faces | Broad phase ∝ path length × R | Plan evidence |
| 9 | Partial support changes mid-path | Centre Δh only | Dest class | Mid-path ring evolution | Optional diagnostic samples; G2B stays dest | Provenance |
| 10 | FREE object R=0.25 vs body 0.575 | Same centre DDA | Object ring | Different clip extent | Shared kernel, per-entity R | Same policy |

```text
CENTRE_PATH_LIMITATION_CONFIRMED = YES
```

---

## 4. Representation comparison

| Option | FN | FP | Deterministic | WRAP | Sparse/proc OK | Cost | PE risk |
|---|---|---|---|---|---|---|---|
| Centre+8 swept rings (C) | High (between rays) | Low | Yes (fixed stencil) | Yes | Yes | ~9× DDA | Low if classify-only |
| Adaptive perimeter | Medium | Medium | Harder | Yes | Yes | Variable | Medium |
| Radius-expanded grid DDA (A) | Medium | Medium–High | Yes | Yes | Yes | O((L+2R)·R) cells | Low as broad |
| Capsule vs faces (D) | Low for ledges | Low with τ | Yes if ordered | Yes | Yes | O(candidates) | Low if topology-only |
| Continuous disk h sample (B) | Low | Medium | Yes | Yes | Yes | High | **High** (tempts PE) |
| **E+D hybrid (F)** | Low | Controllable | Yes | Yes | Yes | Bounded | **Safe if Policy C** |

**Reject:** display resolution, optical R, heading-rotated collision for a circular footprint.

**V1 representation:** E+D hybrid.  
**Upgrade path:** denser perimeter only for diagnostics → optional continuous-PE path integral **after** PE owner migration → support polygon later.  
**Deliberately unmodelled in V1:** pitch/roll, torque, 3D mesh, excavation scar topology beyond column height, gait, N(n_z).

---

## 5. Energy and authority (central)

```text
ONE_PE_AUTHORITY_CURRENT = PE_AUTHORITY_SES_DDA
```

| Policy | Block? | PE from radius? | Safe now? |
|---|---|---|---|
| **A** Detection/classification only | No | No | Yes (zero physics risk) |
| **B** Extra topology blocker (parallel to SES) | Yes | No | Risky dual commit |
| **C** Face-sweep evidence → SES single commit | Yes via SES | No (centre Δh only) | **Yes — selected V1 target** |
| **D** Full radius-aware PE | Yes | Yes | **No** until PE migration |

### Selected policy

**Policy C — Face sweep contributes a barrier proposal to SES; SES remains the only commit and work authority.**

- Radius discontinuity with `|Δh| > τ` → SES may emit a **topology block** (same family as `LARGE_UPHILL_BLOCKED`), **before** pose/work mutation.
- Radius evidence **must not** invent MICRO_UPHILL debit from ring max height.
- Centre-path MICRO_UPHILL work formula unchanged.
- No lift of centre `z` to perimeter max.
- No smoothing ledge → ramp.
- G2B destination class remains non-PE.

**Atomicity:** plan (centre DDA + radius evidence) → single accept/reject → single commit → G2C2 classify.  
Never: commit → discover → rollback.

**G2C prerequisite:** G2C1+G2C2 establish taxonomy and PE stamp. **No further PE-law decomposition required** before Policy C topology blocking. A **minimal SES plan-extension** (not PE rewrite) is required so radius evidence enters `evaluate_path_transitions` before commit.

```text
SES_DECOMPOSITION_PREREQUISITE_COMPLETE = YES   # G2C1+G2C2 exist
ADDITIONAL_SES_REFACTOR_REQUIRED = YES          # minimal plan-evidence seam only
FACE_SWEEP_MAY_BLOCK_IN_V1 = YES                # via SES topology, Policy C
FACE_SWEEP_MAY_CHARGE_PE_IN_V1 = NO
```

---

## 6. Tick order and seam

| Option | Verdict |
|---|---|
| 1 Before horizontal integrate | Proposal incomplete |
| **2 During SES plan creation** | **SELECTED** — proposed path known; terrain authoritative; work not debited; pose not mutated |
| 3 Between plan and commit | Acceptable twin of 2 if plan is pure |
| 4 After SES commit, before vertical | Requires rollback — **reject** |
| 5 During G2B | Too late; G2B is non-PE dest class |

**Recommended seam:** inside / immediately feeding `evaluate_path_transitions` (body and free-object share this planner), **before** `commit_*_elevation_gate` mutates pose or reservoir.

```text
RECOMMENDED_RUNTIME_SEAM = SES_EVALUATE_PATH_TRANSITIONS_PRE_COMMIT
```

G2C2 already classifies post-commit with proposed vs realized — remains valid if block happens inside SES plan.

TwoAgent: one shared-world SES evaluation per entity; insertion-order independent keys (`entity_kind:entity_id`); no `id()`.

---

## 7. Body / object scope

| In V1 | Out of V1 |
|---|---|
| Organism bodies | HELD independent sweep |
| Experimenter bodies (same body path) | Optical / glyph / reach radii |
| FREE objects (shared geometry kernel, `collision_radius`) | Aggregate support_z PE |

**Adapter split:** shared pure function  
`plan_radius_face_evidence(p0, p1, R, world, thr) → evidence`  
+ SES commit adapters (body reservoir vs object K_normal) unchanged.

```text
RECOMMENDED_ENTITY_SCOPE = BODY_AND_FREE_OBJECT_SHARED_KERNEL
```

---

## 8. Starting penetration and mutation

Causes: restore, spawn, terrain mutation, column transfer, legacy centre-only pose, ε overlap.

| Option | Verdict |
|---|---|
| Refuse runtime/load | Too harsh for lab restore |
| Deterministic depenetration | Risky silent teleport |
| **Allow outward / forbid deeper** | **SELECTED** |
| Mark unresolved only | Insufficient alone |
| Researcher intervention only | Supplement, not sole |

**Policy:** if already intersecting a prohibited high face at rest: do not teleport; do not emit impact acoustics on geometry refresh; allow motion that reduces penetration measure; forbid motion that increases it; emit researcher anomaly `RADIUS_STARTING_PENETRATION`. Terrain mutation keeps SES occupied support-rise reject (no free PE).

```text
STARTING_PENETRATION_POLICY = ALLOW_OUTWARD_FORBID_DEEPER_PLUS_ANOMALY_RECEIPT
```

---

## 9. Determinism and WRAP

- Sample / candidate order: ascending path parameter `t`; then face axis `x` before `y`; then `(cell_x, cell_y)` lex; then feature id string — **never** Python `id()`.
- ε: reuse SES `EPS_LEVEL` / path `1e-9` / rounded `t` to 12 decimals (match centre DDA).
- Coincident hits: first in that total order wins.
- WRAP: same `_unwrap_delta` minimum-image as centre DDA; disk tests in unwrapped frame; results wrapped for reporting.
- Ring orientation for any diagnostic samples: **fixed world axes** (as G2B); circle must not gain heading-dependent collision.
- Shared world: one application per `entity_id` per tick; TwoAgent slot partition for receipts like G2C2.
- Snapshot: no dense candidate dumps; restore must not invent a first-tick collision from pose init (mirror G2C2 suppress).

```text
WRAP_POLICY = MIN_IMAGE_UNWRAP_SAME_AS_CENTRE_DDA
TIE_BREAK_POLICY = T_ASC_THEN_AXIS_X_BEFORE_Y_THEN_CELL_LEX_NO_ID
```

---

## 10. Performance (estimate)

Let `L` = path length in cells (centre), `R` = radius in cells, `F` = faces per candidate cell (≤4).

| Stage | Approx queries |
|---|---|
| Broad phase cells | `O((L + 2⌈R⌉) · (2⌈R⌉ + 1))` |
| Narrow face tests | `O(#candidates · F)` height reads via existing support/CSG oracle |
| vs G2B | G2B already 9 CSG samples / entity / tick post-vertical |

**Soft diagnostic cap (suggested):** max 256 candidate cells / transition; max 1024 face tests — **report** `CAP_HIT` anomaly; do **not** silently accept. Hard reject only if evidence incomplete **and** policy requires conservative block (future flag; default V1: report + treat as ambiguous evidence → SES may GEOMETRY_AMBIGUOUS via G2C2, not free climb).

Caches: pose + surface generation keyed; derived; non-authoritative; invalidate on `note_authoritative_surface_mutation`.

```text
MAX_ACCEPTABLE_QUERY_COST_V1 = O((L+2R)*(2R+1))_CELL_ENUM_PLUS_O(CANDIDATES)_FACE_TESTS__SOFT_CAP_256_CELLS
```

---

## 11. Prospective simulation

Code/docs: prospective composition does **not** shadow full SES+FGG+CSG+G2B.

```text
PROSPECTIVE_FACE_SWEEP_SUPPORT = NOT_AVAILABLE__APPROX_LOCOMOTION_ONLY
```

Future: shared immutable geometry oracle / bounded local query context; never a second PE ledger; uncertainty explicit if approximate blocker used.

---

## 12. Future receipt contract (design only — do not implement)

Suggested kind: `RADIUS_AWARE_FACE_SWEEP_EVIDENCE` (researcher-only).

Bounded fields: tick; entity_kind/id; R; origin; proposed; broad_phase_cell_count; earliest_hit `{t, cell, axis, delta_h, feature_type}`; blocking_proposal bool; ses_decision; pe_authority=`PE_AUTHORITY_SES_DDA`; realized; support_class before/after if known; cap/anomaly flags; application_key.

Omit unbounded per-sample dumps. Never copy taxonomy/PE stamps into cognition.

---

## 13. Future acceptance tests (for implementation task)

1–20 as specified in the task brief (ledge clip, partial dest, narrow gap, diagonal corner, WRAP, body vs object R, zero-R ≡ centre, no optical R, no free lift, no duplicate PE, block before commit, insertion permute, TwoAgent single apply, restore no false event, starting penetration, mutation invalidation, G2C2 proposed/realized, parent OFF bit-identical, Tiktaalik unchanged, cognition privacy).

**Budget for later implementation:** ≤300 simulated ticks; no scientific long run.

---

## 14. Required decisions (explicit)

| # | Decision |
|---|---|
| 1 | Ready to implement architecture? **YES.** Ready to flip physics without plan seam? **NO** — need SES plan-evidence extension. |
| 2 | Extra PE-law SES contract? **NO.** Minimal plan refactor? **YES.** |
| 3 | V1 may block? **YES** (SES topology via Policy C). |
| 4 | V1 may charge PE/work from radius? **NO.** |
| 5 | Geometry: **E+D hybrid** (`RADIUS_EXPANDED_CELL_ENUM_PLUS_SWEPT_DISK_VS_CELL_FACE_DISCONTINUITY_V1`). |
| 6 | Seam: **`evaluate_path_transitions` pre-commit**. |
| 7 | Entities: **body + experimenter body + FREE object**; shared kernel. |
| 8 | Starting penetration: **outward OK / deeper forbidden + anomaly**. |
| 9 | WRAP: **min-image unwrap = centre DDA**. |
| 10 | Tie-break: **t → axis x/y → cell lex; no id()**. |
| 11 | Cost: **O((L+2R)(2R+1)) + O(candidates)**; soft cap 256 cells. |
| 12 | Next slice: **`RADIUS_AWARE_FACE_SWEEP_SES_PLAN_EVIDENCE_V1`**. |

### Hard blockers

```text
BLOCKER = NONE
```

No scientific blocker. Implementation requires the documented SES plan-evidence seam; that is a scoped prerequisite, not a show-stopper.

---

## 15. Recommended next slice

| Field | Value |
|---|---|
| Slice | `RADIUS_AWARE_FACE_SWEEP_SES_PLAN_EVIDENCE_V1` |
| Suggested preset | `ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_FACE_SWEEP` (OFF by default) |
| Parent | `ACANTHOSTEGA_PHASE_C_SES_RUNTIME_CLASSIFIER` |
| Mechanism | `radius_aware_face_sweep` (plan evidence + optional SES topology block) |
| PE | Still `PE_AUTHORITY_SES_DDA`; **no** radius PE debit |
| Excludes | continuous PE, N(n_z), g_tangent, aggregate support_z, face-sweep PE, optical R |

```text
RECOMMENDED_NEXT_SLICE = RADIUS_AWARE_FACE_SWEEP_SES_PLAN_EVIDENCE_V1
```

---

## Closing status

```text
FRESHNESS_CHECK = PASS
FACE_SWEEP_ARCHITECTURE_COMPLETE = YES
FACE_SWEEP_IMPLEMENTATION_STARTED = NO
CURRENT_SES_SWEEPS_ENTITY_RADIUS = NO
CENTRE_PATH_LIMITATION_CONFIRMED = YES
RECOMMENDED_V1_POLICY = POLICY_C_BARRIER_PROPOSAL_TO_SES
RECOMMENDED_GEOMETRY = RADIUS_EXPANDED_CELL_ENUM_PLUS_SWEPT_DISK_VS_CELL_FACE_DISCONTINUITY_V1
RECOMMENDED_RUNTIME_SEAM = SES_EVALUATE_PATH_TRANSITIONS_PRE_COMMIT
RECOMMENDED_ENTITY_SCOPE = BODY_AND_FREE_OBJECT_SHARED_KERNEL
STARTING_PENETRATION_POLICY = ALLOW_OUTWARD_FORBID_DEEPER_PLUS_ANOMALY_RECEIPT
WRAP_POLICY = MIN_IMAGE_UNWRAP_SAME_AS_CENTRE_DDA
TIE_BREAK_POLICY = T_ASC_THEN_AXIS_X_BEFORE_Y_THEN_CELL_LEX_NO_ID
FACE_SWEEP_MAY_BLOCK_IN_V1 = YES
FACE_SWEEP_MAY_CHARGE_PE_IN_V1 = NO
ONE_PE_AUTHORITY = PE_AUTHORITY_SES_DDA
SES_DECOMPOSITION_PREREQUISITE_COMPLETE = YES
ADDITIONAL_SES_REFACTOR_REQUIRED = YES
NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO
NORMAL_LOAD_PROJECTION_IMPLEMENTED = NO
TANGENT_GRAVITY_IMPLEMENTED = NO
SLOPE_SLIDING_IMPLEMENTED = NO
RADIUS_FACE_SWEEP_IMPLEMENTED = NO
TIKTAALIK_PHYSICS_CHANGED = NO
PREVIOUS_ACANTHOSTEGA_PRESETS_CHANGED = NO
COGNITION_CHANGED = NO
SCIENTIFIC_VALIDATION_RUN = NO
LONG_RUN_EXECUTED = NO
TOTAL_SIMULATED_TICKS = 0
BLOCKER = NONE
RECOMMENDED_NEXT_SLICE = RADIUS_AWARE_FACE_SWEEP_SES_PLAN_EVIDENCE_V1
```

No git commit/push. No implementation code.
