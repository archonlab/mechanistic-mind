# ACANTHOSTEGA — G2D Continuous Normal-Load Projection Architecture

**Date:** 2026-09-29 (Europe/Oslo, UTC+2)  
**Status:** ARCHITECTURE ONLY — no G2D implementation  
**Repo:** `<repository-root>` · **branch** `main` · **HEAD** `5d0f14cd7968b4d5b190796a2494d348a0e10f48`  
**Parent chain:** G1 CSG → BNLT/FOGF → G2A static → FOGF static twin → G2B → G2C1 → G2C2 → face-sweep SES plan evidence → **this audit**

```text
G2D_ARCHITECTURE_COMPLETE = YES
G2D_IMPLEMENTATION_STARTED = NO
CURRENT_BODY_NORMAL_LOAD = m_eff · g
CURRENT_FREE_OBJECT_NORMAL_LOAD = mass · g
PROJECTED_NORMAL_LOAD_FORM = m_eff · g · n_z   (candidate; not active)
ONE_PE_AUTHORITY = PE_AUTHORITY_SES_DDA
NORMAL_PHYSICAL_EFFECTS_ACTIVE = NO
TANGENT_GRAVITY_IMPLEMENTED = NO
PASSIVE_SLOPE_SLIDING_IMPLEMENTED = NO
CONTINUOUS_PE_IMPLEMENTED = NO
SCIENTIFIC_VALIDATION_RUN = NO
TOTAL_SIMULATED_TICKS = 0
```

**Method:** source inspection of CSG / FGG / SES / BNLT / G2A / FOGF / FOST / G2B / G2C1 / G2C2 / face sweep / EHL / runtime / two-agent. No new mechanism, preset, receipt emitter, or physics change. Prefer code over older prose when they differ.

Evidence pack: `results/acanthostega_continuous_normal_load_g2d_architecture/`.

---

## 0. Repository confirmation (code is authoritative)

| Claim | Code status |
|---|---|
| CSG bilinear height + analytic n̂ | Present; `HEIGHT_PHYSICAL_EFFECTS_ACTIVE=True`; `NORMAL_PHYSICAL_EFFECTS_ACTIVE=False` |
| FGG vertical gravity / grounded | Present |
| SES DDA sole height-transition PE | Present (`climb_work = m·g·Δh`) |
| BNLT kinetic `N = m_eff·g`; accel `a = μ_k·g` | Present |
| G2A body static `j_max = μ_s·N·dt` | Present |
| FOGF kinetic receipt `N = m·g`; accel `a = μ_k·g` | Present |
| FOST FREE static `N = m·g` | Present |
| G2B centre+8 ring; class after vertical | Present; friction reads **prior-tick** class |
| G2C1 / G2C2 / face-sweep SES plan evidence | Present; face sweep may block; no PE |
| Active `N = m·g·n_z` | **NOT implemented** |
| Tangent gravity / slope sliding / continuous PE | **OFF** |
| Pitch/roll / support polygon | **OFF** |

**Discrepancy vs older G2 prose:** G2A static, FOST, G2B, G2C1/C2, and radius face-sweep now exist (older G2 architecture recommended them as future). Force law for N remains flat vertical. No material conflict with “no active normal projection.”

---

## 1. Central question

Should the next slice activate

```text
N = m_eff · g · n_z
```

into static/kinetic traction while `TANGENT_GRAVITY = OFF`?

**Verdict:** **NO for active physics.** Enabling projected N without `g_t` shrinks traction capacity on slopes without adding the downhill drive — a scientifically misleading half-slope model.  
**YES for a diagnostic shadow slice** that computes and receipts projected N while friction still uses flat `N = m·g`.

**Recommended policy:** **Policy A — `G2D_DIAGNOSTIC_NORMAL_LOAD_SHADOW`.**  
Active N + tangent gravity only later, after SES smooth-slope PE decomposition readiness (Policy D atomic active stage).

---

## 2. Current force / tick map (summary)

Full table: `results/.../CURRENT_FORCE_PIPELINE.md`.

```text
BODY / EXPERIMENTER (per slot):
  begin: cognition → MOVE Δv → affinity transmission → (optional) MOVE static capacity μ_s N dt
  finish horizontal:
    prepare_body_coulomb_context  →  N = m_eff·g ; prior grounded ; prior G2B class
    CoM integrate → G2A static then BNLT kinetic (or kinetic only)
    SES evaluate_path_transitions (+ face-sweep evidence) → commit once
    Gentle rest (BNLT bypasses damp)
  finish vertical: FGG → G2B classify (writes class for NEXT friction tick)
  then shared world: FREE horiz → SES → FREE vertical → G2B objects → contacts

FREE object:
  FOST static or FOGF kinetic (prior grounded) → SES+face → FGG vertical → G2B classify

HELD object:
  no independent ground N; mass enters holder m_eff exactly once via EHL
```

### Force-provenance table

| Channel | Mass | Uses N? | Formula today | Work/PE |
|---|---|---|---|---|
| Active MOVE Δv | locomotor / m_eff | optional capacity | affinity scale; optional `j ≤ μ_s N dt` | reservoir on realized ΔK |
| Environmental horizontal | body | no (Gentle absorb) | site forces | no PE |
| Body static hold/breakaway | m_eff | **yes** | `j_max = μ_s N dt`, `N=m_eff g` | zero work on hold |
| Body kinetic BNLT | m_eff | receipt yes | `a = μ_k g` (= μ_k N/m_eff) | dissipates KE |
| FREE static FOST | obj.mass | **yes** | `N=m g`, `j_max=μ_s N dt` | zero on hold |
| FREE kinetic FOGF | obj.mass | receipt | `a = μ_k g` | dissipates KE |
| Vertical gravity FGG | entity mass | no as friction N | `vz -= g dt` | no SES PE |
| SES climb | m_eff / mass | height PE | `W = m g Δh` | **PE_AUTHORITY_SES_DDA** |
| Face-sweep blocker | — | no | topology reject | work/PE = 0 |
| Contact impulse | contact masses | collision normal | impulse solver | not terrain N |
| Held-load | held masses | via holder m_eff | EHL sum once | SES/BNLT share m_eff |

**Every current friction N:** `N = mass × g` or `N = m_eff × g`. **No `n_z`.**

---

## 3. Normal-source inventory

Full comparison: `results/.../NORMAL_SOURCE_OPTIONS.md`.

| ID | Source | Authoritative? | For grounded N? |
|---|---|---|---|
| A | Centre analytic n̂ from bilinear `h(x,y)` | Geometry query; diagnostic for force today | **Best V1 diagnostic** |
| B | G2B centre+8 ring heights / samples | Classification only | Classification gate, not N authority |
| C | Aggregated ring normals | Diagnostic if computed | Future PARTIAL only with care |
| D | SES/DDA face crossings | Topology / PE | Not terrain support normal |
| E | Face-sweep hit axis | Barrier evidence | **Forbidden** as support N |
| F | Contact impulse normals | Collision response | Not terrain support |

**Do not confuse** terrain `n̂`, collision face normals, contact impulse normals, optical response, or body orientation.

---

## 4. Projected normal-load definition

```text
g_vec = (0, 0, -g)
n_hat = (-h_x, -h_y, 1) / ||(-h_x, -h_y, 1)||     # CSG analytic
N_flat = m_eff · g                                  # current law
N_proj = m_eff · g · n_z                              # candidate
g_t   = g_vec - (g_vec · n_hat) n_hat               # OUT OF G2D SCOPE
```

`n_z ∈ (0,1]` on upward-facing patches; decreases as slope steepens.

### Intermediate-stage consistency (central)

Enabling **active** `N_proj` with `g_t = OFF`:

1. Bodies do **not** spontaneously slide downhill (no `g_t`).  
2. Static capacity `μ_s N dt` **shrinks** on slopes → breakaway easier under same MOVE/env forces.  
3. If kinetic rewritten as `a = μ_k N/m = μ_k g n_z`, deceleration **shrinks** → longer slides without downhill drive.  
4. Result is a **misleading half-slope model**.  
5. Therefore active G2D must **not** precede tangent gravity (and SES PE migration readiness).

**Diagnostic shadow** avoids all of the above: physics identical to parent; receipts expose `N_flat` vs `N_proj`.

Full analysis: `results/.../INTERMEDIATE_STAGE_CONSISTENCY.md`.

---

## 5. Recommended policies (binding)

| Decision | Choice |
|---|---|
| Stage policy | **A — Diagnostic shadow first** |
| Active physics now? | **NO** |
| Tangent gravity prerequisite for active N? | **YES** (or atomic later slice) |
| SES smooth-slope PE prerequisite for active N / g_t? | **YES** |
| SES PE prerequisite for diagnostic shadow? | **NO** |
| V1 normal source | **Centre analytic CSG n̂** |
| Future active source | Centre on FULL; bounded aggregate only if PARTIAL policy later justifies |
| Support eligibility (future active) | FULL eligible; PARTIAL diagnostic-only or deferred; EDGE/LOSS/AIRBORNE → no ground N |
| Body mass | `m_eff = body_mass + held_load` (EHL once) |
| FREE mass | `ResourceObject.mass` |
| Entity scope | BODY + experimenter + FREE; HELD deferred as independent |
| Runtime seam (future) | One shared normal-load query at BNLT/FOST/FOGF prep; static+kinetic consume once |
| G2B reorder for diagnostic? | **NO** |
| G2B reorder for same-tick LOSS-gated active N? | Possibly later; not required for shadow |
| G2C2 taxonomy change? | **NO** (`CLIFF_NZ_CUTOFF` remains reserved) |
| Face-sweep normals for support N? | **NO** |
| Next implementation slice | **`G2D_DIAGNOSTIC_NORMAL_LOAD_SHADOW`** |

---

## 6. Energy authority

```text
ONE_PE_AUTHORITY = PE_AUTHORITY_SES_DDA
NORMAL_PROJECTION_CHARGES_WORK = NO
NORMAL_PROJECTION_CHANGES_PE = NO
```

Projected N (even when later active) may change **traction limits only**. It must not debit climb work, credit downhill work, alter `support_z`, create continuous PE, reinterpret face-sweep barriers, or free-lift.

Details: `results/.../ENERGY_AUTHORITY_AUDIT.md`.

---

## 7. Numerical / status contract (future)

Statuses (suggested):

- `PROJECTED`  
- `FLAT_EQUIVALENT` (`n_z ≈ 1`)  
- `NOT_ELIGIBLE_AIRBORNE`  
- `NOT_ELIGIBLE_SUPPORT_LOSS`  
- `NOT_AVAILABLE_DISCONTINUITY`  
- `NOT_AVAILABLE_GEOMETRY`  
- `INVALID_MASS`  
- `DIAGNOSTIC_ONLY`

Fallback for **active** physics must never silently restore extra traction near invalid geometry. Prefer `NOT_ELIGIBLE` / `N=0` over quiet flat-N when discontinuity is known.  
For **diagnostic** shadow: always compute when CSG available; mark status; never feed friction.

Epsilons: own in one module; reuse CSG `EPS_FLAT`; do not scatter.

---

## 8. Snapshot / restore / cognition / prospective

- Serialize: config/profile + counters only; **no** normal grids/caches.  
- Missing key → OFF (legacy presets).  
- Restore: no false breakaway / friction double-hit.  
- Cognition: no n̂ / N / status tokens.  
- Prospective: **APPROXIMATE / NOT_ESTABLISHED** for full G2D parity today — centre height may exist; projected N + support gates not in cognition path.

---

## 9. Performance

- Centre analytic normal: O(1) corner fetches (same as CSG height).  
- Budget: **≤1 normal-load result per entity per scientific tick**, shared by static+kinetic.  
- Do not re-run 9-point G2B stencil solely for N.  
- Caches: derived, non-authoritative, mutation-invalidated, non-serialized.

---

## 10. Acceptance tests (future implementation)

See Part 20 of this audit / `FINAL_REPORT.md`. Budget ≤250 ticks; no long scientific run. Diagnostic shadow tests assert **bit-equivalence** of parent physics plus receipt presence.

---

## 11. Hard blockers for active G2D

| Blocker | Severity |
|---|---|
| Half-slope inconsistency without `g_t` | **Hard** for active N |
| SES still sole continuous height PE owner; no smooth-slope PE split | **Hard** for active slope energy / `g_t` |
| Prior-tick G2B class if same-tick LOSS must gate N | Soft for shadow; medium for active LOSS gating |

**BLOCKER for diagnostic shadow = NONE.**

---

## 12. Exact next slice

```text
RECOMMENDED_NEXT_SLICE = G2D_DIAGNOSTIC_NORMAL_LOAD_SHADOW
```

Scope of that slice (when approved):

- New Acanthostega-only child preset of face-sweep (or G2C2 if face-sweep not required — prefer face-sweep parent so discontinuity status is available).  
- Mechanism: researcher-only normal-load query + receipts.  
- Physics: **identical** to parent (`N_flat` still drives traction).  
- Analyzer/Observer: compact banner + bounded fields.  
- No tangent gravity, no PE change, no G2C1 taxonomy change.

After diagnostic evidence: architecture revisit for atomic **active N + tangent gravity** under SES PE decomposition.

---

## Status block

```
FRESHNESS_CHECK = PASS
G2D_ARCHITECTURE_COMPLETE = YES
G2D_IMPLEMENTATION_STARTED = NO
CURRENT_BODY_NORMAL_LOAD = m_eff * g
CURRENT_FREE_OBJECT_NORMAL_LOAD = mass * g
PROJECTED_NORMAL_LOAD_FORM = m_eff * g * n_z
RECOMMENDED_NORMAL_SOURCE = CENTRE_ANALYTIC_CSG_N_HAT
RECOMMENDED_SUPPORT_ELIGIBILITY = FULL_ELIGIBLE__PARTIAL_DIAGNOSTIC__EDGE_LOSS_AIRBORNE_NO_N
RECOMMENDED_ENTITY_SCOPE = BODY_EXPERIMENTER_AND_FREE_OBJECT
RECOMMENDED_RUNTIME_SEAM = SHARED_QUERY_AT_TRACTION_PREP_ONE_RESULT_PER_ENTITY_TICK
ACTIVE_NORMAL_LOAD_READY_NOW = NO
DIAGNOSTIC_SHADOW_REQUIRED_FIRST = YES
TANGENT_GRAVITY_PREREQUISITE = YES
SES_SMOOTH_PE_DECOMPOSITION_PREREQUISITE = YES
G2B_REORDER_REQUIRED = NO
G2C2_TAXONOMY_CHANGE_REQUIRED = NO
ONE_PE_AUTHORITY = PE_AUTHORITY_SES_DDA
NORMAL_PROJECTION_CHARGES_WORK = NO
NORMAL_PROJECTION_CHANGES_PE = NO
TANGENT_GRAVITY_IMPLEMENTED = NO
PASSIVE_SLOPE_SLIDING_IMPLEMENTED = NO
CONTINUOUS_PE_IMPLEMENTED = NO
SUPPORT_Z_AUTHORITY_CHANGED = NO
RADIUS_FACE_SWEEP_CHANGED = NO
TIKTAALIK_PHYSICS_CHANGED = NO
PREVIOUS_ACANTHOSTEGA_PRESETS_CHANGED = NO
COGNITION_CHANGED = NO
SCIENTIFIC_VALIDATION_RUN = NO
LONG_RUN_EXECUTED = NO
TOTAL_SIMULATED_TICKS = 0
BLOCKER = NONE
RECOMMENDED_NEXT_SLICE = G2D_DIAGNOSTIC_NORMAL_LOAD_SHADOW
```
