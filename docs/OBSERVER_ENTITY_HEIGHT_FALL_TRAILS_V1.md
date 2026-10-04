# OBSERVER_ENTITY_HEIGHT_FALL_TRAILS_V1

## Status

**Implemented** (display-only). Extends `OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1` → **V1_1** with backward-compatible `schema_compatible_with`.

Parent visualization: `OBSERVER_TERRAIN_RELIEF_AND_FREE_SPACE_MARKERS_V1`  
Physical tip unchanged: `ACANTHOSTEGA_BETA4_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION`

## Sample authority

V1A free-space receipts lack per-tick x/y for all entities and are transition-oriented.  
This slice therefore uses:

1. **Authoritative field values** from `entities_vertical` (same serialize-time projection as stems).
2. **Receipt linkage** from bounded RELEASE / SUPPORT_LOSS / LANDING / ACOUSTIC events.
3. **Display-only cache** `world._observer_vertical_trail_cache` marked `DERIVED_OBSERVER_CACHE_NON_AUTHORITATIVE`.

Updated **only** when Observer builds `vertical_display` (no headless cost otherwise).

## Bounds

| Bound | Value |
|-------|------:|
| samples/entity default | 32 |
| samples/entity hard max | 64 |
| visible trail entities | 8 |
| total samples/frame | 256 |
| completed segment lifetime | 48 ticks |
| missing-tick gap threshold | 2 |

## Segments

Start: RELEASE · SUPPORT_LOSS · UNSUPPORTED_TRANSITION · RESTORE_BOUNDARY  
Append while UNSUPPORTED / TERRAIN_INTERSECT / event ticks  
End: LANDING · SUPPORTED_REST · HELD · REMOVED  
HELD objects never get independent FREE trails.  
Supported rest does not grow indefinitely.

Discontinuities: reset/apply/restore clear cache; WRAP splits polylines; missing ticks flagged.

## Frontend

- TRAILS: OFF | SELECTED (default) | UNSUPPORTED
- Length: SHORT 16 / NORMAL 32 / LONG 48
- Display-space height reuses clearance-stem convention (`DISPLAY EXAGGERATION`)
- Label: `AUTHORITATIVE SAMPLES · DISPLAY-SPACE HEIGHT · RESEARCHER ONLY`
- INTERPOLATION_DEFAULT = OFF

## Analyzer

`VERTICAL TRAJECTORIES` reconstructs release/excavation stories from samples+receipts.  
Legacy: `FULL VERTICAL TRAIL NOT AVAILABLE FOR THIS RUN`.  
Progress bar: TEXT_STATUS_ONLY.

## Next

Optional transect deferred — acoustic stream contract is higher value next.  
`AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_CONTRACT`
