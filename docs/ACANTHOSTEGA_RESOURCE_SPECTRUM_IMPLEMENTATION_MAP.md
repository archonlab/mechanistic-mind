# Acanthostega Resource Spectrum Foundation — implementation map

**Status:** forensic analysis only. Resource objects are **not** implemented.  
**Frozen public model:** `TIKTAALIK_BETA31` (fingerprint seed 17: `1621ef2c154864d1`).  
**Target line:** `ACANTHOSTEGA_PHASE0` / `ACANTHOSTEGA_PHASE_A_GENTLE`.  
**Evidence tags:** `OBSERVED` (code or ≤250-tick measurement), `DERIVED` (direct numerical consequence of observed equations), `INFERRED` (plausible, not isolated), `UNKNOWN`.

This document is not a scientific claim about organism intention, preference, food, metabolism, grasp, or inventory. Scalar stocks are not portable objects.

---

## 1. Executive summary

**OBSERVED — what A/B are now:** Resource A and resource B are **anonymous non-negative scalar stocks**. In the world they live as **per-cell arrays** `PlanetState.R_A` and `PlanetState.R_B`. On a body they live as **per-footprint-site arrays** `PhysicalBodyState.R_A_site` and `R_B_site`. They are not entities: no object ID, no independent pose, no mass, no velocity, no collision shape.

**OBSERVED — a third scalar path exists:** `PlanetState.R` / `body.R_site` (`transferable_resource`) is a **separate** cell stock converted by `step_environmental_resource`. It is not A or B. Public two-agent Observer runs **do not step this path** (`TwoAgentRuntime.finish_tick(..., skip_resources=True)` then only `simultaneous_complementary_resources`).

**OBSERVED — why A/B are not portable objects:** Transfer is **automatic cell sampling**. When an oriented footprint site and a cell coincide, `_transfer_one` removes cell stock and adds site stock, with a fractional **loss term**. No discrete action is required. WAIT transfers. The portion has **no identity** after the cell decrement. Conversion (`n_rxn` limited by both site stocks + rate + work capacity) **destroys** A and B scalars and **credits** `mechanical_work_reservoir` (`ΔW = η κ n_rxn`). That is work accounting, not ingestion of an object.

**OBSERVED — FIELD_A / FIELD_B are not resources:** They are physical-signal amplitudes (`physical_signal.py`). Cognition may see `local.FIELD_A` / `local.FIELD_B` when those arrays exist. Cognition does **not** see `R_A` / `R_B` (`observation.accessible_observation`; P12 `P12_NO_RESOURCE_GT_LEAK`).

**Safe extension point (INFERRED from ownership):** Keep Tiktaalik A/B as frozen cell+site scalars. Add an **Acanthostega-only list of physical resource objects** beside `PlanetState` grids, gated by `model_line == "ACANTHOSTEGA"` (or a new key **only** on `acanthostega_mechanism_map()` / a dedicated `acanthostega_resource_mechanism_map()`). Do **not** add keys to `beta31_mechanism_map()`. Do **not** reuse `R_A` cells as objects.

**Recommended first coding task:** one passive `ResourceObject` in the world (stable ID, pose, mass, no auto-absorption, snapshot/restore, researcher-visible). No perception, grasp, carry, mix, or conversion.

---

## 2. Current resource ontology

| Resource/state | Owner | Spatial? | Conserved? | Agent-accessible? | Snapshot? | Tiktaalik-specific? |
|---|---|---:|---:|---:|---:|---:|
| `planet.R` transferable_resource | `PlanetState` (`planet/state.py`) | per-cell scalar grid | **No** (transfer_loss; ecology does not step `R`) | **No** | Yes `serialize_planet_state` | Mechanism default ON; **skipped** on public two-agent tick |
| `planet.R_A` | `PlanetState` | per-cell scalar | **No** (loss, ecology production/decay/diffuse/clip, optional `B_env_source` analog for B) | **No** (Observer GT only) | Yes | Shared infrastructure; Beta 3.1 ecology preset seeds it |
| `planet.R_B` | `PlanetState` | per-cell scalar | **No** (same + `B_env_source_rate` can **create** B) | **No** | Yes | Same |
| `planet.resource_geo_suit_A/B` | `PlanetState` | per-cell suitability | N/A (not a stock) | **No** (`FORBIDDEN_TOKENS`) | Yes | World GT |
| `body.R_site` | `PhysicalBodyState` | per footprint site (not a world object) | **No** (conversion consumes) | **No** as resource type | Yes `body.snapshot()` | Single-agent env path |
| `body.R_A_site` | `PhysicalBodyState` | per footprint site scalar | **No** (transfer_loss, `A_passive_loss`, conversion) | **No** | Yes | Complementary path |
| `body.R_B_site` | `PhysicalBodyState` | per footprint site scalar | **No** (`B_passive_loss` default 0.12/tick) | **No** | Yes | Complementary path |
| `body.mechanical_work_reservoir` | `PhysicalBodyState` | **not spatial** (scalar) | **No** (credited by conversion; spent by action/deformation/motor) | Indirectly via work-limited motor, **not** as A/B | Yes | Shared |
| `body.B` / `B_site` | `PhysicalBodyState` | surface / per-site 3-channel **morphology** | Separate matter-like channel | `body.B*` in observation | Yes | **Not** resource A/B |
| `planet.M` | `PlanetState` | 3-channel cell matter | Transport conservation tests exist | `local.M*` | Yes | **Not** A/B |
| `planet.FIELD_A/B` | `PlanetState` | per-cell **signal** | Wave/deposit dynamics | `local.FIELD_*` if arrays exist | Yes | **Not** resource stocks |
| Climate ecology production | `step_climate_resources` | cell scalars R_A/R_B | **Creates/destroys** stock vs capacity | **No** | Fields persist | Preset `BASELINE_CLIMATE_DEFAULT` ON in public experiments |
| Work trickle | `deformation_work.passive_reservoir_trickle` | none | **Creates** work | N/A | Config | Beta 3.1 ecology sets trickle **0** |

**Units (OBSERVED comments, not SI):** Resource units are anonymous. Work: `ΔW = η * κ * consumed` (`environmental_resource.py` / `complementary_resources.py`). Default complementary: `stoich_A=stoich_B=1`, `η=0.70`, `κ=1`, `conversion_rate=0.05`. Site caps: `A_site_capacity=1.20`, `B_site_capacity=0.22`. Transfer rates: `A_transfer_rate=0.07`, `B_transfer_rate=0.12` **per site per tick**.

**Creation / deletion:**

| Stock | Created | Removed / replenished |
|---|---|---|
| Env R_A/R_B | `initialize_planet` + `initial_resource_fields` when ecology on; `place_source_AB`; `step_climate_resources` production; `B_env_source_rate` on **all** B cells | Transfer remove; ecology decay/diffuse/clip |
| Body R_A_site / R_B_site | Transfer acquire; `ensure_site` zeros | Passive loss; conversion consume |
| Env `R` | `ensure_world_R` / `place_source` | Transfer |
| Work | Conversion; optional trickle; env deform recovery (other mechanisms) | `allocate_shared_work` / action / deformation |

**Persistence between ticks:** **OBSERVED** arrays remain on `PlanetState` / `PhysicalBodyState` until mutated.

**Observer vs agent:** Observer serializes full grids (`serialize.py` `R_A`, `R_B`, `R_A_plus_R_B`) and body site lists. Agent observation forbids resource GT names.

---

## 3. Causal transfer pipeline

### 3.1 Complementary A (and B, same structure)

```text
PlanetState.R_A[iy, ix]                    planet/state.py
  → step_planet / step_climate_resources   planet/dynamics.py  (production/decay BEFORE body transfer)
  → oriented_site_cells(body, footprint)   body_orientation.py  (integer cells, not contact geometry)
  → _transfer_one(env=R_A, store=R_A_site) complementary_resources.py
        remove_i = min(rate, avail, room/(1-loss))
        acq_i = remove_i * (1 - A_transfer_loss)
        env -= remove_i; store += acq_i
  → A_passive_loss * R_A_site[i]           same function, after transfer
  → conversion (needs A and B)             n_rxn = min(A/sa, B/sb, crate, room_W/(ηκ))
        R_A_site -= n_rxn * sa
        mechanical_work_reservoir += η κ n_rxn
  → allocate_shared_work / realize_discrete_action   begin_tick of NEXT tick uses new W
  → structured_events RESOURCE_A_TRANSFERRED / COMPLEMENTARY_CONVERSION
        runtime.py ~1388–1467
  → Observer complementary ledger; Analyzer resource_A = sum(R_A_site)
        scientific_history.py
```

B substitutes `R_B`, `R_B_site`, `B_transfer_*`, `B_passive_loss`, `RESOURCE_B_*`.

**OBSERVED — automatic:** yes. **Action required:** no. **Contact:** footprint **cell overlap**, not `resolve_soft_contact`. **Distance:** none beyond which cell the site maps to. **World stock disappears:** yes, decremented. **Conservation:** transfer identity `removed = acquired + loss` holds (**OBSERVED** residual 0 on 1 WAIT tick). Global A+B+work is **not** conserved (loss, conversion_loss `(1-η)κ n_rxn`, ecology). **Body↔body transfer:** **no** path. **Blocking:** two-agent **flux split** on contested cells (`simultaneous_complementary_resources`), not exclusive lock. **Independent motion:** **no**.

### 3.2 Legacy transferable_resource (not A/B)

```text
planet.R → step_environmental_resource → R_site → (unless skip_conversion) work
```

`PhysicalSystemRuntime._apply_resource_steps` always calls this first, then complementary. If complementary conversion is ON, env conversion is **skipped** (`skip_conversion=True`) so work is not double-credited.

`TwoAgentRuntime._step_once`: **neither** env path nor per-slot complementary `step_complementary_resources` transfer; only simultaneous complementary after contact.

### 3.3 Measured 1-tick WAIT (seed 17, ecology OFF, body on source cell)

| | A | B |
|---|---:|---:|
| env before → after | 1.0 → 0.93 | 0.5 → 0.38 |
| removed / acquired / loss | 0.07 / 0.0665 / 0.0035 | 0.12 / 0.114 / 0.006 |
| consumed into conversion | 0.05 | 0.05 |
| body after | 0.0165 | 0.064 |
| work credited | 0.035 (`η κ n_rxn` = 0.7×1×0.05) | same joint conversion |

**OBSERVED:** one tick performs **transfer + leakage(off here) + conversion**.

---

## 4. Tick ordering

### 4.1 `PhysicalSystemRuntime` (single slot)

**begin_tick (no world advance):** observation → cognition → `request_discrete_action` / `allocate_shared_work` / `realize_discrete_action` (work **spent** from reservoir **before** this tick’s resource credit).

**finish_tick:**

1. `step_planet` — climate/resource ecology mutates `R_A`/`R_B`  
2. `step_physical_body` (site path skips lumped mechanical)  
3. `step_internal_medium`  
4. **`_apply_resource_steps`** — env R then complementary A/B (when `orient_on`; other branches call the same if `not skip_resources`)  
5. `step_orientation_mechanics` — forces, CoM integrate (Gentle Locomotion profile here if Acanthostega)  
6. head / osc / endogenous motor / ground rest  
7. tick += 1; structured events including resource receipts  

**DERIVED:** resource credit on tick *t* cannot pay the action impulse already realized at the start of tick *t*.

### 4.2 `TwoAgentRuntime._step_once` (public Beta 3.1 / Acanthostega presets: two slots)

```text
observations()
begin_tick per slot (process_order)
step_planet once
finish_tick(skip_planet=True, skip_resources=True) per slot
resolve_soft_contact + apply_push_through_contact   (bodies only)
simultaneous_complementary_resources
  frozen env snapshot → desired draws → flux scale → apply
  then per-body step_complementary_resources with transfer_A/B temporarily False
  (passive loss + conversion only)
physical signals / OSC
```

**OBSERVED:** transfer uses a **frozen** env copy; contested cells scale by `avail/sum(requested)`. Process order `(0,1)` vs `(1,0)` did **not** change acquired amounts in a 1-tick overlap test (both 0.02375 from 0.05 A). Order dependence of **cognition** remains; **transfer allocation** is simultaneous.

---

## 5. Perception map

| Channel | What it is | A/B stock? | Agent? | Researcher? |
|---|---|---:|---:|---:|
| `local.T`, `local.M*`, `local.v*` | cell-mean physical | No | Yes | Yes |
| `local.FIELD_A/B` | signal amplitude mean over footprint | **No** | Yes if fields exist | Yes |
| near-field `exo_*` / surface / spatial | optics of surface + other **bodies** | **No** R_A | Yes (anonymous) | GT extras in serialize |
| vestibular / neck | self motion | No | Yes | Yes |
| `R_A`/`R_B` grids | cell stocks | Yes | **No** | Overlay heatmap (`WorldMap` `scalarGrid` + `heatColor`) |
| `resource_geo_suit_*` | ecology suitability | No | **Forbidden** | Yes |
| `R_A_site` sums | body scalars | Yes | **No** | Inspector / Analyzer `resource_A` |
| climate phase / cycle | ecology clock | No | **Forbidden** | Experiment GT |

**OBSERVED:** organism does **not** perceive A vs B as objects. It does **not** get bearing-to-resource. It may feel **other bodies** optically. Distinguishing A vs B would currently require **leaking GT** or a **new physical appearance** (optical/surface coupling), not a `RESOURCE_TYPE` token.

**Future object sensing (INFERRED):** extend `foreign_bodies` / surface_optical sampling to include resource-object poses **as anonymous optical sources**, same `P12` rule: no type label in cognition.

---

## 6. Physical entity infrastructure

**OBSERVED — what exists:**

| Kind | IDs | Pose / v | Collision | Registry | Snapshot | Observer |
|---|---|---|---|---|---|---|
| Organism body | slot `agent_{i}` / `body-{i}` (Observer); Python `id(body)` in undercover inventory | `x,y,vx,vy,theta,omega` | `body_contact.resolve_soft_contact` pairwise **bodies** | `TwoAgentRuntime.slots` | snapshot v2 / two_agent v1 | WorldMap agents |
| Planet fields | none | grids | N/A | `PlanetState` | `serialize_planet_state` | scalar layers |
| `world_engine` objects | `object_id` in `world_engine/models.py` | cell regions | world_engine occupancy | **separate engine** | own models | **not** imported by `physical_system/` |

**OBSERVED:** no general MM-runtime object list, spatial hash, or contact vs non-body shapes.

**Can a resource object reuse a body?** **INFERRED: no.** Bodies run cognition, work, A/B sites, PUSH. Mixing would contaminate identity, Analyzer `cognitive_agent_id`, and Gentle Locomotion.

**Minimal new type:** a dataclass list on world or runtime (`resource_objects: list[ResourceObject]`), **not** a `PhysicalSystemRuntime` slot.

**Mass vs carry (later):** body integrate uses `body.mass` in orientation/lumped dynamics. Object mass is unused until a future grasp coupling adds force/inertia. Gentle Locomotion currently **does not** sample external objects (`step_orientation_mechanics` uses planet flow/terrain/ambient only).

**Do not wire `world_engine` into Tiktaalik** without an explicit later decision: it is a different existence model (cells/routes/affordances).

---

## 7. Save/load and identity

| State | Serialize | Restore |
|---|---|---|
| World R, R_A, R_B | `planet/runtime.py` `serialize_planet_state` | `PhysicalSystemRuntime.restore` via deserialize planet |
| Body R_site, R_A_site, R_B_site, work | `PhysicalBodyState.snapshot` | restore constructs `PhysicalBodyState(..., R_A_site=...)` |
| Complementary **config** | snapshot `config.complementary_resources` | `ComplementaryResourcesConfig.from_dict` |
| Two-agent | shared `world` on agent 0; other agents pop world | `TwoAgentRuntime.restore` aliases `ri.world = restored[0].world` |
| Ledgers | `last_complementary_ledger` is **runtime cache**, not required for physics restore | Recomputed next step |

**Measured (OBSERVED):** snapshot after 1 WAIT transfer, restore, 1 more step: `R_A_site` sum 0.133 vs 0.133, env 0.86 vs 0.86, pose match.

**A/B have no stable portion ID.** Cell coordinates are not identities (ecology can refill the same cell).

**Minimal future object snapshot fields:**

```text
object_id          stable string
pose               x, y, optional theta
mass / quantity    scalar
composition        list of MaterialComponent
physical_state     e.g. FREE | later ATTACHED
velocity           optional; 0 for first task
ownership          none | body_id (later)
provenance         seed / tick / place receipt
```

Determinism: restore list **order + IDs**; do not use Python `id()`.

---

## 8. Observer and Analyzer assumptions

**Hardcoded A/B (OBSERVED):**

- `serialize.py`: layers `R_A`, `R_B`, `R_A_plus_R_B`; note “not food”
- `App.tsx`: ENV A/B, ecology toggles, GT means
- `WorldMap.tsx`: generic heatmap of selected scalar (A/B look like T, not sprites)
- `InspectorDock.tsx`: `R_A / R_B` metric
- Analyzer Next `joins.py` `RESOURCE_STATE`: `resource_A`, `resource_B`, `work`
- `scientific_history.py`: `resource_A = sum(R_A_site)`
- `web/.../runAnalysis.ts` / `types.ts`: series only A/B/work
- Events: `RESOURCE_A_TRANSFERRED`, `RESOURCE_B_TRANSFERRED`, `COMPLEMENTARY_CONVERSION`, plus legacy `RESOURCE_TRANSFERRED` for `planet.R`

**Seam for objects (do not build an inventory HUD):**

- Researcher overlay: markers from object pose list (like agent dots, **not** item bar)
- Analyzer: optional `PHYSICAL_OBJECT_STATE` with `object_id`, pose, mass — **not** `FOOD_FOUND`
- Keep A/B series unchanged for Tiktaalik JSONL compatibility

---

## 9. Proposed material schema

Not implemented. Interpret as **coefficients + conversion process**, not named items.

```text
ResourceObject
  object_id: str
  pose: (x, y[, theta])
  mass: float            # inertial / quantity of the object as a body
  quantity: float        # optional; may equal mass at first
  composition: list[MaterialComponent]
  physical_state: FREE   # later ATTACHED
  velocity: (vx, vy)     # optional; 0
  provenance: dict

MaterialComponent
  component_id: str      # stable lab id, not "food"
  amount: float
  physical_coefficients: dict   # e.g. optical albedo later; density
  conversion_properties: dict   # later: work_yield κ, stoich partners
```

**Candidate component axes (not a frozen catalog):** energy-bearing; structural; catalytic; inert; reactive/harmful. Map onto **existing** work reservoir and **future** Acanthostega conversion, **not** onto `R_A` identity.

**Forbidden:** `if name == "healing_food": damage -= 10`.

**First object:** composition may be a single inert component or even empty coefficients; existence does not require A/B semantics.

**Relationship to A/B:** A/B remain Tiktaalik **cell ecology**. Acanthostega objects are a **parallel** material layer. Later conversion may *credit the same* `mechanical_work_reservoir` via a **new** Acanthostega mechanism, without renaming A/B as “food”.

---

## 10. Recommended Acanthostega seam

```text
shared MM infrastructure
├── Tiktaalik frozen scalar/site resources A/B
│     complementary_resources.py
│     environmental_resource.py
│     climate_ecology.step_climate_resources
│     beta31_mechanism_map()  — DO NOT ADD KEYS
└── Acanthostega material spectrum
      acanthostega_resource_mechanism_map()   # preferred dedicated function
      and/or extra keys only on acanthostega_mechanism_map()
      ├── physical resource objects (first coding task)
      ├── material composition (later)
      └── grasp / combine / body conversion (later)
```

**Concrete symbols:**

| Concern | File | What to do later |
|---|---|---|
| Map function | `experiment_canonical.py` | Add `acanthostega_resource_mechanism_map()` **or** keys on `acanthostega_mechanism_map()` only. Never `beta31_mechanism_map()`. |
| Object type | **new** `physical_system/resource_objects.py` | `ResourceObject`, `place_resource_object`, snapshot helpers |
| World owner | `planet/state.py` **or** runtime field | `resource_objects: list` default empty; Tiktaalik unused |
| Serialize | `planet/runtime.py` `serialize_planet_state` | persist list |
| Restore | `runtime.py` snapshot/restore | round-trip IDs/poses |
| Two-agent | `two_agent.py` snapshot world once | objects live on shared world |
| Observer | `serialize.py` | researcher `world.resource_objects` overlay |
| Tick | `finish_tick` / `_step_once` | first task: **no** step (static pose) |
| Transfer gate later | `complementary_resources` flags on **Acanthostega preset only** | can set `transfer_A_enabled=False` on Acanthostega map **without** editing Tiktaalik map |

**Can Acanthostega disable auto-transfer without changing Tiktaalik?** **OBSERVED yes:** transfer is config flags already in `ComplementaryResourcesConfig` and mechanism ids `resource_A_transfer` / `resource_B_transfer`. `acanthostega_mechanism_map()` currently **copies** `beta31_mechanism_map()` (transfers stay ON). A future Acanthostega-only map edit can turn them OFF. **Do not do this in the first coding task.**

---

## 11. Scientific observability

**Existing mechanical-ish receipts (OBSERVED):**

| Event | Meaning |
|---|---|
| `RESOURCE_TRANSFERRED` | env `R` → `R_site` |
| `RESOURCE_SOURCE_DEPLETED` | cell ~0 |
| `BODY_RESOURCE_CAPACITY_REACHED` | `R_site` cap |
| `RESOURCE_CONVERTED_TO_WORK` | env-R conversion |
| `RESOURCE_A_TRANSFERRED` / `RESOURCE_B_TRANSFERRED` | complementary acquire |
| `RESOURCE_A_DEPLETED` / `RESOURCE_B_DEPLETED` | cell depleted |
| `RESOURCE_A_CAPACITY_REACHED` / `B_...` | site cap |
| `COMPLEMENTARY_CONVERSION` | joint consume → work |
| `WORK_RESERVOIR_REPLENISHED` / `DEPLETED` | W scalar |
| `PUSH_FORCE_APPLIED` | body–body only |

**Gaps vs future claims:**

| Future claim | Current coverage |
|---|---|
| object contacted | **No** (contact is body–body) |
| object grasped / released | **No** |
| material transferred (object→body) | **No** (only cell→site scalars) |
| materials combined | **No** |
| conversion occurred | **Yes** for A+B→work and R→work only |

**Allowed future events:** `RESOURCE_OBJECT_PLACED`, `RESOURCE_OBJECT_CONTACT`, `RESOURCE_OBJECT_ATTACHED`, `RESOURCE_OBJECT_DETACHED`, `MATERIAL_MOVED`, `MATERIAL_MIXED`, `MATERIAL_CONVERTED`. Quantities, IDs, poses, Δamount.

**Forbidden:** `FOOD_FOUND`, `USEFUL_ITEM`, `HEALTH_POTION_CREATED`, `PREFERRED_RESOURCE`.

---

## 12. Preservation contract

```text
TIKTAALIK_RESOURCE_SEMANTICS_CHANGED = NO
TIKTAALIK_MECHANISM_MAP_CHANGED = NO
TIKTAALIK_BETA31_FINGERPRINT_CHANGED = NO
ACANTHOSTEGA_RESOURCE_SEAM_IDENTIFIED = YES
```

This audit did not modify code. Existing tests `tests/test_complementary_resources.py` + `tests/test_environmental_resource.py` passed (27 tests).

---

## 13. Minimal implementation sequence

1. **Passive physical resource object** — ID, pose, mass, no auto-absorb, snapshot, researcher overlay.  
2. **Physical sensing** — anonymous optical/near-field of object pose; no type token.  
3. **Single-manipulator grasp/release** — attach/detach; still no inventory HUD.  
4. **Bilateral manipulation** — `GRASP_LEFT/RIGHT`, `BRING_TOGETHER` (out of current scope).  
5. **Material composition** — `MaterialComponent` amounts on objects.  
6. **Body conversion** — composition + process → work or later structural effect; Acanthostega-only.  
7. **Lifecycle coupling** — forbidden until a later lifecycle task.

---

## 14. Recommended first coding task

### Scope

One `ResourceObject` instance in an **Acanthostega** runtime:

- exists in the shared world  
- stable `object_id`  
- continuous pose `(x, y)` (may sit between cells)  
- `mass > 0`  
- **not** decremented by `_transfer_one` / `step_environmental_resource`  
- snapshot + deterministic restore  
- Observer researcher list/markers  

**Not in scope:** agent observation, grasp, carry, mixing, ingestion, biological effect, A/B semantic change, limbs.

### Files likely to add/touch

- **new** `mechanistic_mind/physical_system/resource_objects.py`  
- `mechanistic_mind/planet/state.py` (optional empty list field)  
- `mechanistic_mind/planet/runtime.py` serialize/deserialize  
- `mechanistic_mind/physical_system/runtime.py` snapshot/restore if objects not inside planet serialize  
- `mechanistic_mind/physical_system/experiment_canonical.py` — `acanthostega_resource_mechanism_map()` **or** Acanthostega-only key; default **OFF** on PHASE0/PHASE_A until explicitly enabled for tests  
- `mechanistic_mind/ui/psy_observer_web/serialize.py` researcher payload  
- `tests/test_acanthostega_resource_object_passive.py` (≤250 ticks)

### Files that must not change (behavior)

- `beta31_mechanism_map()` body  
- `complementary_resources.py` transfer/conversion equations  
- `environmental_resource.py` semantics  
- `canonical_fingerprint` / Tiktaalik identity  
- `tests` that lock Beta 3.1 fingerprint (`1621ef2c154864d1`)  
- Gentle Locomotion kernel (unless a no-op config thread)

### Acceptance criteria

- Tiktaalik Beta 3.1 fingerprint seed 17 unchanged  
- Acanthostega with objects OFF ≡ current Acanthostega physics (no A/B delta)  
- With objects ON: one object pose/mass/id invariant over `WAIT × N` (N≤250) while A/B transfer still follows existing rules if those flags remain ON  
- Restore(snapshot) continues with same `object_id` and pose  
- Cognition payload audit: no `RESOURCE_TYPE` / object_id leak  

### Tests (≤250 ticks)

- Place object at non-integer pose; WAIT 20; pose unchanged; `R_A` transfer still cell-based if body on a source  
- Snapshot/restore equality of object list  
- Two-agent: object on shared world, not duplicated per slot  
- Fingerprint test unchanged  

### Risks

- Serializing objects into Tiktaalik snapshots by accident  
- Rendering as inventory  
- Reusing a body slot  
- Teaching Analyzer that `resource_A` means the new object  
- Turning off A/B transfer in the same PR (scope creep)

---

## 15. Unknowns

### OBSERVED

- A/B are cell + site scalars; transfer automatic on footprint cells; WAIT suffices.  
- Same tick: transfer and complementary conversion.  
- Transfer identity `removed = acquired + loss`.  
- Two-agent contested cells flux-split; order-independent in the overlap diagnostic.  
- Two-agent public path skips `planet.R` / `R_site`.  
- Cognition has no `R_A`/`R_B`; may have `FIELD_A/B`.  
- Snapshot restore matched body A and env A after extra step.  
- Contact/PUSH is body–body only.  
- `acanthostega_mechanism_map()` = Beta 3.1 flags + `gentle_terrain_locomotion`.  
- `world_engine` objects are unused by `physical_system`.  
- Factory `PhysicalSystemConfig` planet ecology OFF (empty R_A/R_B); public presets use `BASELINE_CLIMATE_DEFAULT`.  

### DERIVED

- Work from conversion cannot pay the same tick’s already-realized impulse.  
- Global conservation of A+B+W fails because of transfer_loss, conversion_loss, leakage, ecology, trickle.  
- Multiple scalar fields may occupy one cell (`R_A`, `R_B`, `R`, `M`, `FIELD_*`) without entity identity.  

### INFERRED

- Safest object home is a new list on planet/runtime, Acanthostega-gated.  
- Optical `foreign_bodies` path can later sense objects without symbolic types.  
- Acanthostega can disable auto-transfer later via its own mechanism map.  
- Gentle Locomotion will ignore objects until a new force/contact term is added.  

### UNKNOWN / NOT MEASURED

- Public `BASELINE_CLIMATE_DEFAULT` two-agent conservation over 250 ticks with ecology **ON** (diagnostic froze ecology).  
- Whether Analyzer JSONL schema rejects extra object fields.  
- Exact UI color mapping per layer beyond generic `heatColor`.  
- Interaction of object pose with toroidal wrap if x is not wrapped on restore (bodies use `wrap_coord`).  
- Whether `InspectorDock` `physical.resources.A` binds to complementary `body_A` or is a stale path.  
- Long-horizon numerical drift of site vs env sums with ecology diffusion.  

---

**Stop.** Do not implement Resource Spectrum Foundation without a separate request.
