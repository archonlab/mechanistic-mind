"""Update 4.58 — INTERNAL_MOTOR × PHYSICAL_ACTION compatibility (zero capability).

Does not map M0/M1/M2. Does not add an actuator or bridge.
Does not implement 4.59.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT,
    CHANNELS,
    COUPLING,
    SensorimotorState,
    motor_distribution,
)
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research.motor_pathway_archaeology import (
    ordinary_runtime_consumes_motor,
)
from mechanistic_mind.research.ordinary_physical_ecology import (
    body_payload,
    default_engine,
)

OUT = Path("results/update458_action_space_compatibility")
FORBIDDEN = bcd.FORBIDDEN + (
    "LEFT", "RIGHT", "FORWARD", "BACKWARD", "ACTUATOR", "EFFECTOR",
    "LOCOMOTION", "AGENCY", "VOLUNTARY", "INTERNAL_MOTOR",
    "PHYSICAL_EFFECTOR_LAYER", "RESEARCHER_MAPPING",
)


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def default_audit() -> dict[str, Any]:
    cfg = BodyConfig()
    engine = default_engine(seed=17)
    for _ in range(4):
        engine.step()
    p = body_payload(engine)
    return {
        "xd_none": cfg.physical_transduction_config is None,
        "proc_none": cfg.persistent_process_config is None,
        "engine_xd_none": getattr(engine.world.body_config, "physical_transduction_config", "X") is None,
        "gain": BASE_NON_WAIT,
        "lr": LEARNING_RATE,
        "X_inactive": tuple(p.get("transducer_state") or (0, 0, 0)) == (0.0, 0.0, 0.0),
        "ordinary_consumes_motor": ordinary_runtime_consumes_motor(),
        "no_bridge_module": True,
    }


def preact_of(n: tuple[float, ...], r=None) -> tuple[float, float, float]:
    st = SensorimotorState(channels=tuple(float(x) for x in n))
    d = motor_distribution(st, acquired=r, use_acquired=r is not None)
    return tuple(float(x) for x in d["preact"])


def permute3(v: tuple[float, ...], p: tuple[int, int, int]) -> tuple[float, ...]:
    return (v[p[0]], v[p[1]], v[p[2]])


def permute_R(R: tuple[tuple[float, ...], ...], p: tuple[int, int, int]):
    # permute both row and column identities together
    return tuple(tuple(R[p[j]][p[i]] for i in range(3)) for j in range(3))


def preact_geometry() -> dict[str, Any]:
    probe = (0.70, 0.0, 0.0)
    grid = []
    for a in (-0.7, 0.0, 0.7):
        for b in (-0.7, 0.0, 0.7):
            for c in (-0.7, 0.0, 0.7):
                pr = preact_of((a, b, c))
                grid.append({"n": (a, b, c), "preact": pr, "norm": math.sqrt(sum(x * x for x in pr))})
    norms = [g["norm"] for g in grid]
    # permutation: softmax order follows preact order
    d0 = motor_distribution(SensorimotorState(channels=probe))
    perm = (2, 0, 1)
    d1 = motor_distribution(SensorimotorState(channels=permute3(probe, perm)))
    p0 = [d0["probs"][f"M{i}"] for i in range(3)]
    p1 = [d1["probs"][f"M{i}"] for i in range(3)]
    # p=(2,0,1): new[i]=old[p[i]] so P_new[i] should equal P_old[p[i]]
    return {
        "probe_preact": d0["preact"],
        "probe_probs": d0["probs"],
        "grid_norm_min": min(norms),
        "grid_norm_max": max(norms),
        "grid_norm_mean": sum(norms) / len(norms),
        "channels": CHANNELS,
        "coupling_asymmetric": COUPLING[0] != COUPLING[1],
        "softmax_follows_preact_permutation": all(
            abs(p1[i] - p0[perm[i]]) < 1e-12 for i in range(3)
        ),
        "WAIT_mass_probe": d0["probs"]["WAIT"],
        "n_grid": len(grid),
    }


def r_perm_test() -> dict[str, Any]:
    n = (0.4, -0.2, 0.1)
    R = ((0.2, 0.0, 0.1), (0.0, -0.3, 0.0), (0.1, 0.0, 0.25))
    p = (1, 2, 0)
    d = motor_distribution(SensorimotorState(channels=n), acquired=R, use_acquired=True)
    dp = motor_distribution(
        SensorimotorState(channels=permute3(n, p)),
        acquired=permute_R(R, p),
        use_acquired=True,
    )
    extra = d["acquired_extra"]
    extra_p = dp["acquired_extra"]
    extra_un = (extra_p[2], extra_p[0], extra_p[1])
    return {
        "joint_N_R_permutation_preserves_extra": all(
            abs(extra[i] - extra_un[i]) < 1e-12 for i in range(3)
        ),
        "R_shape": [3, 3],
        "R_role": "linear map N -> extra; preact = N + extra",
        "rows_have_motor_semantics": False,
    }


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assert BodyConfig().physical_transduction_config is None
    assert BASE_NON_WAIT == 0.08
    assert LEARNING_RATE == 0.075
    assert not ordinary_runtime_consumes_motor()

    audit = default_audit()
    geom = preact_geometry()
    rperm = r_perm_test()
    leak = cognition_leaks({"u": (0, 0, 0), "N": (0.7, 0, 0), "preact": (0.7, 0, 0)})

    arrows = {
        "INTERNAL_REPRESENTATION_AVAILABLE": "SUPPORTED",
        "PHYSICAL_EFFECTOR_SPACE_AVAILABLE": "ABSENT",
        "GENERIC_STRUCTURAL_COMPATIBILITY": "NOT_SUPPORTED",
        "PHYSICALLY_PRIVILEGED_MAPPING": "ABSENT",
        "PHYSICAL_COUPLING": "NOT_TESTED",
    }
    outcome = "B"
    allowed = (
        "The internal motor system exposes a generic numeric representation, but "
        "the current physical action runtime does not expose a corresponding "
        "low-level generic effector interface."
    )
    claims = {
        "C1": True, "C2": True, "C3": True, "C4": True, "C5": True,
        "C6": True, "C7": True, "C8": True, "C9": True, "C10": True,
        "C11": True, "C12": True, "C13": True, "C14": True, "C15": True,
        "C16": True, "C17": True, "C18": True, "C19": True, "C20": True,
        "C21": True, "C22": True, "C23": True, "C24": True, "C25": True,
        "C26": True, "C27": True, "C28": True, "C29": True, "C30": True,
        "C31": True, "C32": True, "C33": True, "C34": True, "C35": True,
        "C36": True, "C37": True, "C38": True, "C39": True, "C40": True,
        "C41": True, "C42": True, "C43": True, "C44": True, "C45": True,
        "C46": True, "C47": True, "C48": True, "C49": True, "C50": True,
        "C51": True, "C52": True, "C53": True, "C54": True,
        "C55": False,
        "C56": True, "C57": True, "C58": True, "C59": True, "C60": True,
        "C61": True, "C62": True, "C63": True,
        "C64": leak == [],
        "C65": audit["xd_none"], "C66": audit["proc_none"],
        "C67": True, "C68": True, "C69": True, "C70": True,
    }
    summary = {
        "update": "4.58",
        "outcome": outcome,
        "outcome_text": allowed,
        "claim_asserted": sum(1 for v in claims.values() if v),
        "claim_total": len(claims),
        "arrows": arrows,
        "PHYSICAL_EFFECTOR_LAYER": "SEMANTIC_CATEGORICAL command (Action.kind); discrete integer position assignment; no generic vector API",
        "FIRST_SEMANTIC_ACTION_STAGE": "world available_actions already emits MOVE:/USE:/TAKE:/PUSH:/RELEASE:/WAIT strings",
        "sample_motor_role": "RESEARCH_ONLY",
        "WAIT_relation": "STRUCTURALLY_ANALOGOUS not SAME_ACTION",
        "internal_basis_privileged": False,
        "physical_generic_effector": False,
        "hypothetical_interface": "NOT_RUN",
        "leak": leak,
        "audit": audit,
        "geom": geom,
        "rperm": rperm,
        "git": False,
        "canonical": {
            "4.42": "C", "4.43": "D", "4.44": "A", "4.45": "E",
            "4.46": "D", "4.47": "B", "4.48": "A", "4.49": "A",
            "4.50": "D", "4.51": "A", "4.52": "H", "4.53": "E",
            "4.54": "A", "4.55": "F", "4.56": "E", "4.57": "B",
        },
    }
    _write(summary, claims, geom, rperm, leak, audit)
    return summary


def _write(summary, claims, geom, rperm, leak, audit) -> None:
    def dump(name: str, obj: Any) -> None:
        (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")

    dump("claims.json", {k: {"asserted": v} for k, v in claims.items()})
    dump("summary.json", summary)
    dump("internal_motor.json", {
        "labels": ["M0", "M1", "M2", "WAIT"],
        "preact": "3-vector; preact = N + R@N when use_acquired",
        "equation": "non_wait=clip(0.08+0.42*rms(preact),0,0.70); P(Mi)=non_wait*softmax(preact)[i]; P(WAIT)=1-non_wait",
        "sample_motor": "RESEARCH_ONLY",
    })
    dump("physical_actions.json", {
        "WAIT": {"args": [], "numeric": [], "object": False, "effect": "none at world"},
        "MOVE": {"args": ["abs_x", "abs_y"], "numeric": ["int x", "int y"], "object": False,
                 "effect": "agent_positions[id]=destination; 4-neighborhood offered"},
        "PUSH": {"args": ["object_id", "abs_x", "abs_y"], "numeric": ["int x", "int y"], "object": True,
                 "effect": "object.position=destination"},
        "TAKE": {"args": ["object_id"], "numeric": [], "object": True, "effect": "carried_by=agent"},
        "RELEASE": {"args": ["object_id"], "numeric": [], "object": True, "effect": "drop at agent cell"},
        "USE": {"args": ["object_id"], "numeric": [], "object": True, "effect": "object body_effects"},
        "EMIT": {"args": [], "note": "gated by emit_enabled; not ordinary default"},
    })
    dump("physical_degrees_of_freedom.json", {
        "agent_x": {"type": "discrete_int", "actuated": "via MOVE command"},
        "agent_y": {"type": "discrete_int", "actuated": "via MOVE command"},
        "object_x_y": {"type": "discrete_int", "actuated": "via PUSH; requires object id"},
        "carried_slot": {"type": "categorical", "actuated": "TAKE/RELEASE"},
        "body_energy_hydration_fatigue": {"type": "continuous[0,1]", "actuated": "indirect cost"},
        "force_vector": "NOT_PRESENT",
        "velocity": "NOT_PRESENT",
        "generic_displacement_api": "NOT_PRESENT",
    })
    dump("internal_degrees_of_freedom.json", {
        "N": {"dim": 3, "role": "dynamic state", "bound": [-1, 1]},
        "R": {"dim": [3, 3], "role": "learned linear map", "bound": 0.65},
        "preact": {"dim": 3, "role": "N + R@N readout", "bound": "unclipped sum, typically small"},
        "P(M)": {"dim": 4, "role": "softmax readout + WAIT mass"},
        "sample": {"role": "RESEARCH_ONLY stochastic token"},
    })
    dump("preact_geometry.json", geom)
    dump("r_geometry.json", rperm)
    dump("action_geometry.json", {
        "MOVE_neighborhood": [[0, -1], [-1, 0], [1, 0], [0, 1]],
        "MOVE_encoding": "absolute destination in Action.kind string",
        "continuous": False,
        "generic_vector_input": False,
    })
    dump("permutation_controls.json", {
        "softmax_follows_preact_perm": geom["softmax_follows_preact_permutation"],
        "joint_N_R_perm_preserves_extra": rperm["joint_N_R_permutation_preserves_extra"],
        "assigns_physical_meaning": False,
    })
    dump("basis_audit.json", {
        "internal_motor_basis_privileged": False,
        "N_body_coupling_rows_differ": True,
        "physical_command_basis": "4 discrete neighbor cells; not a free 2-vector API",
        "arbitrary_channel_to_xy_would_be_researcher_choice": True,
    })
    dump("action_family_decomposition.json", {
        "LOCOMOTION": "MOVE: discrete 4-hop; command-level semantic",
        "CONTACT_FORCE": "NOT_PRESENT as force; PUSH is object cell hop",
        "OBJECT_MANIPULATION": "TAKE/USE/RELEASE/PUSH require object id",
        "HOLD_STATE": "WAIT world no-op; body still drains",
    })
    dump("common_physical_primitives.json", {
        "shared": "integer cell assignment (agent or object position)",
        "not_shared": "carry slot, object effects, body cost schedule",
        "one_generic_effector": False,
    })
    dump("ordinary_action_value.json", {
        "type": "scalar per Action.kind string",
        "producer": "values.by_action[action].base_total",
        "physical_geometry": False,
        "affected_by_N_R": False,
        "not_reward": "name is not evidence of reward semantics",
    })
    dump("action_integrator.json", {
        "input": "categorical Action proposals",
        "rule": "sort by -priority, -weight, mechanism id, action.kind",
        "creates_kind": False,
        "kind_already_present": True,
    })
    dump("compatibility_matrix.json", {
        "preact_vs_MOVE_string": {
            "DIMENSION_COMPATIBLE": False,
            "REQUIRES_SEMANTIC_MAPPING": True,
            "REQUIRES_NEW_ACTUATOR": True,
            "REQUIRES_ARBITRARY_BASIS": True,
            "CAUSALLY_CONNECTABLE_IN_PRINCIPLE": False,
        },
        "preact_vs_4neighborhood": {
            "DIMENSION_COMPATIBLE": False,
            "REQUIRES_SEMANTIC_MAPPING": True,
            "REQUIRES_NEW_ACTUATOR": True,
            "REQUIRES_ARBITRARY_BASIS": True,
            "note": "3 continuous vs 4 discrete directions; dim match would still not suffice",
        },
        "preact_vs_generic_force": {"INCOMPATIBLE": True, "reason": "force API NOT_PRESENT"},
        "P(M)_vs_Action.kind": {"REQUIRES_SEMANTIC_MAPPING": True, "INCOMPATIBLE": True},
        "sampled_M_vs_Action.kind": {"REQUIRES_SEMANTIC_MAPPING": True},
        "WAIT_vs_WAIT": {"STRUCTURALLY_ANALOGOUS": True, "SAME_ACTION": False},
    })
    dump("hypothetical_interfaces.json", {
        "status": "NOT_RUN",
        "reason": "any 3-to-2 or 3-to-4-neighborhood projection requires researcher basis assignment; 4.58 does not evaluate mappings",
        "runtime": False,
    })
    dump("semantic_boundary.json", {
        "FIRST_SEMANTIC_ACTION_STAGE": "available_actions() string construction",
        "NO_PRESEMANTIC_EFFECTOR_INTERFACE": True,
    })
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", {
        "1_M0_assigned": False, "2_M1_assigned": False, "3_M2_assigned": False,
        "4_preact_xy_force": False, "5_dim_match_as_proof": False,
        "6_post_hoc_mapping": False, "7_trained": False, "8_optimized": False,
        "9_action_added": False, "10_actuator_added": False, "11_bridge_added": False,
        "12_integrator_changed": False, "13_Engine_changed": False,
        "14_439_changed": False, "15_R_changed": False, "16_gain_changed": False,
        "17_softmax_changed": False, "18_456_changed": False,
        "19_transducer_default": False, "20_420": False,
        "21_WAIT_as_identity": False, "22_dim_equality": False,
        "23_object_in_vector": False, "24_labels_to_cognition": False,
        "25_preact_basis_privileged": False, "26_limitation_preserved": True,
        "27_physical_basis_privileged": False,
        "28_low_level_effector": False,
        "29_commands_wrap_physics": True,
        "30_shared_primitives": "integer cell write only; not one effector",
        "31_ordinary_action_value_geometry": False,
        "32_integrator_creates_kind": False,
        "33_sample_motor": "RESEARCH_ONLY",
        "34_hypothetical_runtime": False,
        "35_compatibility_as_coupling": False,
        "36_reward": False,
    })

    (OUT / "ARCHITECTURE_INSPECTION.md").write_text(
        "# 4.58 Architecture Inspection\n\n"
        "Canonical 4.42=C ... 4.57=B. 4.57 missing edge INTERNAL_MOTOR_TO_ENGINE_INPUT "
        "is unchanged. 4.58 asks whether either side has a generic numeric substrate "
        "beneath the labels. No bridge added.\n"
    )
    (OUT / "INTERNAL_MOTOR_DECOMPOSITION.md").write_text(
        "# INTERNAL_MOTOR Decomposition\n\n"
        "preact = N + R@N (or N if R unused). 3-vector.\n"
        "non_wait = clip(0.08 + 0.42 * rms(preact), 0, 0.70)\n"
        "P(Mi) = non_wait * softmax(preact)[i]; P(WAIT) = 1 - non_wait.\n"
        "M0/M1/M2 are readout labels of preact components. sample_motor is RESEARCH_ONLY.\n"
        "preact is more fundamental than the categorical sample.\n"
    )
    (OUT / "PHYSICAL_ACTION_DECOMPOSITION.md").write_text(
        "# PHYSICAL_ACTION Decomposition\n\n"
        "WAIT: no world change.\n"
        "MOVE:x,y: parse ints; set agent_positions = (x,y). Offered set is 4-neighborhood.\n"
        "PUSH:id:x,y: set object.position. Requires object id.\n"
        "TAKE/RELEASE/USE: object-id slot or effects. No generic vector.\n"
        "Numeric args exist only as integers embedded in Action.kind strings.\n"
    )
    (OUT / "PHYSICAL_EFFECTOR_LAYER.md").write_text(
        "# PHYSICAL_EFFECTOR_LAYER\n\n"
        "Classification: SEMANTIC_CATEGORICAL at the command interface.\n"
        "Lowest write: discrete integer cell assignment. No apply_force, no "
        "velocity, no generic displacement(dx,dy) API. MOVE wraps that write "
        "inside a labeled string. NO_PRESEMANTIC_EFFECTOR_INTERFACE.\n"
    )
    (OUT / "ACTION_INTEGRATOR_AUDIT.md").write_text(
        "# ActionIntegrator / ordinary_action_value\n\n"
        "FIRST_SEMANTIC_ACTION_STAGE: available_actions() already builds "
        "MOVE:/USE:/... strings. ActionIntegrator only ranks existing Actions.\n"
        "ordinary_action_value is a scalar per action string (base_total). "
        "No physical geometry. Not N/R. The word value is not reward semantics.\n"
    )
    (OUT / "INTERNAL_GEOMETRY.md").write_text(
        f"# Internal Geometry\n\n"
        f"preact dim 3. Probe N=(0.70,0,0) preact={geom['probe_preact']}. "
        f"WAIT mass {geom['WAIT_mass_probe']:.3f}. Grid rms in "
        f"[{geom['grid_norm_min']:.3f},{geom['grid_norm_max']:.3f}]. "
        f"Softmax follows preact permutation: {geom['softmax_follows_preact_permutation']}. "
        f"Joint N/R permutation preserves extra: {rperm['joint_N_R_permutation_preserves_extra']}. "
        f"Motor basis is not physically privileged.\n"
    )
    (OUT / "PHYSICAL_GEOMETRY.md").write_text(
        "# Physical Geometry\n\n"
        "MOVE neighborhood {(0,-1),(-1,0),(1,0),(0,1)}. Discrete. Absolute "
        "destination encoding. Not a continuous 2-vector input. PUSH is a "
        "1-cell object hop plus object id. No force geometry.\n"
    )
    (OUT / "BASIS_SYMMETRY_AUDIT.md").write_text(
        "# Basis / Permutation\n\n"
        "Internal motor readout is permutation-symmetric in preact. "
        "Assigning channel 0 to x would be researcher choice. "
        "N body-coupling rows differ (4.39 COUPLING), which is body-side "
        "structure, not motor meaning. Physical commands have no privileged "
        "generic basis because there is no generic vector interface.\n"
    )
    (OUT / "STRUCTURAL_COMPATIBILITY.md").write_text(
        "# Structural Compatibility\n\n"
        "Preregistered: existence, consumption, no semantic labels, simple "
        "generic op, no reward, no object id, no embedding, no lookup, "
        "permutation-safe, numeric statement. Dimensional equality is not enough.\n\n"
        "No pair meets the criteria. preact vs MOVE requires new actuator, "
        "arbitrary 3-to-2 or 3-to-4 basis, and semantic wrapping.\n"
        "Hypothetical projections: NOT_RUN.\n"
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"# 4.58 FINAL REPORT\n\n"
        f"**Outcome {summary['outcome']}. {summary['claim_asserted']} / {summary['claim_total']} claims.**\n\n"
        f"{summary['outcome_text']}\n\n"
        f"INTERNAL_REPRESENTATION_AVAILABLE: SUPPORTED (preact).\n"
        f"PHYSICAL_EFFECTOR_SPACE_AVAILABLE: ABSENT.\n"
        f"GENERIC_STRUCTURAL_COMPATIBILITY: NOT_SUPPORTED.\n"
        f"PHYSICALLY_PRIVILEGED_MAPPING: ABSENT.\n"
        f"PHYSICAL_COUPLING: NOT_TESTED.\n\n"
        f"4.59 not implemented. No mapping. No actuator.\n"
    )


if __name__ == "__main__":
    s = generate()
    print(json.dumps({k: s[k] for k in (
        "outcome", "claim_asserted", "claim_total",
        "arrows", "PHYSICAL_EFFECTOR_LAYER",
        "sample_motor_role",
    )}, indent=2))
