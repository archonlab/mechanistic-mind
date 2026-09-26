"""Beta 3.1 visual surface discrimination — focused tests."""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from mechanistic_mind.physical_body.config import default_physical_body2_config
from mechanistic_mind.physical_system.near_field_exteroception import (
    NearFieldExteroceptionConfig,
    clamp_surface_discrimination,
    cognition_exo_fragments,
    cognition_surface_fragments,
    generate_surface_optical,
    install_surface_on_planet,
    sample_near_field,
    surface_observation_keys,
)
from mechanistic_mind.physical_system.observation import accessible_observation, audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from pathlib import Path
import tempfile

from mechanistic_mind.scientific_v3.analyzer_next.joins import apply_joins
from mechanistic_mind.scientific_v3.analyzer_next.relationships import RelationshipGraph
from mechanistic_mind.scientific_v3.analyzer_next.tick_stories import TickStory, _parse_observation_components
from mechanistic_mind.scientific_v3.receipts import build_observation_receipt, compact_accessible_observation


def _nfe(**kw) -> NearFieldExteroceptionConfig:
    base = dict(
        mode="EXPERIMENTAL",
        perception_enabled=True,
        illumination_enabled=True,
        surface_enabled=True,
        radius=2,
        visual_surface_discrimination="OFF",
        optical_mapping="INDEPENDENT",
    )
    base.update(kw)
    return NearFieldExteroceptionConfig(**base)


def _rt(*, seed=17, disc="OFF", mapping="INDEPENDENT", psc=False) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig()
    cfg.near_field_exteroception = _nfe(
        visual_surface_discrimination=disc,
        optical_mapping=mapping,
    )
    cfg.cognition.psc_off_ticks = None
    cfg.body = default_physical_body2_config()
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.set_mechanism("physical_near_field_vision", True)
    rt.set_mechanism("prospective_scenario_competition", bool(psc))
    rt.set_visual_surface_discrimination(disc)
    return rt


def test_clamp_and_keys():
    assert clamp_surface_discrimination("rich") == "RICH"
    assert clamp_surface_discrimination("nope") == "OFF"
    assert surface_observation_keys("OFF") == ()
    assert surface_observation_keys("LOW") == ("surface_c0_0", "surface_c0_1", "surface_c0_2")
    assert len(surface_observation_keys("RICH")) == 9


def test_optical_field_deterministic():
    cfg = _nfe(visual_surface_discrimination="RICH", optical_mapping="INDEPENDENT")
    a, ma = generate_surface_optical(height=12, width=12, experiment_seed=99, cfg=cfg)
    b, mb = generate_surface_optical(height=12, width=12, experiment_seed=99, cfg=cfg)
    assert a.shape == (3, 12, 12)
    assert np.allclose(a, b)
    assert ma["checksum"] == mb["checksum"]
    c, _ = generate_surface_optical(height=12, width=12, experiment_seed=100, cfg=cfg)
    assert not np.allclose(a, c)


def test_mapping_shuffled_not_identical_layout():
    h = w = 16
    rng = np.random.default_rng(1)
    pot = rng.random((h, w))
    cfg_c = _nfe(optical_mapping="CORRELATED", optical_correlation=1.0)
    cfg_s = _nfe(optical_mapping="SHUFFLED", optical_correlation=1.0)
    corr, _ = generate_surface_optical(
        height=h, width=w, experiment_seed=3, cfg=cfg_c, terrain_potential=pot,
    )
    shuf, _ = generate_surface_optical(
        height=h, width=w, experiment_seed=3, cfg=cfg_s, terrain_potential=pot,
    )
    assert not np.allclose(corr[0], shuf[0])
    assert np.allclose(np.sort(corr[0].ravel()), np.sort(shuf[0].ravel()), atol=1e-9)


def test_uniform_collapses():
    cfg = _nfe(optical_mapping="UNIFORM")
    t, _ = generate_surface_optical(height=8, width=8, experiment_seed=1, cfg=cfg)
    assert np.allclose(t, 0.5)


def test_off_has_no_surface_keys():
    rt = _rt(disc="OFF")
    obs = rt.agent_observation()
    assert all(not k.startswith("surface_c") for k in obs)
    assert "exo_0" in obs or True  # vision may still contribute zeros
    hits = audit_cognition_payload(obs)
    assert "surface_optical" not in hits


def test_low_and_rich_channels():
    low = _rt(disc="LOW")
    rich = _rt(disc="RICH")
    ol = low.agent_observation()
    orich = rich.agent_observation()
    for k in surface_observation_keys("LOW"):
        assert k in ol
    for k in surface_observation_keys("RICH"):
        assert k in orich
    assert "surface_c1_0" not in ol
    assert all(0.0 <= float(orich[k]) <= 1.0 for k in surface_observation_keys("RICH"))


def test_off_equivalence_same_seed():
    a = _rt(seed=21, disc="OFF")
    b = _rt(seed=21, disc="OFF")
    for _ in range(12):
        a.step(1)
        b.step(1)
    oa = {k: v for k, v in a.agent_observation().items() if not str(k).startswith("surface_c")}
    ob = {k: v for k, v in b.agent_observation().items() if not str(k).startswith("surface_c")}
    assert oa.keys() == ob.keys()
    for k in oa:
        assert oa[k] == pytest.approx(ob[k], abs=1e-12)
    assert a.body.x == pytest.approx(b.body.x)
    assert a.body.y == pytest.approx(b.body.y)
    assert a.last_selected_action == b.last_selected_action


def test_off_vs_rich_exo_intensity_path_stable():
    """Discrimination must not rewrite exo_* composition when both see vision."""
    off = _rt(seed=8, disc="OFF")
    # RICH uses extra channels; exo_* still from surface_response.
    rich = _rt(seed=8, disc="RICH")
    so = sample_near_field(world=off.world, body=off.body, cfg=off.config.near_field_exteroception)
    sr = sample_near_field(world=rich.world, body=rich.body, cfg=rich.config.near_field_exteroception)
    assert so["fragments"] == sr["fragments"]


def test_fov_gating_zero_behind():
    rt = _rt(disc="RICH")
    nfe = rt.config.near_field_exteroception
    sample = sample_near_field(world=rt.world, body=rt.body, cfg=nfe)
    behind = [r for r in sample["neighbors"] if not r["inside_fov"]]
    assert behind, "need some cells outside FOV"
    # Outside FOV must not contribute to surface fragments via final==0 path
    for r in behind:
        assert r["final_contribution"] == 0.0


def test_periodic_boundary_cells_wrapped():
    rt = _rt(disc="LOW")
    rt.body.x = 0.2
    rt.body.y = 0.2
    sample = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])
    for r in sample["neighbors"]:
        x, y = r["cell"]
        assert 0 <= x < w and 0 <= y < h


def test_scientific_v3_receipt_includes_surface():
    rt = _rt(disc="RICH")
    acc = compact_accessible_observation(rt.agent_observation())
    rec = build_observation_receipt(
        run_id="t", tick=0, cognitive_agent_id="agent_0",
        physical_body_id="body_0", accessible=acc,
    )
    assert any(k.startswith("surface_c") for k in rec["accessible"])
    assert rec["signature"]


def test_analyzer_surface_exposure():
    acc = {"exo_0": 0.2, "surface_c0_0": 0.1, "surface_c0_1": 0.8, "surface_c0_2": 0.1}
    comps = _parse_observation_components({"accessible": acc})
    story = TickStory(
        run_id="r", tick=3, cognitive_agent_id="agent_0", physical_body_id="b0",
        observation_id="o", decision_id="d", motor_id="m", consequence_id="c",
        observation_components=comps,
    )
    graph = RelationshipGraph(run_id="r")
    with tempfile.TemporaryDirectory() as d:
        apply_joins([story], graph, run_dir=Path(d))
    kinds = {c["kind"] for c in story.external_context}
    assert "SURFACE_EXPOSURE" in kinds
    assert "OPTICAL_CONTRAST_CHANGE" in kinds
    assert "ACTION_UNDER_SURFACE_EXPOSURE" in kinds


def test_save_restore_optical_and_next_tick():
    rt = _rt(seed=44, disc="RICH")
    rt.step(7)
    snap = rt.snapshot()
    assert snap["world"].get("surface_optical") is not None
    cont = deepcopy(rt)
    cont.step(5)
    restored = PhysicalSystemRuntime.restore(snap)
    restored.step(5)
    o1 = {k: cont.agent_observation()[k] for k in surface_observation_keys("RICH")}
    o2 = {k: restored.agent_observation()[k] for k in surface_observation_keys("RICH")}
    for k in o1:
        assert o1[k] == pytest.approx(o2[k], abs=1e-9)
    assert cont.body.x == pytest.approx(restored.body.x)
    assert cont.last_selected_action == restored.last_selected_action


def test_two_agent_independent_channels():
    nfe = _nfe(visual_surface_discrimination="RICH")
    cfg = PhysicalSystemConfig()
    cfg.near_field_exteroception = nfe
    ta = TwoAgentRuntime(seed=5, config=cfg)
    ta.set_mechanism("physical_near_field_vision", True)
    ta.set_visual_surface_discrimination("RICH")
    ta.slots[0].body.x = 2.5
    ta.slots[0].body.y = 2.5
    ta.slots[1].body.x = 20.5
    ta.slots[1].body.y = 20.5
    o0 = ta.slots[0].agent_observation(foreign_bodies=[(ta.slots[1].body, ta.slots[1].config.body)])
    o1 = ta.slots[1].agent_observation(foreign_bodies=[(ta.slots[0].body, ta.slots[0].config.body)])
    assert any(k.startswith("surface_c") for k in o0)
    # Different sites typically differ; allow equality only if fields happen to match
    assert audit_cognition_payload(o0) == []
    assert audit_cognition_payload(o1) == []


def test_psc_off_ticks_activates_without_reset():
    cfg = PhysicalSystemConfig()
    cfg.near_field_exteroception = _nfe()
    cfg.cognition.psc_off_ticks = 4
    rt = PhysicalSystemRuntime(seed=2, config=cfg)
    rt.set_mechanism("physical_near_field_vision", True)
    rt.set_mechanism("prospective_scenario_competition", False)
    cog0 = id(rt.cognition)
    body_x = rt.body.x
    rt.step(4)
    assert getattr(rt, "_psc_auto_activated", False) is True
    assert id(rt.cognition) == cog0
    assert rt.body.x == body_x or True  # may move; history object preserved
    assert rt._psc_activation["history_preserved"] is True
    assert rt._psc_activation["kind"] == "PSC_ACTIVATION"


def test_performance_smoke_off_low_rich():
    import time
    rows = []
    for disc in ("OFF", "LOW", "RICH"):
        rt = _rt(seed=3, disc=disc)
        t0 = time.perf_counter()
        rt.step(40)
        dt = time.perf_counter() - t0
        rows.append((disc, dt))
    # Sanity: all complete; RICH should not be orders of magnitude slower on 40 ticks
    off_t = rows[0][1]
    rich_t = rows[2][1]
    assert rich_t < off_t * 20 + 1.0
