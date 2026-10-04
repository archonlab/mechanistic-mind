"""Central saved-evidence payload normalizer for Analyzer pipelines.

Converts valid historical shapes into a documented canonical record list
without scattering isinstance patches across unrelated summaries.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXPORT_SCHEMA = "mm.analyzer.evidence_payload.v1"


def normalize_evidence_payload(
    raw: Any,
    *,
    source_path: str | None = None,
    schema_hint: str | None = None,
) -> dict[str, Any]:
    """Normalize envelope / record / list / JSONL-decoded payloads.

    Returns:
      source_kind, source_path, schema, records, record_count, warnings, errors, legacy_class
    """
    warnings: list[str] = []
    errors: list[str] = []
    schema = schema_hint
    legacy_class = "CURRENT"
    records: list[dict[str, Any]] = []
    source_kind = "UNKNOWN"

    if raw is None:
        source_kind = "NULL"
        return _result(source_kind, source_path, schema, records, warnings, errors, legacy_class)

    if isinstance(raw, list):
        source_kind = "LIST_OF_RECORDS" if raw else "EMPTY_LIST"
        for i, item in enumerate(raw):
            if isinstance(item, dict):
                records.append(item)
            else:
                errors.append(f"list_element_{i}_not_dict:{type(item).__name__}")
        return _result(source_kind, source_path, schema, records, warnings, errors, legacy_class)

    if isinstance(raw, dict):
        schema = schema or raw.get("schema") or raw.get("receipt_kind")
        # Envelope with embedded records
        for key in ("records", "items", "events", "rows", "traces", "receipts"):
            if key in raw and isinstance(raw[key], list):
                source_kind = "ENVELOPE_DICT"
                legacy_class = "ENVELOPE"
                inner = normalize_evidence_payload(
                    raw[key], source_path=source_path, schema_hint=schema
                )
                warnings.extend(inner["warnings"])
                errors.extend(inner["errors"])
                return _result(
                    source_kind,
                    source_path,
                    schema,
                    list(inner["records"]),
                    warnings,
                    errors,
                    legacy_class,
                )
        # Single record
        source_kind = "SINGLE_RECORD"
        records = [raw]
        return _result(source_kind, source_path, schema, records, warnings, errors, legacy_class)

    # Scalar / unexpected
    source_kind = "MALFORMED"
    errors.append(f"unsupported_payload_type:{type(raw).__name__}")
    return _result(source_kind, source_path, schema, records, warnings, errors, "MALFORMED")


def load_and_normalize_json_file(path: Path | str, *, schema_hint: str | None = None) -> dict[str, Any]:
    """Load JSON or JSONL from disk and normalize."""
    p = Path(path)
    if not p.is_file():
        return _result(
            "MISSING_FILE",
            str(p),
            schema_hint,
            [],
            [],
            [f"missing_file:{p.name}"],
            "MISSING",
        )
    text = p.read_text(encoding="utf-8")
    # JSONL heuristic: multiple non-empty lines that each parse as JSON
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) > 1:
        records: list[Any] = []
        errors: list[str] = []
        for i, ln in enumerate(lines):
            try:
                records.append(json.loads(ln))
            except Exception as exc:
                errors.append(f"jsonl_line_{i}:{exc}")
        out = normalize_evidence_payload(records, source_path=str(p), schema_hint=schema_hint)
        out["source_kind"] = "JSONL_STREAM"
        out["errors"] = list(out["errors"]) + errors
        out["legacy_class"] = "JSONL"
        return out
    try:
        raw = json.loads(text)
    except Exception as exc:
        return _result(
            "MALFORMED",
            str(p),
            schema_hint,
            [],
            [],
            [f"json_parse_error:{exc}"],
            "MALFORMED",
        )
    return normalize_evidence_payload(raw, source_path=str(p), schema_hint=schema_hint)


def _result(
    source_kind: str,
    source_path: str | None,
    schema: str | None,
    records: list[dict[str, Any]],
    warnings: list[str],
    errors: list[str],
    legacy_class: str,
) -> dict[str, Any]:
    return {
        "export_schema": EXPORT_SCHEMA,
        "source_kind": source_kind,
        "source_path": source_path,
        "schema": schema,
        "records": records,
        "record_count": len(records),
        "warnings": warnings,
        "errors": errors,
        "legacy_class": legacy_class,
    }
