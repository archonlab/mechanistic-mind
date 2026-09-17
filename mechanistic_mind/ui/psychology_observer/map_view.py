"""Camera, procedural world rendering, and entity inspection for the Observer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .model import PsychologyTickView


@dataclass(slots=True)
class MapCamera:
    """Display-only transform between simulation cells and screen pixels."""

    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    base_cell_px: float = 54.0
    minimum_zoom: float = 0.25
    maximum_zoom: float = 4.0

    @property
    def cell_px(self) -> float:
        return self.base_cell_px * self.zoom

    def world_to_screen(
        self,
        position: tuple[float, float],
        *,
        viewport: tuple[float, float],
        world_size: tuple[int, int],
    ) -> tuple[float, float]:
        width, height = viewport
        cols, rows = world_size
        return (
            width / 2 + self.pan_x
            + (position[0] + 0.5 - cols / 2) * self.cell_px,
            height / 2 + self.pan_y
            + (position[1] + 0.5 - rows / 2) * self.cell_px,
        )

    def screen_to_world(
        self,
        point: tuple[float, float],
        *,
        viewport: tuple[float, float],
        world_size: tuple[int, int],
    ) -> tuple[float, float]:
        width, height = viewport
        cols, rows = world_size
        return (
            (point[0] - width / 2 - self.pan_x) / self.cell_px
            + cols / 2 - 0.5,
            (point[1] - height / 2 - self.pan_y) / self.cell_px
            + rows / 2 - 0.5,
        )

    def fit(
        self,
        *,
        viewport: tuple[float, float],
        world_size: tuple[int, int],
        margin: float = 44.0,
    ) -> None:
        width, height = viewport
        cols, rows = world_size
        target = min(
            max(8.0, width - margin * 2) / max(1, cols),
            max(8.0, height - margin * 2) / max(1, rows),
        )
        self.zoom = max(
            self.minimum_zoom,
            min(self.maximum_zoom, target / self.base_cell_px),
        )
        self.pan_x = 0.0
        self.pan_y = 0.0

    def change_zoom(
        self,
        factor: float,
        *,
        anchor: tuple[float, float],
        viewport: tuple[float, float],
        world_size: tuple[int, int],
    ) -> None:
        world_anchor = self.screen_to_world(
            anchor, viewport=viewport, world_size=world_size
        )
        self.zoom = max(
            self.minimum_zoom,
            min(self.maximum_zoom, self.zoom * float(factor)),
        )
        projected = self.world_to_screen(
            world_anchor, viewport=viewport, world_size=world_size
        )
        self.pan_x += anchor[0] - projected[0]
        self.pan_y += anchor[1] - projected[1]

    def center_on(
        self,
        position: tuple[int, int],
        *,
        viewport: tuple[float, float],
        world_size: tuple[int, int],
    ) -> None:
        self.pan_x = 0.0
        self.pan_y = 0.0
        point = self.world_to_screen(
            position, viewport=viewport, world_size=world_size
        )
        self.pan_x = viewport[0] / 2 - point[0]
        self.pan_y = viewport[1] / 2 - point[1]


def object_visual_spec(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return an objective-property-only procedural visual specification."""
    shape = str(record.get("shape") or "circle").lower()
    if shape not in {"circle", "square", "triangle", "diamond", "hexagon"}:
        shape = "circle"
    return {
        "shape": shape,
        "color": str(record.get("color") or "#d89b45"),
        "opacity": max(0.1, min(1.0, float(record.get("opacity", 1.0)))),
        "size": max(0.15, min(1.35, float(record.get("size", 0.35)))),
        "interaction_state": str(record.get("interaction_state") or "FREE"),
        "carried_by": record.get("carried_by"),
        "active": bool(record.get("active", True)),
        "blocks_movement": bool(record.get("blocks_movement", False)),
    }


def quantity_fraction(record: Mapping[str, Any]) -> float | None:
    deltas = record.get("interaction_state_deltas")
    regeneration = record.get("regeneration_rates")
    tracks_quantity = (
        isinstance(deltas, dict) and "quantity" in deltas
    ) or (
        isinstance(regeneration, dict) and "quantity" in regeneration
    )
    if not tracks_quantity:
        return None
    try:
        current = float(record.get("quantity", 0.0))
        capacity = float(record.get("max_quantity", 0.0))
    except (TypeError, ValueError):
        return None
    if capacity <= 0.0:
        return 0.0
    return max(0.0, min(1.0, current / capacity))


def selection_snapshot(
    tick: PsychologyTickView,
    kind: str,
    entity_id: str,
) -> dict[str, Any]:
    """Keep world truth, current perception, and learned state distinct."""
    if kind == "agent":
        return {
            "entity": {"kind": "AGENT", "id": entity_id},
            "objective": {
                "position": tick.objective_position,
                "body": tick.body_truth,
            },
            "perceived": {
                "observation": tick.observation,
                "accessible_signals": tick.accessible_signals,
            },
            "learned": {
                "known_objects": tick.known_objects,
                "known_obstacles": tick.known_obstacles,
            },
        }

    raw_objective = tick.world_objects.get(entity_id)
    objective = (
        {
            key: value
            for key, value in raw_objective.items()
            if key != "hidden_role"
        }
        if isinstance(raw_objective, dict)
        else None
    )
    perceived = None
    visible = tick.observation.get("visible_objects", [])
    if isinstance(visible, list):
        perceived = next(
            (
                dict(item)
                for item in visible
                if isinstance(item, dict) and str(item.get("id")) == entity_id
            ),
            None,
        )
    learned_record = tick.known_objects.get(entity_id)
    action_predictions = {
        action: value
        for action, value in tick.predictions.items()
        if f":{entity_id}" in str(action)
    }
    learned = None
    if isinstance(learned_record, dict) or action_predictions:
        learned = {
            "memory": learned_record if isinstance(learned_record, dict) else None,
            "predictions": action_predictions,
        }
    return {
        "entity": {"kind": "OBJECT", "id": entity_id},
        "objective": objective,
        "perceived": perceived,
        "learned": learned,
    }


def _blend(foreground: str, background: str, opacity: float) -> str:
    try:
        fg = tuple(int(foreground[i:i + 2], 16) for i in (1, 3, 5))
        bg = tuple(int(background[i:i + 2], 16) for i in (1, 3, 5))
    except (ValueError, TypeError):
        return foreground
    values = tuple(
        round(f * opacity + b * (1.0 - opacity)) for f, b in zip(fg, bg)
    )
    return "#" + "".join(f"{value:02x}" for value in values)


@dataclass(slots=True)
class CanvasWorldRenderer:
    camera: MapCamera = field(default_factory=MapCamera)
    selected: tuple[str, str] | None = None
    _world_size: tuple[int, int] | None = None
    _hit_regions: list[tuple[float, float, float, str, str]] = field(
        default_factory=list
    )

    def fit(self, canvas: Any, tick: PsychologyTickView) -> None:
        viewport = self._viewport(canvas)
        size = (tick.width, tick.height)
        self.camera.fit(viewport=viewport, world_size=size)
        self._world_size = size

    def hit_test(self, x: float, y: float) -> tuple[str, str] | None:
        for cx, cy, radius, kind, entity_id in reversed(self._hit_regions):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                return kind, entity_id
        return None

    def draw(
        self,
        canvas: Any,
        tick: PsychologyTickView | None,
        palette: Mapping[str, str],
        *,
        show_truth: bool,
        show_memory: bool,
        trajectory: Sequence[tuple[int, int]],
        follow_agent: bool = False,
    ) -> None:
        canvas.delete("all")
        viewport = self._viewport(canvas)
        self._hit_regions = []
        if tick is None:
            canvas.create_text(
                viewport[0] / 2,
                viewport[1] / 2,
                text="WAITING FOR PSYCHOLOGY TELEMETRY\nChoose a world and start the run",
                fill=palette["text.muted"],
                justify="center",
                font=("TkDefaultFont", 10, "bold"),
            )
            return

        world_size = (tick.width, tick.height)
        if self._world_size != world_size:
            self.fit(canvas, tick)
        if follow_agent and tick.objective_position is not None:
            self.camera.center_on(
                tick.objective_position,
                viewport=viewport,
                world_size=world_size,
            )
        cell = self.camera.cell_px

        def center(pos: tuple[int, int]) -> tuple[float, float]:
            return self.camera.world_to_screen(
                pos, viewport=viewport, world_size=world_size
            )

        blocked = set(tick.blocked)
        terrain = tick.objective_world.get("terrain_factors", {})
        env_field = tick.objective_world.get("env_material_field", {}) or {}
        for y in range(tick.height):
            for x in range(tick.width):
                cx, cy = center((x, y))
                half = cell / 2
                key = f"{x},{y}"
                factor = float(terrain.get(key, 1.0)) if isinstance(terrain, dict) else 1.0
                env_avail = float(env_field.get(key, 0.0) or 0.0) if isinstance(env_field, dict) else 0.0
                fill = (
                    palette["surface.elevated"]
                    if (x, y) in blocked
                    else palette["surface.canvas"]
                )
                canvas.create_rectangle(
                    cx - half, cy - half, cx + half, cy + half,
                    fill=fill,
                    outline=palette["border.strong"] if (x, y) in blocked else palette["grid.line"],
                )
                # Update 4.9: faint overlay for local material availability (Observer only).
                if env_avail > 1e-6 and (x, y) not in blocked:
                    # Blend toward status.info-ish without new palette keys: stipple-like via higher outline weight.
                    alpha = max(0.0, min(1.0, float(env_avail)))
                    # Draw a smaller inset rectangle; intensity via outline color choice.
                    inset = max(1.0, half * 0.35 * alpha)
                    canvas.create_rectangle(
                        cx - inset,
                        cy - inset,
                        cx + inset,
                        cy + inset,
                        fill="",
                        outline=palette.get("status.info", palette["border.strong"]),
                        width=1 if alpha < 0.5 else 2,
                    )
                if factor != 1.0 and cell >= 34:
                    canvas.create_text(
                        cx - half + 4, cy - half + 3,
                        text=f"×{factor:g}", anchor="nw",
                        fill=palette["text.muted"], font=("TkFixedFont", 6),
                    )

        context = tick.objective_context_receipt
        if context.get("kind") == "DIRECTIONAL_LOCAL_EXPOSURE":
            origin = _position(context.get("position"))
            direction = _position(context.get("source_direction"))
            if origin is not None and direction is not None:
                for distance in range(0, 4):
                    pos = (
                        origin[0] + direction[0] * distance,
                        origin[1] + direction[1] * distance,
                    )
                    if not (0 <= pos[0] < tick.width and 0 <= pos[1] < tick.height):
                        continue
                    cx, cy = center(pos)
                    half = cell * 0.42
                    canvas.create_rectangle(
                        cx-half, cy-half, cx+half, cy+half,
                        outline=palette["chart.3"], dash=(5, 3), width=2,
                    )
                canvas.create_text(
                    12, 30, anchor="nw",
                    text=(
                        "directional exposure ×"
                        f"{float(context.get('exposure_multiplier', 1.0)):.3f}"
                    ),
                    fill=palette["chart.3"], font=("TkFixedFont", 7, "bold"),
                )

        if show_memory:
            for key in tick.known_positions:
                try:
                    x_text, y_text = str(key).split(",", 1)
                    cx, cy = center((int(x_text), int(y_text)))
                except Exception:
                    continue
                inset = cell * 0.13
                canvas.create_rectangle(
                    cx - cell / 2 + inset, cy - cell / 2 + inset,
                    cx + cell / 2 - inset, cy + cell / 2 - inset,
                    outline=palette["chart.2"], width=1,
                )

        if len(trajectory) >= 2:
            points = [coordinate for pos in trajectory for coordinate in center(pos)]
            canvas.create_line(*points, fill=palette["chart.1"], width=2)

        if show_truth:
            position_slots: dict[tuple[int, int], int] = {}
            for object_id, record in sorted(tick.world_objects.items()):
                if not isinstance(record, dict) or record.get("active", True) is False:
                    continue
                pos = _position(record.get("position"))
                if pos is None:
                    continue
                cx, cy = center(pos)
                slot = position_slots.get(pos, 0)
                position_slots[pos] = slot + 1
                offsets = ((0.0, 0.0), (-0.18, -0.12), (0.18, 0.12), (0.18, -0.12))
                offset_x, offset_y = offsets[min(slot, len(offsets) - 1)]
                cx += cell * offset_x
                cy += cell * offset_y
                spec = object_visual_spec(record)
                if spec["carried_by"]:
                    cx += cell * 0.22
                    cy -= cell * 0.20
                radius = max(5.0, min(cell * 0.38, cell * 0.20 * spec["size"] + 4))
                fill = _blend(
                    spec["color"], palette["surface.canvas"], spec["opacity"]
                )
                outline = (
                    palette["focus.ring"]
                    if self.selected == ("object", str(object_id))
                    else palette["text.primary"]
                )
                self._draw_shape(canvas, spec["shape"], cx, cy, radius, fill, outline)
                fraction = quantity_fraction(record)
                if fraction is not None:
                    bar_width = max(10.0, radius * 2)
                    bar_y = cy - radius - 6
                    canvas.create_rectangle(
                        cx - bar_width / 2,
                        bar_y,
                        cx + bar_width / 2,
                        bar_y + 3,
                        fill=palette["surface.elevated"],
                        outline=palette["border.strong"],
                    )
                    if fraction > 0.0:
                        canvas.create_rectangle(
                            cx - bar_width / 2,
                            bar_y,
                            cx - bar_width / 2 + bar_width * fraction,
                            bar_y + 3,
                            fill=spec["color"],
                            outline="",
                        )
                if spec["blocks_movement"]:
                    canvas.create_rectangle(
                        cx - radius - 2, cy - radius - 2,
                        cx + radius + 2, cy + radius + 2,
                        outline=palette["border.strong"], dash=(3, 2),
                    )
                if spec["interaction_state"] == "CARRIED":
                    canvas.create_line(
                        cx - cell * 0.16, cy + cell * 0.15, cx, cy,
                        fill=palette["chart.2"], width=2,
                    )
                displacement = record.get("last_displacement")
                if isinstance(displacement, dict) and displacement.get("kind") == "PUSHED":
                    before = _position(displacement.get("from"))
                    if before is not None:
                        bx, by = center(before)
                        canvas.create_line(
                            bx, by, cx, cy, fill=palette["chart.3"],
                            width=3, arrow="last", dash=(5, 3),
                        )
                canvas.create_text(
                    cx, cy + radius + 9, text=str(object_id),
                    fill=palette["text.secondary"], font=("TkFixedFont", 6, "bold"),
                )
                self._hit_regions.append((cx, cy, max(12.0, radius + 5), "object", str(object_id)))

        if show_memory:
            for object_id, record in sorted(tick.known_objects.items()):
                if not isinstance(record, dict):
                    continue
                pos = _position(record.get("position"))
                if pos is None:
                    continue
                cx, cy = center(pos)
                r = min(9.0, cell * 0.16)
                canvas.create_polygon(
                    cx, cy-r, cx+r, cy, cx, cy+r, cx-r, cy,
                    fill="", outline=palette["chart.2"], width=2,
                )

        if show_truth:
            for obstacle_id, record in sorted(tick.world_obstacles.items()):
                if not isinstance(record, dict) or record.get("active", True) is False:
                    continue
                pos = _position(record.get("position"))
                if pos is None:
                    continue
                cx, cy = center(pos)
                r = min(12.0, cell * 0.24)
                canvas.create_line(cx-r, cy-r, cx+r, cy+r, fill=palette["status.failed"], width=3)
                canvas.create_line(cx+r, cy-r, cx-r, cy+r, fill=palette["status.failed"], width=3)

        positions = {}
        if isinstance(tick.objective_world, dict):
            raw_positions = tick.objective_world.get("agent_positions")
            if isinstance(raw_positions, dict):
                positions = raw_positions
        if not positions and tick.objective_position is not None:
            positions = {tick.agent_id: list(tick.objective_position)}
        for aid, raw in sorted(positions.items()):
            try:
                pos = (int(raw[0]), int(raw[1]))
            except Exception:
                continue
            cx, cy = center(pos)
            r = min(12.0, cell * 0.20)
            selected = self.selected == ("agent", aid)
            focused = aid == tick.agent_id
            outline = (
                palette["focus.ring"]
                if selected or focused
                else palette["chart.1"]
            )
            fill = palette["text.primary"] if focused else palette["surface.control"]
            canvas.create_oval(
                cx-r, cy-r, cx+r, cy+r,
                fill=fill, outline=outline, width=3,
            )
            canvas.create_text(
                cx, cy - r - 8,
                text=str(aid),
                fill=palette["text.secondary"],
                font=("TkDefaultFont", 7),
            )
            self._hit_regions.append((cx, cy, max(14.0, r + 5), "agent", aid))

        canvas.create_text(
            12, 12, anchor="nw",
            text="● agent   shapes = objective geometry   ◇ memory   ⇢ displacement",
            fill=palette["text.secondary"], font=("TkDefaultFont", 8, "bold"),
        )

    @staticmethod
    def _viewport(canvas: Any) -> tuple[float, float]:
        return max(420.0, float(canvas.winfo_width())), max(330.0, float(canvas.winfo_height()))

    @staticmethod
    def _draw_shape(canvas: Any, shape: str, cx: float, cy: float, r: float, fill: str, outline: str) -> None:
        if shape == "circle":
            canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=fill, outline=outline, width=2)
        elif shape == "square":
            canvas.create_rectangle(cx-r, cy-r, cx+r, cy+r, fill=fill, outline=outline, width=2)
        elif shape == "triangle":
            canvas.create_polygon(cx, cy-r, cx+r, cy+r, cx-r, cy+r, fill=fill, outline=outline, width=2)
        elif shape == "diamond":
            canvas.create_polygon(cx, cy-r, cx+r, cy, cx, cy+r, cx-r, cy, fill=fill, outline=outline, width=2)
        else:
            points = []
            for dx, dy in ((0,-1),(.87,-.5),(.87,.5),(0,1),(-.87,.5),(-.87,-.5)):
                points.extend((cx+dx*r, cy+dy*r))
            canvas.create_polygon(*points, fill=fill, outline=outline, width=2)


def _position(value: Any) -> tuple[int, int] | None:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(item, int) for item in value)
    ):
        return int(value[0]), int(value[1])
    return None


# Update 4.7.1 — Observer-only probe object accent (no social labels).
def probe_object_ids_from_receipts(receipts: dict | None) -> list[str]:
    if not isinstance(receipts, dict):
        return []
    rows = receipts.get("cross_agent_trace_v471") or []
    out: list[str] = []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("kind") == "INTERVENTION":
                # object implied by experiment config; receipt may omit id
                pass
    return out

