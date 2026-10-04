"""Acanthostega Free-Space V1D · RELEASE + excavation support-loss integration.

Mechanism: release_and_excavation_support_loss_integration
Preset: ACANTHOSTEGA_BETA4_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
Parent: ACANTHOSTEGA_BETA4_VERTICAL_IMPACT_ACOUSTIC_EMISSION
Profile: RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION_V1
Receipt: RELEASE_EXCAVATION_SUPPORT_LOSS_V1
Architecture stage: FREE_SPACE_V1D_RELEASE_EXCAVATION_INTEGRATION

Closes the two physical entry paths into the shared free-space chain:
  RELEASE / excavation support loss
    → V1A UNSUPPORTED
    → existing FGG
    → existing V1B landing
    → existing V1C acoustic emission

No private landing or acoustic path. No downward snap. No second integration.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "release_and_excavation_support_loss_integration"
PROFILE_VERSION = "RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION_V1"
STATE_SCHEMA = "RELEASE_EXCAVATION_SUPPORT_LOSS_STATE_V1"
RECEIPT_KIND = "RELEASE_EXCAVATION_SUPPORT_LOSS_V1"
ARCHITECTURE_STAGE = "FREE_SPACE_V1D_RELEASE_EXCAVATION_INTEGRATION"

BANNER = (
    "FREE-SPACE ENTRY INTEGRATION · RELEASE + EXCAVATION SUPPORT LOSS · "
    "T+1 FALL · SHARED LANDING/SOUND · NO SNAP · NO SPECIAL-CASE IMPACT"
)

# Event classes
EVENT_RELEASE_ENTRY = "RELEASE_ENTRY"
EVENT_TERRAIN_MUTATION_REFRESH = "TERRAIN_MUTATION_REFRESH"
EVENT_SUPPORT_REMAINS_VALID = "SUPPORT_REMAINS_VALID"
EVENT_SUPPORT_LOST = "SUPPORT_LOST"
EVENT_REFRESH_DEDUPLICATED = "REFRESH_DEDUPLICATED"
EVENT_INELIGIBLE_ENTITY = "INELIGIBLE_ENTITY"
EVENT_ANOMALY = "ANOMALY"

# Classification / anomaly tokens
CLASS_SUPPORTED = "SUPPORTED"
CLASS_UNSUPPORTED = "UNSUPPORTED"
CLASS_RELEASE_START_PENETRATION = "RELEASE_START_PENETRATION"
CLASS_SUPPORT_GEOMETRY_UNAVAILABLE = "SUPPORT_GEOMETRY_UNAVAILABLE"
CLASS_NON_FINITE_VELOCITY = "NON_FINITE_VELOCITY"

SELECTION_POLICY = "BOUNDED_DYNAMIC_ENTITY_SCAN_BILINEAR_RASP_VERIFY_V1"
ENTITY_ORDER_POLICY = "KIND_THEN_STABLE_ID_ASC"
BILINEAR_NEIGHBORHOOD = "CSG_CELL_CENTRE_LATTICE_FOUR_CORNER_DEPENDENCY_V1"
INVALID_BELOW_TERRAIN_POLICY = (
    "ANOMALY_NO_SNAP_NO_SOUND_DEFER_BOUNDED_CORRECTION_TO_FIRST_ELIGIBLE_V1B"
)

HISTORY_LIMIT_DEFAULT = 48
DEDUP_BOUND = 4096
CHANGED_CELL_BOUND = 256
EPS_SUPPORT = 1e-12
EPS_LEVEL = 1e-9

RESEARCHER_FLAGS = {
    "semantic_label": False,
    "agent_accessible": False,
    "researcher_only": True,
    "special_case_landing": False,
    "special_case_sound": False,
    "second_integration": False,
    "downward_snap": False,
    "free_lift": False,
    "global_energy_conservation_claimed": False,
}


@dataclass
class ReleaseAndExcavationSupportLossIntegrationConfig:
    """Fresh default OFF; absent field = OFF (parent V1C unchanged)."""

    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        return {
            "enabled": on,
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "architecture_stage": ARCHITECTURE_STAGE,
            "receipt_kind": RECEIPT_KIND,
            "selection_policy": SELECTION_POLICY,
            "entity_order_policy": ENTITY_ORDER_POLICY,
            "bilinear_neighborhood": BILINEAR_NEIGHBORHOOD,
            "invalid_below_terrain_policy": INVALID_BELOW_TERRAIN_POLICY,
            "banner": BANNER if on else None,
            "special_case_landing_path": False,
            "special_case_sound_path": False,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None
    ) -> "ReleaseAndExcavationSupportLossIntegrationConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        pv = data.get("profile_version")
        if pv is not None and str(pv) != PROFILE_VERSION:
            raise ValueError(f"unknown release/excavation profile_version: {pv}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: ReleaseAndExcavationSupportLossIntegrationConfig) -> None:
    if not (1 <= int(cfg.history_limit) <= 256):
        raise ValueError("history_limit must be in [1, 256]")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def release_and_excavation_support_loss_integration_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "release_and_excavation_support_loss_integration", None)
    if cfg is None:
        return False
    if isinstance(cfg, dict):
        on = bool(cfg.get("enabled"))
    else:
        on = bool(getattr(cfg, "enabled", False))
    if not on:
        return False
    from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
        vertical_impact_acoustic_emission_is_active,
    )

    return bool(vertical_impact_acoustic_emission_is_active(config))


def set_release_and_excavation_support_loss_integration(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "release_and_excavation_support_loss_integration", None)
    if cur is None:
        if on:
            config.release_and_excavation_support_loss_integration = (
                ReleaseAndExcavationSupportLossIntegrationConfig(enabled=True)
            )
        return
    if isinstance(cur, dict):
        cfg = ReleaseAndExcavationSupportLossIntegrationConfig.from_dict(cur)
        cfg.enabled = on
        config.release_and_excavation_support_loss_integration = cfg
    else:
        cur.enabled = on


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "mechanism_id": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "architecture_stage": ARCHITECTURE_STAGE,
        "receipt_kind": RECEIPT_KIND,
        "enabled": bool(enabled),
        "banner": BANNER if enabled else None,
        "researcher_only": True,
        **RESEARCHER_FLAGS,
    }


@dataclass
class ReleaseAndExcavationSupportLossIntegrationState:
    config: ReleaseAndExcavationSupportLossIntegrationConfig
    event_seq: int = 0
    # (entity_kind|entity_id|tick) → {"result": str, "ended_episode": bool}
    refresh_ledger: dict[str, dict[str, Any]] = field(default_factory=dict)
    # tick → list of changed-cell dicts
    pending_changed_cells: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    last_receipt: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)


def state_of(world: Any) -> ReleaseAndExcavationSupportLossIntegrationState | None:
    raw = getattr(world, "release_and_excavation_support_loss_integration_state", None)
    return raw if isinstance(raw, ReleaseAndExcavationSupportLossIntegrationState) else None


def ensure_release_and_excavation_support_loss_integration_for_runtime(
    world: Any, config: Any
) -> ReleaseAndExcavationSupportLossIntegrationState | None:
    if not release_and_excavation_support_loss_integration_is_active(config):
        if getattr(world, "release_and_excavation_support_loss_integration_state", None) is not None:
            world.release_and_excavation_support_loss_integration_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "release_and_excavation_support_loss_integration", None)
    cfg = (
        raw
        if isinstance(raw, ReleaseAndExcavationSupportLossIntegrationConfig)
        else ReleaseAndExcavationSupportLossIntegrationConfig.from_dict(
            raw if isinstance(raw, dict) else None
        )
    )
    cfg.enabled = True
    validate_config(cfg)
    st = ReleaseAndExcavationSupportLossIntegrationState(config=cfg)
    world.release_and_excavation_support_loss_integration_state = st
    return st


def _trim_history(st: ReleaseAndExcavationSupportLossIntegrationState) -> None:
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    if len(st.refresh_ledger) > DEDUP_BOUND:
        # Drop oldest by insertion order (Py3.7+ dict).
        drop = len(st.refresh_ledger) - DEDUP_BOUND
        for k in list(st.refresh_ledger.keys())[:drop]:
            del st.refresh_ledger[k]


def _bump(st: ReleaseAndExcavationSupportLossIntegrationState, key: str, n: int = 1) -> None:
    st.counters[key] = int(st.counters.get(key, 0)) + int(n)


def _next_seq(st: ReleaseAndExcavationSupportLossIntegrationState) -> int:
    st.event_seq = int(st.event_seq) + 1
    return int(st.event_seq)


def _record(
    st: ReleaseAndExcavationSupportLossIntegrationState,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    row = {**receipt, **RESEARCHER_FLAGS}
    st.last_receipt = row
    st.history.append(row)
    _trim_history(st)
    return row


def _dims(world: Any) -> tuple[int, int]:
    t = getattr(world, "T", None)
    return (int(t.shape[1]), int(t.shape[0])) if t is not None else (32, 32)


def _wrap_cell(i: int, n: int) -> int:
    if n <= 0:
        return 0
    return int(i) % int(n)


def bilinear_corner_cells(x: float, y: float, *, width: int, height: int) -> set[tuple[int, int]]:
    """Cells whose centre-lattice samples feed CSG bilinear h(x,y).

    Matches continuous_surface_geometry._bilinear_patch indexing:
      i0 = floor(x - 0.5), j0 = floor(y - 0.5); corners (i0,j0),(i0+1,j0),(i0,j0+1),(i0+1,j0+1).
    """
    w, h = int(width), int(height)
    sx = float(x) - 0.5
    sy = float(y) - 0.5
    i0 = int(math.floor(sx))
    j0 = int(math.floor(sy))
    return {
        (_wrap_cell(i0, w), _wrap_cell(j0, h)),
        (_wrap_cell(i0 + 1, w), _wrap_cell(j0, h)),
        (_wrap_cell(i0, w), _wrap_cell(j0 + 1, h)),
        (_wrap_cell(i0 + 1, w), _wrap_cell(j0 + 1, h)),
    }


def bilinear_influenced_floor_cells(
    cell_x: int, cell_y: int, *, width: int, height: int
) -> list[tuple[int, int]]:
    """Discrete floor cells that may host poses whose bilinear sample uses (cell_x, cell_y).

    Continuous dependence region is [cx-0.5, cx+1.5) × [cy-0.5, cy+1.5); Moore 3×3 covers it.
    """
    w, h = int(width), int(height)
    cx, cy = int(cell_x), int(cell_y)
    out: list[tuple[int, int]] = []
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            out.append((_wrap_cell(cx + di, w), _wrap_cell(cy + dj, h)))
    out.sort()
    return out


def _entity_support_radius(entity: Any, *, kind: str, config: Any) -> float:
    if kind == "body":
        try:
            from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
                BODY_CONTACT_RADIUS,
            )

            cfg = getattr(config, "physical_body_resource_object_contact", None)
            if cfg is not None:
                return float(getattr(cfg, "body_contact_radius", BODY_CONTACT_RADIUS))
            return float(BODY_CONTACT_RADIUS)
        except Exception:
            return 0.575
    try:
        from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
            ensure_object_collision_radius,
        )

        return float(ensure_object_collision_radius(entity))
    except Exception:
        return float(getattr(entity, "collision_radius", 0.25) or 0.25)


def _rasp_active(config: Any) -> bool:
    try:
        from mechanistic_mind.physical_system.radius_aware_support_points import (
            radius_aware_support_points_is_active,
        )

        return bool(radius_aware_support_points_is_active(config))
    except Exception:
        return False


def _support_sample_poses(
    entity: Any, *, kind: str, config: Any
) -> list[tuple[float, float]]:
    x = float(getattr(entity, "x", 0.0) or 0.0)
    y = float(getattr(entity, "y", 0.0) or 0.0)
    poses = [(x, y)]
    if not _rasp_active(config):
        return poses
    r = _entity_support_radius(entity, kind=kind, config=config)
    # Same 8-ring offsets as radius_aware_support_points.RING_OFFSETS_NORMALIZED
    ring = (
        (1.0, 0.0),
        (0.7071067811865476, 0.7071067811865476),
        (0.0, 1.0),
        (-0.7071067811865476, 0.7071067811865476),
        (-1.0, 0.0),
        (-0.7071067811865476, -0.7071067811865476),
        (0.0, -1.0),
        (0.7071067811865476, -0.7071067811865476),
    )
    for ox, oy in ring:
        poses.append((x + r * ox, y + r * oy))
    return poses


def entity_depends_on_changed_cells(
    entity: Any,
    *,
    kind: str,
    config: Any,
    changed_cells: set[tuple[int, int]],
    width: int,
    height: int,
) -> bool:
    if not changed_cells:
        return False
    for sx, sy in _support_sample_poses(entity, kind=kind, config=config):
        if bilinear_corner_cells(sx, sy, width=width, height=height) & changed_cells:
            return True
    return False


def _iter_dynamic_entities(world: Any, config: Any) -> list[dict[str, Any]]:
    """Bounded full dynamic-entity scan (V1 correctness > index completeness)."""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def _add(kind: str, eid: str, ent: Any, body_slot: str | None = None) -> None:
        key = (kind, eid)
        if key in seen or ent is None:
            return
        seen.add(key)
        rows.append(
            {
                "kind": kind,
                "id": eid,
                "entity": ent,
                "body_slot": body_slot,
            }
        )

    refs = list(getattr(world, "detached_placement_body_refs", None) or [])
    for row in refs:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        _add("body", str(row[0]), row[1], body_slot=str(row[0]))

    body = getattr(world, "body", None)
    if body is not None:
        _add("body", "body-0", body, body_slot="body-0")

    for attr in ("bodies", "agent_bodies"):
        bag = getattr(world, attr, None)
        if isinstance(bag, dict):
            for bid, b in sorted(bag.items(), key=lambda kv: str(kv[0])):
                _add("body", str(bid), b, body_slot=str(bid))
        elif isinstance(bag, (list, tuple)):
            for i, b in enumerate(bag):
                _add("body", f"body-{i}", b, body_slot=f"body-{i}")

    host = getattr(world, "_host_runtime", None)
    if host is not None:
        try:
            from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

            for bid, b in body_refs_for_runtime(host):
                _add("body", str(bid), b, body_slot=str(bid))
        except Exception:
            pass

    for obj in list(getattr(world, "resource_objects", None) or []):
        ps = str(getattr(obj, "physical_state", "") or "")
        if ps == "HELD":
            continue
        if ps not in ("FREE_STATIC", "FREE_MOVING", "FREE_REST"):
            # Still allow free-rest / free-static / free-moving; skip deposits etc.
            if "FREE" not in ps:
                continue
        oid = str(getattr(obj, "object_id", "") or "")
        if not oid:
            continue
        _add("object", oid, obj)

    rows.sort(key=lambda r: (str(r["kind"]), str(r["id"])))
    return rows


def _support_z(world: Any, config: Any, x: float, y: float, *, z: float | None = None) -> float | None:
    try:
        from mechanistic_mind.physical_system.surface_elevation_support import (
            support_z_for_entity,
        )

        sz = float(support_z_for_entity(world, config, float(x), float(y), z=z))
        if not math.isfinite(sz):
            return None
        return sz
    except Exception:
        return None


def _ledger_key(kind: str, eid: str, tick: int) -> str:
    return f"{kind}|{eid}|{int(tick)}"


# ---------------------------------------------------------------------------
# RELEASE entry
# ---------------------------------------------------------------------------


def stamp_release_vertical_eligibility(
    obj: Any,
    *,
    tick: int,
) -> dict[str, Any]:
    """Stamp release_tick=T and dynamics_eligible_tick=max(existing, T+1)."""
    t = int(tick)
    eligible = t + 1
    existing = getattr(obj, "dynamics_eligible_tick", None)
    if existing is not None:
        try:
            eligible = max(int(existing), eligible)
        except (TypeError, ValueError):
            pass
    obj.release_tick = t
    obj.dynamics_eligible_tick = int(eligible)
    obj.release_transition_tick = t
    # Pose-history / FD: clear any grasp-snap velocity contamination on object.
    # Horizontal vx/vy are owned by apply_release_transfer; do not invent here.
    return {
        "release_tick": t,
        "dynamics_eligible_tick": int(eligible),
        "release_transition_tick": t,
    }


def classify_release_support(
    world: Any,
    config: Any,
    obj: Any,
    *,
    tick: int,
) -> dict[str, Any]:
    """Classify support at RELEASE without creating impact/sound."""
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        read_vz,
        read_z,
        vertical_half_extent_of,
    )

    x = float(getattr(obj, "x", 0.0) or 0.0)
    y = float(getattr(obj, "y", 0.0) or 0.0)
    z = float(read_z(obj))
    vz = float(read_vz(obj))
    he = float(vertical_half_extent_of(obj, kind="object", config=config))
    sz = _support_z(world, config, x, y, z=z)
    if sz is None:
        obj.grounded = False
        return {
            "support_classification": CLASS_SUPPORT_GEOMETRY_UNAVAILABLE,
            "support_z": None,
            "anomaly": CLASS_SUPPORT_GEOMETRY_UNAVAILABLE,
            "grounded_after": False,
            "creates_impact": False,
            "creates_sound": False,
            "z": z,
            "centre_z": z + he,
            "vertical_half_extent": he,
            "vz": vz,
        }
    if abs(z - sz) <= EPS_SUPPORT and abs(vz) <= EPS_SUPPORT:
        obj.grounded = True
        return {
            "support_classification": CLASS_SUPPORTED,
            "support_z": float(sz),
            "anomaly": None,
            "grounded_after": True,
            "creates_impact": False,
            "creates_sound": False,
            "z": z,
            "centre_z": z + he,
            "vertical_half_extent": he,
            "vz": vz,
        }
    if z > sz + EPS_SUPPORT:
        obj.grounded = False
        return {
            "support_classification": CLASS_UNSUPPORTED,
            "support_z": float(sz),
            "anomaly": None,
            "grounded_after": False,
            "creates_impact": False,
            "creates_sound": False,
            "z": z,
            "centre_z": z + he,
            "vertical_half_extent": he,
            "vz": vz,
        }
    # Base below support beyond tolerance — anomaly; no snap; defer V1B correction.
    obj.grounded = False
    return {
        "support_classification": CLASS_RELEASE_START_PENETRATION,
        "support_z": float(sz),
        "anomaly": CLASS_RELEASE_START_PENETRATION,
        "grounded_after": False,
        "creates_impact": False,
        "creates_sound": False,
        "z": z,
        "centre_z": z + he,
        "vertical_half_extent": he,
        "vz": vz,
        "penetration": float(sz) - float(z),
        "correction_deferred_to": "FIRST_ELIGIBLE_V1B",
    }


def process_release_entry(
    world: Any,
    config: Any,
    obj: Any,
    holder_body: Any,
    *,
    tick: int,
    holder_body_id: str | None = None,
    manipulator_id: str | None = None,
) -> dict[str, Any] | None:
    """Authoritative RELEASE entry into shared free-space chain (no same-tick FGG/V1B/V1C)."""
    if not release_and_excavation_support_loss_integration_is_active(config):
        return None
    st = ensure_release_and_excavation_support_loss_integration_for_runtime(world, config)
    if st is None:
        return None

    from mechanistic_mind.physical_system.flat_ground_gravity import (
        ensure_object_vertical,
        read_vz,
        read_z,
    )

    ensure_object_vertical(obj, config)
    # Pose authority: held base xyz already mirrored before RELEASE.
    z = float(read_z(obj))
    # Velocity: vz from holder; vx/vy left for FOK apply_release_transfer.
    holder_vz = float(read_vz(holder_body))
    if not math.isfinite(holder_vz):
        holder_vz = 0.0
        vel_anomaly = CLASS_NON_FINITE_VELOCITY
    else:
        vel_anomaly = None
    obj.vz = float(holder_vz)

    elig = stamp_release_vertical_eligibility(obj, tick=int(tick))
    classified = classify_release_support(world, config, obj, tick=int(tick))

    # V1A receipt via existing contract (no gravity this tick).
    try:
        from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
            GRAVITY_SKIP_HELD,
            free_space_state_and_pe_authority_contract_is_active,
            record_vertical_contract_receipt,
        )

        if free_space_state_and_pe_authority_contract_is_active(config):
            sz = classified.get("support_z")
            record_vertical_contract_receipt(
                world,
                config,
                tick=int(tick),
                entity_id=str(getattr(obj, "object_id", "released")),
                entity_kind="object",
                body_slot=str(holder_body_id or ""),
                z_before=z,
                vz_before=float(holder_vz),
                z_after=float(classified["z"]),
                vz_after=float(classified["vz"]),
                centre_z_after=float(classified["centre_z"]),
                vertical_half_extent=float(classified["vertical_half_extent"]),
                support_z=float(sz) if sz is not None else float(classified["z"]),
                was_grounded=False,
                grounded_after=bool(classified["grounded_after"]),
                gravity_applied=False,
                skip_gravity=True,
                gravity_skip_reason=GRAVITY_SKIP_HELD,
                support_applied=False,
                landed=False,
                support_dissipated=0.0,
                mass=float(getattr(obj, "mass", 1.0) or 1.0),
                vertical_integration_eligible=False,
                vertical_integration_applied=False,
                release_transition=True,
            )
    except Exception:
        pass

    event = EVENT_RELEASE_ENTRY
    if classified.get("anomaly"):
        event = EVENT_ANOMALY
        _bump(st, "release_anomalies")
    elif classified["support_classification"] == CLASS_SUPPORTED:
        _bump(st, "release_at_support")
    else:
        _bump(st, "release_above_support")

    _bump(st, "release_entries")
    seq = _next_seq(st)
    receipt = {
        "receipt_kind": RECEIPT_KIND,
        "event_class": event,
        "event_kind": event,
        "event_sequence": seq,
        "tick": int(tick),
        "source_kind": "RELEASE",
        "mechanism_id": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "architecture_stage": ARCHITECTURE_STAGE,
        "entity_kind": "object",
        "entity_id": str(getattr(obj, "object_id", "")),
        "holder_body_id": str(holder_body_id or getattr(obj, "holder_body_id", "") or ""),
        "manipulator_id": str(manipulator_id or getattr(obj, "manipulator_id", "") or ""),
        "pose_x": float(getattr(obj, "x", 0.0) or 0.0),
        "pose_y": float(getattr(obj, "y", 0.0) or 0.0),
        "pose_z": float(classified["z"]),
        "centre_z": float(classified["centre_z"]),
        "collision_radius": float(
            getattr(obj, "collision_radius", classified["vertical_half_extent"]) or 0.0
        ),
        "vertical_half_extent": float(classified["vertical_half_extent"]),
        "inherited_vx": None,  # filled by FOK transfer
        "inherited_vy": None,
        "inherited_vz": float(holder_vz),
        "velocity_provenance": {
            "vx_vy": "EFFECTOR_FINITE_DIFFERENCE_FOK_APPLY_RELEASE_TRANSFER",
            "vz": "HOLDER_BODY_VZ",
            "throwing_impulse": False,
            "grasp_snap_as_trajectory": False,
            "stale_free_pose_sweep": False,
        },
        "release_tick": elig["release_tick"],
        "dynamics_eligible_tick": elig["dynamics_eligible_tick"],
        "support_z": classified.get("support_z"),
        "support_classification": classified["support_classification"],
        "anomaly": classified.get("anomaly") or vel_anomaly,
        "creates_impact": False,
        "creates_sound": False,
        "independent_integration_this_tick": False,
        "enters_shared_v1a": True,
        "enters_shared_fgg": True,  # at T+1 if unsupported
        "enters_shared_v1b": True,  # later physical landing
        "enters_shared_v1c": True,  # later physical landing response
        "special_case_landing": False,
        "special_case_sound": False,
        "release_created_energy": False,
        "penetration": classified.get("penetration"),
        "correction_deferred_to": classified.get("correction_deferred_to"),
    }
    return _record(st, receipt)


def note_release_horizontal_velocity(
    world: Any,
    config: Any,
    *,
    object_id: str,
    vx: float,
    vy: float,
    velocity_measurement: str | None = None,
    tick: int | None = None,
) -> None:
    """Annotate last RELEASE_ENTRY with FOK horizontal velocity provenance."""
    if not release_and_excavation_support_loss_integration_is_active(config):
        return
    st = state_of(world)
    if st is None or not st.history:
        return
    oid = str(object_id)
    for row in reversed(st.history):
        if (
            row.get("event_class") in (EVENT_RELEASE_ENTRY, EVENT_ANOMALY)
            and str(row.get("entity_id")) == oid
            and row.get("source_kind") == "RELEASE"
        ):
            if tick is not None and int(row.get("tick", -1)) != int(tick):
                continue
            row["inherited_vx"] = float(vx) if math.isfinite(float(vx)) else 0.0
            row["inherited_vy"] = float(vy) if math.isfinite(float(vy)) else 0.0
            if not (math.isfinite(float(vx)) and math.isfinite(float(vy))):
                row["anomaly"] = CLASS_NON_FINITE_VELOCITY
                row["event_class"] = EVENT_ANOMALY
            if velocity_measurement is not None:
                row["velocity_measurement"] = str(velocity_measurement)
            st.last_receipt = row
            return


# ---------------------------------------------------------------------------
# Excavation support refresh
# ---------------------------------------------------------------------------


def note_committed_terrain_support_region(
    world: Any,
    config: Any,
    *,
    cell_x: int,
    cell_y: int,
    elevation_before: float | None,
    elevation_after: float,
    tick: int,
    transaction_id: str | None = None,
    sparse_revision: int | None = None,
) -> dict[str, Any] | None:
    """Accumulate a successfully committed terrain mutation into the changed-region ledger."""
    if not release_and_excavation_support_loss_integration_is_active(config):
        return None
    st = ensure_release_and_excavation_support_loss_integration_for_runtime(world, config)
    if st is None:
        return None
    w, h = _dims(world)
    cx = _wrap_cell(int(cell_x), w)
    cy = _wrap_cell(int(cell_y), h)
    t = int(tick) if tick is not None else int(getattr(world, "tick", -1) or -1)
    region = {
        "cell_x": cx,
        "cell_y": cy,
        "elevation_before": (
            float(elevation_before) if elevation_before is not None else None
        ),
        "elevation_after": float(elevation_after),
        "tick": t,
        "transaction_id": str(transaction_id) if transaction_id is not None else None,
        "sparse_revision": (
            int(sparse_revision) if sparse_revision is not None else None
        ),
        "influenced_floor_cells": bilinear_influenced_floor_cells(
            cx, cy, width=w, height=h
        ),
    }
    bag = st.pending_changed_cells.setdefault(t, [])
    bag.append(region)
    if len(bag) > CHANGED_CELL_BOUND:
        st.pending_changed_cells[t] = bag[-CHANGED_CELL_BOUND:]
    _bump(st, "terrain_mutations_noted")

    # CSG generation bump (parent left this unwired; V1D owns the call when ON).
    try:
        from mechanistic_mind.physical_system.continuous_surface_geometry import (
            continuous_surface_geometry_is_active,
            note_authoritative_surface_mutation,
        )

        if continuous_surface_geometry_is_active(config):
            note_authoritative_surface_mutation(world, config)
    except Exception:
        pass

    return region


def refresh_support_after_terrain_mutation(
    world: Any,
    config: Any,
    *,
    cell_x: int,
    cell_y: int,
    elevation_before: float | None = None,
    elevation_after: float,
    tick: int | None = None,
    transaction_id: str | None = None,
    sparse_revision: int | None = None,
) -> list[dict[str, Any]]:
    """Authoritative excavation support refresh (bodies + FREE + bilinear + RASP + dedup)."""
    if not release_and_excavation_support_loss_integration_is_active(config):
        return []
    st = ensure_release_and_excavation_support_loss_integration_for_runtime(world, config)
    if st is None:
        return []

    t = int(tick) if tick is not None else int(getattr(world, "tick", -1) or -1)
    region = note_committed_terrain_support_region(
        world,
        config,
        cell_x=int(cell_x),
        cell_y=int(cell_y),
        elevation_before=elevation_before,
        elevation_after=float(elevation_after),
        tick=t,
        transaction_id=transaction_id,
        sparse_revision=sparse_revision,
    )
    w, h = _dims(world)
    changed: set[tuple[int, int]] = set()
    for reg in st.pending_changed_cells.get(t, []) or []:
        changed.add((int(reg["cell_x"]), int(reg["cell_y"])))
    # Also include this mutation's cell explicitly.
    changed.add((_wrap_cell(int(cell_x), w), _wrap_cell(int(cell_y), h)))

    candidates = _iter_dynamic_entities(world, config)
    verified: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []

    for row in candidates:
        ent = row["entity"]
        kind = str(row["kind"])
        eid = str(row["id"])
        if kind == "object":
            ps = str(getattr(ent, "physical_state", "") or "")
            if ps == "HELD":
                seq = _next_seq(st)
                receipts.append(
                    _record(
                        st,
                        {
                            "receipt_kind": RECEIPT_KIND,
                            "event_class": EVENT_INELIGIBLE_ENTITY,
                            "event_kind": EVENT_INELIGIBLE_ENTITY,
                            "event_sequence": seq,
                            "tick": t,
                            "source_kind": "TERRAIN_MUTATION",
                            "entity_kind": kind,
                            "entity_id": eid,
                            "reason": "HELD_EXCLUDED",
                            "mechanism_id": MECHANISM_ID,
                            "profile_version": PROFILE_VERSION,
                        },
                    )
                )
                continue
        if not entity_depends_on_changed_cells(
            ent,
            kind=kind,
            config=config,
            changed_cells=changed,
            width=w,
            height=h,
        ):
            continue
        verified.append(row)
        rec = _reclassify_entity_after_terrain(
            world,
            config,
            st,
            entity=ent,
            kind=kind,
            entity_id=eid,
            body_slot=row.get("body_slot"),
            tick=t,
            region=region,
            candidate_count=len(candidates),
            verified_before=len(verified),
        )
        if rec is not None:
            receipts.append(rec)

    _bump(st, "refresh_passes")
    _bump(st, "candidates_scanned", len(candidates))
    _bump(st, "entities_verified", len(verified))
    return receipts


def _reclassify_entity_after_terrain(
    world: Any,
    config: Any,
    st: ReleaseAndExcavationSupportLossIntegrationState,
    *,
    entity: Any,
    kind: str,
    entity_id: str,
    body_slot: str | None,
    tick: int,
    region: dict[str, Any] | None,
    candidate_count: int,
    verified_before: int,
) -> dict[str, Any] | None:
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        ensure_body_vertical,
        ensure_object_vertical,
        read_vz,
        read_z,
        vertical_half_extent_of,
    )

    if kind == "body":
        ensure_body_vertical(entity, config)
    else:
        ensure_object_vertical(entity, config)

    lk = _ledger_key(kind, entity_id, tick)
    prior = st.refresh_ledger.get(lk)
    if prior is not None and str(prior.get("result")) == EVENT_SUPPORT_LOST:
        _bump(st, "refresh_deduplicated")
        seq = _next_seq(st)
        return _record(
            st,
            {
                "receipt_kind": RECEIPT_KIND,
                "event_class": EVENT_REFRESH_DEDUPLICATED,
                "event_kind": EVENT_REFRESH_DEDUPLICATED,
                "event_sequence": seq,
                "tick": int(tick),
                "source_kind": "TERRAIN_MUTATION",
                "entity_kind": kind,
                "entity_id": entity_id,
                "body_slot": body_slot,
                "dedup_key": lk,
                "prior_result": prior.get("result"),
                "mechanism_id": MECHANISM_ID,
                "profile_version": PROFILE_VERSION,
                "material_transaction_id": (region or {}).get("transaction_id"),
                "creates_impact": False,
                "creates_sound": False,
            },
        )

    x = float(getattr(entity, "x", 0.0) or 0.0)
    y = float(getattr(entity, "y", 0.0) or 0.0)
    z_before = float(read_z(entity))
    vz_before = float(read_vz(entity))
    grounded_before = bool(getattr(entity, "grounded", True))
    he = float(vertical_half_extent_of(entity, kind=kind, config=config))
    sz = _support_z(world, config, x, y, z=z_before)
    rasp_on = _rasp_active(config)
    rasp_class = None
    if sz is None:
        seq = _next_seq(st)
        return _record(
            st,
            {
                "receipt_kind": RECEIPT_KIND,
                "event_class": EVENT_ANOMALY,
                "event_kind": EVENT_ANOMALY,
                "event_sequence": seq,
                "tick": int(tick),
                "source_kind": "TERRAIN_MUTATION",
                "entity_kind": kind,
                "entity_id": entity_id,
                "anomaly": CLASS_SUPPORT_GEOMETRY_UNAVAILABLE,
                "z_unchanged": True,
                "pose_z": z_before,
                "mechanism_id": MECHANISM_ID,
                "profile_version": PROFILE_VERSION,
                "creates_impact": False,
                "creates_sound": False,
            },
        )

    support_valid = bool(
        grounded_before
        and abs(z_before - float(sz)) <= EPS_SUPPORT
        and abs(vz_before) <= EPS_SUPPORT
    )
    # Radius-aware: if active and previously grounded, LOSS class forces invalid.
    if rasp_on and grounded_before:
        try:
            from mechanistic_mind.physical_system.radius_aware_support_points import (
                CLASS_LOSS,
                RadiusAwareSupportPointsConfig,
                classify_support_contact,
                sample_radius_aware_support,
            )

            r = _entity_support_radius(entity, kind=kind, config=config)
            sample = sample_radius_aware_support(
                world, x, y, r, config=config, grounded=True
            )
            rasp_cfg = getattr(config, "radius_aware_support_points", None)
            if isinstance(rasp_cfg, dict):
                rasp_cfg = RadiusAwareSupportPointsConfig.from_dict(rasp_cfg)
            if rasp_cfg is None:
                rasp_cfg = RadiusAwareSupportPointsConfig(enabled=True)
            classed = classify_support_contact(
                sample,
                grounded=True,
                prev_class=None,
                cfg=rasp_cfg,
            )
            rasp_class = str(classed.get("support_class") or "")
            if rasp_class == CLASS_LOSS:
                support_valid = False
            if z_before > float(sz) + EPS_LEVEL:
                support_valid = False
        except Exception:
            if z_before > float(sz) + EPS_LEVEL:
                support_valid = False
    else:
        if grounded_before and z_before > float(sz) + EPS_LEVEL:
            support_valid = False
        elif not grounded_before:
            # Already airborne — still allow one refresh note if newly affected.
            support_valid = False if z_before > float(sz) + EPS_LEVEL else support_valid

    if support_valid:
        if prior is not None and str(prior.get("result")) == EVENT_SUPPORT_REMAINS_VALID:
            _bump(st, "refresh_deduplicated")
            seq = _next_seq(st)
            return _record(
                st,
                {
                    "receipt_kind": RECEIPT_KIND,
                    "event_class": EVENT_REFRESH_DEDUPLICATED,
                    "event_kind": EVENT_REFRESH_DEDUPLICATED,
                    "event_sequence": seq,
                    "tick": int(tick),
                    "source_kind": "TERRAIN_MUTATION",
                    "entity_kind": kind,
                    "entity_id": entity_id,
                    "dedup_key": lk,
                    "prior_result": EVENT_SUPPORT_REMAINS_VALID,
                    "mechanism_id": MECHANISM_ID,
                    "profile_version": PROFILE_VERSION,
                    "creates_impact": False,
                    "creates_sound": False,
                },
            )
        st.refresh_ledger[lk] = {"result": EVENT_SUPPORT_REMAINS_VALID, "ended_episode": False}
        _bump(st, "support_remains_valid")
        seq = _next_seq(st)
        return _record(
            st,
            {
                "receipt_kind": RECEIPT_KIND,
                "event_class": EVENT_SUPPORT_REMAINS_VALID,
                "event_kind": "SUPPORT_REMAINS_VALID_AFTER_TERRAIN_MUTATION",
                "event_sequence": seq,
                "tick": int(tick),
                "source_kind": "TERRAIN_MUTATION",
                "entity_kind": kind,
                "entity_id": entity_id,
                "body_slot": body_slot,
                "material_transaction_id": (region or {}).get("transaction_id"),
                "source_cell": [
                    (region or {}).get("cell_x"),
                    (region or {}).get("cell_y"),
                ],
                "support_height_before": (region or {}).get("elevation_before"),
                "support_height_after": float(sz),
                "support_z_after": float(sz),
                "pose_z": z_before,
                "entity_z_unchanged": True,
                "grounded_before": grounded_before,
                "grounded_after": True,
                "radius_aware_mode": rasp_on,
                "rasp_support_class": rasp_class,
                "selection_policy": SELECTION_POLICY,
                "candidate_entity_count": int(candidate_count),
                "affected_entity_count": int(verified_before),
                "creates_impact": False,
                "creates_sound": False,
                "mechanism_id": MECHANISM_ID,
                "profile_version": PROFILE_VERSION,
                "architecture_stage": ARCHITECTURE_STAGE,
            },
        )

    # Support loss commit — preserve pose; no snap; no second FGG this tick.
    entity.grounded = False
    # z / vz preserved exactly
    entity.z = float(z_before)
    entity.vz = float(vz_before)

    ended = False
    if prior is None or not bool(prior.get("ended_episode")):
        try:
            from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
                end_episode_for_entity,
            )

            end_episode_for_entity(
                world,
                config,
                entity_kind=kind,
                entity_id=entity_id,
                tick=int(tick),
                reason="SUPPORT_LOSS_TERRAIN_MUTATION",
            )
            ended = True
        except Exception:
            ended = False

    try:
        from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
            free_space_state_and_pe_authority_contract_is_active,
            note_support_loss_terrain_mutation,
        )

        if free_space_state_and_pe_authority_contract_is_active(config):
            note_support_loss_terrain_mutation(
                world,
                config,
                tick=int(tick),
                entity_id=entity_id,
                entity_kind=kind,
                z=float(z_before),
                vz=float(vz_before),
                support_z_after=float(sz),
                half_extent=float(he),
            )
    except Exception:
        pass

    # Next ordinary vertical eligibility: bodies always next tick; objects stamp if present.
    next_eligible = int(tick) + 1
    if kind == "object":
        existing = getattr(entity, "dynamics_eligible_tick", None)
        if existing is not None:
            try:
                next_eligible = max(int(existing), next_eligible)
            except (TypeError, ValueError):
                pass
        entity.dynamics_eligible_tick = int(next_eligible)

    st.refresh_ledger[lk] = {"result": EVENT_SUPPORT_LOST, "ended_episode": bool(ended)}
    _bump(st, "support_lost")
    seq = _next_seq(st)
    return _record(
        st,
        {
            "receipt_kind": RECEIPT_KIND,
            "event_class": EVENT_SUPPORT_LOST,
            "event_kind": EVENT_SUPPORT_LOST,
            "event_sequence": seq,
            "tick": int(tick),
            "source_kind": "TERRAIN_MUTATION",
            "entity_kind": kind,
            "entity_id": entity_id,
            "body_slot": body_slot,
            "material_transaction_id": (region or {}).get("transaction_id"),
            "source_cell": [
                (region or {}).get("cell_x"),
                (region or {}).get("cell_y"),
            ],
            "sparse_revision": (region or {}).get("sparse_revision"),
            "changed_cell_neighborhood": (region or {}).get("influenced_floor_cells"),
            "support_height_before": (region or {}).get("elevation_before"),
            "support_height_after": float(sz),
            "support_z_after": float(sz),
            "pose_z": z_before,
            "entity_z_unchanged": True,
            "downward_snap": False,
            "free_lift": False,
            "grounded_before": grounded_before,
            "grounded_after": False,
            "ground_traction_eligible": False,
            "ground_friction_eligible": False,
            "next_vertical_eligibility": int(next_eligible),
            "episode_end": bool(ended),
            "episode_end_reason": "SUPPORT_LOSS_TERRAIN_MUTATION" if ended else None,
            "dedup_key": lk,
            "radius_aware_mode": rasp_on,
            "rasp_support_class": rasp_class,
            "selection_policy": SELECTION_POLICY,
            "candidate_entity_count": int(candidate_count),
            "affected_entity_count": int(verified_before),
            "second_vertical_integration": False,
            "creates_impact": False,
            "creates_sound": False,
            "enters_shared_v1a": True,
            "enters_shared_fgg": True,
            "enters_shared_v1b": True,
            "enters_shared_v1c": True,
            "special_case_landing": False,
            "special_case_sound": False,
            "terrain_removal_credits_entity": False,
            "second_work_debit": False,
            "mechanism_id": MECHANISM_ID,
            "profile_version": PROFILE_VERSION,
            "architecture_stage": ARCHITECTURE_STAGE,
        },
    )


# ---------------------------------------------------------------------------
# Snapshot / restore
# ---------------------------------------------------------------------------


def serialize_state(
    st: ReleaseAndExcavationSupportLossIntegrationState | None,
) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "event_seq": int(st.event_seq),
        "refresh_ledger": {k: dict(v) for k, v in st.refresh_ledger.items()},
        "pending_changed_cells": {
            str(k): [dict(r) for r in v] for k, v in st.pending_changed_cells.items()
        },
        "counters": dict(st.counters),
        "last_receipt": dict(st.last_receipt) if st.last_receipt else None,
        "history": list(st.history),
        "banner": BANNER,
        **RESEARCHER_FLAGS,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> ReleaseAndExcavationSupportLossIntegrationState | None:
    if not data or not release_and_excavation_support_loss_integration_is_active(config):
        if not release_and_excavation_support_loss_integration_is_active(config):
            world.release_and_excavation_support_loss_integration_state = None
        return None
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "release_and_excavation_support_loss_integration", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = ReleaseAndExcavationSupportLossIntegrationConfig.from_dict(raw_cfg)
    cfg.enabled = True
    validate_config(cfg)
    pending: dict[int, list[dict[str, Any]]] = {}
    for k, v in dict(data.get("pending_changed_cells") or {}).items():
        try:
            pending[int(k)] = [dict(r) for r in (v or [])]
        except (TypeError, ValueError):
            continue
    st = ReleaseAndExcavationSupportLossIntegrationState(
        config=cfg,
        event_seq=int(data.get("event_seq") or 0),
        refresh_ledger={
            str(k): dict(v) for k, v in dict(data.get("refresh_ledger") or {}).items()
        },
        pending_changed_cells=pending,
        counters={str(a): int(b) for a, b in dict(data.get("counters") or {}).items()},
        last_receipt=dict(data["last_receipt"]) if data.get("last_receipt") else None,
        history=[dict(r) for r in (data.get("history") or [])],
    )
    world.release_and_excavation_support_loss_integration_state = st
    return st


def inspector_summary(world: Any, config: Any | None = None) -> dict[str, Any]:
    st = state_of(world)
    on = (
        release_and_excavation_support_loss_integration_is_active(config)
        if config is not None
        else st is not None
    )
    last = dict(st.last_receipt) if st and st.last_receipt else None
    return {
        "active": bool(on),
        "banner": BANNER if on else None,
        "mechanism_id": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "architecture_stage": ARCHITECTURE_STAGE,
        "counters": dict(st.counters) if st else {},
        "last_receipt": last,
        "history_len": len(st.history) if st else 0,
        "researcher_only": True,
    }
