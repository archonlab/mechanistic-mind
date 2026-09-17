from copy import deepcopy
from dataclasses import dataclass
import hashlib

from mechanistic_mind.agent import AgentState, Observation

from .base import MechanismContext, MechanismOutput
from .registry import MechanismRegistry


class MechanismContractError(RuntimeError):
    """Raised when a mechanism violates the runtime provenance contract."""


@dataclass(slots=True)
class MechanismRuntime:
    """Runs installed mechanisms without granting mutation authority."""

    registry: MechanismRegistry
    base_seed: int = 0

    def evaluate(
        self,
        *,
        tick: int,
        agent_id: str,
        observation: Observation,
        agent_state: AgentState,
    ) -> dict[str, MechanismOutput]:
        outputs: dict[str, MechanismOutput] = {}

        for mechanism in self.registry.ordered():
            mechanism_id = mechanism.mechanism_id

            visible_agent_state = AgentState(
                variables=deepcopy(agent_state.variables),
                mechanism_states={},
            )
            own_mechanism_state = deepcopy(
                agent_state.mechanism_states.get(mechanism_id, {})
            )

            context = MechanismContext(
                tick=tick,
                agent_id=agent_id,
                observation=deepcopy(observation),
                agent_state=visible_agent_state,
                mechanism_state=own_mechanism_state,
                random_value=self._stateless_random(
                    tick=tick,
                    agent_id=agent_id,
                    mechanism_id=mechanism_id,
                ),
            )
            output = mechanism.process(context)
            self._validate_provenance(mechanism_id, output)
            outputs[mechanism_id] = output

        return outputs

    def _stateless_random(
        self,
        *,
        tick: int,
        agent_id: str,
        mechanism_id: str,
    ) -> float:
        material = (
            f"{self.base_seed}|{tick}|{agent_id}|{mechanism_id}"
        ).encode("utf-8")
        digest = hashlib.sha256(material).digest()
        integer = int.from_bytes(digest[:8], "big", signed=False)
        return integer / 2**64

    def _validate_provenance(
        self,
        mechanism_id: str,
        output: MechanismOutput,
    ) -> None:
        for proposal in output.proposals:
            if proposal.source_mechanism != mechanism_id:
                raise MechanismContractError(
                    "ActionProposal provenance mismatch: "
                    f"runtime={mechanism_id!r}, "
                    f"proposal={proposal.source_mechanism!r}"
                )
