"""Layered, count-unit-aware Analyzer Markdown — complete downloadable report.

UI preview may be bounded separately. This formatter must not mid-cut sections.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


REPORT_SCHEMA = "mm.analyzer.truthful_markdown.v2"
TERMINAL_MARKER = "END OF ANALYZER REPORT"


def _show(v: Any) -> str:
    if v is None or v == "":
        return "NOT AVAILABLE"
    return str(v)


def _format_what_happened(raw: Any) -> list[str]:
    if raw is None:
        return ["NOT AVAILABLE"]
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("[") and ("WHAT HAPPENED" in text or text.startswith("['")):
            # Accidental str(list) — fall through to lines
            try:
                import ast

                parsed = ast.literal_eval(text)
                if isinstance(parsed, list):
                    return _format_what_happened(parsed)
            except Exception:
                pass
        return [ln for ln in text.splitlines() if ln.strip()] or ["NOT AVAILABLE"]
    if isinstance(raw, (list, tuple)):
        out: list[str] = []
        for item in raw:
            s = str(item).strip()
            if not s:
                continue
            if s.startswith("WHAT HAPPENED"):
                continue
            if s.startswith("- "):
                out.append(s)
            else:
                out.append(f"- {s}")
        return out or ["NOT AVAILABLE"]
    return [f"- {_show(raw)}"]


def _format_episode_counts(counts: Any) -> list[str]:
    if not isinstance(counts, dict) or not counts:
        return [f"Episode counts: {_show(counts)}"]
    lines = [
        "Episode counts (Analyzer reconstruction units = episodes):",
        f"- CONTACT episodes: {_show(counts.get('CONTACT'))}",
        f"- APPROACH episodes: {_show(counts.get('APPROACH'))}",
        f"- WITHDRAWAL episodes: {_show(counts.get('WITHDRAWAL'))}",
        f"- WAIT_PERIOD episodes: {_show(counts.get('WAIT_PERIOD'))}",
        f"- MOTOR_REVERSAL episodes: {_show(counts.get('MOTOR_REVERSAL'))}",
        f"- VISUAL_EXPOSURE episodes: {_show(counts.get('VISUAL_EXPOSURE'))}",
        f"- SIGNAL_EXPOSURE episodes: {_show(counts.get('SIGNAL_EXPOSURE'))}",
        "",
        "Contact semantics:",
        "- CONTACT episodes = reconstructed CONTACT episode objects from TickStories.",
        "- These are not identical to Observer timeline body-body contact_ticks.",
        "- resource-* contact (if any) is DEVELOPMENT_FIXTURE contact, not a separate food ontology.",
        "",
        "Full episode_counts JSON:",
        "```json",
        json.dumps(counts, sort_keys=True),
        "```",
    ]
    return lines


def format_truthful_markdown(payload: dict[str, Any]) -> str:
    ident = payload.get("identity") or {}
    layered = payload.get("layered_coverage") or {}
    cons = payload.get("report_consistency") or {}
    hist = payload.get("canonical_history") or {}
    v3 = payload.get("scientific_v3_core") or {}
    files = payload.get("evidence_files") or []
    files_s = ", ".join(str(x) for x in files) if files else "export manifest did not retain filenames (streams were consumed)"
    unique = hist.get("unique_simulation_ticks") or payload.get("unique_simulation_ticks")
    rng = payload.get("scientific_tick_range") or hist.get("scientific_tick_range") or [None, None]
    banner = layered.get("banner") or "ANALYSIS COMPLETE"
    export_errors = list(cons.get("errors") or [])
    if payload.get("export_validation_errors"):
        export_errors = list(export_errors) + list(payload.get("export_validation_errors") or [])
    if export_errors:
        banner = "ANALYSIS COMPLETE · EXPORT VALIDATION FAILED"
    layers = layered.get("layers") or {}
    elapsed = payload.get("job_elapsed_s")
    if elapsed is None:
        elapsed = payload.get("elapsed_s")

    lines: list[str] = [
        "MECHANISTIC MIND — RUN ANALYSIS",
        "================================",
        f"report_schema: {REPORT_SCHEMA}",
        "",
        "1. RUN IDENTITY",
        f"Run id: {_show(payload.get('run_id') or ident.get('run_id'))}",
        f"Runtime: {_show(ident.get('runtime_type'))}",
        f"Seed: {_show(ident.get('seed'))}",
        f"Generation (runtime_generation): {_show(ident.get('runtime_generation'))}",
        f"Map: {_show(ident.get('map_width'))}×{_show(ident.get('map_height'))} {_show(ident.get('boundary'))}",
        f"Agent count: {_show(ident.get('agent_count'))}",
        f"Public preset: {_show(ident.get('public_preset'))}",
        f"Display name: {_show(ident.get('display_name'))}",
        f"Status: {_show(ident.get('status'))}",
        f"Cognition enabled: {_show(ident.get('cognition_enabled'))}",
        f"Mechanism config fingerprint: {_show(ident.get('mechanism_config_fingerprint'))}",
        f"Scientific generation (package/docs, not a per-run JSON field): {_show(ident.get('scientific_generation'))}",
        "",
        "2. ANALYSIS STATUS AND LAYERED COVERAGE",
        banner,
        f"Analyzer version: {_show(payload.get('analyzer_version') or '1.2.0')}",
        f"Analysis cutoff tick: {_show(payload.get('analysis_cutoff_tick'))}",
        f"Scientific tick range: {_show(rng[0] if rng else None)}–{_show(rng[1] if rng else None)}",
        f"Unique simulation ticks: {_show(unique)} (unit: simulation ticks)",
        f"Tick stories / agent-ticks: {_show(payload.get('tick_stories_count'))} (unit: agent-ticks)",
        f"Complete O→D→M→C chains: {_show(payload.get('complete_odmc'))} (unit: agent-ticks)",
        f"Global DecisionReceipts: {_show(payload.get('decision_receipts'))} ({_show(payload.get('decision_receipts_unit') or 'global receipts')})",
        f"Evidence files: {files_s}",
        f"Report consistency: {_show(cons.get('status'))}",
        f"Consistency errors: {len(cons.get('errors') or [])}",
        f"Consistency warnings: {len(cons.get('warnings') or [])}",
        f"Export integrity errors: {len(payload.get('export_validation_errors') or [])}",
        "",
        "CORE CAUSAL CHAIN COVERAGE",
        f"- O→D→M→C: {_show((layers.get('CORE_CAUSAL_CHAIN_COVERAGE') or {}).get('status'))}",
        f"- complete chains: {_show((layers.get('CORE_CAUSAL_CHAIN_COVERAGE') or {}).get('complete_chains'))}/{_show((layers.get('CORE_CAUSAL_CHAIN_COVERAGE') or {}).get('expected_chains'))}",
        f"RUN METADATA COVERAGE: {_show(layers.get('RUN_METADATA_COVERAGE'))}",
        f"WORLD/PHYSICAL COVERAGE: {_show(layers.get('WORLD_PHYSICAL_COVERAGE'))}",
        f"VISION PROVENANCE COVERAGE: {_show(layers.get('VISION_PROVENANCE_COVERAGE'))}",
        f"SIGNAL PROVENANCE COVERAGE: {_show(layers.get('SIGNAL_PROVENANCE_COVERAGE'))}",
        f"RUNTIME TRANSITION COVERAGE: {_show(layers.get('RUNTIME_TRANSITION_COVERAGE'))}",
        f"OBSERVER TIMELINE COVERAGE: {_show(layers.get('OBSERVER_TIMELINE_COVERAGE'))}",
        f"AUXILIARY COVERAGE: {_show(layered.get('auxiliary'))}",
        "Note: CORE FULL means complete SCIENTIFIC_V3 O→D→M→C chains, not complete world/optical/runtime-aggregate coverage.",
        "",
        "3. CONFIGURATION AND RUNTIME REGIMES",
        "World-intervention configuration history (WORLD_INTERVENTION events) is a different authority layer",
        "from mechanism runtime transitions (PSC schedule / SMC withhold). They must not be collapsed.",
        (payload.get("psc_regime_report_text") or "PSC REGIMES\nNOT AVAILABLE").strip(),
        "",
        "4. WHAT HAPPENED",
    ]
    lines += _format_what_happened(payload.get("what_happened"))
    lines += ["", "5. PER-AGENT SUMMARIES"]
    agents = hist.get("agents") or {}
    for aid in sorted(agents):
        row = agents[aid]
        lines += [
            str(aid).upper(),
            f"  Canonical agent-ticks: {_show(row.get('canonical_ticks') or row.get('ticks_observed'))} (unit: agent-ticks)",
            f"  Per-agent DecisionReceipts: {_show(row.get('decision_receipts'))} ({_show(row.get('decision_receipts_unit') or 'per-agent receipts')})",
            f"  WAIT ticks: {_show(row.get('wait_count'))}  MOVE ticks: {_show(row.get('move_count'))} (unit: agent-ticks; occupancy)",
            f"  Longest contiguous WAIT streak: {_show(row.get('longest_wait_streak'))}  MOVE: {_show(row.get('longest_move_streak'))}",
            f"  Action transitions: {_show(row.get('action_transitions'))}  sequence coverage: {_show(row.get('sequence_coverage'))}",
            f"  Gap ticks missing (streaks break across gaps): {_show(row.get('gap_ticks_missing'))}",
            f"  Duplicates ignored: {_show(row.get('duplicates_ignored'))}",
            "",
        ]
    lines += [
        "6. AGENT COMPARISON",
        "See per-agent occupancy, streaks, and DecisionReceipts above. Global counts are not repeated as per-agent counts.",
        "",
        "7. INTERACTION / CONTACT SUMMARY",
    ]
    lines += _format_episode_counts(payload.get("episode_counts"))
    lines += [
        "",
        "8. VISION",
        str(payload.get("beta31_vision_report_text") or "VISION ANALYSIS: NOT AVAILABLE").rstrip(),
        "",
        "9. HEARING / SIGNALS",
        str(
            payload.get("signal_conditioned_report_text")
            or "SIGNAL FORENSICS: NOT AVAILABLE in this package."
        ).rstrip(),
        "",
        "10. PSC / PREDICTIVE MECHANISMS",
        "See §3 PSC REGIMES. HSS withheld_from_psc is the O-prime history gate, not PSC OFF.",
        str(payload.get("historical_sensorimotor_selection_report_text") or "HISTORICAL SENSORIMOTOR SELECTION: NOT AVAILABLE").rstrip(),
        "",
        "11. VOLUMETRIC PHYSICAL RECONSTRUCTION",
        str(payload.get("volumetric_physical_causal_report_text") or "NOT AVAILABLE").rstrip(),
        "",
        "12. DEVELOPMENT FIXTURES / ONTOLOGY BOUNDARY",
        str(payload.get("development_fixture_section") or "").rstrip(),
        "",
        "13. CAUSAL CLAIMS SUPPORTED",
        "Complete O→D→M→C chains are OBSERVED receipts for each agent-tick in the analyzed interval.",
        "PSC regime boundaries are DERIVED from DecisionReceipt SMC withhold series and snapshot schedule receipts when present.",
        "Action occupancy and contiguous streaks are DERIVED from ordered unique per-agent locomotion tokens.",
        "Detailed chain rows are externalized to analysis_tick_stories.jsonl (not inlined).",
        "",
        "14. NOT ESTABLISHED",
        "Intention, recognition, communication, reward, seeking, and strategy: NOT ESTABLISHED.",
        "Optical occupancy ≠ body exposure ≠ recognition.",
        "resource-* objects are DEVELOPMENT_FIXTURE, not canonical food/goals.",
        "",
        "15. DATA LIMITATIONS",
        "World metadata, optical provenance, runtime aggregates, transition history, and auxiliary streams may be PARTIAL/UNAVAILABLE even when core chains are FULL.",
        "Observer timeline samples may be absent from compact HTTP even when session_timeline.jsonl is listed.",
        "Forensic channel tables remain in named job artifacts; the primary narrative does not dump all raw channel values.",
        "",
        "16. TECHNICAL PROVENANCE",
        f"Scientific V3 decision_receipts (global): {_show(v3.get('decision_receipts'))} (unit: receipts / agent-ticks)",
        f"Observation receipts: {_show(v3.get('observation_receipts'))}",
        f"Motor receipts: {_show(v3.get('motor_receipts'))}",
        f"Consequence receipts: {_show(v3.get('consequence_receipts'))}",
        f"Incomplete chains: {_show(v3.get('incomplete_odmc_chains'))}",
        f"Elapsed_s (analysis job wall): {_show(elapsed)}",
        f"Elapsed source: {_show(payload.get('elapsed_source') or ('job_progress' if payload.get('job_elapsed_s') is not None else 'analyzer_pipeline'))}",
        "",
        "17. DETAILED FORENSIC APPENDIX",
        "Primary narrative above is complete for audit of counts, regimes, and coverage.",
        "Channel-level forensic tables remain in job artifacts:",
        "- analysis_sensorimotor_consequence.json",
        "- optical_occupancy.json / vision_summary.json",
        "- analysis_tick_stories.jsonl",
        "- BEHAVIORAL_RECONSTRUCTION.txt",
        "",
        "Sensorimotor consequence summary (full text from analysis package):",
        str(payload.get("sensorimotor_report_text") or "NOT AVAILABLE").rstrip(),
        "",
    ]
    body = "\n".join(lines).rstrip() + "\n"
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    footer = [
        "EXPORT INTEGRITY",
        f"report_schema: {REPORT_SCHEMA}",
        f"run_id: {_show(payload.get('run_id') or ident.get('run_id'))}",
        f"analysis_cutoff_tick: {_show(payload.get('analysis_cutoff_tick'))}",
        f"normalized_content_hash: {content_hash}",
        "generated_byte_count: __BC__",
        "generated_line_count: __LC__",
        "",
        TERMINAL_MARKER,
        "",
    ]
    return body + "\n".join(footer)


def markdown_body_hash(text: str) -> str:
    """Hash of Markdown excluding the EXPORT INTEGRITY footer and terminal marker."""
    marker = "\nEXPORT INTEGRITY\n"
    idx = text.find(marker)
    body = text[:idx] if idx >= 0 else text
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
