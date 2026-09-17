"""Observer-side diagnostics for Current MM action decisions.

Does NOT alter selection behavior. Receipts record what the runtime already did.
"""
from __future__ import annotations

from collections import Counter, deque
from copy import deepcopy
from typing import Any

import numpy as np

from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import predictive_compression as pc

from .actions import available_actions


def _na() -> str:
    return "NOT_AVAILABLE"


def build_action_decision_receipt(
    *,
    tick: int,
    observation: dict[str, float],
    selected: str,
    selection_source: str,
    actions: list[str],
    predictions: list[dict[str, Any]],
    continuations: list[dict[str, Any]],
    composition: dict[str, Any],
    last_apply: dict[str, Any] | None,
    body_before: dict[str, Any] | None,
    body_after: dict[str, Any] | None,
    selection_rule: str,
    last_selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured receipt from real selection inputs — no invented scores.

    Schema v2 adds scenario_groups + competition when SCENARIO_COMPETITION ran.
    """
    last_selection = last_selection or {}
    pred_by_action = {str(p["action"]): p for p in predictions}
    cont_first_actions = [str((c.get("actions") or ["?"])[0]) for c in continuations]
    scenario_groups = deepcopy(last_selection.get("scenario_groups") or {})
    competition = deepcopy(last_selection.get("competition") or {})
    mode = str(last_selection.get("prospective_selection_mode") or competition.get("mode") or "UNKNOWN")
    peer_evaluation = last_selection.get("peer_evaluation") or "NONE"

    candidates = []
    for act in actions:
        pred = pred_by_action.get(act)
        matching_conts = [
            {
                "actions": c.get("actions"),
                "depth": c.get("depth"),
                "score_reliability": c.get("score_reliability"),
                "edges": [
                    {
                        "status": e.get("status"),
                        "key": e.get("key"),
                        "reliability": e.get("reliability"),
                        "support": e.get("support"),
                    }
                    for e in (c.get("edges") or [])
                ],
            }
            for c in continuations
            if (c.get("actions") or [None])[0] == act
        ]
        group = scenario_groups.get(act) or {}
        supported = bool(group.get("supported") or group.get("count") or matching_conts)
        if isinstance(group.get("scenarios"), list) and group["scenarios"]:
            supported = True
        accepted = act == selected
        rejection = None
        if not accepted:
            if selection_source in {"PROSPECTIVE_SCENARIO", "PROSPECTIVE_TIE_RESOLUTION"}:
                if not supported:
                    rejection = "NO_SUPPORTED_PROSPECTIVE_SCENARIO"
                else:
                    rejection = "DOMINATED_OR_TIED_NOT_CHOSEN_IN_SCENARIO_COMPETITION"
            elif selection_source == "PROSPECTIVE_CONTINUATION":
                if not matching_conts:
                    rejection = "NO_PROSPECTIVE_CONTINUATION_ROOTED_AT_THIS_ACTION"
                elif continuations and str((continuations[0].get("actions") or [None])[0]) != act:
                    rejection = "NOT_FIRST_ACTION_OF_TOP_RANKED_CONTINUATION"
                else:
                    rejection = "NOT_SELECTED_BY_TOP_CONTINUATION_RULE"
            elif selection_source == "RETAINED_PREDICTION":
                rejection = "LOWER_OR_ABSENT_COMPRESSION_SUPPORT" if pred else "NO_COMPRESSION_MATCH"
            else:
                rejection = "NOT_CHOSEN_BY_ENDOGENOUS_INDEX"
        candidates.append({
            "candidate": act,
            "syntactically_available": True,
            "predictively_supported": supported,
            "compression_match": None if pred is None else {
                "status": (pred.get("result") or {}).get("status"),
                "support": (pred.get("result") or {}).get("support", _na()),
            },
            "prospective_roots": matching_conts,
            "prospective_root_count": len(matching_conts),
            "scenario_count": int(group.get("count") or len(group.get("scenarios") or [])),
            "accepted": accepted,
            "rejection_reason": rejection,
            "peer_comparison_score": _na(),
        })

    tie_state = "NOT_APPLICABLE"
    tie_break = _na()
    outcome = competition.get("outcome_class")
    if outcome in {"EXACT_TIE", "PARTIAL_ORDER_TIE", "INCOMPARABLE"}:
        tie_state = str(outcome)
        tie_break = deepcopy(competition.get("tie_resolution") or _na())
    elif outcome == "SINGLE_SUPPORTED":
        tie_state = "SINGLE_SUPPORTED"
        tie_break = "only one first-action had supported prospective scenario"
    elif outcome == "DOMINANT_SCENARIO":
        tie_state = "NO_TIE"
        tie_break = "pareto dominance under (historical_support, reliability, depth)"
    elif outcome == "LEGACY_FIRST_ELEMENT":
        tie_state = "LEGACY_LIST_ORDER"
        tie_break = "LEGACY_FIRST uses continuations[0].actions[0]"
    elif selection_source == "PROSPECTIVE_CONTINUATION" and len(continuations) >= 2:
        a, b = continuations[0], continuations[1]
        if a.get("depth") == b.get("depth") and abs(float(a.get("score_reliability") or 0) - float(b.get("score_reliability") or 0)) < 1e-12:
            tie_state = "TIED_DEPTH_AND_RELIABILITY_AT_RANK_BOUNDARY"
            tie_break = "stable_sort_keeps_earlier_workspace_order; first action of first continuation wins"
        else:
            tie_state = "NO_TIE_AT_TOP"
            tie_break = "rank_key=(-depth,-score_reliability); then take continuations[0].actions[0]"

    consequence = {"status": _na()}
    if body_before and body_after:
        consequence = {
            "status": "AVAILABLE",
            "dx": float(body_after["x"] - body_before["x"]),
            "dy": float(body_after["y"] - body_before["y"]),
            "displacement": float(np.hypot(body_after["x"] - body_before["x"], body_after["y"] - body_before["y"])),
            "dT": float(body_after["T"] - body_before["T"]),
            "dvx": float(body_after["vx"] - body_before["vx"]),
            "dvy": float(body_after["vy"] - body_before["vy"]),
            "position_delta": {
                "from": {"x": body_before["x"], "y": body_before["y"]},
                "to": {"x": body_after["x"], "y": body_after["y"]},
            },
            "body_delta": {
                "dT": float(body_after["T"] - body_before["T"]),
                "dvx": float(body_after["vx"] - body_before["vx"]),
                "dvy": float(body_after["vy"] - body_before["vy"]),
            },
            "world_delta": _na(),
        }

    supported_actions = [
        a for a in actions
        if (scenario_groups.get(a) or {}).get("supported")
        or int((scenario_groups.get(a) or {}).get("count") or 0) > 0
        or bool((scenario_groups.get(a) or {}).get("scenarios"))
    ]
    if not supported_actions and competition.get("supported_actions"):
        supported_actions = list(competition.get("supported_actions") or [])

    return {
        "schema": "mm.action_decision_receipt.v2",
        "tick": int(tick),
        "available_physical_actions": list(actions),
        "supported_physical_actions": supported_actions,
        "selected_action": selected,
        "selection_source": selection_source,
        "prospective_selection_mode": mode,
        "observation": deepcopy(observation),
        "retrieved_structures": {
            "compression_predictions": deepcopy(predictions),
            "note": "Structures listed are those returned by pc.predict for current observation×action; empty if prediction matches=0",
        },
        "prospective_continuations": {
            "count": len(continuations),
            "composition_meta": {
                "expansion_count": composition.get("expansion_count"),
                "max_depth_reached": composition.get("max_depth_reached"),
                "composition_enabled": composition.get("composition_enabled"),
            },
            "top": deepcopy(continuations[:8]),
            "top_first_actions": cont_first_actions[:8],
        },
        "scenario_groups": scenario_groups,
        "competition": {
            "candidates_considered": competition.get("candidates_considered"),
            "evidence_dimensions": competition.get("evidence_dimensions"),
            "evidence_order": competition.get("evidence_order"),
            "dominance_relations": competition.get("dominance_relations"),
            "ties": competition.get("ties"),
            "incomparable_candidates": competition.get("incomparable_candidates"),
            "selected_scenario": competition.get("selected_scenario"),
            "selected_action": competition.get("selected_action"),
            "selection_reason": competition.get("selection_reason") or competition.get("outcome_class"),
            "tie_resolution": competition.get("tie_resolution"),
            "outcome_class": competition.get("outcome_class"),
            "unsupported_actions": competition.get("unsupported_actions"),
            "mode": mode,
        },
        "candidates": candidates,
        "selection": {
            "winner": selected,
            "selection_rule": selection_rule,
            "tie_state": tie_state,
            "tie_break_rule": tie_break,
            "peer_evaluation": peer_evaluation,
        },
        "bridge": {
            "cognitive_selection": selected,
            "cognitive_action": selected,
            "emitted_impulse": deepcopy((last_apply or {}).get("impulse") if isinstance(last_apply, dict) else _na()),
            "physical_action_received": deepcopy((last_apply or {}).get("action") if isinstance(last_apply, dict) else selected),
            "apply": deepcopy(last_apply),
        },
        "consequence": consequence,
    }


def counterfactual_candidate_probe(
    *,
    store: dict[str, Any],
    compression: dict[str, Any],
    observation: dict[str, float],
    actions: list[str] | None = None,
) -> dict[str, Any]:
    """Observer-side: what evidence exists per action without changing selection."""
    actions = list(actions or available_actions())
    rows = []
    for act in actions:
        step = pr.predict_one_step(store, observation, act)
        pred = pc.predict(compression, observation, act, domain="accessible")
        rows.append({
            "action": act,
            "prospective_one_step": {
                "status": step.get("status"),
                "reliability": step.get("reliability", _na()),
                "support": step.get("support", _na()),
                "key": step.get("key"),
            },
            "compression": {
                "status": pred.get("status"),
                "support": pred.get("support", _na()),
            },
        })
    return {"status": "AVAILABLE", "per_action": rows, "note": "Diagnostic only; not used by MM selection"}


def analyze_wait_loop(receipts: list[dict[str, Any]], positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Observer-only pattern labels from recorded decisions/positions."""
    if not receipts:
        return {"status": "NOT_AVAILABLE", "reason": "no receipts"}
    actions = [r.get("selected_action") for r in receipts]
    n = len(actions)
    wait_n = sum(1 for a in actions if a == "WAIT")
    move_n = sum(1 for a in actions if isinstance(a, str) and a.startswith("MOVE"))
    # longest WAIT run
    best = cur = 0
    for a in actions:
        if a == "WAIT":
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    # spatial
    spatial: dict[str, Any] = {"status": _na()}
    if len(positions) >= 2:
        xs = [float(p["x"]) for p in positions]
        ys = [float(p["y"]) for p in positions]
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        # approximate displacement path length (no wrap correction here; occupancy uses wrap-aware segs)
        path = 0.0
        for i in range(1, len(positions)):
            path += float(np.hypot(positions[i]["x"] - positions[i - 1]["x"], positions[i]["y"] - positions[i - 1]["y"]))
        cells = {(int(np.floor(p["x"])), int(np.floor(p["y"]))) for p in positions}
        cx, cy = float(np.mean(xs)), float(np.mean(ys))
        rg = float(np.sqrt(np.mean([(p["x"] - cx) ** 2 + (p["y"] - cy) ** 2 for p in positions])))
        spatial = {
            "status": "AVAILABLE",
            "bbox_dx": dx,
            "bbox_dy": dy,
            "path_length_naive": path,
            "unique_cells": len(cells),
            "radius_of_gyration": rg,
            "n_positions": len(positions),
        }
    # retrieval/continuation similarity
    top_keys = []
    for r in receipts:
        tops = (r.get("prospective_continuations") or {}).get("top") or []
        if tops:
            edges = tops[0].get("edges") or []
            if edges:
                top_keys.append(edges[0].get("key"))
    key_counts = Counter(top_keys)
    labels = []
    if wait_n / max(1, n) >= 0.7:
        labels.append("PERSISTENT_WAIT")
    if spatial.get("status") == "AVAILABLE" and spatial["bbox_dx"] < 2.0 and spatial["bbox_dy"] < 2.0:
        labels.append("LOW_SPATIAL_DISPLACEMENT")
    if key_counts and key_counts.most_common(1)[0][1] / max(1, len(top_keys)) >= 0.5:
        labels.append("REPEATED_CONTINUATION")
    if best >= 20:
        labels.append("ACTION_STATE_RECURRENCE")
    return {
        "status": "AVAILABLE",
        "window": n,
        "wait_fraction": wait_n / max(1, n),
        "move_fraction": move_n / max(1, n),
        "longest_wait_run": best,
        "action_counts": dict(Counter(actions)),
        "spatial": spatial,
        "top_continuation_edge_keys": key_counts.most_common(5),
        "labels": labels,
        "scope": "OBSERVER_DIAGNOSTIC_ONLY",
    }


def wrap_aware_segments(
    positions: list[dict[str, float]], *, width: int, height: int, jump_frac: float = 0.5
) -> list[list[dict[str, float]]]:
    """Split trajectory at periodic jumps so lines do not cross the map."""
    if not positions:
        return []
    segs: list[list[dict[str, float]]] = [[positions[0]]]
    for i in range(1, len(positions)):
        p0, p1 = positions[i - 1], positions[i]
        if abs(p1["x"] - p0["x"]) > width * jump_frac or abs(p1["y"] - p0["y"]) > height * jump_frac:
            segs.append([p1])
        else:
            segs[-1].append(p1)
    return segs


def occupancy_grid(
    positions: list[dict[str, float]], *, width: int, height: int
) -> list[list[int]]:
    g = [[0 for _ in range(width)] for _ in range(height)]
    for p in positions:
        ix = int(np.floor(p["x"])) % width
        iy = int(np.floor(p["y"])) % height
        g[iy][ix] += 1
    return g


def human_summary(loop: dict[str, Any], receipts: list[dict[str, Any]]) -> str:
    if loop.get("status") != "AVAILABLE":
        return "Insufficient ActionDecisionReceipt samples for summary."
    n = int(loop["window"])
    wait_n = int(round(loop["wait_fraction"] * n))
    lines = [
        f"body-0 selected WAIT for {wait_n} of the last {n} recorded decisions "
        f"(wait_fraction={loop['wait_fraction']:.3f}).",
        f"Longest WAIT run={loop['longest_wait_run']}. MOVE fraction={loop['move_fraction']:.3f}.",
    ]
    keys = loop.get("top_continuation_edge_keys") or []
    if keys:
        top_k, top_c = keys[0]
        lines.append(
            f"Most frequent top-continuation edge key={top_k!r} on {top_c}/{sum(c for _, c in keys)} sampled WAIT-path receipts."
        )
    # peer evaluation fact from latest receipt
    if receipts:
        sel = (receipts[-1].get("selection") or {})
        lines.append(f"Selection rule: {sel.get('selection_rule')}")
        lines.append(f"Peer evaluation: {sel.get('peer_evaluation')}")
        # MOVE support at last tick
        move_rows = [c for c in receipts[-1].get("candidates") or [] if str(c.get("candidate", "")).startswith("MOVE")]
        supported = [c for c in move_rows if c.get("prospective_root_count", 0) > 0 or (c.get("compression_match") or {}).get("status") not in {None, "NO_MATCH", "UNKNOWN", "ABLATION"}]
        if not supported:
            lines.append("On the latest sampled tick, MOVE candidates were listed but had no prospective-root continuation and no compression match.")
        else:
            lines.append(
                f"On the latest sampled tick, {len(supported)} MOVE candidate(s) had some prospective/compression evidence but were not selected under the top-continuation-first-action rule."
            )
    spat = loop.get("spatial") or {}
    if spat.get("status") == "AVAILABLE":
        lines.append(
            f"Spatial window: bbox=({spat['bbox_dx']:.3f},{spat['bbox_dy']:.3f}), "
            f"unique_cells={spat['unique_cells']}, radius_of_gyration={spat['radius_of_gyration']:.3f}."
        )
    if loop.get("labels"):
        lines.append("Observer labels: " + ", ".join(loop["labels"]) + " (diagnostic only).")
    return "\n".join(lines)


class DecisionTraceBuffer:
    def __init__(self, capacity: int = 256) -> None:
        self.capacity = capacity
        self.receipts: deque[dict[str, Any]] = deque(maxlen=capacity)
        self.positions: deque[dict[str, Any]] = deque(maxlen=max(capacity * 4, 1024))

    def add_receipt(self, receipt: dict[str, Any]) -> None:
        self.receipts.append(receipt)

    def add_position(self, *, tick: int, x: float, y: float, action: str | None) -> None:
        self.positions.append({"tick": tick, "x": float(x), "y": float(y), "action": action})

    def as_lists(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return list(self.receipts), list(self.positions)
