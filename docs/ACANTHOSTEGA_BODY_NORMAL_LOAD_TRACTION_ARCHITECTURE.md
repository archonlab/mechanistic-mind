# Acanthostega Phase C — Body Normal-Load Traction + Passive Sliding V1

**Document type:** ARCHITECTURE AUDIT ONLY  
**Scientific validation:** NOT RUN  
**IMPLEMENTATION_STARTED:** YES  

**Proposed preset:** `ACANTHOSTEGA_PHASE_C_BODY_NORMAL_LOAD_TRACTION`  
**Proposed mechanism:** `body_normal_load_traction`  
**Proposed profile:** `BODY_NORMAL_LOAD_TRACTION_PASSIVE_SLIDING_V1`  
**Parent:** `ACANTHOSTEGA_PHASE_C_SURFACE_ELEVATION_SUPPORT` / `SUBGRID_MICRORELIEF_RAMP_V1`

**Audit method:** static read/grep/import of runtime, action/motor work, Gentle, affinity traction, FREE ground friction, flat-ground gravity, elevation support, held-load accounting, observation privacy, experiment_canonical / acanthostega presets. No mechanism wiring. No physics parameter changes. No long sims (0 probe ticks).

---

## GATE MAP (user questions 1–20)

| # | Question | Answer from current code |
|---|---|---|
| 1 | MOVE impulse site | `begin_tick` → `request_discrete_action` → `_apply_surface_traction` (affinity multiplier) → work alloc → `realize_discrete_action` mutates `body.vx/vy` **before** world advance. Site: `runtime.begin_tick` + `action_work.py`. Quantity is **Δv**, not force (`discrete_action_quantity: DELTA_V_NOT_FORCE`). |
| 2 | Tick order | **Single:** `begin_tick` (cognition + MOVE Δv) → `finish_tick`: planet → CoM integrate (`step_orientation_mechanics` / `integrate_com_translation` when morph\|orient) → Gentle rest → endo motor update → **then** `integrate_body_vertical` → manipulators → `integrate_free_objects` (friction→elev→commit) → `integrate_free_objects_vertical` → contacts. **Two/experimenter:** all `begin_tick` → shared planet → all `finish_tick(skip_planet, skip_resources)` → body–body contact → shared manipulators/FOK/vertical → body–object contacts. |
| 3 | Overlapping velocity modifiers | (a) MOVE Δv + affinity `traction_multiplier`; (b) endogenous motor Δv; (c) CoM env/Φ/ambient scaled by Gentle; (d) `body.drag` (+ terrain `extra_drag`); (e) Gentle `grounded_damping` + `v_stop` when WAIT; (f) FREE-only Coulomb (bodies unchanged today); (g) elevation may block/revert pose / debit work / (FREE) cut `K_normal`. |
| 4 | Double-friction risk | **YES, live on parent.** Phase C elevation config has Gentle ON (`grounded_damping=0.85`) **and** FREE Coulomb ON. Adding body Coulomb **without** bypassing Gentle WAIT damping would stack two dissipators. Affinity traction scales **active** Δv (transmission), not Coulomb dissipation — orthogonal channel, but must not be redefined as a second damper. |
| 5 | Grounded state | From `flat_ground_gravity`: `grounded ⇔ \|z−support\|≈0 ∧ \|vz\|≈0` (support from elevation when SES ON). Flag on `body.grounded`. Horizontal body step runs **before** vertical; friction/traction must read **prior-tick** grounded (same FOGF rule). Landing → body ground friction starts **next** tick. |
| 6 | Effective mass L/R/combine/experimenter | `locomotor_mass_with_held_load`: sums **all** HELD loads for `holder_body_id` (LEFT+RIGHT+any). COMBINE does not invent extra mass beyond held objects. Experimenter is an ordinary PSR slot (`cognition` OFF); same helper if effector-work accounting ON. Empty hand: `EMPTY_EFFECTOR_INERTIA_NOT_MODELLED` (no arm mass). |
| 7 | Surface property for μ | Cell deposit → `derive_effective_properties` → `surface_affinity` ∈ [0,1] (neutral 0.5 if empty). FREE: `μ_k = MU_MIN+(MU_MAX−MU_MIN)·clip(aff)` with MU∈[0.5,3.0]. Body affinity traction: `traction_multiplier = clip(1+0.8·(aff−0.5), 0.6, 1.4)`. Sample policy body COM: `BODY_COM_FLOOR_WRAP_V1`. |
| 8 | Body vs FREE friction pairing | Same scalar `surface_affinity`; **independent maps**. FREE = `μ_k(aff)` Coulomb. Body today = affinity **multiplier on MOVE only** (no body Coulomb). V1 body passive sliding should reuse FREE’s `μ_k` map; keep MOVE transmission on existing multiplier (or kinetic-capacity clamp). Do **not** retarget FREE paths. |
| 9 | How to clamp MOVE | Today: affinity scales nominal Δv **before** `v_max`, then work budgets scale realization. **Do not invent** `STATIC_FRICTION_FORCE_BALANCING` (still `NOT_IMPLEMENTED` on FREE). V1: keep affinity active clamp; optional future `|J| ≤ μ_k N Δt` kinetic-capacity ceiling **without** static-cone recipes. Airborne: no ground traction scale (gate). |
| 10 | Work accounting | Positive MOVE KE increment debits `mechanical_work_reservoir` via `action_work` / shared alloc with motor+deformation. Affinity changes requested Δv → changes work request (already). Friction **never creates KE**, never credits reservoir (`reservoir_credit=false` on FREE receipts). Climb work (SES) already debits reservoir with `m_eff`. Passive Coulomb only dissipates K. |
| 11 | Airborne gate | **Missing today** for affinity traction (MOVE scales even if airborne). FOGF airborne: conserve `vx,vy`, no ground friction, no air drag. Body V1 **must** gate Coulomb + affinity ground traction on `body.grounded` (prior tick). MOVE Δv in air without ground reaction is a separate policy; recommend no ground-μ coupling while airborne. |
| 12 | Gentle bypass policy | **Required.** When body Coulomb ON: grounded WAIT path must **bypass** Gentle `grounded_damping` + `v_stop` (and not stack with body.drag as a second “friction”). Mirror FOGF: Coulomb **only** vs legacy damp — **never both**. Env-force absorb (`traction_threshold`) may remain as support-force nulling of weak crawl **or** be reviewed so it does not duplicate rest-kill; default recommendation: keep absorb, replace **velocity** damp/snap with Coulomb. |
| 13 | Elevation interaction | Order already: horizontal proposal → SES gate → vertical. Body: `integrate_com_translation` then `commit_body_elevation_gate` (work debit / block / support loss → airborne). Friction must use **source-cell** affinity; elevation does not redefine μ. Large downhill → airborne → next-tick no ground friction. Continuous slopes **not** in SES V1. |
| 14 | Continuous normals first? | **NO** for V1 on flat + microrelief steps. `N = m_eff·g` is vertical under FGG/SES flat support. SES “normals” today are **travel-direction step normals** for FREE `K_normal` climb pay — not continuous surface fields. Continuous `n̂(x,y)` only required for true slopes (tangential gravity / `N=mg·n̂`). |
| 15 | WRAP | Toroidal `wrap_coord` on CoM integrate and FOK drift. Affinity/μ sample: `BODY_COM_FLOOR_WRAP_V1` = `floor` then wrap (same as FREE `OBJECT_SUPPORT_FLOOR_WRAP_V1`). No multi-cell footprint (`FOOTPRINT_MULTI_CELL=NOT_IMPLEMENTED`). |
| 16 | Receipts | Pattern: researcher-only receipt + bounded history + Analyzer section + banner; `agent_accessible=false`. Propose `BODY_NORMAL_LOAD_TRACTION` / step event; mirror FOGF fields (`mu_k`, `N`, `grounded`, `held_mass`, `dissipated_K`, mode). Affinity MOVE receipts already exist (`SURFACE_TRACTION_APPLIED`) — keep separate. |
| 17 | Cognition privacy | Extend `observation.FORBIDDEN_TOKENS` with mechanism id, receipt names, `N`, `normal_load`, `passive_sliding`, etc. Existing: `surface_affinity`, `mu_k`, `traction_multiplier`, elevation tokens. Do **not** expose grounded/μ into agent observation. |
| 18 | Snapshot | Missing key → OFF; prior presets bit-compatible. When ON: serialize config + body `vx,vy,z,vz,grounded` + mechanism state/history. Mid-slide restore continues Coulomb next tick (FOGF pattern). Default OFF omit state → hash-stable. |
| 19 | Single / two / experimenter seam | Same law per body slot. Two-agent: per-slot CoM in `finish_tick`, shared FOK after; body friction is **per-body** inside CoM integrate / post-self-drive — not inside FREE integrator. Experimenter: ordinary body mass+held load; research supply only tops reservoir — does not bypass friction. |
| 20 | Preset / mechanism naming | Preset `ACANTHOSTEGA_PHASE_C_BODY_NORMAL_LOAD_TRACTION`; mechanism `body_normal_load_traction`; profile `BODY_NORMAL_LOAD_TRACTION_PASSIVE_SLIDING_V1`; parent elevation support. Tiktaalik + all prior Acanthostega presets unchanged (mechanism absent = OFF). |

**Gate decision:** Architecture is dependency-safe to implement as a **child of elevation support** with mandatory Gentle velocity-damp bypass, prior-tick grounded gate, held-mass in `N`, reuse of `surface_affinity`→`μ_k`, and **no** continuous-normal prerequisite. Do **not** invent static-cone force balancing in V1.

---

## 1. Scope

**In V1 (proposed):**
- Acanthostega bodies only (single, two-agent, experimenter slot).
- Grounded horizontal passive sliding: Coulomb kinetic `F=μ_k N`, `N=m_eff g`.
- Active MOVE remains work-metered Δv; ground coupling via existing affinity traction (+ optional kinetic-capacity ceiling later).
- Flat ground + SES microrelief parent; vertical `N`.

**Out of V1:**
- Tiktaalik / prior presets.
- Gait, jump, air traction, air drag.
- Continuous slopes / continuous surface normal fields.
- `STATIC_FRICTION_FORCE_BALANCING` / μ_s cone recipes.
- Multi-cell footprint, gait IK, swing impulse, sound-from-friction, reservoir credit from friction.
- Changing FREE object friction law.

---

## 2. Current causal pipeline (MOVE → pose)

```
begin_tick:
  cognition / forced action
  request_discrete_action(MOVE)           # nominal Δv, mass=_locomotor_mass_kg()
  _apply_surface_traction                 # affinity multiplier before v_max (if ON)
  allocate_shared_work
  realize_discrete_action                 # debit reservoir; commit Δv to body.vx/vy
finish_tick:
  step_planet (unless shared)
  step_orientation_mechanics              # site forces → integrate_com_translation
      Gentle env scale / absorb / drag_eff (+ grounded_damping if WAIT)
      wrap displacement
      commit_body_elevation_gate          # may revert / debit W_climb / set airborne
  apply_ground_rest_after_self_drive      # Gentle v_stop when WAIT
  integrate_body_vertical                 # gravity + support → update grounded
  resolve_shared_world_manipulators
      integrate_free_objects              # FOGF Coulomb → SES → commit
      integrate_free_objects_vertical
  contacts / impulses
```

**Implication for body Coulomb:** insert on the **body horizontal** path (CoM integrate and/or post-self-drive), **not** inside `integrate_free_objects`. Read grounded from **previous** vertical; write dissipation **before** SES pose commit when WAIT sliding, consistent with FOGF “friction → proposal → elev”.

---

## 3. Physics contract (proposed V1 — not implemented)

```
m_eff = body.mass + Σ held_mass(holder)     # when effector_work_held_load ON; else body.mass
N     = m_eff * g                           # g from flat_ground_gravity
μ_k   = MU_MIN + (MU_MAX-MU_MIN)*clip(aff) # same numbers as FREE V1
a     = μ_k * g                             # mass-independent deceleration

grounded ∧ |v|>0 (passive / residual):
  Coulomb kinetic step (FOGF coulomb_kinetic_step semantics)
  friction never increases |v|; stop → exact (0,0) under rest_threshold
  Gentle grounded_damping + v_stop BYPASSED this tick

grounded ∧ MOVE active:
  affinity traction_multiplier scales requested Δv (existing)
  optional: capacity check |m_eff·Δv| ≤ μ_k·N·dt  without μ_s solver
  do not apply full kinetic slide twice on the same realized thrust in a double-count way
  body.drag / Gentle env absorb policy: see §6

airborne:
  no ground μ; conserve horizontal from ground channel; no Gentle ground damp
```

Energy: ΔK from friction ≤ 0; no reservoir credit; SES climb still paid from reservoir / FREE `K_normal`.

---

## 4. MOVE impulse site (Q1)

| Item | Location |
|---|---|
| Request | `action_work.request_discrete_action` — `impulse_scale * v_max` along cardinal |
| Mass | `PhysicalSystemRuntime._locomotor_mass_kg()` → held-aware when EHL ON |
| Affinity | `runtime._apply_surface_traction` → `scale_locomotor_request_before_vmax` |
| Realize | `realize_discrete_action` — clips by positive work budget; writes `body.vx/vy` |
| Timing | Entirely in `begin_tick`, **before** CoM force integrate |

Passive sliding must **not** live in `begin_tick`. It belongs with horizontal integrate / rest, after MOVE Δv is already on the body.

---

## 5. Tick order & grounded (Q2, Q5, Q11)

| Stage | Body | FREE objects |
|---|---|---|
| Decision + MOVE Δv | begin_tick | — |
| Horizontal integrate | finish_tick CoM | manipulators: `integrate_free_objects` |
| Elevation gate | `commit_body_elevation_gate` | `commit_free_object_elevation_gate` |
| Vertical / grounded update | `integrate_body_vertical` | `integrate_free_objects_vertical` |
| Contacts | after vertical | after vertical |

**Grounded for friction:** prior-tick flag (post previous vertical). Same-tick landing does not get Coulomb until next tick. Airborne gate mandatory for body ground μ and for affinity ground transmission.

---

## 6. Overlapping modifiers & Gentle bypass (Q3, Q4, Q12)

| Modifier | When | Role | V1 policy with body Coulomb |
|---|---|---|---|
| Affinity `traction_multiplier` | MOVE realize | Active transmission | Keep; gate on grounded |
| Endogenous motor | after/with site | Separate drive | Unchanged; work-metered |
| Gentle env scale / absorb | CoM | Reduce crawl | Keep absorb; do not treat as μ |
| Gentle `grounded_damping` | WAIT CoM | Extra −c v | **BYPASS when body Coulomb ON** |
| Gentle `v_stop` | WAIT post | Snap rest | **BYPASS; Coulomb rest_threshold owns stop** |
| `body.drag` | always in CoM | Baseline linear drag | Prefer: while Coulomb ON & grounded, treat drag as non-friction baseline **or** document explicit residual — **must not** equal a second μN law. Recommended: keep small baseline drag only if calibration requires; never stack as “friction”. |
| FOGF Coulomb | FREE only | Object slide | Unchanged |
| SES | after proposal | Height energy | Unchanged order |

**Invariant:** Gentle must not stack damping with body Coulomb. Pattern clone: FOGF vs FOK exponential damp — **never both**.

---

## 7. Effective mass / held load (Q6)

`held_loads_for_holder` lists every HELD object for the body id (LEFT, RIGHT, …).  
`effective_mass = body_mass + Σ valid masses`.

Already used by:
- MOVE/motor work metering (`_locomotor_mass_kg`)
- SES body climb `W_climb = m_eff g Δh`

**Normal load:** `N = m_eff g` when EHL ON; else `N = body.mass * g`.  
Experimenter slot: same formula. No special experimenter friction exemption.

---

## 8. Surface μ & body↔FREE pairing (Q7, Q8)

| Consumer | Map | Status |
|---|---|---|
| FREE ground friction | `μ_k(aff)` | Implemented |
| Body MOVE | `traction_multiplier(aff)` | Implemented |
| Body passive slide | `μ_k(aff)` (proposed) | **Not implemented** |

`SURFACE_AFFINITY_REUSABLE = YES`. Independent maps; shared deposit sample. Empty cell → neutral 0.5. Same-tick APPLY_TO_SURFACE: deposit eligibility already NEXT_TICK for affinity traction; body μ sample must keep the same latency.

---

## 9. MOVE clamp & work (Q9, Q10)

1. Affinity scales Δv before vmax.  
2. Work budget may further scale realization.  
3. Friction does not pay for MOVE; it only limits/dissipates.  
4. V1 forbids inventing μ_s force-balance solvers (`STATIC_FRICTION_FORCE_BALANCING=NOT_IMPLEMENTED`).  
5. Optional kinetic-capacity ceiling uses existing μ_k and `N` without new material IDs.

---

## 10. Elevation & continuous normals (Q13, Q14)

- SES V1: discrete microrelief / large step block; **no continuous slopes**.  
- Body Coulomb V1: vertical `N`; no `n̂` field required.  
- After LARGE_DOWNHILL support loss: `grounded=false` → no body ground friction until re-support.  
- Friction sample stays on support cell under COM; elevation changes height/energy, not μ recipe.  
**`CONTINUOUS_SURFACE_NORMALS_REQUIRED_FIRST = NO`.**

---

## 11. WRAP (Q15)

Reuse `BODY_COM_FLOOR_WRAP_V1` for body μ/affinity cell. CoM motion stays toroidal wrap. No footprint sweep (`ENTITY_RADIUS_FACE_SWEEP` remains false in SES).

---

## 12. Receipts, Analyzer, privacy (Q16, Q17)

Proposed researcher surface:
- Banner: **BODY NORMAL-LOAD TRACTION + PASSIVE SLIDING V1 · N=m_eff g · μ(affinity) · GENTLE DAMP BYPASS · NO AIR TRACTION**
- Analyzer section: **BODY NORMAL LOAD TRACTION**
- Receipt kind: `BODY_NORMAL_LOAD_TRACTION`
- `agent_accessible=false`; extend `FORBIDDEN_TOKENS`

Do not leak μ, N, grounded, or mechanism ids into cognition payloads.

---

## 13. Snapshot (Q18)

- Absent config key → OFF; Gentle + affinity behave as parent.  
- ON → config + counters/history + rely on body vertical fields already snapshotted under FGG.  
- Mid-slide: restore `vx,vy,grounded,z` + mechanism enabled → continue next tick.

---

## 14. Single / two / experimenter seam (Q19)

| Runtime | Body Coulomb site |
|---|---|
| Single PSR | Inside that body’s CoM / rest path in `finish_tick` |
| TwoAgentRuntime | Per slot `finish_tick`; shared world FOK unchanged |
| Experimenter | Same physical law; forced MOVE still goes through action_work + affinity + (later) Coulomb |

No third integrator; no experimenter-only slip cheat.

---

## 15. Preset / mechanism naming (Q20)

| Kind | Name |
|---|---|
| Public preset | `ACANTHOSTEGA_PHASE_C_BODY_NORMAL_LOAD_TRACTION` |
| Mechanism id | `body_normal_load_traction` |
| Profile | `BODY_NORMAL_LOAD_TRACTION_PASSIVE_SLIDING_V1` |
| Parent | `ACANTHOSTEGA_PHASE_C_SURFACE_ELEVATION_SUPPORT` |
| Module (future) | `mechanistic_mind/physical_system/body_normal_load_traction.py` |

Inheritance map: copy elevation mechanism map and set `body_normal_load_traction=True`. Gentle remains in the map but its **velocity damp/snap** is bypassed when this mechanism is active (config-gated), analogous to FOK damp bypass under FOGF.

---

## 16. Preservation contract

- Tiktaalik: untouched.  
- Prior Acanthostega presets (through elevation support): untouched when key absent.  
- FREE FOGF law/numbers: untouched.  
- Affinity MOVE multiplier: remains unless a later explicit migration.  
- SES energy accounting: untouched.  
- No gait/jump/air traction.  
- Friction never creates KE / never credits reservoir.  
- Held mass enters `N` when EHL ON.  
- Cognition privacy preserved.

---

## 17. Recommended next implementation slice (dependency-safe)

**Slice A — Passive body Coulomb + Gentle bypass (minimal):**
1. New module + config gated OFF by default.  
2. Preset child of elevation support.  
3. In CoM WAIT / residual path: if mechanism ON ∧ grounded → apply FOGF-equivalent `coulomb_kinetic_step` using `μ_k(aff)` at `BODY_COM_FLOOR_WRAP_V1`, `N=m_eff g`; **bypass** Gentle `grounded_damping` + `v_stop`.  
4. Airborne → no body Coulomb.  
5. Receipts + FORBIDDEN_TOKENS + snapshot + Analyzer banner.  
6. Tests: isolation vs parent, never-both Gentle, mass-independent `a`, held mass raises `N` but not `a`, airborne conserve, SES support-loss gate, Tiktaalik/prior hash OFF, two-agent/experimenter smoke.

**Defer:** μ_s static cone, replacing affinity MOVE multiplier, continuous normals/slopes, multi-cell footprint, air traction, long scientific validation.

**What it replaces/bypasses:** Gentle WAIT velocity damp/snap **only while this mechanism ON**.  
**What stays:** affinity MOVE multiplier, FREE FOGF, SES, FGG, EHL mass helper, tick order skeleton.

**Future validation budget (not run now):** unit ≤30 ticks; stop/slide ≤100; snapshot ≤100; focused ≤200; one rest ≤250 OK; no multi-thousand scientific campaign in first impl.

**Minimal prerequisite (not approximate physics):** implement Gentle bypass seam **in the same slice** as body Coulomb — otherwise refuse to ship (double-friction invariant). Continuous normals are **not** a prerequisite.

---

## Verdict

```
BODY_NORMAL_LOAD_TRACTION_READY = YES
CONTINUOUS_SURFACE_NORMALS_REQUIRED_FIRST = NO
GENTLE_SUPPORT_MUST_BE_BYPASSED = YES
SURFACE_AFFINITY_REUSABLE = YES
HELD_MASS_CAN_ENTER_NORMAL_LOAD = YES
IMPLEMENTATION_STARTED = YES
```

**Blockers:** none that require inventing new continuum physics.  
**Hard policy prerequisite for impl:** Gentle grounded velocity-damp/snap bypass when body Coulomb is ON (never both).  
**Explicit non-goal V1:** `STATIC_FRICTION_FORCE_BALANCING` / continuous surface normals.
