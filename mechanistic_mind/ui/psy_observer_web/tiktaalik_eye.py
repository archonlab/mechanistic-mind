"""Tiktaalik Eye — Observer diagnostic over agent-accessible optical state.

Does not sample WorldMap pixels. Does not write into cognition.
Uses last_agent_observation plus sensor-config metadata only.
"""
from __future__ import annotations

import math
from typing import Any

from mechanistic_mind.research.background_context import QUANT_BINS, _quantize
from mechanistic_mind.physical_system.near_field_exteroception import (
    N_EXO_CHANNELS,
    clamp_optical_mapping,
    clamp_spatial_sectors,
    clamp_spatial_vision,
    clamp_surface_discrimination,
    clamp_vision_radius,
    spatial_observation_keys,
    surface_observation_keys,
)

SCHEMA = "mm.observer.tiktaalik_eye.v1"
SECTORS = ("LEFT", "FORWARD", "RIGHT")
EXO_KEYS = tuple(f"exo_{i}" for i in range(N_EXO_CHANNELS))
SAT_EPS = 1e-9
EYE_RATES = ("OFF", "SNAPSHOT", "2FPS", "5FPS", "PER_TICK")
RATE_PERIOD_S = {"2FPS": 0.5, "5FPS": 0.2}


def clamp_eye_rate(rate: Any) -> str:
    s = str(rate or "OFF").strip().upper().replace(" ", "")
    aliases = {"2": "2FPS", "5": "5FPS", "PERTICK": "PER_TICK", "ON": "5FPS"}
    s = aliases.get(s, s)
    return s if s in EYE_RATES else "OFF"


def pe_bin(value: float, bins: int = QUANT_BINS) -> dict[str, Any]:
    """Same 5-bin quantize as cognition sensory_signature (not a new hash)."""
    q = int(_quantize(float(value), bins))
    return {"index": q, "bins": int(bins), "label": f"{q}/{bins}"}


def _cell(raw: float | None, *, present: bool, prev: float | None, sat: float) -> dict[str, Any]:
    if not present:
        return {
            "present": False,
            "raw": None,
            "saturated": False,
            "pe_bin": None,
            "delta": None,
        }
    v = float(raw or 0.0)
    d = None if prev is None else float(v - float(prev))
    return {
        "present": True,
        "raw": v,
        "saturated": bool(v >= float(sat) - SAT_EPS),
        "pe_bin": pe_bin(v),
        "delta": d,
    }


def _row_from_keys(
    obs: dict[str, Any],
    keys: tuple[str, str, str],
    *,
    prev: dict[str, float] | None,
    sat: float,
    required: bool,
) -> dict[str, Any]:
    if required:
        present = all(k in obs for k in keys)
    else:
        present = any(k in obs for k in keys)
        if not present:
            return {
                "present": False,
                "left": _cell(None, present=False, prev=None, sat=sat),
                "forward": _cell(None, present=False, prev=None, sat=sat),
                "right": _cell(None, present=False, prev=None, sat=sat),
            }
    p = prev or {}
    return {
        "present": True,
        "left": _cell(obs.get(keys[0]), present=keys[0] in obs, prev=p.get(keys[0]), sat=sat),
        "forward": _cell(obs.get(keys[1]), present=keys[1] in obs, prev=p.get(keys[1]), sat=sat),
        "right": _cell(obs.get(keys[2]), present=keys[2] in obs, prev=p.get(keys[2]), sat=sat),
    }


def visual_subset(obs: dict[str, Any] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in (obs or {}).items():
        if k.startswith("exo_") or k.startswith("surface_c"):
            try:
                out[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
    return out


def sensor_configuration(nfe: Any, body: Any = None, *, articulated_head: bool | None = None) -> dict[str, Any]:
    """Observer metadata about the sensor. Not agent-accessible values."""
    radius = clamp_vision_radius(getattr(nfe, "radius", 1) if nfe is not None else 1)
    head_on = bool(articulated_head)
    if articulated_head is None and body is not None:
        head_on = bool(getattr(body, "_articulated_head_enabled", False))
    heading = "HEAD" if head_on else "BODY"
    disc = clamp_surface_discrimination(
        getattr(nfe, "visual_surface_discrimination", "OFF") if nfe else "OFF"
    )
    mapping = clamp_optical_mapping(getattr(nfe, "optical_mapping", "INDEPENDENT") if nfe else "INDEPENDENT")
    fov = float(getattr(nfe, "fov_deg", 120.0) or 120.0) if nfe is not None else 120.0
    sat = float(getattr(nfe, "saturation", 1.0) or 1.0) if nfe is not None else 1.0
    illum_on = bool(getattr(nfe, "illumination_enabled", True)) if nfe is not None else False
    return {
        "layer": "SENSOR_CONFIGURATION",
        "not_agent_accessible": True,
        "radius": int(radius),
        "fov_deg": fov,
        "heading_source": heading,
        "surface_discrimination": disc,
        "optical_mapping": mapping,
        "spatial_vision": clamp_spatial_vision(getattr(nfe, "spatial_vision", "LEGACY") if nfe else "LEGACY"),
        "spatial_sectors": clamp_spatial_sectors(getattr(nfe, "spatial_sectors", 5) if nfe else 5),
        "saturation": sat,
        "illumination_enabled": illum_on,
        "radius_note": (
            "R=1: Chebyshev-1 Moore candidates only; farther cells are outside the sensor set."
            if radius == 1
            else f"R={radius}: Moore candidates within Chebyshev radius {radius} (own cell excluded)."
        ),
    }


def compact_contributors(neighbors: list[dict[str, Any]] | None, *, limit: int = 8) -> dict[str, Any]:
    """WORLD / SENSOR PIPELINE DEBUG. Empty unless neighbor rows already exist."""
    if not neighbors:
        return {
            "status": "NOT_AVAILABLE",
            "reason": "neighbor rows not in this Observer frame (compact RUNNING drops them)",
            "note": "WORLD / SENSOR PIPELINE DEBUG — not agent-accessible",
        }
    bins: list[list[dict[str, Any]]] = [[], [], []]
    for row in neighbors:
        if not isinstance(row, dict):
            continue
        final = float(row.get("final_contribution") or 0.0)
        if final <= 0.0:
            continue
        rel = float(row.get("relative_angle_rad") or 0.0)
        # Same mapping as sample_near_field: rel in FOV → bin 0..2. If missing FOV, skip.
        if not row.get("inside_fov"):
            continue
        half = math.radians(60.0)
        u = (rel + half) / max(1e-9, 2.0 * half)
        bi = int(max(0, min(2, math.floor(u * 3))))
        bins[bi].append({
            "cell": row.get("cell"),
            "sector": SECTORS[bi],
            "final_contribution": final,
            "surface_response": row.get("surface_response"),
            "body_optical": row.get("body_optical"),
            "inside_fov": True,
        })
    for lst in bins:
        lst.sort(key=lambda x: -float(x["final_contribution"]))
        del lst[limit:]
    return {
        "status": "AVAILABLE",
        "note": "WORLD / SENSOR PIPELINE DEBUG — decomposed contributors are not cognition",
        "left": bins[0],
        "forward": bins[1],
        "right": bins[2],
    }


def compact_sector_overlay(neighbors: list[dict[str, Any]] | None, *, limit: int = 48) -> dict[str, Any]:
    """WORLD / SENSOR GEOMETRY DEBUG cell list. Not cognition."""
    if not neighbors:
        return {"status": "NOT_AVAILABLE", "cells": []}
    cells = []
    half = math.radians(60.0)
    for row in neighbors:
        if not isinstance(row, dict) or not row.get("cell"):
            continue
        rel = float(row.get("relative_angle_rad") or 0.0)
        inside = bool(row.get("inside_fov"))
        final = float(row.get("final_contribution") or 0.0)
        sector = None
        if inside:
            u = (rel + half) / max(1e-9, 2.0 * half)
            bi = int(max(0, min(2, math.floor(u * 3))))
            sector = SECTORS[bi]
        cells.append({
            "cell": row.get("cell"),
            "inside_fov": inside,
            "sector": sector,
            "final_contribution": final,
            "detectable": bool(row.get("detectable")),
        })
        if len(cells) >= limit:
            break
    return {
        "status": "AVAILABLE",
        "layer": "WORLD_SENSOR_GEOMETRY_DEBUG",
        "not_agent_accessible": True,
        "cells": cells,
    }


def build_agent_eye(
    *,
    agent_id: str,
    observation: dict[str, Any] | None,
    prev_visual: dict[str, float] | None,
    nfe: Any,
    body: Any = None,
    articulated_head: bool | None = None,
    neighbors: list[dict[str, Any]] | None = None,
    include_geometry_debug: bool = False,
    tick: int | None = None,
) -> dict[str, Any]:
    obs = observation if isinstance(observation, dict) else {}
    disc = clamp_surface_discrimination(
        getattr(nfe, "visual_surface_discrimination", "OFF") if nfe is not None else "OFF"
    )
    sat = float(getattr(nfe, "saturation", 1.0) or 1.0) if nfe is not None else 1.0
    prev = prev_visual or {}
    exo_required = any(k in obs for k in EXO_KEYS) or bool(getattr(nfe, "vision_contributes", False))
    rows: dict[str, Any] = {
        "exo": _row_from_keys(obs, ("exo_0", "exo_1", "exo_2"), prev=prev, sat=sat, required=exo_required),
    }
    # Absent vs zero: OFF must omit surface rows (present=false), not invent zeros.
    if disc == "OFF":
        rows["surface_c0"] = _row_from_keys(obs, ("surface_c0_0", "surface_c0_1", "surface_c0_2"), prev=prev, sat=sat, required=False)
        rows["surface_c0"]["present"] = False
        rows["surface_c1"] = {"present": False}
        rows["surface_c2"] = {"present": False}
    elif disc == "LOW":
        rows["surface_c0"] = _row_from_keys(obs, ("surface_c0_0", "surface_c0_1", "surface_c0_2"), prev=prev, sat=sat, required=True)
        rows["surface_c1"] = {"present": False}
        rows["surface_c2"] = {"present": False}
    else:
        rows["surface_c0"] = _row_from_keys(obs, ("surface_c0_0", "surface_c0_1", "surface_c0_2"), prev=prev, sat=sat, required=True)
        rows["surface_c1"] = _row_from_keys(obs, ("surface_c1_0", "surface_c1_1", "surface_c1_2"), prev=prev, sat=sat, required=True)
        rows["surface_c2"] = _row_from_keys(obs, ("surface_c2_0", "surface_c2_1", "surface_c2_2"), prev=prev, sat=sat, required=True)

    spat_mode = clamp_spatial_vision(getattr(nfe, "spatial_vision", "LEGACY") if nfe else "LEGACY")
    n_sec = clamp_spatial_sectors(getattr(nfe, "spatial_sectors", 5) if nfe else 5)
    spatial_bins = []
    if spat_mode != "LEGACY":
        for i in range(n_sec):
            key = f"spatial_exo_a{i}"
            spatial_bins.append({
                "label": f"A{i}",
                "key": key,
                **_cell(obs.get(key) if key in obs else None, present=key in obs, prev=prev.get(key), sat=sat),
            })
    rows["spatial_exo"] = {
        "present": spat_mode != "LEGACY",
        "mode": spat_mode,
        "bins": spatial_bins,
    }
    if spat_mode != "LEGACY" and disc != "OFF":
        for ch in range(3 if disc == "RICH" else 1):
            sb = []
            for i in range(n_sec):
                key = f"spatial_surface_c{ch}_a{i}"
                sb.append({
                    "label": f"A{i}",
                    "key": key,
                    **_cell(obs.get(key) if key in obs else None, present=key in obs, prev=prev.get(key), sat=sat),
                })
            rows[f"spatial_surface_c{ch}"] = {"present": True, "bins": sb}
        if disc != "RICH":
            rows["spatial_surface_c1"] = {"present": False}
            rows["spatial_surface_c2"] = {"present": False}
    else:
        rows["spatial_surface_c0"] = {"present": False}
        rows["spatial_surface_c1"] = {"present": False}
        rows["spatial_surface_c2"] = {"present": False}

    leaked = [
        k for k in obs
        if any(s in k.lower() for s in ("distance", "terrain", "potential", "slope", "height", "agent_id", "depth"))
    ]
    geo = None
    contrib = None
    if include_geometry_debug:
        geo = compact_sector_overlay(neighbors)
        contrib = compact_contributors(neighbors)
    else:
        contrib = {"status": "SKIPPED", "reason": "geometry debug off"}
        geo = {"status": "SKIPPED", "reason": "geometry debug off"}

    return {
        "agent_id": agent_id,
        "tick": tick,
        "accessible": rows,
        "sensor_configuration": sensor_configuration(nfe, body, articulated_head=articulated_head),
        "honesty": (
            "Agent-accessible optical accumulators. Sectors encode bearing; "
            "magnitude entangles visibility, distance attenuation and summed contributions. "
            "Not a camera image. Not depth. Not terrain geometry."
        ),
        "forbidden_leaks": leaked,
        "world_sector_overlay": geo,
        "contributors": contrib,
        "surface_keys_contract": list(surface_observation_keys(disc)),
        "spatial_keys_contract": list(spatial_observation_keys(
            spatial_mode=spat_mode, discrimination=disc, n_sectors=n_sec
        )),
    }


def _foreign_for_slot(runtime: Any, index: int) -> list:
    slots = getattr(runtime, "slots", None)
    if not slots:
        return []
    if hasattr(runtime, "foreign_bodies_for"):
        return list(runtime.foreign_bodies_for(index))
    return [(slots[j].body, slots[j].config.body) for j in range(len(slots)) if j != index]


def collect_canonical_fpv(
    runtime: Any,
    *,
    prev_fpv_finals: dict[str, dict[str, float]] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
    """FPV receipts from sample_near_field(diagnostic=True). Cache-friendly."""
    from mechanistic_mind.physical_system.near_field_exteroception import (
        compact_fpv_receipts,
        sample_near_field,
    )

    prev_all = prev_fpv_finals or {}
    nxt: dict[str, dict[str, float]] = {}
    agents: dict[str, Any] = {}
    slots = getattr(runtime, "slots", None)
    if slots:
        from mechanistic_mind.ui.psy_observer_web.undercover_identity import slot_agent_body_ids

        exp_slot = getattr(runtime, "experimenter_slot", None)
        for i, slot in enumerate(slots):
            aid, _ = slot_agent_body_ids(i, experimenter_slot=exp_slot)
            nfe = getattr(slot.config, "near_field_exteroception", None)
            if nfe is None or not getattr(nfe, "enabled", False):
                agents[aid] = {"status": "VISION_OFF", "samples": []}
                continue
            sample = sample_near_field(
                world=slot.world,
                body=slot.body,
                cfg=nfe,
                foreign_bodies=_foreign_for_slot(runtime, i),
                diagnostic=True,
            )
            receipts = compact_fpv_receipts(sample, prev_finals=prev_all.get(aid))
            agents[aid] = receipts
            store: dict[str, float] = {}
            for rec in receipts.get("samples") or []:
                wc = rec.get("world_cell")
                if isinstance(wc, (list, tuple)) and len(wc) >= 2:
                    store[f"{wc[0]},{wc[1]}"] = float(rec.get("final") or 0.0)
            nxt[aid] = store
    else:
        nfe = getattr(getattr(runtime, "config", None), "near_field_exteroception", None)
        sample = sample_near_field(
            world=runtime.world, body=runtime.body, cfg=nfe, diagnostic=True,
        )
        receipts = compact_fpv_receipts(sample, prev_finals=prev_all.get("agent_0"))
        agents["agent_0"] = receipts
        nxt["agent_0"] = {
            f"{r['world_cell'][0]},{r['world_cell'][1]}": float(r.get("final") or 0.0)
            for r in (receipts.get("samples") or [])
            if isinstance(r.get("world_cell"), (list, tuple)) and len(r.get("world_cell") or []) >= 2
        }
    return agents, nxt


def build_tiktaalik_eye_payload(
    runtime: Any,
    *,
    prev_visual_by_agent: dict[str, dict[str, float]] | None = None,
    include_geometry_debug: bool = False,
    neighbors_by_agent: dict[str, list] | None = None,
    include_fpv: bool = False,
    prev_fpv_finals: dict[str, dict[str, float]] | None = None,
    rate: str = "5FPS",
) -> dict[str, Any]:
    """Compact Eye payload from last_agent_observation. No extra FOV sample."""
    prev_map = prev_visual_by_agent or {}
    nb_map = neighbors_by_agent or {}
    slots = getattr(runtime, "slots", None)
    agents: dict[str, Any] = {}
    if slots:
        from mechanistic_mind.ui.psy_observer_web.undercover_identity import slot_agent_body_ids

        exp_slot = getattr(runtime, "experimenter_slot", None)
        for i, slot in enumerate(slots):
            aid, _bid = slot_agent_body_ids(i, experimenter_slot=exp_slot)
            nfe = getattr(slot.config, "near_field_exteroception", None)
            head_on = bool(getattr(getattr(slot.config, "articulated_head", None), "enabled", False))
            neighbors = nb_map.get(aid) if include_geometry_debug else None
            obs = getattr(slot, "last_agent_observation", None)
            agents[aid] = build_agent_eye(
                agent_id=aid,
                observation=obs,
                prev_visual=prev_map.get(aid),
                nfe=nfe,
                body=slot.body,
                articulated_head=head_on,
                neighbors=neighbors,
                include_geometry_debug=include_geometry_debug,
                tick=int(getattr(slot, "tick", 0) or 0),
            )
    else:
        nfe = getattr(getattr(runtime, "config", None), "near_field_exteroception", None)
        head_on = bool(getattr(getattr(runtime.config, "articulated_head", None), "enabled", False))
        agents["agent_0"] = build_agent_eye(
            agent_id="agent_0",
            observation=getattr(runtime, "last_agent_observation", None),
            prev_visual=prev_map.get("agent_0"),
            nfe=nfe,
            body=getattr(runtime, "body", None),
            articulated_head=head_on,
            include_geometry_debug=False,
            tick=int(getattr(runtime, "tick", 0) or 0),
        )
    nbytes = 0
    fpv_agents: dict[str, Any] | None = None
    fpv_next: dict[str, dict[str, float]] = {}
    if include_fpv:
        fpv_agents, fpv_next = collect_canonical_fpv(runtime, prev_fpv_finals=prev_fpv_finals)
        for aid, panel in agents.items():
            if isinstance(panel, dict) and fpv_agents.get(aid):
                panel["fpv"] = fpv_agents[aid]
    try:
        import json

        nbytes = len(json.dumps({"agents": agents, "fpv": bool(include_fpv)}, default=str).encode("utf-8"))
    except Exception:
        nbytes = 0
    return {
        "schema": SCHEMA,
        "status": "ACTIVE",
        "rate": clamp_eye_rate(rate),
        "observer_only": True,
        "feeds_cognition": False,
        "worldmap_rgb_used": False,
        "fpv_included": bool(include_fpv),
        "agents": agents,
        "payload_bytes": nbytes,
        "fpv_next_finals": fpv_next,
        "note": "TIKTAALIK EYE — SENSOR SPACE. Diagnostic render of accessible optical state.",
    }


def psc_off_ticks_status(runtime: Any) -> dict[str, Any]:
    cog = getattr(getattr(runtime, "config", None), "cognition", None)
    n = getattr(cog, "psc_off_ticks", None) if cog is not None else None
    psc_on = False
    try:
        snap = runtime.mechanisms()
        for m in snap.get("mechanisms") or []:
            if m.get("id") == "prospective_scenario_competition":
                psc_on = bool(m.get("enabled"))
                break
    except Exception:
        psc_on = False
    act = getattr(runtime, "_psc_activation", None)
    if isinstance(act, dict):
        return {
            "psc": "ON" if psc_on else "OFF",
            "schedule": "MANUAL" if n is None else int(n),
            "auto_on_tick": None if n is None else int(n),
            "activated_tick": act.get("tick"),
            "history_preserved": bool(act.get("history_preserved", True)),
            "mode": "ACTIVATED" if psc_on else "SCHEDULED",
        }
    if n is None:
        return {
            "psc": "ON" if psc_on else "OFF",
            "schedule": "MANUAL",
            "auto_on_tick": None,
            "activated_tick": None,
            "history_preserved": True,
            "mode": "MANUAL",
        }
    return {
        "psc": "ON" if psc_on else "OFF",
        "schedule": int(n),
        "auto_on_tick": int(n),
        "activated_tick": None,
        "history_preserved": True,
        "mode": "SCHEDULED" if not psc_on else "ON",
    }
