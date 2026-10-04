"""Researcher summary for Free-Space V1C vertical impact acoustic emission."""
from __future__ import annotations

from typing import Any


def summarize_vertical_impact_acoustic_emission(
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    silent_counts: dict[str, int] = {}
    timelines: list[dict[str, Any]] = []
    emissions = 0
    silent = 0
    total_diss = 0.0
    total_emit = 0.0
    for r in receipts:
        emitted = bool(r.get("emitted")) or str(r.get("receipt_kind") or "") == (
            "VERTICAL_IMPACT_ACOUSTIC_EMISSION"
        ) and r.get("emitted_energy") is not None and float(r.get("emitted_energy") or 0) > 0
        reason = str(r.get("silence_reason") or "")
        if emitted and not reason:
            emissions += 1
            total_emit += float(r.get("emitted_energy") or r.get("selected_acoustic_energy") or 0.0)
        else:
            silent += 1
            if reason:
                silent_counts[reason] = int(silent_counts.get(reason, 0)) + 1
        total_diss += float(r.get("dissipated_energy") or 0.0)
        timelines.append(
            {
                "tick": r.get("emission_tick") or r.get("tick"),
                "entity_id": r.get("entity_id"),
                "entity_kind": r.get("entity_kind"),
                "episode_id": r.get("episode_id"),
                "response_key": r.get("response_key"),
                "emitted": bool(emitted and not reason),
                "silence_reason": reason or None,
                "dissipated_energy": r.get("dissipated_energy"),
                "emitted_energy": r.get("emitted_energy") or r.get("selected_acoustic_energy"),
                "contact_point": r.get("contact_point"),
                "source_id": r.get("source_id"),
                "impulse_magnitude": r.get("impulse_magnitude"),
            }
        )
    return {
        "receipt_count": len(receipts),
        "emissions": emissions,
        "silent": silent,
        "silence_reason_counts": silent_counts,
        "total_dissipated_energy": total_diss,
        "total_emitted_energy": total_emit,
        "timelines": timelines,
        "causal_reconstruction": (
            "unsupported fall → landing contact fact → committed inelastic response → "
            "dissipated vertical KE → acoustic eligibility → neutral-band emission or "
            "explicit silence → LPS transport → anonymous auditory consequence"
        ),
        "restitution": 0.0,
        "rebound_implemented": False,
        "human_playback": "NOT IMPLEMENTED",
        "semantic_sfx": False,
        "material_timbre": False,
        "authoritative_acoustic_world": "SINGLE_LPS",
        "organism_hearing": "PHENOTYPE_SENSOR_MEDIATED",
        "section_title": "VERTICAL IMPACT ACOUSTIC EMISSIONS",
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_vertical_impact_acoustic_emission_section(s: dict[str, Any]) -> str:
    lines = [
        "## VERTICAL IMPACT ACOUSTIC EMISSIONS",
        "",
        str(s.get("causal_reconstruction") or ""),
        "",
        f"receipts={s.get('receipt_count', 0)} · emissions={s.get('emissions', 0)} · "
        f"silent={s.get('silent', 0)} · E_diss_total={float(s.get('total_dissipated_energy') or 0):.6g} · "
        f"E_emit_total={float(s.get('total_emitted_energy') or 0):.6g}",
        "",
        "Explicit: restitution e=0 · rebound not implemented · human playback not implemented · "
        "no semantic SFX · no material timbre · one authoritative LPS acoustic world · "
        "persistent support is not impact · position correction alone is silent · "
        "contact fact alone is silent.",
        "",
    ]
    reasons = s.get("silence_reason_counts") or {}
    if reasons:
        lines.append("Silence reasons: " + ", ".join(f"{k}={v}" for k, v in sorted(reasons.items())))
        lines.append("")
    for row in list(s.get("timelines") or [])[:24]:
        lines.append(
            f"- t={row.get('tick')} entity={row.get('entity_id')}/{row.get('entity_kind')} "
            f"emitted={row.get('emitted')} silence={row.get('silence_reason')} "
            f"E_diss={row.get('dissipated_energy')} E_emit={row.get('emitted_energy')} "
            f"source={row.get('source_id')}"
        )
    return "\n".join(lines)


def vertical_impact_acoustic_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    from pathlib import Path
    import json

    root = Path(run_dir)
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("**/consequences*.jsonl")) + sorted(
        root.glob("**/consequence*.jsonl")
    ):
        try:
            with path.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    for ev in list(row.get("event_refs") or []) + list(row.get("events") or []):
                        if not isinstance(ev, dict):
                            continue
                        kind = str(ev.get("kind") or ev.get("receipt_kind") or "")
                        if (
                            "VERTICAL_IMPACT_ACOUSTIC" in kind
                            or kind.endswith("vertical_impact_acoustic_emission")
                        ):
                            out.append(ev)
        except Exception:
            continue
    return out
