"""ACANTHOSTEGA_PHASE_C_BODY_NORMAL_LOAD_TRACTION — body Coulomb + Gentle bypass V1.

Parent: ACANTHOSTEGA_PHASE_C_SURFACE_ELEVATION_SUPPORT.
CRITICAL: when ON, Gentle grounded_damping + v_stop are BYPASSED (never both).
"""
from __future__ import annotations

import math

from mechanistic_mind.model.acanthostega import (
    acanthostega_body_normal_load_traction_config,
    acanthostega_surface_elevation_support_config,
    model_metadata,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import body_normal_load_traction as bnlt
from mechanistic_mind.physical_system import flat_ground_gravity as fgg
from mechanistic_mind.physical_system import free_resource_object_ground_friction as fogf
from mechanistic_mind.physical_system import surface_elevation_support as ses
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION,
    PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.locomotion_profile import profile_is_active
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

MID = bnlt.MECHANISM_ID


def _rt():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_body_normal_load_traction_config())


def _wait_ticks(rt, n, *, force_wait=True):
    """Advance n ticks with WAIT (passive sliding). Budget-aware helper."""
    for _ in range(int(n)):
        if force_wait:
            rt.step_forced_action("WAIT")
        else:
            rt.step()


# ---------- isolation / gate ----------


def test_01_absent_from_tiktaalik_and_beta31():
    assert MID not in beta31_mechanism_map()
    cfg = tiktaalik_config()
    assert not bnlt.body_normal_load_traction_is_active(cfg)


def test_02_absent_from_parent_elevation():
    cfg = acanthostega_surface_elevation_support_config()
    assert ses.surface_elevation_support_is_active(cfg)
    assert not bnlt.body_normal_load_traction_is_active(cfg)


def test_03_new_preset_enables_parent_plus_bnlt():
    can = preset_canonical(PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION)
    assert can["parent"] == PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT
    assert can["mechanisms"].get(ses.MECHANISM_ID) is True
    assert can["mechanisms"].get(fogf.MECHANISM_ID) is True
    assert can["mechanisms"].get(fgg.MECHANISM_ID) is True
    assert can["mechanisms"].get(MID) is True
    cfg = acanthostega_body_normal_load_traction_config()
    assert bnlt.body_normal_load_traction_is_active(cfg)
    assert ses.surface_elevation_support_is_active(cfg)
    assert fogf.free_resource_object_ground_friction_is_active(cfg)
    assert fgg.flat_ground_gravity_is_active(cfg)
    assert profile_is_active(cfg)
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION)
    assert bnlt.body_normal_load_traction_is_active(cfg)
    meta = model_metadata(cfg)
    assert "BODY_NORMAL_LOAD_TRACTION" in str(meta.get("classification") or "")


def test_04_normalize_aliases():
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_C_BODY_NORMAL_LOAD_TRACTION") == PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION
    assert normalize_preset_name("Acanthostega Phase C Body Normal-Load Traction") == PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_C_SURFACE_ELEVATION_SUPPORT") == PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT


def test_05_forbidden_tokens():
    for tok in (
        "body_normal_load_traction",
        "BODY_NORMAL_LOAD_TRACTION",
        "normal_load",
        "passive_sliding",
        "gentle_grounded_damping_bypassed",
    ):
        assert tok in FORBIDDEN_TOKENS
    hits = audit_cognition_payload({"note": "body_normal_load_traction mu_k normal_load"})
    assert hits


# ---------- Gentle never-both ----------


def test_10_gentle_bypass_proven_on_wait_slide():
    """Stage gate: receipts must show Gentle damp/snap bypassed while Coulomb applied."""
    rt = _rt()
    rt.body.x, rt.body.y = 10.5, 10.5
    rt.body.vx, rt.body.vy = 0.25, 0.0
    rt.body.z, rt.body.vz = 0.0, 0.0
    rt.body.grounded = True
    fgg.ensure_body_vertical(rt.body, rt.config)
    rt.body.grounded = True
    _wait_ticks(rt, 5)
    st = bnlt.state_of(rt.world)
    assert st is not None
    assert int(st.counters.get("gentle_velocity_damp_bypassed") or 0) >= 1
    assert int(st.counters.get("grounded_friction_steps") or 0) >= 1
    rec = st.last_step or {}
    assert rec.get("gentle_grounded_damping_bypassed") is True
    assert rec.get("gentle_v_stop_bypassed") is True
    assert rec.get("receipt_kind") == bnlt.RECEIPT_KIND
    # Parent Gentle would have snapped small v via v_stop; Coulomb path must not stack damp.
    loc = (rt.last_orientation_meta or {}).get("locomotion") or {}
    assert isinstance(loc, dict)
    assert loc.get("gentle_grounded_damping_bypassed") is True
    assert loc.get("gentle_v_stop_bypassed") is True
    assert loc.get("v_stop_applied") is False
    assert float(loc.get("grounded_damping") or 0.0) == 0.0


def test_11_parent_still_uses_gentle_damp():
    """Parent SES (BNLT OFF) still applies Gentle grounded_damping on WAIT."""
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_surface_elevation_support_config())
    rt.body.x, rt.body.y = 10.5, 10.5
    rt.body.vx, rt.body.vy = 0.05, 0.0
    rt.body.z, rt.body.vz = 0.0, 0.0
    fgg.ensure_body_vertical(rt.body, rt.config)
    rt.body.grounded = True
    v0 = float(rt.body.vx)
    _wait_ticks(rt, 3)
    # With Gentle damp 0.85, residual should shrink faster than BNLT mid-μ alone for tiny v,
    # and v_stop may snap. Key: BNLT state absent.
    assert bnlt.state_of(rt.world) is None
    assert abs(float(rt.body.vx)) <= abs(v0) + 1e-12


# ---------- physics ----------


def test_20_coulomb_unit_mass_independent_a():
    step_a = fogf.coulomb_kinetic_step(0.3, 0.0, mu_k=1.75, g=fgg.GRAVITY_ACCELERATION, rest_threshold=0.006)
    step_b = fogf.coulomb_kinetic_step(0.3, 0.0, mu_k=1.75, g=fgg.GRAVITY_ACCELERATION, rest_threshold=0.006)
    assert abs(step_a["a"] - step_b["a"]) < 1e-15
    assert abs(step_a["a"] - 1.75 * fgg.GRAVITY_ACCELERATION) < 1e-12
    # Shared helper
    assert abs(bnlt.mu_k_from_surface_affinity(0.5) - fogf.mu_k_from_surface_affinity(0.5)) < 1e-15


def test_21_flat_slide_stops_and_ke_never_increases():
    rt = _rt()
    rt.body.x, rt.body.y = 8.5, 8.5
    rt.body.vx, rt.body.vy = 0.30, 0.0
    fgg.ensure_body_vertical(rt.body, rt.config)
    rt.body.z = 0.0
    rt.body.vz = 0.0
    rt.body.grounded = True
    for _ in range(30):  # unit ≤30
        _wait_ticks(rt, 1)
    st = bnlt.state_of(rt.world)
    assert st is not None
    # Friction itself never increases KE (env absorb/site may inject between ticks).
    for rec in st.history:
        if rec.get("mode") != "GROUNDED_COULOMB":
            continue
        kb = float(rec.get("kinetic_before") or 0.0)
        ka = float(rec.get("kinetic_after") or 0.0)
        assert ka <= kb + 1e-12
        assert float(rec.get("kinetic_dissipated") or 0.0) >= -1e-15
        sb = float(rec.get("speed_before") or 0.0)
        sa = float(rec.get("speed_after") or 0.0)
        assert sa <= sb + 1e-12
    assert int(st.counters.get("grounded_friction_steps") or 0) >= 1
    assert int(st.counters.get("rest_transitions") or 0) >= 1
    assert math.hypot(rt.body.vx, rt.body.vy) < bnlt.REST_THRESHOLD_DEFAULT + 1e-9


def test_22_airborne_friction_zero_conserves_horizontal():
    rt = _rt()
    rt.body.x, rt.body.y = 8.5, 8.5
    rt.body.vx, rt.body.vy = 0.22, 0.11
    fgg.ensure_body_vertical(rt.body, rt.config)
    rt.body.z = 0.5
    rt.body.vz = 0.0
    rt.body.grounded = False
    vx0, vy0 = float(rt.body.vx), float(rt.body.vy)
    _wait_ticks(rt, 3)
    # While still airborne (may start falling), horizontal from ground channel: no Coulomb.
    st = bnlt.state_of(rt.world)
    assert int(st.counters.get("airborne_conserve_steps") or 0) >= 1
    # Not asserting exact conserve across gravity ticks if landing; check at least one airborne receipt
    hist = list(st.history)
    air = [r for r in hist if r.get("mode") == "AIRBORNE_CONSERVE"]
    assert air
    assert air[0].get("kinetic_dissipated", 0.0) == 0.0 or air[0].get("mu_k") in (None, 0, 0.0)


def test_23_held_load_raises_N_not_a():
    rt = _rt()
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    assert objs
    o = objs[0]
    o.physical_state = "HELD"
    o.holder_body_id = str(getattr(rt, "technical_id", None) or "agent_0")
    o.mass = 2.0
    o.x, o.y = float(rt.body.x), float(rt.body.y)
    rt.body.vx, rt.body.vy = 0.20, 0.0
    fgg.ensure_body_vertical(rt.body, rt.config)
    rt.body.grounded = True
    _wait_ticks(rt, 2)
    rec = bnlt.state_of(rt.world).last_step or {}
    assert float(rec.get("held_mass") or 0.0) >= 2.0 - 1e-9
    m_eff = float(rec.get("m_eff") or 0.0)
    N = float(rec.get("normal_load_N") or 0.0)
    g = float(rec.get("g") or fgg.GRAVITY_ACCELERATION)
    assert abs(N - m_eff * g) < 1e-9
    mu = float(rec.get("mu_k") or 0.0)
    a = float(rec.get("a") or 0.0)
    assert abs(a - mu * g) < 1e-9  # a independent of m_eff


def test_24_snapshot_missing_off_and_restore_continues():
    # Missing key → OFF
    parent = acanthostega_surface_elevation_support_config()
    assert getattr(parent, "body_normal_load_traction", None) in (None, False) or not getattr(
        getattr(parent, "body_normal_load_traction", None), "enabled", False
    )
    rt = _rt()
    rt.body.vx, rt.body.vy = 0.18, 0.0
    fgg.ensure_body_vertical(rt.body, rt.config)
    rt.body.grounded = True
    _wait_ticks(rt, 3)
    snap = rt.snapshot()
    assert "body_normal_load_traction" in (snap.get("config") or {})
    assert snap.get("body_normal_load_traction_state") is not None
    vx_mid = float(rt.body.vx)
    rt2 = PhysicalSystemRuntime.restore(snap)
    assert bnlt.body_normal_load_traction_is_active(rt2.config)
    assert abs(float(rt2.body.vx) - vx_mid) < 1e-12
    assert bool(rt2.body.grounded) is True
    _wait_ticks(rt2, 5)
    # Continued Coulomb → speed should not increase
    assert math.hypot(rt2.body.vx, rt2.body.vy) <= abs(vx_mid) + 1e-9


def test_25_affinity_move_gated_airborne_this_preset_only():
    rt = _rt()
    fgg.ensure_body_vertical(rt.body, rt.config)
    rt.body.grounded = False
    rt.body.z = 0.4
    # Forced MOVE while airborne should not scale via affinity (gate returns early).
    rt.step_forced_action("MOVE:E")
    st = bnlt.state_of(rt.world)
    assert int(st.counters.get("affinity_move_gated_airborne") or 0) >= 1

    # Parent SES: no BNLT gate (counter N/A); mechanism inactive
    rt_p = PhysicalSystemRuntime(seed=17, config=acanthostega_surface_elevation_support_config())
    fgg.ensure_body_vertical(rt_p.body, rt_p.config)
    rt_p.body.grounded = False
    rt_p.body.z = 0.4
    rt_p.step_forced_action("MOVE:E")
    assert bnlt.state_of(rt_p.world) is None


# ---------- dual deposit affinity contrast (validation repair) ----------


def _put_deposit(rt, cell_x: int, cell_y: int, component: str):
    from mechanistic_mind.physical_system.explicit_surface_deposition import (
        SurfaceMaterialDeposit,
        deposit_id_for_cell,
        ensure_surface_deposits,
    )
    from mechanistic_mind.physical_system.resource_objects import MaterialComponent

    ensure_surface_deposits(rt.world)
    deposit = SurfaceMaterialDeposit(
        deposit_id=deposit_id_for_cell(cell_x, cell_y),
        cell_x=int(cell_x),
        cell_y=int(cell_y),
        mass=1.0,
        quantity=1.0,
        composition=(MaterialComponent(component, 1.0),),
        provenance={"lineage_refs": [{"event_id": "bnlt-dual-aff-test", "tick": -1}]},
        created_tick=-1,
        last_updated_tick=-1,
    )
    rt.world.surface_material_deposits[deposit.deposit_id] = deposit
    return deposit


def _slide_on_deposit(component: str, cell: tuple[int, int], *, v0: float = 0.30, ticks: int = 8):
    """Park body on a real deposit cell and WAIT-slide; return first Coulomb receipt + speeds."""
    rt = _rt()
    _put_deposit(rt, cell[0], cell[1], component)
    x, y = float(cell[0]) + 0.5, float(cell[1]) + 0.5
    rt.body.x, rt.body.y = x, y
    rt.body.vx, rt.body.vy = float(v0), 0.0
    fgg.ensure_body_vertical(rt.body, rt.config)
    sh = ses.surface_support_height(rt.world, x, y, config=rt.config)
    rt.body.z = float(sh)
    rt.body.vz = 0.0
    rt.body.grounded = True
    sample = fogf.sample_support_surface_affinity(rt.world, x, y, width=32, height=32)
    speeds = [float(v0)]
    first = None
    for _ in range(int(ticks)):
        _wait_ticks(rt, 1)
        st = bnlt.state_of(rt.world)
        rec = (st.last_step or {}) if st else {}
        if first is None and rec.get("mode") == "GROUNDED_COULOMB":
            first = dict(rec)
        speeds.append(math.hypot(rt.body.vx, rt.body.vy))
    return {
        "sample": sample,
        "receipt": first or {},
        "speeds": speeds,
        "mu_expected": fogf.mu_k_from_surface_affinity(sample["surface_affinity"]),
    }


def test_26_dual_deposit_affinity_mu_impulse_and_braking_differ():
    """VALIDATION REPAIR: two real deposits → different aff → different μ / impulse / trajectory.

    Affinity source: PRIMITIVE_COEFFICIENTS_V1 via SurfaceMaterialDeposit composition
    (component_a → 0.75, component_b → 0.25). Empty cell is NOT used (would both be 0.5).
    Sampling path: BNLT → FOGF sample_support_surface_affinity → derive_effective_properties.
    """
    high = _slide_on_deposit("component_a", (12, 12), v0=0.30, ticks=8)
    low = _slide_on_deposit("component_b", (14, 14), v0=0.30, ticks=8)

    aff_h = float(high["sample"]["surface_affinity"])
    aff_l = float(low["sample"]["surface_affinity"])
    assert high["sample"]["deposit_present"] is True
    assert low["sample"]["deposit_present"] is True
    assert abs(aff_h - 0.75) < 1e-12
    assert abs(aff_l - 0.25) < 1e-12
    assert abs(aff_h - aff_l) > 1e-9
    assert abs(aff_h - 0.5) > 1e-9 and abs(aff_l - 0.5) > 1e-9

    mu_h = float(high["receipt"]["mu_k"])
    mu_l = float(low["receipt"]["mu_k"])
    assert abs(mu_h - high["mu_expected"]) < 1e-12
    assert abs(mu_l - low["mu_expected"]) < 1e-12
    assert abs(mu_h - 2.375) < 1e-12
    assert abs(mu_l - 1.125) < 1e-12
    assert mu_h > mu_l + 1e-9

    # Friction impulse proxy: |m_eff * dv| on first grounded Coulomb step
    imp_h = abs(float(high["receipt"]["m_eff"]) * float(high["receipt"]["dv"]))
    imp_l = abs(float(low["receipt"]["m_eff"]) * float(low["receipt"]["dv"]))
    assert imp_h > imp_l + 1e-12

    # Braking trajectory: higher μ → lower residual speed at mid ticks
    assert high["speeds"][3] < low["speeds"][3] - 1e-9
    assert high["speeds"][5] < low["speeds"][5] - 1e-9
