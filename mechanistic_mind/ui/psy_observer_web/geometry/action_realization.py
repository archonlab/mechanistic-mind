"""BETA2-GEO-03 — Observer-only Action Realization forensics.

Explains requested discrete action → realized displacement from recorded
runtime quantities. Does not alter physics or cognition.
"""
from __future__ import annotations

import math
from collections import deque
from copy import deepcopy
from typing import Any

from mechanistic_mind.physical_system.actions import action_direction
from mechanistic_mind.ui.psy_observer_web.geometry.metrics import (
    ALIGN_REVERSE,
    ALIGN_SUCCESS,
    EPS_DISP,
    action_alignment,
    action_direction_unit,
)

SCHEMA = "mm.action_realization_receipt.v1"
HISTORY_MAX = 64

# Progress threshold for ALIGNED_EFFECTIVE vs ALIGNED_WEAK (world units over 1 tick).
# Below this with high alignment → weak same-direction realization.
ALIGNED_EFFECTIVE_DISP = 0.08


def _vec2(v: Any) -> list[float] | None:
    if v is None:
        return None
    try:
        return [float(v[0]), float(v[1])]
    except (TypeError, IndexError, ValueError):
        return None


def _mag(v: list[float] | None) -> float | None:
    if v is None:
        return None
    return float(math.hypot(v[0], v[1]))


def _wrap_delta(x0: float, y0: float, x1: float, y1: float, w: int, h: int) -> tuple[float, float, float]:
    from mechanistic_mind.planet.topology import toroidal_delta_xy
    dx, dy = toroidal_delta_xy(x0, y0, x1, y1, int(w), int(h))
    return float(dx), float(dy), float(math.hypot(dx, dy))


def build_action_realization_receipt(
    rt: Any,
    *,
    agent_id: str = "agent_0",
    body_id: str | None = None,
    contact: dict[str, Any] | None = None,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    """Build one Observer-only receipt from post-tick runtime state.

    Passive: reads last_* ledgers / motion receipt. Does not mutate physics.
    """
    cfg = getattr(rt, "config", None)
    body = getattr(rt, "body", None)
    ledger = getattr(rt, "last_action_work_ledger", None) or {}
    alloc = getattr(rt, "last_work_allocation", None) or {}
    forces = getattr(rt, "last_force_contributions", None) or {}
    motion = getattr(rt, "last_motion_receipt", None) or {}
    orient = getattr(rt, "last_orientation_meta", None) or {}
    deform = getattr(rt, "last_deformation_meta", None) or {}

    action = str(getattr(rt, "last_selected_action", None) or ledger.get("selected_action") or "WAIT")
    tick = int(getattr(rt, "tick", 0) or motion.get("tick") or 0)

    before = (motion.get("before") or {}).get("body") or {}
    after = (motion.get("after") or {}).get("body") or {}
    if not before and body is not None:
        # Fallback: only post available
        before = {}
        after = {
            "x": float(body.x), "y": float(body.y),
            "vx": float(body.vx), "vy": float(body.vy),
        }

    w = int(width if width is not None else getattr(getattr(cfg, "planet", None), "width", 32) or 32)
    h = int(height if height is not None else getattr(getattr(cfg, "planet", None), "height", 32) or 32)

    x0 = float(before.get("x", after.get("x", 0.0)))
    y0 = float(before.get("y", after.get("y", 0.0)))
    x1 = float(after.get("x", x0))
    y1 = float(after.get("y", y0))
    dx, dy, dist = _wrap_delta(x0, y0, x1, y1, w, h)

    req_dir = action_direction_unit(action)
    align = action_alignment(action, dx, dy) if str(action).startswith("MOVE") else None

    dv_req = _vec2(ledger.get("action_dv_requested") or ledger.get("action_dv_requested_after_vmax"))
    dv_req_vmax = _vec2(ledger.get("action_dv_requested_after_vmax"))
    dv_real = _vec2(ledger.get("action_dv_realized"))
    imp_req = _vec2(ledger.get("action_impulse_requested"))
    imp_real = _vec2(ledger.get("action_impulse_realized"))

    work_req = ledger.get("action_work_requested")
    work_alloc = ledger.get("action_work_allocated")
    work_real = ledger.get("action_work_realized")
    work_frac = ledger.get("action_work_limit_fraction")
    work_limited = bool(ledger.get("work_limited"))
    work_unavail = bool(ledger.get("work_unavailable"))
    reservoir_before = ledger.get("mechanical_work_reservoir_before")
    reservoir_after = ledger.get("mechanical_work_reservoir_after")

    env_force = _vec2(forces.get("environmental_site") or orient.get("net_force"))
    action_dv_force_note = forces.get("discrete_action_quantity") or "DELTA_V_NOT_FORCE"
    action_contrib = _vec2(forces.get("discrete_action"))

    mass = float(getattr(getattr(cfg, "body", None), "mass", 1.0) or 1.0)
    drag = float(getattr(getattr(cfg, "body", None), "drag", 0.0) or 0.0)

    contact = contact or {}
    contact_active = bool(contact.get("contact") or contact.get("active"))
    contact_impulse = None
    if contact_active:
        # Soft contact stores Δv impulses, not force
        ia = contact.get("impulse_a")
        ib = contact.get("impulse_b")
        contact_impulse = {
            "impulse_a": _vec2(ia),
            "impulse_b": _vec2(ib),
            "quantity": "DELTA_V_NOT_FORCE",
            "provenance": "DIRECT",
        }

    deform_work_limited = bool(deform.get("work_limited")) if isinstance(deform, dict) else False
    deform_measure = None
    if isinstance(deform, dict) and deform.get("enabled"):
        deform_measure = {
            "enabled": True,
            "work_limited": deform_work_limited,
            "actuator_scale": deform.get("actuator_scale"),
            "provenance": "DIRECT",
        }

    # Effective progress along requested direction (DERIVED)
    forward = None
    if req_dir is not None and dist is not None:
        forward = float(dx * req_dir[0] + dy * req_dir[1])

    outcome, primary, secondary, attribution = classify_realization(
        action=action,
        alignment=align,
        distance=dist,
        work_limited=work_limited,
        work_fraction=float(work_frac) if work_frac is not None else None,
        work_unavailable=work_unavail,
        env_force=env_force,
        action_dv_realized=dv_real,
        contact_active=contact_active,
        contact_impulse=contact_impulse,
        deform_work_limited=deform_work_limited,
        mass=mass,
    )

    vx0 = float(before.get("vx", 0.0) or 0.0)
    vy0 = float(before.get("vy", 0.0) or 0.0)
    vx1 = float(after.get("vx", getattr(body, "vx", 0.0) or 0.0))
    vy1 = float(after.get("vy", getattr(body, "vy", 0.0) or 0.0))

    if body_id:
        bid = str(body_id)
    elif str(agent_id).startswith("agent_"):
        bid = f"body-{str(agent_id).replace('agent_', '')}"
    elif str(agent_id) == "undercover":
        bid = "body-2"
    else:
        # Never collapse undercover/experimenter labels onto body-0.
        from mechanistic_mind.ui.psy_observer_web.undercover_identity import is_undercover_agent_id
        bid = "body-2" if is_undercover_agent_id(str(agent_id)) else "body-0"

    return {
        "schema": SCHEMA,
        "tick": tick,
        "agent_id": agent_id,
        "body_id": bid,
        "requested_action": action,
        "requested_direction": list(req_dir) if req_dir else None,
        "pre_position": [x0, y0],
        "post_position": [x1, y1],
        "realized_delta": [dx, dy],
        "realized_distance": dist,
        "pre_velocity": [vx0, vy0],
        "post_velocity": [vx1, vy1],
        "delta_velocity": [vx1 - vx0, vy1 - vy0],
        "requested_impulse": imp_req,
        "requested_impulse_magnitude": _mag(imp_req),
        "realized_impulse": imp_real,
        "action_dv_requested": dv_req,
        "action_dv_requested_after_vmax": dv_req_vmax,
        "action_dv_realized": dv_real,
        "available_work_before": reservoir_before if reservoir_before is not None else alloc.get("available"),
        "work_requested": work_req,
        "work_allocated": work_alloc,
        "work_realized": work_real,
        "work_fraction": work_frac,
        "work_limited": work_limited,
        "work_unavailable": work_unavail,
        "reservoir_after": reservoir_after,
        "environmental_force": env_force,
        "environmental_force_provenance": "DIRECT" if env_force is not None else "NOT_AVAILABLE",
        "body_site_force": env_force,  # same measured mean site net_force
        "action_contribution": action_contrib,
        "action_contribution_quantity": action_dv_force_note,
        "deformation": deform_measure if deform_measure else {"status": "NOT_RECORDED"},
        "contact_active": contact_active,
        "contact_impulse": contact_impulse if contact_impulse else {
            "status": "NONE" if not contact_active else "NOT_SEPARATELY_ATTRIBUTABLE",
        },
        "drag": drag,
        "mass": mass,
        "action_alignment": align,
        "effective_progress": forward,
        "expected_free_progress": None,  # NOT_AVAILABLE — no valid free baseline without bypass
        "expected_free_progress_status": "NOT_AVAILABLE",
        "realization_ratio": work_frac,  # DIRECT: |dv_realized|/|dv_req| from ledger
        "outcome": outcome,
        "primary_constraint": primary,
        "secondary_constraints": secondary,
        "attribution": attribution,
        "honesty": {
            "observer_only": True,
            "not_cognition_input": True,
            "no_fabricated_forces": True,
            "expected_free_progress": "NOT_AVAILABLE",
        },
    }


def classify_realization(
    *,
    action: str,
    alignment: float | None,
    distance: float | None,
    work_limited: bool,
    work_fraction: float | None,
    work_unavailable: bool,
    env_force: list[float] | None,
    action_dv_realized: list[float] | None,
    contact_active: bool,
    contact_impulse: dict[str, Any] | None,
    deform_work_limited: bool,
    mass: float,
) -> tuple[str, str, list[str], dict[str, Any]]:
    """Return (outcome, primary_constraint, secondary, attribution_evidence)."""
    attribution: dict[str, Any] = {}
    secondary: list[str] = []

    if not str(action).startswith("MOVE"):
        return (
            "INSUFFICIENT_EVIDENCE" if action == "WAIT" else "INSUFFICIENT_EVIDENCE",
            "NONE",
            [],
            {"note": "Classification focused on MOVE:*; WAIT tracked separately."},
        )

    dist = float(distance or 0.0)
    align = alignment

    # Outcome from alignment + progress
    if align is None and dist < EPS_DISP:
        outcome = "ALIGNED_WEAK"  # near-zero MOVE
    elif align is None:
        outcome = "INSUFFICIENT_EVIDENCE"
    elif align <= ALIGN_REVERSE:
        outcome = "OPPOSED"
    elif align < ALIGN_SUCCESS:
        outcome = "DEFLECTED"
    elif dist >= ALIGNED_EFFECTIVE_DISP:
        outcome = "ALIGNED_EFFECTIVE"
    else:
        outcome = "ALIGNED_WEAK"

    # Contribution magnitudes for ranking (honest)
    env_mag = _mag(env_force) or 0.0
    env_accel = env_mag / max(1e-9, float(mass))
    act_mag = _mag(action_dv_realized) or 0.0

    contact_mag = 0.0
    if contact_active and contact_impulse:
        for k in ("impulse_a", "impulse_b"):
            m = _mag(contact_impulse.get(k))
            if m is not None:
                contact_mag = max(contact_mag, m)

    candidates: list[tuple[str, float, str]] = []
    # (name, score, provenance)

    if work_limited or work_unavailable or (work_fraction is not None and work_fraction < 0.85):
        # Stronger weight when fraction is low
        frac = 1.0 if work_fraction is None else float(work_fraction)
        score = (1.0 - frac) * 2.0 + (1.5 if work_limited or work_unavailable else 0.0)
        if score > 0.05:
            candidates.append(("WORK_LIMITED", score, "DIRECT"))
            attribution["work"] = {
                "work_limited": work_limited,
                "work_unavailable": work_unavailable,
                "work_fraction": work_fraction,
                "provenance": "DIRECT",
            }

    if contact_active and contact_mag > 1e-6:
        candidates.append(("CONTACT_CONSTRAINED", contact_mag * 3.0, "DIRECT"))
        attribution["contact"] = {
            "active": True,
            "impulse_mag": contact_mag,
            "provenance": "DIRECT",
        }
    elif contact_active:
        attribution["contact"] = {"active": True, "impulse_mag": 0.0, "provenance": "DIRECT"}
    else:
        attribution["contact"] = {"active": False, "note": "no contact → never CONTACT_CONSTRAINED"}

    if env_accel > 1e-6:
        # Environment vs action: if env accel comparable/larger than realized action Δv
        ratio = env_accel / max(act_mag, 1e-6)
        score = env_accel * (1.0 + min(2.0, ratio))
        if outcome in ("OPPOSED", "DEFLECTED") or (outcome == "ALIGNED_WEAK" and ratio > 0.5):
            candidates.append(("ENVIRONMENT_DOMINATED", score, "DIRECT"))
        attribution["environment"] = {
            "force_mag": env_mag,
            "accel_mag": env_accel,
            "vs_action_dv_ratio": ratio,
            "provenance": "DIRECT",
        }
    else:
        attribution["environment"] = {"force_mag": 0.0, "provenance": "DIRECT" if env_force is not None else "NOT_AVAILABLE"}

    if deform_work_limited:
        # Co-limited with action work → score high enough to appear as secondary
        candidates.append(("DEFORMATION_DOMINATED", 1.4 if (work_limited or work_unavailable) else 0.8, "DIRECT"))
        attribution["deformation"] = {"work_limited": True, "provenance": "DIRECT"}

    if not candidates:
        if outcome == "ALIGNED_EFFECTIVE":
            return outcome, "NONE", [], attribution
        return outcome, "INSUFFICIENT_EVIDENCE", [], {
            **attribution,
            "note": "No dominant measured constraint above threshold.",
        }

    candidates.sort(key=lambda t: t[1], reverse=True)
    primary = candidates[0][0]
    for name, score, _ in candidates[1:]:
        if score >= 0.35 * candidates[0][1]:
            secondary.append(name)

    if len(secondary) >= 1 and candidates[1][1] >= 0.6 * candidates[0][1]:
        # Close competitors → MIXED when outcome is weak/deflected
        if outcome in ("ALIGNED_WEAK", "DEFLECTED", "OPPOSED", "MIXED_CONSTRAINT"):
            if len(secondary) >= 1:
                outcome_final = outcome
                # Keep outcome; mark primary still top, but note mixed
                attribution["mixed"] = True
                if len([c for c in candidates if c[1] >= 0.6 * candidates[0][1]]) >= 2:
                    # Reclassify outcome to MIXED_CONSTRAINT only when multiple strong
                    if outcome != "OPPOSED":
                        outcome_final = "MIXED_CONSTRAINT"
                return outcome_final, primary, secondary, attribution

    return outcome, primary, secondary, attribution


def compact_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Bounded transport for LIVE frames."""
    return {
        "tick": receipt.get("tick"),
        "agent_id": receipt.get("agent_id"),
        "body_id": receipt.get("body_id"),
        "requested_action": receipt.get("requested_action"),
        "realized_delta": receipt.get("realized_delta"),
        "realized_distance": receipt.get("realized_distance"),
        "action_alignment": receipt.get("action_alignment"),
        "effective_progress": receipt.get("effective_progress"),
        "work_fraction": receipt.get("work_fraction"),
        "work_limited": receipt.get("work_limited"),
        "outcome": receipt.get("outcome"),
        "primary_constraint": receipt.get("primary_constraint"),
        "secondary_constraints": receipt.get("secondary_constraints") or [],
        "contact_active": receipt.get("contact_active"),
    }


def stuck_banner(receipt: dict[str, Any] | None) -> dict[str, Any] | None:
    """Compact YOU-CONTROL diagnostic — not a runtime STUCK flag."""
    if not receipt:
        return None
    act = receipt.get("requested_action") or "—"
    if not str(act).startswith("MOVE"):
        return None
    align = receipt.get("action_alignment")
    dist = receipt.get("realized_distance")
    primary = receipt.get("primary_constraint") or "—"
    outcome = receipt.get("outcome") or "—"
    align_pct = None if align is None else f"{100.0 * float(align):.0f}%"
    return {
        "line": f"{act} → {outcome}",
        "detail": (
            f"{align_pct or '—'} aligned · progress "
            f"{float(dist):.3f}" if dist is not None else "—"
        ),
        "limiting": primary if primary not in ("NONE", "INSUFFICIENT_EVIDENCE") else "—",
        "tick": receipt.get("tick"),
        "honesty": "Observer physical description only — not stuck/frustrated cognition.",
    }


class ActionRealizationAccumulator:
    """Bounded Observer-only receipt ring (O(agents) per tick)."""

    def __init__(self, maxlen: int = HISTORY_MAX) -> None:
        self._by_agent: dict[str, deque[dict[str, Any]]] = {}
        self._maxlen = int(maxlen)
        self.latest: dict[str, dict[str, Any]] = {}

    def observe(self, receipt: dict[str, Any]) -> None:
        aid = str(receipt.get("agent_id") or "agent_0")
        ring = self._by_agent.setdefault(aid, deque(maxlen=self._maxlen))
        # Dedupe same tick+action for hold-key spam: replace last if same tick
        if ring and int(ring[-1].get("tick") or -1) == int(receipt.get("tick") or -2):
            ring[-1] = receipt
        else:
            ring.append(receipt)
        self.latest[aid] = receipt

    def history(self, agent_id: str | None = None, limit: int = 48) -> list[dict[str, Any]]:
        if agent_id:
            return list(self._by_agent.get(agent_id, []))[-int(limit):]
        out: list[dict[str, Any]] = []
        for ring in self._by_agent.values():
            out.extend(ring)
        out.sort(key=lambda r: int(r.get("tick") or 0))
        return out[-int(limit):]

    def compact_live(self, *, history_limit: int = 16) -> dict[str, Any]:
        latest_c = {aid: compact_receipt(r) for aid, r in self.latest.items()}
        # Experimenter banner from experimenter body if present
        exp = None
        for aid, r in self.latest.items():
            if (
                "undercover" in str(aid)
                or "experimenter" in str(aid)
                or r.get("observer_undercover")
                or str(r.get("body_id") or "").startswith("body-") and r.get("agent_id") == "undercover"
            ):
                exp = stuck_banner(r)
                break
        recent = [compact_receipt(r) for r in self.history(limit=int(history_limit))]
        return {
            "status": "AVAILABLE",
            "latest_by_agent": latest_c,
            "recent": recent,
            "history_len": sum(len(v) for v in self._by_agent.values()),
            "experimenter_banner": exp,
            "honesty": {
                "observer_only": True,
                "not_cognition": True,
                "bounded": True,
            },
        }

    def reset(self) -> None:
        self._by_agent.clear()
        self.latest.clear()


def collect_from_runtime(
    runtime: Any,
    *,
    experimenter_slot: int | None = None,
) -> list[dict[str, Any]]:
    """Collect receipts for all slots after a scientific tick (incl. contact)."""
    slots = getattr(runtime, "slots", None)
    contact = getattr(runtime, "last_contact", None)
    contacts = getattr(runtime, "last_contacts", None) or []
    w = int(getattr(getattr(runtime, "config", None), "planet", runtime.config.planet).width)
    h = int(runtime.config.planet.height)
    out: list[dict[str, Any]] = []

    def _contact_for_slot(i: int) -> dict[str, Any] | None:
        for c in contacts:
            if not c:
                continue
            pair = c.get("pair")
            if pair and i in pair and c.get("contact"):
                return c
        if contact and contact.get("contact") and i in (0, 1):
            return contact
        return None

    if slots:
        from mechanistic_mind.ui.psy_observer_web.undercover_identity import slot_agent_body_ids
        for i, rt in enumerate(slots):
            aid, bid = slot_agent_body_ids(i, experimenter_slot=experimenter_slot)
            out.append(build_action_realization_receipt(
                rt,
                agent_id=aid,
                body_id=bid,
                contact=_contact_for_slot(i),
                width=w,
                height=h,
            ))
    else:
        out.append(build_action_realization_receipt(
            runtime, agent_id="agent_0", body_id="body-0", width=w, height=h,
        ))
    return out
