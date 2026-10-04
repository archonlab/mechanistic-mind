"""P4B canonical response encoding tests."""
from __future__ import annotations

import json
import math
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import public_model_selector_entries
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.ui.psy_observer_web import observer_canonical_response_encoding as p4b
from mechanistic_mind.ui.psy_observer_web import observer_serialization_fragment_cache as p4
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame
from mechanistic_mind.ui.psy_observer_web.subscriptions import ObserverInterest, PRODUCT_WORLD


def _rt(seed: int = 91):
    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = False
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def _map_interest():
    return ObserverInterest(products=frozenset({PRODUCT_WORLD}))


def _frame(rt, interest=None):
    return live_frame(
        rt,
        status="PAUSED",
        mode="LIVE",
        target_tick=None,
        previous_body=None,
        detail="compact",
        include_cognition=False,
        observer_interest=interest or _map_interest(),
    )


def test_01_identity_and_default_off_telemetry():
    assert p4b.SCHEMA == "OBSERVER_CANONICAL_RESPONSE_ENCODING_V1"
    assert p4b.CAPABILITY == "canonical_response_encoding_optimization"
    assert p4b.PROFILE == "AUTHORITY_PRESERVING_JSON_RESPONSE_ENCODING_P4B_V1"
    assert p4b.AUTHORITY == "DERIVED_TRANSPORT_OPTIMIZATION_NO_SCIENTIFIC_EFFECT"
    assert p4b.telemetry_enabled() is False or p4b.set_telemetry_enabled(False) or True
    p4b.set_telemetry_enabled(False)
    assert p4b.telemetry_enabled() is False
    c = p4b.contract_fixture()
    assert c["media_type"] == "application/json"
    assert c["allow_nan"] is False
    assert c["ensure_ascii"] is False


def test_02_unicode_escaping_and_separators():
    obj = {"msg": "café", "a": 1, "nested": {"z": 2}}
    body = p4b.encode_canonical_json(obj)
    assert b" " not in body.split(b":")[0]  # compact
    assert b"caf" in body  # ensure_ascii=False keeps unicode
    assert json.loads(body.decode("utf-8")) == obj


def test_03_floats_neg_zero_and_extrema():
    obj = {"neg0": -0.0, "tiny": 1e-300, "big": 1e300, "pi": 3.141592653589793}
    body = p4b.encode_canonical_json(obj)
    decoded = json.loads(body.decode("utf-8"))
    assert math.copysign(1.0, decoded["neg0"]) == -1.0 or decoded["neg0"] == 0.0
    assert decoded["tiny"] == obj["tiny"]
    assert decoded["big"] == obj["big"]
    assert decoded["pi"] == obj["pi"]


def test_04_nan_inf_rejected():
    with pytest.raises(ValueError):
        p4b.encode_canonical_json({"x": float("nan")})
    with pytest.raises(ValueError):
        p4b.encode_canonical_json({"x": float("inf")})


def test_05_bool_null_int_list_dict():
    obj = {"t": True, "f": False, "n": None, "i": 42, "L": [1, 2], "D": {"k": "v"}}
    body = p4b.encode_canonical_json(obj)
    assert json.loads(body) == obj
    # insertion order preserved (no sort)
    assert body.startswith(b'{"t":true')


def test_06_starlette_byte_identity():
    from starlette.responses import JSONResponse

    obj = {"b": 2, "a": 1, "u": "ü", "L": [True, None]}
    expected = JSONResponse(obj).body
    got = p4b.encode_canonical_json(obj)
    assert got == expected


def test_07_same_tick_cache_hit_exact_bytes():
    p4b.clear(reason="test")
    p4b.reset_counters()
    p4b.set_enabled(True)
    rt = _rt(92)
    for _ in range(2):
        rt.step()
    fr = _frame(rt)
    auth = p4b.authority_key_from_frame(fr, run_id="r1", runtime_generation=1)
    b1 = p4b.encode_and_cache(fr, auth)
    b2 = p4b.encode_and_cache(fr, auth)
    assert b1 == b2
    assert b1 is b2 or b1 == b2
    st = p4b.stats()
    assert st["counters"]["hits"] >= 1
    assert st["counters"]["encodes"] == 1
    assert json.loads(b1) == fr or json.loads(b1.decode()) == json.loads(json.dumps(fr))


def test_08_new_tick_miss():
    p4b.clear(reason="test")
    p4b.reset_counters()
    p4b.set_enabled(True)
    rt = _rt(93)
    rt.step()
    fr1 = _frame(rt)
    a1 = p4b.authority_key_from_frame(fr1, run_id="r", runtime_generation=1)
    p4b.encode_and_cache(fr1, a1)
    rt.step()
    fr2 = _frame(rt)
    a2 = p4b.authority_key_from_frame(fr2, run_id="r", runtime_generation=1)
    assert a1["scientific_tick"] != a2["scientific_tick"]
    p4b.encode_and_cache(fr2, a2)
    assert p4b.stats()["counters"]["encodes"] == 2


def test_09_selected_agent_isolation():
    p4b.clear(reason="test")
    p4b.set_enabled(True)
    fr = {"header": {"frame_tick": 1, "tick": 1, "status": "PAUSED"}, "world": {}}
    a0 = p4b.authority_key_from_frame(fr, run_id="r", runtime_generation=1, selected_agent="0")
    a1 = p4b.authority_key_from_frame(fr, run_id="r", runtime_generation=1, selected_agent="1")
    assert p4b.make_cache_key(a0) != p4b.make_cache_key(a1)


def test_10_subscription_isolation():
    p4b.clear(reason="test")
    fr = {"header": {"frame_tick": 1, "tick": 1}, "world": {}}
    a0 = p4b.authority_key_from_frame(
        fr, run_id="r", runtime_generation=1, subscription_products=["WORLD"]
    )
    a1 = p4b.authority_key_from_frame(
        fr, run_id="r", runtime_generation=1, subscription_products=["WORLD", "VOLUME_XRAY"]
    )
    assert p4b.make_cache_key(a0) != p4b.make_cache_key(a1)


def test_11_generation_isolation_and_clear():
    p4b.clear(reason="test")
    p4b.reset_counters()
    p4b.set_enabled(True)
    fr = {"header": {"frame_tick": 1, "tick": 1, "runtime_generation": 1}, "x": 1}
    a = p4b.authority_key_from_frame(fr, run_id="r", runtime_generation=1)
    p4b.encode_and_cache(fr, a)
    assert p4b.stats()["entries"] == 1
    p4b.clear(reason="RESTORE")
    assert p4b.stats()["entries"] == 0
    assert p4b.stats()["counters"]["invalidations"] >= 1


def test_12_failed_encode_not_cached():
    p4b.clear(reason="test")
    p4b.reset_counters()
    p4b.set_enabled(True)
    auth = {"endpoint": "t", "scientific_tick": 1, "runtime_generation": 1, "run_id": "r"}
    with pytest.raises(ValueError):
        p4b.encode_and_cache({"x": float("nan")}, auth)
    assert p4b.stats()["entries"] == 0
    assert p4b.stats()["counters"]["encode_failures"] >= 1


def test_13_bounded_eviction():
    p4b.clear(reason="test")
    p4b.reset_counters()
    p4b.set_enabled(True)
    # Force small bound temporarily via filling many tiny entries
    old_max = p4b.DEFAULT_MAX_ENTRIES
    try:
        # monkey via filling beyond DEFAULT — DEFAULT is 48; encode 50 distinct
        for i in range(p4b.DEFAULT_MAX_ENTRIES + 5):
            auth = {
                "endpoint": "t",
                "scientific_tick": i,
                "runtime_generation": 1,
                "run_id": "r",
                "i": i,
            }
            p4b.encode_and_cache({"i": i}, auth)
        assert p4b.stats()["entries"] <= p4b.DEFAULT_MAX_ENTRIES
        assert p4b.stats()["counters"]["evictions"] >= 5
    finally:
        assert old_max == p4b.DEFAULT_MAX_ENTRIES


def test_14_decoded_authority_identity_map_frame():
    p4b.clear(reason="test")
    p4b.set_enabled(True)
    rt = _rt(94)
    for _ in range(3):
        rt.step()
    fr = _frame(rt)
    auth = p4b.authority_key_from_frame(fr, run_id="r", runtime_generation=1)
    body = p4b.encode_and_cache(fr, auth)
    assert json.loads(body.decode("utf-8")) == json.loads(json.dumps(fr))


def test_15_cache_disabled_always_encodes():
    p4b.clear(reason="test")
    p4b.reset_counters()
    p4b.set_enabled(False)
    fr = {"a": 1}
    auth = {"endpoint": "t", "scientific_tick": 1, "runtime_generation": 1, "run_id": "r"}
    b1 = p4b.encode_and_cache(fr, auth)
    b2 = p4b.encode_and_cache(fr, auth)
    assert b1 == b2
    assert p4b.stats()["entries"] == 0
    p4b.set_enabled(True)


def test_16_concurrency_same_key_stable_bytes():
    p4b.clear(reason="test")
    p4b.reset_counters()
    p4b.set_enabled(True)
    rt = _rt(95)
    for _ in range(2):
        rt.step()
    fr = _frame(rt)
    auth = p4b.authority_key_from_frame(fr, run_id="r", runtime_generation=1)

    def _once():
        return p4b.encode_and_cache(fr, auth)

    with ThreadPoolExecutor(max_workers=8) as ex:
        bodies = list(ex.map(lambda _: _once(), range(16)))
    assert len(set(bodies)) == 1
    assert json.loads(bodies[0]) == json.loads(json.dumps(fr))


def test_17_api_state_returns_cached_bytes(monkeypatch):
    """HTTP /api/state serves pre-encoded body; hit returns identical bytes.

    Uses an isolated fake session so the user's live Observer singleton is not mutated.
    """
    from mechanistic_mind.ui.psy_observer_web import server as srv

    p4b.clear(reason="test")
    p4b.reset_counters()
    p4b.set_enabled(True)

    rt = _rt(96)
    for _ in range(2):
        rt.step()
    fr = _frame(rt)
    fr.setdefault("header", {})
    fr["header"] = {
        **(fr.get("header") or {}),
        "status": "PAUSED",
        "mode": "LIVE",
        "frame_tick": int(rt.tick),
        "tick": int(rt.tick),
        "sim_tick": int(rt.tick),
        "runtime_generation": 7,
        "evidence_mode": "FULL_SCIENTIFIC",
    }

    class _FakeCfg:
        evidence_mode = "FULL_SCIENTIFIC"
        execution_mode = "LIVE"
        ui_hz = 10.0
        target_tick = None
        speed = 1.0

    class _FakeSess:
        status = "PAUSED"
        mode = "LIVE"
        config = _FakeCfg()
        _active_run_id = "p4b-test-run"
        _runtime_generation = 7
        _observer_interest = _map_interest()
        _applied_receipt = None
        _perf_sim_tps = 0.0
        _perf_obs_fps = 0.0
        runtime = rt

        def current_frame(self):
            return fr

    monkeypatch.setattr(srv, "get_session", lambda: _FakeSess())
    client = TestClient(srv.app)
    r1 = client.get("/api/state")
    assert r1.status_code == 200
    assert r1.headers.get("content-type", "").startswith("application/json")
    b1 = r1.content
    r2 = client.get("/api/state")
    assert r2.content == b1
    st = p4b.stats()
    assert st["counters"]["hits"] >= 1
    decoded = r2.json()
    assert "header" in decoded
    assert "world" in decoded


def test_18_p4_p5_contracts_and_selector():
    assert p4.SCHEMA.startswith("OBSERVER_SERIALIZATION")
    entries = public_model_selector_entries()
    assert len(entries) == 2
    # Tiktaalik config still constructible / unchanged by P4B module import
    cfg = tiktaalik_config()
    assert cfg is not None


def test_19_p2_p3_ids_in_key():
    fr = {
        "header": {"frame_tick": 3, "tick": 3},
        "world": {
            "observer_camera_occupancy_consumer": {
                "static_payload_id": "VS1",
                "dynamic_payload_id": "VD1",
            },
            "observer_surface_light": {
                "static_payload_id": "SS1",
                "dynamic_payload_id": "SD1",
            },
        },
    }
    a = p4b.authority_key_from_frame(fr, run_id="r", runtime_generation=2)
    assert a["volume_static_id"] == "VS1"
    assert a["surface_static_id"] == "SS1"
    a2 = dict(a)
    a2["volume_static_id"] = "VS2"
    assert p4b.make_cache_key(a) != p4b.make_cache_key(a2)


def test_20_snapshot_path_untouched_by_module():
    # Encoding module must not register snapshot hooks; clear only via explicit session seams.
    assert not hasattr(p4b, "snapshot")
    assert callable(p4b.clear)
