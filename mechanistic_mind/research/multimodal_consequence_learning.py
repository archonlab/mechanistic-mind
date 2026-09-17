"""Update 4.34 - Bounded multimodal consequence learning (pc store).

Adds bounded online components beside the legacy single-mean transition row.
Does NOT alter mean_cons / predict_one_step / distal_prediction / action_logits.

4.14 modes live on temporal_contingency; 4.33 mean-collapse is in pc.learn_transition.
"""
from __future__ import annotations

import json
import math
import random
from copy import deepcopy
from typing import Any

from mechanistic_mind.research import prospective_composition as pc

FORBIDDEN = (
    "BRANCH", "POSSIBILITY", "OPTION", "SCENARIO", "ALTERNATIVE", "WORLD_MODE",
    "GOOD_OUTCOME", "BAD_OUTCOME", "NOVELTY", "CURIOSITY", "UNCERTAINTY",
    "INFORMATION_GAIN", "PLAN", "POLICY", "DECISION_TREE", "CORRECT_FUTURE",
    "LEAF_EVENT", "OUTCOME_TYPE", "WORLD_CHANGED", "NEW_MODE",
)

MAX_COMPONENTS = 4
ASSIGN_RADIUS_FLOOR = 0.08
ASSIGN_SPREAD_MULT = 2.5
MIN_COMPONENT_SUPPORT = 3.0
IDLE_SUPPORT_DECAY = 0.995


def audit_forbidden(payload: Any) -> list[str]:
    return [t for t in FORBIDDEN if t in str(payload)]


def architecture_inspection() -> dict[str, Any]:
    return {
        "legacy_storage": "pc.learn_transition: one mean (sum/n) + var_sum per (antecedent, action)",
        "variance_already": "var_sum/reliability (4.29) — not multiple centers; reliability -X-> action",
        "raw_observations": "bounded exposure_log (256), not full archive",
        "elsewhere_multimodal": "4.14 multiple_consequences on tc body-deltas; not wired into pc",
        "bounded_memory_reuse": "pc.MAX_TRANSITIONS; 4.14 lowest-support replace; 4.21 structures",
        "smallest_change": "learn_transition_mm + components[] on row; predict_components additive; no action wiring",
        "relation_to_433": "4.33 C2 NULL from mean collapse; 4.34 tests component retention only",
        "params": {
            "MAX_COMPONENTS": MAX_COMPONENTS,
            "ASSIGN_RADIUS_FLOOR": ASSIGN_RADIUS_FLOOR,
            "ASSIGN_SPREAD_MULT": ASSIGN_SPREAD_MULT,
            "MIN_COMPONENT_SUPPORT": MIN_COMPONENT_SUPPORT,
            "IDLE_SUPPORT_DECAY": IDLE_SUPPORT_DECAY,
        },
    }


def _frag_l1(a: dict[str, float], b: dict[str, float]) -> float:
    return float(pc._frag_distance(a, b))


def _assign_radius(comp: dict[str, Any]) -> float:
    return max(float(ASSIGN_RADIUS_FLOOR), float(ASSIGN_SPREAD_MULT) * float(comp.get("spread") or 0.0))


def _new_component(cons: dict[str, float], cid: str, tick: int) -> dict[str, Any]:
    return {
        "id": cid,
        "center": {k: float(v) for k, v in cons.items()},
        "support": 1.0,
        "spread": 0.0,
        "updates": 1,
        "last_tick": int(tick),
    }


def update_components(
    row: dict[str, Any],
    consequent: dict[str, float],
    *,
    tick: int,
    max_components: int | None = None,
    enable: bool = True,
    decay: bool = True,
) -> dict[str, Any]:
    if not enable:
        row.setdefault("components", [])
        return row
    max_c = int(max_components if max_components is not None else MAX_COMPONENTS)
    cons = {k: float(v) for k, v in consequent.items()}
    comps: list[dict[str, Any]] = list(row.get("components") or [])
    next_id = int(row.get("next_component_id") or 1)
    best_i = None
    best_d = None
    for i, c in enumerate(comps):
        d = _frag_l1(cons, c.get("center") or {})
        if best_d is None or d < best_d:
            best_d, best_i = d, i
    touched = None
    if best_i is not None and best_d is not None and best_d <= _assign_radius(comps[best_i]):
        c = comps[best_i]
        n = float(c.get("support") or 0.0) + 1.0
        center = dict(c.get("center") or {})
        for k in set(center) | set(cons):
            old = float(center.get(k, 0.0))
            center[k] = (old * (n - 1.0) + float(cons.get(k, 0.0))) / n
        spread = (float(c.get("spread") or 0.0) * (n - 1.0) + float(best_d)) / n
        c.update({"center": center, "support": n, "spread": spread,
                  "updates": int(c.get("updates") or 0) + 1, "last_tick": int(tick)})
        comps[best_i] = c
        touched = best_i
    else:
        cid = f"M{next_id}"
        next_id += 1
        if len(comps) < max_c:
            comps.append(_new_component(cons, cid, tick))
            touched = len(comps) - 1
        else:
            victim = min(range(len(comps)), key=lambda i: float(comps[i].get("support") or 0.0))
            comps[victim] = _new_component(cons, cid, tick)
            touched = victim
    if decay:
        for i, c in enumerate(comps):
            if i != touched:
                c["support"] = float(c.get("support") or 0.0) * float(IDLE_SUPPORT_DECAY)
    comps = [c for c in comps if float(c.get("support") or 0.0) >= 0.5] or comps[:1]
    row["components"] = comps
    row["next_component_id"] = next_id
    row["component_updates"] = int(row.get("component_updates") or 0) + 1
    return row


def learn_transition_mm(
    store: dict[str, Any],
    *,
    tick: int,
    antecedent: dict[str, float],
    action: str,
    consequent: dict[str, float],
    reliability_weight: float = 1.0,
    enable_components: bool | None = None,
    max_components: int | None = None,
) -> str:
    tid = pc.learn_transition(
        store, tick=tick, antecedent=antecedent, action=action,
        consequent=consequent, reliability_weight=reliability_weight,
    )
    key = pc.transition_key(pc._q(antecedent), action)
    row = (store.get("transitions") or {}).get(key)
    if row is None:
        return tid
    enable = store.get("enable_components", True) if enable_components is None else enable_components
    if store.get("ablate_components"):
        enable = False
    if store.get("force_max_components") is not None:
        max_components = int(store["force_max_components"])
    update_components(
        row, consequent, tick=tick, max_components=max_components,
        enable=bool(enable), decay=bool(store.get("component_decay", True)),
    )
    return tid


def predict_components(
    store: dict[str, Any],
    antecedent: dict[str, float],
    action: str,
    *,
    min_support: float = MIN_COMPONENT_SUPPORT,
) -> dict[str, Any]:
    key = pc.transition_key(pc._q(antecedent), action)
    row = (store.get("transitions") or {}).get(key)
    if row is None:
        step = pc.predict_one_step(store, antecedent, action)
        if step.get("status") != "MATCH":
            return {"status": "NO_MATCH", "components": [], "n_supported": 0, "legacy_mean": None}
        key = step["key"]
        row = (store.get("transitions") or {}).get(key)
    if row is None:
        return {"status": "NO_MATCH", "components": [], "n_supported": 0, "legacy_mean": None}
    legacy = pc.mean_cons(row)
    comps = []
    for c in list(row.get("components") or []):
        if float(c.get("support") or 0.0) >= float(min_support):
            comps.append({
                "id": c.get("id"),
                "center": dict(c.get("center") or {}),
                "support": float(c.get("support") or 0.0),
                "spread": float(c.get("spread") or 0.0),
                "last_tick": c.get("last_tick"),
            })
    total = sum(c["support"] for c in comps) or 1.0
    for c in comps:
        c["empirical_weight"] = c["support"] / total
    comps = sorted(comps, key=lambda x: str(x.get("id")))
    status = "NONE" if not comps else ("SINGLE" if len(comps) == 1 else "MULTIPLE")
    return {
        "status": status, "key": key, "n_supported": len(comps),
        "n_raw": len(row.get("components") or []), "components": comps,
        "legacy_mean": legacy, "legacy_support": int(row.get("support") or 0),
        "leak_tokens": audit_forbidden(comps),
    }


def purge_raw_history(store: dict[str, Any]) -> dict[str, Any]:
    n = len(store.get("exposure_log") or [])
    store["exposure_log"] = []
    return {"purged_exposure_entries": n, "transitions_retained": len(store.get("transitions") or {})}


def memory_bytes_estimate(store: dict[str, Any]) -> dict[str, Any]:
    tr = store.get("transitions") or {}
    raw = store.get("exposure_log") or []
    tr_b = len(json.dumps(tr, default=str).encode())
    raw_b = len(json.dumps(raw, default=str).encode())
    n_comp = sum(len(r.get("components") or []) for r in tr.values())
    return {
        "n_transitions": len(tr), "n_components_total": n_comp,
        "transition_store_bytes": tr_b, "exposure_log_bytes": raw_b,
        "total_predictive_bytes": tr_b,
    }


def base_S() -> dict[str, float]:
    return {
        "energy_signal": 0.45, "hydration_signal": 0.72, "fatigue_signal": 0.20,
        "discomfort_signal": 0.05, "field_1": 0.50, "field_2": 0.50, "resistance": 0.40,
    }


def regime(center_field: float, *, noise: float, rng: random.Random) -> dict[str, float]:
    f1 = max(0.0, min(1.0, center_field + rng.gauss(0.0, noise)))
    return {
        "energy_signal": max(0.0, min(1.0, 0.45 + 0.05 * (f1 - 0.5) + rng.gauss(0, noise * 0.25))),
        "hydration_signal": 0.70,
        "fatigue_signal": max(0.0, min(1.0, 0.22 + rng.gauss(0, noise * 0.25))),
        "discomfort_signal": 0.05,
        "field_1": f1,
        "field_2": max(0.0, min(1.0, 1.0 - f1 + rng.gauss(0, noise * 0.15))),
        "resistance": max(0.0, min(1.0, 0.3 + 0.4 * f1 + rng.gauss(0, noise * 0.2))),
    }


def regime_vec(vec: tuple[float, float, float], *, noise: float, rng: random.Random) -> dict[str, float]:
    a, b, r = vec
    return {
        "energy_signal": max(0.0, min(1.0, 0.45 + rng.gauss(0, noise * 0.2))),
        "hydration_signal": 0.70, "fatigue_signal": 0.22, "discomfort_signal": 0.05,
        "field_1": max(0.0, min(1.0, a + rng.gauss(0, noise))),
        "field_2": max(0.0, min(1.0, b + rng.gauss(0, noise))),
        "resistance": max(0.0, min(1.0, r + rng.gauss(0, noise))),
    }


def empty_mm_store(**kw) -> dict[str, Any]:
    s = pc.empty_store()
    s["enable_components"] = True
    s["component_decay"] = True
    s["ablate_components"] = False
    s.update(kw)
    return s


def acquire_stream(store, *, antecedent, action, sample_fn, n, tick0=1) -> int:
    tick = tick0
    for _ in range(n):
        learn_transition_mm(store, tick=tick, antecedent=antecedent, action=action, consequent=sample_fn())
        tick += 1
    return tick


def nearest_regime_distance(pred, regimes):
    if pred is None or not regimes:
        return None
    return min(_frag_l1(pred, r) for r in regimes)


def centers_f1(pred):
    return [float((c.get("center") or {}).get("field_1", 0.0)) for c in pred.get("components") or []]


def true_regime_frags(centers):
    return [regime(c, noise=0.0, rng=random.Random(0)) for c in centers]


def run_unimodal(*, seed, n=400, noise=0.02):
    rng = random.Random(seed)
    store = empty_mm_store()
    S, A, mu = base_S(), "A0", 0.55
    acquire_stream(store, antecedent=S, action=A, n=n, sample_fn=lambda: regime(mu, noise=noise, rng=rng))
    pred = predict_components(store, S, A)
    return {"condition": "unimodal", "n": n, "n_supported": pred["n_supported"],
            "centers_field1": centers_f1(pred), "legacy_field1": float((pred.get("legacy_mean") or {}).get("field_1", 0)),
            "true_mu": mu, "pred": pred, "memory": memory_bytes_estimate(store), "store": store}


def run_bimodal(*, seed, n=400, noise=0.02, p_right=0.5, left=0.15, right=0.85, **store_kw):
    rng = random.Random(seed)
    store = empty_mm_store(**store_kw)
    S, A = base_S(), "A0"
    def sample():
        return regime(right if rng.random() < p_right else left, noise=noise, rng=rng)
    acquire_stream(store, antecedent=S, action=A, n=n, sample_fn=sample)
    pred = predict_components(store, S, A)
    regs = true_regime_frags([left, right])
    legacy = pred.get("legacy_mean")
    return {"condition": "bimodal", "n": n, "p_right": p_right, "n_supported": pred["n_supported"],
            "centers_field1": centers_f1(pred),
            "weights": [c.get("empirical_weight") for c in pred.get("components") or []],
            "legacy_field1": float((legacy or {}).get("field_1", 0)),
            "legacy_nearest_regime_distance": nearest_regime_distance(legacy, regs),
            "component_nearest_regime_distances": [
                nearest_regime_distance(c.get("center"), regs) for c in pred.get("components") or []],
            "true_centers": [left, right], "pred": pred, "memory": memory_bytes_estimate(store),
            "store": store, "fictitious_mean": abs(float((legacy or {}).get("field_1", 0.5)) - 0.5) < 0.12}


def run_trimodal(*, seed, n=600, noise=0.02):
    rng = random.Random(seed)
    store = empty_mm_store()
    S, A = base_S(), "A0"
    centers = [0.12, 0.50, 0.88]
    acquire_stream(store, antecedent=S, action=A, n=n,
                   sample_fn=lambda: regime(rng.choice(centers), noise=noise, rng=rng))
    pred = predict_components(store, S, A)
    return {"condition": "trimodal", "n_supported": pred["n_supported"], "centers_field1": centers_f1(pred),
            "true_centers": centers, "legacy_field1": float((pred.get("legacy_mean") or {}).get("field_1", 0)),
            "pred": pred, "memory": memory_bytes_estimate(store), "store": store}


def run_broad(*, seed, n=400, noise=0.28):
    rng = random.Random(seed)
    store = empty_mm_store()
    S, A, mu = base_S(), "A0", 0.50
    acquire_stream(store, antecedent=S, action=A, n=n, sample_fn=lambda: regime(mu, noise=noise, rng=rng))
    pred = predict_components(store, S, A)
    return {"condition": "broad_unimodal", "n_supported": pred["n_supported"], "centers_field1": centers_f1(pred),
            "legacy_field1": float((pred.get("legacy_mean") or {}).get("field_1", 0)), "noise": noise,
            "pred": pred, "memory": memory_bytes_estimate(store), "store": store}


def run_appearance(*, seed, n1=300, n2=300):
    rng = random.Random(seed)
    store = empty_mm_store()
    S, A = base_S(), "A0"
    hist = []
    tick = 1
    for _ in range(n1):
        learn_transition_mm(store, tick=tick, antecedent=S, action=A, consequent=regime(0.20, noise=0.02, rng=rng))
        tick += 1
        hist.append({"t": tick, "n": predict_components(store, S, A)["n_supported"]})
    n_after_phase1 = predict_components(store, S, A)["n_supported"]
    for _ in range(n2):
        c = 0.20 if rng.random() < 0.5 else 0.85
        learn_transition_mm(store, tick=tick, antecedent=S, action=A, consequent=regime(c, noise=0.02, rng=rng))
        tick += 1
        hist.append({"t": tick, "n": predict_components(store, S, A)["n_supported"]})
    pred = predict_components(store, S, A)
    appear = next((h["t"] for h in hist[n1:] if h["n"] >= 2), None)
    return {"n_after_phase1": n_after_phase1, "n_final": pred["n_supported"], "appear_tick": appear,
            "centers_field1": centers_f1(pred), "pred": pred, "store": store}


def run_disappearance(*, seed, n1=400, n2=500):
    """C6 operational criterion (pre-registered): after C2 stops, either
    (a) n_supported drops to 1 with remaining center near surviving regime, OR
    (b) weight of vanished-regime-nearest component falls by >= 0.25 absolute.
    Persistence of a near-equal second component is NOT ASSERTED adaptation."""
    rng = random.Random(seed)
    store = empty_mm_store()
    S, A = base_S(), "A0"
    tick = 1
    for _ in range(n1):
        c = 0.15 if rng.random() < 0.5 else 0.85
        learn_transition_mm(store, tick=tick, antecedent=S, action=A, consequent=regime(c, noise=0.02, rng=rng))
        tick += 1
    mid = predict_components(store, S, A)
    w_mid = {round(float((c.get("center") or {}).get("field_1", 0)), 2): c.get("empirical_weight")
             for c in mid.get("components") or []}
    for _ in range(n2):
        learn_transition_mm(store, tick=tick, antecedent=S, action=A, consequent=regime(0.15, noise=0.02, rng=rng))
        tick += 1
    fin = predict_components(store, S, A)
    # weight on component nearest 0.85
    def w_near(pred, target):
        comps = pred.get("components") or []
        if not comps:
            return 0.0
        best = min(comps, key=lambda c: abs(float((c.get("center") or {}).get("field_1", 0)) - target))
        # only count if actually near
        if abs(float((best.get("center") or {}).get("field_1", 0)) - target) > 0.2:
            return 0.0
        return float(best.get("empirical_weight") or 0.0)
    w85_mid = w_near(mid, 0.85)
    w85_fin = w_near(fin, 0.85)
    adapted = (fin["n_supported"] == 1 and abs(centers_f1(fin)[0] - 0.15) < 0.15) or (w85_mid - w85_fin >= 0.25)
    return {"n_mid": mid["n_supported"], "n_final": fin["n_supported"], "w85_mid": w85_mid, "w85_fin": w85_fin,
            "adapted": bool(adapted), "centers_final": centers_f1(fin), "pred_final": fin, "store": store}


def run_drift(*, seed, n=500):
    rng = random.Random(seed)
    store = empty_mm_store()
    S, A = base_S(), "A0"
    tick = 1
    for i in range(n):
        mu = 0.20 + 0.60 * (i / max(1, n - 1))  # slow drift 0.2 -> 0.8
        learn_transition_mm(store, tick=tick, antecedent=S, action=A, consequent=regime(mu, noise=0.02, rng=rng))
        tick += 1
    pred = predict_components(store, S, A)
    return {"n_supported": pred["n_supported"], "centers_field1": centers_f1(pred), "pred": pred, "store": store}


def run_capacity_pressure(*, seed, n=800, n_regimes=6):
    rng = random.Random(seed)
    store = empty_mm_store()  # MAX_COMPONENTS=4
    S, A = base_S(), "A0"
    centers = [0.08 + i * (0.84 / (n_regimes - 1)) for i in range(n_regimes)]
    acquire_stream(store, antecedent=S, action=A, n=n,
                   sample_fn=lambda: regime(rng.choice(centers), noise=0.015, rng=rng))
    pred = predict_components(store, S, A)
    return {"n_regimes": n_regimes, "capacity": MAX_COMPONENTS, "n_supported": pred["n_supported"],
            "centers_field1": centers_f1(pred), "n_raw": pred["n_raw"], "pred": pred,
            "memory": memory_bytes_estimate(store), "store": store}


def run_outlier(*, seed, n=400):
    rng = random.Random(seed)
    store = empty_mm_store()
    S, A = base_S(), "A0"
    tick = 1
    for _ in range(n // 2):
        learn_transition_mm(store, tick=tick, antecedent=S, action=A, consequent=regime(0.50, noise=0.02, rng=rng))
        tick += 1
    # one extreme
    learn_transition_mm(store, tick=tick, antecedent=S, action=A, consequent=regime(0.98, noise=0.0, rng=rng))
    tick += 1
    for _ in range(n // 2):
        learn_transition_mm(store, tick=tick, antecedent=S, action=A, consequent=regime(0.50, noise=0.02, rng=rng))
        tick += 1
    pred = predict_components(store, S, A)
    return {"n_supported": pred["n_supported"], "centers_field1": centers_f1(pred), "pred": pred, "store": store}


def run_multidim(*, seed, n=400):
    rng = random.Random(seed)
    store = empty_mm_store()
    S, A = base_S(), "A0"
    v1, v2 = (0.15, 0.85, 0.25), (0.85, 0.15, 0.75)
    acquire_stream(store, antecedent=S, action=A, n=n,
                   sample_fn=lambda: regime_vec(v1 if rng.random() < 0.5 else v2, noise=0.02, rng=rng))
    pred = predict_components(store, S, A)
    return {"n_supported": pred["n_supported"], "components": pred["components"], "pred": pred, "store": store}


def run_scaling(*, seed, ns=(200, 1000, 5000)):
    rows = []
    for n in ns:
        bi = run_bimodal(seed=seed, n=n)
        uni = run_unimodal(seed=seed, n=n)
        rows.append({"n": n, "bimodal_bytes": bi["memory"]["transition_store_bytes"],
                     "bimodal_n_comp": bi["n_supported"],
                     "unimodal_bytes": uni["memory"]["transition_store_bytes"],
                     "unimodal_n_comp": uni["n_supported"]})
    return rows


def passive_prospection_diagnostic(store):
    """Show legacy distal still mean-like; multimodal not propagated."""
    S, A = base_S(), "A0"
    step = pc.predict_one_step(store, S, A)
    comps = predict_components(store, S, A)
    return {
        "MULTIMODAL_ACQUISITION": "SUPPORTED" if comps["n_supported"] >= 2 else "NOT SUPPORTED",
        "MULTIMODAL_PROSPECTIVE_PROPAGATION": "NOT SUPPORTED",
        "legacy_predict_one_step": step.get("predicted"),
        "n_components": comps["n_supported"],
        "note": "predict_one_step still returns legacy mean; compose unchanged",
    }
