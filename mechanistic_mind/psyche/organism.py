from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.mechanisms import (
    ActionProposal,
    Mechanism,
    MechanismContext,
    MechanismOutput,
    StateUpdate,
)

from .organism_modules import build_organism_modules, build_sensorimotor_modules
from .runtime import PsycheRuntime
from .state import PsycheState


class SingleOrganismPsycheV03(Mechanism):
    """Whole psyche for Organism × World Foundation.

    The mechanism does not own objective body physiology. It only receives
    interoceptive and environmental signals through Observation.
    """

    mechanism_id = "PSYCHE-SINGLE-ORGANISM-V03"
    version = "0.3.4"

    def __init__(
        self,
        *,
        modules=None,
        initial_state: PsycheState | None = None,
    ) -> None:
        self.modules = tuple(
            modules
            if modules is not None
            else build_organism_modules()
        )
        self.runtime = PsycheRuntime(self.modules)
        self.initial_state = (
            initial_state.clone()
            if initial_state is not None
            else PsycheState.initial_organism_v03()
        )

    def process(
        self,
        context: MechanismContext,
    ) -> MechanismOutput:
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
                    "foundation": "ORGANISM_WORLD_V034",
                    "selection": {
                        "action": result.selection.action.kind,
                        "reason": result.selection.reason,
                        "score": result.selection.score,
                        "metadata": deepcopy(
                            result.selection.metadata
                        ),
                    },
                    "internal": deepcopy(result.state.internal),
                    "attention": deepcopy(result.state.attention),
                    "learning": deepcopy(result.state.learning),
                    "memory": deepcopy(result.state.memory),
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
                "psyche_stage_trace": list(
                    result.stage_trace
                ),
                "psyche_module_count": len(
                    self.modules
                ),
                "body_truth_owned_by_psyche": False,
                "developmental": deepcopy(
                    result.state.memory.get("developmental")
                )
                if isinstance(result.state.memory.get("developmental"), dict)
                else None,
            },
        )


class SingleOrganismPsycheV05(SingleOrganismPsycheV03):
    """Organism psyche with continuous experience-structured generation."""

    mechanism_id = "PSYCHE-SENSORIMOTOR-V05"
    version = "0.5.1"

    def __init__(
        self,
        *,
        modules=None,
        initial_state: PsycheState | None = None,
        sensorimotor_config=None,
        developmental=None,
    ) -> None:
        if modules is None:
            modules = build_sensorimotor_modules(
                config=sensorimotor_config,
                developmental=developmental,
            )
        super().__init__(
            modules=modules,
            initial_state=initial_state,
        )
