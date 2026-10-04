"""Acanthostega free ResourceObject kinematics.

ONLY in ACANTHOSTEGA_PHASE_B_FREE_OBJECT_KINEMATICS. Minimal translational causal chain:

    held object snapped to the physical effector pose       (update_held_kinematics, UNCHANGED)
    -> existing RELEASE command                               (apply_*_grasp_release_for_holder, UNCHANGED)
    -> object inherits the measured effector world velocity:
           v_eff = shortest_toroidal_delta(pose_T, pose_{T-1}) / dt      (dt = 1 scientific tick)
           v0    = clamp_speed(release_transfer * v_eff, max_free_object_speed)
    -> FREE_MOVING (or FREE_STATIC == free-rest if |v0| < rest_threshold)
    -> one deterministic step per scientific tick, starting at T+1:
           v' = v * exp(-damping_rate * dt)
           |v'| < rest_threshold  ->  v' = (0, 0), FREE_STATIC, no displacement this tick
           else                   ->  x' = wrap(x + v'x dt), y' = wrap(y + v'y dt)
    -> spatial index reconciled by the existing reconcile_contents (derived index).

Not implemented (deliberately): collision of any kind, gravity, z, slope, support, wind,
buoyancy, impact acoustics, damage, THROW, material-dependent damping. Mass is NOT used
(no forces act on a free object in this layer; damping is a kinematic rate).
No object id, velocity, speed, state label or receipt ever reaches cognition.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "free_resource_object_kinematics"
PROFILE_VERSION = "FREE_OBJECT_KINEMATICS_PROFILE_V1"
STATE_SCHEMA = "FREE_RESOURCE_OBJECT_KINEMATICS_STATE_V1"
VELOCITY_MEASUREMENT = "EFFECTOR_WORLD_POSE_TOROIDAL_DIFFERENCE_V1"
DAMPING_LAW = "EXPONENTIAL_VELOCITY_DAMPING_V1"
INTEGRATOR = "DAMP_THEN_DRIFT_WRAP_V1"
MATERIAL_PROPERTY_INPUT = "NOT_USED"
RELEASE_RECEIPT = "RESOURCE_OBJECT_RELEASE_KINEMATICS"
MOTION_RECEIPT = "RESOURCE_OBJECT_FREE_MOTION"
EVENT_STEP = "FREE_RESOURCE_OBJECT_KINEMATICS_STEP"
COLLISION_PHYSICS = "NOT_IMPLEMENTED"

PHYSICAL_STATE_FREE_MOVING = "FREE_MOVING"
# Free-rest is the pre-existing FREE_STATIC state (schema kept; no new rest label).
PHYSICAL_STATE_FREE_REST = "FREE_STATIC"

M_MEASURED = "MEASURED_TOROIDAL_POSE_DIFFERENCE"
M_NO_PREVIOUS = "NO_PREVIOUS_TICK_POSE"
M_DISCONTINUITY = "EFFECTOR_POSE_DISCONTINUITY"
M_NON_FINITE = "NON_FINITE_EFFECTOR_POSE"

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
    "collision_physics": COLLISION_PHYSICS,
}


@dataclass
class FreeObjectKinematicsConfig:
    """Acanthostega free-object kinematics profile. Fresh default OFF; absent field = OFF."""

    enabled: bool = False
    release_transfer: float = 1.0            # rigid effector->object attachment (dimensionless)
    damping_rate: float = 0.25               # 1/tick, exponential velocity decay
    rest_threshold: float = 0.01             # cells/tick, applied after damping
    max_free_object_speed: float = 0.75      # cells/tick numerical guard (physical effector max ~0.57)
    max_effector_displacement_per_tick: float = 1.0  # cells; larger pose jumps = discontinuity
    history_limit: int = 64

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "release_transfer": float(self.release_transfer),
            "damping_rate": float(self.damping_rate),
            "rest_threshold": float(self.rest_threshold),
            "max_free_object_speed": float(self.max_free_object_speed),
            "max_effector_displacement_per_tick": float(self.max_effector_displacement_per_tick),
            "history_limit": int(self.history_limit),
            "dt": 1.0,
            "profile_version": PROFILE_VERSION,
            "velocity_measurement": VELOCITY_MEASUREMENT,
            "damping_law": DAMPING_LAW,
            "integrator": INTEGRATOR,
            "material_property_input": MATERIAL_PROPERTY_INPUT,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "FreeObjectKinematicsConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        for key, expected in (("profile_version", PROFILE_VERSION), ("velocity_measurement", VELOCITY_MEASUREMENT),
                              ("damping_law", DAMPING_LAW), ("integrator", INTEGRATOR)):
            val = data.get(key)
            if val is not None and str(val) != expected:
                raise ValueError(f"unknown free object kinematics {key}: {val}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            release_transfer=float(data.get("release_transfer", 1.0)),
            damping_rate=float(data.get("damping_rate", 0.25)),
            rest_threshold=float(data.get("rest_threshold", 0.01)),
            max_free_object_speed=float(data.get("max_free_object_speed", 0.75)),
            max_effector_displacement_per_tick=float(data.get("max_effector_displacement_per_tick", 1.0)),
            history_limit=int(data.get("history_limit", 64)),
        )


def validate_config(cfg: FreeObjectKinematicsConfig) -> None:
    vals = (cfg.release_transfer, cfg.damping_rate, cfg.rest_threshold,
            cfg.max_free_object_speed, cfg.max_effector_displacement_per_tick)
    if not all(math.isfinite(float(v)) for v in vals):
        raise ValueError("free object kinematics parameters must be finite")
    if not (0.0 <= float(cfg.release_transfer) <= 1.0):
        raise ValueError("release_transfer must be in [0, 1] (passive transfer cannot add energy)")
    if not (0.0 < float(cfg.damping_rate) <= 5.0):
        raise ValueError("damping_rate must be in (0, 5] per tick (objects must come to rest)")
    if not (0.0 < float(cfg.max_free_object_speed) <= 4.0):
        raise ValueError("max_free_object_speed must be in (0, 4] cells/tick")
    if not (0.0 < float(cfg.rest_threshold) < float(cfg.max_free_object_speed)):
        raise ValueError("rest_threshold must be in (0, max_free_object_speed)")
    if not (0.0 < float(cfg.max_effector_displacement_per_tick) <= 8.0):
        raise ValueError("max_effector_displacement_per_tick must be in (0, 8]")
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def free_resource_object_kinematics_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "free_resource_object_kinematics", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.physical_manipulator import world_manipulators_active
    from mechanistic_mind.physical_system.resource_objects import objects_is_active

    return bool(objects_is_active(config) and world_manipulators_active(config))


def set_free_resource_object_kinematics(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "free_resource_object_kinematics", None)
    if cur is None:
        if on:
            config.free_resource_object_kinematics = FreeObjectKinematicsConfig(enabled=True)
        return  # OFF with no config: field stays absent (every earlier preset)
    cur.enabled = on


# ---------------------------------------------------------------------------
# Pure kinematics helpers
# ---------------------------------------------------------------------------


def _wrap(v: float, size: int) -> tuple[float, bool]:
    s = float(size)
    out = float(v) % s
    if out >= s:  # float modulo of tiny negatives can return s
        out = 0.0
    return out, bool(float(v) < 0.0 or float(v) >= s)


def toroidal_pose_delta(prev: tuple[float, float], cur: tuple[float, float], width: int, height: int) -> tuple[float, float]:
    """Shortest signed displacement prev -> cur on the WRAP_PERIODIC world."""
    from mechanistic_mind.planet.topology import toroidal_delta

    return (float(toroidal_delta(float(prev[0]), float(cur[0]), int(width))),
            float(toroidal_delta(float(prev[1]), float(cur[1]), int(height))))


def clamp_speed(vx: float, vy: float, vmax: float) -> tuple[float, float, bool]:
    """Direction preserved, magnitude limited to vmax. Non-finite input -> (0, 0)."""
    if not (math.isfinite(vx) and math.isfinite(vy)):
        return 0.0, 0.0, False
    s = math.hypot(vx, vy)
    if s <= float(vmax) or s == 0.0:
        return float(vx), float(vy), False
    k = float(vmax) / s
    return float(vx * k), float(vy * k), True


def damped_velocity(vx: float, vy: float, cfg: FreeObjectKinematicsConfig) -> tuple[float, float, float]:
    f = math.exp(-float(cfg.damping_rate) * 1.0)
    return float(vx * f), float(vy * f), float(f)


def measure_effector_velocity(
    prev: list[float] | tuple[float, ...] | None,
    cur: tuple[float, float],
    *,
    tick: int,
    width: int,
    height: int,
    cfg: FreeObjectKinematicsConfig,
) -> dict[str, Any]:
    """Velocity from two scientific-tick world poses. prev = [x, y, tick_recorded]."""
    out: dict[str, Any] = {"current_effector_pose": [float(cur[0]), float(cur[1])],
                           "previous_effector_pose": None, "previous_pose_tick": None,
                           "toroidal_effector_delta": None, "measured_effector_velocity": [0.0, 0.0]}
    if not (math.isfinite(float(cur[0])) and math.isfinite(float(cur[1]))):
        out["measurement"] = M_NON_FINITE
        return out
    if prev is None or len(prev) < 3 or int(prev[2]) != int(tick) - 1:
        out["measurement"] = M_NO_PREVIOUS
        if prev is not None and len(prev) >= 3:
            out["previous_effector_pose"] = [float(prev[0]), float(prev[1])]
            out["previous_pose_tick"] = int(prev[2])
        return out
    px, py = float(prev[0]), float(prev[1])
    out["previous_effector_pose"] = [px, py]
    out["previous_pose_tick"] = int(prev[2])
    if not (math.isfinite(px) and math.isfinite(py)):
        out["measurement"] = M_NON_FINITE
        return out
    dx, dy = toroidal_pose_delta((px, py), (float(cur[0]), float(cur[1])), width, height)
    out["toroidal_effector_delta"] = [dx, dy]
    if math.hypot(dx, dy) > float(cfg.max_effector_displacement_per_tick):
        out["measurement"] = M_DISCONTINUITY  # teleport / reset / researcher placement
        return out
    out["measurement"] = M_MEASURED
    out["measured_effector_velocity"] = [dx / 1.0, dy / 1.0]
    return out


def invariant_fingerprint(obj: Any) -> str:
    """Everything motion must NOT change: id, composition, amounts, mass, quantity, optics, material."""
    d = obj.to_dict()
    keep = {k: d.get(k) for k in ("object_id", "mass", "quantity", "composition", "optical_radius",
                                   "optical_response", "interaction_radius", "material_revision")}
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def _zero_counters() -> dict[str, int]:
    return {
        "releases_observed": 0, "releases_moving": 0, "releases_at_rest": 0, "releases_regrasped_same_tick": 0,
        "measurement_no_previous_pose": 0, "measurement_discontinuity": 0, "measurement_non_finite": 0,
        "speed_clamps": 0, "motion_steps": 0, "rest_transitions": 0, "wrap_events": 0,
        "non_finite_velocity_normalized": 0, "reintegration_suppressed": 0, "conservation_violations": 0,
        "grasp_attempts_with_free_moving_in_reach": 0,
    }


@dataclass
class FreeObjectKinematicsState:
    config: FreeObjectKinematicsConfig
    effector_poses: dict[str, list[float]] = field(default_factory=dict)  # "body|manip" -> [x, y, tick]
    last_integrated_tick: int = -1
    release_tick: int = -1
    release_next: int = 0
    motion_tick: int = -1
    motion_next: int = 0
    episodes: dict[str, dict[str, Any]] = field(default_factory=dict)  # object_id -> open motion episode
    counters: dict[str, int] = field(default_factory=_zero_counters)
    release_history: list[dict[str, Any]] = field(default_factory=list)
    motion_history: list[dict[str, Any]] = field(default_factory=list)
    completed_episodes: list[dict[str, Any]] = field(default_factory=list)
    last_step: dict[str, Any] = field(default_factory=dict)


def state_of(world: Any) -> FreeObjectKinematicsState | None:
    raw = getattr(world, "free_object_kinematics_state", None)
    return raw if isinstance(raw, FreeObjectKinematicsState) else None


def ensure_free_object_kinematics_for_runtime(world: Any, config: Any) -> FreeObjectKinematicsState | None:
    if not free_resource_object_kinematics_is_active(config):
        if state_of(world) is not None:
            world.free_object_kinematics_state = None
        normalize_free_moving_to_rest(world)
        return None
    st = state_of(world)
    if st is not None:
        return st
    cfg = FreeObjectKinematicsConfig.from_dict(config.free_resource_object_kinematics.to_dict())
    validate_config(cfg)
    st = FreeObjectKinematicsState(config=cfg)
    world.free_object_kinematics_state = st
    return st


def normalize_free_moving_to_rest(world: Any) -> int:
    """Mechanism OFF: no object may keep moving (FREE_MOVING -> FREE_STATIC, v = 0)."""
    from mechanistic_mind.physical_system.resource_objects import PHYSICAL_STATE_HELD

    n = 0
    for obj in list(getattr(world, "resource_objects", None) or []):
        if str(getattr(obj, "physical_state", "")) == PHYSICAL_STATE_FREE_MOVING:
            obj.physical_state = PHYSICAL_STATE_FREE_REST
            n += 1
        if str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            if float(getattr(obj, "vx", 0.0) or 0.0) != 0.0 or float(getattr(obj, "vy", 0.0) or 0.0) != 0.0:
                obj.vx, obj.vy = 0.0, 0.0
    return n


def _dims(world: Any) -> tuple[int, int]:
    t = getattr(world, "T", None)
    return (int(t.shape[1]), int(t.shape[0])) if t is not None else (32, 32)


def _trim(rows: list[dict[str, Any]], limit: int) -> None:
    if len(rows) > int(limit):
        del rows[: len(rows) - int(limit)]


def _release_id(st: FreeObjectKinematicsState, tick: int) -> str:
    if st.release_tick != int(tick):
        st.release_tick, st.release_next = int(tick), 0
    rid = f"object-release-{int(tick):08d}-{st.release_next:03d}"
    st.release_next += 1
    return rid


def _motion_id(st: FreeObjectKinematicsState, tick: int) -> str:
    if st.motion_tick != int(tick):
        st.motion_tick, st.motion_next = int(tick), 0
    mid = f"object-motion-{int(tick):08d}-{st.motion_next:03d}"
    st.motion_next += 1
    return mid


# ---------------------------------------------------------------------------
# World-step hooks (called from resolve_shared_world_manipulators, once per world tick)
# ---------------------------------------------------------------------------


def integrate_free_objects(world: Any, tick: int) -> list[dict[str, Any]]:
    """Phase A of the world step: one damp-then-drift step for every FREE_MOVING object.

    Runs after the tick-start held snap and BEFORE this tick's GRASP/RELEASE, so an object released
    at tick T is first integrated at T+1 (never twice, never in its release tick). HELD and
    FREE_STATIC objects are never touched. Guarded by last_integrated_tick (idempotent per tick).
    """
    st = state_of(world)
    if st is None:
        return []
    if int(tick) <= int(st.last_integrated_tick):
        st.counters["reintegration_suppressed"] += 1
        return []
    st.last_integrated_tick = int(tick)
    cfg = st.config
    w, h = _dims(world)
    rows: list[dict[str, Any]] = []
    from mechanistic_mind.physical_system.resource_objects import ensure_resource_object_state

    for obj in sorted(ensure_resource_object_state(world), key=lambda o: str(o.object_id)):
        if str(obj.physical_state) != PHYSICAL_STATE_FREE_MOVING:
            continue
        oid = str(obj.object_id)
        ep = st.episodes.get(oid)
        if ep is None:  # FREE_MOVING without a release episode (restored / researcher-set)
            ep = st.episodes[oid] = {"release_receipt_id": None, "release_tick": None, "path_length": 0.0,
                                     "moving_ticks": 0, "wrap_count": 0, "speed_clamped": False,
                                     "invariant_fingerprint": invariant_fingerprint(obj),
                                     "initial_speed": math.hypot(float(obj.vx or 0.0), float(obj.vy or 0.0))}
        x0, y0 = float(obj.x), float(obj.y)
        vx0, vy0 = float(obj.vx or 0.0), float(obj.vy or 0.0)
        normalized = False
        if not (math.isfinite(vx0) and math.isfinite(vy0)):
            vx0, vy0, normalized = 0.0, 0.0, True
            st.counters["non_finite_velocity_normalized"] += 1
        cvx, cvy, clamped = clamp_speed(vx0, vy0, cfg.max_free_object_speed)
        unclamped = [vx0, vy0]
        if clamped:
            st.counters["speed_clamps"] += 1
            ep["speed_clamped"] = True
        # Ground-friction preset (when active): BYPASS legacy exponential damping.
        # grounded → Coulomb only; airborne → conserve horizontal v (AIR_DRAG=NO).
        # Prior presets: friction state absent → legacy damp-then-drift unchanged.
        # FOGF static twin (when ON): static cone then FOGF kinetic once; parent presets unchanged.
        friction_plan = None
        static_plan = None
        try:
            from mechanistic_mind.physical_system.free_resource_object_static_traction_threshold import (
                state_of as _fost_state,
                plan_free_object_static_traction_step,
                record_static_traction_receipt,
            )
            if _fost_state(world) is not None:
                static_plan = plan_free_object_static_traction_step(
                    world, obj, cvx, cvy, cfg, tick=int(tick), episode=ep,
                )
        except Exception:
            static_plan = None
        if static_plan is not None:
            if static_plan.get("skipped_duplicate_same_tick"):
                # Already applied this tick for object_id — conserve; never stack FOGF.
                friction_plan = {
                    "vx": float(cvx),
                    "vy": float(cvy),
                    "rest_transition": False,
                    "damping_factor": 1.0,
                    "damping_law": "FOST_SKIPPED_DUPLICATE_SAME_TICK",
                    "mode": "SKIPPED",
                    "state_class": "SKIPPED",
                    "static_traction_twin": True,
                    "legacy_fok_damping": False,
                }
            else:
                friction_plan = static_plan
        else:
            try:
                from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
                    plan_free_object_horizontal_step,
                    record_friction_receipt,
                )
                friction_plan = plan_free_object_horizontal_step(world, obj, cvx, cvy, cfg)
            except Exception:
                friction_plan = None
        if friction_plan is not None:
            vx1 = float(friction_plan["vx"])
            vy1 = float(friction_plan["vy"])
            factor = friction_plan.get("damping_factor")
            rest = bool(friction_plan.get("rest_transition"))
            damping_law_used = str(friction_plan.get("damping_law") or friction_plan.get("friction_law") or "GROUND_FRICTION")
            damping_rate_used = None
            material_input = "SURFACE_AFFINITY_SUPPORT_CELL"
        else:
            vx1, vy1, factor = damped_velocity(cvx, cvy, cfg)
            rest = bool(math.hypot(vx1, vy1) < float(cfg.rest_threshold))
            damping_law_used = DAMPING_LAW
            damping_rate_used = float(cfg.damping_rate)
            material_input = MATERIAL_PROPERTY_INPUT
        wrapped = False
        elev_plan = None
        if rest:
            vx1, vy1 = 0.0, 0.0
            x1, y1 = x0, y0
        else:
            x1, wx = _wrap(x0 + vx1 * 1.0, w)
            y1, wy = _wrap(y0 + vy1 * 1.0, h)
            wrapped = bool(wx or wy)
            # Elevation support (when ON): friction → proposal → elev transitions → commit.
            # Prior presets: SES state absent → identity commit (unchanged).
            from mechanistic_mind.physical_system.surface_elevation_support import (
                surface_elevation_support_active_on_world,
                commit_free_object_elevation_gate,
            )
            if surface_elevation_support_active_on_world(world, None):
                elev_plan = commit_free_object_elevation_gate(
                    world, None, obj,
                    x0=x0, y0=y0, x1=float(x1), y1=float(y1),
                    vx=float(vx1), vy=float(vy1), tick=int(tick),
                )
                if elev_plan is not None and elev_plan.get("active"):
                    x1 = float(obj.x)
                    y1 = float(obj.y)
                    vx1 = float(obj.vx)
                    vy1 = float(obj.vy)
                    if not elev_plan.get("accepted"):
                        rest = bool(math.hypot(vx1, vy1) < float(cfg.rest_threshold))
                        wrapped = False
        disp = [float(vx1 * 1.0), float(vy1 * 1.0)]
        step_len = float(math.hypot(disp[0], disp[1]))
        if elev_plan is None or not elev_plan.get("active"):
            obj.x, obj.y, obj.vx, obj.vy = float(x1), float(y1), float(vx1), float(vy1)
        else:
            # Elev gate already committed pose/velocity on the object.
            obj.vx, obj.vy = float(vx1), float(vy1)
        if rest:
            obj.physical_state = PHYSICAL_STATE_FREE_REST
        st.counters["motion_steps"] += 1
        if wrapped:
            st.counters["wrap_events"] += 1
            ep["wrap_count"] = int(ep.get("wrap_count", 0)) + 1
        ep["path_length"] = float(ep.get("path_length", 0.0)) + step_len
        ep["moving_ticks"] = int(ep.get("moving_ticks", 0)) + 1
        fp = invariant_fingerprint(obj)
        conserved = fp == ep.get("invariant_fingerprint")
        if not conserved:
            st.counters["conservation_violations"] += 1
        if friction_plan is not None:
            if bool(friction_plan.get("static_traction_twin")):
                record_static_traction_receipt(
                    world,
                    tick=int(tick),
                    object_id=oid,
                    plan=friction_plan,
                    start_position=[x0, y0],
                    end_position=[float(x1), float(y1)],
                    end_state=str(obj.physical_state),
                    velocity_before=[cvx, cvy],
                    velocity_after=[float(vx1), float(vy1)],
                )
            else:
                from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
                    record_friction_receipt,
                )
                record_friction_receipt(
                    world,
                    tick=int(tick),
                    object_id=oid,
                    plan=friction_plan,
                    start_position=[x0, y0],
                    end_position=[float(x1), float(y1)],
                    end_state=str(obj.physical_state),
                )
        rec = {
            "receipt_kind": MOTION_RECEIPT,
            "motion_id": _motion_id(st, tick),
            "tick": int(tick),
            "object_id": oid,
            "release_receipt_ref": ep.get("release_receipt_id"),
            "start_position": [x0, y0],
            "end_position": [float(x1), float(y1)],
            "start_velocity": [float(obj_v) for obj_v in unclamped],
            "velocity_after_clamp": [cvx, cvy],
            "end_velocity": [float(vx1), float(vy1)],
            "end_speed": float(math.hypot(vx1, vy1)),
            "damping_law": damping_law_used,
            "damping_rate": damping_rate_used if damping_rate_used is not None else float(cfg.damping_rate),
            "damping_factor": (None if factor is None else float(factor)),
            "rest_threshold": float(cfg.rest_threshold),
            "dt": 1.0,
            "displacement": disp,
            "step_length": step_len,
            "wrap_occurred": wrapped,
            "speed_clamped": bool(clamped),
            "non_finite_velocity_normalized": normalized,
            "rest_transition": rest,
            "end_state": str(obj.physical_state),
            "material_property_input": material_input,
            "ground_friction_replaced_damping": bool(friction_plan is not None),
            "ground_friction_mode": (None if friction_plan is None else friction_plan.get("mode")),
            "static_traction_twin": bool(friction_plan is not None and friction_plan.get("static_traction_twin")),
            "static_traction_state_class": (None if friction_plan is None else friction_plan.get("state_class")),
            "invariants_conserved": bool(conserved),
            "contact_detected": False,
            "impulse_transferred": False,
            **RESEARCHER_FLAGS,
        }
        if rest:
            st.counters["rest_transitions"] += 1
            rel_t = ep.get("release_tick")
            done = {
                "object_id": oid,
                "release_receipt_ref": ep.get("release_receipt_id"),
                "release_tick": rel_t,
                "rest_tick": int(tick),
                "ticks_to_rest": (int(tick) - int(rel_t)) if rel_t is not None else None,
                "moving_ticks": int(ep["moving_ticks"]),
                "path_length": float(ep["path_length"]),
                "wrap_count": int(ep["wrap_count"]),
                "initial_speed": float(ep.get("initial_speed") or 0.0),
                "speed_clamped": bool(ep.get("speed_clamped")),
                "invariants_conserved": bool(conserved),
            }
            rec["episode"] = done
            st.completed_episodes.append(done)
            _trim(st.completed_episodes, cfg.history_limit)
            del st.episodes[oid]
        rows.append(rec)
        st.motion_history.append(rec)
    _trim(st.motion_history, cfg.history_limit)
    return rows


def apply_release_transfer(world: Any, holders: list[dict[str, Any]], receipts: list[dict[str, Any]],
                           tick: int) -> list[dict[str, Any]]:
    """Phase B: after the (unchanged) GRASP/RELEASE loop of tick T, give each object released at T the
    measured effector velocity. An object re-grasped in the same tick keeps HELD (no motion)."""
    st = state_of(world)
    if st is None:
        return []
    cfg = st.config
    w, h = _dims(world)
    from mechanistic_mind.physical_system.physical_manipulator import MANIPULATOR_ID
    from mechanistic_mind.physical_system.resource_objects import ensure_resource_object_state

    by_id = {str(o.object_id): o for o in ensure_resource_object_state(world)}
    rows: list[dict[str, Any]] = []
    hand_recs: list[dict[str, Any]] = []
    for rec in receipts or []:
        hands = rec.get("hands") if isinstance(rec, dict) else None
        if isinstance(hands, dict):
            hand_recs.extend(hands[k] for k in sorted(hands) if isinstance(hands.get(k), dict))
        elif isinstance(rec, dict):
            hand_recs.append(rec)
    moving_ids = {oid for oid, o in by_id.items() if str(o.physical_state) == PHYSICAL_STATE_FREE_MOVING}
    for hrec in hand_recs:
        ev = str(hrec.get("event") or "")
        if ev.startswith("GRASP_FAILED") and moving_ids:
            st.counters["grasp_attempts_with_free_moving_in_reach"] += int(_moving_in_reach(
                by_id, moving_ids, hrec, holders, w, h))
        if ev != "RELEASE_SUCCEEDED":
            continue
        oid = str(hrec.get("object_id") or "")
        obj = by_id.get(oid)
        if obj is None:
            continue
        st.counters["releases_observed"] += 1
        body_id = str(hrec.get("body_id") or "")
        mid = str(hrec.get("manipulator_id") or MANIPULATOR_ID)
        cur = hrec.get("effector_xy") or hrec.get("release_xy") or [obj.x, obj.y]
        cur = (float(cur[0]), float(cur[1]))
        rid = _release_id(st, tick)
        base = {
            "receipt_kind": RELEASE_RECEIPT,
            "release_id": rid,
            "tick": int(tick),
            "object_id": oid,
            "releasing_body_id": body_id,
            "effector_side": mid,
            "source_action_receipt": {"event": ev, "manipulator_action": hrec.get("manipulator_action"),
                                      "body_id": body_id, "manipulator_id": mid, "tick": int(tick)},
            "release_transfer": float(cfg.release_transfer),
            "dt": 1.0,
            "velocity_measurement": VELOCITY_MEASUREMENT,
            "body_velocity_used": False,
            **RESEARCHER_FLAGS,
        }
        if str(obj.physical_state) != PHYSICAL_STATE_FREE_REST or obj.holder_body_id:
            st.counters["releases_regrasped_same_tick"] += 1
            row = {**base, "outcome": "REGRASPED_SAME_TICK", "initial_free_state": None,
                   "inherited_velocity_before_clamp": [0.0, 0.0], "velocity_after_clamp": [0.0, 0.0],
                   "speed_clamped": False, "position": [float(obj.x), float(obj.y)],
                   "integrated_in_release_tick": False}
            rows.append(row)
            continue
        meas = measure_effector_velocity(st.effector_poses.get(f"{body_id}|{mid}"), cur,
                                         tick=int(tick), width=w, height=h, cfg=cfg)
        m = meas["measurement"]
        if m == M_NO_PREVIOUS:
            st.counters["measurement_no_previous_pose"] += 1
        elif m == M_DISCONTINUITY:
            st.counters["measurement_discontinuity"] += 1
        elif m == M_NON_FINITE:
            st.counters["measurement_non_finite"] += 1
        vex, vey = meas["measured_effector_velocity"]
        ivx, ivy = float(cfg.release_transfer) * vex, float(cfg.release_transfer) * vey
        cvx, cvy, clamped = clamp_speed(ivx, ivy, cfg.max_free_object_speed)
        if clamped:
            st.counters["speed_clamps"] += 1
        speed = math.hypot(cvx, cvy)
        px, _ = _wrap(cur[0], w)
        py, _ = _wrap(cur[1], h)
        obj.x, obj.y = float(px), float(py)
        if speed < float(cfg.rest_threshold):
            obj.vx, obj.vy = 0.0, 0.0
            obj.physical_state = PHYSICAL_STATE_FREE_REST
            st.counters["releases_at_rest"] += 1
        else:
            obj.vx, obj.vy = float(cvx), float(cvy)
            obj.physical_state = PHYSICAL_STATE_FREE_MOVING
            st.counters["releases_moving"] += 1
            st.episodes[oid] = {"release_receipt_id": rid, "release_tick": int(tick), "path_length": 0.0,
                                "moving_ticks": 0, "wrap_count": 0, "speed_clamped": bool(clamped),
                                "invariant_fingerprint": invariant_fingerprint(obj), "initial_speed": float(speed)}
        row = {
            **base,
            "outcome": "RELEASED",
            **meas,
            "measured_effector_speed": float(math.hypot(vex, vey)),
            "inherited_velocity_before_clamp": [float(ivx), float(ivy)],
            "inherited_speed_before_clamp": float(math.hypot(ivx, ivy)) if math.isfinite(ivx) and math.isfinite(ivy) else None,
            "velocity_after_clamp": [float(obj.vx), float(obj.vy)],
            "speed_after_clamp": float(math.hypot(obj.vx, obj.vy)),
            "max_free_object_speed": float(cfg.max_free_object_speed),
            "speed_clamped": bool(clamped),
            "rest_threshold": float(cfg.rest_threshold),
            "initial_free_state": str(obj.physical_state),
            "position": [float(obj.x), float(obj.y)],
            "integrated_in_release_tick": False,
            "first_integration_tick": int(tick) + 1 if str(obj.physical_state) == PHYSICAL_STATE_FREE_MOVING else None,
            "invariant_fingerprint": invariant_fingerprint(obj),
        }
        rows.append(row)
        st.release_history.append(row)
        try:
            from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
                note_release_horizontal_velocity,
            )

            cfg_note = next(
                (h.get("config") for h in holders if h.get("config") is not None),
                None,
            ) or getattr(getattr(world, "_host_runtime", None), "config", None)
            if cfg_note is not None:
                note_release_horizontal_velocity(
                    world,
                    cfg_note,
                    object_id=oid,
                    vx=float(obj.vx),
                    vy=float(obj.vy),
                    velocity_measurement=str(m),
                    tick=int(tick),
                )
        except Exception:
            pass
    _trim(st.release_history, cfg.history_limit)
    return rows


def _moving_in_reach(by_id: dict[str, Any], moving_ids: set[str], hrec: dict[str, Any],
                     holders: list[dict[str, Any]], w: int, h: int) -> bool:
    from mechanistic_mind.physical_system.physical_manipulator import object_surface_in_reach

    ex = hrec.get("effector_xy")
    row = next((r for r in holders if str(r.get("body_id")) == str(hrec.get("body_id"))), None)
    if not ex or row is None:
        return False
    return any(object_surface_in_reach(by_id[o], float(ex[0]), float(ex[1]), width=w, height=h,
                                       config=row["config"]) for o in sorted(moving_ids) if o in by_id)


def record_effector_poses(world: Any, holders: list[dict[str, Any]], tick: int) -> None:
    """Phase C (end of the world step): authoritative effector world poses of tick T, the reference
    for a RELEASE at T+1. Derived only from body pose/heading/aperture (no independent limb state)."""
    st = state_of(world)
    if st is None:
        return
    w, h = _dims(world)
    from mechanistic_mind.physical_system.physical_manipulator import (
        BILATERAL_IDS,
        MANIPULATOR_ID,
        bilateral_manipulator_is_active,
        effector_world_xy,
        manipulator_is_active,
    )

    poses: dict[str, list[float]] = {}
    for row in sorted(holders, key=lambda r: str(r["body_id"])):
        cfg = row["config"]
        if bilateral_manipulator_is_active(cfg):
            mids = list(BILATERAL_IDS)
        elif manipulator_is_active(cfg):
            mids = [str(getattr(getattr(cfg, "single_physical_manipulator", None), "manipulator_id", None)
                        or MANIPULATOR_ID)]
        else:
            continue
        for mid in mids:
            ex, ey = effector_world_xy(row["body"], width=w, height=h, config=cfg, manipulator_id=mid,
                                       runtime=row.get("runtime"))
            poses[f"{row['body_id']}|{mid}"] = [float(ex), float(ey), int(tick)]
    st.effector_poses = poses


def finish_step(world: Any, tick: int, motion: list[dict[str, Any]], releases: list[dict[str, Any]]) -> None:
    st = state_of(world)
    if st is None:
        return
    st.last_step = {"event": EVENT_STEP, "tick": int(tick), "motion": motion, "releases": releases}
    world.last_free_object_step = st.last_step


# ---------------------------------------------------------------------------
# Snapshot / restore / copy
# ---------------------------------------------------------------------------


def serialize_state(st: FreeObjectKinematicsState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "effector_poses": {k: [float(v[0]), float(v[1]), int(v[2])] for k, v in sorted(st.effector_poses.items())},
        "last_integrated_tick": int(st.last_integrated_tick),
        "release_allocator": {"tick": int(st.release_tick), "next_sequence": int(st.release_next)},
        "motion_allocator": {"tick": int(st.motion_tick), "next_sequence": int(st.motion_next)},
        "episodes": {k: dict(v) for k, v in sorted(st.episodes.items())},
        "counters": dict(st.counters),
        "release_history": list(st.release_history),
        "motion_history": list(st.motion_history),
        "completed_episodes": list(st.completed_episodes),
    }


def _state_from_data(cfg: FreeObjectKinematicsConfig, data: dict[str, Any]) -> FreeObjectKinematicsState:
    ra = data.get("release_allocator") or {}
    ma = data.get("motion_allocator") or {}
    return FreeObjectKinematicsState(
        config=cfg,
        effector_poses={str(k): [float(v[0]), float(v[1]), int(v[2])] for k, v in (data.get("effector_poses") or {}).items()},
        last_integrated_tick=int(data.get("last_integrated_tick", -1)),
        release_tick=int(ra.get("tick", -1)), release_next=int(ra.get("next_sequence", 0)),
        motion_tick=int(ma.get("tick", -1)), motion_next=int(ma.get("next_sequence", 0)),
        episodes={str(k): dict(v) for k, v in (data.get("episodes") or {}).items()},
        counters={**_zero_counters(), **{k: int(v) for k, v in (data.get("counters") or {}).items()}},
        release_history=list(data.get("release_history") or []),
        motion_history=list(data.get("motion_history") or []),
        completed_episodes=list(data.get("completed_episodes") or []),
    )


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> FreeObjectKinematicsState | None:
    """Mechanism OFF (every older snapshot) -> no state and every free object at rest (v = 0).
    Mechanism ON without saved state (older snapshot applied into the new preset) -> fresh state with
    an EMPTY effector pose history: the first RELEASE after restore measures NO_PREVIOUS_TICK_POSE and
    inherits zero velocity (no fictitious impulse for a held object)."""
    if not free_resource_object_kinematics_is_active(config):
        world.free_object_kinematics_state = None
        normalize_free_moving_to_rest(world)
        return None
    if not isinstance(data, dict) or not data:
        world.free_object_kinematics_state = None
        normalize_free_moving_to_rest(world)
        return ensure_free_object_kinematics_for_runtime(world, config)
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(f"unknown free object kinematics state schema: {data.get('schema_version')}")
    saved = FreeObjectKinematicsConfig.from_dict(data.get("config") or {})
    cfg = FreeObjectKinematicsConfig.from_dict(config.free_resource_object_kinematics.to_dict())
    validate_config(cfg)
    if saved.to_dict() != cfg.to_dict():
        raise ValueError("free object kinematics parameters differ from the runtime config")
    st = _state_from_data(cfg, data)
    world.free_object_kinematics_state = st
    return st


def copy_state(st: FreeObjectKinematicsState | None) -> FreeObjectKinematicsState | None:
    if st is None:
        return None
    data = json.loads(json.dumps(serialize_state(st)))
    return _state_from_data(FreeObjectKinematicsConfig.from_dict(data["config"]), data)


# ---------------------------------------------------------------------------
# Researcher views (never cognition)
# ---------------------------------------------------------------------------


def object_overlay(world: Any) -> list[dict[str, Any]]:
    """Derived per-object researcher view (pose/velocity read from the authoritative object)."""
    out = []
    for obj in sorted(list(getattr(world, "resource_objects", None) or []), key=lambda o: str(o.object_id)):
        vx, vy = float(obj.vx or 0.0), float(obj.vy or 0.0)
        state = str(obj.physical_state)
        out.append({
            "object_id": str(obj.object_id),
            "x": float(obj.x), "y": float(obj.y),
            "vx": vx, "vy": vy,
            "speed": float(math.hypot(vx, vy)),
            "physical_state": state,
            "motion_status": ("MOVING" if state == PHYSICAL_STATE_FREE_MOVING else
                              "HELD" if state == "HELD" else "FREE_REST"),
            **RESEARCHER_FLAGS,
        })
    return out


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile": st.config.to_dict(),
        "counters": dict(st.counters),
        "last_integrated_tick": int(st.last_integrated_tick),
        "objects": object_overlay(world),
        "open_episodes": {k: {kk: v.get(kk) for kk in ("release_receipt_id", "release_tick", "path_length",
                                                        "moving_ticks", "wrap_count")}
                          for k, v in sorted(st.episodes.items())},
        "recent_releases": [
            {k: r.get(k) for k in ("release_id", "tick", "object_id", "effector_side", "measurement",
                                   "measured_effector_speed", "speed_after_clamp", "speed_clamped",
                                   "initial_free_state")}
            for r in st.release_history[-8:]
        ],
        "recent_completed_episodes": list(st.completed_episodes[-8:]),
        "labels": ["researcher-only", "not agent-accessible", "collision physics: not implemented",
                   "no gravity / no z", "damping: common coefficient, material-independent"],
        **RESEARCHER_FLAGS,
    }


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "free_resource_object_kinematics.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "description": (
            "Acanthostega free ResourceObject kinematics: on the existing RELEASE the object inherits the "
            "effector world velocity measured as the toroidal pose difference between consecutive "
            "scientific ticks, then moves deterministically with exponential damping until exact rest. "
            "No collision, gravity, z, sound or THROW command. Nothing reaches cognition."
        ),
    }
