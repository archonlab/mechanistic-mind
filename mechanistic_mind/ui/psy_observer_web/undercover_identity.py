"""Canonical Undercover / experimenter physical identity (Observer-only).

Invariant: one Undercover controller ↔ one physical body slot.
Controller objects are non-physical. Cognition never sees these ids.
"""
from __future__ import annotations

from typing import Any

UNDERCOVER_AGENT_ID = "undercover"
LEGACY_EXPERIMENTER_AGENT_IDS = frozenset({
    "experimenter-body-0",
    "experimenter",
    "EXPERIMENTER-BODY-0",
})


def undercover_body_id(slot_index: int) -> str:
    return f"body-{int(slot_index)}"


def slot_agent_body_ids(
    slot_index: int,
    *,
    experimenter_slot: int | None,
) -> tuple[str, str]:
    """Return (agent_id, body_id) for a physical slot."""
    i = int(slot_index)
    if experimenter_slot is not None and i == int(experimenter_slot):
        return UNDERCOVER_AGENT_ID, undercover_body_id(i)
    return f"agent_{i}", f"body-{i}"


def is_undercover_agent_id(agent_id: str | None) -> bool:
    aid = str(agent_id or "")
    return aid == UNDERCOVER_AGENT_ID or aid in LEGACY_EXPERIMENTER_AGENT_IDS or aid.startswith("experimenter")


def normalize_undercover_agent_id(agent_id: str | None) -> str:
    """Map legacy experimenter labels onto the canonical undercover agent id."""
    if is_undercover_agent_id(agent_id):
        return UNDERCOVER_AGENT_ID
    return str(agent_id or "agent_0")


def physical_body_inventory(runtime: Any) -> dict[str, Any]:
    """Developer/Observer diagnostic: every physical body exactly once."""
    slots = getattr(runtime, "slots", None)
    exp_slot = getattr(runtime, "experimenter_slot", None)
    bodies: list[dict[str, Any]] = []
    if not slots:
        body = getattr(runtime, "body", None)
        bodies.append({
            "slot": 0,
            "agent_id": "agent_0",
            "body_id": "body-0",
            "object_id": id(body) if body is not None else None,
            "cognition_attached": bool(getattr(getattr(runtime, "config", None), "cognition", None)
                                       and getattr(runtime.config.cognition, "cognition_enabled", False)),
            "experimenter_controlled": False,
            "x": float(getattr(body, "x", 0.0) or 0.0) if body else None,
            "y": float(getattr(body, "y", 0.0) or 0.0) if body else None,
        })
    else:
        for i, slot in enumerate(slots):
            aid, bid = slot_agent_body_ids(i, experimenter_slot=exp_slot)
            body = slot.body
            ras = getattr(body, "R_A_site", None)
            rbs = getattr(body, "R_B_site", None)
            try:
                ra = float(ras.sum()) if ras is not None else None
                rb = float(rbs.sum()) if rbs is not None else None
            except Exception:
                ra, rb = None, None
            bodies.append({
                "slot": i,
                "agent_id": aid,
                "body_id": bid,
                "object_id": id(body),
                "owner_controller": "EXPERIMENTER" if (
                    exp_slot is not None and i == int(exp_slot)
                ) else "AUTONOMOUS",
                "cognition_attached": bool(slot.config.cognition.cognition_enabled),
                "experimenter_controlled": bool(getattr(slot, "_experimenter_controlled", False))
                or (exp_slot is not None and i == int(exp_slot)),
                "x": float(body.x),
                "y": float(body.y),
                "theta": float(getattr(body, "theta", 0.0) or 0.0),
                "vx": float(body.vx),
                "vy": float(body.vy),
                "optical_response": float(getattr(slot.config.body, "optical_response", 0.65) or 0.65),
                "work": float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0),
                "resource_A": ra,
                "resource_B": rb,
                "agent_seed": int(slot.seed),
            })
    # Ownership invariant checks (identity-based, not coordinate equality)
    violations: list[str] = []
    exp_bodies = [b for b in bodies if b.get("experimenter_controlled")]
    if len(exp_bodies) > 1:
        violations.append("multiple_experimenter_controlled_bodies")
    obj_ids = [b["object_id"] for b in bodies if b.get("object_id") is not None]
    if len(obj_ids) != len(set(obj_ids)):
        violations.append("duplicate_physical_body_object_ids")
    agent_ids = [b["agent_id"] for b in bodies]
    if len(agent_ids) != len(set(agent_ids)):
        violations.append("duplicate_agent_ids")
    return {
        "n_physical_bodies": len(bodies),
        "experimenter_slot": exp_slot,
        "bodies": bodies,
        "violations": violations,
        "invariant_ok": not violations,
        "note": "Observer/developer only — not cognition input.",
    }


def detect_legacy_duplicate_undercover_ids(agent_ids: list[str]) -> dict[str, Any]:
    """Flag historical dual labels without rewriting telemetry."""
    aids = {str(a) for a in agent_ids}
    has_legacy = bool(aids & LEGACY_EXPERIMENTER_AGENT_IDS) or any(
        a.startswith("experimenter") for a in aids
    )
    has_slot_agent = any(a.startswith("agent_") and a not in ("agent_0", "agent_1") for a in aids)
    has_canon = UNDERCOVER_AGENT_ID in aids
    duplicate = has_legacy and (has_slot_agent or has_canon)
    return {
        "legacy_experimenter_label": has_legacy,
        "canonical_undercover": has_canon,
        "extra_agent_slot_label": has_slot_agent,
        "flag": "LEGACY_DUPLICATE_UNDERCOVER_REPRESENTATION" if duplicate else None,
        "readable": True,
    }
