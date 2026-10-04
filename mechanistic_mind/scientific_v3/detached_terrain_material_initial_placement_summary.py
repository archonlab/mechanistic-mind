"""Analyzer Next · Detached terrain material initial placement summary."""
from __future__ import annotations

from typing import Any


def summarize_detached_terrain_material_initial_placement(
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    placed = 0
    rejected = 0
    last: dict[str, Any] | None = None
    for row in receipts:
        st = str(row.get("status") or "")
        if st == "PLACED" or row.get("accepted"):
            placed += 1
        elif "REJECT" in st.upper():
            rejected += 1
        last = row
    return {
        "receipt_count": len(receipts),
        "placed": placed,
        "rejected": rejected,
        "last": last,
        "researcher_only": True,
    }


def format_detached_terrain_material_initial_placement_section(s: dict[str, Any]) -> str:
    last = s.get("last") or {}
    lines = [
        "### Detached Terrain Material Initial Placement",
        f"- receipts: {s.get('receipt_count', 0)} · placed: {s.get('placed', 0)} · rejected: {s.get('rejected', 0)}",
        f"- last status: {last.get('status')}",
        f"- candidate_index: {last.get('candidate_index')}",
        f"- source_cell: {last.get('source_cell')}",
        f"- support_z: {last.get('support_z')} · z: {last.get('z')}",
        f"- dynamics_eligible_tick: {last.get('dynamics_eligible_tick')}",
        f"- placement_policy: {last.get('placement_policy')}",
    ]
    return "\n".join(lines)


def detached_terrain_material_initial_placement_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    from pathlib import Path
    import json

    root = Path(run_dir)
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("**/consequence*.json")) + sorted(root.glob("**/*receipt*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        rows = data if isinstance(data, list) else [data]
        for row in rows:
            if not isinstance(row, dict):
                continue
            payload = (
                row.get("detached_terrain_material_initial_placement")
                or row.get("placement")
                or row
            )
            if not isinstance(payload, dict):
                continue
            kind = str(payload.get("kind") or payload.get("receipt_kind") or "")
            if (
                kind == "detached_terrain_material_initial_placement"
                or payload.get("receipt_kind") == "DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT"
                or payload.get("mechanism") == "detached_terrain_material_initial_placement"
                or payload.get("placement_policy") == "DETACHED_TERRAIN_PLACEMENT_POST_MUTATION_SUPPORT_V1"
            ):
                out.append(dict(payload))
    return out
