#!/usr/bin/env python3
"""Scientific fingerprint: lab development source vs public package (EXACT_MATCH)."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def run_fp(root: Path, seed: int = 17, ticks: int = 40) -> dict:
    sys.path.insert(0, str(root))
    # fresh imports per root
    for mod in list(sys.modules):
        if mod == "mechanistic_mind" or mod.startswith("mechanistic_mind."):
            del sys.modules[mod]
    from mechanistic_mind.physical_system.ecology_presets import (  # noqa: E402
        ECOLOGY_STRUCTURED_TERRAIN,
        make_ecology_config,
    )
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime  # noqa: E402
    from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (  # noqa: E402
        fingerprint_equal,
        scientific_fingerprint,
    )

    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    cfg.cognition.cognition_enabled = True
    rt = TwoAgentRuntime(seed=seed, config=cfg, signal_enabled=True)
    try:
        rt.set_mechanism("spatiotemporal_climate_ecology", False)
    except Exception:
        pass
    for s in rt.slots:
        nfe = getattr(s.config, "near_field_exteroception", None)
        if nfe is not None:
            nfe.radius = 1
    if getattr(rt.config, "near_field_exteroception", None):
        rt.config.near_field_exteroception.radius = 1
    for _ in range(ticks):
        rt.step(1)
    fp = scientific_fingerprint(rt)
    actions = [s.last_selected_action for s in rt.slots]
    return {"fingerprint": fp, "actions": actions, "tick": int(rt.tick)}


def main() -> None:
    lab = Path("<DEV_SOURCE>")
    pub = Path(__file__).resolve().parents[1]
    a = run_fp(lab)
    b = run_fp(pub)
    # compare without importing fingerprint_equal across mixed trees
    equal = json.dumps(a["fingerprint"], sort_keys=True) == json.dumps(b["fingerprint"], sort_keys=True)
    out = {
        "verdict": "EXACT_MATCH" if equal else "MISMATCH",
        "lab_tick": a["tick"],
        "pub_tick": b["tick"],
        "lab_actions": a["actions"],
        "pub_actions": b["actions"],
        "lab_fp": a["fingerprint"],
        "pub_fp": b["fingerprint"],
    }
    dest = Path(__file__).resolve().parent / "SCIENTIFIC_FINGERPRINT.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(out["verdict"])
    print("wrote", dest)
    if not equal:
        sys.exit(1)


if __name__ == "__main__":
    main()
