"""Analyzer section: SES DECOMPOSITION CONTRACT (G2C1).

Ingests researcher-only G2C1 receipts from V3 capture consequences (event_refs of kind
``ses_decomposition_contract``), deduplicated by ``application_key``. Never emits receipts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVENT_REF_KIND = "ses_decomposition_contract"

# Tokens that must never appear in agent observations (cognition privacy).
COGNITION_FORBIDDEN_TOKENS = (
    "SES_DECOMPOSITION",
    "PE_AUTHORITY",
    "SES_DDA",
    "CONTINUOUS_GRAVITY",
    "SMOOTH_PATCH_TRAVERSAL",
    "MICRORELIEF_STEP",
    "LEDGE_BLOCK",
    "SUPPORT_DROP_LOS",
    "OCCUPANT_SUPPORT_RISE",
    "RADIUS_PARTIAL_CONTACT",
    "CLIFF_NZ_CUTOFF",
    "GEOMETRY_AMBIGUOUS",
    "SES_TOPOLOGY_VS_CONTINUOUS_PE_SPLIT",
    "classifier_version",
    "responsibility_stamps",
    "application_key",
    "mutation_provenance",
    "transition_source",
)


def _consistency_issue(r: dict[str, Any]) -> str | None:
    """Taxonomy must only LABEL the SES decision; flag label/decision contradictions."""
    cls = r.get("transition_class")
    acc = bool(r.get("accepted"))
    if cls == "LEDGE_BLOCK" and acc:
        return "ledge_block_but_accepted"
    if cls == "SMOOTH_PATCH_TRAVERSAL" and not acc:
        return "smooth_traversal_but_rejected"
    if cls == "OCCUPANT_SUPPORT_RISE" and acc:
        return "occupant_rise_but_mutation_accepted"
    if r.get("transition_source") == "PATH_GATE":
        if (r.get("ses_legacy_decision") == "ACCEPT") != acc:
            return "legacy_decision_mismatch"
        if not acc and r.get("pose_after") != r.get("pose_before"):
            return "rejected_but_pose_changed"
    if cls == "CLIFF_NZ_CUTOFF":
        return "reserved_class_emitted"
    return None


def summarize_ses_decomposition_contract_events(
    events: list[dict[str, Any]] | None,
    *,
    raw_events: list[dict[str, Any]] | None = None,
    observation_leaks: list[str] | None = None,
) -> dict[str, Any]:
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        ACTIVE_PE_AUTHORITIES_G2C1,
        ANALYZER_SECTION,
        BANNER,
        PROFILE_VERSION,
        RESPONSIBILITY_STAMPS,
        TRANSITION_TAXONOMY,
        detect_authority_anomalies,
    )

    rows = [e for e in (events or []) if isinstance(e, dict)]
    raw = [e for e in (raw_events if raw_events is not None else rows) if isinstance(e, dict)]
    card = detect_authority_anomalies(raw)
    anomalies: list[dict[str, Any]] = []
    for k in ("zero_authority", "more_than_one_authority", "non_active_authority",
              "conflicting_authority", "duplicate_application_key", "duplicate_transition_receipt"):
        for item in card.get(k) or []:
            anomalies.append({"type": k, "ref": item})
    authorities = sorted({str(r.get("pe_authority")) for r in rows if r.get("pe_authority")})
    if len(authorities) > 1:
        anomalies.append({"type": "mixed_pe_authority", "authorities": authorities})
    if rows and not authorities:
        anomalies.append({"type": "missing_authority"})
    for r in rows:
        key = r.get("application_key")
        if r.get("pe_authority") and r.get("pe_authority") not in ACTIVE_PE_AUTHORITIES_G2C1:
            anomalies.append({"type": "continuous_pe_active" if "CONTINUOUS" in str(r.get("pe_authority")) else "unknown_authority", "ref": key})
        for flag, name in (("continuous_pe_active", "continuous_pe_active"),
                           ("tangent_gravity_active", "tangent_gravity_active"),
                           ("normal_physical_effects_active", "normal_physics_active"),
                           ("radius_face_sweep_active", "radius_face_sweep_active"),
                           ("future_intended_authority_active", "continuous_pe_active")):
            if r.get(flag):
                anomalies.append({"type": name, "ref": key})
        issue = _consistency_issue(r)
        if issue:
            anomalies.append({"type": "taxonomy_changed_physics", "detail": issue, "ref": key})
        if r.get("agent_accessible"):
            anomalies.append({"type": "cognition_leakage", "detail": "agent_accessible_receipt", "ref": key})
    for tok in observation_leaks or []:
        anomalies.append({"type": "cognition_leakage", "detail": f"token_in_observations:{tok}"})

    # Restore continuity: per (entity, source) ticks strictly increasing in capture order.
    last_tick: dict[tuple, int] = {}
    replay: list[str] = []
    for r in raw:
        et = (r.get("entity_kind"), r.get("entity_id"), r.get("transition_source"))
        t = int(r.get("tick", -1))
        if et in last_tick and t <= last_tick[et]:
            replay.append(str(r.get("application_key")))
        last_tick[et] = max(t, last_tick.get(et, t))
    for k in replay:
        anomalies.append({"type": "replay_after_restore", "ref": k})

    by_class = {c: 0 for c in TRANSITION_TAXONOMY}
    for r in rows:
        c = str(r.get("transition_class"))
        by_class[c] = by_class.get(c, 0) + 1
    decisions: dict[str, int] = {}
    for r in rows:
        d = str(r.get("ses_legacy_decision"))
        decisions[d] = decisions.get(d, 0) + 1
    support: dict[str, int] = {}
    for r in rows:
        s = str(r.get("support_class"))
        support[s] = support.get(s, 0) + 1
    per_entity_tick: dict[tuple, int] = {}
    for r in rows:
        k = (r.get("tick"), r.get("entity_kind"), r.get("entity_id"), r.get("transition_source"))
        per_entity_tick[k] = per_entity_tick.get(k, 0) + 1
    dhs = [float(r.get("delta_h") or 0.0) for r in rows]
    debits = [float(r.get("work_debit") or 0.0) for r in rows]
    kin = [float(r.get("kinetic_paid") or 0.0) for r in rows]
    return {
        "mechanism": "ses_decomposition_contract",
        "section": ANALYZER_SECTION,
        "analyzer_section": ANALYZER_SECTION,
        "banner": BANNER,
        "profile_version": PROFILE_VERSION,
        "n_receipts": len(rows),
        "n_raw_receipts": len(raw),
        "ingestion_duplicates_dropped": len(raw) - len(rows),
        "taxonomy": by_class,
        "pe_authorities": authorities,
        "responsibility_stamps": dict(RESPONSIBILITY_STAMPS),
        "ses_decisions": decisions,
        "delta_h": {"min": min(dhs) if dhs else None, "max": max(dhs) if dhs else None},
        "work_debit_total": sum(debits),
        "kinetic_paid_total": sum(kin),
        "support_classes": support,
        "ambiguity": [
            {"key": r.get("application_key"), "reason": r.get("ambiguity_reason")}
            for r in rows if r.get("transition_class") == "GEOMETRY_AMBIGUOUS"
        ][:64],
        "ambiguous_count": by_class.get("GEOMETRY_AMBIGUOUS", 0),
        "mutation_provenance": {
            p: sum(1 for r in rows if r.get("mutation_provenance") == p)
            for p in ("OCCUPIED_SUPPORT_RISE", "GROUND_LOWERED")
        },
        "receipt_cardinality": {
            "max_per_entity_transition_tick": max(per_entity_tick.values()) if per_entity_tick else 0,
            "ONE_PE_AUTHORITY_PER_ENTITY_TRANSITION_TICK": (not per_entity_tick) or max(per_entity_tick.values()) == 1,
            "authority_anomaly_count": int(card.get("anomaly_count") or 0),
        },
        "restore_continuity": {"replayed_keys": replay, "continuous": not replay},
        "parent_child_mismatch": "NOT_EVALUATED_IN_SINGLE_RUN (see G2C1 equivalence harness)",
        "continuous_pe_active": False,
        "normal_physical_effects_active": False,
        "tangent_gravity_implemented": False,
        "radius_face_sweep_implemented": False,
        "anomalies": anomalies,
        "agent_accessible": False,
        "researcher_only": True,
    }


def format_ses_decomposition_contract_section(s: dict[str, Any]) -> str:
    card = s.get("receipt_cardinality") or {}
    lines = [
        f"## {s.get('analyzer_section') or 'SES DECOMPOSITION CONTRACT'}",
        f"  banner: {s.get('banner')}",
        f"  receipts: {s.get('n_receipts', 0)} (raw {s.get('n_raw_receipts', 0)}, "
        f"ingestion duplicates dropped {s.get('ingestion_duplicates_dropped', 0)})",
        f"  PE authority: {', '.join(s.get('pe_authorities') or ['NONE'])}",
        "  responsibility stamps: " + "; ".join(f"{k}={v}" for k, v in (s.get("responsibility_stamps") or {}).items()),
        "  taxonomy: " + ", ".join(f"{k}={v}" for k, v in (s.get("taxonomy") or {}).items()),
        "  SES decisions: " + ", ".join(f"{k}={v}" for k, v in (s.get("ses_decisions") or {}).items()),
        f"  delta_h range: {(s.get('delta_h') or {}).get('min')} .. {(s.get('delta_h') or {}).get('max')}",
        f"  work debit total: {s.get('work_debit_total')}; kinetic paid total: {s.get('kinetic_paid_total')}",
        "  support classes: " + ", ".join(f"{k}={v}" for k, v in (s.get("support_classes") or {}).items()),
        f"  ambiguous: {s.get('ambiguous_count', 0)}",
        "  mutation provenance: " + ", ".join(f"{k}={v}" for k, v in (s.get("mutation_provenance") or {}).items()),
        f"  ONE_PE_AUTHORITY_PER_ENTITY_TRANSITION_TICK: {'YES' if card.get('ONE_PE_AUTHORITY_PER_ENTITY_TRANSITION_TICK') else 'NO'}",
        f"  restore continuity: {'CONTINUOUS' if (s.get('restore_continuity') or {}).get('continuous') else 'REPLAY_DETECTED'}",
        "  CLIFF_NZ_CUTOFF: RESERVED / diagnostic-only (never emitted in G2C1)",
        "  continuous PE / normal physics / tangent gravity / radius-face sweep: OFF",
    ]
    anoms = s.get("anomalies") or []
    lines.append(f"  anomalies: {len(anoms)}")
    for a in anoms[:32]:
        lines.append(f"    - {a}")
    return "\n".join(lines)


def _iter_jsonl(path: Path):
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def ses_decomposition_contract_raw_receipts_from_consequences(run_dir: str | Path) -> list[dict[str, Any]]:
    """All G2C1 event_refs in capture order (one consequence file; the V3 name wins)."""
    root = Path(run_dir)
    out: list[dict[str, Any]] = []
    for name in ("scientific_consequences.jsonl", "consequences.jsonl"):
        path = root / name
        if not path.exists():
            continue
        for row in _iter_jsonl(path):
            for ref in row.get("event_refs") or []:
                if isinstance(ref, dict) and ref.get("kind") == EVENT_REF_KIND:
                    out.append({k: v for k, v in ref.items() if k != "kind"})
        break
    return out


def dedup_receipts(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in raw:
        key = str(r.get("application_key") or r.get("dedup_key") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(r)
    return out


def ses_decomposition_contract_receipts_from_consequences(run_dir: str | Path) -> list[dict[str, Any]]:
    return dedup_receipts(ses_decomposition_contract_raw_receipts_from_consequences(run_dir))


def observation_privacy_leaks(run_dir: str | Path) -> list[str]:
    path = Path(run_dir) / "scientific_observations.jsonl"
    if not path.exists():
        return []
    found: set[str] = set()
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                for tok in COGNITION_FORBIDDEN_TOKENS:
                    if tok in line:
                        found.add(tok)
    except OSError:
        return []
    return sorted(found)


def summarize_ses_decomposition_contract_run(run_dir: str | Path) -> dict[str, Any]:
    raw = ses_decomposition_contract_raw_receipts_from_consequences(run_dir)
    return summarize_ses_decomposition_contract_events(
        dedup_receipts(raw), raw_events=raw, observation_leaks=observation_privacy_leaks(run_dir),
    )


def summarize_ses_decomposition_contract(world: Any) -> dict[str, Any] | None:
    """Live-world researcher view (Observer); None when G2C1 is absent."""
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        researcher_summary,
        state_of,
    )

    summary = researcher_summary(world)
    if summary is None:
        return None
    st = state_of(world)
    history = list(st.history) if st else []
    out = summarize_ses_decomposition_contract_events(history)
    out["counters"] = summary.get("counters", {})
    out["pe_authority"] = summary.get("pe_authority")
    out["stage_alias"] = summary.get("stage_alias")
    out["physics_equivalence_version"] = summary.get("physics_equivalence_version")
    out["transitions"] = [
        {k: r.get(k) for k in ("tick", "entity_kind", "entity_id", "transition_class", "event_kind",
                                "delta_h", "accepted", "support_class", "pe_authority",
                                "ambiguity_reason", "application_key")}
        for r in history
    ]
    return out
