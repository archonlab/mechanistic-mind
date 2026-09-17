from copy import deepcopy
from dataclasses import dataclass
from numbers import Real
from typing import Any

from mechanistic_mind.agent import AgentState

from .base import MechanismOutput, StateUpdate


class StateIntegrationError(RuntimeError):
    """Base class for fail-closed state integration errors."""


class StateValidationError(StateIntegrationError):
    """Raised when a requested update violates the state-update contract."""


class StateConflictError(StateIntegrationError):
    """Raised when multiple updates compete for the same target in one tick."""


@dataclass(frozen=True, slots=True)
class AppliedStateUpdate:
    """Auditable record of one accepted state change."""

    source_mechanism: str
    scope: str
    key: str
    operation: str
    before: Any
    after: Any


@dataclass(frozen=True, slots=True)
class StateIntegrationResult:
    state: AgentState
    applied: tuple[AppliedStateUpdate, ...]


@dataclass(slots=True)
class StateIntegrator:
    """Validate and apply mechanism-requested state changes.

    v0.0.4 deliberately fails closed on same-tick write conflicts. We can add
    explicit compositional semantics later, but we do not silently invent them.
    """

    def integrate(
        self,
        current: AgentState,
        outputs: dict[str, MechanismOutput],
    ) -> StateIntegrationResult:
        next_state = deepcopy(current)
        applied: list[AppliedStateUpdate] = []
        claimed_targets: set[tuple[str, str, str]] = set()

        for mechanism_id in sorted(outputs):
            output = outputs[mechanism_id]

            for update in output.state_updates:
                self._validate_update(update)

                namespace = (
                    mechanism_id
                    if update.scope == "MECHANISM_STATE"
                    else "__AGENT__"
                )
                target = (update.scope, namespace, update.key)

                if target in claimed_targets:
                    raise StateConflictError(
                        "Multiple state updates target the same location in one "
                        f"tick: {target}"
                    )
                claimed_targets.add(target)

                before = self._read(
                    next_state,
                    mechanism_id=mechanism_id,
                    update=update,
                )
                after = self._apply_operation(
                    before=before,
                    update=update,
                )
                self._write(
                    next_state,
                    mechanism_id=mechanism_id,
                    update=update,
                    value=after,
                )

                applied.append(
                    AppliedStateUpdate(
                        source_mechanism=mechanism_id,
                        scope=update.scope,
                        key=update.key,
                        operation=update.operation,
                        before=deepcopy(before),
                        after=deepcopy(after),
                    )
                )

        return StateIntegrationResult(
            state=next_state,
            applied=tuple(applied),
        )

    def _validate_update(self, update: StateUpdate) -> None:
        if update.scope not in {"AGENT_VARIABLE", "MECHANISM_STATE"}:
            raise StateValidationError(
                f"Unsupported state scope: {update.scope!r}"
            )

        if update.operation not in {"SET", "ADD"}:
            raise StateValidationError(
                f"Unsupported state operation: {update.operation!r}"
            )

        if not isinstance(update.key, str) or not update.key.strip():
            raise StateValidationError(
                "State update key must be a non-empty string"
            )

    def _read(
        self,
        state: AgentState,
        *,
        mechanism_id: str,
        update: StateUpdate,
    ) -> Any:
        if update.scope == "AGENT_VARIABLE":
            return deepcopy(state.variables.get(update.key))

        namespace = state.mechanism_states.setdefault(mechanism_id, {})
        return deepcopy(namespace.get(update.key))

    def _apply_operation(
        self,
        *,
        before: Any,
        update: StateUpdate,
    ) -> Any:
        if update.operation == "SET":
            return deepcopy(update.value)

        # ADD uses zero only for a previously absent numeric accumulator.
        base = 0 if before is None else before
        delta = update.value

        if (
            isinstance(base, bool)
            or isinstance(delta, bool)
            or not isinstance(base, Real)
            or not isinstance(delta, Real)
        ):
            raise StateValidationError(
                "ADD requires numeric non-boolean current and delta values"
            )

        return base + delta

    def _write(
        self,
        state: AgentState,
        *,
        mechanism_id: str,
        update: StateUpdate,
        value: Any,
    ) -> None:
        if update.scope == "AGENT_VARIABLE":
            state.variables[update.key] = deepcopy(value)
            return

        namespace = state.mechanism_states.setdefault(mechanism_id, {})
        namespace[update.key] = deepcopy(value)
