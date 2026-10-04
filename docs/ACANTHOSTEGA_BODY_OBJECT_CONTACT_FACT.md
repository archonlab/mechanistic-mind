# ACANTHOSTEGA BODY / RESOURCE OBJECT CONTACT FACT

Preset `ACANTHOSTEGA_PHASE_B_BODY_OBJECT_CONTACT` · mechanism `physical_body_resource_object_contact`.

Contact is a measured physical fact only: no impulse, no position/velocity change, no sound, no grasp.

## Implementation map (audit)

| # | Question | Answer |
|---|---|---|
| 1 | Body geometry | Continuous CoM `(body.x, body.y)` + soft-contact half-radius `1.15/2 = 0.575` (matches body-body continuous threshold). Footprint cells used only by body-body overlap, not as solid volume for body/object. |
| 2 | Body-body contact | `resolve_soft_contact`: footprint overlap OR `dist < 1.15`, then impulse + sep. Unchanged. |
| 3 | Previous/current body poses | Contact module stores `prev_body_poses` at end of each detection tick; current = authoritative body after body-body contact + finish_tick. |
| 4 | Previous/current object poses | Same: `prev_object_poses` after detection; current = object after FOK integrate + held snap. |
| 5 | FREE_MOVING integration | Inside `resolve_shared_world_manipulators`, before GRASP/RELEASE. |
| 6 | Held pose update | `update_held_kinematics` before and after grasp/release in same world step. |
| 7 | Spatial index complete | After manipulator `reconcile_contents` and TwoAgent container `reconcile_contents(reason="contact_and_manipulator")`. |
| 8 | One contact phase / world tick | After that container reconcile (TwoAgent) / after single-agent manipulator+reconcile. |
| 9 | Tunneling risk | Yes: object ≤0.75 cell/tick, body ~0.4–0.57; relative can exceed sum of radii. Swept circle implemented. |
| 10 | WRAP | Shortest toroidal delta; swept uses unwrapped start→end along that branch. |
| 11 | Distinct radii | `optical_radius` (vision), `interaction_radius` (held-object/COMBINE), glyph (UI), body footprint (sites), `collision_radius` (NEW, this stage). |
| 12 | Held-object contact | `evaluate_held_object_contact` / BRING_TOGETHER — dual held objects only. Separate mechanism. |
| 13 | Participants | FREE_STATIC + FREE_MOVING. Deposits out. HELD: holder skip; foreign-body held = `HELD_OBJECT_BODY_CONTACT = NOT_IMPLEMENTED`. |
| 14 | Experimenter | Same physical body type / same detection path. |

### Tick seam

```text
body finish_tick (integration)
→ body-body soft contact (+ Audio B if present)
→ resolve_shared_world_manipulators
     held snap → integrate FREE_MOVING → GRASP/RELEASE → release transfer → held snap → held contact/COMBINE
     → reconcile objects
→ container reconcile (bodies+objects)
→ NEW: detect_body_resource_object_contacts  (fact only)
→ later signals / LPS
```

Parent preset = `ACANTHOSTEGA_PHASE_B_FREE_OBJECT_KINEMATICS` (not Audio A/B).


## Final call chain (implemented)

```
TwoAgentRuntime.step
  → per-slot finish_tick (body integrate; manipulators deferred)
  → body-body soft contact / PUSH
  → resolve_shared_world_manipulators  # FREE_MOVING integrate + held pose + GRASP/RELEASE
  → reconcile_contents (spatial index)
  → detect_body_resource_object_contacts  # ONE shared-world phase
       broad phase (spatial index optional) → narrow geometry
       episodes BEGIN/PERSIST/END
       researcher receipts (no response)

PhysicalSystemRuntime.finish_tick (single-agent, manipulators not deferred)
  → … reconcile_contents → detect_body_resource_object_contacts
```

## Geometry

- Body contact radius: `0.575` (= half of body-body soft-contact CoM threshold `1.15`) via `body_contact_geometry`
- Object `collision_radius`: canonical `0.25` (≠ optical `0.45`, ≠ interaction `0.20`, ≠ glyph)
- Swept: IMPLEMENTED; active episodes use endpoint-only for END (swept t=0 cannot block separation)
- HELD_OBJECT_BODY_CONTACT = NOT_IMPLEMENTED
- CONTACT_RESPONSE = NO

## Preset

`ACANTHOSTEGA_PHASE_B_BODY_OBJECT_CONTACT` on top of FREE_OBJECT_KINEMATICS (column-transfer branch, not Audio A/B).
Mechanism: `physical_body_resource_object_contact`.
