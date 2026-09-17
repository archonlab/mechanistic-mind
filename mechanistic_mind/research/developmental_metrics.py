\
"""Update 4.2 Observer/experiment-only developmental metrics.

Never exposed to cognition.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any


ACQUISITION_STAGES = (
    "L0_NO_ENCOUNTER",
    "L1_ACCIDENTAL_ENCOUNTER",
    "L2_BODY_CONSEQUENCE",
    "L3_EXPERIENCE_RETENTION",
    "L4_LATER_RETRIEVAL",
    "L5_DECISION_INFLUENCE",
    "L6_REPEATED_ACQUISITION",
    "L7_SELF_MAINTENANCE",
)


@dataclass
class CollapseConfig:
    window: int = 100
    max_unique_actions: int = 1
    min_same_action_fraction: float = 0.95
    min_residence: int = 50


def action_family(action: str) -> str:
    if ":" in action:
        return action.split(":", 1)[0]
    return action


@dataclass
class RunSeries:
    actions: list[str] = field(default_factory=list)
    energy: list[float | None] = field(default_factory=list)
    hydration: list[float | None] = field(default_factory=list)
    fatigue: list[float | None] = field(default_factory=list)
    mass: list[float | None] = field(default_factory=list)
    depth: list[float | None] = field(default_factory=list)
    maturity: list[float | None] = field(default_factory=list)
    tokens: list[float | None] = field(default_factory=list)
    retrieval_perceptual: list[bool] = field(default_factory=list)
    energy_transfer_pos: list[bool] = field(default_factory=list)
    hydration_transfer_pos: list[bool] = field(default_factory=list)
    selection_reasons: list[str] = field(default_factory=list)
    decision_sources: list[str] = field(default_factory=list)

    def append_tick(self, row: dict[str, Any]) -> None:
        self.actions.append(str(row.get("action") or "UNKNOWN"))
        body = row.get("body") if isinstance(row.get("body"), dict) else {}
        self.energy.append(_f(body.get("energy_reserve")))
        self.hydration.append(_f(body.get("hydration")))
        self.fatigue.append(_f(body.get("fatigue")))
        self.mass.append(_f(body.get("mass_kg")))
        self.depth.append(_f(row.get("cognitive_depth")))
        self.maturity.append(_f(row.get("local_experience_maturity")))
        self.tokens.append(_f(row.get("perceptual_token_count")))
        rm = row.get("retrieval_match") if isinstance(row.get("retrieval_match"), dict) else {}
        self.retrieval_perceptual.append(bool(rm.get("perceptual_features")))
        self.energy_transfer_pos.append(bool(row.get("energy_transfer_positive")))
        self.hydration_transfer_pos.append(bool(row.get("hydration_transfer_positive")))
        self.selection_reasons.append(str(row.get("selection_reason") or ""))
        self.decision_sources.append(str(row.get("decision_source") or ""))


def _f(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def time_to_policy_collapse(
    actions: list[str], config: CollapseConfig | None = None
) -> dict[str, Any]:
    cfg = config or CollapseConfig()
    if len(actions) < cfg.window:
        return {"collapsed": False, "tick": None, "dominant_action": None}
    for end in range(cfg.window, len(actions) + 1):
        window = actions[end - cfg.window : end]
        counts = Counter(window)
        dominant, n = counts.most_common(1)[0]
        unique = len(counts)
        frac = n / cfg.window
        if unique <= cfg.max_unique_actions and frac >= cfg.min_same_action_fraction:
            # require residence continuity ending here
            residence = 0
            for act in reversed(actions[:end]):
                if act == dominant:
                    residence += 1
                else:
                    break
            if residence >= cfg.min_residence:
                return {
                    "collapsed": True,
                    "tick": end - 1,
                    "dominant_action": dominant,
                    "unique_in_window": unique,
                    "same_action_fraction": frac,
                    "residence": residence,
                    "criterion": {
                        "window": cfg.window,
                        "max_unique_actions": cfg.max_unique_actions,
                        "min_same_action_fraction": cfg.min_same_action_fraction,
                        "min_residence": cfg.min_residence,
                    },
                }
    return {"collapsed": False, "tick": None, "dominant_action": None}


def attractor_episodes(actions: list[str], min_residence: int = 20) -> list[dict[str, Any]]:
    if not actions:
        return []
    episodes = []
    start = 0
    cur = actions[0]
    for i, act in enumerate(actions + [None]):
        if act != cur:
            duration = i - start
            if duration >= min_residence:
                episodes.append(
                    {
                        "action": cur,
                        "start_tick": start,
                        "end_tick": i - 1,
                        "duration": duration,
                    }
                )
            start = i
            cur = act
    return episodes


def classify_acquisition_stage(series: RunSeries) -> dict[str, Any]:
    """Heuristic L0–L7 from available telemetry (Observer-only)."""
    encounters = sum(1 for x in series.energy_transfer_pos if x) + sum(
        1 for x in series.hydration_transfer_pos if x
    )
    stage = "L0_NO_ENCOUNTER"
    if encounters >= 1:
        stage = "L1_ACCIDENTAL_ENCOUNTER"
        stage = "L2_BODY_CONSEQUENCE"  # transfers already are body deltas
        # L3 if any experience retention proxy: non-zero maturity growth or tokens
        mats = [m for m in series.maturity if m is not None]
        if mats and max(mats) > (mats[0] + 1e-6):
            stage = "L3_EXPERIENCE_RETENTION"
        if any(series.retrieval_perceptual):
            stage = "L4_LATER_RETRIEVAL"
        # L5 attribution is weak without causal tooling — mark only if retrieval+non-WAIT after encounter
        if stage == "L4_LATER_RETRIEVAL":
            first_enc = next(
                (
                    i
                    for i, (e, h) in enumerate(
                        zip(series.energy_transfer_pos, series.hydration_transfer_pos)
                    )
                    if e or h
                ),
                None,
            )
            if first_enc is not None:
                later = series.actions[first_enc + 1 :]
                if any(action_family(a) in {"USE", "TAKE", "PUSH", "MOVE"} for a in later):
                    stage = "L5_DECISION_INFLUENCE"
        if encounters >= 2:
            stage = "L6_REPEATED_ACQUISITION"
        # L7: multiple depletion→acquisition cycles (energy rose after near-zero)
        cycles = 0
        low = False
        for e, pos in zip(series.energy, series.energy_transfer_pos):
            if e is not None and e <= 0.05:
                low = True
            if low and pos:
                cycles += 1
                low = False
        if cycles >= 2 and encounters >= 3:
            stage = "L7_SELF_MAINTENANCE"
    return {
        "stage": stage,
        "encounters": encounters,
        "stages_enum": list(ACQUISITION_STAGES),
        "provenance": "observer_analysis_only",
    }


def learning_runway_before_depletion(
    series: RunSeries,
    *,
    severe_energy: float = 0.15,
) -> dict[str, Any]:
    idx = None
    for i, e in enumerate(series.energy):
        if e is not None and e <= severe_energy:
            idx = i
            break
    if idx is None:
        idx = len(series.actions)
    slice_actions = series.actions[:idx]
    return {
        "ticks_before_severe_energy": idx,
        "unique_actions": len(set(slice_actions)),
        "action_families": dict(Counter(action_family(a) for a in slice_actions)),
        "mean_tokens": _mean(series.tokens[:idx]),
        "retrieval_perceptual_rate": (
            sum(1 for x in series.retrieval_perceptual[:idx] if x) / idx if idx else 0.0
        ),
        "final_maturity": series.maturity[idx - 1] if idx and series.maturity[idx - 1:] else None,
        "final_depth": series.depth[idx - 1] if idx and series.depth[idx - 1:] else None,
        "energy_transfer_encounters": sum(1 for x in series.energy_transfer_pos[:idx] if x),
        "hydration_transfer_encounters": sum(
            1 for x in series.hydration_transfer_pos[:idx] if x
        ),
        "provenance": "derived_observer_only",
    }


def window_report(series: RunSeries, edges: list[tuple[int, int]]) -> list[dict[str, Any]]:
    rows = []
    n = len(series.actions)
    for lo, hi in edges:
        lo2, hi2 = max(0, lo), min(n, hi)
        if lo2 >= hi2:
            continue
        acts = series.actions[lo2:hi2]
        rows.append(
            {
                "window": [lo2, hi2],
                "action_families": dict(Counter(action_family(a) for a in acts)),
                "unique_actions": len(set(acts)),
                "mean_energy": _mean(series.energy[lo2:hi2]),
                "mean_hydration": _mean(series.hydration[lo2:hi2]),
                "mean_fatigue": _mean(series.fatigue[lo2:hi2]),
                "mean_depth": _mean(series.depth[lo2:hi2]),
                "mean_maturity": _mean(series.maturity[lo2:hi2]),
                "mean_tokens": _mean(series.tokens[lo2:hi2]),
                "retrieval_perceptual_rate": (
                    sum(1 for x in series.retrieval_perceptual[lo2:hi2] if x)
                    / max(1, hi2 - lo2)
                ),
            }
        )
    return rows


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    return sum(vals) / len(vals) if vals else None
