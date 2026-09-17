"""Update 4.15 — Researcher instrumentation for prospective continuity vs reconstruction.

Does NOT implement cognitive continuity, anticipation, commitment, or policy coupling.
Trace IDs are researcher-only metadata for experiments/Observer.
"""
from __future__ import annotations

import itertools
from copy import deepcopy
from typing import Any

from mechanistic_mind.psyche.temporal_contingency import (
    coarse_body_state_key,
    predicted_organism_state,
)
from mechanistic_mind.research.multiple_consequences import delta_l1, MATCH_L1
from mechanistic_mind.research.prediction_violation import VIOLATION_COMPONENTS

_id_counter = itertools.count(1)


def new_trace_id(prefix: str = "PT") -> str:
    return f"{prefix}-{next(_id_counter):05d}"


def snapshot_chain(
    *,
    created_tick: int,
    source_state_key: str,
    source_signals: dict[str, float],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    """edges: list of {action, horizon, predicted_state, provenance, consequence_group_id?, support?}"""
    tid = new_trace_id()
    nodes = []
    parent = None
    for i, e in enumerate(edges):
        nid = new_trace_id("PN")
        nodes.append(
            {
                "prospective_trace_id": tid,
                "node_id": nid,
                "parent_node_id": parent,
                "prediction_created_tick": int(created_tick),
                "source_state_key": source_state_key,
                "edge_index": i,
                "action": e.get("action"),
                "horizon": e.get("horizon"),
                "consequence_group_id": e.get("consequence_group_id"),
                "provenance": e.get("provenance") or "DIRECT",
                "support": e.get("support"),
                "predicted_state": deepcopy(e.get("predicted_state")),
                "predicted_state_key": coarse_body_state_key(
                    e.get("predicted_state") or {}, from_interoception=False
                )
                if e.get("predicted_state")
                else None,
                "researcher_only": True,
            }
        )
        parent = nid
    return {
        "prospective_trace_id": tid,
        "prediction_created_tick": int(created_tick),
        "source_state_key": source_state_key,
        "source_signals": deepcopy(source_signals),
        "nodes": nodes,
        "researcher_only": True,
        "note": "instrumentation snapshot — not a cognition variable",
    }


def compare_states(a: dict | None, b: dict | None, eps: float = MATCH_L1) -> dict[str, Any]:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return {"compatible": False, "l1": None, "status": "MISSING"}
    d = delta_l1(a, b)
    return {
        "compatible": d is not None and d <= float(eps),
        "l1": d,
        "status": "MATCH" if d is not None and d <= float(eps) else "NO_MATCH",
        "component_abs": {
            k: abs(float((a or {}).get(k, 0)) - float((b or {}).get(k, 0))) for k in VIOLATION_COMPONENTS
        },
    }


def classify_first_edge(predicted: dict | None, realized: dict | None) -> str:
    if predicted is None:
        return "NO_PREDICTIVE_BASELINE"
    c = compare_states(predicted, realized)
    if c["status"] == "MATCH":
        return "FIRST_EDGE_CONFIRMED"
    return "FIRST_EDGE_MISMATCH"


def same_trace(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    return str(a.get("prospective_trace_id")) == str(b.get("prospective_trace_id"))


def tail_from(snapshot: dict[str, Any], start_edge_index: int = 1) -> list[dict[str, Any]]:
    return [n for n in (snapshot.get("nodes") or []) if int(n.get("edge_index", -1)) >= int(start_edge_index)]
