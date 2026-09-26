"""Bridge 4.26–4.28 into cognition tick (Observer/science instrumentation only for labels)."""
from __future__ import annotations

from typing import Any

from mechanistic_mind.research import contextual_predictive_organization as cpo
from mechanistic_mind.research import context_grounded_prospection as cgp
from mechanistic_mind.research import persistent_prospective_control as ppc


def _cpo(state: dict[str, Any]) -> dict[str, Any]:
    return state.setdefault("contextual_organization", cpo.empty_store())


def _cgp(state: dict[str, Any]) -> dict[str, Any]:
    return state.setdefault("context_grounded_prospection", cgp.empty_store())


def _ppc(state: dict[str, Any]) -> dict[str, Any]:
    return state.setdefault("persistent_prospective_control", ppc.empty_store())


def sync_flags(state: dict[str, Any], cfg: dict[str, Any]) -> None:
    s = _cpo(state)
    s["enabled"] = bool(cfg.get("contextual_predictive_organization"))
    s["ablate_higher_order"] = bool(cfg.get("contextual_predictive_organization_ablate"))
    s["ablate_predictive_use"] = bool(cfg.get("contextual_predictive_organization_ablate"))
    s["shuffle_members"] = bool(cfg.get("contextual_predictive_organization_shuffle"))
    g = _cgp(state)
    g["enabled"] = bool(cfg.get("context_grounded_prospection"))
    g["ablate_composition"] = bool(cfg.get("context_grounded_prospection_ablate"))
    g["shuffle_relations"] = bool(cfg.get("context_grounded_prospection_shuffle"))
    p = _ppc(state)
    p["enabled"] = bool(cfg.get("persistent_prospective_control"))
    p["ablate_persistence"] = bool(cfg.get("persistent_prospective_control_ablate"))
    p["ablate_motor_chunks"] = bool(cfg.get("persistent_prospective_control_ablate_chunks"))


def on_experience(
    state: dict[str, Any],
    *,
    tick: int,
    previous: dict[str, Any] | None,
    observation: dict[str, Any] | None,
    previous_action: str | None,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """After ordinary compression/prospection learning for this tick."""
    sync_flags(state, cfg)
    diag: dict[str, Any] = {}
    if not isinstance(observation, dict):
        return diag
    cpo_s = _cpo(state)
    cgp_s = _cgp(state)
    ppc_s = _ppc(state)

    # Advance persistent prospective control against unfolding observation.
    if cfg.get("persistent_prospective_control") and ppc_s.get("active"):
        pred = None
        active = ppc_s.get("active") or {}
        preds = active.get("predicted_states") or []
        cursor = int(active.get("cursor") or 0)
        if cursor < len(preds) and isinstance(preds[cursor], dict):
            pred = preds[cursor]
        # Use compression predict as fallback predicted next
        if pred is None and previous is not None and previous_action:
            from mechanistic_mind.research import predictive_compression as pc
            got = pc.predict(state.get("compression") or {}, previous, str(previous_action), domain="accessible")
            if got.get("status") == "MATCH":
                pred = got.get("predicted") or got.get("mean_predicted")
        adv = ppc.advance(
            ppc_s,
            tick=tick,
            realized_observation={
                str(k): float(v)
                for k, v in observation.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            },
            realized_action=str(previous_action) if previous_action else None,
            predicted_next=pred if isinstance(pred, dict) else None,
        )
        diag["ppc_advance"] = adv

    members = cpo.collect_members_from_runtime_state(state)
    # Also include soft keys from observation channels (relation-bearing, not x/y)
    if isinstance(observation, dict):
        for k, v in observation.items():
            ks = str(k)
            if ks in {"x", "y", "cell", "region", "location"}:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                # quantized channel token as weak member (deterministic)
                q = int(max(0.0, min(0.999, abs(float(v)))) * 5)
                members.append(f"ch:{ks}:{q}")
    members = sorted(set(members))[: cpo.MAX_MEMBERS]

    cont = {
        str(k): float(v)
        for k, v in observation.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool) and str(k) not in {"x", "y"}
    }
    formed = None
    if cfg.get("contextual_predictive_organization"):
        formed = cpo.observe_coactivation(
            cpo_s,
            tick=tick,
            members=members,
            continuation=cont,
            action=str(previous_action) if previous_action else None,
        )
        diag["cpo_formed"] = (formed or {}).get("context_id")
        react = cpo.reactivate(cpo_s, tick=tick, evidence_members=members, mode="PARTIAL")
        diag["cpo_reactivate"] = {
            "status": react.get("status"),
            "context_id": (react.get("best") or {}).get("context_id"),
            "ratio": (react.get("best") or {}).get("ratio"),
        }
        state["_cpo_last_reactivation"] = react
        # Learn context→context transition when previous active differs
        prev_cx = (state.get("_cpo_prev_active_id"))
        cur_cx = (formed or {}).get("context_id") or (react.get("best") or {}).get("context_id")
        if cfg.get("context_grounded_prospection") and prev_cx and cur_cx and prev_cx != cur_cx:
            cgp.learn_context_transition(
                cgp_s,
                tick=tick,
                from_id=str(prev_cx),
                to_id=str(cur_cx),
                action=str(previous_action or "WAIT"),
                to_pred=cont,
            )
            diag["cgp_learned"] = f"{prev_cx}->{cur_cx}"
        if cur_cx:
            state["_cpo_prev_active_id"] = cur_cx

    if previous_action:
        ppc.observe_motor_sequence(
            ppc_s,
            actions=[str(previous_action)],
        )
    return diag


def before_selection(
    state: dict[str, Any],
    *,
    tick: int,
    observation: dict[str, Any] | None,
    continuations: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Inject context-grounded compositions; report PPC preferred action."""
    sync_flags(state, cfg)
    diag: dict[str, Any] = {"ppc_preferred": None, "cgp_injected": 0}
    out = list(continuations)
    if not isinstance(observation, dict):
        return out, diag
    cpo_s = _cpo(state)
    cgp_s = _cgp(state)
    ppc_s = _ppc(state)

    if cfg.get("context_grounded_prospection") and cfg.get("contextual_predictive_organization"):
        members = cpo.collect_members_from_runtime_state(state)
        react = state.get("_cpo_last_reactivation") or cpo.reactivate(
            cpo_s, tick=tick, evidence_members=members, mode="PARTIAL"
        )
        start_id = (react.get("best") or {}).get("context_id")
        if start_id:
            comp = cgp.compose_context_trajectories(cgp_s, start_id=str(start_id))
            injected = cgp.inject_as_prospection_continuations(
                comp,
                present={
                    str(k): float(v)
                    for k, v in observation.items()
                    if isinstance(v, (int, float)) and not isinstance(v, bool)
                },
            )
            if injected:
                out = list(out) + injected
                diag["cgp_injected"] = len(injected)
                diag["cgp_max_depth"] = comp.get("max_depth")

    pref = ppc.preferred_action(ppc_s) if cfg.get("persistent_prospective_control") else None
    diag["ppc_preferred"] = pref
    return out, diag


def after_selection(
    state: dict[str, Any],
    *,
    tick: int,
    selected: str | None,
    continuations: list[dict[str, Any]],
    observation: dict[str, Any] | None,
    cfg: dict[str, Any],
    selection_source: str | None = None,
) -> dict[str, Any]:
    """Maybe adopt multi-step continuation as persistent prospective control."""
    sync_flags(state, cfg)
    diag: dict[str, Any] = {}
    if not cfg.get("persistent_prospective_control"):
        return diag
    ppc_s = _ppc(state)
    # If already active and preferred matched selection, do not re-select from scratch
    pref = ppc.preferred_action(ppc_s)
    if pref is not None and selected is not None and str(selected) == str(pref):
        diag["ppc_reuse"] = True
        return diag
    # Find deepest matching continuation for selected first action
    best = None
    for c in continuations:
        acts = list(c.get("actions") or [])
        if not acts:
            continue
        if str(acts[0]) != str(selected):
            continue
        if best is None or int(c.get("depth") or len(acts)) > int(best.get("depth") or 0):
            best = c
    if best and int(best.get("depth") or 0) >= 2:
        # Mark novel if from context-grounded source and not a complete-route habit
        if best.get("source") == "context_grounded_prospection":
            best = dict(best)
            best["complete_route_seen"] = False
            best["novel_composition"] = True
        active = ppc.select_continuation(
            ppc_s,
            tick=tick,
            continuation=best,
            origin_observation={
                str(k): float(v)
                for k, v in (observation or {}).items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            } if isinstance(observation, dict) else None,
        )
        diag["ppc_selected"] = (active or {}).get("id")
        diag["ppc_depth"] = (active or {}).get("depth")
        diag["selection_source"] = selection_source
    return diag


def public_view_sections(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "contextual_predictive_organization": {
            **cpo.snapshot(_cpo(state)),
            "observer_compact": cpo.observer_compact(_cpo(state)),
            "note": "CONTEXTUAL_PREDICTIVE_ORGANIZATION — not place / map / familiar",
        },
        "context_grounded_prospection": {
            **cgp.snapshot(_cgp(state)),
            "observer_compact": cgp.observer_compact(_cgp(state)),
            "note": "CONTEXT_GROUNDED_PROSPECTION — not route / destination",
        },
        "persistent_prospective_control": {
            **ppc.snapshot(_ppc(state)),
            "observer_compact": ppc.observer_compact(_ppc(state)),
            "note": "PERSISTENT_PROSPECTIVE_CONTROL — support-gated, not intention variable",
        },
    }
