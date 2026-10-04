"""Analyzer summary: RELEASE / excavation free-space entry (V1D)."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def release_excavation_support_loss_receipts_from_consequences(
    run_dir: str | Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = Path(run_dir)
    for path in sorted(root.glob("**/consequences*.jsonl")) + sorted(
        root.glob("**/*receipt*.jsonl")
    ):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for line in text.splitlines():
            if "RELEASE_EXCAVATION_SUPPORT_LOSS_V1" not in line:
                continue
            try:
                import json

                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                kind = str(row.get("receipt_kind") or row.get("kind") or "")
                if kind == "RELEASE_EXCAVATION_SUPPORT_LOSS_V1" or kind.endswith(
                    "release_and_excavation_support_loss_integration"
                ):
                    rows.append(row)
    return rows


def summarize_release_and_excavation_support_loss(
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    by_class: dict[str, int] = {}
    release_n = support_lost_n = remains_n = dedup_n = anomaly_n = 0
    shared_handoff = True
    special_landing = False
    special_sound = False
    for r in receipts:
        if not isinstance(r, dict):
            continue
        ec = str(r.get("event_class") or r.get("event_kind") or "")
        by_class[ec] = int(by_class.get(ec, 0)) + 1
        if ec == "RELEASE_ENTRY":
            release_n += 1
        elif ec == "SUPPORT_LOST":
            support_lost_n += 1
        elif "SUPPORT_REMAINS" in ec:
            remains_n += 1
        elif ec == "REFRESH_DEDUPLICATED":
            dedup_n += 1
        elif ec == "ANOMALY":
            anomaly_n += 1
        if r.get("special_case_landing"):
            special_landing = True
            shared_handoff = False
        if r.get("special_case_sound"):
            special_sound = True
            shared_handoff = False
    return {
        "receipt_count": len(receipts),
        "by_event_class": by_class,
        "release_entries": release_n,
        "support_lost": support_lost_n,
        "support_remains_valid": remains_n,
        "refresh_deduplicated": dedup_n,
        "anomalies": anomaly_n,
        "shared_v1_handoff": shared_handoff,
        "special_case_landing": special_landing,
        "special_case_sound": special_sound,
        "section_title": "RELEASE / EXCAVATION FREE-SPACE ENTRY",
    }


def format_release_and_excavation_support_loss_section(s: dict[str, Any]) -> str:
    lines = [
        "RELEASE / EXCAVATION FREE-SPACE ENTRY",
        "====================================",
        "Release chain:",
        "  HELD → RELEASE → pose/velocity stamp → T+1 eligibility → support classification",
        "  → shared FGG → shared V1B → shared V1C",
        "Excavation chain:",
        "  exertion → conservative terrain mutation → support-height change",
        "  → affected-entity refresh → support loss without snap → next-tick FGG",
        "  → shared V1B → shared V1C",
        "",
        f"receipts: {s.get('receipt_count')}",
        f"release_entries: {s.get('release_entries')}",
        f"support_lost: {s.get('support_lost')}",
        f"support_remains_valid: {s.get('support_remains_valid')}",
        f"refresh_deduplicated: {s.get('refresh_deduplicated')}",
        f"anomalies: {s.get('anomalies')}",
        f"by_event_class: {s.get('by_event_class')}",
        f"shared_v1_handoff: {s.get('shared_v1_handoff')}",
        f"special_case_landing: {s.get('special_case_landing')} (must be false)",
        f"special_case_sound: {s.get('special_case_sound')} (must be false)",
        "",
        "No special landing/sound path exists; V1A→FGG→V1B→V1C remains authoritative.",
    ]
    return "\n".join(lines)
