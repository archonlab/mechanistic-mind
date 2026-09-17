#!/usr/bin/env python3
"""Build the documentation-only Mechanistic Mind provenance layer.

This script reads preserved reports/results and writes only under knowledge/.
It never imports or executes agent/runtime code.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
KNOW = ROOT / "knowledge"
STRUCT = KNOW / "structured"
EXPDIR = KNOW / "experiments"


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def dump(name: str, value) -> None:
    (STRUCT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def version_from_dir(name: str) -> str:
    m = re.match(r"update(\d+)", name)
    if not m:
        return "UNKNOWN"
    s = m.group(1)
    if s == "4":
        return "4.0"
    special = {"471": "4.7.1", "491": "4.9.1", "4122": "4.12.2", "4131": "4.13.1", "4181": "4.18.1", "4182": "4.18.2"}
    if s in special:
        return special[s]
    if s.startswith("410") and len(s) > 3:
        return "4.10." + s[3:]
    return "4." + s[1:]


def vkey(v: str):
    if v == "UNKNOWN":
        return (999,)
    return tuple(int(x) for x in v.split("."))


def heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            title = re.sub(r"^#\s+", "", line).strip()
            title = re.sub(r"(?i)^update\s+[\d.]+\s*[-—:]?\s*", "", title)
            title = re.sub(r"(?i)^\d+(?:\.\d+)+\s+final report\s*", "", title)
            title = re.sub(r"(?i)final report\s*[-—:]?\s*", "", title).strip(" —-")
            return title or fallback.replace("_", " ")
    return fallback.replace("_", " ")


def section(text: str, names: tuple[str, ...], limit: int = 1800) -> str | None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("##") and any(n.lower() in line.lower() for n in names):
            out = []
            for x in lines[i + 1:]:
                if x.startswith("##"):
                    break
                if x.strip():
                    out.append(x.strip())
            val = " ".join(out)
            return val[:limit] if val else None
    return None


def report_summary(text: str) -> str:
    chosen = section(text, ("outcome", "result", "answer", "conclusion"), 1400)
    if chosen:
        return chosen
    body = [x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")]
    return " ".join(body)[:1400] if body else "NOT_RECORDED"


def find_report(d: Path) -> Path | None:
    reports = sorted([p for p in d.glob("*.md") if "FINAL_REPORT" in p.name.upper()])
    return reports[0] if reports else None


def source_paths(d: Path) -> list[str]:
    paths = []
    version_digits = re.match(r"update(\d+)", d.name).group(1)
    candidates = list((ROOT / "experiments").glob(f"run_update{version_digits}*.py"))
    candidates += list((ROOT / "mechanistic_mind" / "research").glob("*.py"))
    stem_words = set(d.name.split("_")) - {f"update{version_digits}"}
    for p in candidates:
        score = len(stem_words & set(p.stem.split("_")))
        if p.parent.name == "experiments" or score >= 2:
            paths.append(rel(p))
    return sorted(set(paths))[:8]


def test_paths(d: Path) -> list[str]:
    digits = re.match(r"update(\d+)", d.name).group(1)
    return sorted(rel(p) for p in (ROOT / "tests").glob(f"test_update{digits}*.py"))


def claims_for(d: Path, exp_id: str) -> list[dict]:
    out = []
    for p in sorted(d.glob("*claims*.json")):
        try:
            obj = json.loads(read(p))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        for i, (key, val) in enumerate(obj.items(), 1):
            asserted = val.get("asserted") if isinstance(val, dict) else None
            status = "SUPPORTED" if asserted is True else "NOT_SUPPORTED" if asserted is False else "UNKNOWN"
            seeds = val.get("seeds", []) if isinstance(val, dict) else []
            wording = key.replace("_", " ")
            out.append({
                "claim_id": f"CLAIM-{exp_id[4:]}-{i:03d}", "source_claim_id": key,
                "wording": wording, "experiment": exp_id, "claim_type": "EMPIRICAL_ASSERTION",
                "status": status, "evidence": [rel(p)], "controls": "See experiment record/report",
                "ablations": "See experiment record/report", "limitations": "Claim wording is normalized from the surviving claim key; consult report for semantics.",
                "strongest_supported_interpretation": wording if status == "SUPPORTED" else "No positive empirical interpretation allowed.",
                "prohibited_interpretations": ["anthropomorphic or semantic interpretation beyond the report"],
                "later_reproduced_by": [], "later_modified_by": [], "later_contradicted_by": [],
                "seeds": seeds, "provenance": [rel(p)]
            })
    return out


def main() -> None:
    STRUCT.mkdir(parents=True, exist_ok=True)
    EXPDIR.mkdir(parents=True, exist_ok=True)
    dirs = [d for d in RESULTS.iterdir() if d.is_dir() and re.match(r"update\d", d.name)]
    dirs.sort(key=lambda d: (vkey(version_from_dir(d.name)), d.name))
    experiments, all_claims, provenance = [], [], []
    for idx, d in enumerate(dirs):
        version = version_from_dir(d.name)
        exp_id = "EXP-" + version
        if any(x["experiment_id"] == exp_id for x in experiments):
            exp_id += "-" + re.sub(r"^update\d+_?", "", d.name).upper().replace("_", "-")
        report = find_report(d)
        text = read(report) if report else ""
        result_files = sorted(rel(p) for p in d.iterdir() if p.is_file() and p.suffix.lower() in {".json", ".md", ".txt"})
        preregs = [x for x in result_files if "PREREG" in x.upper()]
        cpaths = source_paths(d)
        tpaths = test_paths(d)
        completeness = "COMPLETE" if report and len(result_files) >= 5 else "SUBSTANTIAL" if report else "PARTIAL" if result_files else "FRAGMENTARY"
        status = "IN_PROGRESS / NOT_CANONICAL" if version == "4.64" and not report else "COMPLETED"
        title = heading(text, d.name) if text else d.name.replace("_", " ")
        result = report_summary(text) if text else "No final report survives; consult preserved structured artifacts."
        question = section(text, ("question", "aim", "objective")) or "NOT_RECORDED"
        limits = section(text, ("limitation", "not mean", "unsupported", "frontier")) or "See report and causal/claim registries; do not infer beyond recorded assertions."
        prev = experiments[-1]["experiment_id"] if experiments else None
        record = {
            "experiment_id": exp_id, "version": version, "update": version, "title": title, "date": "UNKNOWN",
            "status": status, "predecessor": prev, "successor": None, "scientific_question": question,
            "motivation": "Generated by the preceding research frontier; exact wording is NOT_RECORDED where absent from the final report.",
            "previous_result": experiments[-1]["result"][:500] if experiments else "UNKNOWN",
            "unresolved_question": question, "architecture_before": "See predecessor and architecture registry.",
            "architecture_change": section(text, ("architecture", "implementation")) or "NOT_RECORDED",
            "new_capability": "See architecture_change; presence is not treated as empirical occurrence.",
            "hypotheses": "See preregistration/report", "preregistered_predictions": preregs or "NOT_RECORDED",
            "experimental_conditions": "See result files", "controls": section(text, ("control", "ablation")) or "See structured artifacts/report",
            "ablations": "See controls and structured artifacts", "seeds": "See claims/config/result artifacts", "duration": "NOT_RECORDED",
            "measurements": "See structured result artifacts", "result": result, "outcome_letter": (re.search(r"Outcome\s+([A-Z])", text, re.I).group(1).upper() if re.search(r"Outcome\s+([A-Z])", text, re.I) else "UNKNOWN"),
            "observed_effects": result, "null_results": "See normalized negative-result registry", "negative_results": "See normalized negative-result registry",
            "causal_edges_tested": [], "causal_edges_supported": [], "causal_edges_not_supported": [],
            "first_unsupported_arrow": "Extracted in frontier views when explicitly recoverable", "structural_first_unsupported": "UNKNOWN",
            "operating_range_first_unsupported": "UNKNOWN", "semantic_leak_result": "See semantic leakage artifacts; UNKNOWN if absent",
            "regressions": "See report", "strongest_allowed_claim": result[:700],
            "forbidden_stronger_claims": ["consciousness", "self-awareness", "free will", "desire", "intention", "emotion", "suffering", "general agency or intelligence"],
            "limitations": limits, "next_question": section(text, ("next", "frontier")) or "UNKNOWN",
            "motivated_by": prev, "unresolved_from_previous": "See predecessor next_question", "experiment_resolves": question,
            "generated_next_question": section(text, ("next", "frontier")) or "UNKNOWN",
            "source_files": cpaths, "result_files": result_files, "report_files": [rel(report)] if report else [], "tests": tpaths,
            "observer_integration": [x for x in result_files if "OBSERVER" in x.upper()],
            "provenance": ([rel(report)] if report else []) + result_files[:12] + cpaths + tpaths,
            "confidence": completeness, "source_completeness": completeness,
            "source_completeness_reason": f"final_report={bool(report)}; preserved_result_files={len(result_files)}; source_files={len(cpaths)}; tests={len(tpaths)}"
        }
        experiments.append(record)
        all_claims.extend(claims_for(d, exp_id))
        provenance.append({"item_id": exp_id, "experiment": exp_id, "report_paths": record["report_files"], "structured_result_paths": [x for x in result_files if x.endswith(".json")], "source_implementation": cpaths, "tests": tpaths, "inference": False})
    for a, b in zip(experiments, experiments[1:]):
        a["successor"] = b["experiment_id"]

    edges = [
        ("EDGE-WORLD-BODY", "WORLD", "BODY", "4.50", "STRUCTURALLY_PRESENT", "CONTROLLED_SUPPORTED; passive existing ecology NOT_SUPPORTED at 4.63", "DEFAULT_ON but material passive access not supported"),
        ("EDGE-BODY-X", "BODY", "X", "4.56", "STRUCTURALLY_PRESENT", "CONTROLLED_SUPPORTED", "EXPERIMENTAL_ONLY transducer"),
        ("EDGE-X-N", "X", "N", "4.56", "STRUCTURALLY_PRESENT", "CONTROLLED_SUPPORTED", "EXPERIMENTAL_ONLY"),
        ("EDGE-N-R", "N", "R/preact", "4.46", "STRUCTURALLY_PRESENT", "CONTROLLED_SUPPORTED", "RESEARCH_ONLY / bounded"),
        ("EDGE-PREACT-C", "preact", "C", "4.60", "STRUCTURALLY_PRESENT", "CONTROLLED_SUPPORTED", "EXPERIMENTAL_ONLY fixed coupling"),
        ("EDGE-C-D", "C", "D", "4.60", "STRUCTURALLY_PRESENT", "CONTROLLED_SUPPORTED", "EXPERIMENTAL_ONLY"),
        ("EDGE-D-E", "D", "E", "4.59", "STRUCTURALLY_PRESENT", "CONTROLLED_SUPPORTED", "EXPERIMENTAL_ONLY"),
        ("EDGE-E-Q", "E", "Q", "4.59", "STRUCTURALLY_PRESENT", "CONTROLLED_SUPPORTED", "EXPERIMENTAL_ONLY"),
        ("EDGE-Q-LATTICE", "Q", "lattice transition", "4.59", "STRUCTURALLY_PRESENT", "CONTROLLED_SUPPORTED", "live operating range NOT_SUPPORTED at 4.61/4.62"),
        ("EDGE-LIVE-THRESHOLD", "live body-derived internal activity", "physical threshold", "4.61", "STRUCTURALLY_PRESENT", "NOT_SUPPORTED", "R0/R1/R2/R3 remained subthreshold"),
        ("EDGE-PASSIVE-ECOLOGY-BODY", "existing passive ecology", "material body perturbation", "4.63", "PARTIAL_STRUCTURE", "NOT_SUPPORTED", "field effect below 0.01 materiality criterion"),
        ("EDGE-PREDICTED-N-PRESENT-N", "predicted future N", "present N modulation", "4.39", "ABSENT_IN_TESTED_ARCHITECTURE", "NOT_SUPPORTED", "prediction did not re-enter present dynamics"),
    ]
    edge_records = []
    for eid, src, dst, intro, structural, empirical, note in edges:
        tests = [e["experiment_id"] for e in experiments if e["version"] in {intro, "4.61", "4.62", "4.63"}]
        edge_records.append({"edge_id": eid, "source_state": src, "target_state": dst, "first_introduced": "EXP-"+intro, "first_tested": "EXP-"+intro, "experiments_testing": tests, "structural_status": structural, "empirical_status": empirical, "operating_range_status": note, "default_status": note, "experimental_only": "EXPERIMENTAL" in note, "semantic_dependency": "NONE unless explicitly noted in experiment report", "evidence": tests, "counterevidence": [], "latest_status": empirical, "provenance": tests})

    mechanisms = [
        ("MECH-N", "intrinsic sensorimotor dynamics N", "4.39", "bounded competing channels coupling actual body physics to motor distribution", "mechanistic_mind/body/sensorimotor_dynamics.py", "RESEARCH_ONLY"),
        ("MECH-REINSTATEMENT", "predictive reinstatement", "4.40", "test endogenous re-entry of acquired prediction", "mechanistic_mind/body/endogenous_signaling.py", "RESEARCH_ONLY"),
        ("MECH-W", "acquired internal dynamics W", "4.41", "bounded learned internal coupling", "mechanistic_mind/body/adaptive_internal_coupling.py", "RESEARCH_ONLY"),
        ("MECH-R", "acquired sensorimotor coupling R", "4.46", "bounded acquired projection toward motor preactivation", "mechanistic_mind/body/acquired_sensorimotor_coupling.py", "RESEARCH_ONLY"),
        ("MECH-X", "generic physical transduction X", "4.56", "non-semantic body-vector transduction", "mechanistic_mind/body/physical_transduction.py", "EXPERIMENTAL_ONLY"),
        ("MECH-C", "fixed non-semantic coupling C", "4.60", "map generic preactivation to effector drive without semantic channel labels", "mechanistic_mind/research/arbitrary_physical_coupling.py", "EXPERIMENTAL_ONLY"),
        ("MECH-E", "generic physical effector E", "4.59", "bounded physical effector dynamics", "mechanistic_mind/world_engine/physical_effector.py", "EXPERIMENTAL_ONLY"),
        ("MECH-Q", "physical tendency Q", "4.59", "bounded tendency resolved against a physical lattice threshold", "mechanistic_mind/world_engine/physical_effector.py", "EXPERIMENTAL_ONLY"),
        ("MECH-PRED-COMP", "predictive compression", "4.21", "bounded retention and retrieval of predictive structure", "mechanistic_mind/research/predictive_compression.py", "RESEARCH_ONLY"),
        ("MECH-MULTISCALE", "multi-scale prediction", "4.22", "bounded predictions at multiple scales", "mechanistic_mind/research/multiscale_prediction.py", "RESEARCH_ONLY"),
        ("MECH-PROSPECTIVE-COMP", "prospective composition", "4.23", "compose bounded prospective structure", "mechanistic_mind/research/prospective_composition.py", "RESEARCH_ONLY"),
        ("MECH-PASSIVE-FIELD", "passive background-field body coupling", "4.63", "position-dependent field perturbation of fatigue/hydration", "mechanistic_mind/world_engine/background_fields.py", "DEFAULT_ON, empirically negligible at tested materiality threshold"),
    ]
    mechanism_records = [{"mechanism_id": mid, "name": name, "introduced_in": "EXP-"+v, "purpose": purpose, "actual_equation": "See source implementation and equation provenance", "inputs": "See source", "outputs": "See source", "state": "BOUNDED where reported", "boundedness": "See source/report", "persistence": "See source/report", "plasticity": "See source/report", "default_status": status, "research_only_status": status, "cognition_visible_status": "No privileged semantic labels reported", "semantic_content": "NONE by design unless source says otherwise", "experiments_using": [e["experiment_id"] for e in experiments if vkey(e["version"]) >= vkey(v)], "claims_supported": [], "known_limitations": "Do not infer autonomous occurrence from structural presence.", "provenance": [src]} for mid, name, v, purpose, src, status in mechanisms]

    negatives = [
        ("NEG-4.39-001", "Does predicted future N modulate present N?", "Anticipatory sensorimotor modulation", "Not observed at matched current state", "Prediction did not re-enter present sensorimotor dynamics", "EXP-4.39"),
        ("NEG-4.42-001", "Does acquired internal structure autonomously alter motor distribution?", "Autonomous motor access", "Not supported in the diagnostic", "Separated acquired dynamics from motor access", "EXP-4.42"),
        ("NEG-4.43-001", "Does motor variation acquire distal consequence dependence?", "Distal consequence effect", "Null/negative outcome preserved by report", "Prevented semantic interpretation of motor variation", "EXP-4.43"),
        ("NEG-4.47-001", "Does endogenous activity reach the motor pathway?", "Endogenous motor access", "Not supported at the tested frontier", "Motivated dynamic-range diagnostics", "EXP-4.47"),
        ("NEG-4.61-001", "Does the controlled chain cross the unchanged physical threshold live?", "Live physical transition", "All regimes remained subthreshold", "Controlled structural support is not live operating-range support", "EXP-4.61"),
        ("NEG-4.62-001", "Is one bottleneck responsible for subthreshold activity?", "Single removable bottleneck", "No; multiple bounded stages jointly compress/redirect amplitude", "Ruled out a one-stage explanation", "EXP-4.62"),
        ("NEG-4.63-001", "Does existing passive ecology materially perturb body state under WAIT?", "Material body-range expansion", "No relative to basal empty-world control", "Existing passive ecology is structurally present but negligible in tested range", "EXP-4.63"),
    ]
    negative_records = [{"negative_id": nid, "question": q, "expected_possibility": exp, "actual_result": actual, "controls": "See experiment report and structured artifacts", "what_was_ruled_out": ruled, "what_was_not_ruled_out": "Other architectures, operating ranges, and untested conditions", "architectural_implication": ruled, "next_question_generated": "See frontier history", "provenance": [eid]} for nid,q,exp,actual,ruled,eid in negatives]
    open_q = [{"question_id": "Q-4.63-001", "question": "Which already-existing non-semantic WORLD→BODY path, if any, can materially perturb the exact body variables consumed by X under ordinary passive operation?", "generated_by_experiment": "EXP-4.63", "relevant_unsupported_edge": "EDGE-PASSIVE-ECOLOGY-BODY", "why_unresolved": "4.63 found negligible effects; 4.64 has audit artifacts but no surviving final report and is non-canonical.", "forbidden_shortcut": "Do not raise gain, lower threshold, tune ecology from Q, or add a desired edge.", "prerequisite": "Complete source-grounded path audit without changing runtime."}]
    architecture_states = [{"architecture_state_id": "ARCH-"+e["version"], "introduced_by": e["experiment_id"], "architecture_change": e["architecture_change"], "default_runtime_status": "UNKNOWN unless explicitly recorded", "experimental_status": "See experiment record", "provenance": e["provenance"][:5]} for e in experiments if e["architecture_change"] != "NOT_RECORDED"]

    dump("experiments.json", experiments); dump("claims.json", all_claims); dump("causal_edges.json", edge_records)
    dump("mechanisms.json", mechanism_records); dump("negative_results.json", negative_records); dump("open_questions.json", open_q)
    dump("provenance.json", provenance); dump("architecture_states.json", architecture_states)
    graph = {"nodes": ([{"id": e["experiment_id"], "type": "experiment"} for e in experiments] + [{"id": x["mechanism_id"], "type": "mechanism"} for x in mechanism_records] + [{"id": x["claim_id"], "type": "claim"} for x in all_claims] + [{"id": x["negative_id"], "type": "negative_result"} for x in negative_records]), "edges": []}
    for e in experiments:
        if e["predecessor"]: graph["edges"].append({"source": e["experiment_id"], "target": e["predecessor"], "type": "MOTIVATED_BY", "inference": True})
    for c in all_claims: graph["edges"].append({"source": c["experiment"], "target": c["claim_id"], "type": "SUPPORTS" if c["status"] == "SUPPORTED" else "DOES_NOT_SUPPORT"})
    dump("causal_graph.json", graph)

    for e in experiments:
        md = f"# {e['experiment_id']} — {e['title']}\n\n- Status: {e['status']}\n- Source completeness: {e['source_completeness']} ({e['source_completeness_reason']})\n- Predecessor: {e['predecessor'] or 'UNKNOWN'}\n- Successor: {e['successor'] or 'UNKNOWN'}\n\n## Why this experiment existed\n\nPrevious result: {e['previous_result']}\n\nUnresolved question: {e['unresolved_question']}\n\nThis experiment: {e['experiment_resolves']}\n\n## Architecture\n\n{e['architecture_change']}\n\n## Result\n\n{e['result']}\n\n## Limits\n\n{e['limitations']}\n\n## Next question\n\n{e['next_question']}\n\n## Provenance\n\n" + "\n".join(f"- `{p}`" for p in e["provenance"]) + "\n"
        (EXPDIR / (e["experiment_id"].lower().replace(".", "_") + ".md")).write_text(md, encoding="utf-8")

    timeline = ["# Human-readable research timeline", "", "This timeline separates implementation, architecture-enabled possibility, and empirical observation. UNKNOWN means the surviving canonical source did not record the field.", ""]
    for e in experiments:
        timeline += [f"## {e['experiment_id']} — {e['title']}", "", f"**QUESTION:** {e['scientific_question']}", "", f"**CHANGE:** {e['architecture_change']}", "", f"**TEST / RESULT:** {e['result']}", "", f"**WHAT IT MEANS:** {e['strongest_allowed_claim']}", "", "**WHAT IT DOES NOT MEAN:** structural presence or implementation guarantees are not empirical emergence; no anthropomorphic interpretation is licensed.", "", f"**NEXT QUESTION:** {e['next_question']}", ""]
    (KNOW / "timeline.md").write_text("\n".join(timeline), encoding="utf-8")

    readme = """# Mechanistic Mind research knowledge base

This directory is a **scientific provenance layer**. It is not runtime cognition, is not injected into the agent, and is not evidence by itself. It summarizes evidence produced by repository experiments and links every normalized record back to surviving sources.

Source priority is: final experiment reports; structured result JSON; preregistrations; source code; tests; Observer definitions; architecture documents; summaries/README. Conflicts are preserved rather than silently reconciled. `UNKNOWN`/`NOT_RECORDED` means the source did not support reconstruction. `PARTIAL` and `FRAGMENTARY` mark incomplete survival.

The central distinction is: (A) guaranteed by implementation, (B) enabled by architecture but not required, and (C) actually observed experimentally. Only C supports an empirical claim.

`structured/` is intended for audit and future research-director tooling. Nothing under `knowledge/` is imported by runtime code.
"""
    (KNOW / "README.md").write_text(readme, encoding="utf-8")
    (KNOW / "source_index.md").write_text("# Source index\n\n" + "\n".join(f"- **{e['experiment_id']}**: " + ", ".join(f"`{p}`" for p in e["provenance"][:12]) for e in experiments) + "\n", encoding="utf-8")
    (KNOW / "claim_registry.md").write_text("# Claim registry\n\nMachine-readable canonical registry: `structured/claims.json`. Claims are deduplicated per surviving source claim ID; later changes must append revision links rather than erase history.\n\n" + "\n".join(f"- **{c['claim_id']}** [{c['status']}] {c['wording']} — {c['experiment']}" for c in all_claims) + "\n", encoding="utf-8")
    (KNOW / "negative_results.md").write_text("# Negative and null results\n\nNegative results have equal evidential status to positive results.\n\n" + "\n\n".join(f"## {n['negative_id']}\n\n**Question:** {n['question']}\n\n**Observed:** {n['actual_result']}\n\n**Ruled out:** {n['what_was_ruled_out']}\n\n**Not ruled out:** {n['what_was_not_ruled_out']}\n\n**Provenance:** {', '.join(n['provenance'])}" for n in negative_records) + "\n", encoding="utf-8")
    frontier = """# Current frontier

- Latest completed canonical update: **4.63**.
- 4.64: **IN_PROGRESS / NOT_CANONICAL**. The documentation points to a missing `FINAL_REPORT.md`; only audit JSON survives. No 4.64 outcome is inferred.
- Current controlled structural chain: `BODY -> X -> N -> R/preact -> C -> D -> E -> Q -> lattice interface`.
- Current live operating-range limitation: body-derived live Q remained below the unchanged 0.60 transition threshold (4.61, reproduced by 4.62).
- Latest negative result: existing passive ecology did not materially alter body state relative to basal empty-world WAIT control (4.63).
- Current first unsupported arrow: `existing passive WORLD ecology -X-> material perturbation of BODY variables consumed by X`.
- Smallest next scientific question: identify whether any already-existing, ordinary, non-semantic WORLD→BODY path materially reaches X inputs without gain/threshold/ecology tuning.

Notation: `--->` controlled empirical support; `..->` structural only; `-X->` not supported; `???` not tested.

`WORLD passive ecology -X-> BODY ---> X ---> N ---> R/preact ---> C ---> D ---> E ---> Q ..-> lattice transition`

The downstream arrows are controlled/experimental support. They do not establish default-runtime autonomous occurrence.
"""
    (KNOW / "current_frontier.md").write_text(frontier, encoding="utf-8")
    (KNOW / "causal_graph.md").write_text("# Research trajectory graph\n\nCanonical machine-readable graph: `structured/causal_graph.json`. Edge types include MOTIVATED_BY, SUPPORTS, and DOES_NOT_SUPPORT. Inferred chronological motivation edges are explicitly marked `inference: true`.\n", encoding="utf-8")
    (KNOW / "causal_map.md").write_text("# Current causal map\n\nSee `current_frontier.md` and `structured/causal_edges.json`.\n\n`WORLD passive -X-> BODY ---> X ---> N ---> R/preact ---> C ---> D ---> E ---> Q ..-> threshold`\n\nControlled support must not be flattened into live or default-runtime support.\n", encoding="utf-8")
    (KNOW / "first_unsupported_arrow.md").write_text("""# First unsupported arrow history

- 4.39: `actual BODY ---> N ---> motor`; `predicted future N -X-> present N modulation`.
- 4.42–4.47: acquired internal structure existed; autonomous/endogenous access to motor remained unsupported, motivating access and range diagnostics.
- 4.50–4.60: staged controlled links progressively extended through physical transduction, representation compatibility, effector, and arbitrary fixed coupling.
- 4.61: controlled chain existed; `live internal dynamics -X-> unchanged physical threshold`.
- 4.62: no single bottleneck; the operating-range gap survived and was attributed to multi-stage bounded compression/redirection.
- 4.63: `existing passive ecology -X-> material BODY perturbation`; this became the upstream frontier.
- 4.64: path audit incomplete/non-canonical because the referenced final report is absent.
""", encoding="utf-8")
    (KNOW / "frontier_history.md").write_text("""# How the research frontier moved

## Prediction to present dynamics

Supported: actual body state modulated N and motor distribution. Unsupported: predicted future N did not independently modulate present N (4.39). The frontier moved toward explicit endogenous/acquired internal dynamics.

## Acquired dynamics to motor access

Acquired W/R structure could be produced under controlled conditions, but autonomous motor-distribution influence was not automatically implied. Diagnostics 4.42–4.49 isolated access and dynamic-range constraints.

## Controlled internal chain to physical action

4.50–4.60 progressively established controlled links from world/body perturbation through N/R/preactivation and fixed non-semantic coupling to E/Q and world-constrained movement. This was experimental capability, not ordinary autonomous operation.

## Live operating range

4.61 found live body-derived activity remained below the unchanged transition threshold. 4.62 found no single bottleneck; several bounded stages jointly compressed or redirected amplitude.

## Passive world access

4.63 found existing passive ecology structurally present but materially negligible at BODY under WAIT. The next frontier became the completeness and operating relevance of already-existing WORLD→BODY paths; 4.64 remains non-canonical in the surviving tree.
""", encoding="utf-8")
    (KNOW / "architecture_evolution.md").write_text("# Architecture evolution\n\nMachine-readable states: `structured/architecture_states.json`. Each change is recorded with its validating experiment and provenance. Experimental capability is never presented as ordinary default runtime.\n\n" + "\n".join(f"- **{a['introduced_by']}**: {a['architecture_change']} Default status: {a['default_runtime_status']}." for a in architecture_states) + "\n", encoding="utf-8")
    (KNOW / "default_runtime_history.md").write_text("# Default runtime history\n\nMechanism status is recorded in `structured/mechanisms.json`. N, W, R, X, C, E, and Q research paths must be treated as RESEARCH_ONLY or EXPERIMENTAL_ONLY unless a cited source explicitly records default enablement. Passive field coupling is DEFAULT_ON but was materially negligible in 4.63.\n", encoding="utf-8")
    (KNOW / "semantic_leak_history.md").write_text("# Semantic leak history\n\nResearch-side labels do not count as agent-visible semantics. For each experiment, consult `SEMANTIC_LEAKAGE_AUDIT.*` or `semantic_leakage_audit.*` in its provenance. Update 4.39 explicitly reported `leak = []`; late controlled physical-chain experiments report non-semantic couplings. Missing audits are UNKNOWN, never assumed clean.\n", encoding="utf-8")
    (KNOW / "experimental_principles.md").write_text("""# Experimental principles

The repository history supports these methodological constraints: hypotheses determine questions, not answers; negative results are evidence; implementation must be separated from observation; Observer ground truth must not enter cognition; storage and dynamics remain bounded; ablation is preferred to interpretation; structural paths differ from operating-range access; controlled support differs from autonomous occurrence; numeric channels do not justify semantic meaning; and behavior is not called adaptive without consequence-dependent change.

Current methodology further requires frozen parameters where preregistered, no tuning to force a phenomenon, provenance-preserving compression, and conservative claim language.
""", encoding="utf-8")
    (KNOW / "terminology.md").write_text("""# Terminology

- **BODY:** objective bounded physiological state; not a self-representation.
- **X:** generic physical transduction of selected BODY variables.
- **N:** intrinsic bounded sensorimotor dynamics.
- **W:** acquired internal coupling/dynamics.
- **R / preact:** acquired projection and generic motor preactivation.
- **C / D:** fixed non-semantic coupling and downstream drive used in controlled physical-path tests.
- **E / Q:** bounded physical effector and its physical tendency.
- **Observer / ground truth:** research-side measurement unavailable to cognition unless explicitly exposed.
- **bounded cognition:** finite storage, retrieval work, and/or state ranges.
- **acquired structure:** parameter/state relation changed by experience; this alone does not imply use.
- **structural support:** code path exists. **Controlled support:** causal effect appears under controlled intervention. **Live support:** effect occurs in ordinary live dynamics. **Operating range:** magnitudes actually reached under the tested regime.
- **passive ecology:** world dynamics/coupling under WAIT without semantic USE/MOVE selection.
- **consequence learning:** acquired change depends on experienced consequences; not a synonym for reward or desire.
""", encoding="utf-8")
    (KNOW / "equation_provenance.md").write_text("""# Equation provenance

- X absolute mode: `X' = clip(0.70 X + 0.25 (B - 0.5), -1, 1)`; source `mechanistic_mind/body/physical_transduction.py`; audited in 4.64 artifacts.
- Passive field coupling: `fatigue += 0.0002*T`; `hydration += -0.0001*H`; source `mechanistic_mind/world_engine/background_fields.py`; tested at 4.63 and audited in 4.64 artifacts.
- Physical threshold: 0.60 in 4.61/4.62 reports; live maxima R0 0.0659, R1 0.4629, R3 0.4622 in 4.62.

For historical equations not recoverable from versioned source/result artifacts, use `HISTORICAL_EQUATION_NOT_RECOVERABLE`; current code is not silently projected backward.
""", encoding="utf-8")
    (KNOW / "open_questions.md").write_text("# Open questions\n\n" + "\n\n".join(f"## {q['question_id']}\n\n{q['question']}\n\nGenerated by: {q['generated_by_experiment']}. Why unresolved: {q['why_unresolved']} Forbidden shortcut: {q['forbidden_shortcut']}" for q in open_q) + "\n", encoding="utf-8")
    (KNOW / "forbidden_shortcuts.md").write_text("""# Forbidden shortcuts

- Raising gain or lowering the physical threshold merely to cross it would replace an operating-range finding with parameter forcing.
- Selecting C after observing behavior would invalidate the arbitrary-coupling control.
- Encoding curiosity, desire, reward, or semantic motor meaning would make the target phenomenon implementation-guaranteed.
- Leaking Observer ground truth would collapse the distinction between objective measurement and accessible state.
- Tuning ecology based on Q would create a circular downstream-informed world intervention.
- Connecting W/R simply because an edge is desired would turn a scientific question into architecture by fiat.
""", encoding="utf-8")
    (KNOW / "contradictions_and_revisions.md").write_text("""# Contradictions and revisions

- Structural presence was repeatedly narrowed by later operating-range evidence: controlled downstream support through Q (4.60) did not imply live threshold crossing (4.61–4.62).
- Existing passive field coupling was structurally present/default-on, but 4.63 qualified it as materially negligible in the tested regime.
- 4.64 documentation claims a final report exists, while the result directory lacks it. Current status is therefore non-canonical/partial, and no outcome is reconstructed.
- References to earlier canonical results are not counted as reproductions unless the later report explicitly reran the relevant test; 4.62 explicitly reproduced 4.61 Outcome B.
""", encoding="utf-8")
    (KNOW / "reproduction_history.md").write_text("# Reproduction history\n\n- 4.62 explicitly reproduced 4.61 Outcome B, including subthreshold Q maxima and zero hops.\n- Other mentions of canonical status are treated as references unless the report documents a rerun.\n", encoding="utf-8")
    (KNOW / "null_results_that_changed_direction.md").write_text("""# Null results that changed direction

- **Temptation:** call learned prediction anticipatory control. **4.39:** matched-state prediction and ablation were identical. **Shortcut rejected:** directly feed predicted N into present N. **New question:** what minimal endogenous/reinstatement mechanism can be tested?
- **Temptation:** infer motor access from acquired internal structure. **4.42/4.47:** autonomous/endogenous access was not supported. **Shortcut rejected:** wire the desired edge. **New question:** isolate access and dynamic range.
- **Temptation:** infer live physical action from a controlled chain. **4.61:** live activity stayed subthreshold. **Shortcut rejected:** raise gain/lower threshold. **New question:** locate the amplitude budget.
- **Temptation:** blame one bottleneck. **4.62:** no single bottleneck. **Shortcut rejected:** tune one stage. **New question:** examine upstream ordinary physical range.
- **Temptation:** assume passive ecology materially drives BODY because coupling exists. **4.63:** no material effect. **Shortcut rejected:** tune ecology from Q. **New question:** audit existing WORLD→BODY paths.
""", encoding="utf-8")
    counts = Counter(e["source_completeness"] for e in experiments)
    build = f"""# Knowledge-base build report

1. Experiments discovered: **{len(experiments)}** result-directory experiment records.
2. Earliest recoverable update experiment: **{experiments[0]['experiment_id']}** ({experiments[0]['title']}). Pre-update release experiments remain indexed by repository docs/results but are not falsely renumbered.
3. Latest completed canonical experiment on the requested physical frontier: **EXP-4.63**.
4. In-progress/non-canonical: **EXP-4.64** (audit JSON only; referenced final report missing).
5. Experiment records: **{len(experiments)}**.
6. Normalized source claims: **{len(all_claims)}**.
7. Causal edges: **{len(edge_records)}**.
8. Mechanisms: **{len(mechanism_records)}**.
9. Curated negative/null results: **{len(negative_records)}**.
10. Current evidence-generated open questions: **{len(open_q)}**.
11. Architecture revisions recorded: **{len(architecture_states)}**.
12. Source completeness: **{dict(counts)}**.
13. Contradictions/revisions: structural-vs-live qualification; passive field materiality qualification; missing 4.64 final report; see `contradictions_and_revisions.md`.
14. Missing evidence: some early result directories lack final reports/claim registries; dates and several preregistration fields are NOT_RECORDED.
15. Current controlled chain: `BODY -> X -> N -> R/preact -> C -> D -> E -> Q -> lattice interface`.
16. Current first unsupported arrow: `existing passive WORLD ecology -X-> material BODY perturbation`.
17. Operating-range limitation: live Q remained below unchanged 0.60 threshold; multi-stage bounded compression/redirection.
18. Smallest question: whether an already-existing ordinary non-semantic WORLD→BODY path materially reaches X inputs.
19. `knowledge/` isolation: checked by validator; no runtime imports expected.
20. Runtime changed: **NO**.
21. Tests changed: **NO**.
22. Validator: run `python3 tools/validate_knowledge_base.py`.
23. `.git` status: directory present, but `git status` reports that this is not a Git repository; no usable metadata was present.
24. Git actions performed: **NONE**.
"""
    (KNOW / "BUILD_REPORT.md").write_text(build, encoding="utf-8")


if __name__ == "__main__":
    main()
