# ACANTHOSTEGA PHASE C · FREE OBJECT FLAT-GROUND FRICTION V1

Preset `ACANTHOSTEGA_PHASE_C_FREE_OBJECT_GROUND_FRICTION` · parent `ACANTHOSTEGA_PHASE_C_FLAT_GROUND_GRAVITY` ·
module `mechanistic_mind/physical_system/free_resource_object_ground_friction.py` ·
profile `FREE_OBJECT_GROUND_FRICTION_PROFILE_V1` · mechanism `free_resource_object_ground_friction` ·
receipt `FREE_RESOURCE_OBJECT_GROUND_FRICTION`.

Banner: **FREE OBJECT FLAT-GROUND FRICTION V1 · F=μN · MATERIAL-DERIVED SURFACE COUPLING · BODIES UNCHANGED · NO AIR DRAG · NO SLOPES**

Analyzer: **FREE RESOURCE OBJECT GROUND FRICTION**

Absent from Tiktaalik and all prior Acanthostega presets (including flat-ground gravity parent).

---

## GATE MAP (user questions 1–20)

| # | Question | Answer in this runtime |
|---|---|---|
| 1 | FOK formula | `v' = v·exp(−k·dt)`; rest if `|v'| < rest_threshold`; else `x' = wrap(x+v'·dt)`. Integrator `DAMP_THEN_DRIFT_WRAP_V1`. |
| 2 | Exponential damping | `k = 0.25 /tick`, material-independent, applied every FREE_MOVING step in **prior** presets. |
| 3 | Grounded vs airborne | From flat-ground gravity: grounded ⇔ `z=0 ∧ vz=0`. Known at horizontal step from **previous** tick’s vertical support. |
| 4 | Profile-specific integrator | New preset: grounded → `FRICTION_THEN_DRIFT_WRAP_V1` (Coulomb); airborne → conserve then drift. Prior presets keep exponential damp-then-drift. |
| 5 | Support state vs horizontal step | Horizontal runs **before** vertical. Friction reads prior-tick grounded. Landing → friction starts **next** tick. |
| 6 | Normal load | `N = m·g` on FLAT_GROUND_V1. Deceleration `a = μ_k·g` (**mass-independent**). |
| 7 | Surface material / deposit | Cell deposit from APPLY_TO_SURFACE; composition → `derive_effective_properties` → `surface_affinity`. Empty → neutral 0.5. |
| 8 | surface_affinity | Mass-weighted mix of component coefficients. No recipes / IDs / optical. |
| 9 | Body affinity traction | Unchanged: `traction_multiplier = clip(1+0.8·(aff−0.5), 0.6, 1.4)` scales MOVE Δv only. |
| 10 | Deposit mix | Same `derive_effective_properties` mix; friction only reads affinity. |
| 11 | Support sample at (x,y) | `OBJECT_SUPPORT_FLOOR_WRAP_V1` — floor-wrap of object pose. |
| 12 | Footprint multi-cell | `FOOTPRINT_MULTI_CELL = NOT_IMPLEMENTED` (single cell). |
| 13 | APPLY_TO_SURFACE | Existing command; deposits change affinity. Integrate runs before APPLY same tick → same-tick deposit does not affect this tick’s friction. |
| 14 | How friction replaces FOK damping | When friction ON: grounded → Coulomb **only** (legacy damping bypassed); airborne → no damping, conserve `vx,vy`. When OFF: legacy damping unchanged. **Never both.** |
| 15 | Energy receipts | `K = ½ m \|v\|²` dissipates; `reservoir_credit=false`; no sound. Receipt `FREE_RESOURCE_OBJECT_GROUND_FRICTION`. |
| 16 | Airborne vx/vy | Conserved (`AIR_DRAG=NO`). |
| 17 | Contact reads pose | Contacts after horizontal+vertical; read post-friction pose. No re-friction after collision same tick. |
| 18 | Restore mid-slide | Snapshot carries config + friction state + object `vx,vy,grounded,z`; continue Coulomb next tick. |
| 19 | HELD | Out of scope (FOK skips HELD). |
| 20 | FREE_STATIC | Untouched; friction never starts resting objects. `STATIC_FRICTION_FORCE_BALANCING=NOT_IMPLEMENTED`. |

**Gate decision:** FOK can safely replace damping only in the new preset via a gated branch in `integrate_free_objects`. Proceeded.

---

## 1. Scope

FREE_MOVING + FREE_STATIC on FLAT_GROUND_V1 only. NOT HELD, NOT bodies, NOT experimenter-as-entity, NOT deposits-as-entities, NOT columns. FREE_STATIC stays rest.

## 2. Physics

```
N = m g
F = μ_k N
a = μ_k g                         # mass-independent
μ_k = MU_MIN + (MU_MAX−MU_MIN)·clip(surface_affinity,0,1)
                                  # MU_MIN=0.5, MU_MAX=3.0
dv = μ_k g dt                     # dt=1
if dv ≥ speed or speed−dv < rest_threshold: v→(0,0), FREE_STATIC
else: scale v by (speed−dv)/speed
then: x' = wrap(x + vx·dt)        # friction → position (FOK-consistent)
```

Airborne: conserve horizontal v; still drift position; no air drag.

## 3. Tick order

object horizontal friction/integration → vertical gravity/support → contacts.  
Landing: friction next tick after support. No second horizontal integrate on landing tick. No re-friction after collision same tick.

## 4. Affinity → coupling bridge (body traction unchanged)

| Concern | Law |
|---|---|
| Body MOVE traction | `traction_multiplier(aff)` — transmission of motor effort into Δv |
| Object ground friction | `μ_k(aff)` — Coulomb coefficient for kinetic ground friction |

Same scalar `surface_affinity`; **independent** maps. Body traction code paths are not modified.

## 5. Observer / Analyzer

- Banner as above
- Analyzer section: `FREE RESOURCE OBJECT GROUND FRICTION`
- Receipts: `FREE_RESOURCE_OBJECT_GROUND_FRICTION` (bounded history)
- No agent-accessible μ / friction tokens (`observation.FORBIDDEN_TOKENS`)

## 6. Forbidden (V1)

Body friction, slopes, elevation activation, air drag, static friction cone / force balancing, multi-cell footprint, Analyzer progress bar, sound, reservoir credit.

## 7. Calibration table (v0=0.3, g=2/110)

| affinity | μ_k | a=μg | ticks to stop (ceil) |
|---|---|---|---|
| 0.25 | 1.125 | ≈0.02045 | ≈15 |
| 0.50 | 1.750 | ≈0.03182 | ≈10 |
| 0.75 | 2.375 | ≈0.04318 | ≈7 |

## 8. Tests

`tests/test_acanthostega_free_object_ground_friction.py` — isolation, μ map, body-traction unchanged, mass-independent a, damping bypass vs parent, airborne conserve, FREE_STATIC rest, stop→exact zero, landing next-tick, energy, support sample, static NOT_IMPLEMENTED, HELD out of scope, snapshot mid-slide, 250-tick rest, calibration, never-both, banner/UI. Budgets: unit ≤30, stop ≤100, snapshot ≤100, focused ≤200; one 250-tick rest OK. Scientific validation **not run**.

## 9. Preservation contract

- Missing `free_resource_object_ground_friction` key → OFF; legacy FOK damping unchanged
- Parent flat-ground gravity preset unchanged (friction OFF)
- LPS / column-transfer preservation probes already exclude `PHASE_C` / `FLAT_GROUND`
- Prior-suite descendant allowlists that list Phase C flat-ground also list this child
- Default snapshots omit friction state when OFF → prior-preset hashes unchanged

## 10. Files touched (lab machine only; uncommitted; no clone/cloud/commit/push)

- `mechanistic_mind/physical_system/free_resource_object_ground_friction.py` (new)
- `mechanistic_mind/physical_system/free_resource_object_kinematics.py` (gated damping bypass)
- `mechanistic_mind/scientific_v3/free_object_ground_friction_summary.py` (new)
- `tests/test_acanthostega_free_object_ground_friction.py` (new)
- `docs/ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION.md` (this file)
- Wiring: `experiment_canonical`, `mechanism_registry`, `runtime`, `model/acanthostega`, `model/lines`, serialize, observation, analyzer pipeline, `modelPreset.ts`, `App.tsx`, prior-test allowlists
