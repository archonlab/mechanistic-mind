# OBSERVER_ELEVATION_EXCAVATION_FREE_SPACE_VISUALIZATION — Architecture

## Status

**Architecture audit only.** No frontend, backend, physics, or `web_dist` changes in this task.

## Parent tip (verified in code)

| Field | Value |
|-------|-------|
| Cumulative tip | `ACANTHOSTEGA_BETA4_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION` |
| Model line | `ACANTHOSTEGA` |
| Free-Space | V1A + V1B + V1C + V1D complete |
| Renderer | World Map = HTML **Canvas 2D** (`WorldMap.tsx`) |
| Camera | Orthographic top-down (pan/zoom) |

## Central principle

```
simulation state → backend observer serialization → read-only visualization → pixels
```

Never: pixels → physics/support/collision/cognition.

Display-only quantities (hillshade, contours, stems, trails, lerp) = `RENDER_DERIVED_NON_AUTHORITATIVE`.

## Modes (must remain distinct)

| Mode | Role | This stage |
|------|------|------------|
| WORLD MAP / RESEARCHER VIEW | May show researcher-only elevation/z/events with labels | **In scope** |
| FPV WORLD | Future human view from body pose using world geometry | Contract only |
| FPV PERCEPTION / SENSOR SPACE | Existing `TiktaalikEyePanel` / near-field samples only | **Unchanged** |

## Why pits/falls are illegible today

1. **No elevation layer.** WorldMap heatmaps `T`/`R`/… via `scalarGrid`; elevation is not a scalar.
2. **Sparse deltas are indices only.** `procedural_surface_columns.researcher_payload` sends `delta_cells` + count/checksum — **not** elevations.
3. **Top-down collapse.** Bodies/objects drawn at `(x,y)` only; `WorldMap` never reads `z`/`vz`/`grounded`.
4. **Glyph ≠ physical size.** Object diamond ≈ `cell*0.22`; collision circle only when body–object overlay is on.
5. **Event panels ≠ map markers.** V1A/V1B/V1C/V1D exist as Inspector banners/receipts, not map geometry.

## Recommended first implementation slice

**`OBSERVER_TERRAIN_RELIEF_AND_FREE_SPACE_MARKERS_V1`** (parent: V1D tip)

Includes, minimally:

1. Hybrid authoritative elevation payload (dense cell-centre grid + sparse delta records with baseline/current).
2. Selectable researcher overlay: CURRENT ELEVATION (+ optional DELTA).
3. Selected/all entity **clearance stems** (base z vs support z).
4. Event markers: support-loss, RELEASE, V1B landing response, V1C sound source (researcher-only).

Does **not** include: pseudo-isometric, full 3D, FPV, audio playback, side-profile inset (Inspector numbers first), Analyzer progress bar.

## Following slices

1. `OBSERVER_ENTITY_HEIGHT_FALL_TRAILS_V1` — trails, optional display lerp, all-entity stems.
2. `OBSERVER_SELECTED_TRANSECT_PROFILE_V1` — optional side profile.
3. `AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_CONTRACT` → human-audible → organism auditory → extended.

## Docs in this pack

See `results/observer_elevation_excavation_free_space_visualization_architecture/`.
