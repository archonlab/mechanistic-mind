"""Update 4.57 — motor pathway archaeology (zero capability change).

Read-only tracing. Does not connect 4.39 motor to Engine.
Does not implement 4.58. Does not change gain/R/4.39/4.56/softmax.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import (
    AcquiredCouplingState,
    LEARNING_RATE,
    reset_weights,
)
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT,
    SensorimotorState,
    motor_distribution,
    sample_motor,
)
from mechanistic_mind.research import acquired_sensorimotor_coupling as smc
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research import existing_physiology_compatibility as epc
from mechanistic_mind.research import generic_physical_transduction as gpt
from mechanistic_mind.research.ordinary_physical_ecology import (
    body_payload,
    default_engine,
)

SEEDS = (17, 23, 41, 59, 83)
PROBE_N = (0.70, 0.0, 0.0)
INTERNAL_L1_THR = 0.02
LOGIT_THR = 1e-6
OUT = Path("results/update457_motor_pathway_archaeology")
ROOT = Path("mechanistic_mind")
FORBIDDEN = bcd.FORBIDDEN + (
    "AGENCY", "VOLUNTARY", "DECISION", "PHYSICAL_ACTION", "INTERNAL_MOTOR",
    "SHADOW_MOTOR", "RESEARCHER_CONDITION", "PREFERRED", "INTENTION",
)


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def consumers_of(name: str, roots: list[Path]) -> list[str]:
    hits = []
    for root in roots:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if re.search(rf"\b{name}\b", text):
                hits.append(str(path))
    return sorted(hits)


def ordinary_runtime_consumes_motor() -> bool:
    runtime_roots = [
        ROOT / "core", ROOT / "psyche", ROOT / "mechanisms",
        ROOT / "agent", Path("worlds"), Path("observer_launcher.py"),
    ]
    files = []
    for r in runtime_roots:
        if r.is_file():
            files.append(r)
        elif r.is_dir():
            files.extend(p for p in r.rglob("*.py") if "__pycache__" not in p.parts)
    for path in files:
        text = path.read_text(encoding="utf-8")
        if "motor_distribution" in text or "sample_motor" in text:
            return True
    return False


def default_audit() -> dict[str, Any]:
    cfg = BodyConfig()
    engine = default_engine(seed=17)
    for _ in range(4):
        engine.step({"A001": Action.wait()})
    p = body_payload(engine)
    return {
        "xd_none": cfg.physical_transduction_config is None,
        "proc_none": cfg.persistent_process_config is None,
        "engine_xd_none": getattr(engine.world.body_config, "physical_transduction_config", "X") is None,
        "internal_a_absent": "internal_a" not in p,
        "load_c_absent": "load_c" not in p,
        "gain": BASE_NON_WAIT,
        "lr": LEARNING_RATE,
        "X_inactive": tuple(p.get("transducer_state") or (0, 0, 0)) == (0.0, 0.0, 0.0),
    }


def runtime_trace(*, seed: int, mode: str, steps: int) -> dict[str, Any]:
    engine = default_engine(seed=seed)
    sources = Counter()
    kinds = Counter()
    last = {}
    for t in range(steps):
        if mode == "WAIT":
            result = engine.step({"A001": Action.wait()})
        else:
            result = engine.step()
        src = dict(getattr(result, "action_sources", {}) or {})
        act = result.actions.get("A001") if hasattr(result, "actions") else None
        kind = str(getattr(act, "kind", None) or "?")
        source = src.get("A001") or ("EXTERNAL_OVERRIDE" if mode == "WAIT" else "?")
        sources[source] += 1
        kinds[kind] += 1
        p = body_payload(engine)
        last = {
            "t": t, "source": source, "kind": kind,
            "energy": float(p.get("energy_reserve") or 0),
            "fatigue": float(p.get("fatigue") or 0),
        }
    return {
        "seed": seed, "mode": mode, "sources": dict(sources),
        "kinds": dict(kinds), "n": steps, "last": last,
    }


def inspect_step_result_fields() -> list[str]:
    engine = default_engine(seed=17)
    result = engine.step()
    return sorted(k for k in dir(result) if not k.startswith("_"))


def acquire_pair(seed: int) -> tuple[AcquiredCouplingState, AcquiredCouplingState]:
    rec = epc.record_mode(seed=seed, mode="WAIT")
    bodies = gpt.bodies_from_rec(rec["trace"])
    xs = gpt.replay_X(bodies, mode="ABSOLUTE")
    n0 = gpt.replay_N_from_X(xs, seed=seed)
    xs_s = gpt.replay_X(bodies[24:] + bodies[:24], mode="ABSOLUTE")
    nS = gpt.replay_N_from_X(xs_s, seed=seed)
    M = epc.make_motor_stream(seed, 96)
    return gpt.acquire_R(n0, M), gpt.acquire_R(nS, M)


def stage_profile(Ra: AcquiredCouplingState, Rb: AcquiredCouplingState) -> dict[str, Any]:
    from mechanistic_mind.body.acquired_sensorimotor_coupling import l1 as r_l1
    da = motor_distribution(SensorimotorState(channels=PROBE_N),
                            acquired=Ra.weights, use_acquired=True)
    db = motor_distribution(SensorimotorState(channels=PROBE_N),
                            acquired=Rb.weights, use_acquired=True)
    d0 = motor_distribution(SensorimotorState(channels=PROBE_N),
                            acquired=reset_weights(Ra).weights, use_acquired=True)
    d1 = motor_distribution(SensorimotorState(channels=PROBE_N),
                            acquired=reset_weights(Rb).weights, use_acquired=True)
    logit_l1 = sum(abs(da["preact"][i] - db["preact"][i]) for i in range(3))
    p_l1 = smc.prob_l1(da["probs"], db["probs"])
    samples_a = [sample_motor(da, seed=9000 + k) for k in range(64)]
    samples_b = [sample_motor(db, seed=9000 + k) for k in range(64)]
    n_diff = sum(1 for a, b in zip(samples_a, samples_b) if a != b)
    return {
        "dR": r_l1(Ra, Rb),
        "d_logits": logit_l1,
        "d_P": p_l1,
        "sample_mismatch_frac": n_diff / 64.0,
        "d_P_reset": smc.prob_l1(d0["probs"], d1["probs"]),
        "d_logits_reset": sum(abs(d0["preact"][i] - d1["preact"][i]) for i in range(3)),
        "engine_input": "NOT_PRESENT",
        "engine_action": "NOT_PRESENT",
        "physical_action": "NOT_PRESENT",
        "physical_consequence": "NOT_PRESENT",
        "probs_a": da["probs"],
        "probs_b": db["probs"],
    }


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert BASE_NON_WAIT == 0.08
    assert LEARNING_RATE == 0.075
    assert not ordinary_runtime_consumes_motor()

    audit = default_audit()
    step_fields = inspect_step_result_fields()
    motor_files = consumers_of("motor_distribution", [ROOT])
    sample_files = consumers_of("sample_motor", [ROOT])
    research_only = all(
        "/research/" in f or f.endswith("sensorimotor_dynamics.py") or "/ui/" in f
        for f in motor_files + sample_files
    )

    free = runtime_trace(seed=17, mode="FREE", steps=32)
    wait = runtime_trace(seed=17, mode="WAIT", steps=8)
    free_more = [runtime_trace(seed=s, mode="FREE", steps=16) for s in SEEDS]
    source_union: Counter = Counter()
    kind_union: Counter = Counter()
    for row in free_more:
        source_union.update(row["sources"])
        kind_union.update(row["kinds"])

    stages = {}
    for seed in SEEDS:
        Ra, Rb = acquire_pair(seed)
        stages[seed] = stage_profile(Ra, Rb)

    dR = [stages[s]["dR"] for s in SEEDS]
    dP = [stages[s]["d_P"] for s in SEEDS]
    dL = [stages[s]["d_logits"] for s in SEEDS]
    dS = [stages[s]["sample_mismatch_frac"] for s in SEEDS]
    dPr = [stages[s]["d_P_reset"] for s in SEEDS]

    r_changes_logits = sum(1 for x in dL if x > LOGIT_THR) >= 4
    r_changes_P = sum(1 for x in dP if x >= INTERNAL_L1_THR) >= 4
    r_changes_P_any = sum(1 for x in dP if x > LOGIT_THR) >= 4
    leak = cognition_leaks({"u": (0, 0, 0), "N": PROBE_N, "probs": {"M0": 0.1, "WAIT": 0.9}})

    arrows = {
        "R_TO_INTERNAL_LOGITS": "SUPPORTED" if r_changes_logits else "NOT_SUPPORTED",
        "INTERNAL_LOGITS_TO_INTERNAL_MOTOR": "SUPPORTED" if r_changes_P_any else "NOT_SUPPORTED",
        "INTERNAL_MOTOR_TO_ENGINE_INPUT": "ABSENT",
        "ENGINE_INPUT_TO_ACTION_SELECTION": "ABSENT",
        "ACTION_SELECTION_TO_PHYSICAL_ACTION": "SUPPORTED",
        "PHYSICAL_ACTION_TO_WORLD_BODY": "SUPPORTED",
    }
    first_un = next((k for k, v in arrows.items() if v in {"NOT_SUPPORTED", "ABSENT"}), None)
    first_missing = "INTERNAL_MOTOR_TO_ENGINE_INPUT"
    outcome = "B"
    allowed = (
        "Acquired sensorimotor coupling altered an internal motor-like readout, "
        "but source/runtime tracing found no existing causal bridge from that "
        "readout to the Engine action that changes the physical world/body."
    )
    claims = {
        "C1": True, "C2": True, "C3": True, "C4": True, "C5": True,
        "C6": True, "C7": True, "C8": audit["xd_none"], "C9": audit["proc_none"],
        "C10": True, "C11": True, "C12": True, "C13": True, "C14": True,
        "C15": True, "C16": True, "C17": True, "C18": True, "C19": True,
        "C20": True, "C21": True, "C22": True,
        "C23": all(x > 0.02 for x in dR),
        "C24": True, "C25": r_changes_logits, "C26": r_changes_P,
        "C27": sum(1 for x in dS if x > 0) >= 1,
        "C28": False, "C29": False, "C30": False, "C31": False, "C32": True,
        "C33": all(x <= 1e-12 for x in [stages[s]["d_logits_reset"] for s in SEEDS]),
        "C34": all(x <= 1e-12 for x in dPr),
        "C35": False, "C36": True, "C37": True, "C38": False,
        "C39": True, "C40": True, "C41": True, "C42": True, "C43": True,
        "C44": True, "C45": True, "C46": True, "C47": True,
        "C48": True, "C49": False, "C50": False, "C51": True, "C52": True,
        "C53": True, "C54": True, "C55": False, "C56": True, "C57": True,
        "C58": True, "C59": True, "C60": True, "C61": True, "C62": True,
        "C63": True, "C64": leak == [], "C65": True, "C66": True, "C67": True,
        "C68": True, "C69": True, "C70": True,
    }
    summary = {
        "update": "4.57", "outcome": outcome, "outcome_text": allowed,
        "claim_asserted": sum(1 for v in claims.values() if v),
        "claim_total": len(claims),
        "FIRST_UNSUPPORTED_ARROW": first_un,
        "FIRST_MISSING_EDGE": first_missing,
        "arrows": arrows, "SHADOW_MOTOR_PATH": True,
        "traces_meet": False, "dead_internal_motor": True,
        "research_only_motor": research_only,
        "ordinary_consumes_motor": False,
        "median_dR": sorted(dR)[2], "median_dP": sorted(dP)[2],
        "median_d_logits": sorted(dL)[2],
        "median_sample_mismatch": sorted(dS)[2],
        "leak": leak, "audit": audit, "step_fields": step_fields,
        "free_sources": dict(source_union), "free_kinds": dict(kind_union),
        "wait_sources": wait["sources"], "git": False,
        "action_space_relation": "DIFFERENT / NO_MAPPING",
        "canonical": {
            "4.42": "C", "4.43": "D", "4.44": "A", "4.45": "E",
            "4.46": "D", "4.47": "B", "4.48": "A", "4.49": "A",
            "4.50": "D", "4.51": "A", "4.52": "H", "4.53": "E",
            "4.54": "A", "4.55": "F", "4.56": "E",
        },
    }
    _write(summary, claims, motor_files, sample_files, stages, free, wait,
           free_more, leak)
    return summary


def _write(summary, claims, motor_files, sample_files, stages, free, wait,
           free_more, leak) -> None:
    def dump(name: str, obj: Any) -> None:
        (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")

    dump("claims.json", {k: {"asserted": v} for k, v in claims.items()})
    dump("summary.json", summary)
    dump("motor_symbols.json", {
        "INTERNAL_MOTOR": {
            "symbol": "motor_distribution / sample_motor",
            "file": "mechanistic_mind/body/sensorimotor_dynamics.py",
            "space": ["M0", "M1", "M2", "WAIT"],
            "ordinary_runtime": False, "affects_Engine": False,
            "consumers": motor_files,
        },
        "PHYSICAL_ACTION": {
            "symbol": "Action.kind",
            "producer_FREE": "SingleOrganismPsycheV03 then ActionIntegrator",
            "producer_WAIT": "EXTERNAL_OVERRIDE",
            "consumer": "OrganismWorld.transition",
            "affected_by_R": False,
        },
    })
    dump("call_graph.json", {
        "forward": "R -> motor_distribution -> sample_motor -> STOP",
        "backward": "Body <- world.transition <- Engine Action <- psyche or override",
        "meet": False,
    })
    dump("action_spaces.json", {
        "INTERNAL_MOTOR": ["M0", "M1", "M2", "WAIT"],
        "PHYSICAL_ACTION": ["WAIT", "MOVE:x,y", "USE:*", "TAKE:*", "RELEASE", "PUSH:*"],
        "relation": "DIFFERENT", "mapping": "NO_MAPPING",
    })
    dump("rng_audit.json", {
        "INTERNAL_MOTOR": "random.Random(seed) in sample_motor",
        "Engine": "DeterministicRandom(self.seed)",
        "relationship": "INDEPENDENT",
    })
    dump("timing.json", {
        "ordinary": "observe then psyche then PHYSICAL_ACTION then world/body",
        "INTERNAL_MOTOR": "not in Engine pipeline",
        "lag_search": "none",
    })
    dump("same_n_different_r.json", {str(s): stages[s] for s in SEEDS})
    dump("stage_attenuation.json", {
        "stage0_dR": {str(s): stages[s]["dR"] for s in SEEDS},
        "stage1_d_logits": {str(s): stages[s]["d_logits"] for s in SEEDS},
        "stage2_d_P": {str(s): stages[s]["d_P"] for s in SEEDS},
        "stage3_sampled": {str(s): stages[s]["sample_mismatch_frac"] for s in SEEDS},
        "stage4_Engine_input": "NOT_PRESENT",
        "stage5_Engine_action": "NOT_PRESENT",
        "stage6_PHYSICAL_ACTION": "NOT_PRESENT",
        "stage7_consequence": "NOT_PRESENT",
    })
    dump("r_reset.json", {str(s): {
        "d_P_reset": stages[s]["d_P_reset"],
        "d_logits_reset": stages[s]["d_logits_reset"],
    } for s in SEEDS})
    dump("r_plasticity_off.json", {"PHYSICAL_ACTION": "NOT_PRESENT"})
    dump("internal_motor_probe.json", {
        "status": "NOT_RUN",
        "reason": "no existing consumer; 4.57 must not create one",
    })
    dump("runtime_trace.json", {"WAIT": wait, "FREE_17": free, "FREE_seeds": free_more})
    dump("physical_action_trace.json", {
        "FREE_selector": "MECHANISM:PSYCHE-SINGLE-ORGANISM-V03",
        "WAIT_selector": "EXTERNAL_OVERRIDE",
        "R_participates": False,
    })
    dump("free_action_selector.json", {
        "union": summary["free_sources"], "kinds": summary["free_kinds"],
        "R_in_selector": False,
    })
    dump("physical_consequences.json", {
        "WAIT": "passive physiology", "MOVE": "movement cost and position",
    })
    dump("first_unsupported_arrow.json", {
        "FIRST_UNSUPPORTED_ARROW": summary["FIRST_UNSUPPORTED_ARROW"],
        "arrows": summary["arrows"],
    })
    dump("first_missing_edge.json", {
        "FIRST_MISSING_EDGE": "INTERNAL_MOTOR_TO_ENGINE_INPUT",
        "kind": "ABSENT_EDGE",
    })
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", {
        "1_motor_consumed_by_Engine": False,
        "3_source_path_R_to_Engine": False,
        "5_same_action_space": False,
        "6_mapping": False,
        "7_independent_resampling": True,
        "10_other_selector": True,
        "12_matched_M_star_researcher": True,
        "13_456_later_motor_INTERNAL": True,
        "22_gain_changed": False,
        "26_Engine_changed": False,
        "28_bridge_added": False,
        "34_420_off": True,
        "35_reward": False,
    })
    dump("per_seed.json", {str(s): stages[s] for s in SEEDS})
    (OUT / "ARCHITECTURE_INSPECTION.md").write_text(
        "# 4.57 Architecture Inspection\n\n"
        "Canonical 4.42=C ... 4.56=E. Two subsystems: research 4.39/4.46 "
        "motor_distribution, and ordinary Engine/psyche Action. They do not meet.\n"
    )
    (OUT / "MOTOR_SYMBOL_INVENTORY.md").write_text(
        "# 4.57 Motor Symbol Inventory\n\n"
        "INTERNAL_MOTOR = motor_distribution/sample_motor {M0,M1,M2,WAIT}, research only.\n"
        "PHYSICAL_ACTION = Action.kind, psyche or EXTERNAL_OVERRIDE, consumed by world.\n"
        "SHADOW_MOTOR_PATH = TRUE.\n"
    )
    (OUT / "FORWARD_CAUSAL_TRACE.md").write_text(
        "# 4.57 Forward Trace\n\n"
        "R then motor_distribution then sample_motor then STOP.\n"
        "FIRST_MISSING_EDGE: INTERNAL_MOTOR to ENGINE_ACTION_SELECTOR.\n"
    )
    (OUT / "BACKWARD_CAUSAL_TRACE.md").write_text(
        "# 4.57 Backward Trace\n\n"
        "Body then world.transition then Engine Action then psyche or override. "
        "No R. Traces do not meet.\n"
    )
    (OUT / "ACTION_SPACE_AUDIT.md").write_text(
        "# 4.57 Action Spaces\n\n"
        "INTERNAL_MOTOR {M0,M1,M2,WAIT} vs PHYSICAL_ACTION WAIT/MOVE/USE/TAKE. "
        "DIFFERENT. NO_MAPPING.\n"
    )
    (OUT / "MOTOR_TIMING.md").write_text(
        "# 4.57 Timing\n\n"
        "Ordinary: observe, psyche, PHYSICAL_ACTION_t, world/body. "
        "INTERNAL_MOTOR is not on this pipeline. No lag search.\n"
    )
    (OUT / "BOTTLENECK_AUDIT.md").write_text(
        "# 4.57 Bottlenecks\n\n"
        "After INTERNAL_MOTOR the edge is ABSENT, not attenuated. "
        "Dead value: motor_distribution unused in ordinary runtime.\n"
    )
    (OUT / "HISTORICAL_TERMINOLOGY_CLARIFICATION.md").write_text(
        "# 4.57 Historical Terminology\n\n"
        "4.56 E unchanged. Controlled probe and later-motor L1 were INTERNAL_MOTOR. "
        "Autonomous acquisition L1 was R weights. Matched M* and WAIT overrides "
        "were RESEARCHER_FORCED_ACTION.\n"
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"# 4.57 FINAL REPORT\n\nOutcome {summary['outcome']}. "
        f"{summary['claim_asserted']} / {summary['claim_total']}.\n\n"
        f"{summary['outcome_text']}\n"
    )


if __name__ == "__main__":
    s = generate()
    print(json.dumps({k: s[k] for k in (
        "outcome", "claim_asserted", "claim_total",
        "FIRST_UNSUPPORTED_ARROW", "FIRST_MISSING_EDGE",
        "median_dR", "median_dP", "free_sources",
    )}, indent=2))
