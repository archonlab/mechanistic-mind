"""Acanthostega Beta 4 · Repeated conservative surface-column separation V1.

Mechanism: repeated_conservative_surface_column_separation
Preset: ACANTHOSTEGA_BETA4_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
Parent: ACANTHOSTEGA_BETA4_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
Profile: REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION_V1

Safety/persistence contracts around the existing SEPARATE_SURFACE_COLUMN_SLICE
path — no second removal mechanism, no DIG/MINE semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "repeated_conservative_surface_column_separation"
PROFILE_VERSION = "REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION_V1"
STATE_SCHEMA = "REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION_STATE_V1"
RECEIPT_KIND = "REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION"

MAX_SUCCESSFUL_SEPARATIONS_PER_SOURCE_CELL_PER_SCIENTIFIC_TICK = 1
FIRST_WINS_ORDER = "STABLE_SORT_FIRST_WINS_CELL_TICK_CAP"
TRANSACTION_COMMIT_POLICY = "SEQUENTIAL_AGAINST_UPDATED_AUTHORITATIVE_STATE"
ACCUMULATOR_AUTHORITY = "CLEAR_ACCUMULATOR_ON_COMMITTED_SEPARATION_V1_KEEP_ON_WMT_REJECT"
SURPLUS_WORK_POLICY = "CLEAR_ON_COMMITTED_SEPARATION"
RESISTANCE_REFRESH_POLICY = "FROM_CURRENT_TOP_LAYER"
SUPPORT_REFRESH_POLICY = "IMMEDIATE_REEVAL_AIRBORNE_Z_UNCHANGED_NO_FREE_LIFT"
DEPOSIT_COUPLING = "NOT_ESTABLISHED"

CLS_ACCUMULATING = "ACCUMULATING"
CLS_BELOW_THRESHOLD = "BELOW_THRESHOLD"
CLS_COMMITTED_SEPARATION = "COMMITTED_SEPARATION"
CLS_RETAINED_AFTER_WMT_REJECT = "RETAINED_AFTER_WMT_REJECT"
CLS_CELL_TICK_CAP_FIRST_WINS = "CELL_TICK_CAP_FIRST_WINS"
CLS_NO_EXPOSED_MATERIAL = "NO_EXPOSED_MATERIAL"
CLS_MINIMUM_RESOLVED_DEPTH = "MINIMUM_RESOLVED_DEPTH"
CLS_NOT_MODELLED = "NOT_MODELLED"
CLS_PLACEMENT_REJECTED = "PLACEMENT_REJECTED"
CLS_GEOMETRY_QUERY_FAILURE = "GEOMETRY_QUERY_FAILURE"

BANNER = (
    "REPEATED CONSERVATIVE SURFACE-COLUMN SEPARATION\n"
    "ONE SUCCESS PER CELL PER TICK\n"
    "CURRENT TOP MATERIAL RESISTANCE\n"
    "CLEAR WORK ON COMMIT\n"
    "KEEP WORK ON REJECT\n"
    "SEQUENTIAL UPDATED-STATE TRANSACTIONS"
)


@dataclass
class RepeatedConservativeSurfaceColumnSeparationConfig:
    enabled: bool = False
    history_limit: int = 64

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "max_successful_separations_per_source_cell_per_scientific_tick": (
                MAX_SUCCESSFUL_SEPARATIONS_PER_SOURCE_CELL_PER_SCIENTIFIC_TICK
            ),
            "first_wins_order": FIRST_WINS_ORDER,
            "transaction_commit_policy": TRANSACTION_COMMIT_POLICY,
            "accumulator_authority": ACCUMULATOR_AUTHORITY,
            "surplus_work_policy": SURPLUS_WORK_POLICY,
            "resistance_refresh_policy": RESISTANCE_REFRESH_POLICY,
            "support_refresh_policy": SUPPORT_REFRESH_POLICY,
            "deposit_coupling": DEPOSIT_COUPLING,
            "second_removal_path": False,
            "dig_action": False,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None
    ) -> "RepeatedConservativeSurfaceColumnSeparationConfig":
        d = dict(data or {})
        return cls(
            enabled=bool(d.get("enabled", False)),
            history_limit=int(d.get("history_limit", 64)),
        )


def validate_config(cfg: RepeatedConservativeSurfaceColumnSeparationConfig) -> None:
    if int(cfg.history_limit) < 1:
        raise ValueError("history_limit must be >= 1")


def _line_ok(config: Any) -> bool:
    return (
        config is not None
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    )


def repeated_conservative_surface_column_separation_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "repeated_conservative_surface_column_separation", None)
    return cfg is not None and bool(getattr(cfg, "enabled", False))


def set_repeated_conservative_surface_column_separation(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "repeated_conservative_surface_column_separation", None)
    if cur is None:
        if on:
            config.repeated_conservative_surface_column_separation = (
                RepeatedConservativeSurfaceColumnSeparationConfig(enabled=True)
            )
        return
    if isinstance(cur, dict):
        cfg = RepeatedConservativeSurfaceColumnSeparationConfig.from_dict(cur)
        cfg.enabled = on
        config.repeated_conservative_surface_column_separation = cfg
    else:
        cur.enabled = on


@dataclass
class RepeatedConservativeSurfaceColumnSeparationState:
    config: RepeatedConservativeSurfaceColumnSeparationConfig
    ledger_tick: int = -1
    # cell_key "cx|cy" → {transaction_id, attempt_seq, body_id, effector_id, ...}
    successful_cells: dict[str, dict[str, Any]] = field(default_factory=dict)
    attempt_seq: int = 0
    last_step: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(
        default_factory=lambda: {
            "commits": 0,
            "cell_tick_caps": 0,
            "accumulator_clears": 0,
            "surplus_discards": 0,
            "wmt_rejects_retained": 0,
        }
    )


def cell_key(cx: int, cy: int) -> str:
    return f"{int(cx)}|{int(cy)}"


def parse_cell_key(key: str) -> tuple[int, int]:
    a, b = str(key).split("|", 1)
    return int(a), int(b)


def state_of(world: Any) -> RepeatedConservativeSurfaceColumnSeparationState | None:
    raw = getattr(world, "repeated_conservative_surface_column_separation_state", None)
    return raw if isinstance(raw, RepeatedConservativeSurfaceColumnSeparationState) else None


def ensure_repeated_conservative_surface_column_separation_for_runtime(
    world: Any, config: Any
) -> RepeatedConservativeSurfaceColumnSeparationState | None:
    if not repeated_conservative_surface_column_separation_is_active(config):
        world.repeated_conservative_surface_column_separation_state = None
        return None
    raw = getattr(config, "repeated_conservative_surface_column_separation", None)
    if isinstance(raw, RepeatedConservativeSurfaceColumnSeparationConfig):
        cfg = raw
    elif isinstance(raw, dict):
        cfg = RepeatedConservativeSurfaceColumnSeparationConfig.from_dict(raw)
        config.repeated_conservative_surface_column_separation = cfg
    else:
        cfg = RepeatedConservativeSurfaceColumnSeparationConfig(enabled=True)
        config.repeated_conservative_surface_column_separation = cfg
    validate_config(cfg)
    st = state_of(world)
    if st is None or st.config is not cfg:
        st = RepeatedConservativeSurfaceColumnSeparationState(config=cfg)
        world.repeated_conservative_surface_column_separation_state = st
    return st


def _roll_ledger(st: RepeatedConservativeSurfaceColumnSeparationState, tick: int) -> None:
    t = int(tick)
    if int(st.ledger_tick) != t:
        st.ledger_tick = t
        st.successful_cells = {}


def cell_already_committed_this_tick(
    world: Any, config: Any, *, cell_x: int, cell_y: int, tick: int
) -> bool:
    st = ensure_repeated_conservative_surface_column_separation_for_runtime(world, config)
    if st is None:
        return False
    _roll_ledger(st, tick)
    return cell_key(cell_x, cell_y) in st.successful_cells


def mark_cell_committed(
    world: Any,
    config: Any,
    *,
    cell_x: int,
    cell_y: int,
    tick: int,
    meta: dict[str, Any] | None = None,
) -> None:
    st = ensure_repeated_conservative_surface_column_separation_for_runtime(world, config)
    if st is None:
        return
    _roll_ledger(st, tick)
    key = cell_key(cell_x, cell_y)
    st.successful_cells[key] = dict(meta or {})
    st.counters["commits"] = int(st.counters.get("commits", 0)) + 1


def next_attempt_seq(world: Any, config: Any) -> int:
    st = ensure_repeated_conservative_surface_column_separation_for_runtime(world, config)
    if st is None:
        return 0
    st.attempt_seq = int(st.attempt_seq) + 1
    return int(st.attempt_seq)


def clear_accumulator_on_commit(
    fracture_work: dict[str, float],
    key: str,
    *,
    before: float,
    threshold_consumed: float,
) -> dict[str, Any]:
    """CLEAR_ON_COMMITTED_SEPARATION — discard surplus; no cascade."""
    surplus = max(0.0, float(before) - float(threshold_consumed))
    fracture_work[key] = 0.0
    return {
        "accumulator_before_clear": float(before),
        "threshold_consumed": float(threshold_consumed),
        "surplus_discarded": float(surplus),
        "accumulator_after_clear": 0.0,
        "surplus_work_policy": SURPLUS_WORK_POLICY,
    }


def record_step(
    world: Any,
    config: Any,
    *,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    st = ensure_repeated_conservative_surface_column_separation_for_runtime(world, config)
    if st is None:
        return dict(receipt)
    st.last_step = dict(receipt)
    st.history.append(dict(receipt))
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    cls = str(receipt.get("classification") or "")
    if cls == CLS_CELL_TICK_CAP_FIRST_WINS:
        st.counters["cell_tick_caps"] = int(st.counters.get("cell_tick_caps", 0)) + 1
    elif cls == CLS_COMMITTED_SEPARATION:
        if float(receipt.get("surplus_discarded") or 0.0) > 0.0:
            st.counters["surplus_discards"] = int(st.counters.get("surplus_discards", 0)) + 1
        st.counters["accumulator_clears"] = int(st.counters.get("accumulator_clears", 0)) + 1
    elif cls == CLS_RETAINED_AFTER_WMT_REJECT:
        st.counters["wmt_rejects_retained"] = int(
            st.counters.get("wmt_rejects_retained", 0)
        ) + 1
    world.last_repeated_conservative_surface_column_separation = dict(receipt)
    return dict(receipt)


def serialize_state(
    st: RepeatedConservativeSurfaceColumnSeparationState | None,
) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "ledger_tick": int(st.ledger_tick),
        "successful_cells": {
            str(k): dict(v) for k, v in st.successful_cells.items()
        },
        "attempt_seq": int(st.attempt_seq),
        "last_step": dict(st.last_step) if st.last_step else {},
        "history": list(st.history[-int(st.config.history_limit) :]),
        "counters": {k: int(v) for k, v in st.counters.items()},
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> RepeatedConservativeSurfaceColumnSeparationState | None:
    if not repeated_conservative_surface_column_separation_is_active(config):
        world.repeated_conservative_surface_column_separation_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_repeated_conservative_surface_column_separation_for_runtime(
            world, config
        )
    cfg = RepeatedConservativeSurfaceColumnSeparationConfig.from_dict(
        data.get("config") or {}
    )
    cfg.enabled = True
    validate_config(cfg)
    st = RepeatedConservativeSurfaceColumnSeparationState(config=cfg)
    st.ledger_tick = int(data.get("ledger_tick", -1))
    st.successful_cells = {
        str(k): dict(v)
        for k, v in dict(data.get("successful_cells") or {}).items()
        if isinstance(v, dict)
    }
    st.attempt_seq = int(data.get("attempt_seq", 0) or 0)
    st.last_step = dict(data.get("last_step") or {})
    st.history = [dict(r) for r in (data.get("history") or []) if isinstance(r, dict)]
    st.counters = {str(k): int(v) for k, v in dict(data.get("counters") or {}).items()}
    world.repeated_conservative_surface_column_separation_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Repeated conservative surface-column separation",
        "enabled": bool(enabled),
        "researcher_only": True,
        "agent_action": False,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "ledger_tick": int(st.ledger_tick),
        "successful_cells": dict(st.successful_cells),
        "counters": dict(st.counters),
        "last_step": dict(st.last_step) if st.last_step else {},
        "max_successful_separations_per_source_cell_per_scientific_tick": (
            MAX_SUCCESSFUL_SEPARATIONS_PER_SOURCE_CELL_PER_SCIENTIFIC_TICK
        ),
        "deposit_coupling": DEPOSIT_COUPLING,
        "agent_accessible": False,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    cells = []
    for key, meta in st.successful_cells.items():
        try:
            cx, cy = parse_cell_key(key)
        except Exception:
            continue
        cells.append(
            {
                "cell_x": cx,
                "cell_y": cy,
                "transaction_id": meta.get("transaction_id"),
                "object_id": meta.get("detached_object_id"),
            }
        )
    return {
        "modified_cells_this_tick": cells,
        "ledger_tick": int(st.ledger_tick),
        "deposit_coupling": DEPOSIT_COUPLING,
        "researcher_only": True,
    }


def ordering_tuple(
    *,
    tick: int,
    attempt_seq: int,
    cell_y: int,
    cell_x: int,
    body_id: str,
    manipulator_id: str,
    physical_source_kind: str,
    transaction_seq: int = 0,
) -> tuple:
    """STABLE_SORT_FIRST_WINS — repository cell order (y, x) then ids."""
    return (
        int(tick),
        int(attempt_seq),
        int(cell_y),
        int(cell_x),
        str(body_id or ""),
        str(manipulator_id or ""),
        str(physical_source_kind or ""),
        int(transaction_seq),
    )
