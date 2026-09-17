"""MM-BODY-1 — physical body without psyche."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np

from mechanistic_mind.physical_body import (
    PhysicalBodyConfig,
    initialize_physical_body,
    run_world_with_body,
    step_physical_body,
)
from mechanistic_mind.planet.config import PlanetConfig
from mechanistic_mind.planet.state import initialize_planet
from mechanistic_mind.planet.dynamics import step_planet

ROOT = Path(__file__).resolve().parents[1] / "results" / "mm_body1_physical_body_without_psyche"


def test_pack_and_outcome():
    assert (ROOT / "FINAL_REPORT.md").exists()
    text = (ROOT / "FINAL_REPORT.md").read_text()
    assert "BODY_PHYSICALLY_EMBEDDED" in text or "BODY_WITH_" in text
    assert "psyche present? NO" in text


def test_no_psyche_imports():
    import mechanistic_mind.physical_body.dynamics as d
    src = Path(d.__file__).read_text()
    for bad in ("energy_reserve", "hydration", "fatigue", "reward", "embodied_integration", "sensorimotor"):
        assert bad not in src
    # "receptor" substring may appear in comments about absence; ensure no import
    assert "embodied_integration" not in src
    assert "from mechanistic_mind.body" not in src


def test_thermal_exchange_and_inertia():
    r = run_world_with_body(seed=17, horizon=80, snapshot_every=20)
    assert abs(r["body_series"][-1]["T"] - r["body_series"][0]["T"]) > 1e-4
    # not identical to a hard copy expectation: lag exists in summary
    data = json.loads((ROOT / "experiment_summary.json").read_text())
    assert data["best_lag"] >= 1


def test_material_bidirectional_and_conservation_exchange_only():
    pc = PlanetConfig(
        reaction_enabled=False, phase_enabled=False, diffusion_enabled=False,
        advection_enabled=False, wave_enabled=False, flow_enabled=False,
        forcing_enabled=False, thermal_from_forcing=False, cool_rate=0.0,
        heat_gain=0.0, kappa_base=0.0, F_irregular_amp=0.0,
    )
    bc = PhysicalBodyConfig(reaction_enabled=False, mechanical_enabled=False)
    planet = initialize_planet(pc, seed=5)
    body = initialize_physical_body(bc, width=pc.width, height=pc.height)
    iy, ix = body.cell(pc.width, pc.height)
    planet.M[:, iy, ix] = np.array([0.8, 0.6, 0.1])
    tot0 = float(planet.M.sum() + body.B.sum())
    for _ in range(50):
        step_planet(planet, pc, seed=5)
        step_physical_body(body, planet, bc)
    assert abs(float(planet.M.sum() + body.B.sum()) - tot0) < 1e-9
    assert body.matter_in + body.matter_out > 0.0


def test_internal_reaction_bounded():
    r = run_world_with_body(seed=17, horizon=100, snapshot_every=100)
    assert r["body_series"][-1]["react_consumed"] >= 0.0
    assert all(0.0 <= x <= 2.0 for x in r["body_series"][-1]["B"])


def test_passive_displacement_not_action():
    r = run_world_with_body(seed=17, horizon=100, snapshot_every=20)
    # position may change without any Action API
    moved = (r["body_series"][-1]["x"] != r["body_series"][0]["x"]) or (
        r["body_series"][-1]["y"] != r["body_series"][0]["y"]
    )
    assert moved
    import mechanistic_mind.physical_body.dynamics as d
    assert "Action" not in Path(d.__file__).read_text()


def test_forcing_phase_not_in_body_state():
    body = initialize_physical_body()
    keys = body.snapshot().keys()
    assert "forcing_phase" not in keys and "day" not in keys and "season" not in keys


def test_world1_planet_untouched_defaults():
    from mechanistic_mind.planet.config import default_planet_config
    c = default_planet_config()
    assert c.F_fast_period == 40 and c.F_slow_period == 400
    assert c.width == 32


def test_old_organism_body_still_importable():
    from mechanistic_mind.body.models import BodyState
    b = BodyState()
    assert hasattr(b, "energy_reserve")  # old path preserved; not used by BODY-1
