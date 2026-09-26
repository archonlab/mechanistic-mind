"""BETA2-SIGINT-02: controlled FIELD intervention × matched branch experiments.

Observer/experimental harness only. Inactive by default.
Injects physical FIELD amplitudes through the ordinary shared-field path
(``TwoAgentRuntime.inject_source`` → ``extra_sources`` → ``_deposit``).
Never writes intervention metadata into cognition observations.
"""
from __future__ import annotations

import hashlib
import json
import time
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from mechanistic_mind.physical_system.physical_signal import (
    PhysicalSignalConfig,
    _site_cells,
    sample_local,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime


TRIGGER_EXTERNAL = "EXTERNAL_EXPERIMENTAL_INTERVENTION"
TRIGGER_SHAM = "EXTERNAL_EXPERIMENTAL_SHAM"

WINDOW = {
    "PRE": 0,
    "IMMEDIATE": 1,
    "SHORT": 5,
    "MEDIUM": 15,
}


INTERVENTION_DESIGN = {
    "status": "IMPLEMENTED",
    "goal": (
        "At matched physical/internal contexts, compare CONTROL (normal field) vs "
        "INTERVENTION (externally injected FIELD_A/FIELD_B pattern)."
    ),
    "constraints": [
        "Must not alter normal run behavior when harness inactive",
        "Injection is experimental intervention, not semantic instruction",
        "No sender identity leaked into cognition",
        "Observer records intervention receipts separately",
    ],
    "non_claims": [
        "Does not demonstrate communication",
        "Does not demonstrate learned protocol",
        "Does not assign meaning to FIELD_A/B",
    ],
}


def intervention_design_doc() -> str:
    lines = [
        "# SIGINT-02 — Controlled Signal Injection Design",
        "",
        "Status: IMPLEMENTED (harness; experiments are explicit/offline).",
        "",
        "## Goal",
        INTERVENTION_DESIGN["goal"],
        "",
        "## Injection path",
        "EXTERNAL → TwoAgentRuntime.inject_source(cells=...) → _pending_sources",
        "→ step_physical_signals(extra_sources) → _deposit on FIELD_A/FIELD_B",
        "→ ordinary local sensing → clipped local.FIELD_* in cognition.",
        "",
        "## Constraints",
    ]
    for c in INTERVENTION_DESIGN["constraints"]:
        lines.append(f"- {c}")
    lines.append("")
    lines.append("## Non-claims")
    for c in INTERVENTION_DESIGN["non_claims"]:
        lines.append(f"- {c}")
    return "\n".join(lines)


def stable_id(prefix: str, *parts: Any) -> str:
    h = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{h}"


def scientific_fingerprint(rt: TwoAgentRuntime) -> dict[str, Any]:
    rows = []
    for i, slot in enumerate(rt.slots):
        sel = (slot.cognition or {}).get("last_selection") or {}
        obs = slot.last_agent_observation or {}
        field_keys = {
            k: round(float(obs[k]), 6)
            for k in sorted(obs)
            if str(k).startswith("local.FIELD")
        }
        rows.append({
            "agent": f"agent_{i}",
            "tick": int(slot.tick),
            "action": slot.last_selected_action,
            "selection_source": sel.get("source"),
            "x": round(float(slot.body.x), 6),
            "y": round(float(slot.body.y), 6),
            "vx": round(float(slot.body.vx), 6),
            "vy": round(float(slot.body.vy), 6),
            "theta": round(float(getattr(slot.body, "theta", 0.0) or 0.0), 6),
            "work": round(float(getattr(slot.body, "mechanical_work_reservoir", 0.0) or 0.0), 6),
            "seed": int(slot.seed),
            "obs_fields": field_keys,
        })
    fa = getattr(rt.world, "FIELD_A", None)
    fb = getattr(rt.world, "FIELD_B", None)
    return {
        "tick": int(rt.tick),
        "seed": int(rt.seed),
        "agents": rows,
        "field_A_sum": round(float(fa.sum()), 6) if fa is not None else None,
        "field_B_sum": round(float(fb.sum()), 6) if fb is not None else None,
        "field_A_max": round(float(fa.max()), 6) if fa is not None and fa.size else None,
        "field_B_max": round(float(fb.max()), 6) if fb is not None and fb.size else None,
        "pending_sources": len(rt._pending_sources),
    }


def fingerprint_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def cognition_compact(slot) -> dict[str, Any]:
    sel = (slot.cognition or {}).get("last_selection") or {}
    obs = slot.last_agent_observation or {}
    metrics = (slot.cognition or {}).get("metrics") or {}
    preds = (slot.cognition or {}).get("predictions")
    return {
        "action": slot.last_selected_action,
        "selection_source": sel.get("source"),
        "selection_rule": sel.get("selection_rule")
        or (sel.get("competition") or {}).get("selection_reason"),
        "obs_field_A": obs.get("local.FIELD_A"),
        "obs_field_B": obs.get("local.FIELD_B"),
        "prediction_n": len(preds) if isinstance(preds, list) else "MISSING",
        "action_counts": dict(metrics.get("action_counts") or {}),
        "status": "AVAILABLE" if sel.get("source") is not None else "PARTIAL",
    }


def receiver_local_fields(rt: TwoAgentRuntime, slot: int) -> dict[str, float]:
    body = rt.slots[int(slot)].body
    cfg = rt.slots[int(slot)].config.body
    h, w = int(rt.world.T.shape[0]), int(rt.world.T.shape[1])
    cells = _site_cells(body, cfg, w, h)
    return {
        "FIELD_A": float(sample_local(rt.world, cells, "A")),
        "FIELD_B": float(sample_local(rt.world, cells, "B")),
        "n_cells": float(len(cells)),
    }


def receiver_footprint_cells(rt: TwoAgentRuntime, slot: int) -> list[tuple[int, int]]:
    body = rt.slots[int(slot)].body
    cfg = rt.slots[int(slot)].config.body
    h, w = int(rt.world.T.shape[0]), int(rt.world.T.shape[1])
    return list(_site_cells(body, cfg, w, h))


def audit_observation_no_intervention_leak(obs: dict[str, Any] | None) -> list[str]:
    if not isinstance(obs, dict):
        return []
    leaks = []
    for k in obs:
        kl = str(k).lower()
        if any(
            x in kl
            for x in (
                "intervention",
                "emitter",
                "sender",
                "experiment_id",
                "from_",
                "source_agent",
            )
        ):
            leaks.append(str(k))
        if str(k) in ("agent_0", "agent_1", "source_agent_id"):
            leaks.append(str(k))
    return leaks


@dataclass
class FieldPattern:
    channel: str = "A"
    amplitude: float = 0.7
    duration_ticks: int = 3
    temporal_profile: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    mode: str = "FOOTPRINT"

    def amplitudes(self) -> list[float]:
        prof = list(self.temporal_profile) or [1.0]
        out = []
        for i in range(max(1, int(self.duration_ticks))):
            out.append(float(self.amplitude) * float(prof[i % len(prof)]))
        return out


@dataclass
class BranchArm:
    arm_id: str
    kind: str
    pattern: FieldPattern | None = None
    note: str = ""


@dataclass
class CandidateSpec:
    candidate_id: str
    pattern_id: str
    receiver: str
    pre_action: str
    pre_selection_source: str
    channel_preference: str
    contact_any: bool
    evidence_sigint01: str
    feasibility: str
    why: str
    episode_ids: list[str] = field(default_factory=list)
    peak_mean: float | None = None


def rank_sigint01_candidates(sigint01_dir: Path | str) -> list[CandidateSpec]:
    root = Path(sigint01_dir)
    patterns = json.loads((root / "signal_patterns.json").read_text(encoding="utf-8"))
    episodes = []
    with (root / "signal_episodes.jsonl").open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                episodes.append(json.loads(line))
    by_id = {e["episode_id"]: e for e in episodes}
    out: list[CandidateSpec] = []
    for p in patterns:
        pid = p["pattern_id"]
        key = str(p.get("key") or "")
        parts = key.split("|")
        receiver = p.get("receiver") or (parts[0] if parts else "agent_1")
        pre_action = (p.get("PRE") or {}).get("action") or (parts[1] if len(parts) > 1 else "WAIT")
        pre_src = (p.get("PRE") or {}).get("selection_source") or (parts[2] if len(parts) > 2 else "")
        contact = bool((p.get("PRE") or {}).get("contact_any"))
        evid = str(p.get("evidence") or "")
        eids = list(p.get("episode_ids") or [])
        peaks = [
            float(by_id[e]["peak"])
            for e in eids
            if e in by_id and by_id[e].get("peak") is not None
        ]
        peak_mean = sum(peaks) / len(peaks) if peaks else None
        ctrl = p.get("matched_controls") or {}
        ctrl_action = ctrl.get("mean_action_change_rate")
        ctrl_src = ctrl.get("mean_selection_source_change_rate")
        post = p.get("POST") or {}
        why_parts = []
        feas = "WEAK_INTERVENTION_CANDIDATE"
        score = 0
        if evid == "MATCHED_ASSOCIATION":
            score += 3
            why_parts.append("SIGINT-01 MATCHED_ASSOCIATION")
        elif evid == "TEMPORALLY_ASSOCIATED":
            score += 1
            why_parts.append("only TEMPORALLY_ASSOCIATED")
        if not contact:
            score += 2
            why_parts.append("no PRE contact (cleaner FIELD path)")
        else:
            why_parts.append("PRE contact present — FIELD_B confound risk")
        if ctrl_action == 0.0 and ctrl_src == 0.0:
            score += 3
            why_parts.append("matched controls show 0 change rates")
        elif ctrl_action is None:
            why_parts.append("missing control rates")
        if float(post.get("requested_direction_changed_frac") or 0) >= 0.75:
            score += 1
            why_parts.append("high POST direction-change frac")
        ch_pref = "A" if not contact else "B"
        if score >= 6 and not contact:
            feas = "GOOD_INTERVENTION_CANDIDATE"
        elif contact:
            feas = (
                "WEAK_INTERVENTION_CANDIDATE"
                if evid == "MATCHED_ASSOCIATION"
                else "NOT_CURRENTLY_TESTABLE"
            )
        out.append(
            CandidateSpec(
                candidate_id=stable_id("cand", pid),
                pattern_id=pid,
                receiver=str(receiver),
                pre_action=str(pre_action),
                pre_selection_source=str(pre_src),
                channel_preference=ch_pref,
                contact_any=contact,
                evidence_sigint01=evid,
                feasibility=feas,
                why="; ".join(why_parts),
                episode_ids=eids,
                peak_mean=peak_mean,
            )
        )
    order = {
        "GOOD_INTERVENTION_CANDIDATE": 0,
        "WEAK_INTERVENTION_CANDIDATE": 1,
        "NOT_CURRENTLY_TESTABLE": 2,
    }
    out.sort(key=lambda c: (order.get(c.feasibility, 9), -len(c.episode_ids), c.pattern_id))
    return out


def make_signal_runtime(*, seed: int = 17, signal_enabled: bool = True) -> TwoAgentRuntime:
    cfg = PhysicalSystemConfig()
    cfg.cognition.enabled = True
    for name in (
        "unknown_action_physical_probe",
        "predictive_equivalence",
        "predictive_relevance",
        "temporal_predictive_structure",
        "temporal_prospection_bridge",
        "predictive_conflict",
        "future_sensitive_action",
        "prediction_error_revision",
        "temporal_prediction_error",
        "predicted_context_prospection",
        "multistep_action_prospection",
        "experimental_physical_signal",
    ):
        if hasattr(cfg.cognition, name):
            setattr(cfg.cognition, name, True)
    cfg.physical_signal = PhysicalSignalConfig(mode="EXPERIMENTAL")
    return TwoAgentRuntime(
        seed=int(seed),
        config=cfg,
        signal_enabled=bool(signal_enabled),
        contact_enabled=True,
        field_coupling_enabled=True,
    )


def find_matched_s0(
    *,
    seed: int,
    receiver: str,
    pre_action: str,
    pre_selection_source: str,
    require_no_contact: bool = True,
    max_search: int = 800,
    min_age: int = 40,
) -> dict[str, Any] | None:
    rt = make_signal_runtime(seed=seed, signal_enabled=True)
    slot = 1 if str(receiver).endswith("1") else 0
    for _ in range(max_search):
        rt.step()
        if int(rt.tick) < min_age:
            continue
        agent = rt.slots[slot]
        sel = (agent.cognition or {}).get("last_selection") or {}
        src = sel.get("source")
        contact = bool((rt.last_contact or {}).get("contact"))
        if agent.last_selected_action != pre_action:
            continue
        if pre_selection_source and src != pre_selection_source:
            continue
        if require_no_contact and contact:
            continue
        return {
            "snapshot": rt.snapshot(),
            "tick": int(rt.tick),
            "receiver_slot": slot,
            "fingerprint": scientific_fingerprint(rt),
            "selection_source": src,
            "action": agent.last_selected_action,
            "contact": contact,
        }
    return None


def run_branch(
    snapshot: dict[str, Any],
    arm: BranchArm,
    *,
    receiver_slot: int,
    horizon: int = 20,
    experiment_id: str,
    intervention_id: str,
    schedule_from_tick: int = 0,
) -> dict[str, Any]:
    rt = TwoAgentRuntime.restore(deepcopy(snapshot))
    assert len(rt._pending_sources) == 0
    pre_fp = scientific_fingerprint(rt)
    traces: list[dict[str, Any]] = []
    remaining_amps: list[float] = []
    pattern = arm.pattern
    kind = arm.kind
    if pattern is not None and kind != "CONTROL":
        remaining_amps = list(pattern.amplitudes())
        if kind == "SHAM":
            remaining_amps = [0.0 for _ in remaining_amps]
        elif kind == "WRONG_CHANNEL":
            pattern = FieldPattern(
                channel=("B" if pattern.channel == "A" else "A"),
                amplitude=pattern.amplitude,
                duration_ticks=pattern.duration_ticks,
                temporal_profile=list(pattern.temporal_profile),
                mode=pattern.mode,
            )
            remaining_amps = list(pattern.amplitudes())
        elif kind == "TEMPORAL_SHUFFLE":
            prof = list(pattern.temporal_profile)
            shuffled = list(reversed(prof)) if len(prof) > 1 else [0.5, 1.0, 0.25]
            pattern = FieldPattern(
                channel=pattern.channel,
                amplitude=pattern.amplitude,
                duration_ticks=pattern.duration_ticks,
                temporal_profile=shuffled,
                mode=pattern.mode,
            )
            remaining_amps = list(pattern.amplitudes())

    obs_source = f"exp:{experiment_id}:{intervention_id}:{arm.arm_id}"
    for i in range(int(horizon)):
        if remaining_amps and i >= schedule_from_tick and pattern is not None:
            amp = float(remaining_amps.pop(0))
            cells = receiver_footprint_cells(rt, receiver_slot)
            if kind == "CONTEXT_MISMATCH" and cells:
                h, w = int(rt.world.T.shape[0]), int(rt.world.T.shape[1])
                cells = [((iy + 6) % h, (ix + 6) % w) for iy, ix in cells]
            trigger = TRIGGER_SHAM if kind == "SHAM" else TRIGGER_EXTERNAL
            rt.inject_source(
                channel=pattern.channel,
                amplitude=amp,
                cells=cells,
                trigger=trigger,
                observer_source_id=obs_source,
            )
        rt.step()
        slot = rt.slots[receiver_slot]
        leaks = audit_observation_no_intervention_leak(slot.last_agent_observation)
        traces.append({
            "branch_tick": i + 1,
            "runtime_tick": int(rt.tick),
            "fingerprint": scientific_fingerprint(rt),
            "cognition": cognition_compact(slot),
            "local_fields": receiver_local_fields(rt, receiver_slot),
            "obs_fields": {
                "local.FIELD_A": (slot.last_agent_observation or {}).get("local.FIELD_A"),
                "local.FIELD_B": (slot.last_agent_observation or {}).get("local.FIELD_B"),
            },
            "action": slot.last_selected_action,
            "selection_source": ((slot.cognition or {}).get("last_selection") or {}).get("source"),
            "x": float(slot.body.x),
            "y": float(slot.body.y),
            "contact": bool((rt.last_contact or {}).get("contact")),
            "observation_leaks": leaks,
        })

    return {
        "arm_id": arm.arm_id,
        "kind": kind,
        "experiment_id": experiment_id,
        "intervention_id": intervention_id,
        "pre_fingerprint": pre_fp,
        "pattern": asdict(pattern) if pattern else None,
        "note": arm.note,
        "traces": traces,
    }


def first_divergences(control: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    ct = control.get("traces") or []
    ot = other.get("traces") or []
    n = min(len(ct), len(ot))

    def first(pred: Callable[[dict, dict], bool]) -> int | None:
        for i in range(n):
            if pred(ct[i], ot[i]):
                return int(ct[i]["branch_tick"])
        return None

    return {
        "observation_field": first(
            lambda a, b: (a.get("obs_fields") or {}) != (b.get("obs_fields") or {})
            or (a.get("local_fields") or {}) != (b.get("local_fields") or {})
        ),
        "cognition_selection_source": first(
            lambda a, b: a.get("selection_source") != b.get("selection_source")
        ),
        "action": first(lambda a, b: a.get("action") != b.get("action")),
        "position": first(
            lambda a, b: abs(float(a["x"]) - float(b["x"])) > 1e-6
            or abs(float(a["y"]) - float(b["y"])) > 1e-6
        ),
        "full_fingerprint": first(
            lambda a, b: not fingerprint_equal(a["fingerprint"], b["fingerprint"])
        ),
        "contact": first(lambda a, b: bool(a.get("contact")) != bool(b.get("contact"))),
    }


def classify_effect(
    divergences: dict[str, Any],
    *,
    sham_divergences: dict[str, Any] | None = None,
    replicated: bool = False,
) -> dict[str, str]:
    out = {
        "FIELD_TO_OBSERVATION": "NOT_ESTABLISHED",
        "FIELD_TO_COGNITION": "NOT_ESTABLISHED",
        "FIELD_TO_ACTION": "NOT_ESTABLISHED",
        "FIELD_TO_TRAJECTORY": "NOT_ESTABLISHED",
    }
    if divergences.get("observation_field") is not None:
        out["FIELD_TO_OBSERVATION"] = "DIRECT_CAUSAL_LINK"
    if divergences.get("cognition_selection_source") is not None:
        out["FIELD_TO_COGNITION"] = "BRANCH_CAUSAL_EFFECT"
    if divergences.get("action") is not None:
        out["FIELD_TO_ACTION"] = "BRANCH_CAUSAL_EFFECT"
    if divergences.get("position") is not None:
        out["FIELD_TO_TRAJECTORY"] = "DOWNSTREAM_DIVERGENCE"
    if replicated and sham_divergences is not None:
        if (
            out["FIELD_TO_ACTION"] == "BRANCH_CAUSAL_EFFECT"
            and sham_divergences.get("action") is None
            and divergences.get("observation_field") is not None
        ):
            out["FIELD_TO_ACTION"] = "INTERVENTION_SUPPORTED"
        if (
            out["FIELD_TO_COGNITION"] == "BRANCH_CAUSAL_EFFECT"
            and sham_divergences.get("cognition_selection_source") is None
            and divergences.get("observation_field") is not None
        ):
            out["FIELD_TO_COGNITION"] = "INTERVENTION_SUPPORTED"
        if (
            out["FIELD_TO_TRAJECTORY"] == "DOWNSTREAM_DIVERGENCE"
            and sham_divergences.get("position") is None
            and divergences.get("action") is not None
        ):
            out["FIELD_TO_TRAJECTORY"] = "BRANCH_CAUSAL_EFFECT"
    return out


def run_candidate_experiment(
    candidate: CandidateSpec,
    *,
    seeds: Iterable[int] = (17, 19, 23),
    horizon: int = 20,
    intensities: Iterable[float] = (0.0, 0.35, 0.7, 1.0),
) -> dict[str, Any]:
    experiment_id = stable_id("sexp", candidate.candidate_id, time.time_ns())
    amp_base = float(candidate.peak_mean or 0.7)
    amp_base = max(0.25, min(1.0, amp_base if amp_base <= 1.5 else amp_base / 2.0))
    base_pattern = FieldPattern(
        channel=candidate.channel_preference,
        amplitude=amp_base,
        duration_ticks=3,
        temporal_profile=[0.6, 1.0, 0.8],
        mode="FOOTPRINT",
    )
    branch_rows: list[dict[str, Any]] = []
    divergence_rows: list[dict[str, Any]] = []
    replication: dict[str, Any] = {
        "n_pairs": 0,
        "n_obs_effect": 0,
        "n_cognition_effect": 0,
        "n_action_effect": 0,
        "n_trajectory_effect": 0,
        "n_pre_intervention_divergence": 0,
        "n_control_control_fail": 0,
        "seeds_ok": [],
        "seeds_fail_s0": [],
    }
    dose_rows: list[dict[str, Any]] = []
    channel_rows: list[dict[str, Any]] = []
    temporal_rows: list[dict[str, Any]] = []
    context_rows: list[dict[str, Any]] = []

    for seed in seeds:
        s0 = find_matched_s0(
            seed=int(seed),
            receiver=candidate.receiver,
            pre_action=candidate.pre_action,
            pre_selection_source=candidate.pre_selection_source,
            require_no_contact=not candidate.contact_any,
        )
        if s0 is None:
            replication["seeds_fail_s0"].append(int(seed))
            continue
        snap = s0["snapshot"]
        slot = int(s0["receiver_slot"])
        intervention_id = stable_id("sint", candidate.candidate_id, seed, s0["tick"])

        c1 = run_branch(
            snap, BranchArm("CTRL_A", "CONTROL"), receiver_slot=slot, horizon=horizon,
            experiment_id=experiment_id, intervention_id=intervention_id,
        )
        c2 = run_branch(
            snap, BranchArm("CTRL_B", "CONTROL"), receiver_slot=slot, horizon=horizon,
            experiment_id=experiment_id, intervention_id=intervention_id,
        )
        ctrl_eq = all(
            fingerprint_equal(a["fingerprint"], b["fingerprint"])
            for a, b in zip(c1["traces"], c2["traces"])
        )
        if not ctrl_eq:
            replication["n_control_control_fail"] += 1
        if not fingerprint_equal(c1["pre_fingerprint"], c2["pre_fingerprint"]):
            replication["n_pre_intervention_divergence"] += 1

        arms = [
            BranchArm("CONTROL", "CONTROL"),
            BranchArm("INTERVENTION", "INTERVENTION", pattern=deepcopy(base_pattern)),
            BranchArm("SHAM", "SHAM", pattern=deepcopy(base_pattern), note="machinery on, amp=0"),
            BranchArm("WRONG_CHANNEL", "WRONG_CHANNEL", pattern=deepcopy(base_pattern)),
            BranchArm("TEMPORAL_SHUFFLE", "TEMPORAL_SHUFFLE", pattern=deepcopy(base_pattern)),
            BranchArm(
                "CONTEXT_MISMATCH",
                "CONTEXT_MISMATCH",
                pattern=deepcopy(base_pattern),
                note="same amp, displaced cells",
            ),
        ]
        results = {
            a.arm_id: run_branch(
                snap, a, receiver_slot=slot, horizon=horizon,
                experiment_id=experiment_id, intervention_id=intervention_id,
            )
            for a in arms
        }
        control = results["CONTROL"]
        for res in results.values():
            if not fingerprint_equal(control["pre_fingerprint"], res["pre_fingerprint"]):
                replication["n_pre_intervention_divergence"] += 1

        div_int = first_divergences(control, results["INTERVENTION"])
        div_sham = first_divergences(control, results["SHAM"])
        div_wrong = first_divergences(control, results["WRONG_CHANNEL"])
        div_temp = first_divergences(control, results["TEMPORAL_SHUFFLE"])
        div_ctx = first_divergences(control, results["CONTEXT_MISMATCH"])

        replication["n_pairs"] += 1
        if div_int.get("observation_field") is not None:
            replication["n_obs_effect"] += 1
        if div_int.get("cognition_selection_source") is not None:
            replication["n_cognition_effect"] += 1
        if div_int.get("action") is not None:
            replication["n_action_effect"] += 1
        if div_int.get("position") is not None:
            replication["n_trajectory_effect"] += 1
        replication["seeds_ok"].append(int(seed))

        evidence = classify_effect(div_int, sham_divergences=div_sham, replicated=True)
        divergence_rows.append({
            "experiment_id": experiment_id,
            "intervention_id": intervention_id,
            "seed": int(seed),
            "s0_tick": s0["tick"],
            "control_control_equal": ctrl_eq,
            "divergences_vs_control": {
                "INTERVENTION": div_int,
                "SHAM": div_sham,
                "WRONG_CHANNEL": div_wrong,
                "TEMPORAL_SHUFFLE": div_temp,
                "CONTEXT_MISMATCH": div_ctx,
            },
            "evidence": evidence,
        })
        for arm_id, res in results.items():
            branch_rows.append({
                "experiment_id": experiment_id,
                "intervention_id": intervention_id,
                "seed": int(seed),
                "arm_id": arm_id,
                "kind": res["kind"],
                "s0_tick": s0["tick"],
                "final_action": (res["traces"][-1]["action"] if res["traces"] else None),
                "final_selection_source": (
                    res["traces"][-1]["selection_source"] if res["traces"] else None
                ),
                "final_xy": (
                    [res["traces"][-1]["x"], res["traces"][-1]["y"]] if res["traces"] else None
                ),
                "max_obs_FIELD_A": max(
                    (
                        float((t.get("obs_fields") or {}).get("local.FIELD_A") or 0.0)
                        for t in res["traces"]
                    ),
                    default=0.0,
                ),
                "max_obs_FIELD_B": max(
                    (
                        float((t.get("obs_fields") or {}).get("local.FIELD_B") or 0.0)
                        for t in res["traces"]
                    ),
                    default=0.0,
                ),
                "any_observation_leak": any(t.get("observation_leaks") for t in res["traces"]),
                "actions": [t["action"] for t in res["traces"]],
                "selection_sources": [t["selection_source"] for t in res["traces"]],
            })

        channel_rows.append({
            "seed": int(seed),
            "intervention_action_div": div_int.get("action"),
            "wrong_channel_action_div": div_wrong.get("action"),
            "channel_specific": (
                div_int.get("action") is not None and div_wrong.get("action") is None
            ),
        })
        temporal_rows.append({
            "seed": int(seed),
            "intervention_action_div": div_int.get("action"),
            "shuffle_action_div": div_temp.get("action"),
            "temporal_matters": div_int.get("action") != div_temp.get("action"),
        })
        context_rows.append({
            "seed": int(seed),
            "matched_action_div": div_int.get("action"),
            "mismatch_action_div": div_ctx.get("action"),
            "context_dependent": (
                (div_int.get("action") is not None) != (div_ctx.get("action") is not None)
            ),
        })

        for amp in intensities:
            pat = FieldPattern(
                channel=base_pattern.channel,
                amplitude=float(amp),
                duration_ticks=3,
                temporal_profile=[1.0, 1.0, 1.0],
            )
            kind = "CONTROL" if float(amp) <= 0.0 else "INTERVENTION"
            arm = BranchArm(f"DOSE_{amp}", kind, pattern=None if kind == "CONTROL" else pat)
            res = run_branch(
                snap, arm, receiver_slot=slot, horizon=horizon,
                experiment_id=experiment_id, intervention_id=intervention_id,
            )
            div = first_divergences(control, res) if kind != "CONTROL" else {}
            dose_rows.append({
                "seed": int(seed),
                "amplitude": float(amp),
                "action_div_tick": div.get("action"),
                "obs_div_tick": div.get("observation_field"),
                "final_action": res["traces"][-1]["action"] if res["traces"] else None,
                "max_obs_A": max(
                    (
                        float((t.get("obs_fields") or {}).get("local.FIELD_A") or 0.0)
                        for t in res["traces"]
                    ),
                    default=0.0,
                ),
            })

    return {
        "experiment_id": experiment_id,
        "candidate": asdict(candidate),
        "base_pattern": asdict(base_pattern),
        "replication": replication,
        "branch_rows": branch_rows,
        "divergence_rows": divergence_rows,
        "dose_rows": dose_rows,
        "channel_rows": channel_rows,
        "temporal_rows": temporal_rows,
        "context_rows": context_rows,
    }
