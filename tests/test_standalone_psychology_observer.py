from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from mechanistic_mind.ui.psychology_observer.cli import headless_contract
from mechanistic_mind.ui.psychology_observer.controller import (
    PsychologyLaunchSpec,
    PsychologyObserverController,
)
from mechanistic_mind.ui.psychology_observer.model import (
    PsychologyTelemetryProjector,
)


ROOT = Path(__file__).resolve().parents[1]


class UnusedRunner:
    def start(self, command, **kwargs):
        raise AssertionError("not used")

    def stream_and_wait(self, process, output):
        raise AssertionError("not used")

    def terminate(self, process):
        raise AssertionError("not used")


def test_headless_contract_is_standalone() -> None:
    contract = headless_contract(ROOT)
    assert contract["standalone"] is True
    assert contract["launcher_exists"] is True
    assert "contextual-objects" in contract["worlds"]
    assert contract["resizable_panels"] == ["left", "causal-timeline"]
    assert contract["contextual_memory_architectures"][0] == "BOUNDED_COMPRESSED"
    assert "EXPERIENCE_GATED_V05" in contract["contextual_memory_architectures"]
    assert contract["world_dynamics"] == ["STATIC_WORLD", "DYNAMIC_WORLD"]
    assert "cognitive_depth" in contract["observer_panels"]


def test_controller_builds_commands_without_archon(tmp_path: Path) -> None:
    controller = PsychologyObserverController(
        mechanistic_mind_root=ROOT,
        process_runner=UnusedRunner(),
        results_root=tmp_path,
    )

    persistent = controller.build_command(
        PsychologyLaunchSpec(
            world="persistent-targets",
            persistent_condition="REVIVAL",
        ),
        tmp_path,
    )
    assert persistent[0] == sys.executable
    assert "--persistent-condition" in persistent
    assert "REVIVAL" in persistent

    contextual = controller.build_command(
        PsychologyLaunchSpec(world="contextual-objects"),
        tmp_path,
    )
    assert contextual[contextual.index("--mechanism") + 1] == "bounded-compressed"
    assert "--resource-layout" not in contextual
    assert "--obstacle-condition" not in contextual

    legacy = controller.build_command(
        PsychologyLaunchSpec(
            world="contextual-objects",
            memory_architecture="LEGACY_PSYCHE_V03",
        ),
        tmp_path,
    )
    assert legacy[legacy.index("--mechanism") + 1] == "psyche-v03"

    gated = controller.build_command(
        PsychologyLaunchSpec(
            world="contextual-objects",
            memory_architecture="EXPERIENCE_GATED_V05",
            world_dynamics="DYNAMIC_WORLD",
        ),
        tmp_path,
    )
    assert gated[gated.index("--mechanism") + 1] == "psyche-v05-experience-gated"
    assert gated[gated.index("--world-dynamics") + 1] == "dynamic"

    update417 = controller.build_command(
        PsychologyLaunchSpec(
            experiment_preset="4.17 Persistent Expectation × Fresh Prediction Conflict"
        ),
        tmp_path,
    )
    assert update417 == [
        sys.executable,
        str(ROOT / "experiments" / "run_update417_prospective_conflict.py"),
    ]
    update418 = controller.build_command(
        PsychologyLaunchSpec(experiment_preset="4.18 Composed Future Value"), tmp_path / "u418"
    )
    assert update418 == [
        sys.executable,
        str(ROOT / "experiments" / "run_update418_composed_future_value.py"),
    ]
    update4181 = controller.build_command(
        PsychologyLaunchSpec(
            ticks=1000, seed=23, experiment_preset="4.18.1 Prospective Space Development",
            world="contextual-objects", memory_architecture="EXPERIENCE_GATED_V05",
            world_dynamics="DYNAMIC_WORLD", perception_mode="MULTI_CHANNEL",
            cue_mode="PERCEPTUAL_CUE_ENABLED",
        ), tmp_path / "u4181"
    )
    assert update4181[:6] == [
        sys.executable, str(ROOT / "experiments" / "run_update4181_prospective_space_development.py"),
        "--ticks", "1000", "--seed", "23",
    ]
    assert "--memory-architecture" in update4181
    update4182 = controller.build_command(
        PsychologyLaunchSpec(
            ticks=1000, seed=17, experiment_preset="4.18.2 Dynamic Sustaining Ecology",
            ecology_condition="DYNAMIC_SIGNAL", resistance_mode="OVERCOMEABLE",
        ), tmp_path / "u4182"
    )
    assert update4182[:8] == [
        sys.executable, str(ROOT / "experiments" / "run_update4182_dynamic_ecology.py"),
        "--ticks", "1000", "--seed", "17", "--condition", "DYNAMIC_SIGNAL",
    ]
    assert "--jsonl" in update4182 and "--archon-jsonl" in update4182


def test_real_run_projects_canonical_telemetry(tmp_path: Path) -> None:
    psychology = tmp_path / "psychology.jsonl"
    bridge = tmp_path / "bridge.jsonl"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "observer_launcher.py"),
            "--world",
            "obstacle-value",
            "--mechanism",
            "psyche-v03",
            "--ticks",
            "3",
            "--seed",
            "17",
            "--no-signals",
            "--jsonl",
            str(psychology),
            "--archon-jsonl",
            str(bridge),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0

    projector = PsychologyTelemetryProjector()
    for line in psychology.read_text(encoding="utf-8").splitlines():
        projector.apply(json.loads(line))

    assert projector.view.completed is True
    assert len(projector.view.ticks) == 3
    assert projector.view.run_config["standalone_observer"] is True
    assert bridge.is_file()


def test_real_bounded_contextual_run_projects_memory_layers(tmp_path: Path) -> None:
    psychology = tmp_path / "bounded.jsonl"
    bridge = tmp_path / "bounded-bridge.jsonl"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "observer_launcher.py"),
            "--world",
            "contextual-objects",
            "--mechanism",
            "bounded-compressed",
            "--ticks",
            "8",
            "--seed",
            "17",
            "--no-signals",
            "--jsonl",
            str(psychology),
            "--archon-jsonl",
            str(bridge),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    projector = PsychologyTelemetryProjector()
    for line in psychology.read_text(encoding="utf-8").splitlines():
        projector.apply(json.loads(line))
    tick = projector.view.latest
    assert tick is not None
    assert tick.memory_mode == "COMPRESSED"
    assert tick.memory_capacity == 64
    assert tick.memory_episode_count > 0
    assert tick.retrieval["total_candidates_inspected"] <= 12
    assert isinstance(tick.memory_events, tuple)
    assert tick.selection_reason.startswith("BOUNDED_")
    assert projector.view.run_config["bounded_cognition"] is True
