# Acanthostega — Continuous Surface Geometry + Normals

**Document type:** ARCHITECTURE + G1 IMPLEMENTATION STATUS  
**SCIENTIFIC_VALIDATION_RUN:** NO

```
G1_IMPLEMENTED = YES
HEIGHT_PHYSICAL_EFFECTS_ACTIVE = YES
NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO
```

---

## Status legend (use throughout)

| Tag | Meaning |
|---|---|
| **ARCHITECTURE DECISION** | Frozen design choice; still binding |
| **IMPLEMENTED IN G1** | Shipped under CSG preset |
| **VALIDATED IN G1** | Covered by focused tests / probes |
| **DEFERRED TO G2+** | Explicitly not shipped; do not interpret presence of symbols as activation |

---

## 0. Locked identities (G1)

| Kind | Value | Tag |
|---|---|---|
| Public preset | `ACANTHOSTEGA_PHASE_C_CONTINUOUS_SURFACE_GEOMETRY` | IMPLEMENTED IN G1 |
| UI label | Acanthostega Phase C Continuous Surface Geometry | IMPLEMENTED IN G1 |
| Mechanism | `continuous_surface_geometry` | IMPLEMENTED IN G1 |
| Profile | `BILINEAR_HEIGHT_ANALYTIC_NORMAL_V1` | IMPLEMENTED IN G1 |
| Parent | `ACANTHOSTEGA_PHASE_C_BODY_NORMAL_LOAD_TRACTION` | ARCHITECTURE DECISION / IMPLEMENTED IN G1 |
| Module | `mechanistic_mind/physical_system/continuous_surface_geometry.py` | IMPLEMENTED IN G1 |
| Sample locus | `CELL_CENTRE_LATTICE_V1` (`i0 = floor(x−0.5)`, centres at `i+0.5`) | ARCHITECTURE DECISION / IMPLEMENTED IN G1 |
| Shared oracle API | `sample_surface_geometry(world, x, y, …)` | IMPLEMENTED IN G1 |
| Height physical | `HEIGHT_PHYSICAL_EFFECTS_ACTIVE = True` (when mechanism ON) | IMPLEMENTED IN G1 / VALIDATED IN G1 |
| Normal physical | `NORMAL_PHYSICAL_EFFECTS_ACTIVE = False` | IMPLEMENTED IN G1 / VALIDATED IN G1 |
| Dense height raster | NO | ARCHITECTURE DECISION / VALIDATED IN G1 |
| Hidden smoothing | FORBIDDEN | ARCHITECTURE DECISION / VALIDATED IN G1 |

**This document is not map-only.** G1 geometry oracle + continuous support height are implemented. Analytic normal exists as a derived researcher field and is **physically inactive**.

---

## 1. Goal (ARCHITECTURE DECISION)

SES centre-cell piecewise-constant elevation cannot represent continuous support under sub-cell poses or a true surface normal field. G1 adds a **shared geometry oracle** that derives continuous `h(x,y)` and analytic `n̂(x,y)` from the existing column/delta authority **without** slope PE, tangent gravity, or `N(n̂)`.

---

## 2. Authoritative vs derived

| Quantity | Authority | Tag |
|---|---|---|
| Cell `surface_elevation` | Procedural baseline ± sparse delta (+ seed/generator) | ARCHITECTURE DECISION / unchanged |
| Continuous `h(x,y)` | **Derived** — never stored as dense authoritative field | IMPLEMENTED IN G1 |
| `n̂(x,y)`, ∇h, bilinear weights, corner heights | **Derived** from the same bilinear patch as `h` | IMPLEMENTED IN G1 |
| Support placement / grounded z (CSG ON) | Consumes continuous `h` | IMPLEMENTED IN G1 |
| Transition energy / block / support-loss | SES DDA remains sole authority | IMPLEMENTED IN G1 (kept) |
| Analytic normal → forces / friction / N | **Inactive** | DEFERRED TO G2+ |
| Agent observation | Must not expose researcher geometry tokens | VALIDATED IN G1 |

Caches / overlays / receipt history are **non-authoritative acceleration** (same policy as column cache). Snapshot must not serialize a dense continuous raster.

---

## 3. Shared oracle API (`sample_surface_geometry`) — IMPLEMENTED IN G1

```
sample_surface_geometry(world, x, y, *, config=None, record=False) -> dict
```

Returns (researcher-facing / reconstructible): `height`, `gradient_x`/`gradient_y`, `normal_x`/`normal_y`/`normal_z`, `u`/`v`, bilinear weights, four cell indices, corner heights, provenance, profile/version, effect flags.

Helpers:
- continuous support height path used by SES/FGG when CSG ON
- `continuous_surface_normal` → unit `n̂` (physically unused in G1)

**Contract:** geometry query does **not** mutate material / deltas / scientific tick. Sparse mutation is immediately visible on the next query (no stale dense height cache).

---

## 4. Coordinate + WRAP conventions — ARCHITECTURE DECISION / IMPLEMENTED IN G1

1. World units: cell size = 1; toroidal WRAP via existing topology helpers.
2. **Sample locus = cell-centre lattice** (not integer corners):  
   `i0 = floor(x − 0.5)`, `j0 = floor(y − 0.5)`, `u = x − (i0+0.5)`, `v = y − (j0+0.5)`.
3. Four samples: centres `(i0,j0)`, `(i0+1,j0)`, `(i0,j0+1)`, `(i0+1,j0+1)` with WRAP.
4. Bilinear:  
   `h = (1−u)(1−v)h00 + u(1−v)h10 + (1−u)v h01 + u v h11`.
5. At cell centres, continuous `h` == discrete centre sample (SES DDA coexistence).
6. Continuity: height **C⁰**; gradient/normal **discontinuous** across edges (do not claim C¹).
7. Anti-smoothing: no bicubic / blur / write-back / neighbour relaxation.  
   `HIDDEN_SMOOTHING_OF_PITS_AND_EMBANKMENTS = FORBIDDEN`.

Analytic normal (same patch):
```
∂h/∂x = (1−v)(h10−h00) + v(h11−h01)
∂h/∂y = (1−u)(h01−h00) + u(h11−h10)
n_raw = (−∂h/∂x, −∂h/∂y, 1);  n̂ = n_raw / |n_raw|
```
Flat patch → `n̂ = (0,0,1)` exactly.

---

## 5. G1 tick seam — IMPLEMENTED IN G1

When `continuous_surface_geometry.enabled` and mechanism active:

1. **Support height oracle** (`surface_support_height` / `support_z_for_entity`) → continuous `h(x,y)` for grounded body and FREE objects.
2. FGG vertical integrator uses that support z; inelastic support placement / grounded tests track continuous surface.
3. SES centre-path DDA (`SUBGRID_MICRORELIEF_RAMP_V1`) **unchanged** for MICRO_UPHILL / LARGE_UPHILL block / downhill / support-loss energy and blocking.
4. BNLT: still `N = m_eff · g` (vertical); μ from discrete floor-cell affinity; Gentle damp bypass unchanged. Continuous height may update grounded provenance only.
5. FOGF: continuous support for grounded FREE objects; Coulomb/affinity equations unchanged; no slope sliding.
6. Analytic `n̂` may be sampled into researcher receipts / Observer overlay; **must not** retarget forces, friction direction, or N.

**Physical activation flags (locked):**
```
HEIGHT_PHYSICAL_EFFECTS_ACTIVE = YES   # continuous h is support height when CSG ON
NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO    # n̂ does not drive physics in G1
```

**Airborne:** not unconditionally snapped to surface. SES block / support-loss semantics preserved.

**One PE authority in G1:** SES DDA climb/block only — no second slope PE via normal.  
`DOUBLE_POTENTIAL_ENERGY_DEBIT = NO` (G1 contract).

---

## 6. SES authority — KEPT (ARCHITECTURE DECISION / IMPLEMENTED IN G1 coexistence)

| SES piece | G1 fate |
|---|---|
| SCALE GATE `physical_height_scale=1.0` | STAYS |
| `microrelief_threshold` | STAYS for discrete classifier |
| Centre-path DDA | STAYS energy/blocking authority |
| MICRO_UPHILL / downhill / block / support-loss | STAYS |
| Receipt `SURFACE_ELEVATION_TRANSITION` | STAYS |
| Parent presets when CSG key absent | Centre-cell support as before |

Flags:
```
CONTINUOUS_SLOPES = GEOMETRY_ONLY_V1
SES_DISCRETE_DDA = KEPT_PHASE1
```

Energy migration of climb work to continuous path-integral PE is **DEFERRED TO G2+** (must not dual-charge).

---

## 7. Snapshot / cache — IMPLEMENTED IN G1 / VALIDATED IN G1

- Serialize: CSG config + bounded state (history/counters/generation).  
- **Do not** serialize dense continuous height raster.  
- Legacy snapshot without CSG field → OFF.  
- Column cache remains derived/non-authoritative; cold vs warm cache must not change baseline elevation samples.  
- Mutation of sparse delta immediately visible to oracle (generation awareness allowed).

---

## 8. Observer / Analyzer — IMPLEMENTED IN G1

- Preset in canonical selector (`modelPreset.ts` / APPLY EXPERIMENT).
- Status banner (contract language):
  ```
  CONTINUOUS SURFACE GEOMETRY · BILINEAR HEIGHT V1 ·
  ANALYTIC NORMAL AVAILABLE · PHYSICALLY INACTIVE ·
  SES DDA ENERGY/BLOCKING KEPT · NO SLOPE FORCES · NO RADIUS SUPPORT · NO GAIT
  ```
- Overlay: read-only geometry; `normal_implies_slope_forces = false`.
- Analyzer section `CONTINUOUS SURFACE GEOMETRY`: receipts, height range, effect flags, HIDDEN_SMOOTHING, DENSE_RASTER, SES_DDA.
- Cognition privacy: forbidden tokens include mechanism/profile/normal/weights/flags (VALIDATED IN G1).

---

## 9. Validation evidence (VALIDATED IN G1)

Primary suite: `tests/test_acanthostega_continuous_surface_geometry.py` (isolation, flat normal, bilinear, WRAP, anti-smoothing, non-mutating query, mutation immediacy, body support, parent floor-cell, SES smoke, snapshot, BNLT vertical N, banner).

Supporting regressions (Phase C parents / columns / contacts): see  
`results/acanthostega_continuous_surface_geometry/closure/G1_CLOSURE_EVIDENCE.md`.

Probes: `experiments/run_csg_g1_probes.py` + `probe_evidence.json` (planar, WRAP, mutation, body patch, SES, downhill air, FREE, snap/restore).

---

## 10. G1 limits (what is NOT claimed)

| Topic | Status |
|---|---|
| Slope / tangent-plane gravity | DEFERRED TO G2+ |
| `N = m_eff g n_z` or force-balance N | DEFERRED TO G2+ |
| Tangent friction / static cone | DEFERRED TO G2+ |
| Radius-aware / multi-point support footprint | DEFERRED TO G2+ |
| Gait / jump / excavation / hydrology | DEFERRED TO G2+ |
| Dense voxels / authoritative height raster | FORBIDDEN |
| Retiring SES DDA energy under CSG | DEFERRED TO G2+ (after double-count audit) |
| Scientific long validation runs | NOT IN G1 (`SCIENTIFIC_VALIDATION_RUN = NO`) |

**Document must NOT claim** that gravity / `z` / `vz` / surface elevation support are absent from the stack. FGG vertical state, SES elevation energy, BNLT, and FOGF remain live parent mechanisms; G1 only swaps the **support height sample** to continuous `h` under the CSG preset and adds an inactive analytic normal.

---

## 11. Forbidden interpretations of the normal arrow

Do **not** interpret a drawn / logged / overlaid `n̂` as evidence that:

1. Slope gravity is active  
2. Friction lies in the tangent plane  
3. `N = m_eff g · n_z` (or equivalent) is in force  
4. SES climb PE was replaced by continuous PE  
5. Agents receive symbolic SLOPE / CLIFF / UPHILL labels  
6. Radius-aware support or multi-cell footprint exists  
7. Geometry interpolation created or destroyed mass/material  

`NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO` until an explicit G2+ slice activates it under a new energy/force audit.

---

## 12. Reconciliation with columns / transfer (ARCHITECTURE DECISION / kept)

- Oracle reads **only** `surface_elevation` (+ SCALE GATE).  
- No inventing layer thickness / composition / mass from interpolation.  
- Transfer scars remain honest lattice slopes under bilinear — not smoothed.  
- Conservation stays in column/transfer transactions.

---

## 13. BNLT / FOGF / FGG coupling summary

| Mechanism | G1 coupling | Tag |
|---|---|---|
| BNLT | Consume continuous support height for grounded provenance; **N = m_eff·g** vertical | IMPLEMENTED IN G1 |
| FOGF | Consume continuous support height; affinity Coulomb unchanged | IMPLEMENTED IN G1 |
| FGG | Vertical g + inelastic support; `support_z` from oracle when CSG ON | IMPLEMENTED IN G1 |
| SES | Energy/blocking authority unchanged | IMPLEMENTED IN G1 |
| Affinity / deposits | Still discrete per cell (no bilinear μ) | ARCHITECTURE DECISION |

---

## 14. Final flags

```
G1_IMPLEMENTED = YES
HEIGHT_PHYSICAL_EFFECTS_ACTIVE = YES
NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO
HEIGHT_INTERPOLANT = BILINEAR_CELL_CENTRES
AUTHORITATIVE_NORMAL = ANALYTIC_FROM_BILINEAR   # derived field; physically inactive in G1
SHARED_GEOMETRY_ORACLE = sample_surface_geometry
RECONCILES_WITH_PSC_AND_TRANSFER = YES
HIDDEN_SMOOTHING_OF_PITS_AND_EMBANKMENTS = FORBIDDEN
SES_SUBGRID_MICRORELIEF_RAMP_V1 = KEPT_PHASE1_ENERGY_AUTHORITY
BNLT_FOGF_FGG_COUPLING = HEIGHT_NOW_NORMALS_LATER
PRESET = ACANTHOSTEGA_PHASE_C_CONTINUOUS_SURFACE_GEOMETRY
PARENT = ACANTHOSTEGA_PHASE_C_BODY_NORMAL_LOAD_TRACTION
DENSE_AUTHORITATIVE_HEIGHT_RASTER = NO
SLOPE_GRAVITY = NO
TANGENT_PLANE_FRICTION = NO
RADIUS_AWARE_SUPPORT = NO
GAIT = NO
EXCAVATION = NO
SCIENTIFIC_VALIDATION_RUN = NO
MAP_ONLY = NO
```

**Next seam (audit only until G1 closure is green):** G2 energy/force architecture for optional tangent gravity / `N(n̂)` — must prove single PE authority vs SES DDA before any implementation.
