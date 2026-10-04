# ACANTHOSTEGA_EFFECTOR_TO_GROUND_REACHABILITY_AUDIT_V1

Repository-first audit: can Acanthostega Beta 4.0 bare effectors (and separately held objects) physically contact supporting VW1 occupancy?

## Primary verdict

**A. CANONICAL_BARE_EFFECTOR_GROUND_CONTACT_REACHABLE**

Both LEFT and RIGHT bare point probes intersect supporting occupancy under the implemented relative_z DOF (±1.075). A rate-limited multi-tick drive emits ETC `contact_fact` and VW5 identifies the floor interval. EBAE transmits bounded actuator work at the terrain constraint. Material failure was not forced.

## Limiting operational note (not a morphology blocker)

`relative_z` is a genuine physical DOF (`cognition_exposed=False`). Ordinary cognition has no action token to drive it. A short ordinary run (20 ticks) visited 0 ground-reachable configurations — policy utilization only, not physical impossibility.

## Key constants (code authority)

| Quantity | Value |
|----------|-------|
| Body vertical half extent / contact radius | 0.575 |
| Effector tip Z | `centre_z + relative_z` |
| Relative Z envelope | ±1.075 |
| Relative Z rate | 0.1075 / tick |
| Terrain contact probe radius | 0 (not grasp optical 0.40) |
| Clearance | `(tip_z − r) − floor_z_max` (VW5 floor-primary) |

## Evidence

`results/acanthostega_effector_to_ground_reachability_audit_v1/`

Harness: `experiments/run_acanthostega_effector_to_ground_reachability_audit_v1.py`

## Next seam

Volumetric Analyzer design using existing reach/contact evidence; distinguish `NOT_SELECTED` / policy non-use of relative_z from geometric unreachability. Do not begin FIRST_HABITABLE on morphology grounds.

Production physics unchanged. No Analyzer implementation in this slice. No excavation success claimed.
