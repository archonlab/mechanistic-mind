"""Agent-accessible observation for Current MM (PhysicalSystemRuntime).

WORLD TRUTH (full maps, PlanetDisplayState, observer diagnostics) must never
enter cognition. Fragments here are derived only from body-local physical
signals and embodied internal scalars owned by the same agent instance.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.planet.config import PlanetConfig
from mechanistic_mind.planet.state import PlanetState
from mechanistic_mind.internal_medium.state import InternalMediumState
from mechanistic_mind.physical_body.config import PhysicalBodyConfig

# Keys / tokens forbidden in agent-facing cognition payloads.
FORBIDDEN_TOKENS = (
    "PlanetDisplayState",
    "ground_truth",
    "world_truth",
    "hidden_role",
    "observer_only",
    "display_from_planet",
    "full_map",
    "external_material_boundary",
    "season_phase",
    "latitude_coordinate",
    "environmental_cycle_phase",
    "climate_phase",
    "resource_cycle_phase",
    "terrain_potential",
    "terrain_drag",
    "terrain_grad",
    "terrain_seed",
    "resource_geo_suit",
    "resource_suitability",
    "ambient_fx",
    "ambient_fy",
    "ambient_force",
    "ambient_seed",
    "temporal_panel",
    "phase_velocity_per_tick",
    "body_climate_timescale_ratio",
    "OBSTACLE",
    "MOUNTAIN",
    "TRAP",
    # PHYSICAL_PERCEPTION_01 — WORLD GT / pipeline intermediates never cognition-visible by name
    "illumination_phase",
    "surface_response",
    "surface_seed",
    "surface_checksum",
    "surface_meta",
    "world_x",
    "world_y",
    "absolute_direction",
    "terrain_traversability",
    "DAY",
    "NIGHT",
    "TIME_OF_DAY",
    # Visible physical bodies — identity / role never cognition-visible
    "OTHER_AGENT",
    "EXPERIMENTER",
    "experimenter",
    "agent_id",
    "entity_id",
    "entity_type",
    "optical_source_type",
    "visible_body",
    "body_is_agent",
    "TEACHER",
    "DEMONSTRATOR",
    "SOCIAL_SIGNAL",
)


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _norm_signed(x: float, scale: float) -> float:
    """Map signed quantity into [0, 1] via 0.5 + 0.5*tanh(x/scale)."""
    s = max(1e-9, float(scale))
    return _clip01(0.5 + 0.5 * float(np.tanh(float(x) / s)))


def audit_cognition_payload(payload: Any) -> list[str]:
    """Return forbidden token hits in a cognition-facing structure."""
    text = repr(payload)
    return [tok for tok in FORBIDDEN_TOKENS if tok in text]


def world_truth_summary(world: PlanetState) -> dict[str, Any]:
    """Observer-only WORLD TRUTH summary — never pass to cognition."""
    return {
        "kind": "WORLD_TRUTH",
        "tick": int(world.tick),
        "T_mean": float(np.mean(world.T)),
        "T_std": float(np.std(world.T)),
        "M_sum": [float(np.sum(world.M[i])) for i in range(world.M.shape[0])],
        "vx_mean": float(np.mean(world.vx)),
        "vy_mean": float(np.mean(world.vy)),
        "shape": {"T": list(world.T.shape), "M": list(world.M.shape)},
    }


def accessible_observation(
    *,
    world: PlanetState,
    body: PhysicalBodyState,
    internal: InternalMediumState,
    planet_config: PlanetConfig,
    body_config: PhysicalBodyConfig,
    include_signal_fields: bool = True,
    near_field_cfg: Any = None,
    foreign_bodies: Any = None,
) -> dict[str, float]:
    """Canonical physically accessible observation fragment (dict[str, float]).

    Signal keys appear only when world.FIELD_* exists AND include_signal_fields.
    Default PSR has no FIELD arrays, so observation keys stay unchanged.
    Near-field exo_* fragments appear only when near_field_cfg is enabled
    and perception_enabled (ablation: perception_enabled=False → no exo_*).
    """
    w = int(planet_config.width)
    h = int(planet_config.height)
    cells = body.cells(w, h, body_config.footprint)
    n = max(1, len(cells))
    t_loc = 0.0
    m_loc = np.zeros(3, dtype=np.float64)
    vx_loc = 0.0
    vy_loc = 0.0
    for iy, ix in cells:
        t_loc += float(world.T[iy, ix])
        m_loc += world.M[:, iy, ix]
        vx_loc += float(world.vx[iy, ix])
        vy_loc += float(world.vy[iy, ix])
    t_loc /= n
    m_loc /= n
    vx_loc /= n
    vy_loc /= n

    vmax = float(getattr(body_config, "v_max", 0.3) or 0.3)
    frag: dict[str, float] = {
        "body.T": _clip01(float(body.T)),
        "body.B0": _clip01(float(body.B[0]) / max(1e-9, float(body_config.B_max))),
        "body.B1": _clip01(float(body.B[1]) / max(1e-9, float(body_config.B_max))),
        "body.B2": _clip01(float(body.B[2]) / max(1e-9, float(body_config.B_max))),
        "body.mech": _clip01(float(body.mech)),
        "body.vx": _norm_signed(float(body.vx), vmax),
        "body.vy": _norm_signed(float(body.vy), vmax),
        "local.T": _clip01(t_loc),
        "local.M0": _clip01(float(m_loc[0])),
        "local.M1": _clip01(float(m_loc[1])),
        "local.M2": _clip01(float(m_loc[2])),
        "local.vx": _norm_signed(vx_loc, 1.0),
        "local.vy": _norm_signed(vy_loc, 1.0),
    }
    if include_signal_fields:
        for name, key in (("FIELD_A", "local.FIELD_A"), ("FIELD_B", "local.FIELD_B")):
            arr = getattr(world, name, None)
            if arr is None:
                continue
            s = 0.0
            for iy, ix in cells:
                s += float(arr[iy, ix])
            frag[key] = _clip01(s / n)
    # Embodied internal medium is owned by the same agent; expose channel means only.
    c = np.asarray(internal.c, dtype=np.float64)
    if c.size:
        means = c.reshape(c.shape[0], -1).mean(axis=1) if c.ndim >= 2 else c.reshape(-1)
        for i, val in enumerate(means.tolist()[:5]):
            frag[f"internal.c{i}"] = _clip01(float(val))
    # Directional near-field exteroception (PHYSICAL_PERCEPTION_01 + body optics).
    if near_field_cfg is not None:
        from mechanistic_mind.physical_system.near_field_exteroception import cognition_exo_fragments
        exo = cognition_exo_fragments(
            world=world, body=body, cfg=near_field_cfg, foreign_bodies=foreign_bodies
        )
        for k, v in exo.items():
            frag[str(k)] = _clip01(float(v))
    # Leak guard on own output
    hits = audit_cognition_payload(frag)
    if hits:
        raise RuntimeError(f"accessible_observation leaked forbidden tokens: {hits}")
    return frag


def observation_bundle(
    *,
    world: PlanetState,
    body: PhysicalBodyState,
    internal: InternalMediumState,
    planet_config: PlanetConfig,
    body_config: PhysicalBodyConfig,
    include_signal_fields: bool = True,
    near_field_cfg: Any = None,
    foreign_bodies: Any = None,
) -> dict[str, Any]:
    """Observer-facing pair: WORLD TRUTH + AGENT OBSERVATION (separated)."""
    bundle: dict[str, Any] = {
        "world_truth": world_truth_summary(world),
        "agent_observation": accessible_observation(
            world=world,
            body=body,
            internal=internal,
            planet_config=planet_config,
            body_config=body_config,
            include_signal_fields=include_signal_fields,
            near_field_cfg=near_field_cfg,
            foreign_bodies=foreign_bodies,
        ),
        "boundary": "cognition_receives_agent_observation_only",
    }
    if near_field_cfg is not None and getattr(near_field_cfg, "enabled", False):
        from mechanistic_mind.physical_system.near_field_exteroception import sample_near_field
        bundle["near_field_sensor_gt"] = sample_near_field(
            world=world, body=body, cfg=near_field_cfg, foreign_bodies=foreign_bodies
        )
    return bundle