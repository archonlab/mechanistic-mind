# ACANTHOSTEGA BODY / RESOURCE OBJECT CONTACT IMPULSE

Preset `ACANTHOSTEGA_PHASE_B_BODY_OBJECT_IMPULSE` · mechanism `body_resource_object_contact_impulse`.

Separate **response** module on top of contact FACT (`physical_body_resource_object_contact`).
Contact detector stays authoritative for geometry. Contact-fact-only preset must keep working
without this response (`impulse_transferred=false` always in FACT receipts).

## Parent chain

`ACANTHOSTEGA_PHASE_B_BODY_OBJECT_CONTACT` → + mass/compliance normal impulse RESPONSE.

Absent from beta31, Tiktaalik, previous Acanthostega, contact-fact-only, Audio A/B, FOK-only.

## Impulse law (LOCKED)

- Frictionless **normal only**; no tangential change; no sound.
- Normal `n` = unit(shortest_toroidal body→object). Coincident centres: `n=(1,0)`.
- Pre-velocities at response time: `v_body`, `v_obj` (cells/tick).
- `v_rel = v_obj - v_body`; `v_rel_n = dot(v_rel, n)`.
- Impulse **only if approaching**: `v_rel_n < -approach_epsilon`.
- `j = -(1+e) * v_rel_n / (1/m_b + 1/m_o)` with `j > 0` when approaching.
- `Δv_body = -(j/m_b) * n`; `Δv_obj = +(j/m_o) * n`.
- Body clamp `±body_cfg.v_max` after Δv. Object clamp to FOK `max_free_object_speed`.
- Invalid mass (`<=0` or non-finite) → no impulse, `INVALID_MASS` (never silent 1.0).

## Compliance → restitution (LOCKED)

```
e = clamp(e_max * (1 - compliance), e_min, e_max)
```

Defaults: `e_min=0.0`, `e_max=0.85`. Compliance unitless `[0,1]` from
`passive_material_properties` composition-weighted derive; **neutral 0.5** if
passive props off / missing (noted in receipt). Prefer **object** material compliance
as contact surface. Body compliance not required this stage.

Compliance is **not** used in continuous motion yet — this stage maps compliance → `e` only.

## Persistence / dedupe

- Response key: `f"{episode_id}:{tick}:{seq}"`.
- Impulse only on approach; resting/separating → `j=0` (`RESTING_NO_APPROACH` / `SEPARATING`).
- Track `last_approach_signature` per pair so resting PERSIST does not re-fire.
- **Allow** a new impulse in the same episode if `v_rel_n` becomes approaching again
  after a non-approaching period.

## Tick seam

```
body finish_tick (x += v; gentle v_stop may run)
→ body-body soft contact
→ resolve_shared_world_manipulators  # FREE_MOVING integrates HERE (before contact)
→ reconcile_contents
→ detect_body_resource_object_contacts   # FACT (unchanged)
→ apply_body_object_contact_impulse      # RESPONSE (this module)
     → optional reconcile_contents if position corrected
→ later signals / LPS
```

Impulse affects body position on the **next** `finish_tick` (`x += v`).
Object post-velocity is for the **next** FOK tick (do not double-integrate this tick).

## Gentle v_stop grace

After nonzero impulse: `body._boc_impulse_grace_ticks = 1`.
`integrate_com_translation` skips snap when grace>0 and decrements.
`apply_ground_rest_after_self_drive` skips snap when grace>0 (no second decrement).

## Swept crossing policy

1. Reconstruct poses at `contact_fraction` along start→end (toroidal unwrapped).
2. Set body/object to those poses (WRAP).
3. Apply impulse using velocities.
4. Do **not** integrate remainder this tick (post-impact `v` for next tick).
Do not rewrite contact-fact measurements after the fact.

## Position correction

Endpoint penetration only: mass-weighted along normal if `penetration > slop`;
WRAP-safe; bounded by `max_position_correction`; position only (no momentum change).
Marked numerical constraint in receipt.

## FREE_STATIC / FREE_MOVING

After response: if `|v_obj| >= FOK rest_threshold` → `FREE_MOVING`; else `FREE_STATIC` and `v=0`.
Reuse FOK thresholds when available (else rest `0.01`). Do not change FOK damping formula.

## Scope / forbidden

FREE_STATIC + FREE_MOVING only. HELD skipped. `HELD_OBJECT_BODY_CONTACT = NOT_IMPLEMENTED`.
No friction, rolling, angular, object-object, damage, sound, gravity, z, recipes, reward.

## Observer

- Contact-fact-only: `NO IMPULSE · NO RESPONSE`
- Impulse preset: `MASS + COMPLIANCE NORMAL RESPONSE · NO FRICTION · NO SOUND`
  (normal, impulse vector, pre/post vel, correction, masses, e, residual, reason).
Renderer does not compute physics.

## Receipts

`BODY_RESOURCE_OBJECT_CONTACT_RESPONSE` (response module).
Contact FACT receipts keep `impulse_transferred=false`.
