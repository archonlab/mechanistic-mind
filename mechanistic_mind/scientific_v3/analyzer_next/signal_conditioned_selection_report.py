"""SIGNAL-CONDITIONED SENSORIMOTOR SELECTION — report formatter."""
from __future__ import annotations
from typing import Any

SECTION = "SIGNAL-CONDITIONED SENSORIMOTOR SELECTION"


def format_signal_conditioned_selection(payload: dict[str, Any] | None) -> str:
    lines = [SECTION, "=" * len(SECTION), ""]
    if not payload or payload.get("status") in {None, "NOT_RECORDED"}:
        lines += ["status: NOT_RECORDED", ""]
        return chr(10).join(lines)
    lines.append(f"status: {payload.get('status')}")
    lines.append(f"source: {payload.get('source')}")
    lines.append(f"SMC signal channels: {payload.get('smc_signal_channels')}")
    lines.append(f"osc L/R bands in SMC: {payload.get('osc_bands_in_SMC')}")
    lines.append("")
    lines.append("PATH AUDIT")
    for stage, vals in (payload.get("path_audit") or {}).items():
        lines.append(f"  {stage}: {vals}")
    lines.append("")
    lines.append("FUNNEL")
    for k, v in (payload.get("funnel") or {}).items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("GATES")
    for k, v in (payload.get("gates") or {}).items():
        lines.append(f"  {k}: {v}")
    agents = payload.get("agents") or {}
    if agents:
        lines.append("")
        lines.append("PER AGENT")
        for aid, ag in sorted(agents.items()):
            lines.append(f"  {aid}:")
            for k in (
                "signal_present_psc", "signal_smc_predictions", "differentiated_signal_futures",
                "o_prime_history_queries", "historical_support_differentiated",
                "historical_evidence_available_to_psc", "selected_candidates",
                "withheld_cf_changes", "no_vision_signal_present", "no_vision_differentiated",
                "bilateral_obs_ticks",
            ):
                lines.append(f"    {k}: {ag.get(k)}")
            lines.append(f"    ticks: {ag.get('first_tick')}–{ag.get('last_tick')}")
    examples = payload.get("examples") or []
    if examples:
        lines.append("")
        lines.append("FORENSIC EXAMPLES")
        for ex in examples[:5]:
            lines.append(
                f"  tick {ex.get('tick')} {ex.get('cognitive_agent_id')} "
                f"selected={ex.get('selected_action')} mode={ex.get('selection_mode')}"
            )
            lines.append(f"    signal={ex.get('agent_accessible_signal')}")
            lines.append(f"    foreign_body_visual_exposure={ex.get('foreign_body_visual_exposure')}")
            bil = ex.get("bilateral_derived")
            if bil:
                lines.append(
                    f"    bilateral_DERIVED total_L={bil.get('total_L')} total_R={bil.get('total_R')} "
                    f"asym={bil.get('asymmetry')} (NOT AN AGENT VARIABLE)"
                )
            for p in (ex.get("signal_candidate_predictions") or [])[:6]:
                lines.append(
                    f"    cand {p.get('motor')}: status={p.get('status')} "
                    f"signal_delta={p.get('signal_predicted_delta')} support={p.get('support')}"
                )
            br = ex.get("hss_bridge") or {}
            lines.append(
                f"    HSS withheld={br.get('withheld_from_psc')} "
                f"support_diff={br.get('history_support_differentiated')} "
                f"CFdelta={br.get('selection_differs_from_withheld_cf')}"
            )
            bd = ex.get("boundary") or {}
            lines.append(f"    BOUNDARY {bd}")
    cb = payload.get("claims_boundary") or {}
    if cb:
        lines.append("")
        lines.append("CLAIMS BOUNDARY")
        lines.append(f"  allowed_if_supported: {cb.get('allowed_if_supported')}")
        lines.append(f"  not_established: {cb.get('not_established')}")
    lines.append("")
    return chr(10).join(lines)
