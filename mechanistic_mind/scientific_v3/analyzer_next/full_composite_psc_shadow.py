"""Analyzer Next: REAL FULL-COMPOSITE PSC SHADOW (from wet artifacts; SHADOW / NON-CAUSAL)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ARTIFACT_DIR_NAME = "full_composite_psc_shadow"


def _load(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def aggregate_full_composite_psc_shadow(run_dir: Path | None = None, *, artifact_dir: Path | None = None) -> dict[str, Any]:
    """Load shadow replay artifacts. Prefer results/full_composite_psc_shadow/."""
    root = artifact_dir
    if root is None:
        # Prefer workspace results next to repo root
        candidates = []
        if run_dir is not None:
            candidates.append(Path(run_dir) / "results" / ARTIFACT_DIR_NAME)
            candidates.append(Path(run_dir) / ARTIFACT_DIR_NAME)
        candidates.append(Path("results") / ARTIFACT_DIR_NAME)
        root = next((p for p in candidates if p.is_dir()), Path("results") / ARTIFACT_DIR_NAME)
    summary = _load(root / "replay_summary.json") or {}
    funnel = _load(root / "funnel.json") or {}
    classes = _load(root / "classifications.json") or {}
    proxy = _load(root / "proxy_vs_real.json") or {}
    adaptive = _load(root / "adaptive_frontier.json") or []
    perf = _load(root / "performance.json") or {}
    exact = _load(root / "exact_match.json") or {}
    devel = _load(root / "developmental_windows.json") or {}
    no_vis = _load(root / "no_vision_subset.json") or {}
    return {
        "schema": "mm.analyzer.full_composite_psc_shadow.v1",
        "label": "SHADOW / NON-CAUSAL TO PRODUCTION RUN",
        "analysis_only": True,
        "artifact_dir": str(root),
        "available": bool(summary),
        "SHADOW_EXACT_MATCH": (exact.get("SHADOW_EXACT_MATCH") if exact else summary.get("SHADOW_EXACT_MATCH")),
        "eligible_competitions": funnel.get("PSC_COMPETITIONS"),
        "full_replay_coverage": funnel.get("FULL_COMPETE_SCENARIOS_REPLAYED"),
        "same_loco_same_composite": classes.get("SAME_LOCOMOTION_SAME_COMPOSITE"),
        "same_loco_different_composite": classes.get("SAME_LOCOMOTION_DIFFERENT_COMPOSITE"),
        "different_locomotion": classes.get("DIFFERENT_LOCOMOTION"),
        "insufficient_evidence": classes.get("INSUFFICIENT_COMPOSITE_EVIDENCE"),
        "different_locomotion_rate": summary.get("different_locomotion_rate"),
        "proxy_vs_real": {
            "agreement": proxy.get("agreement"),
            "precision": proxy.get("precision_proxy_for_real_diff_loco"),
            "recall": proxy.get("recall_proxy_for_real_diff_loco"),
            "confusion_matrix": proxy.get("confusion_matrix"),
        },
        "developmental_windows": devel,
        "no_vision_subset_n": (no_vis or {}).get("n"),
        "adaptive_frontier": adaptive,
        "performance": perf,
        "funnel": funnel,
        "note": "Real compete_scenarios semantics; production PSC unchanged.",
    }


def format_full_composite_psc_shadow(payload: dict[str, Any] | None) -> str:
    if not payload or not payload.get("available"):
        return "REAL FULL-COMPOSITE PSC SHADOW: NOT_RECORDED (no artifacts)"
    lines = [
        "REAL FULL-COMPOSITE PSC SHADOW  [SHADOW / NON-CAUSAL TO PRODUCTION RUN]",
        f"  EXACT_MATCH={payload.get('SHADOW_EXACT_MATCH')}",
        f"  eligible={payload.get('eligible_competitions')} replayed={payload.get('full_replay_coverage')}",
        f"  SAME_LOCO_SAME_COMPOSITE={payload.get('same_loco_same_composite')}",
        f"  SAME_LOCO_DIFFERENT_COMPOSITE={payload.get('same_loco_different_composite')}",
        f"  DIFFERENT_LOCOMOTION={payload.get('different_locomotion')} rate={payload.get('different_locomotion_rate')}",
        f"  insufficient={payload.get('insufficient_evidence')}",
        f"  proxy agreement={((payload.get('proxy_vs_real') or {}).get('agreement'))}",
        f"  no-vision n={payload.get('no_vision_subset_n')}",
    ]
    return "\n".join(lines)
