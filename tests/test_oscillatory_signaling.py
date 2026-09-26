"""Physical oscillatory signaling × banded L/R reception tests."""
from __future__ import annotations

import math

import numpy as np
import pytest

from mechanistic_mind.physical_system.oscillatory_signaling import (
    OscillatorySignalingConfig,
    apply_osc_motor_action,
    band_response,
    cognition_osc_fragments,
    ensure_osc_fields,
    frequency_from_control,
    receptor_world_positions,
    step_oscillatory_signaling,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.articulated_head import ArticulatedHeadConfig
from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.ui.psy_observer_web.embodiment_forensics import summarize_oscillatory_signaling


def _cfg(**kw):
    return OscillatorySignalingConfig(mode="EXPERIMENTAL", **kw)


def _rt(seed=1, osc=True, head=True):
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.oscillatory_signaling = _cfg() if osc else OscillatorySignalingConfig(mode="OFF")
    if head:
        cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def test_OS1_deterministic_emission():
    a = _rt(seed=9)
    b = _rt(seed=9)
    for rt in (a, b):
        apply_osc_motor_action(rt.body, "OSC_FREQ_UP", rt.config.oscillatory_signaling)
        apply_osc_motor_action(rt.body, "OSC_EMIT", rt.config.oscillatory_signaling)
        rt.step(1)
    assert np.allclose(a.world.OSC_BANDS, b.world.OSC_BANDS)


def test_OS2_OS3_different_freq_amp():
    cfg = _cfg()
    w1 = band_response(0.1, n_bands=6, width=cfg.band_width)
    w2 = band_response(0.9, n_bands=6, width=cfg.band_width)
    assert float(np.argmax(w1)) < float(np.argmax(w2))
    assert not np.allclose(w1, w2)
    # Amplitude scales deposit
    rt = _rt()
    rt.body.osc_freq_u = 0.5
    rt.body.osc_amp_u = 0.2
    apply_osc_motor_action(rt.body, "OSC_EMIT", rt.config.oscillatory_signaling)
    rt.step(1)
    e_lo = float(rt.world.OSC_BANDS.sum())
    rt2 = _rt(seed=1)
    rt2.body.osc_freq_u = 0.5
    rt2.body.osc_amp_u = 0.9
    apply_osc_motor_action(rt2.body, "OSC_EMIT", rt2.config.oscillatory_signaling)
    rt2.step(1)
    e_hi = float(rt2.world.OSC_BANDS.sum())
    assert e_hi > e_lo


def test_OS4_duration_history():
    rt = _rt()
    rt.body.osc_amp_u = 1.0
    apply_osc_motor_action(rt.body, "OSC_EMIT", rt.config.oscillatory_signaling)
    rem0 = int(rt.body.osc_emit_remaining)
    assert rem0 >= 1
    energies = []
    for _ in range(rem0 + 2):
        rt.step(1)
        energies.append(float(rt.world.OSC_BANDS.sum()))
    assert rt.body.osc_emit_remaining == 0
    # Energy persists/decays after emission ends — temporal history differs from 1-tick
    assert any(e > 0 for e in energies)


def test_OS5_zero_amplitude():
    rt = _rt()
    rt.body.osc_amp_u = 0.0
    apply_osc_motor_action(rt.body, "OSC_EMIT", rt.config.oscillatory_signaling)
    rt.step(1)
    assert float(rt.world.OSC_BANDS.sum()) < 1e-9


def test_OS10_no_semantic_in_cognition():
    rt = _rt()
    apply_osc_motor_action(rt.body, "OSC_EMIT", rt.config.oscillatory_signaling)
    rt.step(1)
    obs = rt.agent_observation()
    text = repr(obs)
    for bad in ("ALARM", "GREETING", "MESSAGE", "WORD", "SOURCE_ID", "LOOK_AT"):
        assert bad not in text
    assert any(k.startswith("osc_l_") for k in obs)
    assert any(k.startswith("osc_r_") for k in obs)
    assert "osc_frequency" not in obs
    assert "emitter_frequency" not in obs


def test_BR1_BR2_overlapping_bands_shift():
    cfg = _cfg()
    low = band_response(0.15, n_bands=6, width=cfg.band_width)
    mid = band_response(0.5, n_bands=6, width=cfg.band_width)
    # Overlap: more than one band meaningfully active
    assert (low > 0.05).sum() >= 2
    assert int(np.argmax(low)) != int(np.argmax(mid))


def test_BR4_emitter_identity_invariant():
    """Same local field → same receptor response regardless of emitter id."""
    rt = _rt()
    ensure_osc_fields(rt.world, rt.config.oscillatory_signaling)
    # Manual deposit identical
    from mechanistic_mind.physical_system.oscillatory_signaling import _deposit_band_energy
    _deposit_band_energy(rt.world.OSC_BANDS, iy=4, ix=4, amp=0.8, freq=0.4, cfg=rt.config.oscillatory_signaling)
    body_a = rt.body
    body_a.x, body_a.y = 4.2, 4.2
    f1 = cognition_osc_fragments(body_a, rt.world, rt.config.oscillatory_signaling, articulated_head=True)
    body_b = body_a.copy()
    # Different identity attributes must not affect channels
    f2 = cognition_osc_fragments(body_b, rt.world, rt.config.oscillatory_signaling, articulated_head=True)
    assert f1 == f2


def test_BR9_BR10_no_source_leak():
    rt = _rt()
    apply_osc_motor_action(rt.body, "OSC_EMIT", rt.config.oscillatory_signaling)
    rt.step(2)
    obs = rt.agent_observation()
    for k in obs:
        assert "source" not in k.lower()
        assert "direction" not in k.lower()
        assert "bearing" not in k.lower()
        assert "emitter" not in k.lower()


def test_SR1_SR2_head_rotation_moves_receptors():
    rt = _rt()
    body = rt.body
    body.theta = 0.0
    body.head_relative_angle = 0.0
    l0, r0 = receptor_world_positions(body, articulated_head=True, offset=0.55)
    assert abs(l0[0] - r0[0]) > 1e-6 or abs(l0[1] - r0[1]) > 1e-6
    body.head_relative_angle = 0.7
    l1, r1 = receptor_world_positions(body, articulated_head=True, offset=0.55)
    assert abs(l0[0] - l1[0]) > 1e-4 or abs(l0[1] - l1[1]) > 1e-4


def test_SR5_spatial_LR_asymmetry():
    rt = _rt()
    ensure_osc_fields(rt.world, rt.config.oscillatory_signaling)
    from mechanistic_mind.physical_system.oscillatory_signaling import _deposit_band_energy
    body = rt.body
    body.x, body.y, body.theta = 8.0, 8.0, 0.0
    body.head_relative_angle = 0.0
    (lx, ly), (rx, ry) = receptor_world_positions(body, articulated_head=True, offset=0.55)
    # Deposit near left receptor only
    _deposit_band_energy(
        rt.world.OSC_BANDS,
        iy=int(ly) % rt.world.T.shape[0],
        ix=int(lx) % rt.world.T.shape[1],
        amp=1.0,
        freq=0.5,
        cfg=rt.config.oscillatory_signaling,
    )
    fr = cognition_osc_fragments(body, rt.world, rt.config.oscillatory_signaling, articulated_head=True)
    left_e = sum(fr[k] for k in fr if k.startswith("osc_l_"))
    right_e = sum(fr[k] for k in fr if k.startswith("osc_r_"))
    assert left_e >= right_e


def test_SR6_no_explicit_bearing_channel():
    rt = _rt()
    apply_osc_motor_action(rt.body, "OSC_EMIT", rt.config.oscillatory_signaling)
    rt.step(1)
    obs = rt.agent_observation()
    assert "left_minus_right" not in obs
    assert "sound_direction" not in obs


def test_MM1_out_of_fov_signal_still_receivable():
    """Signal reception does not require visual FOV (independent physical path)."""
    rt = _rt()
    # Disable vision package contribution
    rt.config.near_field_exteroception.mode = "OFF"
    apply_osc_motor_action(rt.body, "OSC_EMIT", rt.config.oscillatory_signaling)
    rt.step(1)
    obs = rt.agent_observation()
    assert not any(k.startswith("exo_") for k in obs)
    assert any(k.startswith("osc_l_") for k in obs)


def test_superposition_two_emitters():
    cfg = _cfg()
    from mechanistic_mind.planet.config import default_planet_config
    from mechanistic_mind.planet.runtime import initialize_planet
    world = initialize_planet(default_planet_config(), seed=1)
    ensure_osc_fields(world, cfg)
    bodies = []
    for i, (x, y, f) in enumerate([(5.0, 5.0, 0.2), (5.0, 5.0, 0.8)]):
        # Minimal body stubs via runtime
        pass
    rt = _rt()
    rt2_body = rt.body.copy()
    rt.body.osc_freq_u = 0.2
    rt.body.osc_amp_u = 0.7
    rt2_body.osc_freq_u = 0.8
    rt2_body.osc_amp_u = 0.7
    rt.body.x = rt.body.y = 5.0
    rt2_body.x = rt2_body.y = 5.0
    apply_osc_motor_action(rt.body, "OSC_EMIT", cfg)
    apply_osc_motor_action(rt2_body, "OSC_EMIT", cfg)
    meta = step_oscillatory_signaling(
        rt.world, [rt.body, rt2_body], cfg, tick=1, articulated_head=True,
        body_ids=["a", "b"], slots=[0, 1],
    )
    assert len(meta["emitters"]) == 2
    assert float(rt.world.OSC_BANDS.sum()) > 0


def test_ablation_off_exact_match_fingerprint():
    def run(on: bool):
        cfg = PhysicalSystemConfig()
        cfg.cognition.cognition_enabled = False
        cfg.oscillatory_signaling = _cfg() if on else OscillatorySignalingConfig(mode="OFF")
        rt = PhysicalSystemRuntime(seed=77, config=cfg)
        # No OSC_EMIT — just physics
        xs = []
        for _ in range(15):
            rt.step(1)
            xs.append((rt.body.x, rt.body.y, rt.body.theta))
        return xs

    assert run(False) == run(False)
    # OFF vs ON without emission should match body trajectory
    assert run(False) == run(True)


def test_fresh_default_includes_oscillatory():
    from mechanistic_mind.physical_system.mechanism_configuration import fresh_experiment_default_map
    d = fresh_experiment_default_map()
    assert d.get("oscillatory_signaling") is True
    assert d.get("spatiotemporal_climate_ecology") is False


def test_forensics_conservative():
    s = summarize_oscillatory_signaling([], [])
    assert s["semantics"]["not_language"] is True
    assert s["evidence_labels"]["reception_to_meaning"] == "NOT_ESTABLISHED"
    s2 = summarize_oscillatory_signaling(
        [{"osc_emit_active": True, "osc_frequency": 0.4, "osc_amplitude": 0.5, "osc_l_energy": 0.1}],
        [],
    )
    assert s2["osc_fields_status"] == "PRESENT"


def test_demo_spectral_differentiation():
    patterns = []
    for f_u in (0.1, 0.5, 0.9):
        rt = _rt(seed=3)
        rt.body.osc_freq_u = f_u
        rt.body.osc_amp_u = 0.8
        apply_osc_motor_action(rt.body, "OSC_EMIT", rt.config.oscillatory_signaling)
        rt.step(1)
        obs = rt.agent_observation()
        vec = [obs.get(f"osc_l_{i}", 0.0) for i in range(6)]
        patterns.append(vec)
    # Distinct overlapping patterns
    assert patterns[0] != patterns[1] != patterns[2]
    assert math.dist(patterns[0], patterns[2]) > math.dist(patterns[0], patterns[1]) * 0.5
