"""Update 4.65 — Minimal passive physical exchange (WORLD → BODY initiation).

Completes the existing 4.9 env-exchange → 4.8 process_materials relation so
local env_material_field can write energy_reserve / hydration / fatigue under
WAIT without requiring physical_intake_enabled (USE acquisition).

Experimental. Default-off. No reward/value/goal/homeostasis. No Action.kind
branch. Coefficients are the existing 4.8/4.9 values; nothing was chosen from
X, N, Q, or the 0.60 hop threshold.
"""
from __future__ import annotations

from typing import Any

from .physical_intake import (
    MATERIAL_A,
    EnvExchangeParams,
    IntakeParams,
    env_exchange_params_from_body_config,
    intake_params_from_body_config,
)

# Frozen 4.8 / 4.9 numeric values (source: BodyConfig / IntakeParams / EnvExchangeParams).
FROZEN_PER_TICK_EXCHANGE_CAPACITY = 0.008
FROZEN_EXCHANGE_COEFFICIENT = 1.0
FROZEN_INTERNAL_CAPACITY = 0.20
FROZEN_PROCESSING_RATE_PER_TICK = 0.25
FROZEN_MAX_PROCESS_PER_TICK = 0.01
FROZEN_YIELDS = {
    "material_a": {"energy_delta": 0.8},
    "material_b": {"hydration_delta": 0.9},
    "material_c": {"energy_delta": 0.4, "hydration_delta": 0.4, "fatigue_delta": -0.1},
}
FROZEN_MATERIAL_ID = MATERIAL_A


def config_dict(cfg: Any) -> dict[str, Any] | None:
    raw = getattr(cfg, "passive_physical_exchange_config", None)
    return raw if isinstance(raw, dict) else None


def exchange_enabled(cfg: Any) -> bool:
    c = config_dict(cfg)
    if c is None:
        return False
    return bool(c.get("enabled", True)) and bool(c.get("exchange_enabled", True))


def processing_enabled(cfg: Any) -> bool:
    c = config_dict(cfg)
    if c is None:
        return False
    return bool(c.get("enabled", True)) and bool(c.get("processing_enabled", True))


def resolve_internal_capacity(cfg: Any) -> float:
    c = config_dict(cfg)
    if c is not None and "internal_capacity" in c:
        return float(c["internal_capacity"])
    return float(getattr(cfg, "intake_internal_capacity", FROZEN_INTERNAL_CAPACITY))


def resolve_env_exchange_params(cfg: Any) -> EnvExchangeParams:
    """Env-exchange params: 4.65 config if present, else existing 4.9 flag."""
    c = config_dict(cfg)
    if c is not None:
        return EnvExchangeParams(
            enabled=bool(c.get("enabled", True)),
            exchange_enabled=bool(c.get("exchange_enabled", True)),
            material_id=str(c.get("material_id", FROZEN_MATERIAL_ID)),
            per_tick_exchange_capacity=float(
                c.get("per_tick_exchange_capacity", FROZEN_PER_TICK_EXCHANGE_CAPACITY)
            ),
            exchange_coefficient=float(
                c.get("exchange_coefficient", FROZEN_EXCHANGE_COEFFICIENT)
            ),
        )
    return env_exchange_params_from_body_config(cfg)


def resolve_processing_params(cfg: Any) -> IntakeParams:
    """Processing yields/rates. 4.65 uses frozen 4.8 defaults; does not enable USE intake."""
    c = config_dict(cfg)
    if c is None:
        return intake_params_from_body_config(cfg)
    yields = c.get("yields")
    if not isinstance(yields, dict) or not yields:
        yields = {k: dict(v) for k, v in FROZEN_YIELDS.items()}
    return IntakeParams(
        enabled=True,
        transfer_enabled=True,
        processing_enabled=bool(c.get("processing_enabled", True)),
        per_interaction_transfer_capacity=float(
            getattr(cfg, "intake_per_interaction_capacity", 0.03)
        ),
        internal_capacity=resolve_internal_capacity(cfg),
        processing_rate_per_tick=float(
            c.get("processing_rate_per_tick", FROZEN_PROCESSING_RATE_PER_TICK)
        ),
        max_process_per_tick=float(
            c.get("max_process_per_tick", FROZEN_MAX_PROCESS_PER_TICK)
        ),
        yields={str(k): dict(v) for k, v in yields.items()},
    )


def default_enabled_config() -> dict[str, Any]:
    """Researcher-facing frozen experimental config. Not a default runtime value."""
    return {
        "enabled": True,
        "exchange_enabled": True,
        "processing_enabled": True,
        "material_id": FROZEN_MATERIAL_ID,
        "per_tick_exchange_capacity": FROZEN_PER_TICK_EXCHANGE_CAPACITY,
        "exchange_coefficient": FROZEN_EXCHANGE_COEFFICIENT,
        "internal_capacity": FROZEN_INTERNAL_CAPACITY,
        "processing_rate_per_tick": FROZEN_PROCESSING_RATE_PER_TICK,
        "max_process_per_tick": FROZEN_MAX_PROCESS_PER_TICK,
        "yields": {k: dict(v) for k, v in FROZEN_YIELDS.items()},
    }
