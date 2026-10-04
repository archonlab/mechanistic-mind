"""Analyzer section: HELD RESOURCE OBJECT / TERRAIN MECHANICAL TRANSMISSION."""
from __future__ import annotations

from typing import Any


SECTION_TITLE = "HELD RESOURCE OBJECT / TERRAIN MECHANICAL TRANSMISSION"


def summarize_held_resource_object_terrain_mechanical_transmission(
    events: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    transmissions = [
        e
        for e in rows
        if float(e.get("work_transmitted_to_terrain") or 0.0) > 1e-15
    ]
    work_used = sum(float(e.get("work_used") or 0.0) for e in rows)
    work_tx = sum(float(e.get("work_transmitted_to_terrain") or 0.0) for e in rows)
    residuals = [float(e.get("work_partition_residual") or 0.0) for e in rows]
    objects = sorted({str(e.get("object_id")) for e in rows if e.get("object_id")})
    coverage = "NOT_AVAILABLE"
    if rows:
        coverage = "FULL" if transmissions else "PARTIAL"
    flags_ok = all(
        (not e.get("setmr_routed"))
        and (not e.get("terrain_failure_coupling"))
        and (not e.get("wmt_invoked"))
        and (not e.get("material_failure"))
        and (not e.get("impulse_transferred"))
        and (not e.get("sound_emitted"))
        and (not e.get("automatic_release"))
        for e in rows
    ) if rows else True
    return {
        "section": SECTION_TITLE,
        "evidence_coverage": coverage,
        "event_count": len(rows),
        "transmission_events": len(transmissions),
        "work_used_sum": work_used,
        "work_transmitted_sum": work_tx,
        "max_abs_residual": max((abs(r) for r in residuals), default=0.0),
        "object_ids": objects[:64],
        "setmr_routed": False,
        "terrain_failure_coupling": False,
        "wmt_invoked": False,
        "response_flags_ok": flags_ok,
        "agent_accessible": False,
        "no_tool_inference": True,
        "researcher_only": True,
    }


def format_held_resource_object_terrain_mechanical_transmission_section(
    s: dict[str, Any],
) -> str:
    if not s:
        return f"{SECTION_TITLE}\n  (no receipts)"
    lines = [
        SECTION_TITLE,
        f"  evidence_coverage: {s.get('evidence_coverage')}",
        f"  events: {s.get('event_count')}  transmissions={s.get('transmission_events')}",
        f"  work_used_sum={s.get('work_used_sum')}  transmitted_sum={s.get('work_transmitted_sum')}",
        f"  max_abs_residual={s.get('max_abs_residual')}  objects={s.get('object_ids')}",
        f"  setmr_routed={s.get('setmr_routed')}  terrain_failure={s.get('terrain_failure_coupling')}",
        f"  wmt={s.get('wmt_invoked')}  flags_ok={s.get('response_flags_ok')}",
        "  agent_accessible: False",
    ]
    return "\n".join(lines)


def held_resource_object_terrain_mechanical_transmission_receipts_from_consequences(
    run_dir,
) -> list[dict[str, Any]]:
    from pathlib import Path
    import json

    root = Path(run_dir)
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("**/consequences*.jsonl")) + sorted(
        root.glob("**/events*.jsonl")
    ):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            kind = str(row.get("kind") or row.get("receipt_kind") or "")
            payload = (
                row.get("held_resource_object_terrain_mechanical_transmission")
                or row.get("receipt")
                or row
            )
            if not isinstance(payload, dict):
                continue
            if (
                kind == "held_resource_object_terrain_mechanical_transmission"
                or payload.get("receipt_kind")
                == "HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION"
                or payload.get("mechanism")
                == "held_resource_object_terrain_mechanical_transmission"
            ):
                out.append(dict(payload))
    return out
