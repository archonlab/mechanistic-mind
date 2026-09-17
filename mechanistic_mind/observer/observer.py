from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from mechanistic_mind.core.state import StepResult
from mechanistic_mind.mechanisms import MechanismRegistry

from .models import RunMetadata, RunSummary, TickRecord, to_plain
from .sinks import ObserverSink


@dataclass(slots=True)
class PsychologyObserver:
    """Interpretation-free observer for Mechanistic Mind runs.

    It records what happened. Psychological labels and derived metrics belong
    in later analysis layers.
    """

    sink: ObserverSink
    run_id: str | None = None
    compact_ticks: bool = False

    _started: bool = False
    _ticks_recorded: int = 0
    _last_objects: dict[str, Any] | None = None
    _last_obstacles: dict[str, Any] | None = None

    def start_run(
        self,
        *,
        engine_version: str,
        seed: int,
        mechanisms: MechanismRegistry,
        world_type: str,
        agent_ids: list[str] | tuple[str, ...],
        config: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> RunMetadata:
        if self._started:
            raise RuntimeError("Observer run already started")

        self.run_id = run_id or f"MM-{uuid4().hex[:16].upper()}"
        self._started = True
        self._ticks_recorded = 0
        self._last_objects = None
        self._last_obstacles = None

        metadata = RunMetadata(
            run_id=self.run_id,
            engine_version=engine_version,
            seed=seed,
            mechanism_versions={
                mechanism.mechanism_id: mechanism.version
                for mechanism in mechanisms.ordered()
            },
            world_type=world_type,
            agent_ids=tuple(sorted(agent_ids)),
            config=deepcopy(config or {}),
        )
        self.sink.write_run_metadata(metadata)
        return metadata

    def record_step(self, result: StepResult) -> TickRecord:
        if not self._started or self.run_id is None:
            raise RuntimeError("Observer run has not been started")

        before = to_plain(result.state_before)
        after = to_plain(result.state_after)
        outputs = to_plain(result.mechanism_outputs)
        updates = to_plain(result.applied_state_updates)
        if self.compact_ticks:
            before = self._compact_state(before)
            after = self._compact_state(after)
            before_truth = before.get("world", {}).get("variables", {}).get("world", {})
            if isinstance(before_truth, dict):
                before_truth["objects"] = {}
                before_truth["obstacles"] = {}
            after_truth = after.get("world", {}).get("variables", {}).get("world", {})
            if isinstance(after_truth, dict):
                current_objects = after_truth.get("objects", {}) if isinstance(after_truth.get("objects"), dict) else {}
                current_obstacles = after_truth.get("obstacles", {}) if isinstance(after_truth.get("obstacles"), dict) else {}
                after_truth["objects"] = self._mapping_delta(self._last_objects, current_objects)
                after_truth["obstacles"] = self._mapping_delta(self._last_obstacles, current_obstacles)
                after_truth["object_delta"] = self._last_objects is not None
                after_truth["obstacle_delta"] = self._last_obstacles is not None
                self._last_objects = deepcopy(current_objects)
                self._last_obstacles = deepcopy(current_obstacles)
            outputs = self._compact_outputs(outputs)
            updates = {agent_id: [] for agent_id in result.applied_state_updates}
        record = TickRecord(
            run_id=self.run_id,
            tick=result.state_before.tick,
            state_before=before,
            observations=to_plain(result.observations),
            mechanism_outputs=outputs,
            signals=to_plain(result.signals),
            action_decisions=to_plain(result.action_decisions),
            actions=to_plain(result.actions),
            action_sources=deepcopy(result.action_sources),
            applied_state_updates=updates,
            state_after=after,
        )
        self.sink.write_tick(record)
        self._ticks_recorded += 1
        return record

    @staticmethod
    def _compact_state(state: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(state)
        outer = result.get("world", {}).get("variables", {})
        history = outer.get("developmental_history")
        if isinstance(history, list):
            outer["developmental_history"] = history[-1:]
        truth = outer.get("world")
        if isinstance(truth, dict):
            for key in ("action_log", "exogenous_event_log", "delayed_effects"):
                rows = truth.get(key)
                if isinstance(rows, list):
                    truth[key] = rows[-1:]
        agents = result.get("agents", {})
        if isinstance(agents, dict):
            for agent in agents.values():
                states = agent.get("mechanism_states", {}) if isinstance(agent, dict) else {}
                if isinstance(states, dict):
                    for mechanism_state in states.values():
                        if isinstance(mechanism_state, dict) and isinstance(mechanism_state.get("memory"), dict):
                            memory = mechanism_state["memory"]
                            mechanism_state["memory"] = {
                                "mode": memory.get("mode"),
                                "perceptual_activation": memory.get("perceptual_activation"),
                                "last_perceptual_dynamics": memory.get("last_perceptual_dynamics", {}),
                            }
        return result

    @staticmethod
    def _compact_outputs(outputs: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(outputs)
        for agent_outputs in result.values():
            if not isinstance(agent_outputs, dict):
                continue
            for output in agent_outputs.values():
                if isinstance(output, dict):
                    output["state_updates"] = []
                    output["telemetry"] = {"observer_history_access": False}
                    # The same mechanism signals already exist once in the
                    # canonical top-level ``signals`` namespace.
                    output["signals"] = {}
        return result

    @staticmethod
    def _mapping_delta(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
        if previous is None:
            return deepcopy(current)
        return {
            key: deepcopy(value)
            for key, value in current.items()
            if key not in previous or previous[key] != value
        }

    def end_run(self, *, final_tick: int) -> RunSummary:
        if not self._started or self.run_id is None:
            raise RuntimeError("Observer run has not been started")

        summary = RunSummary(
            run_id=self.run_id,
            ticks_recorded=self._ticks_recorded,
            final_tick=final_tick,
            completed=True,
        )
        self.sink.write_run_summary(summary)
        self._started = False
        return summary
