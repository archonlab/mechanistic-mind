"""Acanthostega VW6 · Minimal vision 3D geometric interface.

Mechanism: minimal_vision_3d_geometric_interface
Schema: VW6_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE_V1
Authority: AUTHORITATIVE_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE

Physical XYZ + VW1 occupancy line-of-sight for near-field vision.
Does not invent cave/above/below semantics. Does not require a renderer.
Does not implement VW7 camera. Does not unlock VW4 reintegration trigger.

Endpoint convention:
  Open segment (t_eps, 1 - t_eps) is tested for occupancy intersection.
  Origin cell and destination cell are excluded from occlusion so observer
  self-geometry and target endpoint occupancy do not false-pre-occlude.
Nearest blocker: minimal t along the ray; ties by (cell_x, cell_y, z_min).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "VW6_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE_V1"
CAPABILITY = "minimal_volumetric_3d_visual_geometry"
PROFILE = "MINIMAL_VISION_3D_GEOMETRIC_INTERFACE_V1"
AUTHORITY = "AUTHORITATIVE_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE"
MECHANISM_ID = "minimal_vision_3d_geometric_interface"
WORLD_ATTR = "minimal_vision_3d_geometric_interface_state"
HISTORY_LIMIT = 32
T_EPS = 1e-9
TOLERANCE = 1e-9
# No organism pitch DOF: vertical acceptance is full (±90°) unless configured.
DEFAULT_VERTICAL_HALF_ANGLE_DEG = 90.0
TARGET_GEOMETRY = "CELL_CENTRE_XY_PLUS_AUTHORITATIVE_SURFACE_OR_ENTITY_Z"

AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "occupancy_owner": "volumetric_world_material_occupancy",
    "vision_consumer": "near_field_exteroception",
    "target_geometry_approximation": TARGET_GEOMETRY,
    "semantic_cave": False,
    "semantic_above_below": False,
    "renderer_required": False,
    "agent_accessible": False,
    "researcher_only_geometry_receipt": True,
}


class MinimalVision3DValidationError(ValueError):
    """Raised when VW6 config is invalid."""


@dataclass
class MinimalVision3DGeometricInterfaceConfig:
    enabled: bool = False
    profile: str = PROFILE
    schema: str = SCHEMA
    vertical_half_angle_deg: float = DEFAULT_VERTICAL_HALF_ANGLE_DEG
    endpoint_eps: float = T_EPS

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "profile": str(self.profile),
            "schema": str(self.schema),
            "vertical_half_angle_deg": float(self.vertical_half_angle_deg),
            "endpoint_eps": float(self.endpoint_eps),
            **AUTHORITY_FLAGS,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MinimalVision3DGeometricInterfaceConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        profile = str(data.get("profile") or PROFILE)
        schema = str(data.get("schema") or SCHEMA)
        if profile != PROFILE:
            raise MinimalVision3DValidationError(f"unsupported VW6 profile: {profile!r}")
        if schema != SCHEMA:
            raise MinimalVision3DValidationError(f"unsupported VW6 schema: {schema!r}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            profile=profile,
            schema=schema,
            vertical_half_angle_deg=float(
                data.get("vertical_half_angle_deg", DEFAULT_VERTICAL_HALF_ANGLE_DEG)
            ),
            endpoint_eps=float(data.get("endpoint_eps", T_EPS)),
        )


def minimal_vision_3d_geometric_interface_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "minimal_vision_3d_geometric_interface", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        volumetric_world_material_occupancy_is_active,
    )

    return bool(volumetric_world_material_occupancy_is_active(config))


def set_minimal_vision_3d_geometric_interface(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "minimal_vision_3d_geometric_interface", None)
    if cur is None:
        config.minimal_vision_3d_geometric_interface = MinimalVision3DGeometricInterfaceConfig(
            enabled=on
        )
    else:
        cur.enabled = on
    if on:
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            set_volumetric_world_material_occupancy,
        )
        from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
            set_volumetric_world_material_reintegration,
        )

        set_volumetric_world_material_occupancy(config, True)
        # VW4 researcher transaction available for vision feedback tests;
        # physical reintegration trigger remains intentionally blocked.
        set_volumetric_world_material_reintegration(config, True)


@dataclass
class MinimalVision3DGeometricInterfaceState:
    config: MinimalVision3DGeometricInterfaceConfig
    last_receipt: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


def state_of(world: Any) -> MinimalVision3DGeometricInterfaceState | None:
    raw = getattr(world, WORLD_ATTR, None)
    return raw if isinstance(raw, MinimalVision3DGeometricInterfaceState) else None


def ensure_state(world: Any, config: Any) -> MinimalVision3DGeometricInterfaceState | None:
    if not minimal_vision_3d_geometric_interface_is_active(config):
        if getattr(world, WORLD_ATTR, None) is not None:
            setattr(world, WORLD_ATTR, None)
        return None
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        ensure_state as ensure_vw1,
    )

    ensure_vw1(world, config)
    setattr(world, "_physical_system_config", config)
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "minimal_vision_3d_geometric_interface", None)
    cfg = (
        raw
        if isinstance(raw, MinimalVision3DGeometricInterfaceConfig)
        else MinimalVision3DGeometricInterfaceConfig.from_dict(
            raw if isinstance(raw, dict) else None
        )
    )
    cfg.enabled = True
    st = MinimalVision3DGeometricInterfaceState(config=cfg)
    setattr(world, WORLD_ATTR, st)
    return st


# ---------------------------------------------------------------------------
# Eye / target / relative geometry
# ---------------------------------------------------------------------------


def sensor_eye_xyz(body: Any, config: Any | None = None) -> tuple[float, float, float]:
    """Canonical visual origin: body XY + body centre_z (existing anatomy)."""
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of, flat_ground_gravity_is_active

    x = float(getattr(body, "x", 0.0) or 0.0)
    y = float(getattr(body, "y", 0.0) or 0.0)
    if config is not None and flat_ground_gravity_is_active(config):
        z = float(centre_z_of(body, kind="body", config=config))
    else:
        z = float(getattr(body, "z", 0.0) or 0.0)
    return float(x), float(y), float(z)


def cell_target_z(world: Any, cell_x: int, cell_y: int, *, config: Any = None) -> float:
    """Authoritative target Z for a terrain/optical cell (surface approximation)."""
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        compatibility_surface_elevation,
        volumetric_world_material_occupancy_is_active,
    )

    if config is not None and volumetric_world_material_occupancy_is_active(config):
        h = compatibility_surface_elevation(world, float(cell_x) + 0.5, float(cell_y) + 0.5)
        if h is not None and math.isfinite(float(h)):
            return float(h)
    try:
        from mechanistic_mind.physical_system.surface_elevation_support import surface_support_height

        return float(
            surface_support_height(world, float(cell_x) + 0.5, float(cell_y) + 0.5, config=config)
        )
    except Exception:
        return 0.0


def relative_xyz(
    ox: float,
    oy: float,
    oz: float,
    tx: float,
    ty: float,
    tz: float,
    *,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Wrapped XY deltas + absolute Z delta. Z does not wrap."""
    from mechanistic_mind.planet.topology import toroidal_delta

    dx = float(toroidal_delta(float(ox), float(tx), int(width)))
    dy = float(toroidal_delta(float(oy), float(ty), int(height)))
    dz = float(tz) - float(oz)
    dist_xy = float(math.hypot(dx, dy))
    dist_3d = float(math.sqrt(dx * dx + dy * dy + dz * dz))
    elev = float(math.atan2(dz, max(dist_xy, 1e-15)))
    return {
        "dx": dx,
        "dy": dy,
        "dz": dz,
        "distance_xy": dist_xy,
        "distance_3d": dist_3d,
        "elevation_rad": elev,
        "elevation_deg": float(math.degrees(elev)),
        "xy_wrap": True,
        "z_wrap": False,
    }


def elevation_accepted(elevation_rad: float, *, vertical_half_angle_deg: float) -> bool:
    half = math.radians(max(0.0, float(vertical_half_angle_deg)))
    return abs(float(elevation_rad)) <= half + 1e-15


# ---------------------------------------------------------------------------
# Sparse XY column traversal + occupancy LOS
# ---------------------------------------------------------------------------


def traverse_xy_columns(
    ox: float,
    oy: float,
    dx: float,
    dy: float,
    *,
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    """Deterministic Amanatyan-style grid traversal on the XY projection.

    Returns cells crossed by the open segment from (ox,oy) toward (ox+dx,oy+dy)
    with entry/exit parameters t_enter, t_exit in [0,1] along the XY/3D shared
    parameter (same t used for Z interpolation).
    Boundary convention: cell floor; crossing at exact integer prefers the
    next cell in the travel direction. Endpoints included; caller filters t.
    """
    from mechanistic_mind.planet.topology import wrap_coord

    w, h = int(width), int(height)
    if abs(dx) < TOLERANCE and abs(dy) < TOLERANCE:
        cx = int(wrap_coord(math.floor(float(ox)), w))
        cy = int(wrap_coord(math.floor(float(oy)), h))
        return [{"cell_x": cx, "cell_y": cy, "t_enter": 0.0, "t_exit": 1.0}]

    x0, y0 = float(ox), float(oy)
    x1, y1 = x0 + float(dx), y0 + float(dy)
    # Work in unwrapped continuous space for traversal.
    ix = int(math.floor(x0))
    iy = int(math.floor(y0))
    end_ix = int(math.floor(x1 - (1e-15 if abs(dx) > TOLERANCE else 0.0)))
    end_iy = int(math.floor(y1 - (1e-15 if abs(dy) > TOLERANCE else 0.0)))
    step_x = 1 if dx > 0 else (-1 if dx < 0 else 0)
    step_y = 1 if dy > 0 else (-1 if dy < 0 else 0)
    t_max_x = float("inf")
    t_max_y = float("inf")
    t_delta_x = float("inf")
    t_delta_y = float("inf")
    if step_x != 0:
        next_bx = float(ix + (1 if step_x > 0 else 0))
        t_max_x = (next_bx - x0) / dx
        t_delta_x = abs(1.0 / dx)
    if step_y != 0:
        next_by = float(iy + (1 if step_y > 0 else 0))
        t_max_y = (next_by - y0) / dy
        t_delta_y = abs(1.0 / dy)

    out: list[dict[str, Any]] = []
    t = 0.0
    guard = 0
    max_steps = abs(end_ix - ix) + abs(end_iy - iy) + 4
    while guard <= max_steps:
        guard += 1
        cx = int(wrap_coord(ix, w))
        cy = int(wrap_coord(iy, h))
        t_next = min(t_max_x, t_max_y, 1.0)
        out.append(
            {
                "cell_x": cx,
                "cell_y": cy,
                "t_enter": float(t),
                "t_exit": float(t_next),
                "unwrapped_ix": int(ix),
                "unwrapped_iy": int(iy),
            }
        )
        if t_next >= 1.0 - TOLERANCE:
            break
        # Advance — prefer X on exact ties for determinism.
        if t_max_x <= t_max_y + TOLERANCE:
            ix += step_x
            t = t_max_x
            t_max_x += t_delta_x
        else:
            iy += step_y
            t = t_max_y
            t_max_y += t_delta_y
        if guard > max_steps:
            break
    return out


def _interval_intersects_z_range(z_a: float, z_b: float, z_min: float, z_max: float) -> bool:
    """True if open/closed ray Z span overlaps occupied (z_min, z_max]."""
    lo = min(float(z_a), float(z_b))
    hi = max(float(z_a), float(z_b))
    # Occupied (z_min, z_max]; ray span [lo, hi] with open endpoints handled by caller t.
    return hi > float(z_min) + TOLERANCE and lo < float(z_max) + TOLERANCE


def occupancy_line_of_sight(
    world: Any,
    ox: float,
    oy: float,
    oz: float,
    tx: float,
    ty: float,
    tz: float,
    *,
    config: Any = None,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    """Query occupancy LOS along eye→target. Researcher receipt; not cognition."""
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        compatibility_surface_elevation,
        occupied_intervals_at,
    )
    from mechanistic_mind.planet.topology import wrap_coord

    grid = getattr(world, "T", None)
    if width is None or height is None:
        if grid is None:
            raise MinimalVision3DValidationError("world.T required for LOS dims")
        height = int(grid.shape[0])
        width = int(grid.shape[1])
    w, h = int(width), int(height)
    rel = relative_xyz(ox, oy, oz, tx, ty, tz, width=w, height=h)
    dx, dy, dz = rel["dx"], rel["dy"], rel["dz"]
    dist = float(rel["distance_3d"])
    eps = float(
        getattr(
            getattr(config, "minimal_vision_3d_geometric_interface", None),
            "endpoint_eps",
            T_EPS,
        )
        or T_EPS
    )

    columns = traverse_xy_columns(ox, oy, dx, dy, width=w, height=h)
    blockers: list[dict[str, Any]] = []
    n_cols = len(columns)
    for col_i, col in enumerate(columns):
        # Endpoint cells: observer origin and target cell do not self-occlude.
        if n_cols >= 1 and col_i == 0:
            continue
        if n_cols >= 2 and col_i == n_cols - 1:
            continue
        t0 = float(col["t_enter"])
        t1 = float(col["t_exit"])
        # Open-segment filter against endpoints
        ta = max(t0, eps)
        tb = min(t1, 1.0 - eps)
        if tb <= ta + TOLERANCE:
            continue
        z_a = float(oz) + ta * dz
        z_b = float(oz) + tb * dz
        cx, cy = int(col["cell_x"]), int(col["cell_y"])
        intervals = occupied_intervals_at(world, cx + 0.5, cy + 0.5)
        for it in intervals:
            if _interval_intersects_z_range(z_a, z_b, float(it.z_min), float(it.z_max)):
                # Approximate hit t: clamp ray Z into interval then invert.
                if abs(dz) > TOLERANCE:
                    # First t in [ta,tb] where ray Z enters occupied set.
                    # Occupied iff z_min < z <= z_max.
                    candidates = []
                    for z_bound in (float(it.z_min) + 1e-12, float(it.z_max)):
                        t_hit = (z_bound - float(oz)) / dz
                        if ta - TOLERANCE <= t_hit <= tb + TOLERANCE:
                            zz = float(oz) + t_hit * dz
                            if float(it.z_min) + TOLERANCE < zz <= float(it.z_max) + TOLERANCE:
                                candidates.append(t_hit)
                    # Also sample mid if span fully inside
                    t_mid = 0.5 * (ta + tb)
                    zz_mid = float(oz) + t_mid * dz
                    if float(it.z_min) + TOLERANCE < zz_mid <= float(it.z_max) + TOLERANCE:
                        candidates.append(t_mid)
                    if not candidates:
                        continue
                    t_hit = min(candidates)
                else:
                    t_hit = ta
                    zz_mid = float(oz)
                    if not (float(it.z_min) + TOLERANCE < zz_mid <= float(it.z_max) + TOLERANCE):
                        continue
                blockers.append(
                    {
                        "t": float(t_hit),
                        "cell_x": cx,
                        "cell_y": cy,
                        "z_hit": float(oz) + float(t_hit) * dz,
                        "interval": it.as_dict(),
                        "material": [
                            {"component_id": cid, "quantity_per_area": float(amt)}
                            for cid, amt in (it.composition or ())
                        ],
                    }
                )

    blockers.sort(
        key=lambda b: (
            float(b["t"]),
            int(b["cell_x"]),
            int(b["cell_y"]),
            float(b["interval"]["z_min"]),
        )
    )
    clear = len(blockers) == 0
    nearest = blockers[0] if blockers else None

    # Legacy heightfield contradiction: max surface along unwrap vs ray z
    legacy_would_block = False
    legacy_samples: list[dict[str, Any]] = []
    for col in columns:
        t_mid = 0.5 * (float(col["t_enter"]) + float(col["t_exit"]))
        if t_mid <= eps or t_mid >= 1.0 - eps:
            continue
        cx, cy = int(col["cell_x"]), int(col["cell_y"])
        surf = compatibility_surface_elevation(world, cx + 0.5, cy + 0.5)
        ray_z = float(oz) + t_mid * dz
        if surf is not None and math.isfinite(float(surf)) and ray_z < float(surf) - TOLERANCE:
            # Ray under max surface → heightfield "through terrain"
            legacy_would_block = True
            legacy_samples.append(
                {"cell_x": cx, "cell_y": cy, "ray_z": ray_z, "max_surface": float(surf)}
            )

    receipt = {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "eye": [float(ox), float(oy), float(oz)],
        "target": [
            float(wrap_coord(float(ox) + dx, w)),
            float(wrap_coord(float(oy) + dy, h)),
            float(tz),
        ],
        "relative": rel,
        "visible": bool(clear),
        "occluded": (not clear),
        "blocker": nearest,
        "blocker_count": len(blockers),
        "columns_traversed": len(columns),
        "endpoint_eps": float(eps),
        "legacy_max_surface_would_block": bool(legacy_would_block),
        "legacy_samples": legacy_samples[:8],
        "selection_rule": "NEAREST_T_THEN_CELL_XY_THEN_ZMIN",
        "researcher_only": True,
        "cognition_exposed": False,
    }
    st = state_of(world)
    if st is not None:
        st.last_receipt = dict(receipt)
        st.counters["los_queries"] = int(st.counters.get("los_queries", 0)) + 1
        if clear:
            st.counters["los_clear"] = int(st.counters.get("los_clear", 0)) + 1
        else:
            st.counters["los_occluded"] = int(st.counters.get("los_occluded", 0)) + 1
    return receipt


def annotate_near_field_row_with_3d(
    world: Any,
    row: dict[str, Any],
    *,
    eye: tuple[float, float, float],
    config: Any,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Upgrade one neighbor row: 3D distance + occupancy LOS. Mutates row."""
    cell = row.get("cell") or [0, 0]
    cx, cy = int(cell[0]), int(cell[1])
    tx = float(cx) + 0.5
    ty = float(cy) + 0.5
    tz = cell_target_z(world, cx, cy, config=config)
    ox, oy, oz = eye
    rel = relative_xyz(ox, oy, oz, tx, ty, tz, width=width, height=height)
    cfg = getattr(config, "minimal_vision_3d_geometric_interface", None)
    vhalf = float(getattr(cfg, "vertical_half_angle_deg", DEFAULT_VERTICAL_HALF_ANGLE_DEG) or 90.0)
    elev_ok = elevation_accepted(rel["elevation_rad"], vertical_half_angle_deg=vhalf)

    # Replace geometric distance input for attenuation / sector sorting.
    row["dx"] = rel["dx"]
    row["dy"] = rel["dy"]
    row["dz"] = rel["dz"]
    row["distance"] = float(rel["distance_3d"])
    row["distance_xy"] = float(rel["distance_xy"])
    row["elevation_rad"] = float(rel["elevation_rad"])
    row["elevation_deg"] = float(rel["elevation_deg"])
    row["eye_xyz"] = [ox, oy, oz]
    row["target_xyz"] = [tx, ty, tz]
    row["vw6_geometry"] = True
    row["vertical_acceptance"] = bool(elev_ok)

    los = occupancy_line_of_sight(
        world, ox, oy, oz, tx, ty, tz, config=config, width=width, height=height
    )
    row["occupancy_los"] = {
        "visible": los["visible"],
        "occluded": los["occluded"],
        "blocker": los.get("blocker"),
        "legacy_max_surface_would_block": los.get("legacy_max_surface_would_block"),
    }
    if not elev_ok:
        row["final_contribution"] = 0.0
        row["detectable"] = False
        row["visibility"] = "OUTSIDE_VERTICAL_ACCEPTANCE"
        row["visible_contribution"] = 0.0
    elif los["occluded"]:
        row["final_contribution"] = 0.0
        row["detectable"] = False
        row["visibility"] = "OCCLUDED_BY_OCCUPANCY"
        row["visible_contribution"] = 0.0
        row["occluded_by_occupancy"] = los.get("blocker")
    return row


def apply_vw6_to_near_field_sample(
    world: Any,
    sample: dict[str, Any],
    *,
    body: Any,
    config: Any,
) -> dict[str, Any]:
    """Upgrade neighbor rows with XYZ + occupancy LOS before spatial assemble."""
    if not minimal_vision_3d_geometric_interface_is_active(config):
        return sample
    ensure_state(world, config)
    from mechanistic_mind.physical_system.near_field_exteroception import (
        _hash_noise,
        distance_attenuation,
    )

    eye = sensor_eye_xyz(body, config)
    w = int(world.T.shape[1])
    h = int(world.T.shape[0])
    nfe = getattr(config, "near_field_exteroception", None)
    dist_k = float(getattr(nfe, "distance_k", 0.85) or 0.85)
    gain = float(getattr(nfe, "gain", 1.0) or 1.0)
    sat_cap = float(getattr(nfe, "saturation", 1.0) or 1.0)
    thr = float(getattr(nfe, "threshold", 0.0) or 0.0)
    noise_amp = float(getattr(nfe, "signal_hash_noise", 0.0) or 0.0)
    t = int(sample.get("tick") or 0)
    rows = list(sample.get("neighbors") or [])
    for row in rows:
        if not isinstance(row, dict):
            continue
        annotate_near_field_row_with_3d(world, row, eye=eye, config=config, width=w, height=h)
        if row.get("visibility") in ("OCCLUDED_BY_OCCUPANCY", "OUTSIDE_VERTICAL_ACCEPTANCE"):
            continue
        dist = float(row.get("distance") or 0.0)
        dist_f = distance_attenuation(dist, dist_k)
        row["distance_factor"] = float(dist_f)
        ang = float(row.get("angular_factor") or 0.0)
        raw = float(row.get("raw_observable") or 0.0)
        cell = row.get("cell") or [0, 0]
        noise = _hash_noise(t, int(cell[0]), int(cell[1]), noise_amp)
        pre = max(0.0, gain * raw * dist_f * ang + noise)
        sat = min(sat_cap, pre)
        inside = bool(row.get("inside_fov"))
        above = sat >= thr
        final = float(sat) if above and inside else 0.0
        row["pre_threshold"] = float(pre)
        row["detectable"] = bool(above and inside and final > 0.0)
        row["final_contribution"] = float(final)

    sample["neighbors"] = rows
    sample["vw6"] = {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "eye_xyz": list(eye),
        "target_geometry_approximation": TARGET_GEOMETRY,
        "vertical_half_angle_deg": float(
            getattr(
                getattr(config, "minimal_vision_3d_geometric_interface", None),
                "vertical_half_angle_deg",
                DEFAULT_VERTICAL_HALF_ANGLE_DEG,
            )
            or DEFAULT_VERTICAL_HALF_ANGLE_DEG
        ),
        "researcher_only": True,
    }
    sample["eye_xyz"] = list(eye)
    return sample


def researcher_payload(world: Any) -> dict[str, Any]:
    st = state_of(world)
    if st is None:
        return {}
    return {
        "minimal_vision_3d_geometric_interface": {
            "schema": SCHEMA,
            "capability": CAPABILITY,
            "authority": AUTHORITY,
            "mechanism_id": MECHANISM_ID,
            "last_receipt": dict(st.last_receipt) if st.last_receipt else None,
            "counters": dict(st.counters),
            **AUTHORITY_FLAGS,
        }
    }


def observer_vision_3d_inspector_payload(
    world: Any,
    config: Any | None = None,
    *,
    body: Any = None,
    target_cell: tuple[int, int] | None = None,
    phenotype_sample: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Researcher-only VW6 inspector. PassivePassive: does not mutate vision/pose/occupancy."""
    if config is not None and not minimal_vision_3d_geometric_interface_is_active(config):
        return None
    st = state_of(world)
    if st is None and config is not None:
        st = ensure_state(world, config)
    if st is None:
        return None
    live = None
    eye = None
    if body is not None and target_cell is not None:
        cx, cy = int(target_cell[0]), int(target_cell[1])
        eye = sensor_eye_xyz(body, config)
        tz = cell_target_z(world, cx, cy, config=config)
        tx, ty = float(cx) + 0.5, float(cy) + 0.5
        w = int(world.T.shape[1])
        h = int(world.T.shape[0])
        rel = relative_xyz(eye[0], eye[1], eye[2], tx, ty, tz, width=w, height=h)
        cfg = getattr(config, "minimal_vision_3d_geometric_interface", None)
        vhalf = float(getattr(cfg, "vertical_half_angle_deg", DEFAULT_VERTICAL_HALF_ANGLE_DEG) or 90.0)
        elev_ok = elevation_accepted(rel["elevation_rad"], vertical_half_angle_deg=vhalf)
        los = occupancy_line_of_sight(
            world, eye[0], eye[1], eye[2], tx, ty, tz, config=config, width=w, height=h
        )
        # Phenotype/cognition boundary: physical visibility vs receptor access.
        phys_vis = bool(los["visible"]) and bool(elev_ok)
        receptor = None
        if isinstance(phenotype_sample, dict):
            neighbors = phenotype_sample.get("neighbors") or []
            match = None
            for row in neighbors:
                cell = row.get("cell") or []
                if len(cell) >= 2 and int(cell[0]) == cx and int(cell[1]) == cy:
                    match = row
                    break
            if match is not None:
                receptor = {
                    "visibility": match.get("visibility"),
                    "detectable": match.get("detectable"),
                    "final_contribution": match.get("final_contribution"),
                    "inside_fov": match.get("inside_fov"),
                    "distance": match.get("distance"),
                    "vw6_geometry": match.get("vw6_geometry"),
                }
        live = {
            "eye_xyz": list(eye),
            "target_xyz": [tx, ty, tz],
            "relative": rel,
            "distance_3d": rel["distance_3d"],
            "elevation_deg": rel["elevation_deg"],
            "vertical_acceptance": bool(elev_ok),
            "vertical_half_angle_deg": vhalf,
            "occupancy_los": {
                "visible": los["visible"],
                "occluded": los["occluded"],
                "blocker": los.get("blocker"),
                "legacy_max_surface_would_block": los.get("legacy_max_surface_would_block"),
                "legacy_samples": los.get("legacy_samples"),
            },
            "physical_visibility": phys_vis,
            "phenotype_receptor": receptor,
            "cognition_abstraction": "exo_*/surface_*/spatial_* floats only — no authoritative Z metadata",
            "object_occlusion": "WORLD_OCCUPANCY_ONLY",
            "body_occlusion": False,
            "resource_object_occlusion": False,
            "illumination_assumption": "EXISTING_NEAR_FIELD_CONTRACT_PRESERVED",
        }
    return {
        "mechanism": MECHANISM_ID,
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "authority_label": "AUTHORITATIVE VW6 MINIMAL VISION 3D GEOMETRIC INTERFACE",
        "legacy_label": "LEGACY XY / MAX-SURFACE GEOMETRY (not LOS authority when VW6 active)",
        "last_receipt": dict(st.last_receipt) if st.last_receipt else None,
        "live": live,
        "target_geometry_approximation": TARGET_GEOMETRY,
        "researcher_only_view": True,
        "not_agent_accessible": True,
        "source_kind": "VW6_VISION_3D_INSPECTION",
        "passive": True,
    }


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "minimal_vision_3d_geometric_interface.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "schema": SCHEMA,
        "profile": PROFILE,
        "description": (
            "Near-field vision uses physical XYZ + VW1 occupancy LOS. "
            "No cave/above/below semantics. No renderer. Phenotype boundary preserved."
        ),
    }
