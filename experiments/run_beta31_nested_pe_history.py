#!/usr/bin/env python3
"""Nested PE / TPS / TPE forgotten-history duplication forensic.

Does not start 40k. Does not mutate e02e833b.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path("/home/thehost/Desktop/psy")
OUT = ROOT / "results" / "beta31_nested_pe_history"


def make_runtime():
    from experiments.run_beta31_pe_forgotten_compaction import make_runtime as _mr
    return _mr()


def _pe_stores(slot) -> dict[str, dict]:
    cog = slot.cognition if isinstance(slot.cognition, dict) else {}
    out = {"outer": cog.get("equivalence") or {}}
    temporal = cog.get("temporal") or {}
    out["temporal.inner"] = (temporal.get("inner") if isinstance(temporal, dict) else {}) or {}
    tpe = cog.get("temporal_prediction_error") or {}
    lags = (tpe.get("lags") if isinstance(tpe, dict) else {}) or {}
    for k, v in lags.items():
        inner = (v.get("inner") if isinstance(v, dict) else {}) or {}
        out[f"tpe.lags.{k}.inner"] = inner
    return out


def _payload_bytes(cls) -> bytes | None:
    from mechanistic_mind.research import predictive_equivalence as pe
    if not pe.is_forgotten_packed(cls):
        return None
    keys = pe.forgotten_pack_keys(cls)
    parts = [",".join(keys).encode("utf-8")]
    for sig in sorted((cls.get("members") or {})):
        mem = (cls.get("members") or {})[sig]
        parts.append(str(sig).encode("utf-8"))
        for fld in ("fragment", "mean_c", "last_abs"):
            p = mem.get(fld) if isinstance(mem, dict) else None
            if isinstance(p, dict) and "v" in p:
                parts.append(bytes(p.get("v") or b""))
                parts.append(bytes(p.get("p") or b""))
    return b"\x1e".join(parts)


def _digest(b: bytes | None) -> str | None:
    if not b:
        return None
    return hashlib.sha256(b).hexdigest()[:16]


def summarize_store(store: dict, *, path: str) -> dict:
    from mechanistic_mind.research import predictive_equivalence as pe

    classes = store.get("classes") or {}
    n_act = n_for = packed = n_mem = 0
    schemas = Counter()
    payloads = Counter()
    actions = Counter()
    lag_actions = Counter()
    for cls in classes.values():
        if not isinstance(cls, dict):
            continue
        st = cls.get("status")
        if st == "FORGOTTEN":
            n_for += 1
            if pe.is_forgotten_packed(cls):
                packed += 1
            keys = pe.forgotten_pack_keys(cls)
            schemas[",".join(keys)] += 1
            d = _digest(_payload_bytes(cls))
            if d:
                payloads[d] += 1
            act = str(cls.get("action") or "")
            actions[act.split("|")[0]] += 1
            if "|L" in act:
                lag_actions[act.rsplit("|", 1)[-1]] += 1
        else:
            n_act += 1
        n_mem += len(cls.get("members") or {})
    unique_pay = len(payloads)
    dup_records = sum(c for c in payloads.values() if c > 1)
    return {
        "path": path,
        "implementation": "predictive_equivalence.empty_store",
        "ACTIVE_cap": pe.MAX_CLASSES,
        "total_classes": len(classes),
        "active": n_act,
        "forgotten": n_for,
        "packed_forgotten": packed,
        "hybrid_g": packed == n_for if n_for else True,
        "members": n_mem,
        "unique_pack_schemas": len(schemas),
        "top_schema_share": (schemas.most_common(1)[0][1] / n_for) if n_for and schemas else None,
        "unique_member_payloads": unique_pay,
        "MEMBER_PAYLOAD_DUPLICATION_RATIO": round(1.0 - (unique_pay / n_for), 4) if n_for else None,
        "FULL_RECORD_DUPLICATION_RATIO": round(dup_records / n_for, 4) if n_for else None,
        "lag_action_forgotten": dict(lag_actions),
        "learns": store.get("learns"),
        "forgotten_counter": store.get("forgotten"),
    }


def run() -> dict:
    sys.path.insert(0, str(ROOT))
    os.chdir(str(ROOT))
    OUT.mkdir(parents=True, exist_ok=True)
    from mechanistic_mind.research import predictive_equivalence as pe

    ticks = [int(x) for x in os.environ.get("PSY_NESTED_TICKS", "100,250,500,1000").split(",") if x]
    rt = make_runtime()
    t0 = time.perf_counter()
    samples = []
    cur = 0
    for target in ticks:
        while cur < target:
            rt.step(n=1)
            cur = int(rt.tick)
        slot = rt.slots[0]
        stores = _pe_stores(slot)
        rows = {p: summarize_store(s, path=p) for p, s in stores.items() if isinstance(s, dict)}
        outer_f = rows.get("outer", {}).get("forgotten") or 0
        inner_f = rows.get("temporal.inner", {}).get("forgotten") or 0
        tpe_f = sum(v.get("forgotten") or 0 for k, v in rows.items() if k.startswith("tpe."))
        samples.append({
            "tick": cur,
            "wall_s": round(time.perf_counter() - t0, 3),
            "stores": rows,
            "ratio_inner_to_outer": round(inner_f / outer_f, 3) if outer_f else None,
            "tpe_forgotten": tpe_f,
        })

    last = samples[-1]["stores"] if samples else {}
    inner = last.get("temporal.inner") or {}
    outer = last.get("outer") or {}
    tpe_rows = {k: v for k, v in last.items() if k.startswith("tpe.")}

    # Shadow: interned tuple identity of pack_keys
    intern_hits = 0
    intern_n = 0
    seen_id = set()
    for cls in ((rt.slots[0].cognition.get("temporal") or {}).get("inner") or {}).get("classes") or {}.values():
        if isinstance(cls, dict) and pe.is_forgotten_packed(cls):
            intern_n += 1
            kid = id(cls.get("_pack_keys"))
            if kid in seen_id:
                intern_hits += 1
            seen_id.add(kid)

    # Roundtrip expand on 12 forgotten inner classes
    mismatches = 0
    compared = 0
    inner_store = (rt.slots[0].cognition.get("temporal") or {}).get("inner") or {}
    for cls in list((inner_store.get("classes") or {}).values()):
        if not isinstance(cls, dict) or cls.get("status") != "FORGOTTEN":
            continue
        expanded = pe.expand_forgotten_class(cls)
        packed = pe.compact_forgotten_class(dict(cls))
        again = pe.expand_forgotten_class(packed)
        compared += 1
        if expanded.get("id") != again.get("id") or set((expanded.get("members") or {})) != set((again.get("members") or {})):
            mismatches += 1
        if compared >= 24:
            break

    topology = {
        "cognition.equivalence": last.get("outer"),
        "cognition.temporal.inner": last.get("temporal.inner"),
        "cognition.temporal_prediction_error.lags": tpe_rows,
        "tps_LAGS": [1, 2, 3, 4],
        "tps_learns_per_tick": 4,
        "note": "Each tps.learn calls pe.learn once per lag with action|L{lag} and window-delta fragment.",
    }
    (OUT / "nested_pe_topology.json").write_text(json.dumps(topology, indent=2, default=str), encoding="utf-8")
    (OUT / "duplication_metrics.json").write_text(json.dumps(samples, indent=2, default=str), encoding="utf-8")
    summary = {
        "OUTER_FORGOTTEN": outer.get("forgotten"),
        "TEMPORAL_INNER_FORGOTTEN": inner.get("forgotten"),
        "TPE_FORGOTTEN": sum(v.get("forgotten") or 0 for v in tpe_rows.values()),
        "NESTED_TO_OUTER_CLASS_RATIO": samples[-1].get("ratio_inner_to_outer") if samples else None,
        "MEMBER_PAYLOAD_DUPLICATION_RATIO_inner": inner.get("MEMBER_PAYLOAD_DUPLICATION_RATIO"),
        "FULL_RECORD_DUPLICATION_RATIO_inner": inner.get("FULL_RECORD_DUPLICATION_RATIO"),
        "unique_pack_schemas_inner": inner.get("unique_pack_schemas"),
        "top_schema_share_inner": inner.get("top_schema_share"),
        "pack_keys_intern_reuse": intern_hits,
        "pack_keys_intern_n": intern_n,
        "shadow_roundtrip_compared": compared,
        "shadow_mismatches": mismatches,
        "tps": round((samples[-1]["tick"] / samples[-1]["wall_s"]) if samples and samples[-1]["wall_s"] else 0, 3),
    }
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
