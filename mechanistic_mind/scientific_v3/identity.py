\
"""IdentityMap — cognitive agent ≠ physical body ≠ role label."""
from __future__ import annotations

from typing import Any

CONTROLLER_AUTONOMOUS = "AUTONOMOUS"
CONTROLLER_EXPERIMENTER = "EXPERIMENTER"
CONTROLLER_PASSIVE = "PASSIVE"
CONTROLLER_SYSTEM = "SYSTEM"


def classify_controller(
    *,
    slot_index: int,
    experimenter_slot: int | None,
    cognition_enabled: bool,
) -> tuple[str, str]:
    """Return (controller_type, role_label). UNDERCOVER is a role, not an identity."""
    if experimenter_slot is not None and int(slot_index) == int(experimenter_slot):
        return CONTROLLER_EXPERIMENTER, "UNDERCOVER"
    if cognition_enabled:
        return CONTROLLER_AUTONOMOUS, "AUTONOMOUS_AGENT"
    return CONTROLLER_PASSIVE, "PASSIVE_BODY"


def cognitive_agent_id_for_slot(slot_index: int, *, controller_type: str) -> str | None:
    if controller_type == CONTROLLER_PASSIVE:
        return None
    if controller_type == CONTROLLER_EXPERIMENTER:
        # Experimenter controller identity (not UNDERCOVER role reuse as agent id).
        return f"controller_experimenter_{int(slot_index)}"
    return f"agent_{int(slot_index)}"


def physical_body_id_for_slot(slot_index: int) -> str:
    return f"body-{int(slot_index)}"


class IdentityMap:
    """Lifecycle registry for a run. Instrument what exists; do not invent ownership."""

    def __init__(self, *, run_id: str, generation: int = 0) -> None:
        self.run_id = str(run_id)
        self.generation = int(generation)
        self.entries: dict[str, dict[str, Any]] = {}  # key: body_id

    def upsert_slot(
        self,
        *,
        slot_index: int,
        experimenter_slot: int | None,
        cognition_enabled: bool,
        tick: int,
    ) -> dict[str, Any]:
        controller_type, role_label = classify_controller(
            slot_index=slot_index,
            experimenter_slot=experimenter_slot,
            cognition_enabled=cognition_enabled,
        )
        body_id = physical_body_id_for_slot(slot_index)
        cog_id = cognitive_agent_id_for_slot(slot_index, controller_type=controller_type)
        prev = self.entries.get(body_id)
        if prev is None:
            entry = {
                "physical_body_id": body_id,
                "slot_index": int(slot_index),
                "cognitive_agent_id": cog_id,
                "controller_type": controller_type,
                "controller_id": (
                    f"ctrl:{controller_type.lower()}:{slot_index}"
                ),
                "role_label": role_label,
                "spawn_tick": int(tick),
                "despawn_tick": None,
                "generation": self.generation,
                "run_id": self.run_id,
            }
            self.entries[body_id] = entry
            return entry
        # Lifecycle change if controller/cognition role changed.
        if (
            prev.get("controller_type") != controller_type
            or prev.get("cognitive_agent_id") != cog_id
            or prev.get("role_label") != role_label
        ):
            prev["despawn_tick"] = int(tick)
            # Retire old key variant and open new logical epoch under same body_id
            # by appending epoch marker — keep body_id stable; record change event.
            prev.setdefault("lifecycle_changes", []).append(
                {
                    "tick": int(tick),
                    "from": {
                        "controller_type": prev.get("controller_type"),
                        "cognitive_agent_id": prev.get("cognitive_agent_id"),
                        "role_label": prev.get("role_label"),
                    },
                    "to": {
                        "controller_type": controller_type,
                        "cognitive_agent_id": cog_id,
                        "role_label": role_label,
                    },
                }
            )
            prev["controller_type"] = controller_type
            prev["cognitive_agent_id"] = cog_id
            prev["role_label"] = role_label
            prev["controller_id"] = f"ctrl:{controller_type.lower()}:{slot_index}"
        return prev

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "mm.scientific_v3.identity_map.v1",
            "run_id": self.run_id,
            "generation": self.generation,
            "bodies": list(self.entries.values()),
            "notes": [
                "UNDERCOVER is role_label only; never fundamental identity.",
                "agent_N is cognitive_agent_id for AUTONOMOUS slots; not synonymous with UNDERCOVER.",
            ],
        }
