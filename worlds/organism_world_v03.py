from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.agent import Action, Observation
from mechanistic_mind.body import BodyConfig, BodyEngine, BodyState
from mechanistic_mind.body.embodied_integration import (
    EmbodiedIntegrationState,
    integration_enabled,
    step_pre_action,
)
from mechanistic_mind.world_engine.physical_effector import default_effector_config
from mechanistic_mind.world_engine.background_fields import sample_local_fields
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.environment import World, WorldState
from mechanistic_mind.world_engine import (
    ExogenousEventKind,
    ObjectiveObject,
    ObjectiveWorldEngine,
    ScheduledExogenousEvent,
    WorldEngineConfig,
)


def default_organism_world_config(
    *,
    resource_layout: str = "distributed",
    random_event_rate: float = 0.0,
    exogenous_events: tuple[ScheduledExogenousEvent, ...] = (),
) -> WorldEngineConfig:
    if resource_layout == "near":
        energy_pos = (4, 3)
        hydration_pos = (4, 4)
    elif resource_layout == "far":
        energy_pos = (0, 0)
        hydration_pos = (8, 6)
    elif resource_layout == "distributed":
        energy_pos = (1, 1)
        hydration_pos = (7, 5)
    else:
        raise ValueError(
            f"Unsupported resource_layout: {resource_layout!r}"
        )

    objects = (
        ObjectiveObject(
            "OBJ-04",
            (4, 3),
            hidden_role="RECOVERY_SITE",
            body_effects={
                "energy_delta": 0.06,
                "hydration_delta": 0.015,
                "fatigue_delta": -0.20,
            },
        ),
        ObjectiveObject(
            "OBJ-17",
            energy_pos,
            hidden_role="ENERGY_RESOURCE",
            body_effects={
                "energy_delta": 0.40,
                "hydration_delta": 0.01,
                "metabolic_energy_intake": 0.22,
            },
        ),
        ObjectiveObject(
            "OBJ-23",
            hydration_pos,
            hidden_role="HYDRATION_RESOURCE",
            body_effects={
                "hydration_delta": 0.48,
                "fatigue_delta": -0.01,
            },
        ),
        ObjectiveObject(
            "OBJ-31",
            (7, 1),
            hidden_role="PROGRESS_SITE",
            body_effects={
                "energy_delta": -0.035,
                "hydration_delta": -0.025,
                "fatigue_delta": 0.035,
            },
            world_effects={
                "progress_delta": 1.0,
            },
        ),
    )
    return WorldEngineConfig(
        width=9,
        height=7,
        vision_radius=1,
        objects=objects,
        exogenous_events=exogenous_events,
        random_event_rate=random_event_rate,
    )


@dataclass(slots=True)
class OrganismWorld(World):
    """World × Body composition for the v0.3 foundation.

    Objective World and Body truth are stored in WorldState for the simulator
    and Observer. Agent observations expose only partial world perception plus
    interoceptive signals.
    """

    world_config: WorldEngineConfig = field(
        default_factory=default_organism_world_config
    )
    body_config: BodyConfig = field(default_factory=BodyConfig)
    initial_body: BodyState = field(default_factory=BodyState)
    agent_id: str = "A001"
    start_position: tuple[int, int] = (4, 3)
    # Multi-agent (Update 4.7). When unset, derived from agent_id/start_position.
    agent_ids: tuple[str, ...] | None = None
    start_positions: dict[str, tuple[int, int]] | None = None
    initial_bodies: dict[str, BodyState] | None = None
    observation_context: str = "ORGANISM_WORLD_V031"

    state: WorldState = field(init=False)
    world_engine: ObjectiveWorldEngine = field(init=False)
    body_engine: BodyEngine = field(init=False)

    def __post_init__(self) -> None:
        ids = (
            tuple(self.agent_ids)
            if self.agent_ids
            else (self.agent_id,)
        )
        if not ids:
            raise ValueError("OrganismWorld requires at least one agent_id")
        # Keep scalar agent_id aligned with the first configured agent.
        object.__setattr__(self, "agent_ids", ids)
        object.__setattr__(self, "agent_id", ids[0])

        positions: dict[str, tuple[int, int]] = {}
        if self.start_positions:
            positions = {
                str(aid): (int(pos[0]), int(pos[1]))
                for aid, pos in self.start_positions.items()
            }
        for aid in ids:
            if aid not in positions:
                if aid == ids[0]:
                    positions[aid] = (
                        int(self.start_position[0]),
                        int(self.start_position[1]),
                    )
                else:
                    raise ValueError(
                        f"Missing start_position for agent {aid}"
                    )
        object.__setattr__(self, "start_positions", positions)
        object.__setattr__(self, "start_position", positions[ids[0]])

        bodies: dict[str, BodyState] = {}
        if self.initial_bodies:
            bodies = {
                str(aid): body
                for aid, body in self.initial_bodies.items()
            }
        for aid in ids:
            if aid not in bodies:
                bodies[aid] = (
                    self.initial_body
                    if aid == ids[0]
                    else BodyState()
                )
        object.__setattr__(self, "initial_bodies", bodies)

        self.world_engine = ObjectiveWorldEngine(
            self.world_config
        )
        self.body_engine = BodyEngine(
            self.body_config
        )
        self.state = WorldState(
            variables={
                "world": self.world_engine.initial_state(
                    agent_positions=positions,
                ),
                "bodies": {
                    aid: bodies[aid].to_dict()
                    for aid in ids
                },
                "last_experience": {
                    aid: None
                    for aid in ids
                },
                # Per-agent motor demand (4.6+ forward compat; unused if absent upstream).
                "pending_motor_demand_effort": {
                    aid: 0.0
                    for aid in ids
                },
                "developmental_history": [],
                "observer_receipts": {
                    "exogenous_events": [],
                },
            }
        )

    def observe(
        self,
        state: WorldState,
        agent_id: str,
    ) -> Observation:
        world_truth = self._world_truth(state)
        body = self._body_state(state, agent_id)
        local = self.world_engine.local_observation(
            world_truth,
            agent_id=agent_id,
        )
        signals = self.body_engine.signals(
            body
        ).to_dict()
        # Update 4.20: bounded generic process fragments (no regime/need labels).
        if hasattr(self.body_engine, "process_fragments"):
            signals = {**signals, **self.body_engine.process_fragments(body)}
        last_experience = deepcopy(
            self._last_experience(state).get(
                agent_id
            )
        )
        return Observation(
            data={
                **local,
                "interoception": signals,
                "perceptual_context": self.perceptual_context(
                    local=local,
                    signals=signals,
                    last_experience=last_experience,
                ),
                "last_action": (
                    last_experience.get("action")
                    if isinstance(
                        last_experience,
                        dict,
                    )
                    else None
                ),
                "last_experienced_effects": (
                    deepcopy(
                        last_experience.get(
                            "experienced_effects"
                        )
                    )
                    if isinstance(
                        last_experience,
                        dict,
                    )
                    else None
                ),
                "context": self.observation_context,
            }
        )

    def perceptual_context(
        self,
        *,
        local: dict[str, Any],
        signals: dict[str, float],
        last_experience: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Compact lawful modalities; contains no hidden object configuration."""
        visual = list(local.get("visual_fragments", ()))[:16]
        receipt = (
            last_experience.get("action_receipt", {})
            if isinstance(last_experience, dict) else {}
        )
        tactile = []
        if isinstance(receipt, dict) and any(
            receipt.get(key) for key in ("obstacle_contact", "object_moved", "carried", "released")
        ):
            tactile.append({
                "contact": True,
                "movement_blocked": bool(receipt.get("movement_blocked", False)),
                "valid": bool(receipt.get("valid", False)),
            })
        carried = [
            {"cue_signature": row.get("cue_signature"), "interaction_state": row.get("interaction_state")}
            for row in local.get("visible_objects", ())
            if isinstance(row, dict) and row.get("interaction_state") == "CARRIED"
        ][:1]
        fragments = (
            [{"modality": "visual", **row} for row in visual]
            + [{"modality": "tactile", **row} for row in tactile]
            + [{"modality": "proprioceptive", "carried": row} for row in carried]
            + [{"modality": "interoceptive", "bands": {
                key: ("L" if value < 1/3 else "M" if value < 2/3 else "H")
                for key, value in sorted(signals.items())
            }}]
        )
        return {
            "modalities": {
                "visual": bool(visual),
                "tactile": bool(tactile),
                "proprioceptive": True,
                "interoceptive": True,
                "physical_field": False,
            },
            "fragments": fragments[:24],
        }

    def transition(
        self,
        state: WorldState,
        actions: dict[str, Action],
        rng: DeterministicRandom,
    ) -> WorldState:
        expected = set(self.agent_ids or (self.agent_id,))
        if set(actions) != expected:
            raise ValueError(
                "OrganismWorld actions must match configured agents "
                f"{sorted(expected)}; got {sorted(actions)}"
            )

        next_state = deepcopy(state)
        world_cursor = deepcopy(self._world_truth(next_state))
        ordered_ids = sorted(actions)

        # Shared world dynamics advance once; agent actions apply sequentially.
        action_results: dict[str, Any] = {}
        # MM-INT-1: per-agent pre_action integration state carried into body writeback.
        _mm_int1_states: dict[str, EmbodiedIntegrationState] = {}

        for index, agent_id in enumerate(ordered_ids):
            action = actions[agent_id]
            body_before = self._body_state(next_state, agent_id)

            effector_cfg = getattr(self.body_config, "physical_effector_config", None)
            integ_cfg = getattr(self.body_config, "embodied_integration_config", None)
            if integration_enabled(self.body_config):
                emb = EmbodiedIntegrationState.from_dict(body_before.embodied_integration)
                local = self.world_engine.local_observation(world_cursor, agent_id=agent_id)
                last_exp = (next_state.variables.get("last_experience") or {}).get(agent_id)
                obs_data = dict(local) if isinstance(local, dict) else {}
                if isinstance(last_exp, dict):
                    receipt = last_exp.get("action_receipt") or {}
                    if isinstance(receipt, dict) and any(
                        receipt.get(k)
                        for k in ("obstacle_contact", "object_moved", "carried", "released")
                    ):
                        obs_data["_tactile_contact"] = True
                # Deterministic noise from rng without semantic meaning.
                rv = float(rng.random()) if hasattr(rng, "random") else 0.5
                emb, drive = step_pre_action(
                    emb,
                    energy_reserve=float(body_before.energy_reserve),
                    hydration=float(body_before.hydration),
                    fatigue=float(body_before.fatigue),
                    observation_data=obs_data,
                    config=integ_cfg,
                    random_value=rv,
                )
                _mm_int1_states[agent_id] = emb
                if integ_cfg.get("neural_drive_enabled", True) and not integ_cfg.get(
                    "ablate_effector_drive", False
                ):
                    world_cursor["neural_physical_drive"] = list(drive)
                # Auto-enable effector substrate when integration requests neural drive
                # and legacy physical_effector_config is still None.
                if effector_cfg is None and integ_cfg.get("neural_drive_enabled", True):
                    effector_cfg = default_effector_config()
                body_before.embodied_integration = emb.to_dict()

            action_result = self.world_engine.transition_action(
                world_cursor,
                agent_id=agent_id,
                action=action,
                rng=rng,
                body_context={
                    **body_before.to_dict(),
                    **{
                        f"internal_load:{key}": value
                        for key, value in body_before.internal_loads.items()
                    },
                    # Update 4.8 intake flags from BodyConfig (Observer/physics only).
                    "physical_intake_enabled": bool(
                        getattr(self.body_config, "physical_intake_enabled", False)
                    ),
                    "intake_transfer_enabled": bool(
                        getattr(self.body_config, "intake_transfer_enabled", True)
                    ),
                    "intake_processing_enabled": bool(
                        getattr(self.body_config, "intake_processing_enabled", True)
                    ),
                    "intake_per_interaction_capacity": float(
                        getattr(self.body_config, "intake_per_interaction_capacity", 0.03)
                    ),
                    "intake_internal_capacity": float(
                        getattr(self.body_config, "intake_internal_capacity", 0.20)
                    ),
                    "physical_effector_config": effector_cfg,
                    "physical_coupling_config": getattr(
                        self.body_config, "physical_coupling_config", None
                    ),
                    "contact_material_transfer_config": getattr(
                        self.body_config, "contact_material_transfer_config", None
                    ),
                    "embodied_integration_config": integ_cfg,
                    "_intake_params": __import__(
                        "mechanistic_mind.body.physical_intake",
                        fromlist=["intake_params_from_body_config"],
                    ).intake_params_from_body_config(self.body_config).to_dict(),
                },
                advance_dynamics=(index == 0),
            )
            world_cursor = action_result.state
            action_results[agent_id] = (action, body_before, action_result)

        effective_tick = int(world_cursor.get("tick", 0)) + 1

        (
            world_after_delay,
            delayed_body_effects_flat,
            delayed_progress_delta,
            delayed_receipts,
        ) = self.world_engine.release_delayed_effects(
            world_cursor,
            effective_tick=effective_tick,
        )

        delayed_by_agent: dict[str, dict[str, float]] = {
            aid: {} for aid in ordered_ids
        }
        for receipt in delayed_receipts:
            target = receipt.get("agent_id")
            if target not in delayed_by_agent:
                # Legacy untagged delayed effects: attribute to sole agent if N=1.
                if len(ordered_ids) == 1:
                    target = ordered_ids[0]
                else:
                    continue
            for key, value in (receipt.get("body_effects") or {}).items():
                delayed_by_agent[target][key] = (
                    float(delayed_by_agent[target].get(key, 0.0))
                    + float(value)
                )

        # Exogenous world advance once. Organism-targeted body effects apply to
        # every co-located body equally when the event is ambient/organism-wide;
        # attribution uses the first sorted agent_id for world-only event params.
        (
            world_after_events,
            exogenous_body_effects,
            event_receipts,
        ) = self.world_engine.apply_exogenous_events(
            world_after_delay,
            effective_tick=effective_tick,
            agent_id=ordered_ids[0],
            rng=rng,
        )
        world_after_events["tick"] = effective_tick

        pending = next_state.variables.get("pending_motor_demand_effort")
        if not isinstance(pending, dict):
            pending = {aid: 0.0 for aid in ordered_ids}
        else:
            pending = {
                aid: float(pending.get(aid, 0.0))
                for aid in ordered_ids
            }

        for agent_id in ordered_ids:
            action, body_before, action_result = action_results[agent_id]
            signals_before = self.body_engine.signals(body_before).to_dict()

            external_body_effects = dict(action_result.external_body_effects)
            for key, value in delayed_by_agent.get(agent_id, {}).items():
                external_body_effects[key] = (
                    float(external_body_effects.get(key, 0.0)) + float(value)
                )

            contextual_effects, contextual_receipt = self.objective_context_effects(
                world_after_events,
                body_before=body_before,
                action=action,
                agent_id=agent_id,
            )
            for key, value in contextual_effects.items():
                external_body_effects[key] = (
                    float(external_body_effects.get(key, 0.0)) + float(value)
                )

            # Consume any pending motor demand for THIS agent only (never cross-agent).
            demand = float(pending.get(agent_id, 0.0))
            if demand:
                external_body_effects["fatigue_delta"] = (
                    float(external_body_effects.get("fatigue_delta", 0.0))
                    + 0.02 * demand
                )
                external_body_effects["energy_delta"] = (
                    float(external_body_effects.get("energy_delta", 0.0))
                    - 0.01 * demand
                )
                pending[agent_id] = 0.0

            # PHYS-4.76-E1A — generic same-cell contact → existing bounded intake transfer.
            # Default off (contact_material_transfer_config is None). No USE/TAKE required.
            # Arbitration: skip objects already transferred via USE this tick.
            try:
                from mechanistic_mind.body.physical_intake import (
                    apply_bounded_object_intake,
                    contact_material_transfer_enabled,
                    intake_params_from_body_config,
                    merge_intake_transfer,
                    same_cell_contact,
                )
                if contact_material_transfer_enabled(self.body_config):
                    intake_params = intake_params_from_body_config(self.body_config)
                    if intake_params.enabled:
                        pos = None
                        try:
                            pos = self.world_engine.position(world_after_events, agent_id)
                        except Exception:
                            ap = (world_after_events.get("agent_positions") or {}).get(agent_id)
                            if isinstance(ap, (list, tuple)) and len(ap) >= 2:
                                pos = (int(ap[0]), int(ap[1]))
                        receipt = getattr(action_result, "action_receipt", None) or {}
                        if not isinstance(receipt, dict):
                            receipt = {}
                        already = set()
                        # Arbitration: one shared transfer per object/body pair per tick.
                        if receipt.get("intake_mode"):
                            oid = receipt.get("object_id")
                            if oid is None and str(action.kind).startswith("USE:"):
                                oid = action.kind.split(":", 1)[1]
                            if oid is not None:
                                already.add(str(oid))
                        if str(action.kind).startswith("USE:") and isinstance(
                            action_result.external_body_effects.get("intake_transfer"), dict
                        ):
                            already.add(str(action.kind.split(":", 1)[1]))
                        for oid in receipt.get("intake_object_ids") or []:
                            already.add(str(oid))
                        objects = world_after_events.get("objects") or {}
                        contact_events = []
                        mats_est = dict(body_before.internal_materials or {})
                        # Account for same-tick USE intake already in external_body_effects.
                        prior = external_body_effects.get("intake_transfer")
                        if isinstance(prior, dict):
                            for mat, amt in prior.items():
                                if isinstance(amt, (int, float)) and float(amt) > 0:
                                    mats_est[str(mat)] = float(mats_est.get(str(mat), 0.0)) + float(amt)
                        if pos is not None and isinstance(objects, dict):
                            for object_id, record in list(objects.items()):
                                if not isinstance(record, dict):
                                    continue
                                if str(object_id) in already:
                                    continue
                                if not same_cell_contact(pos, record.get("position")):
                                    continue
                                result = apply_bounded_object_intake(
                                    record,
                                    params=intake_params,
                                    internal_materials=mats_est,
                                )
                                accepted = float(result.get("accepted", 0.0) or 0.0)
                                xfer = dict(result.get("intake_transfer") or {})
                                if accepted > 0.0 and xfer:
                                    merge_intake_transfer(external_body_effects, xfer)
                                    for mat, amt in xfer.items():
                                        mats_est[str(mat)] = float(mats_est.get(str(mat), 0.0)) + float(amt)
                                    objects[object_id] = record
                                    contact_events.append(
                                        {
                                            "object_id": str(object_id),
                                            "accepted": accepted,
                                            "intake_transfer": xfer,
                                            "eligibility": "CONTACT",
                                        }
                                    )
                                    already.add(str(object_id))
                        if contact_events:
                            world_after_events["objects"] = objects
                            external_body_effects["contact_intake_events"] = contact_events
                            # Observer/debug only — not cognition-facing semantics.
                            external_body_effects["contact_intake_receipt"] = {
                                "event_count": len(contact_events),
                                "total_accepted": float(
                                    sum(float(e["accepted"]) for e in contact_events)
                                ),
                            }
            except Exception:
                pass

            # Update 4.9 — continuous local env exchange into same internal_materials.
            # Maintained boundary field; no USE/BREATHE action; position→availability→transfer.
            try:
                from mechanistic_mind.body.physical_intake import (
                    compute_environmental_exchange,
                    env_exchange_params_from_body_config,
                    local_material_availability,
                    remaining_capacity,
                )
                from mechanistic_mind.body.passive_physical_exchange import (
                    resolve_env_exchange_params,
                    resolve_internal_capacity,
                )
                env_params = resolve_env_exchange_params(self.body_config)
                if env_params.enabled:
                    pos = None
                    try:
                        pos = self.world_engine.position(world_after_events, agent_id)
                    except Exception:
                        ap = (world_after_events.get("agent_positions") or {}).get(agent_id)
                        if isinstance(ap, (list, tuple)) and len(ap) >= 2:
                            pos = (int(ap[0]), int(ap[1]))
                    avail = (
                        local_material_availability(
                            world_after_events,
                            pos,
                            material_id=env_params.material_id,
                        )
                        if pos is not None
                        else 0.0
                    )
                    cap = remaining_capacity(
                        body_before.internal_materials,
                        resolve_internal_capacity(self.body_config),
                    )
                    exch = compute_environmental_exchange(
                        availability=avail,
                        organism_remaining_cap=cap,
                        params=env_params,
                    )
                    external_body_effects["env_availability"] = float(avail)
                    accepted = float(exch.get("accepted", 0.0) or 0.0)
                    if accepted > 0:
                        mid = str(exch.get("material_id") or env_params.material_id)
                        external_body_effects["env_exchange_transfer"] = {mid: accepted}
                    # Observer/debug receipt (not cognition)
                    external_body_effects["env_exchange_receipt"] = {
                        k: exch[k]
                        for k in (
                            "requested",
                            "accepted",
                            "availability",
                            "ablated",
                            "reason",
                            "capacity_limited",
                        )
                        if k in exch
                    }
            except Exception:
                pass

            # Update 4.20: local ambient sample for process rate modulation (not cognition).
            try:
                pos = self.world_engine.position(world_cursor, agent_id)
                external_body_effects["env_sample"] = sample_local_fields(
                    world_cursor, position=tuple(pos) if not isinstance(pos, tuple) else pos
                )
            except Exception:
                pass

            # Shared exogenous organism effects hit each body (ambient physics).
            body_transition = self.body_engine.transition(
                body_before,
                action=action,
                distance=action_result.distance,
                terrain_factor=action_result.terrain_factor,
                external_effects=external_body_effects,
                exogenous_effects=exogenous_body_effects,
                carried_mass_kg=action_result.carried_mass_kg,
            )

            signals_after = body_transition.signals_after.to_dict()
            signal_delta = {
                key: signals_after[key] - signals_before[key]
                for key in signals_after
            }
            experienced_effects = {
                **signal_delta,
                "progress_delta": float(
                    action_result.progress_delta
                    + (
                        delayed_progress_delta
                        if agent_id == ordered_ids[0]
                        else 0.0
                    )
                ),
            }

            body_out = body_transition.state
            if agent_id in _mm_int1_states:
                body_out.embodied_integration = _mm_int1_states[agent_id].to_dict()
            next_state.variables["bodies"][agent_id] = (
                body_out.to_dict()
            )
            next_state.variables["last_experience"][agent_id] = {
                "action": action.kind,
                "action_receipt": deepcopy(action_result.action_receipt),
                "objective_context_receipt": deepcopy(contextual_receipt),
                "experienced_effects": deepcopy(experienced_effects),
            }

            history = list(
                next_state.variables.get("developmental_history", [])
            )
            history.append(
                {
                    "tick": effective_tick,
                    "agent_id": agent_id,
                    "action": action.kind,
                    "position": deepcopy(
                        world_after_events["agent_positions"][agent_id]
                    ),
                    "experienced_effects": deepcopy(experienced_effects),
                    "body_truth_before": body_before.to_dict(),
                    "body_truth_after": body_transition.state.to_dict(),
                    "mass_dynamics": deepcopy(body_transition.mass_dynamics),
                    "world_action_receipt": deepcopy(
                        action_result.action_receipt
                    ),
                    "exogenous_event_receipts": deepcopy(event_receipts),
                    "delayed_effect_receipts": [
                        deepcopy(row)
                        for row in delayed_receipts
                        if row.get("agent_id") in {None, agent_id}
                        or (
                            row.get("agent_id") is None
                            and len(ordered_ids) == 1
                        )
                    ],
                    "objective_context_receipt": deepcopy(contextual_receipt),
                }
            )
            next_state.variables["developmental_history"] = history[-64:]

        next_state.variables["world"] = world_after_events
        next_state.variables["pending_motor_demand_effort"] = pending

        receipts = deepcopy(
            next_state.variables.get("observer_receipts", {})
        )
        exogenous_log = list(receipts.get("exogenous_events", []))
        exogenous_log.extend(deepcopy(event_receipts))
        receipts["exogenous_events"] = exogenous_log
        delayed_log = list(receipts.get("delayed_effects", []))
        delayed_log.extend(deepcopy(delayed_receipts))
        receipts["delayed_effects"] = delayed_log[-64:]
        next_state.variables["observer_receipts"] = receipts
        return next_state

    def objective_context_effects(
        self,
        world_truth: dict[str, Any],
        *,
        body_before: BodyState,
        action: Action,
        agent_id: str | None = None,
    ) -> tuple[dict[str, float], dict[str, Any]]:
        """Extension point for objective local physics; invisible by default."""
        return {}, {}

    def _world_truth(
        self,
        state: WorldState,
    ) -> dict[str, Any]:
        value = state.variables.get("world")
        if not isinstance(value, dict):
            raise ValueError(
                "OrganismWorld state missing objective world truth"
            )
        return value

    def _body_state(
        self,
        state: WorldState,
        agent_id: str,
    ) -> BodyState:
        bodies = state.variables.get(
            "bodies",
            {},
        )
        payload = (
            bodies.get(agent_id)
            if isinstance(bodies, dict)
            else None
        )
        if not isinstance(payload, dict):
            raise ValueError(
                f"OrganismWorld state missing body truth for {agent_id}"
            )
        return BodyState.from_dict(payload)

    def _last_experience(
        self,
        state: WorldState,
    ) -> dict[str, Any]:
        value = state.variables.get(
            "last_experience",
            {},
        )
        return value if isinstance(value, dict) else {}
