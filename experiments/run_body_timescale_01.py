#!/usr/bin/env python3
"""Thin entrypoints — artifacts produced by run_world_timescale_calibration_01.py."""
from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "run_world_timescale_calibration_01.py"), run_name="__main__")
