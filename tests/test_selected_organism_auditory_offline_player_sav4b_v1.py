"""SELECTED_ORGANISM_AUDITORY_OFFLINE_PLAYER_SAV4B_V1 — identity/privacy (0 ticks)."""
from __future__ import annotations

from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.selected_organism_auditory_offline_player_sav4b import (
    AUTHORITY,
    CAPABILITY,
    PROFILE,
    SCHEMA,
    profile_reference,
)

TICKS = 0


def test_identity_privacy_and_not_mechanism():
    assert SCHEMA == "SELECTED_ORGANISM_AUDITORY_OFFLINE_PLAYER_SAV4B_V1"
    assert CAPABILITY == "selected_organism_auditory_offline_playback"
    assert PROFILE == "SAV4A_SCHEDULE_TRANSLATED_STEREO_OFFLINE_PLAYER_SAV4B_V1"
    assert AUTHORITY == "RESEARCHER_DERIVED_PLAYBACK_OVER_SAV4A_SCHEDULE"
    ref = profile_reference()
    assert ref["physical_mechanism"] is False
    assert ref["physical_preset"] is False
    assert ref["pcm_rendering_implemented"] is False
    assert ref["wav_export_implemented"] is False
    assert ref["input"] == "SAV4A_DETERMINISTIC_SCHEDULE_ONLY"
    assert SCHEMA in FORBIDDEN_TOKENS
    assert CAPABILITY in FORBIDDEN_TOKENS
    assert AUTHORITY in FORBIDDEN_TOKENS
    assert "OFFLINE_SAV4B" in FORBIDDEN_TOKENS
    assert audit_cognition_payload({"osc_l_0": 0.1, "osc_r_0": 0.0}) == []
    assert audit_cognition_payload(
        {"schema": SCHEMA, "playback_cursor": 1, "schedule_digest": "x", "OFFLINE_SAV4B": True}
    )
    assert TICKS == 0
