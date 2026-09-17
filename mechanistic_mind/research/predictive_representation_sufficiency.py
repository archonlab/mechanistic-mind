"""Update 4.36 - Predictive representation sufficiency.

Compares:
  R0 collapsed (marginal follow)
  R1 componentized (4.35 follow_by_component)
  R2 compact relational (bounded IDW anchors)  [NEW]
  R3 context-augmented (4.35 follow_by_context)

No retune of 4.34 ASSIGN_*. No action_logits / compose changes.
"""
from __future__ import annotations

import json
import math
import random
from typing import Any

from mechanistic_mind.research import multimodal_consequence_learning as mm
from mechanistic_mind.research import predictive_structure_selection as pss
from mechanistic_mind.research import prospective_composition as pc

# Unchanged 4.34 geometry
MAX_COMPONENTS = mm.MAX_COMPONENTS
ASSIGN_RADIUS_FLOOR = mm.ASSIGN_RADIUS_FLOOR
ASSIGN_SPREAD_MULT = mm.ASSIGN_SPREAD_MULT

# R2 bounded relational resources (preregistered, shared)
MAX_ANCHORS = 12
ANCHOR_MERGE_RADIUS = 0.06  # continuous local merge; NOT 4.34 retune
IDW_K = 3
IDW_EPS = 1e-3

# Preregistered sufficiency tolerances
EQUAL_ERR_TOL = 0.005
MATERIAL_LOSS = 0.01

FORBIDDEN = (
    "CONTINUOUS", "DISCRETE", "MODE", "REGIME", "REAL_MODE", "TRUE_MODE", "BOUNDARY",
    "STRUCTURE_TYPE", "IMPORTANT", "USEFUL", "REDUNDANT", "NECESSARY", "SIGNAL", "NOISE",
    "WORLD_TYPE", "HIDDEN_STATE", "LATENT_STATE", "BELIEF", "POSSIBILITY", "BRANCH",
    "SCENARIO", "PLAN", "POLICY", "NOVELTY", "CURIOSITY", "UNCERTAINTY", "INFORMATION_GAIN",
)


def audit_forbidden(payload: Any) -> list[str]:
    return [t for t in FORBIDDEN if t in str(payload)]


def architecture_inspection() -> dict[str, Any]:
    return {
        "layers": {
            "A_distributional": "4.34 components[] on transition row",
            "B_sequential": "4.35 follow_by_component / follow_marginal",
            "C_context": "4.35 follow_by_context (HISTORY_LEN=2)",
            "D_compact_relational": "4.36 bounded IDW anchors (x -> next mean)",
        },
        "drift_redundancy": (
            "Under smooth drift, 4.35 component identity carries local continuity; "
            "R2 can express the same local map without treating component id as essential."
        ),
        "compression_421": "4.21 compresses event/structures; not a continuous x->next map.",
        "smallest_change": "Additive relational_anchors + compete_representations; 4.34/4.35 untouched.",
        "params": {
            "MAX_ANCHORS": MAX_ANCHORS,
            "ANCHOR_MERGE_RADIUS": ANCHOR_MERGE_RADIUS,
            "IDW_K": IDW_K,
            "EQUAL_ERR_TOL": EQUAL_ERR_TOL,
            "MATERIAL_LOSS": MATERIAL_LOSS,
            "434_unchanged": {
                "MAX_COMPONENTS": MAX_COMPONENTS,
                "ASSIGN_RADIUS_FLOOR": ASSIGN_RADIUS_FLOOR,
                "ASSIGN_SPREAD_MULT": ASSIGN_SPREAD_MULT,
            },
        },
    }


def _l1(a, b):
    return float(pc._frag_distance(a or {}, b or {}))


def _mean(row):
    n = max(1e-9, float(row.get("n") or 0.0))
    return {k: float(v) / n for k, v in (row.get("sum") or {}).items()}


def empty_prs_store(**kw) -> dict[str, Any]:
    s = pss.empty_pss_store()
    s["relational_anchors"] = []  # [{x, sum_next, n, support, last_tick}]
    s["enable_relational"] = True
    s["ablate_relational"] = False
    s["ablate_components_path"] = False  # force R1 off at predict time
    s.update(kw)
    return s


def _update_anchor(store: dict[str, Any], x: dict[str, float], nxt: dict[str, float], tick: int) -> None:
    if not store.get("enable_relational") or store.get("ablate_relational"):
        return
    anchors = list(store.get("relational_anchors") or [])
    best_i, best_d = None, None
    for i, a in enumerate(anchors):
        d = _l1(x, a.get("x") or {})
        if best_d is None or d < best_d:
            best_d, best_i = d, i
    if best_i is not None and best_d is not None and best_d <= ANCHOR_MERGE_RADIUS:
        a = anchors[best_i]
        n = float(a.get("n") or 0.0) + 1.0
        # update x center and next sum
        xc = dict(a.get("x") or {})
        for k, v in x.items():
            old = float(xc.get(k, 0.0))
            xc[k] = (old * (n - 1.0) + float(v)) / n
        sm = dict(a.get("sum_next") or {})
        for k, v in nxt.items():
            sm[k] = float(sm.get(k, 0.0)) + float(v)
        a.update({"x": xc, "sum_next": sm, "n": n, "support": float(a.get("support") or 0) + 1.0, "last_tick": tick})
        anchors[best_i] = a
    else:
        if len(anchors) >= MAX_ANCHORS:
            victim = min(range(len(anchors)), key=lambda i: float(anchors[i].get("support") or 0.0))
            anchors.pop(victim)
        anchors.append({
            "x": dict(x),
            "sum_next": {k: float(v) for k, v in nxt.items()},
            "n": 1.0,
            "support": 1.0,
            "last_tick": tick,
        })
    store["relational_anchors"] = anchors


def predict_relational(store: dict[str, Any], x: dict[str, float]) -> dict[str, Any]:
    anchors = list(store.get("relational_anchors") or [])
    if not anchors or store.get("ablate_relational"):
        return {"predicted": None, "source": "relational_empty", "n_anchors": len(anchors)}
    scored = []
    for a in anchors:
        d = _l1(x, a.get("x") or {})
        scored.append((d, a))
    scored.sort(key=lambda t: t[0])
    top = scored[:IDW_K]
    # IDW
    num: dict[str, float] = {}
    den = 0.0
    for d, a in top:
        w = 1.0 / (d + IDW_EPS)
        nxt = _mean({"sum": a.get("sum_next") or {}, "n": a.get("n") or 1.0})
        for k, v in nxt.items():
            num[k] = num.get(k, 0.0) + w * float(v)
        den += w
    pred = {k: v / den for k, v in num.items()} if den > 0 else None
    return {"predicted": pred, "source": "relational_idw", "n_anchors": len(anchors), "used": len(top)}


def representation_cost(store: dict[str, Any], antecedent, action) -> dict[str, Any]:
    comps = mm.predict_components(store, antecedent, action)
    return {
        "n_components": comps.get("n_supported") or 0,
        "n_follow_keys": len(store.get("follow_by_component") or {}),
        "n_ctx_keys": len(store.get("follow_by_context") or {}),
        "n_anchors": len(store.get("relational_anchors") or []),
        "bytes": mm.memory_bytes_estimate(store).get("transition_store_bytes"),
        "anchor_bytes": len(json.dumps(store.get("relational_anchors") or [], default=str).encode()),
    }


def predict_path(store, *, antecedent, action, current, path: str):
    """path in {collapsed, component, relational, context}."""
    if path == "relational":
        return predict_relational(store, current)
    if path == "collapsed":
        return pss.predict_next(store, antecedent=antecedent, action=action, current=current, path="collapsed")
    if path == "component":
        if store.get("ablate_components_path"):
            return pss.predict_next(store, antecedent=antecedent, action=action, current=current, path="collapsed")
        return pss.predict_next(store, antecedent=antecedent, action=action, current=current, path="full")
    if path == "context":
        return pss.predict_next(store, antecedent=antecedent, action=action, current=current, path="context")
    return {"predicted": None, "source": "unknown"}


def compete_stream(
    series: list[dict[str, float]],
    *,
    seed: int,
    store_kw: dict | None = None,
    merge_components_for_predict: bool = False,
) -> dict[str, Any]:
    """Prequential competition R0/R1/R2/R3 on one series."""
    store = empty_prs_store(**(store_kw or {}))
    S, A = pss.base_S(), "A0"
    errs = {k: [] for k in ("collapsed", "component", "relational", "context")}
    rng = random.Random(seed)

    for t in range(len(series) - 1):
        cur, nxt = series[t], series[t + 1]
        if t == 0:
            mm.learn_transition_mm(store, tick=1, antecedent=S, action=A, consequent=cur)

        for path in errs:
            pr = predict_path(store, antecedent=S, action=A, current=cur, path=path)
            pred = pr.get("predicted") or cur
            errs[path].append(_l1(pred, nxt))

        # learn sequential + relational
        pss.learn_step(store, tick=t + 2, antecedent=S, action=A, consequent=cur, next_consequent=nxt, rng=rng)
        _update_anchor(store, cur, nxt, tick=t + 2)

    def mean(xs):
        return float(sum(xs) / len(xs)) if xs else None

    means = {k: mean(v) for k, v in errs.items()}
    cost = representation_cost(store, S, A)
    return {
        "err": means,
        "delta_comp_minus_rel": (means["component"] - means["relational"]) if means["component"] is not None else None,
        "delta_col_minus_rel": (means["collapsed"] - means["relational"]) if means["collapsed"] is not None else None,
        "delta_col_minus_comp": (means["collapsed"] - means["component"]) if means["collapsed"] is not None else None,
        "delta_col_minus_ctx": (means["collapsed"] - means["context"]) if means["collapsed"] is not None else None,
        "cost": cost,
        "store": store,
        "n": len(series) - 1,
    }


def approx_equal(a, b, tol=EQUAL_ERR_TOL) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def better(a, b, margin=MATERIAL_LOSS) -> bool:
    """a better than b if a + margin < b (lower error)."""
    if a is None or b is None:
        return False
    return a + margin < b


def not_worse(a, b, tol=EQUAL_ERR_TOL) -> bool:
    if a is None or b is None:
        return False
    return a <= b + tol


# -------------------- process generators --------------------

def gen_linear_drift(*, n, seed, noise=0.015, step=0.04):
    rng = random.Random(seed)
    x = 0.2
    out = []
    direction = 1.0
    for _ in range(n):
        x = x + direction * step + rng.gauss(0, noise)
        if x > 0.9:
            direction = -1.0
            x = 0.9
        if x < 0.1:
            direction = 1.0
            x = 0.1
        out.append(pss.obs(x, noise=noise * 0.5, rng=rng))
    return out


def gen_nonlinear(*, n, seed, noise=0.02):
    """Smooth logistic-like map in [0.1,0.9]."""
    rng = random.Random(seed)
    x = 0.3
    out = []
    for _ in range(n):
        # x <- 0.5 + 0.35*tanh(2*(x-0.5)) + noise  (smooth nonlinear)
        x = 0.5 + 0.35 * math.tanh(2.5 * (x - 0.5)) + rng.gauss(0, noise)
        x = max(0.08, min(0.92, x))
        out.append(pss.obs(x, noise=noise * 0.4, rng=rng))
    return out


def gen_variable_rate(*, n, seed, noise=0.015):
    """dx depends on x: slow near 0.5, faster near edges."""
    rng = random.Random(seed)
    x = 0.2
    out = []
    for _ in range(n):
        rate = 0.02 + 0.08 * abs(x - 0.5)
        x = x + rate * (1.0 if x < 0.85 else -1.0) + rng.gauss(0, noise)
        if x > 0.9:
            x = 0.15
        if x < 0.1:
            x = 0.1
        out.append(pss.obs(x, noise=noise * 0.4, rng=rng))
    return out


def gen_persistent(n, seed):
    return pss.gen_persistent_regimes(n=n, seed=seed, p_switch=0.05)


def gen_hist_diff(n, seed):
    s, _ = pss.gen_history_different_futures(n=n, seed=seed)
    return s


def gen_hist_same(n, seed):
    return pss.gen_history_same_future(n=n, seed=seed)


def gen_memoryless(n, seed):
    return pss.gen_memoryless_bimodal(n=n, seed=seed)


def gen_gap_continuous(*, n, seed, noise=0.02):
    """Smooth underlying map but samples mostly in two lobes (middle rarely visited)."""
    rng = random.Random(seed)
    out = []
    x = 0.2
    for _ in range(n):
        # jump between lobes with smooth local dynamics inside
        if rng.random() < 0.02:
            x = 0.8 if x < 0.5 else 0.2
        else:
            x = x + rng.gauss(0, 0.03)
            if x < 0.35:
                x = max(0.1, min(0.35, x))
            elif x > 0.65:
                x = max(0.65, min(0.9, x))
            else:
                # rare middle: push out
                x = 0.2 if rng.random() < 0.5 else 0.8
        out.append(pss.obs(x, noise=noise, rng=rng))
    return out


def gen_close_present_diff_future(n, seed):
    """Same as hist_diff — overlapping mid with different futures."""
    return gen_hist_diff(n, seed)


def gen_noisy_smooth(*, n, seed, noise=0.08):
    return gen_nonlinear(n=n, seed=seed, noise=noise)


def gen_piecewise(*, n, seed, noise=0.02):
    """Smooth within low and high; sharp change in continuation across ~0.5."""
    rng = random.Random(seed)
    x = 0.25
    out = []
    for _ in range(n):
        if x < 0.5:
            x = x + 0.03 + rng.gauss(0, noise)  # drifts up toward boundary
            if x >= 0.5:
                x = 0.75  # discontinuous jump in dynamics
        else:
            x = x - 0.03 + rng.gauss(0, noise)
            if x < 0.5:
                x = 0.25
        x = max(0.1, min(0.9, x))
        out.append(pss.obs(x, noise=noise * 0.4, rng=rng))
    return out


def gen_reversal(*, n, seed, noise=0.015):
    return gen_linear_drift(n=n, seed=seed, noise=noise, step=0.035)


def gen_complexify(*, n1, n2, seed):
    return gen_linear_drift(n=n1, seed=seed) + gen_persistent(n2, seed + 1)


def gen_simplify(*, n1, n2, seed):
    return gen_persistent(n1, seed) + gen_linear_drift(n=n2, seed=seed + 1)


def merge_damage_probe(series, *, seed) -> dict[str, Any]:
    """FULL vs MERGED component follow: force collapsed path as merge proxy."""
    full = compete_stream(series, seed=seed)
    merged = compete_stream(series, seed=seed, store_kw={"ablate_follow": True, "ablate_context": True})
    # merged still has relational; for merge damage on component path compare component errs
    # Re-run with relational ablated to isolate component merge
    full_c = compete_stream(series, seed=seed, store_kw={"ablate_relational": True})
    merged_c = compete_stream(series, seed=seed, store_kw={"ablate_relational": True, "ablate_follow": True, "ablate_context": True})
    return {
        "err_full_comp": full_c["err"]["component"],
        "err_merged_comp": merged_c["err"]["collapsed"],
        "damage": (merged_c["err"]["collapsed"] or 0) - (full_c["err"]["component"] or 0),
        "err_rel": full["err"]["relational"],
        "err_comp": full["err"]["component"],
    }
