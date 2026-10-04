"""Derived multi-content spatial index. Not an authoritative world."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.planet.topology import wrap_coord

MECHANISM_ID = "multi_content_spatial_index"
SCHEMA_VERSION = "MULTI_CONTENT_SPATIAL_INDEX_V1"
KIND_BODY = "BODY"
KIND_RESOURCE_OBJECT = "RESOURCE_OBJECT"
KIND_SURFACE_DEPOSIT = "SURFACE_DEPOSIT"
EVENT_UPDATED = "SPATIAL_CONTENTS_INDEX_UPDATED"
EVENT_REBUILT = "SPATIAL_CONTENTS_INDEX_REBUILT"
EVENT_MISMATCH = "SPATIAL_CONTENTS_INDEX_MISMATCH"
HISTORY_LIMIT = 16
OPTICAL_CELL_MARGIN = 9

_ORDER = {
    KIND_BODY: 0,
    KIND_RESOURCE_OBJECT: 1,
    KIND_SURFACE_DEPOSIT: 2,
}


@dataclass
class MultiContentSpatialIndexConfig:
    enabled: bool = False
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": bool(self.enabled), "schema_version": self.schema_version}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MultiContentSpatialIndexConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        return cls(
            enabled=bool(data.get("enabled", False)),
            schema_version=str(data.get("schema_version") or SCHEMA_VERSION),
        )


@dataclass(frozen=True)
class SpatialEntityRef:
    entity_kind: str
    entity_id: str
    cell_x: int
    cell_y: int
    state_revision: int
    pose_tick: int

    def sort_key(self) -> tuple[int, str]:
        return (_ORDER.get(self.entity_kind, 9), self.entity_id)

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_kind": self.entity_kind,
            "entity_id": self.entity_id,
            "cell_x": int(self.cell_x),
            "cell_y": int(self.cell_y),
            "state_revision": int(self.state_revision),
            "pose_tick": int(self.pose_tick),
        }


@dataclass
class SpatialContentsIndex:
    schema_version: str = SCHEMA_VERSION
    generation: int = 0
    built_tick: int = 0
    dirty: bool = False
    last_reason: str = ""
    mismatch_count: int = 0
    pose_epoch: int = 0
    by_cell: dict[tuple[int, int], list[SpatialEntityRef]] = field(default_factory=dict)
    by_entity: dict[tuple[str, str], SpatialEntityRef] = field(default_factory=dict)
    records: dict[tuple[str, str], Any] = field(default_factory=dict)


def multi_content_spatial_index_is_active(config: Any) -> bool:
    if str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "multi_content_spatial_index", None)
    return bool(getattr(cfg, "enabled", False))


def set_multi_content_spatial_index(config: Any, enabled: bool) -> None:
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "multi_content_spatial_index", None)
    if cur is None:
        config.multi_content_spatial_index = MultiContentSpatialIndexConfig(enabled=on)
    else:
        cur.enabled = on


def world_cell(x: float, y: float, *, width: int, height: int) -> tuple[int, int]:
    """World (x, y) → wrapped floor cell. x is width, y is height."""
    width = int(width)
    height = int(height)
    cell_x = int(wrap_coord(int(math.floor(float(x))), width))
    cell_y = int(wrap_coord(int(math.floor(float(y))), height))
    return cell_x, cell_y


def _shape(world: Any) -> tuple[int, int]:
    grid = getattr(world, "T", None)
    if grid is None:
        return 32, 32
    return int(grid.shape[0]), int(grid.shape[1])


def _index(world: Any) -> SpatialContentsIndex | None:
    raw = getattr(world, "spatial_contents", None)
    return raw if isinstance(raw, SpatialContentsIndex) else None


def _ensure(world: Any) -> SpatialContentsIndex:
    current = _index(world)
    if current is None:
        current = SpatialContentsIndex()
        world.spatial_contents = current
    return current


def checksum_of(index: SpatialContentsIndex | None) -> str:
    rows = []
    if index is not None:
        for ref in sorted(index.by_entity.values(), key=lambda item: item.sort_key()):
            rows.append(
                f"{ref.entity_kind}|{ref.entity_id}|{int(ref.cell_x)}|{int(ref.cell_y)}|{int(ref.state_revision)}"
            )
    digest = hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()
    return digest[:16]


def contents_at_cell(world: Any, cell_x: int, cell_y: int) -> list[SpatialEntityRef]:
    index = _index(world)
    if index is None:
        return []
    found = list(index.by_cell.get((int(cell_x), int(cell_y)), []))
    found.sort(key=lambda item: item.sort_key())
    return found


def contents_in_wrapped_cells(world: Any, cells: list[tuple[int, int]] | tuple[tuple[int, int], ...]) -> list[SpatialEntityRef]:
    seen: dict[tuple[str, str], SpatialEntityRef] = {}
    for cell_x, cell_y in cells:
        for ref in contents_at_cell(world, int(cell_x), int(cell_y)):
            seen[(ref.entity_kind, ref.entity_id)] = ref
    return sorted(seen.values(), key=lambda item: item.sort_key())


def refs_for_entity(world: Any, entity_kind: str, entity_id: str) -> SpatialEntityRef | None:
    index = _index(world)
    if index is None:
        return None
    return index.by_entity.get((str(entity_kind), str(entity_id)))


def _remember_event(world: Any, event: dict[str, Any]) -> None:
    history = list(getattr(world, "spatial_index_history", None) or [])
    history.append(event)
    world.spatial_index_history = history[-HISTORY_LIMIT:]
    world.last_spatial_index_event = event
    world.spatial_index_checksum = checksum_of(_index(world))
    world.spatial_index_generation = int(getattr(_index(world), "generation", 0) or 0)
    world.spatial_index_schema = SCHEMA_VERSION


def _event(
    world: Any,
    *,
    kind: str,
    tick: int,
    reason: str,
    affected: list[dict[str, Any]],
    mismatch_count: int = 0,
) -> dict[str, Any]:
    index = _index(world)
    return {
        "event": kind,
        "tick": int(tick),
        "generation": int(getattr(index, "generation", 0) or 0),
        "reason": str(reason),
        "affected_entity_refs": affected[-8:],
        "operation": kind,
        "checksum": checksum_of(index),
        "mismatch_count": int(mismatch_count),
        "authoritative_source": "world.resource_objects,surface_material_deposits,body_slots",
        "researcher_only": True,
        "agent_accessible": False,
        "physical_effects_applied": False,
        "schema_version": SCHEMA_VERSION,
    }


def _place(index: SpatialContentsIndex, ref: SpatialEntityRef, record: Any) -> bool:
    """Insert or replace. Returns True when cell membership changes."""
    key = (ref.entity_kind, ref.entity_id)
    previous = index.by_entity.get(key)
    membership = previous is None or (previous.cell_x, previous.cell_y) != (ref.cell_x, ref.cell_y)
    if previous is not None:
        bucket = index.by_cell.get((previous.cell_x, previous.cell_y), [])
        index.by_cell[(previous.cell_x, previous.cell_y)] = [
            item for item in bucket if (item.entity_kind, item.entity_id) != key
        ]
        if not index.by_cell[(previous.cell_x, previous.cell_y)]:
            del index.by_cell[(previous.cell_x, previous.cell_y)]
    bucket = index.by_cell.setdefault((ref.cell_x, ref.cell_y), [])
    bucket = [item for item in bucket if (item.entity_kind, item.entity_id) != key]
    bucket.append(ref)
    index.by_cell[(ref.cell_x, ref.cell_y)] = bucket
    index.by_entity[key] = ref
    if record is not None:
        index.records[key] = record
    return membership


def upsert_ref(world: Any, ref: SpatialEntityRef, record: Any = None, *, tick: int = 0, reason: str = "upsert") -> None:
    index = _ensure(world)
    changed = _place(index, ref, record)
    if changed:
        index.generation += 1
        index.pose_epoch += 1
        _remember_event(world, _event(world, kind=EVENT_UPDATED, tick=tick, reason=reason, affected=[ref.as_dict()]))
    else:
        index.pose_epoch += 1


def remove_ref(world: Any, entity_kind: str, entity_id: str, *, tick: int = 0, reason: str = "remove") -> None:
    index = _index(world)
    if index is None:
        return
    key = (str(entity_kind), str(entity_id))
    previous = index.by_entity.pop(key, None)
    index.records.pop(key, None)
    if previous is None:
        return
    bucket = index.by_cell.get((previous.cell_x, previous.cell_y), [])
    index.by_cell[(previous.cell_x, previous.cell_y)] = [
        item for item in bucket if (item.entity_kind, item.entity_id) != key
    ]
    if not index.by_cell[(previous.cell_x, previous.cell_y)]:
        del index.by_cell[(previous.cell_x, previous.cell_y)]
    index.generation += 1
    index.pose_epoch += 1
    _remember_event(world, _event(world, kind=EVENT_UPDATED, tick=tick, reason=reason, affected=[previous.as_dict()]))


def move_ref(
    world: Any,
    entity_kind: str,
    entity_id: str,
    cell_x: int,
    cell_y: int,
    *,
    state_revision: int = 0,
    pose_tick: int = 0,
    record: Any = None,
    reason: str = "move",
) -> None:
    upsert_ref(
        world,
        SpatialEntityRef(entity_kind, entity_id, int(cell_x), int(cell_y), int(state_revision), int(pose_tick)),
        record,
        tick=pose_tick,
        reason=reason,
    )


def _object_ref(obj: Any, *, width: int, height: int, tick: int) -> SpatialEntityRef:
    cell_x, cell_y = world_cell(float(obj.x), float(obj.y), width=width, height=height)
    return SpatialEntityRef(
        KIND_RESOURCE_OBJECT,
        str(obj.object_id),
        cell_x,
        cell_y,
        int(getattr(obj, "material_revision", 0) or 0),
        int(tick),
    )


def _deposit_ref(deposit: Any, *, tick: int) -> SpatialEntityRef:
    return SpatialEntityRef(
        KIND_SURFACE_DEPOSIT,
        str(deposit.deposit_id),
        int(deposit.cell_x),
        int(deposit.cell_y),
        int(getattr(deposit, "material_revision", 0) or 0),
        int(tick),
    )


def _body_ref(body_id: str, body: Any, *, width: int, height: int, tick: int) -> SpatialEntityRef:
    cell_x, cell_y = world_cell(float(body.x), float(body.y), width=width, height=height)
    return SpatialEntityRef(KIND_BODY, str(body_id), cell_x, cell_y, 0, int(tick))


def body_refs_for_runtime(runtime: Any) -> list[tuple[str, Any]]:
    slots = getattr(runtime, "slots", None)
    if slots:
        from mechanistic_mind.ui.psy_observer_web.undercover_identity import slot_agent_body_ids

        experimenter = getattr(runtime, "experimenter_slot", None)
        return [
            (slot_agent_body_ids(i, experimenter_slot=experimenter)[1], slot.body)
            for i, slot in enumerate(slots)
            if getattr(slot, "body", None) is not None
        ]
    body = getattr(runtime, "body", None)
    if body is None:
        return []
    technical = str(getattr(runtime, "technical_id", "agent_0") or "agent_0")
    if technical == "undercover":
        from mechanistic_mind.ui.psy_observer_web.undercover_identity import undercover_body_id

        return [(undercover_body_id(0), body)]
    if technical.startswith("agent_"):
        return [(f"body-{technical.split('_')[-1]}", body)]
    return [("body-0", body)]


def _expected(world: Any, bodies: list[tuple[str, Any]] | None, tick: int) -> list[tuple[SpatialEntityRef, Any]]:
    height, width = _shape(world)
    rows: list[tuple[SpatialEntityRef, Any]] = []
    for obj in list(getattr(world, "resource_objects", None) or []):
        rows.append((_object_ref(obj, width=width, height=height, tick=tick), obj))
    deposits = getattr(world, "surface_material_deposits", None) or {}
    for deposit in deposits.values():
        rows.append((_deposit_ref(deposit, tick=tick), deposit))
    for body_id, body in bodies or []:
        if body is None:
            continue
        rows.append((_body_ref(body_id, body, width=width, height=height, tick=tick), body))
    return rows


def rebuild_from_world(
    world: Any,
    bodies: list[tuple[str, Any]] | None = None,
    *,
    tick: int = 0,
    reason: str = "rebuild",
    config: Any = None,
) -> SpatialContentsIndex | None:
    if config is not None and not multi_content_spatial_index_is_active(config):
        world.spatial_contents = None
        return None
    index = SpatialContentsIndex(built_tick=int(tick), last_reason=str(reason))
    world.spatial_contents = index
    affected = []
    for ref, record in _expected(world, bodies, tick):
        _place(index, ref, record)
        affected.append(ref.as_dict())
    index.generation = int(getattr(world, "spatial_index_generation", 0) or 0) + 1
    index.pose_epoch = int(getattr(world, "spatial_pose_epoch", 0) or 0) + 1
    index.dirty = False
    index.built_tick = int(tick)
    world.spatial_pose_epoch = index.pose_epoch
    _remember_event(world, _event(world, kind=EVENT_REBUILT, tick=tick, reason=reason, affected=affected))
    return index


def rebuild_after_authoritative_entity_change(
    world: Any,
    bodies: list[tuple[str, Any]] | None,
    *,
    tick: int,
    config: Any,
    reason: str,
    generation_policy: str = "bump",
) -> SpatialContentsIndex | None:
    """Shared lifecycle seam: authoritative entity set finalized → derived spatial index once.

    Used by TwoAgentRuntime construction, restore, experimenter spawn/despawn. Rebuilds from
    authoritative state only. No scientific tick, no physics, no cognition, no receipts beyond the
    existing derived spatial_index_history metadata.

    generation_policy:
      - "bump": normal rebuild_from_world (+1 derived generation). Spawn/despawn.
      - "preserve": keep existing spatial_index_generation (restore / single-agent restore parity).
      - "fresh": start derived generation at 1 (construction after shared world is complete).
    """
    if not multi_content_spatial_index_is_active(config):
        return None
    policy = str(generation_policy or "bump")
    saved_generation = int(getattr(world, "spatial_index_generation", 0) or 0)
    if policy == "fresh":
        world.spatial_index_generation = 0
    index = rebuild_from_world(world, bodies, tick=int(tick), reason=str(reason), config=config)
    if policy == "preserve" and saved_generation and index is not None:
        index.generation = saved_generation
        world.spatial_index_generation = saved_generation
    return index


def rebuild_after_restore(
    world: Any,
    bodies: list[tuple[str, Any]] | None,
    *,
    tick: int,
    config: Any,
) -> SpatialContentsIndex | None:
    """Explicit restore lifecycle point for a shared world (TwoAgentRuntime.restore).

    Called once, after every slot, body pose, ResourceObject, holder attachment and the experimenter
    slot are bound. Builds the derived index from authoritative state only (same rebuild and the same
    saved-generation policy as PhysicalSystemRuntime.restore). No tick, no physics, no receipts;
    the checksum is recomputed from the rebuilt index (existing policy)."""
    return rebuild_after_authoritative_entity_change(
        world,
        bodies,
        tick=int(tick),
        config=config,
        reason="restore",
        generation_policy="preserve",
    )


def spatial_index_consistency(world: Any, bodies: list[tuple[str, Any]] | None) -> dict[str, Any]:
    """Researcher/debug-only, strictly read-only: index vs authoritative world (no events, no repair,
    no mutation). Not agent-visible. Meant for tests and diagnostics, not for every production tick."""
    rows = _expected(world, bodies, 0)
    expected = {(ref.entity_kind, ref.entity_id): ref for ref, _record in rows}
    probe = SpatialContentsIndex()
    for ref, _record in rows:
        _place(probe, ref, None)
    index = _index(world)
    actual = {} if index is None else dict(index.by_entity)
    counts: dict[tuple[str, str], int] = {}
    if index is not None:
        for bucket in index.by_cell.values():
            for ref in bucket:
                key = (ref.entity_kind, ref.entity_id)
                counts[key] = counts.get(key, 0) + 1
    by_cell_keys = set(counts)
    missing = sorted(set(expected) - set(actual))
    stale = sorted((set(actual) | by_cell_keys) - set(expected))
    duplicates = sorted(key for key, n in counts.items() if n > 1)
    wrong_cells = sorted(
        key for key, ref in expected.items()
        if key in actual and (actual[key].cell_x, actual[key].cell_y) != (ref.cell_x, ref.cell_y)
    )
    wrong_revisions = sorted(
        key for key, ref in expected.items()
        if key in actual and int(actual[key].state_revision) != int(ref.state_revision)
    )
    unindexed_in_cells = sorted(key for key in actual if key not in by_cell_keys)
    consistent = index is not None and not (
        missing or stale or duplicates or wrong_cells or wrong_revisions or unindexed_in_cells
    )
    return {
        "spatial_index_consistent_with_authoritative_state": bool(consistent),
        "index_present": index is not None,
        "missing_refs": [list(k) for k in missing],
        "duplicate_refs": [list(k) for k in duplicates],
        "stale_refs": [list(k) for k in stale],
        "wrong_cell_refs": [list(k) for k in wrong_cells],
        "wrong_revision_refs": [list(k) for k in wrong_revisions],
        "by_entity_without_cell_ref": [list(k) for k in unindexed_in_cells],
        "checksum": checksum_of(index),
        "expected_checksum": checksum_of(probe),
        "researcher_only": True,
        "agent_accessible": False,
    }


def reconcile_contents(
    world: Any,
    bodies: list[tuple[str, Any]] | None = None,
    *,
    tick: int = 0,
    reason: str = "sync",
    config: Any = None,
    include_bodies: bool = True,
    include_materials: bool = True,
) -> None:
    if config is not None and not multi_content_spatial_index_is_active(config):
        return
    if _index(world) is None or bool(getattr(_index(world), "dirty", False)):
        try:
            rebuild_from_world(
                world,
                bodies if include_bodies else body_refs_for_runtime(world),
                tick=tick,
                reason=reason,
                config=config,
            )
        except Exception:
            world.spatial_index_dirty = True
            if _index(world) is not None:
                _index(world).dirty = True
        return
    try:
        index = _ensure(world)
        expected = _expected(world, bodies if include_bodies else [], tick)
        if not include_materials:
            expected = [row for row in expected if row[0].entity_kind == KIND_BODY]
        if not include_bodies:
            expected = [row for row in expected if row[0].entity_kind != KIND_BODY]
            for key, ref in list(index.by_entity.items()):
                if ref.entity_kind == KIND_BODY:
                    expected.append((ref, index.records.get(key)))
        if not include_materials:
            for key, ref in list(index.by_entity.items()):
                if ref.entity_kind != KIND_BODY:
                    expected.append((ref, index.records.get(key)))
        wanted = {(ref.entity_kind, ref.entity_id) for ref, _record in expected}
        changed = False
        pose_changed = False
        affected: list[dict[str, Any]] = []
        for ref, record in expected:
            key = (ref.entity_kind, ref.entity_id)
            previous = index.by_entity.get(key)
            if previous is None or (previous.cell_x, previous.cell_y) != (ref.cell_x, ref.cell_y):
                _place(index, ref, record)
                changed = True
                affected.append(ref.as_dict())
            elif previous.state_revision != ref.state_revision:
                _place(index, ref, record)
                pose_changed = True
            else:
                index.records[key] = record
        for key, previous in list(index.by_entity.items()):
            if key in wanted:
                continue
            if not include_bodies and previous.entity_kind == KIND_BODY:
                continue
            if not include_materials and previous.entity_kind != KIND_BODY:
                continue
            remove_bucket = index.by_cell.get((previous.cell_x, previous.cell_y), [])
            index.by_cell[(previous.cell_x, previous.cell_y)] = [
                item for item in remove_bucket if (item.entity_kind, item.entity_id) != key
            ]
            if not index.by_cell.get((previous.cell_x, previous.cell_y)):
                index.by_cell.pop((previous.cell_x, previous.cell_y), None)
            index.by_entity.pop(key, None)
            index.records.pop(key, None)
            changed = True
            affected.append(previous.as_dict())
        if changed:
            index.generation += 1
            index.pose_epoch += 1
            index.built_tick = int(tick)
            index.last_reason = str(reason)
            index.dirty = False
            world.spatial_pose_epoch = index.pose_epoch
            _remember_event(world, _event(world, kind=EVENT_UPDATED, tick=tick, reason=reason, affected=affected))
        elif pose_changed:
            index.pose_epoch += 1
            world.spatial_pose_epoch = index.pose_epoch
            world.spatial_index_checksum = checksum_of(index)
    except Exception:
        index = _index(world)
        if index is not None:
            index.dirty = True
        world.spatial_index_dirty = True
        rebuild_from_world(world, bodies, tick=tick, reason="dirty_rebuild", config=config)


def validate_against_world(
    world: Any,
    bodies: list[tuple[str, Any]] | None = None,
    *,
    tick: int = 0,
    repair: bool = False,
) -> dict[str, Any]:
    """Verification does not rewrite the index. repair=True rebuilds it."""
    expected_rows = _expected(world, bodies, tick)
    expected = {(ref.entity_kind, ref.entity_id): ref for ref, _record in expected_rows}
    index = _index(world)
    actual = {} if index is None else dict(index.by_entity)
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    wrong_cells = []
    wrong_revisions = []
    duplicates = []
    seen_cells: dict[tuple[str, str], int] = {}
    if index is not None:
        for bucket in index.by_cell.values():
            for ref in bucket:
                key = (ref.entity_kind, ref.entity_id)
                seen_cells[key] = seen_cells.get(key, 0) + 1
        duplicates = sorted(key for key, count in seen_cells.items() if count > 1)
    for key, ref in expected.items():
        found = actual.get(key)
        if found is None:
            continue
        if (found.cell_x, found.cell_y) != (ref.cell_x, ref.cell_y):
            wrong_cells.append(key)
        if int(found.state_revision) != int(ref.state_revision):
            wrong_revisions.append(key)
    report = {
        "missing": [list(key) for key in missing],
        "extra": [list(key) for key in extra],
        "duplicates": [list(key) for key in duplicates],
        "wrong_cells": [list(key) for key in wrong_cells],
        "wrong_revisions": [list(key) for key in wrong_revisions],
        "mismatch_count": len(missing) + len(extra) + len(duplicates) + len(wrong_cells) + len(wrong_revisions),
        "checksum": checksum_of(index),
        "expected_checksum": "",
    }
    if report["mismatch_count"] and index is not None:
        index.mismatch_count = int(report["mismatch_count"])
        _remember_event(
            world,
            _event(
                world,
                kind=EVENT_MISMATCH,
                tick=tick,
                reason="validate",
                affected=[],
                mismatch_count=report["mismatch_count"],
            ),
        )
    if repair:
        rebuild_from_world(world, bodies, tick=tick, reason="explicit_rebuild")
        report["repaired"] = True
        report["checksum_after_repair"] = checksum_of(_index(world))
    else:
        report["repaired"] = False
    return report


def resource_objects_for_cells(world: Any, cells: list[tuple[int, int]]) -> list[Any]:
    """Authoritative object records whose center cell is inside the wrapped neighborhood."""
    index = _index(world)
    if index is None or index.dirty:
        return []
    height, width = _shape(world)
    expanded: set[tuple[int, int]] = set()
    for cell_x, cell_y in cells:
        for dy in range(-OPTICAL_CELL_MARGIN, OPTICAL_CELL_MARGIN + 1):
            for dx in range(-OPTICAL_CELL_MARGIN, OPTICAL_CELL_MARGIN + 1):
                expanded.add((
                    int(wrap_coord(int(cell_x) + dx, width)),
                    int(wrap_coord(int(cell_y) + dy, height)),
                ))
    found = []
    seen: set[str] = set()
    for cell in expanded:
        for ref in contents_at_cell(world, cell[0], cell[1]):
            if ref.entity_kind != KIND_RESOURCE_OBJECT or ref.entity_id in seen:
                continue
            record = index.records.get((ref.entity_kind, ref.entity_id))
            if record is None:
                continue
            seen.add(ref.entity_id)
            found.append(record)
    found.sort(key=lambda obj: str(getattr(obj, "object_id", "")))
    return found


def occupied_cell_summary(world: Any) -> dict[str, Any]:
    index = _index(world)
    if index is None:
        return {
            "occupied_cell_count": 0,
            "multi_content_cell_count": 0,
            "maximum_refs_per_cell": 0,
            "counts_by_kind": {},
        }
    counts = {KIND_BODY: 0, KIND_RESOURCE_OBJECT: 0, KIND_SURFACE_DEPOSIT: 0}
    multi = 0
    maximum = 0
    for bucket in index.by_cell.values():
        maximum = max(maximum, len(bucket))
        if len(bucket) > 1:
            multi += 1
    for ref in index.by_entity.values():
        counts[ref.entity_kind] = counts.get(ref.entity_kind, 0) + 1
    return {
        "occupied_cell_count": len(index.by_cell),
        "multi_content_cell_count": multi,
        "maximum_refs_per_cell": maximum,
        "counts_by_kind": counts,
    }


def spatial_index_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "multi_content_spatial_index.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "description": (
            "Derived multi-content cell index. researcher-only. not agent-accessible. "
            "co-location is not collision. no vertical ordering."
        ),
    }
