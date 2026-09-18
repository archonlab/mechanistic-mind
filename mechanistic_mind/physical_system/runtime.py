"""One owner and one clock for the established physical subsystems.

The stage order is inherited from internal_medium.runtime.run_world_body_medium;
this module adds ownership and replay, not physical laws.

MM cognitive integration extends the same runtime with agent-accessible
observation, bounded 4.21–4.25 stores, and a physical action bridge. This is
not a second runtime and not Integrated Psyche v2.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from mechanistic_mind.internal_medium.config import InternalMediumConfig, default_internal_medium_config
from mechanistic_mind.internal_medium.flux import MediumFluxRecord, step_internal_medium
from mechanistic_mind.internal_medium.state import InternalMediumState, initialize_internal_medium
from mechanistic_mind.physical_body.config import PhysicalBodyConfig, default_physical_body2_config
from mechanistic_mind.physical_body.dynamics import step_physical_body
from mechanistic_mind.physical_body.state import PhysicalBodyState, initialize_physical_body
from mechanistic_mind.planet.config import PlanetConfig, default_planet_config
from mechanistic_mind.planet.dynamics import step_planet
from mechanistic_mind.planet.runtime import restore_planet_state, serialize_planet_state
from mechanistic_mind.planet.state import PlanetState, initialize_planet

from .action_work import (
    DiscreteActionWorkConfig,
    realize_discrete_action,
    request_discrete_action,
)
from .morphology_mechanics import MorphologyMechanicsConfig, step_morphology_mechanics
from .body_orientation import BodyOrientationConfig, step_orientation_mechanics
from .body_deformation import BodyDeformationConfig
from .motor_work import (
    EndogenousMotorWorkConfig,
    allocate_shared_work,
    apply_motor_realization,
    preview_motor_positive_work,
    requested_delta_v,
)
from .deformation_work import DeformationWorkConfig, drag_dissipation, kinetic_energy, preview_positive_actuator_work
from .environmental_resource import EnvironmentalResourceConfig, step_environmental_resource
from .complementary_resources import ComplementaryResourcesConfig, step_complementary_resources
from .physical_signal import PhysicalSignalConfig
from .mechanism_registry import RUNTIME_VERSION, mechanism_snapshot, set_mechanism
from .structured_events import StructuredEventBuffer
from .endogenous_motor import (
    EndogenousMotorCouplingConfig,
    local_asymmetry_from_world,
    update_motor_state,
)
from .motion_diagnostics import (
    MotionTraceBuffer,
    build_motion_causal_receipt,
    internal_summary,
    mechanical_stage_decomposition,
    sample_local_world,
)
from .cognition import (
    CognitionConfig,
    cognition_public_view,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.research import predictive_equivalence as pe
from .observation import accessible_observation, observation_bundle
from .diagnostics import (
    DecisionTraceBuffer,
    build_action_decision_receipt,
    counterfactual_candidate_probe,
)


@dataclass
class PhysicalSystemConfig:
    """MM 1.0 Tiktaalik defaults: validated morph/orient/endo ON.
    Historical manifests: from_dict missing keys → those mechanisms OFF.
    """
    runtime_version: str = RUNTIME_VERSION
    planet: PlanetConfig = field(default_factory=default_planet_config)
    body: PhysicalBodyConfig = field(default_factory=default_physical_body2_config)
    internal: InternalMediumConfig = field(default_factory=default_internal_medium_config)
    cognition: CognitionConfig = field(default_factory=CognitionConfig)
    endogenous_motor: EndogenousMotorCouplingConfig = field(default_factory=EndogenousMotorCouplingConfig)
    morphology_mechanics: MorphologyMechanicsConfig = field(default_factory=MorphologyMechanicsConfig)
    body_orientation: BodyOrientationConfig = field(default_factory=BodyOrientationConfig)
    body_deformation: BodyDeformationConfig = field(default_factory=BodyDeformationConfig)
    deformation_work: DeformationWorkConfig = field(default_factory=DeformationWorkConfig)
    environmental_resource: EnvironmentalResourceConfig = field(default_factory=EnvironmentalResourceConfig)
    complementary_resources: ComplementaryResourcesConfig = field(default_factory=ComplementaryResourcesConfig)
    endogenous_motor_work: EndogenousMotorWorkConfig = field(default_factory=EndogenousMotorWorkConfig)
    discrete_action_work: DiscreteActionWorkConfig = field(default_factory=DiscreteActionWorkConfig)
    physical_signal: PhysicalSignalConfig = field(default_factory=PhysicalSignalConfig)

    def copy(self) -> "PhysicalSystemConfig":
        return deepcopy(self)


def _config_from_dict(cls: type, values: dict[str, Any]) -> Any:
    fields = cls.__dataclass_fields__
    data = {key: value for key, value in values.items() if key in fields}
    if cls is PhysicalBodyConfig:
        if "permeability" in data:
            data["permeability"] = tuple(data["permeability"])
        if "footprint" in data:
            data["footprint"] = tuple(tuple(point) for point in data["footprint"])
    return cls(**data)


def _rng_unit(seed: int, tick: int) -> float:
    """Deterministic unit interval from seed+tick (no numpy global RNG)."""
    x = (int(seed) * 1000003 + int(tick) * 9176 + 1) % 2147483647
    return (x % 1000000) / 1000000.0


class PhysicalSystemRuntime:
    """Canonical state lineage X_t=(WORLD_t, BODY_t, INTERNAL_t) + optional cognition."""

    def __init__(
        self,
        *,
        seed: int = 17,
        config: PhysicalSystemConfig | None = None,
        model: str | None = None,
    ) -> None:
        if model == "tiktaalik" and config is None:
            from mechanistic_mind.model.tiktaalik import tiktaalik_config

            config = tiktaalik_config()
        self.seed = int(seed)
        self.config = (config or PhysicalSystemConfig()).copy()
        self.tick = 0
        self.world: PlanetState
        self.body: PhysicalBodyState
        self.internal: InternalMediumState
        self.last_internal_flux: MediumFluxRecord | None = None
        self.cognition: dict[str, Any] = empty_cognitive_state(self.config.cognition)
        self.last_agent_observation: dict[str, float] | None = None
        self.last_selected_action: str | None = None
        self.decision_trace = DecisionTraceBuffer(capacity=256)
        self.motion_trace = MotionTraceBuffer(capacity=256)
        self.motion_trace_enabled: bool = False
        self.motion_trace_mode: str = "every_10"
        self.last_motion_receipt: dict[str, Any] | None = None
        self._internal_c_prev = None
        self.last_endo_motor_meta: dict[str, Any] | None = None
        self.last_morphology_meta: dict[str, Any] | None = None
        self.last_orientation_meta: dict[str, Any] | None = None
        self.last_deformation_meta: dict[str, Any] | None = None
        self.last_work_ledger: dict[str, Any] | None = None
        self.last_resource_ledger: dict[str, Any] | None = None
        self.last_complementary_ledger: dict[str, Any] | None = None
        self.last_motor_work_ledger: dict[str, Any] | None = None
        self.last_action_work_ledger: dict[str, Any] | None = None
        self.last_work_allocation: dict[str, Any] | None = None
        self.last_force_contributions: dict[str, Any] | None = None
        self.structured_events = StructuredEventBuffer()
        self.action_trace_enabled: bool = False
        self.action_trace_mode: str = "every_10"  # every_1|every_10|every_50|on_change|on_long_wait
        self._prev_traced_action: str | None = None
        self._wait_run: int = 0
        self._resource_xfer_on: bool = False
        self._comp_xfer_A: bool = False
        self._comp_xfer_B: bool = False
        self._comp_conv_on: bool = False
        self._motor_drive_on: bool = False
        self._forced_action_once: str | None = None
        self._tick_ctx: dict[str, Any] | None = None
        self.reset()

    def reset(self, *, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = int(seed)
        self.world = initialize_planet(self.config.planet, seed=self.seed)
        self.body = initialize_physical_body(
            self.config.body,
            width=self.config.planet.width,
            height=self.config.planet.height,
        )
        self.internal = initialize_internal_medium(self.config.internal)
        self.tick = 0
        self.last_internal_flux = None
        self.cognition = empty_cognitive_state(self.config.cognition)
        self.last_agent_observation = None
        self.last_selected_action = None
        self.decision_trace = DecisionTraceBuffer(capacity=256)
        self.motion_trace = MotionTraceBuffer(capacity=256)
        self.last_motion_receipt = None
        self._internal_c_prev = None
        self.last_endo_motor_meta = None
        self.last_deformation_meta = None
        self.last_work_ledger = None
        self.last_resource_ledger = None
        self.last_complementary_ledger = None
        self.last_motor_work_ledger = None
        self.last_action_work_ledger = None
        self.last_work_allocation = None
        if self.config.deformation_work.enabled:
            self.body.mechanical_work_reservoir = float(self.config.deformation_work.reservoir_init)
        else:
            self.body.mechanical_work_reservoir = 0.0
        self._prev_traced_action = None
        self._wait_run = 0
        self._resource_xfer_on = False
        self._comp_xfer_A = False
        self._comp_xfer_B = False
        self._comp_conv_on = False
        self._motor_drive_on = False
        self._forced_action_once = None
        if self.config.cognition.cognition_enabled:
            self.last_agent_observation = self.agent_observation()

    def agent_observation(self) -> dict[str, float]:
        sig = getattr(self.config, "physical_signal", None)
        include = bool(sig is not None and sig.enabled and sig.perception_enabled)
        return accessible_observation(
            world=self.world,
            body=self.body,
            internal=self.internal,
            planet_config=self.config.planet,
            body_config=self.config.body,
            include_signal_fields=include,
        )

    def observation_views(self) -> dict[str, Any]:
        """Observer: WORLD TRUTH + AGENT OBSERVATION (separated)."""
        sig = getattr(self.config, "physical_signal", None)
        include = bool(sig is not None and sig.enabled and sig.perception_enabled)
        return observation_bundle(
            world=self.world,
            body=self.body,
            internal=self.internal,
            planet_config=self.config.planet,
            body_config=self.config.body,
            include_signal_fields=include,
        )

    def cognitive_view(self) -> dict[str, Any]:
        return cognition_public_view(self.cognition)

    def set_ablations(self, **flags: bool) -> None:
        """Research ablations: remove genuine causal contribution flags."""
        cfg = self.config.cognition
        for key, value in flags.items():
            if hasattr(cfg, key):
                setattr(cfg, key, bool(value))
        # refresh ablate flags inside stores without wiping learned state unless disabled
        self.cognition["config"] = cfg.to_dict()
        self.cognition["compression"]["ablate_compression"] = not cfg.predictive_compression
        self.cognition["multiscale"]["ablate_local"] = not cfg.multiscale_prediction
        self.cognition["multiscale"]["ablate_broader"] = not cfg.multiscale_prediction
        self.cognition["prospection"]["ablate_composition"] = not cfg.prospective_composition
        self.cognition["instrumental"]["ablate_learned"] = not cfg.instrumental_observation
        if "equivalence" in self.cognition:
            self.cognition["equivalence"]["enabled"] = bool(getattr(cfg, "predictive_equivalence", False))
        if "relevance" in self.cognition:
            self.cognition["relevance"]["enabled"] = bool(getattr(cfg, "predictive_relevance", False))
        if "temporal" in self.cognition:
            self.cognition["temporal"]["enabled"] = bool(getattr(cfg, "temporal_predictive_structure", False))
        if "temporal_bridge" in self.cognition:
            self.cognition["temporal_bridge"]["enabled"] = bool(getattr(cfg, "temporal_prospection_bridge", False))
        if "conflict" in self.cognition:
            self.cognition["conflict"]["enabled"] = bool(getattr(cfg, "predictive_conflict", False))
        if "future_action" in self.cognition:
            self.cognition["future_action"]["enabled"] = bool(getattr(cfg, "future_sensitive_action", False))
        if "prediction_revision" in self.cognition:
            self.cognition["prediction_revision"]["enabled"] = bool(getattr(cfg, "prediction_error_revision", False))
        if "temporal_prediction_error" in self.cognition:
            self.cognition["temporal_prediction_error"]["enabled"] = bool(getattr(cfg, "temporal_prediction_error", False))
        if "predicted_context_prospection" in self.cognition:
            self.cognition["predicted_context_prospection"]["enabled"] = bool(getattr(cfg, "predicted_context_prospection", False))
        if "multistep_action_prospection" in self.cognition:
            self.cognition["multistep_action_prospection"]["enabled"] = bool(getattr(cfg, "multistep_action_prospection", False))

    def _apply_resource_steps(self) -> None:
        skip_old = bool(
            self.config.complementary_resources.enabled
            and self.config.complementary_resources.conversion_enabled
        )
        self.last_resource_ledger = step_environmental_resource(
            self.body,
            self.world,
            self.config.body,
            self.config.environmental_resource,
            self.config.deformation_work,
            receipt_tick=int(self.tick),
            skip_conversion=skip_old,
        )
        self.last_complementary_ledger = step_complementary_resources(
            self.body,
            self.world,
            self.config.body,
            self.config.complementary_resources,
            self.config.deformation_work,
            receipt_tick=int(self.tick),
        )

    def _motor_increment_mode(self, site_path: bool) -> str:
        return "acceleration" if site_path else "force"

    def _compute_work_allocation(
        self,
        *,
        site_path: bool,
        endo_on: bool,
        action_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        mw_on = bool(self.config.endogenous_motor_work.enabled)
        shared_on = bool(mw_on or self.config.discrete_action_work.enabled)
        w_avail = float(getattr(self.body, "mechanical_work_reservoir", 0.0) or 0.0)
        w_def = 0.0
        if shared_on and self.config.body_deformation.enabled and self.config.deformation_work.enabled:
            w_def = preview_positive_actuator_work(
                self.body,
                self.config.body.footprint,
                self.config.body_deformation,
                self.config.deformation_work,
                env_force_body=getattr(self.body, "deformation_env_force", None),
            )
        w_mot = 0.0
        if mw_on and endo_on:
            # Explicit bridge chronology: action precedes motor. Preview motor
            # from the requested post-action velocity, assigning the KE cross
            # term to the later motor channel.
            adv = (action_request or {}).get("action_dv_requested_after_vmax") or [0.0, 0.0]
            w_mot = preview_motor_positive_work(
                vx=float(self.body.vx) + float(adv[0]),
                vy=float(self.body.vy) + float(adv[1]),
                drive_ux=float(self.body.motor_ux),
                drive_uy=float(self.body.motor_uy),
                mass=float(self.config.body.mass),
                v_max=float(self.config.body.v_max),
                increment_mode=self._motor_increment_mode(site_path),
            )
            mdv = requested_delta_v(
                vx=float(self.body.vx),
                vy=float(self.body.vy),
                drive_ux=float(self.body.motor_ux),
                drive_uy=float(self.body.motor_uy),
                mass=float(self.config.body.mass),
                v_max=float(self.config.body.v_max),
                increment_mode=self._motor_increment_mode(site_path),
            )
        else:
            mdv = (0.0, 0.0)
        w_action = (
            float((action_request or {}).get("action_work_requested") or 0.0)
            if self.config.discrete_action_work.enabled
            else 0.0
        )
        alloc = allocate_shared_work(w_avail, w_def, w_mot, w_action)
        alloc["accounting_enabled"] = mw_on
        alloc["shared_allocator_enabled"] = shared_on
        alloc["action_accounting_enabled"] = bool(self.config.discrete_action_work.enabled)
        alloc["policy"] = "PROPORTIONAL_THREE_WAY_POSITIVE_WORK"
        alloc["receipt_id"] = f"wa-{int(self.tick)}"
        alloc["evaluation_order"] = [
            "ACTION_REQUEST",
            "DEFORMATION_REQUEST",
            "MOTOR_REQUEST_AT_POST_ACTION_REQUEST_VELOCITY",
        ]
        adv = (action_request or {}).get("action_dv_requested_after_vmax") or [0.0, 0.0]
        cross = float(self.config.body.mass) * (
            float(adv[0]) * float(mdv[0]) + float(adv[1]) * float(mdv[1])
        )
        alloc["motor_action_ke_cross_term"] = cross
        alloc["cross_term_attribution"] = (
            "SEQUENTIAL_TO_LATER_MOTOR_CHANNEL; symmetric diagnostic halves also reported"
        )
        alloc["cross_term_symmetric_action"] = 0.5 * cross
        alloc["cross_term_symmetric_motor"] = 0.5 * cross
        self.last_work_allocation = alloc
        return alloc

    def _apply_realized_motor(self, *, site_path: bool, endo_on: bool, alloc: dict[str, Any] | None) -> None:
        if not endo_on:
            self.last_motor_work_ledger = None
            return
        mw_on = bool(self.config.endogenous_motor_work.enabled)
        budget = None if (not mw_on or alloc is None) else float(alloc.get("allocated_motor") or 0.0)
        self.last_motor_work_ledger = apply_motor_realization(
            self.body,
            mass=float(self.config.body.mass),
            v_max=float(self.config.body.v_max),
            increment_mode=self._motor_increment_mode(site_path),
            accounting_enabled=mw_on,
            work_budget=budget,
            receipt_tick=int(self.tick),
            reservoir_max=float(self.config.deformation_work.reservoir_max),
        )

    def begin_tick(self, *, observation: dict[str, float] | None = None) -> str:
        """Observe, learn, select, realize action impulse. Does not advance world."""
        if not (self.tick == self.body.tick == self.internal.tick):
            raise RuntimeError("physical subsystem tick mismatch before step")
        if self.world.tick not in (self.tick, self.tick + 1):
            raise RuntimeError("physical subsystem tick mismatch before step")

        morph_on = bool(self.config.morphology_mechanics.enabled)
        orient_on = bool(self.config.body_orientation.enabled)
        endo_on = bool(self.config.endogenous_motor.enabled)
        mw_on = bool(self.config.endogenous_motor_work.enabled)
        action_work_on = bool(self.config.discrete_action_work.enabled)
        site_path = morph_on or orient_on
        selected = "WAIT"
        body_before = self.body.snapshot()
        cognition_result = None
        decision_tick = int(self.tick)
        if self.config.cognition.cognition_enabled:
            obs = observation if observation is not None else self.agent_observation()
            cognition_result = run_cognition_before_action(
                self.cognition,
                observation=obs,
                tick=self.tick,
                rng_value=_rng_unit(self.seed, self.tick),
            )
            selected = cognition_result.selected_action
            self.last_agent_observation = obs
            self.last_selected_action = selected
        else:
            self.last_selected_action = "WAIT"
            if observation is not None:
                self.last_agent_observation = observation

        if self._forced_action_once is not None:
            selected = str(self._forced_action_once)
            self._forced_action_once = None
            self.last_selected_action = selected
            if self.config.cognition.cognition_enabled:
                self.cognition["last_action"] = selected
                self.cognition["last_selection"] = {
                    **(self.cognition.get("last_selection") or {}),
                    "action": selected,
                    "source": "FORCED_GATE",
                }

        action_request = request_discrete_action(
            action=selected,
            vx=float(self.body.vx),
            vy=float(self.body.vy),
            mass=float(self.config.body.mass),
            v_max=float(self.config.body.v_max),
            impulse_scale=float(self.config.discrete_action_work.impulse_scale),
            tick=int(self.tick),
        )
        alloc = self._compute_work_allocation(
            site_path=site_path,
            endo_on=endo_on,
            action_request=action_request,
        )
        self.last_action_work_ledger = realize_discrete_action(
            self.body,
            action_request,
            accounting_enabled=action_work_on,
            allocated_work=(
                float(alloc.get("allocated_action") or 0.0)
                if action_work_on else None
            ),
            reservoir_max=float(self.config.deformation_work.reservoir_max),
        )
        self.cognition["last_apply"] = {
            "action": selected,
            "applied": bool(action_request.get("bridge_available")),
            "bridge": action_request.get("bridge"),
            "detail": deepcopy(self.last_action_work_ledger),
        }

        # Capture post-action-realization body. WAIT leaves vx/vy unchanged.
        body_after_impulse = self.body.snapshot()
        imp = self.last_action_work_ledger.get("action_dv_realized") or [0.0, 0.0]
        impulse = (float(imp[0]), float(imp[1]))
        internal_before = internal_summary(self.internal)
        self._tick_ctx = {
            "morph_on": morph_on,
            "orient_on": orient_on,
            "endo_on": endo_on,
            "mw_on": mw_on,
            "action_work_on": action_work_on,
            "site_path": site_path,
            "selected": selected,
            "body_before": body_before,
            "cognition_result": cognition_result,
            "decision_tick": decision_tick,
            "alloc": alloc,
            "body_after_impulse": body_after_impulse,
            "impulse": impulse,
            "internal_before": internal_before,
        }
        return selected

    def finish_tick(self, *, skip_planet: bool = False, skip_resources: bool = False) -> None:
        """Advance world (optional), body, internal, resources. Completes one tick."""
        ctx = self._tick_ctx or {}
        morph_on = ctx.get("morph_on", bool(self.config.morphology_mechanics.enabled))
        orient_on = ctx.get("orient_on", bool(self.config.body_orientation.enabled))
        endo_on = ctx.get("endo_on", bool(self.config.endogenous_motor.enabled))
        mw_on = ctx.get("mw_on", bool(self.config.endogenous_motor_work.enabled))
        action_work_on = ctx.get("action_work_on", bool(self.config.discrete_action_work.enabled))
        site_path = ctx.get("site_path", morph_on or orient_on)
        selected = ctx.get("selected", self.last_selected_action or "WAIT")
        body_before = ctx.get("body_before") or self.body.snapshot()
        cognition_result = ctx.get("cognition_result")
        decision_tick = int(ctx.get("decision_tick", self.tick))
        alloc = ctx.get("alloc") or self.last_work_allocation or {}
        body_after_impulse = ctx.get("body_after_impulse") or self.body.snapshot()
        impulse = ctx.get("impulse") or (0.0, 0.0)
        internal_before = ctx.get("internal_before") or internal_summary(self.internal)

        if not skip_planet:
            step_planet(self.world, self.config.planet, seed=self.seed)
        local_world = sample_local_world(self.body, self.world, self.config.body)
        mech_decomp = mechanical_stage_decomposition(
            vx_before_mech=float(body_after_impulse["vx"]),
            vy_before_mech=float(body_after_impulse["vy"]),
            mech_before=float(body_after_impulse["mech"]),
            local=local_world,
            cfg=self.config.body,
            motor_ux=float(body_after_impulse.get("motor_ux", 0.0)),
            motor_uy=float(body_after_impulse.get("motor_uy", 0.0)),
            endogenous_motor_enabled=bool(self.config.endogenous_motor.enabled),
        )
        # Avoid double-counting lumped ENV→force when site-level path is active.
        endo_in_dynamics = endo_on and (not site_path) and (not mw_on)
        step_physical_body(
            self.body,
            self.world,
            self.config.body,
            endogenous_motor_enabled=endo_in_dynamics,
            skip_material=site_path,
            skip_mechanical=site_path,
        )
        force_contrib = {
            "environmental_site": [0.0, 0.0],
            "endogenous_motor": [0.0, 0.0],
            "discrete_action": [float(impulse[0]), float(impulse[1])],
            "discrete_action_quantity": "DELTA_V_NOT_FORCE",
            "discrete_action_requested_delta_v": list(
                self.last_action_work_ledger.get("action_dv_requested") or [0.0, 0.0]
            ),
            "note": (
                "Site path replaces lumped flow/drag/wave when morph|orient ON; "
                "endo motor_u is CoM-only (no torque) and composed after site forces."
            ),
        }
        if site_path:
            _coup = self.config.internal.coupling_enabled
            self.config.internal.coupling_enabled = False
            self.last_internal_flux = step_internal_medium(
                self.internal, self.body, self.config.internal
            )
            self.config.internal.coupling_enabled = _coup
            if orient_on:
                ke_before = kinetic_energy(
                    self.body, self.config.body.mass, self.config.body_orientation.inertia
                )
                if not skip_resources:
                    self._apply_resource_steps()
                self.last_orientation_meta = step_orientation_mechanics(
                    self.body,
                    self.world,
                    self.config.body,
                    self.config.body_orientation,
                    self.config.morphology_mechanics,
                    self.config.body_deformation,
                    internal_c=self.internal.c,
                    work_cfg=self.config.deformation_work,
                    work_budget=(
                        None if not (mw_on or action_work_on)
                        else float(alloc.get("allocated_deformation") or 0.0)
                    ),
                )
                self.last_deformation_meta = (self.last_orientation_meta or {}).get("deformation")
                dm = self.last_deformation_meta or {}
                ke_after = kinetic_energy(
                    self.body, self.config.body.mass, self.config.body_orientation.inertia
                )
                d_drag = drag_dissipation(
                    float(self.body.vx),
                    float(self.body.vy),
                    float(self.body.omega),
                    float(self.config.body.drag),
                    float(self.config.body_orientation.angular_drag),
                )
                self.last_work_ledger = {
                    **{k: dm.get(k) for k in (
                        "mechanical_energy_accounting",
                        "reservoir_before",
                        "reservoir_after",
                        "reservoir_work_supplied",
                        "reservoir_work_recovered",
                        "actuator_work",
                        "env_work_on_deformation",
                        "delta_potential",
                        "potential_before",
                        "potential_after",
                        "dissipated_viscous",
                        "deformation_residual",
                        "known_quadrature",
                        "unexplained_residual",
                        "first_law",
                        "actuator_scale",
                        "work_limited",
                        "reservoir_depleted",
                        "shape_change_source",
                        "where_did_the_work_come_from",
                        "work_transfer_enabled",
                    )},
                    "kinetic_before": ke_before,
                    "kinetic_after": ke_after,
                    "kinetic_change": ke_after - ke_before,
                    "com_drag_dissipation": d_drag,
                    "motor_u_channel": "DRIVE_THEN_REALIZATION",
                    "resource": self.last_resource_ledger,
                    "complementary": self.last_complementary_ledger,
                }
                self.last_morphology_meta = {
                    "enabled": morph_on,
                    "via": "body_orientation" if morph_on else "orientation_uniform_susc",
                    "net_force": (self.last_orientation_meta or {}).get("net_force"),
                    "B_site_spread": (self.last_orientation_meta or {}).get("B_site_spread"),
                }
                nf = (self.last_orientation_meta or {}).get("net_force") or [0.0, 0.0]
                force_contrib["environmental_site"] = [float(nf[0]), float(nf[1])]
            else:
                self.last_morphology_meta = step_morphology_mechanics(
                    self.body,
                    self.world,
                    self.config.body,
                    self.config.morphology_mechanics,
                    internal_c=self.internal.c,
                )
                self.last_orientation_meta = {"enabled": False}
                self.last_deformation_meta = None
                self.last_work_ledger = None
                if not skip_resources:
                    self._apply_resource_steps()
                nf = (self.last_morphology_meta or {}).get("net_force") or [0.0, 0.0]
                force_contrib["environmental_site"] = [float(nf[0]), float(nf[1])]
            # Compose endogenous motor as center-applied translation (no torque).
            if endo_on:
                self._apply_realized_motor(site_path=True, endo_on=True, alloc=alloc if mw_on else None)
                ml = self.last_motor_work_ledger or {}
                force_contrib["endogenous_motor"] = list(ml.get("motor_force_realized") or [0.0, 0.0])
                force_contrib["endogenous_motor_drive"] = list(ml.get("motor_drive_requested") or [0.0, 0.0])
                force_contrib["endogenous_motor_work"] = {
                    "requested": ml.get("motor_work_requested"),
                    "realized": ml.get("motor_work_realized"),
                    "unrealized": ml.get("motor_work_unrealized"),
                    "limited": ml.get("work_limited"),
                }
                if self.config.body.displacement_enabled and not orient_on:
                    pass
                elif self.config.body.displacement_enabled and orient_on:
                    pass
        else:
            self.last_internal_flux = step_internal_medium(
                self.internal, self.body, self.config.internal
            )
            self.last_morphology_meta = {"enabled": False}
            self.last_orientation_meta = {"enabled": False}
            self.last_deformation_meta = None
            self.last_work_ledger = None
            if not skip_resources:
                self._apply_resource_steps()
            if endo_on and mw_on:
                self._apply_realized_motor(site_path=False, endo_on=True, alloc=alloc)
                ml = self.last_motor_work_ledger or {}
                force_contrib["endogenous_motor"] = list(ml.get("motor_force_realized") or [0.0, 0.0])
                force_contrib["endogenous_motor_drive"] = list(ml.get("motor_drive_requested") or [0.0, 0.0])
            elif endo_on:
                force_contrib["endogenous_motor"] = [float(self.body.motor_ux), float(self.body.motor_uy)]
        self.last_force_contributions = force_contrib
        if self.last_work_ledger is None:
            self.last_work_ledger = {}
        self.last_work_ledger["work_allocation"] = self.last_work_allocation
        self.last_work_ledger["motor"] = self.last_motor_work_ledger
        self.last_work_ledger["discrete_action"] = self.last_action_work_ledger
        action_debit = float((self.last_action_work_ledger or {}).get("action_work_realized") or 0.0)
        motor_debit = float((self.last_motor_work_ledger or {}).get("motor_work_realized") or 0.0)
        deformation_debit = float((self.last_deformation_meta or {}).get("reservoir_work_supplied") or 0.0)
        available_alloc = float((self.last_work_allocation or {}).get("available") or 0.0)
        self.last_work_ledger["three_way_budget"] = {
            "action_work_realized": action_debit,
            "motor_work_realized": motor_debit,
            "deformation_work_realized": deformation_debit,
            "total_positive_debit": action_debit + motor_debit + deformation_debit,
            "allocation_available": available_alloc,
            "allocation_residual": (
                available_alloc - action_debit - motor_debit - deformation_debit
            ),
            "no_double_spend": bool(
                action_debit + motor_debit + deformation_debit
                <= available_alloc + 1e-9
            ),
            "environmental_work_external": True,
        }
        motor_signed = float((self.last_motor_work_ledger or {}).get("kinetic_energy_change_from_motor") or 0.0)
        if "kinetic_change" in self.last_work_ledger:
            site_dke = float(self.last_work_ledger.get("kinetic_change") or 0.0)
        else:
            ke_enter = (
                0.5 * float(self.config.body.mass)
                * (float(body_after_impulse["vx"]) ** 2 + float(body_after_impulse["vy"]) ** 2)
                + 0.5 * float(self.config.body_orientation.inertia)
                * float(body_after_impulse.get("omega", 0.0)) ** 2
            )
            site_dke = (
                kinetic_energy(
                    self.body,
                    self.config.body.mass,
                    self.config.body_orientation.inertia,
                )
                - ke_enter
                - motor_signed
            )
        com_drag = float(self.last_work_ledger.get("com_drag_dissipation") or 0.0)
        env_shape = float(self.last_work_ledger.get("env_work_on_deformation") or 0.0)
        action_signed = float((self.last_action_work_ledger or {}).get("action_work_signed_realized") or 0.0)
        self.last_work_ledger["multi_channel_energy"] = {
            "W_environment": env_shape + site_dke + com_drag,
            "W_environment_is_external": True,
            "W_motor": motor_debit,
            "W_action": action_debit,
            "W_action_negative_dissipative": float(
                (self.last_action_work_ledger or {}).get("action_negative_work_realized") or 0.0
            ),
            "W_deformation": deformation_debit,
            "delta_KE": action_signed + site_dke + motor_signed,
            "dissipation": com_drag + float(self.last_work_ledger.get("dissipated_viscous") or 0.0),
            "stored_deformation_energy_change": float(self.last_work_ledger.get("delta_potential") or 0.0),
            "deformation_residual": float(self.last_work_ledger.get("deformation_residual") or 0.0),
            "note": (
                "W_environment combines external site/shape work and site-stage "
                "KE change corrected for reported drag; it never debits the reservoir."
            ),
        }
        if self.last_motor_work_ledger:
            self.last_work_ledger["motor_work_realized"] = self.last_motor_work_ledger.get("motor_work_realized")
            self.last_work_ledger["motor_work_requested"] = self.last_motor_work_ledger.get("motor_work_requested")
            self.last_work_ledger["mechanical_work_reservoir_after_motor"] = self.last_motor_work_ledger.get("mechanical_work_reservoir_after")
        # Update endogenous motor state for NEXT tick (established lag).
        asym_x, asym_y, asym_src = local_asymmetry_from_world(
            body_x=float(self.body.x),
            body_y=float(self.body.y),
            planet=self.world,
            body_vx=float(self.body.vx),
            body_vy=float(self.body.vy),
        )
        ux, uy, endo_meta = update_motor_state(
            motor_ux=float(self.body.motor_ux),
            motor_uy=float(self.body.motor_uy),
            c_now=self.internal.c,
            c_prev=self._internal_c_prev,
            body_B=self.body.B,
            cfg=self.config.endogenous_motor,
            asym_x=asym_x,
            asym_y=asym_y,
        )
        endo_meta = {**endo_meta, "asymmetry_source": asym_src, "composed_with_site_path": bool(site_path)}
        self.body.motor_ux = ux
        self.body.motor_uy = uy
        self.last_endo_motor_meta = endo_meta
        self._internal_c_prev = np.asarray(self.internal.c, dtype=np.float64).copy()
        self._emit_structured_events(selected=selected, body_before=body_before)
        self.tick += 1
        body_after = self.body.snapshot()
        internal_after = internal_summary(self.internal)
        self.decision_trace.add_position(
            tick=self.tick, x=body_after["x"], y=body_after["y"], action=selected
        )
        if cognition_result is not None:
            self._maybe_record_decision_receipt(
                decision_tick=decision_tick,
                result=cognition_result,
                body_before=body_before,
                body_after=body_after,
            )
        self._maybe_record_motion_receipt(
            decision_tick=decision_tick,
            selected=selected,
            action_source=(
                None if cognition_result is None else cognition_result.selection_source
            ),
            impulse=impulse,
            body_before_action=body_before,
            body_after_impulse=body_after_impulse,
            body_after=body_after,
            internal_before=internal_before,
            internal_after=internal_after,
            local_world=local_world,
            mech_decomp=mech_decomp,
        )
        if not (self.tick == self.world.tick == self.body.tick == self.internal.tick):
            raise RuntimeError("physical subsystem tick mismatch after step")
        self._tick_ctx = None

    def step(self, n: int = 1) -> None:
        for _ in range(max(1, int(n))):
            self.begin_tick()
            self.finish_tick()

    def step_forced_action(self, action: str) -> None:
        """Research helper: downstream selected-action override, normal physics."""
        self._forced_action_once = str(action)
        self.step()



    def _emit_structured_events(self, *, selected: str, body_before: dict[str, Any]) -> None:
        tick = int(self.tick)
        dx = float(self.body.x) - float(body_before.get("x", self.body.x))
        dy = float(self.body.y) - float(body_before.get("y", self.body.y))
        if abs(dx) + abs(dy) > 1e-9 or abs(self.body.vx) + abs(self.body.vy) > 1e-9:
            self.structured_events.emit(
                "BODY_MOVED",
                tick=tick,
                evidence={
                    "dx": dx, "dy": dy,
                    "vx": float(self.body.vx), "vy": float(self.body.vy),
                    "forces": self.last_force_contributions,
                    "action": selected,
                },
            )
        om = self.last_orientation_meta or {}
        if om.get("enabled") and abs(float(om.get("tau") or 0.0)) > 1e-9:
            self.structured_events.emit(
                "BODY_ROTATED",
                tick=tick,
                evidence={
                    "tau": om.get("tau"),
                    "omega": float(getattr(self.body, "omega", 0.0)),
                    "theta": float(getattr(self.body, "theta", 0.0)),
                    "alpha": om.get("alpha"),
                },
            )
        spread = om.get("B_site_spread")
        if self.body.B_site is not None and spread is not None:
            self.structured_events.emit(
                "LOCAL_MATERIAL_CHANGED",
                tick=tick,
                evidence={"B_site_spread": spread},
            )
        dm = self.last_deformation_meta or {}
        before = np.asarray(dm.get("deformation_before") or [], dtype=float)
        after = np.asarray(dm.get("deformation") or [], dtype=float)
        if dm.get("enabled") and before.shape == after.shape and before.size and np.max(np.abs(after - before)) > 1e-12:
            evidence = {
                "B_site_norms": dm.get("B_site_norms"),
                "deformation_before": dm.get("deformation_before"),
                "deformation": dm.get("deformation"),
                "shape_change_source": dm.get("shape_change_source"),
                "where_did_the_work_come_from": dm.get("where_did_the_work_come_from"),
                "actuator_work": dm.get("actuator_work"),
                "env_work_on_deformation": dm.get("env_work_on_deformation"),
                "reservoir_work_supplied": dm.get("reservoir_work_supplied"),
            }
            self.structured_events.emit("BODY_DEFORMED", tick=tick, evidence=evidence)
            src = str(dm.get("shape_change_source") or "")
            if src == "INTERNALLY_POWERED" or float(dm.get("reservoir_work_supplied") or 0) > 1e-12:
                self.structured_events.emit("DEFORMATION_POWERED", tick=tick, evidence=evidence)
            if src == "ENVIRONMENTALLY_FORCED" or (
                float(dm.get("env_work_on_deformation") or 0) > 1e-12
                and float(dm.get("reservoir_work_supplied") or 0) <= 1e-12
            ):
                self.structured_events.emit("DEFORMATION_EXTERNALLY_FORCED", tick=tick, evidence=evidence)
            if src == "PASSIVE_RELAXATION":
                self.structured_events.emit("DEFORMATION_RELAXED", tick=tick, evidence=evidence)
            if dm.get("work_limited"):
                self.structured_events.emit("DEFORMATION_WORK_LIMITED", tick=tick, evidence={
                    "actuator_scale": dm.get("actuator_scale"),
                    "reservoir_after": dm.get("reservoir_after"),
                })
            if float(dm.get("reservoir_work_supplied") or 0) > 1e-12:
                self.structured_events.emit("WORK_TRANSFERRED", tick=tick, evidence={
                    "supplied": dm.get("reservoir_work_supplied"),
                    "actuator_work": dm.get("actuator_work"),
                    "delta_potential": dm.get("delta_potential"),
                    "dissipated_viscous": dm.get("dissipated_viscous"),
                    "residual": dm.get("deformation_residual"),
                })
            if float(dm.get("delta_potential") or 0) < -1e-12:
                self.structured_events.emit("STORED_MECHANICAL_ENERGY_RELEASED", tick=tick, evidence={
                    "delta_potential": dm.get("delta_potential"),
                    "env_work_on_deformation": dm.get("env_work_on_deformation"),
                    "dissipated_viscous": dm.get("dissipated_viscous"),
                    "recovered": dm.get("reservoir_work_recovered"),
                })
            if dm.get("geometry_coupling_enabled"):
                self.structured_events.emit(
                    "SITE_GEOMETRY_CHANGED",
                    tick=tick,
                    evidence={**evidence, "actual_geometry": dm.get("actual_geometry")},
                )
        if float(dm.get("reservoir_before") or 0) > 1e-12 and float(dm.get("reservoir_after") or 0) <= 1e-12:
            self.structured_events.emit(
                "WORK_RESERVOIR_DEPLETED",
                tick=tick,
                evidence={"reservoir_after": dm.get("reservoir_after")},
            )
        rl = self.last_resource_ledger or {}
        acq = float(rl.get("acquired_by_body") or 0.0)
        if acq > 1e-12:
            if not self._resource_xfer_on:
                self.structured_events.emit(
                    "RESOURCE_TRANSFER_STARTED",
                    tick=tick,
                    evidence={"site_transfers": rl.get("site_transfers"), "acquired": acq},
                )
            self._resource_xfer_on = True
            self.structured_events.emit(
                "RESOURCE_TRANSFERRED",
                tick=tick,
                evidence={
                    "site_transfers": rl.get("site_transfers"),
                    "removed": rl.get("removed_from_env"),
                    "acquired": acq,
                    "loss": rl.get("transfer_loss"),
                    "residual": rl.get("transfer_residual"),
                },
            )
        else:
            self._resource_xfer_on = False
        if rl.get("source_depleted_cells"):
            self.structured_events.emit(
                "RESOURCE_SOURCE_DEPLETED",
                tick=tick,
                evidence={"cells": rl.get("source_depleted_cells")},
            )
        if rl.get("capacity_reached_sites") and acq > 1e-12:
            self.structured_events.emit(
                "BODY_RESOURCE_CAPACITY_REACHED",
                tick=tick,
                evidence={"sites": rl.get("capacity_reached_sites"), "R_site": rl.get("R_site")},
            )
        cred = float(rl.get("work_credited") or 0.0)
        if cred > 1e-12:
            ev = {
                "converted_R": rl.get("converted_R"),
                "work_credited": cred,
                "conversion_loss_work": rl.get("conversion_loss_work"),
                "residual": rl.get("conversion_residual"),
                "where_did_this_work_come_from": rl.get("where_did_this_work_come_from"),
            }
            self.structured_events.emit("RESOURCE_CONVERTED_TO_WORK", tick=tick, evidence=ev)
            self.structured_events.emit("WORK_RESERVOIR_REPLENISHED", tick=tick, evidence={
                "reservoir_before": rl.get("reservoir_before"),
                "reservoir_after": rl.get("reservoir_after"),
                "work_credited": cred,
            })
        cl = self.last_complementary_ledger or {}
        a_acq = float((cl.get("A") or {}).get("acquired") or 0.0)
        b_acq = float((cl.get("B") or {}).get("acquired") or 0.0)
        if a_acq > 1e-12:
            self.structured_events.emit(
                "RESOURCE_A_TRANSFERRED",
                tick=tick,
                evidence={"transfers": (cl.get("A") or {}).get("transfers"), "acquired": a_acq},
            )
            self._comp_xfer_A = True
        else:
            self._comp_xfer_A = False
        if b_acq > 1e-12:
            self.structured_events.emit(
                "RESOURCE_B_TRANSFERRED",
                tick=tick,
                evidence={"transfers": (cl.get("B") or {}).get("transfers"), "acquired": b_acq},
            )
            self._comp_xfer_B = True
        else:
            self._comp_xfer_B = False
        if (cl.get("A") or {}).get("capacity_sites") and a_acq > 1e-12:
            self.structured_events.emit(
                "RESOURCE_A_CAPACITY_REACHED",
                tick=tick,
                evidence={"sites": (cl.get("A") or {}).get("capacity_sites")},
            )
        if (cl.get("B") or {}).get("capacity_sites") and b_acq > 1e-12:
            self.structured_events.emit(
                "RESOURCE_B_CAPACITY_REACHED",
                tick=tick,
                evidence={"sites": (cl.get("B") or {}).get("capacity_sites")},
            )
        if (cl.get("A") or {}).get("depleted"):
            self.structured_events.emit(
                "RESOURCE_A_DEPLETED",
                tick=tick,
                evidence={"cells": (cl.get("A") or {}).get("depleted")},
            )
        if (cl.get("B") or {}).get("depleted"):
            self.structured_events.emit(
                "RESOURCE_B_DEPLETED",
                tick=tick,
                evidence={"cells": (cl.get("B") or {}).get("depleted")},
            )
        lim = str(cl.get("limiting_resource") or "NONE")
        if lim == "A":
            self.structured_events.emit(
                "RESOURCE_A_LIMITING",
                tick=tick,
                evidence={"body_A": cl.get("body_A"), "body_B": cl.get("body_B"), "consumed_A": cl.get("consumed_A"), "consumed_B": cl.get("consumed_B")},
            )
        elif lim == "B":
            self.structured_events.emit(
                "RESOURCE_B_LIMITING",
                tick=tick,
                evidence={"body_A": cl.get("body_A"), "body_B": cl.get("body_B"), "consumed_A": cl.get("consumed_A"), "consumed_B": cl.get("consumed_B")},
            )
        ccred = float(cl.get("work_credited") or 0.0)
        if ccred > 1e-12:
            self.structured_events.emit(
                "COMPLEMENTARY_CONVERSION",
                tick=tick,
                evidence={
                    "AVAILABLE_A": cl.get("body_A"),
                    "AVAILABLE_B": cl.get("body_B"),
                    "REQUIRED_RATIO": cl.get("stoich"),
                    "CONSUMED_A": cl.get("consumed_A"),
                    "CONSUMED_B": cl.get("consumed_B"),
                    "WORK_PRODUCED": ccred,
                    "LIMITING_RESOURCE": lim,
                    "conversion_loss": cl.get("conversion_loss_work"),
                },
            )
            self.structured_events.emit("WORK_RESERVOIR_REPLENISHED", tick=tick, evidence={
                "reservoir_before": cl.get("reservoir_before"),
                "reservoir_after": cl.get("reservoir_after"),
                "work_credited": ccred,
                "path": "complementary",
            })
            self._comp_conv_on = True
        else:
            if self._comp_conv_on and bool(cl.get("conversion_enabled")):
                self.structured_events.emit(
                    "COMPLEMENTARY_CONVERSION_STOPPED",
                    tick=tick,
                    evidence={"limiting_resource": lim, "body_A": cl.get("body_A"), "body_B": cl.get("body_B")},
                )
            self._comp_conv_on = False
        ml = self.last_motor_work_ledger or {}
        drive = ml.get("motor_drive_requested") or [0.0, 0.0]
        drive_mag = abs(float(drive[0])) + abs(float(drive[1]))
        if drive_mag > 1e-12:
            if not self._motor_drive_on:
                self.structured_events.emit(
                    "MOTOR_DRIVE_GENERATED",
                    tick=tick,
                    evidence={"drive": drive, "receipt_id": ml.get("receipt_id")},
                )
            self._motor_drive_on = True
            wreq = float(ml.get("motor_work_requested") or 0.0)
            if wreq > 1e-12:
                self.structured_events.emit(
                    "MOTOR_WORK_REQUESTED",
                    tick=tick,
                    evidence={"work": wreq, "force": ml.get("motor_force_requested"), "receipt_id": ml.get("receipt_id")},
                )
            wreal = float(ml.get("motor_work_realized") or 0.0)
            if wreal > 1e-12:
                self.structured_events.emit(
                    "MOTOR_WORK_REALIZED",
                    tick=tick,
                    evidence={"work": wreal, "force": ml.get("motor_force_realized"), "receipt_id": ml.get("receipt_id")},
                )
                self.structured_events.emit(
                    "WORK_ALLOCATED_TO_MOTOR",
                    tick=tick,
                    evidence={"allocated": (self.last_work_allocation or {}).get("allocated_motor"), "realized": wreal},
                )
            if ml.get("work_limited"):
                self.structured_events.emit(
                    "MOTOR_WORK_LIMITED",
                    tick=tick,
                    evidence={"fraction": ml.get("work_limit_fraction"), "unrealized": ml.get("motor_work_unrealized"), "receipt_id": ml.get("receipt_id")},
                )
            if ml.get("work_unavailable"):
                self.structured_events.emit(
                    "MOTOR_WORK_UNAVAILABLE",
                    tick=tick,
                    evidence={"requested": wreq, "reservoir": ml.get("mechanical_work_reservoir_after"), "receipt_id": ml.get("receipt_id")},
                )
        else:
            self._motor_drive_on = False
        al = self.last_action_work_ledger or {}
        _sel_for_action = (self.cognition.get("last_selection") or {}) if isinstance(self.cognition, dict) else {}
        _action_source = str(_sel_for_action.get("source") or "") or None
        if not self.config.cognition.cognition_enabled:
            _action_source = "COGNITION_DISABLED"
        self.structured_events.emit(
            "DISCRETE_ACTION_SELECTED",
            tick=tick,
            evidence={
                "selected_action": selected,
                "selection_source": _action_source,
                "selection_rule": _sel_for_action.get("selection_rule"),
                "receipt_id": al.get("receipt_id"),
                "selection_is_upstream_of_work": True,
            },
        )
        action_req = float(al.get("action_work_requested") or 0.0)
        if action_req > 1e-12:
            self.structured_events.emit(
                "ACTION_WORK_REQUESTED",
                tick=tick,
                evidence={
                    "selected_action": selected,
                    "dv_requested": al.get("action_dv_requested"),
                    "impulse_requested": al.get("action_impulse_requested"),
                    "work_requested": action_req,
                    "receipt_id": al.get("receipt_id"),
                },
            )
            self.structured_events.emit(
                "ACTION_WORK_ALLOCATED",
                tick=tick,
                evidence={
                    "work_allocated": al.get("action_work_allocated"),
                    "allocation_receipt": (self.last_work_allocation or {}).get("receipt_id"),
                },
            )
        action_real = float(al.get("action_work_realized") or 0.0)
        if action_real > 1e-12:
            self.structured_events.emit(
                "ACTION_WORK_REALIZED",
                tick=tick,
                evidence={
                    "work_realized": action_real,
                    "impulse_realized": al.get("action_impulse_realized"),
                    "receipt_id": al.get("receipt_id"),
                },
            )
        if selected.startswith("MOVE"):
            self.structured_events.emit(
                "ACTION_PHYSICAL_REALIZATION",
                tick=tick,
                evidence={
                    "selected_action": selected,
                    "dv_requested": al.get("action_dv_requested"),
                    "dv_realized": al.get("action_dv_realized"),
                    "work_limit_fraction": al.get("action_work_limit_fraction"),
                    "receipt_id": al.get("receipt_id"),
                },
            )
        if al.get("work_limited"):
            self.structured_events.emit(
                "ACTION_WORK_LIMITED",
                tick=tick,
                evidence={
                    "unrealized": al.get("action_work_unrealized"),
                    "fraction": al.get("action_work_limit_fraction"),
                    "receipt_id": al.get("receipt_id"),
                },
            )
        if al.get("work_unavailable"):
            self.structured_events.emit(
                "ACTION_WORK_UNAVAILABLE",
                tick=tick,
                evidence={
                    "requested": action_req,
                    "selected_action": selected,
                    "receipt_id": al.get("receipt_id"),
                },
            )
        # SCENARIO_SELECTED: cognitive scenario/prospective selection outcome.
        # WAIT must not hide a genuine PROSPECTIVE_* selection (observability only).
        # Fallback / endogenous / forced WAIT must NOT masquerade as scenario selection.
        # Non-WAIT emission preserved for prior MOVE observability regardless of source.
        _SCENARIO_SELECTION_SOURCES = frozenset({
            "PROSPECTIVE_SCENARIO",
            "PROSPECTIVE_TIE_RESOLUTION",
            "PROSPECTIVE_CONTINUATION",
        })
        sel_meta = (self.cognition.get("last_selection") or {}) if isinstance(self.cognition, dict) else {}
        sel_source = str(sel_meta.get("source") or "")
        sel_action = str(sel_meta.get("action") or "")
        cognition_on = bool(self.config.cognition.cognition_enabled)
        emit_scenario = False
        if selected and selected != "WAIT":
            emit_scenario = True
        elif (
            selected == "WAIT"
            and cognition_on
            and sel_action == "WAIT"
            and sel_source in _SCENARIO_SELECTION_SOURCES
        ):
            emit_scenario = True
        if emit_scenario:
            competition = sel_meta.get("competition") if isinstance(sel_meta.get("competition"), dict) else {}
            candidates = sel_meta.get("candidates")
            evidence_sc: dict[str, Any] = {
                "action": selected,
                "selected_action": selected,
                "selection_source": sel_source or None,
                "selection_rule": sel_meta.get("selection_rule"),
                "prospective_selection_mode": sel_meta.get("prospective_selection_mode"),
            }
            if isinstance(candidates, list):
                evidence_sc["candidate_count"] = len(candidates)
                evidence_sc["candidates"] = list(candidates)
            if competition:
                for key in (
                    "outcome_class",
                    "selection_reason",
                    "supported_actions",
                    "unsupported_actions",
                    "selected_scenario",
                    "tie_resolution",
                ):
                    if competition.get(key) is not None:
                        evidence_sc[key] = competition.get(key)
            self.structured_events.emit(
                "SCENARIO_SELECTED",
                tick=tick,
                evidence=evidence_sc,
            )

    def mechanisms(self) -> dict[str, Any]:
        return mechanism_snapshot(self.config)

    def set_mechanism(self, mechanism_id: str, enabled: bool) -> dict[str, Any]:
        snap = set_mechanism(self.config, mechanism_id, enabled)
        if mechanism_id == "experimental_physical_signal":
            from mechanistic_mind.physical_system.physical_signal import clear_fields, ensure_fields
            if bool(enabled):
                ensure_fields(self.world)
            else:
                clear_fields(self.world)
        # Keep the cognition store's config copy aligned with live toggles.
        if isinstance(self.cognition, dict):
            self.cognition["config"] = self.config.cognition.to_dict()
            eq = self.cognition.get("equivalence")
            if isinstance(eq, dict):
                eq["enabled"] = bool(getattr(self.config.cognition, "predictive_equivalence", False))
            rel = self.cognition.get("relevance")
            if isinstance(rel, dict):
                rel["enabled"] = bool(getattr(self.config.cognition, "predictive_relevance", False))
            temporal = self.cognition.get("temporal")
            if isinstance(temporal, dict):
                temporal["enabled"] = bool(getattr(self.config.cognition, "temporal_predictive_structure", False))
            tpb_meta = self.cognition.get("temporal_bridge")
            if isinstance(tpb_meta, dict):
                tpb_meta["enabled"] = bool(getattr(self.config.cognition, "temporal_prospection_bridge", False))
            conflict = self.cognition.get("conflict")
            if isinstance(conflict, dict):
                conflict["enabled"] = bool(getattr(self.config.cognition, "predictive_conflict", False))
            fsa_meta = self.cognition.get("future_action")
            if isinstance(fsa_meta, dict):
                fsa_meta["enabled"] = bool(getattr(self.config.cognition, "future_sensitive_action", False))
            per_st = self.cognition.get("prediction_revision")
            if isinstance(per_st, dict):
                per_st["enabled"] = bool(getattr(self.config.cognition, "prediction_error_revision", False))
            tpe_st = self.cognition.get("temporal_prediction_error")
            if isinstance(tpe_st, dict):
                tpe_st["enabled"] = bool(getattr(self.config.cognition, "temporal_prediction_error", False))
            pcp_meta = self.cognition.get("predicted_context_prospection")
            if isinstance(pcp_meta, dict):
                pcp_meta["enabled"] = bool(getattr(self.config.cognition, "predicted_context_prospection", False))
            map_meta = self.cognition.get("multistep_action_prospection")
            if isinstance(map_meta, dict):
                map_meta["enabled"] = bool(getattr(self.config.cognition, "multistep_action_prospection", False))
        return snap

    def set_motion_trace(self, *, enabled: bool, mode: str = "every_10") -> dict[str, Any]:
        self.motion_trace_enabled = bool(enabled)
        if mode in {"every_1", "every_10", "every_50", "on_move"}:
            self.motion_trace_mode = mode
        return {"enabled": self.motion_trace_enabled, "mode": self.motion_trace_mode}

    def _maybe_record_motion_receipt(
        self,
        *,
        decision_tick: int,
        selected: str,
        action_source: str | None,
        impulse: tuple[float, float],
        body_before_action: dict[str, Any],
        body_after_impulse: dict[str, Any],
        body_after: dict[str, Any],
        internal_before: dict[str, Any],
        internal_after: dict[str, Any],
        local_world: dict[str, Any],
        mech_decomp: dict[str, Any],
    ) -> None:
        mode = self.motion_trace_mode if self.motion_trace_enabled else "every_10"
        dx = abs(float(body_after["x"]) - float(body_before_action["x"]))
        dy = abs(float(body_after["y"]) - float(body_before_action["y"]))
        moved = dx > 1e-9 or dy > 1e-9
        if mode == "every_1":
            sample = True
        elif mode == "every_50":
            sample = decision_tick % 50 == 0
        elif mode == "on_move":
            sample = moved
        else:
            sample = decision_tick % 10 == 0
        receipt = build_motion_causal_receipt(
            tick=decision_tick,
            body_before_action=body_before_action,
            body_after_impulse=body_after_impulse,
            body_after=body_after,
            internal_before=internal_before,
            internal_after=internal_after,
            selected_action=selected,
            action_source=action_source,
            impulse=impulse,
            local_world_after_planet=local_world,
            mech_decomp=mech_decomp,
            observation_after=self.last_agent_observation,
        )
        self.last_motion_receipt = receipt
        if bool(getattr(self.config.morphology_mechanics, "enabled", False)) and isinstance(self.last_morphology_meta, dict) and self.last_morphology_meta.get("enabled"):
            causes = list((receipt.get("why_did_it_move_summary") or {}).get("causes") or [])
            if "MORPHOLOGY_SITE_FORCES" not in causes:
                nf = self.last_morphology_meta.get("net_force") or [0, 0]
                if abs(float(nf[0])) + abs(float(nf[1])) > 1e-12:
                    causes.append("MORPHOLOGY_SITE_FORCES")
            summary = receipt.setdefault("why_did_it_move_summary", {})
            summary["causes"] = causes
            summary["morphology"] = {
                "enabled": True,
                "net_force": self.last_morphology_meta.get("net_force"),
                "B_site_spread": self.last_morphology_meta.get("B_site_spread"),
                "n_sites": self.last_morphology_meta.get("n_sites"),
            }
            if "MORPHOLOGY_SITE_FORCES" in causes:
                summary["INTERNAL_TO_EXTERNAL_TRANSFER"] = "EXPERIMENTAL_MORPHOLOGY_SUSCEPTIBILITY"

        if bool(getattr(self.config.body_orientation, "enabled", False)) and isinstance(self.last_orientation_meta, dict) and self.last_orientation_meta.get("enabled"):
            summary = receipt.setdefault("why_did_it_move_summary", {})
            om = self.last_orientation_meta
            summary["orientation"] = {
                "theta": om.get("theta"),
                "omega": om.get("omega"),
                "tau": om.get("tau"),
                "alpha": om.get("alpha"),
                "net_force": om.get("net_force"),
            }
            causes = list(summary.get("causes") or [])
            if abs(float(om.get("tau") or 0.0)) > 1e-12 and "ORIENTATION_TORQUE" not in causes:
                causes.append("ORIENTATION_TORQUE")
            summary["causes"] = causes
            receipt["why_did_it_rotate"] = {
                "status": "AVAILABLE",
                "tau": om.get("tau"),
                "omega": om.get("omega"),
                "theta": om.get("theta"),
                "alpha": om.get("alpha"),
                "net_force": om.get("net_force"),
                "exposures": (om.get("exposures") or [])[:5],
                "chain": [
                    "LOCAL_ENVIRONMENT",
                    "SITE_EXPOSURE",
                    "LOCAL_SUSCEPTIBILITY",
                    "LOCAL_FORCE",
                    "NET_TORQUE",
                    "ANGULAR_RESPONSE",
                    "THETA_CHANGE",
                ],
            }
            dm = om.get("deformation") or {}
            receipt["why_did_its_shape_change"] = {
                "status": "AVAILABLE" if dm.get("enabled") else "DISABLED",
                "local_material_state": dm.get("B_site_norms"),
                "deformation_state": dm.get("deformation"),
                "rest_geometry": dm.get("rest_geometry"),
                "actual_geometry": dm.get("actual_geometry"),
                "geometry_coupling_enabled": dm.get("geometry_coupling_enabled"),
                "shape_change_source": dm.get("shape_change_source"),
                "where_did_the_work_come_from": dm.get("where_did_the_work_come_from"),
                "work_ledger": self.last_work_ledger,
                "resource_ledger": self.last_resource_ledger,
                "complementary_ledger": self.last_complementary_ledger,
                "chain": [
                    "ENVIRONMENT_TRANSFERABLE_RESOURCE",
                    "BODY_LOCAL_R_SITE",
                    "COMPLEMENTARY_A_B",
                    "CONVERSION",
                    "MECHANICAL_WORK_RESERVOIR",
                    "DEFORMATION_STATE",
                    "BODY_LOCAL_GEOMETRY",
                ],
            }

        summary = receipt.setdefault("why_did_it_move_summary", {})
        causes = list(summary.get("causes") or [])
        ml = self.last_motor_work_ledger or {}
        drive = ml.get("motor_drive_requested") or [0.0, 0.0]
        realized = ml.get("motor_delta_v_realized") or [0.0, 0.0]
        if abs(float(drive[0])) + abs(float(drive[1])) > 1e-12:
            if "ENDOGENOUS_MOTOR_REQUESTED" not in causes:
                causes.append("ENDOGENOUS_MOTOR_REQUESTED")
            if abs(float(realized[0])) + abs(float(realized[1])) > 1e-12 and "ENDOGENOUS_MOTOR_REALIZED" not in causes:
                causes.append("ENDOGENOUS_MOTOR_REALIZED")
        if ml.get("work_limited") or ml.get("work_unavailable"):
            summary["MOTOR_DRIVE_PRESENT"] = True
            summary["PHYSICAL_REALIZATION_LIMITED_BY_AVAILABLE_WORK"] = True
        summary["causes"] = causes
        summary["endogenous_motor_requested"] = drive
        summary["endogenous_motor_realized"] = realized
        summary["motor_work"] = {
            "requested": ml.get("motor_work_requested"),
            "realized": ml.get("motor_work_realized"),
            "unrealized": ml.get("motor_work_unrealized"),
            "receipt_id": ml.get("receipt_id"),
            "where_did_the_motor_work_come_from": ml.get("where_did_the_motor_work_come_from"),
        }
        aw = self.last_action_work_ledger or {}
        summary["selected_discrete_action"] = selected
        summary["requested_action_dv"] = aw.get("action_dv_requested")
        summary["realized_action_dv"] = aw.get("action_dv_realized")
        summary["requested_action_impulse"] = aw.get("action_impulse_requested")
        summary["realized_action_impulse"] = aw.get("action_impulse_realized")
        summary["action_work"] = {
            "requested": aw.get("action_work_requested"),
            "allocated": aw.get("action_work_allocated"),
            "realized": aw.get("action_work_realized"),
            "unrealized": aw.get("action_work_unrealized"),
            "negative_work": aw.get("action_negative_work_realized"),
            "limit_fraction": aw.get("action_work_limit_fraction"),
            "receipt_id": aw.get("receipt_id"),
        }
        if aw.get("work_limited") or aw.get("work_unavailable"):
            summary["WHY_WAS_ACTION_NOT_FULLY_REALIZED"] = (
                "REQUESTED_POSITIVE_WORK_EXCEEDED_ALLOCATED_MECHANICAL_WORK"
            )
        receipt["action_physical_realization"] = deepcopy(aw)
        receipt["work_allocation"] = deepcopy(self.last_work_allocation)
        receipt["why_did_it_move_summary"] = summary

        if sample:
            self.motion_trace.add(receipt)

    def set_action_trace(self, *, enabled: bool, mode: str = "every_10") -> dict[str, Any]:
        self.action_trace_enabled = bool(enabled)
        if mode in {"every_1", "every_10", "every_50", "on_change", "on_long_wait"}:
            self.action_trace_mode = mode
        return {"enabled": self.action_trace_enabled, "mode": self.action_trace_mode}


    def _maybe_record_decision_receipt(
        self,
        *,
        decision_tick: int,
        result: Any,
        body_before: dict[str, Any],
        body_after: dict[str, Any],
    ) -> None:
        selected = result.selected_action
        if selected == "WAIT":
            self._wait_run += 1
        else:
            self._wait_run = 0
        # Default sampling is every_10 even when ACTION TRACE is OFF (bounded).
        mode = self.action_trace_mode if self.action_trace_enabled else "every_10"
        if not self.action_trace_enabled:
            mode = "every_10"
        prev = self._prev_traced_action
        if mode == "every_1":
            sample = True
        elif mode == "every_50":
            sample = decision_tick % 50 == 0
        elif mode == "on_change":
            sample = selected != prev
        elif mode == "on_long_wait":
            sample = self._wait_run in {20, 50, 100, 200} or (self._wait_run > 0 and self._wait_run % 100 == 0)
        else:
            sample = decision_tick % 10 == 0
        self._prev_traced_action = selected

        receipt = build_action_decision_receipt(
            tick=decision_tick,
            observation=result.observation,
            selected=selected,
            selection_source=result.selection_source,
            actions=list(result.actions or []),
            predictions=list(result.predictions or []),
            continuations=list((result.composition or {}).get("continuations") or []),
            composition=result.composition or {},
            last_apply=self.cognition.get("last_apply"),
            body_before=body_before,
            body_after=body_after,
            selection_rule=result.selection_rule or "",
            last_selection=self.cognition.get("last_selection"),
        )
        # attach counterfactual probe (observer diagnostic)
        receipt["counterfactual"] = counterfactual_candidate_probe(
            store=self.cognition["prospection"],
            compression=self.cognition["compression"],
            observation=result.observation,
            actions=list(result.actions or []),
        )
        self.cognition["last_decision_receipt"] = receipt
        if sample:
            self.decision_trace.add_receipt(receipt)

    def diagnostic_bundle(self) -> dict[str, Any]:
        from .diagnostics import analyze_wait_loop, human_summary, occupancy_grid, wrap_aware_segments
        receipts, positions = self.decision_trace.as_lists()
        loop = analyze_wait_loop(receipts, positions)
        w = int(self.config.planet.width)
        h = int(self.config.planet.height)
        return {
            "action_trace": {"enabled": self.action_trace_enabled, "mode": self.action_trace_mode},
            "receipt_count": len(receipts),
            "last_decision_receipt": self.cognition.get("last_decision_receipt"),
            "last_motion_receipt": self.last_motion_receipt,
            "motion_trace": {"enabled": self.motion_trace_enabled, "mode": self.motion_trace_mode, "count": len(self.motion_trace.receipts)},
            "wait_loop": loop,
            "summary": human_summary(loop, receipts),
            "occupancy": {
                "width": w,
                "height": h,
                "grid": occupancy_grid(positions, width=w, height=h) if positions else [],
                "segments": wrap_aware_segments(positions, width=w, height=h) if positions else [],
                "positions_tail": positions[-200:],
            },
            "counterfactual_latest": (self.cognition.get("last_decision_receipt") or {}).get("counterfactual"),
        }


    def model_identity(self) -> dict[str, Any]:
        from mechanistic_mind.model.tiktaalik import model_metadata

        return model_metadata(self.config, seed=self.seed, tick=self.tick)

    def snapshot(self) -> dict[str, Any]:
        """Complete causal state needed to continue this deterministic history."""
        return {
            "schema": "mm.physical_system.snapshot.v2",
            "tick": self.tick,
            "seed": self.seed,
            "model": self.model_identity(),
            "config": {
                "planet": self.config.planet.to_dict(),
                "body": self.config.body.to_dict(),
                "internal": self.config.internal.to_dict(),
                "endogenous_motor": self.config.endogenous_motor.to_dict(),
                "runtime_version": getattr(self.config, "runtime_version", RUNTIME_VERSION),
                "morphology_mechanics": self.config.morphology_mechanics.to_dict(),
                "body_orientation": self.config.body_orientation.to_dict(),
                "body_deformation": self.config.body_deformation.to_dict(),
                "deformation_work": self.config.deformation_work.to_dict(),
                "environmental_resource": self.config.environmental_resource.to_dict(),
                "complementary_resources": self.config.complementary_resources.to_dict(),
                "endogenous_motor_work": self.config.endogenous_motor_work.to_dict(),
                "discrete_action_work": self.config.discrete_action_work.to_dict(),
                "physical_signal": self.config.physical_signal.to_dict(),
                "cognition": self.config.cognition.to_dict(),
            },
            "world": serialize_planet_state(self.world, self.config.planet),
            "body": {
                **self.body.snapshot(),
                "deformation": None if getattr(self.body, "deformation", None) is None else np.asarray(self.body.deformation, dtype=float).tolist(),
            },
            "internal": self.internal.snapshot(),
            "cognition": deepcopy(self.cognition),
            "last_agent_observation": deepcopy(self.last_agent_observation),
            "last_selected_action": self.last_selected_action,
            "internal_c_prev": None if self._internal_c_prev is None else np.asarray(self._internal_c_prev, dtype=float).tolist(),
        }

    @classmethod
    def restore(cls, payload: dict[str, Any]) -> "PhysicalSystemRuntime":
        configs = payload["config"]
        cog_cfg = CognitionConfig.from_dict(configs.get("cognition"))
        config = PhysicalSystemConfig(
            planet=PlanetConfig.from_dict(configs["planet"]),
            body=_config_from_dict(PhysicalBodyConfig, configs["body"]),
            internal=_config_from_dict(InternalMediumConfig, configs["internal"]),
            endogenous_motor=EndogenousMotorCouplingConfig.from_dict(configs.get("endogenous_motor")),
            morphology_mechanics=MorphologyMechanicsConfig.from_dict(configs.get("morphology_mechanics")),
            body_orientation=BodyOrientationConfig.from_dict(configs.get("body_orientation")),
            body_deformation=BodyDeformationConfig.from_dict(configs.get("body_deformation")),
            deformation_work=DeformationWorkConfig.from_dict(configs.get("deformation_work")),
            environmental_resource=EnvironmentalResourceConfig.from_dict(configs.get("environmental_resource")),
            complementary_resources=ComplementaryResourcesConfig.from_dict(configs.get("complementary_resources")),
            endogenous_motor_work=EndogenousMotorWorkConfig.from_dict(configs.get("endogenous_motor_work")),
            discrete_action_work=DiscreteActionWorkConfig.from_dict(configs.get("discrete_action_work")),
            physical_signal=PhysicalSignalConfig.from_dict(configs.get("physical_signal")),
            cognition=cog_cfg,
        )
        runtime = cls(seed=int(payload["seed"]), config=config)
        runtime.world, runtime.config.planet = restore_planet_state(payload["world"])
        b = payload["body"]
        runtime.body = PhysicalBodyState(
            tick=int(b["tick"]), x=float(b["x"]), y=float(b["y"]),
            vx=float(b["vx"]), vy=float(b["vy"]), T=float(b["T"]),
            B=np.asarray(b["B"], dtype=np.float64),
            B_core=np.asarray(b["B_core"], dtype=np.float64), mech=float(b["mech"]),
            motor_ux=float(b.get("motor_ux", 0.0)), motor_uy=float(b.get("motor_uy", 0.0)),
            B_site=None if b.get("B_site") is None else np.asarray(b["B_site"], dtype=np.float64),
            theta=float(b.get("theta", 0.0)), omega=float(b.get("omega", 0.0)),
            matter_in=float(b["matter_in"]), matter_out=float(b["matter_out"]),
            heat_from_world=float(b["heat_from_world"]), heat_to_world=float(b["heat_to_world"]),
            react_consumed=float(b["react_consumed"]), core_exchange_cum=float(b["core_exchange_cum"]),
            mechanical_work_reservoir=float(b.get("mechanical_work_reservoir", 0.0)),
            deformation_env_force=(
                None if b.get("deformation_env_force") is None
                else np.asarray(b["deformation_env_force"], dtype=np.float64)
            ),
            R_site=None if b.get("R_site") is None else np.asarray(b["R_site"], dtype=np.float64),
            R_A_site=None if b.get("R_A_site") is None else np.asarray(b["R_A_site"], dtype=np.float64),
            R_B_site=None if b.get("R_B_site") is None else np.asarray(b["R_B_site"], dtype=np.float64),
        )
        runtime.body.deformation = (
            None if b.get("deformation") is None
            else np.asarray(b["deformation"], dtype=np.float64)
        )
        internal = payload["internal"]
        runtime.internal = InternalMediumState(
            tick=int(internal["tick"]), c=np.asarray(internal["c"], dtype=np.float64)
        )
        runtime.tick = int(payload["tick"])
        runtime.last_internal_flux = None
        if "cognition" in payload:
            runtime.cognition = deepcopy(payload["cognition"])
            eq = runtime.cognition.get("equivalence")
            if isinstance(eq, dict):
                pe.clear_derived_caches(eq)
        else:
            runtime.cognition = empty_cognitive_state(runtime.config.cognition)
        runtime.last_agent_observation = deepcopy(payload.get("last_agent_observation"))
        runtime.last_selected_action = payload.get("last_selected_action")
        runtime._internal_c_prev = (
            None
            if payload.get("internal_c_prev") is None
            else np.asarray(payload["internal_c_prev"], dtype=np.float64)
        )
        if not (runtime.tick == runtime.world.tick == runtime.body.tick == runtime.internal.tick):
            raise ValueError("snapshot contains incoherent physical ticks")
        return runtime
