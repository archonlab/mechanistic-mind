"""Bounded factual metric accumulator — O(1) RAM vs run length."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompactMetrics:
    tick_count: int = 0
    action_counts: dict[str, int] = field(default_factory=dict)
    distance_travelled: float = 0.0
    visited_cells: set[tuple[int, int]] = field(default_factory=set)
    contact_ticks: int = 0
    osc_emit_ticks: int = 0
    osc_recv_ticks: int = 0
    full_duplex_ticks: int = 0
    vision_nonzero_ticks: int = 0
    composite_motor_commands: int = 0
    prediction_ticks: int = 0
    _prev_xy: tuple[float, float] | None = None

    def observe_tick(self, *, tick: int, runtime: Any, events: list[dict] | None = None) -> None:
        self.tick_count = max(self.tick_count, int(tick) + 1)
        body = getattr(runtime, "body", None)
        if body is not None:
            x, y = float(getattr(body, "x", 0.0)), float(getattr(body, "y", 0.0))
            planet = getattr(getattr(runtime, "config", None), "planet", None)
            width = float(getattr(planet, "width", 32) or 32) if planet else 32.0
            height = float(getattr(planet, "height", 32) or 32) if planet else 32.0
            if self._prev_xy is not None:
                dx = x - self._prev_xy[0]
                dy = y - self._prev_xy[1]
                if abs(dx) > width / 2:
                    dx -= width if dx > 0 else -width
                if abs(dy) > height / 2:
                    dy -= height if dy > 0 else -height
                self.distance_travelled += (dx * dx + dy * dy) ** 0.5
            self._prev_xy = (x, y)
            self.visited_cells.add((int(x) % int(width), int(y) % int(height)))

        # Action from last selection if present
        act = getattr(runtime, "last_selected_action", None) or getattr(runtime, "last_action", None)
        if act is None and hasattr(runtime, "slots") and runtime.slots:
            act = getattr(runtime.slots[0], "last_selected_action", None)
        if act is not None:
            key = str(act)
            self.action_counts[key] = self.action_counts.get(key, 0) + 1
            if key.startswith("MOVE:") or key.startswith("NECK_") or key.startswith("OSC_") or key == "PUSH":
                self.composite_motor_commands += 1

        for ev in events or []:
            et = str(ev.get("type") or ev.get("event_type") or "")
            if "CONTACT" in et:
                self.contact_ticks += 1
            if "OSC" in et and "EMIT" in et:
                self.osc_emit_ticks += 1
            if "OSC" in et and ("RECV" in et or "RECEPT" in et):
                self.osc_recv_ticks += 1

        # Vision nonzero from last observation
        obs = getattr(runtime, "last_agent_observation", None) or {}
        if any(float(obs.get(k, 0) or 0) > 0 for k in ("exo_0", "exo_1", "exo_2")):
            self.vision_nonzero_ticks += 1

        # Full-duplex heuristic: emit+recv same tick via events
        types = {str(ev.get("type") or "") for ev in (events or [])}
        if any("OSC" in t and "EMIT" in t for t in types) and any(
            "OSC" in t and ("RECV" in t or "RECEPT" in t or "BAND" in t) for t in types
        ):
            self.full_duplex_ticks += 1

        mind = getattr(runtime, "last_mind", None) or {}
        if mind.get("prediction") or mind.get("n_predictions"):
            self.prediction_ticks += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "tick_count": self.tick_count,
            "action_counts": dict(sorted(self.action_counts.items())),
            "distance_travelled": round(self.distance_travelled, 6),
            "visited_cells": len(self.visited_cells),
            "contact_ticks": self.contact_ticks,
            "osc_emit_ticks": self.osc_emit_ticks,
            "osc_recv_ticks": self.osc_recv_ticks,
            "full_duplex_ticks": self.full_duplex_ticks,
            "vision_nonzero_ticks": self.vision_nonzero_ticks,
            "composite_motor_commands": self.composite_motor_commands,
            "prediction_ticks": self.prediction_ticks,
        }

    def ram_bytes_estimate(self) -> int:
        # Bounded: counters + visited cells (cells ≤ world area, typically 32²)
        return 256 + 16 * len(self.visited_cells) + 32 * len(self.action_counts)
