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
    """Compact JSON-friendly row-major grid (OBS-05)."""
    nested = _grid(arr, max_side=max_side)
    h = len(nested)
    w = len(nested[0]) if nested else 0
    data: list[float] = []
    for row in nested:
        data.extend(float(v) for v in row)
    return {"h": h, "w": w, "data": data}


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
        "experiment": display_name(),
        "model_family": model.get("model_family"),
        "model_version": model.get("model_version"),
        "model_codename": model.get("model_codename"),
        "model_display_name": model.get("display_name"),
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
        "snapshot_compatibility": "TIKTAALIK",
        "ecology_preset": getattr(runtime.config, "ecology_preset", "CURRENT") or "CURRENT",
    }


def world_frame(
    runtime: PhysicalSystemRuntime,
    *,
    max_side: int = 64,
    detail: str = "full",
) -> dict[str, Any]:
    """Serialize planet fields.

    compact RUNNING keeps only visualization-critical scalars (T, flow, FIELD_*),
    omitting M*/u/R* planes that dominate JSON size. Full detail remains on PAUSE/INSPECT.
    Compact also uses flat grid encoding and avoids duplicating planes across
    top-level / scalars / vectors (OBS-05).
    """
    w = runtime.world
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
        "note": "Technical observer IDs. Not present in agent observation.",
    }
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
        )
        near_field_gt = {
            **near_field_gt,
            "perception_enabled": bool(nfe.perception_enabled),
            "body_optical_enabled": bool(getattr(nfe, "body_optical_enabled", True)),
            "illumination_intensity_world": getattr(runtime.world, "illumination_intensity", None),
            "surface_checksum": (getattr(runtime.world, "surface_meta", None) or {}).get("checksum"),
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
            "display": mo.get("display") or runtime.last_selected_action,
            "note": "Structured motor output — not a Cartesian compound action token.",
        },
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
) -> dict[str, Any]:
    mechanisms = __import__(
        "mechanistic_mind.physical_system.mechanism_registry",
        fromlist=["mechanism_snapshot"],
    ).mechanism_snapshot(runtime.config)
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
        "world": world_frame(runtime, max_side=max_side, detail=detail),
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
        "experiment": experiment_config_frame(runtime, detail=detail),
        "honesty": {
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

def _agents_observer_frame(runtime: PhysicalSystemRuntime) -> list[dict[str, Any]]:
    """HUD / strip agent rows for N>=1. Always a list (never null).

    TwoAgentRuntime already exposes observer_agent_summaries. Single-agent
    PhysicalSystemRuntime must still surface agent_0 + selected_action so the
    bottom strip does not fall back to body.selected_action (which body_frame
    does not carry).
    """
    if hasattr(runtime, "observer_agent_summaries"):
        rows = runtime.observer_agent_summaries()
        return list(rows or [])
    # Prefer shared helper (same shape used at finalize)
    try:
        from mechanistic_mind.ui.psy_observer_web.run_finalize import agent_summaries

        return list(agent_summaries(runtime) or [])
    except Exception:
        pass
    return [{
        "observer_id": "agent_0",
        "agent_id": "agent_0",
        "body_id": "body-0",
        "x": float(runtime.body.x),
        "y": float(runtime.body.y),
        "selected_action": runtime.last_selected_action,
        "tick": int(runtime.tick),
        "agent_seed": int(runtime.seed),
    }]


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
