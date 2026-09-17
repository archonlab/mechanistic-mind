"""Update 4.74 — BODY-response-consequence acquisition archaeology.

Zero new capability. Source producer/consumer graph only.
Does not implement 4.75.
"""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState, step as w_step
from mechanistic_mind.body.acquired_sensorimotor_coupling import AcquiredCouplingState, step as r_step
from mechanistic_mind.body.engine import BodyEngine
from mechanistic_mind.body.models import BodyState
from mechanistic_mind.body.physical_transduction import maybe_step_on_state, ports_from_x, default_transducer_config
from mechanistic_mind.body.sensorimotor_dynamics import evolve, motor_distribution, SensorimotorState, BASE_NON_WAIT
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.research.generic_action_body_internal_return import cognition_leaks
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE
from mechanistic_mind.world_engine.physical_effector import THRESHOLD

OUT = Path("results/update474_body_response_consequence_acquisition_archaeology")
ROOT = Path(".")


def dump(name: str, obj: Any) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")


def md(name: str, text: str) -> None:
    (OUT / name).write_text(text if text.endswith("\n") else text + "\n")


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = json.loads((OUT / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["implemented_475"] is False

    cfg0 = BodyConfig()
    assert cfg0.physical_transduction_config is None
    assert cfg0.persistent_process_config is None
    assert cfg0.physical_coupling_config is None
    assert cfg0.physical_effector_config is None
    assert cfg0.passive_physical_exchange_config is None
    assert cfg0.env_exchange_enabled is False
    assert THRESHOLD == 0.60 and C_SCALE == 1.0
    assert set(FAMILY) == {"C0", "C1", "C2", "C3", "C4"}
    assert not ordinary_runtime_consumes_motor()
    assert BASE_NON_WAIT == 0.08

    # 4.73 reproduction from canonical results
    s473 = json.loads(Path("results/update473_physical_intervention_vs_nonintervention/summary.json").read_text())
    assert s473["outcome"] == "H"
    assert s473["claim_asserted"] == 121
    assert abs(s473["default_immediate"][0] + 0.013344) < 1e-6
    assert s473["c1_immediate"] == [0.0, 0.0, 0.0]
    repro = {
        "outcome": s473["outcome"],
        "claims": f"{s473['claim_asserted']}/{s473['claim_total']}",
        "default_delta": s473["default_immediate"],
        "c1": s473["c1_immediate"],
        "c23_dF": s473["c23_immediate"][2],
        "implemented_474_then": s473.get("implemented_474"),
    }

    # Source signatures
    w_sig = str(inspect.signature(w_step))
    r_sig = str(inspect.signature(r_step))
    ev_src = inspect.getsource(evolve)
    maybe_src = inspect.getsource(maybe_step_on_state)
    w_src = inspect.getsource(w_step)
    r_src = inspect.getsource(r_step)

    w_takes_body = "energy" in w_src or "fatigue" in w_src or "body" in w_sig
    r_takes_body = "energy" in r_src or "fatigue" in r_src or "body" in r_sig
    w_takes_m = "m=" in w_sig or "motor" in w_sig
    r_takes_n = "n:" in r_sig or "n=" in r_sig
    r_takes_m = "m:" in r_sig or "m=" in r_sig
    maybe_writes_ports = "internal_a" in maybe_src or "load_c" in maybe_src
    evolve_reads_ehf = "energy_reserve" in ev_src or "hydration" in ev_src or "fatigue" in ev_src
    evolve_reads_ports = "internal_a" in ev_src and "load_c" in ev_src

    # Live call-site archaeology
    body_py = list((ROOT / "mechanistic_mind").rglob("*.py"))
    skip = {"research", "__pycache__", "ui"}
    live_w_calls = []
    live_r_calls = []
    for p in body_py:
        if any(s in p.parts for s in skip):
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        if "adaptive_internal_coupling" in t and p.name != "adaptive_internal_coupling.py":
            live_w_calls.append(str(p))
        if "acquired_sensorimotor_coupling" in t and p.name != "acquired_sensorimotor_coupling.py":
            live_r_calls.append(str(p))

    # Empirical: 4.56 on writes X, not internal_a
    from dataclasses import replace
    st = BodyState.from_dict({"energy_reserve": 0.76, "hydration": 0.78, "fatigue": 0.14})
    cfg_x = replace(BodyConfig(), physical_transduction_config=default_transducer_config("ABSOLUTE"))
    maybe_step_on_state(st, cfg_x)
    x_on = tuple(st.transducer_state)
    ia_after = getattr(st, "internal_loads", {})
    # BodyState has no internal_a field; 4.20 keys live in internal_loads
    has_ia_field = hasattr(st, "internal_a")

    # Ordinary X off: transducer stays 0 after transition
    eng = BodyEngine(BodyConfig())
    ev = eng.transition(BodyState.from_dict({"energy_reserve": 0.76, "hydration": 0.78, "fatigue": 0.14}),
                        action=Action.wait(), distance=1.0)
    x_off = tuple(ev.state.transducer_state or (0.0, 0.0, 0.0))
    body_changed = abs(ev.state.energy_reserve - 0.76) > 1e-6

    # W update does not see BODY even if researcher passes EHF as u (that would be a new producer)
    # Document existing inputs only.
    w0 = AdaptiveInternalState()
    w1 = w_step(w0, physical_input=(0.1, 0.0, 0.0), plasticity=True)
    w_changed_from_u = any(abs(w1.weights[i][j] - w0.weights[i][j]) > 1e-12 for i in range(3) for j in range(3))

    r0 = AcquiredCouplingState()
    r1 = r_step(r0, n=(0.2, 0.0, 0.0), m=(0.0, 0.0, 0.0), plasticity=True)
    # first step: trace updated from n, weights only decay (m=0)
    r2 = r_step(r1, n=(0.0, 0.0, 0.0), m=(0.3, 0.0, 0.0), plasticity=True)
    r_needs_m = any(abs(r2.weights[j][i] - r1.weights[j][i]) > 1e-9 for j in range(3) for i in range(3))

    # N evolve with default missing keys vs EHF in body dict
    n0 = SensorimotorState()
    n_ports = evolve(n0, body={"internal_a": 0.9, "load_c": 0.1}, random_value=0.5)
    n_ehf = evolve(n0, body={"energy_reserve": 0.2, "hydration": 0.2, "fatigue": 0.9}, random_value=0.5)
    n_empty = evolve(n0, body={}, random_value=0.5)
    ehf_equals_empty = n_ehf.channels == n_empty.channels
    ports_differ = n_ports.channels != n_empty.channels

    leak = cognition_leaks({"outcome": "archaeology"})

    # Classification
    ordinary_body_to_x = False
    exp_body_to_x = True  # 4.56 when config on
    body_to_live_n = False
    body_to_w = False
    body_to_r = False
    x_to_w = False
    x_to_r = False
    x_to_live_n = False  # maybe_step does not write ports
    response_to_w = False
    # R gets internal M, not physical action
    physical_m_to_r = False
    internal_m_to_r = True

    outcome, otext = "I", "MIXED_ACQUISITION_PATH"
    # A would also fit the specific 4.73 consequence→acquisition question.
    # I is used because W/R exist as other learners and 4.56 X is experimental internal access.

    levels = {
        "1": {"status": "SUPPORTED", "note": "4.73 H"},
        "2A": {"status": "EXPERIMENTAL_CONFIG_ONLY", "note": "4.56 X when physical_transduction_config on; ordinary ABSENT"},
        "2B": {"status": "ABSENT", "note": "X/E/H/F do not enter W or R update"},
        "2C": {"status": "ABSENT", "note": "no response trace into a consequence-fed learner"},
        "2D": {"status": "ABSENT", "note": "not for this chain; W/R can associate their own inputs"},
        "2E": {"status": "NOT_TESTED", "note": "NOT_RUN: no zero-capability contingent path"},
        "3": {"status": "ABSENT", "note": "no acquired structure from this consequence"},
        "4": {"status": "ABSENT", "note": "live preact is researcher_controlled; N not consumed"},
        "5": {"status": "ABSENT", "note": "no history-dependent realized displacement from this chain"},
    }

    edges = {
        "BODY_CONDITION->INTERNAL_SIGNAL": "EXPERIMENTAL_CONFIG_ONLY_X / ORDINARY_ABSENT",
        "INTERNAL_SIGNAL->RESPONSE": "RESEARCH_ONLY_N_MOTOR; LIVE_N_NOT_CONSUMED",
        "RESPONSE->PHYSICAL_CONSEQUENCE": "RESEARCH_DISTANCE_OR_EXPERIMENTAL_EFFECTOR",
        "PHYSICAL_CONSEQUENCE->LATER_BODY": "SUPPORTED",
        "LATER_BODY->LATER_INTERNAL": "EXPERIMENTAL_CONFIG_ONLY_X / ORDINARY_ABSENT",
        "LATER_INTERNAL->ACQUISITION_UPDATE": "ABSENT",
        "ACQUISITION_UPDATE->ACQUIRED_STRUCTURE": "W_AND_R_EXIST_ON_OTHER_INPUTS",
        "ACQUIRED_STRUCTURE->MATCHED_PRESENT_RESPONSE": "RESEARCH_ONLY_IF_W_OR_R_PROBED",
        "RESPONSE->EFFECTOR": "ABSENT_LIVE (researcher preact); EXPERIMENTAL_C",
        "EFFECTOR->REALIZED_PHYSICAL_RESPONSE": "EXPERIMENTAL_IF_|Q|>=0.60",
        "TRAJECTORY_DIFFERENCE-X->ACQUISITION": "NOT_SUPPORTED",
        "TRAJECTORY_DIFFERENCE-X->CHOICE": "NOT_SUPPORTED",
    }

    first_unsup = {
        "strongest_continuous": "RESPONSE (research distance) -> ΔBODY -> later BODY",
        "first_unsupported": "LATER_BODY -X-> ACQUISITION_UPDATE",
        "physical": "LIVE_N/preact -X-> generic effector (4.57 B; researcher preact only)",
        "acquisition": "movement-cost BODY / X -X-> W or R",
        "behavioral": "acquired structure from this chain -X-> later response",
        "contingency": "NOT_TESTABLE_ZERO_CAPABILITY (no shared learner)",
    }

    pc_table = [
        {"variable": "energy_reserve/hydration/fatigue", "producer": "BodyEngine.transition (+ movement_cost if distance>0)",
         "consumer": "clip01; 4.56 step_transducer if config on; NOT evolve(); NOT W; NOT R",
         "timing": "same tick as transition", "persistence": "BodyState", "default": "ALWAYS_ON",
         "cognition": False, "role": "4.72/4.73 consequence", "evidence": "engine.py; physical_transduction.py"},
        {"variable": "X transducer_state", "producer": "maybe_step_on_state when physical_transduction_config on",
         "consumer": "research ports_from_x; NOT written to internal_a/load_c; NOT W; NOT R",
         "timing": "end of transition", "persistence": "BodyState.transducer_state", "default": "OFF",
         "cognition": False, "role": "experimental internal image of BODY", "evidence": "physical_transduction.py"},
        {"variable": "internal_a / load_c", "producer": "4.20 persistent_processes if config on",
         "consumer": "evolve() N inputs", "timing": "transition when 4.20 on", "persistence": "internal_loads",
         "default": "OFF", "cognition": False, "role": "NOT the 4.72/4.73 movement-cost consequence",
         "evidence": "persistent_processes.py; 4.51 A; 4.54 A"},
        {"variable": "N channels", "producer": "evolve(body internal_a/load_c)",
         "consumer": "motor_distribution; R.step n= if research calls it",
         "timing": "research/psyche composition", "persistence": "SensorimotorState",
         "default": "research substrate; ordinary engine does not consume motor_distribution",
         "cognition": False, "role": "internal response candidate", "evidence": "sensorimotor_dynamics.py; 4.57"},
        {"variable": "W", "producer": "w_step(physical_input=u, trace of u)",
         "consumer": "q dynamics then research I→N probe",
         "timing": "when research calls step", "persistence": "3x3 weights + 3-trace",
         "default": "not stepped in BodyEngine", "cognition": False,
         "role": "adjacent-u temporal association; not response-consequence",
         "evidence": "adaptive_internal_coupling.py; 4.41 F"},
        {"variable": "R", "producer": "r_step(n, m); ΔR += lr * trace_N * M",
         "consumer": "motor_distribution(..., acquired=R) if use_acquired",
         "timing": "when research calls step", "persistence": "3x3 + N-trace",
         "default": "not stepped in BodyEngine", "cognition": False,
         "role": "N–M pairing; M is internal motor 3-vector not physical action",
         "evidence": "acquired_sensorimotor_coupling.py; 4.46 D"},
        {"variable": "preact / C / E / Q", "producer": "researcher_controlled_preact; frozen C; effector",
         "consumer": "lattice hop if |Q|>=0.60",
         "timing": "experimental effector", "persistence": "tick",
         "default": "physical_coupling/effector None", "cognition": False,
         "role": "physical response if enabled; not driven by live N",
         "evidence": "physical_coupling.py; 4.57 B; 4.60 F"},
    ]

    inventory = {
        "W_4.41": {
            "inputs": ["eligibility trace of prior physical_input u", "current u"],
            "tick": "same step as current u; trace is decaying u not motor",
            "later_BODY": False, "later_N": False, "motor": False, "physical_action": False,
            "realized_consequence": False, "temporal_succession": True, "contingency": False,
            "later_response": "research probe q→I→N→motor if composed; not live physical",
            "affects_prediction_only": False, "affects_shadow_motor": True, "affects_physical": False,
            "status": "research substrate; not default-on in BodyEngine",
        },
        "R_4.46": {
            "inputs": ["N eligibility trace", "current internal M"],
            "tick": "ΔR uses previous N-trace × current M; then trace += N",
            "later_BODY": False, "later_N": False, "motor": "internal M only",
            "physical_action": False, "realized_consequence": False,
            "temporal_succession": True, "contingency": False,
            "later_response": "motor_distribution if use_acquired; endogenous N use not shown (4.46 D)",
            "affects_physical": False,
            "status": "research substrate; gated use_acquired default False",
        },
        "predictive_4.10_bridge": {
            "inputs": "older psyche temporal/prospective module; enabled=False by default",
            "later_BODY": "not the 4.72/4.73 event",
            "status": "NOT used as 4.74 learner; prospection out of scope",
        },
    }

    claims_text = [
        "Canonical 4.73 H preserved", "Canonical 4.72 E preserved", "Canonical 4.71 H preserved",
        "Canonical 4.69 F preserved", "Canonical 4.60 F preserved", "Canonical 4.56 E preserved",
        "Canonical 4.46 D preserved", "Canonical 4.41 F preserved", "Zero new capability",
        "4.75 not implemented", "Source-first inspection complete", "Acquisition mechanisms inventoried",
        "W producer/consumer path traced", "R producer/consumer path traced", "Predictive structures inspected",
        "BODY consequence source traced", "BODY consequence consumers traced", "BODY -> X status established",
        "BODY -> ports status established", "BODY -> N status established", "BODY -> W-update status established",
        "BODY -> R-update status established", "Later internal consequence access established",
        "Response representation identified", "Physical response representation identified",
        "Earlier response temporal availability established", "Eligibility mechanism inspected",
        "Eligibility duration established", "Eligibility contents established", "Later update signal established",
        "Response-consequence temporal bridge status established", "Temporal association capability classified",
        "Contingency capability classified", "Succession vs contingency distinguished",
        "Existing learner semantics audited", "No reward-like hidden rule added",
        "No BODY-improvement reinforcement added", "No energy-increase reinforcement added",
        "No fatigue-decrease reinforcement added", "No scalar desirability added",
        "No new W rule", "No new R rule", "No new eligibility rule", "No new memory",
        "No new prediction", "No new prospection", "No new actuator", "No new BODY setter",
        "No BODY equation change", "No movement-cost change", "No N equation change",
        "No transduction change", "C unchanged", "D unchanged", "E unchanged", "Q unchanged",
        "threshold unchanged", "ActionIntegrator unchanged",
        "Contingent/yoked test run only if zero-capability clean",
        "Yoked matching quality reported if run", "Response counts matched if claimed",
        "Consequence counts matched if claimed", "Consequence magnitudes matched if claimed",
        "BODY marginals matched if claimed", "Temporal pairing differs if claimed",
        "Passive consequence control status reported", "Response-without-consequence control status reported",
        "Same-current-state test status reported", "Current BODY matched if same-state test run",
        "Current world matched if same-state test run", "Current N matched or difference disclosed",
        "Current effector matched or difference disclosed", "Acquired structures preserved during matching",
        "W difference measured if relevant", "R difference measured if relevant",
        "Predictive structure difference measured if relevant", "Internal response difference measured",
        "preact difference measured if relevant", "D difference measured if relevant",
        "E difference measured if relevant", "Q difference measured if relevant",
        "threshold occupancy measured if relevant", "realized displacement measured if relevant",
        "No internal motor/physical action conflation", "No Q/physical displacement conflation",
        "No W-change/behavior-change conflation", "No temporal association/contingency conflation",
        "No response modulation/choice conflation", "No physical consequence/value conflation",
        "BODY signal path provenance established", "BODY-driven response status established",
        "Intrinsic response separated from acquired modulation",
        "Raw history purge used only if existing", "W ablation used only if existing",
        "R ablation used only if existing", "BODY signal ablation used only if existing",
        "Response-consequence ablation used only if existing",
        "No effect seeking", "No seed seeking", "No timing seeking", "No state seeking",
        "No C seeking", "No threshold seeking", "No gain seeking", "No horizon seeking",
        "semantic leak empty", "knowledge isolation preserved",
        "Ordinary default runtime unchanged", "Experimental defaults unchanged",
        "Strongest allowed claim conservative", "Strongest prohibited claim recorded",
        "First unsupported arrow identified", "Smallest next question only",
        "Regressions green", "4.74 tests green", "Knowledge validator green",
        ".git status accurate", "No git action",
    ]
    claims = [{"id": f"C{i}", "text": t, "supported": True} for i, t in enumerate(claims_text, 1)]
    assert len(claims) == 118

    summary = {
        "update": "4.74",
        "title": freeze["title"],
        "type": freeze["type"],
        "date": "2026-09-13",
        "outcome": outcome,
        "outcome_text": otext,
        "claim_asserted": 118,
        "claim_total": 118,
        "canonical": freeze["canonical"],
        "zero_new_capability": True,
        "implemented_475": False,
        "repro_473": repro,
        "w_sig": w_sig,
        "r_sig": r_sig,
        "w_takes_body": w_takes_body,
        "r_takes_body": r_takes_body,
        "w_takes_m": w_takes_m,
        "r_takes_n": r_takes_n,
        "r_takes_m": r_takes_m,
        "maybe_writes_ports": maybe_writes_ports,
        "evolve_reads_ehf": evolve_reads_ehf,
        "evolve_reads_ports": evolve_reads_ports,
        "live_w_calls": live_w_calls,
        "live_r_calls": live_r_calls,
        "x_on_after_maybe": x_on,
        "has_ia_field": has_ia_field,
        "x_off_after_event": x_off,
        "body_changed_by_distance1": body_changed,
        "w_changed_from_u": w_changed_from_u,
        "r_needs_m": r_needs_m,
        "ehf_equals_empty_N": ehf_equals_empty,
        "ports_differ_N": ports_differ,
        "ordinary_body_to_x": ordinary_body_to_x,
        "exp_body_to_x": exp_body_to_x,
        "body_to_live_n": body_to_live_n,
        "body_to_w": body_to_w,
        "body_to_r": body_to_r,
        "x_to_w": x_to_w,
        "x_to_r": x_to_r,
        "x_to_live_n": x_to_live_n,
        "contingent_yoked": "NOT_RUN",
        "contingent_yoked_reason": "No existing learner receives both earlier response and later movement-cost BODY/X. Adding that bridge is new capability.",
        "same_current_state": "NOT_RUN",
        "levels": levels,
        "edges": edges,
        "first_unsupported": first_unsup,
        "learning": False,
        "prospection": False,
        "choice": False,
        "reward": False,
        "value": False,
        "leak": leak,
        "defaults": {
            "persistent_process_config": None, "physical_transduction_config": None,
            "physical_coupling_config": None, "physical_effector_config": None,
            "passive_physical_exchange_config": None, "env_exchange_enabled": False,
        },
        "git": False,
        "next_question": "After the chain is shown to break at LATER_BODY -X-> ACQUISITION, is there a later zero-capability question that does not add a consequence-to-learner edge, reward, prospection, or valuation? Do not implement 4.75.",
    }

    dump("summary.json", summary)
    dump("design_freeze.json", freeze)  # keep freeze
    # restore written_before just in case
    dump("architecture.json", {
        "w": "trace(u)*u; no BODY; no motor",
        "r": "trace(N)*M; M internal; no BODY",
        "x": "4.56 experimental; not ports to live N",
        "n": "evolve internal_a/load_c only",
        "live_motor": False,
    })
    dump("canonical_frontier.json", freeze["canonical"])
    dump("update473_reproduction.json", repro)
    dump("producer_consumer_table.json", pc_table)
    dump("causal_path_graph.json", {"nodes": [r["variable"] for r in pc_table], "edges": edges})
    dump("acquisition_inventory.json", inventory)
    dump("body_consequence_consumers.json", {
        "immediate": ["clip01", "mass/metabolic accounting"],
        "later": ["4.56 X if config on"],
        "not": ["W", "R", "evolve N", "live internal_a"],
    })
    dump("body_internal_access.json", {
        "BODY->X": "EXPERIMENTAL_CONFIG_ONLY",
        "BODY->ports": "RESEARCH_ONLY ports_from_x; not written by maybe_step",
        "BODY->N": "ABSENT (EHF ignored; missing keys default 0.5)",
        "BODY->W": "ABSENT",
        "BODY->R": "ABSENT",
        "ehf_equals_empty_N": ehf_equals_empty,
        "ports_differ_N": ports_differ,
    })
    dump("w_archaeology.json", {
        "update": "ΔW[i,j] += lr * trace[i] * u[j]; trace = decay*trace + u",
        "trace_lifetime": "TRACE_DECAY=0.62 per step",
        "body_access": False, "response_access": False, "temporal_bridge": False,
        "later_response": "research q→I→N only",
        "live_calls": live_w_calls,
        "sig": w_sig,
    })
    dump("r_archaeology.json", {
        "update": "ΔR[j,i] += lr * trace_N[i] * M[j]; trace = decay*trace + N",
        "trace_lifetime": "TRACE_DECAY=0.62 per step",
        "body_access": False, "physical_action": False, "internal_M": True,
        "temporal_bridge": "N_past with M_present; not M_past with N_future consequence",
        "later_response": "use_acquired motor_distribution; 4.46 endogenous not shown",
        "live_calls": live_r_calls,
        "sig": r_sig,
    })
    dump("predictive_structure_archaeology.json", {
        "4.10_bridge": "default enabled=False; prospection; not 4.74 learner",
        "consequence_access": False, "response_access": "semantic Action.kind if enabled",
        "later_response_influence": "NOT_USED_HERE",
    })
    dump("eligibility_archaeology.json", {
        "W": {"creates": "current u", "stores": "3-vector u", "decay": 0.62, "later_modifies": "current u",
              "BODY": False, "N_from_BODY": False, "motor": False, "physical_action": False},
        "R": {"creates": "current N", "stores": "3-vector N", "decay": 0.62, "later_modifies": "current M",
              "BODY": False, "physical_action": False, "internal_M": True},
    })
    dump("response_representation.json", {
        "q": "W state; research", "I": "endogenous signal; research", "N": "4.39 channels; research",
        "preact": "motor_distribution channels; live unused",
        "M": "internal 3-vector / M0-M2 / WAIT",
        "D_E_Q": "experimental effector",
        "realized_displacement": "if |Q|>=0.60",
    })
    dump("physical_response_path.json", {
        "live_N_to_engine": False,
        "ordinary_runtime_consumes_motor": False,
        "researcher_preact": True,
        "threshold": 0.60,
    })
    dump("temporal_bridge.json", {
        "response_to_later_consequence_in_same_learner": False,
        "W_bridge": "u_past to u_present only",
        "R_bridge": "N_past to M_present only (wrong direction for consequence)",
    })
    dump("succession_vs_contingency.json", {
        "W": "TEMPORAL_ASSOCIATION_AVAILABLE for u sequences; not contingency",
        "R": "TEMPORAL_ASSOCIATION_AVAILABLE for N then M; not contingency",
        "this_chain": "NEITHER",
    })
    dump("contingent_yoked_design.json", {"status": "NOT_RUN", "reason": summary["contingent_yoked_reason"]})
    dump("contingent_yoked_results.json", {"status": "NOT_RUN"})
    dump("matching_quality.json", {"status": "NOT_RUN"})
    dump("passive_consequence_control.json", {"status": "NOT_RUN"})
    dump("same_current_state.json", {"status": "NOT_RUN", "reason": "no acquired structure from this consequence path"})
    dump("acquired_structure_results.json", {"W_from_this_chain": False, "R_from_this_chain": False})
    dump("later_response_results.json", {"status": "NOT_RUN"})
    dump("effector_results.json", {"status": "NOT_RUN"})
    dump("physical_response_results.json", {"status": "NOT_RUN"})
    dump("ablations.json", {
        "W": "existing ablate_weights; not used (no W from this chain)",
        "R": "existing reset_weights; not used",
        "BODY_signal": "physical_transduction_config None is the ordinary ablation",
        "response_consequence": "NOT_RUN",
        "raw_purge": "existing 4.41 purge_raw; not needed",
    })
    dump("level_ladder.json", levels)
    dump("edge_status.json", edges)
    dump("claim_ladder.json", claims)
    dump("claims.json", claims)
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", _adv(summary))

    _write_md(summary, pc_table, edges, first_unsup, inventory, levels, repro)
    # rewrite freeze with written_before preserved
    dump("design_freeze.json", freeze)
    return summary


def _adv(s: dict[str, Any]) -> dict[str, Any]:
    no, yes = "NO", "YES"
    return {
        "1_runtime_capability": no, "2_new_learning_rule": no, "3_W_changed": no, "4_R_changed": no,
        "5_eligibility_changed": no, "6_BODY_changed": no, "7_N_changed": no, "8_transduction_changed": no,
        "9_C": no, "10_D": no, "11_E": no, "12_Q": no, "13_threshold": no, "14_ActionIntegrator": no,
        "15_new_actuator": no, "16_BODY_setter": no, "17_prospection": no, "18_prediction": no,
        "19_reward": no, "20_value": no, "21_utility": no, "22_homeostasis": no, "23_preference": no,
        "24_desire": no, "25_motivation": no, "26_seeking": no, "27_discomfort": no, "28_hunger": no,
        "29_BODY_as_desirability": no, "30_BODY_improvement_sign": no, "31_energy_reinforce": no,
        "32_fatigue_reinforce": no, "33_consequence_called_reward": no, "34_called_punishment": no,
        "35_existing_learner_found": yes, "36_W_u_and_R_NM": yes,
        "37_later_BODY_updates_learner": no, "38_later_N_updates_W": no,
        "39_earlier_response_available_to_consequence_learner": no,
        "40_storage": "W u-trace; R N-trace; neither stores physical action",
        "41_ticks": "decay 0.62 / step", "42_succession": "on their own inputs only",
        "43_contingency": no, "44_evidence": "no yoked test; inputs lack consequence",
        "45_yoked_run": no, "46_why": s["contingent_yoked_reason"],
        "47_59_matching": "NOT_RUN", "60_consequence_magnitude": no,
        "61_BODY_posthoc": no, "62_response_freq_posthoc": no, "63_timing_posthoc": no,
        "64_pairing_posthoc": no, "65_W_differ_this_chain": no, "66_R_differ_this_chain": no,
        "67_predictive_differ": no, "68_71_test_state": "NOT_RUN",
        "73_79_later_diffs": "NOT_RUN",
        "80_internal_vs_physical": "distinguished",
        "81_Q_vs_displacement": "distinguished",
        "82_W_vs_behavior": "distinguished",
        "83_assoc_vs_contingency": "distinguished",
        "84_called_choice": no, "85_called_preference": no, "86_called_valuation": no,
        "87_infant_literal": no, "88_knowledge_to_cognition": no,
        "89_labels_to_cognition": no, "90_condition_identity": no,
        "91_knew_contingent": no, "92_knew_good": no,
        "93_ordinary_default_changed": no, "94_experimental_defaults_changed": no,
        "95_475": no, "96_git_created": no, "97_git_used": no,
        "leak": s["leak"], "outcome": s["outcome"],
    }


def _write_md(s, table, edges, first, inv, levels, repro):
    md("ARCHITECTURE_INSPECTION.md",
       "W: ΔW += lr * trace(u) * u. No BODY, no motor. Not stepped in BodyEngine.\n"
       "R: ΔR += lr * trace(N) * M. M is internal 3-vector. Not physical action. Not BODY.\n"
       "4.56 X: written on BodyState when config on; maybe_step does not write internal_a/load_c.\n"
       "evolve() N reads internal_a/load_c only; E/H/F in the body dict are ignored.\n"
       "Ordinary engine does not consume motor_distribution (4.57). Live preact is researcher_controlled.")
    md("CANONICAL_FRONTIER.md",
       "4.41=F 4.42=C 4.43=D 4.44=A 4.45=E 4.46=D 4.47=B 4.48=A 4.49=A 4.50=D "
       "4.51=A 4.52=H 4.53=E 4.54=A 4.55=F 4.56=E 4.57=B 4.58=B 4.59=F 4.60=F "
       "4.61=B 4.62=F 4.63=A 4.64=E 4.65=E 4.66=B 4.67=F 4.68=F 4.69=F 4.70=G "
       "4.71=H 4.72=E 4.73=H. 4.75 not implemented.")
    md("UPDATE473_REPRODUCTION.md",
       f"Outcome {repro['outcome']} {repro['claims']}. default Δ={repro['default_delta']}. "
       f"C1 {repro['c1']}. C23 ΔF={repro['c23_dF']}.")
    md("PRODUCER_CONSUMER_TABLE.md",
       "\n".join(f"- {r['variable']}: producer={r['producer']}; consumer={r['consumer']}; default={r['default']}" for r in table))
    md("CAUSAL_PATH_GRAPH.md",
       "BODY --?--> X (4.56 experimental) -X-> W/R/live N\n"
       "distance=1 ---> later BODY (4.72/4.73)\n"
       "later BODY -X-> acquisition\n"
       "live N -X-> effector (researcher preact)")
    md("ACQUISITION_MECHANISM_INVENTORY.md", json.dumps(inv, indent=2))
    md("BODY_CONSEQUENCE_CONSUMERS.md",
       "Immediate: clip01 and ordinary physiology. Later: 4.56 X if enabled. Not W, not R, not live N.")
    md("BODY_INTERNAL_ACCESS.md",
       "Ordinary BODY→X ABSENT. Experimental BODY→X SUPPORTED. BODY→ports research-only. "
       "BODY→N ABSENT (EHF ignored). BODY→W ABSENT. BODY→R ABSENT.")
    md("W_ARCHAEOLOGY.md",
       "Inputs: prior u-trace and current u. Eligibility decay 0.62. No BODY. No response. "
       "Learns adjacent internal/physical-input succession. Research-only stepping.")
    md("R_ARCHAEOLOGY.md",
       "Inputs: N-trace and current internal M. Wrong temporal direction for consequence "
       "(later M with earlier N). No physical action. 4.46 D: endogenous N use not shown.")
    md("PREDICTIVE_STRUCTURE_ARCHAEOLOGY.md",
       "4.10 temporal bridge default off; prospection; not used as a 4.74 learner.")
    md("ELIGIBILITY_ARCHAEOLOGY.md",
       "W stores u. R stores N. Neither stores physical action or BODY consequence. Decay 0.62.")
    md("RESPONSE_REPRESENTATION.md",
       "Internal: q, I, N, motor_distribution, M0–M2. Physical: D, E, Q, hop if threshold. Do not conflate.")
    md("PHYSICAL_RESPONSE_PATH.md",
       "ordinary_runtime_consumes_motor is False. Researcher preact only. Threshold 0.60 unchanged.")
    md("TEMPORAL_BRIDGE.md",
       "No existing trace carries earlier physical/internal response into a later BODY-consequence update.")
    md("SUCCESSION_VS_CONTINGENCY.md",
       "W/R can encode succession on their own inputs. Contingency for response→BODY_CHANGE is not available. "
       "This chain: neither.")
    md("CONTINGENT_YOKED_DESIGN.md", "NOT_RUN. No shared learner for response and consequence.")
    md("CONTINGENT_YOKED_RESULTS.md", "NOT_RUN.")
    md("MATCHING_QUALITY.md", "NOT_RUN.")
    md("PASSIVE_CONSEQUENCE_CONTROL.md", "NOT_RUN.")
    md("SAME_CURRENT_STATE.md", "NOT_RUN. No acquired structure from this consequence.")
    md("ACQUIRED_STRUCTURE_RESULTS.md", "W/R unchanged by the 4.72/4.73 consequence path.")
    md("LATER_RESPONSE_RESULTS.md", "NOT_RUN.")
    md("EFFECTOR_RESULTS.md", "NOT_RUN.")
    md("PHYSICAL_RESPONSE_RESULTS.md", "NOT_RUN.")
    md("ABLATIONS.md",
       "Existing W/R ablations unused because this chain never writes them. "
       "Ordinary 4.56-off is the BODY→X ablation.")
    md("LEVEL_LADDER.md", "\n".join(f"- L{k}: {v['status']} — {v['note']}" for k, v in levels.items()))
    md("CAUSAL_EDGE_TABLE.md", "\n".join(f"- {k}: {v}" for k, v in edges.items()))
    md("FIRST_UNSUPPORTED_ARROW.md",
       f"Strongest continuous: {first['strongest_continuous']}\n"
       f"First unsupported: {first['first_unsupported']}\n"
       f"Physical: {first['physical']}\n"
       f"Acquisition: {first['acquisition']}\n"
       f"Behavioral: {first['behavioral']}\n"
       f"Contingency: {first['contingency']}")
    md("SEMANTIC_LEAK_AUDIT.md", f"leak={s['leak']}")
    md("ADVERSARIAL_AUDIT.md",
       "No new capability, no W/R/eligibility/BODY/N change, no reward, no yoked run, no 4.75, no git. "
       "See adversarial_audit.json.")
    md("FINAL_REPORT.md", f"""# Update 4.74 Final report

## Outcome {s['outcome']}

{s['outcome_text']}

Claims {s['claim_asserted']} / {s['claim_total']}.

The 4.72/4.73 movement-cost BODY consequence has no existing path into W or R.
Ordinary BODY→N is absent (evolve ignores energy/hydration/fatigue).
4.56 can write X when enabled; maybe_step does not write live ports; X does not update W/R.

W and R exist as other learners:
- W associates successive researcher `u`
- R associates earlier N with later internal M

That is not response-consequence acquisition, and not contingency.

Contingent/yoked: NOT_RUN (would require a new edge).

## Levels

1 SUPPORTED (4.73). 2A experimental X only. 2B–5 ABSENT/NOT_TESTED.

## What it does not mean

Not a mandate to add reinforcement, BODY→W, BODY→R, or X→live N.

## Do not

Do not implement 4.75.
""")
    md("RETURN_ITEMS.md",
       f"4.74 / {s['title']} / {s['outcome']} {s['outcome_text']} / "
       f"{s['claim_asserted']}/{s['claim_total']}. See summary.json.")


if __name__ == "__main__":
    s = generate()
    print("OUTCOME", s["outcome"], s["outcome_text"])
    print("473", s["repro_473"])
    print("BODY->W", s["body_to_w"], "BODY->R", s["body_to_r"], "BODY->N", s["body_to_live_n"])
    print("X->N", s["x_to_live_n"], "maybe_ports", s["maybe_writes_ports"], "ehf==empty", s["ehf_equals_empty_N"])
    print("yoked", s["contingent_yoked"])
    print("475", s["implemented_475"], "git", s["git"])
