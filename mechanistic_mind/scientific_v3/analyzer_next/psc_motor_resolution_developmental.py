"""Analyzer Next: PSC MOTOR RESOLUTION — DEVELOPMENTAL FORK."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path("results/psc_motor_resolution_developmental")


def _load(name: str):
    p = ROOT / name
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def aggregate_psc_motor_resolution_developmental(run_dir: Path | None = None) -> dict[str, Any]:
    pilot = _load("pilot_summary.json") or {}
    battery = _load("battery_summary.json") or {}
    identity = _load("fork_identity.json") or {}
    first = _load("first_divergence.json") or {}
    return {
        "schema": "mm.analyzer.psc_motor_resolution_developmental.v1",
        "label": "PSC MOTOR RESOLUTION — DEVELOPMENTAL FORK",
        "available": bool(pilot or battery),
        "A_FORK_IDENTITY": identity,
        "B_CONFIGURATION": {
            "phase_a": (pilot or battery).get("phase_a"),
            "branch_ticks": (pilot or battery).get("branch_ticks"),
            "modes": ["LOCO_FACTORIZED", "OBSERVED_COMPOSITE"],
        },
        "C_FIRST_DIVERGENCE": first,
        "D_NOTE": (
            "PRE-DIVERGENCE = same-state counterfactual from shared snapshot; "
            "POST-DIVERGENCE = trajectory comparison only"
        ),
        "L_PAIRED_SUMMARY": pilot or battery,
        "forensics_dir": str(ROOT / "forensics"),
    }


def format_psc_motor_resolution_developmental(payload: dict[str, Any] | None) -> str:
    if not payload or not payload.get("available"):
        return "PSC MOTOR RESOLUTION DEVELOPMENTAL FORK: NOT_RECORDED"
    s = payload.get("L_PAIRED_SUMMARY") or {}
    lines = [
        "PSC MOTOR RESOLUTION — DEVELOPMENTAL FORK",
        f"  pairs={s.get('pairs')} diverged={s.get('diverged')} no_div={s.get('no_divergence')}",
        f"  phase_a={s.get('phase_a')} branch={s.get('branch_ticks')}",
        f"  note: {payload.get('D_NOTE')}",
    ]
    return "\n".join(lines)
