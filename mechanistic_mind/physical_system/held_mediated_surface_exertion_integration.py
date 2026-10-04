"""Acanthostega Beta 4 · Held-mediated surface exertion integration V1.

Mechanism: held_mediated_surface_exertion_integration
Preset: ACANTHOSTEGA_BETA4_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION

Integration only: when ON, held-terrain constraint winners route
`work_transmitted_to_terrain` into the EXISTING SETMR accumulator /
failure gate / SEPARATE_SURFACE_COLUMN_SLICE WMT.

No new transmission law, resistance law, accumulator, or removal path.
No semantic tool classes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "held_mediated_surface_exertion_integration"
PROFILE_VERSION = "HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION_PROFILE_V1"
STATE_SCHEMA = "HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION_STATE_V1"
RECEIPT_KIND = "HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION"

BANNER = (
    "BETA4 · HELD-MEDIATED SURFACE EXERTION INTEGRATION · "
    "SAME SETMR ACCUMULATOR · SAME SEPARATION WMT · "
    "NO NEW RESISTANCE LAW · NO TOOL CLASS"
)

HISTORY_LIMIT_DEFAULT = 64


@dataclass
class HeldMediatedSurfaceExertionIntegrationConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "routes_to_setmr": True,
            "duplicate_accumulator": False,
            "held_specific_removal_path": False,
            "new_transmission_law": False,
            "new_resistance_law": False,
            "semantic_tool_effectiveness": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "HeldMediatedSurfaceExertionIntegrationConfig":
        d = dict(data or {})
        return cls(
            enabled=bool(d.get("enabled", False)),
            history_limit=int(d.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: HeldMediatedSurfaceExertionIntegrationConfig) -> None:
    if int(cfg.history_limit) < 1:
        raise ValueError("history_limit must be >= 1")


def held_mediated_surface_exertion_integration_is_active(config: Any) -> bool:
    cfg = getattr(config, "held_mediated_surface_exertion_integration", None)
    return cfg is not None and bool(getattr(cfg, "enabled", False))


def set_held_mediated_surface_exertion_integration(config: Any, enabled: bool) -> None:
    cur = getattr(config, "held_mediated_surface_exertion_integration", None)
    if cur is None:
        config.held_mediated_surface_exertion_integration = (
            HeldMediatedSurfaceExertionIntegrationConfig(enabled=bool(enabled))
        )
    else:
        cur.enabled = bool(enabled)


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "mechanism_id": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "enabled": bool(enabled),
        "config_path": "held_mediated_surface_exertion_integration.enabled",
        "provenance": "acanthostega_held_mediated_surface_exertion_integration",
        "routes_to_setmr": True,
        "duplicate_accumulator": False,
        "banner": BANNER,
    }


@dataclass
class HeldMediatedSurfaceExertionIntegrationState:
    config: HeldMediatedSurfaceExertionIntegrationConfig
    counters: dict[str, int] = field(default_factory=dict)
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)


def _zero_counters() -> dict[str, int]:
    return {
        "routes_evaluated": 0,
        "held_routes": 0,
        "tip_passthrough": 0,
        "setmr_invoked": 0,
        "zero_transmitted": 0,
    }


def state_of(world: Any) -> HeldMediatedSurfaceExertionIntegrationState | None:
    raw = getattr(world, "held_mediated_surface_exertion_integration_state", None)
    return raw if isinstance(raw, HeldMediatedSurfaceExertionIntegrationState) else None


def ensure_held_mediated_surface_exertion_integration_for_runtime(
    world: Any, config: Any
) -> HeldMediatedSurfaceExertionIntegrationState | None:
    if not held_mediated_surface_exertion_integration_is_active(config):
        if hasattr(world, "held_mediated_surface_exertion_integration_state"):
            world.held_mediated_surface_exertion_integration_state = None
        return None
    raw_cfg = getattr(config, "held_mediated_surface_exertion_integration", None)
    cfg = (
        raw_cfg
        if isinstance(raw_cfg, HeldMediatedSurfaceExertionIntegrationConfig)
        else HeldMediatedSurfaceExertionIntegrationConfig.from_dict(
            raw_cfg.to_dict() if raw_cfg is not None and hasattr(raw_cfg, "to_dict") else None
        )
    )
    validate_config(cfg)
    st = state_of(world)
    if st is None:
        st = HeldMediatedSurfaceExertionIntegrationState(config=cfg, counters=_zero_counters())
        world.held_mediated_surface_exertion_integration_state = st
    else:
        st.config = cfg
    return st


def serialize_state(
    st: HeldMediatedSurfaceExertionIntegrationState | None,
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
        "routes_to_setmr": True,
        "duplicate_accumulator": False,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> HeldMediatedSurfaceExertionIntegrationState | None:
    if not held_mediated_surface_exertion_integration_is_active(config):
        world.held_mediated_surface_exertion_integration_state = None
        return None
    if not data:
        return ensure_held_mediated_surface_exertion_integration_for_runtime(world, config)
    cfg = HeldMediatedSurfaceExertionIntegrationConfig.from_dict(
        data.get("config") if isinstance(data.get("config"), dict) else None
    )
    validate_config(cfg)
    st = HeldMediatedSurfaceExertionIntegrationState(
        config=cfg,
        counters={**_zero_counters(), **{a: int(b) for a, b in (data.get("counters") or {}).items()}},
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else None,
        history=[dict(r) for r in (data.get("history") or [])],
    )
    world.held_mediated_surface_exertion_integration_state = st
    return st


def record_setmr_route(
    world: Any,
    *,
    config: Any,
    actuator_receipt: dict[str, Any],
    material_receipt: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Annotate transmission + integration receipts after SETMR consume."""
    st = ensure_held_mediated_surface_exertion_integration_for_runtime(world, config)
    if st is None or not isinstance(actuator_receipt, dict):
        return None

    from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
        CONSTRAINT_KIND as HELD_KIND,
    )

    st.counters["routes_evaluated"] = int(st.counters.get("routes_evaluated", 0)) + 1
    kind = str(actuator_receipt.get("external_constraint") or "")
    transmitted = float(
        actuator_receipt.get("work_transmitted_to_terrain")
        or (
            actuator_receipt.get("held_terrain_transmission") or {}
        ).get("work_transmitted_to_terrain")
        or 0.0
    )
    routed = False
    if kind == HELD_KIND:
        st.counters["held_routes"] = int(st.counters.get("held_routes", 0)) + 1
        if transmitted <= 1e-15:
            st.counters["zero_transmitted"] = int(st.counters.get("zero_transmitted", 0)) + 1
        if isinstance(material_receipt, dict) and float(
            material_receipt.get("eligible_work") or 0.0
        ) > 1e-15:
            routed = True
            st.counters["setmr_invoked"] = int(st.counters.get("setmr_invoked", 0)) + 1
    else:
        st.counters["tip_passthrough"] = int(st.counters.get("tip_passthrough", 0)) + 1

    rec = {
        "receipt_kind": RECEIPT_KIND,
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "tick": actuator_receipt.get("tick"),
        "body_id": actuator_receipt.get("body_id"),
        "effector_id": actuator_receipt.get("effector_id"),
        "object_id": actuator_receipt.get("held_object_id")
        or actuator_receipt.get("episode_hint"),
        "external_constraint": kind,
        "work_used": actuator_receipt.get("work_used"),
        "work_transmitted_to_terrain": transmitted,
        "eligible_material_work": (
            (material_receipt or {}).get("eligible_work") if material_receipt else 0.0
        ),
        "setmr_routed": bool(routed),
        "material_loading_status": (material_receipt or {}).get("status"),
        "material_failure": bool((material_receipt or {}).get("failure")),
        "wmt_invoked": bool((material_receipt or {}).get("wmt_invoked")),
        "same_accumulator": True,
        "same_wmt_path": True,
        "duplicate_accumulator": False,
        "held_specific_removal_path": False,
        "semantic_tool_effectiveness": False,
        "researcher_only": True,
        "cognition_exposed": False,
        "banner": BANNER,
    }

    # Propagate onto transmission partition stamp.
    ht = actuator_receipt.get("held_terrain_transmission")
    if isinstance(ht, dict):
        ht["setmr_routed"] = bool(routed)
        ht["terrain_failure_coupling"] = bool((material_receipt or {}).get("failure"))
    actuator_receipt["setmr_routed_held"] = bool(routed)

    tx = getattr(world, "last_held_resource_object_terrain_mechanical_transmission", None)
    if isinstance(tx, dict) and kind == HELD_KIND:
        tx["setmr_routed"] = bool(routed)
        tx["terrain_failure_coupling"] = bool((material_receipt or {}).get("failure"))
        tx["wmt_invoked"] = bool((material_receipt or {}).get("wmt_invoked"))
        tx["material_failure"] = bool((material_receipt or {}).get("failure"))

    st.last_step = rec
    st.history.append(
        {
            "tick": rec.get("tick"),
            "setmr_routed": bool(routed),
            "work_transmitted_to_terrain": transmitted,
            "material_loading_status": rec.get("material_loading_status"),
        }
    )
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    world.last_held_mediated_surface_exertion_integration = rec
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
            "setmr_routed": step.get("setmr_routed"),
            "work_transmitted_to_terrain": step.get("work_transmitted_to_terrain"),
            "material_loading_status": step.get("material_loading_status"),
            "material_failure": step.get("material_failure"),
            "wmt_invoked": step.get("wmt_invoked"),
        },
        "routes_to_setmr": True,
        "duplicate_accumulator": False,
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
        "visually_distinct_from_bare_setmr": True,
    }
