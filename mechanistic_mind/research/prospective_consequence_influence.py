"""Update 4.26 - Prospective consequence influence on present action.

Tests whether predicted distal physical/body consequences can causally alter
present action selection WITHOUT goal/desire/reward-maximizer semantics.

Interface (documented Category A/B):
  - Use Update 4.23 prospective_composition for distal predictions.
  - Evaluate predicted body states with existing prospective_ordinary_value /
    ordinary_state_value (Update 4.5 / 4.18 organism target-error semantics).
  - Blend into stochastic action sampling (softmax), NEVER argmax.
  - Immediate and distal contributions use the SAME valuation function.
  - Distal contribution is gated by composition availability; ablatable.

This permits influence; it does not force the experimentally preferred action.
"""
from __future__ import annotations

import math
import random
from copy import deepcopy
from typing import Any

from mechanistic_mind.research import prospective_composition as pcomp
from mechanistic_mind.research.composed_future_value import ordinary_state_value

FORBIDDEN = (
    "GOAL", "TARGET", "DESIRE", "WANT", "WANT_NOT", "PREFERENCE", "FUTURE_PREFERENCE",
    "PLAN", "STRATEGY", "INTENTION", "PURPOSE", "AVOID", "SEEK", "FEAR", "HOPE",
    "EXPECTED_REWARD", "FUTURE_REWARD", "DISCOUNTED_REWARD", "VALUE_FUNCTION",
    "UTILITY", "BEST_PATH", "WORST_PATH", "GOOD_FUTURE", "BAD_FUTURE",
    "DESIRED_STATE", "DESIRED_FUTURE", "DISTAL_REWARD", "DISTAL_PENALTY",
    "REPLAN", "SACRIFICE", "LONG_TERM_GOAL", "GOOD", "BAD", "CONSEQUENCE_SCORE",
    "DISTAL_VALUE", "WORLD_CHANGED", "VALUES_CHANGED", "GOOD_PATH_CHANGED",
    "BAD_PATH_CHANGED", "REVERSAL", "NEW_GOAL",
)

# Softmax temperature: higher => weaker distal influence (non-guaranteeing).
DEFAULT_TEMPERATURE = 1.25
# Relative weight of distal ordinary value vs immediate when both available.
DISTAL_BLEND = 0.55


def audit_forbidden(payload: Any) -> list[str]:
    text = str(payload)
    return [t for t in FORBIDDEN if t in text]


def default_goals() -> dict[str, Any]:
    """Reuse organism v03 goals if available; else minimal physical targets."""
    try:
        from mechanistic_mind.psyche.state import PsycheState
        return dict(PsycheState.initial_organism_v03().goals)
    except Exception:
        return {
            "signal_targets": {
                "energy_signal": 0.7,
                "hydration_signal": 0.7,
                "fatigue_signal": 0.2,
                "discomfort_signal": 0.05,
            },
            "signal_weights": {
                "energy_signal": 1.0,
                "hydration_signal": 1.0,
                "fatigue_signal": 0.8,
                "discomfort_signal": 0.5,
            },
        }


def S0() -> dict[str, float]:
    return {
        "energy_signal": 0.45,
        "hydration_signal": 0.72,
        "fatigue_signal": 0.20,
        "discomfort_signal": 0.05,
    }


def S1() -> dict[str, float]:
    return {"energy_signal": 0.44, "hydration_signal": 0.72, "fatigue_signal": 0.21, "discomfort_signal": 0.05}


def S2() -> dict[str, float]:
    return {"energy_signal": 0.42, "hydration_signal": 0.71, "fatigue_signal": 0.23, "discomfort_signal": 0.06}


def B_MINUS() -> dict[str, float]:
    """Researcher notation only - depleted distal body outcome."""
    return {"energy_signal": 0.15, "hydration_signal": 0.55, "fatigue_signal": 0.55, "discomfort_signal": 0.25}


def S3() -> dict[str, float]:
    return {"energy_signal": 0.44, "hydration_signal": 0.72, "fatigue_signal": 0.21, "discomfort_signal": 0.05}


def S4() -> dict[str, float]:
    return {"energy_signal": 0.43, "hydration_signal": 0.71, "fatigue_signal": 0.22, "discomfort_signal": 0.06}


def B_PLUS() -> dict[str, float]:
    """Researcher notation only - restored distal body outcome."""
    return {"energy_signal": 0.78, "hydration_signal": 0.75, "fatigue_signal": 0.12, "discomfort_signal": 0.03}


def empty_world_cfg() -> dict[str, Any]:
    return {
        "A_chain": [("A1", S1()), ("A2", S2()), ("A3", B_MINUS())],
        "B_chain": [("B1", S3()), ("B2", S4()), ("B3", B_PLUS())],
        "full_A_exposure": 0,
        "full_B_exposure": 0,
        "ablate_composition": False,
        "ablate_distal_link_A": False,
        "ablate_distal_link_B": False,
        "neutralize_distal": False,
        "shuffle_distal": False,
    }


def train_fragments(store: dict[str, Any], cfg: dict[str, Any], *, n: int = 40, seed: int = 17) -> dict[str, Any]:
    """Learn chain fragments independently. Never log full end-to-end exposure."""
    rng = random.Random(seed)
    start = S0()
    # Immediate matched transitions
    for t in range(1, n + 1):
        # A branch fragments
        if not cfg.get("ablate_distal_link_A"):
            pcomp.learn_transition(store, tick=t, antecedent=start, action="A1", consequent=S1())
            pcomp.learn_transition(store, tick=t, antecedent=S1(), action="A2", consequent=S2())
            distal_a = S2() if cfg.get("neutralize_distal") else (
                B_PLUS() if cfg.get("shuffle_distal") else B_MINUS()
            )
            if cfg.get("neutralize_distal"):
                # both ends matched mid-body
                distal_a = {"energy_signal": 0.45, "hydration_signal": 0.70, "fatigue_signal": 0.25, "discomfort_signal": 0.08}
            pcomp.learn_transition(store, tick=t, antecedent=S2(), action="A3", consequent=distal_a)
        else:
            pcomp.learn_transition(store, tick=t, antecedent=start, action="A1", consequent=S1())
            pcomp.learn_transition(store, tick=t, antecedent=S1(), action="A2", consequent=S2())
            # no A3 link
        # B branch
        if not cfg.get("ablate_distal_link_B"):
            pcomp.learn_transition(store, tick=t, antecedent=start, action="B1", consequent=S3())
            pcomp.learn_transition(store, tick=t, antecedent=S3(), action="B2", consequent=S4())
            distal_b = S4() if cfg.get("neutralize_distal") else (
                B_MINUS() if cfg.get("shuffle_distal") else B_PLUS()
            )
            if cfg.get("neutralize_distal"):
                distal_b = {"energy_signal": 0.45, "hydration_signal": 0.70, "fatigue_signal": 0.25, "discomfort_signal": 0.08}
            pcomp.learn_transition(store, tick=t, antecedent=S4(), action="B3", consequent=distal_b)
        else:
            pcomp.learn_transition(store, tick=t, antecedent=start, action="B1", consequent=S3())
            pcomp.learn_transition(store, tick=t, antecedent=S3(), action="B2", consequent=S4())
        # WAIT local
        pcomp.learn_transition(store, tick=t, antecedent=start, action="WAIT",
                               consequent={"energy_signal": 0.44, "hydration_signal": 0.71,
                                           "fatigue_signal": 0.21, "discomfort_signal": 0.05})
    pcomp.record_full_sequence_exposure(store, pattern_id="S0_A1_A2_A3", experienced=False)
    pcomp.record_full_sequence_exposure(store, pattern_id="S0_B1_B2_B3", experienced=False)
    cfg["full_A_exposure"] = int((store.get("full_sequence_patterns") or {}).get("S0_A1_A2_A3", {}).get("count") or 0)
    cfg["full_B_exposure"] = int((store.get("full_sequence_patterns") or {}).get("S0_B1_B2_B3", {}).get("count") or 0)
    return {"exposure_A": cfg["full_A_exposure"], "exposure_B": cfg["full_B_exposure"], "noise": rng.random()}


def compose_action_distal(store: dict[str, Any], action_seq: list[str], *, ablate_composition: bool = False) -> dict[str, Any]:
    s = store
    if ablate_composition:
        s = deepcopy(store)
        s["ablate_composition"] = True
    return pcomp.distal_prediction(s, start=S0(), action_seq=action_seq)


def evaluate_distal(start: dict[str, float], predicted: dict[str, float] | None, goals: dict[str, Any]) -> dict[str, Any]:
    if not predicted:
        return {"ordinary_value": None, "prospective_available": False}
    return ordinary_state_value(start=start, terminal=predicted, goals=goals)


def immediate_consequence(action: str) -> dict[str, float]:
    """Matched immediate body consequence for A1/B1/WAIT."""
    if action in ("A1", "B1"):
        return {"energy_signal": 0.44, "hydration_signal": 0.72, "fatigue_signal": 0.21, "discomfort_signal": 0.05}
    if action == "WAIT":
        return {"energy_signal": 0.44, "hydration_signal": 0.71, "fatigue_signal": 0.21, "discomfort_signal": 0.05}
    return dict(S0())


def action_logits(
    *,
    store: dict[str, Any],
    goals: dict[str, Any],
    actions: list[str] | None = None,
    use_distal: bool = True,
    ablate_composition: bool = False,
    temperature: float = DEFAULT_TEMPERATURE,
) -> dict[str, Any]:
    """Generic stochastic interface.

    logit(a) = immediate_ordinary_value(a) + DISTAL_BLEND * distal_ordinary_value(a)
    when distal composition available and use_distal True.
    Selection is softmax sampling - not argmax, not forced preference.
    """
    actions = actions or ["A1", "B1", "WAIT"]
    start = S0()
    rows = {}
    for a in actions:
        imm_state = immediate_consequence(a)
        imm = ordinary_state_value(start=start, terminal=imm_state, goals=goals)
        imm_v = float(imm.get("ordinary_value") or 0.0)

        distal_v = None
        comp = None
        if a == "A1":
            seq = ["A1", "A2", "A3"]
        elif a == "B1":
            seq = ["B1", "B2", "B3"]
        else:
            seq = ["WAIT"]
        if use_distal and a != "WAIT":
            comp = compose_action_distal(store, seq, ablate_composition=ablate_composition)
            if comp.get("status") == "COMPOSED" and not ablate_composition:
                ev = evaluate_distal(start, comp.get("predicted_distal"), goals)
                if ev.get("prospective_available"):
                    distal_v = float(ev.get("ordinary_value") or 0.0)
        logit = imm_v
        if distal_v is not None and use_distal:
            logit = imm_v + DISTAL_BLEND * distal_v
        rows[a] = {
            "immediate_value": imm_v,
            "distal_value": distal_v,
            "logit": logit,
            "composition": {
                "status": None if comp is None else comp.get("status"),
                "depth": None if comp is None else comp.get("depth"),
                "predicted_distal": None if comp is None else comp.get("predicted_distal"),
            },
        }
    # softmax
    xs = [rows[a]["logit"] / max(1e-6, temperature) for a in actions]
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    z = sum(exps) or 1.0
    probs = {a: exps[i] / z for i, a in enumerate(actions)}
    return {
        "actions": rows,
        "probs": probs,
        "temperature": temperature,
        "distal_blend": DISTAL_BLEND,
        "use_distal": use_distal,
        "interface": "softmax(immediate_ordinary + blend*distal_ordinary); NOT argmax; same valuation fn",
        "leak_tokens": audit_forbidden(rows),
    }


def sample_actions(probs: dict[str, float], *, n: int, seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    acts = list(probs.keys())
    weights = [probs[a] for a in acts]
    counts = {a: 0 for a in acts}
    for _ in range(n):
        # roulette
        u = rng.random()
        cum = 0.0
        chosen = acts[-1]
        for a, w in zip(acts, weights):
            cum += w
            if u <= cum:
                chosen = a
                break
        counts[chosen] += 1
    return {a: counts[a] / max(1, n) for a in acts}


def snapshot_interface() -> dict[str, Any]:
    return {
        "CATEGORY_A": [
            "existing ordinary_state_value / prospective_ordinary_value reused",
            "4.23 distal_prediction reused",
            "softmax stochastic selection (not argmax)",
        ],
        "CATEGORY_B": [
            "distal ordinary value may blend into logits when composition available",
        ],
        "NOT_IMPLEMENTED": list(FORBIDDEN[:20]),
        "DISTAL_BLEND": DISTAL_BLEND,
        "DEFAULT_TEMPERATURE": DEFAULT_TEMPERATURE,
    }
