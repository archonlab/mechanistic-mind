"""Tiktaalik baseline ecology calibration — diagnostic tests.

Documents WORLD_RESOURCE_FIELD_EMPTY on CURRENT, and that co-located A+B
conversion recovers work without passive_reservoir_trickle.
Does not permanently change factory defaults.
"""
from __future__ import annotations

import numpy as np
import pytest

from mechanistic_mind.physical_system.baseline_ecology_presets import (
    ECOLOGY_A_STATIC_PATCHES,
    ECOLOGY_CLIMATE_DEFAULT,
    make_baseline_ecology_config,
    make_current_uninhabitable_reference,
    seed_static_patches,
)
from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.motor_work import scale_positive_ke
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime


def test_current_ecology_env_resource_fields_empty():
    """Failing substrate condition: complementary ON, climate OFF → no env stock."""
    cfg = make_current_uninhabitable_reference(trickle=0.0)
    assert cfg.complementary_resources.enabled
    assert cfg.complementary_resources.conversion_enabled
    assert not cfg.planet.climate_ecology.enabled
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert float(np.sum(rt.world.R_A)) == pytest.approx(0.0)
    assert float(np.sum(rt.world.R_B)) == pytest.approx(0.0)
    rt.body.mechanical_work_reservoir = 0.0
    rt.step_forced_action("WAIT")
    cl = rt.last_complementary_ledger or {}
    assert float(cl.get("work_credited") or 0.0) == pytest.approx(0.0)


def test_colocated_AB_converts_without_trickle():
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.deformation_work.passive_reservoir_trickle = 0.0
    cfg.deformation_work.reservoir_init = 0.0
    cfg.planet.climate_ecology.enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    rt.world.R_A[:] = 0.0
    rt.world.R_B[:] = 0.0
    iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
    place_source_AB(rt.world, iy, ix, A=2.0, B=2.0)
    rt.step_forced_action("WAIT")
    cl = rt.last_complementary_ledger or {}
    assert float(cl.get("work_credited") or 0.0) > 1e-6
    assert float(rt.body.mechanical_work_reservoir) > 1e-6


def test_A_only_does_not_convert():
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.deformation_work.passive_reservoir_trickle = 0.0
    cfg.deformation_work.reservoir_init = 0.0
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    rt.world.R_A[:] = 0.0
    rt.world.R_B[:] = 0.0
    iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
    place_source_AB(rt.world, iy, ix, A=2.0, B=0.0)
    rt.step_forced_action("WAIT")
    assert float((rt.last_complementary_ledger or {}).get("work_credited") or 0.0) == pytest.approx(0.0)
    assert (rt.last_complementary_ledger or {}).get("limiting_resource") == "B"


def test_empty_reservoir_motor_authority_collapsed():
    assert scale_positive_ke(1.0, 0.0, 0.0, 0.2, 0.0, 0.0) == pytest.approx(0.0)


def test_zero_work_cannot_reach_distant_resource_without_trickle():
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.body.flow_coupling = 0.0
    cfg.deformation_work.passive_reservoir_trickle = 0.0
    cfg.deformation_work.reservoir_init = 0.0
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    rt.body.vx = rt.body.vy = 0.0
    rt.world.R_A[:] = 0.0
    rt.world.R_B[:] = 0.0
    iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
    place_source_AB(rt.world, iy, (ix + 3) % rt.config.planet.width, A=2.0, B=2.0)
    x0 = float(rt.body.x)
    for _ in range(25):
        rt.step_forced_action("MOVE:E")
    assert abs(float(rt.body.x) - x0) < 1e-6
    assert float(rt.body.mechanical_work_reservoir) == pytest.approx(0.0)


def test_climate_default_has_env_stock_and_recovers():
    cfg = make_baseline_ecology_config(ECOLOGY_CLIMATE_DEFAULT, trickle=0.0)
    assert cfg.planet.climate_ecology.enabled
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert float(np.sum(rt.world.R_A)) > 1.0
    assert float(np.sum(rt.world.R_B)) > 1.0
    rt.body.mechanical_work_reservoir = 0.0
    prod = np.asarray(rt.world.R_A) * np.asarray(rt.world.R_B)
    iy, ix = divmod(int(prod.argmax()), prod.shape[1])
    rt.body.x = float(ix) + 0.5
    rt.body.y = float(iy) + 0.5
    credits = []
    for _ in range(15):
        rt.step_forced_action("WAIT")
        credits.append(float((rt.last_complementary_ledger or {}).get("work_credited") or 0.0))
    assert sum(credits) > 1e-4
    assert float(rt.body.mechanical_work_reservoir) > 1e-4


def test_static_patches_seed_colocated_AB():
    cfg = make_baseline_ecology_config(ECOLOGY_A_STATIC_PATCHES, trickle=0.0)
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    centers = seed_static_patches(rt.world, seed=17, spec=getattr(cfg, "_baseline_patch_spec", None))
    assert len(centers) >= 3
    both = (rt.world.R_A > 0.1) & (rt.world.R_B > 0.1)
    assert int(both.sum()) >= 3


def test_trickle_subsidizes_wait_without_resources():
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.deformation_work.passive_reservoir_trickle = 0.002
    cfg.deformation_work.reservoir_init = 0.0
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    rt.world.R_A[:] = 0.0
    rt.world.R_B[:] = 0.0
    for _ in range(100):
        rt.step_forced_action("WAIT")
    assert float(rt.body.mechanical_work_reservoir) == pytest.approx(0.2, abs=0.05)


def test_audit_helpers_importable():
    from experiments.run_tiktaalik_baseline_ecology_calibration import (
        audit_wiring,
        resource_to_work_trace,
    )

    a = audit_wiring()
    assert a["first_edge_hypothesis"] == "WORLD_RESOURCE_FIELD_EMPTY"
    t = resource_to_work_trace(trickle=0.0, ticks=4, seed=17)
    assert t["first_edge_where_flow_stops"]["edge"] == "ENVIRONMENT_RESOURCE_FIELD_EMPTY"
    assert t["conditions"]["D_RA_RB"]["total_conversion"] > 0.0
