"""MM-TRANS-2 — zero-production diagnostic contracts."""
from __future__ import annotations
from pathlib import Path
import json, hashlib
import numpy as np

ROOT = Path("results/mm_trans2_body_history_path_decomposition")

from mechanistic_mind.physical_body import default_physical_body2_config
from mechanistic_mind.internal_substrate import default_internal_substrate_config, run_world_body_substrate
from mechanistic_mind.planet.config import default_planet_config


def test_pack_exists():
    for n in ("FINAL_REPORT.md", "NEXT_FRONTIER.md", "experiment_summary.json",
              "ACTUAL_HISTORY_TO_S_GRAPH.md", "PRODUCTION_FREEZE_AUDIT.md",
              "HISTORY_CONTRACT_COMPARISON.md", "FIRST_CAUSAL_ATTENUATION.md"):
        assert (ROOT / n).is_file()


def test_outcome_and_t2():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["T2"]["full"] > 0.05
    assert s["T2"]["zero"] == 0.0
    assert s["t5_natural"] is False
    assert s["h4_noS"]["matched_dB_total"] > 0.005
    assert s["h4_withS"]["matched_dB_total"] < s["h4_noS"]["matched_dB_total"] * 0.1


def test_production_defaults_frozen():
    assert default_planet_config().F_baseline == 0.08
    assert default_physical_body2_config().core_exchange == 0.015
    assert default_internal_substrate_config().leak == 0.04
    assert default_internal_substrate_config().core_exchange == 0.02
    assert default_internal_substrate_config().backreact_core is True


def test_freeze_hashes_match_summary():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    files = sorted(Path("mechanistic_mind/planet").glob("*.py"))
    files += sorted(Path("mechanistic_mind/physical_body").glob("*.py"))
    files += sorted(Path("mechanistic_mind/internal_substrate").glob("*.py"))
    h = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    assert h == s["freeze0"]


def test_identical_history_floor():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["floor"]["identical_history_dS"] == 0.0


def test_no_new_production_semantics():
    src = "".join(p.read_text() for p in Path("mechanistic_mind/internal_substrate").glob("*.py"))
    assert "from mechanistic_mind.body" not in src
    assert "embodied_integration" not in src
    assert "mechanistic_mind.psyche" not in src
    assert "history_id" not in src
    assert "memory_signal" not in src
    assert "production_inputs" not in src
    assert "energy_reserve" not in src

def test_zero_couple_still_silent():
    from mechanistic_mind.internal_substrate import InternalSubstrateConfig
    sc = InternalSubstrateConfig(thermal_enabled=False, surface_enabled=False, core_enabled=False, mech_enabled=False)
    r = run_world_body_substrate(seed=17, horizon=40, snapshot_every=40, substrate_config=sc)
    assert float(np.linalg.norm(r["substrate"].s)) == 0.0
