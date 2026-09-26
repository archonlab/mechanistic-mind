#!/usr/bin/env python3
"""Post packed-L1 whole-cognition reprofile. Measurement only."""
from __future__ import annotations

import hashlib
import json
import time
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CKPT = (
    ROOT
    / "results/psychology_observer/psy_observer_web"
    / "psyweb-20260925T071301.453542Z-749aeea4"
    / "physical_system_snapshot.json"
)
OUT = ROOT / "results/beta31_post_compose_reprofile"
BENCH_TICKS = 120


def _pctile(xs, p):
    if not xs:
        return None
    ys = sorted(xs)
    i = min(len(ys) - 1, max(0, int(round((p / 100.0) * (len(ys) - 1)))))
    return ys[i]


def _bkt(snap, name):
    for b in snap.get("buckets") or []:
        if b.get("name") == name:
            return b
    return {}


def _pack_rows(slot):
    from mechanistic_mind.research import psc_opt
    pack = psc_opt.ensure_pack(slot.cognition["prospection"])
    return {a: len(v) for a, v in (pack.get("by_action") or {}).items()}


def main() -> None:
    from mechanistic_mind.model.tiktaalik import tiktaalik_cognition_config
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import psc_opt
    from mechanistic_mind.research import tick_profiler as tp
    from mechanistic_mind.physical_system.actions import available_actions, OSC_ACTIONS

    OUT.mkdir(parents=True, exist_ok=True)

    assert psc_opt.packed_l1_mode() == "auto"
    src = Path(psc_opt.__file__).read_text()
    assert "def soft_match_packed_matrix" in src
    assert "hit = soft_match_packed_matrix" in src
    assert 'mode == "numpy"' in src  # present but not default

    cold.set_cold_archive(False)
    cold.set_cold_eviction(False)

    orig_ensure = psc_opt.ensure_pack
    pack_stats = {"calls": 0, "rebuilds": 0, "rebuild_ns": []}

    def ensure(store):
        pack_stats["calls"] += 1
        pack = store.get("_psc_pack")
        ver = int(store.get("_psc_pack_version") or 0)
        hit = isinstance(pack, dict) and int(pack.get("version") or -1) == ver
        t0 = time.perf_counter_ns()
        out = orig_ensure(store)
        if not hit:
            pack_stats["rebuilds"] += 1
            pack_stats["rebuild_ns"].append(time.perf_counter_ns() - t0)
        return out

    psc_opt.ensure_pack = ensure

    print("load", CKPT, flush=True)
    with open(CKPT) as f:
        payload = json.load(f)

    rt = TwoAgentRuntime.restore(deepcopy(payload))
    slot0 = rt.slots[0]
    cog = slot0.config.cognition
    vis = slot0.config.near_field_exteroception
    stock = tiktaalik_cognition_config()
    cog_d = cog.to_dict()
    stock_d = stock.to_dict()
    diffs = {k: {"stock": stock_d.get(k), "runtime": cog_d.get(k)} for k in cog_d if cog_d.get(k) != stock_d.get(k)}
    classification = "STOCK_BETA31" if not diffs else "BETA31_WITH_RESEARCH_OVERRIDES"
    mech_on = sorted(k for k, v in cog_d.items() if v is True)
    mech_off = sorted(k for k, v in cog_d.items() if v is False)
    fp_src = json.dumps(
        {
            "cognition": cog_d,
            "ecology": slot0.config.ecology_preset,
            "vision": {
                "enabled": getattr(vis, "enabled", None),
                "surface_discrimination": getattr(vis, "surface_discrimination", None),
                "spatial_vision": getattr(vis, "spatial_vision", None),
                "surface_mode": getattr(vis, "surface_mode", None),
                "radius": getattr(vis, "radius", None),
                "n_sectors": getattr(vis, "n_sectors", None),
            },
            "psc_motor": cog.psc_motor_resolution,
            "seed": rt.seed,
            "agents": len(rt.slots),
        },
        sort_keys=True,
        default=str,
    )
    fingerprint = hashlib.sha1(fp_src.encode()).hexdigest()[:16]

    rows0 = _pack_rows(rt.slots[0])
    rows1 = _pack_rows(rt.slots[1])

    tps0 = rt.slots[0].cognition.get("temporal") or {}
    tpe0 = rt.slots[0].cognition.get("temporal_prediction_error") or {}
    tps_size = {
        "ring": len(tps0.get("ring") or []),
        "by_key": len(tps0.get("by_key") or tps0.get("index") or {}),
        "keys": sorted(tps0.keys())[:24],
    }
    tpe_lags = list((tpe0.get("lags") or {}).keys())

    sig_on = bool(slot0.config.physical_signal.enabled)
    osc_cfg = slot0.config.oscillatory_signaling
    osc_mech = bool(getattr(osc_cfg, "enabled", False))
    compose_actions = list(available_actions())
    osc_in_compose = [a for a in compose_actions if a in OSC_ACTIONS]

    run_config = {
        "source_run": "psyweb-20260925T071301.453542Z-749aeea4",
        "source_tick": payload.get("tick"),
        "classification": classification,
        "runtime_fingerprint": fingerprint,
        "agent_count": len(rt.slots),
        "seed": int(rt.seed),
        "independent_agent_seeds": getattr(rt, "independent_agent_seeds", None),
        "ecology_preset": slot0.config.ecology_preset,
        "climate_ablated": (not bool(slot0.config.planet.climate_enabled))
        if hasattr(slot0.config.planet, "climate_enabled")
        else None,
        "PSC_mode": cog.prospective_selection,
        "psc_motor_resolution": cog.psc_motor_resolution,
        "cognition_diffs_from_stock": diffs,
        "mechanisms_ON": mech_on,
        "mechanisms_OFF": mech_off,
        "vision": {
            "enabled": getattr(vis, "enabled", None),
            "surface_discrimination": getattr(vis, "surface_discrimination", None),
            "spatial_vision": getattr(vis, "spatial_vision", None),
            "surface_mode": getattr(vis, "surface_mode", None),
            "radius": getattr(vis, "radius", None),
            "n_azimuth": getattr(vis, "n_azimuth", None) or getattr(vis, "n_sectors", None),
            "contributes_to_cognition": getattr(vis, "contributes_to_cognition", None),
        },
        "legacy_signaling_active": sig_on,
        "osc_mechanism_enabled": osc_mech,
        "compose_available_actions": compose_actions,
        "physical_OSC_compose_candidates": len(osc_in_compose),
        "tps_store_compact": tps_size,
        "tpe_lag_keys": tpe_lags,
        "packed_l1_mode": psc_opt.packed_l1_mode(),
        "numpy_production": False,
        "observer": "NOT_PRESENT_IN_BENCHMARK",
        "pe_cold_archive_in_bench": False,
        "pack_rows_start": {"agent_0": rows0, "agent_1": rows1},
    }
    (OUT / "RUN_CONFIG.json").write_text(json.dumps(run_config, indent=2, default=str))

    tp.enable()
    tp.reset()
    walls = []
    for _ in range(BENCH_TICKS):
        tp.begin_tick()
        t0 = time.perf_counter()
        rt.step(1)
        walls.append((time.perf_counter() - t0) * 1000.0)
        tp.end_tick(int(rt.tick))
    snap = tp.snapshot_stats()
    tp.disable()
    psc_opt.ensure_pack = orig_ensure

    n = max(1, int(snap.get("ticks") or BENCH_TICKS))
    cog_ms = float(_bkt(snap, "cognition").get("mean_ms_per_tick") or 0)
    buckets = sorted(snap.get("buckets") or [], key=lambda b: -float(b.get("self_ms_per_tick") or 0))

    # cognition children (from code): listed spans inside run_cognition_before_action
    cog_children = [
        "per_realize", "tpe_ingest", "pc_observe", "ms_ingest", "learn_transition",
        "pe_learn", "tps_learn", "tps_append", "cog_predict_loop", "tpb_collect",
        "compose", "tpb_diagnostic", "pcp_collect", "map_collect", "conflict_organize",
        "fsa_groups", "scenario_groups", "compete_scenarios", "pc_purge", "cog_retain",
    ]
    # nested inside cog_predict_loop — do not add to residual subtraction twice
    nested_in_predict = ["pc_predict", "tps_retrieve", "prl_retrieve", "pe_retrieve", "pe_diagnostic", "tps_diagnostic"]

    def row(name):
        b = _bkt(snap, name)
        inc = float(b.get("mean_ms_per_tick") or 0)
        slf = float(b.get("self_ms_per_tick") or 0)
        calls = float(b.get("calls_per_tick") or 0)
        us = float(b.get("mean_us_per_call") or 0)
        return {
            "name": name,
            "calls_per_tick": calls,
            "ms_tick_inclusive": inc,
            "ms_tick_self": slf,
            "ms_call": us / 1000.0 if calls else 0.0,
            "percent_cognition_inclusive": (100.0 * inc / cog_ms) if cog_ms else 0.0,
            "percent_cognition_self": (100.0 * slf / cog_ms) if cog_ms else 0.0,
        }

    profile_rows = [row(b["name"]) for b in snap.get("buckets") or []]
    (OUT / "cognition_profile.csv").write_text(
        "name,calls_per_tick,ms_tick_inclusive,ms_tick_self,ms_call,percent_cognition_inclusive,percent_cognition_self\n"
        + "\n".join(
            f"{r['name']},{r['calls_per_tick']:.4f},{r['ms_tick_inclusive']:.4f},{r['ms_tick_self']:.4f},"
            f"{r['ms_call']:.6f},{r['percent_cognition_inclusive']:.2f},{r['percent_cognition_self']:.2f}"
            for r in sorted(profile_rows, key=lambda x: -x["ms_tick_inclusive"])
        )
        + "\n"
    )

    child_sum = sum(float(_bkt(snap, n).get("mean_ms_per_tick") or 0) for n in cog_children)
    residual = max(0.0, cog_ms - child_sum)
    residual_pct = 100.0 * residual / cog_ms if cog_ms else 0.0

    rebuild_ms = (sum(pack_stats["rebuild_ns"]) / 1e6) / BENCH_TICKS if pack_stats["rebuild_ns"] else 0.0
    rebuilds_tick = pack_stats["rebuilds"] / BENCH_TICKS

    compose = row("compose")
    tps_r = row("tps_retrieve")
    tps_l = row("tps_learn")
    tpe = row("tpe_ingest")
    pcp = row("pcp_collect")
    tpb = row("tpb_collect")
    fsa = row("fsa_groups")
    conf = row("conflict_organize")
    psc = row("compete_scenarios")

    tps_tpe = tps_r["ms_tick_inclusive"] + tps_l["ms_tick_inclusive"] + tpe["ms_tick_inclusive"] + row("tps_append")["ms_tick_inclusive"] + row("tps_diagnostic")["ms_tick_inclusive"]
    # tps_retrieve nested in cog_predict_loop — family sum of those three ingest/retrieve/learn is valid (non-overlapping with each other)
    tps_tpe_core = tps_r["ms_tick_inclusive"] + tps_l["ms_tick_inclusive"] + tpe["ms_tick_inclusive"]
    compose_family = compose["ms_tick_inclusive"]  # pack rebuild nested inside
    prospection_family = compose["ms_tick_inclusive"] + tpb["ms_tick_inclusive"] + pcp["ms_tick_inclusive"] + row("map_collect")["ms_tick_inclusive"]
    psc_family = psc["ms_tick_inclusive"] + row("scenario_groups")["ms_tick_inclusive"] + fsa["ms_tick_inclusive"]

    vis_ms = row("vis_sample")["ms_tick_inclusive"] + row("vis_spatial")["ms_tick_inclusive"] + row("vis_assemble")["ms_tick_inclusive"]

    grouped = [
        ("COMPOSE_FAMILY", compose_family, "compose inclusive (includes ensure_pack on miss)"),
        ("TPS_TPE_FAMILY", tps_tpe_core, "tps_retrieve + tps_learn + tpe_ingest (non-overlapping)"),
        ("TPS_TPE_PLUS_DIAG", tps_tpe, "core + tps_append + tps_diagnostic"),
        ("PROSPECTION_FAMILY", prospection_family, "compose + tpb_collect + pcp_collect + map_collect"),
        ("PSC_FAMILY", psc_family, "compete_scenarios + scenario_groups + fsa_groups"),
        ("VISION_PHYSICAL", vis_ms, "vis_sample + vis_spatial + vis_assemble"),
    ]
    (OUT / "cognition_grouped_costs.csv").write_text(
        "group,ms_tick,note\n" + "\n".join(f"{a},{b:.4f},{c}" for a, b, c in grouped) + "\n"
    )

    walls_s = sorted(walls)
    tick_lat = {
        "n": len(walls),
        "mean": sum(walls) / len(walls),
        "p50": _pctile(walls, 50),
        "p95": _pctile(walls, 95),
        "p99": _pctile(walls, 99),
        "max": max(walls),
        "profiler_tick_mean": snap.get("mean_ms_per_tick"),
        "profiler_p50": snap.get("p50_ms_per_tick"),
        "profiler_p95": snap.get("p95_ms_per_tick"),
        "profiler_max": snap.get("max_ms_per_tick"),
    }
    (OUT / "tick_latency.csv").write_text(
        "source,mean,p50,p95,p99,max\n"
        f"wall_step,{tick_lat['mean']:.4f},{tick_lat['p50']:.4f},{tick_lat['p95']:.4f},{tick_lat['p99']:.4f},{tick_lat['max']:.4f}\n"
        f"profiler_begin_end,{tick_lat['profiler_tick_mean']:.4f},{tick_lat['profiler_p50']:.4f},{tick_lat['profiler_p95']:.4f},,{tick_lat['profiler_max']:.4f}\n"
    )

    top = [
        ("observation", row("observation")["ms_tick_inclusive"]),
        ("cognition_motor", row("cognition_motor")["ms_tick_inclusive"]),
        ("cognition", cog_ms),
        ("world_physics", row("world_physics")["ms_tick_inclusive"]),
        ("body_finish", row("body_finish")["ms_tick_inclusive"]),
        ("contact_push", row("contact_push")["ms_tick_inclusive"]),
        ("vision_physical", vis_ms),
        ("begin_tick_agent_0", row("begin_tick_agent_0")["ms_tick_inclusive"]),
        ("begin_tick_agent_1", row("begin_tick_agent_1")["ms_tick_inclusive"]),
    ]
    wall_mean = tick_lat["mean"]
    accounted = row("observation")["ms_tick_inclusive"] + row("cognition_motor")["ms_tick_inclusive"] + row("world_physics")["ms_tick_inclusive"] + row("body_finish")["ms_tick_inclusive"] + row("contact_push")["ms_tick_inclusive"]
    (OUT / "subsystem_accounting.csv").write_text(
        "span,ms_tick_inclusive,ms_tick_self,calls_per_tick\n"
        + "\n".join(
            f"{r['name']},{r['ms_tick_inclusive']:.4f},{r['ms_tick_self']:.4f},{r['calls_per_tick']:.4f}"
            for r in profile_rows
        )
        + "\n"
    )

    # ranking: cognition leaves by inclusive, skip parents that nest others
    rank_names = [
        "compose", "tps_learn", "tps_retrieve", "tpe_ingest", "pcp_collect",
        "conflict_organize", "fsa_groups", "tpb_collect", "pe_learn",
        "learn_transition", "cog_predict_loop", "map_collect", "compete_scenarios",
        "scenario_groups", "pc_observe", "ms_ingest", "tps_diagnostic",
        "pe_diagnostic", "pc_predict", "cog_retain", "per_realize", "pc_purge",
        "tps_append",
    ]
    # For ranking use self for parents with children, inclusive for leaves
    rank = []
    for name in rank_names:
        r = row(name)
        if name == "cog_predict_loop":
            ms = r["ms_tick_self"]
        else:
            ms = r["ms_tick_inclusive"]
        if r["calls_per_tick"] <= 0 and ms <= 0:
            continue
        rank.append((name, ms, 100.0 * ms / cog_ms if cog_ms else 0.0, r))
    rank.sort(key=lambda x: -x[1])
    (OUT / "bottleneck_ranking.csv").write_text(
        "rank,subsystem,ms_tick,cognition_share_pct,calls_per_tick,ms_call,timer\n"
        + "\n".join(
            f"{i+1},{nm},{ms:.4f},{share:.2f},{r['calls_per_tick']:.4f},{r['ms_call']:.6f},"
            f"{'self' if nm=='cog_predict_loop' else 'inclusive'}"
            for i, (nm, ms, share, r) in enumerate(rank)
        )
        + f"\nresidual_cognition_self,{residual:.4f},{residual_pct:.2f},,,cognition_inclusive_minus_named_children\n"
    )

    tps_vs = "INSUFFICIENT_EVIDENCE"
    if tps_tpe_core > compose_family * 1.15:
        tps_vs = "YES"
    elif compose_family > tps_tpe_core * 1.15:
        tps_vs = "NO"
    else:
        tps_vs = "APPROXIMATELY_EQUAL"

    rows0e = _pack_rows(rt.slots[0])
    rows1e = _pack_rows(rt.slots[1])

    summary = {
        "profile_start_tick": int(payload.get("tick") or 0),
        "profile_end_tick": int(rt.tick),
        "intentional_ticks": BENCH_TICKS,
        "wall": tick_lat,
        "top": dict(top),
        "accounted_top_ms": accounted,
        "wall_accounted_percent": 100.0 * accounted / wall_mean if wall_mean else None,
        "cognition_ms": cog_ms,
        "cognition_self": float(_bkt(snap, "cognition").get("self_ms_per_tick") or 0),
        "child_sum_named": child_sum,
        "residual": residual,
        "residual_pct": residual_pct,
        "compose": compose,
        "pack_rebuild_ms_tick": rebuild_ms,
        "pack_rebuilds_tick": rebuilds_tick,
        "pack_ensure_calls_tick": pack_stats["calls"] / BENCH_TICKS,
        "tps_retrieve": tps_r,
        "tps_learn": tps_l,
        "tpe_ingest": tpe,
        "pcp": pcp,
        "tpb": tpb,
        "fsa": fsa,
        "conflict": conf,
        "psc": psc,
        "grouped": {a: b for a, b, _ in grouped},
        "tps_tpe_vs_compose": tps_vs,
        "agent_begin": {
            "agent_0": row("begin_tick_agent_0"),
            "agent_1": row("begin_tick_agent_1"),
        },
        "pack_rows_end": {"agent_0": rows0e, "agent_1": rows1e},
        "COGNITION_ACCOUNTING_INCOMPLETE": residual_pct > 15.0,
        "slow_ticks": snap.get("slow_ticks") or [],
        "counters": snap.get("counters") or {},
    }
    (OUT / "_profile_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({
        "classification": classification,
        "fingerprint": fingerprint,
        "wall_mean": tick_lat["mean"],
        "cognition": cog_ms,
        "residual_pct": residual_pct,
        "compose": compose["ms_tick_inclusive"],
        "tps_tpe_core": tps_tpe_core,
        "tps_vs": tps_vs,
        "pack_rebuild_ms": rebuild_ms,
        "rebuilds": rebuilds_tick,
        "rank_top5": [(a, round(b, 3), round(c, 1)) for a, b, c, _ in rank[:5]],
        "vis_ms": vis_ms,
        "agent0_ms": row("begin_tick_agent_0")["ms_tick_inclusive"],
        "agent1_ms": row("begin_tick_agent_1")["ms_tick_inclusive"],
    }, indent=2))


if __name__ == "__main__":
    main()
