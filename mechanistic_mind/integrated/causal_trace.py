from __future__ import annotations

from typing import Any

from mechanistic_mind.integrated.copy_opt import capture_flat_mapping, capture_provenance


def empty_trace(capacity: int = 512) -> dict[str, Any]:
    return {"events": [], "edges": [], "capacity": max(16, int(capacity)), "next_id": 1}


def event(trace: dict[str, Any], *, tick: int, kind: str, mechanism: str,
          payload: dict[str, Any] | None = None) -> str:
    eid = f"C{int(trace.get('next_id', 1)):08d}"
    trace["next_id"] = int(trace.get("next_id", 1)) + 1
    # Flat scalar payloads: shallow container capture (same scientific content).
    trace.setdefault("events", []).append({
        "id": eid, "tick": int(tick), "kind": str(kind),
        "mechanism": str(mechanism), "payload": capture_flat_mapping(payload),
    })
    _trim(trace)
    return eid


def edge(trace: dict[str, Any], *, source: str, target: str, tick: int,
         mechanism: str, provenance: Any, magnitude: float | None = None,
         relation: str = "CAUSAL") -> None:
    # Callers may only add an edge at the point an input is actually consumed.
    row = {"source": source, "target": target, "tick": int(tick),
           "mechanism": mechanism, "provenance": capture_provenance(provenance),
           "relation": relation}
    if magnitude is not None:
        row["magnitude"] = float(magnitude)
    trace.setdefault("edges", []).append(row)
    _trim(trace)


def _trim(trace: dict[str, Any]) -> None:
    """Enforce capacity bounds without reconstructing when already within limits.

    Retention semantics unchanged:
    - keep at most ``capacity`` newest events
    - drop edges that reference removed events
    - keep at most ``capacity * 3`` newest surviving edges
    """
    cap = max(16, int(trace.get("capacity", 512)))
    edge_cap = cap * 3
    events = trace.setdefault("events", [])
    edges = trace.setdefault("edges", [])

    if len(events) <= cap:
        # Previously always re-sliced edges here even when under edge_cap — redundant.
        if len(edges) > edge_cap:
            trace["edges"] = edges[-edge_cap:]
        return

    overflow = len(events) - cap
    removed = {row["id"] for row in events[:overflow]}
    # In-place drop of oldest events (same survivors as events[-cap:]).
    del events[:overflow]
    if removed:
        edges[:] = [
            row for row in edges
            if row.get("source") not in removed and row.get("target") not in removed
        ]
    if len(edges) > edge_cap:
        trace["edges"] = edges[-edge_cap:]
    else:
        trace["edges"] = edges


def neighborhood(trace: dict[str, Any], event_id: str) -> dict[str, Any]:
    from mechanistic_mind.integrated.copy_opt import jsonish_copy

    events = {row["id"]: row for row in trace.get("events", [])}
    incoming = [row for row in trace.get("edges", []) if row.get("target") == event_id]
    outgoing = [row for row in trace.get("edges", []) if row.get("source") == event_id]
    ids = {event_id} | {r["source"] for r in incoming} | {r["target"] for r in outgoing}
    return {
        "selected": jsonish_copy(events.get(event_id)),
        "contributors": jsonish_copy(incoming),
        "influences": jsonish_copy(outgoing),
        "events": [jsonish_copy(events[i]) for i in ids if i in events],
    }
