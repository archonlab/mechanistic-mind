# ACANTHOSTEGA_BETA4_PUBLIC_MODEL_CONVERGENCE_AND_SELECTOR_BOUNDARY_REPAIR_V1

## Purpose
Converge Free-Space V1D + VW1–VW6 into one public Acanthostega Beta 4.0 model, restrict the normal selector to Tiktaalik Beta 3.1 + Acanthostega Beta 4.0, keep development fixtures registered, and render baseline VW1 occupancy in VOLUME.

## Public models
| ID | Label |
|---|---|
| `TIKTAALIK_BETA31` | Tiktaalik Beta 3.1 |
| `ACANTHOSTEGA_BETA4` | Acanthostega Beta 4.0 |

## Builder
`acanthostega_beta4_config()` = Free-Space V1D tip + `set_effector_held_occupancy_exertion_bridge(True)` + `set_minimal_vision_3d_geometric_interface(True)`.

## Classification helpers
- `PUBLIC_MODEL_PRESET_IDS` / `is_public_model_selector_entry` / `public_model_selector_entries` / `visibility_class_for_preset`
- Frontend: `PUBLIC_MODEL_PRESETS` / `isPublicModelSelectorEntry`

## Baseline VOLUME
`build_occupancy_volume_primitives` enumerates VW1 `occupied_intervals_at` over the canonical tile (not sparse-only).

## Held→world
Remains BLOCKED. VW4 transaction existence ≠ organism trigger.

## Evidence
`results/acanthostega_beta4_public_model_convergence_and_selector_boundary_repair_v1/`
