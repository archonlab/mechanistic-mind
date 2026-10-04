# Acanthostega Beta 4 — Release Packaging, Documentation, and Distribution

Schema: `BETA4_RELEASE_PACKAGING_DOCUMENTATION_AND_DISTRIBUTION_V1`  
Verdict: `C. BETA4_PACKAGING_BLOCKED_MECHANISM_MATRIX_OR_LAUNCH`

## Package location

`Release/MM-Acanthostega-Beta-4.0-Release-Candidate/`

Launch: `./PsyObserver`

## Architecture

Bundled CPython (python-build-standalone) → `.venv_psy_web` → uvicorn FastAPI → `web_dist` SPA → PhysicalSystemRuntime.

## Scientific status

Beta 4: partially validated — bounded supported claims  
Post-V1B S6 current authority.

## Mechanism matrix

See `results/beta4_release_packaging_documentation_and_distribution/FULL_ACANTHOSTEGA_MECHANISM_MATRIX.json`.

## Not done

- Git tag / publish / commit
- AppImage (debt unless tool+recipe completed)
