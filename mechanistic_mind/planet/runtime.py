"""Zero-organism planet runtime with bounded telemetry."""
from __future__ import annotations

from typing import Any

import numpy as np

from mechanistic_mind.planet.boundary import boundary_to_dict, mask_sha256
from mechanistic_mind.planet.config import PlanetConfig, default_planet_config
from mechanistic_mind.planet.dynamics import step_planet
from mechanistic_mind.planet.forcing import forcing_field, forcing_phase_fast
from mechanistic_mind.planet.state import PlanetState, initialize_planet


def snapshot_stats(state: PlanetState, cfg: PlanetConfig, seed: int) -> dict[str, Any]:
    F = forcing_field(cfg, max(0, state.tick - 1), *state.T.shape, seed=seed)
    return {
        "tick": state.tick,
        "T_mean": float(state.T.mean()),
        "T_std": float(state.T.std()),
        "T_min": float(state.T.min()),
        "T_max": float(state.T.max()),
        "F_mean": float(F.mean()),
        "F_max": float(F.max()),
        "speed_mean": float(np.hypot(state.vx, state.vy).mean()),
        "speed_max": float(np.hypot(state.vx, state.vy).max()),
        "M0_sum": float(state.M[0].sum()),
        "M1_sum": float(state.M[1].sum()) if state.M.shape[0] > 1 else 0.0,
        "M2_sum": float(state.M[2].sum()) if state.M.shape[0] > 2 else 0.0,
        "M_total": float(state.M.sum()),
        "u_abs_mean": float(np.abs(state.u).mean()),
        "u_abs_max": float(np.abs(state.u).max()),
        "matter_err": float(state.M.sum() - state.matter_initial),
        "energy_in_cum": state.energy_in_cum,
        "energy_diss_cum": state.energy_diss_cum,
        "clip_counts": dict(state.clip_counts),
        "forcing_phase_fast_observer": forcing_phase_fast(state.tick, cfg.F_fast_period),
        "external_material_boundary": boundary_to_dict(state.external_material_boundary),
        "external_material_boundary_mask_sha256": mask_sha256(
            state.external_material_boundary.contact_mask
        ),
    }


def run_planet(
    *,
    seed: int = 17,
    horizon: int = 800,
    config: PlanetConfig | None = None,
    snapshot_every: int = 20,
    impulse_at: int | None = None,
    impulse_amp: float = 1.0,
    impulse_y: int | None = None,
    impulse_x: int | None = None,
) -> dict[str, Any]:
    cfg = config or default_planet_config()
    state = initialize_planet(cfg, seed=seed)
    series: list[dict[str, Any]] = []
    # store sparse field probes: center and seam-adjacent columns
    probes_T = []
    h, w = state.T.shape
    cy, cx = h // 2, w // 2
    series.append(snapshot_stats(state, cfg, seed))
    for t in range(horizon):
        impulse = None
        if impulse_at is not None and t == impulse_at:
            impulse = np.zeros_like(state.u)
            iy = h // 2 if impulse_y is None else int(impulse_y) % h
            ix = w // 2 if impulse_x is None else int(impulse_x) % w
            impulse[iy, ix] = float(impulse_amp)
        step_planet(state, cfg, seed=seed, impulse=impulse)
        if (t + 1) % snapshot_every == 0 or t + 1 == horizon:
            series.append(snapshot_stats(state, cfg, seed))
            probes_T.append({"tick": state.tick, "center": float(state.T[cy, cx]), "seam": float(state.T[cy, 0])})
    return {
        "seed": seed,
        "horizon": horizon,
        "config": cfg.to_dict(),
        "series": series,
        "probes_T": probes_T,
        "final": {
            "T": state.T,
            "M": state.M,
            "vx": state.vx,
            "vy": state.vy,
            "u": state.u,
            "capacity": state.capacity,
            "conductivity": state.conductivity,
            "tick": state.tick,
            "matter_initial": state.matter_initial,
            "clip_counts": dict(state.clip_counts),
        },
        "state": state,
    }




def serialize_planet_state(state: PlanetState, cfg: PlanetConfig) -> dict[str, Any]:
    """Exact snapshot including resolved external material boundary (OPEN-5)."""
    return {
        "tick": int(state.tick),
        "T": state.T.tolist(),
        "M": state.M.tolist(),
        "vx": state.vx.tolist(),
        "vy": state.vy.tolist(),
        "u": state.u.tolist(),
        "u_prev": state.u_prev.tolist(),
        "capacity": state.capacity.tolist(),
        "conductivity": state.conductivity.tolist(),
        "matter_initial": float(state.matter_initial),
        "energy_in_cum": float(state.energy_in_cum),
        "energy_diss_cum": float(state.energy_diss_cum),
        "clip_counts": dict(state.clip_counts),
        "config": cfg.to_dict(),
        "external_material_boundary": boundary_to_dict(state.external_material_boundary),
        "external_material_boundary_mask_sha256": mask_sha256(
            state.external_material_boundary.contact_mask
        ),
        "R": None if getattr(state, "R", None) is None else np.asarray(state.R).tolist(),
        "R_A": None if getattr(state, "R_A", None) is None else np.asarray(state.R_A).tolist(),
        "R_B": None if getattr(state, "R_B", None) is None else np.asarray(state.R_B).tolist(),
        "FIELD_A": None if getattr(state, "FIELD_A", None) is None else np.asarray(state.FIELD_A).tolist(),
        "FIELD_B": None if getattr(state, "FIELD_B", None) is None else np.asarray(state.FIELD_B).tolist(),
    }


def restore_planet_state(payload: dict[str, Any]) -> tuple[PlanetState, PlanetConfig]:
    """Restore planet + boundary. Missing boundary fields => OFF."""
    from mechanistic_mind.planet.boundary import boundary_from_dict

    cfg = PlanetConfig.from_dict(payload.get("config", {}))
    n = int(np.asarray(payload["M"]).shape[0])
    b = boundary_from_dict(payload.get("external_material_boundary"), n_materials=n)
    st = PlanetState(
        tick=int(payload["tick"]),
        T=np.asarray(payload["T"], dtype=np.float64),
        M=np.asarray(payload["M"], dtype=np.float64),
        vx=np.asarray(payload["vx"], dtype=np.float64),
        vy=np.asarray(payload["vy"], dtype=np.float64),
        u=np.asarray(payload["u"], dtype=np.float64),
        u_prev=np.asarray(payload["u_prev"], dtype=np.float64),
        capacity=np.asarray(payload["capacity"], dtype=np.float64),
        conductivity=np.asarray(payload["conductivity"], dtype=np.float64),
        matter_initial=float(payload["matter_initial"]),
        energy_in_cum=float(payload.get("energy_in_cum", 0.0)),
        energy_diss_cum=float(payload.get("energy_diss_cum", 0.0)),
        clip_counts=dict(payload.get("clip_counts", {"T": 0, "M": 0, "v": 0, "u": 0})),
        external_material_boundary=b,
        R=(
            None if payload.get("R") is None
            else np.asarray(payload["R"], dtype=np.float64)
        ),
        R_A=(
            None if payload.get("R_A") is None
            else np.asarray(payload["R_A"], dtype=np.float64)
        ),
        R_B=(
            None if payload.get("R_B") is None
            else np.asarray(payload["R_B"], dtype=np.float64)
        ),
        FIELD_A=(
            None if payload.get("FIELD_A") is None
            else np.asarray(payload["FIELD_A"], dtype=np.float64)
        ),
        FIELD_B=(
            None if payload.get("FIELD_B") is None
            else np.asarray(payload["FIELD_B"], dtype=np.float64)
        ),
    )
    return st, cfg
