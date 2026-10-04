# ACANTHOSTEGA · P2 VOLUME PERSISTENT GEOMETRY AND INCREMENTAL UPDATES V1

## Identity
- Schema: `OBSERVER_VOLUME_INCREMENTAL_PAYLOAD_V1`
- Capability: `volume_persistent_geometry_and_incremental_updates`
- Profile: `VW1_GENERATION_KEYED_VOLUME_DELTA_P2_V1`
- Authority: `RESEARCHER_DERIVED_DELIVERY_OPTIMIZATION_OVER_VW1_NO_PHYSICAL_EFFECT`
- Representation: `COMPACT_INTERVAL_PRISM_LIST_FRONTEND_FACE_EXPAND`

## Verdict
**A. P2_PASS_PERSISTENT_VOLUME_INCREMENTAL_UPDATES**

Ordinary body/object motion no longer rebuilds or resends static VW1 occupancy geometry. DYNAMIC wire omits `occupancy_volumes` when the client holds a matching `static_payload_id`. Materialized static+dynamic matches full VOLUME authority. Internal X-RAY occupancy retained. P1 MAP/SURFACE gating and tab-hidden suspension preserved.

## Decomposition
1. **Static** — VW1 occupancy prism list (`volume_static`) keyed by digest + world dims + runtime generation
2. **Dynamic** — bodies / ResourceObjects / tombstones (`volume_dynamic`) every frame
3. **Reset** — restore, runtime generation, held mismatch, VW1 mutation
4. **UI-only** — camera / X-ray opacity / wireframe local

## Measured (isolated, ≤250 ticks)
| Metric | Value |
|--------|-------|
| Pre-P2 VOLUME build p50 / p95 | 234 / 283 ms |
| Post-P2 cold | ~235 ms |
| Post-P2 warm p95 | ~3.0 ms |
| Body-move warm p95 | ~4.0 ms |
| Static hit rate on body move | 1.0 |
| Static bytes | ~2.25 MB |
| Dynamic bytes p50/p95 | ~1.2 KB |
| Static resend rate (paused polls) | ~0.08 (first FULL only) |

Browser ms: **NOT_MEASURED** (honest); persistent held-static + face cache + ACK implemented.

## Next safe seam
**P4 · global serialize cache** (warm VOLUME delivery is already small; remaining cold cost is VW1 authority enumeration). Alternate: measured browser upload if harness available.

## Artifacts
`results/p2_volume_persistent_geometry_and_incremental_updates_v1/`
