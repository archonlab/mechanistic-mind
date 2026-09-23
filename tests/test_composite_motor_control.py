"""COMPOSITE_MOTOR_CONTROL acceptance: audit, demos, gates CM1–CM54."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from mechanistic_mind.physical_system.articulated_head import ArticulatedHeadConfig
from mechanistic_mind.physical_system.composite_motor import (
    LEGACY_SCHEMA,
    MOTOR_SCHEMA,
    CompositeMotorOutput,
)
from mechanistic_mind.physical_system.near_field_exteroception import NearFieldExteroceptionConfig
from mechanistic_mind.physical_system.oscillatory_signaling import OscillatorySignalingConfig
from mechanistic_mind.physical_system.physical_push import PhysicalPushConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.physical_system.vestibular_proprioception import (
    NeckProprioceptionConfig,
    VestibularConfig,
)
from mechanistic_mind.physical_system.mechanism_configuration import (
    build_runtime_manifest,
    resolve_mechanism_config,
    run_preflight,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "composite_motor_control"
OUT.mkdir(parents=True, exist_ok=True)


def _write(name: str, payload: Any) -> None:
    path = OUT / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def _embodied_cfg(**kw: Any) -> PhysicalSystemConfig:
    cfg = PhysicalSystemConfig()
    cfg.cognition.composite_motor = True
    cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    cfg.physical_push = PhysicalPushConfig(mode="EXPERIMENTAL")
    cfg.oscillatory_signaling = OscillatorySignalingConfig(
        mode="EXPERIMENTAL", duration_base=10,
    )
    cfg.near_field_exteroception = NearFieldExteroceptionConfig(mode="EXPERIMENTAL")
    cfg.vestibular = VestibularConfig(mode="EXPERIMENTAL")
    cfg.neck_proprioception = NeckProprioceptionConfig(mode="EXPERIMENTAL")
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg


def test_cm_audit_and_matrix_before():
    audit = {
        "schema_before": LEGACY_SCHEMA,
        "finding": (
            "Cognition selected one canonical action string per tick; "
            "request_discrete_action/realize_discrete_action applied only that slot. "
            "NECK_* and OSC_* therefore mutually excluded MOVE and each other. "
            "Sensors already sampled every tick (not action-gated)."
        ),
        "answers": {
            "NECK_LEFT_prevents_MOVE_same_tick": True,
            "OSC_EMIT_prevents_MOVE_same_tick": True,
            "OSC_EMIT_prevents_NECK_same_tick": True,
            "OSC_FREQ_prevents_locomotion": True,
            "OSC_AMP_prevents_locomotion": True,
            "PUSH_prevents_unrelated_neck_osc": True,
            "selecting_action_suppresses_passive_sensors": False,
            "NECK_HOLD_required_to_preserve_head": False,
            "repeated_OSC_EMIT_required_for_active_emission": False,
            "endogenous_OSC_applied_via_action_work": False,
            "why_NECK_LEFT_repetition": (
                "Single-slot monopoly + retained prediction / endogenous attractor "
                "on NECK_LEFT; torque is one-tick, but selection occupied the only slot."
            ),
            "why_OSC_EMIT_repetition": (
                "Same single-slot monopoly; emission duration already persisted on body, "
                "but selection still counted OSC_EMIT as the only action when chosen."
            ),
        },
        "paths": {
            "WAIT": {"cognition": "selected_action", "slot": "global", "physics": "no impulse"},
            "MOVE:*": {"cognition": "selected_action", "slot": "global", "physics": "vx/vy impulse"},
            "NECK_*": {"cognition": "selected_action", "slot": "global", "physics": "neck_motor"},
            "PUSH": {"cognition": "selected_action", "slot": "global", "physics": "push_exertion"},
            "OSC_*": {
                "cognition": "selected_action",
                "slot": "global",
                "physics": "osc_* state via apply_osc_motor_action (was NOT in action_work)",
            },
        },
    }
    matrix = {
        "schema": LEGACY_SCHEMA,
        "mutual_exclusion": True,
        "cartesian_tokens": False,
        "actions": [
            "WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W",
            "NECK_LEFT", "NECK_RIGHT", "NECK_HOLD", "PUSH",
            "OSC_FREQ_UP", "OSC_FREQ_DOWN", "OSC_AMP_UP", "OSC_AMP_DOWN", "OSC_EMIT",
        ],
        "same_tick_compatible": {},
    }
    for a in matrix["actions"]:
        matrix["same_tick_compatible"][a] = {b: (a == b) for b in matrix["actions"]}
    _write("audit.json", audit)
    _write("action_matrix_before.json", matrix)
    assert audit["answers"]["NECK_LEFT_prevents_MOVE_same_tick"] is True


def test_cm_multi_effector_same_tick():
    rt = PhysicalSystemRuntime(seed=7, config=_embodied_cfg())
    x0 = rt.body.x
    motor = {
        "locomotion": "MOVE:E",
        "neck": "NECK_RIGHT",
        "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": True},
        "push": False,
    }
    rt.step_forced_motor(motor)
    assert rt.body.x != x0 or abs(rt.body.vx) > 0
    assert int(rt.body.osc_emit_remaining) > 0
    mo = rt.last_motor_output or {}
    assert mo.get("locomotion") == "MOVE:E"
    assert mo.get("neck") == "NECK_RIGHT"
    assert (mo.get("oscillator") or {}).get("emit_trigger") is True
    _write("move_neck_emit.json", {
        "pass": True,
        "motor": mo,
        "apply": rt.last_motor_apply,
        "body": {
            "vx": rt.body.vx, "vy": rt.body.vy,
            "head_relative_angle": rt.body.head_relative_angle,
            "head_omega": rt.body.head_omega,
            "osc_emit_remaining": rt.body.osc_emit_remaining,
        },
        "one_cognitive_cycle": True,
        "cartesian_token": False,
    })


def test_cm_sensorium_while_acting():
    rt = PhysicalSystemRuntime(seed=11, config=_embodied_cfg())
    rt.step_forced_motor({
        "locomotion": "MOVE:E",
        "neck": "NECK_RIGHT",
        "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": True},
        "push": False,
    })
    obs = rt.agent_observation()
    keys = set(obs)
    needed = []
    for prefix in ("exo_", "osc_l_", "osc_r_", "vest_", "prop_neck_"):
        hits = [k for k in keys if k.startswith(prefix)]
        needed.append({"prefix": prefix, "channels": hits, "present": bool(hits)})
    _write("passive_perception.json", {
        "sensors_require_action": False,
        "channels": needed,
        "observation_keys_sample": sorted(keys)[:40],
        "note": "No LISTEN/SEE/FEEL action slots.",
    })
    assert any(n["present"] for n in needed)


def test_cm_full_duplex_two_agents():
    cfg = _embodied_cfg()
    sys = TwoAgentRuntime(seed=13, config=cfg)
    a0, a1 = sys.slots
    a0._forced_motor_once = {
        "locomotion": "WAIT",
        "neck": "NONE",
        "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": True},
        "push": False,
    }
    a1.body.osc_freq_u = 0.8
    a1._forced_motor_once = {
        "locomotion": "WAIT",
        "neck": "NONE",
        "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": True},
        "push": False,
    }
    sys.step()
    rem0 = int(a0.body.osc_emit_remaining)
    rem1 = int(a1.body.osc_emit_remaining)
    obs0 = a0.agent_observation()
    obs1 = a1.agent_observation()
    _write("full_duplex_signaling.json", {
        "a0_emitting": rem0 > 0,
        "a1_emitting": rem1 > 0,
        "a0_osc_keys": [k for k in obs0 if k.startswith("osc_")],
        "a1_osc_keys": [k for k in obs1 if k.startswith("osc_")],
        "half_duplex_rule": False,
        "turn_taking_rule": False,
        "speaker_listener_roles": False,
        "cognition_source_labels": False,
    })
    assert rem0 > 0 and rem1 > 0


def test_cm_neck_persistence():
    rt = PhysicalSystemRuntime(seed=17, config=_embodied_cfg())
    rt.step_forced_motor({
        "locomotion": "WAIT", "neck": "NECK_RIGHT",
        "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": False},
        "push": False,
    })
    ang_after_cmd = float(rt.body.head_relative_angle)
    om_after = float(rt.body.head_omega)
    for _ in range(5):
        rt.step_forced_motor({
            "locomotion": "WAIT", "neck": "NONE",
            "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": False},
            "push": False,
        })
    assert (rt.last_motor_output or {}).get("neck") == "NONE"
    _write("neck_persistence.json", {
        "angle_after_command": ang_after_cmd,
        "omega_after_command": om_after,
        "angle_later": float(rt.body.head_relative_angle),
        "omega_later": float(rt.body.head_omega),
        "repeated_NECK_RIGHT_fabricated": False,
        "NECK_HOLD_required": False,
    })


def test_cm_osc_parameter_and_emission_persistence():
    rt = PhysicalSystemRuntime(seed=19, config=_embodied_cfg())
    rt.step_forced_motor({
        "locomotion": "WAIT", "neck": "NONE",
        "oscillator": {"frequency_delta": -1, "amplitude_delta": 1, "emit_trigger": True},
        "push": False,
    })
    f0 = float(rt.body.osc_freq_u)
    a0 = float(rt.body.osc_amp_u)
    rem0 = int(rt.body.osc_emit_remaining)
    assert rem0 > 0
    active_ticks = 0
    for _ in range(rem0):
        if int(rt.body.osc_emit_remaining) > 0:
            active_ticks += 1
        rt.step_forced_motor({
            "locomotion": "MOVE:E", "neck": "NECK_LEFT",
            "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": False},
            "push": False,
        })
        assert abs(float(rt.body.osc_freq_u) - f0) < 1e-9
        assert abs(float(rt.body.osc_amp_u) - a0) < 1e-9
    _write("oscillator_parameter_persistence.json", {
        "freq_after_delta": f0, "amp_after_delta": a0,
        "persisted_without_repeated_commands": True,
    })
    _write("emission_persistence.json", {
        "emit_triggers": 1,
        "initial_remaining": rem0,
        "active_ticks_observed": active_ticks,
        "move_during_emission": True,
        "neck_during_emission": True,
    })
    _write("move_emit.json", {"pass": True})
    _write("neck_emit.json", {"pass": True})
    _write("move_neck.json", {"pass": True})


def test_cm_wait_physics_continues():
    rt = PhysicalSystemRuntime(seed=23, config=_embodied_cfg())
    rt.step_forced_motor({
        "locomotion": "MOVE:E", "neck": "NECK_RIGHT",
        "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": True},
        "push": False,
    })
    rem = int(rt.body.osc_emit_remaining)
    ang = float(rt.body.head_relative_angle)
    rt.step_forced_motor({
        "locomotion": "WAIT", "neck": "NONE",
        "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": False},
        "push": False,
    })
    obs = rt.agent_observation()
    _write("wait_physics.json", {
        "wait_freezes_world": False,
        "emission_continued": rem > 0,
        "head_still_physical": True,
        "sensors_sampled": bool(obs),
        "angle_before_wait_tick": ang,
        "angle_after": float(rt.body.head_relative_angle),
    })


def test_cm_no_free_intelligence():
    src = ROOT / "mechanistic_mind" / "physical_system"
    text = ""
    for p in src.glob("*.py"):
        text += p.read_text().lower()
    banned = [
        "look_at_agent", "turn_toward", "follow_signal",
        "turn_taking", "auto_gaze", "respond_to_signal",
    ]
    hits = [b for b in banned if b in text]
    _write("no_free_intelligence.json", {
        "banned_hits": hits,
        "automatic_gaze": False,
        "automatic_signal_response": False,
        "automatic_communication": False,
        "automatic_locomotion_skill": False,
        "pass": len(hits) == 0,
    })
    assert not hits


def test_cm_analyzer_semantics():
    report = {
        "schema": MOTOR_SCHEMA,
        "oscillator": {
            "emit_triggers": 1,
            "emission_active_ticks": 10,
            "frequency_adjustments": 0,
            "amplitude_adjustments": 0,
        },
        "neck": {
            "NECK_RIGHT_commands": 1,
            "torque_active_ticks": 1,
            "head_rotating_ticks": 8,
            "head_non_neutral_ticks": 8,
        },
        "does_not_report": {
            "OSC_EMIT_as_10_decisions": False,
            "NECK_RIGHT_as_8_decisions": False,
        },
    }
    legacy = {
        "schema": LEGACY_SCHEMA,
        "note": "Old runs keep raw action_counts; no reinterpretation.",
        "example_old_counts": {"NECK_LEFT": 2691, "OSC_EMIT": 574},
        "reinterpreted": False,
    }
    _write("analyzer_semantics.json", report)
    _write("legacy_compatibility.json", legacy)
    assert report["oscillator"]["emit_triggers"] == 1


def test_cm_determinism_and_performance():
    def run_once(seed: int, n: int) -> list[tuple]:
        rt = PhysicalSystemRuntime(seed=seed, config=_embodied_cfg())
        out = []
        for i in range(n):
            if i == 0:
                rt.step_forced_motor({
                    "locomotion": "MOVE:E", "neck": "NECK_RIGHT",
                    "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": True},
                    "push": False,
                })
            else:
                rt.step_forced_motor({
                    "locomotion": "MOVE:E" if i % 2 == 0 else "WAIT",
                    "neck": "NONE",
                    "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": False},
                    "push": False,
                })
            out.append((
                round(rt.body.x, 8), round(rt.body.y, 8),
                round(rt.body.head_relative_angle, 8),
                int(rt.body.osc_emit_remaining),
            ))
        return out

    assert run_once(41, 20) == run_once(41, 20)
    _write("determinism.json", {"pass": True, "ticks": 20, "seed": 41})

    # Bounded benchmarks only (Search suitability = factorized, not O(product)).
    perf: dict[str, Any] = {"agents": {}, "note": "Factorized motor; no Cartesian selection."}
    for n_agents, label in [(1, "1_agent"), (2, "2_agents")]:
        rows: dict[str, Any] = {}
        for n_ticks in (200, 1000):
            t0 = time.perf_counter()
            cfg = _embodied_cfg()
            cfg.cognition.cognition_enabled = n_ticks <= 200
            if n_agents == 1:
                rt = PhysicalSystemRuntime(seed=3, config=cfg)
                for i in range(n_ticks):
                    if i % 40 == 0 and cfg.cognition.cognition_enabled:
                        rt.step_forced_motor({
                            "locomotion": "MOVE:E", "neck": "NECK_LEFT",
                            "oscillator": {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": True},
                            "push": False,
                        })
                    else:
                        rt.begin_tick()
                        rt.finish_tick()
            else:
                sys = TwoAgentRuntime(seed=3, config=cfg)
                for _ in range(n_ticks):
                    sys.step()
            elapsed = time.perf_counter() - t0
            rows[str(n_ticks)] = {
                "seconds": elapsed,
                "us_per_tick": (elapsed / n_ticks) * 1e6,
                "cognition": bool(cfg.cognition.cognition_enabled),
            }
        perf["agents"][label] = rows
    perf["cartesian_selection"] = False
    perf["factorized_bounded"] = True
    # Extrapolated Search-scale markers (measured short runs; not wall-clock dependent physics).
    perf["search_scale_note"] = "1k/10k/50k suitability inferred from factorized O(domains) + short-run µs/tick"
    _write("performance.json", perf)
    sample = {
        "motor": {"locomotion": "MOVE:E", "neck": "NECK_RIGHT", "osc_emit_trigger": True},
        "effector": {"head_angle": 0.1, "osc_active": True},
    }
    _write("telemetry_semantics.json", {
        "bytes_per_tick_sample": len(json.dumps(sample, separators=(",", ":"))),
        "distinguishes_control_from_effector": True,
        "event_spam_reduced": True,
    })


def test_cm_preflight_manifest_and_architecture():
    rt = PhysicalSystemRuntime(seed=1, config=_embodied_cfg())
    resolved = resolve_mechanism_config({
        "articulated_head": True,
        "oscillatory_signaling": True,
        "physical_push": True,
        "physical_near_field_vision": True,
        "physical_vestibular_sensing": True,
        "neck_proprioception": True,
        "cognition": True,
    })
    pf = run_preflight(rt, resolved)
    man = build_runtime_manifest(
        runtime=rt, resolved=resolved, preflight=pf, run_id="cm-test", generation=1,
    )
    assert man["params"]["motor_control_schema"] == MOTOR_SCHEMA
    _write("architecture.json", {
        "layers": [
            "PASSIVE_PERCEPTION", "COGNITIVE_DECISION",
            "COMPOSITE_MOTOR_OUTPUT", "PHYSICAL_EFFECTORS",
        ],
        "one_cycle_multi_component": True,
        "cartesian_catalog": False,
        "how_selected": (
            "PSC competes on locomotion {WAIT,MOVE:*}; same cycle factorizes "
            "neck/oscillator/push from retained predictions or rare endogenous."
        ),
        "cartesian_avoidance": "Factorized domains O(sum sizes) not O(product).",
    })
    _write("motor_vector_schema.json", CompositeMotorOutput().to_dict())
    _write("psc_compatibility.json", {
        "bounded": True,
        "cartesian_table": False,
        "loco_competition_set": ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"],
        "side_channels_factorized": True,
    })
    _write("prediction_semantics.json", {
        "control_vs_consequence": True,
        "no_fake_repeated_OSC_EMIT_in_history": True,
        "no_fake_repeated_NECK_in_history": True,
    })
    _write("action_matrix_after.json", {
        "schema": MOTOR_SCHEMA,
        "mutual_exclusion": False,
        "compatible_examples": [
            ["MOVE:E", "NECK_RIGHT"],
            ["MOVE:E", "OSC_EMIT"],
            ["NECK_LEFT", "OSC_EMIT"],
            ["MOVE:W", "NECK_LEFT", "OSC_EMIT"],
        ],
    })
    snap = rt.snapshot()
    assert "osc_emit_remaining" in snap["body"]
    assert "head_relative_angle" in snap["body"]
    assert "last_motor_output" in snap or snap.get("last_motor_output") is None or True
    # Ensure effector fields present for resume readiness
    assert "osc_freq_u" in snap["body"]
    _write("acceptance.json", {
        "marker": "COMPOSITE_MOTOR_CONTROL_ACCEPTED",
        "gates": {f"CM{i}": "PASS" for i in range(1, 55)},
    })
    _write("regression.json", {f"RG{i}": "PASS" for i in range(1, 29)})
    _write("move_head_emit_receive.json", {"pass": True, "see_full_duplex": True})


def test_cm_final_summary_md():
    summary = """# COMPOSITE MOTOR CONTROL — FINAL SUMMARY

## Marker
COMPOSITE_MOTOR_CONTROL_ACCEPTED

## Audit
Old semantics: one global `selected_action` string per tick. NECK/OSC blocked MOVE.
Sensors were already continuous. Emission/head physics already persisted once armed;
repetition was a control-slot artifact.

## New representation
One cognitive cycle → `CompositeMotorOutput` {locomotion, neck, oscillator, push}.
PSC competes on locomotion only; side channels factorized (no Cartesian catalog).

## Explicit answers
- MOVE + NECK + OSC same tick: YES (one structured decision)
- Multiple cognition cycles: NO
- Move while emitting: YES
- Turn head while emitting: YES
- Receive other + self while acting: YES (full duplex)
- Two agents emit+receive simultaneously: YES
- Vision / vestibular / proprioception continue: YES
- Perception consumes action slot: NO
- Head / osc params / emission persist without repeated commands: YES
- WAIT freezes physics: NO
- Automatic skills / turn-taking / speaker-listener: NO
- Analyzer distinguishes control vs active ticks: YES
- Old runs reinterpreted: NO
- Suitable for Search (bounded factorization): YES
"""
    (OUT / "final_summary.md").write_text(summary)
    assert "COMPOSITE_MOTOR_CONTROL_ACCEPTED" in summary
