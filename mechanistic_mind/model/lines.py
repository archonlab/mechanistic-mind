"""Preset → model identity. Not an independent model_line selector.

Canonical public presets own model_line / runtime_version. Missing metadata is Tiktaalik.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.model import acanthostega as acanthostega_identity
from mechanistic_mind.model.identity import RUNTIME_VERSION as TIKTAALIK_RUNTIME_VERSION
from mechanistic_mind.model.tiktaalik import model_metadata as tiktaalik_model_metadata

MODEL_LINE_TIKTAALIK = "TIKTAALIK"
MODEL_LINE_ACANTHOSTEGA = "ACANTHOSTEGA"


def normalize_model_line(raw: Any) -> str:
    s = str(raw or "").strip().upper().replace("—", "-")
    compact = " ".join(s.replace("_", " ").split())
    if not s:
        return MODEL_LINE_TIKTAALIK
    if s in {MODEL_LINE_ACANTHOSTEGA, acanthostega_identity.PUBLIC_PRESET} or "ACANTHOSTEGA" in compact:
        return MODEL_LINE_ACANTHOSTEGA
    return MODEL_LINE_TIKTAALIK


def identity_from_public_preset(
    public_preset: Any,
    config=None,
    *,
    seed: int | None = None,
    tick: int | None = None,
) -> dict[str, Any]:
    from mechanistic_mind.physical_system.experiment_canonical import (
        is_acanthostega_public_preset,
        normalize_preset_name,
    )

    preset = normalize_preset_name(public_preset)
    if is_acanthostega_public_preset(preset):
        return acanthostega_identity.model_metadata(config, seed=seed, tick=tick)
    meta = dict(tiktaalik_model_metadata(config, seed=seed, tick=tick))
    meta["model_line"] = MODEL_LINE_TIKTAALIK
    if preset:
        meta["public_preset"] = preset
    return meta


def stamp_config_from_preset(config: Any, public_preset: Any) -> Any:
    """Stamp identity fields from the canonical preset. Preset is the authority."""
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA,
        PRESET_ACANTHOSTEGA_GENTLE,
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
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
        PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        is_acanthostega_public_preset,
        normalize_preset_name,
        preset_canonical,
    )

    if config is None:
        return config
    preset = normalize_preset_name(public_preset)

    # Declared Acanthostega builders (Beta 4 chain, etc.): apply full profile.
    # Preserve caller planet/cognition when already attached (Observer Apply path).
    if is_acanthostega_public_preset(preset):
        canon = preset_canonical(preset) or {}
        builder_name = canon.get("builder") if isinstance(canon, dict) else None
        if builder_name:
            fn = getattr(acanthostega_identity, str(builder_name), None)
            if callable(fn):
                built = fn()
                planet = getattr(config, "planet", None)
                cognition = getattr(config, "cognition", None)
                for key, value in vars(built).items():
                    setattr(config, key, value)
                if planet is not None:
                    config.planet = planet
                if cognition is not None:
                    config.cognition = cognition
                config.model_line = MODEL_LINE_ACANTHOSTEGA
                config.public_preset = preset
                config.runtime_version = TIKTAALIK_RUNTIME_VERSION
                return config

    from mechanistic_mind.physical_system.physical_manipulator import (
        set_bilateral_bring_together,
        set_bilateral_grasp_release,
        set_bilateral_physical_manipulators,
        set_physical_grasp_release,
        set_single_physical_manipulator,
    )
    if preset in {
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
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
        PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
    }:
        from mechanistic_mind.physical_system.physical_manipulator import (
            BilateralBringTogetherConfig,
            BilateralGraspReleaseConfig,
            BilateralPhysicalManipulatorsConfig,
        )
        from mechanistic_mind.physical_system.locomotion_profile import (
            acanthostega_gentle_locomotion_profile,
        )
        from mechanistic_mind.physical_system.resource_objects import (
            PhysicalResourceObjectVisionConfig,
            PhysicalResourceObjectsConfig,
            default_bilateral_spawn_objects,
            set_physical_resource_object_vision,
            set_physical_resource_objects,
        )
        config.model_line = MODEL_LINE_ACANTHOSTEGA
        config.public_preset = preset
        config.locomotion_profile = acanthostega_gentle_locomotion_profile()
        spawn_objects = default_bilateral_spawn_objects()
        if preset in {
            PRESET_ACANTHOSTEGA_SURFACE_TRACTION,
            PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE,
            PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION,
            PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
        }:
            from mechanistic_mind.physical_system.surface_affinity_traction import (
                traction_contrast_spawn_objects,
            )
            spawn_objects = traction_contrast_spawn_objects()
        elif preset in {PRESET_ACANTHOSTEGA_WORLD_MATERIAL, PRESET_ACANTHOSTEGA_MULTI_CONTENT, PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS, PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS}:
            from mechanistic_mind.physical_system.physical_surface_optical_coating import (
                surface_optical_spawn_objects,
            )
            spawn_objects = surface_optical_spawn_objects()
        config.physical_resource_objects = PhysicalResourceObjectsConfig(
            enabled=True, spawn_objects=spawn_objects,
        )
        set_physical_resource_objects(config, True)
        config.physical_resource_object_vision = PhysicalResourceObjectVisionConfig(enabled=True)
        set_physical_resource_object_vision(config, True)
        set_single_physical_manipulator(config, False)
        set_physical_grasp_release(config, False)
        config.bilateral_physical_manipulators = BilateralPhysicalManipulatorsConfig(enabled=True)
        set_bilateral_physical_manipulators(config, True)
        config.bilateral_grasp_release = BilateralGraspReleaseConfig(enabled=True)
        set_bilateral_grasp_release(config, True)
        config.bilateral_bring_together = BilateralBringTogetherConfig(enabled=True)
        set_bilateral_bring_together(config, True)
        from mechanistic_mind.physical_system.material_composition import (
            MaterialCompositionMergeConfig, set_material_composition_merge,
        )
        config.material_composition_merge = MaterialCompositionMergeConfig(
            enabled=preset in {
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
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
        PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
            }
        )
        set_material_composition_merge(
            config, preset in {
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
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
        PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
            }
        )
    elif preset == PRESET_ACANTHOSTEGA_BILATERAL_GRASP:
        config.model_line = MODEL_LINE_ACANTHOSTEGA
        config.public_preset = PRESET_ACANTHOSTEGA_BILATERAL_GRASP
        from mechanistic_mind.physical_system.locomotion_profile import (
            acanthostega_gentle_locomotion_profile,
        )
        from mechanistic_mind.physical_system.resource_objects import (
            PhysicalResourceObjectVisionConfig,
            PhysicalResourceObjectsConfig,
            default_bilateral_spawn_objects,
            set_physical_resource_object_vision,
            set_physical_resource_objects,
        )
        from mechanistic_mind.physical_system.physical_manipulator import (
            BilateralGraspReleaseConfig,
            BilateralPhysicalManipulatorsConfig,
        )
        config.locomotion_profile = acanthostega_gentle_locomotion_profile()
        config.physical_resource_objects = PhysicalResourceObjectsConfig(
            enabled=True, spawn_objects=default_bilateral_spawn_objects(),
        )
        set_physical_resource_objects(config, True)
        config.physical_resource_object_vision = PhysicalResourceObjectVisionConfig(enabled=True)
        set_physical_resource_object_vision(config, True)
        set_single_physical_manipulator(config, False)
        set_physical_grasp_release(config, False)
        config.bilateral_physical_manipulators = BilateralPhysicalManipulatorsConfig(enabled=True)
        set_bilateral_physical_manipulators(config, True)
        config.bilateral_grasp_release = BilateralGraspReleaseConfig(enabled=True)
        set_bilateral_grasp_release(config, True)
        set_bilateral_bring_together(config, False)
    elif preset == PRESET_ACANTHOSTEGA_SINGLE_GRASP:
        config.model_line = MODEL_LINE_ACANTHOSTEGA
        config.public_preset = PRESET_ACANTHOSTEGA_SINGLE_GRASP
        from mechanistic_mind.physical_system.locomotion_profile import (
            acanthostega_gentle_locomotion_profile,
        )
        from mechanistic_mind.physical_system.resource_objects import (
            PhysicalResourceObjectVisionConfig,
            PhysicalResourceObjectsConfig,
            set_physical_resource_object_vision,
            set_physical_resource_objects,
        )
        from mechanistic_mind.physical_system.physical_manipulator import (
            PhysicalGraspReleaseConfig,
            SinglePhysicalManipulatorConfig,
        )
        config.locomotion_profile = acanthostega_gentle_locomotion_profile()
        config.physical_resource_objects = PhysicalResourceObjectsConfig(enabled=True)
        set_physical_resource_objects(config, True)
        config.physical_resource_object_vision = PhysicalResourceObjectVisionConfig(enabled=True)
        set_physical_resource_object_vision(config, True)
        config.single_physical_manipulator = SinglePhysicalManipulatorConfig(enabled=True)
        set_single_physical_manipulator(config, True)
        config.physical_grasp_release = PhysicalGraspReleaseConfig(enabled=True)
        set_physical_grasp_release(config, True)
        set_bilateral_physical_manipulators(config, False)
        set_bilateral_grasp_release(config, False)
        set_bilateral_bring_together(config, False)
    elif preset == PRESET_ACANTHOSTEGA_MATERIAL_VISION:
        config.model_line = MODEL_LINE_ACANTHOSTEGA
        config.public_preset = PRESET_ACANTHOSTEGA_MATERIAL_VISION
        from mechanistic_mind.physical_system.locomotion_profile import (
            acanthostega_gentle_locomotion_profile,
        )
        from mechanistic_mind.physical_system.resource_objects import (
            PhysicalResourceObjectVisionConfig,
            PhysicalResourceObjectsConfig,
            set_physical_resource_object_vision,
            set_physical_resource_objects,
        )
        config.locomotion_profile = acanthostega_gentle_locomotion_profile()
        config.physical_resource_objects = PhysicalResourceObjectsConfig(enabled=True)
        set_physical_resource_objects(config, True)
        config.physical_resource_object_vision = PhysicalResourceObjectVisionConfig(enabled=True)
        set_physical_resource_object_vision(config, True)
        set_single_physical_manipulator(config, False)
        set_physical_grasp_release(config, False)
        set_bilateral_physical_manipulators(config, False)
        set_bilateral_grasp_release(config, False)
    elif preset == PRESET_ACANTHOSTEGA_MATERIALS:
        config.model_line = MODEL_LINE_ACANTHOSTEGA
        config.public_preset = PRESET_ACANTHOSTEGA_MATERIALS
        from mechanistic_mind.physical_system.locomotion_profile import (
            acanthostega_gentle_locomotion_profile,
        )
        from mechanistic_mind.physical_system.resource_objects import (
            PhysicalResourceObjectsConfig,
            set_physical_resource_objects,
        )
        config.locomotion_profile = acanthostega_gentle_locomotion_profile()
        config.physical_resource_objects = PhysicalResourceObjectsConfig(enabled=True)
        set_physical_resource_objects(config, True)
        from mechanistic_mind.physical_system.resource_objects import set_physical_resource_object_vision
        set_physical_resource_object_vision(config, False)
        set_single_physical_manipulator(config, False)
        set_physical_grasp_release(config, False)
        set_bilateral_physical_manipulators(config, False)
        set_bilateral_grasp_release(config, False)
    elif preset == PRESET_ACANTHOSTEGA_GENTLE:
        config.model_line = MODEL_LINE_ACANTHOSTEGA
        config.public_preset = PRESET_ACANTHOSTEGA_GENTLE
        from mechanistic_mind.physical_system.locomotion_profile import (
            acanthostega_gentle_locomotion_profile,
        )
        config.locomotion_profile = acanthostega_gentle_locomotion_profile()
        from mechanistic_mind.physical_system.resource_objects import (
            set_physical_resource_object_vision,
            set_physical_resource_objects,
        )
        set_physical_resource_objects(config, False)
        set_physical_resource_object_vision(config, False)
        set_single_physical_manipulator(config, False)
        set_physical_grasp_release(config, False)
        set_bilateral_physical_manipulators(config, False)
        set_bilateral_grasp_release(config, False)
    elif preset == PRESET_ACANTHOSTEGA:
        config.model_line = MODEL_LINE_ACANTHOSTEGA
        config.public_preset = PRESET_ACANTHOSTEGA
        from mechanistic_mind.physical_system.locomotion_profile import tiktaalik_locomotion_profile
        from mechanistic_mind.physical_system.resource_objects import (
            set_physical_resource_object_vision,
            set_physical_resource_objects,
        )
        config.locomotion_profile = tiktaalik_locomotion_profile()
        set_physical_resource_objects(config, False)
        set_physical_resource_object_vision(config, False)
        set_single_physical_manipulator(config, False)
        set_physical_grasp_release(config, False)
        set_bilateral_physical_manipulators(config, False)
        set_bilateral_grasp_release(config, False)
    elif is_acanthostega_public_preset(preset):
        # Acanthostega without a declared builder: never fall through to Tiktaalik.
        config.model_line = MODEL_LINE_ACANTHOSTEGA
        config.public_preset = preset
    elif preset:
        config.model_line = MODEL_LINE_TIKTAALIK
        config.public_preset = preset
        from mechanistic_mind.physical_system.resource_objects import (
            set_physical_resource_object_vision,
            set_physical_resource_objects,
        )
        set_physical_resource_objects(config, False)
        set_physical_resource_object_vision(config, False)
        set_single_physical_manipulator(config, False)
        set_physical_grasp_release(config, False)
        set_bilateral_physical_manipulators(config, False)
        set_bilateral_grasp_release(config, False)
    else:
        config.model_line = MODEL_LINE_TIKTAALIK
        from mechanistic_mind.physical_system.resource_objects import (
            set_physical_resource_object_vision,
            set_physical_resource_objects,
        )
        set_physical_resource_objects(config, False)
        set_physical_resource_object_vision(config, False)
        set_single_physical_manipulator(config, False)
        set_physical_grasp_release(config, False)
        set_bilateral_physical_manipulators(config, False)
        set_bilateral_grasp_release(config, False)
    from mechanistic_mind.physical_system.passive_material_properties import (
        set_passive_material_properties,
    )
    set_passive_material_properties(
        config, preset in {
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
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
        PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }
    )
    from mechanistic_mind.physical_system.explicit_surface_deposition import (
        set_explicit_surface_deposition,
    )
    set_explicit_surface_deposition(
        config, preset in {
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
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }
    )
    from mechanistic_mind.physical_system.surface_affinity_traction import (
        set_surface_affinity_traction,
    )
    set_surface_affinity_traction(
        config, preset in {
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
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }
    )
    from mechanistic_mind.physical_system.surface_traction_experience import (
        set_surface_traction_experience,
    )
    set_surface_traction_experience(
        config, preset in {
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
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }
    )
    from mechanistic_mind.physical_system.surface_traction_prediction import (
        set_surface_traction_prediction,
    )
    set_surface_traction_prediction(
        config, preset in {
            PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION,
            PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
            PRESET_ACANTHOSTEGA_WORLD_MATERIAL,
            PRESET_ACANTHOSTEGA_MULTI_CONTENT,
            PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
            PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
            PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }
    )
    from mechanistic_mind.physical_system.physical_surface_optical_coating import (
        set_physical_surface_optical_coating,
    )
    set_physical_surface_optical_coating(
        config, preset in {
            PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
            PRESET_ACANTHOSTEGA_WORLD_MATERIAL,
            PRESET_ACANTHOSTEGA_MULTI_CONTENT,
            PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
            PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
            PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        }
    )
    from mechanistic_mind.physical_system.world_material_transaction import (
        set_world_material_transactions,
    )
    set_world_material_transactions(
        config, preset in {PRESET_ACANTHOSTEGA_WORLD_MATERIAL, PRESET_ACANTHOSTEGA_MULTI_CONTENT, PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS, PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW}
    )
    from mechanistic_mind.physical_system.spatial_contents import (
        set_multi_content_spatial_index,
    )
    set_multi_content_spatial_index(
        config, preset in {PRESET_ACANTHOSTEGA_MULTI_CONTENT, PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS, PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW}
    )
    from mechanistic_mind.physical_system.procedural_surface_columns import (
        set_procedural_surface_columns,
    )
    _psc_presets = {PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS, PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW}
    set_procedural_surface_columns(config, preset in _psc_presets)
    # VW1: same preset gate as PSC — sparse absolute-Z occupancy authority (no support/contact migration).
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        set_volumetric_world_material_occupancy,
    )
    set_volumetric_world_material_occupancy(config, preset in _psc_presets)
    from mechanistic_mind.physical_system.conservative_surface_column_transfer import (
        set_conservative_surface_column_transfer,
    )
    set_conservative_surface_column_transfer(
        config, preset in {PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW}
    )
    from mechanistic_mind.physical_system.local_physical_signal_transport import (
        set_local_physical_signal_transport,
    )
    set_local_physical_signal_transport(
        config, preset in {
            PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
            PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        }
    )
    from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
        set_physical_contact_acoustic_emission,
    )
    set_physical_contact_acoustic_emission(
        config,
        preset in {PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS},
    )
    from mechanistic_mind.physical_system.free_resource_object_kinematics import (
        set_free_resource_object_kinematics,
    )
    set_free_resource_object_kinematics(config, preset in {PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS})

    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        set_body_object_contact,
    )
    set_body_object_contact(config, preset in {PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS})
    from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
        set_body_object_impulse,
    )
    set_body_object_impulse(
        config,
        preset in {PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS},
    )
    from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
        set_body_object_impact_acoustics,
    )
    set_body_object_impact_acoustics(
        config,
        preset in {PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS},
    )
    from mechanistic_mind.physical_system.physical_resource_object_pair_contact import (
        set_resource_object_pair_contact,
    )
    set_resource_object_pair_contact(
        config,
        preset in {PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS},
    )
    from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
        set_resource_object_pair_impulse,
    )
    set_resource_object_pair_impulse(
        config,
        preset in {
            PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
            PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        },
    )
    from mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission import (
        set_resource_object_pair_impact_acoustics,
    )
    set_resource_object_pair_impact_acoustics(
        config, preset in {PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS}
    )

    from mechanistic_mind.physical_system.held_resource_object_foreign_body_contact import (
        set_held_foreign_body_contact,
    )
    from mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation import (
        set_held_translational_impulse,
    )
    set_held_foreign_body_contact(
        config, preset in {
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE,
            PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        }
    )
    set_held_translational_impulse(
        config, preset in {
            PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE,
            PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        }
    )
    from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
        set_effector_work_held_load,
    )
    set_effector_work_held_load(
        config, preset in {
            PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING,
            PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        }
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        set_flat_ground_gravity,
    )
    from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
        set_free_resource_object_ground_friction,
    )
    set_free_resource_object_ground_friction(
        config, preset in {
            PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION,
            PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        }
    )
    set_flat_ground_gravity(
        config, preset in {
            PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION,
            PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        }
    )
    from mechanistic_mind.physical_system.surface_elevation_support import (
        set_surface_elevation_support,
    )
    set_surface_elevation_support(
        config, preset in {PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW}
    )
    # VW2: occupancy support/contact queries — same gate as SES (consumes VW1; does not own gravity).
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        set_occupancy_support_and_contact_queries,
    )
    set_occupancy_support_and_contact_queries(
        config, preset in {PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW}
    )
    from mechanistic_mind.physical_system.body_normal_load_traction import (
        set_body_normal_load_traction,
    )
    set_body_normal_load_traction(
        config, preset in {
            PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION,
            PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        }
    )
    from mechanistic_mind.physical_system.continuous_surface_geometry import (
        set_continuous_surface_geometry,
    )
    set_continuous_surface_geometry(
        config, preset in {PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW}
    )
    from mechanistic_mind.physical_system.body_static_traction_threshold import (
        set_body_static_traction_threshold,
    )
    set_body_static_traction_threshold(
        config, preset in {
            PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
            PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        }
    )
    from mechanistic_mind.physical_system.free_resource_object_static_traction_threshold import (
        set_free_resource_object_static_traction_threshold,
    )
    set_free_resource_object_static_traction_threshold(
        config, preset in {
            PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION,
            PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        }
    )
    from mechanistic_mind.physical_system.radius_aware_support_points import (
        set_radius_aware_support_points,
    )
    set_radius_aware_support_points(
        config, preset in {PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW}
    )
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        set_ses_decomposition_contract,
    )
    # G2C1 contract ON for G2C1 and its G2C2 child (never on G2B parent or earlier).
    set_ses_decomposition_contract(
        config, preset in {
            PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT,
            PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        }
    )
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        set_ses_runtime_transition_classifier,
    )
    # G2C2 classifier ON only for its own preset (and future descendants).
    set_ses_runtime_transition_classifier(
        config, preset in {PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW}
    )

    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        set_radius_aware_face_sweep,
    )
    # Face-sweep ON for its own preset and G2D diagnostic shadow descendant.
    set_radius_aware_face_sweep(
        config,
        preset in {
            PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP,
            PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        },
    )

    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        set_diagnostic_normal_load_shadow,
    )
    # Diagnostic shadow ON only for its own preset (and future descendants).
    set_diagnostic_normal_load_shadow(
        config,
        preset in {
            PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
            PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        },
    )

    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
        set_continuous_gravitational_pe_diagnostic_shadow,
    )
    set_continuous_gravitational_pe_diagnostic_shadow(
        config,
        preset in {
            PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW,
            PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        },
    )

    from mechanistic_mind.physical_system.continuous_gravitational_pe import (
        set_continuous_gravitational_pe,
    )
    set_continuous_gravitational_pe(
        config,
        preset in {
            PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C,
            PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
        },
    )

    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
        set_tangent_gravity_diagnostic_shadow,
    )
    set_tangent_gravity_diagnostic_shadow(
        config, preset == PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW
    )

    if preset in {
        PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
        PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
    }:
        # Single Acanthostega signal channel: OSC_EMIT is the (only) physical emitter.
        from mechanistic_mind.physical_system.oscillatory_signaling import OscillatorySignalingConfig
        if getattr(config, "oscillatory_signaling", None) is None:
            config.oscillatory_signaling = OscillatorySignalingConfig()
        config.oscillatory_signaling.mode = "EXPERIMENTAL"
    if getattr(config, "cognition", None) is not None and preset in {
        PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION,
        PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
        PRESET_ACANTHOSTEGA_WORLD_MATERIAL,
        PRESET_ACANTHOSTEGA_MULTI_CONTENT,
        PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
        PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
        PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION, PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY, PRESET_ACANTHOSTEGA_STATIC_TRACTION, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION, PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT, PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT, PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER, PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C, PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW, PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS, PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE, PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
        PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
    }:
        config.cognition.sensorimotor_consequence_model = True
    if preset in {PRESET_ACANTHOSTEGA_SURFACE_OPTICAL, PRESET_ACANTHOSTEGA_WORLD_MATERIAL, PRESET_ACANTHOSTEGA_MULTI_CONTENT, PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS, PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE, PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS}:
        nfe = getattr(config, "near_field_exteroception", None)
        if nfe is not None:
            nfe.visual_surface_discrimination = "RICH"
            nfe.mode = "EXPERIMENTAL"
            nfe.perception_enabled = True
    config.runtime_version = TIKTAALIK_RUNTIME_VERSION
    return config


def identity_for_config(config=None, *, seed: int | None = None, tick: int | None = None) -> dict[str, Any]:
    preset = getattr(config, "public_preset", None) if config is not None else None
    line = getattr(config, "model_line", None) if config is not None else None
    from mechanistic_mind.physical_system.experiment_canonical import (
        is_acanthostega_public_preset,
        normalize_preset_name,
    )

    n = normalize_preset_name(preset)
    # Preset wins over a stray model_line so incompatible pairs cannot be constructed.
    # Acanthostega public presets (including all Beta 4 children) must never resolve as Tiktaalik.
    if is_acanthostega_public_preset(n) or (
        n is None and normalize_model_line(line) == MODEL_LINE_ACANTHOSTEGA
    ):
        return acanthostega_identity.model_metadata(config, seed=seed, tick=tick)
    return identity_from_public_preset(preset, config, seed=seed, tick=tick)


def identity_for_runtime(runtime: Any) -> dict[str, Any]:
    if runtime is None:
        return identity_for_config()
    cfg = getattr(runtime, "config", None)
    return identity_for_config(
        cfg,
        seed=getattr(runtime, "seed", None),
        tick=getattr(runtime, "tick", None),
    )


def snapshot_compatibility_token(identity: dict[str, Any] | None) -> str:
    line = normalize_model_line((identity or {}).get("model_line"))
    if line == MODEL_LINE_ACANTHOSTEGA:
        return "ACANTHOSTEGA"
    return "TIKTAALIK"
