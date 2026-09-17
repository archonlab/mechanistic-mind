"""MM 1.0 Tiktaalik identity constants (no runtime imports)."""

MODEL_FAMILY = "Mechanistic Mind"
MODEL_VERSION = "1.0"
MODEL_CODENAME = "Tiktaalik"
RUNTIME_VERSION = "MM_1_0_TIKTAALIK"
LEGACY_RUNTIME_VERSION = "CURRENT_INTEGRATED_MM"
SNAPSHOT_SCHEMA = "mm.physical_system.snapshot.v2"
OBSERVER_API_VERSION = "0.2.0"
MANIFEST_SCHEMA_VERSION = "mm.model_manifest.v1"

PROMOTION: dict[str, str] = {
    "predictive_compression": "CANONICAL",
    "multiscale_prediction": "CANONICAL",
    "prospective_composition": "CANONICAL",
    "bounded_memory": "CANONICAL",
    "retrieval": "CANONICAL",
    "prospective_scenario_competition": "CANONICAL",
    "instrumental_observation": "CANONICAL",
    "cognition": "CANONICAL",
    "unknown_action_physical_probe": "EXPERIMENTAL",
    "predictive_equivalence": "EXPERIMENTAL",
    "predictive_relevance": "EXPERIMENTAL",
    "temporal_predictive_structure": "EXPERIMENTAL",
    "temporal_prospection_bridge": "EXPERIMENTAL",
    "predictive_conflict": "EXPERIMENTAL",
    "future_sensitive_action": "EXPERIMENTAL",
    "prediction_error_revision": "EXPERIMENTAL",
    "temporal_prediction_error": "EXPERIMENTAL",
    "predicted_context_prospection": "EXPERIMENTAL",
    "multistep_action_prospection": "EXPERIMENTAL",
    "discrete_action_bridge": "CANONICAL",
    "shared_work_allocation": "CANONICAL",
    "environmental_site_mechanics": "CANONICAL",
    "distributed_morphology": "CANONICAL",
    "body_orientation": "CANONICAL",
    "endogenous_motor_coupling": "CANONICAL",
    "endogenous_motor_work_accounting": "CANONICAL",
    "discrete_action_work_accounting": "CANONICAL",
    "body_deformation": "CANONICAL",
    "deformation_work": "CANONICAL",
    "environmental_resource_transfer": "CANONICAL",
    "resource_to_work_conversion": "CANONICAL",
    "resource_A_transfer": "CANONICAL",
    "resource_B_transfer": "CANONICAL",
    "complementary_resource_conversion": "CANONICAL",
    "spatiotemporal_climate_ecology": "EXPERIMENTAL",
    "experimental_physical_signal": "EXPERIMENTAL",
    "two_agent_runtime": "NOT_INTEGRATED",
    "engine_47": "LEGACY",
    "organism_world": "LEGACY",
    "instrumental_emit_bridge": "BRIDGE_MISSING",
}


def display_name() -> str:
    return f"MM {MODEL_VERSION} — {MODEL_CODENAME}"


def promotion_class(mechanism_id: str) -> str:
    return PROMOTION.get(mechanism_id, "NOT_INTEGRATED")
