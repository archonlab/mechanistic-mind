"""Serialize PhysicalSystemRuntime state for the web Observer.

Only real fields. Missing stages become NOT AVAILABLE — never fabricated.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np

from mechanistic_mind.physical_system import PhysicalSystemRuntime, available_actions
from mechanistic_mind.ui.psychology_observer import cli as observer_cli

BOUNDARY_MODES = {
    "WRAP_PERIODIC": {
        "status": "SUPPORTED",
        "description": "Toroidal domain: opposite edges identified. Production Planet/PhysicalBody topology.",
    },
    "CLOSED": {
        "status": "UNSUPPORTED",
        "description": "No wall/reflect/clamp domain edge exists in Current MM Planet physics.",
    },
    "OPEN": {
        "status": "UNSUPPORTED",
        "description": "Spatial open edge (non-wrapping) is not implemented; would require non-toroidal operators.",
    },
}


def discover_world_fields(runtime: "PhysicalSystemRuntime") -> list[dict[str, Any]]:
    """Discover scalar/vector fields actually present on PlanetState."""
    w = runtime.world
    fields: list[dict[str, Any]] = []
    if hasattr(w, "T"):
        fields.append({"id": "T", "kind": "scalar", "source": "world.T", "label": "T"})
    if hasattr(w, "M"):
        m = w.M
        for i in range(int(m.shape[0])):
            fields.append({"id": f"M{i}", "kind": "scalar", "source": f"world.M[{i}]"})
    if hasattr(w, "vx") and hasattr(w, "vy"):
        fields.append({"id": "flow", "kind": "vector", "components": ["vx", "vy"], "source": "world.vx/vy", "label": "flow"})
        fields.append({"id": "vx", "kind": "scalar", "source": "world.vx"})
        fields.append({"id": "vy", "kind": "scalar", "source": "world.vy"})
    if hasattr(w, "u"):
        fields.append({"id": "u", "kind": "scalar", "source": "world.u"})
    if getattr(w, "R", None) is not None:
        fields.append({"id": "R", "kind": "scalar", "source": "world.R", "label": "transferable_resource"})
    if getattr(w, "R_A", None) is not None:
        fields.append({"id": "R_A", "kind": "scalar", "source": "world.R_A", "label": "RESOURCE A"})
    if getattr(w, "R_B", None) is not None:
        fields.append({"id": "R_B", "kind": "scalar", "source": "world.R_B", "label": "RESOURCE B"})
    if getattr(w, "FIELD_A", None) is not None:
        fields.append({"id": "FIELD_A", "kind": "scalar", "source": "world.FIELD_A", "label": "SIGNAL A"})
    if getattr(w, "FIELD_B", None) is not None:
        fields.append({"id": "FIELD_B", "kind": "scalar", "source": "world.FIELD_B", "label": "SIGNAL B"})
    if getattr(w, "terrain_potential", None) is not None:
        fields.append({
            "id": "terrain_potential",
            "kind": "scalar",
            "source": "world.terrain_potential",
            "label": "POTENTIAL",
            "observer_ground_truth": True,
        })
    if getattr(w, "terrain_drag", None) is not None:
        fields.append({
            "id": "terrain_drag",
            "kind": "scalar",
            "source": "world.terrain_drag",
            "label": "DRAG",
            "observer_ground_truth": True,
        })
    if getattr(w, "terrain_grad_x", None) is not None and getattr(w, "terrain_grad_y", None) is not None:
        fields.append({
            "id": "terrain_grad_mag",
            "kind": "scalar",
            "source": "world.terrain_grad_*",
            "label": "GRADIENT",
            "observer_ground_truth": True,
            "derived": True,
        })
    if getattr(w, "resource_geo_suit_A", None) is not None:
        fields.append({
            "id": "resource_geo_suit_A",
            "kind": "scalar",
            "source": "world.resource_geo_suit_A",
            "label": "R_A GEO SUIT",
            "observer_ground_truth": True,
        })
    if getattr(w, "resource_geo_suit_B", None) is not None:
        fields.append({
            "id": "resource_geo_suit_B",
            "kind": "scalar",
            "source": "world.resource_geo_suit_B",
            "label": "R_B GEO SUIT",
            "observer_ground_truth": True,
        })
    if getattr(w, "ambient_fx", None) is not None and getattr(w, "ambient_fy", None) is not None:
        fields.append({
            "id": "ambient_force",
            "kind": "vector",
            "source": "world.ambient_fx/fy",
            "label": "AMBIENT FORCE",
            "observer_ground_truth": True,
        })
        fields.append({
            "id": "ambient_magnitude",
            "kind": "scalar",
            "source": "world.ambient_fx/fy",
            "label": "AMBIENT MAGNITUDE",
            "observer_ground_truth": True,
            "derived": True,
        })
    if getattr(w, "surface_response", None) is not None:
        fields.append({
            "id": "surface_response",
            "kind": "scalar",
            "source": "world.surface_response",
            "label": "SURFACE OBSERVABLE",
            "observer_ground_truth": True,
        })
    return fields


def boundary_metadata(runtime: "PhysicalSystemRuntime") -> dict[str, Any]:
    emb = runtime.world.external_material_boundary
    return {
        "spatial_topology": "WRAP_PERIODIC",
        "spatial_topology_status": "SUPPORTED",
        "modes": BOUNDARY_MODES,
        "selected_mode": "WRAP_PERIODIC",
        "note": "Only WRAP_PERIODIC is scientifically implemented. CLOSED/OPEN spatial modes are UNSUPPORTED.",
        "external_material_boundary": {
            "enabled": bool(getattr(emb, "enabled", False)),
            "kind": "OPEN-5 material exchange (not spatial OPEN topology)",
            "config_default": bool(runtime.config.planet.external_material_boundary_enabled),
        },
        "change_policy": "Spatial topology is fixed by Planet physics. World size and material-boundary fixture require a new run (experiment apply/reset).",
    }



def _ecology_observer_ground_truth(runtime: "PhysicalSystemRuntime") -> dict[str, Any]:
    """Observer-only ecology preset + optional ACTION AUTHORITY (physical)."""
    from mechanistic_mind.physical_system.ecology_presets import ecology_metadata

    cfg = getattr(runtime, "config", None)
    meta = ecology_metadata(cfg)
    # Prefer session-attached authority if present
    auth = getattr(runtime, "_observer_action_authority", None)
    if isinstance(auth, dict):
        meta["action_authority"] = {
            "move_alignment_median": auth.get("move_alignment_median"),
            "opposing_rate": auth.get("opposing_rate"),
            "wait_disp_median": auth.get("wait_disp_median"),
            "strong_deflection_rate": auth.get("strong_deflection_rate"),
            "coupling_label": auth.get("coupling_label"),
            "note": auth.get("note"),
        }
    return meta


def _terrain_observer_block(runtime: "PhysicalSystemRuntime") -> dict[str, Any]:
    import numpy as np

    tmeta = getattr(runtime.world, "terrain_meta", None) or {}
    te = getattr(runtime.config.planet, "terrain", None)
    pot = getattr(runtime.world, "terrain_potential", None)
    drag = getattr(runtime.world, "terrain_drag", None)
    gx = getattr(runtime.world, "terrain_grad_x", None)
    gy = getattr(runtime.world, "terrain_grad_y", None)
    stats: dict[str, Any] = {}
    if pot is not None:
        pa = np.asarray(pot, dtype=np.float64)
        stats["potential_min"] = float(np.min(pa))
        stats["potential_max"] = float(np.max(pa))
    if drag is not None:
        da = np.asarray(drag, dtype=np.float64)
        stats["drag_min"] = float(np.min(da))
        stats["drag_max"] = float(np.max(da))
    if gx is not None and gy is not None:
        mag = np.hypot(np.asarray(gx, dtype=np.float64), np.asarray(gy, dtype=np.float64))
        stats["gradient_mag_min"] = float(np.min(mag))
        stats["gradient_mag_max"] = float(np.max(mag))
    return {
        "enabled": bool(getattr(te, "enabled", False)) if te is not None else False,
        "mode": str(getattr(te, "mode", "FLAT")) if te is not None else "FLAT",
        "experiment_seed": tmeta.get("experiment_seed"),
        "terrain_seed": tmeta.get("terrain_seed"),
        "terrain_seed_source": tmeta.get("terrain_seed_source"),
        "generator_version": tmeta.get("generator_version"),
        "generation_attempt": tmeta.get("generation_attempt"),
        "generation_accepted": tmeta.get("generation_accepted"),
        "generation_fallback": tmeta.get("generation_fallback"),
        "checksum": tmeta.get("checksum"),
        "config": tmeta.get("config") or (te.to_dict() if te is not None and hasattr(te, "to_dict") else None),
        "traversability_audit": tmeta.get("traversability_audit"),
        "largest_connected_traversable_frac": (tmeta.get("traversability_audit") or {}).get(
            "largest_component_frac"
        ),
        "extreme_gradient_frac": (tmeta.get("traversability_audit") or {}).get(
            "extreme_gradient_frac"
        ),
        "static": True,
        "observer_only": True,
        "panel": "OBSERVER_GROUND_TRUTH",
        "note": (
            "POTENTIAL / DRAG / GRADIENT are Observer ground truth. "
            "Not agent observation. Not semantic OBSTACLE/MOUNTAIN/TRAP."
        ),
        **stats,
    }


def _ambient_observer_block(runtime: "PhysicalSystemRuntime") -> dict[str, Any]:
    ameta = getattr(runtime.world, "ambient_meta", None) or {}
    ae = getattr(runtime.config.planet, "ambient", None)
    fx = getattr(runtime.world, "ambient_fx", None)
    fy = getattr(runtime.world, "ambient_fy", None)
    stats: dict[str, Any] = {}
    if fx is not None and fy is not None:
        import numpy as np

        fa = np.asarray(fx, dtype=np.float64)
        fb = np.asarray(fy, dtype=np.float64)
        mag = np.hypot(fa, fb)
        stats = {
            "fx_min": float(np.min(fa)),
            "fx_max": float(np.max(fa)),
            "fy_min": float(np.min(fb)),
            "fy_max": float(np.max(fb)),
            "magnitude_min": float(np.min(mag)),
            "magnitude_max": float(np.max(mag)),
            "magnitude_mean": float(np.mean(mag)),
        }
    return {
        "enabled": bool(getattr(ae, "enabled", False)) if ae is not None else False,
        "experiment_seed": ameta.get("experiment_seed"),
        "ambient_seed": ameta.get("ambient_seed"),
        "ambient_seed_source": ameta.get("ambient_seed_source"),
        "generator_version": ameta.get("generator_version"),
        "checksum": ameta.get("checksum"),
        "config": ameta.get("config") or (ae.to_dict() if ae is not None and hasattr(ae, "to_dict") else None),
        "static": True,
        "observer_only": True,
        "panel": "OBSERVER_GROUND_TRUTH",
        "note": (
            "AMBIENT FORCE is Observer ground truth. Physical vector field only. "
            "Not agent observation. Not semantic WIND/CURRENT/ROUTE."
        ),
        **stats,
    }


def _climate_observer_ground_truth(runtime: "PhysicalSystemRuntime") -> dict[str, Any]:
    """Experimenter-only cycle phase. Never copied into agent_observation."""
    from mechanistic_mind.planet.climate_ecology import observer_climate_ground_truth

    ce = getattr(runtime.config.planet, "climate_ecology", None)
    ecology = _ecology_observer_ground_truth(runtime)
    terrain = _terrain_observer_block(runtime)
    ambient = _ambient_observer_block(runtime)
    if ce is None:
        return {
            "enabled": False,
            "panel": "OBSERVER_GROUND_TRUTH_EXPERIMENT",
            "ecology_preset": ecology.get("ecology_preset"),
            "ecology_ui_label": ecology.get("ui_label"),
            "action_authority": ecology.get("action_authority"),
            "climate_ecology_enabled": False,
            "resource_ecology_A_enabled": False,
            "resource_ecology_B_enabled": False,
            "passive_reservoir_trickle": ecology.get("passive_reservoir_trickle"),
            "body_orientation_force_scale": ecology.get("body_orientation_force_scale"),
            "ecology": ecology,
            "terrain": terrain,
            "ambient": ambient,
        }
    out = observer_climate_ground_truth(
        ce,
        int(runtime.world.tick),
        seed=int(runtime.seed),
        T=runtime.world.T,
        R_A=getattr(runtime.world, "R_A", None),
        R_B=getattr(runtime.world, "R_B", None),
    )
    out["ecology_preset"] = ecology.get("ecology_preset")
    out["ecology_ui_label"] = ecology.get("ui_label")
    out["action_authority"] = ecology.get("action_authority")
    out["climate_ecology_enabled"] = bool(getattr(ce, "enabled", False))
    out["resource_ecology_A_enabled"] = bool(getattr(ce, "resource_ecology_A_enabled", True))
    out["resource_ecology_B_enabled"] = bool(getattr(ce, "resource_ecology_B_enabled", True))
    out["passive_reservoir_trickle"] = ecology.get("passive_reservoir_trickle")
    out["body_orientation_force_scale"] = ecology.get("body_orientation_force_scale")
    out["ecology"] = ecology
    out["terrain"] = terrain
    out["ambient"] = ambient
    # EFFECTIVE WORLD (CLIMATE_AUTHORITY_AUDIT_01) — Observer GT only.
    try:
        from mechanistic_mind.research.climate_authority import (
            effective_world_configuration,
            effective_world_fingerprint,
        )
        eff = effective_world_configuration(runtime)
        out["effective_world"] = {
            **{k: eff[k] for k in (
                "requested_preset", "normalized_preset",
                "climate_package_implies_climate", "climate_ablated",
                "subsystems", "overrides", "authority",
            ) if k in eff},
            "world_fingerprint": effective_world_fingerprint(eff),
            "panel": "EFFECTIVE_WORLD_OBSERVER_GT",
        }
    except Exception as exc:  # noqa: BLE001 — Observer must not crash on GT helper
        out["effective_world"] = {"error": str(exc), "panel": "EFFECTIVE_WORLD_OBSERVER_GT"}
    # Lightweight temporal calibration panel (Observer GT only).
    period = int(out.get("environmental_cycle_period") or getattr(ce, "season_period", 0) or 0)
    vx = float(np.mean(np.abs(runtime.world.vx))) if getattr(runtime.world, "vx", None) is not None else 0.0
    vy = float(np.mean(np.abs(runtime.world.vy))) if getattr(runtime.world, "vy", None) is not None else 0.0
    out["thermal_flow_mean_abs"] = float((vx ** 2 + vy ** 2) ** 0.5)
    out["body_climate_timescale_ratio_proxy"] = (
        float(period) / 6.0 if period else None
    )  # T_cell≈6 from WORLD_TIMESCALE_CALIBRATION_01; diagnostic only
    out["temporal_panel"] = {
        "season_period": period,
        "phase": out.get("environmental_cycle_phase"),
        "phase_velocity_per_tick": out.get("phase_velocity_per_tick"),
        "ticks_per_full_cycle": out.get("ticks_per_full_cycle"),
        "F_fast_period": int(getattr(runtime.config.planet, "F_fast_period", 0) or 0),
        "F_slow_period": int(getattr(runtime.config.planet, "F_slow_period", 0) or 0),
        "note": "Observer temporal diagnostics — never copied into cognition.",
    }
    return out


def _grid(arr: np.ndarray, *, max_side: int = 64) -> list[list[float]]:
    a = np.asarray(arr, dtype=np.float64)
    if a.ndim != 2:
        raise ValueError("expected 2D grid")
    h, w = a.shape
    if max(h, w) > max_side:
        # block-average downsample for transport only
        sh, sw = max(1, h // max_side), max(1, w // max_side)
        nh, nw = h // sh, w // sw
        a = a[: nh * sh, : nw * sw].reshape(nh, sh, nw, sw).mean(axis=(1, 3))
    return [[float(v) for v in row] for row in a.tolist()]


def _flat_grid(arr: np.ndarray, *, max_side: int = 64) -> dict[str, Any]:
    """Compact JSON-friendly row-major grid (OBS-05).

    One ravel().tolist() — do not build a nested row list and flatten it.
    Values match _grid row-major order.
    """
    a = np.asarray(arr, dtype=np.float64)
    if a.ndim != 2:
        raise ValueError("expected 2D grid")
    h, w = a.shape
    if max(h, w) > max_side:
        sh, sw = max(1, h // max_side), max(1, w // max_side)
        nh, nw = h // sh, w // sw
        a = a[: nh * sh, : nw * sw].reshape(nh, sh, nw, sw).mean(axis=(1, 3))
        h, w = a.shape
    return {"h": int(h), "w": int(w), "data": a.ravel().tolist()}


def _mat3(m: np.ndarray, *, max_side: int = 64) -> list[list[list[float]]]:
    m = np.asarray(m, dtype=np.float64)
    return [_grid(m[i], max_side=max_side) for i in range(int(m.shape[0]))]


def observer_agent_id(runtime: PhysicalSystemRuntime) -> str:
    """Canonical observer identity: agent_N | undercover (never a body id)."""
    from mechanistic_mind.ui.psy_observer_web.undercover_identity import slot_agent_body_ids

    slots = getattr(runtime, "slots", None)
    if slots:
        idx = int(getattr(runtime, "selected_index", 0) or 0) % len(slots)
        aid, _ = slot_agent_body_ids(idx, experimenter_slot=getattr(runtime, "experimenter_slot", None))
        return aid
    return "agent_0"


def observer_body_id(runtime: PhysicalSystemRuntime) -> str:
    """Body identity mapped from selected agent — distinct from agent_id."""
    from mechanistic_mind.ui.psy_observer_web.undercover_identity import slot_agent_body_ids

    slots = getattr(runtime, "slots", None)
    if slots:
        idx = int(getattr(runtime, "selected_index", 0) or 0) % len(slots)
        _, bid = slot_agent_body_ids(idx, experimenter_slot=getattr(runtime, "experimenter_slot", None))
        return bid
    return "body-0"


def agent_body_mapping(runtime: PhysicalSystemRuntime) -> list[dict[str, Any]]:
    from mechanistic_mind.ui.psy_observer_web.undercover_identity import slot_agent_body_ids

    slots = getattr(runtime, "slots", None)
    if not slots:
        return [{
            "agent_id": "agent_0",
            "body_id": "body-0",
            "agent_seed": int(getattr(runtime, "seed", 0)),
        }]
    exp_slot = getattr(runtime, "experimenter_slot", None)
    out = []
    for i, slot in enumerate(slots):
        aid, bid = slot_agent_body_ids(i, experimenter_slot=exp_slot)
        out.append({
            "agent_id": aid,
            "body_id": bid,
            "agent_seed": int(getattr(slot, "seed", runtime.seed)),
            "experimenter_controlled": bool(exp_slot is not None and i == int(exp_slot)),
            "cognition_attached": bool(
                getattr(getattr(slot, "config", None), "cognition", None)
                and getattr(slot.config.cognition, "cognition_enabled", False)
            ),
        })
    return out


def header_info(runtime: PhysicalSystemRuntime, *, status: str, mode: str, target_tick: int | None) -> dict[str, Any]:
    from mechanistic_mind.model.lines import snapshot_compatibility_token
    from mechanistic_mind.model.tiktaalik import OBSERVER_API_VERSION, display_name

    contract = observer_cli.headless_contract()
    model = runtime.model_identity() if hasattr(runtime, "model_identity") else {}
    agent_id = observer_agent_id(runtime)
    body_id = observer_body_id(runtime)
    slots = getattr(runtime, "slots", None)
    selected_slot = slots[int(getattr(runtime, "selected_index", 0) or 0)] if slots else runtime
    return {
        "application": "Psy Observer",
        "mm_version": str(contract.get("version", "unknown")),
        "runtime_model": "TwoAgentRuntime" if slots else "PhysicalSystemRuntime",
        "experiment": model.get("display_name") or display_name(),
        "model_family": model.get("model_family"),
        "model_version": model.get("model_version"),
        "model_line": model.get("model_line") or "TIKTAALIK",
        "model_codename": model.get("model_codename"),
        "model_display_name": model.get("display_name"),
        "public_preset": model.get("public_preset") or getattr(getattr(runtime, "config", None), "public_preset", None),
        "runtime_classification": model.get("classification"),
        "canonical": model.get("canonical"),
        "experimental_overrides": model.get("experimental_overrides") or {},
        "seed": int(runtime.seed),
        "inspected_agent_seed": int(getattr(selected_slot, "seed", runtime.seed)),
        "tick": int(runtime.tick),
        "target_tick": target_tick,
        "status": status,
        "mode": mode,
        "selected_agent_id": agent_id,
        "selected_agent": agent_id,  # canonical; body id is separate
        "selected_body_id": body_id,
        "agent_body_mapping": agent_body_mapping(runtime),
        "agent_count": len(slots or [runtime]),
        "world_mode": "two_agent" if slots else "single_agent",
        "canonical_current_runtime": contract.get("canonical_current_runtime"),
        "observer_web_version": OBSERVER_API_VERSION,
        "boundary_topology": "WRAP_PERIODIC",
        "world_size": {"width": int(runtime.config.planet.width), "height": int(runtime.config.planet.height)},
        "snapshot_compatibility": snapshot_compatibility_token(model),
        "ecology_preset": getattr(runtime.config, "ecology_preset", "CURRENT") or "CURRENT",
        "locomotion_profile": (
            "ACANTHOSTEGA_GENTLE"
            if str(getattr(getattr(runtime.config, "locomotion_profile", None), "active_name", "") or "")
            == "ACANTHOSTEGA_GENTLE"
            else "TIKTAALIK"
        ),
        "gentle_terrain_locomotion": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "locomotion_profile", None), "enabled", False))
        ),
        "physical_resource_objects": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "physical_resource_objects", None), "enabled", False))
        ),
        "physical_resource_object_vision": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "physical_resource_object_vision", None), "enabled", False))
        ),
        "single_physical_manipulator": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "single_physical_manipulator", None), "enabled", False))
        ),
        "physical_grasp_release": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "physical_grasp_release", None), "enabled", False))
        ),
        "bilateral_physical_manipulators": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "bilateral_physical_manipulators", None), "enabled", False))
        ),
        "bilateral_grasp_release": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "bilateral_grasp_release", None), "enabled", False))
        ),
        "passive_material_properties": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "passive_material_properties", None), "enabled", False))
        ),
        "explicit_surface_deposition": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "explicit_surface_deposition", None), "enabled", False))
        ),
        "surface_affinity_traction": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "surface_affinity_traction", None), "enabled", False))
        ),
        "surface_traction_experience_bridge": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "surface_traction_experience", None), "enabled", False))
        ),
        "surface_traction_prediction_adaptation": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "surface_traction_prediction", None), "enabled", False))
        ),
        "sensorimotor_consequence_model": bool(
            getattr(getattr(runtime.config, "cognition", None), "sensorimotor_consequence_model", False)
        ),
        "physical_surface_optical_coating": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "physical_surface_optical_coating", None), "enabled", False))
        ),
        "world_material_transactions": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "world_material_transactions", None), "enabled", False))
        ),
        "multi_content_spatial_index": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "multi_content_spatial_index", None), "enabled", False))
        ),
        "procedural_surface_columns": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "procedural_surface_columns", None), "enabled", False))
        ),
        "volumetric_world_material_occupancy": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "volumetric_world_material_occupancy", None), "enabled", False))
        ),
        "occupancy_support_and_contact_queries": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "occupancy_support_and_contact_queries", None), "enabled", False))
        ),
        "volumetric_world_material_separation": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "volumetric_world_material_separation", None), "enabled", False))
        ),
        "volumetric_world_material_reintegration": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "volumetric_world_material_reintegration", None), "enabled", False))
        ),
        "effector_held_occupancy_exertion_bridge": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "effector_held_occupancy_exertion_bridge", None), "enabled", False))
        ),
        "minimal_vision_3d_geometric_interface": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "minimal_vision_3d_geometric_interface", None), "enabled", False))
        ),
        "observer_camera_occupancy_consumer": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "volumetric_world_material_occupancy", None), "enabled", False))
        ),
        "conservative_surface_column_transfer": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "conservative_surface_column_transfer", None), "enabled", False))
        ),
        "local_physical_signal_transport": bool(
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "local_physical_signal_transport", None), "enabled", False))
        ),
        **({"physical_contact_acoustic_emission": True} if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "physical_contact_acoustic_emission", None), "enabled", False))
        ) else {}),
        **({"physical_resource_object_pair_contact": True} if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "physical_resource_object_pair_contact", None), "enabled", False))
        ) else {}),
        **({"held_resource_object_foreign_body_contact": True} if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "held_resource_object_foreign_body_contact", None), "enabled", False))
        ) else {}),
        **({"held_resource_object_translational_impulse_mediation": True} if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "held_resource_object_translational_impulse_mediation", None), "enabled", False))
        ) else {}),
        **({"resource_object_pair_impact_acoustic_emission": True} if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "resource_object_pair_impact_acoustic_emission", None), "enabled", False))
        ) else {}),
        **({"resource_object_pair_contact_impulse": True} if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "resource_object_pair_contact_impulse", None), "enabled", False))
        ) else {}),
        **({"body_resource_object_impact_acoustic_emission": True} if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "body_resource_object_impact_acoustic_emission", None), "enabled", False))
        ) else {}),
        **({"free_resource_object_kinematics": True} if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "free_resource_object_kinematics", None), "enabled", False))
        ) else {}),
    }


def _spatial_contents_payload(world: Any) -> dict[str, Any]:
    index = getattr(world, "spatial_contents", None)
    cells = []
    if index is not None:
        for (cell_x, cell_y), bucket in sorted(index.by_cell.items()):
            refs = sorted(bucket, key=lambda item: (item.entity_kind, item.entity_id))
            cells.append({
                "cell_x": int(cell_x),
                "cell_y": int(cell_y),
                "physical_contents": len(refs),
                "refs": [ref.as_dict() for ref in refs],
            })
    return {
        "spatial_cell_contents": cells,
        "spatial_index_generation": int(getattr(index, "generation", 0) or 0),
        "spatial_index_dirty": bool(getattr(index, "dirty", False)),
        "spatial_index_checksum": str(getattr(world, "spatial_index_checksum", "") or ""),
        "spatial_contents_researcher_only": True,
        "spatial_contents_not_agent_accessible": True,
        "spatial_contents_note": "co-location is not collision. no vertical ordering.",
    }


def _researcher_resource_objects(
    world: Any,
    *,
    object_vision_enabled: bool = False,
    passive_properties_enabled: bool = False,
    optical_profile_enabled: bool = False,
) -> list[dict[str, Any]]:
    """Observer GT only. Never copied into agent observation."""
    from mechanistic_mind.physical_system.resource_objects import ResourceObject, ensure_resource_object_state
    from mechanistic_mind.planet.topology import wrap_coord

    objs = ensure_resource_object_state(world)
    h = int(getattr(world, "T").shape[0]) if getattr(world, "T", None) is not None else 32
    w = int(getattr(world, "T").shape[1]) if getattr(world, "T", None) is not None else 32
    out = []
    for obj in objs:
        rec = obj.to_dict() if isinstance(obj, ResourceObject) else dict(obj)
        x = float(rec.get("x") or 0.0)
        y = float(rec.get("y") or 0.0)
        rec["cell"] = [int(wrap_coord(int(np.floor(y)), h)), int(wrap_coord(int(np.floor(x)), w))]
        rec["researcher_only"] = True
        rec["agent_accessible"] = False
        rec["kind"] = "PHYSICAL_RESOURCE_OBJECT"
        rec["agent_optical_contribution_enabled"] = bool(object_vision_enabled)
        rec["researcher_overlay_independent_of_illumination"] = True
        rec["optical_note"] = (
            "researcher overlay is not agent optics; "
            "agent contribution uses existing anonymous near-field channels when enabled"
        )
        if getattr(world, "free_object_kinematics_state", None) is not None:
            # Derived researcher view of the authoritative object velocity (renderer never writes back).
            _vx, _vy = float(rec.get("vx") or 0.0), float(rec.get("vy") or 0.0)
            _st = str(rec.get("physical_state") or "")
            rec["speed"] = float(np.hypot(_vx, _vy))
            rec["motion_status"] = "MOVING" if _st == "FREE_MOVING" else ("HELD" if _st == "HELD" else "FREE_REST")
            rec["collision_physics"] = "NOT_IMPLEMENTED"
        if str(rec.get("physical_state") or "") == "HELD":
            hid = rec.get("holder_body_id") or "unknown"
            mid = rec.get("manipulator_id") or "manipulator_0"
            rec["held_overlay_label"] = f"HELD by {hid}/{mid}"
        if passive_properties_enabled:
            from mechanistic_mind.physical_system.passive_material_properties import (
                researcher_property_readout,
            )
            rec["passive_material_properties"] = researcher_property_readout(rec.get("composition"))
            rec["passive_material_properties_access"] = "researcher-only"
            rec["passive_material_properties_agent_accessible"] = False
        if optical_profile_enabled:
            from mechanistic_mind.physical_system.physical_optical_material_profile import (
                researcher_profile_readout,
            )
            rec["physical_optical_material_profile"] = researcher_profile_readout(rec.get("composition"))
            rec["physical_optical_material_profile_access"] = "researcher-only"
            rec["physical_optical_material_profile_agent_accessible"] = False
            rec["physical_optical_material_profile_label"] = (
                "MATERIAL PROPERTY ONLY · NO PHYSICAL LIGHT TRANSPORT · NOT DISPLAY RGB"
            )
        # Researcher-only size-geometry readout (does not leak to cognition).
        prov = rec.get("provenance") if isinstance(rec.get("provenance"), dict) else {}
        if prov.get("size_geometry_profile") or prov.get("size_geometry_final_radius") is not None:
            rec["size_geometry"] = {
                "profile_version": prov.get("size_geometry_profile"),
                "geometry_model": prov.get("size_geometry_model"),
                "clamp_status": prov.get("size_geometry_clamp_status"),
                "scope_classification": prov.get("size_geometry_scope"),
                "quantity": prov.get("size_geometry_quantity"),
                "raw_radius": prov.get("size_geometry_raw_radius"),
                "final_radius": prov.get("size_geometry_final_radius"),
                "quantity_ref": prov.get("size_geometry_quantity_ref"),
                "radius_ref": prov.get("size_geometry_radius_ref"),
                "exponent": prov.get("size_geometry_exponent"),
                "collision_radius": rec.get("collision_radius"),
                "optical_radius": rec.get("optical_radius"),
                "vertical_half_extent": rec.get("vertical_half_extent"),
                "size_mutable_after_creation": False,
                "optical_radius_unchanged": True,
                "post_creation_resizing_disabled": True,
                "researcher_only": True,
                "agent_accessible": False,
            }
        out.append(rec)
    return out


def _researcher_manipulators(runtime: Any) -> list[dict[str, Any]]:
    """Observer GT effector/reach. Not agent observation."""
    from mechanistic_mind.physical_system.physical_manipulator import (
        BILATERAL_IDS,
        MANIP_LEFT,
        MANIP_RIGHT,
        MANIPULATOR_ID,
        CANONICAL_GRASP_RADIUS,
        CANONICAL_LATERAL_OFFSET,
        effector_world_xy,
        held_object_for_holder,
        bilateral_manipulator_is_active,
        bring_together_is_active,
        manipulator_is_active,
        world_manipulators_active,
    )

    slots = list(getattr(runtime, "slots", None) or [runtime])
    out = []
    for i, slot in enumerate(slots):
        cfg = getattr(slot, "config", None)
        if not world_manipulators_active(cfg):
            continue
        world = getattr(slot, "world", None) or getattr(runtime, "world", None)
        t = getattr(world, "T", None)
        h = int(t.shape[0]) if t is not None else 32
        w = int(t.shape[1]) if t is not None else 32
        bid = str(getattr(slot, "technical_id", None) or f"agent_{i}")
        rec_m = getattr(slot, "last_manipulator_receipt", None) or {}
        if bilateral_manipulator_is_active(cfg):
            bcfg = getattr(cfg, "bilateral_physical_manipulators", None)
            hands = rec_m.get("hands") if isinstance(rec_m.get("hands"), dict) else {}
            for mid in BILATERAL_IDS:
                ex, ey = effector_world_xy(
                    slot.body, width=w, height=h, config=cfg, manipulator_id=mid, runtime=slot,
                )
                held = held_object_for_holder(world, bid, mid)
                hrec = hands.get(mid) or {}
                out.append({
                    "body_id": bid,
                    "manipulator_id": mid,
                    "side": mid,
                    "effector_x": ex,
                    "effector_y": ey,
                    "grasp_radius": float(getattr(bcfg, "grasp_radius", CANONICAL_GRASP_RADIUS) or CANONICAL_GRASP_RADIUS),
                    "forward_offset": float(getattr(bcfg, "forward_offset", 0.55) or 0.55),
                    "lateral_offset": float(getattr(bcfg, "lateral_offset", CANONICAL_LATERAL_OFFSET) or CANONICAL_LATERAL_OFFSET),
                    "heading_authority": "body.theta",
                    "occupied": held is not None,
                    "held_object_id": str(held.object_id) if held is not None else None,
                    "last_event": hrec.get("event") or rec_m.get("event"),
                    "last_manipulator_action": hrec.get("manipulator_action"),
                    "researcher_only": True,
                })
            if bring_together_is_active(cfg):
                from mechanistic_mind.physical_system.physical_manipulator import (
                    open_pair_aperture,
                    pair_min_aperture,
                    object_center_distance,
                )
                from mechanistic_mind.physical_system.resource_objects import clip_interaction_radius
                left_o = held_object_for_holder(world, bid, MANIP_LEFT)
                right_o = held_object_for_holder(world, bid, MANIP_RIGHT)
                dist = None
                if left_o is not None and right_o is not None and str(left_o.object_id) != str(right_o.object_id):
                    dist = object_center_distance(left_o, right_o, width=w, height=h)
                pair_rec = getattr(slot, "last_pair_receipt", None) or {}
                open_ap = open_pair_aperture(cfg)
                min_ap = pair_min_aperture(world, bid, cfg)
                out.append({
                    "body_id": bid,
                    "kind": "pair_state",
                    "aperture": float(getattr(slot, "pair_aperture", open_ap) or open_ap),
                    "open_aperture": float(open_ap),
                    "min_aperture": float(min_ap),
                    "pair_state": str(getattr(slot, "pair_state", "OPEN") or "OPEN"),
                    "contact": bool(getattr(slot, "pair_contact", False)),
                    "surface_distance": dist,
                    "left_held": left_o is not None,
                    "right_held": right_o is not None,
                    "left_interaction_radius": clip_interaction_radius(getattr(left_o, "interaction_radius", 0.2)) if left_o else None,
                    "right_interaction_radius": clip_interaction_radius(getattr(right_o, "interaction_radius", 0.2)) if right_o else None,
                    "last_pair_receipt": pair_rec,
                    "last_material_transformation_receipt": getattr(slot, "last_material_transformation_receipt", None),
                    "mixing": bool((getattr(slot, "last_material_transformation_receipt", None) or {}).get("outcome") == "MERGE_COMMITTED"),
                    "researcher_only": True,
                })
            continue
        if not manipulator_is_active(cfg):
            continue
        mid = str(getattr(getattr(cfg, "single_physical_manipulator", None), "manipulator_id", None) or MANIPULATOR_ID)
        ex, ey = effector_world_xy(slot.body, width=w, height=h, config=cfg)
        held = held_object_for_holder(world, bid, mid)
        out.append({
            "body_id": bid,
            "manipulator_id": mid,
            "effector_x": ex,
            "effector_y": ey,
            "grasp_radius": float(getattr(cfg.single_physical_manipulator, "grasp_radius", 0.4)),
            "forward_offset": float(getattr(cfg.single_physical_manipulator, "forward_offset", 0.55)),
            "heading_authority": "body.theta",
            "occupied": held is not None,
            "held_object_id": str(held.object_id) if held is not None else None,
            "last_event": rec_m.get("event"),
            "last_manipulator_action": rec_m.get("manipulator_action"),
            "researcher_only": True,
        })
    return out


def _o3a_optical_surfaces_world_payload(runtime: "PhysicalSystemRuntime", world: Any, cfg: Any) -> dict[str, Any]:
    from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
        object_body_held_optical_surfaces_is_active,
        researcher_summary,
    )
    from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

    if not object_body_held_optical_surfaces_is_active(cfg):
        return {}
    bodies = body_refs_for_runtime(runtime)
    return {
        "object_body_held_optical_surfaces": researcher_summary(world, cfg, bodies=bodies),
        "object_body_held_optical_surfaces_researcher_only": True,
    }


def _o4_optical_reception_world_payload(runtime: "PhysicalSystemRuntime", world: Any, cfg: Any) -> dict[str, Any]:
    from mechanistic_mind.physical_system.organism_physical_optical_reception import (
        organism_physical_optical_reception_is_active,
        researcher_summary,
    )

    if not organism_physical_optical_reception_is_active(cfg):
        return {}
    return {
        "organism_physical_optical_reception": researcher_summary(world, cfg),
        "organism_physical_optical_reception_researcher_only": True,
    }


def _o5_temporal_alignment_world_payload(runtime: "PhysicalSystemRuntime", world: Any, cfg: Any) -> dict[str, Any]:
    from mechanistic_mind.physical_system.sensory_modality_temporal_alignment import (
        note_observer_poll_skip,
        researcher_summary,
        sensory_modality_temporal_alignment_is_active,
    )

    if not sensory_modality_temporal_alignment_is_active(cfg):
        return {}
    # Passive poll: never create envelopes
    note_observer_poll_skip(world)
    return {
        "sensory_modality_temporal_alignment": researcher_summary(world, cfg),
        "sensory_modality_temporal_alignment_researcher_only": True,
    }



def _vw7_volume_consumer_world_payload(
    runtime: "PhysicalSystemRuntime",
    *,
    want: bool,
) -> dict[str, Any]:
    """VW7 researcher volume payload — gated by P1 derived subscription; P2 incremental."""
    if not want:
        try:
            from mechanistic_mind.physical_system.beta4_performance_benchmark import (
                count as _b4p_count,
                is_enabled as _b4p_on,
            )
            if _b4p_on():
                _b4p_count("volume_payload_omitted")
        except Exception:
            pass
        return {}
    if getattr(runtime.config, "model_line", "") != "ACANTHOSTEGA":
        return {}
    if not bool(getattr(getattr(runtime.config, "volumetric_world_material_occupancy", None), "enabled", False)):
        return {}
    held = getattr(runtime, "_observer_volume_held_static_id", None)
    payload = __import__(
        "mechanistic_mind.physical_system.observer_camera_occupancy_consumer",
        fromlist=["researcher_payload"],
    ).researcher_payload(
        runtime,
        held_static_payload_id=str(held) if held else None,
        prefer_incremental=True,
    )
    try:
        desc = payload.get("observer_camera_occupancy_consumer") or {}
        sid = desc.get("static_payload_id")
        kind = desc.get("incremental_wire_kind")
        inc = desc.get("observer_volume_incremental") or {}
        if sid and (kind in ("FULL", "RESET", None) or inc.get("volume_static")):
            if kind == "FULL" or (isinstance(inc, dict) and inc.get("volume_static")):
                setattr(runtime, "_observer_volume_held_static_id", str(sid))
        elif kind == "DYNAMIC" and sid:
            setattr(runtime, "_observer_volume_held_static_id", str(sid))
    except Exception:
        pass
    return payload


def _o6_optical_audit_world_payload(
    runtime: "PhysicalSystemRuntime",
    world: Any,
    cfg: Any,
    *,
    want: bool = True,
) -> dict[str, Any]:
    from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
        exposed_surface_optical_interaction_authority_is_active,
    )
    from mechanistic_mind.physical_system.researcher_physical_optical_audit_view import (
        researcher_summary,
    )

    if not want:
        try:
            from mechanistic_mind.physical_system.beta4_performance_benchmark import (
                count as _b4p_count,
                is_enabled as _b4p_on,
            )
            if _b4p_on():
                _b4p_count("surface_payload_omitted")
        except Exception:
            pass
        return {}
    if not exposed_surface_optical_interaction_authority_is_active(cfg):
        return {}
    held = getattr(runtime, "_observer_surface_held_static_id", None)
    # Passive poll: read-only summary (+ cached columnar display); never mutates physics.
    summary = researcher_summary(
        world,
        cfg,
        runtime=runtime,
        held_static_payload_id=str(held) if held else None,
        prefer_incremental=True,
    )
    # Optimistic: after emitting a full/reset base, remember static id for next DYNAMIC wire.
    try:
        sid = summary.get("static_payload_id")
        kind = summary.get("incremental_wire_kind")
        if sid and kind in ("FULL", "RESET", None):
            # Only advance held id when we actually sent static geometry.
            inc = summary.get("observer_surface_incremental") or {}
            if kind == "FULL" or (isinstance(inc, dict) and inc.get("surface_static")):
                setattr(runtime, "_observer_surface_held_static_id", str(sid))
        elif kind == "DYNAMIC" and sid:
            setattr(runtime, "_observer_surface_held_static_id", str(sid))
    except Exception:
        pass
    return {
        "researcher_physical_optical_audit_view": summary,
        "researcher_physical_optical_audit_view_researcher_only": True,
    }


def _acanthostega_beta4_capability_payload(runtime: "PhysicalSystemRuntime") -> dict[str, Any] | None:
    """Researcher-only complete Beta 4.0 capability summary (not public stage toggles)."""
    cfg = runtime.config
    preset = str(getattr(cfg, "public_preset", "") or "").upper()
    is_public_beta4 = preset in {"ACANTHOSTEGA_BETA4", "ACANTHOSTEGA_BETA4_0"}
    is_vw7_fixture = "VOLUMETRIC_WORLD_VW7" in preset
    if not is_public_beta4 and not is_vw7_fixture:
        return None
    if getattr(cfg, "model_line", "") != "ACANTHOSTEGA":
        return None
    if not bool(getattr(getattr(cfg, "volumetric_world_material_occupancy", None), "enabled", False)):
        return None
    stages = {
        "VW1_occupancy": bool(getattr(getattr(cfg, "volumetric_world_material_occupancy", None), "enabled", False)),
        "VW2_support_contact": bool(getattr(getattr(cfg, "occupancy_support_and_contact_queries", None), "enabled", False)),
        "VW3_separation": bool(getattr(getattr(cfg, "volumetric_world_material_separation", None), "enabled", False)),
        "VW4_reintegration_transaction": bool(getattr(getattr(cfg, "volumetric_world_material_reintegration", None), "enabled", False)),
        "VW5_effector_bridge": bool(getattr(getattr(cfg, "effector_held_occupancy_exertion_bridge", None), "enabled", False)),
        "VW6_minimal_vision_3d": bool(getattr(getattr(cfg, "minimal_vision_3d_geometric_interface", None), "enabled", False)),
        "VW7_observer_consumer": bool(getattr(getattr(cfg, "volumetric_world_material_occupancy", None), "enabled", False)),
        "free_space_v1a": bool(getattr(getattr(cfg, "free_space_state_and_pe_authority_contract", None), "enabled", False)),
        "free_space_v1b": bool(getattr(getattr(cfg, "vertical_terrain_landing_contact_response", None), "enabled", False)),
        "free_space_v1c": bool(getattr(getattr(cfg, "vertical_impact_acoustic_emission", None), "enabled", False)),
        "free_space_v1d": bool(getattr(getattr(cfg, "release_and_excavation_support_loss_integration", None), "enabled", False)),
        "V1D_release_excavation": bool(getattr(getattr(cfg, "release_and_excavation_support_loss_integration", None), "enabled", False)),
        "O1_physical_optical_material_profile": bool(
            getattr(getattr(cfg, "physical_optical_material_profile", None), "enabled", False)
        ),
        "O2_exposed_surface_optical_interaction_authority": bool(
            getattr(getattr(cfg, "exposed_surface_optical_interaction_authority", None), "enabled", False)
        ),
        "O3_abstract_spectral_light_source_and_direct_transport": bool(
            getattr(getattr(cfg, "abstract_spectral_light_source_and_direct_transport", None), "enabled", False)
        ),
        "O3A_object_body_held_optical_surfaces": bool(
            getattr(getattr(cfg, "object_body_held_optical_surfaces", None), "enabled", False)
        ),
        "O4_organism_physical_optical_reception": bool(
            getattr(getattr(cfg, "organism_physical_optical_reception", None), "enabled", False)
        ),
        "O5_sensory_modality_temporal_alignment": bool(
            getattr(getattr(cfg, "sensory_modality_temporal_alignment", None), "enabled", False)
        ),
        "O6_researcher_physical_optical_audit_view": bool(
            getattr(getattr(cfg, "exposed_surface_optical_interaction_authority", None), "enabled", False)
        ),
    }
    if is_public_beta4:
        banner = (
            "Acanthostega Beta 4.0\n"
            f"- volumetric occupancy: {'active' if stages['VW1_occupancy'] else 'inactive'}\n"
            f"- free-space vertical dynamics: {'active' if stages['free_space_v1d'] else 'inactive'}\n"
            f"- physical support/contact: {'active' if stages['VW2_support_contact'] else 'inactive'}\n"
            f"- conservative material transactions: {'active' if stages['VW3_separation'] else 'inactive'}\n"
            f"- organism volumetric interaction: {'active' if stages['VW5_effector_bridge'] else 'inactive'}\n"
            f"- organism XYZ vision: {'active' if stages['VW6_minimal_vision_3d'] else 'inactive'}\n"
            f"- MAP / 2D and VOLUME / 3D: {'available' if stages['VW7_observer_consumer'] else 'unavailable'}\n"
            "- held→world incorporation trigger: not yet implemented"
        )
        return {
            "acanthostega_beta4_capability": {
                "schema": "ACANTHOSTEGA_BETA4_CAPABILITY_STATUS_V1",
                "researcher_only": True,
                "public_preset": str(getattr(cfg, "public_preset", "") or ""),
                "model_line": str(getattr(cfg, "model_line", "") or ""),
                "visibility_class": "PUBLIC_MODEL",
                "stages": stages,
                "VW7_is_physical_mechanism": False,
                "held_to_world_physical_trigger": "BLOCKED",
                "authority": "AUTHORITATIVE_WORLD_MATERIAL_OCCUPANCY_ABSOLUTE_Z",
                "banner": banner,
            }
        }
    banner = (
        "VOLUMETRIC WORLD\n"
        f"VW1 occupancy: {'ACTIVE' if stages['VW1_occupancy'] else 'INACTIVE'}\n"
        f"VW2 support/contact: {'ACTIVE' if stages['VW2_support_contact'] else 'INACTIVE'}\n"
        f"VW3 separation: {'ACTIVE' if stages['VW3_separation'] else 'INACTIVE'}\n"
        f"VW4 reintegration transaction: {'ACTIVE' if stages['VW4_reintegration_transaction'] else 'INACTIVE'}\n"
        f"VW5 effector bridge: {'ACTIVE' if stages['VW5_effector_bridge'] else 'INACTIVE'}\n"
        f"VW6 physical XYZ vision: {'ACTIVE' if stages['VW6_minimal_vision_3d'] else 'INACTIVE'}\n"
        f"VW7 Observer consumer: {'AVAILABLE' if stages['VW7_observer_consumer'] else 'UNAVAILABLE'}\n"
        "Held→world incorporation trigger: BLOCKED / NOT IMPLEMENTED"
    )
    return {
        "volumetric_world_vw7_cumulative": {
            "schema": "ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7_STATUS_V1",
            "researcher_only": True,
            "public_preset": str(getattr(cfg, "public_preset", "") or ""),
            "model_line": str(getattr(cfg, "model_line", "") or ""),
            "visibility_class": "DEVELOPMENT_FIXTURE",
            "stages": stages,
            "VW7_is_physical_mechanism": False,
            "held_to_world_physical_trigger": "BLOCKED",
            "authority": "AUTHORITATIVE_WORLD_MATERIAL_OCCUPANCY_ABSOLUTE_Z",
            "banner": banner,
        }
    }


def _volumetric_world_vw7_cumulative_payload(runtime: "PhysicalSystemRuntime") -> dict[str, Any] | None:
    """Researcher-only cumulative VW1–VW7 status for the public VW7 tip preset."""
    cfg = runtime.config
    preset = str(getattr(cfg, "public_preset", "") or "").upper()
    if "VOLUMETRIC_WORLD_VW7" not in preset:
        return None
    if getattr(cfg, "model_line", "") != "ACANTHOSTEGA":
        return None
    if not bool(getattr(getattr(cfg, "volumetric_world_material_occupancy", None), "enabled", False)):
        return None
    if not bool(getattr(getattr(cfg, "minimal_vision_3d_geometric_interface", None), "enabled", False)):
        return None
    stages = {
        "VW1_occupancy": bool(getattr(getattr(cfg, "volumetric_world_material_occupancy", None), "enabled", False)),
        "VW2_support_contact": bool(getattr(getattr(cfg, "occupancy_support_and_contact_queries", None), "enabled", False)),
        "VW3_separation": bool(getattr(getattr(cfg, "volumetric_world_material_separation", None), "enabled", False)),
        "VW4_reintegration_transaction": bool(getattr(getattr(cfg, "volumetric_world_material_reintegration", None), "enabled", False)),
        "VW5_effector_bridge": bool(getattr(getattr(cfg, "effector_held_occupancy_exertion_bridge", None), "enabled", False)),
        "VW6_minimal_vision_3d": bool(getattr(getattr(cfg, "minimal_vision_3d_geometric_interface", None), "enabled", False)),
        "VW7_observer_consumer": bool(getattr(getattr(cfg, "volumetric_world_material_occupancy", None), "enabled", False)),
    }
    banner = (
        "VOLUMETRIC WORLD\n"
        f"VW1 occupancy: {'ACTIVE' if stages['VW1_occupancy'] else 'INACTIVE'}\n"
        f"VW2 support/contact: {'ACTIVE' if stages['VW2_support_contact'] else 'INACTIVE'}\n"
        f"VW3 separation: {'ACTIVE' if stages['VW3_separation'] else 'INACTIVE'}\n"
        f"VW4 reintegration transaction: {'ACTIVE' if stages['VW4_reintegration_transaction'] else 'INACTIVE'}\n"
        f"VW5 effector bridge: {'ACTIVE' if stages['VW5_effector_bridge'] else 'INACTIVE'}\n"
        f"VW6 physical XYZ vision: {'ACTIVE' if stages['VW6_minimal_vision_3d'] else 'INACTIVE'}\n"
        f"VW7 Observer consumer: {'AVAILABLE' if stages['VW7_observer_consumer'] else 'UNAVAILABLE'}\n"
        "Held→world incorporation trigger: BLOCKED / NOT IMPLEMENTED"
    )
    return {
        "volumetric_world_vw7_cumulative": {
            "schema": "ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7_STATUS_V1",
            "researcher_only": True,
            "public_preset": str(getattr(cfg, "public_preset", "") or ""),
            "model_line": str(getattr(cfg, "model_line", "") or ""),
            "stages": stages,
            "VW7_is_physical_mechanism": False,
            "held_to_world_physical_trigger": "BLOCKED",
            "authority": "AUTHORITATIVE_WORLD_MATERIAL_OCCUPANCY_ABSOLUTE_Z",
            "banner": banner,
        }
    }


def world_frame(
    runtime: PhysicalSystemRuntime,
    *,
    max_side: int = 64,
    detail: str = "full",
    observer_interest: Any | None = None,
    derived_subscription: Any | None = None,
) -> dict[str, Any]:
    """Serialize planet fields.

    compact RUNNING keeps only visualization-critical scalars (T, flow, FIELD_*),
    omitting M*/u/R* planes that dominate JSON size. Full detail remains on PAUSE/INSPECT.
    Compact also uses flat grid encoding and avoids duplicating planes across
    top-level / scalars / vectors (OBS-05).

    P1: VOLUME/SURFACE derived geometry builds only when the resolved Observer
    derived-payload subscription requests them. Absent interest defaults to MAP-only.
    """
    from mechanistic_mind.ui.psy_observer_web.observer_derived_payload_subscription import (
        resolve_derived_subscription,
    )

    _derived = derived_subscription or resolve_derived_subscription(observer_interest)
    _want_volume = bool(getattr(_derived, "include_volume", False))
    _want_surface = bool(getattr(_derived, "include_surface", False))

    w = runtime.world
    from mechanistic_mind.physical_system.resource_objects import object_vision_is_active
    _slot0 = (getattr(runtime, "slots", None) or [None])[0]
    _cfg0 = getattr(_slot0, "config", None) if _slot0 is not None else getattr(runtime, "config", None)
    _obj_vis = object_vision_is_active(_cfg0)
    from mechanistic_mind.physical_system.passive_material_properties import (
        passive_material_properties_is_active,
    )
    _props_on = passive_material_properties_is_active(_cfg0)
    from mechanistic_mind.physical_system.physical_optical_material_profile import (
        physical_optical_material_profile_is_active,
        researcher_profile_readout,
        coverage_summary as o1_coverage_summary,
    )
    _o1_on = physical_optical_material_profile_is_active(_cfg0)
    from mechanistic_mind.physical_system.explicit_surface_deposition import (
        ensure_surface_deposits,
        researcher_deposit_readout,
    )
    from mechanistic_mind.physical_system.surface_affinity_traction import (
        surface_affinity_traction_is_active,
        traction_multiplier,
    )
    _traction_on = surface_affinity_traction_is_active(_cfg0)
    _traction_tick = int(getattr(runtime, "tick", 0) or 0)

    def _deposit_row(row: Any) -> dict[str, Any]:
        payload = researcher_deposit_readout(row)
        if _o1_on:
            payload["physical_optical_material_profile"] = researcher_profile_readout(
                payload.get("composition")
            )
            payload["physical_optical_material_profile_label"] = (
                "MATERIAL PROPERTY ONLY · NO PHYSICAL LIGHT TRANSPORT · NOT DISPLAY RGB"
            )
            payload["physical_optical_material_profile_agent_accessible"] = False
        if not _traction_on:
            return payload
        affinity = float(payload.get("surface_affinity") or 0.5)
        updated = int(payload.get("last_updated_tick") or 0)
        payload["traction_multiplier"] = traction_multiplier(affinity)
        payload["traction_eligible"] = updated < _traction_tick
        payload["traction_note"] = "continuous physical law"
        payload["not_a_recipe"] = True
        return payload

    from mechanistic_mind.physical_system.physical_surface_optical_coating import (
        coverage_from_quantity,
        physical_surface_optical_coating_is_active,
    )
    _coating_on = physical_surface_optical_coating_is_active(_cfg0)

    def _with_coating(payload: dict[str, Any], row: Any) -> dict[str, Any]:
        if not _coating_on:
            return payload
        optical = getattr(row, "optical_response", None)
        if optical is None and isinstance(row, dict):
            optical = row.get("optical_response")
        if optical is None:
            payload["optical_coating"] = False
            return payload
        if isinstance(optical, dict):
            triplet = (optical.get("c0"), optical.get("c1"), optical.get("c2"))
        else:
            triplet = tuple(optical)
        quantity = float(getattr(row, "quantity", None) if not isinstance(row, dict) else row.get("quantity") or 0.0)
        payload["optical_c0"] = float(triplet[0])
        payload["optical_c1"] = float(triplet[1])
        payload["optical_c2"] = float(triplet[2])
        payload["coverage"] = coverage_from_quantity(quantity)
        payload["optical_derivation_version"] = getattr(row, "optical_derivation_version", None)
        payload["agent_receives_anonymous_optical_consequence"] = True
        payload["not_a_material_identity"] = True
        payload["not_a_traction_label"] = True
        payload["not_a_recipe"] = True
        payload["researcher_only"] = True
        return payload

    _deposits = [
        _with_coating(_deposit_row(row), row)
        for row in ensure_surface_deposits(w).values()
    ]
    _traction_history: list[dict[str, Any]] = []
    if _traction_on:
        slots = list(getattr(runtime, "slots", None) or [runtime])
        for slot in slots:
            _traction_history.extend(list(getattr(slot, "surface_traction_history", None) or []))
        _traction_history = _traction_history[-8:]
    from mechanistic_mind.physical_system.surface_traction_experience import (
        surface_traction_experience_is_active,
    )
    _experience_on = surface_traction_experience_is_active(_cfg0)
    _experience_history: list[dict[str, Any]] = []
    if _experience_on:
        slots = list(getattr(runtime, "slots", None) or [runtime])
        for slot in slots:
            _experience_history.extend(list(getattr(slot, "traction_experience_history", None) or []))
        _experience_history = [
            {
                "action_tick": row.get("action_tick"),
                "consequence_observation_tick": row.get("consequence_observation_tick"),
                "selected_motor_command": row.get("selected_motor_command"),
                "displacement": row.get("displacement"),
                "prediction_error_status": row.get("prediction_error_status"),
                "memory_status": row.get("memory_status"),
                "memory_reference": row.get("memory_reference"),
                "action_provenance": row.get("action_provenance"),
                "agent_id": row.get("agent_id"),
                "researcher_only": True,
                "not_agent_accessible": True,
            }
            for row in _experience_history[-8:]
        ]
    from mechanistic_mind.physical_system.surface_traction_prediction import (
        surface_traction_prediction_is_active,
    )
    _prediction_on = surface_traction_prediction_is_active(_cfg0)
    _prediction_history: list[dict[str, Any]] = []
    if _prediction_on:
        slots = list(getattr(runtime, "slots", None) or [runtime])
        for slot in slots:
            _prediction_history.extend(list(getattr(slot, "traction_prediction_history", None) or []))
        _prediction_history = [
            {
                "action_tick": row.get("action_tick"),
                "consequence_observation_tick": row.get("consequence_observation_tick"),
                "selected_motor_command": row.get("selected_motor_command"),
                "exposure_phase": row.get("exposure_phase"),
                "prediction_availability": row.get("prediction_availability"),
                "aggregate_error": row.get("aggregate_error"),
                "revision_applied": row.get("revision_applied"),
                "memory_status": row.get("memory_status"),
                "memory_reference": row.get("memory_reference"),
                "action_provenance": row.get("action_provenance"),
                "agent_id": row.get("agent_id"),
                "researcher_only": True,
                "not_agent_accessible": True,
            }
            for row in _prediction_history[-8:]
        ]
    cfg = runtime.config.planet
    fields = discover_world_fields(runtime)
    compact = str(detail).lower() == "compact"
    # full-resolution transport for small worlds; downsample only when above max_side
    if compact:
        T_enc: Any = _flat_grid(w.T, max_side=max_side)
        vx_enc: Any = _flat_grid(w.vx, max_side=max_side)
        vy_enc: Any = _flat_grid(w.vy, max_side=max_side)
        # flow_mag derived client-side from vx/vy when flat — omit duplicate plane
        scalars: dict[str, Any] = {
            "T": T_enc,
            "vx": vx_enc,
            "vy": vy_enc,
            "grids_encoding": "flat",
        }
        if getattr(w, "FIELD_A", None) is not None:
            scalars["FIELD_A"] = _flat_grid(w.FIELD_A, max_side=max_side)
        if getattr(w, "FIELD_B", None) is not None:
            scalars["FIELD_B"] = _flat_grid(w.FIELD_B, max_side=max_side)
        if getattr(w, "terrain_potential", None) is not None:
            scalars["terrain_potential"] = _flat_grid(w.terrain_potential, max_side=max_side)
        if getattr(w, "terrain_drag", None) is not None:
            scalars["terrain_drag"] = _flat_grid(w.terrain_drag, max_side=max_side)
        if getattr(w, "terrain_grad_x", None) is not None and getattr(w, "terrain_grad_y", None) is not None:
            gx = _flat_grid(w.terrain_grad_x, max_side=max_side)
            gy = _flat_grid(w.terrain_grad_y, max_side=max_side)
            # derived magnitude for Observer layer GRADIENT
            data = []
            for i, v in enumerate(gx["data"]):
                data.append(float((v ** 2 + gy["data"][i] ** 2) ** 0.5))
            scalars["terrain_grad_mag"] = {**gx, "data": data}
        if getattr(w, "resource_geo_suit_A", None) is not None:
            scalars["resource_geo_suit_A"] = _flat_grid(w.resource_geo_suit_A, max_side=max_side)
        if getattr(w, "resource_geo_suit_B", None) is not None:
            scalars["resource_geo_suit_B"] = _flat_grid(w.resource_geo_suit_B, max_side=max_side)
        if getattr(w, "surface_response", None) is not None:
            scalars["surface_response"] = _flat_grid(w.surface_response, max_side=max_side)
        T = None
        vx = None
        vy = None
        M = None
        u = None
        Rgrid = None
        vectors: Any = {"flow": {"encoding": "scalars_ref", "vx": "vx", "vy": "vy"}}
        if getattr(w, "ambient_fx", None) is not None and getattr(w, "ambient_fy", None) is not None:
            scalars["ambient_fx"] = _flat_grid(w.ambient_fx, max_side=max_side)
            scalars["ambient_fy"] = _flat_grid(w.ambient_fy, max_side=max_side)
            data = []
            for i, v in enumerate(scalars["ambient_fx"]["data"]):
                data.append(float((v ** 2 + scalars["ambient_fy"]["data"][i] ** 2) ** 0.5))
            scalars["ambient_magnitude"] = {**scalars["ambient_fx"], "data": data}
            vectors["ambient"] = {
                "encoding": "scalars_ref",
                "vx": "ambient_fx",
                "vy": "ambient_fy",
                "observer_ground_truth": True,
            }
        transported_h = int(T_enc["h"])
        transported_w = int(T_enc["w"])
    else:
        T = _grid(w.T, max_side=max_side)
        vx = _grid(w.vx, max_side=max_side)
        vy = _grid(w.vy, max_side=max_side)
        flow_mag = [
            [float((vx[y][x] ** 2 + vy[y][x] ** 2) ** 0.5) for x in range(len(vx[0]))]
            for y in range(len(vx))
        ]
        scalars = {"T": T, "vx": vx, "vy": vy, "flow_mag": flow_mag}
        M = _mat3(w.M, max_side=max_side)
        for i, plane in enumerate(M):
            scalars[f"M{i}"] = plane
        u = _grid(w.u, max_side=max_side) if hasattr(w, "u") else None
        if u is not None:
            scalars["u"] = u
        Rgrid = None
        if getattr(w, "R", None) is not None:
            Rgrid = _grid(w.R, max_side=max_side)
            scalars["R"] = Rgrid
        if getattr(w, "R_A", None) is not None:
            scalars["R_A"] = _grid(w.R_A, max_side=max_side)
        if getattr(w, "R_B", None) is not None:
            scalars["R_B"] = _grid(w.R_B, max_side=max_side)
            if "R_A" in scalars:
                scalars["R_A_plus_R_B"] = [
                    [float(scalars["R_A"][y][x] + scalars["R_B"][y][x]) for x in range(len(scalars["R_B"][0]))]
                    for y in range(len(scalars["R_B"]))
                ]
        if getattr(w, "FIELD_A", None) is not None:
            scalars["FIELD_A"] = _grid(w.FIELD_A, max_side=max_side)
        if getattr(w, "FIELD_B", None) is not None:
            scalars["FIELD_B"] = _grid(w.FIELD_B, max_side=max_side)
        if getattr(w, "terrain_potential", None) is not None:
            scalars["terrain_potential"] = _grid(w.terrain_potential, max_side=max_side)
        if getattr(w, "terrain_drag", None) is not None:
            scalars["terrain_drag"] = _grid(w.terrain_drag, max_side=max_side)
        if getattr(w, "terrain_grad_x", None) is not None and getattr(w, "terrain_grad_y", None) is not None:
            gx = _grid(w.terrain_grad_x, max_side=max_side)
            gy = _grid(w.terrain_grad_y, max_side=max_side)
            scalars["terrain_grad_mag"] = [
                [float((gx[y][x] ** 2 + gy[y][x] ** 2) ** 0.5) for x in range(len(gx[0]))]
                for y in range(len(gx))
            ]
        if getattr(w, "resource_geo_suit_A", None) is not None:
            scalars["resource_geo_suit_A"] = _grid(w.resource_geo_suit_A, max_side=max_side)
        if getattr(w, "resource_geo_suit_B", None) is not None:
            scalars["resource_geo_suit_B"] = _grid(w.resource_geo_suit_B, max_side=max_side)
        if getattr(w, "surface_response", None) is not None:
            scalars["surface_response"] = _grid(w.surface_response, max_side=max_side)
        vectors = {"flow": {"vx": vx, "vy": vy}}
        if getattr(w, "ambient_fx", None) is not None and getattr(w, "ambient_fy", None) is not None:
            afx = _grid(w.ambient_fx, max_side=max_side)
            afy = _grid(w.ambient_fy, max_side=max_side)
            scalars["ambient_fx"] = afx
            scalars["ambient_fy"] = afy
            scalars["ambient_magnitude"] = [
                [float((afx[y][x] ** 2 + afy[y][x] ** 2) ** 0.5) for x in range(len(afx[0]))]
                for y in range(len(afx))
            ]
            vectors["ambient"] = {"vx": afx, "vy": afy, "observer_ground_truth": True}
        transported_h = len(T)
        transported_w = len(T[0]) if T else 0
    return {
        "kind": "WORLD_TRUTH",
        "tick": int(w.tick),
        "width": int(cfg.width),
        "height": int(cfg.height),
        "aspect": float(cfg.width) / max(1, int(cfg.height)),
        "resolution": {"width": int(cfg.width), "height": int(cfg.height)},
        "runtime_resolution": {"width": int(cfg.width), "height": int(cfg.height)},
        "transported_resolution": {"height": transported_h, "width": transported_w},
        "grid_shape_transported": {"height": transported_h, "width": transported_w},
        "frame_detail": "compact" if compact else "full",
        "T": T,
        "M": M,
        "vx": vx,
        "vy": vy,
        "u": u,
        "R": Rgrid,
        "R_A": scalars.get("R_A"),
        "R_B": scalars.get("R_B"),
        "scalars": scalars,
        "vectors": vectors,
        "fields_available": fields,
        "boundary": boundary_metadata(runtime),
        "summary": {
            "T_mean": float(np.mean(w.T)),
            "T_std": float(np.std(w.T)),
            "M_sum": [float(np.sum(w.M[i])) for i in range(w.M.shape[0])] if not compact else "DEFERRED",
            "R_sum": float(np.sum(w.R)) if getattr(w, "R", None) is not None else 0.0,
            "R_A_sum": float(np.sum(w.R_A)) if getattr(w, "R_A", None) is not None else 0.0,
            "R_B_sum": float(np.sum(w.R_B)) if getattr(w, "R_B", None) is not None else 0.0,
            "FIELD_A_sum": float(np.sum(w.FIELD_A)) if getattr(w, "FIELD_A", None) is not None else 0.0,
            "FIELD_B_sum": float(np.sum(w.FIELD_B)) if getattr(w, "FIELD_B", None) is not None else 0.0,
            "vx_mean": float(np.mean(w.vx)),
            "vy_mean": float(np.mean(w.vy)),
        },
        "entities": {
            "note": "Planet fields plus embodied body/bodies. R, R_A, R_B are independent physical stocks (not food).",
            "body": {
                "id": observer_body_id(runtime),
                "agent_id": observer_agent_id(runtime),
                "x": float(runtime.body.x),
                "y": float(runtime.body.y),
                "vx": float(runtime.body.vx),
                "vy": float(runtime.body.vy),
            },
            **({
                "bodies": [
                    {
                        "id": f"body-{i}",
                        "body_id": f"body-{i}",
                        "agent_id": f"agent_{i}",
                        "observer_id": f"agent_{i}",
                        "x": float(slot.body.x),
                        "y": float(slot.body.y),
                        "theta": float(getattr(slot.body, "theta", 0.0) or 0.0),
                        "head_relative_angle": float(getattr(slot.body, "head_relative_angle", 0.0) or 0.0),
                        "head_world_heading": float(
                            getattr(slot.body, "theta", 0.0) or 0.0
                        ) + float(getattr(slot.body, "head_relative_angle", 0.0) or 0.0),
                        "vx": float(slot.body.vx),
                        "vy": float(slot.body.vy),
                        "work": float(getattr(slot.body, "mechanical_work_reservoir", 0.0) or 0.0),
                        "selected_action": slot.last_selected_action,
                    }
                    for i, slot in enumerate(getattr(runtime, "slots", None) or [])
                ]
            } if getattr(runtime, "slots", None) else {}),
            "resource_objects": _researcher_resource_objects(
                w,
                object_vision_enabled=_obj_vis,
                passive_properties_enabled=_props_on,
                optical_profile_enabled=_o1_on,
            ),
            "surface_material_deposits": _deposits,
            **({"surface_traction_receipts": _traction_history} if _traction_on else {}),
            **({"traction_experience_receipts": _experience_history} if _experience_on else {}),
            **({"traction_prediction_receipts": _prediction_history} if _prediction_on else {}),
            "manipulators": _researcher_manipulators(runtime),
        },
        "layers_available": [f["id"] for f in fields] + ["flow_mag", "body"],
        "render_modes": ["SMOOTH", "CELL", "CONTOUR", "VECTOR", "COMPOSITE"],
        "view_modes": {
            "PHYSICAL": "WORLD_TRUTH fields + body pose",
            "AGENT_PERCEPTION": "agent_observation only; world maps marked WORLD GROUND TRUTH vs NOT OBSERVED",
            "PREDICTED": "cognitive prediction/prospection structures when present",
            "DIFFERENCE": "NOT AVAILABLE unless two comparable frames exist in buffer",
        },
        "interpolation_policy": "SMOOTH/CONTOUR interpolation is VISUAL ONLY and never fed back into MM.",
        "observer_ground_truth": _climate_observer_ground_truth(runtime),
        "resource_objects": _researcher_resource_objects(
            w,
            object_vision_enabled=_obj_vis,
            passive_properties_enabled=_props_on,
            optical_profile_enabled=_o1_on,
        ),
        "resource_objects_researcher_only": True,
        "surface_material_deposits": _deposits,
        "surface_material_deposits_researcher_only": True,
        **({
            "physical_optical_material_profile_summary": o1_coverage_summary(
                objects=_researcher_resource_objects(
                    w,
                    object_vision_enabled=_obj_vis,
                    passive_properties_enabled=False,
                    optical_profile_enabled=False,
                ),
                deposits=_deposits,
            ),
            "physical_optical_material_profile_researcher_only": True,
            "physical_optical_material_profile_label": (
                "MATERIAL PROPERTY ONLY · NO PHYSICAL LIGHT TRANSPORT · NOT DISPLAY RGB"
            ),
            "physical_optical_material_profile_organism_saw_material": False,
        } if _o1_on else {}),
        **({
            "exposed_surface_optical_interaction_authority": __import__(
                "mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority",
                fromlist=["researcher_summary"],
            ).researcher_summary(w, _cfg0),
            "exposed_surface_optical_interaction_authority_researcher_only": True,
        } if __import__(
            "mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority",
            fromlist=["exposed_surface_optical_interaction_authority_is_active"],
        ).exposed_surface_optical_interaction_authority_is_active(_cfg0) else {}),
        **({
            "abstract_spectral_light_source_and_direct_transport": __import__(
                "mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport",
                fromlist=["researcher_summary"],
            ).researcher_summary(w, _cfg0),
            "abstract_spectral_light_source_and_direct_transport_researcher_only": True,
        } if __import__(
            "mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport",
            fromlist=["abstract_spectral_light_source_and_direct_transport_is_active"],
        ).abstract_spectral_light_source_and_direct_transport_is_active(_cfg0) else {}),
        **(_o3a_optical_surfaces_world_payload(runtime, w, _cfg0)),
        **(_o4_optical_reception_world_payload(runtime, w, _cfg0)),
        **(_o5_temporal_alignment_world_payload(runtime, w, _cfg0)),
        **(_o6_optical_audit_world_payload(runtime, w, _cfg0, want=_want_surface)),
        **({
            "world_material_transaction": {
                "transaction_id": (getattr(w, "material_transaction_history", None) or [{}])[-1].get("transaction_id"),
                "operation": (getattr(w, "material_transaction_history", None) or [{}])[-1].get("operation_kind"),
                "status": (getattr(w, "material_transaction_history", None) or [{}])[-1].get("status"),
                "input_refs": (getattr(w, "material_transaction_history", None) or [{}])[-1].get("input_refs"),
                "output_refs": (getattr(w, "material_transaction_history", None) or [{}])[-1].get("output_refs"),
                "conservation_verified": all(
                    bool((domain or {}).get("verified"))
                    for domain in ((getattr(w, "material_transaction_history", None) or [{}])[-1].get("conservation") or {}).values()
                    if isinstance(domain, dict)
                ),
                "rejection_reason": (getattr(w, "material_transaction_history", None) or [{}])[-1].get("rejection_reason"),
                "researcher_only": True,
                "not_agent_accessible": True,
                "not_a_recipe": True,
            },
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "world_material_transactions", None), "enabled", False))
            and getattr(w, "material_transaction_history", None)
        ) else {}),
        **(_spatial_contents_payload(w) if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "multi_content_spatial_index", None), "enabled", False))
            and getattr(w, "spatial_contents", None) is not None
        ) else {}),
        **(__import__(
            "mechanistic_mind.physical_system.procedural_surface_columns", fromlist=["researcher_payload"]
        ).researcher_payload(w) if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "procedural_surface_columns", None), "enabled", False))
            and getattr(w, "surface_columns", None) is not None
        ) else {}),
        **(__import__(
            "mechanistic_mind.physical_system.volumetric_world_material_occupancy",
            fromlist=["researcher_payload"],
        ).researcher_payload(w) if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "volumetric_world_material_occupancy", None), "enabled", False))
            and getattr(w, "volumetric_occupancy", None) is not None
        ) else {}),
        **(__import__(
            "mechanistic_mind.physical_system.occupancy_support_and_contact_queries",
            fromlist=["researcher_payload"],
        ).researcher_payload(w) if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "occupancy_support_and_contact_queries", None), "enabled", False))
            and getattr(w, "occupancy_support_contact_state", None) is not None
        ) else {}),
        **(__import__(
            "mechanistic_mind.physical_system.volumetric_world_material_separation",
            fromlist=["researcher_payload"],
        ).researcher_payload(w) if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "volumetric_world_material_separation", None), "enabled", False))
            and getattr(w, "volumetric_material_separation_state", None) is not None
        ) else {}),
        **(__import__(
            "mechanistic_mind.physical_system.volumetric_world_material_reintegration",
            fromlist=["researcher_payload"],
        ).researcher_payload(w) if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "volumetric_world_material_reintegration", None), "enabled", False))
            and getattr(w, "volumetric_material_reintegration_state", None) is not None
        ) else {}),
        **(__import__(
            "mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge",
            fromlist=["researcher_payload"],
        ).researcher_payload(w) if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "effector_held_occupancy_exertion_bridge", None), "enabled", False))
            and getattr(w, "effector_held_occupancy_exertion_bridge_state", None) is not None
        ) else {}),
        **(__import__(
            "mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface",
            fromlist=["researcher_payload"],
        ).researcher_payload(w) if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and bool(getattr(getattr(runtime.config, "minimal_vision_3d_geometric_interface", None), "enabled", False))
            and getattr(w, "minimal_vision_3d_geometric_interface_state", None) is not None
        ) else {}),
        **(_vw7_volume_consumer_world_payload(runtime, want=_want_volume)),
        **(_acanthostega_beta4_capability_payload(runtime) or {}),
        **({
            # Researcher-only visualisation of authoritative emission state (not agent-accessible).
            "local_signal_overlay": __import__(
                "mechanistic_mind.physical_system.local_physical_signal_transport", fromlist=["observer_overlay"]
            ).observer_overlay(w),
            "local_signal_summary": __import__(
                "mechanistic_mind.physical_system.local_physical_signal_transport", fromlist=["researcher_summary"]
            ).researcher_summary(w),
            "local_signal_researcher_only": True,
            **({
                # Researcher-only contact-impulse provenance for the overlay tooltip (not agent-accessible).
                "contact_acoustic_summary": __import__(
                    "mechanistic_mind.physical_system.physical_contact_acoustic_emission",
                    fromlist=["researcher_summary"],
                ).researcher_summary(w),
            } if getattr(w, "contact_acoustic_state", None) is not None else {}),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "local_signal_transport", None) is not None
        ) else {}),
        **({
            # Researcher-only free-object kinematics (authoritative pose/velocity; no collision physics).
            "free_object_kinematics": __import__(
                "mechanistic_mind.physical_system.free_resource_object_kinematics",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "free_object_kinematics_researcher_only": True,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "free_object_kinematics_state", None) is not None
        ) else {}),
        **({
            "body_object_contact": __import__(
                "mechanistic_mind.physical_system.physical_body_resource_object_contact",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "body_object_contact_overlay": __import__(
                "mechanistic_mind.physical_system.physical_body_resource_object_contact",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "body_object_contact_researcher_only": True,
            "body_object_contact_banner": (
                "MASS + COMPLIANCE NORMAL RESPONSE · NO FRICTION · NO SOUND"
                if getattr(w, "body_object_contact_impulse_state", None) is not None
                else "CONTACT FACT ONLY · NO IMPULSE · NO RESPONSE · NO SOUND"
            ),
            "body_object_impulse": (
                __import__(
                    "mechanistic_mind.physical_system.body_resource_object_contact_impulse",
                    fromlist=["researcher_summary"],
                ).researcher_summary(w)
                if getattr(w, "body_object_contact_impulse_state", None) is not None
                else None
            ),
            "body_object_impulse_overlay": (
                __import__(
                    "mechanistic_mind.physical_system.body_resource_object_contact_impulse",
                    fromlist=["overlay_payload"],
                ).overlay_payload(w)
                if getattr(w, "body_object_contact_impulse_state", None) is not None
                else None
            ),
            "body_object_impact_acoustics": (
                __import__(
                    "mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission",
                    fromlist=["researcher_summary"],
                ).researcher_summary(w)
                if getattr(w, "body_object_impact_acoustic_state", None) is not None
                else None
            ),
            "body_object_impact_acoustics_overlay": (
                __import__(
                    "mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission",
                    fromlist=["overlay_payload"],
                ).overlay_payload(w)
                if getattr(w, "body_object_impact_acoustic_state", None) is not None
                else None
            ),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "body_object_contact_state", None) is not None
        ) else {}),

        **({
            "resource_object_pair_contact_impulse": __import__(
                "mechanistic_mind.physical_system.resource_object_pair_contact_impulse",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "resource_object_pair_contact_impulse_overlay": __import__(
                "mechanistic_mind.physical_system.resource_object_pair_contact_impulse",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "resource_object_pair_contact_impulse_researcher_only": True,
            "resource_object_pair_contact_impulse_banner": (
                "OBJECT/OBJECT MASS + COMPLIANCE NORMAL RESPONSE · NO FRICTION · NO SOUND · "
                "MULTI-CONTACT: ISOLATED PAIRS ONLY"
            ),
            "resource_object_pair_impact_acoustics": __import__(
                "mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission",
                fromlist=["researcher_summary"],
            ).researcher_summary(w) if getattr(w, "resource_object_pair_impact_acoustic_state", None) is not None else None,
            "resource_object_pair_impact_acoustics_overlay": __import__(
                "mechanistic_mind.physical_system.resource_object_pair_impact_acoustic_emission",
                fromlist=["overlay_payload"],
            ).overlay_payload(w) if getattr(w, "resource_object_pair_impact_acoustic_state", None) is not None else None,
            "resource_object_pair_impact_acoustics_researcher_only": True,
            "resource_object_pair_impact_acoustics_banner": (
                "OBJECT/OBJECT IMPACT · RESOLVED PAIR IMPULSE → DISSIPATED ENERGY → LOCAL SIGNAL · "
                "NEUTRAL BROADBAND · NO MATERIAL TIMBRE · MULTI-CONTACT UNRESOLVED = SILENT"
            ),
            "resource_object_pair_contact": __import__(
                "mechanistic_mind.physical_system.physical_resource_object_pair_contact",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "resource_object_pair_contact_overlay": __import__(
                "mechanistic_mind.physical_system.physical_resource_object_pair_contact",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "resource_object_pair_contact_researcher_only": True,
            "resource_object_pair_contact_banner": (
                "OBJECT/OBJECT CONTACT FACT ONLY · NO IMPULSE · NO RESPONSE · NO SOUND"
            ),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "resource_object_pair_contact_state", None) is not None
        ) else {}),

        **({
            "held_foreign_body_contact": __import__(
                "mechanistic_mind.physical_system.held_resource_object_foreign_body_contact",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "held_foreign_body_contact_overlay": __import__(
                "mechanistic_mind.physical_system.held_resource_object_foreign_body_contact",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "held_foreign_body_contact_researcher_only": True,
            "held_foreign_body_contact_banner": (
                "HELD OBJECT ↔ FOREIGN BODY CONTACT FACT · NO IMPULSE · NO DAMAGE · NO RELEASE · NO SOUND"
            ),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "held_foreign_body_contact_state", None) is not None
        ) else {}),
        **({
            "held_resource_object_terrain_contact": __import__(
                "mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "held_resource_object_terrain_contact_overlay": __import__(
                "mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "held_resource_object_terrain_contact_researcher_only": True,
            "held_resource_object_terrain_contact_banner": __import__(
                "mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "held_resource_object_terrain_contact_geometry_state", None) is not None
        ) else {}),
        **({
            "held_resource_object_terrain_mechanical_transmission": __import__(
                "mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "held_resource_object_terrain_mechanical_transmission_overlay": __import__(
                "mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "held_resource_object_terrain_mechanical_transmission_researcher_only": True,
            "held_resource_object_terrain_mechanical_transmission_banner": __import__(
                "mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "held_resource_object_terrain_mechanical_transmission_state", None) is not None
        ) else {}),
        **({
            "held_mediated_surface_exertion_integration": __import__(
                "mechanistic_mind.physical_system.held_mediated_surface_exertion_integration",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "held_mediated_surface_exertion_integration_overlay": __import__(
                "mechanistic_mind.physical_system.held_mediated_surface_exertion_integration",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "held_mediated_surface_exertion_integration_researcher_only": True,
            "held_mediated_surface_exertion_integration_banner": __import__(
                "mechanistic_mind.physical_system.held_mediated_surface_exertion_integration",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "held_mediated_surface_exertion_integration_state", None) is not None
        ) else {}),
        **({
            "detached_terrain_material_initial_placement": __import__(
                "mechanistic_mind.physical_system.detached_terrain_material_initial_placement",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "detached_terrain_material_initial_placement_overlay": __import__(
                "mechanistic_mind.physical_system.detached_terrain_material_initial_placement",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "detached_terrain_material_initial_placement_researcher_only": True,
            "detached_terrain_material_initial_placement_banner": __import__(
                "mechanistic_mind.physical_system.detached_terrain_material_initial_placement",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "detached_terrain_material_initial_placement_state", None) is not None
        ) else {}),
        **({
            "bnlt_move_breakaway_locomotion_repair": __import__(
                "mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "bnlt_move_breakaway_locomotion_repair_researcher_only": True,
            "bnlt_move_breakaway_locomotion_repair_banner": __import__(
                "mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "bnlt_move_breakaway_locomotion_repair_state", None) is not None
        ) else {}),
        **({
            "active_locomotion_traction_vs_sliding_friction": __import__(
                "mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "active_locomotion_traction_vs_sliding_friction_researcher_only": True,
            "active_locomotion_traction_vs_sliding_friction_banner": __import__(
                "mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(
                w, "active_locomotion_traction_vs_sliding_friction_state", None
            )
            is not None
        ) else {}),
        **({
            "event_driven_crowded_placement_retry_contract": __import__(
                "mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "event_driven_crowded_placement_retry_contract_researcher_only": True,
            "event_driven_crowded_placement_retry_contract_banner": __import__(
                "mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(
                w, "event_driven_crowded_placement_retry_contract_state", None
            )
            is not None
        ) else {}),
        **({
            "detached_material_amount_scaled_collision_radius": __import__(
                "mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "detached_material_amount_scaled_collision_radius_researcher_only": True,
            "detached_material_amount_scaled_collision_radius_banner": __import__(
                "mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(
                w, "detached_material_amount_scaled_collision_radius_state", None
            )
            is not None
        ) else {}),
        **({
            "held_combine_radius_resize_transaction": __import__(
                "mechanistic_mind.physical_system.held_combine_radius_resize_transaction",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "held_combine_radius_resize_transaction_researcher_only": True,
            "held_combine_radius_resize_transaction_banner": __import__(
                "mechanistic_mind.physical_system.held_combine_radius_resize_transaction",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(
                w, "held_combine_radius_resize_transaction_state", None
            )
            is not None
        ) else {}),
        **({
            "held_deposition_radius_shrink_transaction": __import__(
                "mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "held_deposition_radius_shrink_transaction_researcher_only": True,
            "held_deposition_radius_shrink_transaction_banner": __import__(
                "mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(
                w, "held_deposition_radius_shrink_transaction_state", None
            )
            is not None
        ) else {}),
        **({
            "free_space_state_and_pe_authority_contract": __import__(
                "mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "free_space_state_and_pe_authority_contract_researcher_only": True,
            "free_space_state_and_pe_authority_contract_banner": __import__(
                "mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract",
                fromlist=["BANNER"],
            ).BANNER,
            "last_free_space_support_state": getattr(w, "last_free_space_support_state", None),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(
                w, "free_space_state_and_pe_authority_contract_state", None
            )
            is not None
        ) else {}),
        **({
            "vertical_terrain_landing_contact_response": __import__(
                "mechanistic_mind.physical_system.vertical_terrain_landing_contact_response",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "vertical_terrain_landing_contact_response_researcher_only": True,
            "vertical_terrain_landing_contact_response_banner": __import__(
                "mechanistic_mind.physical_system.vertical_terrain_landing_contact_response",
                fromlist=["BANNER"],
            ).BANNER,
            "last_vertical_terrain_landing": getattr(w, "last_vertical_terrain_landing", None),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(
                w, "vertical_terrain_landing_contact_response_state", None
            )
            is not None
        ) else {}),
        **({
            "vertical_impact_acoustic_emission": __import__(
                "mechanistic_mind.physical_system.vertical_impact_acoustic_emission",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "vertical_impact_acoustic_emission_researcher_only": True,
            "vertical_impact_acoustic_emission_banner": __import__(
                "mechanistic_mind.physical_system.vertical_impact_acoustic_emission",
                fromlist=["BANNER"],
            ).BANNER,
            "last_vertical_impact_acoustic_step": getattr(
                w, "last_vertical_impact_acoustic_step", None
            ),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(
                w, "vertical_impact_acoustic_emission_state", None
            )
            is not None
        ) else {}),
        **({
            "authoritative_physical_acoustic_stream": __import__(
                "mechanistic_mind.physical_system.authoritative_physical_acoustic_stream_contract",
                fromlist=["observer_payload"],
            ).observer_payload(w),
            "authoritative_physical_acoustic_stream_researcher_only": True,
            "authoritative_physical_acoustic_stream_banner": (
                "PHYSICAL ACOUSTIC EVENTS · RESEARCHER-ONLY · NO AUDIO PLAYBACK · NO HZ CALIBRATION"
            ),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and (
                getattr(w, "authoritative_physical_acoustic_stream_state", None) is not None
                or getattr(w, "local_signal_transport", None) is not None
            )
        ) else {}),
        **((lambda _oap: {
            "observer_acoustic_probe": _oap.observer_payload(w),
            "observer_acoustic_probe_researcher_only": True,
            "observer_acoustic_probe_banner": _oap.BANNER,
        })(
            __import__(
                "mechanistic_mind.physical_system.observer_acoustic_probe",
                fromlist=["ensure_probe_state", "observer_payload", "BANNER"],
            )
        ) if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "local_signal_transport", None) is not None
            and __import__(
                "mechanistic_mind.physical_system.observer_acoustic_probe",
                fromlist=["ensure_probe_state"],
            ).ensure_probe_state(w) is not None
        ) else {}),
        **({
            "acoustic_calibration": __import__(
                "mechanistic_mind.physical_system.physical_frequency_amplitude_calibration_contract",
                fromlist=["c0_calibration_reference"],
            ).c0_calibration_reference(),
            "acoustic_calibration_status": __import__(
                "mechanistic_mind.physical_system.physical_frequency_amplitude_calibration_contract",
                fromlist=["observer_calibration_status"],
            ).observer_calibration_status(),
            "acoustic_calibration_contract": __import__(
                "mechanistic_mind.physical_system.physical_frequency_amplitude_calibration_contract",
                fromlist=["c0_calibration_payload"],
            ).c0_calibration_payload(),
            "acoustic_calibration_researcher_only": True,
            "canonical_physical_field_sonification": __import__(
                "mechanistic_mind.physical_system.canonical_physical_field_sonification",
                fromlist=["c1_profile_payload"],
            ).c1_profile_payload(),
            "canonical_physical_field_sonification_status": __import__(
                "mechanistic_mind.physical_system.canonical_physical_field_sonification",
                fromlist=["observer_c1_status"],
            ).observer_c1_status(),
            "canonical_physical_field_sonification_researcher_only": True,
            "selected_organism_auditory_view": __import__(
                "mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt",
                fromlist=["observer_payload"],
            ).observer_payload(w, selected_agent_id=observer_agent_id(runtime)),
            "selected_organism_auditory_view_profile": __import__(
                "mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt",
                fromlist=["profile_reference"],
            ).profile_reference(),
            "selected_organism_auditory_view_researcher_only": True,
            "selected_organism_auditory_view_banner": __import__(
                "mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt",
                fromlist=["WARNING_LABEL"],
            ).WARNING_LABEL,
            "selected_organism_volumetric_vision_view": __import__(
                "mechanistic_mind.physical_system.selected_organism_volumetric_vision_view",
                fromlist=["observer_payload"],
            ).observer_payload(
                w,
                selected_agent_id=observer_agent_id(runtime),
                runtime_generation=getattr(runtime, "runtime_generation", None),
            ),
            "selected_organism_volumetric_vision_view_profile": __import__(
                "mechanistic_mind.physical_system.selected_organism_volumetric_vision_view",
                fromlist=["profile_reference"],
            ).profile_reference(),
            "selected_organism_volumetric_vision_view_researcher_only": True,
            "selected_organism_volumetric_vision_view_banner": __import__(
                "mechanistic_mind.physical_system.selected_organism_volumetric_vision_view",
                fromlist=["BANNER"],
            ).BANNER,
            "organism_receptor_grounded_3d_fpv": __import__(
                "mechanistic_mind.physical_system.organism_receptor_grounded_3d_fpv",
                fromlist=["observer_payload"],
            ).observer_payload(
                w,
                selected_agent_id=observer_agent_id(runtime),
                runtime_generation=getattr(runtime, "runtime_generation", None)
                or getattr(runtime, "_observer_runtime_generation", None),
                # Two-agent runtimes always publish the existing per-agent latest map.
                # Interest remains a cache/delivery hint; it must not hide agent_1.
                include_latest_by_agent=bool(
                    len(getattr(runtime, "slots", None) or []) >= 2
                    or (
                        observer_interest is not None
                        and getattr(observer_interest, "wants", lambda _p: False)(
                            "eye_dock_dual_fpv"
                        )
                    )
                ),
            ),
            "organism_receptor_grounded_3d_fpv_profile": __import__(
                "mechanistic_mind.physical_system.organism_receptor_grounded_3d_fpv",
                fromlist=["profile_reference"],
            ).profile_reference(),
            "organism_receptor_grounded_3d_fpv_researcher_only": True,
            "selected_organism_auditory_sonification": __import__(
                "mechanistic_mind.physical_system.selected_organism_auditory_sonification",
                fromlist=["sav2_profile_payload"],
            ).sav2_profile_payload(),
            "selected_organism_auditory_sonification_status": __import__(
                "mechanistic_mind.physical_system.selected_organism_auditory_sonification",
                fromlist=["observer_sav2_status"],
            ).observer_sav2_status(),
            "selected_organism_auditory_sonification_researcher_only": True,
            "selected_organism_auditory_sonification_banner": __import__(
                "mechanistic_mind.physical_system.selected_organism_auditory_sonification",
                fromlist=["WARNING_LABEL"],
            ).WARNING_LABEL,
            "organism_auditory_transformation_trace": __import__(
                "mechanistic_mind.physical_system.organism_auditory_transformation_trace",
                fromlist=["observer_compact_status"],
            ).observer_compact_status(w),
            "organism_auditory_transformation_trace_profile": __import__(
                "mechanistic_mind.physical_system.organism_auditory_transformation_trace",
                fromlist=["profile_reference"],
            ).profile_reference(),
            "organism_auditory_transformation_trace_researcher_only": True,
            "selected_organism_physical_field_comparison": __import__(
                "mechanistic_mind.physical_system.selected_organism_physical_field_comparison",
                fromlist=["observer_comparison_payload"],
            ).observer_comparison_payload(
                w,
                selected_agent_id=observer_agent_id(runtime),
                selected_body_id=None,
                run_id=str(
                    getattr(runtime, "run_id", None)
                    or getattr(runtime, "seed", None)
                    or "live"
                ),
            ),
            "selected_organism_physical_field_comparison_profile": __import__(
                "mechanistic_mind.physical_system.selected_organism_physical_field_comparison",
                fromlist=["profile_reference"],
            ).profile_reference(),
            "selected_organism_physical_field_comparison_researcher_only": True,
            "selected_organism_physical_field_comparison_banner": __import__(
                "mechanistic_mind.physical_system.selected_organism_physical_field_comparison",
                fromlist=["WARNING"],
            ).WARNING,
            "selected_organism_auditory_offline_reconstruction": __import__(
                "mechanistic_mind.physical_system.selected_organism_auditory_offline_reconstruction_sav4a",
                fromlist=["observer_sav4a_payload"],
            ).observer_sav4a_payload(
                w,
                selected_agent_id=observer_agent_id(runtime),
                selected_body_id=None,
                run_id=str(
                    getattr(runtime, "run_id", None)
                    or getattr(runtime, "seed", None)
                    or "live"
                ),
                runtime_generation=getattr(runtime, "runtime_generation", None),
            ),
            "selected_organism_auditory_offline_reconstruction_profile": __import__(
                "mechanistic_mind.physical_system.selected_organism_auditory_offline_reconstruction_sav4a",
                fromlist=["profile_reference"],
            ).profile_reference(),
            "selected_organism_auditory_offline_reconstruction_researcher_only": True,
            "selected_organism_auditory_offline_reconstruction_banner": __import__(
                "mechanistic_mind.physical_system.selected_organism_auditory_offline_reconstruction_sav4a",
                fromlist=["WARNING"],
            ).WARNING,
            "selected_organism_auditory_offline_player": __import__(
                "mechanistic_mind.physical_system.selected_organism_auditory_offline_player_sav4b",
                fromlist=["observer_banner"],
            ).observer_banner(),
            "selected_organism_auditory_offline_player_profile": __import__(
                "mechanistic_mind.physical_system.selected_organism_auditory_offline_player_sav4b",
                fromlist=["profile_reference"],
            ).profile_reference(),
            "selected_organism_auditory_offline_player_researcher_only": True,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "local_signal_transport", None) is not None
        ) else {}),
        **({
            "release_and_excavation_support_loss_integration": __import__(
                "mechanistic_mind.physical_system.release_and_excavation_support_loss_integration",
                fromlist=["inspector_summary"],
            ).inspector_summary(w, runtime.config),
            "release_and_excavation_support_loss_integration_researcher_only": True,
            "release_and_excavation_support_loss_integration_banner": __import__(
                "mechanistic_mind.physical_system.release_and_excavation_support_loss_integration",
                fromlist=["BANNER"],
            ).BANNER,
            "last_release_excavation_support_loss": (
                getattr(
                    getattr(w, "release_and_excavation_support_loss_integration_state", None),
                    "last_receipt",
                    None,
                )
            ),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(
                w, "release_and_excavation_support_loss_integration_state", None
            )
            is not None
        ) else {}),
        # OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1 — display-only; never physics / never cognition.
        **(__import__(
            "mechanistic_mind.ui.psy_observer_web.vertical_display_contract",
            fromlist=["observer_vertical_display_payload"],
        ).observer_vertical_display_payload(runtime)),
        **({
            "repeated_conservative_surface_column_separation": __import__(
                "mechanistic_mind.physical_system.repeated_conservative_surface_column_separation",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "repeated_conservative_surface_column_separation_overlay": __import__(
                "mechanistic_mind.physical_system.repeated_conservative_surface_column_separation",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "repeated_conservative_surface_column_separation_researcher_only": True,
            "repeated_conservative_surface_column_separation_banner": __import__(
                "mechanistic_mind.physical_system.repeated_conservative_surface_column_separation",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "repeated_conservative_surface_column_separation_state", None) is not None
        ) else {}),
        **({
            "held_translational_impulse": __import__(
                "mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "held_translational_impulse_overlay": __import__(
                "mechanistic_mind.physical_system.held_resource_object_translational_impulse_mediation",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "held_translational_impulse_researcher_only": True,
            "held_translational_impulse_banner": (
                "HELD OBJECT TRANSLATIONAL IMPULSE MEDIATION V1 · CONSTRAINED OBJECT → HOLDER BODY · NO SWING WORK · NO DAMAGE · NO RELEASE · NO SOUND"
            ),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "held_translational_impulse_state", None) is not None
        ) else {}),
        **({
            "effector_work_held_load": __import__(
                "mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "effector_work_held_load_overlay": __import__(
                "mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "effector_work_held_load_researcher_only": True,
            "effector_work_held_load_banner": (
                "EFFECTOR WORK + HELD-LOAD INERTIA ACCOUNTING V1 · NO ARM MASS · NO SWING IMPULSE · NO DAMAGE"
            ),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "effector_work_held_load_state", None) is not None
        ) else {}),
        **({
            "flat_ground_gravity": __import__(
                "mechanistic_mind.physical_system.flat_ground_gravity",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "flat_ground_gravity_overlay": __import__(
                "mechanistic_mind.physical_system.flat_ground_gravity",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "flat_ground_gravity_researcher_only": True,
            "flat_ground_gravity_banner": (
                "PHASE C · FLAT GROUND GRAVITY V1 · UNIFORM g · INELASTIC SUPPORT · "
                "SURFACE ELEVATION NOT ACTIVE · NO SLOPES · NO STACKING"
            ),
            "vertical_state_researcher_only": True,
            "no_agent_symbolic_z": True,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "flat_ground_gravity_state", None) is not None
        ) else {}),
        **({
            "free_resource_object_ground_friction": __import__(
                "mechanistic_mind.physical_system.free_resource_object_ground_friction",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "free_resource_object_ground_friction_overlay": __import__(
                "mechanistic_mind.physical_system.free_resource_object_ground_friction",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "free_resource_object_ground_friction_researcher_only": True,
            "free_resource_object_ground_friction_banner": (
                "FREE OBJECT FLAT-GROUND FRICTION V1 · F=μN · MATERIAL-DERIVED SURFACE COUPLING · "
                "BODIES UNCHANGED · NO AIR DRAG · NO SLOPES"
            ),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "free_resource_object_ground_friction_state", None) is not None
        ) else {}),
        **({
            "surface_elevation_support": __import__(
                "mechanistic_mind.physical_system.surface_elevation_support",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "surface_elevation_support_overlay": __import__(
                "mechanistic_mind.physical_system.surface_elevation_support",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "surface_elevation_support_researcher_only": True,
            "surface_elevation_support_banner": __import__(
                "mechanistic_mind.physical_system.surface_elevation_support",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "surface_elevation_support_state", None) is not None
        ) else {}),
        **({
            "body_normal_load_traction": __import__(
                "mechanistic_mind.physical_system.body_normal_load_traction",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "body_normal_load_traction_overlay": __import__(
                "mechanistic_mind.physical_system.body_normal_load_traction",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "body_normal_load_traction_researcher_only": True,
            "body_normal_load_traction_banner": __import__(
                "mechanistic_mind.physical_system.body_normal_load_traction",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "body_normal_load_traction_state", None) is not None
        ) else {}),
        **({
            "continuous_surface_geometry": __import__(
                "mechanistic_mind.physical_system.continuous_surface_geometry",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "continuous_surface_geometry_overlay": __import__(
                "mechanistic_mind.physical_system.continuous_surface_geometry",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "continuous_surface_geometry_researcher_only": True,
            "continuous_surface_geometry_banner": __import__(
                "mechanistic_mind.physical_system.continuous_surface_geometry",
                fromlist=["BANNER"],
            ).BANNER,
            "continuous_surface_geometry_status_text": __import__(
                "mechanistic_mind.physical_system.continuous_surface_geometry",
                fromlist=["status_text"],
            ).status_text(),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "continuous_surface_geometry_state", None) is not None
        ) else {}),
        **({
            "body_static_traction_threshold": __import__(
                "mechanistic_mind.physical_system.body_static_traction_threshold",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "body_static_traction_threshold_overlay": __import__(
                "mechanistic_mind.physical_system.body_static_traction_threshold",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "body_static_traction_threshold_researcher_only": True,
            "body_static_traction_threshold_banner": __import__(
                "mechanistic_mind.physical_system.body_static_traction_threshold",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "body_static_traction_threshold_state", None) is not None
        ) else {}),
        **({
            "free_resource_object_static_traction_threshold": __import__(
                "mechanistic_mind.physical_system.free_resource_object_static_traction_threshold",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "free_resource_object_static_traction_threshold_overlay": __import__(
                "mechanistic_mind.physical_system.free_resource_object_static_traction_threshold",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "free_resource_object_static_traction_threshold_researcher_only": True,
            "free_resource_object_static_traction_threshold_banner": __import__(
                "mechanistic_mind.physical_system.free_resource_object_static_traction_threshold",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "free_resource_object_static_traction_threshold_state", None) is not None
        ) else {}),
        **({
            "radius_aware_support_points": __import__(
                "mechanistic_mind.physical_system.radius_aware_support_points",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "radius_aware_support_points_overlay": __import__(
                "mechanistic_mind.physical_system.radius_aware_support_points",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "radius_aware_support_points_researcher_only": True,
            "radius_aware_support_points_banner": __import__(
                "mechanistic_mind.physical_system.radius_aware_support_points",
                fromlist=["BANNER"],
            ).BANNER,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "radius_aware_support_points_state", None) is not None
        ) else {}),
        **({
            # G2C1 SES decomposition contract: researcher-only metadata (never agent-visible).
            "ses_decomposition_contract": __import__(
                "mechanistic_mind.physical_system.ses_decomposition_contract",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "ses_decomposition_contract_overlay": __import__(
                "mechanistic_mind.physical_system.ses_decomposition_contract",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "ses_decomposition_contract_researcher_only": True,
            "ses_decomposition_contract_banner": __import__(
                "mechanistic_mind.physical_system.ses_decomposition_contract",
                fromlist=["status_text"],
            ).status_text(),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "ses_decomposition_contract_state", None) is not None
        ) else {}),
        **({
            # G2C2 SES runtime transition classifier: researcher-only (never agent-visible).
            "ses_runtime_transition_classifier": __import__(
                "mechanistic_mind.physical_system.ses_runtime_transition_classifier",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "ses_runtime_transition_classifier_overlay": __import__(
                "mechanistic_mind.physical_system.ses_runtime_transition_classifier",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "ses_runtime_transition_classifier_researcher_only": True,
            "ses_runtime_transition_classifier_banner": __import__(
                "mechanistic_mind.physical_system.ses_runtime_transition_classifier",
                fromlist=["status_text"],
            ).status_text(),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "ses_runtime_transition_classifier_state", None) is not None
        ) else {}),
        **({
            # Radius-aware face sweep: researcher-only SES plan evidence (never agent-visible).
            "radius_aware_face_sweep": __import__(
                "mechanistic_mind.physical_system.radius_aware_face_sweep",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "radius_aware_face_sweep_overlay": __import__(
                "mechanistic_mind.physical_system.radius_aware_face_sweep",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "radius_aware_face_sweep_researcher_only": True,
            "radius_aware_face_sweep_banner": __import__(
                "mechanistic_mind.physical_system.radius_aware_face_sweep",
                fromlist=["status_text"],
            ).status_text(),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "radius_aware_face_sweep_state", None) is not None
        ) else {}),
        **({
            # G2D diagnostic normal-load shadow: researcher-only (never agent-visible).
            "diagnostic_normal_load_shadow": __import__(
                "mechanistic_mind.physical_system.diagnostic_normal_load_shadow",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "diagnostic_normal_load_shadow_overlay": __import__(
                "mechanistic_mind.physical_system.diagnostic_normal_load_shadow",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "diagnostic_normal_load_shadow_researcher_only": True,
            "diagnostic_normal_load_shadow_banner": __import__(
                "mechanistic_mind.physical_system.diagnostic_normal_load_shadow",
                fromlist=["status_text"],
            ).status_text(w),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "diagnostic_normal_load_shadow_state", None) is not None
        ) else {}),

        **({
            "continuous_gravitational_pe_diagnostic_shadow": __import__(
                "mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "continuous_gravitational_pe_diagnostic_shadow_overlay": __import__(
                "mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow",
                fromlist=["overlay_payload"],
            ).overlay_payload(w),
            "continuous_gravitational_pe_diagnostic_shadow_researcher_only": True,
            "continuous_gravitational_pe_diagnostic_shadow_banner": __import__(
                "mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow",
                fromlist=["status_text"],
            ).status_text(w),
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "continuous_gravitational_pe_diagnostic_shadow_state", None) is not None
        ) else {}),

        **({
            "continuous_gravitational_pe": True,
            "continuous_gravitational_pe_banner": __import__(
                "mechanistic_mind.physical_system.continuous_gravitational_pe",
                fromlist=["observer_banner"],
            ).observer_banner(runtime.config),
            "continuous_gravitational_pe_authority": __import__(
                "mechanistic_mind.physical_system.continuous_gravitational_pe",
                fromlist=["active_gravitational_pe_authority"],
            ).active_gravitational_pe_authority(runtime.config),
            "continuous_gravitational_pe_researcher_only": True,
            "projected_normal_load_active": False,
            "tangent_gravity_active": False,
            "passive_slope_sliding_active": False,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and __import__(
                "mechanistic_mind.physical_system.continuous_gravitational_pe",
                fromlist=["endpoint_pe_physically_active"],
            ).endpoint_pe_physically_active(runtime.config)
        ) else {}),

        **({
            "tangent_gravity_diagnostic_shadow": __import__(
                "mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow",
                fromlist=["researcher_summary"],
            ).researcher_summary(w),
            "tangent_gravity_diagnostic_shadow_banner": __import__(
                "mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow",
                fromlist=["status_text"],
            ).status_text(w),
            "tangent_gravity_diagnostic_shadow_researcher_only": True,
            "tangent_gravity_active": False,
            "projected_normal_load_active": False,
            "passive_slope_sliding_active": False,
        } if (
            getattr(runtime.config, "model_line", "") == "ACANTHOSTEGA"
            and getattr(w, "tangent_gravity_diagnostic_shadow_state", None) is not None
        ) else {}),
        **({"surface_traction_receipts": _traction_history, "surface_traction_researcher_only": True} if _traction_on else {}),
        **({
            "traction_experience_receipts": _experience_history,
            "traction_experience_researcher_only": True,
            "traction_experience_not_agent_accessible": True,
        } if _experience_on else {}),
        **({
            "traction_prediction_receipts": _prediction_history,
            "traction_prediction_researcher_only": True,
            "traction_prediction_not_agent_accessible": True,
        } if _prediction_on else {}),
        "manipulators": _researcher_manipulators(runtime),
        "manipulators_researcher_only": True,
        "observer_derived_payload_subscription": _derived.as_frame_meta(
            runtime_generation=int(getattr(runtime, "_observer_runtime_generation", 0) or 0) or None,
        ),
    }


def body_frame(
    runtime: PhysicalSystemRuntime,
    *,
    agent_id: str | None = None,
    body_id: str | None = None,
) -> dict[str, Any]:
    cfg = runtime.config.body
    rest = [list(map(float, p)) for p in cfg.footprint]
    deformation = getattr(runtime.body, "deformation", None)
    deformed = []
    if deformation is not None and len(deformation) == len(rest):
        deformed = [
            [rest[i][0] + float(deformation[i][0]), rest[i][1] + float(deformation[i][1])]
            for i in range(len(rest))
        ]
    else:
        deformed = rest
    theta = float(getattr(runtime.body, "theta", 0.0))
    c, s = float(np.cos(theta)), float(np.sin(theta))
    bsite = getattr(runtime.body, "B_site", None)
    ras = getattr(runtime.body, "R_A_site", None)
    rbs = getattr(runtime.body, "R_B_site", None)
    sites = []
    for i, p in enumerate(deformed):
        sites.append({
            "index": i,
            "rest_local": rest[i],
            "deformed_local": p,
            "world": [
                float(runtime.body.x + c * p[0] - s * p[1]),
                float(runtime.body.y + s * p[0] + c * p[1]),
            ],
            "B_site": (
                float(np.linalg.norm(np.asarray(bsite[i], dtype=np.float64)))
                if bsite is not None and i < len(bsite) else None
            ),
            "B_site_components": (
                np.asarray(bsite[i], dtype=np.float64).astype(float).tolist()
                if bsite is not None and i < len(bsite) else None
            ),
            "R_A_site": float(ras[i]) if ras is not None and i < len(ras) else None,
            "R_B_site": float(rbs[i]) if rbs is not None and i < len(rbs) else None,
        })
    agent_id = agent_id or observer_agent_id(runtime)
    body_id = body_id or observer_body_id(runtime)
    return {
        "id": body_id,
        "body_id": body_id,
        "agent_id": agent_id,
        **runtime.body.snapshot(),
        "deformation": None if getattr(runtime.body, "deformation", None) is None else __import__("numpy").asarray(runtime.body.deformation).tolist(),
        "deformation_diagnostics": getattr(runtime, "last_deformation_meta", None),
        "mechanical_work_reservoir": float(getattr(runtime.body, "mechanical_work_reservoir", 0.0) or 0.0),
        "work_ledger": getattr(runtime, "last_work_ledger", None),
        "motor_work_ledger": getattr(runtime, "last_motor_work_ledger", None),
        "discrete_action_work_ledger": getattr(runtime, "last_action_work_ledger", None),
        "work_allocation_receipt": getattr(runtime, "last_work_allocation", None),
        "R_site": None if getattr(runtime.body, "R_site", None) is None else __import__("numpy").asarray(runtime.body.R_site).tolist(),
        "R_A_site": None if getattr(runtime.body, "R_A_site", None) is None else __import__("numpy").asarray(runtime.body.R_A_site).tolist(),
        "R_B_site": None if getattr(runtime.body, "R_B_site", None) is None else __import__("numpy").asarray(runtime.body.R_B_site).tolist(),
        "resource_ledger": getattr(runtime, "last_resource_ledger", None),
        "complementary_ledger": getattr(runtime, "last_complementary_ledger", None),
        "sites": sites,
        "footprint_source": "PhysicalBodyConfig.footprint + body.deformation, rotated by theta",
        "force_contributions": getattr(runtime, "last_force_contributions", None),
    }


def internal_physical_frame(runtime: PhysicalSystemRuntime) -> dict[str, Any]:
    c = np.asarray(runtime.internal.c, dtype=np.float64)
    return {
        "tick": int(runtime.internal.tick),
        "shape": list(c.shape),
        "c": c.astype(float).tolist(),
        "sum": float(c.sum()),
        "norm": float(np.linalg.norm(c)),
    }


def perception_frame(
    runtime: PhysicalSystemRuntime,
    *,
    foreign_bodies: list | None = None,
) -> dict[str, Any]:
    views = runtime.observation_views(foreign_bodies=foreign_bodies)
    return {
        "agent_observation": views["agent_observation"],
        "boundary": views["boundary"],
        "world_truth_summary": views["world_truth"],
        "unavailable": [
            "object_list",
            "occlusion_map",
            "visual_radar",
            "perception_range_circle",
        ],
    }


def mind_compact_frame(
    runtime: PhysicalSystemRuntime,
    *,
    agent_id: str | None = None,
    body_id: str | None = None,
) -> dict[str, Any]:
    """Compact live cognition summary — not a full MIND dump.

    Observer serialization only. Runtime cognition is unchanged.
    """
    agent_id = agent_id or observer_agent_id(runtime)
    body_id = body_id or observer_body_id(runtime)
    if not runtime.config.cognition.cognition_enabled:
        return {
            "status": "INACTIVE",
            "detail": "compact",
            "source_agent_id": agent_id,
            "agent_id": agent_id,
            "body_id": body_id,
            "agent_seed": int(getattr(runtime, "seed", 0)),
            "tick": int(runtime.tick),
        }
    metrics = (runtime.cognition.get("metrics") or {}) if isinstance(runtime.cognition, dict) else {}
    sel = (runtime.cognition.get("last_selection") or {}) if isinstance(runtime.cognition, dict) else {}
    cog = runtime.cognition if isinstance(runtime.cognition, dict) else {}
    # Compact 4.26–4.28 summaries — no cognition_public_view / cognitive_view.
    from mechanistic_mind.research import contextual_predictive_organization as _cpo
    from mechanistic_mind.research import context_grounded_prospection as _cgp
    from mechanistic_mind.research import persistent_prospective_control as _ppc
    cpo_st = cog.get("contextual_organization") if isinstance(cog.get("contextual_organization"), dict) else {}
    cgp_st = cog.get("context_grounded_prospection") if isinstance(cog.get("context_grounded_prospection"), dict) else {}
    ppc_st = cog.get("persistent_prospective_control") if isinstance(cog.get("persistent_prospective_control"), dict) else {}
    cfg = runtime.config.cognition
    contextual_stack = {
        "detail": "compact",
        "context": _cpo.observer_compact(cpo_st),
        "prospection": _cgp.observer_compact(cgp_st),
        "persistent_control": _ppc.observer_compact(ppc_st),
        "flags": {
            "contextual_predictive_organization": bool(getattr(cfg, "contextual_predictive_organization", False)),
            "context_grounded_prospection": bool(getattr(cfg, "context_grounded_prospection", False)),
            "persistent_prospective_control": bool(getattr(cfg, "persistent_prospective_control", False)),
        },
        "psc_mode": str(getattr(cfg, "prospective_selection", "")),
        "last_event": (ppc_st.get("last_event") if isinstance(ppc_st, dict) else None),
        "last_reactivation": (cpo_st.get("last_reactivation") if isinstance(cpo_st, dict) else None),
        "last_active_context": (cpo_st.get("last_active") if isinstance(cpo_st, dict) else None),
        "selection_source": sel.get("source"),
        "note": "Observer compact chain — not a map/goal/intention variable",
    }
    return {
        "status": "ACTIVE",
        "detail": "compact",
        "source_agent_id": agent_id,
        "agent_id": agent_id,
        "body_id": body_id,
        "agent_seed": int(getattr(runtime, "seed", 0)),
        "tick": int(runtime.tick),
        "action": {
            "selected": runtime.last_selected_action,
            "source": sel.get("source"),
            "selection_rule": sel.get("selection_rule"),
            "candidates": sel.get("candidates"),
        },
        "metrics": {
            "prediction_count": metrics.get("prediction_count"),
            "prospective_compositions": metrics.get("prospective_compositions"),
            "novel_compositions": metrics.get("novel_compositions"),
            "action_counts": dict(metrics.get("action_counts") or {}),
        },
        "contextual_stack": contextual_stack,
        "note": "COMPACT live summary. Open MIND / inspect for full cognition structures.",
    }


def mind_frame(
    runtime: PhysicalSystemRuntime,
    *,
    agent_id: str | None = None,
    body_id: str | None = None,
    cog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    agent_id = agent_id or observer_agent_id(runtime)
    body_id = body_id or observer_body_id(runtime)
    if not runtime.config.cognition.cognition_enabled:
        return {
            "status": "INACTIVE",
            "mechanisms": {},
            "source_agent_id": agent_id,
            "agent_id": agent_id,
            "body_id": body_id,
            "agent_seed": int(getattr(runtime, "seed", 0)),
            "tick": int(runtime.tick),
        }
    cog = cog if cog is not None else runtime.cognitive_view()
    cfg = cog.get("mechanisms") or {}
    bridges = cog.get("bridges") or {}

    def status(flag_key: str, bridge_note: str | None = None) -> dict[str, Any]:
        enabled = bool(cfg.get(flag_key, False))
        ablated = not enabled
        row = {
            "name": flag_key,
            "state": "ABLATED" if ablated else "ACTIVE",
        }
        if bridge_note:
            row["bridge"] = bridge_note
        return row

    mechanisms = [
        status("predictive_compression"),
        status("multiscale_prediction"),
        status("prospective_composition"),
        {
            **status("instrumental_observation"),
            "physical_path": bridges.get("4.25_physical_emit_transducer_on_psr", "UNKNOWN"),
        },
        status("bounded_memory"),
        status("retrieval"),
        {
            **status("unknown_action_physical_probe"),
            "selection_effect": (cog.get("action") or {}).get("unknown_action_probe", {}).get("selection_effect"),
            "unmodeled_first_actions": (cog.get("action") or {}).get("unknown_action_probe", {}).get("unmodeled_first_actions"),
            "modeled_first_actions": (cog.get("action") or {}).get("unknown_action_probe", {}).get("modeled_first_actions"),
            "arbitration": (cog.get("action") or {}).get("unknown_action_probe", {}).get("arbitration"),
        },
        {
            **status("predictive_equivalence"),
            "note": "LEARNED_PREDICTIVE_REPRESENTATION — not physical ground truth",
        },
        {
            **status("predictive_relevance"),
            "note": "LEARNED_RELEVANCE_STRUCTURE — not attention, not physical ground truth",
        },
        {
            **status("temporal_predictive_structure"),
            "note": "TEMPORAL_PREDICTIVE_STRUCTURE — not time perception, not a clock",
        },
        {
            **status("temporal_prospection_bridge"),
            "note": "TEMPORAL_PROSPECTION_BRIDGE — transport only, not planning",
        },
        {
            **status("predictive_conflict"),
            "note": "PREDICTIVE_CONFLICT — not doubt, not belief, not choice",
        },
        {
            **status("future_sensitive_action"),
            "note": "FUTURE_SENSITIVE_ACTION — not utility, not preference, not a new policy",
        },
        {
            **status("prediction_error_revision"),
            "note": "PREDICTION_ERROR_REVISION — not punishment, not trust, not policy",
        },
        {
            **status("temporal_prediction_error"),
            "note": "TEMPORAL_PREDICTION_ERROR — residual fragments, not drift detection",
        },
        {
            **status("predicted_context_prospection"),
            "note": "PREDICTED CONTEXT PROSPECTION — not imagined experience, not a policy",
        },
        {
            **status("multistep_action_prospection"),
            "note": "MULTI-STEP ACTION PROSPECTION — not planning, not a policy",
        },
    ]
    mem = cog.get("memory") or {}
    pred = cog.get("predictive_organization") or {}
    prosp = cog.get("prospection") or {}
    inst = cog.get("instrumental_observation") or {}
    return {
        "status": "ACTIVE",
        "source_agent_id": agent_id,
        "agent_id": agent_id,
        "body_id": body_id,
        "agent_seed": int(getattr(runtime, "seed", 0)),
        "tick": int(runtime.tick),
        "mechanisms": mechanisms,
        "bridges": bridges,
        "memory": mem,
        "predictive_organization": pred,
        "prospection": prosp,
        "instrumental_observation": inst,
        "unknown_action_probe": (cog.get("action") or {}).get("unknown_action_probe") or {"enabled": False},
        "predictive_equivalence": cog.get("predictive_equivalence") or {
            "enabled": False,
            "note": "LEARNED_PREDICTIVE_REPRESENTATION — not physical ground truth",
        },
        "predictive_relevance": cog.get("predictive_relevance") or {
            "enabled": False,
            "note": "LEARNED_RELEVANCE_STRUCTURE — not attention, not physical ground truth",
        },
        "temporal_predictive_structure": cog.get("temporal_predictive_structure") or {
            "enabled": False,
            "note": "TEMPORAL_PREDICTIVE_STRUCTURE — not time perception, not a clock",
        },
        "temporal_prospection_bridge": cog.get("temporal_prospection_bridge") or {
            "enabled": False,
            "note": "TEMPORAL_PROSPECTION_BRIDGE — transport only, not planning",
        },
        "predictive_conflict": cog.get("predictive_conflict") or {
            "enabled": False,
            "note": "PREDICTIVE_CONFLICT — not doubt, not belief, not choice",
        },
        "future_sensitive_action": cog.get("future_sensitive_action") or {
            "enabled": False,
            "note": "FUTURE_SENSITIVE_ACTION — not utility, not preference, not a new policy",
        },
        "prediction_error_revision": cog.get("prediction_error_revision") or {
            "enabled": False,
            "note": "PREDICTION_ERROR_REVISION — not punishment, not trust, not policy",
        },
        "temporal_prediction_error": cog.get("temporal_prediction_error") or {
            "enabled": False,
            "note": "TEMPORAL_PREDICTION_ERROR — residual fragments, not drift detection",
        },
        "predicted_context_prospection": cog.get("predicted_context_prospection") or {
            "enabled": False,
            "note": "PREDICTED CONTEXT PROSPECTION — not imagined experience, not a policy",
        },
        "multistep_action_prospection": cog.get("multistep_action_prospection") or {
            "enabled": False,
            "note": "MULTI-STEP ACTION PROSPECTION — not planning, not a policy",
        },
        "contextual_predictive_organization": cog.get("contextual_predictive_organization") or {
            "enabled": False,
            "note": "CONTEXTUAL_PREDICTIVE_ORGANIZATION — not place / map / familiar",
        },
        "context_grounded_prospection": cog.get("context_grounded_prospection") or {
            "enabled": False,
            "note": "CONTEXT_GROUNDED_PROSPECTION — not route / destination",
        },
        "persistent_prospective_control": cog.get("persistent_prospective_control") or {
            "enabled": False,
            "note": "PERSISTENT_PROSPECTIVE_CONTROL — support-gated, not intention variable",
        },
        "contextual_stack": {
            "detail": "full",
            "context": (cog.get("contextual_predictive_organization") or {}).get("observer_compact") or {},
            "prospection": (cog.get("context_grounded_prospection") or {}).get("observer_compact") or {},
            "persistent_control": (cog.get("persistent_prospective_control") or {}).get("observer_compact") or {},
            "flags": {
                "contextual_predictive_organization": bool((cog.get("mechanisms") or {}).get("contextual_predictive_organization")),
                "context_grounded_prospection": bool((cog.get("mechanisms") or {}).get("context_grounded_prospection")),
                "persistent_prospective_control": bool((cog.get("mechanisms") or {}).get("persistent_prospective_control")),
            },
            "psc_mode": (cog.get("action") or {}).get("prospective_selection_mode"),
            "last_event": ((cog.get("persistent_prospective_control") or {}).get("last_event")),
            "last_reactivation": ((cog.get("contextual_predictive_organization") or {}).get("last_reactivation")),
            "last_active_context": ((cog.get("contextual_predictive_organization") or {}).get("last_active")),
            "selection_source": (cog.get("action") or {}).get("source"),
            "note": "Observer chain from public view — not map/goal/intention",
        },
        "metrics": cog.get("metrics") or {},
        "causal_trace": cog.get("causal_trace") or {},
        "action": cog.get("action") or {},
    }


def causal_chain_compact_frame(
    runtime: PhysicalSystemRuntime,
    *,
    previous_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bounded live pipeline stages for RUNNING compact frames.

    Intentionally avoids ``cognitive_view`` / ``cognition_public_view`` (the full
    capture hotspot). Supplies only the fields the live pipeline cards read.
    """
    body_now = runtime.body.snapshot()
    cog_on = bool(runtime.config.cognition.cognition_enabled)
    sel = (runtime.cognition.get("last_selection") or {}) if isinstance(runtime.cognition, dict) else {}
    metrics = (runtime.cognition.get("metrics") or {}) if isinstance(runtime.cognition, dict) else {}

    # WORLD: UI shows T_mean + tick only.
    try:
        t_mean = float(runtime.world.T.mean())
    except Exception:
        t_mean = float("nan")
    world_data = {"T_mean": t_mean, "tick": int(runtime.world.tick)}

    # PERCEPTION: compact numeric summary (no full observation bundle grids).
    perception_data: dict[str, float] = {
        "x": float(body_now.get("x", 0.0)),
        "y": float(body_now.get("y", 0.0)),
        "T": float(body_now.get("T", 0.0)),
        "mech": float(body_now.get("mech", 0.0)),
        "vx": float(body_now.get("vx", 0.0)),
        "vy": float(body_now.get("vy", 0.0)),
    }

    if previous_body is None:
        consequence: dict[str, Any] = {
            "status": "NOT AVAILABLE",
            "reason": "no prior body snapshot in buffer",
        }
    else:
        consequence = {
            "status": "AVAILABLE",
            "dx": float(body_now["x"] - previous_body["x"]),
            "dy": float(body_now["y"] - previous_body["y"]),
            "dT": float(body_now["T"] - previous_body["T"]),
            "dvx": float(body_now["vx"] - previous_body["vx"]),
            "dvy": float(body_now["vy"] - previous_body["vy"]),
            "d_matter_in": float(body_now["matter_in"] - previous_body["matter_in"]),
            "d_mech": float(body_now["mech"] - previous_body["mech"]),
        }

    internal_phys = internal_physical_frame(runtime)

    return {
        "tick": int(runtime.tick),
        "detail": "compact",
        "stages": {
            "WORLD": {"status": "AVAILABLE", "data": world_data},
            "PERCEPTION": {
                "status": "AVAILABLE",
                "data": perception_data,
                "note": "compact numeric body/local summary; not full observation bundle",
            },
            "BODY": {"status": "AVAILABLE", "data": body_now},
            "INTERNAL": {
                "status": "AVAILABLE",
                "physical": internal_phys,
                "cognitive": {
                    "status": "AVAILABLE" if cog_on else "NOT AVAILABLE",
                    "summary": {
                        "prediction_count": metrics.get("prediction_count"),
                        "action_counts": dict(metrics.get("action_counts") or {}),
                    }
                    if cog_on
                    else None,
                },
            },
            "PREDICTION": {
                "status": "AVAILABLE" if cog_on else "NOT AVAILABLE",
                "prediction_matches": None,
                "continuations": None,
                "predictive_organization_keys": [],
                "metrics": {
                    "prediction_count": metrics.get("prediction_count"),
                    "prospective_compositions": metrics.get("prospective_compositions"),
                }
                if cog_on
                else None,
                "note": "compact: counts only; full matches on PAUSED/INSPECT",
            }
            if cog_on
            else {"status": "NOT AVAILABLE", "reason": "cognition_disabled"},
            "ACTION": {
                "status": "AVAILABLE" if cog_on else "NOT AVAILABLE",
                "selected": runtime.last_selected_action,
                "candidates": list(available_actions()) if cog_on else [],
                "source": sel.get("source") if cog_on else None,
                "last_apply": sel.get("last_apply") if cog_on else None,
            },
            "CONSEQUENCE": consequence,
        },
        "note": "COMPACT live pipeline. PAUSED/INSPECT publishes full causal_chain.",
    }


def cognition_pipeline_compact_frame(runtime: PhysicalSystemRuntime) -> dict[str, Any]:
    """Config-flag pipeline rows without cognitive_view()."""
    from mechanistic_mind.model.tiktaalik import promotion_class

    cfg = runtime.config.cognition
    stages: list[dict[str, Any]] = []

    def add(stage: str, *, enabled: bool, mechanism_id: str) -> None:
        pclass = promotion_class(mechanism_id)
        stages.append({
            "stage": stage,
            "status": "ACTIVE" if enabled else "OFF",
            "promotion_class": pclass,
            "experimental": pclass == "EXPERIMENTAL",
        })

    add("OBSERVATION", enabled=True, mechanism_id="discrete_action_bridge")
    add("HISTORY / INGEST", enabled=bool(cfg.bounded_memory), mechanism_id="bounded_memory")
    add("RETRIEVAL", enabled=bool(cfg.retrieval), mechanism_id="retrieval")
    add("PREDICTIVE COMPRESSION", enabled=bool(cfg.predictive_compression), mechanism_id="predictive_compression")
    add("MULTISCALE PREDICTION", enabled=bool(cfg.multiscale_prediction), mechanism_id="multiscale_prediction")
    add("TEMPORAL PREDICTION", enabled=bool(cfg.temporal_predictive_structure), mechanism_id="temporal_predictive_structure")
    add("PREDICTED CONTEXT", enabled=bool(cfg.predicted_context_prospection), mechanism_id="predicted_context_prospection")
    add("PROSPECTION", enabled=bool(cfg.prospective_composition), mechanism_id="prospective_composition")
    add("MULTI-STEP PROSPECTION", enabled=bool(cfg.multistep_action_prospection), mechanism_id="multistep_action_prospection")
    add("CONFLICT", enabled=bool(cfg.predictive_conflict), mechanism_id="predictive_conflict")
    add(
        "COMPETITION",
        enabled=str(cfg.prospective_selection).upper() == "SCENARIO_COMPETITION",
        mechanism_id="prospective_scenario_competition",
    )
    add("SELECTED ACTION", enabled=bool(cfg.cognition_enabled), mechanism_id="cognition")
    add("REALIZED PHYSICS", enabled=True, mechanism_id="discrete_action_bridge")
    add("ERROR / REVISION", enabled=bool(cfg.prediction_error_revision), mechanism_id="prediction_error_revision")
    return {
        "detail": "compact",
        "stages": stages,
        "selected_action": runtime.last_selected_action,
        "branch_count": None,
        "note": "COMPACT pipeline flags only; no cognitive_view.",
    }


def causal_chain_frame(
    runtime: PhysicalSystemRuntime,
    *,
    previous_body: dict[str, Any] | None = None,
    cog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """WORLD → PERCEPTION → BODY → INTERNAL → PREDICTION → ACTION → CONSEQUENCE."""
    views = runtime.observation_views()
    if cog is None:
        cog = runtime.cognitive_view() if runtime.config.cognition.cognition_enabled else {}
    action = (cog.get("action") if cog else None) or {}
    sel = action
    prosp = (cog.get("prospection") if cog else None) or {}
    pred_org = (cog.get("predictive_organization") if cog else None) or {}
    body_now = runtime.body.snapshot()

    consequence: dict[str, Any]
    if previous_body is None:
        consequence = {"status": "NOT AVAILABLE", "reason": "no prior body snapshot in buffer"}
    else:
        consequence = {
            "status": "AVAILABLE",
            "dx": float(body_now["x"] - previous_body["x"]),
            "dy": float(body_now["y"] - previous_body["y"]),
            "dT": float(body_now["T"] - previous_body["T"]),
            "dvx": float(body_now["vx"] - previous_body["vx"]),
            "dvy": float(body_now["vy"] - previous_body["vy"]),
            "d_matter_in": float(body_now["matter_in"] - previous_body["matter_in"]),
            "d_mech": float(body_now["mech"] - previous_body["mech"]),
        }

    prediction = {
        "status": "AVAILABLE" if runtime.config.cognition.cognition_enabled else "NOT AVAILABLE",
        "prediction_matches": sel.get("prediction_matches") if sel else None,
        "continuations": prosp.get("current") if prosp else None,
        "predictive_organization_keys": list(pred_org)[:16] if pred_org else [],
    }
    if not runtime.config.cognition.cognition_enabled:
        prediction = {"status": "NOT AVAILABLE", "reason": "cognition_disabled"}

    why = _why_this_action(runtime, cog)
    why_move = _why_did_it_move(runtime)

    return {
        "tick": int(runtime.tick),
        "stages": {
            "WORLD": {"status": "AVAILABLE", "data": views["world_truth"]},
            "PERCEPTION": {
                "status": "AVAILABLE",
                "data": views["agent_observation"],
                "note": "agent-accessible only",
            },
            "BODY": {"status": "AVAILABLE", "data": body_now},
            "INTERNAL": {
                "status": "AVAILABLE",
                "physical": internal_physical_frame(runtime),
                "cognitive": {
                    "status": "AVAILABLE" if runtime.config.cognition.cognition_enabled else "NOT AVAILABLE",
                    "summary": {
                        "memory_keys": list((cog.get("memory") or {}))[:12],
                        "bridges": cog.get("bridges"),
                    } if cog else None,
                },
            },
            "PREDICTION": prediction,
            "ACTION": {
                "status": "AVAILABLE" if runtime.config.cognition.cognition_enabled else "NOT AVAILABLE",
                "selected": runtime.last_selected_action,
                "candidates": list(available_actions()),
                "source": sel.get("source") if sel else None,
                "last_apply": sel.get("last_apply") if sel else None,
            },
            "CONSEQUENCE": consequence,
        },
        "why_this_action": why,
        "why_did_it_move": why_move,
    }


def _why_this_action(runtime: PhysicalSystemRuntime, cog: dict[str, Any]) -> dict[str, Any]:
    if not runtime.config.cognition.cognition_enabled or not cog:
        return {"status": "CAUSAL ATTRIBUTION NOT AVAILABLE", "reason": "cognition_disabled"}
    receipt = cog.get("last_decision_receipt") or runtime.cognition.get("last_decision_receipt")
    action = cog.get("action") or {}
    if isinstance(receipt, dict) and str(receipt.get("schema") or "").startswith("mm.action_decision_receipt.v"):
        return {
            "status": "AVAILABLE",
            "schema": receipt.get("schema"),
            "selected": receipt.get("selected_action"),
            "source": receipt.get("selection_source"),
            "selection_rule": (receipt.get("selection") or {}).get("selection_rule"),
            "peer_evaluation": (receipt.get("selection") or {}).get("peer_evaluation"),
            "tie_state": (receipt.get("selection") or {}).get("tie_state"),
            "tie_break_rule": (receipt.get("selection") or {}).get("tie_break_rule"),
            "prospective_selection_mode": receipt.get("prospective_selection_mode"),
            "available_physical_actions": receipt.get("available_physical_actions"),
            "supported_physical_actions": receipt.get("supported_physical_actions"),
            "scenario_groups": receipt.get("scenario_groups"),
            "competition": receipt.get("competition"),
            "candidates": receipt.get("candidates"),
            "prospective_continuations": receipt.get("prospective_continuations"),
            "retrieved_structures": receipt.get("retrieved_structures"),
            "bridge": receipt.get("bridge"),
            "consequence": receipt.get("consequence"),
            "counterfactual": receipt.get("counterfactual"),
            "receipt": receipt,
            "note": "Receipt records actual selection rule; AVAILABLE ≠ SUPPORTED ≠ SELECTED.",
        }
    # fallback to causal_trace edges only
    trace = cog.get("causal_trace") or {}
    events = trace.get("events") or []
    edges = trace.get("edges") or []
    action_events = [e for e in events if e.get("kind") == "ACTION_SELECTED"]
    if not action_events:
        return {
            "status": "CAUSAL ATTRIBUTION NOT AVAILABLE",
            "reason": "no ACTION_SELECTED event / receipt yet",
            "selected": action.get("selected"),
            "source": action.get("source"),
        }
    latest = action_events[-1]
    eid = latest.get("id")
    incoming = [e for e in edges if e.get("target") == eid]
    return {
        "status": "AVAILABLE",
        "selected": action.get("selected"),
        "source": action.get("source"),
        "selection_difference": "SELECTION DIFFERENCE NOT EXPOSED",
        "action_event": latest,
        "contributing_edges": incoming,
        "relation_policy": "Only edges recorded by causal_trace; TEMPORALLY_ASSOCIATED ≠ CAUSALLY_SUPPORTED",
    }


def experiment_config_frame(runtime: PhysicalSystemRuntime, *, detail: str = "full") -> dict[str, Any]:
    cfg = runtime.config
    from mechanistic_mind.physical_system.ecology_presets import ecology_metadata

    eco = ecology_metadata(cfg)
    compact = str(detail).lower() == "compact"
    runtime_block = {
        "type": "TwoAgentRuntime" if getattr(runtime, "slots", None) else "PhysicalSystemRuntime",
        "cognition_enabled": cfg.cognition.cognition_enabled,
        "agent_count": len(getattr(runtime, "slots", None) or [runtime]),
        "selected_agent": observer_agent_id(runtime),
        "selected_agent_id": observer_agent_id(runtime),
        "selected_body_id": observer_body_id(runtime),
        "agent_body_mapping": agent_body_mapping(runtime),
        "observer_agent_ids": (
            [f"agent_{i}" for i in range(len(runtime.slots))]
            if getattr(runtime, "slots", None)
            else ["agent_0"]
        ),
        "ecology_preset": eco.get("ecology_preset"),
        "psc_off_ticks": getattr(cfg.cognition, "psc_off_ticks", None),
        "note": "Technical observer IDs. Not present in agent observation.",
        "pe_cold_history_eviction": False,
    }
    try:
        from mechanistic_mind.ui.psy_observer_web.tiktaalik_eye import psc_off_ticks_status

        runtime_block["psc_schedule"] = psc_off_ticks_status(runtime)
    except Exception:
        runtime_block["psc_schedule"] = {
            "psc": "—",
            "schedule": getattr(cfg.cognition, "psc_off_ticks", None),
            "armed": False,
        }
    try:
        from mechanistic_mind.research import pe_cold_archive as cold

        runtime_block["pe_cold_history_eviction"] = bool(cold.cold_eviction_enabled())
    except Exception:
        pass
    gt = _climate_observer_ground_truth(runtime)
    if compact:
        ew = (gt or {}).get("effective_world") or {}
        slim_ew = {
            "requested_preset": ew.get("requested_preset"),
            "world_fingerprint": ew.get("world_fingerprint"),
            "overrides": ew.get("overrides"),
            "climate_ablated": ew.get("climate_ablated"),
            "climate_package_implies_climate": ew.get("climate_package_implies_climate"),
            "resources_now": ew.get("resources_now"),
            "subsystems": ew.get("subsystems"),
            "climate_ecology": ew.get("climate_ecology"),
            "near_field_exteroception": ew.get("near_field_exteroception"),
        }
        return {
            "detail": "compact",
            "seed": int(runtime.seed),
            "ecology_preset": eco.get("ecology_preset"),
            "ecology_ui_label": eco.get("ui_label"),
            "runtime": runtime_block,
            "world": {
                "width": int(cfg.planet.width),
                "height": int(cfg.planet.height),
                "boundary": boundary_metadata(runtime),
                "ecology_preset": eco.get("ecology_preset"),
            },
            "observer_ground_truth": {
                "ecology_preset": (gt or {}).get("ecology_preset") or eco.get("ecology_preset"),
                "effective_world": slim_ew,
            },
            "note": "Compact experiment omits static planet/body/internal dicts; full on PAUSE/INSPECT.",
        }
    planet = cfg.planet.to_dict() if hasattr(cfg.planet, "to_dict") else {}
    return {
        "seed": int(runtime.seed),
        "ecology_preset": eco.get("ecology_preset"),
        "ecology_ui_label": eco.get("ui_label"),
        "body_orientation_force_scale": eco.get("body_orientation_force_scale"),
        "passive_reservoir_trickle": eco.get("passive_reservoir_trickle"),
        "runtime": runtime_block,
        "world": {
            **planet,
            "width": int(cfg.planet.width),
            "height": int(cfg.planet.height),
            "boundary": boundary_metadata(runtime),
            "fields_available": discover_world_fields(runtime),
            "supported_size_notes": "width/height are PlanetConfig integers; renderer adapts to aspect ratio. Changing size requires a new run.",
            "ecology_preset": eco.get("ecology_preset"),
        },
        "agent_body": cfg.body.to_dict() if hasattr(cfg.body, "to_dict") else {},
        "internal": cfg.internal.to_dict() if hasattr(cfg.internal, "to_dict") else {},
        "mechanisms": cfg.cognition.to_dict(),
        "actions_available": list(available_actions()),
        "actions_bridge_missing": ["TAKE", "RELEASE", "CONTACT", "EMIT"],
        "note": "Only parameters supported by PhysicalSystemConfig / CognitionConfig are listed.",
        "observer_ground_truth": gt,
    }


def cognition_pipeline_frame(
    runtime: PhysicalSystemRuntime,
    *,
    cog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Readable live pipeline from actual configured runtime stages."""
    from mechanistic_mind.model.tiktaalik import promotion_class

    cfg = runtime.config.cognition
    if cog is None:
        cog = runtime.cognitive_view() if cfg.cognition_enabled else {}
    stages: list[dict[str, Any]] = []

    def add(stage: str, *, enabled: bool, mechanism_id: str, detail: str | None = None) -> None:
        pclass = promotion_class(mechanism_id)
        row = {
            "stage": stage,
            "status": "ACTIVE" if enabled else "OFF",
            "promotion_class": pclass,
            "experimental": pclass == "EXPERIMENTAL",
        }
        if detail:
            row["detail"] = detail
        stages.append(row)

    add("OBSERVATION", enabled=True, mechanism_id="discrete_action_bridge")
    add("HISTORY / INGEST", enabled=bool(cfg.bounded_memory), mechanism_id="bounded_memory")
    add("RETRIEVAL", enabled=bool(cfg.retrieval), mechanism_id="retrieval")
    add("PREDICTIVE COMPRESSION", enabled=bool(cfg.predictive_compression), mechanism_id="predictive_compression")
    add("MULTISCALE PREDICTION", enabled=bool(cfg.multiscale_prediction), mechanism_id="multiscale_prediction")
    add("TEMPORAL PREDICTION", enabled=bool(cfg.temporal_predictive_structure), mechanism_id="temporal_predictive_structure")
    add("PREDICTED CONTEXT", enabled=bool(cfg.predicted_context_prospection), mechanism_id="predicted_context_prospection")
    add("PROSPECTION", enabled=bool(cfg.prospective_composition), mechanism_id="prospective_composition")
    add("MULTI-STEP PROSPECTION", enabled=bool(cfg.multistep_action_prospection), mechanism_id="multistep_action_prospection")
    add("CONFLICT", enabled=bool(cfg.predictive_conflict), mechanism_id="predictive_conflict")
    add("COMPETITION", enabled=str(cfg.prospective_selection).upper() == "SCENARIO_COMPETITION", mechanism_id="prospective_scenario_competition")
    add("SELECTED ACTION", enabled=bool(cfg.cognition_enabled), mechanism_id="cognition")
    add("REALIZED PHYSICS", enabled=True, mechanism_id="discrete_action_bridge")
    add("ERROR / REVISION", enabled=bool(cfg.prediction_error_revision), mechanism_id="prediction_error_revision")
    prosp = (cog.get("prospection") if cog else None) or {}
    return {
        "stages": stages,
        "selected_action": runtime.last_selected_action,
        "branch_count": len(prosp.get("branches") or prosp.get("continuations") or []),
        "note": "Only configured stages shown; experimental stages marked in promotion_class.",
    }


def prospection_frame(
    runtime: PhysicalSystemRuntime,
    *,
    cog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bounded prospective branches with explicit future vs selected distinction."""
    if not runtime.config.cognition.cognition_enabled:
        return {"status": "INACTIVE", "branches": []}
    cog = cog if cog is not None else runtime.cognitive_view()
    prosp = cog.get("prospection") or {}
    branches = prosp.get("branches") or prosp.get("continuations") or []
    out = []
    for i, br in enumerate(branches[:8]):
        out.append({
            "branch": i + 1,
            "current": br.get("present") or br.get("start"),
            "first_action": br.get("first_action") or br.get("action"),
            "predicted_context": br.get("predicted_context") or br.get("context"),
            "future_action": (
                (br.get("future_actions") or [None])[0]
                if br.get("future_actions") is not None
                else br.get("future_action")
            ),
            "predicted_consequence": br.get("consequence") or br.get("terminal"),
            "source": br.get("source") or br.get("provenance"),
            "support": br.get("support"),
            "reliability": br.get("reliability"),
            "is_selected": br.get("first_action") == runtime.last_selected_action,
            "note": "FUTURE ACTION is not selected action unless competition chose first_action.",
        })
    return {
        "status": "ACTIVE" if out else "EMPTY",
        "selected_action_now": runtime.last_selected_action,
        "branches": out,
    }


def _physical_bundle(
    runtime: PhysicalSystemRuntime,
    *,
    agent_id: str | None = None,
    body_id: str | None = None,
    foreign_bodies: list | None = None,
) -> dict[str, Any]:
    action_work = getattr(runtime, "last_action_work_ledger", None) or {}
    motor_work = getattr(runtime, "last_motor_work_ledger", None) or {}
    work_allocation = getattr(runtime, "last_work_allocation", None) or {}
    deformation = getattr(runtime, "last_deformation_meta", None) or {}
    resources = getattr(runtime, "last_complementary_ledger", None) or {}
    agent_id = agent_id or observer_agent_id(runtime)
    body_id = body_id or observer_body_id(runtime)
    near_field_gt = None
    nfe = getattr(runtime.config, "near_field_exteroception", None)
    if nfe is not None and getattr(nfe, "enabled", False):
        from mechanistic_mind.physical_system.near_field_exteroception import (
            sample_near_field,
        )
        near_field_gt = sample_near_field(
            world=runtime.world,
            body=runtime.body,
            cfg=nfe,
            foreign_bodies=foreign_bodies,
            physical_config=runtime.config,
        )
        near_field_gt = {
            **near_field_gt,
            "perception_enabled": bool(nfe.perception_enabled),
            "body_optical_enabled": bool(getattr(nfe, "body_optical_enabled", True)),
            "illumination_intensity_world": getattr(runtime.world, "illumination_intensity", None),
            "surface_checksum": (getattr(runtime.world, "surface_meta", None) or {}).get("checksum"),
            "visual_surface_discrimination": getattr(nfe, "surface_discrimination", "OFF"),
            "optical_mapping": getattr(nfe, "optical_mapping", "INDEPENDENT"),
            "spatial_vision": getattr(nfe, "spatial_vision", "LEGACY"),
            "spatial_sectors": getattr(nfe, "n_spatial_sectors", 5),
            "surface_optical_checksum": (getattr(runtime.world, "surface_optical_meta", None) or {}).get("checksum"),
        }
    head_meta = getattr(runtime, "last_head_meta", None) or {}
    from mechanistic_mind.physical_system.vestibular_proprioception import (
        neck_proprioception_world_gt,
        vestibular_world_gt,
        VestibularConfig,
        NeckProprioceptionConfig,
    )
    vest_cfg = getattr(runtime.config, "vestibular", None) or VestibularConfig(mode="OFF")
    prop_cfg = getattr(runtime.config, "neck_proprioception", None) or NeckProprioceptionConfig(mode="OFF")
    vest_gt = vestibular_world_gt(
        runtime.body,
        vest_cfg,
        orientation_meta=getattr(runtime, "last_orientation_meta", None),
        prev_omega=float(getattr(runtime, "_prev_body_omega", 0.0) or 0.0),
    )
    prop_gt = neck_proprioception_world_gt(
        runtime.body,
        prop_cfg,
        articulated_head=getattr(runtime.config, "articulated_head", None),
        head_meta=head_meta,
    )
    from mechanistic_mind.physical_system.oscillatory_signaling import (
        OscillatorySignalingConfig,
        oscillatory_world_gt,
    )
    osc_cfg = getattr(runtime.config, "oscillatory_signaling", None) or OscillatorySignalingConfig(mode="OFF")
    osc_gt = oscillatory_world_gt(
        runtime.body,
        runtime.world,
        osc_cfg,
        articulated_head=bool(getattr(getattr(runtime.config, "articulated_head", None), "enabled", False)),
        last_step=getattr(runtime, "last_osc_meta", None),
    )
    return {
        "selected_action": runtime.last_selected_action,
        "action": action_work,
        "motor": motor_work,
        "deformation": deformation,
        "orientation": {
            "theta": float(getattr(runtime.body, "theta", 0.0)),
            "omega": float(getattr(runtime.body, "omega", 0.0)),
            "enabled": bool(getattr(runtime.config.body_orientation, "enabled", False)),
            "torque": (getattr(runtime, "last_orientation_meta", None) or {}).get("tau"),
            "action_torque": 0.0,
            "motor_torque": 0.0,
            "receipt": getattr(runtime, "last_orientation_meta", None),
            "head_relative_angle": float(getattr(runtime.body, "head_relative_angle", 0.0) or 0.0),
            "head_world_heading": float(head_meta.get("head_world_heading") or getattr(runtime.body, "theta", 0.0)),
            "head_omega": float(getattr(runtime.body, "head_omega", 0.0) or 0.0),
            "neck_motor": float(getattr(runtime.body, "neck_motor", 0.0) or 0.0),
            "articulated_head_enabled": bool(getattr(runtime.config.articulated_head, "enabled", False)),
            "ACTIVE_SENSOR_ORIENTATION": (
                "AVAILABLE"
                if bool(getattr(runtime.config.articulated_head, "enabled", False))
                else "NOT_AVAILABLE"
            ),
        },
        "near_field_exteroception": near_field_gt,
        "push": getattr(runtime, "last_push_meta", None),
        "vestibular": vest_gt,
        "neck_proprioception": prop_gt,
        "oscillatory_signaling": osc_gt,
        "resources": {
            "generic": getattr(runtime, "last_resource_ledger", None),
            "complementary": resources,
            "reservoir": float(getattr(runtime.body, "mechanical_work_reservoir", 0.0) or 0.0),
            "reservoir_capacity": float(runtime.config.deformation_work.reservoir_max),
        },
        "work_allocation": work_allocation,
        "work_ledger": getattr(runtime, "last_work_ledger", None),
        "force_contributions": getattr(runtime, "last_force_contributions", None),
        "source_agent_id": agent_id,
        "body_id": body_id,
    }


def agents_views_frame(
    runtime: PhysicalSystemRuntime,
    *,
    previous_body: dict[str, Any] | None,
    previous_bodies: dict[str, dict[str, Any]] | None = None,
    detail: str = "full",
    include_cognition: bool = True,
) -> dict[str, Any]:
    """Per-agent observer slices at the current tick. Selection does not omit peers."""
    compact = str(detail).lower() == "compact"
    _stub_cog = {"status": "DEFERRED", "reason": "unsubscribed", "observer_only": True}
    slots = getattr(runtime, "slots", None)
    prev_map = previous_bodies or {}
    if not slots:
        cog0 = None
        if include_cognition and not compact and runtime.config.cognition.cognition_enabled:
            # Canonical same-tick public view — one build for all FULL panels.
            cog0 = runtime.cognitive_view()
        return {
            "agent_0": {
                "agent_id": "agent_0",
                "body_id": "body-0",
                "agent_seed": int(runtime.seed),
                "tick": int(runtime.tick),
                "mind": (mind_compact_frame(runtime) if compact else mind_frame(runtime, cog=cog0)) if include_cognition else dict(_stub_cog),
                "body": body_frame(runtime),
                "physical": _physical_bundle(runtime),
                "agent_observation": runtime.agent_observation(),
                "causal_chain": (
                    (causal_chain_compact_frame(runtime, previous_body=previous_body)
                    if compact
                    else causal_chain_frame(runtime, previous_body=previous_body, cog=cog0))
                    if include_cognition else dict(_stub_cog)
                ),
                "cognition_pipeline": (
                    (cognition_pipeline_compact_frame(runtime)
                    if compact
                    else cognition_pipeline_frame(runtime, cog=cog0))
                    if include_cognition else dict(_stub_cog)
                ),
                "prospection_view": (
                    {"status": "DEFERRED", "detail": "compact"}
                    if (compact or not include_cognition)
                    else prospection_frame(runtime, cog=cog0)
                ),
                "perception": perception_frame(runtime) if include_cognition else dict(_stub_cog),
            }
        }
    # Access each PhysicalSystemRuntime slot directly — never fall back across agents.
    prev_selected = int(getattr(runtime, "selected_index", 0) or 0)
    out: dict[str, Any] = {}
    # Generation is stamped by session capture onto the outer frame; views carry tick only
    # unless the runtime exposes an observer generation attribute.
    generation = getattr(runtime, "_observer_runtime_generation", None)
    try:
        from mechanistic_mind.ui.psy_observer_web.undercover_identity import slot_agent_body_ids
        exp_slot = getattr(runtime, "experimenter_slot", None)
        for i, slot in enumerate(slots):
            runtime.selected_index = i  # observer projection only; restored below
            aid, bid = slot_agent_body_ids(i, experimenter_slot=exp_slot)
            cog_slot = None
            if include_cognition and not compact and slot.config.cognition.cognition_enabled:
                # Canonical same-tick public view — one build per agent for all FULL panels.
                cog_slot = slot.cognitive_view()
            mind = (
                mind_compact_frame(slot, agent_id=aid, body_id=bid)
                if compact
                else mind_frame(slot, agent_id=aid, body_id=bid, cog=cog_slot)
            ) if include_cognition else dict(_stub_cog)
            # Prefer per-agent previous body; fall back to selected-only buffer for compat.
            slot_prev = prev_map.get(aid) or prev_map.get(f"agent_{i}")
            if slot_prev is None and i == prev_selected:
                slot_prev = previous_body
            foreign = [
                (slots[j].body, slots[j].config.body)
                for j in range(len(slots))
                if j != i
            ]
            phys = _physical_bundle(slot, agent_id=aid, body_id=bid, foreign_bodies=foreign)
            # Agent-accessible observation with the same foreign_bodies as cognition tick path.
            agent_obs = slot.agent_observation(foreign_bodies=foreign)
            if compact and i != prev_selected and isinstance(phys, dict):
                # Peer agents: drop bulky ledgers on RUNNING compact frames, but keep
                # a vision stub so COMPARE / re-projection is not structurally blind.
                nf = phys.get("near_field_exteroception")
                nf_stub = None
                if isinstance(nf, dict):
                    nf_stub = {
                        "vision_contributes": nf.get("vision_contributes"),
                        "perception_enabled": nf.get("perception_enabled"),
                        "body_optical_enabled": nf.get("body_optical_enabled"),
                        "illumination": nf.get("illumination"),
                        "fragments": nf.get("fragments"),
                        "n_body_optical_cells": nf.get("n_body_optical_cells"),
                        "n_detectable": nf.get("n_detectable"),
                        "body_theta": nf.get("body_theta"),
                        "head_relative_angle": nf.get("head_relative_angle"),
                        "head_world_heading": nf.get("head_world_heading"),
                        "sensor_forward_axis": nf.get("sensor_forward_axis"),
                        "fov_deg": nf.get("fov_deg"),
                        "vision_radius": nf.get("vision_radius") or nf.get("radius"),
                        "radius": nf.get("radius") or nf.get("vision_radius"),
                        "max_candidates": nf.get("max_candidates"),
                        "n_candidates": nf.get("n_candidates"),
                        "fragments": nf.get("fragments"),
                        "surface_fragments": nf.get("surface_fragments"),
                        "visual_surface_discrimination": nf.get("visual_surface_discrimination"),
                        "optical_mapping": nf.get("optical_mapping"),
                        "spatial_vision": nf.get("spatial_vision"),
                        "spatial_sectors": nf.get("spatial_sectors"),
                        "spatial_fragments": nf.get("spatial_fragments"),
                        "n_occluded": nf.get("n_occluded"),
                        "detail": "compact",
                    }
                phys = {
                    "selected_action": phys.get("selected_action"),
                    "orientation": {
                        "theta": (phys.get("orientation") or {}).get("theta")
                        if isinstance(phys.get("orientation"), dict)
                        else None,
                        "status": "COMPACT",
                    },
                    "resources": phys.get("resources"),
                    "near_field_exteroception": nf_stub,
                    "source_agent_id": phys.get("source_agent_id"),
                    "body_id": phys.get("body_id"),
                    "detail": "compact",
                    "note": "Full physical/work ledgers on PAUSE/INSPECT or selected agent.",
                }
            out[aid] = {
                "agent_id": aid,
                "body_id": bid,
                "agent_seed": int(slot.seed),
                "tick": int(slot.tick),
                "generation": generation,
                "mind": mind,
                "body": body_frame(slot, agent_id=aid, body_id=bid),
                "physical": phys,
                "agent_observation": agent_obs,
                "causal_chain": (
                    causal_chain_compact_frame(slot, previous_body=slot_prev)
                    if compact
                    else causal_chain_frame(slot, previous_body=slot_prev, cog=cog_slot)
                ),
                "cognition_pipeline": (
                    cognition_pipeline_compact_frame(slot)
                    if compact
                    else cognition_pipeline_frame(slot, cog=cog_slot)
                ),
                "prospection_view": (
                    {"status": "DEFERRED", "detail": "compact", "source_agent_id": aid}
                    if compact
                    else prospection_frame(slot, cog=cog_slot)
                ),
                "perception": perception_frame(slot, foreign_bodies=foreign),
            }
            # Hard guard: never cross-serve
            if out[aid]["mind"].get("source_agent_id") not in (None, aid):
                raise RuntimeError(f"mind cross-serve: expected {aid}, got {out[aid]['mind'].get('source_agent_id')}")
            if out[aid]["body"].get("agent_id") not in (None, aid):
                raise RuntimeError(f"body cross-serve: expected {aid}, got {out[aid]['body'].get('agent_id')}")
            if int(out[aid]["agent_seed"]) != int(slot.seed):
                raise RuntimeError(f"seed mismatch for {aid}")
            if out[aid]["body_id"] != bid:
                raise RuntimeError(f"body_id mismatch for {aid}: expected {bid}")
    finally:
        runtime.selected_index = prev_selected
    return out


def _effector_relative_z_diagnostics(runtime: PhysicalSystemRuntime) -> dict[str, Any]:
    """Researcher-only per-hand relative_z motor diagnostics (not cognition)."""
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        manipulator_relative_world_actuation_is_active,
        relative_z_of,
    )
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        effector_bounded_actuator_effort_is_active,
    )

    mo = getattr(runtime, "last_motor_output", None) or {}
    avail = False
    try:
        avail = bool(
            manipulator_relative_world_actuation_is_active(runtime.config)
            and effector_bounded_actuator_effort_is_active(runtime.config)
        )
    except Exception:
        avail = False
    body_id = str(getattr(runtime, "technical_id", None) or "agent_0")
    try:
        from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

        refs = body_refs_for_runtime(runtime)
        if refs:
            body_id = str(refs[0][0])
    except Exception:
        pass
    act = getattr(runtime, "last_agent_effector_z_actuation", None)
    if not isinstance(act, dict):
        act = {}

    def _hand(label: str, factor_key: str) -> dict[str, Any]:
        factor = int(mo.get(factor_key) or 0)
        if factor > 0:
            selected = "UP"
        elif factor < 0:
            selected = "DOWN"
        else:
            selected = "NONE"
        rz = 0.0
        try:
            if avail:
                rz = float(relative_z_of(runtime.world, body_id, label, config=runtime.config))
        except Exception:
            rz = 0.0
        rec = act.get(label.lower())
        if not isinstance(rec, dict):
            rec = {}
        return {
            "factor_available": bool(avail),
            "selected": selected,
            "relative_z": rz,
            "requested_delta": rec.get("requested_relative_delta"),
            "realized_delta": rec.get("achieved_relative_delta"),
            "rate_clipped": rec.get("rate_clipped"),
            "reach_clipped": rec.get("reach_clipped"),
            "work_used": rec.get("work_used"),
            "status": rec.get("status") or act.get("status"),
        }

    return {
        "available": bool(avail),
        "LEFT": _hand("LEFT", "effector_z_left"),
        "RIGHT": _hand("RIGHT", "effector_z_right"),
        "note": "Researcher diagnostics only — numeric relative_z not cognition-visible.",
    }


def motor_control_status_frame(runtime: PhysicalSystemRuntime) -> dict[str, Any]:
    """Observer: CURRENT MOTOR OUTPUT vs ACTIVE EFFECTORS vs PASSIVE INPUT."""
    mo = getattr(runtime, "last_motor_output", None) or {}
    body = runtime.body
    osc_cfg = getattr(runtime.config, "oscillatory_signaling", None)
    head_on = bool(getattr(runtime.config.articulated_head, "enabled", False))
    vest_on = bool(getattr(getattr(runtime.config, "vestibular", None), "enabled", False))
    prop_on = bool(getattr(getattr(runtime.config, "neck_proprioception", None), "enabled", False))
    nfe_on = bool(getattr(runtime.config.near_field_exteroception, "enabled", False))
    sig_on = bool(getattr(runtime.config.physical_signal, "enabled", False))
    osc_on = bool(getattr(osc_cfg, "enabled", False)) if osc_cfg else False
    osc = mo.get("oscillator") if isinstance(mo.get("oscillator"), dict) else {}
    rem = int(getattr(body, "osc_emit_remaining", 0) or 0)
    return {
        "schema": mo.get("schema") or (
            "COMPOSITE_MOTOR_V1"
            if bool(getattr(runtime.config.cognition, "composite_motor", True))
            else "LEGACY_SINGLE_SLOT"
        ),
        "current_motor_output": {
            "locomotion": mo.get("locomotion") or runtime.last_selected_action or "WAIT",
            "neck": mo.get("neck") or "NONE",
            "oscillator": {
                "freq_delta": int(osc.get("frequency_delta") or 0),
                "amp_delta": int(osc.get("amplitude_delta") or 0),
                "emit_trigger": bool(osc.get("emit_trigger")),
            },
            "push": bool(mo.get("push")),
            "effector_z_left": int(mo.get("effector_z_left") or 0),
            "effector_z_right": int(mo.get("effector_z_right") or 0),
            "display": mo.get("display") or runtime.last_selected_action,
            "note": "Structured motor output — not a Cartesian compound action token.",
        },
        "effector_relative_z": _effector_relative_z_diagnostics(runtime),
        "active_effectors": {
            "body_locomotor_force": "ACTIVE"
            if str(mo.get("locomotion") or "").startswith("MOVE:")
            else "IDLE",
            "neck_torque": mo.get("neck") if (mo.get("neck") and mo.get("neck") != "NONE") else "NONE",
            "head_angle": float(getattr(body, "head_relative_angle", 0.0) or 0.0),
            "head_omega": float(getattr(body, "head_omega", 0.0) or 0.0),
            "oscillator": "EMITTING" if rem > 0 else "IDLE",
            "osc_freq": float(getattr(body, "osc_freq_u", 0.5) or 0.5),
            "osc_amp": float(getattr(body, "osc_amp_u", 0.5) or 0.5),
            "osc_remaining": rem,
            "push_exertion": float(getattr(body, "push_exertion", 0.0) or 0.0),
        },
        "passive_input": {
            "vision": "ACTIVE" if nfe_on else "OFF",
            "osc_reception": "ACTIVE" if osc_on else "OFF",
            "vestibular": "ACTIVE" if vest_on else "OFF",
            "neck_proprioception": "ACTIVE" if prop_on else "OFF",
            "legacy_fields": "ACTIVE" if sig_on else "OFF",
            "note": "Passive sensory pathways — not actions; no LISTEN/SEE slot.",
        },
        "articulated_head_enabled": head_on,
    }


def signal_forensics_frame(runtime: PhysicalSystemRuntime, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Read-only emission/reception table for the selected agent. Not communication."""
    selected = observer_agent_id(runtime)
    emitted = []
    received = []
    osc_episodes: list[dict[str, Any]] = []
    emit_starts = []
    for ev in events:
        et = str(ev.get("type") or ev.get("kind") or "")
        evidence = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else {}
        if et == "OSC_EMISSION_STARTED":
            emit_starts.append({"tick": ev.get("tick"), "evidence": evidence})
        emitter = (
            ev.get("emitter_agent_id")
            or evidence.get("emitter_agent_id")
        )
        receiver = (
            ev.get("receiver_agent_id")
            or evidence.get("receiver_agent_id")
            or evidence.get("observer_receiver_id")
        )
        observer_src = ev.get("observer_source_id") or evidence.get("observer_source_id")
        row = {
            "tick": ev.get("tick"),
            "event_id": ev.get("id") or ev.get("event_id"),
            "emission_id": evidence.get("emission_id"),
            "type": et,
            "agent": emitter if "EMITTED" in et else (receiver or "UNKNOWN"),
            "observer_source_id": observer_src,
            "channel": evidence.get("channel") or evidence.get("field") or (
                "FIELD_A" if evidence.get("local.FIELD_A") else ("FIELD_B" if evidence.get("local.FIELD_B") else None)
            ),
            "position": evidence.get("position") or evidence.get("xy") or (
                [evidence.get("x"), evidence.get("y")] if evidence.get("x") is not None else None
            ),
            "intensity": evidence.get("intensity") or evidence.get("magnitude") or evidence.get("realized")
            or evidence.get("local.FIELD_A") or evidence.get("local.FIELD_B"),
            "origin_kind": evidence.get("origin_kind"),
            "origin_id": evidence.get("origin_id"),
            "emitter_body_id": evidence.get("emitter_body_id") or evidence.get("body_id"),
            "contact": {
                "a": evidence.get("contact_entity_a_id"),
                "b": evidence.get("contact_entity_b_id"),
            } if evidence.get("contact_entity_a_id") or evidence.get("contact_entity_b_id") else None,
            "counterparty": (
                receiver if "EMITTED" in et else (evidence.get("source_agent_id") or "UNKNOWN")
            ),
            "source_attribution": evidence.get("source_attribution"),
            "causal_parent_ids": evidence.get("causal_parent_ids") or [],
            "distance": evidence.get("distance") or evidence.get("com_distance"),
            "pairing": "PAIRING NOT DEMONSTRATED",
            "note": "Physical signal event — not communication.",
            "evidence": evidence,
        }
        # Match selected agent as emitter OR as observer stream that recorded it
        if "EMITTED" in et and (emitter == selected or observer_src == selected or ev.get("agent_id") == selected):
            emitted.append(row)
        if "RECEIVED" in et and (receiver == selected or ev.get("agent_id") == selected):
            if row["counterparty"] in (None, "", "UNKNOWN"):
                row["counterparty"] = "UNKNOWN"
                row["source"] = evidence.get("source") or "NOT_RECORDED"
            received.append(row)
    # Episode view: trigger ≠ active ticks
    body = runtime.body
    rem = int(getattr(body, "osc_emit_remaining", 0) or 0)
    for st in emit_starts[-10:]:
        osc_episodes.append({
            "start_tick": st.get("tick"),
            "representation": "EMISSION_START → ACTIVE_INTERVAL → EMISSION_END",
            "note": "Do not count each active tick as a separate OSC_EMIT control.",
        })
    duplex = {
        "emitting": rem > 0 or float(getattr(body, "osc_emit_active", 0.0) or 0.0) > 0.0,
        "receiving": True,  # continuous transduction when osc ON
        "full_duplex": True,
        "half_duplex_rule": False,
        "turn_taking_rule": False,
        "speaker_listener_roles": False,
        "note": "Emit and receive may coexist; cognition sees anonymous osc_l_*/osc_r_* only.",
    }
    return {
        "selected_agent_id": selected,
        "signals_emitted": emitted[-20:],
        "signals_received": received[-20:],
        "osc_emission_episodes": osc_episodes,
        "full_duplex": duplex,
        "note": "Observer forensics only. Physical signal exchange is not communication.",
    }


def enrich_structured_event(ev: dict[str, Any], *, agent_id: str, body_id: str) -> dict[str, Any]:
    """Add observer attribution without inventing causal links.

    Distinguishes:
      - emitter_agent_id / emitter_body_id: physical deposit origin
      - receiver_agent_id / receiver_body_id: local field sample recipient
      - observer_source_id: instrumentation stream that recorded the event
    Never substitute observer_source_id for emitter identity.
    """
    row = dict(ev)
    evidence = dict(row.get("evidence") or {}) if isinstance(row.get("evidence"), dict) else {}
    et = str(row.get("type") or row.get("kind") or "")
    # Buffer owner is the observer stream unless evidence already stamped one.
    observer_source = evidence.get("observer_source_id") or agent_id
    evidence.setdefault("observer_source_id", observer_source)
    row["observer_source_id"] = observer_source
    row["agent_id"] = agent_id  # buffer owner (instrumentation), not necessarily emitter

    if "EMITTED" in et:
        emitter = evidence.get("emitter_agent_id")
        if emitter in (None, "", "UNKNOWN") and evidence.get("slot") is not None:
            emitter = f"agent_{int(evidence['slot'])}"
        if emitter in (None, ""):
            emitter = "UNKNOWN"
        emitter_body = evidence.get("emitter_body_id") or evidence.get("body_id")
        if emitter_body in (None, "", "UNKNOWN") and evidence.get("slot") is not None:
            emitter_body = f"body-{int(evidence['slot'])}"
        if emitter_body in (None, ""):
            emitter_body = "UNKNOWN"
        # Do NOT fall back emitter → buffer owner (that was the hybrid identity bug).
        row["emitter_agent_id"] = emitter
        row["emitter_body_id"] = emitter_body
        row["body_id"] = emitter_body
        row["actor_agent_id"] = emitter if emitter != "UNKNOWN" else observer_source
        evidence["emitter_agent_id"] = emitter
        evidence["emitter_body_id"] = emitter_body
        evidence["body_id"] = emitter_body
        evidence.setdefault("origin_kind", evidence.get("origin_kind") or "NOT_RECORDED")
        evidence.setdefault("origin_id", evidence.get("origin_id") or "NOT_RECORDED")
        # Never invent source_agent_id from observer for emissions
        if "source_agent_id" in evidence and evidence.get("source_agent_id") == observer_source and emitter == "UNKNOWN":
            evidence["source_agent_id"] = "UNKNOWN"
    elif "RECEIVED" in et:
        receiver = evidence.get("receiver_agent_id") or evidence.get("observer_receiver_id") or agent_id
        receiver_body = evidence.get("receiver_body_id") or evidence.get("body_id") or body_id
        row["actor_agent_id"] = receiver
        row["receiver_agent_id"] = receiver
        row["receiver_body_id"] = receiver_body
        row["body_id"] = receiver_body
        evidence.setdefault("receiver_agent_id", receiver)
        evidence.setdefault("receiver_body_id", receiver_body)
        evidence["body_id"] = receiver_body
        # Never invent a unique physical source from the observer stream
        if evidence.get("source_agent_id") in (None, ""):
            evidence["source_agent_id"] = "UNKNOWN"
        if evidence.get("source_body_id") in (None, ""):
            evidence["source_body_id"] = "UNKNOWN"
        evidence.setdefault("source_attribution", "NOT_UNIQUELY_ATTRIBUTABLE")
        evidence.setdefault("source", evidence.get("source") or "NOT_RECORDED")
        row["source_agent_id"] = evidence.get("source_agent_id") or "UNKNOWN"
        row["source_attribution"] = evidence.get("source_attribution")
        row["causal_parent_ids"] = evidence.get("causal_parent_ids") or []
        row["contributing_emissions_this_tick"] = evidence.get("contributing_emissions_this_tick") or []
    else:
        row["actor_agent_id"] = agent_id
        evidence.setdefault("actor_agent_id", agent_id)
        evidence.setdefault("body_id", body_id)
        row["body_id"] = body_id
    row["evidence"] = evidence
    return row

def collect_observer_events(runtime: PhysicalSystemRuntime, *, limit: int = 200) -> list[dict[str, Any]]:
    """All agents' structured events with attribution. Observer-only."""
    slots = getattr(runtime, "slots", None)
    if slots:
        out: list[dict[str, Any]] = []
        for i, slot in enumerate(slots):
            buf = getattr(slot, "structured_events", None)
            if buf is None:
                continue
            aid, bid = f"agent_{i}", f"body-{i}"
            for ev in buf.list(limit=max(12, limit // max(1, len(slots)))):
                out.append(enrich_structured_event(dict(ev), agent_id=aid, body_id=bid))
        contact = getattr(runtime, "last_contact", None) or {}
        if contact.get("contact"):
            out.append({
                "type": "CONTACT",
                "tick": int(runtime.tick),
                "agent_id": "observer",
                "actor_agent_id": "observer",
                "evidence": {
                    "com_distance": contact.get("com_distance"),
                    "overlap_n": len(contact.get("overlap_cells") or []),
                },
            })
        out.sort(key=lambda e: (int(e.get("tick") or 0), str(e.get("type") or "")))
        return out[-limit:]
    buf = getattr(runtime, "structured_events", None)
    if buf is None:
        return []
    return [
        enrich_structured_event(dict(ev), agent_id="agent_0", body_id="body-0")
        for ev in buf.list(limit=limit)
    ]


def collect_observer_events_for_tick(
    runtime: PhysicalSystemRuntime,
    *,
    tick: int,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Current-tick structured events only — same enrich/sort contract as collect_observer_events.

    Used by Session drain to avoid reprocessing older buffer entries every tick.
    Ordering among same-tick events remains (tick, type) — identical to filtering the
    full collect_observer_events result to this tick.
    """
    tick = int(tick)
    slots = getattr(runtime, "slots", None)
    out: list[dict[str, Any]] = []
    if slots:
        for i, slot in enumerate(slots):
            buf = getattr(slot, "structured_events", None)
            if buf is None:
                continue
            aid, bid = f"agent_{i}", f"body-{i}"
            # Scan from the end; buffer is append-ordered by emission time ≈ tick order.
            items = list(getattr(buf, "_buf", ()) or buf.list(limit=max(24, limit)))
            for ev in reversed(items):
                if int(ev.get("tick") or -1) < tick:
                    break
                if int(ev.get("tick") or -1) != tick:
                    continue
                out.append(enrich_structured_event(dict(ev), agent_id=aid, body_id=bid))
        contact = getattr(runtime, "last_contact", None) or {}
        if contact.get("contact") and int(runtime.tick) == tick:
            out.append({
                "type": "CONTACT",
                "tick": tick,
                "agent_id": "observer",
                "actor_agent_id": "observer",
                "evidence": {
                    "com_distance": contact.get("com_distance"),
                    "overlap_n": len(contact.get("overlap_cells") or []),
                },
            })
    else:
        buf = getattr(runtime, "structured_events", None)
        if buf is not None:
            items = list(getattr(buf, "_buf", ()) or buf.list(limit=limit))
            for ev in reversed(items):
                if int(ev.get("tick") or -1) < tick:
                    break
                if int(ev.get("tick") or -1) != tick:
                    continue
                out.append(enrich_structured_event(dict(ev), agent_id="agent_0", body_id="body-0"))
    out.sort(key=lambda e: (int(e.get("tick") or 0), str(e.get("type") or "")))
    return out[-limit:]


def _physical_body_inventory_frame(runtime: PhysicalSystemRuntime) -> dict[str, Any]:
    """Observer/developer diagnostic — never cognition input."""
    from mechanistic_mind.ui.psy_observer_web.undercover_identity import (
        detect_legacy_duplicate_undercover_ids,
        physical_body_inventory,
    )

    inv = physical_body_inventory(runtime)
    aids = [str(b.get("agent_id") or "") for b in inv.get("bodies") or []]
    inv["legacy"] = detect_legacy_duplicate_undercover_ids(aids)
    return inv


def _stamp_live_psc_schedule_on_experiment(runtime: Any, experiment: Any) -> dict[str, Any]:
    """Overlay live PSC schedule onto a possibly tick-stable experiment fragment.

    FAMILY_EXPERIMENT_CONFIG is a stable cache family keyed without tick / PSC
    activation. Reusing that fragment as Current-runtime readback hid the tick-1000
    transition in the packaged Observer even when the runtime had already armed.
    """
    exp = dict(experiment) if isinstance(experiment, dict) else {}
    rt_block = dict(exp.get("runtime") or {})
    try:
        from mechanistic_mind.ui.psy_observer_web.tiktaalik_eye import psc_off_ticks_status

        rt_block["psc_schedule"] = psc_off_ticks_status(runtime)
        rt_block["psc_off_ticks"] = getattr(
            getattr(getattr(runtime, "config", None), "cognition", None),
            "psc_off_ticks",
            rt_block.get("psc_off_ticks"),
        )
    except Exception:
        pass
    exp["runtime"] = rt_block
    return exp


def live_frame(
    runtime: PhysicalSystemRuntime,
    *,
    status: str,
    mode: str,
    target_tick: int | None,
    previous_body: dict[str, Any] | None,
    max_side: int = 64,
    detail: str = "full",
    structured_events: list[dict[str, Any]] | None = None,
    previous_bodies: dict[str, dict[str, Any]] | None = None,
    geometry_traversability: dict[str, Any] | None = None,
    include_cognition: bool = True,
    observer_interest: Any | None = None,
) -> dict[str, Any]:
    from mechanistic_mind.ui.psy_observer_web.observer_derived_payload_subscription import (
        resolve_derived_subscription,
    )
    from mechanistic_mind.ui.psy_observer_web import observer_serialization_fragment_cache as _p4cache

    _derived = resolve_derived_subscription(observer_interest)
    _p4_run = _p4cache.run_id_for_runtime(runtime)
    _p4_gen = int(getattr(runtime, "_observer_runtime_generation", 0) or 0)
    _p4_cfg = _p4cache.config_authority_token(runtime)
    mechanisms = _p4cache.get_or_build(
        family=_p4cache.FAMILY_MECHANISM_SNAPSHOT,
        authority_key={
            "run_id": _p4_run,
            "runtime_generation": _p4_gen,
            "config": _p4_cfg,
            "family": _p4cache.FAMILY_MECHANISM_SNAPSHOT,
        },
        builder=lambda: __import__(
            "mechanistic_mind.physical_system.mechanism_registry",
            fromlist=["mechanism_snapshot"],
        ).mechanism_snapshot(runtime.config),
    )
    physical = _physical_bundle(runtime)
    action_work = physical.get("action") or {}
    motor_work = physical.get("motor") or {}
    resources = (physical.get("resources") or {}).get("complementary") or {}
    compact = str(detail).lower() == "compact"
    events = structured_events if structured_events is not None else collect_observer_events(runtime, limit=40)
    agent_id = observer_agent_id(runtime)
    body_id = observer_body_id(runtime)
    views = agents_views_frame(
        runtime,
        previous_body=previous_body,
        previous_bodies=previous_bodies,
        detail=detail,
        include_cognition=include_cognition,
    )
    from mechanistic_mind.ui.psy_observer_web.geometry.live_summary import (
        geometry_live_compact_summary,
    )

    geometry_interp = geometry_live_compact_summary(
        runtime,
        previous_body=previous_body,
        previous_bodies=previous_bodies,
        traversability_overlay=geometry_traversability,
        include_flow_overlay=not compact,
        flow_stride=2,
    )
    # Never fall back to another agent's view — that produces hybrid identity screens.
    selected_view = views.get(agent_id)
    if selected_view is None:
        selected_view = {
            "agent_id": agent_id,
            "body_id": body_id,
            "agent_seed": None,
            "tick": int(runtime.tick),
            "mind": {
                "status": "NOT AVAILABLE",
                "source_agent_id": agent_id,
                "agent_id": agent_id,
                "body_id": body_id,
                "reason": f"agents_views[{agent_id}] missing",
            },
            "body": {
                "id": body_id,
                "body_id": body_id,
                "agent_id": agent_id,
                "status": "NOT AVAILABLE",
                "reason": f"agents_views[{agent_id}] missing",
            },
            "physical": {"source_agent_id": agent_id, "body_id": body_id, "status": "NOT AVAILABLE"},
            "causal_chain": {"status": "NOT AVAILABLE"},
            "cognition_pipeline": {"status": "NOT AVAILABLE", "stages": []},
            "prospection_view": {"status": "NOT AVAILABLE", "branches": []},
            "perception": {"status": "NOT AVAILABLE"},
        }
    header = header_info(runtime, status=status, mode=mode, target_tick=target_tick)
    if compact:
        mech_summary = {
            "detail": "compact",
            "enabled_ids": sorted(
                k for k, v in (mechanisms or {}).items()
                if isinstance(v, dict) and v.get("enabled")
            ) if isinstance(mechanisms, dict) else [],
            "note": "Full mechanism snapshot on PAUSE/INSPECT.",
        }
        # Prefer list-of-id form when mechanisms is a plain enable map
        if isinstance(mechanisms, dict) and mechanisms and not any(
            isinstance(v, dict) for v in mechanisms.values()
        ):
            mech_summary["enabled_ids"] = sorted(k for k, v in mechanisms.items() if v)
        model_banner = {
            **(runtime.model_identity() if hasattr(runtime, "model_identity") else {}),
            "model": (
                runtime.model_identity().get("display_name")
                if hasattr(runtime, "model_identity")
                else "MM 1.0 — Tiktaalik"
            ),
            "runtime_version": getattr(runtime.config, "runtime_version", "MM_1_0_TIKTAALIK"),
            "mechanisms": mech_summary,
            "force_contributions": "DEFERRED",
            "frame_detail": "compact",
        }
        events_out = events[-16:] if isinstance(events, list) else events
    else:
        model_banner = {
            **(runtime.model_identity() if hasattr(runtime, "model_identity") else {}),
            "model": (
                runtime.model_identity().get("display_name")
                if hasattr(runtime, "model_identity")
                else "MM 1.0 — Tiktaalik"
            ),
            "runtime_version": getattr(runtime.config, "runtime_version", "MM_1_0_TIKTAALIK"),
            "mechanisms": mechanisms,
            "force_contributions": getattr(runtime, "last_force_contributions", None),
        }
        events_out = events
    _want_eye_dock_dual_fpv = bool(len(getattr(runtime, "slots", None) or []) >= 2) or bool(
        observer_interest is not None
        and getattr(observer_interest, "wants", lambda _p: False)("eye_dock_dual_fpv")
    )
    _world_auth = {
        "run_id": _p4_run,
        "runtime_generation": _p4_gen,
        "config": _p4_cfg,
        "scientific_tick": int(runtime.tick),
        "detail": detail,
        "max_side": int(max_side),
        "subscription": _p4cache.subscription_token(_derived),
        # Dual FPV map is not part of P1 derived volume/surface token; include explicitly
        # so Hearing/Vision interest toggles cannot reuse a stale world fragment.
        "eye_dock_dual_fpv": _want_eye_dock_dual_fpv,
        "vw1": _p4cache.vw1_digest_token(runtime),
        "entities": _p4cache.entity_revision_token(runtime),
        "volume_held": str(getattr(runtime, "_observer_volume_held_static_id", None) or ""),
        "surface_held": str(getattr(runtime, "_observer_surface_held_static_id", None) or ""),
        "family": _p4cache.FAMILY_WORLD_FRAME,
    }
    _world_was_cached = _p4cache.has_entry(family=_p4cache.FAMILY_WORLD_FRAME, authority_key=_world_auth)
    _world = _p4cache.get_or_build(
        family=_p4cache.FAMILY_WORLD_FRAME,
        authority_key=_world_auth,
        builder=lambda: world_frame(
            runtime,
            max_side=max_side,
            detail=detail,
            observer_interest=observer_interest,
            derived_subscription=_derived,
        ),
    )
    if _world_was_cached:
        # Preserve O5 poll-skip accounting when WORLD fragment is reused (no rebuild side effects).
        try:
            from mechanistic_mind.physical_system.sensory_modality_temporal_alignment import (
                note_observer_poll_skip,
                sensory_modality_temporal_alignment_is_active,
            )
            if sensory_modality_temporal_alignment_is_active(runtime.config):
                note_observer_poll_skip(runtime.world)
        except Exception:
            pass
    _sub_meta = _derived.as_frame_meta(
        runtime_generation=int(getattr(runtime, "_observer_runtime_generation", 0) or 0) or None,
    )
    return {
        "header": header,
        "observer": {
            "selected_agent_id": agent_id,
            "selected_body_id": body_id,
            "inspected_tick": int(runtime.tick),
            "runtime_generation": None,  # filled by session capture
            "identity_tuple": {
                "inspected_tick": int(runtime.tick),
                "selected_agent_id": agent_id,
                "selected_body_id": body_id,
                "agent_seed": selected_view.get("agent_seed"),
            },
            "agent_body_mapping": header.get("agent_body_mapping"),
            "frame_detail": "compact" if compact else "full",
            "note": "Observer-only selection. Does not alter cognition, RNG, or physics.",
        },
        "world": _world,
        "observer_derived_payload_subscription": _sub_meta,
        # Top-level fields are convenience projections of the SAME agents_views entry only.
        "perception": selected_view.get("perception"),
        "body": selected_view.get("body"),
        "internal_physical": internal_physical_frame(runtime),
        "mind": selected_view.get("mind"),
        "causal_chain": selected_view.get("causal_chain"),
        "physical": selected_view.get("physical"),
        "agent_observation": selected_view.get("agent_observation")
        or ((selected_view.get("perception") or {}).get("agent_observation")),
        "agents_views": views,
        "model_banner": model_banner,
        "cognition_pipeline": selected_view.get("cognition_pipeline"),
        "prospection_view": selected_view.get("prospection_view"),
        "geometry_interpretation": geometry_interp,
        "structured_events": events_out,
        "signal_forensics": signal_forensics_frame(runtime, events_out if compact else events),
        "motor_control": motor_control_status_frame(runtime),
        "agents_observer": _agents_observer_frame(runtime),
        "physical_body_inventory": _physical_body_inventory_frame(runtime),
        "contact": getattr(runtime, "last_contact", None),
        "physical_signal": getattr(runtime, "last_signal_receipt", None),
        "experiment": _stamp_live_psc_schedule_on_experiment(
            runtime,
            _p4cache.get_or_build(
                family=_p4cache.FAMILY_EXPERIMENT_CONFIG,
                authority_key={
                    "run_id": _p4_run,
                    "runtime_generation": _p4_gen,
                    "config": _p4_cfg,
                    "detail": detail,
                    "selected_agent_id": agent_id,
                    "family": _p4cache.FAMILY_EXPERIMENT_CONFIG,
                },
                builder=lambda: experiment_config_frame(runtime, detail=detail),
            ),
        ),
        "honesty": _p4cache.get_or_build(
            family=_p4cache.FAMILY_HONESTY,
            authority_key={
                "run_id": _p4_run,
                "runtime_generation": _p4_gen,
                "config": _p4_cfg,
                "detail": "compact" if compact else "full",
                "family": _p4cache.FAMILY_HONESTY,
            },
            builder=lambda: {
                "unsupported_boundary_modes": ["CLOSED", "OPEN"],
                "unavailable_perception": perception_frame(runtime)["unavailable"],
                "replay_limit": "bounded recorded frames only",
                "predicted_spatial_field": "NOT_AVAILABLE",
                "physical_emit_bridge": "NOT_AVAILABLE",
                "scientific_status_is_not_enabled_state": True,
                "signal_is_not_communication": True,
                "simulation_acceleration_only": True,
                "frame_detail": "compact" if compact else "full",
            },
        ),
        "observer_perf": {
            "captured_tick": int(runtime.tick),
            "frame_detail": "compact" if compact else "full",
            "include_cognition": bool(include_cognition),
            "cognitive_view_cache": (
                runtime.cognitive_view_cache_stats()
                if hasattr(runtime, "cognitive_view_cache_stats")
                else {}
            ),
            "note": (
                "LIVE compact avoids FULL cognition_public_view. "
                "FULL builds one canonical public view per agent/tick."
            ),
            **(
                {"serialization_fragment_cache": _p4cache.stats()}
                if _p4cache.telemetry_enabled()
                else {}
            ),
        },
        "overview_facts": {
            "tick": int(runtime.tick),
            "selected_agent_id": agent_id,
            "selected_action": runtime.last_selected_action,
            "requested_action_delta_v": action_work.get("action_dv_requested"),
            "realized_action_delta_v": action_work.get("action_dv_realized"),
            "action_work_limit_fraction": action_work.get("action_work_limit_fraction"),
            "motor_drive": motor_work.get("motor_drive_requested"),
            "motor_realized_delta_v": motor_work.get("motor_delta_v_realized"),
            "environmental_force": (getattr(runtime, "last_force_contributions", None) or {}).get("environmental_site"),
            "theta": float(getattr(runtime.body, "theta", 0.0)),
            "torque": (getattr(runtime, "last_orientation_meta", None) or {}).get("tau"),
            "resource_conversion_work": resources.get("work_credited"),
            "sources": ["runtime state", "work ledgers", "motion/orientation receipts"],
        },
    }


def _structured_events_with_agent_id(runtime: PhysicalSystemRuntime) -> list[dict[str, Any]]:
    return collect_observer_events(runtime, limit=40)

def _attach_composite_action_display(runtime: PhysicalSystemRuntime, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Observer HUD only: final applied CompositeMotorOutput per agent."""
    from mechanistic_mind.ui.psy_observer_web.composite_action_display import (
        observer_applied_composite_action_display_for_runtime,
    )

    slots = getattr(runtime, "slots", None)
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows or []):
        r = dict(row)
        src = slots[i] if slots and i < len(slots) else runtime
        r["composite_action_display"] = observer_applied_composite_action_display_for_runtime(src)
        out.append(r)
    return out


def _agents_observer_frame(runtime: PhysicalSystemRuntime) -> list[dict[str, Any]]:
    """HUD / strip agent rows for N>=1. Always a list (never null).

    TwoAgentRuntime already exposes observer_agent_summaries. Single-agent
    PhysicalSystemRuntime must still surface agent_0 + selected_action so the
    bottom strip does not fall back to body.selected_action (which body_frame
    does not carry).
    """
    if hasattr(runtime, "observer_agent_summaries"):
        rows = runtime.observer_agent_summaries()
        return _attach_composite_action_display(runtime, list(rows or []))
    # Prefer shared helper (same shape used at finalize)
    try:
        from mechanistic_mind.ui.psy_observer_web.run_finalize import agent_summaries

        return _attach_composite_action_display(runtime, list(agent_summaries(runtime) or []))
    except Exception:
        pass
    return _attach_composite_action_display(runtime, [{
        "observer_id": "agent_0",
        "agent_id": "agent_0",
        "body_id": "body-0",
        "x": float(runtime.body.x),
        "y": float(runtime.body.y),
        "selected_action": runtime.last_selected_action,
        "tick": int(runtime.tick),
        "agent_seed": int(runtime.seed),
    }])


def compact_history_from_runtime(runtime: PhysicalSystemRuntime, *, status: str | None = None) -> dict[str, Any]:
    """Per-tick Observer marker from runtime — no world grids, no live_frame."""
    tick = int(getattr(runtime, "tick", 0) or 0)
    slots = getattr(runtime, "slots", None)
    contact = False
    for rec in getattr(runtime, "last_contacts", None) or []:
        if rec and rec.get("contact"):
            contact = True
            break
    if slots:
        from mechanistic_mind.ui.psy_observer_web.undercover_identity import slot_agent_body_ids

        exp_slot = getattr(runtime, "experimenter_slot", None)
        bodies = []
        for i, slot in enumerate(slots):
            aid, _bid = slot_agent_body_ids(i, experimenter_slot=exp_slot)
            bodies.append({
                "agent_id": aid,
                "x": float(slot.body.x),
                "y": float(slot.body.y),
                "action": getattr(slot, "last_selected_action", None),
            })
        primary = slots[0]
        sel = getattr(primary, "last_selection", None) or {}
        source = sel.get("source") if isinstance(sel, dict) else None
        aid0 = bodies[0]["agent_id"] if bodies else "agent_0"
        return {
            "tick": tick,
            "status": status,
            "agent_id": aid0,
            "action": getattr(primary, "last_selected_action", None),
            "action_source": source,
            "body_xy": {"x": float(primary.body.x), "y": float(primary.body.y)},
            "bodies": bodies,
            "contact": contact,
        }
    sel = getattr(runtime, "last_selection", None) or {}
    source = sel.get("source") if isinstance(sel, dict) else None
    return {
        "tick": tick,
        "status": status,
        "agent_id": "agent_0",
        "action": getattr(runtime, "last_selected_action", None),
        "action_source": source,
        "body_xy": {"x": float(runtime.body.x), "y": float(runtime.body.y)},
        "bodies": [{
            "agent_id": "agent_0",
            "x": float(runtime.body.x),
            "y": float(runtime.body.y),
            "action": getattr(runtime, "last_selected_action", None),
        }],
        "contact": contact,
    }


def compact_timeline_event(frame: dict[str, Any]) -> dict[str, Any]:
    """Bounded timeline marker — not a full frame. One shared-world tick."""
    header = frame.get("header") or {}
    action = ((frame.get("causal_chain") or {}).get("stages") or {}).get("ACTION") or {}
    bodies = ((frame.get("world") or {}).get("entities") or {}).get("bodies")
    return {
        "tick": header.get("tick"),
        "status": header.get("status"),
        "agent_id": header.get("selected_agent") or "agent_0",
        "action": action.get("selected"),
        "action_source": action.get("source"),
        "body_xy": {
            "x": (frame.get("body") or {}).get("x"),
            "y": (frame.get("body") or {}).get("y"),
        },
        "bodies": (
            [{"agent_id": b.get("observer_id") or b.get("id"), "x": b.get("x"), "y": b.get("y"),
              "action": b.get("selected_action")} for b in bodies]
            if bodies else None
        ),
        "contact": bool((frame.get("contact") or {}).get("contact")),
    }


def _why_did_it_move(runtime: PhysicalSystemRuntime) -> dict[str, Any]:
    rec = getattr(runtime, "last_motion_receipt", None)
    if not isinstance(rec, dict):
        return {"status": "NOT_AVAILABLE", "reason": "no MotionCausalReceipt yet"}
    summary = rec.get("why_did_it_move_summary") or {}
    return {
        "status": "AVAILABLE",
        "selected_action": (rec.get("action") or {}).get("selected_action"),
        "impulse": (rec.get("action") or {}).get("emitted_impulse"),
        "position_change": summary.get("position_change"),
        "causes": summary.get("causes"),
        "INTERNAL_TO_EXTERNAL_TRANSFER": summary.get("INTERNAL_TO_EXTERNAL_TRANSFER", "NOT_DEMONSTRATED"),
        "endogenous_motor_u": summary.get("endogenous_motor_u"),
        "endogenous_meta": getattr(runtime, "last_endo_motor_meta", None),
        "morphology_meta": getattr(runtime, "last_morphology_meta", None),
        "B_site": None if getattr(runtime.body, "B_site", None) is None else __import__("numpy").asarray(runtime.body.B_site).tolist(),
        "morphology_enabled": bool(getattr(runtime.config.morphology_mechanics, "enabled", False)),
        "orientation": {
            "theta": float(getattr(runtime.body, "theta", 0.0)),
            "omega": float(getattr(runtime.body, "omega", 0.0)),
            "enabled": bool(getattr(runtime.config.body_orientation, "enabled", False)),
            "meta": getattr(runtime, "last_orientation_meta", None),
        },
        "why_did_it_rotate": (rec.get("why_did_it_rotate") if isinstance(rec, dict) else None) or getattr(runtime, "last_orientation_meta", None),
        "why_did_its_shape_change": (rec.get("why_did_its_shape_change") if isinstance(rec, dict) else None) or getattr(runtime, "last_deformation_meta", None),
        "physical_work_energy_flow": getattr(runtime, "last_work_ledger", None),
        "resource_work_flow": getattr(runtime, "last_resource_ledger", None),
        "complementary_resource_flow": getattr(runtime, "last_complementary_ledger", None),
        "motor_work_flow": getattr(runtime, "last_motor_work_ledger", None),
        "discrete_action_work_flow": getattr(runtime, "last_action_work_ledger", None),
        "work_allocation": getattr(runtime, "last_work_allocation", None),
        "execution_order": (rec.get("motion_update") or {}).get("execution_order"),
        "mechanical_decomposition": (rec.get("motion_update") or {}).get("mechanical_decomposition"),
        "environment": rec.get("environment"),
        "internal_transition": rec.get("internal_transition"),
        "receipt": rec,
        "note": "Physical motion causation — separate from WHY THIS ACTION (selection).",
    }
