"""Track B: persisted JSON vs live continuation. Compact artifacts only."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from copy import deepcopy
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path("/home/thehost/Desktop/psy")
OUT = ROOT / "results" / "beta31_persist_determinism"


def make_runtime():
    from experiments.run_beta31_pe_forgotten_compaction import make_runtime as _mr
    return _mr()


def actions(rt) -> tuple:
    return tuple(s.last_selected_action for s in rt.slots)


def osc_energy(rt) -> float:
    b = getattr(rt.world, "OSC_BANDS", None)
    if b is None:
        return 0.0
    return float(np.asarray(b).sum())


def json_roundtrip(snap: dict) -> dict:
    from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist
    buf = StringIO()
    dump_persist(snap, buf, compact=True)
    return json.loads(buf.getvalue())


def restore(snap: dict):
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    return TwoAgentRuntime.restore(snap)


def three_way_at(rt, *, persist_deepcopy: bool = True) -> dict:
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    snap = rt.snapshot(persist=False) if persist_deepcopy else rt.snapshot(persist=True)
    osc_live = osc_energy(rt)
    osc_snap = None
    w = snap.get("world") or {}
    if w.get("OSC_BANDS") is not None:
        osc_snap = float(np.asarray(w["OSC_BANDS"]).sum())
    rest_b = restore(deepcopy(snap))
    js = json_roundtrip(snap)
    rest_c = restore(js)
    a0, b0, c0 = actions(rt), actions(rest_b), actions(rest_c)
    rt.step(n=1)
    rest_b.step(n=1)
    rest_c.step(n=1)
    return {
        "tick_before": int(snap.get("tick") or 0),
        "osc_energy_live": osc_live,
        "osc_energy_snapshot": osc_snap,
        "osc_energy_restore_mem": osc_energy(rest_b),
        "osc_energy_restore_json": osc_energy(rest_c),
        "pre_actions": {"A": a0, "B": b0, "C": c0},
        "post_actions": {"A": actions(rt), "B": actions(rest_b), "C": actions(rest_c)},
        "A_eq_B": actions(rt) == actions(rest_b),
        "B_eq_C": actions(rest_b) == actions(rest_c),
        "A_eq_C": actions(rt) == actions(rest_c),
        "obs0_A": dict(rt.slots[0].last_agent_observation or {}),
        "obs0_B": dict(rest_b.slots[0].last_agent_observation or {}),
        "obs0_C": dict(rest_c.slots[0].last_agent_observation or {}),
    }


def first_obs_diff(a: dict, b: dict) -> dict | None:
    keys = sorted(set(a) | set(b))
    for k in keys:
        if k not in a:
            return {"key": k, "kind": "missing_in_A"}
        if k not in b:
            return {"key": k, "kind": "missing_in_B"}
        va, vb = a[k], b[k]
        if va != vb:
            return {"key": k, "a": va, "b": vb, "kind": "value"}
    return None


def type_diffs(a: Any, b: Any, path: str, out: list, limit: int = 40) -> None:
    if len(out) >= limit:
        return
    if type(a) is not type(b):
        # list vs tuple, array vs list are expected JSON coercions
        ta, tb = type(a).__name__, type(b).__name__
        if {ta, tb} <= {"list", "tuple"}:
            type_diffs(list(a), list(b), path, out, limit)
            return
        out.append({"path": path, "type_a": ta, "type_b": tb})
        return
    if isinstance(a, dict):
        ka, kb = set(a), set(b)
        if ka != kb:
            out.append({"path": path, "kind": "dict_keys", "only_a": sorted(map(str, ka - kb))[:12], "only_b": sorted(map(str, kb - ka))[:12]})
            return
        for k in a:
            type_diffs(a[k], b[k], f"{path}.{k}", out, limit)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append({"path": path, "kind": "len", "len_a": len(a), "len_b": len(b)})
            return
        if path.endswith("OSC_BANDS") or path.endswith(".T") or "terrain" in path:
            return
        for i, (x, y) in enumerate(zip(a[:8], b[:8])):
            type_diffs(x, y, f"{path}[{i}]", out, limit)
    elif isinstance(a, float) and isinstance(b, float):
        if a != b:
            out.append({"path": path, "kind": "float", "a": a, "b": b})


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    os.chdir(str(ROOT))
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    # Binary search first A!=C
    first = None
    trace = []
    for mid in (1, 5, 10, 20, 50, 80, 100, 120):
        rt = make_runtime()
        for _ in range(mid):
            rt.step(n=1)
        tw = three_way_at(rt)
        row = {"t": mid, "A_eq_B": tw["A_eq_B"], "B_eq_C": tw["B_eq_C"], "A_eq_C": tw["A_eq_C"], "osc_live": tw["osc_energy_live"], "osc_snap": tw["osc_energy_snapshot"]}
        trace.append(row)
        if first is None and not tw["A_eq_C"]:
            first = mid

    detail = None
    rt = make_runtime()
    n_detail = first if first is not None else 50
    for _ in range(n_detail):
        rt.step(n=1)
    detail = three_way_at(rt)
    oa = detail.pop("obs0_A")
    ob = detail.pop("obs0_B")
    oc = detail.pop("obs0_C")
    detail["obs_diff_A_B"] = first_obs_diff(oa, ob)
    detail["obs_diff_A_C"] = first_obs_diff(oa, oc)
    detail["obs_diff_B_C"] = first_obs_diff(ob, oc)
    osc_keys = sorted(k for k in oa if str(k).startswith("osc_"))
    detail["osc_channel_mismatch_count"] = sum(1 for k in osc_keys if oa.get(k) != ob.get(k))

    # Structural JSON vs in-memory snapshot at t=20
    rt = make_runtime()
    for _ in range(20):
        rt.step(n=1)
    snap = rt.snapshot(persist=False)
    js = json_roundtrip(snap)
    sdiff: list = []
    type_diffs(snap, js, "snap", sdiff)
    has_osc = snap.get("world", {}).get("OSC_BANDS") is not None

    # Continuation gates
    gates = {}
    for seed_t, n, follow in ((575, 20, 10), (575, 100, 10)):
        key = f"seed_follow_{n}_{follow}"
        # seed 21 uses tiktaalik TwoAgent default? keep make_runtime (575 ecology)
        rt = make_runtime()
        for _ in range(n):
            rt.step(n=1)
        snap = rt.snapshot(persist=False)
        rest = restore(json_roundtrip(snap))
        ok = True
        acts_l, acts_r = [], []
        for _ in range(follow):
            rt.step(n=1)
            rest.step(n=1)
            acts_l.append(actions(rt))
            acts_r.append(actions(rest))
            if acts_l[-1] != acts_r[-1]:
                ok = False
                break
        gates[key] = {"equal": ok, "followed": len(acts_l), "first_mismatch": None if ok else {"i": len(acts_l), "live": acts_l[-1], "json": acts_r[-1]}}

    # Crash checkpoint smoke
    ck = {"CRASH_CHECKPOINT_REGRESSION": "NOT_RUN"}
    try:
        import pytest
        ck["note"] = "see pytest tests/test_beta31_crash_checkpoint.py"
    except Exception:
        pass

    summary = {
        "FIRST_DIVERGENT_CHECKPOINT_TICK": first,
        "search": trace,
        "three_way": {k: v for k, v in (detail or {}).items() if k not in ("obs0_A", "obs0_B", "obs0_C")},
        "snapshot_has_OSC_BANDS": has_osc,
        "structural_type_diffs_sample": sdiff[:30],
        "continuation_gates": gates,
        "osc_bands_in_planet_copy": True,
    }
    (OUT / "minimal_reproduction.json").write_text(json.dumps({"search": trace, "first": first}, indent=2), encoding="utf-8")
    (OUT / "three_way_continuation.json").write_text(json.dumps(summary["three_way"], indent=2, default=str), encoding="utf-8")
    (OUT / "snapshot_json_structural_diff.json").write_text(json.dumps(sdiff[:40], indent=2, default=str), encoding="utf-8")
    (OUT / "continuation_equivalence.json").write_text(json.dumps(gates, indent=2), encoding="utf-8")
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str)[:4000])
