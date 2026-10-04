# ACANTHOSTEGA — Continuous Surface Physics G2 Architecture
**(energy / force audit ONLY — no implementation)**

**Date:** 2026-09-28 (Europe/Oslo, UTC+2)  
**Repo:** `<repository-root>` (lab)  
**Parent (G1):** `ACANTHOSTEGA_PHASE_C_CONTINUOUS_SURFACE_GEOMETRY`  
**Flags today:** `HEIGHT_PHYSICAL_EFFECTS_ACTIVE=YES`, `NORMAL_PHYSICAL_EFFECTS_ACTIVE=NO`  
**SCIENTIFIC_VALIDATION_RUN:** NO  
**Method:** static code inspection of `runtime.py`, `body_orientation.py`, `locomotion_profile.py`, `flat_ground_gravity.py`, `surface_elevation_support.py`, `body_normal_load_traction.py`, `free_resource_object_ground_friction.py`, `free_resource_object_kinematics.py`, `continuous_surface_geometry.py` (+ contact/acoustic call sites). Part B tick budget: 0 sim ticks.

---

## Central question

Minimal scientifically consistent way to activate analytic `n̂`:

```text
analytic n̂ → support reaction → normal load → tangent-plane gravity → surface friction/traction
```

without double-counting height PE already owned by SES DDA (`m·g·Δh` debit / block / micro-downhill dissipate / large-downhill → airborne).

**Verdict preview**

| Gate | Answer |
|---|---|
| ONE_PE_AUTHORITY_IDENTIFIED | **YES** — SES DDA is the sole height-transition PE authority today |
| SES_DECOMPOSITION_REQUIRED | **YES** — before any continuous slope PE / `g_tangent` |
| STATIC_TRACTION_REQUIRED_BEFORE_SLOPE_SLIDING | **YES** — BNLT/FOGF are kinetic-only |
| RADIUS_AWARE_SUPPORT_REQUIRED_BEFORE_NORMAL_PHYSICS | **YES** — before `N = m_eff g n_z` / full slope forces |
| Recommended first G2 slice | **G2A_STATIC_TRACTION_THRESHOLD** (force-side); radius-aware + SES split are hard prerequisites for full normal physics |

---

## B1. Current pipeline map (from code)

`PhysicalSystemRuntime.step(n)` = `begin_tick()` then `finish_tick()` per tick.

### Body — single-agent (`runtime.py`)

| Stage | File / function | Reads | Mutates | Energy / receipt | Authority |
|---|---|---|---|---|---|
| Cognition / select action | `begin_tick` → `run_cognition_before_action` | obs, cognition | `last_selected_action`, motor | none (decision) | cognition |
| Discrete MOVE impulse | `realize_discrete_action` / `apply_composite_motor` | motor, work budget | `body.vx/vy`, reservoir | action/motor work ledgers | discrete_action_work / endogenous_motor_work |
| Surface traction (affinity MOVE gate) | `_apply_surface_traction` | affinity cell | scales impulse request | traction receipts | surface_affinity_traction |
| Site forces + CoM integrate | `finish_tick` → `step_orientation_mechanics` → `integrate_com_translation` | sites, terrain, ambient, BNLT ctx | `body.x/y/vx/vy`, deformation | locomotion receipt; BNLT friction meta | orientation + locomotion_profile |
| BNLT Coulomb (if active) | `apply_body_coulomb_to_velocity` inside integrate | grounded, μ_k, N=m_eff·g | `vx,vy` | `BODY_NORMAL_LOAD_TRACTION_STEP` | BNLT |
| SES DDA gate (horizontal proposal) | `commit_body_elevation_gate` | x0,y0→x1,y1, support heights | may revert pose; debit reservoir | `SURFACE_ELEVATION_TRANSITION` | **SES (PE / block)** |
| Gentle rest after self-drive | `apply_ground_rest_after_self_drive` | profile, BNLT bypass | may snap v→0 | rest meta | locomotion_profile (bypassed if BNLT) |
| Vertical gravity / support | `integrate_body_vertical` → `integrate_vertical_entity` | z,vz, `support_z_for_entity` | z,vz,grounded | FGG vertical step receipt | FGG; support height from SES/CSG oracle |
| Manipulators | `resolve_shared_world_manipulators` | grasp state | held object poses | manipulator receipts | manipulators |
| Spatial index reconcile | `reconcile_contents` | poses | index | rebuild reason | spatial_contents |
| Contacts → impulses → acoustics | body/object, object/object, held/foreign | poses, radii, z intervals | velocities / poses | contact + impact acoustic | contact modules |
| LPS end-of-tick | `step_end_of_tick` | emissions | wavefronts | signal events | LPS |

**Important order fact (Phase C comment at `runtime.py` ~2093):**  
horizontal CoM (+ BNLT + SES gate) → **then** vertical FGG → **then** contacts. Geometry query for support happens inside SES gate / `support_z_for_entity` (CSG bilinear when ON), not as a free-standing mid-pipeline stage.

### FREE ResourceObject

| Stage | Where | Notes |
|---|---|---|
| Horizontal kinematics + FOGF | `free_resource_object_kinematics` → `plan_free_object_horizontal_step` | Coulomb kinetic if grounded; N uses object mass·g |
| SES gate | `commit_free_object_elevation_gate` | same PE/block authority as body |
| Vertical | FGG `integrate_vertical_entity` for objects (with body vertical pass / world vertical) | inelastic support |
| Pair contacts | after body vertical, in finish_tick contact block | vertical filter uses z |

### HELD ResourceObject

Follows effector / holder; vertical offset via FGG held policy; foreign-body contact + translational impulse mediation after body contacts. No independent FOGF while held.

### Experimenter / TwoAgentRuntime

- Experimenter mutations (column transfer / deltas) are transactional and SES-checked for free PE under grounded occupants.  
- `TwoAgentRuntime` shares one world: deferred manipulator/contact resolution once per world tick; each slot still runs begin/finish with `_defer_manipulator_world` patterns. Same PE authorities.

---

## B2. Existing energy authorities

| Mechanism | Creates / transfers / dissipates | Ledger |
|---|---|---|
| MOVE / discrete action | Spends work → Δv | `last_action_work_ledger` (reservoir debit) |
| Endogenous motor | Force drive ↔ work | `last_motor_work_ledger` |
| Held-load / EHL | Inertia & work accounting for held mass | effector_work_held_load state |
| Uniform gravity (FGG) | vz integration with g; **no explicit m·g·z PE ledger** | FGG vertical step receipt |
| Flat / continuous support | Inelastic clamp to support_z; kill penetrating vz | FGG; support_z from SES/CSG |
| SES uphill | **Debit `m·g·Δh` from mechanical_work_reservoir or BLOCK** | `SURFACE_ELEVATION_TRANSITION` |
| SES downhill micro | Dissipate | same |
| SES large downhill | Loss of support → airborne | same |
| BNLT | Kinetic friction dissipates horizontal KE; N=m_eff·g | BNLT receipts |
| FOGF | Same for FREE objects | FOGF receipts |
| Contact impulses | Exchange / dissipate KE | contact impulse receipts |
| Inelastic support | Removes normal kinetic component at ground | FGG |
| Deformation work | Actuator / viscous / residual | orientation deformation meta |

**Findings**

- Explicit **`m·g·z` PE** appears in **SES climb debit** (`m·g·Δh`), not as a stored world potential field.  
- FGG implies gravitational acceleration but does **not** maintain a PE ledger.  
- Reservoir debited: MOVE, motor, SES uphill, deformation actuator.  
- KE changed without reservoir: BNLT/FOGF friction, inelastic support, contact dissipation, micro-downhill.  
- **Global conservation is not claimed**; local ledgers + intentional dissipation.

**ONE PE authority for height transitions today:** SES DDA.  
Continuous CSG height is geometry for support samples — **not** a second PE channel (`NORMAL_PHYSICAL_EFFECTS_ACTIVE=NO`).

---

## B3. G2 variants

### Variant A — SES remains full energy gate

```text
n̂ affects support geometry framing + friction orientation only
g_tangent = OFF
SES keeps m·g·Δh debit/block
```

- **Pros:** no double PE; smallest physics change; keeps G1 contracts.  
- **Cons:** no passive slope sliding; active locomotion still discretely gated; “normal physics” incomplete.  
- **Fit:** safe interim if paired with static traction + optional `N` framing — still not full slope.

### Variant B — Continuous gravity replaces SES energy

```text
g projected onto tangent; PE via force integration
SES drops micro-uphill PE charges; keeps topology/ledge gate only
```

- **Requires SES decomposition first.**  
- Risks without it: free uphill if SES removed too early; double debit if SES kept; reservoir / tick-order breaks; preset drift.  
- **Not viable as first slice.**

### Variant C — Hybrid by transition class

```text
continuous slope physics inside smooth patch
SES handles steps / ledges / scars / support-rise
```

- Attractive long-term.  
- **Hard:** bilinear is C⁰ with discontinuous derivatives at cell edges — cell-centre Δh can look like ramps. Need deterministic classifiers (smooth patch vs genuine step vs scar vs ledge vs support-rise).  
- **Prerequisite:** SES decomposition contract + tests for classification stability under WRAP and sparse deltas.

### Variant D — Delay tangent gravity

```text
activate normal-based support reaction / N projection / friction frame
keep gravity vertical + SES PE authority
```

- Energetically safest for PE.  
- Risk: on steep `n̂`, vertical `mg` + tilted N framing can look artificially stable if static cone missing.  
- Still needs careful `n_z` floor and preferably radius-aware support before trusting N(n̂).

**Chosen strategic path:** **D then C** — never B without decomposition. A alone is insufficient for the central question but is the PE-safe envelope for early force framing.

---

## B4. Normal load

Today: `N = m_eff · g` (vertical), `m_eff` includes held mass once via EHL when ON.

| Q | Answer |
|---|---|
| Flat (`n_z≈1`) | `N → m_eff g` — matches today |
| Steep slope | `N = m_eff g n_z` shrinks; friction capacity drops; needs static cone + loss-of-support |
| Held mass | Must remain **once** in m_eff (EHL contract) |
| Environmental forces | Should **not** silently inflate N in G2A; optional later via explicit force balance |
| Negative N | Clamp to 0 → lose support / airborne; never attract through ground |
| Lose support | Already: SES large drop, FGG airborne, `|vz|` / gap logic — extend with N≤0 / steepness cutoff |
| Radius / support points | Single COM sample cannot represent multi-point unload; **radius-aware required before trusting N(n̂)** |
| Enable `n_z` before radius? | **No** for production physics; diagnostic-only maybe |
| BNLT / FOGF impact | Both consume N; must share one N authority |
| Morphology coupling | Optional later; not required for G2A static traction |

**Decision:** keep `N = m_eff·g` until radius-aware support exists; then introduce `N = m_eff·g·n_z` (or force-balance N) under one authority.

---

## B5. Tangent-plane gravity

```text
g_vec = (0,0,-g)
g_n = (g_vec·n̂) n̂
g_t = g_vec - g_n
```

- Map `g_t` into xy via rejecting world-z or projecting onto local tangent basis from (∇h).  
- **z policy:** prefer kinematic support constraint `z = h(x,y) - he` while grounded (FGG already clamps); do not double-integrate PE.  
- Work/PE: either SES keeps PE (Variant D/A) **xor** continuous PE via ∫ F·dx (Variant B/C) — **never both**.  
- Slip when `|mg_t| > μ_s N` (needs static). Kinetic: oppose `g_t` + velocity with `μ_k N`.  
- Airborne: **no** support friction / no surface `g_t`.  
- `n_z≈0`: cutoff → lose support (cliff), do not apply infinite tangent.  
- FREE objects: same FOGF N authority; bodies: BNLT.

**Decision:** do **not** implement `g_tangent` until SES decomposition + static traction land.

---

## B6. Static vs kinetic traction

BNLT/FOGF today: kinetic Coulomb only (+ Gentle `v_stop` when BNLT off).

- Passive `g_tangent` without μ_s → perpetual creep on any slope.  
- **STATIC_TRACTION_REQUIRED_BEFORE_SLOPE_SLIDING = YES.**  
- Prefer affinity-derived `μ_s ≥ μ_k` (same non-semantic affinity channel); avoid terrain-type labels.  
- Replace magic `v_stop` under BNLT path with static cone rest; keep Gentle path for non-BNLT presets.

---

## B7. SES decomposition

| Responsibility | Recommendation |
|---|---|
| Smooth slope traversal PE | **REPLACE** later by continuous PE *only after* split |
| Step / ledge blocking | **KEEP** |
| Conservative surface mutation / support-rise reject | **KEEP** |
| Loss of support / airborne | **KEEP** (extend with N≤0 / cliff) |
| Discontinuity crossing | **KEEP / SPLIT** classifier |
| Climb work accounting | **KEEP** until continuous PE owns it |
| Micro-downhill dissipate | **KEEP** or **SPLIT** to friction+g_t later |
| Contact/topology validation | **KEEP** |

**SES_DECOMPOSITION_REQUIRED = YES** before Variant B/C slope PE.

---

## B8. Bilinear geometry limitations

- C⁰ height, discontinuous ∇h at patch edges, single-point support, no pitch/roll, WRAP seam, sparse pits/embankments.  
1. Tangent physics possible only with clamps + classifiers + preferably multi-point support.  
2. Slope/gradient clamp: **yes** for first activation.  
3. Cliff classification: **yes** (`n_z` / Δh thresholds).  
4. Radius-aware before full G2 forces: **YES**.  
5. Single-point can balance on unrealistic peaks: **yes — defect class**.  
6. Narrow pits between samples can be “stepped over”: **yes**.  
7. Footprint sampling: **required before trusting N(n̂) / g_t**.

---

## B9. Dependency order

```text
Order 2 (chosen):
G1 → radius-aware support points → (static traction) → SES decomposition → normal-load n_z → g_tangent
```

Force-only Order 1 (normal physics before radius) rejected for production.

**Parallelizable early force slice:** static traction on **current** vertical N (no n̂ required) — does not violate Order 2 for *normal* physics.

---

## B10. Dynamic terrain mutation

Already: column transfer / deltas are atomic; SES rejects free PE under grounded occupants; CSG samples live columns (no write-back).

G2 must keep:

- atomic mutation;  
- invalidate geometry caches;  
- re-evaluate support (loss / rise reject);  
- no forced free lift;  
- scientific receipts for support invalidation;  
- no mid-tick silent normal change without the same gate.

---

## B11. Contact and acoustics

- Vertical contact filters already use z intervals — slope-aligned support must not spam impact acoustics every grounded tick.  
- Support reaction ≠ impact. Acoustics only from resolved dissipative impacts / landings.  
- Position correction must remain horizontal-contact authority; do not let continuous normal invent a second penetration solver in G2A.

---

## B12. Agent observability

Researcher-only: raw n̂, ∇h, coefficients, flags.  
Agent may feel: slip, harder climb (work), failed SES climb, vestibular ω, passive descent via motion — **no** symbolic SLOPE/CLIFF/UPHILL tokens.

---

## B13. Prospective simulation

Prospective paths today approximate locomotion / work; full SES+BNLT+FGG+CSG fork is not established as a cheap shadow physics.

```text
PROSPECTIVE_G2_SUPPORT = NOT_ESTABLISHED
```

Minimal future contract: reuse the same PE authority flags; do not invent a second SES.

---

## B14. Observer / Analyzer contract (future G2)

Observer fields (gated): height, n̂, slope magnitude, g_t, N, static/kinetic state, support status, slip, PE/KE/work ledger, SES class, mutation provenance.  
Banner must show `geometry available` vs `physics inactive/active`.

Analyzer detectors: double PE, KE creation, uphill without work, downhill mismatch, friction positive work, unsupported N, g_t while airborne, static beyond limit, duplicate support/impact.

Privacy: keep FORBIDDEN_TOKENS extended for new G2 ids.

---

## B15. Performance (bounds, not code)

| Concern | Bound / seam |
|---|---|
| Geometry queries | O(1) bilinear per sample; avoid re-query storms — cache per entity per tick |
| Radius footprint | start ≤5–9 samples; LRU with column revision |
| Prospective | forbid full deep copies; NOT_ESTABLISHED |
| Observer payload | sample overlays; no dense raster |
| Analyzer history | capped receipts (existing history_limit pattern) |

---

## B16. Required invariants (pre-implementation)

1. **One PE authority per height transition** (SES xor continuous PE).  
2. Friction never creates mechanical energy.  
3. Ideal support reaction does no work.  
4. Airborne ⇒ no support friction / no surface g_t.  
5. n̂ derives only from authoritative geometry oracle.  
6. No renderer physics.  
7. Affinity stays non-semantic.  
8. Held mass counted once in m_eff.  
9. Old presets frozen (Tiktaalik bit-identity).  
10. Snapshot/restore deterministic; omit inactive defaults.  
11. Mutation atomic + SES free-PE reject.  
12. Acoustics only from dissipative impacts.  
13. **No double vertical ensure on restore for non-FGG.**  
14. Tick order: horizontal (+SES gate) → vertical → contacts preserved.  
15. `NORMAL_PHYSICAL_EFFECTS_ACTIVE` flips only with explicit preset/mechanism.

---

## B17. Recommended first G2 slice

### Choice: `G2A_STATIC_TRACTION_THRESHOLD`

Minimal force-side slice that unblocks future slope sliding **without** touching PE or n̂.

1. **Preset:** e.g. `ACANTHOSTEGA_PHASE_C_STATIC_TRACTION` (name TBD)  
2. **Mechanism:** `body_static_traction` (or BNLT flag `static_cone_enabled`) + FOGF twin  
3. **Parent:** current BNLT preset  
4. **Authoritative:** μ_s (from affinity), rest/slip state per body/object  
5. **Derived:** receipts, overlays  
6. **Tick seam:** inside `integrate_com_translation` / FOGF plan **before** kinetic step; replace Gentle `v_stop` when BNLT on  
7. **Equations:** `|F_t| ≤ μ_s N → v=0`; else kinetic `μ_k N` (N remains m_eff·g)  
8. **Receipts:** `STATIC_TRACTION_REST` / `STATIC_TRACTION_SLIP`  
9. **Exclusions:** no g_t, no N(n̂), no SES change, no radius, no pitch/roll  
10. **Tests:** flat rest without v_stop; small force below μ_s N stays; above slips; Tiktaalik/parent OFF; snapshot omit defaults  
11. **Compatibility:** missing key = OFF; frozen fingerprints  
12. **Validation budget:** focused pytest + ≤100 tick probes; no scientific runs  

### Hard prerequisites for *full* normal physics (later slices)

```text
G2B_RADIUS_AWARE_SUPPORT_POINTS
G2C_SES_DECOMPOSITION_CONTRACT
G2D_NORMAL_LOAD_NZ
G2E_TANGENT_GRAVITY_HYBRID
```

---

## Dependency graph

```text
G1 CSG (h active, n̂ inactive)
        │
        ├─► G2A static traction ─────────────────────────────► enables slope later
        │
        ├─► G2B radius-aware support ──► G2D N(n̂)
        │
        └─► G2C SES decomposition ─────► G2E g_tangent (hybrid C)
```

---

## Closing tags (architecture)

```text
G2_ARCHITECTURE_COMPLETE = YES
G2_IMPLEMENTATION_STARTED = NO
ONE_PE_AUTHORITY_IDENTIFIED = YES
SES_DECOMPOSITION_REQUIRED = YES
STATIC_TRACTION_REQUIRED_BEFORE_SLOPE_SLIDING = YES
RADIUS_AWARE_SUPPORT_REQUIRED_BEFORE_NORMAL_PHYSICS = YES
RECOMMENDED_NEXT_SLICE = G2A_STATIC_TRACTION_THRESHOLD
SCIENTIFIC_VALIDATION_RUN = NO
```
