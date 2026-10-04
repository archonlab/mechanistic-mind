"""Researcher summary for BNLT MOVE breakaway locomotion repair."""
from __future__ import annotations

from typing import Any


def summarize_bnlt_move_breakaway_locomotion_repair(
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    classes: dict[str, int] = {}
    first_blocker = None
    for r in receipts:
        cls = str(r.get("classification") or "UNKNOWN")
        classes[cls] = int(classes.get(cls, 0)) + 1
        if first_blocker is None and cls in {
            "ACTIVE_DRIVE_BLOCKED_INSUFFICIENT",
            "STATIC_HOLD",
        }:
            first_blocker = {
                "classification": cls,
                "tick": r.get("tick"),
                "displacement_mag": r.get("displacement_mag"),
                "drive_accel": r.get("repair_drive_accel") or r.get("drive_accel"),
                "kinetic_a": r.get("kinetic_a"),
            }
    return {
        "receipt_count": len(receipts),
        "class_counts": classes,
        "first_causal_blocker": first_blocker,
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_bnlt_move_breakaway_locomotion_repair_section(s: dict[str, Any]) -> str:
    lines = [
        "## BNLT MOVE breakaway locomotion repair",
        f"receipts={s.get('receipt_count', 0)}",
        f"classes={s.get('class_counts')}",
    ]
    fb = s.get("first_causal_blocker")
    if fb:
        lines.append(f"first_blocker={fb}")
    return "\n".join(lines) + "\n"


def bnlt_move_breakaway_locomotion_repair_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    from pathlib import Path
    import json

    out: list[dict[str, Any]] = []
    p = Path(run_dir)
    for path in sorted(p.glob("**/consequences*.jsonl")):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            for ev in row.get("event_refs") or row.get("events") or []:
                if not isinstance(ev, dict):
                    continue
                kind = str(ev.get("kind") or "")
                if kind == "bnlt_move_breakaway_locomotion_repair" or ev.get(
                    "mechanism"
                ) == "bnlt_move_breakaway_locomotion_repair":
                    out.append(ev)
    return out
