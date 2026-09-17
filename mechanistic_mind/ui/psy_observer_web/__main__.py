"""python -m mechanistic_mind.ui.psy_observer_web

Canonical Beta 1 entry: delegates to the same launcher used by
launch_psy_observer.{sh,command,bat} (port selection, lock/reuse, SPA check).
"""
from __future__ import annotations


def main() -> None:
    from mechanistic_mind.ui.psy_observer_web.launcher import main as launcher_main

    raise SystemExit(launcher_main())


if __name__ == "__main__":
    main()
