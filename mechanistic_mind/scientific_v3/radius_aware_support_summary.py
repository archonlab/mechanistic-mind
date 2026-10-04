"""Analyzer section: RADIUS-AWARE SUPPORT POINTS (G2B Hybrid C⋆)."""
from __future__ import annotations

from typing import Any

from mechanistic_mind.physical_system.radius_aware_support_points import (
    ANALYZER_SECTION,
    BANNER,
    CLASS_AIRBORNE,
    CLASS_EDGE,
    CLASS_FULL,
    CLASS_LOSS,
    CLASS_PARTIAL,
    MECHANISM_ID,
    RECEIPT_KIND,
)


def summarize_radius_aware_support(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    anomalies: list[str] = []
    for e in rows:
        if e.get("optical_radius_used"):
            anomalies.append("optical_radius_used_as_support_R")
        if e.get("authoritative_support_z") is not None and e.get("h_centre") is not None:
            if abs(float(e["authoritative_support_z"]) - float(e["h_centre"])) > 1e-12:
                anomalies.append("centre_z_authority_broken")
        if e.get("NORMAL_PHYSICAL_EFFECTS_ACTIVE") is True:
            anomalies.append("normal_physical_effects_active")
        if e.get("landing_sound"):
            anomalies.append("landing_sound_spam")
        if e.get("high_ring_anomaly"):
            anomalies.append("high_ring_anomaly")
        if e.get("support_class") == CLASS_LOSS and e.get("grounded_after") is True:
            anomalies.append("grounded_while_loss")
    return {
        "mechanism": MECHANISM_ID,
        "section": ANALYZER_SECTION,
        "banner": BANNER,
        "n_receipts": len(rows),
        "full_support_steps": sum(1 for e in rows if e.get("support_class") == CLASS_FULL),
        "partial_support_steps": sum(1 for e in rows if e.get("support_class") == CLASS_PARTIAL),
        "edge_or_sparse_steps": sum(1 for e in rows if e.get("support_class") == CLASS_EDGE),
        "loss_of_support_steps": sum(1 for e in rows if e.get("support_class") == CLASS_LOSS),
        "airborne_steps": sum(1 for e in rows if e.get("support_class") == CLASS_AIRBORNE),
        "CENTRE_Z_AUTHORITY": True,
        "RING_CLASSIFICATION_ONLY": True,
        "ONE_PE_AUTHORITY": "SES_DDA",
        "NORMAL_PHYSICAL_EFFECTS_ACTIVE": False,
        "anomalies": anomalies,
        "researcher_only": True,
    }


def format_radius_aware_support_section(s: dict[str, Any]) -> str:
    lines = [
        f"## {ANALYZER_SECTION}",
        f"  banner: {BANNER}",
        f"  receipts: {s.get('n_receipts', 0)}",
        f"  FULL_SUPPORT: {s.get('full_support_steps', 0)}",
        f"  PARTIAL_SUPPORT: {s.get('partial_support_steps', 0)}",
        f"  EDGE_OR_SPARSE: {s.get('edge_or_sparse_steps', 0)}",
        f"  LOSS_OF_SUPPORT: {s.get('loss_of_support_steps', 0)}",
        f"  AIRBORNE: {s.get('airborne_steps', 0)}",
        f"  CENTRE_Z_AUTHORITY: YES",
        f"  RING_CLASSIFICATION_ONLY: YES",
        f"  ONE_PE_AUTHORITY: SES_DDA",
        f"  NORMAL_PHYSICAL_EFFECTS_ACTIVE: NO",
    ]
    anoms = s.get("anomalies") or []
    lines.append(f"  anomalies: {len(anoms)}")
    for a in anoms[:32]:
        lines.append(f"    - {a}")
    return "\n".join(lines)


def radius_aware_support_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    from pathlib import Path
    import json
    root = Path(run_dir)
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("**/*")):
        if path.suffix not in {".json", ".jsonl"}:
            continue
        try:
            text = path.read_text()
        except Exception:
            continue
        if RECEIPT_KIND not in text and MECHANISM_ID not in text:
            continue
        try:
            if path.suffix == ".jsonl":
                for line in text.splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if isinstance(row, dict) and (
                        row.get("receipt_kind") == RECEIPT_KIND or row.get("mechanism") == MECHANISM_ID
                    ):
                        out.append(row)
            else:
                data = json.loads(text)
                rows = data if isinstance(data, list) else [data]
                for row in rows:
                    if isinstance(row, dict) and (
                        row.get("receipt_kind") == RECEIPT_KIND or row.get("mechanism") == MECHANISM_ID
                    ):
                        out.append(row)
        except Exception:
            continue
    return out
