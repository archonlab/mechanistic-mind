from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from mechanistic_mind.agent.action import Action
from mechanistic_mind.agent.agent import Agent
from mechanistic_mind.environment.world import World
from mechanistic_mind.mechanisms import (
    ActionDecision,
    ActionIntegrator,
    MechanismOutput,
    MechanismRegistry,
    MechanismRuntime,
    StateIntegrator,
)

from .clock import Clock
from .random import DeterministicRandom
from .state import SimulationState, StepResult
from .transitions import build_next_state

if TYPE_CHECKING:
    from mechanistic_mind.observer import PsychologyObserver


def _apply_executed_action_evidence(
    agent_state,
    *,
    selected_action: str,
    executed_action: str,
) -> None:
    """Commit own executed-action evidence into psyche sensorimotor memory.

    Uses execution-layer action token only — no intervention-source labels.
    Mutates agent_state in place after state integration.
    """
    from copy import deepcopy
    from mechanistic_mind.psyche.sensorimotor import (
        SensorimotorStore,
        commit_executed_action,
    )

    for mechanism_id, mstate in list(agent_state.mechanism_states.items()):
        if not isinstance(mstate, dict):
            continue
        psy = mstate.get("psyche")
        if not isinstance(psy, dict):
            continue
        memory = psy.get("memory")
        if not isinstance(memory, dict):
            continue
        sm_raw = memory.get("sensorimotor")
        if not isinstance(sm_raw, dict):
            continue
        store = SensorimotorStore.from_dict(sm_raw)
        # Infer TC config flags from stash if present
        result = commit_executed_action(
            store,
            executed_action,
            selected_action=selected_action,
            config=None,
        )
        memory["sensorimotor"] = store.to_dict()
        working = psy.setdefault("working", {})
        if isinstance(working, dict):
            working["action_execution_evidence"] = deepcopy(result["evidence"])
            working["action_execution_evidence"]["temporal_opened"] = bool(
                result.get("opened_temporal")
            )
            working["action_execution_evidence"]["temporal_action_key"] = result.get(
                "temporal_action_key"
            )
        agent_state.mechanism_states[mechanism_id] = mstate
        return



@dataclass(slots=True)
class Engine:
    """Minimal deterministic simulation runtime."""

    world: World
    agents: dict[str, Agent]
    seed: int = 0
    mechanisms: MechanismRegistry = field(default_factory=MechanismRegistry)
    # Optional private mechanism stacks per agent (Update 4.7).
    mechanisms_by_agent: dict[str, MechanismRegistry] | None = None
    observer: "PsychologyObserver | None" = None
    run_config: dict[str, Any] = field(default_factory=dict)

    clock: Clock = field(init=False)
    rng: DeterministicRandom = field(init=False)
    state: SimulationState = field(init=False)
    mechanism_runtime: MechanismRuntime = field(init=False)
    mechanism_runtimes: dict[str, MechanismRuntime] = field(init=False)
    action_integrator: ActionIntegrator = field(init=False)
    state_integrator: StateIntegrator = field(init=False)

    def __post_init__(self) -> None:
        self.clock = Clock()
        self.rng = DeterministicRandom(self.seed)
        self.state = self._initial_state()
        self.mechanism_runtime = MechanismRuntime(
            self.mechanisms,
            base_seed=self.seed,
        )
        self.mechanism_runtimes = {}
        if self.mechanisms_by_agent:
            for agent_id, registry in self.mechanisms_by_agent.items():
                self.mechanism_runtimes[str(agent_id)] = MechanismRuntime(
                    registry,
                    base_seed=self.seed,
                )
        self.action_integrator = ActionIntegrator()
        self.state_integrator = StateIntegrator()

        if self.observer is not None:
            from mechanistic_mind import __version__

            self.observer.start_run(
                engine_version=__version__,
                seed=self.seed,
                mechanisms=self.mechanisms,
                world_type=type(self.world).__name__,
                agent_ids=sorted(self.agents),
                config=self.run_config,
            )

    def _initial_state(self) -> SimulationState:
        return SimulationState(
            tick=0,
            world=deepcopy(self.world.state),
            agents={
                agent_id: deepcopy(self.agents[agent_id].state)
                for agent_id in sorted(self.agents)
            },
        )

    def observe(self) -> dict:
        return {
            agent_id: self.world.observe(self.state.world, agent_id)
            for agent_id in self.state.agents
        }

    def step(
        self,
        actions: dict[str, Action] | None = None,
    ) -> StepResult:
        state_before = deepcopy(self.state)

        agent_order = sorted(state_before.agents)
        observations = {
            agent_id: self.world.observe(state_before.world, agent_id)
            for agent_id in agent_order
        }

        mechanism_outputs: dict[str, dict[str, MechanismOutput]] = {}
        signals: dict[str, dict[str, dict]] = {}
        action_decisions: dict[str, ActionDecision] = {}

        for agent_id in agent_order:
            observation = observations[agent_id]
            runtime = self.mechanism_runtimes.get(
                agent_id, self.mechanism_runtime
            )
            outputs = runtime.evaluate(
                tick=state_before.tick,
                agent_id=agent_id,
                observation=observation,
                agent_state=state_before.agents[agent_id],
            )
            mechanism_outputs[agent_id] = outputs
            action_decisions[agent_id] = self.action_integrator.decide(outputs)
            signals[agent_id] = {
                mechanism_id: deepcopy(output.signals)
                for mechanism_id, output in outputs.items()
            }

        supplied = actions or {}
        unknown = set(supplied) - set(state_before.agents)
        if unknown:
            raise KeyError(
                f"Actions supplied for unknown agents: {sorted(unknown)}"
            )

        resolved_actions: dict[str, Action] = {}
        action_sources: dict[str, str] = {}

        for agent_id in agent_order:
            if agent_id in supplied:
                resolved_actions[agent_id] = supplied[agent_id]
                action_sources[agent_id] = "EXTERNAL_OVERRIDE"
            else:
                decision = action_decisions[agent_id]
                resolved_actions[agent_id] = decision.action
                if decision.selected_proposal is None:
                    action_sources[agent_id] = "DEFAULT_WAIT"
                else:
                    action_sources[agent_id] = (
                        "MECHANISM:"
                        f"{decision.selected_proposal.source_mechanism}"
                    )

        next_world = self.world.transition(
            state_before.world,
            resolved_actions,
            self.rng,
        )

        next_agents = {}
        applied_state_updates = {}

        for agent_id in agent_order:
            agent_state = state_before.agents[agent_id]
            integration = self.state_integrator.integrate(
                agent_state,
                mechanism_outputs[agent_id],
            )
            next_agents[agent_id] = integration.state
            applied_state_updates[agent_id] = integration.applied
            # Update 4.10.2: bind temporal/performed-action learning to executed action.
            selected_kind = str(action_decisions[agent_id].action.kind)
            executed_kind = str(resolved_actions[agent_id].kind)
            _apply_executed_action_evidence(
                next_agents[agent_id],
                selected_action=selected_kind,
                executed_action=executed_kind,
            )

        self.clock.step()
        self.state = build_next_state(
            state_before,
            world=next_world,
            agents=next_agents,
        )

        result = StepResult(
            state_before=state_before,
            observations=observations,
            mechanism_outputs=mechanism_outputs,
            signals=signals,
            action_decisions=action_decisions,
            actions=resolved_actions,
            action_sources=action_sources,
            applied_state_updates=applied_state_updates,
            state_after=deepcopy(self.state),
        )

        if self.observer is not None:
            self.observer.record_step(result)

        return result

    def run(self, ticks: int) -> SimulationState:
        if ticks < 0:
            raise ValueError("ticks must be >= 0")

        for _ in range(ticks):
            self.step()
        return deepcopy(self.state)

    def close(self) -> None:
        if self.observer is not None and self.observer._started:
            self.observer.end_run(final_tick=self.state.tick)

    def reset(self) -> SimulationState:
        self.clock.reset()
        self.rng.reset()
        self.state = self._initial_state()
        return deepcopy(self.state)
