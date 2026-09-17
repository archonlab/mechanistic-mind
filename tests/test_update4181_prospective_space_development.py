import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "u4181", ROOT / "experiments" / "run_update4181_prospective_space_development.py"
)
u4181 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(u4181)


def test_checkpoints_scale_without_resetting_history():
    assert u4181.checkpoints(100000) == [0, 100, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]
    assert u4181.checkpoints(1000) == [0, 100, 500, 1000]
    assert u4181.checkpoints(20) == [0, 5, 10, 15, 20]


def test_fresh_engine_has_no_pretrained_transition_evidence():
    args = type("Args", (), {"seed": 17, "perception_mode": "multi-channel",
        "world_dynamics": "dynamic", "cue_mode": "perceptual",
        "memory_architecture": "EXPERIENCE_GATED_V05"})()
    eng = u4181.make_engine(args)
    snap = u4181.probe(eng, [], {})
    assert snap["tick"] == 0
    assert snap["experience_count"] == 0
    assert snap["acquired_transition_count"] == 0
    assert snap["supported_transition_count"] == 0
    assert snap["known_depth1"] == snap["known_depth2"] == snap["known_depth3"] == 0


def test_free_step_uses_no_external_action_override():
    args = type("Args", (), {"seed": 23, "perception_mode": "contact-only",
        "world_dynamics": "static", "cue_mode": "legacy",
        "memory_architecture": "EXPERIENCE_GATED_V05"})()
    eng = u4181.make_engine(args)
    result = eng.step()
    assert result.action_sources["A001"] != "EXTERNAL_OVERRIDE"


def test_live_observer_stream_publishes_first_completed_tick(tmp_path):
    path = tmp_path / "psychology_observer.jsonl"
    args = type("Args", (), {"seed": 17, "perception_mode": "multi-channel",
        "world_dynamics": "dynamic", "cue_mode": "perceptual",
        "memory_architecture": "EXPERIENCE_GATED_V05", "jsonl": str(path),
        "archon_jsonl": ""})()
    eng = u4181.make_engine(args)
    eng.step(); eng.close()
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["record_type"] for row in records] == ["run_metadata", "tick", "run_summary"]
    assert records[1]["payload"]["tick"] == 0
    assert records[1]["payload"]["action_sources"]["A001"] != "EXTERNAL_OVERRIDE"
