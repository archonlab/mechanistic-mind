#!/usr/bin/env python3
"""Read-only forensic: what spatial/depth structure reaches accessible_observation.

Does not modify vision, cognition, or runtime semantics.
"""
from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path

import numpy as np

from mechanistic_mind.physical_body.config import default_physical_body2_config
from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.physical_system.near_field_exteroception import (
    NearFieldExteroceptionConfig,
    cognition_exo_fragments,
    cognition_surface_fragments,
    distance_attenuation,
    sample_near_field,
)
from mechanistic_mind.physical_system.observation import accessible_observation
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.research.background_context import sensory_signature
from mechanistic_mind.scientific_v3.receipts import compact_accessible_observation, build_observation_receipt

OUT = Path("results/beta31_visual_depth_forensic")
VISUAL_KEYS = (
    "exo_0", "exo_1", "exo_2",
    *(f"surface_c{c}_{b}" for c in range(3) for b in range(3)),
)


def _nfe(disc: str, radius: int = 3) -> NearFieldExteroceptionConfig:
    return NearFieldExteroceptionConfig(
        mode="EXPERIMENTAL",
        perception_enabled=True,
        illumination_enabled=True,
        illumination_min=1.0,
        illumination_max=1.0,
        illumination_period=240,
        surface_enabled=True,
        radius=radius,
        gain=1.0,
        threshold=0.04,
        saturation=1.0,
        distance_k=0.85,
        fov_deg=120.0,
        visual_surface_discrimination=disc,
        optical_mapping="INDEPENDENT",
        signal_hash_noise=0.0,
        body_optical_enabled=True,
    )


def _rt(disc: str, *, seed: int = 7) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig()
    cfg.near_field_exteroception = _nfe(disc)
    cfg.cognition.cognition_enabled = True
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.set_mechanism("physical_near_field_vision", True)
    rt.set_visual_surface_discrimination(disc)
    return rt


def _place_observer(rt: PhysicalSystemRuntime, x: float = 16.5, y: float = 16.5, theta: float = 0.0) -> None:
    rt.body.x = float(x)
    rt.body.y = float(y)
    rt.body.theta = float(theta)
    rt.body.head_relative_angle = 0.0


def _blank_optics(rt: PhysicalSystemRuntime) -> None:
    s = rt.world.surface_response
    if s is not None:
        s[:, :] = 0.0
    opt = getattr(rt.world, "surface_optical", None)
    if opt is not None:
        opt[:, :, :] = 0.35


def _set_cell_surface(rt: PhysicalSystemRuntime, ix: int, iy: int, surf: float, optical=None) -> None:
    rt.world.surface_response[iy, ix] = float(surf)
    opt = getattr(rt.world, "surface_optical", None)
    if opt is not None and optical is not None:
        for k, v in enumerate(optical):
            if k < opt.shape[0]:
                opt[k, iy, ix] = float(v)


def _visual(obs: dict) -> dict:
    return {k: float(obs.get(k) or 0.0) for k in VISUAL_KEYS if k in obs}


def _flush_sensor_cache(rt: PhysicalSystemRuntime) -> None:
    rt.world.tick = int(rt.world.tick) + 1


def _obs(rt: PhysicalSystemRuntime, foreign=None) -> dict:
    return accessible_observation(
        world=rt.world,
        body=rt.body,
        internal=rt.internal,
        planet_config=rt.config.planet,
        body_config=rt.config.body,
        near_field_cfg=rt.config.near_field_exteroception,
        foreign_bodies=foreign,
    )


def static_depth(disc: str) -> dict:
    """Same bearing (+x), identical surface, distances 1,2,3 and R=3 max."""
    rt = _rt(disc)
    _place_observer(rt)
    rows = []
    # cell centers: observer 16.5,16.5 facing +x (theta=0)
    targets = [
        ("d1", 17, 16, 1.0),
        ("d2", 18, 16, 2.0),
        ("d3", 19, 16, 3.0),
    ]
    for name, ix, iy, d_nom in targets:
        _blank_optics(rt)
        _set_cell_surface(rt, ix, iy, 0.55, optical=(0.8, 0.4, 0.2))
        _flush_sensor_cache(rt)
        obs = _obs(rt)
        vis = _visual(obs)
        sample = sample_near_field(
            world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
        )
        hit = next((r for r in sample["neighbors"] if r["cell"] == [ix, iy]), None)
        rows.append({
            "label": name,
            "cell": [ix, iy],
            "nominal_chebyshev": d_nom,
            "world_distance": None if hit is None else hit["distance"],
            "world_distance_factor": None if hit is None else hit["distance_factor"],
            "world_inside_fov": None if hit is None else hit["inside_fov"],
            "world_final": None if hit is None else hit["final_contribution"],
            "accessible_visual": vis,
            "signature": sensory_signature(obs),
            "receipt_signature": build_observation_receipt(
                run_id="forensic", tick=0, cognitive_agent_id="a0",
                physical_body_id="b0", accessible=compact_accessible_observation(obs),
            )["signature"],
        })
    # saturation alias: surf=1, gain large enough both d=1 and d=3 clip
    sat_rows = []
    for name, ix, iy, d_nom in (("sat_d1", 17, 16, 1.0), ("sat_d3", 19, 16, 3.0)):
        _blank_optics(rt)
        _set_cell_surface(rt, ix, iy, 1.0, optical=(1.0, 1.0, 1.0))
        _flush_sensor_cache(rt)
        obs = _obs(rt)
        vis = _visual(obs)
        sat_rows.append({
            "label": name,
            "accessible_visual": vis,
            "signature": sensory_signature(obs),
        })
    # inverse: dim near vs bright far aiming for similar exo
    k = 0.85
    f1 = distance_attenuation(1.0, k)
    f3 = distance_attenuation(3.0, k)
    _blank_optics(rt)
    _set_cell_surface(rt, 17, 16, 0.40, optical=(0.7, 0.7, 0.7))
    _flush_sensor_cache(rt)
    near_dim = _visual(_obs(rt))
    _blank_optics(rt)
    # scale surface so pre ≈ same if ang equal: surf3 * f3 = surf1 * f1
    surf3 = min(1.0, 0.40 * f1 / f3)
    _set_cell_surface(rt, 19, 16, surf3, optical=(0.7, 0.7, 0.7))
    _flush_sensor_cache(rt)
    far_bright = _visual(_obs(rt))
    return {
        "disc": disc,
        "unsaturated_same_appearance": rows,
        "saturated": sat_rows,
        "near_dim_vs_far_bright": {
            "near_surf": 0.40,
            "far_surf": surf3,
            "near_visual": near_dim,
            "far_visual": far_bright,
            "exo_l1": float(sum(abs(near_dim.get(k, 0) - far_bright.get(k, 0)) for k in ("exo_0", "exo_1", "exo_2"))),
        },
        "static_distance_distinguished_unsaturated": rows[0]["signature"] != rows[2]["signature"],
        "static_distance_aliased_when_saturated": sat_rows[0]["signature"] == sat_rows[1]["signature"]
        or (
            abs(sat_rows[0]["accessible_visual"].get("exo_1", 0) - sat_rows[1]["accessible_visual"].get("exo_1", 0)) < 1e-9
        ),
    }


def bearing_distance_matrix(disc: str) -> dict:
    rt = _rt(disc)
    _place_observer(rt)
    # bearings: +x, +x+y diagonal, +y (may be outside 120 FOV at theta=0)
    placements = [
        ("plus_x_d1", 17, 16),
        ("plus_x_d2", 18, 16),
        ("plus_x_d3", 19, 16),
        ("diag_d1", 17, 17),
        ("diag_d2", 18, 18),
        ("plus_y_d1", 16, 17),  # likely outside FOV for theta=0
        ("plus_y_d2", 16, 18),
        ("minus_x_d1", 15, 16),  # rear
    ]
    table = []
    sigs: dict[str, list] = {}
    for label, ix, iy in placements:
        _blank_optics(rt)
        _set_cell_surface(rt, ix, iy, 0.55, optical=(0.8, 0.4, 0.2))
        _flush_sensor_cache(rt)
        obs = _obs(rt)
        vis = _visual(obs)
        sig = sensory_signature(obs)
        sample = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
        hit = next((r for r in sample["neighbors"] if r["cell"] == [ix, iy]), None)
        rec = {
            "label": label,
            "cell": [ix, iy],
            "world_rel_deg": None if hit is None else hit["relative_angle_deg"],
            "world_dist": None if hit is None else hit["distance"],
            "inside_fov": None if hit is None else hit["inside_fov"],
            "accessible_visual": vis,
            "signature": sig,
        }
        table.append(rec)
        sigs.setdefault(sig, []).append(label)
    aliases = {s: labs for s, labs in sigs.items() if len(labs) > 1}
    return {"disc": disc, "rows": table, "alias_groups": aliases}


def occlusion_test() -> dict:
    rt = _rt("RICH")
    _place_observer(rt)
    _blank_optics(rt)
    _set_cell_surface(rt, 17, 16, 0.9, optical=(1, 0, 0))
    _flush_sensor_cache(rt)
    near_only = _visual(_obs(rt))
    _set_cell_surface(rt, 19, 16, 0.9, optical=(0, 1, 0))
    _flush_sensor_cache(rt)
    both = _visual(_obs(rt))
    _blank_optics(rt)
    _set_cell_surface(rt, 19, 16, 0.9, optical=(0, 1, 0))
    _flush_sensor_cache(rt)
    far_only = _visual(_obs(rt))
    # If no occlusion, both ≈ combination (not equal to near_only)
    return {
        "near_only": near_only,
        "far_only": far_only,
        "both": both,
        "far_still_contributes_when_near_present": both != near_only,
        "classification": "NO_OCCLUSION" if both != near_only else "OCCLUSION_PRESENT",
    }


def other_body_depth() -> dict:
    rt = _rt("OFF")
    _place_observer(rt)
    _blank_optics(rt)
    other_cfg = default_physical_body2_config()
    rows = []
    for d, x in (("d1", 17.5), ("d2", 18.5), ("d3", 19.5)):
        other = deepcopy(rt.body)
        other.x = x
        other.y = 16.5
        other.theta = math.pi
        _flush_sensor_cache(rt)
        obs = _obs(rt, foreign=[(other, other_cfg)])
        vis = _visual(obs)
        rows.append({"label": d, "other_xy": [x, 16.5], "accessible_visual": vis, "signature": sensory_signature(obs)})
        leak = [k for k in obs if "agent" in k.lower() or "other" in k.lower() or "distance" in k.lower()]
        rows[-1]["identity_or_distance_keys"] = leak
    return {
        "rows": rows,
        "distance_key_present": any(r["identity_or_distance_keys"] for r in rows),
        "signatures_differ": len({r["signature"] for r in rows}) > 1,
    }


def temporal_parallax() -> dict:
    """Fixed world target; observer steps +x. Compare Δexo for near vs far target."""
    def series(ix, iy):
        rt = _rt("RICH")
        _place_observer(rt, x=16.5, y=16.5, theta=0.0)
        _blank_optics(rt)
        _set_cell_surface(rt, ix, iy, 0.7, optical=(0.9, 0.3, 0.1))
        out = []
        for step in range(4):
            _flush_sensor_cache(rt)
            obs = _obs(rt)
            out.append({
                "observer_x": rt.body.x,
                "visual": _visual(obs),
                "signature": sensory_signature(obs),
            })
            rt.body.x = 16.5 + 0.5 * (step + 1)
        return out

    near = series(17, 16)
    far = series(19, 16)
    def d_exo(a, b):
        return float(sum(abs(a["visual"].get(k, 0) - b["visual"].get(k, 0)) for k in ("exo_0", "exo_1", "exo_2")))
    return {
        "near_target_cell": [17, 16],
        "far_target_cell": [19, 16],
        "near_series": near,
        "far_series": far,
        "near_step0_to_1_dexo": d_exo(near[0], near[1]),
        "far_step0_to_1_dexo": d_exo(far[0], far[1]),
        "delta_magnitudes_differ": abs(d_exo(near[0], near[1]) - d_exo(far[0], far[1])) > 1e-6,
    }


def terrain_direct_check() -> dict:
    rt = _rt("RICH")
    obs = _obs(rt)
    banned = [
        k for k in obs
        if any(s in k.lower() for s in ("potential", "drag", "grad", "slope", "height", "terrain", "hill"))
    ]
    return {
        "banned_keys_in_accessible": banned,
        "has_surface_c": any(k.startswith("surface_c") for k in obs),
        "has_exo": any(k.startswith("exo_") for k in obs),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "static_depth": {d: static_depth(d) for d in ("OFF", "LOW", "RICH")},
        "bearing_distance": {d: bearing_distance_matrix(d) for d in ("OFF", "RICH")},
        "occlusion": occlusion_test(),
        "other_body": other_body_depth(),
        "temporal": temporal_parallax(),
        "terrain_keys": terrain_direct_check(),
        "equations": {
            "ang": "cos(pi/2 * |rel|/half_fov)^angular_power if |rel|<=half else 0",
            "dist_f": "1 / (1 + distance_k * max(0, dist-1)), default k=0.85",
            "composed": "1 - (1-surf)*(1-body_opt)",
            "final": "clip(gain * composed * illum * dist_f * ang) if inside FOV and >= threshold else 0",
            "exo_bin": "sum final into 3 bins of rel angle within FOV",
            "surface_c": "sum (optical_ck * final) into same 3 angle bins",
        },
    }
    path = OUT / "diagnostics.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    # compact summary
    summ = {
        "static_off_d1_vs_d3": payload["static_depth"]["OFF"]["static_distance_distinguished_unsaturated"],
        "static_rich_d1_vs_d3": payload["static_depth"]["RICH"]["static_distance_distinguished_unsaturated"],
        "occlusion": payload["occlusion"]["classification"],
        "other_body_sigs_differ": payload["other_body"]["signatures_differ"],
        "temporal_deltas_differ": payload["temporal"]["delta_magnitudes_differ"],
        "terrain_banned": payload["terrain_keys"]["banned_keys_in_accessible"],
    }
    (OUT / "summary.json").write_text(json.dumps(summ, indent=2), encoding="utf-8")
    print(json.dumps(summ, indent=2))
    print("wrote", path)


if __name__ == "__main__":
    main()
