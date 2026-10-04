"""Analyzer section: CONTINUOUS SURFACE GEOMETRY."""
from __future__ import annotations

from typing import Any

from mechanistic_mind.physical_system.continuous_surface_geometry import (
    ANALYZER_SECTION,
    BANNER,
    MECHANISM_ID,
    RECEIPT_KIND,
)


def summarize_continuous_surface_geometry(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    heights = [float(e["height"]) for e in rows if e.get("height") is not None]
    normals_inactive = sum(1 for e in rows if e.get("normal_physical_effects_active") is False)
    flat = sum(1 for e in rows if e.get("flat_patch"))
    return {
        "mechanism": MECHANISM_ID,
        "section": ANALYZER_SECTION,
        "banner": BANNER,
        "n_receipts": len(rows),
        "n_flat_patch_samples": flat,
        "n_normal_inactive_stamped": normals_inactive,
        "height_min": min(heights) if heights else None,
        "height_max": max(heights) if heights else None,
        "height_physical_effects_active": True,
        "normal_physical_effects_active": False,
        "HIDDEN_SMOOTHING": "FORBIDDEN",
        "DENSE_HEIGHT_RASTER": "NO",
        "SES_DISCRETE_DDA": "KEPT_PHASE1",
        "volume_status": "INDETERMINATE_IF_UNKNOWN",
        "researcher_only": True,
    }


def format_continuous_surface_geometry_section(s: dict[str, Any]) -> str:
    return "\n".join([
        f"## {ANALYZER_SECTION}",
        f"  banner: {BANNER}",
        f"  receipts: {s.get('n_receipts', 0)}",
        f"  flat-patch samples: {s.get('n_flat_patch_samples', 0)}",
        f"  height range: {s.get('height_min')} .. {s.get('height_max')}",
        f"  height_physical_effects_active: YES",
        f"  normal_physical_effects_active: NO",
        f"  HIDDEN_SMOOTHING: FORBIDDEN",
        f"  DENSE_HEIGHT_RASTER: NO",
        f"  SES_DISCRETE_DDA: KEPT_PHASE1",
        f"  volume: {s.get('volume_status')}",
    ])


def continuous_surface_geometry_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
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
                if isinstance(data, dict) and (
                    data.get("receipt_kind") == RECEIPT_KIND or data.get("mechanism") == MECHANISM_ID
                ):
                    out.append(data)
                elif isinstance(data, list):
                    for row in data:
                        if isinstance(row, dict) and (
                            row.get("receipt_kind") == RECEIPT_KIND or row.get("mechanism") == MECHANISM_ID
                        ):
                            out.append(row)
        except Exception:
            continue
    return out
