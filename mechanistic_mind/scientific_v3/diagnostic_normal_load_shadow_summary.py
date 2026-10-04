"""Analyzer section: CONTINUOUS NORMAL-LOAD SHADOW (DIAGNOSTIC).

Ingests researcher-only CONTINUOUS_NORMAL_LOAD_SHADOW receipts from V3 capture
consequences (event_refs of kind ``diagnostic_normal_load_shadow``).
Never describes projected N as physically active.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

EVENT_REF_KIND = "diagnostic_normal_load_shadow"

COGNITION_FORBIDDEN_TOKENS = (
    "DIAGNOSTIC_NORMAL_LOAD_SHADOW",
    "CONTINUOUS_NORMAL_LOAD_SHADOW",
    "N_projected",
    "N_flat",
    "n_z",
    "CENTRE_ANALYTIC_CSG_N_HAT",
    "PROJECTED_NORMAL_LOAD",
)


def dedup_receipts(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in receipts:
        if not isinstance(r, dict):
            continue
        key = str(r.get("entity_key") or f"{r.get('entity_kind')}:{r.get('entity_id')}:{r.get('tick')}")
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def summarize_diagnostic_normal_load_shadow_events(
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = [r for r in history if isinstance(r, dict)]
    n = len(rows)
    statuses: dict[str, int] = {}
    entity_kinds: dict[str, int] = {}
    nz_vals: list[float] = []
    ratios: list[float] = []
    deltas: list[float] = []
    physics_anomalies = 0
    for r in rows:
        st = str(r.get("status") or "UNKNOWN")
        statuses[st] = statuses.get(st, 0) + 1
        ek = str(r.get("entity_kind") or "unknown")
        entity_kinds[ek] = entity_kinds.get(ek, 0) + 1
        if r.get("influenced_physics"):
            physics_anomalies += 1
        nz = r.get("n_z")
        if nz is not None and math.isfinite(float(nz)):
            nz_vals.append(float(nz))
        ratio = r.get("ratio")
        if ratio is not None and math.isfinite(float(ratio)):
            ratios.append(float(ratio))
        dN = r.get("delta_N")
        if dN is not None and math.isfinite(float(dN)):
            deltas.append(float(dN))

    def _stat(vals: list[float]) -> dict[str, float | None]:
        if not vals:
            return {"min": None, "mean": None, "max": None}
        return {
            "min": float(min(vals)),
            "mean": float(sum(vals) / len(vals)),
            "max": float(max(vals)),
        }

    return {
        "mechanism": "diagnostic_normal_load_shadow",
        "mode": "DIAGNOSTIC_SHADOW",
        "physical_authority": "FLAT_NORMAL_LOAD",
        "candidate_authority": "PROJECTED_NORMAL_LOAD",
        "influenced_physics": False,
        "normal_source": "CENTRE_ANALYTIC_CSG_N_HAT",
        "queries": n,
        "status_counts": statuses,
        "entity_kind_counts": entity_kinds,
        "full_or_flat_equivalent": int(
            statuses.get("PROJECTED", 0) + statuses.get("FLAT_EQUIVALENT", 0)
        ),
        "partial_diagnostic": int(statuses.get("PARTIAL_DIAGNOSTIC_NOT_ACTIVATABLE", 0)),
        "ineligible_edge_loss_airborne": int(
            statuses.get("NOT_ELIGIBLE_EDGE_OR_SPARSE", 0)
            + statuses.get("NOT_ELIGIBLE_SUPPORT_LOSS", 0)
            + statuses.get("NOT_ELIGIBLE_AIRBORNE", 0)
        ),
        "n_z": _stat(nz_vals),
        "ratio_N_proj_over_N_flat": _stat(ratios),
        "abs_delta_N_max": float(max((abs(d) for d in deltas), default=0.0)) if deltas else None,
        "physics_influence_anomalies": physics_anomalies,
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_diagnostic_normal_load_shadow_section(s: dict[str, Any]) -> str:
    if not s:
        return ""
    nz = s.get("n_z") or {}
    ratio = s.get("ratio_N_proj_over_N_flat") or {}
    lines = [
        "CONTINUOUS NORMAL-LOAD SHADOW (DIAGNOSTIC)",
        f"  mode=DIAGNOSTIC_SHADOW · physical_authority=FLAT · candidate=PROJECTED · physics_effect=NONE",
        f"  queries={s.get('queries', 0)} · full/flat={s.get('full_or_flat_equivalent', 0)} · "
        f"partial={s.get('partial_diagnostic', 0)} · ineligible={s.get('ineligible_edge_loss_airborne', 0)}",
        f"  n_z min/mean/max={nz.get('min')}/{nz.get('mean')}/{nz.get('max')}",
        f"  ratio min/mean/max={ratio.get('min')}/{ratio.get('mean')}/{ratio.get('max')}",
        f"  abs_delta_N_max={s.get('abs_delta_N_max')} · physics_anomalies={s.get('physics_influence_anomalies', 0)}",
        f"  entity_kinds={s.get('entity_kind_counts')}",
        f"  status_counts={s.get('status_counts')}",
    ]
    return "\n".join(lines)


def diagnostic_normal_load_shadow_raw_receipts_from_consequences(
    run_dir: str | Path,
) -> list[dict[str, Any]]:
    run_dir = Path(run_dir)
    out: list[dict[str, Any]] = []
    for path in sorted(run_dir.glob("**/consequences*.jsonl")):
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                for ref in row.get("event_refs") or []:
                    if isinstance(ref, dict) and ref.get("kind") == EVENT_REF_KIND:
                        out.append(ref)
    return out


def diagnostic_normal_load_shadow_receipts_from_consequences(
    run_dir: str | Path,
) -> list[dict[str, Any]]:
    return dedup_receipts(diagnostic_normal_load_shadow_raw_receipts_from_consequences(run_dir))


def summarize_diagnostic_normal_load_shadow_run(run_dir: str | Path) -> dict[str, Any]:
    raw = diagnostic_normal_load_shadow_raw_receipts_from_consequences(run_dir)
    return summarize_diagnostic_normal_load_shadow_events(dedup_receipts(raw))


def summarize_diagnostic_normal_load_shadow(world: Any) -> dict[str, Any] | None:
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import state_of

    st = state_of(world)
    if st is None:
        return None
    return summarize_diagnostic_normal_load_shadow_events(list(st.history or []))
