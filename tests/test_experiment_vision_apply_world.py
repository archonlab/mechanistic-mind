"""Experiment Vision config uses existing session APIs; Apply World preserves values."""
from __future__ import annotations

from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _nfe(sess):
    rt = sess.runtime
    slots = getattr(rt, "slots", None)
    if slots:
        return getattr(slots[0].config, "near_field_exteroception", None)
    return getattr(getattr(rt, "config", None), "near_field_exteroception", None)


def test_experiment_vision_apply_world_preserves_existing_wiring():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    r = s.set_vision_radius(2)
    assert r["control_receipt"]["accepted"] is True
    spat = s.set_spatial_vision("OCCLUSION")
    assert spat["control_receipt"]["accepted"] is True
    assert _nfe(s).spatial_vision == "OCCLUSION"
    assert int(_nfe(s).radius) == 2

    out = s.apply_experiment({
        "seed": 17,
        "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
    })
    assert out["control_receipt"]["accepted"] is True
    assert out["control_receipt"]["requires_reset"] is True
    assert int(_nfe(s).radius) == 2
    assert _nfe(s).spatial_vision == "OCCLUSION"
    s.step(5)
    assert int(_nfe(s).radius) == 2
    assert _nfe(s).spatial_vision == "OCCLUSION"

    nfe = (out.get("physical") or {}).get("near_field_exteroception") or {}
    assert nfe.get("fov_deg") is not None
    assert int(nfe.get("vision_radius") or nfe.get("radius") or 0) == 2
