#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from mechanistic_mind.research.psychology_analyzer import PsychologyAnalyzer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stream Psychology Observer JSONL into evidence-backed events, epochs, biography, and HTML.")
    parser.add_argument("source", type=Path, help="psychology_observer.jsonl or its run directory")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output directory (default: <run>/analysis)")
    parser.add_argument("--epoch-window", "--phase-window", dest="epoch_window", type=int, default=100, help="Streaming feature window used for epoch detection")
    parser.add_argument("--epoch-change-threshold", type=float, default=0.38, help="Minimum multi-signal distance that starts a new epoch")
    parser.add_argument("--habit-threshold", type=float, default=0.75, help="Conservative habit evidence threshold")
    parser.add_argument("--keep-timeline", action="store_true", help="Write debug timeline.jsonl (off by default)")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = PsychologyAnalyzer(
        epoch_window=args.epoch_window,
        epoch_change_threshold=args.epoch_change_threshold,
        habit_threshold=args.habit_threshold,
    ).analyze(args.source, args.output, keep_timeline=args.keep_timeline)
    print("Psychology analysis complete")
    print(f"Output: {result.output_dir}")
    print(f"Summary: {result.summary}")
    print(f"Meaningful events: {result.meaningful_events}")
    print(f"Behavioral epochs: {result.epochs}")
    print(f"Biography: {result.biography}")
    print(f"Report: {result.report}")
    if result.timeline:
        print(f"Debug timeline: {result.timeline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
