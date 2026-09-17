"""Update 4.35 - Predictive structure selection.

4.34 multimodal components unchanged (no ASSIGN_* retune).
Adds bounded component->next and optional short-history->next associations.
Prequential evaluation. No action_logits / compose changes.
"""
from __future__ import annotations

import json
import math
import random
from typing import Any, Callable

from mechanistic_mind.research import multimodal_consequence_learning as mm
from mechanistic_mind.research import prospective_composition as pc

MAX_COMPONENTS = mm.MAX_COMPONENTS
ASSIGN_RADIUS_FLOOR = mm.ASSIGN_RADIUS_FLOOR
ASSIGN_SPREAD_MULT = mm.ASSIGN_SPREAD_MULT

MAX_FOLLOW_KEYS = 64
FOLLOW_MIN_SUPPORT = 3.0
HISTORY_LEN = 2
MAX_CTX_FOLLOW = 64
CTX_MIN_SUPPORT = 3.0

FORBIDDEN = (
    "MODE", "REGIME", "SIGNAL", "NOISE", "STRUCTURED", "UNSTRUCTURED", "IMPORTANT",
    "USEFUL", "CAUSAL_STATE", "LATENT_STATE", "BELIEF", "WORLD_TYPE", "BRANCH",
    "POSSIBILITY", "FUTURE_CLASS", "NOVELTY", "CURIOSITY", "INFORMATION_GAIN",
    "UNCERTAINTY", "PLAN", "POLICY", "CORRECT_FUTURE", "WORLD_CHANGED",
)


def audit_forbidden(payload: Any) -> list[str]:
    return [t for t in FORBIDDEN if t in str(payload)]


def architecture_inspection() -> dict[str, Any]:
    return {
        "after_assignment": "4.34 components: id/center/support/spread; legacy mean intact",
        "smallest_change": "bounded follow_by_component + follow_by_context; prequential predict",
        "no_retune": {"MAX_COMPONENTS": MAX_COMPONENTS, "ASSIGN_RADIUS_FLOOR": ASSIGN_RADIUS_FLOOR},
        "bounded": {"MAX_FOLLOW_KEYS": MAX_FOLLOW_KEYS, "HISTORY_LEN": HISTORY_LEN, "MAX_CTX_FOLLOW": MAX_CTX_FOLLOW},
        "relation_434_C4": "historical geometric C4 NULL preserved; 4.35 tests predictive contribution",
    }


def empty_pss_store(**kw) -> dict[str, Any]:
    s = mm.empty_mm_store()
    s["follow_by_component"] = {}
    s["follow_by_context"] = {}
    s["follow_marginal"] = {"sum": {}, "n": 0.0, "support": 0.0}
    s["recent_component_ids"] = []
    s["enable_follow"] = True
    s["enable_context_follow"] = True
    s["ablate_follow"] = False
    s["ablate_context"] = False
    s.update(kw)
    return s


def _l1(a: dict[str, float] | None, b: dict[str, float] | None) -> float:
    return float(pc._frag_distance(a or {}, b or {}))


def _mean(row: dict[str, Any]) -> dict[str, float]:
    n = max(1e-9, float(row.get("n") or 0.0))
    return {k: float(v) / n for k, v in (row.get("sum") or {}).items()}


def _touch_mean(row: dict[str, Any], cons: dict[str, float]) -> None:
    n = float(row.get("n") or 0.0) + 1.0
    sm = dict(row.get("sum") or {})
    for k, v in cons.items():
        sm[k] = float(sm.get(k, 0.0)) + float(v)
    row["sum"] = sm
    row["n"] = n
    row["support"] = float(row.get("support") or 0.0) + 1.0


def _table_update(table: dict[str, Any], key: str, cons: dict[str, float], *, cap: int) -> None:
    if key not in table:
        if len(table) >= cap:
            victim = min(table.items(), key=lambda kv: float(kv[1].get("support") or 0.0))[0]
            del table[victim]
        table[key] = {"sum": {}, "n": 0.0, "support": 0.0}
    _touch_mean(table[key], cons)


def assign_component_id(store: dict[str, Any], antecedent: dict[str, float], action: str, cons: dict[str, float]) -> str | None:
    """Nearest existing component after/with current observation (researcher probe)."""
    key = pc.transition_key(pc._q(antecedent), action)
    row = (store.get("transitions") or {}).get(key)
    if not row:
        return None
    comps = list(row.get("components") or [])
    if not comps:
        return None
    best = min(comps, key=lambda c: _l1(cons, c.get("center") or {}))
    # only count if within assign radius (same rule as 4.34)
    d = _l1(cons, best.get("center") or {})
    rad = max(ASSIGN_RADIUS_FLOOR, ASSIGN_SPREAD_MULT * float(best.get("spread") or 0.0))
    if d > rad * 1.5:
        # still return nearest for soft association learning; mark weak
        return str(best.get("id"))
    return str(best.get("id"))


def learn_step(
    store: dict[str, Any],
    *,
    tick: int,
    antecedent: dict[str, float],
    action: str,
    consequent: dict[str, float],
    next_consequent: dict[str, float] | None = None,
    shuffle_follow: bool = False,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Learn transition_mm; if next provided, update follow tables from assigned component."""
    mm.learn_transition_mm(store, tick=tick, antecedent=antecedent, action=action, consequent=consequent)
    cid = assign_component_id(store, antecedent, action, consequent)
    hist = list(store.get("recent_component_ids") or [])
    tkey = pc.transition_key(pc._q(antecedent), action)
    info = {"component_id": cid, "hist": list(hist)}
    if next_consequent is not None and cid is not None and store.get("enable_follow") and not store.get("ablate_follow"):
        follow_cons = dict(next_consequent)
        if shuffle_follow and rng is not None:
            # caller should pass already-shuffled; keep flag for clarity
            pass
        fkey = f"{tkey}||{cid}"
        _table_update(store["follow_by_component"], fkey, follow_cons, cap=MAX_FOLLOW_KEYS)
        _touch_mean(store["follow_marginal"], follow_cons)
        if store.get("enable_context_follow") and not store.get("ablate_context"):
            ctx = tuple((hist + [cid])[-HISTORY_LEN:])
            ckey = f"{tkey}||{ctx}"
            _table_update(store["follow_by_context"], ckey, follow_cons, cap=MAX_CTX_FOLLOW)
    if cid is not None:
        hist = (hist + [cid])[-HISTORY_LEN:]
        store["recent_component_ids"] = hist
    return info


def predict_next(
    store: dict[str, Any],
    *,
    antecedent: dict[str, float],
    action: str,
    current: dict[str, float],
    path: str = "full",
) -> dict[str, Any]:
    """Predict t+1 physical consequence.

    path:
      full     - component-conditioned follow if available
      collapsed - marginal follow only (ignore component)
      context  - short history-conditioned follow
      legacy   - no follow; None
    """
    tkey = pc.transition_key(pc._q(antecedent), action)
    cid = assign_component_id(store, antecedent, action, current)
    marginal = _mean(store.get("follow_marginal") or {}) if float((store.get("follow_marginal") or {}).get("n") or 0) > 0 else None

    if path == "legacy":
        return {"predicted": None, "source": "legacy", "component_id": cid}
    if path == "collapsed":
        return {"predicted": marginal, "source": "marginal", "component_id": cid}

    if path == "context" and not store.get("ablate_context"):
        hist = list(store.get("recent_component_ids") or [])
        if cid is not None:
            ctx = tuple((hist + [cid])[-HISTORY_LEN:])
            ckey = f"{tkey}||{ctx}"
            row = (store.get("follow_by_context") or {}).get(ckey)
            if row and float(row.get("support") or 0) >= CTX_MIN_SUPPORT:
                return {"predicted": _mean(row), "source": "context", "component_id": cid, "key": ckey}

    if path in ("full", "context") and cid is not None and not store.get("ablate_follow"):
        fkey = f"{tkey}||{cid}"
        row = (store.get("follow_by_component") or {}).get(fkey)
        if row and float(row.get("support") or 0) >= FOLLOW_MIN_SUPPORT:
            return {"predicted": _mean(row), "source": "component", "component_id": cid, "key": fkey}

    return {"predicted": marginal, "source": "marginal_fallback", "component_id": cid}


def prequential_stream(
    store: dict[str, Any],
    *,
    antecedent: dict[str, float],
    action: str,
    series: list[dict[str, float]],
    shuffle_follow: bool = False,
    seed: int = 0,
) -> dict[str, Any]:
    """Online: for t=0..T-2: predict next from current, score, then learn (current, next)."""
    rng = random.Random(seed)
    errs = {"full": [], "collapsed": [], "context": []}
    sources = []
    # optional shuffle buffer of nexts
    nexts = series[1:]
    shuffled_nexts = list(nexts)
    if shuffle_follow:
        rng.shuffle(shuffled_nexts)

    for t in range(len(series) - 1):
        cur = series[t]
        nxt = series[t + 1]
        # predict BEFORE update using current assignment on existing store
        # ensure current is reflected in components by a learn of current alone first time
        if t == 0:
            mm.learn_transition_mm(store, tick=1, antecedent=antecedent, action=action, consequent=cur)
            assign_component_id(store, antecedent, action, cur)

        pf = predict_next(store, antecedent=antecedent, action=action, current=cur, path="full")
        pc_ = predict_next(store, antecedent=antecedent, action=action, current=cur, path="collapsed")
        px = predict_next(store, antecedent=antecedent, action=action, current=cur, path="context")
        for name, pr in (("full", pf), ("collapsed", pc_), ("context", px)):
            pred = pr.get("predicted")
            if pred is None:
                # fallback: predict current (persistence) as neutral baseline
                pred = cur
            errs[name].append(_l1(pred, nxt))
        sources.append(pf.get("source"))

        follow_target = shuffled_nexts[t] if shuffle_follow else nxt
        learn_step(
            store, tick=t + 2, antecedent=antecedent, action=action,
            consequent=cur, next_consequent=follow_target, shuffle_follow=shuffle_follow, rng=rng,
        )

    def mean(xs):
        return float(sum(xs) / len(xs)) if xs else None

    return {
        "n_steps": len(series) - 1,
        "err_full": mean(errs["full"]),
        "err_collapsed": mean(errs["collapsed"]),
        "err_context": mean(errs["context"]),
        "delta_collapsed_minus_full": (mean(errs["collapsed"]) - mean(errs["full"])) if errs["full"] else None,
        "delta_collapsed_minus_context": (mean(errs["collapsed"]) - mean(errs["context"])) if errs["context"] else None,
        "n_components": mm.predict_components(store, antecedent, action)["n_supported"],
        "n_follow_keys": len(store.get("follow_by_component") or {}),
        "n_ctx_keys": len(store.get("follow_by_context") or {}),
        "source_hist": sources[-20:],
        "memory": mm.memory_bytes_estimate(store),
    }


# -------------------- process generators (researcher) --------------------

def base_S() -> dict[str, float]:
    return mm.base_S()


def obs(f1: float, *, noise: float, rng: random.Random) -> dict[str, float]:
    return mm.regime(f1, noise=noise, rng=rng)


def gen_persistent_regimes(*, n: int, seed: int, p_switch: float = 0.05) -> list[dict[str, float]]:
    """Markov persistence: stay in low or high; next ~ same region (predictive)."""
    rng = random.Random(seed)
    state = 0 if rng.random() < 0.5 else 1  # 0->0.15, 1->0.85
    out = []
    for _ in range(n):
        if rng.random() < p_switch:
            state = 1 - state
        mu = 0.15 if state == 0 else 0.85
        out.append(obs(mu, noise=0.02, rng=rng))
    return out


def gen_broad_iid(*, n: int, seed: int, noise: float = 0.28) -> list[dict[str, float]]:
    rng = random.Random(seed)
    return [obs(0.50, noise=noise, rng=rng) for _ in range(n)]


def gen_memoryless_bimodal(*, n: int, seed: int) -> list[dict[str, float]]:
    """Bimodal marginals, independent draws (distributional multimodality, no persistence)."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        mu = 0.15 if rng.random() < 0.5 else 0.85
        out.append(obs(mu, noise=0.02, rng=rng))
    return out


def gen_drift(*, n: int, seed: int) -> list[dict[str, float]]:
    rng = random.Random(seed)
    x = 0.5
    out = []
    for _ in range(n):
        x = max(0.05, min(0.95, x + rng.gauss(0.0, 0.04)))
        out.append(obs(x, noise=0.015, rng=rng))
    return out


def gen_separated_same_future(*, n: int, seed: int) -> list[dict[str, float]]:
    """Alternate C1/C2 presents but next always near 0.5 (same future)."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        if i % 2 == 0:
            out.append(obs(0.15 if rng.random() < 0.5 else 0.85, noise=0.02, rng=rng))
        else:
            out.append(obs(0.50, noise=0.02, rng=rng))
    return out


def gen_history_different_futures(*, n: int, seed: int) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    """Two streams with matched present O~0.5 but different futures after a marker history.

    Stream pattern (researcher):
      A-path: low, mid, high-future...
      B-path: high, mid, low-future...
    Present at mid is overlapping; history differs; future differs.
    Returns (series, meta_tags researcher-only parallel list of 'mid'|'other').
    """
    rng = random.Random(seed)
    series = []
    tags = []
    while len(series) < n:
        if rng.random() < 0.5:
            series.append(obs(0.15, noise=0.02, rng=rng)); tags.append("hA")
            series.append(obs(0.50, noise=0.02, rng=rng)); tags.append("mid")
            series.append(obs(0.85, noise=0.02, rng=rng)); tags.append("fA")
        else:
            series.append(obs(0.85, noise=0.02, rng=rng)); tags.append("hB")
            series.append(obs(0.50, noise=0.02, rng=rng)); tags.append("mid")
            series.append(obs(0.15, noise=0.02, rng=rng)); tags.append("fB")
    return series[:n], tags[:n]


def gen_history_same_future(*, n: int, seed: int) -> list[dict[str, float]]:
    """Histories differ (low,mid vs high,mid) but mid always followed by ~0.5."""
    rng = random.Random(seed)
    series = []
    while len(series) < n:
        if rng.random() < 0.5:
            series.append(obs(0.15, noise=0.02, rng=rng))
        else:
            series.append(obs(0.85, noise=0.02, rng=rng))
        series.append(obs(0.50, noise=0.02, rng=rng))
        series.append(obs(0.50, noise=0.02, rng=rng))
    return series[:n]


def gen_appearance(*, n1: int, n2: int, seed: int) -> list[dict[str, float]]:
    """Phase1: iid around 0.5 (no useful distinction). Phase2: persistent regimes."""
    return gen_broad_iid(n=n1, seed=seed, noise=0.08) + gen_persistent_regimes(n=n2, seed=seed + 1, p_switch=0.05)


def gen_dissolution(*, n1: int, n2: int, seed: int) -> list[dict[str, float]]:
    return gen_persistent_regimes(n=n1, seed=seed, p_switch=0.05) + gen_memoryless_bimodal(n=n2, seed=seed + 1)


def contribution_ok(delta: float | None, *, min_delta: float = 0.01) -> bool:
    return delta is not None and delta >= min_delta


def little_contribution(delta: float | None, *, max_delta: float = 0.005) -> bool:
    return delta is not None and abs(delta) <= max_delta


def run_process(name: str, series: list[dict[str, float]], *, seed: int, **store_kw) -> dict[str, Any]:
    store = empty_pss_store(**store_kw)
    stats = prequential_stream(store, antecedent=base_S(), action="A0", series=series, seed=seed)
    stats["process"] = name
    stats["store"] = store
    stats["n_series"] = len(series)
    return stats


def purge_and_reprobe(store: dict[str, Any], series_probe: list[dict[str, float]], *, seed: int) -> dict[str, Any]:
    mm.purge_raw_history(store)
    # freeze learning: score predictions only using existing follow tables
    S, A = base_S(), "A0"
    errs_f, errs_c = [], []
    for t in range(len(series_probe) - 1):
        cur, nxt = series_probe[t], series_probe[t + 1]
        # soft assign without learn
        pf = predict_next(store, antecedent=S, action=A, current=cur, path="full")
        pc_ = predict_next(store, antecedent=S, action=A, current=cur, path="collapsed")
        pred_f = pf.get("predicted") or cur
        pred_c = pc_.get("predicted") or cur
        errs_f.append(_l1(pred_f, nxt))
        errs_c.append(_l1(pred_c, nxt))
    return {
        "err_full": sum(errs_f) / len(errs_f),
        "err_collapsed": sum(errs_c) / len(errs_c),
        "delta": (sum(errs_c) - sum(errs_f)) / len(errs_f),
    }
