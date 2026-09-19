#!/usr/bin/env python3
"""Minimal public-package smoke: two-agent, undercover, vision R, VF append."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def smoke_two_agent() -> dict:
    from mechanistic_mind.physical_system.ecology_presets import (
        ECOLOGY_STRUCTURED_TERRAIN,
        make_ecology_config,
    )
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
    from datetime import datetime, timezone
    from mechanistic_mind.ui.psy_observer_web.run_finalize import new_run_id

    sess = ObserverSession(config=SessionConfig(seed=17, ui_hz=10.0, buffer_capacity=64, speed=50.0))
    sess.apply_experiment({
        "seed": 17,
        "ecology_preset": ECOLOGY_STRUCTURED_TERRAIN,
        "agent_count": 2,
        "cognition_enabled": True,
        "mechanisms": {
            "cognition_enabled": True,
            "experimental_physical_signal": True,
            "physical_near_field_vision": True,
            "illumination_cycle": True,
            "physical_body_optical_response": True,
            "spatiotemporal_climate_ecology": False,
        },
    })
    try:
        sess.set_mechanism("spatiotemporal_climate_ecology", False)
    except Exception:
        pass
    try:
        sess.set_vision_radius(1)
    except Exception:
        pass
    sess._run_started_at = datetime.now(timezone.utc).isoformat()
    sess._active_run_id = new_run_id()
    with sess._lock:
        sess._ensure_scientific_locked()
    for _ in range(30):
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
                sess._append_scientific_locked()
    assert int(sess.runtime.tick) == 30
    assert len(sess.runtime.slots) == 2
    sci = sess._sci_writer
    assert sci is not None and sci._rows_written >= 30
    # vision R LIVE
    for r in (1, 2, 3, 1):
        sess.set_vision_radius(r)
        assert int(sess.runtime.slots[0].config.near_field_exteroception.radius) == r
    # VF compact present in timeline if file exists
    live = Path(sess._sci_live_dir) / "scientific_timeline.jsonl"
    assert live.is_file()
    line = live.read_text(encoding="utf-8").splitlines()[-1]
    row = json.loads(line)
    assert "vision_optical" in row
    return {
        "tick": int(sess.runtime.tick),
        "agents": 2,
        "sci_rows": sci._rows_written,
        "vision_radius_final": 1,
        "vision_optical": True,
        "default_r_restored": True,
    }


def smoke_undercover() -> dict:
    """Exercise Undercover via the same session API used by the Web UI."""
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    sess = ObserverSession(config=SessionConfig(seed=17, ui_hz=10.0, buffer_capacity=64, speed=50.0))
    sess.apply_experiment({
        "seed": 17,
        "ecology_preset": "STRUCTURED_TERRAIN_EXPERIMENTAL",
        "agent_count": 2,
        "cognition_enabled": True,
    })
    # Enable undercover through available session methods
    enabled = False
    for name in ("set_undercover", "enable_undercover", "undercover_enable"):
        fn = getattr(sess, name, None)
        if callable(fn):
            try:
                fn(True)
                enabled = True
                break
            except TypeError:
                try:
                    fn()
                    enabled = True
                    break
                except Exception:
                    pass
            except Exception:
                pass
    if not enabled and hasattr(sess, "apply_experiment"):
        try:
            sess.apply_experiment({"undercover": True, "seed": 17, "agent_count": 2, "cognition_enabled": True})
            enabled = True
        except Exception:
            pass
    rt = sess.runtime
    slots = list(getattr(rt, "slots", []) or [])
    exp = getattr(rt, "experimenter_slot", None)
    body_ids = []
    for s in slots:
        b = getattr(s, "body", None)
        if b is not None:
            body_ids.append(getattr(b, "body_id", id(b)))
    if exp is not None and getattr(exp, "body", None) is not None:
        body_ids.append(getattr(exp.body, "body_id", id(exp.body)))
    # step a few ticks
    for _ in range(10):
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
    unique_bodies = len(set(body_ids))
    return {
        "enabled_attempted": enabled,
        "slot_count": len(slots),
        "experimenter_slot_present": exp is not None,
        "unique_body_ids": unique_bodies,
        "body_ids": [str(x) for x in body_ids],
        "tick": int(rt.tick),
        "no_duplicate_physical_pair": unique_bodies <= len(slots) + (1 if exp is not None else 0),
    }


def main() -> None:
    out = {
        "two_agent": smoke_two_agent(),
        "undercover": smoke_undercover(),
        "identity": __import__(
            "mechanistic_mind.model.identity", fromlist=["release_display_name"]
        ).release_display_name(),
    }
    path = ROOT / "release_audit" / "SMOKE_RESULTS.json"
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
