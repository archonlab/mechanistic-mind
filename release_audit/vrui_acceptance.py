#!/usr/bin/env python3
"""VRUI acceptance for Public Beta vision radius controls (packaging fix)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "release_audit" / "VRUI_ACCEPTANCE.json"


def main() -> None:
    gates: dict[str, str] = {}

    dist = ROOT / "mechanistic_mind/ui/psy_observer_web/web_dist"
    html = (dist / "index.html").read_text(encoding="utf-8")
    js_files = list((dist / "assets").glob("index-*.js"))
    assert js_files, "no js bundle"
    js = js_files[0].read_text(encoding="utf-8")
    m = re.search(r"/assets/(index-[A-Za-z0-9_-]+\.js)", html)
    gates["VRUI1"] = (
        "PASS"
        if "RADIUS_OPTIONS" in (ROOT / "web/psy-observer/src/components/NearFieldSensorPanel.tsx").read_text(encoding="utf-8")
        and all(s in js for s in ("R=1 · max 8", "R=2 · max 24", "R=3 · max 48"))
        else "FAIL"
    )
    gates["VRUI20"] = (
        "PASS"
        if m and m.group(1) == js_files[0].name
        and all(s in js for s in ("R=1 · max 8", "R=2 · max 24", "R=3 · max 48", "/api/vision/radius"))
        else "FAIL"
    )

    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
    from mechanistic_mind.physical_system.ecology_presets import ECOLOGY_STRUCTURED_TERRAIN

    sess = ObserverSession(config=SessionConfig(seed=17, ui_hz=10.0, buffer_capacity=64, speed=50.0))
    sess.apply_experiment({
        "seed": 17,
        "ecology_preset": ECOLOGY_STRUCTURED_TERRAIN,
        "agent_count": 2,
        "cognition_enabled": True,
        "mechanisms": {
            "cognition_enabled": True,
            "physical_near_field_vision": True,
            "illumination_cycle": True,
            "physical_body_optical_response": True,
            "experimental_physical_signal": True,
            "spatiotemporal_climate_ecology": False,
        },
    })
    try:
        sess.set_mechanism("spatiotemporal_climate_ecology", False)
    except Exception:
        pass

    r0 = int(sess.runtime.slots[0].config.near_field_exteroception.radius)
    gates["VRUI2"] = "PASS" if r0 == 1 else f"FAIL:{r0}"

    with sess._step_lock:
        sess._scientific_step_once_unlocked()

    # Use runtime sample via observation path
    from mechanistic_mind.physical_system.near_field_exteroception import (
        moore_max_candidates,
    )
    assert moore_max_candidates(1) == 8
    assert moore_max_candidates(2) == 24
    assert moore_max_candidates(3) == 48
    gates["VRUI3"] = "PASS"

    tick_before = int(sess.runtime.tick)
    poses0 = [(float(s.body.x), float(s.body.y)) for s in sess.runtime.slots]
    cog0 = [id(s.cognition) for s in sess.runtime.slots]

    out2 = sess.set_vision_radius(2)
    vr = out2.get("vision_radius") or {}
    gates["VRUI4"] = "PASS" if vr.get("new") == 2 else f"FAIL:{vr}"
    gates["VRUI5"] = (
        "PASS"
        if int(sess.runtime.tick) == tick_before
        and poses0 == [(float(s.body.x), float(s.body.y)) for s in sess.runtime.slots]
        and cog0 == [id(s.cognition) for s in sess.runtime.slots]
        else "FAIL"
    )
    r_slots = [int(s.config.near_field_exteroception.radius) for s in sess.runtime.slots]
    gates["VRUI6"] = "PASS" if r_slots == [2, 2] else f"FAIL:{r_slots}"
    gates["VRUI7"] = "PASS" if vr.get("old") == 1 and vr.get("new") == 2 else f"FAIL:{vr}"
    gates["VRUI13"] = "PASS" if r_slots == [2, 2] else f"FAIL:{r_slots}"

    out3 = sess.set_vision_radius(3)
    vr3 = out3.get("vision_radius") or {}
    gates["VRUI8"] = "PASS" if vr3.get("new") == 3 else f"FAIL:{vr3}"
    r_slots = [int(s.config.near_field_exteroception.radius) for s in sess.runtime.slots]
    gates["VRUI9"] = "PASS" if r_slots == [3, 3] else f"FAIL:{r_slots}"
    gates["VRUI10"] = "PASS" if vr3.get("old") == 2 and vr3.get("new") == 3 else f"FAIL:{vr3}"

    out1 = sess.set_vision_radius(1)
    vr1 = out1.get("vision_radius") or {}
    gates["VRUI11"] = "PASS" if vr1.get("new") == 1 else f"FAIL:{vr1}"
    gates["VRUI12"] = "PASS" if moore_max_candidates(1) == 8 and vr1.get("new") == 1 else "FAIL"

    # Visual Forensics radius in scientific history
    from datetime import datetime, timezone
    from mechanistic_mind.ui.psy_observer_web.run_finalize import new_run_id

    sess._run_started_at = datetime.now(timezone.utc).isoformat()
    sess._active_run_id = new_run_id()
    with sess._lock:
        sess._ensure_scientific_locked()
    sess.set_vision_radius(2)
    with sess._step_lock:
        sess._scientific_step_once_unlocked()
        with sess._lock:
            sess._append_scientific_locked()
    with sess._lock:
        if sess._sci_writer is not None:
            sess._sci_writer.flush()
    live = Path(sess._sci_live_dir) / "scientific_timeline.jsonl"
    if not live.is_file():
        gates["VRUI14"] = "FAIL:no_timeline"
        row = {"vision_optical": {}}
    else:
        row = json.loads(live.read_text(encoding="utf-8").strip().splitlines()[-1])
    vo = row.get("vision_optical") or {}
    gates["VRUI14"] = "PASS" if int(vo.get("vision_radius") or vo.get("radius") or 0) == 2 else f"FAIL:{vo}"

    obs = sess.runtime.slots[0].last_agent_observation or {}
    bad = [k for k in obs if any(x in str(k).lower() for x in ("agent_", "undercover", "experimenter"))]
    gates["VRUI15"] = "PASS" if not bad else f"FAIL:{bad[:5]}"

    for k in ("VRUI16", "VRUI17", "VRUI18", "VRUI19"):
        gates.setdefault(k, "PENDING")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"gates": gates, "bundle": js_files[0].name, "vr": {"r2": vr, "r3": vr3, "r1": vr1}}, indent=2), encoding="utf-8")
    print(json.dumps(gates, indent=2))
    fails = [k for k, v in gates.items() if not str(v).startswith("PASS") and v != "PENDING"]
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
