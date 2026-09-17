"""Update 4.25 - Emergent instrumental observation via physical transduction.

No TOOL/INSTRUMENT/INFORMATION/EPISTEMIC semantics in cognition.
World ground truth never enters prediction/action selection.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
from typing import Any

FORBIDDEN = (
    "TOOL", "INSTRUMENT", "MEASUREMENT", "OBSERVATION", "INFORMATION",
    "INFORMATION_GAIN", "MICROSCOPE", "SENSOR_EXTENSION", "UNCERTAINTY",
    "UNCERTAINTY_REDUCTION", "LOOK_CLOSER", "USE_TOOL", "USE_TOOL_TO_KNOW",
    "KNOWLEDGE", "HIDDEN_STATE", "CORRECT_ANSWER", "INVESTIGATE",
    "EXPLORE_FOR_INFORMATION", "EPISTEMIC_VALUE", "EPISTEMIC_REWARD",
    "MEASUREMENT_VALUE", "TOOL_USEFULNESS", "OBSERVATION_OCCURRED",
    "TOOL_USED", "WORLD_REVEALED", "NEW_INFORMATION", "DISCOVERY",
    "TOOL_DISCOVERED", "INFORMATION_ACQUIRED", "MEASUREMENT_SUCCESS",
    "TOOL_REMOVED", "INSTRUMENT_MISSING", "IMPORTANT_OBSERVATION",
    "MEASUREMENT_MEMORY", "TOOL_MEMORY", "BODY_CLOCK", "TIME_SENSE",
    "ELAPSED_TIME", "TEMPORAL_POSITION", "SUBJECTIVE_TIME",
)

# Pre-registered observability thresholds (Observer-side only).
DIRECT_DISTINGUISH_MAX = 0.05   # mean L1 below => not directly discriminable
MEDIATED_DISTINGUISH_MIN = 0.12  # mean L1 above => mediated discriminable
AMP_RATIO_MIN = 1.5             # mediated/direct for AMPLIFIED classification

MAX_PRED = 96
MIN_SUPPORT = 3


def audit_forbidden(payload: Any) -> list[str]:
    text = str(payload)
    return [t for t in FORBIDDEN if t in text]


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


def l1(a: dict[str, float] | None, b: dict[str, float] | None) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    return sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys)


def mean_l1_pairs(samples_a: list[dict[str, float]], samples_b: list[dict[str, float]]) -> float:
    if not samples_a or not samples_b:
        return 0.0
    # pairwise mean against means for stability
    ma = {k: sum(float(s.get(k, 0.0)) for s in samples_a) / len(samples_a)
          for k in set().union(*(s.keys() for s in samples_a))}
    mb = {k: sum(float(s.get(k, 0.0)) for s in samples_b) / len(samples_b)
          for k in set().union(*(s.keys() for s in samples_b))}
    return l1(ma, mb)


# ---------------------------------------------------------------------------
# Physical world (GT) + transducer - researcher physics only
# ---------------------------------------------------------------------------

def world_state(kind: str) -> dict[str, float]:
    """GT only. kind in {A, B}. Never passed to cognition as identity."""
    if kind == "A":
        return {"w_latent": 0.20, "w_noise": 0.50}
    return {"w_latent": 0.80, "w_noise": 0.50}


def direct_observation(w: dict[str, float], *, noise: float = 0.0, rng=None) -> dict[str, float]:
    """Agent-accessible direct sensory: intentionally collapses latent.

    Direct path maps both latents to nearly the same sensory channel.
    """
    # Collapse: only noise-ish ambient; latent cancelled
    base = {"s0": 0.45, "s1": float(w.get("w_noise", 0.5))}
    if rng is not None and noise:
        base = {k: max(0.0, min(1.0, v + rng.uniform(-noise, noise))) for k, v in base.items()}
    return base


def transducer_response(
    w: dict[str, float],
    *,
    mode: str = "useful",
    ablate_world_to_m: bool = False,
    rng=None,
) -> dict[str, float]:
    """Ordinary physical response of object M. No semantic flags.

    mode:
      useful - M state tracks latent
      useless - M state ignores latent (matched interaction surface)
      decorrelated - M varies but independent of latent
    """
    latent = float(w.get("w_latent", 0.5))
    if ablate_world_to_m:
        latent = 0.5  # W no longer changes M differently
    if mode == "useful":
        m = {"m0": latent, "m1": 0.30 + 0.40 * latent}
    elif mode == "useless":
        m = {"m0": 0.50, "m1": 0.50}
    elif mode == "decorrelated":
        # variation unrelated to latent
        u = rng.random() if rng is not None else 0.37
        m = {"m0": u, "m1": 1.0 - u}
    else:
        m = {"m0": 0.50, "m1": 0.50}
    return m


def mediated_observation(
    w: dict[str, float],
    *,
    mode: str = "useful",
    ablate_world_to_m: bool = False,
    ablate_m_to_body: bool = False,
    contact: bool = True,
    rng=None,
) -> dict[str, float]:
    """Body/sensor after ordinary contact with M.

    If contact False or M->BODY ablated: fall back to direct-like observation.
    """
    direct = direct_observation(w, rng=rng)
    if not contact or ablate_m_to_body:
        return dict(direct)
    m = transducer_response(w, mode=mode, ablate_world_to_m=ablate_world_to_m, rng=rng)
    # Propagation into body channels (ordinary physical mixing)
    return {
        "s0": 0.25 * float(direct["s0"]) + 0.75 * float(m["m0"]),
        "s1": 0.25 * float(direct["s1"]) + 0.75 * float(m["m1"]),
    }


def future_consequence(w: dict[str, float], *, strength: str = "large") -> dict[str, float]:
    """Later ordinary physical/body consequence depending on latent.

    strength: large | weak | none
    """
    latent = float(w.get("w_latent", 0.5))
    if strength == "none":
        return {"e": 0.50, "f": 0.50}
    if strength == "weak":
        return {"e": 0.48 + 0.04 * latent, "f": 0.50}
    return {"e": 0.20 + 0.70 * latent, "f": 0.30 + 0.50 * (1.0 - latent)}


# ---------------------------------------------------------------------------
# Learned prediction store (agent-accessible fragments only)
# ---------------------------------------------------------------------------

def empty_store() -> dict[str, Any]:
    return {
        "pred": {},  # observation sig -> future stats
        "exposure": {
            "M_encounters": 0,
            "M_interactions": 0,
            "W_A": 0,
            "W_B": 0,
            "mediated_A": 0,
            "mediated_B": 0,
            "full_mediated_sequence": 0,  # W->M->O->F end-to-end
        },
        "ablate_learned": False,
        "metrics_affect_cognition": False,
    }


def learn_prediction(store: dict[str, Any], observation: dict[str, float], future: dict[str, float]) -> None:
    if store.get("ablate_learned"):
        return
    key = _sig(_q(observation))
    pred = store.setdefault("pred", {})
    row = pred.get(key)
    if row is None:
        if len(pred) >= MAX_PRED:
            victim = min(pred.items(), key=lambda kv: int(kv[1].get("support") or 0))[0]
            del pred[victim]
        row = {"sum": {k: 0.0 for k in future}, "n": 0, "support": 0, "key": key}
        pred[key] = row
    for k, v in future.items():
        row["sum"][k] = float(row["sum"].get(k, 0.0)) + float(v)
    row["n"] = int(row["n"]) + 1
    row["support"] = int(row["support"]) + 1


def predict(store: dict[str, Any], observation: dict[str, float]) -> dict[str, Any]:
    if store.get("ablate_learned"):
        return {"status": "ABLATED", "predicted": None}
    key = _sig(_q(observation))
    row = (store.get("pred") or {}).get(key)
    if not row or int(row.get("support") or 0) < MIN_SUPPORT:
        return {"status": "NO_MATCH", "key": key, "predicted": None}
    n = max(1, int(row["n"]))
    return {
        "status": "MATCH",
        "key": key,
        "support": row["support"],
        "predicted": {k: float(v) / n for k, v in row["sum"].items()},
    }


def observability_audit(
    *,
    n: int = 40,
    seed: int = 17,
    mode: str = "useful",
    ablate_world_to_m: bool = False,
    ablate_m_to_body: bool = False,
    direct_noise: float = 0.01,
) -> dict[str, Any]:
    """Observer-side diagnostic. Must never enter cognition."""
    import random
    rng = random.Random(seed)
    direct_a, direct_b = [], []
    med_a, med_b = [], []
    for _ in range(n):
        wa, wb = world_state("A"), world_state("B")
        direct_a.append(direct_observation(wa, noise=direct_noise, rng=rng))
        direct_b.append(direct_observation(wb, noise=direct_noise, rng=rng))
        med_a.append(mediated_observation(wa, mode=mode, ablate_world_to_m=ablate_world_to_m,
                                          ablate_m_to_body=ablate_m_to_body, rng=rng))
        med_b.append(mediated_observation(wb, mode=mode, ablate_world_to_m=ablate_world_to_m,
                                          ablate_m_to_body=ablate_m_to_body, rng=rng))
    d_direct = mean_l1_pairs(direct_a, direct_b)
    d_med = mean_l1_pairs(med_a, med_b)
    # simple diagnostic accuracy: nearest-mean classifier on held-out samples
    def diag_acc(sa, sb):
        ma = {k: sum(float(x.get(k, 0)) for x in sa[: n // 2]) / max(1, n // 2) for k in sa[0]}
        mb = {k: sum(float(x.get(k, 0)) for x in sb[: n // 2]) / max(1, n // 2) for k in sb[0]}
        correct = 0
        total = 0
        for x in sa[n // 2:]:
            total += 1
            correct += int(l1(x, ma) <= l1(x, mb))
        for x in sb[n // 2:]:
            total += 1
            correct += int(l1(x, mb) <= l1(x, ma))
        return correct / max(1, total)

    acc_d = diag_acc(direct_a, direct_b)
    acc_m = diag_acc(med_a, med_b)
    if d_direct <= DIRECT_DISTINGUISH_MAX and d_med >= MEDIATED_DISTINGUISH_MIN:
        klass = "STRICT_ACQUIRED_OBSERVABILITY"
    elif d_med > d_direct * AMP_RATIO_MIN and d_med >= MEDIATED_DISTINGUISH_MIN:
        klass = "AMPLIFIED_OBSERVABILITY"
    else:
        klass = "NO_ACQUIRED_OBSERVABILITY"
    return {
        "direct_distinguishability": d_direct,
        "mediated_distinguishability": d_med,
        "direct_diagnostic_accuracy": acc_d,
        "mediated_diagnostic_accuracy": acc_m,
        "transduction_effect_size": d_med - d_direct,
        "classification": klass,
        "thresholds": {
            "DIRECT_DISTINGUISH_MAX": DIRECT_DISTINGUISH_MAX,
            "MEDIATED_DISTINGUISH_MIN": MEDIATED_DISTINGUISH_MIN,
            "AMP_RATIO_MIN": AMP_RATIO_MIN,
        },
        "mode": mode,
        "ablate_world_to_m": ablate_world_to_m,
        "ablate_m_to_body": ablate_m_to_body,
        "RESEARCHER_ONLY": True,
    }


def snapshot(store: dict[str, Any]) -> dict[str, Any]:
    return {
        "pred_count": len(store.get("pred") or {}),
        "exposure": deepcopy(store.get("exposure") or {}),
        "ablate_learned": bool(store.get("ablate_learned")),
        "leak_tokens": audit_forbidden({"pred_keys": list((store.get("pred") or {}).keys())[:20],
                                        "exposure": store.get("exposure")}),
        "metrics_affect_cognition": bool(store.get("metrics_affect_cognition")),
    }
