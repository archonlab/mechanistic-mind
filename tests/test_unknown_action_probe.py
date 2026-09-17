"""Unknown-action probe: detection only; selection unchanged; default OFF."""
from __future__ import annotations

from mechanistic_mind.physical_system import CognitionConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.unknown_action_probe import classify_unmodeled_actions
from mechanistic_mind.research import prospective_composition as pr


def _lock_wait(seed: int = 17, ticks: int = 25) -> PhysicalSystemRuntime:
    rt = PhysicalSystemRuntime(seed=seed)
    for _ in range(ticks):
        rt.step()
    return rt


def test_default_probe_flag_off():
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.cognition.unknown_action_physical_probe is False
    rt.step()
    probe = (rt.cognition.get("last_selection") or {}).get("unknown_action_probe") or {}
    assert probe.get("enabled") is False
    assert probe.get("selected_probe_action") is None


def test_classifier_uses_match_absence_only():
    rt = _lock_wait()
    obs = rt.last_agent_observation or rt.agent_observation()
    sel = rt.cognition.get("last_selection") or {}
    supported = list((sel.get("competition") or {}).get("supported_actions") or [])
    cls = classify_unmodeled_actions(
        store=rt.cognition["prospection"],
        observation=obs,
        supported_actions=supported,
    )
    assert "WAIT" in cls["modeled_first_actions"]
    assert "MOVE:E" in cls["unmodeled_first_actions"]
    assert cls["arbitration"] == "NOT_IMPLEMENTED_DESIGN_BOUNDARY"


def test_flag_on_does_not_change_selection():
    off, on = PhysicalSystemRuntime(seed=17), PhysicalSystemRuntime(seed=17)
    on.config.cognition.unknown_action_physical_probe = True
    on.cognition["config"] = on.config.cognition.to_dict()
    seq_off, seq_on = [], []
    for _ in range(40):
        off.step()
        on.step()
        seq_off.append(off.last_selected_action)
        seq_on.append(on.last_selected_action)
    assert seq_off == seq_on
    probe = (on.cognition.get("last_selection") or {}).get("unknown_action_probe") or {}
    assert probe.get("enabled") is True
    assert probe.get("selection_effect") == "NONE_DESIGN_BOUNDARY"
    assert probe.get("selected_probe_action") is None
    if (on.cognition.get("last_selection") or {}).get("source") == "PROSPECTIVE_SCENARIO":
        assert "WAIT" in (probe.get("modeled_first_actions") or [])
        assert "MOVE:E" in (probe.get("unmodeled_first_actions") or [])


def test_classifier_self_extinguishes_after_ordinary_experience():
    rt = _lock_wait()
    obs = rt.agent_observation()
    before = classify_unmodeled_actions(
        store=rt.cognition["prospection"], observation=obs,
        supported_actions=["WAIT"],
    )
    assert "MOVE:E" in before["unmodeled_first_actions"]
    # Ordinary writes only — harness forced physics, not a live probe rule.
    snap_obs = rt.agent_observation()
    rt.step_forced_action("MOVE:E")
    cons = rt.agent_observation()
    for i in range(3):
        pr.learn_transition(
            rt.cognition["prospection"], tick=500 + i,
            antecedent=snap_obs, action="MOVE:E", consequent=cons,
        )
    after = classify_unmodeled_actions(
        store=rt.cognition["prospection"], observation=snap_obs,
        supported_actions=["WAIT"],
    )
    assert "MOVE:E" not in after["unmodeled_first_actions"]
    assert "MOVE:E" in after["modeled_first_actions"]


def test_set_mechanism_toggles_detection_only():
    rt = PhysicalSystemRuntime(seed=17)
    rt.set_mechanism("unknown_action_physical_probe", True)
    assert rt.config.cognition.unknown_action_physical_probe is True
    rt.step()
    assert (rt.cognition.get("last_selection") or {}).get("unknown_action_probe", {}).get("enabled") is True
    rt.set_mechanism("unknown_action_physical_probe", False)
    assert rt.config.cognition.unknown_action_physical_probe is False
