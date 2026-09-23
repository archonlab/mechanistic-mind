"""Smoke: Public Beta 3 recommended preset + save/restore on a tiny run.

When PSY_RELEASE_ROOT is set, that tree should be on PYTHONPATH.
"""
from __future__ import annotations

import os
from pathlib import Path

from mechanistic_mind.physical_system import observed_composite_psc as oc
from mechanistic_mind.ui.psy_observer_web.run_finalize import read_run_manifest, read_run_snapshot
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def test_packaged_recommended_play_pause_save_restore(tmp_path):
    root = Path(os.environ.get("PSY_RELEASE_ROOT") or Path(__file__).resolve().parents[1])
    spa = root / "mechanistic_mind" / "ui" / "psy_observer_web" / "web_dist" / "index.html"
    assert spa.is_file(), f"missing web_dist in {root}"
    s = ObserverSession(SessionConfig(seed=31, buffer_capacity=32, results_root=tmp_path))
    s.apply_experiment({"seed": 31, "public_preset": "BETA3_RECOMMENDED"})
    en = s.runtime.mechanisms()["enabled"]
    assert en["prospective_scenario_competition"] is False
    assert en["spatiotemporal_climate_ecology"] is False
    assert oc.normalize_mode(s.runtime.slots[0].config.cognition.psc_motor_resolution) == "OBSERVED_COMPOSITE"
    s.step(12)
    s.set_mechanism("prospective_scenario_competition", True)
    assert s.runtime.mechanisms()["enabled"]["prospective_scenario_competition"] is True
    assert int(s.runtime.tick) == 12
    s.step(3)
    tick = int(s.runtime.tick)
    out = s.stop(save=True, reason="USER_STOP_SAVED", wait=True)
    assert out["finalize"]["accepted"] is True
    assert int(out["finalize"]["final_tick"]) == tick
    run_dir = Path(out["finalize"]["run_dir"])
    snap = read_run_snapshot(run_dir)
    man = read_run_manifest(run_dir)
    assert int(man["final_tick"]) == tick
    s2 = ObserverSession(SessionConfig(seed=0, results_root=tmp_path))
    rec = s2.restore(snap)
    assert rec["control_receipt"]["accepted"] is True
    t0 = int(s2.runtime.tick)
    s2.step(2)
    assert int(s2.runtime.tick) == t0 + 2
