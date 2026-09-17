from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mechanistic_mind.adapters.archon import (
    ArchonAdapterSink,
    InMemoryArchonSink,
)
from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import Mechanism, MechanismRegistry
from mechanistic_mind.observer import (
    CompositeSink,
    InMemorySink,
    PsychologyObserver,
)
from mechanistic_mind.research.h001_outcome_trace import OutcomeTraceMechanism
from mechanistic_mind.research.h002_simpler_alternative import (
    BestSeenOutcomeMechanism,
)


HYPOTHESIS_ID = "H003-REVERSAL-WORLD"


@dataclass(frozen=True, slots=True)
class ReversalCondition:
    condition: str
    mechanism_id: str
    ticks: int
    reversal_after: int

    pre_a: int
    pre_b: int
    post_a: int
    post_b: int

    pre_optimal_rate: float
    post_optimal_rate: float
    post_switch_tick: int | None
    adapted: bool

    cumulative_outcome: float
    oracle_outcome: float
    regret: float

    final_mechanism_state: dict[str, Any]
    observer_ticks: int
    archon_observations: int
    archon_events: int


@dataclass(frozen=True, slots=True)
class H003Result:
    hypothesis_id: str
    statement: str
    running_means: ReversalCondition
    best_seen: ReversalCondition
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
            "running_means": dc(self.running_means),
            "best_seen": dc(self.best_seen),
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
) -> ReversalCondition:
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

    action_kinds = [
        record.actions["A001"]["kind"]
        for record in canonical_sink.records
    ]

    pre_actions = action_kinds[: world.reversal_after]
    post_actions = action_kinds[world.reversal_after :]

    pre_a = pre_actions.count("CHOOSE_A")
    pre_b = pre_actions.count("CHOOSE_B")
    post_a = post_actions.count("CHOOSE_A")
    post_b = post_actions.count("CHOOSE_B")

    pre_optimal_rate = (
        pre_b / len(pre_actions) if pre_actions else 0.0
    )
    post_optimal_rate = (
        post_a / len(post_actions) if post_actions else 0.0
    )

    # First post-reversal selection of the new optimal action A.
    post_switch_tick = None
    for offset, action in enumerate(post_actions):
        if action == "CHOOSE_A":
            post_switch_tick = world.reversal_after + offset
            break

    adapted = post_optimal_rate > 0.5

    pre_oracle = min(ticks, world.reversal_after) * 3.0
    post_ticks = max(0, ticks - world.reversal_after)
    post_oracle = post_ticks * 4.0
    oracle_outcome = pre_oracle + post_oracle

    final_mechanism_state = dict(
        engine.state.agents["A001"]
        .mechanism_states.get(mechanism.mechanism_id, {})
    )

    cumulative = float(
        engine.state.world.variables["cumulative_outcome"]
    )

    return ReversalCondition(
        condition=condition,
        mechanism_id=mechanism.mechanism_id,
        ticks=ticks,
        reversal_after=world.reversal_after,
        pre_a=pre_a,
        pre_b=pre_b,
        post_a=post_a,
        post_b=post_b,
        pre_optimal_rate=pre_optimal_rate,
        post_optimal_rate=post_optimal_rate,
        post_switch_tick=post_switch_tick,
        adapted=adapted,
        cumulative_outcome=cumulative,
        oracle_outcome=oracle_outcome,
        regret=oracle_outcome - cumulative,
        final_mechanism_state=final_mechanism_state,
        observer_ticks=len(canonical_sink.records),
        archon_observations=len(archon_sink.observations),
        archon_events=len(archon_sink.events),
    )


def run_h003(
    *,
    world_factory,
    ticks: int = 18,
    seed: int = 17,
) -> H003Result:
    running_means = _run(
        condition="RUNNING_MEANS",
        mechanism=OutcomeTraceMechanism(),
        world=world_factory(),
        ticks=ticks,
        seed=seed,
    )

    best_seen = _run(
        condition="BEST_SEEN_ONLY",
        mechanism=BestSeenOutcomeMechanism(),
        world=world_factory(),
        ticks=ticks,
        seed=seed,
    )

    neither_adapts = (
        not running_means.adapted
        and not best_seen.adapted
    )

    if neither_adapts:
        status = "BOTH_MODELS_FAIL_REVERSAL_ADAPTATION"
        interpretation = (
            "Both candidate mechanisms remain locked onto the formerly "
            "advantageous option after the contingency reversal. The reversal "
            "world therefore exposes a missing process shared by both models: "
            "some mechanism for renewed exploration, recency weighting, "
            "forgetting, or change detection."
        )
    elif running_means.adapted and not best_seen.adapted:
        status = "RUNNING_MEANS_DISTINGUISHED"
        interpretation = (
            "The reversal world distinguishes the richer running-means model: "
            "it adapts while the simpler best-seen mechanism does not."
        )
    elif best_seen.adapted and not running_means.adapted:
        status = "BEST_SEEN_DISTINGUISHED"
        interpretation = (
            "The simpler best-seen mechanism adapts while running means do not."
        )
    else:
        status = "BOTH_MODELS_ADAPT"
        interpretation = (
            "Both mechanisms adapt in this reversal world, so the environment "
            "does not yet distinguish them."
        )

    return H003Result(
        hypothesis_id=HYPOTHESIS_ID,
        statement=(
            "A hidden reversal of action-outcome contingencies can distinguish "
            "candidate mechanisms that are behaviorally equivalent in a "
            "stationary environment."
        ),
        running_means=running_means,
        best_seen=best_seen,
        status=status,
        interpretation=interpretation,
        observed={
            "running_means_post_optimal_rate":
                running_means.post_optimal_rate,
            "best_seen_post_optimal_rate":
                best_seen.post_optimal_rate,
            "running_means_regret":
                running_means.regret,
            "best_seen_regret":
                best_seen.regret,
        },
        limits=(
            "No forced exploration is supplied after reversal.",
            "The reversal is deterministic and abrupt.",
            "The agent receives no explicit regime-change signal.",
            "Failure here identifies missing adaptive machinery but does not "
            "uniquely determine which machinery is required.",
        ),
    )
