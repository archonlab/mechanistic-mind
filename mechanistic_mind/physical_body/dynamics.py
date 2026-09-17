"""WORLD <-> PhysicalBody coupling. No psyche/N/receptors/actions."""
from __future__ import annotations
import numpy as np

from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.planet.state import PlanetState
from mechanistic_mind.planet.topology import wrap_coord


def step_physical_body(
    body: PhysicalBodyState,
    planet: PlanetState,
    cfg: PhysicalBodyConfig,
    *,
    endogenous_motor_enabled: bool = False,
    skip_material: bool = False,
    skip_mechanical: bool = False,
) -> PhysicalBodyState:
    h, w = planet.T.shape
    cells = body.cells(w, h, cfg.footprint)
    ncell = max(1, len(cells))

    # average local WORLD fields over footprint
    T_w = float(sum(planet.T[iy, ix] for iy, ix in cells) / ncell)
    M_w = np.zeros(3, dtype=np.float64)
    vx_w = 0.0
    vy_w = 0.0
    u_w = 0.0
    for iy, ix in cells:
        M_w += planet.M[:, iy, ix]
        vx_w += float(planet.vx[iy, ix])
        vy_w += float(planet.vy[iy, ix])
        u_w += float(planet.u[iy, ix])
    M_w /= ncell
    vx_w /= ncell
    vy_w /= ncell
    u_w /= ncell

    # --- thermal ---
    if cfg.thermal_enabled:
        flux = cfg.thermal_conductance * (T_w - body.T)
        dTb = flux / cfg.heat_capacity
        body.T = float(np.clip(body.T + dTb, cfg.T_min, cfg.T_max))
        if flux > 0:
            body.heat_from_world += float(flux)
        else:
            body.heat_to_world += float(-flux)
        share = cfg.thermal_backreact * flux / ncell
        for iy, ix in cells:
            planet.T[iy, ix] = float(np.clip(
                planet.T[iy, ix] - share / max(float(planet.capacity[iy, ix]), 1e-6),
                0.0, 1.0,
            ))

    # --- material surface <-> WORLD (shared across footprint cells) ---
    if cfg.material_enabled and not skip_material:
        for i, perm in enumerate(cfg.permeability):
            if i >= body.B.shape[0]:
                break
            flux_i = float(perm) * (float(M_w[i]) - float(body.B[i]))
            if flux_i > 0:
                # available from all footprint cells
                avail = float(sum(planet.M[i, iy, ix] for iy, ix in cells))
                flux_i = min(flux_i, avail)
            else:
                flux_i = -min(-flux_i, float(body.B[i]))
            body.B[i] = float(np.clip(body.B[i] + flux_i, 0.0, cfg.B_max))
            if cfg.material_backreact and abs(flux_i) > 0:
                # distribute WORLD change evenly across footprint
                per = flux_i / ncell
                for iy, ix in cells:
                    planet.M[i, iy, ix] = float(max(0.0, float(planet.M[i, iy, ix]) - per))
            if flux_i > 0:
                body.matter_in += flux_i
            else:
                body.matter_out += -flux_i

    # --- slow core <-> surface (not WORLD) ---
    if cfg.core_enabled:
        for i in range(3):
            df = cfg.core_exchange * (float(body.B[i]) - float(body.B_core[i]))
            # df > 0: surface richer -> move to core
            if df > 0:
                df = min(df, float(body.B[i]))
            else:
                df = -min(-df, float(body.B_core[i]))
            body.B[i] = float(np.clip(body.B[i] - df, 0.0, cfg.B_max))
            body.B_core[i] = float(np.clip(body.B_core[i] + df, 0.0, cfg.B_max))
            body.core_exchange_cum += abs(df)

    # --- surface reaction ---
    if cfg.reaction_enabled:
        rate = cfg.react_rate * float(np.clip(body.T, 0.0, 1.0))
        consumed = rate * min(float(body.B[0]), float(body.B[1]))
        body.B[0] -= consumed
        body.B[1] -= consumed
        body.B[2] = float(np.clip(body.B[2] + consumed, 0.0, cfg.B_max))
        body.T = float(np.clip(body.T + cfg.react_heat * consumed, cfg.T_min, cfg.T_max))
        body.react_consumed += consumed

    # --- mechanical ---
    if cfg.mechanical_enabled and not skip_mechanical:
        body.mech = 0.85 * body.mech + cfg.wave_coupling * u_w
        ax = cfg.flow_coupling * vx_w - cfg.drag * body.vx
        ay = cfg.flow_coupling * vy_w - cfg.drag * body.vy
        ax += 0.15 * body.mech * (1.0 if abs(vx_w) + abs(vy_w) < 1e-9 else np.sign(vx_w) or 1.0)
        ay += 0.15 * body.mech * (0.0 if abs(vx_w) + abs(vy_w) < 1e-9 else np.sign(vy_w))
        # Experimental endogenous motor (default OFF): continuous contribution, not discrete MOVE.
        ax_endo = float(body.motor_ux) if endogenous_motor_enabled else 0.0
        ay_endo = float(body.motor_uy) if endogenous_motor_enabled else 0.0
        ax += ax_endo
        ay += ay_endo
        body.vx = float(np.clip(body.vx + ax / cfg.mass, -cfg.v_max, cfg.v_max))
        body.vy = float(np.clip(body.vy + ay / cfg.mass, -cfg.v_max, cfg.v_max))
        if cfg.displacement_enabled:
            body.x = float(wrap_coord(body.x + body.vx, w))
            body.y = float(wrap_coord(body.y + body.vy, h))

    body.tick += 1
    return body
