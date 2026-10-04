"""Researcher summary for Free-Space V1A support/PE authority contract."""
from __future__ import annotations

from typing import Any


def summarize_free_space_state_and_pe_authority(
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    state_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    pe_counts: dict[str, int] = {}
    timelines: list[dict[str, Any]] = []
    flags: list[str] = []
    double_pe = 0
    rest_skips = 0
    clamps = 0
    for r in receipts:
        st = str(r.get("support_state") or "UNKNOWN")
        reason = str(r.get("transition_reason") or "UNKNOWN")
        pe = str(r.get("active_pe_authority") or "UNKNOWN")
        state_counts[st] = int(state_counts.get(st, 0)) + 1
        reason_counts[reason] = int(reason_counts.get(reason, 0)) + 1
        pe_counts[pe] = int(pe_counts.get(pe, 0)) + 1
        if r.get("double_pe_authority") is True:
            double_pe += 1
            flags.append(f"double_pe:{r.get('entity_id')}")
        if r.get("gravity_skip_reason") == "GRAVITY_SKIPPED_VALID_SUPPORT":
            rest_skips += 1
        if r.get("current_inelastic_clamp") is True:
            clamps += 1
        if r.get("landing_contact_fact_implemented") is True:
            flags.append(f"unexpected_landing_fact:{r.get('entity_id')}")
        if r.get("impulse_emitted") is True:
            flags.append(f"unexpected_impulse:{r.get('entity_id')}")
        if r.get("impact_sound_emitted") is True:
            flags.append(f"unexpected_impact_sound:{r.get('entity_id')}")
        timelines.append(
            {
                "tick": r.get("tick"),
                "entity_id": r.get("entity_id"),
                "entity_kind": r.get("entity_kind"),
                "support_state": st,
                "previous_support_state": r.get("previous_support_state"),
                "transition_reason": reason,
                "base_z": r.get("base_z"),
                "centre_z": r.get("centre_z"),
                "vz_before": r.get("vz_before"),
                "vz_after": r.get("vz_after"),
                "support_height": r.get("support_height"),
                "gravity_applied": r.get("gravity_applied"),
                "gravity_skipped": r.get("gravity_skipped"),
                "gravity_skip_reason": r.get("gravity_skip_reason"),
                "ground_force_eligibility": r.get("ground_force_eligibility"),
                "active_pe_authority": pe,
                "double_pe_authority": r.get("double_pe_authority"),
                "terrain_intersection": r.get("terrain_intersection"),
                "current_inelastic_clamp": r.get("current_inelastic_clamp"),
                "removed_vertical_ke": r.get("removed_vertical_ke"),
            }
        )
    return {
        "receipt_count": len(receipts),
        "support_state_counts": state_counts,
        "transition_reason_counts": reason_counts,
        "pe_authority_counts": pe_counts,
        "supported_rest_gravity_skips": rest_skips,
        "inelastic_clamp_classifications": clamps,
        "double_pe_authority_count": double_pe,
        "timelines": timelines,
        "flags": flags,
        "causal_reconstruction": (
            "support state → support loss or continued support → "
            "gravity eligibility → vertical integration (FGG) → "
            "terrain intersection / current inelastic clamp → "
            "support acquisition → PE authority → ground-force eligibility → "
            "physically observable consequence"
        ),
        "landing_contact_fact": "NOT IMPLEMENTED",
        "compliance_vertical_impulse": "NOT IMPLEMENTED",
        "vertical_impact_sound": "NOT IMPLEMENTED",
        "prospective_free_space_simulation": "NOT ESTABLISHED",
        "section_title": "FREE-SPACE SUPPORT / PE AUTHORITY",
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_free_space_state_and_pe_authority_section(s: dict[str, Any]) -> str:
    lines = [
        "## FREE-SPACE SUPPORT / PE AUTHORITY",
        f"receipts={s.get('receipt_count', 0)}",
        f"support_states={s.get('support_state_counts')}",
        f"transition_reasons={s.get('transition_reason_counts')}",
        f"pe_authorities={s.get('pe_authority_counts')}",
        f"rest_gravity_skips={s.get('supported_rest_gravity_skips')}",
        f"inelastic_clamps={s.get('inelastic_clamp_classifications')}",
        f"double_pe={s.get('double_pe_authority_count')}",
        f"landing_contact_fact={s.get('landing_contact_fact')}",
        f"compliance_vertical_impulse={s.get('compliance_vertical_impulse')}",
        f"vertical_impact_sound={s.get('vertical_impact_sound')}",
        f"prospective_free_space_simulation={s.get('prospective_free_space_simulation')}",
        f"story={s.get('causal_reconstruction')}",
        f"flags={s.get('flags')}",
    ]
    return "\n".join(lines) + "\n"


def free_space_state_and_pe_authority_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    from pathlib import Path
    import json

    out: list[dict[str, Any]] = []
    p = Path(run_dir)
    for path in sorted(p.glob("**/consequences*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        events = data.get("events") or data.get("event_refs") or []
        if not isinstance(events, list):
            continue
        for e in events:
            if not isinstance(e, dict):
                continue
            kind = str(e.get("kind") or e.get("receipt_kind") or "")
            if (
                "FREE_SPACE_SUPPORT_STATE_V1" in kind
                or kind == "free_space_support_state_v1"
            ):
                out.append(dict(e))
    return out
