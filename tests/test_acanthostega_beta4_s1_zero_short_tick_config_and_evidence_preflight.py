"""Focused S1 preflight tests — digests/ambiguity only (no long runs).

PSC schedule short probe is covered by the experiment harness under the S1 tick budget.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "run_acanthostega_beta4_s1_zero_short_tick_config_and_evidence_preflight.py"


def _load():
    spec = importlib.util.spec_from_file_location("s1_preflight", EXP)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def s1():
    return _load()


def test_authoritative_condition_count_is_nine(s1):
    assert len(s1.AUTHORITATIVE_CONDITIONS) == 9


def test_ambiguous_conditions_are_c4_c7_c8(s1):
    amb = {c["condition_id"] for c in s1.AUTHORITATIVE_CONDITIONS if not c["uniquely_defined"]}
    assert amb == {"C4", "C7", "C8"}


def test_causal_digests_deterministic_and_seed_sensitive(s1):
    a = s1.build_condition_config("C1", seed=17)
    b = s1.build_condition_config("C1", seed=17)
    c0 = s1.build_condition_config("C0", seed=17)
    c3 = s1.build_condition_config("C3", seed=17)
    c1b = s1.build_condition_config("C1", seed=111)
    for x in (a, b, c0, c3, c1b):
        x.pop("runtime_cfg_handle", None)
    assert a["digest"] == b["digest"]
    assert a["digest"] != c0["digest"]
    assert a["digest"] == c3["digest"]
    assert a["digest"] != c1b["digest"]


def test_ambiguous_conditions_have_null_digest(s1):
    for cid in ("C4", "C7", "C8"):
        built = s1.build_condition_config(cid, seed=17)
        built.pop("runtime_cfg_handle", None)
        assert built["status"] == "AMBIGUOUS"
        assert built["digest"] is None


def test_vision_hearing_z_ablations_selective(s1):
    abl = s1.causal_ablation_readiness()
    assert abl["VISION_CAUSAL_CONTROL"]["ready"] is True
    assert abl["HEARING_CAUSAL_CONTROL"]["ready"] is True
    assert abl["EFFECTOR_Z_CAUSAL_CONTROL"]["ready"] is True
    assert abl["SIGNALING_CAUSAL_CONTROL"]["ready"] is True
    assert abl["PSC_CAUSAL_CONTROL"]["ready"] is False
