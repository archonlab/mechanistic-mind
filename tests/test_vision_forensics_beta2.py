"""Vision forensics fixtures VF1–VF30 — analysis-only."""
from __future__ import annotations

from copy import deepcopy

import pytest

from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.physical_body.state import PhysicalBodyState
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
from mechanistic_mind.ui.psy_observer_web.vision_forensics import (
    analyze_optical_series,
    build_visual_causal_chains,
    build_visual_events,
    build_visual_followup,
    channel_overlap,
    snapshot_from_sample,
)


def _calibrated(**kw):
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    for k, v in kw.items():
        setattr(cfg.near_field_exteroception, k, v)
    return cfg


def _rt():
    rt = PhysicalSystemRuntime(seed=17, config=_calibrated())
    rt.world.surface_response[:] = 0.0
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    return rt


def _foreign(x, y, optical=0.65, body_id="body-1"):
    bc = PhysicalBodyConfig(optical_response=optical, footprint=((0, 0),))
    tmp = PhysicalSystemRuntime(seed=1, config=PhysicalSystemConfig(body=bc))
    tmp.body.x, tmp.body.y = float(x), float(y)
    return tmp.body, bc, body_id


def _snap(
    rt,
    foreign=None,
    *,
    tick=0,
    coverage="CONTIGUOUS",
    regime="R0",
    contact=False,
    field=False,
    action=None,
    scenario=None,
):
    fb = []
    src_map = {}
    selected = None
    exo_without = None
    if foreign is not None:
        body, cfg, bid = foreign
        fb = [(body, cfg)]
        selected = bid
        ix, iy = int(body.x), int(body.y)
        src_map[(iy, ix)] = [bid]
        exo_without = cognition_exo_fragments(
            world=rt.world,
            body=rt.body,
            cfg=rt.config.near_field_exteroception,
            foreign_bodies=[],
        )
    sample = sample_near_field(
        world=rt.world,
        body=rt.body,
        cfg=rt.config.near_field_exteroception,
        foreign_bodies=fb,
        tick=tick,
    )
    return snapshot_from_sample(
        tick=tick,
        sample=sample,
        observer_body_id="body-0",
        observer_agent_id="agent_0",
        source_body_ids_by_cell=src_map,
        contact=contact,
        field_reception=field,
        action=action,
        scenario_selected=scenario,
        regime_id=regime,
        coverage=coverage,
        vision_enabled=True,
        body_optics_enabled=True,
        exo_without_body=exo_without,
        selected_source_body_id=selected,
    )


def test_VF_A_NO_BODY():
    rt = _rt()
    rep = analyze_optical_series([_snap(rt, None, tick=0)])
    assert rep["summary"]["foreign_body_visual_entries"] == 0
    assert rep["summary"]["exposure_episodes"] == 0


def test_VF_B_BODY_FRONT():
    rt = _rt()
    rep = analyze_optical_series([_snap(rt, _foreign(17.5, 16.5), tick=1)])
    assert rep["summary"]["foreign_body_visual_entries"] == 1
    assert any(e["type"] == "BODY_VISUAL_ENTRY" for e in rep["events"])
    assert rep["causal_chains"]
    assert rep["causal_chains"][0]["edges"][-1]["link"] == "NOT_ESTABLISHED"


def test_VF_C_BODY_BEHIND():
    rt = _rt()
    snap = _snap(rt, _foreign(15.5, 16.5), tick=1)
    west = next(n for n in snap.neighbors if n.cell == [15, 16])
    assert west.body_optical > 0
    assert west.inside_fov is False
    rep = analyze_optical_series([snap])
    assert rep["summary"]["foreign_body_visual_entries"] == 0


def test_VF_D_BODY_EXIT():
    rt = _rt()
    ticks = [
        _snap(rt, _foreign(17.5, 16.5), tick=10),
        _snap(rt, _foreign(20.5, 16.5), tick=11),
    ]
    types = [e["type"] for e in build_visual_events(ticks)]
    assert "BODY_VISUAL_ENTRY" in types
    assert "BODY_VISUAL_EXIT" in types


def test_VF_E_VISION_ONLY():
    rt = _rt()
    assert channel_overlap(_snap(rt, _foreign(17.5, 16.5), tick=1)) == "VISION_WITHOUT_CONTACT"


def test_VF_F_G_overlap_classes():
    rt = _rt()
    assert channel_overlap(_snap(rt, _foreign(17.5, 16.5), tick=1, field=True)) == "VISION_WITH_SIGNAL"
    assert channel_overlap(_snap(rt, _foreign(17.5, 16.5), tick=1, contact=True)) == "VISION_PLUS_CONTACT"
    assert (
        channel_overlap(_snap(rt, _foreign(17.5, 16.5), tick=1, contact=True, field=True))
        == "VISION_PLUS_FIELD_PLUS_CONTACT"
    )


def test_VF_H_IDENTITY_SWAP():
    rt = _rt()
    a = _snap(rt, _foreign(17.5, 16.5, body_id="ordinary"), tick=1)
    b = _snap(rt, _foreign(17.5, 16.5, body_id="undercover"), tick=1)
    c = _snap(rt, _foreign(17.5, 16.5, body_id="cogfree"), tick=1)
    assert a.exo == b.exo == c.exo
    ra = analyze_optical_series([a])
    rb = analyze_optical_series([b])
    assert ra["summary"]["foreign_body_visual_entries"] == rb["summary"]["foreign_body_visual_entries"]


def test_VF_I_SPARSE_GAP():
    rt = _rt()
    ticks = [
        _snap(rt, _foreign(17.5, 16.5), tick=1, coverage="CONTIGUOUS"),
        _snap(rt, _foreign(17.5, 16.5), tick=2, coverage="GAP"),
        _snap(rt, _foreign(17.5, 16.5), tick=5, coverage="CONTIGUOUS"),
    ]
    rep = analyze_optical_series(ticks)
    assert rep["coverage"] == "SPARSE"
    assert any(ep.get("true_duration") == "NOT_AVAILABLE" for ep in rep["episodes"]) or len(rep["episodes"]) >= 2
    fe = rep["summary"]["first_observed_body_visual_entry"]
    assert fe is not None
    assert fe["wording"] == "FIRST OBSERVED"


def test_VF_J_MULTI_REGIME():
    rt = _rt()
    t0 = _snap(rt, _foreign(17.5, 16.5), tick=1, regime="VISION_ON")
    t1 = _snap(rt, _foreign(17.5, 16.5), tick=2, regime="VISION_ON")
    t2 = _snap(rt, _foreign(17.5, 16.5), tick=3, regime="BODY_OPTICS_OFF")
    t2.body_optics_enabled = False
    for n in t2.neighbors:
        n.body_optical = 0.0
        n.composed_optical = n.surface_response
        n.final_contribution = 0.0
    t2.exo = cognition_exo_fragments(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, foreign_bodies=[]
    )
    t2.selected_source_body_id = None
    rep = analyze_optical_series([t0, t1, t2])
    assert any(e.get("regime_id") == "VISION_ON" for e in rep["events"])
    assert any(e["type"] == "BODY_VISUAL_EXIT" for e in rep["events"])


def test_VF11_12_exo_only_cognition_non_leak():
    rt = _rt()
    other = _foreign(17.5, 16.5)
    exo = cognition_exo_fragments(
        world=rt.world,
        body=rt.body,
        cfg=rt.config.near_field_exteroception,
        foreign_bodies=[(other[0], other[1])],
    )
    assert set(exo) <= {"exo_0", "exo_1", "exo_2"}
    assert audit_cognition_payload(exo) == []


def test_VF18_20_causal_evidence_classes():
    rt = _rt()
    chains = build_visual_causal_chains([_snap(rt, _foreign(17.5, 16.5), tick=1)])
    assert chains
    links = [e["link"] for e in chains[0]["edges"]]
    assert links.count("DIRECT_CAUSAL_LINK") >= 3
    assert links[-1] == "NOT_ESTABLISHED"
    assert chains[0]["values"]["counterfactual_class"] == "DERIVED_COUNTERFACTUAL_PHYSICAL"


def test_VF21_followup_temporally_associated():
    rt = _rt()
    ticks = [
        _snap(rt, _foreign(17.5, 16.5), tick=10, action="WAIT"),
        _snap(rt, _foreign(17.5, 16.5), tick=11, action="WAIT"),
        _snap(rt, _foreign(17.5, 16.5), tick=13, action="MOVE:E", scenario="MOVE:E"),
    ]
    rep = analyze_optical_series(ticks)
    fu = build_visual_followup(ticks, rep["episodes"], window=5)
    assert fu
    assert fu[0]["followup_evidence_class"] == "TEMPORALLY_ASSOCIATED"
    assert fu[0]["linkage_to_cognition"] == "NOT_ESTABLISHED"


def test_VF5_own_body_excluded():
    rt = _rt()
    # Passing observer as foreign would be a caller bug; analysis path uses foreign_bodies only.
    sample = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, foreign_bodies=[]
    )
    assert sample["n_body_optical_cells"] == 0
    snap = snapshot_from_sample(tick=0, sample=sample, observer_body_id="body-0")
    assert not any(n.body_optical > 0 for n in snap.neighbors)


def test_VF27_analysis_does_not_mutate_runtime():
    rt = _rt()
    t0 = rt.world.T.copy()
    s0 = rt.world.surface_response.copy()
    analyze_optical_series([_snap(rt, _foreign(17.5, 16.5), tick=1)])
    assert (rt.world.T == t0).all()
    assert (rt.world.surface_response == s0).all()


def test_VF_gates_table_smoke():
    """VF1–VF30 acceptance smoke from fixtures A–J."""
    rt = _rt()
    front = analyze_optical_series([_snap(rt, _foreign(17.5, 16.5), tick=1)])
    behind = analyze_optical_series([_snap(rt, _foreign(15.5, 16.5), tick=1)])
    assert front["summary"]["foreign_body_visual_entries"] == 1  # VF1, VF6, VF7, VF13
    assert behind["summary"]["foreign_body_visual_entries"] == 0  # VF7 FOV
    assert front["summary"]["cognition_linkage_default"] == "NOT_ESTABLISHED"  # VF20
    assert "Physical visual exposure" in front["summary"]["disclaimer"]
