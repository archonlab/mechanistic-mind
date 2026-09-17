from __future__ import annotations

from mechanistic_mind.agent import Observation
from mechanistic_mind.psyche.perceptual_cue import (
    CUE_LEGACY_ONLY,
    CUE_PERCEPTUAL_ENABLED,
    cue_uptake_summary,
    extract_bounded_perceptual_features,
    perceptual_feature_tokens,
)
from mechanistic_mind.psyche.sensorimotor import (
    SensorimotorConfig,
    context_cue,
    cue_bucket,
    cue_signature,
)


def _physical_perception(*, distant_partial: bool = True) -> dict:
    distant_feats = {"bearing_bin": 3.0, "edge": 1.0}
    if distant_partial:
        # fewer features than near-contact — information loss preserved via bands
        distant_packet = {
            "features": distant_feats,
            "feature_count": 2,
            "bearing_bin": 3.0,
        }
    else:
        distant_packet = {
            "features": {**distant_feats, "a": 1, "b": 2, "c": 3, "d": 4},
            "feature_count": 8,
            "bearing_bin": 3.0,
        }
    return {
        "mode": "MULTI_CHANNEL",
        "channels": {
            "DISTANT_STRUCTURAL": [distant_packet],
            "PASSIVE_WAVE": [
                {"frequency": 0.8, "features": {"amp": 0.4}, "feature_count": 1}
            ],
            "ACTIVE_RETURN": [],
            "NEAR_CONTACT": [
                {
                    "features": {"hardness": 0.9, "temp": 0.2, "grip": 0.5},
                    "feature_count": 6,
                }
            ],
        },
        "summary": {
            "DISTANT_STRUCTURAL": {
                "active_count": 1,
                "strength_sum": 0.4,
                "feature_diversity": 2,
                "mean_feature_count": 2.0,
            },
            "PASSIVE_WAVE": {
                "active_count": 1,
                "strength_sum": 0.8,
                "feature_diversity": 1,
                "mean_feature_count": 1.0,
            },
            "ACTIVE_RETURN": {
                "active_count": 0,
                "strength_sum": 0.0,
                "feature_diversity": 0,
                "mean_feature_count": 0.0,
            },
            "NEAR_CONTACT": {
                "active_count": 1,
                "strength_sum": 1.2,
                "feature_diversity": 6,
                "mean_feature_count": 6.0,
            },
        },
        "delta": {
            "DISTANT_STRUCTURAL": {"strength_sum_delta": 0.1, "active_count_delta": 0},
        },
    }


def _obs(pp: dict | None = None) -> dict:
    return {
        "position": [2, 2],
        "visible_objects": [
            {
                "id": "OBJ-X",
                "cue_signature": "CUE-X",
                "relative_offset": [1, 0],
                "interaction_state": "FREE",
            }
        ],
        "available_actions": ["WAIT", "MOVE:3,2", "EMIT"],
        "interoception": {
            "energy_signal": 0.7,
            "hydration_signal": 0.6,
            "fatigue_signal": 0.2,
        },
        "physical_perception": pp if pp is not None else _physical_perception(),
    }


def test_legacy_cue_excludes_perceptual_features():
    cue = context_cue(_obs(), cue_mode=CUE_LEGACY_ONLY)
    assert cue["cue_mode"] == CUE_LEGACY_ONLY
    assert cue["perceptual_features"] == ()
    assert cue["visible"]


def test_perceptual_cue_includes_bounded_tokens():
    pp = _physical_perception()
    cue = context_cue(_obs(pp), cue_mode=CUE_PERCEPTUAL_ENABLED)
    assert cue["cue_mode"] == CUE_PERCEPTUAL_ENABLED
    assert len(cue["perceptual_features"]) > 0
    tokens = perceptual_feature_tokens(pp)
    assert set(cue["perceptual_features"]) == set(tokens)
    # no raw object ids in perceptual tokens
    joined = " ".join(tokens)
    assert "OBJ-X" not in joined
    assert "CUE-X" not in joined


def test_legacy_vs_perceptual_signatures_differ():
    obs = _obs()
    legacy = context_cue(obs, cue_mode=CUE_LEGACY_ONLY)
    perceptual = context_cue(obs, cue_mode=CUE_PERCEPTUAL_ENABLED)
    assert cue_signature(legacy) != cue_signature(perceptual)
    assert cue_bucket(legacy) != cue_bucket(perceptual)


def test_deterministic_feature_extraction():
    pp = _physical_perception()
    a = extract_bounded_perceptual_features(pp)
    b = extract_bounded_perceptual_features(pp)
    assert a == b
    assert perceptual_feature_tokens(pp) == perceptual_feature_tokens(pp)


def test_distant_partial_preserved_as_low_band():
    partial = _physical_perception(distant_partial=True)
    rich = _physical_perception(distant_partial=False)
    # force rich summary mean_feature_count high
    rich["summary"]["DISTANT_STRUCTURAL"]["mean_feature_count"] = 8.0
    rich["summary"]["DISTANT_STRUCTURAL"]["feature_diversity"] = 8
    partial_tokens = perceptual_feature_tokens(partial)
    rich_tokens = perceptual_feature_tokens(rich)
    assert any("partial" in tok for tok in partial_tokens)
    # partial and rich should not be identical token sets
    assert set(partial_tokens) != set(rich_tokens)


def test_cue_uptake_summary_modes():
    pp = _physical_perception()
    legacy_cue = context_cue(_obs(pp), cue_mode=CUE_LEGACY_ONLY)
    perc_cue = context_cue(_obs(pp), cue_mode=CUE_PERCEPTUAL_ENABLED)
    legacy_u = cue_uptake_summary(
        physical_perception=pp, cue=legacy_cue, mode=CUE_LEGACY_ONLY
    )
    perc_u = cue_uptake_summary(
        physical_perception=pp, cue=perc_cue, mode=CUE_PERCEPTUAL_ENABLED
    )
    assert legacy_u["channels"]["DISTANT_STRUCTURAL"]["AVAILABLE_TO_SENSOR"] == "yes"
    assert legacy_u["channels"]["DISTANT_STRUCTURAL"]["REPRESENTED_IN_CUE"] == "n/a_legacy"
    assert perc_u["channels"]["DISTANT_STRUCTURAL"]["REPRESENTED_IN_CUE"] == "yes"
    assert perc_u["channels"]["ACTIVE_RETURN"]["AVAILABLE_TO_SENSOR"] == "no"
    assert perc_u["perceptual_token_count"] > 0


def test_sensorimotor_config_default_legacy():
    assert SensorimotorConfig().cue_mode == CUE_LEGACY_ONLY
