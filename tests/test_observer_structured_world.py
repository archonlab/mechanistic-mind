"""Observer EXPERIMENT UI: STRUCTURED_WORLD_EXPERIMENTAL apply path."""
from __future__ import annotations

from pathlib import Path

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_STRUCTURED_TERRAIN,
    ECOLOGY_STRUCTURED_WORLD,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

ROOT = Path(__file__).resolve().parents[1]
APP_TSX = ROOT / "web" / "psy-observer" / "src" / "App.tsx"


def test_observer_ui_exposes_structured_world_button():
    """Button next to Structured Terrain posts the real preset id (no frontend config dup)."""
    text = APP_TSX.read_text(encoding="utf-8")
    assert "STRUCTURED_WORLD_EXPERIMENTAL" in text
    assert ">Structured World</button>" in text or "Structured World</button>" in text
    assert "STRUCTURED_TERRAIN_EXPERIMENTAL" in text
    # Apply path still uses ecology_preset state — not a duplicated ambient/terrain blob.
    assert "ecology_preset: ecologyPreset" in text


def test_apply_structured_world_enables_terrain_and_ambient_gt():
    s = ObserverSession(SessionConfig(seed=0))
    frame = s.apply_experiment({
        "seed": 17,
        "ecology_preset": "STRUCTURED_WORLD_EXPERIMENTAL",
        "cognition_enabled": False,
        "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
    })
    rt = s.runtime
    assert rt.config.ecology_preset == ECOLOGY_STRUCTURED_WORLD
    assert rt.config.planet.terrain.enabled is True
    assert rt.config.planet.ambient.enabled is True
    assert rt.world.terrain_potential is not None
    assert rt.world.ambient_fx is not None

    gt = (frame.get("experiment") or {}).get("observer_ground_truth") or {}
    terr = gt.get("terrain") or {}
    amb = gt.get("ambient") or {}
    assert terr.get("enabled") is True
    assert amb.get("enabled") is True
    assert terr.get("terrain_seed") == rt.world.terrain_meta["terrain_seed"]
    assert terr.get("checksum") == rt.world.terrain_meta["checksum"]
    assert amb.get("ambient_seed") == rt.world.ambient_meta["ambient_seed"]
    assert amb.get("checksum") == rt.world.ambient_meta["checksum"]
    assert terr.get("checksum")
    assert amb.get("checksum")
    # Distinct physical streams
    assert terr.get("checksum") != amb.get("checksum")


def test_structured_terrain_preset_still_ambient_off():
    s = ObserverSession(SessionConfig(seed=0))
    frame = s.apply_experiment({
        "seed": 17,
        "ecology_preset": ECOLOGY_STRUCTURED_TERRAIN,
        "cognition_enabled": False,
        "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
    })
    assert s.runtime.config.ecology_preset == ECOLOGY_STRUCTURED_TERRAIN
    assert s.runtime.config.planet.terrain.enabled is True
    assert s.runtime.config.planet.ambient.enabled is False
    gt = (frame.get("experiment") or {}).get("observer_ground_truth") or {}
    assert (gt.get("terrain") or {}).get("enabled") is True
    assert (gt.get("ambient") or {}).get("enabled") is False
