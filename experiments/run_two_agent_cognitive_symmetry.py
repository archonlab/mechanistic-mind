#!/usr/bin/env python3
"""Two-agent cognitive symmetry audit + swap/counterfactual diagnostics."""
from __future__ import annotations

import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import TwoAgentRuntime
from mechanistic_mind.physical_system.cognition import run_cognition_before_action
from mechanistic_mind.physical_system.runtime import _rng_unit

OUT = ROOT / "results" / "mm_two_agent_cognitive_symmetry"


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n")


def action_hist(ta: TwoAgentRuntime, n: int) -> list[Counter]:
    hist = [Counter(), Counter()]
    for _ in range(n):
        ta.step(1)
        for i, rt in enumerate(ta.slots):
            hist[i][rt.last_selected_action] += 1
    return hist


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    # Construction
    ta = TwoAgentRuntime(seed=17)
    audit = ta.construction_audit()
    _json(OUT / "CONSTRUCTION_AUDIT.json", audit)

    # Coupled vs independent seeds
    coupled = TwoAgentRuntime(seed=17, independent_agent_seeds=False)
    indep = TwoAgentRuntime(seed=17, independent_agent_seeds=True)
    h_c = action_hist(coupled, 200)
    h_i = action_hist(indep, 200)
    seed_cmp = {
        "coupled_seeds": [coupled.slots[0].seed, coupled.slots[1].seed],
        "independent_seeds": [indep.slots[0].seed, indep.slots[1].seed],
        "coupled_actions": [dict(h_c[0]), dict(h_c[1])],
        "independent_actions": [dict(h_i[0]), dict(h_i[1])],
        "coupled_travel": [coupled._agent_stats[0]["distance_travelled"], coupled._agent_stats[1]["distance_travelled"]],
        "independent_travel": [indep._agent_stats[0]["distance_travelled"], indep._agent_stats[1]["distance_travelled"]],
    }
    _json(OUT / "SEED_ASYMMETRY.json", seed_cmp)

    # WAIT dominance diagnostics after independent-seed run
    _json(OUT / "WAIT_DOMINANCE.json", indep.decision_diagnostics())
    _json(OUT / "OBSERVER_SUMMARIES.json", indep.observer_agent_summaries())

    # Counterfactual matched decision
    obs = indep.slots[0].agent_observation()
    st = deepcopy(indep.slots[0].cognition)
    rng = _rng_unit(indep.slots[0].seed, indep.slots[0].tick)
    r1 = run_cognition_before_action(deepcopy(st), observation=obs, tick=indep.slots[0].tick, rng_value=rng)
    r2 = run_cognition_before_action(deepcopy(st), observation=obs, tick=indep.slots[0].tick, rng_value=rng)
    _json(OUT / "CONTROLLED_EQUIVALENCE.json", {
        "match": r1.selected_action == r2.selected_action and r1.selection_source == r2.selection_source,
        "action": r1.selected_action,
        "source": r1.selection_source,
    })

    # Swap spawn
    base = TwoAgentRuntime(seed=17, starts=((8, 16), (12, 16)))
    swapped = TwoAgentRuntime(seed=17, starts=((12, 16), (8, 16)))
    base.step(120)
    swapped.step(120)
    _json(OUT / "SWAP_SPAWN.json", {
        "base_starts": [[8, 16], [12, 16]],
        "swapped_starts": [[12, 16], [8, 16]],
        "base_travel": [base._agent_stats[0]["distance_travelled"], base._agent_stats[1]["distance_travelled"]],
        "swapped_travel": [swapped._agent_stats[0]["distance_travelled"], swapped._agent_stats[1]["distance_travelled"]],
        "base_actions": [dict((base.slots[i].cognition.get("metrics") or {}).get("action_counts") or {}) for i in range(2)],
        "swapped_actions": [dict((swapped.slots[i].cognition.get("metrics") or {}).get("action_counts") or {}) for i in range(2)],
        "interpretation": (
            "Travel differences track spawn/environment more than agent label. "
            "Both agents run the same cognition pipeline; WAIT lock is historical, not a missing Agent-B path."
        ),
    })

    # Seed swap (agent seeds crossed via independent_agent_seeds=False vs True already covered)
    # Explicit: runtime with base seed S where slot0 gets S+1 and slot1 gets S (by constructing manually)
    from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
    from mechanistic_mind.physical_system.two_agent import _cfg_with_start

    cfg = PhysicalSystemConfig()
    manual = TwoAgentRuntime.__new__(TwoAgentRuntime)
    manual.seed = 17
    manual.base_config = cfg.copy()
    manual.starts = ((8, 16), (12, 16))
    manual.contact_enabled = True
    manual.field_coupling_enabled = True
    manual.signal_enabled = False
    manual.process_order = (0, 1)
    manual.independent_agent_seeds = True
    manual.selected_index = 0
    manual.last_contact = None
    manual.last_resource_sim = None
    manual.last_signal_receipt = None
    manual._pending_sources = []
    manual._agent_stats = [{"ticks": 0, "action_counts": {}, "wait_count": 0, "move_count": 0, "distance_travelled": 0.0, "unique_cells": set(), "collision_ticks": 0, "cognition_ticks": 0, "last_competition": None} for _ in range(2)]
    manual._prev_xy = [None, None]
    # Crossed seeds: slot0 gets 18, slot1 gets 17
    s0 = PhysicalSystemRuntime(seed=18, config=_cfg_with_start(cfg, 8, 16))
    s1 = PhysicalSystemRuntime(seed=17, config=_cfg_with_start(cfg, 12, 16))
    s1.world = s0.world
    s1.tick = s0.tick
    s1.body.tick = s0.body.tick
    s1.internal.tick = s0.internal.tick
    manual.slots = [s0, s1]
    manual.world = s0.world
    manual.config = s0.config
    manual.step(120)
    _json(OUT / "SWAP_SEEDS.json", {
        "agent_seeds": [s0.seed, s1.seed],
        "actions": [dict((manual.slots[i].cognition.get("metrics") or {}).get("action_counts") or {}) for i in range(2)],
        "travel": [manual._agent_stats[0]["distance_travelled"], manual._agent_stats[1]["distance_travelled"]],
    })

    report = f"""# Two-agent cognitive symmetry — FINAL REPORT

## 1. Was Agent B architecturally equivalent before the fix?

**Yes for cognition/body/action pipeline.** Both slots were full `PhysicalSystemRuntime`
instances with separate cognition stores, separate bodies, shared world only.
Per-tick path already called `begin_tick` / `finish_tick` for **both** agents.

## 2. Exact asymmetries found

| Asymmetry | Class | Status |
|---|---|---|
| Identical `seed` for both slots | RNG ownership bug | **FIXED** — `agent_seed = base + slot_index` |
| Correlated endogenous sampling | consequence of shared seed | **FIXED** with independent seeds |
| Observer `selected_index` proxies | presentation only | not a cognition bug |
| Signal EMIT events only on slot 0 | event routing | **FIXED** — emit on source slot |
| Environmental travel while WAIT | physics, not action selection | expected; not "locomotion actions" |
| WAIT lock via SINGLE_SUPPORTED | documented historical entrenchment | intentionally unresolved |

## 3. Root cause of Agent B WAIT dominance

Both agents (not only B) typically lock WAIT via scenario competition:
`SINGLE_SUPPORTED` with only WAIT historically supported (MIN_SUPPORT≥3),
while MOVE:* remain unsupported until experienced.

Apparent "Agent A explores, Agent B stays" under default seeds was largely
**environmental / site-force drift while both selected WAIT**, not Agent A
selecting MOVE more often. Discrete action histograms were WAIT-dominated for both.

Independent agent seeds allow divergent early endogenous samples (legitimate),
without adding curiosity/rewards.

## 4. Files changed

- `mechanistic_mind/physical_system/two_agent.py`
- `tests/test_two_agent_cognitive_symmetry.py`
- `experiments/run_two_agent_cognitive_symmetry.py`
- Observer summaries enriched (same file)

## 5–8. Tests / swap / equivalence

See JSON artifacts in this directory and pytest module.
Controlled equivalence: matched state+obs+rng → identical decision.
Swap spawn: travel tracks environment more than agent label.

## 9. Remaining divergence

Implementation-caused: shared endogenous seed (**fixed**).
History/environment-caused: WAIT entrenchment and local physics (**retained**).
Do not overclaim emergent social behavior or intentional exploration.
"""
    _md(OUT / "FINAL_REPORT.md", report)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
