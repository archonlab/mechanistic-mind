"""Analyzer 1.2 — Beta 3.1 spatial / optical vision long-run analysis.

Streams V3 JSONL. Does not regenerate sensors from WORLD. No causal claims.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

EPS = 1e-6
SAT = 0.995
Q = 2  # occupancy quantization decimals
MAX_STATES = 2048
MAX_EXAMPLES = 8
MAX_MOTIFS = 48
MAX_REVERSALS = 40
MAX_PAIRS = 24

LEGACY_EXO = ("exo_0", "exo_1", "exo_2")
SURFACE = tuple(f"surface_c{c}_{b}" for c in range(3) for b in range(3))
SPATIAL_EXO = tuple(f"spatial_exo_a{k}" for k in range(5))
SPATIAL_SURFACE = tuple(f"spatial_surface_c{c}_a{k}" for c in range(3) for k in range(5))
ALL_VISUAL = LEGACY_EXO + SURFACE + SPATIAL_EXO + SPATIAL_SURFACE
NONVISUAL_MATCH = ("vest_0", "vest_1", "prop_neck_0", "prop_neck_1", "local.FIELD_A", "local.FIELD_B")

EVIDENCE_MATRIX: list[dict[str, str]] = [
    {"field": "exo_0/1/2", "class": "AGENT_ACCESSIBLE",
     "historical": "ObservationReceipt.accessible when vision ON"},
    {"field": "surface_c*", "class": "AGENT_ACCESSIBLE",
     "historical": "ObservationReceipt when surface discrimination LOW/RICH"},
    {"field": "spatial_exo_a*", "class": "AGENT_ACCESSIBLE",
     "historical": "ObservationReceipt when Spatial Vision ≠ LEGACY"},
    {"field": "spatial_surface_c*", "class": "AGENT_ACCESSIBLE",
     "historical": "ObservationReceipt when Spatial Vision ≠ LEGACY and surface ON"},
    {"field": "local.FIELD_A/B", "class": "AGENT_ACCESSIBLE",
     "historical": "ObservationReceipt + PHYSICAL_SIGNAL_RECEIVED events"},
    {"field": "vestibular vest_*", "class": "AGENT_ACCESSIBLE", "historical": "ObservationReceipt"},
    {"field": "neck proprioception prop_neck_*", "class": "AGENT_ACCESSIBLE", "historical": "ObservationReceipt"},
    {"field": "selected action / composite motor", "class": "COGNITIVE_INTERNAL",
     "historical": "DecisionReceipt + MotorReceipt"},
    {"field": "candidate actions / PSC metadata", "class": "COGNITIVE_INTERNAL",
     "historical": "DecisionReceipt candidate_count, selection_path, selected_candidate_id; full PSC maps not retained in compact stories"},
    {"field": "predicted consequence / SMC deltas", "class": "COGNITIVE_INTERNAL",
     "historical": "DecisionReceipt.sensorimotor_consequence compact (≤12 predictions, ≤48 delta keys)"},
    {"field": "PE / compression internals", "class": "COGNITIVE_INTERNAL",
     "historical": "NOT_RECORDED as per-tick class IDs in V3 CORE DecisionReceipt; PE_VISUAL_FORENSICS=PARTIAL"},
    {"field": "prospective composition", "class": "COGNITIVE_INTERNAL",
     "historical": "DecisionReceipt historical_sensorimotor_selection + selection_mode; continuation maps not fully dumped"},
    {"field": "body pose / heading", "class": "SCIENTIFIC_RECEIPT",
     "historical": "ConsequenceReceipt + timeline x,y,theta"},
    {"field": "head heading", "class": "SCIENTIFIC_RECEIPT",
     "historical": "timeline head_world_heading / head_relative_angle when recorded"},
    {"field": "other-agent pose", "class": "RESEARCHER_ONLY",
     "historical": "DERIVED toroidal geometry from timeline; never agent-accessible as pose"},
    {"field": "occlusion provenance / sample receipts", "class": "RESEARCHER_ONLY",
     "historical": "timeline.vision_optical neighbors_optical / Tiktaalik Eye; do not treat as agent fields"},
    {"field": "terrain / world geometry", "class": "RESEARCHER_ONLY",
     "historical": "NOT_RECORDED_PER_TICK height maps; seed/config only"},
    {"field": "body_exposure / foreign_body_total", "class": "SCIENTIFIC_RECEIPT",
     "historical": "timeline.vision_optical Observer GT; LEGACY_BODY_VISUAL_EXPOSURE"},
]


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def _q(v: float, nd: int = Q) -> float:
    return round(float(v), nd)


class _Chan:
    __slots__ = ("n", "present", "nonzero", "sat", "sx", "sxx", "mn", "mx", "last", "trans", "rep", "states")

    def __init__(self) -> None:
        self.n = 0
        self.present = 0
        self.nonzero = 0
        self.sat = 0
        self.sx = 0.0
        self.sxx = 0.0
        self.mn = None
        self.mx = None
        self.last = None
        self.trans = 0
        self.rep = 0
        self.states: dict[float, int] = {}

    def add(self, v: float | None) -> None:
        self.n += 1
        if v is None:
            self.last = None
            return
        self.present += 1
        if abs(v) > EPS:
            self.nonzero += 1
        if v >= SAT:
            self.sat += 1
        self.sx += v
        self.sxx += v * v
        self.mn = v if self.mn is None else min(self.mn, v)
        self.mx = v if self.mx is None else max(self.mx, v)
        qv = _q(v)
        if len(self.states) < MAX_STATES:
            self.states[qv] = self.states.get(qv, 0) + 1
        if self.last is not None:
            if abs(qv - self.last) > 1e-9:
                self.trans += 1
            else:
                self.rep += 1
        self.last = qv

    def report(self) -> dict[str, Any]:
        p = max(1, self.present)
        mean = self.sx / p if self.present else None
        var = (self.sxx / p - (mean or 0) ** 2) if self.present else None
        std = math.sqrt(max(0.0, var)) if var is not None else None
        return {
            "ticks_scanned": self.n,
            "ticks_present": self.present,
            "ticks_nonzero": self.nonzero,
            "occupancy_fraction": round(self.nonzero / p, 6) if self.present else 0.0,
            "mean": None if mean is None else round(mean, 6),
            "std": None if std is None else round(std, 6),
            "min": self.mn,
            "max": self.mx,
            "saturation_fraction": round(self.sat / p, 6) if self.present else 0.0,
            "quantized_state_diversity": len(self.states),
            "transition_count": self.trans,
            "repeated_state_count": self.rep,
        }


def _vec(acc: dict[str, Any], keys: tuple[str, ...]) -> list[float]:
    return [float(_f(acc.get(k)) or 0.0) for k in keys]


def _l1(a: list[float], b: list[float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b))


def _argmax(v: list[float]) -> int:
    m = max(v) if v else 0.0
    if m <= EPS:
        return -1
    return int(max(range(len(v)), key=lambda i: v[i]))


def _classify_spatial(prev: list[float], cur: list[float]) -> str:
    d = _l1(prev, cur)
    if d < 0.05:
        return "STABLE_SPATIAL_STATE"
    zeros_prev = sum(1 for x in prev if x <= EPS)
    zeros_cur = sum(1 for x in cur if x <= EPS)
    if zeros_cur > zeros_prev + 0 and d >= 0.08:
        return "OCCLUSION_CHANGE"
    if zeros_prev > zeros_cur + 0 and d >= 0.08:
        return "DISOCCLUSION_CHANGE"
    if d >= 0.5:
        return "LARGE_SPATIAL_TRANSITION"
    if _argmax(prev) != _argmax(cur) and _argmax(cur) >= 0:
        return "ANGULAR_SHIFT"
    sm = abs(sum(cur) - sum(prev))
    if sm >= 0.12:
        return "OPTICAL_MAGNITUDE_CHANGE"
    return "DISTRIBUTION_SHIFT"


def _attrib(neck: str, loco: str, d_head: float, d_body: float, d_peer: float, d_self: float) -> str:
    tags = []
    nu = str(neck or "").upper()
    lu = str(loco or "WAIT").upper()
    if nu in ("NECK_LEFT", "NECK_RIGHT") or abs(d_head) > 0.04:
        tags.append("HEAD_ROTATION")
    if lu.startswith("MOVE") or d_self > 0.04:
        tags.append("SELF_TRANSLATION")
    if abs(d_body) > 0.04 and not lu.startswith("MOVE"):
        tags.append("SELF_ROTATION")
    if d_peer > 0.04:
        tags.append("OTHER_BODY_CHANGE")
    if not tags:
        if lu in ("WAIT", "NONE", ""):
            return "NOT_ATTRIBUTABLE"
        return "SHARED_WORLD_CHANGE"
    if len(tags) == 1:
        return tags[0]
    return "MIXED"


def _signal_bin(acc: dict[str, Any]) -> str:
    a = _f(acc.get("local.FIELD_A")) or 0.0
    b = _f(acc.get("local.FIELD_B")) or 0.0
    s = max(a, b)
    if s <= EPS:
        return "absent"
    if s < 0.15:
        return "weak"
    return "stronger"


def _joint(has_vis: bool, sig: str) -> str:
    sp = sig != "absent"
    if has_vis and sp:
        return "VISUAL_PLUS_SIGNAL"
    if has_vis:
        return "VISUAL_ONLY"
    if sp:
        return "SIGNAL_ONLY"
    return "NEITHER"


def load_regimes(run_dir: Path, tmin: int | None, tmax: int | None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in _iter_jsonl(run_dir / "scientific_events.jsonl"):
        kind = str(row.get("type") or row.get("kind") or "")
        if kind not in ("WORLD_INTERVENTION", "MECHANISM_CONFIG", "VISION_CONFIG", "SPATIAL_VISION"):
            if "INTERVENTION" not in kind and "SPATIAL" not in kind and "PSC" not in kind:
                continue
        t = int(row.get("tick") or row.get("simulation_tick") or 0)
        events.append({"tick": t, "kind": kind, "changes": row.get("changes") or row.get("evidence")})
    events.sort(key=lambda e: e["tick"])
    start = int(tmin or 0)
    end = tmax
    regimes = [{"index": 0, "tick_start": start, "tick_end": end, "label": "INITIAL"}]
    for i, ev in enumerate(events):
        regimes[-1]["tick_end"] = ev["tick"] - 1
        regimes.append({
            "index": i + 1,
            "tick_start": ev["tick"],
            "tick_end": end,
            "label": ev["kind"],
            "event": ev,
        })
    return regimes


def _neck(story: Any) -> str:
    mot = getattr(story, "motor", None) or {}
    return str((mot.get("components") or {}).get("neck") or "NECK_HOLD")


def _loco(story: Any) -> str:
    mot = getattr(story, "motor", None) or {}
    return str((mot.get("components") or {}).get("locomotion") or "WAIT")


def analyze_beta31_vision(
    run_dir: Path,
    stories: list[Any],
    *,
    max_tick: int | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    by_story: dict[tuple[str, int], Any] = {(s.cognitive_agent_id, int(s.tick)): s for s in stories}
    agents = sorted({s.cognitive_agent_id for s in stories})
    occ: dict[str, dict[str, _Chan]] = {
        aid: {k: _Chan() for k in ALL_VISUAL} for aid in agents
    }
    spatial_states: dict[str, dict[tuple, int]] = {aid: {} for aid in agents}
    trans_counts: dict[str, Counter] = {aid: Counter() for aid in agents}
    attrib_counts: dict[str, Counter] = {aid: Counter() for aid in agents}
    trans_x_motor: dict[str, Counter] = {aid: Counter() for aid in agents}
    last_spatial: dict[str, list[float]] = {}
    last_tick: dict[str, int] = {}
    last_head: dict[str, float] = {}
    last_theta: dict[str, float] = {}
    last_xy: dict[str, tuple[float, float]] = {}
    last_peer: dict[str, float] = {}
    last_occ_mask: dict[str, tuple[bool, ...]] = {}
    occ_eps: dict[str, list[dict[str, Any]]] = {aid: [] for aid in agents}
    open_occ: dict[str, dict[str, Any] | None] = {aid: None for aid in agents}
    head_d: dict[str, list[float]] = {aid: [] for aid in agents}
    wait_d: dict[str, list[float]] = {aid: [] for aid in agents}
    move_d: dict[str, list[float]] = {aid: [] for aid in agents}
    joint: dict[str, Counter] = {aid: Counter() for aid in agents}
    sig_strat: dict[str, Counter] = {aid: Counter() for aid in agents}
    motifs: dict[str, Counter] = {aid: Counter() for aid in agents}
    motif_xy: dict[str, dict[str, set]] = {aid: {} for aid in agents}
    last_motif: dict[str, list[str]] = {aid: [] for aid in agents}
    dist_series: dict[str, list[tuple[int, float, str, str, dict]]] = {aid: [] for aid in agents}
    nv_buckets: dict[tuple, list] = {}
    n_obs = 0
    visual_present_ticks = 0
    channels_seen: set[str] = set()
    n_spatial_ticks = 0
    n_surface_ticks = 0

    obs_path = run_dir / "scientific_observations.jsonl"
    for row in _iter_jsonl(obs_path):
        if "tick" not in row:
            continue
        t = int(row["tick"])
        if max_tick is not None and t > int(max_tick):
            continue
        aid = str(row.get("cognitive_agent_id") or "")
        if aid not in occ:
            occ[aid] = {k: _Chan() for k in ALL_VISUAL}
            spatial_states.setdefault(aid, {})
            trans_counts.setdefault(aid, Counter())
            attrib_counts.setdefault(aid, Counter())
            trans_x_motor.setdefault(aid, Counter())
            occ_eps.setdefault(aid, [])
            open_occ.setdefault(aid, None)
            head_d.setdefault(aid, [])
            wait_d.setdefault(aid, [])
            move_d.setdefault(aid, [])
            joint.setdefault(aid, Counter())
            sig_strat.setdefault(aid, Counter())
            motifs.setdefault(aid, Counter())
            motif_xy.setdefault(aid, {})
            last_motif.setdefault(aid, [])
            dist_series.setdefault(aid, [])
        acc = row.get("accessible") if isinstance(row.get("accessible"), dict) else {}
        n_obs += 1
        vis_hit = False
        for k in ALL_VISUAL:
            v = _f(acc.get(k)) if k in acc else None
            if k in acc:
                channels_seen.add(k)
                vis_hit = True
            occ[aid][k].add(v if k in acc else None)
        if vis_hit:
            visual_present_ticks += 1
        if any(k in acc for k in SURFACE):
            n_surface_ticks += 1
        spat = _vec(acc, SPATIAL_EXO)
        if any(k in acc for k in SPATIAL_EXO):
            n_spatial_ticks += 1
            qt = tuple(_q(x) for x in spat)
            st = spatial_states[aid]
            if len(st) < MAX_STATES:
                st[qt] = st.get(qt, 0) + 1
        s = by_story.get((aid, t))
        loco = _loco(s) if s else "WAIT"
        neck = _neck(s) if s else "NECK_HOLD"
        pose = None
        geom = None
        if s:
            for d in s.derived_changes:
                if d.get("kind") == "POSE_STATE":
                    pose = d
                elif d.get("kind") == "RELATIVE_GEOMETRY":
                    geom = d
        head = _f((pose or {}).get("head_world_heading") or (pose or {}).get("head_relative_angle")) or 0.0
        theta = _f((pose or {}).get("theta")) or 0.0
        xy = (_f((pose or {}).get("x")) or 0.0, _f((pose or {}).get("y")) or 0.0)
        peer_d = _f((geom or {}).get("toroidal_distance"))
        sig = _signal_bin(acc)
        sig_strat[aid][sig] += 1
        has_vis = any((_f(acc.get(k)) or 0.0) > EPS for k in ALL_VISUAL if k in acc)
        joint[aid][_joint(has_vis, sig)] += 1
        if peer_d is not None and len(dist_series[aid]) < 20000:
            dist_series[aid].append((t, peer_d, loco, neck, {
                "visual": tuple(_q(x) for x in spat) if any(k in acc for k in SPATIAL_EXO) else None,
                "exo": tuple(_q(_f(acc.get(k)) or 0.0) for k in LEGACY_EXO),
                "signal": sig,
                "selected": (s.decision or {}).get("selected_action_legacy") if s and s.decision else None,
                "path": (s.decision or {}).get("selection_path") if s and s.decision else None,
                "xy": xy,
            }))
        if aid in last_spatial and last_tick.get(aid) == t - 1 and any(k in acc for k in SPATIAL_EXO):
            prev = last_spatial[aid]
            kind = _classify_spatial(prev, spat)
            trans_counts[aid][kind] += 1
            d_head = abs(head - last_head.get(aid, head))
            d_th = abs(theta - last_theta.get(aid, theta))
            px, py = last_xy.get(aid, xy)
            d_self = math.hypot(xy[0] - px, xy[1] - py)
            d_peer = 0.0
            if peer_d is not None and last_peer.get(aid) is not None:
                d_peer = abs(peer_d - last_peer[aid])
            att = _attrib(neck, loco, d_head, d_th, d_peer, d_self)
            attrib_counts[aid][att] += 1
            trans_x_motor[aid][f"{kind}|{loco}|{neck}"] += 1
            dl1 = _l1(prev, spat)
            nu = neck.upper()
            if nu in ("NECK_LEFT", "NECK_RIGHT"):
                head_d[aid].append(dl1)
            elif str(loco).upper().startswith("MOVE"):
                move_d[aid].append(dl1)
            else:
                wait_d[aid].append(dl1)
            mask = tuple(x <= EPS for x in spat)
            prev_mask = last_occ_mask.get(aid)
            if prev_mask is not None:
                newly_occ = sum(1 for a, b in zip(prev_mask, mask) if (not a) and b)
                newly_dis = sum(1 for a, b in zip(prev_mask, mask) if a and (not b))
                if newly_occ and open_occ[aid] is None:
                    open_occ[aid] = {
                        "kind": "OCCLUSION_TRANSITION",
                        "start_tick": t,
                        "agent": aid,
                        "action": loco,
                        "neck": neck,
                        "bins": newly_occ,
                    }
                if newly_dis and open_occ[aid] is not None:
                    ep = open_occ[aid]
                    ep["end_tick"] = t
                    ep["duration"] = t - int(ep["start_tick"])
                    ep["close_kind"] = "DISOCCLUSION_TRANSITION"
                    if len(occ_eps[aid]) < 200:
                        occ_eps[aid].append(ep)
                    open_occ[aid] = None
            last_occ_mask[aid] = mask
            tok = f"{kind}:{nu[:6]}:{str(loco)[:8]}"
            mq = last_motif[aid]
            mq.append(tok)
            if len(mq) > 4:
                mq.pop(0)
            if len(mq) == 4:
                key = ">".join(mq)
                motifs[aid][key] += 1
                cells = motif_xy[aid].setdefault(key, set())
                if len(cells) < 32:
                    cells.add((int(xy[0]), int(xy[1])))
        if any(k in acc for k in SPATIAL_EXO):
            last_spatial[aid] = spat
            last_occ_mask.setdefault(aid, tuple(x <= EPS for x in spat))
        last_tick[aid] = t
        last_head[aid] = head
        last_theta[aid] = theta
        last_xy[aid] = xy
        if peer_d is not None:
            last_peer[aid] = peer_d
        nv = tuple(_q(_f(acc.get(k)) or 0.0) for k in NONVISUAL_MATCH)
        vis_fp = tuple(_q(_f(acc.get(k)) or 0.0) for k in (SPATIAL_EXO + SURFACE[:3] + LEGACY_EXO))
        if vis_hit and s is not None:
            bk = (aid, nv)
            if bk in nv_buckets or len(nv_buckets) < 4096:
                lst = nv_buckets.setdefault(bk, [])
                if len(lst) < 10:
                    lst.append({
                        "tick": t,
                        "vis_fp": vis_fp,
                        "selected": (s.decision or {}).get("selected_action_legacy"),
                        "path": (s.decision or {}).get("selection_path"),
                        "candidate_count": (s.decision or {}).get("candidate_count"),
                        "candidate_id": (s.decision or {}).get("selected_candidate_id"),
                        "signal": sig,
                    })

    occupancy = {
        aid: {
            "LEGACY": {k: occ[aid][k].report() for k in LEGACY_EXO},
            "SURFACE": {k: occ[aid][k].report() for k in SURFACE},
            "SPATIAL": {k: occ[aid][k].report() for k in SPATIAL_EXO},
            "SPATIAL_SURFACE": {k: occ[aid][k].report() for k in SPATIAL_SURFACE},
        }
        for aid in occ
    }

    def _mean(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 6) if xs else None

    head_coupling = {}
    for aid in occ:
        hm, wm, mm = _mean(head_d[aid]), _mean(wait_d[aid]), _mean(move_d[aid])
        assoc = "NOT_TESTABLE"
        if hm is not None and wm is not None and (head_d[aid] and wait_d[aid]):
            assoc = "OBSERVED_ASSOCIATION" if hm > wm * 1.15 + 0.01 else "NO_SYSTEMATIC_DIFFERENCE"
        head_coupling[aid] = {
            "n_neck": len(head_d[aid]),
            "n_wait": len(wait_d[aid]),
            "n_move": len(move_d[aid]),
            "mean_dL1_after_neck": hm,
            "mean_dL1_after_wait": wm,
            "mean_dL1_after_move": mm,
            "HEAD_MOTION_SPATIAL_COUPLING": assoc,
            "note": "Association only; not active vision / intention.",
        }

    smc = _scan_smc_pe_psc(
        run_dir, max_tick=max_tick, occupancy_agents=list(occ), nv_buckets=nv_buckets,
    )
    reversals = _distance_reversals(dist_series)
    tmin = min((s.tick for s in stories), default=None)
    tmax = max((s.tick for s in stories), default=None)
    regimes = load_regimes(run_dir, tmin, tmax)

    spatial_detected = n_spatial_ticks > 0 or any(k.startswith("spatial_") for k in channels_seen)
    surface_detected = n_surface_ticks > 0 or any(k.startswith("surface_c") for k in channels_seen)
    occ_recon = "PARTIAL"
    if any(occ_eps[a] for a in occ_eps):
        occ_recon = "PARTIAL"
    if not spatial_detected:
        occ_recon = "NOT_TESTABLE"

    loc_invariant = []
    for aid, ctr in motifs.items():
        for key, n in ctr.most_common(MAX_MOTIFS):
            cells = motif_xy[aid].get(key) or set()
            if n >= 3 and len(cells) >= 2:
                loc_invariant.append({
                    "agent": aid, "motif": key, "support": n,
                    "n_world_cells": len(cells),
                    "label": "LOCATION_INVARIANT_SENSORIMOTOR_MOTIF_CANDIDATE",
                })

    max_level = int(smc.get("max_sensitivity_level") or 0)
    cand = smc.get("naturalistic_psc_visual_sensitivity_candidate") or "NOT_FOUND"

    summary = {
        "schema": "mm.analyzer_1_2.beta31_vision.v1",
        "analyzer_version": "1.2.0",
        "BETA31_VISUAL_CHANNELS_DETECTED": bool(channels_seen),
        "SURFACE_CHANNELS_ANALYZED": bool(surface_detected),
        "SPATIAL_CHANNELS_ANALYZED": bool(spatial_detected),
        "n_observation_rows": n_obs,
        "visual_present_ticks": visual_present_ticks,
        "channels_seen": sorted(channels_seen),
        "HISTORICAL_OCCLUSION_RECONSTRUCTION": occ_recon,
        "NATURALISTIC_SPATIAL_SMC_DIFFERENTIATION": smc.get("spatial_smc_differentiation"),
        "PE_VISUAL_FORENSICS": smc.get("pe_visual_forensics"),
        "PROSPECTIVE_VISUAL_DIFFERENTIATION": smc.get("prospective_visual_differentiation"),
        "NATURALISTIC_PSC_VISUAL_SENSITIVITY_MAX_LEVEL": max_level,
        "NATURALISTIC_PSC_VISUAL_SENSITIVITY_CANDIDATE": cand,
        "DISTANCE_REVERSAL_SEQUENCE_COUNT": len(reversals.get("sequences") or []),
        "TERRAIN_ASSISTED_DISTANCE_REVERSAL_CANDIDATES": reversals.get("terrain_assisted_count", 0),
        "HEAD_MOTION_SPATIAL_COUPLING": {
            aid: v.get("HEAD_MOTION_SPATIAL_COUPLING") for aid, v in head_coupling.items()
        },
        "legacy_body_visual_exposure": {
            aid: sum(1 for s in stories if s.cognitive_agent_id == aid
                     and any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context))
            for aid in agents
        },
        "agent_differences": _agent_diffs(occupancy, spatial_states, head_coupling, smc, reversals, joint),
        "regimes": regimes,
        "REGIME_AWARE": True,
        "limitations": [
            "WORLD remains 2D; no depth/z channel.",
            "c0/c1/c2 are anonymous optical channels, not RGB or terrain labels.",
            "body_exposure is Observer GT (LEGACY_BODY_VISUAL_EXPOSURE), not agent recognition.",
            "PE class IDs are not stored per tick in V3 CORE DecisionReceipt.",
            "LEVEL 5 naturalistic pairs are association candidates, not causal proof.",
            "Occlusion provenance (sample receipts) is RESEARCHER_ONLY; bin-zeroing is a proxy.",
        ],
        "open_causal_questions": [
            "Would withholding spatial_* from ObservationReceipt change PSC selection?",
            "Are visual/action associations residual after signal matching?",
            "Do occlusion episodes exceed chance under reshuffled spatial series?",
        ],
        "claims_boundary": {
            "do_not_claim": [
                "sees in 3D", "understands depth", "recognizes terrain/agent",
                "understands colors", "intentionally approaches", "communicates",
                "learned to use vision", "slingshot strategy",
            ],
        },
    }

    artifacts = {
        "vision_summary": summary,
        "optical_occupancy": occupancy,
        "spatial_transitions": {
            aid: {
                "transforms": dict(trans_counts[aid]),
                "attribution": dict(attrib_counts[aid]),
                "transform_x_motor_top": trans_x_motor[aid].most_common(20),
                "spatial_state_diversity": len(spatial_states[aid]),
            }
            for aid in occ
        },
        "occlusion_sequences": {
            "reconstruction": occ_recon,
            "episodes": {aid: occ_eps[aid][:80] for aid in occ_eps},
            "counts": {aid: len(occ_eps[aid]) for aid in occ_eps},
        },
        "head_motion_coupling": head_coupling,
        "smc_visual_differentiation": smc.get("smc"),
        "pe_visual_survival": smc.get("pe"),
        "prospective_visual_trace": smc.get("prospective"),
        "psc_visual_candidates": smc.get("psc"),
        "spatial_motifs": {
            aid: {
                "top": motifs[aid].most_common(20),
                "location_invariant_candidates": [x for x in loc_invariant if x["agent"] == aid],
            }
            for aid in occ
        },
        "distance_reversal_sequences": reversals,
        "signal_vision_context": {
            aid: {"joint": dict(joint[aid]), "signal": dict(sig_strat[aid])} for aid in occ
        },
        "evidence_matrix": EVIDENCE_MATRIX,
    }

    if out_dir is not None:
        write_vision_artifacts(Path(out_dir), artifacts)

    text = format_beta31_vision_section(artifacts)
    return {
        "beta31_vision": artifacts,
        "beta31_vision_report_text": text,
        "publication": {
            "BETA31_ANALYZER_VISION_PASS": ("FAIL" if not n_obs else "PARTIAL"),
            "ANALYZER_VERSION": "1.2.0",
            "BETA31_VISUAL_CHANNELS_DETECTED": "YES" if channels_seen else "NO",
            "SURFACE_CHANNELS_ANALYZED": "YES" if surface_detected else "NO",
            "SPATIAL_CHANNELS_ANALYZED": "YES" if spatial_detected else "NO",
            "OPTICAL_OCCUPANCY_ANALYSIS": "PASS" if n_obs else "FAIL",
            "SPATIAL_TRANSFORMATION_ANALYSIS": "PASS" if spatial_detected else ("PARTIAL" if n_obs else "FAIL"),
            "OCCLUSION_ANALYSIS": "PARTIAL" if spatial_detected else "PARTIAL",
            "HEAD_MOTION_COUPLING_ANALYSIS": "PASS" if any(head_d[a] or wait_d[a] for a in head_d) else "PARTIAL",
            "NATURALISTIC_SPATIAL_SMC_DIFFERENTIATION": smc.get("spatial_smc_differentiation"),
            "PE_VISUAL_FORENSICS": smc.get("pe_visual_forensics"),
            "PROSPECTIVE_VISUAL_DIFFERENTIATION": smc.get("prospective_visual_differentiation"),
            "NATURALISTIC_PSC_VISUAL_SENSITIVITY_MAX_LEVEL": max_level,
            "NATURALISTIC_PSC_VISUAL_SENSITIVITY_CANDIDATE": cand,
            "DISTANCE_REVERSAL_SEQUENCE_COUNT": len(reversals.get("sequences") or []),
            "TERRAIN_ASSISTED_DISTANCE_REVERSAL_CANDIDATES": reversals.get("terrain_assisted_count", 0),
            "SIGNAL_VISION_CONFOUND_ANALYZED": "YES",
            "REGIME_AWARE": "YES",
            "PUBLIC_BETA31_ANALYSIS_READY": "YES" if n_obs else "NO",
            "note": "PASS withheld: PE class IDs not in V3 DecisionReceipt; occlusion uses bin-zero proxy. PARTIAL is valid.",
        },
    }


def _scan_smc_pe_psc(
    run_dir: Path,
    *,
    max_tick: int | None,
    occupancy_agents: list[str],
    nv_buckets: dict[tuple, list] | None = None,
) -> dict[str, Any]:
    vis_keys = set(ALL_VISUAL)
    n_upd_surf = 0
    n_upd_spat = 0
    n_upd = 0
    antecedents: set[tuple] = set()
    deltas: set[tuple] = set()
    match = low = unk = 0
    diff_same_motor = 0
    examples = []
    pe_status = "PARTIAL"
    pe_reason = (
        "V3 DecisionReceipt does not store predictive-equivalence class IDs or "
        "compressed visual signatures per tick; only SMC predicted_delta compact keys."
    )
    prosp_diff = 0
    prosp_n = 0
    psc_pairs = []
    buckets: dict[tuple, list] = {}
    max_level = 0
    n_vis_pred = 0
    n_dec = 0

    def vis_delta(d: dict) -> tuple:
        items = []
        for k, v in d.items():
            if k in vis_keys or str(k).startswith("spatial_") or str(k).startswith("surface_c") or str(k).startswith("exo_"):
                try:
                    items.append((str(k), round(float(v), 4)))
                except (TypeError, ValueError):
                    continue
        return tuple(sorted(items))

    for row in _iter_jsonl(run_dir / "scientific_decisions.jsonl"):
        t = int(row.get("tick") or 0)
        if max_tick is not None and t > int(max_tick):
            continue
        n_dec += 1
        smc = row.get("sensorimotor_consequence") if isinstance(row.get("sensorimotor_consequence"), dict) else {}
        preds = smc.get("predictions") if isinstance(smc.get("predictions"), list) else []
        last = smc.get("last_update") if isinstance(smc.get("last_update"), dict) else {}
        mean_d = last.get("mean_delta") if isinstance(last.get("mean_delta"), dict) else {}
        if last:
            n_upd += 1
            if any(k in mean_d for k in SURFACE) or any(str(k).startswith("surface_c") for k in mean_d):
                n_upd_surf += 1
            if any(str(k).startswith("spatial_") for k in mean_d):
                n_upd_spat += 1
            vd = vis_delta(mean_d)
            if vd:
                antecedents.add(vd)
                if len(antecedents) > MAX_STATES:
                    antecedents.pop()
        by_motor: dict[str, set] = {}
        for p in preds:
            if not isinstance(p, dict):
                continue
            st = str(p.get("status") or "").upper()
            if "MATCH" in st:
                match += 1
            elif "LOW" in st:
                low += 1
            elif "UNKNOWN" in st or st in ("", "NONE"):
                unk += 1
            d = p.get("predicted_delta") if isinstance(p.get("predicted_delta"), dict) else {}
            vd = vis_delta(d)
            if vd:
                n_vis_pred += 1
                max_level = max(max_level, 2)
                deltas.add(vd)
                if len(deltas) > MAX_STATES:
                    deltas.pop()
                mot = str(p.get("motor") or p.get("candidate_locomotion") or "")
                by_motor.setdefault(mot, set()).add(vd)
        if any(len(v) >= 2 for v in by_motor.values()):
            diff_same_motor += 1
            if len(examples) < MAX_EXAMPLES:
                examples.append({
                    "tick": t,
                    "agent": row.get("cognitive_agent_id"),
                    "kind": "same_motor_differentiated_visual_delta",
                    "motors": {k: list(v)[:2] for k, v in list(by_motor.items())[:4]},
                })
        hss = row.get("historical_sensorimotor_selection") if isinstance(row.get("historical_sensorimotor_selection"), dict) else {}
        cands = hss.get("candidates") if isinstance(hss.get("candidates"), list) else []
        if cands:
            prosp_n += 1
            fields = []
            supports = []
            for c in cands:
                if not isinstance(c, dict):
                    continue
                pf = c.get("predicted_fields") or []
                fields.append(tuple(str(x) for x in pf if str(x).startswith(("exo_", "surface_", "spatial_"))))
                supports.append(c.get("history_support"))
            if len(set(fields)) >= 2 or len({str(x) for x in supports}) >= 2:
                prosp_diff += 1
                max_level = max(max_level, 3)
        nv = tuple()  # filled if we had observation; DecisionReceipt compact has no accessible
        # Match PSC structure from candidate_count + selected
        sel = str(row.get("selected_action_legacy") or "")
        cc = row.get("candidate_count")
        cid = row.get("selected_candidate_id")
        path = row.get("selection_path")
        # Bucket on tick-parity + selected motor family for residual-matched pairs is too weak.
        # Use candidate_count + path as nonvisual-ish proxy only when visual deltas differ.
        if by_motor:
            vis_sig = tuple(sorted((m, tuple(sorted(vs))) for m, vs in by_motor.items()))
            key = (str(row.get("cognitive_agent_id")), str(path), str(cc))
            lst = buckets.setdefault(key, [])
            if len(lst) < 12:
                lst.append({
                    "tick": t,
                    "selected": sel,
                    "candidate_id": cid,
                    "candidate_count": cc,
                    "vis_sig": vis_sig,
                    "path": path,
                })

    pair_examples = []
    cand_label = "NOT_FOUND"
    for key, rows in buckets.items():
        if len(pair_examples) >= MAX_PAIRS:
            break
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                if a["vis_sig"] == b["vis_sig"]:
                    continue
                level = 2
                if a["candidate_count"] != b["candidate_count"] or a["candidate_id"] != b["candidate_id"]:
                    level = 4
                    max_level = max(max_level, 4)
                if a["selected"] != b["selected"]:
                    level = 5
                    max_level = max(max_level, 5)
                    cand_label = "FOUND"
                pair_examples.append({
                    "agent": key[0],
                    "tick_a": a["tick"],
                    "tick_b": b["tick"],
                    "selected_a": a["selected"],
                    "selected_b": b["selected"],
                    "level": level,
                    "match": "selection_path+candidate_count (decision-only; weaker residual)",
                    "residual": "observation nonvisual not in this pair source",
                    "label": "NATURALISTIC_PSC_VISUAL_SENSITIVITY_CANDIDATE" if level >= 5 else "LEVEL_%d" % level,
                })
                if len(pair_examples) >= MAX_PAIRS:
                    break

    obs_pairs = []
    for (aid, nv), rows in (nv_buckets or {}).items():
        if len(obs_pairs) >= MAX_PAIRS:
            break
        vis_groups: dict[tuple, list] = {}
        for r in rows:
            vis_groups.setdefault(r["vis_fp"], []).append(r)
        if len(vis_groups) < 2:
            continue
        keys = list(vis_groups)
        a = vis_groups[keys[0]][0]
        b = vis_groups[keys[1]][0]
        if a["signal"] != b["signal"]:
            continue
        level = 2
        if a.get("candidate_count") != b.get("candidate_count") or a.get("candidate_id") != b.get("candidate_id"):
            level = 4
            max_level = max(max_level, 4)
        if a.get("selected") != b.get("selected"):
            level = 5
            max_level = max(max_level, 5)
            cand_label = "FOUND"
        rec = {
            "agent": aid,
            "tick_a": a["tick"],
            "tick_b": b["tick"],
            "selected_a": a.get("selected"),
            "selected_b": b.get("selected"),
            "level": level,
            "match": "NONVISUAL_MATCH quantized accessible fields + signal bin",
            "residual": "quantization Q=2; unmatched observation keys outside NONVISUAL_MATCH",
            "label": "NATURALISTIC_PSC_VISUAL_SENSITIVITY_CANDIDATE" if level >= 5 else "LEVEL_%d" % level,
        }
        obs_pairs.append(rec)
        if len(pair_examples) < MAX_PAIRS:
            pair_examples.append(rec)

    if n_vis_pred:
        max_level = max(max_level, 2)
    if n_dec and (n_upd_surf or n_upd_spat or n_vis_pred):
        max_level = max(max_level, 1)
    if n_dec:
        max_level = max(max_level, 0)

    spat_diff = "NOT_TESTABLE"
    if n_upd_spat or any("spatial_" in str(x) for tup in deltas for x in tup[:1]):
        spat_diff = "YES" if diff_same_motor else "PARTIAL"
    elif n_upd_surf or n_vis_pred:
        spat_diff = "PARTIAL"
    elif n_dec:
        spat_diff = "NO"

    prosp = "NOT_TESTABLE" if prosp_n == 0 else ("YES" if prosp_diff else "NO")
    if prosp_n and not prosp_diff:
        prosp = "NO"

    return {
        "spatial_smc_differentiation": spat_diff,
        "pe_visual_forensics": pe_status,
        "prospective_visual_differentiation": prosp,
        "max_sensitivity_level": max_level,
        "naturalistic_psc_visual_sensitivity_candidate": cand_label if pair_examples else ("NOT_TESTABLE" if n_dec == 0 else "NOT_FOUND"),
        "smc": {
            "updates": n_upd,
            "updates_with_surface": n_upd_surf,
            "updates_with_spatial": n_upd_spat,
            "distinct_visual_delta_signatures": len(deltas),
            "match": match,
            "low_support": low,
            "unknown": unk,
            "same_motor_visual_differentiation_ticks": diff_same_motor,
            "examples": examples,
        },
        "pe": {
            "status": pe_status,
            "reason": pe_reason,
            "RAW_VISUAL_STATE_COUNT": "NOT_RECORDED",
            "COMPRESSED_VISUAL_STATE_COUNT": "NOT_RECORDED",
            "PE_VISUAL_DISTINCTION_SURVIVAL": "NOT_RECORDED",
            "PE_VISUAL_MERGE_RATE": "NOT_RECORDED",
            "PE_VISUAL_SPLIT_RATE": "NOT_RECORDED",
        },
        "prospective": {
            "ticks_with_hss_candidates": prosp_n,
            "ticks_with_visual_field_or_support_diff": prosp_diff,
            "status": prosp,
        },
        "psc": {
            "n_decisions": n_dec,
            "matched_pair_examples": pair_examples[:12],
            "observation_matched_pairs": obs_pairs[:12],
            "max_level": max_level,
            "candidate": cand_label if pair_examples else "NOT_FOUND",
            "note": "LEVEL 5 is association under residual-matched naturalistic pairs, not ablation causality.",
        },
    }


def _distance_reversals(series: dict[str, list[tuple]]) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    terrain_n = 0
    windows = (5, 10, 20, 40, 80)
    for aid, seq in series.items():
        if len(seq) < 12:
            continue
        dists = [x[1] for x in seq]
        ticks = [x[0] for x in seq]
        for w in windows:
            i = 0
            while i + 2 * w <= len(seq) and len(out) < MAX_REVERSALS:
                mid = i + w
                end = i + 2 * w
                d0, dm, d1 = dists[i], max(dists[i:end]), dists[end - 1]
                rising = dists[mid] - dists[i]
                falling = dists[mid] - dists[end - 1]
                if rising > 0.15 and falling > 0.15 and dm >= d0 and dm >= d1:
                    motors = [seq[k][2] for k in range(i, end)]
                    necks = [seq[k][3] for k in range(i, end)]
                    vel_rev = False
                    # velocity reversal: distance slope sign change (already required)
                    motor_rev = False
                    opp = {("MOVE:N", "MOVE:S"), ("MOVE:S", "MOVE:N"), ("MOVE:E", "MOVE:W"), ("MOVE:W", "MOVE:E")}
                    for a, b in zip(motors, motors[1:]):
                        if (a, b) in opp:
                            motor_rev = True
                            break
                    xy0 = seq[i][4].get("xy")
                    xy1 = seq[end - 1][4].get("xy")
                    disp = None
                    if xy0 and xy1:
                        disp = round(math.hypot(xy1[0] - xy0[0], xy1[1] - xy0[1]), 4)
                    terrain = False
                    # if motors stay constant while distance trend reverses → terrain/peer candidate
                    if len(set(motors)) == 1 and str(motors[0]).upper().startswith("MOVE"):
                        terrain = True
                        terrain_n += 1
                    rec = {
                        "kind": "DISTANCE_REVERSAL_SEQUENCE",
                        "agent": aid,
                        "window": w,
                        "start_tick": ticks[i],
                        "reversal_tick": ticks[mid],
                        "end_tick": ticks[end - 1],
                        "initial_distance": round(d0, 4),
                        "max_distance": round(dm, 4),
                        "final_distance": round(d1, 4),
                        "MOTOR_REVERSAL": motor_rev,
                        "VELOCITY_REVERSAL": True,
                        "DISTANCE_TREND_REVERSAL": True,
                        "agent_displacement": disp,
                        "motor_sequence_compact": motors[:: max(1, w // 4)][:12],
                        "neck_involved": any(str(n).upper() in ("NECK_LEFT", "NECK_RIGHT") for n in necks),
                        "visual_state_start": seq[i][4].get("visual") or seq[i][4].get("exo"),
                        "visual_state_reversal": seq[mid][4].get("visual") or seq[mid][4].get("exo"),
                        "signal_start": seq[i][4].get("signal"),
                        "psc_path_start": seq[i][4].get("path"),
                        "psc_selected_start": seq[i][4].get("selected"),
                        "TERRAIN_ASSISTED_DISTANCE_REVERSAL_CANDIDATE": terrain,
                        "alias": "slingshot" if terrain else None,
                        "note": "Observational geometry; not planning/intention.",
                    }
                    out.append(rec)
                    i = end
                else:
                    i += max(1, w // 4)
    return {"sequences": out, "terrain_assisted_count": terrain_n}


def _agent_diffs(occ, spatial_states, head_coupling, smc, reversals, joint) -> dict[str, Any]:
    agents = sorted(occ)
    rows = []
    for aid in agents:
        exo_nz = sum(occ[aid]["LEGACY"][k]["ticks_nonzero"] for k in LEGACY_EXO)
        spat_div = len(spatial_states.get(aid) or {})
        rows.append({
            "agent": aid,
            "legacy_exo_nonzero_sum": exo_nz,
            "spatial_state_diversity": spat_div,
            "head_coupling": (head_coupling.get(aid) or {}).get("HEAD_MOTION_SPATIAL_COUPLING"),
            "joint_context": dict(joint.get(aid) or {}),
            "distance_reversals": sum(1 for s in (reversals.get("sequences") or []) if s.get("agent") == aid),
        })
    return {"per_agent": rows, "note": "Differences are descriptive; agents are not ranked."}


def write_vision_artifacts(out_dir: Path, artifacts: dict[str, Any]) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "vision_summary.json": artifacts["vision_summary"],
        "optical_occupancy.json": artifacts["optical_occupancy"],
        "spatial_transitions.json": artifacts["spatial_transitions"],
        "occlusion_sequences.json": artifacts["occlusion_sequences"],
        "head_motion_coupling.json": artifacts["head_motion_coupling"],
        "smc_visual_differentiation.json": artifacts["smc_visual_differentiation"],
        "pe_visual_survival.json": artifacts["pe_visual_survival"],
        "prospective_visual_trace.json": artifacts["prospective_visual_trace"],
        "psc_visual_candidates.json": artifacts["psc_visual_candidates"],
        "spatial_motifs.json": artifacts["spatial_motifs"],
        "distance_reversal_sequences.json": artifacts["distance_reversal_sequences"],
        "signal_vision_context.json": artifacts["signal_vision_context"],
        "BETA31_VISION_EVIDENCE_MATRIX.json": artifacts["evidence_matrix"],
    }
    paths = {}
    for name, payload in mapping.items():
        p = out_dir / name
        p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        paths[name] = str(p)
    return paths


def format_beta31_vision_section(artifacts: dict[str, Any]) -> str:
    s = artifacts.get("vision_summary") or {}
    lines = [
        "BETA 3.1 VISION ANALYSIS",
        "========================",
        "CONFIGURATION",
        f"  analyzer: {s.get('analyzer_version')}",
        f"  channels_seen: {', '.join(s.get('channels_seen') or []) or 'NONE'}",
        f"  SURFACE_CHANNELS_ANALYZED: {s.get('SURFACE_CHANNELS_ANALYZED')}",
        f"  SPATIAL_CHANNELS_ANALYZED: {s.get('SPATIAL_CHANNELS_ANALYZED')}",
        "",
        "OPTICAL OCCUPANCY",
        "  See optical_occupancy.json (per-agent LEGACY / SURFACE / SPATIAL / SPATIAL_SURFACE).",
        "  c0/c1/c2 are anonymous optical channels — not RGB, not terrain labels.",
        "",
        "SPATIAL STATE DIVERSITY",
    ]
    st = artifacts.get("spatial_transitions") or {}
    for aid, row in sorted(st.items()):
        lines.append(f"  {aid}: diversity={row.get('spatial_state_diversity')} transforms={row.get('transforms')}")
    lines += [
        "",
        "OCCLUSION / DISOCCLUSION",
        f"  HISTORICAL_OCCLUSION_RECONSTRUCTION = {s.get('HISTORICAL_OCCLUSION_RECONSTRUCTION')}",
        f"  episode counts: {(artifacts.get('occlusion_sequences') or {}).get('counts')}",
        "  Bin-zeroing is a proxy; sample-level occlusion provenance is RESEARCHER_ONLY.",
        "",
        "HEAD-MOTION COUPLING",
    ]
    for aid, row in sorted((artifacts.get("head_motion_coupling") or {}).items()):
        lines.append(
            f"  {aid}: {row.get('HEAD_MOTION_SPATIAL_COUPLING')} "
            f"dL1 neck={row.get('mean_dL1_after_neck')} wait={row.get('mean_dL1_after_wait')} move={row.get('mean_dL1_after_move')}"
        )
    lines += [
        "",
        "BODY-MOTION COUPLING",
        "  Included in spatial transform × motor tables (MOVE vs WAIT).",
        "",
        "SMC VISUAL DIFFERENTIATION",
        f"  NATURALISTIC_SPATIAL_SMC_DIFFERENTIATION = {s.get('NATURALISTIC_SPATIAL_SMC_DIFFERENTIATION')}",
        f"  updates={((artifacts.get('smc_visual_differentiation') or {}).get('updates'))} "
        f"surface={((artifacts.get('smc_visual_differentiation') or {}).get('updates_with_surface'))} "
        f"spatial={((artifacts.get('smc_visual_differentiation') or {}).get('updates_with_spatial'))} "
        f"same_motor_diff_ticks={((artifacts.get('smc_visual_differentiation') or {}).get('same_motor_visual_differentiation_ticks'))}",
        "",
        "COMPRESSION / PE",
        f"  PE_VISUAL_FORENSICS = {s.get('PE_VISUAL_FORENSICS')}",
        f"  {(artifacts.get('pe_visual_survival') or {}).get('reason')}",
        "",
        "PROSPECTIVE VISUAL DIFFERENTIATION",
        f"  PROSPECTIVE_VISUAL_DIFFERENTIATION = {s.get('PROSPECTIVE_VISUAL_DIFFERENTIATION')}",
        "",
        "PSC VISUAL SENSITIVITY",
        f"  MAX_LEVEL = {s.get('NATURALISTIC_PSC_VISUAL_SENSITIVITY_MAX_LEVEL')}",
        f"  CANDIDATE = {s.get('NATURALISTIC_PSC_VISUAL_SENSITIVITY_CANDIDATE')}",
        "  LEVEL 5 is NATURALISTIC_PSC_VISUAL_SENSITIVITY_CANDIDATE (not causal).",
        "",
        "TEMPORAL SPATIAL MOTIFS",
        f"  location-invariant candidates: {sum(len((v.get('location_invariant_candidates') or [])) for v in (artifacts.get('spatial_motifs') or {}).values())}",
        "",
        "DISTANCE REVERSAL SEQUENCES",
        f"  DISTANCE_REVERSAL_SEQUENCE_COUNT = {s.get('DISTANCE_REVERSAL_SEQUENCE_COUNT')}",
        f"  TERRAIN_ASSISTED_DISTANCE_REVERSAL_CANDIDATES = {s.get('TERRAIN_ASSISTED_DISTANCE_REVERSAL_CANDIDATES')}",
        "  Informal alias 'slingshot' is debug-only; not strategy.",
        "",
        "SIGNAL × VISION CONTEXT",
        f"  joint per agent (counts only): "
        + str({aid: v.get("joint") for aid, v in (artifacts.get("signal_vision_context") or {}).items()}),
        "",
        "AGENT DIFFERENCES",
        f"  {s.get('agent_differences')}",
        "",
        "LIMITATIONS",
    ]
    for x in s.get("limitations") or []:
        lines.append(f"  - {x}")
    lines += ["", "OPEN CAUSAL QUESTIONS"]
    for x in s.get("open_causal_questions") or []:
        lines.append(f"  - {x}")
    lines += [
        "",
        "LEGACY_BODY_VISUAL_EXPOSURE (Observer GT body_exposure joins; not recognition):",
        f"  {s.get('legacy_body_visual_exposure')}",
        "SURFACE_OPTICAL_EXPOSURE and SPATIAL_OPTICAL_STRUCTURE are occupancy of those channel families;",
        "they are not interchangeable with LEGACY_BODY_VISUAL_EXPOSURE.",
        "",
        "OBSERVED vs DERIVED vs NOT ESTABLISHED: occupancy/transforms are OBSERVED from receipts;",
        "attribution and matched pairs are DERIVED; recognition/intention remain NOT ESTABLISHED.",
    ]
    return "\n".join(lines) + "\n"
