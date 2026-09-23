"""Deterministic receipt IDs — no random UUIDs in the hot path."""
from __future__ import annotations


def _safe(s: str) -> str:
    return str(s).replace(":", "_").replace("/", "_").replace(" ", "_")


def observation_id(run_id: str, tick: int, agent_id: str) -> str:
    return f"o:{_safe(run_id)}:{int(tick)}:{_safe(agent_id)}"


def decision_id(run_id: str, tick: int, agent_id: str) -> str:
    return f"d:{_safe(run_id)}:{int(tick)}:{_safe(agent_id)}"


def motor_id(run_id: str, tick: int, agent_id: str) -> str:
    return f"m:{_safe(run_id)}:{int(tick)}:{_safe(agent_id)}"


def consequence_id(run_id: str, tick: int, body_id: str) -> str:
    return f"c:{_safe(run_id)}:{int(tick)}:{_safe(body_id)}"


def revision_id(run_id: str, tick: int, agent_id: str) -> str:
    return f"r:{_safe(run_id)}:{int(tick)}:{_safe(agent_id)}"
