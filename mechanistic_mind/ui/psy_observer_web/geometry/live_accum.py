"""Bounded LIVE empirical traversability accumulator (Observer-only).

Incremental: one observe() per scientific tick per agent.
No full-history scans. No cognition coupling.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from mechanistic_mind.ui.psy_observer_web.geometry.metrics import (
    action_alignment,
    action_direction_unit,
    bin_cell,
    evidence_class,
    realized_displacement,
    traversal_outcome_class,
)

# Classification codes for compact grids (UI legend).
CLASS_UNKNOWN = 0
CLASS_LOW_EVIDENCE = 1
CLASS_EASY = 2
CLASS_MIXED = 3
CLASS_DIFFICULT = 4
CLASS_STRONG_DEFLECTION = 5

CLASS_LABELS = {
    CLASS_UNKNOWN: "UNKNOWN",
    CLASS_LOW_EVIDENCE: "LOW_EVIDENCE",
    CLASS_EASY: "EASY",
    CLASS_MIXED: "MIXED",
    CLASS_DIFFICULT: "DIFFICULT",
    CLASS_STRONG_DEFLECTION: "STRONG_DEFLECTION",
}

MOVE_ACTIONS = ("MOVE:N", "MOVE:E", "MOVE:S", "MOVE:W")

# Empirical overlay visual refresh floor (Hz). Scientific accumulate remains every MOVE tick.
EMPIRICAL_PUBLISH_HZ = 4.0


def flatten_grid(grid: list[list[Any]]) -> dict[str, Any]:
    """Compact transport for 2D grids (nested lists → flat data)."""
    h = len(grid)
    w = len(grid[0]) if h else 0
    data: list[Any] = []
    for y in range(h):
        row = grid[y]
        data.extend(row[x] for x in range(w))
    return {"h": h, "w": w, "data": data}


def unflatten_grid(payload: dict[str, Any] | list | None) -> list[list[Any]] | None:
    """Accept flat or nested grids (frontend/backend compatibility)."""
    if payload is None:
        return None
    if isinstance(payload, list):
        return payload  # already nested
    if not isinstance(payload, dict):
        return None
    h = int(payload.get("h") or 0)
    w = int(payload.get("w") or 0)
    data = payload.get("data") or []
    if h <= 0 or w <= 0:
        return []
    out: list[list[Any]] = []
    for y in range(h):
        base = y * w
        out.append(list(data[base : base + w]))
    return out


def classify_bucket(
    attempts: int,
    opposing: int,
    aligned: int,
    mean_align: float | None,
    *,
    sparse: int = 3,
    adequate: int = 8,
) -> int:
    """Derive Observer class from numeric evidence. Not a terrain label."""
    if attempts <= 0:
        return CLASS_UNKNOWN
    if attempts < sparse:
        return CLASS_LOW_EVIDENCE
    opp_rate = opposing / attempts
    ali_rate = aligned / attempts
    ma = mean_align if mean_align is not None else 0.0
    if attempts >= adequate and (opp_rate >= 0.40 or ma <= -0.30):
        return CLASS_STRONG_DEFLECTION
    if attempts >= sparse and opp_rate >= 0.25:
        return CLASS_DIFFICULT
    if attempts >= sparse and ali_rate >= 0.60 and opp_rate < 0.15 and ma >= 0.45:
        return CLASS_EASY
    return CLASS_MIXED


class LiveTraversabilityAccumulator:
    """Per-agent and global cell×action empirical stats for LIVE overlays."""

    def __init__(self, *, width: int = 32, height: int = 32, event_capacity: int = 48) -> None:
        self.width = int(width)
        self.height = int(height)
        # (agent_id, ix, iy, action) → counters
        self._buckets: dict[tuple[str, int, int, str], dict[str, Any]] = {}
        self._events: deque[dict[str, Any]] = deque(maxlen=max(8, int(event_capacity)))
        self._n_observations = 0
        self._last_tick: dict[str, int] = {}
        self._overlay_cache_key: tuple[Any, ...] | None = None
        self._overlay_cache: dict[str, Any] | None = None

    def reset(self, *, width: int | None = None, height: int | None = None) -> None:
        if width is not None:
            self.width = int(width)
        if height is not None:
            self.height = int(height)
        self._buckets.clear()
        self._events.clear()
        self._n_observations = 0
        self._last_tick.clear()
        self._overlay_cache_key = None
        self._overlay_cache = None

    def observe(
        self,
        *,
        agent_id: str,
        tick: int,
        action: str | None,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        contact: bool | None = None,
    ) -> dict[str, Any] | None:
        """Ingest one consecutive-tick step. Returns step metrics or None if skipped."""
        aid = str(agent_id)
        t = int(tick)
        # Guard against duplicate / out-of-order observes
        prev_t = self._last_tick.get(aid)
        if prev_t is not None and t <= prev_t:
            return None
        self._last_tick[aid] = t

        if action is None or not str(action).startswith("MOVE:"):
            return None
        unit = action_direction_unit(action)
        if unit is None:
            return None

        dx, dy, mag = realized_displacement(
            x0, y0, x1, y1, width=self.width, height=self.height,
        )
        align = action_alignment(action, dx, dy)
        outcome = traversal_outcome_class(action, dx, dy)
        ix, iy = bin_cell(x0, y0, width=self.width, height=self.height)
        self._n_observations += 1

        key = (aid, ix, iy, str(action))
        b = self._buckets.get(key)
        if b is None:
            b = {
                "attempts": 0,
                "aligned": 0,
                "opposing": 0,
                "deflected": 0,
                "near_zero": 0,
                "sum_align": 0.0,
                "n_align": 0,
                "sum_mag": 0.0,
                "sum_fwd": 0.0,
                "n_fwd": 0,
                "contact_attempts": 0,
                "contact_opposing": 0,
            }
            self._buckets[key] = b
        b["attempts"] += 1
        b["sum_mag"] += mag
        if align is not None:
            b["sum_align"] += float(align)
            b["n_align"] += 1
            b["sum_fwd"] += float(align) * mag  # proxy; forward stored via align*mag
            b["n_fwd"] += 1
        if outcome == "ALIGNED_TRAVERSAL":
            b["aligned"] += 1
        elif outcome == "OPPOSING_DISPLACEMENT":
            b["opposing"] += 1
        elif outcome == "DEFLECTED_DISPLACEMENT":
            b["deflected"] += 1
        elif outcome == "NEAR_ZERO_DISPLACEMENT":
            b["near_zero"] += 1
        if contact:
            b["contact_attempts"] += 1
            if outcome == "OPPOSING_DISPLACEMENT":
                b["contact_opposing"] += 1

        # Recent geometry events (bounded)
        if outcome == "OPPOSING_DISPLACEMENT" and align is not None and align <= -0.7 and mag > 0.05:
            self._events.append({
                "kind": "STRONG_DEFLECTION",
                "agent_id": aid,
                "tick": t,
                "x": float(x0),
                "y": float(y0),
                "cell": [ix, iy],
                "action": str(action),
                "dx": dx,
                "dy": dy,
                "disp_mag": mag,
                "action_alignment": align,
                "outcome": outcome,
                "contact": bool(contact) if contact is not None else None,
            })
        elif outcome == "OPPOSING_DISPLACEMENT":
            # Track reversals lightly (may coalesce in UI)
            self._events.append({
                "kind": "REVERSAL",
                "agent_id": aid,
                "tick": t,
                "x": float(x0),
                "y": float(y0),
                "cell": [ix, iy],
                "action": str(action),
                "dx": dx,
                "dy": dy,
                "disp_mag": mag,
                "action_alignment": align,
                "outcome": outcome,
                "contact": bool(contact) if contact is not None else None,
            })

        return {
            "agent_id": aid,
            "tick": t,
            "action": str(action),
            "cell": [ix, iy],
            "dx": dx,
            "dy": dy,
            "disp_mag": mag,
            "action_alignment": align,
            "outcome": outcome,
            "contact": contact,
            "requested_unit": list(unit),
        }

    def _mean_align(self, b: dict[str, Any]) -> float | None:
        n = int(b.get("n_align") or 0)
        if n <= 0:
            return None
        return float(b["sum_align"]) / n

    def _bucket_summary(self, b: dict[str, Any], *, ix: int, iy: int, action: str) -> dict[str, Any]:
        attempts = int(b["attempts"])
        opposing = int(b["opposing"])
        aligned = int(b["aligned"])
        mean_a = self._mean_align(b)
        cls = classify_bucket(attempts, opposing, aligned, mean_a)
        unit = action_direction_unit(action)
        return {
            "cell": [ix, iy],
            "action": action,
            "attempts": attempts,
            "aligned": aligned,
            "opposing": opposing,
            "deflected": int(b["deflected"]),
            "near_zero": int(b["near_zero"]),
            "aligned_rate": aligned / attempts if attempts else None,
            "opposing_rate": opposing / attempts if attempts else None,
            "mean_action_alignment": mean_a,
            "mean_disp_mag": (float(b["sum_mag"]) / attempts) if attempts else None,
            "contact_attempts": int(b["contact_attempts"]),
            "contact_opposing": int(b["contact_opposing"]),
            "evidence_class": evidence_class(attempts),
            "class_code": cls,
            "class_label": CLASS_LABELS[cls],
            "requested_unit": list(unit) if unit else None,
        }

    def _aggregate_agent_filter(
        self,
        agent_filter: str,
    ) -> dict[tuple[int, int, str], dict[str, Any]]:
        """Merge buckets for ALL or a single agent."""
        merged: dict[tuple[int, int, str], dict[str, Any]] = {}
        for (aid, ix, iy, action), b in self._buckets.items():
            if agent_filter != "ALL" and aid != agent_filter:
                continue
            key = (ix, iy, action)
            m = merged.get(key)
            if m is None:
                m = {
                    "attempts": 0, "aligned": 0, "opposing": 0, "deflected": 0, "near_zero": 0,
                    "sum_align": 0.0, "n_align": 0, "sum_mag": 0.0,
                    "contact_attempts": 0, "contact_opposing": 0,
                }
                merged[key] = m
            for k in ("attempts", "aligned", "opposing", "deflected", "near_zero",
                      "n_align", "contact_attempts", "contact_opposing"):
                m[k] += int(b[k])
            m["sum_align"] += float(b["sum_align"])
            m["sum_mag"] += float(b["sum_mag"])
        return merged

    def cell_directional(
        self,
        ix: int,
        iy: int,
        *,
        agent_filter: str = "ALL",
    ) -> dict[str, Any]:
        """N/E/S/W stats for one cell under an agent filter."""
        merged = self._aggregate_agent_filter(agent_filter)
        dirs: dict[str, Any] = {}
        total = 0
        for action in MOVE_ACTIONS:
            b = merged.get((ix, iy, action))
            if b is None:
                dirs[action] = {
                    "attempts": 0,
                    "evidence_class": "NO_SAMPLES",
                    "class_label": "UNKNOWN",
                    "class_code": CLASS_UNKNOWN,
                }
                continue
            summary = self._bucket_summary(b, ix=ix, iy=iy, action=action)
            dirs[action] = summary
            total += int(summary["attempts"])
        # Per-agent split when filter is ALL
        by_agent: dict[str, Any] = {}
        if agent_filter == "ALL":
            for aid in sorted({k[0] for k in self._buckets}):
                by_agent[aid] = self.cell_directional(ix, iy, agent_filter=aid)["directions"]

        # Cell-level class = worst among dirs with samples
        worst = CLASS_UNKNOWN
        for d in dirs.values():
            code = int(d.get("class_code") or 0)
            if code > worst:
                worst = code
        return {
            "cell": [ix, iy],
            "agent_filter": agent_filter,
            "total_attempts": total,
            "class_code": worst,
            "class_label": CLASS_LABELS[worst],
            "directions": dirs,
            "by_agent": by_agent if agent_filter == "ALL" else {},
            "note": "Empirical Observer rates — not semantic terrain.",
        }

    def hydrate_from_steps(self, steps: list[dict[str, Any]]) -> int:
        """Bulk-load empirical steps (e.g. from scientific_timeline). Observer-only.

        Bypasses LIVE tick-monotonic guard so historical ticks can be loaded, then
        clears `_last_tick` so subsequent LIVE ticks are accepted.
        """
        n = 0
        saved = dict(self._last_tick)
        self._last_tick.clear()
        # Force accept all historical ticks by temporarily disabling monotonic check
        for st in steps:
            aid = str(st.get("agent_id") or "agent_0")
            t = int(st.get("tick") or 0)
            # Directly set last tick behind so observe accepts
            self._last_tick[aid] = t - 1
            out = self.observe(
                agent_id=aid,
                tick=t,
                action=st.get("action"),
                x0=float(st.get("x0") or 0.0),
                y0=float(st.get("y0") or 0.0),
                x1=float(st.get("x1") or 0.0),
                y1=float(st.get("y1") or 0.0),
                contact=st.get("contact"),
            )
            if out is not None:
                n += 1
        self._last_tick.clear()
        return n

    def overlay_payload(
        self,
        *,
        agent_filter: str = "ALL",
        max_glyphs: int = 96,
        max_events: int = 32,
        include_by_cell_min_attempts: int = 1,
        max_by_cell: int = 200,
        flat_grids: bool = False,
    ) -> dict[str, Any]:
        """Bounded overlay for LIVE/PAUSED frames."""
        cache_key = (
            self._n_observations,
            str(agent_filter),
            int(max_glyphs),
            int(max_events),
            int(include_by_cell_min_attempts),
            int(max_by_cell),
            bool(flat_grids),
            self.width,
            self.height,
        )
        if self._overlay_cache_key == cache_key and self._overlay_cache is not None:
            return self._overlay_cache

        w, h = self.width, self.height
        merged = self._aggregate_agent_filter(agent_filter)

        # Per-cell worst class + max opposing_rate
        class_grid = [[CLASS_UNKNOWN for _ in range(w)] for _ in range(h)]
        opp_grid: list[list[float | None]] = [[None for _ in range(w)] for _ in range(h)]
        align_grid: list[list[float | None]] = [[None for _ in range(w)] for _ in range(h)]
        attempt_grid = [[0 for _ in range(w)] for _ in range(h)]

        cell_dirs: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
        for (ix, iy, action), b in merged.items():
            summary = self._bucket_summary(b, ix=ix, iy=iy, action=action)
            cell_dirs[(ix, iy)].append(summary)
            attempt_grid[iy][ix] += int(summary["attempts"])
            code = int(summary["class_code"])
            if code > class_grid[iy][ix]:
                class_grid[iy][ix] = code
            opp = summary.get("opposing_rate")
            if opp is not None:
                cur = opp_grid[iy][ix]
                if cur is None or float(opp) > float(cur):
                    opp_grid[iy][ix] = float(opp)
            ma = summary.get("mean_action_alignment")
            if ma is not None:
                cur_a = align_grid[iy][ix]
                # Keep the most negative (worst) alignment for deflection view
                if cur_a is None or float(ma) < float(cur_a):
                    align_grid[iy][ix] = float(ma)

        # Glyphs: one per cell×action with enough evidence, prefer strongest signal
        glyph_candidates = []
        for summaries in cell_dirs.values():
            for s in summaries:
                if int(s["attempts"]) < 3:
                    continue
                unit = s.get("requested_unit") or []
                if len(unit) != 2:
                    continue
                glyph_candidates.append(s)
        glyph_candidates.sort(
            key=lambda s: (
                abs(float(s.get("mean_action_alignment") or 0.0)),
                int(s["attempts"]),
            ),
            reverse=True,
        )
        glyphs = []
        for s in glyph_candidates[:max_glyphs]:
            unit = s["requested_unit"]
            glyphs.append({
                "x": s["cell"][0] + 0.5,
                "y": s["cell"][1] + 0.5,
                "ux": unit[0],
                "uy": unit[1],
                "action": s["action"],
                "attempts": s["attempts"],
                "mean_align": s["mean_action_alignment"],
                "opposing_rate": s["opposing_rate"],
                "class_label": s["class_label"],
                "evidence_class": s["evidence_class"],
            })

        # by_cell sparse (directional) for inspector — built from already-aggregated
        # cell_dirs. Do NOT call cell_directional here (that re-scans all buckets
        # per cell and is O(max_by_cell × buckets × agents) under the capture lock).
        by_cell: dict[str, Any] = {}
        if max_by_cell > 0:
            ranked_cells = sorted(
                cell_dirs.keys(),
                key=lambda c: sum(int(s["attempts"]) for s in cell_dirs[c]),
                reverse=True,
            )
            for ix, iy in ranked_cells:
                if len(by_cell) >= max_by_cell:
                    break
                summaries = cell_dirs[(ix, iy)]
                total = sum(int(s["attempts"]) for s in summaries)
                if total < include_by_cell_min_attempts:
                    continue
                dirs: dict[str, Any] = {}
                worst = CLASS_UNKNOWN
                for s in summaries:
                    dirs[str(s["action"])] = s
                    code = int(s.get("class_code") or 0)
                    if code > worst:
                        worst = code
                # Fill missing MOVE dirs with empty stubs (stable shape for UI)
                for action in MOVE_ACTIONS:
                    if action not in dirs:
                        dirs[action] = {
                            "attempts": 0,
                            "evidence_class": "NO_SAMPLES",
                            "class_label": "UNKNOWN",
                            "class_code": CLASS_UNKNOWN,
                        }
                by_cell[f"{ix},{iy}"] = {
                    "cell": [ix, iy],
                    "agent_filter": agent_filter,
                    "total_attempts": total,
                    "class_code": worst,
                    "class_label": CLASS_LABELS[worst],
                    "directions": dirs,
                    "by_agent": {},
                    "note": "Empirical Observer rates — not semantic terrain. "
                    "Per-agent split via /api/geometry/cell on demand.",
                }

        # Events filtered by agent
        events = []
        for ev in reversed(self._events):
            if agent_filter != "ALL" and ev.get("agent_id") != agent_filter:
                continue
            events.append(ev)
            if len(events) >= max_events:
                break
        events.reverse()

        if flat_grids:
            class_out: Any = flatten_grid(class_grid)
            opp_out: Any = flatten_grid(opp_grid)  # type: ignore[arg-type]
            align_out: Any = flatten_grid(align_grid)  # type: ignore[arg-type]
            attempt_out: Any = flatten_grid(attempt_grid)
        else:
            class_out = class_grid
            opp_out = opp_grid
            align_out = align_grid
            attempt_out = attempt_grid

        payload = {
            "status": "AVAILABLE",
            "observer_only": True,
            "agent_filter": agent_filter,
            "width": w,
            "height": h,
            "n_observations": self._n_observations,
            "n_buckets": len(self._buckets),
            "empirical_version": int(self._n_observations),
            "grids_encoding": "flat" if flat_grids else "nested",
            "class_grid": class_out,
            "opposing_rate_grid": opp_out,
            "worst_alignment_grid": align_out,
            "attempt_grid": attempt_out,
            "glyphs": glyphs,
            "events": events,
            "class_legend": CLASS_LABELS,
            "honesty": {
                "empirical_not_terrain": True,
                "no_hard_walls": True,
                "low_evidence_not_easy": True,
                "not_agent_perception": True,
                "ground_truth_flow_separate": True,
            },
        }
        if by_cell:
            payload["by_cell"] = by_cell
        self._overlay_cache_key = cache_key
        self._overlay_cache = payload
        return payload
