"""HISTORICAL SENSORIMOTOR SELECTION — Analyzer Next section formatter."""
from __future__ import annotations
from typing import Any

SECTION = "HISTORICAL SENSORIMOTOR SELECTION"

def format_historical_sensorimotor_selection(payload: dict[str, Any] | None) -> str:
    lines = [SECTION, "=" * len(SECTION), ""]
    if not payload or payload.get("status") in {None, "NOT_RECORDED", "NOT_AVAILABLE"}:
        lines += [
            "status: NOT_RECORDED",
            "note: No O-prime history->PSC bridge evidence on DecisionReceipts for this run.",
            "See docs/O_PRIME_HISTORY_BRIDGE_REPORT.md for the dedicated investigation.",
            "",
        ]
        return chr(10).join(lines)
    lines.append(f"status: {payload.get('status')}")
    lines.append(f"source: {payload.get('source')}")
    lines.append(f"first/last active tick: {payload.get('first_tick')}/{payload.get('last_tick')}")
    fun = payload.get("funnel") or {}
    lines.append("FUNNEL")
    for k in [
        "psc_competitions",
        "multi_candidate",
        "smc_preds_available",
        "predicted_futures_differentiated",
        "o_prime_history_queried",
        "historical_support_differentiated",
        "historical_evidence_available_to_psc",
        "withheld_evaluations",
        "psc_ranking_changed_by_history_evidence",
        "final_selection_differs_from_withheld_counterfactual",
    ]:
        lines.append(f"  {k}: {fun.get(k)}")
    agents = payload.get("agents") or {}
    if agents:
        lines.append("")
        lines.append("PER AGENT")
        for aid, ag in sorted(agents.items()):
            lines.append(
                f"  {aid}: evals={ag.get('candidate_evaluations')} "
                f"Oprime_queries={ag.get('o_prime_history_queries')} "
                f"diff_support={ag.get('differentiated_support_competitions')} "
                f"avail_PSC={ag.get('historical_evidence_available_to_psc')} "
                f"withheld={ag.get('withheld_evaluations')} "
                f"CFdelta={ag.get('selection_differs_from_withheld_cf')} "
                f"ticks={ag.get('first_tick')}–{ag.get('last_tick')}"
            )
    examples = payload.get("examples") or []
    if examples:
        lines.append("")
        lines.append("FORENSIC EXAMPLES")
        for ex in examples[:4]:
            lines.append(
                f"  tick {ex.get('tick')} {ex.get('cognitive_agent_id')} "
                f"selected={ex.get('selected_action')} path={ex.get('selection_path')}"
            )
            br = ex.get("bridge") or {}
            lines.append(
                f"    withheld={br.get('withheld_from_psc')} shuffle={br.get('shuffle')} "
                f"support_diff={br.get('history_support_differentiated')} "
                f"CFdelta={br.get('selection_differs_from_withheld_cf')}"
            )
            for c in (ex.get("candidates") or [])[:6]:
                if not isinstance(c, dict):
                    continue
                lines.append(
                    f"    cand {c.get('candidate_locomotion')}: hist={c.get('history_status')} "
                    f"support={c.get('history_support')} fields={c.get('predicted_fields')} "
                    f"available_to_PSC={c.get('available_to_psc')}"
                )
            lines.append("    BOUNDARY: intentional seeking NOT_ESTABLISHED")
    if payload.get("note"):
        lines.append("")
        lines.append(f"note: {payload.get('note')}")
    lines.append("")
    lines.append("INTERPRETATION BOUNDARY")
    lines.append("  O-prime-keyed historical evidence is not preference / seeking / approach.")
    lines.append("  WITHHELD means evidence existed but was not supplied to PSC.")
    lines.append("  Do not treat logging-only association as selection causation.")
    lines.append("")
    return chr(10).join(lines)
