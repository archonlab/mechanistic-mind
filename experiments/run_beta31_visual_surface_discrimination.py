#!/usr/bin/env python3
"""Beta 3.1 controlled comparison: surface discrimination OFF vs RICH.

Does not claim RICH is better. Measures organization and cost.
GIT_PUSH=NO.
"""
from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path

import numpy as np

from mechanistic_mind.physical_system.near_field_exteroception import (
    NearFieldExteroceptionConfig,
    surface_observation_keys,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.physical_system.sensorimotor_consequence import SENSORY_CHANNELS

OUT = Path("results/beta31_visual_surface_discrimination")


def _cfg(disc: str, *, mapping: str, psc_off_ticks: int | None) -> PhysicalSystemConfig:
    cfg = PhysicalSystemConfig()
    cfg.near_field_exteroception = NearFieldExteroceptionConfig(
        mode="EXPERIMENTAL",
        perception_enabled=True,
        illumination_enabled=True,
        surface_enabled=True,
        radius=3,
        visual_surface_discrimination=disc,
        optical_mapping=mapping,
        optical_correlation=0.35,
    )
    cfg.cognition.psc_motor_resolution = "OBSERVED_COMPOSITE"
    cfg.cognition.psc_off_ticks = psc_off_ticks
    cfg.cognition.predictive_compression = True
    cfg.cognition.predictive_equivalence = True
    cfg.cognition.prospective_composition = True
    cfg.cognition.sensorimotor_consequence_model = True
    return cfg


def _enable_vision(rt: TwoAgentRuntime) -> None:
    rt.set_mechanism("physical_near_field_vision", True)
    rt.set_mechanism("articulated_head", True)
    rt.set_mechanism("prospective_scenario_competition", False)
    rt.set_psc_motor_resolution("OBSERVED_COMPOSITE")


def _store_size(rt: TwoAgentRuntime) -> dict:
    out = {}
    for i, slot in enumerate(rt.slots):
        cog = slot.cognition or {}
        smc = cog.get("sensorimotor_consequence") or {}
        rec = smc.get("records") or {}
        pe = cog.get("equivalence") or {}
        pc = cog.get("compression") or cog.get("predictive_compression") or {}
        out[f"agent_{i}"] = {
            "smc_records": len(rec) if isinstance(rec, dict) else 0,
            "pe_enabled": bool(pe.get("enabled")),
            "tick": int(slot.tick),
        }
        out[f"agent_{i}"]["compression_keys"] = len(pc) if isinstance(pc, dict) else 0
    return out


def _obs_stats(rt: TwoAgentRuntime, disc: str) -> dict:
    keys = surface_observation_keys(disc)
    stats = {}
    for i, slot in enumerate(rt.slots):
        obs = slot.last_agent_observation or slot.agent_observation()
        surf = {k: float(obs.get(k) or 0.0) for k in keys}
        exo = {k: float(obs.get(k) or 0.0) for k in ("exo_0", "exo_1", "exo_2")}
        stats[f"agent_{i}"] = {
            "surface": surf,
            "exo": exo,
            "n_surface_keys": len(keys),
            "surface_sum": float(sum(surf.values())),
            "exo_sum": float(sum(exo.values())),
        }
    return stats


def run_arm(*, disc: str, mapping: str, ticks: int, seed: int, psc_off: int) -> dict:
    cfg = _cfg(disc, mapping=mapping, psc_off_ticks=psc_off)
    rt = TwoAgentRuntime(seed=seed, config=cfg)
    _enable_vision(rt)
    rt.set_visual_surface_discrimination(disc)
    tracemalloc.start()
    t0 = time.perf_counter()
    checkpoints = {}
    for horizon in (1000, 5000, 10000):
        if ticks < horizon:
            continue
        remain = horizon - int(rt.tick)
        if remain > 0:
            rt.step(remain)
        elapsed = time.perf_counter() - t0
        current, peak = tracemalloc.get_traced_memory()
        w = rt.world
        opt = getattr(w, "surface_optical", None)
        snap_bytes = int(w.T.nbytes)
        if getattr(w, "surface_response", None) is not None:
            snap_bytes += int(w.surface_response.nbytes)
        if opt is not None:
            snap_bytes += int(np.asarray(opt).nbytes)
        checkpoints[str(horizon)] = {
            "elapsed_s": elapsed,
            "ms_per_tick": 1000.0 * elapsed / max(1, horizon),
            "ticks_per_sec": horizon / elapsed if elapsed > 0 else None,
            "rss_traced_peak_mb": peak / (1024 * 1024),
            "snapshot_bytes": snap_bytes,
            "stores": _store_size(rt),
            "obs": _obs_stats(rt, disc),
            "psc_activated": bool(getattr(rt.slots[0], "_psc_auto_activated", False)),
        }
    tracemalloc.stop()
    motors = []
    for slot in rt.slots:
        st = {}
        # last action only; full histogram is in slot stats if present
        motors.append({"last": slot.last_selected_action})
    return {
        "disc": disc,
        "mapping": mapping,
        "seed": seed,
        "ticks": ticks,
        "psc_off_ticks": psc_off,
        "checkpoints": checkpoints,
        "last_motors": motors,
        "sensory_allowlist_n": len(SENSORY_CHANNELS),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    seed = 20260923
    psc_off = 1000
    # Practical default: 1000 ticks all arms. Set BETA31_SURFACE_TICKS for 5k/10k.
    import os
    ticks = int(os.environ.get("BETA31_SURFACE_TICKS", "1000"))
    arms = [
        run_arm(disc="OFF", mapping="INDEPENDENT", ticks=ticks, seed=seed, psc_off=psc_off),
        run_arm(disc="LOW", mapping="CORRELATED", ticks=ticks, seed=seed, psc_off=psc_off),
        run_arm(disc="RICH", mapping="CORRELATED", ticks=ticks, seed=seed, psc_off=psc_off),
    ]
    payload = {
        "question": (
            "Does adding a physically available surface distinction change the "
            "predictive/sensorimotor organization of the system?"
        ),
        "not_claimed": "Tiktaalik learned colors / recognized terrain",
        "arms": arms,
    }
    path = OUT / "off_low_rich.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({a["disc"]: a["checkpoints"] for a in arms}, indent=2, default=str))
    print("wrote", path)


if __name__ == "__main__":
    main()
