# Acanthostega — Held Object ↔ Terrain Mechanical Transmission Architecture

**Architecture complete. Implementation slice V1 landed.**

```text
IMPLEMENTATION_STARTED = YES
MECHANISM = held_resource_object_terrain_mechanical_transmission
PRESET = ACANTHOSTEGA_BETA4_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION
ORDINARY_MATTER_MEDIATES_MECHANICAL_INTERACTION = target interpretation
TOOL_USE = researcher interpretation requiring behavioral evidence (not V1)
```

## One-line verdict

Add a **held-object `ExternalRelativeConstraint`** to the existing EBAE relative_z admission stack (preflight inside `request_actuated_relative_displacement`); emit a transmitted-work partition from the **same** `ABSTRACT_BOUNDED_ACTUATOR_V1` budget; route into SETMR in a **following** slice. Do not mint work from HOTC facts. Do not debit `mechanical_work_reservoir` for this path.

## Critical empirical gap (13-tick probe, seed=17)

While HELD and lowering:

| Step | held_clearance | tip_clearance | work_used |
|---|---|---|---|
| 0 | −0.05 (contact) | +0.52 | 0 |
| … | deepening | still free | 0 |
| 6 | −0.575 | ~0 | first tip block |

Held volume penetrates ~`BODY_CONTACT_RADIUS` before tip constraint spends actuator work.

## V1 implementation status

```text
HeldObjectTerrainRelativeZConstraint in EBAE default_external_constraints = YES
constraint_kind = held_resource_object_terrain
work_used = work_transmitted (+ residual ≈ 0) when held wins = YES
SETMR / WMT / terrain failure in transmission-only slice = NO
FOLLOWING_SLICE = HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION_V1 = IMPLEMENTED
```

## Documents

`results/acanthostega_held_object_terrain_mechanical_transmission_architecture/`
`results/acanthostega_held_resource_object_terrain_mechanical_transmission_v1/`
`results/acanthostega_held_mediated_surface_exertion_integration_v1/`
`docs/ACANTHOSTEGA_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION.md`

Prior alias pack (same audit lineage):  
`results/acanthostega_held_resource_object_terrain_mechanical_transmission_architecture/`
