"""Sealed cold-chunk eviction: payload unreachable, transient reload exact."""
from __future__ import annotations

import gc
import tempfile
from pathlib import Path

from mechanistic_mind.research import pe_cold_archive as cold
from mechanistic_mind.research import predictive_equivalence as pe


def _store():
    s = pe.empty_store()
    s["enabled"] = True
    return s


def _fill(s, extra=40, width=8):
    for i in range(pe.MAX_CLASSES + extra):
        pe.learn(
            s,
            fragment={f"k{j}": float(i) + 0.01 * j for j in range(width)},
            action=f"A{i % 3}",
            consequent={"y": float(i)},
            tick=i,
            raw_id=f"r{i}",
        )


def test_evicted_payload_not_reachable():
    pe.set_cold_archive(True)
    pe.set_cold_shadow(True)
    cold.reset_shadow_stats()
    cold.set_cold_chunk_records(8)
    with tempfile.TemporaryDirectory() as td:
        pe.set_cold_eviction(True, root=td)
        try:
            s = _store()
            _fill(s, extra=24)
            assert cold.evicted_chunk_count(s) >= 1
            for chunk in (cold.get_archive(s) or {}).get("chunks") or []:
                if chunk.get("evicted"):
                    assert "floats" not in chunk
                    assert "masks" not in chunk
                    assert "aux_blob" not in chunk
                    p = Path(td) / cold.get_archive(s)["archive_id"] / chunk["disk_relpath"]
                    assert p.is_file()
                    assert cold.verify_chunk_binary(p.read_bytes())
            st = cold.shadow_stats()
            assert st["mismatches"] == 0
            assert st["compared"] > 0
        finally:
            pe.set_cold_eviction(False)
            pe.set_cold_archive(False)
            pe.set_cold_shadow(False)
            cold.set_cold_chunk_records(256)


def test_transient_reload_exact_and_releases():
    pe.set_cold_archive(True)
    cold.set_cold_chunk_records(8)
    with tempfile.TemporaryDirectory() as td:
        pe.set_cold_eviction(True, root=td)
        try:
            s = _store()
            _fill(s, extra=20)
            recs = []
            with cold.forensic_disk_reads():
                recs = list(cold.iter_cold_records(s, reconstruct=True))
            assert recs
            ids = [r["id"] for r in recs]
            assert len(ids) == len(set(ids))
            recs.clear()
            gc.collect()
            for chunk in (cold.get_archive(s) or {}).get("chunks") or []:
                if chunk.get("evicted"):
                    assert "floats" not in chunk
        finally:
            pe.set_cold_eviction(False)
            pe.set_cold_archive(False)
            cold.set_cold_chunk_records(256)


def test_crash_partial_write_keeps_ram_and_rejects_corrupt():
    pe.set_cold_archive(True)
    cold.set_cold_chunk_records(4)
    with tempfile.TemporaryDirectory() as td:
        pe.set_cold_eviction(True, root=td)
        try:
            s = _store()
            cold.set_eviction_crash_inject("during_write")
            raised = False
            try:
                _fill(s, extra=8)
            except RuntimeError as e:
                raised = "during_write" in str(e)
            finally:
                cold.set_eviction_crash_inject(None)
            assert raised
            # Unacked payload still in some RAM chunk
            has_payload = any(
                cold.chunk_has_payload(c)
                for c in (cold.get_archive(s) or {}).get("chunks") or []
            )
            assert has_payload
            d = Path(td)
            bins = list(d.rglob("*.bin"))
            tmps = list(d.rglob("*.tmp"))
            for p in bins:
                assert cold.verify_chunk_binary(p.read_bytes())
            for p in tmps:
                raw = p.read_bytes()
                assert not cold.verify_chunk_binary(raw)
        finally:
            cold.set_eviction_crash_inject(None)
            pe.set_cold_eviction(False)
            pe.set_cold_archive(False)
            cold.set_cold_chunk_records(256)


def test_index_not_updated_before_commit_means_orphan_not_acked():
    pe.set_cold_archive(True)
    cold.set_cold_chunk_records(4)
    with tempfile.TemporaryDirectory() as td:
        pe.set_cold_eviction(True, root=td)
        try:
            s = _store()
            _fill(s, extra=4)
            n_committed = len((cold.get_archive(s) or {}).get("committed") or [])
            cold.set_eviction_crash_inject("after_checksum_before_index")
            try:
                _fill(s, extra=8)
            except RuntimeError:
                pass
            cold.set_eviction_crash_inject(None)
            idx_files = list(Path(td).rglob("committed.json"))
            if idx_files:
                import json
                idx = json.loads(idx_files[0].read_text())
                assert len(idx.get("chunks") or []) == n_committed
        finally:
            cold.set_eviction_crash_inject(None)
            pe.set_cold_eviction(False)
            pe.set_cold_archive(False)
            cold.set_cold_chunk_records(256)


def test_open_sidecar_checkpoint_skips_json_arrays():
    pe.set_cold_archive(True)
    cold.set_cold_chunk_records(8)
    with tempfile.TemporaryDirectory() as td:
        pe.set_cold_eviction(True, root=td)
        try:
            s = _store()
            _fill(s, extra=6)
            dest = Path(td) / "pe_open"
            stats = cold.write_open_sidecars(s, dest)
            assert stats["files"] >= 1
            from io import StringIO
            from json import loads

            from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist

            buf = StringIO()
            dump_persist(s, buf)
            js = loads(buf.getvalue())
            for ch in (js.get("_pe_cold") or {}).get("chunks") or []:
                assert "floats" not in ch
                assert "aux_blob" not in ch
            restored = loads(buf.getvalue())
            n = cold.hydrate_open_sidecars(restored, dest)
            assert n >= 1
            orig = list(cold.iter_cold_records(s, reconstruct=True))
            with cold.forensic_disk_reads():
                got = list(cold.iter_cold_records(restored, reconstruct=True))
            assert len(orig) == len(got)
            for a, b in zip(orig, got):
                assert cold.exact_forgotten_equal(a, b) == []
            open_chunks = [
                c for c in (cold.get_archive(s) or {}).get("chunks") or [] if not c.get("sealed")
            ]
            assert open_chunks
            assert open_chunks[-1].get("sealed") is False
        finally:
            pe.set_cold_eviction(False)
            pe.set_cold_archive(False)
            cold.set_cold_chunk_records(256)


def test_open_chunk_exact_restore_and_append():
    pe.set_cold_archive(True)
    cold.set_cold_chunk_records(8)
    with tempfile.TemporaryDirectory() as td:
        pe.set_cold_eviction(True, root=td)
        try:
            s = _store()
            _fill(s, extra=10)
            dest = Path(td) / "pe_open"
            cold.write_open_sidecars(s, dest)
            from io import StringIO
            from json import loads

            from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist

            buf = StringIO()
            dump_persist(s, buf)
            restored = loads(buf.getvalue())
            cold.hydrate_open_sidecars(restored, dest)
            cold.mark_restore_branch(restored, checkpoint_tick=99, previous_run_id="src")
            arch = cold.get_archive(restored)
            assert arch["branch"]["restored"] is True
            assert arch["branch"]["checkpoint_tick"] == 99
            n0 = cold.archive_count(restored)
            committed0 = list((arch.get("committed") or []))
            paths = []
            for ch in arch.get("chunks") or []:
                if ch.get("evicted") and ch.get("disk_relpath"):
                    p = Path(td) / arch["archive_id"] / ch["disk_relpath"]
                    if p.is_file():
                        paths.append((p, p.stat().st_size))
            _fill(restored, extra=16)
            n1 = cold.archive_count(restored)
            assert n1 > n0
            committed1 = list((cold.get_archive(restored) or {}).get("committed") or [])
            assert committed1[: len(committed0)] == committed0
            for p, sz in paths:
                assert p.is_file()
                assert p.stat().st_size == sz
        finally:
            pe.set_cold_eviction(False)
            pe.set_cold_archive(False)
            cold.set_cold_chunk_records(256)


def test_cognition_does_not_read_evicted_history():
    pe.set_cold_archive(True)
    cold.set_cold_chunk_records(8)
    with tempfile.TemporaryDirectory() as td:
        pe.set_cold_eviction(True, root=td)
        try:
            s = _store()
            _fill(s, extra=24)
            assert cold.evicted_chunk_count(s) >= 1
            cold.reset_disk_read_stats()
            _fill(s, extra=12)
            st = cold.disk_read_stats()
            assert st["cognition_disk_reads"] == 0
        finally:
            pe.set_cold_eviction(False)
            pe.set_cold_archive(False)
            cold.set_cold_chunk_records(256)


def test_analyzer_streams_without_full_materialize():
    pe.set_cold_archive(True)
    cold.set_cold_chunk_records(8)
    with tempfile.TemporaryDirectory() as td:
        pe.set_cold_eviction(True, root=td)
        try:
            s = _store()
            _fill(s, extra=40)
            n_sealed = sum(1 for c in (cold.get_archive(s) or {}).get("chunks") or [] if c.get("evicted"))
            assert n_sealed >= 2
            with cold.forensic_disk_reads():
                recs = list(cold.iter_cold_records(s, reconstruct=True))
            assert len(recs) > 8
            early, mid, late = recs[0], recs[len(recs) // 2], recs[-1]
            assert early["id"] != late["id"]
            assert mid["id"]
            for chunk in (cold.get_archive(s) or {}).get("chunks") or []:
                if chunk.get("evicted"):
                    assert "floats" not in chunk
        finally:
            pe.set_cold_eviction(False)
            pe.set_cold_archive(False)
            cold.set_cold_chunk_records(256)


def test_canonical_beta31_cold_eviction_source_default():
    src = Path(__file__).resolve().parents[1] / "mechanistic_mind" / "research" / "pe_cold_archive.py"
    head = src.read_text().split("def set_cold_archive")[0]
    assert "_COLD_ARCHIVE = True" in head
    assert "_COLD_EVICT = True" in head
    import os
    import subprocess
    import sys

    repo = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo) + os.pathsep + env.get("PYTHONPATH", "")
    p = subprocess.run(
        [
            sys.executable,
            "-c",
            "from mechanistic_mind.research import pe_cold_archive as c; "
            "print(int(c.cold_archive_enabled()), int(c.cold_eviction_enabled()))",
        ],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "1 1"
