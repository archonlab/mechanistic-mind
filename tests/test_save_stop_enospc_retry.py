"""Save & Stop: mocked ENOSPC preserves live state; retry publishes."""
from __future__ import annotations

import errno
import os

import pytest

from mechanistic_mind.ui.psy_observer_web.run_finalize import read_run_manifest, write_finalized_run
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def test_save_stop_enospc_preserves_live_then_retry(tmp_path, monkeypatch):
    session = ObserverSession(SessionConfig(seed=23, buffer_capacity=32, results_root=tmp_path))
    session.apply_experiment({"seed": 23, "agent_count": 2, "public_preset": "BETA3_RECOMMENDED"})
    session.step(5)
    live_tick = int(session.runtime.tick)
    live_id = id(session.runtime)
    assert live_tick == 5

    orig_dump = write_finalized_run.__globals__["_json_dump"]
    calls = {"n": 0}

    def boom_once(path, payload, *, compact=False):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError(errno.ENOSPC, "No space left on device")
        return orig_dump(path, payload, compact=compact)

    monkeypatch.setattr(
        "mechanistic_mind.ui.psy_observer_web.run_finalize._json_dump",
        boom_once,
    )

    failed = session.stop(save=True, reason="USER_STOP_SAVED", wait=True)
    assert failed["finalize"]["accepted"] is False
    err = str(failed["finalize"].get("error") or failed.get("control_receipt", {}).get("reason") or "")
    assert "No space left" in err or "ENOSPC" in err or str(errno.ENOSPC) in err
    assert session.status == "SAVE_FAILED"
    assert id(session.runtime) == live_id
    assert int(session.runtime.tick) == live_tick
    requested = live_tick

    monkeypatch.setattr(
        "mechanistic_mind.ui.psy_observer_web.run_finalize._json_dump",
        orig_dump,
    )
    ok = session.stop(save=True, reason="USER_STOP_SAVED", wait=True)
    assert ok["finalize"]["accepted"] is True
    assert int(ok["finalize"]["final_tick"]) == requested
    dirs = sorted(
        p for p in (tmp_path / "psychology_observer" / "psy_observer_web").iterdir()
        if p.is_dir() and (p / "run.json").is_file()
    )
    assert len(dirs) == 1
    manifest = read_run_manifest(dirs[0])
    assert int(manifest["final_tick"]) == requested
    session.stop(save=False, reason="USER_STOP_NO_SAVE")
