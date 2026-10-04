"""Researcher summary for detached material amount-scaled collision radius."""
from __future__ import annotations

from typing import Any


def summarize_detached_material_size_geometry(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    clamp_counts: dict[str, int] = {}
    timelines: list[dict[str, Any]] = []
    flags: list[str] = []
    for r in receipts:
        clamp = str(r.get("clamp_status") or "UNKNOWN")
        clamp_counts[clamp] = int(clamp_counts.get(clamp, 0)) + 1
        timelines.append(
            {
                "tick": r.get("creation_tick") or r.get("tick"),
                "object_id": r.get("object_id"),
                "transaction_id": r.get("transaction_id"),
                "quantity": r.get("quantity"),
                "raw_radius": r.get("raw_radius"),
                "final_radius": r.get("final_radius") or r.get("collision_radius"),
                "clamp_status": clamp,
                "vertical_half_extent": r.get("vertical_half_extent"),
                "optical_radius": r.get("optical_radius"),
                "committed": r.get("committed"),
            }
        )
        fr = r.get("final_radius")
        vhe = r.get("vertical_half_extent")
        if fr is not None and vhe is not None:
            try:
                if abs(float(fr) - float(vhe)) > 1e-9:
                    flags.append(f"vertical_extent_mismatch:{r.get('object_id')}")
            except (TypeError, ValueError):
                pass
        if r.get("size_mutable_after_creation") is True:
            flags.append(f"unexpected_mutable:{r.get('object_id')}")
    return {
        "receipt_count": len(receipts),
        "clamp_counts": clamp_counts,
        "timelines": timelines,
        "flags": flags,
        "causal_reconstruction": (
            "removed quantity → creation-time r=clamp(0.25×q^(1/3),0.08,0.25) → "
            "DTIP placement with derived radius → later contacts/support/manipulation; "
            "COMBINE/deposition amount-radius debt deferred (no resize in V1)"
        ),
        "optical_collision_divergence_documented": True,
        "combine_deposition_resize_debt": True,
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_detached_material_size_geometry_section(s: dict[str, Any]) -> str:
    lines = [
        "## Detached material amount-scaled collision radius",
        f"receipts={s.get('receipt_count', 0)}",
        f"clamps={s.get('clamp_counts')}",
        f"flags={s.get('flags')}",
        f"story={s.get('causal_reconstruction')}",
    ]
    return "\n".join(lines) + "\n"


def detached_material_size_geometry_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    from pathlib import Path
    import json

    out: list[dict[str, Any]] = []
    p = Path(run_dir)
    for path in sorted(p.glob("**/consequences*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        events = data.get("events") or data.get("event_refs") or []
        if not isinstance(events, list):
            continue
        for e in events:
            if not isinstance(e, dict):
                continue
            kind = str(e.get("kind") or e.get("receipt_kind") or "")
            if "DETACHED_MATERIAL_SIZE_GEOMETRY" in kind or kind == "detached_material_size_geometry":
                out.append(dict(e))
    return out
