"""Update 4.7.1 — Observer/experiment-side cross-agent physical trace probe.

No social semantics. Probe IDs and actor provenance NEVER enter cognition.
Structural matching uses physical quantity/features only.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


PROBE_EVENT_ID = "CROSS_TRACE_001"  # Observer/experiment only.


def quantity_of(world_vars: dict[str, Any], object_id: str) -> float | None:
    world = (world_vars or {}).get("world") or {}
    rec = (world.get("objects") or {}).get(object_id)
    if not isinstance(rec, dict) or "quantity" not in rec:
        return None
    try:
        return float(rec["quantity"])
    except Exception:
        return None


def agent_visible_quantity(observation_data: dict[str, Any], object_id: str) -> dict[str, Any]:
    """Extract agent-available quantity evidence for object_id (no provenance)."""
    out: dict[str, Any] = {
        "object_id": object_id,
        "in_visible_objects": False,
        "quantity": None,
        "channel_hints": [],
        "relative_offset": None,
    }
    if not isinstance(observation_data, dict):
        return out
    for item in observation_data.get("visible_objects") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("id")) != object_id:
            continue
        out["in_visible_objects"] = True
        out["relative_offset"] = deepcopy(item.get("relative_offset"))
        obs_state = item.get("observable_state") or {}
        if isinstance(obs_state, dict) and "quantity" in obs_state:
            try:
                out["quantity"] = float(obs_state["quantity"])
            except Exception:
                out["quantity"] = obs_state.get("quantity")
        break
    pp = observation_data.get("physical_perception") or {}
    channels = pp.get("channels") if isinstance(pp, dict) else {}
    if isinstance(channels, dict):
        for ch_name, rows in channels.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                # Multi-channel packets must not carry object IDs; match by
                # co-presence only when quantity-like numeric fields appear.
                if "quantity" in row or "feature_count" in row:
                    out["channel_hints"].append(str(ch_name))
                    break
    return out


def episode_has_quantity_evidence(episode: dict[str, Any], object_id: str, quantity: float | None) -> bool:
    if not isinstance(episode, dict):
        return False
    for item in episode.get("visible_objects") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("id")) != object_id:
            continue
        obs = item.get("observable_state") or {}
        if not isinstance(obs, dict) or "quantity" not in obs:
            continue
        if quantity is None:
            return True
        try:
            return abs(float(obs["quantity"]) - float(quantity)) < 1e-6
        except Exception:
            return False
    return False


def spatial_has_quantity_evidence(psyche: dict[str, Any], object_id: str) -> dict[str, Any]:
    mem = (psyche or {}).get("memory") or {}
    spatial = mem.get("spatial") or {}
    objects = spatial.get("objects") or {}
    rec = objects.get(object_id) if isinstance(objects, dict) else None
    if not isinstance(rec, dict):
        return {"present": False, "quantity": None, "last_seen_tick": None}
    obs = rec.get("observable_state") or {}
    qty = None
    if isinstance(obs, dict) and "quantity" in obs:
        try:
            qty = float(obs["quantity"])
        except Exception:
            qty = obs.get("quantity")
    return {
        "present": True,
        "quantity": qty,
        "last_seen_tick": rec.get("last_seen_tick"),
    }


def find_matching_episodes(
    psyche: dict[str, Any],
    *,
    object_id: str,
    target_quantity: float | None,
) -> list[dict[str, Any]]:
    mem = (psyche or {}).get("memory") or {}
    episodes = mem.get("episodes") or []
    hits = []
    if not isinstance(episodes, list):
        return hits
    for idx, ep in enumerate(episodes):
        if episode_has_quantity_evidence(ep, object_id, target_quantity):
            hits.append(
                {
                    "index": idx,
                    "tick": ep.get("tick"),
                    "action": ep.get("action"),
                    "quantity_match": True,
                }
            )
    return hits


def scan_for_leakage(payload: Any, forbidden: set[str] | None = None) -> list[str]:
    """Recursively search agent-facing structures for forbidden provenance strings."""
    forbidden = forbidden or {
        PROBE_EVENT_ID,
        "CROSS_TRACE",
        "changed_by",
        "changed_by_agent",
        "source_agent",
        "actor_id",
        "probe_event_id",
        "used_by",
        "visited_by",
        "social",
        "communication",
        "owner",
        "message",
    }
    leaks: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                ks = str(k)
                if any(f.lower() in ks.lower() for f in forbidden):
                    leaks.append(f"{path}.{ks}")
                walk(v, f"{path}.{ks}")
        elif isinstance(node, list):
            for i, v in enumerate(node[:200]):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str):
            low = node.lower()
            for f in forbidden:
                if f.lower() in low:
                    leaks.append(f"{path}={node[:80]}")
                    break

    walk(payload, "$")
    return leaks


def append_observer_receipt(world_variables: dict[str, Any], receipt: dict[str, Any]) -> None:
    """Store ground-truth probe events in Observer-only world receipts."""
    receipts = world_variables.setdefault("observer_receipts", {})
    if not isinstance(receipts, dict):
        return
    bucket = receipts.setdefault("cross_agent_trace_v471", [])
    if isinstance(bucket, list):
        bucket.append(deepcopy(receipt))


def stage_status(chain: dict[str, Any]) -> dict[str, str]:
    """Conservative stage labels for Observer panel."""
    stages = {
        "PHYSICAL_EVENT": "NOT_YET",
        "OBSERVABLE": "NOT_YET",
        "EXPERIENCE": "NOT_YET",
        "RETRIEVAL": "NOT_YET",
        "PREDICTION": "NOT_YET",
        "PROSPECTIVE_VALUE": "NOT_YET",
        "DECISION": "NOT_YET",
    }
    if chain.get("intervention"):
        stages["PHYSICAL_EVENT"] = "OBSERVED"
    if chain.get("b_observation", {}).get("quantity") is not None:
        stages["OBSERVABLE"] = "OBSERVED"
    if chain.get("b_experience", {}).get("stored"):
        stages["EXPERIENCE"] = "STORED"
    ret = chain.get("b_retrieval") or {}
    if ret.get("retrieved"):
        stages["RETRIEVAL"] = "RETRIEVED"
    elif ret.get("eligible") is False:
        stages["RETRIEVAL"] = "NOT_RETRIEVED"
    elif chain.get("b_experience", {}).get("stored"):
        stages["RETRIEVAL"] = "UNAVAILABLE" if ret.get("status") == "UNAVAILABLE" else "NOT_RETRIEVED"
    pred = chain.get("b_prediction") or {}
    if pred.get("participated"):
        stages["PREDICTION"] = "PARTICIPATED"
    elif pred.get("status") == "UNAVAILABLE":
        stages["PREDICTION"] = "UNAVAILABLE"
    elif stages["RETRIEVAL"] in {"RETRIEVED", "NOT_RETRIEVED"}:
        stages["PREDICTION"] = pred.get("status") or "NOT_YET"
    val = chain.get("b_valuation") or {}
    if val.get("participated"):
        stages["PROSPECTIVE_VALUE"] = "PARTICIPATED"
    elif val.get("status") == "UNAVAILABLE":
        stages["PROSPECTIVE_VALUE"] = "UNAVAILABLE"
    dec = chain.get("b_decision") or {}
    if dec.get("selected") is not None:
        stages["DECISION"] = "OBSERVED"
        if dec.get("rejected_trace_related"):
            stages["DECISION"] = "REJECTED"
    return stages
