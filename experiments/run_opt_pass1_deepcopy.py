#!/usr/bin/env python3
"""OPT PASS 1: deepcopy/causal-trim/receipt — equivalence + before/after benches.

Compares HEAD (pre-opt) vs working-tree (post-opt) scientific fingerprints and
Web UI / headless timings. Does not retune mechanisms.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import resource
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = Path("results/performance/optimization_pass_1")
RAW = OUT / "raw"
BENCH = OUT / "benchmarks"
for d in (OUT, RAW, BENCH):
    d.mkdir(parents=True, exist_ok=True)

SEED = 17
ECOLOGY = "STRUCTURED_TERRAIN_EXPERIMENTAL"
WARMUP = 150
PROFILE = 400
FINGERPRINT_TICKS = 300

MECHS = {
    "cognition_enabled": True,
    "experimental_physical_signal": True,
    "physical_near_field_vision": True,
    "illumination_cycle": True,
    "physical_body_optical_response": True,
}

FILES = [
    "mechanistic_mind/integrated/causal_trace.py",
    "mechanistic_mind/physical_system/diagnostics.py",
    "mechanistic_mind/physical_system/scenario_competition.py",
]


def rss_mb() -> float:
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))


def _hash(obj) -> str:
    return hashlib.sha256(_canon(obj).encode()).hexdigest()[:16]


def scientific_fingerprint(rt) -> dict:
    """Compact scientific fingerprint for one TwoAgentRuntime tick state."""
    slots = getattr(rt, "slots", [rt])
    agents = []
    for i, slot in enumerate(slots):
        body = slot.body
        cog = slot.cognition if isinstance(getattr(slot, "cognition", None), dict) else {}
        sel = cog.get("last_selection") or {}
        receipt = cog.get("last_decision_receipt") or {}
        obs = slot.last_agent_observation or {}
        exo = {k: obs.get(k) for k in ("exo_0", "exo_1", "exo_2") if k in obs}
        field = {k: obs.get(k) for k in obs if "FIELD" in str(k)}
        trace = cog.get("trace") or {}
        events = trace.get("events") or []
        edges = trace.get("edges") or []
        ras = getattr(body, "R_A_site", None)
        rbs = getattr(body, "R_B_site", None)
        try:
            ra = float(ras.sum()) if ras is not None else None
            rb = float(rbs.sum()) if rbs is not None else None
        except Exception:
            ra = rb = None
        agents.append({
            "slot": i,
            "action": slot.last_selected_action,
            "source": sel.get("source") or receipt.get("selection_source"),
            "x": float(body.x), "y": float(body.y),
            "vx": float(body.vx), "vy": float(body.vy),
            "theta": float(getattr(body, "theta", 0.0) or 0.0),
            "work": float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0),
            "R_A": ra, "R_B": rb,
            "obs_hash": _hash(obs),
            "exo": exo,
            "field": field,
            "competition_reason": (sel.get("competition") or {}).get("selection_reason")
                or (sel.get("competition") or {}).get("outcome_class"),
            "prospective_n": (cog.get("metrics") or {}).get("prospective_compositions"),
            "receipt_hash": _hash({
                "selected": receipt.get("selected_action"),
                "source": receipt.get("selection_source"),
                "mode": receipt.get("prospective_selection_mode"),
                "supported": receipt.get("supported_physical_actions"),
                "top_first": (receipt.get("prospective_continuations") or {}).get("top_first_actions"),
                "outcome": (receipt.get("competition") or {}).get("outcome_class"),
            }) if receipt else None,
            "trace_n_events": len(events),
            "trace_n_edges": len(edges),
            "trace_tail_hash": _hash(events[-8:]) if events else None,
            "edge_tail_hash": _hash(edges[-16:]) if edges else None,
            "parent_pairs": [
                (e.get("source"), e.get("target"), e.get("relation"))
                for e in edges[-16:]
            ],
        })
    contact = getattr(rt, "last_contact", None) or {}
    sig = getattr(rt, "last_signal_receipt", None) or {}
    return {
        "tick": int(rt.tick),
        "agents": agents,
        "contact": bool(contact.get("contact")),
        "contact_pair": contact.get("pair"),
        "signal_emitted": bool(sig.get("emitted")),
        "signal_sources_n": len(sig.get("sources") or []),
    }


def make_runtime():
    from mechanistic_mind.physical_system.ecology_presets import make_ecology_config
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    cfg = make_ecology_config(ECOLOGY)
    cfg.cognition.cognition_enabled = True
    rt = TwoAgentRuntime(seed=SEED, config=cfg, signal_enabled=True)
    for mid in (
        "physical_near_field_vision",
        "illumination_cycle",
        "physical_body_optical_response",
        "experimental_physical_signal",
    ):
        try:
            rt.set_mechanism(mid, True)
        except Exception:
            pass
    return rt


def run_fingerprints(n_ticks: int) -> list[dict]:
    rt = make_runtime()
    out = []
    for _ in range(n_ticks):
        rt.step(1)
        out.append(scientific_fingerprint(rt))
    return out


def make_session():
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    sess = ObserverSession(config=SessionConfig(seed=SEED, ui_hz=10.0, buffer_capacity=256))
    sess.apply_experiment({
        "seed": SEED,
        "ecology_preset": ECOLOGY,
        "agent_count": 2,
        "cognition_enabled": True,
        "mechanisms": dict(MECHS),
    })
    for mid, val in MECHS.items():
        if mid == "cognition_enabled":
            continue
        try:
            sess.set_mechanism(str(mid), bool(val))
        except Exception:
            pass
    return sess


def scientific_only(sess, n: int) -> list[float]:
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
                sess._append_scientific_locked()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


def bench_webui(label: str) -> dict:
    sess = make_session()
    scientific_only(sess, WARMUP)
    samples = scientific_only(sess, PROFILE)
    mean = sum(samples) / len(samples)
    srt = sorted(samples)
    return {
        "label": label,
        "ticks": PROFILE,
        "mean_ms": mean,
        "p50_ms": srt[len(srt) // 2],
        "p95_ms": srt[int(0.95 * (len(srt) - 1))],
        "tps": 1000.0 / mean,
        "rss_mb": rss_mb(),
    }


def bench_headless(label: str) -> dict:
    rt = make_runtime()
    for _ in range(min(50, WARMUP)):
        rt.step(1)
    samples = []
    for _ in range(PROFILE):
        t0 = time.perf_counter()
        rt.step(1)
        samples.append((time.perf_counter() - t0) * 1000.0)
    mean = sum(samples) / len(samples)
    srt = sorted(samples)
    return {
        "label": label,
        "ticks": PROFILE,
        "mean_ms": mean,
        "p50_ms": srt[len(srt) // 2],
        "p95_ms": srt[int(0.95 * (len(srt) - 1))],
        "tps": 1000.0 / mean,
        "rss_mb": rss_mb(),
    }


def swap_in_before_versions():
    """Install HEAD versions of optimized files; return restore callable."""
    backups = {}
    for rel in FILES:
        path = ROOT / rel
        backups[rel] = path.read_text(encoding="utf-8")
        before = (ROOT / ".git" and None)
        import subprocess
        content = subprocess.check_output(
            ["git", "show", f"HEAD:{rel}"], cwd=str(ROOT)
        ).decode("utf-8")
        path.write_text(content, encoding="utf-8")

    # copy_opt may not exist in HEAD — leave it (unused by HEAD causal_trace)
    def restore():
        for rel, text in backups.items():
            (ROOT / rel).write_text(text, encoding="utf-8")

    # Force reload of key modules
    for name in list(sys.modules):
        if name.startswith("mechanistic_mind.integrated.causal_trace") or \
           name.startswith("mechanistic_mind.physical_system.diagnostics") or \
           name.startswith("mechanistic_mind.physical_system.scenario_competition") or \
           name.startswith("mechanistic_mind.physical_system.cognition") or \
           name.startswith("mechanistic_mind.physical_system.runtime") or \
           name.startswith("mechanistic_mind.physical_system.two_agent") or \
           name.startswith("mechanistic_mind.ui.psy_observer_web"):
            del sys.modules[name]
    return restore


def compare_fps(before: list[dict], after: list[dict]) -> dict:
    assert len(before) == len(after)
    mismatches = []
    for b, a in zip(before, after):
        if b["tick"] != a["tick"]:
            mismatches.append({"tick": b["tick"], "field": "tick", "before": b["tick"], "after": a["tick"]})
            continue
        for i, (ba, aa) in enumerate(zip(b["agents"], a["agents"])):
            for key in (
                "action", "source", "x", "y", "vx", "vy", "theta", "work", "R_A", "R_B",
                "obs_hash", "exo", "field", "competition_reason", "receipt_hash",
                "trace_n_events", "trace_n_edges", "trace_tail_hash", "edge_tail_hash",
                "parent_pairs",
            ):
                if ba.get(key) != aa.get(key):
                    mismatches.append({
                        "tick": b["tick"], "agent": i, "field": key,
                        "before": ba.get(key), "after": aa.get(key),
                    })
                    if len(mismatches) > 40:
                        return {"match": False, "n_mismatch": len(mismatches), "samples": mismatches}
        for key in ("contact", "contact_pair", "signal_emitted", "signal_sources_n"):
            if b.get(key) != a.get(key):
                mismatches.append({"tick": b["tick"], "field": key, "before": b.get(key), "after": a.get(key)})
    return {
        "match": len(mismatches) == 0,
        "n_ticks": len(before),
        "n_mismatch": len(mismatches),
        "samples": mismatches[:20],
        "verdict": "EXACT_MATCH" if not mismatches else "DIVERGENCE",
    }


def main():
    # --- AFTER fingerprints & benches first (current tree) ---
    print("=== AFTER (optimized working tree) ===")
    fp_after = run_fingerprints(FINGERPRINT_TICKS)
    (RAW / "equivalence_fingerprints_after.json").write_text(
        json.dumps({"n": len(fp_after), "tail": fp_after[-3:]}, indent=2), encoding="utf-8"
    )
    # Store compact action streams for quick diff
    actions_after = [
        {"tick": f["tick"], "a0": f["agents"][0]["action"], "a1": f["agents"][1]["action"],
         "s0": f["agents"][0]["source"], "s1": f["agents"][1]["source"]}
        for f in fp_after
    ]
    (RAW / "actions_after.json").write_text(json.dumps(actions_after), encoding="utf-8")

    webui_after = bench_webui("WEBUI_AFTER")
    headless_after = bench_headless("HEADLESS_AFTER")
    (BENCH / "webui_after.json").write_text(json.dumps(webui_after, indent=2), encoding="utf-8")
    (BENCH / "headless_after.json").write_text(json.dumps(headless_after, indent=2), encoding="utf-8")
    print("webui_after", webui_after)
    print("headless_after", headless_after)

    # Full after fingerprints saved compressed as hashes only for size
    (RAW / "fp_after_hashes.json").write_text(
        json.dumps([_hash(f) for f in fp_after]), encoding="utf-8"
    )

    # --- BEFORE: swap HEAD files ---
    print("=== BEFORE (git HEAD versions) ===")
    restore = swap_in_before_versions()
    try:
        fp_before = run_fingerprints(FINGERPRINT_TICKS)
        (RAW / "fp_before_hashes.json").write_text(
            json.dumps([_hash(f) for f in fp_before]), encoding="utf-8"
        )
        actions_before = [
            {"tick": f["tick"], "a0": f["agents"][0]["action"], "a1": f["agents"][1]["action"],
             "s0": f["agents"][0]["source"], "s1": f["agents"][1]["source"]}
            for f in fp_before
        ]
        (RAW / "actions_before.json").write_text(json.dumps(actions_before), encoding="utf-8")
        eq = compare_fps(fp_before, fp_after)
        (RAW / "equivalence_result.json").write_text(json.dumps(eq, indent=2, default=str), encoding="utf-8")
        print("equivalence", eq["verdict"], "mismatches", eq["n_mismatch"])

        webui_before = bench_webui("WEBUI_BEFORE")
        headless_before = bench_headless("HEADLESS_BEFORE")
        (BENCH / "webui_before.json").write_text(json.dumps(webui_before, indent=2), encoding="utf-8")
        (BENCH / "headless_before.json").write_text(json.dumps(headless_before, indent=2), encoding="utf-8")
        print("webui_before", webui_before)
        print("headless_before", headless_before)
    finally:
        restore()
        # reload after modules
        for name in list(sys.modules):
            if name.startswith("mechanistic_mind"):
                del sys.modules[name]

    summary = {
        "equivalence": eq,
        "webui_before": webui_before,
        "webui_after": webui_after,
        "headless_before": headless_before,
        "headless_after": headless_after,
        "ms_saved": webui_before["mean_ms"] - webui_after["mean_ms"],
        "pct_speedup": 100.0 * (webui_before["mean_ms"] - webui_after["mean_ms"]) / webui_before["mean_ms"],
        "tps_delta": webui_after["tps"] - webui_before["tps"],
    }
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
