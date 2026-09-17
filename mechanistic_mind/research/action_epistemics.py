"""Update 4.3 — Observer/diagnostic action epistemics (no policy effect).

Prediction status and lockout flags are analysis metadata only.
Do not feed these into ordinary value, scoring, or selection.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable


class PredictionStatus(str, Enum):
    NO_EVIDENCE = "NO_EVIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    SUPPORTED = "SUPPORTED"
    CONFLICTED = "CONFLICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class LockoutFlag(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"
    INSUFFICIENT_OPPORTUNITY = "INSUFFICIENT_OPPORTUNITY"
    UNKNOWN_BUT_SAMPLED = "UNKNOWN_BUT_SAMPLED"
    LOCKOUT_CANDIDATE = "LOCKOUT_CANDIDATE"
    LOCKOUT_SUPPORTED = "LOCKOUT_SUPPORTED"
    NEGATIVE_EVIDENCE_DOMINATED = "NEGATIVE_EVIDENCE_DOMINATED"
    PHYSICALLY_UNAVAILABLE = "PHYSICALLY_UNAVAILABLE"
    PHYSIOLOGY_DOMINATED = "PHYSIOLOGY_DOMINATED"


class EpistemicEvidenceKind(str, Enum):
    UNKNOWN = "UNKNOWN"
    NEUTRAL = "NEUTRAL"
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    CONFLICTED = "CONFLICTED"


# Thresholds are diagnostic labels only — they do not change selection.
_MIN_SUPPORT_SUPPORTED = 3.0
_MIN_CONFIDENCE_SUPPORTED = 0.35
_NEUTRAL_ABS = 1e-9


def classify_prediction_status(
    *,
    support: float | None,
    confidence: float | None,
    predicted: dict[str, Any] | None,
    physically_available: bool,
) -> PredictionStatus:
    if not physically_available:
        return PredictionStatus.NOT_APPLICABLE
    support_v = float(support or 0.0)
    confidence_v = float(confidence or 0.0)
    has_pred = bool(predicted)
    if support_v <= 0.0 and confidence_v <= 0.0 and not has_pred:
        return PredictionStatus.NO_EVIDENCE
    if support_v < _MIN_SUPPORT_SUPPORTED or confidence_v < _MIN_CONFIDENCE_SUPPORTED:
        return PredictionStatus.INSUFFICIENT_EVIDENCE
    # Conflict detection left conservative: caller may override via evidence_kind.
    return PredictionStatus.SUPPORTED


def classify_evidence_kind(
    *,
    prediction_status: PredictionStatus,
    ordinary_value: float | None,
) -> EpistemicEvidenceKind:
    if prediction_status in (
        PredictionStatus.NO_EVIDENCE,
        PredictionStatus.NOT_APPLICABLE,
    ):
        return EpistemicEvidenceKind.UNKNOWN
    if prediction_status == PredictionStatus.CONFLICTED:
        return EpistemicEvidenceKind.CONFLICTED
    if ordinary_value is None:
        return EpistemicEvidenceKind.UNKNOWN
    v = float(ordinary_value)
    if abs(v) <= _NEUTRAL_ABS:
        return EpistemicEvidenceKind.NEUTRAL
    return EpistemicEvidenceKind.POSITIVE if v > 0 else EpistemicEvidenceKind.NEGATIVE


@dataclass
class ActionCandidateEpistemicRow:
    """One candidate at one diagnostic decision point (Observer-only)."""

    tick: int
    action: str
    physically_available: bool
    candidate_generated: bool
    proposal_source: str | None = None
    lifetime_execution_count: int = 0
    recent_execution_count: int = 0
    relevant_experience_count: float = 0.0
    retrieval_match_count: int = 0
    retrieval_support: float = 0.0
    prediction_status: str = PredictionStatus.NO_EVIDENCE.value
    prediction_value: float | None = None
    prediction_confidence: float | None = None
    uncertainty_represented: bool = False
    local_maturity: float | None = None
    cognitive_depth: float | None = None
    developmental_gate_factor: float | None = None
    effort_contribution: float = 0.0
    body_state_contribution: float = 0.0
    ordinary_value_contribution: float = 0.0
    final_score: float = 0.0
    ranking: int | None = None
    selected: bool = False
    selection_or_rejection_reason: str | None = None
    evidence_kind: str = EpistemicEvidenceKind.UNKNOWN.value
    lockout_flag: str = LockoutFlag.NOT_ASSESSED.value
    physiology_severe: bool = False
    observer_note: str = "OBSERVER ANALYSIS — NOT AVAILABLE TO COGNITION"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def annotate_proposal_metadata(proposal: dict[str, Any], *, physically_available: bool) -> dict[str, Any]:
    """Attach prediction_status to a proposal copy. Does not alter scores."""
    out = dict(proposal)
    support = float(out.get("support", 0.0) or 0.0)
    confidence = float(out.get("confidence", 0.0) or 0.0)
    predicted = out.get("predicted_transition") or out.get("predicted") or {}
    status = classify_prediction_status(
        support=support,
        confidence=confidence,
        predicted=predicted if isinstance(predicted, dict) else {},
        physically_available=physically_available,
    )
    value = float(out.get("ordinary_action_value", 0.0) or 0.0)
    kind = classify_evidence_kind(prediction_status=status, ordinary_value=value)
    meta = dict(out.get("epistemic_metadata") or {})
    meta.update(
        {
            "prediction_status": status.value,
            "evidence_kind": kind.value,
            "unknown_collapsed_to_zero_ordinary_value": (
                status == PredictionStatus.NO_EVIDENCE and abs(value) <= _NEUTRAL_ABS
            ),
            "observer_only": True,
        }
    )
    out["epistemic_metadata"] = meta
    # Mirror top-level for easy telemetry without implying policy use.
    out["prediction_status"] = status.value
    out["evidence_kind"] = kind.value
    return out


def build_rows_from_selection(
    *,
    tick: int,
    available: Iterable[str],
    selection: dict[str, Any],
    execution_counts: dict[str, int] | None = None,
    experience_counts: dict[str, float] | None = None,
    gate: dict[str, Any] | None = None,
    physiology_severe: bool = False,
) -> list[ActionCandidateEpistemicRow]:
    available_set = {str(a) for a in available}
    exec_counts = execution_counts or {}
    exp_counts = experience_counts or {}
    candidates = list(selection.get("candidates") or [])
    selected_action = str(selection.get("action") or "")
    reason = str(selection.get("reason") or "")
    rows: list[ActionCandidateEpistemicRow] = []
    for rank, item in enumerate(candidates, start=1):
        action = str(item.get("action"))
        support = float(item.get("support", 0.0) or 0.0)
        confidence = float(item.get("confidence", 0.0) or 0.0)
        ordinary = float(item.get("ordinary_action_value", item.get("score", 0.0)) or 0.0)
        phys = action in available_set
        status = classify_prediction_status(
            support=support,
            confidence=confidence,
            predicted=item.get("predicted_transition"),
            physically_available=phys,
        )
        kind = classify_evidence_kind(prediction_status=status, ordinary_value=ordinary)
        effort = 0.04 if action.startswith(("PUSH:", "TAKE:", "USE:", "MOVE:")) else 0.0
        body = 0.0
        if physiology_severe and action != "WAIT":
            body = -(0.35 + effort)
        rows.append(
            ActionCandidateEpistemicRow(
                tick=tick,
                action=action,
                physically_available=phys,
                candidate_generated=True,
                proposal_source=str(item.get("source")) if item.get("source") is not None else None,
                lifetime_execution_count=int(exec_counts.get(action, 0)),
                relevant_experience_count=float(exp_counts.get(action, 0.0)),
                retrieval_support=support,
                prediction_status=status.value,
                prediction_confidence=confidence,
                local_maturity=(
                    float(gate["local_experience_maturity"])
                    if isinstance(gate, dict) and gate.get("local_experience_maturity") is not None
                    else None
                ),
                cognitive_depth=(
                    float(gate["cognitive_depth"])
                    if isinstance(gate, dict) and gate.get("cognitive_depth") is not None
                    else None
                ),
                developmental_gate_factor=(
                    float(gate["gate_factor"])
                    if isinstance(gate, dict) and gate.get("gate_factor") is not None
                    else None
                ),
                effort_contribution=effort if physiology_severe else 0.0,
                body_state_contribution=body,
                ordinary_value_contribution=ordinary,
                final_score=float(item.get("score", ordinary) or 0.0),
                ranking=rank,
                selected=(action == selected_action),
                selection_or_rejection_reason=reason if action == selected_action else "NOT_SELECTED",
                evidence_kind=kind.value,
                physiology_severe=physiology_severe,
            )
        )
    # Mark physically available actions missing from candidates.
    seen = {r.action for r in rows}
    for action in sorted(available_set):
        if action in seen:
            continue
        rows.append(
            ActionCandidateEpistemicRow(
                tick=tick,
                action=action,
                physically_available=True,
                candidate_generated=False,
                lifetime_execution_count=int(exec_counts.get(action, 0)),
                relevant_experience_count=float(exp_counts.get(action, 0.0)),
                prediction_status=PredictionStatus.NO_EVIDENCE.value,
                evidence_kind=EpistemicEvidenceKind.UNKNOWN.value,
                selection_or_rejection_reason="NOT_IN_CANDIDATE_SET",
                physiology_severe=physiology_severe,
            )
        )
    return rows
