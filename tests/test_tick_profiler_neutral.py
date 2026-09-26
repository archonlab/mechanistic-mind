"""Profiling ON vs OFF must not change simulation semantics."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.research import tick_profiler as tp


def _fp(rt: TwoAgentRuntime) -> tuple:
    return (
        int(rt.tick),
        tuple(s.last_selected_action for s in rt.slots),
        tuple(round(float(s.body.x), 8) for s in rt.slots),
        tuple(round(float(s.body.y), 8) for s in rt.slots),
        tuple(sorted((s.last_agent_observation or {}).keys()) for s in rt.slots),
        tuple(round(float((s.last_agent_observation or {}).get("exo_0") or 0), 8) for s in rt.slots),
    )


def _run(n: int, profile: bool) -> tuple:
    tp.reset()
    if profile:
        tp.enable()
    else:
        tp.disable()
    cfg = tiktaalik_config()
    rt = TwoAgentRuntime(seed=17, config=cfg)
    fps = []
    for _ in range(n):
        if profile:
            tp.begin_tick()
        rt.step(1)
        if profile:
            tp.end_tick(rt.tick)
        fps.append(_fp(rt))
    tp.disable()
    return tuple(fps)


def test_profiler_off_vs_on_identical_short_fixture():
    a = _run(8, False)
    b = _run(8, True)
    assert a == b
