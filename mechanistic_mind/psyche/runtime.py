from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from numbers import Real
from typing import Any, Iterable

from mechanistic_mind.agent import Action, Observation

from .contracts import (
    PsycheActionCandidate,
    PsycheContext,
    PsycheModule,
    PsycheSelection,
    PsycheStage,
    PsycheUpdate,
)
from .state import PsycheState


class PsycheContractError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PsycheRunResult:
    state: PsycheState
    action: Action
    selection: PsycheSelection
    candidates: tuple[PsycheActionCandidate, ...]
    signals: dict[str, dict[str, Any]]
    stage_trace: tuple[str, ...]


class PsycheRuntime:
    """Deterministic staged runtime for one psyche.

    Stage order is explicit. Modules within a stage receive the same stage-start
    state. Conflicting writes within a stage fail closed.
    """

    def __init__(self, modules: Iterable[PsycheModule]) -> None:
        modules = tuple(modules)
        ids = [module.module_id for module in modules]
        if len(ids) != len(set(ids)):
            raise PsycheContractError("Duplicate psyche module_id")

        self.modules = tuple(
            sorted(modules, key=lambda module: (int(module.stage), module.module_id))
        )

    def run(
        self,
        *,
        tick: int,
        agent_id: str,
        observation: Observation,
        state: PsycheState,
        random_value: float,
    ) -> PsycheRunResult:
        current = state.clone()
        candidates: list[PsycheActionCandidate] = []
        signals: dict[str, dict[str, Any]] = {}
        stage_trace: list[str] = []
        selection: PsycheSelection | None = None

        stages = sorted({module.stage for module in self.modules}, key=int)
        for stage in stages:
            stage_modules = tuple(
                module for module in self.modules if module.stage == stage
            )
            stage_state = current.clone()
            stage_candidates = tuple(deepcopy(candidates))
            pending_updates: list[tuple[str, PsycheUpdate]] = []
            pending_candidates: list[PsycheActionCandidate] = []
            pending_selections: list[PsycheSelection] = []

            for module in stage_modules:
                context = PsycheContext(
                    tick=tick,
                    agent_id=agent_id,
                    stage=stage,
                    observation=deepcopy(observation),
                    state=stage_state.clone(),
                    candidates=stage_candidates,
                    random_value=random_value,
                )
                output = module.process(context)
                signals[module.module_id] = deepcopy(output.signals)
                stage_trace.append(f"{stage.name}:{module.module_id}")

                for update in output.updates:
                    pending_updates.append((module.module_id, update))

                for candidate in output.candidates:
                    if candidate.source_module != module.module_id:
                        raise PsycheContractError(
                            "PsycheActionCandidate provenance mismatch: "
                            f"runtime={module.module_id!r}, "
                            f"candidate={candidate.source_module!r}"
                        )
                    pending_candidates.append(candidate)

                if output.selection is not None:
                    if output.selection.source_module != module.module_id:
                        raise PsycheContractError(
                            "PsycheSelection provenance mismatch"
                        )
                    pending_selections.append(output.selection)

            current = self._integrate_updates(current, pending_updates)
            candidates.extend(deepcopy(pending_candidates))

            if pending_selections:
                if len(pending_selections) != 1:
                    raise PsycheContractError(
                        "More than one action selection in the same psyche tick"
                    )
                if selection is not None:
                    raise PsycheContractError(
                        "More than one action-selection stage produced a selection"
                    )
                selection = pending_selections[0]

        if selection is None:
            raise PsycheContractError(
                "Psyche runtime completed without selecting an action"
            )

        return PsycheRunResult(
            state=current,
            action=selection.action,
            selection=selection,
            candidates=tuple(candidates),
            signals=signals,
            stage_trace=tuple(stage_trace),
        )

    def _integrate_updates(
        self,
        state: PsycheState,
        updates: list[tuple[str, PsycheUpdate]],
    ) -> PsycheState:
        next_state = state.clone()
        claimed: dict[tuple[str, str], str] = {}

        for module_id, update in updates:
            target = (update.compartment, update.key)
            if target in claimed:
                raise PsycheContractError(
                    "Same-stage psyche state conflict: "
                    f"{target} written by {claimed[target]} and {module_id}"
                )
            claimed[target] = module_id

            compartment = next_state.compartment(update.compartment)
            if update.operation == "SET":
                compartment[update.key] = deepcopy(update.value)
            elif update.operation == "ADD":
                before = compartment.get(update.key, 0)
                if (
                    isinstance(before, bool)
                    or isinstance(update.value, bool)
                    or not isinstance(before, Real)
                    or not isinstance(update.value, Real)
                ):
                    raise PsycheContractError(
                        f"ADD requires numeric values at {target}"
                    )
                compartment[update.key] = before + update.value
            else:
                raise PsycheContractError(
                    f"Unsupported psyche operation: {update.operation}"
                )

        return next_state
