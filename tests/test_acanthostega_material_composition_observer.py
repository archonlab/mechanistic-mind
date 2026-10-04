"""Observer/Analyzer integration for Acanthostega material composition merge."""
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BRING_TOGETHER,
    PRESET_ACANTHOSTEGA_COMPOSITION_MERGE,
)
from mechanistic_mind.physical_system.material_composition import MATERIAL_COMPOSITION_MERGE
from mechanistic_mind.scientific_v3.material_summary import summarize_material_transformations
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def test_observer_apply_and_mechanism_catalog_are_stage_scoped():
    session = ObserverSession(SessionConfig(seed=17))
    session.apply_experiment({
        "public_preset": PRESET_ACANTHOSTEGA_COMPOSITION_MERGE,
        "agent_count": 1,
        "cognition_enabled": False,
    })
    runtime = session.runtime
    assert runtime.config.public_preset == PRESET_ACANTHOSTEGA_COMPOSITION_MERGE
    assert "COMBINE" in runtime.cognition["available_actions"]
    mechanisms = {row["id"]: row["enabled"] for row in runtime.mechanisms()["mechanisms"]}
    assert mechanisms[MATERIAL_COMPOSITION_MERGE] is True

    session.apply_experiment({
        "public_preset": PRESET_ACANTHOSTEGA_BRING_TOGETHER,
        "agent_count": 1,
        "cognition_enabled": False,
    })
    old = session.runtime
    assert "COMBINE" not in old.cognition["available_actions"]
    old_mechanisms = {row["id"]: row["enabled"] for row in old.mechanisms()["mechanisms"]}
    assert MATERIAL_COMPOSITION_MERGE not in old_mechanisms or old_mechanisms[MATERIAL_COMPOSITION_MERGE] is False


def test_analyzer_material_summary_reconstructs_conservation():
    event = {
        "type": "MATERIAL_COMBINE_COMMITTED",
        "tick": 12,
        "evidence": {
            "tick": 12,
            "outcome": "MERGE_COMMITTED",
            "transformation_id": "material-merge-000000012-agent_0-resource-000001",
            "left_input": {"object_id": "resource-000001", "mass": 1.0},
            "right_input": {"object_id": "resource-000002", "mass": 2.0},
            "output": {"object_id": "resource-000001", "mass": 3.0},
            "mass_residual": 0.0,
            "quantity_residual": 0.0,
            "component_residuals": {"component_a": 0.0, "component_b": 0.0},
        },
    }
    summary = summarize_material_transformations([event])
    assert summary["combine_attempts"] == 1
    assert summary["combine_committed"] == 1
    assert summary["max_abs_mass_residual"] == 0.0
    assert summary["semantic_recipes_present"] is False
