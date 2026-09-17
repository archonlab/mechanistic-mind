from dataclasses import dataclass

from mechanistic_mind.agent import Action

from .base import ActionProposal, MechanismOutput


@dataclass(frozen=True, slots=True)
class ActionDecision:
    """Result of deterministic proposal arbitration."""

    action: Action
    selected_proposal: ActionProposal | None
    candidates: tuple[ActionProposal, ...]
    reason: str


@dataclass(slots=True)
class ActionIntegrator:
    """Minimal, replaceable infrastructure-level proposal arbitration.

    Ranking:
      1. higher priority
      2. higher weight
      3. stable lexical mechanism id
      4. stable action kind

    This is deliberately not a psychological policy. It only makes competing
    mechanism outputs executable and reproducible.
    """

    def decide(
        self,
        outputs: dict[str, MechanismOutput],
    ) -> ActionDecision:
        candidates = tuple(
            proposal
            for mechanism_id in sorted(outputs)
            for proposal in outputs[mechanism_id].proposals
        )

        if not candidates:
            return ActionDecision(
                action=Action.wait(),
                selected_proposal=None,
                candidates=(),
                reason="NO_PROPOSALS",
            )

        ranked = sorted(
            candidates,
            key=lambda p: (
                -p.priority,
                -p.weight,
                p.source_mechanism,
                p.action.kind,
            ),
        )
        selected = ranked[0]

        return ActionDecision(
            action=selected.action,
            selected_proposal=selected,
            candidates=candidates,
            reason="TOP_RANKED_PROPOSAL",
        )
