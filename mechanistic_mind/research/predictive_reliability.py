"""Update 4.29 - Predictive reliability / conflicting evidence vs action.

Does NOT add UNCERTAINTY/CONFIDENCE/RISK/VARIANCE_AVERSION into cognition.
Uses existing 4.23 transitions (mean + var_sum) and unchanged 4.26
ordinary_state_value -> action_logits pathway.

Researcher metrics may read var_sum / reliability(); action_logits does not.
"""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import prospective_consequence_influence as pci

FORBIDDEN = (
    "UNCERTAINTY", "CONFIDENCE", "DOUBT", "RISK", "TRUST", "RELIABILITY_SCORE",
    "AMBIGUITY", "CONFLICT_AVERSION", "VARIANCE_AVERSION", "ENTROPY_PREFERENCE",
    "INFORMATION_GAIN", "CURIOSITY", "EXPLORATION_BONUS", "SAFE_CHOICE", "RISKY_CHOICE",
    "CAUTIOUS", "ANXIETY", "METACOGNITION",
)

# Pre-registered tolerance for matched expected ordinary_value.
# ordinary_value for B_PLUS vs B_MINUS spans roughly ~0.25 on this organism;
# 0.02 is < ~8% of that span and below typical softmax-visible logit gaps at T=1.25.
MATCHED_MEAN_TOLERANCE = 0.02


def audit_forbidden(payload: Any) -> list[str]:
    return [t for t in FORBIDDEN if t in str(payload)]


def body(energy: float, hydration: float, fatigue: float, discomfort: float) -> dict[str, float]:
    return {
        "energy_signal": float(energy),
        "hydration_signal": float(hydration),
        "fatigue_signal": float(fatigue),
        "discomfort_signal": float(discomfort),
    }


def outcome_catalog() -> dict[str, dict[str, float]]:
    """Physical distal outcomes (Observer labels only)."""
    return {
        "F_hi": pci.B_PLUS(),
        "F_lo": pci.B_MINUS(),
        "F_mid": {
            "energy_signal": 0.45,
            "hydration_signal": 0.70,
            "fatigue_signal": 0.25,
            "discomfort_signal": 0.08,
        },
        "F_mid_hi": {
            "energy_signal": 0.62,
            "hydration_signal": 0.73,
            "fatigue_signal": 0.16,
            "discomfort_signal": 0.05,
        },
        "F_mid_lo": {
            "energy_signal": 0.28,
            "hydration_signal": 0.60,
            "fatigue_signal": 0.40,
            "discomfort_signal": 0.16,
        },
    }


def weighted_mean(pairs: list[tuple[dict[str, float], float]]) -> dict[str, float]:
    wsum = sum(w for _, w in pairs) or 1.0
    keys = set()
    for p, _ in pairs:
        keys |= set(p)
    return {k: sum(float(p.get(k, 0.0)) * w for p, w in pairs) / wsum for k in keys}


def channel_var(pairs: list[tuple[dict[str, float], float]], mean: dict[str, float]) -> dict[str, float]:
    wsum = sum(w for _, w in pairs) or 1.0
    out = {}
    for k, m in mean.items():
        out[k] = sum(w * (float(p.get(k, 0.0)) - m) ** 2 for p, w in pairs) / wsum
    return out


def train_mixture_chain(
    store: dict[str, Any],
    *,
    action_prefix: str,
    mixture: list[tuple[dict[str, float], int]],
    tick0: int,
    mid1: dict[str, float],
    mid2: dict[str, float],
) -> dict[str, Any]:
    """Train S0--X1-->mid1--X2-->mid2--X3-->distal mixture. Fragments; full seq = 0."""
    a1, a2, a3 = f"{action_prefix}1", f"{action_prefix}2", f"{action_prefix}3"
    start = pci.S0()
    t = tick0
    total = 0
    for distal, n in mixture:
        for _ in range(int(n)):
            pc.learn_transition(store, tick=t, antecedent=start, action=a1, consequent=mid1)
            pc.learn_transition(store, tick=t, antecedent=mid1, action=a2, consequent=mid2)
            pc.learn_transition(store, tick=t, antecedent=mid2, action=a3, consequent=distal)
            t += 1
            total += 1
    pattern = f"S0_{a1}_{a2}_{a3}"
    pc.record_full_sequence_exposure(store, pattern_id=pattern, experienced=False)
    return {
        "prefix": action_prefix,
        "total_terminal_exposures": total,
        "full_sequence_exposure_count": int(
            (store.get("full_sequence_patterns") or {}).get(pattern, {}).get("count") or 0
        ),
        "mixture_counts": [(n, distal) for distal, n in mixture],
    }


def terminal_row(store: dict[str, Any], action: str) -> dict[str, Any] | None:
    for row in (store.get("transitions") or {}).values():
        if row.get("action") == action:
            return row
    return None


def researcher_distribution_metrics(row: dict[str, Any] | None) -> dict[str, Any]:
    """Observer/research only — not fed to action_logits."""
    if not row:
        return {"available": False}
    mean = pc.mean_cons(row)
    n = max(1e-9, float(row.get("n") or 1.0))
    vars_ = {}
    for k, vs in (row.get("var_sum") or {}).items():
        vars_[k] = max(0.0, float(vs) / max(n - 1.0, 1e-9))
    mean_var = sum(vars_.values()) / max(1, len(vars_))
    rel = pc.reliability(row)
    return {
        "available": True,
        "n": n,
        "support": int(row.get("support") or 0),
        "mean_predicted": mean,
        "channel_variance": vars_,
        "mean_variance": mean_var,
        "reliability_fn": rel,  # existing pc.reliability; NOT used by action_logits
        "note": "researcher_only; action_logits uses mean predicted_distal -> ordinary_value only",
    }


def compose_and_value(store: dict[str, Any], seq: list[str], goals: dict[str, Any]) -> dict[str, Any]:
    comp = pci.compose_action_distal(store, seq)
    pred = comp.get("predicted_distal")
    ev = pci.evaluate_distal(pci.S0(), pred, goals)
    return {
        "composition_status": comp.get("status"),
        "depth": comp.get("depth"),
        "predicted_distal": pred,
        "ordinary_value": ev.get("ordinary_value"),
        "prospective_available": bool(ev.get("prospective_available")),
    }


def action_probe(store: dict[str, Any], goals: dict[str, Any], *, seed: int, n: int = 300) -> dict[str, Any]:
    logits = pci.action_logits(store=store, goals=goals)
    empir = pci.sample_actions(logits["probs"], n=n, seed=seed)
    probs = logits.get("probs") or {}
    # Confirm reliability not in logits path
    a_row = (logits.get("actions") or {}).get("A1") or {}
    return {
        "probs": probs,
        "logits": {a: (logits.get("actions") or {}).get(a, {}).get("logit") for a in probs},
        "distal_values": {a: (logits.get("actions") or {}).get(a, {}).get("distal_value") for a in probs},
        "empirical": empir,
        "P_A": float(probs.get("A1", 0.0)),
        "P_B": float(probs.get("B1", 0.0)),
        "P_WAIT": float(probs.get("WAIT", 0.0)),
        "delta_P_A_minus_B": float(probs.get("A1", 0.0)) - float(probs.get("B1", 0.0)),
        "A1_composition_fields": list((a_row.get("composition") or {}).keys()),
        "reliability_in_action_row": "reliability" in a_row or "variance" in a_row,
    }


def build_matched_mean_condition(*, seed: int = 0) -> dict[str, Any]:
    """Primary: different predictive distribution, matched mean predicted distal.

    Quantization-safe construction:
      1) Train B as 50/50 conflicting terminal mixture (high var_sum).
      2) Read B empirical mean_cons (post-quantization).
      3) Train A as 100× that exact mean body (near-zero variance).
    Support counts matched. full_sequence_exposure = 0.
    Expected ordinary_value matches because predicted_distal means match.
    """
    cat = outcome_catalog()
    f_hi = dict(cat["F_hi"])
    f_lo = dict(cat["F_lo"])
    # Prefer extremes that remain distinct after 5-bin quantization
    store = pc.empty_store()
    mid1a, mid2a = pci.S1(), pci.S2()
    mid1b, mid2b = pci.S3(), pci.S4()

    meta_b = train_mixture_chain(
        store, action_prefix="B",
        mixture=[(f_hi, 50), (f_lo, 50)],
        tick0=1000, mid1=mid1b, mid2=mid2b,
    )
    row_b = terminal_row(store, "B3")
    b_mean = pc.mean_cons(row_b) if row_b else dict(cat["F_mid"])

    meta_a = train_mixture_chain(
        store, action_prefix="A",
        mixture=[(b_mean, 100)],
        tick0=1, mid1=mid1a, mid2=mid2a,
    )
    for i in range(20):
        pc.learn_transition(store, tick=5000 + i, antecedent=pci.S0(), action="WAIT",
                            consequent=pci.immediate_consequence("WAIT"))

    goals = pci.default_goals()
    va = compose_and_value(store, ["A1", "A2", "A3"], goals)
    vb = compose_and_value(store, ["B1", "B2", "B3"], goals)
    ea = va.get("ordinary_value")
    eb = vb.get("ordinary_value")
    matched = (
        ea is not None and eb is not None
        and abs(float(ea) - float(eb)) <= MATCHED_MEAN_TOLERANCE
    )
    # If quantization of b_mean as A consequent still drifts, force A terminal mean to B's mean
    # while keeping A var_sum ~ 0 (experimental matching of current predictive mean).
    if not matched:
        row_a = terminal_row(store, "A3")
        row_b = terminal_row(store, "B3")
        if row_a and row_b:
            n = float(row_a.get("n") or 100.0)
            bm = pc.mean_cons(row_b)
            row_a["sum"] = {k: float(bm[k]) * n for k in bm}
            row_a["var_sum"] = {k: 0.0 for k in bm}
            va = compose_and_value(store, ["A1", "A2", "A3"], goals)
            vb = compose_and_value(store, ["B1", "B2", "B3"], goals)
            ea = va.get("ordinary_value")
            eb = vb.get("ordinary_value")
            matched = (
                ea is not None and eb is not None
                and abs(float(ea) - float(eb)) <= MATCHED_MEAN_TOLERANCE
            )

    row_a = terminal_row(store, "A3")
    row_b = terminal_row(store, "B3")
    met_a = researcher_distribution_metrics(row_a)
    met_b = researcher_distribution_metrics(row_b)
    dist_differs = (
        met_a.get("available") and met_b.get("available")
        and abs(float(met_a["mean_variance"]) - float(met_b["mean_variance"])) > 1e-4
    )
    return {
        "store": store,
        "goals": goals,
        "meta_a": meta_a,
        "meta_b": meta_b,
        "designed_a_mean": b_mean,
        "designed_b_mean": b_mean,
        "b_extreme_partner": f_lo,
        "value_A": ea,
        "value_B": eb,
        "abs_value_diff": None if ea is None or eb is None else abs(float(ea) - float(eb)),
        "matched_mean": matched,
        "tolerance": MATCHED_MEAN_TOLERANCE,
        "tolerance_rationale": (
            "0.02 absolute on ordinary_value; <~8% of B_PLUS vs B_MINUS value span; "
            "chosen before seeing action deltas. Mean-match may apply post-quantization "
            "alignment of A terminal sum to B mean while preserving A var~0 / B var>0."
        ),
        "dist_A": met_a,
        "dist_B": met_b,
        "distributions_differ": dist_differs,
        "compose_A": va,
        "compose_B": vb,
        "support_A": int(met_a.get("support") or 0),
        "support_B": int(met_b.get("support") or 0),
        "support_matched": abs(int(met_a.get("support") or 0) - int(met_b.get("support") or 0)) <= 5,
    }


def build_matched_distribution_control() -> dict[str, Any]:
    """Negative control: same mixture on A and B (matched mean AND distribution)."""
    cat = outcome_catalog()
    store = pc.empty_store()
    mix = [(cat["F_mid_hi"], 70), (cat["F_mid_lo"], 30)]
    train_mixture_chain(store, action_prefix="A", mixture=mix, tick0=1, mid1=pci.S1(), mid2=pci.S2())
    train_mixture_chain(store, action_prefix="B", mixture=list(mix), tick0=1000, mid1=pci.S3(), mid2=pci.S4())
    for i in range(20):
        pc.learn_transition(store, tick=5000 + i, antecedent=pci.S0(), action="WAIT",
                            consequent=pci.immediate_consequence("WAIT"))
    goals = pci.default_goals()
    va = compose_and_value(store, ["A1", "A2", "A3"], goals)
    vb = compose_and_value(store, ["B1", "B2", "B3"], goals)
    return {
        "store": store,
        "goals": goals,
        "value_A": va.get("ordinary_value"),
        "value_B": vb.get("ordinary_value"),
        "abs_value_diff": abs(float(va["ordinary_value"]) - float(vb["ordinary_value"]))
        if va.get("ordinary_value") is not None and vb.get("ordinary_value") is not None else None,
        "dist_A": researcher_distribution_metrics(terminal_row(store, "A3")),
        "dist_B": researcher_distribution_metrics(terminal_row(store, "B3")),
    }


def build_different_mean_control() -> dict[str, Any]:
    """4.26-style: A -> F_lo, B -> F_hi (clear mean difference)."""
    store = pc.empty_store()
    train_mixture_chain(
        store, action_prefix="A", mixture=[(pci.B_MINUS(), 80)], tick0=1, mid1=pci.S1(), mid2=pci.S2()
    )
    train_mixture_chain(
        store, action_prefix="B", mixture=[(pci.B_PLUS(), 80)], tick0=1000, mid1=pci.S3(), mid2=pci.S4()
    )
    for i in range(20):
        pc.learn_transition(store, tick=5000 + i, antecedent=pci.S0(), action="WAIT",
                            consequent=pci.immediate_consequence("WAIT"))
    goals = pci.default_goals()
    va = compose_and_value(store, ["A1", "A2", "A3"], goals)
    vb = compose_and_value(store, ["B1", "B2", "B3"], goals)
    return {
        "store": store,
        "goals": goals,
        "value_A": va.get("ordinary_value"),
        "value_B": vb.get("ordinary_value"),
        "abs_value_diff": abs(float(va["ordinary_value"]) - float(vb["ordinary_value"]))
        if va.get("ordinary_value") is not None and vb.get("ordinary_value") is not None else None,
    }


def shuffle_terminal_outcomes(store: dict[str, Any], *, seed: int = 0) -> dict[str, Any]:
    """Decorrelate: swap A3/B3 learned means&vars by exchanging terminal rows' stats."""
    import random
    s = deepcopy(store)
    ra = terminal_row(s, "A3")
    rb = terminal_row(s, "B3")
    if not ra or not rb:
        return s
    # shuffle by averaging both into each (destroy structure difference) while keeping combined mean
    # Better: permute by swapping sum/var between A and B
    for key in ("sum", "var_sum", "n", "support"):
        ra[key], rb[key] = deepcopy(rb[key]), deepcopy(ra[key])
    return s


def mean_only_baseline(store: dict[str, Any]) -> dict[str, Any]:
    """Ablate distribution: zero var_sum on terminals; preserve means. Action path unchanged (already mean-only)."""
    s = deepcopy(store)
    for act in ("A3", "B3"):
        row = terminal_row(s, act)
        if row and isinstance(row.get("var_sum"), dict):
            row["var_sum"] = {k: 0.0 for k in row["var_sum"]}
    return s


def ablate_multi_outcome_to_single(store: dict[str, Any], action: str, distal: dict[str, float]) -> dict[str, Any]:
    """Replace terminal mixture with single mean outcome (n preserved)."""
    s = deepcopy(store)
    row = terminal_row(s, action)
    if not row:
        return s
    n = float(row.get("n") or 1.0)
    mean = pc.mean_cons(row)
    # collapse to single point at mean
    row["sum"] = {k: float(mean[k]) * n for k in mean}
    row["var_sum"] = {k: 0.0 for k in mean}
    return s
