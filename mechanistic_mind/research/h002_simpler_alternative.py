from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mechanistic_mind.adapters.archon import (
    ArchonAdapterSink,
    InMemoryArchonSink,
)
from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import (
    ActionProposal,
    Mechanism,
    MechanismContext,
    MechanismOutput,
    MechanismRegistry,
    StateUpdate,
)
from mechanistic_mind.observer import (
    CompositeSink,
    InMemorySink,
    PsychologyObserver,
)
from mechanistic_mind.research.h001_outcome_trace import OutcomeTraceMechanism


HYPOTHESIS_ID = "H002-SIMPLER-ALTERNATIVE"


class BestSeenOutcomeMechanism(Mechanism):
    """Simpler competitor to running empirical means.

    The mechanism probes A, then B, stores only the best observed action/outcome,
    and thereafter repeats that action.

    It does not maintain action-specific counts or running averages.
    """

    mechanism_id = "H002-BEST-SEEN"
    version = "0.1.0"

    def process(self, context: MechanismContext) -> MechanismOutput:
        state = context.mechanism_state

        phase = state.get("phase", "PROBE_A")
        best_action = state.get("best_action")
        best_outcome = state.get("best_outcome")

        last_action = context.observation.data.get("last_action")
        last_outcome = context.observation.data.get("last_outcome")

        updates: list[StateUpdate] = []

        # Fold the previous consequence into a single best-so-far record.
        if last_action in {"CHOOSE_A", "CHOOSE_B"} and last_outcome is not None:
            outcome = float(last_outcome)
            if best_outcome is None or outcome > float(best_outcome):
                best_action = last_action
                best_outcome = outcome
                updates.extend(
                    [
                        StateUpdate.mechanism_state("best_action", best_action),
                        StateUpdate.mechanism_state("best_outcome", best_outcome),
                    ]
                )

        if phase == "PROBE_A":
            selected = "CHOOSE_A"
            next_phase = "PROBE_B"
            mode = "PROBE_A"
        elif phase == "PROBE_B":
            selected = "CHOOSE_B"
            next_phase = "EXPLOIT"
            mode = "PROBE_B"
        else:
            selected = best_action or "CHOOSE_A"
            next_phase = "EXPLOIT"
            mode = "EXPLOIT_BEST_SEEN"

        if next_phase != phase:
            updates.append(
                StateUpdate.mechanism_state("phase", next_phase)
            )

        return MechanismOutput(
            proposals=(
                ActionProposal(
                    source_mechanism=self.mechanism_id,
                    action=Action(selected),
                    priority=10,
                ),
            ),
            state_updates=tuple(updates),
            signals={
                "selection_mode": mode,
                "selected_action": selected,
                "best_action": best_action,
                "best_outcome": best_outcome,
            },
        )


@dataclass(frozen=True, slots=True)
class MechanismCondition:
    condition: str
    mechanism_id: str
    ticks: int
    choose_a: int
    choose_b: int
    choose_b_rate: float
    cumulative_outcome: float
    final_mechanism_state: dict[str, Any]
    state_scalar_count: int
    observer_ticks: int
    archon_observations: int
    archon_events: int


@dataclass(frozen=True, slots=True)
class H002Result:
    hypothesis_id: str
    statement: str
    outcome_trace: MechanismCondition
    simpler_alternative: MechanismCondition
    behavioral_difference: dict[str, float]
    complexity_difference: dict[str, int]
    status: str
    interpretation: str
    limits: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        def dc(obj):
            return {
                field: getattr(obj, field)
                for field in obj.__dataclass_fields__
            }

        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "outcome_trace": dc(self.outcome_trace),
            "simpler_alternative": dc(self.simpler_alternative),
            "behavioral_difference": dict(self.behavioral_difference),
            "complexity_difference": dict(self.complexity_difference),
            "status": self.status,
            "interpretation": self.interpretation,
            "limits": list(self.limits),
        }


def _registry(mechanism: Mechanism) -> MechanismRegistry:
    registry = MechanismRegistry()
    registry.register(mechanism)
    return registry


def _run(
    *,
    condition: str,
    mechanism: Mechanism,
    world,
    ticks: int,
    seed: int,
) -> MechanismCondition:
    canonical_sink = InMemorySink()
    archon_sink = InMemoryArchonSink()

    observer = PsychologyObserver(
        CompositeSink(
            (
                canonical_sink,
                ArchonAdapterSink(archon_sink),
            )
        )
    )

    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=_registry(mechanism),
        observer=observer,
        run_config={
            "hypothesis_id": HYPOTHESIS_ID,
            "condition": condition,
            "ticks": ticks,
        },
    )

    engine.run(ticks)
    engine.close()

    choose_a = sum(
        record.actions["A001"]["kind"] == "CHOOSE_A"
        for record in canonical_sink.records
    )
    choose_b = sum(
        record.actions["A001"]["kind"] == "CHOOSE_B"
        for record in canonical_sink.records
    )

    final_state = dict(
        engine.state.agents["A001"]
        .mechanism_states.get(mechanism.mechanism_id, {})
    )

    return MechanismCondition(
        condition=condition,
        mechanism_id=mechanism.mechanism_id,
        ticks=ticks,
        choose_a=choose_a,
        choose_b=choose_b,
        choose_b_rate=choose_b / max(1, choose_a + choose_b),
        cumulative_outcome=float(
            engine.state.world.variables["cumulative_outcome"]
        ),
        final_mechanism_state=final_state,
        state_scalar_count=len(final_state),
        observer_ticks=len(canonical_sink.records),
        archon_observations=len(archon_sink.observations),
        archon_events=len(archon_sink.events),
    )


def run_h002(
    *,
    world_factory,
    ticks: int = 12,
    seed: int = 17,
) -> H002Result:
    outcome_trace = _run(
        condition="RUNNING_MEANS",
        mechanism=OutcomeTraceMechanism(),
        world=world_factory(),
        ticks=ticks,
        seed=seed,
    )

    simpler = _run(
        condition="BEST_SEEN_ONLY",
        mechanism=BestSeenOutcomeMechanism(),
        world=world_factory(),
        ticks=ticks,
        seed=seed,
    )

    delta_b = simpler.choose_b_rate - outcome_trace.choose_b_rate
    delta_outcome = (
        simpler.cumulative_outcome - outcome_trace.cumulative_outcome
    )
    delta_state = (
        simpler.state_scalar_count - outcome_trace.state_scalar_count
    )

    behavior_equivalent = (
        abs(delta_b) < 1e-12
        and abs(delta_outcome) < 1e-12
    )
    simpler_state = simpler.state_scalar_count < outcome_trace.state_scalar_count

    if behavior_equivalent and simpler_state:
        status = "H001_INTERNAL_COMPLEXITY_NOT_NECESSARY_HERE"
        interpretation = (
            "The simpler best-seen mechanism reproduced the same behavior and "
            "outcome while using fewer persistent state scalars. Running means "
            "are therefore not necessary for this deterministic stationary world."
        )
    elif behavior_equivalent:
        status = "BEHAVIORALLY_EQUIVALENT_NO_COMPLEXITY_GAIN"
        interpretation = (
            "The mechanisms were behaviorally equivalent, but the measured "
            "persistent-state complexity did not decrease."
        )
    else:
        status = "SIMPLER_ALTERNATIVE_NOT_EQUIVALENT"
        interpretation = (
            "The simpler mechanism failed to reproduce the H001 behavior exactly."
        )

    return H002Result(
        hypothesis_id=HYPOTHESIS_ID,
        statement=(
            "Running action-specific empirical means are not necessary to "
            "produce the H001 behavioral effect in a deterministic stationary "
            "two-option environment; a best-seen outcome trace is sufficient."
        ),
        outcome_trace=outcome_trace,
        simpler_alternative=simpler,
        behavioral_difference={
            "delta_choose_B_rate_simpler_minus_h001": delta_b,
            "delta_cumulative_outcome_simpler_minus_h001": delta_outcome,
        },
        complexity_difference={
            "h001_persistent_state_scalars": outcome_trace.state_scalar_count,
            "simpler_persistent_state_scalars": simpler.state_scalar_count,
            "delta_scalars_simpler_minus_h001": delta_state,
        },
        status=status,
        interpretation=interpretation,
        limits=(
            "Complexity is measured only as persistent mechanism-state scalar count.",
            "The environment is deterministic and stationary.",
            "Best-seen memory may fail under noise, reversals, or nonstationarity.",
            "Behavioral equivalence here does not imply mechanistic equivalence.",
        ),
    )
