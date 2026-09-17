"""Autonomous world dynamics — objective temporal processes.

Runs on every world transition tick, including WAIT. Does not write psyche
state and does not expose schedules/routes to agent observation.
"""
from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any

from mechanistic_mind.core import DeterministicRandom

from .models import Position


class MotionPattern(str, Enum):
    NONE = "NONE"
    PERIODIC_ROUTE = "PERIODIC_ROUTE"
    BOUNDED_WANDER = "BOUNDED_WANDER"
    OSCILLATE = "OSCILLATE"


class CausalProvenance(str, Enum):
    AGENT_ACTION = "AGENT_ACTION"
    AUTONOMOUS_OBJECT = "AUTONOMOUS_OBJECT"
    BODY_DYNAMICS = "BODY_DYNAMICS"
    FIELD_DYNAMICS = "FIELD_DYNAMICS"
    OTHER_AGENT = "OTHER_AGENT"
    COMPOSITE = "COMPOSITE"
    UNRESOLVED = "UNRESOLVED"


AUTONOMOUS_FORBIDDEN_KEYS = frozenset(
    {
        "autonomous",
        "autonomous_motion",
        "motion_pattern",
        "motion_route",
        "motion_index",
        "scheduled_motion_tick",
        "autonomous_events",
        "causal_provenance",
        "causal_provenance_tick",
        "hidden_next_position",
        "velocity",
        "transition_period",
    }
)

_EVENT_CAP = 256


def default_autonomous_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "motion": {
            "pattern": MotionPattern.NONE.value,
            "period_ticks": 1,
            "route": [],
            "bound_min": None,
            "bound_max": None,
            "step": 1,
            "phase": 0,
        },
        "state_cycle": None,
    }


def normalize_autonomous(raw: dict[str, Any] | None) -> dict[str, Any]:
    config = default_autonomous_config()
    if not isinstance(raw, dict):
        return config
    config["enabled"] = bool(raw.get("enabled", False))
    motion_in = raw.get("motion") if isinstance(raw.get("motion"), dict) else {}
    motion = dict(config["motion"])
    pattern = str(motion_in.get("pattern") or MotionPattern.NONE.value).upper()
    if pattern not in {item.value for item in MotionPattern}:
        raise ValueError(f"Unsupported autonomous motion pattern: {pattern}")
    motion["pattern"] = pattern
    motion["period_ticks"] = max(1, int(motion_in.get("period_ticks", 1)))
    route = motion_in.get("route") or []
    motion["route"] = [list(map(int, point)) for point in route]
    if motion_in.get("bound_min") is not None:
        motion["bound_min"] = list(map(int, motion_in["bound_min"]))
    if motion_in.get("bound_max") is not None:
        motion["bound_max"] = list(map(int, motion_in["bound_max"]))
    motion["step"] = max(1, int(motion_in.get("step", 1)))
    motion["phase"] = int(motion_in.get("phase", 0))
    config["motion"] = motion
    cycle = raw.get("state_cycle")
    if isinstance(cycle, dict) and cycle.get("field"):
        config["state_cycle"] = {
            "field": str(cycle["field"]),
            "period_ticks": max(1, int(cycle.get("period_ticks", 10))),
            "amplitude": float(cycle.get("amplitude", 0.05)),
            "center": cycle.get("center"),
            "phase": int(cycle.get("phase", 0)),
        }
    else:
        config["state_cycle"] = None
    return config


def append_autonomous_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    events = state.get("autonomous_events")
    if not isinstance(events, list):
        events = []
    events.append(deepcopy(event))
    state["autonomous_events"] = events[-_EVENT_CAP:]


def _position(value: Any) -> Position | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    return None


def _occupied(state: dict[str, Any], exclude_id: str) -> set[Position]:
    occupied: set[Position] = set()
    for agent_pos in (state.get("agent_positions") or {}).values():
        pos = _position(agent_pos)
        if pos is not None:
            occupied.add(pos)
    for blocked in state.get("blocked") or ():
        pos = _position(blocked)
        if pos is not None:
            occupied.add(pos)
    for oid, record in (state.get("objects") or {}).items():
        if str(oid) == exclude_id or not isinstance(record, dict):
            continue
        if record.get("existence", {}).get("present") is False:
            continue
        pos = _position(record.get("position"))
        if pos is not None:
            occupied.add(pos)
    for record in (state.get("obstacles") or {}).values():
        if not isinstance(record, dict) or record.get("active", True) is False:
            continue
        pos = _position(record.get("position"))
        if pos is not None:
            occupied.add(pos)
    return occupied


def _in_bounds(state: dict[str, Any], pos: Position) -> bool:
    width = int(state.get("width", 1))
    height = int(state.get("height", 1))
    return 0 <= pos[0] < width and 0 <= pos[1] < height


def _ensure_runtime(record: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    runtime = record.get("autonomous_runtime")
    if not isinstance(runtime, dict):
        runtime = {
            "motion_index": 0,
            "ticks_since_move": 0,
            "phase": int(config["motion"].get("phase", 0)),
        }
        record["autonomous_runtime"] = runtime
    return runtime


def _move_object(
    state: dict[str, Any],
    *,
    object_id: str,
    record: dict[str, Any],
    destination: Position,
    clock: int,
    pattern: str,
) -> dict[str, Any] | None:
    before = _position(record.get("position"))
    if before is None or destination == before:
        return None
    if not _in_bounds(state, destination):
        return None
    if destination in _occupied(state, object_id):
        return None
    record["position"] = list(destination)
    event = {
        "kind": "AUTONOMOUS_OBJECT_MOVED",
        "tick": clock,
        "object_id": object_id,
        "from": list(before),
        "to": list(destination),
        "pattern": pattern,
        "provenance": CausalProvenance.AUTONOMOUS_OBJECT.value,
    }
    append_autonomous_event(state, event)
    return event


def _advance_motion(
    state: dict[str, Any],
    *,
    object_id: str,
    record: dict[str, Any],
    config: dict[str, Any],
    clock: int,
    rng: DeterministicRandom,
) -> dict[str, Any] | None:
    motion = config["motion"]
    pattern = motion["pattern"]
    if pattern == MotionPattern.NONE.value:
        return None
    runtime = _ensure_runtime(record, config)
    runtime["ticks_since_move"] = int(runtime.get("ticks_since_move", 0)) + 1
    period = int(motion["period_ticks"])
    if runtime["ticks_since_move"] < period:
        return None
    runtime["ticks_since_move"] = 0
    current = _position(record.get("position"))
    if current is None:
        return None

    destination: Position | None = None
    if pattern == MotionPattern.PERIODIC_ROUTE.value:
        route = motion.get("route") or []
        if len(route) < 2:
            return None
        index = int(runtime.get("motion_index", 0)) % len(route)
        next_index = (index + 1) % len(route)
        destination = (int(route[next_index][0]), int(route[next_index][1]))
        runtime["motion_index"] = next_index
    elif pattern == MotionPattern.OSCILLATE.value:
        route = motion.get("route") or []
        if len(route) < 2:
            return None
        # phase 0 -> toward route[1], 1 -> toward route[0]
        phase = int(runtime.get("phase", 0)) % 2
        target = route[1] if phase == 0 else route[0]
        destination = (int(target[0]), int(target[1]))
        runtime["phase"] = 1 - phase
    elif pattern == MotionPattern.BOUNDED_WANDER.value:
        step = int(motion.get("step", 1))
        candidates = [
            (current[0] + dx, current[1] + dy)
            for dx, dy in ((step, 0), (-step, 0), (0, step), (0, -step), (0, 0))
        ]
        bound_min = motion.get("bound_min")
        bound_max = motion.get("bound_max")
        filtered = []
        for cand in candidates:
            if not _in_bounds(state, cand):
                continue
            if bound_min is not None and (
                cand[0] < int(bound_min[0]) or cand[1] < int(bound_min[1])
            ):
                continue
            if bound_max is not None and (
                cand[0] > int(bound_max[0]) or cand[1] > int(bound_max[1])
            ):
                continue
            filtered.append(cand)
        if not filtered:
            return None
        # Deterministic choice from seeded RNG.
        pick = filtered[int(rng.random() * len(filtered)) % len(filtered)]
        destination = pick
    if destination is None:
        return None
    return _move_object(
        state,
        object_id=object_id,
        record=record,
        destination=destination,
        clock=clock,
        pattern=pattern,
    )


def _advance_state_cycle(
    state: dict[str, Any],
    *,
    object_id: str,
    record: dict[str, Any],
    config: dict[str, Any],
    clock: int,
) -> dict[str, Any] | None:
    cycle = config.get("state_cycle")
    if not isinstance(cycle, dict):
        return None
    field = str(cycle["field"])
    if field not in record:
        return None
    period = int(cycle["period_ticks"])
    amplitude = float(cycle["amplitude"])
    center = cycle.get("center")
    if center is None:
        center = float(record.get(f"max_{field}", record.get(field, 0.0)))
    center = float(center)
    phase = int(cycle.get("phase", 0))
    # Triangle-ish oscillation via tick phase.
    t = (clock + phase) % (2 * period)
    if t < period:
        value = center - amplitude + (2 * amplitude * t / period)
    else:
        value = center + amplitude - (2 * amplitude * (t - period) / period)
    capacity = float(record.get(f"max_{field}", center + abs(amplitude)))
    value = max(0.0, min(capacity, value))
    before = float(record.get(field, 0.0))
    if abs(before - value) < 1e-12:
        return None
    record[field] = value
    mutable = record.get("mutable_state")
    if isinstance(mutable, dict) and field in mutable:
        mutable[field] = value
    event = {
        "kind": "AUTONOMOUS_OBJECT_STATE_CYCLE",
        "tick": clock,
        "object_id": object_id,
        "field": field,
        "before": before,
        "after": value,
        "provenance": CausalProvenance.AUTONOMOUS_OBJECT.value,
    }
    append_autonomous_event(state, event)
    return event


def advance_autonomous_dynamics(
    state: dict[str, Any],
    *,
    rng: DeterministicRandom,
    enabled: bool,
) -> list[dict[str, Any]]:
    """Advance per-object autonomous processes. No-op when disabled."""
    # Prefer existence_clock: advanced earlier in the same transition_action.
    clock = int(state.get("existence_clock", state.get("tick", 0)))
    if not enabled:
        state["causal_provenance_tick"] = {
            "tick": clock,
            "enabled": False,
            "events": [],
            "categories": [],
        }
        return []

    updates: list[dict[str, Any]] = []
    objects = state.get("objects")
    if not isinstance(objects, dict):
        objects = {}
    for object_id, record in sorted(objects.items()):
        if not isinstance(record, dict):
            continue
        existence = record.get("existence")
        if isinstance(existence, dict) and existence.get("present") is False:
            continue
        raw = record.get("autonomous")
        if not isinstance(raw, dict):
            continue
        config = normalize_autonomous(raw)
        if not config["enabled"]:
            continue
        moved = _advance_motion(
            state,
            object_id=str(object_id),
            record=record,
            config=config,
            clock=clock,
            rng=rng,
        )
        if moved is not None:
            updates.append(moved)
        cycled = _advance_state_cycle(
            state,
            object_id=str(object_id),
            record=record,
            config=config,
            clock=clock,
        )
        if cycled is not None:
            updates.append(cycled)

    categories = sorted({str(item.get("provenance")) for item in updates})
    state["causal_provenance_tick"] = {
        "tick": clock,
        "enabled": True,
        "events": deepcopy(updates),
        "categories": categories,
        "autonomous_event_count": len(updates),
    }
    return updates


def measure_causal_experience(
    *,
    observations: list[dict[str, Any]],
    actions: list[str],
    autonomous_events: list[dict[str, Any]],
    body_deltas: list[dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Observer-only structural metrics. Not an interestingness score."""
    body_deltas = body_deltas or []
    passive_transitions = 0
    active_transitions = 0
    unique_obs = set()
    unique_deltas = set()
    wait_body_changes = 0
    for index, obs in enumerate(observations):
        signature = repr(sorted((obs or {}).items())) if isinstance(obs, dict) else repr(obs)
        unique_obs.add(signature)
        if index == 0:
            continue
        prev = observations[index - 1]
        delta = repr((prev, obs))
        unique_deltas.add(delta)
        changed = prev != obs
        action = actions[index - 1] if index - 1 < len(actions) else "WAIT"
        if changed and action == "WAIT":
            passive_transitions += 1
        elif changed:
            active_transitions += 1
    for index, delta in enumerate(body_deltas):
        action = actions[index] if index < len(actions) else "WAIT"
        if action == "WAIT" and any(abs(float(v)) > 1e-12 for v in delta.values()):
            wait_body_changes += 1
    auto_moves = sum(1 for e in autonomous_events if e.get("kind") == "AUTONOMOUS_OBJECT_MOVED")
    auto_states = sum(1 for e in autonomous_events if e.get("kind") == "AUTONOMOUS_OBJECT_STATE_CYCLE")
    return {
        "observation_count": len(observations),
        "unique_observations": len(unique_obs),
        "unique_observation_deltas": len(unique_deltas),
        "passive_observation_transitions": passive_transitions,
        "active_observation_transitions": active_transitions,
        "body_state_deltas_during_wait": wait_body_changes,
        "autonomous_object_movements": auto_moves,
        "autonomous_object_state_transitions": auto_states,
        "autonomous_event_count": len(autonomous_events),
        "wait_frequency": sum(1 for a in actions if a == "WAIT") / max(1, len(actions)),
        "move_frequency": sum(1 for a in actions if a.startswith("MOVE:")) / max(1, len(actions)),
        "interaction_frequency": sum(
            1 for a in actions if a.startswith(("USE:", "TAKE:", "PUSH:", "RELEASE:"))
        )
        / max(1, len(actions)),
    }
