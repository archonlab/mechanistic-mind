"""Cold archive: exact reconstruction, shadow forget, cognition-safe default OFF."""
from __future__ import annotations

from copy import deepcopy
from io import StringIO

from mechanistic_mind.research import pe_cold_archive as cold
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist


def _frag(n: float, width: int = 6, **extra):
    d = {f"k{i}": float(n) + 0.01 * i for i in range(width)}
    d.update(extra)
    return d


def _store():
    s = pe.empty_store()
    s["enabled"] = True
    return s


def _fill(s, *, extra=12, width=6):
    for i in range(pe.MAX_CLASSES + extra):
        pe.learn(
            s,
            fragment=_frag(float(i), width=width),
            action=f"A{i % 5}",
            consequent={"out": float(i) * 10.0, "z": float(i) % 3},
            tick=i,
            raw_id=f"r{i}",
        )


def test_default_cold_off_keeps_forgotten_in_classes():
    pe.set_cold_archive(False)
    pe.set_cold_shadow(False)
    s = _store()
    _fill(s)
    forgotten = [c for c in s["classes"].values() if c.get("status") == "FORGOTTEN"]
    assert forgotten
    assert cold.archive_count(s) == 0


def test_cold_archive_exact_roundtrip_and_pops_python_graph():
    pe.set_cold_archive(True)
    pe.set_cold_shadow(True)
    cold.reset_shadow_stats()
    try:
        s = _store()
        _fill(s, extra=20, width=80)
        in_classes = [c for c in s["classes"].values() if c.get("status") == "FORGOTTEN"]
        assert in_classes == []
        assert cold.archive_count(s) >= 20
        st = cold.shadow_stats()
        assert st["compared"] >= 20
        assert st["mismatches"] == 0
        n = 0
        for rec in cold.iter_cold_records(s, reconstruct=True):
            n += 1
            assert rec["status"] == "FORGOTTEN"
            assert rec["id"].startswith("E")
            expanded = pe.expand_forgotten_class(rec)
            assert expanded["members"]
            assert expanded["mean_c"]
        assert n == cold.archive_count(s)
        assert pe.active_class_count(s) <= pe.MAX_CLASSES
        q = _frag(3.0, width=80)
        for act in ("A0", "A1", "A2"):
            got = pe.retrieve(s, q, act, count=False)
            if got.get("status") == "MATCH":
                assert str(got.get("class_id")) in (s.get("_active_ids") or [])
    finally:
        pe.set_cold_archive(False)
        pe.set_cold_shadow(False)


def test_cold_archive_json_persist_restore():
    pe.set_cold_archive(True)
    pe.set_cold_shadow(False)
    try:
        s = _store()
        _fill(s, extra=8, width=6)
        n = cold.archive_count(s)
        assert n >= 8
        original = [pe.expand_forgotten_class(c) for c in cold.iter_cold_records(s)]
        buf = StringIO()
        dump_persist(s, buf)
        from json import loads

        restored = loads(buf.getvalue())
        pe.clear_derived_caches(restored)
        cold.materialize_arrays(cold.get_archive(restored))
        pe.set_cold_archive(True)
        pe.compact_forgotten_in_store(restored)
        got = [pe.expand_forgotten_class(c) for c in cold.iter_cold_records(restored)]
        assert len(got) == len(original)
        for a, b in zip(original, got):
            assert cold.exact_forgotten_equal(a, b) == []
    finally:
        pe.set_cold_archive(False)


def test_chunk_binary_crc():
    pe.set_cold_archive(True)
    try:
        s = _store()
        _fill(s, extra=4)
        arch = cold.get_archive(s)
        chunk = arch["chunks"][0]
        blob = cold.chunk_binary(arch, chunk)
        assert cold.verify_chunk_binary(blob)
        meta, ch = cold.load_chunk_binary(blob)
        assert ch["n"] == chunk["n"]
        recon = cold.reconstruct_at({"schemas": meta["schemas"], "actions": meta["actions"]}, ch, 0)
        orig = cold.reconstruct_at(arch, chunk, 0)
        assert cold.exact_forgotten_equal(orig, recon) == []
        assert not cold.verify_chunk_binary(blob[:-1] + bytes([(blob[-1] ^ 1)]))
    finally:
        pe.set_cold_archive(False)


def test_analyzer_stream_does_not_require_classes_dict():
    pe.set_cold_archive(True)
    try:
        s = _store()
        _fill(s, extra=10)
        recs = list(cold.iter_cold_records(s, reconstruct=False))
        assert recs
        assert all("members" not in r for r in recs)
        assert s["forgotten"] == len(recs)
    finally:
        pe.set_cold_archive(False)
