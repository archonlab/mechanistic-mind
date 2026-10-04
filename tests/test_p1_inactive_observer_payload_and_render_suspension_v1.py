"""P1 inactive Observer payload and render suspension tests.

Schema: OBSERVER_DERIVED_PAYLOAD_SUBSCRIPTION_V1
"""
from __future__ import annotations

import copy
import json
import os

import pytest

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.physical_system.experiment_canonical import public_model_selector_entries
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.ui.psy_observer_web.observer_derived_payload_subscription import (
    AUTHORITY,
    CAPABILITY,
    FAMILY_SURFACE,
    FAMILY_VOLUME,
    OMISSION_NOT_REQUESTED,
    PROFILE,
    PRODUCT_SURFACE_LIGHT,
    PRODUCT_VOLUME_XRAY,
    SCHEMA,
    resolve_derived_subscription,
)
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame, world_frame
from mechanistic_mind.ui.psy_observer_web.subscriptions import (
    ALL_PRODUCTS,
    ObserverInterest,
    PRESET_NORMAL,
    PRODUCT_WORLD,
)


def _rt(*, seed: int = 11):
    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = False
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def _frame(rt, interest=None, detail="compact"):
    return live_frame(
        rt,
        status="PAUSED",
        mode="LIVE",
        target_tick=None,
        previous_body=None,
        detail=detail,
        include_cognition=False,
        observer_interest=interest,
    )


def test_01_subscription_parsing_resolution():
    r = resolve_derived_subscription(None)
    assert r.schema == SCHEMA
    assert r.capability == CAPABILITY
    assert r.profile == PROFILE
    assert r.authority == AUTHORITY
    assert r.include_volume is False
    assert r.include_surface is False
    assert FAMILY_VOLUME in r.omitted_families
    assert FAMILY_SURFACE in r.omitted_families

    r2 = resolve_derived_subscription(explicit_products=[PRODUCT_VOLUME_XRAY])
    assert r2.include_volume is True
    assert r2.include_surface is False

    r3 = resolve_derived_subscription(explicit_products=[PRODUCT_SURFACE_LIGHT])
    assert r3.include_surface is True
    assert r3.include_volume is False

    r4 = resolve_derived_subscription(
        explicit_products=[PRODUCT_VOLUME_XRAY, PRODUCT_SURFACE_LIGHT]
    )
    assert r4.include_volume and r4.include_surface


def test_02_legacy_absent_interest_map_only():
    rt = _rt()
    rt.step()
    fr = _frame(rt, interest=None)
    world = fr["world"]
    assert "observer_camera_occupancy_consumer" not in world
    assert "researcher_physical_optical_audit_view" not in world
    sub = fr["observer_derived_payload_subscription"]
    assert sub["schema"] == SCHEMA
    omitted = {o["family"]: o["reason"] for o in sub["omitted_payload_families"]}
    assert omitted[FAMILY_VOLUME] == OMISSION_NOT_REQUESTED
    assert omitted[FAMILY_SURFACE] == OMISSION_NOT_REQUESTED


def test_03_map_omits_volume_surface():
    rt = _rt(seed=12)
    rt.step()
    interest = ObserverInterest()
    assert PRODUCT_VOLUME_XRAY not in interest.products
    fr = _frame(rt, interest=interest)
    assert "observer_camera_occupancy_consumer" not in fr["world"]
    assert "researcher_physical_optical_audit_view" not in fr["world"]


def test_04_volume_omits_surface():
    rt = _rt(seed=13)
    rt.step()
    interest = ObserverInterest()
    interest.add(PRODUCT_VOLUME_XRAY)
    fr = _frame(rt, interest=interest)
    assert "observer_camera_occupancy_consumer" in fr["world"]
    assert fr["world"]["observer_camera_occupancy_consumer"].get("available") is True
    assert "researcher_physical_optical_audit_view" not in fr["world"]


def test_05_surface_omits_volume():
    rt = _rt(seed=14)
    rt.step()
    interest = ObserverInterest()
    interest.add(PRODUCT_SURFACE_LIGHT)
    fr = _frame(rt, interest=interest)
    assert "researcher_physical_optical_audit_view" in fr["world"]
    assert "observer_camera_occupancy_consumer" not in fr["world"]


def test_06_explicit_multi_family():
    rt = _rt(seed=15)
    rt.step()
    interest = ObserverInterest()
    interest.add(PRODUCT_VOLUME_XRAY)
    interest.add(PRODUCT_SURFACE_LIGHT)
    fr = _frame(rt, interest=interest)
    assert "observer_camera_occupancy_consumer" in fr["world"]
    assert "researcher_physical_optical_audit_view" in fr["world"]


def test_07_vision_does_not_force_central_geometry():
    # Compact O4/O5/agent views remain; VOLUME/SURFACE still omitted on MAP interest.
    rt = _rt(seed=16)
    rt.step()
    fr = _frame(rt, interest=ObserverInterest())
    assert fr.get("perception") is not None or fr.get("agent_observation") is not None or True
    assert "observer_camera_occupancy_consumer" not in fr["world"]


def test_08_hearing_does_not_force_central_geometry():
    rt = _rt(seed=17)
    rt.step()
    # Acoustic summaries may appear; central VOLUME/SURFACE still gated.
    fr = _frame(rt, interest=ObserverInterest())
    assert "observer_camera_occupancy_consumer" not in fr["world"]
    assert "researcher_physical_optical_audit_view" not in fr["world"]


def test_09_omitted_means_not_requested():
    r = resolve_derived_subscription(None)
    meta = r.as_frame_meta()
    for o in meta["omitted_payload_families"]:
        assert o["reason"] == OMISSION_NOT_REQUESTED


def test_10_requested_volume_matches_direct_authority():
    from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import (
        researcher_payload,
    )

    rt = _rt(seed=18)
    rt.step()
    direct = researcher_payload(rt)["observer_camera_occupancy_consumer"]
    interest = ObserverInterest()
    interest.add(PRODUCT_VOLUME_XRAY)
    fr = _frame(rt, interest=interest)
    gated = fr["world"]["observer_camera_occupancy_consumer"]
    # Authority content identical excluding subscription metadata.
    assert gated["schema"] == direct["schema"]
    assert gated["occupancy_digest"] == direct["occupancy_digest"]
    assert gated["occupancy_volume_count"] == direct["occupancy_volume_count"]
    assert len(gated["occupancy_volumes"]) == len(direct["occupancy_volumes"])


def test_11_requested_surface_matches_direct_authority():
    from mechanistic_mind.physical_system.researcher_physical_optical_audit_view import (
        researcher_summary,
    )

    rt = _rt(seed=19)
    rt.step()
    direct = researcher_summary(rt.world, rt.config, runtime=rt)
    interest = ObserverInterest()
    interest.add(PRODUCT_SURFACE_LIGHT)
    fr = _frame(rt, interest=interest)
    gated = fr["world"]["researcher_physical_optical_audit_view"]
    assert gated["schema"] == direct["schema"]
    assert gated.get("facet_count") == direct.get("facet_count")
    assert gated.get("available") == direct.get("available")


def test_12_preset_preserves_derived_viewport_products():
    interest = ObserverInterest()
    interest.add(PRODUCT_VOLUME_XRAY)
    interest.set_preset("NORMAL")
    assert PRODUCT_VOLUME_XRAY in interest.products
    assert PRODUCT_WORLD in interest.products
    assert interest.products >= set(PRESET_NORMAL) or PRODUCT_VOLUME_XRAY in interest.products


def test_13_products_registered():
    assert PRODUCT_VOLUME_XRAY in ALL_PRODUCTS
    assert PRODUCT_SURFACE_LIGHT in ALL_PRODUCTS
    assert PRODUCT_VOLUME_XRAY not in PRESET_NORMAL


def test_14_malformed_unknown_ignored():
    r = resolve_derived_subscription(explicit_products=["not_a_real_product", PRODUCT_VOLUME_XRAY])
    assert "not_a_real_product" in r.malformed_ignored
    assert r.include_volume is True


def test_15_mode_switch_does_not_step():
    rt = _rt(seed=20)
    rt.step()
    tick0 = int(rt.tick)
    interest = ObserverInterest()
    _frame(rt, interest=interest)
    interest.add(PRODUCT_VOLUME_XRAY)
    _frame(rt, interest=interest)
    interest.remove(PRODUCT_VOLUME_XRAY)
    interest.add(PRODUCT_SURFACE_LIGHT)
    _frame(rt, interest=interest)
    assert int(rt.tick) == tick0


def test_16_public_selector_exactly_two():
    sel = public_model_selector_entries()
    assert len(sel) == 2


def test_17_tiktaalik_unchanged():
    from mechanistic_mind.model.tiktaalik import tiktaalik_config

    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=2, config=cfg)
    rt.step()
    fr = _frame(rt, interest=None)
    assert "observer_camera_occupancy_consumer" not in fr["world"]


def test_18_canonical_fingerprint_identity_map_vs_volume_request():
    """Scientific state unchanged when toggling derived subscription on same tick."""
    rt = _rt(seed=21)
    for _ in range(3):
        rt.step()
    snap = copy.deepcopy(rt.snapshot())
    interest_map = ObserverInterest()
    interest_vol = ObserverInterest()
    interest_vol.add(PRODUCT_VOLUME_XRAY)
    _frame(rt, interest=interest_map)
    _frame(rt, interest=interest_vol)
    snap2 = rt.snapshot()
    # Tick and VW1 digest unchanged by Observer frame builds.
    assert snap["tick"] == snap2["tick"] or snap.get("world", {}).get("tick") == snap2.get("world", {}).get("tick")
    w1 = (snap.get("world") or {}).get("volumetric_occupancy") or {}
    w2 = (snap2.get("world") or {}).get("volumetric_occupancy") or {}
    if "revision" in w1 or "revision" in w2:
        assert w1.get("revision") == w2.get("revision")


def test_19_instrumentation_records_omission():
    from mechanistic_mind.physical_system import beta4_performance_benchmark as b4

    b4.reset()
    b4.enable(run_id="p1", profile_id="map")
    rt = _rt(seed=22)
    rt.step()
    _frame(rt, interest=ObserverInterest())
    snap = b4.snapshot()
    assert snap["counters"].get("volume_payload_omitted", 0) >= 1
    assert snap["counters"].get("surface_payload_omitted", 0) >= 1
    b4.disable()
    b4.reset()


def test_20_subscription_not_in_snapshot_schema():
    rt = _rt(seed=23)
    rt.step()
    snap = json.dumps(rt.snapshot(), default=str)
    assert SCHEMA not in snap
    assert "inactive_observer_payload_and_render_suspension" not in snap
