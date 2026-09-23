#!/usr/bin/env python3
"""LIVE OPTICAL PERFORMANCE — lean exposure-centered profiling.

Avoids per-tick extra sample_near_field probes (those distort the measurement).
Exposure detection uses chebyshev proximity ≤ vision_radius as WINDOW proxy,
with periodic authoritative optical GT samples for confirmation.
"""
from __future__ import annotations

import csv
import json
import resource
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "live_optical_performance"
OUT.mkdir(parents=True, exist_ok=True)

SEEDS = (17, 23, 41, 59, 83)
PRIMARY_SEED = 17


def _write(name: str, obj: Any) -> None:
    path = OUT / name
    if isinstance(obj, str):
        path.write_text(obj)
    else:
        path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")
    print("wrote", path, flush=True)


def _rss_mb() -> float:
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def _make_session(*, seed: int, vision: bool = True, vision_radius: int = 3,
                  execution_mode: str = "HEADLESS", ui_hz: float = 1.0,
                  place_adjacent: bool = False):
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
    s = ObserverSession(SessionConfig(
        seed=seed, cognition_enabled=True, execution_mode=execution_mode,
        ui_hz=ui_hz, buffer_capacity=128,
    ))
    s.apply_experiment({
        "seed": seed,
        "agent_count": 2,
        "vision_radius": int(vision_radius),
        "cognition_enabled": True,
        "mechanisms": {
            "physical_near_field_vision": bool(vision),
            "spatiotemporal_climate_ecology": False,
        },
    })
    s.set_execution_mode(execution_mode)
    if vision:
        s.set_vision_radius(int(vision_radius))
    if place_adjacent and getattr(s.runtime, "slots", None):
        s.runtime.slots[0].body.x = 16.0
        s.runtime.slots[0].body.y = 16.0
        s.runtime.slots[0].body.vx = 0.0
        s.runtime.slots[0].body.vy = 0.0
        s.runtime.slots[1].body.x = 17.5
        s.runtime.slots[1].body.y = 16.0
        s.runtime.slots[1].body.vx = 0.0
        s.runtime.slots[1].body.vy = 0.0
    return s


def dump_effective_configuration(s) -> dict[str, Any]:
    integ = s.mechanism_integrity_status()
    rows = (integ.get("preflight") or {}).get("rows") or integ.get("rows") or []
    required_on = [
        "physical_near_field_vision", "articulated_head", "physical_vestibular_sensing",
        "neck_proprioception", "physical_push", "experimental_physical_signal",
        "oscillatory_signaling", "resource_ecology_A", "resource_ecology_B",
        "terrain_geography", "ambient_physical_dynamics", "illumination_cycle", "cognition",
    ]
    status = {}
    for mid in required_on:
        row = next((r for r in rows if r.get("mechanism") == mid), None)
        status[mid] = {
            "configured": None if row is None else row.get("configured"),
            "runtime": None if row is None else row.get("runtime"),
            "status": None if row is None else row.get("status"),
        }
    clim = next((r for r in rows if r.get("mechanism") == "spatiotemporal_climate_ecology"), {})
    vision = next((r for r in rows if r.get("mechanism") == "physical_near_field_vision"), {})
    return {
        "ready": integ.get("ready"),
        "climate": clim,
        "vision": vision,
        "required_on": status,
        "all_required_on": all(
            status[m]["configured"] and status[m]["runtime"] and status[m]["status"] == "READY"
            for m in required_on
        ),
        "climate_off": clim.get("configured") is False and clim.get("runtime") is False,
        "fingerprint": (integ.get("preflight") or {}).get("resolved_fingerprint"),
    }


def _chebyshev(runtime) -> float | None:
    slots = getattr(runtime, "slots", None)
    if not slots or len(slots) < 2:
        return None
    a, b = slots[0].body, slots[1].body
    w = float(getattr(runtime.config.planet, "width", 32) or 32)
    h = float(getattr(runtime.config.planet, "height", 32) or 32)
    dx = abs(float(a.x) - float(b.x))
    dy = abs(float(a.y) - float(b.y))
    dx = min(dx, w - dx)
    dy = min(dy, h - dy)
    return max(dx, dy)


def _optical_gt_once(runtime) -> dict[str, Any]:
    """Authoritative other-body optical exposure (expensive — call sparsely)."""
    from mechanistic_mind.physical_system.near_field_exteroception import (
        cognition_exo_fragments, sample_near_field,
    )
    from mechanistic_mind.ui.psy_observer_web.scientific_history import body_derived_exo_contribution
    out = {"agent_exposure": [], "n_body_optical_cells": []}
    for i, slot in enumerate(runtime.slots):
        nfe = slot.config.near_field_exteroception
        fb = runtime.foreign_bodies_for(i)
        cleaned = [(item[0], item[1]) for item in (fb or []) if len(item) >= 2]
        sample = sample_near_field(world=slot.world, body=slot.body, cfg=nfe, foreign_bodies=cleaned)
        exo = dict(sample.get("fragments") or {})
        exo_wo = cognition_exo_fragments(world=slot.world, body=slot.body, cfg=nfe, foreign_bodies=[])
        der = body_derived_exo_contribution(exo, exo_wo)
        out["agent_exposure"].append(bool(der.get("body_exposure")))
        out["n_body_optical_cells"].append(int(sample.get("n_body_optical_cells") or 0))
    return out


def _window_stats(samples_ms: list[float]) -> dict[str, Any]:
    if not samples_ms:
        return {"n": 0}
    mean = sum(samples_ms) / len(samples_ms)
    return {
        "n": len(samples_ms),
        "mean_ms": mean,
        "tps": 1000.0 / mean if mean > 0 else None,
        "p50_ms": sorted(samples_ms)[len(samples_ms) // 2],
        "p90_ms": sorted(samples_ms)[int(0.9 * (len(samples_ms) - 1))],
    }


def _cognition_sizes(runtime) -> dict[str, Any]:
    from mechanistic_mind.research.webui_perf_profile import cognition_store_sizes
    return cognition_store_sizes(runtime)


def profile_run(
    *,
    seed: int,
    ticks: int,
    vision: bool = True,
    vision_radius: int = 3,
    execution_mode: str = "HEADLESS",
    ui_hz: float = 1.0,
    place_adjacent: bool = False,
    label: str = "run",
    gt_every: int = 25,
) -> dict[str, Any]:
    from mechanistic_mind.research.webui_perf_profile import (
        StageTimer, install_runtime_stage_timers, install_session_stage_timers,
    )
    import mechanistic_mind.physical_system.near_field_exteroception as nfe_mod
    import mechanistic_mind.physical_system.cognition as cog_mod

    s = _make_session(
        seed=seed, vision=vision, vision_radius=vision_radius,
        execution_mode=execution_mode, ui_hz=ui_hz, place_adjacent=place_adjacent,
    )
    cfg = dump_effective_configuration(s)
    timer = StageTimer()
    restores = [
        install_runtime_stage_timers(s.runtime, timer),
        install_session_stage_timers(s, timer),
    ]
    orig_snf = nfe_mod.sample_near_field

    def wrap_snf(*a, **k):
        with timer.stage("vision.sample_near_field"):
            return orig_snf(*a, **k)

    nfe_mod.sample_near_field = wrap_snf
    restores.append(lambda: setattr(nfe_mod, "sample_near_field", orig_snf))

    orig_cog = cog_mod.run_cognition_before_action

    def wrap_cog(*a, **k):
        with timer.stage("cognition.run_before_action"):
            return orig_cog(*a, **k)

    cog_mod.run_cognition_before_action = wrap_cog
    restores.append(lambda: setattr(cog_mod, "run_cognition_before_action", orig_cog))

    tick_ms: list[float] = []
    trace: list[dict[str, Any]] = []
    first_prox: int | None = None  # chebyshev <= R
    first_optical: int | None = None
    first_mutual: int | None = None
    R = float(vision_radius)

    for _ in range(ticks):
        t0 = time.perf_counter()
        s.step(1)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        tick_ms.append(dt_ms)
        timer.record_tick(dt_ms / 1000.0)
        tick = int(s.runtime.tick)
        d = _chebyshev(s.runtime)
        in_range = d is not None and d <= R + 1e-9
        if in_range and first_prox is None:
            first_prox = tick

        row = {
            "tick": tick,
            "total_ms": round(dt_ms, 4),
            "chebyshev": None if d is None else round(d, 4),
            "in_vision_range_proxy": in_range,
            "rss_mb": round(_rss_mb(), 2),
        }
        if tick % gt_every == 0 or tick == 1:
            gt = _optical_gt_once(s.runtime)
            row["agent_0_other_body_optical_exposure"] = gt["agent_exposure"][0]
            row["agent_1_other_body_optical_exposure"] = gt["agent_exposure"][1]
            row["n_body_optical_cells"] = gt["n_body_optical_cells"]
            if any(gt["agent_exposure"]) and first_optical is None:
                first_optical = tick
            if all(gt["agent_exposure"]) and first_mutual is None:
                first_mutual = tick
            row["cognition_sizes"] = _cognition_sizes(s.runtime)
        trace.append(row)

    for r in restores:
        try:
            r()
        except Exception:
            pass

    # Windows by proximity proxy (cheap) + optical confirmation
    anchor = first_optical or first_prox
    windows = {"pre_exposure": [], "first_exposure_pm100": [], "sustained_exposure": [], "far": []}
    for i, ms in enumerate(tick_ms):
        tick = i + 1
        drow = next((r for r in trace if r["tick"] == tick), {})
        in_range = bool(drow.get("in_vision_range_proxy"))
        if anchor is None:
            windows["pre_exposure"].append(ms)
        elif tick < anchor:
            windows["pre_exposure"].append(ms)
        elif abs(tick - anchor) <= 100:
            windows["first_exposure_pm100"].append(ms)
        elif in_range:
            windows["sustained_exposure"].append(ms)
        else:
            windows["far"].append(ms)

    return {
        "label": label,
        "seed": seed,
        "ticks": ticks,
        "vision": vision,
        "vision_radius": vision_radius,
        "execution_mode": execution_mode,
        "place_adjacent": place_adjacent,
        "effective_configuration": cfg,
        "first_proximity_tick": first_prox,
        "first_optical_exposure_tick": first_optical,
        "first_mutual_exposure_tick": first_mutual,
        "overall": _window_stats(tick_ms),
        "windows": {k: _window_stats(v) for k, v in windows.items()},
        "stages": timer.summary(),
        "trace": trace,
        "final_cognition": _cognition_sizes(s.runtime),
        "final_rss_mb": _rss_mb(),
    }


def main() -> int:
    print("=== LOP effective config ===", flush=True)
    s0 = _make_session(seed=PRIMARY_SEED)
    eff = dump_effective_configuration(s0)
    _write("effective_configuration.json", eff)
    if not (eff.get("all_required_on") and eff.get("climate_off")):
        print("CONFIG FAIL", eff)
        return 1

    # Natural repro scan (shorter)
    print("=== reproduction scan ===", flush=True)
    repro = {"candidates": []}
    selected_seed = PRIMARY_SEED
    natural_hit = False
    for seed in SEEDS:
        r = profile_run(seed=seed, ticks=900, label=f"repro_{seed}", gt_every=30)
        entry = {
            "seed": seed,
            "first_proximity_tick": r["first_proximity_tick"],
            "first_optical_exposure_tick": r["first_optical_exposure_tick"],
            "first_mutual_exposure_tick": r["first_mutual_exposure_tick"],
            "overall_tps": r["overall"].get("tps"),
            "pre_tps": r["windows"]["pre_exposure"].get("tps"),
            "exposure_tps": r["windows"]["first_exposure_pm100"].get("tps"),
            "sustained_tps": r["windows"]["sustained_exposure"].get("tps"),
        }
        repro["candidates"].append(entry)
        print("  seed", seed, entry, flush=True)
        if r["first_optical_exposure_tick"] is not None and not natural_hit:
            selected_seed = seed
            natural_hit = True
            repro["selected"] = entry

    use_adjacent = not natural_hit
    if use_adjacent:
        print("=== no natural optical hit; adjacent fixture ===", flush=True)
        selected_seed = PRIMARY_SEED
        repro["fixture"] = "place_adjacent_diagnostic"
    _write("reproduction.json", repro)

    print("=== deep HEADLESS profile ===", flush=True)
    deep = profile_run(
        seed=selected_seed, ticks=2000, label="deep_headless",
        place_adjacent=use_adjacent, gt_every=20,
    )
    _write("exposure_timeline.json", {
        "seed": selected_seed,
        "place_adjacent_fixture": use_adjacent,
        "first_proximity_tick": deep["first_proximity_tick"],
        "first_optical_exposure_tick": deep["first_optical_exposure_tick"],
        "first_mutual_exposure_tick": deep["first_mutual_exposure_tick"],
    })
    _write("transition_profile.json", {
        "windows": deep["windows"],
        "overall": deep["overall"],
        "stages": deep["stages"],
    })

    # CSV
    csv_path = OUT / "per_tick_trace.csv"
    fields = ["tick", "total_ms", "chebyshev", "in_vision_range_proxy",
              "agent_0_other_body_optical_exposure", "agent_1_other_body_optical_exposure", "rss_mb"]
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in deep["trace"]:
            w.writerow(row)
    print("wrote", csv_path, flush=True)
    _write("per_tick_trace_summary.json", {
        "n": len(deep["trace"]),
        "windows": deep["windows"],
    })

    # Cognition growth samples
    samples = [row for row in deep["trace"] if "cognition_sizes" in row]
    _write("cognition_store_growth.json", {
        "anchor_optical": deep["first_optical_exposure_tick"],
        "samples": samples[:40],
        "final": deep["final_cognition"],
    })
    stages = deep["stages"].get("stages") or []
    _write("cognition_profile.json", {
        "top_stages": stages[:15],
        "cognition_stage": next((x for x in stages if "cognition" in x["stage"]), None),
        "begin_tick_stages": [x for x in stages if "begin_tick" in x["stage"]],
    })
    _write("vision_physics_profile.json", {
        "sample_near_field": next((x for x in stages if x["stage"] == "vision.sample_near_field"), None),
        "observations": next((x for x in stages if x["stage"] == "ta.observations"), None),
        "append_scientific": next((x for x in stages if x["stage"] == "sess.append_scientific"), None),
    })

    print("=== Vision ON/OFF ablation ===", flush=True)
    on = profile_run(seed=selected_seed, ticks=700, vision=True, place_adjacent=True, label="von", gt_every=35)
    off = profile_run(seed=selected_seed, ticks=700, vision=False, place_adjacent=True, label="voff", gt_every=35)
    _write("vision_ablation.json", {
        "vision_on": {"overall": on["overall"], "windows": on["windows"], "top_stages": (on["stages"].get("stages") or [])[:8]},
        "vision_off": {"overall": off["overall"], "windows": off["windows"], "top_stages": (off["stages"].get("stages") or [])[:8]},
        "note": "Performance only; trajectories diverge",
    })

    print("=== R1/R2/R3 ===", flush=True)
    scaling = {}
    for r in (1, 2, 3):
        pr = profile_run(seed=selected_seed, ticks=500, vision_radius=r, place_adjacent=True, label=f"R{r}", gt_every=40)
        scaling[f"R{r}"] = {
            "overall": pr["overall"],
            "windows": pr["windows"],
            "vision_stage": next((x for x in (pr["stages"].get("stages") or []) if x["stage"] == "vision.sample_near_field"), None),
            "cognition_stage": next((x for x in (pr["stages"].get("stages") or []) if "cognition" in x["stage"]), None),
            "first_optical": pr["first_optical_exposure_tick"],
        }
    _write("vision_range_scaling.json", scaling)

    print("=== HEADLESS vs LIVE ===", flush=True)
    live = profile_run(seed=selected_seed, ticks=500, execution_mode="LIVE", ui_hz=10.0,
                       place_adjacent=True, label="live", gt_every=40)
    head = profile_run(seed=selected_seed, ticks=500, execution_mode="HEADLESS", ui_hz=1.0,
                       place_adjacent=True, label="head", gt_every=40)
    _write("observer_profile.json", {
        "live": {"overall": live["overall"], "windows": live["windows"], "top": (live["stages"].get("stages") or [])[:10]},
        "headless": {"overall": head["overall"], "windows": head["windows"], "top": (head["stages"].get("stages") or [])[:10]},
    })
    hz = {}
    for h in (1.0, 5.0, 10.0):
        pr = profile_run(seed=selected_seed, ticks=300, execution_mode="LIVE", ui_hz=h,
                         place_adjacent=True, label=f"hz{h}", gt_every=50)
        hz[str(h)] = {"overall": pr["overall"], "windows": pr["windows"]}
    _write("observer_hz_scaling.json", hz)

    _write("contact_control.json", {
        "note": "Contact not separately forced; proximity fixture used",
        "first_optical": deep["first_optical_exposure_tick"],
    })
    _write("signal_control.json", {"signals_enabled_in_primary": True})
    _write("event_rate_profile.json", {
        "accumulate_events": next((x for x in stages if x["stage"] == "sess.accumulate_events"), None),
    })
    _write("action_space_profile.json", {"composite_motor": True})
    _write("long_exposure_profile.json", {
        "ticks": 2000,
        "windows": deep["windows"],
        "rss_final_mb": deep["final_rss_mb"],
    })

    # Classify root cause
    on_tps = on["overall"].get("tps") or 0
    off_tps = off["overall"].get("tps") or 0
    pre = deep["windows"]["pre_exposure"].get("tps")
    exp = deep["windows"]["first_exposure_pm100"].get("tps")
    sus = deep["windows"]["sustained_exposure"].get("tps")
    top = stages[0] if stages else {}
    cog = next((x for x in stages if "cognition" in x["stage"]), None)
    vis = next((x for x in stages if x["stage"] == "vision.sample_near_field"), None)
    sci = next((x for x in stages if x["stage"] == "sess.append_scientific"), None)
    live_tps = live["overall"].get("tps") or 0
    head_tps = head["overall"].get("tps") or 0

    if off_tps > on_tps * 1.2 and cog and cog.get("pct_of_staged", 0) > 25:
        cause = "COGNITION_AFTER_NOVEL_EXO_INPUT"
    elif off_tps > on_tps * 1.2 and vis and vis.get("pct_of_staged", 0) > 20:
        cause = "PHYSICAL_VISION_SAMPLING"
    elif sci and sci.get("pct_of_staged", 0) > 25:
        cause = "SCIENTIFIC_TELEMETRY_OPTICAL_GT"
    elif live_tps and head_tps and live_tps < 0.7 * head_tps:
        cause = "OBSERVER_LIVE_CAPTURE"
    else:
        cause = "MIXED_EXPOSURE_CORRELATED"

    dominant = {
        "classified_root_cause": cause,
        "top_stage": top,
        "pre_tps": pre,
        "exposure_tps": exp,
        "sustained_tps": sus,
        "vision_on_tps": on_tps,
        "vision_off_tps": off_tps,
        "live_tps": live_tps,
        "headless_tps": head_tps,
        "cognition_stage": cog,
        "vision_stage": vis,
        "scientific_stage": sci,
    }
    _write("complexity_audit.json", dominant)
    _write("optimization_candidates.json", {
        "dominant_cause": cause,
        "candidates": [
            {
                "id": "cache_counterfactual_optical_gt",
                "why": "scientific_history._compact_vision_optical_for_slot samples near_field twice per agent/tick",
                "class": "same-tick / writer optimization",
            },
            {
                "id": "tick_scoped_observation_signature_cache",
                "why": "novel exo may inflate PSC/compression work via repeated _q",
                "class": "cognition same-tick cache",
            },
            {
                "id": "bound_live_capture_under_exposure",
                "why": "LIVE may amplify observer cost vs HEADLESS",
                "class": "observer",
            },
        ],
    })

    summary = f"""# LIVE OPTICAL PERFORMANCE

Generated: {datetime.now(timezone.utc).isoformat()}

## Config OK
{eff.get('all_required_on') and eff.get('climate_off')}

## Exposure
seed={selected_seed} adjacent_fixture={use_adjacent}
optical={deep.get('first_optical_exposure_tick')} proximity={deep.get('first_proximity_tick')}

## Transition t/s
pre={pre} exposure±100={exp} sustained={sus}

## Vision ablation t/s
ON={on_tps} OFF={off_tps}

## HEADLESS vs LIVE
HEADLESS={head_tps} LIVE={live_tps}

## Root cause
{cause}

## Top stage
{json.dumps(top, indent=2)}
"""
    _write("SUMMARY.md", summary)
    print(summary, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
