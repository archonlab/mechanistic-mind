# FULL COMPOSITE PSC SHADOW REPLAY

**SHADOW / NON-CAUSAL TO PRODUCTION RUN.** Production PSC remains LOCO_ONLY + COMPOSITE_FACTORIZED side-channels. Nothing in this study was promoted into production selection.

## Primary question

Does replacing locomotion-only candidate representation with empirically observed composite candidates change the result of the **real** downstream chain:

`predicted O′ → historical retrieval / HSS → PSC evidence → compete_scenarios → selected candidate`

when evaluated in shadow mode?

## Production functions reused

1. `sensorimotor_consequence.query` (via snapshot store wrappers `composite_query` / `loco_only_query`)
2. `o_prime_history_bridge.construct_o_prime`
3. `o_prime_history_bridge.query_history_on_o_prime`
4. `o_prime_history_bridge.build_psc_scenario`
5. `scenario_competition.compete_scenarios`
6. `scenario_competition.jsonish_copy` (isolated group trees)
7. `runtime._rng_unit(seed, tick)` — deterministic tie index; **no mutable RNG advance**

Module: `mechanistic_mind/physical_system/full_composite_psc_shadow.py`

## Replay purity / mutation audit

- SMC queries run on `_store_snapshot` (shared read-only records; local query counters).
- Prospection / compression deep-copied (`jsonish_copy`) before history queries.
- `compete_scenarios` receives copied scenario groups.
- RNG: `_rng_unit(seed, tick)` only — same formula production cognition uses; shadow does not consume a mutable RNG stream.
- Paired trajectory: `SHADOW_EXACT_MATCH = true` (250 ticks, seed 111, motors identical with shadow off vs on).

If purity fails: **STOP** (do not promote). This gate passed.

## Wet run

- Seed **111**, TwoAgent, wet world
- Phase A: 150 ticks, PSC OFF, SMC ON, HSS ON, embodied allowlist ON
- Phase B: 100 ticks, PSC ON (no reset)
- Artifacts: `results/full_composite_psc_shadow/`

## Funnel (Phase B)

| Gate | Count |
|------|------:|
| PSC_COMPETITIONS | 100 |
| COMPOSITE_CANDIDATES_AVAILABLE (sum) | 1300 |
| MULTI_COMPOSITE_WITHIN_LOCO | 100 |
| COMPOSITE_EXACT_SMC_PREDICTIONS | 1300 |
| COMPOSITE_O_PRIME_DIFFERENTIATED | 100 |
| COMPOSITE_HISTORY_SUPPORT_DIFFERENTIATED | 89 |
| FULL_COMPETE_SCENARIOS_REPLAYED | 100 |
| SAME_LOCOMOTION_SAME_COMPOSITE | 4 |
| SAME_LOCOMOTION_DIFFERENT_COMPOSITE | 52 |
| DIFFERENT_LOCOMOTION | 44 |
| INSUFFICIENT / NOT_REPLAYABLE | 0 |

### Critical rates (real compete_scenarios)

- **DIFFERENT_LOCOMOTION / replayed = 44/100 = 0.44**
- **SAME_LOCOMOTION_DIFFERENT_COMPOSITE / replayed = 52/100 = 0.52**

These measure **architectural sensitivity**, not better behavior.

Classification compares shadow winner against **production selected locomotion** and **realized COMPOSITE_MOTOR_V1** after COMPOSITE_FACTORIZED side-channels (not only the synthetic `N:NONE` query motor).

## Proxy vs real

Prior support-proxy (separate audit): DIFFERENT_LOCOMOTION **52/200** (upper bound; not real competition).

Same-run confusion (proxy support-ranking vs real compete), n=100:

|  | REAL SAME LOCO | REAL DIFFERENT LOCO |
|--|--:|--:|
| PROXY SAME LOCO | 45 | 20 |
| PROXY DIFFERENT LOCO | 11 | 24 |

- precision (proxy DIFF → real DIFF) ≈ **0.69**
- recall ≈ **0.55**
- agreement ≈ **0.69**

Interpretation: the support proxy **partially tracked** real competition effects but both **over- and under-flagged** locomotion changes. Real replay is required for architecture decisions.

## Motor-dimension attribution (difference cases)

Among SAME_LOCO_DIFFERENT_COMPOSITE + DIFFERENT_LOCOMOTION cases, difference signatures contained:

- neck: 25
- osc_emit: 24
- osc_freq: 25
- osc_amp: 19
- push: 32

Single-dimension clean cases (non-exclusive reporting of singles): emit 13, freq 13, neck 8, push 7, amp 5, locomotion-only 4.

## Sensory-family attribution

Top family by mean |Δ| between production baseline O′ and winning composite O′ (diagnostic only):

- optical: 66
- bilateral: 14
- proprio: 10
- field: 4
- body: 2

## No-vision subset

This wet run: **n = 0** agent ticks with near-zero exo optical energy while bilateral/field energy present. **NOT_RECORDED** for no-vision composite competition change under these conditions.

## Developmental windows (Phase B thirds)

| Window | SAME_COMPOSITE | SAME_LOCO_DIFF_COMPOSITE | DIFFERENT_LOCO |
|--------|--:|--:|--:|
| early_psc | 0 | 9 | 16 |
| middle_psc | 2 | 6 | 17 |
| late_psc | 2 | 37 | 11 |

Motor-resolution sensitivity is present early; late window shows more same-loco composite divergence than different-loco. **Do not assume monotonicity.**

## Performance (shadow only; production cadence unchanged)

Full composite shadow per competition: mean ≈ **46.9 ms**, p50 ≈ 46.5, p95 ≈ 54.4, max ≈ 55.6  
Candidate counts: mean ≈ **13** (p50 12, max 15)

## Observer / Analyzer

- Observer: SIGNAL → PREDICTION → PSC panel, section **MOTOR RESOLUTION** (ANALYSIS ONLY). MINIMAL = DEFERRED.
- Analyzer Next: `full_composite_psc_shadow` product labeled **SHADOW / NON-CAUSAL TO PRODUCTION RUN**.

## Decision gate (evidence answers)

**A.** Yes — full composite resolution changes real PSC competition outcomes in this shadow replay (96/100 not SAME_LOCO_SAME_COMPOSITE).  
**B.** Side-channel / composite realization only: **52/100**.  
**C.** Winning locomotion changes: **44/100**.  
**D.** Associated dimensions: push, neck, osc_emit/freq/amp (often multi-dimension).  
**E.** Predicted futures diverge most often in **optical**, then bilateral / proprio.  
**F.** Proxy agreement ~69%; prior 52/200 is not interchangeable with 44/100 real.  
**G.** See `docs/ADAPTIVE_REFINEMENT_REAL_PSC_STUDY.md`.  
**H.** ~47 ms mean full-composite shadow / tick (this harness).

## Supported claims

- Full composite candidate resolution changes PSC competition under real `compete_scenarios` semantics in shadow.
- Changes selected locomotion in **44/100** replayed cases (this wet run).
- Changes composite realization while preserving locomotion in **52/100** cases.
- Composite-specific O′ can retrieve different historical evidence (89/100 ticks history-support differentiated).
- Motor-resolution sensitivity appears across developmental windows after embodied history (not only late).

## NOT_ESTABLISHED

Better/smarter behavior, planning, intention, attention, communication, language, spatial understanding, optimal motor hierarchy.

## STOP

**Do NOT enable FULL COMPOSITE or ADAPTIVE as production PSC in this task.** Next production architecture decision must use this real shadow replay, not the support proxy alone.
