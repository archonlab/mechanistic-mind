from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
import json


def to_primitive(value: Any) -> Any:
    """Convert observer-visible values into JSON-compatible structures.

    The function is intentionally conservative and deterministic:
    - dict keys become strings and are sorted during JSON encoding
    - tuples/sets become lists
    - dataclasses become dictionaries
    - unsupported custom objects fail instead of being stringified silently
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if is_dataclass(value):
        return to_primitive(asdict(value))

    if isinstance(value, dict):
        return {
            str(key): to_primitive(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]

    if isinstance(value, set):
        return sorted(to_primitive(item) for item in value)

    raise TypeError(
        f"Observer cannot serialize value of type {type(value).__name__}"
    )


def canonical_json(value: Any) -> str:
    """Stable JSON encoding for telemetry comparison and hashing."""
    return json.dumps(
        to_primitive(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def append_jsonl(path: str | Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(value))
        handle.write("\n")
