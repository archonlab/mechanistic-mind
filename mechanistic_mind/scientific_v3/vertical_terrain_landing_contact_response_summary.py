"""Researcher summary for Free-Space V1B vertical terrain landing contact response."""
from __future__ import annotations

from typing import Any


def summarize_vertical_terrain_landing_contact_response(
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    class_counts: dict[str, int] = {}
    phase_counts: dict[str, int] = {}
    timelines: list[dict[str, Any]] = []
    flags: list[str] = []
    impacts = 0
    support_acquired = 0
    dissipated_total = 0.0
    sound_emitted = 0
    rebound_count = 0
    for r in receipts:
        cls = str(r.get("intersection_class") or r.get("response_classification") or "UNKNOWN")
        phase = str(r.get("episode_phase") or "UNKNOWN")
        class_counts[cls] = int(class_counts.get(cls, 0)) + 1
        phase_counts[phase] = int(phase_counts.get(phase, 0)) + 1
        if cls == "LANDING_IMPACT":
            impacts += 1
        if r.get("support_acquired") is True:
            support_acquired += 1
        dissipated_total += float(r.get("dissipated_energy") or 0.0)
        if r.get("impact_sound_emitted") is True:
            sound_emitted += 1
            flags.append(f"unexpected_impact_sound:{r.get('entity_id')}")
        if r.get("rebound") is True:
            rebound_count += 1
            flags.append(f"unexpected_rebound:{r.get('entity_id')}")
        if r.get("restitution") not in (None, 0, 0.0):
            flags.append(f"unexpected_restitution:{r.get('entity_id')}")
        timelines.append(
            {
                "tick": r.get("tick"),
                "entity_id": r.get("entity_id"),
                "entity_kind": r.get("entity_kind"),
                "episode_id": r.get("episode_id"),
                "episode_phase": phase,
                "intersection_class": cls,
                "support_acquired": r.get("support_acquired"),
                "penetration": r.get("penetration"),
                "toi": r.get("toi"),
                "impulse_magnitude": r.get("impulse_magnitude"),
                "dissipated_energy": r.get("dissipated_energy"),
                "vz_pre_response": r.get("vz_pre_response"),
                "vz_post_response": r.get("vz_post_response"),
                "grounded_before": r.get("grounded_before"),
                "grounded_after": r.get("grounded_after"),
                "limitations": r.get("limitations"),
            }
        )
    return {
        "receipt_count": len(receipts),
        "intersection_class_counts": class_counts,
        "episode_phase_counts": phase_counts,
        "landing_impacts": impacts,
        "support_acquisitions": support_acquired,
        "total_dissipated_energy": dissipated_total,
        "impact_sound_emitted_count": sound_emitted,
        "rebound_count": rebound_count,
        "timelines": timelines,
        "flags": flags,
        "causal_reconstruction": (
            "vertical approach → contact fact at committed XY → "
            "inelastic response (e=0) → support acquisition → "
            "PE authority update → physically observable consequence"
        ),
        "rebound_implemented": False,
        "vertical_impact_sound": "NOT IMPLEMENTED",
        "coupled_3d_multi_contact": "NOT RESOLVED V1",
        "section_title": "FREE-SPACE VERTICAL TERRAIN LANDING",
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_vertical_terrain_landing_contact_response_section(s: dict[str, Any]) -> str:
    lines = [
        "## FREE-SPACE VERTICAL TERRAIN LANDING",
        f"receipts={s.get('receipt_count', 0)}",
        f"intersection_classes={s.get('intersection_class_counts')}",
        f"episode_phases={s.get('episode_phase_counts')}",
        f"landing_impacts={s.get('landing_impacts')}",
        f"support_acquisitions={s.get('support_acquisitions')}",
        f"total_dissipated={s.get('total_dissipated_energy')}",
        f"impact_sound_count={s.get('impact_sound_emitted_count')}",
        f"rebound_count={s.get('rebound_count')}",
        f"rebound_implemented={s.get('rebound_implemented')}",
        f"vertical_impact_sound={s.get('vertical_impact_sound')}",
        f"coupled_3d={s.get('coupled_3d_multi_contact')}",
        f"story={s.get('causal_reconstruction')}",
        f"flags={s.get('flags')}",
    ]
    return "\n".join(lines) + "\n"


def vertical_terrain_landing_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
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
                "VERTICAL_TERRAIN_LANDING_V1" in kind
                or kind == "vertical_terrain_landing_v1"
            ):
                out.append(dict(e))
    return out
