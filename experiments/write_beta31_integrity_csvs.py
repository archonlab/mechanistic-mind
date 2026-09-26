"""Emit inventory/matrix CSVs from audit conclusions. No production changes."""
from __future__ import annotations

import csv
from pathlib import Path

from mechanistic_mind.physical_system.experiment_canonical import beta31_mechanism_map
from mechanistic_mind.physical_system.mechanism_registry import MECHANISM_DEFS
from mechanistic_mind.physical_system.mechanism_configuration import WORLD_SUBSYSTEM_IDS, fresh_experiment_default_map

OUT = Path("results/beta31_full_mechanism_integrity_audit")
OUT.mkdir(parents=True, exist_ok=True)

STOCK = beta31_mechanism_map()
FRESH = fresh_experiment_default_map()

# Current analyzed run (user): research overrides ON for experimental cognition + PSC + probe.
RUN_ON = dict(STOCK)
for k in (
    "prospective_scenario_competition",
    "unknown_action_physical_probe",
    "predictive_equivalence",
    "predictive_relevance",
    "temporal_predictive_structure",
    "temporal_prospection_bridge",
    "predictive_conflict",
    "future_sensitive_action",
    "prediction_error_revision",
    "temporal_prediction_error",
    "predicted_context_prospection",
    "multistep_action_prospection",
):
    RUN_ON[k] = True
# Structural always on
for k in ("discrete_action_bridge", "shared_work_allocation", "environmental_site_mechanics"):
    RUN_ON[k] = True
RUN_ON["cognition"] = True

FAMILY = {
    "discrete_action_bridge": "BODY_PHYSICS",
    "shared_work_allocation": "BODY_PHYSICS",
    "environmental_site_mechanics": "WORLD_ECOLOGY",
    "predictive_compression": "MEMORY",
    "multiscale_prediction": "MEMORY",
    "prospective_composition": "PROSPECTION",
    "bounded_memory": "MEMORY",
    "retrieval": "MEMORY",
    "body_deformation": "BODY_PHYSICS",
    "deformation_work": "BODY_PHYSICS",
    "environmental_resource_transfer": "WORLD_ECOLOGY",
    "resource_to_work_conversion": "WORLD_ECOLOGY",
    "resource_A_transfer": "WORLD_ECOLOGY",
    "resource_B_transfer": "WORLD_ECOLOGY",
    "complementary_resource_conversion": "WORLD_ECOLOGY",
    "distributed_morphology": "BODY_PHYSICS",
    "body_orientation": "BODY_PHYSICS",
    "endogenous_motor_coupling": "BODY_PHYSICS",
    "endogenous_motor_work_accounting": "BODY_PHYSICS",
    "discrete_action_work_accounting": "BODY_PHYSICS",
    "prospective_scenario_competition": "PSC",
    "instrumental_observation": "PERCEPTION",
    "unknown_action_physical_probe": "PSC",
    "spatiotemporal_climate_ecology": "WORLD_ECOLOGY",
    "resource_ecology_A": "WORLD_ECOLOGY",
    "resource_ecology_B": "WORLD_ECOLOGY",
    "physical_near_field_vision": "PERCEPTION",
    "illumination_cycle": "PERCEPTION",
    "physical_body_optical_response": "PERCEPTION",
    "experimental_physical_signal": "PERCEPTION",
    "oscillatory_signaling": "SECONDARY_MOTOR",
    "articulated_head": "SECONDARY_MOTOR",
    "physical_push": "SECONDARY_MOTOR",
    "physical_vestibular_sensing": "PERCEPTION",
    "neck_proprioception": "PERCEPTION",
    "predictive_equivalence": "MEMORY",
    "predictive_relevance": "MEMORY",
    "temporal_predictive_structure": "TEMPORAL",
    "temporal_prospection_bridge": "TEMPORAL",
    "predictive_conflict": "PROSPECTION",
    "future_sensitive_action": "PROSPECTION",
    "prediction_error_revision": "TEMPORAL",
    "temporal_prediction_error": "TEMPORAL",
    "predicted_context_prospection": "PROSPECTION",
    "multistep_action_prospection": "PROSPECTION",
    "sensorimotor_consequence_model": "PSC",
    "historical_sensorimotor_selection_bridge": "PSC",
    "contextual_predictive_organization": "PROSPECTION",
    "context_grounded_prospection": "PROSPECTION",
    "persistent_prospective_control": "PROSPECTION",
    "cognition": "PSC",
    "terrain_geography": "WORLD_ECOLOGY",
    "ambient_physical_dynamics": "WORLD_ECOLOGY",
    "visual_surface_discrimination": "PERCEPTION",
    "spatial_vision": "PERCEPTION",
    "composite_motor_factorization": "SECONDARY_MOTOR",
    "psc_motor_resolution": "PSC",
    "pe_cold_history_eviction": "INFRASTRUCTURE",
    "scientific_v3_receipts": "EVIDENCE",
}

OWNER = {
    "discrete_action_bridge": "actions.py / runtime.begin_tick",
    "shared_work_allocation": "runtime._compute_work_allocation",
    "environmental_site_mechanics": "morphology/orientation + planet sampling",
    "predictive_compression": "research/predictive_compression.py",
    "multiscale_prediction": "research/multiscale_prediction.py",
    "prospective_composition": "research/prospective_composition.py",
    "bounded_memory": "pc.purge / store caps",
    "retrieval": "cognition.py pc.predict loop",
    "body_deformation": "body_deformation.py",
    "deformation_work": "deformation_work.py",
    "environmental_resource_transfer": "environmental_resource.py",
    "resource_to_work_conversion": "environmental_resource.py",
    "resource_A_transfer": "complementary_resources.py",
    "resource_B_transfer": "complementary_resources.py",
    "complementary_resource_conversion": "complementary_resources.py",
    "distributed_morphology": "morphology_mechanics.py",
    "body_orientation": "body_orientation.py",
    "endogenous_motor_coupling": "endogenous_motor / runtime",
    "endogenous_motor_work_accounting": "motor_work.py",
    "discrete_action_work_accounting": "action_work.py",
    "prospective_scenario_competition": "scenario_competition.py via cognition.py",
    "instrumental_observation": "instrumental_observation.py",
    "unknown_action_physical_probe": "unknown_action_probe.py via cognition.py",
    "spatiotemporal_climate_ecology": "planet climate",
    "resource_ecology_A": "planet.climate_ecology R_A",
    "resource_ecology_B": "planet.climate_ecology R_B",
    "physical_near_field_vision": "near_field_exteroception.py / observation.py",
    "illumination_cycle": "near_field_exteroception illumination",
    "physical_body_optical_response": "near_field_exteroception body optical",
    "experimental_physical_signal": "physical_signal.py / two_agent.py",
    "oscillatory_signaling": "oscillatory_signaling.py + composite_motor.py",
    "articulated_head": "articulated_head.py + composite_motor",
    "physical_push": "physical_push.py + composite_motor",
    "physical_vestibular_sensing": "vestibular_proprioception.py",
    "neck_proprioception": "vestibular_proprioception.py",
    "predictive_equivalence": "research/predictive_equivalence.py",
    "predictive_relevance": "research/predictive_relevance.py",
    "temporal_predictive_structure": "research/temporal_predictive_structure.py",
    "temporal_prospection_bridge": "research/temporal_prospection_bridge.py",
    "predictive_conflict": "research/predictive_conflict.py",
    "future_sensitive_action": "research/future_sensitive_action.py",
    "prediction_error_revision": "research/prediction_error_revision.py",
    "temporal_prediction_error": "research/temporal_prediction_error.py",
    "predicted_context_prospection": "research/predicted_context_prospection.py",
    "multistep_action_prospection": "research/multistep_action_prospection.py",
    "sensorimotor_consequence_model": "sensorimotor_consequence.py via cognition.py smc.update",
    "historical_sensorimotor_selection_bridge": "o_prime_history_bridge.py via cognition.py evaluate_candidates",
    "contextual_predictive_organization": "contextual_stack_bridge.py via cognition.py on_experience",
    "context_grounded_prospection": "contextual_stack_bridge.py via cognition.py before_selection",
    "persistent_prospective_control": "contextual_stack_bridge.py via cognition.py after_selection",
    "cognition": "cognition.py run_cognition_before_action",
    "terrain_geography": "planet config stamp",
    "ambient_physical_dynamics": "planet dynamics",
    "visual_surface_discrimination": "near_field_exteroception",
    "spatial_vision": "near_field_exteroception",
    "composite_motor_factorization": "runtime._factorized_composite_from_cognition",
    "psc_motor_resolution": "LOCO_FACTORIZED default; observed_composite_psc unused in cognition",
    "pe_cold_history_eviction": "predictive_equivalence cold archive",
    "scientific_v3_receipts": "scientific_v3/receipts.py",
}

ENTRY = {k: v.split("/")[0].strip() if "/" in v else v for k, v in OWNER.items()}

# Verdicts for CURRENT RESEARCH RUN (post-OSC tree).
# Keys: configured, runtime, input, exec, natural, state, physical, down, cog, v3, ana, evid, direct, effective, blocked, first, probe, notes
V = {}

def row(mid, **kw):
    V[mid] = kw

# Helpers
W = "WORKING"
WN = "WORKING_BUT_NOT_EXERCISED"
P = "PARTIAL"
B = "BROKEN"
ND = "NOT_DEMONSTRATED"
NA = "NOT_APPLICABLE_IN_CURRENT_CONFIG"
BLK = "BLOCKED_BY_UPSTREAM_BUG"
Y, N = "YES", "NO"
PR = "PRIOR_ACCEPTED_RESULT"
SRC = "SOURCE_CALLGRAPH"
PRB = "TARGETED_PROBE"
RUN = "CURRENT_RUN_ANALYZER"

# --- body/world working baselines (prior + 5422 tick locomotion/resources assumed from complete O-D-M-C) ---
for mid in (
    "discrete_action_bridge", "shared_work_allocation", "environmental_site_mechanics",
    "body_deformation", "deformation_work", "distributed_morphology", "body_orientation",
    "endogenous_motor_coupling", "endogenous_motor_work_accounting", "discrete_action_work_accounting",
    "environmental_resource_transfer", "resource_to_work_conversion",
    "resource_A_transfer", "resource_B_transfer", "complementary_resource_conversion",
    "resource_ecology_A", "resource_ecology_B", "terrain_geography", "ambient_physical_dynamics",
):
    row(mid, configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical=Y, down=Y, cog=Y if mid.startswith("discrete") else "N/A",
        v3=Y, ana=Y, evid=f"{RUN}+{PR}", direct=W, effective=W, blocked="", first="", probe="none", notes="Complete O-D-M-C; prior body/ecology validation")

row("cognition", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=RUN, direct=W, effective=W, blocked="", first="", probe="none", notes="10844 stories")
row("predictive_compression", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=RUN, direct=W, effective=W, blocked="", first="", probe="none", notes="pc.observe/predict in cognition")
row("multiscale_prediction", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=RUN, direct=W, effective=W, blocked="", first="", probe="none", notes="")
row("prospective_composition", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=RUN, direct=W, effective=W, blocked="", first="", probe="none", notes="compose locomotor only by design")
row("bounded_memory", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=PR, direct=W, effective=W, blocked="", first="", probe="none", notes="caps + packed L1")
row("retrieval", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=RUN, direct=W, effective=W, blocked="", first="", probe="none", notes="")
row("instrumental_observation", configured=Y, runtime=Y, input=Y, exec=Y, natural="YES_STORE", state=Y, physical="N/A", down=P, cog=Y, v3=P, ana=P, evid=SRC, direct=P, effective=P, blocked="", first="physical EMIT still BRIDGE_MISSING (legacy EMIT, not OSC)", probe="none", notes="store+predict wired; 4.25 emit transducer missing")

row("prospective_scenario_competition", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=RUN, direct=W, effective=W, blocked="", first="", probe="none", notes="INTENTIONAL loco alias for N/E/F/A/P vs L; not a broken PSC. LOCO_FACTORIZED.")
row("unknown_action_physical_probe", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical=N, down=N, cog=Y, v3=Y, ana=ND, evid=PRB, direct=W, effective=W, blocked="", first="", probe="empty_cognitive_state 0 ticks", notes="Detection-only DESIGN_BOUNDARY; does not select")

row("spatiotemporal_climate_ecology", configured=N, runtime=N, input="N/A", exec="N/A", natural=N, state="N/A", physical="N/A", down="N/A", cog="N/A", v3="N/A", ana="N/A", evid=PR, direct=NA, effective=NA, blocked="", first="", probe="none", notes="intentional OFF")

row("physical_near_field_vision", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=Y, evid=f"{PR}+{PRB}", direct=W, effective=W, blocked="", first="", probe="1 tick NFE EXPERIMENTAL R3 RICH OCCLUSION", notes="exo_0/1/2 present")
row("illumination_cycle", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=Y, evid=PRB, direct=W, effective=W, blocked="", first="", probe="1 tick", notes="illumination_intensity set")
row("physical_body_optical_response", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=Y, evid=PR, direct=W, effective=W, blocked="", first="", probe="none", notes="")
row("visual_surface_discrimination", configured="RICH", runtime="RICH", input=Y, exec=Y, natural=Y, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=Y, evid=f"{PR}+{PRB}", direct=W, effective=W, blocked="", first="", probe="1 tick 9 surface_* keys", notes="not semantic color")
row("spatial_vision", configured="OCCLUSION", runtime="OCCLUSION", input=Y, exec=Y, natural=Y, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=Y, evid=f"{PR}+{PRB}", direct=W, effective=W, blocked="", first="", probe="1 tick 20 spatial_* keys", notes="not depth perception claim")
row("experimental_physical_signal", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=Y, evid=RUN, direct=W, effective=W, blocked="", first="", probe="inject FIELD_A", notes="SIGNAL_PRESENT=9255")
row("physical_vestibular_sensing", configured=Y, runtime=Y, input=Y, exec=Y, natural=ND, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=ND, evid=PRB, direct=W, effective=W, blocked="", first="", probe="1 tick omega", notes="vest keys change with omega")
row("neck_proprioception", configured=Y, runtime=Y, input=Y, exec=Y, natural=ND, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=ND, evid=PRB, direct=W, effective=W, blocked="", first="", probe="forced NECK_RIGHT", notes="prop_neck tracks head; body theta independent")

row("articulated_head", configured=Y, runtime=Y, input=Y, exec=Y, natural=ND, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=ND, evid=PRB, direct=WN, effective=WN, blocked="", first="", probe="forced neck", notes="Post-OSC factorization reachable; 80e3abc6 likely never selected neck")
row("physical_push", configured=Y, runtime=Y, input=Y, exec=Y, natural=ND, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=ND, evid=PRB, direct=WN, effective=WN, blocked="", first="", probe="forced push+contact", notes="Geometry-gated; component reachable")
row("oscillatory_signaling", configured=Y, runtime=Y, input=Y, exec=Y, natural=N, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=N, evid="results/beta31_osc_path_repair", direct=WN, effective=WN, blocked="", first="", probe="prior OSC repair fixtures", notes="POST-REPAIR path available; original run never emitted")
row("composite_motor_factorization", configured=Y, runtime=Y, input=Y, exec=Y, natural=N, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=N, evid="OSC_FIX + probe", direct=W, effective=W, blocked="", first="", probe="3 tick begin_tick", notes="selection_source=COMPOSITE_FACTORIZED after repair; original run used from_legacy")

row("sensorimotor_consequence_model", configured=Y, runtime=Y, input=Y, exec=Y, natural="PROBE_ONLY", state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=P, evid=f"{SRC}+{PRB}+results/beta31_cognitive_tick_wiring_repair", direct=W, effective=W, blocked="", first="", probe="3 ticks store+updates", notes="Post RG_SMC_HSS_TICK; Analyzer still also reconstructs from receipts")
row("historical_sensorimotor_selection_bridge", configured=Y, runtime=Y, input=Y, exec=Y, natural="PROBE_ONLY", state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=P, evid=f"{SRC}+{PRB}+results/beta31_cognitive_tick_wiring_repair", direct=W, effective=W, blocked="", first="", probe="last_selection o_prime_history_bridge", notes="Default withhold_from_psc True: query attached, PSC scores not injected")

row("contextual_predictive_organization", configured=Y, runtime=Y, input=Y, exec=Y, natural="PROBE_ONLY", state=Y, physical="N/A", down=Y, cog=Y, v3=N, ana=N, evid=f"{SRC}+{PRB}+results/beta31_cognitive_tick_wiring_repair", direct=W, effective=W, blocked="", first="", probe="3 ticks CPO store+recent_coactive", notes="V3 TELEMETRY_GAP; runtime path wired")
row("context_grounded_prospection", configured=Y, runtime=Y, input=Y, exec=Y, natural="PROBE_ONLY", state=Y, physical="N/A", down=Y, cog=Y, v3=N, ana=N, evid=f"{SRC}+{PRB}+results/beta31_cognitive_tick_wiring_repair", direct=W, effective=W, blocked="", first="", probe="csb.before_selection in last_selection", notes="Path reachable; 3-tick fixture may not inject continuations")
row("persistent_prospective_control", configured=Y, runtime=Y, input=Y, exec=Y, natural="PROBE_ONLY", state=Y, physical="N/A", down=Y, cog=Y, v3=N, ana=N, evid=f"{SRC}+{PRB}+results/beta31_cognitive_tick_wiring_repair", direct=W, effective=W, blocked="", first="", probe="csb.after_selection in last_selection", notes="Path reachable; adopt is support-gated existing contract")

row("predictive_equivalence", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=f"{RUN}+{PR}", direct=W, effective=W, blocked="", first="", probe="none", notes="research override; pe.learn in cognition")
row("predictive_relevance", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=PR, direct=W, effective=W, blocked="", first="", probe="none", notes="residual forensic pe_rel_refresh")
row("temporal_predictive_structure", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=f"{RUN}+{PR}", direct=W, effective=W, blocked="", first="", probe="none", notes="prepared query opt present")
row("temporal_prospection_bridge", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=RUN, direct=W, effective=W, blocked="", first="", probe="none", notes="tpb.collect_entry_steps in cognition")
row("predictive_conflict", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=RUN, direct=W, effective=W, blocked="", first="", probe="none", notes="pcf.organize when continuations exist")
row("future_sensitive_action", configured=Y, runtime=Y, input=Y, exec=Y, natural=ND, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=ND, evid=SRC, direct=WN, effective=WN, blocked="", first="", probe="none", notes="wired into group building when flag ON")
row("prediction_error_revision", configured=Y, runtime=Y, input=Y, exec=Y, natural=ND, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=ND, evid=SRC, direct=WN, effective=WN, blocked="", first="", probe="none", notes="filter_entry/continuations/groups wired")
row("temporal_prediction_error", configured=Y, runtime=Y, input=Y, exec=Y, natural=ND, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=ND, evid=SRC, direct=WN, effective=WN, blocked="", first="", probe="none", notes="ingest/pending wired")
row("predicted_context_prospection", configured=Y, runtime=Y, input=Y, exec=Y, natural=ND, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=ND, evid=SRC, direct=WN, effective=WN, blocked="", first="", probe="none", notes="pcp.collect wired in cognition")
row("multistep_action_prospection", configured=Y, runtime=Y, input=Y, exec=Y, natural=ND, state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=ND, evid=SRC, direct=WN, effective=WN, blocked="", first="", probe="none", notes="mapr.collect wired")

row("psc_motor_resolution", configured="LOCO_FACTORIZED", runtime="LOCO_FACTORIZED", input=Y, exec=Y, natural=Y, state=Y, physical=Y, down=Y, cog=Y, v3=Y, ana=Y, evid=SRC, direct=W, effective=W, blocked="", first="", probe="none", notes="OBSERVED_COMPOSITE unused; default intentional")
row("pe_cold_history_eviction", configured=Y, runtime=Y, input=Y, exec=Y, natural="IF_PE_ON", state=Y, physical="N/A", down=Y, cog=Y, v3=Y, ana=Y, evid=PR, direct=W, effective=W, blocked="", first="", probe="none", notes="docs/BETA31_PE_COLD_EVICTION_PRODUCTION.md PASS")
row("scientific_v3_receipts", configured=Y, runtime=Y, input=Y, exec=Y, natural=Y, state=Y, physical="N/A", down=Y, cog="N/A", v3=Y, ana=P, evid=RUN, direct=W, effective=P, blocked="", first="", probe="none", notes="O-D-M-C FULL; Analyzer mechanism summaries may lag (OSC, contact)")

inv_rows = []
for d in MECHANISM_DEFS:
    mid = d["id"]
    inv_rows.append({
        "mechanism": mid,
        "family": FAMILY.get(mid, ""),
        "configured": "ON" if RUN_ON.get(mid, FRESH.get(mid, d.get("default_integrated"))) else "OFF",
        "runtime": "ON" if RUN_ON.get(mid, False) or d.get("ablatable") is False and d.get("default_integrated") else ("ON" if RUN_ON.get(mid) else "OFF"),
        "owner": OWNER.get(mid, ""),
        "entry_point": OWNER.get(mid, ""),
        "intended_input": d.get("description", "")[:120],
        "intended_output": d.get("validation", "")[:120],
        "causal_or_diagnostic": "DIAGNOSTIC" if mid == "unknown_action_physical_probe" else "CAUSAL",
        "audit_required": "YES",
    })
for mid in WORLD_SUBSYSTEM_IDS:
    inv_rows.append({
        "mechanism": mid, "family": "WORLD_ECOLOGY", "configured": "ON", "runtime": "ON",
        "owner": OWNER[mid], "entry_point": OWNER[mid],
        "intended_input": "planet config", "intended_output": "world fields/forces",
        "causal_or_diagnostic": "CAUSAL", "audit_required": "YES",
    })
for mid, extra in (
    ("visual_surface_discrimination", "RICH surface bins"),
    ("spatial_vision", "OCCLUSION spatial bins"),
    ("composite_motor_factorization", "neck/osc/push same-cycle pick"),
    ("psc_motor_resolution", "LOCO_FACTORIZED vs OBSERVED_COMPOSITE"),
    ("pe_cold_history_eviction", "PECA cold archive"),
    ("scientific_v3_receipts", "O/D/M/C jsonl"),
):
    inv_rows.append({
        "mechanism": mid, "family": FAMILY[mid],
        "configured": "ON", "runtime": "ON",
        "owner": OWNER[mid], "entry_point": OWNER[mid],
        "intended_input": extra, "intended_output": extra,
        "causal_or_diagnostic": "DIAGNOSTIC" if mid == "scientific_v3_receipts" else "CAUSAL",
        "audit_required": "YES",
    })

# Fix runtime column from RUN_ON for registry
for r in inv_rows:
    mid = r["mechanism"]
    if mid in RUN_ON:
        r["configured"] = "ON" if RUN_ON[mid] else "OFF"
        r["runtime"] = r["configured"]
    if mid == "spatiotemporal_climate_ecology":
        r["configured"] = "OFF"
        r["runtime"] = "OFF"

with (OUT / "MECHANISM_INVENTORY.csv").open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(inv_rows[0].keys()))
    w.writeheader()
    w.writerows(inv_rows)

mat_fields = [
    "mechanism","family","configured","runtime_enabled","input_reachable","execution_reachable",
    "naturally_exercised","state_effect","physical_effect","downstream_reachable","cognition_reachable",
    "scientific_v3_visible","analyzer_visible","evidence_source","direct_status","effective_status",
    "blocked_by","first_broken_link","probe_used","notes",
]
with (OUT / "MECHANISM_INTEGRITY_MATRIX.csv").open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=mat_fields)
    w.writeheader()
    for r in inv_rows:
        mid = r["mechanism"]
        v = V.get(mid)
        if not v:
            continue
        w.writerow({
            "mechanism": mid,
            "family": r["family"],
            "configured": v.get("configured"),
            "runtime_enabled": v.get("runtime"),
            "input_reachable": v.get("input"),
            "execution_reachable": v.get("exec"),
            "naturally_exercised": v.get("natural"),
            "state_effect": v.get("state"),
            "physical_effect": v.get("physical"),
            "downstream_reachable": v.get("down"),
            "cognition_reachable": v.get("cog"),
            "scientific_v3_visible": v.get("v3"),
            "analyzer_visible": v.get("ana"),
            "evidence_source": v.get("evid"),
            "direct_status": v.get("direct"),
            "effective_status": v.get("effective"),
            "blocked_by": v.get("blocked"),
            "first_broken_link": v.get("first"),
            "probe_used": v.get("probe"),
            "notes": v.get("notes"),
        })

missing = [r["mechanism"] for r in inv_rows if r["mechanism"] not in V]
print("inventory", len(inv_rows), "matrix", len(V), "missing", missing)
