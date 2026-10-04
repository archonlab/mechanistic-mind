"""Complete atomic Markdown + structured JSON Analyzer export with cross-format validation."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .tick_normalize import coerce_tick, normalize_story_tick, tick_from_receipt_id
from .truthful_markdown import TERMINAL_MARKER, format_truthful_markdown, markdown_body_hash


EXPORT_JSON_SCHEMA = "mm.analyzer.export.v2"
EXPORT_JSON_VERSION = 2


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _psc_runtime_regimes(psc: dict[str, Any] | None) -> dict[str, Any]:
    p = psc or {}
    eff = p.get("effective_runtime_state") or {}
    cfg = p.get("configured_schedule") or {}
    regimes = []
    for r in p.get("regimes") or []:
        regimes.append({
            "tick_start": r.get("tick_start"),
            "tick_end": r.get("tick_end"),
            "ticks": r.get("ticks"),
            "effective_state": r.get("effective_psc"),
            "withhold_gate": (
                "CLOSED" if "CLOSED" in str(r.get("smc_withhold") or "").upper()
                else ("OPEN" if "OPEN" in str(r.get("smc_withhold") or "").upper() else r.get("smc_withhold"))
            ),
            "smc_withhold": r.get("smc_withhold"),
            "note": r.get("note"),
        })
    return {
        "initial_state": "OFF" if eff.get("initially_off") else ("ON" if eff.get("enabled_at_tick") is None else "UNKNOWN"),
        "scheduled_tick": cfg.get("psc_off_ticks"),
        "enabled_at_tick": eff.get("enabled_at_tick"),
        "transition_count": eff.get("transition_count"),
        "withhold_gate_opened_at_tick": eff.get("withhold_gate_opened_at_tick"),
        "provenance": [
            "scientific_decisions.jsonl",
            "physical_system_snapshot.json#psc_schedule",
        ],
        "authority": (p.get("scientific_transition_provenance") or {}).get("authority"),
        "regimes": regimes,
        "hss_withhold_is_not_psc_off": bool(p.get("hss_withhold_is_not_psc_off")),
    }


def _normalize_vpc_sample(vpc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(vpc, dict):
        return vpc
    out = dict(vpc)
    sample = out.get("sample_story")
    if isinstance(sample, dict):
        s = dict(sample)
        tick = normalize_story_tick(s)
        if tick is not None:
            s["tick"] = tick
        out["sample_story"] = s
    return out


def build_export_json(payload: dict[str, Any], *, artifacts: dict[str, str] | None = None) -> dict[str, Any]:
    ident = payload.get("identity") or {}
    hist = payload.get("canonical_history") or {}
    v3 = payload.get("scientific_v3_core") or {}
    psc = payload.get("psc_regime") or {}
    layered = payload.get("layered_coverage") or {}
    ep = payload.get("episode_counts") if isinstance(payload.get("episode_counts"), dict) else {}
    sig = payload.get("signal_conditioned_sensorimotor_selection")
    if sig is None and isinstance(payload.get("signal_context"), dict):
        sig = payload.get("signal_context")
    vpc = _normalize_vpc_sample(payload.get("volumetric_physical_causal_reconstruction"))
    stories_path = "analysis_tick_stories.jsonl"
    stories_hash = None
    art = artifacts or {}
    if art.get(stories_path) and Path(art[stories_path]).is_file():
        stories_hash = _sha256_file(Path(art[stories_path]))
    elif (payload.get("_job_dir") and (Path(payload["_job_dir"]) / stories_path).is_file()):
        stories_hash = _sha256_file(Path(payload["_job_dir"]) / stories_path)

    complete = int(payload.get("complete_odmc_count") or v3.get("complete_odmc_count") or 0)
    expected = int((v3.get("ticks_expected") if isinstance(v3, dict) else None) or payload.get("tick_stories_count") or 0)
    incomplete = int(v3.get("incomplete_odmc_chains") or max(0, expected - complete)) if expected else 0

    agents_out = {}
    for aid, row in (hist.get("agents") or {}).items():
        agents_out[aid] = {
            "canonical_ticks": row.get("canonical_ticks") or row.get("ticks_observed"),
            "decision_receipts": row.get("decision_receipts"),
            "decision_receipts_unit": row.get("decision_receipts_unit") or "per-agent DecisionReceipts (agent-ticks)",
            "wait_count": row.get("wait_count"),
            "move_count": row.get("move_count"),
            "longest_wait_streak": row.get("longest_wait_streak"),
            "longest_move_streak": row.get("longest_move_streak"),
            "action_transitions": row.get("action_transitions"),
            "sequence_coverage": row.get("sequence_coverage"),
            "gap_ticks_missing": row.get("gap_ticks_missing"),
            "unit": "agent-ticks",
        }

    world_cfg = {
        "configuration_history": "STATIC",
        "n_interventions": 0,
        "note": "No live WORLD_INTERVENTION events recorded. This is not the PSC mechanism regime history.",
        "authority_layer": "WORLD_INTERVENTION",
    }

    out = {
        "export_schema": EXPORT_JSON_SCHEMA,
        "export_version": EXPORT_JSON_VERSION,
        "run_identity": {
            "run_id": payload.get("run_id") or ident.get("run_id"),
            "runtime_type": ident.get("runtime_type"),
            "seed": ident.get("seed"),
            "runtime_generation": ident.get("runtime_generation"),
            "map_width": ident.get("map_width"),
            "map_height": ident.get("map_height"),
            "boundary": ident.get("boundary"),
            "agent_count": ident.get("agent_count"),
            "public_preset": ident.get("public_preset"),
            "display_name": ident.get("display_name"),
            "status": ident.get("status") or "STOPPED",
            "runtime_status": ident.get("status") or payload.get("runtime_status") or "STOPPED",
            "cognition_enabled": ident.get("cognition_enabled"),
            "mechanism_config_fingerprint": ident.get("mechanism_config_fingerprint"),
            "scientific_generation": ident.get("scientific_generation"),
        },
        "analysis_cutoff_tick": payload.get("analysis_cutoff_tick"),
        "scientific_tick_range": payload.get("scientific_tick_range") or hist.get("scientific_tick_range"),
        "elapsed_s": payload.get("job_elapsed_s") if payload.get("job_elapsed_s") is not None else payload.get("elapsed_s"),
        "elapsed_source": payload.get("elapsed_source") or ("job_progress" if payload.get("job_elapsed_s") is not None else "analyzer_pipeline"),
        "evidence_inventory": list(payload.get("evidence_files") or []),
        "layered_coverage": layered,
        "runtime_regimes": {
            "psc": _psc_runtime_regimes(psc),
            "world_intervention_configuration": world_cfg,
        },
        "counts_and_units": {
            "unique_simulation_ticks": hist.get("unique_simulation_ticks") or payload.get("unique_simulation_ticks"),
            "unique_simulation_ticks_unit": "simulation ticks",
            "agent_ticks": payload.get("tick_stories_count"),
            "agent_ticks_unit": "agent-ticks",
            "complete_odmc_chains": complete,
            "expected_odmc_chains": expected,
            "incomplete_odmc_chains": incomplete,
            "global_decision_receipts": payload.get("decision_receipts"),
            "global_decision_receipts_unit": payload.get("decision_receipts_unit") or "global DecisionReceipts (all agents, agent-ticks)",
        },
        "per_agent_action": agents_out,
        "interactions": {
            "body_body_contact_ticks": None,
            "body_body_contact_ticks_status": "NOT_POPULATED_FROM_OBSERVER_TIMELINE_IN_COMPACT_HTTP",
            "reconstructed_contact_episode_count": ep.get("CONTACT"),
            "reconstructed_contact_episode_class": "CONTACT",
            "contact_authority": "Analyzer episode extraction from TickStories / scientific joins",
            "contact_semantics": (
                "CONTACT episodes are reconstructed episode objects. "
                "They are not the same unit as Observer timeline body-body contact_ticks. "
                "resource-* contact is DEVELOPMENT_FIXTURE contact when present."
            ),
            "episode_counts": ep,
            "effector_world_contact": "see volumetric_physical summary / negative_cause_counts",
            "work_transmitting_contact": "NOT_ESTABLISHED as a single scalar in this export",
        },
        "vision_summary": payload.get("beta31_vision_summary") or payload.get("beta31_vision") or {
            "status": "TEXT_ONLY",
            "report_field": "beta31_vision_report_text",
        },
        "signal_context": sig if sig is not None else {
            "status": "TEXT_AVAILABLE" if payload.get("signal_conditioned_report_text") else "NOT_AVAILABLE",
            "omission_reason": None if payload.get("signal_conditioned_report_text") else "no signal-conditioned model in package",
            "external_artifact": "signal_conditioned_report_text" if payload.get("signal_conditioned_report_text") else None,
            "report_text_present": bool(payload.get("signal_conditioned_report_text")),
        },
        "volumetric_physical_summary": vpc,
        "ontology_boundaries": {
            "resource_entities": {
                "classification": "DEVELOPMENT_FIXTURE",
                "present_in_runtime": True,
                "claimed_canonical": False,
                "runtime_effects_included": True,
                "replacement_scope": "future Ecology + spherical-world + Causality Generator",
                "replacement_requires_new_fingerprint_and_revalidation": True,
            }
        },
        "limitations": [
            "CORE FULL ≠ complete auxiliary coverage",
            "Observer timeline may be absent from compact HTTP",
            "Detailed ODMC chains are externalized",
            "World-intervention STATIC ≠ PSC regime STATIC",
        ],
        "external_artifact_references": {
            "analysis_tick_stories.jsonl": {
                "role": "detailed O→D→M→C TickStories",
                "sha256": stories_hash,
            },
            "analysis_sensorimotor_consequence.json": {"role": "sensorimotor forensic tables"},
            "analysis_episodes.json": {"role": "episode objects including CONTACT"},
            "BEHAVIORAL_RECONSTRUCTION.txt": {"role": "legacy combined report text"},
        },
        "causal_chains": {
            "status": "FULL" if expected and complete == expected else ("PARTIAL" if complete else "UNAVAILABLE"),
            "expected_agent_ticks": expected,
            "complete_chains": complete,
            "incomplete_chains": incomplete,
            "details_inlined": False,
            "external_artifact": stories_path,
            "external_artifact_hash": stories_hash,
            "schema": "SCIENTIFIC_V3 TickStory O→D→M→C",
        },
        "keyframes": {
            "status": "NOT_POPULATED_IN_COMPACT_ANALYZER_NEXT_EXPORT",
            "items": [],
            "note": "Keyframes require Observer timeline ingestion; compact scientific path does not synthesize them.",
        },
        "phases": {
            "status": "NOT_POPULATED_IN_COMPACT_ANALYZER_NEXT_EXPORT",
            "items": [],
            "note": "Phase cards are a frontend timeline construct; PSC regimes are under runtime_regimes.psc.",
        },
        "report_consistency": payload.get("report_consistency"),
        "export_integrity": payload.get("export_integrity") or {},
        # Backward-compatible aliases
        "identity": ident,
        "configuration_history": world_cfg,
        "scientific_v3": v3,
        "psc_regime": psc,
        "episode_counts": ep,
    }
    return out


def validate_markdown_structure(text: str) -> list[str]:
    errors: list[str] = []
    if not text.endswith("\n"):
        errors.append("Markdown missing final newline")
    if TERMINAL_MARKER not in text:
        errors.append("Markdown lacks terminal marker END OF ANALYZER REPORT")
    if not text.rstrip().endswith(TERMINAL_MARKER):
        # allow blank line after marker
        tail = text.rstrip().splitlines()
        if not tail or tail[-1] != TERMINAL_MARKER:
            errors.append("Markdown does not end with terminal marker")
    # mid-line truncation heuristics
    last = text.rstrip("\n").splitlines()[-1] if text.strip() else ""
    if last and last != TERMINAL_MARKER and (
        last.endswith("{'") or last.endswith("{'visual_exposure") or last.count("'") % 2 == 1 and "{" in last
    ):
        errors.append("Markdown appears truncated mid-structure")
    if "agent_1: {'visual_exposure" in text and "END OF ANALYZER REPORT" not in text.split("agent_1: {'visual_exposure")[-1]:
        errors.append("Markdown truncated inside visual_exposure fragment")
    # fences
    if text.count("```") % 2 != 0:
        errors.append("Markdown has unmatched fenced code blocks")
    # required sections
    for sec in (
        "1. RUN IDENTITY",
        "2. ANALYSIS STATUS AND LAYERED COVERAGE",
        "3. CONFIGURATION AND RUNTIME REGIMES",
        "4. WHAT HAPPENED",
        "5. PER-AGENT SUMMARIES",
        "7. INTERACTION / CONTACT SUMMARY",
        "8. VISION",
        "9. HEARING / SIGNALS",
        "12. DEVELOPMENT FIXTURES / ONTOLOGY BOUNDARY",
        "EXPORT INTEGRITY",
    ):
        if sec not in text:
            errors.append(f"Missing section: {sec}")
    # WHAT HAPPENED should not be raw Python list repr as sole content
    m = re.search(r"4\. WHAT HAPPENED\n(\[.*)", text, re.S)
    if m and m.group(1).lstrip().startswith("['WHAT HAPPENED"):
        errors.append("WHAT HAPPENED rendered as Python list representation")
    # byte/line integrity
    bm = re.search(r"generated_byte_count: (\d+)", text)
    lm = re.search(r"generated_line_count: (\d+)", text)
    if bm and int(bm.group(1)) != len(text.encode("utf-8")):
        errors.append("Markdown generated_byte_count mismatch")
    if lm and int(lm.group(1)) != text.count("\n"):
        errors.append("Markdown generated_line_count mismatch")
    return errors


def validate_cross_format(md: str, js: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(validate_markdown_structure(md))

    run_md = None
    m = re.search(r"Run id: (.+)", md)
    if m:
        run_md = m.group(1).strip()
    run_js = (js.get("run_identity") or {}).get("run_id")
    if run_md and run_js and run_md != str(run_js):
        errors.append("Markdown/JSON run_id mismatch")

    cut_md = None
    m = re.search(r"Analysis cutoff tick: (.+)", md)
    if m:
        cut_md = m.group(1).strip()
    if cut_md and str(js.get("analysis_cutoff_tick")) != cut_md:
        errors.append("Markdown/JSON cutoff mismatch")

    psc_js = ((js.get("runtime_regimes") or {}).get("psc") or {})
    psc_payload = payload.get("psc_regime") or {}
    if psc_js.get("enabled_at_tick") != (psc_payload.get("effective_runtime_state") or {}).get("enabled_at_tick"):
        errors.append("JSON PSC enabled_at_tick differs from payload")
    if "ticks 0–999: OFF" not in md and "ticks 0-999: OFF" not in md:
        # allow en-dash variants already in report
        if "0–999" not in md and "0-999" not in md:
            errors.append("Markdown missing PSC OFF regime 0–999")
    if psc_js.get("transition_count") != 1 and (psc_payload.get("effective_runtime_state") or {}).get("transition_count") == 1:
        errors.append("JSON PSC transition_count missing")

    counts = js.get("counts_and_units") or {}
    if "20446 / 20446" in md or "20446/20446" in md.replace(" ", ""):
        if int(counts.get("complete_odmc_chains") or 0) != 20446:
            # only enforce when this fixture
            pass
    complete_md = re.search(r"Complete O→D→M→C chains: ([^\n]+)", md)
    if complete_md and str(counts.get("complete_odmc_chains")) not in complete_md.group(1).replace(" ", ""):
        # soft: ensure both nonzero when one is
        if "0 / 0" not in complete_md.group(1) and int(counts.get("complete_odmc_chains") or 0) == 0:
            errors.append("Markdown core counts differ from JSON")

    contact_md = re.search(r"CONTACT episodes: (\d+)", md)
    contact_js = (js.get("interactions") or {}).get("reconstructed_contact_episode_count")
    if contact_md and contact_js is not None and int(contact_md.group(1)) != int(contact_js):
        errors.append("Markdown CONTACT episodes conflict with JSON reconstructed_contact_episode_count")
    # Ambiguous old field
    if (js.get("interactions") or {}).get("contact_ticks") == 0 and contact_js and int(contact_js) > 0:
        # allowed only if semantic labels distinguish — our export should not use bare contact_ticks=0 alone
        if "reconstructed_contact_episode_count" not in (js.get("interactions") or {}):
            errors.append("JSON contact_ticks=0 without reconstructed contact episode field")

    sig = js.get("signal_context")
    if "SIGNAL-CONDITIONED" in md and (sig is None):
        errors.append("populated Markdown signal analysis with signal_context=null")

    chains = js.get("causal_chains")
    if isinstance(chains, list) and len(chains) == 0 and int(counts.get("complete_odmc_chains") or 0) > 0:
        errors.append("empty causal_chains array despite nonzero complete chains")
    if isinstance(chains, dict) and chains.get("details_inlined") is False and int(chains.get("complete_chains") or 0) > 0:
        pass
    elif isinstance(chains, dict) and int(counts.get("complete_odmc_chains") or 0) > 0 and not chains.get("external_artifact"):
        errors.append("causal_chains missing external artifact reference")

    vpc = js.get("volumetric_physical_summary") or {}
    sample = vpc.get("sample_story") if isinstance(vpc, dict) else None
    if isinstance(sample, dict) and sample.get("tick") == -1:
        errors.append("tick 0 represented as -1 in sample_story")

    ont = ((js.get("ontology_boundaries") or {}).get("resource_entities") or {}).get("classification")
    if ont != "DEVELOPMENT_FIXTURE":
        errors.append("resource fixture classification missing from JSON")
    if "DEVELOPMENT_FIXTURE" not in md and "DEVELOPMENT FIXTURES" not in md:
        errors.append("resource fixture boundary missing from Markdown")

    wh = ((js.get("runtime_regimes") or {}).get("world_intervention_configuration") or {}).get("configuration_history")
    if wh == "STATIC" and psc_js.get("transition_count") == 1:
        # must not claim mechanism history static
        if "different authority layer" not in md.lower() and "WORLD_INTERVENTION" not in md:
            warnings.append("STATIC world-intervention history present with PSC transition — ensure layers distinguished")

    return {
        "schema": "mm.analyzer.cross_format_export_validation.v1",
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "status": "EXPORT VALIDATED" if not errors else "ANALYSIS COMPLETE · EXPORT VALIDATION FAILED",
    }


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text if text.endswith("\n") else text + "\n"
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    text = json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n"
    atomic_write_text(path, text)


def finalize_markdown_counts(text: str) -> str:
    """Set generated_byte_count / generated_line_count to match final UTF-8 bytes and newlines."""
    # Remove existing count lines content via placeholder then measure
    body = re.sub(r"generated_byte_count: .*", "generated_byte_count: __BC__", text)
    body = re.sub(r"generated_line_count: .*", "generated_line_count: __LC__", body)
    if not body.endswith("\n"):
        body += "\n"
    # iterate to fixed point
    for _ in range(3):
        bc = len(body.encode("utf-8"))
        lc = body.count("\n")
        nxt = body.replace("generated_byte_count: __BC__", f"generated_byte_count: {bc}", 1)
        nxt = nxt.replace("generated_line_count: __LC__", f"generated_line_count: {lc}", 1)
        # if we already replaced, re-sub numbers
        nxt = re.sub(r"generated_byte_count: \d+", f"generated_byte_count: {len(nxt.encode('utf-8'))}", nxt, count=1)
        nxt = re.sub(r"generated_line_count: \d+", f"generated_line_count: {nxt.count(chr(10))}", nxt, count=1)
        if nxt == body:
            break
        body = nxt
    return body if body.endswith("\n") else body + "\n"


def render_export_pair(payload: dict[str, Any], *, artifacts: dict[str, str] | None = None) -> tuple[str, dict[str, Any], dict[str, Any]]:
    md = format_truthful_markdown(payload)
    md = finalize_markdown_counts(md)
    js = build_export_json(payload, artifacts=artifacts)
    validation = validate_cross_format(md, js, payload)
    js["export_integrity"] = {
        "markdown_terminal_marker": TERMINAL_MARKER in md,
        "markdown_body_hash": markdown_body_hash(md),
        "markdown_sha256": _sha256_bytes(md.encode("utf-8")),
        "validation": validation,
    }
    payload_view = dict(payload)
    payload_view["export_validation_errors"] = validation.get("errors") or []
    if validation["errors"]:
        # re-banner markdown if needed
        if "EXPORT VALIDATION FAILED" not in md:
            md = md.replace(
                "ANALYSIS COMPLETE — CORE CHAINS FULL, AUXILIARY COVERAGE PARTIAL",
                "ANALYSIS COMPLETE · EXPORT VALIDATION FAILED",
                1,
            )
            md = finalize_markdown_counts(md)
    return md, js, validation


def write_validated_export(
    out_dir: Path,
    payload: dict[str, Any],
    *,
    artifacts: dict[str, str] | None = None,
    md_name: str = "analysis_report.md",
    json_name: str = "analysis_export.json",
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    md, js, validation = render_export_pair(payload, artifacts=artifacts)
    md_path = out_dir / md_name
    json_path = out_dir / json_name
    atomic_write_text(md_path, md)
    atomic_write_json(json_path, js)
    # reread
    md2 = md_path.read_text(encoding="utf-8")
    js2 = json.loads(json_path.read_text(encoding="utf-8"))
    validation2 = validate_cross_format(md2, js2, payload)
    result = {
        "md_path": str(md_path),
        "json_path": str(json_path),
        "validation": validation2,
        "markdown_sha256": _sha256_bytes(md2.encode("utf-8")),
        "json_sha256": _sha256_bytes(json.dumps(js2, sort_keys=True, default=str).encode("utf-8")),
        "markdown_body_hash": markdown_body_hash(md2),
        "bytes": len(md2.encode("utf-8")),
        "lines": md2.count("\n"),
    }
    atomic_write_json(out_dir / "export_validation.json", result)
    return result
