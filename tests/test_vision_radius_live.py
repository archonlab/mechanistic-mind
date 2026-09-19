"""LIVE physical vision Moore radius R=1/2/3 — VR1–VR32."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CALIBRATED_TEMPORAL,
    make_ecology_config,
)
from mechanistic_mind.physical_system.near_field_exteroception import (
    DEFAULT_VISION_RADIUS,
    NearFieldExteroceptionConfig,
    clamp_vision_radius,
    cognition_exo_fragments,
    moore_max_candidates,
    moore_neighbor_cells,
    sample_near_field,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.scientific_history import collect_scientific_tick_rows
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _cfg():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(**kw):
    rt = TwoAgentRuntime(seed=17, config=_cfg())
    for mid in ("physical_near_field_vision", "illumination_cycle", "physical_body_optical_response"):
        try:
            rt.set_mechanism(mid, True)
        except Exception:
            pass
    for k, v in kw.items():
        for slot in rt.slots:
            setattr(slot.config.near_field_exteroception, k, v)
        setattr(rt.config.near_field_exteroception, k, v)
    rt.slots[0].body.x, rt.slots[0].body.y, rt.slots[0].body.theta = 16.5, 16.5, 0.0
    rt.slots[1].body.x, rt.slots[1].body.y, rt.slots[1].body.theta = 17.5, 16.5, 3.14159
    return rt


def test_VR1_default_radius_is_1():
    assert DEFAULT_VISION_RADIUS == 1
    assert NearFieldExteroceptionConfig().radius == 1
    assert NearFieldExteroceptionConfig().vision_radius == 1


def test_VR2_legacy_config_without_radius_loads_as_1():
    cfg = NearFieldExteroceptionConfig.from_dict({"mode": "EXPERIMENTAL", "perception_enabled": True})
    assert cfg.radius == 1
    assert clamp_vision_radius(None) == 1
    assert clamp_vision_radius("nope") == 1


def test_VR3_4_5_moore_counts():
    assert moore_max_candidates(1) == 8
    assert moore_max_candidates(2) == 24
    assert moore_max_candidates(3) == 48
    assert len(moore_neighbor_cells(10, 10, 32, 32, 1)) == 8
    assert len(moore_neighbor_cells(10, 10, 32, 32, 2)) == 24
    assert len(moore_neighbor_cells(10, 10, 32, 32, 3)) == 48


def test_VR6_own_cell_excluded():
    cells = moore_neighbor_cells(10, 10, 32, 32, 3)
    assert (10, 10) not in cells


def test_VR7_8_wrap_unique():
    cells = moore_neighbor_cells(0, 0, 32, 32, 2)
    assert len(cells) == len(set(cells)) == 24
    # Includes wrapped neighbors
    assert any(c[0] == 31 or c[1] == 31 for c in cells)


def test_VR_R1_enumeration_order_matches_legacy_offsets():
    """R=1 order must match historical MOORE_OFFSETS application for EXACT_MATCH."""
    from mechanistic_mind.physical_system.near_field_exteroception import MOORE_OFFSETS
    from mechanistic_mind.planet.topology import wrap_coord

    cx, cy, w, h = 10, 10, 32, 32
    legacy = [
        (int(wrap_coord(cx + dx, w)), int(wrap_coord(cy + dy, h)))
        for dy, dx in MOORE_OFFSETS
    ]
    assert moore_neighbor_cells(cx, cy, w, h, 1) == legacy


def test_VR9_15_filters_and_anonymous_exo():
    rt = _rt(radius=2)
    rt.world.surface_response[:] = 0.0
    rt.step()
    sample = sample_near_field(
        world=rt.slots[0].world,
        body=rt.slots[0].body,
        cfg=rt.slots[0].config.near_field_exteroception,
        foreign_bodies=[(rt.slots[1].body, rt.slots[1].config.body)],
    )
    assert sample["vision_radius"] == 2
    assert sample["n_candidates"] == 24
    # Some candidates outside FOV
    assert sample["n_inside_fov"] < sample["n_candidates"]
    exo = cognition_exo_fragments(
        world=rt.slots[0].world,
        body=rt.slots[0].body,
        cfg=rt.slots[0].config.near_field_exteroception,
        foreign_bodies=[(rt.slots[1].body, rt.slots[1].config.body)],
    )
    assert set(exo) <= {"exo_0", "exo_1", "exo_2"}
    assert audit_cognition_payload(exo) == []


def test_VR16_no_identity_leak():
    rt = _rt(radius=3)
    rt.step()
    obs = rt.slots[0].agent_observation(
        foreign_bodies=[(rt.slots[1].body, rt.slots[1].config.body)]
    )
    blob = json.dumps(obs)
    assert "body-1" not in blob and "radius" not in blob


def test_VR18_sensor_inspector_reports_radius():
    rt = _rt(radius=2)
    rt.step()
    frame = live_frame(rt, status="PAUSED", mode="LIVE", target_tick=None, previous_body=None, detail="full")
    nf = frame["agents_views"]["agent_0"]["physical"]["near_field_exteroception"]
    assert nf["vision_radius"] == 2
    assert nf["max_candidates"] == 24
    assert nf["n_candidates"] == 24


def test_VR20_22_live_radius_no_reset(tmp_path):
    sess = ObserverSession(config=SessionConfig(seed=17, results_root=tmp_path))
    try:
        sess.set_mechanism("physical_near_field_vision", True)
    except Exception:
        pass
    sess.step(3)
    tick0 = int(sess.runtime.tick)
    body = sess.runtime.body
    pose = (float(body.x), float(body.y), float(getattr(body, "theta", 0) or 0))
    out = sess.set_vision_radius(2)
    assert out.get("vision_radius", {}).get("accepted") is True
    assert out.get("vision_radius", {}).get("new") == 2
    assert int(sess.runtime.tick) == tick0
    pose2 = (float(body.x), float(body.y), float(getattr(body, "theta", 0) or 0))
    assert pose == pose2
    assert sess.set_vision_radius(3).get("vision_radius", {}).get("new") == 3
    assert sess.set_vision_radius(1).get("vision_radius", {}).get("new") == 1
    wi = sess.list_world_interventions()
    paths = []
    for ev in wi.get("interventions") or []:
        ch = ev.get("changes") or {}
        if "physical_near_field_vision.radius" in ch:
            paths.append(ch["physical_near_field_vision.radius"])
    assert len(paths) >= 2
    assert all(p.get("old") != p.get("new") for p in paths)


def test_VR31_intervention_replay_deterministic(tmp_path):
    def run_once(root):
        sess = ObserverSession(config=SessionConfig(seed=42, results_root=root))
        try:
            sess.set_mechanism("physical_near_field_vision", True)
        except Exception:
            pass
        sess.runtime.body.x = 16.5
        sess.runtime.body.y = 16.5
        sess.runtime.body.theta = 0.0
        sess.step(5)
        sess.set_vision_radius(2)
        sess.step(5)
        b = sess.runtime.body
        return (
            float(b.x),
            float(b.y),
            float(getattr(b, "theta", 0) or 0),
            getattr(sess.runtime, "last_selected_action", None),
            int(sess.runtime.config.near_field_exteroception.radius),
        )

    assert run_once(tmp_path / "a") == run_once(tmp_path / "b")


def test_VR28_vision_optical_includes_radius():
    rt = _rt(radius=3)
    rt.step()
    rows = collect_scientific_tick_rows(rt)
    for r in rows:
        vo = r["vision_optical"]
        assert vo.get("available")
        assert vo.get("vision_radius") == 3 or vo.get("radius") == 3


def test_VR29_r1_matches_explicit_radius_1_sample():
    """Default (implicit R=1) sample equals explicit radius=1."""
    rt_a = _rt()
    rt_b = _rt(radius=1)
    for rt in (rt_a, rt_b):
        rt.world.surface_response[:] = 0.25
    for i in range(2):
        rt_b.slots[i].body.x = rt_a.slots[i].body.x
        rt_b.slots[i].body.y = rt_a.slots[i].body.y
        rt_b.slots[i].body.theta = rt_a.slots[i].body.theta
    sa = sample_near_field(
        world=rt_a.world, body=rt_a.slots[0].body,
        cfg=rt_a.slots[0].config.near_field_exteroception,
        foreign_bodies=[(rt_a.slots[1].body, rt_a.slots[1].config.body)],
        tick=0,
    )
    sb = sample_near_field(
        world=rt_b.world, body=rt_b.slots[0].body,
        cfg=rt_b.slots[0].config.near_field_exteroception,
        foreign_bodies=[(rt_b.slots[1].body, rt_b.slots[1].config.body)],
        tick=0,
    )
    assert sa["fragments"] == sb["fragments"]
    assert sa["n_candidates"] == sb["n_candidates"] == 8
    assert [r["cell"] for r in sa["neighbors"]] == [r["cell"] for r in sb["neighbors"]]


def test_VR30_fixed_radius_deterministic():
    def run(r):
        rt = _rt(radius=r)
        exo = []
        for _ in range(5):
            rt.step()
            o = rt.slots[0].agent_observation(
                foreign_bodies=[(rt.slots[1].body, rt.slots[1].config.body)]
            )
            exo.append({k: o.get(k) for k in ("exo_0", "exo_1", "exo_2")})
        return exo

    assert run(1) == run(1)
    assert run(2) == run(2)
    assert run(3) == run(3)
