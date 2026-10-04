"""Acanthostega Beta 4 · Surface exertion / terrain material resistance (V1).

Mechanism: surface_exertion_terrain_material_resistance
Preset: ACANTHOSTEGA_BETA4_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE

Consumes authoritative EFFECTOR_ACTUATOR_EFFORT receipts (work_used against
terrain). Applies composition-derived separation_work_per_quantity. Accumulates
irreversible fracture work per cell. On threshold, invokes the SAME existing
SEPARATE_SURFACE_COLUMN_SLICE WMT — no second removal path.

No DIG / EXCAVATE / pressure / stress / contact area / tip mass.
Cognition does not see resistance internals.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
    DEFAULT_MAX_WORK_PER_TICK,
)
from mechanistic_mind.physical_system.passive_material_properties import (
    SEPARATION_WORK_PER_QUANTITY_V1,
    derive_separation_work_per_quantity,
)

MECHANISM_ID = "surface_exertion_terrain_material_resistance"
PROFILE_VERSION = "SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE_PROFILE_V1"
STATE_SCHEMA = "SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE_STATE_V1"
RECEIPT_KIND = "SURFACE_MATERIAL_LOADING"
EVENT_LOAD = "SURFACE_MATERIAL_LOAD"
EVENT_FAILURE = "SURFACE_MATERIAL_FAILURE"

FAILURE_MODEL = "ACCUMULATED_IRREVERSIBLE_FRACTURE_WORK_V1"
ACCUMULATED_STATE_NAME = "accumulated_fracture_work"
MECHANICAL_INPUT = "actuator_receipt.work_used"
EXCESS_WORK_POLICY = "REMAIN_ACCUMULATED_AT_CELL"
SAME_TICK_ORDER = "stable_sort_body_id_effector_id_then_refresh_column"

# Minimum detachable thickness quantum (within WMT max 0.25).
DEFAULT_MIN_SEPARATION_THICKNESS = 0.05
DEFAULT_MAX_WMT_THICKNESS = 0.25
HISTORY_LIMIT_DEFAULT = 64

BANNER = (
    "BETA4 · SURFACE EXERTION / TERRAIN MATERIAL RESISTANCE V1 · "
    "WORK-BASED FAILURE · EXISTING SEPARATION WMT ONLY · NO DIG"
)


@dataclass
class SurfaceExertionTerrainMaterialResistanceConfig:
    """Fresh default OFF. Missing snapshot → mechanism OFF."""

    enabled: bool = False
    min_separation_thickness: float = DEFAULT_MIN_SEPARATION_THICKNESS
    max_wmt_thickness: float = DEFAULT_MAX_WMT_THICKNESS
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "min_separation_thickness": float(self.min_separation_thickness),
            "max_wmt_thickness": float(self.max_wmt_thickness),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "failure_model": FAILURE_MODEL,
            "mechanical_input": MECHANICAL_INPUT,
            "excess_work_policy": EXCESS_WORK_POLICY,
            "contact_area": False,
            "pressure": False,
            "stress": False,
            "dig_action": False,
            "semantic_soil_classes": False,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None
    ) -> "SurfaceExertionTerrainMaterialResistanceConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown surface exertion profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            min_separation_thickness=float(
                data.get("min_separation_thickness", DEFAULT_MIN_SEPARATION_THICKNESS)
            ),
            max_wmt_thickness=float(
                data.get("max_wmt_thickness", DEFAULT_MAX_WMT_THICKNESS)
            ),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: SurfaceExertionTerrainMaterialResistanceConfig) -> None:
    if float(cfg.min_separation_thickness) < 0.0:
        raise ValueError("min_separation_thickness must be >= 0")
    if float(cfg.max_wmt_thickness) <= 0.0:
        raise ValueError("max_wmt_thickness must be > 0")


def surface_exertion_terrain_material_resistance_is_active(config: Any) -> bool:
    cfg = getattr(config, "surface_exertion_terrain_material_resistance", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_surface_exertion_terrain_material_resistance(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "surface_exertion_terrain_material_resistance", None)
    if cur is None:
        config.surface_exertion_terrain_material_resistance = (
            SurfaceExertionTerrainMaterialResistanceConfig(enabled=on)
        )
    else:
        cur.enabled = on


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "SURFACE EXERTION TERRAIN MATERIAL RESISTANCE",
        "config_path": "surface_exertion_terrain_material_resistance.enabled",
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "provenance": "acanthostega_surface_exertion_terrain_material_resistance",
        "banner": BANNER,
        "failure_model": FAILURE_MODEL,
        "cognition_exposed": False,
        "dig_action": False,
        "contact_area": False,
    }


@dataclass
class SurfaceExertionTerrainMaterialResistanceState:
    config: SurfaceExertionTerrainMaterialResistanceConfig
    # key = "cx|cy" → accumulated irreversible fracture work
    fracture_work: dict[str, float] = field(default_factory=dict)
    # researcher/test calibration overrides (not agent-accessible)
    resistance_override: dict[str, float] = field(default_factory=dict)
    last_step: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


def _zero_counters() -> dict[str, int]:
    return {
        "loads": 0,
        "zero_eligible": 0,
        "subthreshold": 0,
        "failures": 0,
        "wmt_commits": 0,
        "wmt_rejects": 0,
    }


def state_of(world: Any) -> SurfaceExertionTerrainMaterialResistanceState | None:
    raw = getattr(world, "surface_exertion_terrain_material_resistance_state", None)
    return raw if isinstance(raw, SurfaceExertionTerrainMaterialResistanceState) else None


def ensure_surface_exertion_terrain_material_resistance_for_runtime(
    world: Any, config: Any
) -> SurfaceExertionTerrainMaterialResistanceState | None:
    if not surface_exertion_terrain_material_resistance_is_active(config):
        if hasattr(world, "surface_exertion_terrain_material_resistance_state"):
            world.surface_exertion_terrain_material_resistance_state = None
        return None
    raw_cfg = getattr(config, "surface_exertion_terrain_material_resistance", None)
    cfg = (
        raw_cfg
        if isinstance(raw_cfg, SurfaceExertionTerrainMaterialResistanceConfig)
        else SurfaceExertionTerrainMaterialResistanceConfig.from_dict(
            raw_cfg.to_dict() if raw_cfg is not None and hasattr(raw_cfg, "to_dict") else None
        )
    )
    validate_config(cfg)
    st = state_of(world)
    if st is None:
        st = SurfaceExertionTerrainMaterialResistanceState(
            config=cfg, counters=_zero_counters()
        )
        world.surface_exertion_terrain_material_resistance_state = st
    else:
        st.config = cfg
    return st


def serialize_state(
    st: SurfaceExertionTerrainMaterialResistanceState | None,
) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "fracture_work": {k: float(v) for k, v in sorted(st.fracture_work.items())},
        "resistance_override": {
            k: float(v) for k, v in sorted(st.resistance_override.items())
        },
        "counters": dict(st.counters),
        "last_step": dict(st.last_step) if st.last_step else None,
        "history": list(st.history),
        "banner": BANNER,
        "researcher_only": True,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> SurfaceExertionTerrainMaterialResistanceState | None:
    if not surface_exertion_terrain_material_resistance_is_active(config):
        world.surface_exertion_terrain_material_resistance_state = None
        return None
    if not data:
        return ensure_surface_exertion_terrain_material_resistance_for_runtime(world, config)
    cfg = SurfaceExertionTerrainMaterialResistanceConfig.from_dict(
        data.get("config") if isinstance(data.get("config"), dict) else None
    )
    validate_config(cfg)
    st = SurfaceExertionTerrainMaterialResistanceState(
        config=cfg,
        fracture_work={
            str(k): float(v) for k, v in (data.get("fracture_work") or {}).items()
        },
        resistance_override={
            str(k): float(v) for k, v in (data.get("resistance_override") or {}).items()
        },
        counters={
            **_zero_counters(),
            **{a: int(b) for a, b in (data.get("counters") or {}).items()},
        },
        last_step=dict(data["last_step"]) if isinstance(data.get("last_step"), dict) else None,
        history=[dict(r) for r in (data.get("history") or [])],
    )
    world.surface_exertion_terrain_material_resistance_state = st
    return st


def _cell_key(cx: int, cy: int) -> str:
    return f"{int(cx)}|{int(cy)}"


def _contact_cell(world: Any, contact_point: list[float] | None) -> tuple[int, int] | None:
    if not contact_point or len(contact_point) < 2:
        return None
    from mechanistic_mind.physical_system.procedural_surface_columns import (
        state_of as psc_state,
        wrap_cell,
    )

    st = psc_state(world)
    if st is not None:
        return wrap_cell(st, float(contact_point[0]), float(contact_point[1]))
    # VW5 / volumetric-only fallback
    try:
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            state_of as vo_state,
            wrap_cell as vo_wrap,
        )

        vo = vo_state(world)
        if vo is not None:
            return vo_wrap(
                vo,
                int(__import__("math").floor(float(contact_point[0]))),
                int(__import__("math").floor(float(contact_point[1]))),
            )
    except Exception:
        pass
    return None


def _top_layer_info(world: Any, cx: int, cy: int) -> dict[str, Any] | None:
    from mechanistic_mind.physical_system.procedural_surface_columns import (
        resolved_column_at,
    )

    col = resolved_column_at(world, cx + 0.5, cy + 0.5)
    layers = col.get("layers") or []
    if not layers:
        return None
    top = layers[0]
    composition_raw = getattr(top, "composition", None)
    if composition_raw is None and isinstance(top, dict):
        composition_raw = top.get("composition")
    thickness = float(
        getattr(top, "thickness", None)
        or (top.get("thickness") if isinstance(top, dict) else 0.0)
        or 0.0
    )
    # Normalize to {component_id, amount} rows for property derivation.
    comp_rows: list[dict[str, Any]] = []
    if isinstance(composition_raw, dict):
        for cid, amt in composition_raw.items():
            comp_rows.append({"component_id": str(cid), "amount": float(amt)})
    elif composition_raw is not None:
        for item in composition_raw:
            if isinstance(item, dict):
                amt = item.get("amount", item.get("quantity_per_area", 0.0))
                comp_rows.append(
                    {
                        "component_id": str(item.get("component_id") or ""),
                        "amount": float(amt),
                    }
                )
            elif isinstance(item, (tuple, list)) and len(item) >= 2:
                comp_rows.append(
                    {"component_id": str(item[0]), "amount": float(item[1])}
                )
    sep = derive_separation_work_per_quantity(comp_rows)
    return {
        "thickness": thickness,
        "composition": comp_rows,
        "separation_work_per_quantity": float(sep["separation_work_per_quantity"]),
        "cell_x": int(col["cell_x"]),
        "cell_y": int(col["cell_y"]),
        "surface_elevation": float(col["surface_elevation"]),
        "sep_report": sep,
    }


def researcher_set_cell_resistance_override(
    world: Any,
    config: Any,
    *,
    cell_x: int,
    cell_y: int,
    separation_work_per_quantity: float,
) -> None:
    """Researcher/test only: override composition-derived resistance at a cell."""
    st = ensure_surface_exertion_terrain_material_resistance_for_runtime(world, config)
    if st is None:
        raise RuntimeError("surface exertion mechanism inactive")
    st.resistance_override[_cell_key(int(cell_x), int(cell_y))] = float(
        separation_work_per_quantity
    )


def consume_actuator_effort_for_terrain_material(
    world: Any,
    *,
    config: Any,
    actuator_receipt: dict[str, Any],
    tick: int,
) -> dict[str, Any]:
    """Apply one actuator effort receipt to terrain material response.

    Eligible mechanical input = actuator_receipt['work_used'] when opposing
    terrain contact with contact_point. Reach/rate-only clips never qualify.
    Body-carried contact without actuator work never reaches here.
    """
    st = ensure_surface_exertion_terrain_material_resistance_for_runtime(world, config)
    if st is None:
        return {
            "receipt_kind": RECEIPT_KIND,
            "status": "INACTIVE",
            "tick": int(tick),
            "researcher_only": True,
        }

    cfg = st.config
    st.counters["loads"] = int(st.counters.get("loads", 0)) + 1
    work_used = float(actuator_receipt.get("work_used") or 0.0)
    opposing = bool(actuator_receipt.get("opposing"))
    cp = actuator_receipt.get("contact_point")
    inward = float(actuator_receipt.get("inward_normal_component") or 0.0)

    base = {
        "receipt_kind": RECEIPT_KIND,
        "event": EVENT_LOAD,
        "tick": int(tick),
        "body_id": actuator_receipt.get("body_id"),
        "effector_id": actuator_receipt.get("effector_id"),
        "actuator_receipt_status": actuator_receipt.get("status"),
        "mechanical_input_authority": MECHANICAL_INPUT,
        "eligible_work": 0.0,
        "fracture_work_applied": 0.0,
        "fracture_work_consumed": 0.0,
        "rigid_remainder_dissipated": 0.0,
        "accumulated_fracture_work_before": 0.0,
        "accumulated_fracture_work_after": 0.0,
        "failure": False,
        "wmt_invoked": False,
        "contact_area": False,
        "pressure": False,
        "stress": False,
        "action_semantics_used": False,
        "researcher_only": True,
        "cognition_exposed": False,
        "failure_model": FAILURE_MODEL,
    }

    eligible = 0.0
    source_kind = "none"
    constraint = str(actuator_receipt.get("external_constraint") or "")
    from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
        CONSTRAINT_KIND as HELD_TERRAIN_CONSTRAINT,
    )

    if (
        opposing
        and work_used > 1e-15
        and inward > 1e-15
        and cp is not None
        and constraint == "terrain_surface"
    ):
        eligible = float(work_used)
        source_kind = "bare_effector"
    else:
        # Held-mediated path: same accumulator, input = work_transmitted
        # (V1 identity ≈ work_used when held-terrain wins).
        try:
            from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
                held_mediated_surface_exertion_integration_is_active,
            )

            held_ok = held_mediated_surface_exertion_integration_is_active(config)
        except Exception:
            held_ok = False
        if (
            held_ok
            and opposing
            and inward > 1e-15
            and cp is not None
            and constraint == HELD_TERRAIN_CONSTRAINT
        ):
            transmitted = float(
                actuator_receipt.get("work_transmitted_to_terrain")
                or (
                    actuator_receipt.get("held_terrain_transmission") or {}
                ).get("work_transmitted_to_terrain")
                or 0.0
            )
            # Fallback: rigid V1 identity before annotate (should be rare).
            if transmitted <= 1e-15 and work_used > 1e-15:
                transmitted = float(work_used)
            if transmitted > 1e-15:
                eligible = float(transmitted)
                source_kind = "held_resource_object_mediated"

    base["exertion_source_kind"] = source_kind
    base["external_constraint"] = constraint
    if source_kind == "held_resource_object_mediated":
        base["held_object_id"] = (
            actuator_receipt.get("held_object_id")
            or actuator_receipt.get("episode_hint")
        )
        base["mechanical_input_authority"] = (
            "actuator_receipt.work_transmitted_to_terrain"
        )

    if eligible <= 1e-15:
        st.counters["zero_eligible"] = int(st.counters.get("zero_eligible", 0)) + 1
        rec = {
            **base,
            "status": "NO_ELIGIBLE_WORK",
            "eligible_work": 0.0,
            "rigid_remainder_dissipated": float(work_used) if work_used > 0 else 0.0,
            "reason": "zero_inward_or_no_terrain_opposition",
        }
        # No fracture; any actuator work_used with no material path stays rigid-dissipated.
        _annotate_actuator(actuator_receipt, rec)
        st.last_step = rec
        world.last_surface_material_loading = rec
        return rec

    cell = _contact_cell(world, cp if isinstance(cp, list) else None)
    if cell is None:
        rec = {**base, "status": "NO_CELL", "eligible_work": eligible}
        _annotate_actuator(actuator_receipt, rec)
        st.last_step = rec
        return rec
    cx, cy = cell
    key = _cell_key(cx, cy)

    # VW5: resistance from contacted occupancy interval (not PSC top layer).
    use_vw5 = False
    top: dict[str, Any] | None = None
    try:
        from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
            contacted_occupancy_material_info,
            effector_held_occupancy_exertion_bridge_is_active,
        )

        use_vw5 = bool(effector_held_occupancy_exertion_bridge_is_active(config))
        if use_vw5:
            top = contacted_occupancy_material_info(
                world, cp if isinstance(cp, list) else None, config=config
            )
            if top is not None:
                key = f"{key}:{top.get('accumulator_key_suffix') or 'interval'}"
    except Exception:
        use_vw5 = False
        top = None
    if top is None:
        top = _top_layer_info(world, cx, cy)
    if top is None or float(top["thickness"]) <= 1e-15:
        rec = {
            **base,
            "status": "NO_TOP_LAYER",
            "eligible_work": eligible,
            "cell_x": cx,
            "cell_y": cy,
            "rigid_remainder_dissipated": eligible,
            "vw5_occupancy_material": bool(use_vw5),
        }
        _annotate_actuator(actuator_receipt, rec)
        st.last_step = rec
        return rec

    w_per_q = float(top["separation_work_per_quantity"])
    if key in st.resistance_override or _cell_key(cx, cy) in st.resistance_override:
        # Cell-level override still applies to volumetric interval loads.
        ov_key = _cell_key(cx, cy)
        if ov_key in st.resistance_override:
            w_per_q = float(st.resistance_override[ov_key])
        elif key in st.resistance_override:
            w_per_q = float(st.resistance_override[key])
        top = {**top, "separation_work_per_quantity": w_per_q, "resistance_override": True}
    if w_per_q <= 1e-18:
        w_per_q = float(UNKNOWN_SEPARATION_FALLBACK())

    before_acc = float(st.fracture_work.get(key, 0.0))
    after_acc = before_acc + eligible
    st.fracture_work[key] = after_acc

    avail = float(top["thickness"])
    max_t = float(cfg.max_wmt_thickness)
    min_t = float(cfg.min_separation_thickness)
    gate_q = min(min_t, avail, max_t)
    work_gate = gate_q * w_per_q if gate_q > 0 else float("inf")

    rec = {
        **base,
        "status": "SUBTHRESHOLD",
        "eligible_work": eligible,
        "fracture_work_applied": eligible,
        "accumulated_fracture_work_before": before_acc,
        "accumulated_fracture_work_after": after_acc,
        "cell_x": cx,
        "cell_y": cy,
        "contact_point": list(cp) if isinstance(cp, list) else cp,
        "surface_normal": actuator_receipt.get("surface_normal"),
        "inward_normal_component": inward,
        "separation_work_per_quantity": w_per_q,
        "top_layer_thickness": avail,
        "gate_quantity": gate_q,
        "work_gate": work_gate,
        "surface_elevation_before": top["surface_elevation"],
        "vw5_occupancy_material": bool(use_vw5),
        "contacted_interval": top.get("interval"),
        "material_authority": top.get("material_authority")
        or ("psc_top_layer" if not use_vw5 else "volumetric_occupancy_contacted_interval"),
    }

    if after_acc + 1e-15 < work_gate or gate_q <= 1e-15:
        st.counters["subthreshold"] = int(st.counters.get("subthreshold", 0)) + 1
        # All eligible became irreversible fracture accumulation; none left as
        # generic rigid dissipation at this contact this tick.
        rec["rigid_remainder_dissipated"] = 0.0
        rec["fracture_work_consumed"] = 0.0
        _annotate_actuator(actuator_receipt, rec)
        _push_history(st, rec)
        world.last_surface_material_loading = rec
        return rec

    # Failure: separate max affordable quantity.
    q = min(after_acc / w_per_q, avail, max_t)
    if q < gate_q - 1e-15:
        # Numerical guard — treat as subthreshold
        st.counters["subthreshold"] = int(st.counters.get("subthreshold", 0)) + 1
        rec["status"] = "SUBTHRESHOLD"
        rec["rigid_remainder_dissipated"] = 0.0
        _annotate_actuator(actuator_receipt, rec)
        _push_history(st, rec)
        world.last_surface_material_loading = rec
        return rec

    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        apply_surface_material_separation,
    )

    # Beta 4 repeated-separation V1: one successful commit per source cell per tick.
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        CLS_CELL_TICK_CAP_FIRST_WINS,
        CLS_COMMITTED_SEPARATION,
        CLS_RETAINED_AFTER_WMT_REJECT,
        clear_accumulator_on_commit,
        cell_already_committed_this_tick,
        mark_cell_committed,
        next_attempt_seq,
        record_step as record_repeated_sep_step,
        repeated_conservative_surface_column_separation_is_active,
        ACCUMULATOR_AUTHORITY,
        FIRST_WINS_ORDER,
        SURPLUS_WORK_POLICY,
        ordering_tuple,
    )

    repeated_on = repeated_conservative_surface_column_separation_is_active(config)
    attempt_seq = next_attempt_seq(world, config) if repeated_on else 0
    source_kind_stable = str(source_kind or "bare_effector")
    order_t = ordering_tuple(
        tick=int(tick),
        attempt_seq=int(attempt_seq),
        cell_y=int(cy),
        cell_x=int(cx),
        body_id=str(actuator_receipt.get("body_id") or ""),
        manipulator_id=str(actuator_receipt.get("effector_id") or ""),
        physical_source_kind=source_kind_stable,
    )

    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        RESULT_CELL_TICK_CAP,
        RESULT_DEDUPLICATED,
        begin_placement_attempt_for_event,
        candidate_summary_from_placement,
        classify_wmt_result,
        event_driven_crowded_placement_retry_contract_is_active,
        record_crowded_retry_step,
    )

    crowding_on = event_driven_crowded_placement_retry_contract_is_active(config)
    crowding_gate: dict[str, Any] | None = None
    if crowding_on:
        crowding_gate = begin_placement_attempt_for_event(
            world,
            config,
            tick=int(tick),
            cell_x=int(cx),
            cell_y=int(cy),
            body_id=actuator_receipt.get("body_id"),
            effector_id=actuator_receipt.get("effector_id"),
            physical_source_kind=source_kind_stable,
            attempt_seq=int(attempt_seq),
        )
        if crowding_gate and not crowding_gate.get("allow_wmt", True):
            st.counters["wmt_rejects"] = int(st.counters.get("wmt_rejects", 0))
            rec.update(
                {
                    "status": "DEDUPLICATED_SAME_EVENT",
                    "failure": False,
                    "wmt_invoked": False,
                    "rigid_remainder_dissipated": 0.0,
                    "requested_separation_thickness": float(q),
                    "accumulated_fracture_work_after": float(after_acc),
                    "attempt_seq": int(attempt_seq) if repeated_on else None,
                    "crowded_retry_result": RESULT_DEDUPLICATED,
                    "exertion_event_id": crowding_gate.get("exertion_event_id"),
                    "retry_event_id": crowding_gate.get("retry_event_id"),
                }
            )
            _annotate_actuator(actuator_receipt, rec)
            _push_history(st, rec)
            world.last_surface_material_loading = rec
            record_crowded_retry_step(
                world,
                config,
                receipt={
                    "tick": int(tick),
                    "retry_event_id": crowding_gate.get("retry_event_id"),
                    "exertion_event_id": crowding_gate.get("exertion_event_id"),
                    "dedup_key": crowding_gate.get("dedup_key"),
                    "cell_x": int(cx),
                    "cell_y": int(cy),
                    "body_id": actuator_receipt.get("body_id"),
                    "effector_id": actuator_receipt.get("effector_id"),
                    "physical_source_kind": source_kind_stable,
                    "attempt_seq": int(attempt_seq),
                    "accepted_new_work": float(eligible),
                    "retained_work_before": float(before_acc),
                    "accumulated_work_after": float(after_acc),
                    "threshold": float(work_gate),
                    "result": RESULT_DEDUPLICATED,
                    "wmt_invoked": False,
                    "accumulator_disposition": "RETAINED",
                },
            )
            return rec

    if repeated_on and cell_already_committed_this_tick(
        world, config, cell_x=int(cx), cell_y=int(cy), tick=int(tick)
    ):
        st.counters["cell_tick_caps"] = int(st.counters.get("cell_tick_caps", 0)) + 1
        rec.update(
            {
                "status": "CELL_TICK_CAP_FIRST_WINS",
                "failure": False,
                "wmt_invoked": False,
                "rigid_remainder_dissipated": 0.0,
                "requested_separation_thickness": float(q),
                "repeated_separation_classification": CLS_CELL_TICK_CAP_FIRST_WINS,
                "first_wins_order": FIRST_WINS_ORDER,
                "ordering_tuple": list(order_t),
                "attempt_seq": int(attempt_seq),
                "accumulator_authority": ACCUMULATOR_AUTHORITY,
                "accumulated_fracture_work_after": float(after_acc),
            }
        )
        _annotate_actuator(actuator_receipt, rec)
        _push_history(st, rec)
        world.last_surface_material_loading = rec
        record_repeated_sep_step(
            world,
            config,
            receipt={
                "receipt_kind": "REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION",
                "classification": CLS_CELL_TICK_CAP_FIRST_WINS,
                "tick": int(tick),
                "cell_x": int(cx),
                "cell_y": int(cy),
                "body_id": actuator_receipt.get("body_id"),
                "effector_id": actuator_receipt.get("effector_id"),
                "physical_source_kind": source_kind_stable,
                "attempt_seq": int(attempt_seq),
                "ordering_tuple": list(order_t),
                "accumulated_fracture_work_before": before_acc,
                "accumulated_fracture_work_after": after_acc,
                "work_added": eligible,
                "wmt_invoked": False,
                "researcher_only": True,
                "agent_accessible": False,
            },
        )
        if crowding_on and crowding_gate is not None:
            record_crowded_retry_step(
                world,
                config,
                receipt={
                    "tick": int(tick),
                    "retry_event_id": crowding_gate.get("retry_event_id"),
                    "exertion_event_id": crowding_gate.get("exertion_event_id"),
                    "dedup_key": crowding_gate.get("dedup_key"),
                    "cell_x": int(cx),
                    "cell_y": int(cy),
                    "body_id": actuator_receipt.get("body_id"),
                    "effector_id": actuator_receipt.get("effector_id"),
                    "physical_source_kind": source_kind_stable,
                    "attempt_seq": int(attempt_seq),
                    "accepted_new_work": float(eligible),
                    "retained_work_before": float(before_acc),
                    "accumulated_work_after": float(after_acc),
                    "result": RESULT_CELL_TICK_CAP,
                    "wmt_invoked": False,
                    "accumulator_disposition": "RETAINED",
                },
            )
        return rec

    causal_id = (
        f"actuator:{actuator_receipt.get('body_id')}:"
        f"{actuator_receipt.get('effector_id')}:t{int(tick)}"
    )
    # When DTIP ON: placement kernel owns xy; do not pass tip contact as spawn.
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        collect_body_refs,
        detached_terrain_material_initial_placement_is_active,
    )

    dtip_on = detached_terrain_material_initial_placement_is_active(config)
    sep_kwargs: dict[str, Any] = {
        "cell_x": int(cx),
        "cell_y": int(cy),
        "requested_thickness": float(q),
        "tick": int(tick),
        "researcher_id": causal_id,
        "acting_body_id": str(actuator_receipt.get("body_id") or "") or None,
        "transmitting_object_id": (
            str(
                actuator_receipt.get("held_object_id")
                or (actuator_receipt.get("held_terrain_transmission") or {}).get("object_id")
                or ""
            )
            or None
        ),
        "body_refs": collect_body_refs(world, config),
    }
    if not dtip_on and isinstance(cp, list):
        sep_kwargs["object_x"] = float(cp[0])
        sep_kwargs["object_y"] = float(cp[1])

    # VW5: route physical failure through VW3 volumetric separation (not top-slice PSC WMT).
    if use_vw5 and top is not None and top.get("interval") is not None:
        from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
            apply_physical_volumetric_separation_from_failure,
            ensure_state as ensure_vw5_state,
        )

        ensure_vw5_state(world, config)
        wmt_out = apply_physical_volumetric_separation_from_failure(
            world,
            config,
            material_info=top,
            requested_thickness=float(q),
            tick=int(tick),
            researcher_id=str(causal_id),
        )
    else:
        wmt_out = apply_surface_material_separation(
            world,
            config,
            **sep_kwargs,
        )
    wmt_receipt = (wmt_out or {}).get("receipt") or {}
    committed = str(wmt_receipt.get("status") or "") == "COMMITTED"
    if not committed:
        st.counters["wmt_rejects"] = int(st.counters.get("wmt_rejects", 0)) + 1
        # Keep accumulation; do not consume.
        place = (wmt_receipt.get("placement") or {}) if isinstance(wmt_receipt, dict) else {}
        reject_cls = CLS_RETAINED_AFTER_WMT_REJECT
        if str(place.get("status") or "").upper() in {"REJECTED", "FAILED"} or str(
            wmt_receipt.get("rejection_reason") or ""
        ).startswith("UNSAFE_OBJECT_PLACEMENT"):
            reject_cls = "PLACEMENT_REJECTED"
        crow_result = classify_wmt_result(wmt_receipt=wmt_receipt, cell_tick_capped=False)
        rec.update(
            {
                "status": "WMT_REJECTED",
                "failure": False,
                "wmt_invoked": True,
                "wmt_receipt": dict(wmt_receipt),
                "rigid_remainder_dissipated": 0.0,
                "requested_separation_thickness": float(q),
                "repeated_separation_classification": reject_cls,
                "accumulator_authority": ACCUMULATOR_AUTHORITY if repeated_on else EXCESS_WORK_POLICY,
                "attempt_seq": int(attempt_seq) if repeated_on else None,
            }
        )
        _annotate_actuator(actuator_receipt, rec)
        _push_history(st, rec)
        world.last_surface_material_loading = rec
        if repeated_on:
            record_repeated_sep_step(
                world,
                config,
                receipt={
                    "receipt_kind": "REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION",
                    "classification": reject_cls,
                    "tick": int(tick),
                    "cell_x": int(cx),
                    "cell_y": int(cy),
                    "body_id": actuator_receipt.get("body_id"),
                    "effector_id": actuator_receipt.get("effector_id"),
                    "physical_source_kind": source_kind_stable,
                    "attempt_seq": int(attempt_seq),
                    "accumulated_fracture_work_before": before_acc,
                    "accumulated_fracture_work_after": after_acc,
                    "wmt_receipt_status": wmt_receipt.get("status"),
                    "rejection_reason": wmt_receipt.get("rejection_reason"),
                    "researcher_only": True,
                    "agent_accessible": False,
                },
            )
        if crowding_on and crowding_gate is not None:
            record_crowded_retry_step(
                world,
                config,
                receipt={
                    "tick": int(tick),
                    "retry_event_id": crowding_gate.get("retry_event_id"),
                    "exertion_event_id": crowding_gate.get("exertion_event_id"),
                    "dedup_key": crowding_gate.get("dedup_key"),
                    "cell_x": int(cx),
                    "cell_y": int(cy),
                    "body_id": actuator_receipt.get("body_id"),
                    "effector_id": actuator_receipt.get("effector_id"),
                    "physical_source_kind": source_kind_stable,
                    "attempt_seq": int(attempt_seq),
                    "accepted_new_work": float(eligible),
                    "retained_work_before": float(before_acc),
                    "accumulated_work_after": float(after_acc),
                    "threshold": float(work_gate),
                    "wmt_transaction_id": wmt_receipt.get("transaction_id"),
                    "candidate_summary": candidate_summary_from_placement(place),
                    "result": crow_result,
                    "wmt_invoked": True,
                    "accumulator_disposition": "RETAINED",
                    "column_revision_before": wmt_receipt.get("column_revision_before"),
                    "column_revision_after": wmt_receipt.get("column_revision_after"),
                    "conservation_residual": (wmt_receipt.get("conservation") or {}).get(
                        "residual"
                    ),
                },
            )
        return rec

    # Actual thickness may have been clamped by WMT.
    actual_t = float(
        wmt_receipt.get("applied_thickness")
        or wmt_receipt.get("separated_thickness")
        or wmt_receipt.get("thickness")
        or q
    )
    # Prefer conservation block if present
    for k in ("applied_thickness", "slice_thickness", "separated_thickness", "thickness"):
        if wmt_receipt.get(k) is not None:
            try:
                actual_t = float(wmt_receipt[k])
                break
            except (TypeError, ValueError):
                pass
    # Plan may store under nested keys
    if "requested_thickness" in wmt_receipt and "clamp" in str(wmt_receipt).lower():
        pass
    actual_t = min(float(actual_t), float(q))
    if actual_t <= 0:
        actual_t = float(q)

    fracture_consumed = float(actual_t) * w_per_q
    residual_acc = max(0.0, after_acc - fracture_consumed)
    surplus_meta: dict[str, Any] = {}
    if repeated_on:
        surplus_meta = clear_accumulator_on_commit(
            st.fracture_work,
            key,
            before=float(after_acc),
            threshold_consumed=float(fracture_consumed),
        )
        residual_acc = 0.0
    else:
        st.fracture_work[key] = residual_acc  # EXCESS_WORK_POLICY

    st.counters["failures"] = int(st.counters.get("failures", 0)) + 1
    st.counters["wmt_commits"] = int(st.counters.get("wmt_commits", 0)) + 1

    obj_id = wmt_receipt.get("object_id") or wmt_receipt.get("resource_object_id")
    if obj_id is None:
        # Fall back: last resource object
        objs = list(getattr(world, "resource_objects", None) or [])
        if objs:
            obj_id = getattr(objs[-1], "object_id", None) or getattr(objs[-1], "id", None)

    if repeated_on:
        # Ledger mark is owned by apply_surface_material_separation after commit.
        pass

    rec.update(
        {
            "event": EVENT_FAILURE,
            "status": "FAILURE_WMT_COMMITTED",
            "failure": True,
            "wmt_invoked": True,
            "fracture_work_consumed": float(fracture_consumed),
            "rigid_remainder_dissipated": 0.0,
            "accumulated_fracture_work_after": float(residual_acc),
            "requested_separation_thickness": float(q),
            "applied_separation_thickness": float(actual_t),
            "excess_work_policy": (
                SURPLUS_WORK_POLICY if repeated_on else EXCESS_WORK_POLICY
            ),
            "wmt_receipt_status": wmt_receipt.get("status"),
            "transaction_id": wmt_receipt.get("transaction_id"),
            "separation_id": wmt_receipt.get("separation_id"),
            "detached_object_id": obj_id,
            "repeated_separation_classification": (
                CLS_COMMITTED_SEPARATION if repeated_on else None
            ),
            "surplus_discarded": float(surplus_meta.get("surplus_discarded") or 0.0),
            "accumulator_authority": (
                ACCUMULATOR_AUTHORITY if repeated_on else EXCESS_WORK_POLICY
            ),
            "attempt_seq": int(attempt_seq) if repeated_on else None,
            "wmt_receipt": {
                k: wmt_receipt[k]
                for k in (
                    "status",
                    "transaction_id",
                    "separation_id",
                    "schema",
                    "operation_kind",
                    "authority",
                    "cell",
                    "cell_x",
                    "cell_y",
                    "object_id",
                    "quantity",
                    "mass",
                    "applied_thickness",
                    "separated_thickness",
                    "thickness",
                    "conservation_verified",
                    "conservation",
                    "placement",
                    "vw5_bridge",
                    "physical_failure_routed_via",
                )
                if k in wmt_receipt
            },
            "vw5_routed_to_vw3": bool(use_vw5 and wmt_receipt.get("vw5_bridge")),
            "provenance": {
                "actuator_body_id": actuator_receipt.get("body_id"),
                "actuator_effector_id": actuator_receipt.get("effector_id"),
                "actuator_tick": actuator_receipt.get("tick"),
                "actuator_work_used": work_used,
                "contact_point": list(cp) if isinstance(cp, list) else cp,
                "causal_researcher_id": causal_id,
                "physical_source_kind": source_kind_stable,
                "attempt_seq": int(attempt_seq) if repeated_on else None,
                "ordering_tuple": list(order_t) if repeated_on else None,
                **surplus_meta,
            },
        }
    )
    _annotate_actuator(actuator_receipt, rec)
    _push_history(st, rec)
    world.last_surface_material_loading = rec
    world.last_surface_material_failure = rec
    if crowding_on and crowding_gate is not None:
        from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
            RESULT_PLACED,
        )

        place_ok = (wmt_receipt.get("placement") or {}) if isinstance(wmt_receipt, dict) else {}
        record_crowded_retry_step(
            world,
            config,
            receipt={
                "tick": int(tick),
                "retry_event_id": crowding_gate.get("retry_event_id"),
                "exertion_event_id": crowding_gate.get("exertion_event_id"),
                "dedup_key": crowding_gate.get("dedup_key"),
                "cell_x": int(cx),
                "cell_y": int(cy),
                "body_id": actuator_receipt.get("body_id"),
                "effector_id": actuator_receipt.get("effector_id"),
                "physical_source_kind": source_kind_stable,
                "attempt_seq": int(attempt_seq),
                "accepted_new_work": float(eligible),
                "retained_work_before": float(before_acc),
                "accumulated_work_after": float(residual_acc),
                "threshold": float(work_gate),
                "wmt_transaction_id": wmt_receipt.get("transaction_id"),
                "candidate_summary": candidate_summary_from_placement(place_ok),
                "result": RESULT_PLACED,
                "object_id": obj_id,
                "wmt_invoked": True,
                "accumulator_disposition": (
                    SURPLUS_WORK_POLICY if repeated_on else EXCESS_WORK_POLICY
                ),
                "column_revision_before": wmt_receipt.get("column_revision_before"),
                "column_revision_after": wmt_receipt.get("column_revision_after"),
                "conservation_residual": (wmt_receipt.get("conservation") or {}).get(
                    "residual"
                ),
            },
        )
    return rec


def UNKNOWN_SEPARATION_FALLBACK() -> float:
    from mechanistic_mind.physical_system.passive_material_properties import (
        UNKNOWN_SEPARATION_WORK_PER_QUANTITY,
    )

    return float(UNKNOWN_SEPARATION_WORK_PER_QUANTITY)


def _annotate_actuator(actuator_receipt: dict[str, Any], mat_rec: dict[str, Any]) -> None:
    """Partition actuator work: fracture vs residual rigid dissipation.

    Actuator work_used is capacity spent (left ABSTRACT source).
    Material layer owns world-side partition — avoids double-counting the same
    joules as both fracture energy and exclusive rigid-contact heat.
    """
    eligible = float(mat_rec.get("eligible_work") or 0.0)
    frac_applied = float(mat_rec.get("fracture_work_applied") or 0.0)
    frac_consumed = float(mat_rec.get("fracture_work_consumed") or 0.0)
    rigid = float(mat_rec.get("rigid_remainder_dissipated") or 0.0)
    # Reinterpret work_dissipated as residual rigid only (not including fracture).
    actuator_receipt["work_dissipated"] = float(rigid)
    actuator_receipt["fracture_work_applied"] = float(frac_applied)
    actuator_receipt["fracture_work_consumed"] = float(frac_consumed)
    actuator_receipt["material_loading_status"] = mat_rec.get("status")
    actuator_receipt["material_failure"] = bool(mat_rec.get("failure"))
    actuator_receipt["separation_wmt"] = bool(mat_rec.get("wmt_invoked") and mat_rec.get("failure"))
    actuator_receipt["blocked_work_policy"] = (
        "MATERIAL_PARTITION_FRACTURE_THEN_RIGID_RESIDUAL_V1"
    )
    actuator_receipt["eligible_material_work"] = eligible


def _push_history(st: SurfaceExertionTerrainMaterialResistanceState, rec: dict[str, Any]) -> None:
    st.last_step = rec
    st.history.append(dict(rec))
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]


def process_pending_actuator_receipts_same_tick(
    world: Any,
    *,
    config: Any,
    receipts: list[dict[str, Any]],
    tick: int,
) -> list[dict[str, Any]]:
    """Deterministic multi-contact ordering: sort by (cell_y, cell_x, body_id, effector_id)."""
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        repeated_conservative_surface_column_separation_is_active,
    )

    def _sort_key(r: dict[str, Any]) -> tuple:
        cx = r.get("cell_x")
        cy = r.get("cell_y")
        if cx is None or cy is None:
            cp = r.get("contact_point")
            if isinstance(cp, (list, tuple)) and len(cp) >= 2:
                try:
                    cx = int(math.floor(float(cp[0])))
                    cy = int(math.floor(float(cp[1])))
                except (TypeError, ValueError):
                    cx, cy = 0, 0
            else:
                cx, cy = 0, 0
        return (
            int(cy),
            int(cx),
            str(r.get("body_id") or ""),
            str(r.get("effector_id") or ""),
        )

    if repeated_conservative_surface_column_separation_is_active(config):
        ordered = sorted(receipts, key=_sort_key)
    else:
        ordered = sorted(
            receipts,
            key=lambda r: (str(r.get("body_id") or ""), str(r.get("effector_id") or "")),
        )
    out: list[dict[str, Any]] = []
    for rec in ordered:
        out.append(
            consume_actuator_effort_for_terrain_material(
                world, config=config, actuator_receipt=rec, tick=tick
            )
        )
    return out
