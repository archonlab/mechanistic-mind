#!/usr/bin/env python3
"""Update 4.3 — Epistemic action lockout diagnostics (controls A–F).

DIAGNOSE ONLY. Does not add curiosity/novelty/exploration bonuses.
Does not retune action economics. Policy arms restore free selection after
diagnostic interventions.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path as _PathBoot
_ROOT = _PathBoot(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "update43_epistemic_lockout_v043"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arm",
        choices=[
            "FREE_POLICY",
            "ACTION_ORDER_PERMUTATION",
            "FIRST_ACTION_INTERVENTION",
            "SHORT_FORCED_COVERAGE",
            "EXPERIENCE_ABLATION",
            "EXPERIENCE_GATED",
            "ADULT_FROM_TICK_0",
            "SYMMETRY_SMOKE",
        ],
        default="SYMMETRY_SMOKE",
    )
    parser.add_argument("--ticks", type=int, default=100)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--first-action", default="MOVE:N")
    parser.add_argument("--forced-ticks", type=int, default=8)
    parser.add_argument("--order-label", default="ALPHA")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if args.arm == "SYMMETRY_SMOKE":
        # Reuse Phase-1 unit reconstruction (no full world required).
        from mechanistic_mind.psyche.sensorimotor import (
            SensorimotorConfig,
            SensorimotorStore,
            generate_proposals,
            select_proposal,
        )
        from mechanistic_mind.research.action_epistemics import annotate_proposal_metadata

        actions = [
            "EMIT", "MOVE:N", "MOVE:E", "MOVE:S", "MOVE:W", "WAIT", "USE:obj_a",
        ]
        obs = {
            "available_actions": actions,
            "visible_objects": [
                {
                    "id": "obj_a",
                    "cue_signature": "obj_a",
                    "relative_offset": (1, 0),
                    "interaction_state": "FREE",
                    "position": (1, 0),
                }
            ],
            "interoception": {
                "energy_signal": 1.0,
                "hydration_signal": 1.0,
                "fatigue_signal": 0.0,
            },
            "position": (0, 0),
        }
        gen = generate_proposals(
            observation=obs,
            store=SensorimotorStore(),
            config=SensorimotorConfig(),
            random_value=0.17,
            values=None,
        )
        proposals = [
            annotate_proposal_metadata(p, physically_available=True)
            for p in gen["proposals"]
        ]
        sel = select_proposal(
            {"proposals": proposals},
            body=obs["interoception"],
            random_value=0.17,
        )
        payload: dict[str, Any] = {
            "arm": args.arm,
            "seed": args.seed,
            "selection": {
                "action": sel["action"],
                "reason": sel["reason"],
                "tie_break": sel["tie_break"],
                "decision_source": sel["decision_source"],
            },
            "status": "PHASE1_SMOKE_OK",
        }
        path = OUT / f"arm_{args.arm.lower()}_seed{args.seed}.json"
        path.write_text(json.dumps(payload, indent=2))
        print(json.dumps(payload, indent=2))
        print("wrote", path)
        return

    # Full-world arms: wire through existing Observer/experiment runners in Phase 2.
    stub = {
        "arm": args.arm,
        "seed": args.seed,
        "ticks": args.ticks,
        "status": "STUB_PENDING_FULL_WORLD_WIRE",
        "note": (
            "Phase 1 scaffold only. Free-policy / intervention / forced-coverage "
            "full runs attach in Phase 2 using psychology observer / update42 runner patterns."
        ),
        "params": {
            "first_action": args.first_action,
            "forced_ticks": args.forced_ticks,
            "order_label": args.order_label,
        },
    }
    path = OUT / f"arm_{args.arm.lower()}_seed{args.seed}_stub.json"
    path.write_text(json.dumps(stub, indent=2))
    print(json.dumps(stub, indent=2))
    print("wrote", path)


if __name__ == "__main__":
    main()
