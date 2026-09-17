"""Observer-only experiment visualization adapters (Updates 4.23–4.27).

One Psychology Observer app; adapters format RESEARCH telemetry for display.
Never feed these strings into cognition / psyche decision paths.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[3]

LAYERS = (
    "WORLD_TRUTH",
    "BODY_TRUTH",
    "ACCESSIBLE_SIGNALS",
    "PSYCHE_MODEL",
    "PROSPECTIVE",
    "ACTION",
    "CONSEQUENCE",
)


def _load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _claim_line(claim_path: Path) -> list[str]:
    cm = _load(claim_path) or {}
    lines = ["CLAIMS:"]
    if not cm:
        lines.append("  (no claim_matrix yet)")
        return lines
    for k, v in cm.items():
        if isinstance(v, dict):
            st = "ASSERTED" if v.get("asserted") else "NOT ASSERTED"
            lines.append(f"  {k}: {st} seeds={v.get('seeds')}")
        else:
            lines.append(f"  {k}: {v}")
    return lines


def format_layers(title: str, layer_map: dict[str, str], extra: list[str] | None = None) -> list[str]:
    lines = [title, ""]
    for layer in LAYERS:
        lines.append(f"[{layer}]")
        lines.append(layer_map.get(layer, "(n/a)"))
        lines.append("")
    if extra:
        lines.extend(extra)
    return lines


def adapter_423() -> list[str]:
    base = ROOT / "results" / "update423_prospective_composition"
    snap = _load(base / "OBSERVER_PROSPECTIVE_SNAPSHOT.json") or {}
    agent = snap.get("CURRENT_AGENT_AVAILABLE") or {}
    res = snap.get("RESEARCHER_ONLY") or {}
    nov = res.get("novel") or {}
    comp = nov.get("compose") or {}
    layers = {
        "WORLD_TRUTH": "Fragment transitions only; full distal path never end-to-end exposed in training.",
        "BODY_TRUTH": "Terminal body states on composed depth (researcher).",
        "ACCESSIBLE_SIGNALS": f"transitions={agent.get('transitions')}",
        "PSYCHE_MODEL": "prospective_composition store (no GOAL/PLAN).",
        "PROSPECTIVE": (
            f"novel_success={nov.get('novel_composition_success')} "
            f"depth={comp.get('max_depth_reached')} expansions={comp.get('expansion_count')}"
        ),
        "ACTION": "Distal→action NOT asserted in 4.23 (deferred; see 4.26).",
        "CONSEQUENCE": "Broken/shuffled fail; composition ablation removes distal.",
    }
    return format_layers("4.23 PROSPECTIVE TRAJECTORY COMPOSITION", layers, _claim_line(base / "claim_matrix.json"))


def adapter_424() -> list[str]:
    base = ROOT / "results" / "update424_endogenous_temporal"
    snap = _load(base / "OBSERVER_TEMPORAL_SNAPSHOT.json") or {}
    agent = snap.get("CURRENT_AGENT_AVAILABLE") or {}
    layers = {
        "WORLD_TRUTH": "Wall-clock delay vs body-rate divergence (researcher metrics).",
        "BODY_TRUTH": "Endogenous body trajectory as temporal reference candidate.",
        "ACCESSIBLE_SIGNALS": (
            f"state_pred={agent.get('state_pred_count')} traj_pred={agent.get('traj_pred_count')} (no CLOCK)"
        ),
        "PSYCHE_MODEL": "No CLOCK leak into cognition.",
        "PROSPECTIVE": "Traj-over-state ≈ NULL; same-state/different-history predictive divergence = NULL.",
        "ACTION": "n/a",
        "CONSEQUENCE": "Strong temporal claim NOT ASSERTED.",
    }
    return format_layers("4.24 ENDOGENOUS TEMPORAL REFERENCE", layers, _claim_line(base / "claim_matrix.json"))


def adapter_425() -> list[str]:
    base = ROOT / "results" / "update425_instrumental_observation"
    snap = _load(base / "OBSERVER_INSTRUMENTAL_SNAPSHOT.json") or {}
    agent = snap.get("CURRENT_AGENT_AVAILABLE") or {}
    res = snap.get("RESEARCHER_ONLY") or {}
    c1 = res.get("C1") or {}
    obs = res.get("obs_useful") or {}
    layers = {
        "WORLD_TRUTH": "Latent W vs accessible transduction paths (researcher).",
        "BODY_TRUTH": "n/a",
        "ACCESSIBLE_SIGNALS": f"pred_count={agent.get('pred_count')} (no W identity / no TOOL label)",
        "PSYCHE_MODEL": "Acquired observability via mediation.",
        "PROSPECTIVE": f"direct={obs.get('direct_distinguishability')} mediated={obs.get('mediated_distinguishability')}",
        "ACTION": "C3 self-initiated observation NOT ASSERTED.",
        "CONSEQUENCE": f"C1={c1.get('assert_candidate')} class={c1.get('classification')}; C2 learned predictive use ASSERTED.",
    }
    return format_layers("4.25 INSTRUMENTAL OBSERVATION", layers, _claim_line(base / "claim_matrix.json"))


def adapter_426() -> list[str]:
    base = ROOT / "results" / "update426_prospective_consequence_influence"
    snap = _load(base / "OBSERVER_PCI_SNAPSHOT.json") or {}
    agent = snap.get("CURRENT_AGENT_AVAILABLE") or {}
    res = snap.get("RESEARCHER_ONLY") or {}
    d = res.get("deltas") or {}
    pr = res.get("prospective") or {}
    layers = {
        "WORLD_TRUTH": "A/B distal chains; full-sequence exposure=0.",
        "BODY_TRUTH": "A→B_MINUS vs B→B_PLUS terminal bodies.",
        "ACCESSIBLE_SIGNALS": f"softmax probs={agent.get('probs')} (no GOAL/argmax)",
        "PSYCHE_MODEL": "4.23 compose + ordinary_state_value; DISTAL_BLEND=0.55 T=1.25",
        "PROSPECTIVE": f"A_comp={pr.get('A_composition_success')} B_comp={pr.get('B_composition_success')}",
        "ACTION": f"shift_toward_B={d.get('shift_toward_B')} (ablation/swap in artifacts)",
        "CONSEQUENCE": "C1–C3 ASSERTED; C4 online revision NOT ASSERTED (EMA swap ≠ sign-reverse).",
    }
    return format_layers("4.26 PROSPECTIVE CONSEQUENCE INFLUENCE", layers, _claim_line(base / "claim_matrix.json"))


def adapter_427() -> list[str]:
    base = ROOT / "results" / "update427_predictive_generalization"
    snap = _load(base / "OBSERVER_GENERALIZATION_SNAPSHOT.json") or {}
    fm = snap.get("feature_matrix") or _load(base / "feature_matrix.json") or {}
    ab = snap.get("ablation_summary") or {}
    layers = {
        "WORLD_TRUTH": (
            f"Instances {fm.get('training_family_observer_labels')} → F−; "
            f"novel {fm.get('novel')}; counterexample {fm.get('counterexample')}"
        ),
        "BODY_TRUTH": f"F−={fm.get('consequence_F_MINUS')} F+={fm.get('consequence_F_PLUS')}",
        "ACCESSIBLE_SIGNALS": "Physical feature bins a,b,+third only (no CATEGORY/CLASS/THREAT).",
        "PSYCHE_MODEL": "exact / single / pair conjunction stores; Observer labels I1/I_NEW only.",
        "PROSPECTIVE": f"per_seed_novel={fm.get('per_seed_novel')}",
        "ACTION": "C3 via unchanged 4.26 ordinary_state_value + action_logits (see claim_matrix).",
        "CONSEQUENCE": (
            f"ablate_shared_blocks={ab.get('shared_blocks')} "
            f"exact_only_blocks={ab.get('exact_only_blocks')} "
            f"shuffle_blocks={ab.get('shuffle_blocks')}"
        ),
    }
    top = snap.get("shared_top_pairs_seed0") or []
    extra = _claim_line(base / "claim_matrix.json") + ["", "TOP PAIR STRUCTURES (seed0):"]
    for t in top[:6]:
        extra.append(f"  {t.get('key')} support={t.get('support')} mean={t.get('mean')}")
    return format_layers("4.27 PREDICTIVE GENERALIZATION", layers, extra)



def adapter_428() -> list[str]:
    base = ROOT / "results" / "update428_predictive_scenario_competition"
    snap = _load(base / "OBSERVER_COMPETITION_SNAPSHOT.json") or {}
    cm = snap.get("claim_matrix") or _load(base / "claim_matrix.json") or {}
    hyst = snap.get("hysteresis") or {}
    sph = snap.get("same_present_different_history") or {}
    hyst_any = any((v or {}).get("observed") for v in hyst.values()) if isinstance(hyst, dict) else False
    layers = {
        "WORLD_TRUTH": "S0 with competing A / B / WAIT continuations; history levels H0–H100",
        "BODY_TRUTH": "Distal body vectors; Observer levels much_less…substantially_more",
        "ACCESSIBLE_SIGNALS": "Matched S0 signals; no HABIT/CONFIDENCE/ENTRENCHMENT in cognition",
        "PSYCHE_MODEL": "4.23 transitions + 4.26 softmax; support = ordinary learn counts",
        "PROSPECTIVE": "All candidate continuations retained (losing branches shown in snapshot)",
        "ACTION": f"same_present_diff_history={sph}",
        "CONSEQUENCE": (
            f"HYSTERESIS CANDIDATE: {'OBSERVED' if hyst_any else 'NOT OBSERVED'}; "
            f"first_unsupported={snap.get('first_unsupported_arrows')}"
        ),
    }
    extra = _claim_line(base / "claim_matrix.json") + [
        "",
        "COMPETING FUTURES: CURRENT S0 → A | B | WAIT → distal → logits → distribution",
        "Do not display only the winning branch — see OBSERVER_COMPETITION_SNAPSHOT.json",
        "",
        "SCIENTIFIC BOUNDARY: persistence/transition/path-dependence only if supported;",
        "NOT habit / belief / stubbornness / commitment / cognitive dissonance.",
    ]
    return format_layers("4.28 PREDICTIVE SCENARIO COMPETITION", layers, extra)




def adapter_429() -> list[str]:
    base = ROOT / "results" / "update429_predictive_reliability"
    snap = _load(base / "OBSERVER_RELIABILITY_SNAPSHOT.json") or {}
    c3 = snap.get("DISTRIBUTIONAL_ACTION_INFLUENCE") or "NOT OBSERVED"
    layers = {
        "WORLD_TRUTH": snap.get("layers", {}).get("WORLD_TRUTH", "A consistent vs B conflicting distal mixtures"),
        "BODY_TRUTH": "Distal body outcomes F_hi/F_lo/F_mid (researcher)",
        "ACCESSIBLE_SIGNALS": snap.get("layers", {}).get("ACCESSIBLE_EVIDENCE", "learned transitions; full_seq=0"),
        "PSYCHE_MODEL": "mean+var_sum retained; action_logits uses mean->ordinary_value only",
        "PROSPECTIVE": f"per_seed={snap.get('per_seed')}",
        "ACTION": f"DISTRIBUTIONAL ACTION INFLUENCE: {c3}",
        "CONSEQUENCE": f"bottleneck={snap.get('information_bottleneck')}; first={snap.get('first_unsupported_arrows')}",
    }
    extra = _claim_line(base / "claim_matrix.json") + [
        "",
        "same/similar mean  !=  same predictive distribution (var_sum / reliability_fn)",
        "NOT claimed: uncertainty / confidence / risk / doubt / metacognition",
    ]
    return format_layers("4.29 PREDICTIVE RELIABILITY", layers, extra)




def adapter_430() -> list[str]:
    base = ROOT / "results" / "update430_unavoidable_state_transition"
    snap = _load(base / "OBSERVER_TRANSITION_SNAPSHOT.json") or {}
    c4 = snap.get("REVISED_PREDICTION_TO_REVISED_ACTION") or "NOT OBSERVED"
    c5 = snap.get("COMPLETE_LOOP") or "NOT OBSERVED"
    layers = {
        "WORLD_TRUTH": "Autonomous field evolves under WAIT (freeze control available)",
        "BODY_TRUTH": "Body metabolizes every tick including WAIT",
        "ACCESSIBLE_SIGNALS": "field_signal + body signals; no REVEAL/TIME tokens",
        "PSYCHE_MODEL": "4.23 transitions; online learn_transition on new field evidence",
        "PROSPECTIVE": f"per_seed={snap.get('per_seed')}",
        "ACTION": f"REVISED PREDICTION -> REVISED ACTION: {c4}; COMPLETE LOOP: {c5}",
        "CONSEQUENCE": f"WAIT=NO ACTIVE INTERVENTION (not PAUSE); first={snap.get('first_unsupported_arrows')}",
    }
    extra = _claim_line(base / "claim_matrix.json") + [
        "",
        "WORLD/BODY EVOLUTION → ACCESSIBLE EVIDENCE → PREDICTION BEFORE/AFTER",
        "→ ORDINARY STATE VALUE → ACTION DISTRIBUTION BEFORE/AFTER",
        "NOT claimed: deliberation / uncertainty / waiting for evidence / information seeking",
    ]
    return format_layers("4.30 UNAVOIDABLE STATE TRANSITION", layers, extra)




def adapter_431() -> list[str]:
    base = ROOT / "results" / "update431_evidence_producing_action"
    snap = _load(base / "OBSERVER_EVIDENCE_ACTION_SNAPSHOT.json") or {}
    auto = snap.get("AUTONOMOUS_MEDIATOR_ACTION") or "NOT OBSERVED"
    evid = snap.get("EVIDENCE_DEPENDENT_SELECTION") or "NOT ASSERTED"
    layers = {
        "WORLD_TRUTH": snap.get("layers", {}).get("WORLD_TRUTH", "latent W (GT only)"),
        "BODY_TRUTH": "mediator m0/m1; body s0/s1",
        "ACCESSIBLE_SIGNALS": "s0/s1 before/after CONTACT_M (no REVEAL)",
        "PSYCHE_MODEL": "4.25 io.predict + 4.26 ordinary_state_value; no info-gain",
        "PROSPECTIVE": f"per_seed={snap.get('per_seed')}",
        "ACTION": f"AUTONOMOUS MEDIATOR ACTION: {auto}; EVIDENCE-DEPENDENT SELECTION: {evid}",
        "CONSEQUENCE": f"bottleneck={snap.get('bottleneck')}; action={snap.get('ACTION_CONTACT_physical_name')}",
    }
    extra = _claim_line(base / "claim_matrix.json") + [
        "",
        "Physical action name: CONTACT_M (not Observe/Inspect/Measure)",
        "NOT claimed: curiosity / information seeking / epistemic motivation",
    ]
    return format_layers("4.31 EVIDENCE-PRODUCING PHYSICAL ACTION", layers, extra)




def adapter_432() -> list[str]:
    base = ROOT / "results" / "update432_learning_mediated_futures"
    snap = _load(base / "OBSERVER_LEARNING_FUTURES_SNAPSHOT.json") or {}
    first = snap.get("FIRST_UNSUPPORTED_ARROW") or []
    layers = {
        "WORLD_TRUTH": snap.get("layers", {}).get("PRESENT_PHYSICAL_STATE", "S0"),
        "BODY_TRUTH": snap.get("layers", {}).get("PHYSICAL_TRANSDUCTION", "4.25"),
        "ACCESSIBLE_SIGNALS": snap.get("layers", {}).get("ACCESSIBLE_SIGNAL", "s0/s1"),
        "PSYCHE_MODEL": "predictive org before/after; no SELF_MODEL sensor",
        "PROSPECTIVE": (
            f"PRESENT CONTACT_M VALUE: FULL==REVISION-OFF; "
            f"FIRST UNSUPPORTED: {first}; bottleneck={snap.get('bottleneck')}"
        ),
        "ACTION": f"per_seed={snap.get('per_seed')}",
        "CONSEQUENCE": snap.get("layers", {}).get("PHYSICAL_CONSEQUENCE", ""),
    }
    extra = _claim_line(base / "claim_matrix.json") + [
        "",
        "FUTURE PREDICTIVE-STATE TRANSITION -X-> PRESENT ACTION VALUE",
        "NOT claimed: curiosity / information seeking / metacognition / planning to learn",
    ]
    return format_layers("4.32 LEARNING-MEDIATED FUTURES", layers, extra)




def adapter_433() -> list[str]:
    base = ROOT / "results" / "update433_conditional_prospection"
    snap = _load(base / "OBSERVER_CONDITIONAL_PROSPECTION_SNAPSHOT.json") or {}
    first = snap.get("FIRST_UNSUPPORTED_ARROW") or []
    diag = (snap.get("LINEAR_VS_CONDITIONAL") or [{}])[0]
    layers = {
        "WORLD_TRUTH": snap.get("layers", {}).get("PRESENT_PHYSICAL_STATE", "S0"),
        "BODY_TRUTH": snap.get("layers", {}).get("FUTURE_PHYSICAL", "Ox/Oy-like fields"),
        "ACCESSIBLE_SIGNALS": "generic field_1/field_2/resistance (no branch labels)",
        "PSYCHE_MODEL": "pc.learn_transition mean store; no PLAN/BRANCH object",
        "PROSPECTIVE": (
            f"fixed_seq={snap.get('fixed_sequence_prospection')}; "
            f"contingent={snap.get('state_contingent_future_action')}; "
            f"diag={diag.get('class')}; FIRST UNSUPPORTED: {first}"
        ),
        "ACTION": f"per_seed={snap.get('per_seed')}",
        "CONSEQUENCE": f"outcome={snap.get('OUTCOME')}; bottleneck={snap.get('bottleneck')}",
    }
    extra = _claim_line(base / "claim_matrix.json") + [
        "",
        "REACTIVE CONDITIONAL ACTION / MULTIPLE CONTINUATIONS /",
        "CONTINUATION-SPECIFIC ACTION / CONDITIONAL PROSPECTION /",
        "PRESENT A0 INFLUENCE / NOVEL COMPOSITION",
        "NOT claimed: planning / alternatives understanding / strategy",
    ]
    return format_layers("4.33 CONDITIONAL PROSPECTION", layers, extra)




def adapter_434() -> list[str]:
    base = ROOT / "results" / "update434_multimodal_consequence_learning"
    snap = _load(base / "OBSERVER_MULTIMODAL_CONSEQUENCE_SNAPSHOT.json") or {}
    first = snap.get("FIRST_UNSUPPORTED_ARROW") or []
    bi = snap.get("example_bimodal") or {}
    br = snap.get("example_broad") or {}
    layers = {
        "WORLD_TRUTH": "same (S,A); separated vs broad consequence processes",
        "BODY_TRUTH": f"legacy_mean field_1={bi.get('legacy_field1')}; fictitious_mean={bi.get('fictitious_mean')}",
        "ACCESSIBLE_SIGNALS": "generic absolute fragments (field_1/field_2/resistance)",
        "PSYCHE_MODEL": f"bounded components capacity={snap.get('params', {}).get('MAX_COMPONENTS')}; legacy mean unchanged",
        "PROSPECTIVE": (
            f"{snap.get('passive_prospection')}; "
            f"FIRST UNSUPPORTED: {first}"
        ),
        "ACTION": "action_logits NOT modified (4.29 NULL preserved)",
        "CONSEQUENCE": (
            f"bimodal centers={bi.get('centers_field1')} n={bi.get('n_supported')}; "
            f"broad n={br.get('n_supported')} centers={br.get('centers_field1')}; "
            f"outcome={snap.get('OUTCOME')}"
        ),
    }
    extra = _claim_line(base / "claim_matrix.json") + [
        "",
        "LEGACY MEAN vs COMPONENT CENTERS vs BROAD-NOISE CONTROL",
        "NOT claimed: possibilities awareness / planning / uncertainty preference",
    ]
    return format_layers("4.34 MULTIMODAL CONSEQUENCE LEARNING", layers, extra)




def adapter_435() -> list[str]:
    base = ROOT / "results" / "update435_predictive_structure_selection"
    snap = _load(base / "OBSERVER_PREDICTIVE_STRUCTURE_SNAPSHOT.json") or {}
    first = snap.get("FIRST_UNSUPPORTED_ARROW") or []
    ex = snap.get("examples") or {}
    layers = {
        "WORLD_TRUTH": "persistent / iid / memoryless-bimodal / drift / hist-diff",
        "BODY_TRUTH": "ordinary field fragments only (no regime labels)",
        "ACCESSIBLE_SIGNALS": "same as 4.34 absolute fragments",
        "PSYCHE_MODEL": "4.34 components + bounded follow_by_component/context; ASSIGN_* unchanged",
        "PROSPECTIVE": "NOT wired; action_logits untouched",
        "ACTION": f"per_seed={snap.get('per_seed')}",
        "CONSEQUENCE": (
            f"persΔ={ (ex.get('persistent') or {}).get('delta_collapsed_minus_full') }; "
            f"iidΔ={ (ex.get('broad_iid') or {}).get('delta_collapsed_minus_full') }; "
            f"memΔ={ (ex.get('memoryless_bimodal') or {}).get('delta_collapsed_minus_full') }; "
            f"driftΔ={ (ex.get('drift') or {}).get('delta_collapsed_minus_full') } n={ (ex.get('drift') or {}).get('n_components') }; "
            f"outcome={snap.get('OUTCOME')}; FIRST={first}"
        ),
    }
    extra = _claim_line(base / "claim_matrix.json") + [
        "",
        "FULL vs COLLAPSED prequential error; 4.34 geometric C4 historical NULL",
        "NOT claimed: latent-state inference / beliefs / planning",
    ]
    return format_layers("4.35 PREDICTIVE STRUCTURE SELECTION", layers, extra)




def adapter_436() -> list[str]:
    base = ROOT / "results" / "update436_predictive_representation_sufficiency"
    snap = _load(base / "OBSERVER_REPRESENTATION_SUFFICIENCY_SNAPSHOT.json") or {}
    first = snap.get("FIRST_UNSUPPORTED_ARROW") or []
    ex = snap.get("examples") or {}
    d = ex.get("drift_435") or {}
    err = d.get("err") or {}
    layers = {
        "WORLD_TRUTH": "continuous drift / persistent / hist-diff / memoryless (no ontology labels)",
        "BODY_TRUTH": f"4.35 drift comps={ (d.get('cost') or {}).get('n_components') } anchors={ (d.get('cost') or {}).get('n_anchors') }",
        "ACCESSIBLE_SIGNALS": "ordinary field fragments",
        "PSYCHE_MODEL": "R0 collapsed | R1 component | R2 IDW relational | R3 context; ASSIGN_* unchanged",
        "PROSPECTIVE": "NOT wired",
        "ACTION": f"per_seed={snap.get('per_seed')}",
        "CONSEQUENCE": (
            f"drift err col={err.get('collapsed')} comp={err.get('component')} rel={err.get('relational')}; "
            f"outcome={snap.get('OUTCOME')}; FIRST={first}"
        ),
    }
    extra = _claim_line(base / "claim_matrix.json") + [
        "",
        "COMPONENTIZED vs COMPACT RELATIONAL vs COLLAPSED",
        "4.35 C6 historical NULL preserved (component identity not required)",
        "NOT claimed: ontology / latent states / planning",
    ]
    return format_layers("4.36 PREDICTIVE REPRESENTATION SUFFICIENCY", layers, extra)




def adapter_437() -> list[str]:
    base = ROOT / "results" / "update437_multimodal_prospective_propagation"
    snap = _load(base / "OBSERVER_CONTINGENT_FUTURES_SNAPSHOT.json") or {}
    first = snap.get("FIRST_UNSUPPORTED_ARROW") or []
    ex = snap.get("examples") or {}
    layers = {
        "WORLD_TRUTH": "bimodal contingent + WAIT world families + body fatigue under WAIT",
        "BODY_TRUTH": f"wait_n={ex.get('wait_n')}; drift_status={ex.get('drift_status')}",
        "ACCESSIBLE_SIGNALS": "ordinary fields; no collision/threat labels",
        "PSYCHE_MODEL": "predict_continuations + propagate_continuations; legacy distal_prediction unchanged",
        "PROSPECTIVE": (
            f"prop_n={ex.get('prop_n')}; traj_actions={ex.get('traj_actions')}; "
            f"C18 mean-path only; FIRST={first}"
        ),
        "ACTION": "continuation-specific later A/B via ordinary_state_value; present logits unchanged",
        "CONSEQUENCE": f"outcome={snap.get('OUTCOME')}; {snap.get('OUTCOME_TEXT')}",
    }
    extra = _claim_line(base / "claim_matrix.json") + [
        "",
        "4.33 historical C2-C7 NULL preserved",
        "NOT claimed: planning / expected utility / fear / world-act tokens",
    ]
    return format_layers("4.37 CONTINGENT PHYSICAL FUTURES", layers, extra)


def adapter_438() -> list[str]:
    base = ROOT / "results" / "update438_psyche_incubation"
    snap = _load(base / "OBSERVER_PSYCHE_INCUBATION_SNAPSHOT.json") or {}
    ex = snap.get("example") or {}; preds = ex.get("predictions") or {}
    layers = {
        "WORLD_TRUTH": "Externally caused X1-X3 interactions, withdrawal, then accessible X1/X4/Y.",
        "BODY_TRUTH": f"external_count={((ex.get('initial') or {}).get('external_count'))}; WAIT body dynamics continue",
        "ACCESSIBLE_SIGNALS": "numeric physical features and body channels only; phase labels are researcher-side",
        "PSYCHE_MODEL": f"bounded passive physical prediction; memory={ex.get('memory')}",
        "PROSPECTIVE": f"known={((preds.get('known') or {}).get('status'))} novel={((preds.get('novel_X4') or {}).get('status'))}",
        "ACTION": f"first={ex.get('first_endogenous_intervention')}; learned contribution to logits=0",
        "CONSEQUENCE": f"outcome={snap.get('outcome')}; first={snap.get('first_unsupported_arrow')}",
    }
    return format_layers("4.38 PSYCHE INCUBATION", layers, _claim_line(base / "claim_matrix.json"))


def adapter_439() -> list[str]:
    base = ROOT / "results" / "update439_sensorimotor_dynamics"
    snap = _load(base / "OBSERVER_SENSORIMOTOR_DYNAMICS_SNAPSHOT.json") or {}
    ex = snap.get("example") or {}; ant = ex.get("anticipatory") or {}; sweep = ex.get("body_sweep") or {}
    layers = {
        "WORLD_TRUTH": "Matched sensory world; actual physical body sweep and ordinary precursor transitions.",
        "BODY_TRUTH": f"generic process levels={list(sweep)}; processes continue under WAIT",
        "ACCESSIBLE_SIGNALS": "internal_a/load_c numeric fragments; signal-only and body-only controls",
        "PSYCHE_MODEL": "bounded three-channel N: decay + persistence + mixed actual-body coupling",
        "PROSPECTIVE": f"composed prediction present; current-state delta={ant.get('state_delta')}",
        "ACTION": f"REACTIVE BODY MODULATION: {snap.get('reactive_body_modulation')}; ANTICIPATORY SENSORIMOTOR MODULATION: {snap.get('anticipatory_sensorimotor_modulation')}",
        "CONSEQUENCE": f"ORDINARY_STATE_VALUE REQUIRED: {snap.get('ordinary_state_value_required')}; first={snap.get('first_unsupported_arrows')}",
    }
    return format_layers("4.39 SENSORIMOTOR DYNAMICS", layers, _claim_line(base / "claims.json"))


def adapter_440() -> list[str]:
    base=ROOT/"results"/"update440_predictive_reinstatement";snap=_load(base/"OBSERVER_PREDICTIVE_SIGNALING_SNAPSHOT.json") or {};ex=snap.get("example") or {};hist=ex.get("history") or {};learned=hist.get("learned") or {}
    layers={
      "WORLD_TRUTH":"Matched precursor probes occur before and with omission of the future body event.",
      "BODY_TRUTH":f"current={learned.get('current_body')}; hidden future contribution=0",
      "ACCESSIBLE_SIGNALS":"ordinary physical precursor features; no phase or future-event token",
      "PSYCHE_MODEL":"bounded generic I (3 channels, decay/persistence) and source-agnostic I->N port",
      "PROSPECTIVE":f"prediction={learned.get('prediction')}; acquired I={snap.get('acquired_endogenous_signal')}",
      "ACTION":f"PRE-EVENT N: {snap.get('pre_event_N_modulation')}; MOTOR: {snap.get('motor_consequence')}",
      "CONSEQUENCE":f"FUTURE-SPECIFIC: {snap.get('future_specific_structure')}; VALUE-INDEPENDENT: {snap.get('valuation_independent')}; FIRST={snap.get('first_unsupported_arrow')}",
    }
    return format_layers("4.40 ENDOGENOUS PREDICTIVE SIGNALING",layers,_claim_line(base/"claims.json"))


def adapter_441() -> list[str]:
    base=ROOT/"results"/"update441_acquired_internal_coupling";snap=_load(base/"OBSERVER_ACQUIRED_INTERNAL_DYNAMICS_SNAPSHOT.json") or {};ex=snap.get("example") or {};st=ex.get("structured") or {}
    layers={"WORLD_TRUTH":"Matched numeric temporal sequences; pre-event probes omit the later physical event.",
    "BODY_TRUTH":"Primary probe body-matched; secondary propagation uses unchanged 4.39 body/N substrate.",
    "ACCESSIBLE_SIGNALS":"three generic numeric channels; no symbolic precursor/destination identities",
    "PSYCHE_MODEL":f"bounded 3x3 local W + eligibility trace; representation={st.get('representation')}",
    "PROSPECTIVE":f"runtime prediction required={snap.get('runtime_prediction_required')}; prediction contribution=0",
    "ACTION":f"I={snap.get('endogenous_I_generated')} N={snap.get('pre_event_N_modulation')} motor={snap.get('motor_consequence')}",
    "CONSEQUENCE":f"plasticity={snap.get('local_plasticity')} history={snap.get('history_dependent_internal_activation')} mapping={snap.get('mapping_specificity')}",}
    return format_layers("4.41 ACQUIRED INTERNAL DYNAMICS",layers,_claim_line(base/"claims.json"))




def adapter_442() -> list[str]:
    base = ROOT / "results" / "update442_body_coupled_regulation"
    snap = _load(base / "OBSERVER_BODY_COUPLED_SNAPSHOT.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "developmental X→A→body sequences; WAIT autonomous body drift; no semantic objects",
        "BODY_TRUTH": f"future_altered={snap.get('FUTURE_BODY_TRAJECTORY_ALTERED')}; closed_loop={snap.get('FULL_CLOSED_LOOP')}",
        "ACCESSIBLE_SIGNALS": "ordinary fields; precursor X numeric only",
        "PSYCHE_MODEL": "4.41 W→q→I→N; local plasticity; prediction/OSV not causal at probe",
        "PROSPECTIVE": f"prediction_required={snap.get('EXPLICIT_PREDICTION_REQUIRED')}; osv_required={snap.get('ORDINARY_STATE_VALUE_REQUIRED')}",
        "ACTION": f"intervention_shift={snap.get('AUTONOMOUS_INTERVENTION_SHIFT')}; revision={snap.get('REVISION')}",
        "CONSEQUENCE": f"outcome={snap.get('outcome')}; {snap.get('outcome_text')}; arrows={arrows}",
    }
    extra = _claim_line(base / "claims.json") + [
        "",
        "Statuses:",
        f"  BODY-COUPLED ACQUISITION: {snap.get('BODY_COUPLED_ACQUISITION')}",
        f"  PRE-EVENT INTERNAL MODULATION: {snap.get('PRE_EVENT_INTERNAL_MODULATION')}",
        f"  AUTONOMOUS INTERVENTION SHIFT: {snap.get('AUTONOMOUS_INTERVENTION_SHIFT')}",
        f"  FUTURE BODY TRAJECTORY ALTERED: {snap.get('FUTURE_BODY_TRAJECTORY_ALTERED')}",
        f"  FULL CLOSED LOOP: {snap.get('FULL_CLOSED_LOOP')}",
        f"  REVISION: {snap.get('REVISION')}",
        f"  EXPLICIT PREDICTION REQUIRED: {snap.get('EXPLICIT_PREDICTION_REQUIRED')}",
        f"  ORDINARY_STATE_VALUE REQUIRED: {snap.get('ORDINARY_STATE_VALUE_REQUIRED')}",
        f"  FIRST UNSUPPORTED ARROW: {arrows}",
        "",
        "Probe fields: current body, precursor X, W, q, I, N, motor/WAIT, physical A=M1,",
        "future body trajectory, stochastic baseline, W / I->N / prediction / valuation ablations.",
        "NOT claimed: hunger/desire/goal/homeostasis/preference/intention",
    ]
    return format_layers("4.42 BODY-COUPLED DEVELOPMENT", layers, extra)




def adapter_443() -> list[str]:
    base = ROOT / "results" / "update443_distal_consequence"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "X → A → delay → B vs X → A + decorrelated B; researcher labels only",
        "BODY_TRUTH": f"outcome={snap.get('outcome')}; {snap.get('outcome_text')}",
        "ACCESSIBLE_SIGNALS": "numeric X/A/B patterns; no CREDIT/GOOD/BAD",
        "PSYCHE_MODEL": "unchanged 4.41 W; TRACE_DECAY=0.62; eligibility at B measured",
        "PROSPECTIVE": "runtime prediction unused; OSV=0",
        "ACTION": f"C30={snap.get('C30')}; C29={snap.get('C29')}",
        "CONSEQUENCE": f"what_B_added={snap.get('what_B_added')}; arrows={arrows}",
    }
    extra = _claim_line(base / "claims.json") + [
        "",
        f"FIRST UNSUPPORTED ARROW: {arrows}",
        "Compare: PROXIMAL ONLY vs DISTAL RELATED vs DISTAL DECORRELATED",
        "NOT claimed: credit assignment, reward, intention, preference",
    ]
    return format_layers("4.43 DISTAL CONSEQUENCE", layers, extra)



def adapter_444() -> list[str]:
    base = ROOT / "results" / "update444_body_context_interaction"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "factorial current body × developmental W; no GOOD/BAD labels",
        "BODY_TRUTH": f"outcome={snap.get('outcome')}; span={snap.get('mean_span')}",
        "ACCESSIBLE_SIGNALS": "internal_a, load_c numeric; acquired W",
        "PSYCHE_MODEL": "unchanged 4.41 W; 4.39 body→N additive; softmax readout unchanged",
        "PROSPECTIVE": "prediction unused; OSV=0",
        "ACTION": f"dPA_mid={snap.get('mean_dPA_mid')}; residual={snap.get('mean_residual')}",
        "CONSEQUENCE": f"{snap.get('outcome_text')}; arrows={arrows}",
    }
    extra = _claim_line(base / "claims.json") + [
        "",
        f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: motivation, context, urgency, preferred state",
    ]
    return format_layers("4.44 BODY × ACQUIRED DYNAMICS", layers, extra)



def adapter_445() -> list[str]:
    base = ROOT / "results" / "update445_world_body_biography"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "X on ch0, body on ch1; paired vs swapped vs shuffled; researcher labels only",
        "BODY_TRUTH": f"outcome={snap.get('outcome')}",
        "ACCESSIBLE_SIGNALS": "numeric world/body pulses; no SELF/BIOGRAPHY in cognition",
        "PSYCHE_MODEL": "unchanged 4.41 W; joint relation only if both channels enter u",
        "PROSPECTIVE": "prediction unused; OSV=0",
        "ACTION": "motor diagnostic only; readout not changed",
        "CONSEQUENCE": f"{snap.get('outcome_text')}; arrows={arrows}",
    }
    extra = _claim_line(base / "claims.json") + ["", f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: autobiographical memory, self, identity, preference"]
    return format_layers("4.45 WORLD–BODY CO-DEVELOPMENT", layers, extra)


def adapter_446() -> list[str]:
    base = ROOT / "results" / "update446_acquired_sensorimotor_coupling"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "matched-marginal N/M pairings H_A vs H_B vs shuffled; researcher labels only",
        "BODY_TRUTH": f"outcome={snap.get('outcome')}",
        "ACCESSIBLE_SIGNALS": "numeric N and M activity; no REWARD/TARGET/PREFERRED",
        "PSYCHE_MODEL": "gated R 3x3; init 0; TRACE_DECAY=0.62; fixed readout default unchanged",
        "PROSPECTIVE": "prediction unused; OSV=0; W unused",
        "ACTION": "distributional P(M) before sample; acquired path additive",
        "CONSEQUENCE": f"{snap.get('outcome_text')}; arrows={arrows}",
    }
    extra = _claim_line(base / "claims.json") + ["", f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: preference, intention, action value, RL"]
    return format_layers("4.46 ACQUIRED SENSORIMOTOR COUPLING", layers, extra)


def adapter_447() -> list[str]:
    base = ROOT / "results" / "update447_endogenous_motor_access"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "4.46 H_A/H_B R frozen; diagnostic N_probe vs N_endo; no gain change",
        "BODY_TRUTH": f"outcome={snap.get('outcome')}",
        "ACCESSIBLE_SIGNALS": "numeric N at R boundary; no BOOST/TARGET",
        "PSYCHE_MODEL": "unchanged 4.46 R; same motor_distribution",
        "PROSPECTIVE": "instrumentation only; OSV=0",
        "ACTION": "distributional P(M); 0.02 is historical reference not a target",
        "CONSEQUENCE": f"{snap.get('outcome_text')}; arrows={arrows}",
    }
    extra = _claim_line(base / "claims.json") + ["", f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: motivation, intention, desire, agency"]
    return format_layers("4.47 ENDOGENOUS MOTOR ACCESS", layers, extra)


def adapter_448() -> list[str]:
    base = ROOT / "results" / "update448_endogenous_dynamic_range"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "4.46 R frozen; natural vs controlled vs probe N; no gain change",
        "BODY_TRUTH": f"outcome={snap.get('outcome')}",
        "ACCESSIBLE_SIGNALS": "numeric q/I/N; no URGENCY/BOOST",
        "PSYCHE_MODEL": "unchanged 4.39–4.46 equations; 4.45 unused",
        "PROSPECTIVE": "survey only; OSV=0",
        "ACTION": "distributional P(M); 0.02 historical reference",
        "CONSEQUENCE": f"{snap.get('outcome_text')}; arrows={arrows}",
    }
    extra = _claim_line(base / "claims.json") + ["", f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: motivation, intention, agency"]
    return format_layers("4.48 ENDOGENOUS DYNAMIC RANGE", layers, extra)


def adapter_449() -> list[str]:
    base = ROOT / "results" / "update449_ordinary_physical_excitation"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "4.19 fields at A/B/far; no world→u bridge added",
        "BODY_TRUTH": f"outcome={snap.get('outcome')}",
        "ACCESSIBLE_SIGNALS": "local field sample; u remains empty; no SALIENCE",
        "PSYCHE_MODEL": "unchanged 4.39–4.46; W.step(physical_input=())",
        "PROSPECTIVE": "audit only; OSV=0",
        "ACTION": "distributional P(M) at 4.48-scale N",
        "CONSEQUENCE": f"{snap.get('outcome_text')}; arrows={arrows}",
    }
    extra = _claim_line(base / "claims.json") + ["", f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: reward, salience, motivation. Bridge not added."]
    return format_layers("4.49 ORDINARY PHYSICAL EXCITATION", layers, extra)



def adapter_450() -> list[str]:
    base = ROOT / "results" / "update450_world_body_motor_access"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "4.19 fields; 4.20 env_modulator→internal_a when config on; no world→u",
        "BODY_TRUTH": f"outcome={snap.get('outcome')}",
        "ACCESSIBLE_SIGNALS": "absolute internal_a / load_c; u=0; no SOURCE_IDENTITY",
        "PSYCHE_MODEL": "unchanged 4.39 evolve + frozen 4.46 R; 4.45 unused",
        "PROSPECTIVE": "audit only; OSV=0",
        "ACTION": "distributional P(M) under frozen R_A / R_B",
        "CONSEQUENCE": f"{snap.get('outcome_text')}; arrows={arrows}",
    }
    extra = _claim_line(base / "claims.json") + ["", f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: desire, motivation, reward, agency. No bridge added."]
    return format_layers("4.50 WORLD → BODY → MOTOR ACCESS", layers, extra)



def adapter_451() -> list[str]:
    base = ROOT / "results" / "update451_default_runtime_body_access"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "DEFAULT organism launch; persistent_process_config remains None",
        "BODY_TRUTH": f"outcome={snap.get('outcome')}",
        "ACCESSIBLE_SIGNALS": "internal_loads empty; physiology changes; no WRITER_ID",
        "PSYCHE_MODEL": "unchanged 4.39–4.50; 4.20 gated off; 4.45 unused",
        "PROSPECTIVE": "audit only; OSV=0",
        "ACTION": "WAIT and free-action default Engine.step",
        "CONSEQUENCE": f"{snap.get('outcome_text')}; arrows={arrows}",
    }
    extra = _claim_line(base / "claims.json") + ["", f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: desire, motivation, reward, agency. No default enabled. Preset is not DEFAULT evidence."]
    return format_layers("4.51 DEFAULT RUNTIME BODY ACCESS", layers, extra)



def adapter_452() -> list[str]:
    base = ROOT / "results" / "update452_early_physical_ecology"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "DEVELOP / WASHOUT / SAME PRESENT; 4.20 ecology research-only",
        "BODY_TRUTH": f"outcome={snap.get('outcome')}",
        "ACCESSIBLE_SIGNALS": "internal_a/load_c; no ECOLOGY_ID / CAREGIVER",
        "PSYCHE_MODEL": "unchanged 4.20/4.39/4.41/4.46; default config still None",
        "PROSPECTIVE": "SAME PRESENT, DIFFERENT PAST; OSV=0",
        "ACTION": "sampled motor during develop; WAIT process action",
        "CONSEQUENCE": f"{snap.get('outcome_text')}; arrows={arrows}",
    }
    extra = _claim_line(base / "claims.json") + ["", f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: upbringing, personality, desire, reward, agency."]
    return format_layers("4.52 EARLY PHYSICAL ECOLOGY", layers, extra)

















def adapter_453() -> list[str]:
    base = ROOT / "results" / "update453_matched_motor_body_history"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "SAME MOTOR HISTORY, DIFFERENT BODY HISTORY; 4.20 pulse schedules research-only",
        "BODY_TRUTH": f"outcome={snap.get('outcome')} sat=0 pulse8 dist vs block",
        "ACCESSIBLE_SIGNALS": "internal_a/load_c; no ecology/stream/cohort id",
        "PSYCHE_MODEL": "unchanged 4.20/4.39/4.46; default config still None",
        "PROSPECTIVE": "matched M* replay is researcher control, not autonomous",
        "ACTION": f"mismatch={snap.get('mismatch_total')} median_D={snap.get('median_D')}",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: upbringing, personality, desire, reward, agency."]
    return format_layers("4.53 MATCHED MOTOR HISTORY", layers, extra)



def adapter_454() -> list[str]:
    base = ROOT / "results" / "update454_ordinary_physical_ecology"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "ORDINARY --world organism; 4.20 gated off; this preset is not ordinary evidence",
        "BODY_TRUTH": f"outcome={snap.get('outcome')} a={snap.get('any_internal_a')} c={snap.get('any_load_c')}",
        "ACCESSIBLE_SIGNALS": "internal_loads empty; no ecology/pulse/schedule id",
        "PSYCHE_MODEL": "unchanged 4.20/4.39/4.46; default config still None",
        "PROSPECTIVE": "Section 24 NOT_RUN unless ordinary 4.39 trajectory exists",
        "ACTION": "WAIT and FREE; no researcher pulse",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: curiosity, upbringing, desire, ordinary pulse ecology."]
    return format_layers("4.54 ORDINARY PHYSICAL ECOLOGY DIAGNOSTIC", layers, extra)



def adapter_455() -> list[str]:
    base = ROOT / "results" / "update455_existing_physiology_compatibility"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW") or {}
    layers = {
        "WORLD_TRUTH": "ORDINARY PHYSIOLOGY RECORDING; 4.20 off; this preset is not a runtime wire",
        "BODY_TRUTH": "WORLD/ACTION → physiology -X-> 4.39 in ordinary runtime",
        "ACCESSIBLE_SIGNALS": "fatigue/energy/hydration exist; they are not 4.39 inputs",
        "PSYCHE_MODEL": "unchanged 4.39/4.46; default config still None",
        "PROSPECTIVE": "RESEARCHER-SIDE 4.39 REPLAY of recorded physiology (not ordinary)",
        "ACTION": f"outcome={snap.get('outcome')} passing={snap.get('passing')}",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: integration, homeostasis, preference, ordinary physiology→N."]
    return format_layers("4.55 EXISTING PHYSIOLOGY COMPATIBILITY", layers, extra)



def adapter_456() -> list[str]:
    base = ROOT / "results" / "update456_generic_physical_transduction"
    snap = _load(base / "summary.json") or {}
    arrows = snap.get("FIRST_UNSUPPORTED_ARROW")
    layers = {
        "WORLD_TRUTH": "ORDINARY WORLD / ACTION; 4.20 off; transducer experimental only",
        "BODY_TRUTH": "BODY physiology → bounded transducer X (not a nervous system)",
        "ACCESSIBLE_SIGNALS": "X is numeric transducer state; names do not enter cognition",
        "PSYCHE_MODEL": "unchanged 4.39 via mixed ports; unchanged 4.46 R; default config None",
        "PROSPECTIVE": "BODY → X(t) → N(t) → R → MOTOR  (experimental pathway)",
        "ACTION": f"outcome={snap.get('outcome')} live={snap.get('live_ok')}",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", f"FIRST UNSUPPORTED ARROW: {arrows}",
        "NOT claimed: nervous system, feeling, desire, homeostasis, default bridge."]
    return format_layers("4.56 GENERIC PHYSICAL TRANSDUCTION", layers, extra)



def adapter_457() -> list[str]:
    base = ROOT / "results" / "update457_motor_pathway_archaeology"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "PHYSICAL_ACTION = Action.kind into OrganismWorld; 4.20 off",
        "BODY_TRUTH": "body changes from PHYSICAL_ACTION, not from 4.39 sample_motor",
        "ACCESSIBLE_SIGNALS": "INTERNAL_MOTOR {M0,M1,M2,WAIT} is research-only",
        "PSYCHE_MODEL": "ordinary selector is SingleOrganismPsycheV03; R not on that path",
        "PROSPECTIVE": "R -> INTERNAL_MOTOR -> ?   |   ? -> PHYSICAL_ACTION -> WORLD/BODY",
        "ACTION": f"outcome={snap.get('outcome')} missing={snap.get('FIRST_MISSING_EDGE')}",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + [
        "", f"FIRST UNSUPPORTED: {snap.get('FIRST_UNSUPPORTED_ARROW')}",
        "Absent edge shown as absent. Not a nervous system. Not a new bridge.",
    ]
    return format_layers("4.57 MOTOR PATHWAY ARCHAEOLOGY", layers, extra)



def adapter_458() -> list[str]:
    base = ROOT / "results" / "update458_action_space_compatibility"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "PHYSICAL: Action.kind then discrete cell writes; no generic effector",
        "BODY_TRUTH": "body costs are consequences, not a vector actuator",
        "ACCESSIBLE_SIGNALS": "INTERNAL: N then R then preact then M0/M1/M2/WAIT",
        "PSYCHE_MODEL": "NO CAUSAL BRIDGE. Comparison only.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} effector={snap.get('PHYSICAL_EFFECTOR_LAYER')}",
        "ACTION": "STRUCTURAL COMPARISON ONLY",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "Not a mapping. Not an actuator."]
    return format_layers("4.58 ACTION SPACE COMPATIBILITY", layers, extra)



def adapter_459() -> list[str]:
    base = ROOT / "results" / "update459_generic_physical_effector"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "RESEARCHER DRIVE then E then local Q then is_open hop. Semantic Action isolated at WAIT.",
        "BODY_TRUTH": "existing distance then movement_cost if a hop realizes; no invented actuator cost",
        "ACCESSIBLE_SIGNALS": "E is NOT observed. preact is NOT read.",
        "PSYCHE_MODEL": "NO COUPLING. preact  X  E",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} dim={snap.get('E_dim')} first_unsupported={snap.get('FIRST_UNSUPPORTED_ARROW')}",
        "ACTION": "RESEARCHER_PHYSICAL_EFFECTOR_RUN. Not autonomous.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "Not a mapping. Not preact control. Not 4.60."]
    return format_layers("4.59 GENERIC PHYSICAL EFFECTOR", layers, extra)



def adapter_460() -> list[str]:
    base = ROOT / "results" / "update460_arbitrary_physical_coupling"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "D then E then Q then is_open hop. WAIT isolated. 4.59 unchanged.",
        "BODY_TRUTH": "existing distance then movement_cost if hop realizes",
        "ACCESSIBLE_SIGNALS": "controlled preact is researcher-imposed. C and Z not observed.",
        "PSYCHE_MODEL": "FIXED C. NON-LEARNED. EXPERIMENTAL. Not M0/M1/M2 directions.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} first_unsupported={snap.get('FIRST_UNSUPPORTED_ARROW')}",
        "ACTION": "CONTROLLED PROBE vs LIVE PREACT DIAGNOSTIC (secondary). Not autonomous.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "Not a learned map. Not 4.61. Not closed-loop."]
    return format_layers("4.60 ARBITRARY PHYSICAL COUPLING", layers, extra)







def adapter_463() -> list[str]:
    base = ROOT / "results" / "update463_existing_physical_ecology"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "WORLD PHYSICS. Passive WAIT exposure/contact. Numeric object/field properties. Not desirability.",
        "BODY_TRUTH": "existing basal + existing field coupling when enabled. Defaults remain None.",
        "ACCESSIBLE_SIGNALS": "BODY then X then N then preact then C then D then E then Q then threshold. RESEARCHER DIAGNOSTICS.",
        "PSYCHE_MODEL": "WAIT isolated. Not desire. Not seeking. Not a goal.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} maxQ={snap.get('max_q')} hops={snap.get('hops_r')}",
        "ACTION": f"body_class={snap.get('body_class')} Q={snap.get('q_by')}",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "DIAGNOSTIC ONLY. Not tuned. Not 4.64. Not adaptive."]
    return format_layers("4.63 EXISTING PHYSICAL ECOLOGY", layers, extra)


def adapter_462() -> list[str]:
    base = ROOT / "results" / "update462_amplitude_budget"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "DIAGNOSTIC ONLY. BODY then X then N then preact then Z then D then E then Q. Then break. Then threshold 0.60. Not cognition.",
        "BODY_TRUTH": "existing 4.56 ABSOLUTE when R1; ordinary basal B. Defaults remain None.",
        "ACCESSIBLE_SIGNALS": "stage norms / sign removal / E persistence / site cancellation / Q margin are researcher annotations.",
        "PSYCHE_MODEL": "WAIT isolated. Not desire. Not a goal. Not a bottleneck label in cognition.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} dominant={snap.get('DOMINANT_BOTTLENECK_IDENTIFIED')}",
        "ACTION": f"R0 maxQ={snap.get('r0_maxQ')} R1={snap.get('r1_maxQ')} R3={snap.get('r3_maxQ')}",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "DIAGNOSTIC ONLY. Not tuned. Not 4.63. Not a repair."]
    return format_layers("4.62 AMPLITUDE BUDGET", layers, extra)


def adapter_461() -> list[str]:
    base = ROOT / "results" / "update461_live_operating_range"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "DIAGNOSTIC. Q vs threshold 0.60. Attempted/realized hop. No success label.",
        "BODY_TRUTH": "4.56 X experimental when enabled; default still None",
        "ACCESSIBLE_SIGNALS": "N then preact then frozen C then D then E then Q",
        "PSYCHE_MODEL": "WAIT isolated. Not desire. Not a goal.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} any_thresh={snap.get('any_thresh')} any_hop={snap.get('any_hop')}",
        "ACTION": f"R0 maxQ={snap.get('r0_maxQ')} R1={snap.get('r1_maxQ')} R3={snap.get('r3_maxQ')}",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "Not tuned. Not 4.62. Not adaptive."]
    return format_layers("4.61 LIVE OPERATING RANGE", layers, extra)



def adapter_464() -> list[str]:
    base = ROOT / "results" / "update464_world_body_path_audit"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "WORLD SOURCES. field PRESENT/NEGLIGIBLE. object USE SEMANTIC_REQUIRED. contact MOVE SEMANTIC_REQUIRED. exchange DEFAULT_OFF then internal_materials ABSENT into 4.56 BODY. events RESEARCH_ONLY.",
        "BODY_TRUTH": "4.56 consumes energy_reserve, hydration, fatigue. Basal is BODY_INTERNAL. Defaults remain None.",
        "ACCESSIBLE_SIGNALS": "INITIATION NEGLIGIBLE. RETURN STRUCTURALLY_PRESENT via distance then movement_cost. Not cognition.",
        "PSYCHE_MODEL": "WAIT isolated. Not desire. Not a goal. Not a bootstrap label in cognition.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} field={snap.get('field_operating')} initiation={snap.get('initiation')}",
        "ACTION": f"object_presence={snap.get('object_presence')} return={snap.get('return_path')}",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "DIAGNOSTIC ONLY. Not tuned. Not 4.65. No new WORLD to BODY edge."]
    return format_layers("4.64 WORLD TO BODY AUDIT", layers, extra)



def adapter_465() -> list[str]:
    base = ROOT / "results" / "update465_minimal_passive_physical_exchange"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "Local env_material_field availability at organism cell. No object class. No USE.",
        "BODY_TRUTH": "energy_reserve / hydration / fatigue trajectories. Exchange magnitude = last_env_exchange / processed material. Not a need.",
        "ACCESSIBLE_SIGNALS": "source present/absent and exchange enabled/disabled are researcher conditions, not cognition.",
        "PSYCHE_MODEL": "WAIT. Not desire. Not a goal.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} materiality={snap.get('materiality')} linf={snap.get('max_comp_linf')}",
        "ACTION": "policy=WAIT. No hop. Q not shown.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "Physical facts only. Not reward. Not 4.66."]
    return format_layers("4.65 MINIMAL PASSIVE PHYSICAL EXCHANGE", layers, extra)



def adapter_466() -> list[str]:
    base = ROOT / "results" / "update466_frozen_physical_composition"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "Frozen 4.65 env_material_field at organism cell. Position. Not a resource label.",
        "BODY_TRUTH": "energy/hydration/fatigue. Exchange on/off. Not a need.",
        "ACCESSIBLE_SIGNALS": "X N preact D E Q and hop are researcher traces, not cognition.",
        "PSYCHE_MODEL": "WAIT. Not seeking. Not avoidance.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} maxQ={snap.get('global_max_Q')} hops={snap.get('realized_hops')}",
        "ACTION": "policy=WAIT. threshold=0.60. No semantic MOVE.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "Composition only. Not 4.67. Not adaptive."]
    return format_layers("4.66 FROZEN PHYSICAL COMPOSITION", layers, extra)



def adapter_467() -> list[str]:
    base = ROOT / "results" / "update467_physical_dof_access_audit"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "Existing physical DOFs. Position/fields/materials. Not cognition.",
        "BODY_TRUTH": "All BodyState fields. 4.56 uses energy/hydration/fatigue only.",
        "ACCESSIBLE_SIGNALS": "Access levels L0-L6 are causal labels, not sophistication.",
        "PSYCHE_MODEL": "Audit. Not seeking. Not observability.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} unused={snap.get('n_unused_paths')} dofs={snap.get('n_dofs')}",
        "ACTION": "WAIT diagnostics only. No new sensor.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "Audit only. Not 4.68. Not composed."]
    return format_layers("4.67 PHYSICAL DOF ACCESS AUDIT", layers, extra)


def adapter_468() -> list[str]:
    base = ROOT / "results" / "update468_persistent_process_provenance"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "Live sample_local_fields at position. Not a researcher schedule.",
        "BODY_TRUTH": "4.20 does not read energy/hydration/fatigue. May write fatigue.",
        "ACCESSIBLE_SIGNALS": "internal_a / load_c exist only when persistent_process_config is on.",
        "PSYCHE_MODEL": "Provenance. Not seeking. Not a Q experiment.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} world_drives={snap.get('world_drives')} default_inert={snap.get('default_inert')}",
        "ACTION": "WAIT diagnostics only. No C/E.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "Provenance only. Not 4.69. Not composed into C/E."]
    return format_layers("4.68 PERSISTENT PROCESS PROVENANCE", layers, extra)



def adapter_469() -> list[str]:
    base = ROOT / "results" / "update469_frozen_physical_composition"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "Live fields when P2. P1 fields off. Not a researcher schedule.",
        "BODY_TRUTH": "4.20 ports when config on. Movement_cost on realized hops. Not valuation.",
        "ACCESSIBLE_SIGNALS": "N written to existing researcher_controlled_preact. R unused.",
        "PSYCHE_MODEL": "Composition. Not seeking. Not a Q optimization.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} maxQ={snap.get('global_max_Q')} hop={snap.get('any_hop')}",
        "ACTION": "WAIT only. Generic E/Q/lattice if |Q|>=0.60.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "Composition only. Not 4.70. Not a loop."]
    return format_layers("4.69 FROZEN PHYSICAL COMPOSITION", layers, extra)



def adapter_470() -> list[str]:
    base = ROOT / "results" / "update470_generic_action_body_internal_return"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "Blocked first dest vs open. Fields off in primary. Not a researcher hop schedule.",
        "BODY_TRUTH": "Hop writes distance then movement_cost. 4.56 X composed ABSOLUTE after BODY. Not valuation.",
        "ACCESSIBLE_SIGNALS": "Live N is 4.20. Return N is 4.56 ports via existing evolve. Streams not mixed.",
        "PSYCHE_MODEL": "Causal return measurement. Not seeking. Not a same-stream loop.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} dB={snap.get('dB')} dX={snap.get('dX')} dNr={snap.get('dNr')}",
        "ACTION": "WAIT only. Existing C/E/Q. Threshold 0.60 unchanged.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "4.56 composed. Live N=4.20. Not 4.71. Same-stream loop not claimed."]
    return format_layers("4.70 GENERIC ACTION BODY INTERNAL RETURN", layers, extra)



def adapter_471() -> list[str]:
    base = ROOT / "results" / "update471_post_consequence_relaxation_latent_return"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "Same 4.70 open vs blocked. Fields off in primary. Not a hop schedule.",
        "BODY_TRUTH": "Temporal fate of hop BODY difference. Full E/H/F. Not valuation.",
        "ACCESSIBLE_SIGNALS": "Full X vector. Δ||X||inf vs ||ΔX||inf. Ports. Parallel N. Live N stays 4.20.",
        "PSYCHE_MODEL": "Relaxation diagnostic. Not a loop. Not seeking.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} dB={snap.get('peaks', {}).get('dB')} ||dX||={snap.get('peaks', {}).get('dX')}",
        "ACTION": "WAIT only. Threshold 0.60 unchanged.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "Parallel return only. Not 4.72. Same-stream loop not claimed."]
    return format_layers("4.71 POST-CONSEQUENCE RELAXATION", layers, extra)



def adapter_472() -> list[str]:
    base = ROOT / "results" / "update472_state_dependent_physical_consequence"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "Same one-cell distance=1 vs 0. Not a preference test.",
        "BODY_TRUTH": "DID of existing movement_cost + clip01. effort=1+0.8F. Not valuation.",
        "ACCESSIBLE_SIGNALS": "Research-side from_dict. No new runtime setter. Live N unchanged.",
        "PSYCHE_MODEL": "State-dependent physical consequence. Not learning. Not a loop.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} pred_ok={snap.get('pred_ok')}",
        "ACTION": "WAIT. Existing transition(distance).",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "CONTROLLED SAME-EVENT. Not 4.73."]
    return format_layers("4.72 STATE-DEPENDENT PHYSICAL CONSEQUENCE", layers, extra)



def adapter_473() -> list[str]:
    base = ROOT / "results" / "update473_physical_intervention_vs_nonintervention"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "Same start. Research-only EVENT vs WAIT branches. Not a choice test.",
        "BODY_TRUTH": "T_EVENT and T_WAIT through existing transition(distance). WAIT is not freeze.",
        "ACCESSIBLE_SIGNALS": "from_dict + clone. Cognition does not see the other branch.",
        "PSYCHE_MODEL": "Alternative physical futures. Not prospection. Not preference.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} pred_ok={snap.get('pred_ok')}",
        "ACTION": "WAIT + distance 1 vs 0 at fork, then both distance=0.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "COUNTERFACTUAL RESEARCH BRANCH. Not 4.74."]
    return format_layers("4.73 PHYSICAL INTERVENTION VS NON-INTERVENTION", layers, extra)



def adapter_474() -> list[str]:
    base = ROOT / "results" / "update474_body_response_consequence_acquisition_archaeology"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "4.73 EVENT/WAIT BODY futures exist. Not a reward.",
        "BODY_TRUTH": "Movement-cost BODY does not enter W/R. 4.56 X experimental only.",
        "ACCESSIBLE_SIGNALS": "Research archaeology. Cognition does not see the graph.",
        "PSYCHE_MODEL": "Mixed acquisition path. Not contingency. Not choice.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} yoked={snap.get('contingent_yoked')}",
        "ACTION": "No new learner. No new edge.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claims.json") + ["", "ARCHAEOLOGY. Not 4.75. LATER_BODY -X-> ACQUISITION."]
    return format_layers("4.74 BODY-RESPONSE-CONSEQUENCE ACQUISITION", layers, extra)



def adapter_475() -> list[str]:
    base = ROOT / "results" / "update475_response_contingent_internal_transition_acquisition"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "Research-controlled distance event. Not autonomous hop.",
        "BODY_TRUTH": "Existing movement-cost then 4.56 X snapshot S. Not live N.",
        "ACCESSIBLE_SIGNALS": f"S_before -> M -> S_after -> L. Lnorm={snap.get('L1', {}).get('frobenius')}",
        "PSYCHE_MODEL": "Bounded relation L. Not reward. L -X-> behavior.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} d12={snap.get('d12')}",
        "ACTION": "Condition identity is Observer ground truth only.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claim_ladder.json") + ["", "ONE CAPABILITY. L -X-> behavior. Not 4.76."]
    return format_layers("4.75 RESPONSE-CONTINGENT INTERNAL TRANSITION", layers, extra)



def adapter_476() -> list[str]:
    base = ROOT / "results" / "update476_acquired_transition_reinstatement"
    snap = _load(base / "summary.json") or {}
    layers = {
        "WORLD_TRUTH": "Frozen 4.75 L. Research S snapshot. Not autonomous.",
        "BODY_TRUTH": f"S_probe={snap.get('s_probe')}",
        "ACCESSIBLE_SIGNALS": f"R=S^T L. R_C F={snap.get('rC_f')} d={snap.get('d_linf')}",
        "PSYCHE_MODEL": "Bounded R_L 2x3. Not reward. R_L -X-> behavior.",
        "PROSPECTIVE": f"outcome={snap.get('outcome')} anal_err={snap.get('anal_err')}",
        "ACTION": "No M selection. Algebraic bilinear only.",
        "CONSEQUENCE": f"{snap.get('outcome_text')}",
    }
    extra = _claim_line(base / "claim_ladder.json") + ["", "ONE CAPABILITY. R_L -X-> N/preact/motor/D/E/Q. Not 4.77."]
    return format_layers("4.76 ACQUIRED TRANSITION REINSTATEMENT", layers, extra)


ADAPTERS: dict[str, Callable[[], list[str]]] = {
    "4.23 Prospective Trajectory Composition": adapter_423,
    "4.24 Endogenous Temporal Reference": adapter_424,
    "4.25 Instrumental Observation": adapter_425,
    "4.26 Prospective Consequence Influence": adapter_426,
    "4.27 Predictive Generalization": adapter_427,
    "4.28 Predictive Scenario Competition": adapter_428,
    "4.29 Predictive Reliability": adapter_429,
    "4.30 Unavoidable State Transition": adapter_430,
    "4.31 Evidence-Producing Physical Action": adapter_431,
    "4.32 Learning-Mediated Futures": adapter_432,
    "4.33 Conditional Prospection": adapter_433,
    "4.34 Multimodal Consequence Learning": adapter_434,
    "4.35 Predictive Structure Selection": adapter_435,
    "4.36 Predictive Representation Sufficiency": adapter_436,
    "4.37 Contingent Physical Futures": adapter_437,
    "4.38 Psyche Incubation": adapter_438,
    "4.39 Sensorimotor Dynamics": adapter_439,
    "4.40 Endogenous Predictive Signaling": adapter_440,
    "4.41 Acquired Internal Dynamics": adapter_441,
    "4.42 Body-Coupled Development": adapter_442,
    "4.43 Distal Consequence": adapter_443,
    "4.44 Body × Acquired Dynamics": adapter_444,
    "4.45 World–Body Biography": adapter_445,
    "4.46 Acquired Sensorimotor Coupling": adapter_446,
    "4.47 Endogenous Motor Access": adapter_447,
    "4.48 Endogenous Dynamic Range": adapter_448,
    "4.49 Ordinary Physical Excitation": adapter_449,
    "4.50 World → Body → Motor Access": adapter_450,
    "4.51 Default Runtime Body Access": adapter_451,
    "4.52 Early Physical Ecology": adapter_452,
    "4.53 Matched Motor History": adapter_453,
    "4.54 Ordinary Physical Ecology Diagnostic": adapter_454,
    "4.55 Existing Physiology Compatibility": adapter_455,
    "4.56 Generic Physical Transduction": adapter_456,
    "4.57 Motor Pathway Archaeology": adapter_457,
    "4.58 Action Space Compatibility": adapter_458,
    "4.59 Generic Physical Effector": adapter_459,
    "4.60 Arbitrary Physical Coupling": adapter_460,
    "4.61 Live Operating Range": adapter_461,
    "4.62 Amplitude Budget": adapter_462,
    "4.63 Existing Physical Ecology": adapter_463,
    "4.64 WORLD→BODY Audit": adapter_464,
    "4.65 Minimal Passive Physical Exchange": adapter_465,
    "4.66 Frozen Physical Composition": adapter_466,
    "4.67 Physical DOF Access Audit": adapter_467,
    "4.68 Persistent Process Provenance": adapter_468,
    "4.69 Frozen Physical Composition": adapter_469,
    "4.70 Generic Action Body Internal Return": adapter_470,
    "4.71 Post-Consequence Relaxation and Latent Return": adapter_471,
    "4.72 State-Dependent Physical Consequence": adapter_472,
    "4.73 Physical Intervention vs Non-Intervention": adapter_473,
    "4.74 Body-Response-Consequence Acquisition Archaeology": adapter_474,
    "4.75 Response-Contingent Internal Transition Acquisition": adapter_475,
    "4.76 Acquired Transition Reinstatement": adapter_476,
}


def lines_for_preset(preset_name: str) -> list[str]:
    fn = ADAPTERS.get(preset_name)
    if not fn:
        # fuzzy match by update number
        for key, adapter in ADAPTERS.items():
            if key[:4] in preset_name:
                return adapter()
        return [f"(no experiment_viz adapter for {preset_name!r})"]
    return fn()
