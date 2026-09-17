from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.research.h002_simpler_alternative import run_h002
from two_choice_yield import TwoChoiceYieldWorld


def main() -> None:
    result = run_h002(
        world_factory=TwoChoiceYieldWorld,
        ticks=12,
        seed=17,
    )
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
