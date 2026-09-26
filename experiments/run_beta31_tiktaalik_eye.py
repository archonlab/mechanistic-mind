#!/usr/bin/env python3
"""Observer-only Eye performance: OFF vs SNAPSHOT vs 5FPS. No science change."""
from __future__ import annotations

import json
import resource
import time
from pathlib import Path

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.tiktaalik_eye import build_tiktaalik_eye_payload

OUT = Path("results/beta31_tiktaalik_eye")


def _rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def bench(rate: str, n: int = 80) -> dict:
    s = ObserverSession(SessionConfig(seed=101, evidence_mode="SEARCH_COMPACT"))
    s.runtime.set_mechanism("physical_near_field_vision", True)
    try:
        s.runtime.set_visual_surface_discrimination("RICH")
    except Exception:
        pass
    s.set_tiktaalik_eye(rate=rate)
    t0 = time.perf_counter()
    for _ in range(n):
        s.step()
    elapsed = time.perf_counter() - t0
    payload = s._eye_last_payload
    bytes_ = int((payload or {}).get("payload_bytes") or 0)
    return {
        "rate": rate,
        "ticks": n,
        "elapsed_s": elapsed,
        "ms_per_tick": 1000.0 * elapsed / max(1, n),
        "ticks_per_s": n / max(1e-9, elapsed),
        "rss_peak_mb": _rss_mb(),
        "eye_payload_bytes": bytes_,
        "eye_update_count": int(s._eye_update_count),
        "eye_last_build_ms": float(s._eye_last_build_ms),
        "eye_status": (payload or {}).get("status") if payload else "none",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Payload-only microbench (no session capture).
    ta = TwoAgentRuntime(seed=3)
    ta.set_mechanism("physical_near_field_vision", True)
    for slot in ta.slots:
        slot.last_agent_observation = slot.agent_observation()
    t0 = time.perf_counter()
    p = build_tiktaalik_eye_payload(ta, rate="5FPS")
    build_ms = (time.perf_counter() - t0) * 1000.0
    rows = [bench("OFF"), bench("SNAPSHOT"), bench("5FPS")]
    summary = {
        "payload_only_build_ms": build_ms,
        "payload_bytes": p.get("payload_bytes"),
        "session": rows,
        "off_vs_5fps_ms_delta": rows[2]["ms_per_tick"] - rows[0]["ms_per_tick"],
    }
    (OUT / "performance.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
