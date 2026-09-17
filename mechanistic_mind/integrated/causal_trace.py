from __future__ import annotations

from copy import deepcopy
from typing import Any


def empty_trace(capacity: int = 512) -> dict[str, Any]:
    return {"events": [], "edges": [], "capacity": max(16, int(capacity)), "next_id": 1}


def event(trace: dict[str, Any], *, tick: int, kind: str, mechanism: str,
          payload: dict[str, Any] | None = None) -> str:
    eid = f"C{int(trace.get('next_id', 1)):08d}"
    trace["next_id"] = int(trace.get("next_id", 1)) + 1
    trace.setdefault("events", []).append({
        "id": eid, "tick": int(tick), "kind": str(kind),
        "mechanism": str(mechanism), "payload": deepcopy(payload or {}),
    })
    _trim(trace)
    return eid


def edge(trace: dict[str, Any], *, source: str, target: str, tick: int,
         mechanism: str, provenance: Any, magnitude: float | None = None,
         relation: str = "CAUSAL") -> None:
    # Callers may only add an edge at the point an input is actually consumed.
    row = {"source": source, "target": target, "tick": int(tick),
           "mechanism": mechanism, "provenance": deepcopy(provenance),
           "relation": relation}
    if magnitude is not None:
        row["magnitude"] = float(magnitude)
    trace.setdefault("edges", []).append(row)
    _trim(trace)


def _trim(trace: dict[str, Any]) -> None:
    cap = max(16, int(trace.get("capacity", 512)))
    events = trace.setdefault("events", [])
    if len(events) <= cap:
        trace["edges"] = trace.setdefault("edges", [])[-cap * 3:]
        return
    removed = {row["id"] for row in events[:-cap]}
    trace["events"] = events[-cap:]
    trace["edges"] = [row for row in trace.setdefault("edges", [])
                      if row.get("source") not in removed and row.get("target") not in removed][-cap * 3:]


def neighborhood(trace: dict[str, Any], event_id: str) -> dict[str, Any]:
    events = {row["id"]: row for row in trace.get("events", [])}
    incoming = [row for row in trace.get("edges", []) if row.get("target") == event_id]
    outgoing = [row for row in trace.get("edges", []) if row.get("source") == event_id]
    ids = {event_id} | {r["source"] for r in incoming} | {r["target"] for r in outgoing}
    return {"selected": deepcopy(events.get(event_id)), "contributors": deepcopy(incoming),
            "influences": deepcopy(outgoing), "events": [deepcopy(events[i]) for i in ids if i in events]}
