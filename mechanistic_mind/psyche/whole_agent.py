from __future__ import annotations

from copy import deepcopy
from typing import Iterable

from mechanistic_mind.mechanisms import (
    ActionProposal,
    Mechanism,
    MechanismContext,
    MechanismOutput,
    StateUpdate,
)

from .modules import (
    ActionGenerationModule,
    ActionSelectionModule,
    AttentionModule,
    EpisodicMemoryModule,
    GlobalModulationModule,
    GoalMaintenanceModule,
    HabitModule,
    InternalRegulationModule,
    OutcomeLearningModule,
    PerceptionModule,
    PredictionErrorModule,
    PredictionModule,
    SelfModelModule,
    UncertaintyModule,
    ValuationModule,
)
from .runtime import PsycheRuntime
from .state import PsycheState


def build_foundation_modules(
    *,
    disabled: Iterable[str] = (),
):
    disabled = set(disabled)
    modules = (
        InternalRegulationModule(),
        PerceptionModule(),
        AttentionModule(),
        OutcomeLearningModule(),
        EpisodicMemoryModule(),
        PredictionModule(),
        PredictionErrorModule(),
        UncertaintyModule(),
        GoalMaintenanceModule(),
        GlobalModulationModule(),
        SelfModelModule(),
        HabitModule(),
        ValuationModule(),
        ActionGenerationModule(),
        ActionSelectionModule(),
    )
    return tuple(
        module for module in modules if module.module_id not in disabled
    )


class SingleAgentPsycheV01(Mechanism):
    """Minimal whole-psyche candidate for one continuous agent.

    It is presented to the Foundation Engine as one mechanism so the existing
    world/observer/ARCHON contracts remain unchanged. Internally it is a staged,
    ablatable, replaceable collection of candidate processes.
    """

    mechanism_id = "PSYCHE-SINGLE-AGENT-V01"
    version = "0.2.0"

    def __init__(
        self,
        *,
        modules=None,
        initial_state: PsycheState | None = None,
    ) -> None:
        self.modules = tuple(
            modules if modules is not None else build_foundation_modules()
        )
        self.runtime = PsycheRuntime(self.modules)
        self.initial_state = (
            initial_state.clone()
            if initial_state is not None
            else PsycheState.initial_v01()
        )

    def process(self, context: MechanismContext) -> MechanismOutput:
        persisted = context.mechanism_state.get("psyche")
        state = (
            PsycheState.from_dict(persisted)
            if isinstance(persisted, dict)
            else self.initial_state.clone()
        )

        result = self.runtime.run(
            tick=context.tick,
            agent_id=context.agent_id,
            observation=context.observation,
            state=state,
            random_value=context.random_value,
        )

        return MechanismOutput(
            proposals=(
                ActionProposal(
                    source_mechanism=self.mechanism_id,
                    action=result.action,
                    priority=100,
                    weight=1.0,
                    metadata={
                        "selection_reason": result.selection.reason,
                        "selection_score": result.selection.score,
                    },
                ),
            ),
            state_updates=(
                StateUpdate.mechanism_state(
                    "psyche",
                    result.state.to_dict(),
                ),
            ),
            signals={
                "whole_psyche": {
                    "selection": {
                        "action": result.selection.action.kind,
                        "reason": result.selection.reason,
                        "score": result.selection.score,
                        "metadata": deepcopy(result.selection.metadata),
                    },
                    "internal": deepcopy(result.state.internal),
                    "attention": deepcopy(result.state.attention),
                    "predictions": deepcopy(result.state.predictions),
                    "prediction_errors": deepcopy(
                        result.state.prediction_errors
                    ),
                    "uncertainty": deepcopy(result.state.uncertainty),
                    "goals": deepcopy(result.state.goals),
                    "global_state": deepcopy(result.state.global_state),
                    "self_model": deepcopy(result.state.self_model),
                    "habits": deepcopy(result.state.habits),
                    "values": deepcopy(result.state.values),
                    "stage_trace": list(result.stage_trace),
                    "module_versions": {
                        module.module_id: module.version
                        for module in self.modules
                    },
                }
            },
            telemetry={
                "psyche_stage_trace": list(result.stage_trace),
                "psyche_module_count": len(self.modules),
            },
        )
