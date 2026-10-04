"""Acanthostega Beta 4 · Effector bounded actuator effort (V1).

Mechanism: effector_bounded_actuator_effort
Preset: ACANTHOSTEGA_BETA4_EFFECTOR_BOUNDED_ACTUATOR_EFFORT

Acts through the existing body-local relative_z channel.
Effector remains KINEMATIC — no tip mass / momentum / KE.

Model:
  relative_z command
    → kinematically admissible Δq (rate + reach)
    → generic external constraint admission
    → achieved Δq
    → bounded actuator work against EXTERNAL blocked displacement only

Work source: ABSTRACT_BOUNDED_ACTUATOR_V1 (finite capacity; not metabolism).
Blocked work policy: DISSIPATED_AT_ACTUATOR_CONTACT (rigid terrain; no
deformation energy deposited into terrain in V1).

Terrain is the first constraint fixture — actuator logic is not terrain-specific.
No DIG / TOUCH / EXCAVATE. Cognition repertoire unchanged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Protocol

from mechanistic_mind.physical_system.flat_ground_gravity import GRAVITY_ACCELERATION
from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
    DEFAULT_MAX_DELTA_Z_PER_TICK,
    DEFAULT_MAX_RELATIVE_Z,
    NEW_DOF,
    NEW_DOF_FRAME,
    manipulator_relative_world_actuation_is_active,
    relative_z_of,
    request_relative_effector_displacement,
)

MECHANISM_ID = "effector_bounded_actuator_effort"
PROFILE_VERSION = "EFFECTOR_BOUNDED_ACTUATOR_EFFORT_PROFILE_V1"
STATE_SCHEMA = "EFFECTOR_BOUNDED_ACTUATOR_EFFORT_STATE_V1"
RECEIPT_KIND = "EFFECTOR_ACTUATOR_EFFORT"
EVENT_STEP = "EFFECTOR_ACTUATOR_EFFORT_STEP"

MECHANICAL_WORK_SOURCE = "ABSTRACT_BOUNDED_ACTUATOR_V1"
BLOCKED_WORK_POLICY = "DISSIPATED_AT_ACTUATOR_CONTACT"
ACTUATOR_MODEL = "BOUNDED_WORK_PER_TICK_ALONG_RELATIVE_Z"

# Capacity: organism-scale weight × one kinematic rate step.
# m_ref=1.0 (BODY-1 default), g=GRAVITY_ACCELERATION, Δz_rate=DEFAULT_MAX_DELTA_Z_PER_TICK.
# ≈ 1.0 * (2/110) * 0.1075 ≈ 0.0019545 work units / tick.
# Coherent with BNLT normal-load scale (mg) and below one MOVE KE (~0.0075).
DEFAULT_MASS_REF = 1.0
DEFAULT_MAX_WORK_PER_TICK = (
    float(DEFAULT_MASS_REF) * float(GRAVITY_ACCELERATION) * float(DEFAULT_MAX_DELTA_Z_PER_TICK)
)
HISTORY_LIMIT_DEFAULT = 64

BANNER = (
    "BETA4 · EFFECTOR BOUNDED ACTUATOR EFFORT V1 · RELATIVE_Z · "
    "NO TIP MASS · ABSTRACT CAPACITY · RIGID-CONTACT DISSIPATION"
)


# ---------------------------------------------------------------------------
# Generic external constraint interface (terrain is one consumer)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExternalConstraintResponse:
    """Admission result for a proposed relative_z displacement.

    Generic — constraint_kind identifies the fixture (terrain, future object, …).
    """

    admitted_delta: float
    blocked_delta: float
    opposing: bool
    constraint_kind: str
    normal: tuple[float, float, float] | None = None
    contact_point: list[float] | None = None
    surface_height: float | None = None
    toi: float | None = None
    inward_normal_component: float = 0.0
    clearance_before: float | None = None
    episode_hint: str | None = None


class ExternalRelativeConstraint(Protocol):
    def admit_relative_z(
        self,
        *,
        world: Any,
        config: Any,
        body: Any,
        body_id: str,
        effector_id: str,
        relative_z_before: float,
        proposed_delta: float,
        runtime: Any | None = None,
    ) -> ExternalConstraintResponse: ...


@dataclass
class TerrainRelativeZConstraint:
    """Terrain surface as external constraint on relative_z (vertical tip).

    Nonpenetration is LOCAL to relative_z — does not alter Phase C body response.
    """

    epsilon: float = 1e-9

    def admit_relative_z(
        self,
        *,
        world: Any,
        config: Any,
        body: Any,
        body_id: str,
        effector_id: str,
        relative_z_before: float,
        proposed_delta: float,
        runtime: Any | None = None,
    ) -> ExternalConstraintResponse:
        from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
            effector_terrain_contact_geometry_is_active,
            effector_world_pose,
            sample_terrain_at,
        )

        if not effector_terrain_contact_geometry_is_active(config):
            return ExternalConstraintResponse(
                admitted_delta=float(proposed_delta),
                blocked_delta=0.0,
                opposing=False,
                constraint_kind="none",
            )

        w = int(world.T.shape[1])
        h = int(world.T.shape[0])
        ex, ey, ez = effector_world_pose(
            body,
            width=w,
            height=h,
            config=config,
            manipulator_id=str(effector_id),
            runtime=runtime,
            world=world,
            body_id=str(body_id),
        )
        # Pose already includes relative_z_before; centre_z = tip_z - relative_z.
        centre = float(ez) - float(relative_z_before)
        # VW5: floor-below from occupancy at tip z; else legacy CSG/SES heightfield.
        use_vw5 = False
        try:
            from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
                effector_held_occupancy_exertion_bridge_is_active,
                occupancy_sample_as_terrain,
            )

            use_vw5 = bool(effector_held_occupancy_exertion_bridge_is_active(config))
        except Exception:
            use_vw5 = False
        if use_vw5:
            terrain = occupancy_sample_as_terrain(
                world, ex, ey, float(ez), radius=0.0, config=config
            )
        else:
            terrain = sample_terrain_at(world, ex, ey, config=config)
        surface_h = float(terrain["height"])
        nx = float(terrain["normal_x"])
        ny = float(terrain["normal_y"])
        nz = float(terrain["normal_z"])
        # No occupancy floor → free space (do not invent false contact from max surface).
        if use_vw5 and not math.isfinite(surface_h):
            return ExternalConstraintResponse(
                admitted_delta=float(proposed_delta),
                blocked_delta=0.0,
                opposing=False,
                constraint_kind="terrain_surface",
                normal=(nx, ny, nz),
                surface_height=None,
                toi=1.0,
                inward_normal_component=0.0,
                clearance_before=float("inf"),
            )
        # Point probe radius = 0: tip_z >= surface_h - eps.
        z_min_rel = float(surface_h) - float(centre)
        clr_before = float(ez) - float(surface_h)

        prop = float(proposed_delta)
        # Outward / free raising: never opposed by terrain nonpenetration.
        if prop >= -1e-15:
            return ExternalConstraintResponse(
                admitted_delta=prop,
                blocked_delta=0.0,
                opposing=False,
                constraint_kind="terrain_surface",
                normal=(nx, ny, nz),
                contact_point=[float(ex), float(ey), float(surface_h)]
                if clr_before <= float(self.epsilon)
                else None,
                surface_height=surface_h,
                toi=1.0,
                inward_normal_component=0.0,
                clearance_before=clr_before,
            )

        tentative = float(relative_z_before) + prop
        # Still strictly above surface after full proposed step.
        if tentative >= z_min_rel - float(self.epsilon):
            return ExternalConstraintResponse(
                admitted_delta=prop,
                blocked_delta=0.0,
                opposing=False,
                constraint_kind="terrain_surface",
                normal=(nx, ny, nz),
                surface_height=surface_h,
                toi=1.0,
                inward_normal_component=0.0,
                clearance_before=clr_before,
            )

        # Clip at surface: admitted = z_min_rel - before (≤ 0).
        admitted = float(z_min_rel - float(relative_z_before))
        if admitted > 0.0:
            admitted = 0.0
        if admitted < prop:
            # proposed is more negative; clamp
            admitted = max(prop, admitted)
        # Already at/below surface: no further inward motion.
        if clr_before <= float(self.epsilon):
            admitted = 0.0
        blocked = float(prop - admitted)

        # World displacement of blocked relative_z (body-local z ≡ world-up).
        # Inward loading: positive when blocked motion points into the surface.
        inward = max(0.0, -(nx * 0.0 + ny * 0.0 + nz * blocked))

        # TOI along vertical path (0 = start, 1 = full proposed).
        if abs(prop) > 1e-18:
            toi = float(admitted / prop) if admitted != 0.0 or abs(prop) > 0 else 0.0
            toi = max(0.0, min(1.0, toi))
        else:
            toi = 1.0
        if clr_before <= float(self.epsilon):
            toi = 0.0

        tip_after_z = float(centre) + float(relative_z_before) + float(admitted)
        del tip_after_z
        return ExternalConstraintResponse(
            admitted_delta=float(admitted),
            blocked_delta=float(blocked),
            opposing=bool(abs(blocked) > 1e-15),
            constraint_kind="terrain_surface",
            normal=(nx, ny, nz),
            contact_point=[float(ex), float(ey), float(surface_h)],
            surface_height=surface_h,
            toi=float(toi),
            inward_normal_component=float(inward),
            clearance_before=clr_before,
        )


def default_external_constraints(config: Any) -> list[ExternalRelativeConstraint]:
    """Repository-native constraint stack.

    Held-object terrain (when transmission ON) is evaluated with tip terrain;
    compose_constraint_responses keeps the most-restrictive winner for work.
    """
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_terrain_contact_geometry_is_active,
    )

    out: list[ExternalRelativeConstraint] = []
    try:
        from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
            HeldObjectTerrainRelativeZConstraint,
            held_resource_object_terrain_mechanical_transmission_is_active,
        )

        if held_resource_object_terrain_mechanical_transmission_is_active(config):
            eps = float(
                getattr(
                    getattr(
                        config, "held_resource_object_terrain_mechanical_transmission", None
                    ),
                    "contact_epsilon",
                    1e-9,
                )
                or 1e-9
            )
            out.append(HeldObjectTerrainRelativeZConstraint(epsilon=eps))
    except Exception:
        pass
    if effector_terrain_contact_geometry_is_active(config):
        eps = float(
            getattr(
                getattr(config, "effector_terrain_contact_geometry", None),
                "epsilon",
                1e-9,
            )
            or 1e-9
        )
        out.append(TerrainRelativeZConstraint(epsilon=eps))
    return out


def compose_constraint_responses(
    responses: list[ExternalConstraintResponse],
    proposed_delta: float,
) -> ExternalConstraintResponse:
    """Most-restrictive admission along signed proposed_delta."""
    if not responses:
        return ExternalConstraintResponse(
            admitted_delta=float(proposed_delta),
            blocked_delta=0.0,
            opposing=False,
            constraint_kind="none",
        )
    prop = float(proposed_delta)
    if prop >= 0.0:
        # Raising: take min admitted (most clipped upward) — usually all full.
        best = min(responses, key=lambda r: float(r.admitted_delta))
    else:
        # Lowering: admitted is ≤ 0; most restrictive = least negative (closest to 0).
        best = max(responses, key=lambda r: float(r.admitted_delta))
    admitted = float(best.admitted_delta)
    if prop < 0.0:
        admitted = max(prop, min(0.0, admitted))
    else:
        admitted = min(prop, max(0.0, admitted))
    blocked = float(prop - admitted)
    return ExternalConstraintResponse(
        admitted_delta=admitted,
        blocked_delta=blocked,
        opposing=bool(abs(blocked) > 1e-15 and best.opposing),
        constraint_kind=str(best.constraint_kind),
        normal=best.normal,
        contact_point=best.contact_point,
        surface_height=best.surface_height,
        toi=best.toi,
        inward_normal_component=float(best.inward_normal_component),
        clearance_before=best.clearance_before,
        episode_hint=best.episode_hint,
    )


# ---------------------------------------------------------------------------
# Config / state
# ---------------------------------------------------------------------------


@dataclass
class EffectorBoundedActuatorEffortConfig:
    """Fresh default OFF. Missing snapshot → mechanism OFF."""

    enabled: bool = False
    max_work_per_tick: float = DEFAULT_MAX_WORK_PER_TICK
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "max_work_per_tick": float(self.max_work_per_tick),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "actuator_model": ACTUATOR_MODEL,
            "mechanical_work_source": MECHANICAL_WORK_SOURCE,
            "blocked_work_policy": BLOCKED_WORK_POLICY,
            "actuation_coordinate": NEW_DOF,
            "actuation_frame": NEW_DOF_FRAME,
            "effector_mass": False,
            "effector_momentum": False,
            "contact_area": False,
            "metabolism": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EffectorBoundedActuatorEffortConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown bounded actuator profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            max_work_per_tick=float(
                data.get("max_work_per_tick", DEFAULT_MAX_WORK_PER_TICK)
            ),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: EffectorBoundedActuatorEffortConfig) -> None:
    if float(cfg.max_work_per_tick) < 0.0:
        raise ValueError("max_work_per_tick must be >= 0")


def effector_bounded_actuator_effort_is_active(config: Any) -> bool:
    cfg = getattr(config, "effector_bounded_actuator_effort", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_effector_bounded_actuator_effort(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "effector_bounded_actuator_effort", None)
    if cur is None:
        config.effector_bounded_actuator_effort = EffectorBoundedActuatorEffortConfig(
            enabled=on
        )
    else:
        cur.enabled = on


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "EFFECTOR BOUNDED ACTUATOR EFFORT",
        "config_path": "effector_bounded_actuator_effort.enabled",
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "provenance": "acanthostega_effector_bounded_actuator_effort",
        "banner": BANNER,
        "actuator_model": ACTUATOR_MODEL,
        "cognition_exposed": False,
        "effector_mass": False,
        "metabolism": False,
    }


@dataclass
class EffectorBoundedActuatorEffortState:
    config: EffectorBoundedActuatorEffortConfig
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


def _zero_counters() -> dict[str, int]:
    return {
        "steps": 0,
        "requests": 0,
        "zero_commands": 0,
        "free_space": 0,
        "external_blocks": 0,
        "work_events": 0,
        "capacity_saturated": 0,
    }


def state_of(world: Any) -> EffectorBoundedActuatorEffortState | None:
    raw = getattr(world, "effector_bounded_actuator_effort_state", None)
    return raw if isinstance(raw, EffectorBoundedActuatorEffortState) else None


def ensure_effector_bounded_actuator_effort_for_runtime(
    world: Any, config: Any
) -> EffectorBoundedActuatorEffortState | None:
    if not effector_bounded_actuator_effort_is_active(config):
        if hasattr(world, "effector_bounded_actuator_effort_state"):
            world.effector_bounded_actuator_effort_state = None
        return None
    raw_cfg = getattr(config, "effector_bounded_actuator_effort", None)
    cfg = (
        raw_cfg
        if isinstance(raw_cfg, EffectorBoundedActuatorEffortConfig)
        else EffectorBoundedActuatorEffortConfig.from_dict(
            raw_cfg.to_dict() if raw_cfg is not None and hasattr(raw_cfg, "to_dict") else None
        )
    )
    validate_config(cfg)
    st = state_of(world)
    if st is None:
        st = EffectorBoundedActuatorEffortState(config=cfg, counters=_zero_counters())
        world.effector_bounded_actuator_effort_state = st
    else:
        st.config = cfg
    return st


def serialize_state(st: EffectorBoundedActuatorEffortState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "counters": dict(st.counters),
        "last_step": dict(st.last_step) if st.last_step else None,
        "history": list(st.history),
        "banner": BANNER,
        "researcher_only": True,
        "note": "capacity is config-only; work is per-tick receipt (no accumulative reservoir)",
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> EffectorBoundedActuatorEffortState | None:
    if not effector_bounded_actuator_effort_is_active(config):
        world.effector_bounded_actuator_effort_state = None
        return None
    if not data:
        return ensure_effector_bounded_actuator_effort_for_runtime(world, config)
    cfg = EffectorBoundedActuatorEffortConfig.from_dict(
        data.get("config") if isinstance(data.get("config"), dict) else None
    )
    validate_config(cfg)
    st = EffectorBoundedActuatorEffortState(
        config=cfg,
        counters={**_zero_counters(), **{a: int(b) for a, b in (data.get("counters") or {}).items()}},
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else None,
        history=[dict(r) for r in (data.get("history") or [])],
    )
    world.effector_bounded_actuator_effort_state = st
    return st


# ---------------------------------------------------------------------------
# Kinematic admissibility (internal limits ≠ external blocking)
# ---------------------------------------------------------------------------


def kinematic_admissible_delta(
    *,
    relative_z_before: float,
    requested_delta_z: float,
    max_relative_z: float = DEFAULT_MAX_RELATIVE_Z,
    max_delta_z_per_tick: float = DEFAULT_MAX_DELTA_Z_PER_TICK,
) -> dict[str, Any]:
    """Rate then reach clip. Does not apply state. Not external blocking."""
    req = float(requested_delta_z)
    before = float(relative_z_before)
    rate = float(max_delta_z_per_tick)
    rate_clipped = False
    delta = req
    if abs(delta) > rate + 1e-15:
        delta = math.copysign(rate, delta)
        rate_clipped = True
    tentative = before + delta
    m = float(max_relative_z)
    reach_clipped = False
    after = tentative
    if after > m:
        after = m
        reach_clipped = True
    elif after < -m:
        after = -m
        reach_clipped = True
    adm = float(after - before)
    return {
        "requested_delta_z": req,
        "kinematically_admissible_delta": adm,
        "rate_clipped": bool(rate_clipped),
        "reach_clipped": bool(reach_clipped),
        "relative_z_before": before,
        "relative_z_after_kinematic": float(after),
    }


def _characteristic_force(cfg: EffectorBoundedActuatorEffortConfig) -> float:
    """F_char = W_max / rate_step so a full-rate full-block spends capacity."""
    rate = float(DEFAULT_MAX_DELTA_Z_PER_TICK)
    if rate <= 1e-18:
        return 0.0
    return float(cfg.max_work_per_tick) / rate


def _account_work(
    *,
    cfg: EffectorBoundedActuatorEffortConfig,
    constraint: ExternalConstraintResponse,
    admissible_delta: float,
) -> dict[str, float | bool]:
    """Mechanical work only for external opposition of otherwise admissible motion."""
    inward = float(constraint.inward_normal_component)
    if not constraint.opposing or inward <= 1e-15:
        return {
            "actuator_capacity": float(cfg.max_work_per_tick),
            "characteristic_force": float(_characteristic_force(cfg)),
            "work_attempted": 0.0,
            "work_used": 0.0,
            "work_dissipated": 0.0,
            "capacity_saturated": False,
        }
    f_char = _characteristic_force(cfg)
    attempted = float(f_char) * float(inward)
    used = min(float(cfg.max_work_per_tick), attempted)
    saturated = attempted > float(cfg.max_work_per_tick) + 1e-15
    return {
        "actuator_capacity": float(cfg.max_work_per_tick),
        "characteristic_force": float(f_char),
        "work_attempted": float(attempted),
        "work_used": float(used),
        "work_dissipated": float(used),  # rigid terrain: dissipated at contact
        "capacity_saturated": bool(saturated),
        "admissible_delta_ref": float(admissible_delta),
    }


# ---------------------------------------------------------------------------
# Public actuation API
# ---------------------------------------------------------------------------


def request_actuated_relative_displacement(
    world: Any,
    *,
    config: Any,
    body: Any,
    body_id: str,
    effector_id: str,
    requested_delta_z: float,
    tick: int,
    runtime: Any | None = None,
    constraints: list[ExternalRelativeConstraint] | None = None,
) -> dict[str, Any]:
    """Bounded actuator step along relative_z.

    Free space: identical kinematic motion to relative-actuation channel.
    External block: clip relative_z, emit work against constraint (bounded).
    Reach/rate clipping never counts as external work.
    """
    st = ensure_effector_bounded_actuator_effort_for_runtime(world, config)
    if st is None:
        return {
            "receipt_kind": RECEIPT_KIND,
            "status": "INACTIVE",
            "tick": int(tick),
            "body_id": str(body_id),
            "effector_id": str(effector_id),
            "requested_relative_delta": float(requested_delta_z),
            "work_used": 0.0,
            "researcher_only": True,
        }
    if not manipulator_relative_world_actuation_is_active(config):
        return {
            "receipt_kind": RECEIPT_KIND,
            "status": "RELATIVE_CHANNEL_INACTIVE",
            "tick": int(tick),
            "body_id": str(body_id),
            "effector_id": str(effector_id),
            "requested_relative_delta": float(requested_delta_z),
            "work_used": 0.0,
            "researcher_only": True,
        }

    cfg = st.config
    st.counters["requests"] = int(st.counters.get("requests", 0)) + 1
    before = float(relative_z_of(world, body_id, effector_id, config=config))
    req = float(requested_delta_z)

    if abs(req) <= 1e-15:
        st.counters["zero_commands"] = int(st.counters.get("zero_commands", 0)) + 1
        rec = {
            "receipt_kind": RECEIPT_KIND,
            "event": EVENT_STEP,
            "status": "ZERO_COMMAND",
            "tick": int(tick),
            "body_id": str(body_id),
            "effector_id": str(effector_id),
            "requested_relative_delta": 0.0,
            "kinematically_admissible_delta": 0.0,
            "achieved_relative_delta": 0.0,
            "externally_blocked_delta": 0.0,
            "rate_clipped": False,
            "reach_clipped": False,
            "external_constraint": "none",
            "work_used": 0.0,
            "work_attempted": 0.0,
            "work_dissipated": 0.0,
            "actuator_capacity": float(cfg.max_work_per_tick),
            "mechanical_work_source": MECHANICAL_WORK_SOURCE,
            "blocked_work_policy": BLOCKED_WORK_POLICY,
            "relative_z_before": before,
            "relative_z_after": before,
            "effector_mass": False,
            "effector_momentum": False,
            "contact_area": False,
            "force_invented": False,
            "researcher_only": True,
            "cognition_exposed": False,
        }
        st.last_step = rec
        world.last_effector_actuator_effort = rec
        return rec

    mrwa_cfg = getattr(config, "manipulator_relative_world_actuation", None)
    max_z = float(getattr(mrwa_cfg, "max_relative_z", DEFAULT_MAX_RELATIVE_Z))
    max_rate = float(getattr(mrwa_cfg, "max_delta_z_per_tick", DEFAULT_MAX_DELTA_Z_PER_TICK))
    kin = kinematic_admissible_delta(
        relative_z_before=before,
        requested_delta_z=req,
        max_relative_z=max_z,
        max_delta_z_per_tick=max_rate,
    )
    adm = float(kin["kinematically_admissible_delta"])

    cons = constraints if constraints is not None else default_external_constraints(config)
    responses = [
        c.admit_relative_z(
            world=world,
            config=config,
            body=body,
            body_id=str(body_id),
            effector_id=str(effector_id),
            relative_z_before=before,
            proposed_delta=adm,
            runtime=runtime,
        )
        for c in cons
    ]
    merged = compose_constraint_responses(responses, adm)
    achieved = float(merged.admitted_delta)
    blocked = float(merged.blocked_delta)

    # Apply achieved via existing kinematic channel (rate already respected).
    kin_rec = request_relative_effector_displacement(
        world,
        config=config,
        body_id=str(body_id),
        effector_id=str(effector_id),
        requested_delta_z=float(achieved),
        tick=int(tick),
    )
    after = float(relative_z_of(world, body_id, effector_id, config=config))
    # Safety: if kinematic channel rounded, trust stored after.
    achieved_actual = float(after - before)

    work = _account_work(cfg=cfg, constraint=merged, admissible_delta=adm)
    if merged.opposing and float(work["work_used"]) > 1e-15:
        st.counters["external_blocks"] = int(st.counters.get("external_blocks", 0)) + 1
        st.counters["work_events"] = int(st.counters.get("work_events", 0)) + 1
        if work["capacity_saturated"]:
            st.counters["capacity_saturated"] = int(st.counters.get("capacity_saturated", 0)) + 1
    else:
        st.counters["free_space"] = int(st.counters.get("free_space", 0)) + 1

    st.counters["steps"] = int(st.counters.get("steps", 0)) + 1
    status = "EXTERNAL_BLOCK" if merged.opposing else "FREE_SPACE"
    if abs(achieved_actual) <= 1e-15 and abs(adm) > 1e-15 and merged.opposing:
        status = "FULLY_BLOCKED"
    elif merged.opposing and abs(achieved_actual) > 1e-15:
        status = "PARTIAL_BLOCK"

    rec = {
        "receipt_kind": RECEIPT_KIND,
        "event": EVENT_STEP,
        "status": status,
        "tick": int(tick),
        "body_id": str(body_id),
        "effector_id": str(effector_id),
        "requested_relative_delta": req,
        "kinematically_admissible_delta": adm,
        "achieved_relative_delta": float(achieved_actual),
        "externally_blocked_delta": float(blocked),
        "rate_clipped": bool(kin["rate_clipped"]),
        "reach_clipped": bool(kin["reach_clipped"]),
        "internal_limit_distinct_from_external": True,
        "external_constraint": str(merged.constraint_kind),
        "opposing": bool(merged.opposing),
        "contact_point": merged.contact_point,
        "surface_normal": list(merged.normal) if merged.normal else None,
        "inward_normal_component": float(merged.inward_normal_component),
        "surface_height": merged.surface_height,
        "toi": merged.toi,
        "clearance_before": merged.clearance_before,
        "episode_hint": merged.episode_hint,
        "held_object_id": merged.episode_hint,
        "actuator_capacity": float(work["actuator_capacity"]),
        "characteristic_force": float(work["characteristic_force"]),
        "work_attempted": float(work["work_attempted"]),
        "work_used": float(work["work_used"]),
        "work_dissipated": float(work["work_dissipated"]),
        "capacity_saturated": bool(work["capacity_saturated"]),
        "mechanical_work_source": MECHANICAL_WORK_SOURCE,
        "blocked_work_policy": BLOCKED_WORK_POLICY,
        "actuator_model": ACTUATOR_MODEL,
        "relative_z_before": before,
        "relative_z_after": after,
        "actuation_coordinate": NEW_DOF,
        "actuation_frame": NEW_DOF_FRAME,
        "effector_mass": False,
        "effector_momentum": False,
        "contact_area": False,
        "force_invented": False,
        "metabolism": False,
        "terrain_mutation": False,
        "material_failure": False,
        "separation_wmt": False,
        "kinematic_channel_receipt_status": kin_rec.get("status"),
        "researcher_only": True,
        "cognition_exposed": False,
    }
    st.last_step = rec
    st.history.append(dict(rec))
    lim = int(cfg.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    world.last_effector_actuator_effort = rec
    # Held transmission partition first so work_transmitted is stamped before SETMR.
    try:
        from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
            annotate_actuator_receipt_transmission,
            held_resource_object_terrain_mechanical_transmission_is_active,
        )

        if held_resource_object_terrain_mechanical_transmission_is_active(config):
            annotate_actuator_receipt_transmission(
                world, config=config, actuator_receipt=rec
            )
    except Exception:
        pass
    # Terrain material response: tip (terrain_surface) always; held-mediated
    # when HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION_V1 is ON.
    mat_rec = None
    try:
        from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
            consume_actuator_effort_for_terrain_material,
            surface_exertion_terrain_material_resistance_is_active,
        )

        if surface_exertion_terrain_material_resistance_is_active(config):
            mat_rec = consume_actuator_effort_for_terrain_material(
                world,
                config=config,
                actuator_receipt=rec,
                tick=int(tick),
            )
    except Exception:
        mat_rec = None
    # Integration provenance: mark held route into SAME SETMR path.
    try:
        from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
            held_mediated_surface_exertion_integration_is_active,
            record_setmr_route,
        )

        if held_mediated_surface_exertion_integration_is_active(config):
            record_setmr_route(
                world,
                config=config,
                actuator_receipt=rec,
                material_receipt=mat_rec if isinstance(mat_rec, dict) else None,
            )
    except Exception:
        pass
    return rec


def drive_actuated_relative_z_to(
    world: Any,
    *,
    config: Any,
    body: Any,
    body_id: str,
    effector_id: str,
    target_z: float,
    tick_start: int,
    max_steps: int = 32,
    runtime: Any | None = None,
) -> list[dict[str, Any]]:
    """Multi-tick actuated drive (rate/reach + external constraints)."""
    out: list[dict[str, Any]] = []
    t = int(tick_start)
    for _ in range(int(max_steps)):
        cur = relative_z_of(world, body_id, effector_id, config=config)
        if abs(cur - float(target_z)) <= 1e-12:
            break
        rec = request_actuated_relative_displacement(
            world,
            config=config,
            body=body,
            body_id=body_id,
            effector_id=effector_id,
            requested_delta_z=float(target_z) - float(cur),
            tick=t,
            runtime=runtime,
        )
        out.append(rec)
        t += 1
        if abs(float(rec.get("achieved_relative_delta") or 0.0)) <= 1e-15:
            if rec.get("status") in {"FULLY_BLOCKED", "EXTERNAL_BLOCK", "PARTIAL_BLOCK"}:
                # Persist inward demand against constraint — keep stepping if target deeper.
                if float(target_z) < float(cur) - 1e-15 and float(
                    rec.get("work_used") or 0.0
                ) >= 0.0:
                    # Allow continued blocked work ticks until max_steps.
                    continue
            break
    return out
