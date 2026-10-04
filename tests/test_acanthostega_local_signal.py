"""ACANTHOSTEGA LOCAL PHYSICAL SIGNAL TRANSPORT (ACANTHOSTEGA_PHASE_B_LOCAL_SIGNAL).

Numbered contract tests 1-51. Controlled harness: the authoritative world of a real runtime of
the new preset plus researcher-positioned bodies (deep copies of the runtime body) driven through
the same end-of-tick step the runtimes call. No runtime semantics are changed by the harness.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from mechanistic_mind.model.acanthostega import (
    acanthostega_column_transfer_config,
    acanthostega_local_signal_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import local_physical_signal_transport as lps
from mechanistic_mind.physical_system import oscillatory_signaling as oscmod
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
    PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
    PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
    PRESET_BETA31,
    beta31_mechanism_map,
    canonical_fingerprint,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.mechanism_registry import mechanism_snapshot, set_mechanism
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import checksum_of, rebuild_from_world
from mechanistic_mind.scientific_v3.local_physical_signal_summary import (
    format_local_physical_signal_section,
    summarize_local_physical_signal,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "acanthostega_local_signal"
FROZEN = "1621ef2c154864d1"
MID = lps.MECHANISM_ID
V, K, R, TH = 2.0, 0.08, 8.0, 0.03
SRC = (10.5, 10.5)


# ---------------------------------------------------------------- harness


class Harness:
    """Researcher-positioned bodies in the authoritative world of a new-preset runtime."""

    def __init__(self, seed: int = 17, cfg=None):
        self.cfg = cfg or acanthostega_local_signal_config()
        self.rt = PhysicalSystemRuntime(seed=seed, config=self.cfg)
        self.world = self.rt.world
        self.st = lps.state_of(self.world)
        assert self.st is not None
        self.bodies: dict = {}
        self.tick = int(self.world.tick)
        self.log: list[dict] = []

    def add(self, bid: str, x: float, y: float):
        b = copy.deepcopy(self.rt.body)
        b.x, b.y, b.vx, b.vy = float(x) % 32.0, float(y) % 32.0, 0.0, 0.0
        b.osc_emit_remaining = 0
        self.bodies[bid] = b
        return b

    def refs(self):
        return sorted(self.bodies.items())

    def emit(self, x=SRC[0], y=SRC[1], amplitude=0.8, frequency=0.5, bands=None):
        rec = lps.queue_researcher_emission(self.world, self.cfg, x=x, y=y, amplitude=amplitude,
                                            frequency=frequency, band_energies=bands)
        assert rec["status"] == "QUEUED", rec
        return rec

    def body_emit(self, bid, amplitude=0.8, freq_u=0.5, duration=1):
        b = self.bodies[bid]
        b.osc_amp_u, b.osc_freq_u, b.osc_emit_remaining = float(amplitude), float(freq_u), int(duration)

    def step(self, bodies=None):
        self.tick += 1
        self.world.tick = self.tick
        out = lps.step_end_of_tick(self.world, self.cfg, bodies if bodies is not None else self.refs(),
                                   tick_now=self.tick)
        for r in out.get("receptions") or []:
            self.log.append(r)
        return out

    def run(self, n):
        for _ in range(n):
            self.step()
        return self

    def frag(self, bid):
        return oscmod.cognition_osc_fragments(self.bodies[bid], self.world, self.cfg.oscillatory_signaling)

    def energy(self, bid):
        return float(sum(self.frag(bid).values()))

    def accepted(self, bid=None):
        return [r for r in self.log if r.get("accepted") and (bid is None or r["receiver_body_id"] == bid)]


def _line(h: Harness, ds, name="r"):
    for i, d in enumerate(ds):
        h.add(f"{name}{i}", SRC[0] + d, SRC[1])
    return h


def _obs_new_keys():
    ct = PhysicalSystemRuntime(seed=17, config=acanthostega_column_transfer_config()).agent_observation()
    ls = PhysicalSystemRuntime(seed=17, config=acanthostega_local_signal_config()).agent_observation()
    return ct, ls


# ---------------------------------------------------------------- preservation (1-8)


@pytest.fixture(scope="module")
def probe():
    before = json.loads((RESULTS / "preservation_before.json").read_text())
    proc = subprocess.run(
        [sys.executable, str(RESULTS / "preservation_probe.py")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return before, json.loads(proc.stdout)


def test_01_tiktaalik_fingerprint_seed17_unchanged(probe):
    before, now = probe
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN
    assert now["beta31_fingerprint"] == before["beta31_fingerprint"] == FROZEN
    assert now["beta31_mechanism_map"] == before["beta31_mechanism_map"]
    assert MID not in beta31_mechanism_map()


def test_02_tiktaalik_signaling_semantics_unchanged(probe):
    before, now = probe
    assert now["two_agent_signal"][PRESET_BETA31] == before["two_agent_signal"][PRESET_BETA31]
    tik = tiktaalik_config()
    set_mechanism(tik, MID, True)          # forced flag on Tiktaalik does not enable it
    lps.set_local_physical_signal_transport(tik, True)
    assert lps.local_physical_signal_transport_is_active(tik) is False
    assert getattr(tik, "local_physical_signal_transport", None) is None
    tik.oscillatory_signaling.mode = "EXPERIMENTAL"
    rt = PhysicalSystemRuntime(seed=17, config=tik)
    assert lps.state_of(rt.world) is None and rt.world.OSC_BANDS is not None  # legacy diffusion field


def test_03_tiktaalik_snapshots_unchanged(probe):
    before, now = probe
    assert now["runtime"]["TIKTAALIK"] == before["runtime"]["TIKTAALIK"]
    snap = PhysicalSystemRuntime(seed=17, config=tiktaalik_config()).snapshot()
    assert "local_physical_signal_transport" not in snap["config"]
    assert "local_signal_transport" not in snap["world"]


def test_04_previous_acanthostega_presets_unchanged(probe):
    before, now = probe
    assert now == before
    ct = preset_canonical(PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, seed=17)["mechanisms"]
    ls = preset_canonical(PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, seed=17)["mechanisms"]
    assert MID not in ct and ls[MID] is True
    assert {k: v for k, v in ls.items() if k != MID} == ct
    cfg = acanthostega_column_transfer_config()
    assert lps.local_physical_signal_transport_is_active(cfg) is False
    assert getattr(cfg, "local_physical_signal_transport", None) is None


def test_05_column_transfer_unchanged(probe):
    before, now = probe
    for sec in ("preset_canonical", "identity", "mechanism_snapshot", "runtime"):
        assert now[sec][PRESET_ACANTHOSTEGA_COLUMN_TRANSFER] == before[sec][PRESET_ACANTHOSTEGA_COLUMN_TRANSFER]
    assert now["two_agent_signal"][PRESET_ACANTHOSTEGA_COLUMN_TRANSFER] == \
        before["two_agent_signal"][PRESET_ACANTHOSTEGA_COLUMN_TRANSFER]


def test_06_procedural_columns_unchanged(probe):
    before, now = probe
    for sec in ("preset_canonical", "identity", "mechanism_snapshot", "runtime"):
        assert now[sec][PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS] == before[sec][PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS]
    h = Harness()
    snap_cols = json.dumps(h.rt.snapshot()["world"]["surface_columns"], sort_keys=True)
    ref = PhysicalSystemRuntime(seed=17, config=acanthostega_column_transfer_config())
    assert snap_cols == json.dumps(ref.snapshot()["world"]["surface_columns"], sort_keys=True)


def test_07_spatial_index_checksum_semantics_unchanged():
    h = Harness()
    idx = h.world.spatial_contents
    before = (checksum_of(idx), int(idx.generation), len(idx.by_entity))
    body = h.rt.body
    h.emit(body.x + 1.0, body.y)
    for _ in range(6):
        h.tick += 1
        h.world.tick = h.tick
        lps.step_end_of_tick(h.world, h.cfg, [("body-0", body)], tick_now=h.tick)
    assert (checksum_of(idx), int(idx.generation), len(idx.by_entity)) == before
    assert all("signal" not in str(k) for k in idx.by_entity)


def test_08_locomotion_traction_vision_unchanged():
    ct, ls = _obs_new_keys()
    for k, v in ct.items():  # vision / proprioception / traction channels identical at tick 0
        assert ls[k] == v, k
    h = Harness()
    b = h.add("a", 12.3, 9.7)
    b.vx, b.vy, b.heading = 0.1, -0.05, 0.7
    pose = (b.x, b.y, b.vx, b.vy, b.heading)
    h.body_emit("a", duration=3)
    h.emit(12.0, 10.0)
    h.run(6)
    assert (b.x, b.y, b.vx, b.vy, b.heading) == pose  # transport never moves a body


# ---------------------------------------------------------------- transport (9-31)


def test_09_stable_deterministic_emission_id():
    ids = []
    for _ in range(2):
        h = Harness()
        h.add("a", 5.5, 5.5)
        h.emit()
        h.emit(20.5, 20.5)
        h.step()
        h.step()
        h.emit()
        h.step()
        ids.append([e["emission_id"] for e in h.st.emission_history])
    assert ids[0] == ids[1]
    assert ids[0] == ["signal-emission-000000000-0000", "signal-emission-000000000-0001",
                      "signal-emission-000000002-0000"]
    assert all(re.fullmatch(r"signal-emission-\d{9}-\d{4}", i) for i in ids[0])


def test_10_physical_source_pose_captured_at_emission():
    h = Harness()
    b = h.add("a", 7.25, 3.75)
    h.add("b", 9.0, 3.75)
    h.body_emit("a")
    out = h.step()
    em = out["emissions"][0]
    assert (em["physical_origin"]["x"], em["physical_origin"]["y"]) == (7.25, 3.75)
    assert em["physical_origin"]["cell"] == [7, 3]
    assert em["selection_provenance"] == lps.PROV_ENDOGENOUS
    b.x, b.y = 8.25, 3.75  # emitter moves after emission: source stays where it was
    h.step()
    active = h.st.active[0] if h.st.active else None
    assert active is not None and (active.source_x, active.source_y) == (7.25, 3.75)
    assert all(r["source_position_at_emission"] == [7.25, 3.75] for r in h.log)


def test_11_minimum_propagation_delay_is_one():
    h = _line(Harness(), [0.0, 0.5, 1.9, 3.0, 5.0])
    h.emit()
    h.run(5)
    assert len(h.accepted()) == 5
    for r in h.accepted():
        assert r["propagation_delay"] >= 1 and r["arrival_tick"] >= r["emission_tick"] + 1
    zero = [r for r in h.accepted() if r["toroidal_distance"] == 0.0][0]
    assert zero["propagation_delay"] == 1


def test_12_no_same_tick_reception():
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_local_signal_config())
    b = rt.body
    lps.queue_researcher_emission(rt.world, rt.config, x=b.x, y=b.y, amplitude=0.8, frequency=0.5)
    t0 = rt.tick
    before = rt.agent_observation()  # observation of tick T precedes the emission of tick T
    assert sum(v for k, v in before.items() if k.startswith("osc_")) == 0.0
    rt.step()
    st = lps.state_of(rt.world)
    em = st.emission_history[-1]
    assert em["emission_tick"] == t0
    rec = [r for r in st.reception_history if r["emission_id"] == em["emission_id"]]
    assert rec and all(r["arrival_tick"] == t0 + 1 for r in rec)
    after = rt.agent_observation()
    assert sum(v for k, v in after.items() if k.startswith("osc_")) > 0.0


def test_13_energy_near_gt_mid_gt_far_gt_zero():
    h = _line(Harness(), [1.0, 3.0, 6.0])
    h.emit()
    e = {}
    for _ in range(4):
        h.step()
        for bid in ("r0", "r1", "r2"):
            e[bid] = max(e.get(bid, 0.0), h.energy(bid))
    assert e["r0"] > e["r1"] > e["r2"] > 0.0
    rec = {r["receiver_body_id"]: r for r in h.accepted()}
    assert rec["r0"]["total_received_energy"] > rec["r1"]["total_received_energy"] > rec["r2"]["total_received_energy"]
    total = h.st.emission_history[0]["total_emitted_energy"]
    for d, bid in ((1.0, "r0"), (3.0, "r1"), (6.0, "r2")):
        assert abs(rec[bid]["total_received_energy"] - total / (1 + K * d * d)) < 1e-9


def test_14_outside_range_receives_nothing():
    h = _line(Harness(), [9.0, 10.0, 14.0])
    h.emit()
    for _ in range(6):
        h.step()
        assert all(h.energy(b) == 0.0 for b in ("r0", "r1", "r2"))
    assert h.accepted() == []
    beyond = [r for r in h.log if r["rejection_reason"] == lps.R_BEYOND_RANGE]
    assert {r["receiver_body_id"] for r in beyond} <= {"r0"}  # only the near-range candidate is receipted
    assert not h.st.active


def test_15_below_threshold_receives_nothing():
    h = _line(Harness(), [1.0, 4.0])
    h.emit(amplitude=0.02)
    got = {"r0": 0.0, "r1": 0.0}
    for _ in range(4):
        h.step()
        for b in got:
            got[b] = max(got[b], h.energy(b))
    assert got["r0"] > 0.0 and got["r1"] == 0.0
    rej = [r for r in h.log if r["receiver_body_id"] == "r1"]
    assert rej and rej[0]["rejection_reason"] == lps.R_BELOW_THRESHOLD and rej[0]["accepted"] is False


def test_16_arrival_tick_deterministic():
    ds = [0.0, 1.0, 2.0, 2.5, 4.0, 5.9, 7.99]
    runs = []
    for _ in range(2):
        h = _line(Harness(), ds)
        h.emit()
        h.run(5)
        runs.append({r["receiver_body_id"]: r["arrival_tick"] for r in h.accepted()})
    assert runs[0] == runs[1]
    for i, d in enumerate(ds):
        assert runs[0][f"r{i}"] == 0 + max(1, math.ceil(d / V)), (d, runs[0])


def test_17_wrap_uses_shortest_toroidal_distance():
    h = Harness()
    h.add("edge", 31.5, 16.5)
    h.add("far_inside", 5.5, 16.5)
    h.emit(0.5, 16.5)
    h.run(5)
    rec = {r["receiver_body_id"]: r for r in h.accepted()}
    assert rec["edge"]["toroidal_distance"] == pytest.approx(1.0)
    assert rec["edge"]["wraps_torus"] is True and rec["edge"]["arrival_tick"] == 1
    assert rec["far_inside"]["wraps_torus"] is False and rec["far_inside"]["arrival_tick"] == 3
    assert h.st.counters["wrap_receptions"] == 1


def test_18_multiple_receivers_in_range_receive_locally():
    h = Harness()
    for i, (dx, dy) in enumerate([(1, 0), (0, -3), (-4, 2), (2.5, 2.5)]):
        h.add(f"n{i}", SRC[0] + dx, SRC[1] + dy)
    h.emit()
    h.run(5)
    assert sorted({r["receiver_body_id"] for r in h.accepted()}) == ["n0", "n1", "n2", "n3"]


def test_19_distant_agents_do_not_receive():
    h = Harness()
    h.add("near", SRC[0] + 2, SRC[1])
    h.add("far", SRC[0] + 12, SRC[1] + 3)
    h.add("antipode", SRC[0] + 16, SRC[1] + 16)
    h.emit()
    seen = {"far": 0.0, "antipode": 0.0}
    for _ in range(6):
        h.step()
        for b in seen:
            seen[b] += h.energy(b)
    assert seen == {"far": 0.0, "antipode": 0.0}
    assert {r["receiver_body_id"] for r in h.log} == {"near"}


def test_20_self_reception_same_law_no_identity_special_case():
    h = Harness()
    h.add("a", 12.5, 12.5)
    h.add("twin", 12.5, 12.5)  # co-located foreign body
    h.body_emit("a")
    h.run(2)
    rec = {r["receiver_body_id"]: r for r in h.accepted()}
    assert rec["a"]["self_reception"] is True and rec["twin"]["self_reception"] is False
    assert rec["a"]["propagation_delay"] == rec["twin"]["propagation_delay"] == 1
    assert rec["a"]["total_received_energy"] == rec["twin"]["total_received_energy"]
    assert h.st.counters["self_receptions"] == 1 and h.st.counters["foreign_receptions"] == 1
    for key in h.frag("a"):
        assert "self" not in key and "my" not in key


def _raw(h, bid):
    e = h.st.auditory.get(bid)
    return (list(e["left"]), list(e["right"])) if e else None


def test_21_overlapping_bands_aggregate_physically():
    p1 = [0.6, 0.3, 0.0, 0.0, 0.0, 0.0]
    p2 = [0.0, 0.0, 0.0, 0.4, 0.9, 1.5]
    single = []
    for bands in (p1, p2):
        h = Harness()
        h.add("rx", 12.5, 10.5)
        h.emit(10.5, 10.5, bands=bands)
        h.step()
        single.append(_raw(h, "rx"))
    h = Harness()
    h.add("rx", 12.5, 10.5)
    h.emit(10.5, 10.5, bands=p1)
    h.emit(14.5, 10.5, bands=p2)  # same distance, other side: simultaneous arrival
    h.step()
    both = _raw(h, "rx")
    assert h.st.auditory["rx"]["n"] == 2 and h.st.counters["overlap_aggregations"] == 1
    frag = h.frag("rx")
    for i in range(6):
        l_sum = single[0][0][i] + single[1][0][i]
        assert both[0][i] == pytest.approx(l_sum)
        assert frag[f"osc_l_{i}"] == pytest.approx(min(1.0, l_sum / h.st.config.sensor_scale))


def test_22_no_source_list_in_agent_payload():
    keys = None
    for n in (0, 1, 2):
        h = Harness()
        h.add("rx", 12.5, 10.5)
        for j in range(n):
            h.emit(10.5 + 4 * j, 10.5)
        h.step()
        f = h.frag("rx")
        assert all(isinstance(v, float) for v in f.values())
        keys = keys or sorted(f)
        assert sorted(f) == keys
    assert keys == sorted([f"osc_l_{i}" for i in range(6)] + [f"osc_r_{i}" for i in range(6)])


@pytest.fixture(scope="module")
def two_agent_run():
    """Cognition-ON two-agent Observer run of the new preset with an endogenous OSC emission."""
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

    s = ObserverSession()
    s.apply_experiment(preset_canonical(PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, seed=17))
    rt = s.runtime
    cfg0 = rt.slots[0].config
    oscmod.set_undercover_osc_params(rt.slots[0].body, frequency=0.4, amplitude=0.8, duration=3,
                                     cfg=cfg0.oscillatory_signaling, emit_now=True)
    obs_log = []
    for _ in range(10):
        obs_log.append(rt.observations())
        rt.step()
    return rt, obs_log


def test_23_source_identity_absent_from_cognition(two_agent_run):
    rt, obs_log = two_agent_run
    st = lps.state_of(rt.world)
    assert st.counters["foreign_receptions"] >= 1
    for obs in obs_log:
        for o in obs:
            text = repr(o)
            assert audit_cognition_payload(o) == []
            for tok in ("body-", "agent_", "signal-emission", "source", "emitter", "undercover"):
                assert tok not in text, tok


def test_24_source_coordinates_absent():
    ct, ls = _obs_new_keys()
    extra = set(ls) - set(ct)
    assert extra == {f"osc_l_{i}" for i in range(6)} | {f"osc_r_{i}" for i in range(6)}
    for k in extra:
        for tok in ("x", "y", "origin", "pos", "coord"):
            assert tok not in k.replace("osc_", ""), k


def test_25_exact_distance_and_bearing_absent(two_agent_run):
    rt, obs_log = two_agent_run
    for obs in obs_log:
        for o in obs:
            for k in o:
                if k.startswith("osc_"):
                    assert re.fullmatch(r"osc_[lr]_\d", k)
                for tok in ("distance", "bearing", "direction", "range", "delay"):
                    assert not (k.startswith("osc_") and tok in k)
    for tok in ("toroidal_distance", "propagation_delay"):
        assert tok in FORBIDDEN_TOKENS


def test_26_semantic_message_absent(two_agent_run):
    rt, obs_log = two_agent_run
    for obs in obs_log:
        for o in obs:
            low = repr(o).lower()
            assert "message" not in low and "semantic" not in low and "word" not in low
    st = lps.state_of(rt.world)
    for r in st.emission_history + st.reception_history:
        assert r["semantic_message"] is False and r["direct_delivery"] is False
        assert r["source_identity_exposed"] is False and r["exact_distance_exposed"] is False


def test_27_direct_delivery_path_absent_in_new_preset(monkeypatch):
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

    def boom(*a, **k):
        raise AssertionError("legacy OSC_BANDS transport must not run in the local-signal preset")

    monkeypatch.setattr(oscmod, "step_oscillatory_signaling", boom)
    s = ObserverSession()
    s.apply_experiment(preset_canonical(PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, seed=17))
    rt = s.runtime
    rt.slots[1].body.x = (rt.slots[0].body.x + 16.0) % 32.0  # receiver far outside range
    rt.slots[1].body.y = (rt.slots[0].body.y + 12.0) % 32.0
    rt._lps_bind()
    oscmod.set_undercover_osc_params(rt.slots[0].body, frequency=0.5, amplitude=1.0, duration=4,
                                     cfg=rt.slots[0].config.oscillatory_signaling, emit_now=True)
    far_energy = 0.0
    for _ in range(8):
        obs = rt.observations()
        far_energy += sum(v for k, v in obs[1].items() if k.startswith("osc_"))
        rt.step()
    st = lps.state_of(rt.world)
    assert st.counters["endogenous_emissions"] >= 1
    assert far_energy == 0.0 and "body-1" not in {r["receiver_body_id"] for r in st.reception_history}
    assert rt.world.OSC_BANDS is None and st.counters["direct_delivery_attempts"] == 0
    # the auditory buffer written by physical reception is the only source of osc_* values
    h = Harness()
    h.add("a", 12.5, 12.5)
    h.emit(12.5, 12.5)
    h.step()
    assert h.energy("a") > 0
    h.st.auditory.clear()
    assert h.energy("a") == 0.0


def test_28_process_order_permutation_unchanged():
    import itertools

    results = []
    for perm in itertools.permutations(range(4), 4):
        h = Harness()
        for i, (dx, dy) in enumerate([(1, 0), (0, 3), (-5, 1), (2, -6)]):
            h.add(f"p{i}", SRC[0] + dx, SRC[1] + dy)
        h.body_emit("p0", duration=2)
        h.emit()
        refs = h.refs()
        for _ in range(6):
            h.step(bodies=[refs[j] for j in perm])
        results.append(json.dumps([h.log, h.st.emission_history], sort_keys=True, default=str))
    assert len(set(results)) == 1


def test_29_expired_emissions_removed():
    h = _line(Harness(), [1.0, 7.0])
    h.emit()
    h.emit(20.0, 20.0)
    h.step()
    assert len(h.st.active) == 2
    exp = h.st.active[0].expiry_tick
    assert exp == 0 + h.st.config.max_arrival_delay == 4
    h.run(3)
    assert h.st.active == [] and h.st.counters["expired"] == 2
    ov = lps.observer_overlay(h.world)
    assert ov["active_count"] == 0 and ov["expired_total"] == 2


def test_30_history_and_active_set_bounded():
    cfg = acanthostega_local_signal_config()
    cfg.local_physical_signal_transport.max_active_emissions = 6
    h = Harness(cfg=cfg)
    for i in range(10):
        h.add(f"b{i}", 3.0 * i + 0.5, 12.5)
    for _ in range(40):
        for j in range(3):
            h.emit(3.0 * j + 1.0, 12.0)
        h.step()
        assert len(h.st.active) <= 6
    lim = h.st.config.history_limit
    assert len(h.st.emission_history) <= lim and len(h.st.reception_history) <= lim
    assert len(h.st.recent_emission_refs) <= 64 and len(h.st.distance_samples) <= 256
    assert len(h.st.non_receivers_by_emission) <= lim and len(h.st.pending) == 0
    assert h.st.counters["capacity_rejected"] > 0


def test_31_duplicate_reception_suppressed():
    h = Harness()
    h.add("a", 12.5, 10.5)
    h.emit()
    h.step()
    assert len(h.accepted("a")) == 1
    again = lps.step_end_of_tick(h.world, h.cfg, h.refs(), tick_now=h.tick)
    assert again["status"] == "ALREADY_PROCESSED" and h.st.counters["reprocess_suppressed"] == 1
    h.st.last_processed_tick -= 1  # replay the same tick (e.g. a re-driven step)
    h.st.prev_pose["a"] = [30.0, 30.0]
    replay = lps.step_end_of_tick(h.world, h.cfg, h.refs(), tick_now=h.tick)
    assert [r for r in replay["receptions"] if r["accepted"]] == []
    assert h.st.counters["duplicates_suppressed"] >= 1 and h.st.counters["accepted_receptions"] == 1


# ---------------------------------------------------------------- receiver movement (32-36)


def _walk(h, bid, dx_per_tick, n):
    out = []
    for _ in range(n):
        h.bodies[bid].x = (h.bodies[bid].x + dx_per_tick) % 32.0
        h.step()
        out.append(h.energy(bid))
    return out


def test_32_receiver_pose_at_arrival_is_used():
    h = Harness()
    h.add("m", SRC[0] + 5.0, SRC[1])
    h.step()  # establish previous pose
    h.emit()
    h.tick += 0
    _walk(h, "m", -1.0, 4)  # approaches the source by 1 cell / tick
    rec = h.accepted("m")
    assert len(rec) == 1
    r = rec[0]
    assert r["receiver_position_at_reception"][0] == pytest.approx(SRC[0] + 3.0)
    assert r["toroidal_distance"] == pytest.approx(3.0) and r["propagation_delay"] == 2
    em = h.st.emission_history[-1]
    assert r["total_received_energy"] == pytest.approx(em["total_emitted_energy"] / (1 + K * 9.0))


def test_33_receiver_leaving_before_arrival_does_not_receive():
    h = Harness()
    h.add("leaver", SRC[0] + 7.5, SRC[1])
    h.add("stayer", SRC[0], SRC[1] + 7.5)
    h.step()
    h.emit()
    got = _walk(h, "leaver", +1.0, 5)
    assert sum(got) == 0.0 and h.accepted("leaver") == []
    assert len(h.accepted("stayer")) == 1 and h.accepted("stayer")[0]["propagation_delay"] == 4


def test_34_receiver_entering_at_arrival_receives():
    h = Harness()
    h.add("enter", SRC[0] + 12.0, SRC[1])  # outside range at emission time
    h.step()
    h.emit()
    got = _walk(h, "enter", -1.0, 5)
    rec = h.accepted("enter")
    assert len(rec) == 1 and rec[0]["propagation_delay"] == 4
    assert rec[0]["toroidal_distance"] == pytest.approx(8.0) and got[3] > 0.0
    assert lps.RECEIVER_POLICY == "POSE_AT_ARRIVAL_WAVEFRONT_CROSSING_V1"


def test_35_same_cell_uses_exact_distance_not_cell_equality():
    h = Harness()
    h.add("inner", 12.45, 10.5)  # d = 1.95 (cell 12)
    h.add("outer", 12.55, 10.5)  # d = 2.05 (same cell 12)
    h.add("far_in_cell", 13.9, 10.5)  # d = 3.4 (cell 13)
    h.add("near_in_cell", 13.1, 10.5)  # d = 2.6 (cell 13)
    h.emit()
    h.run(3)
    rec = {r["receiver_body_id"]: r for r in h.accepted()}
    assert rec["inner"]["arrival_tick"] == 1 and rec["outer"]["arrival_tick"] == 2
    assert rec["near_in_cell"]["total_received_energy"] > rec["far_in_cell"]["total_received_energy"]
    # a body moving inside one cell crosses the front by exact distance
    h2 = Harness()
    h2.add("mover", 12.58, 10.5)
    h2.step()
    h2.emit()
    h2.bodies["mover"].x = 12.40  # still cell 12, now d = 1.9 <= front(1) = 2
    h2.step()
    assert len(h2.accepted("mover")) == 1 and h2.accepted("mover")[0]["arrival_tick"] == 2


def test_36_spatial_index_bounds_candidates():
    h = Harness()
    for i in range(48):
        h.add(f"b{i:02d}", (i * 7.3) % 32.0, (i * 11.9) % 32.0)
    rebuild_from_world(h.world, h.refs(), tick=h.tick, reason="test_rebuild", config=h.cfg)
    h.emit(16.0, 16.0)
    h.run(5)
    st = h.st
    assert st.counters["index_fallbacks"] == 0
    assert st.last_step["index_source"] == "MULTI_CONTENT_SPATIAL_INDEX"
    local = sum(1 for b in h.bodies.values()
                if lps.toroidal_distance(16.0, 16.0, b.x, b.y, 32, 32)[0] <= R + V + lps.CELL_MARGIN + 1.0)
    # cost follows local candidates, never all bodies x all ticks
    assert st.counters["candidate_refs_checked"] <= 3 * local < 48 * 4
    assert st.cost_max["shell_cells"] < 32 * 32
    in_range = sum(1 for b in h.bodies.values()
                   if lps.toroidal_distance(16.0, 16.0, b.x, b.y, 32, 32)[0] <= R)
    assert len({r["receiver_body_id"] for r in h.accepted()}) == in_range


# ---------------------------------------------------------------- snapshot / restore (37-42)


def _rt():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_local_signal_config())


def _recs(rt, after_tick):
    return [(r["emission_id"], r["receiver_body_id"], r["arrival_tick"], round(r["toroidal_distance"], 9),
             r["accepted"]) for r in lps.state_of(rt.world).reception_history if r["arrival_tick"] > after_tick]


def test_37_pending_emission_survives_restore():
    rt = _rt()
    b = rt.body
    lps.queue_researcher_emission(rt.world, rt.config, x=b.x + 6.0, y=b.y, amplitude=0.9, frequency=0.5)
    snap_q = json.loads(json.dumps(rt.snapshot()))  # queued, not yet emitted
    r_q = PhysicalSystemRuntime.restore(snap_q)
    assert len(lps.state_of(r_q.world).pending) == 1
    rt.step()
    snap = json.loads(json.dumps(rt.snapshot()))  # emitted, wavefront still travelling
    st = lps.state_of(rt.world)
    assert len(st.active) == 1 and not [r for r in st.reception_history if r["accepted"]]
    back = PhysicalSystemRuntime.restore(snap)
    stb = lps.state_of(back.world)
    assert [e.to_dict() for e in stb.active] == [e.to_dict() for e in st.active]
    assert stb.active[0].expiry_tick == st.active[0].expiry_tick


def test_38_post_restore_arrival_matches_control():
    rt = _rt()
    b = rt.body
    lps.queue_researcher_emission(rt.world, rt.config, x=b.x + 6.0, y=b.y, amplitude=0.9, frequency=0.5)
    rt.step()
    t = rt.tick
    back = PhysicalSystemRuntime.restore(json.loads(json.dumps(rt.snapshot())))
    for _ in range(5):
        rt.step()
        back.step()
    assert _recs(rt, t) == _recs(back, t) and _recs(rt, t)
    assert (rt.body.x, rt.body.y) == (back.body.x, back.body.y)


def test_39_delivered_reception_not_repeated_after_restore():
    rt = _rt()
    b = rt.body
    lps.queue_researcher_emission(rt.world, rt.config, x=b.x, y=b.y, amplitude=0.9, frequency=0.5)
    rt.step()
    st = lps.state_of(rt.world)
    eid = st.emission_history[-1]["emission_id"]
    assert [r for r in st.reception_history if r["emission_id"] == eid and r["accepted"]]
    back = PhysicalSystemRuntime.restore(json.loads(json.dumps(rt.snapshot())))
    n0 = lps.state_of(back.world).counters["accepted_receptions"]
    for _ in range(5):
        back.step()
    stb = lps.state_of(back.world)
    assert stb.counters["accepted_receptions"] == n0
    assert sum(1 for r in stb.reception_history if r["emission_id"] == eid and r["accepted"]) == 1


def test_40_ids_not_reused_after_restore():
    rt = _rt()
    for _ in range(2):
        lps.queue_researcher_emission(rt.world, rt.config, x=3.0, y=3.0, amplitude=0.5)
    rt.step()
    before = {e["emission_id"] for e in lps.state_of(rt.world).emission_history}
    back = PhysicalSystemRuntime.restore(json.loads(json.dumps(rt.snapshot())))
    stb = lps.state_of(back.world)
    assert (stb.alloc_tick, stb.alloc_next) == (lps.state_of(rt.world).alloc_tick, lps.state_of(rt.world).alloc_next)
    lps.queue_researcher_emission(back.world, back.config, x=3.0, y=3.0, amplitude=0.5)
    back.step()
    new = {e["emission_id"] for e in stb.emission_history} - before
    assert len(new) == 1 and new.isdisjoint(before) and max(new) > max(before)


def test_41_old_snapshot_restores_off():
    old = PhysicalSystemRuntime.restore(PhysicalSystemRuntime(seed=17, config=acanthostega_column_transfer_config()).snapshot())
    assert lps.state_of(old.world) is None and not lps.local_physical_signal_transport_is_active(old.config)
    assert getattr(old.config, "local_physical_signal_transport", None) is None
    snap = json.loads(json.dumps(_rt().snapshot()))
    snap["config"].pop("local_physical_signal_transport")
    snap["world"].pop("local_signal_transport", None)
    back = PhysicalSystemRuntime.restore(snap)
    assert lps.state_of(back.world) is None and not lps.local_physical_signal_transport_is_active(back.config)
    snap2 = json.loads(json.dumps(_rt().snapshot()))
    snap2["config"].pop("local_physical_signal_transport")  # state without config -> dropped (OFF)
    back2 = PhysicalSystemRuntime.restore(snap2)
    assert lps.state_of(back2.world) is None


def test_42_tiktaalik_snapshot_has_no_new_fields():
    tik = tiktaalik_config()
    set_mechanism(tik, MID, True)
    rt = PhysicalSystemRuntime(seed=17, config=tik)
    for _ in range(3):
        rt.step()
    snap = rt.snapshot()
    assert "local_physical_signal_transport" not in snap["config"]
    assert "local_signal_transport" not in snap["world"]
    assert "local_signal_transport" not in json.dumps(snap)
    back = PhysicalSystemRuntime.restore(json.loads(json.dumps(snap)))
    assert lps.state_of(back.world) is None


# ---------------------------------------------------------------- frontend / scientific (43-51)

APP = ROOT / "web" / "psy-observer" / "src" / "App.tsx"
PRESET_TS = ROOT / "web" / "psy-observer" / "src" / "observer" / "modelPreset.ts"
DIST = ROOT / "mechanistic_mind" / "ui" / "psy_observer_web" / "web_dist"
LABEL = "Acanthostega Phase B Local Physical Signal"


def test_43b_observer_preflight_ready_and_step_advances():
    """Regression (found by browser smoke): OSC availability must accept the local transport state
    (OSC_BANDS is intentionally absent in the new preset), so Observer preflight is READY and STEP works."""
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

    s = ObserverSession()
    s.apply_experiment(preset_canonical(PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, seed=17))
    assert getattr(s.runtime.world, "OSC_BANDS", None) is None
    r = s.researcher_local_signal_emission({"amplitude": 0.8, "frequency": 0.5})
    assert r["accepted"] is True and r["receipt"]["direct_cognition_delivery"] is False
    s.step(n=1)
    assert (s._preflight_result or {}).get("status") == "READY"
    assert int(s.runtime.tick) == 1
    st = s.runtime.world.local_signal_transport
    assert st.counters["intervention_emissions"] == 1


def test_43_new_preset_visible_in_common_selector():
    preset = PRESET_TS.read_text()
    app = APP.read_text()
    assert f"'{LABEL}'" in preset and "UI_PRESET_ACANTHOSTEGA_LOCAL_SIGNAL," in preset
    assert app.count("<option>{UI_PRESET_ACANTHOSTEGA_LOCAL_SIGNAL}</option>") == 2
    assert normalize_preset_name(LABEL) == PRESET_ACANTHOSTEGA_LOCAL_SIGNAL
    assert normalize_preset_name("Acanthostega Phase B Column Transfer") == PRESET_ACANTHOSTEGA_COLUMN_TRANSFER
    from mechanistic_mind.model.lines import identity_for_config

    meta = identity_for_config(acanthostega_local_signal_config(), seed=17, tick=0)
    assert meta["phase_label"] == LABEL and meta["local_physical_signal_transport"] is True
    assert meta["conservative_surface_column_transfer"] is True
    cat = {m["id"]: m for m in mechanism_snapshot(acanthostega_local_signal_config())["mechanisms"]}
    assert cat[MID]["enabled"] is True
    assert MID not in {m["id"] for m in mechanism_snapshot(acanthostega_column_transfer_config())["mechanisms"]}


def test_44_single_apply_button():
    app = APP.read_text()
    assert app.count('data-testid="apply-experiment"') == 1
    assert "APPLY LOCAL SIGNAL" not in app and "apply-local-signal" not in app


def test_45_draft_persists_through_apply():
    from mechanistic_mind.physical_system.experiment_canonical import canonical_from_runtime
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

    s = ObserverSession()
    s.apply_experiment(preset_canonical(LABEL, seed=17))
    assert s._canonical_requested["public_preset"] == PRESET_ACANTHOSTEGA_LOCAL_SIGNAL
    back = canonical_from_runtime(s.runtime)
    assert normalize_preset_name(back["public_preset"]) == PRESET_ACANTHOSTEGA_LOCAL_SIGNAL
    assert back["mechanisms"][MID] is True and back["model_line"] == "ACANTHOSTEGA"
    s2 = ObserverSession()
    s2.apply_experiment(back)  # the persisted draft re-applies to the same mechanism state
    assert lps.local_physical_signal_transport_is_active(s2.runtime.slots[0].config)
    s3 = ObserverSession()
    s3.apply_experiment(preset_canonical(PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, seed=17))
    assert lps.state_of(s3.runtime.world) is None


def test_46_researcher_overlay_marked():
    from mechanistic_mind.ui.psy_observer_web.serialize import world_frame
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

    app = APP.read_text()
    assert 'data-testid="local-signal-overlay"' in app
    for label in lps.OBSERVER_LABELS:
        assert label in app
    s = ObserverSession()
    s.apply_experiment(preset_canonical(PRESET_ACANTHOSTEGA_LOCAL_SIGNAL, seed=17))
    rec = s.researcher_local_signal_emission({"amplitude": 0.8})
    assert rec["accepted"] and rec["agent_action"] is False and rec["researcher_only"] is True
    s.runtime.step()
    wf = world_frame(s.runtime)
    ov = wf["local_signal_overlay"]
    assert wf["local_signal_researcher_only"] is True and list(ov["labels"]) == list(lps.OBSERVER_LABELS)
    assert ov["active_count"] == 1 and ov["active"][0]["front_radius"] <= ov["active"][0]["maximum_range"]
    assert ov["agent_accessible"] is False and ov["semantic_message"] is False
    for o in s.runtime.observations():
        assert "local_signal" not in repr(o) and "signal-emission" not in repr(o)
    s2 = ObserverSession()
    s2.apply_experiment(preset_canonical(PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, seed=17))
    assert "local_signal_overlay" not in world_frame(s2.runtime)


def _graph_harness():
    h = Harness()
    h.add("body-a", 10.5, 10.5)
    h.add("body-b", 13.5, 10.5)
    h.add("body-far", 26.5, 26.5)
    h.body_emit("body-a", duration=2)
    h.run(4)
    events = list(h.st.emission_history) + list(h.st.reception_history)
    return h, events


def test_47_analyzer_reports_local_communication_graph():
    h, events = _graph_harness()
    s = summarize_local_physical_signal(events, bodies=sorted(h.bodies), maximum_range=R,
                                        reception_threshold=TH, agent_leakage_hits=0,
                                        direct_delivery_attempts=0)
    assert s["section"] == "LOCAL PHYSICAL SIGNAL TRANSPORT"
    assert s["communication_graph"]["edges"] == {"body-a->body-a": 2, "body-a->body-b": 2}
    assert "body-far" in s["communication_graph"]["nodes"]
    assert all("body-far" in v for v in s["agents_that_did_not_receive"].values())
    assert s["global_delivery_occurred"] is False and s["max_observed_reception_distance"] == pytest.approx(3.0)
    assert s["MATERIAL_DEPENDENT_ACOUSTICS"] == "NOT_IMPLEMENTED"
    assert s["GEOMETRY_AWARE_ACOUSTICS"] == "NOT_IMPLEMENTED"
    assert s["ATMOSPHERIC_ACOUSTICS"] == "NOT_IMPLEMENTED"
    assert s["SEMANTIC_COMMUNICATION"] == "NOT_ESTABLISHED"
    assert "no_same_tick_reception" in s["VERIFIED"] and "direct_delivery_audit" in s["VERIFIED"]
    text = format_local_physical_signal_section(s)
    for needle in ("LOCAL PHYSICAL SIGNAL TRANSPORT", "OBSERVED:", "VERIFIED:", "NOT_IMPLEMENTED:",
                   "communication_graph", "global_delivery_occurred: NO",
                   "SEMANTIC_COMMUNICATION = NOT_ESTABLISHED"):
        assert needle in text
    assert "progress" not in text.lower() and "█" not in text


def test_48_no_semantic_acoustic_labels():
    h, events = _graph_harness()
    text = format_local_physical_signal_section(summarize_local_physical_signal(events)).lower()
    app = APP.read_text()
    start = app.index('data-testid="local-signal-overlay"')
    block = app[start:start + 3000].lower()
    for bad in ("message from", "voice", "word", "language", "music", "song", "call from", "sound of",
                "speaker", "listener", "source_direction", "source_distance"):
        assert bad not in text, bad
        assert bad not in block, bad
    assert "not a semantic message" in " ".join(lps.OBSERVER_LABELS)


def test_49_frontend_tests_pass():
    log = (RESULTS / "frontend_tests.log").read_text()
    assert "ℹ fail 0" in log and "exit=0" in log
    m = re.search(r"ℹ pass (\d+)", log)
    assert m and int(m.group(1)) >= 293


def test_50_production_build_updated():
    bundle = "".join(p.read_text(errors="ignore") for p in DIST.rglob("*.js"))
    assert LABEL in bundle and "local-signal-overlay" in bundle
    assert "/api/research/local-signal-emission" in bundle
    assert "exit=0" in (RESULTS / "frontend_build.log").read_text()


def test_51_acanthostega_suite_gate():
    names = sorted(p.name for p in (ROOT / "tests").glob("test_acanthostega_*.py"))
    for n in ("test_acanthostega_local_signal.py", "test_acanthostega_column_transfer.py",
              "test_acanthostega_procedural_surface_columns.py"):
        assert n in names
    gates = RESULTS / "gates.json"
    if not gates.exists():
        pytest.skip("gates.json is written by the regression run")
    g = json.loads(gates.read_text())
    assert g["regression"]["new_failures"] == []
    assert set(g["regression"]["failures"]) <= set(g["regression"]["documented_pre_existing"])
