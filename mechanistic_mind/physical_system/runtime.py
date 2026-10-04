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
from .composite_motor import (
    CompositeMotorOutput,
    OscillatorMotorComponent,
    apply_composite_motor,
    build_composite_from_factorized,
    motor_control_events,
    select_factorized_side_channels,
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
from .near_field_exteroception import NearFieldExteroceptionConfig
from .articulated_head import ArticulatedHeadConfig, step_articulated_head
from .physical_push import PhysicalPushConfig
from .vestibular_proprioception import VestibularConfig, NeckProprioceptionConfig
from .oscillatory_signaling import OscillatorySignalingConfig
from .locomotion_profile import (
    LocomotionPhysicsProfile,
    apply_ground_rest_after_self_drive,
    profile_is_active,
    tiktaalik_locomotion_profile,
)
from .resource_objects import (
    PhysicalResourceObjectsConfig,
    PhysicalResourceObjectVisionConfig,
    object_vision_is_active,
    spawn_preset_resource_objects,
)
from .material_composition import (
    MaterialCompositionMergeConfig,
    material_composition_merge_is_active,
)
from .passive_material_properties import PassiveMaterialPropertiesConfig
from .physical_optical_material_profile import PhysicalOpticalMaterialProfileConfig
from .exposed_surface_optical_interaction_authority import (
    ExposedSurfaceOpticalInteractionAuthorityConfig,
)
from .abstract_spectral_light_source_and_direct_transport import (
    AbstractSpectralLightSourceAndDirectTransportConfig,
)
from .object_body_held_optical_surfaces import (
    ObjectBodyHeldOpticalSurfacesConfig,
)
from .organism_physical_optical_reception import (
    OrganismPhysicalOpticalReceptionConfig,
)
from .sensory_modality_temporal_alignment import (
    SensoryModalityTemporalAlignmentConfig,
)
from .explicit_surface_deposition import (
    ExplicitSurfaceDepositionConfig,
    explicit_surface_deposition_is_active,
)
from .surface_affinity_traction import (
    SurfaceAffinityTractionConfig,
    surface_affinity_traction_is_active,
)
from .surface_traction_experience import (
    SurfaceTractionExperienceConfig,
    surface_traction_experience_is_active,
)
from .surface_traction_prediction import (
    SurfaceTractionPredictionConfig,
    surface_traction_prediction_is_active,
)
from .physical_surface_optical_coating import (
    PhysicalSurfaceOpticalCoatingConfig,
    physical_surface_optical_coating_is_active,
)
from .world_material_transaction import WorldMaterialTransactionsConfig
from .physical_manipulator import (
    BilateralBringTogetherConfig,
    BilateralGraspReleaseConfig,
    BilateralPhysicalManipulatorsConfig,
    PhysicalGraspReleaseConfig,
    SinglePhysicalManipulatorConfig,
    bilateral_grasp_release_is_active,
    bring_together_is_active,
    grasp_release_is_active,
    manipulator_is_active,
    open_pair_aperture,
    resolve_shared_world_manipulators,
    world_manipulators_active,
)
from .mechanism_registry import RUNTIME_VERSION, mechanism_snapshot, set_mechanism
from .actions import OSC_ACTIONS, PUSH_ACTIONS, available_actions
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
    clear_derived_indexes,
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
    model_line: str = "TIKTAALIK"
    public_preset: str | None = None
    ecology_preset: str = "CURRENT"  # CURRENT | GENTLE_FREE_MOVEMENT — Observer/runtime GT only
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
    near_field_exteroception: NearFieldExteroceptionConfig = field(
        default_factory=NearFieldExteroceptionConfig
    )
    articulated_head: ArticulatedHeadConfig = field(default_factory=ArticulatedHeadConfig)
    physical_push: PhysicalPushConfig = field(default_factory=PhysicalPushConfig)
    vestibular: VestibularConfig = field(default_factory=VestibularConfig)
    neck_proprioception: NeckProprioceptionConfig = field(default_factory=NeckProprioceptionConfig)
    oscillatory_signaling: OscillatorySignalingConfig = field(
        default_factory=OscillatorySignalingConfig
    )
    locomotion_profile: LocomotionPhysicsProfile = field(
        default_factory=tiktaalik_locomotion_profile
    )
    physical_resource_objects: PhysicalResourceObjectsConfig = field(
        default_factory=PhysicalResourceObjectsConfig
    )
    physical_resource_object_vision: PhysicalResourceObjectVisionConfig = field(
        default_factory=PhysicalResourceObjectVisionConfig
    )
    single_physical_manipulator: SinglePhysicalManipulatorConfig = field(
        default_factory=SinglePhysicalManipulatorConfig
    )
    physical_grasp_release: PhysicalGraspReleaseConfig = field(
        default_factory=PhysicalGraspReleaseConfig
    )
    bilateral_physical_manipulators: BilateralPhysicalManipulatorsConfig = field(
        default_factory=BilateralPhysicalManipulatorsConfig
    )
    bilateral_grasp_release: BilateralGraspReleaseConfig = field(
        default_factory=BilateralGraspReleaseConfig
    )
    bilateral_bring_together: BilateralBringTogetherConfig = field(
        default_factory=BilateralBringTogetherConfig
    )
    material_composition_merge: MaterialCompositionMergeConfig = field(
        default_factory=MaterialCompositionMergeConfig
    )
    passive_material_properties: PassiveMaterialPropertiesConfig = field(
        default_factory=PassiveMaterialPropertiesConfig
    )
    physical_optical_material_profile: PhysicalOpticalMaterialProfileConfig = field(
        default_factory=PhysicalOpticalMaterialProfileConfig
    )
    exposed_surface_optical_interaction_authority: ExposedSurfaceOpticalInteractionAuthorityConfig = field(
        default_factory=ExposedSurfaceOpticalInteractionAuthorityConfig
    )
    abstract_spectral_light_source_and_direct_transport: AbstractSpectralLightSourceAndDirectTransportConfig = field(
        default_factory=AbstractSpectralLightSourceAndDirectTransportConfig
    )
    object_body_held_optical_surfaces: ObjectBodyHeldOpticalSurfacesConfig = field(
        default_factory=ObjectBodyHeldOpticalSurfacesConfig
    )
    organism_physical_optical_reception: OrganismPhysicalOpticalReceptionConfig = field(
        default_factory=OrganismPhysicalOpticalReceptionConfig
    )
    sensory_modality_temporal_alignment: SensoryModalityTemporalAlignmentConfig = field(
        default_factory=SensoryModalityTemporalAlignmentConfig
    )
    explicit_surface_deposition: ExplicitSurfaceDepositionConfig = field(
        default_factory=ExplicitSurfaceDepositionConfig
    )
    surface_affinity_traction: SurfaceAffinityTractionConfig = field(
        default_factory=SurfaceAffinityTractionConfig
    )
    surface_traction_experience: SurfaceTractionExperienceConfig = field(
        default_factory=SurfaceTractionExperienceConfig
    )
    surface_traction_prediction: SurfaceTractionPredictionConfig = field(
        default_factory=SurfaceTractionPredictionConfig
    )
    physical_surface_optical_coating: PhysicalSurfaceOpticalCoatingConfig = field(
        default_factory=PhysicalSurfaceOpticalCoatingConfig
    )
    world_material_transactions: WorldMaterialTransactionsConfig = field(
        default_factory=WorldMaterialTransactionsConfig
    )
    multi_content_spatial_index: Any = None
    procedural_surface_columns: Any = None
    # Researcher-only conservative surface column transfer; absent (None) = OFF.
    conservative_surface_column_transfer: Any = None
    # Acanthostega local physical signal transport (UNIFORM_SIGNAL_MEDIUM_V1); absent (None) = OFF.
    local_physical_signal_transport: Any = None
    # Acanthostega physical contact acoustic emission (Audio B); absent (None) = OFF.
    physical_contact_acoustic_emission: Any = None
    # Acanthostega free ResourceObject kinematics; absent (None) = OFF.
    free_resource_object_kinematics: Any = None
    # Acanthostega body↔ResourceObject contact FACT; absent (None) = OFF.
    physical_body_resource_object_contact: Any = None
    # Acanthostega body↔ResourceObject contact RESPONSE (mass+compliance impulse); absent (None) = OFF.
    body_resource_object_contact_impulse: Any = None
    # Acanthostega body/ResourceObject impact acoustic emission; absent (None) = OFF.
    body_resource_object_impact_acoustic_emission: Any = None
    # Acanthostega FREE ResourceObject↔ResourceObject contact FACT; absent (None) = OFF.
    physical_resource_object_pair_contact: Any = None
    # Acanthostega FREE ResourceObject↔ResourceObject contact RESPONSE; absent (None) = OFF.
    resource_object_pair_contact_impulse: Any = None
    # Acanthostega FREE ResourceObject↔ResourceObject impact acoustic emission; absent (None) = OFF.
    resource_object_pair_impact_acoustic_emission: Any = None
    # Acanthostega HELD ResourceObject↔foreign body contact FACT; absent (None) = OFF.
    held_resource_object_foreign_body_contact: Any = None
    # Acanthostega HELD translational impulse mediation RESPONSE; absent (None) = OFF.
    held_resource_object_translational_impulse_mediation: Any = None
    # Acanthostega effector work + held-load inertia accounting; absent (None) = OFF.
    effector_work_and_held_load_inertia_accounting: Any = None
    # Acanthostega Phase C flat ground gravity / vertical state; absent (None) = OFF.
    flat_ground_gravity: Any = None
    free_resource_object_ground_friction: Any = None
    # Acanthostega Phase C energy-accounted surface elevation support; absent (None) = OFF.
    surface_elevation_support: Any = None
    # Acanthostega Phase C body normal-load traction + passive sliding; absent (None) = OFF.
    body_normal_load_traction: Any = None
    # Acanthostega Phase C continuous surface geometry (bilinear h + analytic n̂); absent (None) = OFF.
    continuous_surface_geometry: Any = None
    # Acanthostega Phase C G2A body static traction threshold; absent (None) = OFF.
    body_static_traction_threshold: Any = None
    free_resource_object_static_traction_threshold: Any = None
    radius_aware_support_points: Any = None
    # Acanthostega Phase C G2C1 SES decomposition contract (metadata only); absent (None) = OFF.
    ses_decomposition_contract: Any = None
    # Acanthostega Phase C G2C2 SES runtime transition classifier (classification only); absent (None) = OFF.
    ses_runtime_transition_classifier: Any = None
    # Acanthostega Phase C radius-aware face sweep SES plan evidence; absent (None) = OFF.
    radius_aware_face_sweep: Any = None
    # Acanthostega Phase C G2D diagnostic normal-load shadow; absent (None) = OFF.
    diagnostic_normal_load_shadow: Any = None
    # Acanthostega Phase C continuous gravitational PE diagnostic shadow; absent (None) = OFF.
    continuous_gravitational_pe_diagnostic_shadow: Any = None
    # Acanthostega Phase C Policy C continuous gravitational PE (physical); absent (None) = OFF.
    continuous_gravitational_pe: Any = None
    # Acanthostega Phase C tangent-gravity diagnostic shadow; absent (None) = OFF.
    tangent_gravity_diagnostic_shadow: Any = None
    coherent_slope_dynamics: Any = None
    # Beta 4 conservative surface material separation (column→ResourceObject); absent (None) = OFF.
    conservative_surface_material_separation: Any = None
    # Beta 4 effector↔terrain contact geometry (fact only); absent (None) = OFF.
    effector_terrain_contact_geometry: Any = None
    # Researcher-only passive effector↔occupancy reachability trace; absent (None) = OFF.
    effector_occupancy_reachability_trace: Any = None
    # Beta 4 manipulator relative world actuation (kinematic DOF); absent (None) = OFF.
    manipulator_relative_world_actuation: Any = None
    # Beta 4 effector bounded actuator effort along relative_z; absent (None) = OFF.
    effector_bounded_actuator_effort: Any = None
    # Beta 4 surface exertion / terrain material resistance; absent (None) = OFF.
    surface_exertion_terrain_material_resistance: Any = None
    # Beta 4 held ResourceObject ↔ terrain contact geometry (fact only); absent (None) = OFF.
    held_resource_object_terrain_contact_geometry: Any = None
    # Beta 4 held ResourceObject ↔ terrain mechanical transmission; absent (None) = OFF.
    held_resource_object_terrain_mechanical_transmission: Any = None
    # Beta 4 held-mediated surface exertion → SETMR integration; absent (None) = OFF.
    held_mediated_surface_exertion_integration: Any = None
    # Beta 4 detached terrain material initial placement; absent (None) = OFF.
    detached_terrain_material_initial_placement: Any = None
    # Beta 4 BNLT MOVE breakaway locomotion repair; absent (None) = OFF.
    bnlt_move_breakaway_locomotion_repair: Any = None
    repeated_conservative_surface_column_separation: Any = None
    # Beta 4 event-driven crowded placement retry contract; absent (None) = OFF.
    event_driven_crowded_placement_retry_contract: Any = None
    # Beta 4 detached material amount-scaled collision radius; absent (None) = OFF.
    detached_material_amount_scaled_collision_radius: Any = None
    # Beta 4 held COMBINE radius resize transaction; absent (None) = OFF.
    held_combine_radius_resize_transaction: Any = None
    # Beta 4 held deposition radius shrink transaction; absent (None) = OFF.
    held_deposition_radius_shrink_transaction: Any = None
    # Free-Space V1A support/PE authority contract; absent (None) = OFF.
    free_space_state_and_pe_authority_contract: Any = None
    # Free-Space V1B vertical terrain landing contact response; absent (None) = OFF.
    vertical_terrain_landing_contact_response: Any = None
    # Free-Space V1C vertical impact acoustic emission; absent (None) = OFF.
    vertical_impact_acoustic_emission: Any = None
    # Free-Space V1D RELEASE/excavation support-loss integration; absent (None) = OFF.
    release_and_excavation_support_loss_integration: Any = None

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


def _lps_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field (Tiktaalik / every earlier Acanthostega snapshot) -> None -> mechanism OFF."""
    raw = configs.get("local_physical_signal_transport")
    if not raw:
        return None
    from mechanistic_mind.physical_system.local_physical_signal_transport import UniformSignalMediumConfig

    return UniformSignalMediumConfig.from_dict(raw)


def _pca_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field (Tiktaalik / every earlier Acanthostega snapshot) -> None -> mechanism OFF."""
    raw = configs.get("physical_contact_acoustic_emission")
    if not raw:
        return None
    from mechanistic_mind.physical_system.physical_contact_acoustic_emission import ContactAcousticConfig

    return ContactAcousticConfig.from_dict(raw)


def _boc_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("physical_body_resource_object_contact")
    if not raw:
        return None
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import BodyObjectContactConfig
    return BodyObjectContactConfig.from_dict(raw)

def _boi_config_from_snapshot(configs: dict[str, Any]) -> Any:
    raw = configs.get("body_resource_object_contact_impulse")
    if not raw:
        return None
    from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
        BodyObjectContactImpulseConfig,
    )
    return BodyObjectContactImpulseConfig.from_dict(raw)


def _ooi_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("resource_object_pair_contact_impulse")
    if not raw:
        return None
    from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
        ResourceObjectPairContactImpulseConfig,
    )
    return ResourceObjectPairContactImpulseConfig.from_dict(raw)


def _ooia_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("resource_object_pair_impact_acoustic_emission")
    if not raw:
        return None
    from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
        ResourceObjectPairImpactAcousticConfig,
    )
    return ResourceObjectPairImpactAcousticConfig.from_dict(raw)




def _ehl_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("effector_work_and_held_load_inertia_accounting")
    if not raw:
        return None
    from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
        EffectorWorkHeldLoadConfig,
    )
    return EffectorWorkHeldLoadConfig.from_dict(raw)


def _fgg_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("flat_ground_gravity")
    if not raw:
        return None
    from mechanistic_mind.physical_system.flat_ground_gravity import FlatGroundGravityConfig
    return FlatGroundGravityConfig.from_dict(raw)




def _ses_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("surface_elevation_support")
    if not raw:
        return None
    from mechanistic_mind.physical_system.surface_elevation_support import (
        SurfaceElevationSupportConfig,
    )
    return SurfaceElevationSupportConfig.from_dict(raw)

def _bnlt_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("body_normal_load_traction")
    if not raw:
        return None
    from mechanistic_mind.physical_system.body_normal_load_traction import (
        BodyNormalLoadTractionConfig,
    )
    return BodyNormalLoadTractionConfig.from_dict(raw)


def _csg_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("continuous_surface_geometry")
    if not raw:
        return None
    from mechanistic_mind.physical_system.continuous_surface_geometry import (
        ContinuousSurfaceGeometryConfig,
    )
    return ContinuousSurfaceGeometryConfig.from_dict(raw)


def _bst_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("body_static_traction_threshold")
    if not raw:
        return None
    from mechanistic_mind.physical_system.body_static_traction_threshold import (
        BodyStaticTractionThresholdConfig,
    )
    return BodyStaticTractionThresholdConfig.from_dict(raw)

def _fost_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("free_resource_object_static_traction_threshold")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.free_resource_object_static_traction_threshold import (
        FreeResourceObjectStaticTractionThresholdConfig,
    )
    return FreeResourceObjectStaticTractionThresholdConfig.from_dict(raw)


def _rasp_config_from_snapshot(configs: dict[str, Any]) -> Any:
    raw = configs.get("radius_aware_support_points")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.radius_aware_support_points import (
        RadiusAwareSupportPointsConfig,
    )
    return RadiusAwareSupportPointsConfig.from_dict(raw if isinstance(raw, dict) else None)


def _sdc_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> G2C1 OFF (old parent snapshots stay OFF)."""
    raw = configs.get("ses_decomposition_contract")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        SesDecompositionContractConfig,
        validate_config,
    )
    cfg = SesDecompositionContractConfig.from_dict(raw if isinstance(raw, dict) else None)
    validate_config(cfg)
    return cfg


def _srtc_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> G2C2 OFF (old parent snapshots stay OFF)."""
    raw = configs.get("ses_runtime_transition_classifier")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        SesRuntimeTransitionClassifierConfig,
        validate_config,
    )
    cfg = SesRuntimeTransitionClassifierConfig.from_dict(raw if isinstance(raw, dict) else None)
    validate_config(cfg)
    return cfg


def _rafs_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> face-sweep OFF (old parent snapshots stay OFF)."""
    raw = configs.get("radius_aware_face_sweep")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        RadiusAwareFaceSweepConfig,
        validate_config,
    )
    cfg = RadiusAwareFaceSweepConfig.from_dict(raw if isinstance(raw, dict) else None)
    validate_config(cfg)
    return cfg



def _csd_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> coherent slope dynamics OFF."""
    raw = configs.get("coherent_slope_dynamics")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.coherent_slope_dynamics import (
        CoherentSlopeDynamicsConfig,
        validate_config,
    )
    cfg = CoherentSlopeDynamicsConfig.from_dict(raw if isinstance(raw, dict) else None)
    validate_config(cfg)
    return cfg


def _csms_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> surface material separation OFF."""
    raw = configs.get("conservative_surface_material_separation")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        ConservativeSurfaceMaterialSeparationConfig,
        validate_config,
    )
    cfg = ConservativeSurfaceMaterialSeparationConfig.from_dict(raw if isinstance(raw, dict) else None)
    validate_config(cfg)
    return cfg


def _etc_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> effector terrain contact geometry OFF."""
    raw = configs.get("effector_terrain_contact_geometry")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        EffectorTerrainContactGeometryConfig,
        validate_config,
    )
    cfg = EffectorTerrainContactGeometryConfig.from_dict(raw if isinstance(raw, dict) else None)
    validate_config(cfg)
    return cfg


def _eort_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> effector occupancy reachability trace OFF."""
    raw = configs.get("effector_occupancy_reachability_trace")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.effector_occupancy_reachability_trace import (
        EffectorOccupancyReachabilityTraceConfig,
    )
    return EffectorOccupancyReachabilityTraceConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )


def _mrwa_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> manipulator relative world actuation OFF."""
    raw = configs.get("manipulator_relative_world_actuation")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        ManipulatorRelativeWorldActuationConfig,
        validate_config,
    )
    cfg = ManipulatorRelativeWorldActuationConfig.from_dict(raw if isinstance(raw, dict) else None)
    validate_config(cfg)
    return cfg


def _ebae_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> effector bounded actuator effort OFF."""
    raw = configs.get("effector_bounded_actuator_effort")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        EffectorBoundedActuatorEffortConfig,
        validate_config,
    )
    cfg = EffectorBoundedActuatorEffortConfig.from_dict(raw if isinstance(raw, dict) else None)
    validate_config(cfg)
    return cfg


def _setmr_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> surface exertion terrain material resistance OFF."""
    raw = configs.get("surface_exertion_terrain_material_resistance")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        SurfaceExertionTerrainMaterialResistanceConfig,
        validate_config,
    )
    cfg = SurfaceExertionTerrainMaterialResistanceConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _hotc_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> held object terrain contact geometry OFF."""
    raw = configs.get("held_resource_object_terrain_contact_geometry")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
        HeldResourceObjectTerrainContactGeometryConfig,
        validate_config,
    )
    cfg = HeldResourceObjectTerrainContactGeometryConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _hotmt_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> held object terrain mechanical transmission OFF."""
    raw = configs.get("held_resource_object_terrain_mechanical_transmission")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
        HeldResourceObjectTerrainMechanicalTransmissionConfig,
        validate_config,
    )
    cfg = HeldResourceObjectTerrainMechanicalTransmissionConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _hmsi_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> held-mediated surface exertion integration OFF."""
    raw = configs.get("held_mediated_surface_exertion_integration")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
        HeldMediatedSurfaceExertionIntegrationConfig,
        validate_config,
    )
    cfg = HeldMediatedSurfaceExertionIntegrationConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _dtip_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> detached terrain material initial placement OFF."""
    raw = configs.get("detached_terrain_material_initial_placement")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        DetachedTerrainMaterialInitialPlacementConfig,
        validate_config,
    )
    cfg = DetachedTerrainMaterialInitialPlacementConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _rcss_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> repeated conservative surface-column separation OFF."""
    raw = configs.get("repeated_conservative_surface_column_separation")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        RepeatedConservativeSurfaceColumnSeparationConfig,
        validate_config,
    )
    cfg = RepeatedConservativeSurfaceColumnSeparationConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _crowded_retry_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> event-driven crowded placement retry contract OFF."""
    raw = configs.get("event_driven_crowded_placement_retry_contract")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        EventDrivenCrowdedPlacementRetryContractConfig,
        validate_config,
    )
    cfg = EventDrivenCrowdedPlacementRetryContractConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _detached_material_size_geometry_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> detached material amount-scaled collision radius OFF."""
    raw = configs.get("detached_material_amount_scaled_collision_radius")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        DetachedMaterialAmountScaledCollisionRadiusConfig,
        validate_config,
    )
    cfg = DetachedMaterialAmountScaledCollisionRadiusConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _held_combine_radius_resize_transaction_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> held COMBINE radius resize transaction OFF."""
    raw = configs.get("held_combine_radius_resize_transaction")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
        HeldCombineRadiusResizeTransactionConfig,
        validate_config,
    )
    cfg = HeldCombineRadiusResizeTransactionConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _held_deposition_radius_shrink_transaction_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> held deposition radius shrink transaction OFF."""
    raw = configs.get("held_deposition_radius_shrink_transaction")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction import (
        HeldDepositionRadiusShrinkTransactionConfig,
        validate_config,
    )
    cfg = HeldDepositionRadiusShrinkTransactionConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _free_space_state_and_pe_authority_contract_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> Free-Space V1A contract OFF."""
    raw = configs.get("free_space_state_and_pe_authority_contract")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
        FreeSpaceStateAndPeAuthorityContractConfig,
        validate_config,
    )
    cfg = FreeSpaceStateAndPeAuthorityContractConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _vertical_terrain_landing_contact_response_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> Free-Space V1B landing OFF."""
    raw = configs.get("vertical_terrain_landing_contact_response")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
        VerticalTerrainLandingContactResponseConfig,
        validate_config,
    )
    cfg = VerticalTerrainLandingContactResponseConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _vertical_impact_acoustic_emission_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> Free-Space V1C acoustics OFF."""
    raw = configs.get("vertical_impact_acoustic_emission")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
        VerticalImpactAcousticEmissionConfig,
        validate_config,
    )
    cfg = VerticalImpactAcousticEmissionConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _release_and_excavation_support_loss_integration_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> Free-Space V1D integration OFF."""
    raw = configs.get("release_and_excavation_support_loss_integration")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
        ReleaseAndExcavationSupportLossIntegrationConfig,
        validate_config,
    )
    cfg = ReleaseAndExcavationSupportLossIntegrationConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _bnlt_repair_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> BNLT MOVE breakaway repair OFF."""
    raw = configs.get("bnlt_move_breakaway_locomotion_repair")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        BnltMoveBreakawayLocomotionRepairConfig,
        validate_config,
    )
    cfg = BnltMoveBreakawayLocomotionRepairConfig.from_dict(
        raw if isinstance(raw, dict) else None
    )
    validate_config(cfg)
    return cfg


def _tgds_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> tangent gravity diagnostic shadow OFF."""
    raw = configs.get("tangent_gravity_diagnostic_shadow")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
        TangentGravityDiagnosticShadowConfig,
        validate_config,
    )
    cfg = TangentGravityDiagnosticShadowConfig.from_dict(raw if isinstance(raw, dict) else None)
    validate_config(cfg)
    return cfg


def _cgp_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> Policy C continuous gravitational PE OFF."""
    raw = configs.get("continuous_gravitational_pe")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.continuous_gravitational_pe import (
        ContinuousGravitationalPeConfig,
        validate_config,
    )
    cfg = ContinuousGravitationalPeConfig.from_dict(raw if isinstance(raw, dict) else None)
    validate_config(cfg)
    return cfg


def _cgpe_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> continuous gravitational PE diagnostic shadow OFF."""
    raw = configs.get("continuous_gravitational_pe_diagnostic_shadow")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
        ContinuousGravitationalPeDiagnosticShadowConfig,
        validate_config,
    )
    cfg = ContinuousGravitationalPeDiagnosticShadowConfig.from_dict(raw if isinstance(raw, dict) else None)
    validate_config(cfg)
    return cfg

def _dnls_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> diagnostic shadow OFF (old parent snapshots stay OFF)."""
    raw = configs.get("diagnostic_normal_load_shadow")
    if raw is None:
        return None
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        DiagnosticNormalLoadShadowConfig,
        validate_config,
    )
    cfg = DiagnosticNormalLoadShadowConfig.from_dict(raw if isinstance(raw, dict) else None)
    validate_config(cfg)
    return cfg


def _fogf_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("free_resource_object_ground_friction")
    if not raw:
        return None
    from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
        FreeObjectGroundFrictionConfig,
    )
    return FreeObjectGroundFrictionConfig.from_dict(raw)


def _hti_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("held_resource_object_translational_impulse_mediation")
    if not raw:
        return None
    from mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation import (
        HeldTranslationalImpulseConfig,
    )
    return HeldTranslationalImpulseConfig.from_dict(raw)


def _hfc_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("held_resource_object_foreign_body_contact")
    if not raw:
        return None
    from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
        HeldForeignBodyContactConfig,
    )
    return HeldForeignBodyContactConfig.from_dict(raw)


def _ooc_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("physical_resource_object_pair_contact")
    if not raw:
        return None
    from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
        ResourceObjectPairContactConfig,
    )
    return ResourceObjectPairContactConfig.from_dict(raw)


def _oia_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field -> None -> mechanism OFF."""
    raw = configs.get("body_resource_object_impact_acoustic_emission")
    if not raw:
        return None
    from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
        BodyObjectImpactAcousticConfig,
    )
    return BodyObjectImpactAcousticConfig.from_dict(raw)


def _fok_config_from_snapshot(configs: dict[str, Any]) -> Any:
    """Missing field (Tiktaalik / every earlier Acanthostega snapshot) -> None -> mechanism OFF."""
    raw = configs.get("free_resource_object_kinematics")
    if not raw:
        return None
    from mechanistic_mind.physical_system.free_resource_object_kinematics import FreeObjectKinematicsConfig

    return FreeObjectKinematicsConfig.from_dict(raw)


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
        elif model == "acanthostega" and config is None:
            from mechanistic_mind.model.acanthostega import acanthostega_config

            config = acanthostega_config()
        self.seed = int(seed)
        self.config = (config or PhysicalSystemConfig()).copy()
        self.tick = 0
        self.world: PlanetState
        self.body: PhysicalBodyState
        self.internal: InternalMediumState
        self.last_internal_flux: MediumFluxRecord | None = None
        self.cognition: dict[str, Any] = empty_cognitive_state(self.config.cognition)
        self.last_agent_observation: dict[str, float] | None = None
        self.last_v3_decision_tick: int | None = None
        self.last_v3_body_before: dict | None = None
        self.last_v3_body_after: dict | None = None
        self.last_selected_action: str | None = None
        self.last_motor_output: dict[str, Any] | None = None
        self.last_motor_apply: dict[str, Any] | None = None
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
        self.last_passive_reservoir_trickle: dict[str, Any] | None = None
        self.last_motor_work_ledger: dict[str, Any] | None = None
        self.last_action_work_ledger: dict[str, Any] | None = None
        self.last_work_allocation: dict[str, Any] | None = None
        self.last_force_contributions: dict[str, Any] | None = None
        self.last_head_meta: dict[str, Any] | None = None
        self.last_push_meta: dict[str, Any] | None = None
        self.last_osc_meta: dict[str, Any] | None = None
        self.last_manipulator_receipt: dict[str, Any] | None = None
        self.last_pair_receipt: dict[str, Any] | None = None
        self.last_material_transformation_receipt: dict[str, Any] | None = None
        self.last_surface_deposition_receipt: dict[str, Any] | None = None
        self.last_surface_traction_receipt: dict[str, Any] | None = None
        self.surface_traction_history: list[dict[str, Any]] = []
        self._surface_traction_pending: dict[str, Any] | None = None
        self.last_traction_experience_receipt: dict[str, Any] | None = None
        self.traction_experience_history: list[dict[str, Any]] = []
        self._traction_experience_pending: dict[str, Any] | None = None
        self._traction_experience_physical: dict[str, Any] | None = None
        self._traction_experience_closed_tick: int | None = None
        self.last_traction_prediction_receipt: dict[str, Any] | None = None
        self.traction_prediction_history: list[dict[str, Any]] = []
        self._traction_prediction_pending: dict[str, Any] | None = None
        self._traction_prediction_closed_tick: int | None = None
        self._traction_prediction_episode_index: int = 0
        self.traction_adaptation_phase: str = "UNSPECIFIED"
        self.last_surface_optical_coating_receipt: dict[str, Any] | None = None
        self.surface_optical_coating_history: list[dict[str, Any]] = []
        self.pair_aperture: float = 0.84
        self.pair_state: str = "OPEN"
        self.pair_contact: bool = False
        self.technical_id: str = "agent_0"
        self._defer_manipulator_world: bool = False
        self._prev_body_omega: float = 0.0
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
        self._forced_motor_once: dict[str, Any] | None = None
        self._tick_ctx: dict[str, Any] | None = None
        self.reset()

    def reset(self, *, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = int(seed)
        self.world = initialize_planet(self.config.planet, seed=self.seed)
        nfe = getattr(self.config, "near_field_exteroception", None)
        if nfe is not None and nfe.enabled and nfe.surface_enabled:
            from mechanistic_mind.physical_system.near_field_exteroception import (
                install_surface_on_planet,
                illumination_intensity,
                ILLUMINATION_GENERATOR_VERSION,
            )
            install_surface_on_planet(self.world, experiment_seed=self.seed, cfg=nfe)
            self.world.illumination_intensity = illumination_intensity(0, nfe)
            self.world.illumination_meta = {
                "period": int(nfe.illumination_period),
                "min": float(nfe.illumination_min),
                "max": float(nfe.illumination_max),
                "generator_version": ILLUMINATION_GENERATOR_VERSION,
                "note": "Observational only — does not drive forces/work/resources",
            }
        osc = getattr(self.config, "oscillatory_signaling", None)
        from mechanistic_mind.physical_system.local_physical_signal_transport import (
            local_physical_signal_transport_is_active as _lps_active,
        )
        if osc is not None and osc.enabled and not _lps_active(self.config):
            from mechanistic_mind.physical_system.oscillatory_signaling import ensure_osc_fields
            ensure_osc_fields(self.world, osc)
        spawn_preset_resource_objects(self.world, self.config, seed=self.seed, tick=0)
        self.body = initialize_physical_body(
            self.config.body,
            width=self.config.planet.width,
            height=self.config.planet.height,
        )
        from mechanistic_mind.physical_system.spatial_contents import (
            body_refs_for_runtime,
            multi_content_spatial_index_is_active,
            rebuild_from_world,
        )
        if multi_content_spatial_index_is_active(self.config):
            rebuild_from_world(
                self.world,
                body_refs_for_runtime(self),
                tick=0,
                reason="initialization",
                config=self.config,
            )
        from mechanistic_mind.physical_system.procedural_surface_columns import (
            ensure_surface_columns_for_runtime,
        )
        ensure_surface_columns_for_runtime(self.world, self.config, experiment_seed=self.seed)
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            ensure_state as ensure_volumetric_occupancy_for_runtime,
        )
        ensure_volumetric_occupancy_for_runtime(self.world, self.config)
        from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
            ensure_state as ensure_occupancy_support_contact_for_runtime,
        )
        ensure_occupancy_support_contact_for_runtime(self.world, self.config)
        from mechanistic_mind.physical_system.volumetric_world_material_separation import (
            ensure_state as ensure_volumetric_separation_for_runtime,
        )
        ensure_volumetric_separation_for_runtime(self.world, self.config)
        from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
            ensure_state as ensure_volumetric_reintegration_for_runtime,
        )
        ensure_volumetric_reintegration_for_runtime(self.world, self.config)
        from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
            ensure_state as ensure_vw5_bridge_for_runtime,
        )
        ensure_vw5_bridge_for_runtime(self.world, self.config)
        from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
            ensure_state as ensure_vw6_vision_for_runtime,
        )
        ensure_vw6_vision_for_runtime(self.world, self.config)
        setattr(self.world, "_physical_system_config", self.config)
        if _lps_active(self.config):
            from mechanistic_mind.physical_system.local_physical_signal_transport import (
                bind_body_ids,
                ensure_local_signal_for_runtime,
            )
            ensure_local_signal_for_runtime(self.world, self.config)
            bind_body_ids(body_refs_for_runtime(self))
            from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
                ensure_contact_acoustics_for_runtime,
            )
            ensure_contact_acoustics_for_runtime(self.world, self.config)
            from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
                ensure_body_object_impact_acoustics_for_runtime,
            )
            ensure_body_object_impact_acoustics_for_runtime(self.world, self.config)
        if getattr(self.config, "free_resource_object_kinematics", None) is not None:
            from mechanistic_mind.physical_system.free_resource_object_kinematics import (
                ensure_free_object_kinematics_for_runtime,
            )
            # Canonical passive objects are spawned FREE_STATIC with v = 0; empty effector history.
            ensure_free_object_kinematics_for_runtime(self.world, self.config)
        if getattr(self.config, "physical_body_resource_object_contact", None) is not None:
            from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
                ensure_body_object_contact_for_runtime,
            )
            ensure_body_object_contact_for_runtime(self.world, self.config)
        if getattr(self.config, "body_resource_object_contact_impulse", None) is not None:
            from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
                ensure_body_object_impulse_for_runtime,
            )
            ensure_body_object_impulse_for_runtime(self.world, self.config)
        if getattr(self.config, "body_resource_object_impact_acoustic_emission", None) is not None:
            from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
                ensure_body_object_impact_acoustics_for_runtime,
            )
            ensure_body_object_impact_acoustics_for_runtime(self.world, self.config)
        if getattr(self.config, "physical_resource_object_pair_contact", None) is not None:
            from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
                ensure_resource_object_pair_contact_for_runtime,
            )
            ensure_resource_object_pair_contact_for_runtime(self.world, self.config)
        if getattr(self.config, "resource_object_pair_contact_impulse", None) is not None:
            from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
                ensure_resource_object_pair_impulse_for_runtime,
            )
            ensure_resource_object_pair_impulse_for_runtime(self.world, self.config)
        if getattr(self.config, "resource_object_pair_impact_acoustic_emission", None) is not None:
            from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
                ensure_resource_object_pair_impact_acoustics_for_runtime,
            )
            ensure_resource_object_pair_impact_acoustics_for_runtime(self.world, self.config)
        if getattr(self.config, "held_resource_object_foreign_body_contact", None) is not None:
            from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
                ensure_held_foreign_body_contact_for_runtime,
            )
            ensure_held_foreign_body_contact_for_runtime(self.world, self.config)
        if getattr(self.config, "held_resource_object_translational_impulse_mediation", None) is not None:
            from mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation import (
                ensure_held_translational_impulse_for_runtime,
            )
            ensure_held_translational_impulse_for_runtime(self.world, self.config)
        if getattr(self.config, "effector_work_and_held_load_inertia_accounting", None) is not None:
            from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
                ensure_effector_work_held_load_for_runtime,
            )
            ensure_effector_work_held_load_for_runtime(self.world, self.config)
        if getattr(self.config, "flat_ground_gravity", None) is not None:
            from mechanistic_mind.physical_system.flat_ground_gravity import (
                ensure_flat_ground_gravity_for_runtime,
                ensure_body_vertical,
            )
            ensure_flat_ground_gravity_for_runtime(self.world, self.config)
            ensure_body_vertical(self.body, self.config)
            self.body.z = 0.0
            self.body.vz = 0.0
            self.body.grounded = True
        if getattr(self.config, "free_resource_object_ground_friction", None) is not None:
            from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
                ensure_free_object_ground_friction_for_runtime,
            )
            ensure_free_object_ground_friction_for_runtime(self.world, self.config)
        if getattr(self.config, "surface_elevation_support", None) is not None:
            from mechanistic_mind.physical_system.surface_elevation_support import (
                ensure_surface_elevation_support_for_runtime,
                apply_initial_support_placement,
                surface_elevation_support_is_active,
            )
            ensure_surface_elevation_support_for_runtime(self.world, self.config)
            if surface_elevation_support_is_active(self.config):
                apply_initial_support_placement(self.world, self.config, bodies=[self.body])
        if getattr(self.config, "body_normal_load_traction", None) is not None:
            from mechanistic_mind.physical_system.body_normal_load_traction import (
                ensure_body_normal_load_traction_for_runtime,
            )
            ensure_body_normal_load_traction_for_runtime(self.world, self.config)
        if getattr(self.config, "continuous_surface_geometry", None) is not None:
            from mechanistic_mind.physical_system.continuous_surface_geometry import (
                ensure_continuous_surface_geometry_for_runtime,
            )
            ensure_continuous_surface_geometry_for_runtime(self.world, self.config)
        if getattr(self.config, "body_static_traction_threshold", None) is not None:
            from mechanistic_mind.physical_system.body_static_traction_threshold import (
                ensure_body_static_traction_threshold_for_runtime,
            )
            ensure_body_static_traction_threshold_for_runtime(self.world, self.config)
        if getattr(self.config, "free_resource_object_static_traction_threshold", None) is not None:
            from mechanistic_mind.physical_system.free_resource_object_static_traction_threshold import (
                ensure_free_resource_object_static_traction_threshold_for_runtime,
            )
            ensure_free_resource_object_static_traction_threshold_for_runtime(self.world, self.config)
        if getattr(self.config, "radius_aware_support_points", None) is not None:
            from mechanistic_mind.physical_system.radius_aware_support_points import (
                ensure_radius_aware_support_points_for_runtime,
            )
            ensure_radius_aware_support_points_for_runtime(self.world, self.config)
        if getattr(self.config, "ses_decomposition_contract", None) is not None:
            from mechanistic_mind.physical_system.ses_decomposition_contract import (
                ensure_ses_decomposition_contract_for_runtime,
            )
            ensure_ses_decomposition_contract_for_runtime(self.world, self.config)
        if getattr(self.config, "ses_runtime_transition_classifier", None) is not None:
            from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
                ensure_ses_runtime_transition_classifier_for_runtime,
            )
            ensure_ses_runtime_transition_classifier_for_runtime(self.world, self.config)
        if getattr(self.config, "radius_aware_face_sweep", None) is not None:
            from mechanistic_mind.physical_system.radius_aware_face_sweep import (
                ensure_radius_aware_face_sweep_for_runtime,
            )
            ensure_radius_aware_face_sweep_for_runtime(self.world, self.config)
        if getattr(self.config, "diagnostic_normal_load_shadow", None) is not None:
            from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
                ensure_diagnostic_normal_load_shadow_for_runtime,
            )
            ensure_diagnostic_normal_load_shadow_for_runtime(self.world, self.config)
        if getattr(self.config, "continuous_gravitational_pe_diagnostic_shadow", None) is not None:
            from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
                ensure_continuous_gravitational_pe_diagnostic_shadow_for_runtime,
            )
            ensure_continuous_gravitational_pe_diagnostic_shadow_for_runtime(self.world, self.config)
        if getattr(self.config, "continuous_gravitational_pe", None) is not None:
            from mechanistic_mind.physical_system.continuous_gravitational_pe import (
                ensure_continuous_gravitational_pe_for_runtime,
            )
            ensure_continuous_gravitational_pe_for_runtime(self.world, self.config)
        if getattr(self.config, "tangent_gravity_diagnostic_shadow", None) is not None:
            from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
                ensure_tangent_gravity_diagnostic_shadow_for_runtime,
            )
            ensure_tangent_gravity_diagnostic_shadow_for_runtime(self.world, self.config)
        if getattr(self.config, "coherent_slope_dynamics", None) is not None:
            from mechanistic_mind.physical_system.coherent_slope_dynamics import (
                ensure_coherent_slope_dynamics_for_runtime,
            )
            ensure_coherent_slope_dynamics_for_runtime(self.world, self.config)
        if getattr(self.config, "conservative_surface_material_separation", None) is not None:
            from mechanistic_mind.physical_system.conservative_surface_material_separation import (
                ensure_surface_material_separation_for_runtime,
            )
            ensure_surface_material_separation_for_runtime(self.world, self.config)
        if getattr(self.config, "effector_terrain_contact_geometry", None) is not None:
            from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
                ensure_effector_terrain_contact_geometry_for_runtime,
            )
            ensure_effector_terrain_contact_geometry_for_runtime(self.world, self.config)
        if getattr(self.config, "manipulator_relative_world_actuation", None) is not None:
            from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
                ensure_manipulator_relative_world_actuation_for_runtime,
            )
            ensure_manipulator_relative_world_actuation_for_runtime(self.world, self.config)
        if getattr(self.config, "effector_bounded_actuator_effort", None) is not None:
            from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
                ensure_effector_bounded_actuator_effort_for_runtime,
            )
            ensure_effector_bounded_actuator_effort_for_runtime(self.world, self.config)
        if getattr(self.config, "surface_exertion_terrain_material_resistance", None) is not None:
            from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
                ensure_surface_exertion_terrain_material_resistance_for_runtime,
            )
            ensure_surface_exertion_terrain_material_resistance_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "held_resource_object_terrain_contact_geometry", None) is not None:
            from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
                ensure_held_resource_object_terrain_contact_geometry_for_runtime,
            )
            ensure_held_resource_object_terrain_contact_geometry_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "held_resource_object_terrain_mechanical_transmission", None) is not None:
            from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
                ensure_held_resource_object_terrain_mechanical_transmission_for_runtime,
            )
            ensure_held_resource_object_terrain_mechanical_transmission_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "held_mediated_surface_exertion_integration", None) is not None:
            from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
                ensure_held_mediated_surface_exertion_integration_for_runtime,
            )
            ensure_held_mediated_surface_exertion_integration_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "detached_terrain_material_initial_placement", None) is not None:
            from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
                ensure_detached_terrain_material_initial_placement_for_runtime,
            )
            ensure_detached_terrain_material_initial_placement_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "bnlt_move_breakaway_locomotion_repair", None) is not None:
            from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
                ensure_bnlt_move_breakaway_locomotion_repair_for_runtime,
            )
            ensure_bnlt_move_breakaway_locomotion_repair_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "repeated_conservative_surface_column_separation", None) is not None:
            from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
                ensure_repeated_conservative_surface_column_separation_for_runtime,
            )
            ensure_repeated_conservative_surface_column_separation_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "event_driven_crowded_placement_retry_contract", None) is not None:
            from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
                ensure_event_driven_crowded_placement_retry_contract_for_runtime,
            )
            ensure_event_driven_crowded_placement_retry_contract_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "detached_material_amount_scaled_collision_radius", None) is not None:
            from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
                ensure_detached_material_amount_scaled_collision_radius_for_runtime,
            )
            ensure_detached_material_amount_scaled_collision_radius_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "held_combine_radius_resize_transaction", None) is not None:
            from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
                ensure_held_combine_radius_resize_transaction_for_runtime,
            )
            ensure_held_combine_radius_resize_transaction_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "held_deposition_radius_shrink_transaction", None) is not None:
            from mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction import (
                ensure_held_deposition_radius_shrink_transaction_for_runtime,
            )
            ensure_held_deposition_radius_shrink_transaction_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "free_space_state_and_pe_authority_contract", None) is not None:
            from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
                ensure_free_space_state_and_pe_authority_contract_for_runtime,
            )
            ensure_free_space_state_and_pe_authority_contract_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "vertical_terrain_landing_contact_response", None) is not None:
            from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
                ensure_vertical_terrain_landing_contact_response_for_runtime,
            )
            ensure_vertical_terrain_landing_contact_response_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "vertical_impact_acoustic_emission", None) is not None:
            from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
                ensure_vertical_impact_acoustic_emission_for_runtime,
            )
            ensure_vertical_impact_acoustic_emission_for_runtime(
                self.world, self.config
            )
        if getattr(self.config, "release_and_excavation_support_loss_integration", None) is not None:
            from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
                ensure_release_and_excavation_support_loss_integration_for_runtime,
            )
            ensure_release_and_excavation_support_loss_integration_for_runtime(
                self.world, self.config
            )
        # Authoritative body refs for detached placement occupancy (never PlanetState.body).
        try:
            from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime
            self.world.detached_placement_body_refs = body_refs_for_runtime(self)
            self.world._host_runtime = self
        except Exception:
            pass
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
        self.last_passive_reservoir_trickle = None
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
        self.last_manipulator_receipt = None
        self.last_pair_receipt = None
        self.last_material_transformation_receipt = None
        self.pair_aperture = open_pair_aperture(self.config)
        self.pair_state = "OPEN"
        self.pair_contact = False
        self._sync_embodiment_dofs()
        if self.config.cognition.cognition_enabled:
            self.last_agent_observation = self.agent_observation()

    def agent_observation(self, foreign_bodies=None) -> dict[str, float]:
        sig = getattr(self.config, "physical_signal", None)
        include = bool(sig is not None and sig.enabled and sig.perception_enabled)
        nfe = getattr(self.config, "near_field_exteroception", None)
        if nfe is not None:
            nfe.resource_object_vision_enabled = object_vision_is_active(self.config)
            nfe.surface_optical_coating_enabled = physical_surface_optical_coating_is_active(self.config)
        # Arm researcher-only volumetric vision capture for this scientific pass only.
        from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
            begin_scientific_capture as _sovv_begin,
            end_scientific_capture as _sovv_end,
        )

        agent_id = str(getattr(self, "technical_id", None) or "agent_0")
        body_id = str(
            getattr(self.body, "body_id", None)
            or getattr(self, "technical_id", None)
            or "agent_0"
        )
        slot = getattr(self, "slot_index", None)
        if slot is None and agent_id.startswith("agent_"):
            try:
                slot = int(agent_id.split("_", 1)[1])
            except Exception:
                slot = 0
        run_id = str(getattr(self, "run_id", None) or getattr(self, "seed", None) or "live")
        gen = getattr(self, "runtime_generation", None)
        if gen is None:
            gen = getattr(self.world, "runtime_generation", None)
        _sovv_begin(
            self.world,
            agent_id=agent_id,
            body_id=body_id,
            agent_slot=int(slot) if slot is not None else None,
            run_id=run_id,
            runtime_generation=int(gen) if gen is not None else None,
            decision_tick=int(self.tick),
            experimenter=bool(getattr(self, "is_experimenter", False)),
        )
        try:
            from mechanistic_mind.physical_system.beta4_performance_benchmark import (
                count as _b4p_count,
                is_enabled as _b4p_obs_on,
                span as _b4p_obs_span,
            )

            def _build_obs():
                return accessible_observation(
                    world=self.world,
                    body=self.body,
                    internal=self.internal,
                    planet_config=self.config.planet,
                    body_config=self.config.body,
                    include_signal_fields=include,
                    near_field_cfg=nfe,
                    foreign_bodies=foreign_bodies,
                    vestibular_cfg=getattr(self.config, "vestibular", None),
                    neck_proprioception_cfg=getattr(self.config, "neck_proprioception", None),
                    articulated_head_cfg=getattr(self.config, "articulated_head", None),
                    oscillatory_cfg=self._osc_cfg_for_observation(),
                    orientation_meta=getattr(self, "last_orientation_meta", None),
                    prev_omega=float(getattr(self, "_prev_body_omega", 0.0) or 0.0),
                    manipulator_cfg=getattr(self.config, "single_physical_manipulator", None),
                    holder_body_id=str(getattr(self, "technical_id", None) or "agent_0"),
                    manipulator_proprioception_enabled=world_manipulators_active(self.config),
                    physical_config=self.config,
                    manipulator_runtime=self,
                )

            if _b4p_obs_on():
                with _b4p_obs_span("observation_total"):
                    with _b4p_obs_span("o4_reception", parent="observation_total"):
                        obs = _build_obs()
                    tr = getattr(self.world, "_o4_last_reception_trace", None) or {}
                    _b4p_count("o4_candidates", int(tr.get("candidate_surfaces") or 0))
                    _b4p_count("o4_los_queries", int(tr.get("los_queries") or 0))
                    _b4p_count("o4_accepted", int(tr.get("accepted") or 0))
            else:
                obs = _build_obs()
            # Finalize volumetric vision trace from exact stashed near-field sample.
            try:
                from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
                    capture_from_near_field_sample as _sovv_cap,
                )

                stash = getattr(self.world, "_sovv_last_near_field_by_body", None) or {}
                sample = stash.get(id(self.body)) if isinstance(stash, dict) else None
                if isinstance(sample, dict):
                    _sovv_cap(self.world, sample, diagnostic=False)
            except Exception:
                pass
            # Finalize receptor-grounded FPV from exact O4 (survives SNF cache hits).
            try:
                from mechanistic_mind.physical_system.organism_receptor_grounded_3d_fpv import (
                    capture_from_o4_trace as _fpv_cap,
                )

                by_body = getattr(self.world, "_o4_last_reception_by_body", None)
                full_o4 = by_body.get(id(self.body)) if isinstance(by_body, dict) else None
                if not isinstance(full_o4, dict):
                    full_o4 = getattr(self.world, "_o4_last_reception_trace", None)
                if isinstance(full_o4, dict):
                    _fpv_cap(self.world, full_o4, diagnostic=False)
            except Exception:
                pass
        finally:
            _sovv_end(self.world)
        self._drain_surface_optical_coating()
        return obs

    def _osc_cfg_for_observation(self):
        osc = getattr(self.config, "oscillatory_signaling", None)
        if getattr(self.world, "local_signal_transport", None) is not None:
            from mechanistic_mind.physical_system.local_physical_signal_transport import bind_body_ids
            from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

            if not bool(getattr(self, "_lps_parent_managed", False)):
                bind_body_ids(body_refs_for_runtime(self))
        return osc

    def _capture_selected_organism_auditory_boundary(
        self, observation: dict[str, Any] | None, decision_tick: int
    ) -> None:
        """Freeze A5 osc_l/r from the cognition-bound observation. Researcher-only."""
        agent_id = str(getattr(self, "technical_id", None) or "agent_0")
        body_id = str(
            getattr(self.body, "body_id", None)
            or getattr(self, "technical_id", None)
            or "agent_0"
        )
        run_id = str(getattr(self, "run_id", None) or getattr(self, "seed", None) or "live")
        slot = getattr(self, "slot_index", None)
        if slot is None:
            # TwoAgent sets technical_id agent_N; parse slot when possible
            if agent_id.startswith("agent_"):
                try:
                    slot = int(agent_id.split("_", 1)[1])
                except Exception:
                    slot = 0
            else:
                slot = 0
        if isinstance(observation, dict):
            # Skip if oscillatory perception path is inactive and no osc keys present.
            has_osc = any(str(k).startswith("osc_l_") or str(k).startswith("osc_r_") for k in observation)
            if has_osc:
                from mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt import (
                    capture_from_observation,
                )
                from mechanistic_mind.scientific_v3.ids import observation_id as _oid

                okey = _oid(str(run_id), int(decision_tick), agent_id)
                sav1 = capture_from_observation(
                    self.world,
                    observation=observation,
                    scientific_tick=int(decision_tick),
                    agent_id=agent_id,
                    body_id=body_id,
                    agent_slot=int(slot) if slot is not None else None,
                    run_id=str(run_id),
                    observation_key=okey,
                    config=self.config,
                    body=self.body,
                    experimenter=bool(getattr(self, "is_experimenter", False)),
                )
                # ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1 — researcher-only A3↔A5 linkage.
                # Atomic read of tick-stamped LPS auditory buffer; no LPS/phenotype recompute.
                from mechanistic_mind.physical_system.organism_auditory_transformation_trace import (
                    capture_linked_to_sav1 as _oatt_capture,
                )

                _oatt_capture(
                    self.world,
                    observation=observation,
                    scientific_tick=int(decision_tick),
                    agent_id=agent_id,
                    body_id=body_id,
                    agent_slot=int(slot) if slot is not None else None,
                    run_id=str(run_id),
                    observation_key=okey,
                    config=self.config,
                    body=self.body,
                    sav1_receipt=sav1 if isinstance(sav1, dict) else None,
                    experimenter=bool(getattr(self, "is_experimenter", False)),
                )
        # O5: finalize one researcher-only temporal alignment envelope at observation seam.
        self._finalize_sensory_modality_temporal_alignment(
            observation if isinstance(observation, dict) else None,
            int(decision_tick),
            agent_id=agent_id,
            body_id=body_id,
            run_id=run_id,
        )

    def _finalize_sensory_modality_temporal_alignment(
        self,
        observation: dict[str, Any] | None,
        observation_tick: int,
        *,
        agent_id: str,
        body_id: str,
        run_id: str,
    ) -> None:
        from mechanistic_mind.physical_system.sensory_modality_temporal_alignment import (
            finalize_alignment_envelope,
            sensory_modality_temporal_alignment_is_active,
        )

        if not sensory_modality_temporal_alignment_is_active(self.config):
            return
        gen = getattr(self, "runtime_generation", None)
        if gen is None:
            gen = getattr(self.world, "runtime_generation", None)
        finalize_alignment_envelope(
            world=self.world,
            body=self.body,
            config=self.config,
            observation=observation,
            observation_tick=int(observation_tick),
            agent_id=str(agent_id),
            body_id=str(body_id),
            run_id=str(run_id),
            runtime_generation=gen,
            runtime=self,
        )

    def _drain_surface_optical_coating(self) -> None:
        from mechanistic_mind.physical_system.physical_surface_optical_coating import HISTORY_LIMIT

        world = self.world
        rows = list(getattr(world, "_surface_optical_coating_buffer", None) or [])
        world._surface_optical_coating_buffer = []
        if not rows or not physical_surface_optical_coating_is_active(self.config):
            return
        history = self.surface_optical_coating_history
        for row in rows:
            receipt = {
                "event": "SURFACE_OPTICAL_COATING_OBSERVED",
                "tick": int(self.tick),
                "agent_id": str(getattr(self, "technical_id", None) or "agent_0"),
                "body_id": str(getattr(self.body, "body_id", None) or getattr(self, "technical_id", None) or "agent_0"),
                **row,
            }
            self.last_surface_optical_coating_receipt = receipt
            history.append(receipt)
        if len(history) > HISTORY_LIMIT:
            del history[:-HISTORY_LIMIT]

    def observation_views(self, foreign_bodies=None) -> dict[str, Any]:
        """Observer: WORLD TRUTH + AGENT OBSERVATION (separated)."""
        sig = getattr(self.config, "physical_signal", None)
        include = bool(sig is not None and sig.enabled and sig.perception_enabled)
        nfe = getattr(self.config, "near_field_exteroception", None)
        if nfe is not None:
            nfe.resource_object_vision_enabled = object_vision_is_active(self.config)
            nfe.surface_optical_coating_enabled = physical_surface_optical_coating_is_active(self.config)
        bundle = observation_bundle(
            world=self.world,
            body=self.body,
            internal=self.internal,
            planet_config=self.config.planet,
            body_config=self.config.body,
            include_signal_fields=include,
            near_field_cfg=nfe,
            foreign_bodies=foreign_bodies,
        )
        self._drain_surface_optical_coating()
        return bundle

    def cognitive_view(self) -> dict[str, Any]:
        """Researcher panel snapshot.

        Same-tick cache: a single Observer frame historically called this
        many times per agent (mind/pipeline/prospection/causal). Cognition
        does not mutate mid-capture, so reuse is exact.

        Observer/public-representation only — never caches scientific decisions.
        """
        tick = int(self.tick)
        cached = getattr(self, "_cognitive_view_cache", None)
        if isinstance(cached, tuple) and cached[0] == tick:
            self._cognitive_view_hits = int(getattr(self, "_cognitive_view_hits", 0) or 0) + 1
            return cached[1]
        view = cognition_public_view(self.cognition)
        self._cognitive_view_cache = (tick, view)
        self._cognitive_view_builds = int(getattr(self, "_cognitive_view_builds", 0) or 0) + 1
        return view

    def cognitive_view_cache_stats(self) -> dict[str, int]:
        """Observer diagnostics: same-tick public-view cache counters."""
        return {
            "builds": int(getattr(self, "_cognitive_view_builds", 0) or 0),
            "hits": int(getattr(self, "_cognitive_view_hits", 0) or 0),
            "cached_tick": int(self._cognitive_view_cache[0])
            if isinstance(getattr(self, "_cognitive_view_cache", None), tuple)
            else -1,
        }

    def reset_cognitive_view_cache_stats(self) -> None:
        self._cognitive_view_builds = 0
        self._cognitive_view_hits = 0

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
        # BODY-01: optional passive trickle after resource conversion (ordinary path).
        # Does not bypass allocate_shared_work / realize_discrete_action.
        trickle = float(getattr(self.config.deformation_work, "passive_reservoir_trickle", 0.0) or 0.0)
        if trickle > 0.0:
            w_max = float(self.config.deformation_work.reservoir_max)
            w0 = float(getattr(self.body, "mechanical_work_reservoir", 0.0) or 0.0)
            credited = min(trickle, max(0.0, w_max - w0))
            if credited > 0.0:
                self.body.mechanical_work_reservoir = min(w_max, w0 + credited)
            self.last_passive_reservoir_trickle = {
                "enabled": True,
                "source": "PASSIVE_BODY_TRICKLE",
                "before": w0,
                "credited": float(credited),
                "after": float(self.body.mechanical_work_reservoir),
                "not_experimenter_research_supply": True,
            }
        else:
            self.last_passive_reservoir_trickle = {"enabled": False, "credited": 0.0}

    def _motor_increment_mode(self, site_path: bool) -> str:
        return "acceleration" if site_path else "force"


    def _locomotor_mass_kg(self) -> float:
        """Body mass plus held-load mass when effector-work accounting is active."""
        m = float(self.config.body.mass)
        try:
            from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
                effector_work_held_load_is_active,
                locomotor_mass_with_held_load,
                record_holder_translation_charge,
            )
        except Exception:
            return m
        if not effector_work_held_load_is_active(self.config):
            return m
        try:
            from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime
            refs = body_refs_for_runtime(self)
            bid = str(refs[0][0]) if refs else str(getattr(self, "technical_id", None) or "agent_0")
        except Exception:
            bid = str(getattr(self, "technical_id", None) or "agent_0")
        info = locomotor_mass_with_held_load(
            body_mass=m,
            world=self.world,
            holder_body_id=bid,
            config=self.config,
        )
        if float(info.get("held_mass") or 0.0) > 1e-15:
            record_holder_translation_charge(
                self.world,
                self.config,
                body_id=bid,
                held_mass=float(info["held_mass"]),
                tick=int(getattr(self, "tick", 0) or 0),
            )
        return float(info.get("effective_mass") or m)

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
                mass=float(self._locomotor_mass_kg()),
                v_max=float(self.config.body.v_max),
                increment_mode=self._motor_increment_mode(site_path),
            )
            mdv = requested_delta_v(
                vx=float(self.body.vx),
                vy=float(self.body.vy),
                drive_ux=float(self.body.motor_ux),
                drive_uy=float(self.body.motor_uy),
                mass=float(self._locomotor_mass_kg()),
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
        cross = float(self._locomotor_mass_kg()) * (
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

    def _sync_embodiment_dofs(self) -> None:
        """Keep body vision flag + cognition action repertoire aligned with configs."""
        head_on = bool(getattr(self.config.articulated_head, "enabled", False))
        push_on = bool(getattr(self.config.physical_push, "enabled", False))
        osc_on = bool(getattr(getattr(self.config, "oscillatory_signaling", None), "enabled", False))
        grasp_on = bool(grasp_release_is_active(self.config))
        bilat_on = bool(bilateral_grasp_release_is_active(self.config))
        pair_on = bool(bring_together_is_active(self.config))
        merge_on = bool(material_composition_merge_is_active(self.config))
        deposit_on = bool(explicit_surface_deposition_is_active(self.config))
        from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
            manipulator_relative_world_actuation_is_active as _mrwa_on,
        )
        from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
            effector_bounded_actuator_effort_is_active as _ebae_on,
        )
        effector_z_on = bool(_mrwa_on(self.config) and _ebae_on(self.config))
        # Marker consumed by sample_near_field (legacy paths leave it unset/false).
        self.body._articulated_head_enabled = head_on  # noqa: SLF001
        self.body._osc_cfg = getattr(self.config, "oscillatory_signaling", None)  # noqa: SLF001
        if not head_on:
            self.body.head_relative_angle = 0.0
            self.body.head_omega = 0.0
            self.body.neck_motor = 0.0
        if not push_on:
            self.body.push_exertion = 0.0
        if not osc_on:
            self.body.osc_emit_remaining = 0
            self.body.osc_emit_active = 0.0
        if isinstance(self.cognition, dict):
            self.cognition["available_actions"] = list(
                available_actions(
                    articulated_head=head_on,
                    physical_push=push_on,
                    oscillatory_signaling=osc_on,
                    physical_grasp_release=grasp_on,
                    physical_bilateral_grasp_release=bilat_on,
                    physical_bilateral_bring_together=pair_on,
                    material_composition_merge=merge_on,
                    explicit_surface_deposition=deposit_on,
                    effector_relative_z=effector_z_on,
                )
            )

    def _step_articulated_head(self, *, action_work_on: bool) -> None:
        """Integrate neck DOF; optional work debit for active motor."""
        cfg = self.config.articulated_head
        motor = float(getattr(self.body, "neck_motor", 0.0) or 0.0)
        # Composite / legacy: only clear torque when this tick's motor had no neck command.
        mo = self.last_motor_output or {}
        neck_cmd = str(mo.get("neck") or "")
        selected = str(self.last_selected_action or "WAIT")
        has_neck_cmd = (neck_cmd and neck_cmd != "NONE") or selected.startswith("NECK_")
        if not has_neck_cmd:
            motor = 0.0
            self.body.neck_motor = 0.0
        meta = step_articulated_head(self.body, cfg, neck_motor=motor)
        # Optional work cost for active neck motor (same reservoir as other motors).
        if (
            cfg.enabled
            and action_work_on
            and abs(motor) > 1e-9
            and float(cfg.neck_work_cost_per_motor) > 0.0
        ):
            cost = float(cfg.neck_work_cost_per_motor) * abs(motor)
            w0 = float(getattr(self.body, "mechanical_work_reservoir", 0.0) or 0.0)
            debit = min(w0, cost)
            self.body.mechanical_work_reservoir = max(0.0, w0 - debit)
            meta["neck_work_debit"] = debit
        self.last_head_meta = meta
        if cfg.enabled and abs(motor) > 1e-9:
            self.structured_events.emit(
                "NECK_MOTOR_APPLIED",
                tick=int(self.tick),
                evidence={
                    "neck_motor": motor,
                    "head_relative_angle": meta.get("head_relative_angle"),
                    "head_omega": meta.get("head_omega"),
                    "head_world_heading": meta.get("head_world_heading"),
                    "clamped": meta.get("clamped"),
                },
            )

    def _apply_realized_motor(self, *, site_path: bool, endo_on: bool, alloc: dict[str, Any] | None) -> None:
        if not endo_on:
            self.last_motor_work_ledger = None
            return
        mw_on = bool(self.config.endogenous_motor_work.enabled)
        budget = None if (not mw_on or alloc is None) else float(alloc.get("allocated_motor") or 0.0)
        self.last_motor_work_ledger = apply_motor_realization(
            self.body,
            mass=float(self._locomotor_mass_kg()),
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

        self._sync_embodiment_dofs()
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
        # SCIENTIFIC_V3 CORE instrumentation only (no science change)
        self.last_v3_decision_tick = decision_tick
        self.last_v3_body_before = body_before
        if self.config.cognition.cognition_enabled:
            from mechanistic_mind.physical_system.beta4_performance_benchmark import (
                is_enabled as _b4p_on,
                span as _b4p_span,
            )
            from mechanistic_mind.research.tick_profiler import span as _prof_span

            if observation is not None:
                obs = observation
            else:
                obs = self.agent_observation()
            if _b4p_on():
                with _b4p_span("cognition_total", parent="begin_tick_total"):
                    with _prof_span("cognition"):
                        cognition_result = run_cognition_before_action(
                            self.cognition,
                            observation=obs,
                            tick=self.tick,
                            rng_value=_rng_unit(self.seed, self.tick),
                        )
            else:
                with _prof_span("cognition"):
                    cognition_result = run_cognition_before_action(
                        self.cognition,
                        observation=obs,
                        tick=self.tick,
                        rng_value=_rng_unit(self.seed, self.tick),
                    )
            selected = cognition_result.selected_action
            self.last_agent_observation = obs
            self.last_selected_action = selected
            self._capture_selected_organism_auditory_boundary(obs, decision_tick)
        else:
            self.last_selected_action = "WAIT"
            if observation is not None:
                self.last_agent_observation = observation
                self._capture_selected_organism_auditory_boundary(observation, decision_tick)
        self._close_traction_experience()
        self._close_traction_prediction()

        if self._forced_motor_once is not None:
            motor = CompositeMotorOutput(
                locomotion=str(self._forced_motor_once.get("locomotion") or "WAIT"),
                neck=str(self._forced_motor_once.get("neck") or "NONE"),
                oscillator=OscillatorMotorComponent.from_dict(
                    self._forced_motor_once.get("oscillator")
                ),
                push=bool(self._forced_motor_once.get("push")),
                manipulator=str(self._forced_motor_once.get("manipulator") or "NONE"),
                manipulator_left=str(self._forced_motor_once.get("manipulator_left") or "NONE"),
                manipulator_right=str(self._forced_motor_once.get("manipulator_right") or "NONE"),
                manipulator_pair=str(self._forced_motor_once.get("manipulator_pair") or "NONE"),
                apply_to_surface=bool(self._forced_motor_once.get("apply_to_surface")),
                effector_z_left=int(self._forced_motor_once.get("effector_z_left") or 0),
                effector_z_right=int(self._forced_motor_once.get("effector_z_right") or 0),
                selection_source="FORCED_COMPOSITE",
            )
            motor.legacy_token = motor.compute_legacy_token()
            selected = motor.legacy_token
            self.last_selected_action = selected
            self.last_motor_output = motor.to_dict()
            self._forced_motor_once = None
            self._forced_action_once = None
            if self.config.cognition.cognition_enabled:
                self.cognition["last_action"] = selected
                self.cognition["last_motor_output"] = motor.to_dict()
                self.cognition["last_selection"] = {
                    **(self.cognition.get("last_selection") or {}),
                    "action": selected,
                    "source": "FORCED_COMPOSITE",
                    "motor_output": motor.to_dict(),
                    "motor_schema": motor.schema,
                }
        elif self._forced_action_once is not None:
            selected = str(self._forced_action_once)
            self._forced_action_once = None
            self.last_selected_action = selected
            motor = CompositeMotorOutput.from_legacy(selected, source="FORCED_GATE")
            if bool(getattr(self.config.cognition, "composite_motor", True)):
                motor.schema = "COMPOSITE_MOTOR_V1"
            self.last_motor_output = motor.to_dict()
            if self.config.cognition.cognition_enabled:
                self.cognition["last_action"] = selected
                self.cognition["last_motor_output"] = motor.to_dict()
                self.cognition["last_selection"] = {
                    **(self.cognition.get("last_selection") or {}),
                    "action": selected,
                    "source": "FORCED_GATE",
                    "motor_output": motor.to_dict(),
                    "motor_schema": motor.schema,
                }
        else:
            # Prefer cognition motor_output when present.
            if cognition_result is not None and getattr(cognition_result, "motor_output", None):
                self.last_motor_output = dict(cognition_result.motor_output)
                motor = CompositeMotorOutput(
                    locomotion=str(self.last_motor_output.get("locomotion") or "WAIT"),
                    neck=str(self.last_motor_output.get("neck") or "NONE"),
                    oscillator=OscillatorMotorComponent.from_dict(
                        self.last_motor_output.get("oscillator")
                    ),
                    push=bool(self.last_motor_output.get("push")),
                    manipulator=str(self.last_motor_output.get("manipulator") or "NONE"),
                    manipulator_left=str(self.last_motor_output.get("manipulator_left") or "NONE"),
                    manipulator_right=str(self.last_motor_output.get("manipulator_right") or "NONE"),
                    manipulator_pair=str(self.last_motor_output.get("manipulator_pair") or "NONE"),
                    apply_to_surface=bool(self.last_motor_output.get("apply_to_surface")),
                    schema=str(self.last_motor_output.get("schema") or "COMPOSITE_MOTOR_V1"),
                    legacy_token=str(self.last_motor_output.get("legacy_token") or selected),
                    selection_source=str(
                        self.last_motor_output.get("selection_source") or "COMPOSITE"
                    ),
                    domain_sources=dict(self.last_motor_output.get("domain_sources") or {}),
                )
            elif bool(getattr(self.config.cognition, "composite_motor", True)):
                motor = self._factorized_composite_from_cognition(
                    selected=selected,
                    cognition_result=cognition_result,
                )
                self.last_motor_output = motor.to_dict()
                if isinstance(self.cognition, dict):
                    self.cognition["last_motor_output"] = motor.to_dict()
                    # Beta 3 last_action = legacy_token: MOVE first, else neck,
                    # then OSC emit/freq/amp, then PUSH.
                    token = str(motor.legacy_token or motor.compute_legacy_token())
                    if token.startswith("NECK_") or token in OSC_ACTIONS or token == "PUSH" or token in ("GRASP", "RELEASE", "LEFT_GRASP", "LEFT_RELEASE", "RIGHT_GRASP", "RIGHT_RELEASE", "APPLY_TO_SURFACE"):
                        self.cognition["last_action"] = token
            else:
                motor = CompositeMotorOutput.from_legacy(selected, source="LEGACY")
                self.last_motor_output = motor.to_dict()
                if isinstance(self.cognition, dict):
                    self.cognition["last_motor_output"] = motor.to_dict()

        composite_on = bool(getattr(self.config.cognition, "composite_motor", True))
        if composite_on:
            # Locomotion via work-accounted bridge; neck/osc/push via composite apply.
            loco = motor.locomotion if motor.locomotion not in ("NONE", "") else "WAIT"
            action_request = request_discrete_action(
                action=loco if not motor.push else (
                    # PUSH may coexist with locomotion: apply loco impulse first; push armed below.
                    loco
                ),
                vx=float(self.body.vx),
                vy=float(self.body.vy),
                mass=float(self._locomotor_mass_kg()),
                v_max=float(self.config.body.v_max),
                impulse_scale=float(self.config.discrete_action_work.impulse_scale),
                tick=int(self.tick),
            )
            action_request = self._apply_surface_traction(action_request)
            action_request = self._apply_static_traction_move_limit(action_request)
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
            self._stamp_bnlt_move_breakaway_impulse()
            self._capture_surface_traction_realization()
            # Apply neck / oscillator / push without erasing locomotion Δv.
            side = CompositeMotorOutput(
                locomotion="WAIT",
                neck=motor.neck,
                oscillator=motor.oscillator,
                push=motor.push,
                schema=motor.schema,
            )
            self.last_motor_apply = apply_composite_motor(
                self.body,
                side,
                body_config=self.config.body,
                impulse_scale=float(self.config.discrete_action_work.impulse_scale),
                oscillatory_cfg=getattr(self.config, "oscillatory_signaling", None),
            )
            self.last_motor_apply["locomotion"] = {
                "action": loco,
                "applied": bool(action_request.get("bridge_available")),
                "detail": deepcopy(self.last_action_work_ledger),
            }
            for ev in motor_control_events(motor, tick=int(self.tick)):
                self.structured_events.emit(
                    str(ev.get("type") or "MOTOR_COMPONENT_SELECTED"),
                    tick=int(self.tick),
                    evidence=ev,
                )
        else:
            action_request = request_discrete_action(
                action=selected,
                vx=float(self.body.vx),
                vy=float(self.body.vy),
                mass=float(self._locomotor_mass_kg()),
                v_max=float(self.config.body.v_max),
                impulse_scale=float(self.config.discrete_action_work.impulse_scale),
                tick=int(self.tick),
            )
            action_request = self._apply_surface_traction(action_request)
            action_request = self._apply_static_traction_move_limit(action_request)
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
            self._stamp_bnlt_move_breakaway_impulse()
            self._capture_surface_traction_realization()
            # Legacy OSC fix: apply through physical action bridge when selected.
            if str(selected).startswith("OSC_"):
                from mechanistic_mind.physical_system.actions import apply_physical_action
                apply_physical_action(
                    self.body,
                    selected,
                    body_config=self.config.body,
                    impulse_scale=float(self.config.discrete_action_work.impulse_scale),
                )
            self.last_motor_apply = {"schema": "LEGACY_SINGLE_SLOT", "action": selected}

        self.cognition["last_apply"] = {
            "action": selected,
            "motor_output": self.last_motor_output,
            "motor_apply": self.last_motor_apply,
            "applied": bool((self.last_action_work_ledger or {}).get("bridge_available", True)),
            "bridge": (self.last_action_work_ledger or {}).get("bridge"),
            "detail": deepcopy(self.last_action_work_ledger),
        }

        # Capture post-action-realization body. WAIT leaves vx/vy unchanged.
        body_after_impulse = self.body.snapshot()
        imp = (self.last_action_work_ledger or {}).get("action_dv_realized") or [0.0, 0.0]
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
            "motor_output": self.last_motor_output,
            "body_before": body_before,
            "cognition_result": cognition_result,
            "decision_tick": decision_tick,
            "alloc": alloc,
            "body_after_impulse": body_after_impulse,
            "impulse": impulse,
            "internal_before": internal_before,
        }
        return selected

    def _apply_surface_traction(self, request: dict[str, Any]) -> dict[str, Any]:
        """Scale an active MOVE request from the body-COM deposit. Identity at 1.0."""
        self._surface_traction_pending = None
        self._traction_experience_physical = None
        action = str(request.get("selected_action") or "")
        if action not in ("MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"):
            return request
        if not surface_affinity_traction_is_active(self.config):
            return request
        # THIS preset only: gate affinity MOVE traction on grounded (prior tick).
        from mechanistic_mind.physical_system.body_normal_load_traction import (
            body_normal_load_traction_is_active as _bnlt_on,
            note_affinity_move_gated_airborne,
        )
        if _bnlt_on(self.config) and not bool(getattr(self.body, "grounded", False)):
            note_affinity_move_gated_airborne(self.world)
            return request
        from mechanistic_mind.physical_system.action_work import scale_locomotor_request_before_vmax
        from mechanistic_mind.physical_system.surface_affinity_traction import plan_surface_traction

        height, width = int(self.world.T.shape[0]), int(self.world.T.shape[1])
        plan = plan_surface_traction(
            world=self.world,
            x=float(self.body.x),
            y=float(self.body.y),
            tick=int(self.tick),
            width=width,
            height=height,
        )
        multiplier = float(plan["traction_multiplier"])
        nominal = [float(v) for v in (request.get("action_dv_requested") or [0.0, 0.0])]
        if abs(multiplier - 1.0) > 1e-15:
            request = scale_locomotor_request_before_vmax(
                request,
                multiplier=multiplier,
                vx=float(self.body.vx),
                vy=float(self.body.vy),
                v_max=float(self.config.body.v_max),
            )
            nominal = [float(v) for v in (request.get("action_dv_requested") or nominal)]
        scaled = [nominal[0] * multiplier, nominal[1] * multiplier]
        if surface_traction_experience_is_active(self.config):
            from mechanistic_mind.physical_system.surface_traction_experience import note_physical

            scaled_note = [nominal[0] * multiplier, nominal[1] * multiplier]
            self._traction_experience_physical = note_physical(
                tick=int(self.tick),
                body_id=str(getattr(self, "technical_id", None) or "agent_0"),
                command=action,
                plan=plan,
                requested_dv=nominal,
                scaled_dv=scaled_note,
                after_vmax_dv=[
                    float(v) for v in (request.get("action_dv_requested_after_vmax") or [0.0, 0.0])
                ],
                velocity_before=[float(self.body.vx), float(self.body.vy)],
                position_before=[float(self.body.x), float(self.body.y)],
            )
        if plan.get("emit_receipt"):
            self._surface_traction_pending = {
                **plan,
                "selected_locomotor_command": action,
                "requested_locomotor_dv": nominal,
                "traction_scaled_dv": scaled,
                "after_vmax_dv": [float(v) for v in (request.get("action_dv_requested_after_vmax") or [0.0, 0.0])],
                "velocity_before": [float(self.body.vx), float(self.body.vy)],
                "position_before": [float(self.body.x), float(self.body.y)],
                "body_id": str(getattr(self, "technical_id", None) or "agent_0"),
                "v_max": float(self.config.body.v_max),
            }
        return request

    def _stamp_bnlt_move_breakaway_impulse(self) -> None:
        """Tick-local capacity-limited MOVE impulse for BNLT force-aware drive_accel."""
        from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
            bnlt_move_breakaway_locomotion_repair_is_active,
            clear_move_impulse_on_body,
            stamp_move_impulse_on_body,
        )

        if not bnlt_move_breakaway_locomotion_repair_is_active(self.config):
            clear_move_impulse_on_body(self.body)
            return
        led = self.last_action_work_ledger or {}
        impulse = led.get("action_impulse_realized") or [0.0, 0.0]
        dv = led.get("action_dv_realized") or [0.0, 0.0]
        stamp_move_impulse_on_body(
            self.body,
            impulse_xy=(float(impulse[0]), float(impulse[1])),
            dv_xy=(float(dv[0]), float(dv[1])),
        )

    def _apply_static_traction_move_limit(self, request: dict[str, Any]) -> dict[str, Any]:
        """G2A begin-tick: requested→limited MOVE impulse by μ_s·N·dt when grounded."""
        action = str(request.get("selected_action") or "")
        if action not in ("MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"):
            return request
        from mechanistic_mind.physical_system.body_static_traction_threshold import (
            body_static_traction_threshold_is_active,
            ensure_body_static_traction_threshold_for_runtime,
            limit_move_impulse_by_static_traction,
            mu_static_from_surface_affinity,
            note_move_limited,
        )
        from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
            sample_support_surface_affinity,
        )
        from mechanistic_mind.physical_system.body_normal_load_traction import (
            effective_normal_load_mass,
        )
        if not body_static_traction_threshold_is_active(self.config):
            return request
        st = ensure_body_static_traction_threshold_for_runtime(self.world, self.config)
        if st is None:
            return request
        grounded = bool(getattr(self.body, "grounded", False))
        # Airborne: no ground MOVE traction limit (and BNLT already gates affinity).
        if not grounded:
            return request
        height, width = int(self.world.T.shape[0]), int(self.world.T.shape[1])
        sample = sample_support_surface_affinity(
            self.world, float(self.body.x), float(self.body.y), width=width, height=height
        )
        pair = mu_static_from_surface_affinity(
            float(sample["surface_affinity"]),
            mu_min=float(st.config.mu_min),
            mu_max=float(st.config.mu_max),
            static_ratio=float(st.config.static_ratio),
        )
        mass_info = effective_normal_load_mass(
            body_mass=float(self.config.body.mass),
            world=self.world,
            holder_body_id=str(getattr(self, "technical_id", None) or "agent_0"),
            config=self.config,
        )
        m_eff = float(mass_info["m_eff"])
        from mechanistic_mind.physical_system.flat_ground_gravity import GRAVITY_ACCELERATION
        g = float(GRAVITY_ACCELERATION)
        st_fgg = getattr(self.world, "flat_ground_gravity_state", None)
        if st_fgg is not None and getattr(st_fgg, "config", None) is not None:
            g = float(getattr(st_fgg.config, "g", g))
        N = m_eff * g  # PHYSICAL flat N — diagnostic shadow must not replace
        try:
            from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
                maybe_record_body_shadow,
            )
            bid = str(getattr(self, "technical_id", None) or "agent_0")
            entity_kind = "experimenter" if bid.startswith("experimenter") else "body"
            maybe_record_body_shadow(
                self.world,
                self.config,
                body=self.body,
                body_id=bid,
                m_eff=float(m_eff),
                g=float(g),
                grounded=True,
                held_mass=float(mass_info.get("held_mass") or 0.0),
                body_mass=float(mass_info.get("body_mass") or m_eff),
                entity_kind=entity_kind,
                seam="MOVE_STATIC_CAPACITY",
            )
        except Exception:
            pass
        dv = [float(v) for v in (request.get("action_dv_requested") or [0.0, 0.0])]
        lim = limit_move_impulse_by_static_traction(
            dv[0], dv[1],
            m_eff=m_eff,
            mu_static=float(pair["mu_static"]),
            normal_load_N=N,
            grounded=True,
        )
        if lim.get("limited"):
            from mechanistic_mind.physical_system.action_work import scale_locomotor_request_before_vmax
            # Replace requested Δv with limited (scale relative to current request).
            scale = float(lim["scale"])
            request = scale_locomotor_request_before_vmax(
                request,
                multiplier=scale,
                vx=float(self.body.vx),
                vy=float(self.body.vy),
                v_max=float(self.config.body.v_max),
            )
            note_move_limited(self.world)
            request["static_traction_move_limit"] = lim
        else:
            request["static_traction_move_limit"] = lim
        return request


    def _capture_surface_traction_realization(self) -> None:
        pending = self._surface_traction_pending
        if not isinstance(pending, dict):
            return
        ledger = self.last_action_work_ledger or {}
        pending["realized_dv"] = [float(v) for v in (ledger.get("action_dv_realized") or [0.0, 0.0])]
        pending["work_request"] = float(ledger.get("action_work_requested") or 0.0)
        pending["work_realized"] = float(ledger.get("action_work_realized") or 0.0)
        pending["work_signed_realized"] = float(ledger.get("action_work_signed_realized") or 0.0)
        pending["work_negative_realized"] = float(ledger.get("action_negative_work_realized") or 0.0)
        pending["work_limited"] = bool(ledger.get("work_limited"))
        pending["reservoir_before"] = ledger.get("mechanical_work_reservoir_before")
        pending["reservoir_after"] = ledger.get("mechanical_work_reservoir_after")
        pending["velocity_after_locomotor"] = [float(self.body.vx), float(self.body.vy)]

    def _emit_surface_traction_receipt(self, body_before: dict[str, Any] | None) -> None:
        pending = self._surface_traction_pending
        self._surface_traction_pending = None
        if not isinstance(pending, dict):
            return
        from mechanistic_mind.planet.topology import toroidal_delta
        from mechanistic_mind.physical_system.surface_affinity_traction import (
            ENERGY_INTERPRETATION,
            EVENT_APPLIED,
            HISTORY_LIMIT,
        )

        height, width = int(self.world.T.shape[0]), int(self.world.T.shape[1])
        x0 = float((body_before or {}).get("x", pending["position_before"][0]))
        y0 = float((body_before or {}).get("y", pending["position_before"][1]))
        dx = float(toroidal_delta(x0, float(self.body.x), width))
        dy = float(toroidal_delta(y0, float(self.body.y), height))
        scaled = pending["traction_scaled_dv"]
        after = pending["after_vmax_dv"]
        clamped = abs(float(scaled[0]) - float(after[0])) > 1e-9 or abs(float(scaled[1]) - float(after[1])) > 1e-9
        tick = int(pending["tick"])
        body_id = str(pending["body_id"])
        receipt = {
            "event": EVENT_APPLIED,
            "tick": tick,
            "body_id": body_id,
            "agent_id": body_id,
            "selected_locomotor_command": pending["selected_locomotor_command"],
            "resolved_cell": {
                "cell_x": int(pending["cell_x"]),
                "cell_y": int(pending["cell_y"]),
                "policy": pending["cell_policy"],
            },
            "deposit_id": pending["deposit_id"],
            "deposit_created_tick": pending.get("deposit_created_tick"),
            "deposit_last_updated_tick": pending.get("deposit_last_updated_tick"),
            "deposit_eligible_this_tick": bool(pending["deposit_eligible_this_tick"]),
            "causal_latency": pending["causal_latency"],
            "deposition_event_ids": list(pending.get("deposition_event_ids") or []),
            "derivation_version": pending["derivation_version"],
            "surface_affinity": float(pending["surface_affinity"]),
            "formula_version": pending["formula_version"],
            "traction_gain": float(pending["traction_gain"]),
            "traction_min": float(pending["traction_min"]),
            "traction_max": float(pending["traction_max"]),
            "requested_locomotor_dv": list(pending["requested_locomotor_dv"]),
            "traction_multiplier": float(pending["traction_multiplier"]),
            "traction_scaled_dv": list(scaled),
            "realized_dv": list(pending.get("realized_dv") or [0.0, 0.0]),
            "v_max": float(pending["v_max"]),
            "v_max_clamped": bool(clamped),
            "work_request": pending.get("work_request"),
            "work_realized": pending.get("work_realized"),
            "work_signed_realized": pending.get("work_signed_realized"),
            "work_negative_realized": pending.get("work_negative_realized"),
            "work_limited": bool(pending.get("work_limited")),
            "reservoir_before": pending.get("reservoir_before"),
            "reservoir_after": pending.get("reservoir_after"),
            "velocity_before": list(pending["velocity_before"]),
            "velocity_after_locomotor": list(pending.get("velocity_after_locomotor") or pending["velocity_before"]),
            "velocity_after": [float(self.body.vx), float(self.body.vy)],
            "displacement_this_tick": [dx, dy],
            "causal_source": pending["causal_source"],
            "energy_interpretation": ENERGY_INTERPRETATION,
            "recipe_match": False,
            "semantic_effect": False,
            "body_effect": False,
            "material_reaction": False,
            "deposit_consumed": False,
            "deposit_mass_before": pending.get("deposit_mass"),
            "deposit_mass_after": pending.get("deposit_mass"),
            "deposit_quantity_before": pending.get("deposit_quantity"),
            "deposit_quantity_after": pending.get("deposit_quantity"),
            "researcher_only": True,
            "agent_accessible": False,
        }
        self.last_surface_traction_receipt = receipt
        history = self.surface_traction_history
        history.append(receipt)
        if len(history) > HISTORY_LIMIT:
            del history[:-HISTORY_LIMIT]
        self.structured_events.emit(EVENT_APPLIED, tick=tick, evidence=receipt)

    def _open_traction_experience_pending(self, body_before: dict[str, Any] | None) -> None:
        physical = self._traction_experience_physical
        self._traction_experience_physical = None
        if not isinstance(physical, dict) or self._traction_experience_pending is not None:
            return
        if not surface_traction_experience_is_active(self.config):
            return
        from mechanistic_mind.planet.topology import toroidal_delta
        from mechanistic_mind.physical_system.surface_affinity_traction import resolve_body_com_cell
        from mechanistic_mind.physical_system.surface_traction_experience import open_pending

        height, width = int(self.world.T.shape[0]), int(self.world.T.shape[1])
        x0 = float((physical.get("position_before") or [0.0, 0.0])[0])
        y0 = float((physical.get("position_before") or [0.0, 0.0])[1])
        dx = float(toroidal_delta(x0, float(self.body.x), width))
        dy = float(toroidal_delta(y0, float(self.body.y), height))
        cell_x, cell_y = resolve_body_com_cell(
            float(self.body.x), float(self.body.y), width=width, height=height,
        )
        ledger = self.last_action_work_ledger or {}
        realized = ledger.get("action_dv_realized") or physical.get("after_vmax_dv") or [0.0, 0.0]
        selection = {}
        if isinstance(self.cognition, dict):
            selection = self.cognition.get("last_selection") or {}
        source = str(
            selection.get("source")
            or (self.last_motor_output or {}).get("selection_source")
            or ""
        )
        self._traction_experience_pending = open_pending(
            physical,
            realized_dv=[float(realized[0]), float(realized[1])],
            velocity_after=[float(self.body.vx), float(self.body.vy)],
            position_after=[float(self.body.x), float(self.body.y)],
            displacement=[dx, dy],
            cell_after={"cell_x": int(cell_x), "cell_y": int(cell_y)},
            work_request=ledger.get("action_work_requested"),
            work_realized=ledger.get("action_work_realized"),
            selection_source=source,
        )
        _ = body_before

    def _close_traction_experience(self) -> None:
        pending = self._traction_experience_pending
        if not isinstance(pending, dict):
            return
        if not surface_traction_experience_is_active(self.config):
            self._traction_experience_pending = None
            return
        from mechanistic_mind.physical_system.surface_traction_experience import (
            EVENT_EXPERIENCE,
            HISTORY_LIMIT,
            close_pending,
        )

        delivered = bool(self.config.cognition.cognition_enabled)
        status, receipt = close_pending(
            pending,
            tick=int(self.tick),
            observation=self.last_agent_observation if delivered else None,
            cognition=self.cognition if delivered else None,
            cognition_enabled=delivered,
            last_closed_action_tick=self._traction_experience_closed_tick,
        )
        self._traction_experience_pending = None
        if status != "emit" or not isinstance(receipt, dict):
            return
        self._traction_experience_closed_tick = int(receipt["action_tick"])
        self.last_traction_experience_receipt = receipt
        history = self.traction_experience_history
        history.append(receipt)
        if len(history) > HISTORY_LIMIT:
            del history[:-HISTORY_LIMIT]
        self.structured_events.emit(
            EVENT_EXPERIENCE,
            tick=int(receipt["consequence_observation_tick"]),
            evidence=receipt,
        )

    def _open_traction_prediction_pending(self) -> None:
        experience = self._traction_experience_pending
        if not isinstance(experience, dict) or self._traction_prediction_pending is not None:
            return
        if not surface_traction_prediction_is_active(self.config):
            return
        from mechanistic_mind.physical_system.surface_traction_prediction import (
            open_pending,
            peek_issued_prediction,
        )

        ledger = self.last_action_work_ledger or {}
        motor = self.last_motor_output if isinstance(self.last_motor_output, dict) else {}
        issued = peek_issued_prediction(
            self.cognition if self.config.cognition.cognition_enabled else None,
            self.last_agent_observation,
            motor,
        )
        self._traction_prediction_pending = open_pending(
            experience,
            issued=issued,
            observation=self.last_agent_observation,
            phase=str(getattr(self, "traction_adaptation_phase", None) or "UNSPECIFIED"),
            reservoir_before=ledger.get("reservoir_before"),
            v_max=float(getattr(self.config.body, "v_max", 0.0) or 0.0),
            push=bool(motor.get("push")),
            pair_contact=bool(getattr(self, "pair_contact", False)),
            heading=float(getattr(self.body, "theta", 0.0) or 0.0),
        )

    def _close_traction_prediction(self) -> None:
        pending = self._traction_prediction_pending
        if not isinstance(pending, dict):
            return
        if not surface_traction_prediction_is_active(self.config):
            self._traction_prediction_pending = None
            return
        from mechanistic_mind.physical_system.surface_traction_prediction import (
            EVENT_ADAPTATION,
            HISTORY_LIMIT,
            close_pending,
        )

        delivered = bool(self.config.cognition.cognition_enabled)
        status, receipt = close_pending(
            pending,
            tick=int(self.tick),
            observation=self.last_agent_observation if delivered else None,
            cognition=self.cognition if delivered else None,
            cognition_enabled=delivered,
            last_closed_action_tick=self._traction_prediction_closed_tick,
            episode_index=int(self._traction_prediction_episode_index),
        )
        self._traction_prediction_pending = None
        if status != "emit" or not isinstance(receipt, dict):
            return
        self._traction_prediction_closed_tick = int(receipt["action_tick"])
        self._traction_prediction_episode_index = int(receipt["episode_index"]) + 1
        self.last_traction_prediction_receipt = receipt
        history = self.traction_prediction_history
        history.append(receipt)
        if len(history) > HISTORY_LIMIT:
            del history[:-HISTORY_LIMIT]
        self.structured_events.emit(
            EVENT_ADAPTATION,
            tick=int(receipt["consequence_observation_tick"]),
            evidence=receipt,
        )

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
        # Observational illumination cache (no force/work/resource coupling).
        nfe = getattr(self.config, "near_field_exteroception", None)
        if nfe is not None and nfe.enabled:
            from mechanistic_mind.physical_system.near_field_exteroception import illumination_intensity
            self.world.illumination_intensity = illumination_intensity(int(self.world.tick), nfe)
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
        loco_active = bool(
            str(selected).upper().startswith("MOVE")
            or abs(float(impulse[0])) + abs(float(impulse[1])) > 1e-12
        )
        loco_on = profile_is_active(self.config)
        step_physical_body(
            self.body,
            self.world,
            self.config.body,
            endogenous_motor_enabled=endo_in_dynamics,
            skip_material=site_path,
            skip_mechanical=site_path,
            locomotion_profile=getattr(self.config, "locomotion_profile", None),
            locomotion_profile_active=loco_on,
            locomotor_active=loco_active,
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
                    terrain_cfg=getattr(self.config.planet, "terrain", None),
                    ambient_cfg=getattr(self.config.planet, "ambient", None),
                    locomotor_active=(
                        str(selected).upper().startswith("MOVE")
                        or abs(float(impulse[0])) + abs(float(impulse[1])) > 1e-12
                    ),
                    locomotion_profile=getattr(self.config, "locomotion_profile", None),
                    locomotion_profile_active=profile_is_active(self.config),
                elevation_runtime_config=self.config,
                elevation_body_id=str(getattr(self, "technical_id", None) or "agent_0"),
                elevation_tick=int(self.tick),
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
                tmeta = (self.last_orientation_meta or {}).get("terrain") or {}
                if tmeta.get("enabled"):
                    force_contrib["terrain_potential"] = [
                        float(tmeta.get("fx") or 0.0),
                        float(tmeta.get("fy") or 0.0),
                    ]
                    force_contrib["terrain_extra_drag"] = float(tmeta.get("extra_drag") or 0.0)
                    force_contrib["terrain_note"] = (
                        "External channel only — never credits mechanical_work_reservoir"
                    )
            # Articulated head / neck DOF — after body θ update so relative angle is physical.
            self._step_articulated_head(action_work_on=action_work_on)
            self._step_oscillatory_signaling()
            if not orient_on:
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
            from mechanistic_mind.physical_system.body_normal_load_traction import (
                body_normal_load_traction_is_active as _bnlt_rest_on,
            )
            rest_meta = apply_ground_rest_after_self_drive(
                self.body,
                body_cfg=self.config.body,
                profile=getattr(self.config, "locomotion_profile", None),
                profile_active=profile_is_active(self.config),
                locomotor_active=(
                    str(selected).upper().startswith("MOVE")
                    or abs(float(impulse[0])) + abs(float(impulse[1])) > 1e-12
                ),
                bypass_gentle_v_stop=_bnlt_rest_on(self.config),
            )
            if rest_meta:
                force_contrib["ground_rest_after_self"] = rest_meta
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
            from mechanistic_mind.physical_system.body_normal_load_traction import (
                body_normal_load_traction_is_active as _bnlt_rest_on,
            )
            rest_meta = apply_ground_rest_after_self_drive(
                self.body,
                body_cfg=self.config.body,
                profile=getattr(self.config, "locomotion_profile", None),
                profile_active=profile_is_active(self.config),
                locomotor_active=(
                    str(selected).upper().startswith("MOVE")
                    or abs(float(impulse[0])) + abs(float(impulse[1])) > 1e-12
                ),
                bypass_gentle_v_stop=_bnlt_rest_on(self.config),
            )
            if rest_meta:
                force_contrib["ground_rest_after_self"] = rest_meta
            # Head DOF still integrates when morph|orient site path is OFF.
            self._step_articulated_head(action_work_on=action_work_on)
            self._step_oscillatory_signaling()
        self.last_force_contributions = force_contrib
        om = self.last_orientation_meta if isinstance(self.last_orientation_meta, dict) else {}
        loc_rec = om.get("locomotion") if isinstance(om, dict) else None
        if isinstance(loc_rec, dict):
            force_contrib["locomotion_profile"] = loc_rec.get("locomotion_profile")
            force_contrib["gentle_terrain_locomotion"] = loc_rec.get("gentle_terrain_locomotion")
            force_contrib["environment_force"] = loc_rec.get("environment_force")
            force_contrib["potential_force"] = loc_rec.get("potential_force")
            force_contrib["support_force"] = loc_rec.get("support_force")
            force_contrib["self_force"] = loc_rec.get("self_force")
            force_contrib["velocity_delta"] = loc_rec.get("velocity_delta")
            force_contrib["displacement"] = loc_rec.get("displacement")
        else:
            force_contrib["locomotion_profile"] = (
                "ACANTHOSTEGA_GENTLE" if profile_is_active(self.config) else "TIKTAALIK"
            )
            force_contrib["gentle_terrain_locomotion"] = bool(profile_is_active(self.config))
        self.last_force_contributions = force_contrib
        # Vestibular finite-difference memory (body-local ω only; not agent observation).
        self._prev_body_omega = float(getattr(self.body, "omega", 0.0) or 0.0)
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
        # Phase C: after horizontal CoM integrate → gravity → support → then contacts.
        from mechanistic_mind.physical_system.flat_ground_gravity import (
            flat_ground_gravity_is_active as _fgg_active,
            integrate_body_vertical,
        )
        if _fgg_active(self.config):
            integrate_body_vertical(
                self.body,
                body_id=str(getattr(self, "technical_id", None) or "agent_0"),
                body_cfg=self.config.body,
                config=self.config,
                tick=int(self.tick),
                world=self.world,
            )
            from mechanistic_mind.physical_system.radius_aware_support_points import (
                radius_aware_support_points_is_active as _rasp_on,
                step_after_body_vertical as _rasp_body,
            )
            if _rasp_on(self.config):
                _rasp_body(
                    self.world,
                    self.body,
                    body_id=str(getattr(self, "technical_id", None) or "agent_0"),
                    config=self.config,
                    tick=int(self.tick),
                )
        if not bool(getattr(self, "_defer_manipulator_world", False)):
            resolve_shared_world_manipulators([self], self.world, tick=int(self.tick))
        # Agent-accessible effector relative_z: apply selected factors via EBAE before ETC
        # so contact evaluates the final realized tip pose (Option A wiring).
        from mechanistic_mind.physical_system.beta4_performance_benchmark import (
            is_enabled as _b4p_on,
            span as _b4p_span,
        )

        if not bool(getattr(self, "_defer_manipulator_world", False)):
            if _b4p_on():
                with _b4p_span("ebae_etc", parent="physics_finish_tick_total"):
                    self._apply_agent_effector_relative_z_from_motor()
            else:
                self._apply_agent_effector_relative_z_from_motor()
        from mechanistic_mind.physical_system.spatial_contents import (
            body_refs_for_runtime,
            multi_content_spatial_index_is_active,
            reconcile_contents,
        )
        try:
            self.world.detached_placement_body_refs = body_refs_for_runtime(self)
            self.world._host_runtime = self
        except Exception:
            pass
        if multi_content_spatial_index_is_active(self.config):
            reconcile_contents(
                self.world,
                body_refs_for_runtime(self),
                tick=int(self.tick),
                reason="body_integration",
                config=self.config,
            )
        if not bool(getattr(self, "_defer_manipulator_world", False)):
            from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
                body_object_contact_is_active,
                detect_body_resource_object_contacts,
            )
            if body_object_contact_is_active(self.config):
                detect_body_resource_object_contacts(
                    self.world,
                    body_refs_for_runtime(self),
                    tick=int(self.tick),
                    config=self.config,
                )
                from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
                    body_object_impulse_is_active,
                    apply_body_object_contact_impulse,
                )
                if body_object_impulse_is_active(self.config):
                    apply_body_object_contact_impulse(
                        self.world,
                        [(bid, b, self.config.body) for bid, b in body_refs_for_runtime(self)],
                        tick=int(self.tick),
                        config=self.config,
                    )
                    from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
                        body_object_impact_acoustics_is_active,
                        process_body_object_impact_acoustics,
                    )
                    if body_object_impact_acoustics_is_active(self.config):
                        process_body_object_impact_acoustics(
                            self.world,
                            self.config,
                            emission_tick=int(self.tick),
                        )
                from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
                    resource_object_pair_contact_is_active,
                    detect_resource_object_pair_contacts,
                )
                if resource_object_pair_contact_is_active(self.config):
                    detect_resource_object_pair_contacts(
                        self.world,
                        tick=int(self.tick),
                        config=self.config,
                    )
                    from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
                        resource_object_pair_impulse_is_active,
                        apply_resource_object_pair_contact_impulse,
                    )
                    if resource_object_pair_impulse_is_active(self.config):
                        apply_resource_object_pair_contact_impulse(
                            self.world,
                            tick=int(self.tick),
                            config=self.config,
                            bodies=body_refs_for_runtime(self),
                        )
                        from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
                            resource_object_pair_impact_acoustics_is_active,
                            process_resource_object_pair_impact_acoustics,
                        )
                        if resource_object_pair_impact_acoustics_is_active(self.config):
                            process_resource_object_pair_impact_acoustics(
                                self.world,
                                self.config,
                                emission_tick=int(self.tick),
                            )
                from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
                    held_foreign_body_contact_is_active,
                    detect_held_resource_object_foreign_body_contacts,
                )
                if held_foreign_body_contact_is_active(self.config):
                    detect_held_resource_object_foreign_body_contacts(
                        self.world,
                        body_refs_for_runtime(self),
                        tick=int(self.tick),
                        config=self.config,
                    )
                    from mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation import (
                        held_translational_impulse_is_active,
                        apply_held_resource_object_translational_impulse_mediation,
                    )
                    if held_translational_impulse_is_active(self.config):
                        body_triples = [
                            (bid, b, self.config.body) for bid, b in body_refs_for_runtime(self)
                        ]
                        apply_held_resource_object_translational_impulse_mediation(
                            self.world,
                            body_triples,
                            tick=int(self.tick),
                            config=self.config,
                        )
            from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
                detect_effector_terrain_contacts,
                effector_terrain_contact_geometry_is_active,
            )
            if effector_terrain_contact_geometry_is_active(self.config):
                holders = [
                    {
                        "body_id": bid,
                        "body": b,
                        "config": self.config,
                        "runtime": self,
                    }
                    for bid, b in body_refs_for_runtime(self)
                ]
                detect_effector_terrain_contacts(
                    self.world,
                    holders,
                    tick=int(self.tick),
                    config=self.config,
                )
            from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
                detect_held_resource_object_terrain_contacts,
                held_resource_object_terrain_contact_geometry_is_active,
            )
            if held_resource_object_terrain_contact_geometry_is_active(self.config):
                holders_hotc = [
                    {
                        "body_id": bid,
                        "body": b,
                        "config": self.config,
                        "runtime": self,
                    }
                    for bid, b in body_refs_for_runtime(self)
                ]
                detect_held_resource_object_terrain_contacts(
                    self.world,
                    holders_hotc,
                    tick=int(self.tick),
                    config=self.config,
                )
        from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
            process_vertical_impact_acoustic_emission,
            vertical_impact_acoustic_emission_is_active,
        )
        if vertical_impact_acoustic_emission_is_active(self.config):
            from mechanistic_mind.physical_system.beta4_performance_benchmark import (
                is_enabled as _b4p_via_on,
                span as _b4p_via_span,
            )

            if _b4p_via_on():
                with _b4p_via_span("via", parent="physics_finish_tick_total"):
                    process_vertical_impact_acoustic_emission(
                        self.world,
                        self.config,
                        emission_tick=int(self.tick),
                    )
            else:
                process_vertical_impact_acoustic_emission(
                    self.world,
                    self.config,
                    emission_tick=int(self.tick),
                )
        self._emit_surface_traction_receipt(body_before)
        self._open_traction_experience_pending(body_before)
        self._open_traction_prediction_pending()
        self.tick += 1
        if getattr(self.world, "local_signal_transport", None) is not None and not bool(
            getattr(self, "_lps_parent_managed", False)
        ):
            # Single-body runtime: emissions of tick T and wavefront arrivals at T+1 (after pose commit).
            from mechanistic_mind.physical_system.local_physical_signal_transport import step_end_of_tick
            from mechanistic_mind.physical_system.beta4_performance_benchmark import (
                is_enabled as _b4p_lps_on,
                span as _b4p_lps_span,
            )

            def _lps_block() -> None:
                step_end_of_tick(
                    self.world,
                    self.config,
                    body_refs_for_runtime(self),
                    tick_now=int(self.tick),
                    articulated_head=bool(getattr(self.config.articulated_head, "enabled", False)),
                )
                from mechanistic_mind.physical_system.authoritative_physical_acoustic_stream_contract import (
                    sync_acoustic_stream,
                )

                sync_acoustic_stream(self.world, scientific_tick=int(self.tick))
                from mechanistic_mind.physical_system.observer_acoustic_probe import (
                    sample_observer_acoustic_probe,
                )

                sample_observer_acoustic_probe(self.world, scientific_tick=int(self.tick))

            if _b4p_lps_on():
                with _b4p_lps_span("lps", parent="physics_finish_tick_total"):
                    _lps_block()
            else:
                _lps_block()
        body_after = self.body.snapshot()
        pair_rec = getattr(self, "last_pair_receipt", None)
        if isinstance(pair_rec, dict):
            body_after = dict(body_after)
            body_after["pair"] = dict(pair_rec)
        # SCIENTIFIC_V3 CORE: post-commit snapshot for ConsequenceReceipt(T→T+1)
        self.last_v3_body_after = body_after
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
        from mechanistic_mind.physical_system.beta4_performance_benchmark import (
            is_enabled as _b4p_on,
            span as _b4p_span,
        )

        for _ in range(max(1, int(n))):
            if _b4p_on():
                with _b4p_span("scientific_tick_total"):
                    with _b4p_span("begin_tick_total", parent="scientific_tick_total"):
                        self.begin_tick()
                    with _b4p_span("physics_finish_tick_total", parent="scientific_tick_total"):
                        self.finish_tick()
                    self._maybe_auto_enable_psc()
            else:
                self.begin_tick()
                self.finish_tick()
                self._maybe_auto_enable_psc()

    def step_forced_action(self, action: str) -> None:
        """Research helper: downstream selected-action override, normal physics."""
        self._forced_action_once = str(action)
        self.step()

    def step_forced_motor(self, motor: dict[str, Any] | CompositeMotorOutput) -> None:
        """Research helper: force a composite motor vector for one tick."""
        if isinstance(motor, CompositeMotorOutput):
            self._forced_motor_once = motor.to_dict()
        else:
            self._forced_motor_once = dict(motor)
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

    def _step_oscillatory_signaling(self) -> None:
        """Deposit/propagate oscillatory band energy; sample receptors into last_osc_meta."""
        from mechanistic_mind.physical_system.oscillatory_signaling import (
            step_oscillatory_signaling,
            ensure_osc_fields,
        )
        cfg = getattr(self.config, "oscillatory_signaling", None)
        if cfg is None or not cfg.enabled:
            self.last_osc_meta = {"enabled": False}
            return
        if getattr(self.world, "local_signal_transport", None) is not None:
            # Acanthostega single channel: OSC_EMIT is handled by local physical signal transport
            # (end-of-tick emission + finite-speed wavefront); no OSC_BANDS diffusion field here.
            self.last_osc_meta = {"enabled": True, "transport": "LOCAL_PHYSICAL_SIGNAL_TRANSPORT_V1"}
            return
        ensure_osc_fields(self.world, cfg)
        head_on = bool(getattr(self.config.articulated_head, "enabled", False))
        self.last_osc_meta = step_oscillatory_signaling(
            self.world,
            [self.body],
            cfg,
            tick=int(self.tick),
            articulated_head=head_on,
            body_ids=["agent_0"],
            slots=[0],
        )

    def _apply_agent_effector_relative_z_from_motor(
        self, *, actuation_tick: int | None = None
    ) -> dict[str, Any] | None:
        """Realize COMPOSITE_MOTOR_V1 effector_z_* factors via existing EBAE (one request/hand/tick).

        UP (+1) → +max_delta_z_per_tick (raises tip). DOWN (−1) → −rate (lowers tip).
        NONE (0) → no request. Does not bypass EBAE / invent work.
        """
        from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
            DEFAULT_MAX_DELTA_Z_PER_TICK,
            manipulator_relative_world_actuation_is_active,
        )
        from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
            effector_bounded_actuator_effort_is_active,
            request_actuated_relative_displacement,
        )

        mo = self.last_motor_output if isinstance(self.last_motor_output, dict) else {}
        zl = int(mo.get("effector_z_left") or 0)
        zr = int(mo.get("effector_z_right") or 0)
        # Clamp to ternary domain (legacy / corrupt dicts → NONE).
        if zl not in (-1, 0, 1):
            zl = 0
        if zr not in (-1, 0, 1):
            zr = 0
        if zl == 0 and zr == 0:
            self.last_agent_effector_z_actuation = {
                "tick": int(self.tick) if actuation_tick is None else int(actuation_tick),
                "left": None,
                "right": None,
                "status": "NONE",
            }
            return self.last_agent_effector_z_actuation
        if not (
            manipulator_relative_world_actuation_is_active(self.config)
            and effector_bounded_actuator_effort_is_active(self.config)
        ):
            self.last_agent_effector_z_actuation = {
                "tick": int(self.tick) if actuation_tick is None else int(actuation_tick),
                "left": None,
                "right": None,
                "status": "CAPABILITY_OFF",
            }
            return self.last_agent_effector_z_actuation

        mrwa_cfg = getattr(self.config, "manipulator_relative_world_actuation", None)
        rate = float(getattr(mrwa_cfg, "max_delta_z_per_tick", DEFAULT_MAX_DELTA_Z_PER_TICK))
        # Authoritative body_id matches MRWA/ETC keys (body_refs), not technical_id alone.
        try:
            from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

            refs = body_refs_for_runtime(self)
            body_id = str(refs[0][0]) if refs else str(
                getattr(self.body, "body_id", None)
                or getattr(self, "technical_id", None)
                or "agent_0"
            )
        except Exception:
            body_id = str(
                getattr(self.body, "body_id", None)
                or getattr(self, "technical_id", None)
                or "agent_0"
            )
        if actuation_tick is not None:
            act_tick = int(actuation_tick)
        else:
            ctx = getattr(self, "_tick_ctx", None)
            if isinstance(ctx, dict) and ctx.get("decision_tick") is not None:
                act_tick = int(ctx["decision_tick"])
            else:
                act_tick = int(self.tick)

        receipts: dict[str, Any] = {"tick": act_tick, "status": "APPLIED"}
        # Deterministic hand order: LEFT then RIGHT (no id()-dependent physics).
        for hand, factor in (("LEFT", zl), ("RIGHT", zr)):
            if factor == 0:
                receipts[hand.lower()] = None
                continue
            req = float(factor) * rate
            rec = request_actuated_relative_displacement(
                self.world,
                config=self.config,
                body=self.body,
                body_id=body_id,
                effector_id=hand,
                requested_delta_z=req,
                tick=act_tick,
                runtime=self,
            )
            receipts[hand.lower()] = rec
        self.last_agent_effector_z_actuation = receipts
        return receipts

    def _factorized_composite_from_cognition(
        self,
        *,
        selected: str,
        cognition_result: Any,
    ) -> CompositeMotorOutput:
        """LOCO_FACTORIZED: PSC/cognition choose locomotion; same cycle factorizes side channels.

        OSC / neck / push are not compose candidates. They are resolved here from the
        runtime mechanism-aligned repertoire written by ``_sync_embodiment_dofs``.
        """
        head_on = bool(getattr(self.config.articulated_head, "enabled", False))
        push_on = bool(getattr(self.config.physical_push, "enabled", False))
        osc_on = bool(getattr(getattr(self.config, "oscillatory_signaling", None), "enabled", False))
        grasp_on = bool(grasp_release_is_active(self.config))
        bilat_on = bool(bilateral_grasp_release_is_active(self.config))
        pair_on = bool(bring_together_is_active(self.config))
        merge_on = bool(material_composition_merge_is_active(self.config))
        deposit_on = bool(explicit_surface_deposition_is_active(self.config))
        from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
            manipulator_relative_world_actuation_is_active as _mrwa_on,
        )
        from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
            effector_bounded_actuator_effort_is_active as _ebae_on,
        )
        effector_z_on = bool(_mrwa_on(self.config) and _ebae_on(self.config))
        avail: list[str] = []
        if isinstance(self.cognition, dict):
            avail = [str(a) for a in (self.cognition.get("available_actions") or [])]
        if not avail:
            avail = list(
                available_actions(
                    articulated_head=head_on,
                    physical_push=push_on,
                    oscillatory_signaling=osc_on,
                    physical_grasp_release=grasp_on,
                    physical_bilateral_grasp_release=bilat_on,
                    physical_bilateral_bring_together=pair_on,
                    material_composition_merge=merge_on,
                    explicit_surface_deposition=deposit_on,
                    effector_relative_z=effector_z_on,
                )
            )
        pred: list[dict[str, Any]] = []
        if cognition_result is not None:
            pred = list(getattr(cognition_result, "predictions", None) or [])
        selected_s = str(selected or "WAIT")
        loco = selected_s
        primary_manip = "NONE"
        primary_left = "NONE"
        primary_right = "NONE"
        primary_pair = "NONE"
        if selected_s in ("GRASP", "RELEASE") and grasp_on:
            primary_manip = selected_s
            loco = "WAIT"
        elif selected_s in ("LEFT_GRASP", "LEFT_RELEASE") and bilat_on:
            primary_left = selected_s.split("_", 1)[1]
            loco = "WAIT"
        elif selected_s in ("RIGHT_GRASP", "RIGHT_RELEASE") and bilat_on:
            primary_right = selected_s.split("_", 1)[1]
            loco = "WAIT"
        elif selected_s in ("BRING_TOGETHER", "SEPARATE", "COMBINE") and pair_on and (selected_s != "COMBINE" or merge_on):
            primary_pair = selected_s
            loco = "WAIT"
        elif selected_s == "APPLY_TO_SURFACE" and deposit_on:
            loco = "WAIT"
        elif not (loco == "WAIT" or loco.startswith("MOVE:")):
            loco = CompositeMotorOutput.from_legacy(loco, source="LEGACY").locomotion
        bilat_extra: dict[str, str] = {}
        effector_z_extra: dict[str, Any] = {}
        neck, neck_src, osc, osc_src, push, push_src, manip, manip_src = select_factorized_side_channels(
            available=avail,
            predictions=pred,
            rng_value=_rng_unit(self.seed, self.tick),
            articulated_head=head_on,
            oscillatory=osc_on,
            physical_push=push_on,
            physical_grasp_release=grasp_on,
            bilateral_grasp_release=bilat_on,
            bilateral_bring_together=pair_on,
            bilateral_out=bilat_extra,
            effector_relative_z=effector_z_on,
            effector_z_out=effector_z_extra,
        )
        if primary_manip != "NONE":
            manip, manip_src = primary_manip, "COGNITION_PRIMARY"
        left = str(bilat_extra.get("manipulator_left") or "NONE")
        left_src = str(bilat_extra.get("manipulator_left_source") or "UNAVAILABLE")
        right = str(bilat_extra.get("manipulator_right") or "NONE")
        right_src = str(bilat_extra.get("manipulator_right_source") or "UNAVAILABLE")
        pair = str(bilat_extra.get("manipulator_pair") or "NONE")
        pair_src = str(bilat_extra.get("manipulator_pair_source") or "UNAVAILABLE")
        if primary_left != "NONE":
            left, left_src = primary_left, "COGNITION_PRIMARY"
        if primary_right != "NONE":
            right, right_src = primary_right, "COGNITION_PRIMARY"
        if primary_pair != "NONE":
            pair, pair_src = primary_pair, "COGNITION_PRIMARY"
        src = "COGNITION"
        if cognition_result is not None:
            src = str(getattr(cognition_result, "selection_source", None) or src)
        return build_composite_from_factorized(
            locomotion=loco,
            loco_source=src,
            neck=neck,
            neck_source=neck_src,
            osc=osc,
            osc_source=osc_src,
            push=push,
            push_source=push_src,
            manipulator=manip,
            manipulator_source=manip_src,
            manipulator_left=left,
            manipulator_left_source=left_src,
            manipulator_right=right,
            manipulator_right_source=right_src,
            manipulator_pair=pair,
            manipulator_pair_source=pair_src,
            apply_to_surface=selected_s == "APPLY_TO_SURFACE" and deposit_on,
            apply_to_surface_source="COGNITION_PRIMARY" if selected_s == "APPLY_TO_SURFACE" and deposit_on else "UNAVAILABLE",
            effector_z_left=int(effector_z_extra.get("effector_z_left") or 0),
            effector_z_left_source=str(effector_z_extra.get("effector_z_left_source") or "UNAVAILABLE"),
            effector_z_right=int(effector_z_extra.get("effector_z_right") or 0),
            effector_z_right_source=str(effector_z_extra.get("effector_z_right_source") or "UNAVAILABLE"),
        )

    def mechanisms(self) -> dict[str, Any]:
        return mechanism_snapshot(self.config)

    def set_mechanism(self, mechanism_id: str, enabled: bool) -> dict[str, Any]:
        nfe = getattr(self.config, "near_field_exteroception", None)
        if mechanism_id == "illumination_cycle" and not bool(enabled) and nfe is not None:
            # Freeze at current physical intensity before disabling dynamics.
            from mechanistic_mind.physical_system.near_field_exteroception import illumination_intensity
            cur = getattr(self.world, "illumination_intensity", None)
            if cur is None:
                cur = illumination_intensity(int(self.world.tick), nfe)
            nfe.illumination_frozen = float(cur)
        snap = set_mechanism(self.config, mechanism_id, enabled)
        self._sync_embodiment_dofs()
        if mechanism_id == "experimental_physical_signal":
            from mechanistic_mind.physical_system.physical_signal import clear_fields, ensure_fields
            if bool(enabled):
                ensure_fields(self.world)
            else:
                clear_fields(self.world)
        if mechanism_id == "oscillatory_signaling":
            from mechanistic_mind.physical_system.oscillatory_signaling import (
                clear_osc_fields,
                ensure_osc_fields,
            )
            osc = getattr(self.config, "oscillatory_signaling", None)
            if getattr(self.world, "local_signal_transport", None) is not None:
                clear_osc_fields(self.world)
            elif bool(enabled) and osc is not None:
                ensure_osc_fields(self.world, osc)
            else:
                clear_osc_fields(self.world)
        if mechanism_id == "local_physical_signal_transport":
            from mechanistic_mind.physical_system.local_physical_signal_transport import (
                bind_body_ids,
                ensure_local_signal_for_runtime,
            )
            from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

            ensure_local_signal_for_runtime(self.world, self.config)
            if getattr(self.world, "local_signal_transport", None) is not None:
                bind_body_ids(body_refs_for_runtime(self))
        if mechanism_id in ("local_physical_signal_transport", "physical_contact_acoustic_emission"):
            from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
                ensure_contact_acoustics_for_runtime,
            )
            ensure_contact_acoustics_for_runtime(self.world, self.config)
        if mechanism_id == "free_resource_object_kinematics":
            from mechanistic_mind.physical_system.free_resource_object_kinematics import (
                ensure_free_object_kinematics_for_runtime,
            )
            ensure_free_object_kinematics_for_runtime(self.world, self.config)
        if mechanism_id == "physical_resource_object_pair_contact":
            from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
                ensure_resource_object_pair_contact_for_runtime,
            )
            ensure_resource_object_pair_contact_for_runtime(self.world, self.config)
        if mechanism_id == "resource_object_pair_contact_impulse":
            from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
                ensure_resource_object_pair_impulse_for_runtime,
            )
            ensure_resource_object_pair_impulse_for_runtime(self.world, self.config)
        if mechanism_id == "resource_object_pair_impact_acoustic_emission":
            from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
                ensure_resource_object_pair_impact_acoustics_for_runtime,
            )
            ensure_resource_object_pair_impact_acoustics_for_runtime(self.world, self.config)
        if mechanism_id == "physical_body_resource_object_contact":
            from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
                ensure_body_object_contact_for_runtime,
            )
            ensure_body_object_contact_for_runtime(self.world, self.config)
        if mechanism_id == "body_resource_object_contact_impulse":
            from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
                ensure_body_object_impulse_for_runtime,
            )
            ensure_body_object_impulse_for_runtime(self.world, self.config)
        if mechanism_id in (
            "local_physical_signal_transport",
            "body_resource_object_impact_acoustic_emission",
            "physical_contact_acoustic_emission",
            "resource_object_pair_impact_acoustic_emission",
        ):
            from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
                ensure_body_object_impact_acoustics_for_runtime,
            )
            ensure_body_object_impact_acoustics_for_runtime(self.world, self.config)
            from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
                ensure_resource_object_pair_impact_acoustics_for_runtime,
            )
            ensure_resource_object_pair_impact_acoustics_for_runtime(self.world, self.config)
        if mechanism_id in ("physical_near_field_vision", "illumination_cycle"):
            nfe = getattr(self.config, "near_field_exteroception", None)
            if nfe is not None and nfe.enabled and nfe.surface_enabled:
                if getattr(self.world, "surface_response", None) is None:
                    from mechanistic_mind.physical_system.near_field_exteroception import (
                        install_surface_on_planet,
                        illumination_intensity,
                        ILLUMINATION_GENERATOR_VERSION,
                    )
                    install_surface_on_planet(self.world, experiment_seed=self.seed, cfg=nfe)
                    if getattr(self.world, "illumination_intensity", None) is None:
                        self.world.illumination_intensity = illumination_intensity(int(self.world.tick), nfe)
                        self.world.illumination_meta = {
                            "period": int(nfe.illumination_period),
                            "min": float(nfe.illumination_min),
                            "max": float(nfe.illumination_max),
                            "generator_version": ILLUMINATION_GENERATOR_VERSION,
                            "note": "Observational only — does not drive forces/work/resources",
                        }
            if nfe is not None and nfe.enabled:
                from mechanistic_mind.physical_system.near_field_exteroception import illumination_intensity
                self.world.illumination_intensity = illumination_intensity(int(self.world.tick), nfe)
        # Keep the cognition store's config copy aligned with live toggles.
        if isinstance(self.cognition, dict):
            self.cognition["config"] = self.config.cognition.to_dict()
            # Keep SMC store enable flag aligned with live mechanism toggles (no reset).
            _smc = self.cognition.get("sensorimotor_consequence")
            if isinstance(_smc, dict):
                _smc["enabled"] = bool(getattr(self.config.cognition, "sensorimotor_consequence_model", False))
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
            cpo_st = self.cognition.get("contextual_organization")
            if isinstance(cpo_st, dict):
                cpo_st["enabled"] = bool(getattr(self.config.cognition, "contextual_predictive_organization", False))
                cpo_st["ablate_higher_order"] = bool(getattr(self.config.cognition, "contextual_predictive_organization_ablate", False))
                cpo_st["ablate_predictive_use"] = bool(getattr(self.config.cognition, "contextual_predictive_organization_ablate", False))
                cpo_st["shuffle_members"] = bool(getattr(self.config.cognition, "contextual_predictive_organization_shuffle", False))
            cgp_st = self.cognition.get("context_grounded_prospection")
            if isinstance(cgp_st, dict):
                cgp_st["enabled"] = bool(getattr(self.config.cognition, "context_grounded_prospection", False))
                cgp_st["ablate_composition"] = bool(getattr(self.config.cognition, "context_grounded_prospection_ablate", False))
                cgp_st["shuffle_relations"] = bool(getattr(self.config.cognition, "context_grounded_prospection_shuffle", False))
            ppc_st = self.cognition.get("persistent_prospective_control")
            if isinstance(ppc_st, dict):
                ppc_st["enabled"] = bool(getattr(self.config.cognition, "persistent_prospective_control", False))
                ppc_st["ablate_persistence"] = bool(getattr(self.config.cognition, "persistent_prospective_control_ablate", False))
                ppc_st["ablate_motor_chunks"] = bool(getattr(self.config.cognition, "persistent_prospective_control_ablate_chunks", False))
        return snap

    def set_psc_motor_resolution(self, mode: str) -> dict[str, Any]:
        """Set experimental PSC motor resolution without resetting history/SMC/body.

        Default / unknown → LOCO_FACTORIZED. OBSERVED_COMPOSITE is experimental.
        """
        from mechanistic_mind.physical_system import observed_composite_psc as ocpsc
        old = ocpsc.normalize_mode(getattr(self.config.cognition, "psc_motor_resolution", ocpsc.MODE_LOCO))
        new = ocpsc.normalize_mode(mode)
        self.config.cognition.psc_motor_resolution = new
        if isinstance(self.cognition, dict):
            self.cognition["config"] = self.config.cognition.to_dict()
            hist = self.cognition.setdefault("config_history", [])
            if isinstance(hist, list):
                hist.append({
                    "tick": int(self.tick),
                    "field": "psc_motor_resolution",
                    "old": old,
                    "new": new,
                    "history_reset": False,
                    "cognition_reset": False,
                    "smc_reset": False,
                    "body_reset": False,
                    "experimental": new == ocpsc.MODE_OBSERVED,
                })
                if len(hist) > 64:
                    del hist[:-64]
        return {
            "accepted": True,
            "old": old,
            "new": new,
            "psc_motor_resolution": new,
            "experimental": new == ocpsc.MODE_OBSERVED,
            "history_reset": False,
            "cognition_reset": False,
            "smc_reset": False,
            "body_reset": False,
            "noop": old == new,
        }

    def set_vision_radius(self, radius: int) -> dict[str, Any]:
        """LIVE Moore candidate radius {1,2,3}. Does not reset world/cognition/RNG."""
        from mechanistic_mind.physical_system.near_field_exteroception import (
            DEFAULT_VISION_RADIUS,
            clamp_vision_radius,
            moore_max_candidates,
        )

        nfe = getattr(self.config, "near_field_exteroception", None)
        if nfe is None:
            return {
                "accepted": False,
                "reason": "near_field_exteroception absent",
                "radius": DEFAULT_VISION_RADIUS,
            }
        old = clamp_vision_radius(getattr(nfe, "radius", DEFAULT_VISION_RADIUS))
        new = clamp_vision_radius(radius)
        nfe.radius = new
        return {
            "accepted": True,
            "old": old,
            "new": new,
            "radius": new,
            "max_candidates": moore_max_candidates(new),
            "noop": old == new,
        }

    def set_visual_surface_discrimination(self, mode: str) -> dict[str, Any]:
        """LIVE OFF/LOW/RICH. Does not reset world/cognition/history."""
        from mechanistic_mind.physical_system.near_field_exteroception import (
            clamp_surface_discrimination,
            install_surface_optical_on_planet,
            surface_observation_keys,
        )

        nfe = getattr(self.config, "near_field_exteroception", None)
        if nfe is None:
            return {"accepted": False, "reason": "near_field_exteroception absent"}
        old = clamp_surface_discrimination(getattr(nfe, "visual_surface_discrimination", "OFF"))
        new = clamp_surface_discrimination(mode)
        nfe.visual_surface_discrimination = new
        if new != "OFF" and nfe.enabled and nfe.surface_enabled:
            install_surface_optical_on_planet(
                self.world, experiment_seed=self.seed, cfg=nfe
            )
        return {
            "accepted": True,
            "old": old,
            "new": new,
            "keys": list(surface_observation_keys(new)),
            "noop": old == new,
        }

    def set_optical_mapping(self, mode: str, *, reinstall: bool = True) -> dict[str, Any]:
        """Set WORLD optical mapping. Regenerates optical tensor when mapping changes.

        Does not reset tick, cognition, or history. Agent-accessible surface_c* may change
        because WORLD appearance changed. Not a fifth semantic mode.
        """
        from mechanistic_mind.physical_system.near_field_exteroception import (
            clamp_optical_mapping,
            install_surface_optical_on_planet,
        )

        nfe = getattr(self.config, "near_field_exteroception", None)
        if nfe is None:
            return {"accepted": False, "reason": "near_field_exteroception absent"}
        old = clamp_optical_mapping(getattr(nfe, "optical_mapping", "INDEPENDENT"))
        new = clamp_optical_mapping(mode)
        nfe.optical_mapping = new
        regenerated = False
        if reinstall and (old != new or getattr(self.world, "surface_optical", None) is None):
            install_surface_optical_on_planet(
                self.world, experiment_seed=self.seed, cfg=nfe, force=True
            )
            regenerated = True
        return {
            "accepted": True,
            "old": old,
            "new": new,
            "noop": old == new and not regenerated,
            "world_optical_regenerated": regenerated,
            "requires_world_reset": False,
            "history_reset": False,
            "note": (
                "WORLD optical appearance regenerated from deterministic seed namespaces. "
                "Cognition code unchanged. Accessible surface_c* follow the new WORLD field."
            ),
        }

    def set_spatial_vision(self, mode: str, *, n_sectors: int | None = None) -> dict[str, Any]:
        """LEGACY | ANGULAR | OCCLUSION | TEMPORAL_SPATIAL. No world/history reset."""
        from mechanistic_mind.physical_system.near_field_exteroception import (
            clamp_spatial_sectors,
            clamp_spatial_vision,
            spatial_observation_keys,
            spatial_vision_uses_extra_bins,
        )

        nfe = getattr(self.config, "near_field_exteroception", None)
        if nfe is None:
            return {"accepted": False, "reason": "near_field_exteroception absent"}
        old = clamp_spatial_vision(getattr(nfe, "spatial_vision", "LEGACY"))
        new = clamp_spatial_vision(mode)
        nfe.spatial_vision = new
        if n_sectors is not None:
            nfe.spatial_sectors = clamp_spatial_sectors(n_sectors)
        n_sec = int(getattr(nfe, "n_spatial_sectors", 5))
        cog = self.config.cognition
        fam = dict(getattr(cog, "sensorimotor_consequence_families", None) or {})
        fam["spatial_visual"] = bool(spatial_vision_uses_extra_bins(new))
        cog.sensorimotor_consequence_families = fam
        if hasattr(self, "cognition") and isinstance(self.cognition, dict):
            cfgd = self.cognition.get("config")
            if isinstance(cfgd, dict):
                cfgd["sensorimotor_consequence_families"] = dict(fam)
            smc_store = self.cognition.get("sensorimotor_consequence")
            if isinstance(smc_store, dict):
                from mechanistic_mind.physical_system import sensorimotor_consequence as smc
                smc.set_families(smc_store, spatial_visual=bool(fam["spatial_visual"]))
        return {
            "accepted": True,
            "old": old,
            "new": new,
            "spatial_sectors": n_sec,
            "keys": list(spatial_observation_keys(
                spatial_mode=new,
                discrimination=getattr(nfe, "visual_surface_discrimination", "OFF"),
                n_sectors=n_sec,
            )),
            "history_reset": False,
            "noop": old == new,
        }

    def set_psc_off_ticks(self, value: int | None) -> dict[str, Any]:
        """MANUAL (None) or auto-ON at tick >= N without history reset."""
        cog = self.config.cognition
        old = getattr(cog, "psc_off_ticks", None)
        if value is None:
            cog.psc_off_ticks = None
        else:
            cog.psc_off_ticks = max(0, int(value))
        if hasattr(self, "cognition") and isinstance(self.cognition, dict):
            cfgd = self.cognition.get("config")
            if isinstance(cfgd, dict):
                cfgd["psc_off_ticks"] = cog.psc_off_ticks
        return {
            "accepted": True,
            "old": old,
            "new": cog.psc_off_ticks,
            "schedule": "MANUAL" if cog.psc_off_ticks is None else int(cog.psc_off_ticks),
            "history_reset": False,
            "psc_auto_activated": bool(getattr(self, "_psc_auto_activated", False)),
        }

    def _maybe_auto_enable_psc(self) -> dict[str, Any] | None:
        """Deterministic tick-boundary PSC ON without resetting biography.

        Validation / developmental schedule contract (when psc_off_ticks=N):
        at tick >= N, exactly once: enable scenario competition AND open SMC
        withhold (sensorimotor_consequence_withhold_from_psc=False). These are
        not synonymous; both are required. History is preserved.
        """
        n = getattr(self.config.cognition, "psc_off_ticks", None)
        if n is None:
            return None
        try:
            threshold = int(n)
        except (TypeError, ValueError):
            return None
        if getattr(self, "_psc_auto_activated", False):
            return None
        if int(self.tick) < threshold:
            return None
        snap = self.set_mechanism("prospective_scenario_competition", True)
        cog = self.config.cognition
        withhold_was = bool(getattr(cog, "sensorimotor_consequence_withhold_from_psc", True))
        cog.sensorimotor_consequence_withhold_from_psc = False
        if hasattr(self, "cognition") and isinstance(self.cognition, dict):
            cfgd = self.cognition.get("config")
            if isinstance(cfgd, dict):
                cfgd["sensorimotor_consequence_withhold_from_psc"] = False
                cfgd["prospective_selection"] = str(
                    getattr(cog, "prospective_selection", "") or ""
                )
        self._psc_auto_activated = True
        tick_i = int(self.tick)
        event = {
            "kind": "PSC_ACTIVATION",
            "tick": tick_i,
            "mode": str(getattr(cog, "psc_motor_resolution", "") or ""),
            "history_preserved": True,
            "competition_enabled": True,
            "withhold_opened": True,
            "withhold_was": withhold_was,
            "psc_off_ticks": threshold,
        }
        withhold_receipt = {
            "kind": "SMC_WITHHOLD_OPEN",
            "tick": tick_i,
            "sensorimotor_consequence_withhold_from_psc": False,
            "withhold_was": withhold_was,
            "history_preserved": True,
            "paired_psc_activation": True,
            "psc_off_ticks": threshold,
        }
        self._psc_activation = event
        self._psc_withhold_open = withhold_receipt
        emit = getattr(getattr(self, "structured_events", None), "emit", None)
        if callable(emit):
            try:
                emit("PSC_ACTIVATION", dict(event))
                emit("SMC_WITHHOLD_OPEN", dict(withhold_receipt))
            except Exception:
                pass
        return {
            "mechanism": snap,
            "event": event,
            "withhold_receipt": withhold_receipt,
        }

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
        # Counterfactual soft-match probe is Observer-only and O(actions × store).
        # Run it only when the receipt is sampled into the decision trace (or when
        # ACTION TRACE is explicitly enabled every tick). Unsampled ticks keep a
        # cheap stub so last_decision_receipt remains populated without a second
        # full prospective scan.
        if sample or (self.action_trace_enabled and mode == "every_1"):
            receipt["counterfactual"] = counterfactual_candidate_probe(
                store=self.cognition["prospection"],
                compression=self.cognition["compression"],
                observation=result.observation,
                actions=list(result.actions or []),
            )
        else:
            receipt["counterfactual"] = {
                "status": "DEFERRED",
                "per_action": [],
                "note": "Diagnostic only; computed on sampled decision-trace ticks",
            }
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
        from mechanistic_mind.model.lines import identity_for_config

        return identity_for_config(self.config, seed=self.seed, tick=self.tick)

    def snapshot(self, *, persist: bool = False) -> dict[str, Any]:
        """Complete causal state needed to continue this deterministic history.

        persist=False (default, public API): detach cognition so later ``step()``
        and JSON prep cannot mutate this dict.

        persist=True (Save & Stop): alias live canonical cognition. The encoder
        must not mutate it. Caller must not step the runtime while dumping.
        """
        if persist:
            cognition = self.cognition
            last_obs = self.last_agent_observation
            last_motor = self.last_motor_output
        else:
            cognition = deepcopy(self.cognition)
            last_obs = deepcopy(self.last_agent_observation)
            last_motor = deepcopy(self.last_motor_output)
        payload = {
            "schema": "mm.physical_system.snapshot.v2",
            "tick": self.tick,
            "seed": self.seed,
            "model": self.model_identity(),
            "config": {
                "ecology_preset": getattr(self.config, "ecology_preset", "CURRENT") or "CURRENT",
                "planet": self.config.planet.to_dict(),
                "body": self.config.body.to_dict(),
                "internal": self.config.internal.to_dict(),
                "endogenous_motor": self.config.endogenous_motor.to_dict(),
                "runtime_version": getattr(self.config, "runtime_version", RUNTIME_VERSION),
                "model_line": getattr(self.config, "model_line", "TIKTAALIK") or "TIKTAALIK",
                "public_preset": getattr(self.config, "public_preset", None),
                "morphology_mechanics": self.config.morphology_mechanics.to_dict(),
                "body_orientation": self.config.body_orientation.to_dict(),
                "body_deformation": self.config.body_deformation.to_dict(),
                "deformation_work": self.config.deformation_work.to_dict(),
                "environmental_resource": self.config.environmental_resource.to_dict(),
                "complementary_resources": self.config.complementary_resources.to_dict(),
                "endogenous_motor_work": self.config.endogenous_motor_work.to_dict(),
                "discrete_action_work": self.config.discrete_action_work.to_dict(),
                "physical_signal": self.config.physical_signal.to_dict(),
                "near_field_exteroception": self.config.near_field_exteroception.to_dict(),
                "articulated_head": self.config.articulated_head.to_dict(),
                "physical_push": self.config.physical_push.to_dict(),
                "vestibular": self.config.vestibular.to_dict(),
                "neck_proprioception": self.config.neck_proprioception.to_dict(),
                "oscillatory_signaling": self.config.oscillatory_signaling.to_dict(),
                "cognition": self.config.cognition.to_dict(),
                "locomotion_profile": (
                    self.config.locomotion_profile.to_dict()
                    if getattr(self.config, "locomotion_profile", None) is not None
                    else tiktaalik_locomotion_profile().to_dict()
                ),
                "physical_resource_objects": (
                    self.config.physical_resource_objects.to_dict()
                    if getattr(self.config, "physical_resource_objects", None) is not None
                    else PhysicalResourceObjectsConfig().to_dict()
                ),
                "physical_resource_object_vision": (
                    self.config.physical_resource_object_vision.to_dict()
                    if getattr(self.config, "physical_resource_object_vision", None) is not None
                    else PhysicalResourceObjectVisionConfig().to_dict()
                ),
                "single_physical_manipulator": (
                    self.config.single_physical_manipulator.to_dict()
                    if getattr(self.config, "single_physical_manipulator", None) is not None
                    else SinglePhysicalManipulatorConfig().to_dict()
                ),
                "physical_grasp_release": (
                    self.config.physical_grasp_release.to_dict()
                    if getattr(self.config, "physical_grasp_release", None) is not None
                    else PhysicalGraspReleaseConfig().to_dict()
                ),
                "bilateral_physical_manipulators": (
                    self.config.bilateral_physical_manipulators.to_dict()
                    if getattr(self.config, "bilateral_physical_manipulators", None) is not None
                    else BilateralPhysicalManipulatorsConfig().to_dict()
                ),
                "bilateral_grasp_release": (
                    self.config.bilateral_grasp_release.to_dict()
                    if getattr(self.config, "bilateral_grasp_release", None) is not None
                    else BilateralGraspReleaseConfig().to_dict()
                ),
                "bilateral_bring_together": (
                    self.config.bilateral_bring_together.to_dict()
                    if getattr(self.config, "bilateral_bring_together", None) is not None
                    else BilateralBringTogetherConfig().to_dict()
                ),
                "material_composition_merge": (
                    self.config.material_composition_merge.to_dict()
                    if getattr(self.config, "material_composition_merge", None) is not None
                    else MaterialCompositionMergeConfig().to_dict()
                ),
                "passive_material_properties": (
                    self.config.passive_material_properties.to_dict()
                    if getattr(self.config, "passive_material_properties", None) is not None
                    else PassiveMaterialPropertiesConfig().to_dict()
                ),
                "physical_optical_material_profile": (
                    self.config.physical_optical_material_profile.to_dict()
                    if getattr(self.config, "physical_optical_material_profile", None) is not None
                    else PhysicalOpticalMaterialProfileConfig().to_dict()
                ),
                "exposed_surface_optical_interaction_authority": (
                    self.config.exposed_surface_optical_interaction_authority.to_dict()
                    if getattr(self.config, "exposed_surface_optical_interaction_authority", None) is not None
                    else ExposedSurfaceOpticalInteractionAuthorityConfig().to_dict()
                ),
                "abstract_spectral_light_source_and_direct_transport": (
                    self.config.abstract_spectral_light_source_and_direct_transport.to_dict()
                    if getattr(self.config, "abstract_spectral_light_source_and_direct_transport", None) is not None
                    else AbstractSpectralLightSourceAndDirectTransportConfig().to_dict()
                ),
                "object_body_held_optical_surfaces": (
                    self.config.object_body_held_optical_surfaces.to_dict()
                    if getattr(self.config, "object_body_held_optical_surfaces", None) is not None
                    else ObjectBodyHeldOpticalSurfacesConfig().to_dict()
                ),
                "organism_physical_optical_reception": (
                    self.config.organism_physical_optical_reception.to_dict()
                    if getattr(self.config, "organism_physical_optical_reception", None) is not None
                    else OrganismPhysicalOpticalReceptionConfig().to_dict()
                ),
                "sensory_modality_temporal_alignment": (
                    self.config.sensory_modality_temporal_alignment.to_dict()
                    if getattr(self.config, "sensory_modality_temporal_alignment", None) is not None
                    else SensoryModalityTemporalAlignmentConfig().to_dict()
                ),
                "explicit_surface_deposition": (
                    self.config.explicit_surface_deposition.to_dict()
                    if getattr(self.config, "explicit_surface_deposition", None) is not None
                    else ExplicitSurfaceDepositionConfig().to_dict()
                ),
                "surface_affinity_traction": (
                    self.config.surface_affinity_traction.to_dict()
                    if getattr(self.config, "surface_affinity_traction", None) is not None
                    else SurfaceAffinityTractionConfig().to_dict()
                ),
                "surface_traction_experience": (
                    self.config.surface_traction_experience.to_dict()
                    if getattr(self.config, "surface_traction_experience", None) is not None
                    else SurfaceTractionExperienceConfig().to_dict()
                ),
                "surface_traction_prediction": (
                    self.config.surface_traction_prediction.to_dict()
                    if getattr(self.config, "surface_traction_prediction", None) is not None
                    else SurfaceTractionPredictionConfig().to_dict()
                ),
                "physical_surface_optical_coating": (
                    self.config.physical_surface_optical_coating.to_dict()
                    if getattr(self.config, "physical_surface_optical_coating", None) is not None
                    else PhysicalSurfaceOpticalCoatingConfig().to_dict()
                ),
                "world_material_transactions": (
                    self.config.world_material_transactions.to_dict()
                    if getattr(self.config, "world_material_transactions", None) is not None
                    else WorldMaterialTransactionsConfig().to_dict()
                ),
                "multi_content_spatial_index": (
                    self.config.multi_content_spatial_index.to_dict()
                    if getattr(self.config, "multi_content_spatial_index", None) is not None
                    else {"enabled": False, "schema_version": "MULTI_CONTENT_SPATIAL_INDEX_V1"}
                ),
                "procedural_surface_columns": (
                    self.config.procedural_surface_columns.to_dict()
                    if getattr(self.config, "procedural_surface_columns", None) is not None
                    else {"enabled": False}
                ),
            },
            "world": serialize_planet_state(self.world, self.config.planet),
            "body": {
                **self.body.snapshot(),
                "deformation": None if getattr(self.body, "deformation", None) is None else np.asarray(self.body.deformation, dtype=float).tolist(),
            },
            "internal": self.internal.snapshot(),
            "cognition": cognition,
            "last_agent_observation": last_obs,
            "last_selected_action": self.last_selected_action,
            "last_motor_output": last_motor,
            "last_manipulator_receipt": deepcopy(self.last_manipulator_receipt) if persist is False else self.last_manipulator_receipt,
            "last_pair_receipt": deepcopy(getattr(self, "last_pair_receipt", None)) if persist is False else getattr(self, "last_pair_receipt", None),
            "last_material_transformation_receipt": deepcopy(getattr(self, "last_material_transformation_receipt", None)) if persist is False else getattr(self, "last_material_transformation_receipt", None),
            "pair_aperture": float(getattr(self, "pair_aperture", 0.84) or 0.84),
            "pair_state": str(getattr(self, "pair_state", "OPEN") or "OPEN"),
            "pair_contact": bool(getattr(self, "pair_contact", False)),
            "technical_id": str(getattr(self, "technical_id", None) or "agent_0"),
            "internal_c_prev": None if self._internal_c_prev is None else np.asarray(self._internal_c_prev, dtype=float).tolist(),
            "prev_body_omega": float(getattr(self, "_prev_body_omega", 0.0) or 0.0),
            "last_orientation_meta": deepcopy(self.last_orientation_meta) if persist is False else self.last_orientation_meta,
            # PSC schedule persistence (experiment protocol; not organism observation).
            "psc_schedule": {
                "psc_off_ticks": getattr(self.config.cognition, "psc_off_ticks", None),
                "psc_auto_activated": bool(getattr(self, "_psc_auto_activated", False)),
                "psc_activation": deepcopy(getattr(self, "_psc_activation", None)),
                "psc_withhold_open": deepcopy(getattr(self, "_psc_withhold_open", None)),
                "prospective_selection": str(
                    getattr(self.config.cognition, "prospective_selection", "") or ""
                ),
                "sensorimotor_consequence_withhold_from_psc": bool(
                    getattr(
                        self.config.cognition,
                        "sensorimotor_consequence_withhold_from_psc",
                        True,
                    )
                ),
            },
        }
        if str(getattr(self.config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
            payload["config"].pop("passive_material_properties", None)
            payload["config"].pop("physical_optical_material_profile", None)
            payload["config"].pop("exposed_surface_optical_interaction_authority", None)
            payload["config"].pop("abstract_spectral_light_source_and_direct_transport", None)
            payload["config"].pop("object_body_held_optical_surfaces", None)
            payload["config"].pop("organism_physical_optical_reception", None)
            payload["config"].pop("sensory_modality_temporal_alignment", None)
            payload["config"].pop("explicit_surface_deposition", None)
            payload["config"].pop("surface_affinity_traction", None)
            payload["config"].pop("surface_traction_experience", None)
            payload["config"].pop("surface_traction_prediction", None)
            payload["config"].pop("physical_surface_optical_coating", None)
            payload["config"].pop("world_material_transactions", None)
            payload["config"].pop("multi_content_spatial_index", None)
            payload["config"].pop("procedural_surface_columns", None)
        from mechanistic_mind.physical_system.conservative_surface_column_transfer import (
            conservative_surface_column_transfer_is_active,
        )
        if conservative_surface_column_transfer_is_active(self.config):
            # Written only when ON so every earlier preset's snapshot keeps its exact key set.
            payload["config"]["conservative_surface_column_transfer"] = (
                self.config.conservative_surface_column_transfer.to_dict()
            )
        from mechanistic_mind.physical_system.local_physical_signal_transport import (
            local_physical_signal_transport_is_active as _lps_active,
        )
        if _lps_active(self.config):
            # Written only when ON (Tiktaalik / previous Acanthostega snapshots keep their key set).
            payload["config"]["local_physical_signal_transport"] = (
                self.config.local_physical_signal_transport.to_dict()
            )
        from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
            physical_contact_acoustic_emission_is_active as _pca_active,
        )
        if _pca_active(self.config):
            # Written only when ON (every earlier preset's snapshot keeps its exact key set).
            payload["config"]["physical_contact_acoustic_emission"] = (
                self.config.physical_contact_acoustic_emission.to_dict()
            )
        from mechanistic_mind.physical_system.free_resource_object_kinematics import (
            free_resource_object_kinematics_is_active as _fok_active,
        )
        if _fok_active(self.config):
            # Written only when ON (every earlier preset's snapshot keeps its exact key set).
            payload["config"]["free_resource_object_kinematics"] = (
                self.config.free_resource_object_kinematics.to_dict()
            )
        from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
            body_object_contact_is_active as _boc_active,
        )
        if _boc_active(self.config):
            payload["config"]["physical_body_resource_object_contact"] = (
                self.config.physical_body_resource_object_contact.to_dict()
            )
        from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
            body_object_impulse_is_active as _boi_active,
        )
        if _boi_active(self.config):
            payload["config"]["body_resource_object_contact_impulse"] = (
                self.config.body_resource_object_contact_impulse.to_dict()
            )
        from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
            body_object_impact_acoustics_is_active as _oia_active,
            serialize_state as _oia_serialize,
        )
        if _oia_active(self.config):
            payload["config"]["body_resource_object_impact_acoustic_emission"] = (
                self.config.body_resource_object_impact_acoustic_emission.to_dict()
            )
            payload["body_object_impact_acoustic_state"] = _oia_serialize(
                getattr(self.world, "body_object_impact_acoustic_state", None)
            )
        from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
            resource_object_pair_contact_is_active as _ooc_active,
            serialize_state as _ooc_serialize,
        )
        if _ooc_active(self.config):
            payload["config"]["physical_resource_object_pair_contact"] = (
                self.config.physical_resource_object_pair_contact.to_dict()
            )
            payload["resource_object_pair_contact_state"] = _ooc_serialize(
                getattr(self.world, "resource_object_pair_contact_state", None)
            )
        from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
            resource_object_pair_impulse_is_active as _ooi_active,
            serialize_state as _ooi_serialize,
        )
        if _ooi_active(self.config):
            payload["config"]["resource_object_pair_contact_impulse"] = (
                self.config.resource_object_pair_contact_impulse.to_dict()
            )
            payload["resource_object_pair_contact_impulse_state"] = _ooi_serialize(
                getattr(self.world, "resource_object_pair_contact_impulse_state", None)
            )
        from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
            resource_object_pair_impact_acoustics_is_active as _ooia_active,
            serialize_state as _ooia_serialize,
        )
        if _ooia_active(self.config):
            payload["config"]["resource_object_pair_impact_acoustic_emission"] = (
                self.config.resource_object_pair_impact_acoustic_emission.to_dict()
            )
            payload["resource_object_pair_impact_acoustic_state"] = _ooia_serialize(
                getattr(self.world, "resource_object_pair_impact_acoustic_state", None)
            )

        from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
            held_foreign_body_contact_is_active as _hfc_active,
            serialize_state as _hfc_serialize,
        )
        if _hfc_active(self.config):
            payload["config"]["held_resource_object_foreign_body_contact"] = (
                self.config.held_resource_object_foreign_body_contact.to_dict()
            )
            payload["held_foreign_body_contact_state"] = _hfc_serialize(
                getattr(self.world, "held_foreign_body_contact_state", None)
            )
        from mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation import (
            held_translational_impulse_is_active as _hti_active,
            serialize_state as _hti_serialize,
        )
        if _hti_active(self.config):
            payload["config"]["held_resource_object_translational_impulse_mediation"] = (
                self.config.held_resource_object_translational_impulse_mediation.to_dict()
            )
            payload["held_translational_impulse_state"] = _hti_serialize(
                getattr(self.world, "held_translational_impulse_state", None)
            )

        from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
            effector_work_held_load_is_active as _ehl_active,
            serialize_state as _ehl_serialize,
        )
        if _ehl_active(self.config):
            payload["config"]["effector_work_and_held_load_inertia_accounting"] = (
                self.config.effector_work_and_held_load_inertia_accounting.to_dict()
            )
            payload["effector_work_held_load_state"] = _ehl_serialize(
                getattr(self.world, "effector_work_held_load_state", None)
            )

        from mechanistic_mind.physical_system.flat_ground_gravity import (
            flat_ground_gravity_is_active as _fgg_ser_active,
            serialize_state as _fgg_serialize,
        )
        if _fgg_ser_active(self.config):
            payload["config"]["flat_ground_gravity"] = (
                self.config.flat_ground_gravity.to_dict()
            )
            payload["flat_ground_gravity_state"] = _fgg_serialize(
                getattr(self.world, "flat_ground_gravity_state", None)
            )

        from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
            free_resource_object_ground_friction_is_active as _fogf_ser_active,
            serialize_state as _fogf_serialize,
        )
        if _fogf_ser_active(self.config):
            payload["config"]["free_resource_object_ground_friction"] = (
                self.config.free_resource_object_ground_friction.to_dict()
            )
            payload["free_resource_object_ground_friction_state"] = _fogf_serialize(
                getattr(self.world, "free_resource_object_ground_friction_state", None)
            )

        from mechanistic_mind.physical_system.surface_elevation_support import (
            surface_elevation_support_is_active as _ses_ser_active,
            serialize_state as _ses_serialize,
        )
        if _ses_ser_active(self.config):
            payload["config"]["surface_elevation_support"] = (
                self.config.surface_elevation_support.to_dict()
            )
            payload["surface_elevation_support_state"] = _ses_serialize(
                getattr(self.world, "surface_elevation_support_state", None)
            )

        from mechanistic_mind.physical_system.body_normal_load_traction import (
            body_normal_load_traction_is_active as _bnlt_ser_active,
            serialize_state as _bnlt_serialize,
        )
        if _bnlt_ser_active(self.config):
            payload["config"]["body_normal_load_traction"] = (
                self.config.body_normal_load_traction.to_dict()
            )
            payload["body_normal_load_traction_state"] = _bnlt_serialize(
                getattr(self.world, "body_normal_load_traction_state", None)
            )
        from mechanistic_mind.physical_system.continuous_surface_geometry import (
            continuous_surface_geometry_is_active as _csg_ser_active,
            serialize_state as _csg_serialize,
        )
        if _csg_ser_active(self.config) and getattr(self.config, "continuous_surface_geometry", None) is not None:
            payload["config"]["continuous_surface_geometry"] = (
                self.config.continuous_surface_geometry.to_dict()
            )
            payload["continuous_surface_geometry_state"] = _csg_serialize(
                getattr(self.world, "continuous_surface_geometry_state", None)
            )

        from mechanistic_mind.physical_system.body_static_traction_threshold import (
            body_static_traction_threshold_is_active as _bst_ser_active,
            serialize_state as _bst_serialize,
        )
        if _bst_ser_active(self.config) and getattr(self.config, "body_static_traction_threshold", None) is not None:
            payload["config"]["body_static_traction_threshold"] = (
                self.config.body_static_traction_threshold.to_dict()
            )
            payload["body_static_traction_threshold_state"] = _bst_serialize(
                getattr(self.world, "body_static_traction_threshold_state", None)
            )

        from mechanistic_mind.physical_system.free_resource_object_static_traction_threshold import (
            free_resource_object_static_traction_threshold_is_active as _fost_ser_active,
            serialize_state as _fost_serialize,
        )
        if _fost_ser_active(self.config) and getattr(self.config, "free_resource_object_static_traction_threshold", None) is not None:
            payload["config"]["free_resource_object_static_traction_threshold"] = (
                self.config.free_resource_object_static_traction_threshold.to_dict()
            )
            payload["free_resource_object_static_traction_threshold_state"] = _fost_serialize(
                getattr(self.world, "free_resource_object_static_traction_threshold_state", None)
            )
        from mechanistic_mind.physical_system.radius_aware_support_points import (
            radius_aware_support_points_is_active as _rasp_ser_active,
            serialize_state as _rasp_serialize,
        )
        if _rasp_ser_active(self.config) and getattr(self.config, "radius_aware_support_points", None) is not None:
            payload["config"]["radius_aware_support_points"] = (
                self.config.radius_aware_support_points.to_dict()
            )
            payload["radius_aware_support_points_state"] = _rasp_serialize(
                getattr(self.world, "radius_aware_support_points_state", None)
            )
        from mechanistic_mind.physical_system.ses_decomposition_contract import (
            ses_decomposition_contract_is_active as _sdc_ser_active,
            serialize_state as _sdc_serialize,
        )
        if _sdc_ser_active(self.config) and getattr(self.config, "ses_decomposition_contract", None) is not None:
            payload["config"]["ses_decomposition_contract"] = (
                self.config.ses_decomposition_contract.to_dict()
            )
            payload["ses_decomposition_contract_state"] = _sdc_serialize(
                getattr(self.world, "ses_decomposition_contract_state", None)
            )
        from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
            ses_runtime_transition_classifier_is_active as _srtc_ser_active,
            serialize_state as _srtc_serialize,
        )
        if _srtc_ser_active(self.config) and getattr(self.config, "ses_runtime_transition_classifier", None) is not None:
            payload["config"]["ses_runtime_transition_classifier"] = (
                self.config.ses_runtime_transition_classifier.to_dict()
            )
            payload["ses_runtime_transition_classifier_state"] = _srtc_serialize(
                getattr(self.world, "ses_runtime_transition_classifier_state", None)
            )
        from mechanistic_mind.physical_system.radius_aware_face_sweep import (
            radius_aware_face_sweep_is_active as _rafs_ser_active,
            serialize_state as _rafs_serialize,
        )
        if _rafs_ser_active(self.config) and getattr(self.config, "radius_aware_face_sweep", None) is not None:
            payload["config"]["radius_aware_face_sweep"] = (
                self.config.radius_aware_face_sweep.to_dict()
            )
            payload["radius_aware_face_sweep_state"] = _rafs_serialize(
                getattr(self.world, "radius_aware_face_sweep_state", None)
            )
        from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
            diagnostic_normal_load_shadow_is_active as _dnls_ser_active,
            serialize_state as _dnls_serialize,
        )
        if _dnls_ser_active(self.config) and getattr(self.config, "diagnostic_normal_load_shadow", None) is not None:
            payload["config"]["diagnostic_normal_load_shadow"] = (
                self.config.diagnostic_normal_load_shadow.to_dict()
            )
            payload["diagnostic_normal_load_shadow_state"] = _dnls_serialize(
                getattr(self.world, "diagnostic_normal_load_shadow_state", None)
            )
        from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
            continuous_gravitational_pe_diagnostic_shadow_is_active as _cgpe_ser_active,
            serialize_state as _cgpe_serialize,
        )
        if _cgpe_ser_active(self.config) and getattr(self.config, "continuous_gravitational_pe_diagnostic_shadow", None) is not None:
            payload["config"]["continuous_gravitational_pe_diagnostic_shadow"] = (
                self.config.continuous_gravitational_pe_diagnostic_shadow.to_dict()
            )
            payload["continuous_gravitational_pe_diagnostic_shadow_state"] = _cgpe_serialize(
                getattr(self.world, "continuous_gravitational_pe_diagnostic_shadow_state", None)
            )
        from mechanistic_mind.physical_system.continuous_gravitational_pe import (
            continuous_gravitational_pe_is_active as _cgp_ser_active,
            serialize_state as _cgp_serialize,
        )
        if _cgp_ser_active(self.config) and getattr(self.config, "continuous_gravitational_pe", None) is not None:
            payload["config"]["continuous_gravitational_pe"] = (
                self.config.continuous_gravitational_pe.to_dict()
            )
            payload["continuous_gravitational_pe_state"] = _cgp_serialize(
                getattr(self.world, "continuous_gravitational_pe_state", None)
            )
        from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
            tangent_gravity_diagnostic_shadow_is_active as _tgds_ser_active,
            serialize_state as _tgds_serialize,
        )
        if _tgds_ser_active(self.config) and getattr(self.config, "tangent_gravity_diagnostic_shadow", None) is not None:
            payload["config"]["tangent_gravity_diagnostic_shadow"] = (
                self.config.tangent_gravity_diagnostic_shadow.to_dict()
            )
            payload["tangent_gravity_diagnostic_shadow_state"] = _tgds_serialize(
                getattr(self.world, "tangent_gravity_diagnostic_shadow_state", None)
            )
        from mechanistic_mind.physical_system.coherent_slope_dynamics import (
            coherent_slope_dynamics_is_active as _csd_ser_active,
            serialize_state as _csd_serialize,
        )
        if _csd_ser_active(self.config) and getattr(self.config, "coherent_slope_dynamics", None) is not None:
            payload["config"]["coherent_slope_dynamics"] = (
                self.config.coherent_slope_dynamics.to_dict()
            )
            payload["coherent_slope_dynamics_state"] = _csd_serialize(
                getattr(self.world, "coherent_slope_dynamics_state", None)
            )
        from mechanistic_mind.physical_system.conservative_surface_material_separation import (
            conservative_surface_material_separation_is_active as _csms_ser_active,
            serialize_state as _csms_serialize,
        )
        if _csms_ser_active(self.config) and getattr(
            self.config, "conservative_surface_material_separation", None
        ) is not None:
            payload["config"]["conservative_surface_material_separation"] = (
                self.config.conservative_surface_material_separation.to_dict()
            )
            payload["surface_material_separation_state"] = _csms_serialize(
                getattr(self.world, "surface_material_separation_state", None)
            )
        from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
            effector_terrain_contact_geometry_is_active as _etc_ser_active,
            serialize_state as _etc_serialize,
        )
        if _etc_ser_active(self.config) and getattr(
            self.config, "effector_terrain_contact_geometry", None
        ) is not None:
            payload["config"]["effector_terrain_contact_geometry"] = (
                self.config.effector_terrain_contact_geometry.to_dict()
            )
            payload["effector_terrain_contact_geometry_state"] = _etc_serialize(
                getattr(self.world, "effector_terrain_contact_geometry_state", None)
            )
        from mechanistic_mind.physical_system.effector_occupancy_reachability_trace import (
            effector_occupancy_reachability_trace_is_active as _eort_ser_active,
            serialize_state as _eort_serialize,
        )
        if _eort_ser_active(self.config) and getattr(
            self.config, "effector_occupancy_reachability_trace", None
        ) is not None:
            payload["config"]["effector_occupancy_reachability_trace"] = (
                self.config.effector_occupancy_reachability_trace.to_dict()
            )
            payload["effector_occupancy_reachability_trace_state"] = _eort_serialize(
                getattr(self.world, "effector_occupancy_reachability_trace_state", None)
            )
        from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
            manipulator_relative_world_actuation_is_active as _mrwa_ser_active,
            serialize_state as _mrwa_serialize,
        )
        if _mrwa_ser_active(self.config) and getattr(
            self.config, "manipulator_relative_world_actuation", None
        ) is not None:
            payload["config"]["manipulator_relative_world_actuation"] = (
                self.config.manipulator_relative_world_actuation.to_dict()
            )
            payload["manipulator_relative_world_actuation_state"] = _mrwa_serialize(
                getattr(self.world, "manipulator_relative_world_actuation_state", None)
            )
        from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
            effector_bounded_actuator_effort_is_active as _ebae_ser_active,
            serialize_state as _ebae_serialize,
        )
        if _ebae_ser_active(self.config) and getattr(
            self.config, "effector_bounded_actuator_effort", None
        ) is not None:
            payload["config"]["effector_bounded_actuator_effort"] = (
                self.config.effector_bounded_actuator_effort.to_dict()
            )
            payload["effector_bounded_actuator_effort_state"] = _ebae_serialize(
                getattr(self.world, "effector_bounded_actuator_effort_state", None)
            )
        from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
            surface_exertion_terrain_material_resistance_is_active as _setmr_ser_active,
            serialize_state as _setmr_serialize,
        )
        if _setmr_ser_active(self.config) and getattr(
            self.config, "surface_exertion_terrain_material_resistance", None
        ) is not None:
            payload["config"]["surface_exertion_terrain_material_resistance"] = (
                self.config.surface_exertion_terrain_material_resistance.to_dict()
            )
            payload["surface_exertion_terrain_material_resistance_state"] = _setmr_serialize(
                getattr(self.world, "surface_exertion_terrain_material_resistance_state", None)
            )
        from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
            minimal_vision_3d_geometric_interface_is_active as _vw6_ser_active,
        )
        if _vw6_ser_active(self.config) or getattr(
            self.config, "minimal_vision_3d_geometric_interface", None
        ) is not None:
            payload["config"]["minimal_vision_3d_geometric_interface"] = (
                self.config.minimal_vision_3d_geometric_interface.to_dict()
            )
        from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
            held_resource_object_terrain_contact_geometry_is_active as _hotc_ser_active,
            serialize_state as _hotc_serialize,
        )
        if _hotc_ser_active(self.config) and getattr(
            self.config, "held_resource_object_terrain_contact_geometry", None
        ) is not None:
            payload["config"]["held_resource_object_terrain_contact_geometry"] = (
                self.config.held_resource_object_terrain_contact_geometry.to_dict()
            )
            payload["held_resource_object_terrain_contact_geometry_state"] = _hotc_serialize(
                getattr(self.world, "held_resource_object_terrain_contact_geometry_state", None)
            )
        from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
            held_resource_object_terrain_mechanical_transmission_is_active as _hotmt_ser_active,
            serialize_state as _hotmt_serialize,
        )
        if _hotmt_ser_active(self.config) and getattr(
            self.config, "held_resource_object_terrain_mechanical_transmission", None
        ) is not None:
            payload["config"]["held_resource_object_terrain_mechanical_transmission"] = (
                self.config.held_resource_object_terrain_mechanical_transmission.to_dict()
            )
            payload["held_resource_object_terrain_mechanical_transmission_state"] = _hotmt_serialize(
                getattr(
                    self.world,
                    "held_resource_object_terrain_mechanical_transmission_state",
                    None,
                )
            )
        from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
            held_mediated_surface_exertion_integration_is_active as _hmsi_ser_active,
            serialize_state as _hmsi_serialize,
        )
        if _hmsi_ser_active(self.config) and getattr(
            self.config, "held_mediated_surface_exertion_integration", None
        ) is not None:
            payload["config"]["held_mediated_surface_exertion_integration"] = (
                self.config.held_mediated_surface_exertion_integration.to_dict()
            )
            payload["held_mediated_surface_exertion_integration_state"] = _hmsi_serialize(
                getattr(self.world, "held_mediated_surface_exertion_integration_state", None)
            )
        from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
            detached_terrain_material_initial_placement_is_active as _dtip_ser_active,
            serialize_state as _dtip_serialize,
        )
        if _dtip_ser_active(self.config) or getattr(
            self.config, "detached_terrain_material_initial_placement", None
        ) is not None:
            payload["config"]["detached_terrain_material_initial_placement"] = (
                self.config.detached_terrain_material_initial_placement.to_dict()
            )
            payload["detached_terrain_material_initial_placement_state"] = _dtip_serialize(
                getattr(self.world, "detached_terrain_material_initial_placement_state", None)
            )
        from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
            bnlt_move_breakaway_locomotion_repair_is_active as _bnlt_rep_ser_active,
            serialize_state as _bnlt_rep_serialize,
        )
        if _bnlt_rep_ser_active(self.config) or getattr(
            self.config, "bnlt_move_breakaway_locomotion_repair", None
        ) is not None:
            payload["config"]["bnlt_move_breakaway_locomotion_repair"] = (
                self.config.bnlt_move_breakaway_locomotion_repair.to_dict()
            )
            payload["bnlt_move_breakaway_locomotion_repair_state"] = _bnlt_rep_serialize(
                getattr(self.world, "bnlt_move_breakaway_locomotion_repair_state", None)
            )
        from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
            repeated_conservative_surface_column_separation_is_active as _rcss_ser_active,
            serialize_state as _rcss_serialize,
        )
        if _rcss_ser_active(self.config) or getattr(
            self.config, "repeated_conservative_surface_column_separation", None
        ) is not None:
            payload["config"]["repeated_conservative_surface_column_separation"] = (
                self.config.repeated_conservative_surface_column_separation.to_dict()
            )
            payload["repeated_conservative_surface_column_separation_state"] = _rcss_serialize(
                getattr(self.world, "repeated_conservative_surface_column_separation_state", None)
            )
        from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
            event_driven_crowded_placement_retry_contract_is_active as _crowded_ser_active,
            serialize_state as _crowded_serialize,
        )
        if _crowded_ser_active(self.config) or getattr(
            self.config, "event_driven_crowded_placement_retry_contract", None
        ) is not None:
            payload["config"]["event_driven_crowded_placement_retry_contract"] = (
                self.config.event_driven_crowded_placement_retry_contract.to_dict()
            )
            payload["event_driven_crowded_placement_retry_contract_state"] = _crowded_serialize(
                getattr(self.world, "event_driven_crowded_placement_retry_contract_state", None)
            )
        from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
            detached_material_amount_scaled_collision_radius_is_active as _size_geo_ser_active,
            serialize_state as _size_geo_serialize,
        )
        if _size_geo_ser_active(self.config) or getattr(
            self.config, "detached_material_amount_scaled_collision_radius", None
        ) is not None:
            payload["config"]["detached_material_amount_scaled_collision_radius"] = (
                self.config.detached_material_amount_scaled_collision_radius.to_dict()
            )
            payload["detached_material_amount_scaled_collision_radius_state"] = _size_geo_serialize(
                getattr(self.world, "detached_material_amount_scaled_collision_radius_state", None)
            )
        from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
            held_combine_radius_resize_transaction_is_active as _held_combine_ser_active,
            serialize_state as _held_combine_serialize,
        )
        if _held_combine_ser_active(self.config) or getattr(
            self.config, "held_combine_radius_resize_transaction", None
        ) is not None:
            payload["config"]["held_combine_radius_resize_transaction"] = (
                self.config.held_combine_radius_resize_transaction.to_dict()
            )
            payload["held_combine_radius_resize_transaction_state"] = _held_combine_serialize(
                getattr(self.world, "held_combine_radius_resize_transaction_state", None)
            )
        from mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction import (
            held_deposition_radius_shrink_transaction_is_active as _held_deposition_ser_active,
            serialize_state as _held_deposition_serialize,
        )
        if _held_deposition_ser_active(self.config) or getattr(
            self.config, "held_deposition_radius_shrink_transaction", None
        ) is not None:
            payload["config"]["held_deposition_radius_shrink_transaction"] = (
                self.config.held_deposition_radius_shrink_transaction.to_dict()
            )
            payload["held_deposition_radius_shrink_transaction_state"] = _held_deposition_serialize(
                getattr(self.world, "held_deposition_radius_shrink_transaction_state", None)
            )
        from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
            free_space_state_and_pe_authority_contract_is_active as _fs_ser_active,
            serialize_state as _fs_serialize,
        )
        if _fs_ser_active(self.config) or getattr(
            self.config, "free_space_state_and_pe_authority_contract", None
        ) is not None:
            payload["config"]["free_space_state_and_pe_authority_contract"] = (
                self.config.free_space_state_and_pe_authority_contract.to_dict()
            )
            payload["free_space_state_and_pe_authority_contract_state"] = _fs_serialize(
                getattr(self.world, "free_space_state_and_pe_authority_contract_state", None)
            )
        from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
            vertical_terrain_landing_contact_response_is_active as _vtl_ser_active,
            serialize_state as _vtl_serialize,
        )
        if _vtl_ser_active(self.config) or getattr(
            self.config, "vertical_terrain_landing_contact_response", None
        ) is not None:
            payload["config"]["vertical_terrain_landing_contact_response"] = (
                self.config.vertical_terrain_landing_contact_response.to_dict()
            )
            payload["vertical_terrain_landing_contact_response_state"] = _vtl_serialize(
                getattr(self.world, "vertical_terrain_landing_contact_response_state", None)
            )
        from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
            vertical_impact_acoustic_emission_is_active as _via_ser_active,
            serialize_state as _via_serialize,
        )
        if _via_ser_active(self.config) or getattr(
            self.config, "vertical_impact_acoustic_emission", None
        ) is not None:
            payload["config"]["vertical_impact_acoustic_emission"] = (
                self.config.vertical_impact_acoustic_emission.to_dict()
            )
            payload["vertical_impact_acoustic_emission_state"] = _via_serialize(
                getattr(self.world, "vertical_impact_acoustic_emission_state", None)
            )
        from mechanistic_mind.physical_system.authoritative_physical_acoustic_stream_contract import (
            serialize_state as _apas_serialize,
            state_of as _apas_state_of,
        )
        if _apas_state_of(self.world) is not None or getattr(
            self.world, "local_signal_transport", None
        ) is not None:
            payload["authoritative_physical_acoustic_stream_state"] = _apas_serialize(
                _apas_state_of(self.world)
            )
        from mechanistic_mind.physical_system.observer_acoustic_probe import (
            serialize_state as _oap_serialize,
            state_of as _oap_state_of,
            ensure_probe_state as _oap_ensure,
        )
        # Researcher configuration (+ bounded sample history); not physical LPS state.
        if _oap_state_of(self.world) is not None or getattr(
            self.world, "local_signal_transport", None
        ) is not None:
            _oap_ensure(self.world)
            payload["observer_acoustic_probe_state"] = _oap_serialize(_oap_state_of(self.world))
        from mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt import (
            serialize_state as _soab_serialize,
            state_of as _soab_state_of,
            ensure_state as _soab_ensure,
        )
        if _soab_state_of(self.world) is not None or getattr(
            self.world, "local_signal_transport", None
        ) is not None:
            _soab_ensure(self.world)
            payload["selected_organism_auditory_boundary_state"] = _soab_serialize(
                _soab_state_of(self.world)
            )
        from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
            serialize_state as _sovv_serialize,
            state_of as _sovv_state_of,
            ensure_state as _sovv_ensure,
        )
        if _sovv_state_of(self.world) is not None:
            payload["selected_organism_volumetric_vision_state"] = _sovv_serialize(
                _sovv_state_of(self.world)
            )
        elif getattr(getattr(self.config, "minimal_vision_3d_geometric_interface", None), "enabled", False):
            _sovv_ensure(self.world)
            payload["selected_organism_volumetric_vision_state"] = _sovv_serialize(
                _sovv_state_of(self.world)
            )
        from mechanistic_mind.physical_system.organism_receptor_grounded_3d_fpv import (
            serialize_state as _fpv_serialize,
            state_of as _fpv_state_of,
        )
        if _fpv_state_of(self.world) is not None:
            payload["organism_receptor_grounded_3d_fpv_state"] = _fpv_serialize(
                _fpv_state_of(self.world)
            )
        from mechanistic_mind.physical_system.organism_auditory_transformation_trace import (
            serialize_state as _oatt_serialize,
            state_of as _oatt_state_of,
            ensure_state as _oatt_ensure,
        )
        if _oatt_state_of(self.world) is not None or getattr(
            self.world, "local_signal_transport", None
        ) is not None:
            _oatt_ensure(self.world)
            payload["organism_auditory_transformation_trace_state"] = _oatt_serialize(
                _oatt_state_of(self.world)
            )
        from mechanistic_mind.physical_system.sensory_modality_temporal_alignment import (
            serialize_state as _o5_serialize,
            sensory_modality_temporal_alignment_is_active as _o5_active,
        )
        if _o5_active(self.config) or getattr(
            self.world, "_o5_alignment_envelopes", None
        ) is not None:
            ser = _o5_serialize(self.world)
            if ser is not None:
                payload["sensory_modality_temporal_alignment_state"] = ser
        from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
            release_and_excavation_support_loss_integration_is_active as _resli_ser_active,
            serialize_state as _resli_serialize,
        )
        if _resli_ser_active(self.config) or getattr(
            self.config, "release_and_excavation_support_loss_integration", None
        ) is not None:
            payload["config"]["release_and_excavation_support_loss_integration"] = (
                self.config.release_and_excavation_support_loss_integration.to_dict()
            )
            payload["release_and_excavation_support_loss_integration_state"] = _resli_serialize(
                getattr(self.world, "release_and_excavation_support_loss_integration_state", None)
            )

        if getattr(self, "last_surface_deposition_receipt", None) is not None:
            payload["last_surface_deposition_receipt"] = (
                deepcopy(self.last_surface_deposition_receipt) if persist is False
                else self.last_surface_deposition_receipt
            )
        if getattr(self, "last_surface_traction_receipt", None) is not None:
            payload["last_surface_traction_receipt"] = (
                deepcopy(self.last_surface_traction_receipt) if persist is False
                else self.last_surface_traction_receipt
            )
        if getattr(self, "last_traction_experience_receipt", None) is not None:
            payload["last_traction_experience_receipt"] = (
                deepcopy(self.last_traction_experience_receipt) if persist is False
                else self.last_traction_experience_receipt
            )
        if getattr(self, "_traction_experience_pending", None) is not None:
            payload["traction_experience_pending"] = (
                deepcopy(self._traction_experience_pending) if persist is False
                else self._traction_experience_pending
            )
        if getattr(self, "traction_experience_history", None):
            payload["traction_experience_history"] = (
                deepcopy(self.traction_experience_history) if persist is False
                else list(self.traction_experience_history)
            )
        if getattr(self, "_traction_experience_closed_tick", None) is not None:
            payload["traction_experience_closed_tick"] = int(self._traction_experience_closed_tick)
        if getattr(self, "last_traction_prediction_receipt", None) is not None:
            payload["last_traction_prediction_receipt"] = (
                deepcopy(self.last_traction_prediction_receipt) if persist is False
                else self.last_traction_prediction_receipt
            )
        if getattr(self, "_traction_prediction_pending", None) is not None:
            payload["traction_prediction_pending"] = (
                deepcopy(self._traction_prediction_pending) if persist is False
                else self._traction_prediction_pending
            )
        if getattr(self, "traction_prediction_history", None):
            payload["traction_prediction_history"] = (
                deepcopy(self.traction_prediction_history) if persist is False
                else list(self.traction_prediction_history)
            )
        if getattr(self, "_traction_prediction_closed_tick", None) is not None:
            payload["traction_prediction_closed_tick"] = int(self._traction_prediction_closed_tick)
        payload["traction_prediction_episode_index"] = int(
            getattr(self, "_traction_prediction_episode_index", 0) or 0
        )
        if getattr(self, "surface_optical_coating_history", None):
            payload["surface_optical_coating_history"] = (
                deepcopy(self.surface_optical_coating_history) if persist is False
                else list(self.surface_optical_coating_history)
            )
        if getattr(self, "last_surface_optical_coating_receipt", None) is not None:
            payload["last_surface_optical_coating_receipt"] = (
                deepcopy(self.last_surface_optical_coating_receipt) if persist is False
                else self.last_surface_optical_coating_receipt
            )
        phase = getattr(self, "traction_adaptation_phase", None)
        if phase and phase != "UNSPECIFIED":
            payload["traction_adaptation_phase"] = str(phase)
        return payload

    @classmethod
    def restore(
        cls,
        payload: dict[str, Any],
        *,
        world_seed: int | None = None,
        shared_world_member: bool = False,
    ) -> "PhysicalSystemRuntime":
        """shared_world_member=True (TwoAgentRuntime.restore only): this slot is one of several bodies of
        a shared world, so shared-world finalization (holder-attachment sanitation and the derived
        spatial-index rebuild) is left to the container, which runs it once after every slot is bound.
        Default False = unchanged single-agent restore."""
        from mechanistic_mind.physical_system.spatial_contents import MultiContentSpatialIndexConfig
        from mechanistic_mind.physical_system.procedural_surface_columns import (
            ProceduralSurfaceColumnsConfig,
        )
        from mechanistic_mind.physical_system.conservative_surface_column_transfer import (
            ConservativeSurfaceColumnTransferConfig,
        )

        configs = payload["config"]
        cog_raw = configs.get("cognition") if isinstance(configs.get("cognition"), dict) else {}
        legacy_psc_off_ticks = "psc_off_ticks" not in cog_raw and "psc_schedule" not in payload
        cog_cfg = CognitionConfig.from_dict(configs.get("cognition"))
        # Prefer explicit top-level psc_schedule block when present (post-repair snapshots).
        sched = payload.get("psc_schedule") if isinstance(payload.get("psc_schedule"), dict) else None
        if sched is not None and "psc_off_ticks" in sched:
            cog_cfg.psc_off_ticks = sched.get("psc_off_ticks")
        elif "psc_off_ticks" in cog_raw:
            try:
                v = cog_raw.get("psc_off_ticks")
                cog_cfg.psc_off_ticks = None if v is None else int(v)
            except (TypeError, ValueError):
                cog_cfg.psc_off_ticks = None
        if sched is not None and "prospective_selection" in sched and sched.get("prospective_selection"):
            cog_cfg.prospective_selection = str(sched.get("prospective_selection"))
        if sched is not None and "sensorimotor_consequence_withhold_from_psc" in sched:
            cog_cfg.sensorimotor_consequence_withhold_from_psc = bool(
                sched.get("sensorimotor_consequence_withhold_from_psc")
            )
        config = PhysicalSystemConfig(
            runtime_version=str(configs.get("runtime_version") or RUNTIME_VERSION),
            model_line=str(configs.get("model_line") or (payload.get("model") or {}).get("model_line") or "TIKTAALIK"),
            public_preset=(
                configs.get("public_preset")
                if configs.get("public_preset") is not None
                else (payload.get("model") or {}).get("public_preset")
            ),
            ecology_preset=str(configs.get("ecology_preset") or "CURRENT"),
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
            near_field_exteroception=NearFieldExteroceptionConfig.from_dict(
                configs.get("near_field_exteroception")
            ),
            articulated_head=ArticulatedHeadConfig.from_dict(configs.get("articulated_head")),
            physical_push=PhysicalPushConfig.from_dict(configs.get("physical_push")),
            vestibular=VestibularConfig.from_dict(configs.get("vestibular")),
            neck_proprioception=NeckProprioceptionConfig.from_dict(configs.get("neck_proprioception")),
            oscillatory_signaling=OscillatorySignalingConfig.from_dict(
                configs.get("oscillatory_signaling")
            ),
            locomotion_profile=LocomotionPhysicsProfile.from_dict(
                configs.get("locomotion_profile")
            ),
            physical_resource_objects=PhysicalResourceObjectsConfig.from_dict(
                configs.get("physical_resource_objects")
            ),
            physical_resource_object_vision=PhysicalResourceObjectVisionConfig.from_dict(
                configs.get("physical_resource_object_vision")
            ),
            single_physical_manipulator=SinglePhysicalManipulatorConfig.from_dict(
                configs.get("single_physical_manipulator")
            ),
            physical_grasp_release=PhysicalGraspReleaseConfig.from_dict(
                configs.get("physical_grasp_release")
            ),
            bilateral_physical_manipulators=BilateralPhysicalManipulatorsConfig.from_dict(
                configs.get("bilateral_physical_manipulators")
            ),
            bilateral_grasp_release=BilateralGraspReleaseConfig.from_dict(
                configs.get("bilateral_grasp_release")
            ),
            bilateral_bring_together=BilateralBringTogetherConfig.from_dict(
                configs.get("bilateral_bring_together")
            ),
            material_composition_merge=MaterialCompositionMergeConfig.from_dict(
                configs.get("material_composition_merge")
            ),
            passive_material_properties=PassiveMaterialPropertiesConfig.from_dict(
                configs.get("passive_material_properties")
            ),
            physical_optical_material_profile=PhysicalOpticalMaterialProfileConfig.from_dict(
                configs.get("physical_optical_material_profile")
            ),
            exposed_surface_optical_interaction_authority=ExposedSurfaceOpticalInteractionAuthorityConfig.from_dict(
                configs.get("exposed_surface_optical_interaction_authority")
            ),
            abstract_spectral_light_source_and_direct_transport=AbstractSpectralLightSourceAndDirectTransportConfig.from_dict(
                configs.get("abstract_spectral_light_source_and_direct_transport")
            ),
            object_body_held_optical_surfaces=ObjectBodyHeldOpticalSurfacesConfig.from_dict(
                configs.get("object_body_held_optical_surfaces")
            ),
            organism_physical_optical_reception=OrganismPhysicalOpticalReceptionConfig.from_dict(
                configs.get("organism_physical_optical_reception")
            ),
            sensory_modality_temporal_alignment=SensoryModalityTemporalAlignmentConfig.from_dict(
                configs.get("sensory_modality_temporal_alignment")
            ),
            explicit_surface_deposition=ExplicitSurfaceDepositionConfig.from_dict(
                configs.get("explicit_surface_deposition")
            ),
            surface_affinity_traction=SurfaceAffinityTractionConfig.from_dict(
                configs.get("surface_affinity_traction")
            ),
            surface_traction_experience=SurfaceTractionExperienceConfig.from_dict(
                configs.get("surface_traction_experience")
            ),
            surface_traction_prediction=SurfaceTractionPredictionConfig.from_dict(
                configs.get("surface_traction_prediction")
            ),
            physical_surface_optical_coating=PhysicalSurfaceOpticalCoatingConfig.from_dict(
                configs.get("physical_surface_optical_coating")
            ),
            world_material_transactions=WorldMaterialTransactionsConfig.from_dict(
                configs.get("world_material_transactions")
            ),
            multi_content_spatial_index=MultiContentSpatialIndexConfig.from_dict(
                configs.get("multi_content_spatial_index")
            ),
            procedural_surface_columns=ProceduralSurfaceColumnsConfig.from_dict(
                configs.get("procedural_surface_columns")
            ),
            # Missing field (every older snapshot) -> None -> mechanism OFF.
            conservative_surface_column_transfer=(
                ConservativeSurfaceColumnTransferConfig.from_dict(
                    configs.get("conservative_surface_column_transfer")
                )
                if configs.get("conservative_surface_column_transfer")
                else None
            ),
            local_physical_signal_transport=_lps_config_from_snapshot(configs),
            physical_contact_acoustic_emission=_pca_config_from_snapshot(configs),
            free_resource_object_kinematics=_fok_config_from_snapshot(configs),
            physical_body_resource_object_contact=_boc_config_from_snapshot(configs),
            body_resource_object_contact_impulse=_boi_config_from_snapshot(configs),
            body_resource_object_impact_acoustic_emission=_oia_config_from_snapshot(configs),
            physical_resource_object_pair_contact=_ooc_config_from_snapshot(configs),
            resource_object_pair_contact_impulse=_ooi_config_from_snapshot(configs),
            resource_object_pair_impact_acoustic_emission=_ooia_config_from_snapshot(configs),
            held_resource_object_foreign_body_contact=_hfc_config_from_snapshot(configs),
            held_resource_object_translational_impulse_mediation=_hti_config_from_snapshot(configs),
            effector_work_and_held_load_inertia_accounting=_ehl_config_from_snapshot(configs),
            flat_ground_gravity=_fgg_config_from_snapshot(configs),
            free_resource_object_ground_friction=_fogf_config_from_snapshot(configs),
            surface_elevation_support=_ses_config_from_snapshot(configs),
            body_normal_load_traction=_bnlt_config_from_snapshot(configs),
            continuous_surface_geometry=_csg_config_from_snapshot(configs),
            body_static_traction_threshold=_bst_config_from_snapshot(configs),
            free_resource_object_static_traction_threshold=_fost_config_from_snapshot(configs),
            radius_aware_support_points=_rasp_config_from_snapshot(configs),
            ses_decomposition_contract=_sdc_config_from_snapshot(configs),
            ses_runtime_transition_classifier=_srtc_config_from_snapshot(configs),
            radius_aware_face_sweep=_rafs_config_from_snapshot(configs),
            diagnostic_normal_load_shadow=_dnls_config_from_snapshot(configs),
            continuous_gravitational_pe_diagnostic_shadow=_cgpe_config_from_snapshot(configs),
            continuous_gravitational_pe=_cgp_config_from_snapshot(configs),
            tangent_gravity_diagnostic_shadow=_tgds_config_from_snapshot(configs),
            coherent_slope_dynamics=_csd_config_from_snapshot(configs),
            conservative_surface_material_separation=_csms_config_from_snapshot(configs),
            effector_terrain_contact_geometry=_etc_config_from_snapshot(configs),
            effector_occupancy_reachability_trace=_eort_config_from_snapshot(configs),
            manipulator_relative_world_actuation=_mrwa_config_from_snapshot(configs),
            effector_bounded_actuator_effort=_ebae_config_from_snapshot(configs),
            surface_exertion_terrain_material_resistance=_setmr_config_from_snapshot(configs),
            held_resource_object_terrain_contact_geometry=_hotc_config_from_snapshot(configs),
            held_resource_object_terrain_mechanical_transmission=_hotmt_config_from_snapshot(configs),
            held_mediated_surface_exertion_integration=_hmsi_config_from_snapshot(configs),
            detached_terrain_material_initial_placement=_dtip_config_from_snapshot(configs),
            bnlt_move_breakaway_locomotion_repair=_bnlt_repair_config_from_snapshot(configs),
            repeated_conservative_surface_column_separation=_rcss_config_from_snapshot(configs),
            event_driven_crowded_placement_retry_contract=_crowded_retry_config_from_snapshot(configs),
            detached_material_amount_scaled_collision_radius=_detached_material_size_geometry_config_from_snapshot(configs),
            held_combine_radius_resize_transaction=_held_combine_radius_resize_transaction_config_from_snapshot(configs),
            held_deposition_radius_shrink_transaction=_held_deposition_radius_shrink_transaction_config_from_snapshot(configs),
            free_space_state_and_pe_authority_contract=_free_space_state_and_pe_authority_contract_config_from_snapshot(configs),
            vertical_terrain_landing_contact_response=_vertical_terrain_landing_contact_response_config_from_snapshot(configs),
            vertical_impact_acoustic_emission=_vertical_impact_acoustic_emission_config_from_snapshot(configs),
            release_and_excavation_support_loss_integration=_release_and_excavation_support_loss_integration_config_from_snapshot(configs),
            cognition=cog_cfg,
        )
        raw_vw6 = configs.get("minimal_vision_3d_geometric_interface")
        if isinstance(raw_vw6, dict) and raw_vw6:
            from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
                MinimalVision3DGeometricInterfaceConfig,
            )
            config.minimal_vision_3d_geometric_interface = (
                MinimalVision3DGeometricInterfaceConfig.from_dict(raw_vw6)
            )
            # VW6 requires VW1 occupancy authority.
            from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
                set_volumetric_world_material_occupancy,
            )
            set_volumetric_world_material_occupancy(config, True)
        raw_o2 = configs.get("exposed_surface_optical_interaction_authority")
        if isinstance(raw_o2, dict) and raw_o2:
            config.exposed_surface_optical_interaction_authority = (
                ExposedSurfaceOpticalInteractionAuthorityConfig.from_dict(raw_o2)
            )
            if bool(raw_o2.get("enabled", False)):
                from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
                    set_volumetric_world_material_occupancy,
                )
                set_volumetric_world_material_occupancy(config, True)
        raw_o3 = configs.get("abstract_spectral_light_source_and_direct_transport")
        if isinstance(raw_o3, dict) and raw_o3:
            config.abstract_spectral_light_source_and_direct_transport = (
                AbstractSpectralLightSourceAndDirectTransportConfig.from_dict(raw_o3)
            )
            if bool(raw_o3.get("enabled", False)):
                from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
                    set_volumetric_world_material_occupancy,
                )
                from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
                    set_exposed_surface_optical_interaction_authority,
                )
                from mechanistic_mind.physical_system.physical_optical_material_profile import (
                    set_physical_optical_material_profile,
                )

                set_volumetric_world_material_occupancy(config, True)
                set_physical_optical_material_profile(config, True)
                set_exposed_surface_optical_interaction_authority(config, True)
        raw_o3a = configs.get("object_body_held_optical_surfaces")
        if isinstance(raw_o3a, dict) and raw_o3a:
            config.object_body_held_optical_surfaces = (
                ObjectBodyHeldOpticalSurfacesConfig.from_dict(raw_o3a)
            )
            if bool(raw_o3a.get("enabled", False)):
                from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
                    set_object_body_held_optical_surfaces,
                )
                from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
                    set_abstract_spectral_light_source_and_direct_transport,
                )
                set_abstract_spectral_light_source_and_direct_transport(config, True)
                set_object_body_held_optical_surfaces(config, True)
        raw_o4 = configs.get("organism_physical_optical_reception")
        if isinstance(raw_o4, dict) and raw_o4:
            config.organism_physical_optical_reception = (
                OrganismPhysicalOpticalReceptionConfig.from_dict(raw_o4)
            )
            if bool(raw_o4.get("enabled", False)):
                from mechanistic_mind.physical_system.organism_physical_optical_reception import (
                    set_organism_physical_optical_reception,
                )
                from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
                    set_object_body_held_optical_surfaces,
                )
                from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
                    set_abstract_spectral_light_source_and_direct_transport,
                )
                set_abstract_spectral_light_source_and_direct_transport(config, True)
                set_object_body_held_optical_surfaces(config, True)
                set_organism_physical_optical_reception(config, True)
        raw_o5 = configs.get("sensory_modality_temporal_alignment")
        if isinstance(raw_o5, dict) and raw_o5:
            config.sensory_modality_temporal_alignment = (
                SensoryModalityTemporalAlignmentConfig.from_dict(raw_o5)
            )
            if bool(raw_o5.get("enabled", False)):
                from mechanistic_mind.physical_system.sensory_modality_temporal_alignment import (
                    set_sensory_modality_temporal_alignment,
                )
                set_sensory_modality_temporal_alignment(config, True)
        runtime = cls(seed=int(payload["seed"]), config=config)
        runtime.world, runtime.config.planet = restore_planet_state(payload["world"])
        try:
            from mechanistic_mind.ui.psy_observer_web.vertical_display_contract import (
                invalidate_vertical_display_cache,
            )

            invalidate_vertical_display_cache(runtime.world)
        except Exception:
            pass
        try:
            from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
                invalidate_exposed_surface_cache,
            )
            from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
                invalidate_direct_light_cache,
            )

            invalidate_exposed_surface_cache(runtime.world)
            invalidate_direct_light_cache(runtime.world)
            from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
                invalidate_entity_surface_cache,
            )
            invalidate_entity_surface_cache(runtime.world)
        except Exception:
            pass
        b = payload["body"]
        runtime.body = PhysicalBodyState(
            tick=int(b["tick"]), x=float(b["x"]), y=float(b["y"]),
            vx=float(b["vx"]), vy=float(b["vy"]), T=float(b["T"]),
            B=np.asarray(b["B"], dtype=np.float64),
            B_core=np.asarray(b["B_core"], dtype=np.float64), mech=float(b["mech"]),
            motor_ux=float(b.get("motor_ux", 0.0)), motor_uy=float(b.get("motor_uy", 0.0)),
            B_site=None if b.get("B_site") is None else np.asarray(b["B_site"], dtype=np.float64),
            theta=float(b.get("theta", 0.0)), omega=float(b.get("omega", 0.0)),
            z=float(b.get("z", 0.0) or 0.0), vz=float(b.get("vz", 0.0) or 0.0),
            grounded=bool(b["grounded"]) if "grounded" in b else True,
            vertical_half_extent=(float(b["vertical_half_extent"]) if b.get("vertical_half_extent") is not None else None),
            head_relative_angle=float(b.get("head_relative_angle", 0.0) or 0.0),
            head_omega=float(b.get("head_omega", 0.0) or 0.0),
            neck_motor=float(b.get("neck_motor", 0.0) or 0.0),
            push_exertion=float(b.get("push_exertion", 0.0) or 0.0),
            osc_freq_u=float(b.get("osc_freq_u", 0.5) or 0.5),
            osc_amp_u=float(b.get("osc_amp_u", 0.5) or 0.5),
            osc_emit_remaining=int(b.get("osc_emit_remaining", 0) or 0),
            osc_emit_active=float(b.get("osc_emit_active", 0.0) or 0.0),
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
            if isinstance(runtime.cognition, dict):
                clear_derived_indexes(runtime.cognition)
        else:
            runtime.cognition = empty_cognitive_state(runtime.config.cognition)
        # Restore PSC schedule activation flags (must not re-fire or drop absolute enable tick).
        sched = payload.get("psc_schedule") if isinstance(payload.get("psc_schedule"), dict) else None
        if sched is not None:
            runtime._psc_auto_activated = bool(sched.get("psc_auto_activated", False))
            runtime._psc_activation = deepcopy(sched.get("psc_activation"))
            runtime._psc_withhold_open = deepcopy(sched.get("psc_withhold_open"))
            runtime._psc_schedule_legacy_status = "OK"
        else:
            runtime._psc_auto_activated = bool(payload.get("psc_auto_activated", False))
            runtime._psc_activation = deepcopy(payload.get("psc_activation"))
            runtime._psc_withhold_open = deepcopy(payload.get("psc_withhold_open"))
            runtime._psc_schedule_legacy_status = (
                "LEGACY_MISSING_PSC_OFF_TICKS_EXPLICIT_STATUS_NOT_SILENT_DEFAULT"
                if legacy_psc_off_ticks
                else "OK"
            )
        # Keep live cognition.config aligned with restored CognitionConfig schedule fields.
        if isinstance(runtime.cognition, dict):
            cfgd = runtime.cognition.setdefault("config", {})
            if isinstance(cfgd, dict):
                cfgd["psc_off_ticks"] = getattr(runtime.config.cognition, "psc_off_ticks", None)
                cfgd["prospective_selection"] = str(
                    getattr(runtime.config.cognition, "prospective_selection", "") or ""
                )
                cfgd["sensorimotor_consequence_withhold_from_psc"] = bool(
                    getattr(
                        runtime.config.cognition,
                        "sensorimotor_consequence_withhold_from_psc",
                        True,
                    )
                )
        runtime.last_agent_observation = deepcopy(payload.get("last_agent_observation"))
        runtime.last_selected_action = payload.get("last_selected_action")
        runtime.last_motor_output = deepcopy(payload.get("last_motor_output"))
        runtime.last_manipulator_receipt = deepcopy(payload.get("last_manipulator_receipt"))
        runtime.last_pair_receipt = deepcopy(payload.get("last_pair_receipt"))
        runtime.last_material_transformation_receipt = deepcopy(payload.get("last_material_transformation_receipt"))
        runtime.last_surface_deposition_receipt = deepcopy(payload.get("last_surface_deposition_receipt"))
        runtime.last_surface_traction_receipt = deepcopy(payload.get("last_surface_traction_receipt"))
        runtime.last_traction_experience_receipt = deepcopy(payload.get("last_traction_experience_receipt"))
        runtime._traction_experience_pending = deepcopy(payload.get("traction_experience_pending"))
        runtime.traction_experience_history = list(deepcopy(payload.get("traction_experience_history") or []))
        closed = payload.get("traction_experience_closed_tick")
        runtime._traction_experience_closed_tick = None if closed is None else int(closed)
        runtime.last_traction_prediction_receipt = deepcopy(payload.get("last_traction_prediction_receipt"))
        runtime._traction_prediction_pending = deepcopy(payload.get("traction_prediction_pending"))
        runtime.traction_prediction_history = list(deepcopy(payload.get("traction_prediction_history") or []))
        pred_closed = payload.get("traction_prediction_closed_tick")
        runtime._traction_prediction_closed_tick = None if pred_closed is None else int(pred_closed)
        runtime._traction_prediction_episode_index = int(payload.get("traction_prediction_episode_index") or 0)
        runtime.traction_adaptation_phase = str(payload.get("traction_adaptation_phase") or "UNSPECIFIED")
        runtime.last_surface_optical_coating_receipt = deepcopy(
            payload.get("last_surface_optical_coating_receipt")
        )
        runtime.surface_optical_coating_history = list(
            deepcopy(payload.get("surface_optical_coating_history") or [])
        )
        if payload.get("pair_aperture") is None:
            runtime.pair_aperture = open_pair_aperture(runtime.config)
            runtime.pair_state = "OPEN"
            runtime.pair_contact = False
        else:
            runtime.pair_aperture = float(payload.get("pair_aperture") or open_pair_aperture(runtime.config))
            runtime.pair_state = str(payload.get("pair_state") or "OPEN")
            runtime.pair_contact = bool(payload.get("pair_contact"))
        runtime.technical_id = str(payload.get("technical_id") or "agent_0")
        runtime._internal_c_prev = (
            None
            if payload.get("internal_c_prev") is None
            else np.asarray(payload["internal_c_prev"], dtype=np.float64)
        )
        runtime._prev_body_omega = float(payload.get("prev_body_omega", 0.0) or 0.0)
        runtime.last_orientation_meta = deepcopy(payload.get("last_orientation_meta"))
        runtime._sync_embodiment_dofs()
        from mechanistic_mind.physical_system.physical_manipulator import sanitize_attachments
        if not shared_world_member:
            sanitize_attachments(runtime.world, {str(runtime.technical_id)})
        if not (runtime.tick == runtime.world.tick == runtime.body.tick == runtime.internal.tick):
            raise ValueError("snapshot contains incoherent physical ticks")
        nfe = runtime.config.near_field_exteroception
        if (
            nfe is not None
            and nfe.enabled
            and nfe.surface_discrimination != "OFF"
            and getattr(runtime.world, "surface_optical", None) is None
        ):
            from mechanistic_mind.physical_system.near_field_exteroception import (
                install_surface_optical_on_planet,
            )
            install_surface_optical_on_planet(
                runtime.world, experiment_seed=runtime.seed, cfg=nfe
            )
        from mechanistic_mind.physical_system.spatial_contents import (
            body_refs_for_runtime,
            multi_content_spatial_index_is_active,
            rebuild_from_world,
        )
        saved_generation = int(getattr(runtime.world, "spatial_index_generation", 0) or 0)
        if multi_content_spatial_index_is_active(runtime.config) and not shared_world_member:
            rebuild_from_world(
                runtime.world,
                body_refs_for_runtime(runtime),
                tick=int(runtime.tick),
                reason="restore",
                config=runtime.config,
            )
            if saved_generation:
                runtime.world.spatial_contents.generation = saved_generation
                runtime.world.spatial_index_generation = saved_generation
        from mechanistic_mind.physical_system.procedural_surface_columns import (
            ensure_surface_columns_for_runtime,
        )
        # Shared-world containers (two-agent) pass the world seed; slot seeds are agent streams.
        ensure_surface_columns_for_runtime(
            runtime.world, runtime.config,
            experiment_seed=runtime.seed if world_seed is None else int(world_seed),
        )
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            ensure_state as ensure_volumetric_occupancy_for_runtime,
        )
        ensure_volumetric_occupancy_for_runtime(runtime.world, runtime.config)
        from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
            ensure_state as ensure_occupancy_support_contact_for_runtime,
        )
        ensure_occupancy_support_contact_for_runtime(runtime.world, runtime.config)
        from mechanistic_mind.physical_system.volumetric_world_material_separation import (
            ensure_state as ensure_volumetric_separation_for_runtime,
        )
        ensure_volumetric_separation_for_runtime(runtime.world, runtime.config)
        from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
            ensure_state as ensure_volumetric_reintegration_for_runtime,
        )
        ensure_volumetric_reintegration_for_runtime(runtime.world, runtime.config)
        from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
            ensure_state as ensure_vw5_bridge_for_runtime,
        )
        ensure_vw5_bridge_for_runtime(runtime.world, runtime.config)
        from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
            ensure_state as ensure_vw6_vision_for_runtime,
        )
        ensure_vw6_vision_for_runtime(runtime.world, runtime.config)
        setattr(runtime.world, "_physical_system_config", runtime.config)
        from mechanistic_mind.physical_system.local_physical_signal_transport import (
            bind_body_ids,
            local_physical_signal_transport_is_active as _lps_active,
            restore_state as _lps_restore,
        )
        raw_lps = getattr(runtime.world, "_local_signal_transport_payload", None)
        if raw_lps is not None:
            try:
                del runtime.world._local_signal_transport_payload
            except AttributeError:
                pass
        if _lps_active(runtime.config) or raw_lps:
            # Missing snapshot field -> config None -> OFF; state without config -> dropped.
            _lps_restore(runtime.world, raw_lps, runtime.config)
            if getattr(runtime.world, "local_signal_transport", None) is not None:
                bind_body_ids(body_refs_for_runtime(runtime))
        from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
            physical_contact_acoustic_emission_is_active as _pca_active,
            restore_state as _pca_restore,
        )
        raw_pca = getattr(runtime.world, "_contact_acoustic_payload", None)
        if raw_pca is not None:
            try:
                del runtime.world._contact_acoustic_payload
            except AttributeError:
                pass
        if _pca_active(runtime.config) or raw_pca:
            # Missing snapshot field -> config None -> OFF (no retroactive sounds).
            _pca_restore(runtime.world, raw_pca, runtime.config)
        from mechanistic_mind.physical_system.free_resource_object_kinematics import (
            restore_state as _fok_restore,
        )
        raw_fok = getattr(runtime.world, "_free_object_kinematics_payload", None)
        if raw_fok is not None:
            try:
                del runtime.world._free_object_kinematics_payload
            except AttributeError:
                pass
        # Always: OFF (every older snapshot) -> no state, any free object at rest with v = 0;
        # ON without saved state -> fresh state with empty effector pose history (no false impulse).
        _fok_restore(runtime.world, raw_fok, runtime.config)
        from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
            restore_state as _boc_restore,
        )
        raw_boc = getattr(runtime.world, "_body_object_contact_payload", None)
        if raw_boc is not None:
            try:
                del runtime.world._body_object_contact_payload
            except AttributeError:
                pass
        # Missing snapshot -> OFF; ON without saved state -> fresh episodes (no false BEGIN on restore).
        _boc_restore(runtime.world, raw_boc, runtime.config)
        from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
            restore_state as _boi_restore,
        )
        raw_boi = getattr(runtime.world, "_body_object_contact_impulse_payload", None)
        if raw_boi is not None:
            try:
                del runtime.world._body_object_contact_impulse_payload
            except AttributeError:
                pass
        _boi_restore(runtime.world, raw_boi, runtime.config)
        from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
            restore_state as _oia_restore,
        )
        raw_oia = getattr(runtime.world, "_body_object_impact_acoustic_payload", None)
        if raw_oia is not None:
            try:
                del runtime.world._body_object_impact_acoustic_payload
            except AttributeError:
                pass
        # Also accept top-level snapshot key written alongside config.
        if raw_oia is None and isinstance(payload.get("body_object_impact_acoustic_state"), dict):
            raw_oia = payload.get("body_object_impact_acoustic_state")
        _oia_restore(runtime.world, raw_oia, runtime.config)
        from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
            restore_state as _ooc_restore,
        )
        raw_ooc = getattr(runtime.world, "_resource_object_pair_contact_payload", None)
        if raw_ooc is not None:
            try:
                del runtime.world._resource_object_pair_contact_payload
            except AttributeError:
                pass
        if raw_ooc is None and isinstance(payload.get("resource_object_pair_contact_state"), dict):
            raw_ooc = payload.get("resource_object_pair_contact_state")
        _ooc_restore(runtime.world, raw_ooc, runtime.config)
        from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
            restore_state as _ooi_restore,
        )
        raw_ooi = getattr(runtime.world, "_resource_object_pair_contact_impulse_payload", None)
        if raw_ooi is not None:
            try:
                del runtime.world._resource_object_pair_contact_impulse_payload
            except AttributeError:
                pass
        if raw_ooi is None and isinstance(payload.get("resource_object_pair_contact_impulse_state"), dict):
            raw_ooi = payload.get("resource_object_pair_contact_impulse_state")
        _ooi_restore(runtime.world, raw_ooi, runtime.config)
        from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
            restore_state as _ooia_restore,
        )
        raw_ooia = getattr(runtime.world, "_resource_object_pair_impact_acoustic_payload", None)
        if raw_ooia is not None:
            try:
                del runtime.world._resource_object_pair_impact_acoustic_payload
            except AttributeError:
                pass
        if raw_ooia is None and isinstance(payload.get("resource_object_pair_impact_acoustic_state"), dict):
            raw_ooia = payload.get("resource_object_pair_impact_acoustic_state")
        _ooia_restore(runtime.world, raw_ooia, runtime.config)
        from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
            restore_state as _hfc_restore,
        )
        raw_hfc = getattr(runtime.world, "_held_foreign_body_contact_payload", None)
        if raw_hfc is not None:
            try:
                del runtime.world._held_foreign_body_contact_payload
            except AttributeError:
                pass
        if raw_hfc is None and isinstance(payload.get("held_foreign_body_contact_state"), dict):
            raw_hfc = payload.get("held_foreign_body_contact_state")
        _hfc_restore(runtime.world, raw_hfc, runtime.config)
        from mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation import (
            restore_state as _hti_restore,
        )
        raw_hti = getattr(runtime.world, "_held_translational_impulse_payload", None)
        if raw_hti is not None:
            try:
                del runtime.world._held_translational_impulse_payload
            except Exception:
                pass
        if raw_hti is None and isinstance(payload.get("held_translational_impulse_state"), dict):
            raw_hti = payload.get("held_translational_impulse_state")
        _hti_restore(runtime.world, raw_hti, runtime.config)
        from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
            restore_state as _ehl_restore,
        )
        raw_ehl = getattr(runtime.world, "_effector_work_held_load_payload", None)
        if raw_ehl is not None:
            try:
                del runtime.world._effector_work_held_load_payload
            except Exception:
                pass
        if raw_ehl is None and isinstance(payload.get("effector_work_held_load_state"), dict):
            raw_ehl = payload.get("effector_work_held_load_state")
        _ehl_restore(runtime.world, raw_ehl, runtime.config)
        from mechanistic_mind.physical_system.flat_ground_gravity import (
            restore_state as _fgg_restore,
            ensure_body_vertical as _fgg_ensure_body,
            flat_ground_gravity_is_active as _fgg_active,
        )
        raw_fgg = getattr(runtime.world, "_flat_ground_gravity_payload", None)
        if raw_fgg is not None:
            try:
                del runtime.world._flat_ground_gravity_payload
            except Exception:
                pass
        if raw_fgg is None and isinstance(payload.get("flat_ground_gravity_state"), dict):
            raw_fgg = payload.get("flat_ground_gravity_state")
        _fgg_restore(runtime.world, raw_fgg, runtime.config)
        # Gate: do NOT inject z/vz/grounded/vertical_half_extent into legacy
        # Tiktaalik / pre-FGG snapshots. Migrate only when FGG/Phase C vertical
        # is active, or when vertical fields are already present in the body snap.
        _bpayload_gate = payload.get("body") or {}
        _vertical_already = any(
            k in _bpayload_gate for k in ("z", "vz", "grounded", "vertical_half_extent")
        )
        if _fgg_active(runtime.config) or _vertical_already:
            _fgg_ensure_body(runtime.body, runtime.config)
        from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
            restore_state as _fogf_restore,
        )
        raw_fogf = getattr(runtime.world, "_free_resource_object_ground_friction_payload", None)
        if raw_fogf is not None:
            try:
                del runtime.world._free_resource_object_ground_friction_payload
            except Exception:
                pass
        if raw_fogf is None and isinstance(payload.get("free_resource_object_ground_friction_state"), dict):
            raw_fogf = payload.get("free_resource_object_ground_friction_state")
        _fogf_restore(runtime.world, raw_fogf, runtime.config)
        from mechanistic_mind.physical_system.surface_elevation_support import (
            restore_state as _ses_restore,
        )
        raw_ses = getattr(runtime.world, "_surface_elevation_support_payload", None)
        if raw_ses is not None:
            try:
                del runtime.world._surface_elevation_support_payload
            except Exception:
                pass
        if raw_ses is None and isinstance(payload.get("surface_elevation_support_state"), dict):
            raw_ses = payload.get("surface_elevation_support_state")
        if raw_ses is not None:
            _ses_restore(runtime.world, raw_ses, runtime.config)
        from mechanistic_mind.physical_system.body_normal_load_traction import (
            restore_state as _bnlt_restore,
        )
        raw_bnlt = getattr(runtime.world, "_body_normal_load_traction_payload", None)
        if raw_bnlt is not None:
            try:
                del runtime.world._body_normal_load_traction_payload
            except Exception:
                pass
        if raw_bnlt is None and isinstance(payload.get("body_normal_load_traction_state"), dict):
            raw_bnlt = payload.get("body_normal_load_traction_state")
        _bnlt_restore(runtime.world, raw_bnlt, runtime.config)
        from mechanistic_mind.physical_system.continuous_surface_geometry import (
            restore_state as _csg_restore,
        )
        raw_csg = getattr(runtime.world, "_continuous_surface_geometry_payload", None)
        if raw_csg is not None:
            try:
                del runtime.world._continuous_surface_geometry_payload
            except Exception:
                pass
        if raw_csg is None and isinstance(payload.get("continuous_surface_geometry_state"), dict):
            raw_csg = payload.get("continuous_surface_geometry_state")
        _csg_restore(runtime.world, runtime.config, raw_csg)
        from mechanistic_mind.physical_system.body_static_traction_threshold import (
            restore_state as _bst_restore,
        )
        raw_bst = getattr(runtime.world, "_body_static_traction_threshold_payload", None)
        if raw_bst is not None:
            try:
                del runtime.world._body_static_traction_threshold_payload
            except Exception:
                pass
        if raw_bst is None and isinstance(payload.get("body_static_traction_threshold_state"), dict):
            raw_bst = payload.get("body_static_traction_threshold_state")
        _bst_restore(runtime.world, raw_bst, runtime.config)
        from mechanistic_mind.physical_system.free_resource_object_static_traction_threshold import (
            restore_state as _fost_restore,
        )
        raw_fost = getattr(runtime.world, "_free_resource_object_static_traction_threshold_payload", None)
        if raw_fost is not None:
            try:
                del runtime.world._free_resource_object_static_traction_threshold_payload
            except Exception:
                pass
        if raw_fost is None and isinstance(payload.get("free_resource_object_static_traction_threshold_state"), dict):
            raw_fost = payload.get("free_resource_object_static_traction_threshold_state")
        _fost_restore(runtime.world, raw_fost, runtime.config)
        from mechanistic_mind.physical_system.radius_aware_support_points import (
            restore_state as _rasp_restore,
        )
        raw_rasp = getattr(runtime.world, "_radius_aware_support_points_payload", None)
        if raw_rasp is not None:
            try:
                del runtime.world._radius_aware_support_points_payload
            except Exception:
                pass
        if raw_rasp is None and isinstance(payload.get("radius_aware_support_points_state"), dict):
            raw_rasp = payload.get("radius_aware_support_points_state")
        _rasp_restore(runtime.world, raw_rasp, runtime.config)
        from mechanistic_mind.physical_system.ses_decomposition_contract import (
            restore_state as _sdc_restore,
        )
        raw_sdc = payload.get("ses_decomposition_contract_state")
        _sdc_restore(runtime.world, raw_sdc if isinstance(raw_sdc, dict) else None, runtime.config)
        from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
            restore_state as _srtc_restore,
        )
        raw_srtc = payload.get("ses_runtime_transition_classifier_state")
        _srtc_restore(runtime.world, raw_srtc if isinstance(raw_srtc, dict) else None, runtime.config)
        from mechanistic_mind.physical_system.radius_aware_face_sweep import (
            restore_state as _rafs_restore,
        )
        raw_rafs = payload.get("radius_aware_face_sweep_state")
        _rafs_restore(runtime.world, raw_rafs if isinstance(raw_rafs, dict) else None, runtime.config)
        from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
            restore_state as _dnls_restore,
        )
        raw_dnls = payload.get("diagnostic_normal_load_shadow_state")
        _dnls_restore(runtime.world, raw_dnls if isinstance(raw_dnls, dict) else None, runtime.config)
        from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
            restore_state as _cgpe_restore,
        )
        raw_cgpe = payload.get("continuous_gravitational_pe_diagnostic_shadow_state")
        _cgpe_restore(runtime.world, raw_cgpe if isinstance(raw_cgpe, dict) else None, runtime.config)
        from mechanistic_mind.physical_system.continuous_gravitational_pe import (
            restore_state as _cgp_restore,
        )
        raw_cgp = payload.get("continuous_gravitational_pe_state")
        _cgp_restore(runtime.world, raw_cgp if isinstance(raw_cgp, dict) else None, runtime.config)
        from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
            restore_state as _tgds_restore,
        )
        raw_tgds = payload.get("tangent_gravity_diagnostic_shadow_state")
        _tgds_restore(runtime.world, raw_tgds if isinstance(raw_tgds, dict) else None, runtime.config)
        from mechanistic_mind.physical_system.coherent_slope_dynamics import (
            restore_state as _csd_restore,
        )
        raw_csd = payload.get("coherent_slope_dynamics_state")
        _csd_restore(runtime.world, raw_csd if isinstance(raw_csd, dict) else None, runtime.config)
        from mechanistic_mind.physical_system.conservative_surface_material_separation import (
            restore_state as _csms_restore,
        )
        raw_csms = payload.get("surface_material_separation_state")
        _csms_restore(runtime.world, raw_csms if isinstance(raw_csms, dict) else None)
        from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
            restore_state as _etc_restore,
        )
        raw_etc = payload.get("effector_terrain_contact_geometry_state")
        _etc_restore(
            runtime.world,
            raw_etc if isinstance(raw_etc, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.effector_occupancy_reachability_trace import (
            restore_state as _eort_restore,
        )
        raw_eort = payload.get("effector_occupancy_reachability_trace_state")
        _eort_restore(
            runtime.world,
            raw_eort if isinstance(raw_eort, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
            restore_state as _mrwa_restore,
        )
        raw_mrwa = payload.get("manipulator_relative_world_actuation_state")
        _mrwa_restore(
            runtime.world,
            raw_mrwa if isinstance(raw_mrwa, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
            restore_state as _ebae_restore,
        )
        raw_ebae = payload.get("effector_bounded_actuator_effort_state")
        _ebae_restore(
            runtime.world,
            raw_ebae if isinstance(raw_ebae, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
            restore_state as _setmr_restore,
        )
        raw_setmr = payload.get("surface_exertion_terrain_material_resistance_state")
        _setmr_restore(
            runtime.world,
            raw_setmr if isinstance(raw_setmr, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
            restore_state as _hotc_restore,
        )
        raw_hotc = payload.get("held_resource_object_terrain_contact_geometry_state")
        _hotc_restore(
            runtime.world,
            raw_hotc if isinstance(raw_hotc, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
            restore_state as _hotmt_restore,
        )
        raw_hotmt = payload.get("held_resource_object_terrain_mechanical_transmission_state")
        _hotmt_restore(
            runtime.world,
            raw_hotmt if isinstance(raw_hotmt, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
            restore_state as _hmsi_restore,
        )
        raw_hmsi = payload.get("held_mediated_surface_exertion_integration_state")
        _hmsi_restore(
            runtime.world,
            raw_hmsi if isinstance(raw_hmsi, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
            restore_state as _dtip_restore,
        )
        raw_dtip = payload.get("detached_terrain_material_initial_placement_state")
        _dtip_restore(
            runtime.world,
            raw_dtip if isinstance(raw_dtip, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
            restore_state as _bnlt_rep_restore,
        )
        raw_bnlt_rep = payload.get("bnlt_move_breakaway_locomotion_repair_state")
        _bnlt_rep_restore(
            runtime.world,
            raw_bnlt_rep if isinstance(raw_bnlt_rep, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
            restore_state as _rcss_restore,
        )
        raw_rcss = payload.get("repeated_conservative_surface_column_separation_state")
        _rcss_restore(
            runtime.world,
            raw_rcss if isinstance(raw_rcss, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
            restore_state as _crowded_restore,
        )
        raw_crowded = payload.get("event_driven_crowded_placement_retry_contract_state")
        _crowded_restore(
            runtime.world,
            raw_crowded if isinstance(raw_crowded, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
            restore_state as _size_geo_restore,
        )
        raw_size_geo = payload.get("detached_material_amount_scaled_collision_radius_state")
        _size_geo_restore(
            runtime.world,
            raw_size_geo if isinstance(raw_size_geo, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
            restore_state as _held_combine_restore,
        )
        raw_held_combine = payload.get("held_combine_radius_resize_transaction_state")
        _held_combine_restore(
            runtime.world,
            raw_held_combine if isinstance(raw_held_combine, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction import (
            restore_state as _held_deposition_restore,
        )
        raw_held_deposition = payload.get("held_deposition_radius_shrink_transaction_state")
        _held_deposition_restore(
            runtime.world,
            raw_held_deposition if isinstance(raw_held_deposition, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
            restore_state as _fs_restore,
        )
        raw_fs = payload.get("free_space_state_and_pe_authority_contract_state")
        _fs_restore(
            runtime.world,
            raw_fs if isinstance(raw_fs, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
            restore_state as _vtl_restore,
        )
        raw_vtl = payload.get("vertical_terrain_landing_contact_response_state")
        _vtl_restore(
            runtime.world,
            raw_vtl if isinstance(raw_vtl, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
            restore_state as _via_restore,
        )
        raw_via = payload.get("vertical_impact_acoustic_emission_state")
        _via_restore(
            runtime.world,
            raw_via if isinstance(raw_via, dict) else None,
            runtime.config,
        )
        from mechanistic_mind.physical_system.authoritative_physical_acoustic_stream_contract import (
            restore_state as _apas_restore,
            rebuild_stream_from_histories as _apas_rebuild,
            state_of as _apas_state_of,
        )
        raw_apas = getattr(runtime.world, "_authoritative_physical_acoustic_stream_payload", None)
        if raw_apas is not None:
            try:
                del runtime.world._authoritative_physical_acoustic_stream_payload
            except AttributeError:
                pass
        if raw_apas is None and isinstance(payload.get("authoritative_physical_acoustic_stream_state"), dict):
            raw_apas = payload.get("authoritative_physical_acoustic_stream_state")
        if isinstance(raw_apas, dict):
            _apas_restore(runtime.world, raw_apas)
        elif getattr(runtime.world, "local_signal_transport", None) is not None:
            # Older snapshots: rebuild from restored mechanism/LPS histories (no re-emit).
            _apas_rebuild(runtime.world)
        # Restore must never enqueue into LPS; seen_emission_ids prevent stream duplicates.
        _ = _apas_state_of(runtime.world)
        from mechanistic_mind.physical_system.observer_acoustic_probe import (
            restore_state as _oap_restore,
        )
        raw_oap = getattr(runtime.world, "_observer_acoustic_probe_payload", None)
        if raw_oap is not None:
            try:
                del runtime.world._observer_acoustic_probe_payload
            except AttributeError:
                pass
        if raw_oap is None and isinstance(payload.get("observer_acoustic_probe_state"), dict):
            raw_oap = payload.get("observer_acoustic_probe_state")
        if isinstance(raw_oap, dict):
            # Restore config + history only; do not re-sample old ticks.
            _oap_restore(runtime.world, raw_oap)
        from mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt import (
            restore_state as _soab_restore,
        )
        raw_soab = getattr(runtime.world, "_selected_organism_auditory_boundary_payload", None)
        if raw_soab is not None:
            try:
                del runtime.world._selected_organism_auditory_boundary_payload
            except AttributeError:
                pass
        if raw_soab is None and isinstance(
            payload.get("selected_organism_auditory_boundary_state"), dict
        ):
            raw_soab = payload.get("selected_organism_auditory_boundary_state")
        if isinstance(raw_soab, dict):
            # History only; never replay into cognition / LPS / playback.
            _soab_restore(runtime.world, raw_soab)
        from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
            restore_state as _sovv_restore,
        )
        raw_sovv = getattr(runtime.world, "_selected_organism_volumetric_vision_payload", None)
        if raw_sovv is not None:
            try:
                del runtime.world._selected_organism_volumetric_vision_payload
            except AttributeError:
                pass
        if raw_sovv is None and isinstance(
            payload.get("selected_organism_volumetric_vision_state"), dict
        ):
            raw_sovv = payload.get("selected_organism_volumetric_vision_state")
        if isinstance(raw_sovv, dict):
            # History only; never regenerate perception or alter cognition.
            _sovv_restore(runtime.world, raw_sovv)
        from mechanistic_mind.physical_system.organism_receptor_grounded_3d_fpv import (
            restore_state as _fpv_restore,
        )
        raw_fpv = getattr(runtime.world, "_organism_receptor_grounded_3d_fpv_payload", None)
        if raw_fpv is not None:
            try:
                del runtime.world._organism_receptor_grounded_3d_fpv_payload
            except AttributeError:
                pass
        if raw_fpv is None and isinstance(
            payload.get("organism_receptor_grounded_3d_fpv_state"), dict
        ):
            raw_fpv = payload.get("organism_receptor_grounded_3d_fpv_state")
        if isinstance(raw_fpv, dict):
            # Researcher FPV state only; restore does not create a new observation.
            _fpv_restore(runtime.world, raw_fpv)
        from mechanistic_mind.physical_system.organism_auditory_transformation_trace import (
            restore_state as _oatt_restore,
        )
        raw_oatt = getattr(runtime.world, "_organism_auditory_transformation_trace_payload", None)
        if raw_oatt is not None:
            try:
                del runtime.world._organism_auditory_transformation_trace_payload
            except AttributeError:
                pass
        if raw_oatt is None and isinstance(
            payload.get("organism_auditory_transformation_trace_state"), dict
        ):
            raw_oatt = payload.get("organism_auditory_transformation_trace_state")
        if isinstance(raw_oatt, dict):
            # History only; never regenerate A3, SAV1, LPS, or playback.
            _oatt_restore(runtime.world, raw_oatt)
        from mechanistic_mind.physical_system.sensory_modality_temporal_alignment import (
            restore_state as _o5_restore,
        )
        raw_o5s = getattr(runtime.world, "_sensory_modality_temporal_alignment_payload", None)
        if raw_o5s is not None:
            try:
                del runtime.world._sensory_modality_temporal_alignment_payload
            except AttributeError:
                pass
        if raw_o5s is None and isinstance(
            payload.get("sensory_modality_temporal_alignment_state"), dict
        ):
            raw_o5s = payload.get("sensory_modality_temporal_alignment_state")
        # History only; never create live envelopes or replay reception on restore.
        _o5_restore(runtime.world, raw_o5s if isinstance(raw_o5s, dict) else None)
        from mechanistic_mind.physical_system.researcher_physical_optical_audit_view import (
            invalidate_o6_display_cache as _o6_invalidate,
        )
        _o6_invalidate(runtime.world)
        from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
            restore_state as _resli_restore,
        )
        raw_resli = payload.get("release_and_excavation_support_loss_integration_state")
        _resli_restore(
            runtime.world,
            raw_resli if isinstance(raw_resli, dict) else None,
            runtime.config,
        )
        bpayload = payload.get("body") or {}
        if "z" in bpayload:
            runtime.body.z = float(bpayload.get("z") or 0.0)
        if "vz" in bpayload:
            runtime.body.vz = float(bpayload.get("vz") or 0.0)
        if "grounded" in bpayload:
            runtime.body.grounded = bool(bpayload.get("grounded"))
        if bpayload.get("vertical_half_extent") is not None:
            runtime.body.vertical_half_extent = float(bpayload["vertical_half_extent"])
        return runtime
