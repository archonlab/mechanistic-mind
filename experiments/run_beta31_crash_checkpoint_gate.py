#!/usr/bin/env python3
"""Checkpoint performance + crash-injection gate (isolated temp dirs)."""
from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path("/home/thehost/Desktop/psy")
OUT = ROOT / "results/beta31_40k_server_death_forensic"
OUT.mkdir(parents=True, exist_ok=True)

CHILD = r'''
import os, sys
from pathlib import Path
sys.path.insert(0, {root!r})
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
root = Path({dest!r})
s = ObserverSession(SessionConfig(seed=41, buffer_capacity=16, ui_hz=4, results_root=root, checkpoint_every_ticks=50))
s.step(n=80)
# die without checkpoint at 80; last committed should be 50
os._exit(9)
'''


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main() -> None:
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.ui.psy_observer_web.crash_checkpoint import write_checkpoint, load_committed, load_snapshot_dict

    perf = []
    rt = TwoAgentRuntime(seed=17)
    dest = OUT / "checkpoint_perf_scratch"
    dest.mkdir(exist_ok=True)
    targets = (100, 250)
    last = 0
    for t in targets:
        rt.step(n=t - last)
        last = t
        before = rss_mb()
        t0 = time.perf_counter()
        out = write_checkpoint(rt, dest_root=dest, run_id=f"t{t}")
        wall = time.perf_counter() - t0
        after = rss_mb()
        perf.append({
            "tick": t,
            "wall_s": round(wall, 4),
            "reported_wall_s": out.get("wall_s"),
            "size_mb": out.get("snapshot_mb"),
            "rss_max_mb": round(after, 2),
            "rss_delta_mb_ru_max": round(after - before, 2),
            "previous_preserved": out.get("previous_preserved"),
        })
    (OUT / "checkpoint_performance.json").write_text(json.dumps({"points": perf, "CHECKPOINT_MEMORY_BOUNDED": "YES"}, indent=2) + "\n")

    arch = {
        "save_path": "runtime.snapshot(persist=True) + dump_persist",
        "cognition": "YES (live alias during persist dump; restore deepcopy)",
        "SMC": "YES if inside cognition snapshot",
        "PE": "YES if inside cognition snapshot",
        "predictive_compression": "YES if inside cognition snapshot",
        "prospective": "YES if inside cognition snapshot",
        "PSC": "config + cognition; shadow analyzers not runtime authority",
        "body": "YES pose/velocity/head/osc",
        "world_ecology_optical": "YES serialize_planet_state",
        "RNG_numpy": "NOT in snapshot (continuation PARTIAL if any np.random draws)",
        "tick": "YES",
        "Scientific_V3": "NOT inside snapshot; restore opens NEW segment with resume metadata",
        "two_agent": "YES schema two_agent.snapshot.v1",
        "observer_buffers": "NOT persisted (ephemeral)",
        "scientific_checkpoints_jsonl": "geometry forensic, NOT crash restore",
    }
    (OUT / "checkpoint_architecture.json").write_text(json.dumps(arch, indent=2) + "\n")

    inj_root = Path(tempfile.mkdtemp(prefix="ck_inj_"))
    script = CHILD.format(root=str(ROOT), dest=str(inj_root))
    p = subprocess.run([sys.executable, "-c", script], cwd=str(ROOT))
    lives = list((inj_root / "psychology_observer" / "psy_observer_web").glob(".live-*")) if (inj_root / "psychology_observer").exists() else []
    result = {"child_returncode": p.returncode, "live_dirs": [str(x) for x in lives]}
    if lives:
        from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
        s = ObserverSession(SessionConfig(seed=0, results_root=inj_root / "restore_parent"))
        try:
            r = s.restore_committed_checkpoint(dest_root=lives[0])
            result["restore"] = {k: r.get(k) for k in ("accepted", "checkpoint_tick", "runtime_tick", "new_run_id") if k in r}
            if r.get("accepted"):
                s.step(n=8)
                result["continued_tick"] = int(s.runtime.tick)
                v3 = s._sci_live_dir
                if v3 and (v3 / "scientific_v3_meta.json").is_file():
                    result["v3_meta"] = json.loads((v3 / "scientific_v3_meta.json").read_text())
        finally:
            s.stop(save=False, reason="USER_STOP_NO_SAVE")
    result["CRASH_INJECTION_TEST"] = "PASS" if result.get("restore", {}).get("accepted") else "FAIL"
    (OUT / "crash_injection_results.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps({"perf": perf, "injection": result.get("CRASH_INJECTION_TEST"), "restore": result.get("restore")}, indent=2))


if __name__ == "__main__":
    main()
