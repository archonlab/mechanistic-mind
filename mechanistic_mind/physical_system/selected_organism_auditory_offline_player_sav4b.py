"""SELECTED_ORGANISM_AUDITORY_OFFLINE_PLAYER_SAV4B_V1 — researcher metadata only.

Playback executes in Observer frontend over SAV4A schedule. This module exposes
identity/profile for privacy + serialize banners. Not a physical mechanism.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "SELECTED_ORGANISM_AUDITORY_OFFLINE_PLAYER_SAV4B_V1"
CAPABILITY = "selected_organism_auditory_offline_playback"
PROFILE = "SAV4A_SCHEDULE_TRANSLATED_STEREO_OFFLINE_PLAYER_SAV4B_V1"
AUTHORITY = "RESEARCHER_DERIVED_PLAYBACK_OVER_SAV4A_SCHEDULE"
TITLE = "OFFLINE SAVED-RUN AUDITORY RECONSTRUCTION · SAV4B"
WARNING = (
    "DERIVED TRANSLATED MONITOR OF RECORDED ORGANISM RECEPTOR CHANNELS · "
    "NOT PHYSICAL AUDIO · NOT LITERAL ORGANISM HEARING"
)
INPUT = "SAV4A_DETERMINISTIC_SCHEDULE_ONLY"
OWNER = "OFFLINE_SAV4B"


def profile_reference() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "title": TITLE,
        "warning": WARNING,
        "input": INPUT,
        "owner": OWNER,
        "researcher_only": True,
        "agent_accessible": False,
        "physical_mechanism": False,
        "physical_preset": False,
        "pcm_rendering_implemented": False,
        "wav_export_implemented": False,
        "uses_live_sav2_queue": False,
        "consumes_sav4a_schedule_only": True,
        "raw_oatt_parsed": False,
        "raw_sav1_parsed": False,
        "legacy_evidence_parsed": False,
    }


def observer_banner() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "title": TITLE,
        "warning": WARNING,
        "implemented": True,
        "audio_location": "OBSERVER_FRONTEND_ONLY",
    }
