"""Analyzer section: HELD OBJECT / FOREIGN BODY IMPULSE MEDIATION."""
from __future__ import annotations

from typing import Any


def summarize_held_translational_impulse(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict) and (
        e.get("kind") == "held_resource_object_translational_impulse_mediation"
        or e.get("mechanism") == "held_resource_object_translational_impulse_mediation"
        or e.get("receipt_kind") == "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT_RESPONSE"
    )]
    impulses = [r for r in rows if r.get("impulse_transferred")]
    eligible = [r for r in rows if r.get("mediation_eligible")]
    effector = [r for r in rows if r.get("reason") == "EFFECTOR_WORK_NOT_ACCOUNTED" or r.get("no_response_reason") == "EFFECTOR_WORK_NOT_ACCOUNTED"]
    grasp = [r for r in rows if "GRASP_SNAP" in str(r.get("reason") or r.get("no_response_reason") or "")]
    multi = [r for r in rows if "MULTI_CONSTRAINT" in str(r.get("reason") or r.get("no_response_reason") or "")]
    return {
        "section": "HELD OBJECT / FOREIGN BODY IMPULSE MEDIATION",
        "contact_measurements": len(rows),
        "translationally_eligible": len(eligible),
        "effector_work_unresolved": len(effector),
        "grasp_transition_exclusions": len(grasp),
        "multi_constraint_unresolved": len(multi),
        "impulses_applied": len(impulses),
        "constraint_masses": [r.get("total_constraint_mass") for r in impulses if r.get("total_constraint_mass") is not None],
        "compliance_restitution": [
            {"compliance": r.get("compliance"), "restitution_e": r.get("restitution_e")}
            for r in impulses
        ],
        "momentum_residuals": [r.get("momentum_residual") for r in impulses],
        "ke_before": [r.get("ke_before") for r in impulses],
        "ke_after": [r.get("ke_after") for r in impulses],
        "dissipated_energy": [r.get("dissipated_energy") for r in impulses],
        "correction_count": sum(1 for r in rows if r.get("position_corrected")),
        "holder_delta_v": [r.get("holder_delta_v") for r in impulses],
        "foreign_delta_v": [r.get("foreign_delta_v") for r in impulses],
        "external_impulse_grace": sum(1 for r in rows if int(r.get("grace_ticks_set") or 0) > 0),
        "duplicate_processing": sum(1 for r in rows if r.get("reason") == "ALREADY_PROCESSED"),
        "automatic_releases": sum(1 for r in rows if r.get("automatic_release")),
        "damage": sum(1 for r in rows if r.get("damage_applied")),
        "sound": sum(1 for r in rows if r.get("sound_emitted")),
        "provenance_privacy_complete": all(
            r.get("agent_accessible") is False and r.get("object_remains_held") is True
            for r in rows
        ) if rows else True,
    }


def format_held_translational_impulse_section(s: dict[str, Any]) -> str:
    lines = [
        "HELD OBJECT / FOREIGN BODY IMPULSE MEDIATION",
        f"  contact_measurements: {s.get('contact_measurements')}",
        f"  translationally_eligible: {s.get('translationally_eligible')}",
        f"  effector_work_unresolved: {s.get('effector_work_unresolved')}",
        f"  grasp_transition_exclusions: {s.get('grasp_transition_exclusions')}",
        f"  multi_constraint_unresolved: {s.get('multi_constraint_unresolved')}",
        f"  impulses_applied: {s.get('impulses_applied')}",
        f"  correction_count: {s.get('correction_count')}",
        f"  external_impulse_grace: {s.get('external_impulse_grace')}",
        f"  duplicate_processing: {s.get('duplicate_processing')}",
        f"  automatic_releases: {s.get('automatic_releases')} (expect 0)",
        f"  damage: {s.get('damage')} (expect 0)",
        f"  sound: {s.get('sound')} (expect 0)",
        f"  provenance_privacy_complete: {s.get('provenance_privacy_complete')}",
    ]
    return "\n".join(lines)


def held_translational_impulse_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    """Collect mediation receipts from consequence / capture event refs."""
    from pathlib import Path as _P
    import json
    root = _P(run_dir)
    out: list[dict[str, Any]] = []
    for name in ("consequences.jsonl", "events.jsonl", "tick_events.jsonl"):
        fp = root / name
        if not fp.exists():
            continue
        try:
            for line in fp.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                kind = str(row.get("kind") or row.get("mechanism") or "")
                if "translational_impulse" in kind or row.get("receipt_kind") == "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT_RESPONSE":
                    out.append(row)
                # nested event_refs
                for ref in row.get("event_refs") or []:
                    if isinstance(ref, dict) and (
                        "translational_impulse" in str(ref.get("kind") or "")
                        or ref.get("receipt_kind") == "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT_RESPONSE"
                    ):
                        out.append(ref)
        except Exception:
            continue
    return out
