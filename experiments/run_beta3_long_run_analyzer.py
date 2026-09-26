"""Analyze the preserved forensic aged run without mutating it."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
FORENSIC = (
    _ROOT / "results" / "psychology_observer" / "psy_observer_web"
    / ".live-psyweb-20260923T015520.874726Z-f390c468"
)
OUT = _ROOT / "results" / "beta3_long_run_analysis"


def rss_kb(pid: int) -> int | None:
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except FileNotFoundError:
        return None
    return None


def meminfo() -> dict:
    out = {}
    with open("/proc/meminfo", encoding="utf-8") as f:
        for line in f:
            k, v = line.split(":", 1)
            out[k] = v.strip()
    return out


def main() -> int:
    assert FORENSIC.is_dir(), FORENSIC
    OUT.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in FORENSIC.iterdir()}
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_ROOT)
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [
        sys.executable, "-m", "mechanistic_mind.scientific_v3.analyzer_next.job",
        "--run-dir", str(FORENSIC),
        "--out-dir", str(OUT),
    ]
    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, cwd=str(_ROOT), env=env)
    samples = []
    peak = 0
    swap0 = meminfo()
    while True:
        rc = proc.poll()
        r = rss_kb(proc.pid)
        if r:
            peak = max(peak, r)
            samples.append({"t": round(time.perf_counter() - t0, 2), "rss_kb": r})
        mi = meminfo()
        prog_p = OUT / "progress.json"
        phase = None
        if prog_p.is_file():
            try:
                phase = json.loads(prog_p.read_text()).get("phase")
            except Exception:
                phase = None
        print(
            f"t={time.perf_counter()-t0:.1f}s analyzer_rss_kb={r} peak={peak} "
            f"phase={phase} swap={mi.get('SwapFree')} / {mi.get('SwapTotal')}",
            flush=True,
        )
        if rc is not None:
            break
        time.sleep(2.0)
    wall = time.perf_counter() - t0
    after = {p.name for p in FORENSIC.iterdir()}
    mutated = sorted(after - before)
    progress = {}
    if (OUT / "progress.json").is_file():
        progress = json.loads((OUT / "progress.json").read_text())
    report = {
        "analyzer_pid": proc.pid,
        "parent_pid": os.getpid(),
        "returncode": rc,
        "wall_s": round(wall, 3),
        "peak_rss_kb": peak,
        "samples": samples[-40:],
        "swap_before": {k: swap0.get(k) for k in ("SwapTotal", "SwapFree", "MemAvailable")},
        "swap_after": {k: meminfo().get(k) for k in ("SwapTotal", "SwapFree", "MemAvailable")},
        "forensic_mutated_names": mutated,
        "progress": progress,
        "observer_running": False,
        "isolation": "separate_process",
    }
    (OUT / "run_monitor.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "samples"}, indent=2))
    return 0 if rc == 0 else rc


if __name__ == "__main__":
    raise SystemExit(main())
