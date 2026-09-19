# Source inventory (pre-copy)

Audited development tree: lab `psy` (authoritative science).
Packaging target: `MM-2.0-Tiktaalik-Undercover-Public-Beta-1` (separate clean tree).

## Top-level classification

| Path | Class | Decision |
|------|-------|----------|
| mechanistic_mind/ | REQUIRED_RUNTIME + REQUIRED_UI | INCLUDE (filter caches) |
| web/ | REQUIRED_UI (source) | INCLUDE without node_modules |
| web_dist (under mechanistic_mind/ui/...) | REQUIRED_UI | INCLUDE (prebuilt) |
| configs/ | REQUIRED_EXAMPLE | INCLUDE |
| docs/ | REQUIRED_SCIENTIFIC_REFERENCE | INCLUDE |
| knowledge/ | REQUIRED_SCIENTIFIC_REFERENCE | INCLUDE |
| worlds/ | REQUIRED_RUNTIME | INCLUDE |
| mm/ | REQUIRED_SCIENTIFIC_REFERENCE | INCLUDE |
| packaging/ | REQUIRED_BOOTSTRAP | INCLUDE |
| tools/ | REQUIRED_SCIENTIFIC_REFERENCE | INCLUDE (small) |
| tests/ | TEST_ONLY (intentional public) | INCLUDE curated |
| experiments/*.py | REQUIRED_EXAMPLE / DEV_ONLY mix | INCLUDE `.py` only; drop dumps |
| scripts/bootstrap_psy_observer_env.py | REQUIRED_BOOTSTRAP | INCLUDE (from prior public template; missing in lab) |
| launch_psy_observer.* / PsyObserver | REQUIRED_BOOTSTRAP | INCLUDE (bootstrap launchers from public template) |
| requirements-observer.txt | REQUIRED_BOOTSTRAP | INCLUDE (from public template) |
| LICENSE / COPYRIGHT / COMMERCIAL_LICENSING.md | REQUIRED_DOCUMENTATION | INCLUDE (prior public AGPL; not invented) |
| README / CHANGELOG / release docs | REQUIRED_DOCUMENTATION | REWRITE for MM 2.0 in dest |
| results/ | RESULT_ONLY | EXCLUDE bulk; empty placeholder |
| Release/ | GENERATED / prior packages | EXCLUDE |
| .git/ | DEV_ONLY | EXCLUDE |
| .venv_psy_web/ | MACHINE_LOCAL | EXCLUDE |
| node_modules/ | CACHE | EXCLUDE |
| __pycache__/ .pytest_cache/ | CACHE | EXCLUDE |
| .psy_observer/ | MACHINE_LOCAL | EXCLUDE |
| telemetry/ | RESULT_ONLY | EXCLUDE |
| observer_launcher.py / psychology_*.py | DEV_ONLY / legacy | EXCLUDE |
| PSYCHOLOGY OBSERVER.sh | DEV_ONLY | EXCLUDE |
| archon.json | DEV_ONLY | EXCLUDE |
| tmp* | CACHE | EXCLUDE |

## UNKNOWN resolved

| Item | Resolution |
|------|------------|
| Lab missing LICENSE | Restored from prior public AGPL package (historical decision) |
| Lab launchers lack bootstrap | Use public-template bootstrap launchers |
| Lab missing requirements-observer.txt | Restored from public template |
| Absolute `<LOCAL_HOME>` in SIGINT analysis helpers | Sanitized in public copy only (defaults → None) |
| Desktop github_pat file | Never in psy tree; not copied |

## Secret / private audit (lab → package)

- No `.env`, PEM, credentials.json in packaged tree
- No GitHub tokens in package
- Absolute developer paths removed from packaged runtime/analysis defaults
- Docs may mention `<PACKAGE_ROOT>` placeholders after sanitize
