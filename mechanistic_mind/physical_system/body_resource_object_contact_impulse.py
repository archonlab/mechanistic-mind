"""Acanthostega body ↔ ResourceObject MASS + COMPLIANCE contact RESPONSE.

Preset: ACANTHOSTEGA_PHASE_B_BODY_OBJECT_IMPULSE
Mechanism: body_resource_object_contact_impulse

Separate response module on top of contact FACT.
Contact detector stays authoritative for geometry; contact-fact-only preset
must keep working without this response.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "body_resource_object_contact_impulse"
PROFILE_VERSION = "BODY_RESOURCE_OBJECT_CONTACT_IMPULSE_PROFILE_V1"
STATE_SCHEMA = "BODY_RESOURCE_OBJECT_CONTACT_IMPULSE_STATE_V1"
RECEIPT_KIND = "BODY_RESOURCE_OBJECT_CONTACT_RESPONSE"
EVENT_STEP = "BODY_RESOURCE_OBJECT_CONTACT_RESPONSE_STEP"

NEUTRAL_COMPLIANCE = 0.5

REASON_APPROACHING = "APPROACHING"
REASON_SEPARATING = "SEPARATING"
REASON_RESTING = "RESTING_NO_APPROACH"
REASON_INVALID_MASS = "INVALID_MASS"
REASON_ALREADY_PROCESSED = "ALREADY_PROCESSED"
REASON_BELOW_THRESHOLD = "BELOW_IMPULSE_THRESHOLD"
REASON_NO_CONTACT = "NO_CONTACT_FACT"
REASON_HELD_SKIPPED = "HELD_SKIPPED"

PHYSICAL_STATE_FREE_STATIC = "FREE_STATIC"
PHYSICAL_STATE_FREE_MOVING = "FREE_MOVING"
PHYSICAL_STATE_HELD = "HELD"

DETECTION_SWEPT = "SWEPT_CROSSING"
DETECTION_ENDPOINT = "ENDPOINT_OVERLAP"


@dataclass
class BodyObjectContactImpulseConfig:
    enabled: bool = False
    approach_epsilon: float = 1e-9
    max_contact_impulse: float = 2.0
    penetration_slop: float = 0.02
    max_position_correction: float = 0.35
    e_min: float = 0.0
    e_max: float = 0.85
    impulse_threshold: float = 1e-12
    history_limit: int = 64
    # When True, apply mass-weighted position correction for endpoint penetration.
    position_correction_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "approach_epsilon": float(self.approach_epsilon),
            "max_contact_impulse": float(self.max_contact_impulse),
            "penetration_slop": float(self.penetration_slop),
            "max_position_correction": float(self.max_position_correction),
            "e_min": float(self.e_min),
            "e_max": float(self.e_max),
            "impulse_threshold": float(self.impulse_threshold),
            "history_limit": int(self.history_limit),
            "position_correction_enabled": bool(self.position_correction_enabled),
            "profile_version": PROFILE_VERSION,
            "friction": False,
            "sound_emitted": False,
            "tangential_impulse": False,
            "held_object_body_contact": "NOT_IMPLEMENTED",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BodyObjectContactImpulseConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown body/object contact impulse profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            approach_epsilon=float(data.get("approach_epsilon", 1e-9)),
            max_contact_impulse=float(data.get("max_contact_impulse", 2.0)),
            penetration_slop=float(data.get("penetration_slop", 0.02)),
            max_position_correction=float(data.get("max_position_correction", 0.35)),
            e_min=float(data.get("e_min", 0.0)),
            e_max=float(data.get("e_max", 0.85)),
            impulse_threshold=float(data.get("impulse_threshold", 1e-12)),
            history_limit=int(data.get("history_limit", 64)),
            position_correction_enabled=bool(data.get("position_correction_enabled", True)),
        )


def body_object_impulse_is_active(config: Any) -> bool:
    cfg = getattr(config, "body_resource_object_contact_impulse", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_body_object_impulse(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "body_resource_object_contact_impulse", None)
    if cur is None:
        config.body_resource_object_contact_impulse = BodyObjectContactImpulseConfig(enabled=on)
    else:
        cur.enabled = on
    # Impulse preset requires contact FACT; enabling impulse also ensures contact is on.
    if on:
        from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
            set_body_object_contact,
        )
        set_body_object_contact(config, True)


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "body_resource_object_contact_impulse.enabled",
        "enabled": bool(enabled),
        "description": (
            "Acanthostega researcher-only body↔ResourceObject mass+compliance "
            "normal contact RESPONSE (impulse + position correction). No friction/sound."
        ),
        "agent_accessible": False,
        "collision_response": True,
        "friction": False,
        "sound": False,
    }


def restitution_from_compliance(compliance: float, *, e_min: float, e_max: float) -> float:
    """e = clamp(e_max * (1 - compliance), e_min, e_max). Higher compliance → lower e."""
    c = float(compliance)
    if not math.isfinite(c):
        c = NEUTRAL_COMPLIANCE
    c = max(0.0, min(1.0, c))
    e = float(e_max) * (1.0 - c)
    lo, hi = float(e_min), float(e_max)
    if lo > hi:
        lo, hi = hi, lo
    return float(max(lo, min(hi, e)))


def object_compliance(obj: Any, config: Any) -> tuple[float, str]:
    """Prefer object material compliance; neutral 0.5 if passive props off/missing."""
    note = "OBJECT_MATERIAL_COMPLIANCE"
    try:
        from mechanistic_mind.physical_system.passive_material_properties import (
            derive_effective_properties,
            passive_material_properties_is_active,
        )
        if not passive_material_properties_is_active(config):
            return NEUTRAL_COMPLIANCE, "NEUTRAL_PASSIVE_PROPS_OFF"
        report = derive_effective_properties(getattr(obj, "composition", None))
        c = float(report.get("compliance", NEUTRAL_COMPLIANCE))
        if not math.isfinite(c):
            return NEUTRAL_COMPLIANCE, "NEUTRAL_NONFINITE"
        return max(0.0, min(1.0, c)), note
    except Exception:
        return NEUTRAL_COMPLIANCE, "NEUTRAL_DERIVATION_FALLBACK"


def contact_normal_from_displacement(dx: float, dy: float) -> tuple[float, float]:
    """Unit normal body→object. Coincident centres → (1, 0) matching contact module."""
    dist = math.hypot(float(dx), float(dy))
    if dist < 1e-12:
        return 1.0, 0.0
    return float(dx) / dist, float(dy) / dist


def _valid_mass(m: Any) -> bool:
    try:
        v = float(m)
    except (TypeError, ValueError):
        return False
    return bool(math.isfinite(v) and v > 0.0)


def _clamp_speed(vx: float, vy: float, vmax: float) -> tuple[float, float, bool]:
    sp = math.hypot(vx, vy)
    if sp <= float(vmax) or sp < 1e-18:
        return float(vx), float(vy), False
    s = float(vmax) / sp
    return float(vx) * s, float(vy) * s, True


@dataclass
class BodyObjectContactImpulseState:
    config: BodyObjectContactImpulseConfig
    processed_keys: set[str] = field(default_factory=set)  # response_key set
    last_approach_signature: dict[str, str] = field(default_factory=dict)  # pair_key -> signature
    response_seq: int = 0
    response_tick: int = -1
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


def _zero_counters() -> dict[str, int]:
    return {
        "responses": 0,
        "impulses_applied": 0,
        "position_corrections": 0,
        "separating": 0,
        "resting": 0,
        "already_processed": 0,
        "invalid_mass": 0,
        "below_threshold": 0,
        "swept_pose_set": 0,
        "skipped_held": 0,
    }


def state_of(world: Any) -> BodyObjectContactImpulseState | None:
    raw = getattr(world, "body_object_contact_impulse_state", None)
    return raw if isinstance(raw, BodyObjectContactImpulseState) else None


def ensure_body_object_impulse_for_runtime(world: Any, config: Any) -> BodyObjectContactImpulseState | None:
    if not body_object_impulse_is_active(config):
        world.body_object_contact_impulse_state = None
        return None
    cfg = getattr(config, "body_resource_object_contact_impulse", None) or BodyObjectContactImpulseConfig(enabled=True)
    st = state_of(world)
    if st is None:
        st = BodyObjectContactImpulseState(config=cfg, counters=_zero_counters())
        world.body_object_contact_impulse_state = st
    else:
        st.config = cfg
    return st


def copy_state(st: BodyObjectContactImpulseState | None) -> BodyObjectContactImpulseState | None:
    if st is None:
        return None
    return BodyObjectContactImpulseState(
        config=BodyObjectContactImpulseConfig.from_dict(st.config.to_dict()),
        processed_keys=set(st.processed_keys),
        last_approach_signature={k: str(v) for k, v in st.last_approach_signature.items()},
        response_seq=int(st.response_seq),
        response_tick=int(st.response_tick),
        last_step=dict(st.last_step) if st.last_step else None,
        history=[dict(h) for h in st.history],
        counters=dict(st.counters),
    )


def serialize_state(st: BodyObjectContactImpulseState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    # Persist grace on bodies via world attribute bag when present
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "processed_keys": sorted(st.processed_keys),
        "last_approach_signature": {k: str(v) for k, v in sorted(st.last_approach_signature.items())},
        "response_allocator": {"tick": int(st.response_tick), "next_sequence": int(st.response_seq)},
        "counters": dict(st.counters),
        "history": list(st.history)[-int(st.config.history_limit):],
    }


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> BodyObjectContactImpulseState | None:
    if not body_object_impulse_is_active(config):
        world.body_object_contact_impulse_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_body_object_impulse_for_runtime(world, config)
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(f"unknown body/object contact impulse state schema: {data.get('schema_version')}")
    cfg = BodyObjectContactImpulseConfig.from_dict(data.get("config"))
    cfg.enabled = True
    alloc = data.get("response_allocator") or {}
    st = BodyObjectContactImpulseState(
        config=cfg,
        processed_keys=set(str(k) for k in (data.get("processed_keys") or [])),
        last_approach_signature={str(k): str(v) for k, v in (data.get("last_approach_signature") or {}).items()},
        response_tick=int(alloc.get("tick", -1)),
        response_seq=int(alloc.get("next_sequence", 0)),
        history=list(data.get("history") or []),
        counters={**_zero_counters(), **{k: int(v) for k, v in (data.get("counters") or {}).items()}},
    )
    world.body_object_contact_impulse_state = st
    config.body_resource_object_contact_impulse = cfg
    return st


def _alloc_seq(st: BodyObjectContactImpulseState, tick: int) -> int:
    if int(st.response_tick) != int(tick):
        st.response_tick = int(tick)
        st.response_seq = 0
    st.response_seq += 1
    return int(st.response_seq)


def _fok_thresholds(config: Any) -> tuple[float, float]:
    fok = getattr(config, "free_resource_object_kinematics", None)
    rest = float(getattr(fok, "rest_threshold", 0.01) or 0.01) if fok is not None else 0.01
    vmax = float(getattr(fok, "max_free_object_speed", 0.75) or 0.75) if fok is not None else 0.75
    if not math.isfinite(rest) or rest <= 0.0:
        rest = 0.01
    if not math.isfinite(vmax) or vmax <= 0.0:
        vmax = 0.75
    return rest, vmax


def _set_grace(body: Any, ticks: int = 1) -> None:
    try:
        body._boc_impulse_grace_ticks = int(ticks)
    except Exception:
        pass


def _lerp_toroidal(ax: float, ay: float, bx: float, by: float, t: float, width: int, height: int) -> tuple[float, float]:
    """Interpolate from A to B along shortest toroidal branch; return wrapped pose."""
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        shortest_toroidal_delta,
    )
    from mechanistic_mind.planet.topology import wrap_coord
    dx, dy = shortest_toroidal_delta(ax, ay, bx, by, width, height)
    # Note: shortest_toroidal_delta(ax,ay,bx,by) = unwrapped (b-a)
    x = float(wrap_coord(ax + float(t) * dx, width))
    y = float(wrap_coord(ay + float(t) * dy, height))
    return x, y


def apply_body_object_contact_impulse(
    world: Any,
    bodies: list[tuple[str, Any, Any]],
    *,
    tick: int,
    config: Any,
) -> dict[str, Any] | None:
    """Apply mass+compliance normal impulse AFTER contact detect.

    bodies: list of (body_id, body, body_cfg). Safe to mutate vx/vy after finish_tick.
    Does NOT modify contact-fact measurements. Writes BODY_RESOURCE_OBJECT_CONTACT_RESPONSE.
    """
    if not body_object_impulse_is_active(config):
        return None
    # Contact FACT must be active and have produced a step this tick
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        body_object_contact_is_active,
    )
    if not body_object_contact_is_active(config):
        return None
    st = ensure_body_object_impulse_for_runtime(world, config)
    if st is None:
        return None
    cfg = st.config
    contact_step = getattr(world, "last_body_object_contact_step", None)
    if not isinstance(contact_step, dict):
        return None
    if int(contact_step.get("tick", -1)) != int(tick):
        # Still allow if detect just ran with this tick; otherwise skip
        pass

    height, width = int(world.T.shape[0]), int(world.T.shape[1])
    from mechanistic_mind.planet.topology import wrap_coord

    body_map = {str(bid): (b, bcfg) for bid, b, bcfg in bodies if b is not None}
    obj_map = {str(o.object_id): o for o in list(getattr(world, "resource_objects", None) or [])}
    rest_thr, max_obj_speed = _fok_thresholds(config)

    # Active contact facts this tick (BEGIN + PERSIST); END has contact_fact=False
    candidates: list[dict[str, Any]] = []
    for row in list(contact_step.get("begin") or []) + list(contact_step.get("persist") or []):
        if not isinstance(row, dict):
            continue
        if not bool(row.get("contact_fact")):
            continue
        candidates.append(row)
    candidates.sort(key=lambda r: (str(r.get("body_id")), str(r.get("object_id")), str(r.get("episode_id"))))

    receipts: list[dict[str, Any]] = []
    any_position_changed = False

    for meas in candidates:
        body_id = str(meas.get("body_id"))
        object_id = str(meas.get("object_id"))
        episode_id = str(meas.get("episode_id") or "")
        pair_key = str(meas.get("pair_key") or f"{body_id}|{object_id}")
        seq = _alloc_seq(st, tick)
        response_key = f"{episode_id}:{int(tick)}:{seq}"

        body_pack = body_map.get(body_id)
        obj = obj_map.get(object_id)
        if body_pack is None or obj is None:
            continue
        body, body_cfg = body_pack

        ps = str(getattr(obj, "physical_state", ""))
        if ps == PHYSICAL_STATE_HELD:
            st.counters["skipped_held"] = int(st.counters.get("skipped_held", 0)) + 1
            receipts.append(_diag_receipt(
                tick, seq, response_key, meas, cfg,
                reason=REASON_HELD_SKIPPED, body=body, obj=obj, body_cfg=body_cfg, config=config,
            ))
            continue

        # Dedupe: same measurement reprocessed (processed key already present for this episode:tick)
        # Also track approach signature so resting PERSIST does not re-fire impulse.
        # Allow new impulse in same episode if v_rel_n becomes approaching again after non-approaching.
        pre_keys = [k for k in st.processed_keys if k.startswith(f"{episode_id}:{int(tick)}:")]
        # We'll decide ALREADY_PROCESSED only if we already applied an impulse for this exact
        # episode+tick+measurement identity (same seq path). Use approach signature instead.

        m_b = getattr(body_cfg, "mass", None)
        m_o = getattr(obj, "mass", None)
        if not _valid_mass(m_b) or not _valid_mass(m_o):
            st.counters["invalid_mass"] = int(st.counters.get("invalid_mass", 0)) + 1
            receipts.append(_diag_receipt(
                tick, seq, response_key, meas, cfg,
                reason=REASON_INVALID_MASS, body=body, obj=obj, body_cfg=body_cfg, config=config,
                mass_body=m_b, mass_object=m_o,
            ))
            st.processed_keys.add(response_key)
            continue
        mass_b = float(m_b)
        mass_o = float(m_o)

        # Swept: reconstruct poses at contact_fraction along start→end (toroidal), set WRAP poses,
        # apply impulse using current velocities; do NOT integrate remainder this tick.
        detection_mode = str(meas.get("detection_mode") or "")
        swept_pose_set = False
        if detection_mode == DETECTION_SWEPT:
            frac = meas.get("contact_fraction")
            b0 = meas.get("body_start_pose")
            b1 = meas.get("body_end_pose")
            o0 = meas.get("object_start_pose")
            o1 = meas.get("object_end_pose")
            if frac is not None and b0 and b1 and o0 and o1:
                t = float(frac)
                bx, by = _lerp_toroidal(float(b0[0]), float(b0[1]), float(b1[0]), float(b1[1]), t, width, height)
                ox, oy = _lerp_toroidal(float(o0[0]), float(o0[1]), float(o1[0]), float(o1[1]), t, width, height)
                body.x, body.y = bx, by
                obj.x, obj.y = ox, oy
                swept_pose_set = True
                any_position_changed = True
                st.counters["swept_pose_set"] = int(st.counters.get("swept_pose_set", 0)) + 1

        # Normal from body→object via measurement displacement (authoritative geometry)
        disp = meas.get("shortest_toroidal_displacement")
        if disp is None:
            from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
                shortest_toroidal_delta,
            )
            dx, dy = shortest_toroidal_delta(float(body.x), float(body.y), float(obj.x), float(obj.y), width, height)
        else:
            dx, dy = float(disp[0]), float(disp[1])
            # After swept pose set, recompute from current poses for consistency
            if swept_pose_set:
                from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
                    shortest_toroidal_delta,
                )
                dx, dy = shortest_toroidal_delta(float(body.x), float(body.y), float(obj.x), float(obj.y), width, height)
        nx, ny = contact_normal_from_displacement(dx, dy)

        # Pre-velocities at response time
        vbx0, vby0 = float(body.vx), float(body.vy)
        vox0, voy0 = float(getattr(obj, "vx", 0.0) or 0.0), float(getattr(obj, "vy", 0.0) or 0.0)
        v_rel_x = vox0 - vbx0
        v_rel_y = voy0 - vby0
        v_rel_n = v_rel_x * nx + v_rel_y * ny
        eps = float(cfg.approach_epsilon)

        approaching = v_rel_n < -eps
        separating = v_rel_n > eps
        resting = not approaching and not separating

        # Approach signature: allow re-fire after was non-approaching
        approach_sig = "APPROACHING" if approaching else ("SEPARATING" if separating else "RESTING")
        prev_sig = st.last_approach_signature.get(pair_key)
        # Dedupe resting/separating PERSIST: if same non-approach signature already handled this episode,
        # and we already processed an approaching→resting transition this tick for pair — skip re-fire.
        # Spec: impulse ONLY on approach; resting/separating → j=0. Track last_approach_signature
        # so resting PERSIST does not re-fire. Allow new impulse if becomes approaching again.
        already = False
        if response_key in st.processed_keys:
            already = True
        elif not approaching and prev_sig == approach_sig and prev_sig in ("RESTING", "SEPARATING"):
            # Still emit a zero-impulse receipt once per tick via processed check on episode:tick pattern
            tick_prefix = f"{episode_id}:{int(tick)}:"
            if any(k.startswith(tick_prefix) for k in st.processed_keys):
                already = True

        if already:
            st.counters["already_processed"] = int(st.counters.get("already_processed", 0)) + 1
            receipts.append(_diag_receipt(
                tick, seq, response_key, meas, cfg,
                reason=REASON_ALREADY_PROCESSED, body=body, obj=obj, body_cfg=body_cfg, config=config,
                normal=[nx, ny], v_rel_n=v_rel_n,
                mass_body=mass_b, mass_object=mass_o,
                pre_body=[vbx0, vby0], pre_obj=[vox0, voy0],
            ))
            continue

        compliance, compliance_note = object_compliance(obj, config)
        e = restitution_from_compliance(compliance, e_min=cfg.e_min, e_max=cfg.e_max)

        j = 0.0
        j_raw = 0.0
        clamped = False
        reason = REASON_RESTING
        impulse_applied = False
        if separating:
            reason = REASON_SEPARATING
            st.counters["separating"] = int(st.counters.get("separating", 0)) + 1
        elif resting:
            reason = REASON_RESTING
            st.counters["resting"] = int(st.counters.get("resting", 0)) + 1
        else:
            # Approaching: j = -(1+e)*v_rel_n / (1/m_b + 1/m_o)  with v_rel_n < 0 → j > 0
            inv_sum = (1.0 / mass_b) + (1.0 / mass_o)
            j_raw = -(1.0 + e) * v_rel_n / inv_sum
            j = float(j_raw)
            if j > float(cfg.max_contact_impulse):
                j = float(cfg.max_contact_impulse)
                clamped = True
            if abs(j) < float(cfg.impulse_threshold):
                reason = REASON_BELOW_THRESHOLD
                j = 0.0
                st.counters["below_threshold"] = int(st.counters.get("below_threshold", 0)) + 1
            else:
                reason = REASON_APPROACHING
                impulse_applied = True

        # Apply Δv: body gets - (j/m_b) * n ; object gets + (j/m_o) * n
        dv_bx = dv_by = dv_ox = dv_oy = 0.0
        if impulse_applied and j > 0.0:
            dv_bx = -(j / mass_b) * nx
            dv_by = -(j / mass_b) * ny
            dv_ox = +(j / mass_o) * nx
            dv_oy = +(j / mass_o) * ny
            body.vx = float(body.vx) + dv_bx
            body.vy = float(body.vy) + dv_by
            # Clamp body to ±v_max
            vmax = float(getattr(body_cfg, "v_max", 0.4) or 0.4)
            body.vx = float(max(-vmax, min(vmax, float(body.vx))))
            body.vy = float(max(-vmax, min(vmax, float(body.vy))))
            obj.vx = float(getattr(obj, "vx", 0.0) or 0.0) + dv_ox
            obj.vy = float(getattr(obj, "vy", 0.0) or 0.0) + dv_oy
            # Clamp object speed
            ovx, ovy, _ = _clamp_speed(float(obj.vx), float(obj.vy), max_obj_speed)
            obj.vx, obj.vy = ovx, ovy
            # FREE_STATIC / FREE_MOVING from rest threshold
            if math.hypot(float(obj.vx), float(obj.vy)) >= rest_thr:
                obj.physical_state = PHYSICAL_STATE_FREE_MOVING
            else:
                obj.physical_state = PHYSICAL_STATE_FREE_STATIC
                obj.vx, obj.vy = 0.0, 0.0
            _set_grace(body, 1)
            try:
                from mechanistic_mind.physical_system.free_resource_object_static_traction_threshold import (
                    set_object_impulse_grace as _fost_grace,
                    free_resource_object_static_traction_threshold_is_active as _fost_on,
                )
                # Harmless no-op attribute when FOST OFF; read only when twin active.
                _fost_grace(obj, 1)
            except Exception:
                pass
            st.counters["impulses_applied"] = int(st.counters.get("impulses_applied", 0)) + 1

        vbx1, vby1 = float(body.vx), float(body.vy)
        vox1, voy1 = float(getattr(obj, "vx", 0.0) or 0.0), float(getattr(obj, "vy", 0.0) or 0.0)

        # Position correction (endpoint penetration only; numerical constraint; no momentum change)
        corr_body = [0.0, 0.0]
        corr_obj = [0.0, 0.0]
        position_corrected = False
        penetration = float(meas.get("penetration") or 0.0)
        if (
            cfg.position_correction_enabled
            and detection_mode != DETECTION_SWEPT
            and penetration > float(cfg.penetration_slop)
        ):
            # Mass-weighted separation along normal; total correction = penetration - slop
            depth = penetration - float(cfg.penetration_slop)
            inv_sum = (1.0 / mass_b) + (1.0 / mass_o)
            # Move body opposite to n, object along n
            corr_mag = min(float(cfg.max_position_correction), depth)
            # Share by inverse mass
            share_b = (1.0 / mass_b) / inv_sum
            share_o = (1.0 / mass_o) / inv_sum
            cb = corr_mag * share_b
            co = corr_mag * share_o
            body.x = float(wrap_coord(float(body.x) - cb * nx, width))
            body.y = float(wrap_coord(float(body.y) - cb * ny, height))
            obj.x = float(wrap_coord(float(obj.x) + co * nx, width))
            obj.y = float(wrap_coord(float(obj.y) + co * ny, height))
            corr_body = [-cb * nx, -cb * ny]
            corr_obj = [co * nx, co * ny]
            position_corrected = True
            any_position_changed = True
            st.counters["position_corrections"] = int(st.counters.get("position_corrections", 0)) + 1

        # Local pairwise KE + momentum accounting (no fake world energy conservation)
        ke_pre = 0.5 * mass_b * (vbx0 * vbx0 + vby0 * vby0) + 0.5 * mass_o * (vox0 * vox0 + voy0 * voy0)
        ke_post = 0.5 * mass_b * (vbx1 * vbx1 + vby1 * vby1) + 0.5 * mass_o * (vox1 * vox1 + voy1 * voy1)
        mom_pre = [mass_b * vbx0 + mass_o * vox0, mass_b * vby0 + mass_o * voy0]
        mom_post = [mass_b * vbx1 + mass_o * vox1, mass_b * vby1 + mass_o * voy1]
        residual_n = ((vox1 - vbx1) * nx + (voy1 - vby1) * ny) if impulse_applied else v_rel_n

        receipt = {
            "receipt_kind": RECEIPT_KIND,
            "tick": int(tick),
            "response_key": response_key,
            "response_seq": int(seq),
            "episode_id": episode_id,
            "body_id": body_id,
            "object_id": object_id,
            "pair_key": pair_key,
            "contact_phase": meas.get("contact_phase"),
            "detection_mode": detection_mode,
            "normal": [float(nx), float(ny)],
            "normal_sign_convention": "body_toward_object",
            "v_rel_n": float(v_rel_n),
            "approach_epsilon": float(eps),
            "reason": reason,
            "approaching": bool(approaching),
            "impulse_scalar_j": float(j),
            "impulse_scalar_j_raw": float(j_raw),
            "impulse_clamped": bool(clamped),
            "max_contact_impulse": float(cfg.max_contact_impulse),
            "impulse_vector_on_body": [float(-(j) * nx) if impulse_applied else 0.0,
                                      float(-(j) * ny) if impulse_applied else 0.0],
            "impulse_vector_on_object": [float(j * nx) if impulse_applied else 0.0,
                                        float(j * ny) if impulse_applied else 0.0],
            "delta_v_body": [float(dv_bx), float(dv_by)],
            "delta_v_object": [float(dv_ox), float(dv_oy)],
            "velocity_body_pre": [vbx0, vby0],
            "velocity_body_post": [vbx1, vby1],
            "velocity_object_pre": [vox0, voy0],
            "velocity_object_post": [vox1, voy1],
            "mass_body": float(mass_b),
            "mass_object": float(mass_o),
            "compliance": float(compliance),
            "compliance_source": compliance_note,
            "restitution_e": float(e),
            "e_min": float(cfg.e_min),
            "e_max": float(cfg.e_max),
            "penetration": float(penetration),
            "penetration_slop": float(cfg.penetration_slop),
            "position_corrected": bool(position_corrected),
            "position_correction_body": corr_body,
            "position_correction_object": corr_obj,
            "position_correction_is_numerical_constraint": True,
            "swept_pose_set": bool(swept_pose_set),
            "contact_fraction": meas.get("contact_fraction"),
            "ke_pair_pre": float(ke_pre),
            "ke_pair_post": float(ke_post),
            "ke_pair_delta": float(ke_post - ke_pre),
            "dissipated_energy": float(max(0.0, ke_pre - ke_post)),
            "momentum_pair_pre": mom_pre,
            "momentum_pair_post": mom_post,
            "residual_v_rel_n": float(residual_n),
            "collision_response_applied": bool(impulse_applied or position_corrected or swept_pose_set),
            "impulse_transferred": bool(impulse_applied),
            "velocity_changed": bool(impulse_applied),
            "sound_emitted": False,
            "friction": False,
            "tangential_impulse": False,
            "object_physical_state_post": str(getattr(obj, "physical_state", "")),
            "grace_ticks_set": 1 if impulse_applied else 0,
            "agent_accessible": False,
            "researcher_only": True,
            "mechanism": MECHANISM_ID,
            "preset_mechanism": MECHANISM_ID,
            "contact_fact_episode_id": episode_id,
            "overlay_caption": (
                "MASS + COMPLIANCE NORMAL RESPONSE · NO FRICTION · NO SOUND"
            ),
        }
        receipts.append(receipt)
        st.processed_keys.add(response_key)
        st.last_approach_signature[pair_key] = approach_sig
        st.counters["responses"] = int(st.counters.get("responses", 0)) + 1
        st.history.append(receipt)

    lim = int(cfg.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    # Bound processed_keys growth: keep recent tick keys
    if len(st.processed_keys) > 4096:
        # Drop keys for older ticks
        keep = {k for k in st.processed_keys if f":{int(tick)}:" in k or f":{int(tick)-1}:" in k}
        st.processed_keys = keep if keep else set(list(st.processed_keys)[-512:])

    if any_position_changed:
        try:
            from mechanistic_mind.physical_system.spatial_contents import (
                multi_content_spatial_index_is_active,
                reconcile_contents,
            )
            if multi_content_spatial_index_is_active(config):
                body_refs = [(bid, b) for bid, b, _cfg in bodies]
                reconcile_contents(
                    world,
                    body_refs,
                    tick=int(tick),
                    reason="body_object_contact_impulse",
                    config=config,
                )
        except Exception:
            pass

    step = {
        "event": EVENT_STEP,
        "tick": int(tick),
        "mechanism": MECHANISM_ID,
        "responses": receipts,
        "response_count": len(receipts),
        "impulses_applied": sum(1 for r in receipts if r.get("impulse_transferred")),
        "position_corrections": sum(1 for r in receipts if r.get("position_corrected")),
        "sound_emitted": False,
        "friction": False,
        "agent_accessible": False,
        "researcher_only": True,
        "overlay_caption": "MASS + COMPLIANCE NORMAL RESPONSE · NO FRICTION · NO SOUND",
    }
    st.last_step = step
    world.last_body_object_contact_impulse_step = step
    # Alias used by impact-acoustics consumers (same object).
    world.last_body_object_impulse_step = step
    return step


def _diag_receipt(
    tick: int,
    seq: int,
    response_key: str,
    meas: dict[str, Any],
    cfg: BodyObjectContactImpulseConfig,
    *,
    reason: str,
    body: Any,
    obj: Any,
    body_cfg: Any,
    config: Any,
    normal: list[float] | None = None,
    v_rel_n: float | None = None,
    mass_body: Any = None,
    mass_object: Any = None,
    pre_body: list[float] | None = None,
    pre_obj: list[float] | None = None,
) -> dict[str, Any]:
    compliance, compliance_note = object_compliance(obj, config)
    e = restitution_from_compliance(compliance, e_min=cfg.e_min, e_max=cfg.e_max)
    return {
        "receipt_kind": RECEIPT_KIND,
        "tick": int(tick),
        "response_key": response_key,
        "response_seq": int(seq),
        "episode_id": meas.get("episode_id"),
        "body_id": meas.get("body_id"),
        "object_id": meas.get("object_id"),
        "pair_key": meas.get("pair_key"),
        "contact_phase": meas.get("contact_phase"),
        "detection_mode": meas.get("detection_mode"),
        "normal": normal,
        "v_rel_n": v_rel_n,
        "reason": reason,
        "approaching": False,
        "impulse_scalar_j": 0.0,
        "impulse_transferred": False,
        "collision_response_applied": False,
        "position_corrected": False,
        "velocity_changed": False,
        "sound_emitted": False,
        "friction": False,
        "mass_body": (float(mass_body) if _valid_mass(mass_body) else mass_body),
        "mass_object": (float(mass_object) if _valid_mass(mass_object) else mass_object),
        "compliance": float(compliance),
        "compliance_source": compliance_note,
        "restitution_e": float(e),
        "velocity_body_pre": pre_body or [float(getattr(body, "vx", 0.0)), float(getattr(body, "vy", 0.0))],
        "velocity_object_pre": pre_obj or [float(getattr(obj, "vx", 0.0) or 0.0), float(getattr(obj, "vy", 0.0) or 0.0)],
        "agent_accessible": False,
        "researcher_only": True,
        "mechanism": MECHANISM_ID,
        "preset_mechanism": MECHANISM_ID,
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    step = st.last_step or {}
    return {
        "mechanism": MECHANISM_ID,
        "last_step": {
            "tick": step.get("tick"),
            "response_count": step.get("response_count"),
            "impulses_applied": step.get("impulses_applied"),
            "position_corrections": step.get("position_corrections"),
        },
        "counters": dict(st.counters),
        "overlay_caption": "MASS + COMPLIANCE NORMAL RESPONSE · NO FRICTION · NO SOUND",
        "agent_accessible": False,
        "researcher_only": True,
        "friction": False,
        "sound_emitted": False,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    step = st.last_step or {}
    rows = []
    for r in list(step.get("responses") or [])[-8:]:
        rows.append({
            "body_id": r.get("body_id"),
            "object_id": r.get("object_id"),
            "normal": r.get("normal"),
            "impulse_vector_on_body": r.get("impulse_vector_on_body"),
            "impulse_vector_on_object": r.get("impulse_vector_on_object"),
            "velocity_body_pre": r.get("velocity_body_pre"),
            "velocity_body_post": r.get("velocity_body_post"),
            "velocity_object_pre": r.get("velocity_object_pre"),
            "velocity_object_post": r.get("velocity_object_post"),
            "position_correction_body": r.get("position_correction_body"),
            "position_correction_object": r.get("position_correction_object"),
            "mass_body": r.get("mass_body"),
            "mass_object": r.get("mass_object"),
            "restitution_e": r.get("restitution_e"),
            "compliance": r.get("compliance"),
            "residual_v_rel_n": r.get("residual_v_rel_n"),
            "reason": r.get("reason"),
            "impulse_scalar_j": r.get("impulse_scalar_j"),
        })
    return {
        "caption": "MASS + COMPLIANCE NORMAL RESPONSE\nNO FRICTION · NO SOUND",
        "responses": rows,
        "summary": researcher_summary(world),
    }
