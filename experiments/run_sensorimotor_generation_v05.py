from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.psyche.sensorimotor import (
    SensorimotorConfig,
    SensorimotorStore,
    evidence_bin,
    generate_proposals,
    remember_action,
    select_proposal,
    update_store,
)


def _obs(tag: str = "FAMILIAR", energy: float = 0.8) -> dict:
    cue = "CUE-X" if tag == "FAMILIAR" else "CUE-Z"
    object_id = "OBJ-X" if tag == "FAMILIAR" else "OBJ-Z"
    return {
        "position": [2, 2],
        "visible_objects": [
            {
                "id": object_id,
                "position": [3, 2],
                "relative_offset": [1, 0],
                "cue_signature": cue,
                "interaction_state": "FREE",
            }
        ],
        "available_actions": [f"PUSH:{object_id}:4,2", "MOVE:3,2", "WAIT"],
        "interoception": {
            "energy_signal": energy,
            "hydration_signal": 0.8,
            "fatigue_signal": 0.1,
        },
        "visual_fragments": [{"kind": "OBJECT", "cue_signature": cue}],
    }


def _apply(obs: dict, action: str, *, displace: bool) -> dict:
    nxt = json.loads(json.dumps(obs))
    if action.startswith("PUSH:") and displace:
        for item in nxt["visible_objects"]:
            item["position"] = [item["position"][0] + 1, item["position"][1]]
    if action.startswith("MOVE:"):
        nxt["visual_fragments"] = list(nxt["visual_fragments"]) + [{"kind": "MOVE"}]
    return nxt


def _drive(store: SensorimotorStore, config: SensorimotorConfig, ticks: int, tag: str, displace: bool, seed: float):
    rows = []
    obs = _obs(tag)
    for tick in range(ticks):
        generated = generate_proposals(
            observation=obs, store=store, config=config, random_value=(seed + tick * 0.017) % 1.0
        )
        chosen = select_proposal(generated, body=obs["interoception"], random_value=seed)
        remember_action(store, chosen["action"], obs)
        nxt = _apply(obs, chosen["action"], displace=displace and chosen["action"].startswith("PUSH:"))
        update = update_store(store, observation=nxt, config=config)
        sources = [item["source"] for item in generated["proposals"]]
        rows.append(
            {
                "tick": tick,
                "action": chosen["action"],
                "reason": chosen["reason"],
                "quality": generated["quality"],
                "bin": evidence_bin(generated["quality"], generated["evidence"]["unknown"]),
                "stage": generated["evidence"]["stage"],
                "unknown": generated["evidence"]["unknown"],
                "proposal_sources": sources,
                "endogenous_fraction": sources.count("ENDOGENOUS_VARIATION") / max(1, len(sources)),
                "learned_fraction": sum(source in {"LEARNED_SENSORIMOTOR", "BOTH"} for source in sources)
                / max(1, len(sources)),
                "inspected": generated["evidence"]["inspected"],
                "update": update,
            }
        )
        obs = _obs(tag)
    return rows


def _summary(rows: list[dict]) -> dict:
    if not rows:
        return {}
    early = rows[: max(1, len(rows) // 5)]
    late = rows[-max(1, len(rows) // 5) :]
    return {
        "ticks": len(rows),
        "early_unknown_fraction": sum(item["unknown"] for item in early) / len(early),
        "late_unknown_fraction": sum(item["unknown"] for item in late) / len(late),
        "early_learned_fraction": sum(item["learned_fraction"] for item in early) / len(early),
        "late_learned_fraction": sum(item["learned_fraction"] for item in late) / len(late),
        "interaction_fraction": sum(item["action"].startswith(("PUSH:", "TAKE:", "USE:")) for item in rows)
        / len(rows),
        "max_inspected": max(item["inspected"] for item in rows),
    }


def main() -> None:
    config = SensorimotorConfig()
    experienced = SensorimotorStore()
    rows_a = _drive(experienced, config, 40, "FAMILIAR", True, 0.17)
    newborn = _drive(SensorimotorStore(), config, 8, "FAMILIAR", True, 0.17)
    familiar = generate_proposals(
        observation=_obs("FAMILIAR"), store=experienced, config=config, random_value=0.17
    )
    unfamiliar = generate_proposals(
        observation=_obs("UNFAMILIAR"), store=experienced, config=config, random_value=0.17
    )
    reversed_store = SensorimotorStore.from_dict(experienced.to_dict())
    rows_d = _drive(reversed_store, config, 16, "FAMILIAR", False, 0.17)
    result = {
        "claim_boundary": (
            "Experience-structured sensorimotor generation. "
            "No claim of curiosity, exploration drive, or preference."
        ),
        "A_newborn_to_experienced": _summary(rows_a),
        "B_newborn_vs_experienced": {
            "newborn_unknown": newborn[0]["unknown"],
            "experienced_unknown": rows_a[-1]["unknown"],
            "newborn_sources": newborn[0]["proposal_sources"],
            "experienced_sources": rows_a[-1]["proposal_sources"],
        },
        "C_familiar_vs_unfamiliar": {
            "familiar_quality": familiar["quality"],
            "unfamiliar_quality": unfamiliar["quality"],
            "familiar_bin": evidence_bin(familiar["quality"], familiar["evidence"]["unknown"]),
            "unfamiliar_bin": evidence_bin(unfamiliar["quality"], unfamiliar["evidence"]["unknown"]),
        },
        "D_reversal": {
            "pre_quality": rows_a[-1]["quality"],
            "post_quality": rows_d[-1]["quality"],
            "post_unknown": rows_d[-1]["unknown"],
        },
        "E_controllability_without_reward": {
            "note": "Predictive structure may form without preferential interaction.",
            "interaction_fraction": _summary(rows_a)["interaction_fraction"],
        },
    }
    out = ROOT / "experiments" / "sensorimotor_generation_v05_result.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
