#!/usr/bin/env python3
"""Observer-only FPV performance: OFF vs SENSOR SPACE 5FPS vs FPV 5FPS vs SPLIT."""
from __future__ import annotations

import json
import resource
import time
from pathlib import Path

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.tiktaalik_eye import build_tiktaalik_eye_payload

OUT = Path("results/beta31_tiktaalik_fpv")


def _rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def bench(*, rate: str, fpv: bool, n: int = 60) -> dict:
    s = ObserverSession(SessionConfig(seed=101, evidence_mode="SEARCH_COMPACT"))
    s.runtime.set_mechanism("physical_near_field_vision", True)
    try:
        s.runtime.set_visual_surface_discrimination("RICH")
        s.set_vision_radius(3)
    except Exception:
        pass
    s.set_tiktaalik_eye(rate=rate, fpv=fpv)
    t0 = time.perf_counter()
    for _ in range(n):
        s.step()
    elapsed = time.perf_counter() - t0
    payload = s._eye_last_payload or {}
    n_samples = 0
    for panel in (payload.get("agents") or {}).values():
        fp = (panel or {}).get("fpv") or {}
        n_samples += int(fp.get("n_samples") or len(fp.get("samples") or []))
    return {
        "rate": rate,
        "fpv": fpv,
        "ticks": n,
        "elapsed_s": elapsed,
        "ms_per_tick": 1000.0 * elapsed / max(1, n),
        "ticks_per_s": n / max(1e-9, elapsed),
        "rss_peak_mb": _rss_mb(),
        "payload_bytes": int(payload.get("payload_bytes") or 0),
        "build_ms": float(s._eye_last_build_ms),
        "update_count": int(s._eye_update_count),
        "samples_update": n_samples,
        "fpv_included": bool(payload.get("fpv_included")),
        "status": payload.get("status"),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ta = TwoAgentRuntime(seed=3)
    ta.set_mechanism("physical_near_field_vision", True)
    try:
        ta.set_visual_surface_discrimination("RICH")
        for slot in ta.slots:
            slot.config.near_field_exteroception.radius = 3
            slot.last_agent_observation = slot.agent_observation()
    except Exception:
        pass
    t0 = time.perf_counter()
    p = build_tiktaalik_eye_payload(ta, include_fpv=True, rate="5FPS")
    diag_ms = (time.perf_counter() - t0) * 1000.0
    t1 = time.perf_counter()
    json.dumps(p, default=str)
    ser_ms = (time.perf_counter() - t1) * 1000.0
    n_samples = sum(
        int((a.get("fpv") or {}).get("n_samples") or 0)
        for a in (p.get("agents") or {}).values()
    )
    rows = [
        bench(rate="OFF", fpv=False),
        bench(rate="5FPS", fpv=False),
        bench(rate="5FPS", fpv=True),
    ]
    hl = ObserverSession(SessionConfig(seed=5, evidence_mode="SEARCH_COMPACT", execution_mode="HEADLESS"))
    hl.set_tiktaalik_eye(rate="5FPS", fpv=True)
    with hl._lock:
        frame = hl._capture_locked()
    summary = {
        "payload_fpv_build_ms": diag_ms,
        "payload_serialize_ms": ser_ms,
        "payload_bytes": p.get("payload_bytes"),
        "samples_update": n_samples,
        "session": rows,
        "headless_fpv_included": (frame.get("tiktaalik_eye") or {}).get("fpv_included"),
        "fpv_vs_off_ms_delta": rows[2]["ms_per_tick"] - rows[0]["ms_per_tick"],
        "fpv_vs_sensor_space_ms_delta": rows[2]["ms_per_tick"] - rows[1]["ms_per_tick"],
    }
    (OUT / "performance.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
