#!/usr/bin/env python3
"""Forensic post-run analysis for ONE Psy Observer Web saved run.

Read-only. Does not modify the run directory contents except writing into
<run>/analysis/ (derived artifacts only).
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = (
    _ROOT / "results" / "psychology_observer" / "psy_observer_web"
    / "psyweb-20260916T144643.524707Z-d463612b"
)
EXPECTED_TICK = 17730
OUT = RUN_DIR / "analysis"
W = 32.0
H = 32.0


def _json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=_ser) + "\n")


def _ser(o: Any) -> Any:
    if isinstance(o, set):
        return sorted(o)
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return str(o)


def _md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n")


def wrap_delta(a: float, b: float, period: float) -> float:
    d = b - a
    return d - period * round(d / period)


def wrap_dist(x0: float, y0: float, x1: float, y1: float) -> float:
    dx = wrap_delta(x0, x1, W)
    dy = wrap_delta(y0, y1, H)
    return math.hypot(dx, dy)


def path_length(pts: list[tuple[float, float]]) -> float:
    s = 0.0
    for i in range(1, len(pts)):
        s += wrap_dist(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1])
    return s


def displacement(p0: tuple[float, float], p1: tuple[float, float]) -> float:
    return wrap_dist(p0[0], p0[1], p1[0], p1[1])


def longest_runs(actions: list[str | None]) -> list[dict[str, Any]]:
    out = []
    if not actions:
        return out
    start = 0
    cur = actions[0]
    for i in range(1, len(actions) + 1):
        if i == len(actions) or actions[i] != cur:
            out.append({"action": cur, "start": start, "end": i - 1, "length": i - start})
            if i < len(actions):
                start = i
                cur = actions[i]
    out.sort(key=lambda r: -r["length"])
    return out


def regimes_from_actions(actions: list[str | None], window: int = 100) -> list[dict[str, Any]]:
    """Dominant-action regimes over sliding non-overlapping windows; merge adjacent same label."""
    chunks = []
    for i in range(0, len(actions), window):
        chunk = actions[i : i + window]
        c = Counter(a for a in chunk if a)
        if not c:
            label = "EMPTY"
        else:
            label = c.most_common(1)[0][0]
        chunks.append({"start": i, "end": i + len(chunk) - 1, "dominant": label, "counts": dict(c)})
    merged = []
    for ch in chunks:
        if merged and merged[-1]["dominant"] == ch["dominant"]:
            merged[-1]["end"] = ch["end"]
            for k, v in ch["counts"].items():
                merged[-1]["counts"][k] = merged[-1]["counts"].get(k, 0) + v
        else:
            merged.append({**ch, "counts": dict(ch["counts"])})
    for m in merged:
        m["length"] = m["end"] - m["start"] + 1
    return merged


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    assert RUN_DIR.is_dir(), RUN_DIR

    run = json.loads((RUN_DIR / "run.json").read_text())
    timeline = [json.loads(l) for l in (RUN_DIR / "session_timeline.jsonl").read_text().splitlines() if l.strip()]
    telemetry = json.loads((RUN_DIR / "session_telemetry.json").read_text())
    events_doc = json.loads((RUN_DIR / "structured_events.json").read_text())
    events = events_doc.get("events") or []
    light = json.loads((OUT / "_snapshot_light.json").read_text()) if (OUT / "_snapshot_light.json").is_file() else {}
    if not light:
        # minimal: do not reload 193MB unless needed
        light = {"tick": run.get("final_tick"), "seed": run.get("seed"), "starts": [[8, 16], [12, 16]]}

    # ---------- identity ----------
    final_tick = int(run.get("final_tick") or -1)
    discrepancy = None
    if final_tick != EXPECTED_TICK:
        discrepancy = {
            "expected_final_tick_from_user_query": EXPECTED_TICK,
            "stored_final_tick": final_tick,
            "stored_buffer_live_tick": (run.get("buffer") or {}).get("live_tick"),
            "note": "Continuing analysis using ONLY stored target directory values.",
        }

    identity = {
        "run_id": run.get("run_id"),
        "seed": run.get("seed"),
        "runtime_type": run.get("runtime_type") or run.get("runtime_kind"),
        "generation": run.get("runtime_generation") or run.get("generation") or "NOT_RECORDED",
        "final_tick": final_tick,
        "termination_reason": run.get("termination_reason") or run.get("stop_reason"),
        "capabilities": run.get("capabilities"),
        "available_artifacts": sorted(p.name for p in RUN_DIR.iterdir() if p.is_file()),
        "agent_count": run.get("agent_count"),
        "started_at": run.get("started_at"),
        "stopped_at": run.get("stopped_at"),
        "experimental_overrides": run.get("experimental_overrides"),
        "tick_discrepancy_vs_user_query": discrepancy,
        "snapshot_signal_enabled_flag": light.get("signal_enabled"),
        "snapshot_agent_seeds": light.get("agent_seeds") or [a.get("agent_seed") for a in (run.get("agents") or [])],
        "starts": light.get("starts") or [[8, 16], [12, 16]],
    }

    # ---------- rebuild per-agent series from timeline ----------
    # timeline covers ticks 0..3077 (3077 lines); bodies present on every row
    by_agent: dict[str, dict[str, list]] = {
        "agent_0": {"tick": [], "action": [], "x": [], "y": [], "source": []},
        "agent_1": {"tick": [], "action": [], "x": [], "y": [], "source": []},
    }
    contacts = []
    for row in timeline:
        t = int(row["tick"])
        if row.get("contact"):
            contacts.append(t)
        # action_source is for selected observer agent only
        src = row.get("action_source")
        sel_id = row.get("agent_id")
        for b in row.get("bodies") or []:
            aid = b["agent_id"]
            by_agent[aid]["tick"].append(t)
            by_agent[aid]["action"].append(b.get("action"))
            by_agent[aid]["x"].append(float(b["x"]))
            by_agent[aid]["y"].append(float(b["y"]))
            # source only reliable when this agent is the selected observer in that frame
            by_agent[aid]["source"].append(src if sel_id == aid else None)

    # inter-agent distance series
    dist_series = []
    n = min(len(by_agent["agent_0"]["tick"]), len(by_agent["agent_1"]["tick"]))
    for i in range(n):
        t = by_agent["agent_0"]["tick"][i]
        d = wrap_dist(
            by_agent["agent_0"]["x"][i], by_agent["agent_0"]["y"][i],
            by_agent["agent_1"]["x"][i], by_agent["agent_1"]["y"][i],
        )
        dist_series.append({"tick": t, "distance": d})

    closest = min(dist_series, key=lambda r: r["distance"]) if dist_series else None

    # proximity episodes: distance < threshold
    prox_thr = 2.0
    proximity_episodes = []
    in_ep = False
    ep_start = None
    ep_min = None
    for row in dist_series:
        if row["distance"] < prox_thr:
            if not in_ep:
                in_ep = True
                ep_start = row["tick"]
                ep_min = row["distance"]
            else:
                ep_min = min(ep_min, row["distance"])
        elif in_ep:
            proximity_episodes.append({
                "start": ep_start, "end": row["tick"] - 1,
                "length": row["tick"] - ep_start,
                "min_distance": ep_min, "threshold": prox_thr,
            })
            in_ep = False
    if in_ep:
        proximity_episodes.append({
            "start": ep_start, "end": dist_series[-1]["tick"],
            "length": dist_series[-1]["tick"] - ep_start + 1,
            "min_distance": ep_min, "threshold": prox_thr,
        })

    # contact episodes from timeline
    contact_episodes = []
    if contacts:
        contacts = sorted(set(contacts))
        s = contacts[0]
        prev = contacts[0]
        for t in contacts[1:]:
            if t == prev + 1:
                prev = t
            else:
                contact_episodes.append({"start": s, "end": prev, "length": prev - s + 1})
                s = prev = t
        contact_episodes.append({"start": s, "end": prev, "length": prev - s + 1})

    # ---------- per-agent summaries ----------
    agent_summaries = {}
    for aid, series in by_agent.items():
        actions = series["action"]
        pts = list(zip(series["x"], series["y"]))
        # skip null actions at t=0
        act_counts = Counter(a for a in actions if a)
        transitions = Counter()
        for i in range(1, len(actions)):
            if actions[i - 1] and actions[i] and actions[i - 1] != actions[i]:
                transitions[f"{actions[i-1]}->{actions[i]}"] += 1
        runs = longest_runs(actions)
        wait_runs = [r for r in runs if r["action"] == "WAIT"]
        # WAIT vs MOVE path length
        wait_path = 0.0
        move_path = 0.0
        wait_disp_steps = 0.0
        move_disp_steps = 0.0
        for i in range(1, len(pts)):
            step_d = wrap_dist(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1])
            a = actions[i]  # action selected for this tick (as recorded on body at capture)
            if a == "WAIT":
                wait_path += step_d
                wait_disp_steps += step_d
            elif a and str(a).startswith("MOVE"):
                move_path += step_d
                move_disp_steps += step_d
        total_path = path_length(pts)
        wait_frac = wait_path / total_path if total_path > 0 else None
        # from run.json agent summaries where present
        run_agent = next((a for a in (run.get("agents") or []) if a.get("observer_id") == aid), {})
        regimes = regimes_from_actions(actions, window=200)
        agent_summaries[aid] = {
            "observer_id": aid,
            "agent_seed": run_agent.get("agent_seed"),
            "initial_position": {"x": pts[0][0], "y": pts[0][1]} if pts else None,
            "final_position": {"x": pts[-1][0], "y": pts[-1][1]} if pts else None,
            "net_displacement_wrap": displacement(pts[0], pts[-1]) if pts else None,
            "path_length_wrap": total_path,
            "unique_cells_from_manifest": run_agent.get("unique_cells_visited"),
            "selected_action_counts": dict(act_counts),
            "selected_action_counts_manifest": run_agent.get("action_counts"),
            "action_transitions_top": transitions.most_common(20),
            "longest_action_episodes": runs[:10],
            "longest_WAIT_episodes": wait_runs[:5],
            "wait_path_length": wait_path,
            "move_path_length": move_path,
            "wait_drift_fraction_of_path": wait_frac,
            "move_path_fraction": (move_path / total_path) if total_path else None,
            "final_selected_action": actions[-1] if actions else None,
            "final_selection_source_manifest": run_agent.get("selection_source"),
            "final_selection_reason_manifest": run_agent.get("selection_reason"),
            "final_supported_actions_manifest": run_agent.get("supported_actions"),
            "collision_count_manifest": run_agent.get("collision_count"),
            "distance_travelled_manifest": run_agent.get("distance_travelled"),
            "cognition_ticks_manifest": run_agent.get("cognition_ticks"),
            "prospective_compositions_manifest": run_agent.get("prospective_compositions"),
            "prediction_count_manifest": run_agent.get("prediction_count"),
            "behavioral_regimes_dominant_action_200tick": regimes,
            "timeline_points": len(pts),
            "notes": [
                "Action on timeline bodies is the selected action recorded at capture; may be null at tick 0.",
                "Path lengths use WRAP_PERIODIC metric.",
                "WAIT path length is PASSIVE/environmental/inertial displacement while WAIT was selected — not intentional locomotion.",
                "Telemetry work series appear observer-selected-agent scoped (see limitations).",
            ],
        }

    # ---------- signals ----------
    emits = [e for e in events if e.get("type") == "PHYSICAL_SIGNAL_EMITTED"]
    recvs = [e for e in events if e.get("type") == "PHYSICAL_SIGNAL_RECEIVED"]

    # Deduce: emits recorded on agent_1 with observer_source_id agent_0 are buffer duplicates
    emit_primary = []
    emit_duplicate_buffer = []
    for e in emits:
        evd = e.get("evidence") or {}
        src = evd.get("observer_source_id")
        if src and e.get("agent_id") != src:
            emit_duplicate_buffer.append(e)
        else:
            emit_primary.append(e)

    signal_by_agent = {
        "agent_0": {"emissions_primary": [], "receptions": [], "emissions_duplicate_buffer": []},
        "agent_1": {"emissions_primary": [], "receptions": [], "emissions_duplicate_buffer": []},
    }
    for e in emit_primary:
        aid = e.get("agent_id") or "unknown"
        signal_by_agent.setdefault(aid, {"emissions_primary": [], "receptions": [], "emissions_duplicate_buffer": []})
        signal_by_agent[aid]["emissions_primary"].append(e)
    for e in emit_duplicate_buffer:
        aid = e.get("agent_id") or "unknown"
        signal_by_agent.setdefault(aid, {"emissions_primary": [], "receptions": [], "emissions_duplicate_buffer": []})
        signal_by_agent[aid]["emissions_duplicate_buffer"].append(e)
    for e in recvs:
        aid = e.get("agent_id") or (e.get("evidence") or {}).get("observer_receiver_id")
        signal_by_agent.setdefault(aid, {"emissions_primary": [], "receptions": [], "emissions_duplicate_buffer": []})
        signal_by_agent[aid]["receptions"].append(e)

    # Pairing: for each primary emit, find receptions within temporal window
    pairs = []
    for em in emit_primary:
        et = int(em["tick"])
        ee = em.get("evidence") or {}
        emitter = ee.get("observer_source_id") or em.get("agent_id")
        for rv in recvs:
            rt = int(rv["tick"])
            if rt < et or rt > et + 20:
                continue
            re = rv.get("evidence") or {}
            receiver = re.get("observer_receiver_id") or rv.get("agent_id")
            # spatial: emission has x,y; reception does not have position in evidence
            # use timeline positions at ticks
            sep = None
            conf = "AMBIGUOUS"
            basis = []
            if emitter and receiver:
                # find positions
                try:
                    i_e = by_agent[emitter]["tick"].index(et)
                    i_r = by_agent[receiver]["tick"].index(rt)
                    sep = wrap_dist(
                        by_agent[emitter]["x"][i_e], by_agent[emitter]["y"][i_e],
                        by_agent[receiver]["x"][i_r], by_agent[receiver]["y"][i_r],
                    )
                    basis.append("timeline_positions_at_emit_and_recv_ticks")
                except (ValueError, KeyError):
                    pass
            if receiver == emitter:
                conf = "DIRECTLY_RECORDED"
                basis.append("same_agent_self_reception_after_own_emission")
            elif sep is not None and sep < 5.0 and rt - et <= 5:
                conf = "STRONGLY_SUPPORTED"
                basis.append("temporal_adjacency_and_proximity")
            elif rt - et <= 5:
                conf = "AMBIGUOUS"
                basis.append("temporal_adjacency_only")
            else:
                conf = "UNRESOLVED"
            pairs.append({
                "emission_tick": et,
                "reception_tick": rt,
                "temporal_offset": rt - et,
                "emitter": emitter,
                "receiver": receiver,
                "channel": ee.get("channel") or "A",
                "spatial_separation": sep,
                "emit_realized": ee.get("realized"),
                "recv_field_A": re.get("local.FIELD_A"),
                "classification": conf,
                "evidence_basis": basis,
            })

    # ---------- windows around receptions ----------
    def window_stats(aid: str, center: int, half: int) -> dict[str, Any]:
        ticks = by_agent[aid]["tick"]
        try:
            idx = ticks.index(center)
        except ValueError:
            return {"status": "NOT_RECORDED", "center": center}
        lo = max(0, idx - half)
        hi = min(len(ticks) - 1, idx + half)
        acts = by_agent[aid]["action"][lo : hi + 1]
        xs = by_agent[aid]["x"][lo : hi + 1]
        ys = by_agent[aid]["y"][lo : hi + 1]
        pts = list(zip(xs, ys))
        return {
            "center": center,
            "window": [ticks[lo], ticks[hi]],
            "action_counts": dict(Counter(a for a in acts if a)),
            "path_length": path_length(pts),
            "net_displacement": displacement(pts[0], pts[-1]) if pts else None,
            "n_transitions": sum(
                1 for i in range(1, len(acts)) if acts[i - 1] and acts[i] and acts[i - 1] != acts[i]
            ),
        }

    reception_windows = []
    for rv in recvs:
        aid = (rv.get("evidence") or {}).get("observer_receiver_id") or rv.get("agent_id")
        t = int(rv["tick"])
        reception_windows.append({
            "agent": aid,
            "tick": t,
            "field_A": (rv.get("evidence") or {}).get("local.FIELD_A"),
            "w25": window_stats(aid, t, 25),
            "w100": window_stats(aid, t, 100),
        })

    # cognition events in buffer
    cog_events = [e for e in events if e.get("type") in {
        "SCENARIO_SELECTED", "DISCRETE_ACTION_SELECTED", "PREDICTION_MATCH", "PROSPECTION"
    } or "SCENARIO" in str(e.get("type")) or "ACTION" in str(e.get("type"))]

    # ---------- signal near proximity ----------
    emit_during_prox = []
    for em in emit_primary:
        et = int(em["tick"])
        drow = next((r for r in dist_series if r["tick"] == et), None)
        emit_during_prox.append({
            "tick": et,
            "distance": None if drow is None else drow["distance"],
            "near_threshold_2": (drow is not None and drow["distance"] < 2.0),
            "emitter": (em.get("evidence") or {}).get("observer_source_id"),
        })

    # ---------- causal candidates ----------
    # Check agent_0 emit -> agent_1 receive
    chains = []
    for em in emit_primary:
        et = int(em["tick"])
        emitter = (em.get("evidence") or {}).get("observer_source_id") or em.get("agent_id")
        for rv in recvs:
            rt = int(rv["tick"])
            receiver = (rv.get("evidence") or {}).get("observer_receiver_id") or rv.get("agent_id")
            if receiver == emitter:
                continue  # self
            if not (et <= rt <= et + 30):
                continue
            # action change after reception?
            acts = by_agent[receiver]["action"]
            ticks = by_agent[receiver]["tick"]
            try:
                idx = ticks.index(rt)
            except ValueError:
                continue
            before = acts[max(0, idx - 10) : idx]
            after = acts[idx : min(len(acts), idx + 25)]
            before_c = Counter(a for a in before if a)
            after_c = Counter(a for a in after if a)
            action_changed = before_c.most_common(1) != after_c.most_common(1) if before_c and after_c else False
            # distance at emit
            drow = next((r for r in dist_series if r["tick"] == et), None)
            chains.append({
                "direction": f"{emitter}→{receiver}",
                "links": {
                    "emission": "OBSERVED",
                    "reception": "OBSERVED",
                    "receiver_accessible_field": "OBSERVED" if (rv.get("evidence") or {}).get("local.FIELD_A") is not None else "NOT_RECORDED",
                    "cognition_change": "NOT_RECORDED",  # no per-tick cognition in timeline
                    "action_selection_change": "SUPPORTED" if action_changed else "AMBIGUOUS",
                    "physical_consequence_change": "AMBIGUOUS",
                },
                "emission_tick": et,
                "reception_tick": rt,
                "distance_at_emission": None if drow is None else drow["distance"],
                "before_actions": dict(before_c),
                "after_actions": dict(after_c),
                "action_changed_dominant": action_changed,
                "note": "Cognition internals around these ticks are NOT in timeline; structured_events buffer is late-window only.",
            })

    # Agent1 receptions at 3059-3062: no primary emit in buffer before them (buffer truncated)
    orphan_recvs = []
    for rv in recvs:
        rt = int(rv["tick"])
        receiver = (rv.get("evidence") or {}).get("observer_receiver_id") or rv.get("agent_id")
        prior_emits = [em for em in emit_primary if int(em["tick"]) <= rt]
        if not prior_emits:
            orphan_recvs.append({
                "tick": rt,
                "receiver": receiver,
                "field_A": (rv.get("evidence") or {}).get("local.FIELD_A"),
                "status": "RECEPTION_WITHOUT_EMIT_IN_BOUNDED_BUFFER",
            })

    # ---------- telemetry note ----------
    tel_series = telemetry.get("series") or []
    tel_ticks = [r["tick"] for r in tel_series]

    # physical interaction from events
    body_moved = [e for e in events if e.get("type") == "BODY_MOVED"]
    deformed = [e for e in events if e.get("type") == "BODY_DEFORMED"]

    # ---------- claim boundary ----------
    signal_to_cognition_to_action = {
        "agent_0_to_agent_1": {
            "status": "NO_EVIDENCE",
            "rationale": (
                "Primary emissions in the bounded event buffer are late (t≈3071–3072) from agent_0. "
                "agent_1 receptions in buffer (t≈3059–3062) have no paired emission in the same buffer "
                "(earlier emits overwritten). agent_1 selected WAIT for all 3077 recorded ticks; "
                "no selected-action change is available to attribute to reception."
            ),
        },
        "agent_1_to_agent_0": {
            "status": "NO_EVIDENCE",
            "rationale": (
                "No primary PHYSICAL_SIGNAL_EMITTED with observer_source_id=agent_1 in the saved buffer. "
                "Events labeled PHYSICAL_SIGNAL_EMITTED on agent_1 carry observer_source_id=agent_0 "
                "(duplicate buffer copy of agent_0 emission). Not an agent_1 emission."
            ),
        },
        "overall": "CAUSAL_EFFECT_NOT_DEMONSTRATED",
        "strongest_inter_agent_evidence": (
            "Physical proximity + contact episodes + agent_0 body_motion FIELD_A deposits; "
            "agent_1 local FIELD_A receptions at low magnitude without demonstrated action change."
        ),
    }

    comparison = {
        "agent_0": agent_summaries["agent_0"],
        "agent_1": agent_summaries["agent_1"],
        "asymmetries": [
            {
                "feature": "selected_action_distribution",
                "agent_0": agent_summaries["agent_0"]["selected_action_counts"],
                "agent_1": agent_summaries["agent_1"]["selected_action_counts"],
                "classification": "HISTORY_DEPENDENT",
                "note": "agent_0 locked on MOVE:N (SINGLE_SUPPORTED); agent_1 locked on WAIT (SINGLE_SUPPORTED).",
            },
            {
                "feature": "path_length",
                "agent_0": agent_summaries["agent_0"]["path_length_wrap"],
                "agent_1": agent_summaries["agent_1"]["path_length_wrap"],
                "classification": "HISTORY_DEPENDENT",
                "note": "agent_1 path is almost entirely WAIT-drift.",
            },
            {
                "feature": "wait_drift_fraction",
                "agent_0": agent_summaries["agent_0"]["wait_drift_fraction_of_path"],
                "agent_1": agent_summaries["agent_1"]["wait_drift_fraction_of_path"],
                "classification": "HISTORY_DEPENDENT",
            },
            {
                "feature": "signal_emission_primary",
                "agent_0": len(signal_by_agent["agent_0"]["emissions_primary"]),
                "agent_1": len(signal_by_agent["agent_1"]["emissions_primary"]),
                "classification": "PHYSICAL_INTERACTION",
                "note": "Only agent_0 has primary body_motion emissions in bounded buffer.",
            },
            {
                "feature": "agent_seeds",
                "values": identity["snapshot_agent_seeds"],
                "classification": "INITIAL_CONDITION",
            },
        ],
    }

    limitations = [
        "User-expected final tick 17730 disagrees with stored final_tick 3077.",
        "session_timeline covers ticks 0–3077 (3077 rows) — full for THIS run's stored length, not 17730.",
        "session_telemetry is bounded (2048 samples, ticks 1035–3077) and appears scoped to observer-selected agent work channels.",
        "structured_events buffer is bounded (400 events total); early signal/collision/cognition events overwritten.",
        "No full-history psychology_observer.jsonl (capabilities.full_history_jsonl=false).",
        "Per-tick cognition (competition detail, predictions) not in timeline — only final snapshot cognition + late events.",
        "PHYSICAL_SIGNAL_EMITTED rows on agent_1 with observer_source_id=agent_0 are duplicate buffer copies, not agent_1 emissions.",
        "snapshot.signal_enabled=false while experimental override experimental_physical_signal=true and signal events exist — flag inconsistency in saved metadata.",
        "Cannot reconstruct missing pre-buffer signal history.",
    ]

    next_experiment = {
        "goal": "Test whether FIELD_* reception changes receiver-accessible observation and action selection.",
        "minimal_design": [
            "Fix identical TwoAgent initial state (same seeds/positions).",
            "Intervention arm: inject controlled FIELD_A deposit near agent_1 at a chosen tick.",
            "Control arm: identical run with physical_signal mode OFF / amplitude 0.",
            "Optional receiver-blind: perception of signal fields disabled for agent_1 only.",
            "Primary readout: agent_1 selected action distribution in ±100 ticks; secondary: observation channel values; tertiary: competition supported_actions.",
        ],
        "do_not_claim_from_this_run": [
            "communication",
            "intent",
            "social cognition",
        ],
    }

    # ---------- write machine series ----------
    _json(OUT / "distance_series.json", {
        "topology": "WRAP_PERIODIC",
        "width": W,
        "height": H,
        "n": len(dist_series),
        "closest": closest,
        "series_downsample_every": 10,
        "series": dist_series[::10],  # bounded artifact
        "series_full_available_in_memory_only": True,
        "note": "Full series computed from timeline; file stores every 10th point to bound size. closest uses full series.",
    })
    # also write compact full min summary
    _json(OUT / "distance_summary.json", {
        "n": len(dist_series),
        "min": closest,
        "mean": sum(r["distance"] for r in dist_series) / len(dist_series) if dist_series else None,
        "p10": sorted(r["distance"] for r in dist_series)[len(dist_series)//10] if dist_series else None,
        "p50": sorted(r["distance"] for r in dist_series)[len(dist_series)//2] if dist_series else None,
        "proximity_episodes_threshold_2": proximity_episodes,
        "contact_ticks_count": len(contacts),
        "contact_episodes": contact_episodes,
    })

    _json(OUT / "analysis_summary.json", {
        "identity": identity,
        "history_coverage": {
            "timeline_ticks": [timeline[0]["tick"], timeline[-1]["tick"]] if timeline else None,
            "timeline_rows": len(timeline),
            "telemetry_ticks": [tel_ticks[0], tel_ticks[-1]] if tel_ticks else None,
            "telemetry_rows": len(tel_ticks),
            "structured_events": len(events),
        },
        "closest_approach": closest,
        "proximity_episode_count": len(proximity_episodes),
        "contact_episode_count": len(contact_episodes),
        "signal_emissions_primary": len(emit_primary),
        "signal_receptions": len(recvs),
        "signal_to_cognition_to_action": signal_to_cognition_to_action,
        "limitations": limitations,
    })
    _json(OUT / "agent_comparison.json", comparison)
    _json(OUT / "signal_analysis.json", {
        "primary_emissions": emit_primary,
        "duplicate_buffer_emissions": emit_duplicate_buffer,
        "receptions": recvs,
        "by_agent": {
            k: {
                "n_emissions_primary": len(v["emissions_primary"]),
                "n_receptions": len(v["receptions"]),
                "n_duplicate_emit_rows": len(v["emissions_duplicate_buffer"]),
                "emission_ticks_primary": [int(e["tick"]) for e in v["emissions_primary"]],
                "reception_ticks": [int(e["tick"]) for e in v["receptions"]],
            }
            for k, v in signal_by_agent.items()
        },
        "pairings": pairs,
        "orphan_receptions_no_emit_in_buffer": orphan_recvs,
        "emissions_vs_proximity": emit_during_prox,
        "reception_windows": reception_windows,
    })
    _json(OUT / "interaction_analysis.json", {
        "contact_episodes": contact_episodes,
        "proximity_episodes_threshold_2": proximity_episodes,
        "closest_approach": closest,
        "body_moved_events_in_buffer": len(body_moved),
        "body_deformed_events_in_buffer": len(deformed),
        "collision_counts_manifest": {
            "agent_0": (run.get("agents") or [{}])[0].get("collision_count"),
            "agent_1": (run.get("agents") or [{}, {}])[1].get("collision_count") if len(run.get("agents") or []) > 1 else None,
        },
        "interpretation_boundary": (
            "Contact=true on timeline and collision_count in manifest indicate physical interaction episodes. "
            "Detailed pre/post velocity at each contact is NOT fully recoverable from bounded events."
        ),
    })
    _json(OUT / "behavioral_regimes.json", {
        "agent_0": agent_summaries["agent_0"]["behavioral_regimes_dominant_action_200tick"],
        "agent_1": agent_summaries["agent_1"]["behavioral_regimes_dominant_action_200tick"],
        "method": "non-overlapping 200-tick dominant selected-action windows, adjacent merge",
        "caveat": "Regime labels are descriptive of selected-action histograms, not strategies.",
    })
    _json(OUT / "causal_candidates.json", {
        "chains": chains,
        "orphan_receptions": orphan_recvs,
        "signal_to_cognition_to_action": signal_to_cognition_to_action,
        "next_experiment": next_experiment,
        "claim_boundary": {
            "DIRECTLY_DEMONSTRATED": [
                "TwoAgentRuntime with independent agent seeds 17/18",
                "Full selected-action timeline for both agents over ticks 0–3077",
                "agent_0 MOVE-dominated selection; agent_1 WAIT-only selection",
                "WRAP_PERIODIC inter-agent distance series from timeline",
                "Bounded PHYSICAL_SIGNAL_EMITTED/RECEIVED events late in run",
            ],
            "SUPPORTED_OBSERVATION": [
                "Contact/proximity episodes occurred",
                "agent_0 body_motion triggered FIELD_A deposits near its body",
                "agent_1 accumulated large path length while selecting WAIT (drift)",
            ],
            "CANDIDATE_RELATIONSHIP": [
                "Low-magnitude FIELD_A at agent_1 may be residual/propagated field from earlier deposits not retained in event buffer",
            ],
            "NOT_DEMONSTRATED": [
                "Communication",
                "Signal→cognition→action causal effect",
                "Social attraction/avoidance",
                "Intentional signaling",
            ],
            "NOT_TESTABLE_FROM_THIS_RUN": [
                "Full early signal history",
                "Per-tick cognition state around most of the run",
                "Counterfactual no-signal control",
            ],
        },
    })

    # ---------- report ----------
    a0 = agent_summaries["agent_0"]
    a1 = agent_summaries["agent_1"]
    report = f"""# Post-run analysis — `{identity['run_id']}`

## 1. Run identity

| Field | Value |
|---|---|
| run_id | `{identity['run_id']}` |
| seed | {identity['seed']} |
| runtime | {identity['runtime_type']} |
| generation | {identity['generation']} |
| final_tick (stored) | **{identity['final_tick']}** |
| user-expected tick | {EXPECTED_TICK} |
| termination | {identity['termination_reason']} |
| agent_seeds | {identity['snapshot_agent_seeds']} |
| starts | {identity['starts']} |

**TICK DISCREPANCY:** User query expected final tick **17730**. Stored `run.json` / timeline / snapshot all agree on **{final_tick}**. Analysis uses **{final_tick}** only.

Capabilities: `{json.dumps(identity['capabilities'])}`

Experimental overrides present (non-canonical Tiktaalik): signal + many research cognition flags (see run.json).

## 2. Data actually available

| Artifact | Coverage |
|---|---|
| run.json | identity, final agent summaries, capabilities |
| session_timeline.jsonl | **{len(timeline)}** rows, ticks **{timeline[0]['tick']}–{timeline[-1]['tick']}**, both bodies + actions + contact |
| session_telemetry.json | **{len(tel_ticks)}** samples, ticks **{tel_ticks[0] if tel_ticks else None}–{tel_ticks[-1] if tel_ticks else None}** (bounded; likely selected-agent work) |
| structured_events.json | **{len(events)}** events (bounded ring; late window) |
| physical_system_snapshot.json | final TwoAgent snapshot (~193MB); light extract used |

No `psychology_observer.jsonl`. No full-history cognition JSONL.

## 3. Agent 0 summary

- Seed **{a0['agent_seed']}**; start ≈ ({a0['initial_position']['x']:.3f},{a0['initial_position']['y']:.3f}); end ≈ ({a0['final_position']['x']:.3f},{a0['final_position']['y']:.3f})
- Selected actions: `{a0['selected_action_counts']}`
- Path length (wrap): **{a0['path_length_wrap']:.3f}**
- WAIT-path fraction: **{a0['wait_drift_fraction_of_path']}**; MOVE-path fraction: **{a0['move_path_fraction']}**
- Final lock: `{a0['final_selection_source_manifest']}` / `{a0['final_selection_reason_manifest']}` supported `{a0['final_supported_actions_manifest']}`
- Longest episodes (top): `{a0['longest_action_episodes'][:3]}`

**Interpretation:** Most travel coincides with **MOVE:*** selections (especially MOVE:N), not WAIT. This is selected locomotor action plus realization — still not “intent,” but it is not WAIT-drift.

## 4. Agent 1 summary

- Seed **{a1['agent_seed']}**; start ≈ ({a1['initial_position']['x']:.3f},{a1['initial_position']['y']:.3f}); end ≈ ({a1['final_position']['x']:.3f},{a1['final_position']['y']:.3f})
- Selected actions: `{a1['selected_action_counts']}` — **WAIT only** for all recorded ticks with action
- Path length (wrap): **{a1['path_length_wrap']:.3f}**
- WAIT-path fraction: **{a1['wait_drift_fraction_of_path']}** (≈1.0)
- Final lock: WAIT / SINGLE_SUPPORTED
- Manifest collision_count: {a1['collision_count_manifest']}

**Interpretation:** Apparent motion of agent_1 is **PASSIVE PHYSICAL DISPLACEMENT while selecting WAIT** (environment/inertia/contact), not MOVE realization.

## 5. Agent comparison

| Metric | agent_0 | agent_1 |
|---|---|---|
| Dominant selected | MOVE:N | WAIT |
| MOVE selected ticks | {sum(v for k,v in a0['selected_action_counts'].items() if str(k).startswith('MOVE'))} | 0 |
| WAIT selected ticks | {a0['selected_action_counts'].get('WAIT',0)} | {a1['selected_action_counts'].get('WAIT',0)} |
| Path length | {a0['path_length_wrap']:.2f} | {a1['path_length_wrap']:.2f} |
| WAIT-drift fraction | {a0['wait_drift_fraction_of_path']} | {a1['wait_drift_fraction_of_path']} |

Asymmetry class: primarily **HISTORY_DEPENDENT** action lock-in (different seeds → different early endogenous samples → different SINGLE_SUPPORTED attractors), plus **LOCAL_ENVIRONMENT** / contact effects on WAIT-drift.

## 6. Physical interaction

- Contact episodes (timeline `contact=true`): **{len(contact_episodes)}** → `{contact_episodes[:10]}{'...' if len(contact_episodes)>10 else ''}`
- Manifest collision_count: 14 each
- Closest approach: tick {closest['tick'] if closest else None}, distance **{closest['distance'] if closest else None:.4f}** (wrap)

Detailed per-contact Δv pre/post: **NOT fully recoverable** from bounded event buffer.

## 7. Signal emission / reception

Primary emissions (deduced): **{len(emit_primary)}** — all `observer_source_id=agent_0`, trigger=`body_motion`, channel A, ticks {[e['tick'] for e in emit_primary]}.

Receptions: **{len(recvs)}**
- agent_0: self-reception after own deposits (t=3071–3077)
- agent_1: low-magnitude FIELD_A at t=3059–3062 (**no matching emit in buffer**)

Duplicate EMITTED rows on agent_1 with `observer_source_id=agent_0`: **buffer copies**, not agent_1 emissions.

## 8. Signal pairing

See `signal_analysis.json` → `pairings`.
- Self pairs agent_0→agent_0: **DIRECTLY_RECORDED**
- Cross-agent pairs in buffer: **none with primary emit + agent_1 recv in order**
- agent_1 receptions: **UNRESOLVED** vs emitters (history truncated)

## 9. Proximity analysis

Threshold distance < 2.0: **{len(proximity_episodes)}** episodes (see `distance_summary.json`).
Late primary emissions occur when agents are **not** necessarily co-located (agent_0 near y≈25, agent_1 near y≈2).

## 10. Behavioral regime transitions

Method: 200-tick dominant selected-action windows.
- agent_0: transitions among WAIT-heavy early window → MOVE:N dominance (see `behavioral_regimes.json`)
- agent_1: single WAIT regime entire recorded history

These are **selected-action histogram regimes**, not strategies.

## 11. Cognition / action relationships

From final manifest + late events:
- Both agents: `PROSPECTIVE_SCENARIO` / `SINGLE_SUPPORTED`
- agent_0 supported {{MOVE:N}}; agent_1 supported {{WAIT}}
- Per-tick cognition around signal times: **NOT_RECORDED** in timeline

## 12. Candidate inter-agent causal chains

No complete OBSERVED chain:

emit → receive → cognition change → action change → consequence

Missing links are cognition + action-change for agent_1 (action never leaves WAIT).

## 13. Signal → cognition → action assessment

| Direction | Status |
|---|---|
| agent_0 → agent_1 | **NO_EVIDENCE** (for action change); reception without paired emit in buffer |
| agent_1 → agent_0 | **NO_EVIDENCE** (no primary agent_1 emission) |
| Overall | **CAUSAL_EFFECT_NOT_DEMONSTRATED** |

## 14. Alternative explanations

1. agent_1 WAIT lock from early endogenous sampling (seed 18) — documented MM mechanism.
2. agent_1 displacement = environmental/contact drift under WAIT.
3. agent_1 FIELD_A receptions = residual/propagated field from earlier overwritten deposits, or distant weak field — **not demonstrated**.
4. Visual impression of mutual “signaling behavior” conflates physical field events with communication.

## 15. Data limitations

{chr(10).join('- '+x for x in limitations)}

## 16. Scientific claim boundary

See `causal_candidates.json` → `claim_boundary`.

## 17. Minimal next experiment

{json.dumps(next_experiment, indent=2)}
"""
    _md(OUT / "analysis_report.md", report)

    # terminal summary fields returned via print in __main__
    summary = {
        "RUN": identity["run_id"],
        "RUN_VALIDATION": {
            "expected_tick": EXPECTED_TICK,
            "stored_tick": final_tick,
            "match": final_tick == EXPECTED_TICK,
            "termination": identity["termination_reason"],
        },
        "AVAILABLE_HISTORY": {
            "timeline": f"0–{final_tick} ({len(timeline)} rows)",
            "telemetry": f"{tel_ticks[0]}–{tel_ticks[-1]}" if tel_ticks else None,
            "events": len(events),
        },
        "AGENT_0": a0["selected_action_counts"],
        "AGENT_1": a1["selected_action_counts"],
        "WAIT_DRIFT_FRACTION": {
            "agent_0": a0["wait_drift_fraction_of_path"],
            "agent_1": a1["wait_drift_fraction_of_path"],
        },
        "SIGNAL_EMISSIONS_PRIMARY": len(emit_primary),
        "SIGNAL_RECEPTIONS": len(recvs),
        "CLOSEST_APPROACH": closest,
        "PROXIMITY_EPISODES": len(proximity_episodes),
        "PHYSICAL_INTERACTIONS_CONTACT_EPISODES": len(contact_episodes),
        "SIGNAL_TO_COGNITION_TO_ACTION": signal_to_cognition_to_action["overall"],
        "OUT": str(OUT),
    }
    _json(OUT / "_terminal_summary.json", summary)
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
