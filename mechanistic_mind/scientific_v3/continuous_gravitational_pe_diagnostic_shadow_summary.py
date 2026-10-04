"""Analyzer section: CONTINUOUS GRAVITATIONAL PE SHADOW (DIAGNOSTIC).

Ingests researcher-only CONTINUOUS_GRAVITATIONAL_PE_SHADOW receipts from V3
capture consequences (event_refs kind ``continuous_gravitational_pe_diagnostic_shadow``).
Never describes candidate endpoint ΔU as physically active.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

EVENT_REF_KIND = "continuous_gravitational_pe_diagnostic_shadow"

COGNITION_FORBIDDEN_TOKENS = (
    "CONTINUOUS_GRAVITATIONAL_PE",
    "CONTINUOUS_GRAVITATIONAL_PE_SHADOW",
    "CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW",
    "candidate_endpoint_delta_u",
    "DELTA_U_CANDIDATE",
    "PE_AUTHORITY_CONTINUOUS_GRAVITY",
    "CONTINUOUS_SUPPORT_HEIGHT_ENDPOINT_DELTA_U",
    "CANDIDATE_ONLY",
    "CURRENT_SES_ONLY",
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


def _stat(vals: list[float]) -> dict[str, float | None]:
    if not vals:
        return {"min": None, "mean": None, "max": None, "sum": None}
    return {
        "min": float(min(vals)),
        "mean": float(sum(vals) / len(vals)),
        "max": float(max(vals)),
        "sum": float(sum(vals)),
    }


def summarize_continuous_gravitational_pe_diagnostic_shadow_events(
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = [r for r in history if isinstance(r, dict)]
    n = len(rows)
    statuses: dict[str, int] = {}
    cmps: dict[str, int] = {}
    entity_kinds: dict[str, int] = {}
    cand_vals: list[float] = []
    ses_vals: list[float] = []
    diffs: list[float] = []
    physics_anomalies = 0
    smooth = topological = microrelief = 0
    level_nz = 0
    eligible = blocked = 0
    for r in rows:
        st = str(r.get("status") or "UNKNOWN")
        statuses[st] = statuses.get(st, 0) + 1
        cmp = str(r.get("comparison_class") or "UNKNOWN")
        cmps[cmp] = cmps.get(cmp, 0) + 1
        ek = str(r.get("entity_kind") or "unknown")
        entity_kinds[ek] = entity_kinds.get(ek, 0) + 1
        if r.get("influenced_physics") or r.get("candidate_influenced_physics"):
            physics_anomalies += 1
        if st in ("ELIGIBLE_ENDPOINT_PE", "PARTIAL_DIAGNOSTIC_ENDPOINT_PE"):
            eligible += 1
        if st == "BLOCKED_NO_COMMIT":
            blocked += 1
        tc = str(r.get("transition_class") or "")
        if tc == "SMOOTH_PATCH_TRAVERSAL":
            smooth += 1
        elif tc == "MICRORELIEF_STEP":
            microrelief += 1
        elif tc in (
            "LEDGE_BLOCK",
            "SUPPORT_DROP_LOS",
            "OCCUPANT_SUPPORT_RISE",
            "GEOMETRY_AMBIGUOUS",
            "RADIUS_PARTIAL_CONTACT",
        ):
            topological += 1
        cu = r.get("candidate_endpoint_delta_u")
        if cu is not None and math.isfinite(float(cu)):
            cand_vals.append(float(cu))
        sd = r.get("current_ses_gravitational_delta")
        if sd is not None and math.isfinite(float(sd)):
            ses_vals.append(float(sd))
        diff = r.get("difference")
        if diff is not None and math.isfinite(float(diff)):
            diffs.append(float(diff))
        if (
            str(r.get("event_kind") or "") == "LEVEL"
            and cu is not None
            and abs(float(cu)) > 1e-12
        ):
            level_nz += 1

    return {
        "mechanism": "continuous_gravitational_pe_diagnostic_shadow",
        "mode": "DIAGNOSTIC_SHADOW",
        "current_pe_authority": "PE_AUTHORITY_SES_DDA",
        "candidate_pe_authority": "CONTINUOUS_SUPPORT_HEIGHT_ENDPOINT_DELTA_U",
        "influenced_physics": False,
        "continuous_pe_active": False,
        "endpoint_authority": "CONTINUOUS_SUPPORT_HEIGHT_ENDPOINT_DELTA_U",
        "queries": n,
        "eligible_displacements": eligible,
        "blocked_or_ineligible": blocked + int(statuses.get("SUPPORT_LOSS_INELIGIBLE", 0))
        + int(statuses.get("NOT_ELIGIBLE_EDGE_OR_SPARSE", 0))
        + int(statuses.get("NOT_ELIGIBLE_AIRBORNE", 0)),
        "smooth_count": smooth,
        "topological_count": topological,
        "microrelief_count": microrelief,
        "status_counts": statuses,
        "comparison_counts": cmps,
        "entity_kind_counts": entity_kinds,
        "zero_both": int(cmps.get("ZERO_BOTH", 0)),
        "match": int(cmps.get("MATCH", 0)),
        "current_ses_only": int(cmps.get("CURRENT_SES_ONLY", 0)),
        "candidate_only": int(cmps.get("CANDIDATE_ONLY", 0)),
        "different_magnitude": int(cmps.get("DIFFERENT_MAGNITUDE", 0)),
        "different_sign": int(cmps.get("DIFFERENT_SIGN", 0)),
        "candidate_delta_u": _stat(cand_vals),
        "current_ses_gravitational_delta": _stat(ses_vals),
        "candidate_minus_ses": _stat(diffs),
        "level_nonzero_candidate": level_nz,
        "physics_influence_anomalies": physics_anomalies,
        "possible_double_accounting_anomalies": 0,  # candidate is shadow-only
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_continuous_gravitational_pe_diagnostic_shadow_section(s: dict[str, Any]) -> str:
    if not s:
        return ""
    cu = s.get("candidate_delta_u") or {}
    ses = s.get("current_ses_gravitational_delta") or {}
    diff = s.get("candidate_minus_ses") or {}
    lines = [
        "CONTINUOUS GRAVITATIONAL PE SHADOW (DIAGNOSTIC)",
        "  mode=DIAGNOSTIC_SHADOW · authority=SES_DDA · candidate=ENDPOINT_ΔU · physics_effect=NONE",
        f"  queries={s.get('queries', 0)} · eligible={s.get('eligible_displacements', 0)} · "
        f"blocked/inelig={s.get('blocked_or_ineligible', 0)} · smooth={s.get('smooth_count', 0)} · "
        f"topo={s.get('topological_count', 0)} · micro={s.get('microrelief_count', 0)}",
        f"  ZERO_BOTH={s.get('zero_both', 0)} MATCH={s.get('match', 0)} "
        f"SES_ONLY={s.get('current_ses_only', 0)} CAND_ONLY={s.get('candidate_only', 0)} "
        f"DIFF_MAG={s.get('different_magnitude', 0)} DIFF_SIGN={s.get('different_sign', 0)}",
        f"  candidate ΔU min/mean/max/sum={cu.get('min')}/{cu.get('mean')}/{cu.get('max')}/{cu.get('sum')}",
        f"  SES Δ min/mean/max/sum={ses.get('min')}/{ses.get('mean')}/{ses.get('max')}/{ses.get('sum')}",
        f"  (cand−ses) min/mean/max={diff.get('min')}/{diff.get('mean')}/{diff.get('max')}",
        f"  LEVEL+nonzero_cand={s.get('level_nonzero_candidate', 0)} · "
        f"physics_anomalies={s.get('physics_influence_anomalies', 0)} · "
        f"double_charge_active=0",
        f"  entity_kinds={s.get('entity_kind_counts')}",
        f"  status_counts={s.get('status_counts')}",
    ]
    return "\n".join(lines)


def continuous_gravitational_pe_diagnostic_shadow_raw_receipts_from_consequences(
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


def continuous_gravitational_pe_diagnostic_shadow_receipts_from_consequences(
    run_dir: str | Path,
) -> list[dict[str, Any]]:
    return dedup_receipts(
        continuous_gravitational_pe_diagnostic_shadow_raw_receipts_from_consequences(run_dir)
    )


def summarize_continuous_gravitational_pe_diagnostic_shadow_run(run_dir: str | Path) -> dict[str, Any]:
    raw = continuous_gravitational_pe_diagnostic_shadow_raw_receipts_from_consequences(run_dir)
    return summarize_continuous_gravitational_pe_diagnostic_shadow_events(dedup_receipts(raw))


def summarize_continuous_gravitational_pe_diagnostic_shadow(world: Any) -> dict[str, Any] | None:
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import state_of

    st = state_of(world)
    if st is None:
        return None
    return summarize_continuous_gravitational_pe_diagnostic_shadow_events(list(st.history or []))
