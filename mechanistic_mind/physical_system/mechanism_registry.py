"""Registry of ablatable mechanisms for MM 1.0 Tiktaalik."""
from __future__ import annotations
from typing import Any

from mechanistic_mind.model.identity import RUNTIME_VERSION, promotion_class
PRE_INTEGRATION_BASELINE = "PRE-INTEGRATION_BASELINE"


MECHANISM_DEFS: list[dict[str, Any]] = [
    {
        "id": "discrete_action_bridge",
        "config_path": None,
        "label": "DISCRETE ACTION BRIDGE",
        "description": "Maps WAIT/MOVE strings to requested world-frame physical intervention.",
        "validation": "Implemented bridge; TAKE/RELEASE/CONTACT/EMIT remain unavailable.",
        "provenance": "baseline_action_bridge",
        "default_integrated": True,
        "ablatable": False,
    },
    {
        "id": "shared_work_allocation",
        "config_path": None,
        "label": "SHARED WORK ALLOCATION",
        "description": "Proportional positive-work allocation across action, motor and deformation.",
        "validation": "Validated as part of motor/action work accounting.",
        "provenance": "mm_discrete_action_work_experiment",
        "default_integrated": True,
        "ablatable": False,
    },
    {
        "id": "environmental_site_mechanics",
        "config_path": None,
        "label": "ENVIRONMENTAL SITE MECHANICS",
        "description": "Actual local environment sampling, force composition and torque path.",
        "validation": "Validated morphology/orientation mechanics.",
        "provenance": "validated_orientation_experiment",
        "default_integrated": True,
        "ablatable": False,
    },
    {
        "id": "predictive_compression",
        "config_path": "cognition.predictive_compression",
        "label": "PREDICTIVE COMPRESSION",
        "description": "Retains bounded observation-action predictive structures.",
        "validation": "Existing cognition mechanism; enabled state does not imply a physical bridge.",
        "provenance": "baseline_cognition",
        "default_integrated": True,
    },
    {
        "id": "multiscale_prediction",
        "config_path": "cognition.multiscale_prediction",
        "label": "MULTISCALE PREDICTION",
        "description": "Organizes retained predictive structures across scales.",
        "validation": "Existing cognition mechanism.",
        "provenance": "baseline_cognition",
        "default_integrated": True,
    },
    {
        "id": "prospective_composition",
        "config_path": "cognition.prospective_composition",
        "label": "PROSPECTIVE COMPOSITION",
        "description": "Composes supported future action continuations.",
        "validation": "Existing cognition mechanism.",
        "provenance": "baseline_cognition",
        "default_integrated": True,
    },
    {
        "id": "bounded_memory",
        "config_path": "cognition.bounded_memory",
        "label": "BOUNDED MEMORY",
        "description": "Bounds retained cognitive stores.",
        "validation": "Existing cognition mechanism.",
        "provenance": "baseline_cognition",
        "default_integrated": True,
    },
    {
        "id": "retrieval",
        "config_path": "cognition.retrieval",
        "label": "RETRIEVAL",
        "description": "Queries retained predictive structures for the current observation.",
        "validation": "Existing cognition mechanism.",
        "provenance": "baseline_cognition",
        "default_integrated": True,
    },
    {
        "id": "body_deformation",
        "config_path": "body_deformation",
        "label": "BODY DEFORMATION",
        "description": "Local B_site drives bounded radial body-local site displacement; geometry then changes ordinary mechanics.",
        "validation": "Validated: B_site→deformation→geometry→exposure/force/torque with matched ablations (mm_body_deformation).",
        "provenance": "mm_body_deformation_experiment",
        "default_integrated": True,
    },
    {
        "id": "deformation_work",
        "config_path": "deformation_work",
        "label": "DEFORMATION WORK TRANSFER",
        "description": "Finite abstract mechanical work reservoir pays F·dx for internally powered deformation; env can still deform a depleted body.",
        "validation": "Validated: finite mechanical_work_reservoir pays F·dx; depletion, ablation, isolated-momentum, and passive-env gates (mm_deformation_work).",
        "provenance": "mm_deformation_work_experiment",
        "default_integrated": True,
    },
    {
        "id": "environmental_resource_transfer",
        "config_path": "environmental_resource.transfer_enabled",
        "label": "ENVIRONMENTAL RESOURCE TRANSFER",
        "description": "Site-local transferable_resource from planet.R into R_site; source cell depletes.",
        "validation": "Validated: site-local planet.R → R_site with source depletion and transfer ablation (mm_environmental_work_resource).",
        "provenance": "mm_environmental_work_resource_experiment",
        "default_integrated": True,
    },
    {
        "id": "resource_to_work_conversion",
        "config_path": "environmental_resource.conversion_enabled",
        "label": "RESOURCE TO WORK CONVERSION",
        "description": "Finite-rate conversion of body-local transferable_resource into mechanical_work_reservoir.",
        "validation": "Validated: R_site conversion credits mechanical_work_reservoir; conversion ablation removes replenishment (mm_environmental_work_resource).",
        "provenance": "mm_environmental_work_resource_experiment",
        "default_integrated": True,
    },
    {
        "id": "resource_A_transfer",
        "config_path": "complementary_resources.transfer_A_enabled",
        "label": "RESOURCE A TRANSFER",
        "description": "Site-local transfer of retained stock planet.R_A into R_A_site.",
        "validation": "Validated: independent A transfer with source depletion (mm_complementary_resources).",
        "provenance": "mm_complementary_resources_experiment",
        "default_integrated": True,
    },
    {
        "id": "resource_B_transfer",
        "config_path": "complementary_resources.transfer_B_enabled",
        "label": "RESOURCE B TRANSFER",
        "description": "Site-local transfer of volatile stock planet.R_B into R_B_site.",
        "validation": "Validated: independent B transfer with source depletion (mm_complementary_resources).",
        "provenance": "mm_complementary_resources_experiment",
        "default_integrated": True,
    },
    {
        "id": "complementary_resource_conversion",
        "config_path": "complementary_resources.conversion_enabled",
        "label": "COMPLEMENTARY RESOURCE CONVERSION",
        "description": "Joint A+B conversion into mechanical_work_reservoir; limited by the scarcer required stock.",
        "validation": "Validated: conversion requires both A and B; excess of one cannot replace zero of the other (mm_complementary_resources).",
        "provenance": "mm_complementary_resources_experiment",
        "default_integrated": True,
    },
    {
        "id": "distributed_morphology",
        "config_path": "morphology_mechanics",
        "label": "DISTRIBUTED MORPHOLOGY",
        "description": "Local B_site modulates mechanical susceptibility to local environment.",
        "validation": "Validated: same env + different B_site → different force/path (mm_body_morphology_mechanics).",
        "provenance": "validated_morphology_experiment",
        "default_integrated": True,
    },
    {
        "id": "body_orientation",
        "config_path": "body_orientation",
        "label": "BODY ORIENTATION",
        "description": "Physical theta/omega; site forces produce torque and rotate footprint sampling.",
        "validation": "Validated: env asymmetry → torque → theta → exposure (mm_body_orientation).",
        "provenance": "validated_orientation_experiment",
        "default_integrated": True,
    },
    {
        "id": "endogenous_motor_coupling",
        "config_path": "endogenous_motor",
        "label": "ENDOGENOUS MOTOR",
        "description": "Continuous motor_u from ||Δc|| × local physical asymmetry (not discrete MOVE).",
        "validation": "Validated: zero-flow + WAIT still yields endogenous motion (mm_endogenous_motor_coupling).",
        "provenance": "validated_endogenous_motor_experiment",
        "default_integrated": True,
    },
    {
        "id": "endogenous_motor_work_accounting",
        "config_path": "endogenous_motor_work",
        "label": "ENDOGENOUS MOTOR WORK ACCOUNTING",
        "description": "Realized motor Δv/force is limited by mechanical_work_reservoir; drive generation is unchanged.",
        "validation": "Validated: drive persists when depleted; positive ΔKE debits shared reservoir; abundant work matches historical motor (mm_motor_work_accounting).",
        "provenance": "mm_motor_work_accounting_experiment",
        "default_integrated": True,
    },
    {
        "id": "discrete_action_work_accounting",
        "config_path": "discrete_action_work",
        "label": "DISCRETE ACTION WORK ACCOUNTING",
        "description": "Selected MOVE remains cognitive; its center-applied world-frame Δv is physically limited by the shared work reservoir.",
        "validation": "Validated: selected-vs-realized separation, KE-based debit, three-way allocation, cross-term ledger, and historical ablation (mm_discrete_action_work).",
        "provenance": "mm_discrete_action_work_experiment",
        "default_integrated": True,
    },
    {
        "id": "prospective_scenario_competition",
        "config_path": "cognition.prospective_selection",
        "label": "PROSPECTIVE SCENARIO COMPETITION",
        "description": "Competes supported prospective continuations when multiple exist. Recommended: let the organism explore for a while before enabling PSC so sensorimotor and predictive history can form first. PSC can be enabled during a running simulation without resetting the organism (~1000 ticks is a reasonable experimental starting point).",
        "validation": "Prior prospective competition branch.",
        "provenance": "validated_prospective_competition",
        "default_integrated": True,
    },
    {
        "id": "instrumental_observation",
        "config_path": "cognition.instrumental_observation",
        "label": "INSTRUMENTAL OBSERVATION",
        "description": "Learned instrumental store (prediction match/use).",
        "validation": "Existing cognition switch.",
        "provenance": "baseline_cognition",
        "default_integrated": True,
    },
    {
        "id": "unknown_action_physical_probe",
        "config_path": "cognition.unknown_action_physical_probe",
        "label": "UNKNOWN ACTION PHYSICAL PROBE",
        "description": "Experimental detection of available first-actions lacking MATCH/support. Does not select. Default OFF. DESIGN_BOUNDARY on arbitration.",
        "validation": "Detection-only; selection unchanged (mm_unknown_action_probe).",
        "provenance": "mm_unknown_action_probe_experiment",
        "default_integrated": False,
    },
    {
        "id": "spatiotemporal_climate_ecology",
        "config_path": "planet.climate_ecology.enabled",
        "label": "SPATIOTEMPORAL CLIMATE ECOLOGY",
        "description": (
            "Climate dynamics gate only: latitudinal T_eq, seasonal cycle, climate insolation. "
            "Does NOT gate R_A/R_B environmental ecology (see resource_ecology_A / resource_ecology_B). "
            "Flipping OFF ablates climate temporal dynamics while leaving resource fields intact."
        ),
        "validation": "World physics only; cognition unchanged (mm_seasonal_resource_ecology).",
        "provenance": "mm_seasonal_resource_ecology_experiment",
        "default_integrated": False,
        "toggle_semantics": "ABLATION_OF_CLIMATE_DYNAMICS_ONLY",
    },
    {
        "id": "resource_ecology_A",
        "config_path": "planet.climate_ecology.resource_ecology_A_enabled",
        "label": "RESOURCE ECOLOGY A",
        "description": (
            "Environmental production, persistence and regeneration of R_A. "
            "Independent of climate dynamics and of R_B ecology. "
            "Does not erase agent-body R_A_site inventory."
        ),
        "validation": "World field ecology only; no semantic food labels.",
        "provenance": "beta2_resource_ecology_authority",
        "default_integrated": True,
        "toggle_semantics": "ENVIRONMENTAL_R_A_ECOLOGY",
    },
    {
        "id": "resource_ecology_B",
        "config_path": "planet.climate_ecology.resource_ecology_B_enabled",
        "label": "RESOURCE ECOLOGY B",
        "description": (
            "Environmental production, persistence and regeneration of R_B. "
            "Independent of climate dynamics and of R_A ecology. "
            "Does not erase agent-body R_B_site inventory."
        ),
        "validation": "World field ecology only; no semantic food labels.",
        "provenance": "beta2_resource_ecology_authority",
        "default_integrated": True,
        "toggle_semantics": "ENVIRONMENTAL_R_B_ECOLOGY",
    },
    {
        "id": "physical_near_field_vision",
        "config_path": "near_field_exteroception.perception_enabled",
        "label": "PHYSICAL NEAR-FIELD VISION",
        "description": (
            "Bounded Moore R=1 × body-oriented FOV 120° × surface_response → anonymous exo_0/1/2. "
            "OFF removes visual contribution from cognition only; does not erase surface, "
            "terrain, illumination field, physics, or history. "
            "ACTIVE_SENSOR_ORIENTATION = NOT_AVAILABLE (no LOOK/TURN)."
        ),
        "validation": "Validated: PHYSICAL_PERCEPTION_01 / DIRECTIONAL_NEAR_FIELD_VISION_01 (P1–P22).",
        "provenance": "physical_perception_01",
        "default_integrated": True,
        "toggle_semantics": "VISION_SENSOR_CONTRIBUTION",
    },
    {
        "id": "illumination_cycle",
        "config_path": "near_field_exteroception.illumination_enabled",
        "label": "ILLUMINATION CYCLE",
        "description": (
            "Physical illumination dynamics (period=240). Modulates visual signal strength only. "
            "Does not generate work, alter terrain, or inject DAY/NIGHT semantics into cognition. "
            "LIVE OFF freezes intensity at current physical value."
        ),
        "validation": "Validated: ILLUMINATION_CYCLE_01 (period 240 selected).",
        "provenance": "illumination_cycle_01",
        "default_integrated": True,
        "toggle_semantics": "ILLUMINATION_DYNAMICS",
    },
    {
        "id": "physical_body_optical_response",
        "config_path": "near_field_exteroception.body_optical_enabled",
        "label": "PHYSICAL BODY OPTICAL RESPONSE",
        "description": (
            "Physical bodies contribute to local optical structure available to near-field vision. "
            "Anonymous material optical_response composed with environmental surface_response. "
            "Not agent recognition, not social vision, not experimenter detection."
        ),
        "validation": "Validated composition with PHYSICAL_PERCEPTION_01 filtering (FOV/illumination).",
        "provenance": "visible_physical_bodies_beta2",
        "default_integrated": True,
        "toggle_semantics": "BODY_OPTICAL_CONTRIBUTION",
    },
    {
        "id": "experimental_physical_signal",
        "config_path": "physical_signal.mode",
        "label": "EXPERIMENTAL PHYSICAL SIGNAL",
        "description": "Shared-world FIELD_A/FIELD_B amplitude with decay and neighbor spread. Fresh-experiment default ON. Not EMIT-in-available_actions. Not communication.",
        "validation": "Experimental TwoAgentRuntime signal bridge (mm_two_agent_physical_signals). Unpromoted.",
        "provenance": "mm_two_agent_physical_signals_experiment",
        "default_integrated": True,
    },
    {
        "id": "oscillatory_signaling",
        "config_path": "oscillatory_signaling.mode",
        "label": "PHYSICAL OSCILLATORY SIGNALING",
        "description": (
            "Banded oscillatory emission/reception with L/R head-linked receptors. "
            "Anonymous osc_l_*/osc_r_*. No language, source identity, or source direction. "
            "Alongside legacy FIELD_A/B. Fresh-experiment default ON."
        ),
        "validation": "Experimental physical medium; EXACT_MATCH legacy when OFF.",
        "provenance": "physical_oscillatory_signaling",
        "default_integrated": True,
        "toggle_semantics": "OSCILLATORY_PHYSICAL_SIGNAL",
    },
    {
        "id": "articulated_head",
        "config_path": "articulated_head.mode",
        "label": "ARTICULATED HEAD / ACTIVE SENSOR ORIENTATION",
        "description": (
            "Bounded neck DOF + NECK_LEFT/RIGHT/HOLD motors. Vision FOV uses head_world_heading. "
            "No LOOK_AT / TRACK / ATTENTION. Fresh-experiment default ON."
        ),
        "validation": "Experimental motor DOF; EXACT_MATCH legacy when OFF.",
        "provenance": "active_sensor_orientation_push",
        "default_integrated": True,
    },
    {
        "id": "physical_push",
        "config_path": "physical_push.mode",
        "label": "PHYSICAL PUSH / FORCE EXERTION",
        "description": (
            "Generic PUSH action arms contact-mediated force along body heading. "
            "No PUSH_AGENT, no target identity, no action-at-a-distance. Fresh-experiment default ON."
        ),
        "validation": "Experimental contact force; same path for agents/Undercover.",
        "provenance": "active_sensor_orientation_push",
        "default_integrated": True,
    },
    {
        "id": "physical_vestibular_sensing",
        "config_path": "vestibular.mode",
        "label": "PHYSICAL VESTIBULAR SENSING",
        "description": (
            "Anonymous vest_0/vest_1 from body angular velocity/acceleration. "
            "No compass, no absolute heading to cognition. Ablation removes sensor only."
        ),
        "validation": "Experimental body-local rotational transducer.",
        "provenance": "vestibular_proprioception",
        "default_integrated": True,
    },
    {
        "id": "neck_proprioception",
        "config_path": "neck_proprioception.mode",
        "label": "NECK PROPRIOCEPTION",
        "description": (
            "Anonymous prop_neck_0/prop_neck_1 from head-relative angle/ω. "
            "Requires articulated head. Does not expose head_world_heading to cognition."
        ),
        "validation": "Experimental neck-state sensing; independent of vestibular.",
        "provenance": "vestibular_proprioception",
        "default_integrated": True,
    },
    {
        "id": "predictive_equivalence",
        "config_path": "cognition.predictive_equivalence",
        "label": "PREDICTIVE EQUIVALENCE",
        "description": "Experimental: group continuous observations by experienced continuations. Complements exact SHA. Default OFF. Unpromoted.",
        "validation": "Experimental (mm_predictive_equivalence). Does not replace raw observation identity.",
        "provenance": "mm_predictive_equivalence_experiment",
        "default_integrated": False,
    },
    {
        "id": "predictive_relevance",
        "config_path": "cognition.predictive_relevance",
        "label": "PREDICTIVE RELEVANCE",
        "description": "Experimental: relation-specific relevant keys for partial retrieval. Default OFF. Not a global mask. Not attention.",
        "validation": "Experimental (mm_predictive_relevance). Complements predictive_equivalence.",
        "provenance": "mm_predictive_relevance_experiment",
        "default_integrated": False,
    },
    {
        "id": "temporal_predictive_structure",
        "config_path": "cognition.temporal_predictive_structure",
        "label": "TEMPORAL PREDICTIVE STRUCTURE",
        "description": "Experimental: trajectory-conditioned prediction from ordinary recent fragments (successive differences). Default OFF. No CLOCK. Unpromoted.",
        "validation": "Experimental (mm_temporal_predictive_structure). Complements snapshot SHA/PE.",
        "provenance": "mm_temporal_predictive_structure_experiment",
        "default_integrated": False,
    },
    {
        "id": "temporal_prospection_bridge",
        "config_path": "cognition.temporal_prospection_bridge",
        "label": "TEMPORAL PROSPECTION BRIDGE",
        "description": "Experimental adapter: TPS MATCH → 4.23 first-step roots. Default OFF. Does not predict or select.",
        "validation": "Experimental (mm_temporal_prospection_bridge). Transport only.",
        "provenance": "mm_temporal_prospection_bridge_experiment",
        "default_integrated": False,
    },
    {
        "id": "predictive_conflict",
        "config_path": "cognition.predictive_conflict",
        "label": "PREDICTIVE CONFLICT",
        "description": "Experimental: content-based identity for incompatible same-action futures. Default OFF. Does not select or invent confidence.",
        "validation": "Experimental (mm_predictive_conflict). Scenario identity, not action arbitration.",
        "provenance": "mm_predictive_conflict_experiment",
        "default_integrated": False,
    },
    {
        "id": "future_sensitive_action",
        "config_path": "cognition.future_sensitive_action",
        "label": "FUTURE-SENSITIVE ACTION",
        "description": "Experimental adapter: content-identified scenarios enter existing competition. Default OFF. Not a new policy, reward, or utility.",
        "validation": "Experimental (mm_future_sensitive_action). Preserves discarded prospective identity.",
        "provenance": "mm_future_sensitive_action_experiment",
        "default_integrated": False,
    },
    {
        "id": "prediction_error_revision",
        "config_path": "cognition.prediction_error_revision",
        "label": "PREDICTION ERROR REVISION",
        "description": "Experimental: mismatch vs issued prediction can invalidate current MATCH. Default OFF. Does not rewrite history, punish, or select.",
        "validation": "Experimental (mm_prediction_error_revision). Predictive validity, not reward.",
        "provenance": "mm_prediction_error_revision_experiment",
        "default_integrated": False,
    },
    {
        "id": "temporal_prediction_error",
        "config_path": "cognition.temporal_prediction_error",
        "label": "TEMPORAL PREDICTION ERROR",
        "description": "Experimental: bounded prediction residuals enter existing TPS. Default OFF. Not a drift detector, reward, or policy.",
        "validation": "Experimental (mm_gradual_prediction_drift). Residual trajectory, not DRIFT.",
        "provenance": "mm_gradual_prediction_drift_experiment",
        "default_integrated": False,
    },
    {
        "id": "predicted_context_prospection",
        "config_path": "cognition.predicted_context_prospection",
        "label": "PREDICTED CONTEXT PROSPECTION",
        "description": "Experimental: predicted future context → read-only action-consequence lookup. Default OFF. Does not write experience, invent actions, or select.",
        "validation": "Experimental (mm_predicted_context_prospection). Anticipatory prospection, not a policy.",
        "provenance": "mm_predicted_context_prospection_experiment",
        "default_integrated": False,
    },
    {
        "id": "multistep_action_prospection",
        "config_path": "cognition.multistep_action_prospection",
        "label": "MULTI-STEP ACTION PROSPECTION",
        "description": "Experimental: present action → future context → future action. Default OFF. Not a plan, macro, or policy.",
        "validation": "Experimental (mm_multistep_action_prospection). Composition of learned edges, not planning.",
        "provenance": "mm_multistep_action_prospection_experiment",
        "default_integrated": False,
    },
    {
        "id": "sensorimotor_consequence_model",
        "config_path": "cognition.sensorimotor_consequence_model",
        "label": "SENSORIMOTOR CONSEQUENCE MODEL",
        "description": "Action-conditioned learning of accessible sensory consequences of own motors (O,M)→ΔO. No reward, seeking, or target.",
        "validation": "Demonstrated: ACTION_CONDITIONED_SENSORY_PREDICTION.",
        "provenance": "mm_sensorimotor_consequence",
        "default_integrated": True,
        "ablatable": True,
    },
    {
        "id": "historical_sensorimotor_selection_bridge",
        "config_path": "cognition.historical_sensorimotor_selection_bridge",
        "label": "HISTORICAL SENSORIMOTOR SELECTION",
        "description": "Predicted sensory consequences of candidate actions are queried against the organism's accumulated history; continuation evidence can participate in prospective scenario competition. No reward, goal, or preference scalar.",
        "validation": "Demonstrated: HISTORICAL_SENSORIMOTOR_SELECTION (WITHHELD causal control).",
        "provenance": "mm_o_prime_history_bridge",
        "default_integrated": True,
        "ablatable": True,
    },

    {
        "id": "contextual_predictive_organization",
        "config_path": "cognition.contextual_predictive_organization",
        "label": "CONTEXTUAL PREDICTIVE ORGANIZATION",
        "description": "Reusable higher-order predictive organization from repeated relational experience (4.26). Not place/map/familiar.",
        "validation": "ASSERTED: CONTEXTUAL_PREDICTIVE_ORGANIZATION; HISTORY_DEPENDENT_CONTEXTUAL_COMPRESSION.",
        "provenance": "update426_contextual_predictive_organization",
        "default_integrated": False,
        "ablatable": True,
    },
    {
        "id": "context_grounded_prospection",
        "config_path": "cognition.context_grounded_prospection",
        "label": "CONTEXT-GROUNDED PROSPECTION",
        "description": "Prospective composition over learned higher-order contextual structures (4.27). Not route/destination/plan.",
        "validation": "ASSERTED: CONTEXT_GROUNDED_PROSPECTION.",
        "provenance": "update427_context_grounded_prospection",
        "default_integrated": False,
        "ablatable": True,
    },
    {
        "id": "persistent_prospective_control",
        "config_path": "cognition.persistent_prospective_control",
        "label": "PERSISTENT PROSPECTIVE CONTROL",
        "description": "Selected prospective continuation may remain causally relevant across actions while predictive support holds (4.28). No INTENTION variable.",
        "validation": "ASSERTED: PERSISTENT_PROSPECTIVE_CONTROL; intention-like control SUPPORTED (Observer label only).",
        "provenance": "update428_persistent_prospective_control",
        "default_integrated": False,
        "ablatable": True,
    },
    {
        "id": "cognition",
        "config_path": "cognition.cognition_enabled",
        "label": "COGNITION",
        "description": "Master cognition enable (selection + learning).",
        "validation": "Existing.",
        "provenance": "baseline_cognition",
        "default_integrated": True,
    },
]


def mechanism_snapshot(config) -> dict[str, Any]:
    cog = config.cognition
    morph = config.morphology_mechanics
    orient = config.body_orientation
    endo = config.endogenous_motor
    deform = config.body_deformation
    dwork = config.deformation_work
    eres = config.environmental_resource
    cres = config.complementary_resources
    mwork = getattr(config, "endogenous_motor_work", None)
    awork = getattr(config, "discrete_action_work", None)
    psc_on = str(getattr(cog, "prospective_selection", "")).upper() == "SCENARIO_COMPETITION"
    states = {
        "discrete_action_bridge": True,
        "shared_work_allocation": bool(getattr(mwork, "enabled", False) or getattr(awork, "enabled", False)),
        "environmental_site_mechanics": bool(morph.enabled or orient.enabled),
        "distributed_morphology": bool(morph.enabled),
        "body_orientation": bool(orient.enabled),
        "endogenous_motor_coupling": bool(endo.enabled),
        "endogenous_motor_work_accounting": bool(getattr(mwork, "enabled", False)),
        "discrete_action_work_accounting": bool(getattr(awork, "enabled", False)),
        "body_deformation": bool(deform.enabled),
        "deformation_work": bool(dwork.enabled),
        "environmental_resource_transfer": bool(eres.enabled) and bool(eres.transfer_enabled),
        "resource_to_work_conversion": bool(eres.enabled) and bool(eres.conversion_enabled),
        "resource_A_transfer": bool(cres.enabled) and bool(cres.transfer_A_enabled),
        "resource_B_transfer": bool(cres.enabled) and bool(cres.transfer_B_enabled),
        "complementary_resource_conversion": bool(cres.enabled) and bool(cres.conversion_enabled),
        "prospective_scenario_competition": bool(cog.cognition_enabled) and psc_on,
        "sensorimotor_consequence_model": bool(getattr(cog, "sensorimotor_consequence_model", False)),
        "historical_sensorimotor_selection_bridge": bool(getattr(cog, "historical_sensorimotor_selection_bridge", False)),
        "instrumental_observation": bool(getattr(cog, "instrumental_observation", False)),
        "unknown_action_physical_probe": bool(getattr(cog, "unknown_action_physical_probe", False)),
        "spatiotemporal_climate_ecology": bool(
            getattr(getattr(config.planet, "climate_ecology", None), "enabled", False)
        ),
        "resource_ecology_A": bool(
            getattr(
                getattr(config.planet, "climate_ecology", None),
                "resource_ecology_A_enabled",
                True,
            )
        ) if getattr(config.planet, "climate_ecology", None) is not None else False,
        "resource_ecology_B": bool(
            getattr(
                getattr(config.planet, "climate_ecology", None),
                "resource_ecology_B_enabled",
                True,
            )
        ) if getattr(config.planet, "climate_ecology", None) is not None else False,
        "physical_near_field_vision": bool(
            getattr(getattr(config, "near_field_exteroception", None), "vision_contributes", False)
        ),
        "illumination_cycle": bool(
            getattr(getattr(config, "near_field_exteroception", None), "enabled", False)
            and getattr(getattr(config, "near_field_exteroception", None), "illumination_enabled", True)
        ),
        "physical_body_optical_response": bool(
            getattr(getattr(config, "near_field_exteroception", None), "enabled", False)
            and getattr(getattr(config, "near_field_exteroception", None), "body_optical_enabled", True)
        ),
        "experimental_physical_signal": str(getattr(getattr(config, "physical_signal", None), "mode", "OFF")).upper() == "EXPERIMENTAL",
        "oscillatory_signaling": bool(getattr(getattr(config, "oscillatory_signaling", None), "enabled", False)),
        "articulated_head": bool(getattr(getattr(config, "articulated_head", None), "enabled", False)),
        "physical_push": bool(getattr(getattr(config, "physical_push", None), "enabled", False)),
        "physical_vestibular_sensing": bool(getattr(getattr(config, "vestibular", None), "enabled", False)),
        "neck_proprioception": bool(getattr(getattr(config, "neck_proprioception", None), "enabled", False)),
        "predictive_equivalence": bool(getattr(cog, "predictive_equivalence", False)),
        "predictive_relevance": bool(getattr(cog, "predictive_relevance", False)),
        "temporal_predictive_structure": bool(getattr(cog, "temporal_predictive_structure", False)),
        "temporal_prospection_bridge": bool(getattr(cog, "temporal_prospection_bridge", False)),
        "predictive_conflict": bool(getattr(cog, "predictive_conflict", False)),
        "future_sensitive_action": bool(getattr(cog, "future_sensitive_action", False)),
        "prediction_error_revision": bool(getattr(cog, "prediction_error_revision", False)),
        "temporal_prediction_error": bool(getattr(cog, "temporal_prediction_error", False)),
        "predicted_context_prospection": bool(getattr(cog, "predicted_context_prospection", False)),
        "multistep_action_prospection": bool(getattr(cog, "multistep_action_prospection", False)),
        "contextual_predictive_organization": bool(getattr(cog, "contextual_predictive_organization", False)),
        "context_grounded_prospection": bool(getattr(cog, "context_grounded_prospection", False)),
        "persistent_prospective_control": bool(getattr(cog, "persistent_prospective_control", False)),
        "cognition": bool(cog.cognition_enabled),
        "predictive_compression": bool(getattr(cog, "predictive_compression", True)),
        "multiscale_prediction": bool(getattr(cog, "multiscale_prediction", True)) if hasattr(cog, "multiscale_prediction") else None,
        "prospective_composition": bool(getattr(cog, "prospective_composition", True)) if hasattr(cog, "prospective_composition") else None,
        "bounded_memory": bool(getattr(cog, "bounded_memory", True)),
        "retrieval": bool(getattr(cog, "retrieval", True)),
    }
    categories = {
        "predictive_compression": "COGNITION", "multiscale_prediction": "COGNITION",
        "prospective_composition": "COGNITION", "bounded_memory": "COGNITION",
        "retrieval": "COGNITION", "prospective_scenario_competition": "COGNITION",
        "sensorimotor_consequence_model": "COGNITION",
        "historical_sensorimotor_selection_bridge": "COGNITION",
        "instrumental_observation": "COGNITION", "unknown_action_physical_probe": "COGNITION",
        "cognition": "COGNITION",
        "spatiotemporal_climate_ecology": "WORLD",
        "resource_ecology_A": "RESOURCES",
        "resource_ecology_B": "RESOURCES",
        "physical_near_field_vision": "SENSORS",
        "illumination_cycle": "SENSORS",
        "physical_body_optical_response": "SENSORS",
        "experimental_physical_signal": "WORLD",
        "oscillatory_signaling": "WORLD",
        "predictive_equivalence": "COGNITION",
        "predictive_relevance": "COGNITION",
        "temporal_predictive_structure": "COGNITION",
        "temporal_prospection_bridge": "COGNITION",
        "predictive_conflict": "COGNITION",
        "future_sensitive_action": "COGNITION",
        "prediction_error_revision": "COGNITION",
        "temporal_prediction_error": "COGNITION",
        "predicted_context_prospection": "COGNITION",
        "multistep_action_prospection": "COGNITION",
        "contextual_predictive_organization": "COGNITION",
        "context_grounded_prospection": "COGNITION",
        "persistent_prospective_control": "COGNITION",
        "body_deformation": "BODY", "distributed_morphology": "BODY",
        "body_orientation": "BODY", "endogenous_motor_coupling": "MOTOR",
        "deformation_work": "WORK", "endogenous_motor_work_accounting": "WORK",
        "discrete_action_work_accounting": "WORK",
        "environmental_resource_transfer": "RESOURCES",
        "resource_to_work_conversion": "RESOURCES", "resource_A_transfer": "RESOURCES",
        "resource_B_transfer": "RESOURCES", "complementary_resource_conversion": "RESOURCES",
    }
    dependencies = {
        "prospective_scenario_competition": ["prospective_composition"],
        "historical_sensorimotor_selection_bridge": ["sensorimotor_consequence_model", "prospective_composition"],
        "context_grounded_prospection": ["contextual_predictive_organization", "prospective_composition"],
        "persistent_prospective_control": ["context_grounded_prospection", "prospective_scenario_competition"],
        "multiscale_prediction": ["bounded_memory"],
        "retrieval": ["bounded_memory"],
        "body_deformation": ["body_orientation"],
        "deformation_work": ["body_deformation"],
        "endogenous_motor_work_accounting": ["endogenous_motor_coupling", "deformation_work"],
        "discrete_action_work_accounting": ["deformation_work"],
        "resource_to_work_conversion": ["environmental_resource_transfer"],
        "complementary_resource_conversion": ["resource_A_transfer", "resource_B_transfer"],
        "physical_body_optical_response": ["physical_near_field_vision"],
    }
    reset_recommended = {"body_deformation", "deformation_work", "distributed_morphology", "body_orientation"}
    items = []
    for d in MECHANISM_DEFS:
        mid = d["id"]
        pclass = promotion_class(mid)
        items.append({
            **d,
            "enabled": states.get(mid),
            "state": "ON" if states.get(mid) else "OFF",
            "category": categories.get(mid, "PHYSICAL"),
            "promotion_class": pclass,
            "scientific_status": "VALIDATED" if "Validated:" in str(d.get("validation")) else "IMPLEMENTED",
            "dependencies": dependencies.get(mid, []),
            "toggle_policy": (
                "READ_ONLY" if not d.get("ablatable", True)
                else "RESET_RECOMMENDED" if mid in reset_recommended
                else "LIVE_TOGGLE_SAFE"
            ),
            "historical_compatibility": "missing newer config key preserves historical behavior",
            "live_state_available": True,
            "receipts_available": mid not in {"bounded_memory", "retrieval"},
            "events_available": mid not in {"bounded_memory", "retrieval", "predictive_compression"},
            "ablatable": bool(d.get("ablatable", True)),
        })
    from mechanistic_mind.model.lines import identity_for_config
    from mechanistic_mind.physical_system.locomotion_profile import (
        GENTLE_TERRAIN_LOCOMOTION,
        gentle_mechanism_catalog_item,
        profile_is_active,
    )

    if str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA":
        on = bool(profile_is_active(config))
        states[GENTLE_TERRAIN_LOCOMOTION] = on
        extra = gentle_mechanism_catalog_item(enabled=on)
        extra.update({
            "scientific_status": "IMPLEMENTED",
            "promotion_class": "EXPERIMENTAL",
        })
        items.append(extra)
        from mechanistic_mind.physical_system.resource_objects import (
            PHYSICAL_RESOURCE_OBJECTS,
            objects_is_active,
            resource_objects_catalog_item,
        )
        obj_on = bool(objects_is_active(config))
        states[PHYSICAL_RESOURCE_OBJECTS] = obj_on
        obj_item = resource_objects_catalog_item(enabled=obj_on)
        obj_item.update({
            "scientific_status": "IMPLEMENTED",
            "promotion_class": "EXPERIMENTAL",
        })
        items.append(obj_item)
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_MATERIAL_VISION,
            PRESET_ACANTHOSTEGA_MATERIALS,
            PRESET_ACANTHOSTEGA_SINGLE_GRASP,
            PRESET_ACANTHOSTEGA_BILATERAL_GRASP,
            PRESET_ACANTHOSTEGA_BRING_TOGETHER,
            PRESET_ACANTHOSTEGA_COMPOSITION_MERGE,
            PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES,
            PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION,
            PRESET_ACANTHOSTEGA_SURFACE_TRACTION,
            PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE,
            PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION,
            PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
            PRESET_ACANTHOSTEGA_WORLD_MATERIAL,
            PRESET_ACANTHOSTEGA_MULTI_CONTENT,
            PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
            PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
    PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
    PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_BETA4,
            normalize_preset_name,
        )
        from mechanistic_mind.physical_system.resource_objects import (
            PHYSICAL_RESOURCE_OBJECT_VISION,
            object_vision_is_active,
            resource_object_vision_catalog_item,
        )
        preset_n = normalize_preset_name(getattr(config, "public_preset", None))
        vis_on = bool(object_vision_is_active(config))
        if vis_on or obj_on or preset_n in {
            PRESET_ACANTHOSTEGA_MATERIALS,
            PRESET_ACANTHOSTEGA_MATERIAL_VISION,
            PRESET_ACANTHOSTEGA_SINGLE_GRASP,
            PRESET_ACANTHOSTEGA_BILATERAL_GRASP,
            PRESET_ACANTHOSTEGA_BRING_TOGETHER,
            PRESET_ACANTHOSTEGA_COMPOSITION_MERGE,
            PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES,
            PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION,
            PRESET_ACANTHOSTEGA_SURFACE_TRACTION,
            PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE,
            PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION,
            PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
            PRESET_ACANTHOSTEGA_WORLD_MATERIAL,
            PRESET_ACANTHOSTEGA_MULTI_CONTENT,
            PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
            PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
            PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }:
            states[PHYSICAL_RESOURCE_OBJECT_VISION] = vis_on
            vis_item = resource_object_vision_catalog_item(enabled=vis_on)
            vis_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
            })
            items.append(vis_item)
        from mechanistic_mind.physical_system.physical_manipulator import (
            BILATERAL_BRING_TOGETHER,
            BILATERAL_GRASP_RELEASE,
            BILATERAL_PHYSICAL_MANIPULATORS,
            PHYSICAL_GRASP_RELEASE,
            SINGLE_PHYSICAL_MANIPULATOR,
            bilateral_bring_together_catalog_item,
            bilateral_grasp_release_catalog_item,
            bilateral_grasp_release_is_active,
            bilateral_manipulator_catalog_item,
            bilateral_manipulator_is_active,
            bring_together_is_active,
            grasp_release_catalog_item,
            grasp_release_is_active,
            manipulator_catalog_item,
            manipulator_is_active,
        )
        man_on = bool(manipulator_is_active(config))
        gr_on = bool(grasp_release_is_active(config))
        if man_on or gr_on or preset_n == PRESET_ACANTHOSTEGA_SINGLE_GRASP:
            states[SINGLE_PHYSICAL_MANIPULATOR] = man_on
            man_item = manipulator_catalog_item(enabled=man_on)
            man_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
            })
            items.append(man_item)
            states[PHYSICAL_GRASP_RELEASE] = gr_on
            gr_item = grasp_release_catalog_item(enabled=gr_on)
            gr_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
            })
            items.append(gr_item)
        bi_on = bool(bilateral_manipulator_is_active(config))
        bigr_on = bool(bilateral_grasp_release_is_active(config))
        if bi_on or bigr_on or preset_n in {PRESET_ACANTHOSTEGA_BILATERAL_GRASP, PRESET_ACANTHOSTEGA_BRING_TOGETHER, PRESET_ACANTHOSTEGA_COMPOSITION_MERGE, PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES, PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION, PRESET_ACANTHOSTEGA_SURFACE_TRACTION, PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE, PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION, PRESET_ACANTHOSTEGA_SURFACE_OPTICAL, PRESET_ACANTHOSTEGA_WORLD_MATERIAL}:
            states[BILATERAL_PHYSICAL_MANIPULATORS] = bi_on
            bi_item = bilateral_manipulator_catalog_item(enabled=bi_on)
            bi_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
            })
            items.append(bi_item)
            states[BILATERAL_GRASP_RELEASE] = bigr_on
            bigr_item = bilateral_grasp_release_catalog_item(enabled=bigr_on)
            bigr_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
            })
            items.append(bigr_item)
        pair_on = bool(bring_together_is_active(config))
        if pair_on or preset_n in {PRESET_ACANTHOSTEGA_BRING_TOGETHER, PRESET_ACANTHOSTEGA_COMPOSITION_MERGE, PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES, PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION, PRESET_ACANTHOSTEGA_SURFACE_TRACTION, PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE, PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION, PRESET_ACANTHOSTEGA_SURFACE_OPTICAL, PRESET_ACANTHOSTEGA_WORLD_MATERIAL}:
            states[BILATERAL_BRING_TOGETHER] = pair_on
            pair_item = bilateral_bring_together_catalog_item(enabled=pair_on)
            pair_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
            })
            items.append(pair_item)
        from mechanistic_mind.physical_system.material_composition import (
            MATERIAL_COMPOSITION_MERGE, material_composition_catalog_item,
            material_composition_merge_is_active,
        )
        merge_on = bool(material_composition_merge_is_active(config))
        if merge_on or preset_n in {PRESET_ACANTHOSTEGA_COMPOSITION_MERGE, PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES, PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION, PRESET_ACANTHOSTEGA_SURFACE_TRACTION, PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE, PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION, PRESET_ACANTHOSTEGA_SURFACE_OPTICAL, PRESET_ACANTHOSTEGA_WORLD_MATERIAL}:
            states[MATERIAL_COMPOSITION_MERGE] = merge_on
            merge_item = material_composition_catalog_item(enabled=merge_on)
            merge_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
            })
            items.append(merge_item)
        from mechanistic_mind.physical_system.passive_material_properties import (
            PASSIVE_MATERIAL_PROPERTIES,
            passive_material_properties_catalog_item,
            passive_material_properties_is_active,
        )
        props_on = bool(passive_material_properties_is_active(config))
        if props_on or preset_n in {PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES, PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION, PRESET_ACANTHOSTEGA_SURFACE_TRACTION, PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE, PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION, PRESET_ACANTHOSTEGA_SURFACE_OPTICAL, PRESET_ACANTHOSTEGA_WORLD_MATERIAL}:
            states[PASSIVE_MATERIAL_PROPERTIES] = props_on
            props_item = passive_material_properties_catalog_item(enabled=props_on)
            props_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
            })
            items.append(props_item)
        from mechanistic_mind.physical_system.physical_optical_material_profile import (
            CAPABILITY as PHYSICAL_OPTICAL_MATERIAL_PROFILE,
            physical_optical_material_profile_catalog_item,
            physical_optical_material_profile_is_active,
        )
        o1_on = bool(physical_optical_material_profile_is_active(config))
        if o1_on or preset_n in {PRESET_ACANTHOSTEGA_BETA4, "ACANTHOSTEGA_BETA4_0"}:
            states[PHYSICAL_OPTICAL_MATERIAL_PROFILE] = o1_on
            o1_item = physical_optical_material_profile_catalog_item(enabled=o1_on)
            o1_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
                "behaviorally_dormant_without_light_consumer": True,
            })
            items.append(o1_item)
        from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
            CAPABILITY as EXPOSED_SURFACE_OPTICAL_INTERACTION_AUTHORITY,
            exposed_surface_optical_interaction_authority_catalog_item,
            exposed_surface_optical_interaction_authority_is_active,
        )
        o2_on = bool(exposed_surface_optical_interaction_authority_is_active(config))
        if o2_on or preset_n in {PRESET_ACANTHOSTEGA_BETA4, "ACANTHOSTEGA_BETA4_0"}:
            states[EXPOSED_SURFACE_OPTICAL_INTERACTION_AUTHORITY] = o2_on
            o2_item = exposed_surface_optical_interaction_authority_catalog_item(enabled=o2_on)
            o2_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
                "behaviorally_dormant_without_light_consumer": True,
            })
            items.append(o2_item)
        from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
            CAPABILITY as ABSTRACT_SPECTRAL_LIGHT_SOURCE_AND_DIRECT_TRANSPORT,
            abstract_spectral_light_source_and_direct_transport_catalog_item,
            abstract_spectral_light_source_and_direct_transport_is_active,
        )
        o3_on = bool(abstract_spectral_light_source_and_direct_transport_is_active(config))
        if o3_on or preset_n in {PRESET_ACANTHOSTEGA_BETA4, "ACANTHOSTEGA_BETA4_0"}:
            states[ABSTRACT_SPECTRAL_LIGHT_SOURCE_AND_DIRECT_TRANSPORT] = o3_on
            o3_item = abstract_spectral_light_source_and_direct_transport_catalog_item(enabled=o3_on)
            o3_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
                "behaviorally_dormant_for_organisms": True,
                "organism_reception": False,
            })
            items.append(o3_item)
        from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
            CAPABILITY as OBJECT_BODY_HELD_OPTICAL_SURFACES,
            object_body_held_optical_surfaces_catalog_item,
            object_body_held_optical_surfaces_is_active,
        )
        o3a_on = bool(object_body_held_optical_surfaces_is_active(config))
        if o3a_on or preset_n in {PRESET_ACANTHOSTEGA_BETA4, "ACANTHOSTEGA_BETA4_0"}:
            states[OBJECT_BODY_HELD_OPTICAL_SURFACES] = o3a_on
            o3a_item = object_body_held_optical_surfaces_catalog_item(enabled=o3a_on)
            o3a_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
                "behaviorally_dormant_for_organisms": True,
                "organism_reception": False,
            })
            items.append(o3a_item)
        from mechanistic_mind.physical_system.organism_physical_optical_reception import (
            CAPABILITY as ORGANISM_PHYSICAL_OPTICAL_RECEPTION,
            organism_physical_optical_reception_catalog_item,
            organism_physical_optical_reception_is_active,
        )
        o4_on = bool(organism_physical_optical_reception_is_active(config))
        if o4_on or preset_n in {PRESET_ACANTHOSTEGA_BETA4, "ACANTHOSTEGA_BETA4_0"}:
            states[ORGANISM_PHYSICAL_OPTICAL_RECEPTION] = o4_on
            o4_item = organism_physical_optical_reception_catalog_item(enabled=o4_on)
            o4_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
                "changes_visual_numerics": True,
            })
            items.append(o4_item)
        from mechanistic_mind.physical_system.explicit_surface_deposition import (
            EXPLICIT_SURFACE_DEPOSITION,
            explicit_surface_deposition_catalog_item,
            explicit_surface_deposition_is_active,
        )
        deposit_on = bool(explicit_surface_deposition_is_active(config))
        if deposit_on or preset_n in {PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION, PRESET_ACANTHOSTEGA_SURFACE_TRACTION, PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE, PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION, PRESET_ACANTHOSTEGA_SURFACE_OPTICAL, PRESET_ACANTHOSTEGA_WORLD_MATERIAL}:
            states[EXPLICIT_SURFACE_DEPOSITION] = deposit_on
            deposit_item = explicit_surface_deposition_catalog_item(enabled=deposit_on)
            deposit_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
            })
            items.append(deposit_item)
        from mechanistic_mind.physical_system.surface_affinity_traction import (
            SURFACE_AFFINITY_TRACTION,
            surface_affinity_traction_catalog_item,
            surface_affinity_traction_is_active,
        )
        traction_on = bool(surface_affinity_traction_is_active(config))
        if traction_on or preset_n in {
            PRESET_ACANTHOSTEGA_SURFACE_TRACTION,
            PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE,
            PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION,
            PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
            PRESET_ACANTHOSTEGA_WORLD_MATERIAL,
            PRESET_ACANTHOSTEGA_MULTI_CONTENT,
            PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
            PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
            PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }:
            states[SURFACE_AFFINITY_TRACTION] = traction_on
            traction_item = surface_affinity_traction_catalog_item(enabled=traction_on)
            traction_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
            })
            items.append(traction_item)
        from mechanistic_mind.physical_system.surface_traction_experience import (
            SURFACE_TRACTION_EXPERIENCE_BRIDGE,
            surface_traction_experience_catalog_item,
            surface_traction_experience_is_active,
        )
        experience_on = bool(surface_traction_experience_is_active(config))
        if experience_on or preset_n in {
            PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE,
            PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION,
            PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
            PRESET_ACANTHOSTEGA_WORLD_MATERIAL,
            PRESET_ACANTHOSTEGA_MULTI_CONTENT,
            PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
            PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
            PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }:
            states[SURFACE_TRACTION_EXPERIENCE_BRIDGE] = experience_on
            experience_item = surface_traction_experience_catalog_item(enabled=experience_on)
            experience_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
            })
            items.append(experience_item)
        from mechanistic_mind.physical_system.surface_traction_prediction import (
            MECHANISM_ID as SURFACE_TRACTION_PREDICTION_ADAPTATION,
            surface_traction_prediction_catalog_item,
            surface_traction_prediction_is_active,
        )
        prediction_on = bool(surface_traction_prediction_is_active(config))
        if prediction_on or preset_n in {
            PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION,
            PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
            PRESET_ACANTHOSTEGA_WORLD_MATERIAL,
            PRESET_ACANTHOSTEGA_MULTI_CONTENT,
            PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
            PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
            PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }:
            states[SURFACE_TRACTION_PREDICTION_ADAPTATION] = prediction_on
            prediction_item = surface_traction_prediction_catalog_item(enabled=prediction_on)
            prediction_item.update({
                "scientific_status": "IMPLEMENTED",
                "promotion_class": "EXPERIMENTAL",
            })
            items.append(prediction_item)
        from mechanistic_mind.physical_system.physical_surface_optical_coating import (
            MECHANISM_ID as PHYSICAL_SURFACE_OPTICAL_COATING,
            coating_catalog_item,
            physical_surface_optical_coating_is_active,
        )
        coating_on = bool(physical_surface_optical_coating_is_active(config))
        if coating_on or preset_n in {
            PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
            PRESET_ACANTHOSTEGA_WORLD_MATERIAL,
            PRESET_ACANTHOSTEGA_MULTI_CONTENT,
            PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
            PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
            PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }:
            states[PHYSICAL_SURFACE_OPTICAL_COATING] = coating_on
            coating_item = coating_catalog_item(enabled=coating_on)
            items.append(coating_item)
        from mechanistic_mind.physical_system.world_material_transaction import (
            MECHANISM_ID as WORLD_MATERIAL_TRANSACTIONS,
            world_material_transaction_catalog_item,
            world_material_transactions_is_active,
        )
        transactions_on = bool(world_material_transactions_is_active(config))
        if transactions_on or preset_n in {
            PRESET_ACANTHOSTEGA_WORLD_MATERIAL,
            PRESET_ACANTHOSTEGA_MULTI_CONTENT,
            PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
            PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
            PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }:
            states[WORLD_MATERIAL_TRANSACTIONS] = transactions_on
            items.append(world_material_transaction_catalog_item(enabled=transactions_on))
        from mechanistic_mind.physical_system.spatial_contents import (
            MECHANISM_ID as MULTI_CONTENT_SPATIAL_INDEX,
            multi_content_spatial_index_is_active,
            spatial_index_catalog_item,
        )
        index_on = bool(multi_content_spatial_index_is_active(config))
        if index_on or preset_n in {
            PRESET_ACANTHOSTEGA_MULTI_CONTENT,
            PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
            PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
            PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }:
            states[MULTI_CONTENT_SPATIAL_INDEX] = index_on
            items.append(spatial_index_catalog_item(enabled=index_on))
        from mechanistic_mind.physical_system.procedural_surface_columns import (
            MECHANISM_ID as PROCEDURAL_SURFACE_COLUMNS,
            procedural_surface_columns_catalog_item,
            procedural_surface_columns_is_active,
        )
        columns_on = bool(procedural_surface_columns_is_active(config))
        if columns_on or preset_n in {PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS, PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS}:
            states[PROCEDURAL_SURFACE_COLUMNS] = columns_on
            items.append(procedural_surface_columns_catalog_item(enabled=columns_on))
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            MECHANISM_ID as VOLUMETRIC_WORLD_MATERIAL_OCCUPANCY,
            volumetric_occupancy_catalog_item,
            volumetric_world_material_occupancy_is_active,
        )
        vw1_on = bool(volumetric_world_material_occupancy_is_active(config))
        if vw1_on or columns_on or preset_n in {PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS, PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS}:
            states[VOLUMETRIC_WORLD_MATERIAL_OCCUPANCY] = vw1_on
            items.append(volumetric_occupancy_catalog_item(enabled=vw1_on))
        from mechanistic_mind.physical_system.conservative_surface_column_transfer import (
            MECHANISM_ID as CONSERVATIVE_SURFACE_COLUMN_TRANSFER,
            conservative_surface_column_transfer_catalog_item,
            conservative_surface_column_transfer_is_active,
        )
        transfer_on = bool(conservative_surface_column_transfer_is_active(config))
        if transfer_on or preset_n in {PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS}:
            states[CONSERVATIVE_SURFACE_COLUMN_TRANSFER] = transfer_on
            items.append(conservative_surface_column_transfer_catalog_item(enabled=transfer_on))
        from mechanistic_mind.physical_system.conservative_surface_material_separation import (
            MECHANISM_ID as CONSERVATIVE_SURFACE_MATERIAL_SEPARATION,
            conservative_surface_material_separation_catalog_item,
            conservative_surface_material_separation_is_active,
        )
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION,
        )
        sep_on = bool(conservative_surface_material_separation_is_active(config))
        if sep_on or preset_n == PRESET_ACANTHOSTEGA_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION:
            states[CONSERVATIVE_SURFACE_MATERIAL_SEPARATION] = sep_on
            items.append(conservative_surface_material_separation_catalog_item(enabled=sep_on))
        from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
            MECHANISM_ID as EFFECTOR_TERRAIN_CONTACT_GEOMETRY,
            catalog_item as effector_terrain_contact_catalog_item,
            effector_terrain_contact_geometry_is_active,
        )
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_EFFECTOR_TERRAIN_CONTACT_GEOMETRY,
        )
        etc_on = bool(effector_terrain_contact_geometry_is_active(config))
        if etc_on or preset_n == PRESET_ACANTHOSTEGA_EFFECTOR_TERRAIN_CONTACT_GEOMETRY:
            states[EFFECTOR_TERRAIN_CONTACT_GEOMETRY] = etc_on
            items.append(effector_terrain_contact_catalog_item(enabled=etc_on))
        from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
            MECHANISM_ID as MANIPULATOR_RELATIVE_WORLD_ACTUATION,
            catalog_item as manipulator_relative_world_actuation_catalog_item,
            manipulator_relative_world_actuation_is_active,
        )
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_MANIPULATOR_RELATIVE_WORLD_ACTUATION,
        )
        mrwa_on = bool(manipulator_relative_world_actuation_is_active(config))
        if mrwa_on or preset_n == PRESET_ACANTHOSTEGA_MANIPULATOR_RELATIVE_WORLD_ACTUATION:
            states[MANIPULATOR_RELATIVE_WORLD_ACTUATION] = mrwa_on
            items.append(manipulator_relative_world_actuation_catalog_item(enabled=mrwa_on))
        from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
            MECHANISM_ID as EFFECTOR_BOUNDED_ACTUATOR_EFFORT,
            catalog_item as effector_bounded_actuator_effort_catalog_item,
            effector_bounded_actuator_effort_is_active,
        )
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_EFFECTOR_BOUNDED_ACTUATOR_EFFORT,
        )
        ebae_on = bool(effector_bounded_actuator_effort_is_active(config))
        if ebae_on or preset_n == PRESET_ACANTHOSTEGA_EFFECTOR_BOUNDED_ACTUATOR_EFFORT:
            states[EFFECTOR_BOUNDED_ACTUATOR_EFFORT] = ebae_on
            items.append(effector_bounded_actuator_effort_catalog_item(enabled=ebae_on))
        from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
            MECHANISM_ID as SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE,
            catalog_item as surface_exertion_terrain_material_resistance_catalog_item,
            surface_exertion_terrain_material_resistance_is_active,
        )
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE,
        )
        setmr_on = bool(surface_exertion_terrain_material_resistance_is_active(config))
        if (
            setmr_on
            or preset_n == PRESET_ACANTHOSTEGA_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE
        ):
            states[SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE] = setmr_on
            items.append(
                surface_exertion_terrain_material_resistance_catalog_item(enabled=setmr_on)
            )
        from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
            MECHANISM_ID as HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY,
            catalog_item as held_resource_object_terrain_contact_geometry_catalog_item,
            held_resource_object_terrain_contact_geometry_is_active,
        )
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY,
        )
        hotc_on = bool(held_resource_object_terrain_contact_geometry_is_active(config))
        if (
            hotc_on
            or preset_n == PRESET_ACANTHOSTEGA_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY
        ):
            states[HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY] = hotc_on
            items.append(
                held_resource_object_terrain_contact_geometry_catalog_item(enabled=hotc_on)
            )
        from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
            MECHANISM_ID as HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION,
            catalog_item as held_resource_object_terrain_mechanical_transmission_catalog_item,
            held_resource_object_terrain_mechanical_transmission_is_active,
        )
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION,
        )
        hotmt_on = bool(held_resource_object_terrain_mechanical_transmission_is_active(config))
        if (
            hotmt_on
            or preset_n == PRESET_ACANTHOSTEGA_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION
        ):
            states[HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION] = hotmt_on
            items.append(
                held_resource_object_terrain_mechanical_transmission_catalog_item(enabled=hotmt_on)
            )
        from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
            MECHANISM_ID as HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION,
            catalog_item as held_mediated_surface_exertion_integration_catalog_item,
            held_mediated_surface_exertion_integration_is_active,
        )
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION,
            PRESET_ACANTHOSTEGA_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT,
            PRESET_ACANTHOSTEGA_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR,
            PRESET_ACANTHOSTEGA_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION,
            PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT,
            PRESET_ACANTHOSTEGA_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS,
            PRESET_ACANTHOSTEGA_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION,
            PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION,
            PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT,
            PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE,
            PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION,
            PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION,
            PRESET_ACANTHOSTEGA_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION,
        )
        hmsi_on = bool(held_mediated_surface_exertion_integration_is_active(config))
        if (
            hmsi_on
            or preset_n == PRESET_ACANTHOSTEGA_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION
            or preset_n == PRESET_ACANTHOSTEGA_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
            or preset_n == PRESET_ACANTHOSTEGA_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
            or preset_n == PRESET_ACANTHOSTEGA_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
            or preset_n == PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
            or preset_n == PRESET_ACANTHOSTEGA_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
            or preset_n == PRESET_ACANTHOSTEGA_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
        ):
            states[HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION] = hmsi_on
            items.append(
                held_mediated_surface_exertion_integration_catalog_item(enabled=hmsi_on)
            )
        from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
            MECHANISM_ID as DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT,
            catalog_item as detached_terrain_material_initial_placement_catalog_item,
            detached_terrain_material_initial_placement_is_active,
        )
        dtip_on = bool(detached_terrain_material_initial_placement_is_active(config))
        if (
            dtip_on
            or preset_n == PRESET_ACANTHOSTEGA_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
            or preset_n == PRESET_ACANTHOSTEGA_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
            or preset_n == PRESET_ACANTHOSTEGA_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
            or preset_n == PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
            or preset_n == PRESET_ACANTHOSTEGA_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
            or preset_n == PRESET_ACANTHOSTEGA_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
        ):
            states[DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT] = dtip_on
            items.append(
                detached_terrain_material_initial_placement_catalog_item(enabled=dtip_on)
            )
        from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
            MECHANISM_ID as BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR,
            catalog_item as bnlt_move_breakaway_locomotion_repair_catalog_item,
            bnlt_move_breakaway_locomotion_repair_is_active,
        )
        bnlt_rep_on = bool(bnlt_move_breakaway_locomotion_repair_is_active(config))
        if (
            bnlt_rep_on
            or preset_n == PRESET_ACANTHOSTEGA_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
            or preset_n == PRESET_ACANTHOSTEGA_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
            or preset_n == PRESET_ACANTHOSTEGA_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
            or preset_n == PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
            or preset_n == PRESET_ACANTHOSTEGA_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        ):
            states[BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR] = bnlt_rep_on
            items.append(
                bnlt_move_breakaway_locomotion_repair_catalog_item(enabled=bnlt_rep_on)
            )
        from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
            MECHANISM_ID as ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION,
            catalog_item as active_locomotion_traction_vs_sliding_friction_catalog_item,
            active_locomotion_traction_vs_sliding_friction_is_active,
        )
        altvs_on = bool(active_locomotion_traction_vs_sliding_friction_is_active(config))
        if (
            altvs_on
            or preset_n == PRESET_ACANTHOSTEGA_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
            or preset_n == PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
            or preset_n == PRESET_ACANTHOSTEGA_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        ):
            states[ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION] = altvs_on
            items.append(
                active_locomotion_traction_vs_sliding_friction_catalog_item(enabled=altvs_on)
            )
        from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
            MECHANISM_ID as REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION,
            catalog_item as repeated_conservative_surface_column_separation_catalog_item,
            repeated_conservative_surface_column_separation_is_active,
        )
        rcss_on = bool(repeated_conservative_surface_column_separation_is_active(config))
        if (
            rcss_on
            or preset_n == PRESET_ACANTHOSTEGA_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
            or preset_n == PRESET_ACANTHOSTEGA_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
            or preset_n == PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
            or preset_n == PRESET_ACANTHOSTEGA_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        ):
            states[REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION] = rcss_on
            items.append(
                repeated_conservative_surface_column_separation_catalog_item(enabled=rcss_on)
            )
        from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
            MECHANISM_ID as EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT,
            catalog_item as event_driven_crowded_placement_retry_contract_catalog_item,
            event_driven_crowded_placement_retry_contract_is_active,
        )
        crowded_on = bool(event_driven_crowded_placement_retry_contract_is_active(config))
        if (
            crowded_on
            or preset_n == PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
            or preset_n == PRESET_ACANTHOSTEGA_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        ):
            states[EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT] = crowded_on
            items.append(
                event_driven_crowded_placement_retry_contract_catalog_item(enabled=crowded_on)
            )
        from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
            MECHANISM_ID as DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS,
            catalog_item as detached_material_amount_scaled_collision_radius_catalog_item,
            detached_material_amount_scaled_collision_radius_is_active,
        )
        size_geo_on = bool(detached_material_amount_scaled_collision_radius_is_active(config))
        if (
            size_geo_on
            or preset_n == PRESET_ACANTHOSTEGA_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
            or preset_n == PRESET_ACANTHOSTEGA_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        ):
            states[DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS] = size_geo_on
            items.append(
                detached_material_amount_scaled_collision_radius_catalog_item(enabled=size_geo_on)
            )
        from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
            MECHANISM_ID as HELD_COMBINE_RADIUS_RESIZE_TRANSACTION,
            catalog_item as held_combine_radius_resize_transaction_catalog_item,
            held_combine_radius_resize_transaction_is_active,
        )
        held_combine_on = bool(held_combine_radius_resize_transaction_is_active(config))
        if (
            held_combine_on
            or preset_n == PRESET_ACANTHOSTEGA_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        ):
            states[HELD_COMBINE_RADIUS_RESIZE_TRANSACTION] = held_combine_on
            items.append(
                held_combine_radius_resize_transaction_catalog_item(enabled=held_combine_on)
            )
        from mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction import (
            MECHANISM_ID as HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION,
            catalog_item as held_deposition_radius_shrink_transaction_catalog_item,
            held_deposition_radius_shrink_transaction_is_active,
        )
        held_deposition_on = bool(held_deposition_radius_shrink_transaction_is_active(config))
        if (
            held_deposition_on
            or preset_n == PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
            or preset_n == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        ):
            states[HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION] = held_deposition_on
            items.append(
                held_deposition_radius_shrink_transaction_catalog_item(enabled=held_deposition_on)
            )
        from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
            MECHANISM_ID as FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT,
            catalog_item as free_space_state_and_pe_authority_contract_catalog_item,
            free_space_state_and_pe_authority_contract_is_active,
        )
        free_space_on = bool(free_space_state_and_pe_authority_contract_is_active(config))
        if (
            free_space_on
            or preset_n == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        ):
            states[FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT] = free_space_on
            items.append(
                free_space_state_and_pe_authority_contract_catalog_item(enabled=free_space_on)
            )
        from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
            MECHANISM_ID as VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE,
            catalog_item as vertical_terrain_landing_contact_response_catalog_item,
            vertical_terrain_landing_contact_response_is_active,
        )
        landing_on = bool(vertical_terrain_landing_contact_response_is_active(config))
        if (
            landing_on
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        ):
            states[VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE] = landing_on
            items.append(
                vertical_terrain_landing_contact_response_catalog_item(enabled=landing_on)
            )
        from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
            MECHANISM_ID as VERTICAL_IMPACT_ACOUSTIC_EMISSION,
            catalog_item as vertical_impact_acoustic_emission_catalog_item,
            vertical_impact_acoustic_emission_is_active,
        )
        via_on = bool(vertical_impact_acoustic_emission_is_active(config))
        if (
            via_on
            or preset_n == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        ):
            states[VERTICAL_IMPACT_ACOUSTIC_EMISSION] = via_on
            items.append(
                vertical_impact_acoustic_emission_catalog_item(enabled=via_on)
            )
        from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
            MECHANISM_ID as RELEASE_EXCAVATION_SUPPORT_LOSS,
            catalog_item as release_excavation_support_loss_catalog_item,
            release_and_excavation_support_loss_integration_is_active,
        )
        resli_on = bool(release_and_excavation_support_loss_integration_is_active(config))
        if (
            resli_on
            or preset_n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        ):
            states[RELEASE_EXCAVATION_SUPPORT_LOSS] = resli_on
            items.append(
                release_excavation_support_loss_catalog_item(enabled=resli_on)
            )
        from mechanistic_mind.physical_system.local_physical_signal_transport import (
            MECHANISM_ID as LOCAL_PHYSICAL_SIGNAL_TRANSPORT,
            catalog_item as local_physical_signal_catalog_item,
            local_physical_signal_transport_is_active,
        )
        local_signal_on = bool(local_physical_signal_transport_is_active(config))
        if local_signal_on or preset_n in {PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS}:
            states[LOCAL_PHYSICAL_SIGNAL_TRANSPORT] = local_signal_on
            items.append(local_physical_signal_catalog_item(enabled=local_signal_on))
        from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
            MECHANISM_ID as PHYSICAL_CONTACT_ACOUSTIC_EMISSION,
            catalog_item as contact_acoustic_catalog_item,
            physical_contact_acoustic_emission_is_active,
        )
        contact_acoustic_on = bool(physical_contact_acoustic_emission_is_active(config))
        if contact_acoustic_on or preset_n in {PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS}:
            states[PHYSICAL_CONTACT_ACOUSTIC_EMISSION] = contact_acoustic_on
            items.append(contact_acoustic_catalog_item(enabled=contact_acoustic_on))
        from mechanistic_mind.physical_system.free_resource_object_kinematics import (
            MECHANISM_ID as FREE_RESOURCE_OBJECT_KINEMATICS,
            catalog_item as free_object_kinematics_catalog_item,
            free_resource_object_kinematics_is_active,
        )
        free_object_on = bool(free_resource_object_kinematics_is_active(config))
        if free_object_on or preset_n in {PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS}:
            states[FREE_RESOURCE_OBJECT_KINEMATICS] = free_object_on
            items.append(free_object_kinematics_catalog_item(enabled=free_object_on))
        from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
            MECHANISM_ID as PHYSICAL_BODY_RESOURCE_OBJECT_CONTACT,
            body_object_contact_is_active,
            catalog_item as boc_catalog_item,
        )
        boc_on = bool(body_object_contact_is_active(config))
        if boc_on or preset_n in {PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS}:
            states[PHYSICAL_BODY_RESOURCE_OBJECT_CONTACT] = True
            items.append(boc_catalog_item(enabled=True))
        from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
            MECHANISM_ID as BODY_RESOURCE_OBJECT_CONTACT_IMPULSE,
            body_object_impulse_is_active,
            catalog_item as boi_catalog_item,
        )
        boi_on = bool(body_object_impulse_is_active(config))
        if boi_on or preset_n in {
            PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
            PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        }:
            states[BODY_RESOURCE_OBJECT_CONTACT_IMPULSE] = True
            items.append(boi_catalog_item(enabled=True))
        from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
            MECHANISM_ID as BODY_RESOURCE_OBJECT_IMPACT_ACOUSTIC_EMISSION,
            body_object_impact_acoustics_is_active,
            catalog_item as oia_catalog_item,
        )
        oia_on = bool(body_object_impact_acoustics_is_active(config))
        if oia_on or preset_n in {
            PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        }:
            states[BODY_RESOURCE_OBJECT_IMPACT_ACOUSTIC_EMISSION] = oia_on
            items.append(oia_catalog_item(enabled=oia_on))

        from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
            MECHANISM_ID as PHYSICAL_RESOURCE_OBJECT_PAIR_CONTACT,
            resource_object_pair_contact_is_active,
            catalog_item as ooc_catalog_item,
        )
        ooc_on = bool(resource_object_pair_contact_is_active(config))
        if ooc_on or preset_n in {
            PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
            PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        }:
            states[PHYSICAL_RESOURCE_OBJECT_PAIR_CONTACT] = ooc_on
            items.append(ooc_catalog_item(enabled=ooc_on))
        from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
            MECHANISM_ID as RESOURCE_OBJECT_PAIR_CONTACT_IMPULSE,
            resource_object_pair_impulse_is_active,
            catalog_item as ooi_catalog_item,
        )
        ooi_on = bool(resource_object_pair_impulse_is_active(config))
        if ooi_on or preset_n in {
            PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        }:
            states[RESOURCE_OBJECT_PAIR_CONTACT_IMPULSE] = ooi_on
            items.append(ooi_catalog_item(enabled=ooi_on))
        from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
            MECHANISM_ID as RESOURCE_OBJECT_PAIR_IMPACT_ACOUSTIC_EMISSION,
            resource_object_pair_impact_acoustics_is_active,
            catalog_item as ooia_catalog_item,
        )
        ooia_on = bool(resource_object_pair_impact_acoustics_is_active(config))
        if ooia_on or preset_n in {PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS}:
            states[RESOURCE_OBJECT_PAIR_IMPACT_ACOUSTIC_EMISSION] = ooia_on
            items.append(ooia_catalog_item(enabled=ooia_on))

        from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
            MECHANISM_ID as HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT,
            held_foreign_body_contact_is_active,
            catalog_item as hfc_catalog_item,
        )
        hfc_on = bool(held_foreign_body_contact_is_active(config))
        if hfc_on or preset_n == PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT:
            states[HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT] = hfc_on
            items.append(hfc_catalog_item(enabled=hfc_on))

        from mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation import (
            MECHANISM_ID as HELD_RESOURCE_OBJECT_TRANSLATIONAL_IMPULSE_MEDIATION,
            held_translational_impulse_is_active,
            catalog_item as hti_catalog_item,
        )
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE,
        )
        hti_on = bool(held_translational_impulse_is_active(config))
        if hti_on or preset_n == PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE:
            states[HELD_RESOURCE_OBJECT_TRANSLATIONAL_IMPULSE_MEDIATION] = hti_on
            items.append(hti_catalog_item(enabled=hti_on))

        from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
            MECHANISM_ID as EFFECTOR_WORK_HELD_LOAD,
            effector_work_held_load_is_active,
            catalog_item as ehl_catalog_item,
        )
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING,
        )
        ehl_on = bool(effector_work_held_load_is_active(config))
        if ehl_on or preset_n == PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING:
            states[EFFECTOR_WORK_HELD_LOAD] = ehl_on
            items.append(ehl_catalog_item(enabled=ehl_on))

        from mechanistic_mind.physical_system.flat_ground_gravity import (
            MECHANISM_ID as FLAT_GROUND_GRAVITY,
            CAPABILITY_FLAGS as FGG_FLAGS,
            flat_ground_gravity_is_active,
            catalog_item as fgg_catalog_item,
        )
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION,
            PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION,
        )
        fgg_on = bool(flat_ground_gravity_is_active(config))
        if fgg_on or preset_n in {
            PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION,
            PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION,
        }:
            states[FLAT_GROUND_GRAVITY] = fgg_on
            for flag in FGG_FLAGS:
                states[flag] = fgg_on
            items.append(fgg_catalog_item(enabled=fgg_on))
        from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
            MECHANISM_ID as FREE_RESOURCE_OBJECT_GROUND_FRICTION,
            free_resource_object_ground_friction_is_active,
            catalog_item as fogf_catalog_item,
        )
        fogf_on = bool(free_resource_object_ground_friction_is_active(config))
        if fogf_on or preset_n in {
            PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION,
            PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION,
        }:
            states[FREE_RESOURCE_OBJECT_GROUND_FRICTION] = fogf_on
            items.append(fogf_catalog_item(enabled=fogf_on))
        from mechanistic_mind.physical_system.surface_elevation_support import (
            MECHANISM_ID as SURFACE_ELEVATION_SUPPORT,
            surface_elevation_support_is_active,
            catalog_item as ses_catalog_item,
            capability_flags as ses_capability_flags,
        )
        ses_on = bool(surface_elevation_support_is_active(config))
        if ses_on or preset_n in {PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION}:
            states[SURFACE_ELEVATION_SUPPORT] = ses_on
            for flag, val in ses_capability_flags(config).items():
                states[flag] = bool(val)
            items.append(ses_catalog_item(enabled=ses_on))
        from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
            MECHANISM_ID as OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES,
            occupancy_support_and_contact_queries_is_active,
            occupancy_support_contact_catalog_item,
        )
        vw2_on = bool(occupancy_support_and_contact_queries_is_active(config))
        if vw2_on or ses_on or preset_n in {PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION}:
            states[OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES] = vw2_on
            items.append(occupancy_support_contact_catalog_item(enabled=vw2_on))
        from mechanistic_mind.physical_system.volumetric_world_material_separation import (
            MECHANISM_ID as VOLUMETRIC_WORLD_MATERIAL_SEPARATION,
            volumetric_world_material_separation_is_active,
            volumetric_material_separation_catalog_item,
        )
        vw3_on = bool(volumetric_world_material_separation_is_active(config))
        if vw3_on or vw2_on:
            states[VOLUMETRIC_WORLD_MATERIAL_SEPARATION] = vw3_on
            items.append(volumetric_material_separation_catalog_item(enabled=vw3_on))
        from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
            MECHANISM_ID as VOLUMETRIC_WORLD_MATERIAL_REINTEGRATION,
            volumetric_world_material_reintegration_is_active,
            volumetric_material_reintegration_catalog_item,
        )
        vw4_on = bool(volumetric_world_material_reintegration_is_active(config))
        if vw4_on or vw3_on:
            states[VOLUMETRIC_WORLD_MATERIAL_REINTEGRATION] = vw4_on
            items.append(volumetric_material_reintegration_catalog_item(enabled=vw4_on))
        from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
            MECHANISM_ID as EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE,
            effector_held_occupancy_exertion_bridge_is_active,
            catalog_item as vw5_catalog_item,
        )
        vw5_on = bool(effector_held_occupancy_exertion_bridge_is_active(config))
        if vw5_on or vw4_on or vw3_on:
            states[EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE] = vw5_on
            items.append(vw5_catalog_item(enabled=vw5_on))
        from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
            MECHANISM_ID as MINIMAL_VISION_3D_GEOMETRIC_INTERFACE,
            minimal_vision_3d_geometric_interface_is_active,
            catalog_item as vw6_catalog_item,
        )
        vw6_on = bool(minimal_vision_3d_geometric_interface_is_active(config))
        if vw6_on or vw5_on:
            states[MINIMAL_VISION_3D_GEOMETRIC_INTERFACE] = vw6_on
            items.append(vw6_catalog_item(enabled=vw6_on))
        from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import (
            MECHANISM_ID as OBSERVER_CAMERA_OCCUPANCY_CONSUMER,
            observer_camera_occupancy_consumer_is_active,
            catalog_item as vw7_catalog_item,
        )
        vw7_on = bool(observer_camera_occupancy_consumer_is_active(config))
        if vw7_on or vw6_on or vw1_on:
            states[OBSERVER_CAMERA_OCCUPANCY_CONSUMER] = vw7_on
            items.append(vw7_catalog_item(enabled=vw7_on))
        from mechanistic_mind.physical_system.body_normal_load_traction import (
            MECHANISM_ID as BODY_NORMAL_LOAD_TRACTION,
            body_normal_load_traction_is_active,
            catalog_item as bnlt_catalog_item,
        )
        bnlt_on = bool(body_normal_load_traction_is_active(config))
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY,
            PRESET_ACANTHOSTEGA_STATIC_TRACTION,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION,
            PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT,
            PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT,
            PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW,
        )
        if bnlt_on or preset_n in {
            PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION,
            PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY,
            PRESET_ACANTHOSTEGA_STATIC_TRACTION,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION,
            PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT,
            PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT,
            PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW,
        }:
            states[BODY_NORMAL_LOAD_TRACTION] = bnlt_on
            items.append(bnlt_catalog_item(enabled=bnlt_on))
        from mechanistic_mind.physical_system.continuous_surface_geometry import (
            MECHANISM_ID as CONTINUOUS_SURFACE_GEOMETRY,
            continuous_surface_geometry_is_active,
            catalog_item as csg_catalog_item,
        )
        csg_on = bool(continuous_surface_geometry_is_active(config))
        if csg_on or preset_n in {
            PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY,
            PRESET_ACANTHOSTEGA_STATIC_TRACTION,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION,
            PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT,
        }:
            states[CONTINUOUS_SURFACE_GEOMETRY] = csg_on
            items.append(csg_catalog_item(enabled=csg_on))
        from mechanistic_mind.physical_system.body_static_traction_threshold import (
            MECHANISM_ID as BODY_STATIC_TRACTION_THRESHOLD,
            body_static_traction_threshold_is_active,
            catalog_item as bst_catalog_item,
        )
        bst_on = bool(body_static_traction_threshold_is_active(config))
        if bst_on or preset_n in {
            PRESET_ACANTHOSTEGA_STATIC_TRACTION,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION,
            PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT,
        }:
            states[BODY_STATIC_TRACTION_THRESHOLD] = bst_on
            items.append(bst_catalog_item(enabled=bst_on))
        from mechanistic_mind.physical_system.free_resource_object_static_traction_threshold import (
            MECHANISM_ID as FREE_OBJECT_STATIC_TRACTION_THRESHOLD,
            free_resource_object_static_traction_threshold_is_active,
            catalog_item as fost_catalog_item,
        )
        fost_on = bool(free_resource_object_static_traction_threshold_is_active(config))
        if fost_on or preset_n in {
            PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION,
            PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT,
        }:
            states[FREE_OBJECT_STATIC_TRACTION_THRESHOLD] = fost_on
            items.append(fost_catalog_item(enabled=fost_on))
        from mechanistic_mind.physical_system.radius_aware_support_points import (
            MECHANISM_ID as RADIUS_AWARE_SUPPORT_POINTS,
            radius_aware_support_points_is_active,
            catalog_item as rasp_catalog_item,
        )
        rasp_on = bool(radius_aware_support_points_is_active(config))
        if rasp_on or preset_n in {PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW}:
            states[RADIUS_AWARE_SUPPORT_POINTS] = rasp_on
            items.append(rasp_catalog_item(enabled=rasp_on))
        from mechanistic_mind.physical_system.ses_decomposition_contract import (
            MECHANISM_ID as SES_DECOMPOSITION_CONTRACT,
            ses_decomposition_contract_is_active,
            catalog_item as sdc_catalog_item,
        )
        sdc_on = bool(ses_decomposition_contract_is_active(config))
        if sdc_on or preset_n in {
            PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT,
            PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW,
        }:
            states[SES_DECOMPOSITION_CONTRACT] = sdc_on
            items.append(sdc_catalog_item(enabled=sdc_on))
        from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
            MECHANISM_ID as SES_RUNTIME_TRANSITION_CLASSIFIER,
            ses_runtime_transition_classifier_is_active,
            catalog_item as srtc_catalog_item,
        )
        srtc_on = bool(ses_runtime_transition_classifier_is_active(config))
        if srtc_on or preset_n in {PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW}:
            states[SES_RUNTIME_TRANSITION_CLASSIFIER] = srtc_on
            items.append(srtc_catalog_item(enabled=srtc_on))

        from mechanistic_mind.physical_system.radius_aware_face_sweep import (
            MECHANISM_ID as RADIUS_AWARE_FACE_SWEEP,
            radius_aware_face_sweep_is_active,
            catalog_item as rafs_catalog_item,
        )
        rafs_on = bool(radius_aware_face_sweep_is_active(config))
        if rafs_on or preset_n in {
            PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP,
            PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW,
        }:
            states[RADIUS_AWARE_FACE_SWEEP] = rafs_on
            items.append(rafs_catalog_item(enabled=rafs_on))

        from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
            MECHANISM_ID as DIAGNOSTIC_NORMAL_LOAD_SHADOW,
            diagnostic_normal_load_shadow_is_active,
            catalog_item as dnls_catalog_item,
        )
        dnls_on = bool(diagnostic_normal_load_shadow_is_active(config))
        if dnls_on or preset_n in {
            PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW,
            PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW,
        }:
            states[DIAGNOSTIC_NORMAL_LOAD_SHADOW] = dnls_on
            items.append(dnls_catalog_item(enabled=dnls_on))

        from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
            MECHANISM_ID as CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW,
            continuous_gravitational_pe_diagnostic_shadow_is_active,
            catalog_item as cgpe_catalog_item,
        )
        cgpe_on = bool(continuous_gravitational_pe_diagnostic_shadow_is_active(config))
        if cgpe_on or preset_n == PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW:
            states[CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW] = cgpe_on
            items.append(cgpe_catalog_item(enabled=cgpe_on))


    meta = identity_for_config(config)
    return {
        "runtime_version": RUNTIME_VERSION,
        "model": meta,
        "mechanisms": items,
        "enabled": {k: v for k, v in states.items() if v is not None},
        "disabled": [k for k, v in states.items() if v is False],
        "promotion_summary": {
            "canonical": [m["id"] for m in items if m.get("promotion_class") == "CANONICAL" and m.get("enabled")],
            "experimental_enabled": [
                m["id"] for m in items if m.get("promotion_class") == "EXPERIMENTAL" and m.get("enabled")
            ],
        },
    }


def set_mechanism(config, mechanism_id: str, enabled: bool) -> dict[str, Any]:
    """Toggle a registered mechanism. Returns new snapshot."""
    on = bool(enabled)
    if mechanism_id == "distributed_morphology":
        config.morphology_mechanics.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "body_orientation":
        config.body_orientation.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "endogenous_motor_coupling":
        config.endogenous_motor.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "endogenous_motor_work_accounting":
        config.endogenous_motor_work.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "discrete_action_work_accounting":
        config.discrete_action_work.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "body_deformation":
        config.body_deformation.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "deformation_work":
        config.deformation_work.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "environmental_resource_transfer":
        config.environmental_resource.transfer_enabled = on
        if on:
            config.environmental_resource.mode = "EXPERIMENTAL"
        elif not config.environmental_resource.conversion_enabled:
            config.environmental_resource.mode = "OFF"
    elif mechanism_id == "resource_to_work_conversion":
        config.environmental_resource.conversion_enabled = on
        if on:
            config.environmental_resource.mode = "EXPERIMENTAL"
        elif not config.environmental_resource.transfer_enabled:
            config.environmental_resource.mode = "OFF"
    elif mechanism_id == "resource_A_transfer":
        config.complementary_resources.transfer_A_enabled = on
        if on:
            config.complementary_resources.mode = "EXPERIMENTAL"
        elif (
            not config.complementary_resources.transfer_B_enabled
            and not config.complementary_resources.conversion_enabled
        ):
            config.complementary_resources.mode = "OFF"
    elif mechanism_id == "resource_B_transfer":
        config.complementary_resources.transfer_B_enabled = on
        if on:
            config.complementary_resources.mode = "EXPERIMENTAL"
        elif (
            not config.complementary_resources.transfer_A_enabled
            and not config.complementary_resources.conversion_enabled
        ):
            config.complementary_resources.mode = "OFF"
    elif mechanism_id == "complementary_resource_conversion":
        config.complementary_resources.conversion_enabled = on
        if on:
            config.complementary_resources.mode = "EXPERIMENTAL"
        elif (
            not config.complementary_resources.transfer_A_enabled
            and not config.complementary_resources.transfer_B_enabled
        ):
            config.complementary_resources.mode = "OFF"
    elif mechanism_id == "held_resource_object_foreign_body_contact":
        from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
            set_held_foreign_body_contact,
        )
        set_held_foreign_body_contact(config, on)
    elif mechanism_id == "held_resource_object_translational_impulse_mediation":
        from mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation import (
            set_held_translational_impulse,
        )
        set_held_translational_impulse(config, on)

    elif mechanism_id == "effector_work_and_held_load_inertia_accounting":
        from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
            set_effector_work_held_load,
        )
        set_effector_work_held_load(config, on)

    elif mechanism_id in {
        "flat_ground_gravity",
        "vertical_physical_state",
        "uniform_gravity",
        "flat_ground_support",
        "vertical_contact_filter",
    }:
        from mechanistic_mind.physical_system.flat_ground_gravity import (
            set_flat_ground_gravity,
        )
        # Capability flags are co-gated with the umbrella (CRITICAL ORDER).
        set_flat_ground_gravity(config, on)

    elif mechanism_id == "sensorimotor_consequence_model":
        config.cognition.sensorimotor_consequence_model = bool(on)
    elif mechanism_id == "historical_sensorimotor_selection_bridge":
        config.cognition.historical_sensorimotor_selection_bridge = bool(on)
    elif mechanism_id == "prospective_scenario_competition":
        config.cognition.prospective_selection = "SCENARIO_COMPETITION" if on else "LEGACY_FIRST"
    elif mechanism_id == "instrumental_observation":
        config.cognition.instrumental_observation = on
    elif mechanism_id == "cognition":
        config.cognition.cognition_enabled = on
    elif mechanism_id in {
        "predictive_compression", "multiscale_prediction",
        "prospective_composition", "bounded_memory", "retrieval",
        "unknown_action_physical_probe",
        "predictive_equivalence",
        "predictive_relevance",
        "temporal_predictive_structure",
        "temporal_prospection_bridge",
        "predictive_conflict",
        "future_sensitive_action",
        "prediction_error_revision",
        "temporal_prediction_error",
        "predicted_context_prospection",
        "multistep_action_prospection",
        "contextual_predictive_organization",
        "context_grounded_prospection",
        "persistent_prospective_control",
    }:
        setattr(config.cognition, mechanism_id, on)
    elif mechanism_id == "spatiotemporal_climate_ecology":
        from mechanistic_mind.planet.climate_ecology import ClimateEcologyConfig
        if getattr(config.planet, "climate_ecology", None) is None:
            config.planet.climate_ecology = ClimateEcologyConfig()
        config.planet.climate_ecology.enabled = on
    elif mechanism_id == "resource_ecology_A":
        from mechanistic_mind.planet.climate_ecology import ClimateEcologyConfig
        if getattr(config.planet, "climate_ecology", None) is None:
            config.planet.climate_ecology = ClimateEcologyConfig()
        config.planet.climate_ecology.resource_ecology_A_enabled = on
        ce = config.planet.climate_ecology
        ce.resources_enabled = bool(ce.resource_ecology_A_enabled or ce.resource_ecology_B_enabled)
    elif mechanism_id == "resource_ecology_B":
        from mechanistic_mind.planet.climate_ecology import ClimateEcologyConfig
        if getattr(config.planet, "climate_ecology", None) is None:
            config.planet.climate_ecology = ClimateEcologyConfig()
        config.planet.climate_ecology.resource_ecology_B_enabled = on
        ce = config.planet.climate_ecology
        ce.resources_enabled = bool(ce.resource_ecology_A_enabled or ce.resource_ecology_B_enabled)
    elif mechanism_id == "physical_near_field_vision":
        from mechanistic_mind.physical_system.near_field_exteroception import NearFieldExteroceptionConfig
        if getattr(config, "near_field_exteroception", None) is None:
            config.near_field_exteroception = NearFieldExteroceptionConfig()
        nfe = config.near_field_exteroception
        if on:
            nfe.mode = "EXPERIMENTAL"
            nfe.perception_enabled = True
        else:
            # Ablate exo_* contribution only; keep package mode if already EXPERIMENTAL
            # so surface / illumination world state persist.
            nfe.perception_enabled = False
            if not nfe.enabled:
                nfe.mode = "OFF"
    elif mechanism_id == "illumination_cycle":
        from mechanistic_mind.physical_system.near_field_exteroception import NearFieldExteroceptionConfig
        if getattr(config, "near_field_exteroception", None) is None:
            config.near_field_exteroception = NearFieldExteroceptionConfig()
        nfe = config.near_field_exteroception
        if on:
            nfe.illumination_enabled = True
            nfe.illumination_frozen = None
            if not nfe.enabled:
                # Enable observational package so cycle can run; vision stays off
                # unless perception_enabled is already True.
                nfe.mode = "EXPERIMENTAL"
        else:
            nfe.illumination_enabled = False
    elif mechanism_id == "physical_body_optical_response":
        from mechanistic_mind.physical_system.near_field_exteroception import NearFieldExteroceptionConfig
        if getattr(config, "near_field_exteroception", None) is None:
            config.near_field_exteroception = NearFieldExteroceptionConfig()
        nfe = config.near_field_exteroception
        nfe.body_optical_enabled = bool(on)
        if on and not nfe.enabled:
            nfe.mode = "EXPERIMENTAL"
    elif mechanism_id == "oscillatory_signaling":
        from mechanistic_mind.physical_system.oscillatory_signaling import OscillatorySignalingConfig
        if getattr(config, "oscillatory_signaling", None) is None:
            config.oscillatory_signaling = OscillatorySignalingConfig()
        config.oscillatory_signaling.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "experimental_physical_signal":
        from mechanistic_mind.physical_system.physical_signal import PhysicalSignalConfig
        if getattr(config, "physical_signal", None) is None:
            config.physical_signal = PhysicalSignalConfig()
        config.physical_signal.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "articulated_head":
        from mechanistic_mind.physical_system.articulated_head import ArticulatedHeadConfig
        if getattr(config, "articulated_head", None) is None:
            config.articulated_head = ArticulatedHeadConfig()
        config.articulated_head.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "physical_push":
        from mechanistic_mind.physical_system.physical_push import PhysicalPushConfig
        if getattr(config, "physical_push", None) is None:
            config.physical_push = PhysicalPushConfig()
        config.physical_push.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "physical_vestibular_sensing":
        from mechanistic_mind.physical_system.vestibular_proprioception import VestibularConfig
        if getattr(config, "vestibular", None) is None:
            config.vestibular = VestibularConfig()
        config.vestibular.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "neck_proprioception":
        from mechanistic_mind.physical_system.vestibular_proprioception import NeckProprioceptionConfig
        if getattr(config, "neck_proprioception", None) is None:
            config.neck_proprioception = NeckProprioceptionConfig()
        config.neck_proprioception.mode = "EXPERIMENTAL" if on else "OFF"
    elif mechanism_id == "gentle_terrain_locomotion":
        from mechanistic_mind.physical_system.locomotion_profile import set_gentle_terrain_locomotion
        set_gentle_terrain_locomotion(config, on)
    elif mechanism_id == "physical_resource_objects":
        from mechanistic_mind.physical_system.resource_objects import set_physical_resource_objects
        set_physical_resource_objects(config, on)
    elif mechanism_id == "physical_resource_object_vision":
        from mechanistic_mind.physical_system.resource_objects import set_physical_resource_object_vision
        set_physical_resource_object_vision(config, on)
    elif mechanism_id == "single_physical_manipulator":
        from mechanistic_mind.physical_system.physical_manipulator import set_single_physical_manipulator
        set_single_physical_manipulator(config, on)
    elif mechanism_id == "physical_grasp_release":
        from mechanistic_mind.physical_system.physical_manipulator import set_physical_grasp_release
        set_physical_grasp_release(config, on)
    elif mechanism_id == "bilateral_physical_manipulators":
        from mechanistic_mind.physical_system.physical_manipulator import set_bilateral_physical_manipulators
        set_bilateral_physical_manipulators(config, on)
    elif mechanism_id == "bilateral_grasp_release":
        from mechanistic_mind.physical_system.physical_manipulator import set_bilateral_grasp_release
        set_bilateral_grasp_release(config, on)
    elif mechanism_id == "bilateral_bring_together":
        from mechanistic_mind.physical_system.physical_manipulator import set_bilateral_bring_together
        set_bilateral_bring_together(config, on)
    elif mechanism_id == "material_composition_merge":
        from mechanistic_mind.physical_system.material_composition import set_material_composition_merge
        set_material_composition_merge(config, on)
    elif mechanism_id == "passive_material_properties":
        from mechanistic_mind.physical_system.passive_material_properties import (
            set_passive_material_properties,
        )
        set_passive_material_properties(config, on)
    elif mechanism_id == "explicit_surface_deposition":
        from mechanistic_mind.physical_system.explicit_surface_deposition import (
            set_explicit_surface_deposition,
        )
        set_explicit_surface_deposition(config, on)
    elif mechanism_id == "surface_affinity_traction":
        from mechanistic_mind.physical_system.surface_affinity_traction import (
            set_surface_affinity_traction,
        )
        set_surface_affinity_traction(config, on)
    elif mechanism_id == "surface_traction_experience_bridge":
        from mechanistic_mind.physical_system.surface_traction_experience import (
            set_surface_traction_experience,
        )
        set_surface_traction_experience(config, on)
    elif mechanism_id == "surface_traction_prediction_adaptation":
        from mechanistic_mind.physical_system.surface_traction_prediction import (
            set_surface_traction_prediction,
        )
        set_surface_traction_prediction(config, on)
        from mechanistic_mind.physical_system.surface_traction_prediction import (
            surface_traction_prediction_is_active,
        )
        if surface_traction_prediction_is_active(config) and getattr(config, "cognition", None) is not None:
            config.cognition.sensorimotor_consequence_model = True
    elif mechanism_id == "physical_surface_optical_coating":
        from mechanistic_mind.physical_system.physical_surface_optical_coating import (
            set_physical_surface_optical_coating,
        )
        set_physical_surface_optical_coating(config, on)
    elif mechanism_id == "world_material_transactions":
        from mechanistic_mind.physical_system.world_material_transaction import (
            set_world_material_transactions,
        )
        set_world_material_transactions(config, on)
    elif mechanism_id == "multi_content_spatial_index":
        from mechanistic_mind.physical_system.spatial_contents import (
            set_multi_content_spatial_index,
        )
        set_multi_content_spatial_index(config, on)
    elif mechanism_id == "procedural_surface_columns":
        from mechanistic_mind.physical_system.procedural_surface_columns import (
            set_procedural_surface_columns,
        )
        set_procedural_surface_columns(config, on)
    elif mechanism_id == "volumetric_world_material_occupancy":
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            set_volumetric_world_material_occupancy,
        )
        set_volumetric_world_material_occupancy(config, on)
    elif mechanism_id == "occupancy_support_and_contact_queries":
        from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
            set_occupancy_support_and_contact_queries,
        )
        set_occupancy_support_and_contact_queries(config, on)
    elif mechanism_id == "volumetric_world_material_separation":
        from mechanistic_mind.physical_system.volumetric_world_material_separation import (
            set_volumetric_world_material_separation,
        )
        set_volumetric_world_material_separation(config, on)
    elif mechanism_id == "volumetric_world_material_reintegration":
        from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
            set_volumetric_world_material_reintegration,
        )
        set_volumetric_world_material_reintegration(config, on)
    elif mechanism_id == "effector_held_occupancy_exertion_bridge":
        from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
            set_effector_held_occupancy_exertion_bridge,
        )
        set_effector_held_occupancy_exertion_bridge(config, on)
    elif mechanism_id == "minimal_vision_3d_geometric_interface":
        from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
            set_minimal_vision_3d_geometric_interface,
        )
        set_minimal_vision_3d_geometric_interface(config, on)
    elif mechanism_id == "conservative_surface_column_transfer":
        from mechanistic_mind.physical_system.conservative_surface_column_transfer import (
            set_conservative_surface_column_transfer,
        )
        set_conservative_surface_column_transfer(config, on)
    elif mechanism_id == "conservative_surface_material_separation":
        from mechanistic_mind.physical_system.conservative_surface_material_separation import (
            set_conservative_surface_material_separation,
        )
        set_conservative_surface_material_separation(config, on)
    elif mechanism_id == "effector_terrain_contact_geometry":
        from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
            set_effector_terrain_contact_geometry,
        )
        set_effector_terrain_contact_geometry(config, on)
    elif mechanism_id == "manipulator_relative_world_actuation":
        from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
            set_manipulator_relative_world_actuation,
        )
        set_manipulator_relative_world_actuation(config, on)
    elif mechanism_id == "effector_bounded_actuator_effort":
        from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
            set_effector_bounded_actuator_effort,
        )
        set_effector_bounded_actuator_effort(config, on)
    elif mechanism_id == "surface_exertion_terrain_material_resistance":
        from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
            set_surface_exertion_terrain_material_resistance,
        )
        set_surface_exertion_terrain_material_resistance(config, on)
    elif mechanism_id == "held_resource_object_terrain_contact_geometry":
        from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
            set_held_resource_object_terrain_contact_geometry,
        )
        set_held_resource_object_terrain_contact_geometry(config, on)
    elif mechanism_id == "held_resource_object_terrain_mechanical_transmission":
        from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
            set_held_resource_object_terrain_mechanical_transmission,
        )
        set_held_resource_object_terrain_mechanical_transmission(config, on)
    elif mechanism_id == "held_mediated_surface_exertion_integration":
        from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
            set_held_mediated_surface_exertion_integration,
        )
        set_held_mediated_surface_exertion_integration(config, on)
    elif mechanism_id == "detached_terrain_material_initial_placement":
        from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
            set_detached_terrain_material_initial_placement,
        )
        set_detached_terrain_material_initial_placement(config, on)
    elif mechanism_id == "local_physical_signal_transport":
        from mechanistic_mind.physical_system.local_physical_signal_transport import (
            set_local_physical_signal_transport,
        )
        set_local_physical_signal_transport(config, on)
    elif mechanism_id == "physical_contact_acoustic_emission":
        from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
            set_physical_contact_acoustic_emission,
        )
        set_physical_contact_acoustic_emission(config, on)
    elif mechanism_id == "free_resource_object_kinematics":
        from mechanistic_mind.physical_system.free_resource_object_kinematics import (
            set_free_resource_object_kinematics,
        )
        set_free_resource_object_kinematics(config, on)
    elif mechanism_id == "physical_body_resource_object_contact":
        from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
            set_body_object_contact,
        )
        set_body_object_contact(config, on)
    elif mechanism_id == "body_resource_object_contact_impulse":
        from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
            set_body_object_impulse,
        )
        set_body_object_impulse(config, on)
    elif mechanism_id == "body_resource_object_impact_acoustic_emission":
        from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
            set_body_object_impact_acoustics,
        )
        set_body_object_impact_acoustics(config, on)
    elif mechanism_id == "physical_resource_object_pair_contact":
        from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
            set_resource_object_pair_contact,
        )
        set_resource_object_pair_contact(config, on)
    elif mechanism_id == "resource_object_pair_contact_impulse":
        from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
            set_resource_object_pair_impulse,
        )
        set_resource_object_pair_impulse(config, on)
    elif mechanism_id == "resource_object_pair_impact_acoustic_emission":
        from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
            set_resource_object_pair_impact_acoustics,
        )
        set_resource_object_pair_impact_acoustics(config, on)
    elif mechanism_id == "resource_object_pair_impact_acoustic_emission":
        from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
            set_resource_object_pair_impact_acoustics,
        )
        set_resource_object_pair_impact_acoustics(config, on)
    elif mechanism_id == "sensorimotor_consequence_model":
        if getattr(config, "cognition", None) is not None:
            config.cognition.sensorimotor_consequence_model = bool(on)
    else:
        raise KeyError(f"unknown mechanism: {mechanism_id}")
    return mechanism_snapshot(config)
