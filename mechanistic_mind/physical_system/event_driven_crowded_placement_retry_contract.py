"""Acanthostega Beta 4 · Event-driven crowded placement retry contract V1.

Mechanism: event_driven_crowded_placement_retry_contract
Preset: ACANTHOSTEGA_BETA4_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
Parent: ACANTHOSTEGA_BETA4_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
Profile: EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT_V1

Formalizes existing SETMR→WMT→DTIP crowded rejection: one placement attempt
per eligible exertion event, no background retry, work retained on reject.
Does not change DTIP K=16, conflict geometry, or RCSS/ALTVSF force laws.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "event_driven_crowded_placement_retry_contract"
PROFILE_VERSION = "EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT_V1"
STATE_SCHEMA = "EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT_STATE_V1"
RECEIPT_KIND = "CROWDED_PLACEMENT_RETRY"
DEDUP_KEY_VERSION = "CROWDED_RETRY_DEDUP_V1"

BANNER = (
    "BETA4 · EVENT-DRIVEN CROWDED PLACEMENT RETRY CONTRACT V1 · "
    "NEW PHYSICAL EXERTION REQUIRED · ONE RETRY PER EVENT · "
    "NO BACKGROUND RETRY · K=16 UNCHANGED · NO PENDING MATERIAL"
)

RESEARCHER_FLAGS = {"researcher_only": True, "agent_accessible": False}

# Frozen placement policy references (no redesign).
PLACEMENT_CANDIDATE_COUNT = 16
PLACEMENT_POLICY_REF = "DETACHED_TERRAIN_PLACEMENT_POST_MUTATION_SUPPORT_V1"
MISSING_FAR_SW_OFFSET = (-0.70, -0.70)
CONFLICT_GEOMETRY_REF = "XY_DISK_OVERLAP_MARGIN_0.95_FULL_OBJECT_SCAN"
RETRY_TRIGGER = "RETRY_ONLY_ON_NEW_ELIGIBLE_PHYSICAL_EXERTION_EVENT"
MAX_RETRIES_PER_EVENT = 1

RESULT_PLACED = "PLACED"
RESULT_REJECTED_CROWDED = "REJECTED_CROWDED"
RESULT_REJECTED_OTHER = "REJECTED_OTHER_WMT_REASON"
RESULT_DEDUPLICATED = "DEDUPLICATED_SAME_EVENT"
RESULT_CELL_TICK_CAP = "CELL_TICK_CAP"
RESULT_NOT_INVOKED = "NOT_INVOKED"

HISTORY_LIMIT_DEFAULT = 64
DEDUP_LIMIT_DEFAULT = 256


@dataclass
class EventDrivenCrowdedPlacementRetryContractConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT
    dedup_limit: int = DEDUP_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "history_limit": int(self.history_limit),
            "dedup_limit": int(self.dedup_limit),
            "profile_version": PROFILE_VERSION,
            "retry_trigger": RETRY_TRIGGER,
            "max_retries_per_event": MAX_RETRIES_PER_EVENT,
            "automatic_background_retry": False,
            "placement_candidate_count": PLACEMENT_CANDIDATE_COUNT,
            "placement_policy_ref": PLACEMENT_POLICY_REF,
            "missing_far_sw_offset": list(MISSING_FAR_SW_OFFSET),
            "conflict_geometry_ref": CONFLICT_GEOMETRY_REF,
            "pending_detached_material": False,
            "failed_but_attached_state": False,
            "physical_placement_law_changed": False,
            "dedup_key_version": DEDUP_KEY_VERSION,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None
    ) -> "EventDrivenCrowdedPlacementRetryContractConfig":
        d = dict(data or {})
        return cls(
            enabled=bool(d.get("enabled", False)),
            history_limit=int(d.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            dedup_limit=int(d.get("dedup_limit", DEDUP_LIMIT_DEFAULT)),
        )


def validate_config(cfg: EventDrivenCrowdedPlacementRetryContractConfig) -> None:
    if int(cfg.history_limit) < 1:
        raise ValueError("history_limit must be >= 1")
    if int(cfg.dedup_limit) < 1:
        raise ValueError("dedup_limit must be >= 1")


def _line_ok(config: Any) -> bool:
    return (
        config is not None
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    )


def event_driven_crowded_placement_retry_contract_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "event_driven_crowded_placement_retry_contract", None)
    return cfg is not None and bool(getattr(cfg, "enabled", False))


def set_event_driven_crowded_placement_retry_contract(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "event_driven_crowded_placement_retry_contract", None)
    if cur is None:
        if on:
            config.event_driven_crowded_placement_retry_contract = (
                EventDrivenCrowdedPlacementRetryContractConfig(enabled=True)
            )
        return
    if isinstance(cur, dict):
        cfg = EventDrivenCrowdedPlacementRetryContractConfig.from_dict(cur)
        cfg.enabled = on
        config.event_driven_crowded_placement_retry_contract = cfg
    else:
        cur.enabled = on


@dataclass
class EventDrivenCrowdedPlacementRetryContractState:
    config: EventDrivenCrowdedPlacementRetryContractConfig
    last_step: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    # Ordered list of processed dedup key strings (bounded FIFO).
    processed_event_keys: list[str] = field(default_factory=list)
    processed_event_set: set[str] = field(default_factory=set)
    retry_event_seq: int = 0
    counters: dict[str, int] = field(
        default_factory=lambda: {
            "eligible_events": 0,
            "placement_attempts": 0,
            "placed": 0,
            "rejected_crowded": 0,
            "rejected_other": 0,
            "deduplicated": 0,
            "cell_tick_cap": 0,
            "passive_ticks_no_receipt": 0,
        }
    )


def state_of(world: Any) -> EventDrivenCrowdedPlacementRetryContractState | None:
    raw = getattr(world, "event_driven_crowded_placement_retry_contract_state", None)
    return raw if isinstance(raw, EventDrivenCrowdedPlacementRetryContractState) else None


def ensure_event_driven_crowded_placement_retry_contract_for_runtime(
    world: Any, config: Any
) -> EventDrivenCrowdedPlacementRetryContractState | None:
    if not event_driven_crowded_placement_retry_contract_is_active(config):
        if state_of(world) is not None:
            world.event_driven_crowded_placement_retry_contract_state = None
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "event_driven_crowded_placement_retry_contract", None)
    cfg = (
        EventDrivenCrowdedPlacementRetryContractConfig.from_dict(
            raw.to_dict() if hasattr(raw, "to_dict") else raw
        )
        if raw is not None
        else EventDrivenCrowdedPlacementRetryContractConfig(enabled=True)
    )
    cfg.enabled = True
    validate_config(cfg)
    st = EventDrivenCrowdedPlacementRetryContractState(config=cfg)
    world.event_driven_crowded_placement_retry_contract_state = st
    return st


def make_exertion_event_id(
    *,
    tick: int,
    cell_x: int,
    cell_y: int,
    body_id: Any,
    effector_id: Any,
    physical_source_kind: Any,
    attempt_seq: int,
) -> str:
    return (
        f"{int(tick)}|{int(cell_x)}|{int(cell_y)}|"
        f"{str(body_id or '')}|{str(effector_id or '')}|"
        f"{str(physical_source_kind or '')}|{int(attempt_seq)}"
    )


def make_dedup_key(*, exertion_event_id: str) -> str:
    return f"{DEDUP_KEY_VERSION}|{exertion_event_id}"


def _remember_key(st: EventDrivenCrowdedPlacementRetryContractState, key: str) -> None:
    if key in st.processed_event_set:
        return
    st.processed_event_set.add(key)
    st.processed_event_keys.append(key)
    lim = int(st.config.dedup_limit)
    while len(st.processed_event_keys) > lim:
        old = st.processed_event_keys.pop(0)
        st.processed_event_set.discard(old)


def already_processed(st: EventDrivenCrowdedPlacementRetryContractState, key: str) -> bool:
    return key in st.processed_event_set


def classify_wmt_result(
    *,
    wmt_receipt: dict[str, Any] | None,
    cell_tick_capped: bool = False,
) -> str:
    if cell_tick_capped:
        return RESULT_CELL_TICK_CAP
    if not isinstance(wmt_receipt, dict) or not wmt_receipt:
        return RESULT_NOT_INVOKED
    status = str(wmt_receipt.get("status") or "")
    if status == "COMMITTED":
        return RESULT_PLACED
    place = wmt_receipt.get("placement") or {}
    reason = str(wmt_receipt.get("rejection_reason") or "")
    pstat = str(place.get("status") or "").upper()
    if reason.startswith("UNSAFE_OBJECT_PLACEMENT") or pstat in {
        "REJECTED",
        "FAILED",
        "REJECTED_NO_VALID_CANDIDATE",
    }:
        return RESULT_REJECTED_CROWDED
    return RESULT_REJECTED_OTHER


def begin_placement_attempt_for_event(
    world: Any,
    config: Any,
    *,
    tick: int,
    cell_x: int,
    cell_y: int,
    body_id: Any,
    effector_id: Any,
    physical_source_kind: Any,
    attempt_seq: int,
) -> dict[str, Any]:
    """Gate: return allow_wmt False if this exertion event already attempted placement."""
    st = ensure_event_driven_crowded_placement_retry_contract_for_runtime(world, config)
    if st is None:
        return {
            "contract_active": False,
            "allow_wmt": True,
            "deduplicated": False,
            "exertion_event_id": None,
            "dedup_key": None,
            "retry_event_id": None,
        }
    eid = make_exertion_event_id(
        tick=tick,
        cell_x=cell_x,
        cell_y=cell_y,
        body_id=body_id,
        effector_id=effector_id,
        physical_source_kind=physical_source_kind,
        attempt_seq=attempt_seq,
    )
    key = make_dedup_key(exertion_event_id=eid)
    st.counters["eligible_events"] = int(st.counters.get("eligible_events", 0)) + 1
    if already_processed(st, key):
        st.counters["deduplicated"] = int(st.counters.get("deduplicated", 0)) + 1
        st.retry_event_seq = int(st.retry_event_seq) + 1
        rid = f"retry-{int(st.retry_event_seq)}"
        return {
            "contract_active": True,
            "allow_wmt": False,
            "deduplicated": True,
            "exertion_event_id": eid,
            "dedup_key": key,
            "retry_event_id": rid,
            "result": RESULT_DEDUPLICATED,
        }
    _remember_key(st, key)
    st.counters["placement_attempts"] = int(st.counters.get("placement_attempts", 0)) + 1
    st.retry_event_seq = int(st.retry_event_seq) + 1
    rid = f"retry-{int(st.retry_event_seq)}"
    return {
        "contract_active": True,
        "allow_wmt": True,
        "deduplicated": False,
        "exertion_event_id": eid,
        "dedup_key": key,
        "retry_event_id": rid,
    }


def record_crowded_retry_step(
    world: Any,
    config: Any,
    *,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    st = ensure_event_driven_crowded_placement_retry_contract_for_runtime(world, config)
    if st is None:
        return dict(receipt)
    result = str(receipt.get("result") or "")
    if result == RESULT_PLACED:
        st.counters["placed"] = int(st.counters.get("placed", 0)) + 1
    elif result == RESULT_REJECTED_CROWDED:
        st.counters["rejected_crowded"] = int(st.counters.get("rejected_crowded", 0)) + 1
    elif result == RESULT_REJECTED_OTHER:
        st.counters["rejected_other"] = int(st.counters.get("rejected_other", 0)) + 1
    elif result == RESULT_DEDUPLICATED:
        pass  # counted at begin
    elif result == RESULT_CELL_TICK_CAP:
        st.counters["cell_tick_cap"] = int(st.counters.get("cell_tick_cap", 0)) + 1
    payload = {
        "receipt_kind": RECEIPT_KIND,
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "dedup_key_version": DEDUP_KEY_VERSION,
        "placement_candidate_count": PLACEMENT_CANDIDATE_COUNT,
        "placement_policy_ref": PLACEMENT_POLICY_REF,
        "missing_far_sw_offset": list(MISSING_FAR_SW_OFFSET),
        "conflict_geometry_ref": CONFLICT_GEOMETRY_REF,
        "retry_trigger": RETRY_TRIGGER,
        "max_retries_per_event": MAX_RETRIES_PER_EVENT,
        **RESEARCHER_FLAGS,
        **dict(receipt),
    }
    st.last_step = dict(payload)
    st.history.append(dict(payload))
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    world.last_crowded_placement_retry = dict(payload)
    return dict(payload)


def candidate_summary_from_placement(placement: dict[str, Any] | None) -> dict[str, Any]:
    """Bounded K=16 summary from DTIP placement receipt (no physics change)."""
    if not isinstance(placement, dict):
        return {"candidate_count": PLACEMENT_CANDIDATE_COUNT, "reason_counts": {}}
    trials = placement.get("candidate_trials") or placement.get("candidates") or []
    reason_counts: dict[str, int] = {}
    if isinstance(trials, list):
        for t in trials[:PLACEMENT_CANDIDATE_COUNT]:
            if not isinstance(t, dict):
                continue
            r = str(t.get("status") or t.get("reason") or "UNKNOWN")
            reason_counts[r] = int(reason_counts.get(r, 0)) + 1
    blockers = placement.get("blocker_ids") or placement.get("blockers") or []
    if not isinstance(blockers, list):
        blockers = []
    return {
        "candidate_count": PLACEMENT_CANDIDATE_COUNT,
        "evaluated": len(trials) if isinstance(trials, list) else None,
        "reason_counts": reason_counts,
        "blocker_ids": [str(b) for b in blockers[:32]],
        "placement_status": placement.get("status"),
    }


def serialize_state(
    st: EventDrivenCrowdedPlacementRetryContractState | None,
) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "last_step": dict(st.last_step) if st.last_step else {},
        "history": list(st.history[-int(st.config.history_limit) :]),
        "processed_event_keys": list(st.processed_event_keys[-int(st.config.dedup_limit) :]),
        "retry_event_seq": int(st.retry_event_seq),
        "counters": {k: int(v) for k, v in st.counters.items()},
        "banner": BANNER,
        **RESEARCHER_FLAGS,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> EventDrivenCrowdedPlacementRetryContractState | None:
    if not event_driven_crowded_placement_retry_contract_is_active(config):
        world.event_driven_crowded_placement_retry_contract_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_event_driven_crowded_placement_retry_contract_for_runtime(world, config)
    cfg = EventDrivenCrowdedPlacementRetryContractConfig.from_dict(data.get("config") or {})
    cfg.enabled = True
    validate_config(cfg)
    st = EventDrivenCrowdedPlacementRetryContractState(config=cfg)
    st.last_step = dict(data.get("last_step") or {})
    hist = data.get("history") or []
    if isinstance(hist, list):
        st.history = [dict(h) for h in hist if isinstance(h, dict)]
    keys = data.get("processed_event_keys") or []
    if isinstance(keys, list):
        st.processed_event_keys = [str(k) for k in keys][-int(cfg.dedup_limit) :]
        st.processed_event_set = set(st.processed_event_keys)
    st.retry_event_seq = int(data.get("retry_event_seq", 0) or 0)
    ctr = data.get("counters") or {}
    if isinstance(ctr, dict):
        for k in st.counters:
            if k in ctr:
                st.counters[k] = int(ctr[k])
    world.event_driven_crowded_placement_retry_contract_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Event-driven crowded placement retry contract",
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "researcher_only": True,
        "agent_accessible": False,
        "arch_stage": "BETA4_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT",
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    last = dict(st.last_step) if st.last_step else {}
    blockers_moved = _derived_blockers_moved_since_last(world, last)
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "counters": {k: int(v) for k, v in st.counters.items()},
        "last_step": last,
        "retry_event_seq": int(st.retry_event_seq),
        "processed_event_count": len(st.processed_event_keys),
        "placement_candidate_count": PLACEMENT_CANDIDATE_COUNT,
        "missing_far_sw_offset": list(MISSING_FAR_SW_OFFSET),
        "blockers_moved_since_last_attempt_derived": blockers_moved,
        "blockers_moved_label": "researcher-only/derived from current poses; does not trigger retry",
        "retry_trigger": RETRY_TRIGGER,
        "dedup_key_version": DEDUP_KEY_VERSION,
        **RESEARCHER_FLAGS,
    }


def _derived_blockers_moved_since_last(
    world: Any, last: dict[str, Any]
) -> dict[str, Any]:
    """Researcher-only: compare last receipt blocker IDs' current poses vs recorded.

    Never invokes placement/retry. Missing pose history ⇒ unknown.
    """
    summary = last.get("candidate_summary") or {}
    ids = list(summary.get("blocker_ids") or [])
    recorded = last.get("blocker_poses") or {}
    if not ids:
        return {"known": False, "any_moved": False, "moved_ids": []}
    objs = {
        str(getattr(o, "object_id", "") or getattr(o, "id", "")): o
        for o in (getattr(world, "resource_objects", None) or [])
    }
    moved: list[str] = []
    for bid in ids:
        oid = str(bid)
        obj = objs.get(oid)
        if obj is None:
            moved.append(oid)
            continue
        prev = recorded.get(oid) if isinstance(recorded, dict) else None
        if not isinstance(prev, (list, tuple)) or len(prev) < 2:
            continue
        cur = (float(getattr(obj, "x", 0.0)), float(getattr(obj, "y", 0.0)))
        if abs(cur[0] - float(prev[0])) > 1e-6 or abs(cur[1] - float(prev[1])) > 1e-6:
            moved.append(oid)
    return {
        "known": bool(recorded),
        "any_moved": bool(moved),
        "moved_ids": moved[:32],
    }
