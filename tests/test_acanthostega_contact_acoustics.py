"""ACANTHOSTEGA PHYSICAL CONTACT ACOUSTIC EMISSION (ACANTHOSTEGA_PHASE_B_CONTACT_ACOUSTICS).

Numbered contract tests 1-29 (+ Observer / Analyzer / catalog extras).  Controlled harness: the
authoritative world of a real runtime of the new preset plus researcher-positioned bodies (deep
copies of the runtime body).  The harness calls the *unchanged* soft-contact solver and PUSH
function exactly like ``TwoAgentRuntime._step_once`` does, then the contact-acoustic pass and the
existing Local Physical Signal Transport end-of-tick step.  Runtime tests use the real
``TwoAgentRuntime`` through ``ObserverSession``.
"""
from __future__ import annotations

import copy
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mechanistic_mind.model.acanthostega import (
    acanthostega_column_transfer_config,
    acanthostega_contact_acoustics_config,
    acanthostega_local_signal_config,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import experiment_canonical as ec
from mechanistic_mind.physical_system import local_physical_signal_transport as lps
from mechanistic_mind.physical_system import oscillatory_signaling as oscmod
from mechanistic_mind.physical_system import physical_contact_acoustic_emission as pca
from mechanistic_mind.physical_system.body_contact import resolve_soft_contact
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
    PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING,
    PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION,
    PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT,
    PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION,
    PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY,
    PRESET_ACANTHOSTEGA_STATIC_TRACTION,
    PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION,
    PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT,
    PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT,
    PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER,
    PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP,
    PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW,
    PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW,
    PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C,
    PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW,
    PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
    PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE,
    PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
    PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
    PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
    PRESET_BETA31,
    beta31_mechanism_map,
    canonical_fingerprint,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.mechanism_registry import mechanism_snapshot, set_mechanism
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.physical_push import apply_push_through_contact, set_push_exertion
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.scientific_v3.physical_contact_acoustic_summary import (
    format_physical_contact_acoustic_section,
    summarize_physical_contact_acoustics,
)

ROOT = Path(__file__).resolve().parents[1]
LPS_RESULTS = ROOT / "results" / "acanthostega_local_signal"
APP = ROOT / "web" / "psy-observer" / "src" / "App.tsx"
FROZEN = "1621ef2c154864d1"
MID = pca.MECHANISM_ID
EPS, COUPLING, EMAX = 0.04, 5.0, 2.5
CX, CY = 10.0, 10.5   # grid alignment matters: footprint overlap is cell-quantised


# ---------------------------------------------------------------- harness


class CH:
    """Researcher-positioned bodies; real solver + PUSH + contact-acoustic pass + LPS step."""

    def __init__(self, seed: int = 17, push: bool = False, cfg=None):
        self.cfg = cfg or acanthostega_contact_acoustics_config()
        if push:
            self.cfg.physical_push.mode = "EXPERIMENTAL"
        self.rt = PhysicalSystemRuntime(seed=seed, config=self.cfg)
        self.world = self.rt.world
        self.lst = lps.state_of(self.world)
        self.cst = pca.state_of(self.world)
        self.bodies: dict = {}
        self.tick = int(self.world.tick)
        self.pairs: list[tuple[str, str]] = []
        self.receptions: list[dict] = []
        self.steps: list[dict] = []
        h, w = self.world.T.shape
        self.w, self.h = int(w), int(h)

    def add(self, bid, x, y, theta=None):
        b = copy.deepcopy(self.rt.body)
        b.x, b.y, b.vx, b.vy = float(x) % self.w, float(y) % self.h, 0.0, 0.0
        b.osc_emit_remaining = 0
        if theta is not None:
            b.theta = float(theta)
        self.bodies[bid] = b
        return b

    def pair(self, a, b):
        self.pairs.append((a, b))
        return self

    def refs(self):
        return sorted(self.bodies.items())

    def contact_step(self, pairs=None, reverse_rows=False, freeze=False):
        te = self.tick
        pairs = self.pairs if pairs is None else pairs
        pre = pca.capture_pre_contact(self.refs())
        saved = {k: (b.x, b.y) for k, b in self.bodies.items()}
        rows = []
        for a_id, b_id in pairs:
            A, B = self.bodies[a_id], self.bodies[b_id]
            rec = resolve_soft_contact(A, B, self.cfg.body, self.cfg.body, width=self.w, height=self.h, enabled=True)
            pr = apply_push_through_contact(A, B, self.cfg.body, self.cfg.body,
                                            contact=bool(rec and rec.get("contact")),
                                            push_cfg=self.cfg.physical_push, width=self.w, height=self.h)
            rows.append({"a_id": a_id, "b_id": b_id, "mass_a": float(self.cfg.body.mass),
                         "mass_b": float(self.cfg.body.mass), "contact_receipt": rec, "push_receipt": pr,
                         "body_a": A, "body_b": B})
        if reverse_rows:
            rows = list(reversed(rows))
        out = pca.process_contact_pairs(self.world, self.cfg, rows, emission_tick=te, pre_contact=pre)
        if freeze:  # researcher holds the bodies in place (sustained pressed overlap)
            for k, (x, y) in saved.items():
                self.bodies[k].x, self.bodies[k].y = x, y
                self.bodies[k].vx = self.bodies[k].vy = 0.0
        self.steps.append(out)
        self.tick += 1
        self.world.tick = self.tick
        tr = lps.step_end_of_tick(self.world, self.cfg, self.refs(), tick_now=self.tick)
        self.receptions.extend(tr.get("receptions") or [])
        return out

    def run(self, n, **kw):
        return [self.contact_step(**kw) for _ in range(n)]

    def frag(self, bid):
        return oscmod.cognition_osc_fragments(self.bodies[bid], self.world, self.cfg.oscillatory_signaling)

    def energy(self, bid):
        return float(sum(self.frag(bid).values()))

    def emissions(self):
        return [e for s in self.steps for e in s.get("emissions") or []]

    def measurements(self):
        return [m for s in self.steps for m in s.get("measurements") or []]

    def accepted(self, bid=None, eid=None):
        return [r for r in self.receptions if r.get("accepted")
                and (bid is None or r["receiver_body_id"] == bid)
                and (eid is None or r["emission_id"] == eid)]


def impact(d=0.8, push=False, ids=("body-0", "body-1"), cx=CX, cy=CY):
    h = CH(push=push)
    h.add(ids[0], cx - d / 2, cy, theta=0.0)
    h.add(ids[1], cx + d / 2, cy, theta=math.pi)
    h.pair(*ids)
    return h


def session(preset=PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS, d=0.8):
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

    s = ObserverSession()
    s.apply_experiment(preset_canonical(preset, seed=17))
    rt = s.runtime
    b0, b1 = rt.slots[0].body, rt.slots[1].body
    if d is not None:
        b1.x, b1.y = (b0.x + d) % 32.0, b0.y
    return s, rt


def osc_sum(o):
    return float(sum(v for k, v in o.items() if k.startswith("osc_")))


# ---------------------------------------------------------------- isolation (1-5)


@pytest.fixture(scope="module")
def probe():
    before = json.loads((LPS_RESULTS / "preservation_after.json").read_text())
    proc = subprocess.run(
        [sys.executable, str(LPS_RESULTS / "preservation_probe.py")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return before, json.loads(proc.stdout)


def test_01_tiktaalik_mechanism_map_unchanged(probe):
    before, now = probe
    assert now["beta31_mechanism_map"] == before["beta31_mechanism_map"]
    assert MID not in beta31_mechanism_map()
    assert MID not in preset_canonical(PRESET_BETA31, seed=17)["mechanisms"]


def test_02_tiktaalik_fingerprint_seed17_unchanged(probe):
    before, now = probe
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN
    assert now["beta31_fingerprint"] == before["beta31_fingerprint"] == FROZEN


def test_03_tiktaalik_physics_and_osc_unchanged(probe):
    before, now = probe
    assert now["two_agent_signal"][PRESET_BETA31] == before["two_agent_signal"][PRESET_BETA31]
    assert now["runtime"]["TIKTAALIK"] == before["runtime"]["TIKTAALIK"]
    tik = tiktaalik_config()
    set_mechanism(tik, MID, True)                    # forced flag on Tiktaalik does not enable it
    pca.set_physical_contact_acoustic_emission(tik, True)
    assert pca.physical_contact_acoustic_emission_is_active(tik) is False
    assert getattr(tik, "physical_contact_acoustic_emission", None) is None
    s, rt = session(PRESET_BETA31, d=0.8)            # Tiktaalik two-agent contact: solver only
    rt.step()
    assert getattr(rt.world, "contact_acoustic_state", None) is None
    assert getattr(rt, "last_contact_acoustic", None) is None
    c = rt.last_contact
    assert c is not None and c["contact"] is True
    assert set(c) <= {"enabled", "overlap_cells", "impulse_a", "impulse_b", "contact", "com_distance", "push",
                      "contact_entity_a_kind", "contact_entity_a_id", "contact_entity_b_kind",
                      "contact_entity_b_id", "pair"}
    assert "contact_acoustic_state" not in rt.snapshot()["world"]


def test_04_previous_acanthostega_presets_unchanged(probe):
    before, now = probe
    assert now == before                               # full LPS-stage probe incl. LOCAL preset
    ls = preset_canonical(PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, seed=17)["mechanisms"]
    ca = preset_canonical(PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS, seed=17)["mechanisms"]
    assert MID not in ls and ca[MID] is True
    assert {k: v for k, v in ca.items() if k != MID} == ls
    s, rt = session(PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, d=0.8)   # LOCAL: contact happens, silence
    obs = []
    for _ in range(3):
        rt.step()
        obs.append(rt.observations())
    assert getattr(rt.world, "contact_acoustic_state", None) is None
    st = lps.state_of(rt.world)
    assert st is not None and st.counters.get("physical_contact_emissions", 0) == 0
    assert all(osc_sum(o) == 0.0 for ob in obs for o in ob)


def test_05_contact_acoustics_absent_before_new_preset():
    names = sorted(v for k, v in vars(ec).items() if k.startswith("PRESET_") and isinstance(v, str))
    assert PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS in names
    descendants = {
        PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
        PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
        PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE,
        PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING,
        PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION,
        # Phase C surface/SES descendants inherit contact acoustics via the chain.
        PRESET_ACANTHOSTEGA_SURFACE_ELEVATION_SUPPORT,
        PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION,
        PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY,
        PRESET_ACANTHOSTEGA_STATIC_TRACTION,
        PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION,
        PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT,
        PRESET_ACANTHOSTEGA_SES_DECOMPOSITION_CONTRACT,
        PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER,
        PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP,
        PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW,
        PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW,
        PRESET_ACANTHOSTEGA_CONTINUOUS_PE_POLICY_C,
        PRESET_ACANTHOSTEGA_TANGENT_GRAVITY_DIAGNOSTIC_SHADOW,
        PRESET_ACANTHOSTEGA_COHERENT_SLOPE_DYNAMICS,
    }
    for p in names:
        if p in descendants:
            continue
        mech = preset_canonical(p, seed=17)["mechanisms"]
        assert not mech.get(MID), p
        cfg = stamp_config_from_preset(acanthostega_contact_acoustics_config(), p)
        assert pca.physical_contact_acoustic_emission_is_active(cfg) is False, p
    for cfg in (acanthostega_local_signal_config(), acanthostega_column_transfer_config()):
        assert getattr(cfg, "physical_contact_acoustic_emission", None) is None
        assert pca.state_of(PhysicalSystemRuntime(seed=17, config=cfg).world) is None
    assert pca.physical_contact_acoustic_emission_is_active(acanthostega_contact_acoustics_config())


# ---------------------------------------------------------------- physical causality (6-14)


def test_06_no_contact_no_emission():
    h = impact(d=3.0)
    h.add("rx", CX, CY + 2.0)
    h.run(5)
    assert h.emissions() == [] and h.measurements() == []
    assert h.cst.counters["contact_pairs_observed"] == 0
    assert h.lst.counters.get("physical_contact_emissions", 0) == 0
    assert h.energy("rx") == 0.0


def test_07_contact_true_but_zero_or_subthreshold_impulse_is_silent():
    h = impact(d=2.0)                                  # grazing: 1 shared footprint cell
    h.run(3)
    ms = h.measurements()
    assert ms and all(m["contact_detected"] for m in ms)
    assert abs(ms[0]["contact_impulse_magnitude"] - 0.0375) < 1e-9
    assert all(not m["emitted"] and m["silence_reason"] == pca.R_BELOW_EPSILON for m in ms)
    assert h.emissions() == []
    # boolean contact with a zero impulse receipt (synthetic) never sounds
    h2 = CH()
    h2.add("a", CX, CY); h2.add("b", CX + 0.5, CY)
    rows = [{"a_id": "a", "b_id": "b", "mass_a": 2.0, "mass_b": 2.0,
             "contact_receipt": {"contact": True, "impulse_a": [0.0, 0.0], "impulse_b": [0.0, 0.0],
                                 "overlap_cells": [[1, 1]], "com_distance": 0.5},
             "push_receipt": {"push_applied": False}, "body_a": h2.bodies["a"], "body_b": h2.bodies["b"]}]
    out = pca.process_contact_pairs(h2.world, h2.cfg, rows, emission_tick=h2.tick)
    assert out["emissions"] == [] and out["measurements"][0]["silence_reason"] == pca.R_BELOW_EPSILON


def test_08_small_and_large_impulse_monotone_energies():
    lo, hi = impact(d=1.3), impact(d=0.5)
    lo.contact_step(); hi.contact_step()
    el, eh = lo.emissions()[0], hi.emissions()[0]
    assert abs(el["new_impulse_magnitude"] - 0.075) < 1e-9 and abs(eh["new_impulse_magnitude"] - 0.2375) < 1e-9
    assert abs(el["emitted_energy"] - 0.375) < 1e-9 and abs(eh["emitted_energy"] - 1.1875) < 1e-9
    assert eh["emitted_energy"] > el["emitted_energy"] > 0.0


def test_09_zero_impulse_never_energy_and_law_bounded_monotone():
    cfg = pca.ContactAcousticConfig()
    assert (cfg.impulse_epsilon, cfg.acoustic_coupling, cfg.max_acoustic_energy) == (EPS, COUPLING, EMAX)
    for bad in (0.0, -1.0, float("nan"), float("-inf"), EPS):
        assert pca.acoustic_energy(bad, cfg)[1] == 0.0
    prev = 0.0
    for i in range(1, 400):
        j = i * 0.005
        u, e = pca.acoustic_energy(j, cfg)
        assert 0.0 <= e <= EMAX and e >= prev - 1e-12
        if j > EPS:
            assert abs(u - COUPLING * j) < 1e-9 and abs(e - min(EMAX, COUPLING * j)) < 1e-9
        prev = e
    assert pca.broadband_bands(0.0, 6) == [0.0] * 6
    assert pca.broadband_bands(1.2, 6) == pytest.approx([0.2] * 6)


def test_10_same_impulse_same_spectrum_independent_of_agent_ids():
    a = impact(ids=("body-0", "body-1")); a.contact_step()
    b = impact(ids=("zeta-9", "agent-a")); b.contact_step()
    ea, eb = a.emissions()[0], b.emissions()[0]
    for k in ("anonymous_band_vector", "emitted_energy", "unclamped_energy", "position", "new_impulse_magnitude"):
        assert ea[k] == pytest.approx(eb[k]), k
    assert ea["emission_id"] == eb["emission_id"]
    assert eb["canonical_body_pair"] == ["agent-a", "zeta-9"]


def test_11_persistent_resting_contact_is_silent():
    h = impact(d=0.8)
    h.run(12)
    assert len(h.emissions()) == 1
    ms = h.measurements()
    assert len(ms) == 12 and all(m["contact_detected"] for m in ms)
    assert all(m["silence_reason"] in (pca.R_RESTING, pca.R_BELOW_EPSILON) for m in ms[1:])
    assert sum(m["silence_reason"] == pca.R_RESTING for m in ms) >= 8
    f = impact(d=0.8)                                  # pressed, frozen overlap: identical impulse each tick
    f.run(10, freeze=True)
    assert len(f.emissions()) == 1
    assert all(m["silence_reason"] == pca.R_RESTING for m in f.measurements()[1:])


def test_12_separation_then_new_impact_new_emission():
    h = impact(d=0.8)
    h.run(3)
    for bid, x in (("body-0", CX - 3), ("body-1", CX + 3)):
        h.bodies[bid].x = x
    h.run(2)
    assert h.cst.sounded_level == {} and h.cst.counters["separations"] == 1
    h.bodies["body-0"].x, h.bodies["body-1"].x = CX - 0.4, CX + 0.4
    h.run(2)
    em = h.emissions()
    assert len(em) == 2 and em[0]["emission_id"] != em[1]["emission_id"]
    assert em[1]["emission_tick"] == 5


def test_13_push_through_contact_single_emission():
    h = impact(d=0.8, push=True)
    h.run(3)                                           # impact + resting
    set_push_exertion(h.bodies["body-0"], 1.0)
    out = h.contact_step()
    assert len(out["emissions"]) == 1
    e = out["emissions"][0]
    assert abs(e["push_impulse_magnitude"] - 0.4) < 1e-9 and e["emitted_energy"] > 0
    m = [x for x in out["measurements"] if x["emitted"]][0]
    assert m["push_applied"] is True and m["new_contact_impulse_magnitude"] <= 1e-9
    # onset + PUSH in the same tick: still exactly one emission (one physical impulse sum)
    g = impact(d=0.8, push=True)
    set_push_exertion(g.bodies["body-0"], 1.0)
    out = g.contact_step()
    assert len(out["emissions"]) == 1 and abs(out["emissions"][0]["new_impulse_magnitude"] - 0.5625) < 1e-9
    # PUSH without contact: no force, no sound
    n = impact(d=3.0, push=True)
    set_push_exertion(n.bodies["body-0"], 1.0)
    n.contact_step()
    assert n.emissions() == []
    # duplicated rows for the same physical pair (both traversal sides) are deduplicated
    d = CH(); d.add("a", CX - 0.4, CY); d.add("b", CX + 0.4, CY)
    out = d.contact_step(pairs=[("a", "b"), ("b", "a")])
    assert len(out["emissions"]) <= 1 and d.cst.counters["duplicate_pair_suppressed"] == 1
    assert all(len([x for x in h.emissions() if x["emission_tick"] == t]) <= 1 for t in range(10))


def test_14_contact_position_across_toroidal_boundary():
    h = CH()
    h.add("a", 31.6, CY); h.add("b", 0.4, CY)
    h.pair("a", "b")
    out = h.contact_step()
    e = out["emissions"][0]
    x = e["position"][0]
    assert min(abs(x - 0.0), abs(x - 32.0)) < 1e-9 and abs(e["position"][1] - CY) < 1e-9
    assert e["position_derivation"] == pca.POSITION_DERIVATION
    assert pca.toroidal_midpoint(31.6, 5.0, 0.4, 5.0, 32, 32)[0] % 32.0 == pytest.approx(0.0, abs=1e-9)
    ref = impact(d=0.8); ref.contact_step()
    assert e["emitted_energy"] == pytest.approx(ref.emissions()[0]["emitted_energy"])


# ---------------------------------------------------------------- transport (15-21)


def test_15_no_same_tick_retroactive_reception():
    h = impact()
    h.add("rx", CX + 1.5, CY)
    before = h.energy("rx")
    te = h.tick
    pre = pca.capture_pre_contact(h.refs())
    A, B = h.bodies["body-0"], h.bodies["body-1"]
    rec = resolve_soft_contact(A, B, h.cfg.body, h.cfg.body, width=32, height=32)
    out = pca.process_contact_pairs(h.world, h.cfg, [{"a_id": "body-0", "b_id": "body-1", "mass_a": 2.0,
                                                      "mass_b": 2.0, "contact_receipt": rec, "push_receipt": {}}],
                                    emission_tick=te, pre_contact=pre)
    assert out["emissions"] and h.energy("rx") == before == 0.0   # observation of tick te unaffected
    assert all(r["arrival_tick"] > te for r in h.lst.reception_history) if h.lst.reception_history else True
    h.world.tick = h.tick = te + 1
    lps.step_end_of_tick(h.world, h.cfg, h.refs(), tick_now=h.tick)   # arrival tick te+1 processed
    r = lps.emit_local_physical_signal(h.world, emission_tick=te, x=CX, y=CY, band_energies=[0.1] * 6,
                                       provenance={"selection_provenance": lps.PROV_PHYSICAL_CONTACT})
    assert r["status"] == "REJECTED" and r["rejection_reason"] == "RETROACTIVE_EMISSION"
    assert h.energy("rx") > 0.0                                        # heard at te+1, not at te
    # real two-agent runtime: contact resolved in step T is heard only at observation T+1
    s, rt = session()
    o0 = rt.observations()
    rt.step()
    assert rt.last_contact_acoustic["emissions"]
    assert all(osc_sum(o) == 0.0 for o in o0)
    assert all(osc_sum(o) > 0.0 for o in rt.observations())


def _listener_run(ds, ticks=6):
    h = impact()
    for i, d in enumerate(ds):
        h.add(f"r{i}", CX + d, CY + 2.5)
    h.run(ticks)
    eid = h.emissions()[0]["emission_id"]
    return h, eid


def test_16_near_listener_not_later_than_far():
    h, eid = _listener_run([0.0, 6.0])
    near, far = h.accepted("r0", eid), h.accepted("r1", eid)
    assert near and far
    assert near[0]["arrival_tick"] <= far[0]["arrival_tick"]
    assert near[0]["propagation_delay"] < far[0]["propagation_delay"]


def test_17_far_signal_weaker():
    h, eid = _listener_run([0.0, 5.0])
    near, far = h.accepted("r0", eid)[0], h.accepted("r1", eid)[0]
    assert near["total_received_energy"] > far["total_received_energy"] > 0.0


def test_18_beyond_transport_radius_silent():
    h, eid = _listener_run([9.0])                      # distance ~ 9.34 > R = 8
    assert h.accepted("r0") == []
    assert all(h.energy("r0") == 0.0 for _ in [0])


def test_19_two_listeners_different_side_and_distance():
    h = impact()
    h.add("upper", CX, CY + 2.0, theta=0.0)            # same distance, mirrored side
    h.add("lower", CX, CY - 2.0, theta=0.0)
    h.add("far", CX + 5.0, CY + 1.0, theta=0.0)
    h.contact_step()
    fu, fl = h.frag("upper"), h.frag("lower")
    lu = sum(v for k, v in fu.items() if k.startswith("osc_l_")); ru = sum(v for k, v in fu.items() if k.startswith("osc_r_"))
    ll = sum(v for k, v in fl.items() if k.startswith("osc_l_")); rl = sum(v for k, v in fl.items() if k.startswith("osc_r_"))
    assert lu > 0 and ll > 0 and abs(lu - ru) > 1e-6
    assert lu == pytest.approx(rl) and ru == pytest.approx(ll)   # opposite sides -> mirrored L/R
    h.run(3)
    eid = h.emissions()[0]["emission_id"]
    U, F = h.accepted("upper", eid)[0], h.accepted("far", eid)[0]
    assert F["toroidal_distance"] > U["toroidal_distance"] and F["arrival_tick"] > U["arrival_tick"]
    assert F["total_received_energy"] < U["total_received_energy"]


def test_20_agent_and_row_order_do_not_change_emission_or_reception():
    def run(order_rows, ids):
        h = CH()
        h.add(ids[0], CX - 0.4, CY); h.add(ids[1], CX + 0.4, CY); h.add("rx", CX + 3.0, CY + 1.0)
        h.pair(ids[0], ids[1])
        h.contact_step(reverse_rows=order_rows)
        h.contact_step()
        return ([(e["emission_id"], e["emitted_energy"], tuple(e["position"])) for e in h.emissions()],
                [(r["emission_id"], r["arrival_tick"], round(r["total_received_energy"], 12)) for r in h.accepted("rx")])
    base = run(False, ("body-0", "body-1"))
    assert base == run(True, ("body-0", "body-1")) == run(False, ("body-1", "body-0"))
    # real runtime: slot process order permutation
    res = []
    for order in ((0, 1), (1, 0)):
        s, rt = session()
        rt.process_order = order
        rt.step()
        res.append([(e["emission_id"], round(e["emitted_energy"], 12), tuple(round(v, 12) for v in e["position"]))
                    for e in rt.last_contact_acoustic["emissions"]])
    assert res[0] == res[1] and res[0]


def test_21_deliberate_osc_emit_still_works():
    h = CH()
    h.add("tx", CX, CY); h.add("rx", CX + 2.0, CY)
    b = h.bodies["tx"]
    b.osc_amp_u, b.osc_freq_u, b.osc_emit_remaining = 0.8, 0.5, 1
    h.run(3)
    assert h.lst.counters.get("endogenous_emissions", 0) >= 1 or any(
        e.get("selection_provenance") != lps.PROV_PHYSICAL_CONTACT for e in h.lst.emission_history)
    assert h.accepted("rx")
    assert h.emissions() == []
    assert all(e.get("selection_provenance") != lps.PROV_PHYSICAL_CONTACT for e in h.lst.emission_history)


# ---------------------------------------------------------------- privacy (22-25)


@pytest.fixture(scope="module")
def contact_run():
    s, rt = session()
    obs = [rt.observations()]
    for _ in range(6):
        rt.step()
        obs.append(rt.observations())
    return rt, obs


def test_22_cognition_payload_has_no_cause_fields(contact_run):
    rt, obs = contact_run
    assert pca.state_of(rt.world).counters["emissions"] >= 1
    assert any(osc_sum(o) > 0 for ob in obs for o in ob)
    for ob in obs:
        for o in ob:
            text = repr(o)
            for tok in ("body-", "agent_", "signal-emission", "contact-impulse", "impulse", "PUSH", "CONTACT",
                        "source", "position", "cause", "emission"):
                assert tok not in text, tok


def test_23_agent_receives_only_anonymous_bands(contact_run):
    ls = PhysicalSystemRuntime(seed=17, config=acanthostega_local_signal_config()).agent_observation()
    ca = PhysicalSystemRuntime(seed=17, config=acanthostega_contact_acoustics_config()).agent_observation()
    assert sorted(ls) == sorted(ca)
    rt, obs = contact_run
    for ob in obs:
        for o in ob:
            assert sorted(o) == sorted(obs[0][0])
            assert all(isinstance(o[k], float) for k in o if k.startswith("osc_"))


def test_24_researcher_receipt_full_causal_link():
    h = impact()
    h.add("rx", CX + 2.0, CY + 1.0)
    h.run(3)
    e = h.emissions()[0]
    m = {x["measurement_id"]: x for x in h.measurements()}[e["contact_receipt_ref"]]
    assert m["emitted"] and m["emission_id"] == e["emission_id"]
    for f in ("emission_id", "emission_tick", "canonical_body_pair", "position", "position_derivation",
              "contact_receipt_ref", "new_impulse_vector", "new_impulse_magnitude", "acoustic_coupling",
              "unclamped_energy", "emitted_energy", "anonymous_band_vector", "mechanism", "preset",
              "relative_velocity_pre_contact"):
        assert f in e, f
    assert e["semantic_label"] is False and e["agent_accessible"] is False
    assert e["mechanical_energy_withdrawn"] is False
    assert e["preset"] == PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS and e["mechanism"] == MID
    tr = [x for x in h.lst.emission_history if x["emission_id"] == e["emission_id"]][0]
    assert tr["cause_receipt_ref"] == m["measurement_id"] and tr["selection_provenance"] == lps.PROV_PHYSICAL_CONTACT
    assert tr["source_body_pair"] == ["body-0", "body-1"]
    recs = h.accepted(eid=e["emission_id"])
    assert {r["receiver_body_id"] for r in recs} >= {"rx", "body-0", "body-1"}


def test_25_forbidden_token_scan(contact_run):
    for tok in ("physical_contact_acoustic", "PHYSICAL_CONTACT", "contact-impulse-", "canonical_body_pair",
                "CONTACT_ACOUSTIC", "impulse_magnitude"):
        assert tok in FORBIDDEN_TOKENS
    rt, obs = contact_run
    for ob in obs:
        for o in ob:
            assert audit_cognition_payload(o) == []
    st = pca.state_of(rt.world)
    leak = json.dumps(st.emission_history + st.measurement_history)
    assert "PHYSICAL_CONTACT" in leak and "canonical_body_pair" in leak   # scan is meaningful


# ---------------------------------------------------------------- persistence (26-29)


def _roundtrip(h: CH) -> CH:
    """Snapshot/restore the authoritative world of the harness through the runtime path."""
    h.rt.tick = h.rt.world.tick = h.rt.body.tick = h.rt.internal.tick = h.tick
    snap = json.loads(json.dumps(h.rt.snapshot()))
    snap["world"]["local_signal_transport"] = json.loads(json.dumps(lps.serialize_state(h.lst)))
    snap["world"]["contact_acoustic_state"] = json.loads(json.dumps(pca.serialize_state(h.cst)))
    back = PhysicalSystemRuntime.restore(snap)
    g = CH.__new__(CH)
    g.__dict__.update({k: v for k, v in h.__dict__.items() if k not in ("rt", "world", "lst", "cst", "bodies")})
    g.rt, g.world = back, back.world
    g.cfg = back.config
    g.lst, g.cst = lps.state_of(back.world), pca.state_of(back.world)
    g.bodies = copy.deepcopy(h.bodies)
    g.receptions, g.steps = list(h.receptions), list(h.steps)
    g.world.tick = g.tick
    return g


def test_26_snapshot_before_arrival_restore_keeps_arrival():
    def mk():
        h = impact()
        h.add("far", CX + 6.0, CY + 2.0)
        h.contact_step()
        return h
    ctrl = mk(); ctrl.run(4)
    h = mk()
    assert not h.accepted("far")                     # wavefront still travelling
    g = _roundtrip(h)
    assert g.cst is not None and g.lst is not None
    g.run(4)
    a = [(r["emission_id"], r["arrival_tick"], round(r["total_received_energy"], 12)) for r in ctrl.accepted("far")]
    b = [(r["emission_id"], r["arrival_tick"], round(r["total_received_energy"], 12)) for r in g.accepted("far")]
    assert a == b and a
    # real two-agent runtime snapshot/restore mid-run gives identical continuation
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    s, rt = session()
    rt.step()
    back = TwoAgentRuntime.restore(json.loads(json.dumps(rt.snapshot())))
    def cont(r):
        out = []
        for _ in range(3):
            out.append([round(osc_sum(o), 12) for o in r.observations()])
            r.step()
            out.append([(m["measurement_id"], m["emitted"], m["silence_reason"]) for m in r.last_contact_acoustic["measurements"]])
        return out
    assert cont(rt) == cont(back)


def test_27_snapshot_during_resting_contact_no_reimpact():
    h = impact(); h.run(3)
    g = _roundtrip(h)
    assert g.cst.sounded_level == h.cst.sounded_level and g.cst.sounded_level
    g.run(4)
    assert len(g.emissions()) == 1                      # only the original impact
    assert all(m["silence_reason"] == pca.R_RESTING for m in g.measurements()[3:])
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    s, rt = session(); rt.step(); rt.step()
    back = TwoAgentRuntime.restore(json.loads(json.dumps(rt.snapshot())))
    assert pca.state_of(back.world).sounded_level == pca.state_of(rt.world).sounded_level
    back.step()
    assert back.last_contact_acoustic["emissions"] == []


def test_28_old_snapshot_without_contact_state_loads_off():
    old = PhysicalSystemRuntime(seed=17, config=acanthostega_local_signal_config()).snapshot()
    back = PhysicalSystemRuntime.restore(json.loads(json.dumps(old)))
    assert pca.state_of(back.world) is None and lps.state_of(back.world) is not None
    assert pca.physical_contact_acoustic_emission_is_active(back.config) is False
    snap = json.loads(json.dumps(PhysicalSystemRuntime(seed=17, config=acanthostega_contact_acoustics_config()).snapshot()))
    snap["config"].pop("physical_contact_acoustic_emission", None)
    snap["world"].pop("contact_acoustic_state", None)
    for key in ("model", "identity"):
        if isinstance(snap.get(key), dict):
            snap[key].pop("public_preset", None)
    b2 = PhysicalSystemRuntime.restore(snap)
    assert pca.state_of(b2.world) is None
    assert pca.physical_contact_acoustic_emission_is_active(b2.config) is False
    assert not mechanism_snapshot(b2.config)["enabled"].get(MID, False)
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    s, rt = session(PRESET_ACANTHOSTEGA_LOCAL_SIGNAL)
    rt2 = TwoAgentRuntime.restore(json.loads(json.dumps(rt.snapshot())))
    rt2.step(); rt2.step()
    assert getattr(rt2.world, "contact_acoustic_state", None) is None
    assert lps.state_of(rt2.world).counters.get("physical_contact_emissions", 0) == 0


def test_29_repeated_run_same_ids_and_receipts():
    def go():
        h = impact()
        h.add("rx", CX + 3.0, CY + 1.0)
        h.run(3)
        h.bodies["body-0"].x, h.bodies["body-1"].x = CX - 3, CX + 3
        h.run(2)
        h.bodies["body-0"].x, h.bodies["body-1"].x = CX - 0.3, CX + 0.3
        h.run(3)
        return json.dumps([h.emissions(), h.measurements(), h.accepted()], sort_keys=True, default=str)
    assert go() == go()
    runs = []
    for _ in range(2):
        s, rt = session()
        for _ in range(3):
            rt.step()
        st = pca.state_of(rt.world)
        runs.append(json.dumps([st.emission_history, st.measurement_history], sort_keys=True, default=str))
    assert runs[0] == runs[1]


# ---------------------------------------------------------------- Observer / Analyzer / catalog extras


def test_30_preset_mechanism_and_catalog_acanthostega_only():
    assert normalize_preset_name("Acanthostega Phase B Contact Acoustics") == PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS
    assert MID in ec.acanthostega_contact_acoustics_mechanism_map()
    snap = mechanism_snapshot(acanthostega_contact_acoustics_config())
    assert MID in json.dumps(snap, default=str)
    assert MID not in json.dumps(mechanism_snapshot(tiktaalik_config()), default=str)
    from mechanistic_mind.physical_system.locomotion_profile import ACANTHOSTEGA_ONLY_MECHANISM_IDS
    assert MID in ACANTHOSTEGA_ONLY_MECHANISM_IDS


def test_31_analyzer_section_from_receipts():
    h = impact()
    h.add("rx", CX + 2.0, CY + 1.0)
    h.run(4)
    h.bodies["body-0"].x, h.bodies["body-1"].x = CX - 3, CX + 3
    h.run(1)
    h.bodies["body-0"].x, h.bodies["body-1"].x = CX - 0.25, CX + 0.25
    h.run(3)
    contact = h.measurements() + h.emissions()
    s = summarize_physical_contact_acoustics(contact, list(h.lst.reception_history))
    assert s["emissions_created"] == 2 and s["silent_resting_contact"] >= 3
    assert s["impulse_to_energy_monotone"] == "VERIFIED"
    assert s["resting_contact_reemissions"] == 0 and s["duplicate_emissions_same_pair_same_tick"] == 0
    assert s["provenance_quality"] == "VERIFIED" and s["linked_receptions"] >= 2
    text = format_physical_contact_acoustic_section(s)
    assert text.startswith("PHYSICAL CONTACT ACOUSTIC EVENTS")
    low = text.lower()
    assert "understanding" in low and "communication" in low   # only in the explicit NOT_ESTABLISHED lines
    assert "IMPACT_UNDERSTANDING" in text and "NOT_ESTABLISHED" in text
    empty = summarize_physical_contact_acoustics([], [])
    assert empty["status"] == "NOT_AVAILABLE"


def test_32_observer_serialization_researcher_only(contact_run):
    from mechanistic_mind.ui.psy_observer_web.serialize import world_frame
    rt, _ = contact_run
    summ = pca.researcher_summary(rt.world)
    assert summ and summ.get("agent_accessible") is False and summ["counters"]["emissions"] >= 1
    text = json.dumps(world_frame(rt), default=str)
    assert "contact_acoustic_summary" in text and "contact-impulse derived" in text
    for tok in ("BODY_SOUND", "PUSH_SOUND", "COLLISION_SOUND"):
        assert tok not in text
    ls_s, ls_rt = session(PRESET_ACANTHOSTEGA_LOCAL_SIGNAL)
    assert "contact_acoustic_summary" not in json.dumps(world_frame(ls_rt), default=str)


def test_33_frontend_single_apply_and_no_semantic_sound_names():
    app = APP.read_text()
    assert app.count('data-testid="apply-experiment"') == 1
    mp = (ROOT / "web" / "psy-observer" / "src" / "observer" / "modelPreset.ts").read_text()
    assert "contact-acoustic-overlay" in app
    # Preset options are rendered from MODEL_UI_PRESETS; contact acoustics must remain in the map.
    assert "UI_PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS" in app or "UI_PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS" in mp
    assert "'Acanthostega Phase B Contact Acoustics'" in mp and "'ACANTHOSTEGA_PHASE_B_CONTACT_ACOUSTICS'" in mp
    for tok in ("BODY_SOUND", "PUSH_SOUND", "COLLISION_SOUND", "APPLY CONTACT"):
        assert tok not in app


def test_34_experimenter_body_contact_sounds_and_shared_transport_steps_once():
    """Bug found in browser smoke: the Observer experimenter slot ran its own LPS end-of-tick step,
    advancing the shared transport clock before the container's contact/signal pass."""
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

    for preset in (PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS, PRESET_ACANTHOSTEGA_LOCAL_SIGNAL):
        s = ObserverSession()
        s.apply_experiment(preset_canonical(preset, seed=17))
        s.step(1)
        b = s.runtime.slots[0].body
        assert s.experimenter_spawn(x=(b.x + 0.8) % 32.0, y=b.y, theta=math.pi).get("accepted")
        assert all(getattr(sl, "_lps_parent_managed", False) for sl in s.runtime.slots)
        s.step(1)
        lst = lps.state_of(s.runtime.world)
        assert lst.counters["reprocess_suppressed"] == 0
        cst = pca.state_of(s.runtime.world)
        if preset == PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS:
            assert cst.counters["emissions"] == 1 and cst.counters["transport_rejected"] == 0
            assert cst.emission_history[0]["canonical_body_pair"] == ["body-0", "body-2"]
        else:
            assert cst is None and lst.counters.get("physical_contact_emissions", 0) == 0
