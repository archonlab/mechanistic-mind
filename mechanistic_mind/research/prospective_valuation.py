"""Update 4.5 — prospective ordinary valuation from predicted physical deltas.

Predictability != desirability.
confidence/support gate reliability of using a prediction; they do NOT add value.

Uses the same target-error reduction logic as OrganismValuationModule._target_gain.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def _numeric(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        str(k): float(v)
        for k, v in value.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x



def canonicalize_predicted_body_delta(body_delta: dict[str, float] | None) -> dict[str, float]:
    """Normalize predicted physical consequence keys for prospective valuation.

    Update 4.10.4 — schema alignment only.

    Temporal contingency stores interoception *deltas* under bare `*_signal`
    keys (consequence_from_observations = after - before on interoception).
    Prospective valuation / target_gain expects `*_signal_delta` (or reserve
    `energy_delta` mapped via capacity).

    This boundary:
    - preserves sign and magnitude exactly for already signal-space deltas
    - does not invent channels
    - does not rescale, clip, or reward-shape
    - leaves reserve-shaped `*_delta` keys for existing capacity mapping
    """
    bd = _numeric(body_delta)
    out: dict[str, float] = {}
    for k, v in bd.items():
        if k.endswith("_signal_delta"):
            out[k] = float(v)
        elif k.endswith("_signal"):
            # Already a signal-space delta; rename to canonical *_signal_delta
            out[f"{k}_delta"] = float(v)
        else:
            # reserve deltas (energy_delta, ...) and other physical keys unchanged
            out[k] = float(v)
    return out


def map_reserve_deltas_to_signal_deltas(
    body_delta: dict[str, float],
    *,
    energy_capacity: float = 1.0,
    hydration_capacity: float = 1.0,
) -> dict[str, float]:
    """Map stored physical costs to interoceptive signal deltas.

    Fragments store energy_delta/hydration_delta/fatigue_delta on reserves.
    Valuation expects energy_signal_delta etc.
    """
    e_cap = max(1e-9, float(energy_capacity))
    h_cap = max(1e-9, float(hydration_capacity))
    out: dict[str, float] = {}
    bd = canonicalize_predicted_body_delta(body_delta)
    if "energy_delta" in bd:
        out["energy_signal_delta"] = float(bd["energy_delta"]) / e_cap
    if "hydration_delta" in bd:
        out["hydration_signal_delta"] = float(bd["hydration_delta"]) / h_cap
    if "fatigue_delta" in bd:
        out["fatigue_signal_delta"] = float(bd["fatigue_delta"])
    # Pass through already-signal-shaped keys
    for k, v in bd.items():
        if k.endswith("_signal_delta") or k.endswith("_delta") and "signal" in k:
            out[k] = float(v)
    # effort as discomfort-ish load proxy only if present
    if "motor_effort" in bd and "discomfort_signal_delta" not in out:
        # do not invent discomfort from effort — keep physical only
        pass
    return out


def target_gain_from_predicted_deltas(
    predicted_signal_deltas: dict[str, float],
    current_signals: dict[str, float],
    goals: dict[str, Any],
) -> float:
    """Same math as organism_modules._target_gain (duplicated to avoid circular imports)."""
    targets = _numeric(goals.get("signal_targets"))
    weights = _numeric(goals.get("signal_weights"))
    predicted = _numeric(predicted_signal_deltas)
    total = 0.0
    for key, target in targets.items():
        current = float(current_signals.get(key, target))
        delta_key = f"{key}_delta"
        predicted_delta = float(predicted.get(delta_key, predicted.get(key, 0.0)))
        after = _clamp01(current + predicted_delta)
        before_error = (current - target) ** 2
        after_error = (after - target) ** 2
        total += (before_error - after_error) * float(weights.get(key, 1.0))
    return float(total)


def classify_epistemic_value(
    *,
    has_prediction: bool,
    body_delta_samples: float,
    contradiction: float,
    prospective_value: float | None,
    abs_delta_sum: float,
) -> str:
    if not has_prediction or body_delta_samples <= 0:
        return "UNKNOWN"
    if contradiction > 0.5:
        return "CONFLICTED"
    if prospective_value is None:
        return "UNKNOWN"
    if abs(float(prospective_value)) <= 1e-12 and abs_delta_sum <= 1e-12:
        return "NEUTRAL"
    if float(prospective_value) > 1e-12:
        return "POSITIVE"
    if float(prospective_value) < -1e-12:
        return "NEGATIVE"
    return "NEUTRAL"


def prospective_ordinary_value(
    *,
    mean_body_delta: dict[str, float] | None,
    body_delta_samples: float,
    contradiction: float,
    current_signals: dict[str, float],
    goals: dict[str, Any],
    energy_capacity: float = 1.0,
    hydration_capacity: float = 1.0,
    support: float = 0.0,
    prediction_ablated: bool = False,
    min_support_to_use: float = 1.0,
) -> dict[str, Any]:
    """Compute prospective ordinary value from predicted physical deltas.

    Does NOT add confidence/support into the value number.
    If prediction_ablated or insufficient samples: value unavailable (UNKNOWN).
    """
    result: dict[str, Any] = {
        "prospective_available": False,
        "ordinary_value": None,
        "regulation": None,
        "predicted_signal_deltas": {},
        "predicted_body_delta": {},
        "epistemic_status": "UNKNOWN",
        "confidence_used_as_value": False,
        "support": float(support),
        "contradiction": float(contradiction),
        "body_delta_samples": float(body_delta_samples),
        "reason": None,
        "observer_note": "OBSERVER ONLY fields may mirror this; cognition uses ordinary_value only when available",
    }
    if prediction_ablated:
        result["reason"] = "PREDICTION_ABLATED"
        result["epistemic_status"] = "UNKNOWN"
        return result
    if not mean_body_delta or body_delta_samples < min_support_to_use:
        result["reason"] = "NO_BODY_DELTA_EVIDENCE"
        result["epistemic_status"] = "UNKNOWN"
        return result

    body = _numeric(mean_body_delta)
    signal_deltas = map_reserve_deltas_to_signal_deltas(
        body, energy_capacity=energy_capacity, hydration_capacity=hydration_capacity
    )
    regulation = target_gain_from_predicted_deltas(signal_deltas, current_signals, goals)
    # Habit/navigation not invented for MP — only physical regulation from predicted body deltas.
    ordinary = float(regulation)
    abs_delta_sum = sum(abs(v) for v in body.values()) + sum(abs(v) for v in signal_deltas.values())
    status = classify_epistemic_value(
        has_prediction=True,
        body_delta_samples=body_delta_samples,
        contradiction=contradiction,
        prospective_value=ordinary,
        abs_delta_sum=abs_delta_sum,
    )
    result.update(
        {
            "prospective_available": True,
            "ordinary_value": ordinary,
            "regulation": regulation,
            "predicted_signal_deltas": signal_deltas,
            "predicted_body_delta": body,
            "epistemic_status": status,
            "reason": "PROSPECTIVE_FROM_PHYSICAL_DELTA",
            "components": {"regulation": regulation, "progress": 0.0, "habit": 0.0, "navigation": 0.0},
        }
    )
    return result
