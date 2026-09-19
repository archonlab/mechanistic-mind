"""BETA2-SIGINT-04: natural signal repertoire × functional screening × causal response search.

Reuses SIGINT-02/03 matched branching and NATURAL_SIGNAL_REPLAY → `_deposit` path.
Does not re-prove Level-1 exposure; searches for Level-2+ downstream divergence.
"""
from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    BranchArm,
    FieldPattern,
    audit_observation_no_intervention_leak,
    find_matched_s0,
    fingerprint_equal,
    first_divergences,
    make_signal_runtime,
    receiver_footprint_cells,
    receiver_local_fields,
    run_branch,
    scientific_fingerprint,
    stable_id,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.natural_replay import (
    NOT_RECORDED,
    NaturalSignalLibrary,
    NaturalSignalSpecimen,
    _amp,
    capture_natural_emissions_from_runtime,
    harvest_field_a_specimens,
    run_fidelity_gate,
    run_natural_replay_branch,
    specimen_from_emission_evidence,
)

HORIZON_MARKERS = (1, 2, 5, 10, 25, 50)
DEFAULT_SCREEN_HORIZON = 50

EvidenceClass = Literal[
    "UNTESTED",
    "INERT_UNDER_TESTED_CONTEXTS",
    "LEVEL1_ONLY",
    "COGNITION_CANDIDATE",
    "ACTION_CANDIDATE",
    "TRAJECTORY_CANDIDATE",
]


@dataclass
class ScreenConfig:
    """Bounded experiment queue — never unbounded."""

    max_specimens: int = 24
    max_families: int = 12
    stage_a_seeds: tuple[int, ...] = (17, 19)
    stage_b_seeds: tuple[int, ...] = (17, 19, 23, 29)
    stage_a_horizon: int = DEFAULT_SCREEN_HORIZON
    stage_b_horizon: int = DEFAULT_SCREEN_HORIZON
    max_s0_search: int = 400
    min_s0_age: int = 30
    promote_min_downstream_hits: int = 1  # any Level-2+ hit promotes
    max_stage_b_candidates: int = 6
    include_generic_on_confirm: bool = True
    include_perturbations_on_confirm: bool = True
    harvest_seeds: tuple[int, ...] = (17, 19, 23, 29, 31)
    harvest_steps: int = 140
    harvest_per_seed: int = 8


def physical_feature_vector(sp: NaturalSignalSpecimen) -> dict[str, Any]:
    amp = _amp(sp)
    n_cells = len(sp.cells) if isinstance(sp.cells, tuple) else 0
    if isinstance(sp.cells, tuple) and sp.cells:
        ys = [c[0] for c in sp.cells]
        xs = [c[1] for c in sp.cells]
        h = max(ys) - min(ys) + 1
        w = max(xs) - min(xs) + 1
        aspect = round(w / max(1, h), 2)
        span = h * w
    else:
        h = w = aspect = span = NOT_RECORDED
    # Amplitude bin (log-ish)
    if amp is None:
        amp_bin = "NONE"
    elif amp < 0.05:
        amp_bin = "VL"
    elif amp < 0.15:
        amp_bin = "L"
    elif amp < 0.35:
        amp_bin = "M"
    elif amp < 0.7:
        amp_bin = "H"
    else:
        amp_bin = "VH"
    n_bin = "0" if n_cells == 0 else ("1" if n_cells == 1 else ("2-4" if n_cells < 5 else ("5-8" if n_cells < 9 else "9+")))
    return {
        "channel": sp.channel,
        "trigger": sp.trigger,
        "amp_bin": amp_bin,
        "n_cells_bin": n_bin,
        "n_cells": n_cells,
        "aspect": aspect,
        "span": span,
        "amplitude": amp,
        "reconstruction": sp.reconstruction_completeness,
    }


def family_key_from_features(feat: dict[str, Any]) -> str:
    return "|".join(
        [
            f"ch{feat['channel']}",
            f"tr{feat['trigger']}",
            f"amp{feat['amp_bin']}",
            f"n{feat['n_cells_bin']}",
            f"asp{feat['aspect']}",
        ]
    )


def build_repertoire(
    *,
    cfg: ScreenConfig | None = None,
    sigint03_dir: Path | str | None = None,
    harvest: bool = True,
) -> dict[str, Any]:
    cfg = cfg or ScreenConfig()
    lib = NaturalSignalLibrary(maxlen=512)
    sources: list[str] = []

    if sigint03_dir:
        p = Path(sigint03_dir) / "natural_signal_specimens.json"
        if p.is_file():
            for d in json.loads(p.read_text(encoding="utf-8")):
                lib.add(NaturalSignalSpecimen.from_dict(d))
            sources.append(f"sigint03:{p}")

    if harvest:
        for seed in cfg.harvest_seeds:
            rt = make_signal_runtime(seed=int(seed))
            n = 0
            for _ in range(int(cfg.harvest_steps)):
                rt.step()
                got = capture_natural_emissions_from_runtime(
                    rt, run_id=f"harvest-{seed}", library=lib,
                )
                n += len(got)
                if len(lib.list(limit=512)) >= cfg.max_specimens * 3:
                    break
            sources.append(f"harvest-{seed}:emissions≈{n}")

    # Deduplicate near-equivalents: same channel+trigger+amp_bin+n_cells+rounded amp
    kept: list[NaturalSignalSpecimen] = []
    seen: set[str] = set()
    for d in lib.list(limit=512):
        sp = NaturalSignalSpecimen.from_dict(d)
        amp = _amp(sp)
        amp_r = None if amp is None else round(float(amp), 3)
        n_cells = len(sp.cells) if isinstance(sp.cells, tuple) else 0
        key = f"{sp.channel}|{sp.trigger}|{amp_r}|{n_cells}|{sp.reconstruction_completeness}"
        if key in seen:
            continue
        seen.add(key)
        kept.append(sp)
        if len(kept) >= cfg.max_specimens * 2:
            break

    # Prefer reconstructable
    kept.sort(
        key=lambda s: (
            0 if s.reconstruction_completeness == "CELLS_AND_AMPLITUDE" else 1,
            0 if _amp(s) is not None else 1,
            str(s.specimen_id),
        )
    )
    kept = kept[: max(cfg.max_specimens * 2, 8)]

    families_all = group_into_families(kept, max_families=None)
    families = families_all[: cfg.max_families]
    # Prioritize using full family membership so diversity is not collapsed
    prioritized = prioritize_candidates(kept, families_all, limit=cfg.max_specimens)

    return {
        "n_raw_indexed": len(lib.list(limit=512)),
        "n_deduped": len(kept),
        "sources": sources,
        "specimens": [s.to_dict() for s in kept],
        "families": families,
        "prioritized": prioritized,
        "config": asdict(cfg),
    }


def group_into_families(
    specimens: list[NaturalSignalSpecimen],
    *,
    max_families: int | None = None,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[NaturalSignalSpecimen]] = defaultdict(list)
    why: dict[str, str] = {}
    for sp in specimens:
        feat = physical_feature_vector(sp)
        key = family_key_from_features(feat)
        buckets[key].append(sp)
        why[key] = (
            f"Grouped by channel={feat['channel']}, trigger={feat['trigger']}, "
            f"amp_bin={feat['amp_bin']}, n_cells_bin={feat['n_cells_bin']}, "
            f"footprint_aspect={feat['aspect']} (physical similarity only)."
        )
    families = []
    for key, members in sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        amps = [_amp(m) for m in members if _amp(m) is not None]
        fid = stable_id("fam", key)
        families.append({
            "family_id": fid,
            "family_key": key,
            "n_members": len(members),
            "member_ids": [m.specimen_id for m in members],
            "channel": members[0].channel,
            "trigger": members[0].trigger,
            "amplitude_range": [min(amps), max(amps)] if amps else None,
            "why_grouped": why[key],
            "representative_id": members[0].specimen_id,
        })
    if max_families is not None:
        return families[: max(1, int(max_families))]
    return families


def prioritize_candidates(
    specimens: list[NaturalSignalSpecimen],
    families: list[dict[str, Any]],
    *,
    limit: int = 24,
) -> list[dict[str, Any]]:
    fam_by_member = {}
    for f in families:
        for mid in f["member_ids"]:
            fam_by_member[mid] = f
    ranked = []
    for sp in specimens:
        score = 0
        reasons = []
        if sp.reconstruction_completeness == "CELLS_AND_AMPLITUDE":
            score += 5
            reasons.append("CELLS_AND_AMPLITUDE")
        elif _amp(sp) is not None:
            score += 2
            reasons.append("amplitude_recorded")
        if sp.trigger == "body_motion":
            score += 2
            reasons.append("no-contact body_motion path")
        elif sp.trigger == "body_contact":
            score += 0
            reasons.append("contact trigger — FIELD_B confound risk")
        if sp.channel == "A":
            score += 1
            reasons.append("FIELD_A (SIGINT-02 regime)")
        amp = _amp(sp)
        if amp is not None and (amp < 0.08 or amp > 0.4):
            score += 1
            reasons.append("amplitude outlier vs typical mid-range")
        n_cells = len(sp.cells) if isinstance(sp.cells, tuple) else 0
        if n_cells >= 5:
            score += 1
            reasons.append("multi-cell footprint")
        fam = fam_by_member.get(sp.specimen_id)
        if fam and fam["n_members"] >= 2:
            score += 1
            reasons.append(f"family n={fam['n_members']}")
        # Prefer family representatives for diversity
        if fam and fam.get("representative_id") == sp.specimen_id:
            score += 2
            reasons.append("family representative")
        ranked.append({
            "specimen_id": sp.specimen_id,
            "family_id": (fam or {}).get("family_id"),
            "priority_score": score,
            "reasons": reasons,
            "channel": sp.channel,
            "trigger": sp.trigger,
            "amplitude": amp,
            "reconstruction": sp.reconstruction_completeness,
            "note": "Scheduling heuristic only — not communication evidence.",
        })
    ranked.sort(key=lambda r: (-r["priority_score"], r["specimen_id"]))
    # Soft diversity: prefer unseen families first, then fill to limit
    out: list[dict[str, Any]] = []
    seen_fam: set[str] = set()
    # Pass 1: one per family
    for r in ranked:
        fid = r.get("family_id") or f"solo:{r['specimen_id']}"
        if fid in seen_fam:
            continue
        seen_fam.add(fid)
        out.append(r)
        if len(out) >= limit:
            return out
    # Pass 2: fill remaining slots by score
    have = {r["specimen_id"] for r in out}
    for r in ranked:
        if r["specimen_id"] in have:
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out


def _persistence_label(
    div_tick: int | None,
    control: dict[str, Any],
    other: dict[str, Any],
    *,
    kind: str,
) -> str:
    if div_tick is None:
        return "NONE"
    ct = control.get("traces") or []
    ot = other.get("traces") or []
    n = min(len(ct), len(ot))
    if n == 0:
        return "NONE"

    def differs(i: int) -> bool:
        a, b = ct[i], ot[i]
        if kind == "cognition":
            return a.get("selection_source") != b.get("selection_source")
        if kind == "action":
            return a.get("action") != b.get("action")
        if kind == "trajectory":
            return abs(float(a["x"]) - float(b["x"])) > 1e-6 or abs(float(a["y"]) - float(b["y"])) > 1e-6
        return False

    end_div = differs(n - 1)
    # reconvergence: differed then matched again
    reconverged = False
    for i in range(div_tick, n):  # branch_tick is 1-indexed
        idx = i - 1
        if idx < 0 or idx >= n:
            continue
        if not differs(idx) and i > div_tick:
            reconverged = True
            break
    if end_div and not reconverged:
        return "PERSISTENT_WITHIN_WINDOW"
    if reconverged and (n - div_tick) <= 5:
        return "TRANSIENT"
    if reconverged:
        return "SHORT_LIVED"
    return "SHORT_LIVED" if not end_div else "PERSISTENT_WITHIN_WINDOW"


def measure_latency_persistence(
    control: dict[str, Any],
    replay: dict[str, Any],
) -> dict[str, Any]:
    div = first_divergences(control, replay)
    return {
        "first_divergence": div,
        "latency_markers_hit": {
            str(h): {
                "cognition": div.get("cognition_selection_source") is not None
                and int(div["cognition_selection_source"]) <= h,
                "action": div.get("action") is not None and int(div["action"]) <= h,
                "trajectory": div.get("position") is not None and int(div["position"]) <= h,
                "exposure": div.get("observation_field") is not None
                and int(div["observation_field"]) <= h,
            }
            for h in HORIZON_MARKERS
        },
        "persistence": {
            "cognition": _persistence_label(
                div.get("cognition_selection_source"), control, replay, kind="cognition"
            ),
            "action": _persistence_label(div.get("action"), control, replay, kind="action"),
            "trajectory": _persistence_label(
                div.get("position"), control, replay, kind="trajectory"
            ),
        },
    }


def _find_s0_variants(
    *,
    seed: int,
    receiver: str,
    cfg: ScreenConfig,
) -> list[dict[str, Any]]:
    """Find matched contexts across a small context matrix."""
    contexts = [
        ("WAIT", "RETAINED_PREDICTION", True, "WAIT|RETAINED|no_contact"),
        ("MOVE:E", "ENDOGENOUS_VARIATION", True, "MOVE:E|ENDOGENOUS|no_contact"),
        ("WAIT", "RETAINED_PREDICTION", False, "WAIT|RETAINED|contact_ok"),
    ]
    out = []
    for action, src, no_contact, label in contexts:
        s0 = find_matched_s0(
            seed=int(seed),
            receiver=receiver,
            pre_action=action,
            pre_selection_source=src,
            require_no_contact=no_contact,
            max_search=cfg.max_s0_search,
            min_age=cfg.min_s0_age,
        )
        if s0 is not None:
            out.append({**s0, "context_label": label})
    return out


def run_screen_trial(
    specimen: NaturalSignalSpecimen,
    *,
    seed: int,
    receiver: str,
    context_label: str,
    snapshot: dict[str, Any],
    receiver_slot: int,
    horizon: int,
    experiment_id: str,
    echo_target: str = "PEER",
) -> dict[str, Any]:
    iid = stable_id("scr", specimen.specimen_id, seed, context_label, echo_target)
    control = run_natural_replay_branch(
        snapshot, specimen, receiver_slot=receiver_slot, horizon=horizon,
        experiment_id=experiment_id, intervention_id=iid, kind="CONTROL",
        target=echo_target,
    )
    sham = run_natural_replay_branch(
        snapshot, specimen, receiver_slot=receiver_slot, horizon=horizon,
        experiment_id=experiment_id, intervention_id=iid, kind="SHAM",
        target=echo_target,
    )
    replay = run_natural_replay_branch(
        snapshot, specimen, receiver_slot=receiver_slot, horizon=horizon,
        experiment_id=experiment_id, intervention_id=iid, kind="NATURAL_REPLAY",
        mode="EXACT", target=echo_target,
    )
    # CONTROL/CONTROL check (cheap, one seed)
    c2 = run_natural_replay_branch(
        snapshot, specimen, receiver_slot=receiver_slot, horizon=min(12, horizon),
        experiment_id=experiment_id, intervention_id=iid, kind="CONTROL",
    )
    ctrl_eq = all(
        fingerprint_equal(a["fingerprint"], b["fingerprint"])
        for a, b in zip(control["traces"][:12], c2["traces"])
    )
    div_rep = first_divergences(control, replay)
    div_sham = first_divergences(control, sham)
    lat = measure_latency_persistence(control, replay)
    any_leak = any(
        t.get("observation_leaks")
        for arm in (control, sham, replay)
        for t in (arm.get("traces") or [])
    )
    levels = {
        "L0_fidelity": "DEFERRED",  # filled by caller if needed
        "L1_exposure": div_rep.get("observation_field") is not None,
        "L2_cognition": div_rep.get("cognition_selection_source") is not None
        and div_sham.get("cognition_selection_source") is None,
        "L3_action": div_rep.get("action") is not None and div_sham.get("action") is None,
        "L4_trajectory": div_rep.get("position") is not None and div_sham.get("position") is None,
        # Raw (before sham filter) for diagnostics
        "L2_raw": div_rep.get("cognition_selection_source") is not None,
        "L3_raw": div_rep.get("action") is not None,
        "L4_raw": div_rep.get("position") is not None,
    }
    return {
        "event_type": "SIGNAL_SCREEN_TRIAL",
        "trial_id": iid,
        "specimen_id": specimen.specimen_id,
        "seed": int(seed),
        "receiver": receiver,
        "context_label": context_label,
        "echo_target": echo_target,
        "horizon": horizon,
        "control_control_equal": ctrl_eq,
        "divergences": {"NATURAL_REPLAY": div_rep, "SHAM": div_sham},
        "latency_persistence": lat,
        "levels": levels,
        "any_leak": any_leak,
        "final_actions": {
            "CONTROL": (control["traces"][-1]["action"] if control.get("traces") else None),
            "SHAM": (sham["traces"][-1]["action"] if sham.get("traces") else None),
            "NATURAL_REPLAY": (replay["traces"][-1]["action"] if replay.get("traces") else None),
        },
    }


def classify_from_trials(trials: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(trials)
    if n == 0:
        return {
            "evidence_class": "UNTESTED",
            "tags": [],
            "n": 0,
            "n_L1": 0,
            "n_L2": 0,
            "n_L3": 0,
            "n_L4": 0,
        }
    n1 = sum(1 for t in trials if (t.get("levels") or {}).get("L1_exposure"))
    n2 = sum(1 for t in trials if (t.get("levels") or {}).get("L2_cognition"))
    n3 = sum(1 for t in trials if (t.get("levels") or {}).get("L3_action"))
    n4 = sum(1 for t in trials if (t.get("levels") or {}).get("L4_trajectory"))
    tags = []
    if n2 >= 1:
        tags.append("COGNITION_CANDIDATE")
    if n3 >= 1:
        tags.append("ACTION_CANDIDATE")
    if n4 >= 1:
        tags.append("TRAJECTORY_CANDIDATE")
    if tags:
        evidence = tags[0] if len(tags) == 1 else "DOWNSTREAM_MULTI"
    elif n1 >= max(1, (n + 1) // 2):
        evidence = "LEVEL1_ONLY"
    else:
        evidence = "INERT_UNDER_TESTED_CONTEXTS"
    return {
        "evidence_class": evidence,
        "tags": tags,
        "n": n,
        "n_L1": n1,
        "n_L2": n2,
        "n_L3": n3,
        "n_L4": n4,
        "frac_L1": n1 / n,
        "frac_L2": n2 / n,
        "frac_L3": n3 / n,
        "frac_L4": n4 / n,
    }


def run_stage_a(
    repertoire: dict[str, Any],
    *,
    cfg: ScreenConfig | None = None,
) -> dict[str, Any]:
    cfg = cfg or ScreenConfig()
    by_id = {
        d["specimen_id"]: NaturalSignalSpecimen.from_dict(d)
        for d in repertoire["specimens"]
    }
    prioritized = repertoire.get("prioritized") or []
    experiment_id = stable_id("stageA", time.time_ns())
    results = []
    queue = []

    for rank, item in enumerate(prioritized[: cfg.max_specimens]):
        sp = by_id.get(item["specimen_id"])
        if sp is None or _amp(sp) is None:
            continue
        # Prefer peer receiver opposite emitter
        emitter = sp.emitter_agent_id
        receiver = "agent_1" if str(emitter).endswith("0") else "agent_0"
        if emitter in (NOT_RECORDED, "", None):
            receiver = "agent_1"
        queue.append({
            "rank": rank,
            "specimen_id": sp.specimen_id,
            "family_id": item.get("family_id"),
            "priority_score": item.get("priority_score"),
            "receiver": receiver,
            "stage": "A",
        })
        trials = []
        for seed in cfg.stage_a_seeds:
            s0s = _find_s0_variants(seed=int(seed), receiver=receiver, cfg=cfg)
            if not s0s:
                continue
            # Stage A: only first (cleanest) context
            s0 = s0s[0]
            trial = run_screen_trial(
                sp,
                seed=int(seed),
                receiver=receiver,
                context_label=s0["context_label"],
                snapshot=s0["snapshot"],
                receiver_slot=int(s0["receiver_slot"]),
                horizon=cfg.stage_a_horizon,
                experiment_id=experiment_id,
                echo_target="PEER",
            )
            trials.append(trial)
        summary = classify_from_trials(trials)
        # Skip fidelity gate for all — one spot-check on first
        fid = None
        if rank == 0:
            fid = run_fidelity_gate(sp, seed=17)
        results.append({
            "specimen_id": sp.specimen_id,
            "family_id": item.get("family_id"),
            "priority_score": item.get("priority_score"),
            "receiver": receiver,
            "fidelity_spotcheck": fid,
            "trials": trials,
            "summary": summary,
            "promote": bool(summary.get("tags")),
        })

    promoted = [r for r in results if r.get("promote")][: cfg.max_stage_b_candidates]
    inert = [
        {
            "specimen_id": r["specimen_id"],
            "family_id": r.get("family_id"),
            "summary": r["summary"],
            "label": "INERT_UNDER_TESTED_CONTEXTS",
        }
        for r in results
        if r["summary"]["evidence_class"] == "INERT_UNDER_TESTED_CONTEXTS"
        or r["summary"]["evidence_class"] == "LEVEL1_ONLY"
    ]
    return {
        "experiment_id": experiment_id,
        "queue": queue,
        "results": results,
        "promoted_specimen_ids": [r["specimen_id"] for r in promoted],
        "inert": inert,
        "n_tested": len(results),
        "n_promoted": len(promoted),
        "n_inert": len(inert),
    }


def run_generic_matched_energy(
    snapshot: dict[str, Any],
    specimen: NaturalSignalSpecimen,
    *,
    receiver_slot: int,
    horizon: int,
    experiment_id: str,
    intervention_id: str,
) -> dict[str, Any]:
    amp = float(_amp(specimen) or 0.7)
    # Uniform energy on a compact 1-cell or small box — not natural footprint
    cells = receiver_footprint_cells(
        TwoAgentRuntime.restore(deepcopy(snapshot)), receiver_slot
    )
    # Use center cell only for generic
    if cells:
        cy = sum(c[0] for c in cells) // len(cells)
        cx = sum(c[1] for c in cells) // len(cells)
        gen_cells = [(cy, cx)]
    else:
        gen_cells = [(10, 10)]
    # Match total deposited magnitude roughly: amp_generic * 1 ≈ amp_natural (per deposit API)
    pat = FieldPattern(
        channel=specimen.channel or "A",
        amplitude=amp,
        duration_ticks=1,
        temporal_profile=[1.0],
    )
    # Prefer inject via natural_replay path with artificial LOCATION cells
    rt = TwoAgentRuntime.restore(deepcopy(snapshot))
    pre = scientific_fingerprint(rt)
    traces = []
    for i in range(horizon):
        if i == 0:
            rt.inject_source(
                channel=pat.channel,
                amplitude=float(amp),
                cells=gen_cells,
                trigger="EXTERNAL_EXPERIMENTAL_INTERVENTION",
                observer_source_id=f"exp:{experiment_id}:{intervention_id}:GENERIC",
            )
        rt.step()
        slot = rt.slots[receiver_slot]
        traces.append({
            "branch_tick": i + 1,
            "runtime_tick": int(rt.tick),
            "fingerprint": scientific_fingerprint(rt),
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
            "observation_leaks": audit_observation_no_intervention_leak(slot.last_agent_observation),
        })
    return {
        "arm_id": "GENERIC_FIELD_MATCHED_ENERGY",
        "kind": "GENERIC_FIELD_MATCHED_ENERGY",
        "amplitude": amp,
        "n_cells": len(gen_cells),
        "pre_fingerprint": pre,
        "traces": traces,
    }


def run_shuffled_footprint_branch(
    snapshot: dict[str, Any],
    specimen: NaturalSignalSpecimen,
    *,
    receiver_slot: int,
    horizon: int,
    experiment_id: str,
    intervention_id: str,
) -> dict[str, Any]:
    """Preserve amplitude and cell count; displace spatial organization."""
    amp = _amp(specimen)
    if amp is None:
        return {"accepted": False, "error": "no amplitude"}
    rt = TwoAgentRuntime.restore(deepcopy(snapshot))
    pre = scientific_fingerprint(rt)
    n = len(specimen.cells) if isinstance(specimen.cells, tuple) else 5
    # Deterministic offset shuffle away from original
    base = receiver_footprint_cells(rt, receiver_slot)
    if not base:
        base = [(12, 12)]
    cy, cx = base[0]
    shuffled = [((cy + 3 + i) % 32, (cx + 5 + 2 * i) % 32) for i in range(max(1, n))]
    traces = []
    for i in range(horizon):
        if i == 0:
            rt.inject_source(
                channel=specimen.channel,
                amplitude=float(amp),
                cells=shuffled,
                trigger="EXTERNAL_EXPERIMENTAL_INTERVENTION",
                observer_source_id=f"exp:{experiment_id}:{intervention_id}:SHUFFLED",
            )
        rt.step()
        slot = rt.slots[receiver_slot]
        traces.append({
            "branch_tick": i + 1,
            "runtime_tick": int(rt.tick),
            "fingerprint": scientific_fingerprint(rt),
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
            "observation_leaks": audit_observation_no_intervention_leak(slot.last_agent_observation),
        })
    return {
        "arm_id": "SHUFFLED_FOOTPRINT",
        "kind": "SHUFFLED_FOOTPRINT",
        "amplitude": float(amp),
        "n_cells": len(shuffled),
        "cells": shuffled,
        "pre_fingerprint": pre,
        "traces": traces,
    }


def run_stage_b(
    repertoire: dict[str, Any],
    stage_a: dict[str, Any],
    *,
    cfg: ScreenConfig | None = None,
) -> dict[str, Any]:
    cfg = cfg or ScreenConfig()
    by_id = {
        d["specimen_id"]: NaturalSignalSpecimen.from_dict(d)
        for d in repertoire["specimens"]
    }
    experiment_id = stable_id("stageB", time.time_ns())
    results = []
    context_matrix = []
    receiver_matrix = []
    natural_vs_generic = []
    perturbations = []

    for sid in stage_a.get("promoted_specimen_ids") or []:
        sp = by_id.get(sid)
        if sp is None:
            continue
        emitter = sp.emitter_agent_id
        peer = "agent_1" if str(emitter).endswith("0") else "agent_0"
        self_r = emitter if str(emitter).startswith("agent_") else "agent_0"
        if emitter in (NOT_RECORDED, "", None):
            peer, self_r = "agent_1", "agent_0"

        trials = []
        for seed in cfg.stage_b_seeds:
            for receiver, target, rlabel in (
                (peer, "PEER", "PEER"),
                (self_r, "SELF", "SELF"),
            ):
                s0s = _find_s0_variants(seed=int(seed), receiver=receiver, cfg=cfg)
                for s0 in s0s[:2]:  # up to 2 contexts per seed×receiver
                    trial = run_screen_trial(
                        sp,
                        seed=int(seed),
                        receiver=receiver,
                        context_label=s0["context_label"],
                        snapshot=s0["snapshot"],
                        receiver_slot=int(s0["receiver_slot"]),
                        horizon=cfg.stage_b_horizon,
                        experiment_id=experiment_id,
                        echo_target=target,
                    )
                    trial["event_type"] = "SIGNAL_CONFIRMATION_TRIAL"
                    trial["receiver_role"] = rlabel
                    trials.append(trial)
                    context_matrix.append({
                        "specimen_id": sid,
                        "seed": seed,
                        "receiver": receiver,
                        "context": s0["context_label"],
                        "levels": trial["levels"],
                        "first_divergence": trial["divergences"]["NATURAL_REPLAY"],
                    })
                    receiver_matrix.append({
                        "specimen_id": sid,
                        "seed": seed,
                        "role": rlabel,
                        "receiver": receiver,
                        "L2": trial["levels"]["L2_cognition"],
                        "L3": trial["levels"]["L3_action"],
                        "L4": trial["levels"]["L4_trajectory"],
                    })

        # Specificity on first available matched S0
        if cfg.include_generic_on_confirm or cfg.include_perturbations_on_confirm:
            s0 = find_matched_s0(
                seed=17, receiver=peer, pre_action="WAIT",
                pre_selection_source="RETAINED_PREDICTION", require_no_contact=True,
                max_search=cfg.max_s0_search, min_age=cfg.min_s0_age,
            )
            if s0:
                iid = stable_id("spec", sid)
                ctrl = run_natural_replay_branch(
                    s0["snapshot"], sp, receiver_slot=s0["receiver_slot"],
                    horizon=cfg.stage_b_horizon, experiment_id=experiment_id,
                    intervention_id=iid, kind="CONTROL",
                )
                nat = run_natural_replay_branch(
                    s0["snapshot"], sp, receiver_slot=s0["receiver_slot"],
                    horizon=cfg.stage_b_horizon, experiment_id=experiment_id,
                    intervention_id=iid, kind="NATURAL_REPLAY", target="PEER",
                )
                if cfg.include_generic_on_confirm:
                    gen = run_generic_matched_energy(
                        s0["snapshot"], sp, receiver_slot=s0["receiver_slot"],
                        horizon=cfg.stage_b_horizon, experiment_id=experiment_id,
                        intervention_id=iid,
                    )
                    d_nat = first_divergences(ctrl, nat)
                    d_gen = first_divergences(ctrl, gen)
                    distinguishable = (
                        d_nat.get("cognition_selection_source") != d_gen.get("cognition_selection_source")
                        or d_nat.get("action") != d_gen.get("action")
                        or d_nat.get("position") != d_gen.get("position")
                    )
                    natural_vs_generic.append({
                        "event_type": "SIGNAL_SPECIFICITY_TRIAL",
                        "specimen_id": sid,
                        "div_natural": d_nat,
                        "div_generic": d_gen,
                        "distinguishable_downstream": distinguishable
                        and (
                            d_nat.get("cognition_selection_source") is not None
                            or d_nat.get("action") is not None
                            or d_nat.get("position") is not None
                        ),
                    })
                if cfg.include_perturbations_on_confirm:
                    for mode, scale in (
                        ("ALTER_AMPLITUDE", 0.5),
                        ("ALTER_CHANNEL", 1.0),
                        ("DELAY", 1.0),
                    ):
                        alt = run_natural_replay_branch(
                            s0["snapshot"], sp, receiver_slot=s0["receiver_slot"],
                            horizon=cfg.stage_b_horizon, experiment_id=experiment_id,
                            intervention_id=iid, kind="NATURAL_REPLAY",
                            mode=mode, amplitude_scale=scale, target="PEER",
                        )
                        perturbations.append({
                            "specimen_id": sid,
                            "mode": mode,
                            "div_exact": first_divergences(ctrl, nat),
                            "div_altered": first_divergences(ctrl, alt),
                        })
                    shuf = run_shuffled_footprint_branch(
                        s0["snapshot"], sp, receiver_slot=s0["receiver_slot"],
                        horizon=cfg.stage_b_horizon, experiment_id=experiment_id,
                        intervention_id=iid,
                    )
                    perturbations.append({
                        "specimen_id": sid,
                        "mode": "SHUFFLED_FOOTPRINT",
                        "div_exact": first_divergences(ctrl, nat),
                        "div_altered": first_divergences(ctrl, shuf),
                    })

        summary = classify_from_trials(trials)
        results.append({
            "specimen_id": sid,
            "trials": trials,
            "summary": summary,
        })

    return {
        "experiment_id": experiment_id,
        "results": results,
        "context_matrix": context_matrix,
        "receiver_matrix": receiver_matrix,
        "natural_vs_generic": natural_vs_generic,
        "perturbations": perturbations,
    }


def build_downstream_candidates(
    stage_a: dict[str, Any],
    stage_b: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Candidates with matched branching divergence beyond Level 1."""
    by_sid: dict[str, dict[str, Any]] = {}
    for r in stage_a.get("results") or []:
        s = r["summary"]
        if not s.get("tags"):
            continue
        by_sid[r["specimen_id"]] = {
            "specimen_id": r["specimen_id"],
            "family_id": r.get("family_id"),
            "stage_a": s,
            "classification": list(s.get("tags") or []),
            "Level1": f"{s['n_L1']}/{s['n']}",
            "Level2": f"{s['n_L2']}/{s['n']}",
            "Level3": f"{s['n_L3']}/{s['n']}",
            "Level4": f"{s['n_L4']}/{s['n']}",
            "confirmed": False,
            "honesty": {"not_communication": True, "not_meaning": True},
        }
    if stage_b:
        for r in stage_b.get("results") or []:
            sid = r["specimen_id"]
            s = r["summary"]
            if sid not in by_sid:
                if not s.get("tags"):
                    continue
                by_sid[sid] = {
                    "specimen_id": sid,
                    "classification": list(s.get("tags") or []),
                    "honesty": {"not_communication": True},
                }
            by_sid[sid]["stage_b"] = s
            by_sid[sid]["confirmed"] = bool(s.get("tags"))
            by_sid[sid]["Level1_B"] = f"{s['n_L1']}/{s['n']}"
            by_sid[sid]["Level2_B"] = f"{s['n_L2']}/{s['n']}"
            by_sid[sid]["Level3_B"] = f"{s['n_L3']}/{s['n']}"
            by_sid[sid]["Level4_B"] = f"{s['n_L4']}/{s['n']}"
            # Keep classification from confirmation if present
            if s.get("tags"):
                by_sid[sid]["classification"] = list(s["tags"])
            elif by_sid[sid].get("confirmed") is False:
                by_sid[sid]["note"] = "Stage-A only — not confirmed"
    return list(by_sid.values())


def build_response_fingerprints_screen(
    repertoire: dict[str, Any],
    stage_a: dict[str, Any],
    stage_b: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    fps = []
    b_by = {r["specimen_id"]: r for r in (stage_b or {}).get("results") or []}
    for r in stage_a.get("results") or []:
        sid = r["specimen_id"]
        trials = list(r.get("trials") or [])
        if sid in b_by:
            trials = list(b_by[sid].get("trials") or trials)
        s = classify_from_trials(trials)
        # Latency aggregate
        latencies = []
        for t in trials:
            fd = (t.get("divergences") or {}).get("NATURAL_REPLAY") or {}
            latencies.append(fd)
        fps.append({
            "specimen_id": sid,
            "family_id": r.get("family_id"),
            "n_control": s["n"],
            "n_sham": s["n"],
            "n_replay": s["n"],
            "replay_fidelity": (r.get("fidelity_spotcheck") or {}).get("fidelity"),
            "FIELD_exposure": (
                "STRONG_REPRODUCIBLE_EFFECT" if s["frac_L1"] >= 0.99 and s["n"] >= 2
                else ("REPRODUCIBLE" if s["frac_L1"] >= 0.5 else "WEAK_OR_ABSENT")
            ),
            "selection_source": (
                "REPRODUCIBLE_DIVERGENCE" if s["frac_L2"] >= 0.5 and s["n"] >= 2
                else ("BRANCH_CAUSAL_EFFECT" if s["n_L2"] >= 1 else "NOT_ESTABLISHED")
            ),
            "action": (
                "REPRODUCIBLE_DIVERGENCE" if s["frac_L3"] >= 0.5 and s["n"] >= 2
                else ("BRANCH_CAUSAL_EFFECT" if s["n_L3"] >= 1 else "NOT_ESTABLISHED")
            ),
            "trajectory": (
                "REPRODUCIBLE_DIVERGENCE" if s["frac_L4"] >= 0.5 and s["n"] >= 2
                else ("BRANCH_CAUSAL_EFFECT" if s["n_L4"] >= 1 else "NOT_ESTABLISHED")
            ),
            "evidence_class": s["evidence_class"],
            "tags": s["tags"],
            "confidence": {
                "n_pairs": s["n"],
                "obs_frac": s["frac_L1"],
                "cog_frac": s["frac_L2"],
                "action_frac": s["frac_L3"],
                "traj_frac": s["frac_L4"],
            },
            "honesty": {"not_a_meaning_map": True, "not_communication": True},
        })
    return fps


def receiver_dependence_verdict(receiver_matrix: list[dict[str, Any]]) -> str:
    by_sid: dict[str, dict[str, list]] = defaultdict(lambda: {"SELF": [], "PEER": []})
    for row in receiver_matrix:
        by_sid[row["specimen_id"]][row["role"]].append(row)
    if not by_sid:
        return "INSUFFICIENT_EVIDENCE"
    deps = 0
    inv = 0
    compared = 0
    for sid, roles in by_sid.items():
        if not roles["SELF"] or not roles["PEER"]:
            continue
        compared += 1
        self_l2 = any(r["L2"] for r in roles["SELF"])
        peer_l2 = any(r["L2"] for r in roles["PEER"])
        self_l3 = any(r["L3"] for r in roles["SELF"])
        peer_l3 = any(r["L3"] for r in roles["PEER"])
        if (self_l2, self_l3) != (peer_l2, peer_l3):
            deps += 1
        else:
            inv += 1
    if compared == 0:
        return "INSUFFICIENT_EVIDENCE"
    if deps > inv:
        return "RECEIVER_DEPENDENT_EFFECT"
    if inv > 0 and deps == 0:
        return "RECEIVER_INVARIANT_EFFECT"
    return "INSUFFICIENT_EVIDENCE"


def context_dependence_verdict(context_matrix: list[dict[str, Any]]) -> str:
    by_sid: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for row in context_matrix:
        by_sid[row["specimen_id"]][row["context"]].append(row)
    varied = 0
    compared = 0
    for sid, ctxs in by_sid.items():
        if len(ctxs) < 2:
            continue
        compared += 1
        flags = []
        for ctx, rows in ctxs.items():
            flags.append(any((r.get("levels") or {}).get("L2_cognition") or (r.get("levels") or {}).get("L3_action") for r in rows))
        if any(flags) and not all(flags):
            varied += 1
    if compared == 0:
        return "INSUFFICIENT_EVIDENCE"
    if varied >= 1:
        return "CONTEXT_DEPENDENT_EFFECT"
    return "CONTEXT_STABLE_OR_INERT"
