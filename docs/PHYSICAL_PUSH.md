# Physical PUSH (Contact Force Exertion)

Generic contact-mediated force action for Mechanistic Mind / Tiktaalik.

## What the agent can physically do

When `physical_push.mode = EXPERIMENTAL`:

- Action: `PUSH` (not `PUSH_AGENT`)
- Arms `push_exertion` for the tick
- If soft-contact geometry permits, applies impulse along **body heading**
- Equal-and-opposite Δv through ordinary velocity clamps (`v_max`)
- No force without contact (no action-at-a-distance)

When `OFF` (default): `PUSH` not in available actions.

## What the Observer knows

- `PUSH_FORCE_APPLIED` / `PUSH_NO_CONTACT` events
- Receipt: pusher side, impulses, `causally_linked` for motor→force→Δv
- Explicit: later cognition/action of the other agent is **not** auto-causal

## What cognition receives

No `YOU_WERE_PUSHED`, no pusher identity, no target id.  
Other agent experiences only ordinary body velocity / sensory consequences.

## Object / agent / Undercover equivalence

PSR has no separate movable-object class on this path.  
Tiktaalik, Undercover, and any body in `resolve_soft_contact` share the same push physics.  
Legacy `world_engine` `PUSH:id:x,y` is **not** used.

## What is NOT implemented

- PUSH_AGENT / PUSH_OBJECT semantic targets
- Target coordinates or optimal push vectors in cognition
- Force at a distance
- Privileged Undercover push physics

## Scientific claims supported

- Physical force exertion
- Contact-mediated displacement
- Causal provenance: push motor → contact force → velocity delta

## Claims NOT supported by this alone

aggression, play, intentional pushing, social force, helping/attacking

## Snapshot fields

`push_exertion` (cleared each tick after contact resolution) + config `physical_push`

## Parameters

| Field | Default | Role |
|-------|---------|------|
| `push_impulse_scale` | 0.40 | Momentum scale |
| `push_work_cost` | 0.05 | Reserved for work accounting |

## Tests / artifacts

`tests/test_articulated_head_push.py`  
`results/embodiment/active_sensor_orientation_push/`
