"""Deterministic SignalEpisode grouping from PHYSICAL_SIGNAL_RECEIVED events."""
from __future__ import annotations

import hashlib
import math
from typing import Any, Iterable


# Intensity below this is treated as silence for episode boundaries.
DEFAULT_FLOOR = 1e-6
# Allow this many quiet ticks inside an episode before closing.
DEFAULT_GAP_TOLERANCE = 2
# Cap open episode duration (bounded memory / determinism).
MAX_EPISODE_DURATION = 64


def _ev(ev: dict[str, Any]) -> dict[str, Any]:
    e = ev.get("evidence")
    return e if isinstance(e, dict) else {}


def _receiver(ev: dict[str, Any]) -> str:
    evidence = _ev(ev)
    return str(
        ev.get("receiver_agent_id")
        or evidence.get("receiver_agent_id")
        or evidence.get("observer_receiver_id")
        or ev.get("agent_id")
        or "UNKNOWN"
    )


def _body(ev: dict[str, Any]) -> str:
    evidence = _ev(ev)
    return str(
        ev.get("receiver_body_id")
        or evidence.get("receiver_body_id")
        or evidence.get("body_id")
        or "UNKNOWN"
    )


def _intensities(ev: dict[str, Any]) -> tuple[float, float]:
    evidence = _ev(ev)
    a = float(evidence.get("local.FIELD_A") or 0.0)
    b = float(evidence.get("local.FIELD_B") or 0.0)
    return a, b


def _channel(a: float, b: float, *, floor: float) -> str:
    ha = a > floor
    hb = b > floor
    if ha and hb:
        return "MIXED"
    if ha:
        return "FIELD_A"
    if hb:
        return "FIELD_B"
    return "UNKNOWN"


def _attribution(ev: dict[str, Any]) -> str:
    evidence = _ev(ev)
    return str(
        evidence.get("source_attribution")
        or ev.get("source_attribution")
        or "UNKNOWN"
    )


def _parents(ev: dict[str, Any]) -> list[str]:
    evidence = _ev(ev)
    raw = ev.get("causal_parent_ids") or evidence.get("causal_parent_ids") or []
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if x is not None]


def _contributions(ev: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = _ev(ev)
    raw = evidence.get("contributing_emissions_this_tick") or []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for c in raw:
        if isinstance(c, dict):
            out.append(
                {
                    "emission_id": c.get("emission_id"),
                    "channel": c.get("channel"),
                    "emitter_agent_id": c.get("emitter_agent_id"),
                    "trigger": c.get("trigger"),
                    "origin_kind": c.get("origin_kind"),
                }
            )
    return out


def stable_episode_id(
    *,
    run_id: str,
    receiver_agent_id: str,
    start_tick: int,
    channel: str,
    peak_tick: int,
) -> str:
    raw = f"{run_id}|{receiver_agent_id}|{start_tick}|{channel}|{peak_tick}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"sigep-{digest}"


def _finalize(
    buf: list[dict[str, Any]],
    *,
    run_id: str,
    generation: int | None,
    floor: float,
) -> dict[str, Any]:
    ticks = [int(r["tick"]) for r in buf]
    intensities = [float(r["intensity"]) for r in buf]
    peak_i = max(range(len(intensities)), key=lambda i: intensities[i])
    peak_tick = ticks[peak_i]
    peak_val = intensities[peak_i]
    channel = buf[peak_i]["channel"]
    # Prefer MIXED if any tick was MIXED
    if any(r["channel"] == "MIXED" for r in buf):
        channel = "MIXED"
    elif any(r["channel"] == "FIELD_A" for r in buf) and any(r["channel"] == "FIELD_B" for r in buf):
        channel = "MIXED"

    receiver = buf[0]["receiver_agent_id"]
    body = buf[0]["receiver_body_id"]
    parents: list[str] = []
    contribs: list[dict[str, Any]] = []
    emitter_agents: set[str] = set()
    triggers: set[str] = set()
    attrs: set[str] = set()
    self_n = 0
    cross_n = 0
    for r in buf:
        for p in r["parents"]:
            if p not in parents:
                parents.append(p)
        for c in r["contributions"]:
            contribs.append(c)
            ea = c.get("emitter_agent_id")
            if ea:
                emitter_agents.add(str(ea))
                if str(ea) == receiver:
                    self_n += 1
                else:
                    cross_n += 1
            if c.get("trigger"):
                triggers.add(str(c["trigger"]))
        attrs.add(r["attribution"])

    total_contrib = self_n + cross_n
    if total_contrib > 0:
        self_frac: float | None = self_n / total_contrib
        cross_frac: float | None = cross_n / total_contrib
    else:
        self_frac = None
        cross_frac = None

    if "MIXED" in attrs or len(emitter_agents) > 1:
        attribution = "MIXED"
    elif len(emitter_agents) == 1 and self_n == 0 and cross_n > 0:
        attribution = "UNIQUE"
    elif "NOT_UNIQUELY_ATTRIBUTABLE" in attrs:
        attribution = "NOT_UNIQUELY_ATTRIBUTABLE"
    elif len(emitter_agents) == 1:
        attribution = "UNIQUE" if cross_n == 0 or self_n == 0 else "MIXED"
    else:
        attribution = "UNKNOWN"

    mean_i = sum(intensities) / len(intensities)
    var_i = sum((x - mean_i) ** 2 for x in intensities) / len(intensities)
    ep_id = stable_episode_id(
        run_id=run_id,
        receiver_agent_id=receiver,
        start_tick=ticks[0],
        channel=channel,
        peak_tick=peak_tick,
    )
    return {
        "episode_id": ep_id,
        "run_id": run_id,
        "generation": generation,
        "receiver_agent_id": receiver,
        "receiver_body_id": body,
        "start_tick": ticks[0],
        "peak_tick": peak_tick,
        "end_tick": ticks[-1],
        "duration": ticks[-1] - ticks[0] + 1,
        "n_receptions": len(buf),
        "channel": channel,
        "intensity": {
            "start": intensities[0],
            "peak": peak_val,
            "mean": mean_i,
            "integral": sum(intensities),
            "variance": var_i,
        },
        "contributing_emission_ids": parents[:64],
        "contributing_agent_ids": sorted(emitter_agents)[:8],
        "attribution": attribution,
        "trigger_composition": sorted(triggers) or ["other"],
        "self_contribution_fraction": self_frac,
        "cross_agent_contribution_fraction": cross_frac,
        "spatial_gradient": "NOT_AVAILABLE",
        "local_field_vector": "NOT_AVAILABLE",
        "honesty": {
            "observer_only": True,
            "no_communication_claim": True,
            "superposition_limits_sender_identity": True,
        },
    }


def iter_reception_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ev in events:
        t = str(ev.get("type") or ev.get("kind") or "")
        if t != "PHYSICAL_SIGNAL_RECEIVED":
            continue
        tick = int(ev.get("tick") or -1)
        if tick < 0:
            continue
        a, b = _intensities(ev)
        intensity = a + b
        out.append(
            {
                "tick": tick,
                "receiver_agent_id": _receiver(ev),
                "receiver_body_id": _body(ev),
                "channel": _channel(a, b, floor=DEFAULT_FLOOR),
                "intensity": intensity,
                "field_a": a,
                "field_b": b,
                "attribution": _attribution(ev),
                "parents": _parents(ev),
                "contributions": _contributions(ev),
            }
        )
    out.sort(key=lambda r: (r["receiver_agent_id"], r["tick"]))
    return out


def group_signal_episodes(
    events: Iterable[dict[str, Any]],
    *,
    run_id: str = "unknown",
    generation: int | None = None,
    floor: float = DEFAULT_FLOOR,
    gap_tolerance: int = DEFAULT_GAP_TOLERANCE,
    max_duration: int = MAX_EPISODE_DURATION,
    min_peak: float | None = None,
) -> list[dict[str, Any]]:
    """Group consecutive receptions per receiver into deterministic episodes.

    Criteria (objective):
    - same receiver_agent_id
    - intensity > floor
    - tick gaps ≤ gap_tolerance
    - duration capped at max_duration
    Optional min_peak filters low-informativeness episodes after grouping.
    """
    rows = iter_reception_events(events)
    episodes: list[dict[str, Any]] = []
    by_agent: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if float(r["intensity"]) <= floor:
            continue
        by_agent.setdefault(str(r["receiver_agent_id"]), []).append(r)

    for _aid, seq in sorted(by_agent.items()):
        buf: list[dict[str, Any]] = []
        last_tick: int | None = None
        for r in seq:
            t = int(r["tick"])
            if not buf:
                buf = [r]
                last_tick = t
                continue
            assert last_tick is not None
            gap = t - last_tick
            dur = t - int(buf[0]["tick"]) + 1
            if gap <= gap_tolerance + 1 and dur <= max_duration:
                buf.append(r)
                last_tick = t
            else:
                episodes.append(
                    _finalize(buf, run_id=run_id, generation=generation, floor=floor)
                )
                buf = [r]
                last_tick = t
        if buf:
            episodes.append(
                _finalize(buf, run_id=run_id, generation=generation, floor=floor)
            )

    if min_peak is not None:
        episodes = [
            e for e in episodes if float(e["intensity"]["peak"]) >= float(min_peak)
        ]
    episodes.sort(key=lambda e: (int(e["start_tick"]), str(e["receiver_agent_id"])))
    return episodes


def episode_informativeness(
    episode: dict[str, Any],
    *,
    baseline_mean: float,
    baseline_std: float,
    percentile: float | None = None,
) -> dict[str, Any]:
    """Physical informativeness features — not semantic importance."""
    peak = float(episode["intensity"]["peak"])
    mean = float(episode["intensity"]["mean"])
    integral = float(episode["intensity"]["integral"])
    z = 0.0
    if baseline_std > 1e-12:
        z = (peak - baseline_mean) / baseline_std
    return {
        "peak": peak,
        "mean": mean,
        "integral": integral,
        "deviation_from_baseline": peak - baseline_mean,
        "z_score_vs_baseline": z,
        "intensity_percentile": percentile,
        "channel": episode.get("channel"),
        "cross_agent_contribution_fraction": episode.get("cross_agent_contribution_fraction"),
        "trigger_composition": episode.get("trigger_composition"),
        "onset_tick": episode.get("start_tick"),
        "offset_tick": episode.get("end_tick"),
        "interesting_if": "peak above local baseline / high percentile — not mere RECEIVED existence",
    }
