"""Acanthostega Beta 4 · Held COMBINE radius resize transaction V1.

Mechanism: held_combine_radius_resize_transaction
Preset: ACANTHOSTEGA_BETA4_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
Parent: ACANTHOSTEGA_BETA4_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
Profile: HELD_COMBINE_RADIUS_RESIZE_TRANSACTION_V1

Extends explicit held COMBINE with atomic geometry admission for
profile-stamped survivors: growth-only radius from combined quantity,
held base/feet anchor, m·g·Δr work debit, reject-entire-COMBINE on
conflict or insufficient work. No deposition shrink; no free-grounded resize.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
    PROFILE_VERSION as SIZE_GEOMETRY_PROFILE,
    derive_detached_material_collision_radius,
)
from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
    BODY_CONTACT_RADIUS,
    ensure_object_collision_radius,
    shortest_toroidal_delta,
)
from mechanistic_mind.physical_system.resource_objects import CANONICAL_COLLISION_RADIUS

MECHANISM_ID = "held_combine_radius_resize_transaction"
PROFILE_VERSION = "HELD_COMBINE_RADIUS_RESIZE_TRANSACTION_V1"
STATE_SCHEMA = "HELD_COMBINE_RADIUS_RESIZE_TRANSACTION_STATE_V1"
RECEIPT_KIND = "HELD_COMBINE_GEOMETRY_RESIZE"
ANCHOR_POLICY = "HELD_BASE_FEET_SNAP_RETAINED"

BANNER = (
    "HELD COMBINE RADIUS RESIZE TRANSACTION V1\n"
    "EXPLICIT COMBINE ONLY\n"
    "PROFILE-STAMPED SURVIVOR ONLY\n"
    "HELD BASE ANCHOR\n"
    "m·g·Δr WORK DEBIT\n"
    "ATOMIC GEOMETRY CONFLICT REJECT\n"
    "NO IMPACT SOUND\n"
    "NO DEPOSITION RESIZE"
)

RESEARCHER_FLAGS = {"researcher_only": True, "agent_accessible": False}

GEOMETRY_EPS = 1e-12
PENETRATION_EPS = 1e-9
OVERLAP_MARGIN = 0.95  # match DTIP / placement

CLS_FIXED = "SURVIVOR_FIXED_GEOMETRY_NO_RESIZE"
CLS_NO_CHANGE = "RESIZE_NO_CHANGE_CLAMPED_OR_EQUAL"
CLS_GROWTH_ADMITTED = "RESIZE_GROWTH_ADMITTED"
CLS_COMMITTED = "COMMITTED_RESIZE"
CLS_INSUFFICIENT_WORK = "REJECTED_INSUFFICIENT_RESIZE_WORK"
CLS_HOLDER_SELF = "REJECTED_HOLDER_SELF_OVERLAP_GROWTH"
CLS_TERRAIN = "REJECTED_TERRAIN_OVERLAP_GROWTH"
CLS_FOREIGN_BODY = "REJECTED_FOREIGN_BODY_OVERLAP_GROWTH"
CLS_OBJECT = "REJECTED_OBJECT_OVERLAP_GROWTH"
CLS_STALE = "REJECTED_STALE_RESIZE_PLAN"
CLS_UNEXPECTED_SHRINK = "REJECTED_UNEXPECTED_SHRINK"
CLS_INACTIVE = "RESIZE_MECHANISM_INACTIVE"

HISTORY_LIMIT_DEFAULT = 64


@dataclass
class HeldCombineRadiusResizeTransactionConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "anchor_policy": ANCHOR_POLICY,
            "size_geometry_profile_required": SIZE_GEOMETRY_PROFILE,
            "growth_only": True,
            "shrink_implemented": False,
            "deposition_resize": False,
            "resize_created_impact_sound": False,
            "overlap_margin": float(OVERLAP_MARGIN),
            "geometry_eps": float(GEOMETRY_EPS),
            "penetration_eps": float(PENETRATION_EPS),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None
    ) -> "HeldCombineRadiusResizeTransactionConfig":
        d = dict(data or {})
        return cls(
            enabled=bool(d.get("enabled", False)),
            history_limit=int(d.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: HeldCombineRadiusResizeTransactionConfig) -> None:
    if int(cfg.history_limit) < 1:
        raise ValueError("history_limit must be >= 1")


def _line_ok(config: Any) -> bool:
    return (
        config is not None
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    )


def held_combine_radius_resize_transaction_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "held_combine_radius_resize_transaction", None)
    return cfg is not None and bool(getattr(cfg, "enabled", False))


def set_held_combine_radius_resize_transaction(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "held_combine_radius_resize_transaction", None)
    if cur is None:
        if on:
            config.held_combine_radius_resize_transaction = (
                HeldCombineRadiusResizeTransactionConfig(enabled=True)
            )
        return
    if isinstance(cur, dict):
        cfg = HeldCombineRadiusResizeTransactionConfig.from_dict(cur)
        cfg.enabled = on
        config.held_combine_radius_resize_transaction = cfg
    else:
        cur.enabled = on


@dataclass
class HeldCombineRadiusResizeTransactionState:
    config: HeldCombineRadiusResizeTransactionConfig
    last_step: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(
        default_factory=lambda: {
            "plans": 0,
            "fixed_no_resize": 0,
            "no_change": 0,
            "growth_admitted": 0,
            "committed": 0,
            "rejected_work": 0,
            "rejected_conflict": 0,
            "rejected_shrink": 0,
            "rejected_stale": 0,
        }
    )


def state_of(world: Any) -> HeldCombineRadiusResizeTransactionState | None:
    raw = getattr(world, "held_combine_radius_resize_transaction_state", None)
    return raw if isinstance(raw, HeldCombineRadiusResizeTransactionState) else None


def ensure_held_combine_radius_resize_transaction_for_runtime(
    world: Any, config: Any
) -> HeldCombineRadiusResizeTransactionState | None:
    if not held_combine_radius_resize_transaction_is_active(config):
        if state_of(world) is not None:
            world.held_combine_radius_resize_transaction_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "held_combine_radius_resize_transaction", None)
    cfg = (
        HeldCombineRadiusResizeTransactionConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else HeldCombineRadiusResizeTransactionConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = HeldCombineRadiusResizeTransactionState(config=cfg)
    world.held_combine_radius_resize_transaction_state = st
    return st


def survivor_has_size_geometry_profile(obj: Any) -> bool:
    prov = getattr(obj, "provenance", None) or {}
    if not isinstance(prov, dict):
        return False
    return str(prov.get("size_geometry_profile") or "") == SIZE_GEOMETRY_PROFILE


def gravity_g(config: Any) -> float:
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        GRAVITY_ACCELERATION,
        flat_ground_gravity_is_active,
    )

    if flat_ground_gravity_is_active(config):
        cfg = getattr(config, "flat_ground_gravity", None)
        if cfg is not None:
            return float(getattr(cfg, "g", GRAVITY_ACCELERATION) or GRAVITY_ACCELERATION)
    return float(GRAVITY_ACCELERATION)


def available_mechanical_work(body: Any) -> float:
    if body is None:
        return 0.0
    return float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)


def debit_mechanical_work(body: Any, amount: float) -> float:
    """Debit exactly once; returns amount debited. No-op if amount<=0 or body None."""
    need = float(amount)
    if body is None or need <= 0.0 or not math.isfinite(need):
        return 0.0
    w0 = available_mechanical_work(body)
    debit = min(w0, need)
    body.mechanical_work_reservoir = max(0.0, w0 - debit)
    return float(debit)


def _world_dims(world: Any) -> tuple[int, int]:
    t = getattr(world, "T", None)
    if t is None:
        return 32, 32
    return int(t.shape[1]), int(t.shape[0])


def _xy_dist(ax: float, ay: float, bx: float, by: float, width: int, height: int) -> float:
    dx, dy = shortest_toroidal_delta(ax, ay, bx, by, width, height)
    return float(math.hypot(dx, dy))


def _penetration(dist: float, ra: float, rb: float) -> float:
    """Positive when disks overlap under OVERLAP_MARGIN (same family as DTIP)."""
    thresh = (float(ra) + float(rb)) * OVERLAP_MARGIN
    return float(max(0.0, thresh - float(dist)))


def _collect_bodies(world: Any, config: Any, holder_body_id: str) -> list[tuple[str, Any]]:
    refs = list(getattr(world, "detached_placement_body_refs", None) or [])
    out: list[tuple[str, Any]] = []
    seen: set[str] = set()
    for row in refs:
        if not isinstance(row, (tuple, list)) or len(row) < 2:
            continue
        bid, body = str(row[0]), row[1]
        if bid in seen or body is None:
            continue
        seen.add(bid)
        out.append((bid, body))
    # Ensure holder present if only on planet/runtime attrs
    if holder_body_id not in seen:
        for attr in ("body",):
            b = getattr(world, attr, None)
            if b is not None:
                out.append((str(holder_body_id), b))
                break
    return out


def _body_radius(config: Any) -> float:
    try:
        cfg = getattr(config, "physical_body_resource_object_contact", None)
        if cfg is not None:
            return float(getattr(cfg, "body_contact_radius", BODY_CONTACT_RADIUS) or BODY_CONTACT_RADIUS)
    except Exception:
        pass
    return float(BODY_CONTACT_RADIUS)


def admit_geometry_growth(
    *,
    world: Any,
    config: Any,
    survivor: Any,
    right_id: str,
    holder_body_id: str,
    r_before: float,
    r_proposed: float,
) -> dict[str, Any]:
    """Side-effect-free conflict admit: baseline vs proposed penetration."""
    width, height = _world_dims(world)
    sx = float(getattr(survivor, "x", 0.0) or 0.0)
    sy = float(getattr(survivor, "y", 0.0) or 0.0)
    sz = float(getattr(survivor, "z", 0.0) or 0.0)
    brad = _body_radius(config)
    blockers: list[dict[str, Any]] = []

    # Bodies (including holder) — baseline vs proposed
    for bid, body in _collect_bodies(world, config, holder_body_id):
        bx = float(getattr(body, "x", 0.0) or 0.0)
        by = float(getattr(body, "y", 0.0) or 0.0)
        dist = _xy_dist(sx, sy, bx, by, width, height)
        base_pen = _penetration(dist, r_before, brad)
        prop_pen = _penetration(dist, r_proposed, brad)
        if prop_pen > base_pen + PENETRATION_EPS:
            kind = "HOLDER" if str(bid) == str(holder_body_id) else "FOREIGN_BODY"
            blockers.append(
                {
                    "blocker_id": str(bid),
                    "blocker_type": kind,
                    "baseline_penetration": float(base_pen),
                    "proposed_penetration": float(prop_pen),
                    "distance": float(dist),
                }
            )
            return {
                "admitted": False,
                "classification": CLS_HOLDER_SELF if kind == "HOLDER" else CLS_FOREIGN_BODY,
                "blockers": blockers,
            }

    # ResourceObjects — exclude survivor and right source
    sid = str(getattr(survivor, "object_id", "") or "")
    for obj in list(getattr(world, "resource_objects", None) or []):
        oid = str(getattr(obj, "object_id", "") or "")
        if not oid or oid == sid or oid == str(right_id):
            continue
        ox = float(getattr(obj, "x", 0.0) or 0.0)
        oy = float(getattr(obj, "y", 0.0) or 0.0)
        orad = float(ensure_object_collision_radius(obj))
        dist = _xy_dist(sx, sy, ox, oy, width, height)
        base_pen = _penetration(dist, r_before, orad)
        prop_pen = _penetration(dist, r_proposed, orad)
        if prop_pen > base_pen + PENETRATION_EPS:
            blockers.append(
                {
                    "blocker_id": oid,
                    "blocker_type": "OBJECT",
                    "baseline_penetration": float(base_pen),
                    "proposed_penetration": float(prop_pen),
                    "distance": float(dist),
                }
            )
            return {
                "admitted": False,
                "classification": CLS_OBJECT,
                "blockers": blockers,
            }

    # Same-tick newborns (if any)
    for ex in list(getattr(world, "detached_placement_same_tick_newborns", None) or []):
        oid = str(ex.get("object_id") or "newborn")
        if oid == sid or oid == str(right_id):
            continue
        ox = float(ex.get("x") or 0.0)
        oy = float(ex.get("y") or 0.0)
        orad = float(ex.get("collision_radius") or CANONICAL_COLLISION_RADIUS)
        dist = _xy_dist(sx, sy, ox, oy, width, height)
        base_pen = _penetration(dist, r_before, orad)
        prop_pen = _penetration(dist, r_proposed, orad)
        if prop_pen > base_pen + PENETRATION_EPS:
            blockers.append(
                {
                    "blocker_id": oid,
                    "blocker_type": "NEWBORN",
                    "baseline_penetration": float(base_pen),
                    "proposed_penetration": float(prop_pen),
                }
            )
            return {
                "admitted": False,
                "classification": CLS_OBJECT,
                "blockers": blockers,
            }

    # Terrain: base/feet z unchanged; growth extends upward. Reject only if base already
    # below support more after growth is impossible — compare support vs base.
    try:
        from mechanistic_mind.physical_system.surface_elevation_support import (
            surface_elevation_support_is_active,
            surface_support_height,
        )

        if surface_elevation_support_is_active(config):
            support = float(surface_support_height(world, sx, sy, config=config))
            # Sphere occupies [z, z+2r]; penetrating terrain if z < support.
            # Growth does not lower z; only reject if already penetrating and growth
            # would worsen vertical interval into support (it cannot worsen base).
            # Still: if centre-based terrain contact deepens — use half-extent top.
            base_clearance = float(sz) - support
            if base_clearance < -PENETRATION_EPS:
                # Already below support; growth cannot fix; do not newly worsen base.
                pass
            # Top rises: no overhang model → no additional terrain reject on flat/SES.
    except Exception:
        pass

    return {"admitted": True, "classification": CLS_GROWTH_ADMITTED, "blockers": []}


def plan_held_combine_geometry_resize(
    *,
    world: Any,
    config: Any,
    left: Any,
    right: Any,
    body_id: str,
    actor_body: Any = None,
    quantity_after: float,
    mass_after: float,
) -> dict[str, Any]:
    """Pure admit for COMBINE geometry. Does not mutate world or work reservoir."""
    ensure_held_combine_radius_resize_transaction_for_runtime(world, config)
    st = state_of(world)
    if st is not None:
        st.counters["plans"] = int(st.counters.get("plans", 0)) + 1

    base: dict[str, Any] = {
        "receipt_kind": RECEIPT_KIND,
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "anchor_policy": ANCHOR_POLICY,
        "survivor_id": str(getattr(left, "object_id", "") or ""),
        "source_id": str(getattr(right, "object_id", "") or ""),
        "holder_body_id": str(body_id),
        "impact_sound_emitted": False,
        "impulse_emitted": False,
        "researcher_only": True,
        "agent_accessible": False,
    }

    if not held_combine_radius_resize_transaction_is_active(config):
        return {
            **base,
            "geometry_eligible": False,
            "resize_classification": CLS_INACTIVE,
            "resize_required": False,
            "admitted": True,
            "status": "SKIPPED",
        }

    if not survivor_has_size_geometry_profile(left):
        if st is not None:
            st.counters["fixed_no_resize"] = int(st.counters.get("fixed_no_resize", 0)) + 1
        return {
            **base,
            "geometry_eligible": False,
            "geometry_profile": None,
            "resize_classification": CLS_FIXED,
            "resize_required": False,
            "admitted": True,
            "status": "PLANNED",
            "radius_before": float(ensure_object_collision_radius(left)),
            "radius_proposed": float(ensure_object_collision_radius(left)),
        }

    r_before = float(ensure_object_collision_radius(left))
    vhe_before = float(
        getattr(left, "vertical_half_extent", None)
        if getattr(left, "vertical_half_extent", None) is not None
        else r_before
    )
    z_before = float(getattr(left, "z", 0.0) or 0.0)
    derivation = derive_detached_material_collision_radius(float(quantity_after))
    if not derivation.valid:
        return {
            **base,
            "geometry_eligible": True,
            "geometry_profile": SIZE_GEOMETRY_PROFILE,
            "resize_classification": CLS_UNEXPECTED_SHRINK,
            "resize_required": True,
            "admitted": False,
            "status": "REJECTED",
            "rejection_reason": CLS_UNEXPECTED_SHRINK,
        }
    r_raw = float(derivation.raw_radius)
    r_proposed = float(derivation.final_radius)

    payload = {
        **base,
        "geometry_eligible": True,
        "geometry_profile": SIZE_GEOMETRY_PROFILE,
        "quantity_after": float(quantity_after),
        "mass_after": float(mass_after),
        "radius_before": float(r_before),
        "radius_raw": float(r_raw),
        "radius_proposed": float(r_proposed),
        "vertical_extent_before": float(vhe_before),
        "vertical_extent_proposed": float(r_proposed),
        "base_z_before": float(z_before),
        "base_z_after": float(z_before),
        "centre_z_before": float(z_before) + float(r_before),
        "centre_z_after": float(z_before) + float(r_proposed),
        "delta_r": float(r_proposed - r_before),
        "clamp_status": derivation.clamp_status,
        "gravity": float(gravity_g(config)),
    }

    if r_proposed + GEOMETRY_EPS < r_before:
        if st is not None:
            st.counters["rejected_shrink"] = int(st.counters.get("rejected_shrink", 0)) + 1
        return {
            **payload,
            "resize_classification": CLS_UNEXPECTED_SHRINK,
            "resize_required": True,
            "admitted": False,
            "status": "REJECTED",
            "rejection_reason": CLS_UNEXPECTED_SHRINK,
        }

    if abs(r_proposed - r_before) <= GEOMETRY_EPS:
        if st is not None:
            st.counters["no_change"] = int(st.counters.get("no_change", 0)) + 1
        return {
            **payload,
            "resize_classification": CLS_NO_CHANGE,
            "resize_required": False,
            "admitted": True,
            "status": "PLANNED",
            "required_resize_work": 0.0,
            "available_resize_work": float(available_mechanical_work(actor_body)),
        }

    delta_r = float(r_proposed - r_before)
    g = float(gravity_g(config))
    required = float(max(0.0, float(mass_after) * g * delta_r))
    available = float(available_mechanical_work(actor_body))
    payload["required_resize_work"] = required
    payload["available_resize_work"] = available
    payload["resize_required"] = True

    if available + PENETRATION_EPS < required:
        if st is not None:
            st.counters["rejected_work"] = int(st.counters.get("rejected_work", 0)) + 1
        return {
            **payload,
            "resize_classification": CLS_INSUFFICIENT_WORK,
            "admitted": False,
            "status": "REJECTED",
            "rejection_reason": CLS_INSUFFICIENT_WORK,
        }

    conflict = admit_geometry_growth(
        world=world,
        config=config,
        survivor=left,
        right_id=str(getattr(right, "object_id", "") or ""),
        holder_body_id=str(body_id),
        r_before=r_before,
        r_proposed=r_proposed,
    )
    payload["conflict_summary"] = {
        "admitted": bool(conflict.get("admitted")),
        "blockers": list(conflict.get("blockers") or []),
    }
    if not conflict.get("admitted"):
        if st is not None:
            st.counters["rejected_conflict"] = int(st.counters.get("rejected_conflict", 0)) + 1
        return {
            **payload,
            "resize_classification": str(conflict.get("classification") or CLS_OBJECT),
            "admitted": False,
            "status": "REJECTED",
            "rejection_reason": str(conflict.get("classification") or CLS_OBJECT),
        }

    if st is not None:
        st.counters["growth_admitted"] = int(st.counters.get("growth_admitted", 0)) + 1
    return {
        **payload,
        "resize_classification": CLS_GROWTH_ADMITTED,
        "admitted": True,
        "status": "PLANNED",
    }


def validate_resize_commit_preconditions(
    *,
    world: Any,
    config: Any,
    survivor: Any,
    right: Any,
    actor_body: Any,
    geometry_plan: dict[str, Any],
    body_id: str,
) -> str | None:
    """Return rejection classification if commit must abort before any mutation; else None."""
    if not geometry_plan:
        return None
    if not geometry_plan.get("resize_required"):
        # Fixed / no-change / inactive: still verify survivor radius unchanged if eligible path stamped.
        return None
    if survivor is None or right is None:
        return CLS_STALE
    if str(getattr(survivor, "object_id", "") or "") != str(geometry_plan.get("survivor_id") or ""):
        return CLS_STALE
    if str(getattr(right, "object_id", "") or "") != str(geometry_plan.get("source_id") or ""):
        return CLS_STALE
    if not survivor_has_size_geometry_profile(survivor):
        return CLS_STALE
    r_now = float(ensure_object_collision_radius(survivor))
    if abs(r_now - float(geometry_plan.get("radius_before") or r_now)) > GEOMETRY_EPS:
        return CLS_STALE
    z_now = float(getattr(survivor, "z", 0.0) or 0.0)
    if abs(z_now - float(geometry_plan.get("base_z_before") or z_now)) > GEOMETRY_EPS:
        return CLS_STALE
    required = float(geometry_plan.get("required_resize_work") or 0.0)
    if available_mechanical_work(actor_body) + PENETRATION_EPS < required:
        return CLS_INSUFFICIENT_WORK
    r_proposed = float(geometry_plan.get("radius_proposed") or r_now)
    conflict = admit_geometry_growth(
        world=world,
        config=config,
        survivor=survivor,
        right_id=str(getattr(right, "object_id", "") or ""),
        holder_body_id=str(body_id),
        r_before=r_now,
        r_proposed=r_proposed,
    )
    if not conflict.get("admitted"):
        return str(conflict.get("classification") or CLS_OBJECT)
    return None


def apply_resize_on_commit(
    *,
    world: Any,
    config: Any,
    survivor: Any,
    actor_body: Any,
    geometry_plan: dict[str, Any],
) -> dict[str, Any]:
    """Apply radius/vhe and debit work. Called only after validate_resize_commit_preconditions."""
    st = ensure_held_combine_radius_resize_transaction_for_runtime(world, config)
    cls = str(geometry_plan.get("resize_classification") or "")
    if not geometry_plan.get("resize_required"):
        rec = {
            **geometry_plan,
            "committed": True,
            "work_debited": 0.0,
            "work_debit_count": 0,
            "result": cls,
            "impact_sound_emitted": False,
            "impulse_emitted": False,
        }
        _record(world, st, rec)
        return rec

    r_before = float(geometry_plan.get("radius_before") or ensure_object_collision_radius(survivor))
    r_after = float(geometry_plan.get("radius_proposed") or r_before)
    z = float(getattr(survivor, "z", 0.0) or 0.0)
    survivor.collision_radius = float(r_after)
    survivor.vertical_half_extent = float(r_after)
    survivor.z = float(z)  # base/feet retained

    required = float(geometry_plan.get("required_resize_work") or 0.0)
    debited = debit_mechanical_work(actor_body, required)
    prov = dict(getattr(survivor, "provenance", None) or {})
    prov["last_held_combine_geometry_resize"] = {
        "profile_version": PROFILE_VERSION,
        "radius_before": float(r_before),
        "radius_after": float(r_after),
        "delta_r": float(r_after) - float(r_before),
        "work_debited": float(debited),
        "transaction_id": geometry_plan.get("transaction_id"),
        "researcher_only": True,
    }
    survivor.provenance = prov

    rec = {
        **geometry_plan,
        "committed": True,
        "status": "COMMITTED",
        "resize_classification": CLS_COMMITTED,
        "radius_after": float(r_after),
        "vertical_extent_after": float(r_after),
        "base_z_after": float(z),
        "centre_z_after": float(z) + float(r_after),
        "work_debited": float(debited),
        "work_debit_count": 1 if debited > 0.0 else 0,
        "available_resize_work_after": available_mechanical_work(actor_body),
        "impact_sound_emitted": False,
        "impulse_emitted": False,
    }
    if st is not None:
        st.counters["committed"] = int(st.counters.get("committed", 0)) + 1
    _record(world, st, rec)
    return rec


def _record(world: Any, st: Any, rec: dict[str, Any]) -> None:
    world.last_held_combine_geometry_resize = dict(rec)
    if st is None:
        return
    st.last_step = dict(rec)
    st.history.append(dict(rec))
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]


def serialize_state(st: Any) -> dict[str, Any] | None:
    if not isinstance(st, HeldCombineRadiusResizeTransactionState):
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "last_step": dict(st.last_step) if st.last_step else {},
        "history": [dict(h) for h in st.history],
        "counters": {k: int(v) for k, v in st.counters.items()},
    }


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> Any:
    if not held_combine_radius_resize_transaction_is_active(config):
        world.held_combine_radius_resize_transaction_state = None
        return None
    if not isinstance(data, dict):
        return ensure_held_combine_radius_resize_transaction_for_runtime(world, config)
    cfg_raw = data.get("config")
    cfg = HeldCombineRadiusResizeTransactionConfig.from_dict(
        cfg_raw if isinstance(cfg_raw, dict) else None
    )
    cfg.enabled = True
    validate_config(cfg)
    st = HeldCombineRadiusResizeTransactionState(config=cfg)
    last = data.get("last_step") or {}
    if isinstance(last, dict):
        st.last_step = dict(last)
    hist = data.get("history") or []
    if isinstance(hist, list):
        st.history = [dict(h) for h in hist if isinstance(h, dict)]
    ctr = data.get("counters") or {}
    if isinstance(ctr, dict):
        for k in st.counters:
            if k in ctr:
                st.counters[k] = int(ctr[k])
    world.held_combine_radius_resize_transaction_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Held COMBINE radius resize transaction",
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "researcher_only": True,
        "agent_accessible": False,
        "arch_stage": "BETA4_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION",
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "anchor_policy": ANCHOR_POLICY,
        "counters": {k: int(v) for k, v in st.counters.items()},
        "last_step": dict(st.last_step) if st.last_step else {},
        "deposition_resize": False,
        "resize_created_impact_sound": False,
        **RESEARCHER_FLAGS,
    }
