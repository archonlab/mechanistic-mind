"""SAFE allocation-churn helpers: identical bytes, less temporary joining."""
from __future__ import annotations

import json

import numpy as np

from mechanistic_mind.scientific_v3.writer import ScientificV3Writer
from mechanistic_mind.ui.psy_observer_web.serialize import _flat_grid, _grid


def test_flat_grid_matches_nested_row_major():
    rng = np.random.default_rng(7)
    a = rng.normal(size=(32, 32))
    flat = _flat_grid(a, max_side=64)
    nested = _grid(a, max_side=64)
    assert flat["h"] == 32 and flat["w"] == 32
    assert flat["data"] == [float(v) for row in nested for v in row]


def test_v3_flush_line_write_matches_join(tmp_path):
    rows = [{"tick": i, "x": "café", "n": i * 3} for i in range(5)]
    expected = "".join(
        json.dumps(r, ensure_ascii=False, separators=(",", ":"), default=str) + "\n" for r in rows
    )
    w = ScientificV3Writer(tmp_path, flush_every=100)
    w.open(run_id="flush-eq")
    for r in rows:
        w._bufs["decisions"].append(
            json.dumps(r, ensure_ascii=False, separators=(",", ":"), default=str)
        )
        w._counts["decisions"] += 1
    w.flush()
    got = (tmp_path / "scientific_decisions.jsonl").read_text(encoding="utf-8")
    assert got == expected
