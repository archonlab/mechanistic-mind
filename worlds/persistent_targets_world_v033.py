from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from mechanistic_mind.agent import Action
from mechanistic_mind.body import BodyConfig, BodyEngine, BodyState
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.environment import WorldState
from mechanistic_mind.world_engine import (
    ObjectiveObject,
    ObjectiveWorldEngine,
    WorldActionResult,
    WorldEngineConfig,
)
from organism_world_v03 import OrganismWorld


ANVIL_CUE = "CUE-ANVIL-PERSISTENT"
NEUTRAL_CUE = "CUE-NEUTRAL"
SMALL_CUE = "CUE-BLUE-SMALL"
MEDIUM_CUE = "CUE-AMBER-MEDIUM"


def persistent_targets_world_config(
    *,
    condition: str = "BROKEN",
) -> WorldEngineConfig:
    """v0.3.3 world for repeated target interaction and attractor switching.

    The agent does not observe which targets are genuinely productive, how many
    attempts remain before completion, or whether the target has become broken
    or revived. It only experiences action consequences over time.
    """
    condition = condition.upper()
    if condition not in {"WORKING", "BROKEN", "DEAD", "REVIVAL"}:
        raise ValueError(f"Unsupported condition: {condition!r}")

    objects = (
        ObjectiveObject(
            object_id="HOME-RESOURCE",
            position=(0, 2),
            hidden_role="HOME_RESOURCE",
            cue_signature=NEUTRAL_CUE,
            cue_salience=0.45,
            cooldown_ticks=1,
            body_effects={
                "energy_delta": 0.34,
                "hydration_delta": 0.36,
                "fatigue_delta": -0.20,
                "metabolic_energy_intake": 0.16,
            },
        ),
        ObjectiveObject(
            object_id="TARGET-ANVIL",
            position=(3, 1),
            hidden_role="PERSISTENT_TARGET",
            cue_signature=ANVIL_CUE,
            cue_salience=0.90,
            cooldown_ticks=0,
            body_effects={},
            world_effects={},
        ),
        ObjectiveObject(
            object_id="TARGET-MEDIUM",
            position=(6, 0),
            hidden_role="MEDIUM_GOAL",
            cue_signature=MEDIUM_CUE,
            cue_salience=0.72,
            cooldown_ticks=4,
            body_effects={
                "energy_delta": -0.012,
                "hydration_delta": -0.006,
                "fatigue_delta": 0.010,
            },
            world_effects={
                "progress_delta": 0.35,
            },
        ),
        ObjectiveObject(
            object_id="TARGET-SMALL",
            position=(1, 4),
            hidden_role="SMALL_GOAL",
            cue_signature=SMALL_CUE,
            cue_salience=0.55,
            cooldown_ticks=3,
            body_effects={
                "energy_delta": -0.004,
                "fatigue_delta": 0.004,
            },
            world_effects={
                "progress_delta": 0.12,
            },
        ),
    )

    return WorldEngineConfig(
        width=7,
        height=5,
        vision_radius=1,
        blocked=(),
        objects=objects,
        random_event_rate=0.0,
        causal_reliability=1.0,
    )


def persistent_targets_body_config() -> BodyConfig:
    return BodyConfig(
        basal_energy_drain_per_day=0.008,
        basal_hydration_drain_per_day=0.009,
        passive_fatigue_gain_per_day=0.006,
        basal_metabolic_expenditure_per_day=0.055,
    )


def _persistent_spec(condition: str) -> dict[str, Any]:
    condition = condition.upper()
    return {
        "target_mode": condition,
        "switch_tick": 45,
        "completion_threshold": 2.0,
        "attempt_progress_gain": 1.0,
        "partial_progress_delta": 0.08,
        "completion_progress_delta": 0.92,
        "attempt_body_effects": {
            "energy_delta": -0.008,
            "hydration_delta": -0.004,
            "fatigue_delta": 0.012,
        },
        "completion_body_effects": {
            "fatigue_delta": -0.015,
        },
        "success_count": 0,
        "attempt_count": 0,
        "latent_progress": 0.0,
        "last_outcome": None,
    }


class PersistentTargetWorldEngine(ObjectiveWorldEngine):
    def __init__(
        self,
        config: WorldEngineConfig,
        *,
        condition: str = "BROKEN",
    ) -> None:
        super().__init__(config)
        self.condition = condition.upper()

    def initial_state(
        self,
        *,
        agent_id: str = "A001",
        start_position: tuple[int, int] = (0, 2),
    ) -> dict[str, Any]:
        state = super().initial_state(
            agent_id=agent_id,
            start_position=start_position,
        )
        record = state["objects"]["TARGET-ANVIL"]
        record.update(_persistent_spec(self.condition))
        return state

    def transition_action(
        self,
        state: dict[str, Any],
        *,
        agent_id: str,
        action: Action,
        rng: DeterministicRandom,
        body_context: dict[str, Any] | None = None,
    ) -> WorldActionResult:
        if not action.kind.startswith("USE:"):
            return super().transition_action(
                state,
                agent_id=agent_id,
                action=action,
                rng=rng,
                body_context=body_context,
            )

        object_id = action.kind.split(":", 1)[1]
        record = self._objects(state).get(object_id)
        if not isinstance(record, dict) or not bool(
            record.get("hidden_role") == "PERSISTENT_TARGET"
        ):
            return super().transition_action(
                state,
                agent_id=agent_id,
                action=action,
                rng=rng,
                body_context=body_context,
            )

        next_state = deepcopy(state)
        position_before = self.position(next_state, agent_id)
        available = set(
            self.available_actions(
                next_state,
                agent_id=agent_id,
            )
        )

        distance = 0.0
        terrain_factor = 1.0
        external_body_effects: dict[str, float] = {}
        progress_delta = 0.0
        receipt: dict[str, Any] = {
            "action": action.kind,
            "valid": action.kind in available,
            "position_before": list(position_before),
            "object_id": object_id,
            "persistent_target": True,
        }

        if action.kind not in available:
            receipt["valid"] = False
        else:
            local = self._objects(next_state)[object_id]
            use_count = int(local.get("use_count", 0)) + 1
            local["use_count"] = use_count
            local["attempt_count"] = int(
                local.get("attempt_count", 0)
            ) + 1

            current_tick = int(next_state.get("tick", 0)) + 1
            operative = self._target_operative(
                local,
                current_tick=current_tick,
            )
            before_latent = float(local.get("latent_progress", 0.0))
            after_latent = before_latent

            if rng.random() <= self.config.causal_reliability:
                external_body_effects = self._numeric_mapping(
                    local.get("attempt_body_effects")
                )
                receipt["causal_effect_applied"] = True

                if operative:
                    after_latent = (
                        before_latent
                        + float(
                            local.get(
                                "attempt_progress_gain",
                                1.0,
                            )
                        )
                    )
                    local["latent_progress"] = after_latent
                    progress_delta += float(
                        local.get(
                            "partial_progress_delta",
                            0.0,
                        )
                    )
                    outcome = "PARTIAL"
                    threshold = float(
                        local.get(
                            "completion_threshold",
                            1.0,
                        )
                    )
                    if after_latent >= threshold:
                        progress_delta += float(
                            local.get(
                                "completion_progress_delta",
                                0.0,
                            )
                        )
                        self._merge_numeric(
                            external_body_effects,
                            self._numeric_mapping(
                                local.get(
                                    "completion_body_effects"
                                )
                            ),
                        )
                        local["latent_progress"] = 0.0
                        local["success_count"] = int(
                            local.get("success_count", 0)
                        ) + 1
                        after_latent = 0.0
                        outcome = "SUCCESS"
                else:
                    outcome = "STALL"
            else:
                receipt["causal_effect_applied"] = False
                outcome = "NO_EFFECT"

            cooldown = int(local.get("cooldown_ticks", 0))
            if cooldown > 0:
                local["available_after_tick"] = (
                    int(next_state.get("tick", 0))
                    + cooldown
                    + 1
                )

            local["last_outcome"] = outcome

            receipt["persistent_target_outcome"] = outcome
            receipt["target_mode"] = str(
                local.get("target_mode", "WORKING")
            )
            receipt["target_operative"] = operative
            receipt["latent_progress_before"] = before_latent
            receipt["latent_progress_after"] = after_latent
            receipt["completion_threshold"] = float(
                local.get("completion_threshold", 1.0)
            )
            receipt["success_count"] = int(
                local.get("success_count", 0)
            )
            receipt["attempt_count"] = int(
                local.get("attempt_count", 0)
            )
            receipt["use_count"] = use_count
            receipt["cooldown_ticks"] = cooldown

        next_state["total_progress"] = float(
            next_state.get("total_progress", 0.0)
        ) + progress_delta

        log = list(next_state.get("action_log", []))
        log.append(deepcopy(receipt))
        next_state["action_log"] = log[-64:]

        counts = dict(next_state.get("action_counts", {}))
        counts[action.kind] = int(counts.get(action.kind, 0)) + 1
        next_state["action_counts"] = counts
        next_state["interaction_count"] = int(
            next_state.get("interaction_count", 0)
        ) + 1

        return WorldActionResult(
            state=next_state,
            distance=distance,
            terrain_factor=terrain_factor,
            external_body_effects=external_body_effects,
            progress_delta=progress_delta,
            action_receipt=receipt,
        )

    def _target_operative(
        self,
        record: dict[str, Any],
        *,
        current_tick: int,
    ) -> bool:
        mode = str(record.get("target_mode", "WORKING")).upper()
        switch_tick = int(record.get("switch_tick", 45))
        if mode == "WORKING":
            return True
        if mode == "DEAD":
            return False
        if mode == "BROKEN":
            return current_tick < switch_tick
        if mode == "REVIVAL":
            return current_tick >= switch_tick
        return True


@dataclass(slots=True)
class PersistentTargetsWorld(OrganismWorld):
    """v0.3.3 world with hidden persistent targets and attractor switching."""

    condition: str = "BROKEN"

    def __post_init__(self) -> None:
        self.world_config = persistent_targets_world_config(
            condition=self.condition
        )
        self.body_config = persistent_targets_body_config()
        self.initial_body = BodyState(
            mass_kg=70.0,
            height_m=1.75,
            age_days=18.0 * 365.2425,
            energy_reserve=0.92,
            hydration=0.92,
            fatigue=0.06,
            damage=0.0,
        )
        self.start_position = (0, 2)
        self.observation_context = (
            "PERSISTENT_TARGETS_WORLD_V033"
        )
        self.world_engine = PersistentTargetWorldEngine(
            self.world_config,
            condition=self.condition,
        )
        self.body_engine = BodyEngine(self.body_config)
        self.state = WorldState(
            variables={
                "world": self.world_engine.initial_state(
                    agent_id=self.agent_id,
                    start_position=self.start_position,
                ),
                "bodies": {
                    self.agent_id: self.initial_body.to_dict(),
                },
                "last_experience": {
                    self.agent_id: None,
                },
                "developmental_history": [],
                "observer_receipts": {
                    "exogenous_events": [],
                },
            }
        )
