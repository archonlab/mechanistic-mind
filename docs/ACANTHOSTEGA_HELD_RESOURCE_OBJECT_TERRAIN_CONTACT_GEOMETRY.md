# Acanthostega Beta 4 — Held ResourceObject ↔ Terrain Contact Geometry

Mechanism: `held_resource_object_terrain_contact_geometry`  
Preset: `ACANTHOSTEGA_BETA4_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY`  
Profile: `HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY_PROFILE_V1`  
Receipt: `HELD_RESOURCE_OBJECT_TERRAIN_CONTACT`  
Parent: `ACANTHOSTEGA_BETA4_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE`

## Contract

```text
HELD_OBJECT_TERRAIN_CONTACT_FACT = YES
HELD_OBJECT_TERRAIN_IMPULSE = NO
HELD_OBJECT_TERRAIN_WORK_TRANSMISSION = NO
HELD_OBJECT_TERRAIN_FAILURE = NO
HELD_OBJECT_TERRAIN_SOUND = NO
AUTOMATIC_RELEASE = NO
```

Geometry fact only. Researcher evidence. No cognition tokens. No WMT.
Penetration may persist until mechanical transmission is implemented.

## Collider

```text
SPHERE_AT_CENTRE_Z_RADIUS_EQ_COLLISION_RADIUS
centre = (obj.x, obj.y, centre_z = obj.z + vertical_half_extent)
radius = collision_radius  (= vertical_half_extent by FGG default)
NOT optical_radius / glyph / point-effector / holder radius
```

Terrain: same `evaluate_probe_contact` / CSG oracle as bare-effector ETC.

## Trajectory / anti-fake-sweep

| Transition | Policy |
|---|---|
| STABLE_HELD | swept + endpoint |
| GRASP_SNAP / no history / holder-hand change | endpoint only |
| RELEASE / removal | END with explicit reason |
| Restore missing prev | no fabricated first-tick sweep |

## Tick seam

Held kinematics finalize → bare-effector ETC (unchanged) → **held-object terrain detect** (once/shared world) → remaining contacts/signals.

Detection does not mutate pose, actuator work, terrain, or WMT.

## Observer / Analyzer

- Canonical selector: new preset once, immediately after Surface Exertion parent.
- Researcher banner + inspector panel when state present.
- Analyzer section: `HELD RESOURCE OBJECT / TERRAIN CONTACT FACTS`.

## Next seam

`HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION_ARCHITECTURE` (not this slice).

Evidence: `results/acanthostega_held_resource_object_terrain_contact_geometry_v1/`
