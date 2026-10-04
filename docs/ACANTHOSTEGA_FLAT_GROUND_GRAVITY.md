# ACANTHOSTEGA PHASE C · FLAT GROUND GRAVITY V1

Preset `ACANTHOSTEGA_PHASE_C_FLAT_GROUND_GRAVITY` · parent `ACANTHOSTEGA_PHASE_B_EFFECTOR_WORK_ACCOUNTING` ·
module `mechanistic_mind/physical_system/flat_ground_gravity.py` · profile `FLAT_GROUND_GRAVITY_PROFILE_V1`.

Banner: **PHASE C · FLAT GROUND GRAVITY V1 · UNIFORM g · INELASTIC SUPPORT · SURFACE ELEVATION NOT ACTIVE · NO SLOPES · NO STACKING**

## 1. Mechanism packaging (justification)

**Choice: one umbrella + 4 capability flags (always co-gated).**

| ID | Role |
|---|---|
| `flat_ground_gravity` | Umbrella / enable gate |
| `vertical_physical_state` | z, vz, grounded, half-extent contract |
| `uniform_gravity` | Mass-independent vertical acceleration |
| `flat_ground_support` | FLAT_GROUND_V1 inelastic support at ground_z=0 |
| `vertical_contact_filter` | Filter existing XY contacts by vertical overlap |

**Justification:** CRITICAL ORDER forbids “z exists while XY contacts ignore height.” Independently toggleable mechanisms would allow that invalid mid-state. The umbrella enables all four flags atomically; receipts and the analyzer still name each concern.

Prior presets remain 2D / vertical OFF and **bypass the filter entirely**.

## 2. Vertical geometry contract (landed first)

Locked convention:

- `z` = lower support point height above flat ground (**not** centre)
- `centre_z = z + vertical_half_extent`
- interval `[z, z + 2·half_extent]`
- `ground_z = 0`, upward positive, cells / cells·tick⁻¹
- grounded ⇔ `z=0` and `vz=0`
- Bodies: `vertical_half_extent = BODY_CONTACT_RADIUS` (0.575)
- Objects: `vertical_half_extent = collision_radius` (not optical/glyph/grasp)
- Shared helpers: `vertical_interval`, `vertical_overlap_at_endpoint`, `vertical_overlap_at_fraction`
- Swept contacts interpolate `z` at the horizontal contact fraction
- `FULL_3D_ENTITY_COLLISION = NOT_IMPLEMENTED`
- `VERTICAL_FILTER_FOR_EXISTING_HORIZONTAL_CONTACTS = IMPLEMENTED`
- Episode end reason `VERTICAL_SEPARATION` when overlap is lost

## 3. Scope

Bodies (single, TwoAgent, experimenter) and ResourceObjects in `FREE_STATIC` / `FREE_MOVING` / `HELD`.

- HELD: `z/vz` snap from holder (fixed offset 0); no independent gravity
- Deposits / columns are **not** vertical entities
- Init Apply: all `z=0`, `vz=0`, grounded; **no** initial fall event

## 4. Gravity

`vz_next = clamp(vz − g·dt, ±max_vz)`; `z_next = z + vz_next·dt`; `dt = 1`.

- Calibrated `g = 2/110 ≈ 0.0181818` so fall from `z=1` reaches ground in **10** ticks (band 9–12)
- **No** 9.81; mass-independent acceleration

## 5. Tick order

- Body: after horizontal CoM integrate → gravity → support → then contacts
- FREE objects: after horizontal FOK → gravity → support (shared world once)
- HELD: skip gravity; snap from holder after held kinematics
- One vertical step / entity / tick; `last_vertical_integrated_tick` + per-body guards (TwoAgent safe)

## 6. Support (FLAT_GROUND_V1)

`ground_z=0`, restitution=0, inelastic, no bounce / sound / friction / v_stop coupling. Landing receipt once; grounded rest does not repeat landing.

## 7. Contact filter paths

B/B, free B/O, free O/O, held/foreign, held/held BRING_TOGETHER, GRASP, COMBINE (via held contact). Prior presets bypass.

## 8. RELEASE / GRASP

- RELEASE: `object.z = held z`, `vz = holder.vz`; FOK pattern — no second integrate on release tick
- GRASP: XY + vertical reach; endpoint only; no vertical sweep; grounded grasp preserved

## 9. Energy (researcher-only)

`K_z = ½ m vz²`; `U = m g z` (lower support); support dissipation on landing; **no** reservoir credit; **no** global conservation claim.

## 10. Isolation

`surface_elevation = METADATA_ONLY`; `terrain_potential` is not height. Spatial index stays 2D broadphase.

## 11. Observer / Analyzer

- Banner as above
- Analyzer section: `VERTICAL STATE / GRAVITY / FLAT SUPPORT`
- Receipts: `VERTICAL_PHYSICAL_STEP` (bounded), `FLAT_GROUND_SUPPORT`
- No agent symbolic z / altitude

## 12–18. Forbidden (V1)

surface elevation support, slopes, stacking, vertical entity impulse, landing sound, friction, 3D index/renderer, lifecycle, Analyzer progress bar.

## 19. Tests

`tests/test_acanthostega_flat_ground_gravity.py` — isolation, geometry, gravity/support (incl. 250-tick grounded rest), held/release/grasp, filter, energy/privacy, persistence, calibration scenarios 1–28. Budgets: unit 1–30, fall ≤50, snapshot ≤100, grounded-rest 250. Scientific validation **not run**.

## 20. Preservation contract

- Default vertical fields omitted from body/object snapshots when at rest defaults → prior-preset snapshot hashes unchanged
- LPS / column-transfer preservation probes exclude `FLAT_GROUND` / `PHASE_C`
- Descendant allowlists in prior suites include Phase C where parent effector-work is already a descendant

## 21. Files touched (lab machine only; uncommitted)

- `mechanistic_mind/physical_system/flat_ground_gravity.py` (new)
- `mechanistic_mind/scientific_v3/flat_ground_gravity_summary.py` (new)
- `tests/test_acanthostega_flat_ground_gravity.py` (new)
- `docs/ACANTHOSTEGA_FLAT_GROUND_GRAVITY.md` (this file)
- Wiring: `experiment_canonical`, `mechanism_registry`, `runtime`, `two_agent`, `physical_manipulator`, contact modules, `resource_objects`, `physical_body/state`, `model/acanthostega`, `model/lines`, serialize, analyzer pipeline, `modelPreset.ts`, `App.tsx`, prior-test allowlists / probes
