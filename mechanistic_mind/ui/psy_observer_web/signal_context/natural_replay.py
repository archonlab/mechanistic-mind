"""BETA2-SIGINT-03: natural signal specimens × faithful replay × echo probes.

Reuses SIGINT-02 matched branching and ``inject_source`` → ``_deposit`` path.
Observer/experimenter only — cognition never sees specimen/replay metadata.
"""
from __future__ import annotations

import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Literal

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    TRIGGER_SHAM,
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

TRIGGER_NATURAL_REPLAY = "NATURAL_SIGNAL_REPLAY"
NOT_RECORDED = "NOT_RECORDED"
NOT_RECONSTRUCTABLE = "NOT_RECONSTRUCTABLE"

ReplayFidelity = Literal[
    "EXACT_PHYSICAL_REPLAY",
    "APPROXIMATE_PHYSICAL_REPLAY",
    "INSUFFICIENT_RECONSTRUCTION",
]


@dataclass(frozen=True)
class NaturalSignalSpecimen:
    """Immutable physical recording of a natural FIELD deposit. Not a message."""

    specimen_id: str
    source_run_id: str
    source_emission_id: str
    source_tick: int
    emitter_agent_id: str
    emitter_body_id: str
    channel: str
    trigger: str
    origin_kind: str
    amplitude: float | str
    cells: tuple[tuple[int, int], ...] | str
    x: float | str
    y: float | str
    physical_quantity: str
    physical_quantity_value: float | str
    reconstruction_completeness: str
    provenance: str
    captured_at_mono: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if isinstance(self.cells, tuple):
            d["cells"] = [[int(a), int(b)] for a, b in self.cells]
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "NaturalSignalSpecimen":
        cells = raw.get("cells")
        if isinstance(cells, list) and cells and isinstance(cells[0], (list, tuple)):
            cells_t: tuple[tuple[int, int], ...] | str = tuple(
                (int(c[0]), int(c[1])) for c in cells
            )
        elif cells in (None, "", NOT_RECORDED, NOT_RECONSTRUCTABLE):
            cells_t = str(cells or NOT_RECORDED)
        else:
            cells_t = NOT_RECONSTRUCTABLE
        return cls(
            specimen_id=str(raw["specimen_id"]),
            source_run_id=str(raw.get("source_run_id") or NOT_RECORDED),
            source_emission_id=str(raw.get("source_emission_id") or NOT_RECORDED),
            source_tick=int(raw.get("source_tick") or -1),
            emitter_agent_id=str(raw.get("emitter_agent_id") or NOT_RECORDED),
            emitter_body_id=str(raw.get("emitter_body_id") or NOT_RECORDED),
            channel=str(raw.get("channel") or "A").upper().replace("FIELD_", ""),
            trigger=str(raw.get("trigger") or NOT_RECORDED),
            origin_kind=str(raw.get("origin_kind") or NOT_RECORDED),
            amplitude=raw.get("amplitude", NOT_RECORDED),
            cells=cells_t,
            x=raw.get("x", NOT_RECORDED),
            y=raw.get("y", NOT_RECORDED),
            physical_quantity=str(raw.get("physical_quantity") or NOT_RECORDED),
            physical_quantity_value=raw.get("physical_quantity_value", NOT_RECORDED),
            reconstruction_completeness=str(
                raw.get("reconstruction_completeness") or NOT_RECONSTRUCTABLE
            ),
            provenance=str(raw.get("provenance") or "NATURAL_EMISSION"),
            captured_at_mono=float(raw.get("captured_at_mono") or 0.0),
        )


def _amp(specimen: NaturalSignalSpecimen) -> float | None:
    try:
        return float(specimen.amplitude)
    except (TypeError, ValueError):
        return None


def specimen_from_emission_evidence(
    evidence: dict[str, Any],
    *,
    run_id: str = "live",
    tick: int | None = None,
) -> NaturalSignalSpecimen:
    cells_raw = evidence.get("cells")
    if isinstance(cells_raw, list) and cells_raw:
        cells: tuple[tuple[int, int], ...] | str = tuple(
            (int(c[0]), int(c[1])) for c in cells_raw
        )
        completeness = "CELLS_AND_AMPLITUDE"
    else:
        cells = NOT_RECORDED
        completeness = "POSITION_ONLY"
    amp = evidence.get("amplitude", evidence.get("realized", NOT_RECORDED))
    if amp is None:
        amp = NOT_RECORDED
        if completeness == "CELLS_AND_AMPLITUDE":
            completeness = "CELLS_ONLY"
    elif cells == NOT_RECORDED:
        completeness = "AMPLITUDE_POSITION"
    eid = str(evidence.get("emission_id") or NOT_RECORDED)
    t = int(tick if tick is not None else evidence.get("tick") or evidence.get("originating_tick") or -1)
    sid = stable_id("nspec", run_id, eid, t, evidence.get("channel"), amp)
    if cells == NOT_RECORDED and amp == NOT_RECORDED:
        completeness = NOT_RECONSTRUCTABLE
    return NaturalSignalSpecimen(
        specimen_id=sid,
        source_run_id=str(run_id),
        source_emission_id=eid,
        source_tick=t,
        emitter_agent_id=str(evidence.get("emitter_agent_id") or NOT_RECORDED),
        emitter_body_id=str(evidence.get("emitter_body_id") or NOT_RECORDED),
        channel=str(evidence.get("channel") or "A").upper().replace("FIELD_", ""),
        trigger=str(evidence.get("trigger") or NOT_RECORDED),
        origin_kind=str(evidence.get("origin_kind") or NOT_RECORDED),
        amplitude=amp if not isinstance(amp, (int, float)) else float(amp),
        cells=cells,
        x=evidence.get("x", NOT_RECORDED),
        y=evidence.get("y", NOT_RECORDED),
        physical_quantity=str(evidence.get("physical_quantity") or NOT_RECORDED),
        physical_quantity_value=evidence.get("physical_quantity_value", NOT_RECORDED),
        reconstruction_completeness=completeness,
        provenance="NATURAL_EMISSION",
        captured_at_mono=time.monotonic(),
    )


class NaturalSignalLibrary:
    def __init__(self, *, maxlen: int = 256) -> None:
        self.maxlen = int(maxlen)
        self._by_id: dict[str, NaturalSignalSpecimen] = {}
        self._order: list[str] = []

    def add(self, specimen: NaturalSignalSpecimen) -> NaturalSignalSpecimen:
        if specimen.specimen_id in self._by_id:
            return self._by_id[specimen.specimen_id]
        self._by_id[specimen.specimen_id] = specimen
        self._order.append(specimen.specimen_id)
        while len(self._order) > self.maxlen:
            old = self._order.pop(0)
            self._by_id.pop(old, None)
        return specimen

    def get(self, specimen_id: str) -> NaturalSignalSpecimen | None:
        return self._by_id.get(specimen_id)

    def list(self, *, channel: str | None = None, limit: int = 64) -> list[dict[str, Any]]:
        out = []
        for sid in reversed(self._order):
            s = self._by_id[sid]
            if channel and s.channel != str(channel).upper().replace("FIELD_", ""):
                continue
            out.append(s.to_dict())
            if len(out) >= limit:
                break
        return out

    def to_jsonable(self) -> list[dict[str, Any]]:
        return [self._by_id[sid].to_dict() for sid in self._order]


def queue_natural_replay(
    rt: TwoAgentRuntime,
    specimen: NaturalSignalSpecimen,
    *,
    mode: str = "EXACT",
    amplitude_scale: float = 1.0,
    channel_override: str | None = None,
    target: str = "LOCATION",
    receiver_slot: int | None = None,
    sham: bool = False,
    observer_source_id: str = "natural_replay",
) -> dict[str, Any]:
    amp = _amp(specimen)
    cells: list[tuple[int, int]] | None = None
    if isinstance(specimen.cells, tuple) and specimen.cells:
        cells = list(specimen.cells)
    ch = (channel_override or specimen.channel or "A").upper().replace("FIELD_", "")
    if mode == "ALTER_CHANNEL":
        ch = "B" if ch == "A" else "A"
    if amp is None:
        return {
            "accepted": False,
            "error": "INSUFFICIENT_RECONSTRUCTION",
            "reconstruction_completeness": specimen.reconstruction_completeness,
        }
    if mode == "ALTER_AMPLITUDE":
        amp = float(amp) * float(amplitude_scale)
    if sham:
        amp = 0.0
    if target in ("SELF", "PEER") and receiver_slot is not None:
        cells = receiver_footprint_cells(rt, int(receiver_slot))
    elif cells is None:
        try:
            iy = int(float(specimen.y))
            ix = int(float(specimen.x))
            cells = [(iy, ix)]
        except (TypeError, ValueError):
            return {
                "accepted": False,
                "error": "INSUFFICIENT_RECONSTRUCTION",
                "note": "No cells and no usable x,y",
            }
    delay_ticks = 3 if mode == "DELAY" else 0
    trigger = TRIGGER_SHAM if sham else TRIGGER_NATURAL_REPLAY
    rt.inject_source(
        channel=ch,
        amplitude=float(amp),
        cells=cells,
        trigger=trigger,
        observer_source_id=observer_source_id,
    )
    return {
        "accepted": True,
        "channel": ch,
        "amplitude": float(amp),
        "n_cells": len(cells),
        "cells": [[a, b] for a, b in cells],
        "trigger": trigger,
        "mode": mode,
        "target": target,
        "specimen_id": specimen.specimen_id,
        "delay_ticks": delay_ticks,
        "live_delay_note": (
            "UNCONTROLLED_LIVE_REPLAY: DELAY not sequenced on LIVE path; "
            "use matched branching for temporal DELAY"
            if mode == "DELAY"
            else None
        ),
    }


def measure_replay_fidelity(
    specimen: NaturalSignalSpecimen,
    *,
    replayed_channel: str,
    replayed_amplitude: float,
    replayed_cells: list[tuple[int, int]],
    receiver_field_before: dict[str, float],
    receiver_field_after: dict[str, float],
) -> dict[str, Any]:
    amp = _amp(specimen)
    issues = []
    if amp is None:
        return {
            "fidelity": "INSUFFICIENT_RECONSTRUCTION",
            "issues": ["amplitude NOT_RECORDED"],
            "channel_match": False,
            "amplitude_rel_err": None,
            "cells_jaccard": None,
            "exposure_delta": None,
        }
    ch_ok = str(replayed_channel).upper() == str(specimen.channel).upper()
    if not ch_ok:
        issues.append("channel_mismatch")
    rel_err = abs(float(replayed_amplitude) - float(amp)) / max(1e-9, abs(float(amp)))
    if rel_err > 1e-6:
        issues.append(f"amplitude_rel_err={rel_err:.4g}")
    cells_j = None
    if isinstance(specimen.cells, tuple) and specimen.cells:
        a = set(specimen.cells)
        b = set((int(c[0]), int(c[1])) for c in replayed_cells)
        inter = len(a & b)
        union = len(a | b) or 1
        cells_j = inter / union
        if cells_j < 1.0:
            issues.append(f"cells_jaccard={cells_j:.4g}")
    else:
        issues.append("original_cells_not_recorded")
    ch_key = f"FIELD_{specimen.channel}"
    exp_delta = float(receiver_field_after.get(ch_key, 0.0)) - float(
        receiver_field_before.get(ch_key, 0.0)
    )
    if cells_j == 1.0 and rel_err <= 1e-6 and ch_ok and exp_delta > 0:
        fidelity: ReplayFidelity = "EXACT_PHYSICAL_REPLAY"
    elif ch_ok and exp_delta > 0 and (cells_j is None or cells_j >= 0.5) and rel_err <= 0.25:
        fidelity = "APPROXIMATE_PHYSICAL_REPLAY"
    elif amp is not None and ch_ok:
        fidelity = "APPROXIMATE_PHYSICAL_REPLAY" if exp_delta > 0 else "INSUFFICIENT_RECONSTRUCTION"
    else:
        fidelity = "INSUFFICIENT_RECONSTRUCTION"
    return {
        "fidelity": fidelity,
        "issues": issues,
        "channel_match": ch_ok,
        "amplitude_rel_err": rel_err,
        "cells_jaccard": cells_j,
        "exposure_delta": exp_delta,
        "specimen_amplitude": float(amp),
        "replayed_amplitude": float(replayed_amplitude),
    }


def run_fidelity_gate(
    specimen: NaturalSignalSpecimen,
    *,
    seed: int = 17,
) -> dict[str, Any]:
    rt = make_signal_runtime(seed=seed)
    for _ in range(20):
        rt.step()
    slot = 1
    before = receiver_local_fields(rt, slot)
    q = queue_natural_replay(
        rt, specimen, mode="EXACT", target="LOCATION",
        observer_source_id="fidelity_gate",
    )
    if not q.get("accepted"):
        return {
            "accepted": False,
            "fidelity": "INSUFFICIENT_RECONSTRUCTION",
            "queue": q,
        }
    rt.step()
    after = receiver_local_fields(rt, slot)
    fid = measure_replay_fidelity(
        specimen,
        replayed_channel=str(q["channel"]),
        replayed_amplitude=float(q["amplitude"]),
        replayed_cells=[(c[0], c[1]) for c in q["cells"]],
        receiver_field_before=before,
        receiver_field_after=after,
    )
    return {"accepted": True, "queue": q, **fid, "before": before, "after": after}


def run_natural_replay_branch(
    snapshot: dict[str, Any],
    specimen: NaturalSignalSpecimen,
    *,
    receiver_slot: int,
    horizon: int = 20,
    experiment_id: str,
    intervention_id: str,
    kind: str = "NATURAL_REPLAY",
    mode: str = "EXACT",
    amplitude_scale: float = 1.0,
    target: str = "PEER",
    delay_ticks: int = 0,
) -> dict[str, Any]:
    rt = TwoAgentRuntime.restore(deepcopy(snapshot))
    pre_fp = scientific_fingerprint(rt)
    amp = _amp(specimen)
    if amp is None and kind != "CONTROL":
        return {
            "arm_id": kind,
            "kind": kind,
            "accepted": False,
            "error": "INSUFFICIENT_RECONSTRUCTION",
            "pre_fingerprint": pre_fp,
            "traces": [],
        }
    if mode == "ALTER_AMPLITUDE" and amp is not None:
        amp = float(amp) * float(amplitude_scale)
    ch = specimen.channel
    if mode == "ALTER_CHANNEL":
        ch = "B" if ch == "A" else "A"
    inject_at = int(delay_ticks) if mode == "DELAY" else int(delay_ticks)
    if mode == "DELAY" and inject_at <= 0:
        inject_at = 3
    if mode != "DELAY":
        inject_at = 0
    sham = kind == "SHAM"
    if kind == "CONTROL":
        amp = None
    traces = []
    obs_source = f"exp:{experiment_id}:{intervention_id}:{kind}"
    injected = False
    for i in range(int(horizon)):
        if amp is not None and i == inject_at and kind != "CONTROL":
            if target in ("SELF", "PEER"):
                cells = receiver_footprint_cells(rt, receiver_slot)
            elif isinstance(specimen.cells, tuple) and specimen.cells:
                cells = list(specimen.cells)
            else:
                try:
                    cells = [(int(float(specimen.y)), int(float(specimen.x)))]
                except (TypeError, ValueError):
                    cells = receiver_footprint_cells(rt, receiver_slot)
            rt.inject_source(
                channel=ch,
                amplitude=0.0 if sham else float(amp),
                cells=cells,
                trigger=TRIGGER_SHAM if sham else TRIGGER_NATURAL_REPLAY,
                observer_source_id=obs_source,
            )
            injected = True
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
        "arm_id": kind,
        "kind": kind,
        "accepted": True,
        "injected": injected,
        "channel": ch,
        "amplitude": None if amp is None else (0.0 if sham else float(amp)),
        "mode": mode,
        "target": target,
        "delay_ticks": inject_at,
        "specimen_id": specimen.specimen_id,
        "experiment_id": experiment_id,
        "intervention_id": intervention_id,
        "pre_fingerprint": pre_fp,
        "traces": traces,
    }


def capture_natural_emissions_from_runtime(
    rt: TwoAgentRuntime,
    *,
    run_id: str = "live",
    library: NaturalSignalLibrary | None = None,
) -> list[NaturalSignalSpecimen]:
    lib = library or NaturalSignalLibrary()
    out: list[NaturalSignalSpecimen] = []
    rec = rt.last_signal_receipt or {}
    for src in rec.get("sources") or []:
        trig = str(src.get("trigger") or "")
        # Skip experimenter interventions; keep body_motion / body_contact / environmental.
        if trig in (TRIGGER_SHAM, TRIGGER_NATURAL_REPLAY) or trig.startswith("EXTERNAL"):
            continue
        sp = specimen_from_emission_evidence(src, run_id=run_id, tick=int(rt.tick))
        out.append(lib.add(sp))
    return out


def run_echo_experiment(
    specimen: NaturalSignalSpecimen,
    *,
    echo_kind: str = "PEER_ECHO",
    seeds: Iterable[int] = (17, 19, 23),
    horizon: int = 18,
    include_generic: bool = True,
) -> dict[str, Any]:
    experiment_id = stable_id("echo", echo_kind, specimen.specimen_id, time.time_ns())
    emitter = specimen.emitter_agent_id
    if echo_kind == "SELF_ECHO":
        receiver = emitter if str(emitter).startswith("agent_") else "agent_0"
    else:
        receiver = "agent_1" if str(emitter).endswith("0") else "agent_0"
        if emitter in (NOT_RECORDED, "", None):
            receiver = "agent_1"

    fidelity = run_fidelity_gate(specimen)
    trials = []
    replication: dict[str, Any] = {
        "n_pairs": 0,
        "n_obs_effect": 0,
        "n_cognition_effect": 0,
        "n_action_effect": 0,
        "n_trajectory_effect": 0,
        "n_control_control_fail": 0,
        "n_pre_div": 0,
        "seeds_ok": [],
        "seeds_fail_s0": [],
    }

    for seed in seeds:
        s0 = find_matched_s0(
            seed=int(seed),
            receiver=receiver,
            pre_action="WAIT",
            pre_selection_source="RETAINED_PREDICTION",
            require_no_contact=True,
            max_search=500,
            min_age=30,
        )
        if s0 is None:
            s0 = find_matched_s0(
                seed=int(seed),
                receiver=receiver,
                pre_action="MOVE:E",
                pre_selection_source="ENDOGENOUS_VARIATION",
                require_no_contact=True,
                max_search=400,
                min_age=25,
            )
        if s0 is None:
            replication["seeds_fail_s0"].append(int(seed))
            continue
        snap = s0["snapshot"]
        rslot = int(s0["receiver_slot"])
        intervention_id = stable_id("ereplay", specimen.specimen_id, seed, s0["tick"])

        c1 = run_natural_replay_branch(
            snap, specimen, receiver_slot=rslot, horizon=horizon,
            experiment_id=experiment_id, intervention_id=intervention_id, kind="CONTROL",
        )
        c2 = run_natural_replay_branch(
            snap, specimen, receiver_slot=rslot, horizon=horizon,
            experiment_id=experiment_id, intervention_id=intervention_id, kind="CONTROL",
        )
        ctrl_eq = all(
            fingerprint_equal(a["fingerprint"], b["fingerprint"])
            for a, b in zip(c1["traces"], c2["traces"])
        )
        if not ctrl_eq:
            replication["n_control_control_fail"] += 1
        if not fingerprint_equal(c1["pre_fingerprint"], c2["pre_fingerprint"]):
            replication["n_pre_div"] += 1

        control = run_natural_replay_branch(
            snap, specimen, receiver_slot=rslot, horizon=horizon,
            experiment_id=experiment_id, intervention_id=intervention_id,
            kind="CONTROL", target="PEER",
        )
        sham = run_natural_replay_branch(
            snap, specimen, receiver_slot=rslot, horizon=horizon,
            experiment_id=experiment_id, intervention_id=intervention_id,
            kind="SHAM", target="PEER",
        )
        replay = run_natural_replay_branch(
            snap, specimen, receiver_slot=rslot, horizon=horizon,
            experiment_id=experiment_id, intervention_id=intervention_id,
            kind="NATURAL_REPLAY", target="SELF" if echo_kind == "SELF_ECHO" else "PEER",
        )
        arms: dict[str, Any] = {"CONTROL": control, "SHAM": sham, "NATURAL_REPLAY": replay}
        if include_generic and _amp(specimen) is not None:
            generic_pat = FieldPattern(
                channel="A",
                amplitude=float(_amp(specimen) or 0.7),
                duration_ticks=1,
                temporal_profile=[1.0],
            )
            gen = run_branch(
                snap,
                BranchArm("GENERIC_FIELD_A", "INTERVENTION", pattern=generic_pat),
                receiver_slot=rslot,
                horizon=horizon,
                experiment_id=experiment_id,
                intervention_id=intervention_id,
            )
            arms["GENERIC_FIELD_A"] = gen

        div_replay = first_divergences(control, replay)
        div_sham = first_divergences(control, sham)
        div_generic = (
            first_divergences(control, arms["GENERIC_FIELD_A"])
            if "GENERIC_FIELD_A" in arms
            else None
        )

        replication["n_pairs"] += 1
        if div_replay.get("observation_field") is not None:
            replication["n_obs_effect"] += 1
        if div_replay.get("cognition_selection_source") is not None:
            replication["n_cognition_effect"] += 1
        if div_replay.get("action") is not None:
            replication["n_action_effect"] += 1
        if div_replay.get("position") is not None:
            replication["n_trajectory_effect"] += 1
        replication["seeds_ok"].append(int(seed))

        natural_vs_generic = None
        if div_generic is not None:
            natural_vs_generic = {
                "replay_action_div": div_replay.get("action"),
                "generic_action_div": div_generic.get("action"),
                "replay_cog_div": div_replay.get("cognition_selection_source"),
                "generic_cog_div": div_generic.get("cognition_selection_source"),
                "distinguishable": (
                    div_replay.get("action") != div_generic.get("action")
                    or div_replay.get("cognition_selection_source")
                    != div_generic.get("cognition_selection_source")
                ),
            }

        trials.append({
            "seed": int(seed),
            "s0_tick": s0["tick"],
            "receiver": receiver,
            "echo_kind": echo_kind,
            "control_control_equal": ctrl_eq,
            "divergences": {
                "NATURAL_REPLAY": div_replay,
                "SHAM": div_sham,
                "GENERIC_FIELD_A": div_generic,
            },
            "natural_vs_generic": natural_vs_generic,
            "final_actions": {
                k: (v["traces"][-1]["action"] if v.get("traces") else None)
                for k, v in arms.items()
            },
            "any_leak": any(
                t.get("observation_leaks")
                for v in arms.values()
                for t in (v.get("traces") or [])
            ),
        })

    return {
        "experiment_id": experiment_id,
        "echo_kind": echo_kind,
        "specimen": specimen.to_dict(),
        "receiver": receiver,
        "fidelity_gate": fidelity,
        "replication": replication,
        "trials": trials,
    }


def build_response_fingerprint(
    *,
    specimen: NaturalSignalSpecimen,
    echo_result: dict[str, Any],
    context_label: str,
) -> dict[str, Any]:
    trials = echo_result.get("trials") or []
    n = len(trials)
    n_replay_obs = sum(
        1 for t in trials
        if (t.get("divergences") or {}).get("NATURAL_REPLAY", {}).get("observation_field") is not None
    )
    n_replay_cog = sum(
        1 for t in trials
        if (t.get("divergences") or {}).get("NATURAL_REPLAY", {}).get("cognition_selection_source") is not None
    )
    n_replay_act = sum(
        1 for t in trials
        if (t.get("divergences") or {}).get("NATURAL_REPLAY", {}).get("action") is not None
    )
    n_replay_traj = sum(
        1 for t in trials
        if (t.get("divergences") or {}).get("NATURAL_REPLAY", {}).get("position") is not None
    )
    n_sham_act = sum(
        1 for t in trials
        if (t.get("divergences") or {}).get("SHAM", {}).get("action") is not None
    )

    def level(n_hit: int, n_tot: int, *, sham_hit: int = 0) -> str:
        if n_tot == 0:
            return "NOT_ESTABLISHED"
        if n_hit >= max(2, (n_tot + 1) // 2) and sham_hit == 0:
            return "REPRODUCIBLE_REPLAY_EFFECT" if n_hit == n_tot else "INTERVENTION_SUPPORTED"
        if n_hit >= 1:
            return "BRANCH_CAUSAL_EFFECT"
        return "NOT_ESTABLISHED"

    fid = (echo_result.get("fidelity_gate") or {}).get("fidelity")
    return {
        "specimen_id": specimen.specimen_id,
        "channel": specimen.channel,
        "context": context_label,
        "receiver": echo_result.get("receiver"),
        "echo_kind": echo_result.get("echo_kind"),
        "n_control": n,
        "n_sham": n,
        "n_replay": n,
        "replay_fidelity": fid,
        "FIELD_exposure": (
            "STRONG_REPRODUCIBLE_EFFECT" if n_replay_obs == n and n > 0 else level(n_replay_obs, n)
        ),
        "selection_source": level(n_replay_cog, n),
        "action": level(n_replay_act, n, sham_hit=n_sham_act),
        "trajectory": level(n_replay_traj, n),
        "confidence": {
            "n_pairs": n,
            "obs_frac": n_replay_obs / max(1, n),
            "cog_frac": n_replay_cog / max(1, n),
            "action_frac": n_replay_act / max(1, n),
        },
        "honesty": {"not_a_meaning_map": True, "not_communication": True},
    }


def harvest_field_a_specimens(
    *,
    seed: int = 17,
    max_steps: int = 120,
    max_specimens: int = 8,
) -> list[NaturalSignalSpecimen]:
    lib = NaturalSignalLibrary()
    rt = make_signal_runtime(seed=seed)
    for _ in range(max_steps):
        rt.step()
        capture_natural_emissions_from_runtime(rt, run_id=f"harvest-{seed}", library=lib)
        if len(lib.list(channel="A", limit=max_specimens)) >= max_specimens:
            break
    specs = [NaturalSignalSpecimen.from_dict(d) for d in lib.list(channel="A", limit=64)]
    good = [
        s for s in specs
        if s.reconstruction_completeness in ("CELLS_AND_AMPLITUDE", "CELLS_ONLY", "AMPLITUDE_POSITION")
        and _amp(s) is not None
    ]
    return good[:max_specimens] if good else specs[:max_specimens]
