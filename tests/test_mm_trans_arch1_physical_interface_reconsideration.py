"""MM-TRANS-ARCH-1 — freeze + counterfactual contracts; no production edits."""
from __future__ import annotations
from pathlib import Path
import json, hashlib
import numpy as np

ROOT = Path("results/mm_trans_arch1_physical_interface_reconsideration")

from mechanistic_mind.internal_substrate import default_internal_substrate_config, run_world_body_substrate
from mechanistic_mind.physical_body import default_physical_body2_config
from mechanistic_mind.planet.config import default_planet_config


def test_pack():
    for n in ("FINAL_REPORT.md", "ARCHITECTURAL_VERDICT.md", "H4_EROSION_MECHANISM.md", "experiment_summary.json"):
        assert (ROOT / n).is_file()


def test_freeze_and_defaults():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    files = sorted(Path("mechanistic_mind/planet").glob("*.py"))
    files += sorted(Path("mechanistic_mind/physical_body").glob("*.py"))
    files += sorted(Path("mechanistic_mind/internal_substrate").glob("*.py"))
    h = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    assert h == s["freeze0"]
    assert default_internal_substrate_config().dim == 4
    assert default_internal_substrate_config().backreact_core is True
    assert default_physical_body2_config().core_exchange == 0.015
    assert default_planet_config().F_baseline == 0.08


def test_h4_counterfactuals():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    h = s["h4_table"]
    assert h["body_only"]["dB_total"] > 0.005
    assert h["full_S"]["dB_total"] < 0.001
    assert abs(h["forward_only"]["dB_total"] - h["body_only"]["dB_total"]) < 1e-6
    assert h["no_backreact_core"]["dB_total"] > 0.005
    assert h["no_backreact_thermal"]["dB_total"] < 0.001


def test_t2_forward_only():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["T2"]["full"] > 0.05
    assert s["T2"]["forward_only"] > 0.05
    assert s["T2"]["zero"] == 0.0


def test_no_world_access_in_substrate():
    dyn = Path("mechanistic_mind/internal_substrate/dynamics.py").read_text()
    assert "PlanetState" not in dyn
    assert "step_planet" not in dyn
    assert "from mechanistic_mind.body" not in dyn
    assert "embodied_integration" not in dyn
