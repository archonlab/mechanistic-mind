# Acanthostega — Held ResourceObject ↔ Terrain Mechanical Transmission Architecture

**Status:** architecture / provenance / conservation audit only.  
**Implementation:** NOT in this task.  
**Parent tip today:** `ACANTHOSTEGA_BETA4_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY`  
**Frozen Phase C:** `ACANTHOSTEGA_PHASE_C_COHERENT_SLOPE_DYNAMICS`

## Goal

Determine how bounded actuator effort can transmit:

```text
ABSTRACT_BOUNDED_ACTUATOR_V1
  → grasp/attachment kinematic constraint
  → held ResourceObject volume
  → genuine held-object ↔ CSG terrain contact
  → existing SETMR fracture accumulator
  → existing SEPARATE_SURFACE_COLUMN_SLICE WMT
```

without a second work source, duplicate debit, fake impulse, tool semantics, second failure path, pressure/stress invention, or Phase C change.

## Verdict (one line)

Transmission must enter as an **additional `ExternalRelativeConstraint` on the existing EBAE relative_z admission stack**, keyed by HELD attachment on that effector — not as a post-hoc HOTC fact consumer and not as a new actuator.

## Critical geometry fact

```text
tip_z   = body.z + BODY_CONTACT_RADIUS(0.575) + relative_z
held_z  = body.z + relative_z
⇒ held lower face contacts terrain ~0.575 before bare tip
⇒ tip-only TerrainRelativeZConstraint cannot carry held-object loading
```

## Safe causal chain (future)

```text
ABSTRACT_BOUNDED_ACTUATOR_V1
  → HeldObjectTerrainRelativeZConstraint (compose with tip; one winner)
  → work_used (single)
  → SETMR fracture accumulator (same)
  → SEPARATE_SURFACE_COLUMN_SLICE (same WMT)
```

HOTC BEGIN/PERSIST/END stays researcher geometry; must not mint work.

## Next implementation slice

`HELD_RESOURCE_OBJECT_TERRAIN_ACTUATOR_CONSTRAINT_V1` under parent HOTC preset tip.  
Not tool semantics. Not pressure. Not a second failure path.

Evidence: `results/acanthostega_held_resource_object_terrain_mechanical_transmission_architecture/`

**Canonical pack (Parts 1–20 complete):**  
`docs/ACANTHOSTEGA_HELD_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION_ARCHITECTURE.md`  
`results/acanthostega_held_object_terrain_mechanical_transmission_architecture/`
