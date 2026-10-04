"""LOCAL PHYSICAL SIGNAL TRANSPORT (Acanthostega). Reads emission/reception receipts only.

Statuses: OBSERVED, VERIFIED, NOT_AVAILABLE, NOT_IMPLEMENTED. No progress bar. The communication
graph has an edge src->dst only when a physical reception was actually observed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SECTION = "LOCAL PHYSICAL SIGNAL TRANSPORT"
SCHEMA_VERSION = "LOCAL_PHYSICAL_SIGNAL_TRANSPORT_SUMMARY_V1"
EMISSION = "LOCAL_PHYSICAL_SIGNAL_EMISSION"
RECEPTION = "LOCAL_PHYSICAL_SIGNAL_RECEPTION"

EXPLICIT = {
    "MATERIAL_DEPENDENT_ACOUSTICS": "NOT_IMPLEMENTED",
    "GEOMETRY_AWARE_ACOUSTICS": "NOT_IMPLEMENTED",
    "ATMOSPHERIC_ACOUSTICS": "NOT_IMPLEMENTED",
    "SEMANTIC_COMMUNICATION": "NOT_ESTABLISHED",
}
NOT_IMPLEMENTED = [
    "material_dependent_acoustics", "geometry_aware_acoustics", "atmospheric_acoustics",
    "impact_or_locomotion_sounds", "reflection_or_occlusion", "direction_or_bearing_sensor",
    "source_identity_sensor", "semantic_message", "full_wave_simulation",
]
# Tokens that must never appear in agent-visible payloads (checked by the caller's leakage audit).
AGENT_FORBIDDEN_FIELDS = [
    "emission_id", "source_body_id", "source_position", "toroidal_distance", "bearing",
    "propagation_delay", "semantic", "source_count",
]


def _rows(events: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    emissions, receptions = [], []
    for e in events or []:
        if not isinstance(e, dict):
            continue
        kind = str(e.get("receipt_kind") or "")
        if kind == EMISSION:
            emissions.append(e)
        elif kind == RECEPTION:
            receptions.append(e)
    return emissions, receptions


def _dedup(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen, out = set(), []
    for r in rows:
        k = r.get(key)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def summarize_local_physical_signal(
    events: list[dict[str, Any]] | None,
    *,
    bodies: list[str] | None = None,
    maximum_range: float | None = None,
    reception_threshold: float | None = None,
    agent_leakage_hits: int | None = None,
    direct_delivery_attempts: int | None = None,
    restore_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    emissions, receptions = _rows(events)
    emissions = _dedup(emissions, "emission_id")
    raw_rec_count = len(receptions)
    receptions = _dedup(receptions, "reception_id")
    accepted = [r for r in receptions if r.get("accepted")]
    rejected = [r for r in receptions if r.get("accepted") is False]
    endo = [e for e in emissions if str(e.get("selection_provenance") or "").startswith("ENDOGENOUS")]
    interv = [e for e in emissions if not str(e.get("selection_provenance") or "").startswith("ENDOGENOUS")]
    graph: dict[str, int] = {}
    for r in accepted:
        src = r.get("source_body_id") or "RESEARCHER_INTERVENTION"
        key = f"{src}->{r.get('receiver_body_id')}"
        graph[key] = graph.get(key, 0) + 1
    nodes = sorted(set(bodies or []) | {r.get("receiver_body_id") for r in accepted if r.get("receiver_body_id")}
                   | {e.get("source_body_id") for e in emissions if e.get("source_body_id")})
    receivers_by_em: dict[str, set] = {}
    for r in accepted:
        receivers_by_em.setdefault(str(r.get("emission_id")), set()).add(r.get("receiver_body_id"))
    did_not_receive = {
        str(e.get("emission_id")): sorted(set(nodes) - receivers_by_em.get(str(e.get("emission_id")), set()))
        for e in emissions[:32]
    }
    dist = [(float(r.get("toroidal_distance") or 0.0), float(r.get("total_received_energy") or 0.0),
             int(r.get("propagation_delay") or 0)) for r in accepted]
    buckets: dict[str, list[float]] = {}
    for d, en, _ in dist:
        buckets.setdefault(f"{int(d)}-{int(d) + 1}", []).append(en)
    energy_vs_distance = {k: round(sum(v) / len(v), 6) for k, v in sorted(buckets.items(), key=lambda kv: float(kv[0].split('-')[0]))}
    delays: dict[str, int] = {}
    for _, _, dl in dist:
        delays[str(dl)] = delays.get(str(dl), 0) + 1
    max_d = max((d for d, _, _ in dist), default=0.0)
    beyond = [r for r in rejected if r.get("rejection_reason") == "BEYOND_MAXIMUM_RANGE"]
    below = [r for r in rejected if r.get("rejection_reason") == "BELOW_RECEPTION_THRESHOLD"]
    wraps = [r for r in accepted if r.get("wraps_torus")]
    same_tick = [r for r in accepted if int(r.get("arrival_tick", 0)) <= int(r.get("emission_tick", 0))]
    arrivals: dict[tuple, int] = {}
    for r in accepted:
        k = (r.get("receiver_body_id"), r.get("arrival_tick"))
        arrivals[k] = arrivals.get(k, 0) + 1
    overlaps = sum(1 for v in arrivals.values() if v > 1)
    global_violation = bool(maximum_range is not None and max_d > float(maximum_range) + 1e-9)
    observed, verified = [], []
    if emissions:
        observed.append("physical_emission")
    if accepted:
        observed.append("local_physical_reception")
    if wraps:
        observed.append("wrap_propagation")
    if overlaps:
        observed.append("overlap_aggregation")
    if beyond:
        observed.append("beyond_range_absence")
    if below:
        observed.append("below_threshold_absence")
    if accepted and not same_tick:
        verified.append("no_same_tick_reception")
    if accepted and not global_violation and maximum_range is not None:
        verified.append("bounded_range")
    if raw_rec_count == len(receptions) and receptions:
        verified.append("duplicate_suppression")
    if agent_leakage_hits == 0:
        verified.append("agent_payload_leakage_audit")
    if direct_delivery_attempts == 0:
        verified.append("direct_delivery_audit")
    if (restore_verification or {}).get("status") == "VERIFIED":
        verified.append("snapshot_restore")
    return {
        "section": SECTION,
        "schema_version": SCHEMA_VERSION,
        "event_count": len(emissions) + len(receptions),
        "emission_count": len(emissions),
        "endogenous_emissions": len(endo),
        "intervention_emissions": len(interv),
        "source_positions": [e.get("physical_origin") for e in emissions[:16]],
        "accepted_receptions": len(accepted),
        "unique_receivers": sorted({r.get("receiver_body_id") for r in accepted}),
        "self_receptions": sum(1 for r in accepted if r.get("self_reception")),
        "foreign_receptions": sum(1 for r in accepted if not r.get("self_reception")),
        "distance_distribution": sorted(round(d, 3) for d, _, _ in dist)[:64],
        "energy_vs_distance": energy_vs_distance,
        "propagation_delays": delays,
        "beyond_range_rejections": len(beyond),
        "below_threshold_rejections": len(below),
        "overlap_aggregations": overlaps,
        "wrap_receptions": len(wraps),
        "duplicate_receptions_in_log": raw_rec_count - len(receptions),
        "same_tick_receptions": len(same_tick),
        "direct_delivery_audit": ("VERIFIED" if direct_delivery_attempts == 0 else
                                  ("NOT_AVAILABLE" if direct_delivery_attempts is None else "VIOLATION")),
        "agent_payload_leakage_audit": ("VERIFIED" if agent_leakage_hits == 0 else
                                        ("NOT_AVAILABLE" if agent_leakage_hits is None else "LEAK_DETECTED")),
        "communication_graph": {"nodes": nodes, "edges": dict(sorted(graph.items()))},
        "max_observed_reception_distance": round(max_d, 6),
        "maximum_range": maximum_range,
        "reception_threshold": reception_threshold,
        "agents_that_did_not_receive": did_not_receive,
        "global_delivery_occurred": global_violation,
        "restore_verification": (restore_verification or {}).get("status", "NOT_AVAILABLE"),
        "OBSERVED": observed,
        "VERIFIED": verified,
        "NOT_IMPLEMENTED": list(NOT_IMPLEMENTED),
        **EXPLICIT,
    }


def format_local_physical_signal_section(summary: dict[str, Any] | None) -> str:
    s = summary or {}
    g = s.get("communication_graph") or {}
    lines = [
        SECTION,
        f"  schema_version: {s.get('schema_version')}",
        f"  emissions: {s.get('emission_count')}  endogenous: {s.get('endogenous_emissions')}  "
        f"intervention: {s.get('intervention_emissions')}",
        f"  source_positions: {s.get('source_positions')}",
        f"  accepted_local_receptions: {s.get('accepted_receptions')}  unique_receivers: {s.get('unique_receivers')}",
        f"  self: {s.get('self_receptions')}  foreign: {s.get('foreign_receptions')}",
        f"  distance_distribution: {s.get('distance_distribution')}",
        f"  energy_vs_distance: {s.get('energy_vs_distance')}",
        f"  propagation_delays: {s.get('propagation_delays')}",
        f"  beyond_range_absence: {s.get('beyond_range_rejections')}  below_threshold_absence: "
        f"{s.get('below_threshold_rejections')}",
        f"  overlap_aggregations: {s.get('overlap_aggregations')}  wrap_receptions: {s.get('wrap_receptions')}",
        f"  duplicate_suppression: duplicates_in_log={s.get('duplicate_receptions_in_log')}",
        f"  direct_delivery_audit: {s.get('direct_delivery_audit')}",
        f"  agent_payload_leakage_audit: {s.get('agent_payload_leakage_audit')}",
        f"  communication_graph: nodes={g.get('nodes')} edges={g.get('edges')}",
        f"  max_observed_reception_distance: {s.get('max_observed_reception_distance')} "
        f"(maximum_range={s.get('maximum_range')})",
        f"  agents_that_did_not_receive: {s.get('agents_that_did_not_receive')}",
        f"  global_delivery_occurred: {'YES' if s.get('global_delivery_occurred') else 'NO'}",
        "  OBSERVED: " + ", ".join(s.get("OBSERVED") or ["NOT_AVAILABLE"]),
        "  VERIFIED: " + ", ".join(s.get("VERIFIED") or ["NOT_AVAILABLE"]),
        "  NOT_IMPLEMENTED: " + ", ".join(s.get("NOT_IMPLEMENTED") or []),
    ]
    for k in EXPLICIT:
        lines.append(f"  {k} = {s.get(k, EXPLICIT[k])}")
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
                if isinstance(ref, dict) and ref.get("kind") == "local_physical_signal":
                    found.append(ref)
    return found
