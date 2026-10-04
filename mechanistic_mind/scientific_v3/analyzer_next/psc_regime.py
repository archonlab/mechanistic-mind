"""PSC regime reconstruction from saved DecisionReceipts and snapshot receipts.

Does not invent a transition. Distinguishes configured schedule, effective
runtime state, scientific provenance, and Analyzer inference.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                yield row


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def format_psc_regime_section(payload: dict[str, Any] | None) -> str:
    p = payload or {}
    lines = [
        "PSC REGIMES",
        "===========",
        "Layers: configured schedule ≠ effective runtime state ≠ scientific transition provenance ≠ Analyzer inference.",
        f"Configured schedule psc_off_ticks: {(p.get('configured_schedule') or {}).get('psc_off_ticks')}",
        f"Initially OFF: {(p.get('effective_runtime_state') or {}).get('initially_off')}",
        f"Enabled-at tick: {(p.get('effective_runtime_state') or {}).get('enabled_at_tick')}",
        f"Withhold gate opened at tick: {(p.get('effective_runtime_state') or {}).get('withhold_gate_opened_at_tick')}",
        f"SMC-withhold transition count: {(p.get('effective_runtime_state') or {}).get('transition_count')}",
        f"Provenance: {((p.get('scientific_transition_provenance') or {}).get('authority'))}",
        "",
    ]
    for reg in p.get("regimes") or []:
        lines.append(
            f"- ticks {reg.get('ticks')}: {reg.get('effective_psc')} / {reg.get('smc_withhold') or reg.get('note') or ''}"
        )
    lines.append("")
    lines.append(str(p.get("hss_note") or ""))
    absent = p.get("absent_evidence") or []
    if absent:
        lines.append("Absent evidence: " + "; ".join(absent))
    inf = (p.get("analyzer_inference") or {}).get("note")
    if inf:
        lines.append(str(inf))
    lines.append("")
    return "\n".join(lines)


def reconstruct_psc_regime(run_dir: Path, cutoff_tick: int | None = None) -> dict[str, Any]:
    run_dir = Path(run_dir)
    configured_off: int | None = None
    snapshot_activation: dict[str, Any] | None = None
    snapshot_withhold: dict[str, Any] | None = None
    snap = _load_json(run_dir / "physical_system_snapshot.json")
    agents = snap.get("agents") if isinstance(snap.get("agents"), list) else []
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        sched = agent.get("psc_schedule")
        if not isinstance(sched, dict):
            cog = (agent.get("config") or {}).get("cognition") if isinstance(agent.get("config"), dict) else {}
            if isinstance(cog, dict) and cog.get("psc_off_ticks") is not None:
                configured_off = int(cog["psc_off_ticks"])
            continue
        if sched.get("psc_off_ticks") is not None:
            configured_off = int(sched["psc_off_ticks"])
        act = sched.get("psc_activation")
        if isinstance(act, dict) and snapshot_activation is None:
            snapshot_activation = dict(act)
        wo = sched.get("psc_withhold_open")
        if isinstance(wo, dict) and snapshot_withhold is None:
            snapshot_withhold = dict(wo)

    smc_by_tick: dict[int, bool] = {}
    path_by_tick: dict[int, str] = {}
    for row in _iter_jsonl(run_dir / "scientific_decisions.jsonl"):
        try:
            tick = int(row.get("tick"))
        except (TypeError, ValueError):
            continue
        if cutoff_tick is not None and tick > int(cutoff_tick):
            continue
        smc = row.get("sensorimotor_consequence")
        withheld = None
        if isinstance(smc, dict) and "withheld_from_psc" in smc:
            withheld = bool(smc.get("withheld_from_psc"))
        if withheld is not None and tick not in smc_by_tick:
            smc_by_tick[tick] = withheld
        if tick not in path_by_tick and row.get("selection_path"):
            path_by_tick[tick] = str(row.get("selection_path"))

    transitions: list[dict[str, Any]] = []
    prev: bool | None = None
    for tick in sorted(smc_by_tick):
        val = smc_by_tick[tick]
        if prev is not None and val != prev:
            transitions.append({
                "tick": tick,
                "sensorimotor_consequence_withheld_from_psc": {"from": prev, "to": val},
                "selection_path_at_tick": path_by_tick.get(tick),
                "source": "scientific_decisions.jsonl DecisionReceipt.sensorimotor_consequence.withheld_from_psc",
            })
        prev = val

    enabled_at = None
    if len(transitions) == 1 and transitions[0]["sensorimotor_consequence_withheld_from_psc"]["to"] is False:
        enabled_at = int(transitions[0]["tick"])
    elif snapshot_activation and snapshot_activation.get("tick") is not None:
        # Snapshot receipt is saved evidence but is an end-of-run object.
        # Only treat as enabled_at when decision stream agrees or is empty.
        if not smc_by_tick:
            enabled_at = int(snapshot_activation["tick"])

    withhold_open_at = None
    if snapshot_withhold and snapshot_withhold.get("tick") is not None:
        withhold_open_at = int(snapshot_withhold["tick"])
    if enabled_at is not None:
        withhold_open_at = enabled_at if withhold_open_at is None else withhold_open_at

    ticks = sorted(smc_by_tick)
    tmin = ticks[0] if ticks else None
    tmax = ticks[-1] if ticks else None

    regimes: list[dict[str, Any]] = []
    if enabled_at is not None and tmin is not None and tmax is not None:
        off_end = enabled_at - 1
        if off_end >= tmin:
            regimes.append({
                "ticks": f"{tmin}–{off_end}",
                "tick_start": tmin,
                "tick_end": off_end,
                "effective_psc": "OFF",
                "smc_withhold": "CLOSED (sensorimotor_consequence.withheld_from_psc=true)",
            })
        regimes.append({
            "ticks": f"{enabled_at}–{tmax}",
            "tick_start": enabled_at,
            "tick_end": tmax,
            "effective_psc": "ON",
            "smc_withhold": "OPEN (sensorimotor_consequence.withheld_from_psc=false)",
        })
    elif tmin is not None:
        all_withheld = all(smc_by_tick[t] for t in ticks)
        all_open = all(not smc_by_tick[t] for t in ticks)
        regimes.append({
            "ticks": f"{tmin}–{tmax}",
            "effective_psc": "UNKNOWN" if not (all_withheld or all_open) else ("OFF" if all_withheld else "ON"),
            "note": "No single SMC-withhold transition reconstructed from DecisionReceipts.",
        })

    missing: list[str] = []
    if configured_off is None:
        missing.append("configured psc_off_ticks not found in snapshot cognition/psc_schedule")
    if not snapshot_activation:
        missing.append("snapshot psc_activation receipt not present")
    if not smc_by_tick:
        missing.append("DecisionReceipt SMC withhold series not present")

    provenance = "scientific_decisions.jsonl + physical_system_snapshot.json psc_schedule"
    return {
        "schema": "mm.analyzer.psc_regime.v1",
        "configured_schedule": {
            "psc_off_ticks": configured_off,
            "layer": "frozen_initial_and_snapshot_schedule",
            "source": "physical_system_snapshot.json agents[].psc_schedule.psc_off_ticks",
        },
        "effective_runtime_state": {
            "enabled_at_tick": enabled_at,
            "withhold_gate_opened_at_tick": withhold_open_at,
            "transition_count": len(transitions),
            "initially_off": True if (tmin is not None and smc_by_tick.get(tmin) is True) else (configured_off is not None),
        },
        "scientific_transition_provenance": {
            "decision_smc_withhold_transitions": transitions,
            "snapshot_psc_activation": snapshot_activation,
            "snapshot_smc_withhold_open": snapshot_withhold,
            "authority": provenance,
        },
        "analyzer_inference": {
            "note": "Analyzer infers regime boundaries from recorded SMC withhold and snapshot receipts; it does not replay PSC.",
        },
        "regimes": regimes,
        "hss_withhold_is_not_psc_off": True,
        "hss_note": (
            "historical_sensorimotor_selection.withheld_from_psc is the O-prime history gate. "
            "It must not be reported as PSC remaining OFF."
        ),
        "absent_evidence": missing,
        "tick_range_from_decisions": [tmin, tmax],
    }
