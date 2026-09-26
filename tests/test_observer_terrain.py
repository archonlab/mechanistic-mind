"""Observer wiring for STRUCTURED_TERRAIN_EXPERIMENTAL (no physics retune)."""
from __future__ import annotations

import numpy as np

from mechanistic_mind.physical_system.ecology_presets import (
    DEFAULT_ECOLOGY_PRESET,
    ECOLOGY_STRUCTURED_TERRAIN,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.ui.psy_observer_web.serialize import (
    discover_world_fields,
    world_frame,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _terrain_payload(*, seed: int = 17, terrain_seed=None, ecology=ECOLOGY_STRUCTURED_TERRAIN):
    payload = {
        "seed": seed,
        "ecology_preset": ecology,
        "cognition_enabled": False,
        "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
    }
    if terrain_seed is not None:
        payload["terrain_seed"] = int(terrain_seed)
        payload["world"]["terrain_seed"] = int(terrain_seed)
    return payload


def test_apply_structured_terrain_enables_runtime_terrain():
    s = ObserverSession(SessionConfig(seed=0))
    frame = s.apply_experiment(_terrain_payload(seed=17))
    rt = s.runtime
    assert rt.config.ecology_preset == ECOLOGY_STRUCTURED_TERRAIN
    assert rt.config.planet.terrain.enabled is True
    assert rt.world.terrain_potential is not None
    assert rt.world.terrain_drag is not None
    gt = (frame.get("experiment") or {}).get("observer_ground_truth") or {}
    terr = gt.get("terrain") or {}
    assert terr.get("enabled") is True
    assert terr.get("mode")
    assert terr.get("experiment_seed") == 17
    assert terr.get("terrain_seed") == rt.world.terrain_meta["terrain_seed"]
    assert terr.get("generator_version") == rt.world.terrain_meta["generator_version"]
    assert terr.get("checksum") == rt.world.terrain_meta["checksum"]
    assert terr.get("potential_min") is not None
    assert terr.get("potential_max") is not None
    assert terr.get("drag_min") is not None
    assert terr.get("drag_max") is not None
    assert terr.get("gradient_mag_min") is not None
    assert terr.get("gradient_mag_max") is not None


def test_seed_17_checksum_stable_via_observer_apply():
    s = ObserverSession(SessionConfig(seed=0))
    s.apply_experiment(_terrain_payload(seed=17))
    meta_a = dict(s.runtime.world.terrain_meta)
    pot_a = s.runtime.world.terrain_potential.copy()
    s.apply_experiment(_terrain_payload(seed=17))
    assert s.runtime.world.terrain_meta["checksum"] == meta_a["checksum"]
    assert s.runtime.world.terrain_meta["terrain_seed"] == meta_a["terrain_seed"]
    assert np.allclose(pot_a, s.runtime.world.terrain_potential)


def test_changing_experiment_seed_changes_terrain():
    s = ObserverSession(SessionConfig(seed=0))
    s.apply_experiment(_terrain_payload(seed=17))
    cs17 = s.runtime.world.terrain_meta["checksum"]
    pot17 = s.runtime.world.terrain_potential.copy()
    s.apply_experiment(_terrain_payload(seed=18))
    assert s.runtime.world.terrain_meta["checksum"] != cs17
    assert not np.allclose(pot17, s.runtime.world.terrain_potential)


def test_explicit_terrain_seed_override_via_apply():
    s = ObserverSession(SessionConfig(seed=0))
    s.apply_experiment(_terrain_payload(seed=99, terrain_seed=17))
    assert s.runtime.world.terrain_meta["terrain_seed"] == 17
    assert s.runtime.world.terrain_meta["terrain_seed_source"] == "override"
    pot = s.runtime.world.terrain_potential.copy()
    cs = s.runtime.world.terrain_meta["checksum"]
    s.apply_experiment(_terrain_payload(seed=12345, terrain_seed=17))
    assert s.runtime.world.terrain_meta["terrain_seed"] == 17
    assert np.allclose(pot, s.runtime.world.terrain_potential)
    assert s.runtime.world.terrain_meta["checksum"] == cs


def test_climate_stepping_does_not_regenerate_terrain():
    s = ObserverSession(SessionConfig(seed=0))
    s.apply_experiment(_terrain_payload(seed=17))
    pot0 = s.runtime.world.terrain_potential.copy()
    cs0 = s.runtime.world.terrain_meta["checksum"]
    for _ in range(60):
        s.runtime.step()
    assert np.allclose(pot0, s.runtime.world.terrain_potential)
    assert s.runtime.world.terrain_meta["checksum"] == cs0


def test_reset_unchanged_seed_reproduces_terrain():
    s = ObserverSession(SessionConfig(seed=0))
    s.apply_experiment(_terrain_payload(seed=17))
    snap = (
        s.runtime.world.terrain_meta["checksum"],
        s.runtime.world.terrain_potential.copy(),
        s.runtime.world.terrain_drag.copy(),
    )
    for _ in range(20):
        s.runtime.step()
    s.apply_experiment(_terrain_payload(seed=17))
    assert s.runtime.world.terrain_meta["checksum"] == snap[0]
    assert np.allclose(snap[1], s.runtime.world.terrain_potential)
    assert np.allclose(snap[2], s.runtime.world.terrain_drag)


def test_baseline_presets_have_no_terrain_unless_configured():
    s = ObserverSession(SessionConfig(seed=0))
    for eco in (
        DEFAULT_ECOLOGY_PRESET,
        "CURRENT_LEGACY",
        "GENTLE_FREE_MOVEMENT",
        "BASELINE_A_STATIC_PATCHES",
        "BASELINE_B_MIGRATING_RESOURCES",
        "BASELINE_C_CHANGING_LANDSCAPE",
    ):
        s.apply_experiment(_terrain_payload(seed=17, ecology=eco))
        te = getattr(s.runtime.config.planet, "terrain", None)
        enabled = bool(getattr(te, "enabled", False)) if te is not None else False
        assert enabled is False, eco
        assert s.runtime.world.terrain_potential is None, eco
        gt = (s.current_frame().get("experiment") or {}).get("observer_ground_truth") or {}
        assert (gt.get("terrain") or {}).get("enabled") is False, eco


def test_world_frame_exposes_terrain_scalars_as_observer_gt():
    s = ObserverSession(SessionConfig(seed=0))
    s.apply_experiment(_terrain_payload(seed=17))
    wf = world_frame(s.runtime, detail="compact")
    scalars = wf.get("scalars") or {}
    assert "terrain_potential" in scalars
    assert "terrain_drag" in scalars
    assert "terrain_grad_mag" in scalars
    ids = {f["id"]: f for f in discover_world_fields(s.runtime)}
    assert ids["terrain_potential"].get("observer_ground_truth") is True
    assert ids["terrain_drag"].get("observer_ground_truth") is True
    assert ids["terrain_grad_mag"].get("observer_ground_truth") is True


def test_cognition_inputs_have_no_terrain_ground_truth():
    s = ObserverSession(SessionConfig(seed=0))
    s.apply_experiment({**_terrain_payload(seed=17), "cognition_enabled": True})
    obs = s.runtime.agent_observation()
    hits = audit_cognition_payload(obs)
    assert hits == []
    blob = repr(obs)
    assert "terrain_potential" not in blob
    assert "terrain_drag" not in blob
    assert "terrain_grad" not in blob
    assert "terrain_seed" not in blob
    # Observer frame may carry GT; agent observation must not.
    frame = s.current_frame()
    assert "terrain" in ((frame.get("experiment") or {}).get("observer_ground_truth") or {})
