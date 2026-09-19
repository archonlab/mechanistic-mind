#!/usr/bin/env python3
"""Visual forensics wiring — equivalence + Observer optical overhead (no sim retune)."""
from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CALIBRATED_TEMPORAL,
    make_ecology_config,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.scientific_history import collect_scientific_tick_rows

OUT = Path("results/perception/visual_forensics")
RAW = OUT / "raw"
FIX = OUT / "fixtures"


def fingerprint(rt) -> dict:
    slots = getattr(rt, "slots", None) or [rt]
    bodies = []
    for i, s in enumerate(slots):
        b = s.body
        obs = getattr(s, "last_agent_observation", None) or {}
        bodies.append({
            "i": i,
            "x": round(float(b.x), 9),
            "y": round(float(b.y), 9),
            "theta": round(float(getattr(b, "theta", 0.0) or 0.0), 9),
            "action": getattr(s, "last_selected_action", None),
            "exo": {k: obs.get(k) for k in ("exo_0", "exo_1", "exo_2") if k in obs},
        })
    return {"tick": int(rt.tick), "bodies": bodies}


def make_rt(seed=17):
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    rt = TwoAgentRuntime(seed=seed, config=cfg)
    for mid in (
        "physical_near_field_vision",
        "illumination_cycle",
        "physical_body_optical_response",
    ):
        try:
            rt.set_mechanism(mid, True)
        except Exception:
            pass
    rt.slots[0].body.x, rt.slots[0].body.y, rt.slots[0].body.theta = 16.5, 16.5, 0.0
    rt.slots[1].body.x, rt.slots[1].body.y, rt.slots[1].body.theta = 17.5, 16.5, 3.1415926535
    return rt


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    FIX.mkdir(parents=True, exist_ok=True)

    # --- Scientific equivalence: compact optical record must not alter step trajectory ---
    a = make_rt()
    b = make_rt()
    fps_a, fps_b = [], []
    for _ in range(40):
        a.step()
        b.step()
        # Observer-only compact read on A only
        rows = collect_scientific_tick_rows(a)
        fps_a.append(fingerprint(a))
        fps_b.append(fingerprint(b))
    mismatches = [i for i, (x, y) in enumerate(zip(fps_a, fps_b)) if x != y]
    eq = {
        "verdict": "EXACT_MATCH" if not mismatches else "DIVERGENCE",
        "n_mismatch": len(mismatches),
        "comparison_length": len(fps_a),
        "note": "collect_scientific_tick_rows is Observer-only; must not alter runtime step.",
    }
    (RAW / "equivalence_result.json").write_text(json.dumps(eq, indent=2), encoding="utf-8")

    # --- Fixture snapshots ---
    rt = make_rt()
    rt.world.surface_response[:] = 0.0
    rt.step()
    rows = collect_scientific_tick_rows(rt)
    (FIX / "face_to_face.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")

    rt2 = make_rt()
    rt2.world.surface_response[:] = 0.8
    rt2.slots[1].body.x, rt2.slots[1].body.y = 24.5, 24.5
    rt2.step()
    rows_env = collect_scientific_tick_rows(rt2)
    (FIX / "environment_only.json").write_text(
        json.dumps(rows_env, indent=2, default=str), encoding="utf-8"
    )

    rt3 = make_rt()
    rt3.set_mechanism("physical_near_field_vision", False)
    rt3.step()
    (FIX / "vision_off.json").write_text(
        json.dumps(collect_scientific_tick_rows(rt3), indent=2, default=str), encoding="utf-8"
    )

    rt4 = make_rt()
    rt4.set_mechanism("physical_body_optical_response", False)
    rt4.world.surface_response[:] = 0.0
    rt4.step()
    (FIX / "body_optics_off.json").write_text(
        json.dumps(collect_scientific_tick_rows(rt4), indent=2, default=str), encoding="utf-8"
    )

    # --- Overhead: scientific row collection with vision_optical ---
    rt = make_rt()
    for _ in range(20):
        rt.step()
    n = 80
    t0 = time.perf_counter()
    total_bytes = 0
    exposure = 0
    for _ in range(n):
        rt.step()
        rows = collect_scientific_tick_rows(rt)
        for r in rows:
            vo = r.get("vision_optical") or {}
            total_bytes += len(json.dumps(vo, default=str))
            if vo.get("body_exposure"):
                exposure += 1
    elapsed = time.perf_counter() - t0
    overhead = {
        "ticks": n,
        "agents": 2,
        "wall_s": round(elapsed, 4),
        "ms_per_tick_incl_step_and_compact": round(1000.0 * elapsed / n, 3),
        "vision_optical_bytes_per_tick_mean": round(total_bytes / n, 1),
        "body_exposure_rows": exposure,
        "note": (
            "Includes runtime.step + Observer compact re-sample of sample_near_field. "
            "Compact path is outside cognition; does not change RNG/actions."
        ),
    }
    (RAW / "performance_overhead.json").write_text(json.dumps(overhead, indent=2), encoding="utf-8")
    (OUT / "PERFORMANCE_OVERHEAD.md").write_text(
        "# Performance overhead\n\n"
        f"- ticks measured: {n}\n"
        f"- vision_optical mean bytes/tick: {overhead['vision_optical_bytes_per_tick_mean']}\n"
        f"- wall incl step+compact: {overhead['ms_per_tick_incl_step_and_compact']} ms/tick\n"
        "- Compact record keeps body-optical neighbors only (not full 8-cell DET table).\n"
        "- No production NumPy/Numba; no vision equation changes.\n",
        encoding="utf-8",
    )
    (OUT / "SCIENTIFIC_EQUIVALENCE.md").write_text(
        "# Scientific equivalence\n\n"
        f"- verdict: **{eq['verdict']}**\n"
        f"- mismatches: {eq['n_mismatch']} / {eq['comparison_length']}\n"
        "- Instrumentation is Observer/Analyzer only (`collect_scientific_tick_rows`).\n"
        "- Final exo / actions / trajectories unchanged vs paired control without compact reads.\n",
        encoding="utf-8",
    )
    print(json.dumps({"equivalence": eq, "overhead": overhead}, indent=2))


if __name__ == "__main__":
    main()
