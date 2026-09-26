"""Save/resume reliability: mixed dict keys must not crash finalize."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.run_finalize import json_safe, write_finalized_run


def test_json_safe_int_none_keys_sort():
    payload = {2: "int-key", None: "none-key", "WAIT": 3, True: False}
    dumped = json.dumps(json_safe(payload), sort_keys=True)
    data = json.loads(dumped)
    assert data["2"] == "int-key"
    assert data["null"] == "none-key"
    assert data["WAIT"] == 3
    assert data["true"] is False


def test_json_safe_preserves_none_values():
    assert json_safe({"tick": None, "n": 4})["tick"] is None
    assert json.dumps(json_safe({"tick": None}), sort_keys=True) == '{"tick": null}'


def test_write_finalized_run_with_mixed_cognition_keys():
    rt = TwoAgentRuntime(seed=17)
    rt.step(8)
    store = rt.slots[0].cognition.setdefault("metrics", {}).setdefault("action_counts", {})
    store[None] = 1
    store[0] = 2
    with TemporaryDirectory() as d:
        out = write_finalized_run(
            results_root=Path(d),
            runtime=rt,
            session_meta={"started_at": "t", "seed": 17, "buffer": {}},
            timeline=[{"tick": None}, {"tick": int(rt.tick)}],
            telemetry=[{"tick": None}],
            termination_reason="USER_STOP_SAVED",
            run_id="json-safe-mix",
            identity={
                "expected_final_tick": int(rt.tick),
                "runtime_type": type(rt).__name__,
                "seed": 17,
                "agent_count": 2,
            },
        )
        assert out.get("accepted") is True, out.get("error")
        # Encoder must stringify mixed keys without mutating live cognition.
        assert None in store and 0 in store
        snap_path = Path(out["run_dir"]) / "physical_system_snapshot.json"
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        restored = TwoAgentRuntime.restore(snap)
        assert int(restored.tick) == int(rt.tick)
        x0, y0 = float(rt.slots[0].body.x), float(rt.slots[0].body.y)
        assert abs(float(restored.slots[0].body.x) - x0) < 1e-9
        assert abs(float(restored.slots[0].body.y) - y0) < 1e-9
        restored.step(1)
        assert int(restored.tick) == int(rt.tick) + 1
