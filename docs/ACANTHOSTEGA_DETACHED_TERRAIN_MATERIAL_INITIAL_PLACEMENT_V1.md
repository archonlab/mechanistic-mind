# Acanthostega Beta 4 — Detached Terrain Material Initial Placement V1

```text
IMPLEMENTATION_STARTED = YES
MECHANISM = detached_terrain_material_initial_placement
PRESET = ACANTHOSTEGA_BETA4_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
PARENT = ACANTHOSTEGA_BETA4_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION
PROFILE = DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT_PROFILE_V1
PLACEMENT_POLICY = DETACHED_TERRAIN_PLACEMENT_POST_MUTATION_SUPPORT_V1
```

## Contract

| Item | V1 |
|---|---|
| Placement authority | Post-mutation `surface_support_height(x,y)` |
| Support→centre-z | `object.z = support_z` (feet); `centre_z = z + collision_radius` |
| Candidates | K≤16 fixed offsets from cell centre |
| Conflict | Body + ResourceObject 2D circle; reject WMT if none free |
| Velocity | Exactly zero; no separation impulse |
| Dynamics | `dynamics_eligible_tick = creation_tick + 1` |
| Spawn path | Same `SEPARATE_SURFACE_COLUMN_SLICE` WMT only |

## Evidence

`results/acanthostega_detached_terrain_material_initial_placement_v1/`
