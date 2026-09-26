# Beta 3.1 — Visual Surface Discrimination Phase 1 Results

**GIT_PUSH = NO**  
**Beta 3 tag unmodified:** `v1.0.0-tiktaalik-public-beta-3`

## Tests

| Suite | Result |
|-------|--------|
| `tests/test_visual_surface_discrimination.py` | PASS |
| `tests/test_physical_perception_01.py` | PASS (SNF cache now keys illumination + surface sum) |
| Beta 3 smokes (preset, packaged restore, ENOSPC, vision symmetry, Analyze Current, config integrity, articulated head) | PASS |

## Determinism

`generate_surface_optical` is seed-namespaced (`surface_optical_c{k}`). Same seed/config → identical tensor checksum. SHUFFLED preserves histogram vs CORRELATED; UNIFORM is constant 0.5.

## OFF equivalence

Same seed, two OFF runtimes: matching observations (no `surface_c*`), poses, selected actions over 12 ticks.

Same seed OFF vs RICH: `sample_near_field` **exo fragments identical** (intensity path unchanged). RICH adds `surface_c*` only.

## Performance (two-agent, seed 20260923, 1000 ticks, PSC auto-on at 1000)

| Mode | mapping | ms/tick | ticks/s | traced peak MB | world+optical bytes | SMC records a0/a1 |
|------|---------|---------|---------|----------------|---------------------|-------------------|
| OFF | INDEPENDENT | 91.9 | 10.9 | 40.6 | 16384 | 119 / 224 |
| LOW | CORRELATED | 100.1 | 10.0 | 48.7 | 40960 | 183 / 256 |
| RICH | CORRELATED | 106.0 | 9.4 | 52.1 | 40960 | 194 / 256 |

5 000 / 10 000 tick arms were **not** run: 1 000 ticks × 3 arms ≈ 5 minutes wall. Use `BETA31_SURFACE_TICKS=5000` for longer.

Vision sampling stays inside the existing Moore loop. Cost growth is modest (~15% RICH vs OFF) plus SMC store growth.

Per-subsystem timers (compression / PE / PSC ms) were **not** separately instrumented in this first pass; wall ms/tick and SMC record counts are the primary Phase 1 meters.

## Controlled experiment (OFF vs RICH)

Question: does a physically available surface distinction change predictive/sensorimotor organization?

**Not claimed:** learned colors, recognized terrain, intention.

At tick 1000 (PSC activating at the tick boundary):

- OFF: no `surface_c*` keys; exo still present  
- RICH: 9 FOV-binned optical keys occupied; exo still present and **not** replaced  
- SMC record counts higher under LOW/RICH (more distinct sensory signatures)  
- Last motors differed across arms (descriptive only; not a success metric)

Raw JSON: `results/beta31_visual_surface_discrimination/off_low_rich.json`

## Save / restore

RICH snapshot includes `surface_optical` tensor. Restore + 5 ticks matches uninterrupted continuation (pose, `surface_c*`, last action). OFF snapshots omit the tensor (Beta 3 size class).

## PSC_OFF_TICKS

Implemented on `CognitionConfig.psc_off_ticks` (`None` = MANUAL). After tick ≥ N, `prospective_scenario_competition` enables without resetting cognition/body/history. Event: `PSC_ACTIVATION` with `history_preserved=true`. Not wired into the Vision UI.

## Limitations

- 5k/10k performance matrix not collected  
- Human Observer production `web_dist` rebuilt in this Phase 1 (`index-DaOFbe1w.js`) with OFF/LOW/RICH controls  
- `optical_mapping` is config-level, not a Phase 1 Experiment dropdown  
- SNF cache now includes `sum(surface_response)` so in-place test mutations invalidate (small extra work per sample)  
- Combinatorial growth of signatures under RICH is real (SMC records); no semantic optimization applied  

## Phase 2 (not started)

Tiktaalik Eye diagnostic: WORLD / AGENT 0 EYE / AGENT 1 EYE / SPLIT at bounded FPS from agent-accessible `surface_c*` / `exo_*`, never feeding cognition.
