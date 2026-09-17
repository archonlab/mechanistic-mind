"""SCENARIO_SELECTED observability: cognitive WAIT must not be hidden."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system.cognition import run_cognition_before_action
from mechanistic_mind.physical_system.runtime import _rng_unit
from mechanistic_mind.ui.psy_observer_web.serialize import collect_observer_events, live_frame
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession


SCENARIO_SOURCES = {
    "PROSPECTIVE_SCENARIO",
    "PROSPECTIVE_TIE_RESOLUTION",
    "PROSPECTIVE_CONTINUATION",
}


def _tik_cfg():
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = True
    cfg.planet.width = 12
    cfg.planet.height = 12
    return cfg


def test_a_prospective_wait_emits_scenario_selected():
    ta = TwoAgentRuntime(seed=143, config=_tik_cfg(), starts=((3, 6), (8, 6)))
    ta.step(80)
    for i, rt in enumerate(ta.slots):
        sel = rt.cognition.get("last_selection") or {}
        if sel.get("source") in SCENARIO_SOURCES and sel.get("action") == "WAIT":
            types = [e["type"] for e in rt.structured_events.list(limit=5000)]
            assert types.count("SCENARIO_SELECTED") > 0, f"agent_{i} missing SCENARIO_SELECTED under cognitive WAIT"
            wait_scen = [
                e for e in rt.structured_events.list(limit=5000)
                if e["type"] == "SCENARIO_SELECTED"
                and (e.get("evidence") or {}).get("selected_action") == "WAIT"
            ]
            assert wait_scen, f"agent_{i} SCENARIO_SELECTED WAIT evidence missing"
            assert wait_scen[-1]["evidence"].get("selection_source") in SCENARIO_SOURCES


def test_b_move_still_emits_scenario_selected():
    rt = PhysicalSystemRuntime(seed=17, config=_tik_cfg())
    # Force MOVE after cognition path has run once
    rt.step(5)
    rt._forced_action_once = "MOVE:N"
    rt.step(1)
    types = [e["type"] for e in rt.structured_events.list(limit=200)]
    assert "SCENARIO_SELECTED" in types
    move_ev = [
        e for e in rt.structured_events.list(limit=200)
        if e["type"] == "SCENARIO_SELECTED"
        and str((e.get("evidence") or {}).get("selected_action") or (e.get("evidence") or {}).get("action") or "").startswith("MOVE")
    ]
    assert move_ev


def test_c_fallback_wait_does_not_masquerade_as_scenario():
    """ENDOGENOUS / cognition-off WAIT must not emit SCENARIO_SELECTED."""
    cfg = _tik_cfg()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.step(10)
    scen = [e for e in rt.structured_events.list(limit=200) if e["type"] == "SCENARIO_SELECTED"]
    assert scen == []
    discrete = [e for e in rt.structured_events.list(limit=200) if e["type"] == "DISCRETE_ACTION_SELECTED"]
    assert discrete
    assert all((e.get("evidence") or {}).get("selected_action") == "WAIT" for e in discrete)
    assert all((e.get("evidence") or {}).get("selection_source") == "COGNITION_DISABLED" for e in discrete)


def test_d_e_agent_attribution_two_agent():
    ta = TwoAgentRuntime(seed=143, config=_tik_cfg(), starts=((3, 6), (8, 6)))
    ta.step(40)
    events = collect_observer_events(ta, limit=2000)
    by_agent = Counter()
    for e in events:
        if e.get("type") != "SCENARIO_SELECTED":
            continue
        aid = e.get("agent_id") or e.get("actor_agent_id")
        by_agent[aid] += 1
        assert aid in ("agent_0", "agent_1")
        if aid == "agent_0":
            assert e.get("body_id") in (None, "body-0") or e["evidence"].get("body_id") in (None, "body-0")
        if aid == "agent_1":
            assert e.get("body_id") in (None, "body-1") or e["evidence"].get("body_id") in (None, "body-1")
    # Both agents cognitive WAIT-lock → both should have scenario events
    assert by_agent.get("agent_0", 0) > 0
    assert by_agent.get("agent_1", 0) > 0


def test_k_l_determinism_and_behavior_unchanged():
    """Instrumentation must not alter actions / trajectories."""
    def run_seq(seed=143):
        ta = TwoAgentRuntime(seed=seed, config=_tik_cfg(), starts=((3, 6), (8, 6)))
        acts = [[], []]
        xy = [[], []]
        for _ in range(60):
            ta.step(1)
            for i, rt in enumerate(ta.slots):
                acts[i].append(rt.last_selected_action)
                xy[i].append((round(rt.body.x, 6), round(rt.body.y, 6)))
        return acts, xy

    a1, x1 = run_seq()
    a2, x2 = run_seq()
    assert a1 == a2
    assert x1 == x2


def test_mind_timeline_selection_agree():
    ta = TwoAgentRuntime(seed=143, config=_tik_cfg(), starts=((3, 6), (8, 6)))
    ta.step(30)
    events = collect_observer_events(ta, limit=2000)
    for i, rt in enumerate(ta.slots):
        sel = rt.cognition.get("last_selection") or {}
        if sel.get("source") not in SCENARIO_SOURCES:
            continue
        tick = int(rt.tick) - 1  # last emit was before tick increment in finish_tick... check
        # structured events use tick before increment in _emit during finish_tick
        # After step, rt.tick is post-increment; last event tick is tick-1
        last_tick = int(rt.tick) - 1
        matching = [
            e for e in events
            if e.get("type") == "SCENARIO_SELECTED"
            and (e.get("agent_id") == f"agent_{i}" or e.get("actor_agent_id") == f"agent_{i}")
            and int(e.get("tick") or -1) == last_tick
        ]
        if sel.get("action") == "WAIT" or (sel.get("action") or "").startswith("MOVE"):
            assert matching, f"agent_{i} MIND last_selection not on Timeline at tick {last_tick}"
            ev = matching[-1]["evidence"]
            assert ev.get("selected_action") == sel.get("action") or ev.get("action") == sel.get("action")
            if sel.get("source") in SCENARIO_SOURCES:
                assert ev.get("selection_source") == sel.get("source")


def test_observer_web_session_path_two_agent():
    """EXPERIMENT → TwoAgentRuntime → step → serialize → Timeline events (real Observer path)."""
    session = ObserverSession()
    session.apply_experiment({
        "seed": 143,
        "agent_count": 2,
        "cognition_enabled": True,
        "world": {"width": 12, "height": 12, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": {"cognition_enabled": True, "prospective_composition": True},
    })
    rt = session.runtime
    assert type(rt).__name__ == "TwoAgentRuntime"
    assert [s.seed for s in rt.slots] == [143, 144]
    for _ in range(40):
        session.step(1)
    with session._lock:
        frame = session._capture_locked()
    # Live frames expose structured_events (same payload as /api/events collector).
    events = frame.get("structured_events") or collect_observer_events(rt, limit=2000)
    scen = [e for e in events if e.get("type") == "SCENARIO_SELECTED"]
    assert scen, "Observer frame missing SCENARIO_SELECTED after cognitive WAIT run"
    aids = {e.get("agent_id") or e.get("actor_agent_id") for e in scen}
    assert "agent_0" in aids and "agent_1" in aids
    wait_scen = [
        e for e in scen
        if (e.get("evidence") or {}).get("selected_action") == "WAIT"
        or (e.get("evidence") or {}).get("action") == "WAIT"
    ]
    assert wait_scen, "cognitive WAIT SCENARIO_SELECTED missing on Observer path"
    # MIND / Timeline consistency for selected agent
    mind_action = (frame.get("mind") or {}).get("action") or {}
    assert mind_action.get("selected") == "WAIT"
    assert mind_action.get("source") in SCENARIO_SOURCES
    latest = max(wait_scen, key=lambda e: int(e.get("tick") or 0))
    assert (latest.get("evidence") or {}).get("selection_source") in SCENARIO_SOURCES
    assert (latest.get("evidence") or {}).get("selected_action") == mind_action.get("selected")
    # Per-agent views keep identity
    views = frame.get("agents_views") or {}
    assert views["agent_0"]["agent_seed"] == 143
    assert views["agent_1"]["agent_seed"] == 144
    assert (views["agent_0"].get("mind") or {}).get("action", {}).get("source") in SCENARIO_SOURCES
    assert (views["agent_1"].get("mind") or {}).get("action", {}).get("source") in SCENARIO_SOURCES


def test_forensic_report_seed_143():
    ta = TwoAgentRuntime(seed=143, config=_tik_cfg(), starts=((3, 6), (8, 6)))
    n = 200
    ta.step(n)
    reports = []
    for i, rt in enumerate(ta.slots):
        metrics = rt.cognition.get("metrics") or {}
        counts = dict(metrics.get("action_counts") or {})
        evs = list(rt.structured_events.list(limit=20000))
        scen = [e for e in evs if e["type"] == "SCENARIO_SELECTED"]
        wait_scen = [e for e in scen if (e.get("evidence") or {}).get("selected_action") == "WAIT"
                     or (e.get("evidence") or {}).get("action") == "WAIT"]
        move_scen = [e for e in scen if str((e.get("evidence") or {}).get("selected_action")
                     or (e.get("evidence") or {}).get("action") or "").startswith("MOVE")]
        discrete = [e for e in evs if e["type"] == "DISCRETE_ACTION_SELECTED"]
        sources = Counter(
            (e.get("evidence") or {}).get("selection_source")
            for e in discrete
        )
        wait = int(counts.get("WAIT") or 0)
        move = sum(int(v) for k, v in counts.items() if str(k).startswith("MOVE"))
        reports.append({
            "agent": f"agent_{i}",
            "seed": rt.seed,
            "cognition_ticks": ta._agent_stats[i]["cognition_ticks"],
            "prospective": metrics.get("prospective_compositions"),
            "SCENARIO_SELECTED": len(scen),
            "SCENARIO_SELECTED_WAIT": len(wait_scen),
            "SCENARIO_SELECTED_MOVE": len(move_scen),
            "DISCRETE_ACTION_SELECTED": len(discrete),
            "WAIT": wait,
            "MOVE": move,
            "selection_sources": dict(sources),
        })
        # Invariant: cognitive WAIT → observable
        if wait > 0 and any(s in SCENARIO_SOURCES for s in sources):
            assert len(wait_scen) > 0, reports[-1]
    assert reports[0]["cognition_ticks"] == n
    assert reports[1]["cognition_ticks"] == n
    assert reports[0]["SCENARIO_SELECTED_WAIT"] > 0
    assert reports[1]["SCENARIO_SELECTED_WAIT"] > 0
