"""Update 4.23 — Bounded prospective trajectory composition (label-free).

Compose independently learned action-conditioned transitions into predicted
continuations. No GOAL/PLAN/TARGET/REWARD semantics. No world-engine lookahead.
World future must never enter cognition.

Researcher may describe prospective trajectories; psyche must not receive
planning category tokens.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
from typing import Any


MAX_TRANSITIONS = 128
MAX_WORKSPACE = 32
MAX_DEPTH = 8
MAX_BRANCH = 4
MAX_EXPANSIONS = 64
MIN_SUPPORT = 3
MATCH_TOL = 0.12  # interface compatibility on quantized channels

FORBIDDEN = (
    "GOAL", "GOAL_STATE", "TARGET", "TARGET_STATE", "PLAN", "PLANNER", "STRATEGY",
    "INTENTION", "PURPOSE", "DREAM", "AMBITION", "SUCCESS", "FAILURE", "FUTURE_SELF",
    "DESIRED_FUTURE", "WANTED_STATE", "SUBGOAL", "MILESTONE", "PROGRESS",
    "DISTANCE_TO_GOAL", "BEST_PATH", "OPTIMAL_PATH", "SACRIFICE", "LONG_TERM_REWARD",
    "DELAYED_REWARD_BONUS", "REPLAN", "SHOULD_CONTINUE", "GIVE_UP", "MEANS_TO_AN_END",
    "LOOKAHEAD_REWARD", "FUTURE_VALUE_BONUS", "PATH_COST", "SAFE_PATH", "RISKY_PATH",
    "STATE_ID", "NODE_ID", "PATH_ID", "DESTINATION_ID", "WORLD_CHANGED", "PATH_INVALID",
    "PLAN_FAILED", "REPLAN_NOW", "INFORMATION_GAIN", "CURIOSITY", "NOVELTY_REWARD",
    "EXPLORE_BONUS", "PREDICTION_ERROR_REWARD", "UNCERTAINTY_REDUCTION_REWARD",
)


# Same-tick / same-payload signature reuse (identical digest; bounded map).
_SIG_CACHE: dict[tuple[tuple[str, Any], ...], str] = {}
_SIG_CACHE_MAX = 8192


def _sig(payload: dict[str, Any]) -> str:
    items = tuple(
        sorted(
            (
                str(k),
                round(float(v), 4) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v),
            )
            for k, v in payload.items()
        )
    )
    hit = _SIG_CACHE.get(items)
    if hit is not None:
        return hit
    digest = sha1("|".join(f"{k}:{v}" for k, v in items).encode()).hexdigest()[:12]
    if len(_SIG_CACHE) >= _SIG_CACHE_MAX:
        _SIG_CACHE.clear()
    _SIG_CACHE[items] = digest
    return digest


def _q(fragment: dict[str, float], bins: int = 5) -> dict[str, float]:
    out = {}
    for k, v in fragment.items():
        q = int(max(0.0, min(0.999999, float(v))) * bins)
        out[str(k)] = (q + 0.5) / bins
    return out


def audit_forbidden(payload: Any) -> list[str]:
    text = str(payload)
    return [t for t in FORBIDDEN if t in text]


def empty_store() -> dict[str, Any]:
    return {
        "transitions": {},  # key -> stats
        "exposure_log": [],  # researcher audit of experienced sequences (bounded)
        "exposure_capacity": 256,
        "full_sequence_patterns": {},  # researcher-side complete chain counts
        "ticks": 0,
        "ablate_composition": False,
        "ablate_relations": False,  # filter co-action interface soft boost
        "ablate_broader": False,
        "ablate_distal_influence": False,
        "metrics_affect_cognition": False,
        "relation_boost_ids": set(),  # optional soft interface from 4.20
        "broader_member_ids": set(),  # optional soft from 4.22
        "next_tid": 1,
        "revision_count": 0,
    }


def transition_key(antecedent: dict[str, float], action: str) -> str:
    return f"{_sig(_q(antecedent))}||{action}"


def learn_transition(
    store: dict[str, Any],
    *,
    tick: int,
    antecedent: dict[str, float],
    action: str,
    consequent: dict[str, float],
    reliability_weight: float = 1.0,
) -> str:
    """Learn one action-conditioned transition from ordinary experience."""
    from mechanistic_mind.research.psc_opt import bump_pack_version, invalidate_row_caches

    store["ticks"] = int(tick)
    ant = _q(antecedent)
    cons = _q(consequent)
    key = transition_key(ant, action)
    tr = store.setdefault("transitions", {})
    row = tr.get(key)
    if row is None:
        if len(tr) >= MAX_TRANSITIONS:
            victim = min(tr.items(), key=lambda kv: int(kv[1].get("support") or 0))[0]
            del tr[victim]
        tid = f"T{int(store.get('next_tid') or 1)}"
        store["next_tid"] = int(store.get("next_tid") or 1) + 1
        row = {
            "transition_id": tid,
            "key": key,
            "action": action,
            "antecedent": ant,
            "sum": {k: 0.0 for k in cons},
            "n": 0.0,
            "support": 0,
            "var_sum": {k: 0.0 for k in cons},
            "evidence_ticks": [],
        }
        tr[key] = row
    w = float(reliability_weight)
    n = float(row["n"]) + w
    for k, v in cons.items():
        prev = float(row["sum"].get(k, 0.0))
        # Welford-ish for variance tracking
        mean_old = prev / max(row["n"], 1e-9) if row["n"] else float(v)
        row["sum"][k] = prev + w * float(v)
        mean_new = row["sum"][k] / n
        row["var_sum"][k] = float(row["var_sum"].get(k, 0.0)) + w * (float(v) - mean_old) * (float(v) - mean_new)
    row["n"] = n
    row["support"] = int(row["support"]) + 1
    ev = row.setdefault("evidence_ticks", [])
    ev.append(tick)
    row["evidence_ticks"] = ev[-24:]
    invalidate_row_caches(row)
    bump_pack_version(store)

    # exposure audit: append single-step and maintain rolling episode for full-seq audit
    elog = store.setdefault("exposure_log", [])
    elog.append({"tick": tick, "action": action, "ant": ant, "cons": cons, "key": key})
    store["exposure_log"] = elog[-int(store.get("exposure_capacity") or 256):]
    return row["transition_id"]


def mean_cons(row: dict[str, Any]) -> dict[str, float]:
    n = max(1e-9, float(row.get("n") or 1.0))
    return {k: float(v) / n for k, v in (row.get("sum") or {}).items()}


def reliability(row: dict[str, Any]) -> float:
    n = max(1e-9, float(row.get("n") or 1.0))
    if n < 2:
        return 0.5
    # average channel std
    vars_ = []
    for k, vs in (row.get("var_sum") or {}).items():
        vars_.append(max(0.0, float(vs) / max(n - 1.0, 1e-9)))
    if not vars_:
        return 0.5
    import math
    std = sum(math.sqrt(v) for v in vars_) / len(vars_)
    return float(max(0.0, min(1.0, 1.0 - std)))


def predict_one_step(
    store: dict[str, Any],
    antecedent: dict[str, float],
    action: str,
    *,
    backend: str | None = None,
    _ant_q: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Action-conditioned one-step retrieval / soft match.

    ``backend`` / ``MM_PSC_BACKEND`` selects implementation only:
    ``legacy`` | ``packed`` | ``numba``. Semantics must EXACT_MATCH.

    ``_ant_q``: optional precomputed ``_q(antecedent)`` (same tick reuse).
    """
    from mechanistic_mind.research.psc_opt import (
        ensure_pack,
        mean_cons_cached,
        reliability_cached,
        resolve_backend,
        soft_match_legacy,
        soft_match_numba,
        soft_match_packed,
    )

    ant = _ant_q if _ant_q is not None else _q(antecedent)
    key = f"{_sig(ant)}||{action}"
    transitions = store.get("transitions") or {}
    row = transitions.get(key)
    if not row or int(row.get("support") or 0) < MIN_SUPPORT:
        mode = resolve_backend(backend)
        if mode == "legacy":
            best, best_d = soft_match_legacy(transitions, ant, action)
        else:
            pack = ensure_pack(store)
            if mode == "numba":
                best, best_d = soft_match_numba(pack, ant, action)
            else:
                best, best_d = soft_match_packed(pack, ant, action)
        if best is None or best_d > MATCH_TOL:
            return {"status": "NO_MATCH", "action": action, "key": key}
        row = best
        key = row["key"]
    return {
        "status": "MATCH",
        "action": action,
        "key": key,
        "transition_id": row["transition_id"],
        "predicted": dict(mean_cons_cached(row)),
        "support": row["support"],
        "reliability": reliability_cached(row),
        "depth": 1,
    }


def _frag_distance(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    return sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys) / len(keys)


def _compatible(pred: dict[str, float], ante: dict[str, float]) -> bool:
    return _frag_distance(_q(pred), _q(ante)) <= MATCH_TOL


def compose_trajectories(
    store: dict[str, Any],
    *,
    start: dict[str, float],
    actions_horizon: list[str] | None = None,
    max_depth: int = 3,
    branch_actions: list[str] | None = None,
    entry_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Bounded BFS composition over learned transitions only.

    If ablate_composition: only return one-step predictions (no chaining).

    `entry_steps` is an optional list of already-MATCH first-step edges
    (adapter/bridge). They seed additional roots; they do not replace snapshot
    `predict_one_step` lookup and are not written into the transition store.
    """
    max_depth = min(int(max_depth), MAX_DEPTH)
    branch_actions = list(branch_actions or ["WAIT", "A1", "A2", "A3"])
    expansions = 0
    workspace: list[dict[str, Any]] = []

    # seed: one-step from start for each action (snapshot-conditioned)
    roots = []
    start_q = _q(start)
    for act in branch_actions:
        if expansions >= MAX_EXPANSIONS:
            break
        step = predict_one_step(store, start, act, _ant_q=start_q)
        expansions += 1
        if step.get("status") != "MATCH":
            continue
        snap = dict(step)
        snap.setdefault("prediction_source", "SNAPSHOT")
        node = {
            "actions": [act],
            "states": [dict(start), dict(snap["predicted"])],
            "edges": [snap],
            "depth": 1,
            "score_reliability": float(snap.get("reliability") or 0.5),
            "prediction_source": "SNAPSHOT",
        }
        roots.append(node)
        workspace.append(node)

    # optional bridged first steps (already predicted; not new 4.23 learning)
    for step in entry_steps or []:
        if expansions >= MAX_EXPANSIONS:
            break
        if step.get("status") != "MATCH":
            continue
        pred = step.get("predicted") or {}
        if not pred:
            continue
        act = str(step.get("action") or "")
        if not act:
            continue
        expansions += 1
        rel = step.get("reliability")
        node = {
            "actions": [act],
            "states": [dict(start), dict(pred)],
            "edges": [dict(step)],
            "depth": 1,
            "score_reliability": float(rel) if rel is not None else 0.0,
            "prediction_source": step.get("prediction_source") or "TEMPORAL",
        }
        roots.append(node)
        workspace.append(node)

    if store.get("ablate_composition"):
        workspace.sort(key=lambda n: (-n["score_reliability"], n["actions"][0]))
        return {
            "continuations": workspace[:MAX_BRANCH],
            "expansion_count": expansions,
            "workspace_peak": len(workspace),
            "composition_enabled": False,
            "max_depth_reached": 1 if workspace else 0,
        }

    # expand
    frontier = list(roots)
    depth_reached = 1 if frontier else 0
    while frontier and expansions < MAX_EXPANSIONS:
        cur = frontier.pop(0)
        if cur["depth"] >= max_depth:
            continue
        if len(workspace) >= MAX_WORKSPACE:
            break
        last = cur["states"][-1]
        last_q = _q(last)
        # prefer continuing with specified horizon actions if provided
        next_acts = list(branch_actions)
        if actions_horizon and cur["depth"] < len(actions_horizon):
            # put suggested next action first but still allow alternatives
            sug = actions_horizon[cur["depth"]]
            next_acts = [sug] + [a for a in next_acts if a != sug]
        branched = 0
        for act in next_acts:
            if branched >= MAX_BRANCH or expansions >= MAX_EXPANSIONS:
                break
            expansions += 1
            step = predict_one_step(store, last, act, _ant_q=last_q)
            if step.get("status") != "MATCH":
                continue
            # interface: predicted previous consequent should match this transition's antecedent
            row = (store.get("transitions") or {}).get(step["key"])
            if row is None:
                continue
            if not _compatible(last, row.get("antecedent") or {}):
                continue
            # optional soft filters (not required)
            if store.get("ablate_relations"):
                pass  # relations already not required for edge match
            child = {
                "actions": cur["actions"] + [act],
                "states": cur["states"] + [dict(step["predicted"])],
                "edges": cur["edges"] + [step],
                "depth": cur["depth"] + 1,
                "score_reliability": cur["score_reliability"] * float(step.get("reliability") or 0.5),
                "prediction_source": cur.get("prediction_source") or "SNAPSHOT",
            }
            workspace.append(child)
            frontier.append(child)
            branched += 1
            depth_reached = max(depth_reached, child["depth"])

    # rank by depth then reliability (researcher order; not a GOAL score)
    workspace.sort(key=lambda n: (-n["depth"], -n["score_reliability"]))
    # keep diverse top continuations
    kept = workspace[:MAX_WORKSPACE]
    return {
        "continuations": kept[: max(MAX_BRANCH * 2, 8)],
        "expansion_count": expansions,
        "workspace_peak": len(workspace),
        "composition_enabled": True,
        "max_depth_reached": depth_reached,
        "leak_tokens": audit_forbidden(kept[:5]),
    }


def distal_prediction(
    store: dict[str, Any],
    *,
    start: dict[str, float],
    action_seq: list[str],
) -> dict[str, Any]:
    """Compose along a specific action sequence using learned edges only."""
    if store.get("ablate_composition") and len(action_seq) > 1:
        # only first step
        one = predict_one_step(store, start, action_seq[0])
        return {
            "status": one.get("status"),
            "depth": 1 if one.get("status") == "MATCH" else 0,
            "predicted_distal": one.get("predicted"),
            "path": [one] if one.get("status") == "MATCH" else [],
            "composition_ablated": True,
        }
    cur = dict(start)
    path = []
    for act in action_seq:
        step = predict_one_step(store, cur, act)
        if step.get("status") != "MATCH":
            return {
                "status": "BROKEN",
                "depth": len(path),
                "predicted_distal": cur if path else None,
                "path": path,
                "failed_action": act,
            }
        row = (store.get("transitions") or {}).get(step["key"])
        if row and path and not _compatible(cur, row.get("antecedent") or {}):
            return {
                "status": "INCOMPATIBLE",
                "depth": len(path),
                "predicted_distal": cur,
                "path": path,
                "failed_action": act,
            }
        path.append(step)
        cur = dict(step["predicted"])
    return {
        "status": "COMPOSED",
        "depth": len(path),
        "predicted_distal": cur,
        "path": path,
        "composition_ablated": False,
    }


def record_full_sequence_exposure(
    store: dict[str, Any],
    *,
    pattern_id: str,
    experienced: bool,
) -> None:
    """Researcher-side audit helper for complete chain exposure."""
    fs = store.setdefault("full_sequence_patterns", {})
    row = fs.setdefault(pattern_id, {"count": 0, "ticks": []})
    if experienced:
        row["count"] = int(row["count"]) + 1


def count_component_exposures(store: dict[str, Any], component_keys: list[str]) -> dict[str, int]:
    counts = {k: 0 for k in component_keys}
    for e in store.get("exposure_log") or []:
        k = e.get("key")
        if k in counts:
            counts[k] += 1
    return counts


def revise_transition(
    store: dict[str, Any],
    *,
    tick: int,
    antecedent: dict[str, float],
    action: str,
    consequent: dict[str, float],
) -> dict[str, Any]:
    """Ordinary evidence update after silent world change — not REPLAN."""
    tid = learn_transition(store, tick=tick, antecedent=antecedent, action=action, consequent=consequent)
    store["revision_count"] = int(store.get("revision_count") or 0) + 1
    return {"transition_id": tid, "revision_count": store["revision_count"]}


def snapshot(store: dict[str, Any]) -> dict[str, Any]:
    tr = store.get("transitions") or {}
    return {
        "component_transition_count": len(tr),
        "revision_count": store.get("revision_count"),
        "ablations": {
            "composition": bool(store.get("ablate_composition")),
            "relations": bool(store.get("ablate_relations")),
            "broader": bool(store.get("ablate_broader")),
            "distal_influence": bool(store.get("ablate_distal_influence")),
        },
        "full_sequence_patterns": deepcopy(store.get("full_sequence_patterns") or {}),
        "leak_tokens": audit_forbidden(list(tr.keys())[:20]),
        "metrics_affect_cognition": bool(store.get("metrics_affect_cognition")),
        "bounds": {
            "MAX_TRANSITIONS": MAX_TRANSITIONS,
            "MAX_WORKSPACE": MAX_WORKSPACE,
            "MAX_DEPTH": MAX_DEPTH,
            "MAX_BRANCH": MAX_BRANCH,
            "MAX_EXPANSIONS": MAX_EXPANSIONS,
        },
    }


def provenance_graph(result: dict[str, Any]) -> dict[str, Any]:
    """Researcher-only graph of composed edges."""
    path = result.get("path") or []
    nodes = []
    for i, step in enumerate(path):
        nodes.append({
            "depth": i + 1,
            "action": step.get("action"),
            "transition_id": step.get("transition_id"),
            "key": step.get("key"),
            "support": step.get("support"),
            "reliability": step.get("reliability"),
            "predicted": step.get("predicted"),
        })
    return {"RESEARCHER_ONLY": True, "edges": nodes, "status": result.get("status")}


def l1(a: dict[str, float] | None, b: dict[str, float] | None) -> float | None:
    if not a or not b:
        return None
    keys = set(a) | set(b)
    return sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys)
