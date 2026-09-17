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
        "description": "Competes supported prospective continuations when multiple exist.",
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
        "description": "Experimental world: latitudinal climate gradient, hidden seasonal cycle, finite R_A/R_B productivity from local T. Default OFF. Not a cognition change.",
        "validation": "World physics only; cognition unchanged (mm_seasonal_resource_ecology).",
        "provenance": "mm_seasonal_resource_ecology_experiment",
        "default_integrated": False,
    },
    {
        "id": "experimental_physical_signal",
        "config_path": "physical_signal.mode",
        "label": "EXPERIMENTAL PHYSICAL SIGNAL",
        "description": "Shared-world FIELD_A/FIELD_B amplitude with decay and neighbor spread. Default OFF. Not EMIT-in-available_actions. Not communication.",
        "validation": "Experimental TwoAgentRuntime signal bridge (mm_two_agent_physical_signals). Unpromoted.",
        "provenance": "mm_two_agent_physical_signals_experiment",
        "default_integrated": False,
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
        "instrumental_observation": bool(getattr(cog, "instrumental_observation", False)),
        "unknown_action_physical_probe": bool(getattr(cog, "unknown_action_physical_probe", False)),
        "spatiotemporal_climate_ecology": bool(
            getattr(getattr(config.planet, "climate_ecology", None), "enabled", False)
        ),
        "experimental_physical_signal": str(getattr(getattr(config, "physical_signal", None), "mode", "OFF")).upper() == "EXPERIMENTAL",
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
        "instrumental_observation": "COGNITION", "unknown_action_physical_probe": "COGNITION",
        "cognition": "COGNITION",
        "spatiotemporal_climate_ecology": "WORLD",
        "experimental_physical_signal": "WORLD",
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
        "multiscale_prediction": ["bounded_memory"],
        "retrieval": ["bounded_memory"],
        "body_deformation": ["body_orientation"],
        "deformation_work": ["body_deformation"],
        "endogenous_motor_work_accounting": ["endogenous_motor_coupling", "deformation_work"],
        "discrete_action_work_accounting": ["deformation_work"],
        "resource_to_work_conversion": ["environmental_resource_transfer"],
        "complementary_resource_conversion": ["resource_A_transfer", "resource_B_transfer"],
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
    from mechanistic_mind.model.tiktaalik import model_metadata

    meta = model_metadata(config)
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
    }:
        setattr(config.cognition, mechanism_id, on)
    elif mechanism_id == "spatiotemporal_climate_ecology":
        from mechanistic_mind.planet.climate_ecology import ClimateEcologyConfig
        if getattr(config.planet, "climate_ecology", None) is None:
            config.planet.climate_ecology = ClimateEcologyConfig()
        config.planet.climate_ecology.enabled = on
    elif mechanism_id == "experimental_physical_signal":
        from mechanistic_mind.physical_system.physical_signal import PhysicalSignalConfig
        if getattr(config, "physical_signal", None) is None:
            config.physical_signal = PhysicalSignalConfig()
        config.physical_signal.mode = "EXPERIMENTAL" if on else "OFF"
    else:
        raise KeyError(f"unknown mechanism: {mechanism_id}")
    return mechanism_snapshot(config)
