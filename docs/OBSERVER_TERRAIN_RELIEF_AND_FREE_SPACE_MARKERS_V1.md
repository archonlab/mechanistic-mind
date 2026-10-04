# OBSERVER_TERRAIN_RELIEF_AND_FREE_SPACE_MARKERS_V1

## Status

**Implemented** (display-only Observer slice). No physics, no new physical preset, no FPV, no audio playback, no fall trails.

## Parent tip

`ACANTHOSTEGA_BETA4_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION` (Free-Space V1A–V1D).

## Display contract

`OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1` — **not** a physical mechanism.

Top-level frame field: `world.vertical_display` (researcher-only).

### Payload

| Block | Contents | Authority |
|-------|----------|-----------|
| `cell_centre_elevation` | Dense H×W grid, order `row_major_y_outer_x_inner`, cell-centre samples via `resolved_column_at(x+0.5,y+0.5)` | AUTHORITATIVE SIMULATION STATE (serialized projection) |
| `sparse_deltas[]` | baseline / current / signed_delta / revision / checksums | AUTHORITATIVE |
| `entities_vertical[]` | base_z, centre_z, support_z, clearance, vz, support/physical state, collision_radius | AUTHORITATIVE |
| `events_recent[]` | RELEASE, SUPPORT_LOSS, LANDING_RESPONSE, ACOUSTIC_EMISSION | RESEARCHER-AUTHORITATIVE RECEIPT |
| packed min/max + cache | surface_generation + deltas_checksum keyed | BACKEND-DERIVED DISPLAY CACHE |

Dense subsurface layers are **never** serialized.

### Cache

- Attr: `world._observer_vertical_display_cache` (non-authoritative, not in scientific snapshots).
- Key: schema + dims + `surface_generation` + `deltas_checksum` + generator version.
- Invalidated on excavation (key change), restore/reset/apply (`invalidate_vertical_display_cache`).

### Event lifetime

- Cap: 24 recent markers.
- Display lifetime: 32 ticks (backend-derived helper metadata).
- Restore does **not** replay marker animation (cache cleared; frontend lifetime is frame-relative).

## Frontend

World Map controls (researcher-only):

- `TERRAIN: OPTICAL` (default)
- `TERRAIN: ELEVATION` — false-color from authoritative elevation (1× physical semantics)
- `TERRAIN: DELTA` — sparse excavation overlay
- Optional CONTOURS (render-derived)
- Clearance stems with labelled `DISPLAY EXAGGERATION` (default 2×; stems only)
- Bounded event markers

Label: **RESEARCHER VIEW · NOT AGENT PERCEPTION**

## Classification

- **RENDER_DERIVED**: false color, contours, stems, marker pulse/lifetime, interpolation (default OFF), exaggeration.
- **AGENT SENSOR / FPV**: unchanged.
- **NOT MODELLED**: caves, ceilings, overhangs, stacked terrain, volumetric cavities, 3D acoustic propagation.

## Analyzer

Section `ELEVATION / EXCAVATION / FREE-SPACE STORY` reconstructs causal chains from receipts when present.
Legacy runs without elevation payload: `ELEVATION VISUALIZATION NOT AVAILABLE FOR THIS RUN`.
`ANALYZER_PROGRESS_BAR_STATUS = TEXT_STATUS_ONLY` (not implemented here).

## Privacy

Forbidden cognition tokens include:
`OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1`, `CURRENT_ELEVATION`, `TERRAIN_DELTA`, `CLEARANCE_STEM`, `DISPLAY_EXAGGERATION`, `SUPPORT_LOSS_MARKER`, `LANDING_MARKER`, `PHYSICAL_SOUND_SOURCE_MARKER`.

## Next seam

`OBSERVER_ENTITY_HEIGHT_FALL_TRAILS_V1`
