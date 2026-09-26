"""Observer Apply World wiring for PE cold history eviction. Tiny runtime only."""
from __future__ import annotations

from mechanistic_mind.research import pe_cold_archive as cold
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _applied(frame) -> bool:
    block = (frame.get("experiment") or {}).get("pe_cold_history_eviction") or {}
    if "applied" in block:
        return bool(block["applied"])
    return bool(((frame.get("experiment") or {}).get("runtime") or {}).get("pe_cold_history_eviction"))


def test_apply_world_pe_cold_eviction_on_off_roundtrip():
    prev_a, prev_e = cold.cold_archive_enabled(), cold.cold_eviction_enabled()
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, pe_cold_history_eviction=True))
    try:
        world = {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"}
        off = s.apply_experiment({"seed": 17, "pe_cold_history_eviction": False, "world": world})
        assert off["control_receipt"]["accepted"]
        assert off["control_receipt"]["requires_reset"]
        assert _applied(off) is False
        assert cold.cold_eviction_enabled() is False
        assert s.config.pe_cold_history_eviction is False
        s.step(2)
        assert cold.cold_eviction_enabled() is False
        assert _applied(s.current_frame()) is False

        on = s.apply_experiment({"seed": 17, "pe_cold_history_eviction": True, "world": world})
        assert _applied(on) is True
        assert cold.cold_eviction_enabled() is True
        assert s.config.pe_cold_history_eviction is True
        assert on["experiment"]["pe_cold_history_eviction"]["requested"] is True
        s.step(2)
        assert cold.cold_eviction_enabled() is True
        assert _applied(s.current_frame()) is True

        off2 = s.apply_experiment({"seed": 17, "pe_cold_history_eviction": False, "world": world})
        assert _applied(off2) is False
        assert cold.cold_eviction_enabled() is False
        s.step(2)
        assert _applied(s.current_frame()) is False
    finally:
        pe.set_cold_archive(prev_a)
        pe.set_cold_eviction(prev_e)


def test_session_default_matches_beta31_canonical_on():
    assert SessionConfig().pe_cold_history_eviction is True
    src = __import__("pathlib").Path(__file__).resolve().parents[1] / "mechanistic_mind/research/pe_cold_archive.py"
    head = src.read_text().split("def set_cold_archive")[0]
    assert "_COLD_EVICT = True" in head
