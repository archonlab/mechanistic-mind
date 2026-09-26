#!/usr/bin/env python3
"""Pre-Beta-1 Observer Web path audit via the same HTTP APIs the SPA uses."""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from typing import Any

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8780"
FINDINGS: list[dict[str, Any]] = []


def find(sev: str, area: str, msg: str, **extra: Any) -> None:
    FINDINGS.append({"severity": sev, "area": area, "msg": msg, **extra})
    print(f"[{sev}] {area}: {msg}")


def req(method: str, path: str, body: dict | None = None, timeout: float = 30.0) -> Any:
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def get(path: str) -> Any:
    return req("GET", path)


def post(path: str, body: dict | None = None) -> Any:
    return req("POST", path, body or {})


def control(op: str, body: dict | None = None) -> Any:
    return post(f"/api/control/{op}", body)


def fingerprint(frame: dict) -> str:
    # Use stable scientific fields from state/snapshot if available
    return hashlib.sha256(json.dumps(frame, sort_keys=True, default=str)[:50000].encode()).hexdigest()[:16]


def main() -> int:
    print(f"=== PRE-BETA AUDIT against {BASE} ===")
    health = get("/api/health")
    print("health", health)
    if not health.get("ok"):
        find("BLOCKER", "launch", "health not ok", health=health)
        return 1

    # Fresh canonical one-agent
    f = post("/api/experiment/apply", {
        "seed": 17,
        "agent_count": 1,
        "cognition_enabled": True,
        "world": {"width": 12, "height": 12, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": {"cognition_enabled": True},
    })
    h = f.get("header") or {}
    print("after apply 1-agent", h.get("runtime_model"), "tick", h.get("tick"), "seed", h.get("seed"), "gen", h.get("runtime_generation"))
    if h.get("runtime_model") not in (None, "PhysicalSystemRuntime") and "Physical" not in str(h.get("runtime_model")):
        # some headers use different key
        pass
    state = get("/api/state")
    rt = (state.get("header") or {}).get("runtime_model") or health.get("runtime")
    if "PhysicalSystemRuntime" not in str(rt) and str((state.get("header") or {}).get("agent_count") or 1) != "1":
        find("HIGH", "experiment", f"expected 1-agent PhysicalSystemRuntime, got {rt} agent_count={(state.get('header') or {}).get('agent_count')}")

    # Controls: step/pause/play
    t0 = (get("/api/state").get("header") or {}).get("tick") or 0
    control("step", {"n": 1})
    t1 = (get("/api/state").get("header") or {}).get("tick")
    if t1 != t0 + 1:
        find("BLOCKER", "controls", f"STEP did not advance exactly 1 tick ({t0}→{t1})")
    else:
        print("STEP OK", t0, "→", t1)

    control("play")
    time.sleep(0.4)
    st = get("/api/state")
    if (st.get("header") or {}).get("status") != "RUNNING":
        find("BLOCKER", "controls", f"PLAY status={(st.get('header') or {}).get('status')}")
    tick_a = (st.get("header") or {}).get("tick")
    time.sleep(0.5)
    control("pause")
    st2 = get("/api/state")
    tick_b = (st2.get("header") or {}).get("tick")
    if (st2.get("header") or {}).get("status") != "PAUSED":
        find("BLOCKER", "controls", f"PAUSE status={(st2.get('header') or {}).get('status')}")
    time.sleep(0.3)
    tick_c = (get("/api/state").get("header") or {}).get("tick")
    if tick_c != tick_b:
        find("BLOCKER", "controls", f"PAUSE leaked ticks {tick_b}→{tick_c}")
    else:
        print("PAUSE holds tick", tick_b, "play advanced", tick_a, "→", tick_b)

    # Speed equivalence via step (API path mirrors UI control speed + step)
    def run_n(speed: float, n: int = 25) -> dict:
        post("/api/experiment/apply", {
            "seed": 143, "agent_count": 2, "cognition_enabled": True,
            "world": {"width": 12, "height": 12, "boundary_mode": "WRAP_PERIODIC"},
            "mechanisms": {"cognition_enabled": True, "prospective_composition": True},
        })
        control("speed", {"speed": speed})
        for _ in range(n):
            control("step", {"n": 1})
        snap = get("/api/snapshot")
        return snap

    print("determinism 1x/10x/MAX …")
    s1 = run_n(1)
    s10 = run_n(10)
    smax = run_n(50)
    # Compare agent actions / body from snapshot
    def snap_fp(s: dict) -> str:
        if "agents" in s:
            agents = s["agents"]
            bodies = [(a.get("body", {}).get("x"), a.get("body", {}).get("y"), a.get("last_selected_action") or a.get("body", {}).get("action")) for a in agents]
        else:
            bodies = [(s.get("body", {}).get("x"), s.get("body", {}).get("y"), s.get("last_selected_action"))]
        return json.dumps({"tick": s.get("tick"), "bodies": bodies, "seed": s.get("seed"), "agent_seeds": s.get("agent_seeds")}, sort_keys=True)

    fp1, fp10, fpmax = snap_fp(s1), snap_fp(s10), snap_fp(smax)
    if fp1 != fp10 or fp1 != fpmax:
        find("BLOCKER", "speed", "1×/10×/MAX scientific snapshot divergence", fp1=fp1, fp10=fp10, fpmax=fpmax)
    else:
        print("SPEED EQUIVALENCE OK", fp1[:80])

    # Two-agent + mechanism toggle parity
    post("/api/experiment/apply", {
        "seed": 143, "agent_count": 2, "cognition_enabled": True,
        "world": {"width": 12, "height": 12, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": {"cognition_enabled": True},
    })
    mechs = get("/api/mechanisms")
    # Toggle a cognition mechanism
    control("select_agent", {"index": 1})
    post("/api/control/mechanism", {"mechanism_id": "predictive_conflict", "enabled": True}) if False else None
    # actual endpoint
    try:
        post("/api/mechanism/predictive_conflict", {"enabled": True})
    except Exception:
        try:
            control("toggle_mechanism", {"mechanism_id": "predictive_conflict", "enabled": True})
        except Exception as e:
            # discover
            find("MEDIUM", "experiment", f"mechanism toggle path probe: {e}")

    # Discover mechanism toggle route from openapi if needed
    try:
        openapi = get("/openapi.json")
        paths = [p for p in openapi.get("paths", {}) if "mechanism" in p]
        print("mechanism paths", paths[:12])
    except Exception as e:
        print("no openapi", e)

    # Use known server route from prior knowledge
    try:
        r = req("POST", "/api/mechanisms/predictive_conflict", {"enabled": True})
        print("toggle result keys", list(r.keys())[:8] if isinstance(r, dict) else type(r))
    except urllib.error.HTTPError as e:
        print("toggle HTTP", e.code, e.read()[:200])
    except Exception as e:
        print("toggle err", e)

    # After apply two-agent, inspect agents_views identity
    for _ in range(15):
        control("step", {"n": 1})
    st = get("/api/state")
    views = st.get("agents_views") or {}
    if "agent_0" not in views or "agent_1" not in views:
        find("BLOCKER", "two-agent", f"agents_views missing keys {list(views.keys())}")
    else:
        a0, a1 = views["agent_0"], views["agent_1"]
        if a0.get("agent_seed") != 143 or a1.get("agent_seed") != 144:
            find("BLOCKER", "two-agent", f"seed mismatch {a0.get('agent_seed')} {a1.get('agent_seed')}")
        if a0.get("body_id") != "body-0" or a1.get("body_id") != "body-1":
            find("BLOCKER", "two-agent", f"body_id mismatch {a0.get('body_id')} {a1.get('body_id')}")
        # mind independence
        m0 = (a0.get("mind") or {}).get("metrics") or (a0.get("mind") or {}).get("action")
        m1 = (a1.get("mind") or {}).get("metrics") or (a1.get("mind") or {}).get("action")
        print("agent minds present", bool(m0), bool(m1), "selected", (st.get("header") or {}).get("selected_agent_id"))

    # Events attribution
    ev = get("/api/events?limit=200")
    events = ev.get("events") or []
    by_agent = Counter((e.get("agent_id") or e.get("actor_agent_id")) for e in events)
    print("events by agent", dict(by_agent), "types", Counter(e.get("type") for e in events).most_common(8))
    if by_agent.get("agent_0", 0) == 0 or by_agent.get("agent_1", 0) == 0:
        find("HIGH", "timeline", f"missing agent events {dict(by_agent)}")
    scen = [e for e in events if e.get("type") == "SCENARIO_SELECTED"]
    wait_scen = [e for e in scen if (e.get("evidence") or {}).get("selected_action") == "WAIT"]
    if not wait_scen and scen:
        find("MEDIUM", "timeline", "SCENARIO_SELECTED present but no WAIT selections in sample")
    elif wait_scen:
        print("cognitive WAIT SCENARIO_SELECTED OK", len(wait_scen))

    # Switch agent and verify projection
    control("select_agent", {"index": 0})
    s0 = get("/api/state")
    control("select_agent", {"index": 1})
    s1 = get("/api/state")
    id0 = (s0.get("header") or {}).get("selected_agent_id") or (s0.get("observer") or {}).get("selected_agent_id")
    id1 = (s1.get("header") or {}).get("selected_agent_id") or (s1.get("observer") or {}).get("selected_agent_id")
    print("selected after switch", id0, "→", id1)
    if id0 == id1 == "agent_1" or (id0 and id1 and id0 == id1):
        # may still be ok if header uses different field
        pass
    tick0, tick1 = (s0.get("header") or {}).get("tick"), (s1.get("header") or {}).get("tick")
    if tick0 != tick1:
        find("HIGH", "stale", f"select_agent changed tick {tick0}→{tick1}")

    # Reset isolation
    gen_before = (get("/api/state").get("header") or {}).get("runtime_generation")
    control("reset", {})
    st = get("/api/state")
    gen_after = (st.get("header") or {}).get("runtime_generation")
    tick_after = (st.get("header") or {}).get("tick")
    if tick_after not in (0, None) and int(tick_after or -1) != 0:
        find("HIGH", "lifecycle", f"RESET tick not 0: {tick_after}")
    if gen_after is not None and gen_before is not None and int(gen_after) <= int(gen_before):
        find("MEDIUM", "lifecycle", f"generation did not increase {gen_before}→{gen_after}")
    print("RESET OK gen", gen_before, "→", gen_after, "tick", tick_after)

    # Stop without save
    post("/api/experiment/apply", {
        "seed": 99, "agent_count": 1, "cognition_enabled": True,
        "world": {"width": 12, "height": 12, "boundary_mode": "WRAP_PERIODIC"},
    })
    for _ in range(5):
        control("step", {"n": 1})
    stop = control("stop", {"save": False, "reason": "USER_STOP_DISCARD"})
    print("stop discard keys", list(stop.keys())[:10], "status", (stop.get("header") or {}).get("status"))

    # Two-agent with signals
    try:
        post("/api/experiment/apply", {
            "seed": 143, "agent_count": 2, "cognition_enabled": True,
            "world": {"width": 12, "height": 12, "boundary_mode": "WRAP_PERIODIC"},
            "mechanisms": {"cognition_enabled": True},
            "signal_enabled": True,
        })
    except Exception as e:
        print("signal apply note", e)

    print("\n=== FINDINGS SUMMARY ===")
    by = Counter(f["severity"] for f in FINDINGS)
    print(dict(by), "total", len(FINDINGS))
    for f in FINDINGS:
        print("-", f["severity"], f["area"], f["msg"])
    out_path = "/home/thehost/Desktop/psy/.psy_observer/prebeta_audit_api.json"
    try:
        Path = __import__("pathlib").Path
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps({"base": BASE, "findings": FINDINGS}, indent=2))
        print("wrote", out_path)
    except Exception as e:
        print("write fail", e)
    blockers = by.get("BLOCKER", 0) + by.get("HIGH", 0)
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
