"""Acanthostega VW2 · Occupancy support and contact queries.

Mechanism: occupancy_support_and_contact_queries
Schema: VW2_OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES_V1
Authority: AUTHORITATIVE_SUPPORT_CONTACT_FROM_VOLUMETRIC_OCCUPANCY

VW2 is a geometry/query consumer of VW1 ``world.volumetric_occupancy``.
It does **not** own or duplicate occupancy intervals.

Vertical support for body/object lower extent ``z`` (FGG convention: z = feet /
lower support point) is the top ``z_max`` of the geometrically relevant occupied
interval **at or below** query_z — never the legacy ``max(z_max)`` projected
surface when the body sits in an internal free gap.

Contact ≠ support forever: results carry ``contact_exists`` and
``support_capable`` separately. VW2 resolves vertical floor support/contact;
ceiling/wall dynamic response remains limited (probes may expose provenance).

Gravity / PE / landing ownership unchanged — only the support_z source migrates.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "VW2_OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES_V1"
CAPABILITY = "volumetric_world_support_contact_queries"
PROFILE = "VERTICAL_OCCUPANCY_SUPPORT_CONTACT_V1"
AUTHORITY = "AUTHORITATIVE_SUPPORT_CONTACT_FROM_VOLUMETRIC_OCCUPANCY"
MECHANISM_ID = "occupancy_support_and_contact_queries"
WORLD_ATTR = "occupancy_support_contact_state"
HISTORY_LIMIT = 16
DEFAULT_CONTACT_EPS = 1e-9
NO_SUPPORT_SENTINEL = -1.0e300

AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "occupancy_owner": "volumetric_world_material_occupancy",
    "occupancy_authority": "AUTHORITATIVE_WORLD_MATERIAL_OCCUPANCY_ABSOLUTE_Z",
    "physical_effects_active": True,
    "support_migrated": True,
    "contact_migrated": True,
    "gravity_authority_changed": False,
    "pe_mutex_changed": False,
    "landing_response_duplicated": False,
    "agent_accessible": False,
    "researcher_only_view": True,
    "ceiling_dynamic_response": False,
    "wall_dynamic_response": False,
}


class OccupancySupportContactValidationError(ValueError):
    """Raised when VW2 config or query inputs are invalid."""


@dataclass
class OccupancySupportAndContactQueriesConfig:
    """Fresh default OFF. Missing snapshot field keeps the mechanism OFF."""

    enabled: bool = False
    profile: str = PROFILE
    schema: str = SCHEMA
    contact_eps: float = DEFAULT_CONTACT_EPS

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "profile": str(self.profile),
            "schema": str(self.schema),
            "contact_eps": float(self.contact_eps),
            **AUTHORITY_FLAGS,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "OccupancySupportAndContactQueriesConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        profile = str(data.get("profile") or PROFILE)
        schema = str(data.get("schema") or SCHEMA)
        if profile != PROFILE:
            raise OccupancySupportContactValidationError(f"unsupported VW2 profile: {profile!r}")
        if schema != SCHEMA:
            raise OccupancySupportContactValidationError(f"unsupported VW2 schema: {schema!r}")
        eps = float(data.get("contact_eps", DEFAULT_CONTACT_EPS))
        if not (math.isfinite(eps) and eps >= 0.0):
            raise OccupancySupportContactValidationError("contact_eps must be finite and >= 0")
        return cls(enabled=bool(data.get("enabled", False)), profile=profile, schema=schema, contact_eps=eps)


def validate_config(cfg: OccupancySupportAndContactQueriesConfig) -> None:
    if str(cfg.profile) != PROFILE:
        raise OccupancySupportContactValidationError(f"profile must be {PROFILE!r}")
    if str(cfg.schema) != SCHEMA:
        raise OccupancySupportContactValidationError(f"schema must be {SCHEMA!r}")
    if not (math.isfinite(float(cfg.contact_eps)) and float(cfg.contact_eps) >= 0.0):
        raise OccupancySupportContactValidationError("contact_eps must be finite and >= 0")


def occupancy_support_and_contact_queries_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "occupancy_support_and_contact_queries", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        volumetric_world_material_occupancy_is_active,
    )

    return bool(volumetric_world_material_occupancy_is_active(config))


def set_occupancy_support_and_contact_queries(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "occupancy_support_and_contact_queries", None)
    if cur is None:
        config.occupancy_support_and_contact_queries = OccupancySupportAndContactQueriesConfig(enabled=on)
    else:
        cur.enabled = on
    if on:
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            set_volumetric_world_material_occupancy,
        )

        set_volumetric_world_material_occupancy(config, True)


@dataclass(frozen=True)
class VerticalSupportContactResult:
    """One vertical support/contact query result (derived; not stored world truth)."""

    cell_x: int
    cell_y: int
    query_z: float
    contact_eps: float
    contact_exists: bool
    support_capable: bool
    boundary_z: float | None
    clearance: float | None
    penetration: float
    relation: str
    source_interval: dict[str, Any] | None
    legacy_projected_surface: float | None
    query_type: str
    authority: str = AUTHORITY
    schema: str = SCHEMA

    @property
    def contradicts_legacy_projected_surface(self) -> bool:
        return bool(
            self.boundary_z is not None
            and self.legacy_projected_surface is not None
            and abs(float(self.boundary_z) - float(self.legacy_projected_surface)) > float(self.contact_eps)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "authority": self.authority,
            "query_type": self.query_type,
            "cell_x": int(self.cell_x),
            "cell_y": int(self.cell_y),
            "query_z": float(self.query_z),
            "contact_eps": float(self.contact_eps),
            "contact_exists": bool(self.contact_exists),
            "support_capable": bool(self.support_capable),
            "boundary_z": None if self.boundary_z is None else float(self.boundary_z),
            "clearance": None if self.clearance is None else float(self.clearance),
            "penetration": float(self.penetration),
            "relation": str(self.relation),
            "source_interval": None if self.source_interval is None else dict(self.source_interval),
            "legacy_projected_surface": (
                None if self.legacy_projected_surface is None else float(self.legacy_projected_surface)
            ),
            "contradicts_legacy_projected_surface": bool(
                self.boundary_z is not None
                and self.legacy_projected_surface is not None
                and abs(float(self.boundary_z) - float(self.legacy_projected_surface)) > float(self.contact_eps)
            ),
            "occupancy_owner": AUTHORITY_FLAGS["occupancy_owner"],
            "gravity_authority_changed": False,
            "pe_mutex_changed": False,
            "landing_response_duplicated": False,
            "researcher_only_view": True,
            "agent_accessible": False,
        }


@dataclass
class OccupancySupportContactState:
    config: OccupancySupportAndContactQueriesConfig
    last_result: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    query_count: int = 0


def state_of(world: Any) -> OccupancySupportContactState | None:
    raw = getattr(world, WORLD_ATTR, None)
    return raw if isinstance(raw, OccupancySupportContactState) else None


def ensure_state(world: Any, config: Any) -> OccupancySupportContactState | None:
    if not occupancy_support_and_contact_queries_is_active(config):
        if getattr(world, WORLD_ATTR, None) is not None:
            setattr(world, WORLD_ATTR, None)
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "occupancy_support_and_contact_queries", None)
    cfg = (
        raw
        if isinstance(raw, OccupancySupportAndContactQueriesConfig)
        else OccupancySupportAndContactQueriesConfig.from_dict(raw if isinstance(raw, dict) else None)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = OccupancySupportContactState(config=cfg)
    setattr(world, WORLD_ATTR, st)
    return st


def _eps(config: Any | None, override: float | None = None) -> float:
    if override is not None:
        return float(override)
    if config is not None:
        cfg = getattr(config, "occupancy_support_and_contact_queries", None)
        if cfg is not None:
            return float(getattr(cfg, "contact_eps", DEFAULT_CONTACT_EPS))
    return float(DEFAULT_CONTACT_EPS)


def _cell_xy(world: Any, x: Any, y: Any) -> tuple[int, int]:
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        state_of as vo_state,
        wrap_cell,
    )

    st = vo_state(world)
    if st is not None:
        return wrap_cell(st, x, y)
    from mechanistic_mind.planet.topology import wrap_coord

    grid = getattr(world, "T", None)
    if grid is None:
        return int(math.floor(float(x))), int(math.floor(float(y)))
    h, w = int(grid.shape[0]), int(grid.shape[1])
    return int(wrap_coord(int(math.floor(float(x))), w)), int(wrap_coord(int(math.floor(float(y))), h))


def query_vertical_support_at(
    world: Any,
    x: Any,
    y: Any,
    query_z: float,
    *,
    config: Any | None = None,
    contact_eps: float | None = None,
    record: bool = False,
) -> VerticalSupportContactResult:
    """Nearest support-capable occupied top at/below query_z from VW1 occupancy."""
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        compatibility_surface_elevation,
        occupied_intervals_at,
    )

    zz = float(query_z)
    if not math.isfinite(zz):
        raise OccupancySupportContactValidationError("query_z must be finite")
    eps = _eps(config, contact_eps)
    cell_x, cell_y = _cell_xy(world, x, y)
    intervals = occupied_intervals_at(world, x, y)
    legacy = compatibility_surface_elevation(world, x, y)

    containing = None
    for it in intervals:
        if it.contains(zz):
            containing = it
            break

    if containing is not None:
        boundary = float(containing.z_max)
        clearance = float(zz) - boundary
        penetration = max(0.0, -clearance)
        contact = clearance <= eps
        result = VerticalSupportContactResult(
            cell_x=cell_x,
            cell_y=cell_y,
            query_z=zz,
            contact_eps=eps,
            contact_exists=bool(contact or penetration > 0.0),
            support_capable=True,
            boundary_z=boundary,
            clearance=float(clearance),
            penetration=float(penetration),
            relation="INSIDE_OCCUPIED",
            source_interval=containing.as_dict(),
            legacy_projected_surface=None if legacy is None else float(legacy),
            query_type="VERTICAL_SUPPORT_AT",
        )
        _maybe_record(world, config, result, record=record)
        return result

    best = None
    best_z = -math.inf
    for it in intervals:
        top = float(it.z_max)
        if top <= zz + eps and top > best_z:
            best = it
            best_z = top

    if best is None:
        result = VerticalSupportContactResult(
            cell_x=cell_x,
            cell_y=cell_y,
            query_z=zz,
            contact_eps=eps,
            contact_exists=False,
            support_capable=False,
            boundary_z=None,
            clearance=None,
            penetration=0.0,
            relation="NO_SUPPORT_BELOW",
            source_interval=None,
            legacy_projected_surface=None if legacy is None else float(legacy),
            query_type="VERTICAL_SUPPORT_AT",
        )
        _maybe_record(world, config, result, record=record)
        return result

    boundary = float(best.z_max)
    clearance = float(zz) - boundary
    penetration = max(0.0, -clearance)
    if abs(clearance) <= eps:
        relation = "AT_SUPPORT"
        contact = True
        support_capable = True
    elif clearance > eps:
        relation = "ABOVE_SUPPORT"
        contact = False
        support_capable = False
    else:
        relation = "BELOW_SUPPORT"
        contact = True
        support_capable = True
    result = VerticalSupportContactResult(
        cell_x=cell_x,
        cell_y=cell_y,
        query_z=zz,
        contact_eps=eps,
        contact_exists=bool(contact),
        support_capable=bool(support_capable),
        boundary_z=boundary,
        clearance=float(clearance),
        penetration=float(penetration),
        relation=relation,
        source_interval=best.as_dict(),
        legacy_projected_surface=None if legacy is None else float(legacy),
        query_type="VERTICAL_SUPPORT_AT",
    )
    _maybe_record(world, config, result, record=record)
    return result


def support_boundary_z_for_vertical_integrator(
    world: Any,
    x: Any,
    y: Any,
    query_z: float,
    *,
    config: Any | None = None,
) -> tuple[float | None, VerticalSupportContactResult]:
    result = query_vertical_support_at(world, x, y, query_z, config=config, record=True)
    if result.boundary_z is None:
        return None, result
    return float(result.boundary_z), result


def query_vertical_support_for_entity(
    world: Any,
    entity: Any,
    *,
    config: Any | None = None,
    entity_kind: str = "body",
    record: bool = False,
) -> VerticalSupportContactResult:
    from mechanistic_mind.physical_system.flat_ground_gravity import read_z

    x = float(getattr(entity, "x", 0.0) or 0.0)
    y = float(getattr(entity, "y", 0.0) or 0.0)
    z = float(read_z(entity))
    return query_vertical_support_at(world, x, y, z, config=config, record=record)


def query_ceiling_probe_above(
    world: Any,
    x: Any,
    y: Any,
    query_z: float,
    *,
    config: Any | None = None,
) -> dict[str, Any]:
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import occupied_intervals_at

    zz = float(query_z)
    eps = _eps(config)
    best = None
    best_lo = math.inf
    for it in occupied_intervals_at(world, x, y):
        lo = float(it.z_min)
        if lo + eps >= zz and lo < best_lo:
            best = it
            best_lo = lo
    cell_x, cell_y = _cell_xy(world, x, y)
    return {
        "schema": SCHEMA,
        "query_type": "CEILING_PROBE_ABOVE",
        "cell_x": cell_x,
        "cell_y": cell_y,
        "query_z": zz,
        "ceiling_z_min": None if best is None else float(best.z_min),
        "source_interval": None if best is None else best.as_dict(),
        "dynamic_response": False,
        "researcher_only": True,
    }


def sample_footprint_vertical_support(
    world: Any,
    centre_x: float,
    centre_y: float,
    query_z: float,
    radius: float,
    *,
    config: Any | None = None,
) -> dict[str, Any]:
    from mechanistic_mind.physical_system.radius_aware_support_points import RING_OFFSETS_NORMALIZED

    R = float(radius)
    centre = query_vertical_support_at(world, centre_x, centre_y, query_z, config=config, record=False)
    samples = [
        {
            "role": "centre",
            "ring_index": None,
            "x": float(centre_x),
            "y": float(centre_y),
            "boundary_z": centre.boundary_z,
            "relation": centre.relation,
            "support_capable": centre.support_capable,
        }
    ]
    for k, (ox, oy) in enumerate(RING_OFFSETS_NORMALIZED):
        sx = float(centre_x) + R * float(ox)
        sy = float(centre_y) + R * float(oy)
        r = query_vertical_support_at(world, sx, sy, query_z, config=config, record=False)
        samples.append(
            {
                "role": "ring",
                "ring_index": int(k),
                "x": sx,
                "y": sy,
                "boundary_z": r.boundary_z,
                "relation": r.relation,
                "support_capable": r.support_capable,
            }
        )
    return {
        "schema": SCHEMA,
        "query_type": "FOOTPRINT_VERTICAL_SUPPORT",
        "query_z": float(query_z),
        "radius": float(R),
        "authoritative_support_z": centre.boundary_z,
        "centre_result": centre.as_dict(),
        "samples": samples,
        "researcher_only": True,
    }


def _maybe_record(
    world: Any, config: Any | None, result: VerticalSupportContactResult, *, record: bool
) -> None:
    if not record or world is None or config is None:
        return
    if not occupancy_support_and_contact_queries_is_active(config):
        return
    st = ensure_state(world, config)
    if st is None:
        return
    st.query_count = int(st.query_count) + 1
    payload = result.as_dict()
    st.last_result = payload
    st.history.append(payload)
    if len(st.history) > HISTORY_LIMIT:
        del st.history[: len(st.history) - HISTORY_LIMIT]


def profile_reference() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "mechanism_id": MECHANISM_ID,
        **AUTHORITY_FLAGS,
    }


def researcher_payload(world: Any) -> dict[str, Any]:
    st = state_of(world)
    if st is None:
        return {}
    return {
        "occupancy_support_contact": {
            **profile_reference(),
            "query_count": int(st.query_count),
            "last_result": dict(st.last_result) if st.last_result else None,
            "receipts": list(st.history)[-HISTORY_LIMIT:],
        }
    }


def observer_support_inspector_payload(
    world: Any, x: Any, y: Any, query_z: float, *, config: Any | None = None
) -> dict[str, Any] | None:
    if config is not None and not occupancy_support_and_contact_queries_is_active(config):
        return None
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import column_view

    result = query_vertical_support_at(world, x, y, query_z, config=config, record=False)
    ceiling = query_ceiling_probe_above(world, x, y, query_z, config=config)
    col = column_view(world, x, y)
    return {
        "mechanism": MECHANISM_ID,
        **result.as_dict(),
        "occupancy_column": {
            "occupied_intervals": col.get("occupied_intervals"),
            "free_gaps": col.get("free_gaps"),
            "derived_surface_elevation": col.get("derived_surface_elevation"),
            "source": col.get("source"),
        },
        "ceiling_probe": ceiling,
        "authority_label": "AUTHORITATIVE VW2 SUPPORT/CONTACT FROM VOLUMETRIC OCCUPANCY",
        "legacy_label": "LEGACY / DERIVED SURFACE PROJECTION (not support authority when VW2 active)",
        "researcher_only_view": True,
        "not_agent_accessible": True,
        "source_kind": "VW2_SUPPORT_CONTACT_INSPECTION",
    }


def occupancy_support_contact_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "occupancy_support_and_contact_queries.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "schema": SCHEMA,
        "profile": PROFILE,
        "description": (
            "Vertical support/contact queries from VW1 volumetric occupancy. "
            "Does not duplicate occupancy. Does not own gravity/PE/landing. "
            "Internal cavities contradict legacy max surface. researcher-only provenance."
        ),
    }
