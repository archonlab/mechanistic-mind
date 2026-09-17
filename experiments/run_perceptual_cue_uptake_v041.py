#!/usr/bin/env python3
"""Update 4.1 diagnostics: LEGACY vs PERCEPTUAL cue uptake (no retuning)."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from contextual_object_ecology_v034 import (  # noqa: E402
    ContextualObjectEcologyWorld,
    multi_channel_contextual_object_config,
    todo4_calibrated_body_config,
)
from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import InMemorySink, PsychologyObserver
from mechanistic_mind.psyche import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    SingleOrganismPsycheV05,
)
from mechanistic_mind.psyche.sensorimotor import SensorimotorConfig


def _body(recovery: bool = False) -> BodyConfig:
    base = todo4_calibrated_body_config()
    return BodyConfig(
        **{
            **{f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()},
            "recovery_dynamics_enabled": recovery,
        }
    )


def _world(*, dynamic: bool = True) -> ContextualObjectEcologyWorld:
    cfg = multi_channel_contextual_object_config(17)
    if not dynamic:
        cfg = cfg.__class__(
            **{
                **{f.name: getattr(cfg, f.name) for f in cfg.__dataclass_fields__.values()},
                "autonomous_dynamics_enabled": False,
            }
        )
    return ContextualObjectEcologyWorld(world_config=cfg, body_config=_body(False))


def _psyche_maps(result, agent_id: str = "A001"):
    """Return (working, memory) dicts from SimulationState / dict."""
    state_after = getattr(result, "state_after", None)
    agents = getattr(state_after, "agents", None)
    if agents is None and isinstance(state_after, dict):
        agents = state_after.get("agents")
    if not isinstance(agents, dict):
        return {}, {}
    agent = agents.get(agent_id)
    ms = getattr(agent, "mechanism_states", None) if agent is not None else None
    if ms is None and isinstance(agent, dict):
        ms = agent.get("mechanism_states")
    if not isinstance(ms, dict):
        return {}, {}
    for st in ms.values():
        if not isinstance(st, dict):
            continue
        # SingleOrganism stores flat psyche fields on mechanism state.
        working = st.get("working") if isinstance(st.get("working"), dict) else {}
        memory = st.get("memory") if isinstance(st.get("memory"), dict) else {}
        if not working and isinstance(st.get("psyche"), dict):
            working = st["psyche"].get("working") or {}
            memory = st["psyche"].get("memory") or {}
        if working or memory:
            return working if isinstance(working, dict) else {}, memory if isinstance(memory, dict) else {}
    return {}, {}


def _read_depth(result, agent_id: str = "A001"):
    """Prefer generation diagnostics; distinguish MISSING vs VALUE vs N/A."""
    working, memory = _psyche_maps(result, agent_id)
    gen = working.get("sensorimotor_generation") if isinstance(working.get("sensorimotor_generation"), dict) else {}
    depth = None
    status = "MISSING_TELEMETRY"
    if gen:
        if gen.get("cognitive_depth_status"):
            status = str(gen["cognitive_depth_status"])
        if gen.get("cognitive_depth") is not None:
            depth = gen.get("cognitive_depth")
            status = str(gen.get("cognitive_depth_status") or "VALUE")
    if depth is None:
        dev = memory.get("developmental") if isinstance(memory.get("developmental"), dict) else {}
        if dev.get("cognitive_depth") is not None:
            depth = dev.get("cognitive_depth")
            status = "VALUE"
        elif not gen and not dev:
            status = "MISSING_TELEMETRY"
        elif gen and gen.get("cognitive_depth_status"):
            status = str(gen["cognitive_depth_status"])
    return depth, status


def _cue_info(result, agent_id: str = "A001"):
    working, _memory = _psyche_maps(result, agent_id)
    gen = working.get("sensorimotor_generation") if isinstance(working.get("sensorimotor_generation"), dict) else {}
    sel = working.get("last_selection") if isinstance(working.get("last_selection"), dict) else {}
    summary = gen.get("cue_summary") if isinstance(gen.get("cue_summary"), dict) else {}
    return {
        "cue_mode": gen.get("cue_mode"),
        "perceptual_token_count": int(summary.get("perceptual_token_count") or 0),
        "uptake": gen.get("cue_uptake") if isinstance(gen.get("cue_uptake"), dict) else {},
        "retrieval_match": gen.get("retrieval_match") if isinstance(gen.get("retrieval_match"), dict) else {},
        "selection": {
            "candidates": sel.get("candidates"),
            "tie": sel.get("tie"),
            "tie_break": sel.get("tie_break"),
            "decision_source": sel.get("decision_source"),
            "action": sel.get("action"),
            "reason": sel.get("reason"),
            "score": sel.get("score"),
        }
        if sel
        else {},
    }


def run_arm(*, cue_mode: str, ticks: int = 90, seed: int = 17) -> dict:
    world = _world(dynamic=True)
    psyche = SingleOrganismPsycheV05(
        sensorimotor_config=SensorimotorConfig(cue_mode=cue_mode),
        developmental=DevelopmentalConfig(
            condition=DevelopmentalCondition.EXPERIENCE_GATED
        ),
    )
    registry = MechanismRegistry()
    registry.register(psyche)
    sink = InMemorySink()
    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
        observer=PsychologyObserver(sink),
        run_config={
            "perception_mode": "MULTI_CHANNEL",
            "autonomous_dynamics_enabled": True,
            "cue_mode": cue_mode,
            "update": "4.1",
        },
    )
    actions = []
    depths = []
    statuses = []
    token_counts = []
    cue_sigs = []
    retrieval_hits = Counter()
    selection_rows = []
    for _tick in range(ticks):
        result = engine.step()
        actions.append(result.actions["A001"].kind)
        depth, status = _read_depth(result)
        depths.append(depth)
        statuses.append(status)
        info = _cue_info(result)
        token_counts.append(int(info["perceptual_token_count"]))
        uptake = info.get("uptake") or {}
        cue_sigs.append(
            (
                info.get("cue_mode"),
                int(uptake.get("perceptual_token_count") or info["perceptual_token_count"]),
                tuple(
                    sorted(
                        (
                            name,
                            (row or {}).get("AVAILABLE_TO_SENSOR"),
                            (row or {}).get("REPRESENTED_IN_CUE"),
                            (row or {}).get("MATCHED_IN_RETRIEVAL"),
                        )
                        for name, row in ((uptake.get("channels") or {})).items()
                    )
                ),
            )
        )
        rm = info.get("retrieval_match") or {}
        for key, val in rm.items():
            if val:
                retrieval_hits[key] += 1
        if info.get("selection"):
            selection_rows.append(info["selection"])
    engine.close()

    numeric_depths = [float(d) for d in depths if d is not None]
    action_counts = Counter(actions)
    return {
        "cue_mode": cue_mode,
        "ticks": ticks,
        "seed": seed,
        "action_counts": dict(action_counts),
        "emit_rate": action_counts.get("EMIT", 0) / max(1, ticks),
        "unique_actions": sorted(action_counts),
        "mean_depth": (
            sum(numeric_depths) / len(numeric_depths) if numeric_depths else None
        ),
        "depth_status_counts": dict(Counter(statuses)),
        "mean_perceptual_tokens": (
            sum(token_counts) / len(token_counts) if token_counts else 0.0
        ),
        "unique_cue_signatures": len(set(cue_sigs)),
        "retrieval_hit_ticks": dict(retrieval_hits),
        "selection_sample": selection_rows[:5],
        "final_selection": selection_rows[-1] if selection_rows else None,
        "policy_fingerprint": tuple(actions),
    }


def compare(legacy: dict, perceptual: dict) -> dict:
    same_policy = legacy["policy_fingerprint"] == perceptual["policy_fingerprint"]
    return {
        "A_cue_content_differs": (
            legacy["unique_cue_signatures"] != perceptual["unique_cue_signatures"]
            or legacy["mean_perceptual_tokens"] != perceptual["mean_perceptual_tokens"]
        ),
        "A_legacy_mean_tokens": legacy["mean_perceptual_tokens"],
        "A_perceptual_mean_tokens": perceptual["mean_perceptual_tokens"],
        "B_retrieval_legacy": legacy["retrieval_hit_ticks"],
        "B_retrieval_perceptual": perceptual["retrieval_hit_ticks"],
        "C_emit_rate_legacy": legacy["emit_rate"],
        "C_emit_rate_perceptual": perceptual["emit_rate"],
        "C_selection_sample_perceptual": perceptual.get("final_selection"),
        "D_depth_status_legacy": legacy["depth_status_counts"],
        "D_depth_status_perceptual": perceptual["depth_status_counts"],
        "D_mean_depth_legacy": legacy["mean_depth"],
        "D_mean_depth_perceptual": perceptual["mean_depth"],
        "E_behavior_identical": same_policy,
        "E_note": (
            "behavioral null is valid for Update 4.1 (no retuning)"
            if same_policy
            else "free-policy action sequences differ"
        ),
    }


def main() -> None:
    out_dir = ROOT / "results" / "update41_perceptual_cue_v041"
    out_dir.mkdir(parents=True, exist_ok=True)
    legacy = run_arm(cue_mode="LEGACY_CUE_ONLY", ticks=90, seed=17)
    perceptual = run_arm(cue_mode="PERCEPTUAL_CUE_ENABLED", ticks=90, seed=17)
    ae = compare(legacy, perceptual)
    legacy_save = dict(legacy)
    perceptual_save = dict(perceptual)
    for arm in (legacy_save, perceptual_save):
        fp = arm.pop("policy_fingerprint")
        arm["policy_len"] = len(fp)
        arm["policy_hash"] = hash(fp)
    summary = {
        "update": "4.1",
        "seed": 17,
        "ticks": 90,
        "arms": {
            "LEGACY_CUE_ONLY": legacy_save,
            "PERCEPTUAL_CUE_ENABLED": perceptual_save,
        },
        "experiments_A_E": ae,
    }
    path = out_dir / "summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str))
    (out_dir / "legacy.json").write_text(
        json.dumps(legacy_save, indent=2, sort_keys=True, default=str)
    )
    (out_dir / "perceptual.json").write_text(
        json.dumps(perceptual_save, indent=2, sort_keys=True, default=str)
    )
    print(json.dumps(summary["experiments_A_E"], indent=2, sort_keys=True, default=str))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
