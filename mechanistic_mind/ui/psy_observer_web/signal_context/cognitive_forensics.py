"""BETA2-SIGINT-06: cognitive divergence forensics × signal-to-action bottleneck.

Loads actual SIGINT-05 Level-2 hits and traces FIELD→…→action equality
using existing cognition observables only. Does not alter runtime behavior.
"""
from __future__ import annotations

import json
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.signal_context.interaction_episode import (
    NaturalSignalEpisode,
    EpisodeComponent,
    first_divergences_episode,
    run_episode_branch,
    trajectory_coupling_summary,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    audit_observation_no_intervention_leak,
    find_matched_s0,
    fingerprint_equal,
    make_signal_runtime,
    receiver_local_fields,
    scientific_fingerprint,
    stable_id,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SIGINT05 = (
    _PROJECT_ROOT / "results" / "signal_context_interpreter" / "beta2_sigint_05_20260918T110813Z"
)

HORIZON_MARKERS = (1, 2, 5, 10, 25, 50, 100)


def load_sigint05_level2_hits(
    sigint05_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Return the exact SIGINT-05 trials classified L2_cognition=True."""
    root = Path(sigint05_dir) if sigint05_dir else DEFAULT_SIGINT05
    trials = json.loads((root / "matched_episode_trials.json").read_text(encoding="utf-8"))
    hits = [t for t in trials if (t.get("levels") or {}).get("L2_cognition")]
    # Attach episode payload from repertoire
    rep = json.loads((root / "interaction_episode_repertoire.json").read_text(encoding="utf-8"))
    by_id = {e["episode_id"]: e for e in (rep.get("episodes") or [])}
    out = []
    for t in hits:
        ep = by_id.get(t["episode_id"])
        out.append({
            **t,
            "episode": ep,
            "sigint05_dir": str(root),
        })
    return out


def _scenario_brief(sc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(sc, dict):
        return None
    return {
        "scenario_id": sc.get("scenario_id"),
        "first_action": sc.get("first_action"),
        "historical_support": sc.get("historical_support"),
        "reliability": sc.get("reliability"),
        "depth": sc.get("depth"),
        "action_sequence": sc.get("action_sequence"),
    }


def cognitive_pipeline_snapshot(slot, *, slot_index: int) -> dict[str, Any]:
    """Bounded forensic extract from existing cognition — no new semantic vars."""
    cog = slot.cognition or {}
    sel = cog.get("last_selection") or {}
    obs = slot.last_agent_observation or {}
    comp = sel.get("competition") if isinstance(sel.get("competition"), dict) else {}
    considered = comp.get("candidates_considered") or []
    briefs = []
    if isinstance(considered, list):
        for sc in considered[:12]:
            if isinstance(sc, dict):
                briefs.append(_scenario_brief(sc))
    # Rank by (support, reliability, depth) when present — mirrors competition evidence order
    ranked = sorted(
        [b for b in briefs if b],
        key=lambda b: (
            -float(b.get("historical_support") or 0),
            -float(b.get("reliability") or 0),
            -float(b.get("depth") or 0),
            str(b.get("scenario_id") or ""),
        ),
    )
    winner = _scenario_brief(comp.get("selected_scenario"))
    runner = ranked[1] if len(ranked) > 1 else None
    margin = None
    if winner and runner:
        margin = {
            "support_delta": float(winner.get("historical_support") or 0)
            - float(runner.get("historical_support") or 0),
            "reliability_delta": float(winner.get("reliability") or 0)
            - float(runner.get("reliability") or 0),
            "depth_delta": float(winner.get("depth") or 0) - float(runner.get("depth") or 0),
            "winner_action": winner.get("first_action"),
            "runner_action": runner.get("first_action"),
            "same_action_class": winner.get("first_action") == runner.get("first_action"),
        }
    groups = sel.get("scenario_groups") if isinstance(sel.get("scenario_groups"), dict) else {}
    group_summary = {
        k: {
            "supported": bool((v or {}).get("supported")),
            "count": (v or {}).get("count"),
        }
        for k, v in list(groups.items())[:8]
    }
    preds = cog.get("predictions")
    # temporal / prospection availability (NOT_OBSERVABLE if missing)
    temporal = cog.get("temporal")
    prospection = cog.get("prospection")
    return {
        "slot": slot_index,
        "obs_FIELD_A": obs.get("local.FIELD_A"),
        "obs_FIELD_B": obs.get("local.FIELD_B"),
        "local_fields": None,  # filled by caller with physical sample
        "selection_source": sel.get("source"),
        "selection_rule": sel.get("selection_rule") or comp.get("selection_reason"),
        "requested_action": slot.last_selected_action or sel.get("action"),
        "candidates": list(sel.get("candidates") or []),
        "supported_actions": list(comp.get("supported_actions") or []),
        "unsupported_actions": list(comp.get("unsupported_actions") or []),
        "outcome_class": comp.get("outcome_class"),
        "selection_reason": comp.get("selection_reason"),
        "selected_scenario": winner,
        "candidates_considered": briefs,
        "ranked_scenarios": ranked[:8],
        "runner_up": runner,
        "action_selection_margin": margin,
        "scenario_groups": group_summary,
        "prospective_selection_mode": sel.get("prospective_selection_mode"),
        "prediction_n": len(preds) if isinstance(preds, list) else "NOT_OBSERVABLE",
        "prediction_matches": sel.get("prediction_matches"),
        "temporal_present": temporal is not None,
        "prospection_present": prospection is not None,
        "observation_leaks": audit_observation_no_intervention_leak(obs),
    }


def run_forensic_branch(
    snapshot: dict[str, Any],
    episode: NaturalSignalEpisode,
    *,
    mode: str,
    horizon: int,
    experiment_id: str,
    intervention_id: str,
) -> dict[str, Any]:
    """Episode branch with deep cognitive pipeline snapshots each tick."""
    from collections import defaultdict

    from mechanistic_mind.ui.psy_observer_web.signal_context.interaction_episode import (
        TRIGGER_EPISODE_REPLAY,
        TRIGGER_SHAM,
        _amp,
        _deposit_cells_for_component,
        schedule_for_mode,
        select_components,
    )

    rt = TwoAgentRuntime.restore(deepcopy(snapshot))
    pre_fp = scientific_fingerprint(rt)
    sham = mode == "SHAM"
    control = mode == "CONTROL"
    comps = [] if control else select_components(episode, mode)
    schedule = [] if control else schedule_for_mode(comps, mode)
    by_tick: dict[int, list] = defaultdict(list)
    for t, c in schedule:
        by_tick[int(t)].append(c)

    deep_traces = []
    injected = 0
    for i in range(int(horizon)):
        if i in by_tick:
            for c in by_tick[i]:
                amp = _amp(c)
                if amp is None:
                    continue
                cells = _deposit_cells_for_component(rt, c)
                if not cells:
                    continue
                rt.inject_source(
                    channel=c.channel,
                    amplitude=0.0 if sham else float(amp),
                    cells=cells,
                    trigger=TRIGGER_SHAM if sham else TRIGGER_EPISODE_REPLAY,
                    observer_source_id=f"exp:{experiment_id}:{intervention_id}:{mode}",
                )
                injected += 1
        rt.step()
        agents = []
        for si, slot in enumerate(rt.slots):
            snap_c = cognitive_pipeline_snapshot(slot, slot_index=si)
            snap_c["local_fields"] = receiver_local_fields(rt, si)
            agents.append({
                **snap_c,
                "x": float(slot.body.x),
                "y": float(slot.body.y),
                "vx": float(getattr(slot.body, "vx", 0.0) or 0.0),
                "vy": float(getattr(slot.body, "vy", 0.0) or 0.0),
            })
        deep_traces.append({
            "branch_tick": i + 1,
            "runtime_tick": int(rt.tick),
            "fingerprint": scientific_fingerprint(rt),
            "agents": agents,
            "contact": bool((rt.last_contact or {}).get("contact")),
            "natural_emissions": [
                {
                    "emitter_agent_id": s.get("emitter_agent_id"),
                    "channel": s.get("channel"),
                    "amplitude": s.get("amplitude") or s.get("realized"),
                    "trigger": s.get("trigger"),
                }
                for s in ((rt.last_signal_receipt or {}).get("sources") or [])
                if str(s.get("trigger") or "") not in (
                    TRIGGER_EPISODE_REPLAY, TRIGGER_SHAM, "EXTERNAL_EXPERIMENTAL_INTERVENTION"
                )
                and not str(s.get("trigger") or "").startswith("EXTERNAL")
            ],
        })
    return {
        "arm_id": mode,
        "mode": mode,
        "pre_fingerprint": pre_fp,
        "n_injected": injected,
        "deep_traces": deep_traces,
        "accepted": True,
    }


def _diff_stage(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True, default=str) != json.dumps(b, sort_keys=True, default=str)


def classify_divergence_kind(before: dict, after: dict, *, key: str) -> str | None:
    if not _diff_stage(before.get(key), after.get(key)):
        return None
    if key in ("selection_source",):
        return "SOURCE_CHANGE"
    if key in ("requested_action",):
        return "ACTION_CHANGE"
    if key in ("candidates", "supported_actions"):
        return "MEMBERSHIP_CHANGE"
    if key in ("ranked_scenarios", "candidates_considered"):
        # ordering vs membership
        ids_a = [x.get("scenario_id") for x in (before.get(key) or []) if isinstance(x, dict)]
        ids_b = [x.get("scenario_id") for x in (after.get(key) or []) if isinstance(x, dict)]
        if set(ids_a) != set(ids_b):
            return "CANDIDATE_CHANGE"
        if ids_a != ids_b:
            return "ORDERING_CHANGE"
        return "SCORE_CHANGE"
    if key in ("action_selection_margin", "selected_scenario"):
        return "SCORE_CHANGE"
    return "VALUE_CHANGE"


PIPELINE_KEYS = (
    ("obs_FIELD_A", "observation"),
    ("local_fields", "physical_FIELD_sample"),
    ("prediction_matches", "prediction"),
    ("candidates", "candidate_set"),
    ("ranked_scenarios", "candidate_ranking"),
    ("selected_scenario", "selected_candidate"),
    ("action_selection_margin", "selection_margin"),
    ("selection_source", "selection_source"),
    ("selection_reason", "selection_reason"),
    ("requested_action", "requested_action"),
)


def build_pipeline_ladder(
    control_traces: list[dict[str, Any]],
    replay_traces: list[dict[str, Any]],
    *,
    slot: int = 1,
) -> dict[str, Any]:
    n = min(len(control_traces), len(replay_traces))
    stages = {}
    for key, label in PIPELINE_KEYS:
        first = last = None
        for i in range(n):
            a = control_traces[i]["agents"][slot]
            b = replay_traces[i]["agents"][slot]
            if _diff_stage(a.get(key), b.get(key)):
                if first is None:
                    first = int(control_traces[i]["branch_tick"])
                last = int(control_traces[i]["branch_tick"])
        reconverge = None
        if first is not None and last is not None and last < n:
            # reconverge after last continuous divergence
            for i in range(n):
                tick = int(control_traces[i]["branch_tick"])
                if tick <= last:
                    continue
                a = control_traces[i]["agents"][slot]
                b = replay_traces[i]["agents"][slot]
                if not _diff_stage(a.get(key), b.get(key)):
                    reconverge = tick
                    break
        kind = None
        if first is not None:
            i0 = first - 1
            kind = classify_divergence_kind(
                control_traces[i0]["agents"][slot],
                replay_traces[i0]["agents"][slot],
                key=key,
            )
        stages[label] = {
            "key": key,
            "first_divergence_tick": first,
            "last_divergence_tick": last,
            "duration": None if first is None else (last - first + 1 if last else None),
            "reconvergence_tick": reconverge,
            "kind": kind,
            "status": (
                "DIVERGED" if first is not None else
                ("NOT_OBSERVABLE" if key in ("prediction_matches",) and
                 control_traces[0]["agents"][slot].get(key) is None else "SAME")
            ),
        }
    # Position / trajectory
    first_pos = None
    for i in range(n):
        a = control_traces[i]["agents"][slot]
        b = replay_traces[i]["agents"][slot]
        if abs(float(a["x"]) - float(b["x"])) > 1e-6 or abs(float(a["y"]) - float(b["y"])) > 1e-6:
            first_pos = int(control_traces[i]["branch_tick"])
            break
    stages["realized_position"] = {
        "first_divergence_tick": first_pos,
        "status": "DIVERGED" if first_pos else "SAME",
        "kind": "ACTION_CHANGE" if first_pos else None,
    }
    return stages


def find_bottleneck(
    ladder: dict[str, Any],
    control_traces: list[dict[str, Any]],
    replay_traces: list[dict[str, Any]],
    *,
    slot: int = 1,
) -> dict[str, Any]:
    """Identify last divergent upstream stage before action equality."""
    action_same = ladder.get("requested_action", {}).get("status") == "SAME"
    divergent_stages = [
        (name, info) for name, info in ladder.items()
        if info.get("status") == "DIVERGED" and name != "requested_action"
    ]
    divergent_stages.sort(key=lambda x: (x[1].get("first_divergence_tick") is None, x[1].get("first_divergence_tick") or 10**9))

    last_upstream = None
    for name, info in reversed(list(ladder.items())):
        if name in ("requested_action", "realized_position"):
            continue
        if info.get("status") == "DIVERGED":
            last_upstream = {"stage": name, **info}
            break

    # Explanations A–J tested against data
    explanations = []
    # Sample at first cognition divergence tick
    cog_t = (ladder.get("selection_source") or {}).get("first_divergence_tick")
    sample = None
    if cog_t is not None:
        i = cog_t - 1
        if 0 <= i < min(len(control_traces), len(replay_traces)):
            c = control_traces[i]["agents"][slot]
            r = replay_traces[i]["agents"][slot]
            sample = {"control": c, "replay": r, "branch_tick": cog_t}
            if c.get("requested_action") == r.get("requested_action") and c.get("requested_action") is not None:
                if _diff_stage(c.get("candidates"), r.get("candidates")) or _diff_stage(
                    c.get("ranked_scenarios"), r.get("ranked_scenarios")
                ):
                    # A: different candidates → same action
                    ca = {x.get("first_action") for x in (c.get("ranked_scenarios") or []) if isinstance(x, dict)}
                    ra = {x.get("first_action") for x in (r.get("ranked_scenarios") or []) if isinstance(x, dict)}
                    if c.get("requested_action") in ca and c.get("requested_action") in ra:
                        explanations.append({
                            "code": "A",
                            "supported": True,
                            "text": "Different internal candidates/scenarios map to the same discrete action.",
                        })
                win_c = (c.get("selected_scenario") or {}).get("scenario_id")
                win_r = (r.get("selected_scenario") or {}).get("scenario_id")
                if win_c == win_r and _diff_stage(c.get("ranked_scenarios"), r.get("ranked_scenarios")):
                    explanations.append({
                        "code": "B",
                        "supported": True,
                        "text": "Candidate rankings changed but winner scenario_id did not.",
                    })
                mc = c.get("action_selection_margin") or {}
                mr = r.get("action_selection_margin") or {}
                if mc and mr and (
                    mc.get("support_delta") != mr.get("support_delta")
                    or mc.get("reliability_delta") != mr.get("reliability_delta")
                ):
                    if mc.get("winner_action") == mr.get("winner_action"):
                        explanations.append({
                            "code": "C",
                            "supported": True,
                            "text": "Winning score/margin changed but did not cross an action-changing boundary.",
                        })
                if c.get("selection_source") != r.get("selection_source") and c.get("requested_action") == r.get("requested_action"):
                    explanations.append({
                        "code": "D",
                        "supported": True,
                        "text": "Selection source changed but produced the same action.",
                    })
                # F: reconvergence of selection_source before later ticks
                src = ladder.get("selection_source") or {}
                if src.get("reconvergence_tick") is not None and src.get("duration") is not None and src["duration"] <= 5:
                    explanations.append({
                        "code": "F",
                        "supported": True,
                        "text": "Divergence decayed/reconverged quickly before a lasting action difference.",
                    })
                # J: prediction-related fields differ while action same
                if _diff_stage(c.get("prediction_matches"), r.get("prediction_matches")):
                    explanations.append({
                        "code": "J",
                        "supported": True,
                        "text": "Divergence affected prediction-related observables without changing current action.",
                    })
                # H: action equivalence — runner has same action class
                if (mr.get("same_action_class") is True) or (mc.get("same_action_class") is True):
                    explanations.append({
                        "code": "H",
                        "supported": True,
                        "text": "Top scenarios belong to the same action equivalence class.",
                    })

    if action_same and last_upstream:
        classification = "ACTION_CONVERGENCE_WITH_INTERNAL_DIVERGENCE"
    elif not action_same:
        classification = "ACTION_DIVERGED"
    else:
        classification = "NO_INTERNAL_DIVERGENCE_RECORDED"

    supported = [e for e in explanations if e.get("supported")]
    return {
        "action_same": action_same,
        "classification": classification,
        "last_divergent_upstream": last_upstream,
        "explanations_tested": explanations,
        "best_supported": supported[0] if supported else {
            "code": None,
            "supported": False,
            "text": "Insufficient observable detail to identify a unique bottleneck mechanism.",
        },
        "sample_at_first_source_divergence": {
            "branch_tick": (sample or {}).get("branch_tick"),
            "control_source": ((sample or {}).get("control") or {}).get("selection_source"),
            "replay_source": ((sample or {}).get("replay") or {}).get("selection_source"),
            "control_action": ((sample or {}).get("control") or {}).get("requested_action"),
            "replay_action": ((sample or {}).get("replay") or {}).get("requested_action"),
            "control_winner": ((sample or {}).get("control") or {}).get("selected_scenario"),
            "replay_winner": ((sample or {}).get("replay") or {}).get("selected_scenario"),
            "control_margin": ((sample or {}).get("control") or {}).get("action_selection_margin"),
            "replay_margin": ((sample or {}).get("replay") or {}).get("action_selection_margin"),
        } if sample else None,
    }


def persistence_profile(ladder: dict[str, Any]) -> dict[str, Any]:
    src = ladder.get("selection_source") or {}
    first = src.get("first_divergence_tick")
    last = src.get("last_divergence_tick")
    recon = src.get("reconvergence_tick")
    dur = src.get("duration")
    label = "NOT_ESTABLISHED"
    if first is None:
        label = "NONE"
    elif recon is not None and dur is not None and dur <= 3:
        label = "TRANSIENT"
    elif recon is not None:
        label = "RECONVERGENT"
    elif last is not None and first is not None and (last - first) >= 20:
        label = "PERSISTENT"
    elif first is not None and first > 10:
        label = "DELAYED"
    else:
        label = "SHORT_LIVED"
    markers = {}
    for h in HORIZON_MARKERS:
        markers[str(h)] = bool(first is not None and first <= h and (last is None or last >= h) and (recon is None or recon > h))
    return {
        "label": label,
        "first": first,
        "last": last,
        "duration": dur,
        "reconvergence_tick": recon,
        "markers_still_diverged": markers,
    }


def natural_emission_divergence(
    control_traces: list[dict[str, Any]],
    replay_traces: list[dict[str, Any]],
) -> dict[str, Any]:
    n = min(len(control_traces), len(replay_traces))
    first = None
    rows = []
    for i in range(n):
        a = {(e.get("emitter_agent_id"), e.get("channel"), e.get("trigger")) for e in control_traces[i].get("natural_emissions") or []}
        b = {(e.get("emitter_agent_id"), e.get("channel"), e.get("trigger")) for e in replay_traces[i].get("natural_emissions") or []}
        if a != b:
            if first is None:
                first = int(control_traces[i]["branch_tick"])
            rows.append({
                "branch_tick": int(control_traces[i]["branch_tick"]),
                "control_n": len(a),
                "replay_n": len(b),
            })
    return {
        "first_divergence_tick": first,
        "n_divergent_ticks": len(rows),
        "sample": rows[:12],
    }


def classify_causal_edges(
    *,
    field_first: int | None,
    obs_first: int | None,
    cog_first: int | None,
    action_first: int | None,
    emission_first: int | None,
    sham_cog: int | None,
) -> list[dict[str, Any]]:
    edges = []

    def edge(src, dst, t_src, t_dst, sham_dst=None) -> dict[str, Any]:
        if t_src is None or t_dst is None:
            cls = "NOT_ESTABLISHED"
        elif sham_dst is not None:
            cls = "NOT_ESTABLISHED"  # sham also moved dest
        elif t_dst >= t_src:
            cls = "INTERVENTION_SUPPORTED" if t_dst == t_src or t_dst - t_src <= 5 else "TEMPORALLY_ASSOCIATED"
            if t_dst == t_src and src == "FIELD" and dst == "observation":
                cls = "DIRECT_CAUSAL_LINK"
        else:
            cls = "NOT_ESTABLISHED"
        return {"from": src, "to": dst, "t_from": t_src, "t_to": t_dst, "class": cls}

    edges.append(edge("FIELD", "observation", field_first, obs_first))
    edges.append(edge("observation", "cognition", obs_first, cog_first, sham_cog))
    edges.append(edge("cognition", "action", cog_first, action_first))
    edges.append(edge("cognition", "natural_emission", cog_first, emission_first))
    return edges


def reproduce_level2_hit(
    hit: dict[str, Any],
    *,
    horizon: int = 120,
    extended_horizons: tuple[int, ...] = (),
) -> dict[str, Any]:
    """Reproduce one SIGINT-05 L2 hit with deep forensics."""
    ep_raw = hit.get("episode")
    if not ep_raw:
        return {"accepted": False, "error": "missing episode payload", "hit": _hit_meta(hit)}
    episode = NaturalSignalEpisode(
        episode_id=str(ep_raw["episode_id"]),
        source_run_id=str(ep_raw.get("source_run_id") or ""),
        start_tick=int(ep_raw["start_tick"]),
        end_tick=int(ep_raw["end_tick"]),
        components=tuple(EpisodeComponent.from_dict(c) for c in (ep_raw.get("components") or [])),
        reconstruction=str(ep_raw.get("reconstruction") or "PARTIAL"),
    )
    seed = int(hit["seed"])
    expected_s0 = hit.get("s0_tick")
    s0 = find_matched_s0(
        seed=seed,
        receiver="agent_1",
        pre_action="WAIT",
        pre_selection_source="RETAINED_PREDICTION",
        require_no_contact=True,
        max_search=400,
        min_age=25,
    )
    if s0 is None:
        return {"accepted": False, "error": "no_s0", "hit": _hit_meta(hit)}
    s0_match = int(s0["tick"]) == int(expected_s0) if expected_s0 is not None else True
    eid = stable_id("forensic", episode.episode_id, seed)
    snap = s0["snapshot"]

    control = run_forensic_branch(
        snap, episode, mode="CONTROL", horizon=horizon,
        experiment_id=eid, intervention_id="ctrl",
    )
    sham = run_forensic_branch(
        snap, episode, mode="SHAM", horizon=horizon,
        experiment_id=eid, intervention_id="sham",
    )
    full = run_forensic_branch(
        snap, episode, mode="FULL_EPISODE", horizon=horizon,
        experiment_id=eid, intervention_id="full",
    )
    # CONTROL/CONTROL
    c2 = run_forensic_branch(
        snap, episode, mode="CONTROL", horizon=min(30, horizon),
        experiment_id=eid, intervention_id="cc",
    )
    ctrl_eq = all(
        fingerprint_equal(a["fingerprint"], b["fingerprint"])
        for a, b in zip(control["deep_traces"][:30], c2["deep_traces"])
    )
    # Reproduce FULL twice for determinism of L2
    full2 = run_forensic_branch(
        snap, episode, mode="FULL_EPISODE", horizon=min(40, horizon),
        experiment_id=eid, intervention_id="full2",
    )
    full_eq = all(
        fingerprint_equal(a["fingerprint"], b["fingerprint"])
        for a, b in zip(full["deep_traces"][:40], full2["deep_traces"])
    )

    # Prefer slot that shows selection_source divergence (check both)
    ladders = {
        0: build_pipeline_ladder(control["deep_traces"], full["deep_traces"], slot=0),
        1: build_pipeline_ladder(control["deep_traces"], full["deep_traces"], slot=1),
    }
    sham_ladders = {
        0: build_pipeline_ladder(control["deep_traces"], sham["deep_traces"], slot=0),
        1: build_pipeline_ladder(control["deep_traces"], sham["deep_traces"], slot=1),
    }
    focus_slot = 1
    for s in (0, 1):
        if (ladders[s].get("selection_source") or {}).get("first_divergence_tick") is not None:
            if (sham_ladders[s].get("selection_source") or {}).get("first_divergence_tick") is None:
                focus_slot = s
                break
    ladder = ladders[focus_slot]
    sham_ladder = sham_ladders[focus_slot]
    bottleneck = find_bottleneck(
        ladder, control["deep_traces"], full["deep_traces"], slot=focus_slot,
    )
    persist = persistence_profile(ladder)
    emis = natural_emission_divergence(control["deep_traces"], full["deep_traces"])

    field_first = (ladder.get("physical_FIELD_sample") or {}).get("first_divergence_tick")
    obs_first = (ladder.get("observation") or {}).get("first_divergence_tick")
    cog_first = (ladder.get("selection_source") or {}).get("first_divergence_tick")
    act_first = (ladder.get("requested_action") or {}).get("first_divergence_tick")
    sham_cog = (sham_ladder.get("selection_source") or {}).get("first_divergence_tick")
    edges = classify_causal_edges(
        field_first=field_first,
        obs_first=obs_first,
        cog_first=cog_first,
        action_first=act_first,
        emission_first=emis.get("first_divergence_tick"),
        sham_cog=sham_cog,
    )

    level2_reproduced = (
        cog_first is not None
        and sham_cog is None
        and act_first is None
    )
    reproduction_class = "REPRODUCIBLE_LEVEL2" if (level2_reproduced and full_eq) else (
        "NON_REPRODUCIBLE_LEVEL2" if not level2_reproduced else "REPRODUCIBLE_LEVEL2"
    )

    # Extended horizons (only if L2 reproduced)
    extended = []
    if level2_reproduced and extended_horizons:
        for H in extended_horizons:
            ext_full = run_forensic_branch(
                snap, episode, mode="FULL_EPISODE", horizon=int(H),
                experiment_id=eid, intervention_id=f"ext{H}",
            )
            ext_ctrl = run_forensic_branch(
                snap, episode, mode="CONTROL", horizon=int(H),
                experiment_id=eid, intervention_id=f"extc{H}",
            )
            ext_ladder = build_pipeline_ladder(
                ext_ctrl["deep_traces"], ext_full["deep_traces"], slot=focus_slot,
            )
            div = first_divergences_episode(
                {"traces": _compat_traces(ext_ctrl)},
                {"traces": _compat_traces(ext_full)},
            )
            extended.append({
                "horizon": int(H),
                "action_first": (ext_ladder.get("requested_action") or {}).get("first_divergence_tick"),
                "trajectory_first": (ext_ladder.get("realized_position") or {}).get("first_divergence_tick"),
                "source_still_diverged_at_end": (
                    (ext_ladder.get("selection_source") or {}).get("last_divergence_tick") is not None
                    and (ext_ladder.get("selection_source") or {}).get("reconvergence_tick") is None
                ),
                "compat_div": div,
                "coupling_delta": None,
            })

    # Component ablation: remove emissions at first cog tick's corresponding episode Δt
    ablations = []
    if level2_reproduced and cog_first is not None:
        # Remove components whose delta_t == cog_first-1 (injection branch tick)
        target_dt = max(0, int(cog_first) - 1)
        # Build reduced episode
        kept = [c for c in episode.components if int(c.delta_t) != target_dt]
        if len(kept) < len(episode.components):
            reduced = NaturalSignalEpisode(
                episode_id=episode.episode_id + f"-rm-dt{target_dt}",
                source_run_id=episode.source_run_id,
                start_tick=episode.start_tick,
                end_tick=episode.end_tick,
                components=tuple(kept),
                reconstruction=episode.reconstruction,
            )
            abl = run_forensic_branch(
                snap, reduced, mode="FULL_EPISODE", horizon=min(horizon, 80),
                experiment_id=eid, intervention_id="abl",
            )
            abl_ladder = build_pipeline_ladder(
                control["deep_traces"], abl["deep_traces"], slot=focus_slot,
            )
            ablations.append({
                "removed_delta_t": target_dt,
                "n_removed": len(episode.components) - len(kept),
                "cog_first_after_ablation": (abl_ladder.get("selection_source") or {}).get("first_divergence_tick"),
                "effect_abolished": (abl_ladder.get("selection_source") or {}).get("first_divergence_tick") is None,
            })

    any_leak = any(
        ag.get("observation_leaks")
        for t in full["deep_traces"]
        for ag in t["agents"]
    )

    return {
        "accepted": True,
        "hit": _hit_meta(hit),
        "s0_tick": s0["tick"],
        "s0_tick_matches_sigint05": s0_match,
        "focus_slot": focus_slot,
        "control_control_equal": ctrl_eq,
        "full_full_equal": full_eq,
        "level2_reproduced": level2_reproduced,
        "reproduction_class": reproduction_class,
        "pipeline_ladder": ladder,
        "sham_pipeline_ladder": sham_ladder,
        "both_slots_source_first": {
            0: (ladders[0].get("selection_source") or {}).get("first_divergence_tick"),
            1: (ladders[1].get("selection_source") or {}).get("first_divergence_tick"),
        },
        "bottleneck": bottleneck,
        "persistence": persist,
        "natural_emission_divergence": emis,
        "causal_edges": edges,
        "SIGNAL_TO_COGNITION_TO_EMISSION_CANDIDATE": bool(
            cog_first is not None
            and emis.get("first_divergence_tick") is not None
            and int(emis["first_divergence_tick"]) >= int(cog_first)
            and sham_cog is None
        ),
        "extended_horizon": extended,
        "ablations": ablations,
        "any_leak": any_leak,
        "n_injected_full": full.get("n_injected"),
        # Compact parallel-lane sample around first cog divergence
        "parallel_lanes": _parallel_lanes(
            control["deep_traces"], full["deep_traces"], focus_slot, cog_first,
        ),
    }


def _compat_traces(forensic_arm: dict[str, Any]) -> list[dict[str, Any]]:
    """Adapt deep traces to interaction_episode first_divergences shape."""
    out = []
    for t in forensic_arm.get("deep_traces") or []:
        out.append({
            "branch_tick": t["branch_tick"],
            "agents": [
                {
                    "action": a.get("requested_action"),
                    "selection_source": a.get("selection_source"),
                    "x": a.get("x"),
                    "y": a.get("y"),
                    "obs_fields": {
                        "local.FIELD_A": a.get("obs_FIELD_A"),
                        "local.FIELD_B": a.get("obs_FIELD_B"),
                    },
                    "local_fields": a.get("local_fields") or {},
                }
                for a in t["agents"]
            ],
            "coupling": {
                "inter_agent_distance": 0.0,
                "velocity_alignment": 0.0,
            },
            "contact": t.get("contact"),
            "fingerprint": t.get("fingerprint"),
        })
    return out


def _parallel_lanes(
    control_traces: list[dict[str, Any]],
    replay_traces: list[dict[str, Any]],
    slot: int,
    cog_tick: int | None,
) -> dict[str, Any]:
    if cog_tick is None:
        i = 0
    else:
        i = max(0, min(len(control_traces), len(replay_traces), cog_tick) - 1)
    c = control_traces[i]["agents"][slot]
    r = replay_traces[i]["agents"][slot]
    return {
        "branch_tick": control_traces[i]["branch_tick"],
        "CONTROL": {
            "FIELD": c.get("obs_FIELD_A"),
            "SOURCE": c.get("selection_source"),
            "WINNER": (c.get("selected_scenario") or {}).get("scenario_id"),
            "CAND_ACTIONS": c.get("supported_actions") or c.get("candidates"),
            "ACTION": c.get("requested_action"),
            "MARGIN": c.get("action_selection_margin"),
        },
        "REPLAY": {
            "FIELD": r.get("obs_FIELD_A"),
            "SOURCE": r.get("selection_source"),
            "WINNER": (r.get("selected_scenario") or {}).get("scenario_id"),
            "CAND_ACTIONS": r.get("supported_actions") or r.get("candidates"),
            "ACTION": r.get("requested_action"),
            "MARGIN": r.get("action_selection_margin"),
        },
        "divergence_dies_at_action": c.get("requested_action") == r.get("requested_action")
        and c.get("selection_source") != r.get("selection_source"),
    }


def _hit_meta(hit: dict[str, Any]) -> dict[str, Any]:
    return {
        "episode_id": hit.get("episode_id"),
        "start_tick": hit.get("start_tick"),
        "end_tick": hit.get("end_tick"),
        "seed": hit.get("seed"),
        "s0_tick": hit.get("s0_tick"),
        "reconstruction": hit.get("reconstruction"),
        "sigint05_levels": hit.get("levels"),
        "sigint05_full_div": (hit.get("divergences") or {}).get("FULL_EPISODE"),
    }


def run_small_context_matrix(
    hit: dict[str, Any],
    *,
    horizon: int = 80,
) -> list[dict[str, Any]]:
    """Bounded context variants for a reproduced L2 hit — no arbitrary synthesis."""
    ep_raw = hit.get("episode")
    if not ep_raw:
        return []
    episode = NaturalSignalEpisode(
        episode_id=str(ep_raw["episode_id"]),
        source_run_id=str(ep_raw.get("source_run_id") or ""),
        start_tick=int(ep_raw["start_tick"]),
        end_tick=int(ep_raw["end_tick"]),
        components=tuple(EpisodeComponent.from_dict(c) for c in (ep_raw.get("components") or [])),
        reconstruction=str(ep_raw.get("reconstruction") or "PARTIAL"),
    )
    seed = int(hit["seed"])
    contexts = [
        ("agent_1", "WAIT", "RETAINED_PREDICTION", True, "orig_receiver"),
        ("agent_0", "WAIT", "RETAINED_PREDICTION", True, "peer_receiver"),
        ("agent_1", "MOVE:E", "ENDOGENOUS_VARIATION", True, "move_endogenous"),
    ]
    rows = []
    for receiver, action, src, no_contact, label in contexts:
        s0 = find_matched_s0(
            seed=seed, receiver=receiver, pre_action=action,
            pre_selection_source=src, require_no_contact=no_contact,
            max_search=350, min_age=25,
        )
        if s0 is None:
            rows.append({"context": label, "accepted": False})
            continue
        eid = stable_id("ctx", episode.episode_id, label)
        ctrl = run_forensic_branch(
            s0["snapshot"], episode, mode="CONTROL", horizon=horizon,
            experiment_id=eid, intervention_id="c",
        )
        full = run_forensic_branch(
            s0["snapshot"], episode, mode="FULL_EPISODE", horizon=horizon,
            experiment_id=eid, intervention_id="f",
        )
        slot = 1 if str(receiver).endswith("1") else 0
        ladder = build_pipeline_ladder(ctrl["deep_traces"], full["deep_traces"], slot=slot)
        rows.append({
            "context": label,
            "accepted": True,
            "s0_tick": s0["tick"],
            "receiver": receiver,
            "cog_first": (ladder.get("selection_source") or {}).get("first_divergence_tick"),
            "action_first": (ladder.get("requested_action") or {}).get("first_divergence_tick"),
        })
    return rows
