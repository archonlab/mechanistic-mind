"""EFFECTOR_OCCUPANCY_REACHABILITY_TRACE_V1 — researcher-only passive reachability.

Records final effector pose vs VW1/VW5 occupancy geometry at the ETC evaluation
seam. Does not mutate pose, create contact, transmit work, or alter occupancy.
Not cognition-accessible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "EFFECTOR_OCCUPANCY_REACHABILITY_TRACE_V1"
AUTHORITY = "RESEARCHER_TRACE_OVER_EXISTING_EFFECTOR_AND_VW1_GEOMETRY"
CAPABILITY = "effector_occupancy_reachability_trace"
MECHANISM_ID = "effector_occupancy_reachability_trace"
PROFILE_VERSION = "V1"
STATE_SCHEMA = "EFFECTOR_OCCUPANCY_REACHABILITY_TRACE_STATE_V1"
HISTORY_LIMIT_DEFAULT = 64
BANNER = "EFFECTOR↔OCCUPANCY REACHABILITY TRACE · RESEARCHER-ONLY · PASSIVE"


@dataclass
class EffectorOccupancyReachabilityTraceConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "history_limit": int(self.history_limit),
            "schema": SCHEMA,
            "authority": AUTHORITY,
            "profile_version": PROFILE_VERSION,
            "researcher_only": True,
            "cognition_exposed": False,
            "mutates_pose": False,
            "creates_contact": False,
            "creates_work": False,
            "mutates_occupancy": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EffectorOccupancyReachabilityTraceConfig":
        data = data or {}
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT) or HISTORY_LIMIT_DEFAULT),
        )


def effector_occupancy_reachability_trace_is_active(config: Any) -> bool:
    cfg = getattr(config, "effector_occupancy_reachability_trace", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_effector_occupancy_reachability_trace(config: Any, enabled: bool) -> None:
    cur = getattr(config, "effector_occupancy_reachability_trace", None)
    if cur is None:
        config.effector_occupancy_reachability_trace = EffectorOccupancyReachabilityTraceConfig(
            enabled=bool(enabled)
        )
    else:
        cur.enabled = bool(enabled)


@dataclass
class EffectorOccupancyReachabilityTraceState:
    config: EffectorOccupancyReachabilityTraceConfig
    history: list[dict[str, Any]] = field(default_factory=list)
    last_step: dict[str, Any] | None = None
    episode_tick: int = -1
    episode_next: int = 0
    counters: dict[str, int] = field(
        default_factory=lambda: {"steps": 0, "traces": 0, "restores": 0}
    )


def state_of(world: Any) -> EffectorOccupancyReachabilityTraceState | None:
    return getattr(world, "effector_occupancy_reachability_trace_state", None)


def ensure_for_runtime(world: Any, config: Any) -> EffectorOccupancyReachabilityTraceState | None:
    if not effector_occupancy_reachability_trace_is_active(config):
        world.effector_occupancy_reachability_trace_state = None
        return None
    st = state_of(world)
    cfg = getattr(config, "effector_occupancy_reachability_trace", None)
    if not isinstance(cfg, EffectorOccupancyReachabilityTraceConfig):
        cfg = EffectorOccupancyReachabilityTraceConfig.from_dict(
            cfg.to_dict() if hasattr(cfg, "to_dict") else cfg
        )
        config.effector_occupancy_reachability_trace = cfg
    if st is None:
        st = EffectorOccupancyReachabilityTraceState(config=cfg)
        world.effector_occupancy_reachability_trace_state = st
    else:
        st.config = cfg
    return st


def serialize_state(st: EffectorOccupancyReachabilityTraceState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "history": [dict(r) for r in st.history],
        "last_step": dict(st.last_step) if st.last_step else None,
        "episode_tick": int(st.episode_tick),
        "episode_next": int(st.episode_next),
        "counters": dict(st.counters),
        "banner": BANNER,
        "researcher_only": True,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> EffectorOccupancyReachabilityTraceState | None:
    """Restore prior state. Does not emit new traces."""
    if not effector_occupancy_reachability_trace_is_active(config):
        world.effector_occupancy_reachability_trace_state = None
        return None
    if not data:
        st = ensure_for_runtime(world, config)
        if st is not None:
            st.counters["restores"] = int(st.counters.get("restores", 0)) + 1
        return st
    cfg = EffectorOccupancyReachabilityTraceConfig.from_dict(
        data.get("config") if isinstance(data.get("config"), dict) else None
    )
    st = EffectorOccupancyReachabilityTraceState(
        config=cfg,
        history=[dict(r) for r in (data.get("history") or [])],
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else None,
        episode_tick=int(data.get("episode_tick", -1) or -1),
        episode_next=int(data.get("episode_next", 0) or 0),
        counters={
            **{"steps": 0, "traces": 0, "restores": 0},
            **{a: int(b) for a, b in (data.get("counters") or {}).items()},
        },
    )
    st.counters["restores"] = int(st.counters.get("restores", 0)) + 1
    world.effector_occupancy_reachability_trace_state = st
    return st


def _alloc_trace_id(st: EffectorOccupancyReachabilityTraceState, tick: int) -> str:
    if int(st.episode_tick) != int(tick):
        st.episode_tick = int(tick)
        st.episode_next = 0
    st.episode_next += 1
    return f"eort-{int(tick):06d}-{st.episode_next:04d}"


def _agent_selectable_relative_z(config: Any, runtime: Any | None) -> bool:
    """True when agent repertoire includes effector relative_z motor factors."""
    acts: list[str] = []
    if runtime is not None and isinstance(getattr(runtime, "cognition", None), dict):
        acts = list(runtime.cognition.get("available_actions") or [])
    # Tokens that expose body-local relative_z rate control (not semantic dig/ground).
    selectable_markers = (
        "EFFECTOR_Z",
        "RELATIVE_Z",
        "LOWER_HAND",
        "RAISE_HAND",
        "REACH_GROUND",
        "DIG",
    )
    for a in acts:
        u = str(a).upper()
        if any(t in u for t in selectable_markers):
            return True
    return False


def _physical_relative_z_available(config: Any) -> bool:
    try:
        from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
            manipulator_relative_world_actuation_is_active,
        )

        return bool(manipulator_relative_world_actuation_is_active(config))
    except Exception:
        return False


def record_reachability_traces_from_etc_measures(
    world: Any,
    *,
    config: Any,
    tick: int,
    measures: list[tuple[str, str, str, dict[str, Any]]],
    contact_receipts: list[dict[str, Any]],
    holders: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Passive capture using ETC probe measures. No geometry re-solve beyond measure fields."""
    st = ensure_for_runtime(world, config)
    if st is None:
        return None

    contact_by_key: dict[str, dict[str, Any]] = {}
    for r in contact_receipts or []:
        k = f"{r.get('body_id')}|{r.get('effector_id')}"
        if r.get("contact_fact"):
            contact_by_key[k] = r

    holder_rt: dict[str, Any] = {}
    for row in holders or []:
        holder_rt[str(row.get("body_id") or "")] = row.get("runtime")

    traces: list[dict[str, Any]] = []
    phys_rz = _physical_relative_z_available(config)
    for key, body_id, mid, m in measures:
        runtime = holder_rt.get(body_id)
        agent_sel = _agent_selectable_relative_z(config, runtime)
        clearance = m.get("clearance")
        try:
            sep = float(clearance) if clearance is not None and math.isfinite(float(clearance)) else None
        except (TypeError, ValueError):
            sep = None
        geometric_reach = bool(sep is not None and sep <= 1e-9)
        contact_rec = contact_by_key.get(key)
        relative_z = 0.0
        try:
            from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
                relative_z_of,
            )

            relative_z = float(relative_z_of(world, body_id, mid, config=config))
        except Exception:
            relative_z = 0.0

        # Habitual classification for autonomous ground reach:
        if phys_rz and not agent_sel:
            repertoire_class = "REQUIRED_CONTROL_NOT_IN_REPERTOIRE"
        elif agent_sel and abs(relative_z) <= 1e-15 and not geometric_reach:
            repertoire_class = "NOT_SELECTED"
        elif geometric_reach and not contact_rec:
            repertoire_class = "GEOMETRIC_REACH_NO_CONTACT"
        elif not geometric_reach and abs(relative_z) > 1e-15:
            repertoire_class = "ACTUATED_NO_GEOMETRIC_REACH"
        else:
            repertoire_class = "NOT_ESTABLISHED"

        tid = _alloc_trace_id(st, tick)
        terrain = m.get("terrain") if isinstance(m.get("terrain"), dict) else {}
        occ = terrain.get("occupancy_probe") if isinstance(terrain.get("occupancy_probe"), dict) else {}
        src_iv = occ.get("source_interval") if isinstance(occ.get("source_interval"), dict) else None
        tr = {
            "receipt_kind": SCHEMA,
            "schema": SCHEMA,
            "authority": AUTHORITY,
            "mechanism": MECHANISM_ID,
            "profile_version": PROFILE_VERSION,
            "trace_id": tid,
            "tick": int(tick),
            "body_id": str(body_id),
            "effector_id": str(mid),
            "effector_xyz": [
                m.get("effector_x"),
                m.get("effector_y"),
                m.get("effector_z"),
            ],
            "probe_radius": float(m.get("contact_radius") or 0.0)
            if m.get("contact_radius") is not None
            else 0.0,
            "signed_minimum_separation": sep,
            "sign_convention": "clearance=(tip_z-r)-floor_z_max; +separated 0-touch -penetration",
            "geometric_reach": geometric_reach,
            "runtime_contact_fact": bool(contact_rec),
            "contact_episode_id": None if not contact_rec else contact_rec.get("episode_id"),
            "contact_phase": None if not contact_rec else contact_rec.get("phase"),
            "floor_boundary_z": m.get("surface_height"),
            "terrain_cell": m.get("terrain_cell"),
            "nearest_occupancy_interval": src_iv,
            "relative_z": float(relative_z),
            "physical_relative_z_dof": "AVAILABLE" if phys_rz else "ABSENT",
            "research_actuator_path": "AVAILABLE" if phys_rz else "ABSENT",
            "agent_cognition_token": "ABSENT" if not agent_sel else "PRESENT",
            "agent_selectable_motor_factor": "ABSENT" if not agent_sel else "PRESENT",
            "control_repertoire_class": repertoire_class,
            "limiting_constraint": (
                "relative_z_not_in_cognition_action_repertoire"
                if repertoire_class == "REQUIRED_CONTROL_NOT_IN_REPERTOIRE"
                else ("geometric_separation" if not geometric_reach else None)
            ),
            "detection_mode": m.get("detection_mode"),
            "mutates_pose": False,
            "creates_contact": False,
            "creates_work": False,
            "mutates_occupancy": False,
            "researcher_only": True,
            "cognition_exposed": False,
            "optical_geometry_used": False,
            "second_contact_solver": False,
        }
        traces.append(tr)
        st.counters["traces"] = int(st.counters.get("traces", 0)) + 1

    st.counters["steps"] = int(st.counters.get("steps", 0)) + 1
    step = {
        "event": "REACHABILITY_TRACE_STEP",
        "tick": int(tick),
        "traces": traces,
        "n_traces": len(traces),
        "researcher_only": True,
        "banner": BANNER,
    }
    st.last_step = step
    st.history.append(step)
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    world.last_effector_occupancy_reachability_trace_step = step
    return step
