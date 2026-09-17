"""Update 4.13 — Acquired expectation × prediction violation (measurement only).

Researcher-facing primitives. Does NOT introduce surprise, reward, curiosity,
attention, novelty, or policy inputs. Does NOT alter temporal contingency updates.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.psyche.temporal_contingency import (
    COARSE_STATE_SIGNALS,
    MIN_SUPPORT_KNOWN,
    coarse_body_state_key,
    predicted_organism_state,
)

# Body components used for prospective violation reports (cognition-visible).
VIOLATION_COMPONENTS = tuple(COARSE_STATE_SIGNALS)

# Measurement-stability floor for near-zero comparisons (NOT cognition, NOT σ).
ABS_ERROR_CONFIRM_EPS = 0.003

# Exact semantics strings for Observer / reports (do not invent calibrated σ).
SUPPORT_SEMANTICS = (
    "support = number of settled lag observations folded into the EMA mean_body_delta "
    f"(incremented by 1 per update). MIN_SUPPORT_KNOWN={MIN_SUPPORT_KNOWN}."
)
CONFIDENCE_SEMANTICS = (
    "confidence = consistency * min(1, log1p(support)/log1p(MIN_SUPPORT_KNOWN+5)) "
    "* (1 - 0.5*contradiction), then forced to 0 when support < MIN_SUPPORT_KNOWN "
    "or when WAIT-baseline gating zeros action-specificity. NOT a calibrated probability."
)
CONTRADICTION_SEMANTICS = (
    "contradiction = EMA of (1 - agree), where agree is a cosine-like agreement of each "
    "new body_delta with the running mean_body_delta, mapped to [0,1]. "
    "This is directional agreement EMA, NOT component-wise variance σ. "
    "Therefore standardized_error = |e|/σ is NOT used."
)
CONSISTENCY_SEMANTICS = (
    "consistency = EMA of cosine-like agreement of new deltas with running mean."
)


def _num(d: Any) -> dict[str, float]:
    if not isinstance(d, dict):
        return {}
    return {
        str(k): float(v)
        for k, v in d.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def component_vector(state: dict[str, float] | None) -> dict[str, float]:
    s = _num(state)
    return {k: float(s.get(k, 0.0)) for k in VIOLATION_COMPONENTS}


def signed_errors(predicted: dict[str, float] | None, realized: dict[str, float] | None) -> dict[str, float]:
    p, r = component_vector(predicted), component_vector(realized)
    return {k: r[k] - p[k] for k in VIOLATION_COMPONENTS}


def absolute_errors(signed: dict[str, float]) -> dict[str, float]:
    return {k: abs(float(v)) for k, v in signed.items()}


def epistemic_from_record(rec: dict[str, Any] | None) -> dict[str, Any]:
    """Extract epistemic fields with explicit semantics; no invented σ."""
    if not isinstance(rec, dict):
        return {
            "has_record": False,
            "support": 0.0,
            "confidence": 0.0,
            "consistency": None,
            "contradiction": None,
            "status": "UNKNOWN",
            "mean_body_delta": None,
            "observations": 0,
            "dispersion_proxy": None,
            "dispersion_proxy_name": "contradiction",
            "standardized_error_used": False,
            "semantics": {
                "support": SUPPORT_SEMANTICS,
                "confidence": CONFIDENCE_SEMANTICS,
                "contradiction": CONTRADICTION_SEMANTICS,
                "consistency": CONSISTENCY_SEMANTICS,
            },
        }
    status = str(rec.get("status") or "UNKNOWN")
    support = float(rec.get("support") or 0.0)
    contradiction = float(rec.get("contradiction") or 0.0)
    return {
        "has_record": True,
        "support": support,
        "confidence": float(rec.get("confidence") or 0.0),
        "consistency": float(rec.get("consistency") or 0.0),
        "contradiction": contradiction,
        "status": status,
        "mean_body_delta": dict(rec.get("mean_body_delta") or {}),
        "observations": int(rec.get("observations") or 0),
        "dispersion_proxy": contradiction,
        "dispersion_proxy_name": "contradiction",
        "standardized_error_used": False,
        "semantics": {
            "support": SUPPORT_SEMANTICS,
            "confidence": CONFIDENCE_SEMANTICS,
            "contradiction": CONTRADICTION_SEMANTICS,
            "consistency": CONSISTENCY_SEMANTICS,
        },
    }


def classify_violation_status(
    *,
    epistemic: dict[str, Any],
    abs_err: dict[str, float],
    confirm_eps: float = ABS_ERROR_CONFIRM_EPS,
) -> str:
    """Descriptive status only. UNKNOWN → NO_PREDICTIVE_BASELINE (hard rule)."""
    status = str(epistemic.get("status") or "UNKNOWN")
    support = float(epistemic.get("support") or 0.0)
    has = bool(epistemic.get("has_record"))
    if (not has) or status == "UNKNOWN" or support < float(MIN_SUPPORT_KNOWN):
        return "NO_PREDICTIVE_BASELINE"
    mag = float(sum(abs_err.values()))
    if mag <= float(confirm_eps) * len(VIOLATION_COMPONENTS):
        return "PREDICTION_CONFIRMED"
    # also confirm if every component is within eps
    if all(float(abs_err.get(k, 0.0)) <= float(confirm_eps) for k in VIOLATION_COMPONENTS):
        return "PREDICTION_CONFIRMED"
    return "PREDICTION_MISMATCH"


def measure_prediction_violation(
    *,
    predicted_state: dict[str, float] | None,
    realized_state: dict[str, float] | None,
    record: dict[str, Any] | None,
    horizon: int,
    provenance: str = "DIRECT",
    state_key: str | None = None,
    state_match: str | None = None,
    action: str | None = None,
    violation_source: str = "UNKNOWN",
    confirm_eps: float = ABS_ERROR_CONFIRM_EPS,
) -> dict[str, Any]:
    """Primitive violation measurement for one horizon/transition.

    No error×confidence product. No H1+H2+H3 aggregation. No surprise variable.
    """
    epi = epistemic_from_record(record)
    if predicted_state is None and epi.get("mean_body_delta"):
        # allow caller to pass current+delta externally; here only if both states given
        pass
    signed = signed_errors(predicted_state, realized_state) if predicted_state is not None and realized_state is not None else {}
    abs_err = absolute_errors(signed) if signed else {}
    vstatus = classify_violation_status(epistemic=epi, abs_err=abs_err or {k: 0.0 for k in VIOLATION_COMPONENTS}, confirm_eps=confirm_eps)
    if predicted_state is None or realized_state is None:
        if vstatus != "NO_PREDICTIVE_BASELINE":
            # missing predicted state with weak/known record still cannot confirm
            if predicted_state is None:
                vstatus = "NO_PREDICTIVE_BASELINE"
    return {
        "action": action,
        "horizon": int(horizon),
        "provenance": str(provenance),
        "state_key": state_key,
        "state_match": state_match,
        "expected": {
            "predicted_state": component_vector(predicted_state) if predicted_state is not None else None,
            "epistemic": epi,
        },
        "realized": {
            "realized_state": component_vector(realized_state) if realized_state is not None else None,
        },
        "violation": {
            "signed_error": signed,
            "absolute_error": abs_err,
            "absolute_error_L1": float(sum(abs_err.values())) if abs_err else None,
            "standardized_error": None,
            "standardized_error_reason": (
                "omitted: architecture stores contradiction (directional EMA), "
                "not component-wise empirical σ"
            ),
            "status": vstatus,
            "violation_source": violation_source,
            "confirm_eps": float(confirm_eps),
            "confirm_eps_role": "measurement-stability parameter only; not cognition",
        },
        "notes": [
            "prediction error ≠ prediction violation relative to acquired expectation",
            "same absolute error may differ in epistemic significance via support/contradiction",
            "no surprise / reward / policy coupling",
        ],
    }


def predict_from_transition_edge(edge: dict[str, Any], current_signals: dict[str, float]) -> dict[str, Any]:
    """Build predicted state from apply_transition / compose edge."""
    if not isinstance(edge, dict) or edge.get("status") != "OK":
        return {
            "predicted_state": None,
            "record_like": {
                "support": float((edge or {}).get("support") or 0.0),
                "confidence": float((edge or {}).get("confidence") or 0.0),
                "status": "UNKNOWN",
                "consistency": (edge or {}).get("consistency"),
                "contradiction": (edge or {}).get("contradiction"),
                "mean_body_delta": (edge or {}).get("mean_body_delta"),
                "observations": (edge or {}).get("observations") or 0,
            },
            "provenance": (edge or {}).get("provenance") or "UNKNOWN",
            "state_match": (edge or {}).get("state_match"),
            "state_key": (edge or {}).get("input_state_key") or coarse_body_state_key(current_signals, from_interoception=False),
        }
    pred = edge.get("predicted_state")
    if pred is None:
        pred = predicted_organism_state(current_signals, edge.get("mean_body_delta"))
    rec_like = {
        "support": float(edge.get("support") or 0.0),
        "confidence": float(edge.get("confidence") or 0.0),
        "status": str(edge.get("epistemic_status") or edge.get("status") or "KNOWN"),
        "consistency": edge.get("consistency"),
        "contradiction": edge.get("contradiction"),
        "mean_body_delta": edge.get("mean_body_delta"),
        "observations": edge.get("observations") or int(float(edge.get("support") or 0)),
    }
    # Map compose OK edges: if support < MIN treat as UNKNOWN for violation baseline
    if rec_like["support"] < float(MIN_SUPPORT_KNOWN):
        rec_like["status"] = "UNKNOWN"
    return {
        "predicted_state": pred,
        "record_like": rec_like,
        "provenance": edge.get("provenance") or "DIRECT",
        "state_match": edge.get("state_match"),
        "state_key": edge.get("input_state_key") or coarse_body_state_key(current_signals, from_interoception=False),
    }


def localize_composed_violation(edge_a_meas: dict[str, Any], edge_b_meas: dict[str, Any]) -> dict[str, Any]:
    """Attribute composed mismatch by transition; never a single FAILED label."""
    sa = ((edge_a_meas.get("violation") or {}).get("status"))
    sb = ((edge_b_meas.get("violation") or {}).get("status"))
    ea = ((edge_a_meas.get("violation") or {}).get("absolute_error_L1")) or 0.0
    eb = ((edge_b_meas.get("violation") or {}).get("absolute_error_L1")) or 0.0
    if sa == "NO_PREDICTIVE_BASELINE" and sb == "NO_PREDICTIVE_BASELINE":
        attr = "NO_PREDICTIVE_BASELINE_BOTH_EDGES"
    elif sa == "PREDICTION_CONFIRMED" and sb in ("PREDICTION_MISMATCH", "NO_PREDICTIVE_BASELINE"):
        attr = "EDGE_2_DOMINANT"
    elif sb == "PREDICTION_CONFIRMED" and sa == "PREDICTION_MISMATCH":
        attr = "EDGE_1_DOMINANT"
    elif sa == "PREDICTION_MISMATCH" and sb == "PREDICTION_MISMATCH":
        attr = "BOTH_EDGES_MISMATCH" if abs(ea - eb) < 1e-9 else ("EDGE_1_LARGER_ABS" if ea > eb else "EDGE_2_LARGER_ABS")
    elif sa == "PREDICTION_CONFIRMED" and sb == "PREDICTION_CONFIRMED":
        attr = "BOTH_EDGES_CONFIRMED"
    else:
        attr = "MIXED_OR_UNKNOWN"
    return {
        "attribution": attr,
        "edge_1_status": sa,
        "edge_2_status": sb,
        "edge_1_abs_L1": ea,
        "edge_2_abs_L1": eb,
        "note": "composed trajectory is not labeled FAILED as a whole",
    }
