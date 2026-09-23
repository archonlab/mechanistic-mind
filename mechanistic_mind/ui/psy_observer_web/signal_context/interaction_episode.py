"""BETA2-SIGINT-05: natural interaction episodes × temporal replay × trajectory coupling.

Reuses SIGINT-02/03 inject_source → _deposit path. Episodes are ordered physical
sequences — not conversations.
"""
from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    TRIGGER_EXTERNAL,
    TRIGGER_SHAM,
    audit_observation_no_intervention_leak,
    find_matched_s0,
    fingerprint_equal,
    make_signal_runtime,
    receiver_local_fields,
    scientific_fingerprint,
    stable_id,
)

TRIGGER_EPISODE_REPLAY = "NATURAL_SIGNAL_EPISODE_REPLAY"
NOT_RECORDED = "NOT_RECORDED"
NOT_RECONSTRUCTABLE = "NOT_RECONSTRUCTABLE"

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REF_RUN = (
    _PROJECT_ROOT / "results" / "psychology_observer" / "psy_observer_web"
    / "psyweb-20260918T021911.211579Z-b3cd1135"
)
REF_START, REF_END = 1554, 1563
HORIZON_MARKERS = (1, 2, 5, 10, 25, 50, 100)


@dataclass(frozen=True)
class EpisodeComponent:
    """One physical emission within an episode. Not a conversational turn."""

    component_id: str
    delta_t: int
    source_tick: int
    emitter_agent_id: str
    emitter_body_id: str
    channel: str
    amplitude: float | str
    x: float | str
    y: float | str
    cells: tuple[tuple[int, int], ...] | str
    trigger: str
    origin_kind: str
    emission_id: str
    reconstruction_completeness: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if isinstance(self.cells, tuple):
            d["cells"] = [[int(a), int(b)] for a, b in self.cells]
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EpisodeComponent":
        cells = raw.get("cells")
        if isinstance(cells, list) and cells and isinstance(cells[0], (list, tuple)):
            cells_t: tuple[tuple[int, int], ...] | str = tuple(
                (int(c[0]), int(c[1])) for c in cells
            )
        else:
            cells_t = str(cells or NOT_RECORDED)
        return cls(
            component_id=str(raw["component_id"]),
            delta_t=int(raw["delta_t"]),
            source_tick=int(raw["source_tick"]),
            emitter_agent_id=str(raw.get("emitter_agent_id") or NOT_RECORDED),
            emitter_body_id=str(raw.get("emitter_body_id") or NOT_RECORDED),
            channel=str(raw.get("channel") or "A").upper().replace("FIELD_", ""),
            amplitude=raw.get("amplitude", NOT_RECORDED),
            x=raw.get("x", NOT_RECORDED),
            y=raw.get("y", NOT_RECORDED),
            cells=cells_t,
            trigger=str(raw.get("trigger") or NOT_RECORDED),
            origin_kind=str(raw.get("origin_kind") or NOT_RECORDED),
            emission_id=str(raw.get("emission_id") or NOT_RECORDED),
            reconstruction_completeness=str(
                raw.get("reconstruction_completeness") or NOT_RECONSTRUCTABLE
            ),
        )


@dataclass
class NaturalSignalEpisode:
    """Ordered physical signal sequence. Not a semantic conversation."""

    episode_id: str
    source_run_id: str
    start_tick: int
    end_tick: int
    components: tuple[EpisodeComponent, ...]
    receptions: tuple[dict[str, Any], ...] = ()
    reconstruction: str = "INSUFFICIENT"
    provenance: str = "SCIENTIFIC_EVENTS"
    notes: tuple[str, ...] = ()

    @property
    def duration(self) -> int:
        return int(self.end_tick) - int(self.start_tick) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "source_run_id": self.source_run_id,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "duration": self.duration,
            "n_components": len(self.components),
            "components": [c.to_dict() for c in self.components],
            "receptions": list(self.receptions),
            "reconstruction": self.reconstruction,
            "provenance": self.provenance,
            "notes": list(self.notes),
            "channel_sequence": [c.channel for c in self.components],
            "emitter_sequence": [c.emitter_agent_id for c in self.components],
            "alternation_count": _alternation_count(self.components),
            "honesty": {"not_a_conversation": True, "not_communication": True},
        }


def _alternation_count(components: Iterable[EpisodeComponent]) -> int:
    prev = None
    n = 0
    # Per-tick primary emitters (simultaneous both counts as co-emission, not alt)
    by_dt: dict[int, set[str]] = defaultdict(set)
    for c in components:
        by_dt[int(c.delta_t)].add(c.emitter_agent_id)
    for dt in sorted(by_dt):
        emitters = by_dt[dt]
        if len(emitters) == 1:
            cur = next(iter(emitters))
            if prev is not None and cur != prev:
                n += 1
            prev = cur
        else:
            # simultaneous both — count as bidirectional tick, not strict alternation
            prev = "BOTH"
    return n


def _component_from_emission_event(
    ev: dict[str, Any],
    *,
    start_tick: int,
    run_id: str,
) -> EpisodeComponent:
    evidence = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else ev
    tick = int(ev.get("tick") or evidence.get("tick") or -1)
    amp = evidence.get("realized", evidence.get("amplitude", NOT_RECORDED))
    cells_raw = evidence.get("cells")
    if isinstance(cells_raw, list) and cells_raw:
        cells: tuple[tuple[int, int], ...] | str = tuple(
            (int(c[0]), int(c[1])) for c in cells_raw
        )
        completeness = "CELLS_AND_AMPLITUDE"
    else:
        cells = NOT_RECORDED
        completeness = "AMPLITUDE_POSITION" if amp not in (None, NOT_RECORDED) else NOT_RECONSTRUCTABLE
    eid = str(evidence.get("emission_id") or NOT_RECORDED)
    return EpisodeComponent(
        component_id=stable_id("ecomp", run_id, eid, tick),
        delta_t=tick - int(start_tick),
        source_tick=tick,
        emitter_agent_id=str(
            evidence.get("emitter_agent_id") or ev.get("emitter_agent_id") or NOT_RECORDED
        ),
        emitter_body_id=str(
            evidence.get("emitter_body_id") or evidence.get("body_id") or NOT_RECORDED
        ),
        channel=str(evidence.get("channel") or "A").upper().replace("FIELD_", ""),
        amplitude=float(amp) if isinstance(amp, (int, float)) else (amp if amp is not None else NOT_RECORDED),
        x=evidence.get("x", NOT_RECORDED),
        y=evidence.get("y", NOT_RECORDED),
        cells=cells,
        trigger=str(evidence.get("trigger") or NOT_RECORDED),
        origin_kind=str(evidence.get("origin_kind") or NOT_RECORDED),
        emission_id=eid,
        reconstruction_completeness=completeness,
    )


def load_episode_from_events(
    events_path: Path | str,
    *,
    start_tick: int,
    end_tick: int,
    run_id: str,
) -> NaturalSignalEpisode:
    path = Path(events_path)
    components: list[EpisodeComponent] = []
    receptions: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            t = d.get("tick")
            if t is None:
                continue
            ti = int(t)
            if ti < start_tick or ti > end_tick:
                continue
            typ = str(d.get("type") or "")
            if typ == "PHYSICAL_SIGNAL_EMITTED":
                components.append(
                    _component_from_emission_event(d, start_tick=start_tick, run_id=run_id)
                )
            elif typ == "PHYSICAL_SIGNAL_RECEIVED":
                ev = d.get("evidence") if isinstance(d.get("evidence"), dict) else {}
                receptions.append({
                    "tick": ti,
                    "delta_t": ti - start_tick,
                    "receiver_agent_id": d.get("receiver_agent_id") or ev.get("receiver_agent_id"),
                    "local.FIELD_A": ev.get("local.FIELD_A"),
                    "local.FIELD_B": ev.get("local.FIELD_B"),
                    "causal_parent_ids": ev.get("causal_parent_ids") or d.get("causal_parent_ids"),
                    "source_attribution": ev.get("source_attribution"),
                })
    components.sort(key=lambda c: (c.delta_t, c.emitter_agent_id, c.emission_id))
    notes = []
    has_amp = all(
        isinstance(c.amplitude, (int, float)) for c in components
    ) if components else False
    has_pos = all(
        isinstance(c.x, (int, float)) and isinstance(c.y, (int, float)) for c in components
    ) if components else False
    has_cells = all(isinstance(c.cells, tuple) and c.cells for c in components) if components else False
    if has_cells and has_amp:
        recon = "EXACT"
    elif has_amp and has_pos:
        recon = "PARTIAL"
        notes.append("cells NOT_RECORDED in scientific_events — deposit uses spatial origin cell")
    else:
        recon = "INSUFFICIENT"
        notes.append("missing amplitude and/or position")
    # Bidirectional concurrent traffic note
    by_dt = defaultdict(set)
    for c in components:
        by_dt[c.delta_t].add(c.emitter_agent_id)
    both_ticks = sum(1 for emitters in by_dt.values() if len(emitters) >= 2)
    if both_ticks:
        notes.append(
            f"bidirectional concurrent emissions on {both_ticks}/{len(by_dt)} ticks "
            "(both agents emit same tick — not strict turn-taking)"
        )
    eid = stable_id("ep", run_id, start_tick, end_tick, len(components))
    return NaturalSignalEpisode(
        episode_id=eid,
        source_run_id=run_id,
        start_tick=int(start_tick),
        end_tick=int(end_tick),
        components=tuple(components),
        receptions=tuple(receptions),
        reconstruction=recon,
        provenance="SCIENTIFIC_EVENTS",
        notes=tuple(notes),
    )


def reconstruct_reference_episode_1554_1563(
    run_dir: Path | str | None = None,
) -> NaturalSignalEpisode:
    root = Path(run_dir) if run_dir else DEFAULT_REF_RUN
    run_id = root.name
    events = root / "scientific_events.jsonl"
    return load_episode_from_events(
        events, start_tick=REF_START, end_tick=REF_END, run_id=run_id,
    )


def discover_bidirectional_episodes(
    events_path: Path | str,
    *,
    run_id: str,
    max_episodes: int = 24,
    min_duration: int = 3,
    max_gap: int = 2,
    min_both_ticks: int = 3,
) -> list[NaturalSignalEpisode]:
    """Scan for intervals with repeated same-tick bidirectional FIELD emissions."""
    path = Path(events_path)
    # tick -> set of emitters for FIELD_A body_motion
    by_tick: dict[int, list[dict[str, Any]]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("type") != "PHYSICAL_SIGNAL_EMITTED":
                continue
            ev = d.get("evidence") or {}
            ch = str(ev.get("channel") or "A").upper().replace("FIELD_", "")
            if ch != "A":
                continue
            t = int(d["tick"])
            by_tick[t].append(d)

    both_ticks = sorted(
        t for t, evs in by_tick.items()
        if len({(e.get("evidence") or {}).get("emitter_agent_id") or e.get("emitter_agent_id") for e in evs}) >= 2
    )
    if not both_ticks:
        return []

    # Merge into contiguous / near-contiguous intervals
    intervals: list[tuple[int, int]] = []
    start = both_ticks[0]
    prev = both_ticks[0]
    count = 1
    for t in both_ticks[1:]:
        if t - prev <= max_gap + 1:
            prev = t
            count += 1
        else:
            if count >= min_both_ticks and (prev - start + 1) >= min_duration:
                intervals.append((start, prev))
            start = prev = t
            count = 1
    if count >= min_both_ticks and (prev - start + 1) >= min_duration:
        intervals.append((start, prev))

    episodes = []
    seen_sig = set()
    for a, b in intervals:
        ep = load_episode_from_events(path, start_tick=a, end_tick=b, run_id=run_id)
        if ep.reconstruction == "INSUFFICIENT":
            continue
        # Dedup by emitter/amp signature
        sig = (
            ep.duration,
            tuple(round(float(c.amplitude), 2) if isinstance(c.amplitude, (int, float)) else None for c in ep.components[:6]),
            _alternation_count(ep.components),
        )
        if sig in seen_sig:
            continue
        seen_sig.add(sig)
        episodes.append(ep)
        if len(episodes) >= max_episodes:
            break
    return episodes


def group_episode_families(episodes: list[NaturalSignalEpisode]) -> list[dict[str, Any]]:
    buckets: dict[str, list[NaturalSignalEpisode]] = defaultdict(list)
    for ep in episodes:
        both = sum(
            1
            for dt, emitters in _emitters_by_dt(ep).items()
            if len(emitters) >= 2
        )
        dur_bin = "short" if ep.duration <= 5 else ("mid" if ep.duration <= 12 else "long")
        key = f"FIELD_A|both_ticks≈{both}|dur={dur_bin}|recon={ep.reconstruction}"
        buckets[key].append(ep)
    out = []
    for key, members in sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        out.append({
            "family_id": stable_id("efam", key),
            "family_key": key,
            "n_members": len(members),
            "member_ids": [m.episode_id for m in members],
            "why_grouped": f"Physical structure only: {key}",
            "representative_id": members[0].episode_id,
        })
    return out


def _emitters_by_dt(ep: NaturalSignalEpisode) -> dict[int, set[str]]:
    out: dict[int, set[str]] = defaultdict(set)
    for c in ep.components:
        out[int(c.delta_t)].add(c.emitter_agent_id)
    return out


def _world_hw(rt: TwoAgentRuntime) -> tuple[int, int]:
    w = rt.world
    if hasattr(w, "FIELD_A") and w.FIELD_A is not None:
        h, ww = w.FIELD_A.shape
        return int(h), int(ww)
    if hasattr(w, "T") and w.T is not None:
        h, ww = w.T.shape
        return int(h), int(ww)
    return 32, 32


def _deposit_cells_for_component(
    rt: TwoAgentRuntime,
    comp: EpisodeComponent,
) -> list[tuple[int, int]]:
    if isinstance(comp.cells, tuple) and comp.cells:
        return list(comp.cells)
    try:
        h, w = _world_hw(rt)
        iy = int(float(comp.y)) % h
        ix = int(float(comp.x)) % w
        # Small cross approximating body footprint when cells not recorded
        cells = [(iy, ix)]
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            cells.append(((iy + dy) % h, (ix + dx) % w))
        return cells
    except (TypeError, ValueError):
        return []


def _amp(comp: EpisodeComponent) -> float | None:
    try:
        return float(comp.amplitude)
    except (TypeError, ValueError):
        return None


def select_components(
    episode: NaturalSignalEpisode,
    mode: str,
) -> list[EpisodeComponent]:
    comps = list(episode.components)
    if mode in ("FULL_EPISODE", "FULL", "OPEN_LOOP_REPLAY", "DELAYED_EPISODE"):
        return comps
    if mode in ("A_TO_B_ONLY", "A→B"):
        return [c for c in comps if str(c.emitter_agent_id).endswith("0")]
    if mode in ("B_TO_A_ONLY", "B→A"):
        return [c for c in comps if str(c.emitter_agent_id).endswith("1")]
    if mode == "REMOVE_FIRST_A_EMISSION":
        drop = next((c for c in comps if str(c.emitter_agent_id).endswith("0")), None)
        return [c for c in comps if c is not drop]
    if mode == "REMOVE_FIRST_B_RESPONSE":
        drop = next((c for c in comps if str(c.emitter_agent_id).endswith("1")), None)
        return [c for c in comps if c is not drop]
    if mode == "REMOVE_ALTERNATION":
        # Keep only agent_0 stream
        return [c for c in comps if str(c.emitter_agent_id).endswith("0")]
    if mode == "PARTIAL_CLOSED_LOOP":
        # First tick components only
        if not comps:
            return []
        d0 = min(c.delta_t for c in comps)
        return [c for c in comps if c.delta_t == d0]
    if mode == "ISOLATED_COMPONENTS":
        # Same components; caller forces all at delta 0
        return comps
    if mode == "TIMING_SHUFFLED":
        return comps
    if mode == "ORDER_REVERSED":
        return comps
    if mode == "SHAM":
        return comps
    return comps


def schedule_for_mode(
    components: list[EpisodeComponent],
    mode: str,
    *,
    delay: int = 0,
) -> list[tuple[int, EpisodeComponent]]:
    """Return (inject_branch_tick, component) schedule."""
    if not components:
        return []
    if mode == "ISOLATED_COMPONENTS":
        return [(delay, c) for c in components]
    if mode == "TIMING_SHUFFLED":
        dts = sorted({c.delta_t for c in components})
        # Deterministic shuffle: reverse half-swap
        shuffled = dts[1:] + dts[:1] if len(dts) > 1 else dts
        map_dt = {old: shuffled[i] for i, old in enumerate(dts)}
        return [(delay + map_dt[c.delta_t], c) for c in components]
    if mode == "ORDER_REVERSED":
        max_dt = max(c.delta_t for c in components)
        return [(delay + (max_dt - c.delta_t), c) for c in components]
    if mode == "DELAYED_EPISODE":
        return [(delay + 5 + c.delta_t, c) for c in components]
    # FULL / directional / ablations / closed-loop first tick
    return [(delay + c.delta_t, c) for c in components]


def run_episode_branch(
    snapshot: dict[str, Any],
    episode: NaturalSignalEpisode,
    *,
    mode: str,
    horizon: int = 60,
    experiment_id: str,
    intervention_id: str,
) -> dict[str, Any]:
    rt = TwoAgentRuntime.restore(deepcopy(snapshot))
    pre_fp = scientific_fingerprint(rt)
    sham = mode == "SHAM"
    control = mode == "CONTROL"
    comps = [] if control else select_components(episode, mode)
    schedule = [] if control else schedule_for_mode(comps, mode)
    by_tick: dict[int, list[EpisodeComponent]] = defaultdict(list)
    for t, c in schedule:
        by_tick[int(t)].append(c)

    episode_end = max(by_tick.keys()) if by_tick else -1
    traces = []
    injected_log = []
    natural_followups = []
    obs_source = f"exp:{experiment_id}:{intervention_id}:{mode}"

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
                    observer_source_id=obs_source,
                )
                injected_log.append({
                    "branch_tick": i,
                    "component_id": c.component_id,
                    "emitter": c.emitter_agent_id,
                    "channel": c.channel,
                    "amplitude": 0.0 if sham else float(amp),
                    "n_cells": len(cells),
                    "delta_t_orig": c.delta_t,
                })
        # Capture natural emissions before step clears receipt
        rt.step()
        # Natural follow-ups after open-loop window (and always track)
        rec = rt.last_signal_receipt or {}
        for src in rec.get("sources") or []:
            trig = str(src.get("trigger") or "")
            if trig in (TRIGGER_EPISODE_REPLAY, TRIGGER_SHAM, TRIGGER_EXTERNAL):
                continue
            if trig.startswith("EXTERNAL"):
                continue
            natural_followups.append({
                "branch_tick": i + 1,
                "runtime_tick": int(rt.tick),
                "emitter_agent_id": src.get("emitter_agent_id"),
                "channel": src.get("channel"),
                "amplitude": src.get("amplitude") or src.get("realized"),
                "trigger": trig,
                "after_episode_window": i > episode_end,
            })
        s0, s1 = rt.slots[0], rt.slots[1]
        traces.append({
            "branch_tick": i + 1,
            "runtime_tick": int(rt.tick),
            "fingerprint": scientific_fingerprint(rt),
            "agents": [
                {
                    "action": s0.last_selected_action,
                    "selection_source": ((s0.cognition or {}).get("last_selection") or {}).get("source"),
                    "x": float(s0.body.x),
                    "y": float(s0.body.y),
                    "vx": float(getattr(s0.body, "vx", 0.0) or 0.0),
                    "vy": float(getattr(s0.body, "vy", 0.0) or 0.0),
                    "theta": float(getattr(s0.body, "theta", 0.0) or 0.0),
                    "local_fields": receiver_local_fields(rt, 0),
                    "obs_fields": {
                        "local.FIELD_A": (s0.last_agent_observation or {}).get("local.FIELD_A"),
                        "local.FIELD_B": (s0.last_agent_observation or {}).get("local.FIELD_B"),
                    },
                    "observation_leaks": audit_observation_no_intervention_leak(s0.last_agent_observation),
                },
                {
                    "action": s1.last_selected_action,
                    "selection_source": ((s1.cognition or {}).get("last_selection") or {}).get("source"),
                    "x": float(s1.body.x),
                    "y": float(s1.body.y),
                    "vx": float(getattr(s1.body, "vx", 0.0) or 0.0),
                    "vy": float(getattr(s1.body, "vy", 0.0) or 0.0),
                    "theta": float(getattr(s1.body, "theta", 0.0) or 0.0),
                    "local_fields": receiver_local_fields(rt, 1),
                    "obs_fields": {
                        "local.FIELD_A": (s1.last_agent_observation or {}).get("local.FIELD_A"),
                        "local.FIELD_B": (s1.last_agent_observation or {}).get("local.FIELD_B"),
                    },
                    "observation_leaks": audit_observation_no_intervention_leak(s1.last_agent_observation),
                },
            ],
            "contact": bool((rt.last_contact or {}).get("contact")),
            "coupling": _instant_coupling(s0, s1, rt),
        })

    return {
        "arm_id": mode,
        "kind": mode,
        "mode": mode,
        "episode_id": episode.episode_id,
        "experiment_id": experiment_id,
        "intervention_id": intervention_id,
        "pre_fingerprint": pre_fp,
        "n_injected": len(injected_log),
        "injected_log": injected_log,
        "natural_followups": natural_followups,
        "episode_inject_end_tick": episode_end,
        "traces": traces,
        "accepted": True,
    }


def _toroidal_delta(a: float, b: float, size: int) -> float:
    d = (a - b) % size
    if d > size / 2:
        d -= size
    return d


def _instant_coupling(s0, s1, rt: TwoAgentRuntime) -> dict[str, float]:
    h, w = _world_hw(rt)
    dx = _toroidal_delta(float(s0.body.x), float(s1.body.x), int(w))
    dy = _toroidal_delta(float(s0.body.y), float(s1.body.y), int(h))
    dist = math.hypot(dx, dy)
    v0x = float(getattr(s0.body, "vx", 0.0) or 0.0)
    v0y = float(getattr(s0.body, "vy", 0.0) or 0.0)
    v1x = float(getattr(s1.body, "vx", 0.0) or 0.0)
    v1y = float(getattr(s1.body, "vy", 0.0) or 0.0)
    n0 = math.hypot(v0x, v0y)
    n1 = math.hypot(v1x, v1y)
    if n0 > 1e-9 and n1 > 1e-9:
        align = (v0x * v1x + v0y * v1y) / (n0 * n1)
    else:
        align = 0.0
    a0 = s0.last_selected_action
    a1 = s1.last_selected_action
    dir_agree = 1.0 if (
        a0 and a1 and str(a0).startswith("MOVE") and a0 == a1
    ) else 0.0
    neighborhood = 1.0 if dist <= 2.5 else 0.0
    return {
        "inter_agent_distance": dist,
        "velocity_alignment": align,
        "direction_agreement": dir_agree,
        "shared_neighborhood": neighborhood,
    }


def trajectory_coupling_summary(
    traces: list[dict[str, Any]],
    *,
    post_start: int = 1,
) -> dict[str, Any]:
    """Aggregate POST_EPISODE_MOVEMENT_COUPLING over traces[post_start-1:]."""
    rows = [t for t in traces if int(t["branch_tick"]) >= int(post_start)]
    if not rows:
        return {
            "n": 0,
            "mean_distance": None,
            "mean_velocity_alignment": None,
            "direction_agreement_frac": None,
            "co_movement_ticks": 0,
            "neighborhood_frac": None,
        }
    dists = [float(t["coupling"]["inter_agent_distance"]) for t in rows]
    aligns = [float(t["coupling"]["velocity_alignment"]) for t in rows]
    agrees = [float(t["coupling"]["direction_agreement"]) for t in rows]
    neigh = [float(t["coupling"]["shared_neighborhood"]) for t in rows]
    # Co-movement: same MOVE direction and alignment > 0.3
    co = 0
    for t in rows:
        if t["coupling"]["direction_agreement"] >= 1.0 and t["coupling"]["velocity_alignment"] > 0.3:
            co += 1
    return {
        "n": len(rows),
        "mean_distance": sum(dists) / len(dists),
        "mean_velocity_alignment": sum(aligns) / len(aligns),
        "direction_agreement_frac": sum(agrees) / len(agrees),
        "co_movement_ticks": co,
        "neighborhood_frac": sum(neigh) / len(neigh),
        "distance_delta_start_end": dists[-1] - dists[0],
    }


def first_divergences_episode(control: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    ct = control.get("traces") or []
    ot = other.get("traces") or []
    n = min(len(ct), len(ot))

    def first(pred) -> int | None:
        for i in range(n):
            if pred(ct[i], ot[i]):
                return int(ct[i]["branch_tick"])
        return None

    return {
        "observation_field": first(
            lambda a, b: any(
                (a["agents"][j]["obs_fields"] != b["agents"][j]["obs_fields"])
                or (a["agents"][j]["local_fields"] != b["agents"][j]["local_fields"])
                for j in (0, 1)
            )
        ),
        "cognition_selection_source": first(
            lambda a, b: any(
                a["agents"][j]["selection_source"] != b["agents"][j]["selection_source"]
                for j in (0, 1)
            )
        ),
        "action": first(
            lambda a, b: any(a["agents"][j]["action"] != b["agents"][j]["action"] for j in (0, 1))
        ),
        "trajectory": first(
            lambda a, b: any(
                abs(a["agents"][j]["x"] - b["agents"][j]["x"]) > 1e-6
                or abs(a["agents"][j]["y"] - b["agents"][j]["y"]) > 1e-6
                for j in (0, 1)
            )
        ),
        "coupling_distance": first(
            lambda a, b: abs(
                a["coupling"]["inter_agent_distance"] - b["coupling"]["inter_agent_distance"]
            ) > 1e-4
        ),
        "coupling_alignment": first(
            lambda a, b: abs(
                a["coupling"]["velocity_alignment"] - b["coupling"]["velocity_alignment"]
            ) > 1e-4
        ),
        "contact": first(lambda a, b: bool(a.get("contact")) != bool(b.get("contact"))),
    }


@dataclass
class EpisodeScreenConfig:
    max_episodes: int = 8
    stage_a_seeds: tuple[int, ...] = (17, 19)
    stage_b_seeds: tuple[int, ...] = (17, 19, 23)
    horizon: int = 80
    post_horizon_start: int | None = None  # default = episode duration
    max_s0_search: int = 350
    min_s0_age: int = 30
    promote_on_downstream: bool = True


def _find_s0(seed: int, cfg: EpisodeScreenConfig) -> dict[str, Any] | None:
    s0 = find_matched_s0(
        seed=int(seed),
        receiver="agent_1",
        pre_action="WAIT",
        pre_selection_source="RETAINED_PREDICTION",
        require_no_contact=True,
        max_search=cfg.max_s0_search,
        min_age=cfg.min_s0_age,
    )
    if s0 is None:
        s0 = find_matched_s0(
            seed=int(seed),
            receiver="agent_0",
            pre_action="MOVE:E",
            pre_selection_source="ENDOGENOUS_VARIATION",
            require_no_contact=True,
            max_search=cfg.max_s0_search,
            min_age=cfg.min_s0_age,
        )
    return s0


def run_episode_trial_suite(
    episode: NaturalSignalEpisode,
    *,
    seed: int,
    cfg: EpisodeScreenConfig | None = None,
    modes: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    cfg = cfg or EpisodeScreenConfig()
    modes = modes or (
        "CONTROL", "SHAM", "FULL_EPISODE",
        "A_TO_B_ONLY", "B_TO_A_ONLY",
        "ISOLATED_COMPONENTS", "TIMING_SHUFFLED", "ORDER_REVERSED",
    )
    s0 = _find_s0(seed, cfg)
    if s0 is None:
        return {"accepted": False, "error": "no_matched_s0", "seed": seed}
    experiment_id = stable_id("eptrial", episode.episode_id, seed)
    snap = s0["snapshot"]
    arms = {}
    for mode in modes:
        arms[mode] = run_episode_branch(
            snap, episode, mode=mode, horizon=cfg.horizon,
            experiment_id=experiment_id, intervention_id=stable_id("i", mode, seed),
        )
    # CONTROL/CONTROL
    c2 = run_episode_branch(
        snap, episode, mode="CONTROL", horizon=min(20, cfg.horizon),
        experiment_id=experiment_id, intervention_id="cc",
    )
    ctrl_eq = all(
        fingerprint_equal(a["fingerprint"], b["fingerprint"])
        for a, b in zip(arms["CONTROL"]["traces"][:20], c2["traces"])
    )
    post_start = cfg.post_horizon_start or (episode.duration + 1)
    coupling = {
        m: trajectory_coupling_summary(arms[m]["traces"], post_start=post_start)
        for m in arms
    }
    divs = {
        m: first_divergences_episode(arms["CONTROL"], arms[m])
        for m in arms if m != "CONTROL"
    }
    any_leak = any(
        agent.get("observation_leaks")
        for arm in arms.values()
        for t in (arm.get("traces") or [])
        for agent in t.get("agents") or []
    )
    # Downstream if cognition/action/trajectory/coupling diverge vs control and not sham-only
    sham_div = divs.get("SHAM") or {}
    full_div = divs.get("FULL_EPISODE") or {}

    def real_down(key: str) -> bool:
        return full_div.get(key) is not None and sham_div.get(key) is None

    levels = {
        "L1_exposure": full_div.get("observation_field") is not None,
        "L2_cognition": real_down("cognition_selection_source"),
        "L3_action": real_down("action"),
        "L4_trajectory": real_down("trajectory"),
        "L5_coupling": (
            real_down("coupling_distance") or real_down("coupling_alignment")
        ),
    }
    # Coupling magnitude vs control
    c_full = coupling.get("FULL_EPISODE") or {}
    c_ctrl = coupling.get("CONTROL") or {}
    c_sham = coupling.get("SHAM") or {}
    coupling_delta = None
    if c_full.get("mean_distance") is not None and c_ctrl.get("mean_distance") is not None:
        coupling_delta = {
            "distance_vs_control": c_full["mean_distance"] - c_ctrl["mean_distance"],
            "alignment_vs_control": (
                (c_full.get("mean_velocity_alignment") or 0)
                - (c_ctrl.get("mean_velocity_alignment") or 0)
            ),
            "co_movement_vs_control": (
                (c_full.get("co_movement_ticks") or 0) - (c_ctrl.get("co_movement_ticks") or 0)
            ),
            "distance_vs_sham": (
                c_full["mean_distance"] - (c_sham.get("mean_distance") or c_full["mean_distance"])
            ),
        }

    return {
        "accepted": True,
        "seed": seed,
        "s0_tick": s0["tick"],
        "context_label": "matched_S0",
        "episode_id": episode.episode_id,
        "control_control_equal": ctrl_eq,
        "divergences": divs,
        "coupling": coupling,
        "coupling_delta_full_vs_control": coupling_delta,
        "levels": levels,
        "any_leak": any_leak,
        "natural_followups_full": arms.get("FULL_EPISODE", {}).get("natural_followups") or [],
        "arms_n_injected": {m: arms[m].get("n_injected") for m in arms},
        # Keep traces only for key arms to bound artifact size
        "traces_compact": {
            m: {
                "n": len(arms[m]["traces"]),
                "final_actions": [
                    arms[m]["traces"][-1]["agents"][0]["action"] if arms[m]["traces"] else None,
                    arms[m]["traces"][-1]["agents"][1]["action"] if arms[m]["traces"] else None,
                ],
                "final_coupling": arms[m]["traces"][-1]["coupling"] if arms[m]["traces"] else None,
            }
            for m in arms
        },
    }


def run_partial_closed_loop_probe(
    episode: NaturalSignalEpisode,
    *,
    seed: int = 17,
    cfg: EpisodeScreenConfig | None = None,
) -> dict[str, Any]:
    cfg = cfg or EpisodeScreenConfig()
    s0 = _find_s0(seed, cfg)
    if s0 is None:
        return {"accepted": False, "error": "no_s0"}
    eid = stable_id("cloop", episode.episode_id, seed)
    open_loop = run_episode_branch(
        s0["snapshot"], episode, mode="FULL_EPISODE", horizon=cfg.horizon,
        experiment_id=eid, intervention_id="open",
    )
    closed = run_episode_branch(
        s0["snapshot"], episode, mode="PARTIAL_CLOSED_LOOP", horizon=cfg.horizon,
        experiment_id=eid, intervention_id="closed",
    )
    control = run_episode_branch(
        s0["snapshot"], episode, mode="CONTROL", horizon=cfg.horizon,
        experiment_id=eid, intervention_id="ctrl",
    )
    # Did closed-loop elicit natural subsequent emissions from the other agent?
    closed_fu = [
        f for f in (closed.get("natural_followups") or [])
        if f.get("after_episode_window") or int(f.get("branch_tick") or 0) > 1
    ]
    ctrl_fu = closed_fu  # compare counts vs control
    ctrl_n = len(control.get("natural_followups") or [])
    closed_n = len(closed.get("natural_followups") or [])
    open_n = len(open_loop.get("natural_followups") or [])
    chain = closed_n > ctrl_n + 1
    return {
        "accepted": True,
        "seed": seed,
        "open_loop_n_injected": open_loop.get("n_injected"),
        "closed_loop_n_injected": closed.get("n_injected"),
        "natural_followups": {
            "CONTROL": ctrl_n,
            "OPEN_LOOP": open_n,
            "PARTIAL_CLOSED_LOOP": closed_n,
        },
        "INTERACTION_CHAIN_CANDIDATE": bool(chain),
        "divergences_closed_vs_control": first_divergences_episode(control, closed),
        "divergences_open_vs_control": first_divergences_episode(control, open_loop),
        "honesty": {"not_conversation": True},
    }


def geometry_flow_snapshot(rt: TwoAgentRuntime) -> dict[str, Any]:
    """Conservative confound covariates at S0."""
    out = {"agents": []}
    for i, slot in enumerate(rt.slots):
        body = slot.body
        out["agents"].append({
            "slot": i,
            "x": float(body.x),
            "y": float(body.y),
            "vx": float(getattr(body, "vx", 0.0) or 0.0),
            "vy": float(getattr(body, "vy", 0.0) or 0.0),
            "theta": float(getattr(body, "theta", 0.0) or 0.0),
            "action": slot.last_selected_action,
        })
    out["contact"] = bool((rt.last_contact or {}).get("contact"))
    # Local flow from planet if present
    try:
        planet = rt.world
        ax = out["agents"][0]
        h, w = _world_hw(rt)
        iy, ix = int(ax["y"]) % h, int(ax["x"]) % w
        for name in ("vx", "vy", "flow_x", "flow_y"):
            arr = getattr(planet, name, None)
            if arr is not None:
                out[f"planet_{name}_at_agent0"] = float(arr[iy, ix])
    except Exception:
        pass
    return out


def temporal_strip(episode: NaturalSignalEpisode) -> dict[str, Any]:
    """Compact tick strip for Observer visualization."""
    ticks = list(range(episode.start_tick, episode.end_tick + 1))
    a_row = []
    b_row = []
    field = []
    by_dt = defaultdict(list)
    for c in episode.components:
        by_dt[c.delta_t].append(c)
    for i, t in enumerate(ticks):
        comps = by_dt.get(i, [])
        emitters = {c.emitter_agent_id for c in comps}
        a_row.append("→" if any(str(e).endswith("0") for e in emitters) else "")
        b_row.append("←" if any(str(e).endswith("1") for e in emitters) else "")
        n = len(comps)
        field.append("A" * n if n else "")
    return {
        "ticks": ticks,
        "A": a_row,
        "B": b_row,
        "FIELD": field,
        "note": "Physical emission strip — not a dialogue transcript",
    }
