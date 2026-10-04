"""MM 1.0 — Acanthostega identity (Tiktaalik-compatible runtime token).

Phase 0 is a pre-lifecycle copy of Tiktaalik physics.
Phase A adds optional Gentle Locomotion. Phase A Materials adds one passive
world resource object. Phase A Material Vision adds anonymous optical
contribution of that object to existing near-field channels. Phase A Single
Grasp adds one body-relative effector and GRASP/RELEASE. Phase A Bilateral Grasp
adds independent LEFT/RIGHT effectors. Mixing, conversion, and lifecycle are not
implemented.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.model.identity import (
    MANIFEST_SCHEMA_VERSION,
    MODEL_FAMILY,
    MODEL_VERSION,
    OBSERVER_API_VERSION,
    RUNTIME_VERSION as TIKTAALIK_RUNTIME_VERSION,
    SNAPSHOT_SCHEMA,
)

MODEL_LINE = "ACANTHOSTEGA"
MODEL_CODENAME = "Acanthostega"
WORKING_TITLE = "Acanthostega: Dancing with Death"
PHASE_LABEL = "Acanthostega Phase 0"
PHASE_LABEL_A = "Acanthostega Phase A Gentle"
PHASE_LABEL_MATERIALS = "Acanthostega Phase A Materials"
PHASE_LABEL_MATERIAL_VISION = "Acanthostega Phase A Material Vision"
PHASE_LABEL_SINGLE_GRASP = "Acanthostega Phase A Single Grasp"
PHASE_LABEL_BILATERAL_GRASP = "Acanthostega Phase A Bilateral Grasp"
PHASE_LABEL_BRING_TOGETHER = "Acanthostega Phase A Bring Together"
PHASE_LABEL_COMPOSITION_MERGE = "Acanthostega Phase A Composition Merge"
PHASE_LABEL_MATERIAL_PROPERTIES = "Acanthostega Phase A Material Properties"
PHASE_LABEL_SURFACE_DEPOSITION = "Acanthostega Phase A Surface Deposition"
PHASE_LABEL_SURFACE_TRACTION = "Acanthostega Phase A Surface Traction"
PHASE_LABEL_TRACTION_EXPERIENCE = "Acanthostega Phase A Traction Experience"
PHASE_LABEL_TRACTION_ADAPTATION = "Acanthostega Phase A Traction Adaptation"
PHASE_LABEL_SURFACE_OPTICAL = "Acanthostega Phase A Surface Optical"
PHASE_LABEL_WORLD_MATERIAL = "Acanthostega Phase B World Material Transactions"
PHASE_LABEL_MULTI_CONTENT = "Acanthostega Phase B Multi-Content Index"
PHASE_LABEL_PROCEDURAL_COLUMNS = "Acanthostega Phase B Procedural Columns"
PHASE_LABEL_COLUMN_TRANSFER = "Acanthostega Phase B Column Transfer"
PHASE_LABEL_LOCAL_SIGNAL = "Acanthostega Phase B Local Physical Signal"
PHASE_LABEL_CONTACT_ACOUSTICS = "Acanthostega Phase B Contact Acoustics"
PHASE_LABEL_FREE_OBJECT_KINEMATICS = "Acanthostega Phase B Free Object Kinematics"
PHASE_LABEL_BODY_OBJECT_CONTACT = "Acanthostega Phase B Body Object Contact"
PHASE_LABEL_BODY_OBJECT_IMPULSE = "Acanthostega Phase B Body Object Impulse"
PHASE_LABEL_OBJECT_IMPACT_ACOUSTICS = "Acanthostega Phase B Object Impact Acoustics"
PHASE_LABEL_OBJECT_OBJECT_CONTACT = "Acanthostega Phase B Object Object Contact"
PHASE_LABEL_OBJECT_OBJECT_IMPULSE = "Acanthostega Phase B Object Object Impulse"
PHASE_LABEL_OBJECT_OBJECT_IMPACT_ACOUSTICS = "Acanthostega Phase B Object Object Impact Acoustics"
PHASE_LABEL_HELD_OBJECT_FOREIGN_BODY_CONTACT = "Acanthostega Phase B Held Object Foreign Body Contact"
PHASE_LABEL_HELD_OBJECT_TRANSLATIONAL_IMPULSE = "Acanthostega Phase B Held Object Translational Impulse"
PHASE_LABEL_EFFECTOR_WORK_ACCOUNTING = "Acanthostega Phase B Effector Work Accounting"
PHASE_LABEL_FLAT_GROUND_GRAVITY = "Acanthostega Phase C Flat Ground Gravity"
PHASE_LABEL_FREE_OBJECT_GROUND_FRICTION = "Acanthostega Phase C Free Object Ground Friction"
PHASE_LABEL_SURFACE_ELEVATION_SUPPORT = "Acanthostega Phase C Surface Elevation Support"
PHASE_LABEL_BODY_NORMAL_LOAD_TRACTION = "Acanthostega Phase C Body Normal-Load Traction"
PHASE_LABEL_CONTINUOUS_SURFACE_GEOMETRY = "Acanthostega Phase C Continuous Surface Geometry"
PHASE_LABEL_STATIC_TRACTION = "Acanthostega Phase C Static Traction"
PHASE_LABEL_FREE_OBJECT_STATIC_TRACTION = "Acanthostega Phase C Free Object Static Traction"
PHASE_LABEL_RADIUS_AWARE_SUPPORT = "Acanthostega Phase C Radius-Aware Support"
PHASE_LABEL_SES_DECOMPOSITION_CONTRACT = "Acanthostega Phase C SES Decomposition Contract"
PHASE_LABEL_SES_RUNTIME_CLASSIFIER = "Acanthostega Phase C SES Runtime Classifier"
PHASE_LABEL_RADIUS_AWARE_FACE_SWEEP = "Acanthostega Phase C Radius-Aware Face Sweep"
PHASE_LABEL_DIAGNOSTIC_NORMAL_LOAD_SHADOW = "Acanthostega Phase C Diagnostic Normal-Load Shadow"
PHASE_LABEL_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW = "Acanthostega Phase C Continuous Gravitational PE Diagnostic Shadow"
PHASE_LABEL_CONTINUOUS_PE_POLICY_C = "Acanthostega Phase C Continuous PE Policy C"
PHASE_LABEL_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW = "Acanthostega Phase C Tangent Gravity Diagnostic Shadow"
PHASE_LABEL_COHERENT_SLOPE_DYNAMICS = "Acanthostega Phase C Coherent Slope Dynamics"
PHASE_LABEL_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION = (
    "Acanthostega Beta 4 Conservative Surface Material Separation"
)
PHASE_LABEL_EFFECTOR_TERRAIN_CONTACT_GEOMETRY = (
    "Acanthostega Beta 4 Effector Terrain Contact Geometry"
)
PHASE_LABEL_MANIPULATOR_RELATIVE_WORLD_ACTUATION = (
    "Acanthostega Beta 4 Manipulator Relative World Actuation"
)
PHASE_LABEL_EFFECTOR_BOUNDED_ACTUATOR_EFFORT = (
    "Acanthostega Beta 4 Effector Bounded Actuator Effort"
)
PHASE_LABEL_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE = (
    "Acanthostega Beta 4 Surface Exertion Terrain Material Resistance"
)
PHASE_LABEL_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY = (
    "Acanthostega Beta 4 Held Object Terrain Contact"
)
PHASE_LABEL_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION = (
    "Acanthostega Beta 4 Held Object Terrain Mechanical Transmission"
)
PHASE_LABEL_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION = (
    "Acanthostega Beta 4 Held-Mediated Surface Exertion Integration"
)
PHASE_LABEL_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT = (
    "Acanthostega Beta 4 Detached Terrain Material Initial Placement"
)
PHASE_LABEL_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR = (
    "Acanthostega Beta 4 BNLT MOVE Breakaway Locomotion Repair"
)
PHASE_LABEL_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION = (
    "Acanthostega Beta 4 Active Locomotion Traction vs Sliding Friction"
)
PHASE_LABEL_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT = (
    "Acanthostega Beta 4 Event-Driven Crowded Placement Retry Contract"
)
PHASE_LABEL_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS = (
    "Acanthostega Beta 4 Detached Material Amount-Scaled Collision Radius"
)
PHASE_LABEL_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION = (
    "Acanthostega Beta 4 Held COMBINE Radius Resize Transaction"
)
PHASE_LABEL_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION = (
    "Acanthostega Beta 4 Held Deposition Radius Shrink Transaction"
)
PHASE_LABEL_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT = (
    "Acanthostega Beta 4 Free-Space State And PE Authority Contract"
)
PHASE_LABEL_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE = (
    "Acanthostega Beta 4 Vertical Terrain Landing Contact Response"
)
PHASE_LABEL_VERTICAL_IMPACT_ACOUSTIC_EMISSION = (
    "Acanthostega Beta 4 Vertical Impact Acoustic Emission"
)
PHASE_LABEL_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION = (
    "Beta 4 · Free-Space V1D · RELEASE + Excavation Support-Loss Integration"
)
PHASE_LABEL_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION = (
    "Acanthostega Beta 4 Repeated Conservative Surface-Column Separation"
)
PUBLIC_PRESET = "ACANTHOSTEGA_PHASE0"
PUBLIC_PRESET_GENTLE = "ACANTHOSTEGA_PHASE_A_GENTLE"
PUBLIC_PRESET_MATERIALS = "ACANTHOSTEGA_PHASE_A_MATERIALS"
PUBLIC_PRESET_MATERIAL_VISION = "ACANTHOSTEGA_PHASE_A_MATERIAL_VISION"
PUBLIC_PRESET_SINGLE_GRASP = "ACANTHOSTEGA_PHASE_A_SINGLE_GRASP"
PUBLIC_PRESET_BILATERAL_GRASP = "ACANTHOSTEGA_PHASE_A_BILATERAL_GRASP"
PUBLIC_PRESET_BRING_TOGETHER = "ACANTHOSTEGA_PHASE_A_BRING_TOGETHER"
PUBLIC_PRESET_COMPOSITION_MERGE = "ACANTHOSTEGA_PHASE_A_COMPOSITION_MERGE"
PUBLIC_PRESET_MATERIAL_PROPERTIES = "ACANTHOSTEGA_PHASE_A_MATERIAL_PROPERTIES"
PUBLIC_PRESET_SURFACE_DEPOSITION = "ACANTHOSTEGA_PHASE_A_SURFACE_DEPOSITION"
PUBLIC_PRESET_SURFACE_TRACTION = "ACANTHOSTEGA_PHASE_A_SURFACE_TRACTION"
PUBLIC_PRESET_TRACTION_EXPERIENCE = "ACANTHOSTEGA_PHASE_A_TRACTION_EXPERIENCE"
PUBLIC_PRESET_TRACTION_ADAPTATION = "ACANTHOSTEGA_PHASE_A_TRACTION_ADAPTATION"
PUBLIC_PRESET_SURFACE_OPTICAL = "ACANTHOSTEGA_PHASE_A_SURFACE_OPTICAL"
PUBLIC_PRESET_WORLD_MATERIAL = "ACANTHOSTEGA_PHASE_B_WORLD_MATERIAL_TRANSACTIONS"
PUBLIC_PRESET_MULTI_CONTENT = "ACANTHOSTEGA_PHASE_B_MULTI_CONTENT_INDEX"
PUBLIC_PRESET_PROCEDURAL_COLUMNS = "ACANTHOSTEGA_PHASE_B_PROCEDURAL_COLUMNS"
PUBLIC_PRESET_COLUMN_TRANSFER = "ACANTHOSTEGA_PHASE_B_COLUMN_TRANSFER"
PUBLIC_PRESET_LOCAL_SIGNAL = "ACANTHOSTEGA_PHASE_B_LOCAL_SIGNAL"
PUBLIC_PRESET_CONTACT_ACOUSTICS = "ACANTHOSTEGA_PHASE_B_CONTACT_ACOUSTICS"
PUBLIC_PRESET_FREE_OBJECT_KINEMATICS = "ACANTHOSTEGA_PHASE_B_FREE_OBJECT_KINEMATICS"
PUBLIC_PRESET_BODY_OBJECT_CONTACT = "ACANTHOSTEGA_PHASE_B_BODY_OBJECT_CONTACT"
PUBLIC_PRESET_BODY_OBJECT_IMPULSE = "ACANTHOSTEGA_PHASE_B_BODY_OBJECT_IMPULSE"
PUBLIC_PRESET_OBJECT_IMPACT_ACOUSTICS = "ACANTHOSTEGA_PHASE_B_OBJECT_IMPACT_ACOUSTICS"
PUBLIC_PRESET_OBJECT_OBJECT_CONTACT = "ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_CONTACT"
PUBLIC_PRESET_OBJECT_OBJECT_IMPULSE = "ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_IMPULSE"
PUBLIC_PRESET_OBJECT_OBJECT_IMPACT_ACOUSTICS = "ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_IMPACT_ACOUSTICS"
PUBLIC_PRESET_HELD_OBJECT_FOREIGN_BODY_CONTACT = "ACANTHOSTEGA_PHASE_B_HELD_OBJECT_FOREIGN_BODY_CONTACT"
PUBLIC_PRESET_HELD_OBJECT_TRANSLATIONAL_IMPULSE = "ACANTHOSTEGA_PHASE_B_HELD_OBJECT_TRANSLATIONAL_IMPULSE"
PUBLIC_PRESET_EFFECTOR_WORK_ACCOUNTING = "ACANTHOSTEGA_PHASE_B_EFFECTOR_WORK_ACCOUNTING"
PUBLIC_PRESET_FLAT_GROUND_GRAVITY = "ACANTHOSTEGA_PHASE_C_FLAT_GROUND_GRAVITY"
PUBLIC_PRESET_FREE_OBJECT_GROUND_FRICTION = "ACANTHOSTEGA_PHASE_C_FREE_OBJECT_GROUND_FRICTION"
PUBLIC_PRESET_SURFACE_ELEVATION_SUPPORT = "ACANTHOSTEGA_PHASE_C_SURFACE_ELEVATION_SUPPORT"
PUBLIC_PRESET_BODY_NORMAL_LOAD_TRACTION = "ACANTHOSTEGA_PHASE_C_BODY_NORMAL_LOAD_TRACTION"
PUBLIC_PRESET_CONTINUOUS_SURFACE_GEOMETRY = "ACANTHOSTEGA_PHASE_C_CONTINUOUS_SURFACE_GEOMETRY"
PUBLIC_PRESET_STATIC_TRACTION = "ACANTHOSTEGA_PHASE_C_STATIC_TRACTION"
PUBLIC_PRESET_FREE_OBJECT_STATIC_TRACTION = "ACANTHOSTEGA_PHASE_C_FREE_OBJECT_STATIC_TRACTION"
PUBLIC_PRESET_RADIUS_AWARE_SUPPORT = "ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_SUPPORT"
PUBLIC_PRESET_SES_DECOMPOSITION_CONTRACT = "ACANTHOSTEGA_PHASE_C_SES_DECOMPOSITION_CONTRACT"
PUBLIC_PRESET_SES_RUNTIME_CLASSIFIER = "ACANTHOSTEGA_PHASE_C_SES_RUNTIME_CLASSIFIER"
PUBLIC_PRESET_RADIUS_AWARE_FACE_SWEEP = "ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_FACE_SWEEP"
PUBLIC_PRESET_DIAGNOSTIC_NORMAL_LOAD_SHADOW = "ACANTHOSTEGA_PHASE_C_DIAGNOSTIC_NORMAL_LOAD_SHADOW"
PUBLIC_PRESET_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW = "ACANTHOSTEGA_PHASE_C_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW"
PUBLIC_PRESET_CONTINUOUS_PE_POLICY_C = "ACANTHOSTEGA_PHASE_C_CONTINUOUS_PE_POLICY_C"
PUBLIC_PRESET_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW = "ACANTHOSTEGA_PHASE_C_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW"
PUBLIC_PRESET_COHERENT_SLOPE_DYNAMICS = "ACANTHOSTEGA_PHASE_C_COHERENT_SLOPE_DYNAMICS"
PUBLIC_PRESET_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION = (
    "ACANTHOSTEGA_BETA4_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION"
)
PUBLIC_PRESET_EFFECTOR_TERRAIN_CONTACT_GEOMETRY = (
    "ACANTHOSTEGA_BETA4_EFFECTOR_TERRAIN_CONTACT_GEOMETRY"
)
PUBLIC_PRESET_MANIPULATOR_RELATIVE_WORLD_ACTUATION = (
    "ACANTHOSTEGA_BETA4_MANIPULATOR_RELATIVE_WORLD_ACTUATION"
)
PUBLIC_PRESET_EFFECTOR_BOUNDED_ACTUATOR_EFFORT = (
    "ACANTHOSTEGA_BETA4_EFFECTOR_BOUNDED_ACTUATOR_EFFORT"
)
PUBLIC_PRESET_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE = (
    "ACANTHOSTEGA_BETA4_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE"
)
PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY = (
    "ACANTHOSTEGA_BETA4_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY"
)
PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION = (
    "ACANTHOSTEGA_BETA4_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION"
)
PUBLIC_PRESET_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION = (
    "ACANTHOSTEGA_BETA4_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION"
)
PUBLIC_PRESET_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT = (
    "ACANTHOSTEGA_BETA4_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT"
)
PUBLIC_PRESET_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR = (
    "ACANTHOSTEGA_BETA4_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR"
)
PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION = (
    "ACANTHOSTEGA_BETA4_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION"
)
PUBLIC_PRESET_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT = (
    "ACANTHOSTEGA_BETA4_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT"
)
PUBLIC_PRESET_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS = (
    "ACANTHOSTEGA_BETA4_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS"
)
PUBLIC_PRESET_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION = (
    "ACANTHOSTEGA_BETA4_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION"
)
PUBLIC_PRESET_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION = (
    "ACANTHOSTEGA_BETA4_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION"
)
PUBLIC_PRESET_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT = (
    "ACANTHOSTEGA_BETA4_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT"
)
PUBLIC_PRESET_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE = (
    "ACANTHOSTEGA_BETA4_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE"
)
PUBLIC_PRESET_VERTICAL_IMPACT_ACOUSTIC_EMISSION = (
    "ACANTHOSTEGA_BETA4_VERTICAL_IMPACT_ACOUSTIC_EMISSION"
)
PUBLIC_PRESET_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION = (
    "ACANTHOSTEGA_BETA4_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION"
)
PUBLIC_PRESET_VOLUMETRIC_WORLD_VW7 = (
    "ACANTHOSTEGA_BETA4_VOLUMETRIC_WORLD_VW7"
)
PHASE_LABEL_VOLUMETRIC_WORLD_VW7 = "Acanthostega · Volumetric World · VW7"
RUNTIME_STAGE_VOLUMETRIC_WORLD_VW7 = "BETA4_VOLUMETRIC_WORLD_VW7"

PUBLIC_PRESET_BETA4 = "ACANTHOSTEGA_BETA4"
PHASE_LABEL_BETA4 = "Acanthostega Beta 4.0"
RUNTIME_STAGE_BETA4 = "BETA4_0"
PUBLIC_PRESET_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION = (
    "ACANTHOSTEGA_BETA4_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION"
)
RUNTIME_VERSION = TIKTAALIK_RUNTIME_VERSION
RUNTIME_STAGE = "PHASE0"
RUNTIME_STAGE_A = "PHASE_A"
RUNTIME_STAGE_MATERIALS = "PHASE_A_MATERIALS"
RUNTIME_STAGE_MATERIAL_VISION = "PHASE_A_MATERIAL_VISION"
RUNTIME_STAGE_SINGLE_GRASP = "PHASE_A_SINGLE_GRASP"
RUNTIME_STAGE_BILATERAL_GRASP = "PHASE_A_BILATERAL_GRASP"
RUNTIME_STAGE_BRING_TOGETHER = "PHASE_A_BRING_TOGETHER"
RUNTIME_STAGE_COMPOSITION_MERGE = "PHASE_A_COMPOSITION_MERGE"
RUNTIME_STAGE_MATERIAL_PROPERTIES = "PHASE_A_MATERIAL_PROPERTIES"
RUNTIME_STAGE_SURFACE_DEPOSITION = "PHASE_A_SURFACE_DEPOSITION"
RUNTIME_STAGE_SURFACE_TRACTION = "PHASE_A_SURFACE_TRACTION"
RUNTIME_STAGE_TRACTION_EXPERIENCE = "PHASE_A_TRACTION_EXPERIENCE"
RUNTIME_STAGE_TRACTION_ADAPTATION = "PHASE_A_TRACTION_ADAPTATION"
RUNTIME_STAGE_SURFACE_OPTICAL = "PHASE_A_SURFACE_OPTICAL"
RUNTIME_STAGE_WORLD_MATERIAL = "PHASE_B_WORLD_MATERIAL_TRANSACTIONS"
RUNTIME_STAGE_MULTI_CONTENT = "PHASE_B_MULTI_CONTENT_INDEX"
RUNTIME_STAGE_PROCEDURAL_COLUMNS = "PHASE_B_PROCEDURAL_COLUMNS"
RUNTIME_STAGE_COLUMN_TRANSFER = "PHASE_B_COLUMN_TRANSFER"
RUNTIME_STAGE_LOCAL_SIGNAL = "PHASE_B_LOCAL_SIGNAL"
RUNTIME_STAGE_CONTACT_ACOUSTICS = "PHASE_B_CONTACT_ACOUSTICS"
RUNTIME_STAGE_FREE_OBJECT_KINEMATICS = "PHASE_B_FREE_OBJECT_KINEMATICS"
RUNTIME_STAGE_BODY_OBJECT_CONTACT = "PHASE_B_BODY_OBJECT_CONTACT"
RUNTIME_STAGE_BODY_OBJECT_IMPULSE = "PHASE_B_BODY_OBJECT_IMPULSE"
RUNTIME_STAGE_OBJECT_IMPACT_ACOUSTICS = "PHASE_B_OBJECT_IMPACT_ACOUSTICS"
RUNTIME_STAGE_OBJECT_OBJECT_CONTACT = "PHASE_B_OBJECT_OBJECT_CONTACT"
RUNTIME_STAGE_OBJECT_OBJECT_IMPULSE = "PHASE_B_OBJECT_OBJECT_IMPULSE"
RUNTIME_STAGE_OBJECT_OBJECT_IMPACT_ACOUSTICS = "PHASE_B_OBJECT_OBJECT_IMPACT_ACOUSTICS"
RUNTIME_STAGE_HELD_OBJECT_FOREIGN_BODY_CONTACT = "PHASE_B_HELD_OBJECT_FOREIGN_BODY_CONTACT"
RUNTIME_STAGE_HELD_OBJECT_TRANSLATIONAL_IMPULSE = "PHASE_B_HELD_OBJECT_TRANSLATIONAL_IMPULSE"
RUNTIME_STAGE_EFFECTOR_WORK_ACCOUNTING = "PHASE_B_EFFECTOR_WORK_ACCOUNTING"
RUNTIME_STAGE_FLAT_GROUND_GRAVITY = "PHASE_C_FLAT_GROUND_GRAVITY"
RUNTIME_STAGE_FREE_OBJECT_GROUND_FRICTION = "PHASE_C_FREE_OBJECT_GROUND_FRICTION"
RUNTIME_STAGE_SURFACE_ELEVATION_SUPPORT = "PHASE_C_SURFACE_ELEVATION_SUPPORT"
RUNTIME_STAGE_BODY_NORMAL_LOAD_TRACTION = "PHASE_C_BODY_NORMAL_LOAD_TRACTION"
RUNTIME_STAGE_CONTINUOUS_SURFACE_GEOMETRY = "PHASE_C_CONTINUOUS_SURFACE_GEOMETRY"
RUNTIME_STAGE_STATIC_TRACTION = "PHASE_C_STATIC_TRACTION"
RUNTIME_STAGE_FREE_OBJECT_STATIC_TRACTION = "PHASE_C_FREE_OBJECT_STATIC_TRACTION"
RUNTIME_STAGE_RADIUS_AWARE_SUPPORT = "PHASE_C_RADIUS_AWARE_SUPPORT"
RUNTIME_STAGE_SES_DECOMPOSITION_CONTRACT = "PHASE_C_SES_DECOMPOSITION_CONTRACT"
RUNTIME_STAGE_SES_RUNTIME_CLASSIFIER = "PHASE_C_SES_RUNTIME_CLASSIFIER"
RUNTIME_STAGE_RADIUS_AWARE_FACE_SWEEP = "PHASE_C_RADIUS_AWARE_FACE_SWEEP"
RUNTIME_STAGE_DIAGNOSTIC_NORMAL_LOAD_SHADOW = "PHASE_C_DIAGNOSTIC_NORMAL_LOAD_SHADOW"
RUNTIME_STAGE_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW = "PHASE_C_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW"
RUNTIME_STAGE_CONTINUOUS_PE_POLICY_C = "PHASE_C_CONTINUOUS_PE_POLICY_C"
RUNTIME_STAGE_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW = "PHASE_C_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW"
RUNTIME_STAGE_COHERENT_SLOPE_DYNAMICS = "PHASE_C_COHERENT_SLOPE_DYNAMICS"
RUNTIME_STAGE_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION = (
    "BETA4_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION"
)
RUNTIME_STAGE_EFFECTOR_TERRAIN_CONTACT_GEOMETRY = (
    "BETA4_EFFECTOR_TERRAIN_CONTACT_GEOMETRY"
)
RUNTIME_STAGE_MANIPULATOR_RELATIVE_WORLD_ACTUATION = (
    "BETA4_MANIPULATOR_RELATIVE_WORLD_ACTUATION"
)
RUNTIME_STAGE_EFFECTOR_BOUNDED_ACTUATOR_EFFORT = (
    "BETA4_EFFECTOR_BOUNDED_ACTUATOR_EFFORT"
)
RUNTIME_STAGE_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE = (
    "BETA4_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE"
)
RUNTIME_STAGE_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY = (
    "BETA4_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY"
)
RUNTIME_STAGE_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION = (
    "BETA4_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION"
)
RUNTIME_STAGE_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION = (
    "BETA4_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION"
)
RUNTIME_STAGE_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT = (
    "BETA4_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT"
)
RUNTIME_STAGE_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR = (
    "BETA4_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR"
)
RUNTIME_STAGE_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION = (
    "BETA4_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION"
)
RUNTIME_STAGE_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT = (
    "BETA4_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT"
)
RUNTIME_STAGE_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS = (
    "BETA4_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS"
)
RUNTIME_STAGE_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION = (
    "BETA4_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION"
)
RUNTIME_STAGE_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION = (
    "BETA4_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION"
)
RUNTIME_STAGE_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT = (
    "BETA4_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT"
)
RUNTIME_STAGE_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE = (
    "BETA4_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE"
)
RUNTIME_STAGE_VERTICAL_IMPACT_ACOUSTIC_EMISSION = (
    "BETA4_VERTICAL_IMPACT_ACOUSTIC_EMISSION"
)
RUNTIME_STAGE_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION = (
    "BETA4_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION"
)
RUNTIME_STAGE_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION = (
    "BETA4_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION"
)


def display_name() -> str:
    return f"MM {MODEL_VERSION} — {PHASE_LABEL}"


def _preset_of(config) -> str:
    return str(getattr(config, "public_preset", None) or PUBLIC_PRESET)


def acanthostega_config():
    """Tiktaalik-compatible PhysicalSystemConfig stamped as Acanthostega Phase 0."""
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.locomotion_profile import tiktaalik_locomotion_profile

    cfg = tiktaalik_config()
    cfg.model_line = MODEL_LINE
    cfg.public_preset = PUBLIC_PRESET
    cfg.runtime_version = TIKTAALIK_RUNTIME_VERSION
    cfg.locomotion_profile = tiktaalik_locomotion_profile()
    return cfg


def acanthostega_gentle_config():
    """Phase A: Phase 0 identity plus gentle locomotion profile ON."""
    from mechanistic_mind.physical_system.locomotion_profile import (
        acanthostega_gentle_locomotion_profile,
    )

    cfg = acanthostega_config()
    cfg.public_preset = PUBLIC_PRESET_GENTLE
    cfg.locomotion_profile = acanthostega_gentle_locomotion_profile()
    return cfg


def acanthostega_materials_config():
    """Phase A Materials: Gentle Locomotion plus one passive ResourceObject."""
    from mechanistic_mind.physical_system.resource_objects import (
        PhysicalResourceObjectsConfig,
        set_physical_resource_objects,
    )

    cfg = acanthostega_gentle_config()
    cfg.public_preset = PUBLIC_PRESET_MATERIALS
    cfg.physical_resource_objects = PhysicalResourceObjectsConfig(enabled=True)
    set_physical_resource_objects(cfg, True)
    from mechanistic_mind.physical_system.resource_objects import set_physical_resource_object_vision
    set_physical_resource_object_vision(cfg, False)
    from mechanistic_mind.physical_system.physical_manipulator import (
        set_physical_grasp_release,
        set_single_physical_manipulator,
    )
    set_single_physical_manipulator(cfg, False)
    set_physical_grasp_release(cfg, False)
    return cfg


def acanthostega_material_vision_config():
    """Phase A Material Vision: passive object plus anonymous optical contribution."""
    from mechanistic_mind.physical_system.resource_objects import (
        PhysicalResourceObjectVisionConfig,
        set_physical_resource_object_vision,
    )

    cfg = acanthostega_materials_config()
    cfg.public_preset = PUBLIC_PRESET_MATERIAL_VISION
    cfg.physical_resource_object_vision = PhysicalResourceObjectVisionConfig(enabled=True)
    set_physical_resource_object_vision(cfg, True)
    from mechanistic_mind.physical_system.physical_manipulator import (
        set_physical_grasp_release,
        set_single_physical_manipulator,
    )
    set_single_physical_manipulator(cfg, False)
    set_physical_grasp_release(cfg, False)
    return cfg


def acanthostega_single_grasp_config():
    """Phase A Single Grasp: Material Vision plus one manipulator and GRASP/RELEASE."""
    from mechanistic_mind.physical_system.physical_manipulator import (
        PhysicalGraspReleaseConfig,
        SinglePhysicalManipulatorConfig,
        set_physical_grasp_release,
        set_single_physical_manipulator,
    )

    cfg = acanthostega_material_vision_config()
    cfg.public_preset = PUBLIC_PRESET_SINGLE_GRASP
    cfg.single_physical_manipulator = SinglePhysicalManipulatorConfig(enabled=True)
    set_single_physical_manipulator(cfg, True)
    cfg.physical_grasp_release = PhysicalGraspReleaseConfig(enabled=True)
    set_physical_grasp_release(cfg, True)
    from mechanistic_mind.physical_system.physical_manipulator import (
        set_bilateral_grasp_release,
        set_bilateral_physical_manipulators,
    )
    set_bilateral_physical_manipulators(cfg, False)
    set_bilateral_grasp_release(cfg, False)
    return cfg


def acanthostega_bilateral_grasp_config():
    """Phase A Bilateral Grasp: Material Vision plus independent LEFT/RIGHT GRASP/RELEASE."""
    from mechanistic_mind.physical_system.physical_manipulator import (
        BilateralGraspReleaseConfig,
        BilateralPhysicalManipulatorsConfig,
        set_bilateral_grasp_release,
        set_bilateral_physical_manipulators,
        set_physical_grasp_release,
        set_single_physical_manipulator,
    )
    from mechanistic_mind.physical_system.resource_objects import default_bilateral_spawn_objects

    cfg = acanthostega_material_vision_config()
    cfg.public_preset = PUBLIC_PRESET_BILATERAL_GRASP
    cfg.physical_resource_objects.spawn_objects = default_bilateral_spawn_objects()
    set_single_physical_manipulator(cfg, False)
    set_physical_grasp_release(cfg, False)
    cfg.bilateral_physical_manipulators = BilateralPhysicalManipulatorsConfig(enabled=True)
    set_bilateral_physical_manipulators(cfg, True)
    cfg.bilateral_grasp_release = BilateralGraspReleaseConfig(enabled=True)
    set_bilateral_grasp_release(cfg, True)
    from mechanistic_mind.physical_system.physical_manipulator import set_bilateral_bring_together
    set_bilateral_bring_together(cfg, False)
    return cfg


def acanthostega_bring_together_config():
    """Phase A Bring Together: Bilateral Grasp plus pair aperture actuation."""
    from mechanistic_mind.physical_system.physical_manipulator import (
        BilateralBringTogetherConfig,
        set_bilateral_bring_together,
    )

    cfg = acanthostega_bilateral_grasp_config()
    cfg.public_preset = PUBLIC_PRESET_BRING_TOGETHER
    cfg.bilateral_bring_together = BilateralBringTogetherConfig(enabled=True)
    set_bilateral_bring_together(cfg, True)
    return cfg


def acanthostega_composition_merge_config():
    """Phase A Composition Merge: explicit conserved COMBINE after contact."""
    from mechanistic_mind.physical_system.material_composition import (
        MaterialCompositionMergeConfig, set_material_composition_merge,
    )

    cfg = acanthostega_bring_together_config()
    cfg.public_preset = PUBLIC_PRESET_COMPOSITION_MERGE
    cfg.material_composition_merge = MaterialCompositionMergeConfig(enabled=True)
    set_material_composition_merge(cfg, True)
    from mechanistic_mind.physical_system.passive_material_properties import (
        set_passive_material_properties,
    )
    set_passive_material_properties(cfg, False)
    return cfg


def acanthostega_material_properties_config():
    """Phase A Material Properties: Composition Merge plus passive coefficients."""
    from mechanistic_mind.physical_system.passive_material_properties import (
        PassiveMaterialPropertiesConfig,
        set_passive_material_properties,
    )

    cfg = acanthostega_composition_merge_config()
    cfg.public_preset = PUBLIC_PRESET_MATERIAL_PROPERTIES
    cfg.passive_material_properties = PassiveMaterialPropertiesConfig(enabled=True)
    set_passive_material_properties(cfg, True)
    from mechanistic_mind.physical_system.explicit_surface_deposition import (
        set_explicit_surface_deposition,
    )
    set_explicit_surface_deposition(cfg, False)
    return cfg


def acanthostega_surface_deposition_config():
    """Phase A Surface Deposition: Material Properties plus explicit APPLY_TO_SURFACE."""
    from mechanistic_mind.physical_system.explicit_surface_deposition import (
        ExplicitSurfaceDepositionConfig,
        set_explicit_surface_deposition,
    )

    cfg = acanthostega_material_properties_config()
    cfg.public_preset = PUBLIC_PRESET_SURFACE_DEPOSITION
    cfg.explicit_surface_deposition = ExplicitSurfaceDepositionConfig(enabled=True)
    set_explicit_surface_deposition(cfg, True)
    from mechanistic_mind.physical_system.surface_affinity_traction import (
        set_surface_affinity_traction,
    )
    set_surface_affinity_traction(cfg, False)
    from mechanistic_mind.physical_system.surface_traction_experience import (
        set_surface_traction_experience,
    )
    set_surface_traction_experience(cfg, False)
    return cfg


def acanthostega_surface_traction_config():
    """Phase A Surface Traction: deposition plus continuous surface_affinity coupling."""
    from mechanistic_mind.physical_system.surface_affinity_traction import (
        SurfaceAffinityTractionConfig,
        set_surface_affinity_traction,
        traction_contrast_spawn_objects,
    )

    cfg = acanthostega_surface_deposition_config()
    cfg.public_preset = PUBLIC_PRESET_SURFACE_TRACTION
    cfg.surface_affinity_traction = SurfaceAffinityTractionConfig(enabled=True)
    set_surface_affinity_traction(cfg, True)
    cfg.physical_resource_objects.spawn_objects = traction_contrast_spawn_objects()
    from mechanistic_mind.physical_system.surface_traction_experience import (
        set_surface_traction_experience,
    )
    set_surface_traction_experience(cfg, False)
    return cfg


def acanthostega_traction_experience_config():
    """Phase A Traction Experience: traction physics plus the ordinary experience bridge."""
    from mechanistic_mind.physical_system.surface_traction_experience import (
        SurfaceTractionExperienceConfig,
        set_surface_traction_experience,
    )

    cfg = acanthostega_surface_traction_config()
    cfg.public_preset = PUBLIC_PRESET_TRACTION_EXPERIENCE
    cfg.surface_traction_experience = SurfaceTractionExperienceConfig(enabled=True)
    set_surface_traction_experience(cfg, True)
    from mechanistic_mind.physical_system.surface_traction_prediction import (
        set_surface_traction_prediction,
    )
    set_surface_traction_prediction(cfg, False)
    return cfg


def acanthostega_traction_adaptation_config():
    """Phase A Traction Adaptation: experience bridge plus the generic consequence model."""
    from mechanistic_mind.physical_system.surface_traction_prediction import (
        SurfaceTractionPredictionConfig,
        set_surface_traction_prediction,
    )

    cfg = acanthostega_traction_experience_config()
    cfg.public_preset = PUBLIC_PRESET_TRACTION_ADAPTATION
    cfg.surface_traction_prediction = SurfaceTractionPredictionConfig(enabled=True)
    set_surface_traction_prediction(cfg, True)
    cfg.cognition.sensorimotor_consequence_model = True
    from mechanistic_mind.physical_system.physical_surface_optical_coating import (
        set_physical_surface_optical_coating,
    )
    set_physical_surface_optical_coating(cfg, False)
    return cfg


def acanthostega_surface_optical_config():
    """Phase A Surface Optical: anonymous coating of deposited cells."""
    from mechanistic_mind.physical_system.physical_surface_optical_coating import (
        PhysicalSurfaceOpticalCoatingConfig,
        set_physical_surface_optical_coating,
        surface_optical_spawn_objects,
    )

    cfg = acanthostega_traction_adaptation_config()
    cfg.public_preset = PUBLIC_PRESET_SURFACE_OPTICAL
    cfg.physical_resource_objects.spawn_objects = surface_optical_spawn_objects()
    cfg.physical_surface_optical_coating = PhysicalSurfaceOpticalCoatingConfig(enabled=True)
    set_physical_surface_optical_coating(cfg, True)
    nfe = cfg.near_field_exteroception
    nfe.visual_surface_discrimination = "RICH"
    nfe.mode = "EXPERIMENTAL"
    nfe.perception_enabled = True
    from mechanistic_mind.physical_system.world_material_transaction import (
        set_world_material_transactions,
    )
    set_world_material_transactions(cfg, False)
    return cfg


def acanthostega_world_material_config():
    """Phase B: COMBINE and deposition commit through one material transaction."""
    from mechanistic_mind.physical_system.world_material_transaction import (
        WorldMaterialTransactionsConfig,
        set_world_material_transactions,
    )

    cfg = acanthostega_surface_optical_config()
    cfg.public_preset = PUBLIC_PRESET_WORLD_MATERIAL
    cfg.world_material_transactions = WorldMaterialTransactionsConfig(enabled=True)
    set_world_material_transactions(cfg, True)
    from mechanistic_mind.physical_system.spatial_contents import set_multi_content_spatial_index

    set_multi_content_spatial_index(cfg, False)
    return cfg


def acanthostega_multi_content_config():
    """Phase B: derived multi-content spatial index over the existing world."""
    from mechanistic_mind.physical_system.spatial_contents import (
        MultiContentSpatialIndexConfig,
        set_multi_content_spatial_index,
    )

    cfg = acanthostega_world_material_config()
    cfg.public_preset = PUBLIC_PRESET_MULTI_CONTENT
    cfg.multi_content_spatial_index = MultiContentSpatialIndexConfig(enabled=True)
    set_multi_content_spatial_index(cfg, True)
    from mechanistic_mind.physical_system.procedural_surface_columns import (
        set_procedural_surface_columns,
    )
    set_procedural_surface_columns(cfg, False)
    return cfg


def acanthostega_procedural_columns_config():
    """Phase B: procedural surface column baseline + sparse persistent deltas.

    Storage/query/persistence only. No body, force, vision or traction effect.
    VW1 volumetric occupancy authority is co-enabled (queries/Observer; no support migration).
    """
    from mechanistic_mind.physical_system.procedural_surface_columns import (
        ProceduralSurfaceColumnsConfig,
        set_procedural_surface_columns,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        set_volumetric_world_material_occupancy,
    )

    cfg = acanthostega_multi_content_config()
    cfg.public_preset = PUBLIC_PRESET_PROCEDURAL_COLUMNS
    cfg.procedural_surface_columns = ProceduralSurfaceColumnsConfig(enabled=True)
    set_procedural_surface_columns(cfg, True)
    set_volumetric_world_material_occupancy(cfg, True)
    return cfg


def acanthostega_volumetric_occupancy_config():
    """VW1: sparse absolute-Z material occupancy authority (+ PSC for legacy physics consumers)."""
    return acanthostega_procedural_columns_config()


def acanthostega_column_transfer_config():
    """Phase B: procedural columns + researcher-only conservative surface column transfer.

    World-mutation semantics only. No body, force, vision, traction, support or gravity effect.
    """
    from mechanistic_mind.physical_system.conservative_surface_column_transfer import (
        ConservativeSurfaceColumnTransferConfig,
        set_conservative_surface_column_transfer,
    )

    cfg = acanthostega_procedural_columns_config()
    cfg.public_preset = PUBLIC_PRESET_COLUMN_TRANSFER
    cfg.conservative_surface_column_transfer = ConservativeSurfaceColumnTransferConfig(enabled=True)
    set_conservative_surface_column_transfer(cfg, True)
    return cfg


def acanthostega_local_signal_config():
    """Phase B: column transfer + local physical signal transport (UNIFORM_SIGNAL_MEDIUM_V1).

    OSC_EMIT becomes a local physical emission (finite speed, attenuation, range, threshold).
    No acoustics of materials/geometry/atmosphere, no semantic message, no source identity.
    """
    from mechanistic_mind.physical_system.local_physical_signal_transport import (
        UniformSignalMediumConfig,
        set_local_physical_signal_transport,
    )
    from mechanistic_mind.physical_system.oscillatory_signaling import OscillatorySignalingConfig

    cfg = acanthostega_column_transfer_config()
    cfg.public_preset = PUBLIC_PRESET_LOCAL_SIGNAL
    if getattr(cfg, "oscillatory_signaling", None) is None:
        cfg.oscillatory_signaling = OscillatorySignalingConfig()
    cfg.oscillatory_signaling.mode = "EXPERIMENTAL"
    cfg.local_physical_signal_transport = UniformSignalMediumConfig(enabled=True)
    set_local_physical_signal_transport(cfg, True)
    return cfg


def acanthostega_contact_acoustics_config():
    """Phase B Audio B: local physical signal + physical contact acoustic emission.

    A measured new body-body contact impulse above epsilon becomes a bounded broadband physical
    emission in the unchanged local transport. Contact solver, PUSH and OSC_EMIT are unchanged.
    """
    from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
        ContactAcousticConfig,
        set_physical_contact_acoustic_emission,
    )

    cfg = acanthostega_local_signal_config()
    cfg.public_preset = PUBLIC_PRESET_CONTACT_ACOUSTICS
    cfg.physical_contact_acoustic_emission = ContactAcousticConfig(enabled=True)
    set_physical_contact_acoustic_emission(cfg, True)
    return cfg


def acanthostega_body_object_contact_config():
    """Phase B: free object kinematics + body↔ResourceObject contact FACT (no response)."""
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        BodyObjectContactConfig,
        set_body_object_contact,
    )

    cfg = acanthostega_free_object_kinematics_config()
    cfg.public_preset = PUBLIC_PRESET_BODY_OBJECT_CONTACT
    cfg.physical_body_resource_object_contact = BodyObjectContactConfig(enabled=True)
    set_body_object_contact(cfg, True)
    return cfg


def acanthostega_body_object_impulse_config():
    """Phase B: contact FACT + MASS+COMPLIANCE normal impulse RESPONSE (no friction/sound)."""
    from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
        BodyObjectContactImpulseConfig,
        set_body_object_impulse,
    )
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        BodyObjectContactConfig,
        set_body_object_contact,
    )

    cfg = acanthostega_body_object_contact_config()
    cfg.public_preset = PUBLIC_PRESET_BODY_OBJECT_IMPULSE
    cfg.physical_body_resource_object_contact = BodyObjectContactConfig(enabled=True)
    set_body_object_contact(cfg, True)
    cfg.body_resource_object_contact_impulse = BodyObjectContactImpulseConfig(enabled=True)
    set_body_object_impulse(cfg, True)
    return cfg


def acanthostega_object_impact_acoustics_config():
    """Phase B merge: impulse RESPONSE + OSC/LPS + Audio B + body/object impact acoustics.

    Starts from acanthostega_body_object_impulse_config(), then ALSO enables
    oscillatory_signaling EXPERIMENTAL, local_physical_signal_transport,
    physical_contact_acoustic_emission (body-body Audio B unchanged), and the new
    body_resource_object_impact_acoustic_emission mechanism. Impulse physics unchanged.
    """
    from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
        BodyObjectImpactAcousticConfig,
        set_body_object_impact_acoustics,
    )
    from mechanistic_mind.physical_system.local_physical_signal_transport import (
        UniformSignalMediumConfig,
        set_local_physical_signal_transport,
    )
    from mechanistic_mind.physical_system.oscillatory_signaling import OscillatorySignalingConfig
    from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
        ContactAcousticConfig,
        set_physical_contact_acoustic_emission,
    )

    cfg = acanthostega_body_object_impulse_config()
    cfg.public_preset = PUBLIC_PRESET_OBJECT_IMPACT_ACOUSTICS
    if getattr(cfg, "oscillatory_signaling", None) is None:
        cfg.oscillatory_signaling = OscillatorySignalingConfig()
    cfg.oscillatory_signaling.mode = "EXPERIMENTAL"
    cfg.local_physical_signal_transport = UniformSignalMediumConfig(enabled=True)
    set_local_physical_signal_transport(cfg, True)
    cfg.physical_contact_acoustic_emission = ContactAcousticConfig(enabled=True)
    set_physical_contact_acoustic_emission(cfg, True)
    cfg.body_resource_object_impact_acoustic_emission = BodyObjectImpactAcousticConfig(enabled=True)
    set_body_object_impact_acoustics(cfg, True)
    return cfg



def acanthostega_object_object_contact_config():
    """Phase B: object-impact-acoustics parent + FREE ResourceObject↔ResourceObject contact FACT.

    Starts from acanthostega_object_impact_acoustics_config(), then enables
    physical_resource_object_pair_contact. Keeps object physics, B/O contact/impulse,
    LPS, Audio B, and impact acoustics. No OO impulse/response/sound.
    """
    from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
        ResourceObjectPairContactConfig,
        set_resource_object_pair_contact,
    )

    cfg = acanthostega_object_impact_acoustics_config()
    cfg.public_preset = PUBLIC_PRESET_OBJECT_OBJECT_CONTACT
    cfg.physical_resource_object_pair_contact = ResourceObjectPairContactConfig(enabled=True)
    set_resource_object_pair_contact(cfg, True)
    return cfg


def acanthostega_object_object_impulse_config():
    """Phase B: OO contact FACT + MASS+COMPLIANCE normal impulse RESPONSE (no friction/sound).

    Parent: acanthostega_object_object_contact_config() then enable impulse.
    """
    from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
        ResourceObjectPairContactImpulseConfig,
        set_resource_object_pair_impulse,
    )

    cfg = acanthostega_object_object_contact_config()
    cfg.public_preset = PUBLIC_PRESET_OBJECT_OBJECT_IMPULSE
    cfg.resource_object_pair_contact_impulse = ResourceObjectPairContactImpulseConfig(enabled=True)
    set_resource_object_pair_impulse(cfg, True)
    return cfg


def acanthostega_object_object_impact_acoustics_config():
    """Phase B merge: OO impulse RESPONSE + OO impact acoustics via existing LPS.

    Parent: acanthostega_object_object_impulse_config() then enable OO impact acoustics.
    Keeps OSC transport + Audio B + B/O impact + OO contact/impulse.
    """
    from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
        ResourceObjectPairImpactAcousticConfig,
        set_resource_object_pair_impact_acoustics,
    )

    cfg = acanthostega_object_object_impulse_config()
    cfg.public_preset = PUBLIC_PRESET_OBJECT_OBJECT_IMPACT_ACOUSTICS
    cfg.resource_object_pair_impact_acoustic_emission = ResourceObjectPairImpactAcousticConfig(enabled=True)
    set_resource_object_pair_impact_acoustics(cfg, True)
    return cfg


def acanthostega_held_object_foreign_body_contact_config():
    """Phase B: OO IMPACT ACOUSTICS parent + HELD object ↔ foreign body contact FACT.

    Parent: acanthostega_object_object_impact_acoustics_config() then enable held/foreign contact.
    No impulse/damage/release/sound. HELD+HELD stays BRING_TOGETHER.
    """
    from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
        HeldForeignBodyContactConfig,
        set_held_foreign_body_contact,
    )

    cfg = acanthostega_object_object_impact_acoustics_config()
    cfg.public_preset = PUBLIC_PRESET_HELD_OBJECT_FOREIGN_BODY_CONTACT
    cfg.held_resource_object_foreign_body_contact = HeldForeignBodyContactConfig(enabled=True)
    set_held_foreign_body_contact(cfg, True)
    return cfg


def acanthostega_held_object_translational_impulse_config():
    """Phase B: held/foreign contact FACT parent + translational impulse mediation.

    Parent: acanthostega_held_object_foreign_body_contact_config() then enable mediation.
    Impulse only when approach is accounted by holder CoM translation.
    """
    from mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation import (
        HeldTranslationalImpulseConfig,
        set_held_translational_impulse,
    )

    cfg = acanthostega_held_object_foreign_body_contact_config()
    cfg.public_preset = PUBLIC_PRESET_HELD_OBJECT_TRANSLATIONAL_IMPULSE
    cfg.held_resource_object_translational_impulse_mediation = HeldTranslationalImpulseConfig(enabled=True)
    set_held_translational_impulse(cfg, True)
    return cfg


def acanthostega_effector_work_accounting_config():
    """Phase B: translational impulse parent + effector work / held-load inertia accounting.

    Parent: acanthostega_held_object_translational_impulse_config() then enable accounting.
    Held ResourceObject load inertia only; no arm mass; no swing impulse.
    """
    from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
        EffectorWorkHeldLoadConfig,
        set_effector_work_held_load,
    )

    cfg = acanthostega_held_object_translational_impulse_config()
    cfg.public_preset = PUBLIC_PRESET_EFFECTOR_WORK_ACCOUNTING
    cfg.effector_work_and_held_load_inertia_accounting = EffectorWorkHeldLoadConfig(enabled=True)
    set_effector_work_held_load(cfg, True)
    return cfg


def acanthostega_flat_ground_gravity_config():
    """Phase C: effector-work parent + vertical state + uniform gravity + flat inelastic support.

    Parent: acanthostega_effector_work_accounting_config() then enable flat_ground_gravity.
    Umbrella co-gates vertical_physical_state, uniform_gravity, flat_ground_support,
    vertical_contact_filter. Prior presets remain 2D / vertical OFF.
    """
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        FlatGroundGravityConfig,
        set_flat_ground_gravity,
    )

    cfg = acanthostega_effector_work_accounting_config()
    cfg.public_preset = PUBLIC_PRESET_FLAT_GROUND_GRAVITY
    cfg.flat_ground_gravity = FlatGroundGravityConfig(enabled=True)
    set_flat_ground_gravity(cfg, True)
    return cfg


def acanthostega_free_object_ground_friction_config():
    """Phase C: flat-ground gravity parent + free-object Coulomb ground friction.

    Parent: acanthostega_flat_ground_gravity_config() then enable free_resource_object_ground_friction.
    When ON, FOK exponential damping is bypassed for FREE_MOVING objects (Coulomb when grounded;
    conserve horizontal v when airborne). FREE_STATIC stays rest. Bodies/Gentle unchanged.
    """
    from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
        FreeObjectGroundFrictionConfig,
        set_free_resource_object_ground_friction,
    )

    cfg = acanthostega_flat_ground_gravity_config()
    cfg.public_preset = PUBLIC_PRESET_FREE_OBJECT_GROUND_FRICTION
    cfg.free_resource_object_ground_friction = FreeObjectGroundFrictionConfig(enabled=True)
    set_free_resource_object_ground_friction(cfg, True)
    return cfg



def acanthostega_surface_elevation_support_config():
    """Phase C: free-object ground friction parent + energy-accounted surface elevation support.

    Parent: acanthostega_free_object_ground_friction_config() then enable surface_elevation_support.
    physical_height_scale=1.0; microrelief_threshold=0.12; NO free PE snap/gain.
    Co-enables VW1 occupancy + VW2 support/contact queries (support_z from occupancy).
    """
    from mechanistic_mind.physical_system.surface_elevation_support import (
        SurfaceElevationSupportConfig,
        set_surface_elevation_support,
        assert_physical_height_scale_gate,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        set_volumetric_world_material_occupancy,
    )
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        set_occupancy_support_and_contact_queries,
    )

    assert_physical_height_scale_gate(1.0)
    cfg = acanthostega_free_object_ground_friction_config()
    cfg.public_preset = PUBLIC_PRESET_SURFACE_ELEVATION_SUPPORT
    cfg.surface_elevation_support = SurfaceElevationSupportConfig(enabled=True)
    set_surface_elevation_support(cfg, True)
    set_volumetric_world_material_occupancy(cfg, True)
    set_occupancy_support_and_contact_queries(cfg, True)
    return cfg


def acanthostega_occupancy_support_contact_config():
    """VW2: occupancy support/contact queries over VW1 (+ SES/FGG parents)."""
    return acanthostega_surface_elevation_support_config()


def acanthostega_volumetric_material_separation_config():
    """VW3: volumetric occupancy separation via WMT (+ VW1/VW2/SES parents)."""
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        set_volumetric_world_material_separation,
    )
    from mechanistic_mind.physical_system.world_material_transaction import (
        set_world_material_transactions,
    )

    cfg = acanthostega_occupancy_support_contact_config()
    set_world_material_transactions(cfg, True)
    set_volumetric_world_material_separation(cfg, True)
    return cfg


def acanthostega_volumetric_material_reintegration_config():
    """VW4: volumetric occupancy reintegration via WMT (+ VW3/VW1/VW2 parents)."""
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        set_volumetric_world_material_reintegration,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        set_volumetric_world_material_separation,
    )
    from mechanistic_mind.physical_system.world_material_transaction import (
        set_world_material_transactions,
    )

    cfg = acanthostega_occupancy_support_contact_config()
    set_world_material_transactions(cfg, True)
    set_volumetric_world_material_separation(cfg, True)
    set_volumetric_world_material_reintegration(cfg, True)
    return cfg

def acanthostega_body_normal_load_traction_config():
    """Phase C: surface elevation parent + body normal-load traction / passive sliding V1.

    Parent: acanthostega_surface_elevation_support_config() then enable body_normal_load_traction.
    Gentle grounded_damping + v_stop BYPASSED when ON; Coulomb μ(affinity), N=m_eff g.
    """
    from mechanistic_mind.physical_system.body_normal_load_traction import (
        BodyNormalLoadTractionConfig,
        set_body_normal_load_traction,
    )

    cfg = acanthostega_surface_elevation_support_config()
    cfg.public_preset = PUBLIC_PRESET_BODY_NORMAL_LOAD_TRACTION
    cfg.body_normal_load_traction = BodyNormalLoadTractionConfig(enabled=True)
    set_body_normal_load_traction(cfg, True)
    return cfg



def acanthostega_continuous_surface_geometry_config():
    """Phase C: BNLT parent + continuous surface geometry (bilinear h + analytic n̂) V1.

    Parent: acanthostega_body_normal_load_traction_config() then enable continuous_surface_geometry.
    Continuous h is support height; analytic normal researcher-visible but physically inactive.
    SES DDA remains energy/blocking authority.
    """
    from mechanistic_mind.physical_system.continuous_surface_geometry import (
        ContinuousSurfaceGeometryConfig,
        set_continuous_surface_geometry,
    )

    cfg = acanthostega_body_normal_load_traction_config()
    cfg.public_preset = PUBLIC_PRESET_CONTINUOUS_SURFACE_GEOMETRY
    cfg.continuous_surface_geometry = ContinuousSurfaceGeometryConfig(enabled=True)
    set_continuous_surface_geometry(cfg, True)
    return cfg




def acanthostega_static_traction_config():
    """Phase C G2A: CSG parent + body static traction threshold V1.

    Parent: acanthostega_continuous_surface_geometry_config() then enable body_static_traction_threshold.
    Implements arch stage G2A_STATIC_TRACTION_THRESHOLD (alias body_static_traction).
    N=m_eff·g (no n_z); Gentle damp bypass via BNLT; FOGF twin deferred.
    """
    from mechanistic_mind.physical_system.body_static_traction_threshold import (
        BodyStaticTractionThresholdConfig,
        set_body_static_traction_threshold,
    )

    cfg = acanthostega_continuous_surface_geometry_config()
    cfg.public_preset = PUBLIC_PRESET_STATIC_TRACTION
    cfg.body_static_traction_threshold = BodyStaticTractionThresholdConfig(enabled=True)
    set_body_static_traction_threshold(cfg, True)
    return cfg


def acanthostega_free_object_static_traction_config():
    """Phase C FOGF twin: body static traction parent + free object static traction threshold V1.

    Parent: acanthostega_static_traction_config() then enable free_resource_object_static_traction_threshold.
    Arch stage FOGF_STATIC_TRACTION_TWIN. N=m·g (no n_z). Body G2A unchanged.
    """
    from mechanistic_mind.physical_system.free_resource_object_static_traction_threshold import (
        FreeResourceObjectStaticTractionThresholdConfig,
        set_free_resource_object_static_traction_threshold,
    )

    cfg = acanthostega_static_traction_config()
    cfg.public_preset = PUBLIC_PRESET_FREE_OBJECT_STATIC_TRACTION
    cfg.free_resource_object_static_traction_threshold = FreeResourceObjectStaticTractionThresholdConfig(enabled=True)
    set_free_resource_object_static_traction_threshold(cfg, True)
    return cfg



def acanthostega_radius_aware_support_config():
    """Phase C G2B: FOGF static twin parent + radius-aware support points Hybrid C⋆ V1.

    Parent: acanthostega_free_object_static_traction_config() then enable radius_aware_support_points.
    CENTRE_Z_AUTHORITY; RING_CLASSIFICATION_ONLY; ONE_PE=SES_DDA; NORMAL=NO.
    """
    from mechanistic_mind.physical_system.radius_aware_support_points import (
        RadiusAwareSupportPointsConfig,
        set_radius_aware_support_points,
    )

    cfg = acanthostega_free_object_static_traction_config()
    cfg.public_preset = PUBLIC_PRESET_RADIUS_AWARE_SUPPORT
    cfg.radius_aware_support_points = RadiusAwareSupportPointsConfig(enabled=True)
    set_radius_aware_support_points(cfg, True)
    return cfg


def acanthostega_ses_decomposition_contract_config():
    """Phase C G2C1: radius-aware support parent + SES decomposition contract.

    Parent: acanthostega_radius_aware_support_config() then enable ses_decomposition_contract.
    Contract-only: no PE law change, no physics mutation. Adds transition taxonomy,
    explicit PE authority stamp, researcher-only receipts, snapshot compatibility.
    PE_AUTHORITY = SES_DDA; NORMAL=NO; TANGENT_GRAVITY=NO; SLOPE_SLIDING=NO.
    """
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        SesDecompositionContractConfig,
        set_ses_decomposition_contract,
    )

    cfg = acanthostega_radius_aware_support_config()
    cfg.public_preset = PUBLIC_PRESET_SES_DECOMPOSITION_CONTRACT
    cfg.ses_decomposition_contract = SesDecompositionContractConfig(enabled=True)
    set_ses_decomposition_contract(cfg, True)
    return cfg


def acanthostega_ses_runtime_classifier_config():
    """Phase C G2C2: G2C1 parent + SES runtime transition classifier.

    Parent: acanthostega_ses_decomposition_contract_config() then enable
    ses_runtime_transition_classifier. Classification/provenance only — no PE law
    change, no physics mutation. PE_AUTHORITY = SES_DDA remains.
    """
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        SesRuntimeTransitionClassifierConfig,
        set_ses_runtime_transition_classifier,
    )

    cfg = acanthostega_ses_decomposition_contract_config()
    cfg.public_preset = PUBLIC_PRESET_SES_RUNTIME_CLASSIFIER
    cfg.ses_runtime_transition_classifier = SesRuntimeTransitionClassifierConfig(enabled=True)
    set_ses_runtime_transition_classifier(cfg, True)
    return cfg





def acanthostega_coherent_slope_dynamics_config():
    """Phase C coherent slope dynamics (atomic live g_t + projected N + hold).

    Parent: tangent gravity diagnostic shadow. Enables coherent_slope_dynamics:
    Policy C endpoint ΔU becomes measurement-only; FREE-object slope dynamics
    remain OFF. Force-aware kinetic rest lets post-breakaway motion accumulate
    under repository g≈0.018. Face Sweep unchanged — passive regime uses slopes
    with cell Δh ≤ MICRORELIEF_THRESHOLD.
    """
    from mechanistic_mind.physical_system.coherent_slope_dynamics import (
        CoherentSlopeDynamicsConfig,
        set_coherent_slope_dynamics,
    )

    cfg = acanthostega_tangent_gravity_diagnostic_shadow_config()
    cfg.public_preset = PUBLIC_PRESET_COHERENT_SLOPE_DYNAMICS
    cfg.coherent_slope_dynamics = CoherentSlopeDynamicsConfig(enabled=True)
    set_coherent_slope_dynamics(cfg, True)
    return cfg


def acanthostega_conservative_surface_material_separation_config():
    """Beta 4: conserved column top-slice → ResourceObject via WMT.

    Parent: coherent slope dynamics (frozen Phase C). Researcher-only trigger.
    No DIG/EXCAVATE agent action. Does not modify Phase C parent physics.
    """
    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        ConservativeSurfaceMaterialSeparationConfig,
        set_conservative_surface_material_separation,
    )

    cfg = acanthostega_coherent_slope_dynamics_config()
    cfg.public_preset = PUBLIC_PRESET_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION
    cfg.conservative_surface_material_separation = ConservativeSurfaceMaterialSeparationConfig(
        enabled=True
    )
    set_conservative_surface_material_separation(cfg, True)
    return cfg


def acanthostega_effector_terrain_contact_geometry_config():
    """Beta 4: effector ↔ authoritative terrain contact geometry (fact only).

    Parent: conservative surface material separation. No exertion / failure /
    separation trigger. No DIG / TOUCH_GROUND action.
    """
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        EffectorTerrainContactGeometryConfig,
        set_effector_terrain_contact_geometry,
    )

    cfg = acanthostega_conservative_surface_material_separation_config()
    cfg.public_preset = PUBLIC_PRESET_EFFECTOR_TERRAIN_CONTACT_GEOMETRY
    cfg.effector_terrain_contact_geometry = EffectorTerrainContactGeometryConfig(enabled=True)
    set_effector_terrain_contact_geometry(cfg, True)
    return cfg


def acanthostega_manipulator_relative_world_actuation_config():
    """Beta 4: body-local vertical relative tip DOF (kinematic only).

    Parent: effector terrain contact geometry. No force/mass/work/impulse.
    No REACH/TOUCH/DIG cognition actions.
    """
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        ManipulatorRelativeWorldActuationConfig,
        set_manipulator_relative_world_actuation,
    )

    cfg = acanthostega_effector_terrain_contact_geometry_config()
    cfg.public_preset = PUBLIC_PRESET_MANIPULATOR_RELATIVE_WORLD_ACTUATION
    cfg.manipulator_relative_world_actuation = ManipulatorRelativeWorldActuationConfig(
        enabled=True
    )
    set_manipulator_relative_world_actuation(cfg, True)
    return cfg


def acanthostega_effector_bounded_actuator_effort_config():
    """Beta 4: bounded actuator effort along relative_z.

    Parent: manipulator relative world actuation. No tip mass / metabolism /
    terrain resistance / DIG. Cognition repertoire unchanged.
    """
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        EffectorBoundedActuatorEffortConfig,
        set_effector_bounded_actuator_effort,
    )

    cfg = acanthostega_manipulator_relative_world_actuation_config()
    cfg.public_preset = PUBLIC_PRESET_EFFECTOR_BOUNDED_ACTUATOR_EFFORT
    cfg.effector_bounded_actuator_effort = EffectorBoundedActuatorEffortConfig(enabled=True)
    set_effector_bounded_actuator_effort(cfg, True)
    return cfg


def acanthostega_surface_exertion_terrain_material_resistance_config():
    """Beta 4: work-based terrain material resistance → existing separation WMT.

    Parent: effector bounded actuator effort. No DIG / pressure / tip mass.
    Cognition repertoire unchanged.
    """
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        SurfaceExertionTerrainMaterialResistanceConfig,
        set_surface_exertion_terrain_material_resistance,
    )

    cfg = acanthostega_effector_bounded_actuator_effort_config()
    cfg.public_preset = PUBLIC_PRESET_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE
    cfg.surface_exertion_terrain_material_resistance = (
        SurfaceExertionTerrainMaterialResistanceConfig(enabled=True)
    )
    set_surface_exertion_terrain_material_resistance(cfg, True)
    return cfg


def acanthostega_effector_held_occupancy_exertion_bridge_config():
    """VW5: occupancy-aware effector/held contact + exertion → VW3 bridge.

    Parent: surface exertion. Enables VW1–VW3 (+ WMT). No DIG/BUILD/PLACE.
    VW4 physical reintegration trigger intentionally not bridged.
    """
    from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
        set_effector_held_occupancy_exertion_bridge,
    )

    cfg = acanthostega_surface_exertion_terrain_material_resistance_config()
    set_effector_held_occupancy_exertion_bridge(cfg, True)
    return cfg


def acanthostega_minimal_vision_3d_geometric_interface_config():
    """VW6: physical XYZ + VW1 occupancy LOS for near-field vision.

    Parent: VW5 bridge stack (VW1–VW5). Geometry constrains visual exposure;
    phenotype/receptor boundary preserved. No cave/above/below semantics.
    No renderer. VW4 physical reintegration trigger remains blocked.
    """
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        set_minimal_vision_3d_geometric_interface,
    )

    cfg = acanthostega_effector_held_occupancy_exertion_bridge_config()
    set_minimal_vision_3d_geometric_interface(cfg, True)
    return cfg



def acanthostega_volumetric_world_vw7_config():
    """Public cumulative volumetric tip: VW1–VW6 physical stack + passive VW7 Observer consumer.

    Parent builder: acanthostega_minimal_vision_3d_geometric_interface_config (VW6).
    VW7 is not a physics mechanism — Observer MAP/VOLUME consume VW1 when active.
    Held→world physical reintegration trigger remains BLOCKED (VW5).
    Does not inherit post-SETMR Free-Space V1D tip features (documented fork).
    """
    cfg = acanthostega_minimal_vision_3d_geometric_interface_config()
    cfg.public_preset = PUBLIC_PRESET_VOLUMETRIC_WORLD_VW7
    cfg.model_line = "ACANTHOSTEGA"
    return cfg


def acanthostega_beta4_config():
    """Public cumulative Acanthostega Beta 4.0 model.

    Parent: release/excavation Free-Space V1D tip (complete pre-VW Beta 4 chain).
    Enables VW5 (+VW3) and VW6 (+VW4 config) on that tip so Free-Space V1A–V1D and
    VW1–VW6 coexist. VW7 remains a passive Observer consumer when VW1 is active.
    Held→world physical reintegration trigger remains BLOCKED.
    """
    from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
        set_effector_held_occupancy_exertion_bridge,
    )
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        set_minimal_vision_3d_geometric_interface,
    )

    cfg = acanthostega_release_and_excavation_support_loss_integration_config()
    set_effector_held_occupancy_exertion_bridge(cfg, True)
    set_minimal_vision_3d_geometric_interface(cfg, True)
    from mechanistic_mind.physical_system.effector_occupancy_reachability_trace import (
        set_effector_occupancy_reachability_trace,
    )

    set_effector_occupancy_reachability_trace(cfg, True)
    from mechanistic_mind.physical_system.physical_optical_material_profile import (
        set_physical_optical_material_profile,
    )

    set_physical_optical_material_profile(cfg, True)
    from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
        set_exposed_surface_optical_interaction_authority,
    )

    set_exposed_surface_optical_interaction_authority(cfg, True)
    from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
        set_abstract_spectral_light_source_and_direct_transport,
    )

    set_abstract_spectral_light_source_and_direct_transport(cfg, True)
    from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
        set_object_body_held_optical_surfaces,
    )

    set_object_body_held_optical_surfaces(cfg, True)
    from mechanistic_mind.physical_system.organism_physical_optical_reception import (
        set_organism_physical_optical_reception,
    )

    set_organism_physical_optical_reception(cfg, True)
    from mechanistic_mind.physical_system.sensory_modality_temporal_alignment import (
        set_sensory_modality_temporal_alignment,
    )

    set_sensory_modality_temporal_alignment(cfg, True)
    cfg.public_preset = PUBLIC_PRESET_BETA4
    cfg.model_line = "ACANTHOSTEGA"
    # Canonical public Beta 4.0 cognition defaults (author decisions):
    # PSC begins OFF at tick 0; auto-enable schedule defaults to tick 1000;
    # motor resolution defaults to OBSERVED_COMPOSITE. Distinct fields.
    cog = cfg.cognition
    cog.prospective_selection = "LEGACY_FIRST"
    cog.psc_off_ticks = 1000
    cog.psc_motor_resolution = "OBSERVED_COMPOSITE"
    return cfg



def acanthostega_held_resource_object_terrain_contact_geometry_config():
    """Beta 4: held ResourceObject ↔ authoritative terrain contact geometry.

    Parent: surface exertion / material resistance. Geometry fact only —
    no work transmission, failure, WMT, impulse, or sound from held-terrain contact.
    """
    from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
        HeldResourceObjectTerrainContactGeometryConfig,
        set_held_resource_object_terrain_contact_geometry,
    )

    cfg = acanthostega_surface_exertion_terrain_material_resistance_config()
    cfg.public_preset = PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY
    cfg.held_resource_object_terrain_contact_geometry = (
        HeldResourceObjectTerrainContactGeometryConfig(enabled=True)
    )
    set_held_resource_object_terrain_contact_geometry(cfg, True)
    return cfg


def acanthostega_held_resource_object_terrain_mechanical_transmission_config():
    """Beta 4: held ResourceObject ↔ terrain mechanical transmission V1.

    Parent: held terrain contact geometry. Bounded actuator work via held
    relative_z constraint + transmitted-work partition. No SETMR/WMT/failure.
    """
    from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
        HeldResourceObjectTerrainMechanicalTransmissionConfig,
        set_held_resource_object_terrain_mechanical_transmission,
    )

    cfg = acanthostega_held_resource_object_terrain_contact_geometry_config()
    cfg.public_preset = PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION
    cfg.held_resource_object_terrain_mechanical_transmission = (
        HeldResourceObjectTerrainMechanicalTransmissionConfig(enabled=True)
    )
    set_held_resource_object_terrain_mechanical_transmission(cfg, True)
    return cfg


def acanthostega_held_mediated_surface_exertion_integration_config():
    """Beta 4: route held transmission work into existing SETMR / WMT.

    Parent: held terrain mechanical transmission. Integration only — same
    accumulator, same separation_work_per_quantity, same failure gate, same
    SEPARATE_SURFACE_COLUMN_SLICE. No new resistance/transmission law.
    """
    from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
        HeldMediatedSurfaceExertionIntegrationConfig,
        set_held_mediated_surface_exertion_integration,
    )

    cfg = acanthostega_held_resource_object_terrain_mechanical_transmission_config()
    cfg.public_preset = PUBLIC_PRESET_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION
    cfg.held_mediated_surface_exertion_integration = (
        HeldMediatedSurfaceExertionIntegrationConfig(enabled=True)
    )
    set_held_mediated_surface_exertion_integration(cfg, True)
    return cfg


def acanthostega_detached_terrain_material_initial_placement_config():
    """Beta 4: post-mutation support placement for SEPARATE_SURFACE_COLUMN_SLICE.

    Parent: held-mediated surface exertion integration. Placement kernel only —
    same WMT, fixed radius, zero velocity, dynamics from T+1.
    """
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        DetachedTerrainMaterialInitialPlacementConfig,
        set_detached_terrain_material_initial_placement,
    )

    cfg = acanthostega_held_mediated_surface_exertion_integration_config()
    cfg.public_preset = PUBLIC_PRESET_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
    cfg.detached_terrain_material_initial_placement = (
        DetachedTerrainMaterialInitialPlacementConfig(enabled=True)
    )
    set_detached_terrain_material_initial_placement(cfg, True)
    return cfg



def acanthostega_bnlt_move_breakaway_locomotion_repair_config():
    """Beta 4: BNLT MOVE breakaway locomotion repair V1.

    Parent: detached terrain material initial placement. Gates drive_accel
    authority from capacity-limited MOVE impulse. Does not weaken μ_k.
    """
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        BnltMoveBreakawayLocomotionRepairConfig,
        set_bnlt_move_breakaway_locomotion_repair,
    )

    cfg = acanthostega_detached_terrain_material_initial_placement_config()
    cfg.public_preset = PUBLIC_PRESET_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
    cfg.bnlt_move_breakaway_locomotion_repair = BnltMoveBreakawayLocomotionRepairConfig(
        enabled=True
    )
    set_bnlt_move_breakaway_locomotion_repair(cfg, True)
    return cfg


def acanthostega_active_locomotion_traction_vs_sliding_friction_config():
    """Beta 4: active locomotion traction vs sliding friction V1.

    Parent: repeated conservative surface-column separation (cumulative RCSS world).
    Adds only active-locomotion traction/sliding repair on top of RCSS+BNLT.
    """
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        ActiveLocomotionTractionVsSlidingFrictionConfig,
        set_active_locomotion_traction_vs_sliding_friction,
    )

    cfg = acanthostega_repeated_conservative_surface_column_separation_config()
    cfg.public_preset = PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
    cfg.active_locomotion_traction_vs_sliding_friction = (
        ActiveLocomotionTractionVsSlidingFrictionConfig(enabled=True)
    )
    set_active_locomotion_traction_vs_sliding_friction(cfg, True)
    return cfg


def acanthostega_event_driven_crowded_placement_retry_contract_config():
    """Beta 4: event-driven crowded placement retry contract V1.

    Parent: active locomotion traction vs sliding friction (cumulative tip).
    Formalizes SETMR→WMT→DTIP crowded rejection: one attempt per eligible
    exertion event, no background retry, K=16 frozen. No placement physics change.
    """
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        EventDrivenCrowdedPlacementRetryContractConfig,
        set_event_driven_crowded_placement_retry_contract,
    )

    cfg = acanthostega_active_locomotion_traction_vs_sliding_friction_config()
    cfg.public_preset = PUBLIC_PRESET_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
    cfg.event_driven_crowded_placement_retry_contract = (
        EventDrivenCrowdedPlacementRetryContractConfig(enabled=True)
    )
    set_event_driven_crowded_placement_retry_contract(cfg, True)
    return cfg


def acanthostega_detached_material_amount_scaled_collision_radius_config():
    """Beta 4: detached material amount-scaled collision radius V1.

    Parent: event-driven crowded placement retry contract (cumulative tip).
    Creation-time quantity∛ collision radius for SEPARATE_SURFACE_COLUMN_SLICE
    objects only. r∈[0.08,0.25]; no post-creation resize; optical unchanged.
    """
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        DetachedMaterialAmountScaledCollisionRadiusConfig,
        set_detached_material_amount_scaled_collision_radius,
    )

    cfg = acanthostega_event_driven_crowded_placement_retry_contract_config()
    cfg.public_preset = PUBLIC_PRESET_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
    cfg.detached_material_amount_scaled_collision_radius = (
        DetachedMaterialAmountScaledCollisionRadiusConfig(enabled=True)
    )
    set_detached_material_amount_scaled_collision_radius(cfg, True)
    return cfg


def acanthostega_held_combine_radius_resize_transaction_config():
    """Beta 4: held COMBINE radius resize transaction V1.

    Parent: detached material amount-scaled collision radius (creation-size tip).
    Atomic geometry admission for profile-stamped COMBINE survivors; growth-only.
    """
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
        HeldCombineRadiusResizeTransactionConfig,
        set_held_combine_radius_resize_transaction,
    )

    cfg = acanthostega_detached_material_amount_scaled_collision_radius_config()
    cfg.public_preset = PUBLIC_PRESET_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
    cfg.held_combine_radius_resize_transaction = (
        HeldCombineRadiusResizeTransactionConfig(enabled=True)
    )
    set_held_combine_radius_resize_transaction(cfg, True)
    return cfg


def acanthostega_held_deposition_radius_shrink_transaction_config():
    """Beta 4: held deposition radius shrink transaction V1.

    Parent: held COMBINE radius resize transaction (COMBINE-resize tip).
    Atomic geometry admission for profile-stamped held sources on APPLY_TO_SURFACE;
    shrink-only; released PE dissipated / non-recoverable.
    """
    from mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction import (
        HeldDepositionRadiusShrinkTransactionConfig,
        set_held_deposition_radius_shrink_transaction,
    )

    cfg = acanthostega_held_combine_radius_resize_transaction_config()
    cfg.public_preset = PUBLIC_PRESET_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
    cfg.held_deposition_radius_shrink_transaction = (
        HeldDepositionRadiusShrinkTransactionConfig(enabled=True)
    )
    set_held_deposition_radius_shrink_transaction(cfg, True)
    return cfg


def acanthostega_free_space_state_and_pe_authority_contract_config():
    """Free-Space V1A: support-state + PE authority contract.

    Parent: held deposition radius shrink tip.
    Formalizes SUPPORTED/UNSUPPORTED/TERRAIN_INTERSECT classification,
    mutually exclusive PE authority, and supported-rest gravity skip.
    Does NOT replace FGG integrator; no landing impulse/sound.
    """
    from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
        FreeSpaceStateAndPeAuthorityContractConfig,
        set_free_space_state_and_pe_authority_contract,
    )

    cfg = acanthostega_held_deposition_radius_shrink_transaction_config()
    cfg.public_preset = PUBLIC_PRESET_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
    cfg.free_space_state_and_pe_authority_contract = (
        FreeSpaceStateAndPeAuthorityContractConfig(enabled=True)
    )
    set_free_space_state_and_pe_authority_contract(cfg, True)
    return cfg


def acanthostega_vertical_terrain_landing_contact_response_config():
    """Free-Space V1B: vertical terrain landing contact + inelastic response.

    Parent: free-space support/PE authority contract.
    Replaces FGG post-step clamp when ON. e=0; no rebound; no impact sound.
    """
    from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
        VerticalTerrainLandingContactResponseConfig,
        set_vertical_terrain_landing_contact_response,
    )

    cfg = acanthostega_free_space_state_and_pe_authority_contract_config()
    cfg.public_preset = PUBLIC_PRESET_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
    cfg.vertical_terrain_landing_contact_response = (
        VerticalTerrainLandingContactResponseConfig(enabled=True)
    )
    set_vertical_terrain_landing_contact_response(cfg, True)
    return cfg


def acanthostega_vertical_impact_acoustic_emission_config():
    """Free-Space V1C: vertical impact acoustic emission via LPS.

    Parent: vertical terrain landing contact/response.
    Consumes committed landing response dissipation → neutral broadband LPS.
    No human playback. Persistent support / fact-only remain silent.
    """
    from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
        VerticalImpactAcousticEmissionConfig,
        set_vertical_impact_acoustic_emission,
    )

    cfg = acanthostega_vertical_terrain_landing_contact_response_config()
    cfg.public_preset = PUBLIC_PRESET_VERTICAL_IMPACT_ACOUSTIC_EMISSION
    cfg.vertical_impact_acoustic_emission = VerticalImpactAcousticEmissionConfig(
        enabled=True
    )
    set_vertical_impact_acoustic_emission(cfg, True)
    return cfg



def acanthostega_release_and_excavation_support_loss_integration_config():
    """Free-Space V1D: RELEASE + excavation support-loss entry into shared V1 chain.

    Parent: vertical impact acoustic emission (V1C).
    Stamps RELEASE T+1 eligibility; completes excavation affected-entity refresh.
    No private landing/sound path.
    """
    from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
        ReleaseAndExcavationSupportLossIntegrationConfig,
        set_release_and_excavation_support_loss_integration,
    )

    cfg = acanthostega_vertical_impact_acoustic_emission_config()
    cfg.public_preset = PUBLIC_PRESET_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
    cfg.release_and_excavation_support_loss_integration = (
        ReleaseAndExcavationSupportLossIntegrationConfig(enabled=True)
    )
    set_release_and_excavation_support_loss_integration(cfg, True)
    return cfg


def acanthostega_repeated_conservative_surface_column_separation_config():
    """Beta 4: repeated conservative surface-column separation V1.

    Parent: BNLT MOVE breakaway locomotion repair. Gates cell/tick cap,
    clear-on-commit accumulator, surplus discard. Reuses existing WMT/DTIP.
    Does NOT enable active locomotion (child tip owns that).
    """
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        RepeatedConservativeSurfaceColumnSeparationConfig,
        set_repeated_conservative_surface_column_separation,
    )

    cfg = acanthostega_bnlt_move_breakaway_locomotion_repair_config()
    cfg.public_preset = PUBLIC_PRESET_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
    cfg.repeated_conservative_surface_column_separation = (
        RepeatedConservativeSurfaceColumnSeparationConfig(enabled=True)
    )
    set_repeated_conservative_surface_column_separation(cfg, True)
    return cfg



def acanthostega_tangent_gravity_diagnostic_shadow_config():
    """Phase C tangent-gravity diagnostic shadow (researcher-only).

    Parent: Policy C continuous PE. Computes candidate g_t from CSG n̂.
    Does not activate tangent gravity, projected N, or passive sliding.
    """
    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
        TangentGravityDiagnosticShadowConfig,
        set_tangent_gravity_diagnostic_shadow,
    )

    cfg = acanthostega_continuous_pe_policy_c_config()
    cfg.public_preset = PUBLIC_PRESET_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW
    cfg.tangent_gravity_diagnostic_shadow = TangentGravityDiagnosticShadowConfig(enabled=True)
    set_tangent_gravity_diagnostic_shadow(cfg, True)
    return cfg


def acanthostega_continuous_pe_policy_c_config():
    """Phase C Policy C: exclusive continuous endpoint gravitational PE authority.

    Parent: acanthostega_continuous_gravitational_pe_diagnostic_shadow_config() then
    enable continuous_gravitational_pe with ENDPOINT authority. SES remains gate only.
    Projected N / tangent gravity / passive sliding stay OFF.
    """
    from mechanistic_mind.physical_system.continuous_gravitational_pe import (
        ContinuousGravitationalPeConfig,
        GRAV_PE_AUTH_ENDPOINT,
        set_continuous_gravitational_pe,
    )

    cfg = acanthostega_continuous_gravitational_pe_diagnostic_shadow_config()
    cfg.public_preset = PUBLIC_PRESET_CONTINUOUS_PE_POLICY_C
    cfg.continuous_gravitational_pe = ContinuousGravitationalPeConfig(
        enabled=True,
        gravitational_pe_authority=GRAV_PE_AUTH_ENDPOINT,
    )
    set_continuous_gravitational_pe(cfg, True)
    return cfg


def acanthostega_continuous_gravitational_pe_diagnostic_shadow_config():
    """Phase C continuous gravitational PE diagnostic shadow.

    Parent: acanthostega_diagnostic_normal_load_shadow_config() then enable
    continuous_gravitational_pe_diagnostic_shadow. Researcher-only; PE authority
    remains SES_DDA; candidate endpoint ΔU does not feed physics.
    """
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
        ContinuousGravitationalPeDiagnosticShadowConfig,
        set_continuous_gravitational_pe_diagnostic_shadow,
    )

    cfg = acanthostega_diagnostic_normal_load_shadow_config()
    cfg.public_preset = PUBLIC_PRESET_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW
    cfg.continuous_gravitational_pe_diagnostic_shadow = ContinuousGravitationalPeDiagnosticShadowConfig(enabled=True)
    set_continuous_gravitational_pe_diagnostic_shadow(cfg, True)
    return cfg


def acanthostega_diagnostic_normal_load_shadow_config():
    """Phase C G2D diagnostic shadow: face-sweep parent + continuous normal-load shadow V1.

    Parent: acanthostega_radius_aware_face_sweep_config() then enable
    diagnostic_normal_load_shadow. Researcher-only; physical N remains flat m·g.
    """
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        DiagnosticNormalLoadShadowConfig,
        set_diagnostic_normal_load_shadow,
    )

    cfg = acanthostega_radius_aware_face_sweep_config()
    cfg.public_preset = PUBLIC_PRESET_DIAGNOSTIC_NORMAL_LOAD_SHADOW
    cfg.diagnostic_normal_load_shadow = DiagnosticNormalLoadShadowConfig(enabled=True)
    set_diagnostic_normal_load_shadow(cfg, True)
    return cfg


def acanthostega_radius_aware_face_sweep_config():
    """Phase C face-sweep: G2C2 parent + radius-aware face sweep SES plan evidence V1.

    Parent: acanthostega_ses_runtime_classifier_config() then enable
    radius_aware_face_sweep. May block via SES; PE_AUTHORITY = SES_DDA; no radius PE.
    """
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        RadiusAwareFaceSweepConfig,
        set_radius_aware_face_sweep,
    )

    cfg = acanthostega_ses_runtime_classifier_config()
    cfg.public_preset = PUBLIC_PRESET_RADIUS_AWARE_FACE_SWEEP
    cfg.radius_aware_face_sweep = RadiusAwareFaceSweepConfig(enabled=True)
    set_radius_aware_face_sweep(cfg, True)
    return cfg


def acanthostega_free_object_kinematics_config():
    """Phase B: column transfer (material/manipulation chain) + free ResourceObject kinematics.

    Branches from COLUMN_TRANSFER, not from Audio A/B: the kinematics depends on objects, bilateral
    grasp/release, the spatial index and world material transactions, never on signal transport.
    RELEASE passes the measured effector velocity; free objects damp to exact rest. No collision,
    gravity, z, sound or THROW.
    """
    from mechanistic_mind.physical_system.free_resource_object_kinematics import (
        FreeObjectKinematicsConfig,
        set_free_resource_object_kinematics,
    )

    cfg = acanthostega_column_transfer_config()
    cfg.public_preset = PUBLIC_PRESET_FREE_OBJECT_KINEMATICS
    cfg.free_resource_object_kinematics = FreeObjectKinematicsConfig(enabled=True)
    set_free_resource_object_kinematics(cfg, True)
    return cfg


def model_metadata(config=None, *, seed: int | None = None, tick: int | None = None) -> dict[str, Any]:
    preset = _preset_of(config)
    coherent_slope_dynamics = (
        preset == PUBLIC_PRESET_COHERENT_SLOPE_DYNAMICS
        or "COHERENT_SLOPE_DYNAMICS" in preset.upper()
    )
    surface_material_separation = (
        preset == PUBLIC_PRESET_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION
        or "CONSERVATIVE_SURFACE_MATERIAL_SEPARATION" in preset.upper()
        or ("SURFACE_MATERIAL_SEPARATION" in preset.upper() and "ACANTHOSTEGA" in preset.upper())
    )
    effector_terrain_contact_geometry = (
        preset == PUBLIC_PRESET_EFFECTOR_TERRAIN_CONTACT_GEOMETRY
        or "EFFECTOR_TERRAIN_CONTACT_GEOMETRY" in preset.upper()
        or ("EFFECTOR_TERRAIN_CONTACT" in preset.upper() and "ACANTHOSTEGA" in preset.upper())
    )
    manipulator_relative_world_actuation = (
        preset == PUBLIC_PRESET_MANIPULATOR_RELATIVE_WORLD_ACTUATION
        or "MANIPULATOR_RELATIVE_WORLD_ACTUATION" in preset.upper()
        or ("RELATIVE_WORLD_ACTUATION" in preset.upper() and "ACANTHOSTEGA" in preset.upper())
    )
    effector_bounded_actuator_effort = (
        preset == PUBLIC_PRESET_EFFECTOR_BOUNDED_ACTUATOR_EFFORT
        or "EFFECTOR_BOUNDED_ACTUATOR_EFFORT" in preset.upper()
        or ("BOUNDED_ACTUATOR_EFFORT" in preset.upper() and "ACANTHOSTEGA" in preset.upper())
    )
    surface_exertion_terrain_material_resistance = (
        preset == PUBLIC_PRESET_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE
        or "SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE" in preset.upper()
        or (
            "SURFACE_EXERTION" in preset.upper()
            and "MATERIAL_RESISTANCE" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    held_resource_object_terrain_contact_geometry = (
        preset == PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY
        or "HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY" in preset.upper()
        or (
            "HELD" in preset.upper()
            and "TERRAIN_CONTACT" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
            and "FOREIGN" not in preset.upper()
            and "MECHANICAL_TRANSMISSION" not in preset.upper()
        )
    )
    held_resource_object_terrain_mechanical_transmission = (
        preset == PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION
        or "HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION" in preset.upper()
        or (
            "HELD" in preset.upper()
            and "TERRAIN" in preset.upper()
            and "MECHANICAL_TRANSMISSION" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
            and "MEDIATED" not in preset.upper()
        )
    )
    held_mediated_surface_exertion_integration = (
        preset == PUBLIC_PRESET_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION
        or "HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION" in preset.upper()
        or (
            "HELD" in preset.upper()
            and "MEDIATED" in preset.upper()
            and "SURFACE_EXERTION" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
            and "DETACHED" not in preset.upper()
        )
    )
    repeated_conservative_surface_column_separation = (
        preset == PUBLIC_PRESET_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
        or "REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION" in preset.upper()
        or (
            "REPEATED" in preset.upper()
            and "CONSERVATIVE" in preset.upper()
            and "SURFACE_COLUMN" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    active_locomotion_traction_vs_sliding_friction = (
        preset == PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
        or "ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION" in preset.upper()
        or (
            "ACTIVE_LOCOMOTION" in preset.upper()
            and "TRACTION" in preset.upper()
            and "SLIDING" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    event_driven_crowded_placement_retry_contract = (
        preset == PUBLIC_PRESET_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
        or "EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY" in preset.upper()
        or (
            "CROWDED" in preset.upper()
            and "PLACEMENT" in preset.upper()
            and "RETRY" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    held_deposition_radius_shrink_transaction = (
        preset == PUBLIC_PRESET_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
        or "HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION" in preset.upper()
        or (
            "HELD_DEPOSITION" in preset.upper()
            and "RADIUS_SHRINK" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    vertical_terrain_landing_contact_response = (
        preset == PUBLIC_PRESET_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
        or "VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE" in preset.upper()
        or (
            "VERTICAL_TERRAIN" in preset.upper()
            and "LANDING" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    vertical_impact_acoustic_emission = (
        preset == PUBLIC_PRESET_VERTICAL_IMPACT_ACOUSTIC_EMISSION
        or "VERTICAL_IMPACT_ACOUSTIC_EMISSION" in preset.upper()
        or (
            "VERTICAL_IMPACT" in preset.upper()
            and "ACOUSTIC" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    beta4_public_model = (
        preset == PUBLIC_PRESET_BETA4
        or preset.upper() in {"ACANTHOSTEGA_BETA4", "ACANTHOSTEGA_BETA4_0", "BETA4_0"}
        or (
            preset.upper().endswith("_BETA4")
            and "ACANTHOSTEGA" in preset.upper()
            and "VOLUMETRIC" not in preset.upper()
            and "RELEASE" not in preset.upper()
            and "FREE_SPACE" not in preset.upper()
        )
    )
    volumetric_world_vw7 = (
        preset == PUBLIC_PRESET_VOLUMETRIC_WORLD_VW7
        or "VOLUMETRIC_WORLD_VW7" in preset.upper()
        or (
            "VOLUMETRIC_WORLD" in preset.upper()
            and "VW7" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    release_and_excavation_support_loss_integration = (
        preset == PUBLIC_PRESET_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        or "RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION" in preset.upper()
        or (
            "RELEASE" in preset.upper()
            and "EXCAVATION" in preset.upper()
            and "SUPPORT_LOSS" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    free_space_state_and_pe_authority_contract = (
        preset == PUBLIC_PRESET_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
        or "FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT" in preset.upper()
        or (
            "FREE_SPACE" in preset.upper()
            and "PE_AUTHORITY" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    held_combine_radius_resize_transaction = (
        preset == PUBLIC_PRESET_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
        or "HELD_COMBINE_RADIUS_RESIZE_TRANSACTION" in preset.upper()
        or (
            "HELD_COMBINE" in preset.upper()
            and "RADIUS_RESIZE" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    detached_material_amount_scaled_collision_radius = (
        preset == PUBLIC_PRESET_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
        or "DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS" in preset.upper()
        or (
            "AMOUNT_SCALED" in preset.upper()
            and "COLLISION_RADIUS" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    bnlt_move_breakaway_locomotion_repair = (
        preset == PUBLIC_PRESET_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
        or "BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR" in preset.upper()
        or (
            "BNLT" in preset.upper()
            and "BREAKAWAY" in preset.upper()
            and "LOCOMOTION" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    detached_terrain_material_initial_placement = (
        preset == PUBLIC_PRESET_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
        or "DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT" in preset.upper()
        or (
            "DETACHED" in preset.upper()
            and "TERRAIN" in preset.upper()
            and "INITIAL_PLACEMENT" in preset.upper()
            and "ACANTHOSTEGA" in preset.upper()
        )
    )
    if repeated_conservative_surface_column_separation:
        bnlt_move_breakaway_locomotion_repair = True
    if release_and_excavation_support_loss_integration:
        vertical_impact_acoustic_emission = True
    if vertical_impact_acoustic_emission:
        vertical_terrain_landing_contact_response = True
    if vertical_terrain_landing_contact_response:
        free_space_state_and_pe_authority_contract = True
    if free_space_state_and_pe_authority_contract:
        held_deposition_radius_shrink_transaction = True
    if held_deposition_radius_shrink_transaction:
        held_combine_radius_resize_transaction = True
    if held_combine_radius_resize_transaction:
        detached_material_amount_scaled_collision_radius = True
    if detached_material_amount_scaled_collision_radius:
        # Cumulative tip inherits crowded retry (+ ALTVSF + RCSS + BNLT).
        event_driven_crowded_placement_retry_contract = True
    if event_driven_crowded_placement_retry_contract:
        # Cumulative tip inherits ALTVSF (+ RCSS + BNLT).
        active_locomotion_traction_vs_sliding_friction = True
    if active_locomotion_traction_vs_sliding_friction:
        # Cumulative tip inherits RCSS (+ BNLT via RCSS).
        repeated_conservative_surface_column_separation = True
        bnlt_move_breakaway_locomotion_repair = True
    if bnlt_move_breakaway_locomotion_repair:
        detached_terrain_material_initial_placement = True
    if detached_terrain_material_initial_placement:
        held_mediated_surface_exertion_integration = True
    if held_mediated_surface_exertion_integration:
        held_resource_object_terrain_mechanical_transmission = True
    if held_resource_object_terrain_mechanical_transmission:
        held_resource_object_terrain_contact_geometry = True
    if held_resource_object_terrain_contact_geometry:
        surface_exertion_terrain_material_resistance = True
    if surface_exertion_terrain_material_resistance:
        effector_bounded_actuator_effort = True
    if effector_bounded_actuator_effort:
        manipulator_relative_world_actuation = True
    if manipulator_relative_world_actuation:
        effector_terrain_contact_geometry = True
    if effector_terrain_contact_geometry:
        surface_material_separation = True
    if surface_material_separation:
        coherent_slope_dynamics = True
    tangent_gravity_diagnostic_shadow = (not coherent_slope_dynamics) and (
        preset == PUBLIC_PRESET_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW
        or "TANGENT_GRAVITY_DIAGNOSTIC_SHADOW" in preset.upper()
    )
    continuous_pe_policy_c = (not coherent_slope_dynamics) and (not tangent_gravity_diagnostic_shadow) and (
        preset == PUBLIC_PRESET_CONTINUOUS_PE_POLICY_C
        or "CONTINUOUS_PE_POLICY_C" in preset.upper()
        or ("POLICY_C" in preset.upper() and "CONTINUOUS_PE" in preset.upper())
    )
    continuous_gravitational_pe_diagnostic_shadow = (not continuous_pe_policy_c) and (
        preset == PUBLIC_PRESET_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW
        or "CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW" in preset.upper()
        or ("GRAVITATIONAL_PE" in preset.upper() and "SHADOW" in preset.upper() and "ACANTHOSTEGA" in preset.upper())
    )
    diagnostic_normal_load_shadow = (not continuous_pe_policy_c) and (not continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) and (
        preset == PUBLIC_PRESET_DIAGNOSTIC_NORMAL_LOAD_SHADOW
        or "DIAGNOSTIC_NORMAL_LOAD_SHADOW" in preset.upper()
        or "CONTINUOUS_NORMAL_LOAD_SHADOW" in preset.upper()
        or ("G2D" in preset.upper() and "SHADOW" in preset.upper() and "ACANTHOSTEGA" in preset.upper())
    )
    _phase_c_pe_or_n_shadow = continuous_pe_policy_c or continuous_gravitational_pe_diagnostic_shadow or diagnostic_normal_load_shadow
    radius_aware_face_sweep = (not _phase_c_pe_or_n_shadow) and (
        preset == PUBLIC_PRESET_RADIUS_AWARE_FACE_SWEEP
        or "RADIUS_AWARE_FACE_SWEEP" in preset.upper()
        or ("FACE_SWEEP" in preset.upper() and "RADIUS" in preset.upper())
    )
    ses_runtime_classifier = (not _phase_c_pe_or_n_shadow) and (not radius_aware_face_sweep) and (
        preset == PUBLIC_PRESET_SES_RUNTIME_CLASSIFIER
        or "SES_RUNTIME_CLASSIFIER" in preset.upper()
        or "SES_RUNTIME_TRANSITION_CLASSIFIER" in preset.upper()
        or ("G2C2" in preset.upper() and "SES" in preset.upper())
    )
    ses_decomposition_contract = (not _phase_c_pe_or_n_shadow) and (not ses_runtime_classifier) and (not radius_aware_face_sweep) and (
        preset == PUBLIC_PRESET_SES_DECOMPOSITION_CONTRACT
        or "SES_DECOMPOSITION_CONTRACT" in preset.upper()
        or ("SES_DECOMPOSITION" in preset.upper() and "CONTRACT" in preset.upper())
    )
    radius_aware_support = (not _phase_c_pe_or_n_shadow) and (not ses_decomposition_contract) and (not ses_runtime_classifier) and (not radius_aware_face_sweep) and (
        preset == PUBLIC_PRESET_RADIUS_AWARE_SUPPORT
        or "RADIUS_AWARE_SUPPORT" in preset.upper()
        or ("RADIUS_AWARE" in preset.upper() and "SUPPORT" in preset.upper())
    )
    free_object_static_traction = (not radius_aware_support) and (
        preset == PUBLIC_PRESET_FREE_OBJECT_STATIC_TRACTION
        or "FREE_OBJECT_STATIC_TRACTION" in preset.upper()
        or "FREE_RESOURCE_OBJECT_STATIC_TRACTION" in preset.upper()
        or ("FOGF" in preset.upper() and "STATIC" in preset.upper() and "TRACTION" in preset.upper())
    )
    static_traction = (not free_object_static_traction) and (not radius_aware_support) and (
        preset == PUBLIC_PRESET_STATIC_TRACTION
        or (
            "STATIC_TRACTION" in preset.upper()
            and "FREE_OBJECT" not in preset.upper()
            and "FREE_RESOURCE" not in preset.upper()
            and "FOGF" not in preset.upper()
        )
        or ("STATIC" in preset.upper() and "TRACTION" in preset.upper() and "THRESHOLD" in preset.upper() and "ACANTHOSTEGA" in preset.upper() and "FREE" not in preset.upper())
        or ("BODY_STATIC_TRACTION" in preset.upper())
    )
    continuous_surface_geometry = (not free_object_static_traction) and (not static_traction) and (not radius_aware_support) and (
        preset == PUBLIC_PRESET_CONTINUOUS_SURFACE_GEOMETRY
        or "CONTINUOUS_SURFACE_GEOMETRY" in preset.upper()
        or ("CONTINUOUS_SURFACE" in preset.upper() and "GEOMETRY" in preset.upper() and "ACANTHOSTEGA" in preset.upper())
        or ("BILINEAR_HEIGHT" in preset.upper() and "ACANTHOSTEGA" in preset.upper())
    )
    body_normal_load_traction = (not free_object_static_traction) and (not static_traction) and (not continuous_surface_geometry) and (not radius_aware_support) and (
        preset == PUBLIC_PRESET_BODY_NORMAL_LOAD_TRACTION
        or "BODY_NORMAL_LOAD_TRACTION" in preset.upper()
        or ("NORMAL_LOAD" in preset.upper() and "TRACTION" in preset.upper() and "ACANTHOSTEGA" in preset.upper())
        or ("PASSIVE_SLIDING" in preset.upper() and "ACANTHOSTEGA" in preset.upper())
    )
    surface_elevation_support = (not free_object_static_traction) and (not static_traction) and (not continuous_surface_geometry) and (not body_normal_load_traction) and (not radius_aware_support) and (
        preset == PUBLIC_PRESET_SURFACE_ELEVATION_SUPPORT
        or "SURFACE_ELEVATION_SUPPORT" in preset.upper()
        or ("SURFACE_ELEVATION" in preset.upper() and "SUPPORT" in preset.upper())
    )
    free_object_ground_friction = (not static_traction) and (not continuous_surface_geometry) and (not body_normal_load_traction) and (not surface_elevation_support) and (
        preset == PUBLIC_PRESET_FREE_OBJECT_GROUND_FRICTION
        or "FREE_OBJECT_GROUND_FRICTION" in preset.upper()
        or ("GROUND_FRICTION" in preset.upper() and "ACANTHOSTEGA" in preset.upper())
        or ("FREE_OBJECT" in preset.upper() and "FRICTION" in preset.upper())
    )
    flat_ground_gravity = (not static_traction) and (not continuous_surface_geometry) and (not body_normal_load_traction) and (not surface_elevation_support) and (not free_object_ground_friction) and (
        preset == PUBLIC_PRESET_FLAT_GROUND_GRAVITY
        or "FLAT_GROUND_GRAVITY" in preset.upper()
        or ("PHASE_C" in preset.upper() and "FLAT" in preset.upper() and "FRICTION" not in preset.upper())
    )
    effector_work_accounting = (not static_traction) and (not continuous_surface_geometry) and (not body_normal_load_traction) and (not surface_elevation_support) and (not free_object_ground_friction) and (not flat_ground_gravity) and (
        preset == PUBLIC_PRESET_EFFECTOR_WORK_ACCOUNTING
        or "EFFECTOR_WORK_ACCOUNTING" in preset.upper()
        or (
            "EFFECTOR" in preset.upper()
            and "WORK" in preset.upper()
            and "ACCOUNT" in preset.upper()
        )
    )
    held_translational_impulse = (not static_traction) and (not continuous_surface_geometry) and (not body_normal_load_traction) and (not surface_elevation_support) and (not free_object_ground_friction) and (not flat_ground_gravity) and (not effector_work_accounting) and (
        preset == PUBLIC_PRESET_HELD_OBJECT_TRANSLATIONAL_IMPULSE
        or "HELD_OBJECT_TRANSLATIONAL_IMPULSE" in preset.upper()
        or (
            "HELD" in preset.upper()
            and "TRANSLATIONAL" in preset.upper()
            and "IMPULSE" in preset.upper()
        )
    )
    held_foreign_contact = (not static_traction) and (not continuous_surface_geometry) and (not body_normal_load_traction) and (not surface_elevation_support) and (not free_object_ground_friction) and (not flat_ground_gravity) and (not effector_work_accounting) and (not held_translational_impulse) and (
        preset == PUBLIC_PRESET_HELD_OBJECT_FOREIGN_BODY_CONTACT
        or "HELD_OBJECT_FOREIGN_BODY_CONTACT" in preset.upper()
        or (
            "HELD" in preset.upper()
            and "FOREIGN" in preset.upper()
            and "CONTACT" in preset.upper()
            and "IMPULSE" not in preset.upper()
            and "ACOUSTIC" not in preset.upper()
        )
    )
    object_object_impact_acoustics = (not effector_work_accounting and not held_translational_impulse and not held_foreign_contact) and (
        preset == PUBLIC_PRESET_OBJECT_OBJECT_IMPACT_ACOUSTICS
        or "OBJECT_OBJECT_IMPACT_ACOUSTICS" in preset.upper()
        or (
            "OBJECT" in preset.upper()
            and "IMPACT" in preset.upper()
            and "ACOUSTIC" in preset.upper()
            and (
                "OBJECT_OBJECT" in preset.upper()
                or preset.upper().count("OBJECT") >= 2
                or "PAIR" in preset.upper()
            )
        )
    )
    object_object_impulse = (not held_foreign_contact) and (not object_object_impact_acoustics) and (
        preset == PUBLIC_PRESET_OBJECT_OBJECT_IMPULSE
        or "OBJECT_OBJECT_IMPULSE" in preset.upper()
        or (
            "OBJECT" in preset.upper()
            and "IMPULSE" in preset.upper()
            and "BODY" not in preset.upper()
            and "IMPACT" not in preset.upper()
            and "ACOUSTIC" not in preset.upper()
            and ("OBJECT_OBJECT" in preset.upper() or preset.upper().count("OBJECT") >= 2 or "PAIR" in preset.upper())
        )
    )
    object_object_contact = (not held_foreign_contact) and (not object_object_impulse) and (not object_object_impact_acoustics) and (
        preset == PUBLIC_PRESET_OBJECT_OBJECT_CONTACT
        or "OBJECT_OBJECT_CONTACT" in preset.upper()
        or (
            "OBJECT" in preset.upper()
            and "CONTACT" in preset.upper()
            and "BODY" not in preset.upper()
            and "IMPACT" not in preset.upper()
            and "ACOUSTIC" not in preset.upper()
            and "IMPULSE" not in preset.upper()
            and ("OBJECT_OBJECT" in preset.upper() or preset.upper().count("OBJECT") >= 2 or "PAIR" in preset.upper())
        )
    )
    object_impact_acoustics = (not held_foreign_contact) and (not object_object_contact) and (not object_object_impulse) and (not object_object_impact_acoustics) and (
        preset == PUBLIC_PRESET_OBJECT_IMPACT_ACOUSTICS
        or "OBJECT_IMPACT_ACOUSTICS" in preset.upper()
        or ("OBJECT" in preset.upper() and "IMPACT" in preset.upper() and "ACOUSTIC" in preset.upper())
    )
    body_object_impulse = (not held_foreign_contact) and (not object_impact_acoustics) and (not object_object_contact) and (not object_object_impulse) and (not object_object_impact_acoustics) and (
        preset == PUBLIC_PRESET_BODY_OBJECT_IMPULSE
        or "BODY_OBJECT_IMPULSE" in preset.upper()
        or ("BODY" in preset.upper() and "OBJECT" in preset.upper() and "IMPULSE" in preset.upper()
            and "IMPACT" not in preset.upper() and "ACOUSTIC" not in preset.upper())
    )
    body_object_contact = (not held_foreign_contact) and (not body_object_impulse) and (not object_impact_acoustics) and (not object_object_contact) and (not object_object_impulse) and (not object_object_impact_acoustics) and (
        preset == PUBLIC_PRESET_BODY_OBJECT_CONTACT
        or "BODY_OBJECT_CONTACT" in preset.upper()
        or ("BODY" in preset.upper() and "OBJECT" in preset.upper() and "CONTACT" in preset.upper()
            and "ACOUSTIC" not in preset.upper() and "IMPULSE" not in preset.upper())
    )
    free_object = (not held_foreign_contact) and (not body_object_contact) and (not body_object_impulse) and (
        preset == PUBLIC_PRESET_FREE_OBJECT_KINEMATICS or "FREE_OBJECT_KINEMATICS" in preset.upper()
    )
    # Contact-fact preset inherits free-object kinematics chain.
    free_object_chain = held_foreign_contact or object_object_impact_acoustics or object_object_impulse or object_object_contact or object_impact_acoustics or body_object_impulse or body_object_contact or free_object
    contact_acoustics = object_impact_acoustics or object_object_impact_acoustics or held_foreign_contact or ((not free_object_chain) and (
        preset == PUBLIC_PRESET_CONTACT_ACOUSTICS or "CONTACT_ACOUSTICS" in preset.upper()
    ))
    local_signal = contact_acoustics or object_impact_acoustics or object_object_impact_acoustics or held_foreign_contact or (
        (not free_object_chain) and (preset == PUBLIC_PRESET_LOCAL_SIGNAL or "LOCAL_SIGNAL" in preset.upper())
    )
    column_transfer = local_signal or free_object_chain or (
        preset == PUBLIC_PRESET_COLUMN_TRANSFER or "COLUMN_TRANSFER" in preset.upper()
    )
    procedural_columns = column_transfer or (
        preset == PUBLIC_PRESET_PROCEDURAL_COLUMNS or "PROCEDURAL_COLUMNS" in preset.upper()
    )
    multi_content = procedural_columns or (
        preset == PUBLIC_PRESET_MULTI_CONTENT or "MULTI_CONTENT" in preset.upper() or "MULTI-CONTENT" in preset.upper()
    )
    world_material = multi_content or (
        preset == PUBLIC_PRESET_WORLD_MATERIAL or "WORLD_MATERIAL" in preset.upper()
    )
    surface_optical = world_material or (
        preset == PUBLIC_PRESET_SURFACE_OPTICAL or "SURFACE_OPTICAL" in preset.upper()
    )
    traction_adaptation = surface_optical or (
        preset == PUBLIC_PRESET_TRACTION_ADAPTATION or "TRACTION_ADAPTATION" in preset.upper()
    )
    traction_experience = traction_adaptation or (
        preset == PUBLIC_PRESET_TRACTION_EXPERIENCE or "TRACTION_EXPERIENCE" in preset.upper()
    )
    surface_traction = traction_experience or (
        preset == PUBLIC_PRESET_SURFACE_TRACTION or "SURFACE_TRACTION" in preset.upper()
    )
    surface_deposition = surface_traction or (
        preset == PUBLIC_PRESET_SURFACE_DEPOSITION or "SURFACE_DEPOSITION" in preset.upper()
    )
    material_properties = surface_deposition or (
        preset == PUBLIC_PRESET_MATERIAL_PROPERTIES or "MATERIAL_PROPERTIES" in preset.upper()
    )
    composition_merge = material_properties or (
        preset == PUBLIC_PRESET_COMPOSITION_MERGE or "COMPOSITION_MERGE" in preset.upper()
    )
    bring = (not composition_merge) and (
        preset == PUBLIC_PRESET_BRING_TOGETHER
        or "BRING_TOGETHER" in preset.upper()
        or "BRING TOGETHER" in preset.upper()
    )
    bilateral = (not bring) and (
        preset == PUBLIC_PRESET_BILATERAL_GRASP
        or "BILATERAL" in preset.upper()
    )
    grasp = (not bilateral) and (not bring) and (
        preset == PUBLIC_PRESET_SINGLE_GRASP
        or "SINGLE_GRASP" in preset.upper()
        or ("GRASP" in preset.upper() and "ACANTHOSTEGA" in preset.upper() and "BILATERAL" not in preset.upper())
    )
    material_vision = (not grasp) and (not bilateral) and (not bring) and (
        preset == PUBLIC_PRESET_MATERIAL_VISION
        or "MATERIAL_VISION" in preset.upper()
    )
    materials = (not grasp) and (not bilateral) and (not bring) and (not material_vision) and (
        preset == PUBLIC_PRESET_MATERIALS or "MATERIALS" in preset.upper()
    )
    gentle = (
        (not grasp)
        and (not bilateral)
        and (not bring)
        and (not material_vision)
        and (not materials)
        and (preset == PUBLIC_PRESET_GENTLE or "PHASE_A" in preset.upper())
    )
    if beta4_public_model:
        phase = PHASE_LABEL_BETA4
        public = PUBLIC_PRESET_BETA4
        classification = "ACANTHOSTEGA_BETA4"
        stage = RUNTIME_STAGE_BETA4
        loco = "ACANTHOSTEGA_GENTLE"
    elif volumetric_world_vw7:
        phase = PHASE_LABEL_VOLUMETRIC_WORLD_VW7
        public = PUBLIC_PRESET_VOLUMETRIC_WORLD_VW7
        classification = "ACANTHOSTEGA_BETA4_VOLUMETRIC_WORLD_VW7"
        stage = RUNTIME_STAGE_VOLUMETRIC_WORLD_VW7
        loco = "ACANTHOSTEGA_GENTLE"
    elif release_and_excavation_support_loss_integration:
        phase = PHASE_LABEL_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        public = PUBLIC_PRESET_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        classification = "ACANTHOSTEGA_BETA4_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION"
        stage = RUNTIME_STAGE_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
        loco = "ACANTHOSTEGA_GENTLE"
    elif vertical_impact_acoustic_emission:
        phase = PHASE_LABEL_VERTICAL_IMPACT_ACOUSTIC_EMISSION
        public = PUBLIC_PRESET_VERTICAL_IMPACT_ACOUSTIC_EMISSION
        classification = "ACANTHOSTEGA_BETA4_VERTICAL_IMPACT_ACOUSTIC_EMISSION"
        stage = RUNTIME_STAGE_VERTICAL_IMPACT_ACOUSTIC_EMISSION
        loco = "ACANTHOSTEGA_GENTLE"
    elif vertical_terrain_landing_contact_response:
        phase = PHASE_LABEL_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
        public = PUBLIC_PRESET_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
        classification = "ACANTHOSTEGA_BETA4_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE"
        stage = RUNTIME_STAGE_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
        loco = "ACANTHOSTEGA_GENTLE"
    elif free_space_state_and_pe_authority_contract:
        phase = PHASE_LABEL_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
        public = PUBLIC_PRESET_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
        classification = "ACANTHOSTEGA_BETA4_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT"
        stage = RUNTIME_STAGE_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
        loco = "ACANTHOSTEGA_GENTLE"
    elif held_deposition_radius_shrink_transaction:
        phase = PHASE_LABEL_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
        public = PUBLIC_PRESET_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
        classification = "ACANTHOSTEGA_BETA4_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION"
        stage = RUNTIME_STAGE_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
        loco = "ACANTHOSTEGA_GENTLE"
    elif held_combine_radius_resize_transaction:
        phase = PHASE_LABEL_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
        public = PUBLIC_PRESET_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
        classification = "ACANTHOSTEGA_BETA4_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION"
        stage = RUNTIME_STAGE_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
        loco = "ACANTHOSTEGA_GENTLE"
    elif detached_material_amount_scaled_collision_radius:
        phase = PHASE_LABEL_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
        public = PUBLIC_PRESET_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
        classification = "ACANTHOSTEGA_BETA4_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS"
        stage = RUNTIME_STAGE_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
        loco = "ACANTHOSTEGA_GENTLE"
    elif event_driven_crowded_placement_retry_contract:
        phase = PHASE_LABEL_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
        public = PUBLIC_PRESET_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
        classification = "ACANTHOSTEGA_BETA4_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT"
        stage = RUNTIME_STAGE_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
        loco = "ACANTHOSTEGA_GENTLE"
    elif active_locomotion_traction_vs_sliding_friction:
        phase = PHASE_LABEL_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
        public = PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
        classification = "ACANTHOSTEGA_BETA4_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION"
        stage = RUNTIME_STAGE_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
        loco = "ACANTHOSTEGA_GENTLE"
    elif repeated_conservative_surface_column_separation:
        phase = PHASE_LABEL_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
        public = PUBLIC_PRESET_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
        classification = "ACANTHOSTEGA_BETA4_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION"
        stage = RUNTIME_STAGE_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
        loco = "ACANTHOSTEGA_GENTLE"
    elif bnlt_move_breakaway_locomotion_repair:
        phase = PHASE_LABEL_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
        public = PUBLIC_PRESET_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
        classification = "ACANTHOSTEGA_BETA4_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR"
        stage = RUNTIME_STAGE_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
        loco = "ACANTHOSTEGA_GENTLE"
    elif detached_terrain_material_initial_placement:
        phase = PHASE_LABEL_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
        public = PUBLIC_PRESET_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
        classification = "ACANTHOSTEGA_BETA4_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT"
        stage = RUNTIME_STAGE_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
        loco = "ACANTHOSTEGA_GENTLE"
    elif held_mediated_surface_exertion_integration:
        phase = PHASE_LABEL_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION
        public = PUBLIC_PRESET_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION
        classification = "ACANTHOSTEGA_BETA4_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION"
        stage = RUNTIME_STAGE_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION
        loco = "ACANTHOSTEGA_GENTLE"
    elif held_resource_object_terrain_mechanical_transmission:
        phase = PHASE_LABEL_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION
        public = PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION
        classification = "ACANTHOSTEGA_BETA4_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION"
        stage = RUNTIME_STAGE_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION
        loco = "ACANTHOSTEGA_GENTLE"
    elif held_resource_object_terrain_contact_geometry:
        phase = PHASE_LABEL_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY
        public = PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY
        classification = "ACANTHOSTEGA_BETA4_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY"
        stage = RUNTIME_STAGE_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY
        loco = "ACANTHOSTEGA_GENTLE"
    elif surface_exertion_terrain_material_resistance:
        phase = PHASE_LABEL_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE
        public = PUBLIC_PRESET_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE
        classification = "ACANTHOSTEGA_BETA4_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE"
        stage = RUNTIME_STAGE_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE
        loco = "ACANTHOSTEGA_GENTLE"
    elif effector_bounded_actuator_effort:
        phase = PHASE_LABEL_EFFECTOR_BOUNDED_ACTUATOR_EFFORT
        public = PUBLIC_PRESET_EFFECTOR_BOUNDED_ACTUATOR_EFFORT
        classification = "ACANTHOSTEGA_BETA4_EFFECTOR_BOUNDED_ACTUATOR_EFFORT"
        stage = RUNTIME_STAGE_EFFECTOR_BOUNDED_ACTUATOR_EFFORT
        loco = "ACANTHOSTEGA_GENTLE"
    elif manipulator_relative_world_actuation:
        phase = PHASE_LABEL_MANIPULATOR_RELATIVE_WORLD_ACTUATION
        public = PUBLIC_PRESET_MANIPULATOR_RELATIVE_WORLD_ACTUATION
        classification = "ACANTHOSTEGA_BETA4_MANIPULATOR_RELATIVE_WORLD_ACTUATION"
        stage = RUNTIME_STAGE_MANIPULATOR_RELATIVE_WORLD_ACTUATION
        loco = "ACANTHOSTEGA_GENTLE"
    elif effector_terrain_contact_geometry:
        phase = PHASE_LABEL_EFFECTOR_TERRAIN_CONTACT_GEOMETRY
        public = PUBLIC_PRESET_EFFECTOR_TERRAIN_CONTACT_GEOMETRY
        classification = "ACANTHOSTEGA_BETA4_EFFECTOR_TERRAIN_CONTACT_GEOMETRY"
        stage = RUNTIME_STAGE_EFFECTOR_TERRAIN_CONTACT_GEOMETRY
        loco = "ACANTHOSTEGA_GENTLE"
    elif surface_material_separation:
        phase = PHASE_LABEL_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION
        public = PUBLIC_PRESET_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION
        classification = "ACANTHOSTEGA_BETA4_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION"
        stage = RUNTIME_STAGE_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION
        loco = "ACANTHOSTEGA_GENTLE"
    elif coherent_slope_dynamics:
        phase = PHASE_LABEL_COHERENT_SLOPE_DYNAMICS
        public = PUBLIC_PRESET_COHERENT_SLOPE_DYNAMICS
        classification = "ACANTHOSTEGA_PHASE_C_COHERENT_SLOPE_DYNAMICS"
        stage = RUNTIME_STAGE_COHERENT_SLOPE_DYNAMICS
        loco = "ACANTHOSTEGA_GENTLE"
    elif tangent_gravity_diagnostic_shadow:
        phase = PHASE_LABEL_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW
        public = PUBLIC_PRESET_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW
        classification = "ACANTHOSTEGA_PHASE_C_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW"
        stage = RUNTIME_STAGE_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW
        loco = "ACANTHOSTEGA_GENTLE"
    elif continuous_pe_policy_c:
        phase = PHASE_LABEL_CONTINUOUS_PE_POLICY_C
        public = PUBLIC_PRESET_CONTINUOUS_PE_POLICY_C
        classification = "ACANTHOSTEGA_PHASE_C_CONTINUOUS_PE_POLICY_C"
        stage = RUNTIME_STAGE_CONTINUOUS_PE_POLICY_C
        loco = "ACANTHOSTEGA_GENTLE"
    elif continuous_gravitational_pe_diagnostic_shadow:
        phase = PHASE_LABEL_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW
        public = PUBLIC_PRESET_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW
        classification = "ACANTHOSTEGA_PHASE_C_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW"
        stage = RUNTIME_STAGE_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW
        loco = "ACANTHOSTEGA_GENTLE"
    elif diagnostic_normal_load_shadow:
        phase = PHASE_LABEL_DIAGNOSTIC_NORMAL_LOAD_SHADOW
        public = PUBLIC_PRESET_DIAGNOSTIC_NORMAL_LOAD_SHADOW
        classification = "ACANTHOSTEGA_PHASE_C_DIAGNOSTIC_NORMAL_LOAD_SHADOW"
        stage = RUNTIME_STAGE_DIAGNOSTIC_NORMAL_LOAD_SHADOW
        loco = "ACANTHOSTEGA_GENTLE"
    elif radius_aware_face_sweep:
        phase = PHASE_LABEL_RADIUS_AWARE_FACE_SWEEP
        public = PUBLIC_PRESET_RADIUS_AWARE_FACE_SWEEP
        classification = "ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_FACE_SWEEP"
        stage = RUNTIME_STAGE_RADIUS_AWARE_FACE_SWEEP
        loco = "ACANTHOSTEGA_GENTLE"
    elif ses_runtime_classifier:
        phase = PHASE_LABEL_SES_RUNTIME_CLASSIFIER
        public = PUBLIC_PRESET_SES_RUNTIME_CLASSIFIER
        classification = "ACANTHOSTEGA_PHASE_C_SES_RUNTIME_CLASSIFIER"
        stage = RUNTIME_STAGE_SES_RUNTIME_CLASSIFIER
        loco = "ACANTHOSTEGA_GENTLE"
    elif ses_decomposition_contract:
        phase = PHASE_LABEL_SES_DECOMPOSITION_CONTRACT
        public = PUBLIC_PRESET_SES_DECOMPOSITION_CONTRACT
        classification = "ACANTHOSTEGA_PHASE_C_SES_DECOMPOSITION_CONTRACT"
        stage = RUNTIME_STAGE_SES_DECOMPOSITION_CONTRACT
        loco = "ACANTHOSTEGA_GENTLE"
    elif radius_aware_support:
        phase = PHASE_LABEL_RADIUS_AWARE_SUPPORT
        public = PUBLIC_PRESET_RADIUS_AWARE_SUPPORT
        classification = "ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_SUPPORT"
        stage = RUNTIME_STAGE_RADIUS_AWARE_SUPPORT
        loco = "ACANTHOSTEGA_GENTLE"
    elif free_object_static_traction:
        phase = PHASE_LABEL_FREE_OBJECT_STATIC_TRACTION
        public = PUBLIC_PRESET_FREE_OBJECT_STATIC_TRACTION
        classification = "ACANTHOSTEGA_PHASE_C_FREE_OBJECT_STATIC_TRACTION"
        stage = RUNTIME_STAGE_FREE_OBJECT_STATIC_TRACTION
        loco = "ACANTHOSTEGA_GENTLE"
    elif static_traction:
        phase = PHASE_LABEL_STATIC_TRACTION
        public = PUBLIC_PRESET_STATIC_TRACTION
        classification = "ACANTHOSTEGA_PHASE_C_STATIC_TRACTION"
        stage = RUNTIME_STAGE_STATIC_TRACTION
        loco = "ACANTHOSTEGA_GENTLE"
    elif continuous_surface_geometry:
        phase = PHASE_LABEL_CONTINUOUS_SURFACE_GEOMETRY
        public = PUBLIC_PRESET_CONTINUOUS_SURFACE_GEOMETRY
        classification = "ACANTHOSTEGA_PHASE_C_CONTINUOUS_SURFACE_GEOMETRY"
        stage = RUNTIME_STAGE_CONTINUOUS_SURFACE_GEOMETRY
        loco = "ACANTHOSTEGA_GENTLE"
    elif body_normal_load_traction:
        phase = PHASE_LABEL_BODY_NORMAL_LOAD_TRACTION
        public = PUBLIC_PRESET_BODY_NORMAL_LOAD_TRACTION
        classification = "ACANTHOSTEGA_PHASE_C_BODY_NORMAL_LOAD_TRACTION"
        stage = RUNTIME_STAGE_BODY_NORMAL_LOAD_TRACTION
        loco = "ACANTHOSTEGA_GENTLE"
    elif surface_elevation_support:
        phase = PHASE_LABEL_SURFACE_ELEVATION_SUPPORT
        public = PUBLIC_PRESET_SURFACE_ELEVATION_SUPPORT
        classification = "ACANTHOSTEGA_PHASE_C_SURFACE_ELEVATION_SUPPORT"
        stage = RUNTIME_STAGE_SURFACE_ELEVATION_SUPPORT
        loco = "ACANTHOSTEGA_GENTLE"
    elif free_object_ground_friction:
        phase = PHASE_LABEL_FREE_OBJECT_GROUND_FRICTION
        public = PUBLIC_PRESET_FREE_OBJECT_GROUND_FRICTION
        classification = "ACANTHOSTEGA_PHASE_C_FREE_OBJECT_GROUND_FRICTION"
        stage = RUNTIME_STAGE_FREE_OBJECT_GROUND_FRICTION
        loco = "ACANTHOSTEGA_GENTLE"
    elif flat_ground_gravity:
        phase = PHASE_LABEL_FLAT_GROUND_GRAVITY
        public = PUBLIC_PRESET_FLAT_GROUND_GRAVITY
        classification = "ACANTHOSTEGA_PHASE_C_FLAT_GROUND_GRAVITY"
        stage = RUNTIME_STAGE_FLAT_GROUND_GRAVITY
        loco = "ACANTHOSTEGA_GENTLE"
    elif effector_work_accounting:
        phase = PHASE_LABEL_EFFECTOR_WORK_ACCOUNTING
        public = PUBLIC_PRESET_EFFECTOR_WORK_ACCOUNTING
        classification = "ACANTHOSTEGA_PHASE_B_EFFECTOR_WORK_ACCOUNTING"
        stage = RUNTIME_STAGE_EFFECTOR_WORK_ACCOUNTING
        loco = "ACANTHOSTEGA_GENTLE"
    elif held_translational_impulse:
        phase = PHASE_LABEL_HELD_OBJECT_TRANSLATIONAL_IMPULSE
        public = PUBLIC_PRESET_HELD_OBJECT_TRANSLATIONAL_IMPULSE
        classification = "ACANTHOSTEGA_PHASE_B_HELD_OBJECT_TRANSLATIONAL_IMPULSE"
        stage = RUNTIME_STAGE_HELD_OBJECT_TRANSLATIONAL_IMPULSE
        loco = "ACANTHOSTEGA_GENTLE"
    elif held_foreign_contact:
        phase = PHASE_LABEL_HELD_OBJECT_FOREIGN_BODY_CONTACT
        public = PUBLIC_PRESET_HELD_OBJECT_FOREIGN_BODY_CONTACT
        classification = "ACANTHOSTEGA_PHASE_B_HELD_OBJECT_FOREIGN_BODY_CONTACT"
        stage = RUNTIME_STAGE_HELD_OBJECT_FOREIGN_BODY_CONTACT
        loco = "ACANTHOSTEGA_GENTLE"
    elif object_object_impact_acoustics:
        phase = PHASE_LABEL_OBJECT_OBJECT_IMPACT_ACOUSTICS
        public = PUBLIC_PRESET_OBJECT_OBJECT_IMPACT_ACOUSTICS
        classification = "ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_IMPACT_ACOUSTICS"
        stage = RUNTIME_STAGE_OBJECT_OBJECT_IMPACT_ACOUSTICS
        loco = "ACANTHOSTEGA_GENTLE"
    elif object_object_impulse:
        phase = PHASE_LABEL_OBJECT_OBJECT_IMPULSE
        public = PUBLIC_PRESET_OBJECT_OBJECT_IMPULSE
        classification = "ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_IMPULSE"
        stage = RUNTIME_STAGE_OBJECT_OBJECT_IMPULSE
        loco = "ACANTHOSTEGA_GENTLE"
    elif object_object_contact:
        phase = PHASE_LABEL_OBJECT_OBJECT_CONTACT
        public = PUBLIC_PRESET_OBJECT_OBJECT_CONTACT
        classification = "ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_CONTACT"
        stage = RUNTIME_STAGE_OBJECT_OBJECT_CONTACT
        loco = "ACANTHOSTEGA_GENTLE"
    elif object_impact_acoustics:
        phase = PHASE_LABEL_OBJECT_IMPACT_ACOUSTICS
        public = PUBLIC_PRESET_OBJECT_IMPACT_ACOUSTICS
        classification = "ACANTHOSTEGA_PHASE_B_OBJECT_IMPACT_ACOUSTICS"
        stage = RUNTIME_STAGE_OBJECT_IMPACT_ACOUSTICS
        loco = "ACANTHOSTEGA_GENTLE"
    elif body_object_impulse:
        phase = PHASE_LABEL_BODY_OBJECT_IMPULSE
        public = PUBLIC_PRESET_BODY_OBJECT_IMPULSE
        classification = "ACANTHOSTEGA_PHASE_B_BODY_OBJECT_IMPULSE"
        stage = RUNTIME_STAGE_BODY_OBJECT_IMPULSE
        loco = "ACANTHOSTEGA_GENTLE"
    elif body_object_contact:
        phase = PHASE_LABEL_BODY_OBJECT_CONTACT
        public = PUBLIC_PRESET_BODY_OBJECT_CONTACT
        classification = "ACANTHOSTEGA_PHASE_B_BODY_OBJECT_CONTACT"
        stage = RUNTIME_STAGE_BODY_OBJECT_CONTACT
        loco = "ACANTHOSTEGA_GENTLE"
    elif free_object:
        phase = PHASE_LABEL_FREE_OBJECT_KINEMATICS
        public = PUBLIC_PRESET_FREE_OBJECT_KINEMATICS
        classification = "ACANTHOSTEGA_PHASE_B_FREE_OBJECT_KINEMATICS"
        stage = RUNTIME_STAGE_FREE_OBJECT_KINEMATICS
        loco = "ACANTHOSTEGA_GENTLE"
    elif contact_acoustics:
        phase = PHASE_LABEL_CONTACT_ACOUSTICS
        public = PUBLIC_PRESET_CONTACT_ACOUSTICS
        classification = "ACANTHOSTEGA_PHASE_B_CONTACT_ACOUSTICS"
        stage = RUNTIME_STAGE_CONTACT_ACOUSTICS
        loco = "ACANTHOSTEGA_GENTLE"
    elif local_signal:
        phase = PHASE_LABEL_LOCAL_SIGNAL
        public = PUBLIC_PRESET_LOCAL_SIGNAL
        classification = "ACANTHOSTEGA_PHASE_B_LOCAL_SIGNAL"
        stage = RUNTIME_STAGE_LOCAL_SIGNAL
        loco = "ACANTHOSTEGA_GENTLE"
    elif column_transfer:
        phase = PHASE_LABEL_COLUMN_TRANSFER
        public = PUBLIC_PRESET_COLUMN_TRANSFER
        classification = "ACANTHOSTEGA_PHASE_B_COLUMN_TRANSFER"
        stage = RUNTIME_STAGE_COLUMN_TRANSFER
        loco = "ACANTHOSTEGA_GENTLE"
    elif procedural_columns:
        phase = PHASE_LABEL_PROCEDURAL_COLUMNS
        public = PUBLIC_PRESET_PROCEDURAL_COLUMNS
        classification = "ACANTHOSTEGA_PHASE_B_PROCEDURAL_COLUMNS"
        stage = RUNTIME_STAGE_PROCEDURAL_COLUMNS
        loco = "ACANTHOSTEGA_GENTLE"
    elif multi_content:
        phase = PHASE_LABEL_MULTI_CONTENT
        public = PUBLIC_PRESET_MULTI_CONTENT
        classification = "ACANTHOSTEGA_PHASE_B_MULTI_CONTENT_INDEX"
        stage = RUNTIME_STAGE_MULTI_CONTENT
        loco = "ACANTHOSTEGA_GENTLE"
    elif world_material:
        phase = PHASE_LABEL_WORLD_MATERIAL
        public = PUBLIC_PRESET_WORLD_MATERIAL
        classification = "ACANTHOSTEGA_PHASE_B_WORLD_MATERIAL_TRANSACTIONS"
        stage = RUNTIME_STAGE_WORLD_MATERIAL
        loco = "ACANTHOSTEGA_GENTLE"
    elif surface_optical:
        phase = PHASE_LABEL_SURFACE_OPTICAL
        public = PUBLIC_PRESET_SURFACE_OPTICAL
        classification = "ACANTHOSTEGA_PHASE_A_SURFACE_OPTICAL"
        stage = RUNTIME_STAGE_SURFACE_OPTICAL
        loco = "ACANTHOSTEGA_GENTLE"
    elif traction_adaptation:
        phase = PHASE_LABEL_TRACTION_ADAPTATION
        public = PUBLIC_PRESET_TRACTION_ADAPTATION
        classification = "ACANTHOSTEGA_PHASE_A_TRACTION_ADAPTATION"
        stage = RUNTIME_STAGE_TRACTION_ADAPTATION
        loco = "ACANTHOSTEGA_GENTLE"
    elif traction_experience:
        phase = PHASE_LABEL_TRACTION_EXPERIENCE
        public = PUBLIC_PRESET_TRACTION_EXPERIENCE
        classification = "ACANTHOSTEGA_PHASE_A_TRACTION_EXPERIENCE"
        stage = RUNTIME_STAGE_TRACTION_EXPERIENCE
        loco = "ACANTHOSTEGA_GENTLE"
    elif surface_traction:
        phase = PHASE_LABEL_SURFACE_TRACTION
        public = PUBLIC_PRESET_SURFACE_TRACTION
        classification = "ACANTHOSTEGA_PHASE_A_SURFACE_TRACTION"
        stage = RUNTIME_STAGE_SURFACE_TRACTION
        loco = "ACANTHOSTEGA_GENTLE"
    elif surface_deposition:
        phase = PHASE_LABEL_SURFACE_DEPOSITION
        public = PUBLIC_PRESET_SURFACE_DEPOSITION
        classification = "ACANTHOSTEGA_PHASE_A_SURFACE_DEPOSITION"
        stage = RUNTIME_STAGE_SURFACE_DEPOSITION
        loco = "ACANTHOSTEGA_GENTLE"
    elif material_properties:
        phase = PHASE_LABEL_MATERIAL_PROPERTIES
        public = PUBLIC_PRESET_MATERIAL_PROPERTIES
        classification = "ACANTHOSTEGA_PHASE_A_MATERIAL_PROPERTIES"
        stage = RUNTIME_STAGE_MATERIAL_PROPERTIES
        loco = "ACANTHOSTEGA_GENTLE"
    elif composition_merge:
        phase = PHASE_LABEL_COMPOSITION_MERGE
        public = PUBLIC_PRESET_COMPOSITION_MERGE
        classification = "ACANTHOSTEGA_PHASE_A_COMPOSITION_MERGE"
        stage = RUNTIME_STAGE_COMPOSITION_MERGE
        loco = "ACANTHOSTEGA_GENTLE"
    elif bring:
        phase = PHASE_LABEL_BRING_TOGETHER
        public = PUBLIC_PRESET_BRING_TOGETHER
        classification = "ACANTHOSTEGA_PHASE_A_BRING_TOGETHER"
        stage = RUNTIME_STAGE_BRING_TOGETHER
        loco = "ACANTHOSTEGA_GENTLE"
    elif bilateral:
        phase = PHASE_LABEL_BILATERAL_GRASP
        public = PUBLIC_PRESET_BILATERAL_GRASP
        classification = "ACANTHOSTEGA_PHASE_A_BILATERAL_GRASP"
        stage = RUNTIME_STAGE_BILATERAL_GRASP
        loco = "ACANTHOSTEGA_GENTLE"
    elif grasp:
        phase = PHASE_LABEL_SINGLE_GRASP
        public = PUBLIC_PRESET_SINGLE_GRASP
        classification = "ACANTHOSTEGA_PHASE_A_SINGLE_GRASP"
        stage = RUNTIME_STAGE_SINGLE_GRASP
        loco = "ACANTHOSTEGA_GENTLE"
    elif material_vision:
        phase = PHASE_LABEL_MATERIAL_VISION
        public = PUBLIC_PRESET_MATERIAL_VISION
        classification = "ACANTHOSTEGA_PHASE_A_MATERIAL_VISION"
        stage = RUNTIME_STAGE_MATERIAL_VISION
        loco = "ACANTHOSTEGA_GENTLE"
    elif materials:
        phase = PHASE_LABEL_MATERIALS
        public = PUBLIC_PRESET_MATERIALS
        classification = "ACANTHOSTEGA_PHASE_A_MATERIALS"
        stage = RUNTIME_STAGE_MATERIALS
        loco = "ACANTHOSTEGA_GENTLE"
    elif gentle:
        phase = PHASE_LABEL_A
        public = PUBLIC_PRESET_GENTLE
        classification = "ACANTHOSTEGA_PHASE_A_GENTLE"
        stage = RUNTIME_STAGE_A
        loco = "ACANTHOSTEGA_GENTLE"
    else:
        phase = PHASE_LABEL
        public = PUBLIC_PRESET
        classification = "ACANTHOSTEGA_PHASE0"
        stage = RUNTIME_STAGE
        loco = "TIKTAALIK"
    return {
        "model_family": MODEL_FAMILY,
        "model_version": MODEL_VERSION,
        "model_line": MODEL_LINE,
        "model_codename": MODEL_CODENAME,
        "working_title": WORKING_TITLE,
        "phase_label": phase,
        "display_name": f"MM {MODEL_VERSION} — {phase}",
        "runtime_version": RUNTIME_VERSION,
        "public_preset": public,
        "schema_version": SNAPSHOT_SCHEMA,
        "manifest_schema": MANIFEST_SCHEMA_VERSION,
        "observer_api_version": OBSERVER_API_VERSION,
        "canonical": False,
        "classification": classification,
        "runtime_stage": stage,
        "lifecycle_implemented": False,
        "agent_resource_perception_implemented": False,
        "grasp_release_implemented": bool(grasp or bilateral or bring or composition_merge),
        "material_conversion_implemented": bool(composition_merge),
        "physical_resource_objects": bool(materials or material_vision or grasp or bilateral or bring or composition_merge),
        "physical_resource_object_vision": bool(material_vision or grasp or bilateral or bring or composition_merge),
        "single_physical_manipulator": bool(grasp),
        "bilateral_physical_manipulators": bool(bilateral or bring or composition_merge),
        "bilateral_bring_together": bool(bring or composition_merge),
        "material_composition_merge": bool(composition_merge),
        "passive_material_properties": bool(material_properties),
        "explicit_surface_deposition": bool(surface_deposition),
        "surface_affinity_traction": bool(surface_traction),
        "surface_traction_experience_bridge": bool(traction_experience),
        "surface_traction_prediction_adaptation": bool(traction_adaptation),
        "physical_surface_optical_coating": bool(surface_optical),
        "world_material_transactions": bool(world_material),
        "multi_content_spatial_index": bool(multi_content),
        "procedural_surface_columns": bool(procedural_columns),
        # Present only for the column-transfer preset so earlier presets' metadata is unchanged.
        **({"conservative_surface_column_transfer": True} if column_transfer else {}),
        # Present only for the local-signal preset.
        **({"local_physical_signal_transport": True} if local_signal else {}),
        # Present only for the contact-acoustics preset.
        **({"physical_contact_acoustic_emission": True} if contact_acoustics else {}),
        # Present only for the free-object-kinematics preset.
        **({"free_resource_object_kinematics": True} if free_object else {}),
        **({"flat_ground_gravity": True} if (flat_ground_gravity or free_object_ground_friction or surface_elevation_support or body_normal_load_traction or continuous_surface_geometry or static_traction or free_object_static_traction or radius_aware_support or ses_decomposition_contract or ses_runtime_classifier or radius_aware_face_sweep or diagnostic_normal_load_shadow or continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"free_resource_object_ground_friction": True} if (free_object_ground_friction or surface_elevation_support or body_normal_load_traction or continuous_surface_geometry or static_traction or free_object_static_traction or radius_aware_support or ses_decomposition_contract or ses_runtime_classifier or radius_aware_face_sweep or diagnostic_normal_load_shadow or continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"surface_elevation_support": True} if (surface_elevation_support or body_normal_load_traction or continuous_surface_geometry or static_traction or free_object_static_traction or radius_aware_support or ses_decomposition_contract or ses_runtime_classifier or radius_aware_face_sweep or diagnostic_normal_load_shadow or continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"body_normal_load_traction": True} if (body_normal_load_traction or continuous_surface_geometry or static_traction or free_object_static_traction or radius_aware_support or ses_decomposition_contract or ses_runtime_classifier or radius_aware_face_sweep or diagnostic_normal_load_shadow or continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"continuous_surface_geometry": True} if (continuous_surface_geometry or static_traction or free_object_static_traction or radius_aware_support or ses_decomposition_contract or ses_runtime_classifier or radius_aware_face_sweep or diagnostic_normal_load_shadow or continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"body_static_traction_threshold": True} if (static_traction or free_object_static_traction or radius_aware_support or ses_decomposition_contract or ses_runtime_classifier or radius_aware_face_sweep or diagnostic_normal_load_shadow or continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"free_resource_object_static_traction_threshold": True} if (free_object_static_traction or radius_aware_support or ses_decomposition_contract or ses_runtime_classifier or radius_aware_face_sweep or diagnostic_normal_load_shadow or continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"radius_aware_support_points": True} if (radius_aware_support or ses_decomposition_contract or ses_runtime_classifier or radius_aware_face_sweep or diagnostic_normal_load_shadow or continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"ses_decomposition_contract": True} if (ses_decomposition_contract or ses_runtime_classifier or radius_aware_face_sweep or diagnostic_normal_load_shadow or continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"ses_runtime_transition_classifier": True} if (ses_runtime_classifier or radius_aware_face_sweep or diagnostic_normal_load_shadow or continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"radius_aware_face_sweep": True} if (radius_aware_face_sweep or diagnostic_normal_load_shadow or continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"diagnostic_normal_load_shadow": True} if (diagnostic_normal_load_shadow or continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"continuous_gravitational_pe_diagnostic_shadow": True} if (continuous_gravitational_pe_diagnostic_shadow or continuous_pe_policy_c) else {}),
        **({"continuous_gravitational_pe": True} if continuous_pe_policy_c else {}),
        "experimental_overrides": {},
        "locomotion_profile": loco,
        "seed": seed,
        "tick": tick,
        **({"bnlt_move_breakaway_locomotion_repair": True} if bnlt_move_breakaway_locomotion_repair else {}),
        **({"repeated_conservative_surface_column_separation": True} if repeated_conservative_surface_column_separation else {}),
    }
