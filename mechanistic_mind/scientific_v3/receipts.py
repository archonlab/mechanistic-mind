\
"""CORE receipt builders — record only quantities that already exist."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from . import provenance as P
from .ids import consequence_id, decision_id, motor_id, observation_id



def _short(s: str, n: int) -> str:
    s = str(s)
    return s if len(s) <= n else (s[: n - 1] + "…")

def _json_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _f(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except (TypeError, ValueError):
        return default


def wrap_delta(a: float, b: float, period: float) -> float:
    """Shortest signed wrap-aware delta on a torus of length period."""
    if period <= 0:
        return b - a
    d = (b - a) % period
    if d > period * 0.5:
        d -= period
    return d


def compact_accessible_observation(obs: dict[str, Any] | None) -> dict[str, float]:
    """Keep only finite scalar channels from agent-accessible observation."""
    out: dict[str, float] = {}
    for k, v in (obs or {}).items():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if math.isnan(fv) or math.isinf(fv):
            continue
        # Round for stable compact JSON (does not change runtime science)
        out[str(k)] = round(fv, 8)
    return out


def build_observation_receipt(
    *,
    run_id: str,
    tick: int,
    cognitive_agent_id: str,
    physical_body_id: str,
    accessible: dict[str, float],
) -> dict[str, Any]:
    oid = observation_id(run_id, tick, cognitive_agent_id)
    return {
        "schema": "mm.scientific_v3.observation.core.v1",
        "observation_id": oid,
        "tick": int(tick),
        "run_id": run_id,
        "cognitive_agent_id": cognitive_agent_id,
        "physical_body_id": physical_body_id,
        "accessible": accessible,
        "signature": _json_hash(accessible),
        "provenance": P.AGENT_ACCESSIBLE,
    }


def _selection_path(last_selection: dict[str, Any], cognition_result_source: str | None) -> str:
    """Use actual runtime terminology — never invent paths."""
    src = str(
        last_selection.get("source")
        or cognition_result_source
        or ""
    ).strip()
    mode = str(
        last_selection.get("prospective_selection_mode")
        or (last_selection.get("competition") or {}).get("mode")
        or ""
    ).strip()
    if src:
        return src
    if mode:
        return mode
    return "NOT_AVAILABLE"



def _smc_decision_block(sel: dict[str, Any]) -> dict[str, Any]:
    """QUERIED / PREDICTED summary for Analyzer — references selection tick only."""
    diag = sel.get("sensorimotor_consequence") if isinstance(sel.get("sensorimotor_consequence"), dict) else {}
    preds = sel.get("sensorimotor_candidate_predictions")
    if not isinstance(preds, list):
        preds = []
    compact_preds = []
    for pred in preds[:12]:
        if not isinstance(pred, dict):
            continue
        delta = pred.get("predicted_delta")
        delta_compact = None
        if isinstance(delta, dict) and delta:
            delta_compact = {
                str(k): float(v)
                for k, v in list(delta.items())[:48]
                if isinstance(v, (int, float))
            }
        compact_preds.append({
            "kind": "SENSORIMOTOR_CONSEQUENCE_PREDICTED",
            "motor": pred.get("motor") or pred.get("motor_signature"),
            "candidate_locomotion": pred.get("candidate_locomotion"),
            "status": pred.get("status"),
            "support": pred.get("support"),
            "reliability": pred.get("reliability"),
            "record_id": pred.get("record_id"),
            "predicted_delta": delta_compact,
            "reason": pred.get("reason"),
        })
    last_upd = sel.get("sensorimotor_last_update") if isinstance(sel.get("sensorimotor_last_update"), dict) else None
    last_upd_compact = None
    if isinstance(last_upd, dict):
        receipt = last_upd.get("receipt") if isinstance(last_upd.get("receipt"), dict) else last_upd
        mean_delta = receipt.get("mean_delta") if isinstance(receipt, dict) else None
        mean_compact = None
        if isinstance(mean_delta, dict):
            mean_compact = {
                str(k): float(v)
                for k, v in list(mean_delta.items())[:48]
                if isinstance(v, (int, float))
            }
        last_upd_compact = {
            "kind": last_upd.get("kind") or (receipt or {}).get("kind"),
            "tick": last_upd.get("tick") or (receipt or {}).get("tick"),
            "record_id": (receipt or {}).get("record_id"),
            "motor_signature": (receipt or {}).get("motor_signature"),
            "support": (receipt or {}).get("support"),
            "mean_delta": mean_compact,
        }
    enabled = diag.get("enabled")
    return {
        "kind": "SENSORIMOTOR_CONSEQUENCE_QUERIED",
        "enabled": bool(enabled) if enabled is not None else bool(compact_preds or last_upd_compact),
        "occupancy": diag.get("occupancy"),
        "capacity": diag.get("capacity"),
        "updates": diag.get("updates"),
        "queries": diag.get("queries"),
        "matched_queries": diag.get("matched_queries"),
        "unknown_queries": diag.get("unknown_queries"),
        "withheld_from_psc": bool(sel.get("sensorimotor_withheld_from_psc")),
        "predictions": compact_preds,
        "last_update": last_upd_compact,
    }


def _hss_decision_block(sel: dict[str, Any]) -> dict[str, Any]:
    """O′→history→PSC bridge evidence already computed in cognition last_selection."""
    meta = sel.get("o_prime_history_bridge") if isinstance(sel.get("o_prime_history_bridge"), dict) else {}
    cands = sel.get("o_prime_history_candidates")
    if not isinstance(cands, list):
        cands = []
    compact_cands = []
    for c in cands[:12]:
        if not isinstance(c, dict):
            continue
        fields = c.get("predicted_fields")
        if isinstance(fields, list):
            fields = [str(x) for x in fields[:32]]
        else:
            fields = None
        compact_cands.append({
            "candidate_locomotion": c.get("candidate_locomotion"),
            "history_status": c.get("history_status"),
            "history_support": c.get("history_support"),
            "history_match_count": c.get("history_match_count"),
            "support_spread": c.get("support_spread"),
            "predicted_fields": fields,
            "available_to_psc": c.get("available_to_psc"),
            "history_shuffled": bool(c.get("history_shuffled")),
        })
    if not meta and not compact_cands:
        return {
            "kind": "HISTORICAL_SENSORIMOTOR_SELECTION",
            "enabled": False,
            "candidates": [],
        }
    cf = meta.get("local_counterfactual") if isinstance(meta.get("local_counterfactual"), dict) else None
    cf_compact = None
    if isinstance(cf, dict):
        cf_compact = {
            "selected": cf.get("selected"),
            "source": cf.get("source"),
            "outcome_class": cf.get("outcome_class"),
        }
    return {
        "kind": "HISTORICAL_SENSORIMOTOR_SELECTION",
        "enabled": bool(meta.get("enabled")),
        "withheld_from_psc": bool(meta.get("withheld_from_psc")),
        "shuffle": bool(meta.get("shuffle")),
        "n_candidates_evaluated": meta.get("n_candidates_evaluated"),
        "n_history_match": meta.get("n_history_match"),
        "history_support_spread": meta.get("history_support_spread"),
        "history_support_differentiated": meta.get("history_support_differentiated"),
        "selection_differs_from_withheld_cf": meta.get("selection_differs_from_withheld_cf"),
        "local_counterfactual": cf_compact,
        "candidates": compact_cands,
    }


def build_decision_receipt(
    *,
    run_id: str,
    tick: int,
    cognitive_agent_id: str,
    physical_body_id: str,
    observation_id_value: str,
    motor_id_value: str,
    last_selection: dict[str, Any] | None,
    selected_action: str | None,
    selection_source: str | None,
    selection_rule: str | None,
) -> dict[str, Any]:
    sel = dict(last_selection or {})
    competition = sel.get("competition") if isinstance(sel.get("competition"), dict) else {}
    path = _selection_path(sel, selection_source)
    candidates = sel.get("candidates")
    if not isinstance(candidates, list):
        candidates = sel.get("select_actions") if isinstance(sel.get("select_actions"), list) else []
    candidate_count = len(candidates) if isinstance(candidates, list) else 0
    selected = str(selected_action or sel.get("action") or "NOT_AVAILABLE")
    # Prefer existing competition winner / selected candidate identity if present.
    selected_candidate_id = None
    for key in ("selected_candidate_id", "winner_id", "selected_scenario_id"):
        if sel.get(key) is not None:
            selected_candidate_id = str(sel.get(key))
            break
        if competition.get(key) is not None:
            selected_candidate_id = str(competition.get(key))
            break
    if selected_candidate_id is None and selected not in ("", "NOT_AVAILABLE"):
        selected_candidate_id = f"action:{selected}"

    fallback_reason = None
    peer = sel.get("peer_evaluation")
    if isinstance(peer, str) and peer:
        # Peer evaluation string often encodes defer/fallback rationale.
        if "fallback" in peer.lower() or "defer" in peer.lower() or "no supported" in peer.lower():
            fallback_reason = peer

    mode = str(
        sel.get("prospective_selection_mode")
        or competition.get("mode")
        or "NOT_AVAILABLE"
    )

    return {
        "schema": "mm.scientific_v3.decision.core.v1",
        "decision_id": decision_id(run_id, tick, cognitive_agent_id),
        "observation_id": observation_id_value,
        "motor_id": motor_id_value,
        "tick": int(tick),
        "run_id": run_id,
        "cognitive_agent_id": cognitive_agent_id,
        "physical_body_id": physical_body_id,
        "selection_path": path,
        "selection_source": str(selection_source or sel.get("source") or "NOT_AVAILABLE"),
        "selection_mode": mode,
        "selection_rule": _short(str(selection_rule or sel.get("selection_rule") or "NOT_AVAILABLE"), 96),
        "selected_action_legacy": selected,
        "selected_candidate_id": selected_candidate_id,
        "candidate_count": int(candidate_count),
        "fallback_reason": fallback_reason,
        "peer_evaluation": peer if peer is not None else "NOT_AVAILABLE",
        "provenance": P.DECISION_INTERNAL,
        # Compact action-conditioned sensory prediction telemetry (no ΔS utility).
        "sensorimotor_consequence": _smc_decision_block(sel),
        # O′→history→PSC bridge evidence (candidate-level; no GT enrichment).
        "historical_sensorimotor_selection": _hss_decision_block(sel),
        "psc_motor_resolution": str(
            sel.get("psc_motor_resolution")
            or (competition.get("psc_motor_resolution") if isinstance(competition, dict) else None)
            or "LOCO_FACTORIZED"
        ),
        "observed_composite_selection": (
            sel.get("observed_composite_selection")
            if isinstance(sel.get("observed_composite_selection"), dict)
            else None
        ),
    }


def build_motor_receipt(
    *,
    run_id: str,
    tick: int,
    cognitive_agent_id: str,
    physical_body_id: str,
    decision_id_value: str,
    motor_output: dict[str, Any] | None,
) -> dict[str, Any]:
    mo = dict(motor_output or {})
    schema = str(mo.get("schema") or "COMPOSITE_MOTOR_V1")
    osc = mo.get("oscillator") if isinstance(mo.get("oscillator"), dict) else {}
    osc_compact = {}
    if osc:
        for k in ("frequency_delta", "amplitude_delta", "emit_trigger", "control", "emit"):
            if k in osc and osc.get(k) not in (None, 0, 0.0, False):
                osc_compact[k] = osc.get(k)
    components = {
        "locomotion": str(mo.get("locomotion") or "WAIT"),
        "neck": str(mo.get("neck") or "NONE"),
        "oscillator": osc_compact,
        "push": bool(mo.get("push")),
    }
    return {
        "schema": "mm.scientific_v3.motor.core.v1",
        "motor_id": motor_id(run_id, tick, cognitive_agent_id),
        "decision_id": decision_id_value,
        "tick": int(tick),
        "run_id": run_id,
        "cognitive_agent_id": cognitive_agent_id,
        "physical_body_id": physical_body_id,
        "motor_schema": schema,
        "components": components,
        "selection_source": str(mo.get("selection_source") or "NOT_AVAILABLE"),
        "legacy_token": str(mo.get("legacy_token") or ""),
        "legacy_token_provenance": P.LEGACY_COMPATIBILITY,
        "provenance": P.MOTOR_OUTPUT,
    }


def _resource_scalars(snap: dict[str, Any] | None) -> dict[str, float]:
    snap = snap or {}
    # Prefer mechanical work reservoir + B_sum; R_A/R_B site sums when present.
    ra = snap.get("R_A_site")
    rb = snap.get("R_B_site")
    ra_s = float(sum(ra)) if isinstance(ra, (list, tuple)) else _f(snap.get("R_A"))
    rb_s = float(sum(rb)) if isinstance(rb, (list, tuple)) else _f(snap.get("R_B"))
    return {
        "A": ra_s,
        "B": _f(snap.get("B_sum"), default=_f(snap.get("B"))),
        "work": _f(snap.get("mechanical_work_reservoir")),
    }


def build_consequence_receipt(
    *,
    run_id: str,
    tick_from: int,
    body_id: str,
    motor_id_value: str | None,
    cognitive_agent_id: str | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    world_width: float | None = None,
    world_height: float | None = None,
    event_refs: list[dict[str, Any]] | None = None,
    attribution: str = "UNKNOWN",
) -> dict[str, Any]:
    before = before or {}
    after = after or {}
    w = float(world_width) if world_width else 0.0
    h = float(world_height) if world_height else 0.0
    dx = wrap_delta(_f(before.get("x")), _f(after.get("x")), w) if w > 0 else (_f(after.get("x")) - _f(before.get("x")))
    dy = wrap_delta(_f(before.get("y")), _f(after.get("y")), h) if h > 0 else (_f(after.get("y")) - _f(before.get("y")))
    rb = _resource_scalars(before)
    ra = _resource_scalars(after)
    return {
        "schema": "mm.scientific_v3.consequence.core.v1",
        "consequence_id": consequence_id(run_id, tick_from, body_id),
        "tick_from": int(tick_from),
        "tick_to": int(tick_from) + 1,
        "run_id": run_id,
        "physical_body_id": body_id,
        "cognitive_agent_id": cognitive_agent_id,
        "motor_id": motor_id_value,
        "pose_delta": {"dx": dx, "dy": dy, "wrap_aware": bool(w > 0 and h > 0)},
        "orientation_delta": {
            "d_theta": _f(after.get("theta")) - _f(before.get("theta")),
            "d_omega": _f(after.get("omega")) - _f(before.get("omega")),
            "d_head_relative_angle": _f(after.get("head_relative_angle")) - _f(before.get("head_relative_angle")),
        },
        "resource_delta": {
            "A": ra["A"] - rb["A"],
            "B": ra["B"] - rb["B"],
            "work": ra["work"] - rb["work"],
        },
        "event_refs": list(event_refs or []),
        "attribution": attribution,  # UNKNOWN unless caller derives
        "provenance": P.PHYSICAL_GROUND_TRUTH,
    }
