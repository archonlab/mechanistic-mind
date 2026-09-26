"""Dense append-only cold archive for FORGOTTEN PE classes.

Forgotten classes do not participate in learn/retrieve. This module stores
their scientifically complete payload in chunked structure-of-arrays form
instead of one Python object graph per class.

Does not change PE formation, ACTIVE cap, or forget victim selection.
"""
from __future__ import annotations

import json
import os
import struct
import time
import traceback
import zlib
from array import array
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from mechanistic_mind.research.tick_profiler import span as _prof_span

from mechanistic_mind.research.predictive_equivalence import (
    FORGOTTEN_REP_V1,
    compact_forgotten_class,
    expand_forgotten_class,
    forgotten_pack_keys,
    is_forgotten_packed,
    _as_darray,
    _as_mask,
    _intern_pack_keys,
    _pack_float_map,
)

COLD_REP_V1 = "pe.forgotten.cold.v1"
CHUNK_RECORDS_DEFAULT = 256
MAGIC = b"PECA"
FORMAT_VERSION = 1

_COLD_ARCHIVE = True
_COLD_SHADOW = False
_COLD_EVICT = True
_EVICT_ROOT: Path | None = None
_CHUNK_RECORDS = CHUNK_RECORDS_DEFAULT
_SHADOW_MISMATCHES = 0
_SHADOW_COMPARED = 0
_SHADOW_LAST_DIFFS: list[str] = []
_SHADOW_LAST_ID: str | None = None
_ARCHIVE_SEQ = 0
_INJECT_CRASH: str | None = None
_FORENSIC_READS_OK = 0
_DISK_READS = 0
_COGNITION_DISK_READS = 0
_COGNITION_DISK_TRACE: str | None = None
_COMMIT_FAILURES = 0

PAYLOAD_KEYS = (
    "class_num",
    "id_fallback",
    "action_ix",
    "support",
    "first_tick",
    "revised_at",
    "schema_ix",
    "n_members",
    "member_base",
    "float_off",
    "mask_off",
    "aux_off",
    "aux_len",
    "mem_support",
    "mem_contra",
    "mem_first",
    "mem_last",
    "mem_sig_off",
    "mem_sig_len",
    "floats",
    "masks",
    "sig_blob",
    "aux_blob",
)


def set_cold_archive(enabled: bool) -> None:
    global _COLD_ARCHIVE
    _COLD_ARCHIVE = bool(enabled)


def cold_archive_enabled() -> bool:
    return bool(_COLD_ARCHIVE)


def set_cold_shadow(enabled: bool) -> None:
    global _COLD_SHADOW
    _COLD_SHADOW = bool(enabled)


def cold_shadow_enabled() -> bool:
    return bool(_COLD_SHADOW)


def set_cold_chunk_records(n: int) -> None:
    global _CHUNK_RECORDS
    _CHUNK_RECORDS = max(1, int(n))


def cold_chunk_records() -> int:
    return int(_CHUNK_RECORDS)


def set_cold_eviction(enabled: bool, *, root: str | Path | None = None) -> None:
    """After a sealed chunk is durably committed, drop RAM payload.

    Tiktaalik Beta 3.1 default is enabled. Does not change PE learn/retrieve.
    """
    global _COLD_EVICT, _EVICT_ROOT
    _COLD_EVICT = bool(enabled)
    if root is not None:
        _EVICT_ROOT = Path(root)
    elif enabled and _EVICT_ROOT is None:
        _EVICT_ROOT = Path(
            os.environ.get("PSY_COLD_EVICT_ROOT")
            or (Path.cwd() / ".psy_pe_cold" / "live")
        )


def cold_eviction_enabled() -> bool:
    return bool(_COLD_EVICT)


def eviction_root() -> Path | None:
    return _EVICT_ROOT


def set_eviction_crash_inject(stage: str | None) -> None:
    """Test-only: before_write | during_write | after_write_before_commit | after_checksum_before_index | after_commit_before_evict."""
    global _INJECT_CRASH
    _INJECT_CRASH = stage


def reset_disk_read_stats() -> None:
    global _DISK_READS, _COGNITION_DISK_READS, _COGNITION_DISK_TRACE, _COMMIT_FAILURES
    _DISK_READS = 0
    _COGNITION_DISK_READS = 0
    _COGNITION_DISK_TRACE = None
    _COMMIT_FAILURES = 0


def disk_read_stats() -> dict[str, Any]:
    return {
        "disk_reads": int(_DISK_READS),
        "cognition_disk_reads": int(_COGNITION_DISK_READS),
        "cognition_trace": _COGNITION_DISK_TRACE,
        "commit_failures": int(_COMMIT_FAILURES),
    }


@contextmanager
def forensic_disk_reads():
    global _FORENSIC_READS_OK
    _FORENSIC_READS_OK += 1
    try:
        yield
    finally:
        _FORENSIC_READS_OK -= 1


def shadow_stats() -> dict[str, Any]:
    return {
        "compared": int(_SHADOW_COMPARED),
        "mismatches": int(_SHADOW_MISMATCHES),
        "last_id": _SHADOW_LAST_ID,
        "last_diffs": list(_SHADOW_LAST_DIFFS[:12]),
    }


def reset_shadow_stats() -> None:
    global _SHADOW_COMPARED, _SHADOW_MISMATCHES, _SHADOW_LAST_DIFFS, _SHADOW_LAST_ID
    _SHADOW_COMPARED = 0
    _SHADOW_MISMATCHES = 0
    _SHADOW_LAST_DIFFS = []
    _SHADOW_LAST_ID = None


def _empty_chunk() -> dict[str, Any]:
    return {
        "n": 0,
        "class_num": array("I"),
        "id_fallback": [],
        "action_ix": array("H"),
        "support": array("I"),
        "first_tick": array("i"),
        "revised_at": array("i"),
        "schema_ix": array("H"),
        "n_members": array("B"),
        "member_base": array("I"),
        "float_off": array("I"),
        "mask_off": array("I"),
        "aux_off": array("I"),
        "aux_len": array("I"),
        "mem_support": array("I"),
        "mem_contra": array("H"),
        "mem_first": array("i"),
        "mem_last": array("i"),
        "mem_sig_off": array("I"),
        "mem_sig_len": array("I"),
        "floats": array("d"),
        "masks": array("B"),
        "sig_blob": array("B"),
        "aux_blob": array("B"),
        "sealed": False,
        "evicted": False,
        "state": "OPEN_RAM",
        "chunk_id": None,
        "disk_relpath": None,
        "crc": None,
        "disk_bytes": None,
        "first_class_num": None,
        "last_class_num": None,
        "first_tick_meta": None,
        "last_tick_meta": None,
    }


def empty_archive() -> dict[str, Any]:
    return {
        "rep": COLD_REP_V1,
        "version": FORMAT_VERSION,
        "chunk_records": int(_CHUNK_RECORDS),
        "n": 0,
        "schemas": [],
        "actions": [],
        "chunks": [],
        "archive_id": None,
        "evict_root": None,
        "committed": [],
        "next_chunk_id": 0,
    }


def get_archive(store: dict[str, Any]) -> dict[str, Any] | None:
    raw = store.get("_pe_cold")
    return raw if isinstance(raw, dict) else None


def ensure_archive(store: dict[str, Any]) -> dict[str, Any]:
    raw = store.get("_pe_cold")
    if not isinstance(raw, dict) or raw.get("rep") != COLD_REP_V1:
        raw = empty_archive()
        store["_pe_cold"] = raw
    _ensure_archive_identity(raw)
    return raw


def _ensure_archive_identity(arch: dict[str, Any]) -> None:
    global _ARCHIVE_SEQ, _EVICT_ROOT
    if _COLD_EVICT and _EVICT_ROOT is None:
        _EVICT_ROOT = Path(os.environ.get("PSY_COLD_EVICT_ROOT") or (Path.cwd() / ".psy_pe_cold" / "live"))
    if arch.get("archive_id"):
        if _COLD_EVICT and _EVICT_ROOT is not None and not arch.get("evict_root"):
            arch["evict_root"] = str(_EVICT_ROOT)
        return
    if not (_COLD_EVICT and _EVICT_ROOT is not None):
        return
    _ARCHIVE_SEQ += 1
    arch["archive_id"] = f"peca_{os.getpid()}_{_ARCHIVE_SEQ}_{int(time.time() * 1000) % 100000000}"
    arch["evict_root"] = str(_EVICT_ROOT)
    Path(arch["evict_root"], arch["archive_id"]).mkdir(parents=True, exist_ok=True)


def archive_count(store: dict[str, Any]) -> int:
    arch = get_archive(store)
    return int(arch.get("n") or 0) if arch else 0


def _schema_index(arch: dict[str, Any], keys: tuple[str, ...]) -> int:
    keys = _intern_pack_keys(tuple(str(k) for k in keys))
    schemas: list[tuple[str, ...]] = arch["schemas"]
    for i, s in enumerate(schemas):
        if s == keys:
            return i
    schemas.append(keys)
    return len(schemas) - 1


def _action_index(arch: dict[str, Any], action: str) -> int:
    actions: list[str] = arch["actions"]
    act = str(action)
    for i, a in enumerate(actions):
        if a == act:
            return i
    actions.append(act)
    return len(actions) - 1


def _class_num(cid: str) -> tuple[int, str | None]:
    s = str(cid)
    if len(s) >= 2 and s[0] == "E" and s[1:].isdigit():
        n = int(s[1:])
        if 0 <= n <= 0xFFFFFFFF:
            return n, None
    return 0, s


def _pack_map_onto(floats: array, masks: array, packed: dict[str, Any] | None, keys: tuple[str, ...]) -> None:
    n = len(keys)
    if isinstance(packed, dict) and "v" in packed:
        vals = _as_darray(packed.get("v"), n)
        mask = _as_mask(packed.get("p"), n)
    else:
        tmp = _pack_float_map(packed if isinstance(packed, dict) else {}, keys)
        vals = tmp["v"]
        mask = tmp["p"]
    floats.extend(vals)
    masks.extend(mask)


def _pack_aabb(floats: array, masks: array, aabb: Any, keys: tuple[str, ...]) -> None:
    n = len(keys)
    lo = array("d", [0.0] * n)
    hi = array("d", [0.0] * n)
    mask = bytearray((n + 7) >> 3)
    if isinstance(aabb, dict):
        for i, k in enumerate(keys):
            span = aabb.get(k)
            if not span:
                continue
            try:
                lo[i] = float(span[0])
                hi[i] = float(span[1])
            except (TypeError, ValueError, IndexError):
                continue
            mask[i >> 3] |= 1 << (i & 7)
    floats.extend(lo)
    floats.extend(hi)
    masks.extend(array("B", mask))


def _current_chunk(arch: dict[str, Any]) -> dict[str, Any]:
    chunks = arch["chunks"]
    cap = int(arch.get("chunk_records") or _CHUNK_RECORDS)
    if not chunks or int(chunks[-1].get("n") or 0) >= cap or chunks[-1].get("sealed"):
        chunks.append(_empty_chunk())
    return chunks[-1]


def append_forgotten_class(store: dict[str, Any], cls: dict[str, Any]) -> dict[str, Any]:
    """Serialize one FORGOTTEN class into the store archive. Does not pop the class."""
    if not isinstance(cls, dict) or cls.get("status") != "FORGOTTEN":
        return cls
    if not is_forgotten_packed(cls):
        compact_forgotten_class(cls)
    arch = ensure_archive(store)
    keys = forgotten_pack_keys(cls)
    if not keys:
        keyset: set[str] = set()
        for mem in (cls.get("members") or {}).values():
            if not isinstance(mem, dict):
                continue
            for fld in ("fragment", "mean_c", "last_abs"):
                mp = mem.get(fld)
                if isinstance(mp, dict) and "v" not in mp:
                    keyset.update(str(k) for k in mp)
        mc = cls.get("mean_c")
        if isinstance(mc, dict) and "v" not in mc:
            keyset.update(str(k) for k in mc)
        for k in (cls.get("aabb") or {}):
            keyset.add(str(k))
        keys = _intern_pack_keys(tuple(sorted(keyset)))
        compact_forgotten_class(cls)
        keys = forgotten_pack_keys(cls) or keys
    schema_ix = _schema_index(arch, keys)
    n_keys = len(keys)
    chunk = _current_chunk(arch)
    members = cls.get("members") or {}
    mem_items = list(members.items()) if isinstance(members, dict) else []
    n_mem = len(mem_items)
    cid = str(cls.get("id") or "")
    num, fallback = _class_num(cid)
    aux = {
        "provenance": list(cls.get("provenance") or []),
        "relevance": cls.get("relevance") if isinstance(cls.get("relevance"), dict) else None,
        "raw_ids": [list((m.get("raw_ids") or []) if isinstance(m, dict) else []) for _, m in mem_items],
        "id_fallback": fallback,
        "aabb_extra": {
            str(k): [float(v[0]), float(v[1])]
            for k, v in (cls.get("aabb") or {}).items()
            if k not in keys and isinstance(v, (list, tuple)) and len(v) >= 2
        },
    }
    aux_b = json.dumps(aux, ensure_ascii=False, separators=(",", ":"), allow_nan=True).encode("utf-8")
    aux_arr = array("B")
    aux_arr.frombytes(aux_b)

    chunk["class_num"].append(num)
    if fallback is not None:
        while len(chunk["id_fallback"]) < int(chunk["n"]):
            chunk["id_fallback"].append(None)
        chunk["id_fallback"].append(fallback)
    else:
        chunk["id_fallback"].append(None)
    chunk["action_ix"].append(_action_index(arch, str(cls.get("action") or "")))
    chunk["support"].append(int(cls.get("support") or 0) & 0xFFFFFFFF)
    chunk["first_tick"].append(int(cls.get("first_tick") or 0))
    rev = cls.get("revised_at")
    chunk["revised_at"].append(int(rev) if rev is not None else -1)
    chunk["schema_ix"].append(schema_ix)
    chunk["n_members"].append(min(n_mem, 255))
    chunk["member_base"].append(len(chunk["mem_support"]))
    chunk["float_off"].append(len(chunk["floats"]))
    chunk["mask_off"].append(len(chunk["masks"]))
    chunk["aux_off"].append(len(chunk["aux_blob"]))
    chunk["aux_len"].append(len(aux_b))
    chunk["aux_blob"].extend(aux_arr)

    for sig, mem in mem_items:
        if not isinstance(mem, dict):
            mem = {}
        sb = array("B")
        sb.frombytes(str(sig).encode("utf-8"))
        chunk["mem_sig_off"].append(len(chunk["sig_blob"]))
        chunk["mem_sig_len"].append(len(sb))
        chunk["sig_blob"].extend(sb)
        chunk["mem_support"].append(int(mem.get("support") or 0) & 0xFFFFFFFF)
        chunk["mem_contra"].append(int(mem.get("contra") or 0) & 0xFFFF)
        chunk["mem_first"].append(int(mem.get("first_tick") or 0))
        chunk["mem_last"].append(int(mem.get("last_tick") or 0))
        _pack_map_onto(chunk["floats"], chunk["masks"], mem.get("fragment"), keys)
        _pack_map_onto(chunk["floats"], chunk["masks"], mem.get("mean_c"), keys)
        _pack_map_onto(chunk["floats"], chunk["masks"], mem.get("last_abs"), keys)

    _pack_map_onto(chunk["floats"], chunk["masks"], cls.get("mean_c"), keys)
    _pack_aabb(chunk["floats"], chunk["masks"], cls.get("aabb") or {}, keys)

    chunk["n"] = int(chunk["n"]) + 1
    cap = int(arch.get("chunk_records") or _CHUNK_RECORDS)
    if chunk["n"] >= cap:
        seal_chunk(chunk)
    arch["n"] = int(arch.get("n") or 0) + 1
    return cls


def seal_chunk(chunk: dict[str, Any]) -> None:
    with _prof_span("cold_seal"):
        if chunk.get("sealed"):
            return
        chunk["sealed"] = True
        if not chunk.get("evicted"):
            chunk["state"] = "SEALING"


def _bit_get(mask: array, base: int, i: int) -> bool:
    return bool(mask[base + (i >> 3)] & (1 << (i & 7)))


def _unpack_from(floats: array, masks: array, foff: int, moff: int, keys: tuple[str, ...]) -> tuple[dict[str, Any], int, int]:
    n = len(keys)
    nbytes = (n + 7) >> 3
    packed = {
        "v": array("d", floats[foff : foff + n] if n else []),
        "p": array("B", masks[moff : moff + nbytes] if nbytes else []),
    }
    return packed, foff + n, moff + nbytes


def _aabb_from(floats: array, masks: array, foff: int, moff: int, keys: tuple[str, ...]) -> tuple[dict[str, list[float]], int, int]:
    n = len(keys)
    nbytes = (n + 7) >> 3
    lo = floats[foff : foff + n]
    hi = floats[foff + n : foff + 2 * n]
    out: dict[str, list[float]] = {}
    for i, k in enumerate(keys):
        if _bit_get(masks, moff, i):
            out[k] = [float(lo[i]), float(hi[i])]
    return out, foff + 2 * n, moff + nbytes


def reconstruct_at(arch: dict[str, Any], chunk: dict[str, Any], i: int) -> dict[str, Any]:
    keys = tuple(arch["schemas"][int(chunk["schema_ix"][i])])
    n_keys = len(keys)
    nbytes = (n_keys + 7) >> 3
    n_mem = int(chunk["n_members"][i])
    mbase = int(chunk["member_base"][i])
    foff = int(chunk["float_off"][i])
    moff = int(chunk["mask_off"][i])
    aux_off = int(chunk["aux_off"][i])
    aux_len = int(chunk["aux_len"][i])
    aux_raw = chunk["aux_blob"][aux_off : aux_off + aux_len]
    if isinstance(aux_raw, array):
        aux_raw = aux_raw.tobytes()
    else:
        aux_raw = bytes(aux_raw)
    aux = json.loads(aux_raw.decode("utf-8")) if aux_raw else {}
    num = int(chunk["class_num"][i])
    fallback = aux.get("id_fallback")
    if not fallback and chunk.get("id_fallback"):
        fb_list = chunk["id_fallback"]
        if i < len(fb_list) and fb_list[i]:
            fallback = fb_list[i]
    cid = str(fallback) if fallback else f"E{num}"
    action = str(arch["actions"][int(chunk["action_ix"][i])])
    members: dict[str, Any] = {}
    raw_ids = aux.get("raw_ids") or []
    sig_blob = chunk["sig_blob"]
    for j in range(n_mem):
        mj = mbase + j
        so = int(chunk["mem_sig_off"][mj])
        sl = int(chunk["mem_sig_len"][mj])
        slc = sig_blob[so : so + sl]
        sig = (slc.tobytes() if isinstance(slc, array) else bytes(slc)).decode("utf-8")
        frag, foff, moff = _unpack_from(chunk["floats"], chunk["masks"], foff, moff, keys)
        mc, foff, moff = _unpack_from(chunk["floats"], chunk["masks"], foff, moff, keys)
        la, foff, moff = _unpack_from(chunk["floats"], chunk["masks"], foff, moff, keys)
        members[sig] = {
            "support": int(chunk["mem_support"][mj]),
            "contra": int(chunk["mem_contra"][mj]),
            "first_tick": int(chunk["mem_first"][mj]),
            "last_tick": int(chunk["mem_last"][mj]),
            "raw_ids": list(raw_ids[j]) if j < len(raw_ids) else [],
            "fragment": frag,
            "mean_c": mc,
            "last_abs": la,
        }
    mean_c, foff, moff = _unpack_from(chunk["floats"], chunk["masks"], foff, moff, keys)
    aabb, _, _ = _aabb_from(chunk["floats"], chunk["masks"], foff, moff, keys)
    extra = aux.get("aabb_extra") or {}
    if extra:
        aabb = dict(aabb)
        aabb.update(extra)
    rev = int(chunk["revised_at"][i])
    out = {
        "id": cid,
        "action": action,
        "status": "FORGOTTEN",
        "support": int(chunk["support"][i]),
        "members": members,
        "aabb": aabb,
        "mean_c": mean_c,
        "first_tick": int(chunk["first_tick"][i]),
        "revised_at": None if rev < 0 else rev,
        "provenance": list(aux.get("provenance") or []),
        "_pack_keys": keys,
        "_pe_forgotten_rep": FORGOTTEN_REP_V1,
    }
    rel = aux.get("relevance")
    if rel is not None:
        out["relevance"] = rel
    return out


def iter_cold_records(store: dict[str, Any], *, reconstruct: bool = True) -> Iterator[dict[str, Any]]:
    arch = get_archive(store)
    if not arch:
        return
        yield  # pragma: no cover
    actions = arch.get("actions") or []
    for chunk in arch.get("chunks") or []:
        n = int(chunk.get("n") or 0)
        if chunk.get("evicted"):
            if reconstruct:
                with forensic_disk_reads():
                    loaded = hydrate_chunk(arch, chunk)
                try:
                    for i in range(int(loaded.get("n") or 0)):
                        yield reconstruct_at(arch, loaded, i)
                finally:
                    loaded = None
            else:
                yield {
                    "id": f"E{chunk.get('first_class_num')}" if chunk.get("first_class_num") is not None else None,
                    "action": "",
                    "status": "FORGOTTEN",
                    "support": None,
                    "n_members": None,
                    "first_tick": chunk.get("first_tick_meta"),
                    "revised_at": None,
                    "evicted_chunk": True,
                    "chunk_id": chunk.get("chunk_id"),
                    "n": n,
                    "last_id": f"E{chunk.get('last_class_num')}" if chunk.get("last_class_num") is not None else None,
                }
            continue
        for i in range(n):
            if reconstruct:
                yield reconstruct_at(arch, chunk, i)
            else:
                num = int(chunk["class_num"][i])
                fb = None
                if chunk.get("id_fallback") and i < len(chunk["id_fallback"]):
                    fb = chunk["id_fallback"][i]
                yield {
                    "id": str(fb) if fb else f"E{num}",
                    "action": actions[int(chunk["action_ix"][i])] if actions else "",
                    "status": "FORGOTTEN",
                    "support": int(chunk["support"][i]),
                    "n_members": int(chunk["n_members"][i]),
                    "first_tick": int(chunk["first_tick"][i]),
                    "revised_at": None if int(chunk["revised_at"][i]) < 0 else int(chunk["revised_at"][i]),
                }


def forgotten_in_classes(store: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        c
        for c in (store.get("classes") or {}).values()
        if isinstance(c, dict) and c.get("status") == "FORGOTTEN"
    ]


def iter_forgotten(store: dict[str, Any], *, reconstruct: bool = True) -> Iterator[dict[str, Any]]:
    yield from forgotten_in_classes(store)
    yield from iter_cold_records(store, reconstruct=reconstruct)


def forgotten_total(store: dict[str, Any]) -> int:
    return len(forgotten_in_classes(store)) + archive_count(store)


def migrate_forgotten_to_cold(store: dict[str, Any]) -> int:
    """Move remaining Python FORGOTTEN graphs into the archive (restore / enable)."""
    classes = store.get("classes") or {}
    moved = 0
    drop: list[str] = []
    for cid, cls in list(classes.items()):
        if not isinstance(cls, dict) or cls.get("status") != "FORGOTTEN":
            continue
        append_forgotten_class(store, cls)
        drop.append(str(cid))
        moved += 1
    for cid in drop:
        classes.pop(cid, None)
    if _COLD_EVICT:
        arch = get_archive(store)
        if arch:
            for chunk in list(arch.get("chunks") or []):
                if chunk.get("sealed") and not chunk.get("evicted") and chunk_has_payload(chunk):
                    try:
                        commit_and_evict_chunk(arch, chunk)
                    except Exception:
                        pass
    return moved


def archive_allocated_bytes(store: dict[str, Any]) -> int:
    import sys

    arch = get_archive(store)
    if not arch:
        return 0
    n = sys.getsizeof(arch)
    n += sys.getsizeof(arch.get("schemas") or [])
    for s in arch.get("schemas") or []:
        n += sys.getsizeof(s)
    n += sys.getsizeof(arch.get("actions") or [])
    for a in arch.get("actions") or []:
        n += sys.getsizeof(a)
    for chunk in arch.get("chunks") or []:
        n += sys.getsizeof(chunk)
        for k, v in chunk.items():
            n += sys.getsizeof(k)
            n += sys.getsizeof(v)
            if isinstance(v, list):
                for x in v:
                    n += sys.getsizeof(x)
    return n


def exact_forgotten_equal(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """Return mismatch paths; empty means exact scientific payload match."""
    ea = expand_forgotten_class(a)
    eb = expand_forgotten_class(b)
    diffs: list[str] = []

    def walk(x: Any, y: Any, path: str) -> None:
        if type(x) is not type(y) and not (
            isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool) and not isinstance(y, bool)
        ):
            if x is None and y is None:
                return
            if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
                pass
            elif isinstance(x, dict) and isinstance(y, dict):
                pass
            else:
                diffs.append(f"{path}: type {type(x).__name__} vs {type(y).__name__}")
                return
        if isinstance(x, dict):
            if set(x) != set(y):
                diffs.append(f"{path}: keys {sorted(set(x) ^ set(y))[:8]}")
            for k in set(x) | set(y):
                if k in ("_pack_keys", "_pe_forgotten_rep", "_mean_c_cached", "_mean_c_gen") or str(k).startswith("_"):
                    continue
                walk(x.get(k), y.get(k) if isinstance(y, dict) else None, f"{path}.{k}")
            return
        if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
            if len(x) != len(y):
                diffs.append(f"{path}: len {len(x)} vs {len(y)}")
                return
            for i, (xi, yi) in enumerate(zip(x, y)):
                walk(xi, yi, f"{path}[{i}]")
            return
        if isinstance(x, float) and isinstance(y, float):
            if struct.pack("<d", x) != struct.pack("<d", y):
                diffs.append(f"{path}: float {x!r} vs {y!r}")
            return
        if x != y:
            diffs.append(f"{path}: {x!r} vs {y!r}")

    walk(ea, eb, "cls")
    return diffs


def compare_shadow(original: dict[str, Any], reconstructed: dict[str, Any]) -> bool:
    global _SHADOW_COMPARED, _SHADOW_MISMATCHES, _SHADOW_LAST_DIFFS, _SHADOW_LAST_ID
    _SHADOW_COMPARED += 1
    diffs = exact_forgotten_equal(original, reconstructed)
    if diffs:
        _SHADOW_MISMATCHES += 1
        _SHADOW_LAST_DIFFS = diffs
        _SHADOW_LAST_ID = str(original.get("id"))
        return False
    return True


def maybe_archive_after_forget(store: dict[str, Any], classes: dict[str, Any], victim: str, cls: dict[str, Any]) -> None:
    if not (_COLD_ARCHIVE or _COLD_SHADOW):
        return
    append_forgotten_class(store, cls)
    if _COLD_SHADOW:
        arch = get_archive(store)
        chunk = arch["chunks"][-1]
        if chunk.get("evicted"):
            with forensic_disk_reads():
                loaded = hydrate_chunk(arch, chunk)
            recon = reconstruct_at(arch, loaded, int(loaded["n"]) - 1)
        else:
            recon = reconstruct_at(arch, chunk, int(chunk["n"]) - 1)
        compare_shadow(cls, recon)
    if _COLD_ARCHIVE:
        classes.pop(victim, None)
    if _COLD_EVICT:
        arch = get_archive(store)
        if arch:
            for chunk in list(arch.get("chunks") or []):
                if chunk.get("sealed") and not chunk.get("evicted") and "floats" in chunk:
                    commit_and_evict_chunk(arch, chunk)


def materialize_arrays(arch: dict[str, Any] | None) -> None:
    """After JSON restore, coerce lists back to array.array / bytes."""
    if not isinstance(arch, dict):
        return
    schemas = []
    for s in arch.get("schemas") or []:
        schemas.append(tuple(str(k) for k in s))
    arch["schemas"] = schemas
    arch["actions"] = [str(a) for a in (arch.get("actions") or [])]
    for chunk in arch.get("chunks") or []:
        if chunk.get("evicted"):
            continue
        if chunk.get("open_sidecar") and not isinstance(chunk.get("floats"), (list, tuple, array)):
            continue
        for key, code in (
            ("class_num", "I"),
            ("action_ix", "H"),
            ("support", "I"),
            ("first_tick", "i"),
            ("revised_at", "i"),
            ("schema_ix", "H"),
            ("n_members", "B"),
            ("member_base", "I"),
            ("float_off", "I"),
            ("mask_off", "I"),
            ("aux_off", "I"),
            ("aux_len", "I"),
            ("mem_support", "I"),
            ("mem_contra", "H"),
            ("mem_first", "i"),
            ("mem_last", "i"),
            ("mem_sig_off", "I"),
            ("mem_sig_len", "I"),
            ("floats", "d"),
            ("masks", "B"),
        ):
            raw = chunk.get(key)
            if isinstance(raw, array):
                continue
            chunk[key] = array(code, raw or [])
        for blob_key in ("sig_blob", "aux_blob"):
            raw = chunk.get(blob_key)
            if isinstance(raw, array) and raw.typecode == "B":
                continue
            if isinstance(raw, (bytes, bytearray)):
                a = array("B")
                a.frombytes(bytes(raw))
                chunk[blob_key] = a
            elif isinstance(raw, list):
                chunk[blob_key] = array("B", (int(x) & 255 for x in raw))
            elif isinstance(raw, str):
                a = array("B")
                a.frombytes(raw.encode("latin1"))
                chunk[blob_key] = a
            else:
                chunk[blob_key] = array("B")
        fb = chunk.get("id_fallback")
        if not isinstance(fb, list):
            chunk["id_fallback"] = []


def chunk_binary(arch: dict[str, Any], chunk: dict[str, Any], *, mark_sealed: bool = False) -> bytes:
    """Explicit little-endian payload for a chunk (not pickle).

    Does not mark the live chunk sealed unless ``mark_sealed`` (commit path).
    Checkpoint uses this for OPEN_RAM without changing chunk lifecycle.
    """
    if mark_sealed:
        seal_chunk(chunk)
    meta = {
        "version": FORMAT_VERSION,
        "n": int(chunk["n"]),
        "schemas": [list(s) for s in arch.get("schemas") or []],
        "actions": list(arch.get("actions") or []),
        "id_fallback": list(chunk.get("id_fallback") or []),
        "endian": "little",
        "dtype": {
            "floats": "float64",
            "masks": "uint8",
            "class_num": "uint32",
        },
    }
    meta_b = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    parts = [MAGIC, struct.pack("<HI", FORMAT_VERSION, len(meta_b)), meta_b]
    for key in (
        "class_num",
        "action_ix",
        "support",
        "first_tick",
        "revised_at",
        "schema_ix",
        "n_members",
        "member_base",
        "float_off",
        "mask_off",
        "aux_off",
        "aux_len",
        "mem_support",
        "mem_contra",
        "mem_first",
        "mem_last",
        "mem_sig_off",
        "mem_sig_len",
        "floats",
        "masks",
    ):
        buf = chunk[key].tobytes()
        parts.append(struct.pack("<I", len(buf)))
        parts.append(buf)
    for blob_key in ("sig_blob", "aux_blob"):
        raw = chunk[blob_key]
        buf = raw.tobytes() if isinstance(raw, array) else bytes(raw)
        parts.append(struct.pack("<I", len(buf)))
        parts.append(buf)
    body = b"".join(parts)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def verify_chunk_binary(blob: bytes) -> bool:
    if len(blob) < 14:
        return False
    crc_stored = struct.unpack_from("<I", blob, len(blob) - 4)[0]
    body = blob[:-4]
    return (zlib.crc32(body) & 0xFFFFFFFF) == crc_stored and body.startswith(MAGIC)


_CHUNK_ARRAY_SPEC = (
    ("class_num", "I"),
    ("action_ix", "H"),
    ("support", "I"),
    ("first_tick", "i"),
    ("revised_at", "i"),
    ("schema_ix", "H"),
    ("n_members", "B"),
    ("member_base", "I"),
    ("float_off", "I"),
    ("mask_off", "I"),
    ("aux_off", "I"),
    ("aux_len", "I"),
    ("mem_support", "I"),
    ("mem_contra", "H"),
    ("mem_first", "i"),
    ("mem_last", "i"),
    ("mem_sig_off", "I"),
    ("mem_sig_len", "I"),
    ("floats", "d"),
    ("masks", "B"),
)


def load_chunk_binary(blob: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    """Decode a chunk sidecar. Raises ValueError if magic/crc/version fail."""
    if not verify_chunk_binary(blob):
        raise ValueError("cold chunk checksum or magic failed")
    body = blob[:-4]
    if body[0:4] != MAGIC:
        raise ValueError("bad magic")
    ver, meta_len = struct.unpack_from("<HI", body, 4)
    if ver != FORMAT_VERSION:
        raise ValueError(f"unsupported cold chunk version {ver}")
    off = 4 + 2 + 4
    meta = json.loads(body[off : off + meta_len].decode("utf-8"))
    off += meta_len
    chunk = _empty_chunk()
    for key, code in _CHUNK_ARRAY_SPEC:
        n = struct.unpack_from("<I", body, off)[0]
        off += 4
        buf = body[off : off + n]
        off += n
        a = array(code)
        a.frombytes(buf)
        chunk[key] = a
    for blob_key in ("sig_blob", "aux_blob"):
        n = struct.unpack_from("<I", body, off)[0]
        off += 4
        buf = body[off : off + n]
        off += n
        a = array("B")
        a.frombytes(buf)
        chunk[blob_key] = a
    chunk["n"] = int(meta.get("n") or 0)
    chunk["id_fallback"] = list(meta.get("id_fallback") or [])
    chunk["sealed"] = True
    arch_meta = {
        "schemas": [tuple(str(k) for k in s) for s in (meta.get("schemas") or [])],
        "actions": list(meta.get("actions") or []),
        "version": ver,
        "endian": meta.get("endian"),
        "dtype": meta.get("dtype"),
    }
    return arch_meta, chunk


def _note_disk_read() -> None:
    global _DISK_READS, _COGNITION_DISK_READS, _COGNITION_DISK_TRACE
    _DISK_READS += 1
    if _FORENSIC_READS_OK <= 0:
        _COGNITION_DISK_READS += 1
        if _COGNITION_DISK_TRACE is None:
            _COGNITION_DISK_TRACE = "".join(traceback.format_stack(limit=16))


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_bytes_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    stage = _INJECT_CRASH
    if stage == "before_write":
        raise RuntimeError("injected crash before_write")
    with open(tmp, "wb") as f:
        if stage == "during_write":
            f.write(data[: max(1, len(data) // 2)])
            f.flush()
            os.fsync(f.fileno())
            raise RuntimeError("injected crash during_write")
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    if stage == "after_write_before_commit":
        raise RuntimeError("injected crash after_write_before_commit")
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def _archive_dir(arch: dict[str, Any]) -> Path:
    _ensure_archive_identity(arch)
    root = Path(str(arch.get("evict_root") or _EVICT_ROOT or "/tmp/psy_pe_cold_evict"))
    aid = str(arch.get("archive_id") or "anon")
    d = root / aid
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path(arch: dict[str, Any]) -> Path:
    return _archive_dir(arch) / "committed.json"


def _write_committed_index(arch: dict[str, Any]) -> None:
    idx = {
        "version": 1,
        "rep": COLD_REP_V1,
        "archive_id": arch.get("archive_id"),
        "chunk_records": arch.get("chunk_records"),
        "n_records": int(arch.get("n") or 0),
        "chunks": list(arch.get("committed") or []),
    }
    raw = json.dumps(idx, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if _INJECT_CRASH == "after_checksum_before_index":
        raise RuntimeError("injected crash after_checksum_before_index")
    _atomic_bytes_write(_index_path(arch), raw)


def strip_chunk_payload(chunk: dict[str, Any]) -> None:
    for k in PAYLOAD_KEYS:
        chunk.pop(k, None)
    chunk["evicted"] = True
    chunk["sealed"] = True
    chunk["state"] = "EVICTED_DISK"


def chunk_has_payload(chunk: dict[str, Any]) -> bool:
    return isinstance(chunk.get("floats"), array) and not chunk.get("evicted")


def commit_and_evict_chunk(arch: dict[str, Any], chunk: dict[str, Any]) -> dict[str, Any]:
    """Durable PECA write then drop RAM payload. On failure keep RAM and report."""
    global _COMMIT_FAILURES
    if chunk.get("evicted"):
        return chunk
    if not chunk.get("sealed"):
        seal_chunk(chunk)
    if not chunk_has_payload(chunk):
        return chunk
    n = int(chunk.get("n") or 0)
    first_num = int(chunk["class_num"][0]) if n else None
    last_num = int(chunk["class_num"][n - 1]) if n else None
    first_tick = int(chunk["first_tick"][0]) if n else None
    last_tick = int(chunk["first_tick"][n - 1]) if n else None
    try:
        with _prof_span("cold_evict"):
            blob = chunk_binary(arch, chunk)
            crc = struct.unpack_from("<I", blob, len(blob) - 4)[0]
            cid = int(arch.get("next_chunk_id") or 0)
            rel = f"chunk_{cid:06d}.bin"
            dest = _archive_dir(arch) / rel
            with _prof_span("cold_disk_write"):
                _atomic_bytes_write(dest, blob)
        rec = {
            "chunk_id": cid,
            "file": rel,
            "crc": crc,
            "n": n,
            "bytes": len(blob),
            "first_class_num": first_num,
            "last_class_num": last_num,
            "first_tick": first_tick,
            "last_tick": last_tick,
        }
        committed = list(arch.get("committed") or [])
        committed.append(rec)
        arch["committed"] = committed
        arch["next_chunk_id"] = cid + 1
        _write_committed_index(arch)
        chunk["chunk_id"] = cid
        chunk["disk_relpath"] = rel
        chunk["crc"] = crc
        chunk["disk_bytes"] = len(blob)
        chunk["first_class_num"] = first_num
        chunk["last_class_num"] = last_num
        chunk["first_tick_meta"] = first_tick
        chunk["last_tick_meta"] = last_tick
        chunk["state"] = "SEALED_RAM"
        if _INJECT_CRASH == "after_commit_before_evict":
            raise RuntimeError("injected crash after_commit_before_evict")
        strip_chunk_payload(chunk)
        return chunk
    except Exception:
        _COMMIT_FAILURES += 1
        chunk["state"] = "SEALED_RAM"
        raise


def hydrate_chunk(arch: dict[str, Any], chunk: dict[str, Any]) -> dict[str, Any]:
    """Return a payload-bearing chunk dict. Evicted chunks load from disk (transient)."""
    if chunk_has_payload(chunk):
        return chunk
    rel = chunk.get("disk_relpath")
    if not rel:
        raise ValueError("evicted chunk missing disk_relpath")
    path = _archive_dir(arch) / str(rel)
    blob = path.read_bytes()
    _note_disk_read()
    meta, loaded = load_chunk_binary(blob)
    loaded["state"] = "LOADED_TRANSIENT"
    if meta.get("schemas") and not arch.get("schemas"):
        arch["schemas"] = meta["schemas"]
    if meta.get("actions") and not arch.get("actions"):
        arch["actions"] = meta["actions"]
    return loaded


def archive_disk_bytes(store: dict[str, Any]) -> int:
    arch = get_archive(store)
    if not arch:
        return 0
    n = 0
    for rec in arch.get("committed") or []:
        n += int(rec.get("bytes") or 0)
    return n


def resident_index_bytes(store: dict[str, Any]) -> int:
    import sys

    arch = get_archive(store)
    if not arch:
        return 0
    n = sys.getsizeof(arch)
    for k in ("archive_id", "evict_root", "committed", "schemas", "actions", "n", "next_chunk_id"):
        n += sys.getsizeof(k)
        n += sys.getsizeof(arch.get(k))
    for rec in arch.get("committed") or []:
        n += sys.getsizeof(rec)
        if isinstance(rec, dict):
            for a, b in rec.items():
                n += sys.getsizeof(a) + sys.getsizeof(b)
    for chunk in arch.get("chunks") or []:
        if chunk.get("evicted"):
            n += sys.getsizeof(chunk)
            for a, b in chunk.items():
                n += sys.getsizeof(a) + sys.getsizeof(b)
        elif chunk_has_payload(chunk):
            n += sys.getsizeof(chunk.get("floats")) + sys.getsizeof(chunk.get("masks"))
    return n


def evicted_chunk_count(store: dict[str, Any]) -> int:
    arch = get_archive(store)
    if not arch:
        return 0
    return sum(1 for c in (arch.get("chunks") or []) if c.get("evicted"))


def open_chunk_bytes(store: dict[str, Any]) -> int:
    import sys

    arch = get_archive(store)
    if not arch:
        return 0
    n = 0
    for chunk in arch.get("chunks") or []:
        if chunk.get("evicted") or chunk.get("sealed"):
            continue
        n += sys.getsizeof(chunk)
        for k, v in chunk.items():
            n += sys.getsizeof(v)
    return n


def iter_pe_stores(root: Any) -> Iterator[dict[str, Any]]:
    """Yield PE store dicts from a runtime, cognition mapping, or snapshot."""
    if root is None:
        return
        yield  # pragma: no cover
    slots = getattr(root, "slots", None)
    if slots:
        for slot in slots:
            cog = getattr(slot, "cognition", None)
            yield from iter_pe_stores(cog)
        return
    cog = getattr(root, "cognition", None)
    if isinstance(cog, dict) and cog is not root:
        yield from iter_pe_stores(cog)
        return
    if not isinstance(root, dict):
        return
        yield  # pragma: no cover
    if root.get("rep") == COLD_REP_V1:
        return
    if isinstance(root.get("classes"), dict) or root.get("_pe_cold") is not None:
        yield root
    eq = root.get("equivalence")
    if isinstance(eq, dict):
        yield eq
    temporal = root.get("temporal")
    if isinstance(temporal, dict):
        inner = temporal.get("inner")
        if isinstance(inner, dict):
            yield inner
    tpe = root.get("temporal_prediction_error")
    if isinstance(tpe, dict):
        lags = tpe.get("lags") or {}
        if isinstance(lags, dict):
            for v in lags.values():
                if isinstance(v, dict):
                    inn = v.get("inner")
                    if isinstance(inn, dict):
                        yield inn
    cog = root.get("cognition")
    if isinstance(cog, dict):
        yield from iter_pe_stores(cog)
    for ag in root.get("agents") or []:
        if isinstance(ag, dict):
            yield from iter_pe_stores(ag)


def write_open_sidecars(root: Any, dest: Path) -> dict[str, Any]:
    """Write PECA binaries for resident OPEN_RAM payloads. Does not strip live arrays."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    total = 0
    files: list[str] = []
    for store in iter_pe_stores(root):
        arch = get_archive(store)
        if not arch:
            continue
        _ensure_archive_identity(arch)
        for i, chunk in enumerate(arch.get("chunks") or []):
            if not chunk_has_payload(chunk):
                continue
            aid = str(arch.get("archive_id") or "open")
            rel = f"open_{aid}_{i}.peca"
            blob = chunk_binary(arch, chunk, mark_sealed=False)
            path = dest / rel
            tmp = path.with_name(path.name + ".tmp")
            with open(tmp, "wb") as f:
                f.write(blob)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
            chunk["open_sidecar"] = rel
            chunk["open_sidecar_bytes"] = len(blob)
            n += 1
            total += len(blob)
            files.append(rel)
    return {"files": n, "bytes": total, "relpaths": files, "dir": str(dest)}


def hydrate_open_sidecars(root: Any, dest: Path | None) -> int:
    """Load OPEN_RAM PECA sidecars into chunk arrays after JSON restore."""
    if dest is None:
        return 0
    dest = Path(dest)
    if not dest.is_dir():
        return 0
    loaded_n = 0
    for store in iter_pe_stores(root):
        arch = get_archive(store)
        if not arch:
            continue
        materialize_arrays(arch)
        for chunk in arch.get("chunks") or []:
            if chunk.get("evicted"):
                continue
            rel = chunk.get("open_sidecar")
            if not rel:
                continue
            if chunk_has_payload(chunk) and len(chunk.get("floats") or []) > 0:
                continue
            path = dest / str(rel)
            if not path.is_file():
                raise FileNotFoundError(f"missing OPEN_RAM sidecar {path}")
            meta, loaded = load_chunk_binary(path.read_bytes())
            if meta.get("schemas") and not arch.get("schemas"):
                arch["schemas"] = meta["schemas"]
            if meta.get("actions") and not arch.get("actions"):
                arch["actions"] = meta["actions"]
            for k in PAYLOAD_KEYS:
                if k in loaded:
                    chunk[k] = loaded[k]
            chunk["n"] = int(loaded.get("n") or 0)
            chunk["sealed"] = False
            chunk["evicted"] = False
            chunk["state"] = "OPEN_RAM"
            loaded_n += 1
    return loaded_n


def mark_restore_branch(root: Any, *, checkpoint_tick: int, previous_run_id: str | None = None) -> None:
    for store in iter_pe_stores(root):
        arch = get_archive(store)
        if not arch:
            continue
        arch["branch"] = {
            "restored": True,
            "checkpoint_tick": int(checkpoint_tick),
            "previous_run_id": previous_run_id,
            "note": "New continuation branch; do not merge dead post-checkpoint ticks.",
        }


def cold_json_skip_keys(chunk: dict[str, Any]) -> bool:
    """True if dump_persist must omit SOA payload keys (sidecar or evicted)."""
    return bool(chunk.get("open_sidecar") or chunk.get("evicted") or chunk.get("disk_relpath"))



