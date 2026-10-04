# ACANTHOSTEGA · P1 INACTIVE OBSERVER PAYLOAD AND RENDER SUSPENSION V1

## Identity
- Schema: `OBSERVER_DERIVED_PAYLOAD_SUBSCRIPTION_V1`
- Capability: `inactive_observer_payload_and_render_suspension`
- Profile: `ACTIVE_CONSUMER_DERIVED_PAYLOAD_GATING_P1_V1`
- Authority: `RESEARCHER_DELIVERY_POLICY_NO_PHYSICAL_EFFECT`

## Verdict
**A. P1_PASS_INACTIVE_WORK_REMOVED**

Inactive researcher Observer consumers no longer force VW7 VOLUME or O6 SURFACE payload construction. Frontend mounts exactly one central renderer and suspends draw work when the tab is hidden or the requested derived payload has not yet arrived.

## Causal separation
| Layer | Effect of P1 |
|-------|----------------|
| Scientific simulation / O1–O5 / VW1–VW7 physics | Unchanged |
| Full scientific evidence / Analyzer saved evidence | Unchanged |
| Snapshots | Unchanged (no subscription fields) |
| Active Observer viewport subscription | Selects which **derived display** families are built/sent/rendered |

## Contract
See `results/p1_inactive_observer_payload_and_render_suspension_v1/SUBSCRIPTION_CONTRACT.md`.

Products `volume_xray` / `surface_light` extend existing `ObserverInterest` (not in presets). Absent interest defaults to MAP-only.

## Server gating
`serialize.world_frame` / `live_frame` resolve `observer_derived_payload_subscription` and gate:
- VW7 `observer_camera_occupancy_consumer.researcher_payload`
- O6 `researcher_physical_optical_audit_view.researcher_summary`

Omitted reason: `NOT_REQUESTED`.

## Frontend
- `DerivedViewportSubscriptionDriver` syncs `volumeWorkspace` → products
- `WorldPane` exclusive-mounts MAP | VOLUME | SURFACE
- Pending subscription shows loading; never keeps stale VOLUME/SURFACE as current
- `TabVisibilityDriver` + `suspended` props skip geometry rebuild/draw when tab hidden
- Left VISION/HEARING keep-alive unchanged; audio not suspended by central mode

## Measured (server, isolated)
See `BENCHMARK_RESULTS.json`. MAP volume/surface build counts = 0 and bytes absent. VOLUME omits SURFACE; SURFACE omits VOLUME.

Browser cold/warm ms: **NOT_MEASURED** (honest); suspension paths are code-proven.

## Next safe seam
From post-P1 bottleneck ranking (VOLUME frame build still dominates when requested):
**P2 · VOLUME persist / incremental geometry** (then P3 SURFACE persist).

Equivalence gate for next slice: same as P1 — canonical fingerprints, O1–O5, actions, VW1 digest, acoustics, snapshots, full scientific evidence; requested payload authority identity.

## Artifacts
`results/p1_inactive_observer_payload_and_render_suspension_v1/`
