#!/usr/bin/env python3
"""Update 4.9 — Continuous World–Organism Exchange × Physical Dependency.

Physical mechanism only. Same internal_materials + processing as 4.8.
No survival-label semantics in cognition. Null cognitive results are valid.
"""
from __future__ import annotations

import json
import re
import sys
import time
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.body.physical_intake import (
    MATERIAL_A,
    build_split_field,
    build_uniform_field,
)
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import CompositeSink, InMemorySink, PsychologyObserver
from mechanistic_mind.psyche import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    SingleOrganismPsycheV05,
)
from mechanistic_mind.psyche.sensorimotor import SensorimotorConfig
from mechanistic_mind.research.developmental_subsidy import (
    apply_subsidy_to_body_config,
    apply_subsidy_to_body_state,
    subsidy_from_tick_equivalent,
)
from contextual_object_ecology_v034 import (
    multi_channel_contextual_object_config,
    todo4_calibrated_body_config,
)

OUT = ROOT / "results" / "update49_world_exchange"
OUT.mkdir(parents=True, exist_ok=True)

SEED = 17
A = "A001"
OID = "OBJ-100"
OPOS = (5, 2)
# Default start away from object for env-only probes
EPOS = (2, 3)


def _dump(name: str, payload: Any) -> None:
    path = OUT / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


def _bcfg(
    *,
    intake: bool = True,
    transfer: bool = True,
    processing: bool = True,
    env: bool = True,
    env_xfer: bool = True,
    env_cap: float = 0.008,
    capacity: float = 0.20,
) -> BodyConfig:
    base = todo4_calibrated_body_config()
    d = {f: getattr(base, f) for f in base.__dataclass_fields__}
    d["recovery_dynamics_enabled"] = True
    d["physical_intake_enabled"] = intake
    d["intake_transfer_enabled"] = transfer
    d["intake_processing_enabled"] = processing
    d["intake_internal_capacity"] = capacity
    d["env_exchange_enabled"] = env
    d["env_exchange_transfer_enabled"] = env_xfer
    d["env_exchange_per_tick_capacity"] = env_cap
    d["env_exchange_material_id"] = MATERIAL_A
    return BodyConfig(**d)


def _world_cfg(field: dict[str, float] | None = None):
    base = multi_channel_contextual_object_config(SEED)
    return replace(base, env_material_field=dict(field or {}))


def _engine(
    *,
    field: dict[str, float] | None = None,
    body_config: BodyConfig | None = None,
    pos=EPOS,
    body: BodyState | None = None,
) -> Engine:
    cfg = body_config or _bcfg()
    spec = subsidy_from_tick_equivalent(50)
    cfg = apply_subsidy_to_body_config(cfg, spec)
    b0 = apply_subsidy_to_body_state(body or BodyState(), spec)
    from contextual_object_ecology_v034 import ContextualObjectEcologyWorld

    world = ContextualObjectEcologyWorld(
        world_config=_world_cfg(field),
        body_config=cfg,
        agent_ids=(A,),
        start_positions={A: pos},
        initial_bodies={A: b0},
    )
    reg = MechanismRegistry()
    reg.register(
        SingleOrganismPsycheV05(
            sensorimotor_config=SensorimotorConfig(
                cue_mode="PERCEPTUAL_CUE_ENABLED",
                prospective_valuation=True,
            ),
            developmental=DevelopmentalConfig(
                condition=DevelopmentalCondition.EXPERIENCE_GATED
            ),
        )
    )
    return Engine(
        world=world,
        agents={A: Agent(agent_id=A)},
        seed=SEED,
        mechanisms=reg,
        observer=PsychologyObserver(
            CompositeSink((InMemorySink(),)), compact_ticks=True
        ),
        run_config={"update": "4.9", "env_exchange": True},
    )


def _body(eng: Engine) -> dict[str, Any]:
    return deepcopy(eng.state.world.variables["bodies"][A])


def _pos(eng: Engine) -> tuple[int, int]:
    p = eng.state.world.variables["world"]["agent_positions"][A]
    return int(p[0]), int(p[1])


def _snap(eng: Engine) -> dict[str, Any]:
    b = _body(eng)
    return {
        "pos": list(_pos(eng)),
        "energy": b.get("energy_reserve"),
        "hydration": b.get("hydration"),
        "fatigue": b.get("fatigue"),
        "internal": deepcopy(b.get("internal_materials") or {}),
        "last_env_exchange": b.get("last_env_exchange"),
        "last_env_availability": b.get("last_env_availability"),
        "last_intake_transfer": b.get("last_intake_transfer"),
        "last_intake_processed": b.get("last_intake_processed"),
    }


def _act(kind: str, **params: Any) -> Action:
    # Match Update 4.8 string Action forms: WAIT / USE:id / MOVE:x,y
    if kind == "WAIT":
        return Action("WAIT")
    if kind == "USE":
        return Action(f"USE:{params['object_id']}")
    if kind == "MOVE":
        # relative one-step via absolute destination computed by caller preferred
        if "destination" in params:
            x, y = params["destination"]
            return Action(f"MOVE:{int(x)},{int(y)}")
        direction = params.get("direction", "E")
        # caller should pass destination; keep direction sentinel for spatial helper
        raise ValueError(f"MOVE requires destination=, got direction={direction}")
    return Action(kind)


def _step(eng: Engine, action: Action | None = None) -> None:
    if action is None:
        eng.step()
    else:
        eng.step({A: action})


def _w(w: int | None = None, h: int | None = None) -> tuple[int, int]:
    cfg = multi_channel_contextual_object_config(SEED)
    return int(w or cfg.width), int(h or cfg.height)


def control_available() -> dict[str, Any]:
    """High uniform availability → continuous exchange + delayed processing effects."""
    w, h = _w()
    eng = _engine(field=build_uniform_field(w, h, 1.0), pos=EPOS)
    series = [_snap(eng)]
    for _ in range(30):
        _step(eng, Action("WAIT"))
        series.append(_snap(eng))
    return {
        "control": "ENV_AVAILABLE",
        "field": "uniform_1.0",
        "ticks": 30,
        "action": "WAIT",
        "series": series,
        "pass_exchange_nonzero": any(
            float(s.get("last_env_exchange") or 0) > 0 for s in series[1:]
        ),
        "pass_internal_rose": (
            sum((series[-1].get("internal") or {}).values())
            + sum((series[10].get("internal") or {}).values())
        )
        > 0,
        "pass_energy_responded": float(series[-1]["energy"]) != float(series[0]["energy"]),
    }


def control_deprived() -> dict[str, Any]:
    w, h = _w()
    # Preload some material then deprive
    eng = _engine(
        field=build_uniform_field(w, h, 1.0),
        pos=EPOS,
        body=BodyState(internal_materials={MATERIAL_A: 0.05}),
    )
    # Switch field to zero by rewriting world truth after first tick of exchange
    series = [_snap(eng)]
    for i in range(40):
        if i == 5:
            eng.state.world.variables["world"]["env_material_field"] = build_uniform_field(
                w, h, 0.0
            )
        _step(eng, Action("WAIT"))
        series.append(_snap(eng))
    mid = series[6]
    end = series[-1]
    return {
        "control": "ENV_DEPRIVED",
        "note": "availability→0 at tick 5; WAIT only",
        "series_head": series[:8],
        "series_tail": series[-5:],
        "pass_exchange_stops": float(mid.get("last_env_exchange") or 0) == 0.0
        or float(series[7].get("last_env_exchange") or 0) == 0.0,
        "pass_internal_declines": sum((end.get("internal") or {}).values())
        < sum((series[5].get("internal") or {}).values()),
    }


def control_restored() -> dict[str, Any]:
    w, h = _w()
    eng = _engine(field=build_uniform_field(w, h, 0.0), pos=EPOS)
    series = [_snap(eng)]
    for i in range(40):
        if i == 15:
            eng.state.world.variables["world"]["env_material_field"] = build_uniform_field(
                w, h, 1.0
            )
        _step(eng, Action("WAIT"))
        series.append(_snap(eng))
    return {
        "control": "ENV_RESTORED",
        "note": "availability 0→1 at tick 15",
        "before": series[14],
        "after": series[20],
        "pass_exchange_returns": float(series[20].get("last_env_exchange") or 0) > 0,
        "pass_internal_rises_after": sum((series[30].get("internal") or {}).values())
        > sum((series[14].get("internal") or {}).values()),
    }


def control_exchange_ablated() -> dict[str, Any]:
    w, h = _w()
    eng = _engine(
        field=build_uniform_field(w, h, 1.0),
        body_config=_bcfg(env=True, env_xfer=False),
        pos=EPOS,
    )
    series = [_snap(eng)]
    for _ in range(20):
        _step(eng, Action("WAIT"))
        series.append(_snap(eng))
    return {
        "control": "EXCHANGE_ABLATED",
        "pass_zero_exchange": all(
            float(s.get("last_env_exchange") or 0) == 0 for s in series
        ),
        "pass_internal_flat": all(
            sum((s.get("internal") or {}).values()) == 0 for s in series
        ),
        "final": series[-1],
    }


def control_processing_ablated() -> dict[str, Any]:
    w, h = _w()
    eng = _engine(
        field=build_uniform_field(w, h, 1.0),
        body_config=_bcfg(processing=False),
        pos=EPOS,
    )
    series = [_snap(eng)]
    e0 = float(series[0]["energy"])
    for _ in range(25):
        _step(eng, Action("WAIT"))
        series.append(_snap(eng))
    return {
        "control": "PROCESSING_ABLATED",
        "pass_exchange_ok": any(
            float(s.get("last_env_exchange") or 0) > 0 for s in series[1:]
        ),
        "pass_internal_accumulates": sum((series[-1].get("internal") or {}).values())
        > 0.05,
        "pass_no_processing_credit": all(
            float(s.get("last_intake_processed") or 0) == 0 for s in series
        ),
        "energy_delta": float(series[-1]["energy"]) - e0,
        "final": series[-1],
    }


def control_spatial_move() -> dict[str, Any]:
    """MOVE changes exchange only via position → local availability."""
    w, h = _w()
    field = build_split_field(w, h, high_value=1.0, low_value=0.0, split_x=w // 2)
    # Start in high region (x small)
    start = (1, 3)
    eng = _engine(field=field, pos=start)
    series = [_snap(eng)]
    # Wait in high
    for _ in range(5):
        _step(eng, Action("WAIT"))
        series.append(_snap(eng))
    high_ex = [float(s.get("last_env_exchange") or 0) for s in series[1:6]]
    # MOVE east past split (width//2) into low-availability region
    target_x = (w // 2) + 2
    guard = 0
    while _pos(eng)[0] < target_x and guard < 40:
        x, y = _pos(eng)
        _step(eng, Action(f"MOVE:{x+1},{y}"))
        series.append(_snap(eng))
        guard += 1
    # settle a few ticks in low region
    for _ in range(5):
        _step(eng, Action("WAIT"))
        series.append(_snap(eng))
    low_ex = [float(s.get("last_env_exchange") or 0) for s in series[-5:]]
    return {
        "control": "SPATIAL_MOVE",
        "start": list(start),
        "end_pos": series[-1]["pos"],
        "high_exchanges": high_ex,
        "low_exchanges": low_ex,
        "pass_high_gt_low": (sum(high_ex) / max(1, len(high_ex)))
        > (sum(low_ex) / max(1, len(low_ex)) + 1e-9),
        "pass_moved": series[-1]["pos"][0] > start[0],
        "series_compact": [
            {
                "pos": s["pos"],
                "ex": s["last_env_exchange"],
                "avail": s["last_env_availability"],
            }
            for s in series
        ],
    }


def control_use_regression() -> dict[str, Any]:
    """4.8 USE path still works with env field present (env can be on)."""
    w, h = _w()
    eng = _engine(
        field=build_uniform_field(w, h, 0.0),  # env silent so USE isolated
        body_config=_bcfg(env=True, env_xfer=True),
        pos=OPOS,
    )
    before = _snap(eng)
    qty0 = float(eng.state.world.variables["world"]["objects"][OID]["quantity"])
    _step(eng, Action(f"USE:{OID}"))
    after1 = _snap(eng)
    qty1 = float(eng.state.world.variables["world"]["objects"][OID]["quantity"])
    for _ in range(5):
        _step(eng, Action("WAIT"))
    after = _snap(eng)
    return {
        "control": "USE_REGRESSION_4_8",
        "qty0": qty0,
        "qty1": qty1,
        "before": before,
        "after_use": after1,
        "after_wait": after,
        "pass_qty_down": qty1 < qty0,
        "pass_use_transfer": float(after1.get("last_intake_transfer") or 0) > 0,
        "pass_processing_later": float(after.get("last_intake_processed") or 0) > 0
        or sum((after.get("internal") or {}).values())
        < sum((after1.get("internal") or {}).values()),
    }


def control_autonomous() -> dict[str, Any]:
    w, h = _w()
    eng = _engine(field=build_uniform_field(w, h, 1.0), pos=EPOS)
    counts: dict[str, int] = {}
    exchanges = 0.0
    for _ in range(200):
        eng.step()
        # last action from experience
        exp = eng.state.world.variables.get("last_experience", {}).get(A, {})
        kind = exp.get("action") or "?"
        counts[kind] = counts.get(kind, 0) + 1
        exchanges += float(_body(eng).get("last_env_exchange") or 0)
    return {
        "control": "AUTONOMOUS_200",
        "action_counts": counts,
        "total_env_exchange": exchanges,
        "final": _snap(eng),
        "note": "Null policy adaptation is OK; physics should still exchange if WAIT/MOVE in field",
    }


def semantic_leakage_audit() -> dict[str, Any]:
    """Scan 4.9 API identifiers (not ban-list docs) for survival/food labels."""
    forbidden_idents = [
        "food",
        "eat",
        "hunger",
        "oxygen",
        "breathe",
        "breath",
        "survival",
        "thirst",
        # "air" alone is too noisy in English prose; require air_ / _air token
        "air_",
        "_air",
    ]
    files = [
        ROOT / "mechanistic_mind/body/physical_intake.py",
        ROOT / "mechanistic_mind/body/engine.py",
        ROOT / "mechanistic_mind/body/models.py",
        ROOT / "worlds/organism_world_v03.py",
    ]
    hits = []
    for path in files:
        text = path.read_text(errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            code = line.split("#", 1)[0]
            # skip pure doc / ban-list sentences
            if "No food" in code or "no food" in code or "forbidden" in code.lower():
                continue
            low = code.lower()
            for tok in forbidden_idents:
                if re.search(rf"(?<![A-Za-z0-9_]){re.escape(tok)}(?![A-Za-z0-9_])", low):
                    hits.append(
                        {
                            "file": str(path.relative_to(ROOT)),
                            "line": i,
                            "tok": tok,
                            "text": line.strip()[:120],
                        }
                    )
    return {
        "forbidden_in_code_lines": hits,
        "pass": len(hits) == 0,
        "note": "API/identifier scan on core physics files; ban-list docs excluded.",
    }


def main() -> None:
    t0 = time.time()
    results = {}
    for name, fn in [
        ("ENV_AVAILABLE", control_available),
        ("ENV_DEPRIVED", control_deprived),
        ("ENV_RESTORED", control_restored),
        ("EXCHANGE_ABLATED", control_exchange_ablated),
        ("PROCESSING_ABLATED", control_processing_ablated),
        ("SPATIAL_MOVE", control_spatial_move),
        ("USE_REGRESSION_4_8", control_use_regression),
        ("AUTONOMOUS_200", control_autonomous),
    ]:
        print(f"running {name}...")
        try:
            results[name] = fn()
            _dump(f"{name}_SUMMARY.json", results[name])
        except Exception as exc:
            results[name] = {"control": name, "error": repr(exc)}
            _dump(f"{name}_SUMMARY.json", results[name])
            print(f"  ERROR: {exc!r}")

    leak = semantic_leakage_audit()
    _dump("SEMANTIC_LEAKAGE_AUDIT.json", leak)

    # Causal chain compact
    chain = {
        "paths": [
            "local_env_availability → env_exchange_transfer → internal_materials → process_materials → body_deltas",
            "USE → intake_transfer → internal_materials (deferred process) → body_deltas (4.8 preserved)",
            "MOVE → position → local availability → exchange rate (no direct MOVE bonus)",
        ],
        "controls": {k: {kk: vv for kk, vv in v.items() if kk.startswith("pass_") or kk == "error"} for k, v in results.items()},
        "elapsed_s": round(time.time() - t0, 2),
    }
    _dump("TEMPORAL_CAUSAL_CHAIN.json", chain)

    cfg = {
        "update": "4.9",
        "seed": SEED,
        "env_exchange_per_tick_capacity": 0.008,
        "material": MATERIAL_A,
        "same_internal_materials_as_4_8": True,
        "default_env_off": True,
        "artifacts": sorted(results),
    }
    _dump("UPDATE49_CONFIG.json", cfg)

    # Compact final report
    lines = [
        "# Update 4.9 — FINAL REPORT",
        "",
        "Continuous World–Organism Exchange × Physical Dependency",
        "",
        "## Mechanism",
        "- Maintained `env_material_field` (boundary condition) → per-tick `env_exchange_transfer`",
        "- Same `BodyState.internal_materials` and `process_materials` as Update 4.8",
        "- USE discrete transfer still defers processing; continuous env does **not** permanently defer",
        "- MOVE affects exchange only via position → local availability",
        "",
        "## Controls",
    ]
    for k, v in results.items():
        if "error" in v:
            lines.append(f"- **{k}**: ERROR `{v['error']}`")
            continue
        passes = {kk: vv for kk, vv in v.items() if kk.startswith("pass_")}
        ok = all(bool(x) for x in passes.values()) if passes else False
        lines.append(f"- **{k}**: {'PASS' if ok else 'CHECK'} {passes}")
    lines += [
        "",
        f"## Semantic leakage: {'PASS' if leak.get('pass') else 'FAIL'} ({len(leak.get('forbidden_in_code_lines') or [])} hits)",
        "",
        "## Cognitive frontier",
        "- Not repaired. Dependency is physical; policy learning of deprivation is out of scope.",
        "",
        f"Elapsed: {chain['elapsed_s']}s",
        "",
    ]
    (OUT / "UPDATE49_FINAL_REPORT.md").write_text("\n".join(lines))
    print("wrote UPDATE49_FINAL_REPORT.md")
    print(json.dumps(chain["controls"], indent=2))


if __name__ == "__main__":
    main()
