"""Command-line entry point for the standalone Psychology Observer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .app import PsychologyObserverApp
from .controller import PsychologyObserverController, SubprocessRunner
from .theme import ThemeMode


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def headless_contract(project_root: Path = PROJECT_ROOT) -> dict[str, object]:
    """Describe the self-contained UI contract without creating a window."""
    return {
        "application": "Mechanistic Mind Psychology Observer",
        "version": "0.4.0",
        "standalone": True,
        "map_camera": ["zoom", "pan", "fit", "follow-agent"],
        "resizable_panels": ["left", "causal-timeline"],
        "selection_layers": ["OBJECTIVE", "PERCEIVED", "LEARNED"],
        "object_interactions": ["FREE", "CARRIED", "PUSHED", "DROPPED"],
        "contextual_memory_architectures": [
            "BOUNDED_COMPRESSED",
            "BOUNDED_RAW",
            "BOUNDED_FORGETFUL",
            "LEGACY_PSYCHE_V03",
            "EXPERIENCE_GATED_V05",
            "ADULT_FROM_TICK_0_V05",
            "DEVELOPMENTAL_V05",
        ],
        "world_dynamics": [
            "STATIC_WORLD",
            "DYNAMIC_WORLD",
        ],
        "observer_panels": [
            "cognitive_depth",
            "autonomous_world",
            "perception",
            "activity_recovery",
        ],
        "perception_modes": ["CONTACT_ONLY", "MULTI_CHANNEL"],
        "cue_modes": ["LEGACY_CUE_ONLY", "PERCEPTUAL_CUE_ENABLED"],
        "observer_panels_extra": ["cue_retrieval", "physical_world", "external_material_boundary"],
        "view_modes": ["organism", "physical_world"],
        "user_modes": ["Current MM", "Legacy Experiments"],
        "planet_field_layers": ["M0", "M1", "M2", "Temperature", "Flow", "Wave"],
        "mm_obs1_read_only": True,
        "legacy_mode_default": False,
        "canonical_current_runtime": "PhysicalSystemRuntime",
        "no_canonical_current_organism_runtime": False,
        "current_agent": "runtime.body + runtime.internal",
        "organism_view_is_legacy": True,
        "current_launch_depends_on_legacy_mode": False,
        "legacy_start_run_requires_mode": True,
        "neutral_legacy_status": "NO LEGACY EXPERIMENT ACTIVE",
        "recovery_dynamics": ["off", "on"],
        "worlds": [
            "organism",
            "obstacle-value",
            "persistent-targets",
            "contextual-objects",
            "object-manipulation",
        ],
        "canonical_input": "psychology_observer.jsonl",
        "compatibility_output": "archon_bridge.jsonl",
        "project_root": str(project_root),
        "launcher_exists": (project_root / "observer_launcher.py").is_file(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mechanistic Mind Psychology Observer 0.4.0"
    )
    parser.add_argument(
        "--theme",
        choices=tuple(item.value for item in ThemeMode),
        default=ThemeMode.SYSTEM.value,
    )
    parser.add_argument("--headless-check", action="store_true")
    parser.add_argument("--auto-close-ms", type=int)
    args = parser.parse_args(argv)

    if args.headless_check:
        print(json.dumps(headless_contract(), indent=2, sort_keys=True))
        return 0

    if not (PROJECT_ROOT / "observer_launcher.py").is_file():
        parser.error("observer_launcher.py is missing from Mechanistic Mind")

    import tkinter as tk

    root = tk.Tk()
    controller = PsychologyObserverController(
        mechanistic_mind_root=PROJECT_ROOT,
        process_runner=SubprocessRunner(),
    )
    app = PsychologyObserverApp(
        root,
        controller,
        initial_theme=ThemeMode(args.theme),
    )
    if args.auto_close_ms is not None:
        root.after(max(1, args.auto_close_ms), app.close)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
