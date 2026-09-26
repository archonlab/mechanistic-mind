"""Analyzer vision forensics — optical provenance without runtime mutation.

Consumes OpticalTickSnapshot series (from fixtures, live GT, or compact scientific
archive). Never modifies world/cognition/vision equations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

EVIDENCE = (
    "OBSERVED",
    "DERIVED",
    "DERIVED_COUNTERFACTUAL_PHYSICAL",
    "CAUSALLY_LINKED",
    "TEMPORALLY_ASSOCIATED",
    "DIRECT_CAUSAL_LINK",
    "NOT_ESTABLISHED",
    "NOT_AVAILABLE",
)


@dataclass
class OpticalNeighbor:
    cell: list[int]
    inside_fov: bool
    surface_response: float
    body_optical: float
    composed_optical: float
    final_contribution: float
    relative_angle_deg: float = 0.0
    source_body_ids: list[str] = field(default_factory=list)  # OBSERVER_GT_ONLY


@dataclass
class OpticalTickSnapshot:
    """One observer tick of physical vision GT (analysis-facing)."""

    tick: int
    observer_body_id: str
    observer_agent_id: str = ""
    theta: float = 0.0
    exo: dict[str, float] = field(default_factory=dict)
    illumination: float = 0.0
    vision_enabled: bool = True
    body_optics_enabled: bool = True
    illumination_enabled: bool = True
    neighbors: list[OpticalNeighbor] = field(default_factory=list)
    contact: bool = False
    field_reception: bool = False
    action: str | None = None
    scenario_selected: str | None = None
    regime_id: str = "default"
    coverage: str = "CONTIGUOUS"  # CONTIGUOUS | SPARSE | GAP
    # Counterfactual exo without selected foreign body (optional precomputed)
    exo_without_body: dict[str, float] | None = None
    selected_source_body_id: str | None = None  # GT attribution for this tick's foreign focus


def snapshot_from_sample(
    *,
    tick: int,
    sample: dict[str, Any],
    observer_body_id: str,
    observer_agent_id: str = "",
    source_body_ids_by_cell: dict[tuple[int, int], list[str]] | None = None,
    contact: bool = False,
    field_reception: bool = False,
    action: str | None = None,
    scenario_selected: str | None = None,
    regime_id: str = "default",
    coverage: str = "CONTIGUOUS",
    vision_enabled: bool = True,
    body_optics_enabled: bool = True,
    exo_without_body: dict[str, float] | None = None,
    selected_source_body_id: str | None = None,
) -> OpticalTickSnapshot:
    """Build analysis snapshot from sample_near_field output (no runtime write)."""
    src_map = source_body_ids_by_cell or {}
    neighbors: list[OpticalNeighbor] = []
    for row in sample.get("neighbors") or []:
        cell = list(row.get("cell") or [0, 0])
        ix, iy = int(cell[0]), int(cell[1])
        key = (iy, ix)
        neighbors.append(
            OpticalNeighbor(
                cell=[ix, iy],
                inside_fov=bool(row.get("inside_fov")),
                surface_response=float(row.get("surface_response") or 0.0),
                body_optical=float(row.get("body_optical") or 0.0),
                composed_optical=float(row.get("composed_optical") or row.get("surface_response") or 0.0),
                final_contribution=float(row.get("final_contribution") or 0.0),
                relative_angle_deg=float(row.get("relative_angle_deg") or 0.0),
                source_body_ids=list(src_map.get(key) or []),
            )
        )
    return OpticalTickSnapshot(
        tick=int(tick),
        observer_body_id=str(observer_body_id),
        observer_agent_id=str(observer_agent_id),
        theta=float(sample.get("body_theta") or 0.0),
        exo={k: float(v) for k, v in (sample.get("fragments") or {}).items()},
        illumination=float(sample.get("illumination") or 0.0),
        vision_enabled=bool(vision_enabled),
        body_optics_enabled=bool(body_optics_enabled and sample.get("body_optical_enabled", True)),
        illumination_enabled=bool(sample.get("illumination_enabled", True)),
        neighbors=neighbors,
        contact=bool(contact),
        field_reception=bool(field_reception),
        action=action,
        scenario_selected=scenario_selected,
        regime_id=str(regime_id),
        coverage=str(coverage),
        exo_without_body=exo_without_body,
        selected_source_body_id=selected_source_body_id,
    )


def contributing_source_bodies(snap: OpticalTickSnapshot) -> set[str]:
    out: set[str] = set()
    for n in snap.neighbors:
        if n.body_optical > 0.0 and n.inside_fov and n.final_contribution > 0.0:
            out.update(n.source_body_ids)
    if snap.selected_source_body_id and any(
        n.body_optical > 0.0 and n.inside_fov for n in snap.neighbors
    ):
        out.add(snap.selected_source_body_id)
    return out


BODY_OPTICAL_EPS = 1e-12


def body_optical_active(snap: OpticalTickSnapshot) -> bool:
    """BODY_OPTICAL_EXPOSURE: surviving body-derived exo contribution > float dust."""
    if not snap.vision_enabled or not snap.body_optics_enabled:
        return False
    # Prefer counterfactual exo delta when available (matches scientific compact).
    if snap.exo_without_body is not None:
        delta = exo_delta(snap.exo, snap.exo_without_body)
        total = sum(max(0.0, float(v)) for v in delta.values())
        return total > BODY_OPTICAL_EPS
    # Legacy: body_opt must survive into final_contribution inside FOV (not DET alone).
    return any(
        n.body_optical > 0.0 and n.inside_fov and n.final_contribution > 0.0
        for n in snap.neighbors
    )


def dominant_exo_channel(exo: dict[str, float]) -> str | None:
    if not exo:
        return None
    return max(exo.items(), key=lambda kv: kv[1])[0]


def exo_delta(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    keys = set(a) | set(b)
    return {k: float(a.get(k, 0.0) - b.get(k, 0.0)) for k in sorted(keys)}


def channel_overlap(snap: OpticalTickSnapshot) -> str:
    vis = body_optical_active(snap)
    if not vis:
        return "NO_BODY_VISION"
    if snap.contact and snap.field_reception:
        return "VISION_PLUS_FIELD_PLUS_CONTACT"
    if snap.field_reception:
        return "VISION_WITH_SIGNAL"
    if snap.contact:
        return "VISION_PLUS_CONTACT"
    return "VISION_WITHOUT_CONTACT"


def build_visual_events(ticks: list[OpticalTickSnapshot]) -> list[dict[str, Any]]:
    """Detect BODY_VISUAL_ENTRY / EXIT / BODY_OPTICAL_CONTRIBUTION / VISUAL_SENSOR_CHANGE."""
    events: list[dict[str, Any]] = []
    prev_active: dict[str, set[str]] = {}  # observer -> source bodies
    prev_exo: dict[str, dict[str, float]] = {}
    for snap in sorted(ticks, key=lambda s: s.tick):
        if snap.coverage == "GAP":
            # Break continuity — do not invent events across gaps
            prev_active[snap.observer_body_id] = set()
            prev_exo[snap.observer_body_id] = {}
            continue
        oid = snap.observer_body_id
        active = contributing_source_bodies(snap) if body_optical_active(snap) else set()
        # If GT ids missing but body optical present, use anonymous placeholder
        if body_optical_active(snap) and not active and snap.selected_source_body_id:
            active = {snap.selected_source_body_id}
        if body_optical_active(snap) and not active:
            active = {"foreign_body_anonymous"}
        was = prev_active.get(oid, set())
        for sid in sorted(active - was):
            events.append({
                "type": "BODY_VISUAL_ENTRY",
                "tick": snap.tick,
                "observer_body_id": oid,
                "observer_agent_id": snap.observer_agent_id,
                "source_body_id": sid,
                "source_identity_layer": "OBSERVER_GT_ONLY",
                "evidence_class": "OBSERVED",
                "regime_id": snap.regime_id,
                "channel_overlap": channel_overlap(snap),
                "exo": dict(snap.exo),
                "illumination": snap.illumination,
                "dominant_exo": dominant_exo_channel(snap.exo),
                "mechanisms": {
                    "physical_near_field_vision": snap.vision_enabled,
                    "physical_body_optical_response": snap.body_optics_enabled,
                    "illumination_cycle": snap.illumination_enabled,
                },
            })
        for sid in sorted(was - active):
            events.append({
                "type": "BODY_VISUAL_EXIT",
                "tick": snap.tick,
                "observer_body_id": oid,
                "source_body_id": sid,
                "source_identity_layer": "OBSERVER_GT_ONLY",
                "evidence_class": "OBSERVED",
                "regime_id": snap.regime_id,
            })
        if active:
            events.append({
                "type": "BODY_OPTICAL_CONTRIBUTION",
                "tick": snap.tick,
                "observer_body_id": oid,
                "source_body_ids": sorted(active),
                "source_identity_layer": "OBSERVER_GT_ONLY",
                "evidence_class": "OBSERVED",
                "n_body_optical_neighbors": sum(1 for n in snap.neighbors if n.body_optical > 0),
                "peak_body_optical": max((n.body_optical for n in snap.neighbors), default=0.0),
                "exo": dict(snap.exo),
                "regime_id": snap.regime_id,
                "channel_overlap": channel_overlap(snap),
            })
        prev = prev_exo.get(oid)
        if prev is not None and snap.exo != prev:
            events.append({
                "type": "VISUAL_SENSOR_CHANGE",
                "tick": snap.tick,
                "observer_body_id": oid,
                "evidence_class": "OBSERVED",
                "exo_delta": exo_delta(snap.exo, prev),
                "exo": dict(snap.exo),
                "body_optical_active": bool(active),
            })
        prev_active[oid] = active
        prev_exo[oid] = dict(snap.exo)
    return events


def build_exposure_episodes(ticks: list[OpticalTickSnapshot]) -> list[dict[str, Any]]:
    """Group contiguous contributing ticks; sparse gaps break episodes."""
    episodes: list[dict[str, Any]] = []
    open_ep: dict[tuple[str, str], dict[str, Any]] = {}

    def close(key: tuple[str, str], end_tick: int, *, gap_break: bool = False) -> None:
        ep = open_ep.pop(key, None)
        if not ep:
            return
        ep["end_tick"] = end_tick
        ep["observed_contiguous_duration"] = int(end_tick) - int(ep["start_tick"]) + 1
        if ep.get("had_gap") or gap_break:
            ep["true_duration"] = "NOT_AVAILABLE"
            ep["coverage_status"] = "SPARSE"
            ep["first_event_wording"] = "FIRST OBSERVED"
        else:
            ep["true_duration"] = ep["observed_contiguous_duration"]
            ep["coverage_status"] = "CONTIGUOUS"
            ep["first_event_wording"] = "FIRST OBSERVED" if ep.get("incomplete_prefix") else "OBSERVED"
        ep["peak_body_optical"] = max(ep.get("_peaks") or [0.0])
        ep["exo_delta_peak"] = ep.get("_exo_peak") or {}
        ep.pop("_peaks", None)
        ep.pop("_exo_peak", None)
        episodes.append(ep)

    sorted_ticks = sorted(ticks, key=lambda s: (s.observer_body_id, s.tick))
    for snap in sorted_ticks:
        oid = snap.observer_body_id
        if snap.coverage == "GAP":
            for key in list(open_ep):
                if key[0] == oid:
                    close(key, snap.tick - 1, gap_break=True)
            continue
        active = contributing_source_bodies(snap) if body_optical_active(snap) else set()
        if body_optical_active(snap) and not active:
            active = {snap.selected_source_body_id or "foreign_body_anonymous"}
        # close ended
        for key in list(open_ep):
            if key[0] == oid and key[1] not in active:
                close(key, snap.tick - 1)
        for sid in active:
            key = (oid, sid)
            if key not in open_ep:
                open_ep[key] = {
                    "type": "VISUAL_EXPOSURE_EPISODE",
                    "observer_body_id": oid,
                    "observer_agent_id": snap.observer_agent_id,
                    "source_body_id": sid,
                    "source_identity_layer": "OBSERVER_GT_ONLY",
                    "start_tick": snap.tick,
                    "regime_id": snap.regime_id,
                    "channel_overlap_set": set(),
                    "fov_sectors": set(),
                    "illumination_min": snap.illumination,
                    "illumination_max": snap.illumination,
                    "theta_min": snap.theta,
                    "theta_max": snap.theta,
                    "_peaks": [],
                    "had_gap": False,
                    "incomplete_prefix": False,
                    "mechanisms_at_start": {
                        "physical_near_field_vision": snap.vision_enabled,
                        "physical_body_optical_response": snap.body_optics_enabled,
                        "illumination_cycle": snap.illumination_enabled,
                    },
                }
            ep = open_ep[key]
            if ep["regime_id"] != snap.regime_id:
                # Regime boundary: close and reopen
                close(key, snap.tick - 1)
                open_ep[key] = {
                    "type": "VISUAL_EXPOSURE_EPISODE",
                    "observer_body_id": oid,
                    "observer_agent_id": snap.observer_agent_id,
                    "source_body_id": sid,
                    "source_identity_layer": "OBSERVER_GT_ONLY",
                    "start_tick": snap.tick,
                    "regime_id": snap.regime_id,
                    "channel_overlap_set": set(),
                    "fov_sectors": set(),
                    "illumination_min": snap.illumination,
                    "illumination_max": snap.illumination,
                    "theta_min": snap.theta,
                    "theta_max": snap.theta,
                    "_peaks": [],
                    "had_gap": False,
                    "incomplete_prefix": False,
                    "mechanisms_at_start": {
                        "physical_near_field_vision": snap.vision_enabled,
                        "physical_body_optical_response": snap.body_optics_enabled,
                        "illumination_cycle": snap.illumination_enabled,
                    },
                }
                ep = open_ep[key]
            ep["channel_overlap_set"].add(channel_overlap(snap))
            dom = dominant_exo_channel(snap.exo)
            if dom:
                ep["fov_sectors"].add(dom)
            ep["illumination_min"] = min(ep["illumination_min"], snap.illumination)
            ep["illumination_max"] = max(ep["illumination_max"], snap.illumination)
            ep["theta_min"] = min(ep["theta_min"], snap.theta)
            ep["theta_max"] = max(ep["theta_max"], snap.theta)
            ep["_peaks"].append(max((n.body_optical for n in snap.neighbors), default=0.0))
            if snap.coverage == "SPARSE":
                ep["had_gap"] = True
        # end loop
    # close remaining
    if sorted_ticks:
        last_by_obs = {}
        for snap in sorted_ticks:
            last_by_obs[snap.observer_body_id] = snap.tick
        for key in list(open_ep):
            close(key, last_by_obs.get(key[0], open_ep[key]["start_tick"]))

    # serialize sets
    for ep in episodes:
        ep["channel_overlaps"] = sorted(ep.pop("channel_overlap_set", set()))
        ep["dominant_sensor_channels"] = sorted(ep.pop("fov_sectors", set()))
        ep["vision_only"] = ep["channel_overlaps"] in (["VISION_ONLY"], ["VISION_WITHOUT_CONTACT"])
        ep["vision_without_contact"] = ep["vision_only"]
    return episodes


def build_visual_causal_chains(
    ticks: list[OpticalTickSnapshot],
    *,
    max_chains: int = 12,
) -> list[dict[str, Any]]:
    chains: list[dict[str, Any]] = []
    for snap in ticks:
        if snap.coverage == "GAP" or not body_optical_active(snap):
            continue
        sources = contributing_source_bodies(snap)
        if not sources and snap.selected_source_body_id:
            sources = {snap.selected_source_body_id}
        if not sources:
            sources = {"foreign_body_anonymous"}
        for sid in sorted(sources):
            contrib_cells = [
                n for n in snap.neighbors
                if n.body_optical > 0 and n.inside_fov
            ]
            if not contrib_cells:
                continue
            peak = max(contrib_cells, key=lambda n: n.final_contribution)
            delta = None
            delta_class = "NOT_AVAILABLE"
            if snap.exo_without_body is not None:
                delta = exo_delta(snap.exo, snap.exo_without_body)
                delta_class = "DERIVED_COUNTERFACTUAL_PHYSICAL"
            chains.append({
                "id": f"chain-vision-{snap.tick}-{sid}-{snap.observer_body_id}",
                "tick": snap.tick,
                "observer_body_id": snap.observer_body_id,
                "source_body_id": sid,
                "source_identity_layer": "OBSERVER_GT_ONLY",
                "nodes": [
                    f"body_footprint:{sid}",
                    f"body_opt:cell{peak.cell}",
                    "composed_optical_source",
                    "physical_sensor_contribution",
                    "exo_*",
                    "later_cognition_or_action",
                ],
                "edges": [
                    {
                        "from": f"body_footprint:{sid}",
                        "to": f"body_opt:cell{peak.cell}",
                        "link": "DIRECT_CAUSAL_LINK",
                        "evidence_class": "OBSERVED",
                        "reason": "Foreign footprint occupancy maps to body_opt via max optical_response.",
                    },
                    {
                        "from": f"body_opt:cell{peak.cell}",
                        "to": "composed_optical_source",
                        "link": "DIRECT_CAUSAL_LINK",
                        "evidence_class": "DERIVED",
                        "reason": "composed = 1-(1-surf)*(1-body_opt) (validated soft-OR).",
                    },
                    {
                        "from": "composed_optical_source",
                        "to": "physical_sensor_contribution",
                        "link": "DIRECT_CAUSAL_LINK",
                        "evidence_class": "OBSERVED",
                        "reason": "Same illumination × FOV × angular × distance filter as surface.",
                    },
                    {
                        "from": "physical_sensor_contribution",
                        "to": "exo_*",
                        "link": "DIRECT_CAUSAL_LINK",
                        "evidence_class": "OBSERVED",
                        "reason": "Channel bins accumulate final_contribution into exo_0/1/2.",
                    },
                    {
                        "from": "exo_*",
                        "to": "later_cognition_or_action",
                        "link": "NOT_ESTABLISHED",
                        "evidence_class": "NOT_ESTABLISHED",
                        "reason": "No causal_parent_ids from exo to scenario/action in runtime provenance.",
                    },
                ],
                "values": {
                    "body_optical": peak.body_optical,
                    "surface_response": peak.surface_response,
                    "composed_optical": peak.composed_optical,
                    "final_contribution": peak.final_contribution,
                    "exo": dict(snap.exo),
                    "counterfactual_exo_delta": delta,
                    "counterfactual_class": delta_class,
                    "illumination": snap.illumination,
                    "channel_overlap": channel_overlap(snap),
                },
                "disclaimer": (
                    "Physical visual exposure ≠ recognition. "
                    "Sensor change ≠ interpretation. "
                    "Temporal follow-up ≠ causal behavioral effect."
                ),
            })
            if len(chains) >= max_chains:
                return chains
    return chains


def build_visual_followup(
    ticks: list[OpticalTickSnapshot],
    episodes: list[dict[str, Any]],
    *,
    window: int = 10,
) -> list[dict[str, Any]]:
    """Descriptive follow-up after exposure starts — TEMPORALLY_ASSOCIATED only."""
    by_obs: dict[str, list[OpticalTickSnapshot]] = {}
    for s in ticks:
        by_obs.setdefault(s.observer_body_id, []).append(s)
    for oid in by_obs:
        by_obs[oid].sort(key=lambda s: s.tick)

    out: list[dict[str, Any]] = []
    for ep in episodes:
        oid = ep["observer_body_id"]
        series = by_obs.get(oid) or []
        start = int(ep["start_tick"])
        before = [s for s in series if s.tick < start]
        during = [s for s in series if start <= s.tick <= int(ep.get("end_tick", start))]
        after = [s for s in series if start < s.tick <= start + window]
        action_before = before[-1].action if before else None
        first_after_move = next(
            (s for s in after if s.action and str(s.action).startswith("MOVE")),
            None,
        )
        first_scenario = next((s for s in after if s.scenario_selected), None)
        out.append({
            "episode_start": start,
            "observer_body_id": oid,
            "source_body_id": ep.get("source_body_id"),
            "action_before": action_before,
            "actions_during": [s.action for s in during if s.action],
            "first_action_after": after[0].action if after else None,
            "first_MOVE_after": None if first_after_move is None else {
                "tick": first_after_move.tick,
                "action": first_after_move.action,
                "latency_ticks": first_after_move.tick - start,
            },
            "first_scenario_after": None if first_scenario is None else {
                "tick": first_scenario.tick,
                "scenario_selected": first_scenario.scenario_selected,
                "latency_ticks": first_scenario.tick - start,
            },
            "linkage_to_cognition": "NOT_ESTABLISHED",
            "followup_evidence_class": "TEMPORALLY_ASSOCIATED",
            "note": "Chronology only — not a causal behavioral claim.",
        })
    return out


def analyze_optical_series(ticks: list[OpticalTickSnapshot]) -> dict[str, Any]:
    """Full vision forensics package for a series of optical ticks."""
    if not ticks:
        return {
            "coverage": "NOT_AVAILABLE",
            "events": [],
            "episodes": [],
            "causal_chains": [],
            "followup": [],
            "summary": {"note": "No optical ticks supplied to Analyzer."},
        }
    events = build_visual_events(ticks)
    episodes = build_exposure_episodes(ticks)
    chains = build_visual_causal_chains(ticks)
    followup = build_visual_followup(ticks, episodes)
    entries = [e for e in events if e["type"] == "BODY_VISUAL_ENTRY"]
    vision_only = [e for e in episodes if e.get("vision_only")]
    first_entry = entries[0] if entries else None
    sparse = any(t.coverage in ("SPARSE", "GAP") for t in ticks)
    return {
        "coverage": "SPARSE" if sparse else "CONTIGUOUS",
        "n_ticks": len(ticks),
        "events": events,
        "episodes": episodes,
        "causal_chains": chains,
        "followup": followup,
        "summary": {
            "foreign_body_visual_entries": len(entries),
            "exposure_episodes": len(episodes),
            "vision_only_episodes": len(vision_only),
            "first_observed_body_visual_entry": None
            if first_entry is None
            else {
                "tick": first_entry["tick"],
                "wording": "FIRST OBSERVED" if sparse else "FIRST OBSERVED",
                "source_body_id": first_entry.get("source_body_id"),
                "evidence_class": "OBSERVED",
            },
            "cognition_linkage_default": "NOT_ESTABLISHED",
            "disclaimer": (
                "Physical visual exposure ≠ recognition. "
                "Sensor change ≠ interpretation. "
                "Temporal follow-up ≠ causal behavioral effect."
            ),
        },
    }


def format_visual_forensics_section(report: dict[str, Any]) -> str:
    lines = [
        "VISUAL FORENSICS",
        "  Physical visual exposure ≠ recognition.",
        "  Sensor change ≠ interpretation.",
        "  Temporal follow-up ≠ causal behavioral effect.",
        f"  Coverage: {report.get('coverage', 'NOT_AVAILABLE')}",
    ]
    s = report.get("summary") or {}
    lines.append(f"  Foreign-body visual entries: {s.get('foreign_body_visual_entries', 'NOT_AVAILABLE')}")
    lines.append(f"  Exposure episodes: {s.get('exposure_episodes', 'NOT_AVAILABLE')}")
    lines.append(f"  Vision-only episodes: {s.get('vision_only_episodes', 'NOT_AVAILABLE')}")
    fe = s.get("first_observed_body_visual_entry")
    if fe:
        lines.append(
            f"  {fe.get('wording', 'FIRST OBSERVED')} BODY VISUAL ENTRY @ t{fe.get('tick')} "
            f"(source GT={fe.get('source_body_id')})"
        )
    else:
        lines.append("  FIRST OBSERVED BODY VISUAL ENTRY: NONE / NOT_AVAILABLE")
    lines.append(f"  Cognition linkage: {s.get('cognition_linkage_default', 'NOT_ESTABLISHED')}")
    lines.append("  Visual causal chains (representative):")
    chains = report.get("causal_chains") or []
    if not chains:
        lines.append("    NONE / NOT_AVAILABLE")
    for ch in chains[:8]:
        lines.append(f"    {ch.get('id')} @ t{ch.get('tick')}")
        for e in ch.get("edges") or []:
            lines.append(f"      {e['from']} =[{e['link']}]=> {e['to']}")
    return "\n".join(lines)


def optical_snapshots_from_scientific_ticks(
    rows: list[dict[str, Any]],
    *,
    coverage_default: str = "CONTIGUOUS",
) -> list[OpticalTickSnapshot]:
    """Rehydrate OpticalTickSnapshot series from scientific_timeline vision_optical compact."""
    out: list[OpticalTickSnapshot] = []
    for row in rows:
        vo = row.get("vision_optical")
        if not isinstance(vo, dict) or not vo.get("available"):
            continue
        src_map: dict[tuple[int, int], list[str]] = {}
        for sb in vo.get("source_bodies_gt") or []:
            cell = sb.get("cell") or [0, 0]
            key = (int(cell[1]), int(cell[0]))
            src_map.setdefault(key, []).append(str(sb.get("source_body_id")))
        neighbors = [
            OpticalNeighbor(
                cell=list(n.get("cell") or [0, 0]),
                inside_fov=bool(n.get("inside_fov")),
                surface_response=float(n.get("surface_response") or 0.0),
                body_optical=float(n.get("body_optical") or 0.0),
                composed_optical=float(n.get("composed_optical") or 0.0),
                final_contribution=float(n.get("final_contribution") or 0.0),
                relative_angle_deg=float(n.get("relative_angle_deg") or 0.0),
                source_body_ids=list(src_map.get((int((n.get("cell") or [0, 0])[1]), int((n.get("cell") or [0, 0])[0]))) or []),
            )
            for n in (vo.get("neighbors_optical") or [])
        ]
        # Attach GT source ids to neighbors by cell
        for n in neighbors:
            key = (int(n.cell[1]), int(n.cell[0]))
            if key in src_map:
                n.source_body_ids = list(src_map[key])
        selected = None
        if vo.get("source_bodies_gt"):
            selected = str(vo["source_bodies_gt"][0].get("source_body_id"))
        out.append(
            OpticalTickSnapshot(
                tick=int(row.get("tick") or 0),
                observer_body_id=str(row.get("body_id") or "body-0"),
                observer_agent_id=str(row.get("agent_id") or ""),
                theta=float(row.get("theta") or 0.0),
                exo={k: float(v) for k, v in (vo.get("exo") or {}).items()},
                illumination=float(vo.get("illumination") or 0.0),
                vision_enabled=bool(vo.get("perception_enabled", True)),
                body_optics_enabled=bool(vo.get("body_optical_enabled", True)),
                neighbors=neighbors,
                contact=bool(row.get("contact")),
                field_reception=bool(vo.get("field_reception")),
                action=row.get("action"),
                scenario_selected=None,
                regime_id=str(row.get("regime_id") or "default"),
                coverage=str(row.get("coverage") or coverage_default),
                exo_without_body=vo.get("exo_without_foreign_bodies"),
                selected_source_body_id=selected,
            )
        )
    return out


__all__ = [
    "OpticalNeighbor",
    "OpticalTickSnapshot",
    "snapshot_from_sample",
    "analyze_optical_series",
    "build_visual_events",
    "build_exposure_episodes",
    "build_visual_causal_chains",
    "build_visual_followup",
    "channel_overlap",
    "format_visual_forensics_section",
    "optical_snapshots_from_scientific_ticks",
]
