# Update 4 acceptance

Status filled after tests + short A–D runs. Experiment E (10k) prepared, not claimed complete until raw run exists.

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1 | ≥3 channels | PASS | 4 channels |
| 2 | 4 channels preferred | PASS | |
| 3 | Distant before contact | PASS | MULTI_CHANNEL |
| 4 | Detail loss with distance | PASS | feature_count drops |
| 5 | Info content not only amplitude | PASS | feature budget by distance |
| 6 | Passive waves | PASS | emission configs |
| 7 | Waves non-semantic | PASS | |
| 8 | EMIT action | PASS | |
| 9 | EMIT interacts with objects | PASS | reflectivity/geometry |
| 10 | Returns no privileged object id | PASS | stripped for cognition |
| 11 | EMIT no intrinsic reward | PASS | cost only |
| 12 | Same object multi-channel | PASS | |
| 13 | No privileged cross-channel binding | PASS | |
| 14 | Movement alters distant patterns | PASS | by construction |
| 15 | Autonomous motion alters WAIT sensory | PASS | Update 3 + channels |
| 16 | Autonomous remains functional | PASS | |
| 17 | WAIT does not freeze world | PASS | |
| 18 | WAIT does not freeze body | PASS | |
| 19 | Activity accumulates load | PASS | when recovery enabled |
| 20 | Reduced activity recovery | PASS | optional switch |
| 21 | Recovery bounded | PASS | load-scaled + cap |
| 22 | Long WAIT not unlimited benefit | PASS | load drains |
| 23 | No WAIT reward | PASS | |
| 24 | No rest reward | PASS | |
| 25 | No curiosity reward | PASS | |
| 26 | No novelty reward | PASS | |
| 27 | No forced exploration | PASS | |
| 28 | Signals enter ordinary experience | PASS | observation pipeline |
| 29 | No special developmental memory | PASS | |
| 30 | Experience-gated can consume | PASS | ordinary obs |
| 31 | Bounded cognition remains | PASS | |
| 32 | Compression constraints | PASS | |
| 33 | Observer perception panel | PASS | panel 8 |
| 34 | Observer depth panel | PASS | panel 6 |
| 35 | Observer autonomous panel | PASS | panel 7 |
| 36 | Observer activity/recovery panel | PASS | panel 9 |
| 37 | Observer EMIT events | PASS | event list + last EMIT |
| 38 | Agent input vs ground truth | PASS | panels labeled |
| 39 | GT object id not in channel packets | PASS | prior id leak in visible_objects remains documented |
| 40 | Causal timeline for loops | PARTIAL | events enriched; full timeline columns limited |
| 41 | CONTACT_ONLY runnable | PASS | |
| 42 | MULTI_CHANNEL runnable | PASS | |
| 43 | Recovery disableable | PASS | default off |
| 44 | Static world runnable | PASS | |
| 45 | Previous regressions | PASS | full pytest green |
| 46 | Combined 10k runnable | PARTIAL | runner ready; 10k not executed this session |
| 47 | Null behavioral outcomes preserved | PASS | no retuning |
| 48 | No cosmetic parameter tuning | PASS | |

## Final questions (separate)

1. Richer physically available information? **YES** (MULTI_CHANNEL vs CONTACT_ONLY signatures).
2. Richer recorded experience stream? **measure in A–D summary** (unique perception signatures).
3. Experience-gated cognition uses evidence differently? **null-capable; report from depth metrics**.
4. Behavior changes? **null-capable; report action diversity / attractors without retuning**.


## Short A–D numbers (seed 17)

- A: CONTACT_ONLY unique_perception=1 vs MULTI_CHANNEL=14 (same action diversity 3 vs 3)
- B WAIT: static unique=2, dynamic unique=12
- C forced EMIT: emit_count=18
- D recovery off/on wait_fraction=0.0/0.0 action_diversity=3/3

Physics-only smoke: CONTACT unique=2 vs MULTI=27; WAIT-only MULTI unique=12.
