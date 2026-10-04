# Acanthostega — Held-Mediated Surface Exertion Integration

**Integration slice V1.** Routes held-object transmitted actuator work into the existing SETMR / WMT path.

```text
IMPLEMENTATION_STARTED = YES
MECHANISM = held_mediated_surface_exertion_integration
PRESET = ACANTHOSTEGA_BETA4_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION
PARENT = ACANTHOSTEGA_BETA4_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION
```

## Contract

| Concern | V1 |
|---|---|
| New transmission law | NO |
| New resistance law | NO |
| Second accumulator | NO |
| Second terrain-removal path | NO |
| Semantic tool classes | NO |
| Eligible input (held) | `work_transmitted_to_terrain` |
| Eligible input (tip) | `work_used` (unchanged) |
| Failure / WMT | SAME SETMR gate → SEPARATE_SURFACE_COLUMN_SLICE |

## Evidence

`results/acanthostega_held_mediated_surface_exertion_integration_v1/`
