"""Update 4.28 - Competing predictive continuations.

No HABIT/BELIEF/COMMITMENT/CONFIDENCE/ENTRENCHMENT/SWITCHING_COST in cognition.
Uses existing 4.23 composition + 4.26 ordinary_state_value -> softmax pathway.
Historical support is operationalized only as ordinary learn_transition counts.
"""
from __future__ import annotations

import math
import random
from copy import deepcopy
from typing import Any

from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import prospective_consequence_influence as pci

FORBIDDEN = (
    "HABIT", "HABIT_STRENGTH", "ROUTINE", "BELIEF", "BELIEF_STRENGTH", "CONFIDENCE",
    "TRUST", "CERTAINTY", "ENTRENCHMENT", "COMMITMENT", "RESISTANCE", "INERTIA",
    "STATUS_QUO", "FAMILIAR", "NOVEL", "OLD_SCENARIO", "NEW_SCENARIO", "SWITCH",
    "SWITCHING_COST", "CHANGE_MIND", "PERSIST", "CONFLICT", "SCENARIO_WINNER",
    "STUBBORNNESS", "STATUS_QUO_BIAS", "FAMILIARITY_PREFERENCE", "NOVELTY_PREFERENCE",
)


def audit_forbidden(payload: Any) -> list[str]:
    return [t for t in FORBIDDEN if t in str(payload)]


def F_neutral() -> dict[str, float]:
    return {"energy_signal": 0.45, "hydration_signal": 0.70, "fatigue_signal": 0.25, "discomfort_signal": 0.08}


def distal_levels() -> dict[str, dict[str, float]]:
    """Observer-side labels only; cognition sees body vectors."""
    return {
        "much_less": {"energy_signal": 0.10, "hydration_signal": 0.50, "fatigue_signal": 0.65, "discomfort_signal": 0.30},
        "slightly_less": {"energy_signal": 0.25, "hydration_signal": 0.58, "fatigue_signal": 0.45, "discomfort_signal": 0.18},
        "equal": dict(F_neutral()),
        "slightly_more": {"energy_signal": 0.62, "hydration_signal": 0.72, "fatigue_signal": 0.18, "discomfort_signal": 0.06},
        "substantially_more": dict(pci.B_PLUS()),
    }


def learn_A_direct(store: dict[str, Any], *, n: int, distal: dict[str, float] | None = None, tick0: int = 1) -> int:
    """Historically established A continuation via repeated fragment+terminal learning.
    When n>0, also records full-sequence exposure for A (end-to-end experienced).
    """
    distal = distal or pci.B_MINUS()
    start = pci.S0()
    for i in range(n):
        t = tick0 + i
        pc.learn_transition(store, tick=t, antecedent=start, action="A1", consequent=pci.S1())
        pc.learn_transition(store, tick=t, antecedent=pci.S1(), action="A2", consequent=pci.S2())
        pc.learn_transition(store, tick=t, antecedent=pci.S2(), action="A3", consequent=distal)
        pc.learn_transition(store, tick=t, antecedent=start, action="WAIT",
                            consequent=pci.immediate_consequence("WAIT"))
        if n > 0:
            pc.record_full_sequence_exposure(store, pattern_id="S0_A1_A2_A3", experienced=True)
    return n


def learn_B_fragments(
    store: dict[str, Any],
    *,
    n: int,
    distal: dict[str, float] | None = None,
    tick0: int = 1000,
    end_to_end: bool = False,
) -> dict[str, int]:
    """B continuation. Default: fragments only, full end-to-end exposure = 0."""
    distal = distal or pci.B_PLUS()
    start = pci.S0()
    for i in range(n):
        t = tick0 + i
        pc.learn_transition(store, tick=t, antecedent=start, action="B1", consequent=pci.S3())
        pc.learn_transition(store, tick=t, antecedent=pci.S3(), action="B2", consequent=pci.S4())
        pc.learn_transition(store, tick=t, antecedent=pci.S4(), action="B3", consequent=distal)
        if end_to_end:
            pc.record_full_sequence_exposure(store, pattern_id="S0_B1_B2_B3", experienced=True)
    if not end_to_end:
        pc.record_full_sequence_exposure(store, pattern_id="S0_B1_B2_B3", experienced=False)
    full = int((store.get("full_sequence_patterns") or {}).get("S0_B1_B2_B3", {}).get("count") or 0)
    return {"fragment_n": n, "full_B_end_to_end_exposure_count": full}


def learn_A_repetition_no_structure(store: dict[str, Any], *, n: int, tick0: int = 1) -> int:
    """Raw A1 executions without stable distal continuation (consequence varies)."""
    start = pci.S0()
    variants = [pci.S1(), pci.S2(), F_neutral(), pci.B_PLUS(), pci.B_MINUS()]
    for i in range(n):
        t = tick0 + i
        # only one-step noisy outcomes — no A2/A3 chain
        pc.learn_transition(store, tick=t, antecedent=start, action="A1", consequent=variants[i % len(variants)])
        pc.learn_transition(store, tick=t, antecedent=start, action="WAIT",
                            consequent=pci.immediate_consequence("WAIT"))
    return n


def full_exposure(store: dict[str, Any], pattern: str) -> int:
    return int((store.get("full_sequence_patterns") or {}).get(pattern, {}).get("count") or 0)


def transition_support(store: dict[str, Any], action: str) -> int:
    """Sum of supports for transitions involving action (ordinary stats)."""
    total = 0
    for row in (store.get("transitions") or {}).values():
        if str(row.get("action") or "") == action:
            total += int(row.get("support") or row.get("n") or 0)
    return total


def candidate_snapshot(store: dict[str, Any], goals: dict[str, Any], *, ablate_composition: bool = False) -> dict[str, Any]:
    """All simultaneously available continuations from S0 (Observer/research)."""
    out = {"candidates": {}}
    for label, seq in (("A", ["A1", "A2", "A3"]), ("B", ["B1", "B2", "B3"]), ("WAIT", ["WAIT"])):
        comp = pci.compose_action_distal(store, seq, ablate_composition=ablate_composition)
        pred = comp.get("predicted_distal")
        ev = pci.evaluate_distal(pci.S0(), pred, goals)
        out["candidates"][label] = {
            "composition_status": comp.get("status"),
            "depth": comp.get("depth"),
            "predicted_distal": pred,
            "ordinary_value": ev.get("ordinary_value"),
            "prospective_available": bool(ev.get("prospective_available")),
            # Observer-only origin hint (never written into store cognition fields)
            "prediction_origin_observer": (
                "DIRECT" if label == "A" and full_exposure(store, "S0_A1_A2_A3") > 0
                else "COMPOSED" if comp.get("status") == "COMPOSED"
                else "NONE"
            ),
        }
    out["A_full_sequence_exposures"] = full_exposure(store, "S0_A1_A2_A3")
    out["B_full_sequence_exposures"] = full_exposure(store, "S0_B1_B2_B3")
    out["A_support_A1"] = transition_support(store, "A1")
    out["B_support_B1"] = transition_support(store, "B1")
    return out


def measure_action(store: dict[str, Any], goals: dict[str, Any], *, seed: int, n: int = 300, **kw) -> dict[str, Any]:
    logits = pci.action_logits(store=store, goals=goals, **kw)
    empir = pci.sample_actions(logits["probs"], n=n, seed=seed)
    probs = logits.get("probs") or {}
    # entropy of action distribution (researcher diagnostic only)
    ent = 0.0
    for p in probs.values():
        p = float(p)
        if p > 1e-12:
            ent -= p * math.log(p)
    return {
        "probs": probs,
        "logits": logits.get("logits"),
        "empirical": empir,
        "P_A": float(probs.get("A1", 0.0)),
        "P_B": float(probs.get("B1", 0.0)),
        "P_WAIT": float(probs.get("WAIT", 0.0)),
        "action_entropy": ent,
        "rows": logits.get("rows"),
    }


def ablate_A_structure(store: dict[str, Any]) -> dict[str, Any]:
    """Selectively remove A-chain transitions; keep B and WAIT."""
    s = deepcopy(store)
    doomed = []
    for k, row in list((s.get("transitions") or {}).items()):
        act = str(row.get("action") or "")
        if act in ("A1", "A2", "A3"):
            doomed.append(k)
    for k in doomed:
        del s["transitions"][k]
    # clear A full-sequence bookkeeping
    fsp = s.setdefault("full_sequence_patterns", {})
    if "S0_A1_A2_A3" in fsp:
        fsp["S0_A1_A2_A3"] = {"count": 0}
    return s


def reduce_A_retrieval(store: dict[str, Any], keep_frac: float = 0.15) -> dict[str, Any]:
    """Reduce A transition support counts (retrieval/strength proxy) without deleting B."""
    s = deepcopy(store)
    for row in (s.get("transitions") or {}).values():
        act = str(row.get("action") or "")
        if act in ("A1", "A2", "A3"):
            for key in ("support", "n", "count"):
                if key in row and isinstance(row[key], (int, float)):
                    row[key] = max(0, int(float(row[key]) * keep_frac))
            # weaken sum stats if present
            if isinstance(row.get("sum"), dict):
                row["sum"] = {k: float(v) * keep_frac for k, v in row["sum"].items()}
    return s


def build_history_store(
    *,
    a_n: int,
    b_fragment_n: int = 0,
    a_distal: dict[str, float] | None = None,
    b_distal: dict[str, float] | None = None,
    b_end_to_end: bool = False,
    seed: int = 0,
) -> dict[str, Any]:
    store = pc.empty_store()
    learn_A_direct(store, n=a_n, distal=a_distal, tick0=1)
    if b_fragment_n > 0:
        learn_B_fragments(store, n=b_fragment_n, distal=b_distal, tick0=5000, end_to_end=b_end_to_end)
    return store


def find_crossover(points: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate first step where P_B >= P_A from an evidence/advantage sweep."""
    for i, p in enumerate(points):
        if float(p.get("P_B", 0)) >= float(p.get("P_A", 0)):
            return {"found": True, "index": i, "point": p}
    return {"found": False, "index": None, "point": None}


def classify_transition(series: list[float], thr: float = 0.05) -> str:
    if len(series) < 2:
        return "insufficient"
    d = series[-1] - series[0]
    osc = sum(1 for i in range(1, len(series)) if (series[i] - series[i - 1]) * (series[i - 1] - (series[i - 2] if i > 1 else series[0])) < 0)
    if abs(d) < thr:
        return "no_transition"
    if osc >= max(2, len(series) // 3):
        return "oscillation"
    # abrupt if most change in one step
    steps = [abs(series[i] - series[i - 1]) for i in range(1, len(series))]
    if steps and max(steps) >= 0.6 * abs(d):
        return "abrupt"
    return "gradual"
