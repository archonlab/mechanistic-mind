# Acanthostega Gentle Locomotion Kernel — implementation map

**Status:** forensic analysis only. Kernel not implemented.  
**Frozen public model:** `TIKTAALIK_BETA31` (fingerprint seed 17: `1621ef2c154864d1`).  
**Target line:** `ACANTHOSTEGA_PHASE0` (Phase 0 still shares Tiktaalik runtime token).  
**Evidence tags:** `OBSERVED` (code or ≤250-tick measurement), `DERIVED` (direct numerical consequence of observed equations), `INFERRED` (plausible, not isolated), `UNKNOWN`.

This document is not a scientific claim about organism intention. Motor command and displacement are distinct.

---

## 1. Executive summary

**OBSERVED — why trajectories look “billiard”:**

1. MOVE is a **world-frame velocity impulse** (`body_velocity_impulse_v1`), not a position step. Velocity persists across ticks.
2. Integration is **semi-implicit Euler with `dt = 1` tick**, then **toroidal wrap** (`wrap_coord`). Fast sustained MOVE wraps the 32-cell world; path length can greatly exceed net displacement.
3. After the impulse, **site forces from planet flow / wave / morphology susceptibility** continuously add acceleration. There is **no rest snap** (`v → 0` threshold) on CoM velocity.
4. Public Observer Beta 3.1 additionally stamps **`terrain_geography` + `ambient_physical_dynamics` ON** (`fresh_experiment_default_map`), injecting a **scalar potential field Φ** with force `F += −κ∇Φ` plus **extra drag γ**. Φ is **not geometric height**. Cell-to-cell Φ/γ jumps (including generator discontinuities) change force abruptly.
5. Two-agent contact applies **soft overlap impulses and positional separation after** both bodies have already integrated — extra Δv that is not a locomotor command.

**OBSERVED — why WAIT still moves (the long “drift” users notice):**

- Leftover MOVE inertia **is not** the 250-tick effect. After one `MOVE:E` on factory Tiktaalik, speed fell below `0.025` in **8 WAIT ticks** (seed 17).
- Over `WAIT × 250`, factory Tiktaalik still displaced **~2.17 cells** (path ~2.36) with final speed ~0.022. Planet flow starts at **0** at `t=0` and is generated each `step_planet`; site forces (`flow_coupling × planet.vx/vy × force_scale`) then accelerate the body **without a motor command**.
- `GENTLE_FREE_MOVEMENT` is **not** a rest-stable locomotion kernel: it **raises** `body_orientation.force_scale` 0.15 → 0.50 while softening planet flow. `WAIT × 250` still displaced **~2.41 cells**.

**Recommended Acanthostega-only seam:** keep the shared integrator (`realize_discrete_action` → `step_orientation_mechanics` / lumped `step_physical_body` → wrap → optional contact). Add an **`ACANTHOSTEGA_GENTLE` physics profile** (config + optional mechanism `gentle_terrain_locomotion` **only** on the Acanthostega mechanism map) that retunes **passive damping, rest threshold, locomotor thrust scale, and terrain κ/γ coupling** after forces are sampled and **before** CoM integrate. Default OFF ⇒ numerically Tiktaalik-compatible.

**Reuse without change:** planet stepper, discrete action bridge, work allocator, PUSH/contact modules, cognition, `beta31_mechanism_map()`, Beta 3.1 fingerprint, tick order.

---

## 2. Current causal pipeline

```text
DecisionReceipt (cognition, begin_tick)
    → selected_action / CompositeMotorOutput.locomotion
    → request_discrete_action  (requested Δv, work preview)
    → allocate_shared_work
    → realize_discrete_action  (applies Δv to body.vx/vy; WAIT Δv=0)
    → apply_composite_motor    (neck / osc / push arming; locomotion WAIT on side channel)
    → [end begin_tick; world not advanced]
finish_tick:
    → step_planet              (T, flow vx/vy, matter, wave, optional climate/resources)
    → sample_local_world + mechanical_stage_decomposition  (lumped diagnostic; see §9)
    → step_physical_body       (site_path: skip_mechanical+skip_material)
    → step_internal_medium
    → [resources if not skip]
    → step_orientation_mechanics
          step_deformation
          per-site flow/wave forces
          sample_terrain_force / sample_ambient_force
          CoM: v += (F − drag_eff v) / m;  x += v; wrap
          angular: ω, θ
    → optional endogenous apply_motor_realization (CoM, no torque)
    → update motor_ux/uy for NEXT tick
    → tick += 1; motion / V3 body_after snapshots
TwoAgentRuntime only, AFTER both finish_tick:
    → resolve_soft_contact + apply_push_through_contact
    → simultaneous complementary resources
```

| Link | File | Symbol | Key variables | Units / meaning | Tick place |
|---|---|---|---|---|---|
| Decision | `physical_system/runtime.py` `cognition.py` | `begin_tick` → `run_cognition_before_action` | `selected_action`, `motor_output.locomotion` | discrete token, not displacement | start of tick, **before** physics |
| Composite motor | `composite_motor.py` | `CompositeMotorOutput` | `locomotion`, `push`, `neck` | command channels | `begin_tick` |
| Discrete request | `action_work.py` | `request_discrete_action` | `impulse_scale * v_max * unit(dir)`; clip to `±v_max` | Δv in **cells/tick** (world frame) | `begin_tick` |
| Impulse apply | `action_work.py` | `realize_discrete_action` | `body.vx += dv` | cells/tick; work = +ΔKE vs reservoir | `begin_tick` |
| WAIT | `action_work.py` `actions.py` | WAIT branch | `action_dv_* = 0`; **does not zero velocity** | — | `begin_tick` |
| Planet | `planet/dynamics.py` | `step_planet` | `planet.vx/vy`, `u`, `T`, `M`, `R_A/R_B` | flow field driving site forces | `finish_tick` first |
| Lumped body (orient/morph **OFF**) | `physical_body/dynamics.py` | `step_physical_body` | `ax = flow_coupling*vx_w − drag*vx` (+ wave, endo) | force-like; `/mass` → Δv | `finish_tick` |
| Site path (default ON) | `body_orientation.py` | `step_orientation_mechanics` | `fx = susc * flow_coupling * planet.vx * force_scale` | **force**, then `/mass` | `finish_tick`; lumped mechanical **skipped** |
| Terrain | `planet/terrain.py` | `sample_terrain_force` | `fx = −κ ∇Φ`; `extra_drag = drag_coupling * γ` | Φ scalar field; γ ≥ 0 drag field | inside orientation, **before** drag integrate |
| Ambient | `planet/ambient.py` | `sample_ambient_force` | static horizontal force | Observer Beta 3.1 default ON via stamp | same |
| Integrate v,x | `body_orientation.py` | `apply_net_force_to_com` | `drag_eff = body.drag + extra_drag` | **no v_stop** | after forces |
| Boundary | `planet/topology.py` | `wrap_coord` | periodic `[0, W)` / `[0, H)` | not a bounce wall | after `x += vx` |
| Contact / PUSH | `body_contact.py` `physical_push.py` `two_agent.py` | `resolve_soft_contact`, `apply_push_through_contact` | overlap impulse + 0.08·overlap sep | **after** both bodies stepped | two-agent only |
| Work / resources | `runtime.py` `_apply_resource_steps` | complementary + env resource | may **credit** reservoir; terrain **never** credits | after or interleaved per flags | |
| Receipts | `runtime.py` `motion_diagnostics.py` `diagnostics.py` | `last_v3_body_*`, `build_motion_causal_receipt`, `build_action_decision_receipt` | snapshots; causes list | **after** commit | end `finish_tick` |

**OBSERVED:** There is no Python class `ConsequenceReceipt`. V3 uses `last_v3_body_before` / `last_v3_body_after` plus Analyzer joins. Motion uses `build_motion_causal_receipt`.

**OBSERVED MOVE gain:** `Δv_nominal = impulse_scale * v_max * (dx,dy)`. Factory: `0.35 * 0.30 = 0.105` cells/tick. Same tick, orientation drag reduces realized speed (seed 17 factory after one `MOVE:E`: **0.089**).

---

## 3. State ownership

| State/parameter | Owner | Updated where | Persists across ticks? | Can move body during WAIT? | Tiktaalik-specific? |
|---|---|---|---:|---:|---:|
| `body.vx, vy` | `PhysicalBodyState` | impulse; orientation/lumped integrate; contact; endo motor | **YES** | **YES** (inertia + env) | shared |
| `body.x, y` | body | `x += vx` + wrap | YES | YES if `v≠0` or wrap | shared |
| `body.theta, omega` | body | orientation angular step | YES | rotation ≠ translation; torque from site forces **can** change heading | shared |
| `body.motor_ux, uy` | body | **end of tick** `update_motor_state` | YES (decay) | **YES** next tick if endo ON | shared; default ON |
| `planet.vx, vy, u` | `PlanetState` | `step_planet` | YES (fields evolve) | **YES** via coupling | shared |
| `terrain_potential, terrain_drag, ∇Φ` | planet | generated at init (static fields) | YES (static) | **YES** if terrain enabled (`F=−κ∇Φ` even at WAIT, κ reduced near rest) | stamped ON in public experiment; **OFF** on `tiktaalik_config()` factory |
| ambient force field | planet | init | YES | **YES** if ambient enabled | Observer stamp |
| `mechanical_work_reservoir` | body | action/motor/deformation debit; complementary credit | YES | does not itself translate; empty reservoir **clips** MOVE Δv | shared |
| `deformation`, `deformation_env_force` | body | `step_deformation`; env force stored for **next** tick | YES | **INFERRED** site-cell hops can change F | shared; default ON |
| `push_exertion` | body | composite PUSH arming; cleared in push apply | one-tick arming | only via contact impulse | default **OFF** |
| cognition stores | cognition dict | `begin_tick` **before** impulse | YES | **NO** direct x,y; can choose MOVE later | Tiktaalik maps frozen |
| `locomotor_active` | derived | `MOVE*` or `‖impulse‖>0` | no | gates terrain κ (WAIT near-rest × `wait_force_scale`) | shared |

---

## 4. Terrain model

**OBSERVED** (`planet/terrain.py` module docstring and `TerrainConfig`):

Runtime stores only:

- `terrain_drag` γ ≥ 0  
- `terrain_potential` Φ (scalar)  
- precomputed `∇Φ` (`terrain_grad_y`, `terrain_grad_x`)

**Not stored:** geometric elevation mesh, slope angle, walkable bitmask as a separate layer, “uphill” labels.

**Force law (OBSERVED):** `F = −κ ∇Φ` with `κ = force_scale`, ∇ clipped to `max_gradient`. Extra dissipative term: `drag_eff = body.drag + drag_coupling * mean(γ)`.

**WAIT attenuation (OBSERVED):** if not `locomotor_active` and `speed < kinetic_speed_threshold` (0.025), `κ *= wait_force_scale` (0.20). If WAIT but `speed ≥ 0.025`, **full κ** (`kinetic_wait`).

**Can terrain accelerate without motor?** **YES.** Conservative `−κ∇Φ` does not require `v≠0`. Near rest it is weaker (×0.20) but not zero. Drag extra term is **−γ_eff v** (opposes velocity; zero at rest).

**Directionality:** Φ force is **anisotropic** (depends on ∇Φ). Extra drag is **isotropic** in the linear `−c v` sense (same coefficient both ways). There is **no** coded uphill/downhill of a height field.

**Cell transition impulses:** **INFERRED.** Φ/γ are cell-sampled (footprint/site cells). Crossing a discontinuity (`discontinuity_rate=0.012`, `discontinuity_amplitude=0.55` in structured/Observer stamp) can jump ∇Φ and γ in one tick → abrupt Δa, not a geometric bounce.

**Modes (OBSERVED):**

| Name | What it is |
|---|---|
| `TerrainConfig.mode` `FLAT` / `CORRELATED` / `RUGGED` | generator of Φ and γ |
| `TerrainConfig.enabled=False` | factory `tiktaalik_config()` / `BASELINE_CLIMATE_DEFAULT` **without** mechanism stamp |
| Ecology `GENTLE_FREE_MOVEMENT` | **not** a terrain mode; retunes flow/drag/`force_scale`/`impulse_scale`; climate OFF |
| Ecology `STRUCTURED_TERRAIN_EXPERIMENTAL` | enables `TerrainConfig` CORRELATED + weaker planet flow |
| Ecology `STRUCTURED_WORLD_EXPERIMENTAL` | structured terrain **+** ambient |
| Mechanism `terrain_geography` | `fresh_experiment_default_map()=True` → Observer Apply stamps CORRELATED terrain onto planet if not already enabled |

**Do not call Φ “height.”** It is a force-potential field chosen so `F=−κ∇Φ` plus drag contrast.

---

## 5. Drift and billiard causes

### Confirmed (`OBSERVED` / `DERIVED`)

| Cause | Evidence |
|---|---|
| Velocity persists; WAIT does not clear `vx,vy` | `realize_discrete_action` WAIT Δv=0; docs `COMPOSITE_MOTOR_CONTROL.md`; measurements |
| Linear drag without rest snap | `v ← clip(v + (F − c v)/m, ±v_max)` |
| Continuous environmental acceleration | site `flow_coupling * planet.vx * force_scale`; planet flow **grows after t=0** (`vx=0` at init seed 17) |
| Toroidal wrap of fast trajectories | factory `MOVE:E × 100`: path **23.52** vs displacement **8.48** (wrap) |
| Terrain extra drag + Φ force when stamped | Observer-like: `extra_drag ~ 0.18–0.30` added to `body.drag=0.30` |
| Two-agent contact Δv + positional sep | `resolve_soft_contact` after integrate |
| Endogenous `motor_u` lag drive | updated end of tick; applied next mechanical step if enabled |
| `GENTLE_FREE_MOVEMENT` still passively translates | `WAIT×250` disp **2.41** |

### Probable (`INFERRED`)

- Morphology susceptibility contrast makes site F differ across footprint → torque and curved paths.  
- Deformation-shifted sites sample different cells → apparent “funnels.”  
- Wave term `0.15 * wave_coupling * u * unit(flow)` when flow ≈ 0 uses a coded fallback direction in **lumped** path (`dynamics.py` sign of vx_w). Site path uses zero wave if `‖flow‖<1e-12`.  
- Ambient field on public experiments adds a static bias.  
- Motion receipts may **mis-attribute** site-path motion using **lumped** `mechanical_stage_decomposition` computed from pre-orientation velocity.

### Excluded (`OBSERVED`)

- WAIT as a cognitive “keep moving” action: forced `WAIT` still moves; cognition was **OFF** in diagnostics.  
- Terrain crediting work / metabolic downhill regeneration: `sample_terrain_force` never credits reservoir.  
- PUSH as the source of single-agent WAIT drift: `physical_push` default **OFF**.  
- Re-application of last MOVE token: WAIT request is Δv=0; last action is not replayed.  
- Wall-clock frame rate: integrator uses **tick=1**, not `dt` from FPS.  
- Factory baseline terrain: `tiktaalik_config()` has `terrain.enabled=False`.

### Unknown

- Exact mix of flow vs climate vs ambient vs Φ on a given Observer screenshot without that session’s ecology + mechanism stamp.  
- Whether any historical “hundreds of ticks of sliding” was **wrap + continuous flow** rather than underdamped inertia (inertia alone decays in **tens** of ticks at default `drag/mass`).  
- Two-agent process-order effects on contact for identical seeds (`process_order`).

---

## 6. Baseline measurements

All runs: **cognition_enabled=False**, `PhysicalSystemRuntime.step_forced_action`, **seed=17**, start `(8.5, 16.5)`, world 32×32 WRAP. Python: repo `.venv_psy_web`. **Not** a published scientific result — diagnostic only.

**Configs**

| Label | Construction |
|---|---|
| factory Tiktaalik | `tiktaalik_config()` = ecology `BASELINE_CLIMATE_DEFAULT`, body2 `mass=2`, `drag=0.30`, `v_max=0.30`, `impulse_scale=0.35`, `force_scale=0.15`, **terrain OFF**, **ambient OFF** |
| observer-like | same ecology + `stamp_config_world_subsystems(terrain_geography+ambient ON)` + Observer body overlay `mass=1`, `v_max=0.4` |
| GENTLE | `make_ecology_config(GENTLE_FREE_MOVEMENT)` |
| structured | `STRUCTURED_TERRAIN_EXPERIMENTAL` |

### A. Passive drift

| Run | ticks | displacement | path | final speed | time-to-rest after MOVE (`speed<0.025`) | cell transitions |
|---|---:|---:|---:|---:|---:|---:|
| factory `WAIT×250` | 250 | 2.166 | 2.359 | 0.0224 | n/a (never MOVE); speed stayed &lt;0.025 the whole run | 4 |
| factory `MOVE:E×1 + WAIT×249` | 250 | 2.084 | 2.832 | 0.0226 | **8** WAIT ticks (separate probe) | 12 |
| observer-like `WAIT×250` | 250 | 1.798 | 1.902 | 0.0138 | n/a | 2 |
| observer-like `MOVE:E×1 + WAIT×249` | 250 | 1.833 | 1.999 | 0.0141 | **2** WAIT ticks to &lt;0.025; **never** &lt;0.001 in 80 WAIT (env floor) | 2 |
| GENTLE `WAIT×250` | 250 | 2.410 | 2.440 | 0.0163 | — | 2 |

Factory leftover-MOVE probe (80 WAIT): speed after MOVE **0.089**; after 20 WAIT **0.0037**; then **rose again** to **0.0082** by tick 80 — **OBSERVED** environmental re-acceleration, not pure exponential decay.

Work on WAIT factory: reservoir **2.00 → 2.069** (`DERIVED`: complementary/resource credit, not terrain).

### B. Sustained `MOVE:E × 100`

| Config | displacement | path | mean speed | heading vs +x | work Δ |
|---|---:|---:|---:|---|---:|
| factory | 8.483 | **23.520** (wrap) | 0.233 | n/a (wrapped) | **−2.000** (reservoir emptied) |
| observer-like | 9.275 | 9.289 | 0.092 | cos **0.999**, err **2.04°** | −2.000 |

Work cost tracks **positive KE increment of realized Δv**, not path length. After `v≈v_max`, remaining Δv shrinks (`0.105` then `~0.045`) but **still debits** every MOVE until reservoir ~0.

### C. Directional comparison (`MOVE × 40`)

`MOVE:N=(0,−1)`, `MOVE:S=(0,+1)`, `MOVE:E=(1,0)`, `MOVE:W=(−1,0)` world frame.

| Config | N disp | S disp | E disp | W disp |
|---|---:|---:|---:|---:|
| factory (no terrain) | 9.917 | 9.917 | 9.917 | 9.916 |
| observer-like (Φ+γ+ambient) | 5.437 | 4.684 | 4.107 | 4.854 |

Structured start cell `(iy,ix)=(16,8)`: Φ=0.0123, γ=0.247, ∇Φ=(gx,gy)≈(0.0037, 0.0062). **This is not a height map.** Asymmetry N/S/E/W on observer-like is **Φ/γ/flow/ambient**, not geometric uphill.

**FLAT baseline:** factory `terrain.enabled=False` is the honest flat-field control (no Φ force). Enabling `mode=FLAT` with `enabled=True` still generates fields via `generate_terrain_fields_raw` — do not assume zeros without checking.

### D. Determinism

observer-like `MOVE:E + WAIT×49`, seed 17 twice: **identical** `end_xy` and speed. Seed 18 differs (`disp` 0.171 vs 0.162). **OBSERVED** seed-deterministic for this forced-action, cognition-off path.

---

## 7. Recommended Acanthostega seam

```text
shared integrator (unchanged control flow)
├── Tiktaalik frozen physics profile   (current coefficients; default)
└── Acanthostega gentle locomotion profile
        gated by model_line==ACANTHOSTEGA
        AND mechanism gentle_terrain_locomotion (Acanthostega map only)
        OFF ⇒ same numbers as Tiktaalik path
```

**Exact hook points (minimal):**

1. **`PhysicalSystemConfig`** (or nested dataclass): `locomotion_profile: Literal["TIKTAALIK","ACANTHOSTEGA_GENTLE"]` + numeric knobs. Default `TIKTAALIK`. `acanthostega_config()` may set profile only when mechanism ON.  
2. **`step_orientation_mechanics`** after `Fx,Fy,extra_drag` assembled, **inside** the existing `apply_net_force_to_com` block: apply profile damping / `v_stop` / optional κ scale. **Do not** change `sample_terrain_force` defaults.  
3. **`step_physical_body` mechanical branch** — same profile function so morph/orient-OFF Tiktaalik and future Acanthostega stay dual-pathed.  
4. **Do not** hook `realize_discrete_action` unless thrust scale is profile-specific; if so, branch on profile **without** changing Tiktaalik `impulse_scale` default.  
5. **Do not** hook `resolve_soft_contact` / `apply_push_through_contact`.  
6. **Mechanism registration:** new id **not** in `beta31_mechanism_map()`; Acanthostega map only; snapshot via existing `set_mechanism` / config to_dict.  
7. **Observer:** catalog filter `model_line==ACANTHOSTEGA`.  
8. **Receipts:** stamp `locomotion_profile` + `gentle_terrain_locomotion` boolean on motion/V3 meta (factual flags, not narrative).

Shared: `step_planet`, wrap, work allocator, cognition, two-agent order.

---

## 8. Proposed parameters

Do **not** freeze final values; measurements above only bound the problem.

| Parameter | Existing or new | Physical sense | Applied | Why needed | Tiktaalik risk |
|---|---|---|---|---|---|
| `discrete_action_work.impulse_scale` | existing (0.35; GENTLE 0.55) | MOVE Δv fraction of `v_max` | `request_discrete_action` | active thrust | changing default **breaks** Beta 3.1; profile-local copy only |
| `body.v_max` | existing (2.0-body 0.30; Observer overlay 0.40) | speed clip | integrate + impulse clip | cap locomotor speed | Observer overlay already differs from factory |
| `body.drag` | existing (0.30; GENTLE 0.36) | linear CoM damping | `F − c v` | passive decay | do not retune Tiktaalik |
| `body.flow_coupling` | existing (baseline 0.09) | env flow → F | site/lumped | reduce billiard advection | ecology already retunes this |
| `body_orientation.force_scale` | existing (baseline 0.15; GENTLE **0.50**) | scales all site F | orientation | GENTLE **increased** this — not a rest kernel | leave Tiktaalik 0.15 |
| `terrain.force_scale` κ | existing (stamp 0.08) | `F=−κ∇Φ` | `sample_terrain_force` | soften Φ dominance | only scale when Acanthostega profile ON |
| `terrain.drag_coupling` / γ fields | existing | extra −c v | orientation `extra_drag` | walking-like resistance **if** Φ kept | isotropic; not slope |
| `terrain.wait_force_scale` | existing 0.20 | WAIT near-rest κ | sample_terrain_force | already a rest attenuator | changing it on Tiktaalik experiments changes WAIT drift |
| `kinetic_speed_threshold` | existing 0.025 | WAIT full-κ if sliding | sample_terrain_force | related to rest | Tiktaalik-stamped terrain only |
| **`v_stop_threshold`** | **new** | snap `v=0` when `‖v‖<ε` and no locomotor | CoM integrate | true rest despite env leak | **must be 0 / unused** on Tiktaalik |
| **`passive_damping_extra`** | **new** | additional −c_p v when WAIT | CoM integrate | kill flow-driven crawl | Tiktaalik unused |
| **`env_force_scale_wait`** | **new** or reuse wait_force_scale for **flow/ambient** not only Φ | WAIT should not be advection | site F composition | factory WAIT still moves with terrain OFF | Tiktaalik unused |
| `slope_coupling` | **do not add now** | height·g | n/a | **no height field** | would fake geometry |
| contact `stiffness` 0.25 | existing | overlap impulse | two-agent | keep Tiktaalik contacts | do not scale in locomotion profile |
| `physical_push.push_impulse_scale` | existing | PUSH | contact | keep separate | out of locomotion profile |

---

## 9. Scientific observability

**Present (factual if recorded):**

- selected motor: `last_selected_action`, `last_motor_output.locomotion`, DecisionReceipt  
- applied Δv: `last_action_work_ledger.action_dv_realized` / `action_work_realized`  
- terrain sample: `last_orientation_meta.terrain` (`fx,fy,extra_drag,kappa,locomotor_active,kinetic_wait`)  
- site net F: `last_orientation_meta.net_force`  
- displacement: `body` snapshots; **wrap-naive** `dx` in `build_motion_causal_receipt`  
- work: `last_work_ledger` three-way + complementary  

**Gaps (`OBSERVED`):**

- No first-class ConsequenceReceipt object.  
- `mechanical_stage_decomposition` is **lumped** from `body_after_impulse` + local planet averages; **site path skips lumped mechanics**, so `why_did_it_move` can miss Φ/ambient/site F or mis-label WORLD_FLOW.  
- No split of Δv into `{impulse, env_site, terrain, ambient, drag, contact, endo}`.  
- Contact impulses exist on two-agent receipts, not on single-runtime motion receipt.  
- Profile name not stamped today.

**Needed later (flags, not interpretation):** `locomotion_profile`, `gentle_terrain_locomotion`, `delta_v_impulse`, `delta_v_env`, `delta_v_terrain`, `delta_v_drag`, `delta_v_contact`, `delta_x_wrap_aware`, `work_action`, `work_not_from_terrain`.

---

## 10. Preservation contract

```text
TIKTAALIK_MECHANISM_MAP_CHANGED = NO
TIKTAALIK_BETA31_FINGERPRINT_CHANGED = NO
TIKTAALIK_PHYSICS_CHANGED = NO
TIKTAALIK_TICK_ORDER_CHANGED = NO
ACANTHOSTEGA_ONLY_SEAM_IDENTIFIED = YES
```

---

## 11. Minimal implementation sequence

1. **Profile dataclass + OFF default** on Acanthostega config; Tiktaalik untouched. Tests: Beta 3.1 fingerprint; forced WAIT/MOVE 250-tick equality Tiktaalik vs Acanthostega-with-mechanism-OFF.  
2. Apply profile **only** in CoM integrate (damping + `v_stop`); no terrain rewrite.  
3. Optional Acanthostega-only κ/γ scale; mechanism flag; snapshot + Observer visibility.  
4. Motion receipt additive channels (no narrative).  
5. **Stop** before resources, grasp, limbs, lifecycle.

Do **not** start by rewriting `step_planet` or replacing Euler.

---

## 12. Recommended first coding task

**Scope:** introduce `LocomotionPhysicsProfile` (`TIKTAALIK` | `ACANTHOSTEGA_GENTLE`) with **numeric fields unused unless** `model_line==ACANTHOSTEGA` **and** a new mechanism `gentle_terrain_locomotion` is ON. When OFF, call the **existing** integrate lines unchanged (same expressions, same defaults). Add tests ≤250 ticks. **Do not** retune Tiktaalik defaults. **Do not** add Φ-as-height. **Do not** change PUSH/contact.

**Likely files to add/touch:**

- `mechanistic_mind/physical_system/locomotion_profile.py` (new)  
- `mechanistic_mind/model/acanthostega.py` (attach profile / future map helper only)  
- `tests/test_acanthostega_gentle_locomotion_profile.py` (new)  
- Optionally a **no-op** read of profile in `body_orientation.py` / `dynamics.py` **iff** the OFF path is bit-identical  

**Do not change:**

- `beta31_mechanism_map()` / `preset_canonical(TIKTAALIK_BETA31)` fingerprint inputs  
- `mechanistic_mind/model/tiktaalik.py` physics defaults  
- `action_work.py` WAIT/MOVE semantics for the Tiktaalik profile  
- `body_contact.py`, `physical_push.py`, cognition, resource/lifecycle modules  

**Acceptance:**

- `canonical_fingerprint(preset_canonical("TIKTAALIK_BETA31", seed=17)) == 1621ef2c154864d1`  
- Acanthostega Phase 0 with mechanism OFF: factory-matched `WAIT×250` and `MOVE:E×1+WAIT×20` body `x,y,vx,vy` vs Tiktaalik factory (cognition off, same seed)  
- Mechanism ON + gentle profile: **documented** smaller WAIT displacement than Tiktaalik **on the same seed/config family** — but **do not** require final tuning in task 1 if only the seam lands with identity tests  
- No new keys in Beta 3.1 mechanism map  

**Tests ≤250 ticks:** determinism seed 17; WAIT rest; single MOVE decay; Tiktaalik bit-stable when profile unused.

**Prove Tiktaalik unchanged:** fingerprint test + optional hash of `(x,y,vx,vy)` trace for `tiktaalik_config()` forced WAIT 50 vs pre-change golden (if no golden, equality vs current HEAD before profile apply).

---

## 13. Risks and unknowns

| Area | Risk |
|---|---|
| Numerical | `v_stop` + continuing `F_env` chatters; Euler + wrap; `v_max` clips work accounting |
| Frame dependence | today `dt=1`; introducing real `dt` later would change all coefficients |
| Save/load | `vx,vy`, `motor_u`, deformation, terrain fields already in snapshot; **new profile must serialize** or restore silently becomes Tiktaalik |
| Two-agent | contact after integrate; changing damping changes overlap statistics; **do not** retune stiffness in the same task |
| PUSH | default OFF; when ON, heading impulse is independent — keep it out of gentle profile |
| Observer | factory `tiktaalik_config()` ≠ Apply-experiment (mass 1 / v_max 0.4 / terrain+ambient ON). Tuning against factory will **not** match UI |
| Receipts | lumped decomp vs site path; wrap-naive dx |
| Portable objects | future grasp/mass objects will share this integrator; extra damping must not be secretly “object-aware” |
| GENTLE ecology name | **semantic trap**: `GENTLE_FREE_MOVEMENT` **increases** orientation `force_scale` |
| Future leakage | cognition runs **before** impulse in the same tick (stores update; not x,y). Endo `motor_u` is **next-tick**. `deformation_env_force` is **next-tick**. SMC learns ΔS after commit |

---

*End of implementation map. Gentle Locomotion Kernel is not implemented in this task.*
