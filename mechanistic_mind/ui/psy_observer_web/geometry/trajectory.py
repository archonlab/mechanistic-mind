"""Trajectory segments and bounded geometry episodes (Observer-only)."""
from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any

from mechanistic_mind.ui.psy_observer_web.geometry.metrics import evidence_class


def stable_episode_id(
    *,
    run_id: str,
    generation: int | None,
    agent_id: str,
    kind: str,
    start_tick: int,
    end_tick: int,
) -> str:
    raw = f"{run_id}|{generation}|{agent_id}|{kind}|{start_tick}|{end_tick}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"geo-{kind.lower()}-{digest}"


def detect_episodes(
    steps: list[dict[str, Any]],
    *,
    run_id: str = "unknown",
    generation: int | None = None,
    width: int = 32,
    height: int = 32,
) -> list[dict[str, Any]]:
    """Detect bounded geometry episodes from step records.

    Objective criteria only — no intention language.
    """
    episodes: list[dict[str, Any]] = []
    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for st in steps:
        by_agent[str(st.get("agent_id") or "agent_0")].append(st)

    for aid, seq in by_agent.items():
        seq = sorted(seq, key=lambda s: int(s.get("tick") or 0))
        episodes.extend(
            _agent_episodes(seq, run_id=run_id, generation=generation, agent_id=aid,
                            width=width, height=height)
        )
    episodes.sort(key=lambda e: (int(e["start_tick"]), e["agent_id"], e["kind"]))
    return episodes


def _agent_episodes(
    seq: list[dict[str, Any]],
    *,
    run_id: str,
    generation: int | None,
    agent_id: str,
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    # --- consecutive opposing MOVE streaks ---
    i = 0
    while i < len(seq):
        st = seq[i]
        if st.get("outcome") != "OPPOSING_DISPLACEMENT":
            i += 1
            continue
        j = i
        while j < len(seq) and seq[j].get("outcome") == "OPPOSING_DISPLACEMENT":
            # same action preferred but allow mixed MOVE opposing
            j += 1
        if j - i >= 3:
            out.append(
                _episode(
                    kind="TRAVERSAL_REVERSAL",
                    run_id=run_id,
                    generation=generation,
                    agent_id=agent_id,
                    steps=seq[i:j],
                    criterion="≥3 consecutive MOVE outcomes with action_alignment ≤ -0.3",
                )
            )
        i = max(j, i + 1)

    # --- strong single-step deflection ---
    for st in seq:
        align = st.get("action_alignment")
        if align is not None and float(align) <= -0.7 and float(st.get("disp_mag") or 0) > 0.05:
            out.append(
                _episode(
                    kind="STRONG_DEFLECTION",
                    run_id=run_id,
                    generation=generation,
                    agent_id=agent_id,
                    steps=[st],
                    criterion="single MOVE with alignment ≤ -0.7 and |Δ| > 0.05",
                )
            )

    # --- contact-conditioned opposing ---
    for st in seq:
        if st.get("contact") and st.get("outcome") == "OPPOSING_DISPLACEMENT":
            out.append(
                _episode(
                    kind="CONTACT_CONDITIONED_TRAVERSAL",
                    run_id=run_id,
                    generation=generation,
                    agent_id=agent_id,
                    steps=[st],
                    criterion="contact=True and opposing displacement on MOVE",
                )
            )

    # --- aligned success after opposing in same cell/action ---
    cell_action_hist: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for st in seq:
        cell = st.get("cell") or [0, 0]
        act = str(st.get("action") or "")
        if not act.startswith("MOVE:"):
            continue
        cell_action_hist[(int(cell[0]), int(cell[1]), act)].append(st)
    for key, hist in cell_action_hist.items():
        saw_oppose = False
        for st in hist:
            if st.get("outcome") == "OPPOSING_DISPLACEMENT":
                saw_oppose = True
            elif saw_oppose and st.get("outcome") == "ALIGNED_TRAVERSAL":
                out.append(
                    _episode(
                        kind="TRAVERSAL_SUCCESS",
                        run_id=run_id,
                        generation=generation,
                        agent_id=agent_id,
                        steps=[st],
                        criterion=(
                            f"ALIGNED_TRAVERSAL after prior OPPOSING at cell={key[0:2]} action={key[2]}"
                        ),
                        extra={"cell": list(key[0:2]), "action": key[2]},
                    )
                )
                break

    # --- recurrent route: same cell×action ≥ 8 MOVE attempts ---
    for key, hist in cell_action_hist.items():
        if len(hist) >= 8:
            out.append(
                _episode(
                    kind="RECURRENT_ROUTE",
                    run_id=run_id,
                    generation=generation,
                    agent_id=agent_id,
                    steps=hist,
                    criterion="≥8 MOVE attempts from same cell with same requested action",
                    extra={"cell": list(key[0:2]), "action": key[2], "attempts": len(hist)},
                )
            )

    # --- large spatial departure: rolling net |Δ| from window start > 8 ---
    window = 40
    for i in range(0, max(0, len(seq) - window), window // 2):
        chunk = seq[i : i + window]
        if len(chunk) < window // 2:
            continue
        x0, y0 = float(chunk[0]["x0"]), float(chunk[0]["y0"])
        x1, y1 = float(chunk[-1]["x1"]), float(chunk[-1]["y1"])
        from mechanistic_mind.ui.psy_observer_web.geometry.metrics import realized_displacement

        _, _, mag = realized_displacement(x0, y0, x1, y1, width=width, height=height)
        if mag >= 8.0:
            out.append(
                _episode(
                    kind="LARGE_SPATIAL_DEPARTURE",
                    run_id=run_id,
                    generation=generation,
                    agent_id=agent_id,
                    steps=chunk,
                    criterion=f"net toroidal displacement ≥ 8 over ~{len(chunk)} ticks",
                    extra={"net_disp_mag": mag},
                )
            )

    return out


def _episode(
    *,
    kind: str,
    run_id: str,
    generation: int | None,
    agent_id: str,
    steps: list[dict[str, Any]],
    criterion: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    start = int(steps[0]["tick"])
    end = int(steps[-1]["tick"])
    eid = stable_episode_id(
        run_id=run_id,
        generation=generation,
        agent_id=agent_id,
        kind=kind,
        start_tick=start,
        end_tick=end,
    )
    actions = [s.get("action") for s in steps]
    dx = sum(float(s.get("dx") or 0.0) for s in steps)
    dy = sum(float(s.get("dy") or 0.0) for s in steps)
    contacts = sum(1 for s in steps if s.get("contact"))
    return {
        "episode_id": eid,
        "kind": kind,
        "run_id": run_id,
        "generation": generation,
        "agent_id": agent_id,
        "start_tick": start,
        "end_tick": end,
        "start_position": [float(steps[0]["x0"]), float(steps[0]["y0"])],
        "end_position": [float(steps[-1]["x1"]), float(steps[-1]["y1"])],
        "requested_action_summary": {
            "first": actions[0],
            "last": actions[-1],
            "unique": sorted({str(a) for a in actions if a}),
            "n_steps": len(steps),
        },
        "realized_displacement": {"dx_sum": dx, "dy_sum": dy},
        "physical_context": {
            "criterion": criterion,
            "mean_alignment": _mean([s.get("action_alignment") for s in steps]),
            "mean_disp_mag": _mean([s.get("disp_mag") for s in steps]),
            **(extra or {}),
        },
        "contact_context": {
            "contact_steps": contacts,
            "contact_fraction": contacts / len(steps) if steps else 0.0,
        },
        "evidence_class": evidence_class(len(steps)),
        "derivation": "Observer geometry interpreter BETA2-GEO-01; trajectory-only",
        "provenance": "scientific_timeline consecutive poses + requested action",
    }


def _mean(xs: list[Any]) -> float | None:
    vals = [float(x) for x in xs if x is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)
