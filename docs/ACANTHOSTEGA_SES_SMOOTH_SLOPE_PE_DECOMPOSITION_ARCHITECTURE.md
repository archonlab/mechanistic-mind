# ACANTHOSTEGA — SES Smooth-Slope PE Decomposition Architecture

**Date:** 2026-09-29 (Europe/Oslo, UTC+2)  
**Status:** ARCHITECTURE / AUDIT ONLY — no physics implementation  
**Repo:** `<repository-root>` · **branch** `main` · **HEAD** `5d0f14cd7968b4d5b190796a2494d348a0e10f48`  
**Parent chain:** G1 CSG → BNLT/FOGF → G2A → FOST → G2B → G2C1 → G2C2 → Radius-Aware Face Sweep → G2D diagnostic normal-load shadow → **this audit**

```text
SES_SMOOTH_SLOPE_PE_DECOMPOSITION_ARCHITECTURE_COMPLETE = YES
IMPLEMENTATION_STARTED = NO
CURRENT_PE_AUTHORITY = PE_AUTHORITY_SES_DDA
CURRENT_PHYSICAL_N = m_eff · g   (FREE: mass · g)
PROJECTED_NORMAL_LOAD_ACTIVE = NO
TANGENT_GRAVITY_ACTIVE = NO
PASSIVE_SLOPE_SLIDING_ACTIVE = NO
CONTINUOUS_PE_ACTIVE = NO
CURRENT_SES_PHYSICS_CHANGED = NO
TOTAL_SIMULATED_TICKS = 0
```

**Method:** Code inspection of SES / FGG / CSG / G2C1 / G2C2 / face-sweep / BNLT / FOST / FOGF / G2B / EHL / G2D shadow; prior architecture packs (`docs/ACANTHOSTEGA_CONTINUOUS_NORMAL_LOAD_G2D_ARCHITECTURE.md`, `results/acanthostega_*`). No mechanism, preset, or force change.

Evidence pack: `results/acanthostega_ses_smooth_slope_pe_decomposition_architecture/`.

---

## 0. Freshness

| Item | Value |
|---|---|
| pwd | `<repository-root>` |
| branch | `main` |
| HEAD | `5d0f14cd7968b4d5b190796a2494d348a0e10f48` |
| Tree | Dirty (Phase C work preserved; no reset/revert/checkout/commit/push) |

**FRESHNESS_CHECK = PASS**

---

## 1. Central question

Not “how do we add downhill gravity?”

**How must gravitational work and PE authority be decomposed so continuous surface traversal and discrete SES topology coexist without accounting for the same height change twice?**

G2D already blocked active `N_projected` without `g_t` (half-slope). This audit blocks active continuous PE / `g_t` / projected N until a single gravitational accounting path is defined.

---

## 2. Current SES PE / work authority (A)

Full pipeline: `results/.../CURRENT_SES_PE_PIPELINE.md`.

```text
proposal (motor / FREE velocity)
  → SES DDA evaluate_path_transitions (+ optional radius face-sweep)
  → MICRO_UPHILL: W_climb = m · g · Δh (body: m_eff; FREE: mass; reservoir or K_normal)
  → MICRO_DOWNHILL: dissipated_pe = m g |Δh|; ke_gain = 0
  → LARGE_UPHILL / face barrier: reject; no debit
  → LARGE_DOWNHILL: support lost; z unchanged
  → LEVEL: no climb work; commit may still snap z to continuous support height
  → accept → commit pose; grounded z = surface_support_height(x,y)
  → FGG vertical (U = m_body g z receipts; mass asymmetry vs SES m_eff)
```

**Answers:**

| Question | Finding |
|---|---|
| Who owns gravitational PE/work today? | **SES DDA** (`PE_AUTHORITY_SES_DDA`; `climb_work` / inelastic descent) |
| Where is Δz authoritative for energy? | **DDA cell-centre height difference** on crossed faces (not continuous path Δz) |
| Where is commit z authoritative? | **Continuous support height** at accepted (x,y) when CSG ON |
| Descent energy? | **Dissipated** (`ke_gain=0`); not returned to reservoir / KE |
| Rejected transitions? | Restore xy; no work debit; face-sweep PE deltas = 0 |
| PE vs acceptance? | Climb work charged **only on accept**; large uphill blocks without debit |
| BODY vs FREE? | Same SES elevation classifier; body pays reservoir; FREE pays K_normal; HELD via EHL once |
| Experimenter? | Same body elevation gate path |

**Dual-height tension:** LEVEL paths can change continuous commit z with **zero** SES climb_work — unpaid continuous PE today. MICRO paths charge DDA Δh which can disagree with continuous endpoint Δz.

---

## 3. Smooth vs topological (B)

Full boundary: `results/.../SMOOTH_VS_TOPOLOGICAL_TRANSITION_BOUNDARY.md`.

**Do not invent semantic `SLOPE`.** Use existing evidence:

| Smooth continuous traversal (future continuous PE candidate) | Topological / discrete (SES gate remains) |
|---|---|
| Accepted path; decisive `LEVEL` / G2C1 `SMOOTH_PATCH_TRAVERSAL` | `LEDGE_BLOCK`, `RADIUS_FACE_BARRIER`, hard-cap ambiguous |
| No support-loss / occupant-rise mutation block | `SUPPORT_DROP_LOS`, `OCCUPANT_SUPPORT_RISE` |
| Grounded; finite CSG; `n_z > 0` | EDGE / AIRBORNE / LOS traction ineligible |
| Prefer FULL for **active** forces; PARTIAL diagnostic | `RADIUS_PARTIAL_CONTACT` classification |

**MICRORELIEF_STEP:** discrete DDA threshold event today; under Policy C migrate **energy** to continuous endpoint ΔU while SES keeps **gate/threshold** semantics.

G2C1 already seeds continuous PE: LEVEL → `delta_h = z_after − z_before`.

---

## 4. PE authority decomposition (C)

Full comparison: `results/.../PE_AUTHORITY_OPTIONS.md`.

| Policy | Verdict |
|---|---|
| A — SES forever sole PE | Reject long-term once slope forces exist (double-count with `g_t`; unpaid LEVEL Δz) |
| B — Split smooth vs topo PE owners | High double-count risk at MICRORELIEF / cell boundaries |
| **C — Unified endpoint ΔU; SES = transition gate** | **Recommended** |
| D — Diagnostic continuous PE shadow | **Required staging** before C goes live |

```text
RECOMMENDED_PE_AUTHORITY_MODEL = POLICY_C_UNIFIED_CONTINUOUS_ENDPOINT_PE
SMOOTH_TRANSITION_AUTHORITY     = CONTINUOUS_SUPPORT_HEIGHT_ENDPOINT_DELTA_U
TOPOLOGICAL_TRANSITION_AUTHORITY = SES_DDA_PLUS_FACE_SWEEP_GATE
```

**Mutex invariant:**

```text
∀ accepted displacement D:
  energy_owner(D) ∈ {SES_DDA, CONTINUOUS_GRAVITY}
  |energy_owner| = 1
```

Until migration: `CURRENT_PE_AUTHORITY = PE_AUTHORITY_SES_DDA`; `CONTINUOUS_PE_ACTIVE = False`.

---

## 5. Continuous PE source (D)

**Prefer:** authoritative start/end **centre support elevation** via the same oracle as commit (`surface_support_height` / CSG when ON):

```text
ΔU = m_eff · g · (z_end − z_start)
```

| Alternative | Why not primary |
|---|---|
| Path ∫∇h·dr | More cost; must match WRAP unwrap |
| Sum of DDA face Δh | Disagrees with continuous commit z |
| Pose Δz alone | OK iff grounded z always equals support height |

**Duplicate accounting warning:** Do **not** charge endpoint ΔU **and** integrate `g_t·v` as independent gravitational debits. For a quasistatic conservative height field, pick one accounting channel (force work **or** endpoint ΔU) with the other diagnostic/check-only, or prove identity within eps.

---

## 6. Tangent gravity readiness (E)

Full: `results/.../TANGENT_GRAVITY_READINESS.md`.

```text
g_n = (g · n̂) n̂
g_t = g − g_n
```

**Seam:** existing horizontal integrate (body CoM / FREE FOST-FOGF) — **no second integrator**. Static cone must see `m g_t` demand; kinetic uses same projected N after activation gate. MICRO_DOWNHILL inelastic must be replaced for smooth patches when `g_t` is live.

---

## 7. Projected normal-load coordination (F)

Full: `results/.../PROJECTED_NORMAL_LOAD_ACTIVATION_GATE.md`.

```text
PROJECTED_NORMAL_LOAD_ACTIVATION_GATE =
  CONTINUOUS_PE_AUTHORITY_ACTIVE
  AND TANGENT_GRAVITY_ACTIVE
  AND STATIC_SLOPE_HOLD_USES_SAME_N
  AND KINETIC_FRICTION_USES_SAME_N
  AND SES_CLIMB_WORK_NOT_DOUBLE_COUNTING
  AND PARENT_CHILD_EQUIVALENCE_WHEN_OFF
  AND G2D_SHADOW_VALIDATED
```

Until then: `CURRENT_PHYSICAL_N = m_eff · g` (shadow may compute `N_projected`).

---

## 8. Static hold / passive sliding (G–H)

Architecture only:

- Hold when `|m g_t| ≤ μ_s N` (BNLT/G2A/FOST; WAIT remains rest).
- Breakaway → kinetic (FOGF/BNLT) + residual `g_t` → downhill via **existing** integrators.
- No `IF_SLOPE_THEN_SLIDE`; no new locomotion subsystem.

---

## 9. SES after decomposition (I)

**SES retains:**

- Topology / discontinuity traversal planning  
- Ledge blocking / support-loss / radius face barriers  
- Ambiguous geometry policy  
- Elevation-gate accept/reject  
- Transition receipts / G2C taxonomy inputs  
- Discrete **threshold policy** (what is climbable)  

**SES stops owning (once Policy C ACTIVE):**

- Separate gravitational PE/work from DDA face Δh for migrated smooth/micro paths  
- Inelastic micro-descent as the sole gravitational energy model on continuous patches  

**Must never** leave both SES climb_work and continuous ΔU live for the same displacement.

---

## 10. Preservation / privacy / observability (J–L)

**Preserve** unless a later explicit child preset implements change: Tiktaalik; all prior Acanthostega presets; face-sweep; G2B; G2C1/C2; support_z / centre elevation authority; G2D shadow behavior; cognition; manipulation; acoustics; identity; materials; snapshot determinism; Observer selected-vs-active.

**Cognition:** no agent access to n̂, PE authority stamps, taxonomy, tangent/friction researcher receipts.

**Minimal receipts (future):** one authority stamp per entity/transition/tick:

```text
pe_authority | continuous_vs_topological | z_start | z_end
ΔU | work_charged | ses_gate | continuous_force | N_mode | g_t_mode
double_count_possible = false
```

---

## 11. Snapshot / restore (M)

Persist: mechanism/config activation flags; true dynamic pose/velocity/reservoirs.  
Recompute: normals, force decomposition, PE diagnostics.  
Do not persist dense derived evidence unless restore determinism requires it.

---

## 12. Validation (N)

Matrix: `results/.../FUTURE_VALIDATION_MATRIX.md` (flat/up/down/steep/hold/slide/DDA-boundary/ledge/LOS/face/PARTIAL/EDGE/AIRBORNE/FREE/BODY/experimenter/held/WRAP/snapshot/parent-child/double-PE/cognition/Tiktaalik).

```text
TARGET_SIMULATED_TICKS = 0
TOTAL_SIMULATED_TICKS  = 0   # this architecture task
```

---

## 13. Recommended next slice

**Not** live PE migration, projected N, or `g_t`.

```text
NEXT_SAFE_IMPLEMENTATION_SLICE =
  CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW
```

Mirror G2D: researcher-only `ΔU_cont` vs SES work receipts; physics still `PE_AUTHORITY_SES_DDA`; parent bit-equivalence; no cognition leakage.

Then later: Policy C live + atomic force cutover under `PROJECTED_NORMAL_LOAD_ACTIVATION_GATE`.

```text
BLOCKER =
  Active N_projected / g_t / continuous PE without Policy C mutex
  would create half-slope dynamics and/or double gravitational accounting.
```

---

## 14. Explicit answers (FINAL_REPORT checklist)

1. **PE/work owner today:** SES DDA (`climb_work` / MICRO_DOWNHILL inelastic).  
2. **Smooth vs topo evidence:** LEVEL / SMOOTH_PATCH_TRAVERSAL + accepted + no ledge/LOS/face barrier + grounded CSG; vs LARGE_*/RADIUS_FACE_BARRIER / SUPPORT_DROP / MICRORELIEF (hybrid).  
3. **Future owners (Policy C):** gate=SES+face-sweep; z=continuous support; ΔU=unified continuous; motor=action_work; g_t=horizontal integrate; N=projected after gate; friction=BNLT/G2A/FOST/FOGF; integrate=existing.  
4. **Double charge?** Forbidden by mutex `energy_owner| = 1`.  
5. **g_t seam:** existing body/FREE horizontal integrate (with static cone).  
6. **Before N_projected physical:** PE authority active + g_t + same-N static/kinetic + no SES double-count + parent-child OFF eq + G2D shadow validated.  
7. **SES role:** becomes **transition/gating** authority; PE moves to unified continuous (Policy C).  
8. **Smallest next slice:** continuous gravitational PE **diagnostic shadow** (not live decomposition).
