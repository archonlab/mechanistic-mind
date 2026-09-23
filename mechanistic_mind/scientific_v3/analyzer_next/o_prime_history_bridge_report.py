
"""HISTORICAL SENSORIMOTOR SELECTION (O′ bridge) Analyzer section."""
from __future__ import annotations
from typing import Any

def format_o_prime_bridge_section(payload: dict[str, Any] | None) -> str:
    lines = ["HISTORICAL SENSORIMOTOR SELECTION", "=" * 34, ""]
    if not payload or payload.get("status") in {None, "NOT_RECORDED"}:
        lines += ["status: NOT_RECORDED", "see docs/O_PRIME_HISTORY_BRIDGE_REPORT.md", ""]
        return "\n".join(lines)
    lines.append(f"status: {payload.get('status')}")
    fun = payload.get("funnel") or {}
    lines.append("FUNNEL")
    for k, v in fun.items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    return "\n".join(lines)
