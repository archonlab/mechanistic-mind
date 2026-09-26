"""Bounded LIVE signal-episode accumulator (Observer-only)."""
from __future__ import annotations

from collections import deque
from typing import Any

from mechanistic_mind.ui.psy_observer_web.signal_context.episodes import (
    DEFAULT_FLOOR,
    DEFAULT_GAP_TOLERANCE,
    group_signal_episodes,
)


class LiveSignalEpisodeAccumulator:
    """Incremental reception buffer for LIVE UI — no full-history scans."""

    def __init__(
        self,
        *,
        max_receptions: int = 512,
        max_episodes: int = 64,
        run_id: str = "live",
    ) -> None:
        self.max_receptions = int(max_receptions)
        self.max_episodes = int(max_episodes)
        self.run_id = str(run_id)
        self._receptions: deque[dict[str, Any]] = deque(maxlen=self.max_receptions)
        self._episodes: list[dict[str, Any]] = []
        self.n_observed = 0

    def reset(self, *, run_id: str | None = None) -> None:
        if run_id is not None:
            self.run_id = str(run_id)
        self._receptions.clear()
        self._episodes = []
        self.n_observed = 0

    def observe_events(self, events: list[dict[str, Any]] | None) -> None:
        if not events:
            return
        added = 0
        for ev in events:
            t = str(ev.get("type") or ev.get("kind") or "")
            if t != "PHYSICAL_SIGNAL_RECEIVED":
                continue
            self._receptions.append(ev)
            self.n_observed += 1
            added += 1
        # Only regroup when new receptions arrived — not on every structured-event drain.
        if added == 0:
            return
        eps = group_signal_episodes(
            list(self._receptions),
            run_id=self.run_id,
            floor=DEFAULT_FLOOR,
            gap_tolerance=DEFAULT_GAP_TOLERANCE,
        )
        self._episodes = eps[-self.max_episodes :]

    def compact_summary(self) -> dict[str, Any]:
        recent = []
        for ep in self._episodes[-12:]:
            recent.append(
                {
                    "episode_id": ep.get("episode_id"),
                    "receiver_agent_id": ep.get("receiver_agent_id"),
                    "start_tick": ep.get("start_tick"),
                    "peak_tick": ep.get("peak_tick"),
                    "end_tick": ep.get("end_tick"),
                    "channel": ep.get("channel"),
                    "attribution": ep.get("attribution"),
                    "intensity": {
                        "peak": (ep.get("intensity") or {}).get("peak"),
                        "mean": (ep.get("intensity") or {}).get("mean"),
                    },
                    "cross_agent_contribution_fraction": ep.get(
                        "cross_agent_contribution_fraction"
                    ),
                    "trigger_composition": ep.get("trigger_composition"),
                }
            )
        return {
            "status": "AVAILABLE",
            "n_receptions_buffered": len(self._receptions),
            "n_episodes": len(self._episodes),
            "n_observed_total": self.n_observed,
            "recent_episodes": recent,
            "honesty": {
                "observer_only": True,
                "live_bounded": True,
                "matched_controls": "ANALYZE_RESULTS_ONLY",
                "no_communication_claim": True,
            },
        }
