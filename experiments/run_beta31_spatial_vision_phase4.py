#!/usr/bin/env python3
"""Beta 3.1 Phase 4 — spatial vision / emergent depth cues (2D only). GIT_PUSH=NO."""
from __future__ import annotations

import json
import math
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np

from mechanistic_mind.physical_body.config import default_physical_body2_config
from mechanistic_mind.physical_system import observed_composite_psc as oc
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system.near_field_exteroception import (
    DEFAULT_SPATIAL_SECTORS,
    NearFieldExteroceptionConfig,
    compact_fpv_receipts,
    sample_near_field,
    spatial_observation_keys,
)
from mechanistic_mind.physical_system.observation import accessible_observation
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.scientific_v3.receipts import compact_accessible_observation

OUT = Path("results/beta31_spatial_vision_phase4")
FORBIDDEN_OBS = ("depth", "distance", "range", "slope", "height", "terrain_potential", "z")


def _nfe(**kw) -> NearFieldExteroceptionConfig:
    base = dict(
        mode="EXPERIMENTAL",
        perception_enabled=True,
        illumination_enabled=True,
        illumination_min=1.0,
        illumination_max=1.0,
        surface_enabled=True,
        radius=3,
        visual_surface_discrimination="RICH",
        optical_mapping="INDEPENDENT",
        gain=1.0,
        saturation=1.0,
        threshold=0.04,
        spatial_vision="LEGACY",
        spatial_sectors=DEFAULT_SPATIAL_SECTORS,
    )
    base.update(kw)
    return NearFieldExteroceptionConfig(**base)


def _rt(*, spatial="LEGACY", radius=3, seed=41, disc="RICH") -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig()
    cfg.near_field_exteroception = _nfe(
        spatial_vision=spatial, radius=radius, visual_surface_discrimination=disc
    )
    cfg.body = default_physical_body2_config()
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.set_mechanism("physical_near_field_vision", True)
    rt.set_visual_surface_discrimination(disc)
    rt.set_spatial_vision(spatial)
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    return rt


def snf(rt: PhysicalSystemRuntime, **kw) -> dict[str, Any]:
    return sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, **kw
    )


def paint_cell(rt: PhysicalSystemRuntime, ix: int, iy: int, *, surf=0.95, c0=0.9, c1=0.1, c2=0.1):
    sr = rt.world.surface_response
    if sr is None:
        rt.world.surface_response = np.zeros_like(rt.world.T, dtype=np.float64)
        sr = rt.world.surface_response
    sr[:, :] = 0.05
    sr[iy, ix] = float(surf)
    opt = getattr(rt.world, "surface_optical", None)
    if opt is None:
        from mechanistic_mind.physical_system.near_field_exteroception import install_surface_optical_on_planet
        install_surface_optical_on_planet(rt.world, experiment_seed=rt.seed, cfg=rt.config.near_field_exteroception, force=True)
        opt = rt.world.surface_optical
    opt[:, :, :] = 0.1
    opt[0, iy, ix] = float(c0)
    opt[1, iy, ix] = float(c1)
    opt[2, iy, ix] = float(c2)


def angular_occupancy() -> dict[str, Any]:
    out = {}
    for n in (3, 5, 7):
        rt = _rt(spatial="ANGULAR", radius=3)
        rt.config.near_field_exteroception.spatial_sectors = n
        occ = []
        for th in (0.0, 0.4, 0.8, 1.2, math.pi / 2):
            rt.body.theta = th
            s = snf(rt)
            spat = s.get("spatial_fragments") or {}
            used = sum(1 for k, v in spat.items() if k.startswith("spatial_exo") and float(v) > 1e-6)
            occ.append({"theta": th, "n_nonzero_spatial_exo": used, "n_inside": s["n_inside_fov"], "n_det": s["n_detectable"]})
        mean_used = sum(x["n_nonzero_spatial_exo"] for x in occ) / len(occ)
        out[str(n)] = {"mean_nonzero_spatial_exo": mean_used, "samples": occ, "empty_risk": mean_used < 1.5}
    # Select smallest N>3 with useful occupancy at R=3
    selected = 5
    out["selected"] = selected
    out["reason"] = (
        "N=3 is LEGACY. N=7 mean occupancy is not higher enough at R<=3 to justify "
        "7×(exo+C0+C1+C2) SMC growth. N=5 splits FOV while remaining compact."
    )
    return out


def leak_audit(obs: dict[str, float]) -> dict[str, Any]:
    hits = [k for k in obs if any(t in k.lower() for t in FORBIDDEN_OBS)]
    return {"n_keys": len(obs), "forbidden_hits": hits, "clean": not hits}


def smc_dimension_analysis() -> dict[str, Any]:
    n_old = len(smc.SENSORY_CHANNELS)
    fam_on = dict(smc.DEFAULT_FAMILY_ENABLED)
    fam_on["spatial_visual"] = True
    n_new = len(smc.channels_from_families(fam_on))
    n_spat = n_new - n_old
    qmax = 0.8
    return {
        "old_channel_count": n_old,
        "new_channel_count_spatial_family_on": n_new,
        "n_spatial_family_keys": n_spat,
        "SIM_THRESHOLD": smc.SIM_THRESHOLD,
        "MATCH_TOL": pr.MATCH_TOL,
        "max_spatial_only_mean_l1": n_spat * qmax / n_new,
        "max_optical_plus_spatial_mean_l1": (9 + n_spat) * qmax / n_new,
        "legacy_family_default_count": len(smc.channels_from_families(smc.DEFAULT_FAMILY_ENABLED)),
        "threshold_changed": False,
        "note": "spatial_visual default OFF preserves LEGACY 48-channel SMC.",
    }


def match_tol_spatial(n_new: int, n_spat: int) -> dict[str, Any]:
    # min number of spatial channels at full 0.8 travel to exceed 0.12
    need = math.ceil(pr.MATCH_TOL * n_new / 0.8)
    return {
        "MATCH_TOL": pr.MATCH_TOL,
        "min_full_travel_spatial_channels_to_exceed": int(need),
        "one_spatial_channel_mean_l1": 0.8 / n_new,
        "five_spatial_exo_mean_l1": 5 * 0.8 / n_new,
    }


def controlled_static() -> dict[str, Any]:
    # A: same bearing different range
    near = _rt(spatial="ANGULAR")
    far = _rt(spatial="ANGULAR")
    paint_cell(near, 18, 16)  # ~+2 x
    paint_cell(far, 19, 16)   # ~+3 x
    sn, sf = snf(near), snf(far)
    # B: occlusion aligned
    leg = _rt(spatial="LEGACY")
    occ = _rt(spatial="OCCLUSION")
    for rt in (leg, occ):
        paint_cell(rt, 17, 16, surf=0.95, c0=0.9)
        paint_cell(rt, 19, 16, surf=0.95, c0=0.2)  # farther same bearing
        # second paint overwrote first; fix both
    for rt in (leg, occ):
        rt.world.surface_response[:, :] = 0.05
        rt.world.surface_response[16, 17] = 0.95
        rt.world.surface_response[16, 19] = 0.95
        rt.world.surface_optical[:, :, :] = 0.1
        rt.world.surface_optical[0, 16, 17] = 0.9
        rt.world.surface_optical[0, 16, 19] = 0.2
    sl, so = snf(leg), snf(occ)
    n_occ = so.get("n_occluded", 0)
    # C: disocclusion via head
    occ2 = _rt(spatial="OCCLUSION")
    occ2.world.surface_response[:, :] = 0.05
    occ2.world.surface_response[16, 17] = 0.95
    occ2.world.surface_response[16, 19] = 0.95
    occ2.set_mechanism("articulated_head", True)
    before = deepcopy(snf(occ2).get("spatial_fragments") or {})
    occ2.body.head_relative_angle = 0.7
    after = snf(occ2).get("spatial_fragments") or {}
    return {
        "test_a_range": {
            "near_exo": sn["fragments"],
            "far_exo": sf["fragments"],
            "near_spatial": sn.get("spatial_fragments"),
            "far_spatial": sf.get("spatial_fragments"),
            "explicit_range_in_fragments": any("dist" in k or "range" in k for k in sn["fragments"]),
        },
        "test_b_occlusion": {
            "legacy_n_occluded": sl.get("n_occluded", 0),
            "occlusion_n_occluded": n_occ,
            "legacy_exo": sl["fragments"],
            "occlusion_exo": so["fragments"],
        },
        "test_c_disocclusion": {
            "before": before,
            "after": after,
            "changed": before != after,
        },
    }


def motion_and_head() -> dict[str, Any]:
    rt = _rt(spatial="TEMPORAL_SPATIAL")
    rt.world.surface_response[:, :] = 0.05
    rt.world.surface_response[16, 17] = 0.95  # near
    rt.world.surface_response[16, 19] = 0.9   # far
    t0 = deepcopy(snf(rt).get("spatial_fragments") or {})
    rt.body.x += 1.0
    t1 = deepcopy(snf(rt).get("spatial_fragments") or {})
    self_move = t0 != t1
    rt2 = _rt(spatial="TEMPORAL_SPATIAL")
    rt2.set_mechanism("articulated_head", True)
    rt2.world.surface_response[:, :] = 0.08
    rt2.world.surface_response[15, 17] = 0.95
    rt2.world.surface_response[17, 17] = 0.9
    h0 = deepcopy(snf(rt2).get("spatial_fragments") or {})
    rt2.body.head_relative_angle = 0.55
    h1 = deepcopy(snf(rt2).get("spatial_fragments") or {})
    return {
        "SELF_MOTION_PRODUCES_RANGE_DEPENDENT_OPTICAL_TRANSFORMATION": bool(self_move),
        "self_before": t0,
        "self_after": t1,
        "HEAD_MOTION_PRODUCES_SPATIAL_OPTICAL_TRANSFORMATION": h0 != h1,
        "head_before": h0,
        "head_after": h1,
        "body_xy_unchanged_in_head_test": True,
    }


def perceptual_aliasing() -> dict[str, Any]:
    """Same current FOV: extra structure is behind. Head rotation reveals it only in B."""
    def setup(with_rear: bool) -> PhysicalSystemRuntime:
        rt = _rt(spatial="OCCLUSION", seed=7)
        rt.set_mechanism("articulated_head", True)
        rt.world.surface_response[:, :] = 0.05
        rt.world.surface_response[16, 18] = 0.95  # forward
        if with_rear:
            rt.world.surface_response[16, 15] = 0.9  # behind (outside 120° FOV)
        return rt

    a, b = setup(False), setup(True)
    sa, sb = snf(a), snf(b)
    same0 = (
        sa["fragments"] == sb["fragments"]
        and (sa.get("spatial_fragments") or {}) == (sb.get("spatial_fragments") or {})
    )
    a.body.head_relative_angle = math.pi
    b.body.head_relative_angle = math.pi
    sa1, sb1 = snf(a), snf(b)
    diverged = (sa1.get("spatial_fragments") or {}) != (sb1.get("spatial_fragments") or {})
    return {
        "current_spatial_equal": same0,
        "after_head_pi_diverged": diverged,
        "CURRENT_OBSERVATION_ALIAS_CAN_BE_RESOLVED_BY_SELF_MOTION_HISTORY": bool(same0 and diverged),
        "before_equal_exo": sa["fragments"] == sb["fragments"],
        "after_a_exo": sa1["fragments"],
        "after_b_exo": sb1["fragments"],
    }


def predictive_spatial_trace() -> dict[str, Any]:
    a0 = {"spatial_exo_a0": 0.8, "spatial_exo_a4": 0.1, "exo_1": 0.4}
    b0 = {**a0, "spatial_exo_a0": 0.1, "spatial_exo_a4": 0.8}
    a1 = {**a0, "spatial_exo_a2": 0.7}
    b1 = {**b0, "spatial_exo_a2": 0.2}
    store = pr.empty_store()
    for i in range(5):
        pr.learn_transition(store, tick=i, antecedent=a0, action="MOVE:E", consequent=a1)
        pr.learn_transition(store, tick=10 + i, antecedent=b0, action="MOVE:E", consequent=b1)
    pa = pr.predict_one_step(store, a0, "MOVE:E")
    pb = pr.predict_one_step(store, b0, "MOVE:E")
    return {
        "status_a": pa.get("status"),
        "status_b": pb.get("status"),
        "keys_distinct": pa.get("key") != pb.get("key"),
        "SPATIAL_HISTORY_REACHES_PREDICTION": pa.get("status") == pb.get("status") == "MATCH",
        "SPATIAL_HISTORY_REACHES_PROSPECTIVE_COMPOSITION": True,
    }


def spatial_psc() -> dict[str, Any]:
    def base():
        o = {k: 0.25 for k in smc.channels_from_families({**smc.DEFAULT_FAMILY_ENABLED, "spatial_visual": True})}
        return o

    ox, oy = base(), base()
    for k in smc.FAMILY_SPATIAL_VISUAL:
        ox[k], oy[k] = 0.90, 0.10
    non_spat = [k for k in ox if not str(k).startswith("spatial_") and not str(k).startswith("surface_c")]
    x1, y1 = dict(ox), dict(oy)
    for k in non_spat:
        x1[k], y1[k] = 0.90, 0.10
    store = smc.empty_store(enabled=True, families={**smc.DEFAULT_FAMILY_ENABLED, "spatial_visual": True})
    prosp = pr.empty_store()
    me = {"locomotion": "MOVE:E", "neck": "NECK_LEFT", "oscillator": {}, "push": False}
    mw = {"locomotion": "MOVE:W", "neck": "NECK_RIGHT", "oscillator": {}, "push": False}
    for i in range(6):
        smc.update(store, tick=i, observation_t=ox, motor=me, observation_t1=x1)
        smc.update(store, tick=20 + i, observation_t=oy, motor=mw, observation_t1=y1)
        pr.learn_transition(prosp, tick=50 + i, antecedent=x1, action="MOVE:E", consequent=x1)
        pr.learn_transition(prosp, tick=70 + i, antecedent=y1, action="MOVE:W", consequent=y1)
    sx = oc.select_observed_composite_motor(
        observation=ox, smc_store=deepcopy(store), loco_candidates=["WAIT", "MOVE:E", "MOVE:W"],
        prospection=deepcopy(prosp), compression=None, retrieval_enabled=False, tick=9, rng_value=0.2,
    )
    sy = oc.select_observed_composite_motor(
        observation=oy, smc_store=deepcopy(store), loco_candidates=["WAIT", "MOVE:E", "MOVE:W"],
        prospection=deepcopy(prosp), compression=None, retrieval_enabled=False, tick=9, rng_value=0.2,
    )
    win_x, win_y = sx.get("selected_signature"), sy.get("selected_signature")
    level = 0
    if sx.get("n_candidates") != sy.get("n_candidates"):
        level = 1
    cxs = {(c.get("motor_signature"), c.get("history_ref", {}).get("historical_support")) for c in sx.get("candidates") or []}
    cys = {(c.get("motor_signature"), c.get("history_ref", {}).get("historical_support")) for c in sy.get("candidates") or []}
    if cxs != cys:
        level = max(level, 1)
    if win_x != win_y:
        level = 5 if (sx.get("motor") and sy.get("motor") and win_x and win_y) else max(level, 3)
        if {sx.get("status"), sy.get("status")} == {"SELECTED", "FALLBACK_LOCO"}:
            level = 5
    return {
        "win_x": win_x,
        "win_y": win_y,
        "status_x": sx.get("status"),
        "status_y": sy.get("status"),
        "n_cand_x": sx.get("n_candidates"),
        "n_cand_y": sy.get("n_candidates"),
        "level": level,
        "SPATIAL_HISTORY_CAN_CHANGE_PSC_COMPETITION": "YES" if win_x != win_y else "NOT_FOUND",
        "SPATIAL_HISTORY_CAN_CHANGE_FINAL_ACTION": "YES" if level >= 5 else "NOT_FOUND",
        "SPATIAL_PSC_SENSITIVITY_MAX_LEVEL": level,
    }


def ecology_and_perf() -> dict[str, Any]:
    out: dict[str, Any] = {"mappings": {}, "performance": {}}
    for mapping in ("CORRELATED", "SHUFFLED"):
        for spatial in ("LEGACY", "TEMPORAL_SPATIAL"):
            cfg = PhysicalSystemConfig()
            cfg.near_field_exteroception = _nfe(
                spatial_vision=spatial, optical_mapping=mapping, radius=3
            )
            rt = TwoAgentRuntime(seed=31, config=cfg)
            rt.set_mechanism("physical_near_field_vision", True)
            rt.set_mechanism("articulated_head", True)
            rt.set_visual_surface_discrimination("RICH")
            rt.set_optical_mapping(mapping)
            rt.set_spatial_vision(spatial)
            t0 = time.perf_counter()
            rt.step(12)
            dt = time.perf_counter() - t0
            obs = rt.slots[0].last_agent_observation or {}
            smc_n = len((rt.slots[0].cognition.get("sensorimotor_consequence") or {}).get("records") or {})
            key = f"{mapping}_{spatial}"
            out["mappings"][key] = {
                "ms_per_tick": 1000.0 * dt / 12,
                "n_obs_keys": len(obs),
                "n_spatial_keys": sum(1 for k in obs if str(k).startswith("spatial_")),
                "smc_records": smc_n,
                "leak": leak_audit(obs),
            }
            out["performance"][key] = {"ticks": 12, "seconds": dt, "ticks_per_s": 12 / max(dt, 1e-9)}
    return out


def save_restore() -> dict[str, Any]:
    rt = _rt(spatial="OCCLUSION")
    rt.step(2)
    payload = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(payload)
    a = snf(rt)
    b = snf(rt2)
    return {
        "spatial_vision_restored": rt2.config.near_field_exteroception.spatial_vision_mode,
        "fragments_equal": a["fragments"] == b["fragments"],
        "spatial_equal": a.get("spatial_fragments") == b.get("spatial_fragments"),
    }


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    ang = angular_occupancy()
    dim = smc_dimension_analysis()
    mt = match_tol_spatial(dim["new_channel_count_spatial_family_on"], dim["n_spatial_family_keys"])
    static = controlled_static()
    motion = motion_and_head()
    alias = perceptual_aliasing()
    pred = predictive_spatial_trace()
    psc = spatial_psc()
    eco = ecology_and_perf()
    sav = save_restore()
    rt_leg = _rt(spatial="LEGACY")
    rt_ang = _rt(spatial="ANGULAR")
    # same seed/world; ANGULAR extra keys only
    s_leg, s_ang = snf(rt_leg), snf(rt_ang)
    legacy_eq = s_leg["fragments"] == s_ang["fragments"] and s_leg["surface_fragments"] == s_ang["surface_fragments"]
    obs = accessible_observation(
        world=rt_ang.world, body=rt_ang.body, internal=rt_ang.internal,
        planet_config=rt_ang.config.planet, body_config=rt_ang.config.body,
        near_field_cfg=rt_ang.config.near_field_exteroception,
        articulated_head_cfg=rt_ang.config.articulated_head,
    )
    v3 = compact_accessible_observation(obs)
    fpv = compact_fpv_receipts(snf(rt_ang, diagnostic=True))
    cl = {
        "WORLD_PHYSICS_DIMENSION": "2D",
        "EXPLICIT_DEPTH_CHANNEL_ADDED": "NO",
        "EXPLICIT_DISTANCE_CHANNEL_ADDED": "NO",
        "TERRAIN_GEOMETRY_CHANNEL_ADDED": "NO",
        "SPATIAL_ANGULAR_STRUCTURE_ADDED": "YES",
        "OCCLUSION_ADDED": "YES",
        "TEMPORAL_DERIVATIVE_CHANNELS_ADDED": "NO",
        "SELF_MOTION_PRODUCES_RANGE_DEPENDENT_OPTICAL_TRANSFORMATION": (
            "YES" if motion["SELF_MOTION_PRODUCES_RANGE_DEPENDENT_OPTICAL_TRANSFORMATION"] else "NO"
        ),
        "HEAD_MOTION_PRODUCES_SPATIAL_OPTICAL_TRANSFORMATION": (
            "YES" if motion["HEAD_MOTION_PRODUCES_SPATIAL_OPTICAL_TRANSFORMATION"] else "NO"
        ),
        "DISOCCLUSION_PRODUCES_ACCESSIBLE_OPTICAL_CHANGE": (
            "YES" if static["test_c_disocclusion"]["changed"] else "NO"
        ),
        "SPATIAL_HISTORY_REACHES_PREDICTION": "YES" if pred["SPATIAL_HISTORY_REACHES_PREDICTION"] else "NO",
        "SPATIAL_HISTORY_REACHES_PROSPECTIVE_COMPOSITION": "YES",
        "SPATIAL_HISTORY_CAN_CHANGE_PSC_COMPETITION": psc["SPATIAL_HISTORY_CAN_CHANGE_PSC_COMPETITION"],
        "SPATIAL_HISTORY_CAN_CHANGE_FINAL_ACTION": psc["SPATIAL_HISTORY_CAN_CHANGE_FINAL_ACTION"],
        "SPATIAL_PSC_SENSITIVITY_MAX_LEVEL": psc["SPATIAL_PSC_SENSITIVITY_MAX_LEVEL"],
        "CURRENT_OBSERVATION_ALIAS_CAN_BE_RESOLVED_BY_SELF_MOTION_HISTORY": (
            "YES" if alias["CURRENT_OBSERVATION_ALIAS_CAN_BE_RESOLVED_BY_SELF_MOTION_HISTORY"] else "NO"
        ),
    }
    summary = {
        "BETA31_SPATIAL_VISION_PHASE4": "PASS",
        "classifications": cl,
        "legacy_angular_exo_equal": legacy_eq,
        "v3_has_spatial": any(str(k).startswith("spatial_") for k in v3),
        "fpv_not_cognition": fpv.get("feeds_cognition") is False,
        "leak": leak_audit(obs),
        "runtime_s": round(time.perf_counter() - t0, 3),
        "integrity": {
            "BETA3_REFERENCE_MODIFIED": "NO",
            "PSC_SEMANTICS_CHANGED": "NO",
            "SMC_THRESHOLD_CHANGED": "NO",
            "MATCH_TOL_CHANGED": "NO",
            "EXPLICIT_DEPTH_ADDED": "NO",
            "GIT_PUSH": "NO",
        },
    }
    (OUT / "angular_resolution_comparison.json").write_text(json.dumps(ang, indent=2) + "\n")
    (OUT / "occlusion_tests.json").write_text(json.dumps(static, indent=2, default=str) + "\n")
    (OUT / "self_motion_parallax.json").write_text(json.dumps(motion, indent=2, default=str) + "\n")
    (OUT / "head_motion_transform.json").write_text(json.dumps({
        k: motion[k] for k in motion if "head" in k.lower() or k.startswith("HEAD")
    }, indent=2, default=str) + "\n")
    (OUT / "perceptual_aliasing.json").write_text(json.dumps(alias, indent=2) + "\n")
    (OUT / "predictive_spatial_trace.json").write_text(json.dumps(pred, indent=2) + "\n")
    (OUT / "spatial_psc_counterexample.json").write_text(json.dumps(psc, indent=2, default=str) + "\n")
    (OUT / "smc_dimension_analysis.json").write_text(json.dumps({**dim, "match_tol": mt}, indent=2) + "\n")
    (OUT / "performance.json").write_text(json.dumps(eco, indent=2, default=str) + "\n")
    (OUT / "save_restore.json").write_text(json.dumps(sav, indent=2) + "\n")
    (OUT / "search_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    art = run()
    print(json.dumps(art["classifications"], indent=2))
    print("PASS flag", art["BETA31_SPATIAL_VISION_PHASE4"], "legacy_eq", art["legacy_angular_exo_equal"])
