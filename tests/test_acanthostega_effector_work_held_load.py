"""ACANTHOSTEGA_PHASE_B_EFFECTOR_WORK_ACCOUNTING — effector work + held-load inertia V1."""
from __future__ import annotations

from mechanistic_mind.model.acanthostega import (
    acanthostega_effector_work_accounting_config,
    acanthostega_held_object_translational_impulse_config,
    model_metadata,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import effector_work_and_held_load_inertia_accounting as ehl
from mechanistic_mind.physical_system import held_resource_object_translational_impulse_mediation as hti
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING,
    PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION,
    PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.physical_manipulator import (
    MANIP_LEFT,
    MANIP_RIGHT,
    apply_pair_actuation,
    ensure_pair_runtime,
    update_held_kinematics,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

MID = ehl.MECHANISM_ID


def _place_object(rt, idx, x, y, *, state="FREE_STATIC", vx=0.0, vy=0.0,
                  holder=None, hand=None, mass=None):
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    assert len(objs) > idx
    o = objs[idx]
    o.x, o.y = float(x), float(y)
    o.vx, o.vy = float(vx), float(vy)
    o.physical_state = state
    o.holder_body_id = holder
    o.manipulator_id = hand
    if mass is not None:
        o.mass = float(mass)
    return o


def _place_body(rt, x, y, *, vx=0.0, vy=0.0, theta=0.0):
    b = rt.body
    b.x, b.y = float(x), float(y)
    b.vx, b.vy = float(vx), float(vy)
    b.theta = float(theta)
    return b


def _body_id(rt):
    return body_refs_for_runtime(rt)[0][0]


def _rt():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_effector_work_accounting_config())


def _hold_both(rt, mass_l=1.0, mass_r=1.0):
    hid = _body_id(rt)
    b = _place_body(rt, 8.0, 8.0, theta=0.0)
    holders = [{"body_id": hid, "body": b, "config": rt.config, "runtime": rt}]
    left = _place_object(rt, 0, b.x, b.y, state="HELD", holder=hid, hand=MANIP_LEFT, mass=mass_l)
    right = _place_object(rt, 1, b.x, b.y, state="HELD", holder=hid, hand=MANIP_RIGHT, mass=mass_r)
    ensure_pair_runtime(rt, rt.config)
    update_held_kinematics(rt.world, holders)
    return left, right, b, hid


# ---------- isolation ----------


def test_01_absent_from_tiktaalik_and_beta31():
    assert MID not in beta31_mechanism_map()
    cfg = tiktaalik_config()
    assert not ehl.effector_work_held_load_is_active(cfg)


def test_02_absent_from_parent_translational_preset():
    cfg = acanthostega_held_object_translational_impulse_config()
    assert hti.held_translational_impulse_is_active(cfg)
    assert not ehl.effector_work_held_load_is_active(cfg)


def test_03_new_preset_enables_parent_plus_accounting():
    can = preset_canonical(PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING)
    assert can["mechanisms"].get(hti.MECHANISM_ID) is True
    assert can["mechanisms"].get(MID) is True
    cfg = acanthostega_effector_work_accounting_config()
    assert hti.held_translational_impulse_is_active(cfg)
    assert ehl.effector_work_held_load_is_active(cfg)
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING)
    assert ehl.effector_work_held_load_is_active(cfg)


def test_04_normalize_more_specific_first():
    assert (
        normalize_preset_name("ACANTHOSTEGA_PHASE_B_EFFECTOR_WORK_ACCOUNTING")
        == PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING
    )
    assert (
        normalize_preset_name("ACANTHOSTEGA_PHASE_B_HELD_OBJECT_TRANSLATIONAL_IMPULSE")
        == PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE
    )
    assert normalize_preset_name(PRESET_BETA31) == PRESET_BETA31


def test_05_receipt_kind_and_safety_flags():
    assert ehl.RECEIPT_KIND == "EFFECTOR_HELD_LOAD_WORK_ACCOUNTING"
    cfg = ehl.EffectorWorkHeldLoadConfig(enabled=True)
    d = cfg.to_dict()
    assert d["UNACCOUNTED_EFFECTOR_WORK_PRODUCES_IMPULSE"] is False
    assert d["ACCOUNTED_EFFECTOR_WORK_PRODUCES_SWING_IMPULSE"] is False
    assert d["ARM_MASS_MODELLED"] is False
    assert d["EMPTY_EFFECTOR_INERTIA_MODELLED"] is False
    assert d["ROTATIONAL_WORK_STATUS"] == ehl.ROTATIONAL_NOT_ESTABLISHED
    assert d["work_source"] == ehl.WORK_SOURCE_ID
    assert d["swing_impulse"] is False
    assert d["damage_applied"] is False
    assert d["sound_emitted"] is False


def test_06_model_metadata_classification():
    cfg = acanthostega_effector_work_accounting_config()
    meta = model_metadata(cfg)
    assert meta["classification"] == "ACANTHOSTEGA_PHASE_B_EFFECTOR_WORK_ACCOUNTING"
    assert "Effector Work" in meta["phase_label"]


# ---------- accounting ----------


def test_10_empty_hand_skips_inertia():
    rt = _rt()
    b = _place_body(rt, 8.0, 8.0)
    ensure_pair_runtime(rt, rt.config)
    w0 = float(b.mechanical_work_reservoir)
    rec = apply_pair_actuation(
        world=rt.world, body=b, config=rt.config, body_id=_body_id(rt),
        runtime=rt, command="BRING_TOGETHER", tick=1,
    )
    assert "effector_held_load_work" in rec
    ew = rec["effector_held_load_work"]
    assert ew["work_debit"] == 0.0
    assert any(h.get("policy") == ehl.EMPTY_EFFECTOR for h in ew["hands"])
    assert float(b.mechanical_work_reservoir) == w0


def test_11_relative_hand_debits_positive_ke():
    rt = _rt()
    left, right, b, hid = _hold_both(rt, mass_l=2.0, mass_r=2.0)
    ensure_pair_runtime(rt, rt.config)
    # Force open aperture so closing moves hands.
    rt.pair_aperture = float(rt.config.bilateral_bring_together.open_aperture)
    w0 = float(b.mechanical_work_reservoir)
    rec = apply_pair_actuation(
        world=rt.world, body=b, config=rt.config, body_id=hid,
        runtime=rt, command="BRING_TOGETHER", tick=2,
    )
    ew = rec["effector_held_load_work"]
    assert ew["work_debit"] > 0.0
    assert float(b.mechanical_work_reservoir) == w0 - ew["work_debit"]
    assert ew["work_source"] == ehl.WORK_SOURCE_ID
    assert abs(rec["delta_aperture"]) > 0.0
    assert abs(rec["delta_aperture"]) <= abs(rec["delta_aperture_desired"]) + 1e-12


def test_12_insufficient_work_scales_deterministically():
    rt = _rt()
    left, right, b, hid = _hold_both(rt, mass_l=5.0, mass_r=5.0)
    ensure_pair_runtime(rt, rt.config)
    rt.pair_aperture = float(rt.config.bilateral_bring_together.open_aperture)
    b.mechanical_work_reservoir = 0.0
    rec = apply_pair_actuation(
        world=rt.world, body=b, config=rt.config, body_id=hid,
        runtime=rt, command="BRING_TOGETHER", tick=3,
    )
    ew = rec["effector_held_load_work"]
    assert ew["work_unavailable"] or ew["admission_scale"] == 0.0
    assert abs(rec["delta_aperture"]) <= 1e-12
    assert float(b.mechanical_work_reservoir) >= 0.0
    assert ew["work_debit"] == 0.0


def test_13_brake_does_not_credit_reservoir():
    info = ehl.positive_relative_work_request(mass=2.0, v_rel_prev=0.5, v_rel_desired=0.1)
    assert info["work_positive_requested"] == 0.0
    assert info["phase"] == "BRAKE_OR_HOLD"
    assert info["dissipated_not_recovered"] > 0.0


def test_14_reverse_needs_fresh_positive_work():
    info = ehl.positive_relative_work_request(mass=2.0, v_rel_prev=0.4, v_rel_desired=-0.3)
    assert info["phase"] == "REVERSE_FRESH_POSITIVE"
    assert abs(info["work_positive_requested"] - 0.5 * 2.0 * 0.3 * 0.3) < 1e-12


def test_15_holder_translation_effective_mass():
    rt = _rt()
    _hold_both(rt, mass_l=1.5, mass_r=0.5)
    info = ehl.locomotor_mass_with_held_load(
        body_mass=float(rt.config.body.mass),
        world=rt.world,
        holder_body_id=_body_id(rt),
        config=rt.config,
    )
    assert info["accounting_active"] is True
    assert abs(info["held_mass"] - 2.0) < 1e-12
    assert abs(info["effective_mass"] - (float(rt.config.body.mass) + 2.0)) < 1e-12
    assert rt._locomotor_mass_kg() == info["effective_mass"]


def test_16_parent_preset_still_uses_aperture_proxy_not_ke_admission():
    rt = PhysicalSystemRuntime(
        seed=17, config=acanthostega_held_object_translational_impulse_config()
    )
    hid = _body_id(rt)
    b = _place_body(rt, 8.0, 8.0)
    _place_object(rt, 0, b.x, b.y, state="HELD", holder=hid, hand=MANIP_LEFT, mass=3.0)
    _place_object(rt, 1, b.x, b.y, state="HELD", holder=hid, hand=MANIP_RIGHT, mass=3.0)
    ensure_pair_runtime(rt, rt.config)
    rt.pair_aperture = float(rt.config.bilateral_bring_together.open_aperture)
    rec = apply_pair_actuation(
        world=rt.world, body=b, config=rt.config, body_id=hid,
        runtime=rt, command="BRING_TOGETHER", tick=1,
    )
    assert "effector_held_load_work" not in rec
    assert "admission_scale" not in rec


# ---------- two hands ----------


def test_20_two_hands_order_independent_allocation():
    a = ehl.allocate_proportional(1.0, [3.0, 1.0])
    b = ehl.allocate_proportional(1.0, [1.0, 3.0])
    assert abs(a[0] - 0.75) < 1e-12 and abs(a[1] - 0.25) < 1e-12
    assert abs(b[0] - 0.25) < 1e-12 and abs(b[1] - 0.75) < 1e-12
    assert abs(sum(a) - 1.0) < 1e-12


def test_21_unequal_masses_both_limited_together():
    rt = _rt()
    left, right, b, hid = _hold_both(rt, mass_l=1.0, mass_r=4.0)
    ensure_pair_runtime(rt, rt.config)
    rt.pair_aperture = float(rt.config.bilateral_bring_together.open_aperture)
    # Tiny budget forces shared scale.
    b.mechanical_work_reservoir = 1e-4
    rec = apply_pair_actuation(
        world=rt.world, body=b, config=rt.config, body_id=hid,
        runtime=rt, command="BRING_TOGETHER", tick=4,
    )
    ew = rec["effector_held_load_work"]
    assert ew["admission_scale"] < 1.0
    assert float(b.mechanical_work_reservoir) >= -1e-15


# ---------- transitions ----------


def test_30_grasp_init_no_snap_work():
    rt = _rt()
    st = ehl.ensure_effector_work_held_load_for_runtime(rt.world, rt.config)
    note = ehl.note_grasp_attachment(
        rt.world, rt.config, body_id="agent_0", hand_id=MANIP_LEFT, object_id="objA", tick=1
    )
    assert note["work_debit"] == 0.0
    assert note["source"] == ehl.SOURCE_GRASP_SNAP
    assert st.counters["grasp_snap_no_work"] >= 1
    hs = st.per_hand["agent_0"][MANIP_LEFT]
    assert hs.v_rel == 0.0
    assert hs.last_object_id == "objA"


def test_31_rotation_marked_not_established():
    cfg = ehl.EffectorWorkHeldLoadConfig(enabled=True).to_dict()
    assert cfg["ROTATIONAL_WORK_STATUS"] == ehl.ROTATIONAL_NOT_ESTABLISHED
    cat = ehl.catalog_item(enabled=True)
    assert cat["rotational_work"] == ehl.ROTATIONAL_NOT_ESTABLISHED
    assert cat["UNACCOUNTED_EFFECTOR_WORK_PRODUCES_IMPULSE"] is False
    assert cat["ACCOUNTED_EFFECTOR_WORK_PRODUCES_SWING_IMPULSE"] is False


# ---------- safety ----------


def test_40_no_nan_no_overdraft():
    rt = _rt()
    left, right, b, hid = _hold_both(rt, mass_l=10.0, mass_r=10.0)
    ensure_pair_runtime(rt, rt.config)
    rt.pair_aperture = float(rt.config.bilateral_bring_together.open_aperture)
    b.mechanical_work_reservoir = 0.05
    for tick in range(5, 15):
        rec = apply_pair_actuation(
            world=rt.world, body=b, config=rt.config, body_id=hid,
            runtime=rt, command="BRING_TOGETHER", tick=tick,
        )
        assert float(b.mechanical_work_reservoir) >= -1e-12
        ew = rec.get("effector_held_load_work") or {}
        assert ew.get("work_debit", 0.0) == ew.get("work_debit", 0.0)  # not NaN
        import math
        assert math.isfinite(float(ew.get("work_debit") or 0.0))
        assert math.isfinite(float(rec.get("delta_aperture") or 0.0))


def test_41_flags_forbid_swing_impulse_damage_sound():
    rt = _rt()
    left, right, b, hid = _hold_both(rt)
    ensure_pair_runtime(rt, rt.config)
    rt.pair_aperture = float(rt.config.bilateral_bring_together.open_aperture)
    rec = apply_pair_actuation(
        world=rt.world, body=b, config=rt.config, body_id=hid,
        runtime=rt, command="BRING_TOGETHER", tick=9,
    )
    ew = rec["effector_held_load_work"]
    assert ew["swing_impulse"] is False
    assert ew["damage_applied"] is False
    assert ew["sound_emitted"] is False
    assert ew["UNACCOUNTED_EFFECTOR_WORK_PRODUCES_IMPULSE"] is False
    assert ew["ACCOUNTED_EFFECTOR_WORK_PRODUCES_SWING_IMPULSE"] is False


# ---------- persistence ----------


def test_50_serialize_restore_roundtrip_no_fake_work():
    rt = _rt()
    left, right, b, hid = _hold_both(rt, mass_l=2.0, mass_r=2.0)
    ensure_pair_runtime(rt, rt.config)
    rt.pair_aperture = float(rt.config.bilateral_bring_together.open_aperture)
    apply_pair_actuation(
        world=rt.world, body=b, config=rt.config, body_id=hid,
        runtime=rt, command="BRING_TOGETHER", tick=11,
    )
    st = ehl.state_of(rt.world)
    blob = ehl.serialize_state(st)
    assert blob["schema_version"] == ehl.STATE_SCHEMA
    w0 = float(b.mechanical_work_reservoir)
    # Restore into fresh world state
    rt2 = _rt()
    ehl.restore_state(rt2.world, blob, rt2.config)
    st2 = ehl.state_of(rt2.world)
    assert st2 is not None
    assert st2.counters["restore_no_fake_work"] >= 1
    # Reservoir unchanged by restore itself
    assert float(rt2.body.mechanical_work_reservoir) == float(
        rt2.config.deformation_work.reservoir_init
    )
    # Per-hand v_rel preserved
    assert abs(
        st2.per_hand[hid][MANIP_LEFT].v_rel - st.per_hand[hid][MANIP_LEFT].v_rel
    ) < 1e-12


def test_51_overlay_caption():
    assert "NO ARM MASS" in ehl.OVERLAY_CAPTION
    assert "NO SWING IMPULSE" in ehl.OVERLAY_CAPTION
    rt = _rt()
    summary = ehl.researcher_summary(rt.world)
    assert summary is not None
    assert summary["overlay_caption"] == ehl.OVERLAY_CAPTION
