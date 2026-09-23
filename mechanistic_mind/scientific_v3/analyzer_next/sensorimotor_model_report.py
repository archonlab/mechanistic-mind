"""ACTION-CONDITIONED SENSORIMOTOR MODEL report section (Analyzer Next)."""
from __future__ import annotations

from typing import Any


SECTION = "ACTION-CONDITIONED SENSORIMOTOR MODEL"


def format_sensorimotor_model_section(payload: dict[str, Any] | None) -> str:
    lines = [SECTION, "=" * len(SECTION), ""]
    if not payload or payload.get("status") in {None, "NOT_RECORDED", "NOT_AVAILABLE"}:
        lines.append("status: NOT_RECORDED")
        lines.append("note: No sensorimotor consequence model telemetry in this run (ablated or pre-feature).")
        lines.append("")
        return chr(10).join(lines)
    lines.append(f"status: {payload.get('status', 'RECORDED')}")
    lines.append(f"enabled: {payload.get('enabled')}")
    lines.append(f"source: {payload.get('source')}")
    lines.append(f"queries: {payload.get('queries')}  updates: {payload.get('updates')}")
    lines.append(f"matched/unknown: {payload.get('matched_queries')}/{payload.get('unknown_queries')}")
    lines.append(f"differentiated_predicted_futures_ticks: {payload.get('differentiated_predicted_futures_ticks')}")
    lines.append(f"first/last evidence tick: {payload.get('first_tick')}/{payload.get('last_tick')}")
    motors = payload.get("candidate_motors_represented") or []
    lines.append(f"candidate motors represented (n={len(motors)}): {motors[:12]}")
    agents = payload.get("agents") or {}
    if agents:
        lines.append("")
        lines.append("PER AGENT")
        for aid, ag in sorted(agents.items()):
            lines.append(
                f"  {aid}: decisions={ag.get('decisions')} updates={ag.get('updates')} "
                f"predictions_available={ag.get('predictions_available')} "
                f"ticks={ag.get('first_tick')}–{ag.get('last_tick')} "
                f"motors={ag.get('n_motors')}"
            )
    examples = payload.get("examples") or []
    if examples:
        lines.append("")
        lines.append("FORENSIC EXAMPLES")
        for ex in examples[:5]:
            lines.append(f"  tick {ex.get('tick')} {ex.get('cognitive_agent_id')} decision={ex.get('decision_id')}")
            for pred in (ex.get("predictions") or [])[:4]:
                if not isinstance(pred, dict):
                    continue
                lines.append(
                    f"    motor={pred.get('motor') or pred.get('motor_signature')} "
                    f"status={pred.get('status')} support={pred.get('support')} "
                    f"delta={pred.get('predicted_delta')}"
                )
            upd = ex.get("last_update")
            if isinstance(upd, dict):
                lines.append(
                    f"    update record_id={upd.get('record_id')} motor={upd.get('motor_signature')} "
                    f"mean_delta={upd.get('mean_delta')}"
                )
    lines.append("")
    lines.append("INTERPRETATION BOUNDARY")
    lines.append("  prediction of sensory delta != causation of selection")
    lines.append("  availability to prospection != preference over delta direction")
    lines.append("  no seeking/approach/reward semantics")
    lines.append("")
    return chr(10).join(lines)
