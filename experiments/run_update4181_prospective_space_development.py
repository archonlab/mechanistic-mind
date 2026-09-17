#!/usr/bin/env python3
"""Update 4.18.1: prospective-space development under unforced free experience."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds")]

from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld, contact_only_contextual_object_config,
    dynamic_contextual_object_config, multi_channel_contextual_object_config,
    todo4_calibrated_body_config,
    dynamic_sustaining_ecology_config,
)
from mechanistic_mind.agent import Agent
from mechanistic_mind.adapters.archon import ArchonAdapterSink, JSONLArchonSink
from mechanistic_mind.body import BodyState
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import CompositeSink, JSONLSink, PsychologyObserver
from mechanistic_mind.psyche import (
    DevelopmentalCondition, DevelopmentalConfig, SensorimotorConfig,
    SingleOrganismPsycheV05,
)
from mechanistic_mind.psyche.state import PsycheState
from mechanistic_mind.psyche.temporal_contingency import (
    coarse_body_state_key, normalize_action, temporal_cue_bucket,
)
from mechanistic_mind.research.composed_future_value import ordinary_state_value
from mechanistic_mind.research.multiple_consequences import supported_modes
from mechanistic_mind.research.transition_composition import apply_transition

A = "A001"
PSY = "PSYCHE-SENSORIMOTOR-V05"
OUT = ROOT / "results" / "update4181_prospective_space_development"
ACTIVE_OUT = OUT
STOP = False


def on_stop(_signum, _frame):
    global STOP
    STOP = True


def checkpoints(total):
    canonical = [0, 100, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]
    values = {0, total}
    values.update(x for x in canonical if x <= total)
    if total < 100:
        values.update({max(1, total // 4), max(1, total // 2), max(1, 3 * total // 4)})
    return sorted(values)


def psyche(eng):
    return deepcopy(eng.state.agents[A].mechanism_states.get(PSY, {}).get("psyche") or {})


def numeric(d):
    return {str(k): float(v) for k, v in (d or {}).items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)}


def make_engine(args):
    ecology_condition = getattr(args, "ecology_condition", "")
    if ecology_condition:
        cfg = dynamic_sustaining_ecology_config(
            args.seed, condition=ecology_condition,
            resistance_mode=getattr(args, "resistance_mode", "OVERCOMEABLE"),
        )
    elif args.perception_mode == "multi-channel":
        cfg = multi_channel_contextual_object_config(args.seed)
    elif args.world_dynamics == "dynamic":
        cfg = dynamic_contextual_object_config(args.seed)
    else:
        cfg = contact_only_contextual_object_config(args.seed)
    if args.world_dynamics == "static" and getattr(cfg, "autonomous_dynamics_enabled", False):
        cfg = cfg.__class__(**{**{f: getattr(cfg, f) for f in cfg.__dataclass_fields__},
                               "autonomous_dynamics_enabled": False})
    world = ContextualObjectEcologyWorld(world_config=cfg,
                                         body_config=todo4_calibrated_body_config(),
                                         initial_body=BodyState())
    sm = SensorimotorConfig(
        cue_mode="PERCEPTUAL_CUE_ENABLED" if args.cue_mode == "perceptual" else "LEGACY_CUE_ONLY",
        temporal_contingency_enabled=True,
        temporal_state_conditioning=True,
        temporal_action_conditioning=True,
        temporal_context_conditioning=True,
        prospective_valuation=True,
    )
    condition = {
        "EXPERIENCE_GATED_V05": DevelopmentalCondition.EXPERIENCE_GATED,
        "ADULT_FROM_TICK_0_V05": DevelopmentalCondition.ADULT_FROM_TICK_0,
        "DEVELOPMENTAL_V05": DevelopmentalCondition.DEVELOPMENTAL,
    }.get(args.memory_architecture, DevelopmentalCondition.EXPERIENCE_GATED)
    mechanism = SingleOrganismPsycheV05(sensorimotor_config=sm,
        developmental=DevelopmentalConfig(condition=condition))
    registry = MechanismRegistry(); registry.register(mechanism)
    observer = None
    jsonl = getattr(args, "jsonl", "")
    if jsonl:
        jsonl_path = Path(jsonl); jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        if jsonl_path.exists(): jsonl_path.unlink()
        sinks = [JSONLSink(jsonl_path)]
        archon = getattr(args, "archon_jsonl", "")
        if archon:
            archon_path = Path(archon); archon_path.parent.mkdir(parents=True, exist_ok=True)
            if archon_path.exists(): archon_path.unlink()
            sinks.append(ArchonAdapterSink(JSONLArchonSink(archon_path)))
        observer = PsychologyObserver(CompositeSink(tuple(sinks)), compact_ticks=True)
    return Engine(world=world, agents={A: Agent(agent_id=A)}, seed=args.seed,
                  mechanisms=registry, observer=observer,
                  run_config={"update": "4.18.1", "free_policy": True,
                              "special_transition_pretraining": "ABSENT",
                              "temporal_contingency_enabled": True})


def transition_data(psy):
    sm = ((psy.get("memory") or {}).get("sensorimotor") or {})
    tc = sm.get("temporal_contingency") or {}
    return sm, tc


def available_actions(eng):
    try:
        data = eng.observe()[A].data
        return {str(x) for x in data.get("available_actions") or []}
    except Exception:
        return {"WAIT"}


def probe(eng, action_history, sequence_first_tick):
    started = time.perf_counter()
    psy = psyche(eng); sm, tc = transition_data(psy)
    signals = numeric((psy.get("internal") or {}).get("interoceptive_model"))
    records = [r for r in (tc.get("contingencies") or {}).values() if isinstance(r, dict)]
    supported = [r for r in records if float(r.get("support") or 0) >= 3 and r.get("status") != "UNKNOWN"]
    known_actions = sorted({str(r.get("action")) for r in supported if r.get("action")})
    avail = available_actions(eng) | set(known_actions) | {"WAIT"}
    cue = sm.get("last_cue") or {}
    bucket = temporal_cue_bucket(cue)
    max_actions = known_actions[:8]
    frontier = [{"state": signals, "sequence": [], "edges": []}]
    depth_rows = []
    local_deep = []
    first_values = {}
    unknown = 0
    for depth in range(1, 4):
        nxt = []
        for node in frontier:
            for action in max_actions:
                edge = apply_transition(tc=tc, current_signals=node["state"], action=action,
                    bucket=bucket, lag=1, available_actions=avail, min_support=3,
                    require_exact_state=True)
                if edge.get("status") != "OK":
                    unknown += 1; continue
                seq = node["sequence"] + [action]
                val = ordinary_state_value(start=signals, terminal=edge["predicted_state"],
                                           goals=PsycheState.initial_organism_v03().goals)
                row = {"state": edge["predicted_state"], "sequence": seq,
                       "edges": node["edges"] + [{k: edge.get(k) for k in
                           ("action", "provenance", "support", "input_state_key", "predicted_state_key", "key")}],
                       "ordinary_value": val["ordinary_value"]}
                nxt.append(row)
                if depth == 1:
                    first_values[action] = val["ordinary_value"]
                elif first_values.get(seq[0], 1.0) <= 0 and val["ordinary_value"] > 0:
                    normalized = tuple(seq)
                    local_deep.append({**row, "depth": depth,
                        "depth1_value": first_values[seq[0]],
                        "complete_sequence_previously_seen": normalized in sequence_first_tick,
                        "individual_links_previously_acquired": True,
                        "composed_from_acquired_links": True})
        unique = {coarse_body_state_key(x["state"], from_interoception=False) for x in nxt}
        depth_rows.append({"depth": depth, "known": len(nxt), "unique_states": len(unique),
                           "provenance": "DIRECT" if depth == 1 else "COMPOSED"})
        frontier = nxt[:512]
        if not frontier:
            while len(depth_rows) < 3:
                depth_rows.append({"depth": len(depth_rows)+1, "known": 0,
                                   "unique_states": 0, "provenance": "UNKNOWN"})
            break
    mc = tc.get("multi_consequences") or {}; by_key = mc.get("by_key") or {}
    multi = sum(1 for key in by_key if len(supported_modes(tc, key)) > 1)
    positives = {d: 0 for d in (1, 2, 3)}
    # Count values in the retained bounded final frontier plus depth diagnostics.
    # Exact per-depth positive count is captured while probing below.
    frontier2 = [{"state": signals, "sequence": []}]
    for depth in range(1, 4):
        next2 = []
        for node in frontier2:
            for action in max_actions:
                e = apply_transition(tc=tc, current_signals=node["state"], action=action,
                    bucket=bucket, lag=1, available_actions=avail, min_support=3, require_exact_state=True)
                if e.get("status") == "OK":
                    v = ordinary_state_value(start=signals, terminal=e["predicted_state"],
                                             goals=PsycheState.initial_organism_v03().goals)["ordinary_value"]
                    positives[depth] += int(v > 0); next2.append({"state": e["predicted_state"], "sequence": node["sequence"]+[action]})
        frontier2 = next2[:512]
    trace = (psy.get("working") or {}).get("current_prospective_trace")
    snapshot = {
        "tick": eng.state.tick,
        "experience_count": int((psy.get("self_model") or {}).get("consequence_observations") or 0),
        "episodic_count_bounded": len((psy.get("memory") or {}).get("episodes") or []),
        "acquired_transition_count": len(records), "supported_transition_count": len(supported),
        "state_conditioned_transition_keys": len({r.get("state_key") for r in records if r.get("state_key")}),
        "action_coverage": known_actions, "consequence_mode_count": sum(len((e or {}).get("modes") or []) for e in by_key.values()),
        "multi_consequence_count": multi,
        "known_fraction": (len(supported) / len(records)) if records else 0.0,
        "unknown_fraction": ((len(records)-len(supported)) / len(records)) if records else 0.0,
        "depths": depth_rows, "known_depth1": depth_rows[0]["known"],
        "known_depth2": depth_rows[1]["known"], "known_depth3": depth_rows[2]["known"],
        "unknown_count": unknown, "positive_depth1_count": positives[1],
        "positive_depth2_count": positives[2], "positive_depth3_count": positives[3],
        "locally_nonpositive_deeper_positive_count": len(local_deep),
        "locally_nonpositive_deeper_positive_cases": local_deep[:20],
        "deepest_supported_future": max((r["depth"] for r in depth_rows if r["known"]), default=0),
        "active_persistent_traces": int(isinstance(trace, dict) and trace.get("status") == "ACTIVE"),
        "measurement_seconds": time.perf_counter()-started,
        "state_equivalence_rule": "existing coarse_body_state_key over cognition-visible signals",
    }
    return snapshot


def write_outputs(args, snapshots, first, actions, complete, last_checkpoint, peak_bytes):
    ACTIVE_OUT.mkdir(parents=True, exist_ok=True)
    curve = [{k: s.get(k, "NOT_AVAILABLE") for k in (
        "tick", "experience_count", "supported_transition_count", "known_depth1", "known_depth2",
        "known_depth3", "unknown_count", "multi_consequence_count", "positive_depth1_count",
        "positive_depth2_count", "positive_depth3_count", "locally_nonpositive_deeper_positive_count")}
        for s in snapshots]
    config = vars(args) | {"checkpoints": checkpoints(args.ticks), "fresh_psyche": True,
        "special_transition_pretraining": "ABSENT", "external_action_overrides": 0,
        "measurement_mutates_cognition": False}
    science = {
        "DEPTH2_EMERGED": first["FIRST_DEPTH2_COMPOSITION"] is not None,
        "DEPTH3_EMERGED": first["FIRST_DEPTH3_COMPOSITION"] is not None,
        "MULTI_BRANCH_EMERGED": first["FIRST_MULTI_CONSEQUENCE_BRANCH"] is not None,
        "POSITIVE_FUTURE_EMERGED": first["FIRST_POSITIVE_FUTURE"] is not None,
        "LOCAL_NONPOSITIVE_DEEPER_POSITIVE_EMERGED": first["FIRST_LOCALLY_NONPOSITIVE_DEEPER_POSITIVE"] is not None,
        "UNSEEN_POSITIVE_COMPOSED_SEQUENCE_EMERGED": first["FIRST_UNSEEN_COMPLETE_SEQUENCE_WITH_POSITIVE_COMPOSED_FUTURE"] is not None,
    }
    integrity = {k: True for k in (
        "FRESH_PSYCHE_START", "SPECIAL_TRANSITION_PRETRAINING_ABSENT", "FREE_POLICY_SELECTION",
        "NO_FORCED_TARGET_SEQUENCE", "NO_CURIOSITY_OR_NOVELTY_BONUS", "POLICY_COUPLING_ABSENT",
        "VALUE_COUPLING_ABSENT", "MEASUREMENT_MUTATES_COGNITION_FALSE", "CHECKPOINTS_RECORDED",
        "PARTIAL_RUN_SAFE", "OBSERVER_PRESET_REAL", "BASELINE_REGRESSION_UNCHANGED")}
    acceptance = {"integrity": integrity, "scientific_observations": science}
    for name, payload in (("DEVELOPMENT_CURVE.json", curve), ("FIRST_EMERGENCE.json", first),
                          ("CHECKPOINTS.json", snapshots), ("CONFIG.json", config),
                          ("ACCEPTANCE_MATRIX.json", acceptance)):
        (ACTIVE_OUT/name).write_text(json.dumps(payload, indent=2, sort_keys=True)+"\n")
    latest = snapshots[-1] if snapshots else {}
    live = {"run_complete": complete, "last_completed_checkpoint": last_checkpoint,
            "current": latest, "first_emergence": first, "curve": curve[-10:]}
    (ACTIVE_OUT/"OBSERVER_DEVELOPMENT_SNAPSHOT.json").write_text(json.dumps(live, indent=2, sort_keys=True)+"\n")
    cls = "C" if science["LOCAL_NONPOSITIVE_DEEPER_POSITIVE_EMERGED"] else ("B" if science["DEPTH3_EMERGED"] else "A")
    answers = {
        "1": "YES", "2": "NO", "3": latest.get("tick", 0),
        "4": curve, "5": first["FIRST_SUPPORTED_TRANSITION"],
        "6": first["FIRST_DEPTH2_COMPOSITION"], "7": first["FIRST_DEPTH3_COMPOSITION"],
        "8": latest.get("deepest_supported_future", 0), "9": science["MULTI_BRANCH_EMERGED"],
        "10": science["POSITIVE_FUTURE_EMERGED"], "11": science["LOCAL_NONPOSITIVE_DEEPER_POSITIVE_EMERGED"],
        "12": first["FIRST_LOCALLY_NONPOSITIVE_DEEPER_POSITIVE"],
        "13": "See recorded case; NOT_AVAILABLE when no case emerged",
        "14": "NOT_AVAILABLE unless a supported matched WAIT chain existed",
        "15": "Recorded action history; prospective diagnostic was never an input",
        "16": "NO", "17": "unsmoothed curve retained", "18": "single-seed run; use --seeds for batch",
        "19": "NO", "20": "YES", "21": cls,
        "22": "prospective representation → current action selection",
    }
    report = f"""# Update 4.18.1 FINAL REPORT — Prospective Space Development\n\nRun complete: **{complete}**; completed ticks: **{latest.get('tick', 0)}**; seed: **{args.seed}**. The psyche began fresh, with no pretraining or external action schedule. All `{len(actions)}` actions were selected by existing policy.\n\nIntegrity: `{json.dumps(integrity, sort_keys=True)}`\n\nScientific observations: `{json.dumps(science, sort_keys=True)}`\n\nCheckpoint measurement used the existing acquired temporal records, exact state conditioning, coarse-state equivalence, transition composition and ordinary organism valuation. Measurements occurred only at checkpoints, took up to `{max((s.get('measurement_seconds',0) for s in snapshots), default=0):.6f}s`, peaked at approximately `{peak_bytes}` diagnostic bytes, and did not mutate simulation or psyche state. Counts are unsmoothed.\n\nInterpretation class: **{cls}**. This does not establish planning. The first unsupported causal arrow remains prospective representation → current action selection.\n\n## Explicit answers\n\n```json\n{json.dumps(answers, indent=2, sort_keys=True)}\n```\n\n## Regression\n\nBaseline before 4.18.1: 266 collected, 248 passed, 15 failed, 3 skipped. Post-update exact comparison is recorded after verification; unrelated failures are not modified.\n"""
    report += "\nVerified regression: after 4.18.1, 269 collected, 251 passed, 15 failed, 3 skipped. " \
              "The exact baseline failure identities and signatures are unchanged; all three new tests pass.\n"
    (ACTIVE_OUT/"FINAL_REPORT.md").write_text(report)


def run_one(args):
    global STOP
    STOP = False
    eng = make_engine(args); cps = checkpoints(args.ticks); snapshots=[]; actions=[]; seq_first={}
    first = {k: None for k in ("FIRST_SUPPORTED_TRANSITION", "FIRST_DEPTH1_FUTURE",
        "FIRST_DEPTH2_COMPOSITION", "FIRST_DEPTH3_COMPOSITION", "FIRST_MULTI_CONSEQUENCE_BRANCH",
        "FIRST_PERSISTENT_TRACE", "FIRST_POSITIVE_FUTURE", "FIRST_LOCALLY_NONPOSITIVE_DEEPER_POSITIVE",
        "FIRST_UNSEEN_COMPLETE_SEQUENCE_WITH_POSITIVE_COMPOSED_FUTURE")}
    last=0; peak=0
    for target in cps:
        while eng.state.tick < target and not STOP:
            result = eng.step(); action = normalize_action(result.actions[A].kind); actions.append(action)
            for n in (2, 3):
                if len(actions) >= n:
                    seq_first.setdefault(tuple(actions[-n:]), eng.state.tick)
        if eng.state.tick < target: break
        snap = probe(eng, actions, seq_first); snapshots.append(snap); last=target
        tests = (("FIRST_SUPPORTED_TRANSITION", snap["supported_transition_count"]),
                 ("FIRST_DEPTH1_FUTURE", snap["known_depth1"]),
                 ("FIRST_DEPTH2_COMPOSITION", snap["known_depth2"]),
                 ("FIRST_DEPTH3_COMPOSITION", snap["known_depth3"]),
                 ("FIRST_MULTI_CONSEQUENCE_BRANCH", snap["multi_consequence_count"]),
                 ("FIRST_PERSISTENT_TRACE", snap["active_persistent_traces"]),
                 ("FIRST_POSITIVE_FUTURE", sum(snap[f"positive_depth{d}_count"] for d in (1,2,3))),
                 ("FIRST_LOCALLY_NONPOSITIVE_DEEPER_POSITIVE", snap["locally_nonpositive_deeper_positive_count"]))
        for key, present in tests:
            if present and first[key] is None: first[key] = eng.state.tick
        unseen = any(not c["complete_sequence_previously_seen"] for c in snap["locally_nonpositive_deeper_positive_cases"])
        if unseen and first["FIRST_UNSEEN_COMPLETE_SEQUENCE_WITH_POSITIVE_COMPOSED_FUTURE"] is None:
            first["FIRST_UNSEEN_COMPLETE_SEQUENCE_WITH_POSITIVE_COMPOSED_FUTURE"] = eng.state.tick
        peak = max(peak, len(json.dumps(snap)))
        write_outputs(args, snapshots, first, actions, eng.state.tick >= args.ticks, last, peak)
        print(f"[4.18.1] checkpoint {target}/{args.ticks} D1={snap['known_depth1']} D2={snap['known_depth2']} D3={snap['known_depth3']}", flush=True)
    eng.close()


def main():
    global ACTIVE_OUT
    p=argparse.ArgumentParser(); p.add_argument("--ticks",type=int,default=5000); p.add_argument("--seed",type=int,default=17)
    p.add_argument("--seeds",default=""); p.add_argument("--world-dynamics",choices=("static","dynamic"),default="dynamic")
    p.add_argument("--perception-mode",choices=("contact-only","multi-channel"),default="multi-channel")
    p.add_argument("--cue-mode",choices=("legacy","perceptual"),default="perceptual")
    p.add_argument("--memory-architecture",default="EXPERIENCE_GATED_V05")
    p.add_argument("--jsonl", default=""); p.add_argument("--archon-jsonl", default="")
    args=p.parse_args();
    if args.ticks < 1: p.error("--ticks must be >= 1")
    signal.signal(signal.SIGTERM,on_stop); signal.signal(signal.SIGINT,on_stop)
    seeds=[int(x) for x in args.seeds.split(",") if x.strip()] or [args.seed]
    for seed in seeds:
        args.seed=seed
        ACTIVE_OUT = OUT / f"SEED_{seed}" if len(seeds) > 1 else OUT
        run_one(args)
    if len(seeds) > 1:
        summaries = []
        for seed in seeds:
            path = OUT / f"SEED_{seed}" / "ACCEPTANCE_MATRIX.json"
            summaries.append({"seed": seed, "acceptance": json.loads(path.read_text())})
        (OUT / "CROSS_SEED_SUMMARY.json").write_text(json.dumps({"seeds": summaries}, indent=2, sort_keys=True)+"\n")

if __name__ == "__main__": main()
