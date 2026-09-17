from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.research.h003_reversal_world import run_h003
from reversal_yield import ReversalYieldWorld


def main() -> None:
    result = run_h003(
        world_factory=lambda: ReversalYieldWorld(reversal_after=6),
        ticks=18,
        seed=17,
    )
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
