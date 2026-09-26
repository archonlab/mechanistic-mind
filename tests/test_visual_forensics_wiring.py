"""VF wiring: Sensor Inspector optical authority → Analyzer Visual Forensics."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CALIBRATED_TEMPORAL,
    make_ecology_config,
)
from mechanistic_mind.physical_system.near_field_exteroception import (
    cognition_exo_fragments,
    sample_near_field,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.scientific_history import (
    BODY_OPTICAL_EPS,
    body_derived_exo_contribution,
    collect_scientific_tick_rows,
)
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame
from mechanistic_mind.ui.psy_observer_web.vision_forensics import (
    analyze_optical_series,
    body_optical_active,
    optical_snapshots_from_scientific_ticks,
)


def _cfg(**kw):
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    for k, v in kw.items():
        setattr(cfg.near_field_exteroception, k, v)
    return cfg


def _two(*, vision=True, body_optics=True):
    rt = TwoAgentRuntime(seed=17, config=_cfg())
    if vision:
        rt.set_mechanism("physical_near_field_vision", True)
    else:
        rt.set_mechanism("physical_near_field_vision", False)
    if body_optics:
        rt.set_mechanism("physical_body_optical_response", True)
    else:
        rt.set_mechanism("physical_body_optical_response", False)
    try:
        rt.set_mechanism("illumination_cycle", True)
    except Exception:
        pass
    rt.slots[0].body.x, rt.slots[0].body.y, rt.slots[0].body.theta = 16.5, 16.5, 0.0
    rt.slots[1].body.x, rt.slots[1].body.y, rt.slots[1].body.theta = 17.5, 16.5, 3.1415926535
    return rt


def test_VF1_sensor_inspector_path_uses_sample_near_field():
    """Sensor Inspector physical.near_field_exteroception == sample_near_field authority."""
    rt = _two()
    rt.step()
    frame = live_frame(rt, status="PAUSED", mode="LIVE", target_tick=None, previous_body=None, detail="full")
    nf0 = (frame["agents_views"]["agent_0"]["physical"] or {}).get("near_field_exteroception")
    assert nf0 is not None
    assert "neighbors" in nf0
    assert "fragments" in nf0
    assert "n_detectable" in nf0
    assert "n_body_optical_cells" in nf0
    # Same authority function
    direct = sample_near_field(
        world=rt.slots[0].world,
        body=rt.slots[0].body,
        cfg=rt.slots[0].config.near_field_exteroception,
        foreign_bodies=[(rt.slots[1].body, rt.slots[1].config.body)],
    )
    assert nf0["n_body_optical_cells"] == direct["n_body_optical_cells"]
    for k in ("exo_0", "exo_1", "exo_2"):
        assert abs(float(nf0["fragments"][k]) - float(direct["fragments"][k])) < 1e-12


def test_VF2_scientific_rows_reuse_same_authority():
    rt = _two()
    for _ in range(3):
        rt.step()
    rows = collect_scientific_tick_rows(rt)
    assert len(rows) == 2
    for r in rows:
        vo = r["vision_optical"]
        assert vo["available"] is True
        assert vo["authority"] == "sample_near_field"
        assert "foreign_body_contribution" in vo
        assert "body_exposure" in vo
        assert "final_exo" in vo


def test_VF5_env_only_not_body_exposure():
    rt = PhysicalSystemRuntime(seed=17, config=_cfg())
    rt.set_mechanism("physical_near_field_vision", True)
    rt.world.surface_response[:] = 0.8
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    sample = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, foreign_bodies=[]
    )
    assert sample["n_detectable"] >= 1
    assert sample["n_body_optical_cells"] == 0
    derived = body_derived_exo_contribution(sample["fragments"], sample["fragments"])
    assert derived["body_exposure"] is False
    assert derived["foreign_body_total"] <= BODY_OPTICAL_EPS


def test_VF6_face_to_face_body_exposure():
    rt = _two()
    # Zero surface so body contribution is unambiguous
    rt.world.surface_response[:] = 0.0
    for _ in range(2):
        rt.step()
    rows = collect_scientific_tick_rows(rt)
    exposed = [r for r in rows if r["vision_optical"].get("body_exposure")]
    assert exposed, "expected body_exposure for face-to-face agents"
    snaps = optical_snapshots_from_scientific_ticks(rows)
    assert any(body_optical_active(s) for s in snaps)


def test_VF7_fov_out_no_exposure():
    rt = _two()
    rt.world.surface_response[:] = 0.0
    # Place body-1 behind agent_0 FOV (agent_0 faces +x, put peer at -x)
    rt.slots[0].body.x, rt.slots[0].body.y, rt.slots[0].body.theta = 16.5, 16.5, 0.0
    rt.slots[1].body.x, rt.slots[1].body.y = 15.5, 16.5
    rt.step()
    row0 = [r for r in collect_scientific_tick_rows(rt) if r["agent_id"] == "agent_0"][0]
    vo = row0["vision_optical"]
    # Peer may occupy a cell with body_optical but outside FOV → no surviving exo delta
    assert vo["body_exposure"] is False or vo["foreign_body_total"] <= BODY_OPTICAL_EPS


def test_VF8_outside_range_no_exposure():
    rt = _two()
    rt.world.surface_response[:] = 0.0
    rt.slots[0].body.x, rt.slots[0].body.y = 16.5, 16.5
    rt.slots[1].body.x, rt.slots[1].body.y = 20.5, 20.5  # outside Moore R=1
    rt.step()
    row0 = [r for r in collect_scientific_tick_rows(rt) if r["agent_id"] == "agent_0"][0]
    assert row0["vision_optical"]["body_exposure"] is False
    assert row0["vision_optical"]["n_body_optical_cells"] == 0


def test_VF9_body_optics_off():
    rt = _two(body_optics=False)
    rt.world.surface_response[:] = 0.0
    rt.step()
    for r in collect_scientific_tick_rows(rt):
        vo = r["vision_optical"]
        assert vo.get("body_optical_enabled") is False or vo.get("body_optics_enabled") is False
        assert vo["body_exposure"] is False


def test_VF10_vision_off_available_false_or_disabled():
    rt = _two(vision=False)
    rt.step()
    for r in collect_scientific_tick_rows(rt):
        vo = r["vision_optical"]
        # Package OFF → available False; or enabled package with perception off
        if vo.get("available"):
            assert vo.get("vision_enabled") is False or vo.get("vision_contributes") is False
        else:
            assert vo.get("reason")


def test_VF11_two_agent_symmetry_exposure():
    rt = _two()
    rt.world.surface_response[:] = 0.0
    for _ in range(3):
        rt.step()
    rows = collect_scientific_tick_rows(rt)
    by = {r["agent_id"]: r["vision_optical"] for r in rows}
    assert by["agent_0"]["body_exposure"] is True
    assert by["agent_1"]["body_exposure"] is True


def test_VF14_identity_not_in_cognition():
    rt = _two()
    rt.step()
    for i, slot in enumerate(rt.slots):
        fb = [(rt.slots[j].body, rt.slots[j].config.body) for j in range(2) if j != i]
        obs = slot.agent_observation(foreign_bodies=fb)
        assert set(k for k in obs if str(k).startswith("exo_")) <= {"exo_0", "exo_1", "exo_2"}
        assert audit_cognition_payload(obs) == []
        blob = json.dumps(obs)
        assert "body-1" not in blob and "body-0" not in blob
        assert "Tiktaalik" not in blob and "undercover" not in blob


def test_VF15_exposure_without_contact():
    rt = _two()
    rt.world.surface_response[:] = 0.0
    # Adjacent but ensure soft contact flag false if possible — still optical
    rt.step()
    rows = collect_scientific_tick_rows(rt)
    snaps = optical_snapshots_from_scientific_ticks(rows)
    active = [s for s in snaps if body_optical_active(s)]
    assert active
    # Contact may or may not coincide; Analyzer must be able to represent without fabricating
    rep = analyze_optical_series(active)
    assert rep["summary"]["cognition_linkage_default"] == "NOT_ESTABLISHED"


def test_VF19_old_rows_without_vision_optical():
    rows = [{"tick": 1, "agent_id": "agent_0", "body_id": "body-0", "action": "WAIT"}]
    snaps = optical_snapshots_from_scientific_ticks(rows)
    assert snaps == []
    rep = analyze_optical_series(snaps)
    assert rep["coverage"] == "NOT_AVAILABLE"


def test_VF27_28_exo_unchanged_by_compact_record():
    rt = _two()
    rt.world.surface_response[:] = 0.0
    rt.step()
    fb = [(rt.slots[1].body, rt.slots[1].config.body)]
    exo_before = cognition_exo_fragments(
        world=rt.slots[0].world,
        body=rt.slots[0].body,
        cfg=rt.slots[0].config.near_field_exteroception,
        foreign_bodies=fb,
    )
    rows = collect_scientific_tick_rows(rt)
    exo_after = cognition_exo_fragments(
        world=rt.slots[0].world,
        body=rt.slots[0].body,
        cfg=rt.slots[0].config.near_field_exteroception,
        foreign_bodies=fb,
    )
    assert exo_before == exo_after
    vo = [r for r in rows if r["agent_id"] == "agent_0"][0]["vision_optical"]
    for k in ("exo_0", "exo_1", "exo_2"):
        assert abs(float(vo["final_exo"][k]) - float(exo_before[k])) < 1e-12


def test_VF26_sensor_inspector_still_has_candidate_rows():
    rt = _two()
    rt.step()
    frame = live_frame(rt, status="PAUSED", mode="LIVE", target_tick=None, previous_body=None, detail="full")
    nf = frame["agents_views"]["agent_0"]["physical"]["near_field_exteroception"]
    assert len(nf["neighbors"]) == 8
    assert any("body_optical" in n and "composed_optical" in n for n in nf["neighbors"])
