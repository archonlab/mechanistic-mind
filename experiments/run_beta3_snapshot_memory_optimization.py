#!/usr/bin/env python3
"""NEW persist-view + compact JSON aged-save matrix. Does not overwrite prior results."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

import run_beta3_aged_save_memory as aged  # noqa: E402

OUT = ROOT / "results" / "beta3_snapshot_memory_optimization"
FORENSIC = aged.FORENSIC_LIVE


def json_format_bench(label: str, spec: dict) -> dict:
    """Same persist view: compact vs pretty. Isolated from write_finalized_run extras."""
    import gc
    from mechanistic_mind.physical_system import TwoAgentRuntime
    from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist

    dest = OUT / "json_format" / label.lower()
    dest.mkdir(parents=True, exist_ok=True)
    rt = TwoAgentRuntime(seed=int(spec.get("seed", 33)), config=aged._beta3_cfg())
    for _ in range(int(spec.get("steps", 16))):
        rt.step()
    aged._fill_cognition(rt, extra_forgotten=int(spec["extra_forgotten"]))
    gc.collect()
    rss0, vm0 = aged._rss_vm_kb()
    t0 = time.perf_counter()
    view = rt.snapshot(persist=True)
    t_cap = time.perf_counter() - t0
    rss1, vm1 = aged._rss_vm_kb()

    compact_path = dest / "compact.json"
    pretty_path = dest / "pretty.json"
    t1 = time.perf_counter()
    with compact_path.open("w", encoding="utf-8") as fh:
        dump_persist(view, fh, compact=True)
        fh.flush()
        os.fsync(fh.fileno())
    t_compact = time.perf_counter() - t1
    rss_c, vm_c = aged._rss_vm_kb()

    t2 = time.perf_counter()
    with pretty_path.open("w", encoding="utf-8") as fh:
        dump_persist(view, fh, compact=False)
        fh.flush()
        os.fsync(fh.fileno())
    t_pretty = time.perf_counter() - t2
    rss_p, vm_p = aged._rss_vm_kb()

    import json as _json
    a = _json.loads(compact_path.read_text(encoding="utf-8"))
    b = _json.loads(pretty_path.read_text(encoding="utf-8"))
    assert a == b
    return {
        "label": label,
        "rss_before_mb": aged._kb_mb(rss0),
        "rss_after_persist_view_mb": aged._kb_mb(rss1),
        "rss_after_compact_mb": aged._kb_mb(rss_c),
        "rss_after_pretty_mb": aged._kb_mb(rss_p),
        "vm_before_mb": aged._kb_mb(vm0),
        "vm_after_view_mb": aged._kb_mb(vm1),
        "capture_s": round(t_cap, 4),
        "compact_s": round(t_compact, 3),
        "pretty_s": round(t_pretty, 3),
        "compact_bytes": compact_path.stat().st_size,
        "pretty_bytes": pretty_path.stat().st_size,
        "json_load_equal": True,
        "view_aliases_cognition": view["agents"][0]["cognition"] is rt.slots[0].cognition,
    }


def deepcopy_capture_cost(spec: dict) -> dict:
    import gc
    from mechanistic_mind.physical_system import TwoAgentRuntime

    rt = TwoAgentRuntime(seed=int(spec.get("seed", 33)), config=aged._beta3_cfg())
    for _ in range(int(spec.get("steps", 16))):
        rt.step()
    aged._fill_cognition(rt, extra_forgotten=int(spec["extra_forgotten"]))
    gc.collect()
    a, _ = aged._rss_vm_kb()
    t0 = time.perf_counter()
    detached = rt.snapshot(persist=False)
    t_det = time.perf_counter() - t0
    b, _ = aged._rss_vm_kb()
    t1 = time.perf_counter()
    view = rt.snapshot(persist=True)
    t_per = time.perf_counter() - t1
    c, _ = aged._rss_vm_kb()
    return {
        "rss_baseline_mb": aged._kb_mb(a),
        "rss_after_deepcopy_snapshot_mb": aged._kb_mb(b),
        "rss_after_persist_view_mb": aged._kb_mb(c),
        "deepcopy_capture_s": round(t_det, 4),
        "persist_capture_s": round(t_per, 6),
        "deepcopy_delta_mb": round(aged._kb_mb(b) - aged._kb_mb(a), 2),
        "persist_delta_mb": round(aged._kb_mb(c) - aged._kb_mb(b), 2),
        "detached_is_copy": detached["agents"][0]["cognition"] is not rt.slots[0].cognition,
        "persist_is_alias": view["agents"][0]["cognition"] is rt.slots[0].cognition,
    }


def main() -> None:
    assert FORENSIC.is_dir()
    OUT.mkdir(parents=True, exist_ok=True)
    aged.OUT = OUT
    scan = {
        **aged._scan_save_path(),
        "dump_persist_defined": "def dump_persist" in (
            ROOT / "mechanistic_mind/ui/psy_observer_web/run_finalize.py"
        ).read_text(encoding="utf-8"),
        "snapshot_persist_kw": "persist: bool = False" in (
            ROOT / "mechanistic_mind/physical_system/runtime.py"
        ).read_text(encoding="utf-8"),
    }
    sizes = {
        "SMALL": {"extra_forgotten": 0, "jsonl_lines": 40, "steps": 6, "seed": 11},
        "MEDIUM": {"extra_forgotten": 400, "jsonl_lines": 4000, "steps": 12, "seed": 22, "jsonl_pad": 200},
        "AGED": {"extra_forgotten": 6000, "jsonl_lines": 25000, "steps": 16, "seed": 33, "jsonl_pad": 220},
        "EXTREME": {"extra_forgotten": 14000, "jsonl_lines": 40000, "steps": 16, "seed": 44, "jsonl_pad": 240},
    }
    mem = Path("/proc/meminfo").read_text(encoding="utf-8")
    avail_kb = 0
    for line in mem.splitlines():
        if line.startswith("MemAvailable:"):
            avail_kb = int(line.split()[1])
    if avail_kb < 8 * 1024 * 1024:
        sizes.pop("EXTREME", None)

    table = {}
    for label, spec in sizes.items():
        table[label] = aged.parent_run_label(label, spec)

    fmt = {
        "MEDIUM": json_format_bench("MEDIUM", sizes["MEDIUM"]),
        "AGED": json_format_bench("AGED", sizes["AGED"]),
    }
    dc = deepcopy_capture_cost(sizes["AGED"])
    async_r = aged.run_async_api(OUT / "async_api")
    fail_r = aged.run_failure(OUT / "failure")
    repeat_r = aged.run_repeat(sizes["MEDIUM"], OUT / "repeat")

    old_path = ROOT / "results/beta3_aged_save_memory/summary.json"
    old = json.loads(old_path.read_text(encoding="utf-8")) if old_path.is_file() else {}
    old_sizes = old.get("sizes") or {}
    comparison = {}
    for label, neu in table.items():
        prev = old_sizes.get(label) or {}
        old_d = prev.get("delta_rss_mb")
        new_d = neu.get("delta_rss_mb")
        old_t = prev.get("save_s")
        new_t = neu.get("save_s")
        old_sz = prev.get("snapshot_file_mb")
        new_sz = neu.get("snapshot_file_mb")
        comparison[label] = {
            "old_delta_rss_mb": old_d,
            "new_delta_rss_mb": new_d,
            "memory_reduction_mb": None if old_d is None or new_d is None else round(old_d - new_d, 2),
            "old_save_s": old_t,
            "new_save_s": new_t,
            "time_speedup": None if not old_t or not new_t else round(old_t / new_t, 3),
            "old_snapshot_mb": old_sz,
            "new_snapshot_mb": new_sz,
            "old_peak_rss_mb": prev.get("peak_rss_mb"),
            "new_peak_rss_mb": neu.get("peak_rss_mb"),
            "old_peak_over_baseline": prev.get("peak_over_baseline"),
            "new_peak_over_baseline": neu.get("peak_over_baseline"),
            "new_persist_timings": neu.get("persist_timings"),
            "new_restore_ok": neu.get("restore_ok"),
        }

    summary = {
        "forensic_live_untouched": FORENSIC.is_dir(),
        "scan": scan,
        "sizes": table,
        "comparison_vs_prior_aged_matrix": comparison,
        "json_format": fmt,
        "deepcopy_capture_cost_aged": dc,
        "async_api": async_r,
        "controlled_failure": fail_r,
        "repeat_save": repeat_r,
        "memavailable_mb": aged._kb_mb(avail_kb),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(comparison, indent=2))
    print("json_format", fmt)
    print("deepcopy_cost", dc)
    print("async", async_r)
    print("failure", fail_r)
    print("repeat", repeat_r)


if __name__ == "__main__":
    main()
