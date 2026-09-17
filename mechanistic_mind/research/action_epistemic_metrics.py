"""Update 4.3 — aggregatable action-epistemic metrics (Observer/analysis only)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any


FAMILY_PREFIXES = ("MOVE", "EMIT", "WAIT", "USE", "TAKE", "RELEASE", "PUSH")


def action_family(action: str) -> str:
    a = str(action)
    for prefix in FAMILY_PREFIXES:
        if a == prefix or a.startswith(prefix + ":"):
            return prefix
    return "OTHER"


@dataclass
class ActionBootstrapCascade:
    action: str
    first_availability_tick: int | None = None
    first_candidacy_tick: int | None = None
    first_selection_tick: int | None = None
    first_consequence_tick: int | None = None
    first_stored_experience_tick: int | None = None
    first_retrieval_tick: int | None = None
    first_supported_prediction_tick: int | None = None
    first_evidence_influenced_selection_tick: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActionOpportunityStats:
    action: str
    availability_ticks: int = 0
    unknown_ticks: int = 0
    candidate_ticks: int = 0
    selection_count: int = 0
    selection_rate_when_unknown: float | None = None
    mean_rank_when_unknown: float | None = None
    mean_score_when_unknown: float | None = None
    time_to_first_execution: int | None = None
    time_to_second_execution: int | None = None
    time_to_first_relevant_experience: int | None = None
    time_to_first_supported_prediction: int | None = None
    longest_non_selection_while_available: int = 0
    pre_depletion_selections: int = 0
    post_depletion_selections: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EpistemicRunAggregator:
    cascades: dict[str, ActionBootstrapCascade] = field(default_factory=dict)
    stats: dict[str, ActionOpportunityStats] = field(default_factory=dict)
    _unknown_ranks: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    _unknown_scores: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    _unknown_selected: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    _exec_ticks: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    _gap: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    coverage: dict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(
            lambda: {
                "physically_available_opportunities": 0,
                "executions": 0,
                "stored_consequences": 0,
                "later_retrievals": 0,
                "supported_predictions": 0,
            }
        )
    )

    def _cascade(self, action: str) -> ActionBootstrapCascade:
        if action not in self.cascades:
            self.cascades[action] = ActionBootstrapCascade(action=action)
        return self.cascades[action]

    def _stat(self, action: str) -> ActionOpportunityStats:
        if action not in self.stats:
            self.stats[action] = ActionOpportunityStats(action=action)
        return self.stats[action]

    def observe_row(self, row: dict[str, Any], *, depletion: bool = False) -> None:
        action = str(row.get("action"))
        tick = int(row.get("tick", 0))
        fam = action_family(action)
        st = self._stat(action)
        cas = self._cascade(action)
        if row.get("physically_available"):
            st.availability_ticks += 1
            self.coverage[fam]["physically_available_opportunities"] += 1
            if cas.first_availability_tick is None:
                cas.first_availability_tick = tick
            self._gap[action] = self._gap.get(action, 0) + 1
            st.longest_non_selection_while_available = max(
                st.longest_non_selection_while_available, self._gap[action]
            )
        status = str(row.get("prediction_status") or "")
        unknown = status in ("NO_EVIDENCE", "INSUFFICIENT_EVIDENCE")
        if unknown and row.get("physically_available"):
            st.unknown_ticks += 1
        if row.get("candidate_generated"):
            st.candidate_ticks += 1
            if cas.first_candidacy_tick is None:
                cas.first_candidacy_tick = tick
        if row.get("selected"):
            st.selection_count += 1
            self._gap[action] = 0
            self._exec_ticks[action].append(tick)
            self.coverage[fam]["executions"] += 1
            if cas.first_selection_tick is None:
                cas.first_selection_tick = tick
            if depletion:
                st.post_depletion_selections += 1
            else:
                st.pre_depletion_selections += 1
            if unknown:
                self._unknown_selected[action].append(1)
            if str(row.get("evidence_kind")) in ("POSITIVE", "NEGATIVE", "NEUTRAL", "CONFLICTED"):
                if status == "SUPPORTED" and cas.first_evidence_influenced_selection_tick is None:
                    cas.first_evidence_influenced_selection_tick = tick
        elif unknown and row.get("physically_available"):
            self._unknown_selected[action].append(0)
        if unknown and row.get("ranking") is not None:
            self._unknown_ranks[action].append(float(row["ranking"]))
        if unknown and row.get("final_score") is not None:
            self._unknown_scores[action].append(float(row["final_score"]))
        if float(row.get("relevant_experience_count") or 0) > 0:
            if cas.first_stored_experience_tick is None:
                cas.first_stored_experience_tick = tick
            if st.time_to_first_relevant_experience is None:
                st.time_to_first_relevant_experience = tick
            self.coverage[fam]["stored_consequences"] += 1
        if float(row.get("retrieval_support") or 0) > 0 or int(row.get("retrieval_match_count") or 0) > 0:
            if cas.first_retrieval_tick is None:
                cas.first_retrieval_tick = tick
            self.coverage[fam]["later_retrievals"] += 1
        if status == "SUPPORTED":
            if cas.first_supported_prediction_tick is None:
                cas.first_supported_prediction_tick = tick
            if st.time_to_first_supported_prediction is None:
                st.time_to_first_supported_prediction = tick
            self.coverage[fam]["supported_predictions"] += 1

    def finalize(self) -> dict[str, Any]:
        for action, st in self.stats.items():
            ticks = self._exec_ticks.get(action, [])
            if ticks:
                st.time_to_first_execution = ticks[0]
            if len(ticks) >= 2:
                st.time_to_second_execution = ticks[1]
            sel = self._unknown_selected.get(action, [])
            if sel:
                st.selection_rate_when_unknown = sum(sel) / len(sel)
            ranks = self._unknown_ranks.get(action, [])
            if ranks:
                st.mean_rank_when_unknown = sum(ranks) / len(ranks)
            scores = self._unknown_scores.get(action, [])
            if scores:
                st.mean_score_when_unknown = sum(scores) / len(scores)
        return {
            "observer_note": "OBSERVER ANALYSIS — NOT AVAILABLE TO COGNITION",
            "cascades": {k: v.to_dict() for k, v in sorted(self.cascades.items())},
            "per_action": {k: v.to_dict() for k, v in sorted(self.stats.items())},
            "coverage_matrix_by_family": {k: dict(v) for k, v in sorted(self.coverage.items())},
        }
