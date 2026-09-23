"""Sensorimotor consequence analysis — trend persistence/reversal; receding-while-watching.

All labels are operational. No seeking / recognition / intent.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, asdict, field
from typing import Any

from .geometry import approach_decomposition, orienting_error, toroidal_distance
from .tick_stories import TickStory


WINDOWS = {
    "EARLY": (1, 1000),
    "MIDDLE": (1001, 2334),
    "LATE": (2335, 10**9),
}

TARGET_INTERVALS = [
    (1075, 1075),
    (1905, 1905),
    (1907, 1923),
    (1925, 1939),
    (2125, 2127),
    (2212, 2223),
    (3254, 3259),
    (3304, 3304),
    (3309, 3313),
    (3250, 3315),  # focus region
]


def _loco(s: TickStory) -> str:
    return str(((s.motor or {}).get("components") or {}).get("locomotion") or "WAIT")


def _is_move(loco: str) -> bool:
    u = str(loco).upper()
    return u.startswith("MOVE") or u not in ("WAIT", "NONE", "")


def _optical_from_story(s: TickStory) -> dict[str, Any]:
    for c in s.external_context:
        if c.get("kind") == "VISION_EXPOSURE":
            return c
    return {}


def _geom_peer(s: TickStory, other: str | None = None) -> dict[str, Any] | None:
    for d in s.derived_changes:
        if d.get("kind") != "RELATIVE_GEOMETRY":
            continue
        if other and d.get("other_agent") != other:
            continue
        return d
    return None


def _foreign_total_from_ctx(s: TickStory) -> float | None:
    for c in s.external_context:
        if c.get("kind") == "VISION_EXPOSURE" and c.get("foreign_body_total") is not None:
            try:
                return float(c["foreign_body_total"])
            except (TypeError, ValueError):
                return None
    return None


def enrich_optical_on_stories(stories: list[TickStory], timeline: dict[tuple[str, int], dict[str, Any]]) -> None:
    """Attach Observer optical magnitudes into VISION_EXPOSURE context (GT provenance tagged)."""
    for s in stories:
        row = timeline.get((s.cognitive_agent_id, s.tick))
        if not row:
            continue
        vo = row.get("vision_optical") or {}
        for c in s.external_context:
            if c.get("kind") != "VISION_EXPOSURE":
                continue
            c["foreign_body_total"] = vo.get("foreign_body_total")
            c["foreign_body_contribution"] = vo.get("foreign_body_contribution")
            c["final_exo"] = vo.get("final_exo")
            c["exo_without_foreign_bodies"] = vo.get("exo_without_foreign_bodies")
            c["neighbors_optical"] = vo.get("neighbors_optical")
            c["source_bodies_gt"] = vo.get("source_bodies_gt")
            c["identity_layer"] = vo.get("identity_layer")
            c["provenance"] = "OBSERVER_GT_OPTICAL"


@dataclass
class SensorimotorStep:
    agent: str
    tick: int
    peer: str | None
    visual_exposure: bool
    distance_t: float | None
    distance_t1: float | None
    distance_delta: float | None
    focal_contribution: float | None
    source_contribution: float | None
    dominant_mover: str | None
    bearing_error_deg: float | None
    bearing_error_t1_deg: float | None
    bearing_error_delta_deg: float | None
    optical_total: float | None
    optical_total_t1: float | None
    optical_delta: float | None
    exo_delta: dict[str, float] | None
    motor_t: str | None
    motor_t1: str | None
    loco_t: str | None
    loco_t1: str | None
    decision_path_t: str | None
    decision_path_t1: str | None
    trend_class: str  # INCREASE_DISTANCE | DECREASE_DISTANCE | STABLE | UNKNOWN
    next_response: str  # CONTINUE | REVERSE | ORTHOGONAL | WAIT | NECK_ONLY | OSC_ONLY | OTHER
    observation_id: str | None = None
    decision_id: str | None = None
    motor_id: str | None = None
    consequence_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _exo_map(s: TickStory) -> dict[str, float]:
    out = {}
    for c in s.observation_components:
        k = str(c.get("key") or "")
        if k.startswith("exo_"):
            try:
                out[k] = float(c.get("value") or 0)
            except (TypeError, ValueError):
                pass
    return out


def _classify_next_response(s0: TickStory, s1: TickStory, dist_delta: float | None) -> str:
    loco0 = _loco(s0)
    loco1 = _loco(s1)
    c0 = (s0.motor or {}).get("components") or {}
    c1 = (s1.motor or {}).get("components") or {}
    if not _is_move(loco1):
        # neck or osc only?
        neck_chg = str(c1.get("neck") or "") != str(c0.get("neck") or "") and str(c1.get("neck") or "").upper() not in ("NECK_HOLD", "HOLD", "")
        osc1 = c1.get("oscillator") or {}
        osc_on = isinstance(osc1, dict) and any(osc1.values())
        if neck_chg and not _is_move(loco1):
            return "NECK_ONLY"
        if osc_on and not _is_move(loco1):
            return "OSC_ONLY"
        return "WAIT"
    # compare locomotion direction tokens
    if loco0 == loco1:
        return "CONTINUE"
    # reverse heuristic: opposite cardinal if both MOVE
    opposites = {("MOVE:N", "MOVE:S"), ("MOVE:S", "MOVE:N"), ("MOVE:E", "MOVE:W"), ("MOVE:W", "MOVE:E")}
    pair = (loco0 if loco0.startswith("MOVE") else loco0, loco1 if loco1.startswith("MOVE") else loco1)
    if pair in opposites or (pair[1], pair[0]) in opposites:
        return "REVERSE"
    # if distance trend reverses at next step via geometry on s1
    return "ORTHOGONAL" if loco0 != loco1 else "CONTINUE"


def build_sensorimotor_steps(
    stories: list[TickStory],
    *,
    width: float = 32.0,
    height: float = 32.0,
) -> list[SensorimotorStep]:
    by_agent: dict[str, list[TickStory]] = defaultdict(list)
    for s in stories:
        by_agent[s.cognitive_agent_id].append(s)
    for a in by_agent:
        by_agent[a].sort(key=lambda x: x.tick)

    agents = sorted(by_agent.keys())
    steps: list[SensorimotorStep] = []

    for agent, seq in by_agent.items():
        peers = [a for a in agents if a != agent]
        peer = peers[0] if peers else None
        by_tick = {s.tick: s for s in seq}
        for s in seq:
            s1 = by_tick.get(s.tick + 1)
            if s1 is None:
                continue
            g = _geom_peer(s, peer)
            g1 = _geom_peer(s1, peer)
            ap = (g or {}).get("approach") or {}
            ori = (g or {}).get("orienting") or {}
            ori1 = (g1 or {}).get("orienting") or {}
            d0 = ap.get("distance_t") if ap else (g or {}).get("toroidal_distance")
            d1 = ap.get("distance_t1") if ap else (g1 or {}).get("toroidal_distance")
            dd = ap.get("delta_distance")
            if dd is None and d0 is not None and d1 is not None:
                dd = float(d1) - float(d0)
            opt0 = _foreign_total_from_ctx(s)
            opt1 = _foreign_total_from_ctx(s1)
            od = None
            if opt0 is not None and opt1 is not None:
                od = opt1 - opt0
            e0 = _exo_map(s)
            e1 = _exo_map(s1)
            exo_delta = {k: e1.get(k, 0.0) - e0.get(k, 0.0) for k in set(e0) | set(e1)} if e0 or e1 else None
            be0 = ori.get("abs_angular_error_deg")
            be1 = ori1.get("abs_angular_error_deg")
            bed = None
            if be0 is not None and be1 is not None:
                bed = float(be1) - float(be0)
            if dd is None:
                trend = "UNKNOWN"
            elif dd > 0.05:
                trend = "INCREASE_DISTANCE"
            elif dd < -0.05:
                trend = "DECREASE_DISTANCE"
            else:
                trend = "STABLE"
            vis = any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context)
            resp = _classify_next_response(s, s1, dd)
            steps.append(SensorimotorStep(
                agent=agent,
                tick=s.tick,
                peer=peer,
                visual_exposure=vis,
                distance_t=float(d0) if d0 is not None else None,
                distance_t1=float(d1) if d1 is not None else None,
                distance_delta=float(dd) if dd is not None else None,
                focal_contribution=ap.get("agent_contribution"),
                source_contribution=ap.get("source_contribution"),
                dominant_mover=ap.get("dominant_mover"),
                bearing_error_deg=float(be0) if be0 is not None else None,
                bearing_error_t1_deg=float(be1) if be1 is not None else None,
                bearing_error_delta_deg=bed,
                optical_total=opt0,
                optical_total_t1=opt1,
                optical_delta=od,
                exo_delta=exo_delta,
                motor_t=s.composite_motor_summary,
                motor_t1=s1.composite_motor_summary,
                loco_t=_loco(s),
                loco_t1=_loco(s1),
                decision_path_t=(s.decision or {}).get("selection_path"),
                decision_path_t1=(s1.decision or {}).get("selection_path"),
                trend_class=trend,
                next_response=resp,
                observation_id=s.observation_id,
                decision_id=s.decision_id,
                motor_id=s.motor_id,
                consequence_id=s.consequence_id,
            ))
    return steps


def detect_motor_reversals(stories: list[TickStory]) -> list[dict[str, Any]]:
    by_agent: dict[str, list[TickStory]] = defaultdict(list)
    for s in stories:
        by_agent[s.cognitive_agent_id].append(s)
    out = []
    opposites = {("MOVE:N", "MOVE:S"), ("MOVE:S", "MOVE:N"), ("MOVE:E", "MOVE:W"), ("MOVE:W", "MOVE:E")}
    for agent, seq in by_agent.items():
        seq = sorted(seq, key=lambda x: x.tick)
        for i in range(1, len(seq)):
            if seq[i].tick != seq[i - 1].tick + 1:
                continue
            a, b = _loco(seq[i - 1]), _loco(seq[i])
            if (a, b) in opposites:
                out.append({
                    "episode_type": "MOTOR_REVERSAL",
                    "agent": agent,
                    "start_tick": seq[i - 1].tick,
                    "end_tick": seq[i].tick,
                    "from_loco": a,
                    "to_loco": b,
                    "motor_from": seq[i - 1].composite_motor_summary,
                    "motor_to": seq[i].composite_motor_summary,
                    "visual_at_from": any(c.get("kind") == "VISION_EXPOSURE" for c in seq[i - 1].external_context),
                    "layer": "OBSERVED",
                })
    return out


def detect_sensorimotor_trend_reversals(steps: list[SensorimotorStep], *, k: int = 3) -> list[dict[str, Any]]:
    """Candidate SENSORIMOTOR_TREND_REVERSAL: visual exposure + geometric trend + later reverse response."""
    by_agent: dict[str, list[SensorimotorStep]] = defaultdict(list)
    for st in steps:
        by_agent[st.agent].append(st)
    out = []
    for agent, seq in by_agent.items():
        seq = sorted(seq, key=lambda x: x.tick)
        for i, st in enumerate(seq):
            if not st.visual_exposure:
                continue
            if st.trend_class not in ("INCREASE_DISTANCE", "DECREASE_DISTANCE"):
                continue
            # look ahead for REVERSE response or opposite trend
            reversed_at = None
            strength = "WEAK"
            for j in range(i + 1, min(i + 1 + k, len(seq))):
                nxt = seq[j]
                if nxt.next_response == "REVERSE" or (
                    st.trend_class == "INCREASE_DISTANCE" and nxt.trend_class == "DECREASE_DISTANCE"
                ) or (
                    st.trend_class == "DECREASE_DISTANCE" and nxt.trend_class == "INCREASE_DISTANCE"
                ):
                    reversed_at = nxt.tick
                    if st.optical_delta is not None or st.bearing_error_delta_deg is not None:
                        strength = "MODERATE"
                    break
            if reversed_at is None:
                continue
            out.append({
                "episode_type": "SENSORIMOTOR_TREND_REVERSAL",
                "agent": agent,
                "peer": st.peer,
                "start_tick": st.tick,
                "end_tick": reversed_at,
                "initial_trend": st.trend_class,
                "distance_delta_t": st.distance_delta,
                "optical_delta_t": st.optical_delta,
                "bearing_error_delta_t": st.bearing_error_delta_deg,
                "next_response": st.next_response,
                "evidence_strength": strength,
                "note": "Operational trend reversal after sensory exposure — not proven intentional correction",
                "layer": "ASSOCIATED",
                "causation": "NOT_ESTABLISHED",
            })
    return out


def find_receding_while_watching(
    steps: list[SensorimotorStep],
    stories_by_key: dict[tuple[str, int], TickStory],
    *,
    min_run: int = 2,
    bearing_err_max_deg: float = 90.0,
) -> list[dict[str, Any]]:
    """Search: visual exposure + distance increasing + optical decrease OR error not improving + head still roughly toward source + loco continues away."""
    by_agent: dict[str, list[SensorimotorStep]] = defaultdict(list)
    for st in steps:
        by_agent[st.agent].append(st)
    episodes = []
    for agent, seq in by_agent.items():
        seq = sorted(seq, key=lambda x: x.tick)
        i = 0
        while i < len(seq):
            st = seq[i]
            cond = (
                st.visual_exposure
                and st.distance_delta is not None
                and st.distance_delta > 0.05
                and _is_move(st.loco_t or "WAIT")
                and (st.bearing_error_deg is None or st.bearing_error_deg <= bearing_err_max_deg)
                and (
                    (st.optical_delta is not None and st.optical_delta < -1e-4)
                    or (st.bearing_error_delta_deg is not None and st.bearing_error_delta_deg >= 0)
                    or True  # allow distance-increase under exposure even if optical flat (clipped exo)
                )
            )
            # tighten: require visual + distance increase + (optical down OR bearing error not decreasing)
            tight = (
                st.visual_exposure
                and st.distance_delta is not None
                and st.distance_delta > 0.05
                and _is_move(st.loco_t or "WAIT")
                and st.bearing_error_deg is not None
                and st.bearing_error_deg <= bearing_err_max_deg
                and (
                    (st.optical_delta is not None and st.optical_delta <= 0)
                    or (st.bearing_error_delta_deg is not None and st.bearing_error_delta_deg >= -1.0)
                )
            )
            if not tight:
                i += 1
                continue
            j = i + 1
            while j < len(seq) and seq[j].tick == seq[j - 1].tick + 1:
                stj = seq[j]
                ok = (
                    stj.visual_exposure
                    and stj.distance_delta is not None
                    and stj.distance_delta > 0.02
                    and _is_move(stj.loco_t or "WAIT")
                    and stj.bearing_error_deg is not None
                    and stj.bearing_error_deg <= bearing_err_max_deg
                )
                if not ok:
                    break
                j += 1
            length = j - i
            if length >= min_run:
                first, last = seq[i], seq[j - 1]
                # look for later loco reverse
                reversed_at = None
                for k in range(j, min(j + 8, len(seq))):
                    if seq[k].next_response == "REVERSE" or (
                        seq[k].loco_t and first.loco_t and (seq[k].loco_t, first.loco_t) in {
                            ("MOVE:N", "MOVE:S"), ("MOVE:S", "MOVE:N"), ("MOVE:E", "MOVE:W"), ("MOVE:W", "MOVE:E")
                        }
                    ) or (seq[k].distance_delta is not None and seq[k].distance_delta < -0.05):
                        reversed_at = seq[k].tick
                        break
                # observation before reversal
                pre_obs = None
                if reversed_at is not None:
                    s_rev = stories_by_key.get((agent, reversed_at))
                    if s_rev:
                        pre_obs = {
                            "exo": _exo_map(s_rev),
                            "field_A": next((c.get("value") for c in s_rev.observation_components if c.get("key") == "local.FIELD_A"), None),
                            "decision": (s_rev.decision or {}).get("selected_action_legacy"),
                            "motor": s_rev.composite_motor_summary,
                        }
                d0 = first.distance_t
                d1 = last.distance_t1 if last.distance_t1 is not None else last.distance_t
                episodes.append({
                    "phenomenon": "RECEDING_WHILE_WATCHING",
                    "layer": "DERIVED",
                    "agent": agent,
                    "peer": first.peer,
                    "start_tick": first.tick,
                    "end_tick": last.tick,
                    "ticks": length,
                    "initial_distance": d0,
                    "final_distance": d1,
                    "distance_delta": (None if d0 is None or d1 is None else float(d1) - float(d0)),
                    "bearing_error_start_deg": first.bearing_error_deg,
                    "bearing_error_end_deg": last.bearing_error_deg,
                    "optical_start": first.optical_total,
                    "optical_end": last.optical_total_t1,
                    "optical_trend": None if first.optical_total is None or last.optical_total_t1 is None else float(last.optical_total_t1) - float(first.optical_total),
                    "loco_sequence": [seq[t].loco_t for t in range(i, j)],
                    "motor_sequence": [seq[t].motor_t for t in range(i, j)],
                    "decision_paths": [seq[t].decision_path_t for t in range(i, j)],
                    "locomotion_reversed_at": reversed_at,
                    "observation_at_reversal": pre_obs,
                    "interpretation_boundary": {
                        "visual_context_recorded": True,
                        "specific_optical_caused_decision": "NOT_ESTABLISHED",
                        "recognition": "NOT_ESTABLISHED",
                        "intentional_withdrawal": "NOT_ESTABLISHED",
                    },
                })
            i = max(j, i + 1)
    return episodes


def summarize_steps(steps: list[SensorimotorStep]) -> dict[str, Any]:
    by_agent: dict[str, list[SensorimotorStep]] = defaultdict(list)
    for st in steps:
        by_agent[st.agent].append(st)
    out: dict[str, Any] = {"agents": {}, "global": {}}
    all_vis = [st for st in steps if st.visual_exposure]
    resp = Counter(st.next_response for st in all_vis)
    trends = Counter(st.trend_class for st in all_vis)
    # When distance increased under vision, how often next REVERSE?
    inc = [st for st in all_vis if st.trend_class == "INCREASE_DISTANCE"]
    dec = [st for st in all_vis if st.trend_class == "DECREASE_DISTANCE"]
    out["global"] = {
        "visual_steps": len(all_vis),
        "response_given_visual": dict(resp),
        "trend_given_visual": dict(trends),
        "after_distance_increase": {
            "n": len(inc),
            "next_response": dict(Counter(st.next_response for st in inc)),
        },
        "after_distance_decrease": {
            "n": len(dec),
            "next_response": dict(Counter(st.next_response for st in dec)),
        },
    }
    for agent, seq in by_agent.items():
        vis = [st for st in seq if st.visual_exposure]
        closure = [st for st in vis if st.distance_delta is not None and st.distance_delta < -0.05]
        focal_dom = sum(1 for st in closure if st.dominant_mover == "AGENT")
        src_dom = sum(1 for st in closure if st.dominant_mover == "SOURCE")
        out["agents"][agent] = {
            "steps": len(seq),
            "visual_steps": len(vis),
            "closure_steps_under_vision": len(closure),
            "closure_focal_dominant": focal_dom,
            "closure_source_dominant": src_dom,
            "response_under_vision": dict(Counter(st.next_response for st in vis)),
            "mean_bearing_error_under_vision": (
                round(sum(st.bearing_error_deg for st in vis if st.bearing_error_deg is not None) /
                      max(1, sum(1 for st in vis if st.bearing_error_deg is not None)), 2)
                if any(st.bearing_error_deg is not None for st in vis) else None
            ),
        }
    return out


def longitudinal_comparison(stories: list[TickStory], steps: list[SensorimotorStep], latest_tick: int) -> dict[str, Any]:
    windows = {
        "EARLY": (1, min(1000, latest_tick)),
        "MIDDLE": (1001, min(2334, latest_tick)),
        "LATE": (2335, latest_tick),
    }
    # drop empty
    windows = {k: v for k, v in windows.items() if v[0] <= v[1]}
    result: dict[str, Any] = {"label": "LONGITUDINAL_CHANGE", "note": "Not labeled as learning", "windows": {}}
    for name, (a, b) in windows.items():
        ss = [s for s in stories if a <= s.tick <= b]
        st = [x for x in steps if a <= x.tick <= b]
        by_agent: dict[str, Any] = {}
        agents = sorted({s.cognitive_agent_id for s in ss})
        for agent in agents:
            sag = [s for s in ss if s.cognitive_agent_id == agent]
            stag = [x for x in st if x.agent == agent]
            vis = sum(1 for s in sag if any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context))
            sig = sum(1 for s in sag if any(c.get("kind") == "SIGNAL_RECEPTION" for c in s.external_context))
            contact = sum(1 for s in sag if any(c.get("kind") == "CONTACT" for c in s.external_context))
            wait = sum(1 for s in sag if not _is_move(_loco(s)))
            neck = sum(1 for s in sag if str(((s.motor or {}).get("components") or {}).get("neck") or "").upper() not in ("", "NECK_HOLD", "HOLD", "NONE"))
            rev = sum(1 for x in stag if x.next_response == "REVERSE")
            dists = [x.distance_t for x in stag if x.distance_t is not None]
            by_agent[agent] = {
                "n_ticks": len(sag),
                "visual_exposure_ticks": vis,
                "signal_reception_ticks": sig,
                "contact_ticks": contact,
                "wait_p": round(wait / max(1, len(sag)), 4),
                "neck_control_ticks": neck,
                "reverse_responses": rev,
                "mean_distance": round(sum(dists) / len(dists), 3) if dists else None,
                "decision_modes": dict(Counter(str((s.decision or {}).get("selection_mode")) for s in sag)),
            }
        result["windows"][name] = {"range": [a, b], "agents": by_agent}
    return result


def explain_visual_asymmetry(stories: list[TickStory], steps: list[SensorimotorStep]) -> dict[str, Any]:
    """Geometric explanation candidates for agent_0 vs agent_1 visual exposure asymmetry."""
    agents = sorted({s.cognitive_agent_id for s in stories})
    stats = {}
    for agent in agents:
        sag = [s for s in stories if s.cognitive_agent_id == agent]
        vis_ticks = [s for s in sag if any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context)]
        errs = []
        dists = []
        for s in vis_ticks:
            g = _geom_peer(s)
            if not g:
                continue
            ori = g.get("orienting") or {}
            if ori.get("abs_angular_error_deg") is not None:
                errs.append(float(ori["abs_angular_error_deg"]))
            if g.get("toroidal_distance") is not None:
                dists.append(float(g["toroidal_distance"]))
        near_ticks = set()
        for s in sag:
            g = _geom_peer(s)
            if g and g.get("toroidal_distance") is not None and float(g["toroidal_distance"]) <= 3.5:
                near_ticks.add(s.tick)
            if any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context):
                near_ticks.add(s.tick)
        near = len(near_ticks)
        stats[agent] = {
            "visual_exposure_ticks": len(vis_ticks),
            "ticks_within_vision_radius_3": near,
            "mean_bearing_error_during_exposure": round(sum(errs) / len(errs), 2) if errs else None,
            "mean_distance_during_exposure": round(sum(dists) / len(dists), 3) if dists else None,
            "exposure_as_fraction_of_near": round(len(vis_ticks) / max(1, near), 4),
        }
    # hypothesis ranking by numbers only
    explanation = []
    if len(stats) >= 2:
        a0, a1 = agents[0], agents[1]
        if stats[a0]["ticks_within_vision_radius_3"] != stats[a1]["ticks_within_vision_radius_3"]:
            explanation.append(
                "DIFFERENT_TIME_WITHIN_VISION_RADIUS: agents spent unequal ticks within toroidal distance ≤3"
            )
        e0 = stats[a0]["mean_bearing_error_during_exposure"]
        e1 = stats[a1]["mean_bearing_error_during_exposure"]
        if e0 is not None and e1 is not None and abs(e0 - e1) > 15:
            explanation.append("DIFFERENT_HEAD_ALIGNMENT: mean sensor-bearing error during exposure differs")
        explanation.append(
            "Exposure requires Observer body_exposure (FOV/radius/illumination), not mere proximity — "
            "near-ticks vs exposure-ticks ratio is the geometric diagnostic."
        )
    return {
        "layer": "DERIVED",
        "label": "VISUAL_EXPOSURE_ASYMMETRY",
        "per_agent": stats,
        "candidate_explanations": explanation,
        "not_established": ["social preference", "recognition superiority"],
    }


def reconstruct_interval(
    stories: list[TickStory],
    steps: list[SensorimotorStep],
    start: int,
    end: int,
) -> dict[str, Any]:
    ss = [s for s in stories if start <= s.tick <= end]
    st = [x for x in steps if start <= x.tick <= end]
    by_agent: dict[str, Any] = defaultdict(list)
    for s in sorted(ss, key=lambda x: (x.tick, x.cognitive_agent_id)):
        g = _geom_peer(s)
        by_agent[s.cognitive_agent_id].append({
            "tick": s.tick,
            "motor": s.composite_motor_summary,
            "decision": (s.decision or {}).get("selected_action_legacy"),
            "mode": (s.decision or {}).get("selection_mode"),
            "distance": (g or {}).get("toroidal_distance"),
            "bearing_error_deg": ((g or {}).get("orienting") or {}).get("abs_angular_error_deg"),
            "dominant_mover": ((g or {}).get("approach") or {}).get("dominant_mover"),
            "distance_delta": ((g or {}).get("approach") or {}).get("delta_distance"),
            "visual": any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context),
            "signal": any(c.get("kind") == "SIGNAL_RECEPTION" for c in s.external_context),
            "contact": any(c.get("kind") == "CONTACT" for c in s.external_context),
            "observation_id": s.observation_id,
            "decision_id": s.decision_id,
            "motor_id": s.motor_id,
            "consequence_id": s.consequence_id,
        })
    # approach history before start (up to 200 ticks)
    pre = [s for s in stories if start - 200 <= s.tick < start]
    pre_dist = []
    for s in pre:
        if s.cognitive_agent_id != (sorted(by_agent.keys())[0] if by_agent else ""):
            continue
        g = _geom_peer(s)
        if g and g.get("toroidal_distance") is not None:
            pre_dist.append((s.tick, float(g["toroidal_distance"])))
    return {
        "interval": [start, end],
        "agents": dict(by_agent),
        "sensorimotor_steps_in_interval": [s.to_dict() for s in st[:80]],
        "approach_history_200_pre": {
            "distance_trace_agent0_or_first": pre_dist[-40:],  # last 40 points
            "note": "Distance before interval — do not start story at contact",
        },
    }
