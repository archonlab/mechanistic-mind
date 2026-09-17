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


HYPOTHESIS_ID = "H004-REOPEN-EXPLORATION"


def _other(action: str) -> str:
    return "CHOOSE_B" if action == "CHOOSE_A" else "CHOOSE_A"


class RandomExplorationMechanism(Mechanism):
    """Best-seen memory plus fixed-probability exploration."""

    mechanism_id = "H004-RANDOM-EXPLORATION"
    version = "0.1.0"

    def __init__(self, epsilon: float = 0.25) -> None:
        if not (0.0 <= epsilon <= 1.0):
            raise ValueError("epsilon must be within [0, 1]")
        self.epsilon = float(epsilon)

    def process(self, context: MechanismContext) -> MechanismOutput:
        state = context.mechanism_state
        phase = state.get("phase", "PROBE_A")
        best_action = state.get("best_action")
        best_outcome = state.get("best_outcome")

        last_action = context.observation.data.get("last_action")
        last_outcome = context.observation.data.get("last_outcome")

        updates: list[StateUpdate] = []

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
            mode = "INITIAL_PROBE_A"
        elif phase == "PROBE_B":
            selected = "CHOOSE_B"
            next_phase = "EXPLOIT"
            mode = "INITIAL_PROBE_B"
        else:
            next_phase = "EXPLOIT"
            exploit = best_action or "CHOOSE_A"
            if context.random_value < self.epsilon:
                selected = _other(exploit)
                mode = "RANDOM_EXPLORE"
            else:
                selected = exploit
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
                "epsilon": self.epsilon,
                "random_value": context.random_value,
            },
        )


class DropTriggeredExplorationMechanism(Mechanism):
    """Probe the alternative only when the exploited outcome deteriorates."""

    mechanism_id = "H004-DROP-TRIGGERED"
    version = "0.1.0"

    def __init__(self, drop_threshold: float = 0.75) -> None:
        if drop_threshold < 0:
            raise ValueError("drop_threshold must be >= 0")
        self.drop_threshold = float(drop_threshold)

    def process(self, context: MechanismContext) -> MechanismOutput:
        state = context.mechanism_state
        phase = state.get("phase", "PROBE_A")
        best_action = state.get("best_action")
        best_outcome = state.get("best_outcome")
        reference_outcome = state.get("reference_outcome")

        last_action = context.observation.data.get("last_action")
        last_outcome = context.observation.data.get("last_outcome")
        updates: list[StateUpdate] = []

        # Best-seen bookkeeping is skipped while VERIFY_ALTERNATIVE handles
        # the probe outcome itself. This preserves the fail-closed invariant:
        # one mechanism may request at most one write per state target per tick.
        if (
            phase != "VERIFY_ALTERNATIVE"
            and last_action in {"CHOOSE_A", "CHOOSE_B"}
            and last_outcome is not None
        ):
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
            mode = "INITIAL_PROBE_A"

        elif phase == "PROBE_B":
            selected = "CHOOSE_B"
            next_phase = "EXPLOIT"
            mode = "INITIAL_PROBE_B"

        elif phase == "VERIFY_ALTERNATIVE":
            # We are now observing the consequence of the alternative probe.
            alt_outcome = (
                float(last_outcome)
                if last_outcome is not None
                else float("-inf")
            )
            prior_reference = (
                float(reference_outcome)
                if reference_outcome is not None
                else float("-inf")
            )

            if alt_outcome > prior_reference:
                selected = last_action or (best_action or "CHOOSE_A")
                best_action = selected
                best_outcome = alt_outcome
                reference_outcome = alt_outcome
                updates.extend(
                    [
                        StateUpdate.mechanism_state("best_action", best_action),
                        StateUpdate.mechanism_state("best_outcome", best_outcome),
                        StateUpdate.mechanism_state(
                            "reference_outcome",
                            reference_outcome,
                        ),
                    ]
                )
                mode = "SWITCH_AFTER_BETTER_PROBE"
            else:
                selected = best_action or "CHOOSE_A"
                mode = "RETURN_AFTER_FAILED_PROBE"

            next_phase = "EXPLOIT"

        else:
            exploit = best_action or "CHOOSE_A"

            if reference_outcome is None and best_outcome is not None:
                reference_outcome = float(best_outcome)
                updates.append(
                    StateUpdate.mechanism_state(
                        "reference_outcome",
                        reference_outcome,
                    )
                )

            deterioration = False
            if (
                last_action == exploit
                and last_outcome is not None
                and reference_outcome is not None
            ):
                deterioration = (
                    float(last_outcome)
                    < float(reference_outcome) - self.drop_threshold
                )

            if deterioration:
                selected = _other(exploit)
                next_phase = "VERIFY_ALTERNATIVE"
                mode = "DROP_TRIGGERED_PROBE"
            else:
                selected = exploit
                next_phase = "EXPLOIT"
                mode = "EXPLOIT_STABLE"

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
                "reference_outcome": reference_outcome,
                "drop_threshold": self.drop_threshold,
            },
        )


@dataclass(frozen=True, slots=True)
class H004Condition:
    condition: str
    mechanism_id: str
    ticks: int
    reversal_after: int
    pre_optimal_rate: float
    post_optimal_rate: float
    first_post_a_tick: int | None
    post_a: int
    post_b: int
    cumulative_outcome: float
    oracle_outcome: float
    regret: float
    exploration_events: int
    observer_ticks: int
    archon_observations: int
    archon_events: int


@dataclass(frozen=True, slots=True)
class H004Result:
    hypothesis_id: str
    statement: str
    random_exploration: H004Condition
    drop_triggered: H004Condition
    status: str
    interpretation: str
    observed: dict[str, Any]
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
            "random_exploration": dc(self.random_exploration),
            "drop_triggered": dc(self.drop_triggered),
            "status": self.status,
            "interpretation": self.interpretation,
            "observed": dict(self.observed),
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
) -> H004Condition:
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
            "reversal_after": world.reversal_after,
        },
    )

    engine.run(ticks)
    engine.close()

    actions = [
        record.actions["A001"]["kind"]
        for record in canonical_sink.records
    ]
    signals = [
        next(iter(record.signals["A001"].values()))
        for record in canonical_sink.records
    ]

    pre = actions[: world.reversal_after]
    post = actions[world.reversal_after :]

    pre_optimal_rate = pre.count("CHOOSE_B") / max(1, len(pre))
    post_optimal_rate = post.count("CHOOSE_A") / max(1, len(post))

    first_post_a_tick = None
    for offset, action in enumerate(post):
        if action == "CHOOSE_A":
            first_post_a_tick = world.reversal_after + offset
            break

    exploration_events = sum(
        signal.get("selection_mode") in {
            "RANDOM_EXPLORE",
            "DROP_TRIGGERED_PROBE",
        }
        for signal in signals
    )

    oracle_outcome = (
        min(ticks, world.reversal_after) * 3.0
        + max(0, ticks - world.reversal_after) * 4.0
    )
    cumulative = float(
        engine.state.world.variables["cumulative_outcome"]
    )

    return H004Condition(
        condition=condition,
        mechanism_id=mechanism.mechanism_id,
        ticks=ticks,
        reversal_after=world.reversal_after,
        pre_optimal_rate=pre_optimal_rate,
        post_optimal_rate=post_optimal_rate,
        first_post_a_tick=first_post_a_tick,
        post_a=post.count("CHOOSE_A"),
        post_b=post.count("CHOOSE_B"),
        cumulative_outcome=cumulative,
        oracle_outcome=oracle_outcome,
        regret=oracle_outcome - cumulative,
        exploration_events=exploration_events,
        observer_ticks=len(canonical_sink.records),
        archon_observations=len(archon_sink.observations),
        archon_events=len(archon_sink.events),
    )


def run_h004(
    *,
    world_factory,
    ticks: int = 30,
    seed: int = 17,
    epsilon: float = 0.25,
    drop_threshold: float = 0.75,
) -> H004Result:
    random_condition = _run(
        condition="RANDOM_EXPLORATION",
        mechanism=RandomExplorationMechanism(epsilon=epsilon),
        world=world_factory(),
        ticks=ticks,
        seed=seed,
    )
    drop_condition = _run(
        condition="DROP_TRIGGERED_EXPLORATION",
        mechanism=DropTriggeredExplorationMechanism(
            drop_threshold=drop_threshold
        ),
        world=world_factory(),
        ticks=ticks,
        seed=seed,
    )

    random_adapts = random_condition.post_optimal_rate > 0.5
    drop_adapts = drop_condition.post_optimal_rate > 0.5

    if random_adapts and drop_adapts:
        if drop_condition.regret < random_condition.regret:
            status = "BOTH_ADAPT_DROP_TRIGGER_MORE_EFFICIENT"
            interpretation = (
                "Both reopening mechanisms recover after reversal, but the "
                "outcome-drop trigger produces lower regret in this run."
            )
        elif random_condition.regret < drop_condition.regret:
            status = "BOTH_ADAPT_RANDOM_MORE_EFFICIENT"
            interpretation = (
                "Both reopening mechanisms recover after reversal, but fixed "
                "random exploration produces lower regret in this run."
            )
        else:
            status = "BOTH_ADAPT_EQUAL_REGRET"
            interpretation = (
                "Both reopening mechanisms recover with equal regret."
            )
    elif drop_adapts:
        status = "DROP_TRIGGER_DISTINGUISHED"
        interpretation = (
            "Outcome deterioration is sufficient to reopen exploration and "
            "recover after reversal, while the sampled random-exploration "
            "trajectory does not recover within the horizon."
        )
    elif random_adapts:
        status = "RANDOM_EXPLORATION_DISTINGUISHED"
        interpretation = (
            "Fixed random exploration recovers after reversal, while the "
            "drop-triggered mechanism does not."
        )
    else:
        status = "BOTH_FAIL"
        interpretation = (
            "Neither reopening mechanism restores predominantly optimal "
            "post-reversal behavior within the tested horizon."
        )

    return H004Result(
        hypothesis_id=HYPOTHESIS_ID,
        statement=(
            "Reversal adaptation can be restored by reopening alternatives; "
            "a deterioration-triggered probe may do so with less unnecessary "
            "exploration than fixed random exploration."
        ),
        random_exploration=random_condition,
        drop_triggered=drop_condition,
        status=status,
        interpretation=interpretation,
        observed={
            "random_post_optimal_rate":
                random_condition.post_optimal_rate,
            "drop_post_optimal_rate":
                drop_condition.post_optimal_rate,
            "random_regret": random_condition.regret,
            "drop_regret": drop_condition.regret,
            "random_exploration_events":
                random_condition.exploration_events,
            "drop_exploration_events":
                drop_condition.exploration_events,
        },
        limits=(
            "One deterministic reversal world.",
            "Random-exploration result depends on deterministic seed and epsilon.",
            "Drop threshold is hand-specified and not learned.",
            "No noise or gradual regime drift is present.",
            "Lower regret here does not establish biological plausibility.",
        ),
    )
