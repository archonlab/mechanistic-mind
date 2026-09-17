"""Objective object existence dynamics.

Effects and spatial-temporal existence are independent world properties.
This module owns only ground-truth presence, absence, and relocation.
It does not interpret objects as resources and does not write psyche state.
"""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, Iterable

from mechanistic_mind.core import DeterministicRandom

from .models import Position


EXISTENCE_MODES = frozenset(
    {"STATIC", "RELOCATING_RANDOM", "RELOCATING_ROUTE"}
)
EXISTENCE_TRIGGERS = frozenset({"DEPLETED", "RESIDENCE_ELAPSED"})

COGNITIVE_FORBIDDEN_KEYS = frozenset(
    {
        "autonomous",
        "autonomous_runtime",
        "autonomous_events",
        "causal_provenance_tick",
        "existence",
        "existence_mode",
        "existence_present",
        "existence_region_index",
        "existence_region_id",
        "route",
        "route_index",
        "next_region",
        "next_position",
        "remaining_transition_delay",
        "relocation_trigger",
        "future_appearance_tick",
        "scheduled_reappear_tick",
        "appearance_count",
        "local_availability",
        "remaining_uses",
        "transition_reason",
        "hidden_next_position",
        "existence_clock",
        "existence_events",
    }
)

_EVENT_CAP = 128


class ExistenceMode(str, Enum):
    STATIC = "STATIC"
    RELOCATING_RANDOM = "RELOCATING_RANDOM"
    RELOCATING_ROUTE = "RELOCATING_ROUTE"


def default_existence_config() -> dict[str, Any]:
    return {
        "mode": ExistenceMode.STATIC.value,
        "trigger": {"type": "DEPLETED"},
        "route": [],
        "allowed_regions": [],
        "cycle": True,
        "residence_ticks": None,
        "transition_delay_ticks": [0, 0],
        "randomize_position_within_region": True,
        "reset_availability_on_appearance": True,
        "deplete_when_effect_unavailable": False,
    }


def normalize_existence(raw: dict[str, Any] | None) -> dict[str, Any]:
    config = default_existence_config()
    if not raw:
        return config
    incoming = deepcopy(raw)
    mode = str(incoming.get("mode") or ExistenceMode.STATIC.value).upper()
    if mode not in EXISTENCE_MODES:
        raise ValueError(f"Unsupported existence mode: {mode}")
    config["mode"] = mode
    trigger = incoming.get("trigger")
    if isinstance(trigger, str):
        trigger = {"type": trigger}
    if isinstance(trigger, dict):
        trigger_type = str(trigger.get("type") or "DEPLETED").upper()
        if trigger_type not in EXISTENCE_TRIGGERS:
            raise ValueError(f"Unsupported existence trigger: {trigger_type}")
        config["trigger"] = {"type": trigger_type}
    if "cycle" in incoming:
        config["cycle"] = bool(incoming["cycle"])
    if "randomize_position_within_region" in incoming:
        config["randomize_position_within_region"] = bool(
            incoming["randomize_position_within_region"]
        )
    if "reset_availability_on_appearance" in incoming:
        config["reset_availability_on_appearance"] = bool(
            incoming["reset_availability_on_appearance"]
        )
    if "deplete_when_effect_unavailable" in incoming:
        config["deplete_when_effect_unavailable"] = bool(
            incoming["deplete_when_effect_unavailable"]
        )
    delay = incoming.get("transition_delay_ticks", [0, 0])
    config["transition_delay_ticks"] = _tick_range(delay, "transition_delay_ticks")
    residence = incoming.get("residence_ticks")
    if residence is not None:
        config["residence_ticks"] = _tick_range(residence, "residence_ticks")
    config["route"] = [
        normalize_region(item, fallback_id=f"R{index}")
        for index, item in enumerate(incoming.get("route") or [])
    ]
    config["allowed_regions"] = [
        normalize_region(item, fallback_id=f"A{index}")
        for index, item in enumerate(incoming.get("allowed_regions") or [])
    ]
    return config


def normalize_region(raw: Any, *, fallback_id: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Existence region must be an object")
    region_id = str(raw.get("region") or raw.get("region_id") or fallback_id)
    cells = _explicit_cells(raw.get("cells"))
    bounds = raw.get("bounds")
    if not cells and isinstance(bounds, dict):
        cells = _cells_from_bounds(bounds)
    if not cells and all(key in raw for key in ("x_min", "y_min", "x_max", "y_max")):
        cells = _cells_from_bounds(raw)
    if not cells and "position" in raw:
        position = _as_position(raw.get("position"))
        if position is not None:
            cells = [list(position)]
    if not cells:
        raise ValueError(f"Existence region {region_id!r} has no valid cells")
    return {"region_id": region_id, "cells": cells}


def validate_existence_config(
    config: dict[str, Any],
    *,
    width: int,
    height: int,
    blocked: Iterable[Position],
    object_id: str,
) -> None:
    mode = config.get("mode", ExistenceMode.STATIC.value)
    if mode not in EXISTENCE_MODES:
        raise ValueError(f"{object_id}: unsupported existence mode {mode}")
    blocked_set = {tuple(item) for item in blocked}
    regions = list(config.get("route") or []) + list(config.get("allowed_regions") or [])
    for region in regions:
        for raw_cell in region.get("cells", []):
            cell = _as_position(raw_cell)
            if cell is None:
                raise ValueError(f"{object_id}: malformed region cell")
            x, y = cell
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError(
                    f"{object_id}: region cell {cell} is outside the world"
                )
            if cell in blocked_set:
                raise ValueError(f"{object_id}: region cell {cell} is blocked")
    if mode == ExistenceMode.RELOCATING_ROUTE.value and not config.get("route"):
        raise ValueError(f"{object_id}: RELOCATING_ROUTE requires a route")


def initial_existence_state(
    config: dict[str, Any],
    *,
    position: Position,
) -> dict[str, Any]:
    route = list(config.get("route") or [])
    region_index = 0
    region_id = None
    if route:
        region_index, region_id = _matching_region(route, position)
    return {
        "config": deepcopy(config),
        "mode": config.get("mode", ExistenceMode.STATIC.value),
        "present": True,
        "region_index": region_index,
        "region_id": region_id,
        "scheduled_reappear_tick": None,
        "hidden_next_position": None,
        "hidden_next_region_index": None,
        "hidden_next_region_id": None,
        "appearance_count": 1,
        "present_since_clock": 0,
        "residence_until_clock": None,
        "last_event": None,
        "route_complete": False,
    }


def is_static(record: dict[str, Any]) -> bool:
    existence = record.get("existence")
    if not isinstance(existence, dict):
        return True
    return str(existence.get("mode") or ExistenceMode.STATIC.value) == (
        ExistenceMode.STATIC.value
    )


def is_present(record: dict[str, Any]) -> bool:
    if record.get("active", True) is False:
        return False
    existence = record.get("existence")
    if isinstance(existence, dict) and existence.get("present") is False:
        return False
    return True


def existence_events(state: dict[str, Any]) -> list[dict[str, Any]]:
    events = state.get("existence_events")
    return list(events) if isinstance(events, list) else []


def append_existence_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    events = existence_events(state)
    events.append(event)
    state["existence_events"] = events[-_EVENT_CAP:]


def observation_contains_forbidden(payload: Any) -> list[str]:
    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key) in COGNITIVE_FORBIDDEN_KEYS:
                    found.append(str(key))
                walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child)

    walk(payload)
    return found


def _tick_range(raw: Any, name: str) -> list[int]:
    if isinstance(raw, int):
        values = [int(raw), int(raw)]
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        values = [int(raw[0]), int(raw[1])]
    elif isinstance(raw, dict) and "min" in raw and "max" in raw:
        values = [int(raw["min"]), int(raw["max"])]
    else:
        raise ValueError(f"{name} must be an int or [min, max]")
    if values[0] < 0 or values[1] < values[0]:
        raise ValueError(f"{name} must satisfy 0 <= min <= max")
    return values


def _explicit_cells(raw: Any) -> list[list[int]]:
    cells: list[list[int]] = []
    if not isinstance(raw, (list, tuple)):
        return cells
    for item in raw:
        position = _as_position(item)
        if position is None:
            raise ValueError("Region cell must be an [x, y] pair")
        cells.append(list(position))
    return cells


def _cells_from_bounds(raw: dict[str, Any]) -> list[list[int]]:
    try:
        x_min = int(raw.get("x_min", raw.get("x0")))
        y_min = int(raw.get("y_min", raw.get("y0")))
        x_max = int(raw.get("x_max", raw.get("x1")))
        y_max = int(raw.get("y_max", raw.get("y1")))
    except (TypeError, ValueError) as exc:
        raise ValueError("Region bounds must be integers") from exc
    if x_max < x_min or y_max < y_min:
        raise ValueError("Region bounds must satisfy min <= max")
    return [
        [x, y]
        for x in range(x_min, x_max + 1)
        for y in range(y_min, y_max + 1)
    ]


def _as_position(raw: Any) -> Position | None:
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        try:
            return int(raw[0]), int(raw[1])
        except (TypeError, ValueError):
            return None
    return None


def _matching_region(
    route: list[dict[str, Any]],
    position: Position,
) -> tuple[int, str | None]:
    for index, region in enumerate(route):
        cells = {
            tuple(cell)
            for cell in region.get("cells", [])
            if _as_position(cell) is not None
        }
        if position in cells:
            return index, str(region.get("region_id") or f"R{index}")
    first = route[0]
    return 0, str(first.get("region_id") or "R0")


def sample_delay(config: dict[str, Any], rng: DeterministicRandom) -> int:
    low, high = config.get("transition_delay_ticks") or [0, 0]
    if low == high:
        return int(low)
    return int(rng.randint(int(low), int(high)))


def sample_residence(config: dict[str, Any], rng: DeterministicRandom) -> int | None:
    span = config.get("residence_ticks")
    if not span:
        return None
    low, high = span
    if low == high:
        return int(low)
    return int(rng.randint(int(low), int(high)))


def choose_position(
    *,
    cells: list[Position],
    randomize: bool,
    rng: DeterministicRandom,
    open_fn,
    object_id: str,
) -> Position | None:
    valid = [cell for cell in cells if open_fn(cell, object_id)]
    pool = valid or list(cells)
    if not pool:
        return None
    if not randomize:
        return pool[0]
    index = int(rng.randint(0, len(pool) - 1))
    return pool[index]
