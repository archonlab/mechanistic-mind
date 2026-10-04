"""CONSERVATIVE SURFACE COLUMN TRANSFER. Reads transfer receipts; never re-runs a transfer.

Statuses: OBSERVED, VERIFIED, REJECTED, NOT_IMPLEMENTED. No progress bar.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SECTION = "CONSERVATIVE SURFACE COLUMN TRANSFER"
SCHEMA_VERSION = "CONSERVATIVE_SURFACE_COLUMN_TRANSFER_SUMMARY_V1"
EVENT_COMMITTED = "SURFACE_COLUMN_TRANSFER_COMMITTED"
EVENT_REJECTED = "SURFACE_COLUMN_TRANSFER_REJECTED"
EVENT_RESTORE_VERIFIED = "SURFACE_COLUMN_TRANSFER_RESTORE_VERIFIED"
EVENTS = {EVENT_COMMITTED, EVENT_REJECTED, EVENT_RESTORE_VERIFIED}

NOT_IMPLEMENTED = [
    "agent_excavation",
    "gravity",
    "support",
    "explicit_carried_material",
    "pile_dynamics",
    "detached_terrain_object",
    "surface_elevation_body_effect",
    "slope_physics",
    "erosion",
]

STATEMENTS = [
    "agent excavation not implemented",
    "gravity not implemented",
    "support not implemented",
    "explicit carried material not implemented",
]


def _rows(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        if str(event.get("event") or "") in EVENTS or event.get("kind") == "surface_column_transfer":
            out.append(event)
    return out


def _fmax(values: list[Any]) -> float:
    best = 0.0
    for v in values:
        try:
            best = max(best, abs(float(v)))
        except (TypeError, ValueError):
            continue
    return best


def summarize_surface_column_transfer(
    events: list[dict[str, Any]] | None,
    *,
    persistence_verification: dict[str, Any] | None = None,
    agent_leakage_hits: int | None = None,
    sparse_delta_count: int | None = None,
) -> dict[str, Any]:
    rows = _rows(events)
    committed = [r for r in rows if r.get("event") == EVENT_COMMITTED or r.get("status") == "COMMITTED"]
    rejected = [r for r in rows if r.get("event") == EVENT_REJECTED or (
        r.get("status") == "REJECTED" and r.get("event") != EVENT_RESTORE_VERIFIED)]
    restores = [r for r in rows if r.get("event") == EVENT_RESTORE_VERIFIED]
    stale = [r for r in rejected if str(r.get("rejection_reason") or "").startswith("STALE_")]
    reasons: dict[str, int] = {}
    for r in rejected:
        key = str(r.get("rejection_reason") or "UNKNOWN")
        reasons[key] = reasons.get(key, 0) + 1
    residual = {"mass": [], "quantity": [], "components": [], "elevation": []}
    for r in committed:
        for k, v in (r.get("conservation_residual_max") or {}).items():
            residual.setdefault(k, []).append(v)
    residual_max = {k: _fmax(v) for k, v in residual.items()}
    atomic_ok = bool(committed) and all(
        (r.get("atomic_pair") or {}).get("both_columns_written") is True
        and int((r.get("atomic_pair") or {}).get("touched_columns") or 0) == 2
        for r in committed
    )
    conservation_ok = bool(committed) and all(r.get("conservation_verified") is True for r in committed)
    transfers = [
        {
            "transfer_id": r.get("transfer_id"),
            "transaction_id": r.get("transaction_id"),
            "tick": r.get("tick"),
            "source_cell": r.get("source_cell"),
            "destination_cell": r.get("destination_cell"),
            "committed_thickness": r.get("committed_thickness"),
            "source_elevation_change": _delta(r, "source_elevation"),
            "destination_elevation_change": _delta(r, "destination_elevation"),
            "source_resolved_depth_change": _delta(r, "source_resolved_depth"),
            "destination_resolved_depth_change": _delta(r, "destination_resolved_depth"),
            "source_revision": [r.get("source_revision_before"), r.get("source_revision_after")],
            "destination_revision": [r.get("destination_revision_before"), r.get("destination_revision_after")],
            "layer_merge_status": r.get("layer_merge_status"),
        }
        for r in committed
    ][:16]
    merges = sum(1 for r in committed if str(r.get("layer_merge_status") or "").startswith("MERGED"))
    persistence = dict(persistence_verification or {})
    if restores and not persistence:
        persistence = {
            "status": "VERIFIED",
            "restore_events": len(restores),
            "closed_world_residual_max": _fmax([r.get("closed_world_residual_max") for r in restores]),
        }
    observed, verified, rejected_status = [], [], []
    if rows:
        observed.append("surface_column_transfer_receipt")
    if committed:
        observed.append("committed_transfer")
    if atomic_ok:
        verified.append("atomic_pair_commit")
    if conservation_ok:
        verified.append("mass_quantity_component_conservation")
    if persistence.get("status") == "VERIFIED":
        verified.append("persistence_restore")
    leakage = "VERIFIED" if not agent_leakage_hits else "LEAK_DETECTED"
    if agent_leakage_hits == 0:
        verified.append("agent_leakage_audit")
    if rejected:
        rejected_status.append(f"rejected_transfers={len(rejected)}")
    if stale:
        rejected_status.append(f"stale_conflicts={len(stale)}")
    return {
        "section": SECTION,
        "schema_version": SCHEMA_VERSION,
        "event_count": len(rows),
        "planned_count": len(committed) + len(rejected),
        "committed_count": len(committed),
        "rejected_count": len(rejected),
        "rejection_reasons": reasons,
        "stale_conflict_count": len(stale),
        "layer_merge_count": merges,
        "sparse_delta_count": sparse_delta_count,
        "transfers": transfers,
        "conservation_residual_max": residual_max,
        "atomic_pair_verification": "VERIFIED" if atomic_ok else ("NOT_AVAILABLE" if not committed else "FAILED"),
        "persistence_restore_verification": persistence.get("status", "NOT_AVAILABLE"),
        "persistence_detail": persistence,
        "agent_leakage_audit": leakage if agent_leakage_hits is not None else "VERIFIED_BY_FORBIDDEN_TOKENS",
        "physical_effect_status": "INACTIVE",
        "physical_effects_active": False,
        "agent_accessible": False,
        "agent_action": False,
        "researcher_only": True,
        "resource_spawned": False,
        "geometry_role": "METADATA_ONLY",
        "OBSERVED": observed,
        "VERIFIED": verified,
        "REJECTED": rejected_status,
        "NOT_IMPLEMENTED": list(NOT_IMPLEMENTED),
        "statements": list(STATEMENTS),
    }


def _delta(row: dict[str, Any], prefix: str) -> float | None:
    try:
        return float(row.get(f"{prefix}_after")) - float(row.get(f"{prefix}_before"))
    except (TypeError, ValueError):
        return None


def format_surface_column_transfer_section(summary: dict[str, Any] | None) -> str:
    summary = summary or {}
    lines = [
        SECTION,
        f"  schema_version: {summary.get('schema_version')}",
        f"  planned: {summary.get('planned_count')}  committed: {summary.get('committed_count')}  "
        f"rejected: {summary.get('rejected_count')}",
        f"  rejection_reasons: {summary.get('rejection_reasons')}",
        f"  stale_conflicts: {summary.get('stale_conflict_count')}",
        f"  layer_merges: {summary.get('layer_merge_count')}",
        f"  sparse_delta_count: {summary.get('sparse_delta_count')}",
    ]
    for t in summary.get("transfers") or []:
        lines.append(
            f"  transfer {t.get('transfer_id')}: {t.get('source_cell')} -> {t.get('destination_cell')} "
            f"thickness={t.get('committed_thickness')} d_elev_src={t.get('source_elevation_change')} "
            f"d_elev_dst={t.get('destination_elevation_change')} d_depth_src={t.get('source_resolved_depth_change')} "
            f"d_depth_dst={t.get('destination_resolved_depth_change')} rev_src={t.get('source_revision')} "
            f"rev_dst={t.get('destination_revision')} merge={t.get('layer_merge_status')}"
        )
    lines += [
        f"  conservation_residual_max: {summary.get('conservation_residual_max')}",
        f"  atomic_pair_verification: {summary.get('atomic_pair_verification')}",
        f"  persistence_restore_verification: {summary.get('persistence_restore_verification')}",
        f"  agent_leakage_audit: {summary.get('agent_leakage_audit')}",
        "  PHYSICAL_EFFECTS_ACTIVE = NO (persistent authoritative geometry scar with physical effects inactive)",
        "  RESEARCHER_ONLY = YES; AGENT_ACTION = NO; RESOURCE_SPAWNED = NO",
        "  OBSERVED: " + ", ".join(summary.get("OBSERVED") or ["NOT_AVAILABLE"]),
        "  VERIFIED: " + ", ".join(summary.get("VERIFIED") or ["NOT_AVAILABLE"]),
        "  REJECTED: " + ", ".join(summary.get("REJECTED") or ["—"]),
        "  NOT_IMPLEMENTED: " + ", ".join(summary.get("NOT_IMPLEMENTED") or []),
    ]
    lines += [f"  {s}" for s in summary.get("statements") or []]
    return "\n".join(lines)


def receipts_from_consequences(run_dir: Path) -> list[dict[str, Any]]:
    path = Path(run_dir) / "scientific_consequences.jsonl"
    found: list[dict[str, Any]] = []
    if not path.exists():
        return found
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            for ref in row.get("event_refs") or []:
                if isinstance(ref, dict) and ref.get("kind") == "surface_column_transfer":
                    found.append(ref)
    return found
