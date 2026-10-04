"""Acanthostega-only single physical manipulator + GRASP/RELEASE.

Heading authority: body.theta (not articulated head, not camera).
Forward unit is (cos(theta), sin(theta)); theta=0 faces +x (MOVE:E).

Mass of a held object does not load locomotion in this slice.
Holding cost is zero. Command cost is a small bounded reservoir debit.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Any

from mechanistic_mind.planet.topology import toroidal_delta, wrap_coord
from mechanistic_mind.physical_system.resource_objects import (
    PHYSICAL_STATE_FREE_STATIC,
    ResourceObject,
    clip_interaction_radius,
    clip_optical_radius,
    ensure_resource_object_state,
    objects_is_active,
)

SINGLE_PHYSICAL_MANIPULATOR = "single_physical_manipulator"
PHYSICAL_GRASP_RELEASE = "physical_grasp_release"
BILATERAL_PHYSICAL_MANIPULATORS = "bilateral_physical_manipulators"
BILATERAL_GRASP_RELEASE = "bilateral_grasp_release"
BILATERAL_BRING_TOGETHER = "bilateral_bring_together"
MANIPULATOR_ID = "manipulator_0"
MANIP_LEFT = "LEFT"
MANIP_RIGHT = "RIGHT"
BILATERAL_IDS = (MANIP_LEFT, MANIP_RIGHT)
MANIP_NONE = "NONE"
MANIP_GRASP = "GRASP"
MANIP_RELEASE = "RELEASE"
MANIPULATOR_ACTIONS = (MANIP_GRASP, MANIP_RELEASE)
BILATERAL_ACTION_TOKENS = (
    "LEFT_GRASP",
    "LEFT_RELEASE",
    "RIGHT_GRASP",
    "RIGHT_RELEASE",
)
PAIR_NONE = "NONE"
PAIR_BRING_TOGETHER = "BRING_TOGETHER"
PAIR_SEPARATE = "SEPARATE"
PAIR_COMBINE = "COMBINE"
PAIR_ACTIONS = (PAIR_BRING_TOGETHER, PAIR_SEPARATE, PAIR_COMBINE)
PAIR_ACTION_TOKENS = PAIR_ACTIONS
PAIR_OPEN = "OPEN"
PAIR_CLOSING = "CLOSING"
PAIR_CONTACT = "CONTACT"
PAIR_OPENING = "OPENING"
PHYSICAL_STATE_HELD = "HELD"
EVENT_HELD_OBJECT_CONTACT_BEGIN = "HELD_OBJECT_CONTACT_BEGIN"
EVENT_HELD_OBJECT_CONTACT_END = "HELD_OBJECT_CONTACT_END"

# Surface of object intersects effector disk when
# toroidal_distance(effector, object) <= grasp_radius + optical_radius.
CANONICAL_FORWARD_OFFSET = 0.55
CANONICAL_LATERAL_OFFSET = 0.42
CANONICAL_GRASP_RADIUS = 0.40
COMMAND_WORK_COST = 0.01
HOLDING_WORK_COST = 0.0
# LEFT = +lateral, RIGHT = -lateral. At theta=0, forward=+x, LEFT=+y, RIGHT=-y.
CANONICAL_OPEN_APERTURE = 2.0 * CANONICAL_LATERAL_OFFSET
# Empty-hands floor: well below 2×interaction_radius so dual-held contact is reachable.
CANONICAL_MIN_EMPTY_APERTURE = 0.08
CANONICAL_PAIR_ACTUATION_RATE = 0.06
CANONICAL_PAIR_WORK_PER_UNIT = 0.02


@dataclass
class SinglePhysicalManipulatorConfig:
    """Fresh default OFF. Missing snapshot key → no effector."""

    enabled: bool = False
    manipulator_id: str = MANIPULATOR_ID
    forward_offset: float = CANONICAL_FORWARD_OFFSET
    grasp_radius: float = CANONICAL_GRASP_RADIUS
    command_work_cost: float = COMMAND_WORK_COST
    holding_work_cost: float = HOLDING_WORK_COST

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SinglePhysicalManipulatorConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        return cls(**payload)


@dataclass
class PhysicalGraspReleaseConfig:
    """Fresh default OFF. Missing snapshot key → no GRASP/RELEASE channel."""

    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PhysicalGraspReleaseConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        return cls(**payload)


@dataclass
class BilateralPhysicalManipulatorsConfig:
    """Fresh default OFF. Missing snapshot key → no second effector."""

    enabled: bool = False
    forward_offset: float = CANONICAL_FORWARD_OFFSET
    lateral_offset: float = CANONICAL_LATERAL_OFFSET
    grasp_radius: float = CANONICAL_GRASP_RADIUS
    command_work_cost: float = COMMAND_WORK_COST
    holding_work_cost: float = HOLDING_WORK_COST

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BilateralPhysicalManipulatorsConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        return cls(**payload)


@dataclass
class BilateralGraspReleaseConfig:
    """Fresh default OFF. Missing snapshot key → no LEFT/RIGHT GRASP/RELEASE."""

    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BilateralGraspReleaseConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        return cls(**payload)


@dataclass
class BilateralBringTogetherConfig:
    """Fresh default OFF. Missing snapshot key → no pair aperture channel."""

    enabled: bool = False
    open_aperture: float = CANONICAL_OPEN_APERTURE
    min_empty_aperture: float = CANONICAL_MIN_EMPTY_APERTURE
    actuation_rate: float = CANONICAL_PAIR_ACTUATION_RATE
    work_per_unit_aperture: float = CANONICAL_PAIR_WORK_PER_UNIT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BilateralBringTogetherConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        return cls(**payload)


def manipulator_is_active(config: Any) -> bool:
    if config is None:
        return False
    if str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    if not objects_is_active(config):
        return False
    cfg = getattr(config, "single_physical_manipulator", None)
    return bool(getattr(cfg, "enabled", False)) and not bilateral_manipulator_is_active(config)


def bilateral_manipulator_is_active(config: Any) -> bool:
    if config is None:
        return False
    if str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    if not objects_is_active(config):
        return False
    cfg = getattr(config, "bilateral_physical_manipulators", None)
    return bool(getattr(cfg, "enabled", False))


def world_manipulators_active(config: Any) -> bool:
    return manipulator_is_active(config) or bilateral_manipulator_is_active(config)


def grasp_release_is_active(config: Any) -> bool:
    if not manipulator_is_active(config):
        return False
    cfg = getattr(config, "physical_grasp_release", None)
    return bool(getattr(cfg, "enabled", False))


def bilateral_grasp_release_is_active(config: Any) -> bool:
    if not bilateral_manipulator_is_active(config):
        return False
    cfg = getattr(config, "bilateral_grasp_release", None)
    return bool(getattr(cfg, "enabled", False))


def set_single_physical_manipulator(config: Any, enabled: bool) -> None:
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "single_physical_manipulator", None)
    if cur is None:
        config.single_physical_manipulator = SinglePhysicalManipulatorConfig(enabled=on)
    else:
        cur.enabled = on
    if on:
        set_bilateral_physical_manipulators(config, False)
    if not on:
        set_physical_grasp_release(config, False)


def set_physical_grasp_release(config: Any, enabled: bool) -> None:
    on = (
        bool(enabled)
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
        and manipulator_is_active(config)
    )
    cur = getattr(config, "physical_grasp_release", None)
    if cur is None:
        config.physical_grasp_release = PhysicalGraspReleaseConfig(enabled=on)
    else:
        cur.enabled = on


def set_bilateral_physical_manipulators(config: Any, enabled: bool) -> None:
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "bilateral_physical_manipulators", None)
    if cur is None:
        config.bilateral_physical_manipulators = BilateralPhysicalManipulatorsConfig(enabled=on)
    else:
        cur.enabled = on
    if on:
        cur_s = getattr(config, "single_physical_manipulator", None)
        if cur_s is None:
            config.single_physical_manipulator = SinglePhysicalManipulatorConfig(enabled=False)
        else:
            cur_s.enabled = False
        set_physical_grasp_release(config, False)
    if not on:
        set_bilateral_grasp_release(config, False)


def set_bilateral_grasp_release(config: Any, enabled: bool) -> None:
    on = (
        bool(enabled)
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
        and bilateral_manipulator_is_active(config)
    )
    cur = getattr(config, "bilateral_grasp_release", None)
    if cur is None:
        config.bilateral_grasp_release = BilateralGraspReleaseConfig(enabled=on)
    else:
        cur.enabled = on
    if not on:
        set_bilateral_bring_together(config, False)


def set_bilateral_bring_together(config: Any, enabled: bool) -> None:
    on = (
        bool(enabled)
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
        and bilateral_grasp_release_is_active(config)
    )
    cur = getattr(config, "bilateral_bring_together", None)
    if cur is None:
        config.bilateral_bring_together = BilateralBringTogetherConfig(enabled=on)
    else:
        cur.enabled = on


def bring_together_is_active(config: Any) -> bool:
    if not bilateral_grasp_release_is_active(config):
        return False
    cfg = getattr(config, "bilateral_bring_together", None)
    return bool(getattr(cfg, "enabled", False))


def normalize_manipulator_action(raw: Any) -> str:
    s = str(raw or MANIP_NONE).strip().upper()
    if s in MANIPULATOR_ACTIONS:
        return s
    return MANIP_NONE


def parse_bilateral_token(raw: Any) -> tuple[str, str] | None:
    s = str(raw or "").strip().upper()
    if s == "LEFT_GRASP":
        return MANIP_LEFT, MANIP_GRASP
    if s == "LEFT_RELEASE":
        return MANIP_LEFT, MANIP_RELEASE
    if s == "RIGHT_GRASP":
        return MANIP_RIGHT, MANIP_GRASP
    if s == "RIGHT_RELEASE":
        return MANIP_RIGHT, MANIP_RELEASE
    return None


def normalize_pair_action(raw: Any) -> str:
    s = str(raw or PAIR_NONE).strip().upper()
    if s in PAIR_ACTIONS:
        return s
    return PAIR_NONE


def pair_command_from_motor(mo: dict[str, Any] | None) -> str:
    mo = mo if isinstance(mo, dict) else {}
    cmd = normalize_pair_action(mo.get("manipulator_pair"))
    if cmd != PAIR_NONE:
        return cmd
    for key in ("legacy_token", "display"):
        cmd = normalize_pair_action(mo.get(key))
        if cmd != PAIR_NONE:
            return cmd
    return PAIR_NONE


def open_pair_aperture(config: Any) -> float:
    pcfg = getattr(config, "bilateral_bring_together", None)
    if pcfg is not None:
        try:
            ap = float(getattr(pcfg, "open_aperture", CANONICAL_OPEN_APERTURE) or CANONICAL_OPEN_APERTURE)
            if math.isfinite(ap) and ap > 0.0:
                return ap
        except (TypeError, ValueError):
            pass
    bcfg = getattr(config, "bilateral_physical_manipulators", None) or BilateralPhysicalManipulatorsConfig()
    return 2.0 * float(getattr(bcfg, "lateral_offset", CANONICAL_LATERAL_OFFSET) or CANONICAL_LATERAL_OFFSET)


def ensure_pair_runtime(runtime: Any, config: Any) -> None:
    if runtime is None:
        return
    open_ap = open_pair_aperture(config)
    if getattr(runtime, "pair_aperture", None) is None:
        runtime.pair_aperture = float(open_ap)
    if not getattr(runtime, "pair_state", None):
        runtime.pair_state = PAIR_OPEN
    if getattr(runtime, "pair_contact", None) is None:
        runtime.pair_contact = False


def dual_held_objects(world: Any, body_id: str) -> tuple[ResourceObject | None, ResourceObject | None]:
    left = held_object_for_holder(world, body_id, MANIP_LEFT)
    right = held_object_for_holder(world, body_id, MANIP_RIGHT)
    if left is None or right is None:
        return None, None
    if str(left.object_id) == str(right.object_id):
        return None, None
    return left, right


def object_center_distance(a: ResourceObject, b: ResourceObject, *, width: int, height: int) -> float:
    return float(
        math.hypot(
            toroidal_delta(float(a.x), float(b.x), int(width)),
            toroidal_delta(float(a.y), float(b.y), int(height)),
        )
    )


def interaction_surface_contact(a: ResourceObject, b: ResourceObject, *, width: int, height: int) -> bool:
    ra = clip_interaction_radius(getattr(a, "interaction_radius", 0.0))
    rb = clip_interaction_radius(getattr(b, "interaction_radius", 0.0))
    return object_center_distance(a, b, width=width, height=height) <= (ra + rb + 1e-12)


def pair_min_aperture(world: Any, body_id: str, config: Any) -> float:
    pcfg = getattr(config, "bilateral_bring_together", None) or BilateralBringTogetherConfig()
    empty = float(getattr(pcfg, "min_empty_aperture", CANONICAL_MIN_EMPTY_APERTURE) or CANONICAL_MIN_EMPTY_APERTURE)
    left, right = dual_held_objects(world, body_id)
    if left is None or right is None:
        return empty
    needed = clip_interaction_radius(left.interaction_radius) + clip_interaction_radius(right.interaction_radius)
    return max(empty, float(needed))


def _grasp_radius(config: Any) -> float:
    if bilateral_manipulator_is_active(config):
        cfg = getattr(config, "bilateral_physical_manipulators", None) or BilateralPhysicalManipulatorsConfig()
        return float(getattr(cfg, "grasp_radius", CANONICAL_GRASP_RADIUS) or 0.0)
    cfg = getattr(config, "single_physical_manipulator", None) or SinglePhysicalManipulatorConfig()
    return float(getattr(cfg, "grasp_radius", CANONICAL_GRASP_RADIUS) or 0.0)


def effector_world_xy(
    body: Any,
    *,
    width: int,
    height: int,
    config: Any,
    manipulator_id: str | None = None,
    runtime: Any = None,
) -> tuple[float, float]:
    """Effector pose from body pose + body.theta.

    Single: forward offset only (manipulator_0).
    Bilateral LEFT/RIGHT: forward ± lateral. LEFT = +lateral, RIGHT = −lateral.
    When bilateral_bring_together is ON, lateral = aperture/2 from runtime pair state.
    Bilateral Grasp (mechanism OFF) keeps fixed lateral_offset.
    """
    theta = float(getattr(body, "theta", 0.0) or 0.0)
    bx = float(getattr(body, "x", 0.0) or 0.0)
    by = float(getattr(body, "y", 0.0) or 0.0)
    fwd_x, fwd_y = math.cos(theta), math.sin(theta)
    lat_x, lat_y = -math.sin(theta), math.cos(theta)
    mid = str(manipulator_id or "")
    if mid in BILATERAL_IDS or bilateral_manipulator_is_active(config):
        cfg = getattr(config, "bilateral_physical_manipulators", None) or BilateralPhysicalManipulatorsConfig()
        offset = float(getattr(cfg, "forward_offset", CANONICAL_FORWARD_OFFSET) or 0.0)
        lateral = float(getattr(cfg, "lateral_offset", CANONICAL_LATERAL_OFFSET) or 0.0)
        if bring_together_is_active(config) and runtime is not None:
            ensure_pair_runtime(runtime, config)
            lateral = 0.5 * float(runtime.pair_aperture)
        sign = 1.0 if mid == MANIP_LEFT else (-1.0 if mid == MANIP_RIGHT else 0.0)
        if mid not in BILATERAL_IDS:
            sign = 0.0
        x = bx + offset * fwd_x + sign * lateral * lat_x
        y = by + offset * fwd_y + sign * lateral * lat_y
        return float(wrap_coord(x, int(width))), float(wrap_coord(y, int(height)))
    cfg = getattr(config, "single_physical_manipulator", None) or SinglePhysicalManipulatorConfig()
    offset = float(getattr(cfg, "forward_offset", CANONICAL_FORWARD_OFFSET) or 0.0)
    x = bx + offset * fwd_x
    y = by + offset * fwd_y
    return float(wrap_coord(x, int(width))), float(wrap_coord(y, int(height)))


def object_reach_distance(
    obj: ResourceObject,
    ex: float,
    ey: float,
    *,
    width: int,
    height: int,
) -> float:
    return float(math.hypot(toroidal_delta(ex, float(obj.x), int(width)), toroidal_delta(ey, float(obj.y), int(height))))


def object_surface_in_reach(
    obj: ResourceObject,
    ex: float,
    ey: float,
    *,
    width: int,
    height: int,
    config: Any,
    body: Any | None = None,
) -> bool:
    grasp_r = _grasp_radius(config)
    obj_r = clip_optical_radius(getattr(obj, "optical_radius", 0.0))
    if object_reach_distance(obj, ex, ey, width=width, height=height) > (grasp_r + obj_r + 1e-12):
        return False
    # Phase C: XY + vertical reach; endpoint only; no vertical sweep.
    if body is not None:
        from .flat_ground_gravity import grasp_vertical_reachable
        if not grasp_vertical_reachable(body, obj, config):
            return False
    return True


def held_object_for_holder(world: Any, holder_body_id: str, manipulator_id: str = MANIPULATOR_ID) -> ResourceObject | None:
    hid = str(holder_body_id or "")
    mid = str(manipulator_id or MANIPULATOR_ID)
    found: list[ResourceObject] = []
    for obj in ensure_resource_object_state(world):
        if str(obj.physical_state) != PHYSICAL_STATE_HELD:
            continue
        if str(obj.holder_body_id or "") == hid and str(obj.manipulator_id or "") == mid:
            found.append(obj)
    if not found:
        return None
    found.sort(key=lambda o: str(o.object_id))
    return found[0]


def occupancy_scalar(world: Any, holder_body_id: str, manipulator_id: str = MANIPULATOR_ID) -> float:
    return 1.0 if held_object_for_holder(world, holder_body_id, manipulator_id) is not None else 0.0


def cognition_grip_fragments(
    *,
    world: Any,
    holder_body_id: str,
    enabled: bool,
    manipulator_id: str = MANIPULATOR_ID,
    config: Any = None,
    runtime: Any = None,
) -> dict[str, float]:
    """Anonymous occupancy only. Empty when manipulator OFF. No object identity."""
    if not enabled:
        return {}
    if config is not None and bilateral_manipulator_is_active(config):
        out = {
            "prop_grip_left": occupancy_scalar(world, holder_body_id, MANIP_LEFT),
            "prop_grip_right": occupancy_scalar(world, holder_body_id, MANIP_RIGHT),
        }
        if bring_together_is_active(config):
            ensure_pair_runtime(runtime, config)
            open_ap = open_pair_aperture(config)
            ap = float(getattr(runtime, "pair_aperture", open_ap) or open_ap) if runtime is not None else open_ap
            norm = 0.0 if open_ap <= 1e-12 else max(0.0, min(1.0, ap / open_ap))
            contact = 1.0 if bool(getattr(runtime, "pair_contact", False)) else 0.0
            out["prop_pair_aperture"] = float(norm)
            out["prop_pair_contact"] = float(contact)
        return out
    return {"prop_grip_0": occupancy_scalar(world, holder_body_id, manipulator_id)}


def select_nearest_free_object(
    objects: list[ResourceObject],
    ex: float,
    ey: float,
    *,
    width: int,
    height: int,
    config: Any,
    body: Any | None = None,
) -> ResourceObject | None:
    """World mechanic: nearest FREE_STATIC in reach; tie-break by object_id. No agent object_id."""
    eligible: list[tuple[float, str, ResourceObject]] = []
    for obj in objects:
        if str(obj.physical_state) != PHYSICAL_STATE_FREE_STATIC:
            continue
        if not object_surface_in_reach(obj, ex, ey, width=width, height=height, config=config, body=body):
            continue
        dist = object_reach_distance(obj, ex, ey, width=width, height=height)
        eligible.append((dist, str(obj.object_id), obj))
    if not eligible:
        return None
    eligible.sort(key=lambda row: (row[0], row[1]))
    return eligible[0][2]



def _maybe_note_grasp_effector_work(world, config, *, body_id, hand_id, object_id, tick):
    try:
        from .effector_work_and_held_load_inertia_accounting import (
            effector_work_held_load_is_active,
            note_grasp_attachment,
        )
    except Exception:
        return None
    if not effector_work_held_load_is_active(config):
        return None
    return note_grasp_attachment(
        world, config, body_id=body_id, hand_id=hand_id, object_id=object_id, tick=tick
    )

def _debit_command_work(body: Any, config: Any, *, bilateral: bool = False) -> float:
    if bilateral:
        cfg = getattr(config, "bilateral_physical_manipulators", None) or BilateralPhysicalManipulatorsConfig()
    else:
        cfg = getattr(config, "single_physical_manipulator", None) or SinglePhysicalManipulatorConfig()
    cost = float(getattr(cfg, "command_work_cost", COMMAND_WORK_COST) or 0.0)
    if cost <= 0.0:
        return 0.0
    work_on = bool(getattr(getattr(config, "discrete_action_work", None), "enabled", False))
    if not work_on:
        return 0.0
    w0 = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)
    debit = min(w0, cost)
    body.mechanical_work_reservoir = max(0.0, w0 - debit)
    return float(debit)


def _debit_pair_work(body: Any, config: Any, magnitude: float) -> float:
    pcfg = getattr(config, "bilateral_bring_together", None) or BilateralBringTogetherConfig()
    unit = float(getattr(pcfg, "work_per_unit_aperture", CANONICAL_PAIR_WORK_PER_UNIT) or 0.0)
    cost = unit * abs(float(magnitude))
    if cost <= 1e-15:
        return 0.0
    work_on = bool(getattr(getattr(config, "discrete_action_work", None), "enabled", False))
    if not work_on:
        return 0.0
    w0 = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)
    debit = min(w0, cost)
    body.mechanical_work_reservoir = max(0.0, w0 - debit)
    return float(debit)


def sanitize_attachments(world: Any, valid_holder_ids: set[str]) -> None:
    objs = ensure_resource_object_state(world)
    objs.sort(key=lambda o: str(o.object_id))
    seen_holders: set[tuple[str, str]] = set()
    seen_objects: set[str] = set()
    for obj in objs:
        if str(obj.physical_state) != PHYSICAL_STATE_HELD:
            obj.holder_body_id = None
            obj.manipulator_id = None
            continue
        hid = str(obj.holder_body_id or "")
        mid = str(obj.manipulator_id or MANIPULATOR_ID)
        oid = str(obj.object_id)
        key = (hid, mid)
        if hid not in valid_holder_ids or key in seen_holders or oid in seen_objects:
            obj.physical_state = PHYSICAL_STATE_FREE_STATIC
            obj.holder_body_id = None
            obj.manipulator_id = None
            continue
        seen_holders.add(key)
        seen_objects.add(oid)


def update_held_kinematics(world: Any, holders: list[dict[str, Any]]) -> None:
    """Snap HELD object centers to current effector. No independent object velocity."""
    if not holders:
        return
    t = getattr(world, "T", None)
    if t is None:
        return
    h, w = int(t.shape[0]), int(t.shape[1])
    by_id = {str(row["body_id"]): row for row in holders}
    for obj in ensure_resource_object_state(world):
        if str(obj.physical_state) != PHYSICAL_STATE_HELD:
            continue
        row = by_id.get(str(obj.holder_body_id or ""))
        if row is None:
            obj.physical_state = PHYSICAL_STATE_FREE_STATIC
            obj.holder_body_id = None
            obj.manipulator_id = None
            continue
        ex, ey = effector_world_xy(
            row["body"],
            width=w,
            height=h,
            config=row["config"],
            manipulator_id=str(obj.manipulator_id or MANIPULATOR_ID),
            runtime=row.get("runtime"),
        )
        obj.x = ex
        obj.y = ey
        obj.vx = 0.0
        obj.vy = 0.0


def apply_grasp_release_for_holder(
    *,
    world: Any,
    body: Any,
    config: Any,
    body_id: str,
    action: str,
    tick: int,
) -> dict[str, Any]:
    """Authoritative world attachment. Visibility is not used."""
    cmd = normalize_manipulator_action(action)
    t = getattr(world, "T", None)
    h = int(t.shape[0]) if t is not None else 32
    w = int(t.shape[1]) if t is not None else 32
    mid = str(getattr(getattr(config, "single_physical_manipulator", None), "manipulator_id", None) or MANIPULATOR_ID)
    ex, ey = effector_world_xy(body, width=w, height=h, config=config)
    receipt: dict[str, Any] = {
        "event": None,
        "manipulator_action": cmd,
        "body_id": str(body_id),
        "manipulator_id": mid,
        "effector_xy": [ex, ey],
        "object_id": None,
        "work_debit": 0.0,
        "researcher_only_object_id": None,
        "heading_authority": "body.theta",
        "mass_load_applied": False,
        "holding_work_cost": HOLDING_WORK_COST,
    }
    if cmd == MANIP_NONE or not grasp_release_is_active(config):
        receipt["event"] = "MANIPULATOR_IDLE"
        return receipt
    debit = _debit_command_work(body, config)
    receipt["work_debit"] = debit
    held = held_object_for_holder(world, body_id, mid)
    if cmd == MANIP_RELEASE:
        if held is None:
            receipt["event"] = "RELEASE_NO_OBJECT"
            return receipt
        held.physical_state = PHYSICAL_STATE_FREE_STATIC
        held.holder_body_id = None
        held.manipulator_id = None
        held.vx = 0.0
        held.vy = 0.0
        held.x = float(wrap_coord(float(held.x), w))
        held.y = float(wrap_coord(float(held.y), h))
        from .flat_ground_gravity import apply_release_vertical
        apply_release_vertical(
            held,
            body,
            config,
            world=world,
            tick=int(tick),
            holder_body_id=str(body_id),
            manipulator_id=str(mid),
        )
        receipt["event"] = "RELEASE_SUCCEEDED"
        receipt["object_id"] = str(held.object_id)
        receipt["researcher_only_object_id"] = str(held.object_id)
        receipt["release_xy"] = [float(held.x), float(held.y)]
        receipt["release_z"] = float(getattr(held, "z", 0.0) or 0.0)
        receipt["release_vz"] = float(getattr(held, "vz", 0.0) or 0.0)
        return receipt
    # GRASP
    receipt["event"] = "GRASP_ATTEMPT"
    if held is not None:
        receipt["event"] = "GRASP_FAILED_OCCUPIED"
        receipt["object_id"] = str(held.object_id)
        receipt["researcher_only_object_id"] = str(held.object_id)
        return receipt
    objs = ensure_resource_object_state(world)
    target = select_nearest_free_object(objs, ex, ey, width=w, height=h, config=config, body=body)
    if target is None:
        occupied_in_reach = [
            obj
            for obj in objs
            if str(obj.physical_state) == PHYSICAL_STATE_HELD
            and object_surface_in_reach(obj, ex, ey, width=w, height=h, config=config, body=body)
        ]
        if occupied_in_reach:
            occupied_in_reach.sort(key=lambda o: str(o.object_id))
            other = occupied_in_reach[0]
            receipt["event"] = "GRASP_FAILED_OCCUPIED"
            receipt["object_id"] = str(other.object_id)
            receipt["researcher_only_object_id"] = str(other.object_id)
            return receipt
        receipt["event"] = "GRASP_FAILED_OUT_OF_REACH"
        return receipt
    target.physical_state = PHYSICAL_STATE_HELD
    target.holder_body_id = str(body_id)
    target.manipulator_id = mid
    target.x = ex
    target.y = ey
    target.vx = 0.0
    target.vy = 0.0
    receipt["event"] = "GRASP_SUCCEEDED"
    receipt["object_id"] = str(target.object_id)
    receipt["researcher_only_object_id"] = str(target.object_id)
    receipt["tick"] = int(tick)
    ew = _maybe_note_grasp_effector_work(
        world, config, body_id=body_id, hand_id=mid, object_id=str(target.object_id), tick=tick
    )
    if ew is not None:
        receipt["effector_held_load_work"] = ew
    return receipt


def _empty_hand_receipt(*, body_id: str, mid: str, cmd: str, ex: float, ey: float) -> dict[str, Any]:
    return {
        "event": "MANIPULATOR_IDLE",
        "manipulator_action": cmd,
        "body_id": str(body_id),
        "manipulator_id": mid,
        "effector_xy": [ex, ey],
        "object_id": None,
        "work_debit": 0.0,
        "researcher_only_object_id": None,
        "heading_authority": "body.theta",
        "mass_load_applied": False,
        "holding_work_cost": HOLDING_WORK_COST,
        "arbitration": "surface_distance,object_id,manipulator_id",
        "inter_agent_contention": "technical_id_ascending_agent_0_first",
    }


def _motor_hand_commands(mo: dict[str, Any] | None) -> dict[str, str]:
    mo = mo if isinstance(mo, dict) else {}
    left = normalize_manipulator_action(mo.get("manipulator_left"))
    right = normalize_manipulator_action(mo.get("manipulator_right"))
    for key in ("legacy_token", "manipulator", "display"):
        parsed = parse_bilateral_token(mo.get(key))
        if parsed is None:
            continue
        mid, cmd = parsed
        if mid == MANIP_LEFT and left == MANIP_NONE:
            left = cmd
        if mid == MANIP_RIGHT and right == MANIP_NONE:
            right = cmd
    return {MANIP_LEFT: left, MANIP_RIGHT: right}


def apply_bilateral_grasp_release_for_holder(
    *,
    world: Any,
    body: Any,
    config: Any,
    body_id: str,
    commands: dict[str, str],
    tick: int,
    runtime: Any = None,
) -> dict[str, Any]:
    """Same-body LEFT/RIGHT resolve. Visibility unused.

    Same-body GRASP arbitration: candidate pairs (hand, free object in that
    hand's reach) sorted by (surface distance, object_id, manipulator_id).
    Greedy assignment without reusing an object or a hand. Equal distance
    therefore prefers LEFT over RIGHT only as a lexicographic last key.
    """
    t = getattr(world, "T", None)
    h = int(t.shape[0]) if t is not None else 32
    w = int(t.shape[1]) if t is not None else 32
    poses = {
        mid: effector_world_xy(
            body, width=w, height=h, config=config, manipulator_id=mid, runtime=runtime,
        )
        for mid in BILATERAL_IDS
    }
    hands: dict[str, dict[str, Any]] = {}
    total_debit = 0.0
    cmds = {mid: normalize_manipulator_action(commands.get(mid)) for mid in BILATERAL_IDS}
    for mid in BILATERAL_IDS:
        cmd = cmds[mid]
        if cmd not in MANIPULATOR_ACTIONS:
            cmd = MANIP_NONE
            cmds[mid] = cmd
        rec = _empty_hand_receipt(body_id=body_id, mid=mid, cmd=cmd, ex=poses[mid][0], ey=poses[mid][1])
        rec["occupancy_before"] = occupancy_scalar(world, body_id, mid)
        if cmd != MANIP_NONE and bilateral_grasp_release_is_active(config):
            debit = _debit_command_work(body, config, bilateral=True)
            rec["work_debit"] = debit
            total_debit += debit
        hands[mid] = rec
    if not bilateral_grasp_release_is_active(config):
        return {
            "event": "BILATERAL_IDLE",
            "hands": hands,
            "work_debit": total_debit,
            "body_id": str(body_id),
        }
    # RELEASE first, LEFT then RIGHT (independent; order only for receipts).
    for mid in BILATERAL_IDS:
        rec = hands[mid]
        if cmds[mid] != MANIP_RELEASE:
            continue
        held = held_object_for_holder(world, body_id, mid)
        if held is None:
            rec["event"] = "RELEASE_NO_OBJECT"
            continue
        held.physical_state = PHYSICAL_STATE_FREE_STATIC
        held.holder_body_id = None
        held.manipulator_id = None
        held.vx = 0.0
        held.vy = 0.0
        held.x = float(wrap_coord(float(held.x), w))
        held.y = float(wrap_coord(float(held.y), h))
        from .flat_ground_gravity import apply_release_vertical
        apply_release_vertical(
            held,
            body,
            config,
            world=world,
            tick=int(tick),
            holder_body_id=str(body_id),
            manipulator_id=str(mid),
        )
        rec["event"] = "RELEASE_SUCCEEDED"
        rec["object_id"] = str(held.object_id)
        rec["researcher_only_object_id"] = str(held.object_id)
        rec["release_xy"] = [float(held.x), float(held.y)]
        rec["release_z"] = float(getattr(held, "z", 0.0) or 0.0)
        rec["release_vz"] = float(getattr(held, "vz", 0.0) or 0.0)
    grasp_hands = [mid for mid in BILATERAL_IDS if cmds[mid] == MANIP_GRASP]
    occupied_skip: set[str] = set()
    for mid in grasp_hands:
        rec = hands[mid]
        rec["event"] = "GRASP_ATTEMPT"
        held = held_object_for_holder(world, body_id, mid)
        if held is not None:
            rec["event"] = "GRASP_FAILED_OCCUPIED"
            rec["object_id"] = str(held.object_id)
            rec["researcher_only_object_id"] = str(held.object_id)
            occupied_skip.add(mid)
    empty_grasp = [mid for mid in grasp_hands if mid not in occupied_skip]
    objs = ensure_resource_object_state(world)
    pairs: list[tuple[float, str, str, ResourceObject]] = []
    for mid in empty_grasp:
        ex, ey = poses[mid]
        for obj in objs:
            if str(obj.physical_state) != PHYSICAL_STATE_FREE_STATIC:
                continue
            if not object_surface_in_reach(obj, ex, ey, width=w, height=h, config=config, body=body):
                continue
            dist = object_reach_distance(obj, ex, ey, width=w, height=h)
            pairs.append((dist, str(obj.object_id), mid, obj))
    pairs.sort(key=lambda row: (row[0], row[1], row[2]))
    claimed_obj: set[str] = set()
    claimed_hand: set[str] = set()
    assigned: dict[str, ResourceObject] = {}
    for _dist, oid, mid, obj in pairs:
        if oid in claimed_obj or mid in claimed_hand:
            continue
        assigned[mid] = obj
        claimed_obj.add(oid)
        claimed_hand.add(mid)
    for mid in empty_grasp:
        rec = hands[mid]
        if mid in assigned:
            target = assigned[mid]
            if str(target.physical_state) != PHYSICAL_STATE_FREE_STATIC:
                rec["event"] = "GRASP_FAILED_OCCUPIED"
                rec["object_id"] = str(target.object_id)
                rec["researcher_only_object_id"] = str(target.object_id)
                continue
            ex, ey = poses[mid]
            target.physical_state = PHYSICAL_STATE_HELD
            target.holder_body_id = str(body_id)
            target.manipulator_id = mid
            target.x = ex
            target.y = ey
            target.vx = 0.0
            target.vy = 0.0
            rec["event"] = "GRASP_SUCCEEDED"
            rec["object_id"] = str(target.object_id)
            rec["researcher_only_object_id"] = str(target.object_id)
            rec["tick"] = int(tick)
            ew = _maybe_note_grasp_effector_work(
                world, config, body_id=body_id, hand_id=mid, object_id=str(target.object_id), tick=tick
            )
            if ew is not None:
                rec["effector_held_load_work"] = ew
            continue
        ex, ey = poses[mid]
        occupied_in_reach = [
            obj
            for obj in objs
            if str(obj.physical_state) == PHYSICAL_STATE_HELD
            and object_surface_in_reach(obj, ex, ey, width=w, height=h, config=config, body=body)
        ]
        if occupied_in_reach:
            occupied_in_reach.sort(key=lambda o: str(o.object_id))
            other = occupied_in_reach[0]
            rec["event"] = "GRASP_FAILED_OCCUPIED"
            rec["object_id"] = str(other.object_id)
            rec["researcher_only_object_id"] = str(other.object_id)
        else:
            rec["event"] = "GRASP_FAILED_OUT_OF_REACH"
    for mid in BILATERAL_IDS:
        hands[mid]["occupancy_after"] = occupancy_scalar(world, body_id, mid)
    return {
        "event": "BILATERAL_RESOLVED",
        "hands": hands,
        "work_debit": total_debit,
        "body_id": str(body_id),
        "occupancy_after": {mid: occupancy_scalar(world, body_id, mid) for mid in BILATERAL_IDS},
        "arbitration": "surface_distance,object_id,manipulator_id",
        "inter_agent_contention": "technical_id_ascending_agent_0_first",
    }


def apply_pair_actuation(
    *,
    world: Any,
    body: Any,
    config: Any,
    body_id: str,
    runtime: Any,
    command: str,
    tick: int,
) -> dict[str, Any]:
    """Change aperture with a bounded per-tick rate. Does not teleport.

    NONE holds the current aperture (no auto-return). Objects are not mixed.
    Same-tick dual GRASP + BRING_TOGETHER: GRASP resolves first, then this
    actuation runs in the same tick.
    """
    t = getattr(world, "T", None)
    h = int(t.shape[0]) if t is not None else 32
    w = int(t.shape[1]) if t is not None else 32
    cmd = normalize_pair_action(command)
    if cmd == PAIR_COMBINE:
        from .material_composition import material_composition_merge_is_active
        if not material_composition_merge_is_active(config):
            cmd = PAIR_NONE
    ensure_pair_runtime(runtime, config)
    open_ap = open_pair_aperture(config)
    min_ap = pair_min_aperture(world, body_id, config)
    left, right = dual_held_objects(world, body_id)
    ap_before = float(runtime.pair_aperture)
    state_before = str(runtime.pair_state or PAIR_OPEN)
    contact_before = bool(runtime.pair_contact)
    dist_before = None
    if left is not None and right is not None:
        dist_before = object_center_distance(left, right, width=w, height=h)
    if not bring_together_is_active(config):
        return {
            "event": "PAIR_IDLE",
            "pair_command": PAIR_NONE,
            "pair_state_before": state_before,
            "pair_state_after": state_before,
            "aperture_before": ap_before,
            "aperture_after": ap_before,
            "delta_aperture": 0.0,
            "left_held": left is not None,
            "right_held": right is not None,
            "surface_distance_before": dist_before,
            "surface_distance_after": dist_before,
            "contact_before": contact_before,
            "contact_after": contact_before,
            "work_debit": 0.0,
            "outcome": "PAIR_UNAVAILABLE",
            "body_id": str(body_id),
            "tick": int(tick),
        }
    pcfg = getattr(config, "bilateral_bring_together", None) or BilateralBringTogetherConfig()
    rate = max(0.0, float(getattr(pcfg, "actuation_rate", CANONICAL_PAIR_ACTUATION_RATE) or 0.0))
    ap_desired = ap_before
    if cmd == PAIR_BRING_TOGETHER:
        ap_desired = max(min_ap, ap_before - min(rate, max(0.0, ap_before - min_ap)))
    elif cmd == PAIR_SEPARATE:
        ap_desired = min(open_ap, ap_before + min(rate, max(0.0, open_ap - ap_before)))
    delta_desired = float(ap_desired - ap_before)

    from .effector_work_and_held_load_inertia_accounting import (
        effector_work_held_load_is_active,
        admit_relative_hand_aperture,
    )

    effector_receipt = None
    if effector_work_held_load_is_active(config) and abs(delta_desired) > 1e-15:
        # NEW preset: KE admission for held-load relative hand work (no aperture proxy).
        effector_receipt = admit_relative_hand_aperture(
            world=world,
            body=body,
            config=config,
            body_id=body_id,
            runtime=runtime,
            desired_delta_aperture=delta_desired,
            aperture_before=ap_before,
            open_aperture=open_ap,
            min_aperture=min_ap,
            tick=tick,
        )
        ap_after = float(effector_receipt.get("aperture_after", ap_before))
        delta = float(effector_receipt.get("aperture_admitted_delta", 0.0))
        runtime.pair_aperture = float(ap_after)
        debit = float(effector_receipt.get("work_debit") or 0.0)
    else:
        ap_after = ap_desired
        delta = delta_desired
        runtime.pair_aperture = float(ap_after)
        debit = _debit_pair_work(body, config, abs(delta))
    out = {
        "event": "PAIR_ACTUATED",
        "pair_command": cmd,
        "pair_state_before": state_before,
        "pair_state_after": state_before,
        "aperture_before": ap_before,
        "aperture_after": ap_after,
        "aperture_desired": ap_desired,
        "delta_aperture": delta,
        "delta_aperture_desired": delta_desired,
        "left_held": left is not None,
        "right_held": right is not None,
        "left_object_id": str(left.object_id) if left is not None else None,
        "right_object_id": str(right.object_id) if right is not None else None,
        "surface_distance_before": dist_before,
        "surface_distance_after": dist_before,
        "contact_before": contact_before,
        "contact_after": contact_before,
        "work_debit": debit,
        "outcome": "PAIR_HOLD",
        "open_aperture": open_ap,
        "min_aperture": min_ap,
        "body_id": str(body_id),
        "tick": int(tick),
        "mixing": False,
        "same_tick_grasp_then_pair": True,
    }
    if effector_receipt is not None:
        out["effector_held_load_work"] = effector_receipt
        out["work_limited"] = bool(effector_receipt.get("work_limited"))
        out["work_unavailable"] = bool(effector_receipt.get("work_unavailable"))
        out["admission_scale"] = effector_receipt.get("admission_scale")
    return out


def evaluate_held_object_contact(
    *,
    world: Any,
    config: Any,
    body_id: str,
    runtime: Any,
    pair_receipt: dict[str, Any],
    tick: int,
) -> dict[str, Any]:
    t = getattr(world, "T", None)
    h = int(t.shape[0]) if t is not None else 32
    w = int(t.shape[1]) if t is not None else 32
    ensure_pair_runtime(runtime, config)
    open_ap = open_pair_aperture(config)
    min_ap = pair_min_aperture(world, body_id, config)
    left, right = dual_held_objects(world, body_id)
    contact_before = bool(pair_receipt.get("contact_before"))
    dist_after = None
    contact_after = False
    if left is not None and right is not None:
        dist_after = object_center_distance(left, right, width=w, height=h)
        contact_after = bool(bring_together_is_active(config) and interaction_surface_contact(left, right, width=w, height=h))
        if contact_after:
            from .flat_ground_gravity import vertical_overlap_at_endpoint, flat_ground_gravity_is_active
            if flat_ground_gravity_is_active(config) and not vertical_overlap_at_endpoint(
                left, right, kind_a="object", kind_b="object", config=config
            ):
                contact_after = False
                pair_receipt["vertical_separation_reason"] = "VERTICAL_SEPARATION"
    ap = float(runtime.pair_aperture)
    cmd = str(pair_receipt.get("pair_command") or PAIR_NONE)
    delta = float(pair_receipt.get("delta_aperture") or 0.0)
    if contact_after:
        state_after = PAIR_CONTACT
    elif ap >= open_ap - 1e-9:
        state_after = PAIR_OPEN
    elif cmd == PAIR_SEPARATE and delta > 1e-12:
        state_after = PAIR_OPENING
    elif cmd == PAIR_BRING_TOGETHER and delta < -1e-12:
        state_after = PAIR_CLOSING
    else:
        prev = str(runtime.pair_state or PAIR_OPEN)
        if prev == PAIR_CONTACT:
            state_after = PAIR_OPENING if ap > min_ap + 1e-9 else PAIR_CLOSING
        elif prev in {PAIR_CLOSING, PAIR_OPENING}:
            state_after = prev
        else:
            state_after = PAIR_CLOSING if ap < open_ap - 1e-9 else PAIR_OPEN
    runtime.pair_state = state_after
    runtime.pair_contact = bool(contact_after)
    outcome = "PAIR_HOLD"
    if not bring_together_is_active(config):
        outcome = "PAIR_UNAVAILABLE"
    elif contact_after and not contact_before:
        outcome = "OBJECT_CONTACT_BEGIN"
    elif contact_before and not contact_after:
        outcome = "OBJECT_CONTACT_END"
    elif cmd == PAIR_BRING_TOGETHER and left is None:
        if abs(delta) <= 1e-12 and ap <= min_ap + 1e-9:
            outcome = "PAIR_NO_DUAL_OBJECTS"
        elif abs(delta) <= 1e-12:
            outcome = "PAIR_NO_DUAL_OBJECTS"
        else:
            outcome = "PAIR_NO_DUAL_OBJECTS"
    elif cmd == PAIR_BRING_TOGETHER and abs(delta) <= 1e-12 and (contact_after or ap <= min_ap + 1e-9):
        outcome = "PAIR_AT_CONTACT_LIMIT"
    elif cmd == PAIR_SEPARATE and abs(delta) <= 1e-12 and ap >= open_ap - 1e-9:
        outcome = "PAIR_AT_OPEN_LIMIT"
    elif cmd == PAIR_BRING_TOGETHER and delta < -1e-12:
        outcome = "PAIR_CLOSING"
    elif cmd == PAIR_SEPARATE and delta > 1e-12:
        outcome = "PAIR_OPENING"
    pair_receipt["pair_state_after"] = state_after
    pair_receipt["surface_distance_after"] = dist_after
    pair_receipt["contact_after"] = contact_after
    pair_receipt["left_held"] = left is not None
    pair_receipt["right_held"] = right is not None
    pair_receipt["left_object_id"] = str(left.object_id) if left is not None else None
    pair_receipt["right_object_id"] = str(right.object_id) if right is not None else None
    pair_receipt["outcome"] = outcome
    pair_receipt["event"] = outcome
    if contact_after and not contact_before:
        runtime.structured_events.emit(
            EVENT_HELD_OBJECT_CONTACT_BEGIN,
            tick=int(tick),
            evidence={
                "body_id": str(body_id),
                "left_object_id": pair_receipt.get("left_object_id"),
                "right_object_id": pair_receipt.get("right_object_id"),
                "surface_distance": dist_after,
                "aperture": ap,
                "researcher_only": True,
                "mixing": False,
            },
        )
    if contact_before and not contact_after:
        runtime.structured_events.emit(
            EVENT_HELD_OBJECT_CONTACT_END,
            tick=int(tick),
            evidence={
                "body_id": str(body_id),
                "surface_distance": dist_after,
                "aperture": ap,
                "researcher_only": True,
                "mixing": False,
            },
        )
    return pair_receipt


def _emit_hand_events(rt: Any, rec: dict[str, Any], *, tick: int) -> None:
    ev = str(rec.get("event") or "")
    if ev in ("", "MANIPULATOR_IDLE", "BILATERAL_IDLE", "BILATERAL_RESOLVED"):
        return
    evidence = {
        k: rec.get(k)
        for k in (
            "manipulator_action",
            "body_id",
            "manipulator_id",
            "effector_xy",
            "researcher_only_object_id",
            "work_debit",
            "release_xy",
            "heading_authority",
            "mass_load_applied",
            "arbitration",
            "inter_agent_contention",
        )
    }
    rt.structured_events.emit(ev, tick=int(tick), evidence=evidence)
    if ev == "GRASP_SUCCEEDED":
        rt.structured_events.emit(
            "ATTACHMENT_UPDATED",
            tick=int(tick),
            evidence={**evidence, "physical_state": PHYSICAL_STATE_HELD},
        )


def resolve_shared_world_manipulators(runtimes: list[Any], world: Any, *, tick: int) -> list[dict[str, Any]]:
    """Deterministic world step.

    Order per tick: GRASP/RELEASE → pair actuation → held kinematics → contact.
    Same-tick dual GRASP + BRING_TOGETHER: closing acts this tick after grasp.

    Inter-agent contention: holders sorted by body_id ascending (agent_0 before
    agent_1). Independent of TwoAgentRuntime.process_order. Technical debt:
    agent_0 is systematically first. Same-body LEFT/RIGHT uses distance order,
    not left-first. Cross-agent held-object contact is not implemented.
    """
    holders = []
    valid: set[str] = set()
    for rt in runtimes:
        cfg = getattr(rt, "config", None)
        if not world_manipulators_active(cfg):
            continue
        bid = str(getattr(rt, "technical_id", None) or "agent_0")
        valid.add(bid)
        holders.append({"body_id": bid, "body": rt.body, "config": cfg, "runtime": rt})
    sanitize_attachments(world, valid)
    update_held_kinematics(world, holders)
    if holders:
        from .flat_ground_gravity import flat_ground_gravity_is_active as _fgg0, snap_held_vertical_from_holders as _snap0
        for _row in holders:
            if _fgg0(_row.get("config")):
                _snap0(world, holders, _row["config"])
                break
    # Acanthostega free-object kinematics (absent world state = no-op for every other preset):
    # one damp-then-drift step for FREE_MOVING objects, before this tick's GRASP/RELEASE.
    from .free_resource_object_kinematics import state_of as _fok_state

    _fok_on = _fok_state(world) is not None
    _fok_motion: list[dict[str, Any]] = []
    if _fok_on:
        from .free_resource_object_kinematics import integrate_free_objects

        _fok_motion = integrate_free_objects(world, int(tick))
    # Phase C: after horizontal FOK → gravity → support (shared world once). HELD skipped.
    from .flat_ground_gravity import (
        flat_ground_gravity_is_active as _fgg_on_fn,
        integrate_free_objects_vertical,
        snap_held_vertical_from_holders,
    )
    _fgg_on = False
    for row in holders:
        if _fgg_on_fn(row.get("config")):
            _fgg_on = True
            break
    if _fgg_on:
        # Use first active holder config (shared world / same preset).
        _fgg_cfg = next(r["config"] for r in holders if _fgg_on_fn(r.get("config")))
        integrate_free_objects_vertical(world, _fgg_cfg, int(tick))
        from .radius_aware_support_points import (
            radius_aware_support_points_is_active as _rasp_on,
            step_after_free_objects_vertical as _rasp_objs,
        )
        if _rasp_on(_fgg_cfg):
            _rasp_objs(world, _fgg_cfg, int(tick))
    held_at_tick_start = {
        str(row["body_id"]): (
            str(held.object_id) if (
                held := held_object_for_holder(world, str(row["body_id"]), MANIP_LEFT)
            ) is not None else None
        )
        for row in holders
    }
    receipts: list[dict[str, Any]] = []
    for row in sorted(holders, key=lambda r: str(r["body_id"])):
        rt = row["runtime"]
        cfg = row["config"]
        if bilateral_manipulator_is_active(cfg):
            mo = getattr(rt, "last_motor_output", None) or {}
            cmds = _motor_hand_commands(mo if isinstance(mo, dict) else {})
            rec = apply_bilateral_grasp_release_for_holder(
                world=world,
                body=row["body"],
                config=cfg,
                body_id=row["body_id"],
                commands=cmds,
                tick=tick,
                runtime=rt,
            )
            pair_cmd = pair_command_from_motor(mo if isinstance(mo, dict) else {})
            pair_rec = apply_pair_actuation(
                world=world,
                body=row["body"],
                config=cfg,
                body_id=row["body_id"],
                runtime=rt,
                command=pair_cmd,
                tick=tick,
            )
            rec["pair"] = pair_rec
            rt.last_manipulator_receipt = rec
            rt.last_pair_receipt = pair_rec
            for mid in BILATERAL_IDS:
                _emit_hand_events(rt, (rec.get("hands") or {}).get(mid) or {}, tick=tick)
            n_left = occupancy_scalar(world, row["body_id"], MANIP_LEFT)
            n_right = occupancy_scalar(world, row["body_id"], MANIP_RIGHT)
            rt.structured_events.emit(
                "MANIPULATOR_OCCUPANCY",
                tick=int(tick),
                evidence={
                    "body_id": row["body_id"],
                    "prop_grip_left": n_left,
                    "prop_grip_right": n_right,
                    "n_held": int(n_left + n_right),
                    "researcher_only": True,
                },
            )
            receipts.append(rec)
            continue
        action = MANIP_NONE
        if grasp_release_is_active(cfg):
            mo = getattr(rt, "last_motor_output", None) or {}
            action = normalize_manipulator_action(mo.get("manipulator") if isinstance(mo, dict) else MANIP_NONE)
            if action in BILATERAL_ACTION_TOKENS:
                action = MANIP_NONE
        rec = apply_grasp_release_for_holder(
            world=world,
            body=row["body"],
            config=cfg,
            body_id=row["body_id"],
            action=action,
            tick=tick,
        )
        rt.last_manipulator_receipt = rec
        _emit_hand_events(rt, rec, tick=tick)
        receipts.append(rec)
    _fok_releases: list[dict[str, Any]] = []
    if _fok_on:
        from .free_resource_object_kinematics import apply_release_transfer

        # Objects released at T receive the measured effector velocity; first integrated at T+1.
        _fok_releases = apply_release_transfer(world, holders, receipts, int(tick))
    update_held_kinematics(world, holders)
    if holders:
        from .flat_ground_gravity import flat_ground_gravity_is_active as _fgg1, snap_held_vertical_from_holders as _snap1
        for _row in holders:
            if _fgg1(_row.get("config")):
                _snap1(world, holders, _row["config"])
                break
    for row in sorted(holders, key=lambda r: str(r["body_id"])):
        rt = row["runtime"]
        cfg = row["config"]
        if not bring_together_is_active(cfg):
            continue
        pair_rec = getattr(rt, "last_pair_receipt", None)
        if not isinstance(pair_rec, dict):
            continue
        evaluate_held_object_contact(
            world=world,
            config=cfg,
            body_id=row["body_id"],
            runtime=rt,
            pair_receipt=pair_rec,
            tick=tick,
        )
        if str(pair_rec.get("pair_command") or PAIR_NONE) == PAIR_COMBINE:
            from .material_composition import merge_held_materials
            from .world_material_transaction import (
                commit_material_transaction,
                plan_combine,
                world_material_transactions_is_active,
            )

            left, right = dual_held_objects(world, row["body_id"])
            confirmed = bool(pair_rec.get("contact_before") and pair_rec.get("contact_after"))
            if world_material_transactions_is_active(cfg):
                planned = plan_combine(
                    world=world,
                    config=cfg,
                    body_id=row["body_id"],
                    left=left,
                    right=right,
                    confirmed_contact=confirmed,
                    tick=tick,
                    actor_agent_id=str(getattr(rt, "technical_id", None) or row["body_id"]),
                    selection_provenance=str(getattr(rt, "last_selected_action", None) or ""),
                    actor_body=row.get("body"),
                )
                committed = commit_material_transaction(world, planned)
                merge_rec = committed.get("legacy") or {
                    "event": "MATERIAL_COMBINE_REJECTED",
                    "outcome": "MERGE_REJECTED",
                    "command": "COMBINE",
                    "tick": int(tick),
                    "body_id": row["body_id"],
                    "transaction_status": (committed.get("receipt") or {}).get("status"),
                    "rejection_reason": (committed.get("receipt") or {}).get("rejection_reason"),
                    "researcher_only": True,
                    "semantic_effects": False,
                }
                rt.last_world_material_transaction = committed.get("receipt")
            else:
                merge_rec = merge_held_materials(
                    world=world,
                    config=cfg,
                    body_id=row["body_id"],
                    left=left,
                    right=right,
                    confirmed_contact=confirmed,
                    tick=tick,
                )
            rt.last_material_transformation_receipt = merge_rec
            pair_rec["material_transformation"] = merge_rec
            if merge_rec.get("outcome") == "MERGE_COMMITTED":
                rt.pair_contact = False
                rt.pair_state = PAIR_OPENING
                pair_rec["contact_after"] = False
                pair_rec["right_held"] = False
                pair_rec["right_object_id"] = None
            rt.structured_events.emit(
                str(merge_rec.get("event") or "MATERIAL_COMBINE_REJECTED"),
                tick=int(tick),
                evidence=dict(merge_rec),
            )
        rec = getattr(rt, "last_manipulator_receipt", None)
        if isinstance(rec, dict):
            rec["pair"] = pair_rec
    from .explicit_surface_deposition import (
        apply_explicit_surface_deposition,
        command_requested_from_motor,
    )

    planned_deposits: list[tuple[Any, dict[str, Any], dict[str, Any]]] = []
    for row in sorted(holders, key=lambda r: str(r["body_id"])):
        rt = row["runtime"]
        motor = getattr(rt, "last_motor_output", None)
        if not command_requested_from_motor(motor):
            continue
        from .world_material_transaction import (
            commit_material_transaction,
            plan_deposition,
            world_material_transactions_is_active,
        )
        if world_material_transactions_is_active(row["config"]):
            planned_deposits.append((rt, row, plan_deposition(
                world=world,
                config=row["config"],
                body=row["body"],
                body_id=row["body_id"],
                held_object_id_at_tick_start=held_at_tick_start.get(str(row["body_id"])),
                tick=tick,
                runtime=rt,
                actor_agent_id=str(getattr(rt, "technical_id", None) or row["body_id"]),
                selection_provenance=str(getattr(rt, "last_selected_action", None) or ""),
            )))
            continue
        deposit_rec = apply_explicit_surface_deposition(
            world=world,
            config=row["config"],
            body=row["body"],
            body_id=row["body_id"],
            command_requested=True,
            held_object_id_at_tick_start=held_at_tick_start.get(str(row["body_id"])),
            tick=tick,
            runtime=rt,
        )
        if deposit_rec is None:
            continue
        rt.last_surface_deposition_receipt = deposit_rec
        rec = getattr(rt, "last_manipulator_receipt", None)
        if isinstance(rec, dict):
            rec["surface_deposition"] = {
                "event": deposit_rec.get("event"),
                "outcome": deposit_rec.get("outcome"),
                "deposit_id": deposit_rec.get("deposit_id"),
                "source_object_id": deposit_rec.get("source_object_id"),
            }
        rt.structured_events.emit(
            str(deposit_rec.get("event") or "SURFACE_DEPOSITION_REJECTED"),
            tick=int(tick),
            evidence=dict(deposit_rec),
        )
    for rt, row, planned in planned_deposits:
        committed = commit_material_transaction(world, planned)
        rt.last_world_material_transaction = committed.get("receipt")
        deposit_rec = committed.get("legacy")
        if not isinstance(deposit_rec, dict):
            continue
        rt.last_surface_deposition_receipt = deposit_rec
        rec = getattr(rt, "last_manipulator_receipt", None)
        if isinstance(rec, dict):
            rec["surface_deposition"] = {
                "event": deposit_rec.get("event"),
                "outcome": deposit_rec.get("outcome"),
                "deposit_id": deposit_rec.get("deposit_id"),
                "source_object_id": deposit_rec.get("source_object_id"),
            }
        rt.structured_events.emit(
            str(deposit_rec.get("event") or "SURFACE_DEPOSITION_REJECTED"),
            tick=int(tick),
            evidence=dict(deposit_rec),
        )
    if _fok_on:
        from .free_resource_object_kinematics import finish_step, record_effector_poses

        record_effector_poses(world, holders, int(tick))
        finish_step(world, int(tick), _fok_motion, _fok_releases)
    if runtimes:
        from mechanistic_mind.physical_system.spatial_contents import (
            multi_content_spatial_index_is_active,
            reconcile_contents,
        )
        config = getattr(runtimes[0], "config", None)
        if multi_content_spatial_index_is_active(config):
            reconcile_contents(
                world,
                tick=int(tick),
                reason="manipulator",
                config=config,
                include_bodies=False,
            )
    return receipts


def manipulator_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": SINGLE_PHYSICAL_MANIPULATOR,
        "config_path": "single_physical_manipulator.enabled",
        "label": "SINGLE PHYSICAL MANIPULATOR",
        "description": (
            "Acanthostega-only one effector posed from body heading. "
            "Not a second arm. Not neck. Not a camera."
        ),
        "validation": "Acanthostega Phase A Single Grasp effector geometry.",
        "provenance": "acanthostega_single_physical_manipulator",
        "default_integrated": True,
        "ablatable": True,
        "enabled": bool(enabled),
        "state": "ON" if enabled else "OFF",
        "category": "MOTOR",
        "promotion_class": "EXPERIMENTAL",
        "scientific_status": "IMPLEMENTED",
        "dependencies": ["physical_resource_objects"],
        "toggle_policy": "RESET_RECOMMENDED",
        "model_line": "ACANTHOSTEGA",
        "historical_compatibility": "missing key means no effector",
        "live_state_available": True,
        "receipts_available": True,
        "events_available": True,
        "capabilities": {
            "single_effector": True,
            "second_manipulator": False,
            "grasp_release": False,
            "material_conversion": False,
            "lifecycle": False,
        },
    }


def grasp_release_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": PHYSICAL_GRASP_RELEASE,
        "config_path": "physical_grasp_release.enabled",
        "label": "PHYSICAL GRASP RELEASE",
        "description": (
            "Acanthostega-only GRASP/RELEASE motor channel. Local nearest FREE_STATIC "
            "in reach. Agent does not select object_id. Not PUSH. Not ingestion."
        ),
        "validation": "Acanthostega Phase A Single Grasp attachment.",
        "provenance": "acanthostega_physical_grasp_release",
        "default_integrated": True,
        "ablatable": True,
        "enabled": bool(enabled),
        "state": "ON" if enabled else "OFF",
        "category": "MOTOR",
        "promotion_class": "EXPERIMENTAL",
        "scientific_status": "IMPLEMENTED",
        "dependencies": [SINGLE_PHYSICAL_MANIPULATOR],
        "toggle_policy": "RESET_RECOMMENDED",
        "model_line": "ACANTHOSTEGA",
        "historical_compatibility": "missing key means no grasp/release",
        "live_state_available": True,
        "receipts_available": True,
        "events_available": True,
        "capabilities": {
            "grasp_release": True,
            "symbolic_object_targeting": False,
            "throw": False,
            "ingestion": False,
            "mixing": False,
            "lifecycle": False,
        },
    }


def bilateral_manipulator_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": BILATERAL_PHYSICAL_MANIPULATORS,
        "config_path": "bilateral_physical_manipulators.enabled",
        "label": "BILATERAL PHYSICAL MANIPULATORS",
        "description": (
            "Acanthostega-only LEFT and RIGHT effectors from body heading. "
            "LEFT = +lateral, RIGHT = -lateral. Not neck. Not mixing."
        ),
        "validation": "Acanthostega Phase A Bilateral Grasp geometry.",
        "provenance": "acanthostega_bilateral_physical_manipulators",
        "default_integrated": True,
        "ablatable": True,
        "enabled": bool(enabled),
        "state": "ON" if enabled else "OFF",
        "category": "MOTOR",
        "promotion_class": "EXPERIMENTAL",
        "scientific_status": "IMPLEMENTED",
        "dependencies": ["physical_resource_objects"],
        "toggle_policy": "RESET_RECOMMENDED",
        "model_line": "ACANTHOSTEGA",
        "historical_compatibility": "missing key means no second effector",
        "live_state_available": True,
        "receipts_available": True,
        "events_available": True,
        "capabilities": {
            "single_effector": False,
            "second_manipulator": True,
            "grasp_release": False,
            "material_conversion": False,
            "lifecycle": False,
        },
    }


def bilateral_grasp_release_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": BILATERAL_GRASP_RELEASE,
        "config_path": "bilateral_grasp_release.enabled",
        "label": "BILATERAL GRASP RELEASE",
        "description": (
            "Independent LEFT/RIGHT GRASP/RELEASE. Same-body assignment by "
            "surface distance. Agent does not select object_id. Not mixing."
        ),
        "validation": "Acanthostega Phase A Bilateral Grasp attachment.",
        "provenance": "acanthostega_bilateral_grasp_release",
        "default_integrated": True,
        "ablatable": True,
        "enabled": bool(enabled),
        "state": "ON" if enabled else "OFF",
        "category": "MOTOR",
        "promotion_class": "EXPERIMENTAL",
        "scientific_status": "IMPLEMENTED",
        "dependencies": [BILATERAL_PHYSICAL_MANIPULATORS],
        "toggle_policy": "RESET_RECOMMENDED",
        "model_line": "ACANTHOSTEGA",
        "historical_compatibility": "missing key means no bilateral grasp",
        "live_state_available": True,
        "receipts_available": True,
        "events_available": True,
        "capabilities": {
            "grasp_release": True,
            "symbolic_object_targeting": False,
            "throw": False,
            "ingestion": False,
            "mixing": False,
            "lifecycle": False,
        },
    }


def bilateral_bring_together_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": BILATERAL_BRING_TOGETHER,
        "config_path": "bilateral_bring_together.enabled",
        "label": "BILATERAL BRING TOGETHER",
        "description": (
            "Acanthostega-only pair aperture channel. BRING_TOGETHER/SEPARATE "
            "move effectors gradually. Held-object surface contact is not mixing."
        ),
        "validation": "Acanthostega Phase A Bring Together pair actuation.",
        "provenance": "acanthostega_bilateral_bring_together",
        "default_integrated": True,
        "ablatable": True,
        "enabled": bool(enabled),
        "state": "ON" if enabled else "OFF",
        "category": "MOTOR",
        "promotion_class": "EXPERIMENTAL",
        "scientific_status": "IMPLEMENTED",
        "dependencies": [BILATERAL_GRASP_RELEASE],
        "toggle_policy": "RESET_RECOMMENDED",
        "model_line": "ACANTHOSTEGA",
        "historical_compatibility": "missing key means no pair channel",
        "live_state_available": True,
        "receipts_available": True,
        "events_available": True,
        "capabilities": {
            "pair_actuation": True,
            "held_object_contact": True,
            "mixing": False,
            "reactions": False,
            "ingestion": False,
            "lifecycle": False,
        },
    }
