"""Standalone process controller for the Mechanistic Mind observer UI."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import queue
import subprocess
import threading
import time
import uuid
import os
import signal
import sys
from typing import Any, Protocol, Sequence

from .model import (
    PsychologyRunView,
    PsychologyTelemetryProjector,
    read_jsonl_since,
)


WORLD_MODES = (
    "organism",
    "obstacle-value",
    "persistent-targets",
    "contextual-objects",
    "object-manipulation",
)
RESOURCE_LAYOUTS = ("distributed", "near", "far")
OBSTACLE_CONDITIONS = ("HAZARD", "SHAM_CUE", "NO_OBSTACLE", "REMOVAL")
PERSISTENT_CONDITIONS = ("WORKING", "BROKEN", "DEAD", "REVIVAL")
MEMORY_ARCHITECTURES = (
    "BOUNDED_COMPRESSED",
    "BOUNDED_RAW",
    "BOUNDED_FORGETFUL",
    "LEGACY_PSYCHE_V03",
    "EXPERIENCE_GATED_V05",
    "ADULT_FROM_TICK_0_V05",
    "DEVELOPMENTAL_V05",
)
WORLD_DYNAMICS = (
    "STATIC_WORLD",
    "DYNAMIC_WORLD",
)
CUE_MODES = ("LEGACY_CUE_ONLY", "PERCEPTUAL_CUE_ENABLED")
PERCEPTION_MODES = (
    "CONTACT_ONLY",
    "MULTI_CHANNEL",
)


class ProcessRunner(Protocol):
    """Small process boundary used by the controller and its tests."""

    def start(
        self, command: Sequence[str], **kwargs: Any
    ) -> subprocess.Popen[str]: ...
    def stream_and_wait(
        self, process: subprocess.Popen[str], output: queue.Queue[Any]
    ) -> int: ...
    def terminate(self, process: subprocess.Popen[str]) -> None: ...


class SubprocessRunner:
    """Default local process implementation; has no ARCHON dependency."""

    def start(
        self, command: Sequence[str], **kwargs: Any
    ) -> subprocess.Popen[str]:
        return subprocess.Popen(command, **kwargs)

    def stream_and_wait(
        self, process: subprocess.Popen[str], output: queue.Queue[Any]
    ) -> int:
        if process.stdout is not None:
            for line in process.stdout:
                output.put(line)
        return process.wait()

    def terminate(self, process: subprocess.Popen[str]) -> None:
        os.killpg(process.pid, signal.SIGTERM)


@dataclass(frozen=True, slots=True)
class PsychologyLaunchSpec:
    ticks: int = 90
    seed: int = 17
    world: str = "organism"
    resource_layout: str = "distributed"
    random_event_rate: float = 0.0
    obstacle_condition: str = "HAZARD"
    persistent_condition: str = "BROKEN"
    tick_delay_ms: int = 120
    memory_architecture: str = "BOUNDED_COMPRESSED"
    world_dynamics: str = "STATIC_WORLD"
    perception_mode: str = "CONTACT_ONLY"
    cue_mode: str = "LEGACY_CUE_ONLY"
    recovery_dynamics: bool = False
    developmental_subsidy_ticks: int = 0
    telemetry_mode: str = "FULL"
    # UI routing only. Empty/default preserves the ordinary live Observer run.
    experiment_preset: str = ""
    ecology_condition: str = "DYNAMIC_SIGNAL"
    resistance_mode: str = "OVERCOMEABLE"


    def validate(self) -> None:
        if self.ticks < 1:
            raise ValueError("ticks must be >= 1")
        if self.world not in WORLD_MODES:
            raise ValueError(f"Unsupported world: {self.world!r}")
        if self.resource_layout not in RESOURCE_LAYOUTS:
            raise ValueError(
                f"Unsupported resource layout: {self.resource_layout!r}"
            )
        if not (0.0 <= self.random_event_rate <= 1.0):
            raise ValueError("random_event_rate must be in [0, 1]")
        if self.obstacle_condition not in OBSTACLE_CONDITIONS:
            raise ValueError(
                f"Unsupported obstacle condition: {self.obstacle_condition!r}"
            )
        if self.persistent_condition not in PERSISTENT_CONDITIONS:
            raise ValueError(
                f"Unsupported persistent condition: {self.persistent_condition!r}"
            )
        if self.tick_delay_ms < 0:
            raise ValueError("tick_delay_ms must be >= 0")
        if self.memory_architecture not in MEMORY_ARCHITECTURES:
            raise ValueError(
                "Unsupported memory architecture: "
                f"{self.memory_architecture!r}"
            )
        if self.world_dynamics not in WORLD_DYNAMICS:
            raise ValueError(
                f"Unsupported world dynamics: {self.world_dynamics!r}"
            )
        if self.perception_mode not in PERCEPTION_MODES:
            raise ValueError(
                f"Unsupported perception mode: {self.perception_mode!r}"
            )
        if self.cue_mode not in CUE_MODES:
            raise ValueError(
                f"Unsupported cue mode: {self.cue_mode!r}"
            )
        if self.ecology_condition not in {"POOR", "DYNAMIC_SUSTAINING", "DYNAMIC_SIGNAL", "DECORRELATED_SIGNAL", "UNSIGNALED", "INERT_SIGNAL"}:
            raise ValueError(f"Unsupported ecology condition: {self.ecology_condition!r}")
        if self.resistance_mode not in {"OFF", "LOW", "OVERCOMEABLE", "IMPOSSIBLE", "DYNAMIC", "STRUCTURED", "RANDOM_CONTROL"}:
            raise ValueError(f"Unsupported resistance mode: {self.resistance_mode!r}")


class PsychologyObserverController:
    def __init__(
        self,
        *,
        mechanistic_mind_root: Path,
        process_runner: ProcessRunner,
        results_root: Path | None = None,
    ) -> None:
        self.mechanistic_mind_root = (
            Path(mechanistic_mind_root).expanduser().resolve()
        )
        self.results_root = (
            Path(results_root).expanduser().resolve()
            if results_root is not None
            else self.mechanistic_mind_root
            / "results"
            / "psychology_observer"
        )
        self.process_runner = process_runner
        self.output: queue.Queue[str] = queue.Queue()
        self.process: subprocess.Popen[str] | None = None
        self.state = "IDLE"
        self.launch_id: str | None = None
        self.run_dir: Path | None = None
        self.psychology_jsonl: Path | None = None
        self.archon_bridge_jsonl: Path | None = None
        self.exit_code: int | None = None
        self.error: str | None = None
        self.projector = PsychologyTelemetryProjector()
        self._offset = 0

    @property
    def is_active(self) -> bool:
        return self.state in {"STARTING", "RUNNING", "STOPPING"}

    @property
    def view(self) -> PsychologyRunView:
        return self.projector.view

    def build_command(
        self,
        spec: PsychologyLaunchSpec,
        run_dir: Path,
    ) -> list[str]:
        # Legacy preset branches import sys locally; bind those imports to the
        # existing module symbol so early-return presets can use it safely.
        global sys
        spec.validate()
        if spec.experiment_preset == "Integrated Psyche v1":
            runner = self.mechanistic_mind_root / "experiments" / "run_integrated_psyche_v1.py"
            return [sys.executable, str(runner), "--seed", str(spec.seed), "--ticks", str(spec.ticks),
                    "--jsonl", str(run_dir / "psychology_observer.jsonl")]
        if spec.experiment_preset == "4.41 Acquired Internal Dynamics":
            runner=Path("experiments/run_update441_acquired_internal_dynamics.py")
            if not runner.exists(): raise FileNotFoundError(str(runner))
            return [sys.executable,str(runner),"--seeds",str(spec.seed),"--trials","36"]
        if spec.experiment_preset == "4.40 Endogenous Predictive Signaling":
            runner = Path("experiments/run_update440_predictive_reinstatement.py")
            if not runner.exists(): raise FileNotFoundError(str(runner))
            return [sys.executable,str(runner),"--seeds",str(spec.seed),"--exposures","36"]
        if spec.experiment_preset == "4.39 Sensorimotor Dynamics":
            runner = Path("experiments/run_update439_sensorimotor_dynamics.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--exposures", "36"]
        if spec.experiment_preset == "4.37 Contingent Physical Futures":
            runner = Path("experiments/run_update437_multimodal_prospective_propagation.py")
        elif spec.experiment_preset == "4.38 Psyche Incubation":
            runner = Path("experiments/run_update438_psyche_incubation.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--dose", "36"]
        if spec.experiment_preset == "4.36 Predictive Representation Sufficiency":
            runner = Path("experiments/run_update436_predictive_representation_sufficiency.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "40"]
        if spec.experiment_preset == "4.35 Predictive Structure Selection":
            runner = Path("experiments/run_update435_predictive_structure_selection.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "40"]
        if spec.experiment_preset == "4.34 Multimodal Consequence Learning":
            runner = Path("experiments/run_update434_multimodal_consequence_learning.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "40"]
        if spec.experiment_preset == "4.33 Conditional Prospection":
            runner = Path("experiments/run_update433_conditional_prospection.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "40"]
        if spec.experiment_preset == "4.32 Learning-Mediated Futures":
            runner = Path("experiments/run_update432_learning_mediated_futures.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "40"]
        if spec.experiment_preset == "4.31 Evidence-Producing Physical Action":
            runner = Path("experiments/run_update431_evidence_producing_action.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "30"]
        if spec.experiment_preset == "4.30 Unavoidable State Transition":
            runner = Path("experiments/run_update430_unavoidable_state_transition.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "5"]
        if spec.experiment_preset == "4.29 Predictive Reliability":
            runner = Path("experiments/run_update429_predictive_reliability.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "100"]
        if spec.experiment_preset == "4.28 Predictive Scenario Competition":
            runner = Path("experiments/run_update428_predictive_scenario_competition.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "50"]
        if spec.experiment_preset == "4.27 Predictive Generalization":
            runner = Path("experiments/run_update427_predictive_generalization.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "8"]
        if spec.experiment_preset == "4.26 Prospective Consequence Influence":
            runner = Path("experiments/run_update426_prospective_consequence_influence.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "40"]
        if spec.experiment_preset == "4.25 Instrumental Observation":
            runner = Path("experiments/run_update425_instrumental_observation.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "80"]
        if spec.experiment_preset == "4.24 Endogenous Temporal Reference":
            runner = Path("experiments/run_update424_endogenous_temporal.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "60"]
        if spec.experiment_preset == "4.23 Prospective Trajectory Composition":
            runner = Path("experiments/run_update423_prospective_composition.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "40"]
        if spec.experiment_preset == "4.22 Multi-Scale Predictive Organization":
            runner = Path("experiments/run_update422_multiscale_prediction.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seeds", str(spec.seed), "--ticks", "400"]
        if spec.experiment_preset == "4.21 Predictive Compression":
            runner = Path("experiments/run_update421_predictive_compression.py")
            if not runner.exists():
                raise FileNotFoundError(str(runner))
            import sys
            return [sys.executable, str(runner), "--seed", str(spec.seed)]
        if spec.experiment_preset == "4.20 Hierarchical Body Prediction":
            runner = Path("experiments/run_update420_hierarchical_body_prediction.py")
            if not runner.exists():
                raise FileNotFoundError("Update 4.20 experiment runner not found: " + str(runner))
            import sys
            return [sys.executable, str(runner), "--seed", str(spec.seed)]
        if spec.experiment_preset == "4.19 Context Formation":
            runner = Path("experiments/run_update419_context_formation.py")
            if not runner.exists():
                raise FileNotFoundError("Update 4.19 experiment runner not found: " + str(runner))
            import sys
            return [sys.executable, str(runner), "--seed", str(spec.seed)]
        if spec.experiment_preset == "4.18.2 Dynamic Sustaining Ecology":
            runner = self.mechanistic_mind_root / "experiments" / "run_update4182_dynamic_ecology.py"
            if not runner.is_file():
                raise FileNotFoundError("Update 4.18.2 experiment runner not found: " + str(runner))
            return [sys.executable, str(runner), "--ticks", str(spec.ticks), "--seed", str(spec.seed),
                    "--condition", spec.ecology_condition, "--resistance-mode", spec.resistance_mode,
                    "--jsonl", str(run_dir / "psychology_observer.jsonl"),
                    "--archon-jsonl", str(run_dir / "archon_bridge.jsonl")]
        if spec.experiment_preset == "4.18.1 Prospective Space Development":
            runner = self.mechanistic_mind_root / "experiments" / "run_update4181_prospective_space_development.py"
            if not runner.is_file():
                raise FileNotFoundError("Update 4.18.1 experiment runner not found: " + str(runner))
            return [sys.executable, str(runner), "--ticks", str(spec.ticks), "--seed", str(spec.seed),
                    "--world-dynamics", {"STATIC_WORLD": "static", "DYNAMIC_WORLD": "dynamic"}[spec.world_dynamics],
                    "--perception-mode", {"CONTACT_ONLY": "contact-only", "MULTI_CHANNEL": "multi-channel"}[spec.perception_mode],
                    "--cue-mode", {"LEGACY_CUE_ONLY": "legacy", "PERCEPTUAL_CUE_ENABLED": "perceptual"}[spec.cue_mode],
                    "--memory-architecture", spec.memory_architecture,
                    "--jsonl", str(run_dir / "psychology_observer.jsonl"),
                    "--archon-jsonl", str(run_dir / "archon_bridge.jsonl")]
        if spec.experiment_preset == "4.18 Composed Future Value":
            runner = self.mechanistic_mind_root / "experiments" / "run_update418_composed_future_value.py"
            if not runner.is_file():
                raise FileNotFoundError("Update 4.18 experiment runner not found: " + str(runner))
            return [sys.executable, str(runner)]
        if spec.experiment_preset == "4.17 Persistent Expectation × Fresh Prediction Conflict":
            runner = self.mechanistic_mind_root / "experiments" / "run_update417_prospective_conflict.py"
            if not runner.is_file():
                raise FileNotFoundError("Update 4.17 experiment runner not found: " + str(runner))
            return [sys.executable, str(runner)]
        launcher = self.mechanistic_mind_root / "observer_launcher.py"
        if not launcher.is_file():
            raise FileNotFoundError(
                "Mechanistic Mind observer launcher not found: "
                + str(launcher)
            )

        psychology_jsonl = run_dir / "psychology_observer.jsonl"
        bridge_jsonl = run_dir / "archon_bridge.jsonl"
        if spec.world == "object-manipulation":
            mechanism = "physical-demo"
        elif spec.world == "contextual-objects":
            mechanism = {
                "BOUNDED_COMPRESSED": "bounded-compressed",
                "BOUNDED_RAW": "bounded-raw",
                "BOUNDED_FORGETFUL": "bounded-forgetful",
                "LEGACY_PSYCHE_V03": "psyche-v03",
                "EXPERIENCE_GATED_V05": "psyche-v05-experience-gated",
                "ADULT_FROM_TICK_0_V05": "psyche-v05-adult",
                "DEVELOPMENTAL_V05": "psyche-v05-developmental",
            }[spec.memory_architecture]
        else:
            mechanism = "psyche-v03"
        command = [
            sys.executable,
            str(launcher),
            "--world",
            spec.world,
            "--mechanism",
            mechanism,
            "--ticks",
            str(spec.ticks),
            "--seed",
            str(spec.seed),
            "--tick-delay-ms",
            str(spec.tick_delay_ms),
        ]
        if spec.world == "obstacle-value":
            command.extend([
                "--obstacle-condition",
                spec.obstacle_condition,
            ])
        elif spec.world == "organism":
            command.extend([
                "--resource-layout",
                spec.resource_layout,
                "--random-event-rate",
                str(spec.random_event_rate),
            ])
        elif spec.world == "persistent-targets":
            command.extend([
                "--persistent-condition",
                spec.persistent_condition,
            ])
        if spec.world == "contextual-objects":
            command.extend([
                "--world-dynamics",
                {
                    "STATIC_WORLD": "static",
                    "DYNAMIC_WORLD": "dynamic",
                }[spec.world_dynamics],
                "--perception-mode",
                {
                    "CONTACT_ONLY": "contact-only",
                    "MULTI_CHANNEL": "multi-channel",
                }[spec.perception_mode],
            ])
            if spec.recovery_dynamics:
                command.append("--recovery-dynamics")
            command.extend([
                "--cue-mode",
                {
                    "LEGACY_CUE_ONLY": "legacy",
                    "PERCEPTUAL_CUE_ENABLED": "perceptual",
                }[spec.cue_mode],
            ])
            if int(spec.developmental_subsidy_ticks) > 0:
                command.extend([
                    "--developmental-subsidy-ticks",
                    str(int(spec.developmental_subsidy_ticks)),
                ])
            if str(spec.telemetry_mode).upper() == "LONG_RUN":
                command.append("--long-run-telemetry")
        command.extend([
            "--jsonl",
            str(psychology_jsonl),
            "--archon-jsonl",
            str(bridge_jsonl),
            "--no-signals",
        ])
        return command

    def resolve_effective_config(
        self,
        spec: PsychologyLaunchSpec,
    ) -> dict[str, object]:
        """What the launcher/simulation will actually receive.

        UI-only fields that are not passed for the selected world are marked
        applied=False with an explicit reason (prerequisite), never silently
        rewritten to a different scientific value.
        """
        spec.validate()
        world = spec.world
        mds_applied = world == "contextual-objects"
        layout_applied = world == "organism"
        recovery_applied = world == "contextual-objects"
        mds_value = int(spec.developmental_subsidy_ticks) if mds_applied else None
        layout_value = str(spec.resource_layout) if layout_applied else None
        recovery_value = bool(spec.recovery_dynamics) if recovery_applied else None
        # Activity capacity/load dynamics (Update 4.5.1) accumulate when recovery
        # dynamics are enabled on contextual-objects body config.
        if recovery_applied and recovery_value:
            activity_451 = "enabled"
        elif recovery_applied:
            activity_451 = "disabled"
        else:
            activity_451 = "n/a"
        return {
            "world": world,
            "developmental_subsidy_ticks": {
                "value": mds_value,
                "applied": mds_applied,
                "prerequisite": None if mds_applied else "requires WORLD=contextual-objects",
                "widget_value": int(spec.developmental_subsidy_ticks),
            },
            "resource_layout": {
                "value": layout_value,
                "applied": layout_applied,
                "prerequisite": None if layout_applied else "requires WORLD=organism",
                "widget_value": str(spec.resource_layout),
            },
            "recovery_dynamics": {
                "value": recovery_value,
                "applied": recovery_applied,
                "prerequisite": None if recovery_applied else "requires WORLD=contextual-objects",
                "widget_value": bool(spec.recovery_dynamics),
            },
            "activity_physiology_451": activity_451,
            "random_event_rate": {
                "value": float(spec.random_event_rate) if world == "organism" else None,
                "applied": world == "organism",
                "prerequisite": None if world == "organism" else "requires WORLD=organism",
                "widget_value": float(spec.random_event_rate),
            },
        }

    def validate_gui_matches_effective(
        self,
        spec: PsychologyLaunchSpec,
    ) -> None:
        """Raise if a GUI value would not propagate while appearing active.

        Catches mismatches before Start Run: e.g. MDS ticks set but world does
        not receive --developmental-subsidy-ticks; layout shown as if active
        but not passed for non-organism worlds.
        """
        effective = self.resolve_effective_config(spec)
        mds = effective["developmental_subsidy_ticks"]
        assert isinstance(mds, dict)
        if mds["applied"]:
            if int(mds["value"]) != int(mds["widget_value"]):
                raise ValueError(
                    "MDS subsidy ticks widget value does not match effective "
                    f"launch value ({mds['widget_value']!r} vs {mds['value']!r})."
                )
        elif int(mds["widget_value"]) != 0:
            raise ValueError(
                "MDS SUBSIDY TICKS is set to "
                f"{mds['widget_value']}, but it is NOT applied for WORLD="
                f"{spec.world!r}. Prerequisite: {mds['prerequisite']}. "
                "Switch WORLD to contextual-objects, or set MDS to 0."
            )
        layout = effective["resource_layout"]
        assert isinstance(layout, dict)
        if layout["applied"]:
            if str(layout["value"]) != str(layout["widget_value"]):
                raise ValueError(
                    "RESOURCE LAYOUT widget value does not match effective "
                    f"launch value ({layout['widget_value']!r} vs {layout['value']!r})."
                )
        # Layout widget may retain a value while disabled; only error if the
        # caller claims it must apply. Soft check: if world is organism, must match.
        # For non-organism, do not force-clear widget (preserve user choice for switch-back).

        # Command-level verification for applied fields.
        from pathlib import Path as _Path
        import tempfile
        tmp = _Path(tempfile.mkdtemp(prefix="mmpo_cfg_check_"))
        try:
            cmd = self.build_command(spec, tmp)
        finally:
            try:
                tmp.rmdir()
            except OSError:
                pass
        if mds["applied"] and int(mds["widget_value"]) > 0:
            if "--developmental-subsidy-ticks" not in cmd:
                raise ValueError(
                    "MDS subsidy ticks is applied in UI but missing from launch command."
                )
            idx = cmd.index("--developmental-subsidy-ticks")
            if cmd[idx + 1] != str(int(mds["widget_value"])):
                raise ValueError(
                    "MDS subsidy ticks launch command mismatch: "
                    f"expected {mds['widget_value']}, got {cmd[idx + 1]!r}."
                )
        if layout["applied"]:
            if "--resource-layout" not in cmd:
                raise ValueError(
                    "RESOURCE LAYOUT is applied in UI but missing from launch command."
                )
            idx = cmd.index("--resource-layout")
            if cmd[idx + 1] != str(layout["widget_value"]):
                raise ValueError(
                    "RESOURCE LAYOUT launch command mismatch: "
                    f"expected {layout['widget_value']}, got {cmd[idx + 1]!r}."
                )

    def start(self, spec: PsychologyLaunchSpec) -> None:
        spec.validate()
        self.validate_gui_matches_effective(spec)
        if self.is_active:
            raise RuntimeError("A Psychology run is already active.")

        self.launch_id = (
            "MMPO-"
            + time.strftime("%Y%m%d-%H%M%S")
            + "-"
            + uuid.uuid4().hex[:8].upper()
        )
        self.run_dir = (
            self.results_root / self.launch_id
        )
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.psychology_jsonl = self.run_dir / "psychology_observer.jsonl"
        self.archon_bridge_jsonl = self.run_dir / "archon_bridge.jsonl"

        self.projector = PsychologyTelemetryProjector()
        self._offset = 0
        self.exit_code = None
        self.error = None
        self.state = "STARTING"

        command = self.build_command(spec, self.run_dir)
        try:
            process = self.process_runner.start(
                command,
                cwd=str(self.mechanistic_mind_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                shell=False,
                start_new_session=True,
            )
        except Exception as exc:
            self.state = "FAILED"
            self.error = str(exc)
            raise

        self.process = process
        self.state = "RUNNING"
        threading.Thread(
            target=self._stream_worker,
            args=(process,),
            daemon=True,
            name=f"psychology-observer3-{self.launch_id}",
        ).start()

    def _stream_worker(self, process: subprocess.Popen[str]) -> None:
        try:
            code = self.process_runner.stream_and_wait(
                process,
                self.output,
            )
            self.exit_code = int(code)
            self.state = "COMPLETED" if code == 0 else "FAILED"
            if code != 0:
                self.error = f"Mechanistic Mind exited with code {code}"
        except Exception as exc:
            self.state = "FAILED"
            self.error = str(exc)
        finally:
            self.process = None

    def poll_telemetry(self) -> int:
        if self.psychology_jsonl is None:
            return 0
        records, self._offset = read_jsonl_since(
            self.psychology_jsonl,
            self._offset,
        )
        for record in records:
            self.projector.apply(record)
        return len(records)

    def stop(self) -> None:
        process = self.process
        if process is None or not self.is_active:
            return
        self.state = "STOPPING"
        self.process_runner.terminate(process)
