"""Agent-accessible observation for Current MM (PhysicalSystemRuntime).

WORLD TRUTH (full maps, PlanetDisplayState, observer diagnostics) must never
enter cognition. Fragments here are derived only from body-local physical
signals and embodied internal scalars owned by the same agent instance.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.planet.config import PlanetConfig
from mechanistic_mind.planet.state import PlanetState
from mechanistic_mind.internal_medium.state import InternalMediumState
from mechanistic_mind.physical_body.config import PhysicalBodyConfig

# Keys / tokens forbidden in agent-facing cognition payloads.
FORBIDDEN_TOKENS = (
    "PlanetDisplayState",
    "ground_truth",
    "world_truth",
    "hidden_role",
    "observer_only",
    "display_from_planet",
    "full_map",
    "external_material_boundary",
    "season_phase",
    "latitude_coordinate",
    "environmental_cycle_phase",
    "climate_phase",
    "resource_cycle_phase",
    "terrain_potential",
    "terrain_drag",
    "terrain_grad",
    "terrain_seed",
    "resource_geo_suit",
    "resource_suitability",
    "ambient_fx",
    "ambient_fy",
    "ambient_force",
    "ambient_seed",
    "temporal_panel",
    "phase_velocity_per_tick",
    "body_climate_timescale_ratio",
    "OBSTACLE",
    "MOUNTAIN",
    "TRAP",
    # PHYSICAL_PERCEPTION_01 — WORLD GT / pipeline intermediates never cognition-visible by name
    "illumination_phase",
    "surface_response",
    "surface_optical",
    "surface_seed",
    "surface_checksum",
    "surface_meta",
    "world_x",
    "world_y",
    "absolute_direction",
    "terrain_traversability",
    "DAY",
    "NIGHT",
    "TIME_OF_DAY",
    # Visible physical bodies — identity / role never cognition-visible
    "OTHER_AGENT",
    "EXPERIMENTER",
    "experimenter",
    "agent_id",
    "entity_id",
    "entity_type",
    "optical_source_type",
    "visible_body",
    "body_is_agent",
    "TEACHER",
    "DEMONSTRATOR",
    "SOCIAL_SIGNAL",
    "SOURCE_ID",
    "resource_objects",
    "RESOURCE_OBJECT",
    "physical_resource_objects",
    "FREE_STATIC",
    "physical_resource_object_vision",
    "RESOURCE_OBJECT_SURFACE",
    "source_object_id",
    "resource-000001",
    "component_0",
    "component_a",
    "component_b",
    "compliance",
    "surface_affinity",
    "passive_material_properties",
    "effective_properties",
    "COMPOSITION_WEIGHTED_MEAN_V1",
    "physical_optical_material_profile",
    "PHYSICAL_OPTICAL_MATERIAL_PROFILE_V1",
    "ANONYMOUS_SPECTRAL_REFLECTANCE_MATERIAL_PROFILE_O1_V1",
    "PHYSICAL_MATERIAL_PROPERTY_NON_SI_NO_LIGHT_TRANSPORT",
    "spectral_reflectance",
    "optical_band_0",
    "optical_band_1",
    "optical_band_2",
    "optical_band_3",
    "optical_band_4",
    "optical_band_5",
    "optical_band_identifiers",
    "PROFILE_RESOLVED",
    "UNKNOWN_PROFILE",
    "INVALID_MATERIAL_COMPOSITION",
    "LEGACY_FIXED_COMPATIBILITY",
    "QUANTITY_WEIGHTED_MEAN_REFLECTANCE_V1",
    "registry_digest",
    "component_references",
    "exposed_surface_optical_interaction_authority",
    "EXPOSED_SURFACE_OPTICAL_INTERACTION_AUTHORITY_V1",
    "VW1_OCCUPIED_FREE_BOUNDARY_FACETS_O2_V1",
    "AUTHORITATIVE_DERIVATION_FROM_VW1_OCCUPANCY_READ_ONLY",
    "facet_id",
    "facet_checksum",
    "outward_unit_normal",
    "face_class",
    "abstract_spectral_light_source_and_direct_transport",
    "ABSTRACT_SPECTRAL_LIGHT_SOURCE_AND_DIRECT_TRANSPORT_V1",
    "DIRECT_OCCUPANCY_OCCLUDED_ANONYMOUS_SPECTRAL_LIGHT_O3_V1",
    "PHYSICAL_ABSTRACT_NON_SI_DIRECT_LIGHT_FIELD",
    "incident_spectrum",
    "reflected_spectral_exitance_proxy",
    "abstract_directional_source_0",
    "DIRECT_ILLUMINATED",
    "OCCLUDED_ZERO",
    "BACK_FACING_ZERO",
    "SOURCE_DISABLED_ZERO",
    "UNKNOWN_MATERIAL_RESPONSE",
    "NOT_EVALUATED",
    "object_body_held_optical_surfaces",
    "OBJECT_BODY_HELD_OPTICAL_SURFACES_V1",
    "ANALYTIC_PHYSICAL_SURFACE_SAMPLES_FOR_DIRECT_LIGHT_O3A_V1",
    "DERIVED_FROM_AUTHORITATIVE_BODY_AND_RESOURCE_OBJECT_GEOMETRY",
    "area_weight",
    "pose_digest",
    "SPHERE_AXIS6_V1",
    "CAPSULE_TOP_BOTTOM_EQ8_V1",
    "organism_physical_optical_reception",
    "ORGANISM_PHYSICAL_OPTICAL_RECEPTION_V1",
    "O3_SURFACE_TO_VW6_RECEPTOR_DIRECT_RECEPTION_O4_V1",
    "PHYSICAL_ABSTRACT_OPTICAL_FIELD_TO_ORGANISM_RECEPTOR",
    "o4_trace",
    "k_visual",
    "contrib_bands",
    "organism_receptor_grounded_3d_fpv",
    "ORGANISM_RECEPTOR_GROUNDED_3D_FPV_V1",
    "EXACT_O4_RECEPTOR_CONTRIBUTION_FIRST_PERSON_RECONSTRUCTION_V1",
    "RESEARCHER_DISPLAY_OVER_AUTHORITATIVE_O4_RECEPTION",
    "contribution_id",
    "accepted_raw_six_band",
    "display_rgb_nonphysical",
    "reflected_spectral_exitance_proxy",
    "sensory_modality_temporal_alignment",
    "SENSORY_MODALITY_TEMPORAL_ALIGNMENT_CONTRACT_V1",
    "PHYSICAL_EVENT_RECEPTOR_OBSERVATION_TICK_ENVELOPE_O5_V1",
    "RESEARCHER_AND_CAUSAL_METADATA_OVER_EXISTING_MODALITY_TIMING",
    "alignment_envelope",
    "source_event_refs",
    "source_to_receptor_propagation_delay_ticks",
    "receptor_to_observation_delay_ticks",
    "ALIGNED_OBSERVATION_DIFFERENT_PHYSICAL_EVENT_TIMES",
    "EXPLICITLY_ALIGNED_AT_OBSERVATION",
    "researcher_presentation_tick",
    "researcher_physical_optical_audit_view",
    "RESEARCHER_PHYSICAL_OPTICAL_AUDIT_VIEW_V1",
    "EXPOSED_SURFACE_AND_DIRECT_LIGHT_DISPLAY_O6_V1",
    "RESEARCHER_TRANSFORM_OVER_O2_O3_O3A_O4_O5_READ_ONLY",
    "facets_columnar",
    "composite_display_rgb",
    "SURFACE_LIGHT",
    "surface-deposit",
    "SURFACE_DEPOSITION_COMMITTED",
    "SURFACE_DEPOSITION_REJECTED",
    "explicit_surface_deposition",
    "surface_material_deposits",
    "surface_affinity_traction",
    "SURFACE_TRACTION_APPLIED",
    "traction_multiplier",
    "SURFACE_AFFINITY_TRACTION_V1",
    "LOCAL_SURFACE_MATERIAL_PROPERTY",
    "SLIPPERY",
    "STICKY",
    "surface_traction_experience_bridge",
    "TRACTION_EXPERIENCE",
    "surface_traction_prediction_adaptation",
    "TRACTION_PREDICTION_ADAPTATION",
    "physical_surface_optical_coating",
    "SURFACE_OPTICAL_COATING",
    "SURFACE_OPTICAL_COATING_OBSERVED",
    "SURFACE_OPTICAL_COATING_V1",
    "world_material_transactions",
    "WORLD_MATERIAL_TRANSACTION",
    "WORLD_MATERIAL_TRANSACTION_V1",
    "material_revision",
    "transaction_id",
    "multi_content_spatial_index",
    "SPATIAL_CONTENTS_INDEX",
    "MULTI_CONTENT_SPATIAL_INDEX",
    "spatial_index_generation",
    "spatial_index_checksum",
    # ACANTHOSTEGA PROCEDURAL SURFACE COLUMNS — authoritative world state, never cognition-visible
    "procedural_surface_columns",
    "surface_column",
    "SURFACE_COLUMN",
    "surface_elevation",
    "surface_elevation_support",
    "SURFACE_ELEVATION_TRANSITION",
    "SURFACE_ELEVATION_SUPPORT",
    "microrelief_threshold",
    "physical_height_scale",
    "W_climb",
    "baseline_checksum",
    "resolved_checksum",
    "modelled_depth",
    "material_property_derivation_version",
    "GEOMETRY_METADATA_ONLY",
    # ACANTHOSTEGA CONSERVATIVE SURFACE COLUMN TRANSFER — researcher-only world mutation
    "conservative_surface_column_transfer",
    "local_physical_signal_transport",
    "LOCAL_PHYSICAL_SIGNAL",
    "signal-emission-",
    "emission_id",
    "source_body_id",
    "toroidal_distance",
    "propagation_delay",
    # ACANTHOSTEGA PHYSICAL CONTACT ACOUSTIC EMISSION — researcher-only provenance
    "physical_contact_acoustic",
    "PHYSICAL_CONTACT",
    "contact-impulse-",
    "canonical_body_pair",
    "CONTACT_ACOUSTIC",
    "impulse_magnitude",
    # ACANTHOSTEGA FREE RESOURCE OBJECT KINEMATICS — researcher-only kinematic provenance
    "free_resource_object_kinematics",
    "FREE_OBJECT_KINEMATICS",
    "free_resource_object_ground_friction",
    "FREE_RESOURCE_OBJECT_GROUND_FRICTION",
    "GROUND_FRICTION",
    "mu_k",
    "body_normal_load_traction",
    "BODY_NORMAL_LOAD_TRACTION",
    "BODY_NORMAL_LOAD_TRACTION_STEP",
    "normal_load",
    "normal_load_N",
    "passive_sliding",
    "BODY_NORMAL_LOAD_TRACTION_PASSIVE_SLIDING_V1",
    "gentle_grounded_damping_bypassed",
    "gentle_v_stop_bypassed",
    "continuous_surface_geometry",
    "body_static_traction_threshold",
    "BODY_STATIC_TRACTION",
    "BODY_STATIC_TRACTION_THRESHOLD",
    "free_resource_object_static_traction_threshold",
    "FREE_RESOURCE_OBJECT_STATIC_TRACTION",
    "FREE_OBJECT_STATIC_TRACTION",
    "FOGF_STATIC_TRACTION_TWIN",
    "RELEASE_TRANSITION_NOT_ELIGIBLE",
    "static_traction",
    "STATIC_HOLD",
    "active_locomotion_traction_vs_sliding_friction",
    "ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION",
    "event_driven_crowded_placement_retry_contract",
    "EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT",
    "CROWDED_PLACEMENT_RETRY",
    "crowded_placement_retry",
    "detached_material_amount_scaled_collision_radius",
    "DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS",
    "DETACHED_MATERIAL_SIZE_GEOMETRY",
    "AMOUNT_SCALED_COLLISION_RADIUS",
    "held_combine_radius_resize_transaction",
    "HELD_COMBINE_RADIUS_RESIZE_TRANSACTION",
    "HELD_COMBINE_GEOMETRY_RESIZE",
    "HELD_COMBINE_RADIUS_RESIZE",
    "required_resize_work",
    "available_resize_work",
    "resize_classification",
    "REJECTED_INSUFFICIENT_RESIZE_WORK",
    "REJECTED_HOLDER_SELF_OVERLAP_GROWTH",
    "COMMITTED_RESIZE",
    "SURVIVOR_FIXED_GEOMETRY_NO_RESIZE",
    "last_held_combine_geometry_resize",
    "held_deposition_radius_shrink_transaction",
    "HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION",
    "HELD_DEPOSITION_GEOMETRY_SHRINK",
    "HELD_DEPOSITION_RADIUS_SHRINK",
    "released_pe_magnitude",
    "SOURCE_FIXED_GEOMETRY_NO_SHRINK",
    "COMMITTED_SHRINK",
    "SOURCE_EXHAUSTED_OBJECT_REMOVED",
    "SURVIVOR_GEOMETRY_DISSIPATED_NON_RECOVERABLE",
    "last_held_deposition_geometry_shrink",
    "free_space_state_and_pe_authority_contract",
    "FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT",
    "FREE_SPACE_SUPPORT_STATE_V1",
    "FREE_SPACE_STATE_PE_AUTHORITY_PROFILE_V1",
    "FREE_SPACE_V1A_STATE_AND_PE_AUTHORITY_CONTRACT",
    "last_free_space_support_state",
    "vertical_terrain_landing_contact_response",
    "VERTICAL_TERRAIN_LANDING_V1",
    "VERTICAL_TERRAIN_CONTACT",
    "LANDING_CONTACT",
    "CONTACT_EPISODE_ID",
    "TIME_OF_IMPACT",
    "PENETRATION_DEPTH",
    "LANDING_IMPULSE",
    "DISSIPATED_ENERGY",
    "SUPPORT_ACQUIRED",
    "COUPLED_3D_MULTI_CONTACT_NOT_RESOLVED_V1",
    "last_vertical_terrain_landing",
    "VERTICAL_IMPACT_ACOUSTIC_EMISSION",
    "vertical_impact_acoustic_emission",
    "VERTICAL_IMPACT_ACOUSTIC",
    "VERTICAL_IMPACT_ACOUSTIC_MEASUREMENT",
    # Body/object and object/object impact acoustics (parity with vertical/contact)
    "body_resource_object_impact_acoustic_emission",
    "BODY_RESOURCE_OBJECT_IMPACT_ACOUSTIC",
    "BODY_OBJECT_IMPACT_ACOUSTIC",
    "body_object_impact_acoustic",
    "last_body_object_impact_acoustic_step",
    "resource_object_pair_impact_acoustic_emission",
    "RESOURCE_OBJECT_PAIR_IMPACT_ACOUSTIC",
    "resource_object_pair_impact_acoustic",
    "last_resource_object_pair_impact_acoustic_step",
    # AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_CONTRACT_V1 — researcher stream only
    "AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_V1",
    "AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM",
    "authoritative_physical_acoustic_stream",
    "PHYSICAL_ACOUSTIC_STREAM_RECORD",
    "PHYSICAL_ACOUSTIC_STREAM",
    "stream_record_id",
    "stream_sequence",
    "spectral_profile_id",
    "apas:",
    # OBSERVER_ACOUSTIC_PROBE_V1 — researcher passive field sample only
    "OBSERVER_ACOUSTIC_PROBE_V1",
    "OBSERVER_ACOUSTIC_PROBE",
    "observer_acoustic_probe",
    "OBSERVER_ACOUSTIC_PROBE_SAMPLE",
    "observer-acoustic-probe-0",
    "POINT_MONO_V1",
    "PRE_PHENOTYPE_MONO_POINT_FIELD",
    "sample_key",
    "active_signals_examined",
    "contributor_count_truncated",
    "crossing_events_total",
    # PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION_CONTRACT_V1 — researcher C0 metadata only
    "PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION_CONTRACT_V1",
    "PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION",
    "physical_frequency_amplitude_calibration_contract",
    "ABSTRACT_ACOUSTIC_AUTHORITY_C0_V1",
    "C0_ABSTRACT_AUTHORITY",
    "acoustic_calibration",
    "acoustic_calibration_status",
    "CANONICAL PHYSICAL-FIELD SONIFICATION",
    "CANONICAL_PHYSICAL_FIELD_SONIFICATION",
    "CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1",
    "CANONICAL_ABSTRACT_BAND_SONIFICATION_C1_V1",
    "canonical_physical_field_sonification",
    "canonical_playback_carrier_hz",
    "PLAYBACK_DERIVED_NON_PHYSICAL",
    "SQRT_ENERGY_FIXED_REFERENCE",
    "SIX_FIXED_OSCILLATOR_CARRIERS",
    "mapped_amplitudes",
    "playback_time_scale",
    "canonical_seconds_per_tick",
    "MAX_PLAYBACK_MUTED_BY_POLICY",
    "FAST_PLAYBACK_LOSSY_MONITORING",
    "CANONICAL_SONIFICATION_UNAVAILABLE_LEGACY_EVIDENCE",
    "SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1",
    "SELECTED_ORGANISM_AUDITORY_VIEW_SAV1",
    "ORGANISM_AUDITORY_BOUNDARY_RECEIPT",
    "ORGANISM_AUDITORY_BOUNDARY_A5_V1",
    "selected_organism_auditory_view",
    "selected_organism_auditory_boundary",
    "A5_OSC_LR_ACCESSIBLE_OBSERVATION_PRE_COGNITION",
    "section_b_researcher_provenance",
    "phenotype_clip_stamp",
    "SELECTED_ORGANISM_AUDITORY_VIEW_UNAVAILABLE_LEGACY_EVIDENCE",
    "SELECTED_ORGANISM_AUDITORY_SONIFICATION_V1",
    "SELECTED_ORGANISM_AUDITORY_SONIFICATION",
    "CANONICAL_ORGANISM_RECEPTOR_SONIFICATION_SAV2_V1",
    "selected_organism_auditory_sonification",
    "LINEAR_RECEPTOR_ACTIVATION_FIXED_REFERENCE_V1",
    "TRANSLATED_STEREO_LR_RECEPTOR_MONITOR_V1",
    "PLAYBACK_DERIVED_TRANSLATED_RECEPTOR_MONITOR",
    "MUTUALLY_EXCLUSIVE_LISTENING_MODES",
    "SELECTED_ORGANISM_AUDITORY_SONIFICATION_UNAVAILABLE_LEGACY_EVIDENCE",
    "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1",
    "ORGANISM_AUDITORY_TRANSFORMATION_TRACE",
    "AUDITORY_A3_TO_A5_TRANSFORMATION_TRACE_V1",
    "A3_RAW_LR_RECEPTOR_BAND_ENERGY_PRE_PHENOTYPE",
    "A4_SENSOR_SCALE_CLIP_V1",
    "organism_auditory_transformation_trace",
    "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_UNAVAILABLE_LEGACY_EVIDENCE",
    "A3_A4_A5_TRANSFORM_MISMATCH",
    "AUTHORITATIVE_PHYSICAL_RECEPTOR_STATE_RESEARCHER_ONLY",
    "DETERMINISTIC_RESEARCHER_DERIVATION",
    "left_receptor_band_energy",
    "right_receptor_band_energy",
    "per_band_loss_accounting",
    "transform_residual",
    "a3_capture_key",
    "SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3_V1",
    "selected_organism_physical_field_comparison",
    "A3_TO_A5_CAUSAL_COMPARISON_SAV3_V1",
    "RESEARCHER_COMPARISON_OVER_AUTHORITATIVE_TRACE",
    "SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_UNAVAILABLE_LEGACY_EVIDENCE",
    "EXPERIMENTER_AUDITORY_COMPARISON_NOT_AVAILABLE",
    "band_identifiers",
    "interpretation_version",
    "SELECTED_ORGANISM_AUDITORY_OFFLINE_RECONSTRUCTION_SAV4A_V1",
    "selected_organism_auditory_offline_reconstruction",
    "SAVED_EVIDENCE_NORMALIZATION_AND_DETERMINISTIC_SCHEDULE_SAV4A_V1",
    "RESEARCHER_DERIVED_READ_ONLY_OVER_SAVED_AUTHORITATIVE_EVIDENCE",
    "SELECTED_ORGANISM_AUDITORY_OFFLINE_RECONSTRUCTION_UNAVAILABLE_LEGACY_EVIDENCE",
    "OATT_EXACT_TRACE",
    "SAV1_EXACT_A5",
    "LEGACY_OSC_A5_ONLY",
    "normalized_record_digest",
    "schedule_digest",
    "identity_segments",
    "OFFLINE AUDITORY RECONSTRUCTION",
    "SELECTED_ORGANISM_AUDITORY_OFFLINE_PLAYER_SAV4B_V1",
    "selected_organism_auditory_offline_playback",
    "SAV4A_SCHEDULE_TRANSLATED_STEREO_OFFLINE_PLAYER_SAV4B_V1",
    "RESEARCHER_DERIVED_PLAYBACK_OVER_SAV4A_SCHEDULE",
    "OFFLINE_SAV4B",
    "playback_cursor",
    "schedule_item_id",
    "OFFLINE SAVED-RUN AUDITORY RECONSTRUCTION",
    "RELEASE_EXCAVATION_SUPPORT_LOSS_V1",
    "RELEASE_VERTICAL_ELIGIBILITY",
    "SUPPORT_LOST_TERRAIN_MUTATION",
    "AFFECTED_ENTITY_SELECTION",
    "CHANGED_REGION",
    "REFRESH_DEDUP",
    "TERRAIN_TRANSACTION_ID",
    "release_and_excavation_support_loss_integration",
    "RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION",
    "RELEASE_ENTRY",
    "TERRAIN_MUTATION_REFRESH",
    "SUPPORT_REMAINS_VALID_AFTER_TERRAIN_MUTATION",
    "RELEASE_START_PENETRATION",
    "last_release_excavation_support_loss",
    "last_vertical_impact_acoustic_step",
    "ACOUSTIC_COUPLING",
    "emitted_energy",
    "silence_reason",
    "source_id",
    "UNIFORM_BROADBAND_V1",
    # OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1 — researcher display only
    "OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1",
    "OBSERVER_TERRAIN_RELIEF_AND_FREE_SPACE_MARKERS_V1",
    "vertical_display",
    "CURRENT_ELEVATION",
    "TERRAIN_DELTA",
    "CLEARANCE_STEM",
    "DISPLAY_EXAGGERATION",
    "SUPPORT_LOSS_MARKER",
    "LANDING_MARKER",
    "PHYSICAL_SOUND_SOURCE_MARKER",
    "cell_centre_elevation",
    "entities_vertical",
    "events_recent",
    "elev_min",
    "elev_max",
    "signed_delta",
    # OBSERVER_ENTITY_HEIGHT_FALL_TRAILS_V1
    "OBSERVER_ENTITY_HEIGHT_FALL_TRAILS_V1",
    "OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1_1",
    "VERTICAL_TRAJECTORY",
    "TRAIL_SEGMENT",
    "AUTHORITATIVE_SAMPLE",
    "DISPLAY_SPACE_HEIGHT",
    "RESTORE_BOUNDARY",
    "SAMPLE_COUNT",
    "Z_MIN_MAX",
    "CLEARANCE_MIN_MAX",
    "trail_segments",
    "display_space_height",

    # VW1_VOLUMETRIC_OCCUPANCY_AUTHORITY_V1 — researcher occupancy inspection only
    "VW1_VOLUMETRIC_OCCUPANCY_AUTHORITY_V1",
    "VOLUMETRIC_OCCUPANCY_SNAPSHOT_V1",
    "AUTHORITATIVE_WORLD_MATERIAL_OCCUPANCY_ABSOLUTE_Z",
    "SPARSE_ABSOLUTE_Z_OCCUPIED_INTERVALS_V1",
    "volumetric_occupancy",
    "volumetric_world_material_occupancy",
    "occupied_intervals",
    "free_gaps",
    "derived_surface_elevation",
    "LEGACY_SURFACE_COLUMN_DERIVATION",
    "SPARSE_AUTHORITY",
    "VOLUMETRIC_OCCUPANCY_COLUMN_INSPECTION",
    "HALF_OPEN_LOWER_EXCLUSIVE_UPPER_INCLUSIVE",
    "interval_endpoint_semantics",
    "compatibility_surface_elevation",
    "researcher_only_view",

    # VW2_OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES_V1
    "VW2_OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES_V1",
    "AUTHORITATIVE_SUPPORT_CONTACT_FROM_VOLUMETRIC_OCCUPANCY",
    "occupancy_support_and_contact_queries",
    "occupancy_support_contact",
    "occupancy_support_contact_state",
    "support_capable",
    "boundary_z",
    "contradicts_legacy_projected_surface",
    "VERTICAL_SUPPORT_AT",
    "NO_SUPPORT_BELOW",
    "ABOVE_SUPPORT",
    "AT_SUPPORT",
    "INSIDE_OCCUPIED",
    "VW2_SUPPORT_CONTACT_INSPECTION",
    "CEILING_PROBE_ABOVE",

    # VW3_VOLUMETRIC_MATERIAL_SEPARATION_V1
    "VW3_VOLUMETRIC_MATERIAL_SEPARATION_V1",
    "AUTHORITATIVE_VOLUMETRIC_MATERIAL_SEPARATION_VIA_WMT",
    "volumetric_world_material_separation",
    "volumetric_material_separation",
    "volumetric_material_separation_state",
    "SEPARATE_VOLUMETRIC_OCCUPANCY_INTERVAL",
    "removed_pieces",
    "VW3_SEPARATION_INSPECTION",
    "VOLUMETRIC_MATERIAL_SEPARATION",

    # VW4_CONSERVATIVE_VOLUMETRIC_DEPOSITION_REINTEGRATION_V1
    "VW4_CONSERVATIVE_VOLUMETRIC_DEPOSITION_REINTEGRATION_V1",
    "AUTHORITATIVE_VOLUMETRIC_MATERIAL_REINTEGRATION_VIA_WMT",
    "volumetric_world_material_reintegration",
    "volumetric_material_reintegration",
    "volumetric_material_reintegration_state",
    "REINTEGRATE_VOLUMETRIC_OCCUPANCY_INTERVAL",
    "VW4_REINTEGRATION_INSPECTION",
    "VOLUMETRIC_MATERIAL_REINTEGRATION",
    "conservative_volumetric_material_reintegration",

    # VW5_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE_V1
    "VW5_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE_V1",
    "AUTHORITATIVE_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE",
    "effector_held_occupancy_exertion_bridge",
    "organism_physical_interaction_with_volumetric_world",
    "VW5_BRIDGE_INSPECTION",
    "volumetric_occupancy_floor_below",
    "FLOOR_BELOW_GREATEST_ZMAX_THEN_DETERMINISTIC_TIEBREAK",

    # VOLUMETRIC_ANALYZER_PHYSICAL_CAUSAL_RECONSTRUCTION_V1 / reachability trace
    "VOLUMETRIC_ANALYZER_PHYSICAL_CAUSAL_RECONSTRUCTION_V1",
    "EFFECTOR_OCCUPANCY_REACHABILITY_TRACE_V1",
    "RESEARCHER_TRACE_OVER_EXISTING_EFFECTOR_AND_VW1_GEOMETRY",
    "RESEARCHER_RECONSTRUCTION_OVER_AUTHORITATIVE_PHYSICAL_RECEIPTS",
    "VW1_TO_VW6_MECHANISM_CAUSAL_STORY_V1",
    "volumetric_analyzer_physical_causal_reconstruction",
    "effector_occupancy_reachability_trace",
    "effector_occupancy_reachability_trace_state",
    "signed_minimum_separation",
    "control_repertoire_class",
    "REQUIRED_CONTROL_NOT_IN_REPERTOIRE",
    "ACTUATED_NO_GEOMETRIC_REACH",
    "GEOMETRIC_REACH_NO_CONTACT",
    "CONTACT_INSUFFICIENT_WORK",
    "CONTACT_NO_WORK",
    "NOT_SELECTED",
    "SELECTED_NOT_ACTUATED",
    "relative_z",
    "effector_z_left",
    "effector_z_right",
    "requested_relative_delta",
    "achieved_relative_delta",
    "last_agent_effector_z_actuation",
    "POST_FAILURE_MANIPULATION_NOT_ESTABLISHED",
    "VOLUMETRIC PHYSICAL CAUSAL STORY",
    "causal_ladder",
    "negative_cause",

    # VW6_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE_V1
    "VW6_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE_V1",
    "AUTHORITATIVE_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE",
    "minimal_vision_3d_geometric_interface",
    "minimal_volumetric_3d_visual_geometry",
    "VW6_VISION_3D_INSPECTION",
    "occupancy_los",
    "occluded_by_occupancy",
    "OCCLUDED_BY_OCCUPANCY",
    "legacy_max_surface_would_block",
    "eye_xyz",
    "target_xyz",
    "elevation_rad",
    "elevation_deg",
    "distance_3d",
    "vw6_geometry",
    "vertical_acceptance",
    "OUTSIDE_VERTICAL_ACCEPTANCE",

    # OBSERVER_SELECTED_ORGANISM_VOLUMETRIC_VISION_VIEW_V1 — researcher reconstruction only
    "SELECTED_ORGANISM_VOLUMETRIC_VISION_VIEW_V1",
    "selected_organism_volumetric_vision_view",
    "VW6_PHYSICAL_GEOMETRY_TO_ORGANISM_VISUAL_INPUT_AUDIT_V1",
    "RESEARCHER_VISUALIZATION_OVER_EXISTING_VW6_PERCEPTION",
    "selected_organism_volumetric_vision_state",
    "SELECTED_ORGANISM_VOLUMETRIC_VISION_STATE_V1",
    "EXPERIMENTER_VOLUMETRIC_VISION_BOUNDARY_NOT_AVAILABLE",
    "SELECTED_ORGANISM_VOLUMETRIC_VISION_UNAVAILABLE_LEGACY_EVIDENCE",
    "RECEPTOR_ONLY_FALLBACK_GEOMETRIC_TRACE_UNAVAILABLE",
    "AUDIT REJECTED CANDIDATES",
    "NOT AVAILABLE TO ORGANISM",
    "RESEARCHER_LOS_OVERLAY",
    "organism_visible",
    "rejection_class",
    "BLOCKED_BY_VW1_OCCUPANCY",
    "OUTSIDE_VERTICAL_FOV",
    "OUTSIDE_HORIZONTAL_FOV",
    "geometric_trace_available",
    "occupancy_digest",
    "trace_id",
    "AZIMUTH_ELEVATION_DIAGNOSTIC",

    # OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1
    "OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1",
    "RESEARCHER_CAMERA_OVER_AUTHORITATIVE_VOLUMETRIC_OCCUPANCY",
    "observer_camera_occupancy_consumer",
    "researcher_3d_camera_over_authoritative_volumetric_world",
    "occupancy_volumes",
    "OCCUPIED_INTERVAL_PRISM",
    "OBSERVER_RENDER_LIGHTING_ONLY",

    "PE_AUTHORITY_SUPPORTED_TERRAIN",
    "PE_AUTHORITY_UNSUPPORTED_FREE_SPACE",
    "PE_AUTHORITY_HELD_NO_INDEPENDENT",
    "PE_AUTHORITY",
    "SUPPORT_LOST",
    "SUPPORT_LOST_HORIZONTAL_MOTION",
    "SUPPORT_LOST_TERRAIN_MUTATION",
    "SUPPORT_ACQUIRED_INELASTIC_CLAMP",
    "GRAVITY_SKIPPED_VALID_SUPPORT",
    "CURRENT_INELASTIC_CLAMP_DISSIPATION",
    "TERRAIN_INTERSECT",
    "SUPPORTED",
    "UNSUPPORTED",
    "CONSTRAINED_HELD_NOT_INDEPENDENT",
    "double_pe_authority",
    "active_pe_authority",
    "HELD_BASE_FEET_SNAP_RETAINED",
    "size_geometry_profile",
    "size_geometry_clamp_status",
    "retry_event_id",
    "exertion_event_id",
    "candidate_summary",
    "blocker_ids",
    "DEDUPLICATED_SAME_EVENT",
    "REJECTED_CROWDED",
    "traction_protection_applied",
    "full_drive_protected",
    "protected_mag",
    "FULL_SUPPORT",
    "PARTIAL_SUPPORT",
    "EDGE_OR_SPARSE_SUPPORT",
    "LOSS_OF_SUPPORT",
    "AIRBORNE_NO_SUPPORT",
    "RADIUS_AWARE_SUPPORT",
    "RADIUS_AWARE_SUPPORT_POINTS",
    "RADIUS_SUPPORT_CLASS",
    "RADIUS_SUPPORT_LOST",
    "SUPPORT_CONTACT_CLASS",

    "STATIC_BREAKAWAY",
    "mu_static",
    "j_static_max",
    "G2A_STATIC_TRACTION_THRESHOLD",
    "physical_static_hold",
    "CONTINUOUS_SURFACE_GEOMETRY",
    "CONTINUOUS_SURFACE_SAMPLE",
    "BILINEAR_HEIGHT_ANALYTIC_NORMAL_V1",
    "analytic_normal",
    "surface_gradient",
    "corner_heights",
    "bilinear_weights",
    "normal_physical_effects_active",
    "height_physical_effects_active",
    "FREE_MOVING",
    "RESOURCE_OBJECT_RELEASE_KINEMATICS",
    "RESOURCE_OBJECT_FREE_MOTION",
    "object-release-",
    "object-motion-",
    "release_transfer",
    "inherited_velocity",
    "measured_effector_velocity",
    "TRANSFER_SURFACE_COLUMN_SLICE",
    "surface-column",
    "transfer_id",
    "transfer_role",
    "fixed_lower_datum",
    "resolved_modelled_depth",
    "requested_thickness",
    "committed_thickness",
    "transferred_mass",
    "transferred_quantity",
    "transferred_component",
    "net_exchange",
    "layer_merge",
    "CROSSES_LAYER_BOUNDARY",
    "INTERVENTION_SETUP",
    "PERSISTENT_AUTHORITATIVE_GEOMETRY_SCAR",
    "LOW_TRACTION",
    "HIGH_TRACTION",
    "holder_body_id",
    "manipulator_id",
    "GRASP_SUCCEEDED",
)


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _norm_signed(x: float, scale: float) -> float:
    """Map signed quantity into [0, 1] via 0.5 + 0.5*tanh(x/scale)."""
    s = max(1e-9, float(scale))
    return _clip01(0.5 + 0.5 * float(np.tanh(float(x) / s)))


def audit_cognition_payload(payload: Any) -> list[str]:
    """Return forbidden token hits in a cognition-facing structure."""
    text = repr(payload)
    return [tok for tok in FORBIDDEN_TOKENS if tok in text]


def world_truth_summary(world: PlanetState) -> dict[str, Any]:
    """Observer-only WORLD TRUTH summary — never pass to cognition."""
    return {
        "kind": "WORLD_TRUTH",
        "tick": int(world.tick),
        "T_mean": float(np.mean(world.T)),
        "T_std": float(np.std(world.T)),
        "M_sum": [float(np.sum(world.M[i])) for i in range(world.M.shape[0])],
        "vx_mean": float(np.mean(world.vx)),
        "vy_mean": float(np.mean(world.vy)),
        "shape": {"T": list(world.T.shape), "M": list(world.M.shape)},
    }


def accessible_observation(
    *,
    world: PlanetState,
    body: PhysicalBodyState,
    internal: InternalMediumState,
    planet_config: PlanetConfig,
    body_config: PhysicalBodyConfig,
    include_signal_fields: bool = True,
    near_field_cfg: Any = None,
    foreign_bodies: Any = None,
    vestibular_cfg: Any = None,
    neck_proprioception_cfg: Any = None,
    articulated_head_cfg: Any = None,
    oscillatory_cfg: Any = None,
    orientation_meta: Any = None,
    prev_omega: float | None = None,
    manipulator_cfg: Any = None,
    holder_body_id: str | None = None,
    manipulator_proprioception_enabled: bool = False,
    physical_config: Any = None,
    manipulator_runtime: Any = None,
) -> dict[str, float]:
    """Canonical physically accessible observation fragment (dict[str, float]).

    Signal keys appear only when world.FIELD_* exists AND include_signal_fields.
    Default PSR has no FIELD arrays, so observation keys stay unchanged.
    Near-field exo_* fragments appear only when near_field_cfg is enabled
    and perception_enabled (ablation: perception_enabled=False → no exo_*).
    Vestibular vest_* / neck prop_neck_* appear only when those sensors are ON.
    """
    w = int(planet_config.width)
    h = int(planet_config.height)
    cells = body.cells(w, h, body_config.footprint)
    n = max(1, len(cells))
    t_loc = 0.0
    m_loc = np.zeros(3, dtype=np.float64)
    vx_loc = 0.0
    vy_loc = 0.0
    for iy, ix in cells:
        t_loc += float(world.T[iy, ix])
        m_loc += world.M[:, iy, ix]
        vx_loc += float(world.vx[iy, ix])
        vy_loc += float(world.vy[iy, ix])
    t_loc /= n
    m_loc /= n
    vx_loc /= n
    vy_loc /= n

    vmax = float(getattr(body_config, "v_max", 0.3) or 0.3)
    frag: dict[str, float] = {
        "body.T": _clip01(float(body.T)),
        "body.B0": _clip01(float(body.B[0]) / max(1e-9, float(body_config.B_max))),
        "body.B1": _clip01(float(body.B[1]) / max(1e-9, float(body_config.B_max))),
        "body.B2": _clip01(float(body.B[2]) / max(1e-9, float(body_config.B_max))),
        "body.mech": _clip01(float(body.mech)),
        "body.vx": _norm_signed(float(body.vx), vmax),
        "body.vy": _norm_signed(float(body.vy), vmax),
        "local.T": _clip01(t_loc),
        "local.M0": _clip01(float(m_loc[0])),
        "local.M1": _clip01(float(m_loc[1])),
        "local.M2": _clip01(float(m_loc[2])),
        "local.vx": _norm_signed(vx_loc, 1.0),
        "local.vy": _norm_signed(vy_loc, 1.0),
    }
    if include_signal_fields:
        for name, key in (("FIELD_A", "local.FIELD_A"), ("FIELD_B", "local.FIELD_B")):
            arr = getattr(world, name, None)
            if arr is None:
                continue
            s = 0.0
            for iy, ix in cells:
                s += float(arr[iy, ix])
            frag[key] = _clip01(s / n)
    # Embodied internal medium is owned by the same agent; expose channel means only.
    c = np.asarray(internal.c, dtype=np.float64)
    if c.size:
        means = c.reshape(c.shape[0], -1).mean(axis=1) if c.ndim >= 2 else c.reshape(-1)
        for i, val in enumerate(means.tolist()[:5]):
            frag[f"internal.c{i}"] = _clip01(float(val))
    # Directional near-field exteroception (PHYSICAL_PERCEPTION_01 + body optics).
    if near_field_cfg is not None:
        from mechanistic_mind.physical_system.near_field_exteroception import cognition_exo_fragments
        exo = cognition_exo_fragments(
            world=world, body=body, cfg=near_field_cfg, foreign_bodies=foreign_bodies,
            physical_config=physical_config,
        )
        for k, v in exo.items():
            frag[str(k)] = _clip01(float(v))
        from mechanistic_mind.physical_system.near_field_exteroception import cognition_surface_fragments
        surf = cognition_surface_fragments(
            world=world, body=body, cfg=near_field_cfg, foreign_bodies=foreign_bodies,
            physical_config=physical_config,
        )
        for k, v in surf.items():
            frag[str(k)] = _clip01(float(v))
        from mechanistic_mind.physical_system.near_field_exteroception import cognition_spatial_fragments
        spat = cognition_spatial_fragments(
            world=world, body=body, cfg=near_field_cfg, foreign_bodies=foreign_bodies,
            physical_config=physical_config,
        )
        for k, v in spat.items():
            frag[str(k)] = _clip01(float(v))
    # Vestibular / neck proprioception (anonymous; no compass / absolute heading).
    if vestibular_cfg is not None:
        from mechanistic_mind.physical_system.vestibular_proprioception import (
            cognition_vestibular_fragments,
        )
        vest = cognition_vestibular_fragments(
            body,
            vestibular_cfg,
            orientation_meta=orientation_meta if isinstance(orientation_meta, dict) else None,
            prev_omega=prev_omega,
        )
        for k, v in vest.items():
            frag[str(k)] = float(v)
    if neck_proprioception_cfg is not None:
        from mechanistic_mind.physical_system.vestibular_proprioception import (
            cognition_neck_proprioception_fragments,
        )
        prop = cognition_neck_proprioception_fragments(
            body,
            neck_proprioception_cfg,
            articulated_head=articulated_head_cfg,
        )
        for k, v in prop.items():
            frag[str(k)] = float(v)
    # Oscillatory L/R banded receptors (anonymous; no source id/direction/frequency).
    if oscillatory_cfg is not None:
        from mechanistic_mind.physical_system.oscillatory_signaling import cognition_osc_fragments
        head_on = bool(getattr(articulated_head_cfg, "enabled", False)) if articulated_head_cfg else False
        osc = cognition_osc_fragments(
            body, world, oscillatory_cfg, articulated_head=head_on,
        )
        for k, v in osc.items():
            frag[str(k)] = float(v)
    if manipulator_proprioception_enabled and holder_body_id is not None:
        from mechanistic_mind.physical_system.physical_manipulator import cognition_grip_fragments
        grip = cognition_grip_fragments(
            world=world,
            holder_body_id=str(holder_body_id),
            enabled=True,
            manipulator_id=str(getattr(manipulator_cfg, "manipulator_id", None) or "manipulator_0"),
            config=physical_config,
            runtime=manipulator_runtime,
        )
        for k, v in grip.items():
            frag[str(k)] = float(v)
    # Leak guard on own output
    hits = audit_cognition_payload(frag)
    if hits:
        raise RuntimeError(f"accessible_observation leaked forbidden tokens: {hits}")
    return frag


def observation_bundle(
    *,
    world: PlanetState,
    body: PhysicalBodyState,
    internal: InternalMediumState,
    planet_config: PlanetConfig,
    body_config: PhysicalBodyConfig,
    include_signal_fields: bool = True,
    near_field_cfg: Any = None,
    foreign_bodies: Any = None,
) -> dict[str, Any]:
    """Observer-facing pair: WORLD TRUTH + AGENT OBSERVATION (separated)."""
    bundle: dict[str, Any] = {
        "world_truth": world_truth_summary(world),
        "agent_observation": accessible_observation(
            world=world,
            body=body,
            internal=internal,
            planet_config=planet_config,
            body_config=body_config,
            include_signal_fields=include_signal_fields,
            near_field_cfg=near_field_cfg,
            foreign_bodies=foreign_bodies,
        ),
        "boundary": "cognition_receives_agent_observation_only",
    }
    if near_field_cfg is not None and getattr(near_field_cfg, "enabled", False):
        from mechanistic_mind.physical_system.near_field_exteroception import sample_near_field
        bundle["near_field_sensor_gt"] = sample_near_field(
            world=world, body=body, cfg=near_field_cfg, foreign_bodies=foreign_bodies,
            physical_config=getattr(world, "_physical_system_config", None),
        )
    return bundle