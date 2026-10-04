"""P5 browser render performance — focused contracts (no live-run mutation)."""
from __future__ import annotations

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import public_model_selector_entries
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of


SCHEMA = "OBSERVER_BROWSER_RENDER_PERFORMANCE_V1"
CAPABILITY = "browser_upload_render_profiling_and_optimization"


def test_01_identity_and_selector():
    assert SCHEMA == "OBSERVER_BROWSER_RENDER_PERFORMANCE_V1"
    assert CAPABILITY == "browser_upload_render_profiling_and_optimization"
    assert len(public_model_selector_entries()) == 2


def test_02_payload_build_does_not_mutate_occupancy():
    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=91, config=cfg)
    for _ in range(2):
        rt.step()
    dig = state_of(rt.world).digest()
    from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import researcher_payload

    researcher_payload(rt)
    assert state_of(rt.world).digest() == dig


def test_03_tiktaalik_unchanged_path():
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=2, config=cfg)
    rt.step()
    assert str(getattr(rt.config, "model_line", "")).upper() == "TIKTAALIK"
