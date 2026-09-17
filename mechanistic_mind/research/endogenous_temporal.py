"""Update 4.24 - Body as endogenous temporal reference (no clock semantics).

Temporal prediction may use ordinary bodily/environmental fragments and their
trajectories. Cognition must not receive CLOCK/ELAPSED_TIME/AGE/TIME_SENSE.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
from typing import Any

from mechanistic_mind.body.persistent_processes import (
    PROCESS_KEYS,
    advance_persistent_processes,
    default_process_config,
    ensure_process_state,
)

MAX_LOCAL = 96
MAX_TRAJ = 64
TRAJ_LEN = 4  # recent body observations used as trajectory evidence
MIN_SUPPORT = 3
MATCH_TOL = 0.08

FORBIDDEN = (
    "CLOCK", "INTERNAL_CLOCK", "ELAPSED_TIME", "AGE", "TIME_SENSE", "BODY_CLOCK",
    "TIME_ESTIMATE", "TEMPORAL_POSITION", "DURATION", "SUBJECTIVE_TIME",
)


def _sig(payload: dict[str, Any]) -> str:
    items = sorted(
        (str(k), round(float(v), 4) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v))
        for k, v in payload.items()
    )
    return sha1("|".join(f"{k}:{v}" for k, v in items).encode()).hexdigest()[:12]


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
        "state_pred": {},      # current body -> next body
        "traj_pred": {},       # trajectory sig + action -> next body
        "recent_body": [],     # ring of body fragments (agent-accessible)
        "ticks_sim": 0,        # researcher only - never used as cognition feature
        "ablate_trajectory": False,
        "ablate_body": False,
        "metrics_affect_cognition": False,
        "next_id": 1,
    }


def body_fragment(loads: dict[str, float], *, sensory_keys: list[str] | None = None) -> dict[str, float]:
    keys = sensory_keys or list(PROCESS_KEYS)
    return {k: float(loads.get(k, 0.0)) for k in keys}


def traj_sig(recent: list[dict[str, float]]) -> str:
    # Concatenate quantized recent body observations - not a clock.
    parts = []
    for frag in recent[-TRAJ_LEN:]:
        parts.append(_sig(_q(frag)))
    return "TR|" + "|".join(parts)


def learn(
    store: dict[str, Any],
    *,
    body_now: dict[str, float],
    body_next: dict[str, float],
    action: str = "WAIT",
    env_frag: dict[str, float] | None = None,
) -> None:
    if store.get("ablate_body"):
        return
    store["ticks_sim"] = int(store.get("ticks_sim") or 0) + 1
    recent = store.setdefault("recent_body", [])
    # learn from previous recent -> using body_now as current before append? 
    # Protocol: caller passes body_now (pre-step), body_next (post-step).
    # Trajectory uses recent BEFORE appending current.
    prior_recent = list(recent[-TRAJ_LEN:])
    bn = _q(body_now)
    bx = _q(body_next)

    # state-only
    sk = f"{_sig(bn)}||{action}"
    sp = store.setdefault("state_pred", {})
    row = sp.get(sk)
    if row is None:
        if len(sp) >= MAX_LOCAL:
            victim = min(sp.items(), key=lambda kv: int(kv[1].get("support") or 0))[0]
            del sp[victim]
        row = {"sum": {k: 0.0 for k in bx}, "n": 0, "support": 0, "key": sk}
        sp[sk] = row
    for k, v in bx.items():
        row["sum"][k] = float(row["sum"].get(k, 0.0)) + float(v)
    row["n"] = int(row["n"]) + 1
    row["support"] = int(row["support"]) + 1

    # trajectory-conditioned (if we have enough history)
    if not store.get("ablate_trajectory") and len(prior_recent) >= 1:
        # trajectory = prior_recent + current body_now
        traj = prior_recent + [bn]
        tk = f"{traj_sig(traj)}||{action}"
        tp = store.setdefault("traj_pred", {})
        trow = tp.get(tk)
        if trow is None:
            if len(tp) >= MAX_TRAJ:
                victim = min(tp.items(), key=lambda kv: int(kv[1].get("support") or 0))[0]
                del tp[victim]
            trow = {"sum": {k: 0.0 for k in bx}, "n": 0, "support": 0, "key": tk,
                    "traj_len": len(traj)}
            tp[tk] = trow
        for k, v in bx.items():
            trow["sum"][k] = float(trow["sum"].get(k, 0.0)) + float(v)
        trow["n"] = int(trow["n"]) + 1
        trow["support"] = int(trow["support"]) + 1

    recent.append(bn)
    store["recent_body"] = recent[-32:]


def _mean(row: dict[str, Any]) -> dict[str, float]:
    n = max(1, int(row.get("n") or 1))
    return {k: float(v) / n for k, v in (row.get("sum") or {}).items()}


def _frag_dist(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    return sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys) / len(keys)


def predict_state_only(store: dict[str, Any], body_now: dict[str, float], action: str = "WAIT") -> dict[str, Any]:
    if store.get("ablate_body"):
        return {"status": "NO_BODY", "mode": "state_only"}
    bn = _q(body_now)
    sk = f"{_sig(bn)}||{action}"
    row = (store.get("state_pred") or {}).get(sk)
    if not row or int(row.get("support") or 0) < MIN_SUPPORT:
        # soft nearest
        best, best_d = None, 1e9
        for r in (store.get("state_pred") or {}).values():
            if not r.get("key", "").endswith("||" + action):
                continue
            # recover ante from... we don't store ante; skip soft for honesty
            if int(r.get("support") or 0) < MIN_SUPPORT:
                continue
        return {"status": "NO_MATCH", "mode": "state_only", "key": sk}
    return {"status": "MATCH", "mode": "state_only", "key": sk, "predicted": _mean(row),
            "support": row["support"]}


def predict_trajectory(store: dict[str, Any], body_now: dict[str, float], action: str = "WAIT") -> dict[str, Any]:
    if store.get("ablate_trajectory") or store.get("ablate_body"):
        return predict_state_only(store, body_now, action) | {"mode": "traj_ablated_fallback"}
    bn = _q(body_now)
    prior = list(store.get("recent_body") or [])[-TRAJ_LEN:]
    # If recent already ends with bn from last learn, use prior without duplicate;
    # at probe time recent is history before current, so traj = prior + bn
    traj = prior + [bn]
    tk = f"{traj_sig(traj)}||{action}"
    row = (store.get("traj_pred") or {}).get(tk)
    if not row or int(row.get("support") or 0) < MIN_SUPPORT:
        return {"status": "NO_MATCH", "mode": "trajectory", "key": tk,
                "fallback_state": predict_state_only(store, body_now, action)}
    return {"status": "MATCH", "mode": "trajectory", "key": tk, "predicted": _mean(row),
            "support": row["support"], "traj_len": row.get("traj_len")}


def additional_traj_value(state_pred: dict[str, float] | None, traj_pred: dict[str, float] | None,
                          realized: dict[str, float]) -> dict[str, float | None]:
    def l1(p):
        if not p:
            return None
        keys = set(p) | set(realized)
        return sum(abs(float(realized.get(k, 0.0)) - float(p.get(k, 0.0))) for k in keys)
    e_s, e_t = l1(state_pred), l1(traj_pred)
    delta = None if e_s is None or e_t is None else e_s - e_t
    return {"state_error": e_s, "traj_error": e_t, "traj_predictive_delta": delta}


def snapshot(store: dict[str, Any]) -> dict[str, Any]:
    return {
        "state_pred_count": len(store.get("state_pred") or {}),
        "traj_pred_count": len(store.get("traj_pred") or {}),
        "recent_body_len": len(store.get("recent_body") or {}),
        "ablations": {"trajectory": bool(store.get("ablate_trajectory")), "body": bool(store.get("ablate_body"))},
        "leak_tokens": audit_forbidden({
            "state_keys": list((store.get("state_pred") or {}).keys())[:10],
            "traj_keys": list((store.get("traj_pred") or {}).keys())[:10],
        }),
        "metrics_affect_cognition": bool(store.get("metrics_affect_cognition")),
        "bounds": {"MAX_LOCAL": MAX_LOCAL, "MAX_TRAJ": MAX_TRAJ, "TRAJ_LEN": TRAJ_LEN},
    }


def simulate_body_episode(
    *,
    n_ticks: int,
    base_rate: float,
    env_stable: bool = True,
    env_sequence: list[dict[str, float]] | None = None,
    start_loads: dict[str, float] | None = None,
    action: str = "WAIT",
    days_per_tick: float = 1.0,
    wall_clock_delay_ms: float = 0.0,
    hidden_boost: float = 0.0,
    hidden_boost_after: int | None = None,
    sensory_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Researcher-side physical episode. days_per_tick scales body rate without a clock feature.

    wall_clock_delay_ms is host-side only and must not enter agent fragments.
    """
    import time
    cfg = default_process_config()
    cfg["base_rate"] = float(base_rate)
    cfg["regime"] = "REGIME_A"
    cfg["regime_rates"] = {"REGIME_A": float(base_rate)}
    cfg["env_rate_gain"] = 0.0 if env_stable else 0.08
    loads = ensure_process_state(start_loads)
    # hidden_h is WORLD/body GT only - never copied into agent sensory fragment
    loads.setdefault("hidden_h", 0.0)
    sense = sensory_keys or list(PROCESS_KEYS)
    trajectory = []
    t0 = time.perf_counter()
    for t in range(n_ticks):
        if wall_clock_delay_ms > 0:
            time.sleep(wall_clock_delay_ms / 1000.0)
        if env_sequence is not None:
            env = env_sequence[t % len(env_sequence)]
        elif env_stable:
            env = {"temperature": 0.5, "chemical_1": 0.4, "vibration": 0.2}
        else:
            phase = (t % 20) / 20.0
            env = {"temperature": 0.3 + 0.4 * phase, "chemical_1": 0.2 + 0.5 * ((t // 7) % 2),
                   "vibration": 0.1 + 0.6 * ((t % 11) / 11.0)}
        # researcher-only hidden modulation of rate (not a CLOCK)
        hb = float(hidden_boost)
        if hidden_boost_after is not None and t >= int(hidden_boost_after):
            hb = float(hidden_boost)
        elif hidden_boost_after is not None and t < int(hidden_boost_after):
            hb = 0.0
        cfg_t = dict(cfg)
        cfg_t["base_rate"] = float(base_rate) + hb
        cfg_t["regime_rates"] = {"REGIME_A": float(base_rate) + hb}
        before = body_fragment(loads, sensory_keys=sense)
        loads, _deltas, receipt = advance_persistent_processes(
            loads, config=cfg_t, action_kind=action, env_sample=env, days=days_per_tick
        )
        # preserve hidden_h marker for GT (not advanced by process engine)
        loads["hidden_h"] = hb
        after = body_fragment(loads, sensory_keys=sense)
        trajectory.append({
            "tick": t,
            "body_before": before,
            "body_after": after,
            "env": dict(env),
            "rate_used": receipt.get("rate"),
            "hidden_h_gt": hb,
        })
    wall = time.perf_counter() - t0
    return {
        "trajectory": trajectory,
        "final_loads": loads,
        "n_ticks": n_ticks,
        "base_rate": base_rate,
        "days_per_tick": days_per_tick,
        "wall_clock_sec": wall,  # researcher only
        "env_stable": env_stable,
        "sensory_keys": list(sense),
    }


def train_from_episode(store: dict[str, Any], episode: dict[str, Any], action: str = "WAIT") -> None:
    for step in episode.get("trajectory") or []:
        learn(store, body_now=step["body_before"], body_next=step["body_after"], action=action,
              env_frag=step.get("env"))


def body_path_distance(episode: dict[str, Any]) -> float:
    traj = episode.get("trajectory") or []
    if len(traj) < 2:
        return 0.0
    d = 0.0
    for i in range(1, len(traj)):
        d += _frag_dist(traj[i - 1]["body_after"], traj[i]["body_after"])
    return d


def match_body_state(a: dict[str, float], b: dict[str, float], tol: float = MATCH_TOL) -> bool:
    return _frag_dist(_q(a), _q(b)) <= tol
