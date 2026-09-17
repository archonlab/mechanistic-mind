"""Update 4.8 — Bounded physical intake × delayed internal processing.

Physical organism mechanism only. No food/eat/hunger semantics.
No positive value for acquisition or processing.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


# Nonsemantic material identifiers.
MATERIAL_A = "material_a"
MATERIAL_B = "material_b"
MATERIAL_C = "material_c"

# Body-effect keys that qualify an object for intake redirection when enabled.
REPLENISHING_KEYS = (
    "energy_delta",
    "hydration_delta",
    "metabolic_energy_intake",
    "fatigue_delta",
)


@dataclass(slots=True)
class IntakeParams:
    """Physical parameters for transfer + processing (not cognition)."""

    enabled: bool = True
    transfer_enabled: bool = True
    processing_enabled: bool = True
    per_interaction_transfer_capacity: float = 0.03
    internal_capacity: float = 0.20
    # Fraction of stored material processed per tick (bounded).
    processing_rate_per_tick: float = 0.25
    # Max absolute material processed per tick.
    max_process_per_tick: float = 0.01
    # Map material_id -> body delta yields per unit material processed.
    # Defaults map material_a→energy, material_b→hydration, material_c→mixed.
    yields: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            MATERIAL_A: {"energy_delta": 0.8},
            MATERIAL_B: {"hydration_delta": 0.9},
            MATERIAL_C: {"energy_delta": 0.4, "hydration_delta": 0.4, "fatigue_delta": -0.1},
        }
    )

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe snapshot for world logs / reset contracts."""
        return {
            "enabled": bool(self.enabled),
            "transfer_enabled": bool(self.transfer_enabled),
            "processing_enabled": bool(self.processing_enabled),
            "per_interaction_transfer_capacity": float(self.per_interaction_transfer_capacity),
            "internal_capacity": float(self.internal_capacity),
            "processing_rate_per_tick": float(self.processing_rate_per_tick),
            "max_process_per_tick": float(self.max_process_per_tick),
            "yields": {
                str(mat): {str(k): float(v) for k, v in (deltas or {}).items()}
                for mat, deltas in (self.yields or {}).items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "IntakeParams":
        if not data:
            return cls()
        kwargs: dict[str, Any] = {}
        for key in cls.__dataclass_fields__:
            if key not in data:
                continue
            if key == "yields":
                raw = data.get("yields") or {}
                kwargs["yields"] = {
                    str(mat): {str(k): float(v) for k, v in (deltas or {}).items()}
                    for mat, deltas in raw.items()
                }
            else:
                kwargs[key] = data[key]
        return cls(**kwargs)


def coerce_intake_params(value: Any) -> IntakeParams:
    """Accept IntakeParams or a to_dict payload (world logs must stay JSON-safe)."""
    if isinstance(value, IntakeParams):
        return value
    if isinstance(value, dict):
        return IntakeParams.from_dict(value)
    return IntakeParams()


def internal_total(materials: dict[str, float] | None) -> float:
    if not materials:
        return 0.0
    return float(sum(max(0.0, float(v)) for v in materials.values()))


def remaining_capacity(materials: dict[str, float] | None, capacity: float) -> float:
    return max(0.0, float(capacity) - internal_total(materials))


def object_uses_intake(record: dict[str, Any], params: IntakeParams) -> bool:
    if not params.enabled:
        return False
    if bool(record.get("intake_enabled", False)):
        return True
    tm = record.get("transferable_materials")
    if isinstance(tm, dict) and tm:
        return True
    # Auto: finite reservoir objects with any numeric body_effects become
    # intake-compatible (deferred processing instead of immediate effect).
    if record.get("effect_scale_state") not in {"quantity", "durability"}:
        return False
    effects = record.get("body_effects") or {}
    if not isinstance(effects, dict):
        return False
    return any(isinstance(v, (int, float)) and float(v) != 0.0 for v in effects.values())


def material_composition(record: dict[str, Any]) -> dict[str, float]:
    """Derive nonsemantic material mix from object record."""
    explicit = record.get("transferable_materials")
    if isinstance(explicit, dict) and explicit:
        out = {
            str(k): max(0.0, float(v))
            for k, v in explicit.items()
            if isinstance(v, (int, float))
        }
        total = sum(out.values()) or 1.0
        return {k: v / total for k, v in out.items()}
    effects = record.get("body_effects") or {}
    if not isinstance(effects, dict):
        return {MATERIAL_A: 1.0}
    energy = float(effects.get("energy_delta", 0.0) or 0.0)
    hydr = float(effects.get("hydration_delta", 0.0) or 0.0)
    meta = float(effects.get("metabolic_energy_intake", 0.0) or 0.0)
    fat = float(effects.get("fatigue_delta", 0.0) or 0.0)
    # Positive replenishing-like components only for composition weights.
    weights = {
        MATERIAL_A: max(0.0, energy) + max(0.0, meta),
        MATERIAL_B: max(0.0, hydr),
        MATERIAL_C: max(0.0, -fat),  # fatigue reduction → material_c
    }
    total = sum(weights.values())
    if total <= 1e-12:
        return {MATERIAL_A: 1.0}
    return {k: v / total for k, v in weights.items() if v > 0}


def compute_transfer(
    *,
    requested: float,
    object_available: float,
    per_interaction_cap: float,
    organism_remaining_cap: float,
    transfer_enabled: bool,
) -> dict[str, Any]:
    if not transfer_enabled:
        return {
            "requested": float(requested),
            "accepted": 0.0,
            "capacity_limited": False,
            "transfer_ablated": True,
            "reason": "TRANSFER_ABLATED",
        }
    req = max(0.0, float(requested))
    avail = max(0.0, float(object_available))
    per = max(0.0, float(per_interaction_cap))
    rem = max(0.0, float(organism_remaining_cap))
    accepted = min(req, avail, per, rem)
    return {
        "requested": req,
        "accepted": float(accepted),
        "object_available": avail,
        "per_interaction_cap": per,
        "organism_remaining_cap": rem,
        "capacity_limited": rem + 1e-12 < min(req, avail, per),
        "transfer_ablated": False,
        "reason": None if accepted > 0 else "ZERO_ACCEPTED",
    }


def apply_transfer_to_materials(
    materials: dict[str, float],
    *,
    accepted: float,
    composition: dict[str, float],
) -> dict[str, float]:
    next_m = {k: float(v) for k, v in materials.items()}
    for mat, weight in composition.items():
        next_m[mat] = float(next_m.get(mat, 0.0)) + float(accepted) * float(weight)
    return next_m


def process_materials(
    materials: dict[str, float],
    *,
    params: IntakeParams,
) -> tuple[dict[str, float], dict[str, float], float]:
    """Return (next_materials, body_deltas, processed_amount)."""
    if not params.processing_enabled:
        return deepcopy(materials), {}, 0.0
    total = internal_total(materials)
    if total <= 1e-12:
        return deepcopy(materials), {}, 0.0
    target = min(
        params.max_process_per_tick,
        total * float(params.processing_rate_per_tick),
        total,
    )
    if target <= 1e-12:
        return deepcopy(materials), {}, 0.0
    next_m = {k: float(v) for k, v in materials.items()}
    body: dict[str, float] = {}
    processed = 0.0
    # Process proportionally across materials.
    for mat, amount in list(next_m.items()):
        if amount <= 0:
            continue
        share = amount / total
        take = min(amount, target * share)
        if take <= 0:
            continue
        next_m[mat] = amount - take
        processed += take
        yields = params.yields.get(mat) or {}
        for k, y in yields.items():
            body[k] = float(body.get(k, 0.0)) + float(y) * take
    # Drop near-zeros
    next_m = {k: v for k, v in next_m.items() if v > 1e-12}
    return next_m, body, float(processed)



def apply_bounded_object_intake(
    record: dict[str, Any],
    *,
    params: IntakeParams,
    internal_materials: dict[str, float] | None,
) -> dict[str, Any]:
    """Shared physical object→organism transfer (Update 4.8 equations).

    Eligibility to *call* this function is decided by the caller (USE or
    geometric contact). This function does not inspect Action.kind, scores,
    goals, BODY need, object names, or object IDs except via the record dict
    fields required for quantity/composition.
    Mutates record["quantity"] when accepted > 0.
    """
    if not object_uses_intake(record, params):
        return {
            "applied": False,
            "accepted": 0.0,
            "intake_transfer": {},
            "reason": "OBJECT_NOT_INTAKE_ELIGIBLE",
            "transfer": None,
            "composition": {},
        }
    try:
        qty = float(record.get("quantity", 0.0) or 0.0)
    except Exception:
        qty = 0.0
    rem = remaining_capacity(internal_materials or {}, params.internal_capacity)
    tr = compute_transfer(
        requested=float(params.per_interaction_transfer_capacity),
        object_available=qty,
        per_interaction_cap=float(params.per_interaction_transfer_capacity),
        organism_remaining_cap=rem,
        transfer_enabled=bool(params.transfer_enabled),
    )
    accepted = float(tr["accepted"])
    composition = material_composition(record)
    intake_transfer = {
        mat: accepted * float(weight)
        for mat, weight in composition.items()
        if float(weight) > 0.0 and accepted > 0.0
    }
    if accepted > 0.0:
        record["quantity"] = max(0.0, qty - accepted)
    return {
        "applied": True,
        "accepted": accepted,
        "intake_transfer": intake_transfer,
        "reason": tr.get("reason"),
        "transfer": tr,
        "composition": composition,
    }


def same_cell_contact(
    agent_position: tuple[int, int] | list[int] | None,
    object_position: tuple[int, int] | list[int] | None,
) -> bool:
    """Source-grounded geometric contact: identical discrete cell."""
    if agent_position is None or object_position is None:
        return False
    try:
        return (int(agent_position[0]), int(agent_position[1])) == (
            int(object_position[0]),
            int(object_position[1]),
        )
    except Exception:
        return False


def contact_material_transfer_enabled(cfg: Any) -> bool:
    """PHYS-4.76-E1A experimental switch; default OFF when config is None."""
    conf = getattr(cfg, "contact_material_transfer_config", None)
    if conf is None:
        return False
    if isinstance(conf, dict):
        return bool(conf.get("enabled", False))
    return False


def merge_intake_transfer(
    destination: dict[str, Any],
    intake_transfer: dict[str, float],
) -> None:
    """Merge material maps into external_body_effects["intake_transfer"]."""
    if not intake_transfer:
        return
    existing = destination.get("intake_transfer")
    if not isinstance(existing, dict):
        existing = {}
    merged = {str(k): float(v) for k, v in existing.items()}
    for mat, amt in intake_transfer.items():
        if isinstance(amt, (int, float)) and float(amt) > 0.0:
            merged[str(mat)] = float(merged.get(str(mat), 0.0)) + float(amt)
    destination["intake_transfer"] = merged



def intake_params_from_body_config(cfg: Any) -> IntakeParams:
    return IntakeParams(
        enabled=bool(getattr(cfg, "physical_intake_enabled", False)),
        transfer_enabled=bool(getattr(cfg, "intake_transfer_enabled", True)),
        processing_enabled=bool(getattr(cfg, "intake_processing_enabled", True)),
        per_interaction_transfer_capacity=float(
            getattr(cfg, "intake_per_interaction_capacity", 0.03)
        ),
        internal_capacity=float(getattr(cfg, "intake_internal_capacity", 0.20)),
        processing_rate_per_tick=float(
            getattr(cfg, "intake_processing_rate_per_tick", 0.25)
        ),
        max_process_per_tick=float(getattr(cfg, "intake_max_process_per_tick", 0.01)),
    )


@dataclass(slots=True)
class EnvExchangeParams:
    """Update 4.9 — continuous local world→organism exchange (boundary-maintained)."""

    enabled: bool = False
    exchange_enabled: bool = True  # ablation switch
    material_id: str = MATERIAL_A
    per_tick_exchange_capacity: float = 0.008
    # Multiplier on local availability [0,1] → requested transfer.
    exchange_coefficient: float = 1.0


def env_exchange_params_from_body_config(cfg: Any) -> EnvExchangeParams:
    return EnvExchangeParams(
        enabled=bool(getattr(cfg, "env_exchange_enabled", False)),
        exchange_enabled=bool(getattr(cfg, "env_exchange_transfer_enabled", True)),
        material_id=str(getattr(cfg, "env_exchange_material_id", MATERIAL_A)),
        per_tick_exchange_capacity=float(
            getattr(cfg, "env_exchange_per_tick_capacity", 0.008)
        ),
        exchange_coefficient=float(getattr(cfg, "env_exchange_coefficient", 1.0)),
    )


def local_material_availability(
    world_truth: dict[str, Any],
    position: tuple[int, int] | list[int],
    *,
    material_id: str = MATERIAL_A,
) -> float:
    """Read maintained local availability in [0,1]. Boundary condition, not organism-created."""
    field = world_truth.get("env_material_field") or {}
    if not isinstance(field, dict):
        return 0.0
    key = f"{int(position[0])},{int(position[1])}"
    # Support nested {material_id: {pos: val}} or flat {pos: val} for material_a
    if material_id in field and isinstance(field[material_id], dict):
        raw = field[material_id].get(key, 0.0)
    else:
        raw = field.get(key, 0.0)
    try:
        return max(0.0, min(1.0, float(raw)))
    except Exception:
        return 0.0


def compute_environmental_exchange(
    *,
    availability: float,
    organism_remaining_cap: float,
    params: EnvExchangeParams,
) -> dict[str, Any]:
    if not params.enabled or not params.exchange_enabled:
        return {
            "requested": 0.0,
            "accepted": 0.0,
            "availability": float(availability),
            "ablated": not params.exchange_enabled,
            "reason": "EXCHANGE_DISABLED" if params.enabled else "ENV_EXCHANGE_OFF",
        }
    avail = max(0.0, min(1.0, float(availability)))
    requested = (
        avail
        * float(params.exchange_coefficient)
        * float(params.per_tick_exchange_capacity)
    )
    accepted = min(
        requested,
        float(params.per_tick_exchange_capacity),
        max(0.0, float(organism_remaining_cap)),
    )
    return {
        "requested": float(requested),
        "accepted": float(accepted),
        "availability": avail,
        "ablated": False,
        "material_id": params.material_id,
        "capacity_limited": organism_remaining_cap + 1e-12 < requested,
        "reason": None if accepted > 0 else "ZERO_ACCEPTED",
    }


def build_uniform_field(
    width: int,
    height: int,
    value: float,
) -> dict[str, float]:
    v = max(0.0, min(1.0, float(value)))
    return {f"{x},{y}": v for y in range(height) for x in range(width)}


def build_split_field(
    width: int,
    height: int,
    *,
    high_value: float = 1.0,
    low_value: float = 0.0,
    split_x: int | None = None,
) -> dict[str, float]:
    """Left region high availability, right region low (Observer description only)."""
    sx = width // 2 if split_x is None else int(split_x)
    hi = max(0.0, min(1.0, float(high_value)))
    lo = max(0.0, min(1.0, float(low_value)))
    out: dict[str, float] = {}
    for y in range(height):
        for x in range(width):
            out[f"{x},{y}"] = hi if x < sx else lo
    return out

