"""Update 4.12 — bounded shadow transition composition.

Compose independently acquired prospective transitions:
  Ŝ1 = F(S0, A, L)
  Ŝ2 = F(Ŝ1, B, L)   # B conditioned on predicted Ŝ1, not S0

Shadow only. No ranking, search, gamma, or policy integration.
Provenance: DIRECT | COMPOSED | UNKNOWN
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.psyche.temporal_contingency import (
    coarse_body_state_key,
    ensure_temporal,
    normalize_action,
    predicted_organism_state,
    predictions_by_lag_for_action,
    retrieve_temporal,
)


def _signals(d: dict[str, Any] | None) -> dict[str, float]:
    if not isinstance(d, dict):
        return {}
    return {
        str(k): float(v)
        for k, v in d.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def _pick_lag_record(
    hits: list[dict[str, Any]],
    action: str,
    lag: int,
    *,
    require_exact_state: bool = False,
) -> dict[str, Any] | None:
    by = predictions_by_lag_for_action(hits, action, lags=(lag,))
    rec = by.get(int(lag))
    if rec is None:
        return None
    if require_exact_state and rec.get("_state_match") not in ("EXACT", "UNCONDITIONAL", "LEGACY"):
        # OTHER_STATE alone is not enough when we demand compatibility
        if rec.get("_state_match") == "OTHER_STATE":
            return None
    return rec


def apply_transition(
    *,
    tc: dict[str, Any],
    current_signals: dict[str, float],
    action: str,
    bucket: str,
    lag: int,
    available_actions: set[str],
    min_support: float = 3.0,
    state_conditioning: bool = True,
    require_exact_state: bool = True,
) -> dict[str, Any]:
    """One acquired transition F(S, A, L) → predicted state (or UNKNOWN)."""
    cur = _signals(current_signals)
    state_key = coarse_body_state_key(cur, from_interoception=False)
    avail = set(available_actions) | {normalize_action(action), "WAIT"}
    hits = retrieve_temporal(
        tc,
        bucket=bucket,
        available_actions=avail,
        action_conditioning=True,
        context_conditioning=True,
        min_support=min_support,
        state_key=state_key if state_conditioning else None,
        state_conditioning=state_conditioning,
    )
    rec = _pick_lag_record(
        hits, action, lag, require_exact_state=require_exact_state and state_conditioning
    )
    if rec is None:
        return {
            "status": "UNKNOWN",
            "provenance": "UNKNOWN",
            "reason": "NO_COMPATIBLE_TRANSITION",
            "action": normalize_action(action),
            "lag": int(lag),
            "input_state_key": state_key,
            "input_signals": cur,
            "predicted_state": None,
            "mean_body_delta": None,
            "support": 0.0,
            "confidence": 0.0,
            "state_match": None,
        }
    # Allow UNKNOWN epistemic status if support exists — composition uses evidence presence;
    # specificity gate may mark UNKNOWN while deltas remain. Prefer KNOWN/WEAK when available.
    delta = rec.get("mean_body_delta") or {}
    if not delta:
        return {
            "status": "UNKNOWN",
            "provenance": "UNKNOWN",
            "reason": "EMPTY_DELTA",
            "action": normalize_action(action),
            "lag": int(lag),
            "input_state_key": state_key,
            "input_signals": cur,
            "predicted_state": None,
            "mean_body_delta": None,
            "support": float(rec.get("support") or 0),
            "confidence": float(rec.get("confidence") or 0),
            "state_match": rec.get("_state_match"),
        }
    if float(rec.get("support") or 0) < float(min_support):
        return {
            "status": "UNKNOWN",
            "provenance": "UNKNOWN",
            "reason": "INSUFFICIENT_SUPPORT",
            "action": normalize_action(action),
            "lag": int(lag),
            "input_state_key": state_key,
            "input_signals": cur,
            "predicted_state": None,
            "mean_body_delta": delta,
            "support": float(rec.get("support") or 0),
            "confidence": float(rec.get("confidence") or 0),
            "state_match": rec.get("_state_match"),
        }
    pred = predicted_organism_state(cur, delta)
    out_key = coarse_body_state_key(pred or {}, from_interoception=False)
    return {
        "status": "OK",
        "provenance": "DIRECT",  # caller may rewrite to COMPOSED
        "reason": "ACQUIRED_TRANSITION",
        "action": normalize_action(action),
        "lag": int(lag),
        "input_state_key": state_key,
        "input_signals": cur,
        "predicted_state": pred,
        "predicted_state_key": out_key,
        "mean_body_delta": delta,
        "support": float(rec.get("support") or 0),
        "confidence": float(rec.get("confidence") or 0),
        "epistemic_record_status": rec.get("status"),
        "state_match": rec.get("_state_match"),
        "key": rec.get("key"),
        "record_state_key": rec.get("state_key"),
    }


def compose_two_step(
    *,
    tc: dict[str, Any],
    s0_signals: dict[str, float],
    action_a: str,
    action_b: str,
    bucket: str,
    lag_a: int = 1,
    lag_b: int = 1,
    available_actions: set[str] | None = None,
    min_support: float = 3.0,
    require_exact_state: bool = True,
) -> dict[str, Any]:
    """S0 --A/LA--> Ŝ1 --B/LB--> Ŝ2 with B conditioned on Ŝ1 (not S0)."""
    avail = set(available_actions or set()) | {"WAIT", normalize_action(action_a), normalize_action(action_b)}
    first = apply_transition(
        tc=tc,
        current_signals=s0_signals,
        action=action_a,
        bucket=bucket,
        lag=lag_a,
        available_actions=avail,
        min_support=min_support,
        require_exact_state=require_exact_state,
    )
    first["provenance"] = "DIRECT" if first.get("status") == "OK" else "UNKNOWN"
    if first.get("status") != "OK" or not first.get("predicted_state"):
        return {
            "status": "UNKNOWN",
            "composition": "UNKNOWN",
            "reason": "FIRST_TRANSITION_FAILED",
            "edge_a": first,
            "edge_b": {
                "status": "UNKNOWN",
                "provenance": "UNKNOWN",
                "reason": "NO_INTERMEDIATE",
            },
            "s0_state_key": coarse_body_state_key(s0_signals, from_interoception=False),
            "s_hat_1": None,
            "s_hat_2": None,
            "total_duration": None,
        }
    s1 = first["predicted_state"]
    # Critical: second transition from predicted intermediate, not S0
    second = apply_transition(
        tc=tc,
        current_signals=s1,
        action=action_b,
        bucket=bucket,
        lag=lag_b,
        available_actions=avail,
        min_support=min_support,
        require_exact_state=require_exact_state,
    )
    if second.get("status") != "OK":
        second["provenance"] = "UNKNOWN"
        return {
            "status": "UNKNOWN",
            "composition": "UNKNOWN",
            "reason": second.get("reason") or "SECOND_TRANSITION_FAILED",
            "edge_a": first,
            "edge_b": second,
            "s0_state_key": first["input_state_key"],
            "s_hat_1": s1,
            "s_hat_1_key": first.get("predicted_state_key"),
            "s_hat_2": None,
            "total_duration": int(lag_a),  # only first hop realized in prediction
        }
    second["provenance"] = "COMPOSED"
    return {
        "status": "OK",
        "composition": "COMPOSED",
        "reason": "TWO_STEP_COMPOSITION",
        "edge_a": first,
        "edge_b": second,
        "s0_state_key": first["input_state_key"],
        "s_hat_1": s1,
        "s_hat_1_key": first.get("predicted_state_key"),
        "s_hat_2": second.get("predicted_state"),
        "s_hat_2_key": second.get("predicted_state_key"),
        "total_duration": int(lag_a) + int(lag_b),
        "note": "B conditioned on predicted Ŝ1; not prediction(A|S0)+prediction(B|S0)",
    }


def depth1_branches(
    *,
    tc: dict[str, Any],
    s0_signals: dict[str, float],
    actions: list[str],
    bucket: str,
    lag: int = 1,
    min_support: float = 3.0,
) -> dict[str, Any]:
    out = {}
    for a in actions:
        out[a] = apply_transition(
            tc=tc,
            current_signals=s0_signals,
            action=a,
            bucket=bucket,
            lag=lag,
            available_actions=set(actions),
            min_support=min_support,
        )
    return out


def depth2_tree(
    *,
    tc: dict[str, Any],
    s0_signals: dict[str, float],
    actions: list[str],
    bucket: str,
    lag: int = 1,
    min_support: float = 3.0,
) -> dict[str, Any]:
    """Visualization only — no ranking."""
    tree = {"S0": coarse_body_state_key(s0_signals, from_interoception=False), "branches": {}}
    counts = {"DIRECT": 0, "COMPOSABLE": 0, "UNKNOWN": 0}
    for a in actions:
        e1 = apply_transition(
            tc=tc,
            current_signals=s0_signals,
            action=a,
            bucket=bucket,
            lag=lag,
            available_actions=set(actions),
            min_support=min_support,
        )
        node = {"edge": e1, "continuations": {}}
        if e1.get("status") == "OK":
            counts["DIRECT"] += 1
            for b in actions:
                e2 = apply_transition(
                    tc=tc,
                    current_signals=e1["predicted_state"],
                    action=b,
                    bucket=bucket,
                    lag=lag,
                    available_actions=set(actions),
                    min_support=min_support,
                )
                if e2.get("status") == "OK":
                    e2 = dict(e2)
                    e2["provenance"] = "COMPOSED"
                    counts["COMPOSABLE"] += 1
                else:
                    e2 = dict(e2)
                    e2["provenance"] = "UNKNOWN"
                    counts["UNKNOWN"] += 1
                node["continuations"][b] = e2
        else:
            counts["UNKNOWN"] += 1
        tree["branches"][a] = node
    tree["counts"] = counts
    return tree


def ablate_action_evidence(tc: dict[str, Any], action_prefix: str) -> dict[str, Any]:
    """Return a deepcopy of tc with contingencies for action removed (control)."""
    out = deepcopy(tc)
    cont = out.get("contingencies") or {}
    drop = [
        k
        for k, v in cont.items()
        if isinstance(v, dict)
        and (
            str(v.get("action")) == action_prefix
            or str(v.get("action", "")).startswith(action_prefix)
        )
    ]
    for k in drop:
        cont.pop(k, None)
    out["contingencies"] = cont
    return out


def shuffle_state_keys(tc: dict[str, Any], remap: dict[str, str]) -> dict[str, Any]:
    """Disrupt intermediate-state compatibility by remapping record state_keys."""
    out = deepcopy(tc)
    cont = out.get("contingencies") or {}
    new_cont = {}
    for k, v in cont.items():
        if not isinstance(v, dict):
            continue
        vv = dict(v)
        old = str(vv.get("state_key") or "")
        if old in remap:
            vv["state_key"] = remap[old]
        # rebuild key string loosely
        new_cont[k + "|SHUF"] = vv
    out["contingencies"] = new_cont
    # wipe index — retrieve will scan contingencies
    out["index"] = {}
    return out


def compose_from_consequence_branches(
    *,
    tc: dict[str, Any],
    s0_signals: dict[str, float],
    action_a: str,
    action_b: str,
    bucket: str,
    key_a: str,
    lag_a: int = 1,
    lag_b: int = 1,
    available_actions: set[str] | None = None,
    min_support: float = 3.0,
) -> dict[str, Any]:
    """Continue action_b independently from each supported consequence of action_a.

    Outcome branches of one action — not ranking / policy.
    """
    from mechanistic_mind.research.multiple_consequences import prospective_consequences

    pack = prospective_consequences(
        tc=tc, key=key_a, current_signals=s0_signals, min_support=min_support
    )
    branches = []
    for cons in pack.get("consequences") or []:
        s1 = cons.get("predicted_state")
        if not isinstance(s1, dict):
            branches.append({
                "consequence_id": cons.get("id"),
                "status": "UNKNOWN",
                "reason": "NO_PREDICTED_STATE",
                "edge_a_consequence": cons,
                "edge_b": None,
            })
            continue
        second = apply_transition(
            tc=tc,
            current_signals=s1,
            action=action_b,
            bucket=bucket,
            lag=lag_b,
            available_actions=set(available_actions or set()) | {"WAIT", normalize_action(action_a), normalize_action(action_b)},
            min_support=min_support,
        )
        second["provenance"] = "COMPOSED" if second.get("status") == "OK" else "UNKNOWN"
        branches.append({
            "consequence_id": cons.get("id"),
            "status": "OK" if second.get("status") == "OK" else "UNKNOWN",
            "support_a": cons.get("support"),
            "s_hat_1": s1,
            "s_hat_1_key": coarse_body_state_key(s1, from_interoception=False),
            "edge_b": second,
            "s_hat_2": second.get("predicted_state"),
            "s_hat_2_key": second.get("predicted_state_key"),
        })
    return {
        "action_a": normalize_action(action_a),
        "action_b": normalize_action(action_b),
        "n_branches": len(branches),
        "parent_status": pack.get("status"),
        "branches": branches,
        "note": "consequence branching — not action ranking",
    }
