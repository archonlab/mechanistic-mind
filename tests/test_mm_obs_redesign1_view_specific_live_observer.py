"""MM-OBS-REDESIGN-1 — view-specific chrome, continuous==manual, render reuse."""
from __future__ import annotations

import hashlib
import time

import numpy as np
import pytest

from mechanistic_mind.planet.config import PlanetConfig
from mechanistic_mind.ui.psychology_observer.cli import headless_contract
from mechanistic_mind.ui.psychology_observer.planet_model import FIELD_LAYERS
from mechanistic_mind.ui.psychology_observer.planet_session import PlanetInspectionSession
from mechanistic_mind.ui.psychology_observer.planet_view import PlanetFieldRenderer


def _phys_hash(st) -> str:
    h = hashlib.sha256()
    for arr in (st.T, st.M, st.vx, st.vy, st.u, st.u_prev, st.capacity, st.conductivity):
        h.update(np.ascontiguousarray(arr).tobytes())
    h.update(int(st.tick).to_bytes(8, "little"))
    return h.hexdigest()


class FakeCanvas:
    def __init__(self):
        self._next = 1
        self.items: dict = {}
        self._w = 640
        self._h = 480

    def update_idletasks(self):
        return None

    def winfo_width(self):
        return self._w

    def winfo_height(self):
        return self._h

    def delete(self, *a):
        if a and a[0] == "all":
            self.items.clear()
            return
        for x in a:
            self.items.pop(x, None)

    def create_rectangle(self, *a, **k):
        i = self._next
        self._next += 1
        self.items[i] = ("rect", dict(k))
        return i

    def create_line(self, *a, **k):
        i = self._next
        self._next += 1
        self.items[i] = ("line", dict(k))
        return i

    def create_text(self, *a, **k):
        i = self._next
        self._next += 1
        self.items[i] = ("text", dict(k))
        return i

    def itemconfig(self, iid, **k):
        if iid in self.items:
            kind, old = self.items[iid]
            old.update(k)
            self.items[iid] = (kind, old)

    def coords(self, iid, *a):
        return None


PAL = {
    "cell.quiet": "#18314a",
    "chart.4": "#69bfff",
    "chart.3": "#ffa148",
    "grid.line": "#132a3d",
    "text.secondary": "#c5d1dc",
    "text.muted": "#9bafc1",
    "text.primary": "#f4f7fb",
    "status.info": "#63a9ff",
    "focus.ring": "#b29cff",
}


def _session(seed=17, boundary=False):
    s = PlanetInspectionSession(seed=seed, config=PlanetConfig(F_irregular_amp=0.0))
    s.reset()
    if boundary:
        mask = np.zeros((32, 32), dtype=bool)
        mask[2:6, 2:6] = True
        s.apply_boundary_fixture(enabled=True, contact_mask=mask, K=0.16, M_ext=[0.25, 0.25, 0.25])
    return s


def test_headless_contract_still_has_worlds_and_physical():
    c = headless_contract()
    assert "physical_world" in c["view_modes"]
    assert "organism" in c["worlds"]
    assert "contextual-objects" in c["worlds"]


def test_render_reuses_cells_same_geometry():
    s = _session()
    r = PlanetFieldRenderer()
    c = FakeCanvas()
    r.draw(c, s.display, PAL)
    first = r.stats_last_frame_creates
    s.step(3)
    r.draw(c, s.display, PAL)
    assert r.stats_reused_frames >= 1
    assert r.stats_last_frame_creates < first
    assert r.stats_last_frame_creates <= 64  # legends/arrows/selection only


def test_layer_switch_does_not_step():
    s = _session()
    tick0 = s.display.tick
    r = PlanetFieldRenderer()
    c = FakeCanvas()
    for layer in FIELD_LAYERS:
        r.layer = layer
        r.draw(c, s.display, PAL)
    assert s.display.tick == tick0


def test_manual_n_equals_continuous_batch_off():
    """Continuous mode = repeated step(1); equivalence is step loops."""
    n = 50
    a = _session(17, False)
    b = _session(17, False)
    for _ in range(n):
        a.step(1)
    # simulate continuous batches of varying size summing to n
    left = n
    while left:
        batch = min(7, left)
        b.step(batch)
        left -= batch
    assert _phys_hash(a._state) == _phys_hash(b._state)


def test_manual_n_equals_continuous_batch_on():
    n = 50
    a = _session(23, True)
    b = _session(23, True)
    for _ in range(n):
        a.step(1)
    left = n
    while left:
        batch = min(11, left)
        b.step(batch)
        left -= batch
    assert _phys_hash(a._state) == _phys_hash(b._state)
    assert np.allclose(a._state.external_material_boundary.cum_import, b._state.external_material_boundary.cum_import)
    assert np.allclose(a._state.external_material_boundary.cum_export, b._state.external_material_boundary.cum_export)
    assert a._state.external_material_boundary.last_residual_max == pytest.approx(
        b._state.external_material_boundary.last_residual_max
    )


def test_scheduler_helpers_exist_on_app():
    from mechanistic_mind.ui.psychology_observer.app import PsychologyObserverApp

    for name in (
        "_planet_run",
        "_planet_pause",
        "_planet_step",
        "_planet_reset",
        "_planet_tick_batch",
        "_apply_view_chrome",
        "_register_view_chrome",
    ):
        assert hasattr(PsychologyObserverApp, name)


def test_no_live_physics_editors():
    from mechanistic_mind.ui.psychology_observer.app import PsychologyObserverApp
    c = PsychologyObserverApp.observer_mm_obs1_read_only_contract(PsychologyObserverApp)
    assert c["has_live_K_slider"] is False
    assert c["has_live_mask_paint"] is False
    assert c["has_live_M_ext_slider"] is False
    src = open("mechanistic_mind/ui/psychology_observer/app.py").read()
    assert "configure_external_material_boundary(" not in src


def test_selected_cell_preserved_across_draws():
    s = _session()
    r = PlanetFieldRenderer()
    r.selected_cell = (4, 5)
    c = FakeCanvas()
    r.draw(c, s.display, PAL)
    s.step(2)
    r.draw(c, s.display, PAL)
    assert r.selected_cell == (4, 5)


def test_geometry_change_rebuilds_cache():
    s = _session()
    r = PlanetFieldRenderer()
    c = FakeCanvas()
    r.draw(c, s.display, PAL)
    # force geom change via invalidate
    r.invalidate_cache(c)
    r.draw(c, s.display, PAL)
    assert r.stats_last_frame_creates >= 1024


def test_off_baseline_hash_noninterference():
    s = _session(17, False)
    for _ in range(200):
        s.step(1)
    assert _phys_hash(s._state) == "82a760fb5718518c77ece288bc636728f63552d47d137da4e65be070c23654ad"


def test_planet_batch_wall_bound_config():
    # Documented defaults exist on class/init pattern via source
    src = open("mechanistic_mind/ui/psychology_observer/app.py").read()
    assert "_planet_render_interval_s = 0.05" in src
    assert "_planet_batch_wall_ms = 12.0" in src
    assert "_planet_batch_max_ticks = 48" in src
