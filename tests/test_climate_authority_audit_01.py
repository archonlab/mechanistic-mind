"""Tests for CLIMATE_AUTHORITY_AUDIT_01."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.model.tiktaalik import experimental_overrides
from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CALIBRATED_TEMPORAL,
    make_ecology_config,
)
from mechanistic_mind.physical_system.near_field_exteroception import NearFieldExteroceptionConfig
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.research.climate_authority import (
    climate_package_implies_on,
    compare_configs,
    effective_world_configuration,
    effective_world_fingerprint,
    harness_calibrated_config,
    interactive_calibrated_config,
)


def test_calibrated_package_implies_climate():
    assert climate_package_implies_on(ECOLOGY_CALIBRATED_TEMPORAL)


def test_harness_interactive_config_match():
    a = harness_calibrated_config()
    b = interactive_calibrated_config()
    a.cognition.cognition_enabled = False
    b.cognition.cognition_enabled = False
    assert compare_configs(a, b)["match"]


def test_climate_off_under_calibrated_is_explicit_ablation():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.planet.climate_ecology.enabled = False
    ov = experimental_overrides(cfg)
    assert ov.get("spatiotemporal_climate_ecology_disabled") is True


def test_terrain_ambient_independent_of_climate_toggle():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    t0 = (rt.world.terrain_meta or {}).get("checksum")
    a0 = (rt.world.ambient_meta or {}).get("checksum")
    rt.set_mechanism("spatiotemporal_climate_ecology", False)
    assert (rt.world.terrain_meta or {}).get("checksum") == t0
    assert (rt.world.ambient_meta or {}).get("checksum") == a0


def test_resources_independent_of_climate_at_init():
    """Beta 2: climate OFF must NOT erase R_A/R_B ecology at construction."""
    on = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    on.cognition.cognition_enabled = False
    off = deepcopy(on)
    off.planet.climate_ecology.enabled = False
    rt_on = PhysicalSystemRuntime(seed=17, config=on)
    rt_off = PhysicalSystemRuntime(seed=17, config=off)
    assert float(rt_on.world.R_A.max()) > 0.01
    assert float(rt_off.world.R_A.max()) > 0.01
    assert float(rt_off.world.R_B.max()) > 0.01


def test_resources_disabled_only_when_ecology_A_B_off():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.planet.climate_ecology.resource_ecology_A_enabled = False
    cfg.planet.climate_ecology.resource_ecology_B_enabled = False
    cfg.planet.climate_ecology.resources_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert float(rt.world.R_A.max()) < 1e-9
    assert float(rt.world.R_B.max()) < 1e-9


def test_illumination_independent_of_climate():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.planet.climate_ecology.enabled = False
    cfg.near_field_exteroception = NearFieldExteroceptionConfig(mode="EXPERIMENTAL")
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert rt.world.surface_response is not None
    assert rt.world.illumination_intensity is not None


def test_fingerprint_differs_under_ablation():
    on = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    on.cognition.cognition_enabled = False
    off = deepcopy(on)
    off.planet.climate_ecology.enabled = False
    rt_on = PhysicalSystemRuntime(seed=17, config=on)
    rt_off = PhysicalSystemRuntime(seed=17, config=off)
    assert effective_world_fingerprint(runtime=rt_on) != effective_world_fingerprint(runtime=rt_off)


def test_effective_world_reports_ablation():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.planet.climate_ecology.enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    eff = effective_world_configuration(rt)
    assert eff["climate_ablated"] is True
    assert "CLIMATE_ECOLOGY_ABLATED" in eff["overrides"]
    # Resources remain independently ON under climate ablation.
    assert eff["subsystems"]["resource_A_production"] is True
    assert eff["subsystems"]["resource_B_production"] is True
    assert eff["subsystems"]["climate_equilibrium_T_eq"] is False
    assert eff["climate_ecology"]["resource_ecology_A_enabled"] is True
    assert eff["climate_ecology"]["resource_ecology_B_enabled"] is True


def test_no_cognition_gt_from_effective_world():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    assert "climate_ablated" not in repr(obs)
    assert "world_fingerprint" not in repr(obs)


def test_thermal_body_coupling_ablation_reduces_excursion():
    base = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    base.cognition.cognition_enabled = False
    full = deepcopy(base)
    no_body = deepcopy(base)
    # Clean isolation: flow_coupling=0 alone leaves wave*unit(vx,vy) coupling.
    no_body.body.flow_coupling = 0.0
    no_body.planet.flow_enabled = False
    from mechanistic_mind.research.local_physical_coherence import trajectory_metrics_extended

    def run(cfg):
        rt = PhysicalSystemRuntime(seed=17, config=cfg)
        xs, ys = [], []
        for _ in range(400):
            rt.step_forced_action("WAIT")
            xs.append(float(rt.body.x))
            ys.append(float(rt.body.y))
        return trajectory_metrics_extended(
            xs, ys, width=rt.config.planet.width, height=rt.config.planet.height
        )

    a = run(full)
    b = run(no_body)
    assert a["max_excursion_from_start"] > 2.0 * b["max_excursion_from_start"]


def test_flow_coupling_zero_alone_leaves_wave_steering():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.body.flow_coupling = 0.0
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    eff = effective_world_configuration(rt)
    assert eff["subsystems"]["direct_flow_coupling"] is False
    assert eff["subsystems"]["wave_flow_steering"] is True
    assert eff["subsystems"]["thermal_body_coupling"] is True
    assert "DIRECT_FLOW_COUPLING_OFF_WAVE_STEERING_REMAINS" in eff["overrides"]
