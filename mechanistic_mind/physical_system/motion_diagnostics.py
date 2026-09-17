"""Observer-side motion causal diagnostics for PhysicalSystemRuntime.

Does NOT alter physics. Reconstructs mechanical contributions from the
actual formulas in physical_body.dynamics.step_physical_body.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any

import numpy as np

from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.planet.state import PlanetState


def _na() -> str:
    return "NOT_AVAILABLE"


def sample_local_world(body: PhysicalBodyState, planet: PlanetState, cfg: PhysicalBodyConfig) -> dict[str, Any]:
    h, w = planet.T.shape
    cells = body.cells(w, h, cfg.footprint)
    ncell = max(1, len(cells))
    T_w = float(sum(planet.T[iy, ix] for iy, ix in cells) / ncell)
    vx_w = float(sum(float(planet.vx[iy, ix]) for iy, ix in cells) / ncell)
    vy_w = float(sum(float(planet.vy[iy, ix]) for iy, ix in cells) / ncell)
    u_w = float(sum(float(planet.u[iy, ix]) for iy, ix in cells) / ncell)
    return {
        "T_w": T_w,
        "vx_w": vx_w,
        "vy_w": vy_w,
        "u_w": u_w,
        "flow_speed": float(np.hypot(vx_w, vy_w)),
        "ncell": ncell,
    }


def mechanical_stage_decomposition(
    *,
    vx_before_mech: float,
    vy_before_mech: float,
    mech_before: float,
    local: dict[str, Any],
    cfg: PhysicalBodyConfig,
    motor_ux: float = 0.0,
    motor_uy: float = 0.0,
    endogenous_motor_enabled: bool = False,
) -> dict[str, Any]:
    """Replay mechanical formulas without mutating state.

    Matches dynamics.py mechanical block (linear terms + mech sign terms).
    """
    if not cfg.mechanical_enabled:
        return {
            "status": "MECHANICAL_DISABLED",
            "stages": [],
            "identifiable_sum": False,
        }
    vx_w = float(local["vx_w"])
    vy_w = float(local["vy_w"])
    u_w = float(local["u_w"])
    mech_after = 0.85 * mech_before + cfg.wave_coupling * u_w

    ax_flow = cfg.flow_coupling * vx_w
    ay_flow = cfg.flow_coupling * vy_w
    ax_drag = -cfg.drag * vx_before_mech
    ay_drag = -cfg.drag * vy_before_mech
    # sign terms exactly as in dynamics.py
    if abs(vx_w) + abs(vy_w) < 1e-9:
        sx, sy = 1.0, 0.0
    else:
        sx = float(np.sign(vx_w) or 1.0)
        sy = float(np.sign(vy_w))
    ax_mech = 0.15 * mech_after * sx
    ay_mech = 0.15 * mech_after * sy

    ax_endo = float(motor_ux) if endogenous_motor_enabled else 0.0
    ay_endo = float(motor_uy) if endogenous_motor_enabled else 0.0
    ax = ax_flow + ax_drag + ax_mech + ax_endo
    ay = ay_flow + ay_drag + ay_mech + ay_endo
    dvx = ax / cfg.mass
    dvy = ay / cfg.mass
    vx1 = float(np.clip(vx_before_mech + dvx, -cfg.v_max, cfg.v_max))
    vy1 = float(np.clip(vy_before_mech + dvy, -cfg.v_max, cfg.v_max))

    stages = [
        {"name": "velocity_entering_mechanical", "vx": vx_before_mech, "vy": vy_before_mech},
        {
            "name": "world_flow_acceleration_term",
            "ax": ax_flow, "ay": ay_flow,
            "note": "flow_coupling * local planet.vx/vy",
        },
        {
            "name": "drag_term",
            "ax": ax_drag, "ay": ay_drag,
            "note": "-drag * velocity_entering_mechanical",
        },
        {
            "name": "mech_wave_term",
            "ax": ax_mech, "ay": ay_mech,
            "mech_before": mech_before,
            "mech_after_update": mech_after,
            "note": "0.15 * updated_mech * sign(world_flow)",
        },
        {
            "name": "endogenous_motor_term",
            "ax": ax_endo, "ay": ay_endo,
            "enabled": bool(endogenous_motor_enabled),
            "note": "continuous motor_u from site Δc; not discrete MOVE",
        },
        {
            "name": "velocity_after_mechanical_pre_clip_delta",
            "dvx": dvx, "dvy": dvy,
        },
        {
            "name": "velocity_after_mechanical",
            "vx": vx1, "vy": vy1,
            "clip_applied": abs(vx_before_mech + dvx) > cfg.v_max or abs(vy_before_mech + dvy) > cfg.v_max,
        },
    ]
    return {
        "status": "AVAILABLE",
        "identifiable_sum": True,
        "additive_acceleration": {
            "ax_total": ax, "ay_total": ay,
            "ax_flow": ax_flow, "ay_flow": ay_flow,
            "ax_drag": ax_drag, "ay_drag": ay_drag,
            "ax_mech": ax_mech, "ay_mech": ay_mech,
            "ax_internal_c": 0.0,
            "ay_internal_c": 0.0,
            "ax_endogenous_motor": ax_endo,
            "ay_endogenous_motor": ay_endo,
            "internal_c_term_in_equation": False,
            "endogenous_motor_enabled": bool(endogenous_motor_enabled),
            "note": (
                "baseline: internal.c absent from ax/ay; "
                "EXPERIMENTAL endogenous motor adds motor_u when enabled"
            ),
        },
        "stages": stages,
        "predicted_vx_after": vx1,
        "predicted_vy_after": vy1,
    }


def build_motion_causal_receipt(
    *,
    tick: int,
    body_before_action: dict[str, Any],
    body_after_impulse: dict[str, Any],
    body_after: dict[str, Any],
    internal_before: dict[str, Any] | None,
    internal_after: dict[str, Any] | None,
    selected_action: str,
    action_source: str | None,
    impulse: tuple[float, float],
    local_world_after_planet: dict[str, Any],
    mech_decomp: dict[str, Any],
    observation_after: dict[str, float] | None = None,
) -> dict[str, Any]:
    dx = float(body_after["x"] - body_before_action["x"])
    dy = float(body_after["y"] - body_before_action["y"])
    # wrap-naive; Observer may also show wrap-aware
    moved = abs(dx) > 1e-12 or abs(dy) > 1e-12 or abs(body_after["vx"]) > 1e-12 or abs(body_after["vy"]) > 1e-12

    internal_transition = {"status": _na()}
    if internal_before is not None and internal_after is not None:
        c0 = np.asarray(internal_before.get("c_mean") or internal_before.get("c") or [], dtype=np.float64)
        c1 = np.asarray(internal_after.get("c_mean") or internal_after.get("c") or [], dtype=np.float64)
        if c0.size and c1.size and c0.shape == c1.shape:
            dc = c1 - c0
            internal_transition = {
                "status": "AVAILABLE",
                "c_mean_before": c0.tolist(),
                "c_mean_after": c1.tolist(),
                "delta_c_mean": dc.tolist(),
                "delta_c_l1": float(np.abs(dc).sum()),
                "delta_c_l2": float(np.linalg.norm(dc)),
            }

    # causal path labels actually present
    path = ["ACTION_IMPULSE", "WORLD_STEP", "BODY_MECHANICAL(flow+drag+mech)", "INTERNAL_MEDIUM(after motion)"]
    causes = []
    if abs(impulse[0]) > 1e-15 or abs(impulse[1]) > 1e-15:
        causes.append("ACTION_IMPULSE")
    add = (mech_decomp or {}).get("additive_acceleration") or {}
    if abs(add.get("ax_flow", 0)) + abs(add.get("ay_flow", 0)) > 1e-12:
        causes.append("WORLD_FLOW")
    if abs(add.get("ax_drag", 0)) + abs(add.get("ay_drag", 0)) > 1e-12:
        causes.append("DRAG_ON_EXISTING_VELOCITY")
    if abs(add.get("ax_mech", 0)) + abs(add.get("ay_mech", 0)) > 1e-12:
        causes.append("WAVE_MECH_TERM")
    if abs(add.get("ax_endogenous_motor", 0)) + abs(add.get("ay_endogenous_motor", 0)) > 1e-12:
        causes.append("ENDOGENOUS_MOTOR_COUPLING")
    # internal physical contribution to ax/ay
    internal_to_external = {
        "status": "NOT_DEMONSTRATED",
        "in_mechanical_equation": False,
        "ax_from_internal_c": 0.0,
        "ay_from_internal_c": 0.0,
        "note": "step_physical_body mechanical block does not read internal.c",
    }

    return {
        "schema": "mm.motion_causal_receipt.v1",
        "tick": int(tick),
        "before": {
            "position": {"x": body_before_action["x"], "y": body_before_action["y"]},
            "velocity": {"vx": body_before_action["vx"], "vy": body_before_action["vy"]},
            "body": deepcopy(body_before_action),
            "internal": deepcopy(internal_before) if internal_before else _na(),
        },
        "internal_transition": internal_transition,
        "action": {
            "selected_action": selected_action,
            "action_source": action_source or _na(),
            "emitted_impulse": [float(impulse[0]), float(impulse[1])],
            "velocity_after_impulse": {
                "vx": body_after_impulse["vx"],
                "vy": body_after_impulse["vy"],
            },
        },
        "environment": {
            "local_after_planet_step": deepcopy(local_world_after_planet),
        },
        "motion_update": {
            "velocity_before_action": {
                "vx": body_before_action["vx"],
                "vy": body_before_action["vy"],
            },
            "velocity_after_impulse_before_mech": {
                "vx": body_after_impulse["vx"],
                "vy": body_after_impulse["vy"],
            },
            "mechanical_decomposition": mech_decomp,
            "velocity_after": {"vx": body_after["vx"], "vy": body_after["vy"]},
            "position_before": {"x": body_before_action["x"], "y": body_before_action["y"]},
            "position_after": {"x": body_after["x"], "y": body_after["y"]},
            "delta_position_naive": {"dx": dx, "dy": dy, "mag": float(np.hypot(dx, dy))},
            "identifiable_causes_this_tick": causes,
            "execution_order": path,
        },
        "internal_to_external_spatial": internal_to_external,
        "after": {
            "body": deepcopy(body_after),
            "internal": deepcopy(internal_after) if internal_after else _na(),
            "observation": deepcopy(observation_after) if observation_after else _na(),
        },
        "moved": bool(moved),
        "why_did_it_move_summary": {
            "action": selected_action,
            "impulse": [float(impulse[0]), float(impulse[1])],
            "position_change": {"dx": dx, "dy": dy},
            "causes": causes or ["NONE_IDENTIFIED_OR_STATIONARY"],
            "INTERNAL_TO_EXTERNAL_TRANSFER": (
                "EXPERIMENTAL_ENDOGENOUS_MOTOR"
                if "ENDOGENOUS_MOTOR_COUPLING" in causes
                else "NOT_DEMONSTRATED_IN_BASELINE"
            ),
            "endogenous_motor_u": {
                "ux": body_after.get("motor_ux", _na()),
                "uy": body_after.get("motor_uy", _na()),
            },
        },
    }


def internal_summary(internal) -> dict[str, Any]:
    c = np.asarray(internal.c, dtype=np.float64)
    return {
        "c_mean": c.mean(axis=0).tolist() if c.ndim == 2 else c.tolist(),
        "c_l1": float(np.abs(c).sum()),
        "tick": int(internal.tick),
    }


class MotionTraceBuffer:
    def __init__(self, capacity: int = 256) -> None:
        self.capacity = capacity
        self.receipts: deque[dict[str, Any]] = deque(maxlen=capacity)

    def add(self, receipt: dict[str, Any]) -> None:
        self.receipts.append(receipt)

    def list(self) -> list[dict[str, Any]]:
        return list(self.receipts)
