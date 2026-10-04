"""AGENT_ACCESSIBLE_EFFECTOR_RELATIVE_Z_CONTROL_V1 — focused tests.

Option A: independent ternary per-hand effector_z side-channels → EBAE.
Budget: keep total simulated ticks well under 180.
"""
from __future__ import annotations

from copy import deepcopy

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _beta4_cfg(*, cognition: bool = False):
    from mechanistic_mind.model.acanthostega import acanthostega_beta4_config

    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = bool(cognition)
    return cfg


def _rt(seed: int = 17, *, cognition: bool = False):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    return PhysicalSystemRuntime(seed=seed, config=_beta4_cfg(cognition=cognition))


def _bid(rt) -> str:
    from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

    return body_refs_for_runtime(rt)[0][0]


def _motor(*, zl: int = 0, zr: int = 0, loco: str = "WAIT", osc_fd: int = 0):
    from mechanistic_mind.physical_system.composite_motor import (
        CompositeMotorOutput,
        OscillatorMotorComponent,
    )

    motor = CompositeMotorOutput(
        locomotion=loco,
        oscillator=OscillatorMotorComponent(frequency_delta=int(osc_fd)),
        effector_z_left=int(zl),
        effector_z_right=int(zr),
    )
    motor.legacy_token = motor.compute_legacy_token()
    return motor


def _step_forced(rt, *, zl: int = 0, zr: int = 0, loco: str = "WAIT", osc_fd: int = 0):
    rt.step_forced_motor(_motor(zl=zl, zr=zr, loco=loco, osc_fd=osc_fd))
    _tick()


# ---------------------------------------------------------------------------
# SCHEMA / AVAILABILITY
# ---------------------------------------------------------------------------


def test_beta4_exposes_effector_z_factors():
    from mechanistic_mind.physical_system.actions import EFFECTOR_Z_ACTIONS

    rt = _rt()
    rt._sync_embodiment_dofs()
    acts = set(rt.cognition.get("available_actions") or [])
    for a in EFFECTOR_Z_ACTIONS:
        assert a in acts, a


def test_tiktaalik_lacks_effector_z_factors():
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.actions import EFFECTOR_Z_ACTIONS
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=3, config=tiktaalik_config())
    rt._sync_embodiment_dofs()
    acts = set(rt.cognition.get("available_actions") or [])
    for a in EFFECTOR_Z_ACTIONS:
        assert a not in acts, a


def test_public_selector_still_two_models():
    from mechanistic_mind.physical_system.experiment_canonical import public_model_selector_entries

    entries = public_model_selector_entries()
    labels = [str(e.get("label") or "") for e in entries]
    assert labels == ["Tiktaalik Beta 3.1", "Acanthostega Beta 4.0"]
    assert len(entries) == 2


def test_factors_are_ternary_and_none_unique():
    from mechanistic_mind.physical_system.composite_motor import CompositeMotorOutput
    from mechanistic_mind.physical_system.sensorimotor_consequence import (
        motor_signature_from_composite,
    )

    none_sig = motor_signature_from_composite(CompositeMotorOutput().to_dict())
    none_sig2 = motor_signature_from_composite(
        {
            "locomotion": "WAIT",
            "neck": "NONE",
            "oscillator": {},
            "push": False,
            "effector_z_left": 0,
            "effector_z_right": 0,
        }
    )
    assert none_sig == none_sig2
    assert "|ZL:0|ZR:0" in none_sig


# ---------------------------------------------------------------------------
# IDENTITY
# ---------------------------------------------------------------------------


def test_motor_identity_hand_and_direction():
    from mechanistic_mind.physical_system.sensorimotor_consequence import (
        motor_signature_from_composite,
    )

    def sig(zl=0, zr=0, loco="WAIT", push=False, fd=0):
        return motor_signature_from_composite(
            {
                "locomotion": loco,
                "neck": "NONE",
                "oscillator": {
                    "frequency_delta": fd,
                    "amplitude_delta": 0,
                    "emit_trigger": False,
                },
                "push": push,
                "effector_z_left": zl,
                "effector_z_right": zr,
            }
        )

    assert sig(zl=1) != sig(zl=-1)
    assert sig(zl=1) != sig(zr=1)
    assert sig(zl=1, zr=-1) != sig(zl=-1, zr=1)
    assert sig(zl=1, zr=1) != sig(zl=-1, zr=-1)
    assert sig(zl=1, loco="MOVE:N") != sig(zl=1, loco="WAIT")
    assert sig(zl=1, fd=1) != sig(zl=1, fd=0)
    assert sig() == sig()


# ---------------------------------------------------------------------------
# PHYSICAL REALIZATION
# ---------------------------------------------------------------------------


def test_left_down_requests_ebae_and_sign():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        relative_z_of,
    )

    rt = _rt()
    before = float(relative_z_of(rt.world, _bid(rt), "LEFT", config=rt.config))
    _step_forced(rt, zl=-1)
    after = float(relative_z_of(rt.world, _bid(rt), "LEFT", config=rt.config))
    assert after < before - 1e-12
    act = getattr(rt, "last_agent_effector_z_actuation", {}) or {}
    left = act.get("left") or {}
    assert float(left.get("requested_relative_delta") or 0.0) < 0.0
    assert act.get("right") is None


def test_right_up_sign_and_none_no_request():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        relative_z_of,
    )

    rt = _rt()
    before = float(relative_z_of(rt.world, _bid(rt), "RIGHT", config=rt.config))
    _step_forced(rt, zr=1)
    after = float(relative_z_of(rt.world, _bid(rt), "RIGHT", config=rt.config))
    assert after > before + 1e-12
    _step_forced(rt, zr=0)
    act = getattr(rt, "last_agent_effector_z_actuation", {}) or {}
    assert act.get("status") == "NONE"
    held = float(relative_z_of(rt.world, _bid(rt), "RIGHT", config=rt.config))
    assert abs(held - after) < 1e-12


def test_bounds_and_rate_preserved():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        DEFAULT_MAX_DELTA_Z_PER_TICK,
        DEFAULT_MAX_RELATIVE_Z,
        relative_z_of,
    )

    rt = _rt()
    for _ in range(12):
        _step_forced(rt, zl=-1)
    z = float(relative_z_of(rt.world, _bid(rt), "LEFT", config=rt.config))
    assert z >= -DEFAULT_MAX_RELATIVE_Z - 1e-9
    assert z <= DEFAULT_MAX_RELATIVE_Z + 1e-9
    before = z
    _step_forced(rt, zl=-1)
    after = float(relative_z_of(rt.world, _bid(rt), "LEFT", config=rt.config))
    assert abs(after - before) <= DEFAULT_MAX_DELTA_Z_PER_TICK + 1e-9


def test_bilateral_independent():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        relative_z_of,
    )

    rt = _rt()
    _step_forced(rt, zl=-1, zr=1)
    zl = float(relative_z_of(rt.world, _bid(rt), "LEFT", config=rt.config))
    zr = float(relative_z_of(rt.world, _bid(rt), "RIGHT", config=rt.config))
    assert zl < 0
    assert zr > 0
    act = getattr(rt, "last_agent_effector_z_actuation", {}) or {}
    assert act.get("left") is not None and act.get("right") is not None


def test_move_plus_z_and_osc_coexist():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        relative_z_of,
    )
    from mechanistic_mind.physical_system.sensorimotor_consequence import (
        motor_signature_from_composite,
    )

    rt = _rt()
    _step_forced(rt, zl=-1, loco="MOVE:N", osc_fd=1)
    z = float(relative_z_of(rt.world, _bid(rt), "LEFT", config=rt.config))
    assert z < 0
    sig = motor_signature_from_composite(rt.last_motor_output)
    assert "L:MOVE:N" in sig and "ZL:-1" in sig and "F:1" in sig


# ---------------------------------------------------------------------------
# MULTI-TICK CONTACT
# ---------------------------------------------------------------------------


def test_one_down_no_contact_multi_tick_reaches():
    rt = _rt()
    _step_forced(rt, zl=-1)
    last = getattr(rt.world, "last_effector_terrain_contact_step", None) or {}
    left_contact_one = any(
        r.get("contact_fact") and str(r.get("effector_id")) == "LEFT"
        for r in (last.get("receipts") or [])
    )
    assert not left_contact_one

    saw_contact = False
    for _ in range(12):
        _step_forced(rt, zl=-1)
        last = getattr(rt.world, "last_effector_terrain_contact_step", None) or {}
        if any(
            r.get("contact_fact") and str(r.get("effector_id")) == "LEFT"
            for r in (last.get("receipts") or [])
        ):
            saw_contact = True
            break
    assert saw_contact, "LEFT DOWN multi-tick should produce ETC contact"


def test_right_multi_tick_contact():
    rt = _rt()
    saw = False
    for _ in range(12):
        _step_forced(rt, zr=-1)
        last = getattr(rt.world, "last_effector_terrain_contact_step", None) or {}
        if any(
            r.get("contact_fact") and str(r.get("effector_id")) == "RIGHT"
            for r in (last.get("receipts") or [])
        ):
            saw = True
            break
    assert saw


# ---------------------------------------------------------------------------
# SNAPSHOT / PRIVACY / ANALYZER
# ---------------------------------------------------------------------------


def test_snapshot_restore_no_replay():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        relative_z_of,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = _rt()
    for _ in range(3):
        _step_forced(rt, zl=-1)
    z = float(relative_z_of(rt.world, _bid(rt), "LEFT", config=rt.config))
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(deepcopy(snap))
    z2 = float(relative_z_of(rt2.world, _bid(rt2), "LEFT", config=rt2.config))
    assert abs(z2 - z) < 1e-12


def test_privacy_forbidden_tokens_cover_relative_z():
    from mechanistic_mind.physical_system.observation import (
        FORBIDDEN_TOKENS,
        audit_cognition_payload,
    )

    for tok in ("relative_z", "signed_minimum_separation", "requested_relative_delta"):
        assert tok in FORBIDDEN_TOKENS
    hits = audit_cognition_payload({"relative_z": 0.5, "vision": 1.0})
    assert "relative_z" in hits


def test_eort_agent_selectable_present_on_beta4():
    from mechanistic_mind.physical_system.effector_occupancy_reachability_trace import (
        _agent_selectable_relative_z,
    )

    rt = _rt()
    rt._sync_embodiment_dofs()
    assert _agent_selectable_relative_z(rt.config, rt) is True


def test_analyzer_not_selected_when_available():
    from mechanistic_mind.scientific_v3.analyzer_next.volumetric_physical_causal_reconstruction import (
        classify_story_physical,
    )

    class _Story:
        tick = 0
        cognitive_agent_id = "a0"
        physical_body_id = "agent_0"
        observation_id = "o"
        motor = {
            "components": {
                "locomotion": "WAIT",
                "effector_z_left": 0,
                "effector_z_right": 0,
            }
        }

    out = classify_story_physical(
        _Story(),
        reach_traces=[
            {
                "tick": 0,
                "body_id": "agent_0",
                "physical_relative_z_dof": "AVAILABLE",
                "agent_selectable_motor_factor": "PRESENT",
                "relative_z": 0.0,
                "geometric_reach": False,
            }
        ],
        etc_contacts=[],
        work_rows=[],
        wmt_rows=[],
        model={"volumetric_physical_story": "APPLICABLE", "is_acanthostega_beta4": True},
    )
    assert out.get("negative_cause") == "NOT_SELECTED"


def test_ordinary_cognition_path_can_include_factor():
    """Short ordinary run: factors available; utilization may be zero (honest)."""
    from mechanistic_mind.physical_system.actions import EFFECTOR_Z_ACTIONS

    rt = _rt(cognition=True)
    rt._sync_embodiment_dofs()
    acts = set(rt.cognition.get("available_actions") or [])
    assert set(EFFECTOR_Z_ACTIONS).issubset(acts)
    for _ in range(5):
        rt.step()
        _tick()
    # Do not require selection; just ensure no crash and repertoire remains.
    rt._sync_embodiment_dofs()
    assert set(EFFECTOR_Z_ACTIONS).issubset(set(rt.cognition.get("available_actions") or []))


def test_tick_budget_cap():
    assert TICKS["n"] <= 180
