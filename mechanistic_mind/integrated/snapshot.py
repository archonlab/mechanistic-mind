from __future__ import annotations

import base64
from copy import deepcopy
import json
from pathlib import Path
import pickle
from typing import Any

from mechanistic_mind.core.state import SimulationState


def save_snapshot(engine, path: str | Path) -> Path:
    """Save resumable state without observer telemetry."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"format": "mechanistic-mind-integrated-v1", "seed": engine.seed,
               "clock_tick": engine.clock.tick,
               "state_pickle": base64.b85encode(pickle.dumps(engine.state)).decode("ascii"),
               "rng_state": base64.b85encode(pickle.dumps(engine.rng._rng.getstate())).decode("ascii"),
               "run_config": deepcopy(engine.run_config)}
    target.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return target


def load_snapshot(engine, path: str | Path) -> SimulationState:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("format") != "mechanistic-mind-integrated-v1":
        raise ValueError("Unsupported snapshot format")
    engine.state = pickle.loads(base64.b85decode(payload["state_pickle"].encode("ascii")))
    if not isinstance(engine.state, SimulationState):
        raise ValueError("Snapshot does not contain a SimulationState")
    engine.clock.tick = int(payload.get("clock_tick", engine.state.tick))
    engine.rng._rng.setstate(pickle.loads(base64.b85decode(payload["rng_state"].encode("ascii"))))
    return deepcopy(engine.state)
