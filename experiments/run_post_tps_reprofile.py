#!/usr/bin/env python3
"""Post TPS prepared-query whole-cognition reprofile. Measurement only."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CKPT = (
    ROOT
    / "results/psychology_observer/psy_observer_web"
    / "psyweb-20260925T071301.453542Z-749aeea4"
    / "physical_system_snapshot.json"
)
OUT = ROOT / "results/beta31_post_tps_reprofile"
BENCH_TICKS = 120

# Pre-TPS whole-cognition profile (same snapshot, 120 ticks, packed-L1 present).
PRE = {
    "cognition": 114.34286508333334,
    "compose": 20.46042471666667,
    "tps_retrieve": 10.133806658333333,
    "tps_learn": 8.26334535,
    "tpe_ingest": 8.683232141666668,
    "pcp": 5.247482033333333,
    "tpb": 2.841955558333333,
    "conflict": 5.2964785,
    "residual": 39.52736864166667,
    "tps_diagnostic": 2.1862,
    "fsa": 2.8254,
    "map_collect": 1.1168,
}


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


def _pq_stats(rt):
    builds = hits = misses = 0
    n_cached = 0
    for s in rt.slots:
        t = s.cognition.get("temporal") or {}
        builds += int(t.get("_prepared_query_builds") or 0)
        hits += int(t.get("_prepared_query_hits") or 0)
        misses += int(t.get("_prepared_query_misses") or 0)
        if t.get("_prepared_query"):
            n_cached += 1
    return {
        "builds": builds,
        "hits": hits,
        "misses": misses,
        "stores_with_prepared": n_cached,
    }


def main() -> None:
    from mechanistic_mind.model.tiktaalik import tiktaalik_cognition_config
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.research import pe_cold_archive as cold
    from mechanistic_mind.research import psc_opt
    from mechanistic_mind.research import tick_profiler as tp
    from mechanistic_mind.research import temporal_predictive_structure as tps
    from mechanistic_mind.physical_system.actions import available_actions, OSC_ACTIONS

    OUT.mkdir(parents=True, exist_ok=True)

    assert psc_opt.packed_l1_mode() == "auto"
    src = Path(psc_opt.__file__).read_text()
    assert "def soft_match_packed_matrix" in src
    assert "hit = soft_match_packed_matrix" in src
    assert tps.prepared_query_enabled() is True
    tps_src = Path(tps.__file__).read_text()
    assert "def get_prepared_query" in tps_src
    assert "_USE_PREPARED_QUERY" in tps_src

    cold.set_cold_archive(False)
    cold.set_cold_eviction(False)

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
    assert fingerprint == "b8584ee48f712d91", fingerprint

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
        "ecology_preset": slot0.config.ecology_preset,
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
        },
        "legacy_signaling_active": sig_on,
        "osc_mechanism_enabled": osc_mech,
        "compose_available_actions": compose_actions,
        "physical_OSC_compose_candidates": len(osc_in_compose),
        "packed_l1_mode": psc_opt.packed_l1_mode(),
        "tps_prepared_query_enabled": tps.prepared_query_enabled(),
        "observer": "NOT_PRESENT_IN_BENCHMARK",
        "science": "NOT_PRESENT_IN_BENCHMARK",
        "pe_cold_archive_in_bench": False,
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
    pq = _pq_stats(rt)
    n = max(1, BENCH_TICKS)
    pq_tick = {k: pq[k] / n for k in ("builds", "hits", "misses")}

    cog_ms = float(_bkt(snap, "cognition").get("mean_ms_per_tick") or 0)

    cog_children = [
        "per_realize", "tpe_ingest", "pc_observe", "ms_ingest", "learn_transition",
        "pe_learn", "tps_learn", "tps_append", "cog_predict_loop", "tpb_collect",
        "compose", "tpb_diagnostic", "pcp_collect", "map_collect", "conflict_organize",
        "fsa_groups", "scenario_groups", "compete_scenarios", "pc_purge", "cog_retain",
    ]

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

    child_sum = sum(float(_bkt(snap, name).get("mean_ms_per_tick") or 0) for name in cog_children)
    residual = max(0.0, cog_ms - child_sum)
    residual_pct = 100.0 * residual / cog_ms if cog_ms else 0.0
    prev_res = PRE["residual"]
    drop = prev_res - residual
    if drop >= 10.0:
        res_class = "LARGE_DROP"
    elif drop >= 3.0:
        res_class = "MODERATE_DROP"
    elif drop <= -3.0:
        res_class = "INCREASED"
    else:
        res_class = "APPROXIMATELY_STABLE"

    compose = row("compose")
    tps_r = row("tps_retrieve")
    tps_l = row("tps_learn")
    tpe = row("tpe_ingest")
    pcp = row("pcp_collect")
    tpb = row("tpb_collect")
    fsa = row("fsa_groups")
    conf = row("conflict_organize")
    psc = row("compete_scenarios")
    tps_d = row("tps_diagnostic")
    tpb_d = row("tpb_diagnostic")

    vis_ms = row("vis_sample")["ms_tick_inclusive"] + row("vis_spatial")["ms_tick_inclusive"] + row("vis_assemble")["ms_tick_inclusive"]
    tps_learn_tpe = tps_l["ms_tick_inclusive"] + tpe["ms_tick_inclusive"]
    pcp_tpb = pcp["ms_tick_inclusive"] + tpb["ms_tick_inclusive"]

    rank_names = [
        "compose", "tps_learn", "tps_retrieve", "tpe_ingest", "pcp_collect",
        "conflict_organize", "fsa_groups", "tpb_collect", "pe_learn",
        "learn_transition", "cog_predict_loop", "map_collect", "compete_scenarios",
        "scenario_groups", "pc_observe", "ms_ingest", "tps_diagnostic",
        "pe_diagnostic", "pc_predict", "cog_retain", "per_realize", "pc_purge",
        "tps_append", "tpb_diagnostic",
    ]
    rank = []
    for name in rank_names:
        r = row(name)
        ms = r["ms_tick_self"] if name == "cog_predict_loop" else r["ms_tick_inclusive"]
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

    tick_lat = {
        "n": len(walls),
        "mean": sum(walls) / len(walls),
        "p50": _pctile(walls, 50),
        "p95": _pctile(walls, 95),
        "p99": _pctile(walls, 99),
        "max": max(walls),
    }
    wall_mean = tick_lat["mean"]
    accounted = (
        row("observation")["ms_tick_inclusive"]
        + row("cognition_motor")["ms_tick_inclusive"]
        + row("world_physics")["ms_tick_inclusive"]
        + row("body_finish")["ms_tick_inclusive"]
        + row("contact_push")["ms_tick_inclusive"]
    )

    def delta(key, cur):
        old = PRE[key]
        return {"pre": old, "post": cur, "delta": cur - old}

    cmp_rows = [
        ("cognition", PRE["cognition"], cog_ms),
        ("compose", PRE["compose"], compose["ms_tick_inclusive"]),
        ("TPS_retrieve", PRE["tps_retrieve"], tps_r["ms_tick_inclusive"]),
        ("TPS_learn", PRE["tps_learn"], tps_l["ms_tick_inclusive"]),
        ("TPE_ingest", PRE["tpe_ingest"], tpe["ms_tick_inclusive"]),
        ("PCP", PRE["pcp"], pcp["ms_tick_inclusive"]),
        ("TPB", PRE["tpb"], tpb["ms_tick_inclusive"]),
        ("conflict", PRE["conflict"], conf["ms_tick_inclusive"]),
        ("residual", PRE["residual"], residual),
        ("tps_diagnostic", PRE["tps_diagnostic"], tps_d["ms_tick_inclusive"]),
    ]
    (OUT / "cognition_before_after.csv").write_text(
        "span,pre_tps_ms_tick,post_tps_ms_tick,delta_ms,note\n"
        + "\n".join(
            f"{n},{a:.4f},{b:.4f},{b-a:.4f},same_snapshot_120_ticks"
            for n, a, b in cmp_rows
        )
        + "\n"
    )

    tps_span_saving = PRE["tps_retrieve"] - tps_r["ms_tick_inclusive"]
    cog_saving = PRE["cognition"] - cog_ms
    additional = cog_saving - tps_span_saving
    named_extra = {
        "pcp": PRE["pcp"] - pcp["ms_tick_inclusive"],
        "tpb": PRE["tpb"] - tpb["ms_tick_inclusive"],
        "tps_diagnostic": PRE["tps_diagnostic"] - tps_d["ms_tick_inclusive"],
        "tpb_diagnostic": 0.0 - tpb_d["ms_tick_inclusive"],
        "residual": PRE["residual"] - residual,
        "tps_learn": PRE["tps_learn"] - tps_l["ms_tick_inclusive"],
        "tpe": PRE["tpe_ingest"] - tpe["ms_tick_inclusive"],
        "compose": PRE["compose"] - compose["ms_tick_inclusive"],
        "conflict": PRE["conflict"] - conf["ms_tick_inclusive"],
    }
    extra_accounted = named_extra["pcp"] + named_extra["tpb"] + named_extra["tps_diagnostic"]
    summary = {
        "classification": classification,
        "fingerprint": fingerprint,
        "profile_start_tick": int(payload.get("tick") or 0),
        "profile_end_tick": int(rt.tick),
        "intentional_ticks": BENCH_TICKS,
        "wall": tick_lat,
        "cognition_ms": cog_ms,
        "residual": residual,
        "residual_pct": residual_pct,
        "residual_class": res_class,
        "compose": compose,
        "tps_retrieve": tps_r,
        "tps_learn": tps_l,
        "tpe_ingest": tpe,
        "pcp": pcp,
        "tpb": tpb,
        "fsa": fsa,
        "conflict": conf,
        "psc": psc,
        "tps_diagnostic": tps_d,
        "pq_per_tick": pq_tick,
        "pq_raw": pq,
        "accounted_percent": 100.0 * accounted / wall_mean if wall_mean else None,
        "vis_ms": vis_ms,
        "observation": row("observation")["ms_tick_inclusive"],
        "world_physics": row("world_physics")["ms_tick_inclusive"],
        "cognition_motor": row("cognition_motor")["ms_tick_inclusive"],
        "body_finish": row("body_finish")["ms_tick_inclusive"],
        "contact_push": row("contact_push")["ms_tick_inclusive"],
        "accounted_top_ms": accounted,
        "tps_learn_plus_tpe": tps_learn_tpe,
        "pcp_plus_tpb": pcp_tpb,
        "rank_top5": [(a, b, c) for a, b, c, _ in rank[:8]],
        "extra_saving": {
            "tps_span_saving_vs_pre_profile": tps_span_saving,
            "cognition_saving_vs_pre_profile": cog_saving,
            "additional": additional,
            "named_deltas": named_extra,
            "pcp_tpb_diag_sum": extra_accounted,
        },
        "slow_ticks": snap.get("slow_ticks") or [],
        "observer": "NOT_PRESENT_IN_BENCHMARK",
    }
    (OUT / "_profile_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({
        "fingerprint": fingerprint,
        "wall_mean": tick_lat["mean"],
        "cognition": cog_ms,
        "residual": residual,
        "residual_pct": residual_pct,
        "residual_class": res_class,
        "compose": compose["ms_tick_inclusive"],
        "tps_retrieve": tps_r["ms_tick_inclusive"],
        "tps_learn": tps_l["ms_tick_inclusive"],
        "tpe": tpe["ms_tick_inclusive"],
        "pcp": pcp["ms_tick_inclusive"],
        "tpb": tpb["ms_tick_inclusive"],
        "conflict": conf["ms_tick_inclusive"],
        "pq_tick": pq_tick,
        "rank_top5": [(a, round(b, 3), round(c, 1)) for a, b, c, _ in rank[:5]],
        "extra": summary["extra_saving"],
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
