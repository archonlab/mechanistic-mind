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
        "terrain_potential": (
            None if getattr(state, "terrain_potential", None) is None
            else np.asarray(state.terrain_potential).tolist()
        ),
        "terrain_drag": (
            None if getattr(state, "terrain_drag", None) is None
            else np.asarray(state.terrain_drag).tolist()
        ),
        "terrain_grad_y": (
            None if getattr(state, "terrain_grad_y", None) is None
            else np.asarray(state.terrain_grad_y).tolist()
        ),
        "terrain_grad_x": (
            None if getattr(state, "terrain_grad_x", None) is None
            else np.asarray(state.terrain_grad_x).tolist()
        ),
        "terrain_meta": (
            None if getattr(state, "terrain_meta", None) is None
            else dict(state.terrain_meta)
        ),
        "resource_geo_suit_A": (
            None if getattr(state, "resource_geo_suit_A", None) is None
            else np.asarray(state.resource_geo_suit_A).tolist()
        ),
        "resource_geo_suit_B": (
            None if getattr(state, "resource_geo_suit_B", None) is None
            else np.asarray(state.resource_geo_suit_B).tolist()
        ),
        "ambient_fx": (
            None if getattr(state, "ambient_fx", None) is None
            else np.asarray(state.ambient_fx).tolist()
        ),
        "ambient_fy": (
            None if getattr(state, "ambient_fy", None) is None
            else np.asarray(state.ambient_fy).tolist()
        ),
        "ambient_meta": (
            None if getattr(state, "ambient_meta", None) is None
            else dict(state.ambient_meta)
        ),
        "surface_response": (
            None if getattr(state, "surface_response", None) is None
            else np.asarray(state.surface_response).tolist()
        ),
        "surface_meta": (
            None if getattr(state, "surface_meta", None) is None
            else dict(state.surface_meta)
        ),
        "illumination_intensity": getattr(state, "illumination_intensity", None),
        "illumination_meta": (
            None if getattr(state, "illumination_meta", None) is None
            else dict(state.illumination_meta)
        ),
        "experiment_seed": (
            int((state.terrain_meta or {}).get("experiment_seed"))
            if getattr(state, "terrain_meta", None)
            and (state.terrain_meta or {}).get("experiment_seed") is not None
            else None
        ),
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
        terrain_potential=(
            None if payload.get("terrain_potential") is None
            else np.asarray(payload["terrain_potential"], dtype=np.float64)
        ),
        terrain_drag=(
            None if payload.get("terrain_drag") is None
            else np.asarray(payload["terrain_drag"], dtype=np.float64)
        ),
        terrain_grad_y=(
            None if payload.get("terrain_grad_y") is None
            else np.asarray(payload["terrain_grad_y"], dtype=np.float64)
        ),
        terrain_grad_x=(
            None if payload.get("terrain_grad_x") is None
            else np.asarray(payload["terrain_grad_x"], dtype=np.float64)
        ),
        terrain_meta=(
            None if payload.get("terrain_meta") is None
            else dict(payload["terrain_meta"])
        ),
        resource_geo_suit_A=(
            None if payload.get("resource_geo_suit_A") is None
            else np.asarray(payload["resource_geo_suit_A"], dtype=np.float64)
        ),
        resource_geo_suit_B=(
            None if payload.get("resource_geo_suit_B") is None
            else np.asarray(payload["resource_geo_suit_B"], dtype=np.float64)
        ),
        ambient_fx=(
            None if payload.get("ambient_fx") is None
            else np.asarray(payload["ambient_fx"], dtype=np.float64)
        ),
        ambient_fy=(
            None if payload.get("ambient_fy") is None
            else np.asarray(payload["ambient_fy"], dtype=np.float64)
        ),
        ambient_meta=(
            None if payload.get("ambient_meta") is None
            else dict(payload["ambient_meta"])
        ),
        surface_response=(
            None if payload.get("surface_response") is None
            else np.asarray(payload["surface_response"], dtype=np.float64)
        ),
        surface_meta=(
            None if payload.get("surface_meta") is None
            else dict(payload["surface_meta"])
        ),
        illumination_intensity=(
            None if payload.get("illumination_intensity") is None
            else float(payload["illumination_intensity"])
        ),
        illumination_meta=(
            None if payload.get("illumination_meta") is None
            else dict(payload["illumination_meta"])
        ),
    )
    # Legacy snapshots without serialized grids but with terrain config enabled:
    # regenerate deterministically from experiment_seed + namespaced terrain_seed.
    te = getattr(cfg, "terrain", None)
    if (
        te is not None
        and bool(getattr(te, "enabled", False))
        and st.terrain_potential is None
    ):
        from mechanistic_mind.planet.terrain import install_terrain_on_planet

        seed = int(
            (payload.get("terrain_meta") or {}).get("experiment_seed")
            or payload.get("experiment_seed")
            or payload.get("seed")
            or 17
        )
        install_terrain_on_planet(st, experiment_seed=seed, config=te)
    elif st.terrain_meta is None and st.terrain_potential is not None:
        from mechanistic_mind.planet.terrain import build_terrain_metadata

        te2 = te or getattr(cfg, "terrain", None)
        if te2 is not None:
            st.terrain_meta = build_terrain_metadata(
                experiment_seed=int(payload.get("experiment_seed") or payload.get("seed") or 17),
                config=te2,
                potential=st.terrain_potential,
                drag=st.terrain_drag,
                height=int(st.T.shape[0]),
                width=int(st.T.shape[1]),
            )
            st.terrain_meta["enabled"] = True
    # Legacy snapshots without ambient grids but with ambient config enabled.
    ae = getattr(cfg, "ambient", None)
    if (
        ae is not None
        and bool(getattr(ae, "enabled", False))
        and st.ambient_fx is None
    ):
        from mechanistic_mind.planet.ambient import install_ambient_on_planet

        seed = int(
            (payload.get("ambient_meta") or {}).get("experiment_seed")
            or payload.get("experiment_seed")
            or payload.get("seed")
            or 17
        )
        install_ambient_on_planet(st, experiment_seed=seed, config=ae)
    return st, cfg
