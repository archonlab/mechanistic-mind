# Acanthostega — Detached Terrain Material Initial Placement Architecture

**Audit only.** No physics implementation, no new preset/mechanism, no runtime behavior change in this document set.

```text
ARCHITECTURE = DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT_ARCHITECTURE
PARENT_COMPLETE = ACANTHOSTEGA_BETA4_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION
VERDICT = READY_TO_IMPLEMENT
RECOMMENDED_NEXT_SLICE = DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT_V1
FOLLOWING_ROADMAP_SEAM = REPEATED_CONSERVATIVE_TERRAIN_MODIFICATION_ARCHITECTURE
```

## Central question

What is the smallest deterministic, physically honest initial-placement contract for a `ResourceObject` created by `SEPARATE_SURFACE_COLUMN_SLICE`?

## Answer (repository-grounded)

Use the **existing** WMT commit boundary. After the planned column mutation is known, place the object at a **deterministically chosen conflict-free (x,y)** near the source cell, with

```text
z = surface_support_height(world, x, y)   # post-mutation; feet/support reference
physical_state = FREE_STATIC
vx = vy = vz = 0
grounded = True
collision_radius = CANONICAL_COLLISION_RADIUS  # fixed; not mass-derived
```

Do **not** invent ejection impulse. Do **not** use Observer/render correction. Do **not** open a second terrain-removal path.

## Why next (not blocked)

| Prerequisite | Status |
|---|---|
| Single WMT separation path | Present |
| Atomic column + object publish | Present |
| Mass/quantity/component conservation | Present |
| SES / FGG support height API | Present |
| Fixed object radius | Present |
| Bare/held → same SETMR → same WMT | Present (HMSI) |

Gaps are **placement-policy defects**, not missing mechanisms: tip xy conflicts, dead body occupancy check, z tied to source elev rather than local support.

## Evidence pack

`results/acanthostega_detached_terrain_material_initial_placement_architecture/`

| File | Content |
|---|---|
| `CURRENT_CREATION_PIPELINE.md` | Path, seams, current pose |
| `PLACEMENT_GEOMETRY_OPTIONS.md` | Options + chosen authority |
| `ATOMICITY_AND_CONSERVATION_AUDIT.md` | Conservation + conflict |
| `SAME_TICK_ELIGIBILITY_AUDIT.md` | T vs T+1 + ordering |
| `OBSERVER_ANALYZER_CONTRACT.md` | Provenance / snapshot / UI |
| `PERFORMANCE_AND_VALIDATION_BUDGET.md` | Cost + tests |
| `FINAL_REPORT.md` | Verdict block |

## Recommended implementation names (later)

| Item | Name |
|---|---|
| Preset | `ACANTHOSTEGA_BETA4_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT` |
| Parent | `ACANTHOSTEGA_BETA4_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION` |
| Mechanism | `detached_terrain_material_initial_placement` |
| Profile | `DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT_PROFILE_V1` |
| Placement policy id | `DETACHED_TERRAIN_PLACEMENT_POST_MUTATION_SUPPORT_V1` |
| Receipt | `DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT` |

Tiktaalik and all prior Acanthostega presets remain unchanged until that slice is explicitly applied.

## Preservation

No DIG/MINE/TOOL/ORE; no second spawn path; no free KE from separation work; no Phase C change; no cognition leakage; no renderer authority over pose.
