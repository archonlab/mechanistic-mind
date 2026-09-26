"""Promotion regressions: BASELINE_CLIMATE_DEFAULT + trickle=0 + resource→work chain."""
from __future__ import annotations

import numpy as np
import pytest

from mechanistic_mind.model.tiktaalik import is_canonical_tiktaalik, tiktaalik_config
from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.ecology_presets import (
    BODY01_PASSIVE_RESERVOIR_TRICKLE,
    DEFAULT_ECOLOGY_PRESET,
    ECOLOGY_BASELINE,
    ECOLOGY_CURRENT_LEGACY,
    ECOLOGY_GENTLE,
    make_ecology_config,
    normalize_ecology_preset,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime


def test_default_ecology_is_promoted_baseline():
    assert DEFAULT_ECOLOGY_PRESET == ECOLOGY_BASELINE
    assert normalize_ecology_preset(None) == ECOLOGY_BASELINE
    assert float(BODY01_PASSIVE_RESERVOIR_TRICKLE) == pytest.approx(0.0)


def test_gate1_promoted_baseline_has_env_RA_RB():
    cfg = make_ecology_config(ECOLOGY_BASELINE)
    assert cfg.planet.climate_ecology.enabled is True
    assert float(cfg.deformation_work.passive_reservoir_trickle) == pytest.approx(0.0)
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert float(np.sum(rt.world.R_A)) > 1.0
    assert float(np.sum(rt.world.R_B)) > 1.0


def test_gate2_baseline_trickle_zero():
    cfg = make_ecology_config()
    assert cfg.ecology_preset == ECOLOGY_BASELINE
    assert float(cfg.deformation_work.passive_reservoir_trickle) == pytest.approx(0.0)


def test_gate3_no_resource_wait_no_spontaneous_work():
    """No env stock + trickle=0 ⇒ WAIT does not create work (mechanism retained, unused)."""
    cfg = make_ecology_config(ECOLOGY_CURRENT_LEGACY, trickle=0.0)
    cfg.planet.climate_ecology.enabled = False
    cfg.planet.climate_ecology.resources_enabled = False
    cfg.planet.climate_ecology.resource_ecology_A_enabled = False
    cfg.planet.climate_ecology.resource_ecology_B_enabled = False
    rt = PhysicalSystemRuntime(seed=11, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    rt.world.R_A[:] = 0.0
    rt.world.R_B[:] = 0.0
    if getattr(rt.world, "R", None) is not None:
        rt.world.R[:] = 0.0
    n = len(rt.config.body.footprint)
    rt.body.R_A_site = np.zeros(n)
    rt.body.R_B_site = np.zeros(n)
    if getattr(rt.body, "R_site", None) is not None:
        rt.body.R_site = np.zeros(n)
    for _ in range(40):
        rt.step_forced_action("WAIT")
        assert float((rt.last_complementary_ledger or {}).get("work_credited") or 0.0) == pytest.approx(0.0)
        trickle = rt.last_passive_reservoir_trickle or {}
        assert float(trickle.get("credited") or 0.0) == pytest.approx(0.0)
    assert float(rt.body.mechanical_work_reservoir) == pytest.approx(0.0, abs=1e-12)


def test_gate4_colocated_resources_recover_work():
    cfg = make_ecology_config(ECOLOGY_CURRENT_LEGACY, trickle=0.0)
    cfg.planet.flow_enabled = False
    cfg.body.flow_coupling = 0.0
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    rt.world.R_A[:] = 0.0
    rt.world.R_B[:] = 0.0
    iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
    place_source_AB(rt.world, iy, ix, A=2.0, B=2.0)
    w0 = float(rt.body.mechanical_work_reservoir)
    rt.step_forced_action("WAIT")
    assert float(rt.body.mechanical_work_reservoir) > w0
    # Remove contact stock — conversion path must not continue crediting from empty env
    rt.world.R_A[:] = 0.0
    rt.world.R_B[:] = 0.0
    # Drain internal sites so residual conversion exhausts
    n = len(rt.config.body.footprint)
    for _ in range(80):
        rt.step_forced_action("WAIT")
    w_mid = float(rt.body.mechanical_work_reservoir)
    for _ in range(20):
        rt.step_forced_action("WAIT")
    # After sites empty, work should not keep rising via conversion
    assert float(rt.body.mechanical_work_reservoir) <= w_mid + 1e-9


def test_legacy_current_remains_empty_resource_world():
    cfg = make_ecology_config(ECOLOGY_CURRENT_LEGACY)
    assert cfg.ecology_preset == ECOLOGY_CURRENT_LEGACY
    assert cfg.planet.climate_ecology.enabled is False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert float(np.sum(rt.world.R_A)) == pytest.approx(0.0)
    assert float(np.sum(rt.world.R_B)) == pytest.approx(0.0)


def test_current_alias_maps_to_legacy_not_baseline():
    """Old snapshots saying CURRENT must not silently gain climate stock."""
    assert normalize_ecology_preset("CURRENT") == ECOLOGY_CURRENT_LEGACY
    cfg = make_ecology_config("CURRENT")
    assert cfg.ecology_preset == ECOLOGY_CURRENT_LEGACY
    assert cfg.planet.climate_ecology.enabled is False


def test_trickle_control_levels_still_configurable():
    for tr in (0.0, 0.0005, 0.002):
        cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=tr)
        assert float(cfg.deformation_work.passive_reservoir_trickle) == pytest.approx(tr)


def test_tiktaalik_config_uses_promoted_baseline():
    cfg = tiktaalik_config()
    assert cfg.ecology_preset == ECOLOGY_BASELINE
    assert cfg.planet.climate_ecology.enabled is True
    assert float(cfg.deformation_work.passive_reservoir_trickle) == pytest.approx(0.0)
    assert is_canonical_tiktaalik(cfg) is True


def test_gentle_legacy_locomotion_preset_climate_off():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    assert cfg.ecology_preset == ECOLOGY_GENTLE
    assert cfg.planet.climate_ecology.enabled is False
