#!/usr/bin/env python3
"""PHYSICAL_GEOGRAPHY_01 — structured terrain geography validation.

Physics / geography acceptance only. Not a cognition success test.
Uses STRUCTURED_TERRAIN_EXPERIMENTAL across multiple seeds.
"""
from __future__ import annotations

import json
import math
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from scipy.stats import pearsonr, spearmanr

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_STRUCTURED_TERRAIN,
    make_ecology_config,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.planet.terrain import (
    TERRAIN_GENERATOR_VERSION,
    generate_terrain_fields,
    resolve_terrain_seed,
    terrain_field_checksum,
)

OUT_ROOT = ROOT / "results" / "physics"

SEEDS = (17, 31, 43, 71, 101)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, str):
        path.write_text(obj, encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def _neighbor_delta_mean(field: np.ndarray) -> float:
    h, w = field.shape
    deltas = [
        abs(float(field[y, x] - field[y, (x + 1) % w])) for y in range(h) for x in range(w)
    ]
    deltas += [
        abs(float(field[y, x] - field[(y + 1) % h, x])) for y in range(h) for x in range(w)
    ]
    return float(np.mean(deltas))


def _independent_noise_neighbor_baseline(field: np.ndarray, *, rng: np.random.Generator) -> float:
    """Same marginal std as field, spatially independent cells."""
    noise = rng.normal(0.0, float(np.std(field)) + 1e-12, size=field.shape)
    return _neighbor_delta_mean(noise)


def _corr(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    aa = np.asarray(a, dtype=np.float64).ravel()
    bb = np.asarray(b, dtype=np.float64).ravel()
    sp = float(spearmanr(aa, bb).correlation)
    pe = float(pearsonr(aa, bb)[0])
    if math.isnan(sp):
        sp = 0.0
    if math.isnan(pe):
        pe = 0.0
    return {"spearman": sp, "pearson": pe}


def _seed_report(seed: int) -> dict[str, Any]:
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN, trickle=0.0)
    assert cfg.planet.terrain.enabled
    assert bool(cfg.planet.climate_ecology.geography_resources_enabled)

    # --- reproducibility (two independent runtimes) ---
    rt_a = PhysicalSystemRuntime(seed=seed, config=deepcopy(cfg))
    rt_b = PhysicalSystemRuntime(seed=seed, config=deepcopy(cfg))
    pot_a = np.asarray(rt_a.world.terrain_potential)
    pot_b = np.asarray(rt_b.world.terrain_potential)
    drag_a = np.asarray(rt_a.world.terrain_drag)
    meta_a = dict(rt_a.world.terrain_meta or {})
    checksum_a = terrain_field_checksum(pot_a, drag_a)
    checksum_b = terrain_field_checksum(pot_b, np.asarray(rt_b.world.terrain_drag))
    reproducible = bool(
        np.allclose(pot_a, pot_b)
        and np.allclose(drag_a, rt_b.world.terrain_drag)
        and checksum_a == checksum_b
        and meta_a.get("checksum") == rt_b.world.terrain_meta.get("checksum")
        and meta_a.get("generation_attempt") == rt_b.world.terrain_meta.get("generation_attempt")
    )

    # Direct generator path (same resolved seed) matches runtime install.
    resolved, _src = resolve_terrain_seed(seed, cfg.planet.terrain)
    pot_g, drag_g, _gy, _gx, gen_info = generate_terrain_fields(
        height=pot_a.shape[0],
        width=pot_a.shape[1],
        terrain_seed=resolved,
        config=cfg.planet.terrain,
    )
    generator_matches = bool(np.allclose(pot_a, pot_g) and np.allclose(drag_a, drag_g))

    # --- correlated geography vs independent noise ---
    nbr = _neighbor_delta_mean(pot_a)
    noise_base = _independent_noise_neighbor_baseline(pot_a, rng=np.random.default_rng(seed + 9001))
    geography_smoother = nbr < 0.92 * noise_base

    # --- traversability ---
    audit = (meta_a.get("traversability_audit") or {})
    trav_pass = bool(audit.get("passed"))
    largest_frac = float(audit.get("largest_component_frac") or 0.0)

    # --- RNG independence: step climate/cognition must not mutate terrain ---
    cfg_cog = deepcopy(cfg)
    cfg_cog.cognition.cognition_enabled = True
    rt_c = PhysicalSystemRuntime(seed=seed, config=cfg_cog)
    pot0 = np.asarray(rt_c.world.terrain_potential).copy()
    cs0 = rt_c.world.terrain_meta["checksum"]
    for _ in range(60):
        rt_c.step()
    rng_independent = bool(np.allclose(pot0, rt_c.world.terrain_potential) and rt_c.world.terrain_meta["checksum"] == cs0)

    # --- resource geography correlation (early; before diffusion washes signal) ---
    rt_r = PhysicalSystemRuntime(seed=seed, config=deepcopy(cfg))
    geo_A = np.asarray(rt_r.world.resource_geo_suit_A)
    geo_B = np.asarray(rt_r.world.resource_geo_suit_B)
    assert geo_A is not None and geo_B is not None
    corr_A0 = _corr(rt_r.world.R_A, geo_A)
    corr_B0 = _corr(rt_r.world.R_B, geo_B)
    for _ in range(20):
        rt_r.step_forced_action("WAIT")
    corr_A20 = _corr(rt_r.world.R_A, geo_A)
    corr_B20 = _corr(rt_r.world.R_B, geo_B)
    ra_rb_differ = float(np.mean(np.abs(rt_r.world.R_A - rt_r.world.R_B))) > 1e-4
    geo_channels_differ = float(np.mean(np.abs(geo_A - geo_B))) > 1e-4

    obs = rt_r.agent_observation()
    obs_hits = audit_cognition_payload(obs)
    obs_blob = repr(obs)
    suitability_not_in_obs = (
        not obs_hits
        and "resource_geo_suit" not in obs_blob
        and "terrain_potential" not in obs_blob
        and "terrain_drag" not in obs_blob
        and "terrain_seed" not in obs_blob
    )

    resource_corr_ok = (
        corr_A0["spearman"] > 0.15
        and corr_B0["spearman"] > 0.15
        and corr_A0["pearson"] > 0.10
        and corr_B0["pearson"] > 0.10
        and ra_rb_differ
        and geo_channels_differ
        and suitability_not_in_obs
    )

    gates = {
        "reproducibility": reproducible and generator_matches,
        "correlated_geography": geography_smoother,
        "traversability": trav_pass and largest_frac >= 0.52,
        "rng_independence": rng_independent,
        "resource_geography": resource_corr_ok,
    }

    return {
        "seed": seed,
        "ecology_preset": ECOLOGY_STRUCTURED_TERRAIN,
        "generator_version": TERRAIN_GENERATOR_VERSION,
        "terrain_seed": meta_a.get("terrain_seed"),
        "checksum": checksum_a,
        "generation_attempt": meta_a.get("generation_attempt"),
        "generation_accepted": meta_a.get("generation_accepted"),
        "generation_fallback": meta_a.get("generation_fallback"),
        "reproducibility": {
            "runtime_pair_identical": reproducible,
            "generator_matches_runtime": generator_matches,
            "attempt": meta_a.get("generation_attempt"),
            "checksum": checksum_a,
        },
        "correlated_geography": {
            "neighbor_delta_mean": nbr,
            "independent_noise_neighbor_delta": noise_base,
            "ratio_vs_noise": nbr / max(1e-12, noise_base),
            "passed": geography_smoother,
        },
        "traversability": {
            **{k: audit.get(k) for k in (
                "feasible_transition_frac",
                "largest_component_frac",
                "largest_component_size",
                "n_components",
                "extreme_gradient_frac",
                "neighbor_delta_phi_mean",
                "passed",
            )},
            "passed": trav_pass and largest_frac >= 0.52,
        },
        "rng_independence": {
            "passed": rng_independent,
            "checksum_before": cs0,
            "checksum_after": rt_c.world.terrain_meta["checksum"],
        },
        "resource_geography": {
            "corr_R_A_geo_A_t0": corr_A0,
            "corr_R_B_geo_B_t0": corr_B0,
            "corr_R_A_geo_A_t20": corr_A20,
            "corr_R_B_geo_B_t20": corr_B20,
            "R_A_R_B_mean_abs_diff": float(np.mean(np.abs(rt_r.world.R_A - rt_r.world.R_B))),
            "geo_A_geo_B_mean_abs_diff": float(np.mean(np.abs(geo_A - geo_B))),
            "suitability_not_in_agent_observation": suitability_not_in_obs,
            "observation_forbidden_hits": obs_hits,
            "passed": resource_corr_ok,
        },
        "gen_info_accepted": bool(gen_info.get("accepted")),
        "gates": gates,
        "all_passed": all(gates.values()),
    }


def main() -> int:
    out = OUT_ROOT / f"physical_geography_01_{_ts()}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    per_seed = [_seed_report(s) for s in SEEDS]
    gate_names = (
        "reproducibility",
        "correlated_geography",
        "traversability",
        "rng_independence",
        "resource_geography",
    )
    aggregate = {g: all(r["gates"][g] for r in per_seed) for g in gate_names}
    # STRUCTURED_TERRAIN keeps ambient OFF (ambient is STRUCTURED_WORLD only).
    _cfg_chk = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN, trickle=0.0)
    _rt_chk = PhysicalSystemRuntime(seed=SEEDS[0], config=_cfg_chk)
    ambient_off = (
        bool(getattr(_cfg_chk.planet.ambient, "enabled", False)) is False
        and _rt_chk.world.ambient_fx is None
        and _rt_chk.world.ambient_fy is None
    )
    aggregate["ambient_off"] = ambient_off
    gate_names = gate_names + ("ambient_off",)
    summary = {
        "experiment": "PHYSICAL_GEOGRAPHY_01",
        "ecology_preset": ECOLOGY_STRUCTURED_TERRAIN,
        "ambient_enabled": False,
        "ambient_off_verified": ambient_off,
        "seeds": list(SEEDS),
        "elapsed_s": time.perf_counter() - t0,
        "generator_version": TERRAIN_GENERATOR_VERSION,
        "per_seed": per_seed,
        "gates": aggregate,
        "all_passed": all(aggregate.values()),
        "allowed_claim": (
            "Multi-scale structured terrain is reproducible, spatially correlated, "
            "physically traversable, RNG-isolated from cognition/climate stepping, "
            "and geography-conditions resource fields without leaking suitability into "
            "agent_observation. Ambient horizontal force remains OFF under "
            "STRUCTURED_TERRAIN_EXPERIMENTAL (enabled only in STRUCTURED_WORLD)."
        ),
    }
    _write(out / "summary.json", summary)
    _write(out / "per_seed.json", per_seed)

    lines = [
        "# PHYSICAL_GEOGRAPHY_01",
        "",
        "Structured terrain geography validation (physics only).",
        "",
        f"Seeds: {list(SEEDS)}",
        f"Generator: {TERRAIN_GENERATOR_VERSION}",
        "",
        "## Gates",
        "",
    ]
    for g in gate_names:
        status = "PASS" if aggregate[g] else "FAIL"
        lines.append(f"- **{g}**: {status}")
    lines.append("")
    lines.append("## Per-seed checksums / attempts")
    lines.append("")
    for r in per_seed:
        lines.append(
            f"- seed {r['seed']}: checksum={r['checksum']} "
            f"attempt={r['generation_attempt']} accepted={r['generation_accepted']} "
            f"nbr_ratio={r['correlated_geography']['ratio_vs_noise']:.3f} "
            f"spA={r['resource_geography']['corr_R_A_geo_A_t0']['spearman']:.3f} "
            f"spB={r['resource_geography']['corr_R_B_geo_B_t0']['spearman']:.3f}"
        )
    lines.append("")
    lines.append(f"Overall: {'PASS' if summary['all_passed'] else 'FAIL'}")
    lines.append("")
    report = "\n".join(lines) + "\n"
    _write(out / "REPORT.md", report)

    print(f"out_dir={out}")
    n_pass = sum(1 for v in aggregate.values() if v)
    n_fail = len(aggregate) - n_pass
    print(f"gates: {n_pass} PASS / {n_fail} FAIL")
    for g, ok in aggregate.items():
        print(f"  {'PASS' if ok else 'FAIL'}: {g}")
    if not summary["all_passed"]:
        for r in per_seed:
            fails = [k for k, v in r["gates"].items() if not v]
            if fails:
                print(f"  seed {r['seed']} failed: {fails}")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
