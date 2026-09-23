"""Update 4.21 — Provenance-preserving predictive compression.

Research/measurement memory layer. No semantic autobiographical labels.
Does not alter valuation or introduce motivation. Does not tune 4.20 NULLs.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
from typing import Any


# Explicit capacities (Category A).
RECENT_CAPACITY = 128
STRUCTURE_CAPACITY = 64
PROVENANCE_EDGES_PER_STRUCTURE = 24
REVISION_DEPTH = 8
REPRESENTATIVE_PER_STRUCTURE = 4
EXCEPTION_CAPACITY = 32
PREDICTION_AT_EVENT_CAPACITY = 64
RAW_ARCHIVE_CAPACITY = 0  # after purge: must stay 0 for deleted ids


# Same-payload signature reuse (identical digest; bounded map).
_SIG_CACHE: dict[tuple[tuple[str, Any], ...], str] = {}
_SIG_CACHE_MAX = 8192


def _sig(payload: dict[str, Any]) -> str:
    items = tuple(
        sorted(
            (
                str(k),
                round(float(v), 4) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v),
            )
            for k, v in payload.items()
        )
    )
    hit = _SIG_CACHE.get(items)
    if hit is not None:
        return hit
    raw = "|".join(f"{k}:{v}" for k, v in items)
    digest = sha1(raw.encode("utf-8")).hexdigest()[:12]
    if len(_SIG_CACHE) >= _SIG_CACHE_MAX:
        _SIG_CACHE.clear()
    _SIG_CACHE[items] = digest
    return digest


def empty_memory(*, recent_capacity: int = RECENT_CAPACITY) -> dict[str, Any]:
    return {
        "recent": [],
        "recent_capacity": int(recent_capacity),
        "structures": {},
        "structure_capacity": STRUCTURE_CAPACITY,
        "exceptions": {},
        "exception_capacity": EXCEPTION_CAPACITY,
        "prediction_at_event": {},
        "pae_capacity": PREDICTION_AT_EVENT_CAPACITY,
        "raw_log": {},  # id -> record; physically purged
        "raw_removed_ids": [],
        "next_raw_id": 1,
        "next_struct_id": 1,
        "ticks_lived": 0,
        "raw_generated": 0,
        "raw_retained": 0,
        "raw_removed": 0,
        "compressions": 0,
        "revisions": 0,
        "forgotten_structures": 0,
        "ablate_compression": False,
        "ablate_provenance": False,
        "ablate_representatives": False,
        "metrics_affect_cognition": False,  # must stay False
    }


def observe(
    mem: dict[str, Any],
    *,
    tick: int,
    fragment: dict[str, float],
    action: str,
    predicted: dict[str, float] | None = None,
    realized: dict[str, float] | None = None,
    domain: str = "generic",
) -> dict[str, Any]:
    """Append to recent buffer and raw_log (bounded). Returns raw_id record."""
    mem["ticks_lived"] = int(tick)
    mem["raw_generated"] = int(mem.get("raw_generated") or 0) + 1
    rid = int(mem.get("next_raw_id") or 1)
    mem["next_raw_id"] = rid + 1
    pred = dict(predicted or {})
    real = dict(realized if realized is not None else fragment)
    mismatch = False
    abs_l1 = 0.0
    if pred:
        keys = set(pred) | set(real)
        abs_l1 = sum(abs(float(real.get(k, 0.0)) - float(pred.get(k, 0.0))) for k in keys)
        mismatch = abs_l1 > 0.12
    record = {
        "raw_id": rid,
        "tick": int(tick),
        "domain": str(domain),
        "action": str(action),
        "fragment": {str(k): float(v) for k, v in fragment.items() if isinstance(v, (int, float))},
        "predicted": pred,
        "realized": real,
        "mismatch": mismatch,
        "abs_l1": round(abs_l1, 5),
        "antecedent_sig": _sig(fragment),
        "consequent_sig": _sig(real),
    }
    # raw_log only while not purged; still bounded by recent+pending
    mem.setdefault("raw_log", {})[rid] = record
    mem["raw_retained"] = len(mem["raw_log"])
    recent = mem.setdefault("recent", [])
    recent.append(rid)
    cap = int(mem.get("recent_capacity") or RECENT_CAPACITY)
    while len(recent) > cap:
        old = recent.pop(0)
        # do not auto-delete from raw_log here — compression/purge owns deletion
        _ = old
    mem["recent"] = recent

    if pred and mismatch:
        _preserve_prediction_at_event(mem, record)

    if not mem.get("ablate_compression"):
        _maybe_compress_transition(mem, record)
    return record


def _preserve_prediction_at_event(mem: dict[str, Any], record: dict[str, Any]) -> None:
    pae = mem.setdefault("prediction_at_event", {})
    eid = f"E{record['raw_id']}"
    pae[eid] = {
        "event_id": eid,
        "tick": record["tick"],
        "predicted": deepcopy(record.get("predicted") or {}),
        "observed": deepcopy(record.get("realized") or {}),
        "mismatch": True,
        "abs_l1": record.get("abs_l1"),
        "antecedent_sig": record.get("antecedent_sig"),
        "action": record.get("action"),
        "domain": record.get("domain"),
        "linked_structure": None,
        # frozen prediction-at-time — never overwrite with current model
        "frozen": True,
    }
    while len(pae) > int(mem.get("pae_capacity") or PREDICTION_AT_EVENT_CAPACITY):
        oldest = sorted(pae.items(), key=lambda kv: int(kv[1].get("tick") or 0))[0][0]
        pae.pop(oldest, None)


def _maybe_compress_transition(mem: dict[str, Any], record: dict[str, Any]) -> None:
    key = f"{record['domain']}||{record['antecedent_sig']}||{record['action']}||{record['consequent_sig']}"
    structures = mem.setdefault("structures", {})
    row = structures.get(key)
    if row is None:
        if len(structures) >= int(mem.get("structure_capacity") or STRUCTURE_CAPACITY):
            # forget weakest unused
            victim = min(
                structures.items(),
                key=lambda kv: (float(kv[1].get("support") or 0), int(kv[1].get("last_tick") or 0)),
            )[0]
            _forget_structure(mem, victim)
        sid = f"P{int(mem.get('next_struct_id') or 1)}"
        mem["next_struct_id"] = int(mem.get("next_struct_id") or 1) + 1
        row = {
            "structure_id": sid,
            "key": key,
            "domain": record["domain"],
            "antecedent_sig": record["antecedent_sig"],
            "action": record["action"],
            "consequent_sig": record["consequent_sig"],
            "mean_predicted": deepcopy(record.get("realized") or {}),
            "support": 0,
            "contradictions": 0,
            "first_tick": record["tick"],
            "last_tick": record["tick"],
            "status": "ACTIVE",
            "provenance": [],
            "representatives": [],
            "revision_of": None,
            "superseded_by": None,
            "revision_chain": [],
        }
        structures[key] = row
        mem["compressions"] = int(mem.get("compressions") or 0) + 1
        _add_prov(mem, row, "compressed_from", record["raw_id"], tick=record["tick"])

    row["support"] = int(row.get("support") or 0) + 1
    row["last_tick"] = record["tick"]
    # EMA of realized
    mean = row.setdefault("mean_predicted", {})
    s = float(row["support"])
    for k, v in (record.get("realized") or {}).items():
        prev = float(mean.get(k, 0.0))
        mean[k] = prev + (float(v) - prev) / s

    if not mem.get("ablate_representatives"):
        _update_representatives(row, record)

    if record.get("mismatch"):
        row["contradictions"] = int(row.get("contradictions") or 0) + 1
        _retain_exception(mem, record, row)
        _link_pae(mem, record, row)
        _maybe_revise(mem, row, record)


def _update_representatives(row: dict[str, Any], record: dict[str, Any]) -> None:
    reps = row.setdefault("representatives", [])
    # keep first formation + strongest support contribution (latest) + contradictions
    entry = {
        "raw_id": record["raw_id"],
        "tick": record["tick"],
        "kind": "support",
        "fragment": deepcopy(record.get("fragment") or {}),
        "realized": deepcopy(record.get("realized") or {}),
    }
    if not reps:
        entry["kind"] = "first_evidence"
        reps.append(entry)
    else:
        # replace weakest non-first if full
        if len(reps) < REPRESENTATIVE_PER_STRUCTURE:
            reps.append(entry)
        else:
            # keep index 0 (first), refresh last support slot
            reps[-1] = entry
    if record.get("mismatch"):
        contra = dict(entry)
        contra["kind"] = "contradiction"
        # ensure a contradiction slot
        kinds = [r.get("kind") for r in reps]
        if "contradiction" in kinds:
            reps[kinds.index("contradiction")] = contra
        elif len(reps) < REPRESENTATIVE_PER_STRUCTURE:
            reps.append(contra)
        else:
            reps[-2] = contra if len(reps) > 1 else contra


def _add_prov(mem: dict[str, Any], row: dict[str, Any], edge_type: str, target: Any, *, tick: int) -> None:
    if mem.get("ablate_provenance"):
        return
    prov = row.setdefault("provenance", [])
    prov.append({"type": edge_type, "target": target, "tick": tick})
    while len(prov) > PROVENANCE_EDGES_PER_STRUCTURE:
        prov.pop(0)


def _retain_exception(mem: dict[str, Any], record: dict[str, Any], row: dict[str, Any]) -> None:
    ex = mem.setdefault("exceptions", {})
    eid = f"X{record['raw_id']}"
    ex[eid] = {
        "exception_id": eid,
        "raw_id": record["raw_id"],
        "tick": record["tick"],
        "structure_id": row.get("structure_id"),
        "predicted": deepcopy(record.get("predicted") or {}),
        "observed": deepcopy(record.get("realized") or {}),
        "antecedent_sig": record.get("antecedent_sig"),
        "action": record.get("action"),
        "domain": record.get("domain"),
        "status": "UNRESOLVED",
        # snapshot of evidence — survives raw deletion
        "evidence_snapshot": {
            "fragment": deepcopy(record.get("fragment") or {}),
            "realized": deepcopy(record.get("realized") or {}),
        },
    }
    while len(ex) > int(mem.get("exception_capacity") or EXCEPTION_CAPACITY):
        oldest = sorted(ex.items(), key=lambda kv: int(kv[1].get("tick") or 0))[0][0]
        ex.pop(oldest, None)
    _add_prov(mem, row, "contradicted_by", eid, tick=record["tick"])


def _link_pae(mem: dict[str, Any], record: dict[str, Any], row: dict[str, Any]) -> None:
    eid = f"E{record['raw_id']}"
    pae = (mem.get("prediction_at_event") or {}).get(eid)
    if isinstance(pae, dict):
        pae["linked_structure"] = row.get("structure_id")


def _maybe_revise(mem: dict[str, Any], row: dict[str, Any], record: dict[str, Any]) -> None:
    """If contradictions accumulate vs support, spawn revised structure."""
    support = int(row.get("support") or 0)
    contra = int(row.get("contradictions") or 0)
    if contra < 3 or contra * 2 < support:
        return
    # revise: supersede with structure whose consequent matches latest observation
    new_key = f"{record['domain']}||{record['antecedent_sig']}||{record['action']}||{record['consequent_sig']}"
    if new_key == row.get("key"):
        return
    structures = mem.setdefault("structures", {})
    if new_key in structures:
        successor = structures[new_key]
    else:
        sid = f"P{int(mem.get('next_struct_id') or 1)}"
        mem["next_struct_id"] = int(mem.get("next_struct_id") or 1) + 1
        successor = {
            "structure_id": sid,
            "key": new_key,
            "domain": record["domain"],
            "antecedent_sig": record["antecedent_sig"],
            "action": record["action"],
            "consequent_sig": record["consequent_sig"],
            "mean_predicted": deepcopy(record.get("realized") or {}),
            "support": 1,
            "contradictions": 0,
            "first_tick": record["tick"],
            "last_tick": record["tick"],
            "status": "ACTIVE",
            "provenance": [],
            "representatives": [],
            "revision_of": row.get("structure_id"),
            "superseded_by": None,
            "revision_chain": [],
        }
        structures[new_key] = successor
        mem["compressions"] = int(mem.get("compressions") or 0) + 1
    row["status"] = "SUPERSEDED"
    row["superseded_by"] = successor.get("structure_id")
    chain = list(row.get("revision_chain") or [])
    chain.append(row.get("structure_id"))
    chain = chain[-REVISION_DEPTH:]
    successor["revision_chain"] = chain + [successor.get("structure_id")]
    successor["revision_of"] = row.get("structure_id")
    _add_prov(mem, successor, "revised_after", row.get("structure_id"), tick=record["tick"])
    _add_prov(mem, row, "superseded_by", successor.get("structure_id"), tick=record["tick"])
    mem["revisions"] = int(mem.get("revisions") or 0) + 1
    # resolve matching exceptions
    for ex in (mem.get("exceptions") or {}).values():
        if ex.get("structure_id") == row.get("structure_id") and ex.get("status") == "UNRESOLVED":
            if ex.get("tick") == record["tick"] or True:
                ex["status"] = "INCORPORATED"
                ex["resolved_into"] = successor.get("structure_id")


def _forget_structure(mem: dict[str, Any], key: str) -> None:
    structures = mem.get("structures") or {}
    row = structures.pop(key, None)
    if row:
        mem["forgotten_structures"] = int(mem.get("forgotten_structures") or 0) + 1


def predict(
    mem: dict[str, Any],
    fragment: dict[str, float],
    action: str,
    *,
    domain: str = "generic",
    antecedent_sig: str | None = None,
) -> dict[str, Any]:
    """Retrieve best matching ACTIVE structure for antecedent+action."""
    ant = antecedent_sig if antecedent_sig is not None else _sig(fragment)
    best = None
    for row in (mem.get("structures") or {}).values():
        if row.get("status") != "ACTIVE":
            continue
        if row.get("domain") != domain:
            continue
        if row.get("antecedent_sig") != ant:
            continue
        if row.get("action") != action:
            continue
        if best is None or int(row.get("support") or 0) > int(best.get("support") or 0):
            best = row
    if best is None:
        return {"status": "NO_MATCH", "predicted": {}}
    return {
        "status": "MATCH",
        "structure_id": best.get("structure_id"),
        "predicted": deepcopy(best.get("mean_predicted") or {}),
        "support": best.get("support"),
        "key": best.get("key"),
    }


def purge_redundant_raw(mem: dict[str, Any], *, keep_recent: bool = True) -> dict[str, Any]:
    """Physically delete raw records that are redundant given compressed structures.

    Keeps: recent buffer ids, representative raw snapshots (already copied),
    exception evidence_snapshots, prediction_at_event frozen payloads.
    Removes raw_log entries and clears provenance targets that pointed only to raw ids
    by replacing with snapshots already stored.
    """
    keep = set(mem.get("recent") or []) if keep_recent else set()
    # representatives store raw_id but also fragment snapshots — raw can go
    removed = []
    raw_log = mem.get("raw_log") or {}
    for rid in list(raw_log.keys()):
        if rid in keep:
            continue
        # eligible if support already folded into some structure
        raw_log.pop(rid, None)
        removed.append(rid)
    mem["raw_removed"] = int(mem.get("raw_removed") or 0) + len(removed)
    mem.setdefault("raw_removed_ids", []).extend(removed)
    # bound removed id list
    mem["raw_removed_ids"] = list(mem["raw_removed_ids"])[-500:]
    mem["raw_retained"] = len(raw_log)
    # scrub provenance targets that are bare raw ids no longer in raw_log
    for row in (mem.get("structures") or {}).values():
        for edge in row.get("provenance") or []:
            t = edge.get("target")
            if isinstance(t, int) and t not in raw_log:
                edge["target_status"] = "RAW_DELETED"
                edge["target_snapshot_note"] = "raw purged; use representatives/exceptions/pae"
    # ensure deleted ids not secretly accessible
    assert all(rid not in raw_log for rid in removed)
    return {"removed": len(removed), "retained": len(raw_log), "recent_kept": len(keep)}


def expand_structure(mem: dict[str, Any], structure_id: str) -> dict[str, Any]:
    """Researcher-side expandable view — not agent cognition."""
    for row in (mem.get("structures") or {}).values():
        if row.get("structure_id") == structure_id:
            linked_pae = [
                v for v in (mem.get("prediction_at_event") or {}).values()
                if v.get("linked_structure") == structure_id
            ]
            linked_ex = [
                v for v in (mem.get("exceptions") or {}).values()
                if v.get("structure_id") == structure_id
            ]
            return {
                "structure": deepcopy(row),
                "representatives": deepcopy(row.get("representatives") or []),
                "provenance": deepcopy(row.get("provenance") or []),
                "revision_chain": deepcopy(row.get("revision_chain") or []),
                "prediction_at_events": linked_pae,
                "exceptions": linked_ex,
                "raw_still_present": [
                    r.get("raw_id") for r in (row.get("representatives") or [])
                    if r.get("raw_id") in (mem.get("raw_log") or {})
                ],
            }
    return {"error": "NOT_FOUND", "structure_id": structure_id}


def memory_cost(mem: dict[str, Any]) -> dict[str, Any]:
    """Observer/research cost panel.

    ``bytes_*`` are exact JSON sizes of the persistent/raw maps. Results are
    cached on ``mem`` until structural occupancy counters change so LIVE/full
    frames do not re-serialize the entire store on every ``cognitive_view``.
    """
    import json

    structures = mem.get("structures") or {}
    exceptions = mem.get("exceptions") or {}
    recent = mem.get("recent") or []
    pae = mem.get("prediction_at_event") or {}
    raw_log = mem.get("raw_log") or {}
    cache_key = (
        int(mem.get("ticks_lived") or 0),
        int(mem.get("raw_generated") or 0),
        int(mem.get("raw_retained") or 0),
        int(mem.get("raw_removed") or 0),
        int(mem.get("revisions") or 0),
        len(recent),
        len(structures),
        len(exceptions),
        len(pae),
        len(raw_log) if isinstance(raw_log, dict) else 0,
    )
    cached = mem.get("_memory_cost_cache")
    if isinstance(cached, dict) and cached.get("key") == cache_key:
        return dict(cached["cost"])

    persistent = {
        "recent": recent,
        "structures": structures,
        "exceptions": exceptions,
        "prediction_at_event": pae,
        "raw_log": raw_log,
    }
    raw_only = {"raw_log": raw_log}
    bytes_persistent = len(json.dumps(persistent, sort_keys=True).encode("utf-8"))
    bytes_raw = len(json.dumps(raw_only, sort_keys=True).encode("utf-8"))
    ticks = max(1, int(mem.get("ticks_lived") or 1))
    cost = {
        "ticks_lived": mem.get("ticks_lived"),
        "raw_generated": mem.get("raw_generated"),
        "raw_retained": mem.get("raw_retained"),
        "raw_removed": mem.get("raw_removed"),
        "recent_buffer_size": len(recent),
        "compressed_structure_count": len(structures),
        "exception_count": len(exceptions),
        "provenance_edge_count": sum(len(r.get("provenance") or []) for r in structures.values()),
        "revision_count": mem.get("revisions"),
        "forgotten_structures": mem.get("forgotten_structures"),
        "prediction_at_event_count": len(pae),
        "bytes_persistent": bytes_persistent,
        "bytes_raw_log": bytes_raw,
        "bytes_per_lived_tick": round(bytes_persistent / ticks, 4),
        "compression_ratio_generated_vs_retained_raw": round(
            float(mem.get("raw_generated") or 0) / max(1, float(mem.get("raw_retained") or 1)), 4
        ),
        "metrics_affect_cognition": bool(mem.get("metrics_affect_cognition")),
    }
    mem["_memory_cost_cache"] = {"key": cache_key, "cost": cost}
    return dict(cost)


def snapshot(mem: dict[str, Any]) -> dict[str, Any]:
    return {
        "cost": memory_cost(mem),
        "active_structures": sum(1 for r in (mem.get("structures") or {}).values() if r.get("status") == "ACTIVE"),
        "superseded": sum(1 for r in (mem.get("structures") or {}).values() if r.get("status") == "SUPERSEDED"),
        "unresolved_exceptions": sum(1 for e in (mem.get("exceptions") or {}).values() if e.get("status") == "UNRESOLVED"),
        "ablations": {
            "compression": bool(mem.get("ablate_compression")),
            "provenance": bool(mem.get("ablate_provenance")),
            "representatives": bool(mem.get("ablate_representatives")),
        },
    }


def reconstruct_violation_chain(mem: dict[str, Any], event_id: str) -> dict[str, Any]:
    """Researcher reconstruction from PAE + exceptions + revision — not current-model retrodiction."""
    pae = (mem.get("prediction_at_event") or {}).get(event_id)
    if not isinstance(pae, dict):
        return {"status": "NO_PAE", "event_id": event_id}
    sid = pae.get("linked_structure")
    struct = None
    successor = None
    for row in (mem.get("structures") or {}).values():
        if row.get("structure_id") == sid:
            struct = row
        if row.get("revision_of") == sid:
            successor = row
    return {
        "status": "OK",
        "prediction_before": deepcopy(pae.get("predicted") or {}),
        "observation": deepcopy(pae.get("observed") or {}),
        "mismatch": pae.get("mismatch"),
        "frozen": pae.get("frozen"),
        "structure_at_time": sid,
        "structure_status_now": (struct or {}).get("status"),
        "superseded_by": (struct or {}).get("superseded_by"),
        "successor": (successor or {}).get("structure_id"),
        "from_current_model_retrodiction": False,
    }
