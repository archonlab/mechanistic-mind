"""Acanthostega Beta 4 · Held ResourceObject ↔ terrain mechanical transmission V1.

Mechanism: held_resource_object_terrain_mechanical_transmission
Preset: ACANTHOSTEGA_BETA4_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION

Bounded ABSTRACT_BOUNDED_ACTUATOR_V1 effort → rigid grasp → held sphere/lower-face
terrain constraint → clipped relative_z → one work_used → transmitted-work partition.

NO SETMR routing, terrain failure, WMT, impulse, sound, auto-release, pressure.
Following slice: HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION_V1.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.resource_objects import PHYSICAL_STATE_HELD

MECHANISM_ID = "held_resource_object_terrain_mechanical_transmission"
PROFILE_VERSION = "HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION_PROFILE_V1"
STATE_SCHEMA = "HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION_STATE_V1"
RECEIPT_KIND = "HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION"
CONSTRAINT_KIND = "held_resource_object_terrain"

BANNER = (
    "BETA4 · HELD OBJECT ↔ TERRAIN MECHANICAL TRANSMISSION · "
    "BOUNDED ACTUATOR WORK · NO TOOL CLASS · NO PRESSURE/STRESS · "
    "NO AUTOMATIC RELEASE · TRANSMISSION ONLY · TERRAIN FAILURE COUPLING NOT ACTIVE"
)

HISTORY_LIMIT_DEFAULT = 64


@dataclass
class HeldResourceObjectTerrainMechanicalTransmissionConfig:
    enabled: bool = False
    contact_epsilon: float = 1e-9
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "contact_epsilon": float(self.contact_epsilon),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "setmr_routed": False,
            "terrain_failure_coupling": False,
            "wmt_invoked": False,
            "impulse": False,
            "sound": False,
            "automatic_release": False,
            "pressure": False,
            "stress": False,
            "object_mass_participates": False,
            "object_compliance_participates": False,
            "object_composition_participates": False,
            "semantic_tool_effectiveness": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "HeldResourceObjectTerrainMechanicalTransmissionConfig":
        d = dict(data or {})
        return cls(
            enabled=bool(d.get("enabled", False)),
            contact_epsilon=float(d.get("contact_epsilon", 1e-9)),
            history_limit=int(d.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: HeldResourceObjectTerrainMechanicalTransmissionConfig) -> None:
    if float(cfg.contact_epsilon) < 0.0:
        raise ValueError("contact_epsilon must be >= 0")
    if int(cfg.history_limit) < 1:
        raise ValueError("history_limit must be >= 1")


def held_resource_object_terrain_mechanical_transmission_is_active(config: Any) -> bool:
    cfg = getattr(config, "held_resource_object_terrain_mechanical_transmission", None)
    return cfg is not None and bool(getattr(cfg, "enabled", False))


def set_held_resource_object_terrain_mechanical_transmission(config: Any, enabled: bool) -> None:
    cur = getattr(config, "held_resource_object_terrain_mechanical_transmission", None)
    if cur is None:
        config.held_resource_object_terrain_mechanical_transmission = (
            HeldResourceObjectTerrainMechanicalTransmissionConfig(enabled=bool(enabled))
        )
    else:
        cur.enabled = bool(enabled)


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "mechanism_id": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "enabled": bool(enabled),
        "config_path": "held_resource_object_terrain_mechanical_transmission.enabled",
        "provenance": "acanthostega_held_resource_object_terrain_mechanical_transmission",
        "setmr_routed": False,
        "terrain_failure_coupling": False,
        "banner": BANNER,
    }


@dataclass
class HeldResourceObjectTerrainMechanicalTransmissionState:
    config: HeldResourceObjectTerrainMechanicalTransmissionConfig
    counters: dict[str, int] = field(default_factory=dict)
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)


def _zero_counters() -> dict[str, int]:
    return {
        "constraints_evaluated": 0,
        "held_blocks": 0,
        "transmissions": 0,
        "zero_command": 0,
        "empty_hand": 0,
    }


def state_of(world: Any) -> HeldResourceObjectTerrainMechanicalTransmissionState | None:
    raw = getattr(world, "held_resource_object_terrain_mechanical_transmission_state", None)
    return raw if isinstance(raw, HeldResourceObjectTerrainMechanicalTransmissionState) else None


def ensure_held_resource_object_terrain_mechanical_transmission_for_runtime(
    world: Any, config: Any
) -> HeldResourceObjectTerrainMechanicalTransmissionState | None:
    if not held_resource_object_terrain_mechanical_transmission_is_active(config):
        if hasattr(world, "held_resource_object_terrain_mechanical_transmission_state"):
            world.held_resource_object_terrain_mechanical_transmission_state = None
        return None
    raw_cfg = getattr(config, "held_resource_object_terrain_mechanical_transmission", None)
    cfg = (
        raw_cfg
        if isinstance(raw_cfg, HeldResourceObjectTerrainMechanicalTransmissionConfig)
        else HeldResourceObjectTerrainMechanicalTransmissionConfig.from_dict(
            raw_cfg.to_dict() if raw_cfg is not None and hasattr(raw_cfg, "to_dict") else None
        )
    )
    validate_config(cfg)
    st = state_of(world)
    if st is None:
        st = HeldResourceObjectTerrainMechanicalTransmissionState(
            config=cfg, counters=_zero_counters()
        )
        world.held_resource_object_terrain_mechanical_transmission_state = st
    else:
        st.config = cfg
    return st


def serialize_state(
    st: HeldResourceObjectTerrainMechanicalTransmissionState | None,
) -> dict[str, Any] | None:
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
        "setmr_routed": False,
        "terrain_failure_coupling": False,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> HeldResourceObjectTerrainMechanicalTransmissionState | None:
    if not held_resource_object_terrain_mechanical_transmission_is_active(config):
        world.held_resource_object_terrain_mechanical_transmission_state = None
        return None
    if not data:
        return ensure_held_resource_object_terrain_mechanical_transmission_for_runtime(world, config)
    cfg = HeldResourceObjectTerrainMechanicalTransmissionConfig.from_dict(
        data.get("config") if isinstance(data.get("config"), dict) else None
    )
    validate_config(cfg)
    st = HeldResourceObjectTerrainMechanicalTransmissionState(
        config=cfg,
        counters={**_zero_counters(), **{a: int(b) for a, b in (data.get("counters") or {}).items()}},
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else None,
        history=[dict(r) for r in (data.get("history") or [])],
    )
    world.held_resource_object_terrain_mechanical_transmission_state = st
    return st


def find_held_object_for_effector(world: Any, body_id: str, effector_id: str) -> Any | None:
    hid = str(body_id)
    mid = str(effector_id)
    hits: list[Any] = []
    for obj in list(getattr(world, "resource_objects", None) or []):
        if str(getattr(obj, "physical_state", "")) != PHYSICAL_STATE_HELD:
            continue
        if str(getattr(obj, "holder_body_id", "") or "") != hid:
            continue
        if str(getattr(obj, "manipulator_id", "") or "") != mid:
            continue
        hits.append(obj)
    if not hits:
        return None
    hits.sort(key=lambda o: str(getattr(o, "object_id", "") or ""))
    return hits[0]


@dataclass
class HeldObjectTerrainRelativeZConstraint:
    """Held ResourceObject lower-support / sphere vs CSG height as relative_z constraint.

    Active only when mechanical transmission mechanism is ON and the effector holds
    an object. Empty hand → full admit (tip constraint remains authoritative).
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
    ):
        from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
            ExternalConstraintResponse,
        )
        from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
            effector_world_pose,
            sample_terrain_at,
        )
        from mechanistic_mind.physical_system.flat_ground_gravity import (
            flat_ground_gravity_is_active,
            read_z,
        )

        if not held_resource_object_terrain_mechanical_transmission_is_active(config):
            return ExternalConstraintResponse(
                admitted_delta=float(proposed_delta),
                blocked_delta=0.0,
                opposing=False,
                constraint_kind="none",
            )

        st = ensure_held_resource_object_terrain_mechanical_transmission_for_runtime(world, config)
        if st is not None:
            st.counters["constraints_evaluated"] = int(st.counters.get("constraints_evaluated", 0)) + 1

        obj = find_held_object_for_effector(world, body_id, effector_id)
        if obj is None:
            if st is not None:
                st.counters["empty_hand"] = int(st.counters.get("empty_hand", 0)) + 1
            return ExternalConstraintResponse(
                admitted_delta=float(proposed_delta),
                blocked_delta=0.0,
                opposing=False,
                constraint_kind="none",
            )

        w = int(world.T.shape[1])
        h = int(world.T.shape[0])
        ex, ey, _ez = effector_world_pose(
            body,
            width=w,
            height=h,
            config=config,
            manipulator_id=str(effector_id),
            runtime=runtime,
            world=world,
            body_id=str(body_id),
        )
        # Authoritative grasp xy = effector; lower support z = body.z + relative_z (+offset).
        offset = 0.0
        if flat_ground_gravity_is_active(config):
            fgg = getattr(config, "flat_ground_gravity", None)
            offset = float(getattr(fgg, "held_vertical_offset", 0.0) or 0.0)
        body_z = float(read_z(body)) if flat_ground_gravity_is_active(config) else float(
            getattr(body, "z", 0.0) or 0.0
        )
        held_z_before = float(body_z + offset + float(relative_z_before))
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
                world, ex, ey, float(held_z_before), radius=0.0, config=config
            )
        else:
            terrain = sample_terrain_at(world, ex, ey, config=config)
        surface_h = float(terrain["height"])
        nx = float(terrain["normal_x"])
        ny = float(terrain["normal_y"])
        nz = float(terrain["normal_z"])
        eps = float(self.epsilon)
        cfg_eps = getattr(
            getattr(config, "held_resource_object_terrain_mechanical_transmission", None),
            "contact_epsilon",
            None,
        )
        if cfg_eps is not None:
            eps = float(cfg_eps)
        if use_vw5 and not math.isfinite(surface_h):
            from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
                ExternalConstraintResponse,
            )

            return ExternalConstraintResponse(
                admitted_delta=float(proposed_delta),
                blocked_delta=0.0,
                opposing=False,
                constraint_kind=CONSTRAINT_KIND,
                normal=(nx, ny, nz),
                surface_height=None,
                toi=1.0,
                inward_normal_component=0.0,
                clearance_before=float("inf"),
                episode_hint=str(getattr(obj, "object_id", "") or "") or None,
            )
        # Lower-support nonpenetration: held_z >= surface_h - eps
        # held_z = body_z + offset + relative_z  ⇒  relative_z >= surface_h - body_z - offset
        z_min_rel = float(surface_h) - float(body_z) - float(offset)
        clr_before = float(held_z_before) - float(surface_h)
        prop = float(proposed_delta)
        oid = str(getattr(obj, "object_id", "") or "")

        if prop >= -1e-15:
            return ExternalConstraintResponse(
                admitted_delta=prop,
                blocked_delta=0.0,
                opposing=False,
                constraint_kind=CONSTRAINT_KIND,
                normal=(nx, ny, nz),
                contact_point=[float(ex), float(ey), float(surface_h)]
                if clr_before <= eps
                else None,
                surface_height=surface_h,
                toi=1.0,
                inward_normal_component=0.0,
                clearance_before=clr_before,
                episode_hint=oid or None,
            )

        tentative = float(relative_z_before) + prop
        if tentative >= z_min_rel - eps:
            return ExternalConstraintResponse(
                admitted_delta=prop,
                blocked_delta=0.0,
                opposing=False,
                constraint_kind=CONSTRAINT_KIND,
                normal=(nx, ny, nz),
                surface_height=surface_h,
                toi=1.0,
                inward_normal_component=0.0,
                clearance_before=clr_before,
                episode_hint=oid or None,
            )

        admitted = float(z_min_rel - float(relative_z_before))
        if admitted > 0.0:
            admitted = 0.0
        if admitted < prop:
            admitted = max(prop, admitted)
        if clr_before <= eps:
            admitted = 0.0
        blocked = float(prop - admitted)
        inward = max(0.0, -(nx * 0.0 + ny * 0.0 + nz * blocked))
        if abs(prop) > 1e-18:
            toi = float(admitted / prop) if admitted != 0.0 or abs(prop) > 0 else 0.0
            toi = max(0.0, min(1.0, toi))
        else:
            toi = 1.0
        if clr_before <= eps:
            toi = 0.0

        if st is not None and abs(blocked) > 1e-15:
            st.counters["held_blocks"] = int(st.counters.get("held_blocks", 0)) + 1

        return ExternalConstraintResponse(
            admitted_delta=float(admitted),
            blocked_delta=float(blocked),
            opposing=bool(abs(blocked) > 1e-15),
            constraint_kind=CONSTRAINT_KIND,
            normal=(nx, ny, nz),
            contact_point=[float(ex), float(ey), float(surface_h)],
            surface_height=surface_h,
            toi=float(toi),
            inward_normal_component=float(inward),
            clearance_before=clr_before,
            episode_hint=oid or None,
        )


def annotate_actuator_receipt_transmission(
    world: Any,
    *,
    config: Any,
    actuator_receipt: dict[str, Any],
) -> dict[str, Any] | None:
    """Partition work_used when held-terrain constraint won compose. No SETMR/WMT."""
    st = ensure_held_resource_object_terrain_mechanical_transmission_for_runtime(world, config)
    if st is None or not isinstance(actuator_receipt, dict):
        return None

    kind = str(actuator_receipt.get("external_constraint") or "")
    work_used = float(actuator_receipt.get("work_used") or 0.0)
    opposing = bool(actuator_receipt.get("opposing"))
    transmitted = 0.0
    if kind == CONSTRAINT_KIND and opposing and work_used > 1e-15:
        transmitted = float(work_used)
        st.counters["transmissions"] = int(st.counters.get("transmissions", 0)) + 1

    residual = float(work_used) - float(transmitted)
    if abs(residual) < 1e-12:
        residual = 0.0

    rec = {
        "receipt_kind": RECEIPT_KIND,
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "tick": actuator_receipt.get("tick"),
        "body_id": actuator_receipt.get("body_id"),
        "effector_id": actuator_receipt.get("effector_id"),
        "object_id": (
            actuator_receipt.get("episode_hint")
            or actuator_receipt.get("held_object_id")
            or None
        ),
        "external_constraint": kind,
        "opposing": opposing,
        "work_capacity": actuator_receipt.get("actuator_capacity"),
        "work_attempted": actuator_receipt.get("work_attempted"),
        "work_used": work_used,
        "work_transmitted_to_terrain": float(transmitted),
        "work_for_held_load": 0.0,
        "work_dissipated_in_constraint": float(work_used) if transmitted <= 1e-15 else float(transmitted),
        "work_partition_residual": float(residual),
        "achieved_relative_delta": actuator_receipt.get("achieved_relative_delta"),
        "externally_blocked_delta": actuator_receipt.get("externally_blocked_delta"),
        "inward_normal_component": actuator_receipt.get("inward_normal_component"),
        "contact_point": actuator_receipt.get("contact_point"),
        "surface_normal": actuator_receipt.get("surface_normal"),
        "clearance_before": actuator_receipt.get("clearance_before"),
        "toi": actuator_receipt.get("toi"),
        "mechanical_work_source": actuator_receipt.get("mechanical_work_source"),
        "setmr_routed": False,
        "terrain_failure_coupling": False,
        "material_failure": False,
        "wmt_invoked": False,
        "impulse_transferred": False,
        "sound_emitted": False,
        "automatic_release": False,
        "pressure": False,
        "stress": False,
        "object_mass_participates": False,
        "object_compliance_participates": False,
        "semantic_tool_effectiveness": False,
        "researcher_only": True,
        "cognition_exposed": False,
        "banner": BANNER,
    }
    # Prefer episode_hint from constraint response if stamped on actuator receipt.
    hint = actuator_receipt.get("episode_hint") or actuator_receipt.get("held_object_id")
    if hint:
        rec["object_id"] = str(hint)
    elif not rec.get("object_id"):
        held = find_held_object_for_effector(
            world,
            str(actuator_receipt.get("body_id") or ""),
            str(actuator_receipt.get("effector_id") or ""),
        )
        if held is not None:
            rec["object_id"] = str(getattr(held, "object_id", "") or "") or None

    actuator_receipt["held_terrain_transmission"] = {
        "work_transmitted_to_terrain": float(transmitted),
        "work_partition_residual": float(residual),
        "setmr_routed": False,
        "terrain_failure_coupling": False,
        "constraint_kind": kind,
        "object_id": rec.get("object_id"),
    }
    actuator_receipt["work_transmitted_to_terrain"] = float(transmitted)
    actuator_receipt["work_partition_residual"] = float(residual)

    st.last_step = rec
    st.history.append(
        {
            "tick": rec.get("tick"),
            "work_used": work_used,
            "work_transmitted_to_terrain": float(transmitted),
            "object_id": rec.get("object_id"),
            "status": actuator_receipt.get("status"),
        }
    )
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    world.last_held_resource_object_terrain_mechanical_transmission = rec
    return rec


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    step = st.last_step or {}
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "counters": dict(st.counters),
        "last_step": {
            "tick": step.get("tick"),
            "object_id": step.get("object_id"),
            "work_used": step.get("work_used"),
            "work_transmitted_to_terrain": step.get("work_transmitted_to_terrain"),
            "work_partition_residual": step.get("work_partition_residual"),
            "setmr_routed": False,
            "terrain_failure_coupling": False,
        },
        "setmr_routed": False,
        "terrain_failure_coupling": False,
        "researcher_only": True,
        "agent_accessible": False,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "caption": BANNER,
        "active": researcher_summary(world),
        "latest": st.last_step,
        "researcher_only": True,
        "visually_distinct_from_setmr": True,
    }
