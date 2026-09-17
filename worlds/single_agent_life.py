from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.agent import Action, Observation
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.environment import World, WorldState

Position = tuple[int, int]


@dataclass(slots=True)
class SingleAgentLifeWorld(World):
    """Spatial life world with partial observation and hidden object outcomes."""

    width: int = 9
    height: int = 7
    vision_radius: int = 1
    state: WorldState = field(default_factory=lambda: WorldState(
        variables={
            "tick": 0,
            "width": 9,
            "height": 7,
            "agent_position": [4, 3],
            "blocked": [[3, 1], [3, 2], [5, 4], [5, 5]],
            "objects": {
                "OBJ-04": {
                    "position": [4, 3], "affordance": "USE",
                    "hidden_role": "RECOVERY_SITE",
                    "outcome": {"energy_delta": 0.16, "hydration_delta": 0.04, "fatigue_delta": -0.24, "progress_delta": 0.0},
                },
                "OBJ-17": {
                    "position": [1, 1], "affordance": "USE",
                    "hidden_role": "ENERGY_RESOURCE",
                    "outcome": {"energy_delta": 0.46, "hydration_delta": 0.02, "fatigue_delta": 0.0, "progress_delta": 0.0},
                },
                "OBJ-23": {
                    "position": [7, 5], "affordance": "USE",
                    "hidden_role": "HYDRATION_RESOURCE",
                    "outcome": {"energy_delta": 0.0, "hydration_delta": 0.52, "fatigue_delta": -0.02, "progress_delta": 0.0},
                },
                "OBJ-31": {
                    "position": [7, 1], "affordance": "USE",
                    "hidden_role": "PROGRESS_SITE",
                    "outcome": {"energy_delta": -0.07, "hydration_delta": -0.05, "fatigue_delta": 0.07, "progress_delta": 1.0},
                },
            },
            "last_action": None,
            "last_consequence": None,
            "total_progress": 0.0,
            "visited_positions": [[4, 3]],
            "visit_counts": {"4,3": 1},
            "object_use_counts": {},
            "movement_count": 0,
        }
    ))

    MOVE_COST = {"energy_delta": -0.012, "hydration_delta": -0.006, "fatigue_delta": 0.012, "progress_delta": 0.0}
    WAIT_COST = {"energy_delta": 0.0, "hydration_delta": 0.0, "fatigue_delta": -0.01, "progress_delta": 0.0}

    def observe(self, state: WorldState, agent_id: str) -> Observation:
        position = self._position(state)
        visible_objects: list[dict[str, Any]] = []
        objects = state.variables.get("objects", {})
        if isinstance(objects, dict):
            for object_id, record in sorted(objects.items()):
                if not isinstance(record, dict):
                    continue
                obj_position = self._tuple_position(record.get("position"))
                if obj_position is None:
                    continue
                if self._manhattan(position, obj_position) <= self.vision_radius:
                    visible_objects.append({
                        "id": str(object_id),
                        "position": list(obj_position),
                        "relative_offset": [obj_position[0] - position[0], obj_position[1] - position[1]],
                        "affordance": str(record.get("affordance") or "USE"),
                    })
        return Observation(data={
            "position": list(position),
            "visible_objects": visible_objects,
            "available_actions": tuple(self._available_actions(state, position)),
            "last_action": state.variables.get("last_action"),
            "last_consequence": deepcopy(state.variables.get("last_consequence")),
            "context": "SPATIAL_LIFE_V01",
        })

    def transition(self, state: WorldState, actions: dict[str, Action], rng: DeterministicRandom) -> WorldState:
        if len(actions) != 1:
            raise ValueError("SingleAgentLifeWorld requires exactly one agent")
        action = next(iter(actions.values()))
        next_state = deepcopy(state)
        position = self._position(next_state)
        available = set(self._available_actions(next_state, position))

        if action.kind not in available:
            consequence = {"energy_delta": -0.005, "hydration_delta": -0.003, "fatigue_delta": 0.005, "progress_delta": 0.0, "invalid_action": 1.0}
        elif action.kind.startswith("MOVE:"):
            destination = self._parse_move(action.kind)
            if destination is None:
                raise ValueError(f"Malformed movement action: {action.kind}")
            position = destination
            next_state.variables["agent_position"] = list(position)
            next_state.variables["movement_count"] = int(next_state.variables.get("movement_count", 0)) + 1
            consequence = deepcopy(self.MOVE_COST)
        elif action.kind.startswith("USE:"):
            object_id = action.kind.split(":", 1)[1]
            objects = next_state.variables.get("objects", {})
            record = objects.get(object_id, {}) if isinstance(objects, dict) else {}
            consequence = deepcopy(record.get("outcome", {}))
            counts = dict(next_state.variables.get("object_use_counts", {}))
            counts[object_id] = int(counts.get(object_id, 0)) + 1
            next_state.variables["object_use_counts"] = counts
        elif action.kind == "WAIT":
            consequence = deepcopy(self.WAIT_COST)
        else:
            raise ValueError(f"Unsupported life-world action: {action.kind}")

        next_state.variables["total_progress"] = float(next_state.variables.get("total_progress", 0.0)) + float(consequence.get("progress_delta", 0.0))
        next_state.variables["last_action"] = action.kind
        next_state.variables["last_consequence"] = consequence
        next_state.variables["tick"] = int(next_state.variables.get("tick", 0)) + 1

        visits = list(next_state.variables.get("visited_positions", []))
        if list(position) not in visits:
            visits.append(list(position))
        next_state.variables["visited_positions"] = visits
        counts = dict(next_state.variables.get("visit_counts", {}))
        key = f"{position[0]},{position[1]}"
        counts[key] = int(counts.get(key, 0)) + 1
        next_state.variables["visit_counts"] = counts
        return next_state

    def _available_actions(self, state: WorldState, position: Position) -> list[str]:
        actions: list[str] = []
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            destination = (position[0] + dx, position[1] + dy)
            if self._is_open(state, destination):
                actions.append(f"MOVE:{destination[0]},{destination[1]}")
        objects = state.variables.get("objects", {})
        if isinstance(objects, dict):
            for object_id, record in sorted(objects.items()):
                if isinstance(record, dict) and self._tuple_position(record.get("position")) == position:
                    actions.append(f"USE:{object_id}")
        actions.append("WAIT")
        return actions

    def _is_open(self, state: WorldState, position: Position) -> bool:
        x, y = position
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        blocked = {tuple(item) for item in state.variables.get("blocked", []) if isinstance(item, list) and len(item) == 2}
        return position not in blocked

    @staticmethod
    def _parse_move(action: str) -> Position | None:
        try:
            payload = action.split(":", 1)[1]
            x_text, y_text = payload.split(",", 1)
            return int(x_text), int(y_text)
        except Exception:
            return None

    @staticmethod
    def _tuple_position(value: Any) -> Position | None:
        if isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(item, int) for item in value):
            return int(value[0]), int(value[1])
        return None

    def _position(self, state: WorldState) -> Position:
        value = self._tuple_position(state.variables.get("agent_position"))
        if value is None:
            raise ValueError("Life world has invalid agent_position")
        return value

    @staticmethod
    def _manhattan(a: Position, b: Position) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
