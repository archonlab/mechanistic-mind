"""Update 4.9.1 — Environmental regulation probe helpers (telemetry only).

Telemetry helpers only. No new psyche capability. No env-value channel.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def local_avail(world: dict[str, Any], pos: list | tuple, material_id: str = "material_a") -> float:
    field = world.get("env_material_field") or {}
    if not isinstance(field, dict):
        return 0.0
    key = f"{int(pos[0])},{int(pos[1])}"
    if material_id in field and isinstance(field[material_id], dict):
        raw = field[material_id].get(key, 0.0)
    else:
        raw = field.get(key, 0.0)
    try:
        return float(raw)
    except Exception:
        return 0.0


def agent_snap(eng: Any, agent_id: str) -> dict[str, Any]:
    world = eng.state.world.variables["world"]
    body = deepcopy(eng.state.world.variables["bodies"][agent_id])
    pos = world["agent_positions"][agent_id]
    return {
        "tick": int(eng.state.tick),
        "pos": [int(pos[0]), int(pos[1])],
        "avail": local_avail(world, pos),
        "ex": float(body.get("last_env_exchange") or 0.0),
        "proc": float(body.get("last_intake_processed") or 0.0),
        "internal": float(sum((body.get("internal_materials") or {}).values())),
        "internal_mats": deepcopy(body.get("internal_materials") or {}),
        "energy": float(body.get("energy_reserve") or 0.0),
        "hydration": float(body.get("hydration") or 0.0),
        "fatigue": float(body.get("fatigue") or 0.0),
    }


def psyche_memory(eng: Any, agent_id: str) -> dict[str, Any]:
    agents = eng.state.agents
    st = agents[agent_id]
    # AgentState may wrap psyche differently
    psyche = getattr(st, "psyche", None)
    if psyche is None and isinstance(st, dict):
        psyche = st.get("psyche") or st
    mem = {}
    learning = {}
    working = {}
    if psyche is not None:
        if hasattr(psyche, "memory"):
            mem = deepcopy(getattr(psyche, "memory") or {})
            learning = deepcopy(getattr(psyche, "learning") or {})
            working = deepcopy(getattr(psyche, "working") or {})
        elif isinstance(psyche, dict):
            mem = deepcopy(psyche.get("memory") or {})
            learning = deepcopy(psyche.get("learning") or {})
            working = deepcopy(psyche.get("working") or {})
    # Also check mechanism runtime store
    return {"memory": mem, "learning": learning, "working": working, "raw_type": type(st).__name__}


def episodes_of(eng: Any, agent_id: str) -> list[dict[str, Any]]:
    info = psyche_memory(eng, agent_id)
    eps = (info.get("memory") or {}).get("episodes") or []
    return list(eps) if isinstance(eps, list) else []


def sensorimotor_store(eng: Any, agent_id: str) -> dict[str, Any]:
    """Best-effort pull of sensorimotor store from mechanism runtime."""
    out: dict[str, Any] = {"found": False}
    runtimes = getattr(eng, "mechanism_runtimes", None) or {}
    rt = runtimes.get(agent_id) or getattr(eng, "mechanism_runtime", None)
    if rt is None:
        return out
    # Search nested stores
    for attr in ("mechanisms", "modules", "states", "stores"):
        container = getattr(rt, attr, None)
        if isinstance(container, dict):
            for k, v in container.items():
                store = getattr(v, "store", None) or getattr(v, "sensorimotor_store", None)
                if store is None and hasattr(v, "state"):
                    store = getattr(v.state, "sensorimotor", None)
                if store is not None:
                    cont = getattr(store, "contingencies", None)
                    if cont is None and isinstance(store, dict):
                        cont = store.get("contingencies")
                    if isinstance(cont, dict):
                        out = {
                            "found": True,
                            "path": f"{attr}.{k}",
                            "n_contingencies": len(cont),
                            "sample_keys": list(cont.keys())[:12],
                        }
                        return out
    # Psyche working/learning fallback
    info = psyche_memory(eng, agent_id)
    learning = info.get("learning") or {}
    if "sensorimotor" in learning or "contingencies" in learning:
        out = {"found": True, "path": "psyche.learning", "keys": list(learning.keys())[:20]}
    return out


def classify_experience_components(episodes: list[dict[str, Any]], move_ticks: list[int]) -> dict[str, Any]:
    """Classify whether ordinary memory contains nonsemantic evidence pieces."""
    move_eps = [e for e in episodes if isinstance(e, dict) and str(e.get("action", "")).startswith("MOVE")]
    wait_eps = [e for e in episodes if isinstance(e, dict) and str(e.get("action", "")) == "WAIT"]
    has_action = any(e.get("action") for e in move_eps)
    has_pos = any(e.get("position") for e in move_eps)
    has_effects_on_move = any(
        isinstance(e.get("experienced_effects"), dict) and e.get("experienced_effects")
        for e in move_eps
    )
    # Later body consequence often lands on WAIT episodes after MOVE
    later_body = False
    for t in move_ticks:
        for e in episodes:
            if not isinstance(e, dict):
                continue
            et = int(e.get("tick") or -1)
            if et > t:
                eff = e.get("experienced_effects") or {}
                if isinstance(eff, dict) and any(
                    abs(float(v)) > 1e-9
                    for v in eff.values()
                    if isinstance(v, (int, float))
                ):
                    later_body = True
                    break
    # No explicit temporal edge between MOVE episode and later WAIT consequence
    temporal_edge = False  # architecture has none
    return {
        "A_action_taken": "YES" if has_action else "NO",
        "B_pre_action_context": "PARTIAL",  # not explicit in organism episode
        "C_post_movement_context": "YES" if has_pos else "NO",
        "D_env_physical_in_perception": "NO",  # field not in observation
        "E_intero_before_move": "PARTIAL",  # only via contingency update path if present
        "F_intero_after_move": "YES" if has_effects_on_move else "PARTIAL",
        "G_later_body_consequence_in_memory": "YES" if later_body else "NO",
        "H_explicit_temporal_ordering_edge": "NO",
        "move_episode_count": len(move_eps),
        "wait_episode_count": len(wait_eps),
        "note": "Separate memories ≠ temporal association",
    }


def arrow_table(physical: dict[str, Any], cognitive: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    def add(stage, evidence, status, ref=""):
        rows.append({"stage": stage, "evidence": evidence, "status": status, "ref": ref})
    add("MOVE", physical.get("move_ok"), "DEMONSTRATED" if physical.get("move_ok") else "NULL")
    add("POSITION_CHANGE", physical.get("pos_changed"), "DEMONSTRATED" if physical.get("pos_changed") else "NULL")
    add("LOCAL_ENV_CHANGE", physical.get("avail_changed"), "DEMONSTRATED" if physical.get("avail_changed") else "NULL")
    add("EXCHANGE_CHANGE", physical.get("ex_changed"), "DEMONSTRATED" if physical.get("ex_changed") else "NULL")
    add("INTERNAL_CHANGE", physical.get("internal_changed"), "DEMONSTRATED" if physical.get("internal_changed") else "PARTIAL")
    add("BODY_CONSEQUENCE", physical.get("body_changed"), "DEMONSTRATED" if physical.get("body_changed") else "PARTIAL")
    add("EXPERIENCE_STORAGE", cognitive.get("exp_stored"), cognitive.get("exp_status", "PARTIAL"))
    add("TEMPORAL_ASSOCIATION", cognitive.get("assoc"), cognitive.get("assoc_status", "NULL"))
    add("RETRIEVAL_ELIGIBILITY", cognitive.get("eligible"), cognitive.get("eligible_status", "IMPLEMENTED_BUT_UNPROVEN"))
    add("DECISION_TIME_RETRIEVAL", cognitive.get("retrieved"), cognitive.get("retrieved_status", "NULL"))
    add("PREDICTION", cognitive.get("prediction"), cognitive.get("pred_status", "IMPLEMENTED_BUT_UNPROVEN"))
    add("PROSPECTIVE_VALUE", cognitive.get("value"), cognitive.get("value_status", "IMPLEMENTED_BUT_UNPROVEN"))
    add("CANDIDATE_COMPARISON", cognitive.get("compare"), cognitive.get("compare_status", "IMPLEMENTED_BUT_UNPROVEN"))
    add("SELECTION", cognitive.get("selection"), cognitive.get("selection_status", "NULL"))
    add("FUTURE_EXPOSURE_CHANGE", cognitive.get("future_exposure"), cognitive.get("future_status", "NULL"))
    return rows
