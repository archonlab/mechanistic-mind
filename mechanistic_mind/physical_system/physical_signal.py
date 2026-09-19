"""Experimental shared-world physical signal fields.

FIELD_A / FIELD_B are non-negative scalar amplitudes on PlanetState.
Default OFF. Not messages. Not EMIT-in-available_actions.

Physics (when enabled):
  each tick: decay, then optional 4-neighbor spread, then additive sources.
  sources: body motion → FIELD_A; contact → FIELD_B; explicit inject (env or body).
  superposition: additive then clip to field_cap.
  range/lifetime: emergent from decay+spread+floor; no teleport.

EMISSION_ENERGETICS = NOT_MODELED
Do not debit mechanical_work_reservoir. MOVE already has its own work path.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.planet.state import PlanetState
from mechanistic_mind.physical_system.body_deformation import rest_geometry
from mechanistic_mind.physical_system.body_orientation import oriented_site_cells


CHANNELS = ("A", "B")


@dataclass
class PhysicalSignalConfig:
    """Fresh default OFF. from_dict missing → OFF."""

    mode: str = "OFF"
    emission_enabled: bool = True
    propagation_enabled: bool = True
    perception_enabled: bool = True
    decay: float = 0.28
    spread: float = 0.22
    floor: float = 1e-4
    field_cap: float = 2.0
    source_cap: float = 1.0
    motion_gain: float = 0.85
    motion_speed_threshold: float = 0.04
    contact_gain: float = 1.0
    energetics: str = "NOT_MODELED"

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PhysicalSignalConfig":
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def ensure_fields(planet: PlanetState) -> tuple[np.ndarray, np.ndarray]:
    h, w = planet.T.shape
    for name in ("FIELD_A", "FIELD_B"):
        arr = getattr(planet, name, None)
        if arr is None or np.asarray(arr).shape != (h, w):
            setattr(planet, name, np.zeros((h, w), dtype=np.float64))
        else:
            setattr(planet, name, np.asarray(arr, dtype=np.float64))
    return planet.FIELD_A, planet.FIELD_B


def clear_fields(planet: PlanetState) -> None:
    planet.FIELD_A = None
    planet.FIELD_B = None


def _site_cells(body: PhysicalBodyState, body_cfg: PhysicalBodyConfig, width: int, height: int):
    rest = rest_geometry(body_cfg.footprint)
    d = getattr(body, "deformation", None)
    r_body = rest + np.asarray(d, dtype=np.float64) if d is not None and np.asarray(d).shape == rest.shape else rest
    theta = float(getattr(body, "theta", 0.0) or 0.0)
    return oriented_site_cells(body, width, height, body_cfg.footprint, theta=theta, r_body=r_body)


def sample_local(planet: PlanetState, cells: list[tuple[int, int]], channel: str) -> float:
    arr = getattr(planet, f"FIELD_{channel}", None)
    if arr is None or not cells:
        return 0.0
    return float(sum(float(arr[iy, ix]) for iy, ix in cells) / max(1, len(cells)))


def _propagate(field: np.ndarray, cfg: PhysicalSignalConfig) -> None:
    decay = min(max(0.0, float(cfg.decay)), 1.0)
    field *= (1.0 - decay)
    if cfg.propagation_enabled:
        sp = min(max(0.0, float(cfg.spread)), 1.0)
        neigh = (
            np.roll(field, 1, 0) + np.roll(field, -1, 0)
            + np.roll(field, 1, 1) + np.roll(field, -1, 1)
        )
        field *= (1.0 - sp)
        field += (sp / 4.0) * neigh
    np.clip(field, 0.0, float(cfg.field_cap), out=field)
    field[field < float(cfg.floor)] = 0.0


def _deposit(field: np.ndarray, cells: list[tuple[int, int]], amp: float, cfg: PhysicalSignalConfig) -> float:
    amp = float(min(max(0.0, amp), float(cfg.source_cap)))
    if amp <= 0.0 or not cells:
        return 0.0
    each = amp / max(1, len(cells))
    for iy, ix in cells:
        field[iy, ix] = float(min(float(cfg.field_cap), float(field[iy, ix]) + each))
    return amp


def _emission_id(tick: int, channel: str, seq: int, *, slot: int | None = None, trigger: str = "") -> str:
    """Stable observational id for a deposit this tick. Not a persistent particle."""
    who = f"s{slot}" if slot is not None else "env"
    trig = str(trigger or "src").replace(" ", "_")
    return f"e{int(tick)}-{channel}-{who}-{trig}-{int(seq)}"


def _contact_pair_meta(contact: dict[str, Any] | None, n_bodies: int) -> dict[str, Any]:
    """Observational contact-pair fields from soft-contact receipt. No inference beyond known pair."""
    if not contact or not contact.get("contact"):
        return {}
    # TwoAgent soft contact is always body-0 × body-1 when n_bodies >= 2.
    meta: dict[str, Any] = {
        "origin_kind": "BODY_BODY_CONTACT" if n_bodies >= 2 else "BODY_CONTACT",
        "contact_entity_a_kind": contact.get("contact_entity_a_kind") or "BODY",
        "contact_entity_a_id": contact.get("contact_entity_a_id") or ("body-0" if n_bodies >= 1 else "NOT_RECORDED"),
        "contact_entity_b_kind": contact.get("contact_entity_b_kind") or ("BODY" if n_bodies >= 2 else "NOT_RECORDED"),
        "contact_entity_b_id": contact.get("contact_entity_b_id") or ("body-1" if n_bodies >= 2 else "NOT_RECORDED"),
        "com_distance": contact.get("com_distance"),
        "overlap_cells": list(contact.get("overlap_cells") or []),
        "overlap_n": len(contact.get("overlap_cells") or []),
    }
    a_id = meta["contact_entity_a_id"]
    b_id = meta["contact_entity_b_id"]
    meta["origin_id"] = f"{a_id}×{b_id}"
    return meta


def step_physical_signals(
    planet: PlanetState,
    bodies: list[PhysicalBodyState],
    body_cfgs: list[PhysicalBodyConfig],
    cfg: PhysicalSignalConfig,
    *,
    contact: dict[str, Any] | None = None,
    extra_sources: list[dict[str, Any]] | None = None,
    receipt_tick: int = 0,
) -> dict[str, Any]:
    """Decay/spread existing field, then add this-tick sources. One shared world."""
    receipt: dict[str, Any] = {
        "enabled": bool(cfg.enabled),
        "tick": int(receipt_tick),
        "energetics": cfg.energetics,
        "emission_enabled": bool(cfg.emission_enabled),
        "propagation_enabled": bool(cfg.propagation_enabled),
        "perception_enabled": bool(cfg.perception_enabled),
        "sources": [],
        "sum_A": 0.0,
        "sum_B": 0.0,
        "max_A": 0.0,
        "max_B": 0.0,
        "emitted": False,
    }
    if not cfg.enabled:
        return receipt
    FA, FB = ensure_fields(planet)
    _propagate(FA, cfg)
    _propagate(FB, cfg)
    h, w = FA.shape
    contact_meta = _contact_pair_meta(contact, len(bodies))
    if cfg.emission_enabled:
        for i, body in enumerate(bodies):
            cells = _site_cells(body, body_cfgs[i], w, h)
            speed = float(np.hypot(body.vx, body.vy))
            vmax = max(1e-9, float(getattr(body_cfgs[i], "v_max", 0.3) or 0.3))
            agent_id = f"agent_{i}"
            body_id = f"body-{i}"
            if speed >= float(cfg.motion_speed_threshold):
                amp = float(cfg.motion_gain) * float(np.tanh(speed / vmax))
                realized = _deposit(FA, cells, amp, cfg)
                if realized > 0:
                    seq = len(receipt["sources"])
                    receipt["sources"].append({
                        "emission_id": _emission_id(receipt_tick, "A", seq, slot=i, trigger="body_motion"),
                        "channel": "A",
                        "trigger": "body_motion",
                        "slot": i,
                        # Physical emitter = body depositing into FIELD_A at its site cells.
                        "emitter_agent_id": agent_id,
                        "emitter_body_id": body_id,
                        "origin_kind": "BODY_MOTION",
                        "origin_id": body_id,
                        # Observer stream that recorded this deposit (instrumentation ≠ emitter claim).
                        "observer_source_id": agent_id,
                        "realized": realized,
                        "amplitude": realized,
                        "cells": [(int(iy), int(ix)) for iy, ix in cells],
                        "x": float(body.x),
                        "y": float(body.y),
                        "physical_quantity": "speed",
                        "physical_quantity_value": speed,
                    })
                    receipt["emitted"] = True
            if contact and contact.get("contact"):
                # Soft body↔body contact: each overlapping body deposits FIELD_B at its own cells.
                realized = _deposit(FB, cells, float(cfg.contact_gain), cfg)
                if realized > 0:
                    seq = len(receipt["sources"])
                    src = {
                        "emission_id": _emission_id(receipt_tick, "B", seq, slot=i, trigger="body_contact"),
                        "channel": "B",
                        "trigger": "body_contact",
                        "slot": i,
                        "emitter_agent_id": agent_id,
                        "emitter_body_id": body_id,
                        "observer_source_id": agent_id,
                        "realized": realized,
                        "amplitude": realized,
                        "cells": [(int(iy), int(ix)) for iy, ix in cells],
                        "x": float(body.x),
                        "y": float(body.y),
                        "physical_quantity": "contact_gain",
                        "physical_quantity_value": float(cfg.contact_gain),
                    }
                    src.update(contact_meta)
                    # Depositing body remains the emitter; contact pair is the physical cause.
                    receipt["sources"].append(src)
                    receipt["emitted"] = True
    for src in extra_sources or []:
        ch = str(src.get("channel") or "A").upper()
        field = FA if ch == "A" else FB
        amp = float(src.get("amplitude") or 0.0)
        if src.get("cells"):
            cells = [(int(c[0]), int(c[1])) for c in src["cells"]]
        else:
            iy = int(src["iy"]) % h
            ix = int(src["ix"]) % w
            cells = [(iy, ix)]
        realized = _deposit(field, cells, amp, cfg)
        if realized > 0:
            seq = len(receipt["sources"])
            slot = src.get("slot")
            slot_i = int(slot) if slot is not None else None
            if slot_i is not None:
                emitter_agent = f"agent_{slot_i}"
                emitter_body = f"body-{slot_i}"
                origin_kind = "BODY_INJECT"
                origin_id = emitter_body
            else:
                emitter_agent = "NOT_RECORDED"
                emitter_body = "NOT_RECORDED"
                origin_kind = "ENVIRONMENTAL"
                origin_id = f"cell:{cells[0][0]},{cells[0][1]}"
            receipt["sources"].append({
                "emission_id": _emission_id(
                    receipt_tick, ch, seq, slot=slot_i, trigger=str(src.get("trigger") or "environmental"),
                ),
                "channel": ch,
                "trigger": str(src.get("trigger") or "environmental"),
                "slot": slot_i,
                "emitter_agent_id": emitter_agent,
                "emitter_body_id": emitter_body,
                "origin_kind": origin_kind,
                "origin_id": origin_id,
                "observer_source_id": src.get("observer_source_id") or (
                    emitter_agent if slot_i is not None else "environment"
                ),
                "realized": realized,
                "amplitude": realized,
                "cells": [(int(iy), int(ix)) for iy, ix in cells],
                "iy": cells[0][0],
                "ix": cells[0][1],
                "x": float(cells[0][1]) + 0.5,
                "y": float(cells[0][0]) + 0.5,
            })
            receipt["emitted"] = True
    receipt["sum_A"] = float(FA.sum())
    receipt["sum_B"] = float(FB.sum())
    receipt["max_A"] = float(FA.max())
    receipt["max_B"] = float(FB.max())
    receipt["decay"] = float(cfg.decay)
    receipt["spread"] = float(cfg.spread)
    receipt["floor"] = float(cfg.floor)
    return receipt
