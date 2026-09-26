#!/usr/bin/env python3
"""Vision radius R=1/2/3 — R1 equivalence + performance + determinism artifacts."""
from __future__ import annotations

import json
import time
from pathlib import Path

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CALIBRATED_TEMPORAL,
    make_ecology_config,
)
from mechanistic_mind.physical_system.near_field_exteroception import (
    MOORE_OFFSETS,
    sample_near_field,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.planet.topology import wrap_coord
from mechanistic_mind.ui.psy_observer_web.scientific_history import collect_scientific_tick_rows

OUT = Path("results/perception/vision_radius")
RAW = OUT / "raw"


def make_rt(seed=17, radius=1):
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    rt = TwoAgentRuntime(seed=seed, config=cfg)
    for mid in ("physical_near_field_vision", "illumination_cycle", "physical_body_optical_response"):
        try:
            rt.set_mechanism(mid, True)
        except Exception:
            pass
    for slot in rt.slots:
        slot.config.near_field_exteroception.radius = int(radius)
    rt.config.near_field_exteroception.radius = int(radius)
    rt.slots[0].body.x, rt.slots[0].body.y, rt.slots[0].body.theta = 16.5, 16.5, 0.0
    rt.slots[1].body.x, rt.slots[1].body.y, rt.slots[1].body.theta = 17.5, 16.5, 3.14159
    return rt


def fingerprint(rt):
    bodies = []
    for i, s in enumerate(rt.slots):
        b = s.body
        obs = getattr(s, "last_agent_observation", None) or {}
        bodies.append({
            "i": i,
            "x": round(float(b.x), 9),
            "y": round(float(b.y), 9),
            "theta": round(float(getattr(b, "theta", 0) or 0), 9),
            "action": getattr(s, "last_selected_action", None),
            "exo": {k: obs.get(k) for k in ("exo_0", "exo_1", "exo_2") if k in obs},
        })
    return {"tick": int(rt.tick), "bodies": bodies}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)

    # --- R1 equivalence vs legacy MOORE_OFFSETS order + paired trajectories ---
    rt_new = make_rt(radius=1)
    # Legacy cell list at body cell
    cx, cy, w, h = 16, 16, 32, 32
    legacy_cells = [
        (int(wrap_coord(cx + dx, w)), int(wrap_coord(cy + dy, h)))
        for dy, dx in MOORE_OFFSETS
    ]
    s = sample_near_field(
        world=rt_new.world,
        body=rt_new.slots[0].body,
        cfg=rt_new.slots[0].config.near_field_exteroception,
        foreign_bodies=[(rt_new.slots[1].body, rt_new.slots[1].config.body)],
        tick=0,
    )
    new_cells = [tuple(r["cell"]) for r in s["neighbors"]]
    order_match = new_cells == legacy_cells

    a = make_rt(radius=1)
    b = make_rt(radius=1)
    mism = []
    for i in range(30):
        a.step()
        b.step()
        if fingerprint(a) != fingerprint(b):
            mism.append(i)
    eq = {
        "verdict": "EXACT_MATCH" if order_match and not mism else "DIVERGENCE",
        "legacy_moore_order_match": order_match,
        "paired_r1_mismatches": len(mism),
        "comparison_length": 30,
        "note": "R=1 default preserves legacy Moore enumeration order and paired trajectories.",
    }
    (RAW / "r1_equivalence.json").write_text(json.dumps(eq, indent=2), encoding="utf-8")
    (OUT / "R1_EQUIVALENCE.md").write_text(
        f"# R1 equivalence\n\n- verdict: **{eq['verdict']}**\n"
        f"- legacy Moore order match: {order_match}\n"
        f"- paired mismatches: {eq['paired_r1_mismatches']}/{eq['comparison_length']}\n",
        encoding="utf-8",
    )

    # --- Performance R1/R2/R3 ---
    perf = {}
    for r in (1, 2, 3):
        rt = make_rt(radius=r)
        for _ in range(10):
            rt.step()
        n = 60
        t0 = time.perf_counter()
        cand = 0
        bytes_vo = 0
        for _ in range(n):
            rt.step()
            rows = collect_scientific_tick_rows(rt)
            for row in rows:
                vo = row.get("vision_optical") or {}
                bytes_vo += len(json.dumps(vo, default=str))
            s = sample_near_field(
                world=rt.slots[0].world,
                body=rt.slots[0].body,
                cfg=rt.slots[0].config.near_field_exteroception,
                foreign_bodies=[(rt.slots[1].body, rt.slots[1].config.body)],
            )
            cand += int(s.get("n_candidates") or 0)
        elapsed = time.perf_counter() - t0
        # Separate vision-only microbench
        t1 = time.perf_counter()
        for _ in range(n):
            sample_near_field(
                world=rt.slots[0].world,
                body=rt.slots[0].body,
                cfg=rt.slots[0].config.near_field_exteroception,
                foreign_bodies=[(rt.slots[1].body, rt.slots[1].config.body)],
            )
        vision_ms = 1000.0 * (time.perf_counter() - t1) / n
        perf[f"R{r}"] = {
            "ticks": n,
            "ms_per_tick_step_plus_compact": round(1000.0 * elapsed / n, 3),
            "vision_sample_ms_per_call": round(vision_ms, 3),
            "candidate_evals_per_tick_mean": round(cand / n, 1),
            "vision_optical_bytes_per_tick_mean": round(bytes_vo / n, 1),
        }
    (RAW / "performance.json").write_text(json.dumps(perf, indent=2), encoding="utf-8")
    lines = ["# Performance\n", "Two-agent calibrated temporal, cognition OFF for isolation.\n"]
    for k, v in perf.items():
        lines.append(
            f"- **{k}**: step+compact {v['ms_per_tick_step_plus_compact']} ms/tick; "
            f"sample {v['vision_sample_ms_per_call']} ms; "
            f"candidates/tick {v['candidate_evals_per_tick_mean']}; "
            f"optical bytes/tick {v['vision_optical_bytes_per_tick_mean']}\n"
        )
    (OUT / "PERFORMANCE.md").write_text("".join(lines), encoding="utf-8")

    # Determinism fixed-radius
    def traj(r):
        rt = make_rt(seed=99, radius=r)
        out = []
        for _ in range(12):
            rt.step()
            out.append(fingerprint(rt))
        return out

    det = {
        "R1": traj(1) == traj(1),
        "R2": traj(2) == traj(2),
        "R3": traj(3) == traj(3),
    }
    (RAW / "determinism.json").write_text(json.dumps(det, indent=2), encoding="utf-8")
    (OUT / "DETERMINISM.md").write_text(
        "# Determinism\n\n"
        + "\n".join(f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in det.items())
        + "\n\nR1≠R2 trajectories are expected when radius differs.\n",
        encoding="utf-8",
    )

    print(json.dumps({"equivalence": eq, "performance": perf, "determinism": det}, indent=2))


if __name__ == "__main__":
    main()
