"""Resolve Analyzer report metadata from saved-run files with explicit precedence.

Never infers values from filenames. Missing fields remain NOT AVAILABLE.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PRECEDENCE = [
    "scientific_v3_meta.json",
    "scientific_meta.json",
    "run.json",
    "physical_system_snapshot.json (identity/config only)",
    "identity_map.json",
    "Observer archive metadata",
]


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _field(value: Any, *, source: str, layer: str, full_run: bool = True) -> dict[str, Any]:
    if value is None or value == "":
        return {
            "value": "NOT AVAILABLE",
            "authoritative": False,
            "source": source,
            "layer": layer,
            "covers_full_run": full_run,
            "safe_to_populate": False,
        }
    return {
        "value": value,
        "authoritative": True,
        "source": source,
        "layer": layer,
        "covers_full_run": full_run,
        "safe_to_populate": True,
    }


def list_evidence_streams(run_dir: Path) -> list[str]:
    run_dir = Path(run_dir)
    manifest = _load(run_dir / "run.json")
    arts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    names: list[str] = []
    if arts:
        for _k, rel in arts.items():
            if isinstance(rel, str) and (run_dir / rel).is_file() and rel not in names:
                names.append(rel)
    sci = manifest.get("scientific_history") if isinstance(manifest.get("scientific_history"), dict) else {}
    for rel in sci.get("files") or []:
        if isinstance(rel, str) and (run_dir / rel).is_file() and rel not in names:
            names.append(rel)
    for fallback in (
        "scientific_spine.jsonl",
        "scientific_observations.jsonl",
        "scientific_decisions.jsonl",
        "scientific_motors.jsonl",
        "scientific_consequences.jsonl",
        "scientific_timeline.jsonl",
        "scientific_events.jsonl",
        "scientific_v3_meta.json",
        "scientific_meta.json",
        "identity_map.json",
        "run.json",
        "physical_system_snapshot.json",
    ):
        if (run_dir / fallback).is_file() and fallback not in names:
            names.append(fallback)
    return names


def resolve_run_metadata(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    v3 = _load(run_dir / "scientific_v3_meta.json")
    meta = _load(run_dir / "scientific_meta.json")
    run = _load(run_dir / "run.json")
    ident = _load(run_dir / "identity_map.json")
    world = run.get("world") if isinstance(run.get("world"), dict) else {}
    model = run.get("model") if isinstance(run.get("model"), dict) else {}
    if not model:
        model = v3 if v3.get("public_preset") else {}

    streams = list_evidence_streams(run_dir)
    fields = {
        "run_id": _field(run.get("run_id") or v3.get("run_id") or meta.get("run_id"), source="run.json", layer="saved-run scientific manifest"),
        "preset_model_line": _field(
            model.get("public_preset") or v3.get("public_preset") or meta.get("public_preset"),
            source="run.json / scientific_v3_meta.json",
            layer="saved-run scientific manifest",
        ),
        "display_name": _field(
            model.get("display_name") or v3.get("display_name") or meta.get("display_name"),
            source="run.json / scientific_v3_meta.json",
            layer="saved-run scientific manifest",
        ),
        "runtime_class": _field(
            run.get("runtime_type") or v3.get("runtime_type") or meta.get("runtime_type"),
            source="run.json",
            layer="saved-run scientific manifest",
        ),
        "seed": _field(run.get("seed") if run.get("seed") is not None else v3.get("seed"), source="run.json", layer="saved-run scientific manifest"),
        "runtime_generation": _field(
            run.get("runtime_generation") if run.get("runtime_generation") is not None else v3.get("generation"),
            source="run.json",
            layer="saved-run scientific manifest",
        ),
        "agent_count": _field(run.get("agent_count") or v3.get("agent_count") or meta.get("agent_count"), source="run.json", layer="saved-run scientific manifest"),
        "world_width": _field(world.get("width"), source="run.json world", layer="saved-run scientific manifest"),
        "world_height": _field(world.get("height"), source="run.json world", layer="saved-run scientific manifest"),
        "boundary_mode": _field(world.get("topology"), source="run.json world", layer="saved-run scientific manifest"),
        "mechanism_config_fingerprint": _field(
            meta.get("mechanism_config_fingerprint") or (meta.get("runtime_mechanism_manifest") or {}).get("resolved_fingerprint"),
            source="scientific_meta.json",
            layer="applied configuration manifest",
            full_run=False,
        ),
        "public_model_fingerprint_library": _field(
            None,
            source="not stored on this run; library identity is reported separately when labeled",
            layer="n/a",
        ),
        "cognition_initial": _field(
            _psc_initial(meta),
            source="scientific_meta.json runtime_mechanism_manifest (tick 0)",
            layer="frozen initial state",
            full_run=False,
        ),
        "evidence_file_list": _field(streams, source="run.json artifacts + present files", layer="evidence stream schemas"),
        "evidence_record_counts": _field(
            (v3.get("counts") or meta.get("counts") or {"rows_written": meta.get("rows_written")}),
            source="scientific_v3_meta.json counts",
            layer="evidence stream schemas",
        ),
        "run_start": _field(run.get("started_at") or meta.get("started_at") or v3.get("opened_at"), source="run.json", layer="saved-run scientific manifest"),
        "run_end": _field(run.get("stopped_at") or meta.get("closed_at") or v3.get("updated_at"), source="run.json", layer="saved-run scientific manifest"),
        "scientific_generation_label": _field(
            "GEN_POST_V1B_VERTICAL_SUPPORT_ESCAPE_REPAIR",
            source="current scientific generation (package/docs; not a per-run JSON field)",
            layer="Observer archive metadata",
        ),
        "status": _field(run.get("status") or run.get("termination_reason"), source="run.json", layer="saved-run scientific manifest"),
        "cognition_enabled_initial_manifest": _field(
            _mech_runtime(meta, "cognition"),
            source="scientific_meta.json runtime_mechanism_manifest",
            layer="frozen initial state",
            full_run=False,
        ),
    }
    # Library public-model fingerprint is known for named presets; label as library not instance.
    preset = str((fields["preset_model_line"] or {}).get("value") or "")
    if preset == "ACANTHOSTEGA_BETA4":
        fields["public_model_fingerprint_library"] = {
            "value": "3666b58d67932821",
            "authoritative": True,
            "source": "mechanistic_mind.physical_system.experiment_canonical PRESET_ACANTHOSTEGA_BETA4 seed=17",
            "layer": "public-model identity (not this run's instance fingerprint)",
            "covers_full_run": False,
            "safe_to_populate": True,
            "note": "This is the frozen public-model fingerprint, not a hash of seed 9768.",
        }
    identity = {
        "run_id": fields["run_id"]["value"] if fields["run_id"]["safe_to_populate"] else None,
        "runtime_type": fields["runtime_class"]["value"] if fields["runtime_class"]["safe_to_populate"] else None,
        "seed": fields["seed"]["value"] if fields["seed"]["safe_to_populate"] else None,
        "runtime_generation": fields["runtime_generation"]["value"] if fields["runtime_generation"]["safe_to_populate"] else None,
        "agent_count": fields["agent_count"]["value"] if fields["agent_count"]["safe_to_populate"] else None,
        "map_width": fields["world_width"]["value"] if fields["world_width"]["safe_to_populate"] else None,
        "map_height": fields["world_height"]["value"] if fields["world_height"]["safe_to_populate"] else None,
        "boundary": fields["boundary_mode"]["value"] if fields["boundary_mode"]["safe_to_populate"] else None,
        "public_preset": fields["preset_model_line"]["value"] if fields["preset_model_line"]["safe_to_populate"] else None,
        "display_name": fields["display_name"]["value"] if fields["display_name"]["safe_to_populate"] else None,
        "status": fields["status"]["value"] if fields["status"]["safe_to_populate"] else None,
        "cognition_enabled": "REGIME-DEPENDENT (see PSC REGIMES)",
        "mechanism_config_fingerprint": fields["mechanism_config_fingerprint"]["value"] if fields["mechanism_config_fingerprint"]["safe_to_populate"] else None,
        "scientific_generation": fields["scientific_generation_label"]["value"],
        "identity_map_present": bool(ident),
    }
    return {
        "schema": "mm.analyzer.metadata_authority.v1",
        "precedence": PRECEDENCE,
        "fields": fields,
        "identity": identity,
        "evidence_files": streams,
        "run_dir": str(run_dir),
    }


def _psc_initial(meta: dict[str, Any]) -> str | None:
    man = meta.get("runtime_mechanism_manifest") or {}
    for row in man.get("mechanisms") or []:
        if isinstance(row, dict) and row.get("id") == "prospective_scenario_competition":
            runtime = row.get("runtime")
            configured = row.get("configured")
            return f"configured={configured} runtime={runtime} (manifest tick {man.get('runtime_tick_at_manifest')})"
    return None


def _mech_runtime(meta: dict[str, Any], mech_id: str) -> Any:
    man = meta.get("runtime_mechanism_manifest") or {}
    for row in man.get("mechanisms") or []:
        if isinstance(row, dict) and row.get("id") == mech_id:
            return row.get("runtime")
    return None
