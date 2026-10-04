"""Acanthostega-only passive physical resource objects.

Not cell stocks R_A/R_B. Not food. Not agent-accessible as a symbolic item.
mass is inertial mass (unused by locomotion in this slice).
quantity is total material amount (sum of composition amounts).
This slice uses density 1: quantity == mass for the canonical first object.

optical_radius is the physical optical surface radius in world cells
(same units as body x,y). It is not a collision radius (collision is absent).
optical_response is an anonymous (c0,c1,c2) surface coefficient, stored
separately from composition — not a chemical or resource label.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, fields
from typing import Any

from mechanistic_mind.planet.topology import toroidal_delta, wrap_coord

PHYSICAL_RESOURCE_OBJECTS = "physical_resource_objects"
PHYSICAL_RESOURCE_OBJECT_VISION = "physical_resource_object_vision"
PHYSICAL_STATE_FREE_STATIC = "FREE_STATIC"
PHYSICAL_STATE_HELD = "HELD"
CANONICAL_FIRST_OBJECT_ID = "resource-000001"
CANONICAL_SECOND_OBJECT_ID = "resource-000002"
CANONICAL_SPAWN_X = 24.5
CANONICAL_SPAWN_Y = 8.5
CANONICAL_SPAWN_X2 = 8.5
CANONICAL_SPAWN_Y2 = 24.5
CANONICAL_MASS = 1.0
CANONICAL_COMPONENT_ID = "component_0"
CANONICAL_COMPONENT_AMOUNT = 1.0
# Optical surface radius in world cells. Not Observer glyph size. Not collision.
CANONICAL_OPTICAL_RADIUS = 0.45
# Material interaction surface radius. Not optical, not Observer glyph, not a
# general collision radius (free-object collision is absent).
# Open bilateral aperture is 0.84; 2×0.20=0.40 so open pose has no contact
# and closed pose (aperture 0.40) reaches surface contact without overlap.
CANONICAL_INTERACTION_RADIUS = 0.20
# Physical collision radius for body/object contact FACT. Not optical, not
# interaction/held-contact, not Observer glyph size.
CANONICAL_COLLISION_RADIUS = 0.25
# Anonymous spectral coefficients (not RGB, not RESOURCE type). Independent of composition.
CANONICAL_OPTICAL_RESPONSE = (0.72, 0.41, 0.18)
CANONICAL_OPTICAL_RESPONSE_2 = (0.18, 0.55, 0.72)


@dataclass(frozen=True)
class MaterialComponent:
    """Anonymous material amount. No biological effect in this slice."""

    component_id: str
    amount: float

    def to_dict(self) -> dict[str, Any]:
        return {"component_id": str(self.component_id), "amount": float(self.amount)}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MaterialComponent":
        d = data or {}
        return cls(
            component_id=str(d.get("component_id") or CANONICAL_COMPONENT_ID),
            amount=float(d.get("amount") or 0.0),
        )


def clip_optical_triplet(raw: Any) -> tuple[float, float, float]:
    if raw is None:
        return CANONICAL_OPTICAL_RESPONSE
    if isinstance(raw, dict):
        vals = [raw.get("c0"), raw.get("c1"), raw.get("c2")]
        if all(v is None for v in vals):
            vals = [raw.get(0), raw.get(1), raw.get(2)]
        seq = vals
    else:
        seq = list(raw)
    out = []
    defaults = CANONICAL_OPTICAL_RESPONSE
    for i in range(3):
        try:
            v = float(seq[i]) if i < len(seq) and seq[i] is not None else float(defaults[i])
        except (TypeError, ValueError):
            v = float(defaults[i])
        out.append(max(0.0, min(1.0, v)))
    return (out[0], out[1], out[2])


def clip_optical_radius(raw: Any) -> float:
    try:
        r = float(raw)
    except (TypeError, ValueError):
        r = CANONICAL_OPTICAL_RADIUS
    if not math.isfinite(r):
        r = CANONICAL_OPTICAL_RADIUS
    return float(max(0.0, min(8.0, r)))


def clip_interaction_radius(raw: Any) -> float:
    try:
        r = float(raw)
    except (TypeError, ValueError):
        r = CANONICAL_INTERACTION_RADIUS
    if not math.isfinite(r):
        r = CANONICAL_INTERACTION_RADIUS
    return float(max(0.0, min(8.0, r)))


@dataclass
class ResourceObject:
    object_id: str
    x: float
    y: float
    mass: float
    quantity: float
    composition: tuple[MaterialComponent, ...]
    physical_state: str = PHYSICAL_STATE_FREE_STATIC
    holder_body_id: str | None = None
    manipulator_id: str | None = None
    vx: float = 0.0
    vy: float = 0.0
    provenance: dict[str, Any] = field(default_factory=dict)
    optical_radius: float = CANONICAL_OPTICAL_RADIUS
    optical_response: tuple[float, float, float] = CANONICAL_OPTICAL_RESPONSE
    interaction_radius: float = CANONICAL_INTERACTION_RADIUS
    collision_radius: float = CANONICAL_COLLISION_RADIUS
    material_revision: int = 0
    # Acanthostega Phase C vertical (unused when flat_ground_gravity OFF).
    z: float = 0.0
    vz: float = 0.0
    grounded: bool = True
    vertical_half_extent: float | None = None
    # Detached-terrain placement V1: None = immediately eligible (legacy).
    creation_tick: int | None = None
    dynamics_eligible_tick: int | None = None

    def copy(self) -> "ResourceObject":
        return ResourceObject(
            object_id=str(self.object_id),
            x=float(self.x),
            y=float(self.y),
            mass=float(self.mass),
            quantity=float(self.quantity),
            composition=tuple(
                MaterialComponent(c.component_id, float(c.amount)) for c in self.composition
            ),
            physical_state=str(self.physical_state),
            holder_body_id=(str(self.holder_body_id) if self.holder_body_id else None),
            manipulator_id=(str(self.manipulator_id) if self.manipulator_id else None),
            vx=float(self.vx or 0.0),
            vy=float(self.vy or 0.0),
            provenance=dict(self.provenance or {}),
            optical_radius=clip_optical_radius(self.optical_radius),
            optical_response=clip_optical_triplet(self.optical_response),
            interaction_radius=clip_interaction_radius(self.interaction_radius),
            collision_radius=float(getattr(self, "collision_radius", CANONICAL_COLLISION_RADIUS) or CANONICAL_COLLISION_RADIUS),
            material_revision=int(getattr(self, "material_revision", 0) or 0),
            z=float(getattr(self, "z", 0.0) or 0.0),
            vz=float(getattr(self, "vz", 0.0) or 0.0),
            grounded=bool(getattr(self, "grounded", True)),
            vertical_half_extent=getattr(self, "vertical_half_extent", None),
            creation_tick=(
                int(self.creation_tick) if getattr(self, "creation_tick", None) is not None else None
            ),
            dynamics_eligible_tick=(
                int(self.dynamics_eligible_tick)
                if getattr(self, "dynamics_eligible_tick", None) is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        c0, c1, c2 = clip_optical_triplet(self.optical_response)
        payload = {

            "object_id": str(self.object_id),
            "x": float(self.x),
            "y": float(self.y),
            "mass": float(self.mass),
            "quantity": float(self.quantity),
            "composition": [c.to_dict() for c in self.composition],
            "physical_state": str(self.physical_state),
            "holder_body_id": (str(self.holder_body_id) if self.holder_body_id else None),
            "manipulator_id": (str(self.manipulator_id) if self.manipulator_id else None),
            "vx": float(self.vx or 0.0),
            "vy": float(self.vy or 0.0),
            "provenance": dict(self.provenance or {}),
            "optical_radius": clip_optical_radius(self.optical_radius),
            "optical_response": {"c0": c0, "c1": c1, "c2": c2},
            "interaction_radius": clip_interaction_radius(self.interaction_radius),
            "collision_radius": float(getattr(self, "collision_radius", CANONICAL_COLLISION_RADIUS) or CANONICAL_COLLISION_RADIUS),
            **({} if int(getattr(self, "material_revision", 0) or 0) == 0 else {
                "material_revision": int(self.material_revision),
            }),
            "researcher_only": True,
            "agent_accessible": False,
        }
        z = float(getattr(self, "z", 0.0) or 0.0)
        vz = float(getattr(self, "vz", 0.0) or 0.0)
        grounded = bool(getattr(self, "grounded", True))
        he = getattr(self, "vertical_half_extent", None)
        if abs(z) > 1e-15 or abs(vz) > 1e-15 or (not grounded) or he is not None:
            payload["z"] = z
            payload["vz"] = vz
            payload["grounded"] = grounded
            if he is not None:
                payload["vertical_half_extent"] = float(he)
        ct = getattr(self, "creation_tick", None)
        det = getattr(self, "dynamics_eligible_tick", None)
        if ct is not None:
            payload["creation_tick"] = int(ct)
        if det is not None:
            payload["dynamics_eligible_tick"] = int(det)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ResourceObject":
        d = dict(data or {})
        raw_comp = d.get("composition") or []
        comps: list[MaterialComponent] = []
        if isinstance(raw_comp, dict):
            for k, v in raw_comp.items():
                comps.append(MaterialComponent(str(k), float(v)))
        else:
            for item in raw_comp:
                if isinstance(item, dict):
                    comps.append(MaterialComponent.from_dict(item))
        if not comps:
            comps.append(MaterialComponent(CANONICAL_COMPONENT_ID, 0.0))
        qty = d.get("quantity")
        if qty is None:
            qty = sum(float(c.amount) for c in comps)
        opt = d.get("optical_response")
        if opt is None and "optical_c0" in d:
            opt = (d.get("optical_c0"), d.get("optical_c1"), d.get("optical_c2"))
        radius = d.get("optical_radius")
        if radius is None:
            radius = CANONICAL_OPTICAL_RADIUS
        return cls(
            object_id=str(d.get("object_id") or CANONICAL_FIRST_OBJECT_ID),
            x=float(d.get("x") or 0.0),
            y=float(d.get("y") or 0.0),
            mass=float(d.get("mass") or 0.0),
            quantity=float(qty),
            composition=tuple(comps),
            physical_state=str(d.get("physical_state") or PHYSICAL_STATE_FREE_STATIC),
            holder_body_id=(str(d["holder_body_id"]) if d.get("holder_body_id") else None),
            manipulator_id=(str(d["manipulator_id"]) if d.get("manipulator_id") else None),
            vx=float(d.get("vx") or 0.0),
            vy=float(d.get("vy") or 0.0),
            provenance=dict(d.get("provenance") or {}),
            optical_radius=clip_optical_radius(radius),
            optical_response=clip_optical_triplet(opt if opt is not None else CANONICAL_OPTICAL_RESPONSE),
            interaction_radius=clip_interaction_radius(
                d["interaction_radius"] if d.get("interaction_radius") is not None else CANONICAL_INTERACTION_RADIUS
            ),
            collision_radius=float(
                d["collision_radius"] if d.get("collision_radius") is not None else CANONICAL_COLLISION_RADIUS
            ),
            material_revision=int(d.get("material_revision") or 0),
            z=float(d.get("z") or 0.0),
            vz=float(d.get("vz") or 0.0),
            grounded=bool(d["grounded"]) if "grounded" in d else True,
            vertical_half_extent=(
                float(d["vertical_half_extent"]) if d.get("vertical_half_extent") is not None else None
            ),
            creation_tick=(int(d["creation_tick"]) if d.get("creation_tick") is not None else None),
            dynamics_eligible_tick=(
                int(d["dynamics_eligible_tick"]) if d.get("dynamics_eligible_tick") is not None else None
            ),
        )


@dataclass
class PhysicalResourceObjectsConfig:
    """Fresh default OFF. Missing snapshot key → OFF (legacy)."""

    enabled: bool = False
    spawn_id: str = CANONICAL_FIRST_OBJECT_ID
    spawn_x: float = CANONICAL_SPAWN_X
    spawn_y: float = CANONICAL_SPAWN_Y
    spawn_mass: float = CANONICAL_MASS
    spawn_component_id: str = CANONICAL_COMPONENT_ID
    spawn_component_amount: float = CANONICAL_COMPONENT_AMOUNT
    spawn_optical_radius: float = CANONICAL_OPTICAL_RADIUS
    spawn_optical_c0: float = CANONICAL_OPTICAL_RESPONSE[0]
    spawn_optical_c1: float = CANONICAL_OPTICAL_RESPONSE[1]
    spawn_optical_c2: float = CANONICAL_OPTICAL_RESPONSE[2]
    spawn_interaction_radius: float = CANONICAL_INTERACTION_RADIUS
    # Empty → one canonical object (Materials / Vision / Single Grasp).
    spawn_objects: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PhysicalResourceObjectsConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        raw = payload.get("spawn_objects")
        if raw is None:
            payload.pop("spawn_objects", None)
        else:
            payload["spawn_objects"] = [dict(row) for row in list(raw or []) if isinstance(row, dict)]
        return cls(**payload)


@dataclass
class PhysicalResourceObjectVisionConfig:
    """Acanthostega-only. Missing snapshot key → OFF (agent-invisible objects)."""

    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PhysicalResourceObjectVisionConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        return cls(**payload)


def objects_is_active(config: Any) -> bool:
    if config is None:
        return False
    if str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "physical_resource_objects", None)
    return bool(getattr(cfg, "enabled", False))


def set_physical_resource_objects(config: Any, enabled: bool) -> None:
    """Enable only on Acanthostega. Tiktaalik cannot host objects."""
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "physical_resource_objects", None)
    if cur is None:
        config.physical_resource_objects = PhysicalResourceObjectsConfig(enabled=on)
    else:
        cur.enabled = on


def object_vision_is_active(config: Any) -> bool:
    if not objects_is_active(config):
        return False
    cfg = getattr(config, "physical_resource_object_vision", None)
    return bool(getattr(cfg, "enabled", False))


def set_physical_resource_object_vision(config: Any, enabled: bool) -> None:
    """Anonymous optical sampling of world objects. Tiktaalik remains OFF."""
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "physical_resource_object_vision", None)
    if cur is None:
        config.physical_resource_object_vision = PhysicalResourceObjectVisionConfig(enabled=on)
    else:
        cur.enabled = on
    nfe = getattr(config, "near_field_exteroception", None)
    if nfe is not None and hasattr(nfe, "resource_object_vision_enabled"):
        nfe.resource_object_vision_enabled = bool(on)


def parse_resource_object_index(object_id: str) -> int | None:
    s = str(object_id or "")
    prefix = "resource-"
    if not s.startswith(prefix):
        return None
    tail = s[len(prefix):]
    if not tail.isdigit():
        return None
    return int(tail)


def next_object_id(next_index: int) -> str:
    return f"resource-{max(1, int(next_index)):06d}"


def ensure_resource_object_state(planet: Any) -> list[ResourceObject]:
    raw = getattr(planet, "resource_objects", None)
    out: list[ResourceObject] = []
    if raw:
        for item in raw:
            if isinstance(item, ResourceObject):
                out.append(item)
            elif isinstance(item, dict):
                out.append(ResourceObject.from_dict(item))
    planet.resource_objects = out
    if getattr(planet, "resource_object_next_id", None) is None:
        planet.resource_object_next_id = 1
    return out


def objects_from_payload(payload: Any) -> tuple[list[ResourceObject], int]:
    """Legacy missing field → empty list, next_id 1."""
    if payload is None:
        return [], 1
    rows = payload
    next_id = 1
    if isinstance(payload, dict):
        rows = payload.get("objects") or payload.get("resource_objects") or []
        next_id = int(payload.get("next_id") or payload.get("resource_object_next_id") or 1)
    objs = []
    seen: set[str] = set()
    max_idx = 0
    for item in rows or []:
        obj = item.copy() if isinstance(item, ResourceObject) else ResourceObject.from_dict(item)
        if obj.object_id in seen:
            continue
        seen.add(obj.object_id)
        objs.append(obj)
        idx = parse_resource_object_index(obj.object_id)
        if idx is not None:
            max_idx = max(max_idx, idx)
    next_id = max(int(next_id), max_idx + 1, 1)
    return objs, next_id


def serialize_resource_objects(planet: Any) -> dict[str, Any]:
    objs = ensure_resource_object_state(planet)
    next_id = int(getattr(planet, "resource_object_next_id", 1) or 1)
    return {
        "objects": [o.to_dict() for o in objs],
        "next_id": next_id,
    }


def restore_resource_objects(planet: Any, payload: Any) -> None:
    objs, next_id = objects_from_payload(payload)
    planet.resource_objects = [o.copy() for o in objs]
    planet.resource_object_next_id = int(next_id)


def canonical_first_object(*, width: int, height: int, config: Any, seed: int, tick: int) -> ResourceObject:
    cfg = getattr(config, "physical_resource_objects", None) or PhysicalResourceObjectsConfig()
    amount = float(cfg.spawn_component_amount)
    mass = float(cfg.spawn_mass)
    comp = MaterialComponent(str(cfg.spawn_component_id), amount)
    oid = str(cfg.spawn_id or CANONICAL_FIRST_OBJECT_ID)
    x = float(wrap_coord(float(cfg.spawn_x), int(width)))
    y = float(wrap_coord(float(cfg.spawn_y), int(height)))
    return ResourceObject(
        object_id=oid,
        x=x,
        y=y,
        mass=mass,
        quantity=float(amount),
        composition=(comp,),
        physical_state=PHYSICAL_STATE_FREE_STATIC,
        optical_radius=clip_optical_radius(getattr(cfg, "spawn_optical_radius", CANONICAL_OPTICAL_RADIUS)),
        optical_response=clip_optical_triplet((
            getattr(cfg, "spawn_optical_c0", CANONICAL_OPTICAL_RESPONSE[0]),
            getattr(cfg, "spawn_optical_c1", CANONICAL_OPTICAL_RESPONSE[1]),
            getattr(cfg, "spawn_optical_c2", CANONICAL_OPTICAL_RESPONSE[2]),
        )),
        interaction_radius=clip_interaction_radius(
            getattr(cfg, "spawn_interaction_radius", CANONICAL_INTERACTION_RADIUS)
        ),
        collision_radius=float(getattr(cfg, "spawn_collision_radius", CANONICAL_COLLISION_RADIUS) or CANONICAL_COLLISION_RADIUS),
        provenance={
            "source": "PRESET_SPAWN",
            "public_preset": getattr(config, "public_preset", None),
            "seed": int(seed),
            "tick": int(tick),
            "mechanism": PHYSICAL_RESOURCE_OBJECTS,
            "note": "Passive world object. Not transferred into R_A/R_B. Researcher-only.",
        },
    )


def default_bilateral_spawn_objects() -> list[dict[str, Any]]:
    """Deterministic two-object list. Not used by Materials / Vision / Single Grasp."""
    c0, c1, c2 = CANONICAL_OPTICAL_RESPONSE
    d0, d1, d2 = CANONICAL_OPTICAL_RESPONSE_2
    return [
        {
            "object_id": CANONICAL_FIRST_OBJECT_ID,
            "x": CANONICAL_SPAWN_X,
            "y": CANONICAL_SPAWN_Y,
            "mass": CANONICAL_MASS,
            "component_id": CANONICAL_COMPONENT_ID,
            "component_amount": CANONICAL_COMPONENT_AMOUNT,
            "optical_radius": CANONICAL_OPTICAL_RADIUS,
            "optical_c0": c0,
            "optical_c1": c1,
            "optical_c2": c2,
        },
        {
            "object_id": CANONICAL_SECOND_OBJECT_ID,
            "x": CANONICAL_SPAWN_X2,
            "y": CANONICAL_SPAWN_Y2,
            "mass": CANONICAL_MASS,
            "component_id": CANONICAL_COMPONENT_ID,
            "component_amount": CANONICAL_COMPONENT_AMOUNT,
            "optical_radius": CANONICAL_OPTICAL_RADIUS,
            "optical_c0": d0,
            "optical_c1": d1,
            "optical_c2": d2,
        },
    ]


def object_from_spawn_spec(
    spec: dict[str, Any],
    *,
    width: int,
    height: int,
    config: Any,
    seed: int,
    tick: int,
    fallback_id: str,
) -> ResourceObject:
    cfg = getattr(config, "physical_resource_objects", None) or PhysicalResourceObjectsConfig()
    amount = float(spec.get("component_amount", spec.get("quantity", cfg.spawn_component_amount)))
    mass = float(spec.get("mass", cfg.spawn_mass))
    cid = str(spec.get("component_id") or cfg.spawn_component_id)
    oid = str(spec.get("object_id") or fallback_id)
    x = float(wrap_coord(float(spec.get("x", cfg.spawn_x)), int(width)))
    y = float(wrap_coord(float(spec.get("y", cfg.spawn_y)), int(height)))
    return ResourceObject(
        object_id=oid,
        x=x,
        y=y,
        mass=mass,
        quantity=float(amount),
        composition=(MaterialComponent(cid, amount),),
        physical_state=PHYSICAL_STATE_FREE_STATIC,
        optical_radius=clip_optical_radius(spec.get("optical_radius", getattr(cfg, "spawn_optical_radius", CANONICAL_OPTICAL_RADIUS))),
        optical_response=clip_optical_triplet((
            spec.get("optical_c0", getattr(cfg, "spawn_optical_c0", CANONICAL_OPTICAL_RESPONSE[0])),
            spec.get("optical_c1", getattr(cfg, "spawn_optical_c1", CANONICAL_OPTICAL_RESPONSE[1])),
            spec.get("optical_c2", getattr(cfg, "spawn_optical_c2", CANONICAL_OPTICAL_RESPONSE[2])),
        )),
        interaction_radius=clip_interaction_radius(
            spec.get("interaction_radius", getattr(cfg, "spawn_interaction_radius", CANONICAL_INTERACTION_RADIUS))
        ),
        collision_radius=float(
            spec.get("collision_radius", getattr(cfg, "spawn_collision_radius", CANONICAL_COLLISION_RADIUS))
            or CANONICAL_COLLISION_RADIUS
        ),
        provenance={
            "source": "PRESET_SPAWN",
            "public_preset": getattr(config, "public_preset", None),
            "seed": int(seed),
            "tick": int(tick),
            "mechanism": PHYSICAL_RESOURCE_OBJECTS,
            "note": "Passive world object. Not transferred into R_A/R_B. Researcher-only.",
        },
    )


def spawn_preset_resource_objects(planet: Any, config: Any, *, seed: int, tick: int = 0) -> list[ResourceObject]:
    """Deterministic spawn at construction. Does not run on restore (caller overwrites world)."""
    ensure_resource_object_state(planet)
    planet.resource_objects = []
    planet.resource_object_next_id = 1
    if not objects_is_active(config):
        return []
    h, w = int(planet.T.shape[0]), int(planet.T.shape[1])
    cfg = getattr(config, "physical_resource_objects", None) or PhysicalResourceObjectsConfig()
    specs = [dict(row) for row in list(getattr(cfg, "spawn_objects", None) or []) if isinstance(row, dict)]
    if not specs:
        obj = canonical_first_object(width=w, height=h, config=config, seed=seed, tick=tick)
        planet.resource_objects = [obj]
        idx = parse_resource_object_index(obj.object_id) or 1
        planet.resource_object_next_id = int(idx) + 1
        return planet.resource_objects
    objs: list[ResourceObject] = []
    seen: set[str] = set()
    max_idx = 0
    for i, spec in enumerate(specs):
        fallback = next_object_id(i + 1)
        obj = object_from_spawn_spec(
            spec, width=w, height=h, config=config, seed=seed, tick=tick, fallback_id=fallback,
        )
        if obj.object_id in seen:
            continue
        seen.add(obj.object_id)
        objs.append(obj)
        idx = parse_resource_object_index(obj.object_id)
        if idx is not None:
            max_idx = max(max_idx, idx)
    planet.resource_objects = objs
    planet.resource_object_next_id = max(max_idx + 1, 1)
    return planet.resource_objects


def resource_object_occupied_cells(obj: ResourceObject, *, width: int, height: int) -> list[tuple[int, int]]:
    """Project optical disk onto vision sampler cells. Not collision occupancy."""
    w, h = int(width), int(height)
    if w <= 0 or h <= 0:
        return []
    ox = float(obj.x)
    oy = float(obj.y)
    radius = clip_optical_radius(obj.optical_radius)
    cx = int(math.floor(ox)) % w
    cy = int(math.floor(oy)) % h
    cells: set[tuple[int, int]] = {(cy, cx)}
    rad = int(math.ceil(radius)) + 1
    for dy in range(-rad, rad + 1):
        for dx in range(-rad, rad + 1):
            ix = int(wrap_coord(cx + dx, w))
            iy = int(wrap_coord(cy + dy, h))
            ncx = float(ix) + 0.5
            ncy = float(iy) + 0.5
            dist = math.hypot(toroidal_delta(ox, ncx, w), toroidal_delta(oy, ncy, h))
            if dist <= radius + 1e-12:
                cells.add((iy, ix))
    return list(cells)


def resource_object_optical_occupancy(
    world: Any,
    *,
    enabled: bool,
    cells: list[tuple[int, int]] | None = None,
) -> tuple[
    dict[tuple[int, int], float],
    dict[tuple[int, int], tuple[float, float, float]],
    dict[tuple[int, int], list[str]],
]:
    """Cell occupancy for the existing near-field sampler. Empty when mechanism OFF."""
    if not enabled:
        return {}, {}, {}
    indexed = getattr(world, "spatial_contents", None)
    if cells is not None and indexed is not None and not bool(getattr(indexed, "dirty", False)):
        from mechanistic_mind.physical_system.spatial_contents import resource_objects_for_cells

        objs = resource_objects_for_cells(world, cells)
    else:
        objs = ensure_resource_object_state(world)
    if not objs:
        return {}, {}, {}
    t = getattr(world, "T", None)
    if t is None:
        return {}, {}, {}
    h, w = int(t.shape[0]), int(t.shape[1])
    intensity: dict[tuple[int, int], float] = {}
    spectra: dict[tuple[int, int], tuple[float, float, float]] = {}
    ids: dict[tuple[int, int], list[str]] = {}
    for obj in objs:
        resp = clip_optical_triplet(obj.optical_response)
        bright = max(resp)
        if bright <= 0.0:
            continue
        oid = str(obj.object_id)
        for key in resource_object_occupied_cells(obj, width=w, height=h):
            prev_i = intensity.get(key, 0.0)
            if bright > prev_i:
                intensity[key] = bright
            prev_s = spectra.get(key)
            if prev_s is None:
                spectra[key] = resp
            else:
                spectra[key] = (
                    1.0 - (1.0 - float(prev_s[0])) * (1.0 - float(resp[0])),
                    1.0 - (1.0 - float(prev_s[1])) * (1.0 - float(resp[1])),
                    1.0 - (1.0 - float(prev_s[2])) * (1.0 - float(resp[2])),
                )
            bucket = ids.setdefault(key, [])
            if oid not in bucket:
                bucket.append(oid)
    return intensity, spectra, ids


def resource_objects_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": PHYSICAL_RESOURCE_OBJECTS,
        "config_path": "physical_resource_objects.enabled",
        "label": "PHYSICAL RESOURCE OBJECTS",
        "description": (
            "Acanthostega-only passive world objects with stable IDs. "
            "Not cell stocks A/B. Not grasped, perceived, or converted in this stage."
        ),
        "validation": "Acanthostega Phase A Materials passive object.",
        "provenance": "acanthostega_passive_resource_object",
        "default_integrated": True,
        "ablatable": True,
        "enabled": bool(enabled),
        "state": "ON" if enabled else "OFF",
        "category": "RESOURCES",
        "promotion_class": "EXPERIMENTAL",
        "scientific_status": "IMPLEMENTED",
        "dependencies": [],
        "toggle_policy": "RESET_RECOMMENDED",
        "model_line": "ACANTHOSTEGA",
        "historical_compatibility": "missing key preserves empty object list",
        "live_state_available": True,
        "receipts_available": False,
        "events_available": False,
        "capabilities": {
            "passive_object": True,
            "agent_perception": False,
            "grasp_release": False,
            "material_conversion": False,
            "lifecycle": False,
        },
    }


def resource_object_vision_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": PHYSICAL_RESOURCE_OBJECT_VISION,
        "config_path": "physical_resource_object_vision.enabled",
        "label": "PHYSICAL RESOURCE OBJECT VISION",
        "description": (
            "Acanthostega-only: object optical surfaces contribute to existing "
            "anonymous near-field channels. No object ID, type, or composition in cognition."
        ),
        "validation": "Acanthostega Phase A Material Vision anonymous optical contribution.",
        "provenance": "acanthostega_physical_resource_object_vision",
        "default_integrated": True,
        "ablatable": True,
        "enabled": bool(enabled),
        "state": "ON" if enabled else "OFF",
        "category": "PERCEPTION",
        "promotion_class": "EXPERIMENTAL",
        "scientific_status": "IMPLEMENTED",
        "dependencies": [PHYSICAL_RESOURCE_OBJECTS],
        "toggle_policy": "RESET_RECOMMENDED",
        "model_line": "ACANTHOSTEGA",
        "historical_compatibility": "missing key leaves objects researcher-visible and agent-invisible",
        "live_state_available": True,
        "receipts_available": False,
        "events_available": False,
        "capabilities": {
            "anonymous_optical_contribution": True,
            "symbolic_resource_sensor": False,
            "agent_perception_of_resource": False,
            "grasp_release": False,
            "material_conversion": False,
            "lifecycle": False,
        },
    }
