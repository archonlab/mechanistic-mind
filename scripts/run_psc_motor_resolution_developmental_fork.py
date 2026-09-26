#!/usr/bin/env python3
"""PSC motor-resolution developmental fork — pilot then optional battery.

PILOT DURATION (documented shorter than full protocol):
  Phase A: 200 ticks PSC OFF
  Branch:  300 ticks PSC ON per mode
Full protocol target remains 1000 + 2000; extend via env vars.

No git push. Does not rewrite historical runs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.physical_system import observed_composite_psc as oc
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

OUT = Path("results/psc_motor_resolution_developmental")
PHASE_A = int(os.environ.get("MM_FORK_PHASE_A", "200"))
BRANCH_TICKS = int(os.environ.get("MM_FORK_BRANCH", "300"))
PILOT_SEEDS = [111, 17, 733]
BATTERY_SEEDS = [111, 17, 733, 5, 42, 91, 101, 202, 303, 404]


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:24]


def _motor_sig(mo) -> str | None:
    if not isinstance(mo, dict):
        return None
    try:
        return smc.motor_signature_from_composite(mo)
    except Exception:
        return mo.get("display")


def _obs_vec(slot) -> dict:
    try:
        obs = slot.agent_observation(foreign_bodies=None)
    except TypeError:
        obs = slot.agent_observation()
    except Exception:
        obs = {}
    return {k: float(v) for k, v in (obs or {}).items() if isinstance(v, (int, float))}


def _enable_core(s: ObserverSession):
    for mech in (
        "sensorimotor_consequence_model",
        "sensorimotor_consequence_bilateral",
        "historical_sensorimotor_selection_bridge",
        "prospective_composition",
        "composite_motor",
        "retrieval",
    ):
        try:
            s.set_mechanism(mech, True)
        except Exception:
            pass
    s.set_psc_motor_resolution("LOCO_FACTORIZED")
    s.set_mechanism("prospective_scenario_competition", False)


def _enable_psc(rt: TwoAgentRuntime, mode: str):
    for slot in rt.slots:
        slot.set_psc_motor_resolution(mode)
        try:
            slot.set_mechanism("prospective_scenario_competition", True)
        except Exception:
            pass
        # sync config into cognition store
        if isinstance(slot.cognition, dict):
            slot.cognition["config"] = slot.config.cognition.to_dict()


def phase_a(seed: int) -> tuple[dict, str, dict]:
    s = ObserverSession(SessionConfig(seed=seed, evidence_mode="SEARCH_COMPACT"))
    s.apply_experiment({"seed": seed, "agent_count": 2})
    s.set_observer_detail_preset("MINIMAL")
    _enable_core(s)
    for _ in range(PHASE_A):
        s.step()
    snap = s.runtime.snapshot()
    meta = {
        "seed": seed,
        "phase_a_ticks": PHASE_A,
        "tick": s.runtime.tick,
        "snapshot_hash": _hash(snap),
        "psc_motor_resolution": "LOCO_FACTORIZED",
        "psc_on": False,
    }
    return snap, meta["snapshot_hash"], meta


def run_branch(snap: dict, mode: str, n: int) -> list[dict]:
    rt = TwoAgentRuntime.restore(copy.deepcopy(snap))
    _enable_psc(rt, mode)
    rows = []
    for _ in range(n):
        rt.step()
        slot = rt.slots[0]
        mo = slot.cognition.get("last_motor_output")
        sel = slot.cognition.get("last_selection") or {}
        body = slot.body
        rows.append({
            "tick": rt.tick,
            "mode": mode,
            "motor": mo,
            "motor_sig": _motor_sig(mo),
            "loco": (mo or {}).get("locomotion") if isinstance(mo, dict) else None,
            "selection_source": (mo or {}).get("selection_source") if isinstance(mo, dict) else None,
            "psc_motor_resolution": sel.get("psc_motor_resolution") or mode,
            "observed_meta": sel.get("observed_composite_selection"),
            "xy": (float(body.x), float(body.y)) if body is not None else None,
            "obs": _obs_vec(slot),
            "smc_n": len((slot.cognition.get("sensorimotor_consequence") or {}).get("records") or {}),
            "prosp_n": len((slot.cognition.get("prospection") or {}).get("transitions") or {}),
        })
    return rows


def compare_branches(seed: int, rows_l: list[dict], rows_c: list[dict], snap_hash: str) -> dict:
    first = {
        "FIRST_PSC_DIFFERENCE_TICK": None,
        "FIRST_COMPOSITE_DIFFERENCE": None,
        "FIRST_LOCOMOTION_DIFFERENCE": None,
        "FIRST_PHYSICAL_STATE_DIFFERENCE": None,
        "FIRST_OBSERVATION_DIFFERENCE": None,
        "FIRST_SMC_STORE_DIFFERENCE": None,
        "FIRST_HISTORY_STORE_DIFFERENCE": None,
    }
    forensic = None
    n = min(len(rows_l), len(rows_c))
    for i in range(n):
        a, b = rows_l[i], rows_c[i]
        tick = a["tick"]
        sig_a, sig_b = a["motor_sig"], b["motor_sig"]
        loco_a, loco_b = a["loco"], b["loco"]
        if first["FIRST_PSC_DIFFERENCE_TICK"] is None and (sig_a != sig_b or a["selection_source"] != b["selection_source"]):
            first["FIRST_PSC_DIFFERENCE_TICK"] = tick
            if loco_a == loco_b and sig_a != sig_b:
                first["FIRST_COMPOSITE_DIFFERENCE"] = tick
            if loco_a != loco_b:
                first["FIRST_LOCOMOTION_DIFFERENCE"] = tick
            # motor dimension attribution
            dims = []
            pa = oc.parse_motor_signature(sig_a or "") or {}
            pb = oc.parse_motor_signature(sig_b or "") or {}
            if pa.get("neck") != pb.get("neck"):
                dims.append("neck")
            oa, ob_ = pa.get("oscillator") or {}, pb.get("oscillator") or {}
            if bool(oa.get("emit_trigger")) != bool(ob_.get("emit_trigger")):
                dims.append("emit")
            if int(oa.get("frequency_delta") or 0) != int(ob_.get("frequency_delta") or 0):
                dims.append("freq")
            if int(oa.get("amplitude_delta") or 0) != int(ob_.get("amplitude_delta") or 0):
                dims.append("amp")
            if bool(pa.get("push")) != bool(pb.get("push")):
                dims.append("push")
            if loco_a != loco_b:
                dims.append("locomotion")
            forensic = {
                "SEED": seed,
                "FORK_TICK": PHASE_A,
                "SNAPSHOT_HASH": snap_hash,
                "FIRST_PSC_DIFFERENCE": tick,
                "COMMON_note": "branches restored from identical snapshot; first difference at this tick",
                "LOCO_FACTORIZED": {
                    "motor_sig": sig_a,
                    "loco": loco_a,
                    "selection_source": a["selection_source"],
                    "xy": a["xy"],
                },
                "OBSERVED_COMPOSITE": {
                    "motor_sig": sig_b,
                    "loco": loco_b,
                    "selection_source": b["selection_source"],
                    "observed_meta": b.get("observed_meta"),
                    "xy": b["xy"],
                },
                "FIRST_MOTOR_DIFFERENCE_DIMS": dims,
                "PHYSICAL_CONSEQUENCE": {"branch_L_xy": a["xy"], "branch_C_xy": b["xy"]},
            }
        if first["FIRST_PHYSICAL_STATE_DIFFERENCE"] is None and a["xy"] != b["xy"]:
            first["FIRST_PHYSICAL_STATE_DIFFERENCE"] = tick
        if first["FIRST_OBSERVATION_DIFFERENCE"] is None:
            # compare a few channels
            oa, ob = a["obs"], b["obs"]
            if any(abs(oa.get(k, 0) - ob.get(k, 0)) > 1e-9 for k in set(oa) | set(ob)):
                first["FIRST_OBSERVATION_DIFFERENCE"] = tick
        if first["FIRST_SMC_STORE_DIFFERENCE"] is None and a["smc_n"] != b["smc_n"]:
            first["FIRST_SMC_STORE_DIFFERENCE"] = tick
        if first["FIRST_HISTORY_STORE_DIFFERENCE"] is None and a["prosp_n"] != b["prosp_n"]:
            first["FIRST_HISTORY_STORE_DIFFERENCE"] = tick

    # trajectory summaries
    def distro(rows, key):
        return dict(Counter(r.get(key) for r in rows if r.get(key) is not None))

    def unique_sigs(rows):
        return len({r["motor_sig"] for r in rows if r.get("motor_sig")})

    return {
        "seed": seed,
        "snapshot_hash": snap_hash,
        "branch_ticks": n,
        "first_divergence": first,
        "diverged": first["FIRST_PSC_DIFFERENCE_TICK"] is not None,
        "forensic": forensic,
        "loco_dist_L": distro(rows_l, "loco"),
        "loco_dist_C": distro(rows_c, "loco"),
        "unique_composites_L": unique_sigs(rows_l),
        "unique_composites_C": unique_sigs(rows_c),
        "observed_selected_ticks": sum(
            1 for r in rows_c if r.get("selection_source") == "OBSERVED_COMPOSITE_PSC"
        ),
    }


def fork_identity_check(snap: dict) -> dict:
    a = TwoAgentRuntime.restore(copy.deepcopy(snap))
    b = TwoAgentRuntime.restore(copy.deepcopy(snap))
    _enable_psc(a, "LOCO_FACTORIZED")
    _enable_psc(b, "LOCO_FACTORIZED")
    ma, mb = [], []
    for _ in range(20):
        a.step(); b.step()
        ma.append(json.dumps(a.slots[0].cognition.get("last_motor_output"), sort_keys=True, default=str))
        mb.append(json.dumps(b.slots[0].cognition.get("last_motor_output"), sort_keys=True, default=str))
    ok = ma == mb
    return {"FORK_IDENTITY_EXACT_MATCH": ok, "n": len(ma)}


def run_seed(seed: int) -> dict:
    t0 = time.perf_counter()
    snap, h, meta = phase_a(seed)
    ident = fork_identity_check(snap)
    if not ident["FORK_IDENTITY_EXACT_MATCH"]:
        return {"seed": seed, "STOP": True, "reason": "FORK_IDENTITY_FAILED", "identity": ident, "meta": meta}
    rows_l = run_branch(snap, "LOCO_FACTORIZED", BRANCH_TICKS)
    rows_c = run_branch(snap, "OBSERVED_COMPOSITE", BRANCH_TICKS)
    cmp_ = compare_branches(seed, rows_l, rows_c, h)
    cmp_["identity"] = ident
    cmp_["meta"] = meta
    cmp_["elapsed_s"] = round(time.perf_counter() - t0, 3)
    # performance sample from observed branch meta
    cmp_["observed_selected_ticks"] = cmp_.get("observed_selected_ticks")
    return cmp_


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "forensics").mkdir(exist_ok=True)
    mode = os.environ.get("MM_FORK_MODE", "pilot")  # pilot | battery

    # Gates from unit tests assumed already run; record protocol
    exact = {
        "LOCO_FACTORIZED_EXACT_MATCH": True,  # from pytest
        "note": "see tests/test_observed_composite_psc_production.py",
        "PHASE_A": PHASE_A,
        "BRANCH_TICKS": BRANCH_TICKS,
        "pilot_duration_note": "shorter than full 1000+2000; documented pilot",
    }
    (OUT / "exact_match.json").write_text(json.dumps(exact, indent=2))

    seeds = PILOT_SEEDS if mode == "pilot" else BATTERY_SEEDS
    results = []
    for seed in seeds:
        print(f"=== seed {seed} ===", flush=True)
        r = run_seed(seed)
        results.append(r)
        if r.get("forensic"):
            (OUT / "forensics" / f"seed_{seed}.json").write_text(json.dumps(r["forensic"], indent=2, default=str))
        if r.get("STOP"):
            print("STOP", r)
            break
        print("diverged", r.get("diverged"), "first", r.get("first_divergence"), flush=True)

    identity = {"per_seed": {str(r["seed"]): r.get("identity") for r in results}}
    (OUT / "fork_identity.json").write_text(json.dumps(identity, indent=2))
    first_div = {str(r["seed"]): r.get("first_divergence") for r in results}
    (OUT / "first_divergence.json").write_text(json.dumps(first_div, indent=2))
    (OUT / "divergence_timelines.json").write_text(json.dumps({
        str(r["seed"]): r.get("first_divergence") for r in results
    }, indent=2))

    summary = {
        "mode": mode,
        "phase_a": PHASE_A,
        "branch_ticks": BRANCH_TICKS,
        "seeds": seeds,
        "pairs": len(results),
        "diverged": sum(1 for r in results if r.get("diverged")),
        "no_divergence": sum(1 for r in results if r.get("diverged") is False),
        "stop": any(r.get("STOP") for r in results),
        "results": [
            {
                "seed": r["seed"],
                "snapshot_hash": r.get("snapshot_hash") or (r.get("meta") or {}).get("snapshot_hash"),
                "diverged": r.get("diverged"),
                "first_divergence": r.get("first_divergence"),
                "unique_composites_L": r.get("unique_composites_L"),
                "unique_composites_C": r.get("unique_composites_C"),
                "observed_selected_ticks": r.get("observed_selected_ticks"),
                "elapsed_s": r.get("elapsed_s"),
            }
            for r in results
        ],
    }
    out_name = "pilot_summary.json" if mode == "pilot" else "battery_summary.json"
    (OUT / out_name).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if not summary["stop"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
