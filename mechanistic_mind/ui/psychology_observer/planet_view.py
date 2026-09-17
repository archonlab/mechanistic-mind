"""Planet field canvas renderer for Psychology Observer (MM-OBS-REDESIGN-1).

Same-size frames reuse Canvas rectangle items (itemconfig) instead of
delete-all rebuild. Geometry changes trigger a full rebuild.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from .map_view import MapCamera
from .planet_model import (
    FIELD_LAYERS,
    PlanetDisplayState,
    cell_inspector,
    field_array,
    field_minmax,
    format_boundary_panel,
    format_world_status,
)


def _lerp_hex(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, float(t)))

    def rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    ra, ga, ba = rgb(a)
    rb, gb, bb = rgb(b)
    return "#{:02x}{:02x}{:02x}".format(
        int(ra + (rb - ra) * t),
        int(ga + (gb - ga) * t),
        int(ba + (bb - ba) * t),
    )


def colorize(value: float, vmin: float, vmax: float, palette: Mapping[str, str]) -> str:
    if not np.isfinite(value):
        return palette["cell.quiet"]
    span = vmax - vmin
    if abs(span) < 1e-15:
        t = 0.5
    else:
        t = (value - vmin) / span
    if t < 0.5:
        return _lerp_hex(palette["cell.quiet"], palette["chart.4"], t * 2.0)
    return _lerp_hex(palette["chart.4"], palette["chart.3"], (t - 0.5) * 2.0)


@dataclass
class PlanetFieldRenderer:
    camera: MapCamera = field(default_factory=MapCamera)
    layer: str = "M0"
    show_boundary_overlay: bool = True
    selected_cell: tuple[int, int] | None = None  # (y, x)
    _world_size: tuple[int, int] | None = None
    _last_display: PlanetDisplayState | None = None
    # render cache
    _cell_items: list[list[int]] | None = None  # [y][x] -> canvas id
    _boundary_items: dict[tuple[int, int], int] = field(default_factory=dict)
    _arrow_items: list[int] = field(default_factory=list)
    _legend_items: list[int] = field(default_factory=list)
    _selection_item: int | None = None
    _cached_geom: tuple[int, int] | None = None
    _cache_canvas_id: int | None = None
    stats_created: int = 0
    stats_reused_frames: int = 0
    stats_last_frame_creates: int = 0

    def set_layer(self, layer: str) -> None:
        if layer not in FIELD_LAYERS:
            raise KeyError(layer)
        self.layer = layer

    def invalidate_cache(self, canvas: Any | None = None) -> None:
        self._cell_items = None
        self._boundary_items = {}
        self._arrow_items = []
        self._legend_items = []
        self._selection_item = None
        self._cached_geom = None
        if canvas is not None:
            try:
                canvas.delete("all")
            except Exception:
                pass

    def fit(self, canvas: Any, display: PlanetDisplayState) -> None:
        viewport = self._viewport(canvas)
        size = (display.width, display.height)
        self.camera.fit(viewport=viewport, world_size=size)
        self._world_size = size
        self.invalidate_cache(canvas)

    def _viewport(self, canvas: Any) -> tuple[float, float]:
        canvas.update_idletasks()
        return max(1.0, float(canvas.winfo_width())), max(1.0, float(canvas.winfo_height()))

    def screen_to_cell(
        self,
        point: tuple[float, float],
        *,
        viewport: tuple[float, float],
        display: PlanetDisplayState,
    ) -> tuple[int, int]:
        wx, wy = self.camera.screen_to_world(
            point, viewport=viewport, world_size=(display.width, display.height)
        )
        cx = int(np.floor(wx + 0.5)) % display.width
        cy = int(np.floor(wy + 0.5)) % display.height
        return cy, cx

    def _ensure_cells(
        self,
        canvas: Any,
        display: PlanetDisplayState,
        viewport: tuple[float, float],
    ) -> bool:
        """Create cell rectangles if needed. Returns True if freshly created."""
        geom = (display.height, display.width)
        canvas_id = id(canvas)
        world_size = (display.width, display.height)
        if (
            self._cell_items is not None
            and self._cached_geom == geom
            and self._cache_canvas_id == canvas_id
        ):
            return False
        canvas.delete("all")
        self._boundary_items = {}
        self._arrow_items = []
        self._legend_items = []
        self._selection_item = None
        cell = self.camera.cell_px
        half = cell / 2
        items: list[list[int]] = []
        created = 0
        for y in range(display.height):
            row: list[int] = []
            for x in range(display.width):
                cx, cy = self.camera.world_to_screen(
                    (x, y), viewport=viewport, world_size=world_size
                )
                iid = canvas.create_rectangle(
                    cx - half,
                    cy - half,
                    cx + half,
                    cy + half,
                    fill="#000000",
                    outline="#000000",
                    width=1,
                    tags=("planet_cell",),
                )
                row.append(iid)
                created += 1
            items.append(row)
        self._cell_items = items
        self._cached_geom = geom
        self._cache_canvas_id = canvas_id
        self.stats_created += created
        self.stats_last_frame_creates = created
        return True

    def draw(
        self,
        canvas: Any,
        display: PlanetDisplayState | None,
        palette: Mapping[str, str],
    ) -> None:
        viewport = self._viewport(canvas)
        self._last_display = display
        self.stats_last_frame_creates = 0
        if display is None:
            self.invalidate_cache(canvas)
            canvas.create_text(
                viewport[0] / 2,
                viewport[1] / 2,
                text="PHYSICAL WORLD NOT STARTED\nApply setup, then Run / Step / Reset",
                fill=palette["text.muted"],
                justify="center",
                font=("TkDefaultFont", 10, "bold"),
            )
            return

        world_size = (display.width, display.height)
        if self._world_size != world_size:
            self.fit(canvas, display)

        fresh = self._ensure_cells(canvas, display, viewport)
        if not fresh:
            self.stats_reused_frames += 1

        arr = field_array(display, self.layer)
        vmin, vmax = field_minmax(arr)
        assert self._cell_items is not None
        for y in range(display.height):
            for x in range(display.width):
                fill = colorize(float(arr[y, x]), vmin, vmax, palette)
                canvas.itemconfig(
                    self._cell_items[y][x],
                    fill=fill,
                    outline=palette["grid.line"],
                )

        # Boundary overlay: manage per-contact dashed rects
        b = display.boundary
        want: set[tuple[int, int]] = set()
        if self.show_boundary_overlay and b.enabled and b.contact_mask is not None:
            mask = b.contact_mask
            cell = self.camera.cell_px
            half = cell / 2
            inset = max(1.0, half * 0.82)
            for y in range(display.height):
                for x in range(display.width):
                    if not mask[y, x]:
                        continue
                    want.add((y, x))
                    cx, cy = self.camera.world_to_screen(
                        (x, y), viewport=viewport, world_size=world_size
                    )
                    if (y, x) in self._boundary_items:
                        canvas.coords(
                            self._boundary_items[(y, x)],
                            cx - inset,
                            cy - inset,
                            cx + inset,
                            cy + inset,
                        )
                        canvas.itemconfig(
                            self._boundary_items[(y, x)],
                            outline=palette["status.info"],
                        )
                    else:
                        iid = canvas.create_rectangle(
                            cx - inset,
                            cy - inset,
                            cx + inset,
                            cy + inset,
                            fill="",
                            outline=palette["status.info"],
                            width=2,
                            dash=(2, 2),
                            tags=("planet_boundary",),
                        )
                        self._boundary_items[(y, x)] = iid
                        self.stats_last_frame_creates += 1
        # remove stale boundary items
        for key in list(self._boundary_items):
            if key not in want:
                try:
                    canvas.delete(self._boundary_items.pop(key))
                except Exception:
                    self._boundary_items.pop(key, None)

        # Flow arrows: recreate lightly each Flow frame (sparse)
        for iid in self._arrow_items:
            try:
                canvas.delete(iid)
            except Exception:
                pass
        self._arrow_items = []
        if self.layer == "Flow":
            step = max(1, min(display.height, display.width) // 8)
            scale = self.camera.cell_px * 0.35
            for y in range(0, display.height, step):
                for x in range(0, display.width, step):
                    vx = float(display.vx[y, x])
                    vy = float(display.vy[y, x])
                    mag = (vx * vx + vy * vy) ** 0.5
                    if mag < 1e-9:
                        continue
                    cx, cy = self.camera.world_to_screen(
                        (x, y), viewport=viewport, world_size=world_size
                    )
                    dx = (vx / mag) * scale
                    dy = (vy / mag) * scale
                    iid = canvas.create_line(
                        cx,
                        cy,
                        cx + dx,
                        cy + dy,
                        fill=palette["text.primary"],
                        arrow="last",
                        width=1,
                        tags=("planet_arrow",),
                    )
                    self._arrow_items.append(iid)
                    self.stats_last_frame_creates += 1

        # selection
        if self._selection_item is not None:
            try:
                canvas.delete(self._selection_item)
            except Exception:
                pass
            self._selection_item = None
        if self.selected_cell is not None:
            sy, sx = self.selected_cell
            half = self.camera.cell_px / 2
            cx, cy = self.camera.world_to_screen(
                (sx, sy), viewport=viewport, world_size=world_size
            )
            self._selection_item = canvas.create_rectangle(
                cx - half,
                cy - half,
                cx + half,
                cy + half,
                outline=palette["focus.ring"],
                width=2,
                fill="",
                tags=("planet_selection",),
            )
            self.stats_last_frame_creates += 1

        # legend texts — recreate (2 items)
        for iid in self._legend_items:
            try:
                canvas.delete(iid)
            except Exception:
                pass
        self._legend_items = [
            canvas.create_text(
                10,
                12,
                anchor="nw",
                text=f"layer={self.layer}  min={vmin:.5g}  max={vmax:.5g}  tick={display.tick}",
                fill=palette["text.secondary"],
                font=("TkDefaultFont", 8, "bold"),
                tags=("planet_legend",),
            ),
            canvas.create_text(
                10,
                28,
                anchor="nw",
                text=(
                    "overlay: External Material Contact (dashed)"
                    if b.enabled
                    else "External Material Boundary: OFF"
                ),
                fill=palette["status.info"] if b.enabled else palette["text.muted"],
                font=("TkDefaultFont", 8),
                tags=("planet_legend",),
            ),
        ]
        self.stats_last_frame_creates += 2


def format_cell_inspector_text(display: PlanetDisplayState, y: int, x: int) -> str:
    info = cell_inspector(display, y, x)
    lines = [
        "CELL INSPECTOR (observer ground truth)",
        f"coords (y,x)=({info['y']},{info['x']})",
        f"T={info['T']:.8g}",
        f"M0={info['M0']:.8g}  M1={info['M1']}  M2={info['M2']}",
        f"vx={info['vx']:.8g}  vy={info['vy']:.8g}",
        f"u={info['u']:.8g}",
        f"boundary_contact={info['boundary_contact']}",
    ]
    if info["local_J"] is not None:
        lines.append(f"local_J (UI-derived)={info['local_J']}")
        lines.append(info["sign_convention"])
    lines.append(info["note"])
    return "\n".join(lines)


def world_and_boundary_text(display: PlanetDisplayState) -> str:
    return format_world_status(display) + "\n\n" + format_boundary_panel(display)
