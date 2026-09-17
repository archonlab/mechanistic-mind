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


HYPOTHESIS_ID = "H001-OUTCOME-TRACE"


class AlternatingProbeMechanism(Mechanism):
    """Control mechanism with no action-outcome memory.

    It deterministically alternates between the two available actions.
    """

    mechanism_id = "H001-CONTROL-ALTERNATOR"
    version = "0.1.0"

    def process(self, context: MechanismContext) -> MechanismOutput:
        action_kind = "CHOOSE_A" if context.tick % 2 == 0 else "CHOOSE_B"
        return MechanismOutput(
            proposals=(
                ActionProposal(
                    source_mechanism=self.mechanism_id,
                    action=Action(action_kind),
                    priority=10,
                ),
            ),
            signals={
                "selection_mode": "ALTERNATE",
                "selected_action": action_kind,
            },
        )


class OutcomeTraceMechanism(Mechanism):
    """Candidate mechanism that persists action-outcome estimates.

    It samples each option once, then chooses the option with the larger
    empirical mean. This is deliberately minimal and deterministic.
    """

    mechanism_id = "H001-OUTCOME-TRACE"
    version = "0.1.0"

    def process(self, context: MechanismContext) -> MechanismOutput:
        state = context.mechanism_state

        count_a = int(state.get("count_A", 0))
        count_b = int(state.get("count_B", 0))
        value_a = float(state.get("mean_A", 0.0))
        value_b = float(state.get("mean_B", 0.0))

        last_action = context.observation.data.get("last_action")
        last_outcome = context.observation.data.get("last_outcome")

        updates: list[StateUpdate] = []

        # Incorporate the consequence of the previous action into a running mean.
        if last_action == "CHOOSE_A" and last_outcome is not None:
            new_count_a = count_a + 1
            new_value_a = value_a + (
                float(last_outcome) - value_a
            ) / new_count_a
            count_a = new_count_a
            value_a = new_value_a
            updates.extend(
                [
                    StateUpdate.mechanism_state("count_A", count_a),
                    StateUpdate.mechanism_state("mean_A", value_a),
                ]
            )
        elif last_action == "CHOOSE_B" and last_outcome is not None:
            new_count_b = count_b + 1
            new_value_b = value_b + (
                float(last_outcome) - value_b
            ) / new_count_b
            count_b = new_count_b
            value_b = new_value_b
            updates.extend(
                [
                    StateUpdate.mechanism_state("count_B", count_b),
                    StateUpdate.mechanism_state("mean_B", value_b),
                ]
            )

        # Minimal deterministic exploration: sample each option once.
        if count_a == 0:
            selected = "CHOOSE_A"
            mode = "PROBE_A"
        elif count_b == 0:
            selected = "CHOOSE_B"
            mode = "PROBE_B"
        elif value_b > value_a:
            selected = "CHOOSE_B"
            mode = "EXPLOIT_ESTIMATE"
        else:
            selected = "CHOOSE_A"
            mode = "EXPLOIT_ESTIMATE"

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
                "estimated_mean_A": value_a,
                "estimated_mean_B": value_b,
                "samples_A": count_a,
                "samples_B": count_b,
            },
        )


@dataclass(frozen=True, slots=True)
class ConditionObservation:
    condition: str
    ticks: int
    choose_a: int
    choose_b: int
    choose_b_rate: float
    cumulative_outcome: float
    observer_ticks: int
    archon_observations: int
    archon_events: int
    action_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class H001Result:
    hypothesis_id: str
    statement: str
    control: ConditionObservation
    treatment: ConditionObservation
    observed_effect: dict[str, float]
    interpretation: str
    status: str
    limits: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "control": self.control.__dict__
            if hasattr(self.control, "__dict__")
            else {
                field: getattr(self.control, field)
                for field in self.control.__dataclass_fields__
            },
            "treatment": self.treatment.__dict__
            if hasattr(self.treatment, "__dict__")
            else {
                field: getattr(self.treatment, field)
                for field in self.treatment.__dataclass_fields__
            },
            "observed_effect": dict(self.observed_effect),
            "interpretation": self.interpretation,
            "status": self.status,
            "limits": list(self.limits),
        }


def _registry(mechanism: Mechanism) -> MechanismRegistry:
    registry = MechanismRegistry()
    registry.register(mechanism)
    return registry


def _run_condition(
    *,
    condition: str,
    mechanism: Mechanism,
    world,
    ticks: int,
    seed: int,
) -> ConditionObservation:
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
        1
        for record in canonical_sink.records
        if record.actions["A001"]["kind"] == "CHOOSE_A"
    )
    choose_b = sum(
        1
        for record in canonical_sink.records
        if record.actions["A001"]["kind"] == "CHOOSE_B"
    )

    decision_count = choose_a + choose_b
    choose_b_rate = (
        choose_b / decision_count if decision_count else 0.0
    )

    return ConditionObservation(
        condition=condition,
        ticks=ticks,
        choose_a=choose_a,
        choose_b=choose_b,
        choose_b_rate=choose_b_rate,
        cumulative_outcome=float(
            engine.state.world.variables["cumulative_outcome"]
        ),
        observer_ticks=len(canonical_sink.records),
        archon_observations=len(archon_sink.observations),
        archon_events=len(archon_sink.events),
        action_sources=tuple(
            record.action_sources["A001"]
            for record in canonical_sink.records
        ),
    )


def run_h001(
    *,
    world_factory,
    ticks: int = 12,
    seed: int = 17,
) -> H001Result:
    """Run the first paired diagnostic hypothesis test."""

    control = _run_condition(
        condition="CONTROL_NO_OUTCOME_TRACE",
        mechanism=AlternatingProbeMechanism(),
        world=world_factory(),
        ticks=ticks,
        seed=seed,
    )
    treatment = _run_condition(
        condition="TREATMENT_OUTCOME_TRACE",
        mechanism=OutcomeTraceMechanism(),
        world=world_factory(),
        ticks=ticks,
        seed=seed,
    )

    delta_b = treatment.choose_b_rate - control.choose_b_rate
    delta_outcome = (
        treatment.cumulative_outcome - control.cumulative_outcome
    )

    supported = delta_b > 0 and delta_outcome > 0

    return H001Result(
        hypothesis_id=HYPOTHESIS_ID,
        statement=(
            "A persistent action-outcome trace is sufficient, in this "
            "diagnostic environment, to shift choice occupancy toward the "
            "higher-yield option after limited exploration."
        ),
        control=control,
        treatment=treatment,
        observed_effect={
            "delta_choose_B_rate": delta_b,
            "delta_cumulative_outcome": delta_outcome,
        },
        interpretation=(
            "The candidate mechanism changed behavior in the predicted "
            "direction under a fixed asymmetric environment."
            if supported
            else
            "The predicted behavioral divergence was not observed."
        ),
        status=(
            "SUPPORTED_IN_DIAGNOSTIC_WORLD"
            if supported
            else "NOT_SUPPORTED_IN_DIAGNOSTIC_WORLD"
        ),
        limits=(
            "Deterministic two-option environment.",
            "Single agent.",
            "No stochastic outcomes or transfer test.",
            "This supports the mechanism-world claim only; it does not "
            "establish a human psychological mechanism.",
        ),
    )
